from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GENERATED_DIR = ROOT / "generated"
MASTER_PATH = DATA_DIR / "master_scenario_elements.jsonl"
WORKS_PATH = GENERATED_DIR / "original_works.jsonl"
INDEX_PATH = GENERATED_DIR / "index.json"

UNSAFE_GENRES = {"adult cast", "boys love", "ecchi", "erotica", "hentai", "girls love"}

TITLE_PREFIXES = ["透明な", "最後の", "眠らない", "二度目の", "忘れられた", "逆さまの", "月下の", "名前のない"]
TITLE_NOUNS = ["観測者", "修復士", "記録係", "逃亡者", "交渉人", "調律師", "灯台", "地図", "迷宮", "時計塔", "残響"]
WORLDS = [
    "感情が公共インフラとして数値化される都市",
    "夢の記録が裁判証拠になる近未来",
    "失われた物語だけが通貨として流通する群島",
    "毎朝、住民の役割が抽選で入れ替わる学園都市",
    "過去の選択を一度だけ郵送できる地方都市",
    "怪異と行政手続きが共存する辺境の町",
    "記憶を修理する職人ギルドがある王国",
    "宇宙移民船の中に再現された古い商店街",
]
PROTAGONISTS = [
    "嘘を見抜けるが自分の本心だけ読めない新人調査官",
    "誰からも忘れられる体質を利用して事件を解く学生",
    "敗者の記憶を預かることになった元アスリート",
    "禁じられた物語を修復する若い司書",
    "未来の自分から届く失敗報告だけを頼りに動く配達員",
    "怪異専門の窓口で働く臆病な公務員",
    "他人の願いを翻訳できるが自分の夢を失った音楽家",
]
PRESSURES = [
    "秩序を守る名目で個人の記憶を標準化する組織",
    "成功者だけを英雄化し、失敗の記録を消す社会制度",
    "人々の恐怖を燃料に成長する都市そのもの",
    "主人公の選択を先回りして封じる予測アルゴリズム",
    "善意で世界を単純化しようとする改革者",
    "過去の約束を債務として取り立てる契約機関",
]
MOTIFS = ["壊れた時計", "白紙の地図", "返送されない手紙", "録音された雨音", "消えないチケット", "未完成の楽譜", "錆びた鍵"]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def is_safe_source_record(record: Dict[str, Any]) -> bool:
    title = clean(record.get("canonical_title"))
    genres = {clean(g) for g in record.get("genres", [])}
    if any(word in title for word in ["hentai", "erotica", "porn"]):
        return False
    return not bool(genres & UNSAFE_GENRES)


def popularity_score(record: Dict[str, Any]) -> float:
    pop = record.get("popularity") or {}
    score = 1.0
    score += float(pop.get("wikidata_sitelinks") or 0) / 40.0
    score += float(pop.get("mal_members") or 0) / 100000.0
    rank = pop.get("mal_rank")
    if isinstance(rank, (int, float)) and rank > 0:
        score += max(0.0, 1000.0 - float(rank)) / 100.0
    return max(score, 1.0)


def weighted_sample(records: Sequence[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    if not records:
        return []
    pool = list(records)
    chosen: List[Dict[str, Any]] = []
    for _ in range(min(count, len(pool))):
        weights = [popularity_score(row) for row in pool]
        item = random.choices(pool, weights=weights, k=1)[0]
        chosen.append(item)
        pool.remove(item)
    return chosen


def collect_list(records: Sequence[Dict[str, Any]], element_key: str) -> List[str]:
    values: List[str] = []
    for record in records:
        elements = record.get("scenario_elements") or {}
        values.extend(str(v) for v in elements.get(element_key, []) if v)
    return values


def top_values(values: Sequence[str], fallback: Sequence[str], limit: int) -> List[str]:
    filtered = [v for v in values if v and "unspecified" not in clean(v) and "manual" not in clean(v)]
    if not filtered:
        return list(fallback)[:limit]
    return [value for value, _ in Counter(filtered).most_common(limit)]


def make_title(theme_tags: Sequence[str], setting_tags: Sequence[str]) -> str:
    combined = " ".join([*theme_tags, *setting_tags]).lower()
    if "truth" in combined or "justice" in combined:
        return f"{random.choice(TITLE_PREFIXES)}証言者たち"
    if "coming" in combined or "school" in combined:
        return f"{random.choice(TITLE_PREFIXES)}放課後の{random.choice(TITLE_NOUNS)}"
    if "family" in combined:
        return f"{random.choice(TITLE_NOUNS)}家族の約束"
    return f"{random.choice(TITLE_PREFIXES)}{random.choice(TITLE_NOUNS)}"


def fallback_records() -> List[Dict[str, Any]]:
    return [
        {
            "record_id": "fallback:1",
            "medium": "novel",
            "genres": ["Drama", "Mystery", "Fantasy"],
            "popularity": {"fallback": True},
            "scenario_elements": {
                "conflict_axis": ["mystery/revelation", "goal vs obstacle"],
                "emotional_engine": ["curiosity", "empathy"],
                "setting_tags": ["speculative everyday life"],
                "theme_tags": ["identity", "truth and justice"],
                "hook_tags": ["high concept"],
            },
        }
    ]


def build_work(anchor_records: Sequence[Dict[str, Any]], existing_fingerprints: set[str]) -> Dict[str, Any]:
    genres: List[str] = []
    for record in anchor_records:
        genres.extend(str(g) for g in record.get("genres", []) if g)
    genre_mix = top_values(genres, ["Drama", "Mystery", "Fantasy"], 4)
    conflict_axis = top_values(collect_list(anchor_records, "conflict_axis"), ["goal vs obstacle"], 2)
    emotions = top_values(collect_list(anchor_records, "emotional_engine"), ["curiosity", "empathy"], 2)
    settings = top_values(collect_list(anchor_records, "setting_tags"), ["speculative everyday life"], 2)
    themes = top_values(collect_list(anchor_records, "theme_tags"), ["identity", "trust and betrayal"], 3)
    hooks = top_values(collect_list(anchor_records, "hook_tags"), ["high concept", "clear dilemma"], 3)

    title = make_title(themes, settings)
    medium = Counter(str(r.get("medium", "novel")) for r in anchor_records).most_common(1)[0][0]
    if random.random() < 0.25:
        medium = random.choice(["novel", "manga", "film", "series"])
    world = random.choice(WORLDS)
    protagonist = random.choice(PROTAGONISTS)
    pressure = random.choice(PRESSURES)
    motifs = random.sample(MOTIFS, k=3)
    now = iso_now()

    seed_text = "|".join([title, medium, world, protagonist, pressure, ",".join(genre_mix), ",".join(themes)])
    fingerprint = stable_hash(seed_text, 20)
    if fingerprint in existing_fingerprints:
        title = f"{title}-{stable_hash(now, 4)}"
        fingerprint = stable_hash(seed_text + title + now, 20)

    source_ids = [str(record.get("record_id")) for record in anchor_records if record.get("record_id")]
    logline = f"{world}で、{protagonist}が、{pressure}に抗いながら、失われた選択の意味を取り戻す物語。"
    return {
        "work_id": f"orig:{utc_now().strftime('%Y%m%d%H%M%S')}:{fingerprint}",
        "generated_at": now,
        "generator": "algorithmic_tag_synthesis_v2",
        "status": "concept",
        "title_ja": title,
        "medium_suggestion": medium,
        "target_audience": random.choice(["YA以上", "一般向け", "青年・一般向け"]),
        "genre_mix": genre_mix,
        "logline_ja": logline,
        "core_conflict": {"axis": conflict_axis, "description_ja": f"主人公の願いと、{pressure}が作る社会的圧力が衝突する。"},
        "emotional_engine": {"tags": emotions, "description_ja": f"主感情は「{emotions[0]}」。章ごとに謎、選択、代償を提示する。"},
        "world_setting_ja": world,
        "protagonist_ja": protagonist,
        "antagonistic_pressure_ja": pressure,
        "supporting_cast_ja": ["目的を隠して協力する相棒", "制度側にいる監査役", "小さな依頼を持ち込むキーパーソン"],
        "act_structure_ja": {
            "act_1": f"{world}の日常と欠陥を見せ、主人公が取り返しのつかない依頼を受ける。",
            "act_2": f"{conflict_axis[0]}が拡大し、味方の秘密と社会制度の矛盾が明らかになる。",
            "act_3": f"主人公は勝利条件を変える決断をし、{themes[0]}を共同体の選択として提示する。",
        },
        "recurring_motifs_ja": motifs,
        "sequel_hooks_ja": ["別地域で同じ構造の異変が残る。", "味方が次作では別の正義を掲げて対立する。"],
        "hook_tags": hooks,
        "theme_tags": themes,
        "source_pattern_ids": source_ids,
        "originality_guardrails": ["既存作品の本文、台詞、固有キャラクター、固有世界観を使用しない。", "参照元は抽象タグと人気指標のみ。"],
        "fingerprint": fingerprint,
    }


def render_markdown(works: Sequence[Dict[str, Any]]) -> str:
    lines = [f"# Original work concepts - {utc_now().date().isoformat()}", ""]
    for work in works:
        lines += [
            f"## {work['title_ja']}",
            "",
            f"- ID: `{work['work_id']}`",
            f"- Medium: `{work['medium_suggestion']}`",
            f"- Genre: {', '.join(work['genre_mix'])}",
            f"- Logline: {work['logline_ja']}",
            f"- World: {work['world_setting_ja']}",
            f"- Protagonist: {work['protagonist_ja']}",
            f"- Antagonistic pressure: {work['antagonistic_pressure_ja']}",
            "",
            "### Three-act structure",
            f"1. {work['act_structure_ja']['act_1']}",
            f"2. {work['act_structure_ja']['act_2']}",
            f"3. {work['act_structure_ja']['act_3']}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def write_index(all_works: Sequence[Dict[str, Any]]) -> None:
    by_medium = Counter(work.get("medium_suggestion", "unknown") for work in all_works)
    latest = sorted(all_works, key=lambda w: w.get("generated_at", ""), reverse=True)[:20]
    index = {
        "generated_at": iso_now(),
        "total_generated_works": len(all_works),
        "by_medium": dict(sorted(by_medium.items())),
        "latest": [{"work_id": w.get("work_id"), "title_ja": w.get("title_ja"), "generated_at": w.get("generated_at")} for w in latest],
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate(count: int) -> List[Dict[str, Any]]:
    seed = int(utc_now().strftime("%Y%m%d%H%M")) + int(os.getenv("GITHUB_RUN_NUMBER", "0") or "0")
    random.seed(seed)
    source_records = [row for row in read_jsonl(MASTER_PATH) if is_safe_source_record(row)] or fallback_records()
    existing = read_jsonl(WORKS_PATH)
    fingerprints = {str(w.get("fingerprint")) for w in existing if w.get("fingerprint")}
    new_works: List[Dict[str, Any]] = []
    for _ in range(count):
        anchors = weighted_sample(source_records, random.randint(1, min(5, len(source_records))))
        work = build_work(anchors or fallback_records(), fingerprints)
        fingerprints.add(work["fingerprint"])
        new_works.append(work)
    append_jsonl(WORKS_PATH, new_works)
    day_path = GENERATED_DIR / f"{utc_now().date().isoformat()}.md"
    old = day_path.read_text(encoding="utf-8") + "\n" if day_path.exists() else ""
    day_path.parent.mkdir(parents=True, exist_ok=True)
    day_path.write_text(old + render_markdown(new_works), encoding="utf-8")
    write_index(existing + new_works)
    return new_works


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    count = max(1, min(args.count, 20))
    if args.dry_run:
        records = [row for row in read_jsonl(MASTER_PATH) if is_safe_source_record(row)] or fallback_records()
        works = [build_work(weighted_sample(records, min(3, len(records))) or fallback_records(), set()) for _ in range(count)]
        print(json.dumps(works, ensure_ascii=False, indent=2))
        return 0
    works = generate(count)
    print(json.dumps({"generated": len(works), "path": str(WORKS_PATH)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
