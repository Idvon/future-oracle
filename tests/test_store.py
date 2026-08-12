from app.collectors.store_collector import _epic_date, _gog_date, _steam_date
from app.models import RawRecord, Source
from app.normalizers import signals


def _store_raw(payload: dict) -> RawRecord:
    source = Source(
        id=99,
        name="GOG",
        kind="store",
        url="https://www.gog.com",
        reliability=0.7,
    )
    return RawRecord(
        id=99,
        source=source,
        event_id=1,
        title="Cyberpunk 2077 — GOG listing",
        content="",
        url="",
        payload=payload,
    )


def test_epic_date_parsing():
    assert _epic_date("2026-12-10T00:00:00.000Z").isoformat() == "2026-12-10"
    assert _epic_date("") is None
    assert _epic_date(None) is None


def test_gog_date_parsing():
    assert _gog_date("2026.12.10").isoformat() == "2026-12-10"
    assert _gog_date("garbage") is None


def test_steam_date_parsing():
    assert _steam_date("10 Dec, 2026").isoformat() == "2026-12-10"
    assert _steam_date("Dec 10, 2026").isoformat() == "2026-12-10"
    assert _steam_date("TBA") is None


def test_store_ingest_future_date():
    metrics = signals.ingest(
        _store_raw({"release_date": "2026-12-10", "coming_soon": None})
    )
    types = {metric.signal_type for metric in metrics}
    assert types == {"official_date_confirmed", "preorder_open"}


def test_store_ingest_coming_soon_only():
    metrics = signals.ingest(
        _store_raw({"release_date": None, "coming_soon": True})
    )
    assert [metric.signal_type for metric in metrics] == ["preorder_open"]


def test_store_ingest_released_no_signal():
    metrics = signals.ingest(
        _store_raw({"release_date": "2020-12-10", "coming_soon": False})
    )
    assert metrics == []


def test_rss_ingest_still_works():
    source = Source(
        id=98,
        name="GameSpot RSS",
        kind="rss",
        url="https://www.gamespot.com/feeds/news/",
        reliability=0.6,
    )
    raw = RawRecord(
        id=98,
        source=source,
        event_id=1,
        title="Cyberpunk 2077 news",
        content="",
        url="",
        payload={},
    )
    metrics = signals.ingest(raw)
    assert [metric.signal_type for metric in metrics] == ["news_mention_recent"]
