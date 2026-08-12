from sqlalchemy.orm import Session

from app.models import Event, Prediction, RawRecord, Resolution, Source


def list_events(session: Session, status: str | None = None) -> list[Event]:
    query = session.query(Event)
    if status:
        query = query.filter(Event.status == status)
    return query.order_by(Event.target_date).all()


def get_event(session: Session, event_id: int) -> Event | None:
    return session.get(Event, event_id)


def latest_prediction(session: Session, event_id: int) -> Prediction | None:
    return (
        session.query(Prediction)
        .filter(Prediction.event_id == event_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )


def list_predictions(session: Session, event_id: int | None = None) -> list[Prediction]:
    query = session.query(Prediction)
    if event_id is not None:
        query = query.filter(Prediction.event_id == event_id)
    return query.order_by(Prediction.created_at.desc()).all()


def list_sources(session: Session) -> list[Source]:
    return session.query(Source).order_by(Source.name).all()


def list_raw_records(session: Session, event_id: int) -> list[RawRecord]:
    return (
        session.query(RawRecord)
        .filter(RawRecord.event_id == event_id)
        .order_by(RawRecord.collected_at.desc())
        .all()
    )


def list_resolutions(session: Session) -> list[Resolution]:
    return (
        session.query(Resolution)
        .order_by(Resolution.resolved_at.desc())
        .all()
    )
