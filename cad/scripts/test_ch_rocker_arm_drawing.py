"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import ast
import math
import re

from pathlib import Path
from types import SimpleNamespace

import pytest

import ch_rocker_arm_notes
import ch_rocker_arm_spec
import _rocker_interface as rocker_interface
import draw_ch_rocker_arm as drawing
import build_ch_rocker_arm as arm
import _drawing_detail_crop as detail_crop
from _gtol_frame import gtol_frame_signature, gtol_frame_xml
from _layout_geometry import AnnotationGeometry, Box, DrawableRegion, Segment, segment_box_distance, text_overlap
from _drawing_registry import DRAWINGS_BY_NAME
from _cone_axis_constants import MECHANISM_X_SHIFT
from _hole_spec import blind_cut_dia_mm


def _native(*interfaces, **members):
    """Declare a producer's interfaces; never infer ownership from its members."""
    if {"IAnnotation", "IDisplayDimension"} <= set(interfaces):
        raise AssertionError("annotation and display dimension require distinct objects")
    return SimpleNamespace(_native_interfaces=interfaces, **members)


def _bind_owner(native, interface, *_members):
    """NULL survives binding; unknown and wrong interfaces fail without COM."""
    if native is None:
        return None
    owners = getattr(native, "_native_interfaces", ())
    if interface not in owners:
        raise RuntimeError(f"native owner mismatch: {owners!r} cannot bind {interface}")
    query = getattr(native, "_native_query", None)
    return query(interface) if query is not None else native


def _front_xy(mx: float, my: float) -> tuple[float, float]:
    """Offline projection fixture, never production or native layout evidence."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    return (drawing.FRONT_CENTER[0] + mx * scale,
            drawing.FRONT_CENTER[1] + (my - drawing.TOP_END_Y / 2.0) * scale)


def _end_xy(mx: float, my: float) -> tuple[float, float]:
    scale = drawing.END_SCALE[0] / drawing.END_SCALE[1] / 1000.0
    cx = (drawing.BOT_END_X + drawing.ROD_TIP_X) / 2.0
    cy = (drawing._BOT_END_Y + drawing.TOP_END_Y) / 2.0
    return (drawing.END_CENTER[0] + (mx - cx) * scale,
            drawing.END_CENTER[1] + (my - cy) * scale)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["ch_rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is ch_rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*ch_rocker_arm_notes.DRAWING_DIMENSIONS.values())
    keeps = (drawing.FRONT_KEEP, drawing.HUB_KEEP, drawing.END_KEEP, drawing.RIGHT_KEEP)
    kept = set().union(*keeps)
    assert kept == marked
    assert sum(map(len, keeps)) == len(marked)
    assert not hasattr(drawing, "TOP_KEEP")


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        rocker_interface.ROD_HOLE_X,
        ch_rocker_arm_spec.TOP_END_Y,
    )
    assert ch_rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert ch_rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert ch_rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert ch_rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert arm.ROD_HOLE_SPEC is ch_rocker_arm_spec.ROD_HOLE_SPEC
    assert drawing._ROD_HOLE_DIA == blind_cut_dia_mm(ch_rocker_arm_spec.ROD_HOLE_SPEC)


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        rocker_interface.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(rocker_interface.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    assert ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert drawing.RIGHT_SCALE == (ch_rocker_arm_notes.RIGHT_VIEW_SCALE, 1)
    assert ch_rocker_arm_notes.RIGHT_VIEW_NOTE.endswith(
        f"SCALE {drawing.RIGHT_SCALE[0]}:{drawing.RIGHT_SCALE[1]}"
    )
    assert f"VIEW {ch_rocker_arm_notes.VIEW_ARROW_LETTER} " in ch_rocker_arm_notes.RIGHT_VIEW_NOTE
    # The caption sits under view F's silhouette, inside the sheet border.
    scale = drawing.RIGHT_SCALE[0] / drawing.RIGHT_SCALE[1]
    view_bottom = drawing.RIGHT_CENTER[1] - ch_rocker_arm_spec.TOP_END_Y * scale / 2000.0
    assert drawing.RIGHT_CAPTION_XY[1] < view_bottom - 0.02
    assert drawing.RIGHT_CAPTION_XY[0] > 0.0125


def test_view_arrow_names_the_removed_right_view_from_the_notes_letter() -> None:
    # The caption and the arrow share one letter, owned by the notes module.
    letter = ch_rocker_arm_notes.VIEW_ARROW_LETTER
    assert f"VIEW {letter} " in ch_rocker_arm_notes.RIGHT_VIEW_NOTE
    assert drawing.add_leader_note.__module__ == "_drawing_leader_notes"


def test_rod_drill_callout_prints_the_limits_it_exports() -> None:
    # The callout's printed size is the #47 drill's exact decimal, so its
    # DRILLED HOLES +.004/0 limits are the exported ones and admit the drill.
    nominal_in = blind_cut_dia_mm(ch_rocker_arm_spec.ROD_HOLE_SPEC) / 25.4
    places = drawing.ROD_CALLOUT_PRECISION["hw-diam"]
    assert places == drawing.ROD_HOLE.precision["dia"] == 4
    printed = round(nominal_in, places)
    assert printed == pytest.approx(nominal_in, abs=1e-5) and printed == 0.0785
    low, high = drawing.ROD_HOLE.fields["dia"][0]
    assert (round(low / 25.4, 4), round(high / 25.4, 4)) == (0.0785, 0.0825)


def test_native_gdt_and_finish_present() -> None:
    """Native print arguments retain the part-owned limit and A-B-C frame."""
    from _drawing_hole_callout import add_native_hole_callout

    assert drawing.add_native_hole_callout is add_native_hole_callout
    assert drawing.ROD_HOLE.fields["dia"][1] == (
        "ROD_HOLE_SPEC",
        "UNIT",
        ("_hole_spec", "NUMBER_DRILL_MM"),
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = pivot bore axis, B = broad face (right end view), G = the hub's -Z
    # end face: edge tags. C is the rod-pin hole, tagged on its own position
    # frame (option 4), which references only A|B.
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_frame_datum_feature(\n            adapter, end, rod_position_gtol,") == 1
    assert drawing.ROD_HOLE.fields["datum"][0] == "C"
    # Datum A's leader runs oblique, 45 deg off both centre-mark axes.
    assert math.degrees(drawing.PIVOT_DATUM_ANGLE) % 90.0 == pytest.approx(45.0)
    assert 'label="pivot bore cylindrical datum feature"' in source
    assert source.count("shoulder=True") == 1
    tree = ast.parse(source)
    frames = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_feature_control_frame"
        and any(
            keyword.arg == "characteristic"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "position"
            for keyword in node.keywords
        )
    ]
    assert len(frames) == 1
    keywords = {keyword.arg: keyword.value for keyword in frames[0].keywords}
    # Evaluate the actual native print-call arguments without invoking COM.
    printed_datums = eval(
        compile(ast.Expression(keywords["datums"]), drawing.__file__, "eval"),
        vars(drawing),
    )
    assert printed_datums == ("A", "B")
    printed_tolerance = eval(
        compile(ast.Expression(keywords["tolerance"]), drawing.__file__, "eval"),
        vars(drawing),
    )
    assert (
        printed_tolerance
        == ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_IN["rod-pin hole position"]
    )
    assert drawing.ROD_HOLE.fields["position_dia"][0] == pytest.approx(float(printed_tolerance) * 25.4)
    assert ast.unparse(keywords["diameter"]) == "True"
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" not in source
    assert "add_native_hole_callout(" in source
    # r743-p1s-B: both rod-pin annotations take the diameter-picked edge.
    assert "edge_xy=rod_rim" not in source
    assert source.count("edge=rod_hole_edge") == 1
    assert source.count("edge_entity=rod_hole_edge") == 1


def test_profile_nominals_are_kept_natively_without_note_only_duplicates() -> None:
    names = {"TopRadius", "BottomRadius", "TopAbovePivot", "BottomBelowPivot"}
    assert drawing.BASIC_PROFILE_DIMENSIONS == names
    assert names <= drawing.FRONT_KEEP.keys()
    assert not hasattr(drawing, "NOTE_ONLY_DIMENSIONS")


def test_basic_radius_text_positions_are_outside_their_parent_circles() -> None:
    """Inside-circle R800 placement retained a centre tail on the native sheet."""
    centre_model_y = (
        drawing.PIVOT_MID_Y + ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT + drawing.R_TOP
    )
    centre = _front_xy(0.0, centre_model_y)
    for name, radius in (
        ("TopRadius", drawing.R_TOP),
        ("BottomRadius", drawing.R_BOTTOM),
    ):
        rendered_radius = math.dist(
            centre, _front_xy(0.0, centre_model_y + radius)
        )
        assert math.dist(centre, drawing.FRONT_KEEP[name]) > rendered_radius
    # Negative control: the former top label lay inside the same nominal circle.
    top_rendered_radius = math.dist(
        centre, _front_xy(0.0, centre_model_y + drawing.R_TOP)
    )
    assert math.dist(centre, (0.130, 0.218)) < top_rendered_radius


def test_radius_text_positions_are_outside_their_parent_circles() -> None:
    """Inside-circle R800 placement retained a centre tail on the native sheet."""
    centre_model_y = (
        drawing.PIVOT_MID_Y + ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT + drawing.R_TOP
    )
    centre = _front_xy(0.0, centre_model_y)
    for name, radius in (
        ("TopRadius", drawing.R_TOP),
        ("BottomRadius", drawing.R_BOTTOM),
    ):
        rendered_radius = math.dist(
            centre, _front_xy(0.0, centre_model_y + radius)
        )
        assert math.dist(centre, drawing.FRONT_KEEP[name]) > rendered_radius
    # Negative control: the former top label lay inside the same nominal circle.
    top_rendered_radius = math.dist(
        centre, _front_xy(0.0, centre_model_y + drawing.R_TOP)
    )
    assert math.dist(centre, (0.130, 0.218)) < top_rendered_radius


def test_r20_local_requests_leave_views_geometry_and_strict_caption_air_unchanged() -> None:
    """Placement hypotheses from R19 ink, not proof of the next native render."""
    assert drawing.FRONT_CENTER == (0.180, 0.175)
    assert drawing.ISO_CENTER == (0.345, 0.205)
    assert drawing.HUB_CENTER == (0.180, 0.095)
    assert drawing.END_CENTER == (0.330, 0.110)
    assert drawing.HUB_SCALE == (4.0, 1.0)
    assert drawing.END_SCALE == (2.0, 1.0)
    assert drawing.DETAIL_NO_OUTLINE == {"D": False, "E": False}
    assert drawing.DETAIL_STYLE == {"D": 2, "E": 2}  # swDetViewLEADER connects each source circle.
    assert drawing.DETAIL_LETTER_XY == {"D": (0.188, 0.161), "E": (0.264, 0.155)}
    assert drawing.ROD_CALLOUT_XY == (0.279, 0.115)
    assert drawing.FCF_XY == (0.262, 0.1001)
    assert drawing._DETAIL_CAPTION_TARGET_AIR_M == 0.004
    assert drawing.DETAIL_GEOMETRY_TOL_M == 0.00005
    # R816 moves left; the RD2 arrow and full witness stay at physical A's X.
    radius_dx = drawing.FRONT_KEEP["BottomRadius"][0] - 0.170
    assert 0.180 - (0.1784 + radius_dx) >= 0.002
    # Hole callout and DOT FCF requests: physical circular edge remains unchanged.
    pin_xy = _end_xy(drawing.ROD_HOLE_X, drawing.ROD_HOLE_Y)
    assert math.dist(drawing.ROD_CALLOUT_XY, pin_xy) < math.dist((0.270, 0.145), pin_xy)


def _view_f_xy(z_mm: float, y_mm: float) -> tuple[float, float]:
    """View F (Right view) sheet point of model (z, y): +Z prints left."""
    scale = drawing.RIGHT_SCALE[0] / drawing.RIGHT_SCALE[1]
    return (
        drawing.RIGHT_CENTER[0] - z_mm * scale / 1000.0,
        drawing.RIGHT_CENTER[1] + (y_mm - ch_rocker_arm_spec.TOP_END_Y / 2.0) * scale / 1000.0,
    )


def test_datum_b_sits_on_the_projected_broad_face_above_the_hub_and_thickness_block() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build"
    )
    broad = next(
        node for node in build.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(name, ast.Name) and name.id == "broad_face"
            for target in node.targets for name in ast.walk(target)
        )
    )
    call = next(
        node for node in ast.walk(build)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_datum_feature"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "broad face"
            for keyword in node.keywords
        )
    )
    calls, projected = [], []
    right = object()

    def project(_adapter, view, points, **_kwargs):
        assert view is right
        projected.extend(points)
        return [_view_f_xy(z * 1000.0, y * 1000.0) for _x, y, z in points]

    namespace = dict(
        adapter=object(), right=right, _project=project,
        ARM_THICKNESS=drawing.ARM_THICKNESS,
        DATUM_B_PICK_MODEL_Y=drawing.DATUM_B_PICK_MODEL_Y,
        DATUM_B_SYMBOL_XY=drawing.DATUM_B_SYMBOL_XY,
        STRAP_DATUM_B=drawing.STRAP_DATUM_B,
        add_datum_feature=lambda *_args, **kwargs: calls.append(kwargs),
    )
    module = ast.Module(body=[broad, ast.Expr(value=call)], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), drawing.__file__, "exec"), namespace)
    assert len(calls) == 1
    assert calls[0]["datum"] == drawing.STRAP_DATUM_B.fields["datum"][0] == "B"
    # The pick is a model point on the +Z broad face, projected natively at
    # view F's scale, above the hub band (the hub hides the flank there) and
    # inside the strap's height.
    ((_x, pick_y, pick_z),) = projected
    assert pick_z * 1000.0 == pytest.approx(ch_rocker_arm_spec.ARM_THICKNESS / 2.0)
    hub_top = rocker_interface.PIVOT_MID_Y + ch_rocker_arm_spec.HUB_DIA / 2.0
    assert hub_top + 5.0 < pick_y * 1000.0 < ch_rocker_arm_spec.TOP_END_Y - 0.5
    assert calls[0]["edge_xy"] == _view_f_xy(pick_z * 1000.0, pick_y * 1000.0)
    # The tag box (~7 mm) hangs up-left of the pick, above the strap
    # thickness block (value + three mate rows, centred on its request).
    symbol_x, symbol_y = calls[0]["symbol_xy"]
    assert symbol_x < calls[0]["edge_xy"][0]
    rows = 1 + len(ch_rocker_arm_notes.STRAP_FIT_CALLOUT.splitlines())
    block_top = drawing.STRAP_THICKNESS_TEXT_XY[1] + (rows - 1) * RENDERED_ROW_PITCH / 2 + 0.00175
    assert symbol_y - 0.0035 - block_top >= 0.003
    assert symbol_y + 0.0035 < DRAWABLE.ymax


_REAM_ROW = Box(0.1040, 0.1444, 0.1561, 0.1480)
_R816_ROW = Box(0.0815, 0.1512, 0.1032, 0.1547)
# R8 native readbacks at the former (20,134) request, not a frame-width guess.
_R8_LOWER_FRAME_WIDTH_M = 0.047339
_R8_RIGHT_SHOULDER_M = 0.006350
_R8_LOWER_LANDING = (0.130000, 0.170752)


@pytest.mark.parametrize("junction", [(0.1056, 0.1185), (0.0937, 0.1015)])
def test_observed_r6_r7_profile_junctions_intersect_ream_row(junction) -> None:
    """Recorded native junctions, not a side inferred from the frame request."""
    segment = Segment(*junction, 0.1300, 0.1708, "leader")
    target = AnnotationGeometry("REAM +0.03", "hole-callout", "front")
    assert segment_box_distance(segment, _REAM_ROW) == 0.0
    penetration, _span = text_overlap(segment, target, _REAM_ROW)
    assert penetration > 0.0036


def test_r7_cannot_be_proved_clear_from_a_guessed_left_junction() -> None:
    guessed = Segment(0.040 - 0.0064, 0.105 - 0.0035, 0.130, 0.1708, "leader")
    observed = Segment(0.0937, 0.1015, 0.130, 0.1708, "leader")
    assert segment_box_distance(guessed, _REAM_ROW) > drawing.ARC_PROFILE_TEXT_CLEARANCE_M
    assert segment_box_distance(observed, _REAM_ROW) == 0.0


def test_observed_r8_profile_route_intersects_actual_basic_r816_row() -> None:
    observed = Segment(0.073689, 0.130500, *_R8_LOWER_LANDING, "leader")
    target = AnnotationGeometry("BASIC R816", "dim", "front")
    assert segment_box_distance(observed, _R816_ROW) == 0.0
    penetration, _span = text_overlap(observed, target, _R816_ROW)
    assert penetration > 0.0
    assert segment_box_distance(observed, _REAM_ROW) > drawing.ARC_PROFILE_TEXT_CLEARANCE_M


def test_historical_r9_prediction_clears_both_r8_rows_independent_of_r10() -> None:
    """Historical observed-algorithm regression, not proof of current placement."""
    assert drawing.ARC_PROFILE_TEXT_CLEARANCE_M == 0.001
    frame_x, frame_y = (0.020, 0.129)
    head = (frame_x + _R8_LOWER_FRAME_WIDTH_M, frame_y - 0.0035)
    elbow = (head[0] + _R8_RIGHT_SHOULDER_M, head[1])
    assert head == pytest.approx((0.067339, 0.125500))
    assert elbow == pytest.approx((0.073689, 0.125500))
    predicted = (Segment(*head, *elbow, "leader"), Segment(*elbow, *_R8_LOWER_LANDING, "leader"))
    for box, predicted_gap_mm in ((_REAM_ROW, 1.448), (_R816_ROW, 1.547)):
        distance = min(segment_box_distance(segment, box) for segment in predicted)
        assert distance >= drawing.ARC_PROFILE_TEXT_CLEARANCE_M
        assert distance * 1000.0 == pytest.approx(predicted_gap_mm, abs=0.002)


def _native_line(x0, y0, x1, y1):
    return [0, 0, 0, 0, x0, y0, 0, x1, y1, 0]


class _ClearanceDisplayData:
    """Method-shaped native reads; the real dump/parser are NOT replaced."""

    _native_interfaces = ("IDisplayData",)

    def __init__(self, texts, lines, *, primitives=None):
        self.texts, self.lines = texts, lines
        self.primitives = {} if primitives is None else primitives

    def GetLineCount(self):  # noqa: N802
        return len(self.lines)

    def GetLineAtIndex3(self, index):  # noqa: N802
        return self.lines[index]

    def GetTextCount(self):  # noqa: N802
        return len(self.texts)

    def GetTextAtIndex(self, index):  # noqa: N802
        return self.texts[index]["t"]

    def GetTextPositionAtIndex(self, index):  # noqa: N802
        return self.texts[index]["pos"]

    def GetTextHeightAtIndex(self, index):  # noqa: N802
        return self.texts[index]["h"]

    def GetTextRefPositionAtIndex(self, index):  # noqa: N802
        return self.texts[index].get("ref", 1)

    def GetTextAngleAtIndex(self, index):  # noqa: N802
        return self.texts[index].get("ang", 0.0)

    def GetTextFontAtIndex(self, index):  # noqa: N802
        return "Arial"

    def GetTextLineSpacingAtIndex(self, index):  # noqa: N802
        return 0.0

    def GetTextInBoxWidthAtIndex(self, index):  # noqa: N802
        return self.texts[index].get("w", 0.0)

    def __getattr__(self, name):
        # Unused primitive classes have an authoritative zero count, not None.
        primitives = {
            "GetArcCount": ("arcs", "GetArcAtIndex2"),
            "GetArrowHeadCount": ("arrows", "GetArrowHeadAtIndex2"),
            "GetPolyLineCount": ("polylines", "GetPolylineAtIndex2"),
            "GetPolygonCount": ("polygons", "GetPolygonAtIndex"),
            "GetTriangleCount": ("triangles", "GetTriangleAtIndex"),
            "GetEllipseCount": ("ellipses", "GetEllipseAtIndex2"),
        }
        for count_name, (key, getter_name) in primitives.items():
            if name == count_name:
                return lambda: len(self.primitives.get(key, ()))
            if name == getter_name:
                return lambda index: self.primitives.get(key, ())[index]
        raise AttributeError(name)


# IDisplayData's documented rows, not shortened fixtures accepted by tolerant
# parsers. Metadata is unitless; all point/size values below are in metres.
_NATIVE_CALLOUT_ROWS = {
    "lines": _native_line(0.03, 0.04, 0.05, 0.04),
    "arcs": [-1, 0, 0, 0, 0.03, 0.04, 0, 0.04, 0.05, 0,
             0.03, 0.05, 0, 0, 0, 1, -1],
    "polylines": [0, 0, 0, 0, 0, 0, 3,
                  0.03, 0.04, 0, 0.05, 0.04, 0, 0.06, 0.05, 0],
    "polygons": [0, 0, 0, 0, 3,
                 0.03, 0.04, 0, 0.05, 0.04, 0, 0.06, 0.05, 0],
    "triangles": [0.03, 0.04, 0, 0.05, 0.04, 0, 0.06, 0.05, 0, -1, 0],
    "arrows": [0.06, 0.05, 0, -1, 0, 0, 0.003, 0.002, 0, 0, 0, 1],
    "ellipses": [-1, 0, 0, 0, 0.03, 0.04, 0, 0.03, 0.04, 0,
                 0.04, 0.04, 0, 0.05, 0.04, 0, 0.04, 0.045, 0],
}


def test_profile_zone_mirror_station_envelopes_and_template_aim() -> None:
    """Only at the mirror station is the arc normal vertical. These limits
    do not assert a rigid vertical offset of the curve at its ends. The
    nominal is mid-zone (owner ruling 2026-11-08, #2144 item 10.3): its zones
    admit exactly the former one-sided bands' edges."""
    centre = rocker_interface.CENTER_Y
    assert (ch_rocker_arm_spec.R_TOP, rocker_interface.R_BOTTOM) == pytest.approx((799.746, 815.746))
    nominal_top = centre - ch_rocker_arm_spec.R_TOP - rocker_interface.PIVOT_MID_Y
    nominal_bottom = centre - rocker_interface.R_BOTTOM
    assert nominal_top == pytest.approx(8.254)
    assert nominal_bottom == pytest.approx(0.254)
    assert drawing.TOP_EDGE_BAND is ch_rocker_arm_spec.TOP_EDGE_BAND
    zone = float(drawing.ARC_PROFILE_ZONE_MM)
    assert zone == pytest.approx(0.508)
    assert not hasattr(drawing, "ARC_PROFILE_OUTSIDE_MM")
    assert (nominal_top - zone / 2.0, nominal_top + zone / 2.0) == pytest.approx((8.0, 8.508))
    assert (nominal_bottom - zone / 2.0, nominal_bottom + zone / 2.0) == pytest.approx((0.0, 0.508))
    # The template aims at the nominal itself now.
    assert nominal_top == pytest.approx(8.254)
    # The printed frames read the same zone in inch.
    assert drawing.ARC_PROFILE_ZONE_TEXT == ".020"


def test_part_stamps_make_critical_drawing_properties() -> None:
    import _config

    spec = _config.parts("ch-rocker-arm")
    assert spec["material_specification"] == "AISI 1018 low-carbon steel"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20


def test_pivot_bore_carries_no_roughness_symbol() -> None:
    """Owner ruling 2026-11-24, fit audit question 1: the pivot only rocks
    against one side of its clearance (drawing-guidelines.md rule 6)."""
    assert ch_rocker_arm_spec.SURFACE_FINISHES == ()
    assert arm.SURFACE_FINISHES == ()
    assert arm.PIVOT_HOLE_DIA == ch_rocker_arm_spec.PIVOT_HOLE_DIA
    assert "finish_ra" not in drawing.PIVOT_BORE.requirements


def test_every_view_keep_map_is_curated_on_its_own_view() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRk__): RIGHT_KEEP promised HubLength but
    build() curated only the front view, so the hub length never printed. Each
    non-empty <VIEW>_KEEP must be curated on that view, and curation fails
    loud on a missing kept dimension, so the print carries every one."""

    assert drawing.DRAWING_DIMENSIONS is ch_rocker_arm_notes.DRAWING_DIMENSIONS


def test_hub_length_prints_its_symmetric_band() -> None:
    """#3114: the arms float on the pivot shaft, each located by its rod, so
    no stack sums the hubs and the length is not the station pitch; it prints
    .278 +/-.002 at three places, natively."""
    import _config
    from _drawing_contract import model_toleranced_dimensions

    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["Hub"] == {"HubLength"}
    assert "HubLength" in drawing.RIGHT_KEEP
    assert model_toleranced_dimensions(arm)[("Hub", "HubLength")] == "hub_upper"
    assert ch_rocker_arm_spec.HUB_LENGTH_BAND == (0.0508, -0.0508)
    assert ch_rocker_arm_notes.DRAWING_PRECISION["Hub"]["HubLength"] == 3
    assert ch_rocker_arm_spec.inch_text(ch_rocker_arm_spec.HUB_LENGTH, 3) == ".278"
    assert ch_rocker_arm_spec.HUB_LENGTH_MAX < _config.machine("channels", "station_pitch_mm")
    assert f"{ch_rocker_arm_spec.HUB_LENGTH:.2f}" not in ch_rocker_arm_notes.DRAWING_NOTES


def test_strap_thickness_prints_its_band_natively() -> None:
    """Main ruling 2026-10, option b: each inter-arm gap holds one tine of
    each neighbouring rod fork, so the strap prints 2.500 +/-0.025 at three
    places on the Strap extrude's own depth (drawing-simplicity-policy.md `How the repository implements the guidelines`), selected by
    feature and dimension name in the end view, and no note repeats it."""
    from _drawing_contract import model_toleranced_dimensions

    assert ch_rocker_arm_spec.ARM_THICKNESS_BAND == (0.0254, -0.0254)
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["Strap"] == {"StrapThickness"}
    assert ch_rocker_arm_notes.DRAWING_PRECISION["Strap"]["StrapThickness"] == 3
    assert "StrapThickness" in drawing.RIGHT_KEEP
    assert "StrapThickness" not in drawing.FRONT_KEEP
    assert model_toleranced_dimensions(arm)[("Strap", "StrapThickness")] == "strap_upper"
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "ALL HOLES THRU" not in joined
    assert "STRAP 2.50" not in joined
    assert "THICK" not in joined
    assert "GROUND" not in joined  # the strap faces are milled (plan op 20)


def _callout_block(xy: tuple[float, float], callout: str) -> Box:
    """Predicted native block: value row plus below-text rows, centred on the request."""
    rows = [""] + callout.splitlines()
    half_w = max(len(row) for row in rows) * CAPTION_CHAR_WIDTH / 2.0
    half_h = (len(rows) - 1) * RENDERED_ROW_PITCH / 2.0 + 0.00175
    return Box(xy[0] - half_w, xy[1] - half_h, xy[0] + half_w, xy[1] + half_h)


def test_view_f_size_blocks_stand_left_of_the_view_on_the_strap_and_under_it() -> None:
    """Opus #1020 r2 C3: the 2.500 line crosses the strap alone, not the hub;
    the hub width's line runs under the view."""
    assert drawing.RIGHT_KEEP == {
        "HubLength": drawing.HUB_LENGTH_TEXT_XY,
        "StrapThickness": drawing.STRAP_THICKNESS_TEXT_XY,
        "HubRootRadius": drawing.HUB_ROOT_TEXT_XY,
    }
    strap = _callout_block(drawing.STRAP_THICKNESS_TEXT_XY, ch_rocker_arm_notes.STRAP_FIT_CALLOUT)
    hub = _callout_block(drawing.HUB_LENGTH_TEXT_XY, drawing.HUB_LENGTH_TEXT)
    hub_end_x, _ = _view_f_xy(ch_rocker_arm_spec.HUB_LENGTH / 2.0, 0.0)
    strap_left_x, _ = _view_f_xy(ch_rocker_arm_spec.ARM_THICKNESS / 2.0, 0.0)
    _, view_bottom = _view_f_xy(0.0, 0.0)
    _, view_top = _view_f_xy(0.0, ch_rocker_arm_spec.TOP_END_Y)
    _, hub_top = _view_f_xy(0.0, rocker_interface.PIVOT_MID_Y + ch_rocker_arm_spec.HUB_DIA / 2.0)
    for block in (strap, hub):
        assert block.xmin - DRAWABLE.xmin >= 0.005
    # Each block clears the ink level with it: the strap's (above the hub)
    # only the strap face, the hub width's the hub end.
    assert strap_left_x - strap.xmax >= 0.002
    assert hub_end_x - hub.xmax >= 0.002
    # Native runs each dimension line along the block's bottom: the strap's
    # crosses the strap above the hub, the hub width's runs under the view.
    assert strap.ymin - hub_top >= 0.010
    assert strap.ymin < view_top
    assert hub.ymin < view_bottom
    assert strap.ymin - hub.ymax >= 0.020
    # The hub-root radius reads left of the view between the two blocks: under
    # the strap's position frame (one ~5 mm row under its line), over the hub
    # block and the hub top, and left of the hub end, so its leader runs
    # short down-right to the +Z root corner it measures, crossing no part.
    # The whole block counts: value row plus the callout's rows (#2136 r3:
    # the three-row callout's top met the frame).
    root_text = f"{ch_rocker_arm_notes.HUB_ROOT_PREFIX}{ch_rocker_arm_spec.HUB_ROOT_RADIUS_MAX:.3f} MAX"
    root = _callout_block(drawing.HUB_ROOT_TEXT_XY, ch_rocker_arm_notes.HUB_ROOT_CALLOUT)
    root_half_w = len(root_text) * CAPTION_CHAR_WIDTH / 2.0
    assert root.xmax - root.xmin >= 2 * root_half_w
    assert root.xmin - DRAWABLE.xmin >= 0.005
    assert hub_end_x - root.xmax >= 0.002
    assert (strap.ymin - 0.005) - root.ymax >= 0.003
    assert root.ymin - hub.ymax >= 0.010
    assert hub_top < root.ymin


def test_right_view_caption_sits_under_view_f_clear_of_the_hub_width() -> None:
    caption = ch_rocker_arm_notes.RIGHT_VIEW_NOTE
    left, top = drawing.RIGHT_CAPTION_XY
    right = left + len(caption) * CAPTION_CHAR_WIDTH
    assert left > DRAWABLE.xmin
    # Under the view, its row spanning the view's centre line.
    assert left < drawing.RIGHT_CENTER[0] < right
    hub = _callout_block(drawing.HUB_LENGTH_TEXT_XY, drawing.HUB_LENGTH_TEXT)
    # The caption reads well under the hub width's line.
    assert hub.ymin - top >= 0.020
    # Inside the bottom border.
    assert top - 0.0035 > BORDER_BOTTOM


def test_datum_g_and_its_basic_stand_right_of_the_hub_minus_z_face() -> None:
    """#1579 option 1: G's box out right of the -Z face's lower half, the
    BASIC's boxed text out right above the hub, both short of the front
    view's 132.8 left witness and clear of each other."""
    spec = ch_rocker_arm_spec
    face_x, landing_y = _view_f_xy(
        -spec.HUB_LENGTH / 2.0, drawing.HUB_FACE_DATUM_LANDING_Y_MM
    )
    _, hub_bottom = _view_f_xy(0.0, rocker_interface.PIVOT_MID_Y - spec.HUB_DIA / 2.0)
    _, pivot = _view_f_xy(0.0, rocker_interface.PIVOT_MID_Y)
    _, hub_top = _view_f_xy(0.0, rocker_interface.PIVOT_MID_Y + spec.HUB_DIA / 2.0)
    assert hub_bottom < landing_y < pivot
    witness = drawing.FRONT_LEFT_WITNESS_X - drawing.ARROW_TEXT_CLEARANCE_M
    # The tag's box (~7 mm) leads straight out right from its landing.
    g_left = face_x + drawing.HUB_FACE_DATUM_STANDOFF_M
    g = Box(g_left, landing_y - 0.0035, g_left + 0.007, landing_y + 0.0035)
    assert g.xmin - face_x >= 0.005
    assert g.xmax <= witness
    # The BASIC's text, centred on its request, clears the face's extension
    # line, the witness, the hub top and G.
    places = drawing.HUB_FACES.precision["length"]
    text = ch_rocker_arm_spec.inch_text(drawing.HUB_FACE_BASIC_MM, places)
    text_x, text_y = drawing.HUB_FACE_BASIC_TEXT_XY
    half_w = len(text) * CAPTION_CHAR_WIDTH / 2.0
    basic = Box(text_x - half_w, text_y - 0.00175, text_x + half_w, text_y + 0.00175)
    assert basic.xmin - face_x >= drawing.ARROW_TEXT_CLEARANCE_M
    assert basic.xmax <= witness
    assert basic.ymin - hub_top >= 0.005
    assert basic.ymin - g.ymax >= 0.020


def test_top_edge_model_band_is_unchanged_by_the_basic_drawing_override() -> None:
    """The source keeps its height band and centre equation; the drawing's
    imported height is BASIC and governed by surface profile."""
    from _drawing_contract import model_toleranced_dimensions

    upper, lower = ch_rocker_arm_spec.TOP_EDGE_BAND
    assert (upper, lower) == pytest.approx((0.254, -0.254))
    assert ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT == pytest.approx(8.254)
    assert not hasattr(ch_rocker_arm_notes, "TOP_EDGE_BAND")
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["TopEdgeReference"] == {"TopAbovePivot"}
    assert model_toleranced_dimensions(arm)[("TopEdgeReference", "TopAbovePivot")] == (
        "*deviations(TOP_EDGE_BAND)"
    )
    assert "TopAbovePivot" in drawing.FRONT_KEEP
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "ABOVE THE PIVOT" not in joined
    assert f"+{upper:.2f}/0" not in joined
    assert ch_rocker_arm_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"] == 3


def test_pivot_bore_is_f_drilled_at_the_drilled_holes_row() -> None:
    """Owner ruling 2026-11-24, fit audit question 1: the bore is drilled F,
    .257 at the title block's DRILLED HOLES row, with no native band; the
    callout names the drill and its mate and prints no number of its own."""
    from _drawing_contract import model_toleranced_dimensions
    from _hole_spec import LETTER_DRILL_MM

    assert ch_rocker_arm_spec.PIVOT_HOLE_SPEC.size == "F"
    assert ch_rocker_arm_spec.PIVOT_HOLE_DIA == LETTER_DRILL_MM["F"]
    assert ("PivotHoleProfile", "PivotDia") not in model_toleranced_dimensions(arm)
    assert ch_rocker_arm_notes.DRAWING_PRECISION["PivotHoleProfile"]["PivotDia"] == 3
    assert "PivotDia" in drawing.HUB_KEEP
    assert drawing.PIVOT_BORE.fields["process"][0] == "F DRILL"
    assert drawing.PIVOT_BORE.fields["drill"][0] == "F"
    callout = ch_rocker_arm_notes.PIVOT_FIT_CALLOUT
    assert "MHA-CH-05" in callout
    assert "REAM" not in callout
    assert not any(ch.isdigit() for ch in callout.replace("MHA-CH-05", ""))
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "REAM" not in joined


def test_no_rocker_note_carries_a_tolerance_band() -> None:
    """No size/profile band is duplicated in prose. Hub coaxiality remains
    a plain note by Main's ruling (2026-09-26)."""
    for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines():
        if "COAXIAL" in line or "WITHIN" in line:
            continue
        assert not re.search(r"\+\d|[-+]0\.\d+/|±|\+/-", line), line


def test_tip_angle_is_recorded_before_the_unchanged_profile_definition_and_extrusion():
    assert arm._ALPHA_TOP == pytest.approx(ch_rocker_arm_spec._ALPHA_TOP)
    land_angle = math.atan2(
        ch_rocker_arm_spec.ROD_TIP_X - ch_rocker_arm_spec.TOP_END_X,
        ch_rocker_arm_spec.TIP_FACE * math.cos(ch_rocker_arm_spec._ALPHA_TOP),
    )
    assert land_angle == pytest.approx(arm._ALPHA_TOP)


def test_top_basic_height_is_off_the_pin_x_witness() -> None:
    assert drawing.FRONT_KEEP["TopAbovePivot"] == (0.165, 0.191)
    assert drawing.FRONT_KEEP["TopAbovePivot"][0] != drawing.FRONT_CENTER[0]
    assert drawing.PIN_X_TEXT_XY[1] == 0.197
    assert drawing.TAPER_INTERSECTION_TEXT_XY[1] == 0.137
    land_rows = max(
        drawing.LAND_LOCATION_TEXT_XY[1], drawing.LEFT_LAND_LOCATION_TEXT_XY[1]
    )
    assert drawing.OVERALL_WIDTH_TEXT_XY[1] > land_rows + RENDERED_ROW_PITCH
    assert drawing.OVERALL_WIDTH_TEXT_XY[1] + 0.0035 < DRAWABLE.ymax


_APP = _native("ISldWorks", IsSame=lambda a, b: 1 if a is b else 0)


@pytest.fixture
def bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass native wrapping for offline logic only, not native-binding proof."""
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(detail_crop, "_early_bound", _bind_owner)
    import _drawing_layout_audit

    monkeypatch.setattr(_drawing_layout_audit, "_early_bound", _bind_owner)
    # Caption refusals must never probe this host's real seat in an offline test.
    def capture(_adapter, _label, _message, *, exception, **_context):
        raise exception
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)


# Measured on the r743-p1s-B2 render (5100x3300 px on 431.8x279.4 mm): the
# drawable region ends 12.7 mm above the sheet's bottom edge, the linked
# notes pitch ~4.14 mm a line, and the iso caption runs ~2.5 mm a character.
BORDER_BOTTOM = 0.0127
CAPTION_CHAR_WIDTH = 0.0026
# The general notes' rendered advance: r3c's 40-character row spans ~106 mm.
NOTES_CHAR_WIDTH = 0.0027


def _notes_fit_left_of_the_title_block(notes: str) -> bool:
    """Opus #1020 r3 C3 (rule 7's four lines): the notes run full width under
    the front view, every row ending 10 mm short of the title block."""
    widest = max(map(len, notes.splitlines()))
    title_left = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_left_m
    return drawing.NOTES_LEFT + widest * NOTES_CHAR_WIDTH <= title_left - 0.010


# Dimension value + callout rows as the r1 farm render printed them (strap
# thickness: value ~0.183 to last row ~0.166 over three pitches).
RENDERED_ROW_PITCH = 0.0056
RIGHT_BORDER = 0.415
DRAWABLE = DrawableRegion(0.0127, BORDER_BOTTOM, 0.4191, 0.2667)


class _FakeAnnotation:
    _native_interfaces = ("IAnnotation",)
    def __init__(self, position: tuple[float, float]) -> None:
        self.position = position

    def GetPosition(self) -> tuple[float, float, float]:
        return (*self.position, 0.0)

    def SetPosition(self, x: float, y: float, _z: float) -> bool:
        self.position = (x, y)
        return True


class _FakeNote:
    """A top-left-anchored text block whose box sits off its insertion point
    and follows a move only ``tracking`` of the way, as SolidWorks' does."""

    _native_interfaces = ("INote",)

    def __init__(
        self, anchor: tuple[float, float], height: float, tracking: float = 1.0
    ) -> None:
        self.annotation = _FakeAnnotation(anchor)
        self.anchor = anchor
        self.height = height
        self.tracking = tracking

    def GetAnnotation(self) -> _FakeAnnotation:
        return self.annotation

    def GetExtent(self) -> tuple[float, ...]:
        x, y = (
            a + (p - a) * self.tracking
            for a, p in zip(self.anchor, self.annotation.position)
        )
        x0, y1 = x + 0.0008, y - 0.0011
        return (x0, y1 - self.height, 0.0, x0 + 0.180, y1, 0.0)


    # The shorter notes need no historical line-count overflow assumption:
    # the rendered extent, not an old insertion point, governs seating.


# r743-3 (4ca562169, w4): the 21-line block rendered 16.06..110.76 mm, i.e.
# 94.70 mm tall, 0.76 over NOTES_CEILING -- ~4.51 mm a line of rendered
# extent (box margins included), well above the 4.14 line pitch B2 measured.
R743_3_RENDERED_PITCH = 0.09470 / 21


def test_general_notes_leave_a_full_line_of_headroom() -> None:
    """Main (r743-3): the line estimate undercounted, so the block must fit
    the band with one full rendered line to spare at the measured pitch."""
    lines = len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines())
    band = drawing.NOTES_CEILING - DRAWABLE.ymin - drawing.NOTES_BORDER_CLEARANCE
    assert (lines + 1) * R743_3_RENDERED_PITCH <= band
    # Every row ends short of the title block.
    assert _notes_fit_left_of_the_title_block(ch_rocker_arm_notes.DRAWING_NOTES)
    assert len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines()) <= 4


def test_iso_caption_sits_under_the_iso_clear_of_the_frame_and_end_view() -> None:
    caption = ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE
    left, top = drawing.ISO_CAPTION_XY
    right = left + len(caption) * CAPTION_CHAR_WIDTH
    assert top < drawing.ISO_CENTER[1] - 0.003
    assert left > drawing.RIGHT_CENTER[0] + 0.015  # the end view and its +0.05
    assert right < RIGHT_BORDER - 0.005
    # Under the iso: the caption's span overlaps the iso's.
    assert left < drawing.ISO_CENTER[0] < right


def test_land_and_hub_sizes_are_marked_model_dimensions_at_normal_precision() -> None:
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["StrapProfile"] == {
        "TopRadius", "BottomRadius", "RodTipLen", "TipLandAngle",
    }
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["HubProfile"] == {"HubDia"}
    assert set(drawing.END_KEEP) == {"RodTipLen", "TipLandAngle"}
    assert ch_rocker_arm_notes.DRAWING_PRECISION["StrapProfile"]["TipLandAngle"] == 2
    assert "TipLandVerticalLength" not in set().union(
        *ch_rocker_arm_notes.DRAWING_DIMENSIONS.values()
    )
    assert set(drawing.HUB_KEEP) == {"PivotDia", "HubDia"}
    assert not {"RodTipLen", "HubDia"} & set(drawing.FRONT_KEEP)
    assert ch_rocker_arm_notes.DRAWING_PRECISION["HubProfile"]["HubDia"] == 2
    assert ch_rocker_arm_notes.DEFAULT_DRAWING_PRECISION == 2
    assert ch_rocker_arm_spec.LINEAR_2PL == pytest.approx(0.254)
    assert ch_rocker_arm_spec.STRAP_HUB_SYMMETRY == pytest.approx(0.1016)
    # Strap symmetry is a position zone on the strap width to the hub width's
    # datum (Main's option B): no chained hub-end-to-strap offset survives.
    assert ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_IN["strap position to hub"] == ".004"
    letter = drawing.HUB_FACES.fields["datum"][0]
    assert drawing.STRAP_FACES.fields["position_datums"][0] == [letter]
    # Its letter names nothing else on the sheet (Opus #1020 r3 C4: datum D
    # read against detail D) and avoids ASME's barred I, O and Q.
    taken = {"A", "B", "C", *drawing.DETAIL_LETTER_XY, ch_rocker_arm_notes.VIEW_ARROW_LETTER}
    assert letter not in taken | {"I", "O", "Q"}
    assert not any("Offset" in name for names in ch_rocker_arm_notes.DRAWING_DIMENSIONS.values() for name in names)
    assert "StrapOffset" not in drawing.RIGHT_KEEP
    joined = " ".join(ch_rocker_arm_notes.DRAWING_NOTES.split())
    assert "STRAP SYMMETRIC" not in joined


def test_new_measured_quantities_follow_the_source_geometry_equations() -> None:
    spec = ch_rocker_arm_spec
    alpha = spec.TOP_ARC_LEN / (2.0 * rocker_interface.CURVE_RADIUS)
    assert spec._ALPHA_TOP == pytest.approx(alpha)
    assert 2.0 * spec.ROD_TIP_X == pytest.approx(
        2.0 * (rocker_interface.CURVE_RADIUS + spec.TIP_FACE) * math.sin(alpha),
    )
    assert spec.BOT_END_X == pytest.approx(
        (rocker_interface.CURVE_RADIUS + rocker_interface.ARM_DEPTH)
        * math.sin(spec.BOT_ARC_LEN / (2.0 * (rocker_interface.CURVE_RADIUS + rocker_interface.ARM_DEPTH))),
    )
    assert spec.TIP_FACE == pytest.approx(5.706195, abs=1e-6)
    assert (spec.TOP_ARC_LEN, spec.BOT_ARC_LEN) == pytest.approx((291.499258, 266.459732), abs=1e-6)
    assert spec.HUB_DIA == pytest.approx(10.16)
    # (7.0612 - 2.4892) / 2: the .278 hub stands .090 off each strap face (#3114).
    assert (spec.HUB_LENGTH - spec.ARM_THICKNESS) / 2.0 == pytest.approx(2.286)
    assert arm.HUB_PROUD == pytest.approx(2.286)


def test_rod_hole_keeps_its_normal_wall_to_the_real_k_taper_at_printed_bands():
    """Rule 17: the finite oblique taper, not horizontal edge distance.

    Charge the lower profile zone's inside half against the wall: the zone is
    equal-bilateral about the mid-zone taper (#2144 item 10.3), so the wall
    is the one the former Ⓤ0 zone left. This short through hole in the .098
    plate needs no deep-hole drill-wander allowance.
    """
    from _inch_wall_limits import WALL_TARGET_MM
    from _printed_tolerance import drilled_oversize_mm

    spec = ch_rocker_arm_spec
    centre = (rocker_interface.ROD_HOLE_X, rocker_interface.ROD_HOLE_Y)
    tip = (
        spec.ROD_TIP_X,
        spec.TOP_END_Y + spec.TIP_FACE * (spec.TOP_END_Y - rocker_interface.CENTER_Y) / spec.R_TOP,
    )
    bottom = (
        spec.BOT_END_X,
        rocker_interface.CENTER_Y - math.sqrt(rocker_interface.R_BOTTOM**2 - spec.BOT_END_X**2),
    )
    direction = (bottom[0] - tip[0], bottom[1] - tip[1])
    fraction = sum(
        (centre[index] - tip[index]) * direction[index] for index in range(2)
    ) / sum(value**2 for value in direction)
    assert fraction == pytest.approx(0.78301843047)
    assert 0.0 < fraction < 1.0
    closest = tuple(tip[index] + fraction * direction[index] for index in range(2))
    normal_distance = math.dist(centre, closest)
    taper_face = drawing._RIGHT[1]
    face_distance = abs(
        sum(taper_face.normal[index] * centre[index] for index in range(2))
        - taper_face.offset_mm
    )
    assert normal_distance == pytest.approx(face_distance)
    assert normal_distance == pytest.approx(3.56435328575)
    hole_nominal = blind_cut_dia_mm(spec.ROD_HOLE_SPEC)
    # A named drill retains its real size even when its numeric callout rounds.
    # Charge the larger of the native and displayed (inch, rounded up) nominal.
    places = drawing.ROD_HOLE.precision["dia"]
    displayed = math.ceil(hole_nominal / 25.4 * 10**places - 1e-9) / 10**places * 25.4
    conservative_hole_max = max(hole_nominal, displayed) + drilled_oversize_mm(unit=spec.UNIT)
    # Four places (.0785) ceil to .0786 + .004: the .079 three-place print
    # charged 2.1082.
    assert conservative_hole_max == pytest.approx(2.09804)
    position_diameter = float(spec.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    assert position_diameter == drawing.ROD_HOLE.fields["position_dia"][0]
    profile_allowance = -spec.BOTTOM_EDGE_BAND[1]
    worst_wall = normal_distance - conservative_hole_max / 2.0 - position_diameter / 2.0 - profile_allowance
    assert worst_wall == pytest.approx(2.08353328575)
    assert worst_wall >= WALL_TARGET_MM, f"rod-pin hole to K-taper normal wall is only {worst_wall:g} mm"


@pytest.mark.parametrize("ignored_part", [None, 1, 2])
def test_native_reference_parentheses_never_replace_the_measured_nominal(
    monkeypatch: pytest.MonkeyPatch, ignored_part: int | None,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    text = {1: "", 2: ""}
    writes = []
    model = _native("IDimension", SystemValue=0.00227825)

    def set_text(part, value):
        writes.append((part, value))
        if part != ignored_part:
            text[part] = value

    display = _native("IDisplayDimension", SetText=set_text, GetText=lambda part: text[part],
    GetDimension2=lambda _index: model,)
    annotation = _native("IAnnotation", GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    if ignored_part is None:
        assert _drawing_dimensions.set_reference_dimension(
            adapter, annotation, label="strap offset",
        ) is display
        assert text == {1: "(", 2: ")"}
    else:
        with pytest.raises(RuntimeError, match="failed to parenthesize"):
            _drawing_dimensions.set_reference_dimension(
                adapter, annotation, label="strap offset",
            )
    assert writes == [(1, "("), (2, ")")]
    assert model.SystemValue == 0.00227825


def test_rod_drill_identifier_and_native_callout_process_share_the_hole_spec() -> None:
    from _hole_spec import drill_process

    assert ch_rocker_arm_spec.ROD_HOLE_SPEC.kind == "drilled_number"
    assert ch_rocker_arm_spec.ROD_HOLE_SPEC.size == "#47"
    assert drill_process(ch_rocker_arm_spec.ROD_HOLE_SPEC) == "#47 DRILL"
    # The pin that runs in the hole is named over the drill (Opus #1020 r3 C5).
    import _config

    assert _config.parts("sh-vn-pivot-pin")["number"] in ch_rocker_arm_notes.ROD_PIN_MATE_CALLOUT
    assert drawing.ROD_HOLE_SPEC is ch_rocker_arm_spec.ROD_HOLE_SPEC


@pytest.mark.parametrize("quantity,expected", [
    ("overall", 2.0 * ch_rocker_arm_spec.ROD_TIP_X),
    ("land", ch_rocker_arm_spec.TIP_FACE),
    ("taper", ch_rocker_arm_spec.BOT_END_X),
    ("hub", ch_rocker_arm_spec.HUB_DIA),
    ("offset", (ch_rocker_arm_spec.HUB_LENGTH - ch_rocker_arm_spec.ARM_THICKNESS) / 2.0),
])
@pytest.mark.parametrize("defect", [
    None, "wrong", "missing", "neighbour", "dangling", "nan", "inf", "no_value",
])
def test_native_linear_measurement_reads_the_model_and_named_attachments(
    monkeypatch: pytest.MonkeyPatch, quantity: str, expected: float, defect: str | None,
) -> None:
    import _drawing_edge_dimensions
    from solidworks_mcp.adapters import sw_type_info

    first, second, neighbour = object(), object(), object()
    model = None if defect == "missing" else _native("IDimension", SystemValue=(expected + (0.1 if defect == "wrong" else 0.0)) / 1000.0, )
    if defect in {"nan", "inf", "no_value"}:
        model.SystemValue = None if defect == "no_value" else float(defect)
    attached = (first, neighbour if defect == "neighbour" else second)
    annotation = _native("IAnnotation", GetAttachedEntities3=lambda: attached, GetAttachedEntityTypes=lambda: (1, 1),
    IsDangling=lambda: defect == "dangling",)
    display = _native("IDisplayDimension", GetDimension2=lambda _index: model, GetAnnotation=lambda: annotation,)
    adapter = SimpleNamespace(swApp=_APP)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", _bind_owner)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    monkeypatch.setattr(
        _drawing_edge_dimensions, "_is_same_attachment",
        lambda _adapter, actual, wanted, _kind: actual is wanted,
    )
    kwargs = dict(expected_mm=expected, label=quantity, entities=(first, second))
    if defect is None:
        assert _drawing_edge_dimensions.assert_dimension_measures(
            adapter, display, **kwargs,
        ) == pytest.approx(expected)
    else:
        with pytest.raises((RuntimeError, AttributeError)):
            _drawing_edge_dimensions.assert_dimension_measures(adapter, display, **kwargs)


@pytest.mark.parametrize("retained", [True, False])
def test_native_reference_precision_reads_back_normal_two_places(
    monkeypatch: pytest.MonkeyPatch, retained: bool,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    state = {"precision": 3}
    calls = []

    def set_precision(primary, dual, tolerance, dual_tolerance):
        calls.append((primary, dual, tolerance, dual_tolerance))
        if retained:
            state["precision"] = primary
        return 0  # SetPrecision3 returns native integer status, not VT_BOOL.

    display = _native("IDisplayDimension", SetPrecision3=set_precision, GetPrimaryPrecision2=lambda: state["precision"],)
    annotation = _native("IAnnotation", GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda *_: "offset")
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    kwargs = {"offset": ch_rocker_arm_notes.DEFAULT_DRAWING_PRECISION}
    if retained:
        _drawing_dimensions.set_dimension_precision(adapter, [annotation], kwargs)
        assert state["precision"] == 2
    else:
        with pytest.raises(RuntimeError, match="did not take"):
            _drawing_dimensions.set_dimension_precision(adapter, [annotation], kwargs)
    assert calls == [(2, -1, -1, -1)]


def test_rocker_native_helpers_use_the_extracted_owners() -> None:
    import _drawing_edge_dimensions
    import _drawing_gdt
    import _drawing_hole_callout

    assert drawing.add_edge_dimension is _drawing_edge_dimensions.add_edge_dimension
    assert drawing.add_datum_feature is _drawing_gdt.add_datum_feature
    assert drawing.add_feature_control_frame is _drawing_gdt.add_feature_control_frame
    assert drawing.add_native_hole_callout is _drawing_hole_callout.add_native_hole_callout


@pytest.mark.parametrize("defect", [None, "one_place", "missing", "no_display"])
@pytest.mark.parametrize("feature,name", [("HubProfile", "HubDia"), ("StrapProfile", "TipLandAngle")])
def test_imported_native_dimensions_cannot_lose_the_model_two_place_precision(
    monkeypatch: pytest.MonkeyPatch, defect: str | None, feature: str, name: str,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    display = _native("IDisplayDimension", GetPrimaryPrecision2=lambda: 1 if defect == "one_place" else 2, SetPrecision3=lambda *_: pytest.fail("imported precision is part-owned"),)
    annotation = _native("IAnnotation", GetSpecificAnnotation=lambda: None if defect == "no_display" else display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda *_: name)
    annotations = [] if defect == "missing" else [annotation]
    precision = {name: ch_rocker_arm_notes.DRAWING_PRECISION[feature][name]}
    if defect is None:
        _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)
    else:
        with pytest.raises(RuntimeError):
            _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)


@pytest.mark.parametrize("name", [
    "ROD_TIP_X", "TIP_FACE", "_ALPHA_TOP", "BOT_END_X", "HUB_DIA",
    "ARM_THICKNESS",
])
def test_measured_dimension_expectations_import_the_geometry_source(name: str) -> None:
    assert getattr(drawing, name) == getattr(ch_rocker_arm_spec, name)


class _NativeQuantityAnnotation:
    """IAnnotation owns specific-object lookup and dimension attachment reads."""

    _native_interfaces = ("IAnnotation",)

    def __init__(self, display):
        self.display = display
        self.name = display.name

    def GetSpecificAnnotation(self):
        return self.display

    def GetAttachedEntities3(self):
        return self.display.attached

    def GetAttachedEntityTypes(self):
        return tuple(1 for _ in self.display.attached)

    def IsDangling(self):
        return self.display.dangling


class _NativeQuantity:
    """IDisplayDimension retaining independent text and model-size bands."""

    _native_interfaces = ("IDisplayDimension",)

    def __init__(self, name: str, mm: float, *, precision: int = 2) -> None:
        self.name = name
        self.precision = precision
        self.text = {
            1: "<MOD-DIAM>" if name in {"PivotDia", "HubDia"} else "", 2: "",
            3: "<native-upper>", 4: "<native-lower>",
        }
        self.writes = []
        self.ignored_text = None
        self.ignored_precision = False
        self.ShowDimensionValue = True
        self.SolidLeader = True
        self.ArrowSide = 0
        self.second_arrow = (True, True)
        self.Type2 = 6 if name in {"PivotDia", "HubDia"} else 1
        self.band = (0.0, 0.0)
        self.tolerance_type = 0
        self.attached = ()
        self.dangling = False
        self.arc_conditions = {1: 2, 2: 0}
        self.annotation = _NativeQuantityAnnotation(self)
        self.model = _native("IDimension", SystemValue=mm / 1000.0, Type2=6 if name in {"PivotDia", "HubDia"} else 1,
        SetToleranceType=self._set_tolerance_type,
        GetToleranceType=lambda: self.tolerance_type,
        Tolerance=_native("IDimensionTolerance", GetMaxValue=lambda: self.band[0], GetMinValue=lambda: self.band[1]),
        GetArcEndCondition=lambda index: self.arc_conditions[index],
        SetArcEndCondition=self._set_arc_condition,)

    def _set_tolerance_type(self, kind):
        self.tolerance_type = kind
        return True

    def GetAnnotation(self):
        return self.annotation

    def GetDimension2(self, _index):
        return self.model

    def GetDimension(self):
        return self.model

    def _set_arc_condition(self, index, condition):
        self.arc_conditions[index] = condition
        return 0

    def GetText(self, part):
        return self.text[{5: 1, 6: 2, 7: 3, 8: 4}.get(part, part)]

    def SetText(self, part, value):
        self.writes.append((part, value))
        if part != self.ignored_text:
            self.text[part] = value

    def SetPrecision3(self, primary, _dual, _primary_tolerance, _dual_tolerance):
        if not self.ignored_precision:
            self.precision = primary
        return 0  # Native integer status, not VT_BOOL.

    def GetPrimaryPrecision2(self):
        return self.precision

    def SetSecondArrow(self, use_doc, enabled):
        self.second_arrow = (use_doc, enabled)

    def GetUseDocSecondArrow(self):
        return self.second_arrow[0]

    def GetSecondArrow(self):
        return self.second_arrow[1]


def _imported_native_quantities(monkeypatch: pytest.MonkeyPatch):
    from solidworks_mcp.adapters import sw_type_info
    import _drawing_dimensions
    import _drawing_edge_dimensions

    displays = {
        "PivotDia": _NativeQuantity("PivotDia", ch_rocker_arm_spec.PIVOT_HOLE_DIA),
        "RodTipLen": _NativeQuantity("RodTipLen", ch_rocker_arm_spec.TIP_FACE, precision=1),
        "HubDia": _NativeQuantity("HubDia", ch_rocker_arm_spec.HUB_DIA),
        "TipLandAngle": _NativeQuantity("TipLandAngle", 0.0),
    }
    angle = displays["TipLandAngle"]
    angle.Type2 = angle.model.Type2 = 3
    angle.model.SystemValue = ch_rocker_arm_spec._ALPHA_TOP
    adapter = SimpleNamespace(
        _attempt=lambda fn, **_kwargs: fn(), swApp=_APP,
        currentModel=_native("IModelDoc2", GraphicsRedraw2=lambda: None),
    )
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", _bind_owner)
    monkeypatch.setattr(_drawing_dimensions, "_early_bound", _bind_owner)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    def name(_adapter, annotation):
        return _bind_owner(annotation, "IAnnotation").name
    monkeypatch.setattr(drawing, "dimension_name", name)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", name)
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    return adapter, displays


def test_land_locator_guard_runs_after_final_rebuild_and_preserves_marked_census():
    assert set(drawing.FRONT_KEEP) == drawing.BASIC_PROFILE_DIMENSIONS | set(drawing.ARC_RADIUS_NAMES)


def test_datum_c_hangs_under_the_rod_pin_frame_after_its_dot_is_configured() -> None:
    # Y14.5: a feature of size's datum feature symbol sits on its frame.
    frame_left, frame_top = drawing.FCF_XY
    width, height = drawing.ROD_FRAME_SIZE
    x, y = drawing.ROD_DATUM_C_XY
    assert x == pytest.approx(frame_left + width / 2.0)
    assert y == pytest.approx(frame_top - height - 0.005 - drawing.DATUM_TAG_BOX)
    assert width == pytest.approx(0.0351)  # ⌖|Ø0.20|A|B cells on v43, C removed
    assert not hasattr(drawing, "_add_land_datum") and not hasattr(drawing, "LAND_DATUM_STANDOFF")


class _HubRootDisplay(_NativeQuantity):
    """View F's imported HubRootRadius: a radial display with a native MAX band."""

    def __init__(self) -> None:
        super().__init__("HubRootRadius", ch_rocker_arm_spec.HUB_ROOT_RADIUS_MAX, precision=1)
        self.Diametric = False
        self.ignore_leader = False
        self.ArcExtensionLineOrOppositeSide = True
        self.text[1] = ch_rocker_arm_notes.HUB_ROOT_PREFIX  # stamped by the part
        self.model.Tolerance = _native("IDimensionTolerance", Type=ch_rocker_arm_notes.HUB_ROOT_R_TOL_TYPE)

    def __setattr__(self, name, value):
        if name == "ArcExtensionLineOrOppositeSide" and getattr(self, "ignore_leader", False):
            return
        super().__setattr__(name, value)


def test_datum_g_basic_is_the_half_hub_length_off_the_face_requirements() -> None:
    """#1579 option 1: G is the hub's -Z end face, and the strap frame's
    BASIC runs from it to the strap's centre plane, derived, never typed."""
    assert drawing.HUB_FACE_BASIC_MM == pytest.approx(
        ch_rocker_arm_spec.HUB_LENGTH / 2.0
    )
    places = drawing.HUB_FACES.precision["length"]
    assert ch_rocker_arm_spec.inch_text(drawing.HUB_FACE_BASIC_MM, places) == ".139"
    assert drawing.HUB_FACES.fields["datum"] == (
        "G",
        (("draw_ch_rocker_arm", "_hub_face_datum"),),
    )
    (g,) = [
        meta.datums["G"] for meta in drawing._FEATURE_METADATA if "G" in meta.datums
    ]
    assert g[0] == {
        "feature": "hub_faces",
        "surface": "-Z hub end face (stops the neighbouring arm)",
    }
    assert g[1] == (("draw_ch_rocker_arm", "_hub_face_datum"),)
    assert drawing.STRAP_FACES.fields["position_datums"][0] == ["G"]


class _DetailCircle:
    """Native method-shaped labels, void setter, two out-double getter."""
    _native_interfaces = ("IDetailCircle",)
    def __init__(self, label, *, ignored=False):
        self.label, self.ignored = label, ignored
        self.xy = (0.0, 0.0)

    def GetLabel(self):
        return self.label

    def SetLabelPosition(self, x, y):
        if not self.ignored:
            self.xy = (x, y)

    def GetLabelPosition(self):
        return self.xy


class _DetailTransform:
    """Nonidentity native sketch transform; inverse maps back to sheet units."""
    _native_interfaces = ("IMathTransform",)
    __slots__ = ("scale", "translation", "bad_inverse", "bad_matrix", "inverse_calls")

    def __init__(self, scale=2.0, translation=(0.013, -0.007, 0.0)):
        self.scale, self.translation = scale, translation
        self.bad_inverse = self.bad_matrix = False
        self.inverse_calls = 0

    @property
    def ArrayData(self):
        return () if self.bad_matrix else (
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            *self.translation, self.scale, 0.0, 0.0, 0.0,
        )

    def Inverse(self):
        self.inverse_calls += 1
        if self.bad_inverse:
            return None
        return _DetailTransform(1.0 / self.scale, tuple(-v / self.scale for v in self.translation))

    def IInverse(self):
        raise AssertionError("R11 IDispatch rejects IInverse; use the automation Inverse method")

    def apply(self, xyz):
        return tuple(xyz[i] * self.scale + self.translation[i] for i in range(3))


class _DetailParent:
    _native_interfaces = ("IView",)
    __slots__ = ("transform", "ScaleRatio", "projection_scale", "display_updates")

    def __init__(self):
        self.transform = _DetailTransform()
        self.ScaleRatio = (1.0, 2.0)
        self.projection_scale = 0.5
        self.display_updates = 0

    def GetSketch(self):
        return _native("ISketch", ModelToSketchTransform=self.transform)

    @property
    def ModelToViewTransform(self):
        # Synthetic NEW cross-view hop; the original sketch hop is independent.
        assert self.display_updates > 0
        return _DetailTransform(self.projection_scale, (0.180, 0.175, 0.0))

    def UpdateViewDisplayGeometry(self):
        self.display_updates += 1

    def project(self, xyz):
        return (0.180 + xyz[0] * self.projection_scale,
                0.175 + xyz[1] * self.projection_scale)


class _DetailArc:
    """ISketchArc slice of the same native circle as its selectable segment."""

    _native_interfaces = ("ISketchArc",)

    def __init__(self, segment):
        self.segment = segment

    def IsCircle(self):
        return self.segment.complete  # Native INT 1/0.

    def GetCenterPoint2(self):
        centre = self.segment.centre
        if centre is None:
            return None
        return _native("ISketchPoint", X=centre[0], Y=centre[1], Z=centre[2])

    def GetRadius(self):
        return self.segment.radius


class _DetailProfile:
    _native_interfaces = ("ISketchSegment", "ISketchArc")
    __slots__ = ("centre", "radius", "sketch", "complete", "segment_type", "selectable")

    def __init__(self, centre, radius, sketch):
        self.centre, self.radius, self.sketch = centre, radius, sketch
        self.complete, self.segment_type, self.selectable = 1, 1, True

    def _native_query(self, interface):
        return self if interface == "ISketchSegment" else _DetailArc(self)

    def GetType(self):
        return self.segment_type

    def GetSketch(self):
        return self.sketch

    def Select4(self, _append, _data):
        return self.selectable


def test_detail_transform_fake_refuses_native_inverse_but_supports_automation():
    transform = _DetailTransform()
    with pytest.raises(AssertionError, match="IDispatch rejects IInverse"):
        transform.IInverse()
    inverse = transform.Inverse()
    assert inverse is not None
    assert inverse.apply(transform.apply((0.180, 0.175, 0.0))) == pytest.approx((0.180, 0.175, 0.0))
    assert transform.inverse_calls == 1
    transform.bad_inverse = True
    assert transform.Inverse() is None


class _CaptionTextFormat:
    """Read-only test surface for the native properties the probe reads."""

    _native_interfaces = ("ITextFormat",)

    CharHeight = property(lambda self: 0.0035)
    CharHeightInPts = property(lambda self: 10)
    TypeFaceName = property(lambda self: "Arial")
    LineSpacing = property(lambda self: 1.0)

    def IsHeightSpecifiedInPts(self):
        return False


class _CaptionNote(_FakeNote):
    def __init__(self, label, *, height=0.007):
        super().__init__((0.16 if label == "D" else 0.30, 0.07), height)
        self.label = label
        self._linked = "<VLNAME> <VLLABEL>\r\nSCALE <VLSCALE>"
        self.annotation.SetPosition2 = self.annotation.SetPosition
        self.annotation.GetTextFormatCount = lambda: 1
        self.annotation.GetTextFormat = lambda index: _CaptionTextFormat() if index == 0 else None
        self.annotation.GetUseDocTextFormat = lambda index: index == 0
        self.data = _ClearanceDisplayData([
            {"t": f"DETAIL {label}", "pos": [0.30, 0.07, 0.0], "h": 0.0035},
            {"t": "SCALE 2:1", "pos": [0.30, 0.065, 0.0], "h": 0.0035},
        ], [])
        self.annotation.GetDisplayData = lambda: self.data

    PropertyLinkedText = property(lambda self: self._linked, lambda self, value: setattr(self, "_linked", value))
    HasMultipleFonts = property(lambda self: False)

    def GetText(self):
        return f"DETAIL {self.label}\r\nSCALE 2:1"

    def GetHeight(self):
        return 0.0035

    def GetHeightInPoints(self):
        return 10

    def GetExtent(self):
        extent = list(super().GetExtent())
        extent[3] = extent[0] + 0.03145
        return tuple(extent)


@pytest.fixture
def native_annotation_binding(monkeypatch):
    """Opaque raw dispatches cannot expose members of their bound interfaces."""
    wrappers, calls = {}, []

    def raw(native, interface):
        _bind_owner(native, interface)
        dispatch = object()
        wrappers[id(dispatch)] = (dispatch, interface, native)
        return dispatch

    def bind(dispatch, interface, *_members):
        entry = wrappers.get(id(dispatch))
        if entry is None:
            return _bind_owner(dispatch, interface)
        assert entry[0] is dispatch and entry[1] == interface
        calls.append((interface, entry[2]))
        return _bind_owner(entry[2], interface)

    import _drawing_dimensions
    import _drawing_edge_dimensions
    import _drawing_layout_audit
    import _drawing_notes
    from solidworks_mcp.adapters import sw_type_info

    for module in (
        drawing, detail_crop, _drawing_dimensions, _drawing_edge_dimensions,
        _drawing_layout_audit, _drawing_notes,
    ):
        monkeypatch.setattr(module, "_early_bound", bind)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", bind)
    return SimpleNamespace(raw=raw, bind=bind, calls=calls)


@pytest.mark.parametrize("defect", [
    None, "missing", "null-display", "ignored", "strap-missing", "strap-ignored", "root-missing",
])
def test_hub_length_neighbour_callout_is_below_and_preserves_native_size(
    monkeypatch, defect,
):
    adapter, _imported = _imported_native_quantities(monkeypatch)
    hub = _NativeQuantity("HubLength", ch_rocker_arm_spec.HUB_LENGTH, precision=3)
    hub.band = tuple(value / 1000.0 for value in ch_rocker_arm_spec.HUB_LENGTH_BAND)
    hub.tolerance_type = 4
    strap = _NativeQuantity("StrapThickness", ch_rocker_arm_spec.ARM_THICKNESS, precision=3)
    strap.tolerance_type = 4
    root = _HubRootDisplay()
    before = [
        (d.model.SystemValue, d.band, d.tolerance_type, d.precision) for d in (hub, strap, root)
    ]
    if defect == "null-display":
        hub.annotation.GetSpecificAnnotation = lambda: None
    elif defect == "ignored":
        hub.ignored_text = 4
    elif defect == "strap-ignored":
        strap.ignored_text = 4
    displays = {
        "missing": (strap, root), "strap-missing": (hub, root), "root-missing": (hub, strap),
    }.get(defect, (hub, strap, root))
    annotations = [display.GetAnnotation() for display in displays]
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build"
    )
    start = next(
        index for index, node in enumerate(build.body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "right_annotations"
            for target in node.targets
        )
    )
    # View F's dressing (hub root, strap frame, the strap's centre plane, and
    # datum G with its BASIC to that plane) is one guarded block.
    stop = next(
        index for index, node in enumerate(build.body)
        if isinstance(node, ast.Try)
        and any(
            isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == "_strap_position_frame"
            for call in ast.walk(node)
        )
    )
    label_start = next(
        index for index, node in enumerate(build.body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "set_dimension_callouts"
        and isinstance(node.value.args[1], ast.Name)
        and node.value.args[1].id == "right_annotations"
    )
    assert start < label_start < stop
    right, plane, placed, captured = object(), object(), [], []
    namespace = dict(
        adapter=adapter, right=right, RIGHT_KEEP=drawing.RIGHT_KEEP,
        DRAWING_DIMENSIONS=drawing.DRAWING_DIMENSIONS,
        curate_view_dimensions=lambda *_args, **_kwargs: annotations,
        set_dimension_callouts=drawing.set_dimension_callouts,
        dimension_name=drawing.dimension_name, _early_bound=drawing._early_bound,
        rocker_notes=ch_rocker_arm_notes, HUB_LENGTH_TEXT=drawing.HUB_LENGTH_TEXT,
        _dress_hub_root=drawing._dress_hub_root,
        _strap_position_frame=lambda _adapter, view, ann: placed.append(
            ("frame", view, ann)
        ),
        _strap_centre_plane=lambda _adapter, view: (
            placed.append(("centre plane", view)) or plane
        ),
        _hub_face_datum_g=lambda _adapter, view, centre, ann: placed.append(
            ("G", view, centre, ann)
        ),
        _capture_layout_failure=lambda _adapter, phase, _exc: captured.append(phase),
    )
    # This label test owns the right import, its callout/readback and view F's
    # dressing, not the preceding all-view precision checks and other views.
    module = ast.Module(
        body=[build.body[start], *build.body[label_start:stop + 1]], type_ignores=[],
    )
    code = compile(ast.fix_missing_locations(module), drawing.__file__, "exec")
    if defect is None:
        exec(code, namespace)
        # Hub length names the neighbour it stops and the strap its fork fit,
        # both in below rows (above-text line breaks print as one run).
        assert hub.writes == [(4, drawing.HUB_LENGTH_TEXT)]
        assert "MHA-CH-06" in drawing.HUB_LENGTH_TEXT
        assert strap.writes == [(4, ch_rocker_arm_notes.STRAP_FIT_CALLOUT)]
        assert "MHA-CH-03" in ch_rocker_arm_notes.STRAP_FIT_CALLOUT
        # The position frame hangs on the strap width, then the centre plane
        # it locates, then G on the -Z face with its BASIC to that plane, read
        # back against the hub width.
        assert placed == [
            ("frame", right, strap.annotation),
            ("centre plane", right),
            ("G", right, plane, hub.annotation),
        ]
        assert root.ArcExtensionLineOrOppositeSide is False
        assert captured == []
    else:
        with pytest.raises((RuntimeError, ValueError)):
            exec(code, namespace)
    assert [
        (d.model.SystemValue, d.band, d.tolerance_type, d.precision) for d in (hub, strap, root)
    ] == before


def test_details_keep_native_scale_source_census_and_unclipped_overall_contract():
    assert drawing.HUB_SCALE == (4.0, 1.0) and drawing.END_SCALE == (2.0, 1.0)
    assert not hasattr(drawing, "OVERALL_WITNESS_LENGTH")
    assert not hasattr(drawing, "PIVOT_PICK_ZOOM_HALF")
    assert set(drawing.FRONT_KEEP) == drawing.BASIC_PROFILE_DIMENSIONS | set(drawing.ARC_RADIUS_NAMES)
    assert not hasattr(drawing, "_sheet_xy")
    assert not hasattr(drawing, "_native_circle_geometry")


def test_datum_landing_refuses_null_native_annotation(monkeypatch):
    import _drawing_gdt

    monkeypatch.setattr(_drawing_gdt, "_early_bound", _bind_owner)
    tag = _native("IDatumTag", GetAnnotation=lambda: None)
    with pytest.raises(RuntimeError, match="datum landing has no annotation.*rod-side radial land"):
        _drawing_gdt.assert_datum_landing(
            object(), tag, expected_xy=(0.21, 0.167), label="rod-side radial land",
        )


class _StyleTextFormat:
    """Native get/put properties; CharHeight switches authority to metres."""

    _native_interfaces = ("ITextFormat",)

    def __init__(self, height=0.00635, *, points=False, font="Century Gothic"):
        self._height, self.points, self.font = height, points, font

    CharHeight = property(
        lambda self: self._height,
        lambda self, value: (setattr(self, "_height", value), setattr(self, "points", False)),
    )
    CharHeightInPts = property(lambda self: 24)
    TypeFaceName = property(lambda self: self.font)

    def IsHeightSpecifiedInPts(self):
        return self.points


class _StyleNote(_CaptionNote):
    """R15 local formatting cannot resize the generated SCALE/ratio space."""

    def __init__(self, label, *, ordinary_height=None):
        super().__init__(label, height=0.0166799)
        self.rich = ordinary_height is None
        self.has_multiple = False  # Exercise height guards independently of this flag.
        self.use_doc = True
        self.text_format = _StyleTextFormat(0.00635 if self.rich else ordinary_height)
        self.font_height = self.text_format.CharHeight
        self.writes, self.events = [], []
        self.reset_result = self.write_result = True
        self.on_write = lambda: None
        self.readback_delta = 0.0
        self.document_applied = False
        self._linked = (
            "<VLNAME> <FONT size=3.5><VLLABEL>\r\n"
            "<VLSCALE><FONT size=6.35> <FONT size=3.5><VLSCALEV><FONT size=6.35>"
            if self.rich else '$PRPSHEET:"Manufacturing Notes"'
        )
        runs = [
            ("DETAIL ", 0.0035), (label + "\r\n", 0.0035),
            ("SCALE", 0.0035), (" ", 0.00635),
            ("4:1" if label == "D" else "2:1", 0.0035),
        ] if self.rich else [("1. TURN HUB\r\n", ordinary_height), ("2. REAM BORE", ordinary_height)]
        self.data = _ClearanceDisplayData([
            {"t": text, "h": height, "font": "Century Gothic", "pos": [0.30, 0.07, 0.0]}
            for text, height in runs
        ], [])
        self.data.GetTextFontAtIndex = lambda index: self.data.texts[index]["font"]
        self.annotation.GetDisplayData = lambda: self.data
        self.annotation.GetTextFormat = self.get_format
        self.annotation.GetUseDocTextFormat = lambda _index: self.use_doc
        self.annotation.SetTextFormat = self.set_format

    HasMultipleFonts = property(lambda self: self.has_multiple)

    def GetText(self):
        return " \r\n "  # Not resolved native view-field glyphs.

    def get_format(self, index):
        assert index == 0
        self.events.append("get-format")
        return self.text_format

    def set_format(self, index, use_doc, text_format):
        assert index == 0
        self.writes.append((index, use_doc, None if text_format is None else text_format.CharHeight))
        self.events.append("reset" if use_doc else "local")
        result = self.reset_result if use_doc else self.write_result
        if result is not True:
            return result
        if use_doc:
            assert text_format is None
            self.rich, self.use_doc = False, True
            self._linked = re.sub(r"<FONT[^>]*>", "", self._linked)
        else:
            if self.rich:
                return False
            self.font_height, self.use_doc = text_format.CharHeight, False
            for fragment in self.data.texts:
                if fragment["t"] != " ":  # Actual R15 standalone separator stays 6.35 mm.
                    fragment["h"] = self.font_height + self.readback_delta
            self.height = self.font_height * 2.0
            self.on_write()
        return True

    def apply_document_font(self, preferences):
        if not self.rich or self.document_applied:
            return
        # Generated native runs inherit distinct document detail-font families.
        for fragment, preference in zip(self.data.texts, ((42, 301), (43, 301), (44, 301), (18, 0), (45, 301)), strict=True):
            text_format = preferences[preference]
            fragment["h"] = text_format.CharHeight + self.readback_delta
            fragment["font"] = text_format.TypeFaceName
        self.font_height = self.data.texts[0]["h"]
        self.height = self.font_height * 2.0
        self.document_applied = True
        self.on_write()


class _StyleDocExtension:
    """Document-only native preference methods with detached fresh readbacks."""

    _native_interfaces = ("IModelDocExtension",)

    def __init__(self, notes, circles):
        self.notes, self.circles = notes, circles
        self.preferences = {
            pair: _StyleTextFormat(font="Arial")
            for pair in ((18, 0), (3, 301), (42, 301), (43, 301), (44, 301), (45, 301))
        }
        self.writes, self.reads = [], []
        self.result = True
        self.on_write = lambda _preference: None
        self.on_read = lambda _preference, text_format: text_format

    def SetUserPreferenceTextFormat(self, preference, option, text_format):
        self.writes.append((preference, option, text_format))
        if self.result is True:
            self.preferences[preference, option] = _StyleTextFormat(
                text_format.CharHeight, points=text_format.IsHeightSpecifiedInPts(),
                font=text_format.TypeFaceName,
            )
            self.on_write(preference)
        return self.result

    def GetUserPreferenceTextFormat(self, preference, option):
        self.reads.append((preference, option))
        installed = self.preferences[preference, option]
        return self.on_read(preference, _StyleTextFormat(
            installed.CharHeight, points=installed.IsHeightSpecifiedInPts(), font=installed.TypeFaceName,
        ))

    def create_details(self):
        assert len(self.writes) == 6
        for note in self.notes.values():
            note.apply_document_font(self.preferences)
        text_format = self.preferences[3, 301]
        for circle in self.circles.values():
            circle.font_height, circle.font = text_format.CharHeight, text_format.TypeFaceName
            circle.use_doc, circle.points = True, text_format.IsHeightSpecifiedInPts()


class _StyleCircle(_DetailCircle):
    """Local native circle formatting; a refused setter leaves format unmoved."""

    def __init__(self, label, front, view):
        super().__init__(label)
        self.xy = drawing.DETAIL_LETTER_XY[label]
        # Native textPt and GetLabelPosition need not describe the same anchor.
        self.display_xy = (self.xy[0] + 0.0007, self.xy[1] - 0.0004)
        self.arrows = []
        self.front, self.view = front, view
        self.font_height, self.use_doc, self.points = 0.00635, True, True
        self.font = "Century Gothic"
        self.result = True
        self.delta = self.display_delta = 0.0
        self.writes = []
        self.on_write = lambda: None

    def GetView(self):
        return self.front

    def GetDetailView(self):
        return self.view

    def GetTextFormat(self):
        return _StyleTextFormat(self.font_height, points=self.points, font=self.font)

    def GetUseDocTextFormat(self):
        return self.use_doc

    def SetTextFormat(self, use_doc, text_format):
        self.writes.append((use_doc, text_format.CharHeight))
        if self.result is True:
            self.font_height = text_format.CharHeight + self.delta
            self.use_doc, self.points = use_doc, text_format.IsHeightSpecifiedInPts()
            self.font = text_format.TypeFaceName
            self.on_write()
        return self.result


@pytest.fixture
def native_caption_style(bound, monkeypatch):
    import _drawing_notes

    monkeypatch.setattr(_drawing_notes, "_early_bound", _bind_owner)
    front = _native("IView")
    notes = {label: _StyleNote(label) for label in ("D", "E")}
    views = {
        label: _native("IView", GetNotes=lambda label=label: [notes[label]], GetBaseView=lambda: front,
        Position=drawing.HUB_CENTER if label == "D" else drawing.END_CENTER,
        ScaleRatio=drawing.HUB_SCALE if label == "D" else drawing.END_SCALE,
        UseParentScale=False, UseSheetScale=0,) for label in ("D", "E")
    }
    circles = {label: _StyleCircle(label, front, views[label]) for label in ("D", "E")}
    front.GetDetailCircles = lambda: [circles["E"], circles["D"]]

    display_order, display_reads = ["D", "E"], []
    circle_padding = []

    def circle_info():
        display_reads.append({label: tuple(circle.writes) for label, circle in circles.items()})
        values = [2.0]
        for label in display_order:
            circle = circles[label]
            values.extend([
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                *circle.display_xy, 0, circle.font_height + circle.display_delta, len(circle.arrows),
            ])
            for arrow in circle.arrows:
                values.extend(arrow)
        values.extend(circle_padding)
        return tuple(values)

    front.GetDetailCircleInfo2 = circle_info
    # Native allocation metadata is independent of a replaced info method.
    front.GetDetailCircleCount2 = lambda: (
        len(circles),
        1 + sum(16 + 9 * len(circle.arrows) for circle in circles.values()) + len(circle_padding),
    )
    events, captures = [], []
    extension = _StyleDocExtension(notes, circles)
    def redraw():
        events.append("redraw")
    adapter = SimpleNamespace(
        currentModel=_native("IModelDoc2", Extension=extension, GraphicsRedraw2=redraw),
        swApp=_native("ISldWorks", IsSame=_APP.IsSame),  # No application preferences exist.
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: events.append("rebuild"))
    monkeypatch.setattr(
        drawing._seat_forensics, "capture_com_failure",
        lambda *_args, **context: captures.append(context["exception"]),
    )
    return SimpleNamespace(
        adapter=adapter, front=front, notes=notes, views=views, circles=circles,
        source=_StyleNote("source", ordinary_height=0.0035), events=events, captures=captures,
        extension=extension, display_order=display_order, display_reads=display_reads,
        circle_padding=circle_padding,
    )


def _normalize_style(case):
    font_source = drawing._pin_detail_caption_font_source(case.adapter, case.source)
    case.extension.create_details()  # Native creation happens only AFTER the source pin.
    drawing._normalize_detail_caption_styles(
        case.adapter, case.front, case.views["D"], case.views["E"], font_source,
    )


def test_r15_local_reset_leaves_native_scale_space_but_document_source_pin_fixes_it(native_caption_style):
    local_note = _StyleNote("D")
    annotation = local_note.annotation
    assert annotation.SetTextFormat(0, True, None) is True
    text_format = annotation.GetTextFormat(0)
    text_format.CharHeight = 0.0035
    assert annotation.SetTextFormat(0, False, text_format) is True
    assert local_note.data.texts[3]["t"] == " "
    assert local_note.data.texts[3]["h"] == 0.00635
    assert all(fragment["h"] == 0.0035 for index, fragment in enumerate(local_note.data.texts) if index != 3)
    case = native_caption_style
    assert case.notes["D"].data.texts[3]["h"] == 0.00635
    _normalize_style(case)
    assert case.notes["D"].data.texts[3]["h"] == 0.0035
    assert case.notes["D"].writes == []


@pytest.mark.parametrize("char_height", [None, 0.0041])
def test_ordinary_linked_note_factory_keeps_no_height_and_single_write_paths(native_caption_style, monkeypatch, char_height):
    import _drawing_notes

    note = _StyleNote("ordinary", ordinary_height=0.0035)
    calls = []
    def add_note(adapter, text, x, y):
        calls.append((adapter, text, x, y))
        return note
    monkeypatch.setattr(_drawing_notes, "add_note", add_note)
    returned = _drawing_notes.add_property_linked_note(
        native_caption_style.adapter, "Manufacturing Notes", 0.02, 0.08, char_height=char_height,
    )
    assert returned is note
    assert calls == [(native_caption_style.adapter, '$PRPSHEET:"Manufacturing Notes"', 0.02, 0.08)]
    assert note.PropertyLinkedText == '$PRPSHEET:"Manufacturing Notes"'
    assert note.writes == ([] if char_height is None else [(0, False, char_height)])
    assert "reset" not in note.events
    assert native_caption_style.extension.writes == []


def test_style_normalization_precedes_settled_link_capture_and_both_final_probes():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    (normalize,) = [node for node in calls if node.func.id == "_normalize_detail_caption_styles"]
    (letters,) = [node for node in calls if node.func.id == "_place_detail_letters"]
    (pin_source,) = [node for node in calls if node.func.id == "_pin_detail_caption_font_source"]
    detail_creations = [node for node in calls if node.func.id == "_create_detail"]
    (source_note,) = [
        node for node in calls if node.func.id == "add_property_linked_note"
        and len(node.args) > 1 and ast.literal_eval(node.args[1]) == "Manufacturing Notes"
    ]
    (source_seat,) = [node for node in calls if node.func.id == "_seat_notes_on_border"]
    assert source_note.lineno < source_seat.lineno < pin_source.lineno < min(node.lineno for node in detail_creations)
    assert tuple(ast.unparse(arg) for arg in source_note.args) == ("adapter", "'Manufacturing Notes'", "NOTES_LEFT", "NOTES_CEILING")
    assert tuple(ast.unparse(arg) for arg in pin_source.args) == ("adapter", "notes")
    probes = [node for node in calls if node.func.id == "_record_detail_caption"]
    seats = [node for node in calls if node.func.id == "_seat_detail_caption"]
    assert tuple(ast.unparse(arg) for arg in normalize.args) == ("adapter", "front", "hub", "end", "caption_font_source")
    assert letters.lineno < normalize.lineno < min(node.lineno for node in probes)
    assert max(node.lineno for node in probes) < min(node.lineno for node in seats)
    seat = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_seat_detail_caption")
    assert "note.PropertyLinkedText != linked" in ast.unparse(seat)
    assert drawing.END_CENTER[1] == 0.110
    assert drawing._DETAIL_CAPTION_TARGET_AIR_M == 0.004
    assert "crop[1] - 0.003" in ast.unparse(seat)
    assert "lower_boundary + 0.003" in ast.unparse(seat)
    source_creation_guard = next(
        node for node in ast.walk(build) if isinstance(node, ast.Try)
        and any(call is source_note for call in ast.walk(node))
    )
    assert "_capture_caption_failure(adapter, 'styles', exc)" in ast.unparse(source_creation_guard)
    source_pin = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_pin_detail_caption_font_source")
    assert "_capture_caption_failure(adapter, 'styles', exc)" in ast.unparse(source_pin)
    caption_check = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_require_detail_caption_style")
    assert "SetTextFormat" not in ast.unparse(caption_check)
    import _drawing_notes
    assert not hasattr(_drawing_notes, "set_note_text_height")


def test_reference_dimension_rejects_display_dimension_as_annotation(monkeypatch):
    import _drawing_dimensions

    adapter, _imported = _imported_native_quantities(monkeypatch)
    display = _NativeQuantity("rocker overall width", 2.0 * drawing.ROD_TIP_X)
    nominal = display.model.SystemValue
    with pytest.raises(RuntimeError, match="native owner mismatch.*IAnnotation"):
        _drawing_dimensions.set_reference_dimension(
            adapter, display, label="rocker overall width",
        )
    assert display.writes == []
    assert display.model.SystemValue == nominal
    assert not hasattr(display, "GetSpecificAnnotation")
    assert not hasattr(display.GetAnnotation(), "GetAnnotation")
    assert not hasattr(display.GetAnnotation(), "SetText")


def test_native_owner_registry_refuses_unknown_or_forged_owner(native_annotation_binding):
    binding = native_annotation_binding
    with pytest.raises(RuntimeError, match="native owner mismatch"):
        binding.bind(object(), "IView")
    display = _NativeQuantity("span", 1)
    with pytest.raises(RuntimeError, match="native owner mismatch.*IAnnotation"):
        binding.raw(display, "IAnnotation")
    raw = binding.raw(display, "IDisplayDimension")
    with pytest.raises(AssertionError):
        binding.bind(raw, "IAnnotation")
    assert binding.bind(None, "IAnnotation") is None
    assert binding.calls == []


def test_detail_circle_qi_exposes_separate_segment_and_arc_member_slices():
    profile = _DetailProfile((0, 0, 0), 0.01, _DetailParent().GetSketch())
    segment = _bind_owner(profile, "ISketchSegment")
    arc = _bind_owner(profile, "ISketchArc")
    assert segment is profile and arc.segment is profile
    assert segment.GetType() == 1 and arc.IsCircle() == 1
    assert arc.GetRadius() == 0.01
    assert not hasattr(segment, "IsCircle")
    assert not hasattr(segment, "GetCenterPoint2")
    assert not hasattr(arc, "GetType")
    assert not hasattr(arc, "Select4")


def test_native_fixture_cannot_declare_annotation_and_display_as_one_object():
    with pytest.raises(AssertionError, match="require distinct objects"):
        _native("IAnnotation", "IDisplayDimension")


class _AuthoredGdtAnnotation(_FakeAnnotation):
    """Native IAnnotation only; its producer owns tag/frame-specific methods."""

    def __init__(self, entity, data, *, leaders):
        super().__init__((0.0, 0.0))
        self.entity, self.data = entity, data
        self.leaders, self.dangling = leaders, False
        self.landing = (0.0, 0.0)
        self.leader_writes = []

    def SetPosition2(self, x, y, z):
        assert z == 0.0
        return self.SetPosition(x, y, z)

    def GetAttachedEntities3(self):
        return (self.entity,)

    def GetAttachedEntityCount3(self):
        return 1

    def GetAttachedEntityTypes(self):
        return (1,)  # swSelEDGES.

    def GetLeaderCount(self):
        return self.leaders

    def IsDangling(self):
        return self.dangling

    def GetDisplayData(self):
        return self.data

    def SetLeader3(self, *args):
        self.leader_writes.append(args)
        return 0  # Native integer status.

    def GetLeaderPointsAtIndex(self, index):
        assert index == 0
        return (*self.position, 0.0, *self.landing, 0.0)


class _AuthoredDatumTag:
    _native_interfaces = ("IDatumTag",)

    def __init__(self, annotation):
        self.annotation, self.label = annotation, ""
        self.Shoulder = self.ForcedShoulder = False

    def SetLabel(self, label):
        self.label = label
        return True

    def GetLabel(self):
        return self.label

    def GetAnnotation(self):
        return self.annotation


class _AuthoredGtolFrame:
    """Only IGtolFrame may read/write the XML payload."""

    _native_interfaces = ("IGtolFrame",)

    def __init__(self, events):
        self.xml = ""
        self.events, self.writes = events, []
        self.result = True
        self.on_write = lambda xml: xml

    def SetSymbolXml(self, xml):
        self.events.append("SetSymbolXml")
        self.writes.append(xml)
        if self.result is True:
            self.xml = self.on_write(xml)
        return self.result

    def GetSymbolXml(self):
        self.events.append("GetSymbolXml")
        return self.xml


class _AuthoredGtol:
    """Only IGtol may produce a frame; legacy migration retains native shapes."""

    _native_interfaces = ("IGtol",)

    def __init__(self, frame, annotation, events):
        self.frame, self.annotation, self.events = frame, annotation, events
        self.count, self.format = 0, 2
        self.add_result = True
        self.seed_symbols, self.seed_values = [], []

    def GetFrameCount(self):
        return self.count

    def AddFrame(self):
        self.events.append("AddFrame")
        if self.add_result is True:
            self.count += 1
        return self.add_result

    def GetFrame(self, index):
        assert index == 1
        self.events.append("GetFrame")
        return self.frame if self.format == 2 and self.count == 1 else None

    def GetFormat(self):
        return self.format

    def SetFrameSymbols2(self, *args):
        self.seed_symbols.append(args)
        return None  # Native VT_VOID.

    def SetFrameValues2(self, *args):
        self.seed_values.append(args)
        return True

    def CanConvertFormat(self):
        return True

    def ConvertFormat(self):

        assert self.count == 1 and self.seed_symbols and self.seed_values
        self.events.append("ConvertFormat")
        self.format = 2
        # The migrated current-format frame carries the seeded zone and datums.
        _index, tolerance, _second, *datums = self.seed_values[-1]
        self.migrated_frame.xml = gtol_frame_xml(
            "profile_surface", tolerance, datums=tuple(datum for datum in datums if datum)
        )
        return 0  # Native conversion status.

    def GetAnnotation(self):
        return self.annotation


@pytest.fixture
def actual_rocker_gdt(native_annotation_binding, monkeypatch):
    """Execute actual selection, insertion, attachment, landing and XML helpers."""
    import _drawing_attachment
    import _drawing_gdt
    import _drawing_selection

    binding = native_annotation_binding
    for module in (_drawing_attachment, _drawing_gdt, _drawing_selection):
        monkeypatch.setattr(module, "_early_bound", binding.bind)

    events, selected = [], []
    view = _native("IView", GetName2=lambda: "rocker front")
    landing = (0.210, 0.167)
    data = _ClearanceDisplayData([], [], primitives={
        "arrows": [[*landing, 0.0, -1, 0, 0, 0.003, 0.003, 0, 0, 0, 1]],
    })
    state = SimpleNamespace(
        events=events, selected=selected, landing=landing, selection_result=True,
        on_rebuild=lambda: None,
    )

    def select(append, select_data):
        assert append is False and select_data.View is view
        selected[:] = [entity]
        events.append("Select4")
        return True

    entity = _native("IEntity", Select4=select)
    datum_annotation = _AuthoredGdtAnnotation(
        entity, binding.raw(data, "IDisplayData"), leaders=0,
    )
    frame_annotation = _AuthoredGdtAnnotation(entity, None, leaders=1)
    datum = _AuthoredDatumTag(binding.raw(datum_annotation, "IAnnotation"))
    frame = _AuthoredGtolFrame(events)
    gtol = _AuthoredGtol(
        binding.raw(frame, "IGtolFrame"),
        binding.raw(frame_annotation, "IAnnotation"), events,
    )
    gtol.migrated_frame = frame  # ConvertFormat's current-format payload lands here.
    state.datum_result = binding.raw(datum, "IDatumTag")
    state.gtol_result = binding.raw(gtol, "IGtol")

    def set_landing(index, mark, x, y, z):
        assert (index, mark, z) == (1, -1, 0.0)
        assert selected == [entity]
        events.append(("SetSelectionPoint2", x, y))
        if state.selection_result is True:
            datum_annotation.landing = frame_annotation.landing = (x, y)
            data.primitives["arrows"][0][:2] = [x, y]
        return state.selection_result

    manager = _native(
        "ISelectionMgr",
        CreateSelectData=lambda: _native("ISelectData"),
        GetSelectedObjectCount2=lambda _mark: len(selected),
        GetSelectedObject6=lambda index, mark: selected[index - 1],
        SetSelectionPoint2=set_landing,
    )

    def coordinate_select(name, kind, x, y, z, append, mark, callout, option):
        assert (name, kind, z, append, mark, option) == ("", "EDGE", 0.0, False, 0, 0)
        selected[:] = [entity]
        events.append("SelectByID2")
        return True

    extension = _native("IModelDocExtension", SelectByID2=coordinate_select)

    def insert(kind):
        events.append("InsertDatumTag2" if kind == "datum" else "InsertGtol")
        assert selected == [entity]
        return state.datum_result if kind == "datum" else state.gtol_result

    doc = _native(
        "IModelDoc2", "IDrawingDoc",
        SelectionManager=manager, Extension=extension,
        ActivateView=lambda name: name == "rocker front",
        ClearSelection2=lambda _all: selected.clear(),
        InsertDatumTag2=lambda: insert("datum"),
        InsertGtol=lambda: insert("frame"),
    )
    view.UpdateViewDisplayGeometry = lambda: events.append("UpdateViewDisplayGeometry")
    adapter = SimpleNamespace(
        currentModel=doc, swApp=_APP,
        _get_attr_or_call=lambda native, member: getattr(_bind_owner(native, "IView"), member)(),
    )

    def rebuild(_adapter, *, label):
        assert _adapter is adapter
        events.append(("rebuild", label))
        state.on_rebuild()

    monkeypatch.setattr(_drawing_gdt, "rebuild_drawing", rebuild)
    state.adapter, state.view, state.entity = adapter, view, entity
    state.datum, state.datum_annotation, state.data = datum, datum_annotation, data
    state.gtol, state.frame, state.frame_annotation = gtol, frame, frame_annotation
    state.manager, state.extension, state.doc, state.binding = manager, extension, doc, binding
    return state


def _author_actual_rocker_gdt(case, kind, *, coordinate=False, arc="TopRadius"):
    import _drawing_gdt

    pick = (
        {"edge_xy": case.landing, "expected_entity": case.entity}
        if coordinate and kind == "datum"
        else {"edge_xy": case.landing}
        if coordinate
        else {"edge_entity": case.entity}
    )
    if kind == "datum":
        return _drawing_gdt.add_datum_feature(
            case.adapter, case.view, **pick,
            symbol_xy=(0.225, 0.180), datum="C", label="+Z rod-side radial land",
            leader_attach_xy=case.landing,
        )
    return _drawing_gdt.add_feature_control_frame(
        case.adapter, case.view, **pick,
        frame_xy=drawing.ARC_PROFILE_FRAME_XY[arc], characteristic="profile_surface",
        tolerance=drawing.ARC_PROFILE_ZONE_TEXT,
        datums=("A", "B", "C"), leader_attach_xy=case.landing,
        label=f"arc-system {arc} profile",
    )


@pytest.mark.parametrize("coordinate", [False, True])
def test_actual_datum_helper_retains_selected_land_and_rendered_triangle(actual_rocker_gdt, coordinate):
    import _drawing_gdt

    case = actual_rocker_gdt
    assert _author_actual_rocker_gdt(case, "datum", coordinate=coordinate) is case.datum
    assert case.datum.GetLabel() == "C"
    assert case.datum_annotation.GetPosition() == (0.225, 0.180, 0.0)
    assert _drawing_gdt.assert_datum_landing(
        case.adapter, case.datum, expected_xy=case.landing, label="strict datum C",
    ) == case.landing
    assert ("SetSelectionPoint2", *case.landing) in case.events
    assert case.events.index(("SetSelectionPoint2", *case.landing)) < case.events.index("InsertDatumTag2")
    assert ("IDatumTag", case.datum) in case.binding.calls
    assert ("IAnnotation", case.datum_annotation) in case.binding.calls
    assert ("IDisplayData", case.data) in case.binding.calls
    assert case.datum_annotation.GetLeaderCount() == 0
    assert case.datum_annotation.GetAttachedEntities3() == (case.entity,)


@pytest.mark.parametrize("stage", [
    "drawing-document", "selection-manager", "datum-tag", "annotation", "display-data", "selection-extension",
])
def test_actual_datum_helper_refuses_wrong_produced_interface(actual_rocker_gdt, stage):
    case = actual_rocker_gdt
    if stage == "drawing-document":
        case.adapter.currentModel = case.datum_annotation
    elif stage == "selection-manager":
        case.doc.SelectionManager = case.datum_annotation
    elif stage == "datum-tag":
        case.datum_result = case.frame
    elif stage == "annotation":
        case.datum.annotation = case.datum
    elif stage == "display-data":
        case.datum_annotation.data = case.frame
    else:
        case.doc.Extension = case.datum_annotation
    with pytest.raises((RuntimeError, AttributeError)):
        _author_actual_rocker_gdt(case, "datum", coordinate=stage == "selection-extension")


@pytest.mark.parametrize("defect", ["dangling", "missing-data", "moved-tip", "no-tip", "nonfinite-tip"])
def test_actual_datum_landing_refuses_unreadable_or_moved_triangle(actual_rocker_gdt, defect):
    import _drawing_gdt

    case = actual_rocker_gdt
    _author_actual_rocker_gdt(case, "datum")
    if defect == "dangling":
        case.datum_annotation.dangling = True
    elif defect == "missing-data":
        case.datum_annotation.data = None
    elif defect == "moved-tip":
        case.data.primitives["arrows"][0][0] += 0.000051
    elif defect == "no-tip":
        case.data.primitives.clear()
    else:
        case.data.primitives["arrows"][0][0] = float("nan")
    with pytest.raises(RuntimeError, match="datum landing"):
        _drawing_gdt.assert_datum_landing(
            case.adapter, case.datum, expected_xy=case.landing, label="strict datum C",
        )


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("coordinate", [False, True])
def test_actual_profile_frame_helper_preserves_equal_bilateral_xml_on_frame_owner(
    actual_rocker_gdt, legacy, coordinate,
):

    case = actual_rocker_gdt
    case.gtol.format = 1 if legacy else 2
    case.gtol.count = 1 if legacy else 0
    arc = "TopRadius"  # The drawing's one profile frame.
    assert _author_actual_rocker_gdt(case, "frame", arc=arc, coordinate=coordinate) is case.gtol
    signature = gtol_frame_signature(case.frame.GetSymbolXml())
    assert signature.tolerance == "0.02"
    # Equal-bilateral (#2144 item 10.3): the frame carries no Ⓤ disposition.
    assert signature.outside_disposition is None
    assert signature.datums == ("A", "B", "C")
    assert signature.tolerance_zone == "linear"
    # A migrated frame already carries the equal-bilateral zone: no XML write.
    assert len(case.frame.writes) == (0 if legacy else 1)
    if legacy:
        assert "AddFrame" not in case.events  # AddFrame is current-format only.
        assert "SetSymbolXml" not in case.events
    else:
        assert case.events.index("AddFrame") < case.events.index("SetSymbolXml")
    assert case.events.index(("SetSelectionPoint2", *case.landing)) < case.events.index("InsertGtol")
    assert case.gtol.GetFormat() == 2 and case.gtol.GetFrameCount() == 1
    assert bool(case.gtol.seed_symbols) is legacy
    assert bool(case.gtol.seed_values) is legacy
    if legacy:
        assert case.gtol.seed_values == [
            (1, drawing.ARC_PROFILE_ZONE_TEXT, "", "A", "B", "C"),
        ]
    assert ("IGtol", case.gtol) in case.binding.calls
    assert ("IGtolFrame", case.frame) in case.binding.calls
    assert ("IAnnotation", case.frame_annotation) in case.binding.calls
    assert case.frame_annotation.GetAttachedEntities3() == (case.entity,)
    assert case.frame_annotation.leader_writes == [(2, 0, True, False, False, False)]


@pytest.mark.parametrize("stage", [
    "selection-manager", "selection-extension", "gtol", "frame", "annotation",
])
def test_actual_profile_frame_helper_refuses_wrong_produced_interface(actual_rocker_gdt, stage):
    case = actual_rocker_gdt
    if stage == "selection-manager":
        case.doc.SelectionManager = case.frame_annotation
    elif stage == "selection-extension":
        case.doc.Extension = case.frame_annotation
    elif stage == "gtol":
        case.gtol_result = case.frame
    elif stage == "frame":
        case.gtol.frame = case.frame_annotation
    else:
        case.gtol.annotation = case.gtol
    with pytest.raises((RuntimeError, AttributeError)):
        _author_actual_rocker_gdt(case, "frame", coordinate=stage == "selection-extension")


@pytest.mark.parametrize("target", ["AddFrame", "SetSymbolXml"])
@pytest.mark.parametrize("result", [False, None, 1])
def test_actual_profile_frame_helper_requires_native_bool_writer_success(actual_rocker_gdt, target, result):
    case = actual_rocker_gdt
    if target == "AddFrame":
        case.gtol.add_result = result
    else:
        case.frame.result = result
    with pytest.raises(RuntimeError, match="failed to create|rejected feature-control frame XML"):
        _author_actual_rocker_gdt(case, "frame")
    assert case.frame.xml == ""


@pytest.mark.parametrize("kind", ["datum", "frame"])
@pytest.mark.parametrize("result", [False, None, 1])
def test_actual_gdt_helpers_require_true_selection_landing_before_insertion(actual_rocker_gdt, kind, result):
    case = actual_rocker_gdt
    case.selection_result = result
    with pytest.raises(RuntimeError, match="failed to set.*landing"):
        _author_actual_rocker_gdt(case, kind)
    assert "InsertDatumTag2" not in case.events and "InsertGtol" not in case.events


@pytest.mark.parametrize("defect", [
    "outside-before-rebuild", "outside-after-rebuild", "attachment", "leader-landing",
])
def test_actual_profile_frame_helper_retains_xml_attachment_and_landing_guards(actual_rocker_gdt, defect):

    case = actual_rocker_gdt
    unequal = gtol_frame_xml(
        "profile_surface", drawing.ARC_PROFILE_ZONE_TEXT, datums=("A", "B", "C"),
        outside_disposition=drawing.ARC_PROFILE_ZONE_TEXT,
    )
    if defect == "outside-before-rebuild":
        case.frame.on_write = lambda _xml: unequal
    elif defect == "outside-after-rebuild":
        case.on_rebuild = lambda: setattr(case.frame, "xml", unequal)
    elif defect == "attachment":
        case.on_rebuild = lambda: setattr(case.frame_annotation, "entity", object())
    else:
        case.on_rebuild = lambda: setattr(case.frame_annotation, "landing", (0.215, 0.167))
    with pytest.raises(RuntimeError, match="did not persist|changed semantics|lost its edge attachment|leader attachment moved"):
        _author_actual_rocker_gdt(case, "frame")


def test_actual_gdt_producers_keep_specific_frame_and_annotation_members_disjoint(actual_rocker_gdt):
    case = actual_rocker_gdt
    assert not hasattr(case.gtol, "SetSymbolXml")
    assert not hasattr(case.frame, "AddFrame")
    assert not hasattr(case.frame, "GetAnnotation")
    assert not hasattr(case.frame_annotation, "AddFrame")
    assert not hasattr(case.frame_annotation, "SetSymbolXml")
    assert not hasattr(case.datum_annotation, "SetLabel")
    for native, wrong in (
        (case.gtol, "IGtolFrame"), (case.frame, "IGtol"),
        (case.datum, "IAnnotation"), (case.datum_annotation, "IDatumTag"),
        (case.frame_annotation, "IGtolFrame"),
    ):
        with pytest.raises(RuntimeError, match="native owner mismatch"):
            case.binding.bind(native, wrong)


# R19 layout-audit replay (20261013T051541021Z-0456b55b4ef7424793cb5fdafaf10c41).
# The shared JSON rounds coordinates to 7dp. These are serialized fixtures,
# never unrounded COM evidence and never a production containment allowance.
_R19_NATIVE_MARK_CROPS = {
    "D": (0.15310000000000007, 0.0681000000000001,
          0.20689999999999992, 0.12189999999999995),
    "E": (0.30616186089949615, 0.08616186089949626,
          0.35383813910050377, 0.13383813910050388),
}


def _r19_mark_lines(rows):
    return [[-1.0, 0.0, style, 0.0, x0, y0, 0.0, x1, y1, 0.0]
            for style, x0, y0, x1, y1 in rows]


_R19_MARK_LINES = {
    "front-pivot": _r19_mark_lines((
        (0, 0.18, 0.1716763, 0.18, 0.1729263),
        (0, 0.18, 0.1716763, 0.17875, 0.1716763),
        (0, 0.18, 0.1716763, 0.18, 0.1704263),
        (0, 0.18, 0.1716763, 0.18125, 0.1716763),
        (-1, 0.18, 0.1741763, 0.18, 0.1754763),
        (-1, 0.1775, 0.1716763, 0.1762, 0.1716763),
        (-1, 0.18, 0.1691763, 0.18, 0.1678763),
        (-1, 0.1825, 0.1716763, 0.1838, 0.1716763),
    )),
    "front-pin": _r19_mark_lines((
        (0, 0.2465337, 0.1759044, 0.2465337, 0.1771544),
        (0, 0.2465337, 0.1759044, 0.2452837, 0.1759044),
        (0, 0.2465337, 0.1759044, 0.2465337, 0.1746544),
        (0, 0.2465337, 0.1759044, 0.2477837, 0.1759044),
        (-1, 0.2465337, 0.1771544, 0.2465337, 0.1776528),
        (-1, 0.2452837, 0.1759044, 0.2447852, 0.1759044),
        (-1, 0.2465337, 0.1746544, 0.2465337, 0.1741559),
        (-1, 0.2477837, 0.1759044, 0.2482822, 0.1759044),
    )),
    "D": _r19_mark_lines((
        (0, 0.18, 0.095, 0.18, 0.105),
        (0, 0.18, 0.095, 0.17, 0.095),
        (0, 0.18, 0.095, 0.18, 0.085),
        (0, 0.18, 0.095, 0.19, 0.095),
        (-1, 0.18, 0.115, 0.18, 0.1219),
        (-1, 0.16, 0.095, 0.1531, 0.095),
        (-1, 0.18, 0.075, 0.18, 0.0681),
        (-1, 0.2, 0.095, 0.2069, 0.095),
    )),
    "E": _r19_mark_lines((
        (0, 0.317123, 0.1027457, 0.317123, 0.1077457),
        (0, 0.317123, 0.1027457, 0.312123, 0.1027457),
        (0, 0.317123, 0.1027457, 0.317123, 0.0977457),
        (0, 0.317123, 0.1027457, 0.322123, 0.1027457),
        (-1, 0.317123, 0.1077457, 0.317123, 0.1097396),
        (-1, 0.312123, 0.1027457, 0.3101291, 0.1027457),
        (-1, 0.317123, 0.0977457, 0.317123, 0.0957518),
        (-1, 0.322123, 0.1027457, 0.3241169, 0.1027457),
    )),
}
_R19_MARK_RECORDS = {
    "front": (
        ("DetailItem347", (0.1781134, 0.1699608, 0.0017641), "front-pivot"),
        ("DetailItem349", (0.2462447, 0.1754982, 0.000625), "front-pin"),
        ("DetailItem359", (0.1781134, 0.1699608, -0.0017641), "front-pivot"),
        ("DetailItem361", (0.2462447, 0.1754982, 0.000625), "front-pin"),
    ),
    "D": (
        ("DetailItem352", (0.1616543, 0.0860784, -0.014113), "D"),
        ("DetailItem354", (0.7086834, 0.1270803, 0.005), None),
        ("DetailItem362", (0.1616329, 0.0861226, 0.014113), "D"),
        ("DetailItem364", (0.7083548, 0.1280648, 0.005), None),
    ),
    "E": (
        ("DetailItem356", (0.0417128, 0.0815902, -0.0070565), None),
        ("DetailItem358", (0.3153098, 0.1019162, 0.0025), "E"),
        ("DetailItem365", (0.0453988, 0.0773014, 0.0070565), None),
        ("DetailItem367", (0.3153176, 0.1018994, 0.0025), "E"),
    ),
}


class _MarkDisplayData:
    """Closed IDisplayData surface, with explicit authoritative zero counts."""
    _native_interfaces = ("IDisplayData",)
    _primitives = {
        "lines": ("GetLineCount", ("GetLineAtIndex3", "GetLineAtIndex2")),
        "arcs": ("GetArcCount", ("GetArcAtIndex2",)),
        "arrows": ("GetArrowHeadCount", ("GetArrowHeadAtIndex2",)),
        "polylines": ("GetPolyLineCount", ("GetPolylineAtIndex2",)),
        "polygons": ("GetPolygonCount", ("GetPolygonAtIndex",)),
        "triangles": ("GetTriangleCount", ("GetTriangleAtIndex",)),
        "ellipses": ("GetEllipseCount", ("GetEllipseAtIndex2",)),
    }

    def __init__(self, display):
        self.display = display
        self.overrides, self.reads = {}, []

    def _answer(self, member, default, args):
        self.reads.append((member, args))
        value = self.overrides.get(member, default)
        if isinstance(value, Exception):
            raise value
        return value(*args) if callable(value) else value

    def __getattr__(self, member):
        for key, (count_member, getters) in self._primitives.items():
            if member == count_member:
                return lambda: self._answer(member, len(self.display.get(key, ())), ())
            if member in getters:
                return lambda index: self._answer(
                    member, lambda i: self.display.get(key, ())[i], (index,),
                )
        if member == "GetTextCount":
            return lambda: self._answer(member, len(self.display.get("texts", ())), ())
        raise AttributeError(f"IDisplayData does not own {member}")


class _MarkAnnotation:
    """IAnnotation owns the dispatch hop; it never owns display-data methods."""
    _native_interfaces = ("IAnnotation",)

    def __init__(self, name, position, data):
        self.name, self.position, self.data = name, position, data

    def GetType(self):
        return 13

    def GetName(self):
        return self.name

    def GetPosition(self):
        return self.position

    def GetDisplayData(self):
        return self.data


@pytest.fixture
def mark_census(monkeypatch, native_annotation_binding):
    """Actual census and decoders, opaque native dispatches at both owner hops."""
    binding = native_annotation_binding
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)

    def make(records, *, crop=(0.0, 0.0, 0.1, 0.1)):
        annotations, datas, raws = [], [], []
        for name, position, display in records:
            data = _MarkDisplayData(display)
            annotation = _MarkAnnotation(name, position, binding.raw(data, "IDisplayData"))
            datas.append(data)
            annotations.append(annotation)
            raws.append(binding.raw(annotation, "IAnnotation"))
        view = _native(
            "IView", GetAnnotationCount=lambda: len(raws), GetAnnotations=lambda: tuple(raws),
            GetOutline=lambda: crop,
        )
        return SimpleNamespace(
            annotations=annotations, datas=datas, raws=raws, native_view=view,
            view=binding.raw(view, "IView"), logs=logs, binding=binding, crop=crop,
        )
    return make


@pytest.mark.parametrize("label", ["D", "E"])
def test_r19_crop_and_rows_have_explicit_serialization_intervals_not_a_runtime_allowance(label):
    quantum = 1e-7  # _drawing_layout_audit._round: 0.1 um serialized coordinates.
    native = _R19_NATIVE_MARK_CROPS[label]
    serialized = tuple(round(value, 7) for value in native)
    for observed, boundary in zip(serialized, native):
        assert observed - quantum / 2.0 <= boundary <= observed + quantum / 2.0
    record = next(record for record in _R19_MARK_RECORDS[label] if record[2] is not None)
    assert drawing._center_mark_bucket(record[1], {"lines": _R19_MARK_LINES[label]}, serialized) == "PRINTED"
    # Mixed readback/serialized coordinates differ by a few float64 ULP in D.
    # R23's display-only float32 spacing admits that difference, not the much
    # larger 0.1 um serialization interval; the interval is fixture evidence.
    assert drawing._center_mark_bucket(record[1], {"lines": _R19_MARK_LINES[label]}, native) == "PRINTED"
    row = list(_R19_MARK_LINES[label][0])
    row[4], row[7] = native[0] - quantum / 2.0, native[0] + 0.001
    with pytest.raises(ValueError, match="outside crop"):
        drawing._center_mark_bucket(record[1], {"lines": [row]}, native)


def test_center_mark_containment_rejects_two_float32_ulp_without_fixture_padding():
    crop = (0.0, 0.0, 0.1, 0.1)
    row = _native_line(0.05, 0.05, crop[2], 0.05)
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, crop) == "PRINTED"
    row[7] = crop[2] + 2.0 * math.ldexp(1.0, -27)  # Float32 spacing at 0.1 m.
    with pytest.raises(ValueError, match="outside crop"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, crop)


def test_pure_center_mark_text_data_cannot_use_relative_positions_as_absolute_bounds():
    text = {"t": "X", "pos": [0.05, 0.05, 0], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.004}
    with pytest.raises(ValueError, match="cannot certify primitive containment.*text"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"texts": [text]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("bbox", [
    None, (), (0, 0, 1), (0.1, 0, 0, 0.1), (0, 0.1, 0.1, 0),
    (0, 0, 0, 0.1), (0, 0, 0.1, math.nan), (False, 0, 0.1, 0.1),
])
def test_center_mark_invalid_or_inverted_crop_is_fatal(bbox):
    with pytest.raises(ValueError, match="crop bbox"):
        drawing._center_mark_bucket((0.5, 0.05, 0), {}, bbox)


@pytest.mark.parametrize("buckets,total", [
    ([], 1), (["PRINTED"], 0), (["PRINTED", "GHOST"], 3), (["OTHER"], 1),
])
def test_center_mark_accounting_guard_rejects_count_mismatch_or_unknown_bucket(buckets, total):
    with pytest.raises(RuntimeError, match="bucket/count mismatch|bucket fallthrough"):
        drawing._center_mark_census_totals(buckets, total)


def test_center_mark_fakes_keep_owners_and_member_surfaces_disjoint(mark_census):
    case = mark_census([("ghost", (0.5, 0.05, 0), {})])
    annotation, data = case.annotations[0], case.datas[0]
    assert not hasattr(annotation, "GetLineCount")
    assert not hasattr(annotation, "GetTextCount")
    assert not hasattr(data, "GetDisplayData")
    assert not hasattr(data, "GetType")
    assert not hasattr(data, "GetAnnotations")
    assert not hasattr(data, "GetSpecificAnnotation")
    assert not hasattr(data, "IGetDisplayData")
    for native, interface in ((annotation, "IDisplayData"), (data, "IAnnotation"), (data, "IView")):
        with pytest.raises(RuntimeError, match="native owner mismatch"):
            _bind_owner(native, interface)


@pytest.mark.parametrize("key,header", [("polylines", 7), ("polygons", 5)])
def test_center_mark_one_point_primitive_has_bounds_and_cannot_disappear(key, header):
    row = list(_NATIVE_CALLOUT_ROWS[key][:header + 3])
    row[header - 1] = 1
    assert drawing._center_mark_bucket((0.5, 0.05, 0), {key: [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"
    row[header] = 0.2
    with pytest.raises(ValueError, match="outside crop"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {key: [row]}, (0, 0, 0.1, 0.1))


def test_center_mark_degenerate_line_still_accounts_its_native_coordinates():
    row = _native_line(0.05, 0.05, 0.05, 0.05)
    assert drawing._center_mark_bucket((0.5, 0.05, 0), {"lines": [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"
    row[4] = row[7] = 0.2
    with pytest.raises(ValueError, match="outside crop"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("direction,normal_z", [(1, 1), (0, 1), (1, -1), (-1, 1)])
def test_center_mark_arc_certifies_full_circle_without_guessing_sweep_or_normal_convention(direction, normal_z):
    row = [-1, 0, 0, 0, 0.1, 0.05, 0, 0, 0.05, 0,
           0.05, 0.05, 0, 0, 0, normal_z, direction]
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"arcs": [row]}, (-0.1, -0.1, 0.2, 0.2)) == "PRINTED"
    # A partial sweep could fit, but a nearly closed circle is not distinguished
    # without inventing a threshold. The complete envelope must certify it.
    with pytest.raises(ValueError, match="cannot certify primitive containment.*partial native arcs") as caught:
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arcs": [row]}, (-0.1, -0.1, 0.2, 0.075))
    assert "outside crop" not in str(caught.value)


def test_center_mark_closed_arc_bounds_every_cardinal_extremum():
    row = [-1, 0, 0, 0, 0.05, 0.05, 0, 0.05, 0.05, 0,
           0, 0.05, 0, 0, 0, 1, 1]
    with pytest.raises(ValueError, match="arcs.*envelope not certified inside"):
        drawing._center_mark_bucket((0, 0.05, 0), {"arcs": [row]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("index,value", [(13, 1), (14, 1), (15, 0), (16, 2), (6, 1), (9, 1), (12, 1)])
def test_center_mark_arc_refuses_unmeasurable_plane_or_direction(index, value):
    row = list(_NATIVE_CALLOUT_ROWS["arcs"])
    row[index] = value
    with pytest.raises(ValueError, match="arcs plane/direction"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arcs": [row]}, (0, 0, 0.1, 0.1))


def test_center_mark_ellipse_uses_analytic_rotated_envelope_not_axis_endpoints():
    # X/Y axis extrema lie beyond the individually contained major/minor points.
    row = [-1, 0, 0, 0, 0.08, 0.08, 0, 0.08, 0.08, 0,
           0.05, 0.05, 0, 0.08, 0.08, 0, 0.02, 0.08, 0]
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"
    with pytest.raises(ValueError, match="ellipses.*envelope not certified inside"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0.02, 0.02, 0.08, 0.08))


def test_center_mark_invalid_ellipse_axes_do_not_fall_through():
    row = list(_NATIVE_CALLOUT_ROWS["ellipses"])
    row[16:19] = row[13:16]
    with pytest.raises(ValueError, match="ellipses axes"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("display", [None, [], {"unknown": []}, {"lines": None}])
def test_center_mark_unrecognized_display_data_is_fatal_not_empty(display):
    with pytest.raises(ValueError, match="invalid native"):
        drawing._center_mark_bucket((0.5, 0.05, 0), display, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("data_size", [0, 7, 12])
def test_center_mark_type1_polyline_cannot_guess_undocumented_geomdata_layout(data_size):
    row = list(_NATIVE_CALLOUT_ROWS["polylines"])
    row[:2] = [1, data_size]
    with pytest.raises(ValueError, match="cannot certify primitive containment.*polylines type-1 GeomData"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"polylines": [row]}, (0, 0, 0.1, 0.1))
    row.append(0.05)
    with pytest.raises(ValueError, match="invalid native polylines"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"polylines": [row]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("style", [0, 1])
def test_center_mark_reuses_contracted_triangular_arrow_styles(style):
    row = list(_NATIVE_CALLOUT_ROWS["arrows"])
    row[8] = style
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"arrows": [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"


def test_center_mark_partial_ellipse_accepts_only_proved_full_envelope_certificate():
    row = [-1, 0, 0, 0, 0.08, 0.08, 0, 0.02, 0.08, 0,
           0.05, 0.05, 0, 0.08, 0.08, 0, 0.02, 0.08, 0]
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"
    with pytest.raises(ValueError, match="cannot certify primitive containment.*partial native ellipses") as caught:
        drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0.02, 0.02, 0.08, 0.08))
    assert "raw=" in str(caught.value) and "crop=" in str(caught.value)
    assert "outside crop" not in str(caught.value)  # Sweep direction is unobserved.


@pytest.mark.parametrize("crop", [(-0.1, -0.1, 0.2, 0.2), (-0.1, -0.1, 0.2, 0.075)])
def test_center_mark_inconsistent_arc_radii_are_fatal_even_when_an_estimated_box_would_fit(crop):
    row = [-1, 0, 0, 0, 0.1, 0.05, 0, 0.025, 0.05, 0,
           0.05, 0.05, 0, 0, 0, 1, 1]
    with pytest.raises(ValueError, match="invalid native arcs radius: inconsistent endpoint radii") as caught:
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arcs": [row]}, crop)
    assert "outside crop" not in str(caught.value)


def test_arc_subnormal_float64_endpoint_delta_keeps_strict_full_envelope_requirement():
    # This is the strict curve certificate, not the display bbox's float32 allowance.
    row = [-1, 0, 0, 0, 0.05, 0, 0, 0.05, math.nextafter(0.0, math.inf), 0,
           0, 0, 0, 0, 0, 1, 1]
    assert math.dist(row[4:6], row[10:12]) == math.dist(row[7:9], row[10:12])
    assert drawing._center_mark_bucket((0, 0, 0), {"arcs": [row]}, (-0.1, -0.1, 0.1, 0.1)) == "PRINTED"
    with pytest.raises(ValueError, match="cannot certify primitive containment.*partial native arcs"):
        drawing._center_mark_bucket((0, 0, 0), {"arcs": [row]}, (-0.1, -1e-100, 0.1, 1e-100))


@pytest.mark.parametrize("index,value", [
    (3, 0), (5, 1), (6, -1), (7, -1), (8, -1), (8, 0.5), (8, 13),
    (9, 1), (10, 1), (11, 0),
])
def test_center_mark_arrow_certificate_requires_valid_planar_direction_size_and_known_style(index, value):
    row = list(_NATIVE_CALLOUT_ROWS["arrows"])
    row[index] = value
    with pytest.raises(ValueError, match="invalid native arrows"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arrows": [row]}, (0, 0, 0.1, 0.1))


def test_center_mark_arrow_two_sided_certificate_does_not_rely_on_empirical_base_convention():
    row = list(_NATIVE_CALLOUT_ROWS["arrows"])
    row[0:2] = [0.098, 0.05]
    # The historical triangle points left and would fit, but the documented
    # dimensions alone do not seat its base side. Refuse, do not claim outside.
    with pytest.raises(ValueError, match="cannot certify primitive containment.*native arrows") as caught:
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arrows": [row]}, (0, 0, 0.1, 0.1))
    assert "outside crop" not in str(caught.value)


@pytest.mark.parametrize("magnitude,spacing_exponent", [
    (0.0, -149),
    (math.nextafter(0.0, math.inf), -149),
    (math.ldexp(1.0, -150), -149),  # Half a subnormal rounds to zero.
    (math.ldexp(1.0, -149), -149),
    (math.ldexp(1.0, -126), -149),  # Minimum normal float32.
    (math.ldexp(1.0, -125), -148),
    (math.nextafter(math.ldexp(1.0, -125), 0.0), -148),
    (0.5, -24),
    (1.0 - math.ldexp(1.0, -24), -24),  # Previous float32 before 1.
    (math.nextafter(1.0, 0.0), -23),  # Float64 below 1 rounds UP to float32 1.
    (1.0, -23),
    (math.nextafter(2.0, 0.0), -22),
    (2.0, -22),
    (0.1, -27),
    (0.1531, -26),
])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("larger_operand", ["actual", "boundary"])
def test_display_coordinate_spacing_rounds_float32_before_deriving_ulp(
    magnitude, spacing_exponent, sign, larger_operand,
):
    actual, boundary = (sign * magnitude, 0.0) if larger_operand == "actual" else (0.0, sign * magnitude)
    assert drawing._display_coordinate_ulp_m(actual, boundary) == math.ldexp(1.0, spacing_exponent)


@pytest.mark.parametrize("actual,boundary", [
    (False, 0.1), (0.1, True), ("0.1", 0.1), (0.1, None),
    (math.nan, 0.1), (0.1, math.inf), (-math.inf, 0.1),
    (1e40, 0.1), (0.1, -1e40),
    (float.fromhex("0x1.fffffep+127"), 0.1),
    (0.1, math.nextafter(float.fromhex("0x1.fffffep+127"), 0.0)),
])
def test_display_coordinate_spacing_refuses_invalid_overflow_or_infinite_successor(actual, boundary):
    with pytest.raises(ValueError, match="display precision|display spacing"):
        drawing._display_coordinate_ulp_m(actual, boundary)


def test_display_bbox_allowance_is_per_side_not_a_global_padding():
    crop = (0.125, 0.125, 0.25, 0.25)
    low_ulp, high_ulp = math.ldexp(1.0, -26), math.ldexp(1.0, -25)
    box = Box(crop[0] - low_ulp, crop[1] - low_ulp, crop[2] + high_ulp, crop[3] + high_ulp)
    comparisons = drawing._display_bbox_comparisons(box, crop)
    assert [item["coordinate"] for item in comparisons] == ["xmin", "ymin", "xmax", "ymax"]
    assert [item["tolerance_m"] for item in comparisons] == [low_ulp, low_ulp, high_ulp, high_ulp]
    assert [item["overrun_m"] for item in comparisons] == [low_ulp, low_ulp, high_ulp, high_ulp]
    assert all(item["accepted"] and item["precision_error"] is None for item in comparisons)


@pytest.mark.parametrize("side", range(4))
def test_display_bbox_each_side_rejects_two_float32_ulp(side):
    crop = (0.125, 0.125, 0.25, 0.25)
    coordinates = list(crop)
    ulp = math.ldexp(1.0, -26 if side < 2 else -25)
    coordinates[side] += (-2.0 if side < 2 else 2.0) * ulp
    comparisons = drawing._display_bbox_comparisons(Box(*coordinates), crop)
    assert comparisons[side]["overrun_m"] == 2.0 * ulp
    assert comparisons[side]["accepted"] is False
    assert all(item["accepted"] for index, item in enumerate(comparisons) if index != side)


def test_display_precision_allowance_does_not_change_exact_empty_ghost_anchors():
    crop = (0.0, 0.0, 0.1, 0.1)
    assert drawing._center_mark_bucket((math.nextafter(crop[2], math.inf), 0.05, 0), {}, crop) == "GHOST"
    for anchor_x in (crop[2], math.nextafter(crop[2], 0.0)):
        with pytest.raises(ValueError, match="empty native centre-mark display inside crop"):
            drawing._center_mark_bucket((anchor_x, 0.05, 0), {}, crop)


def test_display_containment_rejects_one_and_a_quarter_ulp_not_rounded_ulp_distance():
    crop = (0.0, 0.0, 0.125, 0.125)
    row = _native_line(0.1, 0.05, crop[2] + 1.25 * math.ldexp(1.0, -26), 0.05)
    evidence = []
    with pytest.raises(ValueError, match="lines #0 outside crop beyond one float32 ULP"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, crop, primitive_evidence=evidence)
    upper_x = evidence[0]["comparisons"][2]
    assert upper_x["overrun_m"] == 1.25 * math.ldexp(1.0, -26)
    assert upper_x["tolerance_m"] == math.ldexp(1.0, -26)
    assert upper_x["accepted"] is False


def test_display_containment_rejects_two_subnormal_steps_outside_zero_boundary():
    crop = (0.0, 0.0, 0.1, 0.1)
    row = _native_line(0.0, 0.05, -math.ldexp(1.0, -148), 0.05)
    evidence = []
    with pytest.raises(ValueError, match="lines #0 outside crop beyond one float32 ULP"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, crop, primitive_evidence=evidence)
    lower_x = evidence[0]["comparisons"][0]
    assert lower_x["overrun_m"] == math.ldexp(1.0, -148)
    assert lower_x["tolerance_m"] == math.ldexp(1.0, -149)
    assert lower_x["accepted"] is False


@pytest.mark.parametrize("label,text_position,arrow_tips,connector", [
    ("dt-cylinder-gear/FaceWidth", (0.225, 0.220),
     ((0.2102924, 0.220), (0.2057924, 0.220)),
     [0.0, 0.0, 0.0, 0.0, 0.2080424, 0.220, 0.0464999, 0.2127281, 0.2172219, 0.0]),
    ("dt-crank-handle-pivot-screw/ReliefDia", (0.1155, 0.144),
     ((0.08575, 0.162225), (0.08575, 0.167775)),
     [0.0, 0.0, 0.0, 0.0, 0.08575, 0.165, -0.0003, 0.0908542, 0.138417, 0.0]),
    ("sm-gooseneck-spring-screw/ReliefDia", (0.23005, 0.1495),
     ((0.202, 0.1606), (0.202, 0.1694)),
     [0.0, 0.0, 0.0, 0.0, 0.202, 0.165, -0.0004, 0.2028181, 0.143917, 0.0]),
    ("fr-top-frame/PocketRise", (0.0422, 0.0785),
     ((0.070, 0.091875), (0.070, 0.099875)),
     [0.0, 0.0, 0.0, 0.0, 0.070, 0.095875, 0.107, 0.0656719, 0.0673875, -0.0]),
])
def test_r26_actual_four_native_linear_offset_samples_keep_dimension_midpoint_attachment(
    label, text_position, arrow_tips, connector,
):
    # Actual rows from C:/farm-runs/ms-stop/
    # 20261012T055029190Z-4b5f6c488dce44489a438169e748265c.out/reports/layout-audit/
    # <label before slash>.json. PocketRise is on a later sheet, Drawing View11.
    terminal = tuple(connector[4:6])
    midpoint = tuple((a + b) / 2.0 for a, b in zip(*arrow_tips, strict=True))
    assert terminal == pytest.approx(midpoint, abs=1e-12), label
    assert math.dist(terminal, text_position) > 0.001
    assert tuple(connector[7:9]) != terminal


def test_least_tip_land_is_the_basic_land_shortened_by_the_taper_tilted_into_the_zone():
    # Independent of the vertex search: the land on its zone's outside limit,
    # the top arc on its zone's inside one (the former BASICs, which the
    # mid-zone nominal sits half the zone in from, #2144 item 10.3); the taper
    # keeps its bottom end on its outside limit and swings its foot to its
    # inside one, so the land ends where that tilted taper crosses it.
    top, tip, bottom = drawing._TOP, drawing._TIP, drawing._BOTTOM
    half = ch_rocker_arm_spec.BOTTOM_EDGE_BAND[0]
    zone = half - ch_rocker_arm_spec.BOTTOM_EDGE_BAND[1]
    interior = ((top[0] + bottom[0]) / 2.0, (top[1] + bottom[1]) / 2.0)

    def inward(start, end):
        dx, dy = end[0] - start[0], end[1] - start[1]
        n = (-dy / math.hypot(dx, dy), dx / math.hypot(dx, dy))
        side = (interior[0] - start[0]) * n[0] + (interior[1] - start[1]) * n[1]
        return n if side > 0.0 else (-n[0], -n[1])

    land_n, taper_n = inward(top, tip), inward(tip, bottom)
    p0 = (top[0] - half * land_n[0], top[1] - half * land_n[1])
    p1 = (tip[0] - half * land_n[0], tip[1] - half * land_n[1])
    foot = (tip[0] + half * taper_n[0], tip[1] + half * taper_n[1])
    end = (bottom[0] - half * taper_n[0], bottom[1] - half * taper_n[1])
    ux, uy = p1[0] - p0[0], p1[1] - p0[1]
    ex, ey = end[0] - foot[0], end[1] - foot[1]
    s = ((foot[0] - p0[0]) * ey - (foot[1] - p0[1]) * ex) / (ux * ey - uy * ex)
    land_end = (p0[0] + s * ux, p0[1] + s * uy)
    fx, fy = p0[0], p0[1] - rocker_interface.CENTER_Y
    a, b = ux * ux + uy * uy, 2.0 * (fx * ux + fy * uy)
    radius = ch_rocker_arm_spec.R_TOP + half
    root = math.sqrt(b * b - 4.0 * a * (fx * fx + fy * fy - radius**2))
    u = min(((-b + root) / (2.0 * a), (-b - root) / (2.0 * a)), key=abs)
    tilted = math.dist((p0[0] + u * ux, p0[1] + u * uy), land_end)
    assert drawing._least_tip_land_mm() == pytest.approx(tilted, abs=1e-9)
    assert drawing.TIP_LAND_LEAST_MM == 4.965
    assert 0.0 < drawing.TIP_LAND_LEAST_MM <= drawing._least_tip_land_mm()
    # A parallel shift of the taper (zone / sin of the land-taper angle) is
    # milder than the tilt; the land never lengthens past its basic as worst.
    tx, ty = bottom[0] - tip[0], bottom[1] - tip[1]
    cos_angle = abs(ux * tx + uy * ty) / (math.hypot(ux, uy) * math.hypot(tx, ty))
    parallel = ch_rocker_arm_spec.TIP_FACE - zone / math.sqrt(1.0 - cos_angle**2)
    assert drawing.TIP_LAND_LEAST_MM < parallel < ch_rocker_arm_spec.TIP_FACE
