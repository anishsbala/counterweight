from app.jobs import JobService


class FakeRepository:
    def __init__(self):
        self.completed = None
        self.failed = None

    def create(self, payload, max_attempts=3):
        return {"job_id": "job-1", "status": "QUEUED", "payload": payload}

    def claim(self, job_id, worker_id):
        return {"payload": {"title": "Test"}, "attempts": 1, "max_attempts": 3}

    def complete(self, job_id, result):
        self.completed = (job_id, result)

    def fail(self, job_id, error):
        self.failed = (job_id, error)
        return True

    def get(self, job_id):
        return {"job_id": job_id, "status": "QUEUED"}

    def list(self, limit):
        return [{"job_id": "job-1", "status": "QUEUED"}]

    def queued_ids(self):
        return ["job-1", "job-2"]


class FakeQueue:
    def __init__(self):
        self.items = []

    def enqueue(self, job_id):
        self.items.append(job_id)

    def dequeue(self, timeout=5):
        del timeout
        return self.items.pop() if self.items else None


def test_create_job_persists_before_enqueueing():
    repository = FakeRepository()
    queue = FakeQueue()
    service = JobService(repository=repository, queue=queue)

    result = service.create_job({"title": "Test"})

    assert result["job_id"] == "job-1"
    assert result["status_url"] == "/jobs/job-1"
    assert queue.items == ["job-1"]


def test_failed_job_is_requeued_when_attempts_remain():
    repository = FakeRepository()
    queue = FakeQueue()
    service = JobService(repository=repository, queue=queue)

    retry = service.fail_job("job-1", "temporary error")

    assert retry is True
    assert repository.failed == ("job-1", "temporary error")
    assert queue.items == ["job-1"]


def test_recover_queued_jobs_repopulates_redis():
    repository = FakeRepository()
    queue = FakeQueue()
    service = JobService(repository=repository, queue=queue)

    recovered = service.recover_queued_jobs()

    assert recovered == 2
    assert queue.items == ["job-1", "job-2"]
