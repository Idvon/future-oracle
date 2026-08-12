from datetime import date, datetime, timezone

from app.models import Event, Metric
from app.scoring import predictor


def _metric(signal_type: str, value: float, reliability: float = 0.8) -> Metric:
    metric = Metric(
        signal_type=signal_type,
        value=value,
        source_reliability=reliability,
    )
    metric.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return metric


def _event() -> Event:
    return Event(id=1, game="Test Game", target_date=date(2026, 12, 31))


def test_positive_signals_increase_probability():
    event = _event()
    weak = predictor.predict(event, [_metric("news_mention_recent", 0.2)])
    strong = predictor.predict(event, [_metric("news_mention_recent", 0.9)])
    assert strong.probability > weak.probability


def test_negative_signals_decrease_probability():
    event = _event()
    base = predictor.predict(event, [_metric("official_date_confirmed", 0.8)])
    with_delay = predictor.predict(
        event,
        [_metric("official_date_confirmed", 0.8), _metric("delay_history", 0.9)],
    )
    assert with_delay.probability < base.probability


def test_confidence_grows_with_more_signals():
    event = _event()
    single = predictor.predict(event, [_metric("official_date_confirmed", 0.8)])
    many = predictor.predict(
        event,
        [
            _metric("official_date_confirmed", 0.8),
            _metric("rating_board_listing", 1.0),
            _metric("preorder_open", 0.9),
        ],
    )
    assert many.confidence > single.confidence


def test_probability_clamped_to_max():
    event = _event()
    prediction = predictor.predict(
        event,
        [
            _metric("official_date_confirmed", 1.0),
            _metric("rating_board_listing", 1.0),
            _metric("preorder_open", 1.0),
        ],
    )
    assert prediction.probability <= 0.98
    assert prediction.probability > 0.0


def test_risk_reasons_present_for_negative_signal():
    event = _event()
    prediction = predictor.predict(event, [_metric("silent_period", 0.9)])
    assert prediction.risk_reasons


def test_arguments_explain_each_signal():
    event = _event()
    prediction = predictor.predict(
        event, [_metric("official_date_confirmed", 0.8), _metric("delay_history", 0.5)]
    )
    assert len(prediction.arguments) == 2
    assert any("delay" in a.lower() for a in prediction.arguments)


def test_empty_signals_give_low_confidence():
    event = _event()
    prediction = predictor.predict(event, [])
    assert prediction.confidence == 0.05
    assert prediction.probability == 0.5
