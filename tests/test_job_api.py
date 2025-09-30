from fastapi.testclient import TestClient

import app.main as main_module

client = TestClient(main_module.app)

JOB_ONE = "7d71943b-8b9e-46f8-95e6-8614b290ed27"
JOB_TWO = "ba55a3a4-d45f-4531-a310-3661be37ccb0"


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

    def job_statuses(self, job_ids):
        rows = {
            JOB_ONE: {"job_id": JOB_ONE, "status": "RUNNING", "error": None},
            JOB_TWO: {"job_id": JOB_TWO, "status": "SUCCEEDED", "error": None},
        }
        return [rows[job_id] for job_id in reversed(job_ids) if job_id in rows]


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


def test_reads_compact_job_statuses_in_request_order(monkeypatch):
    monkeypatch.setattr(main_module, "job_service", FakeJobService())

    response = client.post("/jobs/statuses", json={"job_ids": [JOB_ONE, JOB_TWO]})

    assert response.status_code == 200
    assert response.json() == [
        {"job_id": JOB_ONE, "status": "RUNNING", "error": None},
        {"job_id": JOB_TWO, "status": "SUCCEEDED", "error": None},
    ]


def test_rejects_invalid_batch_job_ids(monkeypatch):
    monkeypatch.setattr(main_module, "job_service", FakeJobService())

    response = client.post("/jobs/statuses", json={"job_ids": ["not-a-uuid"]})

    assert response.status_code == 422
