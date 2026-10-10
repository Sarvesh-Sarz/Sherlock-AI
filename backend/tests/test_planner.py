from app.planner.planner import Planner


def test_wifi_slow_uses_wifi_only():
    planner = Planner()

    plan = planner.create_plan("My WiFi is very slow")

    assert plan.tools_to_execute == ["wifi"]
    assert plan.matched_keywords == ["wifi"]


def test_slow_computer_uses_generic_diagnostics():
    planner = Planner()

    plan = planner.create_plan("My computer is very slow")

    assert plan.tools_to_execute == [
        "cpu",
        "memory",
        "startup",
        "disk",
    ]
    assert plan.matched_keywords == ["slow"]


def test_internet_problem_uses_wifi():
    planner = Planner()

    plan = planner.create_plan("My internet is not working")

    assert plan.tools_to_execute == ["wifi"]
    assert plan.matched_keywords == ["internet"]


def test_battery_and_hot_can_match_together():
    planner = Planner()

    plan = planner.create_plan("My battery is draining and my laptop is hot")

    assert plan.tools_to_execute == [
        "battery",
        "cpu",
        "startup",
        "temperature",
    ]
    assert plan.matched_keywords == ["battery", "hot"]


def test_unknown_problem_uses_default_tool():
    planner = Planner()

    plan = planner.create_plan("My speakers are making a strange noise")

    assert plan.tools_to_execute == ["cpu"]
    assert plan.matched_keywords == []


def test_keyword_matching_uses_whole_words():
    planner = Planner()

    plan = planner.create_plan("The hotel application is slow")

    assert "hot" not in plan.matched_keywords
    assert "slow" in plan.matched_keywords


def test_duplicate_tools_are_removed():
    planner = Planner()

    plan = planner.create_plan("My computer is slow and hot")

    assert plan.tools_to_execute == [
        "cpu",
        "memory",
        "startup",
        "disk",
        "temperature",
    ]