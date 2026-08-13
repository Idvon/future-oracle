from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import EventSummary, ResolveIn
from app.scoring import predictor
from app.storage import repository

router = APIRouter(prefix="/events", tags=["events"])


def _summarize(event, prediction) -> EventSummary:
    return EventSummary(
        id=event.id,
        game=event.game,
        platform=event.platform,
        target_date=event.target_date,
        status=event.status,
        outcome=event.outcome,
        probability=prediction.probability if prediction else None,
        confidence=prediction.confidence if prediction else None,
        risk=prediction.risk if prediction else None,
    )


@router.get("", response_model=list[EventSummary])
def list_events(q: str | None = None, db: Session = Depends(get_db)):
    query = (q or "").strip()
    if query:
        events = repository.search_events(db, query)
    else:
        events = repository.list_events(db, status="active")
    return [_summarize(e, repository.latest_prediction(db, e.id)) for e in events]


@router.get("/{event_id}", response_model=dict)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = repository.get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    prediction = repository.latest_prediction(db, event_id)
    summary = _summarize(event, prediction)
    if prediction:
        summary = summary.model_dump() | {
            "arguments": prediction.arguments,
            "breakdown": prediction.breakdown,
            "risk_reasons": prediction.risk_reasons,
            "predicted_at": prediction.created_at,
        }
    return summary


@router.post("/{event_id}/predict")
def predict(event_id: int, db: Session = Depends(get_db)):
    event = repository.get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    prediction = predictor.recompute_latest(db, event)
    return {
        "id": prediction.id,
        "event_id": prediction.event_id,
        "probability": prediction.probability,
        "confidence": prediction.confidence,
        "risk": prediction.risk,
        "created_at": prediction.created_at,
    }


@router.post("/{event_id}/resolve")
def resolve(event_id: int, body: ResolveIn, db: Session = Depends(get_db)):
    resolution = predictor.resolve_event(db, event_id, body.outcome)
    if resolution is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return {
        "event_id": resolution.event_id,
        "actual_outcome": resolution.actual_outcome,
        "probability": resolution.probability,
        "brier_score": resolution.brier_score,
    }
