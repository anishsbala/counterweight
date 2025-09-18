from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

API_URL = "http://localhost:8000"


def request_json(method: str, path: str, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_health(timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            request_json("GET", "/health")
            return
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise TimeoutError("API did not become healthy")


def main() -> int:
    wait_for_health()
    accepted = request_json(
        "POST",
        "/jobs",
        {
            "title": "Queue smoke test",
            "article_text": (
                "According to researchers, solar generation increased during 2024 "
                "while battery storage costs continued to decline."
            ),
            "persist": True,
        },
    )
    job_id = accepted["job_id"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        job = request_json("GET", f"/jobs/{job_id}")
        if job["status"] == "SUCCEEDED":
            assert job["attempts"] == 1
            assert job["worker_id"]
            assert job["result"]["claims"]
            print(f"queued job {job_id} completed on {job['worker_id']}")
            return 0
        if job["status"] == "FAILED":
            raise RuntimeError(job["error"])
        time.sleep(0.25)
    raise TimeoutError(f"job {job_id} did not complete")


if __name__ == "__main__":
    raise SystemExit(main())
