from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GENERATED_DIR = ROOT / "generated"
HEALTH_DIR = ROOT / "health"
MASTER_PATH = DATA_DIR / "master_scenario_elements.jsonl"
DATA_INDEX_PATH = DATA_DIR / "index.json"
WORKS_PATH = GENERATED_DIR / "original_works.jsonl"
GEN_INDEX_PATH = GENERATED_DIR / "index.json"
LATEST_REPORT_PATH = GENERATED_DIR / "latest_output.md"
HEALTH_PATH = HEALTH_DIR / "latest_healthcheck.json"
HEALTH_MD_PATH = HEALTH_DIR / "latest_healthcheck.md"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


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


def parse_dt(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def hours_since(value: Optional[str]) -> Optional[float]:
    parsed = parse_dt(value)
    if not parsed:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return (utc_now() - parsed).total_seconds() / 3600.0


def get_latest_time(rows: List[Dict[str, Any]], key: str) -> Optional[str]:
    values = [str(row.get(key)) for row in rows if row.get(key)]
    return max(values) if values else None


def latest_generated_work(works: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not works:
        return None
    return sorted(works, key=lambda row: str(row.get("generated_at", "")), reverse=True)[0]


def render_latest_output(work: Optional[Dict[str, Any]], health: Dict[str, Any]) -> str:
    lines = ["# Latest automated output", ""]
    lines.append(f"- Health status: **{health['status']}**")
    lines.append(f"- Checked at UTC: `{health['checked_at']}`")
    lines.append(f"- Master DB records: `{health['master_records']}`")
    lines.append(f"- Generated concepts: `{health['generated_works']}`")
    lines.append("")

    if not work:
        lines.append("No generated work concept is available yet.")
        return "\n".join(lines).rstrip() + "\n"

    lines.extend([
        f"## {work.get('title_ja', 'Untitled')}",
        "",
        f"- Work ID: `{work.get('work_id', '')}`",
        f"- Generated at UTC: `{work.get('generated_at', '')}`",
        f"- Medium: `{work.get('medium_suggestion', '')}`",
        f"- Genre mix: {', '.join(work.get('genre_mix', []))}",
        f"- Logline: {work.get('logline_ja', '')}",
        f"- World: {work.get('world_setting_ja', '')}",
        f"- Protagonist: {work.get('protagonist_ja', '')}",
        f"- Antagonistic pressure: {work.get('antagonistic_pressure_ja', '')}",
        f"- Themes: {', '.join(work.get('theme_tags', []))}",
        f"- Hook tags: {', '.join(work.get('hook_tags', []))}",
        "",
        "### Three-act structure",
        "",
        f"1. {work.get('act_structure_ja', {}).get('act_1', '')}",
        f"2. {work.get('act_structure_ja', {}).get('act_2', '')}",
        f"3. {work.get('act_structure_ja', {}).get('act_3', '')}",
        "",
        "### Source pattern IDs",
        "",
        ", ".join(work.get("source_pattern_ids", [])) or "None",
    ])
    return "\n".join(lines).rstrip() + "\n"


def render_health_md(health: Dict[str, Any]) -> str:
    checks = health.get("checks", [])
    lines = ["# Latest healthcheck", ""]
    lines.append(f"- Status: **{health['status']}**")
    lines.append(f"- Checked at UTC: `{health['checked_at']}`")
    lines.append(f"- Master records: `{health['master_records']}`")
    lines.append(f"- Generated works: `{health['generated_works']}`")
    lines.append(f"- Latest DB update age hours: `{health.get('latest_db_update_age_hours')}`")
    lines.append(f"- Latest generation age hours: `{health.get('latest_generation_age_hours')}`")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    for check in checks:
        mark = "✅" if check.get("ok") else "❌"
        lines.append(f"- {mark} `{check.get('name')}`: {check.get('message')}")
    lines.append("")
    return "\n".join(lines)


def run_healthcheck(max_age_hours: float) -> Dict[str, Any]:
    master_rows = read_jsonl(MASTER_PATH)
    works = read_jsonl(WORKS_PATH)
    data_index = read_json(DATA_INDEX_PATH)
    gen_index = read_json(GEN_INDEX_PATH)

    latest_db_update = get_latest_time(master_rows, "updated_at") or data_index.get("generated_at")
    latest_generation = get_latest_time(works, "generated_at") or gen_index.get("generated_at")
    db_age = hours_since(latest_db_update)
    gen_age = hours_since(latest_generation)

    by_medium = Counter(row.get("medium", "unknown") for row in master_rows)
    by_gen_medium = Counter(row.get("medium_suggestion", "unknown") for row in works)

    checks = [
        {
            "name": "master_db_exists",
            "ok": MASTER_PATH.exists() and len(master_rows) > 0,
            "message": f"{len(master_rows)} master records found.",
        },
        {
            "name": "generated_works_exist",
            "ok": WORKS_PATH.exists() and len(works) > 0,
            "message": f"{len(works)} generated concepts found.",
        },
        {
            "name": "latest_db_update_recent",
            "ok": db_age is not None and db_age <= max_age_hours,
            "message": f"latest DB update age is {db_age:.2f} hours." if db_age is not None else "No DB update timestamp found.",
        },
        {
            "name": "latest_generation_recent",
            "ok": gen_age is not None and gen_age <= max_age_hours,
            "message": f"latest generation age is {gen_age:.2f} hours." if gen_age is not None else "No generation timestamp found.",
        },
    ]

    status = "ok" if all(check["ok"] for check in checks) else "fail"
    health = {
        "status": status,
        "checked_at": iso_now(),
        "max_age_hours": max_age_hours,
        "master_records": len(master_rows),
        "generated_works": len(works),
        "latest_db_update": latest_db_update,
        "latest_generation": latest_generation,
        "latest_db_update_age_hours": round(db_age, 4) if db_age is not None else None,
        "latest_generation_age_hours": round(gen_age, 4) if gen_age is not None else None,
        "master_by_medium": dict(sorted(by_medium.items())),
        "generated_by_medium": dict(sorted(by_gen_medium.items())),
        "checks": checks,
    }

    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    HEALTH_PATH.write_text(json.dumps(health, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    HEALTH_MD_PATH.write_text(render_health_md(health), encoding="utf-8")
    LATEST_REPORT_PATH.write_text(render_latest_output(latest_generated_work(works), health), encoding="utf-8")
    return health


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether cloud automation is running and write latest output report.")
    parser.add_argument("--max-age-hours", type=float, default=36.0)
    args = parser.parse_args()
    health = run_healthcheck(args.max_age_hours)
    print(json.dumps(health, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if health["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
