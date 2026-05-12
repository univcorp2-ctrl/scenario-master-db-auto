from src.collector import infer_scenario_elements, normalise_title, parse_year, stable_hash


def test_normalise_title():
    assert normalise_title("  The   Example   Work  ") == "The Example Work"


def test_parse_year():
    assert parse_year("1999-07-16T00:00:00Z") == 1999


def test_hash_is_stable():
    assert stable_hash("example") == stable_hash("example")


def test_infer_scenario_elements():
    record = {
        "canonical_title": "Example Mystery School Story",
        "genres": ["Mystery", "Drama", "School"],
        "public_description": "A school mystery drama",
        "popularity": {"wikidata_sitelinks": 100},
    }
    result = infer_scenario_elements(record)
    assert "mystery/revelation" in result["conflict_axis"]
    assert "school/youth" in result["setting_tags"]
    assert "high-recognition work" in result["hook_tags"]
