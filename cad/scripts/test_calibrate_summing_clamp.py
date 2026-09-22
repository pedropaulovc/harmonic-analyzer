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
