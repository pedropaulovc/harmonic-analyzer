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
from _inch_wall_limits import WALL_TARGET_MM
from _layout_geometry import Box, Segment, segment_box_distance, segment_box_overlap_length
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
    # At .300 in pitch the row spans 144.78; the body's -Z end stands .25 in
    # farther out than its +Z end (#1038 owner ruling 4), so both end taps
    # keep more than the old j=0 end distance (5.572).
    assert spec.PLATE_Z_PLUS == pytest.approx(76.2)
    assert spec.PLATE_Z_MINUS == pytest.approx(-82.55)
    assert spec.HOLE_END_OFFSET_FIRST == pytest.approx(6.5685, abs=5e-4)
    assert spec.HOLE_END_OFFSET_LAST == pytest.approx(7.4015, abs=5e-4)
    # drawing-guidelines.md rule 17 (walls and webs): each end tap keeps the
    # .080 target to its plate end at the printed length, position and thread
    # limits; the spec refuses at import below it.
    assert spec.SPRING_TAP_END_WALL_MIN == WALL_TARGET_MM
    assert spec.SPRING_TAP_END_WALL_MINUS == pytest.approx(4.4349, abs=5e-4)
    assert spec.SPRING_TAP_END_WALL_PLUS == pytest.approx(5.5219, abs=5e-4)
    assert min(spec.SPRING_TAP_END_WALL_MINUS, spec.SPRING_TAP_END_WALL_PLUS) >= WALL_TARGET_MM


def _spec_with_values(**values):
    """Run the real spec, and so its import-time guards, with changed inputs."""
    path = Path(sm_summing_lever_spec.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    replaced = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in values:
                    node.value = ast.parse(repr(values[target.id]), mode="eval").body
                    replaced.add(target.id)
    assert replaced == values.keys()
    namespace = {"__name__": "sm_summing_lever_spec_mutant"}
    exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), namespace)
    return namespace


@pytest.mark.parametrize(("values", "end"), [
    # The 6.00 plate the .300 in row outgrew (#1038 conflict 3).
    ({"PLATE_Z_MINUS": -76.2}, "-Z"),
    ({"PLATE_Z_PLUS": 72.0}, r"\+Z"),
    # The channel stations walk the whole row toward either end.
    ({"CHANNEL_Z0": -76.0}, "-Z"),
    ({"CHANNEL_Z0": -66.0}, r"\+Z"),
    ({"CHANNEL_PITCH": 8.0}, r"\+Z"),
])
def test_spec_refuses_an_end_tap_without_its_rule_17_wall(values, end) -> None:
    with pytest.raises(AssertionError, match=rf"spring-tap row: the {end} end tap keeps"):
        _spec_with_values(**values)


def test_end_wall_guard_charges_length_band_position_zone_and_thread_major() -> None:
    spec = sm_summing_lever_spec
    unchanged = _spec_with_values(PLATE_Z_MINUS=spec.PLATE_Z_MINUS)
    assert unchanged["SPRING_TAP_END_WALL_MINUS"] == spec.SPRING_TAP_END_WALL_MINUS
    # #6-32 major .138 in, over the purchased hook's shank and neck.
    assert spec.SPRING_TAP_WALL_RADIUS == pytest.approx(0.138 * 25.4 / 2.0)
    assert spec.SPRING_TAP_WALL_RADIUS >= ANCHOR_9489T111.thread_major_dia_mm / 2.0
    charged = (
        spec.SPRING_TAP_WALL_RADIUS
        + 0.005 * 25.4  # half the Ø.010 position zone
    )
    # Datum B's end carries no length band (the row is BASIC from it); the
    # -Z end is also short by the 6.25 length's .XX band.
    assert spec.SPRING_TAP_END_WALL_PLUS == pytest.approx(spec.HOLE_END_OFFSET_LAST - charged)
    assert spec.SPRING_TAP_END_WALL_MINUS == pytest.approx(
        spec.HOLE_END_OFFSET_FIRST - charged - 0.01 * 25.4
    )
    # Walk the row to each end's limit: 1 um inside passes, 1 um past refuses.
    for end, wall, toward in (
        ("-Z", spec.SPRING_TAP_END_WALL_MINUS, -1.0),
        (r"\+Z", spec.SPRING_TAP_END_WALL_PLUS, 1.0),
    ):
        spare = wall - WALL_TARGET_MM
        assert spare > 0.0
        _spec_with_values(CHANNEL_Z0=spec.CHANNEL_Z0 + toward * (spare - 1e-3))
        with pytest.raises(AssertionError, match=f"the {end} end tap keeps"):
            _spec_with_values(CHANNEL_Z0=spec.CHANNEL_Z0 + toward * (spare + 1e-3))


def _line(start, end):
    return ViewEdge(object(), (start, end), None, None)


def test_end_face_edge_rejects_inboard_flange_and_hidden_underside() -> None:
    """Datum B and the start-Z BASIC belong to the physical +Z end face."""
    spec = sm_summing_lever_spec
    z = spec.PLATE_Z_PLUS
    top = _line((0.0, 15.24, z), (30.0, 6.0, z))
    flange = _line((0.0, 15.24, z - spec.RIB_T), (30.0, 6.0, z - spec.RIB_T))
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
    with pytest.raises(RuntimeError, match=r"measures 7\.62\d* mm, expected 8\.43"):
        assert_dimension_measures(
            identity, _dimension(pitch, (seed, second)), expected_mm=8.43,
            label="spring-hole start Z", entities=(seed, second),
        )


    # False-return/no-effect selection also has a wrong count. Those independent
    # guards legitimately mask one another; this is a pre-creation behavior
    # contract, not a claim to isolate the return guard from the count guard.


def test_knife_height_location_budgets_whole_right_hand_text_and_route():
    """Projection of R2 VIEW F geometry/ink, not regenerated native proof."""
    x, y = drawing.KNIFE_HEIGHT_LOCATION_XY
    # R2 PlateThickness and receiver readbacks establish model origin X314.3625,
    # Y150 mm; *Back reverses X. The boss's actual right end is X400.0875 mm.
    spec = sm_summing_lever_spec
    boss_end = 0.3143625 - spec.TIP_X / 1000.0 + spec.ANCHOR_R / 1000.0
    assert x - boss_end >= 0.003
    # Same ordinary four-character native row/shoulder as the measured 7.00.
    text = Box(x, y - 0.0027781, x + 0.0116375, y + 0.0007219)
    assert 0.4318 - 0.0127 - text.xmax >= 0.00357
    neighbors = (
        Box(0.3289257, 0.1066122, 0.3894868, 0.1213316),  # whole tap callout
        Box(0.3049167, 0.1731656, 0.3550833, 0.1877781),  # ReceiverX0 and both rows
        Box(0.2154417, 0.1689437, 0.2645584, 0.178),  # ReceiverX1 and mate row
        Box(0.2038833, 0.1529437, 0.253, 0.162),  # ReceiverY0 and mate row
        Box(0.2513625, 0.1302219, 0.263, 0.1337219),  # complete 7.00
        Box(0.2597443, 0.0796524, 0.3302765, 0.084418),  # VIEW F caption
        Box(0.3216982, 0.2007008, 0.4074806, 0.2054665),  # pictorial caption
    )
    column = Segment(x, text.ymin, x, 0.150 + spec.HEX_H / 2000.0 + 0.00635)
    assert all(text.gap(neighbor) >= 0.00357 for neighbor in neighbors)
    assert all(segment_box_distance(column, neighbor) >= 0.00357 for neighbor in neighbors)


def test_bracket_receiver_retains_the_blind_native_contract_and_final_proof() -> None:
    import build_sm_summing_lever as part
    import magnifying_bracket_joint_layout as joint
    assert part.LEVER_HOLE_POINTS is joint.LEVER_HOLE_POINTS
    assert part.TAP_SPEC is joint.TAP_SPEC
    assert (part.TAP_SPEC.kind, part.TAP_SPEC.end) == ("tapped_bottoming", "blind")
    # Native depth/band behavior is exercised by the adapter tests below.
    assert part.TAP_SPEC.size == "#2-56"
    assert part.TAP_SPEC.depth_mm == 6.604
    assert part.TAP_SPEC.overrides_mm["ThreadDepth"] == 4.95
    assert joint.THREAD_DEPTH_BAND == 0.0508
    # Printed .26 +/-.01 (the lever's .XX row) about the 6.604 model depth.
    assert joint.DRILL_DEPTH_DEVIATIONS == pytest.approx((-0.254, 0.254))
    assert "PlateThickness" in drawing.BACK_KEEP
    assert "EdgeRibThickness" in drawing.TOP_KEEP


def test_receiver_pilot_continues_from_uniform_rib_into_connected_plate() -> None:
    """Screen ordinary pilot walls, not finished thread walls or strength."""
    import magnifying_bracket_joint_layout as joint

    spec = sm_summing_lever_spec
    drill_radius_max = joint.receiver_pilot_radius_max()
    wander = math.tan(math.radians(joint.DRILL_WANDER_DEG)) * (
        joint.DRILL_DEPTH_MAX + drill_radius_max * joint.DRILL_POINT_H
    )
    rib_t = (spec.RIB_T + spec.RIB_T_DEVIATIONS[0], spec.RIB_T + spec.RIB_T_DEVIATIONS[1])
    for x, y, _z in joint.LEVER_HOLE_POINTS:
        assert x - joint.POSITION_BAND - drill_radius_max > spec.CYL_R
        assert x + joint.POSITION_BAND + drill_radius_max < spec.RIB_REACH
        assert spec.COEFFICIENT_TOP_Y - y == pytest.approx(3.2512)  # .128 in
    assert rib_t[1] < joint.DRILL_DEPTH_MIN
    assert rib_t[0] < joint.THREAD_DEPTH
    # ReceiverY0 is from the actual top: top-position variation cancels.
    upper_plate_wall = (
        joint.LEVER_RECEIVER_ROW_FROM_TOP - joint.POSITION_BAND - drill_radius_max - wander
    )
    lower_plate_wall = (
        spec.COEFFICIENT_T + spec.COEFFICIENT_T_DEVIATIONS[0] - joint.LEVER_RECEIVER_ROW_FROM_TOP
        - joint.POSITION_BAND - drill_radius_max - wander
    )
    assert upper_plate_wall == pytest.approx(2.221735, abs=1e-6)
    assert lower_plate_wall == pytest.approx(2.577335, abs=1e-6)
    assert joint.receiver_pilot_material_wall_budget() == pytest.approx(
        min(upper_plate_wall, lower_plate_wall),
    )
    assert joint.RECEIVER_PILOT_MATERIAL_WALL_MIN >= joint.RECEIVER_PILOT_WALL_MIN


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
    assert set(notes.DIMENSION_CALLOUTS_BELOW) <= set(keeps)
    for name, _prefix in notes.DIMENSION_PREFIXES:
        assert name in notes.DRAWING_DIMENSIONS


def test_one_three_rib_size_leaves_the_distinct_counter_web_top_flush() -> None:
    spec = sm_summing_lever_spec
    assert lever_build.RIB_T == spec.RIB_T == 5.08
    assert spec.COUNTER_WEB_T == spec.COEFFICIENT_T == 7.0
    assert spec.COUNTER_WEB_T / 2.0 == spec.COEFFICIENT_TOP_Y == 3.5
    assert -spec.COUNTER_WEB_T / 2.0 == spec.COEFFICIENT_BOTTOM_Y == -3.5
    assert notes.DRAWING_DIMENSIONS["EdgeRibFront"] == {"EdgeRibThickness"}
    assert notes.DIMENSION_PREFIXES[("EdgeRibFront", "EdgeRibThickness")] == "3X "
    rib_dimensions = {
        name for names in notes.DRAWING_DIMENSIONS.values() for name in names
        if name in {"RibDepth", "MiddleRibThickness", "EdgeRibThickness"}
    }
    assert rib_dimensions == {"EdgeRibThickness"}


def test_three_rib_size_clears_boss_witness_and_complete_neighbors() -> None:
    """Replay the R2 native/PDF envelopes, not proof of regenerated native ink."""
    # R2 20261022T190921801Z-dbfece22b19a4d68ac2dd248e5168731,
    # reports/layout-audit/sm-summing-lever.json, Lever Geometry / Drawing View2.
    # Native rows/lines are rounded to 0.1 um; PDF spans are measured ink.
    old_x, old_y = 0.2095, 0.1035
    x, y = drawing.TOP_KEEP["EdgeRibThickness"]
    dx = x - old_x
    assert y == old_y, "keep the rib route below the cylinder-diameter callout"
    witness = Segment(0.1972187, 0.129, 0.1972187, 0.0685219, "ext-line")
    native_text = Box(0.1911396, 0.1007219, 0.2095, 0.1042219)
    printed_text = Box(0.1925961, 0.1016558, 0.2080575, 0.1052211)
    neighbors = (
        # Every row of 76.20 / BOSS AXIS AND / MID RIB CENTRE, not its anchor.
        Box(0.1441812, 0.1137781, 0.1558187, 0.1172781),
        Box(0.1329934, 0.1082219, 0.1670066, 0.1117219),
        Box(0.1324806, 0.1026656, 0.1675195, 0.1061656),
        # Complete native diameter text, including its diameter glyph.
        Box(0.199249, 0.1071951, 0.2187511, 0.1107486),
        Box(0.221, 0.0875713, 0.2308437, 0.0900713),  # lower Ra 1.6
    )
    # The actual printed height is 3.5653 mm; retain a whole text height of air.
    clearance = 0.00357
    for recorded in (native_text, printed_text):
        assert segment_box_overlap_length(witness, recorded) == pytest.approx(recorded.height)
        placed = Box(
            recorded.xmin + dx, recorded.ymin,
            recorded.xmax + dx, recorded.ymax,
        )
        assert segment_box_distance(witness, placed) >= clearance
        assert all(placed.gap(neighbor) >= clearance for neighbor in neighbors)
    # TOP_KEEP moves the whole native route: its complete shoulder and both
    # outside-arrow runs must also clear the neighboring text, not just the X.
    route = (
        Segment(native_text.xmin + dx, 0.1007219, x, 0.1007219),
        Segment(x, 0.1007219, x, 0.0944),
        Segment(x, 0.0919, x, 0.08555),
    )
    assert all(
        segment_box_distance(segment, neighbor) >= clearance
        for segment in route for neighbor in neighbors
    )


def test_the_knife_edge_prints_its_ridge_and_flanks_to_the_sides() -> None:
    """Code review C09 (owner ruling T1): Detail D holds the ridge sharp
    .159 +/-.002 from each side face and each upper flank 122.4 deg to its
    side face, on both stubs; the width is a reference.  The flank angle
    prints at the title block's ±1° (rulings.md D24)."""
    from _printed_tolerance import angular_band_deg

    spec = sm_summing_lever_spec
    knife = notes.DRAWING_DIMENSIONS["KnifeEnvelopeReference"]
    assert knife == {
        "HexWidth", "HexHeight", "RidgeFromLeft", "RidgeFromRight", "FlankToSide", "LowerFlankToSide",
    }
    assert set(knife) <= set(drawing.DETAIL_KEEP)
    assert "KnifeRidgeRadius" in drawing.DETAIL_KEEP
    prefixes = notes.DIMENSION_PREFIXES
    assert prefixes[("KnifeEnvelopeReference", "HexWidth")] == "EACH STUB ("
    for name in ("HexHeight", "RidgeFromLeft", "RidgeFromRight"):
        assert prefixes[("KnifeEnvelopeReference", name)] == "EACH STUB "
    assert prefixes[("KnifeEnvelopeReference", "FlankToSide")] == "2X PER STUB "
    # The lower corners close the hexagon at the title block's angular row.
    assert prefixes[("KnifeEnvelopeReference", "LowerFlankToSide")] == "2X PER STUB "
    assert "LowerFlankToSide" not in notes.DIMENSION_CALLOUTS_BELOW
    assert prefixes[("KnifeRidgeFillet", "KnifeRidgeRadius")] == "EACH STUB R"
    # The knife envelope's bands link one note naming their seat once (rule
    # 4); EACH STUB states the multiplicity without a multiline prefix.
    seat_bands = ("RidgeFromLeft", "RidgeFromRight", "FlankToSide", "HexHeight")
    for name in seat_bands:
        assert notes.DIMENSION_CALLOUTS_BELOW[name] == notes.KNIFE_SEAT_NOTE_LINK, name
    assert notes.DRAWING_NOTES.count(notes.KNIFE_MOUNT_NUMBER) == 1
    assert notes.DRAWING_NOTES.startswith(f"{notes.KNIFE_SEAT_NOTE}. ")
    every_callout = notes.DIMENSION_CALLOUTS_BELOW
    assert "HexWidth" not in every_callout
    assert (spec.RIDGE_FROM_SIDE, spec.RIDGE_FROM_SIDE_TOL) == (4.040, 0.0508)
    assert spec.KNIFE_FLANK_TO_SIDE_DEG == 122.4
    assert spec.KNIFE_FLANK_TO_SIDE_TOL_DEG == angular_band_deg(unit=spec.UNIT) == 1.0
    assert not hasattr(spec, "RIDGE_ANGLE_TOL_DEG")
    assert not hasattr(spec, "KNIFE_SHOULDER_RISE")

    assert spec.DRAWING_PRECISION["KnifeEnvelopeReference"] == dict.fromkeys(
        ("HexWidth", "HexHeight", "RidgeFromLeft", "RidgeFromRight"), 3,
    )
    # The model sketch's angle is the flank-to-side angle the print rounds.
    assert round(180.0 - spec.RIDGE_ANGLE_DEG / 2.0, 1) == spec.KNIFE_FLANK_TO_SIDE_DEG


def _builder_function(name: str) -> ast.FunctionDef | ast.FunctionDef:
    tree = ast.parse(Path(lever_build.__file__).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef,)) and node.name == name:
            return node
    raise AssertionError(f"build_sm_summing_lever has no {name}()")


def _calls_in_order(node: ast.AST) -> list[ast.Call]:
    calls = [call for call in ast.walk(node) if isinstance(call, ast.Call)]
    return sorted(calls, key=lambda call: (call.lineno, call.col_offset))


def _call_name(call: ast.Call) -> str:
    func = call.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


@pytest.mark.parametrize("digits", [1, 2, -1, None])
def test_body_length_import_refuses_lost_part_authored_precision(monkeypatch, digits) -> None:
    import _drawing_dimensions as dimensions

    adapter = SimpleNamespace(_attempt=lambda action: action())
    display = SimpleNamespace(GetPrimaryPrecision2=lambda: digits)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    monkeypatch.setattr(
        dimensions._sw_type_info, "early_bound_or_flag", lambda value, *_args: value,
    )
    monkeypatch.setattr(dimensions, "dimension_name", lambda *_args: "PlateLength")
    precision = sm_summing_lever_spec.DRAWING_PRECISION["CoefficientsPlate"]
    if digits == 2:
        dimensions.assert_imported_precision(adapter, [annotation], precision)
    else:
        with pytest.raises(RuntimeError, match="part authored 2"):
            dimensions.assert_imported_precision(adapter, [annotation], precision)
    with pytest.raises(RuntimeError, match="never reached the sheet"):
        dimensions.assert_imported_precision(adapter, [], precision)


def test_counter_flank_import_contract() -> None:
    name = "MiddleRibCounterAngle"
    assert notes.DRAWING_DIMENSIONS["MiddleRibProfile"] == {name}
    assert notes.DIMENSION_PREFIXES[("MiddleRibProfile", name)] == "2X "
    assert sm_summing_lever_spec.DRAWING_PRECISION["MiddleRibProfile"] == {name: 1}
    assert drawing.FRONT_KEEP[name] == (0.216, 0.2378)


def test_layout_retains_six_views_on_two_sheets_without_a_section() -> None:
    """Pin the approved topology, not helper spelling or projection wiring."""
    assert len(drawing.SHEET_NAMES) == len(set(drawing.SHEET_NAMES)) == 2


def test_flank_shelf_clears_recorded_angular_route_and_complete_neighbors() -> None:
    """R3 native/PDF placement projection, not regenerated native acceptance."""
    # r3-sm-visual-evidence/sm-native-layout-audit.json, sheet 2 / Detail D.
    # The source arc stays seeded separately; its connector may re-solve on
    # that arc. Do not translate or freeze R3's old connector attachment.
    native_rows = (
        Box(0.0347931, 0.081, 0.0672070, 0.0845),
        Box(0.0323139, 0.0754437, 0.0696861, 0.0789437),
    )
    printed_rows = (
        Box(0.0349097, 0.0819339, 0.0670622, 0.0854993),
        Box(0.0325705, 0.0763776, 0.0696114, 0.079943),
    )
    old_connector = Segment(0.0583221, 0.1667272, 0.0696861, 0.0754438)
    assert segment_box_overlap_length(old_connector, printed_rows[1]) > 0.003
    x, y = drawing.FLANK_TEXT_XY
    dx, dy = x - 0.051, y - 0.081
    native = tuple(Box(row.xmin + dx, row.ymin + dy, row.xmax + dx, row.ymax + dy) for row in native_rows)
    printed = tuple(Box(row.xmin + dx, row.ymin + dy, row.xmax + dx, row.ymax + dy) for row in printed_rows)
    clearance = 0.00357  # one complete recorded printed cap height
    neighbors = (
        # Combined complete native/PDF blocks, not just the closest numbers.
        Box(0.0153583, 0.1388875, 0.0530416, 0.1600555),  # all four height rows
        Box(0.0251583, 0.2399375, 0.0628416, 0.2611055),  # left ridge, all four rows
        Box(0.1779316, 0.2399656, 0.2240684, 0.2555774),  # right ridge, all three rows
        Box(0.1655003, 0.2162219, 0.1964997, 0.2207211),  # complete R0.1
        Box(0.1908059, 0.0802219, 0.2151941, 0.0847865),  # reference width
        Box(0.1114999, 0.2011553, 0.1184999, 0.2093401),  # whole A symbol/triangle
        Box(0.0986641, 0.0548708, 0.1310708, 0.0710741),  # detail caption and scale
        Box(0.2038833, 0.1529437, 0.253, 0.1629992),  # complete ReceiverY0 block
        Box(0.2154417, 0.1689437, 0.2645584, 0.1789993),  # complete ReceiverX1 block
    )
    neighbor_lines = (
        Segment(0.0332, 0.0986601, 0.1139999, 0.0986601),
        Segment(0.0332, 0.2013401, 0.1139999, 0.2013401),
        Segment(0.0342, 0.0986601, 0.0342, 0.1388875),
        Segment(0.0342, 0.1611125, 0.0342, 0.2013401),
        Segment(0.0745999, 0.1766701, 0.0745999, 0.2409375),
        Segment(0.1149999, 0.2113401, 0.1149999, 0.2409656),
        Segment(0.0251583, 0.2399375, 0.1149999, 0.2399375),
        Segment(0.1149999, 0.2399656, 0.2240684, 0.2399656),
        Segment(0.0745999, 0.0792219, 0.0745999, 0.1746701),
        Segment(0.1553999, 0.0792219, 0.1553999, 0.1746701),
        Segment(0.11595, 0.2004674, 0.1639128, 0.2162219),
    )
    for row in (*native, *printed):
        assert row.xmin - 0.0127 >= clearance
        assert 0.2667 - row.ymax >= clearance
        assert all(row.gap(neighbor) >= clearance for neighbor in neighbors)
        assert all(segment_box_distance(line, row) >= clearance for line in neighbor_lines)
    # The whole recorded exterior arc and both native witness lines remain.
    # Its bounding rectangle also bounds every possible connector attachment.
    arc = Box(0.0560269, 0.1657097, 0.0745999, 0.1942428)
    witnesses = (
        Segment(0.0737559, 0.1751338, 0.05808, 0.1651734),
        Segment(0.0745999, 0.1766701, 0.0745999, 0.1952428),
    )
    # A length-plus-half-width square conservatively contains either arrow
    # direction, so the budget does not depend on arrow-vector convention.
    arrow_reach = 0.003556 + 0.000762 / 2.0
    arrows = tuple(
        Box(px - arrow_reach, py - arrow_reach, px + arrow_reach, py + arrow_reach)
        for px, py in ((0.058924, 0.1657097), (0.0745999, 0.1942428))
    )
    for row in (*native, *printed):
        assert all(row.gap(ink) >= clearance for ink in (arc, *arrows))
        assert all(segment_box_distance(line, row) >= clearance for line in witnesses)
    shelf_y = 0.0754438 + dy
    shoulder = Segment(native[1].xmin, shelf_y, native[1].xmax, shelf_y)
    connector = Box(
        min(arc.xmin, shoulder.x1), min(arc.ymin, shelf_y),
        max(arc.xmax, shoulder.x1), max(arc.ymax, shelf_y),
    )
    assert all(connector.gap(neighbor) >= clearance for neighbor in neighbors)
    assert all(segment_box_distance(shoulder, neighbor) >= clearance for neighbor in neighbors)
    # Underlining is intentional; neither that shelf nor ANY straight
    # connector on the unchanged arc may enter either complete printed row.
    assert all(connector.gap(row) >= 0.0009 for row in printed)
    assert all(segment_box_distance(shoulder, row) >= 0.0009 for row in printed)


@pytest.mark.parametrize("kind", ["width", "ridge"])
@pytest.mark.parametrize("damage", [None, "missing", "duplicate", "wrong_start", "short_tail"])
def test_local_witness_placement_rebuilds_and_checks_projected_ink(
    monkeypatch, kind, damage,
) -> None:
    """Fake-native controls; projected points are independent of recipe keeps."""
    adapter, view = object(), object()
    names = ["PlateWidth"] if kind == "width" else ["RidgeFromLeft", "RidgeFromRight"]
    annotations = [SimpleNamespace(name=name, GetSpecificAnnotation=lambda: object()) for name in names]
    events = []
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, raw: raw.name)
    monkeypatch.setattr(
        drawing, "_set_witness_gap",
        lambda _display, index, gap, *, label: events.append(("gap", label, index, gap)),
    )
    monkeypatch.setattr(
        drawing, "rebuild_drawing",
        lambda _adapter, **_kwargs: events.append(("rebuild",)),
    )

    def project_width(owner, target, points, **_kwargs):
        assert owner is adapter and target is view
        return [(0.210, 0.140), (0.210, 0.100), (0.250, 0.100)]

    def project_ridge(owner, target, point, **_kwargs):
        assert owner is adapter and target is view
        return (0.120, 0.200)

    monkeypatch.setattr(drawing, "model_points_in_view", project_width)
    monkeypatch.setattr(drawing, "model_point_in_view", project_ridge)

    def segments(_annotation):
        assert events[-1] == ("rebuild",)
        if kind == "width":
            strokes = [((x, 0.090), (x, 0.099)) for x in (0.210, 0.250)]
        else:
            strokes = [((0.120, 0.210), (0.120, 0.225))]
        if damage == "missing":
            return strokes[1:]
        if damage == "duplicate":
            return [*strokes, strokes[0]]
        if damage in ("wrong_start", "short_tail"):
            x = strokes[0][0][0]
            strokes[0] = (
                ((x, 0.097), (x, 0.099)) if damage == "short_tail" and kind == "width"
                else ((x, 0.210), (x, 0.212)) if damage == "short_tail"
                else ((x, 0.090), (x, 0.100)) if kind == "width"
                else ((x, 0.209), (x, 0.225))
            )
        return strokes

    monkeypatch.setattr(drawing, "dimension_segments", segments)
    helper = drawing._clear_plate_width_witnesses if kind == "width" else drawing._clear_ridge_witnesses
    if damage is None:
        helper(adapter, view, annotations)
        writes = [event for event in events if event[0] == "gap"]
        assert [(event[1], event[2]) for event in writes] == (
            [("PlateWidth", 0), ("PlateWidth", 1)] if kind == "width"
            else [("RidgeFromLeft", 0), ("RidgeFromRight", 0)]
        )
        assert [event[3] for event in writes] == pytest.approx(
            [0.041, 0.041] if kind == "width" else [0.010, 0.010]
        )
    else:
        with pytest.raises(RuntimeError, match="witness"):
            helper(adapter, view, annotations)


def test_both_knife_stubs_are_one_prism_read_back_coplanar() -> None:
    """Code review C09: the stubs are ONE sketch extruded end to end through
    the body, so each side face of the -Z stub is the +Z stub's plane by
    construction, and the build reads that back once the model is final."""
    assert not hasattr(lever_build, "_hex_collar")


def test_the_knife_prism_merges_into_the_pivot_between_the_stubs() -> None:
    """One prism leaves the solid unchanged only if the hexagon lies inside
    the solid cylinder between the body ends and each stub keeps its own
    21.717 overhang."""
    spec = sm_summing_lever_spec
    w2, h2, h4 = spec.HEX_W / 2.0, spec.HEX_H / 2.0, spec.HEX_H / 4.0
    vertices = [(0.0, h2), (-w2, h4), (-w2, -h4), (0.0, -h2), (w2, -h4), (w2, h4)]
    assert max(math.hypot(x, y) for x, y in vertices) < spec.CYL_R
    assert spec.HEX_Z_OUTER_PLUS - spec.PLATE_Z_PLUS == pytest.approx(spec.HEX_DEPTH)
    assert spec.PLATE_Z_MINUS - spec.HEX_Z_OUTER_MINUS == pytest.approx(spec.HEX_DEPTH)
    assert spec.HEX_Z_OUTER_PLUS - spec.HEX_Z_OUTER_MINUS == pytest.approx(
        spec.PLATE_L + 2.0 * spec.HEX_DEPTH
    )
    for name in (
        "HEX_W", "HEX_H", "HEX_DEPTH", "PLATE_Z_MINUS", "PLATE_Z_PLUS",
        "HEX_Z_OUTER_MINUS", "HEX_Z_OUTER_PLUS", "CYL_R",
    ):
        assert getattr(lever_build, name) == getattr(spec, name), name
    assert notes.DRAWING_DIMENSIONS["KnifeStubReference"] == {"KnifeStubLength"}
    assert notes.DIMENSION_PREFIXES[("KnifeStubReference", "KnifeStubLength")] == "2X "


def test_the_between_stub_ridge_bound_holds_only_with_the_sides_in_one_plane() -> None:
    """Each ridge is .159 +/-.002 from its stub's sides.  Only with both
    stubs' sides the same planes does that hold the two ridges within 0.1016
    of each other (0.0815 of hook-arm spread over the hole column); the bound,
    the callout and the one-prism build stand or fall together."""
    spec = sm_summing_lever_spec
    assert spec.KNIFE_STUB_RIDGE_OFFSET_MAX == pytest.approx(0.1016)
    assert spec.KNIFE_STUB_RIDGE_OFFSET_MAX == 2.0 * spec.RIDGE_FROM_SIDE_TOL
    assert spec.KNIFE_RIDGE_CONTACT_SPAN == pytest.approx(
        spec.KNIFE_SEAT_Z_PLUS - spec.KNIFE_SEAT_Z_MINUS
    )
    assert spec.KNIFE_SEAT_Z_PLUS == pytest.approx((spec.PLATE_Z_PLUS + spec.HEX_Z_OUTER_PLUS) / 2.0)
    assert spec.KNIFE_SEAT_Z_MINUS == pytest.approx((spec.PLATE_Z_MINUS + spec.HEX_Z_OUTER_MINUS) / 2.0)
    assert spec.KNIFE_HOOK_ARM_SPREAD_MAX == pytest.approx(0.0815, abs=5e-4)
    assert notes.DIMENSION_PREFIXES[("KnifeEnvelopeReference", "RidgeFromLeft")] == "EACH STUB "
    assert notes.DIMENSION_PREFIXES[("KnifeEnvelopeReference", "RidgeFromRight")] == "EACH STUB "
    assert lever_build.KNIFE_SIDE_PLANE_TOL == 1e-6
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
    lines = [*value.split("\n"), *notes.DIMENSION_CALLOUTS_BELOW.get(name, "").split("\n")]
    lines = [line for line in lines if line]
    # The angular arc keeps its native exterior seed; only its text is offset.
    x, y = {
        "FlankToSide": drawing.FLANK_TEXT_XY, "LowerFlankToSide": drawing.LOWER_FLANK_TEXT_XY,
    }.get(name, drawing.DETAIL_KEEP.get(name))
    half_w = _CHAR_M * max(map(len, lines)) / 2.0
    half_h = _LINE_M * len(lines) / 2.0
    return x - half_w, x + half_w, y - half_h, y + half_h, len(lines)


def _dimension_line_y(name: str, lines: int) -> float:
    return drawing.DETAIL_KEEP[name][1] - _ONE_LINE_DROP_M - _LINE_M * (lines - 1) / 2.0


def _knife_envelope_model_owners():
    """Read the native reference's endpoint owners, not left/right name guesses."""
    lines, spans, angle_lines = {}, {}, []
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
                angle_lines.append(tuple(lines[argument.id] for argument in call.args[1:3]))
    assert set(spans) == {"RidgeFromLeft", "RidgeFromRight"}
    assert len(angle_lines) == 2  # upper, then lower corner
    return spans, angle_lines


def test_back_projected_knife_detail_uses_model_owned_spans_and_exterior_angle() -> None:
    """Analytical Back-projected layout budget, not proof of native annotation ink."""
    spec = sm_summing_lever_spec
    assert drawing.DETAIL_SCALE == (10.0, 1.0)
    scale = drawing.DETAIL_SCALE[0] / 1000.0
    cx, cy = drawing.DETAIL_CENTER
    fence = drawing.DETAIL_RADIUS_MM * scale
    hw = spec.HEX_W / 2.0 * scale
    spans, (angle_lines, lower_lines) = _knife_envelope_model_owners()
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
    # Budget the actual inch text, not the pre-migration metric values.
    def inch(value, places=spec.KNIFE_ENVELOPE_PLACES):
        return f"{value / 25.4:.{places}f}".removeprefix("0")

    ridge_value = f"EACH STUB {inch(spec.RIDGE_FROM_SIDE)} ±{inch(spec.RIDGE_FROM_SIDE_TOL)}"
    blocks = {
        "HexWidth": _detail_block("HexWidth", f"EACH STUB ({inch(spec.HEX_W)})"),
        "HexHeight": _detail_block("HexHeight", f"EACH STUB {inch(spec.HEX_H)}"),
        "RidgeFromLeft": _detail_block("RidgeFromLeft", ridge_value),
        "RidgeFromRight": _detail_block("RidgeFromRight", ridge_value),
        "FlankToSide": _detail_block(
            "FlankToSide", f"2X PER STUB {spec.KNIFE_FLANK_TO_SIDE_DEG:.1f}°",
        ),
        "KnifeRidgeRadius": _detail_block(
            "KnifeRidgeRadius", f"EACH STUB R{inch(spec.KNIFE_RIDGE_R, spec.KNIFE_RIDGE_R_PLACES)} max.",
        ),
        "LowerFlankToSide": _detail_block(
            "LowerFlankToSide", f"2X PER STUB {spec.KNIFE_FLANK_TO_SIDE_DEG:.1f}°",
        ),
    }
    for name, (left, _right, _bottom, top, _lines) in blocks.items():
        assert top < _BORDER_TOP_M - 0.004, name
        assert left > _BORDER_LEFT_M + 0.002, name
    assert blocks["FlankToSide"][1] < shoulder[0] - 0.002
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
    assert blocks["HexHeight"][1] < cx - fence - 0.0015
    width_line = _dimension_line_y("HexWidth", blocks["HexWidth"][4])
    assert drawing.DETAIL_LABEL_XY[1] + 0.005 < width_line < cy - fence - 0.001
    assert blocks["HexWidth"][0] > cx + hw + 0.002
    datum_foot = vertex[1] + drawing.RIDGE_DATUM_RISE
    assert datum_foot + 0.007 < cy + fence
    # R7's complete R0.1 text must clear the x155.4 width witness, not
    # merely sit to the right of the ridge centre.
    assert blocks["KnifeRidgeRadius"][0] > 0.1554 + 0.002
    # Native single-line shoulder starts 27.8 mm left of the keep; its
    # underline overhang, not only the glyph box, must clear the witness.
    assert drawing.DETAIL_KEEP["KnifeRidgeRadius"][0] - 0.0278 > 0.1554 + 0.002
    assert blocks["KnifeRidgeRadius"][2] > datum_foot + 0.007 + 0.004
    assert blocks["KnifeRidgeRadius"][3] < pair_line - 0.004
    # The lower corner: the same +X side's shoulder, its arc in the exterior
    # wedge, its one-row text below the height's bottom witness and left of
    # the width's witness, the arc clear of the height text and width line.
    [model_lower] = set(lower_lines[0]) & set(lower_lines[1])
    [model_bottom] = set(lower_lines[0]) - {model_lower}
    [model_side_top] = set(lower_lines[1]) - {model_lower}
    lower, bottom, side_top = map(project, (model_lower, model_bottom, model_side_top))
    assert lower[0] == pytest.approx(shoulder[0]) and bottom[0] == pytest.approx(vertex[0])
    lower_x, lower_y = drawing.DETAIL_KEEP["LowerFlankToSide"]
    direction = math.degrees(math.atan2(lower_y - lower[1], lower_x - lower[0])) % 360.0
    from_flank = math.degrees(math.atan2(lower[1] - bottom[1], lower[0] - bottom[0])) % 360.0
    from_side = math.degrees(math.atan2(lower[1] - side_top[1], lower[0] - side_top[0])) % 360.0
    assert from_flank < direction < from_side
    lower_radius = math.dist((lower_x, lower_y), lower)
    assert lower[0] - lower_radius > blocks["HexHeight"][1] + 0.002
    assert lower[1] - lower_radius > width_line + 0.002
    left, right, _bottom, top, _ = blocks["LowerFlankToSide"]
    assert top < bottom[1] - 0.002 and right < lower[0] - 0.002
    assert left > _BORDER_LEFT_M + 0.002
    assert _bottom > drawing.DETAIL_LABEL_XY[1]


def test_notes_are_short_stated_shortfalls() -> None:
    for text in (
        notes.ISOMETRIC_VIEW_NOTE,
        notes.BACK_VIEW_NOTE,
        notes.FRONT_VIEW_NOTE,
        notes.DRAWING_NOTES,
    ):
        assert len(text.splitlines()) <= 4
        for word in ("RULE", "EXCEPTION", "RULING", "NYLON", "LOCTITE", "THREADLOCK"):
            assert word not in text.upper()
    # The uniform plate retains 1.5D of full #6-32 thread at its lower limit.
    assert notes.SPRING_TAP_ENGAGEMENT_MIN >= 1.5 * notes.SPRING_TAP_MAJOR_DIA
    # The 20X callout prints that full thread (round 3 read VIEW G's .20 web
    # as the plate): floored, never rounded up, and still 1.5D.
    printed = float(notes.SPRING_TAP_CALLOUT_BELOW.split()[2])
    assert notes.SPRING_TAP_CALLOUT_BELOW == "FULL THREAD .22 MIN"
    assert printed * 25.4 <= notes.SPRING_TAP_ENGAGEMENT_MIN
    assert printed >= 1.5 * 0.138
    assert not hasattr(notes, "BRACKET_RECEIVER_NOTE")
    assert "summation anchor position" not in sm_summing_lever_spec.GEOMETRIC_TOLERANCES_MM


def test_receiver_pilots_keep_independent_profile_and_connected_plate_wall_budgets() -> None:
    """The rib footprint and the beyond-rib plate continuation both matter."""
    import magnifying_bracket_joint_layout as joint
    from sm_summing_lever_profile import receiver_pilot_wall_budget

    walls = receiver_pilot_wall_budget()
    assert [wall.x_mm for wall in walls] == [point[0] for point in joint.LEVER_HOLE_POINTS]
    assert all(wall.minimum_mm >= joint.RECEIVER_PILOT_WALL_MIN for wall in walls)
    assert joint.receiver_pilot_material_wall_budget() == pytest.approx(
        joint.RECEIVER_PILOT_MATERIAL_WALL_MIN,
    )
    assert joint.RECEIVER_PILOT_MATERIAL_WALL_MIN >= joint.RECEIVER_PILOT_WALL_MIN


@pytest.mark.parametrize(
    ("name", "feature", "check_radius", "value_m", "max_type"),
    [
        ("KnifeRidgeRadius", "KnifeRidgeFillet", drawing._assert_knife_ridge_radius,
         sm_summing_lever_spec.KNIFE_RIDGE_R / 1000.0, drawing.KNIFE_RIDGE_R_TOL_TYPE),
        ("KnifeRidgeRadius", "KnifeRidgeFillet", drawing._assert_knife_ridge_radius,
         0.0001016004, drawing.KNIFE_RIDGE_R_TOL_TYPE),
    ],
)
@pytest.mark.parametrize("damage", [None, "value", "band", "diameter", "missing", "duplicate"])
def test_imported_radii_keep_the_native_model_value_and_max_band(
    monkeypatch, name, feature, check_radius, value_m, max_type, damage,
) -> None:
    # The nonexact value is a native readback within the one-nanometre
    # budget of R.004 (0.1016 mm).
    dimension = SimpleNamespace(
        FullName=f"{name}@{feature}@sm-summing-lever.SLDPRT",
        SystemValue=value_m + (0.00001 if damage == "value" else 0.0),
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


@pytest.mark.parametrize(
    ("name", "feature", "check_radius", "nominal_m", "max_type"),
    [
        ("KnifeRidgeRadius", "KnifeRidgeFillet", drawing._assert_knife_ridge_radius,
         sm_summing_lever_spec.KNIFE_RIDGE_R / 1000.0, drawing.KNIFE_RIDGE_R_TOL_TYPE),
    ],
)
@pytest.mark.parametrize("direction", [-1.0, 1.0])
@pytest.mark.parametrize("inside_budget", [True, False])
def test_radius_nominal_readback_has_one_nanometre_budget(
    monkeypatch, name, feature, check_radius, nominal_m, max_type, direction, inside_budget,
) -> None:
    value = math.nextafter(
        nominal_m + direction * 1e-9, nominal_m if inside_budget else direction * math.inf,
    )
    dimension = SimpleNamespace(
        FullName=f"{name}@{feature}@sm-summing-lever.Part", SystemValue=value,
        Tolerance=SimpleNamespace(Type=max_type),
    )
    display = SimpleNamespace(
        Diametric=False, GetDimension2=lambda _index: dimension, GetText=lambda _part: name,
    )
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda *_args: name)
    if inside_budget:
        check_radius(object(), [annotation])
    else:
        with pytest.raises(RuntimeError):
            check_radius(object(), [annotation])


def test_title_block_and_mass_material_name_one_gray_iron() -> None:
    # #1611 delegated ruling 2026-11-17 (review #2144; precedent #2334 B1):
    # the printed material is one gray-iron grade with no alternative, the
    # SolidWorks library material behind the mass properties is the same
    # iron, and the finish states the knife edges' unhardened condition.
    row = _config.parts("sm-summing-lever")
    assert row["material"] == row["material_specification"]
    assert " OR " not in row["material"]
    assert "GRAY IRON" in row["material"]
    assert "Gray" in lever_build.MATERIAL
    assert "KNIFE EDGES (AS MACHINED, NOT HARDENED)" in row["finish"]
