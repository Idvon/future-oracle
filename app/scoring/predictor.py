import math

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Event, Metric, Prediction, Resolution

MIN_PROB = 0.02
MAX_PROB = 0.98


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _latest_per_type(metrics: list[Metric]) -> dict[str, Metric]:
    latest: dict[str, Metric] = {}
    for m in metrics:
        current = latest.get(m.signal_type)
        if current is None or m.created_at > current.created_at:
            latest[m.signal_type] = m
    return latest


def _effective_value(signal_type: str, value: float) -> float:
    weight = settings.signal_weights.get(signal_type, 0.5)
    sign = 1.0 if weight >= 0 else -1.0
    return value * sign


def _confidence(latest: dict[str, Metric]) -> float:
    if not latest:
        return 0.05
    n = len(latest)
    coverage = 1 - math.exp(-n / 3.0)
    effective = [_effective_value(k, m.value) for k, m in latest.items()]
    spread = max(effective) - min(effective)
    agreement = clamp(1 - spread, 0.0, 1.0)
    reliability = sum(m.source_reliability for m in latest.values()) / n
    return clamp(coverage * (0.5 + 0.5 * agreement) * reliability, 0.02, 0.98)


def _risk_reasons(latest: dict[str, Metric]) -> list[str]:
    reasons: list[str] = []
    for signal_type, m in latest.items():
        weight = settings.signal_weights.get(signal_type, 0.5)
        if weight < 0 and m.value >= 0.5:
            label = settings.signal_labels.get(signal_type, signal_type)
            reasons.append(f"{label} (strength {m.value:.2f})")
    if len(latest) < 2:
        reasons.append("Too few independent signals")
    return reasons or ["Release dates are frequently delayed in the industry"]


def predict(event: Event, metrics: list[Metric]) -> Prediction:
    latest = _latest_per_type(metrics)
    weights = settings.signal_weights
    labels = settings.signal_labels

    total = 0.0
    total_abs_weight = 0.0
    breakdown: dict[str, dict] = {}
    arguments: list[str] = []

    for signal_type, m in latest.items():
        weight = weights.get(signal_type, 0.5)
        contribution = weight * m.value
        total += contribution
        total_abs_weight += abs(weight)
        label = labels.get(signal_type, signal_type)
        breakdown[signal_type] = {
            "value": round(m.value, 3),
            "weight": weight,
            "contribution": round(contribution, 3),
            "source": m.note or "",
        }
        effect = "increases" if contribution >= 0 else "decreases"
        arguments.append(
            f"{label}: strength {m.value:.2f} -> {effect} (weight {weight:+.1f})"
        )

    if total_abs_weight == 0:
        probability = 0.5
    else:
        probability = clamp(total / total_abs_weight, MIN_PROB, MAX_PROB)

    confidence = _confidence(latest)
    risk = round(1 - confidence, 3)

    return Prediction(
        event_id=event.id,
        probability=round(probability, 4),
        confidence=round(confidence, 4),
        risk=risk,
        arguments=arguments,
        breakdown=breakdown,
        risk_reasons=_risk_reasons(latest),
    )


def recompute_latest(session: Session, event: Event) -> Prediction:
    metrics = (
        session.query(Metric)
        .filter(Metric.event_id == event.id)
        .order_by(Metric.created_at.desc())
        .all()
    )
    prediction = predict(event, metrics)
    session.add(prediction)
    session.commit()
    session.refresh(prediction)
    return prediction


def resolve_event(session: Session, event_id: int, outcome: bool) -> Resolution | None:
    event = session.get(Event, event_id)
    if event is None:
        return None
    event.status = "resolved"
    event.outcome = outcome
    last = (
        session.query(Prediction)
        .filter(Prediction.event_id == event.id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    probability = last.probability if last else 0.5
    brier = (probability - (1.0 if outcome else 0.0)) ** 2
    resolution = Resolution(
        event_id=event.id,
        actual_outcome=outcome,
        probability=probability,
        brier_score=round(brier, 4),
    )
    session.add(resolution)
    session.commit()
    session.refresh(resolution)
    return resolution
