from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Metric, RawRecord


def _recency_value(published: str | None) -> float:
    if published is None:
        return 0.3
    try:
        published_date = date.fromisoformat(published[:10])
    except ValueError:
        return 0.3
    days = (datetime.utcnow().date() - published_date).days
    if days <= 7:
        return 0.9
    if days <= 30:
        return 0.6
    return 0.3


def ingest(raw: RawRecord) -> Metric | None:
    if raw.source is None or raw.source.kind != "rss" or raw.event_id is None:
        return None
    return Metric(
        event_id=raw.event_id,
        raw_record_id=raw.id,
        signal_type="news_mention_recent",
        value=_recency_value(raw.payload.get("published") if raw.payload else None),
        weight=settings.signal_weights["news_mention_recent"],
        source_reliability=raw.source.reliability,
        note=f"RSS article from {raw.source.name}: {raw.title[:80]}",
    )


def ingest_all(session: Session, raw_records: list[RawRecord]) -> int:
    count = 0
    for raw in raw_records:
        metric = ingest(raw)
        if metric is not None:
            session.add(metric)
            count += 1
    if count:
        session.commit()
    return count
