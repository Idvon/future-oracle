from pydantic import BaseModel, ConfigDict


class ResolveIn(BaseModel):
    outcome: bool


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    probability: float
    confidence: float
    risk: float
    arguments: list[str]
    breakdown: dict
    risk_reasons: list[str]
    created_at: object


class EventSummary(BaseModel):
    id: int
    game: str
    platform: str | None
    target_date: object
    status: str
    outcome: bool | None
    probability: float | None
    confidence: float | None
    risk: float | None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: str
    url: str
    reliability: float


class AccuracyRow(BaseModel):
    event_id: int
    game: str
    target_date: object
    probability: float
    actual_outcome: bool
    brier_score: float
    resolved_at: object
