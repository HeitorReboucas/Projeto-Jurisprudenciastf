from fastapi.testclient import TestClient

import app.main as main
from app.database import Database


class IdleCollector:
    def run(self, _: str) -> None:
        return None


def test_api_creates_and_reads_a_job(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "state.sqlite3")
    monkeypatch.setattr(main, "database", database)
    monkeypatch.setattr(main, "collector", IdleCollector())

    with TestClient(main.app) as client:
        health = client.get("/api/health")
        types = client.get("/api/content-types")
        created = client.post(
            "/api/jobs",
            json={
                "content_types": ["acordaos"],
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
                "query": "liberdade",
            },
        )

        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert {item["id"] for item in types.json()} == {
            "acordaos",
            "decisoes_monocraticas",
            "sumulas",
            "informativos",
        }
        assert created.status_code == 202
        job_id = created.json()["id"]
        assert created.json()["status"] == "queued"
        assert client.get(f"/api/jobs/{job_id}").json()["query"] == "liberdade"
        assert len(client.get(f"/api/jobs/{job_id}/events").json()) == 1


def test_api_rejects_invalid_date_range(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "state.sqlite3")
    monkeypatch.setattr(main, "database", database)
    monkeypatch.setattr(main, "collector", IdleCollector())

    with TestClient(main.app) as client:
        response = client.post(
            "/api/jobs",
            json={
                "content_types": ["acordaos"],
                "date_from": "2024-12-31",
                "date_to": "2024-01-01",
            },
        )

    assert response.status_code == 422