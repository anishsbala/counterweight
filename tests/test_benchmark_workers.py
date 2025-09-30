import pytest

from scripts import benchmark_workers


def test_wait_for_jobs_polls_job_collection(monkeypatch):
    responses = iter(
        [
            [
                {"job_id": "job-1", "status": "RUNNING"},
                {"job_id": "job-2", "status": "SUCCEEDED"},
            ],
            [
                {"job_id": "job-1", "status": "SUCCEEDED"},
                {"job_id": "job-2", "status": "SUCCEEDED"},
            ],
        ]
    )
    requests = []

    def request_json(method, url, payload=None):
        requests.append((method, url, payload))
        return next(responses)

    monkeypatch.setattr(benchmark_workers, "request_json", request_json)
    monkeypatch.setattr(benchmark_workers.time, "sleep", lambda _: None)

    benchmark_workers.wait_for_jobs("http://counterweight.test", ["job-1", "job-2"], timeout=1)

    assert requests == [
        (
            "POST",
            "http://counterweight.test/jobs/statuses",
            {"job_ids": ["job-1", "job-2"]},
        ),
        (
            "POST",
            "http://counterweight.test/jobs/statuses",
            {"job_ids": ["job-1"]},
        ),
    ]


def test_wait_for_jobs_surfaces_failed_job(monkeypatch):
    monkeypatch.setattr(
        benchmark_workers,
        "request_json",
        lambda *args, **kwargs: [
            {"job_id": "job-1", "status": "FAILED", "error": "pipeline error"}
        ],
    )

    with pytest.raises(RuntimeError, match="pipeline error"):
        benchmark_workers.wait_for_jobs("http://counterweight.test", ["job-1"], timeout=1)


def test_queue_drain_prefills_jobs_before_unpausing(monkeypatch):
    events = []
    job_numbers = iter(range(2))

    monkeypatch.setattr(benchmark_workers, "worker_container_ids", lambda: ["worker-1"])
    monkeypatch.setattr(
        benchmark_workers,
        "set_paused",
        lambda workers, paused: events.append(("paused", paused)),
    )

    def request_json(method, url, payload=None):
        events.append(("request", method))
        return {"job_id": f"job-{next(job_numbers)}"}

    monkeypatch.setattr(benchmark_workers, "request_json", request_json)
    monkeypatch.setattr(
        benchmark_workers,
        "wait_for_jobs",
        lambda api_url, job_ids: events.append(("wait", list(job_ids))),
    )
    timestamps = iter([10.0, 12.5])
    monkeypatch.setattr(benchmark_workers.time, "perf_counter", lambda: next(timestamps))

    elapsed = benchmark_workers.run_queue_drain("http://counterweight.test", 2, {"persist": True})

    assert elapsed == 2.5
    assert events == [
        ("paused", True),
        ("request", "POST"),
        ("request", "POST"),
        ("paused", False),
        ("wait", ["job-0", "job-1"]),
    ]
