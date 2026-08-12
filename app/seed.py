from datetime import date

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, init_db
from app.models import Event, Metric, Resolution, Source
from app.scoring import predictor

DEMO_SOURCES = [
    ("Wikipedia", "wikipedia", "https://en.wikipedia.org/wiki/2026_in_video_games", 0.8),
    ("GameSpot RSS", "rss", "https://www.gamespot.com/feeds/news/", 0.7),
    ("Eurogamer RSS", "rss", "https://www.eurogamer.net/feed", 0.6),
    ("ESRB", "ratings", "https://www.esrb.org", 0.9),
    ("Steam Store", "store", "https://store.steampowered.com", 0.8),
]

DEMO_EVENTS = [
    {
        "game": "Grand Theft Auto VI",
        "platform": "PS5 / Xbox Series / PC",
        "target": date(2026, 12, 31),
        "resolved": None,
        "signals": [
            ("Wikipedia", "official_date_confirmed", 1.0, "Wikipedia: 2026 in video games"),
            ("ESRB", "rating_board_listing", 1.0, "ESRB listing found"),
            ("GameSpot RSS", "news_mention_recent", 0.9, "IGN article (recency 0.9)"),
        ],
    },
    {
        "game": "Half-Life 3",
        "platform": "PC",
        "target": date(2026, 12, 31),
        "resolved": None,
        "signals": [
            ("Wikipedia", "silent_period", 0.8, "No credible updates for years"),
            ("Wikipedia", "delay_history", 0.9, "Valve has a long history of delays"),
        ],
    },
    {
        "game": "Elden Ring 2",
        "platform": "PS5 / Xbox Series / PC",
        "target": date(2026, 9, 30),
        "resolved": None,
        "signals": [
            ("Wikipedia", "official_date_confirmed", 0.9, "Wikipedia: 2026 in video games"),
            ("Steam Store", "preorder_open", 1.0, "Pre-orders open on Steam"),
            ("Eurogamer RSS", "dev_phase", 0.8, "News report: game in final polishing"),
        ],
    },
    {
        "game": "Star Citizen 2.0",
        "platform": "PC",
        "target": date(2026, 12, 31),
        "resolved": None,
        "signals": [
            ("Wikipedia", "delay_history", 0.95, "Decade of delays"),
            ("Eurogamer RSS", "silent_period", 0.6, "Little press coverage recently"),
            ("GameSpot RSS", "dev_phase", 0.2, "Vague statements about roadmap"),
        ],
    },
    {
        "game": "Cyberpunk 2078",
        "platform": "PS5 / Xbox Series / PC",
        "target": date(2026, 6, 30),
        "resolved": None,
        "signals": [
            ("Wikipedia", "official_date_confirmed", 0.7, "Wikipedia: 2026 in video games"),
            ("Eurogamer RSS", "dev_phase", 0.6, "Feature-complete per developer"),
            ("Wikipedia", "delay_history", 0.4, "Studio history of delays"),
        ],
    },
    {
        "game": "Tiny Forest Builder",
        "platform": "PC / Switch",
        "target": date(2025, 12, 31),
        "resolved": True,
        "signals": [
            ("Steam Store", "preorder_open", 0.9, "Pre-orders open on Steam"),
            ("Eurogamer RSS", "dev_phase", 1.0, "Gold master announced"),
            ("GameSpot RSS", "news_mention_recent", 0.7, "IGN article (recency 0.7)"),
        ],
    },
]


def _add_signal(session: Session, event_id: int, source_name: str, signal_type: str, value: float, note: str) -> None:
    source = session.query(Source).filter_by(name=source_name).first()
    metric = Metric(
        event_id=event_id,
        signal_type=signal_type,
        value=value,
        weight=settings.signal_weights.get(signal_type, 0.5),
        source_reliability=source.reliability if source else 0.5,
        note=note,
    )
    session.add(metric)


def seed_demo(force: bool = False) -> dict:
    with SessionLocal() as session:
        if force:
            for table in reversed(Base.metadata.sorted_tables):
                session.execute(table.delete())
            if inspect(session.bind).has_table("sqlite_sequence"):
                session.execute(text("DELETE FROM sqlite_sequence"))
            session.commit()
        if session.query(Event).count() > 0:
            return {"skipped": True, "events": session.query(Event).count()}

        for name, kind, url, reliability in DEMO_SOURCES:
            session.add(Source(name=name, kind=kind, url=url, reliability=reliability))
        session.commit()

        created = 0
        for item in DEMO_EVENTS:
            event = Event(
                game=item["game"],
                platform=item["platform"],
                target_date=item["target"],
            )
            session.add(event)
            session.flush()
            for source_name, signal_type, value, note in item["signals"]:
                _add_signal(session, event.id, source_name, signal_type, value, note)
            created += 1

        session.commit()

        for event in session.query(Event).all():
            predictor.recompute_latest(session, event)
            resolved = next(
                (d for d in DEMO_EVENTS if d["game"] == event.game), None
            )
            if resolved and resolved["resolved"] is not None:
                predictor.resolve_event(session, event.id, resolved["resolved"])

    return {"skipped": False, "events": created}
