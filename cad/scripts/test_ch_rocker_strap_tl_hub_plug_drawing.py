"""Offline contracts for the rocker strap's hub plug (MHA-CH-13-TL-02)."""

from __future__ import annotations

import ast
import math
import sys
import tomllib
from pathlib import Path

import pytest

import _buildgraph as bg
import _config
import build_ch_rocker_strap_tl_hub_plug as part
import ch_rocker_arm_spec as arm
import ch_rocker_hub_fit as fit
import ch_rocker_strap_spec as strap
import ch_rocker_strap_tl_hub_plug_spec as spec
import draw_ch_rocker_strap_tl_hub_plug as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from test_pd_transgear_adapter_contract import (
    _adapter_calls,
    _adapter_methods,
    _missing,
    _signature,
    _tree,
)

INCH = 25.4
XX = printed_band_mm(2, unit="in")
XXX = printed_band_mm(3, unit="in")
SCRIPTS = Path(__file__).resolve().parent
PLAN = SCRIPTS.parent / "process" / "ch_rocker_strap" / "plan.toml"
STEM = "ch_rocker_strap_tl_hub_plug"


def _plan() -> dict:
    return tomllib.loads(PLAN.read_text(encoding="utf-8"))["parameters"]


def test_registry_row_is_inch_shop_tooling_with_a_learn_sheet() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-CH-13-TL-02"
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert row["tolerance_class"] == "machined_block"
    assert int(row["quantity"]) == 1
    # One material: the MATERIAL cell holds one line (LEARN review r5).
    assert row["material"] == "6061 ALUMINUM" and part.MATERIAL == "6061 Alloy"
    assert str(row["material_specification"]).startswith("6061 aluminum round")
    entry = DRAWINGS_BY_NAME[STEM]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert entry.script == Path(drawing.__file__).resolve()
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert "draw_ch_rocker_strap_tl_hub_plug.py" in PRECISION_MIGRATED_DRAWINGS
    assert bg.is_shop_fixture(STEM)
    for machine in bg.MACHINE_ASSEMBLIES:
        assert STEM not in bg.references_of(machine)


def test_mirrored_mates_match_the_strap_and_the_plan() -> None:
    """The spec copies these to keep its closure light; each copy must equal
    the module or plan that owns it."""
    assert spec.STRAP_HOLE_DIA == strap.HOLE_DIA == arm.HUB_DIA
    assert spec.STRAP_HOLE_LIMITS == pytest.approx(
        (
            strap.HOLE_DIA + fit.STRAP_HOLE_BAND[1],
            strap.HOLE_DIA + fit.STRAP_HOLE_BAND[0],
        )
    )
    assert spec.STRAP_THICKNESS_MIN == pytest.approx(
        arm.ARM_THICKNESS + arm.ARM_THICKNESS_BAND[1]
    )
    plan = _plan()
    assert spec.TAPE_STACK == plan["tape_stack_mm"]
    assert spec.TAPE_MIN == plan["tape_stack_min_mm"]
    assert spec.TAPE_MAX == plan["tape_stack_max_mm"]
    assert spec.COUNTERBORE_DIA >= plan["hub_relief_dia_mm"]
    assert spec.COUNTERBORE_DEPTH == pytest.approx(
        plan["hub_relief_depth_mm"], abs=0.01
    )


def test_mirrored_counterbore_matches_the_plate() -> None:
    import ch_rocker_strap_tl_sub_plate_spec as plate

    assert spec.COUNTERBORE_DIA == plate.HUB_CBORE_DIA
    assert spec.COUNTERBORE_DEPTH == plate.HUB_CBORE_DEPTH
    assert (spec.COUNTERBORE_BAND, -spec.COUNTERBORE_BAND) == plate.HUB_CBORE_BAND
    assert spec.COUNTERBORE_LOCATION_TOL == plate.HUB_LOCATION_TOL


def test_sizes_are_the_contract_and_its_ruled_changes() -> None:
    assert spec.BODY_DIA == pytest.approx(0.47 * INCH)
    # #3622: .170 -> .165, the counterbore's depth at its wizard .XX.
    assert spec.BODY_LENGTH == pytest.approx(0.165 * INCH)
    assert spec.OVERALL_LENGTH == pytest.approx(0.272 * INCH)
    assert spec.PILOT_DIA == pytest.approx(0.393 * INCH)
    assert spec.BORE_DIA == pytest.approx(
        0.201 * INCH
    )  # owner ruling 2026-11-23: #10-32, #7 drill
    assert spec.CHAMFER == pytest.approx(0.02 * INCH)


def test_the_plug_floats_so_the_fence_and_end_stop_locate_the_blank() -> None:
    """#3713: the plug no longer locates the blank. Body and pilot at their
    title-block bands drop into the smallest counterbore and enter the
    smallest reamed hole, and their least play takes up the counterbore's
    position band on both axes, so the plug cannot hold the blank off the
    fence or the end stop."""
    assert spec.BODY_LIMITS == pytest.approx((0.46 * INCH, 0.48 * INCH))
    assert spec.PILOT_LIMITS == pytest.approx((0.388 * INCH, 0.398 * INCH))
    assert spec.BODY_FLOAT == pytest.approx((0.010 * INCH, 0.050 * INCH))
    hole = spec.STRAP_HOLE_LIMITS
    least = hole[0] - spec.PILOT_LIMITS[1]
    greatest = hole[1] - spec.PILOT_LIMITS[0]
    assert (least, greatest) == pytest.approx(spec.PILOT_CLEARANCE)
    assert spec.PILOT_CLEARANCE == pytest.approx((0.0020 * INCH, 0.0125 * INCH))
    play = (spec.BODY_FLOAT[0] + spec.PILOT_CLEARANCE[0]) / 2.0
    assert play == pytest.approx(0.006 * INCH)
    offset = 0.002 * INCH * math.sqrt(2.0)
    assert play - offset > 0.001 * INCH
    # Nothing on the plug is a fit any longer.
    for text in spec.DIMENSION_CALLOUTS_BY_NAME.values():
        assert "FIT" not in text and "MEASURED" not in text
    assert spec.WALL_TEXT == "WALL .091 MIN"


def test_seated_on_the_floor_the_plug_stays_inside_the_strap_at_the_worst_case() -> (
    None
):
    """Plate frame, Z0 the floor the tape stack lies on; every band at its worst."""
    floor = (
        -spec.COUNTERBORE_DEPTH - 0.010 * INCH,
        -spec.COUNTERBORE_DEPTH + 0.010 * INCH,
    )
    shoulder_max = floor[1] + spec.BODY_LENGTH + XXX
    assert shoulder_max < 0.0
    assert shoulder_max == pytest.approx(-0.005 * INCH)
    pilot_top = (
        floor[0] + spec.OVERALL_LENGTH - XXX,
        floor[1] + spec.OVERALL_LENGTH + XXX,
    )
    assert pilot_top == pytest.approx(spec.PILOT_TOP_Z_RANGE)
    plan = _plan()
    strap_top_min = (
        plan["tape_stack_min_mm"] + arm.ARM_THICKNESS + arm.ARM_THICKNESS_BAND[1]
    )
    assert pilot_top[1] < strap_top_min
    assert spec.PILOT_TOP_Z == pytest.approx(2.21, abs=0.01)
    # The cylindrical land under the chamfer reaches past the strap's
    # underside (the stack's top at its thickest).
    assert pilot_top[0] - (spec.CHAMFER + XX) > plan["tape_stack_max_mm"]


def test_the_bore_clears_the_number_ten_screw_and_its_wall_meets_the_target() -> None:
    """Owner ruling 2026-11-23: "change the screw to #10-32. The sub-plate's
    tapped hole becomes #10-32 and the plug's bore .201 (#7 drill)."
    (2026-11-17's "Use a 1/4-20 hub screw." left .064 under the pilot.)"""
    assert spec.BORE_DIA > spec.SCREW_MAJOR_DIA == pytest.approx(0.190 * INCH)
    wall = (spec.PILOT_LIMITS[0] - spec.BORE_DIA - drilled_oversize_mm(unit="in")) / 2.0
    assert wall == pytest.approx(spec.WALL_MIN)
    assert WALL_FLOOR_MM < WALL_TARGET_MM <= wall
    assert spec.WALL_TEXT == "WALL .091 MIN"
    assert not spec.WALL_STATED
    assert spec.DIMENSION_CALLOUTS_BY_NAME["BoreDia"] == "DRILL THRU"
    row = _config.parts(spec.PART_NAME)
    assert "machinist_exceptions" not in row


def test_callouts_name_what_each_size_clears() -> None:
    callouts = spec.DIMENSION_CALLOUTS_BY_NAME
    assert callouts["BodyDia"] == "CLEARS MHA-CH-13-TL-01 COUNTERBORE"
    assert callouts["PilotDia"] == "CLEARS MHA-CH-13 HUB HOLE"
    assert callouts["BodyLength"] == "SHOULDER BELOW\nMHA-CH-13-TL-01 FLOOR"
    assert callouts["OverallLength"] == "PILOT TOP BELOW\nMHA-CH-13 TOP FACE"
    assert callouts["ChamferSize"] == "X 45\u00b0"
    assert _config.parts("ch-rocker-strap-tl-sub-plate")["number"] == spec.PLATE_NUMBER
    assert _config.parts("ch-rocker-strap")["number"] == spec.STRAP_NUMBER


def test_places_and_bands_are_the_parts() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "BodyDia": 2,
        "BoreDia": 3,
        "BodyLength": 3,
        "OverallLength": 3,
        "PilotDia": 3,
        "ChamferSize": 2,
    }
    # Every size takes its title-block row: no explicit band, no reference.
    assert model_toleranced_dimensions(part) == {}
    tree = _tree(Path(part.__file__))
    called = {
        getattr(node.func, "id", None)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "set_limits" not in called
    assert "(<MOD-DIAM>" not in Path(part.__file__).read_text(encoding="utf-8")


def test_volume_is_the_two_annuli_less_the_chamfer() -> None:
    def ring(d: float, length: float) -> float:
        return math.pi / 4.0 * (d**2 - spec.BORE_DIA**2) * length

    c = spec.CHAMFER
    expected = (
        ring(spec.BODY_DIA, spec.BODY_LENGTH)
        + ring(spec.PILOT_DIA, spec.OVERALL_LENGTH - spec.BODY_LENGTH)
        - math.pi * c**2 * (spec.PILOT_DIA / 2.0 - c / 3.0)
    )
    assert spec.V_PLUG == pytest.approx(expected)


def test_every_marked_dimension_ends_on_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.SIDE_KEEP)
    assert set(drawing.MOVED) == {"BodyDia", "PilotDia"} < set(drawing.END_KEEP)


def test_the_isometric_is_in_the_hidden_line_loop() -> None:
    tree = _tree(Path(drawing.__file__))
    loops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Tuple)
        and any(
            isinstance(call, ast.Call)
            and getattr(call.func, "id", None) == "set_hidden_lines_removed"
            for call in ast.walk(node)
        )
    ]
    assert len(loops) == 1
    assert {ast.unparse(e) for e in loops[0].iter.elts} == {"end", "side", "iso"}


Box = tuple[float, float, float, float]  # x0, x1, y0, y1 (sheet metres)


def _overlap(a: Box, b: Box) -> bool:
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def _block(xy: tuple[float, float], x0: float, x1: float) -> Box:
    return (x0, x1, xy[1] - drawing.BLOCK_BELOW, xy[1] + drawing.BLOCK_ABOVE)


def _sheet_boxes() -> dict[str, Box]:
    """Every view and text block, sized from farm r1's layout audit
    (``draw_ch_rocker_strap_tl_hub_plug``'s block constants)."""
    s = drawing._S
    body_half = spec.BODY_DIA / 2.0 * s
    iso_half = spec.BODY_DIA / 2000.0 * drawing.ISO_SCALE[0] * 1.25
    end, side, iso = drawing.END_CENTER, drawing.SIDE_CENTER, drawing.ISO_CENTER
    keep = {**drawing.END_KEEP, **drawing.SIDE_KEEP, **drawing.MOVED}
    half = drawing.LENGTH_BLOCK_HALF_WIDTH
    body = keep["BodyDia"]
    pilot = keep["PilotDia"]
    return {
        "end view": (
            end[0] - body_half,
            end[0] + body_half,
            end[1] - body_half,
            end[1] + body_half,
        ),
        "side view": (
            drawing.TOP_X,
            drawing.BOTTOM_X,
            side[1] - body_half,
            side[1] + body_half,
        ),
        "isometric": (
            iso[0] - iso_half,
            iso[0] + iso_half,
            iso[1] - iso_half,
            iso[1] + iso_half,
        ),
        "iso note": (
            drawing.ISO_NOTE_XY[0],
            drawing.ISO_NOTE_XY[0] + 0.060,
            drawing.ISO_NOTE_XY[1],
            drawing.ISO_NOTE_XY[1] + 0.005,
        ),
        # The bore's block, ~25 mm wide, centred on its keep.
        "bore": _block(
            keep["BoreDia"], keep["BoreDia"][0] - 0.013, keep["BoreDia"][0] + 0.013
        ),
        "pilot": _block(pilot, pilot[0] - drawing.PILOT_BLOCK_WIDTH, pilot[0]),
        "body": _block(
            body,
            body[0] - drawing.BODY_BLOCK_HALF_WIDTH,
            body[0] + drawing.BODY_BLOCK_HALF_WIDTH,
        ),
        "body length": _block(
            keep["BodyLength"],
            keep["BodyLength"][0] - half,
            keep["BodyLength"][0] + half,
        ),
        "overall": _block(
            keep["OverallLength"],
            keep["OverallLength"][0] - half,
            keep["OverallLength"][0] + half,
        ),
        # .02 / X 45°, ~15 mm wide.
        "chamfer": _block(
            keep["ChamferSize"],
            keep["ChamferSize"][0] - 0.008,
            keep["ChamferSize"][0] + 0.008,
        ),
    }


def test_the_end_view_projects_level_with_the_side_view() -> None:
    """Machinist review r9 (rule 15, third angle): the end view looks at the
    pilot's top, which stands at the side view's left end, so it is a left
    view: level with the side view's axis and left of it."""
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    body_half = spec.BODY_DIA / 2.0 * drawing._S
    assert drawing.END_CENTER[0] + body_half < drawing.TOP_X


def test_no_two_blocks_or_views_overlap_and_all_stand_on_the_sheet() -> None:
    """Farm r1 defects 1-3: the body's block on the side view, the .170 on
    the .272, the pilot's block on the bore's. B landscape 0.4318 x 0.2794,
    border 0.0127; title block x >= 0.216 below y 0.066."""
    boxes = _sheet_boxes()
    names = sorted(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert not _overlap(boxes[a], boxes[b]), (a, b)
    title = (0.216, 0.4191, 0.0127, 0.066)
    for name, box in boxes.items():
        assert 0.0127 < box[0] and box[1] < 0.4191, name
        assert 0.0127 < box[2] and box[3] < 0.2667, name
        assert not _overlap(box, title), name


def test_each_dimension_line_reaches_its_block_without_crossing_another() -> None:
    """The diameters' lines run vertically from the part to their blocks; the
    lengths' blocks stand outside their extension lines (r1: two extension
    lines ran through their own text)."""
    boxes = _sheet_boxes()
    s = drawing._S
    side = drawing.SIDE_CENTER
    body_half = spec.BODY_DIA / 2.0 * s
    pilot_half = spec.PILOT_DIA / 2.0 * s
    lines = {
        # The pilot's: just left of the pilot, from its lower edge up.
        "pilot": (
            drawing.PILOT_ON_SIDE[0],
            side[1] - pilot_half,
            drawing.PILOT_ON_SIDE[1],
        ),
        # The body's: right of the body, from its lower edge up.
        "body": (drawing.BODY_ON_SIDE[0], side[1] - body_half, drawing.BODY_ON_SIDE[1]),
        # The two length extension lines that drop furthest: the pilot's top
        # face (the overall) and the body's bottom face (both lengths).
        "overall": (drawing.TOP_X, drawing.SIDE_KEEP["OverallLength"][1], side[1]),
        "body length": (
            drawing.BOTTOM_X,
            drawing.SIDE_KEEP["OverallLength"][1],
            side[1],
        ),
    }
    assert drawing.PILOT_ON_SIDE[0] < drawing.TOP_X
    assert drawing.BODY_ON_SIDE[0] > drawing.BOTTOM_X
    for owner, (x, y0, y1) in lines.items():
        for name, box in boxes.items():
            if name in (owner, "side view"):
                continue
            assert not (box[0] < x < box[1] and box[2] < y1 and y0 < box[3]), (
                owner,
                name,
            )
    # The body's block stands above its upper extension line; the body
    # length's block below its lower one.
    assert boxes["body"][2] > side[1] + body_half
    assert boxes["body length"][3] < side[1] - body_half
    # Each length's block stands outside its own extension lines.
    assert boxes["body length"][0] > drawing.BOTTOM_X
    assert boxes["overall"][1] < drawing.TOP_X
    assert drawing.BOTTOM_X - drawing.TOP_X == pytest.approx(spec.OVERALL_LENGTH * s)


@pytest.mark.parametrize(
    "recipe",
    ["build_ch_rocker_strap_tl_hub_plug.py", "draw_ch_rocker_strap_tl_hub_plug.py"],
)
def test_every_direct_adapter_call_exists_and_binds(recipe: str) -> None:
    tree = _tree(SCRIPTS / recipe)
    calls = _adapter_calls(tree)
    assert calls, recipe
    assert not _missing(tree), sorted(_missing(tree))
    for call in calls:
        path, method = _adapter_methods()[call.func.attr]
        try:
            _signature(method).bind(
                call.func.value,
                *call.args,
                **{k.arg: k.value for k in call.keywords},
            )
        except TypeError as error:
            pytest.fail(f"{recipe}:{call.lineno}: {call.func.attr}: {error}")


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
