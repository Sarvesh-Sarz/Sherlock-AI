from fastapi.testclient import TestClient


def test_start_investigation_returns_case(client: TestClient) -> None:
    response = client.post(
        "/investigation/start",
        json={"problem_description": "My laptop becomes slow after startup."},
    )

    assert response.status_code == 201
    body = response.json()
    # Status moves past "received" because the CPU tool runs synchronously
    # during intake — see InvestigationService._collect_evidence.
    assert body["status"] == "investigating"
    assert body["problem_description"] == "My laptop becomes slow after startup."
    assert body["case_id"]

    # Three tools are wired up today: cpu, memory, and disk. "slow" plans
    # all of them (plus "startup", which isn't implemented yet and is
    # silently skipped by ToolManager). Numeric values are
    # environment-dependent, so assert on structure/types, not specific
    # numbers — a real machine could report literally anything valid here.
    assert len(body["evidence"]) == 3
    evidence_by_tool = {item["tool_name"]: item for item in body["evidence"]}
    assert set(evidence_by_tool) == {"cpu", "memory", "disk"}

    cpu_result = evidence_by_tool["cpu"]
    assert cpu_result["status"] in ("success", "error")
    assert "collected_at" in cpu_result
    if cpu_result["status"] == "success":
        payload = cpu_result["payload"]
        assert isinstance(payload["usage_percent"], (int, float))
        assert "physical_cores" in payload
        assert "logical_cores" in payload
        assert "current_frequency" in payload
        assert "max_frequency" in payload

    memory_result = evidence_by_tool["memory"]
    assert memory_result["status"] in ("success", "error")
    assert "collected_at" in memory_result
    if memory_result["status"] == "success":
        payload = memory_result["payload"]
        assert isinstance(payload["usage_percent"], (int, float))
        assert "total_gb" in payload
        assert "available_gb" in payload
        assert "used_gb" in payload
        assert "swap_total_gb" in payload
        assert "swap_used_gb" in payload

    disk_result = evidence_by_tool["disk"]
    assert disk_result["status"] in ("success", "error")
    assert "collected_at" in disk_result
    if disk_result["status"] == "success":
        payload = disk_result["payload"]
        assert isinstance(payload["volumes"], list)
        for volume in payload["volumes"]:
            assert "mountpoint" in volume
            assert isinstance(volume["usage_percent"], (int, float))
            assert "total_gb" in volume
            assert "used_gb" in volume
            assert "free_gb" in volume
            assert "filesystem" in volume


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
    assert body["status"] == "investigating"
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["tool_name"] == "cpu"
    assert body["findings"] == []
    assert body["report"] is None


def test_get_investigation_missing_case_returns_404(client: TestClient) -> None:
    response = client.get("/investigation/does-not-exist")

    assert response.status_code == 404
