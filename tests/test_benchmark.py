import json
from datetime import datetime, timezone

from app.services.benchmark import BenchmarkService


def test_benchmark_is_unavailable_without_measured_result(tmp_path):
    response = BenchmarkService(tmp_path / "missing.json").get_summary()

    assert response.available is False
    assert response.speedup is None


def test_benchmark_loads_measured_worker_result(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps(
            {
                "jobs": 40,
                "single_worker_seconds": 12.4,
                "four_worker_seconds": 4.0,
                "speedup": 3.1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    response = BenchmarkService(path).get_summary()

    assert response.available is True
    assert response.speedup == 3.1
