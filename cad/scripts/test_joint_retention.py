"""check:joint_retention -- the threaded-joint retention audit and its table.

The fixture is the case that exposed the gap: a #10-32 stud screwed into an
arm until its shim seats, carrying an oiled rotating gear cluster that a front
cap retains axially (MHA-082 in MHA-164, paper drive). SolidWorks-free.
"""

from __future__ import annotations

import dataclasses

import joint_retention as jr
import pytest
from joint_retention import Exposure, Inventory, Joint, Kind, Lock

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


def _audit(joints, inventory=INVENTORY, **kwargs):
    kwargs.setdefault("threaded", THREADED)
    kwargs.setdefault("unthreaded", UNTHREADED)
    return jr.audit(joints, inventory, **kwargs)


def _kinds(findings) -> set[tuple[str, Kind]]:
    return {(f.subject, f.kind) for f in findings}


def _with_stud(**changes) -> tuple[Joint, ...]:
    return (dataclasses.replace(STUD, **changes), CAP, SCREW, NUT)


def test_a_mechanically_locked_stud_and_reasoned_static_clamps_pass() -> None:
    assert _audit(VALID) == []


def test_a_missing_joint_row_is_an_omitted_threaded_part() -> None:
    findings = _audit((STUD, CAP, NUT))
    # The screw and the base it threads into are named by no other row.
    assert _kinds(findings) == {("screw", Kind.OMITTED), ("base", Kind.OMITTED)}


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
    assert _audit(joints, rulings={"U99": "user, 2026-10-01"}) == []


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
    # An assembly without a keyed step list cannot be checked for it.
    unkeyed = Inventory({"paper_drive": PARTS})
    assert _audit(_with_stud(lock_step="SHEET 4 STEP 9"), unkeyed) == []


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
    findings = jr.audit([hook], inventory, threaded=threaded, unthreaded=frozenset())
    assert _kinds(findings) == {(hook.id, Kind.UNLOCKED)}
    # The same row filed under one sub-assembly cannot name the other's part.
    misfiled = dataclasses.replace(hook, assembly="channel")
    findings = jr.audit(
        [misfiled], inventory, threaded=threaded, unthreaded=frozenset()
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
    }
)


def test_the_table_covers_every_threaded_part_the_build_assembles() -> None:
    findings = [f for f in jr.audit_table() if f.kind in COVERAGE]
    assert findings == [], "\n".join(
        f"{f.assembly} {f.subject}: {f.kind}: {f.detail}" for f in findings
    )
