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
    # Each anchor's thread must span the seat it screws into (the
    # spring-anchor pad under the plate's free edge).
    assert ANCHOR_9489T111.thread_length_mm > sm_summing_lever_spec.SPRING_SEAT_T
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


def test_end_face_edge_is_the_rib_top_edge_not_the_flange_or_underside() -> None:
    """Datum B and the start-Z BASIC hang on the +Z END face: the rib flange
    5.08 mm inboard reads 3.35 for 8.43 (#1105), and the rib's underside edge
    shares the end plane but is hidden under the plate."""
    z = sm_summing_lever_spec.PLATE_L / 2.0
    # The ribs keep the slant towards (PLATE_W, 0) but end on a vertical face
    # at build_sm_summing_lever.RIB_PLATE_REACH (HOLE_X - 4.1), short of the
    # hole column and still proud of the plate top there.
    reach = lever_build.RIB_PLATE_REACH
    end_h = lever_build.edge_rib_half_height(reach)
    half_t = sm_summing_lever_spec.PLATE_T / 2.0
    assert reach == pytest.approx(sm_summing_lever_spec.HOLE_X - 4.1)
    assert end_h - half_t == pytest.approx(0.44286, abs=1e-5)
    top = _line((0.0, 15.24, z), (reach, end_h, z))
    flange = _line(
        (0.0, 15.24, z - sm_summing_lever_spec.PLATE_T), (reach, end_h, z - 5.08)
    )
    step = _line((reach, end_h, z), (reach, half_t, z))
    underside = _line((reach, -end_h, z), (0.0, -15.24, z))
    plate_end = _line((reach, half_t, z), (sm_summing_lever_spec.PLATE_W, half_t, z))
    edges = ViewEdges(label="plan", edges=(flange, underside, step, plate_end, top))
    assert drawing._end_face_edge(edges, x_mm=10.0) is top
    assert drawing._end_face_edge(edges, x_mm=32.0) is top
    assert drawing._end_face_edge(edges, x_mm=40.0) is plate_end
    # At the rib's end face the rib edge, its step and the plate edge all meet.
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(edges, x_mm=reach)
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(ViewEdges(label="plan", edges=(flange, underside)), x_mm=10.0)


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


def test_bracket_receiver_is_blind_and_authored_after_ribs() -> None:
    from pathlib import Path
    import build_sm_summing_lever as part
    import magnifying_bracket_joint_layout as joint
    assert part.LEVER_HOLE_POINTS is joint.LEVER_HOLE_POINTS
    assert part.TAP_SPEC is joint.TAP_SPEC
    assert (part.TAP_SPEC.kind, part.TAP_SPEC.end) == ("tapped_bottoming", "blind")
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.index("await _middle_rib(adapter, drive_jobs)") < source.index(
        "await _bracket_mounting_taps(adapter)"
    )
    assert "DRILL_DEPTH + DRILL_POINT_DEPTH / 3.0" in source
    assert 'name="BracketMountingTaps"' in source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "mounting_rims[0].edge" in drawing_source
    assert "process=BRACKET_TAP_CALLOUT_PROCESS" in drawing_source
    # The process line leads the callout; the native size starts the next row.
    assert notes.BRACKET_TAP_CALLOUT_PROCESS.endswith("\n")
    assert notes.BRACKET_SCREW_NUMBER in notes.BRACKET_TAP_CALLOUT_PROCESS
    assert notes.BRACKET_TAP_CALLOUT_PROCESS.splitlines()[-1] == joint.THREAD_EXTENT_REQUIREMENT
    assert joint.THREAD_EXTENT_REQUIREMENT == "THREAD EXTENT WITHIN DRILL CYLINDER"
    assert '"hw-threaddepth": THREAD_DEPTH' in drawing_source
    assert '"hw-tapdrldepth": DRILL_DEPTH' in drawing_source
    assert "bracket tap callout omits native depths" in drawing_source
    assert part.TAP_SPEC.size == "#2-56"
    assert part.TAP_SPEC.depth_mm == 6.50
    assert part.TAP_SPEC.overrides_mm["ThreadDepth"] == 4.95
    assert joint.THREAD_DEPTH_BAND == 0.05
    assert joint.DRILL_DEPTH_DEVIATIONS == (-0.51, 0.51)  # ordinary .XX width
    # The -Z rib's depth rides the title block (no native band of its own).
    assert joint.RIB_DEPTH_BAND == joint.LINEAR_BAND
    assert not hasattr(joint, "RECEIVER_DIMENSION_BANDS")
    assert "variable.ToleranceMin" in drawing_source
    assert "variable.ToleranceMax" in drawing_source
    assert "variable = dynamic_dispatch(raw._oleobj_)" in drawing_source
    assert '_early_bound(raw, "ICalloutVariable")' not in drawing_source
    assert "ReceiverY0" in drawing_source
    assert "Bracket Receiver Note" not in drawing_source
    assert "Manufacturing Notes" not in drawing_source
    final_proof = source.index('"summing lever after native receiver bands"')
    assert source.index("_receiver_model_bands(adapter)") < final_proof
    assert source.index("_receiver_coordinate_dimensions(adapter)") < final_proof
    assert final_proof < source.index("artefacts = await save_part_and_images")
    assert "v_built, 1e-5 * v_built" in source


def test_receiver_upper_stop_keeps_drill_out_of_unbacked_plate() -> None:
    """H-H steps down to bare plate, not a floor or the spring-anchor pad."""
    import magnifying_bracket_joint_layout as joint

    # Both longitudinal receivers sit outside the pivot cylinder and inboard
    # of the pad. After the end rib, only the plate backs their bore walls.
    drill_radius_max = joint.TAP_DRILL_RADIUS_MAX
    pad_inner_x = sm_summing_lever_spec.PLATE_W - sm_summing_lever_spec.SPRING_PAD_W
    for x, _y, _z in joint.LEVER_HOLE_POINTS:
        assert x - joint.POSITION_BAND - drill_radius_max > sm_summing_lever_spec.CYL_R
        assert x + joint.POSITION_BAND + drill_radius_max < pad_inner_x
    assert joint.DRILL_POINT_RIB_MARGIN_MIN > 0.0
    # A MIN-only depth would allow the full drill diameter into this thinner
    # section. Its worst wall would not meet the unchanged 1.5 mm floor.
    bare_plate_wall = (
        joint.RECEIVER_LOWER_NOTCH_HEIGHT_MIN
        - drill_radius_max - joint.DRILL_WANDER_MAX
    )
    assert bare_plate_wall < 1.5


def test_nothing_reads_as_an_overall_or_a_band_it_is_not() -> None:
    """Machinist review 20261018: the plan's 152.40 read as the overall (the
    stubs stand 2X 21.72 past it) and the 0.44 rib-end step as a tight band
    (it is derived from the slant and the plate)."""
    plate_length = notes.DIMENSION_CALLOUTS_BELOW["PlateLength"]
    assert " ".join(plate_length.split()) == "BODY END FACES"
    x, _ = drawing.TOP_KEEP["PlateLength"]
    widest = max(len("152.40"), *map(len, plate_length.split("\n")))
    assert x + _CHAR_M * widest / 2.0 < 0.4191 - 0.002  # under the right border
    assert notes.REFERENCE_DIMENSIONS == {"EdgeRibFrontEndStep"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in source


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
    overrun = drawing.RECEIVER_AXIS_OVERRUN_MM
    station = drawing.RECEIVER_AXIS_START_MM - overrun
    outer_tap = max(point[0] for point in joint.LEVER_HOLE_POINTS)
    assert outer_tap + joint.TAP_DRILL_DIA / 2.0 < lever_build.RIB_PLATE_REACH
    assert lever_build.RIB_PLATE_REACH < station
    assert station + overrun < spec.PLATE_W
    assert overrun > 0.0


def test_receiver_view_is_on_a_back_view_sheet_with_real_binding() -> None:
    import ast
    from pathlib import Path
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "from _sw_type_info import" not in source
    assert '"*Back", *BACK_CENTER' in source
    assert "expected_sheet_names=SHEET_NAMES" in source
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "scan_view_edges":
                assert len(node.args) == 1
    assert 'length = _early_bound(raw, "ICalloutLengthVariable")' in source


@pytest.mark.parametrize("placed", [2, 4])  # the farm places views in HLR (2)
def test_sheet_one_views_never_pass_through_hidden_lines_visible(
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


def test_dimension_metadata_names_resolve_to_their_model_owners() -> None:
    names = [
        name
        for owned in drawing.DIMENSIONS_BY_FEATURE.values()
        for name in owned
    ]
    assert len(names) == len(set(names)), "a model dimension has two owning features"
    above = set(notes.DIMENSION_CALLOUTS_ABOVE)
    below = set(notes.DIMENSION_CALLOUTS_BELOW)
    assert not above & below
    assert above | below <= set(names)
    for (feature, name), _prefix in notes.DIMENSION_PREFIXES.items():
        assert name in notes.DRAWING_DIMENSIONS[feature]


def test_middle_theoretical_reach_and_end_rib_faces_have_distinct_native_owners() -> None:
    assert notes.DRAWING_DIMENSIONS["MiddleRibProfile"] == {"MidRibLeftX"}
    assert drawing.DIMENSIONS_BY_FEATURE["MiddleRibProfile"] == {"MidRibLeftX"}
    assert "MidRibLeftX" not in notes.DRAWING_DIMENSIONS["EdgeRibFrontProfile"]
    assert "EdgeRibFrontEndTopX" in notes.DRAWING_DIMENSIONS["EdgeRibFrontProfile"]
    assert notes.DIMENSION_CALLOUTS_ABOVE["EdgeRibFrontEndTopX"] == "END RIB FACES"
    assert notes.DIMENSION_CALLOUTS_ABOVE["MidRibLeftX"] == "MID RIB THEORETICAL INTERSECTION"
    assert "MidRibLeftX" not in notes.REFERENCE_DIMENSIONS
    assert "MidRibLeftX" not in drawing.TOP_KEEP


def test_the_knife_edge_prints_its_ridge_and_flanks_to_the_sides(monkeypatch) -> None:
    """Code review C09 (owner ruling T1): Detail D holds the ridge sharp
    4.040 +/-0.05 from each side face and each upper flank 122.4 +/-0.5 deg
    to its side face, on both stubs; the width is a reference."""
    spec = sm_summing_lever_spec
    knife = notes.DRAWING_DIMENSIONS["KnifeEnvelopeReference"]
    assert knife == {"HexWidth", "HexHeight", "RidgeFromLeft", "RidgeFromRight", "FlankToSide"}
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
# The boss diameter's four lines under Detail D (top, stack r4 sheet).
_BOSS_CALLOUT_TOP_M = 0.1784


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


def test_the_knife_detail_text_stands_clear_of_the_hexagon() -> None:
    """Detail D (4:1): the ridge pair's one line over the fence, E's fence
    and the flank angle's arc, each text outside its own span and every block
    under the border; the flank angle's text outside the fence, in the wedge
    opposite the +X shoulder's corner, so it reads 122.4, not its 57.6
    supplement; the vertex height between the border and the fence.  Stack
    r4 printed the -X callout 9.7 mm over the border, the pair's -X line on
    E's fence, and the angle's text and extension through the vertex height.
    Detail E (10:1): the R MAX right of the fence and of datum A's box."""
    spec = sm_summing_lever_spec
    scale = drawing.DETAIL_SCALE[0] / 1000.0
    cx, cy = drawing.DETAIL_CENTER
    fence = drawing.DETAIL_RADIUS_MM * scale
    hw = spec.HEX_W / 2.0 * scale
    vertex = (cx, cy + spec.HEX_H / 2.0 * scale)
    shoulder = (cx + hw, cy + spec.HEX_H / 4.0 * scale)
    # The fence holds the hexagon.
    assert spec.HEX_H / 2.0 < drawing.DETAIL_RADIUS_MM - 0.5
    blocks = {
        "HexWidth": _detail_block("HexWidth", "2X (8.080)"),
        "HexHeight": _detail_block("HexHeight", "2X 10.268"),
        "RidgeFromLeft": _detail_block("RidgeFromLeft", "2X 4.040 ±0.05"),
        "RidgeFromRight": _detail_block("RidgeFromRight", "2X 4.040 ±0.05"),
        "FlankToSide": _detail_block("FlankToSide", "4X 122.4° ±0.5°"),
    }
    for name, (left, _right, _bottom, top, _lines) in blocks.items():
        assert top < _BORDER_TOP_M - 0.004, name
        assert left > _BORDER_LEFT_M + 0.002, name
    # View G's 19.05 (AnchorHeight) is the nearest text to the right.
    g_left = drawing.FRONT_KEEP["AnchorHeight"][0] - _CHAR_M * len("19.05") / 2.0
    for name in ("RidgeFromRight", "FlankToSide", "HexWidth"):
        assert blocks[name][1] < g_left - 0.003, name

    # The ridge pair: one line, each text outside its own span.
    left_line = _dimension_line_y("RidgeFromLeft", blocks["RidgeFromLeft"][4])
    right_line = _dimension_line_y("RidgeFromRight", blocks["RidgeFromRight"][4])
    assert left_line == pytest.approx(right_line, abs=2e-4)
    assert blocks["RidgeFromLeft"][1] < cx - hw - 0.002
    assert blocks["RidgeFromRight"][0] > cx + hw + 0.002
    e_fence = drawing.RIDGE_DETAIL_RADIUS_MM * scale
    assert left_line > cy + fence + 0.004
    assert left_line > vertex[1] + e_fence + 0.004  # arrowheads clear E's fence

    # The flank angle: in the wedge, its text outside the fence, its arc
    # (and the side face's extension to it) under the ridge pair's line.
    angle_x, angle_y = drawing.DETAIL_KEEP["FlankToSide"]
    direction = math.degrees(math.atan2(angle_y - shoulder[1], angle_x - shoulder[0]))
    flank_down = -(90.0 - spec.RIDGE_ANGLE_DEG / 2.0)
    assert flank_down < direction < 90.0
    a_left, a_right, a_bottom, a_top, _ = blocks["FlankToSide"]
    near_x = min(max(cx, a_left), a_right)
    near_y = min(max(cy, a_bottom), a_top)
    assert math.hypot(near_x - cx, near_y - cy) > fence + 0.001
    assert a_left > shoulder[0] + 0.002
    arc = math.hypot(angle_x - shoulder[0], angle_y - shoulder[1])
    assert shoulder[1] + arc < left_line - 0.002

    # The vertex height: left of the fence at the block's height, its line
    # and text clear of the angle's wedge.
    h_left, h_right, h_bottom, h_top, _ = blocks["HexHeight"]
    dy = 0.0 if h_bottom < cy < h_top else min(abs(h_bottom - cy), abs(h_top - cy))
    assert h_right < cx - math.sqrt(max(fence**2 - dy**2, 0.0)) - 0.0015
    assert h_right < cx - hw

    # The reference width: its line under the fence, over the boss callout.
    width_line = _dimension_line_y("HexWidth", blocks["HexWidth"][4])
    assert _BOSS_CALLOUT_TOP_M + 0.002 < width_line < cy - fence - 0.001
    assert blocks["HexWidth"][0] > cx + hw + 0.002

    # E's letter sits between the +X pair's extension lines, under its line.
    letter = (
        vertex[0] + drawing.RIDGE_DETAIL_LETTER_OFFSET[0],
        vertex[1] + drawing.RIDGE_DETAIL_LETTER_OFFSET[1],
    )
    assert cx + 0.002 < letter[0] < cx + hw - 0.002
    assert vertex[1] < letter[1] < right_line - 0.004
    assert math.hypot(letter[0] - vertex[0], letter[1] - vertex[1]) > e_fence + 0.003
    e_radius = drawing.RIDGE_DETAIL_RADIUS_MM * drawing.RIDGE_DETAIL_SCALE[0] / 1000.0
    ex, ey = drawing.RIDGE_DETAIL_CENTER
    r_x, r_y = drawing.RIDGE_DETAIL_KEEP["KnifeRidgeRadius"]
    assert math.hypot(r_x - ex, r_y - ey) > e_radius + 0.010
    assert r_x > ex + 0.020  # right of datum A's box over the vertex


def test_the_ridge_callouts_fit_detail_d() -> None:
    """The +X ridge band takes two wide lines; the -X one and the angle sit
    in tighter room (the border, the fence, the angle's arc), so they take
    short lines: the layout test above places them."""
    lines = notes.DIMENSION_CALLOUTS_BELOW["RidgeFromRight"].split("\n")
    assert len(lines) == 2
    assert max(map(len, lines)) <= notes.RIDGE_CALLOUT_MAX_CHARS
    assert len(notes.DIMENSION_CALLOUTS_BELOW["RidgeFromLeft"].split("\n")) == 2
    assert "\n" not in notes.DIMENSION_CALLOUTS_BELOW["FlankToSide"]


def test_notes_are_short_stated_shortfalls() -> None:
    for text in (
        notes.ISOMETRIC_VIEW_NOTE,
        notes.BACK_VIEW_NOTE,
        notes.FRONT_VIEW_NOTE,
        notes.STUB_ROOT_VIEW_NOTE,
    ):
        assert len(text.splitlines()) <= 4
        for word in ("RULE", "EXCEPTION", "RULING", "NYLON", "LOCTITE", "THREADLOCK"):
            assert word not in text.upper()
    # The spring pad itself gives every #6-32 anchor 1.5D of full thread at
    # the pad's worst case, so no engagement shortfall is printed.
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
    definitions = {
        5: f"{notes.BRACKET_TAP_CALLOUT_PROCESS}#2-56 <hw-threadsize>",
        6: "<hw-threaddepth> MIN",
        7: "<hw-tapdrldepth>",
        8: "",
    }
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
    callout = SimpleNamespace(
        GetHoleCalloutVariables=lambda: variables,
        GetText=lambda part: definitions[part],
    )
    return SimpleNamespace(
        dress=lambda: drawing._dress_bracket_depth_callout(callout),
        thread=thread, drill=drill, unrelated=unrelated, variables=variables,
        dispatched=dispatched, bound=bound, definitions=definitions,
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


@pytest.mark.parametrize("replacement", ["", "THREAD EXTENT UNBOUNDED"])
def test_bracket_depth_callout_requires_the_printed_thread_extent_process(
    bracket_depth_callout, replacement,
) -> None:
    case = bracket_depth_callout
    required = "THREAD EXTENT WITHIN DRILL CYLINDER"
    assert required in case.definitions[5]
    case.definitions[5] = case.definitions[5].replace(required, replacement)
    with pytest.raises(RuntimeError, match="omits bounded physical thread extent"):
        case.dress()


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


def test_rib_added_area_matches_independent_cross_section_integration() -> None:
    """Integrate profile minus the existing cylinder/plate/pad union by strips.

    Midpoint strips avoid the production circle-lens and pad-area formulae.
    The 0.002 mm² allowance covers quadrature at the curved boundary and
    rectangle edges, but resolves either overlap term being omitted.
    """
    part = lever_build
    strip_count = 40_000
    dx = (part.ARC_R + part.RIB_PLATE_REACH) / strip_count
    area = 0.0
    for index in range(strip_count):
        x = -part.ARC_R + (index + 0.5) * dx
        half_height = (
            math.sqrt(part.ARC_R**2 - x**2) if x < 0
            else part.ARC_R * (1 - x / part.PLATE_W)
        )
        occupied_low = occupied_high = 0.0
        if abs(x) < part.CYL_R:
            occupied_high = math.sqrt(part.CYL_R**2 - x**2)
            occupied_low = -occupied_high
        if 0 <= x <= part.PLATE_W:
            occupied_low = min(occupied_low, -part.PLATE_T / 2)
            occupied_high = max(occupied_high, part.PLATE_T / 2)
        if part.PLATE_W - part.SPRING_PAD_W <= x <= part.PLATE_W:
            occupied_low = min(occupied_low, part.PLATE_T / 2 - part.SPRING_SEAT_T)
        # Every existing interval contains y=0, so their union has no gaps.
        covered = max(0.0, min(half_height, occupied_high) - max(-half_height, occupied_low))
        area += (2 * half_height - covered) * dx
    assert part.edge_rib_added_area_mm2() == pytest.approx(area, abs=0.002)


@pytest.mark.asyncio
async def test_only_receiver_rib_extrudes_inward_to_nine_point_four(monkeypatch) -> None:
    from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

    part = lever_build
    calls, volumes = [], []
    events = []
    state = SimpleNamespace(volume=1000.0)

    async def success(*args, **kwargs):
        return AdapterResult(status=AdapterResultStatus.SUCCESS, data="entity")

    async def arc(*args):
        return "arc", None, None

    async def measured(*args):
        events.append("measure")
        return state.volume

    def extrude(adapter, depth, offset, **kwargs):
        events.append("extrude")
        calls.append((depth, offset, kwargs))
        state.volume += 17.0 * depth

    async def volume_check(adapter, label, expected, tolerance):
        events.append("check")
        volumes.append((label, expected, tolerance))

    class SketchDims:
        def record(self, *args):
            pass

        def apply(self, *args):
            return []

    adapter = SimpleNamespace(**{
        name: success for name in (
            "create_sketch", "add_line", "add_sketch_constraint",
            "add_sketch_dimension", "exit_sketch",
        )
    })
    monkeypatch.setattr(part, "SketchDims", SketchDims)
    monkeypatch.setattr(part, "_three_point_arc", arc)
    monkeypatch.setattr(part, "_measured_volume", measured)
    monkeypatch.setattr(part, "force_rebuild", success)
    monkeypatch.setattr(part, "volume_check", volume_check)
    for name in ("anchor_point_to_origin", "dimension_between", "ensure_fully_defined"):
        monkeypatch.setattr(part, name, success)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda *args: None)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    monkeypatch.setattr(part, "name_dimensions", lambda *args: ["front thickness"])
    monkeypatch.setattr(part, "extrude_at_offset", extrude)
    jobs = []
    await part._edge_rib(adapter, True, "receiver", "EdgeRibBack", jobs)
    await part._edge_rib(adapter, False, "opposite", "EdgeRibFront", jobs)
    assert len(calls) == 2
    for (depth, offset, _), expected in zip(calls, ((9.4, 66.8), (5.08, 71.12)), strict=True):
        assert (depth, offset) == pytest.approx(expected)
    assert [kwargs for _, _, kwargs in calls] == [{"flip": True}, {}]
    assert -calls[0][1] - calls[0][0] == pytest.approx(-76.2)
    assert calls[1][1] + calls[1][0] == pytest.approx(76.2)
    area = part.edge_rib_added_area_mm2()
    assert area > 0
    baselines = [1000.0, 1000.0 + 17.0 * 9.4]
    assert [value - baseline for (_, value, _), baseline in zip(volumes, baselines, strict=True)] == pytest.approx(
        [area * 9.4, area * 5.08]
    )
    assert events == ["measure", "extrude", "check", "measure", "extrude", "check"]
    assert jobs == [("front thickness", '"RibT"')]


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

    planes = {"EdgeRibBack": [-76.2, -66.8], "EdgeRibFront": [71.12, 76.2]}
    depths = {"EdgeRibBack": 9.4, "EdgeRibFront": 5.08}
    if damage == "outer-caps-absent":
        planes = {"EdgeRibBack": [-66.8], "EdgeRibFront": [71.12]}
    elif damage == "receiver-depth":
        depths["EdgeRibBack"] = 7.3
    elif damage == "opposite-depth":
        depths["EdgeRibFront"] = 9.4
    elif damage == "receiver-entry":
        planes["EdgeRibBack"][0] -= 0.9
    elif damage == "receiver-inner":
        planes["EdgeRibBack"][1] = -67.7
    elif damage == "opposite-inner":
        planes["EdgeRibFront"][0] = 66.8
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


def test_receiver_row_sits_inside_the_end_rib_height() -> None:
    """The row is located from the plate top, which the plate's title-block
    thickness band moves by half that band about the rib's mid-plane; both
    taps lie inside the end rib's reach, so their walls run to the rib's
    upper and lower faces, not the plate's."""
    import magnifying_bracket_joint_layout as joint

    drill_radius_max = joint.TAP_DRILL_RADIUS_MAX
    outer_x = max(point[0] for point in joint.LEVER_HOLE_POINTS)
    assert outer_x + drill_radius_max + joint.POSITION_BAND < lever_build.RIB_PLATE_REACH
    row_offset_max = joint.POSITION_BAND + joint.LINEAR_BAND / 2.0
    rib_half_min = (
        lever_build.edge_rib_half_height(outer_x + drill_radius_max + joint.POSITION_BAND)
        - joint.LINEAR_BAND / 2.0
    )
    wall = rib_half_min - row_offset_max - drill_radius_max - joint.DRILL_WANDER_MAX
    assert wall == pytest.approx(3.17805, abs=1e-5)
    assert wall >= 2.0


def test_tap_section_cuts_the_outer_tap_through_the_rib_into_solid_plate() -> None:
    import magnifying_bracket_joint_layout as joint

    x, y, end_z = drawing.TAP_SECTION_HOLE
    assert (x, y, end_z) == max(joint.LEVER_HOLE_POINTS)
    assert drawing.TAP_SECTION_LETTER not in {
        "A",
        "B",
        "C",
        drawing.DETAIL_LETTER,
        drawing.RIDGE_DETAIL_LETTER,
        notes.BACK_VIEW_LETTER,
        notes.FRONT_VIEW_LETTER,
    }
    # The line spans the rib's full height at the tap, outside both faces.
    rib_half = lever_build.edge_rib_half_height(x)
    low, high = drawing.TAP_SECTION_LINE_Y
    assert low < -rib_half and high > rib_half
    # The crop circle holds the rib's four corners (end face and inboard
    # face, full height), and the break past the drill point and the rib;
    # the plate's faces leave the circle just past the break.
    _, _, centre_z = drawing._TAP_SECTION_ANCHOR_MM
    radius = drawing.TAP_SECTION_CROP_RADIUS
    for z in (end_z, end_z + joint.RIB_DEPTH):
        assert math.hypot(z - centre_z, rib_half) < radius
    far_z = drawing._TAP_SECTION_FAR_Z
    assert far_z > end_z + joint.DRILL_DEPTH_MAX
    assert far_z > end_z + joint.RIB_DEPTH
    assert drawing.TAP_SECTION_BREAK[0][0] == drawing.TAP_SECTION_BREAK[-1][0] == far_z
    face_exit = centre_z + math.sqrt(radius**2 - (lever_build.PLATE_T / 2.0) ** 2)
    assert far_z < face_exit < far_z + 0.5
    assert drawing.TAP_SECTION_SCALE == (4, 1)
    # The break prints on the black thin layer, not as a grey sketch line.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("def _tap_section") :]
    body = body[: body.index("\ndef ")]
    assert body.index("_thin_visible_layer(adapter)") < body.index("CreateLine")
    assert "segment.Layer = TAP_THREAD_LAYER" in body


def _thread_annotation_drawing(monkeypatch, note_count: int = 7):
    """PR1709's two sheets: four H-H threads even when its auto-label is absent."""
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

    top, iso, section, back = [view(name) for name in ("plan", "iso", "H-H", "back")]
    section.annotations.extend(Annotation(1, f"thread{index}") for index in range(4))
    for index in range(note_count):
        owner = (top, top, top, back, iso, iso, iso, section)[index % 8]
        owner.annotations.append(note(
            "#2-56 tapped hole" if owner is section else "#6-32 Tapped Hole",
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
            5: f"{notes.BRACKET_TAP_CALLOUT_PROCESS if owner is back else ''}{prefix} <hw-threadsize>",
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
        drawing.SHEET_NAMES[0]: (top, iso, section),
        drawing.SHEET_NAMES[1]: (back,),
    }
    all_views = (top, iso, section, back)

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
        section=section, back=back, unrelated=unrelated, note=note,
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
    assert sum(a.kind == 1 for a in case.section.annotations) == 4
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
    case.section.annotations.append(case.note("#2-56 TAPPED HOLE", "late H-H label"))
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


@pytest.mark.parametrize("replacement", ["", "THREAD EXTENT UNBOUNDED"])
def test_finished_bracket_callout_preserves_the_printed_thread_extent_process(
    monkeypatch, replacement,
) -> None:
    case = _thread_annotation_drawing(monkeypatch)
    bracket_callout = case.callouts[-1][2]
    required = "THREAD EXTENT WITHIN DRILL CYLINDER"
    assert required in bracket_callout.definitions[5]
    check = drawing._finished_thread_annotation_check(case.adapter, case.callouts)
    drawing._remove_redundant_thread_notes(case.adapter)
    check()
    bracket_callout.definitions[5] = bracket_callout.definitions[5].replace(required, replacement)
    with pytest.raises(RuntimeError, match="authored native hole callout changed"):
        check()


def _native_plate_thickness(monkeypatch, offset=(0.0, 0.0), band=(0, 0.0, 0.0)):
    """Measured native C-C contract; rebuild alone updates its visible gap ink."""
    dx, dy = offset
    state = SimpleNamespace(
        name="PlateThickness@CoefficientsPlate@sm-summing-lever.SLDPRT",
        value=0.00508, band=band, owner_type=0, dangling=False,
        gaps=[0.001, 0.001], use_doc=[True, False], ink_gaps=[0.001, 0.001],
        set_calls=[], gap_reads=[], setter_results=[True, True], persist=[True, True],
        read_overrides={}, projection_offset=(0.0, 0.0), projection_scale=(1.0, 1.0),
        projected_bad=None, projections=[], rebuilds=[],
        active_sheet=drawing.SHEET_NAMES[1], activate_result=True,
    )
    free_x, tail_x, arrow_x = 0.085975 + dx, 0.048525 + dx, 0.049525 + dx
    levels = (0.12746 + dy, 0.13254 + dy)
    state.arrows = [
        [arrow_x, y, 0.0, 0.0, direction, 0.0, 0.001, 0.001, 0.0, 0.0, 0.0, 1.0]
        for y, direction in zip(levels, (-1.0, 1.0))
    ]

    def regenerate():
        state.lines = [
            ((free_x - gap, y), (tail_x, y))
            for gap, y in zip(state.ink_gaps, levels)
        ] + [((arrow_x, levels[0]), (arrow_x, levels[1]))]

    regenerate()

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
            assert state.active_sheet == drawing.SHEET_NAMES[0]
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
            stage = "after" if state.set_calls else "before"
            state.gap_reads.append((stage, index))
            return state.read_overrides.get(
                (stage, index), (True, state.use_doc[index], state.gaps[index]),
            )

        def SetWitnessLineGap(self, index, use_doc, gap):
            assert use_doc is False
            state.set_calls.append((index, use_doc, gap))
            result = state.setter_results[index]
            if result is True and state.persist[index]:
                state.gaps[index], state.use_doc[index] = gap, use_doc
            return result

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
    view = SimpleNamespace(GetAnnotations=lambda: tuple(state.annotations))

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
        assert z == drawing.PLATE_SECTION_Z / 1000.0
        state.projections.append(xyz)
        if state.projected_bad is not None:
            return (state.projected_bad, 0.130 + dy + y)
        return (
            0.075 + dx + state.projection_offset[0]
            + state.projection_scale[0] * (x - 0.033475),
            0.130 + dy + state.projection_offset[1] + state.projection_scale[1] * y,
        )

    def rebuild(_adapter, *, label):
        state.rebuilds.append(label)
        state.ink_gaps = list(state.gaps)
        regenerate()

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        solidworks_mcp.adapters.sw_type_info, "early_bound_or_flag", lambda value, *_args: value,
    )
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    return SimpleNamespace(
        adapter=adapter, view=view, annotation=annotation, state=state,
        style=lambda: drawing._style_plate_thickness_witnesses(adapter, view, [annotation]),
    )


@pytest.mark.parametrize(
    ("offset", "band"), [((0.0, 0.0), (0, 0.0, 0.0)), ((0.017, -0.009), (2, -0.0001, 0.0002))],
)
def test_plate_thickness_witnesses_shorten_native_ink_outside_the_bare_cut(
    monkeypatch, offset, band,
) -> None:
    case = _native_plate_thickness(monkeypatch, offset, band)
    state = case.state
    original = (state.dimension, state.display, state.name, state.value, state.band)
    arrows = [tuple(row) for row in state.arrows]
    settled_check = case.style()
    settled_check()
    assert original == (state.dimension, state.display, state.name, state.value, state.band)
    assert [tuple(row) for row in state.arrows] == arrows
    assert state.set_calls == [(0, False, pytest.approx(0.03145)), (1, False, pytest.approx(0.03145))]
    assert state.gaps == pytest.approx((0.03145, 0.03145))
    assert state.use_doc == [False, False]
    for line, y in zip(state.lines[:2], (0.12746 + offset[1], 0.13254 + offset[1])):
        assert line[0] == pytest.approx((0.054525 + offset[0], y))
        assert line[1] == pytest.approx((0.048525 + offset[0], y))
        assert math.dist(*line) == pytest.approx(0.006)
    assert set(state.projections) == {
        (x / 1000.0, y / 1000.0, drawing.PLATE_SECTION_Z / 1000.0)
        for x in (drawing.PLATE_SECTION_X[0], drawing.PLATE_W)
        for y in (-drawing.PLATE_T / 2.0, drawing.PLATE_T / 2.0)
    }
    for index in (0, 1):
        assert ("before", index) in state.gap_reads
        assert state.gap_reads.count(("after", index)) >= 3
    assert len(state.rebuilds) == 1


@pytest.mark.parametrize(("index", "result"), [(0, False), (0, 1), (1, None)])
def test_plate_thickness_witness_gap_setters_require_native_true(
    monkeypatch, index, result,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    case.state.setter_results[index] = result
    with pytest.raises(RuntimeError, match=f"native witness gap {index} was refused"):
        case.style()
    assert case.state.rebuilds == []


@pytest.mark.parametrize(
    ("stage", "answer"),
    [
        ("before", (1, False, 0.001)),
        ("before", (True, 0, 0.001)),
        ("before", (True, False, True)),
        ("before", (True, False, math.nan)),
        ("before", (True, False, 0.002)),
        ("after", (False, False, 0.03145)),
        ("after", (True, True, 0.03145)),
        ("after", (True, False, math.inf)),
        ("after", (True, False, True)),
        ("after", (True, False, 0.001)),
    ],
)
def test_plate_thickness_witness_gaps_require_checked_readback(
    monkeypatch, stage, answer,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    case.state.read_overrides[(stage, 1)] = answer
    with pytest.raises(RuntimeError, match="witness gap"):
        case.style()
    assert case.state.rebuilds == []
    if stage == "before":
        assert case.state.set_calls == []


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("name", "PlateThickness@SpringAnchorPad"),
        ("value", True),
        ("value", math.nan),
        ("value", 0.005),
        ("dimension", None),
        ("band", (False, 0.0, 0.0)),
        ("band", (2, math.nan, 0.0002)),
        ("owner_type", 1),
        ("owner_type", False),
        ("dangling", True),
        ("annotations", []),
        ("activate_result", False),
        ("activate_result", 1),
    ],
)
def test_plate_thickness_witnesses_reject_unexpected_model_state(
    monkeypatch, member, value,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    setattr(case.state, member, value)
    with pytest.raises(RuntimeError, match="section C-C PlateThickness"):
        case.style()
    assert case.state.set_calls == []


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("projection_scale", (-1.0, 1.0)),
        ("projection_scale", (1.0, -1.0)),
        ("projection_scale", (2.0, 1.0)),
        ("projection_offset", (0.001, 0.0)),
        ("projected_bad", math.nan),
        ("projected_bad", True),
    ],
)
def test_plate_thickness_witnesses_reject_unexpected_projected_geometry(
    monkeypatch, member, value,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    setattr(case.state, member, value)
    with pytest.raises(RuntimeError, match="projected plate|witness endpoint"):
        case.style()
    assert case.state.set_calls == []


@pytest.mark.parametrize(
    "damage",
    ["one_arrow", "nonfinite_arrow", "boolean_arrow", "arrow_level", "arrow_x",
     "missing_witness", "extra_horizontal", "witness_level", "witness_origin", "nonfinite_witness"],
)
def test_plate_thickness_witnesses_reject_arrow_and_witness_mismatch(
    monkeypatch, damage,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    if damage == "one_arrow":
        state.arrows.pop()
    elif damage in {"nonfinite_arrow", "boolean_arrow", "arrow_level", "arrow_x"}:
        coordinate, value = {
            "nonfinite_arrow": (0, math.inf), "boolean_arrow": (0, True),
            "arrow_level": (1, 0.130), "arrow_x": (0, 0.050525),
        }[damage]
        state.arrows[0][coordinate] = value
    elif damage == "missing_witness":
        state.lines.pop(0)
    elif damage == "extra_horizontal":
        state.lines.append(((0.060, 0.125), (0.080, 0.125)))
    else:
        first, second = state.lines[0]
        state.lines[0] = {
            "witness_level": ((first[0], 0.130), (second[0], 0.130)),
            "witness_origin": ((0.075, first[1]), second),
            "nonfinite_witness": ((math.nan, first[1]), second),
        }[damage]
    with pytest.raises(RuntimeError, match="native|witness"):
        case.style()
    assert state.set_calls == []


@pytest.mark.parametrize(
    "damage", ["old_ink", "tail", "arrow", "origin", "detached", "replacement", "band", "value"],
)
def test_settled_plate_thickness_check_reads_regenerated_native_ink(
    monkeypatch, damage,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    settled_check = case.style()
    state.active_sheet = drawing.SHEET_NAMES[1]  # The thread check visits this sheet last.
    writes = list(state.set_calls)
    if damage == "old_ink":
        # Settings persist, but a later regeneration draws the old continuation.
        state.lines[0] = ((0.084975, 0.12746), (0.048525, 0.12746))
    elif damage == "tail":
        state.lines[0] = (state.lines[0][0], (0.047525, 0.12746))
    elif damage == "arrow":
        state.arrows[0][1] = 0.130
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
        state.band = (0, 0.0, 1e-13)  # Even a tiny native band drift is not ours to accept.
    else:
        state.value += 1e-13
    with pytest.raises(RuntimeError, match="section C-C PlateThickness"):
        settled_check()
    assert state.set_calls == writes


def test_plate_section_returns_its_settled_native_witness_check(monkeypatch) -> None:
    case = _native_plate_thickness(monkeypatch)
    cut_state = SimpleNamespace(surface_only=False)
    cut = SimpleNamespace(
        SetDisplayOnlySurfaceCut=lambda value: setattr(cut_state, "surface_only", value),
        GetDisplayOnlySurfaceCut=lambda: cut_state.surface_only,
    )
    case.view.GetSection = lambda: cut
    case.view.UpdateViewDisplayGeometry = lambda: None
    monkeypatch.setattr(drawing, "create_section_view", lambda *args, **kwargs: case.view)
    monkeypatch.setattr(drawing, "_hidden_lines_removed_without_greyed_pass", lambda view: None)
    monkeypatch.setattr(drawing, "model_points_in_view", lambda *args, **kwargs: [(0.0, 0.0), (1.0, 0.0)])
    monkeypatch.setattr(drawing, "position_section_caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *args, **kwargs: [case.annotation])
    settled_check = drawing._plate_section(case.adapter, case.view)
    settled_check()
    case.state.lines[0] = ((0.084975, 0.12746), (0.048525, 0.12746))
    with pytest.raises(RuntimeError, match="witness endpoint"):
        settled_check()


@pytest.mark.parametrize(
    ("name", "radius_mm", "tol_type"),
    [
        (
            "KnifeRidgeRadius",
            sm_summing_lever_spec.KNIFE_RIDGE_R,
            sm_summing_lever_spec.KNIFE_RIDGE_R_TOL_TYPE,
        ),
        (
            "StubRootRadius",
            sm_summing_lever_spec.STUB_ROOT_R,
            sm_summing_lever_spec.INSIDE_CORNER_R_TOL_TYPE,
        ),
        (
            "RibEndRadius",
            sm_summing_lever_spec.RIB_END_R,
            sm_summing_lever_spec.INSIDE_CORNER_R_TOL_TYPE,
        ),
    ],
)
def test_radius_import_requires_its_own_native_radius_and_maximum(
    monkeypatch, name, radius_mm, tol_type
) -> None:
    tolerance = SimpleNamespace(Type=tol_type)
    dimension = SimpleNamespace(SystemValue=radius_mm / 1000.0, Tolerance=tolerance)
    display = SimpleNamespace(
        Diametric=False,
        GetDimension2=lambda _index: dimension,
        GetText=lambda _part: "2X R",
    )
    annotation = SimpleNamespace(
        name=name, GetSpecificAnnotation=lambda: display,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, value: value.name)
    kwargs = {"name": name, "radius_mm": radius_mm, "tol_type": tol_type}
    drawing._assert_native_max_radius(None, [annotation], **kwargs)
    dimension.SystemValue += 0.0001
    with pytest.raises(RuntimeError, match="does not measure"):
        drawing._assert_native_max_radius(None, [annotation], **kwargs)
    dimension.SystemValue = radius_mm / 1000.0
    tolerance.Type = 0
    with pytest.raises(RuntimeError, match="lost its native MAX"):
        drawing._assert_native_max_radius(None, [annotation], **kwargs)
    tolerance.Type = tol_type
    display.Diametric = True
    with pytest.raises(RuntimeError, match="not a radial dimension"):
        drawing._assert_native_max_radius(None, [annotation], **kwargs)
    display.Diametric = False
    with pytest.raises(RuntimeError, match=f"expected one {name}"):
        drawing._assert_native_max_radius(None, [annotation, annotation], **kwargs)
    annotation.name = "Other" + name
    with pytest.raises(RuntimeError, match=f"expected one {name}"):
        drawing._assert_native_max_radius(None, [annotation], **kwargs)


@pytest.mark.parametrize("visible", [False, True])
def test_tangent_display_requires_native_mode_readback(monkeypatch, visible) -> None:
    updates = []
    view = SimpleNamespace(
        mode=2 if not visible else 0,
        GetDisplayTangentEdges2=lambda: view.mode,
        GetName2=lambda: "fillet view",
        UpdateViewDisplayGeometry=lambda: updates.append(True),
    )
    view.SetDisplayTangentEdges2 = lambda mode: setattr(view, "mode", mode)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    drawing._set_tangent_edges(view, visible=visible)
    assert view.mode == (2 if visible else 0)
    assert updates == [True]
    view.mode = 0 if visible else 2
    view.SetDisplayTangentEdges2 = lambda _mode: None
    with pytest.raises(RuntimeError, match="tangent edges did not become"):
        drawing._set_tangent_edges(view, visible=visible)


@pytest.mark.parametrize(
    ("name", "arc_mm", "centre", "radius", "signs"),
    [
        (
            "StubRootRadius",
            drawing.STUB_ROOT_ARC_MM,
            (0.1027, 0.2225),
            0.0025,
            (-1.0, 1.0),
        ),
        (
            "RibEndRadius",
            drawing.RIB_END_ARC_MM,
            (0.056, 0.069),
            0.004,
            (1.0, -1.0),
        ),
    ],
)
def test_radius_arrow_landing_rejects_invisible_extension_and_air(
    monkeypatch, name, arc_mm, centre, radius, signs
) -> None:
    arc_xy = [
        centre,
        (centre[0] + signs[0] * radius, centre[1]),
        (centre[0], centre[1] + signs[1] * radius),
    ]
    offset = tuple(sign * radius / math.sqrt(2.0) for sign in signs)
    state = SimpleNamespace(
        tip=tuple(c + d for c, d in zip(centre, offset)),
        count=1,
        dangling=False,
    )
    data = SimpleNamespace(
        GetArrowHeadCount=lambda: state.count,
        GetArrowHeadAtIndex2=lambda _index: (*state.tip, 0.0, *([0.0] * 9)),
    )
    display = SimpleNamespace(GetDisplayData=lambda: data)
    annotation = SimpleNamespace(
        GetSpecificAnnotation=lambda: display,
        IsDangling=lambda: state.dangling,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda *_args: name)
    monkeypatch.setattr(drawing, "model_points_in_view", lambda *_args, **_kwargs: arc_xy)
    kwargs = {"name": name, "arc_mm": arc_mm}
    drawing._assert_radius_arrow_lands(None, None, [annotation], **kwargs)
    # Same complete circle, opposite non-material quarter: the original K/J
    # metadata and flag checks accepted this visibly floating native arrow.
    state.tip = tuple(c - d for c, d in zip(centre, offset))
    with pytest.raises(RuntimeError, match="does not land on its visible fillet arc"):
        drawing._assert_radius_arrow_lands(None, None, [annotation], **kwargs)
    # Right sector but floating away from the material still must fail.
    state.tip = tuple(c + 1.5 * d for c, d in zip(centre, offset))
    with pytest.raises(RuntimeError, match="does not land on its visible fillet arc"):
        drawing._assert_radius_arrow_lands(None, None, [annotation], **kwargs)
    state.tip = tuple(c + d for c, d in zip(centre, offset))
    state.count = 0
    with pytest.raises(RuntimeError, match="exactly one native radial arrow"):
        drawing._assert_radius_arrow_lands(None, None, [annotation], **kwargs)
    state.count = 1
    state.dangling = True
    with pytest.raises(RuntimeError, match="native radius is dangling"):
        drawing._assert_radius_arrow_lands(None, None, [annotation], **kwargs)


def _native_middle_rib_profile(monkeypatch, *, reverse=False, alternate=False):
    """Expose native sketch points through the view's referenced part, in metres."""
    vertex_mm = (lever_build.RIB_PLATE_REACH, 0.0, 0.0)
    upper_mm = (6.496716083916082, 13.785872483270184, 0.0)
    lower_mm = (6.496716083916082, -13.785872483270184, 0.0)
    if alternate:
        # A source-reading seam must interpolate what is actually in the native
        # sketch, not silently regenerate the nominal tangent from constants.
        upper_mm, lower_mm = (8.0, 14.5, 0.0), (7.2, -13.5, 0.0)

    def point(mm):
        return SimpleNamespace(**dict(zip("XYZ", (value / 1000.0 for value in mm), strict=True)))

    def line(start, end):
        segment = SimpleNamespace(start=point(start), end=point(end), GetType=lambda: 0)
        segment.GetStartPoint2 = lambda: segment.start
        segment.GetEndPoint2 = lambda: segment.end
        return segment

    upper = line(upper_mm, vertex_mm) if reverse else line(vertex_mm, upper_mm)
    lower = line(vertex_mm, lower_mm) if reverse else line(lower_mm, vertex_mm)
    state = SimpleNamespace(
        segments=[
            line((-76.2, 0.0, 0.0), (-3.048, 14.9, 0.0)),
            lower, SimpleNamespace(GetType=lambda: 1), upper,
        ],
        feature_present=True, sketch_present=True, lookups=[],
    )
    sketch = SimpleNamespace(GetSketchSegments=lambda: state.segments)
    feature = SimpleNamespace(
        GetSpecificFeature2=lambda: sketch if state.sketch_present else None,
    )

    def feature_by_name(name):
        state.lookups.append(name)
        assert name == "MiddleRibProfile"
        return feature if state.feature_present else None

    part = SimpleNamespace(FeatureByName=feature_by_name)
    view = SimpleNamespace(ReferencedDocument=part)

    def drawing_feature_lookup(_name):
        raise AssertionError("native profile must come from the referenced part, not the drawing")

    def attr_or_call(value, name):
        member = getattr(value, name)
        return member() if callable(member) else member

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(FeatureByName=drawing_feature_lookup),
        _get_attr_or_call=attr_or_call,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    return SimpleNamespace(
        adapter=adapter, view=view, state=state, upper=upper, lower=lower,
        upper_mm=upper_mm, lower_mm=lower_mm, vertex_mm=vertex_mm,
    )


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("alternate", [False, True])
def test_middle_rib_extensions_interpolate_the_actual_referenced_native_tangents(
    monkeypatch, reverse, alternate,
) -> None:
    case = _native_middle_rib_profile(monkeypatch, reverse=reverse, alternate=alternate)
    extensions = drawing._middle_rib_source_tangents(case.adapter, case.view)
    assert len(extensions) == 2
    assert case.state.lookups == ["MiddleRibProfile"]
    by_height = sorted(extensions, key=lambda endpoints: endpoints[0][1])
    for (join, vertex), tangent in zip(
        by_height, (case.lower_mm, case.upper_mm), strict=True,
    ):
        tx, ty, _tz = tangent
        plate_y = math.copysign(lever_build.PLATE_T / 2.0, ty)
        expected_x = case.vertex_mm[0] + (
            tx - case.vertex_mm[0]
        ) * abs(plate_y / ty)
        assert join == pytest.approx((expected_x, plate_y, 0.0))
        assert vertex == pytest.approx(case.vertex_mm)
        assert tx < join[0] < vertex[0]
    if not alternate:
        assert by_height[0][0][0] == pytest.approx(30.360182182011)
        assert by_height[1][0][0] == pytest.approx(30.360182182011)


@pytest.mark.parametrize(
    "damage",
    [
        "missing-part", "missing-feature", "missing-sketch", "missing-segments",
        "missing-lower", "duplicate-upper", "missing-vertex", "off-plane-vertex",
        "endpoint-inside-plate", "endpoint-negative-x", "off-plane-endpoint",
        "nonfinite-endpoint",
    ],
)
def test_middle_rib_extensions_refuse_incomplete_or_ambiguous_native_profiles(
    monkeypatch, damage,
) -> None:
    case = _native_middle_rib_profile(monkeypatch)
    if damage == "missing-part":
        case.view.ReferencedDocument = None
    elif damage == "missing-feature":
        case.state.feature_present = False
    elif damage == "missing-sketch":
        case.state.sketch_present = False
    elif damage == "missing-segments":
        case.state.segments = None
    elif damage == "missing-lower":
        case.state.segments.remove(case.lower)
    elif damage == "duplicate-upper":
        case.state.segments.append(case.upper)
    elif damage == "missing-vertex":
        case.upper.start.X += 0.00001
    elif damage == "off-plane-vertex":
        case.upper.start.Z = 0.00001
    elif damage == "endpoint-inside-plate":
        case.upper.end.Y = lever_build.PLATE_T / 2000.0
    elif damage == "off-plane-endpoint":
        case.upper.end.Z = 0.00001
    elif damage == "nonfinite-endpoint":
        case.upper.end.X = math.nan
    else:
        case.upper.end.X = -case.upper.end.X
    with pytest.raises(RuntimeError, match="paired native middle-rib tangents"):
        drawing._middle_rib_source_tangents(case.adapter, case.view)


def test_middle_rib_layout_accepts_actual_finite_ink_inside_its_allocated_regions() -> None:
    drawing._require_middle_rib_layout(
        {
            "section": ((0.120, 0.210, 0.150, 0.240), (0.110, 0.200, 0.160, 0.250)),
            "plan": ((0.200, 0.020, 0.230, 0.060), (0.190, 0.010, 0.240, 0.070)),
        },
        {"foreign-view": (0.280, 0.100, 0.320, 0.180)},
    )


@pytest.mark.parametrize("side", range(4))
def test_middle_rib_layout_rejects_actual_ink_outside_each_region_edge(side) -> None:
    region = (0.110, 0.200, 0.160, 0.250)
    inside = list(region)
    outside = list(region)
    direction = -1 if side < 2 else 1
    inside[side] -= direction * 1e-6
    outside[side] += direction * 1e-6
    drawing._require_middle_rib_layout({"section": (tuple(inside), region)}, {})
    with pytest.raises(RuntimeError, match="outside allocated"):
        drawing._require_middle_rib_layout({"section": (tuple(outside), region)}, {})


@pytest.mark.parametrize("side", ["left", "right", "below", "above"])
def test_middle_rib_layout_discriminates_two_mm_foreign_ink_clearance(side) -> None:
    section = (0.120, 0.210, 0.150, 0.240)
    region = (0.110, 0.200, 0.160, 0.250)

    def neighbor(gap):
        if side == "left":
            return (0.100, 0.210, section[0] - gap, 0.240)
        if side == "right":
            return (section[2] + gap, 0.210, 0.170, 0.240)
        if side == "below":
            return (0.120, 0.190, 0.150, section[1] - gap)
        return (0.120, section[3] + gap, 0.150, 0.260)

    drawing._require_middle_rib_layout(
        {"section": (section, region)}, {"foreign-ink": neighbor(0.002 + 1e-6)},
    )
    with pytest.raises(RuntimeError, match="crowds"):
        drawing._require_middle_rib_layout(
            {"section": (section, region)}, {"foreign-ink": neighbor(0.002 - 1e-6)},
        )


@pytest.mark.parametrize("coordinate", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("owner", ["section", "foreign"])
def test_middle_rib_layout_refuses_nonfinite_actual_ink(coordinate, owner) -> None:
    section = (0.120, 0.210, 0.150, 0.240)
    region = (0.110, 0.200, 0.160, 0.250)
    foreign = (0.280, 0.100, 0.320, 0.180)
    if owner == "section":
        section = (coordinate, *section[1:])
    else:
        foreign = (coordinate, *foreign[1:])
    with pytest.raises(RuntimeError):
        drawing._require_middle_rib_layout(
            {"section": (section, region)}, {"foreign-ink": foreign},
        )


def _native_middle_rib_cut_ink(monkeypatch):
    """Native GetSectionLineInfo2 payload: segments, two arrows, two letter positions."""
    state = SimpleNamespace(
        label="L",
        values=[
            1.0, 0.0, 2.0,
            0.0, 0.120, 0.040, 0.0, 0.160, 0.040, 0.0,
            0.0, 0.160, 0.040, 0.0, 0.200, 0.040, 0.0,
            0.120, 0.040, 0.0, 0.115, 0.040, 0.0, 0.001, 0.002, 0.0,
            0.200, 0.040, 0.0, 0.205, 0.040, 0.0, 0.001, 0.003, 0.0,
            0.110, 0.045, 0.0, 0.207, 0.045, 0.0, 0.003,
        ],
    )
    section = SimpleNamespace(GetLabel=lambda: state.label)
    state.sections = [section]
    plan = SimpleNamespace(
        GetSectionLines=lambda: state.sections,
        GetSectionLineInfo2=lambda: state.values,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    return SimpleNamespace(state=state, plan=plan)


def test_middle_rib_cut_ink_bounds_each_native_line_arrow_and_letter(monkeypatch) -> None:
    case = _native_middle_rib_cut_ink(monkeypatch)
    ink = drawing._middle_rib_cut_ink(case.plan)
    expected = {
        "L-L cut segment 0": (0.120, 0.040, 0.160, 0.040),
        "L-L cut segment 1": (0.160, 0.040, 0.200, 0.040),
        "L-L cut arrow 0": (0.113, 0.038, 0.122, 0.042),
        "L-L cut arrow 1": (0.197, 0.037, 0.208, 0.043),
        "L-L cut letter 0": (0.110, 0.042, 0.113, 0.045),
        "L-L cut letter 1": (0.207, 0.042, 0.210, 0.045),
    }
    assert ink.keys() == expected.keys()
    for name, box in expected.items():
        assert ink[name] == pytest.approx(box)
    region = (0.100, 0.030, 0.220, 0.050)
    drawing._require_middle_rib_layout(
        {name: (box, region) for name, box in ink.items()},
        {"foreign-view": (0.240, 0.030, 0.260, 0.050)},
    )


@pytest.mark.parametrize(
    ("primitive", "coordinate_index"),
    [("segment", 7), ("arrow", 20), ("letter", 35)],
)
def test_middle_rib_native_cut_ink_cannot_escape_via_line_arrow_or_letter(
    monkeypatch, primitive, coordinate_index,
) -> None:
    case = _native_middle_rib_cut_ink(monkeypatch)
    case.state.values[coordinate_index] = 0.240
    ink = drawing._middle_rib_cut_ink(case.plan)
    region = (0.100, 0.030, 0.220, 0.050)
    with pytest.raises(RuntimeError, match=f"{primitive}.*outside allocated"):
        drawing._require_middle_rib_layout(
            {name: (box, region) for name, box in ink.items()}, {},
        )


@pytest.mark.parametrize(
    "damage",
    [
        "missing-section", "duplicate-section", "wrong-label", "missing-payload",
        "wrong-section-count", "zero-segments", "fractional-segments",
        "truncated", "extra-values", "nonfinite-segment", "nonfinite-arrow",
        "nonfinite-letter", "zero-arrow-size", "zero-letter-height",
    ],
)
def test_middle_rib_cut_ink_refuses_malformed_native_arrays(monkeypatch, damage) -> None:
    case = _native_middle_rib_cut_ink(monkeypatch)
    state = case.state
    if damage == "missing-section":
        state.sections.clear()
    elif damage == "duplicate-section":
        state.sections *= 2
    elif damage == "wrong-label":
        state.label = "Q"
    elif damage == "missing-payload":
        state.values = None
    elif damage == "wrong-section-count":
        state.values[0] = 2.0
    elif damage == "zero-segments":
        state.values[2] = 0.0
    elif damage == "fractional-segments":
        state.values[2] = 2.5
    elif damage == "truncated":
        state.values.pop()
    elif damage == "extra-values":
        state.values.append(0.0)
    elif damage == "nonfinite-segment":
        state.values[4] = math.nan
    elif damage == "nonfinite-arrow":
        state.values[20] = math.inf
    elif damage == "nonfinite-letter":
        state.values[35] = -math.inf
    elif damage == "zero-arrow-size":
        state.values[23:25] = [0.0, 0.0]
    else:
        state.values[-1] = 0.0
    with pytest.raises(RuntimeError, match="middle-rib"):
        drawing._middle_rib_cut_ink(case.plan)
