"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import solidworks_mcp.adapters

import _config
import _drawing_attachment
import _drawing_edge_dimensions
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_edges import ViewEdge, ViewEdges
from _hole_spec import blind_cut_dia_mm
import build_sm_summing_lever as lever_build
import draw_sm_summing_lever as drawing
from _cone_axis_constants import SUMMING_Z
import rocker_bank_layout
import sm_summing_lever_notes as notes
import sm_summing_lever_spec
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1


def test_anchor_seats_are_the_purchased_anchors_own_threads() -> None:
    """Both lower spring anchors are purchased eyebolts threaded straight into
    this casting -- there is no nut -- so a seat that does not match its
    anchor, or a boss its anchor cannot span, is an unassemblable part."""
    plate, boss = sm_summing_lever_spec.HOLE_SPEC, sm_summing_lever_spec.COUNTER_HOLE_SPEC
    assert (plate.kind, plate.end) == ("tapped", "through_all")
    assert (boss.kind, boss.end) == ("tapped", "through_all")
    assert plate.size == ANCHOR_9489T111.thread_size
    assert boss.size == ANCHOR_9490T1.thread_size
    # The spring anchor spans the whole uniform coefficient plate.
    assert ANCHOR_9489T111.thread_length_mm > sm_summing_lever_spec.COEFFICIENT_T
    assert ANCHOR_9490T1.thread_length_mm >= sm_summing_lever_spec.ANCHOR_H
    # ...and each tap must fit the feature it passes through.
    assert blind_cut_dia_mm(boss) < 2.0 * sm_summing_lever_spec.ANCHOR_R
    assert blind_cut_dia_mm(plate) < sm_summing_lever_spec.HOLE_EDGE_OFFSET


def test_spring_hole_column_rides_the_channel_arm_plane() -> None:
    """Each anchor tap is coaxial with its channel spring at z_j + ARM_MID_DZ
    (the cam plane), in the lever's frame (machine z less SUMMING_Z). The spec
    restates the offset (its closure must stay config-free); this pins it."""
    spec = sm_summing_lever_spec
    assert spec.HOLE_Z_OFFSET == pytest.approx(rocker_bank_layout.ARM_MID_DZ, abs=1e-12)
    z0 = _config.machine("channels", "station_z0_mm")
    pitch = _config.machine("channels", "station_pitch_mm")
    assert spec.CHANNEL_Z0 == pytest.approx(z0 - SUMMING_Z, abs=1e-9)
    assert spec.CHANNEL_PITCH == pytest.approx(pitch, abs=1e-9)
    for j in (0, spec.HOLE_COUNT - 1):
        hole_z = spec.CHANNEL_Z0 + spec.CHANNEL_PITCH * j + spec.HOLE_Z_OFFSET
        assert hole_z + SUMMING_Z == pytest.approx(rocker_bank_layout.hub_mid_z(j))
    assert spec.HOLE_END_OFFSET_FIRST == pytest.approx(5.572, abs=5e-4)
    assert spec.HOLE_END_OFFSET_LAST == pytest.approx(12.755, abs=5e-4)
    # drawing-guidelines.md rule 17 (walls and webs): the j=0 tap keeps a 2.0 wall to the -Z plate end.
    tap_r = blind_cut_dia_mm(spec.HOLE_SPEC) / 2.0
    assert spec.HOLE_END_OFFSET_FIRST - tap_r >= 2.0


def _line(start, end):
    return ViewEdge(object(), (start, end), None, None)


def test_end_face_edge_rejects_inboard_flange_and_hidden_underside() -> None:
    """Datum B and the start-Z BASIC belong to the physical +Z end face."""
    spec = sm_summing_lever_spec
    z = spec.PLATE_L / 2.0
    top = _line((0.0, 15.24, z), (30.0, 6.0, z))
    flange = _line((0.0, 15.24, z - 5.08), (30.0, 6.0, z - 5.08))
    underside = _line((30.0, spec.COEFFICIENT_BOTTOM_Y, z), (0.0, -15.24, z))
    plate_end = _line(
        (spec.RIB_REACH, spec.COEFFICIENT_TOP_Y, z),
        (spec.PLATE_W, spec.COEFFICIENT_TOP_Y, z),
    )
    edges = ViewEdges(label="plan", edges=(flange, underside, plate_end, top))
    assert drawing._end_face_edge(edges, x_mm=10.0) is top
    assert drawing._end_face_edge(edges, x_mm=40.0) is plate_end
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(ViewEdges(label="plan", edges=(flange, underside)), x_mm=10.0)
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(ViewEdges(label="duplicate", edges=(top, top)), x_mm=10.0)


def _dimension(mm: float, attached: tuple[object, ...]):
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: attached,
        GetAttachedEntityTypes=lambda: tuple(1 for _ in attached),
        IsDangling=lambda: False,
    )
    return SimpleNamespace(
        GetDimension2=lambda _index: SimpleNamespace(SystemValue=mm / 1000.0),
        GetAnnotation=lambda: annotation,
    )


@pytest.fixture
def identity(monkeypatch):
    monkeypatch.setattr(_drawing_attachment, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        solidworks_mcp.adapters.sw_type_info, "early_bound_or_flag", lambda value, *_args: value
    )
    return SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))


def test_pitch_proof_rejects_an_equal_pitch_between_other_holes(identity) -> None:
    """Nineteen hole pairs measure CHANNEL_PITCH: the value cannot tell the
    seed/second pair from the next one down, only the attached rims can."""
    seed, second, third = object(), object(), object()
    pitch = sm_summing_lever_spec.CHANNEL_PITCH
    assert assert_dimension_measures(
        identity, _dimension(pitch, (second, seed)), expected_mm=pitch,
        label="spring-hole pitch", entities=(seed, second),
    ) == pytest.approx(pitch)
    with pytest.raises(RuntimeError, match=r"unmatched picks=\[0\]") as info:
        assert_dimension_measures(
            identity, _dimension(pitch, (second, third)), expected_mm=pitch,
            label="spring-hole pitch", entities=(seed, second),
        )
    assert "not the dimension between its named entities" in str(info.value)
    # One entity attached twice is not a span between two.
    with pytest.raises(RuntimeError, match=r"unmatched picks=\[1\]"):
        assert_dimension_measures(
            identity, _dimension(pitch, (seed, seed)), expected_mm=pitch,
            label="spring-hole pitch", entities=(seed, second),
        )
    # A third attachment or a dangling leader is not the named span either.
    with pytest.raises(RuntimeError, match=r"extra attachments=1"):
        assert_dimension_measures(
            identity, _dimension(pitch, (seed, second, third)), expected_mm=pitch,
            label="spring-hole pitch", entities=(seed, second),
        )
    # Identity passes, the value still has to match.
    with pytest.raises(RuntimeError, match=r"measures 7\.0565 mm, expected 8\.43"):
        assert_dimension_measures(
            identity, _dimension(pitch, (seed, second)), expected_mm=8.43,
            label="spring-hole start Z", entities=(seed, second),
        )


def test_bracket_receiver_retains_the_blind_native_contract_and_final_proof() -> None:
    import build_sm_summing_lever as part
    import magnifying_bracket_joint_layout as joint
    assert part.LEVER_HOLE_POINTS is joint.LEVER_HOLE_POINTS
    assert part.TAP_SPEC is joint.TAP_SPEC
    assert (part.TAP_SPEC.kind, part.TAP_SPEC.end) == ("tapped_bottoming", "blind")
    # Native depth/band behavior is exercised by the adapter tests below.
    # The process line leads the callout; the native size starts the next row.
    assert notes.BRACKET_TAP_CALLOUT_PROCESS.endswith("\n")
    assert notes.BRACKET_SCREW_NUMBER in notes.BRACKET_TAP_CALLOUT_PROCESS
    assert part.TAP_SPEC.size == "#2-56"
    assert part.TAP_SPEC.depth_mm == 6.50
    assert part.TAP_SPEC.overrides_mm["ThreadDepth"] == 4.95
    assert joint.THREAD_DEPTH_BAND == 0.05
    assert joint.DRILL_DEPTH_DEVIATIONS == (-0.51, 0.51)  # ordinary .XX width
    # The -Z rib's depth rides the title block (no native band of its own).
    assert joint.RIB_DEPTH_BAND == joint.LINEAR_BAND
    assert not hasattr(joint, "RECEIVER_DIMENSION_BANDS")
    assert "PlateThickness" in drawing.BACK_KEEP
    assert "RibDepth" in drawing.TOP_KEEP
    order = [_call_name(call) for call in _calls_in_order(_builder_function("build"))]
    bands = order.index("_receiver_model_bands")
    coordinates = order.index("_receiver_coordinate_dimensions")
    saved = order.index("save_part_and_images")
    assert bands < coordinates < saved
    assert "volume_check" in order[coordinates:saved]


def test_receiver_upper_stop_keeps_drill_inside_the_proven_rib() -> None:
    """Thickening downward does not remove the receiver's upper-wall limit."""
    import magnifying_bracket_joint_layout as joint

    spec = sm_summing_lever_spec
    drill_radius_max = (joint.TAP_DRILL_DIA + joint.DRILLED_DIAMETER_PLUS) / 2.0
    for x, _y, _z in joint.LEVER_HOLE_POINTS:
        assert x - joint.POSITION_BAND - drill_radius_max > spec.CYL_R
        assert x + joint.POSITION_BAND + drill_radius_max < spec.RIB_REACH
    assert joint.DRILL_POINT_RIB_MARGIN_MIN > 0.0
    upper_plate_wall = (
        spec.COEFFICIENT_TOP_Y - joint.LINEAR_BAND - joint.POSITION_BAND
        - drill_radius_max - joint.DRILL_WANDER_MAX
    )
    assert upper_plate_wall < 1.5


def test_body_end_span_does_not_read_as_the_overall() -> None:
    """The unchanged stubs extend beyond the dimensioned body end faces."""
    plate_length = notes.DIMENSION_CALLOUTS_BELOW["PlateLength"]
    assert " ".join(plate_length.split()) == "BODY END FACES"
    assert "PlateLength" in drawing.TOP_KEEP
    x, _ = drawing.TOP_KEEP["PlateLength"]
    widest = max(len("152.40"), *map(len, plate_length.split("\n")))
    assert x + _CHAR_M * widest / 2.0 < 0.4191 - 0.002  # under the right border


def test_receiver_rim_scan_uses_back_entry_face() -> None:
    import magnifying_bracket_joint_layout as joint
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append((center, radius, axis))
        return SimpleNamespace(edge=object())

    edges = SimpleNamespace(circle_at=circle_at)
    assert len(drawing._mounting_rims(edges)) == len(joint.LEVER_HOLE_POINTS)
    assert [call[0] for call in calls] == list(joint.LEVER_HOLE_POINTS)
    assert all(call[1] == joint.TAP_DRILL_DIA / 2.0 for call in calls)
    assert [call[2] for call in calls] == [(0.0, 0.0, 1.0)] * len(calls)


def test_view_f_axis_centreline_extends_beyond_the_receiver_row() -> None:
    """The receiver row and hex axis share a line spanning both tap centres."""
    import magnifying_bracket_joint_layout as joint

    spec = sm_summing_lever_spec
    assert all(point[1] == 0.0 for point in joint.LEVER_HOLE_POINTS)
    station = drawing.RECEIVER_AXIS_STATION_MM
    overrun = drawing.RECEIVER_AXIS_OVERRUN_MM
    outer_tap = max(point[0] for point in joint.LEVER_HOLE_POINTS)
    assert outer_tap + joint.TAP_DRILL_DIA / 2.0 < spec.RIB_REACH
    assert spec.RIB_REACH < station
    assert station + overrun < spec.PLATE_W
    assert overrun > 0.0




@pytest.mark.parametrize("placed", [2, 4])  # the farm places views in HLR (2)
def test_newly_placed_views_do_not_pass_through_hidden_lines_visible(
    monkeypatch, placed
) -> None:
    """#1591: the bracket taps' label grew on sheet 1 at the greyed pass, on
    some builds only."""

    class View:
        def __init__(self) -> None:
            self.mode = placed
            self.sets: list[int] = []

        def GetDisplayMode2(self) -> int:
            return self.mode

        def SetDisplayMode4(self, use_parent, mode, faceted, edges, quality) -> bool:
            self.sets.append(mode)
            changed = mode != self.mode
            self.mode = mode
            return changed  # a same-mode set is a no-op that returns False

        def GetName2(self) -> str:
            return "Drawing View2"

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    view = View()
    drawing._hidden_lines_removed_without_greyed_pass(view)
    assert view.sets == [2]  # swHIDDEN only, never swHIDDEN_GREYED (1)
    assert view.mode == 2




def test_marked_dimensions_are_all_placed_and_their_callouts_land() -> None:
    keeps = {
        **drawing.FRONT_KEEP,
        **drawing.DETAIL_KEEP,
        **drawing.TOP_KEEP,
        **drawing.BACK_KEEP,
    }
    placed = [
        *drawing.FRONT_KEEP,
        *drawing.DETAIL_KEEP,
        *drawing.TOP_KEEP,
        *drawing.BACK_KEEP,
    ]
    assert len(placed) == len(keeps), "a dimension is kept in two views"
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert marked <= set(keeps)
    for feature, names in notes.DRAWING_DIMENSIONS.items():
        assert drawing.DIMENSIONS_BY_FEATURE[feature] == names
    above = set(notes.DIMENSION_CALLOUTS_ABOVE)
    below = set(notes.DIMENSION_CALLOUTS_BELOW)
    assert not above & below
    assert above | below <= set(keeps)
    for name, _prefix in notes.DIMENSION_PREFIXES:
        assert name in notes.DRAWING_DIMENSIONS


def test_the_knife_edge_prints_its_ridge_and_flanks_to_the_sides(monkeypatch) -> None:
    """Code review C09 (owner ruling T1): Detail D holds the ridge sharp
    4.040 +/-0.05 from each side face and each upper flank 122.4 +/-0.5 deg
    to its side face, on both stubs; the width is a reference."""
    spec = sm_summing_lever_spec
    knife = notes.DRAWING_DIMENSIONS["KnifeEnvelopeReference"]
    assert knife == {"HexWidth", "HexHeight", "RidgeFromLeft", "RidgeFromRight", "FlankToSide"}
    assert set(knife) <= set(drawing.DETAIL_KEEP)
    assert "KnifeRidgeRadius" in drawing.DETAIL_KEEP
    prefixes = notes.DIMENSION_PREFIXES
    assert prefixes[("KnifeEnvelopeReference", "HexWidth")] == "2X ("
    assert prefixes[("KnifeEnvelopeReference", "RidgeFromLeft")] == "2X "
    assert prefixes[("KnifeEnvelopeReference", "RidgeFromRight")] == "2X "
    assert prefixes[("KnifeEnvelopeReference", "FlankToSide")] == "4X "
    # Each band on the knife edge names its seat, as the vertex height does
    # (machinist review 20261018), and the pair states the symmetry.
    seat_bands = ("RidgeFromLeft", "RidgeFromRight", "FlankToSide", "HexHeight")
    for name in seat_bands:
        callout = notes.DIMENSION_CALLOUTS_BELOW[name]
        assert notes.KNIFE_MOUNT_NUMBER in callout, name
        assert "MILL" not in callout and "PASS" not in callout, name
    pair = " ".join(
        " ".join(notes.DIMENSION_CALLOUTS_BELOW[name].split())
        for name in ("RidgeFromLeft", "RidgeFromRight")
    )
    assert "SYMMETRIC TO SIDES" in pair and "BOTH STUBS" in pair
    # The model holds the sides in one plane; the print states no limitless
    # coplanarity requirement (machinist review bdc033f13).
    assert "PLANE" not in pair
    every_callout = {**notes.DIMENSION_CALLOUTS_ABOVE, **notes.DIMENSION_CALLOUTS_BELOW}
    assert "HexWidth" not in every_callout
    assert (spec.RIDGE_FROM_SIDE, spec.RIDGE_FROM_SIDE_TOL) == (4.040, 0.05)
    assert (spec.KNIFE_FLANK_TO_SIDE_DEG, spec.KNIFE_FLANK_TO_SIDE_TOL_DEG) == (122.4, 0.5)
    assert not hasattr(spec, "RIDGE_ANGLE_TOL_DEG")
    assert not hasattr(spec, "KNIFE_SHOULDER_RISE")

    calls = []
    for name in (
        "set_dimension_display_precision",
        "set_dimension_symmetric_tolerance",
        "set_dimension_symmetric_angular_tolerance",
        "set_dimension_prefix",
        "mark_dimensions_for_drawing",
    ):
        monkeypatch.setattr(
            lever_build,
            name,
            lambda adapter, *args, _name=name, **kwargs: calls.append((_name, args, kwargs)),
        )
    monkeypatch.setattr(
        lever_build, "_hex_width_reference", lambda adapter: calls.append(("reference", (), {}))
    )
    lever_build._drawing_dimension_contract(object())
    feature = "KnifeEnvelopeReference"
    assert ("set_dimension_display_precision", (feature, "FlankToSide", 1), {}) in calls
    for name in ("HexWidth", "HexHeight", "RidgeFromLeft", "RidgeFromRight"):
        assert ("set_dimension_display_precision", (feature, name, 3), {}) in calls
    for name in ("RidgeFromLeft", "RidgeFromRight"):
        assert ("set_dimension_symmetric_tolerance", (feature, name, 0.05), {}) in calls
    assert (
        "set_dimension_symmetric_angular_tolerance",
        (feature, "FlankToSide", 0.5),
        {"require_driven": True},
    ) in calls
    # HexWidth is never toleranced: it reads back as the reference.
    assert ("reference", (), {}) in calls
    assert not any(
        name.startswith("set_dimension_symmetric") and args[1] == "HexWidth"
        for name, args, _ in calls
    )
    # The model sketch's angle is the flank-to-side angle the print rounds.
    assert round(180.0 - spec.RIDGE_ANGLE_DEG / 2.0, 1) == spec.KNIFE_FLANK_TO_SIDE_DEG


def _builder_function(name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(Path(lever_build.__file__).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"build_sm_summing_lever has no {name}()")


def _calls_in_order(node: ast.AST) -> list[ast.Call]:
    calls = [call for call in ast.walk(node) if isinstance(call, ast.Call)]
    return sorted(calls, key=lambda call: (call.lineno, call.col_offset))


def _call_name(call: ast.Call) -> str:
    func = call.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


def test_both_knife_stubs_are_one_prism_read_back_coplanar() -> None:
    """Code review C09: the stubs are ONE sketch extruded mid-plane through
    the body, so each side face of the -Z stub is the +Z stub's plane by
    construction, and the build reads that back once the model is final."""
    assert not hasattr(lever_build, "_hex_collar")
    order = [_call_name(call) for call in _calls_in_order(_builder_function("build"))]
    for name in ("_hex_knife", "_knife_stub_reference", "_assert_knife_sides_coplanar"):
        assert order.count(name) == 1, name
    knife = order.index("_hex_knife")
    reference = order.index("_knife_stub_reference")
    readback = order.index("_assert_knife_sides_coplanar")
    assert knife < reference < readback
    assert "volume_check" in order[reference:readback]

    prism = [_call_name(call) for call in _calls_in_order(_builder_function("_hex_knife"))]
    assert prism.count("create_sketch") == 1
    assert prism.count("create_extrusion") == 1
    assert "extrude_at_offset" not in prism
    [params] = [
        call
        for call in _calls_in_order(_builder_function("_hex_knife"))
        if _call_name(call) == "ExtrusionParameters"
    ]
    keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in params.keywords}
    assert keywords == {"depth": "2.0 * HEX_Z_OUTER", "both_directions": "True"}


def test_the_knife_prism_merges_into_the_pivot_between_the_stubs() -> None:
    """One prism leaves the solid unchanged only if the hexagon lies inside
    the solid cylinder between the body ends and each stub keeps its own
    21.717 overhang."""
    spec = sm_summing_lever_spec
    w2, h2, h4 = spec.HEX_W / 2.0, spec.HEX_H / 2.0, spec.HEX_H / 4.0
    vertices = [(0.0, h2), (-w2, h4), (-w2, -h4), (0.0, -h2), (w2, -h4), (w2, h4)]
    assert max(math.hypot(x, y) for x, y in vertices) < spec.CYL_R
    assert spec.HEX_Z_INNER == spec.PLATE_L / 2.0
    assert spec.HEX_Z_OUTER - spec.HEX_Z_INNER == pytest.approx(spec.HEX_DEPTH)
    for name in ("HEX_W", "HEX_H", "HEX_DEPTH", "HEX_Z_INNER", "HEX_Z_OUTER", "CYL_R"):
        assert getattr(lever_build, name) == getattr(spec, name), name
    assert notes.DRAWING_DIMENSIONS["KnifeStubReference"] == {"KnifeStubLength"}
    assert notes.DIMENSION_PREFIXES[("KnifeStubReference", "KnifeStubLength")] == "2X "


def _knife_faces(shift_minus_z_side_m: float = 0.0) -> list[SimpleNamespace]:
    """Fake IFace2s for the HexKnife prism: per stub, its six lateral faces
    (split once, as a boolean may), its outboard end and a ridge round."""
    spec = sm_summing_lever_spec
    w2, h2, h4 = spec.HEX_W / 2000.0, spec.HEX_H / 2000.0, spec.HEX_H / 4000.0
    vertices = [(0.0, h2), (-w2, h4), (-w2, -h4), (0.0, -h2), (w2, -h4), (w2, h4)]

    def face(normal, root, z_range, *, plane: bool = True) -> SimpleNamespace:
        surface = SimpleNamespace(
            IsPlane=lambda: plane, PlaneParams=(*normal, *root)
        )
        return SimpleNamespace(
            Normal=normal,
            GetSurface=lambda: surface,
            GetBox=lambda: (-w2, -h2, z_range[0], w2, h2, z_range[1]),
        )

    faces = []
    for sign in (1.0, -1.0):
        inner, outer = sign * spec.HEX_Z_INNER / 1000.0, sign * spec.HEX_Z_OUTER / 1000.0
        mid = (inner + outer) / 2.0
        for index, (a, b) in enumerate(zip(vertices, vertices[1:] + vertices[:1])):
            # The chain runs CCW, so (dy, -dx) points out of the prism.
            nx, ny = b[1] - a[1], a[0] - b[0]
            length = math.hypot(nx, ny)
            normal = (nx / length, ny / length, 0.0)
            root = list(a) + [mid]
            if sign < 0.0 and index == 1:  # the -Z stub's -X side face
                root[0] -= shift_minus_z_side_m
            for span in ((inner, mid), (mid, outer)):
                faces.append(face(normal, tuple(root), sorted(span)))
        faces.append(face((0.0, 0.0, sign), (0.0, 0.0, outer), (outer, outer)))
        faces.append(face((0.0, 1.0, 0.0), (0.0, h2, mid), sorted((inner, outer)), plane=False))
    return faces


def _knife_adapter(faces: list[SimpleNamespace]) -> SimpleNamespace:
    feature = SimpleNamespace(GetFaces=lambda: faces)
    model = SimpleNamespace(FeatureByName=lambda name: feature if name == "HexKnife" else None)
    return SimpleNamespace(currentModel=model)


def test_the_coplanarity_readback_passes_one_prism_and_fails_a_stepped_side() -> None:
    lever_build._assert_knife_sides_coplanar(_knife_adapter(_knife_faces()))
    stepped = _knife_adapter(_knife_faces(shift_minus_z_side_m=1e-5))
    with pytest.raises(RuntimeError, match="not one plane each"):
        lever_build._assert_knife_sides_coplanar(stepped)
    # Within KNIFE_SIDE_PLANE_TOL (1e-6 m, the API's unit) the planes are one.
    lever_build._assert_knife_sides_coplanar(
        _knife_adapter(_knife_faces(shift_minus_z_side_m=0.5e-6))
    )


def test_the_between_stub_ridge_bound_holds_only_with_the_sides_in_one_plane() -> None:
    """Each ridge is 4.040 +/-0.05 from its stub's sides.  Only with both
    stubs' sides the same planes does that hold the two ridges within 0.10
    of each other (0.077 of hook-arm spread over the hole column); the bound,
    the callout and the one-prism build stand or fall together."""
    spec = sm_summing_lever_spec
    assert spec.KNIFE_STUB_RIDGE_OFFSET_MAX == pytest.approx(0.10)
    assert spec.KNIFE_STUB_RIDGE_OFFSET_MAX == 2.0 * spec.RIDGE_FROM_SIDE_TOL
    assert spec.KNIFE_RIDGE_CONTACT_SPAN == pytest.approx(spec.HEX_Z_INNER + spec.HEX_Z_OUTER)
    assert spec.KNIFE_HOOK_ARM_SPREAD_MAX == pytest.approx(0.077, abs=5e-4)
    callout = " ".join(notes.DIMENSION_CALLOUTS_BELOW["RidgeFromRight"].split())
    assert "BOTH STUBS" in callout and "PLANE" not in callout
    assert notes.DIMENSION_PREFIXES[("KnifeEnvelopeReference", "RidgeFromLeft")] == "2X "
    assert lever_build.KNIFE_SIDE_PLANE_TOL == 1e-6
    assert "_assert_knife_sides_coplanar" in [
        _call_name(call) for call in _calls_in_order(_builder_function("build"))
    ]
    assert not hasattr(lever_build, "_hex_collar")


# Detail D's text blocks as SolidWorks prints them (3.5 mm text, measured on
# the stack r4 sheet): 2.5 mm a character, 5.5 mm a line, the whole block
# (value and callout lines) centred on its keep, and a linear dimension's line
# under the block's bottom line, 2.8 mm under the keep for one line.
_CHAR_M = 0.0025
_LINE_M = 0.0055
_ONE_LINE_DROP_M = 0.0028
_BORDER_TOP_M = 0.2794 - 0.0127
_BORDER_LEFT_M = 0.0127


def _detail_block(name: str, value: str) -> tuple[float, float, float, float, int]:
    """(left, right, bottom, top, lines) of a Detail D dimension's text."""
    lines = [value, *notes.DIMENSION_CALLOUTS_BELOW.get(name, "").split("\n")]
    lines = [line for line in lines if line]
    x, y = drawing.DETAIL_KEEP[name]
    half_w = _CHAR_M * max(map(len, lines)) / 2.0
    half_h = _LINE_M * len(lines) / 2.0
    return x - half_w, x + half_w, y - half_h, y + half_h, len(lines)


def _dimension_line_y(name: str, lines: int) -> float:
    return drawing.DETAIL_KEEP[name][1] - _ONE_LINE_DROP_M - _LINE_M * (lines - 1) / 2.0


def _knife_envelope_model_owners():
    """Read the native reference's endpoint owners, not left/right name guesses."""
    lines, spans, angle_lines = {}, {}, None
    pending_span = None

    def endpoint(reference):
        assert isinstance(reference, ast.JoinedStr) and len(reference.values) == 2
        variable, suffix = reference.values
        assert isinstance(variable, ast.FormattedValue)
        assert isinstance(variable.value, ast.Name) and isinstance(suffix, ast.Constant)
        return lines[variable.value.id][{".start": 0, ".end": 1}[suffix.value]]

    for statement in _builder_function("_knife_envelope_reference").body:
        calls = _calls_in_order(statement)
        authored_lines = [call for call in calls if _call_name(call) == "add_line"]
        if authored_lines:
            assert isinstance(statement, ast.Assign) and len(authored_lines) == 1
            [target] = statement.targets
            assert isinstance(target, ast.Name)
            # These are the reference's actual constant HEX_W/HEX_H arithmetic,
            # not executing the builder or substituting screen-side coordinates.
            coordinates = tuple(
                float(eval(
                    compile(ast.Expression(argument), "<knife endpoint>", "eval"),
                    {"__builtins__": {}},
                    {"HEX_W": sm_summing_lever_spec.HEX_W, "HEX_H": sm_summing_lever_spec.HEX_H},
                ))
                for argument in authored_lines[0].args
            )
            assert len(coordinates) == 4
            lines[target.id] = (coordinates[:2], coordinates[2:])
        for call in calls:
            name = _call_name(call)
            if name == "dimension_between":
                pending_span = (endpoint(call.args[1]), endpoint(call.args[2]))
            elif name == "record" and isinstance(call.args[0], ast.Constant):
                mark = call.args[0].value
                if mark in ("RidgeFromLeft", "RidgeFromRight"):
                    assert pending_span is not None
                    spans[mark] = pending_span
            elif name == "add_angular_reference_dimension":
                angle_lines = tuple(lines[argument.id] for argument in call.args[1:3])
    assert set(spans) == {"RidgeFromLeft", "RidgeFromRight"}
    assert angle_lines is not None
    return spans, angle_lines


def test_back_projected_knife_detail_uses_model_owned_spans_and_exterior_angle() -> None:
    """Analytical Back-projected layout budget, not proof of native annotation ink."""
    spec = sm_summing_lever_spec
    assert drawing.DETAIL_SCALE == (10.0, 1.0)
    scale = drawing.DETAIL_SCALE[0] / 1000.0
    cx, cy = drawing.DETAIL_CENTER
    fence = drawing.DETAIL_RADIUS_MM * scale
    hw = spec.HEX_W / 2.0 * scale
    spans, angle_lines = _knife_envelope_model_owners()
    [model_vertex] = set(spans["RidgeFromLeft"]) & set(spans["RidgeFromRight"])
    [model_shoulder] = set(angle_lines[0]) & set(angle_lines[1])
    assert model_vertex in angle_lines[0]
    [model_side_end] = set(angle_lines[1]) - {model_shoulder}

    def project(point):
        # D derives from unrotated *Back: +X goes left and +Y goes up.
        return cx - point[0] * scale, cy + point[1] * scale

    vertex, shoulder, side_end = map(project, (model_vertex, model_shoulder, model_side_end))
    assert shoulder[0] < vertex[0]  # the model's +X flank, not its opposite
    assert spec.HEX_H / 2.0 < drawing.DETAIL_RADIUS_MM - 0.5
    blocks = {
        "HexWidth": _detail_block("HexWidth", "2X (8.080)"),
        "HexHeight": _detail_block("HexHeight", "2X 10.268"),
        "RidgeFromLeft": _detail_block("RidgeFromLeft", "2X 4.040 ±0.05"),
        "RidgeFromRight": _detail_block("RidgeFromRight", "2X 4.040 ±0.05"),
        "FlankToSide": _detail_block("FlankToSide", "4X 122.4° ±0.5°"),
        "KnifeRidgeRadius": _detail_block("KnifeRidgeRadius", "2X R0.1 MAX"),
    }
    for name, (left, _right, _bottom, top, _lines) in blocks.items():
        assert top < _BORDER_TOP_M - 0.004, name
        assert left > _BORDER_LEFT_M + 0.002, name
    pair_lines = {
        name: _dimension_line_y(name, blocks[name][4]) for name in spans
    }
    pair_line = pair_lines["RidgeFromLeft"]
    assert pair_line == pytest.approx(pair_lines["RidgeFromRight"], abs=2e-4)
    assert pair_line > cy + fence + 0.004
    for name, model_span in spans.items():
        projected_x = [project(point)[0] for point in model_span]
        outer = project(next(point for point in model_span if point != model_vertex))[0]
        if outer > vertex[0]:
            assert blocks[name][0] > max(projected_x) + 0.002, name
        else:
            assert blocks[name][1] < min(projected_x) - 0.002, name

    angle_x, angle_y = drawing.DETAIL_KEEP["FlankToSide"]
    direction = math.degrees(math.atan2(angle_y - shoulder[1], angle_x - shoulder[0])) % 360.0
    outside_side = math.degrees(math.atan2(
        shoulder[1] - side_end[1], shoulder[0] - side_end[0],
    )) % 360.0
    outside_flank = math.degrees(math.atan2(
        shoulder[1] - vertex[1], shoulder[0] - vertex[0],
    )) % 360.0
    assert outside_side < direction < outside_flank
    angle_radius = math.dist((angle_x, angle_y), shoulder)
    # The entire exterior arc stays right of the height annotation's column
    # and below the shared ridge line; an apparently exterior text anchor alone
    # would miss the long arc's collision with the height text.
    assert shoulder[0] - angle_radius > blocks["HexHeight"][1] + 0.002
    assert shoulder[1] + angle_radius < pair_line - 0.002
    # Its complete text rectangle stays outside the actual sloping flank,
    # even though its right edge can lie to the right of the shoulder itself.
    angle_left, angle_right, angle_bottom, angle_top, _ = blocks["FlankToSide"]
    assert shoulder[1] < angle_bottom < angle_top < vertex[1]
    for y in (angle_bottom, angle_top):
        flank_x = shoulder[0] + (y - shoulder[1]) * (
            vertex[0] - shoulder[0]
        ) / (vertex[1] - shoulder[1])
        assert angle_right + 0.002 < flank_x
    assert angle_left > _BORDER_LEFT_M + 0.002
    assert blocks["HexHeight"][1] < cx - fence - 0.0015
    width_line = _dimension_line_y("HexWidth", blocks["HexWidth"][4])
    assert drawing.DETAIL_LABEL_XY[1] + 0.005 < width_line < cy - fence - 0.001
    assert blocks["HexWidth"][0] > cx + hw + 0.002
    datum_foot = vertex[1] + drawing.RIDGE_DATUM_RISE
    assert datum_foot + 0.007 < cy + fence
    assert blocks["KnifeRidgeRadius"][0] > cx + 0.010
    assert blocks["KnifeRidgeRadius"][2] > datum_foot + 0.007 + 0.004
    assert blocks["KnifeRidgeRadius"][3] < pair_line - 0.004


def test_knife_detail_is_cut_from_the_existing_receiver_view(monkeypatch) -> None:
    calls = []
    adapter, back, result = object(), object(), object()
    monkeypatch.setattr(
        drawing, "_detail_view",
        lambda *args, **kwargs: calls.append((args, kwargs)) or result,
    )
    assert drawing._knife_detail(adapter, back) is result
    (args, definition), = calls
    assert args == (adapter, back)
    assert definition["centre_mm"] == (
        0.0, 0.0, -drawing.PLATE_L / 2.0 - drawing.HEX_DEPTH,
    )
    assert definition["radius_m"] == pytest.approx(0.006)
    assert definition["scale"] == (10.0, 1.0)
    assert definition["letter"] == "D"


def test_datum_a_attaches_the_actual_visible_back_knife_round(monkeypatch) -> None:
    calls = []
    edge, detail = object(), object()
    spec = sm_summing_lever_spec
    z = -spec.PLATE_L / 2.0 - spec.HEX_DEPTH
    center_y = spec.HEX_H / 2.0 - spec.KNIFE_RIDGE_R / math.sin(
        math.radians(spec.RIDGE_ANGLE_DEG) / 2.0,
    )

    def circle_at(center, radius, *, axis, label):
        assert center == pytest.approx((0.0, center_y, z))
        assert radius == spec.KNIFE_RIDGE_R
        assert axis == (0.0, 0.0, 1.0)
        return SimpleNamespace(edge=edge)

    def project(adapter, view, points, **kwargs):
        assert view is detail
        assert points == [
            drawing._metres((0.0, center_y + spec.KNIFE_RIDGE_R, z)),
            drawing._metres((0.0, spec.HEX_H / 2.0, z)),
        ]
        return (0.115, 0.200), (0.115, 0.20134)

    monkeypatch.setattr(drawing, "scan_view_edges", lambda view, **kwargs: SimpleNamespace(circle_at=circle_at))
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "add_datum_feature", lambda *args, **kwargs: calls.append((args, kwargs)))
    drawing._ridge_datum(object(), detail)
    (args, definition), = calls
    assert args[1] is detail
    assert definition["edge_entity"] is edge
    assert definition["datum"] == "A"
    assert definition["leader_attach_xy"] == (0.115, 0.200)
    assert definition["symbol_xy"] == pytest.approx((0.115, 0.20234))
    assert definition["position_tolerance_m"] == 0.003


def test_the_ridge_callouts_fit_detail_d() -> None:
    """Reflow preserves every word while the complete projected blocks fit."""
    right = notes.DIMENSION_CALLOUTS_BELOW["RidgeFromRight"]
    assert " ".join(right.split()) == (
        f"KNIFE-EDGE SEAT IN {notes.KNIFE_MOUNT_NUMBER}; BOTH STUBS"
    )
    for name in ("RidgeFromLeft", "RidgeFromRight", "FlankToSide"):
        assert max(map(len, notes.DIMENSION_CALLOUTS_BELOW[name].split("\n"))) <= (
            notes.RIDGE_CALLOUT_MAX_CHARS
        )


def test_notes_are_short_stated_shortfalls() -> None:
    for text in (
        notes.ISOMETRIC_VIEW_NOTE,
        notes.BACK_VIEW_NOTE,
        notes.FRONT_VIEW_NOTE,
    ):
        assert len(text.splitlines()) <= 4
        for word in ("RULE", "EXCEPTION", "RULING", "NYLON", "LOCTITE", "THREADLOCK"):
            assert word not in text.upper()
    # The uniform plate retains 1.5D of full #6-32 thread at its lower limit.
    assert notes.SPRING_TAP_ENGAGEMENT_MIN >= 1.5 * notes.SPRING_TAP_MAJOR_DIA
    assert not hasattr(notes, "DRAWING_NOTES")
    assert not hasattr(notes, "BRACKET_RECEIVER_NOTE")
    assert "summation anchor position" not in sm_summing_lever_spec.GEOMETRIC_TOLERANCES_MM


def test_receiver_depth_bands_follow_owned_dimensions_without_native_name_guesses(monkeypatch) -> None:
    import _appearance
    import _com
    import _custom_properties
    import _dimensions
    import _feature_tree
    import _part_checks
    import _part_properties
    import _part_save
    import _rebuild
    import _session
    import _sketch
    import _sketch_rectangle
    import _drawing_marks
    import build_sm_summing_lever as part
    import pytest

    class Dimension:
        def __init__(self, name, owner, nominal, kind=0):
            self._name = name
            self.owner = owner
            self._value = nominal / 1000.0
            self.kind = kind

        @property
        def Name(self):
            return self._name

        @Name.setter
        def Name(self, value):
            if self.owner in {"BracketMountingTaps", "Sketch14", "Hole Thread22", "Hole Thread23", "ReferencePlane"}:
                raise AssertionError("native Wizard dimension names must not be rewritten")
            self._name = value

        @property
        def FullName(self):
            return f"{self.Name}@{self.owner}"

        @property
        def SystemValue(self):
            return self._value

        def GetType(self):
            return self.kind

    def display(dimension):
        def get_dimension(index):
            assert index == 0
            return dimension
        return SimpleNamespace(GetDimension2=get_dimension)

    class Feature:
        def __init__(self, name, dimensions=(), children=()):
            self.Name = name
            self.displays = [display(dim) for dim in dimensions]
            self.children = children
            self.next_subfeature = None
            for current, following in zip(children, children[1:]):
                current.next_subfeature = following

        def Parameter(self, name):
            return next(
                (item.GetDimension2(0) for item in self.displays if item.GetDimension2(0).Name == name),
                None,
            )

        def GetFirstDisplayDimension(self):
            return self.displays[0] if self.displays else None

        def GetNextDisplayDimension(self, current):
            index = self.displays.index(current) + 1
            return self.displays[index] if index < len(self.displays) else None

        def GetFirstSubFeature(self):
            return self.children[0] if self.children else None

        def GetNextSubFeature(self):
            return self.next_subfeature

    # Native shape observed on the farm (2026-10-09): the tap drill depth lives
    # on a sketch subfeature, and each hole gets its own cosmetic thread.
    drill = Dimension("Tap Drill Depth", "Sketch14", 6.50)
    thread = Dimension("D1", "Hole Thread22", 4.95)
    thread_b = Dimension("D1", "Hole Thread23", 4.95)
    unrelated = Dimension("Depth", "ReferencePlane", 4.95)
    angular = Dimension("D3", "BracketMountingTaps", 4.95, kind=1)
    sketch_feature = Feature("Sketch14", [drill])
    thread_feature = Feature("Hole Thread22", [thread])
    thread_feature_b = Feature("Hole Thread23", [thread_b])
    taps = Feature(
        "BracketMountingTaps",
        [drill, thread, thread_b, unrelated, angular],
        [sketch_feature, thread_feature, thread_feature_b],
    )
    rib_depth = Dimension("D1", "EdgeRibBack", lever_build.RECEIVER_RIB_T)
    features = {"EdgeRibBack": Feature("EdgeRibBack", [rib_depth])}
    features["BracketMountingTaps"] = taps
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))

    def invoke(value, interface, member, *args):
        attribute = getattr(value, member)
        if callable(attribute):
            return attribute(*args)
        assert not args
        return attribute

    monkeypatch.setattr(_appearance, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_com, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_custom_properties, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_feature_tree, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_checks, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_properties, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_save, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_rebuild, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_session, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_sketch, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_sketch_rectangle, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_com, "_com_invoke", invoke)
    monkeypatch.setattr(_dimensions, "_com_invoke", invoke)
    monkeypatch.setattr(_feature_tree, "_com_invoke", invoke)
    monkeypatch.setattr(_drawing_marks, "_com_invoke", invoke)
    bands = []
    monkeypatch.setattr(
        part, "set_dimension_symmetric_tolerance",
        lambda adapter, feature, name, band: bands.append((feature, name, band)),
    )
    monkeypatch.setattr(part, "set_dimension_display_precision", lambda *args: None)
    held = []
    monkeypatch.setattr(
        part, "_band_held_dimension",
        lambda display, dimension, band, label: held.append(
            (display.GetDimension2(0) is dimension, dimension, band, label)
        ),
    )
    monkeypatch.setattr(part, "mark_dimensions_for_drawing", lambda *args: None)
    inventory = []
    monkeypatch.setattr(part._telemetry, "info", inventory.append)
    part._receiver_model_bands(adapter)
    assert bands == []
    assert rib_depth.Name == "RibDepth"
    # Subfeatures are not FeatureByName-reachable and both threads are "D1":
    # band the exact native objects found in the walk, never a by-name lookup.
    assert held == [
        (True, thread, (-0.05, 0.05), "D1@Hole Thread22"),
        (True, thread_b, (-0.05, 0.05), "D1@Hole Thread23"),
        (True, drill, (-0.51, 0.51), "Tap Drill Depth@Sketch14"),
    ]
    assert (drill.Name, thread.Name, thread_b.Name, unrelated.Name) == (
        "Tap Drill Depth", "D1", "D1", "Depth"
    )
    assert angular.Name == "D3"
    assert any("D3@BracketMountingTaps = 0.00495 SI" in row for row in inventory)
    assert any("D1@Hole Thread22 = 4.95 mm (feature Hole Thread22)" in row for row in inventory)
    assert any("Depth@ReferencePlane = 4.95 mm" in row for row in inventory)

    # Parent-only traversal: dimensions owned by subfeatures must not be
    # mistaken for parent parameters.
    taps.children = ()
    inventory.clear()
    rib_depth.Name = "D1"
    with pytest.raises(RuntimeError, match="expected 2 native FullThreadDepth .*found 0"):
        part._receiver_model_bands(adapter)
    assert inventory and any("D1@Hole Thread22" in row for row in inventory)
    # Two depths on ONE cosmetic thread (one hole uncovered) is ambiguous.
    taps.children = (sketch_feature, thread_feature)
    thread_feature.next_subfeature = None
    sketch_feature.next_subfeature = thread_feature
    thread_feature.displays.append(display(Dimension("D9", thread_feature.Name, 4.95)))
    rib_depth.Name = "D1"
    with pytest.raises(RuntimeError, match="expected 2 native FullThreadDepth \\(one per owner\\), found 2"):
        part._receiver_model_bands(adapter)


def test_receiver_native_drill_band_is_explicit_symmetric_ordinary_width(monkeypatch) -> None:
    import _com
    import _drawing_tolerances
    import magnifying_bracket_joint_layout as joint

    class Tolerance:
        Type = 0

        def SetValues(self, lower, upper):
            self.lower, self.upper = lower, upper
            return True

        def GetMinValue(self):
            return self.lower

        def GetMaxValue(self):
            return self.upper

    tolerance = Tolerance()
    display = SimpleNamespace(
        SetPrecision3=lambda *args: True,
        GetPrimaryPrecision2=lambda: 2,
    )
    monkeypatch.setattr(_com, "_bind", lambda value, _kind: value)
    monkeypatch.setattr(_com, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(_drawing_tolerances, "_set_tolerance_precision", lambda *args, **kwargs: None)
    lever_build._band_held_dimension(
        display, SimpleNamespace(Tolerance=tolerance),
        joint.DRILL_DEPTH_DEVIATIONS, "native receiver drill",
    )
    assert tolerance.Type == 4  # swTolSYMMETRIC, not bilateral or MIN
    assert (tolerance.lower, tolerance.upper) == pytest.approx((-0.00051, 0.00051))


@pytest.fixture
def bracket_depth_callout(monkeypatch):
    """Keep late-bound metadata distinct from the native length interface."""
    import sys

    class Interface:
        def __init__(self, **values):
            object.__setattr__(self, "values", values)
            object.__setattr__(self, "ignored", set())
            object.__setattr__(self, "writes", [])

        def __getattr__(self, name):
            return self.values[name]

        def __setattr__(self, name, value):
            self.writes.append((name, value))
            if name not in self.ignored:
                self.values[name] = value

    def native(name, depth):
        metadata = Interface(
            VariableName=name, ToleranceType=4, ToleranceMin=0.0, ToleranceMax=0.0,
        )
        length = Interface(Length=depth / 1000.0, Precision=1, TolerancePrecision=1)
        return SimpleNamespace(raw=SimpleNamespace(_oleobj_=metadata), metadata=metadata, length=length)

    thread = native("hw-threaddepth", 4.95)
    drill = native("hw-tapdrldepth", 6.50)
    unrelated = native("hw-threaddia", 2.1844)
    variables = [unrelated.raw, thread.raw, drill.raw]
    dispatched = []
    bound = []

    def dispatch(ole):
        assert any(ole is item.metadata for item in (unrelated, thread, drill))
        dispatched.append(ole)
        return ole

    def early_bound(raw, kind):
        assert kind == "ICalloutLengthVariable"
        for item in (thread, drill):
            if raw is item.raw:
                bound.append(raw)
                return item.length
        raise AssertionError("unrelated callout variable must not be dressed")

    monkeypatch.setitem(sys.modules, "win32com.client.dynamic", SimpleNamespace(Dispatch=dispatch))
    monkeypatch.setattr(drawing, "_early_bound", early_bound)
    callout = SimpleNamespace(GetHoleCalloutVariables=lambda: variables)
    return SimpleNamespace(
        dress=lambda: drawing._dress_bracket_depth_callout(callout),
        thread=thread, drill=drill, unrelated=unrelated, variables=variables,
        dispatched=dispatched, bound=bound,
    )


def test_bracket_depth_callout_inherits_printed_two_place_band(bracket_depth_callout) -> None:
    import magnifying_bracket_joint_layout as joint

    case = bracket_depth_callout
    unrelated_before = (dict(case.unrelated.metadata.values), dict(case.unrelated.length.values))
    case.dress()
    assert case.drill.metadata.ToleranceType == 0  # swTolNONE: title-block presentation
    assert case.drill.length.Precision == 2
    assert case.drill.length.Length == pytest.approx(0.00650)
    # NONE hides the native variable's unused tolerance fields; dressing must
    # not write them or assume SOLIDWORKS retains hidden deviations.
    assert case.drill.metadata.writes == [("ToleranceType", 0)]
    assert case.drill.length.writes == [("Precision", 2)]
    assert case.thread.metadata.ToleranceType == 5  # swTolMIN, not a bilateral thread depth
    assert case.thread.length.Length == pytest.approx(0.00495)
    assert case.thread.length.writes == []
    assert (case.thread.metadata.ToleranceMin, case.thread.metadata.ToleranceMax) == (0.0, 0.0)
    assert (case.unrelated.metadata.values, case.unrelated.length.values) == unrelated_before
    assert case.unrelated.metadata.writes == case.unrelated.length.writes == []
    assert case.bound == [case.thread.raw, case.drill.raw]
    assert case.dispatched == [case.unrelated.metadata, case.thread.metadata, case.drill.metadata]

    # Derive the effective band from the printed nominal and the actual sheet
    # row, not value_in (whose metric conversion is intentionally rounded).
    printed_nominal = f"{case.drill.length.Length * 1000.0:.{case.drill.length.Precision}f}"
    assert printed_nominal == "6.50"
    display = _config.title_block("linear_2pl")["display"]
    assert display.startswith("±")
    printed_band = float(display.removeprefix("±"))
    effective_limits = (float(printed_nominal) - printed_band, float(printed_nominal) + printed_band)
    assert effective_limits == pytest.approx((5.99, 7.01))
    physical_limits = tuple(joint.DRILL_DEPTH + delta for delta in joint.DRILL_DEPTH_DEVIATIONS)
    assert effective_limits == pytest.approx(physical_limits)


@pytest.mark.parametrize(("member", "wrong_mm"), [("thread", 4.90), ("drill", 6.00)])
def test_bracket_depth_callout_rejects_wrong_native_length(
    bracket_depth_callout, member, wrong_mm,
) -> None:
    case = bracket_depth_callout
    getattr(case, member).length.values["Length"] = wrong_mm / 1000.0
    with pytest.raises(RuntimeError):
        case.dress()


@pytest.mark.parametrize("missing", ["thread", "drill", "both"])
def test_bracket_depth_callout_requires_both_native_depth_variables(
    bracket_depth_callout, missing,
) -> None:
    case = bracket_depth_callout
    removed = (case.thread.raw, case.drill.raw) if missing == "both" else (getattr(case, missing).raw,)
    case.variables[:] = [raw for raw in case.variables if all(raw is not item for item in removed)]
    with pytest.raises(RuntimeError):
        case.dress()


@pytest.mark.parametrize(
    ("member", "interface", "setter"),
    [
        ("thread", "metadata", "ToleranceType"),
        ("drill", "metadata", "ToleranceType"),
        ("drill", "length", "Precision"),
    ],
)
def test_bracket_depth_callout_rejects_ignored_native_setters(
    bracket_depth_callout, member, interface, setter,
) -> None:
    case = bracket_depth_callout
    target = getattr(getattr(case, member), interface)
    target.ignored.add(setter)
    with pytest.raises(RuntimeError):
        case.dress()
    assert any(name == setter for name, _value in target.writes)


@pytest.mark.parametrize("band", [(-0.51, 0.40), (-0.40, 0.40)])
def test_bracket_depth_callout_rejects_engineering_band_not_inherited_by_print(
    monkeypatch, bracket_depth_callout, band,
) -> None:
    monkeypatch.setattr(drawing, "DRILL_DEPTH_DEVIATIONS", band)
    with pytest.raises(RuntimeError):
        bracket_depth_callout.dress()




@pytest.mark.parametrize(
    "damage",
    (
        None, "outer-caps-absent", "missing", "empty", "receiver-entry",
        "receiver-inner", "opposite-inner", "extra", "receiver-depth",
        "opposite-depth", "missing-depth",
    ),
)
def test_native_rib_end_planes_preserve_both_outer_faces(monkeypatch, damage) -> None:
    def face(z):
        surface = SimpleNamespace(
            IsPlane=lambda: True, PlaneParams=(0.0, 0.0, 1.0, 0.0, 0.0, z / 1000.0),
        )
        return SimpleNamespace(GetSurface=lambda: surface)

    planes = {"EdgeRibBack": [-76.2, -68.0], "EdgeRibFront": [71.12, 76.2]}
    depths = {"EdgeRibBack": 8.2, "EdgeRibFront": 5.08}
    if damage == "outer-caps-absent":
        planes = {"EdgeRibBack": [-68.0], "EdgeRibFront": [71.12]}
    elif damage == "receiver-depth":
        depths["EdgeRibBack"] = 7.3
    elif damage == "opposite-depth":
        depths["EdgeRibFront"] = 8.2
    elif damage == "receiver-entry":
        planes["EdgeRibBack"][0] -= 0.9
    elif damage == "receiver-inner":
        planes["EdgeRibBack"][1] = -68.9
    elif damage == "opposite-inner":
        planes["EdgeRibFront"][0] = 68.0
    elif damage == "extra":
        planes["EdgeRibBack"].append(-70.0)
    elif damage == "empty":
        planes["EdgeRibBack"] = []

    def feature(name, values):
        expected_parameter = "RibDepth" if name == "EdgeRibBack" else "EdgeRibThickness"

        def parameter(parameter_name):
            assert parameter_name == expected_parameter
            if damage == "missing-depth" and name == "EdgeRibBack":
                return None
            return SimpleNamespace(SystemValue=depths[name] / 1000.0)

        return SimpleNamespace(
            GetFaces=lambda: tuple(face(z) for z in values),
            Parameter=parameter,
        )

    features = {name: feature(name, values) for name, values in planes.items()}
    if damage == "missing":
        del features["EdgeRibBack"]
    monkeypatch.setattr(lever_build, "_early_bound", lambda value, _kind: value)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))
    if damage in (None, "outer-caps-absent"):
        lever_build._assert_edge_rib_end_planes(adapter)
    else:
        with pytest.raises(RuntimeError, match="EdgeRibBack|EdgeRibFront"):
            lever_build._assert_edge_rib_end_planes(adapter)


def test_receiver_row_retains_its_profile_wall_margin() -> None:
    """The blind receivers stay in the unchanged footprint, inside the G1 rib."""
    import magnifying_bracket_joint_layout as joint
    from sm_summing_lever_profile import receiver_wall_margin

    drill_radius_max = (joint.TAP_DRILL_DIA + joint.DRILLED_DIAMETER_PLUS) / 2.0
    for x, y, _z in joint.LEVER_HOLE_POINTS:
        assert receiver_wall_margin(
            x + joint.POSITION_BAND,
            y + joint.POSITION_BAND,
            drill_radius_max,
        ) - joint.LINEAR_BAND - joint.DRILL_WANDER_MAX >= 2.0


def _thread_annotation_drawing(monkeypatch, note_count: int = 7):
    """The six-view package: labels vary but the three native callouts survive."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    state = SimpleNamespace(selected=None, deletes=True, selectable=True)

    class Annotation:
        def __init__(self, kind, name, specific=None):
            self.kind, self.name, self.specific = kind, name, specific
            self.dangling = False

        def GetType(self):
            return self.kind

        def GetName(self):
            return self.name

        def GetSpecificAnnotation(self):
            return self.specific

        def Select2(self, _append, _mark):
            state.selected = self
            return state.selectable

        def IsDangling(self):
            return self.dangling

    def note(text, name):
        return Annotation(6, name, SimpleNamespace(GetText=lambda: text))

    def view(name):
        annotations = []
        return SimpleNamespace(
            name=name, annotations=annotations,
            GetAnnotations=lambda: tuple(annotations),
            GetNotes=lambda: tuple(a.specific for a in annotations if a.kind == 6),
        )

    top, iso, detail, back = [view(name) for name in ("plan", "iso", "D", "back")]
    back.annotations.extend(Annotation(1, f"thread{index}") for index in range(2))
    for index in range(note_count):
        owner = (top, top, top, back, iso, iso, iso, detail)[index % 8]
        owner.annotations.append(note(
            "#2-56 tapped hole" if owner is back else "#6-32 Tapped Hole",
            f"label{index}",
        ))
    unrelated = note("VIEW F", "view label")
    back.annotations.append(unrelated)
    callouts = []
    for label, owner, prefix in (
        ("anchor tap", top, "#10-24"),
        ("spring-hole pattern", top, "20X #6-32"),
        ("two blind bracket mounting taps", back, "#2-56"),
    ):
        # Native definitions retain associative fields, including the blind depths.
        definitions = {
            5: f"{prefix} <hw-threadsize>",
            6: "<hw-threaddepth> MIN" if owner is back else "THRU",
            7: "<hw-tapdrldepth>" if owner is back else "",
            8: "",
        }
        annotation = Annotation(4, label)
        display = SimpleNamespace(
            definitions=definitions, hole_callout=True,
            GetAnnotation=lambda annotation=annotation: annotation,
            GetText=lambda part, definitions=definitions: definitions[part],
        )
        display.IsHoleCallout = lambda display=display: display.hole_callout
        annotation.specific = display
        owner.annotations.append(annotation)
        callouts.append((label, owner, display))
    views = {
        drawing.SHEET_NAMES[0]: (top, iso),
        drawing.SHEET_NAMES[1]: (back, detail),
    }
    all_views = (top, iso, detail, back)

    def delete():
        if state.deletes:
            for owner in all_views:
                if state.selected in owner.annotations:
                    owner.annotations.remove(state.selected)

    document = SimpleNamespace(
        Sheet=lambda name: SimpleNamespace(GetViews=lambda: views[name]),
        ClearSelection2=lambda _all: None,
        EditDelete=delete,
    )
    adapter = SimpleNamespace(
        currentModel=document,
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
    )
    return SimpleNamespace(
        adapter=adapter, state=state, callouts=tuple(callouts), views=all_views,
        detail=detail, back=back, unrelated=unrelated, note=note,
    )


@pytest.mark.parametrize("note_count", [0, 7, 8, 9])
def test_actual_thread_notes_are_removed_without_losing_authored_callouts(
    monkeypatch, note_count,
) -> None:
    case = _thread_annotation_drawing(monkeypatch, note_count)
    check = drawing._finished_thread_annotation_check(case.adapter, case.callouts)
    drawing._remove_redundant_thread_notes(case.adapter)
    check()
    assert all(
        annotation.kind != 6 or annotation is case.unrelated
        for view in case.views for annotation in view.annotations
    )
    assert case.unrelated in case.back.annotations
    assert sum(a.kind == 1 for a in case.back.annotations) == 2
    for _, owner, display in case.callouts:
        assert display.GetAnnotation() in owner.annotations


def test_thread_note_cleanup_requires_deletion_readback(monkeypatch) -> None:
    case = _thread_annotation_drawing(monkeypatch)
    case.state.deletes = False  # EditDelete returns void even when nothing disappeared.
    with pytest.raises(RuntimeError, match="notes survived deletion"):
        drawing._remove_redundant_thread_notes(case.adapter)
    case = _thread_annotation_drawing(monkeypatch)
    case.state.selectable = False
    with pytest.raises(RuntimeError, match="failed to select"):
        drawing._remove_redundant_thread_notes(case.adapter)


def test_finished_thread_check_rejects_a_late_automatic_note(monkeypatch) -> None:
    case = _thread_annotation_drawing(monkeypatch)
    check = drawing._finished_thread_annotation_check(case.adapter, case.callouts)
    drawing._remove_redundant_thread_notes(case.adapter)
    check()
    case.detail.annotations.append(case.note("#2-56 TAPPED HOLE", "late detail label"))
    with pytest.raises(RuntimeError, match="redundant tapped-hole note remains"):
        check()


@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("damage", ["missing", "changed", "dangling", "not_native"])
def test_finished_thread_check_preserves_each_authoritative_callout(
    monkeypatch, index, damage,
) -> None:
    case = _thread_annotation_drawing(monkeypatch)
    check = drawing._finished_thread_annotation_check(case.adapter, case.callouts)
    drawing._remove_redundant_thread_notes(case.adapter)
    _, owner, display = case.callouts[index]
    annotation = display.GetAnnotation()
    if damage == "missing":
        owner.annotations.remove(annotation)
        # A replacement with the same label and definition is not the authored object.
        replacement = type(annotation)(annotation.GetType(), annotation.GetName())
        replacement.specific = SimpleNamespace(
            GetAnnotation=lambda: replacement,
            GetText=display.GetText,
            IsHoleCallout=lambda: True,
        )
        owner.annotations.append(replacement)
    elif damage == "changed":
        display.definitions[6] = "THRU ALL"  # In particular, cannot lose the blind depth.
    elif damage == "dangling":
        annotation.dangling = True
    else:
        display.hole_callout = False
    with pytest.raises(RuntimeError, match="authored native hole callout"):
        check()


def test_finished_thread_capture_rejects_an_initially_nonnative_callout(monkeypatch) -> None:
    case = _thread_annotation_drawing(monkeypatch)
    case.callouts[0][2].hole_callout = False
    with pytest.raises(RuntimeError, match="authored annotation is not a native hole callout"):
        drawing._finished_thread_annotation_check(case.adapter, case.callouts)


def _native_plate_thickness(monkeypatch, offset=(0.0, 0.0), band=(0, 0.0, 0.0)):
    """Native boundaries for the actual free-end witnesses in back VIEW F."""
    dx, dy = offset
    state = SimpleNamespace(
        name="PlateThickness@PlateProfile@sm-summing-lever.SLDPRT",
        value=0.007, band=band, owner_type=0, dangling=False,
        gaps=[0.001, 0.001], use_doc=[True, False], read_overrides={},
        projection_offset=(0.0, 0.0), projection_scale=(1.0, 1.0),
        projected_bad=None, projections=[], scans=0, count_override=None,
        active_sheet=drawing.SHEET_NAMES[0], activate_result=True,
    )
    free_x, tail_x, arrow_x = 0.235 + dx, 0.225 + dx, 0.228 + dx
    levels = (
        0.100 + dy + drawing.COEFFICIENT_BOTTOM_Y / 1000.0,
        0.100 + dy + drawing.COEFFICIENT_TOP_Y / 1000.0,
    )
    state.arrows = [
        [arrow_x, y, 0.0, 0.0, direction, 0.0, 0.001, 0.001, 0.0, 0.0, 0.0, 1.0]
        for y, direction in zip(levels, (-1.0, 1.0))
    ]
    state.lines = [
        ((free_x - gap, y), (tail_x, y)) for gap, y in zip(state.gaps, levels)
    ] + [((arrow_x, levels[0]), (arrow_x, levels[1]))]
    z_mm = -drawing.PLATE_L / 2.0
    state.edges = [
        _line((drawing.PLATE_W - 2.0, y, z_mm), (drawing.PLATE_W, y, z_mm))
        for y in (drawing.COEFFICIENT_BOTTOM_Y, drawing.COEFFICIENT_TOP_Y)
    ]

    class Tolerance:
        Type = property(lambda self: state.band[0])

        def GetMinValue(self):
            return state.band[1]

        def GetMaxValue(self):
            return state.band[2]

    tolerance = Tolerance()

    class Dimension:
        FullName = property(lambda self: state.name)
        SystemValue = property(lambda self: state.value)
        Tolerance = property(lambda self: tolerance)

    class Data:
        def GetArrowHeadCount(self):
            assert state.active_sheet == drawing.SHEET_NAMES[1]
            return len(state.arrows)

        def GetArrowHeadAtIndex2(self, index):
            return state.arrows[index]

        def GetLineCount(self):
            return len(state.lines)

        def GetLineAtIndex2(self, index):
            first, second = state.lines[index]
            return (0.0, 0.0, 0.0, 0.0, *first, 0.0, *second, 0.0)

    class Display:
        def GetDimension2(self, index):
            assert index == 0
            return state.dimension

        def GetDisplayData(self):
            return state.data

        def GetWitnessLineGap(self, index, use_doc, gap):
            assert type(index) is int and index in (0, 1)
            assert use_doc is False and gap == 0.0
            return state.read_overrides.get(
                index, (True, state.use_doc[index], state.gaps[index]),
            )

    class Annotation:
        OwnerType = property(lambda self: state.owner_type)

        def GetType(self):
            return 4

        def IsDangling(self):
            return state.dangling

        def GetSpecificAnnotation(self):
            return state.display

    state.dimension, state.data, state.display = Dimension(), Data(), Display()
    annotation = Annotation()
    state.annotations = [annotation]
    view = SimpleNamespace(
        GetAnnotationCount=lambda: (
            len(state.annotations) if state.count_override is None else state.count_override
        ),
        GetAnnotations=lambda: tuple(state.annotations),
    )

    def activate_sheet(name):
        if state.activate_result is True:
            state.active_sheet = name
        return state.activate_result

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(ActivateSheet=activate_sheet),
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
    )

    def project(_adapter, _view, xyz, *, label):
        x, y, z = xyz
        assert _view is view
        assert z == z_mm / 1000.0
        state.projections.append(xyz)
        if state.projected_bad is not None:
            return (state.projected_bad, 0.100 + dy + y)
        return (
            free_x + state.projection_offset[0]
            - state.projection_scale[0] * (x - drawing.PLATE_W / 1000.0),
            0.100 + dy + state.projection_offset[1] + state.projection_scale[1] * y,
        )

    def scan(_view, *, label):
        assert _view is view
        state.scans += 1
        return ViewEdges(label=label, edges=tuple(state.edges))

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda *_args: "PlateThickness")
    monkeypatch.setattr(
        solidworks_mcp.adapters.sw_type_info, "early_bound_or_flag", lambda value, *_args: value,
    )
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    return SimpleNamespace(
        adapter=adapter, view=view, annotation=annotation, state=state,
        capture=lambda: drawing._plate_thickness_check(adapter, view, [annotation]),
    )


@pytest.mark.parametrize(
    ("offset", "band"),
    [((0.0, 0.0), (0, 0.0, 0.0)), ((0.017, -0.009), (2, -0.0001, 0.0002))],
)
def test_plate_thickness_keeps_native_identity_band_gaps_and_free_end_ink(
    monkeypatch, offset, band,
) -> None:
    case = _native_plate_thickness(monkeypatch, offset, band)
    state = case.state
    original = (state.dimension, state.display, state.name, state.value, state.band)
    arrows = [tuple(row) for row in state.arrows]
    lines = list(state.lines)
    settled_check = case.capture()
    state.active_sheet = drawing.SHEET_NAMES[0]
    settled_check()
    assert original == (state.dimension, state.display, state.name, state.value, state.band)
    assert [tuple(row) for row in state.arrows] == arrows
    assert state.lines == lines
    assert state.gaps == [0.001, 0.001]
    assert state.use_doc == [True, False]
    assert state.active_sheet == drawing.SHEET_NAMES[1]
    assert state.scans == 2
    assert set(state.projections) == {
        drawing._metres((drawing.PLATE_W, y, -drawing.PLATE_L / 2.0))
        for y in (drawing.COEFFICIENT_BOTTOM_Y, drawing.COEFFICIENT_TOP_Y)
    } | {
        drawing._metres((
            drawing.PLATE_W - 1.0, drawing.COEFFICIENT_BOTTOM_Y, -drawing.PLATE_L / 2.0,
        )),
    }


@pytest.mark.parametrize(
    "answer",
    [(1, False, 0.001), (True, 0, 0.001), (True, False, True),
     (False, False, 0.001), (True, False, math.nan), (True, False, -0.001)],
)
def test_plate_thickness_requires_authoritative_native_witness_gap(monkeypatch, answer) -> None:
    case = _native_plate_thickness(monkeypatch)
    case.state.read_overrides[1] = answer
    with pytest.raises(RuntimeError, match="witness gap"):
        case.capture()


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("name", "PlateThickness@OtherFeature"),
        ("name", "PlateThickness@CoefficientsPlate@sm-summing-lever.SLDPRT"),
        ("value", True), ("value", math.nan), ("value", 0.00508),
        ("dimension", None), ("band", (False, 0.0, 0.0)),
        ("band", (2, math.nan, 0.0002)), ("owner_type", 1),
        ("owner_type", False), ("dangling", True), ("annotations", []),
        ("count_override", True), ("count_override", 2),
        ("activate_result", False), ("activate_result", 1),
    ],
)
def test_plate_thickness_rejects_wrong_model_identity_or_view(monkeypatch, member, value) -> None:
    case = _native_plate_thickness(monkeypatch)
    setattr(case.state, member, value)
    with pytest.raises(RuntimeError, match="VIEW F PlateThickness"):
        case.capture()


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("projection_scale", (-1.0, 1.0)), ("projection_scale", (1.0, -1.0)),
        ("projection_scale", (2.0, 1.0)), ("projection_offset", (0.001, 0.0)),
        ("projected_bad", math.nan), ("projected_bad", True),
    ],
)
def test_plate_thickness_rejects_wrong_projection(monkeypatch, member, value) -> None:
    case = _native_plate_thickness(monkeypatch)
    setattr(case.state, member, value)
    with pytest.raises(RuntimeError, match="projected plate|witness endpoint"):
        case.capture()


@pytest.mark.parametrize("damage", ["hidden", "inboard_end", "wrong_face"])
def test_plate_thickness_requires_both_actual_visible_free_end_edges(monkeypatch, damage) -> None:
    case = _native_plate_thickness(monkeypatch)
    bottom = drawing.COEFFICIENT_BOTTOM_Y
    z = -drawing.PLATE_L / 2.0
    if damage == "hidden":
        case.state.edges.pop(0)
    elif damage == "inboard_end":
        case.state.edges[0] = _line(
            (drawing.PLATE_W - 2.0, bottom, z), (drawing.PLATE_W - 0.1, bottom, z),
        )
    else:
        case.state.edges[0] = _line(
            (drawing.PLATE_W - 2.0, bottom, z),
            (drawing.PLATE_W, bottom + 0.1, z),
        )
    with pytest.raises(RuntimeError, match="coefficient|free end"):
        case.capture()


@pytest.mark.parametrize(
    "damage",
    ["one_arrow", "nonfinite_arrow", "boolean_arrow", "arrow_level", "arrow_x",
     "missing_witness", "extra_horizontal", "witness_level", "witness_origin", "nonfinite_witness"],
)
def test_plate_thickness_rejects_unattached_or_wrong_native_ink(monkeypatch, damage) -> None:
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    if damage == "one_arrow":
        state.arrows.pop()
    elif damage in {"nonfinite_arrow", "boolean_arrow", "arrow_level", "arrow_x"}:
        coordinate, value = {
            "nonfinite_arrow": (0, math.inf), "boolean_arrow": (0, True),
            "arrow_level": (1, 0.100), "arrow_x": (0, 0.229),
        }[damage]
        state.arrows[0][coordinate] = value
    elif damage == "missing_witness":
        state.lines.pop(0)
    elif damage == "extra_horizontal":
        state.lines.append(((0.230, 0.125), (0.240, 0.125)))
    else:
        first, second = state.lines[0]
        state.lines[0] = {
            "witness_level": ((first[0], 0.100), (second[0], 0.100)),
            "witness_origin": ((first[0] - 0.001, first[1]), second),
            "nonfinite_witness": ((math.nan, first[1]), second),
        }[damage]
    with pytest.raises(RuntimeError, match="native|witness"):
        case.capture()


@pytest.mark.parametrize(
    "damage", ["tail", "arrow", "origin", "detached", "replacement", "band", "value", "gap"],
)
def test_settled_thickness_check_reads_regenerated_native_state(monkeypatch, damage) -> None:
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    settled_check = case.capture()
    if damage == "tail":
        first, second = state.lines[0]
        state.lines[0] = (first, (second[0] - 0.001, second[1]))
    elif damage == "arrow":
        state.arrows[0][1] = 0.100
    elif damage == "origin":
        state.projection_offset = (0.001, 0.0)
    elif damage == "detached":
        state.annotations = []
    elif damage == "replacement":
        old = state.dimension
        state.dimension = SimpleNamespace(
            FullName=old.FullName, SystemValue=old.SystemValue, Tolerance=old.Tolerance,
        )
    elif damage == "band":
        state.band = (0, 0.0, 1e-13)
    elif damage == "value":
        state.value += 1e-13
    else:
        state.use_doc[0] = False
    with pytest.raises(RuntimeError, match="VIEW F PlateThickness"):
        settled_check()


@pytest.mark.parametrize(
    ("name", "check_radius", "nominal", "max_type"),
    [
        ("KnifeRidgeRadius", drawing._assert_knife_ridge_radius,
         drawing.KNIFE_RIDGE_R, drawing.KNIFE_RIDGE_R_TOL_TYPE),
        ("RibRootRadius", drawing._assert_rib_root_radius,
         drawing.RIB_BLEND_R, drawing.RIB_BLEND_R_TOL_TYPE),
    ],
)
@pytest.mark.parametrize("damage", [None, "value", "band", "diameter", "missing", "duplicate"])
def test_imported_radii_keep_the_native_model_value_and_max_band(
    monkeypatch, name, check_radius, nominal, max_type, damage,
) -> None:
    dimension = SimpleNamespace(
        SystemValue=(nominal + (0.01 if damage == "value" else 0.0)) / 1000.0,
        Tolerance=SimpleNamespace(Type=0 if damage == "band" else max_type),
    )
    display = SimpleNamespace(
        Diametric=damage == "diameter", GetDimension2=lambda _index: dimension,
        GetText=lambda _part: name,
    )
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    annotations = [] if damage == "missing" else [annotation]
    if damage == "duplicate":
        annotations.append(annotation)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda *_args: name)
    if damage is None:
        check_radius(object(), annotations)
    else:
        with pytest.raises(RuntimeError):
            check_radius(object(), annotations)


def _dimension_ownership_drawing(monkeypatch):
    """Six native view inventories, including both undimensioned isometrics."""
    owners = {
        name: feature
        for feature, names in drawing.DIMENSIONS_BY_FEATURE.items() for name in names
    }

    def annotation(name):
        state = SimpleNamespace(
            full_name=f"{name}@{owners[name]}@sm-summing-lever.SLDPRT",
            owner_type=0, visible=1, dangling=False,
        )

        class ModelDimension:
            FullName = property(lambda self: state.full_name)

        class Annotation:
            OwnerType = property(lambda self: state.owner_type)
            Visible = property(lambda self: state.visible)

            def GetType(self):
                return 4

            def GetSpecificAnnotation(self):
                return SimpleNamespace(GetDimension2=lambda _index: ModelDimension())

            def IsDangling(self):
                return state.dangling

        return Annotation(), state

    views, states, assignments = {}, {}, []
    native = SimpleNamespace(active_sheet=None, activation_result=True, calls=[])

    def activate(sheet):
        native.calls.append(sheet)
        if native.activation_result is True:
            native.active_sheet = sheet
        return native.activation_result

    adapter = SimpleNamespace(currentModel=SimpleNamespace(ActivateSheet=activate))
    for sheet, label, wanted in (
        (drawing.SHEET_NAMES[0], "VIEW G", drawing.FRONT_KEEP),
        (drawing.SHEET_NAMES[0], "top", drawing.TOP_KEEP),
        (drawing.SHEET_NAMES[0], "geometry isometric", {}),
        (drawing.SHEET_NAMES[1], "D", drawing.DETAIL_KEEP),
        (drawing.SHEET_NAMES[1], "VIEW F", drawing.BACK_KEEP),
        (drawing.SHEET_NAMES[1], "receiver isometric", {}),
    ):
        annotations = []
        view = SimpleNamespace(
            annotations=annotations, count_override=None, sheet=sheet,
        )

        def read_annotations(view=view):
            assert native.active_sheet == view.sheet
            return tuple(view.annotations)

        view.GetAnnotations = read_annotations
        view.GetAnnotationCount = lambda view=view: (
            len(view.annotations) if view.count_override is None else view.count_override
        )
        for name in wanted:
            raw, state = annotation(name)
            annotations.append(raw)
            states[name] = state
        views[label] = view
        assignments.append((sheet, label, view, wanted))
    # A native hole callout has no underlying model IDimension and is not a
    # second marked model dimension; a plain null dimension is not equivalent.
    callout = SimpleNamespace(
        hole=True, GetDimension2=lambda _index: None,
        IsHoleCallout=lambda: callout.hole,
    )
    views["VIEW F"].annotations.append(SimpleNamespace(
        GetType=lambda: 4, GetSpecificAnnotation=lambda: callout,
    ))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    return SimpleNamespace(
        check=drawing._dimension_ownership_check(adapter, assignments),
        views=views, states=states, callout=callout, native=native,
    )


def test_each_native_dimension_belongs_to_one_of_the_six_views(monkeypatch) -> None:
    case = _dimension_ownership_drawing(monkeypatch)
    case.check()
    assert len(case.views) == 6
    assert case.native.calls == list(drawing.SHEET_NAMES)
    case.check()
    assert case.native.calls == list(drawing.SHEET_NAMES) * 2
    assert set(drawing.DETAIL_KEEP) == {
        *notes.DRAWING_DIMENSIONS["KnifeEnvelopeReference"], "KnifeRidgeRadius",
    }
    assert "PlateThickness" in drawing.BACK_KEEP
    assert "RibReach" in drawing.FRONT_KEEP
    assert "RibRootRadius" in drawing.FRONT_KEEP


@pytest.mark.parametrize(
    "damage",
    ["moved", "duplicate", "missing", "wrong_feature", "sheet_owned", "hidden",
     "dangling", "bad_count", "boolean_count", "null_non_callout", "iso_dimension",
     "sheet_activation"],
)
def test_dimension_ownership_rejects_wrong_native_view_or_inventory(monkeypatch, damage) -> None:
    case = _dimension_ownership_drawing(monkeypatch)
    case.check()
    knife = case.views["D"]
    raw = knife.annotations[0]
    state = case.states[next(iter(drawing.DETAIL_KEEP))]
    if damage == "moved":
        knife.annotations.remove(raw)
        case.views["VIEW F"].annotations.append(raw)
    elif damage == "duplicate":
        knife.annotations.append(raw)
    elif damage == "missing":
        knife.annotations.remove(raw)
    elif damage == "wrong_feature":
        state.full_name = state.full_name.replace("KnifeEnvelopeReference", "OtherFeature")
    elif damage == "sheet_owned":
        state.owner_type = 1
    elif damage == "hidden":
        state.visible = 3
    elif damage == "dangling":
        state.dangling = True
    elif damage == "bad_count":
        knife.count_override = len(knife.annotations) + 1
    elif damage == "boolean_count":
        knife.count_override = True
    elif damage == "null_non_callout":
        case.callout.hole = False
    elif damage == "sheet_activation":
        case.native.activation_result = False
    else:
        case.views["receiver isometric"].annotations.append(raw)
    with pytest.raises(RuntimeError, match="ownership|census|no model owner|cannot activate"):
        case.check()
