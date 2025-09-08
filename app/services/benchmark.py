import json
from pathlib import Path

from app.schemas import BenchmarkResponse


class BenchmarkService:
    def __init__(self, results_path: Path | None = None) -> None:
        self.results_path = results_path or Path(__file__).resolve().parents[2] / "benchmarks" / "latest.json"

    def get_summary(self) -> BenchmarkResponse:
        if not self.results_path.exists():
            return BenchmarkResponse(
                available=False,
                notes=[
                    "No measured result is available.",
                    "Run python scripts/benchmark_workers.py with Docker to generate one.",
                ],
            )

        result = json.loads(self.results_path.read_text(encoding="utf-8"))
        return BenchmarkResponse(
            available=True,
            jobs=result["jobs"],
            single_worker_seconds=result["single_worker_seconds"],
            four_worker_seconds=result["four_worker_seconds"],
            speedup=result["speedup"],
            generated_at=result["generated_at"],
            notes=result.get(
                "notes",
                ["Measured end-to-end through the persistent job API."],
            ),
        )
