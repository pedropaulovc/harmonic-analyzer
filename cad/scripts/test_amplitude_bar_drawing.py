"""Offline contracts for the amplitude-bar drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import amplitude_bar_notes
import amplitude_bar_spec
import draw_amplitude_bar as drawing
import build_amplitude_bar as bar
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm, drill_process


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/amplitude-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/amplitude-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/amplitude-bar_drawing.png")
    assert DRAWINGS_BY_NAME["amplitude_bar"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert bar.DRAWING_DIMENSIONS is amplitude_bar_spec.DRAWING_DIMENSIONS
    marked = set().union(*amplitude_bar_spec.DRAWING_DIMENSIONS.values())
    keeps = (
        drawing.FRONT_KEEP,
        drawing.RIGHT_KEEP,
        drawing.TOP_KEEP,
        drawing.DETAIL_A_KEEP,
        drawing.DETAIL_B_KEEP,
    )
    kept = set().union(*keeps)
    assert kept == marked
    assert sum(len(keep) for keep in keeps) == len(marked)  # one view each
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked


def test_part_geometry_matches_the_spec() -> None:
    assert amplitude_bar_spec.BAR_LENGTH == bar.BAR_LENGTH
    assert amplitude_bar_spec.BAR_WIDTH == bar.BAR_WIDTH
    assert bar.TOP_PIN_HOLE_SPEC is amplitude_bar_spec.TOP_PIN_HOLE_SPEC
    assert blind_cut_dia_mm(amplitude_bar_spec.TOP_PIN_HOLE_SPEC) == 1.994


def test_sheet_runs_at_1_to_4_with_1_to_8_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 8)" in source  # the isometric override
    assert "scale=(4, 1)" in source  # the top end-view section override
    assert amplitude_bar_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:8"
    assert amplitude_bar_notes.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_carry_the_notches_and_hole() -> None:
    notes = amplitude_bar_notes.DRAWING_NOTES
    assert "END NOTCHES (DETAILS A, B)" in notes
    assert drill_process(amplitude_bar_spec.TOP_PIN_HOLE_SPEC) in notes
    assert "LINEAR +/-" not in notes
    assert "STEEL" not in notes
    assert "CHROME" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_bottom_notch_depth_band_is_native_on_its_dimension() -> None:
    """User ruling 2026-09-26: a deep notch drops the cheeks onto the rocker
    hub one for one, so the depth may only come out shallow. Codex #936
    PRRT_kwDOPHDy386mWF0L, policy rule 2: that band is the part's, native on
    BottomNotchHeight from the one constant the cheek-over-hub test reads,
    printed in DETAIL A -- and no note carries it or any notch size."""
    from _drawing_contract import model_toleranced_dimensions

    upper, lower = amplitude_bar_spec.BOTTOM_NOTCH_DEPTH_BAND
    assert lower == -0.50 < upper == 0.0
    assert not hasattr(amplitude_bar_notes, "BOTTOM_NOTCH_DEPTH_BAND")
    assert model_toleranced_dimensions(bar)[("BarProfile", "BottomNotchHeight")] == (
        "*deviations(BOTTOM_NOTCH_DEPTH_BAND)"
    )
    assert "BottomNotchHeight" in drawing.DETAIL_A_KEEP
    notes = " ".join(
        line.strip() for line in amplitude_bar_notes.DRAWING_NOTES.splitlines()
    )
    assert "DEEP" not in notes
    assert "+0/" not in notes
    assert "3.18" not in notes and "2.38" not in notes and "12.70" not in notes
    assert bar.DRAWING_NOTES is amplitude_bar_notes.DRAWING_NOTES


# Each printed profile dimension's two sketch endpoints (part x, y mm): a
# detail drops any dimension whose reference lies outside its fence.
_W = amplitude_bar_spec.BAR_WIDTH
_O = (_W - amplitude_bar_spec.BOTTOM_NOTCH_WIDTH) / 2.0  # bottom ledge
_OT = (_W - amplitude_bar_spec.TOP_NOTCH_WIDTH) / 2.0  # top ledge
_L = amplitude_bar_spec.BAR_LENGTH
_DETAIL_DIMENSION_ENDS = {
    "BottomLeftLedge": ((0.0, 0.0), (_O, 0.0)),
    "BottomNotchHeight": ((_O, 0.0), (_O, amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT)),
    "BottomNotchWidth": (
        (_O, amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT),
        (_W - _O, amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT),
    ),
    "TopRightLedge": ((_W, _L), (_W - _OT, _L)),
    "TopNotchHeight": (
        (_W - _OT, _L),
        (_W - _OT, _L - amplitude_bar_spec.TOP_NOTCH_HEIGHT),
    ),
    "TopNotchWidth": (
        (_W - _OT, _L - amplitude_bar_spec.TOP_NOTCH_HEIGHT),
        (_OT, _L - amplitude_bar_spec.TOP_NOTCH_HEIGHT),
    ),
}


def test_notch_details_frame_their_ends_and_place_text_outside_the_bar() -> None:
    """Both details run 4:1 (Main ruling 2026-09-27). DETAIL A takes in the
    foot notch and the open end; DETAIL B the 12.7 top notch. Every printed
    dimension's ends lie inside its fence; each depth's text stands outside
    the bar's side and each ledge/width row outside its open end, where the
    witnesses run through air."""
    spec = amplitude_bar_spec
    a, b = drawing.DETAIL_A, drawing.DETAIL_B
    assert a.scale == b.scale == (4, 1)
    for detail, keep in ((a, drawing.DETAIL_A_KEEP), (b, drawing.DETAIL_B_KEEP)):
        fx, fy = detail.fence_mm
        for name in keep:
            for x, y in _DETAIL_DIMENSION_ENDS[name]:
                assert math.hypot(x - fx, y - fy) < detail.radius_mm - 0.5, name
    depth_x, depth_y = drawing.DETAIL_A_KEEP["BottomNotchHeight"]
    assert depth_x < a.centre[0] - a.radius_mm * a.mm  # left of the fence
    assert (
        a.sheet_xy(0.0, 0.0)[1] < depth_y < a.sheet_xy(0.0, spec.BOTTOM_NOTCH_HEIGHT)[1]
    )
    # r743-6b (64fedd3cc): a width with its +0.3/0.0 stack prints ~20 mm
    # wide; centred on the ~12.4 mm mouth it straddled both extension lines.
    # Each width's text now stands west of the bar, clear of it.
    ledge_x, ledge_y = drawing.DETAIL_A_KEEP["BottomLeftLedge"]
    width_x, width_y = drawing.DETAIL_A_KEEP["BottomNotchWidth"]
    assert width_y < ledge_y < a.sheet_xy(0.0, 0.0)[1]
    assert ledge_y - width_y >= 0.007  # the stack's half-height plus a line
    assert ledge_x < a.sheet_xy(0.0, 0.0)[0]
    assert width_x + 0.010 < a.sheet_xy(0.0, 0.0)[0]
    assert (
        drawing.DETAIL_B_KEEP["TopNotchHeight"][0] > b.sheet_xy(spec.BAR_WIDTH, 0.0)[0]
    )
    top_row = {drawing.DETAIL_B_KEEP[n][1] for n in ("TopRightLedge", "TopNotchWidth")}
    (row_y,) = top_row
    assert row_y > b.sheet_xy(0.0, spec.BAR_LENGTH)[1]
    assert drawing.DETAIL_B_KEEP["TopNotchWidth"][0] + 0.010 < b.sheet_xy(0.0, 0.0)[0]
    assert (
        drawing.DETAIL_B_KEEP["TopRightLedge"][0] > b.sheet_xy(spec.BAR_WIDTH, 0.0)[0]
    )
    # Both details and their labels stay on the sheet, clear of the title
    # block (x >= 0.218 below y 0.065), the notes block (right edge ~0.237),
    # the end-view note (from x 0.205) and the isometric (x 0.330, top 0.181).
    for detail in (a, b):
        radius = detail.radius_mm * detail.mm
        assert detail.label_xy[1] - 0.010 > 0.0127
        assert detail.centre[1] + radius < 0.2667
    assert drawing._DETAIL_B_ROW_Y + 0.004 < 0.2667
    assert a.centre[0] + a.radius_mm * a.mm < 0.205
    assert b.centre[0] - b.radius_mm * b.mm > 0.240
    assert b.label_xy[0] + 0.022 < drawing.ISO_CENTER[0] - 0.002


def test_notch_centring_bands_ride_each_details_ledge_not_a_note() -> None:
    """Main ruling A(a) 2026-09-27 (Codex #936 PRRT_kwDOPHDy386mWF0L): the
    'CENTRED ON THE WIDTH WITHIN 0.10' note becomes a native +/-0.05 on the
    NotchOffset ledge each detail prints."""
    from _drawing_contract import model_toleranced_dimensions

    assert amplitude_bar_spec.NOTCH_OFFSET_TOLERANCE_MM == 0.05
    assert amplitude_bar_spec.BOTTOM_NOTCH_OFFSET == _O == bar.BOTTOM_NOTCH_OFFSET
    assert amplitude_bar_spec.TOP_NOTCH_OFFSET == _OT == bar.TOP_NOTCH_OFFSET
    bands = model_toleranced_dimensions(bar)
    for name, keep in (
        ("BottomLeftLedge", drawing.DETAIL_A_KEEP),
        ("TopRightLedge", drawing.DETAIL_B_KEEP),
    ):
        assert bands[("BarProfile", name)] == "NOTCH_OFFSET_TOLERANCE_MM"
        assert name in keep
        assert amplitude_bar_spec.DRAWING_PRECISION["BarProfile"][name] == 2
    notes = " ".join(
        line.strip() for line in amplitude_bar_notes.DRAWING_NOTES.splitlines()
    )
    assert "CENTRED" not in notes and "WITHIN" not in notes


def test_notes_keep_only_the_ruled_prose() -> None:
    """Note 2 keeps its orientation prose and the Main-ruled R0.40 MAX
    exception word for word; the Ra note is gone and PLATING renumbers."""
    assert amplitude_bar_notes.DRAWING_NOTES.splitlines() == [
        "1. BAR SECTION 6.35 SQUARE.",
        "2. END NOTCHES (DETAILS A, B):",
        "   BOTH THRU THE FULL DEPTH, OPEN TO",
        "   OPPOSITE ENDS, IN ONE COMMON PLANE;",
        "   ROOTS R0.40 MAX.",
        f"3. TOP PIN HOLE {drill_process(amplitude_bar_spec.TOP_PIN_HOLE_SPEC)} THRU BOTH",
        "   TOP-NOTCH CHEEKS AT MID-DEPTH,",
        "   6.35 BELOW THE BAR TOP.",
        "4. DIMS APPLY AFTER PLATING.",
    ]


def test_functional_notch_finish_is_a_native_symbol_on_the_floor() -> None:
    """Main ruling B 2026-09-27: the foot notch floor's Ra 0.8 is a native
    finish symbol on the floor in DETAIL A, authored on the part, not a note."""
    import amplitude_bar_drawing_spec as finish_spec
    from _gtol_spec import PlanarFace
    from _surface_finish import GROUND, surface_finish_by_key

    control = surface_finish_by_key(finish_spec.SURFACE_FINISHES, "bottom_notch_floor")
    assert control.roughness_ra == GROUND == "0.8"
    assert control.face == PlanarFace(
        (0, -1, 0), -amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT
    )
    assert len(finish_spec.SURFACE_FINISHES) == 1
    assert "Ra" not in amplitude_bar_notes.DRAWING_NOTES
    part_source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bottom_notch_floor")' in source
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert drawing.FINISH_CHAR_HEIGHT == 0.0025
    # The channel/magnifier/summing closure imports amplitude_bar_spec; the
    # finish controls stay out of it.
    spec_source = Path(amplitude_bar_spec.__file__).read_text(encoding="utf-8")
    assert "SurfaceFinishControl" not in spec_source


def test_floor_finish_leader_runs_through_the_mouth_crossing_only_a_witness() -> None:
    """The symbol (~17 mm wide) cannot stand in the 12.7 mm mouth; its bent
    leader climbs from under the right cheek through the mouth to the floor,
    crossing the right witness between the bar's end and the width row, never
    the width's dimension line, its text or the cheek. The width's text stands
    west of the bar, so its dimension line runs west from the right witness
    and the air east of that witness is the symbol's."""
    a = drawing.DETAIL_A
    spec = amplitude_bar_spec
    ax, ay = drawing.FLOOR_FINISH_ATTACH
    vx, vy = drawing.FLOOR_FINISH_SYMBOL
    kx = vx - drawing.FINISH_SHOULDER  # the shoulder runs toward the attach
    end_y = a.sheet_xy(0.0, 0.0)[1]
    left_wall = a.sheet_xy(_O, 0.0)[0]
    right_wall = a.sheet_xy(_O + spec.BOTTOM_NOTCH_WIDTH, 0.0)[0]
    bar_right = a.sheet_xy(_W, 0.0)[0]
    row_y = drawing.DETAIL_A_KEEP["BottomNotchWidth"][1]

    assert ay == a.sheet_xy(0.0, spec.BOTTOM_NOTCH_HEIGHT)[1]  # on the floor
    assert left_wall < ax < right_wall

    def x_at(y: float) -> float:
        return kx + (ax - kx) * (y - vy) / (ay - vy)

    # Leaves the mouth clear of the cheek's corner.
    assert left_wall + 0.001 < x_at(end_y) < right_wall - 0.001
    # Crosses the right witness between the bar's end and the row...
    t = (kx - right_wall) / (kx - ax)
    witness_y = vy + t * (ay - vy)
    assert row_y + 0.002 < witness_y < end_y - 0.002
    # ...and stays east of that witness below it, above the width row: the
    # width's line and text lie west of the witness (r743-6b had the text on
    # the mouth, under the leader).
    assert drawing.DETAIL_A_KEEP["BottomNotchWidth"][0] < left_wall
    assert kx > right_wall + 0.001
    assert vy > row_y + 0.002
    # The symbol body (~2.5 mm left of the vertex to ~15 mm right, 5.4 mm up)
    # stands under the right cheek, clear of the bar, inside the fence.
    assert vx - 0.0025 > right_wall + 0.004
    assert vy + 0.0054 < end_y - 0.004
    for x, y in ((vx + 0.015, vy), (vx + 0.015, vy + 0.0054)):
        assert math.dist((x, y), a.centre) < a.radius_mm * a.mm
    assert vy + 0.0054 < end_y and vx + 0.015 > bar_right  # under, past the cheek


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("amplitude-bar")
    assert spec["material_specification"] == "AISI 1018 cold-rolled steel, 6.35 sq"
    assert spec["finish"] == "bright chrome plated"
    assert int(spec["quantity"]) == 20


def test_each_notch_minimum_clears_its_plate_at_max_material() -> None:
    """User ruling 2026-09-27 (#1038): a notch is never narrower than the
    plate it straddles. Its minimum -- the modelled nominal -- is the plate at
    max material plus MIN_END_PLAY; the band is +0.30/0, native on the width."""
    import channel_lever_spec as lever
    import rocker_arm_notes
    import rocker_arm_spec as rocker
    import rocker_bank_layout as bank
    from _drawing_contract import model_toleranced_dimensions

    spec = amplitude_bar_spec
    # The restated plate constants are their sources'.
    assert spec.LEVER_THICKNESS == lever.LEVER_THICKNESS
    lever_print = (
        f"{lever.LEVER_THICKNESS:.2f} +/-{spec.LEVER_THICKNESS_TOLERANCE:.2f} OVERALL"
    )
    assert lever_print in lever.DRAWING_NOTES
    assert spec.STRAP_THICKNESS == rocker.ARM_THICKNESS
    assert spec.STRAP_THICKNESS_TOLERANCE == rocker.LINEAR_2PL  # printed at .XX
    assert f"STRAP {rocker.ARM_THICKNESS:.2f} THICK" in rocker_arm_notes.DRAWING_NOTES
    assert spec.STRADDLE_RUNNING_FLOOR == bank.MIN_END_PLAY

    upper, lower = spec.NOTCH_WIDTH_BAND
    assert (upper, lower) == (0.30, 0.0)
    for width, plate, tolerance in (
        (spec.TOP_NOTCH_WIDTH, spec.LEVER_THICKNESS, spec.LEVER_THICKNESS_TOLERANCE),
        (spec.BOTTOM_NOTCH_WIDTH, spec.STRAP_THICKNESS, spec.STRAP_THICKNESS_TOLERANCE),
    ):
        least = width + lower
        assert least >= plate + tolerance + bank.MIN_END_PLAY - 1e-9
        assert least - (plate + tolerance + bank.MIN_END_PLAY) < 0.01  # the minimum
    assert spec.TOP_NOTCH_WIDTH == 3.20
    assert spec.BOTTOM_NOTCH_WIDTH == 3.11
    assert bar.TOP_NOTCH_WIDTH is spec.TOP_NOTCH_WIDTH
    assert bar.BOTTOM_NOTCH_WIDTH is spec.BOTTOM_NOTCH_WIDTH

    bands = model_toleranced_dimensions(bar)
    for name in ("BottomNotchWidth", "TopNotchWidth"):
        assert bands[("BarProfile", name)] == "*deviations(NOTCH_WIDTH_BAND)"
        assert spec.DRAWING_PRECISION["BarProfile"][name] == 2


@pytest.mark.xfail(
    strict=True,
    reason="#1038: at the printed bands a bar's notch float can close the "
    "0.7065 side gap to its neighbour (user ruling 2026-09-27: ship as a "
    "known issue with interim bands)",
)
def test_neighbouring_bars_keep_a_running_gap_at_the_printed_worst_case() -> None:
    """Bars 6.35 wide sit at the 7.0565 station pitch. Each floats on its
    straddled plate by (notch max - plate min); two neighbours floating toward
    each other close the side gap by that much, at the top and at the foot."""
    import rocker_bank_layout as bank

    spec = amplitude_bar_spec
    gap = bank.PITCH - spec.BAR_WIDTH
    upper, _lower = spec.NOTCH_WIDTH_BAND
    for width, plate, tolerance in (
        (spec.TOP_NOTCH_WIDTH, spec.LEVER_THICKNESS, spec.LEVER_THICKNESS_TOLERANCE),
        (spec.BOTTOM_NOTCH_WIDTH, spec.STRAP_THICKNESS, spec.STRAP_THICKNESS_TOLERANCE),
    ):
        float_max = (width + upper) - (plate - tolerance)
        assert gap - float_max >= bank.MIN_END_PLAY


def test_details_are_cropped_model_views_dimensioned_before_the_crop() -> None:
    """r743-6 (d92938949, leaf 20260927T020523Z-1-e3f9f1f7): the front view's
    import took the notch dimensions and deleted them, then a native detail of
    it imported nothing (available=[]). Each detail is now a 4:1 *Front model
    view, dimensioned uncropped, then cropped (the pc-r15 kink-detail pattern,
    d6b8ed93f), and both details import before the front view."""
    import ast
    import inspect

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "CreateDetailViewAt4" not in source
    tree = ast.parse(source)

    def calls(function: str) -> list[str]:
        node = next(
            item
            for item in ast.walk(tree)
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == function
        )
        found = []
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                name = getattr(call.func, "id", None) or getattr(call.func, "attr", "")
                found.append((call.lineno, call.col_offset, name))
        return [name for _line, _col, name in sorted(found)]

    order = calls("_dimension_then_crop")
    assert order.index("curate_view_dimensions") < order.index("_crop_detail_view")
    assert order.count("_view_dimension_names") == 2
    build = calls("build")
    assert build.index("_placed_detail_view") < build.index("_dimension_then_crop")
    assert build.index("_dimension_then_crop") < build.index("curate_view_dimensions")
    assert build.index("curate_view_dimensions") < build.index("_mark_detail_on_front")
    assert "Crop2" in inspect.getsource(drawing._crop_detail_view)
    for detail in (drawing.DETAIL_A, drawing.DETAIL_B):
        assert detail.label_text == f"DETAIL {detail.label}\nSCALE 4 : 1"
        assert detail.crop_radius == pytest.approx(detail.radius_mm * 4 / 1000)
        assert detail.mark_radius == pytest.approx(detail.radius_mm / 4 / 1000)
        # The label note's two lines stay on the sheet.
        assert detail.label_xy[1] - 0.012 > 0.0127
