from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MASTER_PATH = DATA_DIR / "master_scenario_elements.jsonl"
INDEX_PATH = DATA_DIR / "index.json"
RUN_LOG_PATH = DATA_DIR / "run_log.jsonl"

USER_AGENT = os.getenv("SCENARIO_DB_USER_AGENT", "scenario-master-db-auto/1.0")
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
JIKAN_TOP_MANGA = "https://api.jikan.moe/v4/top/manga"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def normalise_title(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_year(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.match(r"^(\d{4})", value)
    if not match:
        return None
    year = int(match.group(1))
    if 1500 <= year <= utc_now().year + 2:
        return year
    return None


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def http_get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    try:
        response = HTTP.get(url, params=params, timeout=35)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def wikidata_query(sparql: str) -> List[Dict[str, Any]]:
    try:
        response = HTTP.get(
            WIKIDATA_ENDPOINT,
            params={"query": sparql, "format": "json"},
            headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
            timeout=45,
        )
        response.raise_for_status()
        return response.json().get("results", {}).get("bindings", [])
    except requests.RequestException:
        return []


def binding(row: Dict[str, Any], key: str) -> Optional[str]:
    return (row.get(key) or {}).get("value")


def collect_wikidata_medium(medium: str, class_qid: str, limit: int, offset: int) -> List[Dict[str, Any]]:
    sparql = f"""
SELECT ?item ?itemLabel ?itemDescription ?pubDate ?genreLabel ?countryLabel ?sitelinks WHERE {{
  ?item wdt:P31/wdt:P279* wd:{class_qid} .
  ?item wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= 20)
  OPTIONAL {{ ?item wdt:P577 ?pubDate . }}
  OPTIONAL {{ ?item wdt:P136 ?genre . }}
  OPTIONAL {{ ?item wdt:P495 ?country . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,ja" . }}
}}
ORDER BY DESC(?sitelinks)
LIMIT {int(limit)}
OFFSET {int(offset)}
"""
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in wikidata_query(sparql):
        item_url = binding(row, "item")
        title = normalise_title(binding(row, "itemLabel") or "")
        if not item_url or not title:
            continue
        qid = item_url.rsplit("/", 1)[-1]
        rid = f"wd:{qid}"
        record = grouped.setdefault(
            rid,
            {
                "record_id": rid,
                "canonical_title": title,
                "medium": medium,
                "release_year": parse_year(binding(row, "pubDate")),
                "countries": [],
                "genres": [],
                "popularity": {"wikidata_sitelinks": int(float(binding(row, "sitelinks") or 0))},
                "external_ids": {"wikidata_qid": qid},
                "source_urls": [item_url],
                "public_description": binding(row, "itemDescription") or "",
                "source": "wikidata",
            },
        )
        genre = binding(row, "genreLabel")
        country = binding(row, "countryLabel")
        if genre and genre not in record["genres"]:
            record["genres"].append(genre)
        if country and country not in record["countries"]:
            record["countries"].append(country)
    return list(grouped.values())


def collect_jikan_manga(limit: int, seed: int) -> List[Dict[str, Any]]:
    payload = http_get_json(JIKAN_TOP_MANGA, params={"page": seed % 20 + 1})
    records = []
    for item in (payload or {}).get("data", [])[:limit]:
        mal_id = item.get("mal_id")
        title = normalise_title(item.get("title_english") or item.get("title") or "")
        if not mal_id or not title:
            continue
        published = item.get("published") or {}
        genres = []
        for group in ["genres", "themes", "demographics"]:
            genres.extend(g.get("name") for g in item.get(group, []) if g.get("name"))
        records.append(
            {
                "record_id": f"jikan:manga:{mal_id}",
                "canonical_title": title,
                "medium": "manga",
                "release_year": parse_year(published.get("from")),
                "countries": ["Japan"],
                "genres": sorted(set(genres)),
                "popularity": {
                    "mal_score": item.get("score"),
                    "mal_rank": item.get("rank"),
                    "mal_popularity": item.get("popularity"),
                    "mal_members": item.get("members"),
                },
                "external_ids": {"mal_id": mal_id},
                "source_urls": [item.get("url")],
                "public_description": "",
                "source": "jikan",
            }
        )
    return records


def infer_scenario_elements(record: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join(
        [str(g).lower() for g in record.get("genres", [])]
        + [str(record.get("public_description", "")).lower(), str(record.get("canonical_title", "")).lower()]
    )
    conflict = []
    emotion = []
    setting = []
    themes = []
    hooks = []

    rules = [
        (("mystery", "detective", "crime", "thriller"), "mystery/revelation", "suspense"),
        (("horror", "supernatural", "monster"), "survival", "fear"),
        (("romance", "romantic"), "relationship/choice", "longing"),
        (("comedy", "comic"), "social friction", "laughter"),
        (("adventure", "fantasy", "quest"), "quest/journey", "wonder"),
        (("action", "battle", "war"), "physical confrontation", "adrenaline"),
        (("drama", "family"), "inner/social pressure", "empathy"),
        (("sports",), "competition", "underdog drive"),
    ]
    for keywords, c, e in rules:
        if any(k in text for k in keywords):
            conflict.append(c)
            emotion.append(e)

    if any(k in text for k in ["school", "student", "campus"]):
        setting.append("school/youth")
        themes.append("coming of age")
    if any(k in text for k in ["space", "future", "sci-fi", "science fiction"]):
        setting.append("speculative/sci-fi")
    if any(k in text for k in ["fantasy", "magic", "isekai"]):
        setting.append("fantasy world")
    if any(k in text for k in ["family"]):
        themes.append("family bonds")
    if any(k in text for k in ["crime", "detective", "mystery"]):
        themes.append("truth and justice")

    pop = record.get("popularity") or {}
    if (pop.get("wikidata_sitelinks") or 0) >= 75:
        hooks.append("high-recognition work")
    if pop.get("mal_rank") and pop.get("mal_rank") <= 100:
        hooks.append("top-ranked manga")

    return {
        "genre_mix": sorted(set(record.get("genres", [])))[:12],
        "conflict_axis": sorted(set(conflict or ["goal vs obstacle"])),
        "emotional_engine": sorted(set(emotion or ["curiosity"])),
        "setting_tags": sorted(set(setting or ["unspecified/public metadata only"])),
        "theme_tags": sorted(set(themes or ["to be manually classified"])),
        "hook_tags": sorted(set(hooks)),
        "analysis_note": "Auto-inferred from public metadata only; verify manually before use.",
    }


def enrich_record(record: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(record)
    for key in ["genres", "countries", "source_urls"]:
        record[key] = sorted(set(x for x in record.get(key, []) if x))
    record["scenario_elements"] = infer_scenario_elements(record)
    record["updated_at"] = iso_now()
    record.setdefault("created_at", record["updated_at"])
    return record


def collect_candidates(batch_size: int) -> List[Dict[str, Any]]:
    seed = int(utc_now().strftime("%Y%m%d%H")) + int(os.getenv("GITHUB_RUN_NUMBER", "0") or "0")
    random.seed(seed)
    limit = max(batch_size * 2, 12)
    offset = (seed * 37) % 1500
    items = []
    items.extend(collect_wikidata_medium("film", "Q11424", limit, offset))
    items.extend(collect_wikidata_medium("novel", "Q8261", limit, (offset + 200) % 1500))
    items.extend(collect_jikan_manga(limit, seed))
    random.shuffle(items)
    return items[:batch_size]


def merge_records(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    by_id = {row.get("record_id"): row for row in existing if row.get("record_id")}
    created = 0
    updated = 0
    for raw in incoming:
        rid = raw.get("record_id") or f"auto:{stable_hash(str(raw))}"
        raw["record_id"] = rid
        new = enrich_record(raw)
        if rid in by_id:
            new["created_at"] = by_id[rid].get("created_at", new["created_at"])
            by_id[rid].update(new)
            updated += 1
        else:
            by_id[rid] = new
            created += 1
    rows = sorted(by_id.values(), key=lambda row: (row.get("medium", ""), row.get("canonical_title", "").casefold()))
    summary = {"created": created, "updated": updated, "candidate_count": len(incoming), "finished_at": iso_now()}
    return rows, summary


def build_index(records: List[Dict[str, Any]], latest_run: Dict[str, Any]) -> Dict[str, Any]:
    by_medium: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    for record in records:
        by_medium[record.get("medium", "unknown")] = by_medium.get(record.get("medium", "unknown"), 0) + 1
        by_source[record.get("source", "unknown")] = by_source.get(record.get("source", "unknown"), 0) + 1
    return {
        "generated_at": iso_now(),
        "total_records": len(records),
        "by_medium": by_medium,
        "by_source": by_source,
        "latest_run": latest_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    batch_size = max(1, min(args.batch_size, 50))
    existing = read_jsonl(MASTER_PATH)
    incoming = collect_candidates(batch_size)
    records, summary = merge_records(existing, incoming)
    summary["total_records"] = len(records)

    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    write_jsonl(MASTER_PATH, records)
    INDEX_PATH.write_text(json.dumps(build_index(records, summary), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    append_jsonl(RUN_LOG_PATH, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
