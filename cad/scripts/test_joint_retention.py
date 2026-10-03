"""check:joint_retention -- the threaded-joint retention audit and its table.

The fixture is the case that exposed the gap: a #10-32 stud screwed into an
arm until its shim seats, carrying an oiled rotating gear cluster that a front
cap retains axially (the paper drive's MHA-082 stud in MHA-164, retired by
R9-68 for a pressed pin). SolidWorks-free.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import joint_retention as jr
import pytest
from joint_retention import Exposure, Inventory, Joint, Kind, Lock, Occurrence, Ruling

PARTS = frozenset({"stud", "arm", "shim", "disc", "cap", "jam_nut", "base", "screw"})
THREADED = frozenset({"stud", "arm", "cap", "jam_nut", "base", "screw"})
UNTHREADED = PARTS - THREADED
STEPS = ("stud-fitted", "cluster-fitted", "stud-locked", "base-screwed")
INVENTORY = Inventory({"paper_drive": PARTS}, steps={"paper_drive": STEPS})

STUD = Joint(
    id="paper-drive/stud-in-arm",
    assembly="paper_drive",
    member="stud",
    receiver="arm",
    thread="#10-32 UNF",
    installed_at="stud-fitted",
    exposure=Exposure.ROTATING_DRAG,
    exposure_reason="fixed stud carries the oiled rotating disc cluster",
    axial_capture="shim seated on the arm face",
    lock=Lock.JAM_NUT,
    lock_part="jam_nut",
    lock_binds=("stud", "arm"),
    lock_step="stud-locked",
    evidence="fixture",
)
CAP = Joint(
    id="paper-drive/cap-on-stud",
    assembly="paper_drive",
    member="cap",
    receiver="stud",
    thread="#6-32 UNC",
    installed_at="cluster-fitted",
    exposure=Exposure.STATIC_CLAMP,
    exposure_reason="seats on the stud's journal shoulder; the cluster runs on "
    "end float against the cap face, no torque about the cap's thread",
    axial_capture="seats on the journal shoulder",
    lock=Lock.NONE,
    evidence="fixture",
)
SCREW = Joint(
    id="paper-drive/screw-in-base",
    assembly="paper_drive",
    member="screw",
    receiver="base",
    thread="#8-32 UNC",
    installed_at="base-screwed",
    exposure=Exposure.STATIC_CLAMP,
    exposure_reason="clamps the arm bracket flat on the base; neither moves",
    axial_capture="head on the bracket spotface",
    lock=Lock.NONE,
    evidence="fixture",
)
NUT = Joint(
    id="paper-drive/jam-nut-on-stud",
    assembly="paper_drive",
    member="jam_nut",
    receiver="stud",
    thread="#10-32 UNF",
    installed_at="stud-locked",
    exposure=Exposure.STATIC_CLAMP,
    exposure_reason="jammed against the arm's rear face; the stud it locks cannot "
    "turn, so no operating torque reaches the nut",
    axial_capture="bears on the arm's rear face",
    lock=Lock.NONE,
    evidence="fixture",
)
VALID = (STUD, CAP, SCREW, NUT)
REQUIRED = {j.id: Occurrence(j.assembly, "fixture", j.id) for j in VALID}


def _audit(joints, inventory=INVENTORY, **kwargs):
    kwargs.setdefault("threaded", THREADED)
    kwargs.setdefault("unthreaded", UNTHREADED)
    kwargs.setdefault("required", REQUIRED)
    return jr.audit(joints, inventory, **kwargs)


def _kinds(findings) -> set[tuple[str, Kind]]:
    return {(f.subject, f.kind) for f in findings}


def _with_stud(**changes) -> tuple[Joint, ...]:
    return (dataclasses.replace(STUD, **changes), CAP, SCREW, NUT)


def test_a_mechanically_locked_stud_and_reasoned_static_clamps_pass() -> None:
    assert _audit(VALID) == []


def test_a_missing_joint_row_is_omitted() -> None:
    findings = _audit((STUD, CAP, NUT))
    # The registered screw joint has no row, and the screw and the base it
    # threads into are named by no other row.
    assert _kinds(findings) == {
        (SCREW.id, Kind.OMITTED),
        ("screw", Kind.OMITTED),
        ("base", Kind.OMITTED),
    }


def test_a_missing_row_is_omitted_when_another_row_names_its_parts() -> None:
    # A second screw of the same stock into the same base: stem coverage is
    # satisfied by the first screw's row, so only the registry sees the gap.
    second = dataclasses.replace(SCREW, id="paper-drive/second-screw-in-base")
    required = {**REQUIRED, second.id: Occurrence("paper_drive", "fixture", "")}
    assert _audit((*VALID, second), required=required) == []
    assert _kinds(_audit(VALID, required=required)) == {(second.id, Kind.OMITTED)}


def test_a_row_the_registry_does_not_list_is_unregistered() -> None:
    extra = dataclasses.replace(SCREW, id="paper-drive/second-screw-in-base")
    assert _kinds(_audit((*VALID, extra))) == {(extra.id, Kind.UNREGISTERED)}
    # Registered under another assembly is not a match either.
    required = {**REQUIRED, SCREW.id: Occurrence("frame", "fixture", "")}
    assert _kinds(_audit(VALID, required=required)) == {(SCREW.id, Kind.UNREGISTERED)}


def test_threaded_lock_hardware_needs_its_own_row() -> None:
    # The stud row names the jam nut as its lock; that does not cover the nut.
    findings = _audit((STUD, CAP, SCREW))
    assert _kinds(findings) == {(NUT.id, Kind.OMITTED), ("jam_nut", Kind.OMITTED)}


def test_a_part_the_assembly_references_must_be_classified() -> None:
    findings = _audit(VALID, unthreaded=UNTHREADED - {"shim"})
    assert _kinds(findings) == {("shim", Kind.UNCLASSIFIED_PART)}


def test_purchased_hardware_is_unthreaded_only_with_a_reason() -> None:
    purchased = frozenset({"shim", "screw"})
    assert _kinds(_audit(VALID, purchased=purchased)) == {
        ("shim", Kind.UNCLASSIFIED_PART)
    }
    assert (
        _audit(VALID, purchased=purchased, unthreaded_stock={"shim": "plain shim"})
        == []
    )


def test_two_rows_with_one_id_are_reported() -> None:
    twin = dataclasses.replace(SCREW, id=CAP.id)
    findings = _audit((STUD, CAP, twin, NUT))
    assert (CAP.id, Kind.DUPLICATE_ID) in _kinds(findings)


@pytest.mark.parametrize("lock", [Lock.THREADLOCKER_ONLY, Lock.NONE])
@pytest.mark.parametrize(
    "exposure", [Exposure.ROTATING_DRAG, Exposure.OSCILLATING, Exposure.ADJUSTER]
)
def test_an_exposed_joint_without_a_mechanical_lock_fails(lock, exposure) -> None:
    joints = _with_stud(
        exposure=exposure, lock=lock, lock_part="", lock_binds=(), lock_step=""
    )
    assert _kinds(_audit(joints)) == {(STUD.id, Kind.UNLOCKED)}


def test_a_user_ruling_is_the_only_waiver_for_an_unlocked_exposed_joint() -> None:
    joints = _with_stud(
        lock=Lock.THREADLOCKER_ONLY,
        lock_part="",
        lock_binds=(),
        lock_step="",
        exception="U99",
    )
    assert _kinds(_audit(joints)) == {
        (STUD.id, Kind.UNKNOWN_EXCEPTION),
        (STUD.id, Kind.UNLOCKED),
    }
    ruling = {"U99": Ruling(joint=STUD.id, granted="user, 2026-10-01")}
    assert _audit(joints, rulings=ruling) == []


def test_a_ruling_waives_only_the_joint_it_names() -> None:
    # The screw cites the stud's ruling: it stays unlocked, and the reuse is
    # itself a finding; the stud is still waived.
    stud = dataclasses.replace(
        STUD,
        lock=Lock.THREADLOCKER_ONLY,
        lock_part="",
        lock_binds=(),
        lock_step="",
        exception="U99",
    )
    screw = dataclasses.replace(SCREW, exposure=Exposure.OSCILLATING, exception="U99")
    ruling = {"U99": Ruling(joint=STUD.id, granted="user, 2026-10-01")}
    assert _kinds(_audit((stud, CAP, screw, NUT), rulings=ruling)) == {
        (SCREW.id, Kind.EXCEPTION_MISMATCH),
        (SCREW.id, Kind.UNLOCKED),
    }


def test_the_thumbnut_rocked_by_the_free_t24_is_waived_only_by_its_ruling() -> None:
    """Machinist review of 6c385465d: the free T24 rocks against the MHA-126
    flange through its pin backlash, so the nut is an exposed joint; the
    user's U-MHA-126-no-lock ruling (2026-10-03) waives it, with the backlash
    the specs give."""
    import math

    import transgear_knob_drive_pin_spec as pin
    import transgear_removable_spec as wheel
    from _printed_tolerance import drilled_oversize_mm

    joint_id = "paper-drive/thumbnut-on-knob-shaft"
    (row,) = [j for j in jr.JOINTS if j.id == joint_id]
    assert row.exposure is Exposure.OSCILLATING
    assert row.lock is Lock.NONE
    assert jr.RULINGS[row.exception].joint == joint_id

    def unlocked(rulings) -> set[str]:
        findings = jr.audit(
            jr.JOINTS,
            jr.build_inventory(),
            threaded=jr.THREADED_PARTS,
            unthreaded=jr.UNTHREADED_PARTS,
            purchased=jr.purchased_parts(),
            unthreaded_stock=jr.UNTHREADED_STOCK,
            required=jr.REQUIRED_JOINTS,
            rulings=rulings,
        )
        return {f.subject for f in findings if f.kind is Kind.UNLOCKED}

    assert joint_id not in unlocked(jr.RULINGS)
    without = {k: v for k, v in jr.RULINGS.items() if k != row.exception}
    assert joint_id in unlocked(without)
    # The rock the ruling states: the largest drilled hole over the pin, on
    # the pin circle.
    clearance = (wheel.PIN_HOLE_DIA + drilled_oversize_mm() - pin.DIA) / 2.0
    rock = math.degrees(clearance / wheel.PIN_CIRCLE_RADIUS)
    assert f"\u00b1{rock:.1f}\u00b0 per reversal" in jr.RULINGS[row.exception].granted


def test_a_static_clamp_must_say_why_no_operating_torque_reaches_it() -> None:
    unreasoned = dataclasses.replace(SCREW, exposure_reason="  ")
    assert _kinds(_audit((STUD, CAP, unreasoned, NUT))) == {
        (SCREW.id, Kind.UNREASONED_STATIC_CLAMP)
    }


def test_an_unclassified_exposure_is_reported() -> None:
    joints = _with_stud(exposure=Exposure.UNCLASSIFIED)
    assert _kinds(_audit(joints)) == {(STUD.id, Kind.UNCLASSIFIED_EXPOSURE)}


def test_a_lock_part_the_assembly_does_not_contain_fails() -> None:
    joints = _with_stud(lock_part="lock_washer")
    assert _kinds(_audit(joints)) == {(STUD.id, Kind.LOCK_PART_ABSENT)}
    assert _kinds(_audit(_with_stud(lock_part=""))) == {
        (STUD.id, Kind.LOCK_PART_ABSENT)
    }


def test_a_modelled_feature_of_the_joint_itself_is_a_lock_part() -> None:
    staked = _with_stud(
        lock=Lock.STAKED, lock_part="stud:staked end", lock_binds=("arm", "stud")
    )
    assert _audit(staked) == []


def test_the_cluster_cap_is_not_credited_as_locking_the_stud_in_its_arm() -> None:
    joints = _with_stud(
        lock=Lock.LOCKED_NUT, lock_part="cap", lock_binds=("cap", "stud")
    )
    assert _kinds(_audit(joints)) == {(STUD.id, Kind.LOCK_WRONG_INTERFACE)}


def test_the_locking_operation_must_be_a_step_of_the_assembly() -> None:
    assert _kinds(_audit(_with_stud(lock_step="stud-torqued"))) == {
        (STUD.id, Kind.LOCK_STEP_ABSENT)
    }
    assert _kinds(_audit(_with_stud(lock_step=""))) == {
        (STUD.id, Kind.LOCK_STEP_ABSENT)
    }
    # Without a keyed step list the printed step text is accepted, but a lock
    # that no step installs is still reported.
    unkeyed = Inventory({"paper_drive": PARTS})
    assert _audit(_with_stud(lock_step="SHEET 4 STEP 9"), unkeyed) == []
    assert _kinds(_audit(_with_stud(lock_step=""), unkeyed)) == {
        (STUD.id, Kind.LOCK_STEP_ABSENT)
    }


def test_hardware_the_drawings_call_for_but_no_assembly_places_is_reported() -> None:
    # The arm's set screw is drilled for but never modelled: the row is
    # reported as missing hardware (not as an unknown part) and, exposed with
    # no lock, as unlocked.
    set_screw = Joint(
        id="paper-drive/arm-set-screw",
        assembly="paper_drive",
        member=jr.UNMODELLED,
        receiver="arm",
        thread="unresolved",
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason="pins the arm to the rocking shaft",
        axial_capture="none modelled",
        lock=Lock.NONE,
        evidence="fixture",
    )
    required = {**REQUIRED, set_screw.id: Occurrence("paper_drive", "fixture", "")}
    findings = _audit((set_screw, CAP, SCREW, NUT, STUD), required=required)
    assert _kinds(findings) == {
        (set_screw.id, Kind.HARDWARE_UNMODELLED),
        (set_screw.id, Kind.UNLOCKED),
    }


def test_a_row_naming_a_part_outside_its_assembly_fails() -> None:
    assert _kinds(_audit(_with_stud(receiver="frame_rail"))) == {
        (STUD.id, Kind.UNKNOWN_PART),
        (STUD.id, Kind.LOCK_WRONG_INTERFACE),
        ("arm", Kind.OMITTED),
    }


def test_a_cross_assembly_joint_covers_the_parts_of_both_subassemblies() -> None:
    inventory = Inventory(
        {
            "top": frozenset(),
            "channel": frozenset({"hook"}),
            "summing": frozenset({"plate"}),
        },
        subassemblies={"top": frozenset({"channel", "summing"})},
    )
    hook = Joint(
        id="top/hook-in-plate",
        assembly="top",
        member="hook",
        receiver="plate",
        thread="#6-32 UNC",
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason="the hook carries the rocking channel spring",
        axial_capture="trimmed shank tip short of the plate underside",
        lock=Lock.NONE,
        evidence="fixture",
    )
    threaded = frozenset({"hook", "plate"})
    required = {hook.id: Occurrence("top", "fixture", "")}
    findings = jr.audit(
        [hook], inventory, threaded=threaded, unthreaded=frozenset(), required=required
    )
    assert _kinds(findings) == {(hook.id, Kind.UNLOCKED)}
    # The same row filed under one sub-assembly cannot name the other's part.
    misfiled = dataclasses.replace(hook, assembly="channel")
    findings = jr.audit(
        [misfiled],
        inventory,
        threaded=threaded,
        unthreaded=frozenset(),
        required=required,
    )
    assert (hook.id, Kind.UNKNOWN_PART) in _kinds(findings)
    assert ("plate", Kind.OMITTED) in _kinds(findings)


# Table integrity: what the real table must satisfy in either enforcement
# mode. The retention findings are the audit's report, not a test failure.
COVERAGE = frozenset(
    {
        Kind.UNCLASSIFIED_PART,
        Kind.OMITTED,
        Kind.DUPLICATE_ID,
        Kind.UNKNOWN_PART,
        Kind.INSTALL_STEP_ABSENT,
        Kind.UNKNOWN_EXCEPTION,
        Kind.UNREGISTERED,
    }
)


def test_the_table_covers_every_threaded_part_the_build_assembles() -> None:
    findings = [f for f in jr.audit_table() if f.kind in COVERAGE]
    assert findings == [], "\n".join(
        f"{f.assembly} {f.subject}: {f.kind}: {f.detail}" for f in findings
    )


def test_every_registered_joint_cites_a_live_source_occurrence() -> None:
    scripts = Path(jr.__file__).parent
    stale = [
        f"{joint_id}: {o.anchor!r} not in {o.source}"
        for joint_id, o in jr.REQUIRED_JOINTS.items()
        if o.anchor not in (scripts / o.source).read_text(encoding="utf-8")
    ]
    assert stale == []


def test_deleting_a_row_whose_parts_other_rows_name_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The guide screws' stems stay named without their row: fillister_screw
    # as the clip screws' member, platen_guide as the lock screws' receiver.
    # Only the registry notices the guide-screw joint is gone.
    gone = "paper-drive/guide-screw-in-guide"
    table = tuple(j for j in jr.JOINTS if j.id != gone)
    findings = jr.audit(
        table,
        jr.build_inventory(),
        threaded=jr.THREADED_PARTS,
        unthreaded=jr.UNTHREADED_PARTS,
        purchased=jr.purchased_parts(),
        unthreaded_stock=jr.UNTHREADED_STOCK,
        required=jr.REQUIRED_JOINTS,
    )
    assert {f.subject for f in findings if f.kind is Kind.OMITTED} == {gone}
    monkeypatch.setattr(jr, "JOINTS", table)
    assert gone in jr.report(findings)["failing_joints"]


# Joints whose hardware the drawings call for but no builder places. A row
# reusing the stem of a placed instance of the same part would hide them.
UNPLACED = frozenset(
    {
        "magnifier/fixture-thumb-screw",  # build_magnifier_assembly omits it
        "pen/v-block-set-screw-on-rod",  # no set-screw part exists
    }
)


def test_hardware_no_builder_places_is_reported_as_unmodelled() -> None:
    unmodelled = {
        f.subject for f in jr.audit_table() if f.kind is Kind.HARDWARE_UNMODELLED
    }
    assert UNPLACED <= unmodelled


def test_per_channel_joints_follow_the_built_channel_count(monkeypatch) -> None:
    # A reduced build (machine/channels.yaml active_count) places fewer
    # channel anchors; the report must count what the build places.
    built = jr._config.active_count()
    before = jr.report([])["per_assembly"]["harmonic_analyzer"]["instances"]
    monkeypatch.setattr(jr._config, "active_count", lambda: 5)
    data = jr.report([])
    assert data["per_assembly"]["harmonic_analyzer"]["instances"] == before - (
        built - 5
    )
    anchors = next(
        j
        for j in data["joints"]
        if j["id"] == "harmonic-analyzer/channel-anchor-in-summing-plate"
    )
    assert anchors["instances"] == 5
