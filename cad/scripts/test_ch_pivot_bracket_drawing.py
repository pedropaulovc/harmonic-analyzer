from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import build_ch_pivot_bracket as part
import ch_pivot_bracket_drawing_spec as drawing_spec
import ch_pivot_bracket_spec as spec
import draw_ch_pivot_bracket as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from ch_pivot_bracket_sides import (
    FOOT_LEN,
    FOOT_Z1,
    HEAD_TO_EAR_FACE_MIN,
    HOLE_STATION,
    HOLE_Z,
)

_FRAME_M = 0.0127


def _drawing_source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_registry_row_names_the_bracket_outputs() -> None:
    row = DRAWINGS_BY_NAME["ch_pivot_bracket"]
    assert row.part == "ch_pivot_bracket"
    assert row.script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-pivot-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-pivot-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-pivot-bracket_drawing.png")


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is drawing_spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is drawing_spec.DRAWING_DIMENSIONS
    marked = set().union(*drawing_spec.DRAWING_DIMENSIONS.values())
    # Every marked dimension is placed by exactly one view; an unplaced import
    # is deleted silently, a kept name the part never marks never prints.
    keeps = (
        set(drawing.FRONT_KEEP),
        set(drawing.TOP_KEEP),
        set(drawing.RIGHT_KEEP_NAMES),
    )
    assert set().union(*keeps) == marked
    assert sum(len(names) for names in keeps) == len(marked)
    # Every manufactured feature is sized and located: foot (width, length,
    # height), ear (thickness; its width is the foot's), arch (radius, the
    # overall height to its apex), bore (size, height, lateral), hold-down
    # hole (size, station, lateral), the apex tap (native callout + station)
    # and the foot-to-ear corner's MAX radius.
    assert marked == {
        "FootW",
        "FootLen",
        "FootHt",
        "EarThick",
        "ArchRadius",
        "OverallHeight",
        "BoreCz",
        "ShaftBoreDia",
        "BoreLateral",
        "HoleStation",
        "HoleDia",
        "HoleLateral",
        "SetScrewLocation",
        "CornerRadius",
    }
    assert spec.EAR_W == spec.FOOT_W


def test_the_part_owns_every_printed_decimal_place() -> None:
    assert drawing_spec.DRAWING_PRECISION_BY_NAME == {
        **{name: 2 for name in set().union(*drawing_spec.DRAWING_DIMENSIONS.values())},
        **{
            name: 3
            for name in ("EarThick", "ShaftBoreDia", "HoleDia", "SetScrewLocation")
        },
    }
    assert drawing.DRAWING_PRECISION_BY_NAME is drawing_spec.DRAWING_PRECISION_BY_NAME
    assert part.DRAWING_PRECISION is drawing_spec.DRAWING_PRECISION
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    # Every height is a model dimension now (#1371 r1: the overall height runs
    # from the seat); the one sheet-made length, the bore axis to the apex
    # (owner Q12), is a REFERENCE that sets no precision of its own.
    assert not hasattr(drawing_spec, "DRAWING_REFERENCE_PRECISION")
    assert "_set_reference_precision" not in _drawing_source()
    assert "AddVerticalDimension2" not in _drawing_source()
    assert "SetPrecision3" not in _drawing_source()


def test_bore_axis_to_apex_prints_as_a_reference_in_the_foot_height_lane() -> None:
    """Owner Q12 (2026-10-16): the arch's centre stands ARCH_LIFT over the
    bore, so the sheet prints the metal over the bore as the bore axis to the
    apex, a REF chained on the bore height between its extension lines."""
    assert spec.APEX_ABOVE_BORE == pytest.approx(9.852)
    assert spec.ARCH_LIFT == pytest.approx(1.724)
    assert 0.0 < spec.ARCH_LIFT < spec.BORE_DIA / 2.0
    x, y = drawing.APEX_REFERENCE_TEXT_XY
    assert x == drawing.FRONT_KEEP["FootHt"][0]
    assert drawing.FRONT_KEEP["BoreCz"][0] < x < drawing.FRONT_CENTER[0]
    assert drawing._front_y(spec.BORE_H) < y < drawing._front_y(spec.EAR_TOP_Y)
    assert drawing.APEX_REFERENCE_PLACES == 2
    source = _drawing_source()
    assert "set_reference_dimension(" in source
    assert "_add_apex_reference(adapter, front)" in source


def test_each_hole_keeps_one_centre_mark() -> None:
    # The template may mark the holes as each view is placed; the explicit
    # AutoInsertCenterMarks2 then printed every mark twice (Q12 r1/r2, #913).
    source = _drawing_source()
    assert "if _center_mark_count(view) == 0 and not auto_center_marks(" in source
    assert (drawing.FRONT_CENTER_MARKS, drawing.PLAN_CENTER_MARKS) == (1, 2)


def test_model_bands_come_from_named_spec_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("Ear", "EarThick"): "EAR_T_BAND",
        ("SetScrewReference", "SetScrewLocation"): "SET_SCREW_STATION_BAND",
        ("ShaftBoreProfile", "ShaftBoreDia"): "*deviations(BORE_DIA_BAND)",
    }
    assert part.EAR_T_BAND == part.SET_SCREW_STATION_BAND == pytest.approx(0.1016)
    # The hold-down station rides the title block's .XX too (#1371 review: a
    # band on a clearance hole's station holds nothing), as do the overall
    # and the bore heights the tap's thread is counted against.
    assert spec.STATION_BAND == spec.HEIGHT_BAND == pytest.approx(0.254)
    assert "HoleStation" not in drawing.DIMENSION_CALLOUTS
    assert round(HOLE_STATION / 25.4, 2) * 25.4 == pytest.approx(HOLE_STATION)
    # The foot length rides the title block's .XX (its wall to the hold-down
    # hole is sized for it), so its sheet value carries no band of its own.
    assert spec.FOOT_LEN_BAND == spec.EDGE_BAND == pytest.approx(0.254)
    assert "FootLen" not in drawing.DIMENSION_CALLOUTS
    # The reamed bore holds the drilled-hole growth its set-screw thread
    # count assumes: largest bore = nominal + DRILL_GROWTH.
    upper, lower = drawing_spec.BORE_DIA_BAND
    assert lower == 0.0
    assert abs(spec.BORE_DIA + upper - 2.0 * spec.BORE_RADIUS_MAX) < 1e-9


def test_reference_lines_restate_the_geometry_their_equations_drive() -> None:
    """Each line's value, and the origin anchors that place it on the outline,
    evaluate from the part's globals to the as-built value: the deferred
    equations are neutral, and a global edit moves the line."""
    globals_mm = {
        "FootW": spec.FOOT_W,
        "FootZ1": FOOT_Z1,
        "EarT": spec.EAR_T,
        "TopH": spec.EAR_TOP_Y,
        "BoreH": spec.BORE_H,
    }

    def evaluate(expression: str) -> float:
        text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expression)
        return float(eval(text, {"__builtins__": {}}))  # noqa: S307 - literal arithmetic

    expected = {
        "BoreLateral": spec.FOOT_W / 2.0,
        "HoleLateral": spec.FOOT_W / 2.0,
        # The tap sits at z = 0, the bore axis plane; the station runs from
        # the ear's inboard face, the face every plan length starts on.
        "SetScrewLocation": 0.0 - spec.FOOT_Z0,
        # The seat up the tap's axis to the arch apex: the overall height.
        "OverallHeight": spec.EAR_TOP_Y,
    }
    assert (
        tuple(row[0] for row in part.REFERENCE_LINES) == drawing_spec.REFERENCE_SKETCHES
    )
    for (
        sketch,
        plane,
        name,
        start,
        end,
        orientation,
        value,
        drives,
    ) in part.REFERENCE_LINES:
        assert value == pytest.approx(expected[name]), sketch
        axis = 1 if orientation == "vertical" else 0
        assert abs(end[axis] - start[axis]) == pytest.approx(value)
        assert end[1 - axis] == start[1 - axis]
        anchors = [abs(c) for c in start if abs(c) > 1e-9]
        assert [evaluate(d) for d in drives] == pytest.approx([value, *anchors]), sketch
        assert plane == ("Front" if name in {"BoreLateral", "OverallHeight"} else "Top")
    starts = {row[2]: row[3] for row in part.REFERENCE_LINES}
    # Laterals start on the west side face, the tap station on the inboard
    # face (Top-plane sketch y is model -Z).
    assert starts["BoreLateral"][0] == starts["HoleLateral"][0] == -spec.FOOT_W / 2.0
    assert -starts["SetScrewLocation"][1] == spec.FOOT_Z0
    # The overall height starts on the seat.
    assert starts["OverallHeight"] == (0.0, 0.0)
    # The hold-down station is the hole's z off that same face.
    assert abs(HOLE_STATION - (HOLE_Z - spec.FOOT_Z0)) < 1e-9
    assert abs(FOOT_LEN - (FOOT_Z1 - spec.FOOT_Z0)) < 1e-9


def test_bore_callout_names_the_mating_pivot_shaft() -> None:
    number = _config.parts("ch-pivot-shaft")["number"]
    assert number == "MHA-CH-05"
    bore = drawing.DIMENSION_CALLOUTS["ShaftBoreDia"]
    assert bore.startswith("REAM THRU\n")
    assert bore.endswith(f"PIVOT SHAFT {number}")
    assert drawing.DIMENSION_CALLOUTS["HoleDia"] == "DRILL THRU"
    assert set(drawing.DIMENSION_CALLOUTS) <= set(drawing.FRONT_KEEP) | set(
        drawing.TOP_KEEP
    ) | set(drawing.RIGHT_KEEP_NAMES)


def test_every_banded_length_says_what_its_band_holds() -> None:
    """A band tighter than the title block names its reason, and its mate's
    part number, at the dimension, one reason per dimension (#1371 review:
    the set-screw note belongs to the tap's station, not the ear thickness,
    and names the shaft)."""
    banded = {name for _feature, name in model_toleranced_dimensions(part)}
    assert banded <= set(drawing.DIMENSION_CALLOUTS)
    washer = _config.parts("ch-vn-rocker-thrust-washer")["number"]
    assert washer == "MHA-CH-VN-56"
    assert drawing.DIMENSION_CALLOUTS["EarThick"] == f"THRUST FACES ON {washer}"
    shaft = _config.parts("ch-pivot-shaft")["number"]
    assert drawing.DIMENSION_CALLOUTS["SetScrewLocation"] == (
        f"SET SCREW ON FLAT OF\nPIVOT SHAFT {shaft}"
    )
    assert sum("SET SCREW" in text for text in drawing.DIMENSION_CALLOUTS.values()) == 1


# The native definitions of a through-next 4-40 Hole Wizard tap, as the
# fleet's TAP-prefixed callouts carry them (part 5 the thread, part 7 the
# tap drill).
_NATIVE_TAP = {
    5: "TAP <hw-threaddesc> - <hw-threadclass> <hw-thru>",
    6: "",
    7: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>",
    8: "",
}


def test_tap_callout_says_to_bore_and_states_no_shortfall() -> None:
    updated = drawing.set_screw_callout_definitions(dict(_NATIVE_TAP))
    assert updated[7] == "<MOD-DIAM><hw-thrutapdrldia> TO BORE"
    assert updated[5] == "TAP <hw-threaddesc> TO BORE"
    joined = "\n".join(updated.values())
    # Every Hole Wizard size variable survives; the class and THRU are gone.
    assert "<hw-threaddesc>" in joined and "<hw-thrutapdrldia>" in joined
    assert "<hw-threadclass>" not in joined and "<hw-thru>" not in joined
    # The lifted arch gives the tap rule 18's 1.5D, so nothing is stated.
    assert "ENGAGEMENT" not in joined
    assert spec.SET_SCREW_ENGAGEMENT_D >= spec.SET_SCREW_MIN_ENGAGEMENT_D == 1.5


def test_apex_set_screw_meets_rule_18_so_nothing_is_declared() -> None:
    """The owner's 2026-10-15 shortfall ruling (#1371) covered the R8 arch's
    1.08D; the lifted arch holds 1.5D, so the sheet states no shortfall and
    the part declares no exception for one."""
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    assert load_exceptions(CAD_ROOT / "config", "ch_pivot_bracket", "part") == ()
    assert not hasattr(drawing, "SET_SCREW_QUALIFIER")
    assert spec.SET_SCREW_FULL_THREAD_MIN == pytest.approx(
        sum(spec.SET_SCREW_WALL_TERMS.values())
    )
    ratio = spec.SET_SCREW_FULL_THREAD_MIN / spec.SET_SCREW_MAJOR_DIA
    assert spec.SET_SCREW_ENGAGEMENT_PRINTED == math.floor(ratio * 100.0) / 100.0
    assert spec.SET_SCREW_ENGAGEMENT_PRINTED >= 1.5


def test_tap_callout_rewrite_refuses_an_unexpected_native_format() -> None:
    blind = {**_NATIVE_TAP, 5: "TAP <hw-threaddesc> <hw-threadclass> <hw-depth>"}
    with pytest.raises(RuntimeError, match="two native extents"):
        drawing.set_screw_callout_definitions(blind)
    no_class = {**_NATIVE_TAP, 5: "TAP <hw-threaddesc> <hw-thru>"}
    with pytest.raises(RuntimeError, match="not in one callout part"):
        drawing.set_screw_callout_definitions(no_class)


def test_foot_seat_is_the_one_finish_controlled_face() -> None:
    (control,) = drawing_spec.SURFACE_FINISHES
    assert control.key == "foot_seat"
    assert control.roughness_um == 3.2
    assert control.face.normal == (0, -1, 0)
    assert control.face.offset_mm == 0.0


def test_projected_views_stay_aligned_and_ordered() -> None:
    """One scale for every view; the right view stands level with the
    elevation, the plan over it (#1371 review: third-angle alignment)."""
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing._VIEW_SCALE == (2, 1)
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    for model_y in (0.0, spec.FOOT_H, spec.EAR_TOP_Y):
        assert drawing._right_y(model_y) == pytest.approx(drawing._front_y(model_y))
    seat = drawing._front_y(0.0)
    apex = drawing._front_y(spec.EAR_TOP_Y)
    assert abs((seat + apex) / 2.0 - drawing.FRONT_CENTER[1]) < 1e-12
    plan_top = drawing._top_y(spec.FOOT_Z0)
    plan_bottom = drawing._top_y(FOOT_Z1)
    assert abs((plan_top + plan_bottom) / 2.0 - drawing.TOP_CENTER[1]) < 1e-12
    # Room for the two lateral lanes between the elevation and the plan.
    lanes = (drawing.TOP_KEEP["HoleLateral"][1], drawing.TOP_KEEP["FootW"][1])
    assert plan_bottom > lanes[0] > lanes[1] > apex + 0.010
    source = _drawing_source()
    assert source.count("scale=_VIEW_SCALE") == 4
    assert "add_note" not in source


def _planned_corner_text() -> tuple[float, float]:
    """The R MAX text in the planned right-view frame (*Right: +Z left)."""
    dz, dy = drawing.CORNER_TEXT_OFFSET
    return (
        drawing._right_x(spec.EAR_T / 2.0) - dz,
        drawing._right_y(spec.FOOT_H) + dy,
    )


def test_every_annotation_anchor_prints_inside_the_sheet() -> None:
    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["ch_pivot_bracket"].layout]
    anchors = {
        **drawing.FRONT_KEEP,
        **drawing.TOP_KEEP,
        "front view": drawing.FRONT_CENTER,
        "plan view": drawing.TOP_CENTER,
        "isometric view": drawing.ISO_CENTER,
        "set-screw callout": drawing.SET_SCREW_CALLOUT_XY,
        "right view": drawing.RIGHT_CENTER,
        "corner radius (planned frame)": _planned_corner_text(),
        "bore axis to apex reference": drawing.APEX_REFERENCE_TEXT_XY,
    }
    for label, (x, y) in anchors.items():
        assert _FRAME_M < x < template.width_m - _FRAME_M, label
        assert _FRAME_M < y < template.height_m - _FRAME_M, label
        assert not (
            x > template.title_block_left_m and y < template.title_block_top_m
        ), f"{label} is inside the title block"


def test_apex_tap_callout_fits_above_the_plan_between_the_lanes() -> None:
    from _drawing_annotation_extent import CLEAR_GAP_M
    from _layout_geometry import estimate_text_box

    # The native callout font as MHA-DT-02 printed it (cap 3.5 mm,
    # 109.7 mm per 42 glyphs, lines 16.8 pt apart).
    drill_in = blind_cut_dia_mm(spec.SET_SCREW_HOLE_SPEC) / 25.4
    drill = f"Ø.{round(drill_in * 1000):03d} {drawing.SET_SCREW_EXTENT}"
    thread = f"{drawing.SET_SCREW_PROCESS} 4-40 UNC {drawing.SET_SCREW_EXTENT}"
    box = estimate_text_box(
        f"{drill}\n{thread}",
        anchor=drawing.SET_SCREW_CALLOUT_XY,
        height=0.0035,
        reference=2,  # swCENTER
        advance_ratio=109.7 / (42 * 3.5),
        line_spacing=16.8 * 25.4 / 72.0 / 3.5,
    )
    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["ch_pivot_bracket"].layout]
    assert box.xmin >= _FRAME_M + CLEAR_GAP_M
    assert box.ymax <= template.height_m - _FRAME_M - CLEAR_GAP_M
    # Wholly above the plan's top edge and every extension line drawn off it.
    assert box.ymin >= drawing._top_y(spec.FOOT_Z0) + CLEAR_GAP_M
    # Its leader drops from the block's east end to the tap's east rim: east
    # of the plan centre (where the hole station's witness ends) and west of
    # the east edge (where the right lanes' witnesses start).
    assert drawing.TOP_CENTER[0] < box.xmax < drawing._EAST_X
    # Clear of the tap station's text above its span.
    set_screw_text_x = drawing.TOP_KEEP["SetScrewLocation"][0]
    assert box.xmax + 0.015 < set_screw_text_x


def _hanging_block(text: str, column_xy: tuple[float, float]) -> tuple[float, ...]:
    """A banded station's block as SolidWorks prints text placed outside its
    witnesses: the shelf starts on the dimension's column and the block runs
    east from it, centred on the placed height (5bca52e PDF: the 4.00 block
    x 161.0..216.1 off its 0.161 column)."""
    from _layout_geometry import estimate_text_box

    box = estimate_text_box(
        text,
        anchor=(0.0, 0.0),
        height=0.0035,
        reference=2,  # swCENTER
        advance_ratio=109.7 / (42 * 3.5),
        line_spacing=16.8 * 25.4 / 72.0 / 3.5,
    )
    x, y = column_xy
    return (x, y + box.ymin, x + box.width, y + box.ymax)


def test_banded_plan_stations_each_print_at_their_own_arrows() -> None:
    """5bca52e machinist review FIX: the 4.00 block stood over the 8.00
    column's top arrow and the 8.00 text sat inside the 4.00 span. The tap
    station's text hangs above its span, the ear thickness's below its span,
    each off its own column, and no other column stands under either."""
    from _drawing_annotation_extent import CLEAR_GAP_M

    plan_top = drawing._top_y(spec.FOOT_Z0)
    ear_face = drawing._top_y(spec.FOOT_Z0 + spec.EAR_T)
    plan_bottom = drawing._top_y(FOOT_Z1)
    tap_column = drawing.TOP_KEEP["SetScrewLocation"]
    ear_column = drawing.TOP_KEEP["EarThick"]
    foot_column = drawing.TOP_KEEP["FootLen"]
    tap = _hanging_block(
        f".160 ±.004\n{drawing.DIMENSION_CALLOUTS['SetScrewLocation']}", tap_column
    )
    ear = _hanging_block(
        f".320 ±.004\n{drawing.DIMENSION_CALLOUTS['EarThick']}", ear_column
    )
    # Nested shortest first, each column clear of the plan and the one inside.
    assert drawing._EAST_X + 0.008 <= tap_column[0] < ear_column[0] < foot_column[0]
    # The tap station's block: wholly above the plan's top edge.
    assert tap[1] > plan_top + CLEAR_GAP_M
    # The ear thickness's column, and the outside arrow it raises over the
    # top edge, stand clear east of the tap station's block.
    assert ear_column[0] > tap[2] + 0.010
    # Its block: under the ear's outboard-face line (its own lower witness),
    # over the foot length's lower extension line, east of the hold-down
    # hole's DRILL THRU block (~26 mm centred on its anchor), west of the
    # foot length's column.
    assert ear[3] < ear_face - CLEAR_GAP_M
    assert ear[1] > plan_bottom + CLEAR_GAP_M
    assert ear[0] > drawing.TOP_KEEP["HoleDia"][0] + 0.013 + 0.020
    assert ear[2] + 0.005 < foot_column[0]
    # The foot length's text sits in its span's upper half, above the ear
    # thickness's block, and left of the isometric.
    assert ear[3] + CLEAR_GAP_M < foot_column[1] - 0.003 < plan_top
    assert foot_column[0] + 0.008 < drawing.ISO_CENTER[0] - 0.025


def test_tap_note_solidworks_adds_is_removed() -> None:
    source = _drawing_source()
    assert 'redundant_note_substrings=("Tapped Hole",)' in source
    assert "expected_redundant_notes=1" in source


def test_registry_row_carries_the_title_block_material_specification() -> None:
    config = _config.parts("ch-pivot-bracket")
    assert config["number"] == "MHA-CH-08"
    assert config["material_specification"]
    assert int(config["quantity"]) == 2


def test_corner_radius_is_the_largest_the_screw_head_clears() -> None:
    """Rule 16: the foot-to-ear inside corner carries the largest radius the
    hold-down screw's head clears at the worst case, at one place, modelled
    at that limit and printed as a single MAX limit."""
    assert drawing_spec.CORNER_R_PLACES == 2
    assert drawing_spec.CORNER_R_MAX == pytest.approx(0.508)  # R.02
    assert drawing_spec.CORNER_R_MAX <= HEAD_TO_EAR_FACE_MIN
    step = 25.4 * 10.0**-drawing_spec.CORNER_R_PLACES
    assert drawing_spec.CORNER_R_MAX + step > HEAD_TO_EAR_FACE_MIN
    assert drawing_spec.CORNER_R_BAND == (0.0, -drawing_spec.CORNER_R_MAX)
    assert drawing_spec.CORNER_R_TOL_TYPE == 6  # swTolMAX
    assert drawing_spec.DRAWING_DIMENSIONS["CornerFillet"] == {"CornerRadius"}
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        "add_fillet(\n            CORNER_R_MAX, [[0.0, FOOT_H, EAR_T / 2.0]], propagate=False"
        in source
    )
    assert 'name_dimensions(adapter, "CornerFillet", ["CornerRadius"])' in source
    assert "drive_jobs.append((corner_dim[0], '\"CornerR\"'))" in source
    assert source.index("apply_drawing_precision(adapter, DRAWING_PRECISION)") < (
        source.index("_corner_radius_max_limit(adapter)\n")
    )
    # The spandrel the fillet adds, along the ear's width, is in the target.
    assert part.V_CORNER == pytest.approx((1.0 - math.pi / 4.0) * 0.508**2 * spec.EAR_W)
    assert part.V_TOTAL == pytest.approx(
        part.V_FOOT
        + part.V_BLOCK
        + part.V_ARCH
        - part.V_BORE
        - part.V_TAP
        - part.V_HOLE
        + part.V_CORNER
    )


def test_corner_radius_names_the_screw_head_it_clears() -> None:
    """Rule 4: the R MAX, tighter than the title block's inside corners,
    names the mate it serves (machinist review FIX: a bare "R0.3 max." with no
    reason), and its callout block stands in the corner's open air: above the
    foot top, left of the ear, right of the bore callout."""
    from _drawing_annotation_extent import CLEAR_GAP_M
    from _layout_geometry import estimate_text_box

    screw = _config.parts("ch-vn-bracket-hold-down-screw")["number"]
    assert screw == "MHA-CH-VN-57"
    callout = drawing.DIMENSION_CALLOUTS["CornerRadius"]
    assert callout == f"CLEARS HEAD OF\nHOLD-DOWN SCREW\n{screw}"
    # The native dimension font as the bore callout prints (cap 3.5 mm).
    box = estimate_text_box(
        f"R.{round(drawing_spec.CORNER_R_MAX / 25.4 * 100):02d} MAX\n{callout}",
        anchor=_planned_corner_text(),
        height=0.0035,
        reference=5,  # swUPPER_CENTER: the value line on the anchor
        advance_ratio=109.7 / (42 * 3.5),
        line_spacing=16.8 * 25.4 / 72.0 / 3.5,
    )
    assert box.ymin > drawing._right_y(spec.FOOT_H) + CLEAR_GAP_M
    assert box.xmax < drawing._right_x(spec.EAR_T / 2.0) - CLEAR_GAP_M
    bore_text_right = drawing.FRONT_KEEP["ShaftBoreDia"][0] + 0.029
    assert box.xmin > bore_text_right + CLEAR_GAP_M


def test_right_view_shows_the_corner_radius_clear_of_its_neighbours() -> None:
    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["ch_pivot_bracket"].layout]
    assert drawing.RIGHT_KEEP_NAMES == ("CornerRadius",)
    left = drawing._right_x(FOOT_Z1)
    right = drawing._right_x(spec.FOOT_Z0)
    bottom = drawing._right_y(0.0)
    top = drawing._right_y(spec.EAR_TOP_Y)
    assert abs((left + right) / 2.0 - drawing.RIGHT_CENTER[0]) < 1e-12
    assert abs((bottom + top) / 2.0 - drawing.RIGHT_CENTER[1]) < 1e-12
    # Over the title block, under the foot length's extension line, left of
    # the isometric (whose outline starts ~0.025 left of its centre at 2:1),
    # right of the bore callout.
    assert bottom - 0.010 > template.title_block_top_m
    assert top + 0.010 < drawing._top_y(FOOT_Z1)
    assert right + 0.015 < drawing.ISO_CENTER[0] - 0.025
    bore_text_right = drawing.FRONT_KEEP["ShaftBoreDia"][0] + 0.029
    text_x, text_y = _planned_corner_text()
    assert bore_text_right + 0.008 < text_x - 0.011
    # The R MAX text stands over the open corner, above the foot top.
    assert text_y > drawing._right_y(spec.FOOT_H) + 0.015
    assert left - 0.011 < text_x < drawing._right_x(spec.EAR_T / 2.0)
    source = _drawing_source()
    assert source.count("for view in (front, top, iso, right):") == 2
    assert source.index("set_dimension_callouts(adapter, imported_annotations") < (
        source.index("_dress_corner_radius(adapter, right_annotations)")
    )


def test_bore_callout_clears_the_elevation() -> None:
    """The REAM block's widest line (its mate's part number, ~58 mm centred on
    the text) starts clear of the elevation's right edge."""
    x, _y = drawing.FRONT_KEEP["ShaftBoreDia"]
    assert x - 0.029 > drawing._EAST_X + 0.005


def test_drill_callout_hides_its_dimension_leader_lines() -> None:
    assert drawing._LEADER_LINE_NONE == 3
    call = (
        "_hide_diameter_leader_lines(\n"
        '        adapter, top_annotations, dimension="HoleDia", label="hold-down hole"'
    )
    assert call in _drawing_source()
