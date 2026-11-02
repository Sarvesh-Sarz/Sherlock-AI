from fastapi.testclient import TestClient


def test_start_response_includes_a_readable_trace(client: TestClient) -> None:
    body = client.post(
        "/investigation/start",
        json={"problem_description": "My laptop becomes slow after startup."},
    ).json()

    trace = body["trace"]
    assert trace, "every investigation should explain how it was run"
    assert trace[0]["stage"] == "plan"
    assert trace[-1]["stage"] == "reason"
    for event in trace:
        assert event["message"]
        assert event["timestamp"]
        assert event["stage"] in {"plan", "collect", "assess", "research", "reason"}


def test_trace_survives_a_round_trip_through_get(client: TestClient) -> None:
    started = client.post(
        "/investigation/start", json={"problem_description": "my wifi is slow"}
    ).json()
    fetched = client.get(f"/investigation/{started['case_id']}").json()

    assert fetched["trace"] == started["trace"]
    # The Planner's wifi-only decision is visible, and no broad scan sneaks in.
    plan_event = fetched["trace"][0]
    assert plan_event["details"]["tools"] == ["wifi"]
