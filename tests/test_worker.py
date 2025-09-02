from app.schemas import VerdictCountsResponse, VerifyArticleResponse
from app.worker import process_next_job


class FakeJobs:
    def __init__(self):
        self.completed = None
        self.failed = None

    def next_job(self, timeout=5):
        del timeout
        return "job-1"

    def claim_job(self, job_id, worker_id):
        return {
            "payload": {
                "title": "Test article",
                "article_text": "A sufficiently long factual claim for the queued worker test.",
                "persist": False,
            },
            "attempts": 1,
        }

    def complete_job(self, job_id, result):
        self.completed = (job_id, result)

    def fail_job(self, job_id, error):
        self.failed = (job_id, error)
        return False


def response():
    return VerifyArticleResponse(
        article_id=0,
        title="Test article",
        source_url=None,
        article_domain="technology",
        overall_verdict="likely supported",
        claims=[],
        results=[],
        verdict_counts=VerdictCountsResponse(
            likely_supported=1,
            mixed_support=0,
            weak_support=0,
            insufficient_evidence=0,
        ),
        report_summary="Complete",
        elapsed_ms=10,
    )


def test_worker_completes_claimed_job():
    jobs = FakeJobs()

    processed = process_next_job(jobs, lambda payload: response(), "worker-1", timeout=0)

    assert processed is True
    assert jobs.completed[0] == "job-1"
    assert jobs.completed[1]["overall_verdict"] == "likely supported"


def test_worker_records_failure():
    jobs = FakeJobs()

    def fail(payload):
        raise RuntimeError("pipeline failure")

    processed = process_next_job(jobs, fail, "worker-1", timeout=0)

    assert processed is True
    assert jobs.failed == ("job-1", "pipeline failure")
