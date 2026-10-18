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
from dt_cone_pivot_post_installation import SUMMING_Z
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
    assert '"hw-threaddepth": THREAD_DEPTH' in drawing_source
    assert '"hw-tapdrldepth": DRILL_DEPTH' in drawing_source
    assert "bracket tap callout omits native depths" in drawing_source
    assert part.TAP_SPEC.size == "#2-56"
    assert part.TAP_SPEC.depth_mm == 6.05
    assert part.TAP_SPEC.overrides_mm["ThreadDepth"] == 4.95
    assert joint.THREAD_DEPTH_BAND == 0.05
    assert joint.DRILL_DEPTH_BAND == 0.10
    # The -Z rib's depth rides the title block (no native band of its own).
    assert joint.RIB_DEPTH_BAND == joint.LINEAR_BAND
    assert not hasattr(joint, "RECEIVER_DIMENSION_BANDS")
    assert "variable.ToleranceMin" in drawing_source
    assert "variable.ToleranceMax" in drawing_source
    assert "variable = dynamic_dispatch(raw._oleobj_)" in drawing_source
    assert '_early_bound(raw, "ICalloutVariable")' not in drawing_source
    assert "ReceiverY0" in drawing_source
    assert "SpringSeatThickness" in drawing.BACK_KEEP
    assert "PlateThickness" in drawing.PLATE_SECTION_TEXT_MM
    assert "RibDepth" in drawing.TOP_KEEP
    assert "Bracket Receiver Note" not in drawing_source
    assert "Manufacturing Notes" not in drawing_source
    final_proof = source.index('"summing lever after native receiver bands"')
    assert source.index("_receiver_model_bands(adapter)") < final_proof
    assert source.index("_receiver_coordinate_dimensions(adapter)") < final_proof
    assert final_proof < source.index("artefacts = await save_part_and_images")
    assert "v_built, 1e-5 * v_built" in source


def test_nothing_reads_as_an_overall_or_a_band_it_is_not() -> None:
    """Machinist review 20261018: the plan's 152.40 read as the overall (the
    stubs stand 2X 21.72 past it) and the 0.44 rib-end step as a tight band
    (it is derived from the slant and the plate)."""
    plate_length = notes.DIMENSION_CALLOUTS_BELOW["PlateLength"]
    assert " ".join(plate_length.split()) == "BODY END FACES"
    assert "PlateLength" in drawing.TOP_KEEP
    x, _ = drawing.TOP_KEEP["PlateLength"]
    widest = max(len("152.40"), *map(len, plate_length.split("\n")))
    assert x + _CHAR_M * widest / 2.0 < 0.4191 - 0.002  # under the right border
    assert notes.REFERENCE_DIMENSIONS == {"EdgeRibFrontEndStep"}
    assert set(notes.REFERENCE_DIMENSIONS) <= set(drawing.FRONT_KEEP)
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


def test_view_f_axis_reference_ties_the_plate_top_to_the_hex_centre() -> None:
    """Machinist gate 2026-10-17 on #1607: the row's 2.54 +-0.05 needs a
    located origin. The row lies on the hex centre's line, the plate is
    centred on it, and the (2.54) REF stands where the -Z end shows the
    plate's own top edge, its centreline running past the hex's flats."""
    import magnifying_bracket_joint_layout as joint

    spec = sm_summing_lever_spec
    assert all(point[1] == 0.0 for point in joint.LEVER_HOLE_POINTS)
    station = drawing.RECEIVER_AXIS_STATION_MM
    overrun = drawing.RECEIVER_AXIS_OVERRUN_MM
    outer_tap = max(point[0] for point in joint.LEVER_HOLE_POINTS)
    assert outer_tap + joint.TAP_DRILL_DIA / 2.0 < lever_build.RIB_PLATE_REACH
    assert lever_build.RIB_PLATE_REACH < station
    assert station + overrun < spec.PLATE_W
    assert overrun > 0.0 and drawing.RECEIVER_AXIS_TEXT_RISE_MM > spec.PLATE_T

    z = -spec.PLATE_L / 2.0
    half_t = spec.PLATE_T / 2.0
    reach = lever_build.RIB_PLATE_REACH
    plate_top = _line((reach, half_t, z), (spec.PLATE_W, half_t, z))
    far_top = _line((reach, half_t, -z), (spec.PLATE_W, half_t, -z))
    step = _line((reach, lever_build.edge_rib_half_height(reach), z), (reach, half_t, z))
    underside = _line((spec.PLATE_W, -half_t, z), (reach, -half_t, z))
    edges = ViewEdges(label="back", edges=(far_top, step, underside, plate_top))
    assert drawing._receiver_plate_top_edge(edges) is plate_top
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._receiver_plate_top_edge(ViewEdges(label="back", edges=(far_top, step)))

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("def _receiver_axis_reference") :]
    body = body[: body.index("\ndef ")]
    assert "-(HEX_W / 2.0 + RECEIVER_AXIS_OVERRUN_MM), 0.0, z_mm" in body
    assert "expected_mm=PLATE_T / 2.0" in body
    assert "set_reference_dimension(" in body
    assert 'orientation="vertical"' in body
    assert "_receiver_axis_reference(adapter, back, back_edges)" in source


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


def test_only_the_receiver_sheet_uses_the_greyed_regen() -> None:
    import ast
    from pathlib import Path

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    greyed = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "set_hidden_lines_removed"
            for call in ast.walk(node)
        )
    ]
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "set_hidden_lines_removed"
    ]
    assert len(calls) == 1 and len(greyed) == 1
    assert ast.unparse(greyed[0].iter) == "(back, receiver_iso)"
    direct = [
        ast.unparse(node.args[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_hidden_lines_removed_without_greyed_pass"
    ]
    assert sorted(direct) == ["detail", "native", "native", "ridge_detail", "view"]


def test_marked_dimensions_are_all_placed_and_their_callouts_land() -> None:
    keeps = {
        **drawing.FRONT_KEEP,
        **drawing.DETAIL_KEEP,
        **drawing.RIDGE_DETAIL_KEEP,
        **drawing.TOP_KEEP,
        **drawing.BACK_KEEP,
        **drawing.PLATE_SECTION_TEXT_MM,
    }
    placed = [
        *drawing.FRONT_KEEP,
        *drawing.DETAIL_KEEP,
        *drawing.RIDGE_DETAIL_KEEP,
        *drawing.TOP_KEEP,
        *drawing.BACK_KEEP,
        *drawing.PLATE_SECTION_TEXT_MM,
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
    assert set(drawing.RIDGE_DETAIL_KEEP) == {"KnifeRidgeRadius"}
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
    assert "SYMMETRIC TO SIDES" in pair
    assert "BOTH STUBS, SIDES IN ONE PLANE" in pair
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
    assert "BOTH STUBS, SIDES IN ONE PLANE" in callout
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
    drill = Dimension("Tap Drill Depth", "Sketch14", 6.05)
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
        (True, thread, 0.05, "D1@Hole Thread22"),
        (True, thread_b, 0.05, "D1@Hole Thread23"),
        (True, drill, 0.10, "Tap Drill Depth@Sketch14"),
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


def test_receiver_row_sits_inside_the_end_rib_height() -> None:
    """The row is located from the plate top, which the plate's title-block
    thickness band moves by half that band about the rib's mid-plane; both
    taps lie inside the end rib's reach, so their walls run to the rib's
    upper and lower faces, not the plate's."""
    import magnifying_bracket_joint_layout as joint

    drill_radius_max = (joint.TAP_DRILL_DIA + 0.10) / 2.0
    outer_x = max(point[0] for point in joint.LEVER_HOLE_POINTS)
    assert outer_x + drill_radius_max + joint.POSITION_BAND < lever_build.RIB_PLATE_REACH
    row_offset_max = joint.POSITION_BAND + joint.LINEAR_BAND / 2.0
    rib_half_min = (
        lever_build.edge_rib_half_height(outer_x + drill_radius_max + joint.POSITION_BAND)
        - joint.LINEAR_BAND / 2.0
    )
    wall = rib_half_min - row_offset_max - drill_radius_max - joint.DRILL_WANDER_MAX
    assert wall == pytest.approx(3.18390, abs=1e-5)
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
    assert far_z > end_z + joint.DRILL_DEPTH + joint.DRILL_DEPTH_BAND
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
