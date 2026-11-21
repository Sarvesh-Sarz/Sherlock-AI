from datetime import datetime, timezone

import pytest

from app.models.investigation_report import Confidence, Hypothesis
from app.models.tool_result import ToolResult, ToolStatus
from app.reasoning.grounding import collect_facts, ground_hypotheses, is_grounded, overall_confidence


def ev(name, payload, status=ToolStatus.SUCCESS):
    return ToolResult(tool_name=name, status=status, collected_at=datetime.now(timezone.utc), payload=payload)


WIFI = ev("wifi", {
    "connected": True, "ssid": "CampusNet", "signal_percent": 62, "link_speed_mbps": 200.0,
    "radio_type": "802.11ac", "interface": "Wi-Fi",
    "adapter": "Intel(R) Wi-Fi 6 AX201 160MHz",
})
NET = ev("network", {"dns_ms": 2.8, "connect_ms": 4.6, "first_byte_ms": 124.1, "failed_samples": 0})
FACTS = collect_facts([WIFI, NET])


def hyp(title, *entries, confidence=Confidence.MEDIUM):
    return Hypothesis(title=title, explanation="x", supporting_evidence=list(entries), confidence=confidence)


# ---- What counts as a fact ---------------------------------------------------

def test_failed_evidence_grounds_nothing():
    facts = collect_facts([ev("cpu", {"usage_percent": 93.0}, ToolStatus.ERROR)])
    assert not is_grounded("CPU usage: 93%", facts)


def test_nested_values_and_list_lengths_are_facts():
    facts = collect_facts([ev("disk", {"volumes": [{"usage_percent": 91.2, "free_gb": 12.3}, {"usage_percent": 40.0}]})])
    assert is_grounded("C: is 91.2% full", facts)
    assert is_grounded("2 volumes were checked", facts)


def test_booleans_are_not_numbers():
    assert not is_grounded("connected: 1", collect_facts([ev("wifi", {"connected": True})]))


# ---- is_grounded ---------------------------------------------------------------

@pytest.mark.parametrize("entry", [
    "Wi-Fi signal strength: 62%",
    "Time to first response: 124 ms",       # rounds 124.1
    "Time to first response: 124.1 ms",
    "Link rate 200 Mbps and signal 62%",
    "Name lookup took 2.8 ms",
])
def test_real_values_are_grounded(entry):
    assert is_grounded(entry, FACTS)


@pytest.mark.parametrize("entry", [
    "Signal strength: 45%",                       # invented number
    "Time to first response: 125 ms",             # wrong when rounded to the stated precision
    "Signal 62% but latency 900 ms",              # one real number does not launder a fake one
    "Wi-Fi adapter settings may be misconfigured",  # a claim with no measurement
    "The driver is outdated",
    "",
])
def test_invented_or_unmeasured_claims_are_not_grounded(entry):
    assert not is_grounded(entry, FACTS)


def test_digits_inside_known_names_are_labels_not_claimed_measurements():
    assert is_grounded("Intel(R) Wi-Fi 6 AX201 160MHz reports 62% signal", FACTS)
    assert is_grounded("Standard 802.11ac at 62% signal", FACTS)


def test_digits_in_unknown_identifiers_do_not_count_as_numbers_either_way():
    # "AX201" alone cites no measurement, so it cannot ground anything.
    assert not is_grounded("The AX201 adapter looks old", FACTS)


# ---- ground_hypotheses -------------------------------------------------------------

def test_a_hypothesis_without_any_grounded_entry_is_dropped():
    result = ground_hypotheses([hyp("Adapter or driver issue", "Adapter reports an error", "Signal 45%")], FACTS)
    assert result.kept == []
    assert result.dropped_titles == ["Adapter or driver issue"]
    assert result.removed_entries == 2


def test_ungrounded_entries_are_removed_from_a_hypothesis_that_survives():
    result = ground_hypotheses([hyp("Slow responses", "First response: 124 ms", "Probably congested")], FACTS)
    (kept,) = result.kept
    assert kept.supporting_evidence == ["First response: 124 ms"]
    assert result.removed_entries == 1 and result.dropped_titles == []


def test_a_hypothesis_with_no_supporting_evidence_at_all_is_dropped():
    assert ground_hypotheses([hyp("Just a feeling")], FACTS).kept == []


def test_the_input_hypotheses_are_not_mutated():
    original = hyp("Slow responses", "First response: 124 ms", "Probably congested")
    ground_hypotheses([original], FACTS)
    assert original.supporting_evidence == ["First response: 124 ms", "Probably congested"]


# ---- overall_confidence ----------------------------------------------------------------

def test_overall_confidence_is_the_strongest_hypothesis_not_an_average():
    assert overall_confidence([hyp("a", confidence=Confidence.LOW), hyp("b", confidence=Confidence.HIGH)]) == Confidence.HIGH
    assert overall_confidence([hyp("a", confidence=Confidence.LOW), hyp("b", confidence=Confidence.MEDIUM)]) == Confidence.MEDIUM
    assert overall_confidence([hyp("a", confidence=Confidence.LOW)]) == Confidence.LOW


def test_no_hypotheses_means_low_confidence():
    assert overall_confidence([]) == Confidence.LOW
