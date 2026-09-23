"""Offline contracts for the clamp fixture's arm-end root (no SolidWorks).

clamp-both-r2/r3 rooted the eye against the plug face alone and never evaluated
the coplanar tube end face until the final gate, so both presets failed there
with 0.503 mm3 of spring inside the tube. The arm end is one clamp surface: the
root must bracket the FIRST contact with plug OR tube.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from diagnostics import calibrate_summing_clamp as clamp

CLEAR = {"state": "clear", "volume_mm3": 0.0}
HIT = {"state": "interfering", "volume_mm3": 0.5}


def _fixture(states, distances=None, *, limit=1e-5):
    calls = []

    def state(role):
        calls.append(role)
        return dict(states.get(role, CLEAR))

    def face_distance(role, certify=False):
        return {"distance_mm": (distances or {}).get(role, 1.0)}

    def require_contact(role):
        return {"role": role, "distance_mm": (distances or {})[role]}

    fixture = SimpleNamespace(
        state=state, face_distance=face_distance, require_contact=require_contact,
        distance_limit=limit, calls=calls,
    )
    for name in ("arm_end_state", "arm_end_contact", "all_clear"):
        setattr(fixture, name, getattr(clamp.Fixture, name).__get__(fixture))
    return fixture


@pytest.mark.parametrize("hit", ["plug", "tube"])
def test_arm_end_state_interferes_when_either_body_does(hit) -> None:
    fixture = _fixture({hit: HIT})

    result = fixture.arm_end_state()

    assert result["state"] == "interfering"
    assert set(fixture.calls) == {"plug", "tube"}


def test_arm_end_state_is_clear_only_when_both_bodies_are() -> None:
    assert _fixture({}).arm_end_state()["state"] == "clear"


def test_arm_end_contact_certifies_the_face_the_eye_bears_on() -> None:
    fixture = _fixture({}, {"plug": 0.5, "tube": 2e-6})

    result = fixture.arm_end_contact()

    assert result["rooting_faces"] == ["tube"]
    assert list(result["contacts"]) == ["tube"]


def test_arm_end_contact_refuses_a_landing_touching_neither_face() -> None:
    with pytest.raises(RuntimeError, match="no arm-end face in contact"):
        _fixture({}, {"plug": 0.5, "tube": 0.5}).arm_end_contact()


@pytest.mark.parametrize("role", ["boss", "plug", "tube", "screw"])
def test_all_clear_refuses_any_overlapping_clamp_body(role) -> None:
    with pytest.raises(RuntimeError, match="spring overlaps a clamp body"):
        _fixture({role: HIT}).all_clear("landing")


def test_root_lands_on_the_tube_rim_before_the_plug(monkeypatch) -> None:
    """Negative travel drives the eye toward the arm end. The tube rim is met at
    -0.03 mm, the plug (r3's only predicate) at -0.504: land on the tube."""
    tube_at, plug_at = -0.03, -0.504
    fixture = _fixture({}, {"tube": 2e-6, "plug": 0.47})
    fixture.resolution = 1e-6
    fixture.allowance = 6e-6
    fixture.evidence = {}

    def trial(_fixture, _seed, travel):
        hit = travel <= tube_at or travel <= plug_at
        return {"parameter_mm": travel, "state": "interfering" if hit else "clear"}

    monkeypatch.setattr(clamp, "_tilt_trial", trial)

    landed = clamp._arm_end_root(fixture, seed=None)

    assert landed["state"] == "clear"
    assert tube_at < landed["parameter_mm"] <= tube_at + 2e-5
    assert landed["arm_end_contact"]["rooting_faces"] == ["tube"]
    assert set(landed["all_bodies"]) == {"boss", "plug", "tube", "screw"}
    assert fixture.evidence["arm_end_landed"] is landed


def test_root_backs_out_of_a_seed_already_inside_the_arm_end(monkeypatch) -> None:
    """The (a) seed is flush with the tube rim; a seed reading interfering must
    march outboard to the first clear pose, not inward."""
    fixture = _fixture({}, {"tube": 2e-6, "plug": 0.5})
    fixture.resolution = 1e-6
    fixture.allowance = 6e-6
    fixture.evidence = {}

    def trial(_fixture, _seed, travel):
        return {"parameter_mm": travel, "state": "interfering" if travel <= 1e-4 else "clear"}

    monkeypatch.setattr(clamp, "_tilt_trial", trial)

    landed = clamp._arm_end_root(fixture, seed=None)

    assert 1e-4 < landed["parameter_mm"] <= 1e-4 + 2e-5


def _withdrawal(amount, distance, raw=None, native=CLEAR):
    raw = distance if raw is None else raw
    return {"withdrawn_mm": amount, "native": dict(native),
            "distance": {"distance_mm": distance, "raw_closest_distance": {"distance_mm": raw}}}


def test_face_normal_head_withdrawal_keeps_the_0_04_floor() -> None:
    assert clamp._withdrawal_refusal("head", [_withdrawal(0.05, 0.0499)], 1.7e-5) is None
    assert "face-normal" in clamp._withdrawal_refusal("head", [_withdrawal(0.05, 0.03)], 1.7e-5)
    # the raw channel is independent: a low raw reading refuses on its own
    assert clamp._withdrawal_refusal("head", [_withdrawal(0.05, 0.05, raw=0.01)], 1.7e-5)


def test_edge_contact_on_the_tube_corner_passes_the_direction_agnostic_proof() -> None:
    """r4: the eye wire wraps the tube's OD corner, so a 0.05 mm axial
    withdrawal opens only ~0.05*|n_x|. That is separation, not a failure."""
    rows = [_withdrawal(0.05, 0.012), _withdrawal(0.10, 0.024)]

    assert clamp._withdrawal_refusal("tube", rows, 1.7e-5) is None
    # the same readings would fail a face-normal floor
    assert clamp._withdrawal_refusal("head", rows[:1], 1.7e-5) is not None


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ([_withdrawal(0.05, 1e-5), _withdrawal(0.10, 0.02)], "contact limit"),
        ([_withdrawal(0.05, 0.02), _withdrawal(0.10, 0.02)], "strictly increase"),
        ([_withdrawal(0.05, 0.02), _withdrawal(0.10, 0.03, raw=0.01)], "strictly increase"),
        ([_withdrawal(0.05, 0.02, native=HIT), _withdrawal(0.10, 0.04)], "native overlap"),
    ],
)
def test_edge_withdrawal_refuses_what_does_not_prove_separation(rows, reason) -> None:
    assert reason in clamp._withdrawal_refusal("tube", rows, 1.7e-5)


def test_refused_control_still_reports_what_it_measured() -> None:
    """The failed report must carry the withdrawn distances (r4 lost them)."""
    fixture = SimpleNamespace(
        evidence={}, expected={"screw": [0.0] * 16, "tube": [0.0] * 16}, distance_limit=1.7e-5,
        require_contact=lambda role: {"role": role, "distance_mm": 0.0},
        put=lambda targets: None, shift=lambda role, direction, amount: None,
        face_distance=lambda role, certify=False: {
            "distance_mm": 0.05 if role == "head" else 0.01,
            "raw_closest_distance": {"distance_mm": 0.05 if role == "head" else 0.01},
        },
        state=lambda role: dict(CLEAR),
    )

    with pytest.raises(RuntimeError, match="tube: finite-face withdrawal positive control failed"):
        clamp._positive_controls(fixture, 4.6, ["tube"])

    tube = fixture.evidence["positive_controls"]["tube"]
    assert [row["withdrawn_mm"] for row in tube["withdrawals"]] == [0.05, 0.10]
    assert fixture.evidence["positive_controls"]["head"]["withdrawals"][0]["withdrawn_mm"] == 0.05


def _report(tmp_path, preset, *, status="completed", eye_error=0.0):
    import json

    row = {
        "pose": {"length_mm": 350.0, "lower_eye_xy": [-91.24, 1006.5],
                 "upper_eye_xy": [clamp.mounts.COUNTER_UPPER_EYE_X + eye_error, 1346.8],
                 "axis_xy": [-0.005, 0.99999], "centre_xy": [-92.1, 1176.6], "clocking": "half_turn"},
        "gooseneck_origin_y_mm": 1186.5,
        "final_distance_mm": {"lower": 1e-6, "upper": 2e-8, "tube_face": 0.0, "under_head_face": 3e-6},
        "clamp_gap_mm": 4.6,
    }
    path = tmp_path / f"{preset}.json"
    path.write_text(json.dumps({"status": status, "counters": {preset: row}}), encoding="utf-8")
    return path


@pytest.fixture
def springs_copy(tmp_path, monkeypatch):
    from diagnostics import calibrate_spring_seats as seats

    copy = tmp_path / "springs.yaml"
    copy.write_text(seats.SPRINGS_YAML.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(seats, "SPRINGS_YAML", copy)
    return copy


def test_apply_report_replaces_only_the_counter_rows(tmp_path, springs_copy) -> None:
    import yaml

    before = yaml.safe_load(springs_copy.read_text(encoding="utf-8"))["springs"]
    header = [line for line in springs_copy.read_text(encoding="utf-8").splitlines() if line.startswith("#")]

    clamp.apply_reports([_report(tmp_path, preset) for preset in clamp.PRESETS])

    text = springs_copy.read_text(encoding="utf-8")
    after = yaml.safe_load(text)["springs"]
    assert [line for line in text.splitlines() if line.startswith("#")] == header
    assert after["channel_seats"] == before["channel_seats"]
    assert after["source"] == before["source"]
    for preset in clamp.PRESETS:
        counter = after["presets"][preset]["counter"]
        assert set(counter) == {"pose", "gooseneck_origin_y_mm", "final_distance_mm"}
        assert set(counter["final_distance_mm"]) == {"lower", "upper"}
        assert {k: v for k, v in after["presets"][preset].items() if k != "counter"} == {
            k: v for k, v in before["presets"][preset].items() if k != "counter"
        }


@pytest.mark.parametrize(
    ("make", "reason"),
    [
        (lambda tmp: [_report(tmp, "neutral", status="failed"), _report(tmp, "square")], "completed"),
        (lambda tmp: [_report(tmp, "neutral")], "missing"),
        (lambda tmp: [_report(tmp, "neutral", eye_error=2e-4), _report(tmp, "square")], "committed"),
    ],
)
def test_apply_report_refuses_what_it_cannot_certify(tmp_path, springs_copy, make, reason) -> None:
    original = springs_copy.read_text(encoding="utf-8")

    with pytest.raises(SystemExit, match=reason):
        clamp.apply_reports(make(tmp_path))

    assert springs_copy.read_text(encoding="utf-8") == original
