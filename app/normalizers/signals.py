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


def _news_metric(raw: RawRecord) -> Metric:
    return Metric(
        event_id=raw.event_id,
        raw_record_id=raw.id,
        signal_type="news_mention_recent",
        value=_recency_value(raw.payload.get("published") if raw.payload else None),
        weight=settings.signal_weights["news_mention_recent"],
        source_reliability=raw.source.reliability,
        note=f"RSS article from {raw.source.name}: {raw.title[:80]}",
    )


def _store_metrics(raw: RawRecord) -> list[Metric]:
    payload = raw.payload or {}
    parsed = None
    if payload.get("release_date"):
        try:
            parsed = date.fromisoformat(str(payload["release_date"])[:10])
        except ValueError:
            parsed = None
    coming_soon = bool(payload.get("coming_soon"))
    metrics = []
    if parsed is not None and parsed > date.today():
        metrics.append(
            Metric(
                event_id=raw.event_id,
                raw_record_id=raw.id,
                signal_type="official_date_confirmed",
                value=0.9,
                weight=settings.signal_weights["official_date_confirmed"],
                source_reliability=raw.source.reliability,
                note=f"{raw.source.name} lists release date {parsed.isoformat()} ({raw.title[:80]})",
            )
        )
        metrics.append(
            Metric(
                event_id=raw.event_id,
                raw_record_id=raw.id,
                signal_type="preorder_open",
                value=0.8,
                weight=settings.signal_weights["preorder_open"],
                source_reliability=raw.source.reliability,
                note=f"{raw.source.name} has the game listed for a future release",
            )
        )
    elif coming_soon:
        metrics.append(
            Metric(
                event_id=raw.event_id,
                raw_record_id=raw.id,
                signal_type="preorder_open",
                value=0.7,
                weight=settings.signal_weights["preorder_open"],
                source_reliability=raw.source.reliability,
                note=f"{raw.source.name} lists the game as coming soon",
            )
        )
    return metrics


def ingest(raw: RawRecord) -> list[Metric]:
    if raw.source is None or raw.event_id is None:
        return []
    if raw.source.kind == "rss":
        return [_news_metric(raw)]
    if raw.source.kind == "store":
        return _store_metrics(raw)
    return []


def ingest_all(session: Session, raw_records: list[RawRecord]) -> int:
    count = 0
    for raw in raw_records:
        for metric in ingest(raw):
            session.add(metric)
            count += 1
    if count:
        session.commit()
    return count
