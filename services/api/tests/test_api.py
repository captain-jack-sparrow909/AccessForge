from fastapi.testclient import TestClient

from accessforge.main import app


def test_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_contains_phase_one_routes() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    document = response.json()
    assert response.status_code == 200
    assert "/v1/projects" in document["paths"]
    assert "/health/ready" in document["paths"]


def test_project_routes_require_bearer_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/projects")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
