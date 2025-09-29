from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "benchmarks" / "latest.json"


def request_json(
    method: str,
    url: str,
    payload: Dict[str, Any] | None = None,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_api(api_url: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            request_json("GET", f"{api_url}/health")
            return
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise RuntimeError("Counterweight API did not become healthy.")


def set_worker_count(count: int) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--scale",
            f"worker={count}",
            "--force-recreate",
            "worker",
        ],
        cwd=ROOT,
        check=True,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if len(worker_container_ids()) == count:
            time.sleep(1)
            return
        time.sleep(0.25)
    raise RuntimeError(f"Expected {count} worker containers to be running.")


def wait_for_jobs(api_url: str, job_ids: List[str], timeout: float = 300) -> None:
    remaining = set(job_ids)
    deadline = time.monotonic() + timeout
    while remaining and time.monotonic() < deadline:
        jobs = request_json("GET", f"{api_url}/jobs?limit=100")
        for job in jobs:
            job_id = job["job_id"]
            if job_id not in remaining:
                continue
            if job["status"] == "SUCCEEDED":
                remaining.remove(job_id)
            elif job["status"] == "FAILED":
                raise RuntimeError(f"Benchmark job failed: {job_id}: {job.get('error')}")
        if remaining:
            time.sleep(0.1)
    if remaining:
        raise TimeoutError(f"Timed out waiting for {len(remaining)} jobs.")


def worker_container_ids() -> List[str]:
    result = subprocess.run(
        ["docker", "compose", "ps", "--status", "running", "-q", "worker"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def set_paused(container_ids: Sequence[str], paused: bool) -> None:
    if not container_ids:
        raise RuntimeError("No running worker containers were found.")
    action = "pause" if paused else "unpause"
    subprocess.run(["docker", action, *container_ids], cwd=ROOT, check=True, capture_output=True)


def run_queue_drain(api_url: str, jobs: int, payload: Dict[str, Any]) -> float:
    workers = worker_container_ids()
    paused = False
    try:
        set_paused(workers, True)
        paused = True
        job_ids = [request_json("POST", f"{api_url}/jobs", payload)["job_id"] for _ in range(jobs)]
        started = time.perf_counter()
        set_paused(workers, False)
        paused = False
        wait_for_jobs(api_url, job_ids)
        return time.perf_counter() - started
    finally:
        if paused:
            set_paused(workers, False)


def benchmark(api_url: str, jobs: int) -> Dict[str, Any]:
    payload = json.loads((ROOT / "scripts" / "demo_request_tech.json").read_text(encoding="utf-8"))
    payload["persist"] = True

    subprocess.run(
        ["docker", "compose", "up", "--build", "-d", "db", "redis", "api"],
        cwd=ROOT,
        check=True,
    )
    wait_for_api(api_url)

    set_worker_count(1)
    single_seconds = run_queue_drain(api_url, jobs, payload)

    set_worker_count(4)
    four_seconds = run_queue_drain(api_url, jobs, payload)

    return {
        "jobs": jobs,
        "single_worker_seconds": round(single_seconds, 3),
        "four_worker_seconds": round(four_seconds, 3),
        "speedup": round(single_seconds / four_seconds, 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Measured the time required to drain an identical prefilled Redis queue.",
            "Job submission time was excluded so the result isolates worker throughput.",
            "The same persisted verification workload was used for both runs.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare one Counterweight worker with four Docker workers.")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--jobs", type=int, default=80)
    parser.add_argument("--minimum-speedup", type=float, default=3.1)
    args = parser.parse_args()
    if args.jobs < 8:
        parser.error("--jobs must be at least 8")
    if args.jobs > 100:
        parser.error("--jobs cannot exceed the API status window of 100")

    result = benchmark(args.api_url.rstrip("/"), args.jobs)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

    if result["speedup"] < args.minimum_speedup:
        print(
            f"Measured {result['speedup']}x, below required {args.minimum_speedup}x. "
            "Do not use the resume claim until the measured result supports it."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
