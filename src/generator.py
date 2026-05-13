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

ADULT_OR_UNSAFE_GENRES = {
    "adult cast",
    "boys love",
    "ecchi",
    "erotica",
    "hentai",
    "girls love",
    "gore",
}

JP_GENRE = {
    "action": "アクション",
    "adventure": "冒険",
    "comedy": "コメディ",
    "crime": "犯罪劇",
    "drama": "ドラマ",
    "fantasy": "ファンタジー",
    "horror": "ホラー",
    "mystery": "ミステリー",
    "psychological": "心理劇",
    "romance": "ロマンス",
    "sci-fi": "SF",
    "science fiction": "SF",
    "slice of life": "日常劇",
    "sports": "スポーツ",
    "supernatural": "超常現象",
    "suspense": "サスペンス",
    "thriller": "スリラー",
}

TITLE_NOUNS = [
    "観測者", "巡礼者", "修復士", "翻訳者", "記録係", "逃亡者", "交渉人", "調律師", "案内人", "継承者",
    "灯台", "地図", "迷宮", "境界線", "約束", "方舟", "時計塔", "合唱", "夜明け", "残響",
]

TITLE_ADJECTIVES = [
    "最後の", "透明な", "眠らない", "二度目の", "忘れられた", "逆さまの", "沈黙する", "名前のない", "春を待つ", "月下の",
]

WORLD_FRAGMENTS = [
    "感情が公共インフラとして数値化される都市",
    "夢の記録が裁判証拠になる近未来",
    "失われた物語だけが通貨として流通する群島",
    "毎朝、住民の役割が抽選で入れ替わる学園都市",
    "過去の選択を一度だけ郵送できる地方都市",
    "怪異と行政手続きが共存する辺境の町",
    "記憶を修理する職人ギルドがある王国",
    "宇宙移民船の中に再現された古い商店街",
]

PROTAGONIST_FRAGMENTS = [
    "嘘を見抜けるが自分の本心だけ読めない新人調査官",
    "誰からも忘れられる体質を利用して事件を解く学生",
    "敗者の記憶を預かることになった元アスリート",
    "禁じられた物語を修復する若い司書",
    "未来の自分から届く失敗報告だけを頼りに動く配達員",
    "怪異専門の窓口で働く臆病な公務員",
    "他人の願いを翻訳できるが自分の夢を失った音楽家",
    "家族を守るため、感情取引市場に潜入する会計士",
]

ANTAGONIST_PRESSURES = [
    "秩序を守る名目で個人の記憶を標準化する組織",
    "成功者だけを英雄化し、失敗の記録を消す社会制度",
    "人々の恐怖を燃料に成長する都市そのもの",
    "主人公の選択を先回りして封じる予測アルゴリズム",
    "善意で世界を単純化しようとする改革者",
    "過去の約束を債務として取り立てる契約機関",
    "真実よりも心地よい物語を求める群衆心理",
]

MOTIFS = [
    "壊れた時計", "白紙の地図", "返送されない手紙", "録音された雨音", "消えないチケット",
    "片方だけの手袋", "未完成の楽譜", "錆びた鍵", "匿名のレシート", "夜だけ光る標識",
]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat()


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


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def clean_token(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def is_safe_source_record(record: Dict[str, Any]) -> bool:
    genres = {clean_token(g) for g in record.get("genres", [])}
    if genres & ADULT_OR_UNSAFE_GENRES:
        return False
    title = clean_token(record.get("canonical_title", ""))
    blocked_words = ["hentai", "erotica", "porn"]
    return not any(word in title for word in blocked_words)


def popularity_score(record: Dict[str, Any]) -> float:
    pop = record.get("popularity") or {}
    score = 1.0
    score += float(pop.get("wikidata_sitelinks") or 0) / 50.0
    score += float(pop.get("mal_members") or 0) / 100_000.0
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
        weights = [popularity_score(r) for r in pool]
        selected = random.choices(pool, weights=weights, k=1)[0]
        chosen.append(selected)
        pool.remove(selected)
    return chosen


def collect_tags(records: Sequence[Dict[str, Any]], key: str) -> List[str]:
    out: List[str] = []
    for record in records:
        elements = record.get("scenario_elements") or {}
        for tag in elements.get(key, []) or []:
            if tag:
                out.append(str(tag))
    return out


def top_or_default(values: Sequence[str], default: Sequence[str], limit: int = 3) -> List[str]:
    clean = [v for v in values if v and "unspecified" not in v and "manually" not in v]
    if not clean:
        return list(default)[:limit]
    counter = Counter(clean)
    return [item for item, _ in counter.most_common(limit)]


def jp_genre_name(genre: str) -> str:
    key = clean_token(genre)
    return JP_GENRE.get(key, genre)


def make_title(theme_tags: Sequence[str], setting_tags: Sequence[str]) -> str:
    adjective = random.choice(TITLE_ADJECTIVES)
    noun = random.choice(TITLE_NOUNS)
    if any("truth" in clean_token(t) or "justice" in clean_token(t) for t in theme_tags):
        return f"{adjective}証言者たち"
    if any("coming" in clean_token(t) or "school" in clean_token(t) for t in theme_tags + tuple(setting_tags)):
        return f"{adjective}放課後の{noun}"
    if any("family" in clean_token(t) for t in theme_tags):
        return f"{noun}家族の{adjective}約束"
    if any("survival" in clean_token(t) for t in theme_tags):
        return f"{adjective}{noun}サバイバル"
    return f"{adjective}{noun}"


def build_medium_suggestion(records: Sequence[Dict[str, Any]]) -> str:
    media = [record.get("medium") for record in records if record.get("medium")]
    if not media:
        return random.choice(["novel", "manga", "film"])
    most_common = Counter(media).most_common(1)[0][0]
    # Shift the medium sometimes so the generator creates fresh transmedia ideas.
    if random.random() < 0.35:
        return random.choice(["novel", "manga", "film", "series"])
    return str(most_common)


def build_work(anchor_records: Sequence[Dict[str, Any]], existing_fingerprints: set[str]) -> Dict[str, Any]:
    genres = []
    for record in anchor_records:
        genres.extend(str(g) for g in record.get("genres", []) if g)
    genre_mix = top_or_default(genres, ["Drama", "Mystery", "Fantasy"], 4)
    conflict_axis = top_or_default(collect_tags(anchor_records, "conflict_axis"), ["goal vs obstacle", "mystery/revelation"], 2)
    emotion = top_or_default(collect_tags(anchor_records, "emotional_engine"), ["curiosity", "empathy"], 2)
    setting_tags = top_or_default(collect_tags(anchor_records, "setting_tags"), ["speculative everyday life", "border town"], 2)
    theme_tags = top_or_default(collect_tags(anchor_records, "theme_tags"), ["identity", "trust and betrayal"], 3)
    hook_tags = top_or_default(collect_tags(anchor_records, "hook_tags"), ["clear dilemma", "high concept"], 3)

    title = make_title(theme_tags, setting_tags)
    medium = build_medium_suggestion(anchor_records)
    world = random.choice(WORLD_FRAGMENTS)
    protagonist = random.choice(PROTAGONIST_FRAGMENTS)
    pressure = random.choice(ANTAGONIST_PRESSURES)
    motif_set = random.sample(MOTIFS, k=3)

    genre_jp = "×".join(jp_genre_name(g) for g in genre_mix[:3])
    main_conflict = conflict_axis[0]
    main_emotion = emotion[0]
    main_theme = theme_tags[0]

    logline = (
        f"{world}で、{protagonist}が、{pressure}に抗いながら、"
        f"失われた選択の意味を取り戻す{genre_jp}。"
    )

    fingerprint_source = "|".join([
        title,
        medium,
        world,
        protagonist,
        pressure,
        ",".join(genre_mix),
        ",".join(conflict_axis),
        ",".join(theme_tags),
    ])
    fingerprint = stable_hash(fingerprint_source, 20)
    if fingerprint in existing_fingerprints:
        title = f"{title} #{stable_hash(iso_now() + fingerprint, 4)}"
        fingerprint = stable_hash(fingerprint_source + title + iso_now(), 20)

    now = iso_now()
    source_ids = [str(r.get("record_id")) for r in anchor_records if r.get("record_id")]
    return {
        "work_id": f"orig:{utc_now().strftime('%Y%m%d%H%M%S')}:{fingerprint}",
        "generated_at": now,
        "generator": "algorithmic_tag_synthesis_v1",
        "status": "concept",
        "title_ja": title,
        "medium_suggestion": medium,
        "target_audience": random.choice(["YA以上", "一般向け", "青年・一般向け", "ファミリー向けではなく一般向け"]),
        "genre_mix": genre_mix,
        "logline_ja": logline,
        "core_conflict": {
            "axis": conflict_axis,
            "description_ja": f"主人公の個人的な願いと、{pressure}が生む社会的圧力が衝突する。",
        },
        "emotional_engine": {
            "tags": emotion,
            "description_ja": f"読者・観客を動かす主感情は「{main_emotion}」。毎話または各章で小さな謎、選択、代償を提示する。",
        },
        "world_setting_ja": world,
        "protagonist_ja": protagonist,
        "antagonistic_pressure_ja": pressure,
        "supporting_cast_ja": [
            "主人公の弱点を見抜くが、目的を隠して協力する相棒",
            "制度側にいながら主人公の違和感に気づく監査役",
            "一見無関係な小さな依頼を持ち込む年少のキーパーソン",
        ],
        "act_structure_ja": {
            "act_1": f"{world}の日常と欠陥を見せ、主人公が取り返しのつかない依頼を受ける。",
            "act_2": f"{main_conflict}が段階的に拡大し、味方の秘密と社会制度の矛盾が同時に明らかになる。",
            "act_3": f"主人公は勝利条件を変える決断をし、{main_theme}を個人ではなく共同体の選択として提示する。",
        },
        "recurring_motifs_ja": motif_set,
        "sequel_hooks_ja": [
            "解決した事件の背後に、同じ構造を持つ別地域の異変が残る。",
            "味方だと思われた人物が、次作では別の正義を掲げて対立する。",
        ],
        "hook_tags": hook_tags,
        "theme_tags": theme_tags,
        "source_pattern_ids": source_ids,
        "originality_guardrails": [
            "既存作品の本文、台詞、固有キャラクター、固有世界観を使用しない。",
            "参照元は抽象タグと人気指標のみ。",
            "商用利用前に人間が類似性チェックと権利確認を行う。",
        ],
        "fingerprint": fingerprint,
    }


def fallback_records() -> List[Dict[str, Any]]:
    return [
        {
            "record_id": "fallback:drama-mystery",
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


def render_markdown(works: Sequence[Dict[str, Any]]) -> str:
    lines = [f"# Original work concepts - {utc_now().date().isoformat()}", ""]
    for work in works:
        lines.extend([
            f"## {work['title_ja']}",
            "",
            f"- ID: `{work['work_id']}`",
            f"- Medium: `{work['medium_suggestion']}`",
            f"- Genre: {', '.join(work['genre_mix'])}",
            f"- Logline: {work['logline_ja']}",
            f"- Core conflict: {work['core_conflict']['description_ja']}",
            f"- World: {work['world_setting_ja']}",
            f"- Protagonist: {work['protagonist_ja']}",
            f"- Antagonistic pressure: {work['antagonistic_pressure_ja']}",
            f"- Motifs: {', '.join(work['recurring_motifs_ja'])}",
            f"- Source pattern IDs: {', '.join(work['source_pattern_ids'])}",
            "",
            "### Three-act structure",
            "",
            f"1. {work['act_structure_ja']['act_1']}",
            f"2. {work['act_structure_ja']['act_2']}",
            f"3. {work['act_structure_ja']['act_3']}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def write_daily_markdown(works: Sequence[Dict[str, Any]]) -> None:
    if not works:
        return
    path = GENERATED_DIR / f"{utc_now().date().isoformat()}.md"
    content = render_markdown(works)
    if path.exists():
        previous = path.read_text(encoding="utf-8").rstrip() + "\n\n"
        path.write_text(previous + content, encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")


def write_index(all_works: Sequence[Dict[str, Any]]) -> None:
    by_medium = Counter(work.get("medium_suggestion", "unknown") for work in all_works)
    by_status = Counter(work.get("status", "unknown") for work in all_works)
    latest = sorted(all_works, key=lambda w: w.get("generated_at", ""), reverse=True)[:20]
    index = {
        "generated_at": iso_now(),
        "total_generated_works": len(all_works),
        "by_medium": dict(sorted(by_medium.items())),
        "by_status": dict(sorted(by_status.items())),
        "latest": [
            {
                "work_id": work.get("work_id"),
                "title_ja": work.get("title_ja"),
                "medium_suggestion": work.get("medium_suggestion"),
                "generated_at": work.get("generated_at"),
            }
            for work in latest
        ],
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate(count: int) -> List[Dict[str, Any]]:
    seed = int(utc_now().strftime("%Y%m%d%H%M")) + int(os.getenv("GITHUB_RUN_NUMBER", "0") or "0")
    random.seed(seed)

    source_records = [record for record in read_jsonl(MASTER_PATH) if is_safe_source_record(record)]
    if not source_records:
        source_records = fallback_records()

    existing_works = read_jsonl(WORKS_PATH)
    existing_fingerprints = {str(work.get("fingerprint")) for work in existing_works if work.get("fingerprint")}
    new_works: List[Dict[str, Any]] = []

    attempts = 0
    while len(new_works) < count and attempts < count * 8:
        attempts += 1
        anchors = weighted_sample(source_records, random.randint(3, min(7, max(3, len(source_records)))))
        work = build_work(anchors, existing_fingerprints)
        if work["fingerprint"] in existing_fingerprints:
            continue
        existing_fingerprints.add(work["fingerprint"])
        new_works.append(work)

    append_jsonl(WORKS_PATH, new_works)
    write_daily_markdown(new_works)
    write_index(existing_works + new_works)
    return new_works


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate original work concepts from scenario master database.")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    count = max(1, min(args.count, 20))
    if args.dry_run:
        source_records = [record for record in read_jsonl(MASTER_PATH) if is_safe_source_record(record)] or fallback_records()
        works = [build_work(weighted_sample(source_records, min(5, len(source_records))), set()) for _ in range(count)]
        print(json.dumps(works, ensure_ascii=False, indent=2))
        return 0

    works = generate(count)
    print(json.dumps({"generated": len(works), "path": str(WORKS_PATH)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
