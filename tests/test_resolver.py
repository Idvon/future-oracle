from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Event, RawRecord, Resolution, Source
from app.resolver import auto_resolve
from app.scoring import predictor


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with testing_session() as s:
        yield s
    engine.dispose()


def _source(session, name="Steam Store") -> Source:
    source = Source(name=name, kind="store", url="https://store.steampowered.com", reliability=0.8)
    session.add(source)
    session.flush()
    return source


def _event(session, game: str, target: date) -> Event:
    event = Event(game=game, target_date=target)
    session.add(event)
    session.flush()
    return event


def _store_raw(session, event: Event, source: Source, product_title: str, release_date: date | None) -> RawRecord:
    raw = RawRecord(
        source_id=source.id,
        event_id=event.id,
        title=f"{product_title} — Steam Store listing",
        content="",
        url="",
        payload={
            "store": source.name,
            "product_title": product_title,
            "release_date": release_date.isoformat() if release_date else None,
            "coming_soon": False,
        },
    )
    session.add(raw)
    session.flush()
    return raw


def _seed_prediction(session, event: Event) -> None:
    predictor.recompute_latest(session, event)


def test_released_by_target_resolves_true(session):
    yesterday = date.today() - timedelta(days=1)
    source = _source(session)
    event = _event(session, "Forza Horizon 6", yesterday)
    _store_raw(session, event, source, "Forza Horizon 6", yesterday - timedelta(days=1))
    _seed_prediction(session, event)

    resolved = auto_resolve(session)

    assert len(resolved) == 1
    assert resolved[0]["outcome"] is True
    session.expire_all()
    assert event.status == "resolved"
    assert event.outcome is True
    assert session.query(Resolution).filter_by(event_id=event.id).count() == 1


def test_release_after_target_resolves_false(session):
    target = date.today() - timedelta(days=10)
    source = _source(session)
    event = _event(session, "Star Citizen 2.0", target)
    _store_raw(session, event, source, "Star Citizen 2.0", date.today() + timedelta(days=30))
    _seed_prediction(session, event)

    resolved = auto_resolve(session)

    assert resolved[0]["outcome"] is False
    session.expire_all()
    assert event.outcome is False


def test_fuzzy_false_positive_is_ignored(session):
    target = date.today() - timedelta(days=30)
    source = _source(session)
    event = _event(session, "Sonic the Hedgehog", target)
    _store_raw(session, event, source, "The Murder of Sonic the Hedgehog", date(2023, 3, 31))
    _seed_prediction(session, event)

    assert auto_resolve(session) == []
    session.expire_all()
    assert event.status == "active"


def test_future_target_not_touched(session):
    source = _source(session)
    event = _event(session, "Elden Ring 2", date.today() + timedelta(days=90))
    _store_raw(session, event, source, "Elden Ring 2", date.today() + timedelta(days=30))
    _seed_prediction(session, event)

    assert auto_resolve(session) == []
    session.expire_all()
    assert event.status == "active"


def test_no_store_listing_not_resolved(session):
    event = _event(session, "Witch on the Holy Night", date.today() - timedelta(days=5))
    _seed_prediction(session, event)

    assert auto_resolve(session) == []
    session.expire_all()
    assert event.status == "active"
