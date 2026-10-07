"""Part 9 unit tests: interpretation, events, documents, PDF (rule 23).

These are deliberately offline (no HTTP) so the *pieces* are verified
independently of the endpoint layer.
"""

from __future__ import annotations

import types

import pytest

from app.analyses.constants import NO_UNSAFE_DETECTED_NOTE, UNSAFE_DETECTED_NOTE
from app.analyses.events import EventRecorder, stage_index
from app.analyses.interpret import interpret_goal
from app.analyses.pdf import render_report_pdf
from app.analyses.pipeline import (
    MITIGATION_BOUNDS,
    apply_mitigations_to_case,
    build_reverify_document,
    failure_detail,
    locate_failure,
    reverify_verdict,
)


# ----------------------------------------------------------------- interpret


def test_interpret_increase_throughput_by_30():
    change = interpret_goal("Increase production throughput by 30%")
    assert change.direction == "increase"
    assert change.magnitude == "30%"
    assert change.magnitude_value == 30.0
    assert change.is_percent is True
    assert change.variables == ["feed_factor"]
    assert change.unrecognised == []


def test_interpret_conflicting_direction_is_reported_not_guessed():
    change = interpret_goal("increase cooling then decrease cooling")
    assert change.direction == "conflicting"


def test_interpret_unknown_nouns_recorded_as_unrecognised():
    change = interpret_goal("raise the frobnicator level")
    assert change.direction == "increase"
    assert change.variables == []
    assert change.unrecognised, change.unrecognised


def test_interpret_never_invents_numbers():
    change = interpret_goal("make it nicer")
    assert change.magnitude is None
    assert change.magnitude_value is None


# -------------------------------------------------------------------- events


def test_event_recorder_sequences_are_gapless_and_time_measured():
    import time as _time

    fake_clock = iter([0.0, 5.0, 5.0, 7.0])
    rows: list[types.SimpleNamespace] = []

    class FakeDB:
        def add(self, row):
            rows.append(row)

    recorder = EventRecorder(FakeDB(), "an-1", monotonic=lambda: next(fake_clock))
    recorder.emit("planning", payload={"axes": 1})
    recorder.emit("observing_result", payload={"counts": {}})
    recorder.emit("complete")
    assert [r.seq for r in rows] == [1, 2, 3]
    assert rows[0].elapsed_ms == 5000
    assert rows[2].elapsed_ms == 7000
    assert [r.kind for r in rows] == ["planning", "observing_result", "complete"]
    del _time


def test_stage_index_maps_pipeline_order():
    assert stage_index("understanding_change") == 1
    assert stage_index("checking_safeguard") == 9
    assert stage_index("complete") is None


def test_event_recorder_bounds_oversized_lists():
    rows: list[types.SimpleNamespace] = []

    class FakeDB:
        def add(self, row):
            rows.append(row)

    recorder = EventRecorder(FakeDB(), "an-1")
    recorder.emit("observing_result", payload={"items": list(range(500))})
    kept = rows[0].payload["items"]
    assert len(kept) == 120  # MAX_STORED_TIMELINE
    assert kept[-1] == 499  # newest wins


# ------------------------------------------------------------------ pipeline


def test_locate_failure_matches_only_exact_key():
    result = {"failures": [{"key": "cooling_factor=0.0", "label": "x"}]}
    assert locate_failure(result, "cooling_factor=0.0") is not None
    assert locate_failure(result, "cooling_factor=0.5") is None
    assert locate_failure(None, "x") is None


def test_failure_detail_carries_the_full_evidence_page():
    original = {
        "plan": {
            "safety_limits": {"max_temperature_c": 150.0},
            "duration_s": 600.0,
            "time_step_s": 1.0,
        },
        "mode": "sweep",
        "counts": {"failing": 1},
    }
    failure = {
        "key": "cooling_factor=0.0",
        "label": "cooling 0%",
        "status": "violation",
        "values": {"cooling_factor": 0.0},
        "peaks": {"temperature_c": 152.5, "pressure_bar": 9.3, "level_pct": 44.0},
        "findings": [
            {
                "type": "temperature_c",
                "status": "violation",
                "peak": 152.5,
                "limit": 150.0,
            }
        ],
    }
    detail = failure_detail(
        analysis_id="an-1",
        failure=failure,
        original=original,
        series={"time_s": [0.0, 1.0], "true_temperature_c": [80.0, 152.5]},
        safeguards=[{"safeguard": "emergency_shutdown", "trigger_time_s": 3.0}],
    )
    assert detail["first_violation"]["type"] == "temperature_c"
    assert detail["configured_limits"]["max_temperature_c"] == 150.0
    assert detail["series"]["true_temperature_c"][-1] == 152.5
    assert detail["safeguard_events"][0]["trigger_time_s"] == 3.0
    assert detail["note"] == UNSAFE_DETECTED_NOTE


def test_apply_mitigations_maps_percent_and_delay_to_allowlist():
    values = {
        "cooling_factor": 0.0,
        "feed_factor": 1.30,
        "outlet_factor": 1.0,
        "valve_target_pct": 55.0,
        "shutdown_delay_s": 30.0,
    }
    mapped = apply_mitigations_to_case(
        values,
        {"cooling_capacity_pct": 120.0, "shutdown_delay_s": 5.0},
    )
    assert mapped["cooling_factor"] == pytest.approx(1.2)
    assert mapped["shutdown_delay_s"] == 5.0
    # Untouched values stay exactly as the parent case had them.
    assert mapped["feed_factor"] == values["feed_factor"]


def test_apply_mitigations_rejects_unknown_and_out_of_range():
    with pytest.raises(ValueError):
        apply_mitigations_to_case({}, {"banana_pct": 5.0})
    with pytest.raises(ValueError):
        apply_mitigations_to_case({}, {"cooling_factor": 99.0})


def test_reverify_verdict_language_is_exact():
    assert reverify_verdict({"failing_after": 0}) == NO_UNSAFE_DETECTED_NOTE
    assert (
        reverify_verdict({"failing_after": 1})
        == "Unsafe conditions were detected within the tested simulation scenarios; the listed failures are the evidence."
    )


def test_build_reverify_document_counts_improvements():
    parent = types.SimpleNamespace(
        id="an-parent",
        result={"pivot": {"values": {"cooling_factor": 0.0}}},
    )
    rows = [
        {
            "failure_id": "f1",
            "status_before": "violation",
            "status_after": "safe",
            "peaks_before": {},
            "peaks_after": {},
            "improved": True,
        },
        {
            "failure_id": "f2",
            "status_before": "violation",
            "status_after": "violation",
            "peaks_before": {},
            "peaks_after": {},
            "improved": False,
        },
    ]
    document = build_reverify_document(parent=parent, mitigations={"cooling_factor": 1.0}, after_rows=rows)
    assert document["comparison"]["failing_before"] == 2
    assert document["comparison"]["failing_after"] == 1
    assert document["verdict"] == UNSAFE_DETECTED_NOTE
    assert len(MITIGATION_BOUNDS) >= 5


# ------------------------------------------------------------------ PDF


BIG_DOC = {
    "goal": "Increase production throughput by 30%",
    "interpreted_change": {"direction": "increase", "magnitude": "30%", "variables": ["feed_factor"]},
    "original": {
        "status": "complete",
        "counts": {"scenarios": 9, "failing": 1, "violation": 1, "safeguard_activated": 0},
        "cases": [
            {"label": "case-1", "status": "safe", "peaks": {"temperature_c": 80.0}},
            {"label": "case-2", "status": "violation", "peaks": {"temperature_c": 168.0}},
        ],
        "notes": [],
    },
    "failures": [
        {
            "key": "cooling_factor=0.0",
            "label": "cooling 0%",
            "status": "violation",
            "peaks": {"temperature_c": 168.0, "pressure_bar": 10.4, "level_pct": 30.0},
        }
    ],
    "counterfactuals": [
        {
            "label": "restore cooling",
            "variable": "cooling_factor",
            "value": 1.0,
            "status": "safe",
            "improved": True,
        }
    ],
    "safeguards": {
        "timings": [
            {
                "safeguard": "emergency_shutdown",
                "trigger_time_s": 24.0,
                "response_time_s": 26.0,
                "violation_time_s": 22.5,
                "prevented": False,
            }
        ]
    },
    "ai_explanation": {"text": "Cooling loss raises temperature fastest."},
}


def _assert_pdf_structure(data: bytes) -> None:
    assert data.startswith(b"%PDF-1.4")
    assert data.rstrip().endswith(b"%%EOF")
    import re

    m = re.search(rb"startxref\n(\d+)\n%%EOF", data)
    assert m, "startxref missing"
    xref_pos = int(m.group(1))
    entries = re.findall(rb"(\d{10}) 00000 n", data[xref_pos:])
    assert entries, "no xref entries"
    for index, entry in enumerate(entries, start=1):
        offset = int(entry)
        assert data[offset:].startswith(f"{index} 0 obj".encode())


def test_pdf_has_valid_structure():
    data = render_report_pdf(BIG_DOC)
    _assert_pdf_structure(data)


def test_pdf_contains_goal_and_required_sentences():
    data = render_report_pdf(BIG_DOC).decode("cp1252", "replace")
    assert "Increase production throughput by 30%" in data
    assert "No unsafe condition was detected" not in data  # failures exist
    # Decompressed inspection is overkill; the escaped text must be present.
    assert "emergency_shutdown" in data


def test_pdf_escapes_special_characters():
    doc = {**BIG_DOC, "goal": "raise (pressure) \\50% and newline"}
    data = render_report_pdf(doc).decode("cp1252", "replace")
    # Parentheses and backslashes must be escaped in the PDF string, so the
    # raw stream carries the escaped form while the rendered text round-trips.
    assert "\\50%" in data
    assert "raise \\(pressure\\)" in data
