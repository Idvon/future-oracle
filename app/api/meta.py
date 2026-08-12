from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AccuracyRow, SourceOut
from app.storage import repository

router = APIRouter(tags=["meta"])


@router.get("/sources", response_model=list[SourceOut])
def sources(db: Session = Depends(get_db)):
    return repository.list_sources(db)


@router.get("/accuracy", response_model=list[AccuracyRow])
def accuracy(db: Session = Depends(get_db)):
    rows = []
    for resolution in repository.list_resolutions(db):
        rows.append(
            AccuracyRow(
                event_id=resolution.event_id,
                game=resolution.event.game,
                target_date=resolution.event.target_date,
                probability=resolution.probability,
                actual_outcome=resolution.actual_outcome,
                brier_score=resolution.brier_score,
                resolved_at=resolution.resolved_at,
            )
        )
    return rows


@router.get("/health")
def health():
    return {"status": "ok"}
