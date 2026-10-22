"""Offline contracts for the paper-drive assembly and its drawing (MHA-PD-00)."""

import asyncio
from itertools import product
import math
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from _column_clamp_interface import BAR_DEPTH
import _assembly
from _assembly_contract import assembly_contract
import _chain as chain
import _com
import _config
import _component_references
import _drawing_balloons
import _drawing_tables
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
import build_pd_paper_drive_assembly as assembly
import draw_pd_paper_drive_assembly as drawing
import dt_drive_train_steps
import fr_harmonic_base_spec as base
import fr_nameplate_spec as nameplate
import paper_drive_geom as paper_geometry
import paper_drive_rack_setup as rack_setup
import pd_paper_drive_assembly_steps as steps
import pd_paper_drive_explode_spec as explode
import pd_rack_pinion_spec as disc
import pd_transgear_drive_collar_spec as collar
import pd_transgear_front_bushing_spec as front_bushing
import pd_transgear_feed_pinion_spec as feed_pinion
import pd_transgear_knob_cup_spec as cup
import pd_transgear_knob_shaft_spec as knob_shaft
import pd_vn_transgear_arm_plate_locating_pin_spec as plate_locating_pin
import _transgear_arm_plate_locating_interface as plate_locating_interface
import pd_vn_transgear_arm_plate_screw_spec as plate_screw
import pd_vn_transgear_knob_drive_pin_spec as drive_pin
import pd_transgear_rear_bushing_spec as rear_bushing
from _test_stubbed_build import stub_seat
import pd_transgear_removable_spec as sprocket
import _sprocket_seat_geometry as seat_geometry
import transgear_cluster_fit as cluster_fit
import transgear_hanger_joints as joints
import pd_vn_transgear_knob_cup_pin_spec as cup_pin
import pd_vn_transgear_pivot_screw_spec as pivot_screw

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d), as test_channel_assembly_drawing uses them;
# #945 moves these into _drawing_common.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045
# Words no sheet of the package may print (drawing-simplicity policy).
FORBIDDEN_SHEET_WORDS = ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY")

# CONTRACT-paper-drive.md, the round-10 component set.
UNCHANGED_FAMILIES = {
    "pd-support-bar",
    "sh-column-clamp-front",
    "sh-column-clamp-back",
    "sh-vn-clamp-screw",
    "pd-platen",
    "pd-platen-rack",
    "pd-platen-guide",
    "pd-guide-lock",
    "pd-platen-clip",
    "pd-platen-paper",
    "sh-vn-brass-fillister-screw",
    "pd-vn-platen-clip-screw",  # the four #2-56 clip screws leave MHA-PD-VN-52
    "pd-vn-guide-lock-screw",  # R9-31: the eight lock screws leave MHA-PD-VN-52
    "sh-vn-chain-link--InnerLink",
    "sh-vn-chain-link--OuterLink",
    "pd-vn-chain-connecting-link",  # MHA-PD-VN-66 closes the loop as its last outer link
    "pd-transgear-removable",
}
CONTRACT_TRANSGEAR_QUANTITIES = {
    "pd-transgear-arm": 1,
    "pd-transgear-arm-plate": 1,
    "pd-vn-transgear-arm-plate-screw": 2,
    "pd-vn-transgear-arm-plate-locating-pin": plate_locating_pin.ASSEMBLY_QUANTITY,
    "pd-transgear-pivot-spacer": 1,
    "pd-vn-transgear-pivot-screw": 1,
    "pd-vn-transgear-pivot-spring": 1,
    "pd-vn-transgear-pivot-shim": 1,
    "pd-vn-transgear-latch-pin": 1,
    "sh-vn-fillister-screw-90280a108": 2,
    "pd-latch-hook": 1,
    "pd-transgear-pin": 1,
    "pd-transgear-rear-bushing": 1,
    "pd-transgear-feed-pinion": 1,
    "pd-transgear-disc-hub": 1,
    "pd-transgear-front-bushing": 1,
    "pd-vn-transgear-retaining-ring": 1,
    "pd-rack-pinion": 1,
    "pd-vn-transgear-disc-screw": 3,
    "pd-transgear-knob-shaft": 1,
    "pd-transgear-drive-collar": 1,
    "pd-vn-transgear-knob-drive-pin": 2,
    "pd-transgear-removable": 3,
    "pd-transgear-thumbnut": 1,
    "pd-transgear-knob-thrust-ring": 1,
    "pd-transgear-knob-cup": 1,
    "pd-vn-transgear-knob-cup-pin": 1,
}
RETIRED_FAMILIES = {
    "transgear-latch",
    "transgear-pinion",
    "transgear-bracket",
    "bracket-screw",
    "pd-latch-hook-bracket",
    "vn-latch-hook-rivet",
    "vn-transgear-collar-cross-pin",
}


def _unit_operating_domain() -> drawing.RackOperatingDomain:
    """The real engaged-feed window: closed-form, cheap and source-derived."""
    return rack_setup.feed_rack_operating_domain()


def _unit_step_notes() -> drawing.StepNotes:
    return drawing.format_step_notes(operating_domain=_unit_operating_domain())


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head."""
    text = _unit_step_notes().fitup_steps
    heads = list(STEP_HEAD.finditer(text))
    index = steps.step_number(key) - 1
    end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
    return " ".join(text[heads[index].end() : end].split())


def _number(stem: str) -> str:
    return _config.parts(drawing.BOM_COMPONENT_IDENTITIES.get(stem, (stem, None))[0])["number"]


def test_paper_drive_keeps_registry_outputs_and_names_its_sheets() -> None:
    spec = DRAWINGS_BY_NAME["pd_paper_drive_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "pd_paper_drive"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert set(drawing.SHEET_LAYOUTS) == set(drawing.SHEET_NAMES)
    assert len(set(drawing.SHEET_NAMES)) == len(drawing.SHEET_NAMES)


def test_an_unknown_step_is_refused() -> None:
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    notes = _unit_step_notes()
    printed = [
        int(n)
        for text in (notes.platen_steps, *notes.fitup_notes, *notes.chain_notes)
        for n in STEP_HEAD.findall(text)
    ]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))


def test_the_crank_side_pointer_names_the_sheet_that_prints_those_steps() -> None:
    """§13.2 (1): the chain fit-up starts from the crank side's own fit-up,
    and the pointer names the MHA-DT-00 sheet whose note prints both steps."""
    import draw_dt_drive_train_assembly as drive_train
    notes = _unit_step_notes()

    pointers = re.findall(
        r"(MHA-[A-Z]{2}-00)\b SHEET (\d+), STEPS (\d+) AND (\d+)",
        notes.chain_notes[0].replace("\n", " "),
    )
    wanted = [str(dt_drive_train_steps.step_number(key)) for key in steps.CRANK_SIDE_KEYS]
    assert pointers == [
        (assembly_contract("dt-drive-train").number, str(drive_train.SEQUENCE_SHEET), *wanted)
    ]
    assert steps.CRANK_SIDE_KEYS == ("crank-mesh-checked", "paper-drive-wheel")
    # The cone-and-crank steps are the note package_note_fields stacks on
    # SEQUENCE_SHEET.
    printed = set(STEP_HEAD.findall(drive_train.CONE_CRANK_STEPS))
    assert set(wanted) <= printed
    fitup_ref = steps.step_number(drawing.FITUP_CHAIN_KEY)
    pose_ref = steps.step_number("fitup-pose-set")
    assert f"STEP {pose_ref}" in _step_body("fitup-accepted")
    heading = notes.chain_notes[0].index("CHAIN FIT-UP")
    assert notes.chain_notes[0].index(f"\n{fitup_ref}. ") > heading


def test_the_steps_fit_their_fields() -> None:
    notes = _unit_step_notes()
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    fields = (
        *zip(
            notes.fitup_notes,
            drawing.FITUP_NOTE_XY,
            drawing.FITUP_NOTE_LIMITS,
            strict=True,
        ),
        *zip(
            notes.chain_notes,
            drawing.FITUP_NOTE_XY,
            drawing.FITUP_NOTE_LIMITS,
            strict=True,
        ),
        (
            notes.platen_steps,
            drawing.PLATEN_NOTE_XY,
            (drawing.PLATEN_NOTE_RIGHT, template.title_block_top_m),
        ),
        *(
            (
                text,
                drawing.ASSEMBLED_CAPTION_XY,
                (
                    drawing.ISO_RING_LIMITS[0] - 0.003,
                    drawing.SHEET_INNER_BORDER_BOTTOM,
                ),
            )
            for text in drawing.ASSEMBLED_CAPTIONS.values()
        ),
    )
    for text, (left, top), (right_limit, bottom_limit) in fields:
        lines = text.splitlines()
        assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < right_limit
        assert top - len(lines) * NOTE_LINE_PITCH > bottom_limit
    (first_left, _), (second_left, _) = drawing.FITUP_NOTE_XY
    first_limit, second_limit = drawing.FITUP_NOTE_LIMITS
    assert first_limit[0] < second_left
    assert second_limit[1] > template.title_block_top_m
    assert first_left > 0.0 and second_limit[0] < template.width_m
    # Sheet 3's caption sits under its steps, sheet 1's under the front view.
    assert notes.exploded_caption_xy[1] < drawing.PLATEN_NOTE_XY[1] - (
        len(notes.platen_steps.splitlines()) * NOTE_LINE_PITCH
    )
    assert notes.exploded_caption_xy[1] - NOTE_LINE_PITCH > template.title_block_top_m


def test_a_bom_that_cannot_fit_all_rows_is_refused_not_truncated() -> None:
    # f353's native 437.2384 mm table cannot fit these two fields even split.
    heights = (0.0102, *(0.01016758 for _ in range(42)))
    with pytest.raises(RuntimeError, match="complete paper-drive BOM does not fit"):
        drawing.bom_split_row(heights, 1)


def test_native_bom_containment_keeps_the_reference_title_and_border_clear() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    width = sum(drawing.BOM_COLUMN_WIDTHS.values())
    left, top = drawing.BOM_ANCHOR
    ref_floor = drawing.BOM_REFERENCE_LIMITS[3] + drawing.BOM_BORDER_CLEARANCE
    assert drawing.bom_extent_violations((left, top), width, top - ref_floor) == []
    assert drawing.bom_extent_violations((left, top), width, top - ref_floor + 0.001)
    right, top = drawing.BOM_SECOND_ANCHOR
    title_floor = template.title_block_top_m + drawing.BOM_BORDER_CLEARANCE
    assert drawing.bom_extent_violations((right, top), width, top - title_floor) == []
    assert drawing.bom_extent_violations((right, top), width, top - title_floor + 0.001)
    border = drawing.SHEET_INNER_BORDER_BOTTOM + drawing.BOM_BORDER_CLEARANCE
    assert drawing.bom_extent_violations(
        (template.width_m - border - width + 0.001, top), width, 0.1
    )


def test_bom_rows_are_exactly_the_round10_families() -> None:
    families = set(drawing.BOM_PART_NUMBERS)
    assert families == UNCHANGED_FAMILIES | set(CONTRACT_TRANSGEAR_QUANTITIES)
    assert not families & RETIRED_FAMILIES
    assert drawing.TRANSGEAR_QUANTITIES == CONTRACT_TRANSGEAR_QUANTITIES


def test_bom_numbers_and_purchased_skus_come_from_the_registry() -> None:
    for stem, number in drawing.BOM_PART_NUMBERS.items():
        assert number == _number(stem), stem
    for stem, description in drawing.BOM_DESCRIPTIONS.items():
        registry = _config.parts(drawing.BOM_COMPONENT_IDENTITIES[stem][0])
        skus = registry.get("supplier_skus") or ()
        # A fabricated part from purchased stock (the SDP/SI platen rack) is
        # not itself a McMaster purchase line.
        if skus and registry.get("supplier") == "McMaster-Carr":
            assert description.endswith(f"MCMASTER {skus[0]}"), stem
        else:
            assert "MCMASTER" not in description, stem
    # Distinct physical members deliberately share one canonical purchase Number.
    inner, outer = "sh-vn-chain-link--InnerLink", "sh-vn-chain-link--OuterLink"
    assert drawing.BOM_PART_NUMBERS[inner] == drawing.BOM_PART_NUMBERS[outer]
    assert drawing.BOM_COMPONENT_IDENTITIES[inner] != drawing.BOM_COMPONENT_IDENTITIES[outer]


def test_the_two_locating_dowels_are_not_the_two_knob_wheel_drive_dowels() -> None:
    locating = "pd-vn-transgear-arm-plate-locating-pin"
    driving = "pd-vn-transgear-knob-drive-pin"
    assert plate_locating_pin.ASSEMBLY_QUANTITY == 2
    assert drawing.TRANSGEAR_QUANTITIES[locating] == plate_locating_pin.ASSEMBLY_QUANTITY
    assert drawing.TRANSGEAR_QUANTITIES[driving] == len(seat_geometry.PIN_HOLE_ANGLES_DEG)
    assert _number(locating) != _number(driving)
    assert "PLATE LOCATING DOWEL" in drawing.BOM_DESCRIPTIONS[locating]
    assert "WHEEL DRIVE DOWEL" in drawing.BOM_DESCRIPTIONS[driving]
    assert locating in drawing.INNER_STEMS
    for stem in (locating, driving):
        assert len(drawing.BOM_DESCRIPTIONS[stem]) <= drawing.BOM_DESCRIPTION_MAX_CHARS


def test_the_critical_matched_dowels_locate_and_the_plate_screws_only_clamp() -> None:
    located = _step_body("arm-plate-located")
    assert (
        f"PRESS {plate_locating_pin.ASSEMBLY_QUANTITY} "
        f"{_number('pd-vn-transgear-arm-plate-locating-pin')} DOWELS"
    ) in located
    assert (
        "TOGETHER IN A JIG HOLDING THE PLATE'S KNOB BORE "
        f"{disc.CENTRE_DISTANCE:.3f} FROM THE ARM'S PIN BORE, PER THEIR DRAWINGS"
    ) in located
    assert "MATCH-DRILL AND REAM THE LOCATING HOLES" in located
    assert (
        f"{plate_locating_interface.PROUD_LIMITS_MM[0]:.2f} TO "
        f"{plate_locating_interface.PROUD_LIMITS_MM[1]:.2f} PROUD, NOT TO THE BLIND FLOOR"
    ) in located
    assert "MATCH-MARK ARM AND PLATE" in located
    fitted = _step_body("arm-plate-fitted")
    assert "PLATE ON THE LOCATING DOWELS" in fitted
    assert "DOWELS LOCATE; SCREWS CLAMP ONLY" in fitted
    # One ordinary hand check; no gauge budget or load qualification text.
    assert "PUSH AND ROCK THE PLATE BY HAND: NO SHAKE ON THE DOWELS" in fitted
    assert "RE-CHECK AFTER EVERY REMOVAL" in fitted
    for method in ("RFS", "UNCERTAINTY", "QUALIFIED", "ACTUAL"):
        assert method not in fitted
    assert "COUNTERSINK" not in fitted
    assert "PIVOT BORE WAS REAMED TO THIS SCREW" in _step_body("hanger-pivoted")
    assert steps.step_number("arm-plate-located") + 1 == steps.step_number("arm-plate-fitted")


def test_bom_identifies_the_current_inch_mesh_parts_without_cutter_prose() -> None:
    for stem, spec in (
        ("pd-rack-pinion", disc),
        ("pd-transgear-knob-shaft", knob_shaft),
        ("pd-transgear-feed-pinion", feed_pinion),
    ):
        description = drawing.BOM_DESCRIPTIONS[stem]
        assert f"{spec.TEETH}T" in description
        assert f"{spec.DIAMETRAL_PITCH:g}DP" in description
        assert f"PA{spec.PRESSURE_ANGLE_DEG:g}" in description
        assert "STOCK" in description
        assert "SHIFTED" not in description
        assert len(description) <= drawing.BOM_DESCRIPTION_MAX_CHARS
    assert "REDUCER DISC" in drawing.BOM_DESCRIPTIONS["pd-rack-pinion"]
    rack = drawing.BOM_DESCRIPTIONS["pd-platen-rack"]
    assert "RACK + BACKER" in rack
    assert f"{feed_pinion.DIAMETRAL_PITCH:g}DP" in rack
    assert f"PA{feed_pinion.PRESSURE_ANGLE_DEG:g}" in rack
    for text in (*drawing.sheet_texts(_unit_step_notes()), *drawing.BOM_DESCRIPTIONS.values()):
        assert "CUTTER" not in text


def test_the_feed_setup_reference_uses_the_selected_ratios_and_reference_pitch() -> (
    None
):
    expected = (
        sprocket.CRANK_TEETH
        / sprocket.KNOB_TEETH
        * knob_shaft.TEETH
        / disc.TEETH
        * math.pi
        * feed_pinion.PITCH_DIA
    )
    assert paper_geometry.NET_RACK_TRAVEL_PER_CRANK_REV == pytest.approx(expected)
    text = steps.PAPER_FEED_REFERENCE_TEXT
    match = re.search(r"PLATEN TRAVEL (\d+\.\d+) PER CRANK REV \(REF\)", text)
    assert match
    places = steps.PAPER_FEED_REFERENCE_PLACES
    assert len(match[1].split(".")[1]) == places
    assert float(match[1]) == pytest.approx(expected, abs=0.5 * 10.0**-places)
    assert f"{sprocket.CRANK_CONFIG} CRANK" in text
    assert f"{sprocket.KNOB_CONFIG} KNOB" in text
    for caption in drawing.ASSEMBLED_CAPTIONS.values():
        assert text in caption
    # The form-cutter setting changes the tooth boundary, not the rolling pitch.
    tip_based_travel = expected * feed_pinion.OUTSIDE_DIA / feed_pinion.PITCH_DIA
    assert float(match[1]) != pytest.approx(tip_based_travel)
    # The historical 30DP comparison is provenance, not a second setup value.
    assert "30DP" not in text and "%" not in text


def test_sheet_two_shows_and_balloons_exactly_the_transgear() -> None:
    expected = {
        f"{stem}-{index}"
        for stem, count in CONTRACT_TRANSGEAR_QUANTITIES.items()
        for index in range(1, count + 1)
        if stem != "pd-transgear-removable"
    } | {"pd-transgear-removable-1"}
    assert drawing.TRANSGEAR_INSTANCES == expected
    # The collar alone has no batch anchor: it balloons on its rear rim.
    anchored = set(CONTRACT_TRANSGEAR_QUANTITIES) - {drawing.COLLAR_STEM}
    assert set(drawing.TRANSGEAR_BALLOON_ANCHORS) == anchored
    # The knob wheel is instance 1; crank wheel and spare T18 stay off.
    assert drawing.TRANSGEAR_BALLOON_ANCHORS["pd-transgear-removable"].instance == (
        "pd-transgear-removable-1"
    )


def test_the_collar_leader_lands_on_its_rear_rim_beside_the_lower_end() -> None:
    # The inner view sees the collar's rims edge-on from the right; hit tests
    # missed them on farm runs 20261002T160324403Z, 20261002T164049933Z and
    # 20261002T171234232Z. The leader lands past the drive-pin hole, so one
    # re-solved to the rim line's nearer end stays in limit.
    x, y, z = drawing.COLLAR_LANDING_MM
    radius = collar.OD / 2.0
    assert math.hypot(x, y) == pytest.approx(radius, abs=1e-9)
    assert z == pytest.approx(collar.LENGTH)
    pin_gap = math.dist((x, y), (0.0, -collar.PIN_CIRCLE_RADIUS)) - collar.PIN_HOLE_DIA / 2.0
    assert pin_gap > 0.5
    # The rear slot along local X splits the rim: the landing stays on the -Y arc.
    assert abs(math.degrees(math.atan2(x, -y))) < 30.0
    # Green run 20261001T172013211Z's 1:2 rear-rim line, -Y end to +Y end.
    minus_end, plus_end = (0.21852, 0.171822), (0.21852, 0.180572)
    landing = drawing.collar_rim_landing(minus_end, plus_end)
    assert landing[0] == pytest.approx(0.21852)
    view_y = drawing.COLLAR_LANDING_Y
    assert landing[1] - minus_end[1] == pytest.approx((radius + view_y) / 2.0 / 1000.0)
    largest_scale = max(num / den for num, den in drawing.INNER_SCALE_LADDER)
    end_gap_m = (radius + view_y) * largest_scale / 1000.0
    assert end_gap_m < _drawing_balloons._BALLOON_LANDING_TOLERANCE_M / 2.0
    # Below the axis is away from the feed sleeve: its stud stands above the knob.
    assert assembly.STUD_XY[1] > assembly.KNOB_SHAFT_XY[1]


def test_the_collar_rim_points_follow_the_front_stack_spin() -> None:
    # Run 10: the collar is spun -3 deg with the knob front stack, so its
    # LOCAL +X point sat r sin 3 deg off the edge-on line's midpoint.
    assert assembly.THIRD_PHASE_DEG == knob_shaft.FRONT_STACK_PHASE_DEG
    spin = math.radians(assembly.THIRD_PHASE_DEG)
    rows = ((math.cos(spin), -math.sin(spin)), (math.sin(spin), math.cos(spin)))
    radius = collar.OD / 2.0
    view_frame = [
        (rows[0][0] * x + rows[0][1] * y, rows[1][0] * x + rows[1][1] * y)
        for x, y, _z in drawing.COLLAR_RIM_VIEW_POINTS_MM
    ]
    expected = [(0.0, -radius), (0.0, radius), (radius, 0.0), (-radius, 0.0)]
    for got, want in zip(view_frame, expected, strict=True):
        assert got == pytest.approx(want, abs=1e-12)
    x, y, _z = drawing.COLLAR_LANDING_MM
    assert rows[1][0] * x + rows[1][1] * y == pytest.approx(drawing.COLLAR_LANDING_Y)


def _circle(
    z: float, radius: float, closest: tuple[float, float, float], axis_z: float = 1.0
) -> drawing.RimCandidate:
    return drawing.RimCandidate(
        edge=object(),
        circle=(0.0, 0.0, z, 0.0, 0.0, axis_z, radius),
        closest_mm=closest,
    )


def test_the_collar_rim_matcher_takes_the_one_arc_holding_the_landing() -> None:
    radius, z = collar.OD / 2.0, collar.LENGTH
    landing = drawing.COLLAR_LANDING_MM
    # The nearest-point matcher must reject a different circular carrier,
    # whether a model seam splits a rim or the source has one complete circle.
    lower = _circle(z, radius, landing)
    upper = _circle(z, radius, (-radius, 0.0, z))
    front = _circle(0.0, radius, (landing[0], landing[1], 0.0))
    bore = _circle(z, collar.BORE_DIA / 2.0, (landing[0] / 2, landing[1] / 2, z))
    assert drawing.collar_rear_rim([front, upper, lower, bore]) is lower
    # Either axis sense is the collar's.
    flipped = _circle(z, radius, landing, axis_z=-1.0)
    assert drawing.collar_rear_rim([front, flipped, upper]) is flipped
    # 2 micrometres off the landing is another arc.
    near = _circle(z, radius, (landing[0], landing[1] - 0.002, z))
    with pytest.raises(RuntimeError, match=r"matched 0 of 4 circles: r 8\.7500"):
        drawing.collar_rear_rim([front, upper, bore, near])
    with pytest.raises(RuntimeError, match="matched 0 of 0 circles: none"):
        drawing.collar_rear_rim([])
    with pytest.raises(RuntimeError, match="matched 2 of 3 circles"):
        drawing.collar_rear_rim([lower, flipped, upper])


# Farm run 20261002T180658288Z's inner-view ring (its drawing.balloon_ring
# event): BOM item and attachment (sheet m), in ring order. 17 is the
# arm-plate screw, 24 the rear bushing, 32 the collar.
INNER_RING_180658 = (
    ("34", (0.219889, 0.176708)),
    ("32", (0.220362, 0.174046)),
    ("18", (0.229903, 0.170997)),
    ("35", (0.234541, 0.176240)),
    ("39", (0.236058, 0.178096)),
    ("26", (0.226995, 0.178996)),
    ("24", (0.228995, 0.180840)),
    ("17", (0.233308, 0.188817)),
    ("33", (0.218228, 0.178923)),
)
# That run logged no outline: run 20261002T172458664Z's 1:2 inner outline,
# scaled to 1:3 about the collar's landing (218.520, 171.821 there; 220.362,
# 174.046 here). Its circles render r 5.232 mm.
INNER_OUTLINE_180658 = (0.209403, 0.162653, 0.239943, 0.192772)
BALLOON_RADIUS = 0.005232


def _ring_centres(
    outline: tuple[float, float, float, float],
) -> list[tuple[float, float]]:
    """_spread_balloons' circle centres for INNER_RING_180658, in its order."""
    cx, cy = (outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0
    rx = (outline[2] - outline[0]) / 2.0 + drawing.BALLOON_MARGIN
    ry = (outline[3] - outline[1]) / 2.0 + drawing.BALLOON_MARGIN
    thetas = [math.atan2(y - cy, x - cx) for _item, (x, y) in INNER_RING_180658]
    order = sorted(range(len(thetas)), key=thetas.__getitem__)
    gap = _drawing_balloons._min_angular_gap(
        min(rx, ry), BALLOON_RADIUS, clearance=_drawing_balloons._BALLOON_CLEARANCE_M
    )
    angles = _drawing_balloons._push_apart_on_ring(
        [thetas[index] for index in order], min_gap=gap
    )
    centres = [(0.0, 0.0)] * len(thetas)
    for index, angle in zip(order, angles):
        centres[index] = (cx + rx * math.cos(angle), cy + ry * math.sin(angle))
    return centres


def _crossed_items(
    centres: list[tuple[float, float]], slots: list[int]
) -> set[frozenset[str]]:
    """The item pairs whose printed leaders, circle edge to attachment, cross."""
    segments = []
    for (item, (x, y)), slot in zip(INNER_RING_180658, slots):
        bx, by = centres[slot]
        length = math.hypot(x - bx, y - by)
        segments.append(
            LeaderSegment(
                label=item,
                kind="balloon",
                x0=bx + (x - bx) / length * BALLOON_RADIUS,
                y0=by + (y - by) / length * BALLOON_RADIUS,
                x1=x,
                y1=y,
            )
        )
    return {
        frozenset((crossing.a.label, crossing.b.label))
        for crossing in find_leader_leader_crossings(segments)
    }


def test_the_inner_ring_swaps_crossing_leaders_onto_each_others_slots() -> None:
    attachments = [attach for _item, attach in INNER_RING_180658]
    identity = list(range(len(INNER_RING_180658)))
    centres = _ring_centres(INNER_OUTLINE_180658)
    # The ring as run 20261002T180658288Z left it crosses 17 over 24.
    assert _crossed_items(centres, identity) == {frozenset({"17", "24"})}
    slots = drawing.uncrossed_ring_slots(centres, attachments)
    moved = {INNER_RING_180658[index][0] for index in identity if slots[index] != index}
    assert moved == {"17", "24"}
    assert _crossed_items(centres, slots) == set()
    # The outline is reconstructed: within 2 mm of it either way, whatever
    # the ring crosses, the slots it takes cross nothing, and no leader runs
    # through another balloon's circle.
    for dx, dy in product((-0.002, 0.0, 0.002), repeat=2):
        x0, y0, x1, y1 = INNER_OUTLINE_180658
        shifted = _ring_centres((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
        slots = drawing.uncrossed_ring_slots(shifted, attachments)
        assert sorted(slots) == identity
        assert _crossed_items(shifted, slots) == set(), (dx, dy)
        for index, (x, y) in enumerate(attachments):
            bx, by = shifted[slots[index]]
            for other, (ox, oy) in enumerate(shifted):
                if other == slots[index]:
                    continue
                t = ((ox - bx) * (x - bx) + (oy - by) * (y - by)) / (
                    (x - bx) ** 2 + (y - by) ** 2
                )
                t = min(1.0, max(0.0, t))
                gap = math.hypot(bx + t * (x - bx) - ox, by + t * (y - by) - oy)
                assert gap > BALLOON_RADIUS, (dx, dy, index, other)


def test_an_uncrossed_ring_keeps_its_slots() -> None:
    centres = [(0.0, 1.0), (1.0, 0.0), (0.0, -1.0)]
    attachments = [(0.0, 0.1), (0.1, 0.0), (0.0, -0.1)]
    assert drawing.uncrossed_ring_slots(centres, attachments) == [0, 1, 2]
    # Two leaders swapped across each other go back.
    assert drawing.uncrossed_ring_slots(centres[:2], attachments[1::-1]) == [1, 0]


def test_the_isometric_ring_pair_from_run_082822_swaps() -> None:
    """Run 20261015T082822796Z's audit: isometric balloons 14 and 16, leaders
    (circle edge -> attachment), crossed at (372.9, 178.4) mm. Their slots
    swap, and the swapped leaders cross nothing."""
    centres = [(0.4017, 0.1595), (0.4032, 0.1753)]
    attachments = [(0.3703, 0.1801), (0.3639, 0.1793)]

    def crossings(slots: list[int]) -> list:
        return find_leader_leader_crossings(
            [
                LeaderSegment(
                    label=str(index),
                    kind="balloon",
                    x0=centres[slot][0],
                    y0=centres[slot][1],
                    x1=attach[0],
                    y1=attach[1],
                )
                for index, (slot, attach) in enumerate(zip(slots, attachments))
            ]
        )

    assert crossings([0, 1])
    slots = drawing.uncrossed_ring_slots(centres, attachments)
    assert slots == [1, 0]
    assert not crossings(slots)


# These families were assigned to the inner view after farm run
# 20261001T051043622Z found no reachable isometric ink for the sleeve.
# Native balloon landings, not old diameters or centres, defend the selection.
HIDDEN_BY_THE_ISOMETRIC = {
    "pd-transgear-feed-pinion",
    "pd-transgear-knob-shaft",
    "pd-transgear-drive-collar",
    "pd-vn-transgear-knob-drive-pin",
    "pd-vn-transgear-knob-cup-pin",
    "pd-vn-transgear-arm-plate-screw",
    "pd-vn-transgear-arm-plate-locating-pin",
    "pd-vn-transgear-latch-pin",
    "pd-transgear-rear-bushing",
}


def test_each_transgear_family_balloons_once_on_the_view_that_shows_it() -> None:
    # Item numbers against the dict order, so the order must come from them.
    items = {
        stem: str(len(drawing.BOM_PART_NUMBERS) - index)
        for index, stem in enumerate(drawing.BOM_PART_NUMBERS)
    }
    iso, inner = drawing.transgear_balloon_items(items)
    iso_stems = {stem for stem, _item in iso}
    inner_stems = {stem for stem, _item in inner}
    assert inner_stems == HIDDEN_BY_THE_ISOMETRIC
    assert iso_stems == set(CONTRACT_TRANSGEAR_QUANTITIES) - HIDDEN_BY_THE_ISOMETRIC
    for balloons in (iso, inner):
        assert all(items[stem] == item for stem, item in balloons)
        numbers = [int(item) for _stem, item in balloons]
        assert numbers == sorted(numbers)
    # The inner view shows every instance of its families and nothing else,
    # so no outer part covers them there.
    assert drawing.INNER_INSTANCES == {
        f"{stem}-{index}"
        for stem in inner_stems
        for index in range(1, CONTRACT_TRANSGEAR_QUANTITIES[stem] + 1)
    }
    assert drawing.INNER_INSTANCES <= drawing.TRANSGEAR_INSTANCES


# Native run 20261001T062924323Z (024e240b3) read sheet 2's outlines in x: the
# isolated transgear at 2:3 centred at x 355 mm spans 295.3 to 404.8, the
# inner *Right view at 2:3 placed at x 240 spans 201.0 to 258.3. Their y
# extents are estimates from the builder's stations (the run reported no y).
ISO_OUTLINE_AT_355 = (0.2953, 0.1438, 0.4048, 0.2319)
INNER_OUTLINE_AT_2_3 = (0.2010, 0.1622, 0.2583, 0.2179)


def _iso_outline(center_x: float) -> tuple[float, float, float, float]:
    dx = center_x - 0.355
    x0, y0, x1, y1 = ISO_OUTLINE_AT_355
    return (x0 + dx, y0, x1 + dx, y1)


def _scaled(
    outline: tuple[float, float, float, float], scale: tuple[float, float]
) -> tuple[float, float, float, float]:
    """``outline`` (read at 2:3) at ``scale``, about its centre."""
    k = (scale[0] / scale[1]) / (2.0 / 3.0)
    x0, y0, x1, y1 = outline
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * k, (y1 - y0) / 2 * k
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def test_the_024e240b3_layout_is_refused_naming_each_overflow() -> None:
    """The native failure: both views at 2:3, the isometric centred at 355."""
    with pytest.raises(ValueError) as refused:
        drawing.inner_view_shift(_iso_outline(0.355), INNER_OUTLINE_AT_2_3)
    message = str(refused.value)
    assert "isometric ring right 421.8 mm past 415.0 mm" in message
    assert "inner view ring left 184.0 mm past 185.0 mm" in message
    assert (
        "inner view ring right 275.3 mm within 4 mm of the isometric ring (278.3 mm)"
        in message
    )
    with pytest.raises(ValueError, match="no inner-view scale fits.*1:2.*1:3"):
        drawing.inner_view_scale(_iso_outline(0.355), INNER_OUTLINE_AT_2_3, (2.0, 3.0))


def test_both_model_rings_fit_inside_their_reserved_sheet_two_fields() -> None:
    iso = _iso_outline(drawing.TRANSGEAR_VIEW_CENTER[0])
    scale = drawing.inner_view_scale(iso, INNER_OUTLINE_AT_2_3, (2.0, 3.0))
    assert scale == (1.0, 2.0)
    inner = _scaled(INNER_OUTLINE_AT_2_3, scale)
    dx, dy = drawing.inner_view_shift(iso, inner)
    reach = drawing.BALLOON_RING_REACH
    iso_left, iso_right = iso[0] - reach, iso[2] + reach
    left, right = inner[0] + dx - reach, inner[2] + dx + reach
    assert iso_right <= 0.415 - 0.002
    assert left >= drawing.SHEET_TWO_RING_LIMITS[0] + 0.0015
    assert right <= iso_left - drawing.SHEET_TWO_RING_GAP - 0.0015
    # Level with the isometric.
    assert (inner[1] + inner[3]) / 2.0 + dy == pytest.approx((iso[1] + iso[3]) / 2.0)
    # Its caption stands under the ring, over the title block, left of the
    # isometric's ring.
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    caption_top = inner[1] + dy - reach - drawing.INNER_CAPTION_GAP
    assert caption_top - NOTE_LINE_PITCH > template.title_block_top_m
    assert left + len(drawing.INNER_CAPTIONS[scale]) * NOTE_CHAR_WIDTH < iso_left


def test_an_inner_view_wider_than_measured_steps_down_to_1_3() -> None:
    """Ten per cent wider at 2:3 overflows at 1:2; 1:3 then fits."""
    x0, y0, x1, y1 = INNER_OUTLINE_AT_2_3
    wider = (x0 - (x1 - x0) * 0.05, y0, x1 + (x1 - x0) * 0.05, y1)
    iso = _iso_outline(drawing.TRANSGEAR_VIEW_CENTER[0])
    with pytest.raises(ValueError, match="inner view ring"):
        drawing.inner_view_shift(iso, _scaled(wider, (1.0, 2.0)))
    assert drawing.inner_view_scale(iso, wider, (2.0, 3.0)) == (1.0, 3.0)


# The v40 sheet 2 (the same layout code as 594749aec) printed the views'
# outlines, read from the PDF's view images: the transgear isometric at 2:3
# and the inner view at 1:3. The farm run of 9055bc155 refused the one-piece
# hook's isometric. That isometric's left edge and top come from its message
# (rings at 261.5 and 265.8). Its right edge and bottom are v40's, because
# the hook only grows the view up and left. The run's inner view at 1:2 was
# 46.5 mm wide (ring 181.0 to 261.5). Its height is v40's 1:3 height
# scaled, since the run reported no y.
ISO_OUTLINE_V40 = (0.2853, 0.1112, 0.3966, 0.2448)
INNER_OUTLINE_V40_AT_1_3 = (0.2073, 0.1612, 0.2418, 0.1948)
ISO_OUTLINE_ONE_PIECE_HOOK = (0.2785, 0.1112, 0.3966, 0.2488)
INNER_OUTLINE_ONE_PIECE_HOOK_AT_1_2 = (0.2000, 0.1528, 0.2465, 0.2032)
# v40's printed 1:3 inner view, as placed at 1:2 (1.5 times about its centre).
INNER_OUTLINE_V40_AT_1_2 = (
    0.224550 - 0.0258750,
    0.178000 - 0.0252000,
    0.224550 + 0.0258750,
    0.178000 + 0.0252000,
)


def _moved(
    outline: tuple[float, float, float, float], shift: tuple[float, float]
) -> tuple[float, float, float, float]:
    dx, dy = shift
    return (outline[0] + dx, outline[1] + dy, outline[2] + dx, outline[3] + dy)


def test_the_one_piece_hook_isometric_as_placed_is_refused_as_on_the_farm() -> None:
    """The farm refusal of 9055bc155, word for word: placed at
    TRANSGEAR_VIEW_CENTER, the grown isometric's ring tops the field at
    every inner-view scale."""
    with pytest.raises(ValueError) as refused:
        drawing.inner_view_scale(
            ISO_OUTLINE_ONE_PIECE_HOOK, INNER_OUTLINE_ONE_PIECE_HOOK_AT_1_2, (1.0, 2.0)
        )
    assert str(refused.value) == (
        "no inner-view scale fits sheet 2 (1:2: sheet 2 balloon rings do not fit: "
        "isometric ring top 265.8 mm past 262.0 mm; inner view ring left 181.0 mm "
        "past 185.0 mm; inner view ring right 261.5 mm within 4 mm of the "
        "isometric ring (261.5 mm) | 1:3: sheet 2 balloon rings do not fit: "
        "isometric ring top 265.8 mm past 262.0 mm)"
    )


@pytest.mark.parametrize(
    ("iso_outline", "inner_at_placed"),
    [
        (ISO_OUTLINE_ONE_PIECE_HOOK, INNER_OUTLINE_ONE_PIECE_HOOK_AT_1_2),
        (ISO_OUTLINE_V40, INNER_OUTLINE_V40_AT_1_2),
    ],
    ids=["one-piece-hook", "v40"],
)
def test_the_centred_isometric_leaves_the_inner_view_room_at_1_3(
    iso_outline: tuple[float, float, float, float],
    inner_at_placed: tuple[float, float, float, float],
) -> None:
    """Centred vertically and unmoved along x, the isometric's ring fits the
    field. The inner view then steps down to 1:3, and the outline of 1:3 as
    printed (with its padding) fits beside it."""
    shift = drawing.transgear_view_shift(iso_outline)
    assert shift[0] == 0.0
    iso = _moved(iso_outline, shift)
    reach = drawing.BALLOON_RING_REACH
    left, bottom, right, top = drawing.SHEET_TWO_RING_LIMITS
    assert (iso[1] - reach - bottom) == pytest.approx(top - (iso[3] + reach))
    assert iso[1] - reach >= bottom and iso[3] + reach <= top
    assert drawing.inner_view_scale(iso, inner_at_placed, (1.0, 2.0)) == (1.0, 3.0)
    dx, dy = drawing.inner_view_shift(iso, INNER_OUTLINE_V40_AT_1_3)
    inner = _moved(INNER_OUTLINE_V40_AT_1_3, (dx, dy))
    assert inner[0] - reach >= left
    assert inner[2] + reach <= iso[0] - reach - drawing.SHEET_TWO_RING_GAP


def test_the_one_piece_hook_isometric_moves_down_4_0_mm() -> None:
    dx, dy = drawing.transgear_view_shift(ISO_OUTLINE_ONE_PIECE_HOOK)
    assert (dx, dy) == (0.0, pytest.approx(-0.0040))


def test_an_isometric_taller_than_the_field_is_refused() -> None:
    x0, y0, x1, _y1 = ISO_OUTLINE_ONE_PIECE_HOOK
    with pytest.raises(
        ValueError, match=r"isometric ring height 173\.0 mm > room 172\.0 mm"
    ):
        drawing.transgear_view_shift((x0, y0, x1, y0 + 0.139))


def test_no_sheet_prints_a_forbidden_word() -> None:
    texts = (*drawing.sheet_texts(_unit_step_notes()), *drawing.BOM_DESCRIPTIONS.values())
    for text in texts:
        for word in FORBIDDEN_SHEET_WORDS:
            assert word not in text.upper(), (word, text)


def test_no_retired_part_is_named_on_the_sheet() -> None:
    retired = {"MHA-079", "MHA-080", "MHA-108", "MHA-109"}
    text = _unit_step_notes().fitup_steps
    printed = set(re.findall(r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])", text))
    assert not any(number in text for number in retired)
    assert printed <= set(drawing.BOM_PART_NUMBERS.values()) | {
        assembly_contract("dt-drive-train").number
    }


def test_the_knob_stack_prints_front_to_rear() -> None:
    """Contract §1: thumbnut | knob wheel | collar | 12T | ring | plate hub | plate |
    rear boss | cup | screw."""
    body = _step_body("knob-stack-fitted")
    order = [
        "pd-transgear-thumbnut",
        "pd-transgear-removable",
        "pd-transgear-drive-collar",
        "pd-transgear-knob-shaft",
        "pd-transgear-knob-thrust-ring",
        "pd-transgear-arm-plate",
        "pd-transgear-knob-cup",
        "pd-vn-transgear-knob-cup-pin",
    ]
    assert [stem for stem, _label in drawing.KNOB_STACK if stem] == order
    positions = [body.index(_number(stem)) for stem in order]
    assert positions == sorted(positions)
    assert body.index("PLATE HUB") < body.index(_number("pd-transgear-arm-plate"))
    assert body.index("REAR BOSS") < body.index(_number("pd-transgear-knob-cup"))


def test_the_pivot_screw_is_staked_and_the_spacer_pressed_as_made() -> None:
    """Rule 23: MHA-PD-VN-57 runs through the bar, its tip faced below the
    front face and staked there, shown in the pivot view; threadlocker is
    optional. R9-6 never faces MHA-PD-20.  R9-71: the spacer is pressed on
    the shoulder flush with its end, and the MHA-PD-VN-63 spring under the
    MHA-PD-VN-67 shim holds the arm on it."""
    body = _step_body("hanger-pivoted")
    low, high = pivot_screw.TIP_RECESS
    assert "THREADLOCKER OPTIONAL" in body
    assert "BLIND" not in body
    assert "THROUGH TAP" in body
    assert f"{low:.2f} TO {high:.2f} BELOW THE BAR'S FRONT FACE" in body
    assert "STAKE THE FRONT TAP MOUTH ONTO THE TIP AT 2 OPPOSITE POINTS" in body
    # The screw is chosen by its unfaced tip before the arm's bore is reamed
    # to it, so the fitter never meets a matched screw that fails the check.
    assert (
        "THE ARM'S PIVOT BORE WAS REAMED TO THIS SCREW, CHOSEN BEFORE REAMING "
        "SO ITS UNFACED TIP REACHES THAT WINDOW: KEEP THEM TOGETHER."
    ) in body
    face = body.index("BELOW THE BAR'S FRONT FACE")
    assert face < body.index("CHOSEN BEFORE REAMING")
    assert "ANOTHER SCREW" not in body
    assert drawing.PIVOT_VIEW_REF in body
    assert body.index(_number("pd-vn-transgear-pivot-shim")) < body.index(
        _number("pd-vn-transgear-pivot-spring")
    )
    assert _number("pd-vn-transgear-pivot-screw") in body
    assert _number("pd-transgear-pivot-spacer") in body
    assert _number("pd-vn-transgear-pivot-spring") in body
    assert "AS MADE" in body
    assert "FLUSH WITH ITS END ON A FLAT" in body
    # No step shortens the spacer.
    assert not re.search(r"\bFACE (IT|THE SPACER|TO)\b", _unit_step_notes().fitup_steps)


def test_the_fitup_acceptance_prints_the_contract_bands() -> None:
    """§13.2 (8): the seated chain offset, cup-set knob float and minimum
    collar-disc air use their owning specs; R9-71 leaves no head play."""
    expected_float = (
        knob_shaft.END_FLOAT - knob_shaft.END_FLOAT_SET_TOL,
        knob_shaft.END_FLOAT + knob_shaft.END_FLOAT_SET_TOL,
    )
    assert drawing.KNOB_END_FLOAT_RANGE == pytest.approx(expected_float, abs=1e-9)
    body = _step_body("fitup-accepted")
    for text in (
        f"{steps.OFFSET_ACCEPT_TEXT} FORWARD",
        f"{expected_float[0]:.2f} TO {expected_float[1]:.2f}",
        steps.COLLAR_DISC_AIR_TEXT,
        f"{sprocket.KNOB_CONFIG} FREE UNDER THE NUT",
    ):
        assert text in body, text
    assert "HEAD PLAY" not in body


def test_the_pivot_section_and_its_locator_keep_to_sheet_two_left_field() -> None:
    ring_left, _bottom, _right, ring_top = drawing.SHEET_TWO_RING_LIMITS
    field_right = ring_left - drawing.SHEET_TWO_RING_GAP
    # The section's balloon ring stays in the field.
    sx, sy = drawing.PIVOT_SECTION_CENTER
    reach = drawing.PIVOT_SECTION_RADIUS + drawing.BALLOON_RING_REACH
    assert sx - reach > 0.018
    assert sx + reach < field_right
    # The locator's circle sits above the ring, its cutting line inside the
    # circle and at least 1 mm past the stack each way along the axis.
    lx, ly = drawing.PIVOT_LOCATOR_CENTER
    lr = drawing.PIVOT_LOCATOR_RADIUS
    assert lx + lr < field_right
    assert ly + lr < ring_top
    assert sy + reach < ly - lr - 0.006
    scale = drawing.PIVOT_LOCATOR_SCALE[0] / drawing.PIVOT_LOCATOR_SCALE[1]
    stack_half = (pivot_screw.HEAD_H - drawing.PIVOT_FRONT_FACE_Y) / 2.0
    assert (stack_half + 1.0) * scale / 1000.0 <= drawing.PIVOT_CUT_HALF < lr
    # The caption over the ring, left of the locator's section arrows.
    caption_lines = drawing.PIVOT_CAPTION.splitlines()
    cx, cy = drawing.PIVOT_CAPTION_XY
    assert cx > 0.018
    assert cx + max(map(len, caption_lines)) * NOTE_CHAR_WIDTH < lx - lr - 0.008
    assert cy <= ring_top
    assert cy - len(caption_lines) * NOTE_LINE_PITCH > sy + reach
    # The native section caption under the ring, above the border.
    caption_y = drawing.PIVOT_SECTION_CAPTION_XY[1]
    assert caption_y < sy - reach
    assert caption_y - 2 * NOTE_LINE_PITCH > drawing.SHEET_INNER_BORDER_BOTTOM
    # Both circles frame the screw from its head to the bar's front face.
    assert drawing.PIVOT_FRONT_FACE_Y == pytest.approx(
        -(pivot_screw.SHOULDER_LEN + BAR_DEPTH)
    )
    assert drawing.PIVOT_SECTION_RADIUS == pytest.approx(
        drawing.PIVOT_FRAME_RADIUS_MM
        * drawing.PIVOT_SECTION_SCALE[0]
        / drawing.PIVOT_SECTION_SCALE[1]
        / 1000.0
    )
    assert drawing.PIVOT_VIEW_INSTANCES >= {
        "pd-support-bar-1",
        "pd-vn-transgear-pivot-screw-1",
        "pd-vn-transgear-pivot-shim-1",
    }


def test_each_pivot_section_balloon_points_into_its_own_cut_face() -> None:
    tips = {stem: (side, y, r) for stem, side, y, r in drawing.PIVOT_BALLOON_TIPS}
    assert set(tips) == {
        name.rsplit("-", 1)[0] for name in drawing.PIVOT_VIEW_INSTANCES
    }
    shim, spring, spacer = joints.SHIM, joints.SPRING, joints.SPACER
    arm_geometry = joints.ARM
    floor = -(shim.THICKNESS + spring.MODEL_HEIGHT)
    arm_front = -(pivot_screw.SHOULDER_LEN - spacer.LENGTH)
    # (y span along the axis, r span off it) of each part's cut face, in the
    # screw's frame, head underside y 0.
    faces = {
        "pd-vn-transgear-pivot-screw": (
            (0.0, pivot_screw.HEAD_H),
            (pivot_screw.SOCKET_AF / math.sqrt(3.0), pivot_screw.HEAD_DIA / 2.0),
        ),
        "pd-vn-transgear-pivot-shim": ((-shim.THICKNESS, 0.0), (shim.ID / 2, shim.OD / 2)),
        "pd-vn-transgear-pivot-spring": (
            (floor, -shim.THICKNESS),
            (spring.ID / 2, spring.OD / 2),
        ),
        "pd-transgear-arm": (
            (arm_front, floor),
            (arm_geometry.PIVOT_BORE_DIA / 2, arm_geometry.SPOT_FACE_DIA / 2),
        ),
        "pd-transgear-pivot-spacer": (
            (-pivot_screw.SHOULDER_LEN, arm_front),
            (spacer.BORE_DIA / 2, spacer.OD / 2),
        ),
        "pd-support-bar": (
            (drawing.PIVOT_FRONT_FACE_Y, -pivot_screw.SHOULDER_LEN),
            (assembly.BAR.PIVOT_TAP_CSK_DIA / 2, drawing.PIVOT_FRAME_RADIUS_MM),
        ),
    }
    centre_y = drawing.PIVOT_VIEW_CENTRE_MM[1]
    for stem, (side, y, r) in tips.items():
        (y0, y1), (r0, r1) = faces[stem]
        assert y0 < y < y1, stem
        assert r0 < r < r1, stem
        # Inside the crop circle.
        assert math.hypot(r, y - centre_y) < drawing.PIVOT_FRAME_RADIUS_MM, stem
    # The spring's tip is on its cone's diagonal, inside its thin wall.
    _side, y, r = tips["pd-vn-transgear-pivot-spring"]
    assert y == pytest.approx((floor - shim.THICKNESS) / 2.0)
    assert r == pytest.approx((spring.ID + spring.OD) / 4.0)
    # Down the stack the tips alternate sides.
    order = sorted(tips.values(), key=lambda tip: -tip[1])
    assert [side for side, _y, _r in order] == ["right", "left"] * 3


def test_the_pivot_stake_note_points_at_the_front_mouth_clear_of_the_balloons() -> None:
    """Rule 23: SECTION A-A shows where the lock is, its pointer in the bar's
    metal at the front tap mouth and its text off the section and balloons."""
    y, r = drawing.PIVOT_STAKE_TIP
    front = -(pivot_screw.SHOULDER_LEN + BAR_DEPTH)
    csk_rim = assembly.BAR.PIVOT_TAP_CSK_DIA / 2.0
    # In the bar, under 1 mm from the front face and the countersink's rim.
    assert front < y < front + 1.0
    assert csk_rim < r < csk_rim + 1.0
    centre_y = drawing.PIVOT_VIEW_CENTRE_MM[1]
    assert math.hypot(r, y - centre_y) < drawing.PIVOT_FRAME_RADIUS_MM
    # Its tip is right of the axis; the bar's balloon points left.
    sides = {stem: side for stem, side, *_ in drawing.PIVOT_BALLOON_TIPS}
    assert sides["pd-support-bar"] == "left"
    assert drawing.PIVOT_STAKE_POINTS_TEXT in drawing.PIVOT_STAKE_NOTE
    assert drawing.PIVOT_STAKE_POINTS_TEXT in drawing.PIVOT_CAPTION
    assert drawing.PIVOT_STAKE_NOTE in drawing.sheet_texts(_unit_step_notes())

    lines = drawing.PIVOT_STAKE_NOTE.splitlines()
    width = max(map(len, lines)) * NOTE_CHAR_WIDTH
    height = len(lines) * NOTE_LINE_PITCH
    sx, sy = drawing.PIVOT_SECTION_CENTER
    radius = drawing.PIVOT_SECTION_RADIUS
    scale = drawing.PIVOT_SECTION_SCALE[0] / drawing.PIVOT_SECTION_SCALE[1] / 1000.0
    # The section is centred on the stack with its axis vertical, so the tip
    # stands r right of the circle's centre.
    tip_x = sx + r * scale
    column_x = sx + radius + drawing.PIVOT_BALLOON_GAP
    field_right = drawing.SHEET_TWO_RING_LIMITS[0] - drawing.SHEET_TWO_RING_GAP
    caption_y = drawing.PIVOT_SECTION_CAPTION_XY[1]
    right_tips = [
        tip_y
        for _stem, side, tip_y, _r in drawing.PIVOT_BALLOON_TIPS
        if side == "right"
    ]
    for front_side in (1.0, -1.0):
        left, top = drawing.pivot_stake_note_xy(tip_x, front_side)
        bottom = top - height
        # The whole text right of the tip: the leader leaves its left end.
        assert left - tip_x >= 0.005
        assert left + width < field_right
        # Outside the circle at the front face's end, the tip beyond the
        # text's near edge, so the leader runs away from the text.
        tip_y = sy - front_side * (y - centre_y) * scale
        if front_side > 0:
            assert bottom > sy + radius
            assert sy < tip_y < bottom
        else:
            assert top < sy - radius
            assert top < tip_y < sy
            # Above the native section caption with a line to spare.
            assert bottom - NOTE_LINE_PITCH > caption_y
        near = top if front_side < 0 else bottom
        assert math.hypot(left - tip_x, tip_y - near) < 0.015
        # Clear of the right balloon column, whichever way the axis runs.
        ys = sorted(
            (sy - front_side * (tip - centre_y) * scale for tip in right_tips),
            reverse=True,
        )
        for balloon_y in drawing.spread_balloon_column(ys, drawing.PIVOT_BALLOON_PITCH):
            dx = max(left - column_x, 0.0, column_x - (left + width))
            dy = max(bottom - balloon_y, 0.0, balloon_y - top)
            assert math.hypot(dx, dy) > BALLOON_RADIUS + 0.002
    with pytest.raises(ValueError):
        drawing.pivot_stake_note_xy(tip_x, 0.0)


def test_pivot_section_balloon_columns_keep_order_and_pitch() -> None:
    pitch = drawing.PIVOT_BALLOON_PITCH
    assert drawing.spread_balloon_column([0.05, 0.0, -0.05], pitch) == [
        pytest.approx(v) for v in (0.05, 0.0, -0.05)
    ]
    spread = drawing.spread_balloon_column([0.010, 0.008, 0.007], pitch)
    assert all(a - b >= pitch - 1e-12 for a, b in zip(spread, spread[1:]))
    assert sum(spread) == pytest.approx(0.025)
    with pytest.raises(ValueError):
        drawing.spread_balloon_column([0.0, 0.01], pitch)
    # Every balloon of either column stays inside the section's ring reach.
    scale = drawing.PIVOT_SECTION_SCALE[0] / drawing.PIVOT_SECTION_SCALE[1] / 1000.0
    sx, sy = drawing.PIVOT_SECTION_CENTER
    centre_y = drawing.PIVOT_VIEW_CENTRE_MM[1]
    reach = drawing.PIVOT_SECTION_RADIUS + drawing.BALLOON_RING_REACH
    assert drawing.PIVOT_SECTION_RADIUS + drawing.PIVOT_BALLOON_GAP < reach
    for flip in (1.0, -1.0):
        for column in ("left", "right"):
            ys = sorted(
                (
                    sy + flip * (y - centre_y) * scale
                    for _stem, side, y, _r in drawing.PIVOT_BALLOON_TIPS
                    if side == column
                ),
                reverse=True,
            )
            for balloon_y in drawing.spread_balloon_column(ys, pitch):
                assert abs(balloon_y - sy) < reach - 0.005


def test_the_actual_collar_disc_overlap_is_checked_before_final_platen_installation() -> None:
    """A static F-to-disc setting cannot certify all loaded overlapping patches."""
    assert _step_body("platen-hung").startswith("TRIAL-HANG")
    inspected = _step_body("collar-disc-air-inspected")
    assert "CHAIN OFF" in inspected
    assert f"REMOVE THE {_number('pd-platen')} PLATEN" in inspected
    assert "TRIAL PLATEN" not in inspected
    assert "ARM HELD IN ITS OPERATING LATCH POSE" in inspected
    assert " ".join(collar.COLLAR_DISC_AIR_PHRASE.split()) in inspected
    assert f"ONE DISC TURN = {disc.TEETH / knob_shaft.TEETH:g} KNOB TURNS" in inspected
    assert "REFIT THE PLATEN AND LATCH THE HANGER" in inspected
    assert "RE-CHECK THE OVERLAP AIR AND RACK MESH" in inspected
    assert "BIASED" not in inspected
    assert steps.COLLAR_DISC_AIR_MIN == collar.COLLAR_DISC_AIR_MIN
    assert "AT OVERLAP AFTER REFITTING AND LATCHING" in _step_body("fitup-accepted")
    keys = (
        "hook-pin-hole-match-drilled",
        "collar-shoulder-seated",
        "collar-disc-air-inspected",
        "fitup-accepted",
        "chain-closed",
    )
    positions = [steps.step_number(key) for key in keys]
    assert positions == sorted(positions)


def test_one_disc_cycle_reference_travel_is_one_feed_revolution() -> None:
    """The disc and feed rotate together; reducer input turns are not feed turns."""
    knob_turns_per_disc = disc.TEETH / knob_shaft.TEETH
    crank_turns_per_disc = (
        knob_turns_per_disc * sprocket.KNOB_TEETH / sprocket.CRANK_TEETH
    )
    assert (
        crank_turns_per_disc * paper_geometry.NET_RACK_TRAVEL_PER_CRANK_REV
    ) == pytest.approx(math.pi * feed_pinion.PITCH_DIA)


def test_the_rear_cup_is_pinned_and_the_nut_seats_on_the_faced_pilot() -> None:
    """R9-70's rear cup and wheel-float fit remain; the front drive is a true D."""
    knob = _step_body("knob-stack-fitted")
    for text in (
        f"{knob_shaft.END_FLOAT:.1f} FEELER AT THE BOSS",
        cup_pin.HOLE_TEXT,
        f"{cup.PIN_HOLE_FROM_FRONT:.1f} FROM THE CUP FRONT",
    ):
        assert text in knob, text
    seq = steps.SEQUENCE
    assert seq.index("pilot-faced-to-fit") < seq.index("knob-stack-fitted")
    assert seq.index("pilot-faced-to-fit") < seq.index("collar-shoulder-seated")
    assert f"{collar.PILOT_PROUD_TEXT} PROUD" in _step_body("pilot-faced-to-fit")
    seated = _step_body("collar-shoulder-seated")
    assert "NUT TIGHT ON THE PILOT." in seated
    # The nut is a static clamp (the D-flat and dowels drive): rule 23's
    # U-MHA-PD-13-no-lock holds only while nobody turns it to drive.
    assert seated.endswith("THUMBNUT IS A CLAMP ONLY; NEVER TURNED TO DRIVE.")


def test_the_knob_and_its_grip_are_defined_and_service_turns_the_crank() -> None:
    knob = _step_body("knob-stack-fitted")
    chain_step = steps.step_number("chain-closed")
    assert knob.endswith(
        "THIS SHAFT IS THE KNOB; ITS GRIP IS THE COLLAR: HOLD OR TURN THE KNOB BY "
        f"IT TILL STEP {chain_step}, THEN TURN THE CRANK."
    )
    assert "KNOB HELD" in _step_body("hanger-meshed")
    assert steps.SEQUENCE.index("knob-stack-fitted") < steps.SEQUENCE.index(
        "hanger-meshed"
    )
    assert _step_body("chain-run-accepted").startswith("TURN THE CRANK")
    for key in steps.SEQUENCE[chain_step - 1 :]:
        assert "TURN THE KNOB" not in _step_body(key), key


def test_the_fitted_collar_rear_face_reacts_on_the_actual_gear_shoulder() -> None:
    faced = _step_body("collar-rear-faced-to-fit")
    assert collar.BODY_FACE_PHRASE in faced
    assert "START LONG; STRIP AND FACE THE REAR" in faced
    assert "REFITTING WITH THE REAR FACE SEATED" in faced
    assert (
        f"FINISHED BODY WITHIN {_number('pd-transgear-drive-collar')}'S FITTED LIMITS"
    ) in faced
    seated = _step_body("collar-shoulder-seated")
    assert "D-BORE ON THE SHAFT D-FLAT" in seated
    assert "REAR FACE BEARING ON THE MHA-PD-08 12T FRONT FACE" in seated
    assert "ON THE DRIVE DOWELS" in seated
    assert collar.BODY_REAR_FACE_FROM_F == 0.0
    assert collar.LENGTH_FITTED_MIN <= collar.LENGTH <= collar.LENGTH_FITTED_MAX
    assert not {"collar-gap-measured", "collar-pinned"} & set(steps.SEQUENCE)


def test_the_fitup_steps_and_the_collar_note_share_facing_setting_and_stud_cut() -> None:
    """R9-30's shared fit phrases now describe shoulder seating, not core drilling."""
    note = " ".join(collar.FIT_UP_NOTE.split())
    for key, phrase in (
        ("collar-rear-faced-to-fit", collar.BODY_FACE_PHRASE),
        ("collar-rear-faced-to-fit", collar.FIT_UP_OFFSET_SET_TEXT),
        ("stud-end-cut", collar.STUD_CUT_PHRASE),
    ):
        assert phrase in _step_body(key), key
        assert phrase in note, key
    for text in drawing.sheet_texts(_unit_step_notes()):
        assert "THROUGH THE CORE" not in text
        assert "SPRING PIN IN THE SLOT" not in text
        assert "SLOTTED SHIM" not in text
    assert not hasattr(steps, "CLAMP_SLEEVE_OD")
    assert not hasattr(steps, "CLAMP_SLEEVE_ID")


def test_the_collar_is_faced_and_shoulder_seated_before_stud_cut_and_acceptance() -> None:
    order = [
        "hook-pin-hole-match-drilled",
        "fitup-pose-set",
        "collar-rear-faced-to-fit",
        "collar-shoulder-seated",
        "stud-end-cut",
        "collar-disc-air-inspected",
        "fitup-accepted",
    ]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == sorted(numbers)
    assert steps.SEQUENCE.index("fitup-accepted") == len(steps.SEQUENCE) - 3
    assert steps.step_number("collar-pins-pressed") < steps.step_number(
        "knob-stack-fitted"
    )


def test_the_cluster_float_and_pin_bands_print_their_spec_ranges() -> None:
    rear = _step_body("rear-bushing-faced-to-fit")
    assert f"DISC END FLOAT {cluster_fit.FLOAT_WINDOW_TEXT}" in rear
    assert cluster_fit.FIT_WINDOW_TEXT in _step_body("front-bushing-faced-to-fit")
    for key, bounds in (
        ("collar-pins-pressed", drive_pin.PROUD_RANGE),
        ("latch-pin-pressed", joints.LATCH_PIN_PROUD_RANGE),
    ):
        assert f"{bounds[0]:.2f} TO {bounds[1]:.2f} PROUD" in _step_body(key)


def test_the_hub_recess_is_in_m_and_in_the_disc_end_float() -> None:
    """Codex P2 (6c385465d): the hub stands up to HUB_NOSE_WINDOW behind the
    nose, so hub and disc reach the front bushing that much ahead of the
    step. m is read with them forward, so the recess cannot close it below
    FIT_WINDOW's minimum, and the front bushing's longest fit carries it; the
    rear bushing leaves the sleeve the float less the recess, so the disc's
    end float stays FLOAT_WINDOW (the disc-to-platen stack's term)."""
    recess = cluster_fit.HUB_NOSE_WINDOW
    longest = (
        cluster_fit.FRONT_CHAIN_NOMINAL
        + cluster_fit.FRONT_CHAIN_BAND
        + cluster_fit.FIT_WINDOW[1]
        + recess[1]
    )
    assert cluster_fit.FRONT_BUSHING_FITTED_MAX == pytest.approx(longest)
    assert front_bushing.BLANK_LENGTH_MIN >= longest + front_bushing.FACING_ALLOWANCE
    sleeve = cluster_fit.SLEEVE_FLOAT_WINDOW
    for r in recess:
        assert cluster_fit.FLOAT_WINDOW[0] <= sleeve[0] + r
        assert sleeve[1] + r <= cluster_fit.FLOAT_WINDOW[1] + 1e-9
    # The model, cluster rearward with the hub on the step, reads m forward.
    forward = (
        cluster_fit.SLEEVE_FLOAT_WINDOW_CENTRE + cluster_fit.HUB_NOSE_WINDOW_CENTRE
    )
    assert cluster_fit.DISC_FRONT_Z - forward - cluster_fit.F_Z == pytest.approx(
        cluster_fit.FIT_WINDOW_CENTRE
    )
    assert "CLUSTER, HUB AND DISC FORWARD, FEEL m" in _step_body(
        "front-bushing-faced-to-fit"
    )


def test_the_rear_bushing_blank_is_faced_to_the_gauged_gap_before_it_goes_on() -> None:
    """Codex P2 (724f78f26): the MHA-PD-24 blank is longer than the gap it
    fills (6.85 MIN against 6.30 nominal, cluster forward), so refitted
    unfaced it keeps the ring out of its groove. The step gauges that gap,
    sleeve rear face from the arm's front face, with the front bushing and
    ring on, faces the blank to it less the float, and only then puts it on
    the pin."""
    gap_nominal = (
        cluster_fit.REAR_CHAIN_NOMINAL
        - cluster_fit.FIT_WINDOW_CENTRE
        - cluster_fit.HUB_NOSE_WINDOW_CENTRE
    )
    assert rear_bushing.BLANK_LENGTH_MIN > gap_nominal
    lo, hi = cluster_fit.SLEEVE_REAR_FORWARD_FROM_ARM
    assert lo <= gap_nominal <= hi
    # The gap less the sleeve's float band is the length band the bushing's
    # sheet sets.
    sleeve = cluster_fit.SLEEVE_FLOAT_WINDOW
    assert lo - sleeve[1] == pytest.approx(rear_bushing.GAP_MIN)
    assert hi - sleeve[0] == pytest.approx(rear_bushing.GAP_MAX)
    rear = _step_body("rear-bushing-faced-to-fit")
    gauged = rear.index("DEPTH-GAUGE THE SLEEVE REAR FACE FROM THE ARM")
    faced = rear.index(f"BLANK TO THAT LESS {cluster_fit.SLEEVE_FLOAT_WINDOW_TEXT}")
    fitted = rear.index("BLANK ON")
    assert gauged < faced < fitted
    # The hung cluster carries no rear bushing until then.
    assert "NO REAR BUSHING YET" in _step_body("disc-cluster-hung")
    assert steps.step_number("disc-cluster-hung") < steps.step_number(
        "rear-bushing-faced-to-fit"
    )


def test_the_hub_is_faced_to_the_nose_before_the_disc_is_tapped() -> None:
    """R9-68: the hub's front face is faced to stand just behind the sleeve
    nose on the bench, disc seated and hub on the flat, before the flange
    holes are transferred; the front bushing then bears on the nose."""
    order = ["disc-cluster-assembled", "hub-faced-to-nose", "disc-taps-transferred"]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == list(range(numbers[0], numbers[0] + 3))
    faced = _step_body("hub-faced-to-nose")
    assert f"TILL {cluster_fit.HUB_NOSE_WINDOW_TEXT} BEHIND" in faced
    assert "ON THE NOSE TRAPS HUB AND DISC" in _step_body("disc-cluster-hung")


def test_the_disc_is_centred_to_its_running_bore_before_transfer_and_match_mark() -> None:
    """Pilot fit and a free span do not centre the assembled tooth spaces."""
    transferred = _step_body("disc-taps-transferred")
    assert (
        f"MANDREL IN THE {drawing._N['pd-transgear-feed-pinion']} BORE" in transferred
    )
    assert (
        f"WITH A \u00d8{disc.TOOTH_SPACE_GAUGE_PIN_DIA_MM:.3f} GAUGE PIN IN EACH "
        f"{drawing._N['pd-rack-pinion']} TOOTH SPACE IN TURN"
    ) in transferred
    tir = drawing.quality.toothspace_runout_tir_mm()
    assert f"TILL THE DIAL READS {tir:.2f} TIR MAX" in transferred
    for method in ("CERTIFIED", "RUNNING-BORE", "INDICATOR STATION", "INSPECTION"):
        assert method not in transferred
    ordered_actions = (
        "TAP THE DISC CENTRAL",
        "SPOT-DRILL THE DISC",
        "SCREWS.",
        f"RECHECK ALL {disc.TEETH} SPACES",
        "THEN MATCH-MARK DISC AND HUB",
    )
    locations = [transferred.index(action) for action in ordered_actions]
    assert locations == sorted(locations)
    assert "OD RUNOUT" not in transferred
    # joint_retention: pd-paper-drive/disc-screws is a static clamp, Lock.NONE.
    assert "LOCK" not in transferred


def test_the_plate_screws_are_cut_to_the_limit_the_lock_sweep_clears() -> None:
    """R9-44: cut off the mechanism, then refit the same screws before the
    hanger is pivoted."""
    order = ["arm-plate-fitted", "arm-plate-screws-cut", "hanger-pivoted"]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == list(range(numbers[0], numbers[0] + 3))
    body = _step_body("arm-plate-screws-cut")
    assert body.startswith(
        f"TAKE BOTH {_number('pd-vn-transgear-arm-plate-screw')} SCREWS OUT"
    )
    assert "REFIT THE SAME SCREWS IN THE SAME HOLES BEFORE PIVOTING THE HANGER" in body
    limit = f"FLUSH TO {joints.PLATE_SCREW_CUT_PROUD_MAX:.2f} PROUD"
    assert limit in body
    assert f"BREAK THE CUT EDGE {plate_screw.CUT_END_BREAK_TEXT}" in body
    assert joints.PLATE_SCREW_TIP_PROUD_MAX == joints.PLATE_SCREW_CUT_PROUD_MAX
    row = _config.parts("pd-vn-transgear-arm-plate-screw")
    assert " ".join(row["installation_notes"].split()) == (
        " ".join(plate_screw.PURCHASED_STOCK_NOTE.split())
    )
    assert f"PROUD {joints.PLATE_SCREW_CUT_PROUD_MAX:g} MAX" in plate_screw.PURCHASED_STOCK_NOTE
    assert f"CUT-END BREAK {plate_screw.CUT_END_BREAK_TEXT}" in plate_screw.PURCHASED_STOCK_NOTE
    # Positive control: the fit step itself does not mention the cut.
    assert "CUT" not in _step_body("arm-plate-fitted")


def _spare_world_point(monkeypatch, local):
    """Exercise the production row-vector transform without a COM connection."""
    transform = [value for row in assembly.ROT_X_NEG90 for value in row]
    transform += [value / 1000.0 for value in assembly.SPARE_GEAR_POS]
    transform += [1.0, 0.0, 0.0, 0.0]
    adapter = object()

    def component_transform(actual_adapter, name):
        assert actual_adapter is adapter
        assert name == "pd-transgear-removable-3"
        return transform

    monkeypatch.setattr(_assembly, "component_transform", component_transform)
    return _assembly.world_point(adapter, "pd-transgear-removable-3", local)


def test_spare_sprocket_transformed_underside_contacts_base_deck(monkeypatch):
    # The spec's plate is local Z=0..PLATE, identical in all tooth configs.
    underside = _spare_world_point(monkeypatch, [0.0, 0.0, 0.0])
    top = _spare_world_point(monkeypatch, [0.0, 0.0, seat_geometry.PLATE])
    assert underside[1] == pytest.approx(base.STACK_HEIGHT, rel=0, abs=1e-9)
    assert top[1] == pytest.approx(base.STACK_HEIGHT + seat_geometry.PLATE, rel=0, abs=1e-9)
    assert (underside[0], underside[2]) == (140.0, -75.0)
    assert (top[0], top[2]) == (140.0, -75.0)


def test_spare_t18_footprint_is_on_the_flat_deck(monkeypatch):
    # The deck's flat ends at its edge break (user ruling 2026-10-09: the
    # black deck x +-167.0, z +-130.25 stands DECK_RISE above the green land).
    radius = sprocket.outside_dia(sprocket.TEETH["T18"]) / 2.0
    for x, y, z in product((-radius, radius), (-radius, radius), (0.0, seat_geometry.PLATE)):
        world = _spare_world_point(monkeypatch, [x, y, z])
        assert abs(world[0]) < base.DECK_HALF_X - base.DECK_EDGE_BREAK
        assert abs(world[2]) < base.DECK_HALF_Z - base.DECK_EDGE_BREAK


def test_spare_storage_clears_nameplate_envelope_by_five_mm(monkeypatch):
    # Native top gate rejected the first deck-seating candidate: retaining
    # X=160/Z=-15 intersected the brass nameplate by 605.55 mm^3.
    radius = sprocket.outside_dia(sprocket.TEETH["T18"]) / 2.0
    plate_corners = [
        nameplate.mount_point(point)
        for point in product(
            (0.0, nameplate.PLATE_WIDTH),
            (0.0, nameplate.PLATE_HEIGHT),
            (-nameplate.PLATE_THICKNESS, 0.0),
        )
    ]
    spare_max_z = max(
        _spare_world_point(monkeypatch, [x, y, z])[2]
        for x, y, z in product(
            (-radius, radius), (-radius, radius), (0.0, seat_geometry.PLATE)
        )
    )
    assert spare_max_z <= min(point[2] for point in plate_corners) - 5.0




def _numbered_items() -> dict[str, str]:
    """Item numbers against the dict order, so plans must sort by them."""
    return {
        stem: str(len(drawing.BOM_PART_NUMBERS) - index)
        for index, stem in enumerate(drawing.BOM_PART_NUMBERS)
    }


def test_every_bom_item_is_ballooned_on_some_sheet() -> None:
    """Codex B1 (19e33c6c2): items 1-12 and the chain had no balloon."""
    items = _numbered_items()
    iso, inner = drawing.transgear_balloon_items(items)
    plans = (
        drawing.assembled_balloon_items(items),
        drawing.platen_balloon_items(items),
        iso,
        inner,
    )
    ballooned = [stem for plan in plans for stem, _item in plan]
    assert set(ballooned) == set(drawing.BOM_PART_NUMBERS)
    for plan in plans:
        assert [int(item) for _stem, item in plan] == sorted(
            int(item) for _stem, item in plan
        )
    # Only the removable is ballooned twice: on the mounted knob wheel (sheet 2) and
    # on the spare T18 on the deck (sheet 1), which the caption names.
    repeated = {stem for stem in ballooned if ballooned.count(stem) > 1}
    assert repeated == {"pd-transgear-removable"}
    spare = drawing.ASSEMBLED_BALLOON_ANCHORS["pd-transgear-removable"].instance
    assert spare == drawing.SPARE_INSTANCE == "pd-transgear-removable-3"
    # Edge-on in the front and right views the spare is a bare bar: hidden
    # there, shown and ballooned on the isometric only.
    for caption in drawing.ASSEMBLED_CAPTIONS.values():
        assert "T18 SPARE, STORED LOOSE" in " ".join(caption.split())


def test_the_exploded_sheet_balloons_exactly_the_platen_group() -> None:
    platen_group = {
        "pd-support-bar",
        "sh-column-clamp-front",
        "sh-column-clamp-back",
        "sh-vn-clamp-screw",
        "pd-platen",
        "pd-platen-rack",
        "pd-platen-guide",
        "pd-guide-lock",
        "pd-platen-clip",
        "pd-platen-paper",
        "sh-vn-brass-fillister-screw",
        "pd-vn-platen-clip-screw",
        "pd-vn-guide-lock-screw",
    }
    assert set(drawing.PLATEN_BALLOON_ANCHORS) == platen_group
    assert explode.SHOWN_STEMS == platen_group
    assert drawing.SHEET_NAMES[2] == "PLATEN AND SUPPORT"


def _platen_instances() -> list[explode.Instance]:
    instances = [explode.Instance(f"{stem}-1", stem) for stem in explode.SHOWN_STEMS]
    instances.append(explode.Instance("pd-rack-pinion-1", "pd-rack-pinion"))
    return instances


def test_the_explode_moves_only_the_platen_group_and_keeps_the_platen() -> None:
    plan = explode.plan_explode(_platen_instances())
    moved = {name for _step, names in plan for name in names}
    assert "pd-rack-pinion-1" not in moved
    assert "pd-platen-1" not in moved
    assert {name.rsplit("-", 1)[0] for name in moved} == (
        explode.SHOWN_STEMS - explode.STATIONARY_STEMS
    )
    # The guide screws leave with the guides' step, the clip screws with the
    # clips': the two screw families never share a step.
    for _step, names in plan:
        assert not {"sh-vn-brass-fillister-screw-1", "pd-vn-platen-clip-screw-1"} <= set(names)


def test_the_explode_refuses_a_model_missing_a_shown_family() -> None:
    instances = [i for i in _platen_instances() if i.stem != "pd-vn-platen-clip-screw"]
    with pytest.raises(ValueError, match="pd-vn-platen-clip-screw"):
        explode.plan_explode(instances)


def test_the_platen_group_is_built_and_hung_before_its_locks_are_set() -> None:
    """Codex B2: the steps started with the locks already on."""
    order = ["bar-clamped", "rack-soldered", "guides-screwed", "clips-fitted"]
    order += ["platen-hung", "guide-locks-set", "lock-seats-faced"]
    assert list(steps.SEQUENCE[: len(order)]) == order
    assert f"{steps.BAR_TOP_ABOVE_DECK:.1f} ABOVE THE BASE DECK" in _step_body(
        "bar-clamped"
    )
    # The round pair locates the bar before the slotted pair is tightened;
    # the step names it by its holes, as no package sheet defines END A.
    bar_clamped = _step_body("bar-clamped")
    assert "TIGHTEN THE ROUND-HOLE PAIR, THEN THE SLOTTED PAIR." in bar_clamped
    assert "END A" not in bar_clamped
    # The latched hook cannot take up a rack set off its band (rack-crest
    # ruling): the step prints the crest band itself.
    assert f"CRESTS {steps.RACK_CREST_TEXT} BELOW ITS BOTTOM EDGE" in _step_body(
        "rack-soldered"
    )
    assert steps.BAR_TOP_ABOVE_DECK == pytest.approx(
        assembly.BAR_TOP_Y - assembly.BASE_DECK_Y, abs=5e-4
    )
    assert steps.RACK_CREST_DROP == pytest.approx(
        assembly.PLATE_Y0 - assembly.RACK_TIP_Y, abs=1e-9
    )
    # Codex P2 (724f78f26): the step solders the rack flush; the model places
    # it so (the platen pose, not the rack, takes the mesh phasing).
    assert "ENDS FLUSH WITH THE PLATEN'S" in _step_body("rack-soldered")
    assert assembly.RACK_X0 == assembly.PLATE_X0
    # Every platen-group screw count the steps print is the model's.
    assert f"{drawing.GUIDE_SCREWS} " in _step_body("guides-screwed")
    assert drawing.GUIDE_SCREWS + drawing.CLIP_SCREWS == len(
        assembly.GUIDE_SCREW_XY
    ) + len(assembly.CLIP_SCREW_XY)


def test_the_chain_is_closed_and_run_after_the_collar_is_accepted() -> None:
    """Codex B3: routing, closure, adjustment and a functional run."""
    assert steps.SEQUENCE[-3:] == (
        "fitup-accepted",
        "chain-closed",
        "chain-run-accepted",
    )
    closed = _step_body("chain-closed")
    assert f"LOOP {chain.LINK_COUNT} PITCHES" in closed
    assert "ANSI #25" in closed
    assert f"OVER THE {sprocket.KNOB_CONFIG} AND THE {sprocket.CRANK_CONFIG}" in closed
    assert chain.LINK_COUNT % 2 == 0
    assert chain.LINK_PITCH == sprocket.CHAIN_PITCH
    assert chain.CENTRELINE_LEN == pytest.approx(
        chain.LINK_COUNT * sprocket.CHAIN_PITCH
    )
    assert drawing.CHAIN_QUANTITIES == {
        "sh-vn-chain-link--InnerLink": chain.LINK_COUNT // 2,
        "sh-vn-chain-link--OuterLink": chain.LINK_COUNT // 2 - 1,
        "pd-vn-chain-connecting-link": 1,
    }
    assert sum(drawing.CHAIN_QUANTITIES.values()) == chain.LINK_COUNT
    assert (
        f"{chain.LINK_COUNT // 2} {_number('sh-vn-chain-link--InnerLink')} INNER AND "
        f"{chain.LINK_COUNT // 2 - 1} {_number('sh-vn-chain-link--OuterLink')} OUTER LINKS"
    ) in closed
    assert f"THE {_number('pd-vn-chain-connecting-link')} #25 CONNECTING LINK" in closed
    for stem in drawing.CHAIN_QUANTITIES:
        assert "ANSI #25" in drawing.BOM_DESCRIPTIONS[stem]
    assert "CONNECTING LINK" in closed and "CLOSED END LEADING" in closed
    assert "NO TENSIONING" in closed
    run = _step_body("chain-run-accepted")
    assert "EVERY TOOTH" in run and "TOUCHES NOTHING" in run
    assert "LOOPED" not in _step_body("collar-shoulder-seated")


def test_the_setting_and_the_acceptance_offsets_are_told_apart() -> None:
    """Codex clarity: 0.05 ±0.05 sets, 0.05 ±0.10 accepts; the knob wheel
    behind the crank wheel within the acceptance passes."""
    setting = _step_body("collar-rear-faced-to-fit")
    accepted = _step_body("fitup-accepted")
    assert f"STEP {steps.step_number('fitup-accepted')} RE-CHECKS" in setting
    assert f"STEP {steps.step_number('collar-rear-faced-to-fit')}'S SETTING" in accepted
    behind = steps.OFFSET_ACCEPT_TOL - collar.FIT_UP_OFFSET_TARGET
    assert behind > 0.0
    assert f"UP TO {behind:.2f} BEHIND PASSES" in accepted


def test_the_knob_wheel_is_read_held_back_on_its_seat() -> None:
    """Codex P2 on b2eb9a0e1: read the wheel held back on its seat, not
    floated forward under the nut. Its actual float is paid once in service."""
    pose = _step_body("fitup-pose-set")
    assert steps.KNOB_HELD_BACK_TEXT in pose
    assert steps.KNOB_HELD_BACK_TEXT in _step_body("collar-rear-faced-to-fit")
    accepted = _step_body("fitup-accepted")
    assert accepted.startswith(f"ACCEPT, IN STEP {steps.step_number('fitup-pose-set')}")
    low, high = steps.ACCEPTED_CHAIN_OFFSET_IN_SERVICE
    half_plate_spread = (max(seat_geometry.PLATE_BAND) - min(seat_geometry.PLATE_BAND)) / 2.0
    assert (low, high) == pytest.approx(
        (
            -(collar.FIT_UP_OFFSET_TARGET + steps.OFFSET_ACCEPT_TOL)
            - half_plate_spread
            - collar.CRANK_END_PLAY_MAX
            - collar.KNOB_END_FLOAT_MAX
            - max(collar.KNOB_FLOAT_RANGE),
            steps.OFFSET_ACCEPT_TOL
            - collar.FIT_UP_OFFSET_TARGET
            + half_plate_spread
            + collar.HANGER_AXIAL_PLAY_MAX,
        ),
        abs=1e-9,
    )
    # The float is in the budget, forward: the contract's set range and the
    # acceptance both lose it at their forward ends.
    assert collar.CHAIN_OFFSET_IN_SERVICE[0] == pytest.approx(
        collar.CHAIN_SET_RANGE[0]
        - collar.CRANK_END_PLAY_MAX
        - collar.KNOB_END_FLOAT_MAX
        - max(collar.KNOB_FLOAT_RANGE)
    )
    assert max(abs(low), abs(high)) <= collar.CHAIN_OFFSET_LIMIT


def test_a_balloon_ring_is_centred_in_its_room_or_refused() -> None:
    limits = (0.2, 0.1, 0.4, 0.3)
    outline = (0.0, 0.0, 0.1, 0.1)
    dx, dy = drawing.ring_fit_shift(outline, limits, name="t")
    ring = drawing._grown(
        (outline[0] + dx, outline[1] + dy, outline[2] + dx, outline[3] + dy),
        drawing.BALLOON_RING_REACH,
    )
    assert ring[0] - limits[0] == pytest.approx(limits[2] - ring[2])
    assert ring[1] - limits[1] == pytest.approx(limits[3] - ring[3])
    with pytest.raises(ValueError, match="width"):
        drawing.ring_fit_shift((0.0, 0.0, 0.19, 0.1), limits, name="t")


# Farm run 20261001T142942518Z (8689c2a0d) read sheet 1's isometric at 1:3:
# its outline 187.7 mm tall; its width passed, so at most 149 mm.
ISO_OUTLINE_AT_1_3 = (0.250, 0.075, 0.250 + 0.149, 0.075 + 0.1877)


class _PaddedView:
    """A view whose read-back outline is its content, which scales, plus a
    fixed sheet-space padding, which does not (SolidWorks' outline)."""

    def __init__(self, size_m, at_scale, padding_m):
        self.content = tuple(
            (side - padding_m) / (at_scale[0] / at_scale[1]) for side in size_m
        )
        self.padding = padding_m
        self.applied = []

    def outline_at(self, scale):
        self.applied.append(scale)
        ratio = scale[0] / scale[1]
        width, height = (side * ratio + self.padding for side in self.content)
        return (0.2, 0.1, 0.2 + width, 0.1 + height)


def test_the_sheet_one_isometric_ring_fits_at_the_sheet_scale() -> None:
    """The 1:3 isometric's ring overflowed natively (221.7 > 198.0 mm); at the
    sheet's scale the same view's ring fits, whatever its fixed padding."""
    with pytest.raises(ValueError, match=r"height 221\.7 mm > room 198\.0 mm"):
        drawing.ring_fit_shift(
            ISO_OUTLINE_AT_1_3, drawing.ISO_RING_LIMITS, name="sheet 1 isometric"
        )
    size = (
        ISO_OUTLINE_AT_1_3[2] - ISO_OUTLINE_AT_1_3[0],
        ISO_OUTLINE_AT_1_3[3] - ISO_OUTLINE_AT_1_3[1],
    )
    assert drawing.ISO_SCALE_LADDER[0] == drawing.ASSEMBLED_SCALE
    for padding in (0.0, 0.0127, 0.0254):
        view = _PaddedView(size, (1.0, 3.0), padding)
        scale, _outline = drawing.step_down_to_fit(
            view.outline_at, drawing.ISO_SCALE_LADDER, drawing.ISO_RING_LIMITS, name="t"
        )
        assert scale == drawing.ASSEMBLED_SCALE, padding
    # Every scale the isometric may take has its caption.
    assert set(drawing.ASSEMBLED_CAPTIONS) == set(drawing.ISO_SCALE_LADDER)


def test_the_exploded_view_steps_down_on_its_native_outline() -> None:
    """Codex P2 (aa9d3b681): a 211.9 mm wide outline at 1:3 with 12.7 mm of
    fixed padding, scaled whole, predicts a 192.9 mm ring at 1:4 in the 193.0
    room; natively it is 196.1, so the view must go on to 1:5 (166.2)."""
    ladder = drawing.EXPLODED_SCALE_LADDER
    limits = drawing.EXPLODED_RING_LIMITS
    assert limits[2] - limits[0] == pytest.approx(0.193)
    view = _PaddedView((0.2119, 0.100), (1.0, 3.0), 0.0127)
    scale, outline = drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")
    assert scale == (1.0, 5.0)
    assert view.applied == list(ladder)
    assert outline == view.outline_at(scale)
    # A view that fits as placed is not rescaled.
    view = _PaddedView((0.120, 0.120), (1.0, 3.0), 0.0127)
    assert (
        drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")[0]
        == (ladder[0])
    )
    assert view.applied == [ladder[0]]
    # Only when 1:5 still overflows does it refuse, naming every scale.
    view = _PaddedView((0.5, 0.5), (1.0, 3.0), 0.0127)
    with pytest.raises(ValueError, match=r"no t scale fits: .*1:3.*1:4.*1:5"):
        drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")
    assert set(drawing.EXPLODED_CAPTIONS) == set(ladder)


def test_the_hook_is_set_on_a_meshed_and_run_hanger() -> None:
    """Codex (8b5e1f354) / R9-62: the hook was match-drilled with the hanger
    "latched" but the pinion-in-rack mesh never set nor the platen run."""
    keys = ("latch-hook-fitted", "hanger-meshed", "hook-pin-hole-match-drilled")
    fitted, meshed, drilled = (steps.step_number(key) for key in keys)
    assert meshed == fitted + 1 and drilled == meshed + 1
    domain = _unit_operating_domain()
    text = drawing._step_text(operating_domain=domain)
    fit = " ".join(text["latch-hook-fitted"].split())
    assert "ITS PIN HOLE IS NOT YET DRILLED" in fit
    mesh = " ".join(text["hanger-meshed"].split())
    assert mesh.startswith(
        f"SWING THE HANGER UP TILL THE {_number('pd-transgear-feed-pinion')} TEETH"
    )
    for method in ("RECEIVING RECORD", "ADMISSION", "TRAVELER"):
        assert method not in mesh
    assert "ALIGN A FEED TOOTH CENTRE DIRECTLY BELOW A RACK SPACE CENTRE" in mesh
    assert f"SET {steps.RACK_DATUM_BACKLASH_TEXT} PLATEN SHAKE AT THAT DATUM" in mesh
    assert "(DIAL ALONG THE RACK)" in mesh
    assert domain.operating_window_text in mesh
    assert drawing.OPERATING_DIRECTION_TEXT in mesh
    assert "RUN THAT WINDOW: NO TIGHT SPOT, SHAKE AT EVERY TOOTH" in mesh
    assert "STOP BEFORE EITHER END LIMIT" in mesh
    assert "RESET ONLY WITH FEED DISENGAGED" in mesh
    assert "FULL TRAVEL" not in mesh
    hook = " ".join(text["hook-pin-hole-match-drilled"].split())
    assert hook.startswith("HOLDING THAT MESH")
    # Codex P1 on b2eb9a0e1: set clear of the pin, the unclamped arm fell
    # through the hole's clearance and opened the feed mesh.
    pin = drawing._N["pd-vn-transgear-latch-pin"]
    assert f"ITS HOLE'S LOWER EDGE ON THE {pin} PIN" in hook
    assert "CLEAR" not in hook
    # The one-piece hook's pin hole is drilled from the pin at the set mesh,
    # then the part is hardened: no fitter-measured set position remains.
    assert "DRAWN PLACE" not in hook
    # Rule 24: the heat treatment is the hook drawing's; the re-run re-checks
    # step 24's datum shake (rule 4: the drilled hole must keep that band).
    hook_number = drawing._N["pd-latch-hook"]
    assert f"HARDEN AND TEMPER PER {hook_number}." in hook
    assert "BLUE" not in hook
    assert hook.endswith(
        "UNCLAMP, LATCH, RE-RUN THE DEFINED ENGAGED-FEED WINDOW; RE-CHECK "
        f"{steps.RACK_DATUM_BACKLASH_TEXT} SHAKE AT THE DATUM."
    )


def test_the_loaded_rack_check_is_one_dial_run_over_the_engaged_window() -> None:
    body = _step_body("loaded-rack-geometry-checked")
    assert body.startswith("HANGER LATCHED, PAPER LOADED. TRAVEL: TURN THE KNOB")
    travel, backlash = body.split(" BACKLASH: ")
    assert "RUN THE PLATEN THROUGH THE WHOLE ENGAGED WINDOW: NO TIGHT SPOT" in travel
    assert "KNOB HELD" not in travel
    assert backlash.startswith("KNOB HELD, ROCK THE PLATEN ALONG THE RACK")
    for method in ("UNCERTAINTY", "RE-ZERO", "DATUM", "REJECT"):
        assert method not in body
    assert steps.step_number("hook-pin-hole-match-drilled") < steps.step_number(
        "loaded-rack-geometry-checked"
    ) < steps.step_number("fitup-pose-set")
    assert drawing.FITUP_CHAIN_KEY == "loaded-rack-geometry-checked"


def test_the_reducer_is_clocked_once_with_an_ordinary_limit() -> None:
    body = _step_body("fitup-pose-set")
    assert body.startswith("HANGER LATCHED.")
    assert steps.KNOB_HELD_BACK_TEXT in body
    clock = drawing.quality.reducer_setup_clock_deviation_mm()
    assert (
        "TURN THE DISC SO, ON THE LINE THROUGH THE KNOB AND CLUSTER AXES, A "
        f"{disc.TEETH}T TOOTH STANDS CENTRED IN A {knob_shaft.TEETH}T GAP, "
        f"WITHIN {clock:.2f} AT THE PITCH CIRCLE"
    ) in body
    assert body.endswith("TURN THE KNOB: NO TIGHT SPOT, SHAKE AT EVERY TOOTH.")
    for method in ("UNCERTAINTY", "RE-ZERO", "RE-CLOCK", "ABSOLUTE", "REJECT"):
        assert method not in body
    assert steps.step_number("knob-stack-fitted") < steps.step_number("fitup-pose-set")
    assert steps.step_number("fitup-pose-set") < steps.step_number("chain-closed")


def test_the_feed_mesh_stays_on_the_hook_run_and_passes_its_closed_form_gates() -> None:
    assert assembly.RACK_MESH_EXT == pytest.approx(feed_pinion.RACK_MESH_EXTENSION)
    assert rack_setup.RACK_DATUM_BACKLASH_RANGE == feed_pinion.RACK_BACKLASH_RANGE
    height = assembly.RACK_PITCH_Y - assembly.STUD_XY[1]
    assert height == pytest.approx(feed_pinion.RACK_AXIS_DISTANCE)
    low, high = rack_setup.RACK_DATUM_MODEL_AXIS_DISTANCE_RANGE
    assert low < height < high
    # A mesh change at the stud turns the hanger about P: the pin crosses the
    # hook's straight run by the change over the stud's lever, and the
    # match-drilled hole with its wall must stay on that run.
    hook_geometry = assembly.HOOK
    lever = hook_geometry.HOLE_STATION / (
        assembly.ARM.PIN_STATION * math.cos(math.radians(assembly.ARM_ANGLE_DEG))
    )
    room = hook_geometry.PIN_HOLE_DIA / 2.0 + assembly.HOOK_SPEC.WALL_TARGET
    for end in (low, high):
        shift = abs(end - height) * lever
        assert shift + room < hook_geometry.RUN_ABOVE_HOLE
        assert shift + room < hook_geometry.RUN_BELOW_HOLE
    assert assembly._assert_rack_mesh() == rack_setup.feed_rack_operating_domain()


def test_the_native_feed_mesh_rejects_a_height_outside_its_actual_datum(monkeypatch) -> None:
    height = rack_setup.RACK_DATUM_MODEL_AXIS_DISTANCE_RANGE[1] + feed_pinion.MODULE_MM
    monkeypatch.setattr(assembly, "RACK_MESH_EXT", height - feed_pinion.PITCH_DIA / 2.0)
    monkeypatch.setattr(assembly, "RACK_PITCH_Y", assembly.STUD_XY[1] + height)
    with pytest.raises(ValueError):
        assembly._assert_rack_mesh()


def test_native_rack_pose_reads_the_cut_end_and_running_axis_with_all_loaded_motion(
    monkeypatch,
) -> None:
    """No nominal rack-gap phase or sleeve-profile centre substitutes for either datum."""
    seen = []
    points = {
        ("actual-rack", (0.0, 0.0, 0.0)): [-30.0, 0.0, 0.0],
        ("actual-rack", (1.0, 0.0, 0.0)): [-29.0, 0.0, 0.0],
        (
            "actual-rack",
            (
                0.0, assembly.RACK_BAR_HEIGHT - assembly.RACK_ADDENDUM,
                assembly.RACK_BACK_Z - (assembly.FEED_Z0 - assembly.FEED_FACE / 2.0),
            ),
        ): [-30.0, feed_pinion.RACK_AXIS_DISTANCE, 0.0],
        (
            "actual-stud",
            (0.0, 0.0, assembly.PIN_Z0 - (assembly.FEED_Z0 - assembly.FEED_FACE / 2.0)),
        ): [2.0, 0.0, 0.0],
    }

    def native_point(adapter, name, local):
        seen.append((name, tuple(local)))
        return points[name, tuple(local)]

    observed = {}

    def require_native_travel(**kwargs):
        observed.update(kwargs)

    # Deliberately synthetic: tests coordinate forwarding, not the source grade.
    monkeypatch.setattr(
        paper_geometry, "feed_running_axis_x_displacement_band_mm", lambda: (-0.04, 0.07)
    )
    monkeypatch.setattr(assembly, "world_point", native_point)
    domain = SimpleNamespace(require_machine_travel_mm=require_native_travel)
    assembly._assert_native_rack_operating_pose(object(), domain, "actual-rack", "actual-stud")
    assert observed["rack_left_end_x_band_mm"] == (-30.0, -30.0)
    assert observed["running_axis_x_band_mm"] == pytest.approx((1.96, 2.07))
    assert len(seen) == 4


def test_the_native_default_pose_and_whole_loaded_axis_family_fit_the_end_window(
    monkeypatch,
) -> None:
    """Exercise real readback guards with bounded unit limits, not a contact proof."""
    domain = _unit_operating_domain()
    pin_station = assembly.PIN_Z0 - (assembly.FEED_Z0 - assembly.FEED_FACE / 2.0)

    def nominal_native_point(adapter, name, local):
        if name == "actual-rack":
            return [
                assembly.RACK_X0 + local[0],
                assembly.RACK_Y0 - local[1],
                assembly.RACK_BACK_Z - local[2],
            ]
        assert name == "actual-stud" and tuple(local) == (0.0, 0.0, pin_station)
        return [assembly.STUD_XY[0], assembly.STUD_XY[1], 0.0]

    monkeypatch.setattr(assembly, "world_point", nominal_native_point)
    assembly._assert_native_rack_operating_pose(object(), domain, "actual-rack", "actual-stud")
    motion_low, motion_high = paper_geometry.feed_running_axis_x_displacement_band_mm()
    allowed_low, allowed_high = domain.axis_from_left_end_limits_mm
    domain.require_axis_distance_band_mm(
        (
            assembly.STUD_XY[0] + motion_low - assembly.RACK_X0,
            assembly.STUD_XY[0] + motion_high - assembly.RACK_X0,
        )
    )
    # A nominal point on a printed edge is insufficient if any allowed load
    # moves the actual axis beyond that edge.
    if motion_high > 0.0:
        edge = allowed_high
    else:
        assert motion_low < 0.0
        edge = allowed_low
    with pytest.raises(ValueError, match="cut-end overrun"):
        domain.require_axis_distance_band_mm((edge + motion_low, edge + motion_high))


def test_native_rack_height_is_observed_not_assumed_from_the_recipe(monkeypatch) -> None:
    observed = []
    bad_height = rack_setup.RACK_DATUM_MODEL_AXIS_DISTANCE_RANGE[1] + feed_pinion.MODULE_MM

    def native_point(adapter, name, local):
        if name == "actual-stud":
            return [0.0, 0.0, 0.0]
        if local[1] != 0.0:
            return [-30.0, bad_height, 0.0]
        return [-30.0 + local[0], 0.0, 0.0]

    monkeypatch.setattr(assembly, "world_point", native_point)
    domain = SimpleNamespace(
        require_machine_travel_mm=lambda **kwargs: observed.append(kwargs)
    )
    with pytest.raises(ValueError):
        assembly._assert_native_rack_operating_pose(
            object(), domain, "actual-rack", "actual-stud"
        )
    assert not observed


def test_a_direct_datum_reader_cannot_widen_the_printed_setup_band() -> None:
    low, high = rack_setup.RACK_DATUM_BACKLASH_RANGE
    span = high - low
    with pytest.raises(ValueError, match="datum setup band leaves"):
        rack_setup.require_feed_rack_datum_axis_distance(
            feed_pinion.RACK_AXIS_DISTANCE, (low - span, high + span)
        )


def test_note_formatting_is_explicit_about_its_supplied_window() -> None:
    domain = _unit_operating_domain()
    notes = drawing.format_step_notes(operating_domain=domain)
    assert domain.operating_window_text in notes.fitup_steps.replace("\n   ", " ")
    assert (notes.platen_steps, notes.fitup_notes, notes.chain_notes) == drawing._step_columns(
        operating_domain=domain
    )
    assert drawing.sheet_texts(notes)[:5] == (
        notes.platen_steps, *notes.fitup_notes, *notes.chain_notes,
    )


def test_drawing_notes_print_the_window_checked_against_the_paper_sweep() -> None:
    notes = drawing.require_step_notes()
    assert notes == drawing.format_step_notes(operating_domain=rack_setup.feed_rack_operating_domain())


@pytest.mark.parametrize(
    ("recording", "message"),
    (
        (
            {
                "paper_left_inset_band_mm": (10.0, 10.0),
                "paper_width_band_mm": (300.0, 300.0),
                "pen_x_from_running_axis_band_mm": (0.0, 0.0),
            },
            "required paper stroke",
        ),
        (
            {
                "paper_left_inset_band_mm": (255.0, 255.0),
                "paper_width_band_mm": (20.0, 20.0),
                "pen_x_from_running_axis_band_mm": (0.0, 0.0),
            },
            "cut-end overrun",
        ),
    ),
)
def test_the_notes_refuse_a_paper_sweep_the_finite_rack_cannot_carry(
    recording, message, monkeypatch,
) -> None:
    monkeypatch.setattr(paper_geometry, "recording_paper_sweep_bands_mm", lambda: recording)
    with pytest.raises(ValueError, match=message):
        drawing.require_step_notes()


@pytest.mark.parametrize(
    ("fault", "exception", "message"),
    (
        ("orientation", RuntimeError, "cut-end datum is not along"),
        ("end-overrun", ValueError, "cut-end overrun"),
    ),
)
def test_native_rack_readback_rejects_wrong_cut_datum_or_end_overrun(
    fault, exception, message, monkeypatch,
) -> None:
    """Bounded native coordinates exercise real guards, not physical qualification."""
    domain = _unit_operating_domain()
    rack_left_x = -30.0
    axis_x = rack_left_x + domain.axis_from_left_end_limits_mm[1] + 1.0

    def native_point(adapter, name, local):
        if name == "actual-stud":
            return [axis_x, 0.0, 0.0]
        assert name == "actual-rack"
        if local[1] != 0.0:
            return [rack_left_x, feed_pinion.RACK_AXIS_DISTANCE, 0.0]
        dx = local[0] * (0.5 if fault == "orientation" else 1.0)
        return [rack_left_x + dx, 0.0, 0.0]

    monkeypatch.setattr(assembly, "world_point", native_point)
    with pytest.raises(exception, match=message):
        assembly._assert_native_rack_operating_pose(
            object(), domain, "actual-rack", "actual-stud"
        )


class _DrawnInstance:
    def __init__(self, name: str) -> None:
        self.instance = name
        self.Name = f"pd-paper-drive/{name}@pd-paper-drive"
        self.Visible = None  # never written: the sheet's default


def test_spare_is_hidden_edge_on_and_shown_on_the_ballooned_isometric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seat = stub_seat(
        monkeypatch, drawing,
        keep=("_place_assembled_sheet", "_hide_instances", "_set_instance_visibility"),
    )
    seat._early_bound.side_effect = lambda obj, _interface: obj
    cx = sum(drawing.ISO_RING_LIMITS[0::2]) / 2.0
    cy = sum(drawing.ISO_RING_LIMITS[1::2]) / 2.0
    seat._native_outline_at.return_value = (
        lambda _scale: (cx - 0.001, cy - 0.001, cx + 0.001, cy + 0.001)
    )
    names = (drawing.SPARE_INSTANCE, "pd-transgear-removable-1", "pd-platen-rack-1")
    views: dict[str, tuple[object, list[_DrawnInstance]]] = {}

    def place_view(_adapter, _path, orientation, _x, _y, *, scale):
        drawn = [_DrawnInstance(name) for name in names]
        root = SimpleNamespace(GetChildren=lambda: tuple(drawn))
        views[orientation] = (SimpleNamespace(RootDrawingComponent2=lambda _all: root), drawn)
        return views[orientation][0]

    seat.place_view.side_effect = place_view
    iso = drawing._place_assembled_sheet(MagicMock())

    assert set(views) == {"*Front", "*Right", "*Isometric"}
    for orientation in ("*Front", "*Right"):
        shown = {drawn.instance: drawn.Visible for drawn in views[orientation][1]}
        assert shown == {name: name != drawing.SPARE_INSTANCE for name in names}
    # The returned isometric is the ballooned one, its instances untouched.
    assert iso is views["*Isometric"][0]
    assert all(drawn.Visible is None for drawn in views["*Isometric"][1])


def _native_pd_component(name, stem, configuration, *, origin=None):
    transform = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    transform.extend(value / 1000.0 for value in (origin or (0.0, 0.0, 0.0)))
    return SimpleNamespace(
        Name2=name,
        GetPathName=lambda: f"C:/native/{stem}.SLDPRT",
        ReferencedConfiguration=configuration,
        ComponentReference="",
        Transform2=SimpleNamespace(ArrayData=transform),
    )


def _native_chain_fixture(monkeypatch):
    monkeypatch.setattr(assembly, "_early_bound", lambda obj, *_args: obj)
    monkeypatch.setattr(_assembly, "_early_bound", lambda obj, *_args: obj)
    monkeypatch.setattr(_assembly, "_POSE_LEDGER", {})
    monkeypatch.setattr(_component_references, "_early_bound", lambda obj, *_args: obj)
    components = []
    for station in range(chain.LINK_COUNT):
        stem = assembly.CHAIN_LINK_STEM
        configuration = (
            assembly.INNER_LINK_CONFIGURATION if station % 2 == 0
            else assembly.OUTER_LINK_CONFIGURATION
        )
        if station == chain.LINK_COUNT - 1:
            stem, configuration = assembly.CONNECTING_LINK_STEM, "Default"
        # Native suffixes deliberately run opposite to semantic loop ordinals.
        component = _native_pd_component(
            f"{stem}--{configuration}-{901 - station * 7}",
            stem,
            configuration,
            origin=assembly._chain_station_point(station),
        )
        # Pattern copies may initially inherit one seed reference.
        component.ComponentReference = f"{configuration}:1"
        components.append(component)
    model = MagicMock()
    model.GetComponents.side_effect = lambda _top_only: tuple(reversed(components))
    model.GetComponentByName.side_effect = lambda name: next(
        (component for component in components if component.Name2 == name), None
    )
    model.ForceRebuild3.return_value = True
    return SimpleNamespace(currentModel=model), components


def test_chain_roles_follow_validated_loop_stations_not_native_indices(monkeypatch):
    adapter, components = _native_chain_fixture(monkeypatch)
    model = adapter.currentModel
    names = assembly._assign_chain_references(adapter)
    assert len(names) == 67
    assert names["@InnerLink:1"] == components[0].Name2
    assert names["@InnerLink:34"] == components[66].Name2
    assert names["@OuterLink:33"] == components[65].Name2
    assert len({component.ComponentReference for component in components[:-1]}) == 67
    model.ForceRebuild3.assert_called_once_with(False)
    # Drawing simplification may change only the derived suffix.
    for component in components:
        component.ReferencedConfiguration += " Simplified"
    assert assembly._chain_reference_names(model) == names


@pytest.mark.parametrize("fault", ("wrong-member", "duplicate-station", "off-plane", "missing"))
def test_chain_station_census_rejects_wrong_or_duplicate_members(monkeypatch, fault):
    adapter, components = _native_chain_fixture(monkeypatch)
    if fault == "wrong-member":
        components[3].ReferencedConfiguration = assembly.INNER_LINK_CONFIGURATION
    elif fault == "duplicate-station":
        components[3].Transform2.ArrayData = components[1].Transform2.ArrayData[:]
    elif fault == "off-plane":
        components[3].Transform2.ArrayData[11] += 0.001
    else:
        components.pop(3)
    with pytest.raises(RuntimeError):
        assembly._assign_chain_references(adapter)


def test_chain_roles_are_read_back_after_pattern_rebuild(monkeypatch):
    adapter, components = _native_chain_fixture(monkeypatch)
    model = adapter.currentModel

    def overwrite_inherited_references(_top_only):
        for component in components[0:-1:2]:
            component.ComponentReference = "InnerLink:1"
        return True

    model.ForceRebuild3.side_effect = overwrite_inherited_references
    with pytest.raises(RuntimeError, match="duplicated"):
        assembly._assign_chain_references(adapter)


def test_chain_reference_assignment_refuses_failed_native_rebuild(monkeypatch):
    adapter, components = _native_chain_fixture(monkeypatch)
    model = adapter.currentModel
    names_before = [component.Name2 for component in components]
    configurations_before = [
        component.ReferencedConfiguration for component in components
    ]
    transforms_before = [
        list(component.Transform2.ArrayData) for component in components
    ]
    connecting_reference = components[-1].ComponentReference
    model.ForceRebuild3.return_value = False

    with pytest.raises(RuntimeError, match="chain component reference rebuild failed"):
        assembly._assign_chain_references(adapter)

    model.ForceRebuild3.assert_called_once_with(False)
    # No post-rebuild association census can certify a failed native solve.
    assert model.GetComponents.call_count == 1
    roles = (assembly.INNER_LINK_CONFIGURATION, assembly.OUTER_LINK_CONFIGURATION)
    expected_references = [
        f"{roles[station % 2]}:{station // 2 + 1}"
        for station in range(chain.LINK_COUNT - 1)
    ]
    assert [component.ComponentReference for component in components[:-1]] == (
        expected_references
    )
    assert len(set(expected_references)) == 67
    assert components[-1].ComponentReference == connecting_reference
    assert [component.Name2 for component in components] == names_before
    assert [
        component.ReferencedConfiguration for component in components
    ] == configurations_before
    assert [
        list(component.Transform2.ArrayData) for component in components
    ] == transforms_before


def test_chain_pattern_rebuild_rebinds_existing_pose_witnesses(monkeypatch):
    adapter, components = _native_chain_fixture(monkeypatch)
    model = adapter.currentModel
    placed_stations = (0, 1, chain.LINK_COUNT - 2, chain.LINK_COUNT - 1)
    before = {station: component.Name2 for station, component in enumerate(components)}
    arrays = [list(component.Transform2.ArrayData) for component in components]
    transforms = [component.Transform2 for component in components]
    configurations = [component.ReferencedConfiguration for component in components]
    connecting_reference = components[-1].ComponentReference
    entries = {}
    for station in placed_stations:
        array = arrays[station]
        _assembly._ledger_record(
            before[station],
            [value * 1000.0 for value in array[9:12]],
            [array[0:3], array[3:6], array[6:9]],
        )
        entries[station] = _assembly._POSE_LEDGER[before[station]]

    def rename_after_reference_assignment(_top_only):
        for station in (*placed_stations, 2):
            index = before[station].rsplit("-", 1)[-1]
            components[station].Name2 = f"rebuilt-native-chain-{index}"
        return True

    model.ForceRebuild3.side_effect = rename_after_reference_assignment
    names = assembly._assign_chain_references(adapter)
    model.ForceRebuild3.assert_called_once_with(False)
    assert len(names) == chain.LINK_COUNT - 1
    assert names["@InnerLink:1"] == components[0].Name2
    assert names["@OuterLink:1"] == components[1].Name2
    assert names["@InnerLink:34"] == components[-2].Name2
    assert not {
        before[station] for station in placed_stations
    }.intersection(_assembly._POSE_LEDGER), (
        "old chain pose ledger keys survived collective rebuild"
    )
    assert set(_assembly._POSE_LEDGER) == {
        components[station].Name2 for station in placed_stations
    }
    for station in placed_stations:
        assert _assembly._POSE_LEDGER[components[station].Name2] is entries[station]
    assert components[2].Name2 not in _assembly._POSE_LEDGER
    assert before[2] not in _assembly._POSE_LEDGER
    assert all(
        component.Transform2 is transform
        and list(component.Transform2.ArrayData) == array
        for component, transform, array in zip(
            components, transforms, arrays, strict=True
        )
    )
    assert [
        component.ReferencedConfiguration for component in components
    ] == configurations
    assert components[-1].ComponentReference == connecting_reference
    # This is the real save-time guard, with native lookup accepting live names
    # only. Migrating keys must preserve the existing solved pose witnesses.
    _assembly.assert_pose_ledger(adapter)
    assert _assembly._POSE_LEDGER == {}


@pytest.mark.parametrize(
    ("station", "fault"),
    (
        (2, "index-drift"),
        (chain.LINK_COUNT - 1, "index-drift"),
        (chain.LINK_COUNT - 1, "ledger-collision"),
    ),
)
def test_chain_pattern_rebuild_refuses_unsafe_pose_rebinding(
    monkeypatch, station, fault
):
    adapter, components = _native_chain_fixture(monkeypatch)
    model = adapter.currentModel
    component = components[station]
    previous = component.Name2
    array = list(component.Transform2.ArrayData)
    index = previous.rsplit("-", 1)[-1]
    current = f"rebuilt-native-chain-{index if fault == 'ledger-collision' else '9999'}"
    entry = None
    if station == chain.LINK_COUNT - 1:
        _assembly._ledger_record(
            previous,
            [value * 1000.0 for value in array[9:12]],
            [array[0:3], array[3:6], array[6:9]],
        )
        entry = _assembly._POSE_LEDGER[previous]
    collision = ([999.0, 999.0, 999.0], list(array[0:9]))

    def damage_after_reference_assignment(_top_only):
        component.Name2 = current
        if fault == "ledger-collision":
            _assembly._POSE_LEDGER[current] = collision
        return True

    model.ForceRebuild3.side_effect = damage_after_reference_assignment
    expected_error = (
        f"component binding collides with pose ledger {current!r}"
        if fault == "ledger-collision"
        else f"rebuild changed native component index or scope: {previous!r} -> {current!r}"
    )
    with pytest.raises(RuntimeError, match=re.escape(expected_error)):
        assembly._assign_chain_references(adapter)
    model.ForceRebuild3.assert_called_once_with(False)
    assert component.Name2 == current
    assert list(component.Transform2.ArrayData) == array
    if entry is not None:
        assert _assembly._POSE_LEDGER[previous] is entry
    else:
        assert previous not in _assembly._POSE_LEDGER
    if fault == "ledger-collision":
        assert _assembly._POSE_LEDGER[current] is collision
    else:
        assert current not in _assembly._POSE_LEDGER


_PD_NATIVE_PART_WIDTH = 0.046824451973134076


def _pd_bom_fixture(monkeypatch, *, native_columns=False, advertised_extra=0):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, *_args: obj)
    monkeypatch.setattr(_com, "_early_bound", lambda obj, *_args: obj)
    monkeypatch.setattr(_component_references, "_early_bound", lambda obj, *_args: obj)
    monkeypatch.setattr(
        _drawing_tables._sw_type_info, "early_bound_or_flag", lambda obj, *_args: obj
    )
    quantities = {
        key: 1 for key in drawing.BOM_COMPONENT_IDENTITIES
    } | drawing.TRANSGEAR_QUANTITIES | drawing.CHAIN_QUANTITIES
    quantities["sh-vn-brass-fillister-screw"] = len(assembly.GUIDE_SCREW_XY)
    quantities["sh-vn-clamp-screw"] = len(assembly.CLAMP_HOLE_X)
    components_by_key = {}
    for key, (stem, member) in drawing.BOM_COMPONENT_IDENTITIES.items():
        configurations = (
            (sprocket.KNOB_CONFIG, sprocket.CRANK_CONFIG, "T18")
            if key == "pd-transgear-removable" else
            (member or "Default",) * quantities[key]
        )
        components_by_key[key] = [
            _native_pd_component(
                f"native-{key}-{index + 100}", stem, f"{configuration} Simplified"
            )
            for index, configuration in enumerate(configurations)
        ]
        number = drawing.BOM_PART_NUMBERS[key]
        properties = {
            (component.ReferencedConfiguration, "Number"): number
            for component in components_by_key[key]
        } | {("", "Number"): number}
        native_configurations = {
            component.ReferencedConfiguration: SimpleNamespace(
                BOMPartNoSource=8,
                AlternateName=member or stem,
                UseAlternateNameInBOM=True,
                Description=drawing.BOM_DESCRIPTIONS[key],
                UseDescriptionInBOM=key == "pd-transgear-removable",
            )
            for component in components_by_key[key]
        }
        # Both assembly configurations address real members of the same files.
        # Switching BOM membership must not mutate the source occurrences.
        for member_name, configuration_info in tuple(native_configurations.items()):
            native_configurations[member_name.removesuffix(" Simplified")] = configuration_info
            properties[(member_name.removesuffix(" Simplified"), "Number")] = number
        native = SimpleNamespace(
            properties=properties,
            configurations=native_configurations,
            GetCustomInfoValue=lambda selected, property_name, values=properties: (
                values.get((selected, property_name), "")
            ),
            GetConfigurationByName=native_configurations.get,
        )
        for component in components_by_key[key]:
            component.GetModelDoc2 = lambda native=native: native
            component.GetSuppression2 = lambda: 2
            exclusions = {
                (3, (configuration,)): False
                for configuration in ("Default", drawing.SIMPLIFIED_VIEW_CONFIGURATION)
            }
            component.exclusions = exclusions
            component.GetExcludeFromBOM2 = (
                lambda option, names, values=exclusions: (values[(option, tuple(names))],)
            )
    components = [
        component for group in components_by_key.values() for component in group
    ]
    model = SimpleNamespace(GetComponents=lambda _top_only: tuple(components))
    keys = tuple(reversed(drawing.BOM_PART_NUMBERS))
    cells = [["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."]]
    native_rows = [components_by_key[key] for key in keys]
    for row, key in enumerate(keys, 1):
        component = native_rows[row - 1][0]
        native = component.GetModelDoc2()
        cells.append([
            str(row),
            native.GetConfigurationByName(component.ReferencedConfiguration).AlternateName,
            drawing.BOM_DESCRIPTIONS[key],
            str(quantities[key]),
        ])
    columns = [
        SimpleNamespace(
            kind=202, property_name="", raw_property_data="", hidden=False, width=0.025
        ),
        SimpleNamespace(
            kind=201, property_name="", raw_property_data="", hidden=False,
            width=_PD_NATIVE_PART_WIDTH,
        ),
        SimpleNamespace(
            kind=204, property_name="Description", raw_property_data="Description",
            hidden=False, width=0.025,
        ),
        SimpleNamespace(
            kind=203, property_name="", raw_property_data="", hidden=False, width=0.045
        ),
    ]
    table = MagicMock()
    table.Type = 2
    available = ("Default", drawing.SIMPLIFIED_VIEW_CONFIGURATION)
    members_by_configuration = {
        drawing.SIMPLIFIED_VIEW_CONFIGURATION: tuple(native_rows),
        "Default": tuple([
            SimpleNamespace(**(vars(component) | {
                "ReferencedConfiguration": component.ReferencedConfiguration.removesuffix(" Simplified"),
            }))
            for component in group
        ] for group in native_rows),
    }
    state = SimpleNamespace(
        columns=columns, native_rows=native_rows, row_keys=list(keys), cells=cells,
        advertised_extra=advertised_extra, hidden_rows=set(), requested_heights={},
        configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        members_by_configuration=members_by_configuration,
    )

    def set_configurations(only_visible, flags, names):
        flags, names = tuple(flags), tuple(names)
        if (
            type(only_visible) is not bool
            or len(flags) != len(names)
            or any(type(flag) is not bool for flag in flags)
            or sum(flags) != 1
        ):
            return False
        if only_visible:
            # Split fixtures may select a single visible configuration directly.
            if len(names) != 1 or names[0] not in available:
                return False
        elif len(names) != len(available) or set(names) != set(available):
            return False
        selected = next(name for name, visible in zip(names, flags, strict=True) if visible)
        native_rows[:] = members_by_configuration[selected]
        state.configuration = selected
        # Native quantities follow eligible occurrences, not a caller's cell writes.
        for index, column in enumerate(columns):
            if column.kind == 203:
                for row, group in enumerate(native_rows, 1):
                    cells[row][index] = str(len(group))
        return True

    table.BomFeature = SimpleNamespace(
        PartConfigurationGrouping=3, DisplayAsOneItem=False, TableType=2,
        SetConfigurations=set_configurations,
        GetConfigurationCount=lambda only_visible: 1 if only_visible else 2,
        GetConfigurations=lambda only_visible, _visibility: (
            ((state.configuration,), (True,)) if only_visible else
            (available, tuple(name == state.configuration for name in available))
        ),
    )
    table._pd_state = state
    type(table).RowCount = PropertyMock(side_effect=lambda: len(cells))
    type(table).TotalRowCount = PropertyMock(side_effect=lambda: len(cells))
    type(table).ColumnCount = PropertyMock(
        side_effect=lambda: sum(not column.hidden for column in columns)
    )
    type(table).TotalColumnCount = PropertyMock(
        side_effect=lambda: len(columns) + state.advertised_extra
    )

    def raw_index(index, include_hidden):
        indices = (
            list(range(len(columns))) if include_hidden else
            [i for i, column in enumerate(columns) if not column.hidden]
        )
        return indices[index] if 0 <= index < len(indices) else None

    def column_type(index, include_hidden):
        physical = raw_index(index, include_hidden)
        if physical is None:
            # Native PD 2291: identical empty signature at every invalid index.
            return -1, None, 0
        column = columns[physical]
        return column.kind, column.raw_property_data or None, 0

    def displayed_text(row, index, include_hidden):
        physical = raw_index(index, include_hidden)
        return "" if physical is None else cells[row][physical]

    def row_hidden(row):
        if type(row) is not int or not 0 <= row < len(cells):
            raise IndexError(row)
        return row in state.hidden_rows

    def custom_property(index):
        if not 0 <= index < len(columns) or columns[index].kind != 204:
            return ""
        return columns[index].property_name

    def bind_property(index, property_name):
        for row, group in enumerate(native_rows, 1):
            values = set()
            for component in group:
                native = component.GetModelDoc2()
                configuration = (
                    native.GetConfigurationByName(component.ReferencedConfiguration)
                    if property_name == "Description"
                    else None
                )
                values.add(str(
                    configuration.Description
                    if configuration is not None and configuration.UseDescriptionInBOM
                    else (
                        native.GetCustomInfoValue(
                            component.ReferencedConfiguration, property_name
                        )
                        or native.GetCustomInfoValue("", property_name)
                        or ""
                    )
                ).strip())
            cells[row][index] = "; ".join(sorted(values))

    def set_custom_property(index, property_name):
        if not 0 <= index < len(columns) or columns[index].kind != 204:
            return False
        column = columns[index]
        column.property_name = property_name
        column.raw_property_data = f'$PRP:"{property_name}"' if property_name else ""
        cells[0][index] = property_name
        bind_property(index, property_name)
        return True

    def move_column(source, where, destination):
        if where not in (2, 3):
            return False
        if not (0 <= source < len(columns) and 0 <= destination < len(columns)):
            return False
        insertion = destination + (where == 3) - (source < destination)
        columns.insert(insertion, columns.pop(source))
        for row in cells:
            row.insert(insertion, row.pop(source))
        return True

    def insert_column(where, index, name, width_style):
        if width_style != 0 or where not in (2, 3):
            return False
        if not 0 <= index < len(columns):
            return False
        insertion = index + (where == 3)
        # Native 2352 inserts an already user-defined/custom-property column.
        columns.insert(
            insertion,
            SimpleNamespace(
                kind=204, property_name="", raw_property_data="", hidden=False,
                width=columns[index].width,
            ),
        )
        for row in cells:
            row.insert(insertion, name if row is cells[0] else "")
        return True

    def hide_column(index, hidden):
        if type(index) is not int or not 1 <= index <= len(columns):
            raise IndexError(index)
        if type(hidden) is not bool:
            raise TypeError(hidden)
        columns[index - 1].hidden = hidden
        # ITableAnnotation.SetColumnHidden is VOID, not a success flag.
        return None

    def set_column_type(index, kind, include_hidden, property_name):
        index = raw_index(index, include_hidden)
        if index is None:
            return 1  # swColumnTypeStatus_InvalidIndex
        previous = columns[index].kind
        columns[index].kind = kind
        columns[index].property_name = property_name if kind == 204 else ""
        columns[index].raw_property_data = (
            f'$PRP:"{property_name}"' if kind == 204 and property_name else ""
        )
        if previous == 201 and not any(column.kind == 201 for column in columns):
            # Native seat evidence: destroying the final PartNumber column
            # immediately deletes this grouped row and its native associations.
            row = state.row_keys.index("pd-transgear-removable")
            cells.pop(row + 1)
            native_rows.pop(row)
            state.row_keys.pop(row)
        if kind == 204 and property_name:
            bind_property(index, property_name)
        return 0

    def set_column_title(index, title, include_hidden):
        physical = raw_index(index, include_hidden)
        if physical is None:
            return False
        cells[0][physical] = title
        return True

    def set_text(row, index, include_hidden, text):
        physical = raw_index(index, include_hidden)
        if physical is None:
            raise IndexError(index)
        cells[row][physical] = text


    def get_width(index):
        physical = raw_index(index, False)
        return 0.0 if physical is None else columns[physical].width

    def set_width(index, width, _options):
        # Widths are a separate unversioned API, never PROPERTY1..N.
        physical = raw_index(index, False)
        if physical is None:
            raise IndexError(index)
        columns[physical].width = width
        return columns[physical].width

    def row_height(row):
        if type(row) is not int or not 0 <= row < len(cells):
            raise IndexError(row)
        return max(drawing.BOM_ROW_HEIGHT, state.requested_heights.get(row, 0.0))

    def set_row_height(row, height, _options):
        row_height(row)
        state.requested_heights[row] = height
        return row_height(row)

    table.MoveColumn.side_effect = move_column
    table.InsertColumn2.side_effect = insert_column
    table.SetColumnHidden.side_effect = hide_column
    table.ColumnHidden.side_effect = lambda index: (
        columns[index - 1].hidden if 1 <= index <= len(columns) else False
    )
    table.GetColumnWidth.side_effect = get_width
    table.GetColumnType3.side_effect = column_type
    table.SetColumnType3.side_effect = set_column_type
    table.GetColumnCustomProperty.side_effect = custom_property
    table.SetColumnCustomProperty.side_effect = set_custom_property
    table.SetColumnTitle2.side_effect = set_column_title
    table.GetColumnTitle2.side_effect = lambda index, include_hidden: displayed_text(
        0, index, include_hidden
    )
    table.DisplayedText.side_effect = lambda row, column: displayed_text(row, column, False)
    table.Text2.side_effect = displayed_text
    table.DisplayedText2.side_effect = displayed_text
    table.RowHidden.side_effect = row_hidden
    table.IsCellTextEditable.return_value = True
    table.SetText2.side_effect = set_text
    table.SetColumnWidth.side_effect = set_width
    table.GetHeaderCount.return_value = 1
    table.GetRowHeight.side_effect = row_height
    table.SetRowHeight.side_effect = set_row_height
    table.GetComponents2.side_effect = lambda row, configuration: (
        native_rows[row - 1]
        if configuration == state.configuration else ()
    )
    if not native_columns:
        # Most consumer tests begin with the valid, already-bound final table.
        columns[1] = SimpleNamespace(
            kind=204, property_name="Number", raw_property_data='$PRP:"Number"',
            hidden=False, width=0.025,
        )
        columns.append(
            SimpleNamespace(
                kind=201, property_name="", raw_property_data="", hidden=False,
                width=_PD_NATIVE_PART_WIDTH,
            )
        )
        for row in cells:
            row.append(row[1])
        bind_property(1, "Number")
        hide_column(len(columns), True)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    return model, components, table, adapter, cells, keys


def test_source_census_distinguishes_chain_members_and_preserves_transgear_aggregation(monkeypatch):
    model, _components, table, adapter, _cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    assert counts["sh-vn-chain-link--InnerLink"] == 34
    assert counts["sh-vn-chain-link--OuterLink"] == 33
    assert counts["pd-vn-chain-connecting-link"] == 1
    assert counts["pd-transgear-removable"] == 3
    items = dict(
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    )
    for key in ("sh-vn-chain-link--InnerLink", "sh-vn-chain-link--OuterLink", "pd-transgear-removable"):
        assert items[key] == str(keys.index(key) + 1)
    assert items["sh-vn-chain-link--InnerLink"] != items["sh-vn-chain-link--OuterLink"]
    table.SetText2.assert_not_called()


def test_pd_consumer_refuses_missing_native_spare_with_unchanged_printed_quantity(monkeypatch):
    model, _components, table, adapter, _cells, keys = _pd_bom_fixture(monkeypatch)
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    gear_row = keys.index("pd-transgear-removable") + 1
    physical_gears = tuple(table.GetComponents2(gear_row, configuration))
    assert {component.ReferencedConfiguration for component in physical_gears} == {
        "T12 Simplified", "T18 Simplified", "T24 Simplified"
    }
    table._pd_state.native_rows[gear_row - 1] = [
        component for component in physical_gears
        if component.ReferencedConfiguration != "T18 Simplified"
    ]
    counts = drawing._source_family_counts(model)
    assert counts["pd-transgear-removable"] == 3
    assert {component.ReferencedConfiguration for component in table.GetComponents2(
        gear_row, configuration
    )} == {"T12 Simplified", "T24 Simplified"}
    assert table.DisplayedText2(gear_row, 1, True) == drawing.BOM_PART_NUMBERS["pd-transgear-removable"]
    assert table.DisplayedText2(gear_row, 3, True) == "3"
    with pytest.raises(RuntimeError, match="native occurrence count.*printed quantity"):
        drawing._validate_bom(adapter, table, counts, configuration=configuration)


@pytest.mark.parametrize("hidden_row", (0, 1), ids=("header", "data"))
@pytest.mark.parametrize("during_rebuild", (False, True), ids=("initial", "final"))
def test_pd_consumer_refuses_hidden_physical_rows(monkeypatch, hidden_row, during_rebuild):
    model, _components, table, adapter, cells, _keys = _pd_bom_fixture(monkeypatch)
    before = tuple(tuple(row) for row in cells)
    counts = drawing._source_family_counts(model)
    if during_rebuild:
        def rebuild():
            table._pd_state.hidden_rows.add(hidden_row)
            return True

        adapter.currentModel.EditRebuild3 = rebuild
    else:
        table._pd_state.hidden_rows.add(hidden_row)
    with pytest.raises(RuntimeError, match="hidden or unreadable|row visibility changed"):
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    assert table.RowHidden(hidden_row) is True
    assert table.RowCount == table.TotalRowCount == 44
    assert tuple(tuple(row) for row in cells) == before


@pytest.mark.parametrize("row", (-1, 44, 45))
def test_pd_native_row_visibility_refuses_nonexistent_rows(monkeypatch, row):
    _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    with pytest.raises(IndexError):
        table.RowHidden(row)


@pytest.mark.parametrize("fault", ("wrong-member", "duplicate-total", "duplicate-native-name"))
def test_source_census_rejects_member_substitution_and_duplicate_occurrences(monkeypatch, fault):
    model, components, _table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    inner = next(c for c in components if c.ReferencedConfiguration == "InnerLink Simplified")
    if fault == "wrong-member":
        inner.ReferencedConfiguration = "OuterLink Simplified"
    elif fault == "duplicate-total":
        components.append(_native_pd_component("extra-native-707", "sh-vn-chain-link", "InnerLink"))
    else:
        components.append(inner)
    with pytest.raises(RuntimeError):
        drawing._source_family_counts(model)


@pytest.mark.parametrize("fault", ("merged-members", "wrong-quantity", "internal-number", "blank-number"))
def test_bom_refuses_merged_chain_rows_or_noncanonical_numbers(monkeypatch, fault):
    model, _components, table, adapter, cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    inner_row = keys.index("sh-vn-chain-link--InnerLink") + 1
    outer_row = keys.index("sh-vn-chain-link--OuterLink") + 1
    if fault == "merged-members":
        original = table.GetComponents2.side_effect
        table.GetComponents2.side_effect = lambda row, configuration: (
            original(inner_row, configuration) + original(outer_row, configuration)
            if row == inner_row else original(row, configuration)
        )
    elif fault == "wrong-quantity":
        cells[inner_row][3] = "67"
    else:
        cells[inner_row][1] = "" if fault == "blank-number" else "sh-vn-chain-link--InnerLink"
    with pytest.raises(RuntimeError):
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    table.SetText2.assert_not_called()


@pytest.mark.parametrize("configuration", ("Default", "", "InnerLink Simplified", "innerlink"))
def test_chain_insertion_refuses_an_implicit_or_inexact_member(monkeypatch, configuration):
    place = AsyncMock()
    monkeypatch.setattr(assembly, "place_component", place)
    with pytest.raises(ValueError, match="requires a named member"):
        asyncio.run(
            assembly._place_chain_seed(
                object(), assembly.CHAIN_LINK_STEM, 0, configuration=configuration
            )
        )
    place.assert_not_awaited()


def test_bom_canonical_numbers_are_read_again_after_the_last_rebuild(monkeypatch):
    model, _components, table, adapter, cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    inner_row = keys.index("sh-vn-chain-link--InnerLink") + 1

    def rebuild_with_stale_number():
        cells[inner_row][1] = "sh-vn-chain-link--InnerLink"
        return True

    adapter.currentModel.EditRebuild3 = rebuild_with_stale_number
    with pytest.raises(RuntimeError, match="BOM part number"):
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    table.SetText2.assert_not_called()


@pytest.mark.parametrize(
    ("fault", "message"),
    (
        ("swapped-chain-associations", "native associations changed"),
        ("missing-transgear-association", "has no native component association"),
        ("missing-spare-quantity", "BOM row.*changed"),
        ("missing-transgear-row", "dimensions changed"),
        ("grouping", "configuration grouping changed"),
        ("column-property", None),
        ("native-number", "associative Number"),
        ("changed-retained-native", "unique trailing native column"),
        ("unhidden-retained-native", "dimensions changed"),
        ("moved-retained-native", None),
    ),
)
def test_bom_rechecks_members_and_quantities_after_the_last_rebuild(
    monkeypatch, fault, message
):
    model, _components, table, adapter, cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    inner_row = keys.index("sh-vn-chain-link--InnerLink") + 1
    outer_row = keys.index("sh-vn-chain-link--OuterLink") + 1
    transgear_row = keys.index("pd-transgear-removable") + 1
    native_components = table.GetComponents2.side_effect

    def rebuild_with_changed_bom():
        if fault == "swapped-chain-associations":
            # Both rows still print the same canonical purchase Number. A
            # Number-only readback cannot notice the wrong native attachment.
            table.GetComponents2.side_effect = lambda row, configuration: native_components(
                {inner_row: outer_row, outer_row: inner_row}.get(row, row),
                configuration,
            )
        elif fault == "missing-transgear-association":
            table.GetComponents2.side_effect = lambda row, configuration: (
                () if row == transgear_row else native_components(row, configuration)
            )
        elif fault == "missing-spare-quantity":
            cells[transgear_row][3] = "2"
        elif fault == "grouping":
            table.BomFeature.PartConfigurationGrouping = 2
        elif fault == "column-property":
            table._pd_state.columns[1].property_name = "Description"
        elif fault == "changed-retained-native":
            table._pd_state.columns[-1].kind = 202
        elif fault == "unhidden-retained-native":
            table._pd_state.columns[-1].hidden = False
        elif fault == "moved-retained-native":
            columns = table._pd_state.columns
            columns[3], columns[4] = columns[4], columns[3]
            for row in cells:
                row[3], row[4] = row[4], row[3]
        elif fault == "native-number":
            native = native_components(
                inner_row, drawing.SIMPLIFIED_VIEW_CONFIGURATION
            )[0].GetModelDoc2()
            native.GetCustomInfoValue = lambda *_: "WRONG-NATIVE-NUMBER"
        else:
            cells.pop(transgear_row)
            table.GetComponents2.side_effect = lambda row, configuration: native_components(
                row + (row >= transgear_row), configuration
            )
        return True

    adapter.currentModel.EditRebuild3 = rebuild_with_changed_bom
    with pytest.raises(RuntimeError, match=message):
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    table.SetText2.assert_not_called()


def _pd_bom_insertion_fixture(monkeypatch, *, advertised_extra=0):
    model, components, table, adapter, cells, keys = _pd_bom_fixture(
        monkeypatch, native_columns=True, advertised_extra=advertised_extra
    )
    monkeypatch.setattr(_drawing_tables._sw_type_info, "early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_tables._sw_type_info, "is_early_bound", lambda *_: True)
    monkeypatch.setattr(_drawing_tables, "_activate_and_select_view", lambda *_, **__: None)
    monkeypatch.setattr(_drawing_tables, "bom_table_template", lambda _: "native.sldbomtbt")
    monkeypatch.setattr(_drawing_tables, "bool_array", tuple)
    monkeypatch.setattr(_drawing_tables, "bstr_array", tuple)
    adapter._get_attr_or_call = lambda obj, name: getattr(obj, name)
    adapter._attempt = lambda action: action()
    adapter.currentModel.ClearSelection2 = lambda _: None
    adapter.currentModel.ForceRebuild3 = lambda _: True
    view = SimpleNamespace(
        ReferencedConfiguration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        InsertBomTable6=lambda *_: table,
    )

    def insert():
        return _drawing_tables.insert_bom_table(
            adapter,
            view,
            anchor_xy=drawing.BOM_ANCHOR,
            expected_components=tuple(drawing.BOM_PART_NUMBERS),
            descriptions=drawing.BOM_DESCRIPTIONS,
            component_identities=drawing.BOM_COMPONENT_IDENTITIES,
            part_number_property="Number",
            configuration_grouping="same-name",
            label="paper-drive",
        )

    return SimpleNamespace(
        model=model, components=components, table=table, adapter=adapter,
        cells=cells, keys=keys, state=table._pd_state, insert=insert, view=view,
    )


def test_native_visibility_fixture_keeps_property_text_and_width_domains_distinct(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    table = scene.insert()
    native = scene.state.columns[-1]
    quantity = scene.state.columns[3]
    assert (native.kind, native.hidden, native.width) == (201, True, _PD_NATIVE_PART_WIDTH)
    assert (quantity.kind, quantity.hidden, quantity.width) == (203, False, 0.045)
    assert table.GetColumnWidth(3) == quantity.width
    assert table.GetColumnWidth(4) == 0.0
    assert table.ColumnHidden(4) is False
    assert table.ColumnHidden(5) is True

    assert table.SetColumnHidden(5, False) is None
    assert table.GetColumnWidth(3) == 0.045
    assert table.GetColumnWidth(4) == _PD_NATIVE_PART_WIDTH
    for index in range(5):
        assert table.GetColumnType3(index, True) == table.GetColumnType3(index, False)
        assert table.GetColumnTitle2(index, True) == table.GetColumnTitle2(index, False)
        assert table.DisplayedText2(0, index, True) == table.DisplayedText2(0, index, False)
    assert table.SetColumnHidden(5, True) is None
    assert native.width == _PD_NATIVE_PART_WIDTH
    assert quantity.width == 0.045

    # Insertions inherit their physical neighbour's stored width.
    assert table.InsertColumn2(3, 2, "PURCHASE SKU", 0) is True
    assert scene.state.columns[3].width == scene.state.columns[2].width
    assert scene.state.columns[4] is quantity
    assert scene.state.columns[5] is native
    assert table.GetColumnWidth(4) == quantity.width
    assert table.GetColumnWidth(5) == 0.0
    assert table.ColumnHidden(5) is False
    assert table.ColumnHidden(6) is True
    for index in (6, 7, 8):
        assert table.GetColumnWidth(index) == 0.0
        assert table.ColumnHidden(index + 1) is False
        assert table.GetColumnType3(index, True) == (-1, None, 0)


def test_pd_all_visible_authoring_preserves_visible_quantities_and_native_snapshot(monkeypatch):
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    widths = tuple(enumerate(
        drawing.BOM_COLUMN_WIDTHS[key]
        for key in ("item", "part", "description", "quantity")
    ))
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    table = scene.insert()
    before = _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        expected_rows=44, occurrence_quantities=True,
    )
    before_identities = tuple(
        (id(component), component.GetPathName(), component.ReferencedConfiguration,
         component.Name2, component.ComponentReference)
        for component in scene.components
    )
    before_cells = tuple(tuple(row) for row in scene.cells)
    items = dict(drawing._validate_bom(
        scene.adapter, table, drawing._source_family_counts(scene.model),
        configuration=configuration,
    ))
    assert set(items) == set(drawing.BOM_PART_NUMBERS)
    assert tuple(column.width for column in scene.state.columns[:4]) == tuple(
        width for _index, width in widths
    )
    assert (scene.state.columns[-1].kind, scene.state.columns[-1].hidden,
            scene.state.columns[-1].width) == (
                201, True, drawing.BOM_COLUMN_WIDTHS["description"]
            )
    assert tuple(tuple(row) for row in scene.cells) == before_cells
    assert tuple(
        (id(component), component.GetPathName(), component.ReferencedConfiguration,
         component.Name2, component.ComponentReference)
        for component in scene.components
    ) == before_identities
    snapshot = _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        expected_rows=44, occurrence_quantities=True,
    )
    assert snapshot == before
    proof_by_row = {row[0]: row for row in snapshot}
    for key, count, configurations in (
        ("pd-transgear-removable", 3, {"T12 Simplified", "T18 Simplified", "T24 Simplified"}),
        ("sh-vn-chain-link--InnerLink", 34, {"InnerLink Simplified"}),
        ("sh-vn-chain-link--OuterLink", 33, {"OuterLink Simplified"}),
    ):
        row = scene.keys.index(key) + 1
        members = table.GetComponents2(row, configuration)
        assert len(members) == count
        assert {component.ReferencedConfiguration for component in members} == configurations
        assert table.DisplayedText2(row, 3, True) == str(count)
        assert table.DisplayedText2(row, 3, False) == str(count)
        assert table.DisplayedText2(row, 1, False) == drawing.BOM_PART_NUMBERS[key]
        assert proof_by_row[row][2:] == (drawing.BOM_PART_NUMBERS[key], str(count))
        assert sum(identity[2] for identity in proof_by_row[row][1]) == count
    assert items["sh-vn-chain-link--InnerLink"] != items["sh-vn-chain-link--OuterLink"]
    heights = tuple(table.GetRowHeight(row) for row in range(44))
    assert heights == (drawing.BOM_ROW_HEIGHT,) * 44
    split_after = drawing.bom_split_row(heights, 1)
    for anchor, height in (
        (drawing.BOM_ANCHOR, sum(heights[:split_after + 1])),
        (drawing.BOM_SECOND_ANCHOR, heights[0] + sum(heights[split_after + 1:])),
    ):
        assert not drawing.bom_extent_violations(
            anchor, sum(drawing.BOM_COLUMN_WIDTHS.values()), height
        )
    # Fixture row fit is not native displayed-grid or saved/reopened qualification.
    assert sum(table.GetColumnWidth(index) for index in range(4)) == pytest.approx(
        sum(drawing.BOM_COLUMN_WIDTHS.values())
    )


@pytest.mark.parametrize("with_sku", (False, True))
def test_pd_width_authoring_sets_physical_columns_and_preserves_untargeted_widths(
    monkeypatch, with_sku
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    table = scene.insert()
    if with_sku:
        assert table.InsertColumn2(3, 2, "PURCHASE SKU", 0) is True
    quantity_column = 4 if with_sku else 3
    widths = (
        (0, 0.012), (1, 0.048), (2, 0.118), (quantity_column, 0.012),
    )
    original = {
        id(column): (column.width, column.kind, column.property_name,
                     column.raw_property_data, column.hidden)
        for column in scene.state.columns
    }
    before_cells = tuple(tuple(row) for row in scene.cells)
    before_members = tuple(tuple(group) for group in scene.state.native_rows)
    drawing._set_bom_column_widths(table, widths)
    for index, column in enumerate(scene.state.columns):
        old_width, *old_metadata = original[id(column)]
        expected = (
            drawing.BOM_COLUMN_WIDTHS["description"]
            if column.kind == 201 else dict(widths).get(index, old_width)
        )
        assert column.width == expected
        assert [column.kind, column.property_name, column.raw_property_data, column.hidden] == (
            old_metadata
        )
    assert scene.state.columns[-1].width == drawing.BOM_COLUMN_WIDTHS["description"]
    assert scene.state.columns[-1].hidden is True
    assert scene.state.columns[quantity_column].width == 0.012
    assert table.GetColumnWidth(quantity_column) == 0.012
    assert tuple(tuple(row) for row in scene.cells) == before_cells
    assert tuple(tuple(group) for group in scene.state.native_rows) == before_members


@pytest.mark.parametrize(
    "fault", ("missing", "unhidden", "duplicate", "not-trailing", "hidden-neighbour")
)
def test_pd_width_authoring_refuses_invalid_original_retained_column_state(monkeypatch, fault):
    _model, _components, table, _adapter, cells, _keys = _pd_bom_fixture(monkeypatch)
    columns = table._pd_state.columns
    if fault == "missing":
        columns.pop()
        for row in cells:
            row.pop()
    elif fault == "unhidden":
        columns[-1].hidden = False
    elif fault == "duplicate":
        columns[2].kind = 201
    elif fault == "not-trailing":
        columns[3], columns[4] = columns[4], columns[3]
        for row in cells:
            row[3], row[4] = row[4], row[3]
    else:
        columns[2].hidden = True
    before = [vars(column).copy() for column in columns]
    with pytest.raises(RuntimeError):
        drawing._set_bom_column_widths(
            table, ((0, 0.012), (1, 0.048), (2, 0.118), (3, 0.012))
        )
    assert [vars(column) for column in columns] == before


@pytest.mark.parametrize(
    "fault",
    ("unhide-refused", "legacy-kind", "legacy-title", "legacy-header",
     "physical-kind-changed", "physical-order-changed"),
)
def test_pd_width_authoring_requires_all_visible_metadata_alignment_before_writing(
    monkeypatch, fault
):
    _model, _components, table, _adapter, cells, _keys = _pd_bom_fixture(monkeypatch)
    columns = table._pd_state.columns
    before_widths = {id(column): column.width for column in columns}
    native_hide = table.SetColumnHidden.side_effect
    native_type = table.GetColumnType3.side_effect
    native_title = table.GetColumnTitle2.side_effect
    native_text = table.DisplayedText2.side_effect

    def hide(index, hidden):
        if not hidden and fault == "unhide-refused":
            return None
        result = native_hide(index, hidden)
        if not hidden and fault == "physical-kind-changed":
            columns[3].kind = 202
        elif not hidden and fault == "physical-order-changed":
            columns[0], columns[2] = columns[2], columns[0]
            for row in cells:
                row[0], row[2] = row[2], row[0]
        return result

    def column_type(index, include_hidden):
        if (fault == "legacy-kind" and not columns[-1].hidden
                and index == 3 and include_hidden is False):
            return 201, None, 0
        return native_type(index, include_hidden)

    def title(index, include_hidden):
        if (fault == "legacy-title" and not columns[-1].hidden
                and index == 3 and include_hidden is False):
            return "PART NUMBER"
        return native_title(index, include_hidden)

    def displayed(row, index, include_hidden):
        if (fault == "legacy-header" and not columns[-1].hidden
                and row == 0 and index == 3 and include_hidden is False):
            return "PART NUMBER"
        return native_text(row, index, include_hidden)

    table.SetColumnHidden.side_effect = hide
    table.GetColumnType3.side_effect = column_type
    table.GetColumnTitle2.side_effect = title
    table.DisplayedText2.side_effect = displayed
    with pytest.raises(RuntimeError):
        drawing._set_bom_column_widths(
            table, ((0, 0.012), (1, 0.048), (2, 0.118), (3, 0.012))
        )
    assert {id(column): column.width for column in columns} == before_widths
    assert columns[-1].hidden is True


@pytest.mark.parametrize(
    "result", (float("nan"), float("inf"), 0.013),
    ids=("nan", "infinite", "wrong-width"),
)
def test_pd_width_authoring_refuses_bad_setter_return_despite_correct_readback(monkeypatch, result):
    _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    columns = table._pd_state.columns
    native_set = table.SetColumnWidth.side_effect

    def set_width(index, width, options):
        actual = native_set(index, width, options)
        return result if index == 3 else actual

    table.SetColumnWidth.side_effect = set_width
    with pytest.raises(RuntimeError):
        drawing._set_bom_column_widths(
            table, ((0, 0.012), (1, 0.048), (2, 0.118), (3, 0.012))
        )
    assert columns[3].width == 0.012
    assert (columns[-1].hidden, columns[-1].width) == (True, _PD_NATIVE_PART_WIDTH)


@pytest.mark.parametrize("fault", ("quantity", "retained-native", "untargeted-sku"))
def test_pd_width_authoring_refuses_independent_width_readback_damage(monkeypatch, fault):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    table = scene.insert()
    assert table.InsertColumn2(3, 2, "PURCHASE SKU", 0) is True
    columns = scene.state.columns
    damaged_column = {"quantity": 4, "retained-native": 5, "untargeted-sku": 3}[fault]
    before = columns[damaged_column].width
    native_set = table.SetColumnWidth.side_effect

    def set_width(index, width, options):
        actual = native_set(index, width, options)
        if index == damaged_column or (fault == "untargeted-sku" and index == 4):
            columns[damaged_column].width += 0.001
        return actual

    table.SetColumnWidth.side_effect = set_width
    with pytest.raises(RuntimeError):
        drawing._set_bom_column_widths(
            table, ((0, 0.012), (1, 0.048), (2, 0.118), (4, 0.012))
        )
    assert columns[damaged_column].width == pytest.approx(
        {"quantity": 0.012, "retained-native": 0.118}.get(fault, before) + 0.001
    )
    assert columns[-1].hidden is True


@pytest.mark.parametrize("fault", ("ignored", "wrong-column", "raises-after-effect"))
def test_pd_width_authoring_refuses_failed_restoration_without_a_primary_error(monkeypatch, fault):
    _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    columns = table._pd_state.columns
    native_hide = table.SetColumnHidden.side_effect

    def hide(index, hidden):
        if not hidden:
            return native_hide(index, hidden)
        if fault == "ignored":
            return None
        if fault == "wrong-column":
            return native_hide(4, True)
        native_hide(index, hidden)
        raise RuntimeError("native restore failed after taking effect")

    table.SetColumnHidden.side_effect = hide
    with pytest.raises(RuntimeError):
        drawing._set_bom_column_widths(
            table, ((0, 0.012), (1, 0.048), (2, 0.118), (3, 0.012))
        )
    assert columns[3].width == 0.012
    assert columns[-1].width == drawing.BOM_COLUMN_WIDTHS["description"]
    assert columns[-1].hidden is (fault == "raises-after-effect")
    assert columns[3].hidden is (fault == "wrong-column")


@pytest.mark.parametrize("restore_fault", ("raises-before-effect", "raises-after-effect", "wrong-column"))
def test_pd_width_authoring_does_not_mask_primary_exception_when_restoration_fails(
    monkeypatch, restore_fault
):
    _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    columns = table._pd_state.columns
    native_set = table.SetColumnWidth.side_effect
    native_hide = table.SetColumnHidden.side_effect
    primary = RuntimeError("primary native width failure")

    def set_width(index, width, options):
        if index == 3:
            raise primary
        return native_set(index, width, options)

    def hide(index, hidden):
        if not hidden:
            return native_hide(index, hidden)
        if restore_fault == "wrong-column":
            return native_hide(4, True)
        if restore_fault == "raises-after-effect":
            native_hide(index, hidden)
        raise RuntimeError("secondary native restoration failure")

    table.SetColumnWidth.side_effect = set_width
    table.SetColumnHidden.side_effect = hide
    with pytest.raises(RuntimeError) as caught:
        drawing._set_bom_column_widths(
            table, ((0, 0.012), (1, 0.048), (2, 0.118), (3, 0.012))
        )
    assert caught.value is primary
    assert columns[-1].hidden is (restore_fault == "raises-after-effect")
    assert columns[-1].width == _PD_NATIVE_PART_WIDTH


def test_pd_width_authoring_restores_after_an_unhide_exception_with_native_side_effect(monkeypatch):
    _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    columns = table._pd_state.columns
    before_widths = tuple(column.width for column in columns)
    native_hide = table.SetColumnHidden.side_effect
    primary = RuntimeError("unhide raised after taking effect")

    def hide(index, hidden):
        result = native_hide(index, hidden)
        if not hidden:
            raise primary
        return result

    table.SetColumnHidden.side_effect = hide
    with pytest.raises(RuntimeError) as caught:
        drawing._set_bom_column_widths(
            table, ((0, 0.012), (1, 0.048), (2, 0.118), (3, 0.012))
        )
    assert caught.value is primary
    assert tuple(column.width for column in columns) == before_widths
    assert columns[-1].hidden is True


@pytest.mark.parametrize("advertised_extra", (0, 1), ids=("accurate-count", "native-2291"))
@pytest.mark.parametrize("number_source", ("configuration", "document"))
def test_bom_insertion_retains_grouped_native_members_through_pd_consumer(
    monkeypatch, number_source, advertised_extra
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=advertised_extra)
    counts = drawing._source_family_counts(scene.model)
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    gear_components = tuple(scene.table.GetComponents2(gear_row, configuration))
    native = gear_components[0].GetModelDoc2()
    if number_source == "configuration":
        native.properties[("", "Number")] = "WRONG-DOCUMENT-FALLBACK"
    else:
        for component in gear_components:
            native.properties[(component.ReferencedConfiguration, "Number")] = ""
    assert scene.table.ColumnCount == 4
    assert scene.table.TotalColumnCount == 4 + advertised_extra
    assert _drawing_tables._bom_physical_columns(scene.table, label="paper-drive") == (
        (202, False), (201, False), (204, False), (203, False)
    )

    table = scene.insert()
    assert table is scene.table
    baseline = None
    for with_sku in (False, True):
        if with_sku:
            description_column = next(
                index for index in range(table.ColumnCount)
                if table.DisplayedText2(0, index, True) == "DESCRIPTION"
            )
            assert table.InsertColumn2(3, description_column, "PURCHASE SKU", 0) is True
        visible = 5 if with_sku else 4
        assert table.ColumnCount == visible
        assert table.TotalColumnCount == visible + 1 + advertised_extra
        physical = _drawing_tables._bom_physical_columns(table, label="paper-drive")
        assert len(physical) == visible + 1
        assert physical[-1] == (201, True)
        assert all(not hidden for _kind, hidden in physical[:-1])
        assert table.GetColumnType3(visible, True) == (201, None, 0)
        assert table.GetColumnWidth(visible) == 0.0
        assert table.GetColumnType3(visible, False) == (-1, None, 0)
        assert table.GetColumnType3(1, True) == (204, '$PRP:"Number"', 0)
        assert table.GetColumnCustomProperty(1) == "Number"
        assert table.BomFeature.PartConfigurationGrouping == 3
        assert table.BomFeature.DisplayAsOneItem is False
        assert table.RowCount == table.TotalRowCount == len(scene.keys) + 1 == 44
        quantity_column = visible - 1
        assert table.GetColumnType3(quantity_column, True) == (203, None, 0)
        assert table.GetColumnType3(quantity_column, False) == (203, None, 0)
        assert table.DisplayedText2(0, quantity_column, True) == "QTY."
        assert table.DisplayedText2(0, quantity_column, False) == "QTY."
        assert table.DisplayedText(0, quantity_column) == "QTY."
        visible_headers = tuple(table.DisplayedText(0, index) for index in range(visible))
        assert visible_headers.count("PART NUMBER") == 1
        assert visible_headers.count("QTY.") == 1
        # PROPERTY of the last real column collides with the first typed-invalid
        # physical integer. Its mapped beyond-prefix PROPERTY is still False.
        assert table.ColumnHidden(visible + 1) is True
        assert table.GetColumnType3(visible + 1, True) == (-1, None, 0)
        assert table.ColumnHidden(visible + 2) is False
        snapshot = _drawing_tables.validate_bom_number_property(
            table, configuration=configuration, label="paper-drive", expected_rows=44,
            occurrence_quantities=True,
        )
        assert tuple(row[0] for row in snapshot) == tuple(range(1, 44))
        proof_by_row = {row[0]: row for row in snapshot}
        assert proof_by_row[gear_row][2:] == (
            drawing.BOM_PART_NUMBERS["pd-transgear-removable"], "3"
        )
        assert sum(identity[2] for identity in proof_by_row[gear_row][1]) == 3
        items = dict(drawing._validate_bom(
            scene.adapter, table, counts, configuration=configuration
        ))
        assert set(items) == set(drawing.BOM_PART_NUMBERS)
        if baseline is None:
            baseline = snapshot, items
        else:
            assert (snapshot, items) == baseline
        assert table.DisplayedText2(gear_row, 1, True) == drawing.BOM_PART_NUMBERS["pd-transgear-removable"]
        assert table.DisplayedText2(gear_row, quantity_column, True) == scene.cells[gear_row][quantity_column] == "3"
        assert table.DisplayedText2(gear_row, quantity_column, False) == "3"
        assert tuple(table.GetComponents2(gear_row, configuration)) == gear_components
        assert {component.ReferencedConfiguration for component in gear_components} == {
            "T12 Simplified", "T18 Simplified", "T24 Simplified"
        }
        for key, quantity, member in (
            ("sh-vn-chain-link--InnerLink", "34", "InnerLink Simplified"),
            ("sh-vn-chain-link--OuterLink", "33", "OuterLink Simplified"),
        ):
            row = scene.keys.index(key) + 1
            assert table.DisplayedText2(row, 1, True) == drawing.BOM_PART_NUMBERS[key]
            assert table.DisplayedText2(row, quantity_column, True) == scene.cells[row][quantity_column] == quantity
            assert table.DisplayedText2(row, quantity_column, False) == quantity
            assert table.DisplayedText2(row, 1, False) == drawing.BOM_PART_NUMBERS[key]
            assert proof_by_row[row][2:] == (drawing.BOM_PART_NUMBERS[key], quantity)
            assert sum(identity[2] for identity in proof_by_row[row][1]) == int(quantity)
            members = table.GetComponents2(row, configuration)
            assert len(members) == int(quantity)
            assert {component.ReferencedConfiguration for component in members} == {member}
        assert items["sh-vn-chain-link--InnerLink"] != items["sh-vn-chain-link--OuterLink"]

    # A plausible raw variant cannot replace the dedicated binding getter,
    # even after insertion has shifted Qty and the retained native column.
    scene.state.columns[1].property_name = "Description"
    for raw_metadata in ('$PRP:"Number"', "Number"):
        scene.state.columns[1].raw_property_data = raw_metadata
        assert table.GetColumnType3(1, True) == (204, raw_metadata, 0)
        assert table.GetColumnCustomProperty(1) == "Description"
        with pytest.raises(RuntimeError, match="Number property binding did not persist"):
            drawing._validate_bom(scene.adapter, table, counts, configuration=configuration)


@pytest.mark.parametrize("with_sku", (False, True))
@pytest.mark.parametrize("advertised_extra", (0, 1))
def test_pd_hidden_native_property_collision_accepts_zero_width_without_losing_visible_qty(
    monkeypatch, with_sku, advertised_extra
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=advertised_extra)
    table = scene.insert()
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    if with_sku:
        assert table.InsertColumn2(3, 2, "PURCHASE SKU", 0) is True
    before = _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        expected_rows=44, occurrence_quantities=True,
    )
    native_column = len(scene.state.columns) - 1
    scene.state.columns[native_column].width = 0.0
    assert table.GetColumnType3(native_column + 1, True) == (-1, None, 0)
    assert table.ColumnHidden(native_column + 1) is True
    assert table.ColumnHidden(native_column + 2) is False
    assert _drawing_tables._bom_physical_columns(table, label="paper-drive")[-1] == (201, True)
    assert _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        expected_rows=44, occurrence_quantities=True,
    ) == before


@pytest.mark.parametrize("with_sku", (False, True))
@pytest.mark.parametrize("fault", ("qty-hidden", "visible-qty", "visible-number"))
def test_pd_consumer_refuses_wrong_visible_projection_despite_unchanged_physical_snapshot(
    monkeypatch, with_sku, fault
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    table = scene.insert()
    if with_sku:
        assert table.InsertColumn2(3, 2, "PURCHASE SKU", 0) is True
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    counts = drawing._source_family_counts(scene.model)
    drawing._validate_bom(scene.adapter, table, counts, configuration=configuration)
    before_cells = tuple(tuple(row) for row in scene.cells)
    before_members = tuple(tuple(group) for group in scene.state.native_rows)

    def native_identities():
        return tuple(
            tuple(
                (
                    component.GetPathName(), component.ReferencedConfiguration,
                    component.Name2, component.ComponentReference,
                )
                for component in group
            )
            for group in scene.state.native_rows
        )

    before_identities = native_identities()
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    quantity_column = 4 if with_sku else 3
    native_column = quantity_column + 1
    retained_quantities = tuple(
        (scene.keys.index(key) + 1, quantity)
        for key, quantity in (
            ("pd-transgear-removable", 3),
            ("sh-vn-chain-link--InnerLink", 34),
            ("sh-vn-chain-link--OuterLink", 33),
        )
    )
    for row, quantity in retained_quantities:
        assert len(table.GetComponents2(row, configuration)) == quantity
        assert table.DisplayedText2(row, quantity_column, True) == str(quantity)
        assert table.DisplayedText2(row, quantity_column, False) == str(quantity)
    visible_width = sum(table.GetColumnWidth(index) for index in range(table.ColumnCount))
    assert table.GetColumnWidth(quantity_column) == 0.012
    assert table.GetColumnWidth(native_column) == 0.0
    if not with_sku:
        assert visible_width == pytest.approx(0.190)
    if fault == "qty-hidden":
        assert table.SetColumnHidden(native_column + 1, False) is None
        assert table.SetColumnHidden(quantity_column + 1, True) is None
        assert table.DisplayedText2(0, quantity_column, False) == "PART NUMBER"
        assert table.DisplayedText2(gear_row, quantity_column, True) == "3"
        assert table.GetColumnWidth(quantity_column) == 0.118
        assert table.GetColumnWidth(native_column) == 0.0
        assert sum(table.GetColumnWidth(index) for index in range(table.ColumnCount)) == pytest.approx(
            visible_width - 0.012 + 0.118
        )
        if not with_sku:
            assert sum(table.GetColumnWidth(index) for index in range(4)) == pytest.approx(0.296)
        reason = "BOM widths need one hidden trailing native column"
    else:
        original_text = table.DisplayedText2.side_effect
        damaged_column = quantity_column if fault == "visible-qty" else 1

        def displayed(row, column, include_hidden):
            if row == gear_row and column == damaged_column and include_hidden is False:
                return "2" if fault == "visible-qty" else "WRONG-NUMBER"
            return original_text(row, column, include_hidden)

        table.DisplayedText2.side_effect = displayed
        assert table.DisplayedText2(gear_row, damaged_column, False) != (
            table.DisplayedText2(gear_row, damaged_column, True)
        )
        name = "quantity" if fault == "visible-qty" else "Number"
        reason = f"visible {name} .*does not match physical {name}"
    with pytest.raises(RuntimeError, match=reason):
        drawing._validate_bom(scene.adapter, table, counts, configuration=configuration)
    assert tuple(tuple(row) for row in scene.cells) == before_cells
    assert tuple(tuple(group) for group in scene.state.native_rows) == before_members
    assert table.RowCount == table.TotalRowCount == 44
    assert native_identities() == before_identities
    for row, quantity in retained_quantities:
        assert len(table.GetComponents2(row, configuration)) == quantity
        assert table.DisplayedText2(row, quantity_column, True) == str(quantity)


@pytest.mark.parametrize("fault", ("lost-spare", "changed-quantity"))
def test_inserted_pd_bom_refuses_gear_damage_after_sku_shift(monkeypatch, fault):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    counts = drawing._source_family_counts(scene.model)
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    table = scene.insert()
    assert table.InsertColumn2(3, 2, "PURCHASE SKU", 0) is True
    drawing._validate_bom(scene.adapter, table, counts, configuration=configuration)
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    if fault == "lost-spare":
        scene.state.native_rows[gear_row - 1] = [
            component for component in scene.state.native_rows[gear_row - 1]
            if component.ReferencedConfiguration != "T18 Simplified"
        ]
        assert len(table.GetComponents2(gear_row, configuration)) == 2
        assert table.DisplayedText2(gear_row, 4, True) == "3"
        message = "native occurrence count.*printed quantity"
    else:
        scene.cells[gear_row][4] = "2"
        assert len(table.GetComponents2(gear_row, configuration)) == 3
        assert table.DisplayedText2(gear_row, 4, True) == "2"
        message = "BOM quantity"
    with pytest.raises(RuntimeError, match=message):
        drawing._validate_bom(scene.adapter, table, counts, configuration=configuration)


@pytest.mark.parametrize("hidden_row", (0, 1), ids=("header", "data"))
def test_bom_insertion_refuses_hidden_physical_rows_before_number_binding(monkeypatch, hidden_row):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    scene.state.hidden_rows.add(hidden_row)
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.cells) == before_cells
    assert scene.table.RowHidden(hidden_row) is True


def _pd_native_balloon_note(table, component):
    """Native eligibility depends on occurrence AND actual member, not Number."""
    def item(_upper):
        wanted = (component.GetPathName(), component.Name2, component.ReferencedConfiguration)
        for row in range(1, table.TotalRowCount):
            for eligible in table.GetComponents2(row, table._pd_state.configuration):
                if (eligible.GetPathName(), eligible.Name2, eligible.ReferencedConfiguration) == wanted:
                    column = next(
                        index for index in range(table.TotalColumnCount)
                        if table.GetColumnType3(index, True)[0] == 202
                    )
                    return table.DisplayedText2(row, column, True)
        return "*"

    return SimpleNamespace(GetBomBalloonText=item)


def test_default_balloon_is_ineligible_for_simplified_only_bom(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    table = scene.insert()  # No override retains the simplified rendered view.
    stem = "pd-vn-transgear-pivot-screw"
    row = scene.keys.index(stem)
    component = scene.state.members_by_configuration["Default"][row][0]
    landing = drawing.BalloonLanding(
        stem, component.Name2, _pd_native_balloon_note(table, component), None, "PD consumer",
    )
    assert table.GetComponents2(row + 1, drawing.SIMPLIFIED_VIEW_CONFIGURATION)
    assert landing.note.GetBomBalloonText(True) == "*"
    with pytest.raises(RuntimeError, match=r"resolved item \*, expected"):
        drawing._assert_bom_balloon_items([landing], {stem: str(row + 1)})


def test_place_bom_sheet_preserves_native_grouped_quantities_with_visible_number_binding(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    configuration = drawing.BOM_CONFIGURATION
    before_members = {
        key: tuple(id(component) for component in group)
        for key, group in zip(scene.keys, scene.state.members_by_configuration[configuration], strict=True)
    }
    before_identities = {
        key: tuple(
            (
                component.GetPathName(), component.ReferencedConfiguration,
                component.Name2, component.ComponentReference,
            )
            for component in group
        )
        for key, group in zip(scene.keys, scene.state.members_by_configuration[configuration], strict=True)
    }
    # Isolate graphical view/split/balloon work, not the real insertion helper,
    # Number binding, rebuilds, native identity checks or quantity consumers.
    for name in (
        "_activate_sheet", "set_high_quality_shaded_with_edges",
        "apply_view_configuration", "_place_sheet_note", "_link_view_to_bom",
        "_isolate_instances", "_shift_view", "_uncross_ring", "_spread_balloons",
    ):
        monkeypatch.setattr(drawing, name, lambda *_, **__: None)
    # Model the observed post-operation views, without attributing the native
    # configuration change to any particular link/isolation/scale operation.
    native_views = iter((
        scene.view, SimpleNamespace(ReferencedConfiguration="Default"),
        SimpleNamespace(ReferencedConfiguration="Default"),
    ))
    monkeypatch.setattr(drawing, "place_view", lambda *_, **__: next(native_views))
    monkeypatch.setattr(drawing, "_view_outline", lambda _: drawing.BOM_REFERENCE_LIMITS)
    monkeypatch.setattr(drawing, "transgear_view_shift", lambda _: (0.0, 0.0))
    monkeypatch.setattr(drawing, "inner_view_shift", lambda *_: (0.0, 0.0))
    monkeypatch.setattr(drawing, "inner_view_scale", lambda *_: drawing.INNER_SCALE_LADDER[0])
    monkeypatch.setattr(drawing, "_split_bom", lambda *_, **__: ())
    def balloons(_adapter, view, *, items, **_options):
        landings = []
        for stem, _item in items:
            row = scene.keys.index(stem)
            component = scene.state.members_by_configuration["Default"][row][0]
            note = _pd_native_balloon_note(scene.table, component)
            landings.append(drawing.BalloonLanding(stem, component.Name2, note, None, "PD consumer"))
        drawing._assert_bom_balloon_items(landings, dict(items))
        return landings

    monkeypatch.setattr(drawing, "add_component_bom_balloons", balloons)
    monkeypatch.setattr(drawing, "_balloon_collar_on_its_rear_rim", lambda adapter, view, *, item, label: (
        balloons(adapter, view, items=((drawing.COLLAR_STEM, item),))[0]
    ))

    _landings, table, items, _pieces, snapshot = drawing._place_bom_sheet(
        scene.adapter, drawing._source_family_counts(scene.model)
    )
    assert table is scene.table
    assert scene.view.ReferencedConfiguration == drawing.SIMPLIFIED_VIEW_CONFIGURATION
    assert table.GetComponents2(1, drawing.SIMPLIFIED_VIEW_CONFIGURATION) == ()
    drawing._assert_bom_balloon_items(_landings, items)
    assert set(items) == set(drawing.BOM_PART_NUMBERS)
    assert table.RowCount == table.TotalRowCount == 44
    assert _drawing_tables._bom_physical_columns(table, label="paper-drive") == (
        (202, False), (204, False), (204, False), (203, False), (201, True)
    )
    assert table.GetColumnCustomProperty(1) == "Number"
    assert table.BomFeature.PartConfigurationGrouping == 3
    assert table.BomFeature.DisplayAsOneItem is False
    proof_by_row = {row[0]: row for row in snapshot}
    for row, key in enumerate(scene.keys, 1):
        members = table.GetComponents2(row, configuration)
        assert tuple(id(component) for component in members) == before_members[key]
        assert tuple(
            (
                component.GetPathName(), component.ReferencedConfiguration,
                component.Name2, component.ComponentReference,
            )
            for component in members
        ) == before_identities[key]
        assert table.DisplayedText2(row, 1, True) == drawing.BOM_PART_NUMBERS[key]
    for key, quantity, configurations in (
        ("pd-transgear-removable", 3, {"T12", "T18", "T24"}),
        ("sh-vn-chain-link--InnerLink", 34, {"InnerLink"}),
        ("sh-vn-chain-link--OuterLink", 33, {"OuterLink"}),
    ):
        row = scene.keys.index(key) + 1
        assert table.Text2(row, 3, True) == table.DisplayedText2(row, 3, True) == str(quantity)
        assert table.DisplayedText2(row, 3, False) == str(quantity)
        assert table.DisplayedText2(row, 1, False) == drawing.BOM_PART_NUMBERS[key]
        assert proof_by_row[row][2:] == (drawing.BOM_PART_NUMBERS[key], str(quantity))
        assert sum(identity[2] for identity in proof_by_row[row][1]) == quantity
        members = table.GetComponents2(row, configuration)
        assert len(members) == quantity
        assert {component.ReferencedConfiguration for component in members} == configurations
    assert items["sh-vn-chain-link--InnerLink"] != items["sh-vn-chain-link--OuterLink"]


def test_native_part_number_conversion_reproduces_consumer_visible_group_loss(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    counts = drawing._source_family_counts(scene.model)
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    gear_components = tuple(scene.state.native_rows[gear_row - 1])
    before = scene.table.RowCount
    scene.table.SetColumnType3(1, 204, True, "Number")
    assert scene.table.RowCount == scene.table.TotalRowCount == before - 1
    assert "pd-transgear-removable" not in scene.state.row_keys
    assert not {
        id(component) for group in scene.state.native_rows for component in group
    }.intersection(id(component) for component in gear_components)
    with pytest.raises(RuntimeError, match="paper-drive BOM is.*expected"):
        drawing._validate_bom(
            scene.adapter, scene.table, counts,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        )


@pytest.mark.parametrize(
    "failure",
    (
        "move", "move-noop", "insert", "insert-noop", "hide-readback",
        "number-property-status", "number-property-readback", "initial-inconsistent-counts",
    ),
)
def test_bom_insertion_refuses_failed_native_column_retention(monkeypatch, failure):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    if failure == "move":
        scene.table.MoveColumn.side_effect = lambda *_: False
    elif failure == "move-noop":
        scene.table.MoveColumn.side_effect = lambda *_: True
    elif failure == "insert":
        scene.table.InsertColumn2.side_effect = lambda *_: False
    elif failure == "insert-noop":
        scene.table.InsertColumn2.side_effect = lambda *_: True
    elif failure == "number-property-status":
        scene.table.SetColumnCustomProperty.side_effect = lambda *_: False
    elif failure == "number-property-readback":
        native_property = scene.table.GetColumnCustomProperty.side_effect
        scene.table.GetColumnCustomProperty.side_effect = lambda index: (
            "Description" if index == 1 else native_property(index)
        )
    elif failure == "initial-inconsistent-counts":
        type(scene.table).ColumnCount = PropertyMock(return_value=3)
    else:
        # A VOID call returning None is valid, but a no-op must fail readback.
        scene.table.SetColumnHidden.side_effect = lambda *_: None
    with pytest.raises(RuntimeError):
        scene.insert()



@pytest.mark.parametrize("kind", (0, 201, 202, 203))
def test_bom_insertion_refuses_noncustom_inserted_column(monkeypatch, kind):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    native_insert = scene.table.InsertColumn2.side_effect
    before_members = tuple(tuple(group) for group in scene.state.native_rows)
    before_quantities = tuple(row[3] for row in scene.cells)

    def insert_column(where, index, name, width_style):
        result = native_insert(where, index, name, width_style)
        scene.state.columns[index + (where == 3)].kind = kind
        return result

    scene.table.InsertColumn2.side_effect = insert_column
    with pytest.raises(RuntimeError):
        scene.insert()
    assert scene.state.columns[1].kind == kind
    assert scene.table.GetColumnCustomProperty(1) == ""
    assert scene.table.RowCount == scene.table.TotalRowCount == 44
    assert tuple(tuple(group) for group in scene.state.native_rows) == before_members
    assert tuple(row[3] for row in scene.cells) == before_quantities


@pytest.mark.parametrize("result", (None, 0, 1, "True"), ids=("none", "zero", "one", "string"))
def test_bom_insertion_refuses_nonbool_property_setter_success(monkeypatch, result):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    native_set = scene.table.SetColumnCustomProperty.side_effect
    before_members = tuple(tuple(group) for group in scene.state.native_rows)
    before_quantities = tuple(row[3] for row in scene.cells)

    def set_custom_property(index, property_name):
        assert native_set(index, property_name) is True
        return result

    scene.table.SetColumnCustomProperty.side_effect = set_custom_property
    with pytest.raises(RuntimeError):
        scene.insert()
    assert scene.table.GetColumnCustomProperty(1) == "Number"
    assert scene.table.RowCount == scene.table.TotalRowCount == 44
    assert tuple(tuple(group) for group in scene.state.native_rows) == before_members
    assert tuple(row[3] for row in scene.cells) == before_quantities

@pytest.mark.parametrize(
    "fault",
    (
        "missing-native", "changed-native", "unhidden-native", "duplicate-native",
        "native-not-last", "hidden-visible-gap", "bad-native-status",
        "bad-number-kind", "bad-number-status",
        "bad-property-readback", "short-total-count", "short-visible-count",
    ),
)
def test_bom_number_proof_refuses_invalid_retained_column_state(monkeypatch, fault):
    _model, _components, table, _adapter, cells, _keys = _pd_bom_fixture(monkeypatch)
    columns = table._pd_state.columns
    if fault == "missing-native":
        columns.pop()
        for row in cells:
            row.pop()
    elif fault == "changed-native":
        columns[-1].kind = 202
    elif fault == "unhidden-native":
        columns[-1].hidden = False
    elif fault == "duplicate-native":
        columns[2].kind = 201
    elif fault == "native-not-last":
        columns[3], columns[4] = columns[4], columns[3]
        for row in cells:
            row[3], row[4] = row[4], row[3]
    elif fault == "hidden-visible-gap":
        columns[2].hidden = True
    elif fault == "bad-number-kind":
        columns[1].kind = 202
    elif fault == "bad-property-readback":
        native_property = table.GetColumnCustomProperty.side_effect
        table.GetColumnCustomProperty.side_effect = lambda index: (
            "Description" if index == 1 else native_property(index)
        )
    elif fault in ("bad-native-status", "bad-number-status"):
        original_type = table.GetColumnType3.side_effect
        bad_index = 4 if fault == "bad-native-status" else 1
        table.GetColumnType3.side_effect = lambda index, hidden: (
            (*original_type(index, hidden)[:2], 1)
            if index == bad_index else original_type(index, hidden)
        )
    elif fault == "short-total-count":
        type(table).TotalColumnCount = PropertyMock(return_value=4)
    else:
        type(table).ColumnCount = PropertyMock(return_value=3)
    with pytest.raises(RuntimeError):
        _drawing_tables.validate_bom_number_property(
            table, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            label="paper-drive", expected_rows=len(drawing.BOM_PART_NUMBERS) + 1,
        )


def test_bom_number_proof_uses_binding_getter_not_raw_property_data(monkeypatch):
    _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    before = _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        occurrence_quantities=True,
    )
    column = table._pd_state.columns[1]
    assert column.raw_property_data == '$PRP:"Number"'
    for raw_metadata in ("Number", '$PRP:"Number"'):
        column.raw_property_data = raw_metadata
        assert _drawing_tables.validate_bom_number_property(
            table, configuration=configuration, label="paper-drive",
            occurrence_quantities=True,
        ) == before
    column.property_name = "Description"
    with pytest.raises(RuntimeError):
        _drawing_tables.validate_bom_number_property(
            table, configuration=configuration, label="paper-drive",
            occurrence_quantities=True,
        )


@pytest.mark.parametrize("invalid_status", (0, 1), ids=("observed-success", "sdk-invalid-index"))
def test_bom_column_census_accepts_matching_complete_empty_native_fingerprints(
    monkeypatch, invalid_status
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    original_type = scene.table.GetColumnType3.side_effect

    def column_type(index, include_hidden):
        value = original_type(index, include_hidden)
        return (-1, None, invalid_status) if value[0] == -1 else value

    scene.table.GetColumnType3.side_effect = column_type
    physical = _drawing_tables._bom_physical_columns(scene.table, label="paper-drive")
    assert physical == ((202, False), (201, False), (204, False), (203, False))
    for index in (4, 5, 6):
        for include_hidden in (False, True):
            assert scene.table.GetColumnType3(index, include_hidden) == (
                -1, None, invalid_status
            )
            assert scene.table.GetColumnTitle2(index, include_hidden) == ""
            assert scene.table.DisplayedText2(0, index, include_hidden) == ""
        assert scene.table.GetColumnWidth(index) == 0.0
        assert scene.table.ColumnHidden(index + 1) is False
        assert scene.table.GetColumnCustomProperty(index) == ""
    assert scene.insert() is scene.table
    assert len(_drawing_tables._bom_physical_columns(scene.table, label="paper-drive")) == 5
    items = dict(drawing._validate_bom(
        scene.adapter, scene.table, drawing._source_family_counts(scene.model),
        configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
    ))
    assert set(items) == set(drawing.BOM_PART_NUMBERS)
    assert scene.table.RowCount == scene.table.TotalRowCount == 44


@pytest.mark.parametrize(
    ("index", "member", "mode", "value"),
    (
        (4, "GetColumnType3", True, (-1, None)),
        (4, "GetColumnType3", True, (999, None, 0)),
        (4, "GetColumnType3", True, ("-1", None, 0)),
        (4, "GetColumnType3", True, (-1, None, "0")),
        (4, "GetColumnType3", True, (-1, None, 2)),
        (4, "GetColumnType3", True, (-1, "", 0)),
        (4, "GetColumnType3", False, (-1, "Number", 0)),
        (4, "GetColumnTitle2", True, "UNEXPECTED"),
        (4, "GetColumnTitle2", False, "UNEXPECTED"),
        (4, "DisplayedText2", True, "UNEXPECTED"),
        (4, "DisplayedText2", False, "UNEXPECTED"),
        (4, "GetColumnWidth", None, 0.025),
        (4, "GetColumnWidth", None, -0.001),
        (4, "GetColumnWidth", None, float("nan")),
        (4, "GetColumnWidth", None, float("inf")),
        (5, "ColumnHidden", None, True),
        (5, "ColumnHidden", None, 1),
        (5, "ColumnHidden", None, None),
        (4, "GetColumnCustomProperty", None, "Audit"),
        (4, "GetColumnType3", True, (-1, None, 1)),
        (5, "GetColumnType3", True, (-1, None, 1)),
        (6, "GetColumnType3", True, (-1, None, 1)),
        (5, "GetColumnType3", True, (204, None, 0)),
        (6, "GetColumnTitle2", False, "UNEXPECTED"),
    ),
    ids=(
        "malformed-type", "unknown-kind", "string-kind", "string-status",
        "invalid-property-status", "nonempty-property-data", "visible-property-data",
        "physical-title", "visible-title", "physical-header", "visible-header",
        "nonzero-width", "negative-width", "nan-width", "infinite-width",
        "hidden-invalid", "nonboolean-hidden", "missing-hidden", "custom-property",
        "tail-control-status-mismatch", "first-control-status-mismatch",
        "second-control-status-mismatch", "typed-control", "nonempty-control",
    ),
)
def test_bom_column_census_refuses_invalid_native_slot_without_mutating(
    monkeypatch, index, member, mode, value
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    accessor = getattr(scene.table, member)
    original = accessor.side_effect

    if member == "DisplayedText2":
        def read(row, column, include_hidden):
            if column == index and include_hidden is mode:
                return value
            return original(row, column, include_hidden)
    elif mode is None:
        def read(column):
            return value if column == index else original(column)
    else:
        def read(column, include_hidden):
            if column == index and include_hidden is mode:
                return value
            return original(column, include_hidden)

    accessor.side_effect = read
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


@pytest.mark.parametrize("statuses", ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 1, 1)))
def test_bom_column_census_does_not_normalize_distinct_invalid_statuses(
    monkeypatch, statuses
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    original_type = scene.table.GetColumnType3.side_effect

    def column_type(index, include_hidden):
        if index in (4, 5, 6):
            return -1, None, statuses[index - 4]
        return original_type(index, include_hidden)

    scene.table.GetColumnType3.side_effect = column_type
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


def test_bom_column_census_refuses_empty_interior_before_later_typed_column(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    original_type = scene.table.GetColumnType3.side_effect
    original_title = scene.table.GetColumnTitle2.side_effect
    original_text = scene.table.DisplayedText2.side_effect
    original_width = scene.table.GetColumnWidth.side_effect
    original_property = scene.table.GetColumnCustomProperty.side_effect
    scene.table.GetColumnType3.side_effect = lambda index, mode: (
        (-1, None, 0) if index == 2 else original_type(index, mode)
    )
    scene.table.GetColumnTitle2.side_effect = lambda index, mode: (
        "" if index == 2 else original_title(index, mode)
    )
    scene.table.DisplayedText2.side_effect = lambda row, index, mode: (
        "" if index == 2 else original_text(row, index, mode)
    )
    scene.table.GetColumnWidth.side_effect = lambda index: (
        0.0 if index == 2 else original_width(index)
    )
    scene.table.GetColumnCustomProperty.side_effect = lambda index: (
        "" if index == 2 else original_property(index)
    )
    before = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert tuple(tuple(row) for row in scene.cells) == before
    assert scene.table.GetColumnType3(3, True) == (203, None, 0)
    assert len(scene.state.columns) == 4


@pytest.mark.parametrize("kind", (201, 204), ids=("native-part-number", "custom-property"))
def test_bom_insertion_refuses_actual_preexisting_hidden_zero_width_column(
    monkeypatch, kind
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    scene.state.columns.append(SimpleNamespace(
        kind=kind, property_name="Audit" if kind == 204 else "",
        raw_property_data="Audit" if kind == 204 else "", hidden=True, width=0.0,
    ))
    for row in scene.cells:
        row.append("")
    assert scene.table.ColumnCount == 4
    assert scene.table.TotalColumnCount == 6
    physical = _drawing_tables._bom_physical_columns(scene.table, label="paper-drive")
    assert len(physical) == 5
    assert physical[-1] == (kind, True)
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


def test_bom_column_census_refuses_advertised_cap_overflow_without_truncation(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    type(scene.table).TotalColumnCount = PropertyMock(return_value=99)
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


@pytest.mark.parametrize("index", (15, 16, 17), ids=("last-declared", "first-control", "second-control"))
def test_bom_column_census_refuses_bad_metadata_beyond_diagnostic_display_cap(
    monkeypatch, index
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    type(scene.table).TotalColumnCount = PropertyMock(return_value=16)
    original_property = scene.table.GetColumnCustomProperty.side_effect
    scene.table.GetColumnCustomProperty.side_effect = lambda column: (
        "Audit" if column == index else original_property(column)
    )
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


def test_native_column_fixture_keeps_visible_and_physical_indices_distinct(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    assert scene.table.SetColumnHidden(2, True) is None
    assert scene.table.ColumnCount == 3
    assert scene.table.TotalColumnCount == 5
    assert scene.table.GetColumnType3(1, True) == (201, None, 0)
    assert scene.table.GetColumnType3(1, False) == (204, "Description", 0)
    assert scene.table.GetColumnTitle2(1, True) == "PART NUMBER"
    assert scene.table.GetColumnTitle2(1, False) == "DESCRIPTION"
    assert scene.table.DisplayedText2(0, 1, False) == "DESCRIPTION"
    assert scene.table.GetColumnType3(3, False) == (-1, None, 0)
    assert _drawing_tables._bom_physical_columns(scene.table, label="paper-drive") == (
        (202, False), (201, True), (204, False), (203, False)
    )


@pytest.mark.parametrize("index", (-1, 4, 5, 6))
def test_native_column_fixture_refuses_nonaddressable_mutation_destinations(
    monkeypatch, index
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    assert scene.table.MoveColumn(1, 3, index) is False
    assert scene.table.MoveColumn(index, 3, 0) is False
    assert scene.table.InsertColumn2(2, index, "PART NUMBER", 0) is False
    assert scene.table.SetColumnType3(index, 204, True, "Number") == 1
    assert scene.table.SetColumnCustomProperty(index, "Number") is False
    assert scene.table.SetColumnTitle2(index, "PART NUMBER", True) is False
    with pytest.raises(IndexError):
        scene.table.SetColumnHidden(index + 1, True)
    with pytest.raises(IndexError):
        scene.table.SetColumnWidth(index, 0.025, 0)
    with pytest.raises(IndexError):
        scene.table.SetText2(0, index, True, "PART NUMBER")
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


@pytest.mark.parametrize(
    ("failure", "member", "mode"),
    (
        ("type_all", "GetColumnType3", True),
        ("type_visible", "GetColumnType3", False),
        ("title_all", "GetColumnTitle2", True),
        ("title_visible", "GetColumnTitle2", False),
        ("header_all", "DisplayedText2", True),
        ("header_visible", "DisplayedText2", False),
        ("width", "GetColumnWidth", None),
        ("hidden", "ColumnHidden", None),
        ("custom_property", "GetColumnCustomProperty", None),
    ),
)
def test_bom_column_census_refuses_accessor_errors_without_mutating(
    monkeypatch, failure, member, mode
):
    scene = _pd_bom_insertion_fixture(monkeypatch, advertised_extra=1)
    accessor = getattr(scene.table, member)
    original = accessor.side_effect

    def fail():
        raise RuntimeError("native-column-read-failure")

    if member == "DisplayedText2":
        def read(row, column, include_hidden):
            if column == 4 and include_hidden is mode:
                fail()
            return original(row, column, include_hidden)
    elif mode is None:
        def read(column):
            if column == (5 if member == "ColumnHidden" else 4):
                fail()
            return original(column)
    else:
        def read(column, include_hidden):
            if column == 4 and include_hidden is mode:
                fail()
            return original(column, include_hidden)

    accessor.side_effect = read
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


@pytest.mark.parametrize("drop", ("transgear", "all"))
def test_bom_insertion_refuses_row_loss_from_the_number_binding(monkeypatch, drop):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    native_rows = scene.state.native_rows
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    gear_components = tuple(native_rows[gear_row - 1])
    changed = False

    def rebuild():
        nonlocal changed
        if scene.state.columns[1].property_name == "Number" and not changed:
            if drop == "all":
                del scene.cells[1:]
                native_rows.clear()
            else:
                row = scene.keys.index("pd-transgear-removable") + 1
                scene.cells.pop(row)
                native_rows.pop(row - 1)
            changed = True
        return True

    scene.adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(RuntimeError):
        scene.insert()
    assert changed
    if drop == "all":
        assert scene.table.RowCount == scene.table.TotalRowCount == 1
        assert native_rows == []
    else:
        assert scene.table.RowCount == scene.table.TotalRowCount == len(scene.keys)
        assert not {
            id(component) for group in native_rows for component in group
        }.intersection(id(component) for component in gear_components)
    with pytest.raises(RuntimeError):
        drawing._validate_bom(
            scene.adapter, scene.table, drawing._source_family_counts(scene.model),
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        )


@pytest.mark.parametrize("effect", ("omitted", "merged", "excluded", "hidden"))
def test_number_binding_consumer_refuses_changed_native_bom_state(monkeypatch, effect):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    native_rows = scene.state.native_rows
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    gear_components = tuple(native_rows[gear_row - 1])
    gear_ids = {id(component) for component in gear_components}
    original_rows = scene.table.RowCount
    original_native_rows = tuple(
        tuple(id(component) for component in group) for group in native_rows
    )
    changed = False

    def rebuild():
        nonlocal changed
        if scene.state.columns[1].property_name != "Number" or changed:
            return True
        if effect == "hidden":
            scene.state.hidden_rows.add(gear_row)
        else:
            scene.cells.pop(gear_row)
            native_rows.pop(gear_row - 1)
            if effect == "merged":
                native_rows[0].extend(gear_components)
                quantity_column = next(
                    index for index, column in enumerate(scene.state.columns)
                    if column.kind == 203
                )
                scene.cells[1][quantity_column] = str(len(native_rows[0]))
            elif effect == "excluded":
                for component in gear_components:
                    component.exclusions[(3, (configuration,))] = True
        changed = True
        return True

    scene.adapter.currentModel.EditRebuild3 = rebuild
    if effect == "merged":
        message = "associative Number.*does not match native component Numbers"
    elif effect == "hidden":
        message = rf"BOM row {gear_row} is not proven visible"
    else:
        message = rf"BOM table is .*expected {original_rows} rows"
    with pytest.raises(RuntimeError, match=message):
        scene.insert()
    assert changed
    associated_rows = {
        row
        for row in range(1, scene.table.RowCount)
        for component in scene.table.GetComponents2(row, configuration)
        if id(component) in gear_ids
    }
    actual_native_rows = tuple(
        tuple(id(component) for component in scene.table.GetComponents2(row, configuration))
        for row in range(1, scene.table.RowCount)
    )
    if effect == "hidden":
        assert scene.table.RowCount == scene.table.TotalRowCount == original_rows
        assert scene.table.RowHidden(gear_row) is True
        assert associated_rows == {gear_row}
        assert actual_native_rows == original_native_rows
    else:
        assert scene.table.RowCount == scene.table.TotalRowCount == original_rows - 1
        assert associated_rows == ({1} if effect == "merged" else set())
        expected_native_rows = list(original_native_rows)
        removed = expected_native_rows.pop(gear_row - 1)
        if effect == "merged":
            expected_native_rows[0] += removed
        assert actual_native_rows == tuple(expected_native_rows)
        if effect == "excluded":
            assert all(
                component.GetExcludeFromBOM2(3, (configuration,)) == (True,)
                for component in gear_components
            )


@pytest.mark.parametrize("failure", ("row-association", "component-path"))
def test_number_binding_refuses_bad_native_rows_and_components(monkeypatch, failure):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    native_components = scene.table.GetComponents2.side_effect
    if failure == "row-association":
        def components(row, configuration):
            if row == 1:
                raise RuntimeError("native-row-association-failure")
            return native_components(row, configuration)

        scene.table.GetComponents2.side_effect = components
        message = "native-row-association-failure"
    else:
        component = native_components(1, drawing.SIMPLIFIED_VIEW_CONFIGURATION)[0]
        component.GetPathName = lambda: ""
        message = "component has no native file path"
    with pytest.raises(RuntimeError, match=message):
        scene.insert()


@pytest.mark.parametrize(
    ("fault", "message"),
    (
        ("native-associations", "native associations changed during finalization"),
        ("grouping", "configuration grouping changed during finalization"),
        ("column-property", "Number property binding did not persist"),
        ("native-number", "associative Number"),
    ),
)
def test_bom_insertion_refuses_changes_from_the_description_rebuild(
    monkeypatch, fault, message
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    inner_row = scene.keys.index("sh-vn-chain-link--InnerLink") + 1
    outer_row = scene.keys.index("sh-vn-chain-link--OuterLink") + 1
    native_components = scene.table.GetComponents2.side_effect
    native_property = scene.table.GetColumnCustomProperty.side_effect

    def rebuild():
        if scene.table.SetText2.called:
            if fault == "grouping":
                scene.table.BomFeature.PartConfigurationGrouping = 2
            elif fault == "column-property":
                scene.table.GetColumnCustomProperty.side_effect = lambda index: (
                    "Description" if index == 1 else native_property(index)
                )
            elif fault == "native-number":
                native = native_components(
                    inner_row, drawing.SIMPLIFIED_VIEW_CONFIGURATION
                )[0].GetModelDoc2()
                native.GetCustomInfoValue = lambda *_: "WRONG-NATIVE-NUMBER"
            else:
                scene.table.GetComponents2.side_effect = lambda row, configuration: native_components(
                    {inner_row: outer_row, outer_row: inner_row}.get(row, row),
                    configuration,
                )
        return True

    scene.adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(RuntimeError, match=message):
        scene.insert()



def _pd_display_grid(table, rows, anchor):
    """Model displayed physical borders, not a requested-width/readback echo."""
    xs = [anchor[0]]
    for column in table._pd_state.columns:
        if not column.hidden:
            xs.append(xs[-1] + column.width)
    ys = [anchor[1]]
    for row in rows:
        ys.append(ys[-1] - table.GetRowHeight(row))

    def line(x1, y1, x2, y2):
        return (0, 0, 0, 0, x1, y1, 0.0, x2, y2, 0.0)

    return (
        [line(x, ys[-1], x, ys[0]) for x in xs]
        + [line(xs[0], y, xs[-1], y) for y in ys]
    )


@pytest.mark.parametrize("actual", ["Default", "Default Simplified", "", None])
def test_pd_balloon_configuration_guard_reads_actual_state_without_forcing_it(monkeypatch, actual):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, *_: obj)

    class View:
        @property
        def ReferencedConfiguration(self):
            return actual

    if actual == drawing.BOM_CONFIGURATION:
        drawing._assert_bom_balloon_configuration(View(), label="post-operation view")
    else:
        with pytest.raises(RuntimeError, match="post-operation view: balloon view configuration"):
            drawing._assert_bom_balloon_configuration(View(), label="post-operation view")


@pytest.mark.parametrize("changed_item", [None, "*", "1"], ids=("stable", "star", "wrong-item"))
def test_pd_build_settled_checks_reject_native_item_drift_with_good_attachments(
    monkeypatch, changed_item,
):
    pieces, _reads, _split_after, _total_rows, snapshot = _pd_split_bom_fixture(
        monkeypatch, configuration=drawing.BOM_CONFIGURATION,
    )
    for name in ("_early_bound", "_bind"):
        monkeypatch.setattr(_drawing_balloons, name, lambda obj, *_: obj)
    items = {key: str(index) for index, key in enumerate(pieces[0]._pd_state.row_keys, 1)}
    stem = "pd-transgear-removable"
    if changed_item not in (None, "*"):
        assert changed_item in items.values()
        assert changed_item != items[stem]
    row = pieces[0]._pd_state.row_keys.index(stem)
    components = pieces[0]._pd_state.native_rows[row]
    values = [items[stem]] * len(components)
    landings = []
    for index, component in enumerate(components):
        edge = SimpleNamespace(GetComponent=lambda component=component: component)
        annotation = SimpleNamespace(
            GetAttachedEntities3=lambda edge=edge: (edge,),
            GetAttachedEntityTypes=lambda: (1,),
        )
        note = SimpleNamespace(
            GetBomBalloonText=lambda _upper, index=index: values[index],
            GetAnnotation=lambda annotation=annotation: annotation,
        )
        landings.append(drawing.BalloonLanding(stem, component.Name2, note, None, "settled PD"))
    assert len(landings) == 3  # Same family, three distinct native occurrences.
    drawing._assert_bom_balloon_items(landings, items)

    def rebuild():
        if changed_item is not None:
            values[-1] = changed_item  # A stem-deduplicated census would miss this.
        return True

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(EditRebuild3=rebuild),
        open_model=AsyncMock(),
        _attempt=lambda action, **_options: action(),
    )
    monkeypatch.setattr(drawing, "SOURCE", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(drawing, "check", lambda *_: None)
    monkeypatch.setattr(drawing, "require_step_notes", lambda: object())
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_, **__: {"Number": steps.DRAWING_NUMBER})
    monkeypatch.setattr(drawing, "_source_family_counts", lambda _: {})
    for name in (
        "_validate_persisted_explode", "_create_sheets", "_place_assembled_sheet",
        "_place_pivot_view", "_place_fitup_sheets", "assert_full_detail_view",
    ):
        monkeypatch.setattr(drawing, name, lambda *_, **__: None)
    monkeypatch.setattr(drawing, "_place_bom_sheet", lambda *_: (
        landings, pieces[0], items, pieces, snapshot,
    ))
    monkeypatch.setattr(drawing, "_balloon_assembled_sheet", lambda *_: [])
    monkeypatch.setattr(drawing, "_place_exploded_sheet", lambda *_: [])

    async def finalize(actual_adapter, _outputs, *, settled_checks, **_options):
        assert actual_adapter.currentModel.EditRebuild3() is True
        drawing.assert_balloon_landings(adapter, landings)  # Geometry remains valid.
        for check in settled_checks:
            check()
        return {"settled": "passed"}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    if changed_item is None:
        assert asyncio.run(drawing.build(adapter)) == {"settled": "passed"}
        with pytest.raises(RuntimeError, match="no native components"):
            drawing._assert_bom_pieces(
                pieces, header_count=1, total_rows=44,
                configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION, expected_snapshot=snapshot,
            )
    else:
        with pytest.raises(RuntimeError, match=r"settled pd-transgear-removable .*resolved item .*expected"):
            asyncio.run(drawing.build(adapter))


def _pd_split_bom_fixture(
    monkeypatch, *, coverage="complete", configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
):
    total_rows = len(drawing.BOM_PART_NUMBERS) + 1
    split_after = drawing.bom_split_row(
        (drawing.BOM_ROW_HEIGHT,) * total_rows, 1
    )
    _model, _components, baseline, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    assert baseline.BomFeature.SetConfigurations(True, (True,), (configuration,))
    expected_snapshot = _drawing_tables.validate_bom_number_property(
        baseline, configuration=configuration,
        label="paper-drive", expected_rows=total_rows,
    )
    second_start = split_after + {"complete": 1, "duplicate": 0, "missing": 2}[coverage]
    pieces = []
    association_reads = []
    for index, (start, end) in enumerate(
        ((0, split_after), (second_start, total_rows - 1))
    ):
        _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
        assert table.BomFeature.SetConfigurations(True, (True,), (configuration,))
        data_rows = frozenset(range(max(start, 1), end + 1))
        readable_rows = data_rows | {0}
        reads = set()
        native_components = table.GetComponents2.side_effect
        native_text = table.DisplayedText2.side_effect
        native_hidden = table.RowHidden.side_effect

        def components(
            row, configuration, *, allowed=data_rows, reads=reads,
            native_components=native_components,
        ):
            if row not in allowed:
                raise RuntimeError(f"row {row} is outside this split piece's global data rows")
            reads.add(row)
            return native_components(row, configuration)

        def displayed(
            row, column, include_hidden, *, allowed=readable_rows, native_text=native_text
        ):
            if row not in allowed:
                raise RuntimeError(f"row {row} is outside this split piece's global rows")
            return native_text(row, column, include_hidden)

        def row_hidden(row, *, allowed=readable_rows, native_hidden=native_hidden):
            if row not in allowed:
                raise RuntimeError(f"row {row} is outside this split piece's global rows")
            return native_hidden(row)

        def row_height(row, *, allowed=readable_rows):
            if row not in allowed:
                raise RuntimeError(f"row {row} is outside this split piece's global rows")
            return drawing.BOM_ROW_HEIGHT

        # RowCount is local to the piece, but native calls use global indices.
        type(table).RowCount = PropertyMock(return_value=len(readable_rows))
        type(table).TotalRowCount = PropertyMock(return_value=total_rows)
        table.GetSplitInformation.side_effect = (
            lambda *_args, info=(1, index, 2, start, end): info
        )
        table.GetComponents2.side_effect = components
        table.DisplayedText2.side_effect = displayed
        table.RowHidden.side_effect = row_hidden
        table.GetRowHeight.side_effect = row_height
        widths = tuple(drawing.BOM_COLUMN_WIDTHS[key] for key in (
            "item", "part", "description", "quantity"
        ))
        for column, width in enumerate(widths):
            table._pd_state.columns[column].width = width
        table._pd_state.columns[-1].width = drawing.BOM_COLUMN_WIDTHS["description"]
        anchor = (drawing.BOM_ANCHOR, drawing.BOM_SECOND_ANCHOR)[index]
        lines = _pd_display_grid(table, sorted(readable_rows), anchor)
        display = SimpleNamespace(
            GetLineCount=lambda lines=lines: len(lines),
            GetLineAtIndex3=lambda line_index, lines=lines: lines[line_index],
        )
        table._pd_grid_lines = lines
        table.GetAnnotation.return_value = SimpleNamespace(
            GetPosition=lambda anchor=anchor: (*anchor, 0.0),
            GetDisplayData=lambda display=display: display,
        )
        pieces.append(table)
        association_reads.append(reads)
    return pieces, association_reads, split_after, total_rows, expected_snapshot


def test_split_bom_proves_global_native_numbers_and_grid_independently_of_width_getter(monkeypatch):
    pieces, association_reads, split_after, total_rows, expected_snapshot = (
        _pd_split_bom_fixture(monkeypatch)
    )
    for piece in pieces:
        assert tuple(column.width for column in piece._pd_state.columns[:4]) == (
            0.012, 0.048, 0.118, 0.012
        )
        assert piece._pd_state.columns[-1].width == 0.118
        assert piece._pd_state.columns[-1].hidden is True
        # An injected unversioned getter alias cannot replace the actual grid.
        # This is a fault model, not a claim about native hidden-state widths.
        original_width = piece.GetColumnWidth.side_effect
        piece.GetColumnWidth.side_effect = lambda index, original=original_width: (
            0.118 if index == 3 else original(index)
        )
        assert sum(piece.GetColumnWidth(index) for index in range(4)) == pytest.approx(
            0.296
        )
    drawing._assert_bom_pieces(
        pieces, header_count=1, total_rows=total_rows,
        configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        expected_snapshot=expected_snapshot,
    )
    assert association_reads == [
        set(range(1, split_after + 1)),
        set(range(split_after + 1, total_rows)),
    ]
    # A local-index implementation must not silently read another piece's row.
    with pytest.raises(RuntimeError, match="outside this split piece's global data rows"):
        pieces[1].GetComponents2(1, drawing.SIMPLIFIED_VIEW_CONFIGURATION)
    with pytest.raises(RuntimeError, match="outside this split piece's global rows"):
        pieces[1].DisplayedText2(1, 3, True)
    with pytest.raises(RuntimeError, match="outside this split piece's global rows"):
        pieces[1].RowHidden(1)


def test_split_bom_accepts_complete_segmented_grid_and_zero_length_records(monkeypatch):
    pieces, _reads, _split_after, total_rows, snapshot = _pd_split_bom_fixture(monkeypatch)
    for piece in pieces:
        lines = piece._pd_grid_lines
        original = lines.pop(0)
        midpoint = (original[5] + original[8]) / 2
        lines.extend((
            (*original[:7], original[7], midpoint, original[9]),
            (*original[:5], midpoint, *original[6:]),
            (0.0,) * 10,
        ))
    drawing._assert_bom_pieces(
        pieces, header_count=1, total_rows=total_rows,
        configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        expected_snapshot=snapshot,
    )


@pytest.mark.parametrize("wrong_order", (False, True))
def test_split_bom_grid_tracks_nonuniform_global_row_heights(monkeypatch, wrong_order):
    pieces, _reads, split_after, total_rows, snapshot = _pd_split_bom_fixture(monkeypatch)
    for index, piece in enumerate(pieces):
        native_height = piece.GetRowHeight.side_effect

        def row_height(row, native_height=native_height):
            return native_height(row) + row * 0.00001

        piece.GetRowHeight.side_effect = row_height
        rows = (
            list(range(split_after + 1)) if index == 0
            else [0, *range(split_after + 1, total_rows)]
        )
        if wrong_order and index == 1:
            # Render the same rows and total height in the wrong vertical order;
            # independent native global-row heights remain unchanged.
            rows[1], rows[2] = rows[2], rows[1]
        piece._pd_grid_lines[:] = _pd_display_grid(
            piece, rows, (drawing.BOM_ANCHOR, drawing.BOM_SECOND_ANCHOR)[index]
        )
    if wrong_order:
        with pytest.raises(RuntimeError, match="row heights disagree with native split rows"):
            drawing._assert_bom_pieces(
                pieces, header_count=1, total_rows=total_rows,
                configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
                expected_snapshot=snapshot,
            )
    else:
        drawing._assert_bom_pieces(
            pieces, header_count=1, total_rows=total_rows,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            expected_snapshot=snapshot,
        )


@pytest.mark.parametrize(
    "fault",
    ("malformed", "nonfinite", "missing-boundary", "gap", "translated",
     "hidden-column", "whole-table", "missing-repeated-header", "wrong-column-width",
     "diagonal", "nonplanar", "outlying-extension"),
)
def test_split_bom_refuses_corrupted_actual_second_piece_grid(monkeypatch, fault):
    pieces, _reads, split_after, total_rows, snapshot = _pd_split_bom_fixture(monkeypatch)
    second = pieces[1]
    lines = second._pd_grid_lines
    original_grid = tuple(lines)
    if fault == "malformed":
        lines[0] = lines[0][:-1]
    elif fault == "nonfinite":
        lines[0] = (*lines[0][:4], float("nan"), *lines[0][5:])
    elif fault == "missing-boundary":
        del lines[1]
    elif fault == "gap":
        # Keep every coordinate boundary but leave an interior horizontal gap.
        original = lines.pop(5)
        left, right = original[4], original[7]
        lines.extend((
            (*original[:7], left + (right - left) * 0.4, *original[8:]),
            (*original[:4], left + (right - left) * 0.6, *original[5:]),
        ))
    elif fault == "translated":
        lines[:] = [
            (*line[:4], line[4] + 0.001, *line[5:7], line[7] + 0.001, *line[8:])
            for line in lines
        ]
    elif fault == "hidden-column":
        # A leaked hidden native border is not part of the four-column grid.
        edge = lines[4]
        lines.append((
            *edge[:4], edge[4] + second._pd_state.columns[-1].width,
            *edge[5:7], edge[7] + second._pd_state.columns[-1].width, *edge[8:],
        ))
    elif fault in ("whole-table", "missing-repeated-header"):
        rows = (
            [0] * total_rows if fault == "whole-table"
            else range(split_after + 1, total_rows)
        )
        lines[:] = _pd_display_grid(second, rows, drawing.BOM_SECOND_ANCHOR)
    elif fault == "wrong-column-width":
        second._pd_state.columns[3].width = 0.013
        lines[:] = _pd_display_grid(
            second, [0, *range(split_after + 1, total_rows)], drawing.BOM_SECOND_ANCHOR
        )
    elif fault == "diagonal":
        lines[0] = (*lines[0][:7], lines[0][7] + 0.001, *lines[0][8:])
    elif fault == "nonplanar":
        lines[0] = (*lines[0][:-1], 0.001)
    elif fault == "outlying-extension":
        horizontal = lines[5]
        lines[5] = (*horizontal[:7], horizontal[7] + 0.001, *horizontal[8:])
    reasons = {
        "malformed": "line 0 is not a ten-value record",
        "nonfinite": "line 0 has non-finite values",
        "missing-boundary": "boundary counts are",
        "gap": "has incomplete horizontal boundary coverage",
        "translated": "displayed grid does not match its native annotation anchor",
        "hidden-column": "boundary counts are",
        "whole-table": "boundary counts are",
        "missing-repeated-header": "boundary counts are",
        "wrong-column-width": "column widths changed",
        "diagonal": "unsupported non-axis-aligned geometry",
        "nonplanar": "non-sheet Z coordinates",
        "outlying-extension": "has outlying horizontal boundary geometry",
    }
    assert tuple(lines) != original_grid
    with pytest.raises(RuntimeError, match=reasons[fault]):
        drawing._assert_bom_pieces(
            pieces, header_count=1, total_rows=total_rows,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            expected_snapshot=snapshot,
        )


@pytest.mark.parametrize("hidden_row", ("header", "first-data", "last-data"))
def test_split_bom_refuses_hidden_header_or_global_data_rows(monkeypatch, hidden_row):
    pieces, _association_reads, split_after, total_rows, expected_snapshot = (
        _pd_split_bom_fixture(monkeypatch)
    )
    row = {
        "header": 0,
        "first-data": split_after + 1,
        "last-data": total_rows - 1,
    }[hidden_row]
    second = pieces[1]
    second._pd_state.hidden_rows.add(row)
    assert second.RowHidden(row) is True
    assert second.RowHidden(split_after + 1 if row == 0 else 0) is False
    with pytest.raises(RuntimeError, match=f"row {row} is not proven visible"):
        drawing._assert_bom_pieces(
            pieces, header_count=1, total_rows=total_rows,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            expected_snapshot=expected_snapshot,
        )


@pytest.mark.parametrize(
    "fault", ("native-kind", "native-unhidden", "number-property", "native-number")
)
def test_split_bom_refuses_second_piece_native_binding_damage(monkeypatch, fault):
    pieces, _association_reads, split_after, total_rows, expected_snapshot = (
        _pd_split_bom_fixture(monkeypatch)
    )
    second = pieces[1]
    if fault == "native-kind":
        second._pd_state.columns[-1].kind = 202
    elif fault == "native-unhidden":
        second._pd_state.columns[-1].hidden = False
    elif fault == "number-property":
        second._pd_state.columns[1].property_name = "Description"
    else:
        component = second.GetComponents2(
            split_after + 1, drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )[0]
        native = component.GetModelDoc2()
        native.properties[(component.ReferencedConfiguration, "Number")] = "WRONG-NATIVE-NUMBER"
    with pytest.raises(RuntimeError):
        drawing._assert_bom_pieces(
            pieces, header_count=1, total_rows=total_rows,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            expected_snapshot=expected_snapshot,
        )


@pytest.mark.parametrize("fault", ("qty-hidden", "visible-qty", "visible-number"))
def test_split_bom_refuses_visible_damage_with_unchanged_native_snapshot(monkeypatch, fault):
    pieces, _reads, split_after, total_rows, expected_snapshot = _pd_split_bom_fixture(monkeypatch)
    second = pieces[1]
    before_cells = tuple(tuple(row) for row in second._pd_state.cells)
    before_members = tuple(tuple(group) for group in second._pd_state.native_rows)
    if fault == "qty-hidden":
        assert second.SetColumnHidden(5, False) is None
        assert second.SetColumnHidden(4, True) is None
    else:
        original_text = second.DisplayedText2.side_effect
        damaged_column = 3 if fault == "visible-qty" else 1

        def displayed(row, column, include_hidden):
            if row == split_after + 1 and column == damaged_column and include_hidden is False:
                return "WRONG-VISIBLE-CELL"
            return original_text(row, column, include_hidden)

        second.DisplayedText2.side_effect = displayed
    with pytest.raises(RuntimeError):
        drawing._assert_bom_pieces(
            pieces, header_count=1, total_rows=total_rows,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            expected_snapshot=expected_snapshot,
        )
    assert tuple(tuple(row) for row in second._pd_state.cells) == before_cells
    assert tuple(tuple(group) for group in second._pd_state.native_rows) == before_members


@pytest.mark.parametrize("fault", ("same-number-chain-swap", "spare-quantity"))
def test_split_bom_snapshot_refuses_membership_or_quantity_changes(monkeypatch, fault):
    pieces, _association_reads, _split_after, total_rows, expected_snapshot = (
        _pd_split_bom_fixture(monkeypatch)
    )
    keys = pieces[0]._pd_state.row_keys
    inner_row = keys.index("sh-vn-chain-link--InnerLink") + 1
    outer_row = keys.index("sh-vn-chain-link--OuterLink") + 1
    gear_row = keys.index("pd-transgear-removable") + 1
    if fault == "same-number-chain-swap":
        for piece in pieces:
            native_rows = piece._pd_state.native_rows
            for component in native_rows[inner_row - 1]:
                component.ReferencedConfiguration = "OuterLink Simplified"
            for component in native_rows[outer_row - 1]:
                component.ReferencedConfiguration = "InnerLink Simplified"
            assert len(native_rows[inner_row - 1]) == 34
            assert len(native_rows[outer_row - 1]) == 33
            cells = piece._pd_state.cells
            assert cells[inner_row][1] == cells[outer_row][1]
            assert (cells[inner_row][3], cells[outer_row][3]) == ("34", "33")
        message = "membership or quantities changed"
    else:
        for piece in pieces:
            piece._pd_state.cells[gear_row][3] = "2"
        message = "native occurrence count.*printed quantity"
    # Associative Number readback alone remains valid in both failure modes.
    for piece in pieces:
        _direction, _index, _count, start, end = piece.GetSplitInformation(0, 0, 0, 0)
        _drawing_tables.validate_bom_number_property(
            piece, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            label="paper-drive split",
            row_indices=tuple(range(max(start, 1), end + 1)),
        )
    with pytest.raises(RuntimeError, match=message):
        drawing._assert_bom_pieces(
            pieces, header_count=1, total_rows=total_rows,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            expected_snapshot=expected_snapshot,
        )


@pytest.mark.parametrize("coverage", ("duplicate", "missing"))
@pytest.mark.parametrize("hidden_header", (False, True))
def test_split_bom_snapshot_refuses_duplicate_or_missing_global_coverage(
    monkeypatch, coverage, hidden_header
):
    pieces, _association_reads, _split_after, total_rows, expected_snapshot = (
        _pd_split_bom_fixture(monkeypatch, coverage=coverage)
    )
    if hidden_header:
        # Invalid native coverage must be rejected before a visibility result
        # can be treated as evidence that any supplied row actually belongs.
        for piece in pieces:
            piece._pd_state.hidden_rows.add(0)
    with pytest.raises(RuntimeError, match="omit or repeat logical data rows"):
        drawing._assert_bom_pieces(
            pieces, header_count=1, total_rows=total_rows,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            expected_snapshot=expected_snapshot,
        )


@pytest.mark.parametrize("fault", ("different-selected-number", "missing-number"))
def test_number_binding_refuses_invalid_native_selected_config_properties(monkeypatch, fault):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    members = scene.state.native_rows[gear_row - 1]
    native = members[0].GetModelDoc2()
    if fault == "different-selected-number":
        native.properties[("T18 Simplified", "Number")] = "WRONG-T18"
        message = "associative Number"
    else:
        for component in members:
            native.properties[(component.ReferencedConfiguration, "Number")] = ""
        native.properties[("", "Number")] = ""
        message = "has no Number property"
    with pytest.raises(RuntimeError, match=message):
        scene.insert()


def test_number_binding_does_not_fabricate_a_canonical_number_for_bad_native_data(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    members = scene.state.native_rows[gear_row - 1]
    native = members[0].GetModelDoc2()
    for component in members:
        native.properties[(component.ReferencedConfiguration, "Number")] = "INTERNAL-GEAR-NUMBER"
    # A valid document fallback cannot replace a nonempty selected-config value.
    assert native.properties[("", "Number")] == drawing.BOM_PART_NUMBERS["pd-transgear-removable"]
    table = scene.insert()
    assert table.DisplayedText2(gear_row, 1, True) == "INTERNAL-GEAR-NUMBER"
    with pytest.raises(RuntimeError, match="associative Number"):
        drawing._validate_bom(
            scene.adapter, table, drawing._source_family_counts(scene.model),
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        )
