"""check:joint_retention -- the threaded-joint retention audit and its table.

The fixture is the case that exposed the gap: a #10-32 stud screwed into an
arm until its shim seats, carrying an oiled rotating gear cluster that a front
cap retains axially (the paper drive's MHA-082 stud in MHA-PD-18, retired by
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
INVENTORY = Inventory({"pd_paper_drive": PARTS}, steps={"pd_paper_drive": STEPS})

STUD = Joint(
    id="pd-paper-drive/stud-in-arm",
    assembly="pd_paper_drive",
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
    id="pd-paper-drive/cap-on-stud",
    assembly="pd_paper_drive",
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
    id="pd-paper-drive/screw-in-base",
    assembly="pd_paper_drive",
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
    id="pd-paper-drive/jam-nut-on-stud",
    assembly="pd_paper_drive",
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


def test_magnifying_bracket_joint_is_a_two_screw_static_clamp() -> None:
    row = next(
        joint
        for joint in jr.JOINTS
        if joint.id == "ha-harmonic-analyzer/magnifying-bracket-screws"
    )
    assert row.assembly == "ha_harmonic_analyzer"
    assert row.member == "mg_vn_magnifying_bracket_screw"
    assert row.receiver == "sm_summing_lever"
    assert row.quantity == 2
    assert row.thread == "#2-56 UNC"
    assert "flange front face" in row.axial_capture
    assert row.exposure is Exposure.STATIC_CLAMP
    assert row.lock is Lock.NONE
    assert not row.lock_part and not row.exception
    assert "without relative motion" in row.exposure_reason
    assert row.member in jr.THREADED_PARTS
    assert "mg_magnifying_bracket" in jr.THREADED_PARTS
    assert jr.REQUIRED_JOINTS[row.id].assembly == row.assembly
    assert row.member in jr.build_inventory().parts["mg_magnifier"]


def test_lever_thread_is_depth_installed_without_invented_shoulder_or_lock() -> None:
    import mg_magnifier_assembly_steps as steps
    row = next(joint for joint in jr.JOINTS if joint.id == "mg-magnifier/lever-in-bracket")
    assert row.member == "mg_magnifying_lever" and row.receiver == "mg_magnifying_bracket"
    assert row.member in jr.THREADED_PARTS and row.receiver in jr.THREADED_PARTS
    assert row.installed_at == steps.LEVER_THREADED_KEY
    assert row.exposure is Exposure.ADJUSTER and row.lock is Lock.NONE
    assert not row.lock_part
    assert "ThreadProjection" in row.axial_capture and "no shoulder" in row.axial_capture
    assert jr.REQUIRED_JOINTS[row.id].assembly == row.assembly
    assert jr.RULINGS[row.exception].joint == row.id
    inventory = Inventory(
        {row.assembly: frozenset({row.member, row.receiver})},
        steps={row.assembly: (row.installed_at,)},
    )
    arguments = {
        "threaded": frozenset({row.member, row.receiver}),
        "unthreaded": frozenset(),
        "required": {row.id: jr.REQUIRED_JOINTS[row.id]},
    }
    assert jr.audit((row,), inventory, **arguments) == []
    unwaived = dataclasses.replace(row, exception="")
    assert _kinds(jr.audit((unwaived,), inventory, **arguments)) == {(row.id, Kind.UNLOCKED)}


@pytest.mark.parametrize("name,kind", (
    ("mg_magnifying_bracket", "part"),
    ("mg_magnifying_lever", "part"),
    ("mg_magnifier_assembly", "assembly"),
))
def test_unseated_lever_exception_reaches_only_its_actual_review_packages(monkeypatch, name, kind) -> None:
    import machinist_review
    from machinist_exceptions import load_exceptions

    package = machinist_review.ReviewPackage(name, kind, (Path("native-sheet.png"),))
    monkeypatch.setattr(machinist_review, "_text_layers", lambda _package: "")
    exceptions = load_exceptions(machinist_review.CAD_ROOT / "config", name, kind)
    declaration = next(entry for entry in exceptions if "unseated lever thread" in entry.finding)
    assert declaration.kind == "accept"
    prompt = machinist_review._review_prompt(package, 1, prompt_text="")
    assert f"- {declaration.id} [accept]" in prompt
    assert declaration.finding in prompt and declaration.reason in prompt
    assert "vibration" in declaration.reason.lower()
    unrelated = machinist_review.ReviewPackage("mg_magnifying_clamp", "part", package.sources)
    assert declaration.finding not in machinist_review._review_prompt(unrelated, 1, prompt_text="")


def test_pinion_cam_inch_set_screws_remain_staked_at_fitup() -> None:
    import dt_pinion_cam_geometry as geometry
    import dt_pinion_cam_spec as spec

    row = next(
        joint
        for joint in jr.JOINTS
        if joint.id == "dt-drive-train/pinion-cam-set-screw"
    )
    assert row.thread.startswith(f"{geometry.SET_SCREW_HOLE_SPEC.size} UNC ")
    assert row.member == "dt_pinion_cam"
    assert row.receiver == "dt_pinion_lift_rod"
    assert row.quantity == 2
    assert row.exposure is Exposure.OSCILLATING
    assert row.lock is Lock.STAKED
    assert row.lock_step == spec.SET_SCREW_STAKE_STEP_KEY
    assert row.lock_binds == (row.member, row.receiver)
    assert jr.REQUIRED_JOINTS[row.id].anchor == row.lock_step


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
    second = dataclasses.replace(SCREW, id="pd-paper-drive/second-screw-in-base")
    required = {**REQUIRED, second.id: Occurrence("pd_paper_drive", "fixture", "")}
    assert _audit((*VALID, second), required=required) == []
    assert _kinds(_audit(VALID, required=required)) == {(second.id, Kind.OMITTED)}


@pytest.mark.parametrize(
    "gone",
    [
        "ha-harmonic-analyzer/spring-foot-screw-in-base",
        "ha-harmonic-analyzer/swing-stop-screw-in-base",
    ],
)
def test_shared_stock_does_not_merge_operational_foot_and_stop_joints(gone) -> None:
    ids = {
        "ha-harmonic-analyzer/spring-foot-screw-in-base",
        "ha-harmonic-analyzer/swing-stop-screw-in-base",
    }
    rows = tuple(joint for joint in jr.JOINTS if joint.id in ids)
    assert len(rows) == 2
    assert {joint.member for joint in rows} == {"sh_vn_fillister_screw_90280a108"}
    assert {joint.receiver for joint in rows} == {"fr_harmonic_base"}
    assert sum(joint.quantity for joint in rows) == 2
    assert all(joint.quantity == 1 for joint in rows)
    inventory = Inventory(
        {"ha_harmonic_analyzer": frozenset({rows[0].member, rows[0].receiver})}
    )
    findings = jr.audit(
        tuple(joint for joint in rows if joint.id != gone),
        inventory,
        threaded=frozenset({rows[0].member, rows[0].receiver}),
        unthreaded=frozenset(),
        required={joint.id: jr.REQUIRED_JOINTS[joint.id] for joint in rows},
    )
    assert _kinds(findings) == {(gone, Kind.OMITTED)}


def test_a_row_the_registry_does_not_list_is_unregistered() -> None:
    extra = dataclasses.replace(SCREW, id="pd-paper-drive/second-screw-in-base")
    assert _kinds(_audit((*VALID, extra))) == {(extra.id, Kind.UNREGISTERED)}
    # Registered under another assembly is not a match either.
    required = {**REQUIRED, SCREW.id: Occurrence("fr_frame", "fixture", "")}
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
    """Machinist review of 6c385465d: the free T24 rocks against the MHA-PD-13
    flange through its pin backlash, so the nut is an exposed joint; the
    user's U-MHA-PD-13-no-lock ruling (2026-10-03) waives it, with the backlash
    the specs give."""
    import math

    import pd_vn_transgear_knob_drive_pin_spec as pin
    import _sprocket_seat_geometry as wheel
    from _printed_tolerance import drilled_oversize_mm

    joint_id = "pd-paper-drive/thumbnut-on-knob-shaft"
    (row,) = [j for j in jr.JOINTS if j.id == joint_id]
    assert row.thread == "#8-32 UNC"
    assert row.installed_at == "collar-shoulder-seated"
    assert "D-flat -> shaft" in row.exposure_reason
    assert "actual F" in row.axial_capture
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


def test_the_knife_hanger_is_a_plain_clamp_keyed_by_its_two_dowels() -> None:
    """The cut #10-24 hex bolt clamps through a new SAE washer; the two
    pressed dowels react torque, so the static clamp takes no lock and no
    threadlocker (period hardware). The plain washer is not a thread lock."""
    (row,) = [j for j in jr.JOINTS if j.id == "sm-summing/knife-hanger-in-mount"]
    assert row.thread == "#10-24 UNC"
    assert row.exposure is Exposure.STATIC_CLAMP
    assert row.lock is Lock.NONE
    notes = jr._config.parts("sm-vn-knife-hanger-stud")["installation_notes"]
    assert "THREADLOCK" not in notes.upper()
    assert "sm_vn_knife_mount_dowel" in jr.UNTHREADED_PARTS
    assert jr.UNTHREADED_STOCK["sm_vn_knife_mount_dowel"] == (
        "dowel pin pressed into a blind reamed hole"
    )
    washer = "sm_vn_knife_hanger_washer"
    assert washer in jr.UNTHREADED_PARTS
    assert washer not in jr.THREADED_PARTS
    assert jr.UNTHREADED_STOCK[washer] == (
        "plain SAE washer under the knife-hanger hex head; no thread"
    )
    assert row.quantity == 2
    assert not row.lock_part and not row.lock_binds
    assert "two pressed MHA-SM-VN-53 dowels" in row.exposure_reason
    # Owner ruling 2026-10-24 (T+H3): the crossbar holds the press and the
    # block takes the slip.
    assert "held in the crossbar's underside reams" in row.exposure_reason
    assert "the block's round hole and slot" in row.exposure_reason
    assert "92314A253" in row.axial_capture
    assert "96659A104" in row.axial_capture
    assert "crossbar's faced top" in row.axial_capture
    assert "spotface" not in row.axial_capture
    # The length is cut at MHA-SM-00 to the measured stack, not banded on
    # the bolt or carried by the frame's grip band.
    assert "MHA-SM-00 step 4 cuts each bolt" in row.axial_capture
    assert "measured at its own hole plus .351 +/-.006 in" in row.axial_capture
    assert "46.70 +/-0.15" not in row.axial_capture
    assert "36.50 +/-0.05" not in row.axial_capture
    assert "HANGER_FIT_REACH" in row.evidence
    assert "HANGER_SPOTFACE" not in row.evidence
    assert "8.9173 nominal (8.763..9.0678 worst case)" in row.axial_capture
    assert "9.65 +/-0.13" in row.axial_capture
    assert "0.4910667 spare" in row.axial_capture
    assert "7.7046667 full engagement" in row.axial_capture
    assert "0.4522 minimum tip air" in row.axial_capture


def test_the_channel_apex_set_screws_are_staked_like_the_keeper_screws() -> None:
    """PR #1317 Codex review: the MHA-CH-VN-53 cups hold the rocked MHA-CH-05
    shaft, an exposed joint. Its Loctite 222 waiver was retired (2026-10-16,
    the user's standing no-threadlocker rule): each is snugged and its tap
    mouth staked at 2 points, as the fulcrum keeper set screws are."""
    import draw_ch_channel_assembly as channel

    joint_id = "ch-channel/pivot-bracket-apex-set-screw"
    (row,) = [j for j in jr.JOINTS if j.id == joint_id]
    assert row.exposure is Exposure.OSCILLATING
    assert row.lock is Lock.STAKED
    assert row.lock_step == row.installed_at == "set-screws-driven"
    assert row.exception == ""
    assert "U-MHA-CH-VN-53-channel-threadlocker" not in jr.RULINGS
    assert not [r for r in jr.RULINGS.values() if r.joint == joint_id]
    (keeper,) = [
        j for j in jr.JOINTS if j.id == "ch-channel/fulcrum-shaft-set-screw-in-keeper"
    ]
    assert keeper.lock is Lock.STAKED
    rocker_fitup, fulcrum_fitup, _hookup = (
        " ".join(n.split()) for n in channel.FITUP_NOTES
    )
    assert "SNUG, AND STAKE EACH TAP MOUTH AT 2 POINTS." in rocker_fitup
    assert "STAKE EACH TAP MOUTH AT 2 POINTS." in fulcrum_fitup
    for banned in ("LOCTITE", "THREADLOCK"):
        assert banned not in rocker_fitup.upper()
        assert banned not in row.evidence.upper()
    assert jr._config.parts("sh-vn-arbor-set-screw")["number"] not in fulcrum_fitup

    findings = jr.audit(
        jr.JOINTS,
        jr.build_inventory(),
        threaded=jr.THREADED_PARTS,
        unthreaded=jr.UNTHREADED_PARTS,
        purchased=jr.purchased_parts(),
        unthreaded_stock=jr.UNTHREADED_STOCK,
        required=jr.REQUIRED_JOINTS,
        rulings=jr.RULINGS,
    )
    assert joint_id not in {f.subject for f in findings if f.kind is Kind.UNLOCKED}


def test_the_gooseneck_set_screw_is_waived_only_by_its_ruling() -> None:
    """Q5 on PR #1348: the MHA-FR-VN-52 cup point is the gooseneck post's only
    retention, an oscillating joint with no jam nut. The user waived drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads)
    for it (2026-10-12): adjustable by design and re-set periodically."""
    joint_id = "ha-harmonic-analyzer/gooseneck-set-screw-in-top-frame"
    (row,) = [j for j in jr.JOINTS if j.id == joint_id]
    assert row.exposure is Exposure.OSCILLATING
    assert row.lock is Lock.NONE
    assert "91410A540" in row.evidence
    assert jr._config.parts("fr-vn-gooseneck-set-screw")["supplier_skus"] == ["91410A540"]
    ruling = jr.RULINGS[row.exception]
    assert ruling.joint == joint_id
    assert "adjustable by design, periodic re-set; user 2026-10-12" in ruling.granted

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
    assert joint_id not in {f.subject for f in jr.audit_table()}
    without = {k: v for k, v in jr.RULINGS.items() if k != row.exception}
    assert joint_id in unlocked(without)


def test_the_pen_rod_set_screw_is_waived_only_by_its_ruling() -> None:
    """PR #1436: the MHA-PN-VN-52 cup point is the v-block's only retention on
    the rod, an oscillating joint with no room for a jam screw. The user
    waived drawing-guidelines.md rule 23 for it (2026-10-14): an operator
    adjustment and light clamp, period-faithful and plain."""
    joint_id = "pn-pen/rod-set-screw-in-v-block"
    (row,) = [j for j in jr.JOINTS if j.id == joint_id]
    assert row.exposure is Exposure.OSCILLATING
    assert row.lock is Lock.NONE
    assert "91375A105" in row.evidence
    assert jr._config.parts("pn-vn-pen-rod-set-screw")["supplier_skus"] == ["91375A105"]
    ruling = jr.RULINGS[row.exception]
    assert ruling.joint == joint_id
    assert "2026-10-14" in ruling.granted and "PR #1436" in ruling.granted
    assert joint_id not in {f.subject for f in jr.audit_table()}
    without = {k: v for k, v in jr.RULINGS.items() if k != row.exception}
    findings = jr.audit(
        jr.JOINTS,
        jr.build_inventory(),
        threaded=jr.THREADED_PARTS,
        unthreaded=jr.UNTHREADED_PARTS,
        purchased=jr.purchased_parts(),
        unthreaded_stock=jr.UNTHREADED_STOCK,
        required=jr.REQUIRED_JOINTS,
        rulings=without,
    )
    assert (joint_id, Kind.UNLOCKED) in {(f.subject, f.kind) for f in findings}


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
    unkeyed = Inventory({"pd_paper_drive": PARTS})
    assert _audit(_with_stud(lock_step="SHEET 4 STEP 9"), unkeyed) == []
    assert _kinds(_audit(_with_stud(lock_step=""), unkeyed)) == {
        (STUD.id, Kind.LOCK_STEP_ABSENT)
    }


def test_hardware_the_drawings_call_for_but_no_assembly_places_is_reported() -> None:
    # The arm's set screw is drilled for but never modelled: the row is
    # reported as missing hardware (not as an unknown part) and, exposed with
    # no lock, as unlocked.
    set_screw = Joint(
        id="pd-paper-drive/arm-set-screw",
        assembly="pd_paper_drive",
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
    required = {**REQUIRED, set_screw.id: Occurrence("pd_paper_drive", "fixture", "")}
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
            "ch_channel": frozenset({"hook"}),
            "sm_summing": frozenset({"plate"}),
        },
        subassemblies={"top": frozenset({"ch_channel", "sm_summing"})},
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
    misfiled = dataclasses.replace(hook, assembly="ch_channel")
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
    # The cross screws' stems stay named without their base row:
    # frame_cross_screw as the top-frame row's member, harmonic_base as the
    # receiver of other frame rows. Only the registry notices the joint is gone.
    gone = "fr-frame/cross-screw-in-base"
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


def test_every_joint_the_table_names_places_its_hardware() -> None:
    # The last unplaced row (the pen v-block's rod set screw) became the
    # placed MHA-PN-VN-52; a new UNMODELLED row must be a deliberate change here.
    unmodelled = {
        f.subject for f in jr.audit_table() if f.kind is Kind.HARDWARE_UNMODELLED
    }
    assert unmodelled == set()


def test_per_channel_joints_follow_the_built_channel_count(monkeypatch) -> None:
    # A reduced build (machine/channels.yaml active_count) places fewer
    # channel anchors; the report must count what the build places.
    built = jr._config.active_count()
    before = jr.report([])["per_assembly"]["ha_harmonic_analyzer"]["instances"]
    per_channel = sum(
        j.quantity
        for j in jr.JOINTS
        if j.assembly == "ha_harmonic_analyzer" and j.per_channel
    )
    # Each channel anchor and its jam nut.
    assert per_channel == 2
    monkeypatch.setattr(jr._config, "active_count", lambda: 5)
    data = jr.report([])
    assert data["per_assembly"]["ha_harmonic_analyzer"]["instances"] == before - (
        per_channel * (built - 5)
    )
    for joint_id in (
        "ha-harmonic-analyzer/channel-anchor-in-summing-plate",
        "ha-harmonic-analyzer/channel-anchor-jam-nut-on-anchor",
    ):
        row = next(j for j in data["joints"] if j["id"] == joint_id)
        assert row["instances"] == 5


def test_channel_anchors_are_locked_by_their_jam_nuts() -> None:
    rows = {j.id: j for j in jr.JOINTS}
    anchor = rows["ha-harmonic-analyzer/channel-anchor-in-summing-plate"]
    assert anchor.exposure is Exposure.ADJUSTER
    assert anchor.lock is Lock.JAM_NUT
    assert anchor.lock_part == "ch_anchor_jam_nut"
    assert set(anchor.lock_binds) == {"ch_vn_spring_hook", "sm_summing_lever"}
    assert anchor.exception == ""
    nut = rows["ha-harmonic-analyzer/channel-anchor-jam-nut-on-anchor"]
    assert nut.member == "ch_anchor_jam_nut"
    assert nut.receiver == "ch_vn_spring_hook"
    assert nut.exposure is Exposure.STATIC_CLAMP
    for row in (anchor, nut):
        text = " ".join((row.axial_capture, row.evidence, row.exposure_reason))
        for banned in ("THREADLOCK", "LOCTITE", "NYLON", "NYLOC"):
            assert banned not in text.upper()


