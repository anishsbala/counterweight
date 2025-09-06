from fastapi.testclient import TestClient

import app.main as main_module

client = TestClient(main_module.app)


class FakeJobService:
    def create_job(self, payload, max_attempts=3):
        assert payload["persist"] is True
        assert max_attempts == 3
        return {
            "job_id": "job-123",
            "status": "QUEUED",
            "status_url": "/jobs/job-123",
        }

    def get_job(self, job_id):
        if job_id != "job-123":
            return None
        return {
            "job_id": job_id,
            "status": "SUCCEEDED",
            "attempts": 1,
            "max_attempts": 3,
            "worker_id": "worker-1",
            "result": {"overall_verdict": "likely supported"},
            "created_at": "2025-08-01T12:00:00Z",
        }

    def list_jobs(self, limit):
        return []


def test_create_and_read_queued_job(monkeypatch):
    monkeypatch.setattr(main_module, "job_service", FakeJobService())
    response = client.post(
        "/jobs",
        json={
            "title": "Queued verification",
            "article_text": "Researchers reported that solar capacity increased across several regions in 2024.",
            "persist": False,
        },
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-123"

    status = client.get("/jobs/job-123")
    assert status.status_code == 200
    assert status.json()["status"] == "SUCCEEDED"
    assert status.json()["worker_id"] == "worker-1"


def test_unknown_job_returns_not_found(monkeypatch):
    monkeypatch.setattr(main_module, "job_service", FakeJobService())

    response = client.get("/jobs/missing")

    assert response.status_code == 404
