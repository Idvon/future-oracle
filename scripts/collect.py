from app.collectors import rss_collector, store_collector, wikipedia_collector
from app.database import init_db, SessionLocal
from app.models import Event, RawRecord
from app.normalizers import signals
from app.scoring import predictor


def main() -> None:
    init_db()
    with SessionLocal() as session:
        try:
            created, updated = wikipedia_collector.collect(session)
            print(f"wikipedia: {created} events created, {updated} updated")
        except Exception as exc:
            print(f"wikipedia: skipped ({exc})")

        matched = rss_collector.collect(session)
        print(f"rss: {matched} articles matched to events")

        store_matched = store_collector.collect(session)
        print(f"stores: {store_matched} store listings matched to events")

        pending = (
            session.query(RawRecord)
            .filter(~RawRecord.metrics.any())
            .all()
        )
        normalized = signals.ingest_all(session, pending)
        print(f"normalizer: {normalized} metrics created from raw records")

        for event in session.query(Event).filter(Event.status == "active").all():
            prediction = predictor.recompute_latest(session, event)
            print(
                f"{event.game}: {prediction.probability:.0%} "
                f"(confidence {prediction.confidence:.0%})"
            )
    print("done")


if __name__ == "__main__":
    main()
