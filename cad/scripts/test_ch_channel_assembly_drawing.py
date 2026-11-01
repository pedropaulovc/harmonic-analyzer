"""Offline contract for the channel assembly drawing (MHA-CH-00)."""

from __future__ import annotations

import math
from pathlib import Path
import re

import _buildgraph
from _assembly_contract import assembly_contract
import _config
import ch_channel_assembly_steps as steps
import draw_ch_channel_assembly as drawing
import dt_drive_train_steps
from ch_rocker_arm_spec import HUB_LENGTH, HUB_LENGTH_BAND
import pytest
import rocker_bank_layout as bank
from _drawing_registry import DRAWINGS_BY_NAME

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
# A drive-train or frame sequence head, sub-steps included ("9F. ").
ANY_STEP_HEAD = re.compile(r"^(\d+[A-Z]?)\. ", re.MULTILINE)
STEP_POINTER = re.compile(r"(MHA-[A-Z]{2}-00)\b STEP (\d+[A-Z]?)")
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d); #945 moves these into _drawing_common.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head or the
    end of its sheet's block (never into the next sheet's heading)."""
    number = steps.step_number(key)
    for block in drawing.FITUP_NOTES:
        heads = list(STEP_HEAD.finditer(block))
        for index, head in enumerate(heads):
            if int(head.group(1)) == number:
                end = heads[index + 1].start() if index + 1 < len(heads) else len(block)
                return " ".join(block[head.end() : end].split())
    raise KeyError(key)


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
    assert drawing.SHEET_SCALES[drawing.SHEET_NAMES[0]] == (1.0, 5.0)
    assert drawing.ASSEMBLED_ISO_SCALE == drawing.SHEET_SCALE
    assert drawing.FRONT_CENTER == (0.075, 0.140)
    assert drawing.RIGHT_CENTER == (0.185, 0.140)
    assert drawing.ISO_CENTER == (0.320, 0.150)
    # Front and Right in projection: one centre line.
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]
    assert drawing.ISO_LABEL == "ISOMETRIC\nSCALE 1 : 7"


def test_step_numbers_follow_the_sequence_and_unknown_steps_are_refused() -> None:
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_every_cross_sheet_step_pointer_lands_on_the_step_it_names() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRlAE): step 2 sent the fitter to an A03
    step that did not exist. The user ruled option A: an A03 step sets the
    north bracket by DRO, after MHA-FR-00 step 8 has screwed the support down.
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
    # MHA-HA-00's sequence is not on this branch's base: its one pointer is
    # checked by value against steps.HA_ANCHORS_SET_REF instead.
    foreign = set()
    for sheet, bodies in sheets.items():
        for body in bodies.values():
            for pointer in STEP_POINTER.finditer(body):
                if pointer.group(1) not in sheets:
                    foreign.add((sheet, pointer.group(0)))
                    continue
                found.add((sheet, pointer.group(0)))
                target = sheets[pointer.group(1)][pointer.group(2)]
                assert expected[(sheet, pointer.group(0))] in target, pointer.group(0)
    assert found == set(expected)
    assert foreign == {(channel_number, steps.HA_ANCHORS_SET_REF)}
    north_label = str(dt_drive_train_steps.step_number(steps.NORTH_BRACKET_SET_KEY))
    north = sheets[fitup_number][north_label]
    assert "EAR INNER FACE TO Y" in north and "DRO STILL ZEROED AS 9A" in north
    # The plain shaft threads through the set ear: the bracket stays down,
    # and the channel sheet threads the shaft and the washer measured there
    # from the north.
    assert "LIFT IT OFF" not in north
    assert "MIC THE MHA-CH-VN-56, W" in north
    north_ear = _step_body("north-ear-datum")
    washer = _config.parts("ch-vn-rocker-thrust-washer")["number"]
    assert "FLATS UP" in north_ear and "SOUTH THROUGH THE EAR" in north_ear
    # Machinist review (PR #1605): "MICED AND KEPT" read as a second, unstated
    # measurement; the washer is the one measured at the drive-train step.
    assert f"THE {washer} WASHER MEASURED AT THAT STEP, THEN HUBS" in north_ear
    assert "MICED" not in north_ear
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
    assert len(steps.SEQUENCE) == 14
    assert steps.SEQUENCE[4:] == (
        "south-bracket-spring-set",
        "south-bracket-screwed",
        "shaft-set",
        "set-screws-driven",
        steps.KEEPERS_PAIR_REAMED_KEY,
        steps.KEEPERS_SET_KEY,
        steps.BARS_PINNED_KEY,
        steps.LEVER_BANK_THREADED_KEY,
        steps.SET_SCREWS_STAKED_KEY,
        steps.SPRINGS_HOOKED_KEY,
    )


def test_the_spring_set_and_its_preload_check_are_printed_from_the_layout() -> None:
    """#948 ruling R (PR #1292): the south bracket is set off the MHA-CH-VN-56
    washer by the spring's set blade, beside the MHA-CH-VN-54 spring, which is
    first run along the shaft (its catalogue ID can bind). drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the blade
    comes from rocker_bank_layout, never typed; the acceptance is the preload."""
    spring = _config.parts("ch-vn-rocker-bank-spring")["number"]
    shaft = _config.parts("ch-pivot-shaft")["number"]
    setting = _step_body("south-bracket-spring-set")
    assert f"RUN A {spring} SPRING ALONG THE {shaft}; REJECT ONE THAT BINDS." in setting
    assert "SPRING-SET BLADE (DETAIL A) BESIDE THE SPRING" in setting
    # Machinist review (PR #1605): the spring-back check is run while the
    # bracket is only clamped, so "repeat" re-sets a bracket that can still
    # move; it used to follow the drilled, tapped, screwed and staked step.
    assert "CLAMP AND PULL THE BLADE. ACCEPT: PUSHED SOUTH," in setting
    assert "THE BANK SPRINGS BACK ONTO THE NORTH WASHER" in setting
    assert "ELSE UNCLAMP AND REPEAT THIS STEP." in setting
    support = _config.parts("fr-rocker-arm-support")["number"]
    hold_down = _config.parts("ch-vn-bracket-hold-down-screw")["number"]
    bracket = _config.parts("ch-pivot-bracket")["number"]
    assert support not in setting and hold_down not in setting
    # r10 machinist review: worded as step 10's keeper transfer.
    screwed = _step_body("south-bracket-screwed")
    assert screwed.startswith("STILL CLAMPED AS ACCEPTED, ")
    assert (
        f"TRANSFER THE SOUTH {bracket} FOOT HOLE INTO THE {support} RAIL, TAP AS "
        f"{support}, SCREW DOWN ONE {hold_down}."
    ) in screwed
    # Screwed down only after the check passes, and before anything staked.
    assert (
        steps.step_number("south-bracket-spring-set") + 1
        == steps.step_number("south-bracket-screwed")
        < steps.step_number("set-screws-driven")
    )
    stack = _step_body("rocker-stack-accepted")
    assert "TO THE ROCKER BANK VIEW'S STACK DIMENSION" in stack
    # The numbers live in the model dimensions, never in the step text.
    assert f"{bank.ROCKER_SPRING_SET:.2f}" not in setting
    assert f"{bank.STACK_L20_ACCEPT[0]:.2f}" not in stack
    assert steps.NORTH_BRACKET_SET_REF in _step_body("north-ear-datum")
    # No feeler end play survives the ruling.
    assert "FEELER" not in drawing.FITUP_STEPS
    assert "END PLAY" not in drawing.FITUP_STEPS
    # Positive control: the spring is not what step 4 fits.
    assert spring not in _step_body("south-washer-fitted")


def test_the_stack_step_says_which_way_and_where_to_re_face() -> None:
    """Machinist review (PR #1605): "RE-FACE A LONG STACK" left a short stack
    and the face to cut open. The hub band is upper-only, so the shortest
    stack meets the acceptance's low limit, and the re-face is on the south
    faces, never the datum face the strap is dimensioned from."""
    arm = _config.parts("ch-rocker-arm")["number"]
    assert HUB_LENGTH_BAND[1] == 0.0
    assert bank.COUNT * (HUB_LENGTH + HUB_LENGTH_BAND[1]) >= bank.STACK_L20_ACCEPT[0] - 1e-9
    stack = _step_body("rocker-stack-accepted")
    assert (
        f"EVERY {arm} HUB COMES AT OR OVER PRINT LENGTH, SO THE STACK IS NEVER "
        "SHORT. RE-FACE A LONG STACK ON THE SOUTH FACES OF THE LONGEST HUBS AS "
        "STACKED, NEVER THE DATUM FACE, NO HUB UNDER PRINT LENGTH."
    ) in stack
    assert f"{HUB_LENGTH:.2f}" not in stack




def test_each_step_block_fits_the_field_right_of_its_bank_view() -> None:
    rocker, lever, lever_continued = drawing.FITUP_NOTES
    assert drawing.FITUP_STEPS == f"{rocker}\n{lever}\n{lever_continued}"
    template = drawing._TEMPLATE
    left, top = drawing.STEPS_XY
    for note in (rocker, lever, lever_continued):
        lines = note.splitlines()
        assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < (
            template.width_m - drawing.BORDER
        )
        assert top - len(lines) * NOTE_LINE_PITCH > template.title_block_top_m
        assert top < template.height_m - drawing.BORDER
    # Each 1:1 bank's ends (the keeper and ear outer faces) clear the block.
    for view, south_z in (
        (drawing.ROCKER_BANK, -80.4589 - 2.0),
        (drawing.LEVER_BANK, drawing.asm.LUG_INNER_FACE_Z[0] - 10.0),
    ):
        assert view.sheet_xy(south_z, 0.0)[0] < left - 0.010
    assert rocker.startswith("ROCKER BANK FIT-UP\n1. ")
    assert lever.startswith(
        f"LEVER BANK FIT-UP\n{steps.step_number(steps.KEEPERS_PAIR_REAMED_KEY)}. "
    )
    assert lever_continued.startswith(
        f"LEVER BANK FIT-UP (CONT.)\n{steps.step_number(steps.SPRINGS_HOOKED_KEY)}. "
    )
    assert "TIGHTEN" not in rocker
    assert "TIGHTEN" in lever and "STAKE" in lever
    assert _config.parts("sh-vn-arbor-set-screw")["number"] not in lever
    # The sheet-5 view's outline (model x 7.4-217.1, y 955.6-1078.6 on the
    # 06616793e farm leaf) sits under its step block, above the title block
    # and inside the border.
    hookup = drawing.HOOKUP
    cx, cy, _ = hookup.centre_xyz
    x0, x1 = (hookup.centre[0] + (x - cx) * hookup.mm for x in (7.4, 217.1))
    y0, y1 = (hookup.centre[1] + (y - cy) * hookup.mm for y in (955.6, 1078.6))
    steps_bottom = top - len(lever_continued.splitlines()) * NOTE_LINE_PITCH
    assert drawing.BORDER < x0 and x1 < template.width_m - drawing.BORDER
    assert template.title_block_top_m + 0.010 < y0 and y1 < steps_bottom - 0.010


def test_steps_are_one_blank_line_apart_and_never_split() -> None:
    """User request: a blank line between consecutive steps; none before
    step 1 of a block, none inside a step."""
    for block in drawing.FITUP_NOTES:
        lines = block.splitlines()
        heads = [i for i, line in enumerate(lines) if STEP_HEAD.match(line)]
        assert heads[0] == 1
        for previous, head in zip(heads, heads[1:]):
            assert lines[head - 1] == ""
            assert "" not in lines[previous : head - 1]
        assert "" not in lines[heads[-1] :]


def test_the_package_sheets_and_settings_contract() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED VIEWS",
        "EXPLODED VIEW + BOM",
        "ROCKER BANK FIT-UP",
        "LEVER BANK FIT-UP",
        "LEVER BANK FIT-UP (CONT.)",
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    asm = drawing.asm
    explode = drawing.explode
    kept = {
        **drawing.STACK_KEEP,
        **drawing.SPRING_KEEP,
        **drawing.LUG_KEEP,
        **drawing.PLAN_KEEP,
    }
    assert sorted(kept) == sorted(asm.DIMENSION_FEATURE)
    # Each bank view shows only its own axis's sketch.
    assert {asm.DIMENSION_FEATURE[name] for name in drawing.LUG_KEEP} == {
        asm.FULCRUM_FEATURE
    }
    assert {
        asm.DIMENSION_FEATURE[name] for name in (*drawing.STACK_KEEP, *drawing.SPRING_KEEP)
    } == {asm.PIVOT_FEATURE}
    assert {asm.DIMENSION_FEATURE[name] for name in drawing.PLAN_KEEP} == {
        asm.KEEPER_PLAN_FEATURE
    }
    assert set(drawing.notes.DIMENSION_CALLOUTS) == set(kept)
    assert drawing.notes.REFERENCE_DIMENSIONS == {asm.LUG_SPAN_DIMENSION}
    assert set(asm.DIMENSION_TOLERANCES) == set(kept) - drawing.notes.REFERENCE_DIMENSIONS
    lower, upper = asm.DIMENSION_TOLERANCES[asm.SPRING_SET_DIMENSION]
    assert (lower, upper) == (-bank.ROCKER_SPRING_SET_BAND, bank.ROCKER_SPRING_SET_BAND)
    # Every kept dimension text lands on its own sheet, inside the border.
    for x, y in kept.values():
        assert drawing.BORDER < x < drawing.STEPS_XY[0]
        assert drawing.BORDER < y < drawing._TEMPLATE.height_m - drawing.BORDER
    # The south-end detail's spring-set text sits above its crop circle,
    # clear of the arc (r7 layout audit: inside it, the arc crossed the text).
    detail = drawing.SOUTH_END
    x, y = drawing.SPRING_KEEP[asm.SPRING_SET_DIMENSION]
    radius = detail.crop_radius_mm * detail.mm
    assert y > detail.centre[1] + radius
    # ...and wholly south of the ear-side extension line (b9ae review: centred
    # on the gap, the text sat on its own dimension and extension lines).
    ear_x, _ = detail.sheet_xy(asm.PIVOT_CHAIN_Z[0], 0.0)
    callout = drawing.notes.DIMENSION_CALLOUTS[asm.SPRING_SET_DIMENSION]
    assert x - len(callout) * NOTE_CHAR_WIDTH / 2.0 > ear_x
    # Detail A names the four bodies its caption lists, each pointer tip
    # inside the crop circle and each text outside it.
    assert [text.split()[0] for text, _, _ in drawing.DETAIL_POINTERS] == [
        drawing.BOM_PART_NUMBERS[stem]
        for stem in ("ch-rocker-arm", explode.WASHER, explode.BANK_SPRING, explode.BRACKET)
    ]
    for text, (tx, ty), (px, py) in drawing.DETAIL_POINTERS:
        assert (px - detail.centre[0]) ** 2 + (py - detail.centre[1]) ** 2 < radius**2
        lines = text.splitlines()
        width = max(map(len, lines)) * NOTE_CHAR_WIDTH
        bottom = ty - len(lines) * NOTE_LINE_PITCH
        near_x = min(max(detail.centre[0], tx), tx + width)
        near_y = min(max(detail.centre[1], bottom), ty)
        assert math.dist((near_x, near_y), detail.centre) > radius
        assert drawing.BORDER < tx and tx + width < drawing.STEPS_XY[0]
        assert ty < y - NOTE_LINE_PITCH
    # The parent rocker-bank view carries the detail's boundary, about the
    # same model point the detail is centred on, lettered outside it; the
    # detail's title and step 5 cite the same letter.
    (cx, cy), parent_radius = drawing.detail_boundary(drawing.ROCKER_BANK, detail)
    assert (cx, cy) == drawing.ROCKER_BANK.sheet_xy(
        detail.centre_xyz[2], detail.centre_xyz[1]
    )
    assert parent_radius == detail.crop_radius_mm / 1000.0
    lx, ly = drawing.letter_xy((cx, cy), parent_radius)
    assert (lx - cx) ** 2 + (ly - cy) ** 2 > parent_radius**2
    assert drawing.BORDER < lx < drawing.STEPS_XY[0]
    assert detail.letter == drawing.DETAIL_LETTER
    assert detail.title.startswith(f"DETAIL {drawing.DETAIL_LETTER},")
    assert f"(DETAIL {drawing.DETAIL_LETTER})" in _step_body("south-bracket-spring-set")


def _iso(point: tuple[float, float, float]) -> tuple[float, float]:
    """The *Isometric projection (eye on +x +y +z), model mm on the view."""
    x, y, z = point
    return (x - z) * 0.5**0.5, (2.0 * y - x - z) / 6.0**0.5


def test_the_exploded_details_enlarge_the_north_hardware_beside_the_bom() -> None:
    explode = drawing.explode
    north = "north"
    lug_z = drawing.FULCRUM_KEEPER_CENTRE_Z + drawing.KEEPER_Z_OFF
    # 60 north, then the whole north-end cluster 30 further north and 570 up,
    # clear of the hanging rocker arms (r10 machinist review, DETAIL B), and
    # (r11) between the bank and the north-most channel pulled out of it.
    assert drawing.exploded_offset(explode.BRACKET, north) == (0.0, 570.0, 90.0)
    assert drawing.exploded_offset(explode.BRACKET_SET_SCREW, north) == (0.0, 595.0, 90.0)
    assert drawing.exploded_offset(explode.WASHER, north) == (0.0, 570.0, 50.0)
    assert drawing.exploded_offset(explode.KEEPER_FOOT_SCREW, north) == (0.0, 50.0, 50.0)
    assert drawing.exploded_offset(explode.BRACKET_HOLD_DOWN, north) == (0.0, 630.0, 90.0)
    assert drawing.exploded_offset(explode.BRACKET, "south") == (0.0, 0.0, -60.0)
    bracket, keeper = drawing.NORTH_BRACKET_DETAIL, drawing.NORTH_KEEPER_DETAIL
    assert drawing.EXPLODED_DETAILS == (bracket, keeper)
    # #1660 r3 (rule 22): lifted, the cluster read as the lever bank's, so an
    # explode trail runs from the bracket's seat on the rocker shaft, north
    # along its axis, then up to DETAIL B's centre (its exploded bore).
    seat, along, lifted = drawing.north_end_trail_mm()
    assert seat == (*drawing.ROCKER_PIVOT_XY, bank.PIVOT_BRACKET_Z[1])
    assert along == (*drawing.ROCKER_PIVOT_XY, seat[2] + 90.0)
    assert lifted == pytest.approx(bracket.centre_xyz)
    assert (drawing.TRAIL_LINE_STYLE, drawing.TRAIL_COLOR) == (2, 0)
    # Machinist review (PR #1605): at the upper right the letter B sat over
    # the rocker bank's stack beside the circle; the lower left is open.
    assert bracket.letter_corner == (-1, -1)
    # Each cluster member's exploded reference point projects inside its
    # circle with room for the part round it: the washer (Ø10.2), the set
    # screw above the ear apex, the hold-down over its foot hole.
    pivot_x, pivot_y = drawing.ROCKER_PIVOT_XY
    ear_z = bank.PIVOT_BRACKET_Z[1]
    washer_z = sum(bank.NORTH_WASHER_Z) / 2.0
    members = {
        bracket: (
            drawing._exploded((pivot_x, pivot_y, washer_z), explode.WASHER, north),
            drawing._exploded(
                (pivot_x, pivot_y + 15.0, ear_z), explode.BRACKET_SET_SCREW, north
            ),
            drawing._exploded(
                (pivot_x, pivot_y - 15.0, ear_z + 8.0), explode.BRACKET_HOLD_DOWN, north
            ),
        ),
        keeper: (
            drawing._exploded(
                (keeper.centre_xyz[0], drawing.LEVER_FULCRUM_XY[1] + 10.0, lug_z),
                explode.KEEPER_SET_SCREW,
                north,
            ),
            drawing._exploded(
                (keeper.centre_xyz[0], drawing.LEVER_FULCRUM_XY[1] - 20.0, lug_z + 8.5),
                explode.KEEPER_FOOT_SCREW,
                north,
            ),
        ),
    }
    for detail, points in members.items():
        assert detail.orientation == "*Isometric" and detail.exploded
        assert detail.title == f"DETAIL {detail.letter}"
        cu, cv = _iso(detail.centre_xyz)
        for point in points:
            u, v = _iso(point)
            assert ((u - cu) ** 2 + (v - cv) ** 2) ** 0.5 < detail.crop_radius_mm - 5.0
    # The column right of the BOM, inside the border and above the title
    # block, the circles apart and each label (under its circle) inside it.
    template = drawing._TEMPLATE
    bom_right = drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values())
    right = template.width_m - drawing.BORDER
    previous_bottom = template.height_m - drawing.BORDER
    for detail in drawing.EXPLODED_DETAILS:
        (x, y), radius = detail.centre, detail.crop_radius_mm * detail.mm
        assert bom_right + 0.004 < x - radius and x + radius < right
        assert y + radius < previous_bottom
        lines = detail.label_text.splitlines()
        lx, ly = detail.crop_label_xy
        assert lx + max(map(len, lines)) * NOTE_CHAR_WIDTH < right
        previous_bottom = ly - len(lines) * NOTE_LINE_PITCH
    assert previous_bottom > template.title_block_top_m


class _CaptionAnnotation:
    def __init__(self, position: tuple[float, ...]) -> None:
        self.position = position

    def GetPosition(self) -> tuple[float, ...]:
        return self.position


class _CaptionTable:
    def __init__(
        self,
        heights: tuple[float, ...],
        position: tuple[float, ...] = (0.205, 0.250, 0.0),
    ) -> None:
        self.heights = heights
        self.annotation = _CaptionAnnotation(position)
        self.RowCount = len(heights)

    def GetAnnotation(self) -> _CaptionAnnotation:
        return self.annotation

    def GetRowHeight(self, row: int) -> float:
        return self.heights[row]


class _CaptionNote:
    def __init__(self, extent: tuple[float, ...]) -> None:
        self.extent = extent

    def GetExtent(self) -> tuple[float, ...]:
        return self.extent


@pytest.fixture
def native_caption_geometry(monkeypatch) -> None:
    """Exercise native geometry guards without a SolidWorks seat."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda adapter, name: None)


def test_native_bom_limits_use_its_actual_position_and_each_row_height(
    native_caption_geometry,
) -> None:
    table = _CaptionTable((0.005, 0.009, 0.013), (0.180, 0.240, 0.002))
    assert drawing._bom_vertical_limits(table) == pytest.approx((0.213, 0.240))


def test_caption_tracks_native_bom_growth_from_wrapped_rows(
    native_caption_geometry,
) -> None:
    heights = (0.0065,) * 20
    short = _CaptionTable(heights, (*drawing.BOM_ANCHOR, 0.0))
    wrapped_heights = list(heights)
    wrapped_heights[17] = 0.019
    wrapped_heights[18] = 0.019
    wrapped = _CaptionTable(tuple(wrapped_heights), (*drawing.BOM_ANCHOR, 0.0))

    short_bottom, short_top = drawing._bom_vertical_limits(short)
    wrapped_bottom, wrapped_top = drawing._bom_vertical_limits(wrapped)
    growth = sum(wrapped_heights) - sum(heights)
    assert (short_bottom, short_top) == pytest.approx(
        (drawing.BOM_ANCHOR[1] - sum(heights), drawing.BOM_ANCHOR[1])
    )
    assert wrapped_top == pytest.approx(short_top)
    assert wrapped_bottom == pytest.approx(short_bottom - growth)
    short_xy = drawing.exploded_caption_xy(short_bottom)
    wrapped_xy = drawing.exploded_caption_xy(wrapped_bottom)
    assert short_xy == pytest.approx((drawing.BOM_ANCHOR[0], short_bottom - 0.006))
    assert wrapped_xy == pytest.approx(
        (drawing.BOM_ANCHOR[0], wrapped_bottom - 0.006)
    )
    assert short_xy[1] - wrapped_xy[1] == pytest.approx(growth)


@pytest.mark.parametrize(
    "heights",
    [
        (),
        (0.0,),
        (-0.001,),
        (math.nan,),
        (math.inf,),
        (-math.inf,),
        (0.006, 0.0, 0.006),
        (0.006, -0.001, 0.006),
        (0.006, math.nan, 0.006),
    ],
)
def test_native_bom_refuses_missing_or_invalid_row_heights(
    native_caption_geometry, heights,
) -> None:
    with pytest.raises(RuntimeError):
        drawing._bom_vertical_limits(_CaptionTable(heights))


@pytest.mark.parametrize(
    "position",
    [
        (),
        (0.205, 0.250),
        (0.205, 0.250, 0.0, 0.0),
        (math.nan, 0.250, 0.0),
        (0.205, math.inf, 0.0),
        (0.205, 0.250, -math.inf),
    ],
)
def test_native_bom_refuses_invalid_annotation_positions(
    native_caption_geometry, position,
) -> None:
    with pytest.raises(RuntimeError):
        drawing._bom_vertical_limits(_CaptionTable((0.006,), position))


@pytest.mark.parametrize("gap", [-0.0200011, -0.001, 0.0, 0.003, 0.003999])
def test_caption_refuses_native_bom_overlap_or_under_four_mm_clearance(
    native_caption_geometry, gap,
) -> None:
    table = _CaptionTable((0.0625, 0.0625))
    # The native BOM bottom is 0.125 m; use the note's actual upper edge,
    # not its insertion point or a text-height estimate.
    top = 0.125 - gap
    note = _CaptionNote((0.205, top - 0.009, 0.0, 0.285, top, 0.0))
    with pytest.raises(RuntimeError):
        drawing._assert_exploded_caption(object(), table, note)


@pytest.mark.parametrize("gap", [0.004, 0.004001, 0.010])
def test_caption_accepts_at_least_four_mm_native_clearance(
    native_caption_geometry, gap,
) -> None:
    table = _CaptionTable((0.0625, 0.0625))
    top = 0.125 - gap
    note = _CaptionNote((0.205, top - 0.009, 0.0, 0.285, top, 0.0))
    drawing._assert_exploded_caption(object(), table, note)


@pytest.mark.parametrize(
    "extent",
    [
        (),
        (0.205, 0.100, 0.0, 0.285, 0.110),
        (0.205, 0.100, 0.0, 0.285, 0.110, 0.0, 0.0),
        (0.205, 0.100, 0.0, 0.205, 0.110, 0.0),
        (0.205, 0.100, 0.0, 0.285, 0.100, 0.0),
        (0.285, 0.100, 0.0, 0.205, 0.110, 0.0),
        (0.205, 0.110, 0.0, 0.285, 0.100, 0.0),
    ],
)
def test_caption_refuses_malformed_or_empty_native_extents(
    native_caption_geometry, extent,
) -> None:
    with pytest.raises(RuntimeError):
        drawing._assert_exploded_caption(
            object(), _CaptionTable((0.0625, 0.0625)), _CaptionNote(extent)
        )


@pytest.mark.parametrize("coordinate", range(6))
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_caption_refuses_nonfinite_native_extent_coordinates(
    native_caption_geometry, coordinate, value,
) -> None:
    extent = [0.205, 0.100, 0.0, 0.285, 0.110, 0.0]
    extent[coordinate] = value
    with pytest.raises(RuntimeError):
        drawing._assert_exploded_caption(
            object(), _CaptionTable((0.0625, 0.0625)), _CaptionNote(tuple(extent))
        )


@pytest.mark.parametrize("edge", ["left", "right", "bottom", "top"])
def test_caption_refuses_native_extent_outside_sheet_border(
    native_caption_geometry, edge,
) -> None:
    template = drawing._TEMPLATE
    box = {
        "left": (drawing.BORDER - 0.001, 0.100, drawing.BORDER + 0.010, 0.110),
        "right": (
            template.width_m - drawing.BORDER - 0.010,
            0.100,
            template.width_m - drawing.BORDER + 0.001,
            0.110,
        ),
        "bottom": (0.020, drawing.BORDER - 0.001, 0.030, drawing.BORDER + 0.010),
        "top": (
            0.020,
            template.height_m - drawing.BORDER - 0.010,
            0.030,
            template.height_m - drawing.BORDER + 0.001,
        ),
    }[edge]
    x0, y0, x1, y1 = box
    # Put the BOM above the note, so this refusal proves containment rather
    # than accidentally failing the separate BOM-clearance condition.
    table = _CaptionTable((0.006,), (0.205, y1 + 0.020, 0.0))
    with pytest.raises(RuntimeError, match="border"):
        drawing._assert_exploded_caption(
            object(), table, _CaptionNote((x0, y0, 0.0, x1, y1, 0.0))
        )


def test_caption_refuses_native_extent_entering_title_block(
    native_caption_geometry,
) -> None:
    template = drawing._TEMPLATE
    top = template.title_block_top_m + 0.003
    note = _CaptionNote(
        (
            template.title_block_left_m + 0.005,
            template.title_block_top_m - 0.003,
            0.0,
            template.width_m - drawing.BORDER - 0.005,
            top,
            0.0,
        )
    )
    table = _CaptionTable((0.006,), (0.205, top + 0.020, 0.0))
    with pytest.raises(RuntimeError, match="title block"):
        drawing._assert_exploded_caption(object(), table, note)


def test_the_lifted_foot_screws_clear_their_uprights_in_the_isometric() -> None:
    """r2 machinist review (sheet 2, DETAILS B/C): lifted 25, each keeper
    foot screw and bracket hold-down hung in front of its upright (it sits
    outboard of it, nearer the eye) and read as resting against it.  Lifted
    straight up its foot hole's axis, each tip now projects over the
    upright's top silhouette in the isometric (eye on +x +y +z) by 2 mm, on
    both sides, and each north head stays inside its detail's crop."""
    import ch_fulcrum_keeper_spec as keeper
    import ch_pivot_bracket_sides as sides
    import ch_pivot_bracket_spec as bracket
    import ch_vn_bracket_hold_down_screw_spec as hold_down
    import ch_vn_frame_side_screw_spec as foot_screw

    explode = drawing.explode
    root2, root5, root6 = 2.0**0.5, 5.0**0.5, 6.0**0.5
    # 2y - x - z (the isometric's v times root 6) over a round top: the
    # half-round of radius r about height h peaks at 2h + r * root 5, and the
    # upright's inboard face (-z_rel = half its thickness) stands highest.
    lug_top = 2.0 * keeper.SHAFT_AXIS_H + keeper.CROWN_R * root5 + keeper.LUG_HALF_T
    arch_h = bracket.EAR_TOP_Y - bracket.EAR_ARCH_R
    ear_top = 2.0 * arch_h + bracket.EAR_ARCH_R * root5 + bracket.EAR_T / 2.0
    keeper_out = keeper.KEEPER_SCREW_Z_OFF - keeper.KEEPER_Z_OFF
    keeper_seat = keeper.FOOT_H - keeper.CBORE_DEPTH_MM
    keeper_case = (explode.KEEPER_FOOT_SCREW, explode.KEEPER, lug_top, keeper_out)
    bracket_case = (explode.BRACKET_HOLD_DOWN, explode.BRACKET, ear_top, sides.HOLE_Z)
    cases = (
        (*keeper_case, keeper_seat, foot_screw),
        (*bracket_case, bracket.FOOT_H, hold_down),
    )
    for stem, part, top, outboard, seat_y, screw in cases:
        for side, sign in (("south", -1.0), ("north", 1.0)):
            moved = drawing.exploded_offset(stem, side)
            carried = drawing.exploded_offset(part, side)
            # Straight up its foot hole's axis.
            assert (moved[0], moved[2]) == (carried[0], carried[2])
            tip_y = seat_y - screw.SHANK_LEN + moved[1] - carried[1]
            tip = 2.0 * tip_y - sign * outboard - screw.SHANK_DIA / 2.0 * root2
            assert (tip - top) / root6 > 2.0, (stem, side)

    # The lifted north heads inside their details' crops.
    pivot_x, pivot_y = drawing.ROCKER_PIVOT_XY
    fulcrum_x, fulcrum_y = drawing.LEVER_FULCRUM_XY
    keeper_z = drawing.FULCRUM_KEEPER_CENTRE_Z + drawing.KEEPER_Z_OFF
    hold_down_top = (
        pivot_x,
        pivot_y - bracket.BORE_H + bracket.FOOT_H + hold_down.HEAD_H,
        bank.PIVOT_BRACKET_Z[1] + sides.HOLE_Z,
    )
    foot_screw_top = (
        fulcrum_x,
        fulcrum_y - keeper.SHAFT_AXIS_H + keeper.FOOT_H,
        keeper_z + keeper_out,
    )
    bracket_head = (drawing.NORTH_BRACKET_DETAIL, hold_down_top, explode.BRACKET_HOLD_DOWN)
    keeper_head = (drawing.NORTH_KEEPER_DETAIL, foot_screw_top, explode.KEEPER_FOOT_SCREW)
    heads = ((*bracket_head, hold_down), (*keeper_head, foot_screw))
    for detail, head_top, stem, screw in heads:
        cu, cv = _iso(detail.centre_xyz)
        u, v = _iso(drawing._exploded(head_top, stem, "north"))
        reach = ((u - cu) ** 2 + (v - cv) ** 2) ** 0.5 + screw.HEAD_DIA / 2.0
        assert reach < detail.crop_radius_mm - 3.0, stem


def test_the_bracket_balloon_lands_left_of_its_lifted_hold_down() -> None:
    """Proof run 20261017T222049387Z, sheet 2: walked to the ear's apex, the
    bracket's leader 3 ran down the lifted hold-down (item 7) that stands
    over it.  It lands on the foot's free-end edge instead: on the part, at
    half the foot's height, and in the isometric well left of the
    hold-down's head (the north bracket carries its hold-down, so their
    offsets cancel apart from the lift, which moves v only)."""
    import ch_pivot_bracket_sides as sides
    import ch_pivot_bracket_spec as bracket
    import ch_vn_bracket_hold_down_screw_spec as hold_down

    x, y, z = drawing.BRACKET_BALLOON_POINT_MM
    assert x == -bracket.FOOT_W / 2.0
    assert z == sides.FOOT_Z1
    assert 0.0 < y < bracket.FOOT_H
    # The north bracket's part frame runs with the machine's (its foot
    # toward machine +z), so the part point projects like a machine one.
    assert sides.OUTBOARD_SIGN["N"] == 1.0
    moved = drawing.exploded_offset(drawing.explode.BRACKET_HOLD_DOWN, "north")
    carried = drawing.exploded_offset(drawing.explode.BRACKET, "north")
    assert (moved[0], moved[2]) == (carried[0], carried[2])
    head_left = _iso((0.0, 0.0, sides.HOLE_Z))[0] - hold_down.HEAD_DIA / 2.0
    # 6.0 model mm, 0.86 on the sheet at 1:7: a leader's width and more.
    assert head_left - _iso((x, y, z))[0] > 5.0


def test_the_north_keeper_balloons_on_detail_c_right_of_its_lifted_screws() -> None:
    """#1895 machinist review: on the 1:7 view the north keeper stands in
    front of the near-black rocker bank, and leaders 8-10 crossing it were
    lost. Its family balloons on DETAIL C, the caption says so, and the
    keeper's leader lands on its inner crown apex, which projects right of
    both lifted screws (eye on +x +y +z), so its ring slot is the right-most
    and its leader crosses neither screw."""
    from _hole_spec import THREAD_MAJOR_MM
    import ch_fulcrum_keeper_spec as keeper
    import ch_vn_frame_side_screw_spec as foot_screw

    explode = drawing.explode
    detail = drawing.NORTH_KEEPER_DETAIL
    family = {explode.KEEPER, explode.KEEPER_SET_SCREW, explode.KEEPER_FOOT_SCREW}
    assert drawing.KEEPER_DETAIL_BALLOON_STEMS == detail.stems == family
    assert detail.title in drawing.EXPLODED_CAPTION
    assert drawing.BALLOON_POINTS_MM[explode.KEEPER] == (
        -keeper.LUG_HALF_T,
        keeper.CROWN_TOP_Y,
        0.0,
    )
    # North keeper: part +x is outboard, machine +z. Relative to the lug
    # mid-plane, the apex sits 4 inboard, the set screw on the mid-plane and
    # the foot screw SCREW_X outboard; both screws move straight up.
    for stem in (explode.KEEPER_SET_SCREW, explode.KEEPER_FOOT_SCREW):
        moved = drawing.exploded_offset(stem, "north")
        carried = drawing.exploded_offset(explode.KEEPER, "north")
        assert (moved[0], moved[2]) == (carried[0], carried[2])
    apex_u = _iso((0.0, 0.0, -keeper.LUG_HALF_T))[0]
    set_screw_right = THREAD_MAJOR_MM[keeper.SET_SCREW_THREAD] / 2.0
    foot_screw_right = _iso((0.0, 0.0, keeper.SCREW_X))[0] + foot_screw.HEAD_DIA / 2.0
    assert apex_u - set_screw_right > 1.5
    assert apex_u - foot_screw_right > 5.0
    # The ring stays in the column above DETAIL C: the farm read its outline
    # 44.1 mm tall about the crop centre (run 20261023T222629630Z), so the
    # top balloon reaches 22.05 + margin + a balloon radius over it, under
    # DETAIL B's three-line label.
    bracket_label_bottom = (
        drawing.NORTH_BRACKET_DETAIL.crop_label_xy[1]
        - len(drawing.NORTH_BRACKET_DETAIL.label_text.splitlines()) * NOTE_LINE_PITCH
    )
    ring_top = (
        detail.centre[1]
        + 0.02205
        + drawing.KEEPER_DETAIL_BALLOON_MARGIN
        + drawing.BALLOON_MAX_RADIUS
    )
    assert ring_top + 0.004 < bracket_label_bottom


def test_the_pivot_shaft_balloon_lands_on_its_bare_south_stub() -> None:
    """#1895 machinist review (r2, r3): leader 1 climbed through the black
    rocker-arm fan to a landing it hid. It lands on the south flat's
    eye-side edge, on the stub between hub 0 and the exploded south ear,
    whose line of sight (eye on +x +y +z) clears hub 0 and arm 0's top edge,
    and its balloon stands off the ring, above and east of that landing."""
    import ch_pivot_shaft_spec as shaft
    import ch_rocker_arm_spec as arm

    x, y, z = drawing.BALLOON_POINTS_MM[drawing.PIVOT_SHAFT_STEM]
    radius = shaft.SHAFT_DIA / 2.0
    assert y == pytest.approx(radius - shaft.FLAT_DEPTH)
    assert x > 0.0 and math.hypot(x, y) == pytest.approx(radius)
    point_z = bank.PIVOT_SHAFT_NORTH_Z + z
    assert point_z == pytest.approx(bank.PIVOT_BRACKET_Z[0])
    assert bank.SOUTH_EAR_OUTER_Z < point_z < bank.HUB0_SOUTH_FACE_Z
    assert drawing.exploded_offset(drawing.explode.BRACKET, "south")[2] < 0.0
    hub_t = bank.HUB0_SOUTH_FACE_Z - point_z
    assert math.hypot(x + hub_t, y + hub_t) > arm.HUB_DIA / 2.0 + 5.0
    arm_t = bank.hub_mid_z(0) - arm.ARM_THICKNESS / 2.0 - point_z
    reach = x + arm_t
    top_edge = arm.TOP_EDGE_ABOVE_PIVOT + arm.R_TOP - math.sqrt(arm.R_TOP**2 - reach**2)
    assert y + arm_t - top_edge > 1.5
    dx, dy = drawing.PIVOT_SHAFT_BALLOON_OFFSET
    assert dy > 0.04 and 0.0 < dx < dy / 3.0


def test_the_bom_covers_every_family_once_with_its_sku() -> None:
    assert len(drawing.BOM_COMPONENTS) == 19
    assert set(drawing.BOM_PART_NUMBERS) == set(drawing.BOM_COMPONENTS)
    assert len(set(drawing.BOM_PART_NUMBERS.values())) == len(drawing.BOM_COMPONENTS)
    for stem in drawing.BOM_COMPONENTS:
        row = drawing.PART_ROWS[stem]
        skus = row.get("supplier_skus") or ()
        assert drawing.BOM_SKUS[stem] == (
            " / ".join(map(str, skus)) if skus else drawing.MADE_PART_SKU
        )
        assert drawing.BOM_DESCRIPTIONS[stem]
    assert drawing.BOM_QUANTITIES[drawing.SPRING_STEM] == drawing.CHANNELS
    assert sum(drawing.BOM_QUANTITIES.values()) == 2 + 7 * 2 + 1 + 9 * drawing.CHANNELS
    # The anchor's jam nut (MHA-CH-14, made) is its own row, one per anchor.
    nut = drawing.explode.ANCHOR_NUT
    assert drawing.BOM_QUANTITIES[nut] == drawing.BOM_QUANTITIES[drawing.explode.HOOK]
    assert drawing.BOM_SKUS[nut] == drawing.MADE_PART_SKU
    body = _step_body(steps.SPRINGS_HOOKED_KEY)
    assert (
        f"THREADED AND JAMMED BY ITS {drawing.BOM_PART_NUMBERS[nut]} PER "
        f"{steps.HA_ANCHORS_SET_REF}."
    ) in body


def test_a_preset_with_several_spring_lengths_is_refused_at_drawing_time(
    monkeypatch,
) -> None:
    """Code review C07: the square preset builds 11 spring variants (one per
    distinct amplitude), each its own SLDPRT under MHA-CH-VN-50, so its BOM
    would print 11 rows of one part number. The drawing refuses that preset
    when it runs, not at import, so collection and the neutral contract hold."""
    import asyncio

    square = _config.machine("springs", "presets", "square", "amplitudes_mm")
    stems = drawing.spring_stems(square, drawing.CHANNELS)
    assert len(square) == drawing.CHANNELS == 20
    assert len(stems) == len(set(square)) == 11
    neutral = drawing.spring_stems([0.0] * drawing.CHANNELS, drawing.CHANNELS)
    assert neutral == ("ch-vn-channel-spring-installed-stretch00",)
    drawing.require_single_spring_variant(neutral, "neutral")

    real_machine = _config.machine
    monkeypatch.setattr(
        _config,
        "machine",
        lambda *keys: "square" if keys == ("amplitude", "preset") else real_machine(*keys),
    )
    monkeypatch.setattr(drawing, "SPRING_STEMS", stems)
    with pytest.raises(RuntimeError) as refused:
        asyncio.run(drawing.build(object()))
    message = str(refused.value)
    assert "'square' amplitude preset builds 11 spring variants" in message
    assert "MHA-CH-VN-50" in message
    assert drawing.SPRING_VARIANT_ISSUE in message
    assert drawing.SPRING_VARIANT_ISSUE.endswith("/issues/1610")


def test_the_sheet_text_stays_out_of_the_assembly_recipe() -> None:
    """Code review C03: the BOM descriptions, dimension callouts and which
    dimension prints as a reference are read by the drawing alone. The
    builder's recipe closure (file-granular, every local import followed)
    must not reach them, or a wording edit would force a full native rebuild
    of the channel assembly."""
    scripts = Path(drawing.__file__).resolve().parent
    sheet = str(scripts / "ch_channel_assembly_sheet.py")
    explode_spec = str(scripts / "ch_channel_explode_spec.py")
    for builder in ("build_ch_channel_assembly.py", "_ch_channel_explode.py"):
        assert sheet not in _buildgraph.module_deps_of(scripts / builder)
        assert explode_spec in _buildgraph.module_deps_of(scripts / builder)
    assert sheet in _buildgraph.module_deps_of(scripts / "draw_ch_channel_assembly.py")
    for text in ("BOM_DESCRIPTIONS", "DIMENSION_CALLOUTS", "REFERENCE_DIMENSIONS"):
        assert not hasattr(drawing.asm, text)
        assert not hasattr(drawing.explode, text)


def test_the_explode_plan_moves_every_family_and_only_them() -> None:
    explode = drawing.explode
    names = {explode.EXPLODED_VIEW_NAME}
    assert names == {drawing.EXPLODED_VIEW_NAMES[drawing.ASSEMBLY_VIEW_CONFIGURATION]}
    instances = []
    for stem, quantity in drawing.BOM_QUANTITIES.items():
        if quantity == 2:
            instances += [
                explode.Instance(f"{stem}-1", stem, -70.0),
                explode.Instance(f"{stem}-2", stem, 70.0),
            ]
        else:
            instances += [
                explode.Instance(f"{stem}-{j + 1}", stem, -70.0 + 7.0 * j)
                for j in range(quantity)
            ]
    plan = explode.plan_explode(instances)
    moved = {name for step in plan for name in step[1]}
    # r11 machinist review: one channel, the north-most (the balloons'), is
    # pulled out of the closed-up bank; every other channel stays in it.
    channel = {
        stem: max(
            (instance for instance in instances if explode.family(instance.stem) == stem),
            key=lambda instance: instance.z_mm,
        ).name
        for stem in explode.EXPLODED_STEMS - explode.FULLY_EXPLODED_STEMS
    }
    assert set(channel) == {explode.ARM, explode.ROD_PIN, explode.LEVER, explode.CHANNEL_SPRING}
    assert moved == {
        instance.name
        for instance in instances
        if explode.family(instance.stem) in explode.FULLY_EXPLODED_STEMS
    } | set(channel.values())
    (pulled,) = [
        names for step, names in plan if step.label == "north-most channel out"
    ]
    assert len(pulled) == 9 and set(channel.values()) <= set(pulled)
    assert all(name.endswith("-20") for name in pulled)
    assert drawing.exploded_offset(explode.ARM, "north-most") == (0.0, 0.0, 300.0)
    assert drawing.exploded_offset(explode.ROD, "north-most") == (0.0, -50.0, 300.0)
    assert drawing.exploded_offset(explode.ROD_PIN, "north-most") == (0.0, 0.0, 325.0)
    # Machinist review (PR #1605): withdrawn north the bar pin sat on the
    # lever's lower edge and balloon 16's arrowhead lay along the lever, so it
    # read as landing on the lever end with 17. South, along its own axis
    # (still coaxial with its bar), it stands in the open past the bar's top.
    assert drawing.exploded_offset(explode.BAR_PIN, "north-most") == (0.0, 20.0, 275.0)
    bar_offset = drawing.exploded_offset(explode.BAR, "north-most")
    pin_offset = drawing.exploded_offset(explode.BAR_PIN, "north-most")
    assert pin_offset[:2] == bar_offset[:2] and pin_offset[2] < bar_offset[2]
    assert drawing.exploded_offset(explode.BAR, "north-most") == (0.0, 20.0, 300.0)
    assert drawing.exploded_offset(explode.BAR, "north") == (0.0, 50.0, 0.0)
    spring = drawing.exploded_offset(drawing.SPRING_STEM, "north-most")
    assert spring == (0.0, 0.0, 300.0)
    assert drawing.exploded_offset(explode.ARM, "north") == (0.0, 0.0, 0.0)
    assert {"ch-pivot-shaft", explode.ARM, explode.LEVER}.isdisjoint(explode.FULLY_EXPLODED_STEMS)
    assert explode.FULCRUM_SHAFT in explode.EXPLODED_STEMS


def test_the_fulcrum_keepers_are_pair_reamed_set_by_dro_and_staked() -> None:
    """GPT review F5/F6 and round 3 (PR #1311): the two keeper bores share one
    axis only if they are reamed through in one pass at their installed
    spacing, feet on one flat; the actual shaft gauges that line in the
    clamped setup. The pair is then set on the top frame by DRO with the
    shaft through both, and each crown tap's mouth is staked over its set
    screw (drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads)'s lock). The keeper print points at these steps."""
    import ch_fulcrum_keeper_spec as keeper
    import draw_ch_fulcrum_keeper as keeper_drawing
    from channel_frame_geom import LEVER_FULCRUM_XY
    from frame_column_stations import COLUMN_X

    number = _config.parts("ch-fulcrum-keeper")["number"]
    fulcrum_shaft = _config.parts("ch-fulcrum-shaft")["number"]
    top_frame = _config.parts("fr-top-frame")["number"]
    assert steps.SEQUENCE[-6:-4] == drawing.LEVER_KEYS[:2]
    assert drawing.LEVER_KEYS + drawing.LEVER_CONTINUED_KEYS == (
        steps.KEEPERS_PAIR_REAMED_KEY,
        steps.KEEPERS_SET_KEY,
        steps.BARS_PINNED_KEY,
        steps.LEVER_BANK_THREADED_KEY,
        steps.SET_SCREWS_STAKED_KEY,
        steps.SPRINGS_HOOKED_KEY,
    )
    places = keeper.KEEPER_FITUP_PLACES
    front, rear = keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    reamed = _step_body(steps.KEEPERS_PAIR_REAMED_KEY)
    # The controlling operation: installed spacing (KEEPERS_SET_KEY's two faces),
    # one common flat, axis set to it, one pass to the keeper print's bore band.
    assert keeper.KEEPER_INNER_FACE_SPAN_MM == pytest.approx(rear - front) == 142.0
    assert f"CLAMP BOTH {number}, FEET OUTBOARD ON ONE FLAT" in reamed
    assert "INNER LUG FACES AT THE LEVER BANK VIEW'S LUG SPAN" in reamed
    assert keeper.KEEPER_INNER_FACE_SPAN_MM == pytest.approx(
        drawing.asm.LUG_INNER_FACE_Z[1] - drawing.asm.LUG_INNER_FACE_Z[0]
    )
    assert "BORE AXIS PARALLEL TO THE FLAT" in reamed
    # Machinist gate 2026-10-17 (rule 7): the step states the bores' acceptance,
    # never the operation or the made-to-order reamer (sized against the keeper
    # print's band in ch_fulcrum_keeper_spec). 5d5245a48 review (rule 24): the
    # bore limits are the keeper print's, not this sheet's. #1660 r3 (rules 1
    # and 22): the step says plainly that the bores are made in this setup.
    assert (
        f"STILL CLAMPED, MAKE BOTH {number} BORES TO THEIR DRAWING, IN LINE: "
        f"THE {fulcrum_shaft} SHAFT SLIDES FREELY THROUGH BOTH." in reamed
    )
    assert "6.388" not in reamed and "6.400" not in reamed
    for method in ("REAM", "0.2515", " IN LONG", " PASS"):
        assert method not in reamed
    assert keeper.PAIR_REAMER_REACH_MARGIN_MM > 0.0
    # #1660 r2 (rules 22 and 24): the crown and its tap centre on the bore
    # made here, so the keeper is finished in this step, but its sizes and the
    # tap's place are the keeper print's (CrownRadius and the crown tap, which
    # point back at this step); the assembly sheet restates none of them.
    assert (
        "THEN, ON EACH BORE'S AXIS, FINISH THAT KEEPER'S CROWN AND CROWN TAP "
        f"TO THE {number} DRAWING." in reamed
    )
    for part_data in ("R7.0", "#1-72", " PIN ", "CROWN TOP", "9.8", "10.6"):
        assert part_data not in reamed
    assert keeper_drawing.DIMENSION_CALLOUTS["CrownRadius"].endswith(
        f"PER {steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)}"
    )
    # #1660 r2 (rule 19): the lever bank has no stack fit-up because it needs
    # none. Twenty hubs at the top of their band leave end play at the
    # shortest lug span the two inner-face bands allow, and the bars on the
    # rocker straps locate the bank. The step says so and gauges it.
    from ch_channel_lever_spec import HUB_LENGTH as LEVER_HUB, HUB_LENGTH_BAND

    span_min = (
        keeper.KEEPER_INNER_FACE_SPAN_MM - 2 * keeper.KEEPER_FITUP_LOCATION_BAND_MM
    )
    assert span_min - drawing.COUNT * (LEVER_HUB + HUB_LENGTH_BAND[0]) > 0.2
    threaded = _step_body(steps.LEVER_BANK_THREADED_KEY)
    assert "THE BARS ON THE STRAPS LOCATE THE LEVER BANK" in threaded
    assert "SLIDES ALONG THE SHAFT BETWEEN THE LUGS" in threaded
    assert keeper.SET_SCREW_ENGAGEMENT_D >= keeper.SET_SCREW_MIN_ENGAGEMENT_D
    fitted = _step_body(steps.KEEPERS_SET_KEY)
    assert f"{top_frame} ON THE MILL:" in fitted
    # Main's ruling: X off the receiving web, Z off the upper socket line; the
    # owner's (X1+B1, b9ae review): the settings are the keeper plan view's
    # own banded dimensions, the step carries no number of them.
    assert keeper.KEEPER_FITUP_X_FROM_WEB_MM == pytest.approx(
        LEVER_FULCRUM_XY[0] - COLUMN_X
    )
    assert (
        "SET EACH LUG CENTRE OFF THE RAIL WEB CENTRE BELOW IT AND THE LUG INNER "
        "FACES OFF THE LINE OF THE UPPER SOCKET CENTRES, TO THE KEEPER PLAN VIEW"
    ) in fitted
    assert drawing.KEEPER_PLAN.title == "KEEPER PLAN VIEW"
    for value in (keeper.KEEPER_FITUP_X_FROM_WEB_MM, front, rear):
        assert f"{value:.{places}f}" not in fitted
    asm = drawing.asm
    # Owner ruling X-A: the lug centre carries its own looser band, the
    # inner faces the location band.
    for name, band in (
        (asm.KEEPER_X_DIMENSION, keeper.KEEPER_FITUP_X_BAND_MM),
        (asm.KEEPER_FRONT_Z_DIMENSION, keeper.KEEPER_FITUP_LOCATION_BAND_MM),
        (asm.KEEPER_REAR_Z_DIMENSION, keeper.KEEPER_FITUP_LOCATION_BAND_MM),
    ):
        assert asm.DIMENSION_TOLERANCES[name] == (-band, band)
        assert asm.DRAWING_PRECISION[asm.KEEPER_PLAN_FEATURE][name] == places
    assert asm.KEEPER_LUG_X - asm.KEEPER_SOCKET_XZ[0] == pytest.approx(
        keeper.KEEPER_FITUP_X_FROM_WEB_MM
    )
    assert [z - asm.KEEPER_SOCKET_XZ[1] for z in asm.LUG_INNER_FACE_Z] == pytest.approx(
        [front, rear]
    )
    # The web centre label reads as the split of both web faces (owner ruling).
    assert any(
        "WEB CENTRE,\nSPLIT OF BOTH WEB FACES" in text
        for text, _, _ in drawing.PLAN_POINTERS
    )
    # The bands' functions (Main's ruling, 2026-10-16): together they hold the
    # shaft's flat-station window (ch_fulcrum_shaft_spec); the slide (r11
    # review) moves both flats at once, the band is what leaves it a seat. The
    # south face's band also keeps its foot off the front socket boss at the
    # printed worst case (build_fr_top_frame), which the step names so the
    # absolute setting has a stated reason (#1660 r1, rules 4 and 19). Since
    # the keeper prints its overall length off the inner lug face (owner
    # ruling 2026-10-28) the boss would clear even at the title block's band.
    import build_fr_top_frame as top

    south_margin, north_margin = top.KEEPER_FOOT_PRINTED_BOSS_MARGINS
    band = keeper.KEEPER_FITUP_LOCATION_BAND_MM
    title_block_band = top.PRINTED_LINEAR_BAND_MM[places]
    assert 0.0 < south_margin
    assert south_margin + band - title_block_band > 0.0
    assert north_margin > 10 * band
    # #1660 r6 (rule 4): the lug centre's ±0.10 (owner ruling X-A) is charged
    # in the transferred foot tap's wall to the rail web, which holds the
    # frame's .060 floor (rule 17) with it.
    assert top.KEEPER_TAP_DRILL_WALL_MARGIN >= top.WALL_FLOOR_MM
    staked_number = steps.step_number(steps.SET_SCREWS_STAKED_KEY)
    for phrase in (
        "THE LUG CENTRE'S BAND KEEPS EACH FOOT HOLE, TRANSFERRED BELOW, OVER "
        "THE RAIL WEB WITH A FULL WALL ROUND ITS TAP",
        f"SOUTH FOOT CLEAR OF THE {top_frame} FRONT SOCKET BOSS",
        f"THE {fulcrum_shaft} FLATS ARE A FIXED PITCH APART",
        f"BANDS TOGETHER LEAVE ONE STEP {staked_number} SHAFT POSITION",
    ):
        assert phrase in fitted
    assert "EACH FLAT LIES UNDER ITS CROWN TAP" in _step_body(
        steps.SET_SCREWS_STAKED_KEY
    )
    assert "TRANSFER EACH FOOT HOLE INTO THE RAIL" in fitted
    staked = _step_body(steps.SET_SCREWS_STAKED_KEY)
    assert "STAKE EACH TAP MOUTH AT 2 POINTS" in staked
    # The keeper print cites these steps by key.
    assert keeper_drawing.DIMENSION_CALLOUTS["BoreDia"].endswith(
        f"PER {steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)}"
    )
    assert keeper_drawing.DIMENSION_CALLOUTS["CrownRadius"].endswith(
        f"PER {steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)}"
    )
    staking = steps.step_ref(steps.SET_SCREWS_STAKED_KEY)
    assert staking in keeper_drawing.SET_SCREW_QUALIFIER


def test_each_rod_fork_is_pinned_to_its_arm_at_the_bench_first() -> None:
    """The rod ring is captured in its closed cam slot during the cylinder
    stack, and a pressed pin needs its far tine backed on the press, so the
    MHA-CH-10 pin goes in at the bench, before that drive-train step -- after
    the hub stack is proved on the shaft and the rockers come off in order.
    User ruling 2026-10-09 (PR #1292 review F1): pressed, ends dressed flush,
    removable with a punch, as the MHA-CH-11 bar pin."""
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
    # Positive control: no other step pins this pin; only the bar pin presses.
    for key in steps.SEQUENCE:
        if key != steps.RODS_PINNED_KEY:
            assert pin not in _step_body(key)
        if key not in (steps.RODS_PINNED_KEY, steps.BARS_PINNED_KEY):
            assert "PRESS" not in _step_body(key)



def test_the_finished_shaft_is_set_by_its_north_tip_before_the_screws() -> None:
    """Machinist review (fleet pass): MHA-CH-05 comes finished, domed both
    ends to its overall length, so nothing is cut at assembly. Between the
    south bracket's setting and the set screws one step sets the shaft's
    north tip DOME_HEIGHT proud of the north ear, within the layout's band."""
    import ch_pivot_shaft_spec as shaft

    assert "UNCUT" not in shaft.DRAWING_NOTES and "SUPPLY" not in shaft.DRAWING_NOTES
    assert not hasattr(shaft, "LENGTH_CALLOUT")
    for key in steps.SEQUENCE:
        body = _step_body(key)
        assert "CUT THE" not in body and "SCRIBE" not in body and "UNCUT" not in body
    key = "shaft-set"
    number = steps.step_number(key)
    assert steps.step_number("south-bracket-screwed") < number
    assert number < steps.step_number("set-screws-driven")
    low = shaft.DOME_HEIGHT - bank.SHAFT_TIP_SET_BAND
    high = shaft.DOME_HEIGHT + bank.SHAFT_TIP_SET_BAND
    assert (
        f"NORTH TIP STANDS {low:.2f} TO {high:.2f} PROUD OF THE NORTH EAR'S OUTER FACE"
        in _step_body(key)
    )
    # Positive control: no other step sets the tip.
    for other in steps.SEQUENCE:
        if other != key:
            assert "NORTH TIP" not in _step_body(other)


def test_the_set_screws_go_in_after_the_shaft_is_set_and_print_the_engagement_fact() -> None:
    """User, 2026-10-10: one MHA-SH-VN-54 down each ear's apex tap onto the
    plain shaft's flat, once the shaft is set. The preload is accepted before
    (machinist review, PR #1605: a failed check after staking could not be
    re-set). The step prints the bracket spec's engagement fact from the
    spec, never typed."""
    import ch_pivot_bracket_spec as bracket_spec

    set_screw = _config.parts("sh-vn-arbor-set-screw")["number"]
    key = "set-screws-driven"
    number = steps.step_number(key)
    assert steps.step_number("shaft-set") < number
    assert steps.step_number("south-bracket-spring-set") < number
    assert number < steps.step_number(steps.KEEPERS_PAIR_REAMED_KEY)
    body = _step_body(key)
    assert f"RUN ONE {set_screw} DOWN EACH APEX TAP ONTO ITS FLAT" in body
    assert "FLATS UP" in body and "NORTH FIRST" in body
    # drawing-guidelines.md rule 23, period hardware: staked as the keeper
    # set screws are, never threadlocked.
    assert "SNUG, AND STAKE EACH TAP MOUTH AT 2 POINTS." in body
    assert "LOCTITE" not in drawing.FITUP_STEPS
    assert body.endswith(" ".join(bracket_spec.SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT.split()))
    # Positive control: no other step fits the set screws or prints the fact.
    for other in steps.SEQUENCE:
        if other != key:
            assert set_screw not in _step_body(other)
    assert drawing.FITUP_STEPS.count("ENGAGEMENT") == 1


def test_the_set_screw_step_states_a_fact_that_needs_no_declaration() -> None:
    """The owner's 2026-10-15 shortfall ruling (#1371) covered the R8 arch's
    1.08D; the lifted arch holds 1.5D, so the step's engagement fact is no
    shortfall and the channel contract declares no exception for it. RV-01
    covers the keeper inner-face bands of owner ruling X-A."""
    import ch_pivot_bracket_spec as bracket_spec
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    name = "ch_channel_assembly"
    assert DRAWINGS_BY_NAME[name].source_kind == "assembly"
    entries = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", name, "assembly")
    }
    keeper_bands = entries["RV-01"]
    assert not [id_ for id_ in entries if "1667" in id_]
    assert (keeper_bands.id, keeper_bands.kind) == ("RV-01", "accept")
    assert "KeeperFrontFaceZ, KeeperRearFaceZ" in keeper_bands.where
    assert "ENGAGEMENT" not in keeper_bands.where.upper()
    fact = (
        f"{bracket_spec.SET_SCREW_THREAD} ENGAGEMENT "
        f"{bracket_spec.SET_SCREW_FULL_THREAD_MIN:.2f} MIN "
        f"({bracket_spec.SET_SCREW_ENGAGEMENT_PRINTED:.2f}D)."
    )
    assert _step_body("set-screws-driven").endswith(fact)
    assert bracket_spec.SET_SCREW_ENGAGEMENT_PRINTED >= 1.5
    assert assembly_contract("ch-channel").number == "MHA-CH-00"


def test_the_set_screw_interference_allowance_is_the_ear_tap() -> None:
    """_interference_contracts restates the ear's apex height over the bore
    and the bore as literals (every assembly imports it); they must be the
    bracket spec's, and the screws' thread its apex tap's."""
    import _interference_contracts as ic
    import ch_pivot_bracket_spec as bracket_spec
    import sh_vn_arbor_set_screw_spec as screw_spec

    assert ic.PIVOT_EAR_APEX_AND_BORE == (
        bracket_spec.APEX_ABOVE_BORE,
        bracket_spec.BORE_DIA,
    )
    assert screw_spec.THREAD == bracket_spec.SET_SCREW_THREAD
    pairs = ic.allowed_interference_pairs("ch-channel")
    for n in (1, 2):
        pair = frozenset((f"sh-vn-arbor-set-screw-{n}", f"ch-pivot-bracket-{n}"))
        assert pairs[pair] == ic.PIVOT_EAR_SET_SCREW_LIMIT


def test_shared_arbor_set_screws_keep_their_two_ear_seats_and_learned_sides() -> None:
    stem = "sh-vn-arbor-set-screw"
    assert drawing.explode.BRACKET_SET_SCREW == stem
    assert drawing.BOM_QUANTITIES[stem] == 2
    assert drawing.BOM_PART_NUMBERS[stem] == "MHA-SH-VN-54"
    assert drawing.BOM_SKUS[stem] == "91375A106"
    seeds = assembly_contract("ch-channel").flip_invert
    assert {f"sh vn arbor set screw datum {axis}" for axis in "xyz"} <= seeds
    assert not any(seed.startswith("ch vn arbor set screw datum ") for seed in seeds)
