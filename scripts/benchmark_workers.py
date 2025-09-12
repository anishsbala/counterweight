from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "benchmarks" / "latest.json"


def request_json(
    method: str,
    url: str,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
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
    time.sleep(3)


def wait_for_jobs(api_url: str, job_ids: List[str], timeout: float = 300) -> None:
    remaining = set(job_ids)
    deadline = time.monotonic() + timeout
    while remaining and time.monotonic() < deadline:
        for job_id in list(remaining):
            job = request_json("GET", f"{api_url}/jobs/{job_id}")
            if job["status"] == "SUCCEEDED":
                remaining.remove(job_id)
            elif job["status"] == "FAILED":
                raise RuntimeError(f"Benchmark job failed: {job_id}: {job.get('error')}")
        if remaining:
            time.sleep(0.1)
    if remaining:
        raise TimeoutError(f"Timed out waiting for {len(remaining)} jobs.")


def run_batch(api_url: str, jobs: int, payload: Dict[str, Any]) -> float:
    started = time.perf_counter()
    job_ids = [request_json("POST", f"{api_url}/jobs", payload)["job_id"] for _ in range(jobs)]
    wait_for_jobs(api_url, job_ids)
    return time.perf_counter() - started


def benchmark(api_url: str, jobs: int) -> Dict[str, Any]:
    payload = json.loads((ROOT / "scripts" / "demo_request_tech.json").read_text(encoding="utf-8"))
    payload["persist"] = False

    subprocess.run(
        ["docker", "compose", "up", "--build", "-d", "db", "redis", "api"],
        cwd=ROOT,
        check=True,
    )
    wait_for_api(api_url)

    set_worker_count(1)
    run_batch(api_url, 2, payload)
    single_seconds = run_batch(api_url, jobs, payload)

    set_worker_count(4)
    run_batch(api_url, 4, payload)
    four_seconds = run_batch(api_url, jobs, payload)

    return {
        "jobs": jobs,
        "single_worker_seconds": round(single_seconds, 3),
        "four_worker_seconds": round(four_seconds, 3),
        "speedup": round(single_seconds / four_seconds, 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Measured end-to-end through POST /jobs and GET /jobs/{id}.",
            "The same verification payload and persisted queue were used for both runs.",
            "Warm-up jobs were excluded from timing.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare one Counterweight worker with four Docker workers.")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--jobs", type=int, default=40)
    parser.add_argument("--minimum-speedup", type=float, default=3.1)
    args = parser.parse_args()
    if args.jobs < 8:
        parser.error("--jobs must be at least 8")

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
