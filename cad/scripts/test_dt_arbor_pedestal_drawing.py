"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import dt_arbor_pedestal_spec
import build_dt_arbor_pedestal as part
import draw_dt_arbor_pedestal as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _hole_spec import blind_cut_dia_mm


def _drawing_source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-arbor-pedestal_drawing.png")
    assert DRAWINGS_BY_NAME["dt_arbor_pedestal"].script == Path(drawing.__file__).resolve()


def test_pedestal_uses_the_common_cone_axis_height() -> None:
    from cone_line import Y_BASE_TOP, Y_DRIVE
    from _cone_axis_constants import CONE_AXIS_HEIGHT_MM, PLATFORM_THICKNESS_MM

    height = CONE_AXIS_HEIGHT_MM + PLATFORM_THICKNESS_MM
    assert part.BORE_HEIGHT == drawing.BORE_HEIGHT == dt_arbor_pedestal_spec.BORE_HEIGHT == height
    assert abs(Y_DRIVE - Y_BASE_TOP - height) < 1e-9


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is dt_arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    # Every marked dimension is placed by exactly one view, and no view keeps a
    # name the part never marks: an unplaced import is deleted silently.
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    assert marked == {
        "Width",
        "Depth",
        "FootHt",
        "BoreDia",
        "BoreHeight",
        "DomeRadius",
        "StrapDepth",
        "HoldDownLocation",
        "HoleLateral",
        "BoreLateral",
        "SetScrewLocation",
    }
    # The strap band is owned by its reference sketch, so the strap profile
    # stays unmarked.
    assert "StrapProfile" not in dt_arbor_pedestal_spec.DRAWING_DIMENSIONS


def test_the_part_owns_every_printed_decimal_place() -> None:
    """drawing-simplicity-policy.md `How the repository implements the guidelines`: places are the tolerance, so the .SLDPRT carries them."""
    by_name = dt_arbor_pedestal_spec.DRAWING_PRECISION_BY_NAME
    # Inch sheet: every size and location .XX; the V-drilled bore prints the
    # drill's size at three places (fit audit F01).
    assert by_name == {
        name: (3 if name == "BoreDia" else 2)
        for name in set().union(*dt_arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    }
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_only_the_drilled_bore_asks_for_a_third_decimal() -> None:
    """The bore prints the V drill's .377 (fit audit F01: no band, the
    DRILLED HOLES row); nothing else on this post needs a third place."""
    places = {
        **dt_arbor_pedestal_spec.DRAWING_PRECISION_BY_NAME,
        **dt_arbor_pedestal_spec.DRAWING_REFERENCE_PRECISION,
    }
    assert {name for name, value in places.items() if value > 2} == {"BoreDia"}
    assert max(places.values()) == 3
    assert model_toleranced_dimensions(part) == {}


def test_crown_radius_is_the_dome_radius_the_part_drives() -> None:
    """#810 Codex l4afp follow-up (Main): the R11.0 crown is a controlling
    dimension, so it is the dome boss's own model dimension, never a radius the
    sheet measures off the arc.

    v37 printed R22.0: the dome carried a DIAMETER dimension driven by
    ``"TopRadius" * 2`` and the sheet flipped it radial, so the drawing's
    rebuild fed 22 into a radius and doubled the crown (the part render stayed
    R11). The part now dimensions the crown as the radius it is, and each dome
    equation evaluates to the as-built value it drives."""
    spec = dt_arbor_pedestal_spec
    assert spec.DRAWING_DIMENSIONS["DomeProfile"] == {"DomeRadius"}
    assert spec.DRAWING_PRECISION["DomeProfile"] == {"DomeRadius": 2}
    assert "DomeRadius" in drawing.FRONT_KEEP
    globals_mm = {"BoreHeight": spec.BORE_HEIGHT, "TopRadius": spec.TOP_RADIUS}
    as_built = {"DomeCy": spec.BORE_HEIGHT, "DomeRadius": spec.TOP_RADIUS}
    assert set(part.DOME_DRIVES) == set(as_built)
    for name, expression in part.DOME_DRIVES.items():
        text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expression)
        assert float(eval(text, {"__builtins__": {}})) == as_built[name], name  # noqa: S307
    # 810-l4afp-1 eye pass: the radius line ran through the bore to the
    # centre; the arrow sits outside the arc so the leader stops on it.
    assert drawing._ARROWS_OUTSIDE == 1


# Every Diametric write a drawing script may make, each onto a dimension that
# is ALREADY a diameter, so the write changes nothing the model solves. Setting
# Diametric on a MODEL dimension keeps its value and re-reads it as the other
# kind: False on a diameter doubles the feature (v37 MHA-DT-02 printed an R22
# crown on the R11 part), True on a radius halves it. A new writer must show
# its dimension is sheet-made or already the kind it sets, and join this list.
_DIAMETRIC_WRITERS = {
    # The OD reference is sheet-made; the cross-hole callout is the
    # CrossHoleProfile define_circle DIAMETER.
    "draw_fr_tube_frame.py": 2,
    # set_near_side_diameter styles imported define_circle DIAMETERS.
    "_drawing_leaders.py": 1,
}


def test_no_sheet_re_solves_a_model_dimension_through_diametric() -> None:
    """A radial print must come from a radial model dimension (define_circle
    size_dimension="radius"), never from flipping a diameter on the sheet."""
    writes = re.compile(r"""Diametric["']?\s*(?:=|,)\s*(True|False)\b""")
    scripts = Path(drawing.__file__).parent
    found: dict[str, list[str]] = {}
    for path in sorted(scripts.glob("draw_*.py")) + sorted(scripts.glob("_drawing_*.py")):
        values = writes.findall(path.read_text(encoding="utf-8"))
        if values:
            found[path.name] = values
    assert all(value == "True" for values in found.values() for value in values), found
    assert {name: len(values) for name, values in found.items()} == _DIAMETRIC_WRITERS


def test_manufacturing_locations_are_model_dimensions() -> None:
    """#810 Codex l4afp, drawing-simplicity-policy.md `How the repository implements the guidelines`: the strap band, the hold-down station
    and both lateral locations carry the .X band, so the part owns them --
    hidden reference sketches whose one driving dimension IS the value --
    and the sheet imports them verbatim instead of deriving them from view
    edges and rewriting their precision."""
    spec = dt_arbor_pedestal_spec
    owned = {
        "StrapDepthReference": "StrapDepth",
        "HoldDownReference": "HoldDownLocation",
        "HoleLateralReference": "HoleLateral",
        "BoreLateralReference": "BoreLateral",
        "SetScrewReference": "SetScrewLocation",
    }
    assert spec.REFERENCE_SKETCHES == tuple(owned)
    for sketch, name in owned.items():
        assert spec.DRAWING_DIMENSIONS[sketch] == {name}
        assert spec.DRAWING_PRECISION[sketch] == {name: 2}


def test_reference_lines_restate_the_geometry_their_equations_drive() -> None:
    """Each reference line's value, and the origin anchors that place it on
    the outline, evaluate from the part's globals to the as-built value: the
    deferred equations are neutral, and a global edit moves the line."""
    spec = dt_arbor_pedestal_spec
    globals_mm = {
        "FootWidth": spec.FOOT_WIDTH,
        "FootDepth": spec.FOOT_DEPTH,
        "StrapInnerZ": spec.STRAP_INNER_Z,
        "StrapThickness": spec.STRAP_T,
        "ScrewZ": -spec.SCREW_Z,
        "SetScrewZ": spec.SET_SCREW_Z,
    }

    def evaluate(expression: str) -> float:
        text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expression)
        return float(eval(text, {"__builtins__": {}}))  # noqa: S307 - literal arithmetic

    expected = {
        "StrapDepth": spec.STRAP_T,
        "HoldDownLocation": spec.STRAP_INNER_Z - spec.SCREW_Z,
        "HoleLateral": spec.FOOT_WIDTH / 2.0,
        "BoreLateral": spec.FOOT_WIDTH / 2.0,
        "SetScrewLocation": spec.STRAP_INNER_Z - spec.SET_SCREW_Z,
    }
    for sketch, plane, name, start, end, orientation, value, drives in part.REFERENCE_LINES:
        assert value == expected[name]
        axis = 1 if orientation == "vertical" else 0
        assert abs(end[axis] - start[axis]) == value
        assert end[1 - axis] == start[1 - axis]
        anchors = [abs(c) for c in start if abs(c) > 1e-9]
        assert [evaluate(d) for d in drives] == [value, *anchors], sketch
        # drawing-guidelines.md rule 10 (dimension from a real feature): every line starts on a feature -- the west side face for a
        # lateral location, the far face or strap root for a plan depth.
        if name in ("HoleLateral", "BoreLateral", "HoldDownLocation"):
            assert start[0] == -spec.FOOT_WIDTH / 2.0
        assert plane == ("Front" if name == "BoreLateral" else "Top")


def test_arbor_bore_is_drilled_v_and_names_its_arbor_and_clamp() -> None:
    import _config

    # Fit audit F01 (owner ruling 2026-11-24): V DRILL (.377) THRU; the arbor
    # enters by hand and the apex set screw clamps it (rule 4 v2 form 1).
    assert dt_arbor_pedestal_spec.BORE_DIA == 9.5758
    assert dt_arbor_pedestal_spec.BORE_DIA_BAND == (0.1016, 0.0)
    arbor = str(_config.parts("dt-cylinder-gear-shaft")["number"])
    screw = str(_config.parts("sh-vn-arbor-set-screw")["number"])
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == (
        f"V DRILL THRU\nARBOR {arbor} ENTERS BY HAND,\nCLAMPED BY {screw}"
    )
    # The arbor (3/8 ground, .3742-.3750) enters every drilled bore
    # (.377-.381) by hand: .0020 least clearance, .0068 at most.
    shaft_limits = (9.50468, 9.525)
    bore_limits = (9.5758, 9.6774)
    assert round(bore_limits[0] - shaft_limits[1], 5) == 0.0508
    assert round(bore_limits[1] - shaft_limits[0], 5) == 0.17272


def test_screw_hole_contract_is_part_owned() -> None:
    spec = dt_arbor_pedestal_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is spec
    assert spec.kind == "clearance"
    assert spec.size == "#8"
    assert spec.fit == "close"
    assert dt_arbor_pedestal_spec.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)
    assert part.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)


def test_foot_grew_outboard_only_around_an_unmoved_strap() -> None:
    """U34c: the strap inner face and part origin stay put; only the ledge
    grew outboard.  #290: every station sits on the .01-in grid."""
    spec = dt_arbor_pedestal_spec
    assert spec.STRAP_INNER_Z == 8.0
    assert spec.STRAP_ROOT_Z == pytest.approx(8.0 - 0.40 * 25.4)
    assert spec.FOOT_DEPTH == pytest.approx(1.10 * 25.4)
    assert spec.LEDGE_DEPTH == pytest.approx(0.70 * 25.4)
    assert spec.FOOT_NEAR_Z == pytest.approx(8.0 - 1.10 * 25.4)
    assert spec.SCREW_Z == pytest.approx(8.0 - 0.75 * 25.4)


def test_hold_down_hole_webs_hold_u27_at_the_printed_worst_case() -> None:
    """The plan locates the hole off the strap inner face at .XX, and the
    foot depth and strap depth print at .XX too. Every web the hole leaves
    must keep the .080 target with those bands stacked against it, plus the
    title block's +.004 drilled-hole oversize."""
    from _inch_wall_limits import WALL_TARGET_MM
    from _printed_tolerance import drilled_oversize_mm, printed_band_mm

    spec = dt_arbor_pedestal_spec
    band = printed_band_mm(2, unit="in")
    radius = (spec.SCREW_HOLE_DIA + drilled_oversize_mm(unit="in")) / 2.0
    to_strap_root = spec.STRAP_ROOT_Z - spec.SCREW_Z - radius
    to_ledge_end = spec.SCREW_Z - spec.FOOT_NEAR_Z - radius
    to_side = spec.FOOT_WIDTH / 2.0 - radius
    assert to_strap_root - 2 * band >= WALL_TARGET_MM
    assert to_ledge_end - 2 * band >= WALL_TARGET_MM
    assert to_side - band - band / 2.0 >= WALL_TARGET_MM
    # The MHA-DT-VN-62 head (Ø.270) floats with the shank in the hole; it must
    # still clear the strap root it is tightened beside.
    head_r = 6.858 / 2.0
    float_r = (spec.SCREW_HOLE_DIA - 4.1656) / 2.0
    assert spec.STRAP_ROOT_Z - spec.SCREW_Z - head_r - 2 * band - float_r >= WALL_TARGET_MM
    # Dimensioned from the strap inner face, the printed value is the strap
    # plus half the ledge -- one datum for every Z on the plan.
    assert spec.STRAP_INNER_Z - spec.SCREW_Z == pytest.approx(0.75 * 25.4)


def test_feature_callouts_do_not_repeat_dimension_values() -> None:
    """Feature callouts qualify the model dimensions rather than restating them."""
    source = _drawing_source()
    # The only free text left is digit-free and tied to the dimension it
    # qualifies (a reaming instruction, a concentricity/tangency statement),
    # bar the part numbers that name a mate and the clamp (rule 7).
    assert not re.search(r'SetText\(\d+,\s*"[^"]*\d', source)
    for text in drawing.DIMENSION_CALLOUTS.values():
        text = text.replace(drawing.ARBOR_NUMBER, "")
        text = text.replace(drawing.SET_SCREW_NUMBER, "")
        assert not re.search(r"\d", text), text


def test_pedestal_has_no_gdt_or_basic_dimensions() -> None:
    assert not hasattr(dt_arbor_pedestal_spec, "GEOMETRIC_TOLERANCES_MM")


def test_bore_and_mating_foot_seat_carry_surface_finish_controls() -> None:
    by_key = {c.key: c for c in dt_arbor_pedestal_spec.SURFACE_FINISHES}
    assert set(by_key) == {"arbor_bore", "foot_seat"}
    # A drilled bore (fit audit F01), static and clamped: Ra 3.2 (125 µin).
    assert by_key["arbor_bore"].roughness_um == 3.2
    assert by_key["arbor_bore"].face.contains_y_mm == dt_arbor_pedestal_spec.BORE_HEIGHT
    # The seat is the only face that MUST be cut on a part the title block
    # otherwise leaves CAST/MACHINED; it is the y=0 plane facing -Y.
    assert by_key["foot_seat"].roughness_um == 3.2
    assert by_key["foot_seat"].face.normal == (0, -1, 0)
    assert by_key["foot_seat"].face.offset_mm == 0.0


def test_projected_views_stay_aligned_and_ordered() -> None:
    """Third angle: the plan sits above the elevation on the same centre, and
    the two view boxes do not overlap at the sheet's 2:1 scale."""
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    dome_top = drawing._front_y(
        dt_arbor_pedestal_spec.BORE_HEIGHT + dt_arbor_pedestal_spec.TOP_RADIUS
    )
    plan_bottom = drawing._top_y(dt_arbor_pedestal_spec.STRAP_INNER_Z)
    # Air for the crown callout between the elevation and the plan.
    assert plan_bottom - dome_top >= 0.012
    # The plan's near edge (the exposed hold-down ledge) projects to its top,
    # and the view is centred on its bounding box, not on model z 0.
    plan_top = drawing._top_y(dt_arbor_pedestal_spec.FOOT_NEAR_Z)
    assert plan_top > plan_bottom
    assert abs((plan_top + plan_bottom) / 2.0 - drawing.TOP_CENTER[1]) < 1e-12
    assert drawing._front_y(0.0) < drawing._front_y(dt_arbor_pedestal_spec.FOOT_HEIGHT)


def test_every_annotation_anchor_prints_inside_the_sheet() -> None:
    """A mistyped lane coordinate is a dimension off the sheet edge or buried
    in the title block -- neither survives a machinist review, and neither is
    visible until the farm renders the PDF."""
    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["dt_arbor_pedestal"].layout]
    margin = 0.0127
    anchors = {
        **drawing.FRONT_KEEP,
        **drawing.TOP_KEEP,
        "front view": drawing.FRONT_CENTER,
        "plan view": drawing.TOP_CENTER,
        "isometric view": drawing.ISO_CENTER,
        "bore lateral lane": drawing.BORE_LATERAL_XY,
        "hole lateral lane": drawing.HOLE_LATERAL_XY,
        "set-screw callout": drawing.SET_SCREW_CALLOUT_XY,
        "hold-down callout": drawing.HOLD_DOWN_CALLOUT_XY,
    }
    for label, (x, y) in anchors.items():
        assert margin < x < template.width_m - margin, label
        assert margin < y < template.height_m - margin, label
        assert not (
            x > template.title_block_left_m and y < template.title_block_top_m
        ), f"{label} is inside the title block"


# The native hole-callout font as v37 MHA-DT-02 printed it: the thread line
# "TAP TO BORE, AT CROWN APEX 4-40 UNC <depth> 0.00" (42 glyphs) ran
# 109.7 mm at the 3.5 mm cap height, and its two lines stood 16.8 pt apart.
_CALLOUT_CAP_M = 0.0035
_CALLOUT_ADVANCE = 109.7 / (42 * 3.5)
_CALLOUT_LINE_SPACING = 16.8 * 25.4 / 72.0 / 3.5


def _estimated_set_screw_callout():
    from _layout_geometry import estimate_text_box

    drill = (
        f"Ø{blind_cut_dia_mm(dt_arbor_pedestal_spec.SET_SCREW_HOLE_SPEC):.2f}"
        f" {drawing.SET_SCREW_EXTENT}"
    )
    thread = f"{drawing.SET_SCREW_PROCESS} 4-40 UNC {drawing.SET_SCREW_EXTENT}"
    return estimate_text_box(
        f"{drill}\n{thread}",
        anchor=drawing.SET_SCREW_CALLOUT_XY,
        height=_CALLOUT_CAP_M,
        reference=2,  # swCENTER: callout_xy is the text block's centre
        advance_ratio=_CALLOUT_ADVANCE,
        line_spacing=_CALLOUT_LINE_SPACING,
    )


def test_apex_tap_callout_prints_inside_the_zone_frame() -> None:
    """V37 blocker: the callout's CENTRE sat on the sheet, its text ran 22.6 mm
    past the left zone frame. The whole estimated block must fit, with the
    clear gap the sheet's read-back proof demands."""
    from _drawing_annotation_extent import CLEAR_GAP_M

    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["dt_arbor_pedestal"].layout]
    frame = 0.0127
    box = _estimated_set_screw_callout()
    assert box.xmin >= frame + CLEAR_GAP_M
    assert box.xmax <= template.width_m - frame - CLEAR_GAP_M
    # Left of the hole, so the leader rises right into the plan.
    assert box.xmax < drawing.TOP_CENTER[0]


def test_apex_tap_callout_clears_the_crown_the_plan_and_the_left_lanes() -> None:
    """V37 blocker: the callout sat on the (61.72) and the elevation. Its
    estimated block must clear every neighbour the sheet's read-back proof
    checks, WITHOUT place_callout_clear having to move it (a move only goes up
    or right, toward the plan)."""
    from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M, boxes_clear

    box = _estimated_set_screw_callout()
    block = (box.xmin, box.ymin, box.xmax, box.ymax)
    below = drawing.set_screw_callout_below()
    beside = drawing.set_screw_callout_beside()
    above = drawing.set_screw_callout_above()
    assert set(below) == {
        "crown apex and its overall-height extension line",
        "overall height dimension line",
    }
    assert set(above) == {"plan far face"}
    neighbours = {**below, **beside, **above}
    crowded = [name for name, other in neighbours.items() if not boxes_clear(block, other)]
    assert crowded == []
    # No upward move: the band's floor already clears the crown with settle.
    assert all(box.ymin >= other[3] + CLEAR_GAP_M + PLACE_SETTLE_M for other in below.values())
    # The leader may cross the plan's own far face to reach the hole, never
    # the extension lines drawn off it (place_callout_clear checks below and
    # beside only).
    assert "plan far face" not in {**below, **beside}


# The native definitions of a through-next 4-40 Hole Wizard tap, as the
# fleet's TAP-prefixed callouts carry them (part 5 the thread, part 7 the
# tap drill).
_NATIVE_TAP = {
    5: "TAP <hw-threaddesc> - <hw-threadclass> <hw-thru>",
    6: "",
    7: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>",
    8: "",
}


def test_tap_callout_gives_one_extent_to_the_bore() -> None:
    """ENFORCE r1: "Ø2.26 THRU / TAP TO BORE ... THRU" read as two extents."""
    updated = drawing.set_screw_callout_definitions(dict(_NATIVE_TAP))
    assert updated[7] == "<MOD-DIAM><hw-thrutapdrldia> TO BORE"
    assert updated[5] == "TAP <hw-threaddesc> TO BORE"
    joined = "\n".join(updated.values())
    assert "<hw-threaddesc>" in joined and "<hw-thrutapdrldia>" in joined
    assert "<hw-threadclass>" not in joined and "<hw-thru>" not in joined


def test_tap_callout_rewrite_refuses_an_unexpected_native_format() -> None:
    import pytest

    blind = {**_NATIVE_TAP, 5: "TAP <hw-threaddesc> <hw-threadclass> <hw-depth>"}
    with pytest.raises(RuntimeError, match="two native extents"):
        drawing.set_screw_callout_definitions(blind)
    no_class = {**_NATIVE_TAP, 5: "TAP <hw-threaddesc> <hw-thru>"}
    with pytest.raises(RuntimeError, match="not in one callout part"):
        drawing.set_screw_callout_definitions(no_class)


def test_hold_down_callout_reads_size_then_drill_then_extent() -> None:
    """Fan-out screen 20261107T081227004Z: "DRILL Ø .180 THRU ALL" put the
    process ahead of the size (rule 26: size, process, depth)."""
    import pytest

    native = {5: "<MOD-DIAM><hw-diam> <hw-thru>", 6: "", 7: "", 8: ""}
    updated = drawing.hold_down_callout_definitions(dict(native))
    assert updated == {5: "<MOD-DIAM><hw-diam> DRILL <hw-thru>", 6: "", 7: "", 8: ""}
    with pytest.raises(RuntimeError, match="one bare diameter"):
        drawing.hold_down_callout_definitions(updated)


def test_part_stamps_make_flexible_material_and_protective_finish() -> None:
    assert part.MATERIAL == "Plain Carbon Steel"
    import _config

    config = _config.parts("dt-arbor-pedestal")
    assert config["material"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["finish"] == (
        "BLACK JAPAN/ENAMEL; MASK BORE AND FOOT SEAT; OIL BARE MACHINED SURFACES"
    )
    assert config["process"] == "machined from solid stock or casting"
    # Two identical pedestals: the south support plus the north one rotated
    # 180 about Y (build_drive_train_assembly places both).
    assert int(config["quantity"]) == 2


def test_lateral_locations_start_on_a_feature_not_the_symmetry_axis() -> None:
    """drawing-guidelines.md rule 10 (dimension from a real feature): X is dimensioned from the foot's west side face in both
    views, and no callout falls back on the part centreline."""
    starts = {row[2]: row[3] for row in part.REFERENCE_LINES}
    assert starts["BoreLateral"][0] == -dt_arbor_pedestal_spec.FOOT_WIDTH / 2.0
    assert starts["HoleLateral"][0] == -dt_arbor_pedestal_spec.FOOT_WIDTH / 2.0
    # Both plan lanes sit above its near edge, the hole lateral inside the
    # foot width, so the apex tap callout's leader leaves the plan downward
    # across no dimension line; the hold-down callout sits left of the plan,
    # clear of the 19.0 lane, so its leader crosses neither.
    plan_top = drawing._top_y(dt_arbor_pedestal_spec.FOOT_NEAR_Z)
    assert plan_top < drawing.HOLE_LATERAL_XY[1] < drawing.TOP_KEEP["Width"][1]
    plan_west = (
        drawing.TOP_CENTER[0] - dt_arbor_pedestal_spec.FOOT_WIDTH * drawing._S / 2
    )
    assert drawing.HOLD_DOWN_CALLOUT_XY[0] + 0.025 < plan_west
    assert drawing.HOLD_DOWN_EDGE_XY[1] > drawing._top_y(dt_arbor_pedestal_spec.SCREW_Z)
    assert drawing.HOLD_DOWN_CALLOUT_XY[1] > drawing.HOLD_DOWN_EDGE_XY[1]
    # The bore lane sits below the seat.
    assert drawing.BORE_LATERAL_XY[1] < drawing._front_y(0.0)


def test_plan_holes_share_one_drawn_centreline_through_both_centres() -> None:
    """Rule 26: the .47 lateral runs to the hold-down hole, and the apex tap
    sits on the same line; one centreline runs past both rims."""
    spec = dt_arbor_pedestal_spec
    (x0, _, z_far), (x1, _, z_near) = drawing.PLAN_HOLE_CENTRELINE_MM
    assert x0 == x1 == 0.0
    tap_radius = blind_cut_dia_mm(spec.SET_SCREW_HOLE_SPEC) / 2.0
    assert z_far < spec.SCREW_Z - spec.SCREW_HOLE_DIA / 2.0
    assert z_near > spec.SET_SCREW_Z + tap_radius


def test_crown_callout_and_flank_angle_define_the_tapered_flanks() -> None:
    """Round-2 review: the flanks run from the foot top (the strap root is the
    full foot width) up to tangency with the crown.  Fan-out local repeat of
    e308920ca9: the coined "FOOT CORNERS" left the taper unprinted, so the
    flank's angle off the seat prints as a reference."""
    import math


    spec = dt_arbor_pedestal_spec
    assert drawing.CROWN_CALLOUT == "SIDES TANGENT"
    assert not re.search(r"\d", drawing.CROWN_CALLOUT)
    lean = math.degrees(
        math.atan(
            (spec.FOOT_WIDTH / 2.0 - spec.TAPER_TANGENT_X)
            / (spec.TAPER_TANGENT_Y - spec.FOOT_HEIGHT)
        )
    )
    assert 1.0 < lean < 2.0
    assert drawing.FLANK_ANGLE_DEG == pytest.approx(90.0 + lean)
    # The text stands east of the elevation, between the foot-height lane and
    # the bore axis.
    east_flank = drawing.FRONT_CENTER[0] + spec.FOOT_WIDTH * drawing._S / 2.0
    assert drawing.FLANK_ANGLE_XY[0] > east_flank
    assert drawing._front_y(spec.FOOT_HEIGHT) < drawing.FLANK_ANGLE_XY[1]
    assert drawing.FLANK_ANGLE_XY[1] < drawing._front_y(spec.BORE_HEIGHT)


def test_parallel_sides_are_allowed_as_an_option() -> None:
    """Owner ruling 2026-11-20 on #2372: "Allow parallel sides as an option."
    The option rides under the reference flank angle, in words only, and the
    parallel strap tangent to the crown stays inside the foot."""
    spec = dt_arbor_pedestal_spec
    assert drawing.FLANK_ANGLE_CALLOUT == "PARALLEL\nSIDES OK"
    assert not re.search(r"\d", drawing.FLANK_ANGLE_CALLOUT)
    assert spec.TOP_RADIUS < spec.FOOT_WIDTH / 2.0


def test_apex_set_screw_tap_keeps_1_5d_only_at_r11() -> None:
    """#743 Q3 (user: "set screw located at apex of straps"): a #4-40 tap
    through the crown onto the arbor. At the printed worst case (crown radius
    .XX low, bore at its maximum, both sags across the thread and a one-pitch
    entry lost) the photographed R10 crown would leave under 1.5D of full
    thread and fail drawing-guidelines.md rule 18; R.43 leaves 1.72D at the
    V-drilled bore's .381 analysis maximum (fit audit F01)."""
    spec = dt_arbor_pedestal_spec
    assert spec.TOP_RADIUS == pytest.approx(0.43 * 25.4)
    assert spec.SET_SCREW_THREAD == "#4-40"
    assert spec.SET_SCREW_HOLE_SPEC.kind == "tapped"
    # Through-next: the tap stops in the bore, never drills on into the strap.
    assert spec.SET_SCREW_HOLE_SPEC.end == "through_next"
    assert spec.set_screw_engagement_d(10.0) < 1.5 <= spec.SET_SCREW_ENGAGEMENT_D
    assert round(spec.SET_SCREW_ENGAGEMENT_D, 2) == 1.72
    assert round(spec.SET_SCREW_FULL_THREAD_MM, 2) == 4.89
    terms = spec.set_screw_wall_terms(spec.TOP_RADIUS)
    assert terms["crown radius at .XX minimum"] == pytest.approx(spec.TOP_RADIUS - 0.254)
    assert all(v < 0 for k, v in terms.items() if k != "crown radius at .XX minimum")


def test_apex_set_screw_sits_mid_strap_with_its_webs() -> None:
    """The tap stands at the strap's mid-depth; its station prints at two
    places so the outer web keeps the .080 target."""
    from _inch_wall_limits import WALL_TARGET_MM

    spec = dt_arbor_pedestal_spec
    assert spec.SET_SCREW_Z == (spec.STRAP_INNER_Z + spec.STRAP_ROOT_Z) / 2.0
    assert spec.DRAWING_PRECISION_BY_NAME["SetScrewLocation"] == 2
    assert spec.SET_SCREW_WEB_MM >= WALL_TARGET_MM
    assert round(spec.SET_SCREW_WEB_MM, 2) == 3.15
    assert not re.search(r"\d", drawing.SET_SCREW_PROCESS)
