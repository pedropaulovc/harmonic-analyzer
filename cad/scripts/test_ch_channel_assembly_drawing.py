"""Offline contract for the channel assembly drawing (MHA-CH-000)."""

from __future__ import annotations

import re
from pathlib import Path

from _assembly_contract import assembly_contract
import _config
import ch_channel_assembly_steps as steps
import draw_ch_channel_assembly as drawing
import dt_drive_train_steps
import pytest
import rocker_bank_layout as bank
from _drawing_registry import DRAWINGS_BY_NAME

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
# A drive-train or frame sequence head, sub-steps included ("9F. ").
ANY_STEP_HEAD = re.compile(r"^(\d+[A-Z]?)\. ", re.MULTILINE)
STEP_POINTER = re.compile(r"(MHA-[A-Z]{2}-000) STEP (\d+[A-Z]?)")
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d); #945 moves these into _drawing_common.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head."""
    text = drawing.FITUP_STEPS
    heads = list(STEP_HEAD.finditer(text))
    index = steps.step_number(key) - 1
    end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
    return " ".join(text[heads[index].end() : end].split())


def _sequence_steps(text: str) -> dict[str, str]:
    """Every step of a printed sequence: its head label to its joined text."""
    heads = list(ANY_STEP_HEAD.finditer(text))
    bodies = {}
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        assert head.group(1) not in bodies, f"step {head.group(1)} printed twice"
        bodies[head.group(1)] = " ".join(text[head.end() : end].split())
    return bodies




def test_channel_assembly_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["ch_channel_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "ch_channel"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 7.0)
    assert drawing.FRONT_CENTER == (0.060, 0.150)
    assert drawing.RIGHT_CENTER == (0.130, 0.150)
    assert drawing.ISO_CENTER == (0.225, 0.140)


def test_step_numbers_follow_the_sequence_and_unknown_steps_are_refused() -> None:
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_every_cross_sheet_step_pointer_lands_on_the_step_it_names() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRlAE): step 2 sent the fitter to an A03
    step that did not exist. The user ruled option A: an A03 step sets the
    north bracket by DRO, after MHA-FR-000 step 8 has screwed the support down.
    Each pointer must land on a printed step that does what it cites, and the
    A02 pointer is the A03 registry's, never a typed number."""
    import draw_dt_drive_train_assembly as drive_train
    import draw_fr_frame_assembly as frame

    bracket = _config.parts("ch-pivot-bracket")["number"]
    support = _config.parts("fr-rocker-arm-support")["number"]
    channel_number = assembly_contract("ch-channel").number
    fitup_number = assembly_contract("dt-drive-train").number
    frame_number = assembly_contract("fr-frame").number
    north_ref = (
        f"{fitup_number} STEP "
        f"{dt_drive_train_steps.step_number(steps.NORTH_BRACKET_SET_KEY)}"
    )
    stack_ref = (
        f"{fitup_number} STEP "
        f"{dt_drive_train_steps.step_number(steps.CYLINDER_STACK_KEY)}"
    )
    sheets = {
        channel_number: _sequence_steps(drawing.FITUP_STEPS),
        fitup_number: _sequence_steps(
            "\n".join(
                (
                    drive_train.CONE_CRANK_STEPS,
                    drive_train.BANK_STEPS,
                    drive_train.rig_steps(pivot_blocks=2, cams=2, slotted=4),
                )
            )
        ),
        frame_number: _sequence_steps(frame.ASSEMBLY_STEPS),
    }
    # What each pointer's target must name, keyed by (citing sheet, pointer).
    expected = {
        (channel_number, north_ref): f"THE NORTH {bracket}",
        # The rod rings go onto their cams in the cylinder stack, so the
        # bench-pinned rod + arm pairs must exist by then.
        (channel_number, stack_ref): "ON ITS CAM AS ITS GEAR GOES ON",
        # ... and that drive-train step names the pinning step it relies on.
        (fitup_number, steps.RODS_PINNED_REF): "ROD FORK TO ITS",
        (fitup_number, f"{frame_number} STEP 8"): f"{support} ON DECK",
        # The drive-train step that sets the north bracket keeps the miced
        # north washer for the channel sheet's threading of the shaft.
        (fitup_number, steps.step_ref("north-ear-datum")): "PUSH THE",
    }
    found = set()
    for sheet, bodies in sheets.items():
        for body in bodies.values():
            for pointer in STEP_POINTER.finditer(body):
                found.add((sheet, pointer.group(0)))
                target = sheets[pointer.group(1)][pointer.group(2)]
                assert expected[(sheet, pointer.group(0))] in target, pointer.group(0)
    assert found == set(expected)
    north_label = str(dt_drive_train_steps.step_number(steps.NORTH_BRACKET_SET_KEY))
    north = sheets[fitup_number][north_label]
    assert "EAR INNER FACE TO Y" in north and "DRO STILL ZEROED AS 9A" in north
    # The plain shaft threads through the set ear: the bracket stays down,
    # and the channel sheet threads the shaft and the miced washer from the
    # north.
    assert "LIFT IT OFF" not in north
    assert "MIC ONE MHA-CH-009, W" in north
    north_ear = _step_body("north-ear-datum")
    washer = _config.parts("ch-rocker-thrust-washer")["number"]
    assert "UNCUT END FIRST" in north_ear and "SOUTH THROUGH THE EAR" in north_ear
    assert f"ITS MICED {washer}" in north_ear
    # Positive control: the step before it is the bank's end play, not the ear.
    assert f"NORTH {bracket}" not in sheets[fitup_number]["9F"]
    # It follows 9F, the bank's last sub-step, on the bank sheet: the rig's
    # first step comes after it.
    labels = list(sheets[fitup_number])
    assert labels.index(north_label) == labels.index("9F") + 1
    # The rig's first step is whichever key the registry puts right after the
    # north bracket, so reordering the rig's own steps cannot break this.
    sequence = dt_drive_train_steps.SEQUENCE
    assert steps.NORTH_BRACKET_SET_KEY in sequence[:-1], (
        f"{steps.NORTH_BRACKET_SET_KEY!r} must be in "
        "drive_train_steps.SEQUENCE with a rig step after it"
    )
    rig_first_key = sequence[sequence.index(steps.NORTH_BRACKET_SET_KEY) + 1]
    rig_first = str(dt_drive_train_steps.step_number(rig_first_key))
    assert labels.index(rig_first) == labels.index(north_label) + 1


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    printed = [int(n) for n in STEP_HEAD.findall(drawing.FITUP_STEPS)]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))


def test_the_spring_set_and_its_preload_check_are_printed_from_the_layout() -> None:
    """#948 ruling R (PR #1292): the south bracket is set off the MHA-CH-009
    washer by the spring's set blade, beside the MHA-VN-053 spring, which is
    first run along the shaft (its catalogue ID can bind). Rule 6: the blade
    comes from rocker_bank_layout, never typed; the acceptance is the preload."""
    spring = _config.parts("vn-rocker-bank-spring")["number"]
    shaft = _config.parts("ch-pivot-shaft")["number"]
    setting = _step_body("south-bracket-spring-set")
    assert f"RUN A {spring} SPRING ALONG THE {shaft}; REJECT ONE THAT BINDS." in setting
    assert f"{bank.ROCKER_SPRING_SET:.2f} BLADE BESIDE THE SPRING" in setting
    assert "PULL THE BLADE" in setting
    accept = _step_body("preload-accepted")
    assert "PUSHED SOUTH," in accept
    assert "THE BANK SPRINGS BACK ONTO THE NORTH WASHER" in accept
    assert f"STEP {steps.step_number('south-bracket-spring-set')}" in accept
    stack = _step_body("rocker-stack-accepted")
    assert f"{bank.STACK_L20_ACCEPT[0]:.2f} TO {bank.STACK_L20_ACCEPT[1]:.2f}" in stack
    assert steps.NORTH_BRACKET_SET_REF in _step_body("north-ear-datum")
    # No feeler end play survives the ruling.
    assert "FEELER" not in drawing.FITUP_STEPS
    assert "END PLAY" not in drawing.FITUP_STEPS
    # Positive control: the spring is not what step 4 fits.
    assert spring not in _step_body("south-washer-fitted")




def test_the_step_block_fits_the_field_right_of_the_isometric() -> None:
    rocker, fulcrum = drawing.FITUP_NOTES
    assert drawing.FITUP_STEPS == f"{rocker}\n{fulcrum}"
    for note, (left, top), (right_limit, bottom_limit) in (
        (rocker, drawing.FITUP_NOTE_XY, drawing.FITUP_FIELD_LIMIT),
        (fulcrum, drawing.FULCRUM_NOTE_XY, drawing.FULCRUM_FIELD_LIMIT),
    ):
        lines = note.splitlines()
        assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < right_limit
        assert top - len(lines) * NOTE_LINE_PITCH > bottom_limit
    # The isometric's right edge sat at x ~0.248 on the v36 render; on the
    # v41 render the front and right views end at y ~0.079 and the title
    # block starts at x ~0.218.
    assert drawing.FITUP_NOTE_XY[0] > 0.248 + 0.015
    assert drawing.FULCRUM_NOTE_XY[1] < 0.079
    assert drawing.FULCRUM_FIELD_LIMIT[0] < 0.218
    assert rocker.startswith("ROCKER BANK FIT-UP\n1. ")
    assert fulcrum.startswith(
        f"FULCRUM SHAFT FIT-UP\n{steps.step_number(steps.KEEPERS_PAIR_REAMED_KEY)}. "
    )


def test_the_fulcrum_keepers_are_pair_reamed_set_by_dro_and_staked() -> None:
    """GPT review F5/F6 (PR #1311): the two keeper bores share one axis only
    if they are reamed as a pair; the pair is then set on the top frame by DRO
    with the shaft through both, and each crown tap's mouth is staked over its
    set screw (rule 9's lock). The keeper print points at these steps."""
    import ch_fulcrum_keeper_spec as keeper
    import draw_ch_fulcrum_keeper as keeper_drawing
    from channel_frame_geom import LEVER_FULCRUM_XY
    from frame_column_stations import COLUMN_X

    number = _config.parts("ch-fulcrum-keeper")["number"]
    fulcrum_shaft = _config.parts("ch-fulcrum-shaft")["number"]
    top_frame = _config.parts("fr-top-frame")["number"]
    assert steps.SEQUENCE[-3:] == drawing.FULCRUM_KEYS
    assert drawing.FULCRUM_KEYS == (
        steps.KEEPERS_PAIR_REAMED_KEY,
        steps.KEEPERS_SET_KEY,
        steps.SET_SCREWS_STAKED_KEY,
    )
    reamed = _step_body(steps.KEEPERS_PAIR_REAMED_KEY)
    assert f"CLAMP THE TWO {number} KEEPERS INNER LUG FACES TOGETHER" in reamed
    assert "DRILL AND REAM BOTH BORES IN ONE SETUP" in reamed
    assert "ROUND EACH CROWN ABOUT ITS OWN BORE" in reamed
    assert f"ACCEPT IF THE {fulcrum_shaft} SHAFT SLIDES THROUGH BOTH." in reamed
    places = keeper.KEEPER_FITUP_PLACES
    front, rear = keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    fitted = _step_body(steps.KEEPERS_SET_KEY)
    assert f"{top_frame} ON THE MILL:" in fitted
    # Main's ruling: X off the receiving web, Z off the upper-left socket.
    assert keeper.KEEPER_FITUP_X_FROM_WEB_MM == pytest.approx(
        LEVER_FULCRUM_XY[0] - COLUMN_X
    )
    x = f"{keeper.KEEPER_FITUP_X_FROM_WEB_MM:.{places}f}"
    assert f"{x} WEST OF THE RAIL WEB CENTRE BELOW IT" in fitted
    z = f"Z {front:.{places}f} AND {rear:.{places}f} FROM THE UPPER-LEFT SOCKET"
    assert z in fitted
    assert f"WITHIN {keeper.KEEPER_FITUP_LOCATION_BAND_MM:.{places}f}" in fitted
    assert "TRANSFER EACH FOOT HOLE INTO THE RAIL" in fitted
    staked = _step_body(steps.SET_SCREWS_STAKED_KEY)
    assert "STAKE EACH TAP MOUTH AT 2 POINTS" in staked
    # The keeper print cites these steps by key.
    assert keeper_drawing.DIMENSION_CALLOUTS["BoreDia"].endswith(
        f"PER {steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)}"
    )
    assert keeper_drawing.DIMENSION_CALLOUTS["CrownDia"].endswith(
        f"PER {steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)}"
    )
    staking = steps.step_ref(steps.SET_SCREWS_STAKED_KEY)
    assert staking in keeper_drawing.SET_SCREW_PROCESS


def test_each_rod_fork_is_pinned_to_its_arm_at_the_bench_first() -> None:
    """The rod ring is captured in its closed cam slot during the cylinder
    stack, and a pressed pin needs its far tine backed on the press, so the
    MHA-CH-010 pin goes in at the bench, before that drive-train step -- after
    the hub stack is proved on the shaft and the rockers come off in order.
    User ruling 2026-10-09 (PR #1292 review F1): pressed, ends dressed flush,
    removable with a punch, as the MHA-CH-011 bar pin."""
    from ch_rod_pivot_pin_spec import PIN_END_PROUD_MAX

    assert steps.SEQUENCE[:2] == ("rocker-stack-accepted", steps.RODS_PINNED_KEY)
    stack = _step_body("rocker-stack-accepted")
    assert stack.endswith("SLIDE THE ROCKERS OFF IN ORDER AND KEEP THAT ORDER.")
    body = _step_body(steps.RODS_PINNED_KEY)
    rod = _config.parts("ch-connecting-rod")["number"]
    arm = _config.parts("ch-rocker-arm")["number"]
    pin = _config.parts("ch-rod-pivot-pin")["number"]
    assert f"BEFORE {steps.CYLINDER_STACK_REF}, AT THE BENCH:" in body
    assert f"EACH {rod} ROD FORK TO ITS {arm} ARM WITH ONE {pin}." in body
    assert "PRESS IT IN, FAR TINE BACKED; DRESS BOTH ENDS FLUSH." in body
    assert PIN_END_PROUD_MAX == 0.0  # what "FLUSH" states
    # Removal is a property of the pin, not a step: the later steps need the
    # pin in place (CodeRabbit, PR #1292).
    assert "PIN REMOVABLE WITH PUNCH." in body
    assert "DRIVE OUT" not in body
    assert "SWINGS FREE UNDER ITS OWN WEIGHT" in body
    assert "PEEN" not in drawing.FITUP_STEPS
    assert "COUNTERSINK" not in drawing.FITUP_STEPS
    # Positive control: no other step pins or presses.
    for key in steps.SEQUENCE:
        if key != steps.RODS_PINNED_KEY:
            assert pin not in _step_body(key) and "PRESS" not in _step_body(key)



def test_the_shaft_supplied_long_is_cut_to_fit_before_the_preload_is_accepted() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mSteE): MHA-CH-005 is supplied long with its
    plain end uncut, and its print defers the length to the assembly, but no
    step cut it. A step between the south bracket's setting and the preload
    acceptance must scribe the shaft at the ear, take it out, and cut and dome
    it to the layout's band."""
    import ch_pivot_shaft_spec as shaft

    # The part's promise this sheet has to keep.
    assert "PLAIN END UNCUT" in shaft.DRAWING_NOTES
    assert shaft.LENGTH_CALLOUT.startswith("CUT TO FIT")
    cut_steps = [key for key in steps.SEQUENCE if "PLAIN END" in _step_body(key)]
    assert len(cut_steps) == 1
    (key,) = cut_steps
    number = steps.step_number(key)
    assert steps.step_number("south-bracket-spring-set") < number
    assert number < steps.step_number("preload-accepted")
    body = _step_body(key)
    upper, lower = bank.PLAIN_END_CUT_BAND
    cut = f"{shaft.DOME_HEIGHT + lower:.1f} TO {shaft.DOME_HEIGHT + upper:.1f}"
    assert f"CUT THE PLAIN END {cut} PAST THE SCRIBE" in body
    assert f"DOME IT {shaft.DOME_HEIGHT:.1f}" in body
    assert "SCRIBE" in body.split("CUT")[0] and "SOUTH EAR'S OUTER FACE" in body
    # The pinned rods hold the arms at their stations: the plain shaft comes
    # out northward through the set north ear and goes back by the threading
    # of the north-ear step, the south bracket staying down at its spring
    # setting.
    assert "NORTH END FLUSH WITH ITS EAR" in body.split("SCRIBE")[0]
    assert "DRAW IT OUT NORTH" in body and "UNSCREW THE NORTH" not in body
    assert "EACH ARM LEFT HANGING ON ITS ROD" in body
    # The refit re-threads the washers and spring the draw-out caught.
    assert (
        f"REFIT AS STEP {steps.step_number('north-ear-datum')}, WASHERS AND SPRING"
        " IN PLACE;"
    ) in body
    assert f"SOUTH EAR AT ITS STEP {steps.step_number('south-bracket-spring-set')} SETTING" in body
    assert "CATCH WASHERS AND SPRING" in body
    assert "UNSCREW THE SOUTH" not in body
    # Positive control: no other step mentions the cut.
    assert "SCRIBE" not in _step_body("south-bracket-spring-set")


def test_the_set_screws_go_in_after_the_cut_and_print_the_engagement_fact() -> None:
    """User, 2026-10-10: one MHA-VN-034 down each ear's apex tap onto the
    plain shaft's flat, once the shaft is cut and refitted, before the preload
    is accepted. The step prints the bracket spec's engagement fact, the
    named exception, from the spec, never typed."""
    import ch_pivot_bracket_spec as bracket_spec

    set_screw = _config.parts("vn-arbor-set-screw")["number"]
    key = "set-screws-driven"
    number = steps.step_number(key)
    assert steps.step_number("shaft-cut-to-fit") < number
    assert number < steps.step_number("preload-accepted")
    body = _step_body(key)
    assert f"RUN ONE {set_screw} DOWN EACH APEX TAP ONTO ITS FLAT" in body
    assert "FLATS UP" in body and "NORTH FIRST" in body
    assert body.endswith(" ".join(bracket_spec.SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT.split()))
    # Positive control: no other step fits the set screws or prints the fact.
    for other in steps.SEQUENCE:
        if other != key:
            assert set_screw not in _step_body(other)
    assert drawing.FITUP_STEPS.count("ENGAGEMENT") == 1
    source = Path(drawing.__file__).read_text(encoding="utf-8").splitlines()
    emit = next(
        i for i, line in enumerate(source) if "{SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT}" in line
    )
    assert source[emit - 1].strip() == (
        "# Named exception: MHA-CH-008 set-screw engagement "
        '(drawing-simplicity-policy.md, "Named exceptions").'
    )


def test_the_set_screw_interference_allowance_is_the_ear_tap() -> None:
    """_interference_contracts restates the ear's arch radius and bore as
    literals (every assembly imports it); they must be the bracket spec's,
    and the screws' thread its apex tap's."""
    import _interference_contracts as ic
    import ch_pivot_bracket_spec as bracket_spec
    import vn_arbor_set_screw_spec as screw_spec

    assert ic.PIVOT_EAR_ARCH_AND_BORE == (bracket_spec.EAR_ARCH_R, bracket_spec.BORE_DIA)
    assert screw_spec.THREAD == bracket_spec.SET_SCREW_THREAD
    pairs = ic.allowed_interference_pairs("ch-channel")
    for n in (1, 2):
        pair = frozenset((f"vn-arbor-set-screw-{n}", f"ch-pivot-bracket-{n}"))
        assert pairs[pair] == ic.PIVOT_EAR_SET_SCREW_LIMIT
