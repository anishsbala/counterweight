from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_benchmark_route_requires_measured_results():
    response = client.get("/benchmark")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["speedup"] is None


def test_verify_route_without_database():
    response = client.post(
        "/verify",
        json={
            "title": "Energy brief",
            "persist": False,
            "article_text": (
                "Solar power accounted for most new electricity generation capacity added globally in recent years. "
                "Battery storage costs declined over time, making grid-scale storage more practical."
            ),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["claims"]) >= 1
    assert len(body["results"]) == len(body["claims"])
    assert body["overall_verdict"] in {"likely supported", "mixed support", "weak support", "insufficient evidence"}


def test_source_detail_route():
    response = client.get("/sources/iea-renewables")
    assert response.status_code == 200
    assert response.json()["organization"] == "International Energy Agency"
