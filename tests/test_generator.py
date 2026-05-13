from src.generator import build_work, is_safe_source_record, stable_hash


def test_rejects_adult_genre_record():
    assert not is_safe_source_record({"canonical_title": "Example", "genres": ["Hentai"]})


def test_build_work_creates_original_concept_without_source_title():
    source = {
        "record_id": "test:1",
        "canonical_title": "Famous Existing Work",
        "medium": "manga",
        "genres": ["Mystery", "Drama", "Fantasy"],
        "popularity": {"wikidata_sitelinks": 100},
        "scenario_elements": {
            "conflict_axis": ["mystery/revelation"],
            "emotional_engine": ["curiosity"],
            "setting_tags": ["school/youth"],
            "theme_tags": ["truth and justice"],
            "hook_tags": ["high concept"],
        },
    }
    work = build_work([source], set())
    combined_text = " ".join(str(value) for value in work.values())
    assert "Famous Existing Work" not in combined_text
    assert work["title_ja"]
    assert work["logline_ja"]
    assert work["source_pattern_ids"] == ["test:1"]


def test_stable_hash_is_deterministic():
    assert stable_hash("abc") == stable_hash("abc")
