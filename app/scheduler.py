from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.models import Event
from app.resolver import auto_resolve
from app.scoring import predictor

_scheduler: BackgroundScheduler | None = None


def _collect_job() -> None:
    with SessionLocal() as session:
        for event in session.query(Event).filter(Event.status == "active").all():
            predictor.recompute_latest(session, event)
        auto_resolve(session)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _collect_job, "interval", minutes=settings.collect_interval_minutes
    )
    _scheduler.start()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
