from app.planner.planner import Planner


def test_wifi_slow_checks_the_link_and_the_connection_but_not_the_whole_pc():
    planner = Planner()

    plan = planner.create_plan("My WiFi is very slow")

    # wifi = the link to the router; network = the connection beyond it.
    assert plan.tools_to_execute == ["wifi", "network"]
    assert plan.matched_keywords == ["wifi"]
    # "slow" must not widen this into the broad CPU/memory/disk scan.
    assert not {"cpu", "memory", "startup", "disk"} & set(plan.tools_to_execute)


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


def test_internet_problem_checks_the_link_and_the_connection():
    planner = Planner()

    plan = planner.create_plan("My internet is not working")

    assert plan.tools_to_execute == ["wifi", "network"]
    assert plan.matched_keywords == ["internet"]


def test_hyphenated_wi_fi_spelling_is_recognised():
    plan = Planner().create_plan("My Wi-Fi keeps dropping")

    assert plan.tools_to_execute == ["wifi", "network"]
    assert plan.matched_keywords == ["wi-fi"]


def test_network_slow_does_not_trigger_the_generic_scan():
    plan = Planner().create_plan("the network is slow today")

    assert plan.tools_to_execute == ["wifi", "network"]
    assert "cpu" not in plan.tools_to_execute


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

    plan = planner.create_plan("My computer smells like fresh paint")

    assert plan.tools_to_execute == ["cpu"]
    assert plan.matched_keywords == []


def test_speakers_problem_uses_audio():
    planner = Planner()

    plan = planner.create_plan("My speakers are making a strange noise")

    assert plan.tools_to_execute == ["audio"]
    assert plan.matched_keywords == ["speakers"]



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