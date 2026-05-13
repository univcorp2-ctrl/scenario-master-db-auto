from src.healthcheck import parse_dt, render_latest_output


def test_parse_dt_accepts_iso_z():
    assert parse_dt("2026-05-12T19:25:38Z") is not None


def test_render_latest_output_without_work():
    health = {
        "status": "ok",
        "checked_at": "2026-01-01T00:00:00+00:00",
        "master_records": 1,
        "generated_works": 0,
    }
    text = render_latest_output(None, health)
    assert "Latest automated output" in text
    assert "No generated work" in text
