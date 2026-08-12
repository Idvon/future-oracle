import os
import pathlib

TEST_DB = pathlib.Path(__file__).resolve().parent / "test_oracle.db"
os.environ["FO_DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_demo  # noqa: E402


def setup_module():
    TEST_DB.unlink(missing_ok=True)
    init_db()
    seed_demo(force=True)


def teardown_module():
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


def test_health():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"


def test_events_list():
    with TestClient(app) as client:
        response = client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 5
        assert all("probability" in item for item in data)


def test_event_detail():
    with TestClient(app) as client:
        event = client.get("/api/events").json()[0]
        response = client.get(f"/api/events/{event['id']}")
        assert response.status_code == 200
        body = response.json()
        assert "arguments" in body
        assert "breakdown" in body


def test_predict_recompute():
    with TestClient(app) as client:
        event = client.get("/api/events").json()[0]
        response = client.post(f"/api/events/{event['id']}/predict")
        assert response.status_code == 200
        assert 0.0 < response.json()["probability"] < 1.0


def test_resolve_creates_brier():
    with TestClient(app) as client:
        events = client.get("/api/events").json()
        active = next(item for item in events if item["status"] == "active")
        response = client.post(
            f"/api/events/{active['id']}/resolve", json={"outcome": True}
        )
        assert response.status_code == 200
        assert "brier_score" in response.json()
        accuracy = client.get("/api/accuracy").json()
        assert any(row["event_id"] == active["id"] for row in accuracy)


def test_index_page_renders():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Future Oracle" in response.text
        assert "Grand Theft Auto VI" in response.text


def test_accuracy_and_sources_pages():
    with TestClient(app) as client:
        assert client.get("/accuracy").status_code == 200
        sources_page = client.get("/sources")
        assert sources_page.status_code == 200
        assert "Wikipedia" in sources_page.text
