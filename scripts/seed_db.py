import sys

from app.database import init_db
from app.seed import seed_demo


def main() -> None:
    init_db()
    force = "--force" in sys.argv
    result = seed_demo(force=force)
    if result.get("skipped"):
        print("Database already has data. Use --force to reseed demo data.")
    else:
        print(f"Seeded {result['events']} demo events with sources, signals and predictions.")


if __name__ == "__main__":
    main()
