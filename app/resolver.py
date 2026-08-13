import re
from datetime import date

from sqlalchemy.orm import Session

from app.models import Event
from app.scoring import predictor


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _store_release_dates(event: Event) -> list[date]:
    dates: list[date] = []
    for raw in event.raw_records:
        if raw.source is None or raw.source.kind != "store":
            continue
        payload = raw.payload or {}
        product_title = payload.get("product_title")
        if not product_title or _norm(product_title) != _norm(event.game):
            continue
        raw_date = payload.get("release_date")
        if not raw_date:
            continue
        try:
            dates.append(date.fromisoformat(str(raw_date)[:10]))
        except ValueError:
            continue
    return dates


def auto_resolve(session: Session) -> list[dict]:
    """Разрешает активные события с прошедшей целевой датой по магазинным листингам.

    Берётся только листинг с точным совпадением названия игры (защита от ложных
    фаззи-совпадений). Если магазинная дата релиза раньше/равна целевой — исход True,
    если позже — False. Без подтверждающего листинга событие остаётся активным.
    """
    today = date.today()
    results: list[dict] = []
    events = (
        session.query(Event)
        .filter(Event.status == "active", Event.target_date < today)
        .all()
    )
    for event in events:
        dates = _store_release_dates(event)
        if not dates:
            continue
        release = min(dates)
        outcome = release <= event.target_date
        predictor.resolve_event(session, event.id, outcome)
        results.append(
            {
                "event_id": event.id,
                "game": event.game,
                "target_date": event.target_date.isoformat(),
                "release_date": release.isoformat(),
                "outcome": outcome,
            }
        )
    return results
