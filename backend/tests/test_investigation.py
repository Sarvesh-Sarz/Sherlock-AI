from fastapi.testclient import TestClient


def test_start_investigation_returns_case(client: TestClient) -> None:
    response = client.post(
        "/investigation/start",
        json={"problem_description": "My laptop becomes slow after startup."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "received"
    assert body["problem_description"] == "My laptop becomes slow after startup."
    assert body["case_id"]


def test_start_investigation_rejects_empty_description(client: TestClient) -> None:
    response = client.post("/investigation/start", json={"problem_description": ""})

    assert response.status_code == 422


def test_get_investigation_returns_created_case(client: TestClient) -> None:
    start_response = client.post(
        "/investigation/start",
        json={"problem_description": "Fans spin at full speed constantly."},
    )
    case_id = start_response.json()["case_id"]

    response = client.get(f"/investigation/{case_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == case_id
    assert body["status"] == "received"
    assert body["findings"] == []
    assert body["report"] is None


def test_get_investigation_missing_case_returns_404(client: TestClient) -> None:
    response = client.get("/investigation/does-not-exist")

    assert response.status_code == 404
