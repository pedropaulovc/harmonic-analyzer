"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import solidworks_mcp.adapters

import _config
from _printed_tolerance import printed_band_mm
import _drawing_attachment
import _drawing_edge_dimensions
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_edges import ViewEdge, ViewEdges
from _hole_spec import blind_cut_dia_mm
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
    with pytest.raises(RuntimeError, match=r"measures 7\.0565 mm, expected 8\.43"):
        assert_dimension_measures(
            identity, _dimension(pitch, (seed, second)), expected_mm=8.43,
            label="spring-hole start Z", entities=(seed, second),
        )


def _native_boss_face_location(monkeypatch, identity):
    spec = sm_summing_lever_spec
    upper = ViewEdge(
        object(), None,
        (spec.TIP_X, spec.ANCHOR_H / 2.0, 0.0, 0.0, 1.0, 0.0, spec.ANCHOR_R),
        None,
    )
    lower = ViewEdge(
        object(), None,
        (spec.TIP_X, -spec.ANCHOR_H / 2.0, 0.0, 0.0, 1.0, 0.0, spec.ANCHOR_R),
        None,
    )
    wrong_axis = ViewEdge(
        object(), None,
        (spec.TIP_X, spec.ANCHOR_H / 2.0, 0.0, 0.0, 0.0, 1.0, spec.ANCHOR_R),
        None,
    )
    plate = _line(
        (spec.RIB_REACH, spec.COEFFICIENT_TOP_Y, spec.PLATE_L / 2.0),
        (spec.PLATE_W, spec.COEFFICIENT_TOP_Y, spec.PLATE_L / 2.0),
    )
    inboard = _line(
        (spec.RIB_REACH, spec.COEFFICIENT_TOP_Y, spec.PLATE_L / 2.0 - spec.RIB_T),
        (spec.PLATE_W, spec.COEFFICIENT_TOP_Y, spec.PLATE_L / 2.0 - spec.RIB_T),
    )
    state = SimpleNamespace(
        edges=[lower, wrong_axis, inboard, plate, upper],
        attached=(upper.edge, plate.edge), value=(spec.ANCHOR_H / 2.0 - spec.COEFFICIENT_TOP_Y) / 1000.0,
        sign=1.0, projection_factor=1.0, precision=2, document_precision=2,
        tolerance=SimpleNamespace(Type=0), activate=True, sheets=[], picks=[], projections=[],
    )
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: state.attached,
        GetAttachedEntityTypes=lambda: (1, 1), IsDangling=lambda: False,
    )

    class NativeDimension:
        SystemValue = property(lambda self: state.value)
        Tolerance = property(lambda self: state.tolerance)

    dimension = NativeDimension()
    display = SimpleNamespace(
        GetDimension2=lambda _index: dimension, GetAnnotation=lambda: annotation,
        GetPrimaryPrecision2=lambda: state.precision,
    )

    def activate(sheet):
        state.sheets.append(sheet)
        return state.activate

    def preference(preference, option):
        assert (preference, option) == (24, 206)
        return state.document_precision

    identity.currentModel = SimpleNamespace(
        ActivateSheet=activate,
        Extension=SimpleNamespace(GetUserPreferenceInteger=preference),
    )
    front = SimpleNamespace(ScaleRatio=(1.0, 2.0))

    def project(adapter, view, points, **_kwargs):
        assert adapter is identity and view is front
        state.projections.append(points)
        return [
            (0.2 + x / 2.0, 0.1 + state.sign * y * state.projection_factor / 2.0)
            for x, y, _z in points
        ]

    def add(adapter, view, **kwargs):
        assert adapter is identity and view is front
        state.picks.append(kwargs)
        return display

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        drawing, "scan_view_edges",
        lambda _view, **_kwargs: ViewEdges(label="front", edges=tuple(state.edges)),
    )
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "add_edge_dimension", add)
    return SimpleNamespace(
        capture=lambda: drawing._boss_face_location_check(identity, front),
        state=state, upper=upper, plate=plate, front=front,
    )


@pytest.mark.parametrize("missing", ["upper", "plate"])
def test_boss_face_location_refuses_nearby_but_wrong_actual_edges(monkeypatch, identity, missing):
    case = _native_boss_face_location(monkeypatch, identity)
    case.state.edges.remove(getattr(case, missing))
    with pytest.raises(RuntimeError):
        case.capture()
    assert not case.state.picks


@pytest.mark.parametrize("settled", [False, True])
@pytest.mark.parametrize(
    "damage", ["sign", "scale", "association", "value", "precision", "tolerance", "sheet"],
)
def test_boss_face_location_rechecks_native_authority(monkeypatch, identity, settled, damage):
    case = _native_boss_face_location(monkeypatch, identity)
    check = case.capture() if settled else case.capture
    if damage == "sign":
        case.state.sign = -1.0
    elif damage == "scale":
        case.state.projection_factor = 2.0
    elif damage == "association":
        case.state.attached = (case.upper.edge, object())
    elif damage == "value":
        case.state.value += 0.0001
    elif damage == "precision":
        case.state.precision = 1
    elif damage == "tolerance":
        case.state.tolerance.Type = 2
    else:
        case.state.activate = False
    with pytest.raises(RuntimeError):
        check()


@pytest.mark.parametrize("places", [1, 2, 3])
def test_boss_face_location_reads_document_precision_when_inherited(monkeypatch, identity, places):
    case = _native_boss_face_location(monkeypatch, identity)
    case.state.precision = -2
    case.state.document_precision = places
    if places == 2:
        case.capture()()
    else:
        with pytest.raises(RuntimeError):
            case.capture()


def _native_knife_height(monkeypatch, identity):
    spec = sm_summing_lever_spec
    state = SimpleNamespace(
        selected=[], picks=[], placements=[], value=(spec.HEX_H / 2.0 - spec.COEFFICIENT_TOP_Y) / 1000.0,
        precision=2, document_precision=2, tolerance=SimpleNamespace(Type=0),
        activate=True, missing=False, dangling=False, source_y=spec.HEX_H / 2000.0,
        view_activate=True, refuse_pick=None, extra_pick_after=None, null_dimension=False,
    )
    view = SimpleNamespace(ScaleRatio=(1.0, 1.0))

    def selectable(name):
        entity = SimpleNamespace()

        def select(append, data):
            assert data.View is view and append == (name == "plate top")
            state.picks.append(name)
            if state.refuse_pick == name:
                return False  # native refusal: call recorded, selection unchanged
            state.selected.append(entity)
            if state.extra_pick_after == name:
                state.selected.append(object())
            return True

        entity.Select4 = select
        return entity

    point, edge = selectable("height.end"), selectable("plate top")
    plate = ViewEdge(
        edge,
        ((spec.RIB_REACH, spec.COEFFICIENT_TOP_Y, -spec.PLATE_L / 2.0),
         (spec.PLATE_W, spec.COEFFICIENT_TOP_Y, -spec.PLATE_L / 2.0)),
        None, None,
    )
    state.attached = (point, edge)
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: state.attached,
        GetAttachedEntityTypes=lambda: (11, 1), IsDangling=lambda: state.dangling,
        OwnerType=0, Visible=1, Owner=view,
    )

    class NativeDimension:
        SystemValue = property(lambda self: state.value)
        Tolerance = property(lambda self: state.tolerance)

    display = SimpleNamespace(
        GetDimension2=lambda _index: NativeDimension(), GetAnnotation=lambda: annotation,
        GetPrimaryPrecision2=lambda: state.precision,
    )
    state.inventory, state.annotation_count = [annotation], 1
    view.GetAnnotationCount = lambda: state.annotation_count
    view.GetAnnotations = lambda: state.inventory
    manager = SimpleNamespace(
        CreateSelectData=SimpleNamespace, GetSelectedObjectCount2=lambda _mark: len(state.selected),
    )

    def create(*position):
        state.placements.append(position)
        if state.null_dimension or state.selected != [point, edge]:
            return None
        return display

    identity.currentModel = SimpleNamespace(
        ActivateView=lambda _name: state.view_activate, ActivateSheet=lambda _name: state.activate,
        ClearSelection2=lambda _all: state.selected.clear(), SelectionManager=manager,
        AddVerticalDimension2=create,
        Extension=SimpleNamespace(GetUserPreferenceInteger=lambda *_args: state.document_precision),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "VIEW F")
    monkeypatch.setattr(
        drawing, "_theoretical_knife_vertex_in_view",
        lambda *_args: (point, (0.0, state.source_y, 0.0)),
    )
    monkeypatch.setattr(
        drawing, "scan_view_edges",
        lambda *_args, **_kwargs: ViewEdges(label="VIEW F", edges=() if state.missing else (plate,)),
    )
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, **_kwargs: [(0.3143625 - x, 0.150 + y) for x, y, _z in points],
    )
    return SimpleNamespace(
        capture=lambda: drawing._knife_height_location_check(identity, view),
        state=state, point=point, edge=edge, view=view, annotation=annotation,
    )


def test_knife_height_is_a_native_point_to_actual_plate_top_dimension(monkeypatch, identity):
    case = _native_knife_height(monkeypatch, identity)
    check = case.capture()
    check()
    assert case.state.picks == ["height.end", "plate top"]
    assert case.state.placements == [(*drawing.KNIFE_HEIGHT_LOCATION_XY, 0.0)]
    assert case.state.value * 1000.0 == pytest.approx(2.594)
    case.state.precision = -2
    check()  # ordinary precision may follow the existing document
    case.state.document_precision = 3
    with pytest.raises(RuntimeError, match="two-place"):
        check()


@pytest.mark.parametrize("damage", ["view", "point_refusal", "edge_refusal", "point_count", "edge_count"])
def test_knife_height_refuses_selection_before_attempting_native_dimension(monkeypatch, identity, damage):
    case = _native_knife_height(monkeypatch, identity)
    if damage == "view":
        case.state.view_activate = False
    elif damage.endswith("_refusal"):
        case.state.refuse_pick = "height.end" if damage == "point_refusal" else "plate top"
    else:
        case.state.extra_pick_after = "height.end" if damage == "point_count" else "plate top"
    with pytest.raises(RuntimeError, match="activate VIEW F|selection failed"):
        case.capture()
    assert case.state.placements == [], "bad native selection must not reach AddVerticalDimension2"
    assert case.state.selected == [], "failed insertion must release its native selections"
    # False-return/no-effect selection also has a wrong count. Those independent
    # guards legitimately mask one another; this is a pre-creation behavior
    # contract, not a claim to isolate the return guard from the count guard.


def test_knife_height_refuses_missing_native_dimension_before_reading_it(monkeypatch, identity):
    case = _native_knife_height(monkeypatch, identity)
    case.state.null_dimension = True
    with pytest.raises(RuntimeError, match="native vertical dimension was not created"):
        case.capture()
    assert case.state.placements == [(*drawing.KNIFE_HEIGHT_LOCATION_XY, 0.0)]
    assert case.state.selected == []


@pytest.mark.parametrize("settled", [False, True])
@pytest.mark.parametrize("damage", ["missing", "duplicate", "count", "shape"])
def test_knife_height_refuses_inconsistent_native_view_inventory(monkeypatch, identity, settled, damage):
    case = _native_knife_height(monkeypatch, identity)
    check = case.capture() if settled else case.capture
    if damage == "missing":
        case.state.inventory = [object()]  # same count, no owned annotation
    elif damage == "duplicate":
        case.state.inventory = [case.annotation, case.annotation]
        case.state.annotation_count = 2
    elif damage == "count":
        case.state.annotation_count = 0  # nonempty native array disagrees
    else:
        case.state.inventory = None
    with pytest.raises(RuntimeError, match="not visible and owned by VIEW F"):
        check()



@pytest.mark.parametrize("settled", [False, True])
@pytest.mark.parametrize("damage", ["crest", "plate", "attachment", "value", "band", "precision", "owner", "hidden", "dangling", "sheet"])
def test_knife_height_refuses_wrong_reference_or_lost_native_authority(monkeypatch, identity, settled, damage):
    case = _native_knife_height(monkeypatch, identity)
    check = case.capture() if settled else case.capture
    if damage == "crest":
        case.state.source_y -= 0.00002
    elif damage == "plate":
        case.state.missing = True
    elif damage == "attachment":
        case.state.attached = (object(), case.edge)
    elif damage == "value":
        case.state.value += 0.0001
    elif damage == "band":
        case.state.tolerance.Type = 2
    elif damage == "precision":
        case.state.precision = 3
    elif damage == "owner":
        case.annotation.Owner = object()
    elif damage == "hidden":
        case.annotation.Visible = 3
    elif damage == "dangling":
        case.state.dangling = True
    else:
        case.state.activate = False
    with pytest.raises(RuntimeError):
        check()


@pytest.mark.parametrize("damage", [
    None, "missing", "duplicate", "crest", "transform", "correspondence", "nonconstruction", "sketch_owner",
])
def test_theoretical_vertex_is_the_existing_height_endpoint_not_a_coincident_flank(monkeypatch, identity, damage):
    state = SimpleNamespace(shift=0.0, mapped=[], correspondence=True)
    half = sm_summing_lever_spec.HEX_H / 2000.0
    sketch = SimpleNamespace()

    def point(x, y):
        return SimpleNamespace(X=x, Y=y, Z=0.0, GetSketch=lambda: sketch)

    start, vertex, coincident_flank = point(0.0, -half), point(0.0, half), point(0.0, half)

    def line(first, last):
        return SimpleNamespace(
            GetType=lambda: 0, ConstructionGeometry=True,
            GetStartPoint2=lambda: first, GetEndPoint2=lambda: last,
        )

    height = line(start, vertex)
    sketch.GetSketchSegments = lambda: state.segments
    state.segments = [line(coincident_flank, point(0.00404, half / 2.0)), height]
    inverse = object()
    sketch.ModelToSketchTransform = SimpleNamespace(Inverse=lambda: inverse)

    def create_point(coordinates):
        def multiply(transform):
            assert transform is inverse
            x, y, z = coordinates
            return SimpleNamespace(ArrayData=(x, y + state.shift, z))
        return SimpleNamespace(MultiplyTransform=multiply)

    identity.swApp.GetMathUtility = lambda: SimpleNamespace(CreatePoint=create_point)
    feature = SimpleNamespace(GetSpecificFeature2=lambda: sketch)

    def feature_by_name(name):
        assert name == "KnifeEnvelopeReference"
        return feature

    mapped = object()

    def correspond(source):
        state.mapped.append(source)
        return mapped if state.correspondence else None

    view = SimpleNamespace(
        ReferencedDocument=SimpleNamespace(FeatureByName=feature_by_name),
        GetCorresponding=correspond,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "double_array", tuple)
    if damage == "missing":
        state.segments.remove(height)
    elif damage == "duplicate":
        state.segments.append(line(start, vertex))
    elif damage == "crest":
        vertex.Y -= 0.00002
    elif damage == "transform":
        state.shift = -0.00002
    elif damage == "correspondence":
        state.correspondence = False
    elif damage == "nonconstruction":
        height.ConstructionGeometry = False
    elif damage == "sketch_owner":
        vertex.GetSketch = lambda: object()
    if damage is not None:
        with pytest.raises(RuntimeError):
            drawing._theoretical_knife_vertex_in_view(identity, view)
    else:
        actual, xyz = drawing._theoretical_knife_vertex_in_view(identity, view)
        assert actual is mapped and state.mapped == [vertex]
        assert xyz == pytest.approx((0.0, half, 0.0))
        spans, _angles = _knife_envelope_model_owners()
        shared = set(spans["RidgeFromLeft"]) & set(spans["RidgeFromRight"])
        assert any(math.dist(reference, (0.0, half * 1000.0)) < 1e-9 for reference in shared)


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
    assert part.TAP_SPEC.depth_mm == 6.50
    assert part.TAP_SPEC.overrides_mm["ThreadDepth"] == 4.95
    assert joint.THREAD_DEPTH_BAND == 0.0508
    # Printed .256 +/-.005 (the lever's .XXX row) about the 6.50 model depth.
    assert joint.DRILL_DEPTH_DEVIATIONS == pytest.approx((-0.1246, 0.1294))
    assert "PlateThickness" in drawing.BACK_KEEP
    assert "EdgeRibThickness" in drawing.TOP_KEEP
    order = [_call_name(call) for call in _calls_in_order(_builder_function("build"))]
    bands = order.index("_receiver_model_bands")
    coordinates = order.index("_receiver_coordinate_dimensions")
    saved = order.index("save_part_and_images")
    assert bands < coordinates < saved
    assert "volume_check" in order[coordinates:saved]


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
        assert spec.COEFFICIENT_TOP_Y - y == pytest.approx(3.25)
    assert rib_t[1] < joint.DRILL_DEPTH_MIN
    assert rib_t[0] < joint.THREAD_DEPTH
    # ReceiverY0 is from the actual top: top-position variation cancels.
    upper_plate_wall = (
        joint.RECEIVER_ROW_FROM_TOP - joint.POSITION_BAND - drill_radius_max - wander
    )
    lower_plate_wall = (
        spec.COEFFICIENT_T + spec.COEFFICIENT_T_DEVIATIONS[0] - joint.RECEIVER_ROW_FROM_TOP
        - joint.POSITION_BAND - drill_radius_max - wander
    )
    assert upper_plate_wall == pytest.approx(2.221731, abs=1e-6)
    assert lower_plate_wall == pytest.approx(2.579731, abs=1e-6)
    assert joint.receiver_pilot_material_wall_budget() == pytest.approx(
        min(upper_plate_wall, lower_plate_wall),
    )
    assert joint.RECEIVER_PILOT_MATERIAL_WALL_MIN >= joint.RECEIVER_PILOT_WALL_MIN


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


@pytest.mark.parametrize("scale,origin", [(1.0, (0.2, 0.1)), (2.0, (0.3, 0.15))])
def test_view_f_centerline_projects_only_the_actual_relocated_receiver_row(
    monkeypatch, scale, origin,
) -> None:
    """Drive the real owned-line path through projection and sketch readback."""
    adapter, back = SimpleNamespace(), SimpleNamespace()
    transform = object()
    back.GetSketch = lambda: SimpleNamespace(ModelToSketchTransform=transform)
    projected_points, created_lines, activated = [], [], []

    def project(actual_adapter, view, points, **_kwargs):
        assert actual_adapter is adapter and view is back
        projected_points.extend(points)
        return [
            (origin[0] - scale * x, origin[1] + scale * y)
            for x, y, _z in points
        ]

    class Point:
        def __init__(self, values):
            self.ArrayData = values

        def MultiplyTransform(self, actual_transform):
            assert actual_transform is transform
            x, y, z = self.ArrayData
            return Point((x + 0.03, y - 0.02, z))

    manager = SimpleNamespace(AddToDB=False)

    def create(*coordinates):
        assert manager.AddToDB is True
        created_lines.append(coordinates)
        start, end = coordinates[:3], coordinates[3:]
        return SimpleNamespace(
            Color=-1,
            GetStartPoint2=lambda: SimpleNamespace(**dict(zip("XYZ", start))),
            GetEndPoint2=lambda: SimpleNamespace(**dict(zip("XYZ", end))),
        )

    manager.CreateCenterLine = create
    adapter.currentModel = SimpleNamespace(
        ActivateView=lambda name: activated.append(name) or True,
        ClearSelection2=lambda _all: None,
        SketchManager=manager,
    )
    adapter.swApp = SimpleNamespace(GetMathUtility=lambda: SimpleNamespace(CreatePoint=Point))
    adapter._get_attr_or_call = lambda value, name: (
        getattr(value, name)() if callable(getattr(value, name)) else getattr(value, name)
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "VIEW F")
    monkeypatch.setattr(drawing, "double_array", lambda values: values)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    segment = drawing._receiver_axis_centerline(adapter, back)
    assert activated == ["VIEW F"]
    assert projected_points == [
        pytest.approx((0.0317, -0.00071, -0.0762)),
        pytest.approx((0.0140, -0.00071, -0.0762)),
    ]
    assert created_lines == [pytest.approx((
        origin[0] - scale * 0.0317 + 0.03,
        origin[1] - scale * 0.00071 - 0.02,
        0.0,
        origin[0] - scale * 0.0140 + 0.03,
        origin[1] - scale * 0.00071 - 0.02,
        0.0,
    ))]
    assert manager.AddToDB is False
    assert segment.Color == 0




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


def test_one_three_rib_size_leaves_the_distinct_counter_web_top_flush() -> None:
    spec = sm_summing_lever_spec
    assert lever_build.RIB_T == spec.RIB_T == 5.08
    assert spec.COUNTER_WEB_T == 5.08
    assert spec.COUNTER_WEB_T / 2.0 == spec.COEFFICIENT_TOP_Y == 2.54
    assert spec.COEFFICIENT_T == 7.0
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
    .159 +/-.002 from each side face and each upper flank 122.4 +/-0.5 deg
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
    assert (spec.RIDGE_FROM_SIDE, spec.RIDGE_FROM_SIDE_TOL) == (4.040, 0.0508)
    assert (spec.KNIFE_FLANK_TO_SIDE_DEG, spec.KNIFE_FLANK_TO_SIDE_TOL_DEG) == (122.4, 0.5)
    assert not hasattr(spec, "RIDGE_ANGLE_TOL_DEG")
    assert not hasattr(spec, "KNIFE_SHOULDER_RISE")

    assert spec.DRAWING_PRECISION["KnifeEnvelopeReference"] == dict.fromkeys(
        ("HexWidth", "HexHeight", "RidgeFromLeft", "RidgeFromRight"), 3,
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


def _drawing_function(name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def test_layout_retains_six_views_on_two_sheets_without_a_section() -> None:
    """Pin the approved topology, not helper spelling or projection wiring."""
    calls = _calls_in_order(_drawing_function("build"))
    assert sum(_call_name(call) == "place_view" for call in calls) == 5
    assert sum(_call_name(call) == "_knife_detail" for call in calls) == 1
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    assert not any(
        "section" in _call_name(call).lower()
        for call in _calls_in_order(tree)
    )
    assert len(drawing.SHEET_NAMES) == len(set(drawing.SHEET_NAMES)) == 2


@pytest.mark.parametrize("index,gap", [(0, 0.010), (1, 0.0391)])
def test_local_witness_gap_persists_native_override(index, gap) -> None:
    state = SimpleNamespace(use_document=True, gap=0.0)

    def write(actual_index, use_document, value):
        assert actual_index == index
        state.use_document, state.gap = use_document, value
        return True

    display = SimpleNamespace(
        SetWitnessLineGap=write,
        GetWitnessLineGap=lambda *_args: (True, state.use_document, state.gap),
    )
    drawing._set_witness_gap(display, index, gap, label="local test")
    assert state.use_document is False
    assert state.gap == pytest.approx(gap)


@pytest.mark.parametrize("result", [False, None, 0, 1])
def test_local_witness_gap_refuses_nonboolean_native_write(result) -> None:
    def unexpected_read(*_args):
        raise AssertionError("must refuse the failed write before readback")

    display = SimpleNamespace(
        SetWitnessLineGap=lambda *_args: result, GetWitnessLineGap=unexpected_read,
    )
    with pytest.raises(RuntimeError, match="refused"):
        drawing._set_witness_gap(display, 0, 0.010, label="local test")


@pytest.mark.parametrize("answer", [
    (False, False, 0.010), (1, False, 0.010), (True, True, 0.010),
    (True, 0, 0.010), (True, False, True), (True, False, "0.010"),
    (True, False, math.nan), (True, False, math.inf), (True, False, 0.011),
])
def test_local_witness_gap_refuses_ineffective_native_override(answer) -> None:
    display = SimpleNamespace(
        SetWitnessLineGap=lambda *_args: True,
        GetWitnessLineGap=lambda *_args: answer,
    )
    with pytest.raises(RuntimeError, match="did not persist"):
        drawing._set_witness_gap(display, 0, 0.010, label="local test")


@pytest.mark.parametrize("damage", [None, "seed_write", "seed_read", "offset_flag", "shelf_read"])
def test_flank_text_refuses_failed_arc_or_shelf_placement(monkeypatch, damage) -> None:
    display = SimpleNamespace(OffsetText=True)
    state = SimpleNamespace(position=None)

    def seed(x, y, z):
        assert display.OffsetText is False
        state.position = (x + (0.001 if damage == "seed_read" else 0.0), y, z)
        return False if damage == "seed_write" else True

    annotation = SimpleNamespace(
        GetSpecificAnnotation=lambda: display, SetPosition2=seed,
        GetPosition=lambda: state.position,
    )
    adapter = object()
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, _raw: "FlankToSide")

    def offset(owner, annotations, positions):
        display.OffsetText = damage != "offset_flag"
        x, y = positions["FlankToSide"]
        state.position = (x, y + (0.001 if damage == "shelf_read" else 0.0), 0.0)

    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    if damage is None:
        drawing._place_flank_text(adapter, [annotation])
    else:
        with pytest.raises(RuntimeError, match="FlankToSide"):
            drawing._place_flank_text(adapter, [annotation])


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
    assert x == 0.051, "retain the measured horizontal shelf/neighbor relationship"
    dy = y - 0.081
    native = tuple(Box(row.xmin, row.ymin + dy, row.xmax, row.ymax + dy) for row in native_rows)
    printed = tuple(Box(row.xmin, row.ymin + dy, row.xmax, row.ymax + dy) for row in printed_rows)
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
    """Each ridge is .159 +/-.002 from its stub's sides.  Only with both
    stubs' sides the same planes does that hold the two ridges within 0.1016
    of each other (0.078 of hook-arm spread over the hole column); the bound,
    the callout and the one-prism build stand or fall together."""
    spec = sm_summing_lever_spec
    assert spec.KNIFE_STUB_RIDGE_OFFSET_MAX == pytest.approx(0.1016)
    assert spec.KNIFE_STUB_RIDGE_OFFSET_MAX == 2.0 * spec.RIDGE_FROM_SIDE_TOL
    assert spec.KNIFE_RIDGE_CONTACT_SPAN == pytest.approx(spec.HEX_Z_INNER + spec.HEX_Z_OUTER)
    assert spec.KNIFE_HOOK_ARM_SPREAD_MAX == pytest.approx(0.078, abs=5e-4)
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
    # The angular arc keeps its native exterior seed; only its text is offset.
    x, y = drawing.FLANK_TEXT_XY if name == "FlankToSide" else drawing.DETAIL_KEEP[name]
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
    assert blocks["HexHeight"][1] < cx - fence - 0.0015
    width_line = _dimension_line_y("HexWidth", blocks["HexWidth"][4])
    assert drawing.DETAIL_LABEL_XY[1] + 0.005 < width_line < cy - fence - 0.001
    assert blocks["HexWidth"][0] > cx + hw + 0.002
    datum_foot = vertex[1] + drawing.RIDGE_DATUM_RISE
    assert datum_foot + 0.007 < cy + fence
    # R7's complete R0.1 text must clear the x155.4 width witness, not
    # merely sit to the right of the ridge centre.
    assert blocks["KnifeRidgeRadius"][0] > 0.1554 + 0.002
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


def test_plan_ridge_reference_follows_datum_a_negative_z_stub(monkeypatch) -> None:
    adapter, top, segment = object(), object(), object()
    endpoints = []

    def owned_reference(actual_adapter, actual_view, ends_mm, **_kwargs):
        assert actual_adapter is adapter
        assert actual_view is top
        endpoints.extend(ends_mm)
        return segment

    monkeypatch.setattr(drawing, "_owned_centerline", owned_reference)
    assert drawing._ridge_centerline(adapter, top) is segment
    inner_z = -drawing.PLATE_L / 2.0
    assert endpoints[0] == pytest.approx((0.0, drawing.HEX_H / 2.0, inner_z))
    assert endpoints[1] == pytest.approx((
        0.0, drawing.HEX_H / 2.0,
        inner_z - drawing.HEX_DEPTH - drawing.RIDGE_AXIS_OVERRUN_MM,
    ))


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


def test_datum_c_is_the_coefficient_top_the_spring_taps_pierce(monkeypatch) -> None:
    """C is the plate top edge-on in VIEW G, tagged outboard of the free end."""
    calls = []
    edge, front = object(), object()
    spec = sm_summing_lever_spec

    def exact_line_through(point, *, label):
        assert point[1] == spec.COEFFICIENT_TOP_Y
        assert spec.RIB_REACH < point[0] < spec.PLATE_W
        return SimpleNamespace(edge=edge)

    monkeypatch.setattr(
        drawing, "scan_view_edges",
        lambda view, **kwargs: SimpleNamespace(exact_line_through=exact_line_through),
    )
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda adapter, view, points, **kwargs: [(0.25 + x, 0.236) for x, _y, _z in points],
    )
    monkeypatch.setattr(drawing, "add_datum_feature", lambda *args, **kwargs: calls.append((args, kwargs)))
    drawing._plate_top_datum(object(), front)
    (args, definition), = calls
    assert args[1] is front
    assert definition["edge_entity"] is edge and definition["datum"] == "C"
    end_x = 0.25 + spec.PLATE_W / 1000.0
    assert definition["symbol_xy"][0] > end_x  # off the part, on the extension
    assert definition["symbol_xy"][1] < 0.236  # below the line, under the boss witness



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
    import _com
    import _dimensions
    import _feature_tree
    import build_sm_summing_lever as part

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
    features = {"BracketMountingTaps": taps}
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))

    def invoke(value, interface, member, *args):
        attribute = getattr(value, member)
        if callable(attribute):
            return attribute(*args)
        assert not args
        return attribute

    monkeypatch.setattr(_com, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_feature_tree, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_com, "_com_invoke", invoke)
    monkeypatch.setattr(_dimensions, "_com_invoke", invoke)
    monkeypatch.setattr(_feature_tree, "_com_invoke", invoke)
    held = []
    monkeypatch.setattr(
        part, "_band_held_dimension",
        lambda display, dimension, band, label: held.append(
            (display.GetDimension2(0) is dimension, dimension, band, label)
        ),
    )
    inventory = []
    monkeypatch.setattr(part._telemetry, "info", inventory.append)
    part._receiver_model_bands(adapter)
    # Subfeatures are not FeatureByName-reachable and both threads are "D1":
    # band the exact native objects found in the walk, never a by-name lookup.
    assert held == [
        (True, thread, (-0.0508, 0.0508), "D1@Hole Thread22"),
        (True, thread_b, (-0.0508, 0.0508), "D1@Hole Thread23"),
        (True, drill, (-0.127, 0.127), "Tap Drill Depth@Sketch14"),
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
    with pytest.raises(RuntimeError, match="expected 2 native FullThreadDepth .*found 0"):
        part._receiver_model_bands(adapter)
    assert inventory and any("D1@Hole Thread22" in row for row in inventory)
    # Two depths on ONE cosmetic thread (one hole uncovered) is ambiguous.
    taps.children = (sketch_feature, thread_feature)
    thread_feature.next_subfeature = None
    sketch_feature.next_subfeature = thread_feature
    thread_feature.displays.append(display(Dimension("D9", thread_feature.Name, 4.95)))
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
        GetPrimaryPrecision2=lambda: 3,
    )
    monkeypatch.setattr(_com, "_bind", lambda value, _kind: value)
    monkeypatch.setattr(_com, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(_drawing_tolerances, "_set_tolerance_precision", lambda *args, **kwargs: None)
    lever_build._band_held_dimension(
        display, SimpleNamespace(Tolerance=tolerance),
        (-joint.DRILL_DEPTH_BAND, joint.DRILL_DEPTH_BAND), "native receiver drill",
    )
    assert tolerance.Type == 4  # swTolSYMMETRIC, not bilateral or MIN
    assert (tolerance.lower, tolerance.upper) == pytest.approx((-0.000127, 0.000127))


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


def test_bracket_depth_callout_inherits_printed_three_place_band(bracket_depth_callout) -> None:
    import magnifying_bracket_joint_layout as joint

    case = bracket_depth_callout
    unrelated_before = (dict(case.unrelated.metadata.values), dict(case.unrelated.length.values))
    case.dress()
    assert case.drill.metadata.ToleranceType == 0  # swTolNONE: title-block presentation
    assert case.drill.length.Precision == 3
    assert case.drill.length.Length == pytest.approx(0.00650)
    # NONE hides the native variable's unused tolerance fields; dressing must
    # not write them or assume SOLIDWORKS retains hidden deviations.
    assert case.drill.metadata.writes == [("ToleranceType", 0)]
    assert case.drill.length.writes == [("Precision", 3)]
    assert case.thread.metadata.ToleranceType == 5  # swTolMIN, not a bilateral thread depth
    assert case.thread.length.Length == pytest.approx(0.00495)
    assert case.thread.length.writes == []
    assert (case.thread.metadata.ToleranceMin, case.thread.metadata.ToleranceMax) == (0.0, 0.0)
    assert (case.unrelated.metadata.values, case.unrelated.length.values) == unrelated_before
    assert case.unrelated.metadata.writes == case.unrelated.length.writes == []
    assert case.bound == [case.thread.raw, case.drill.raw]
    assert case.dispatched == [case.unrelated.metadata, case.thread.metadata, case.drill.metadata]

    # Derive the effective band from the printed inch nominal and the actual
    # sheet row: .256 +/-.005.
    printed_in = f"{case.drill.length.Length / 0.0254:.{case.drill.length.Precision}f}"
    assert printed_in == "0.256"
    printed_band = printed_band_mm(3, unit="in")
    printed_mm = float(printed_in) * 25.4
    effective_limits = (printed_mm - printed_band, printed_mm + printed_band)
    assert effective_limits == pytest.approx((6.3754, 6.6294))
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


@pytest.mark.parametrize("band", [0.51, 0.40])
def test_bracket_depth_callout_rejects_engineering_band_not_inherited_by_print(
    monkeypatch, bracket_depth_callout, band,
) -> None:
    monkeypatch.setattr(drawing, "DRILL_DEPTH_BAND", band)
    with pytest.raises(RuntimeError):
        bracket_depth_callout.dress()


@pytest.mark.parametrize(
    "damage",
    (
        None, "outer-caps-absent", "missing", "empty", "receiver-entry",
        "receiver-inner", "opposite-inner", "extra", "receiver-depth",
        "opposite-depth", "missing-depth", "middle-missing", "middle-depth",
        "middle-missing-depth", "middle-inner", "middle-outer", "middle-one-cap",
    ),
)
def test_native_rib_end_planes_preserve_uniform_depths_and_fixed_outer_faces(
    monkeypatch, damage,
) -> None:
    def face(z):
        surface = SimpleNamespace(
            IsPlane=lambda: True, PlaneParams=(0.0, 0.0, 1.0, 0.0, 0.0, z / 1000.0),
        )
        return SimpleNamespace(GetSurface=lambda: surface)

    planes = {
        "EdgeRibBack": [-76.2, -71.12],
        "EdgeRibFront": [71.12, 76.2],
        "MiddleRib": [-2.54, 2.54],
    }
    depths = {name: 5.08 for name in planes}
    if damage == "outer-caps-absent":
        planes["EdgeRibBack"] = [-71.12]
        planes["EdgeRibFront"] = [71.12]
    elif damage == "receiver-depth":
        depths["EdgeRibBack"] = 9.0
    elif damage == "opposite-depth":
        depths["EdgeRibFront"] = 5.0
    elif damage == "middle-depth":
        depths["MiddleRib"] = 5.0
    elif damage == "receiver-entry":
        planes["EdgeRibBack"][0] -= 0.9
    elif damage == "receiver-inner":
        planes["EdgeRibBack"][1] = -67.2
    elif damage == "opposite-inner":
        planes["EdgeRibFront"][0] = 71.2
    elif damage == "middle-inner":
        planes["MiddleRib"][0] = -2.5
    elif damage == "middle-outer":
        planes["MiddleRib"][1] = 2.5
    elif damage == "middle-one-cap":
        planes["MiddleRib"] = [-2.5]
    elif damage == "extra":
        planes["EdgeRibBack"].append(-70.0)
    elif damage == "empty":
        planes["EdgeRibBack"] = []

    def feature(name, values):
        expected_parameter = "MiddleRibThickness" if name == "MiddleRib" else "EdgeRibThickness"

        def parameter(parameter_name):
            assert parameter_name == expected_parameter
            if (
                damage == "missing-depth" and name == "EdgeRibBack"
                or damage == "middle-missing-depth" and name == "MiddleRib"
            ):
                return None
            return SimpleNamespace(SystemValue=depths[name] / 1000.0)

        return SimpleNamespace(
            GetFaces=lambda: tuple(face(z) for z in values),
            Parameter=parameter,
        )

    features = {name: feature(name, values) for name, values in planes.items()}
    if damage == "missing":
        del features["EdgeRibBack"]
    elif damage == "middle-missing":
        del features["MiddleRib"]
    monkeypatch.setattr(lever_build, "_early_bound", lambda value, _kind: value)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))
    if damage in (None, "outer-caps-absent"):
        lever_build._assert_edge_rib_end_planes(adapter)
    else:
        with pytest.raises(RuntimeError, match="EdgeRibBack|EdgeRibFront|MiddleRib"):
            lever_build._assert_edge_rib_end_planes(adapter)


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
    """Synthetic native API boundary for independent geometry/identity mutations."""
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
    state.geometry_failures = []
    state.annotation_position = (0.228 + dx, 0.083 + dy, 0.0)
    state.view_position = (0.235 + dx, 0.100 + dy)
    state.transform = (
        -1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0,
        free_x + drawing.PLATE_W / 1000.0, 0.100 + dy, 0.0, 1.0, 0.0, 0.0, 0.0,
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

        def GetTextCount(self):
            return 1

        def GetTextPositionAtIndex(self, index):
            assert index == 0
            return (0.0, 0.0, 0.0)

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

        def GetPosition(self):
            return state.annotation_position

        def GetDisplayData(self):
            return state.annotation_data

    state.dimension, state.data, state.display = Dimension(), Data(), Display()
    state.annotation_data = state.data
    annotation = Annotation()
    state.annotations = [annotation]
    view = SimpleNamespace(
        GetAnnotationCount=lambda: (
            len(state.annotations) if state.count_override is None else state.count_override
        ),
        GetAnnotations=lambda: tuple(state.annotations),
        Position=state.view_position,
        ModelToViewTransform=SimpleNamespace(ArrayData=state.transform),
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
    monkeypatch.setattr(
        drawing._telemetry, "error",
        lambda _message, **fields: state.geometry_failures.append(fields),
    )
    return SimpleNamespace(
        adapter=adapter, view=view, annotation=annotation, state=state,
        capture=lambda: drawing._plate_thickness_check(adapter, view, [annotation]),
    )


def _recorded_plate_thickness(monkeypatch):
    """Replay r6's dimension-display rows and projected free-end coordinates."""
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    state.name = "PlateThickness@PlateProfile@sm-summing-lever.Part"
    state.value = 0.006999999969999999
    state.use_doc = [True, True]
    state.annotation_position = (0.228, 0.083, -9.999999999949722e-05)
    state.view_position = (0.3, 0.1)
    state.transform = (
        -1.0, 0.0, 6.982962677686267e-15, 0.0, 1.0, 0.0,
        -6.982962677686267e-15, 0.0, -1.0,
        0.2793625, 0.1, 1.441108922607503e-16, 1.0, 0.0, 0.0, 0.0,
    )
    case.view.Position = state.view_position
    case.view.ModelToViewTransform.ArrayData = state.transform
    state.lines = [
        (0.0, 0.0, -1.0, -1.0,
         0.23391250000000002, 0.10254, -9.999999999953851e-05,
         0.22700000000000004, 0.10254, -9.999999999949024e-05),
        (0.0, 0.0, -1.0, -1.0,
         0.23391250000000002, 0.09554000003, -9.999999999953851e-05,
         0.22700000000000004, 0.09554000003, -9.999999999949024e-05),
        (0.0, 0.0, -1.0, -1.0,
         0.21636249951273206, 0.08022187500447034, -9.999999999945843e-05,
         0.22800000000000004, 0.08022187500447034, -9.999999999949723e-05),
        (0.0, 0.0, -1.0, -1.0,
         0.22800000000000004, 0.08022187500447034, -9.999999999949723e-05,
         0.22800000000000004, 0.09554000003, -9.999999999949722e-05),
        (0.0, 0.0, -1.0, -1.0,
         0.22800000000000004, 0.10254, -9.999999999949722e-05,
         0.22800000000000004, 0.10889, -9.999999999949722e-05),
    ]
    state.arrows = [
        [0.22800000000000004, 0.10254, -9.999999999949722e-05,
         -0.0, 1.0, -0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0],
        [0.22800000000000004, 0.09554000003, -9.999999999949722e-05,
         0.0, -1.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0],
    ]
    state.projected = {
        (0.044449999999999996, -0.0044599999999999996, -0.07619999999999999):
            (0.23491250000000055, 0.09554),
        (0.044449999999999996, 0.00254, -0.07619999999999999):
            (0.23491250000000055, 0.10254),
        (0.043449999999999996, -0.0044599999999999996, -0.07619999999999999):
            (0.23591250000000055, 0.09554),
    }
    state.text_position = (
        0.21636249951273206, 0.08022187482984736, -9.999999999949722e-05,
    )
    monkeypatch.setattr(state.data, "GetLineAtIndex2", lambda index: state.lines[index])
    monkeypatch.setattr(
        state.data, "GetTextPositionAtIndex",
        lambda _index: state.text_position,
    )
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda _adapter, _view, xyz, **_kwargs: state.projected[xyz],
    )
    return case


def test_plate_thickness_accepts_recorded_native_layout(monkeypatch) -> None:
    case = _recorded_plate_thickness(monkeypatch)
    state = case.state
    original = (tuple(state.lines), tuple(tuple(row) for row in state.arrows))
    check = case.capture()
    check()
    assert (tuple(state.lines), tuple(tuple(row) for row in state.arrows)) == original
    assert state.geometry_failures == []


@pytest.mark.parametrize("offset", [(0.0, 0.0), (0.017, -0.009), (0.035, 0.050)])
@pytest.mark.parametrize("reverse", [False, True])
def test_recorded_plate_thickness_is_independent_of_sheet_position_and_row_order(
    monkeypatch, offset, reverse,
) -> None:
    case = _recorded_plate_thickness(monkeypatch)
    state = case.state
    dx, dy = offset
    moved = []
    for raw in state.lines:
        row = list(raw)
        for index in (4, 7):
            row[index] += dx
            row[index + 1] += dy
        if reverse:
            row[4:7], row[7:10] = row[7:10], row[4:7]
        moved.append(tuple(row))
    state.lines = moved[::-1] if reverse else moved
    for row in state.arrows:
        row[0] += dx
        row[1] += dy
    if reverse:
        state.arrows.reverse()
    state.projected = {
        model: (point[0] + dx, point[1] + dy) for model, point in state.projected.items()
    }
    for member in ("annotation_position", "text_position", "view_position"):
        point = getattr(state, member)
        setattr(state, member, (point[0] + dx, point[1] + dy, *point[2:]))
    transform = list(state.transform)
    transform[9] += dx
    transform[10] += dy
    state.transform = tuple(transform)
    case.view.Position = state.view_position
    case.view.ModelToViewTransform.ArrayData = state.transform
    case.capture()()
    assert state.geometry_failures == []


@pytest.mark.parametrize("settled", [False, True])
@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "damage",
    ["missing_witness", "displaced_witness", "duplicate_candidate",
     "duplicate_reversed", "duplicate_wrong_origin", "displaced_origin",
     "displaced_arrow", "wrong_edge"],
)
def test_recorded_plate_thickness_rejects_wrong_native_geometry(
    monkeypatch, settled, index, damage,
) -> None:
    case = _recorded_plate_thickness(monkeypatch)
    state = case.state
    check = case.capture() if settled else case.capture
    if damage == "missing_witness":
        state.lines.pop(index)
    elif damage in {"duplicate_candidate", "duplicate_reversed", "duplicate_wrong_origin"}:
        row = list(state.lines[index])
        if damage == "duplicate_reversed":
            row[4:7], row[7:10] = row[7:10], row[4:7]
        elif damage == "duplicate_wrong_origin":
            row[4] -= 0.001
        state.lines.append(tuple(row))
    elif damage in {"displaced_witness", "displaced_origin"}:
        row = list(state.lines[index])
        if damage == "displaced_witness":
            row[5] += 0.001
            row[8] += 0.001
        else:
            row[4] -= 0.001
        state.lines[index] = tuple(row)
    elif damage == "displaced_arrow":
        state.arrows[index][1] += 0.001
    else:
        y = (drawing.COEFFICIENT_BOTTOM_Y, drawing.COEFFICIENT_TOP_Y)[index]
        z = -drawing.PLATE_L / 2.0
        state.edges[index] = _line(
            (drawing.PLATE_W - 2.0, y, z), (drawing.PLATE_W - 0.1, y, z),
        )
    with pytest.raises(RuntimeError):
        check()
    assert len(state.geometry_failures) == 1


@pytest.mark.parametrize("settled", [False, True])
@pytest.mark.parametrize("index", [0, 2, 3])
@pytest.mark.parametrize("damage", ["incomplete", "nonfinite", "nonnumeric"])
def test_recorded_plate_thickness_rejects_malformed_display_lines(
    monkeypatch, settled, index, damage,
) -> None:
    case = _recorded_plate_thickness(monkeypatch)
    state = case.state
    check = case.capture() if settled else case.capture
    row = list(state.lines[index])
    if damage == "incomplete":
        row = row[:7]
    else:
        row[4] = math.nan if damage == "nonfinite" else "unreadable-coordinate"
    state.lines[index] = tuple(row)
    with pytest.raises(RuntimeError):
        check()
    record = state.geometry_failures[0]["geometry"]
    assert record["dimension_display"]["lines"]["rows"][index] == tuple(row)


@pytest.mark.parametrize("settled", [False, True])
@pytest.mark.parametrize(
    "damage", ["arrows_outside", "arrows_at_endpoint", "detached_leader", "diagonal_leader"],
)
def test_recorded_plate_thickness_preserves_arrow_intersections_and_leader_attachment(
    monkeypatch, settled, damage,
) -> None:
    case = _recorded_plate_thickness(monkeypatch)
    state = case.state
    check = case.capture() if settled else case.capture
    if damage in {"arrows_outside", "arrows_at_endpoint"}:
        x = state.lines[0][7] - (0.001 if damage == "arrows_outside" else 0.0)
        for arrow in state.arrows:
            arrow[0] = x
    else:
        row = list(state.lines[2])
        row[5] += 0.001
        if damage == "detached_leader":
            row[8] += 0.001
        state.lines[2] = tuple(row)
    with pytest.raises(RuntimeError):
        check()


def test_recorded_plate_thickness_settled_tail_movement_is_not_hidden_by_text_ink(
    monkeypatch,
) -> None:
    case = _recorded_plate_thickness(monkeypatch)
    state = case.state
    check = case.capture()
    row = list(state.lines[1])
    row[7] -= 0.001
    state.lines[1] = tuple(row)
    with pytest.raises(RuntimeError):
        check()
    record = state.geometry_failures[0]["geometry"]
    original, regenerated = record["original_ink"], record["regenerated_ink"]
    assert original[:2] == regenerated[:2]
    assert regenerated[2][0] == original[2][0] - 0.001
    assert regenerated[2][1] == original[2][1]


@pytest.mark.parametrize(
    ("full_name", "value_m"),
    [
        ("PlateThickness@PlateProfile@sm-summing-lever.SLDPRT", 0.007),
        # Native r4 readback: the explicit-mm global evaluated in an inch part.
        ("PlateThickness@PlateProfile@sm-summing-lever.Part", 0.006999999969999999),
    ],
)
@pytest.mark.parametrize(
    ("offset", "band"),
    [((0.0, 0.0), (0, 0.0, 0.0)), ((0.017, -0.009), (2, -0.0001, 0.0002))],
)
def test_plate_thickness_keeps_native_identity_band_gaps_and_free_end_ink(
    monkeypatch, offset, band, full_name, value_m,
) -> None:
    case = _native_plate_thickness(monkeypatch, offset, band)
    state = case.state
    state.name, state.value = full_name, value_m
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
    assert state.geometry_failures == []
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


@pytest.mark.parametrize("direction", [-1.0, 1.0])
@pytest.mark.parametrize("inside_budget", [True, False])
def test_plate_thickness_nominal_readback_has_one_nanometre_budget(
    monkeypatch, direction, inside_budget,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    # Adjacent representable values straddle each side of the absolute budget.
    # Do not derive this test's budget from the production constant.
    case.state.value = math.nextafter(
        0.007 + direction * 1e-9, 0.007 if inside_budget else direction * math.inf,
    )
    if inside_budget:
        case.capture()()
    else:
        with pytest.raises(RuntimeError, match="wrong model identity or thickness"):
            case.capture()


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


@pytest.mark.parametrize("readback", [0.007, 0.006999999969999999])
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
def test_plate_thickness_rejects_wrong_model_identity_or_view(
    monkeypatch, member, value, readback,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    case.state.value = readback
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


@pytest.mark.parametrize("readback", [0.007, 0.006999999969999999])
@pytest.mark.parametrize(
    "damage", ["tail", "arrow", "origin", "detached", "replacement", "band", "value", "gap"],
)
def test_settled_thickness_check_reads_regenerated_native_state(
    monkeypatch, damage, readback,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    state.value = readback
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


@pytest.mark.parametrize("settled", [False, True])
@pytest.mark.parametrize(
    "damage",
    ["missing_edge", "projection", "gap", "extra_arrow", "arrow_x",
     "missing_witness", "extra_horizontal", "witness_origin", "other_ink"],
)
def test_plate_thickness_refusals_capture_every_native_geometry_boundary(
    monkeypatch, settled, damage,
) -> None:
    case = _native_plate_thickness(monkeypatch, band=(2, -0.0001, 0.0002))
    state = case.state
    check = case.capture() if settled else case.capture
    if damage == "missing_edge":
        state.edges.pop(0)
    elif damage == "projection":
        state.projection_scale = (-1.0, 1.0)
    elif damage == "gap":
        state.read_overrides[0] = (False, True, 0.003)
    elif damage == "extra_arrow":
        state.arrows.append([*state.arrows[0]])
    elif damage == "arrow_x":
        state.arrows[0][0] += 0.001
    elif damage == "missing_witness":
        state.lines.pop(0)
    elif damage == "extra_horizontal":
        state.lines.append(((0.230, 0.125), (0.240, 0.125)))
    elif damage == "witness_origin":
        first, second = state.lines[0]
        state.lines[0] = ((first[0] - 0.001, first[1]), second)
    else:
        state.lines.append(((0.220, 0.101), (0.224, 0.102)))

    # Exercise the real guard, including failures before it reaches display
    # data. The error log must still retain every independent observation.
    with pytest.raises(RuntimeError):
        check()
    assert len(state.geometry_failures) == 1
    record = state.geometry_failures[0]["geometry"]
    display = record["dimension_display"]
    assert display["lines"]["count"] == len(state.lines)
    assert display["lines"]["rows"] == [
        (0.0, 0.0, 0.0, 0.0, *first, 0.0, *second, 0.0)
        for first, second in state.lines
    ]
    assert display["arrows"]["count"] == len(state.arrows)
    assert display["arrows"]["rows"] == [tuple(row) for row in state.arrows]
    assert display["text_positions"]["rows"] == [(0.0, 0.0, 0.0)]
    assert record["annotation_display"] == display
    assert record["annotation_position_m"] == state.annotation_position
    assert record["view_position_m"] == state.view_position
    assert record["model_to_view_transform"] == state.transform
    assert record["native_model"] == {
        "FullName": state.name, "SystemValue_m": state.value,
        "tolerance": {"Type": 2, "min_m": -0.0001, "max_m": 0.0002},
    }
    assert record["native_gap_replies"] == [
        state.read_overrides.get(index, (True, state.use_doc[index], state.gaps[index]))
        for index in (0, 1)
    ]
    model = record["expected_model_points_m"]
    projected = record["expected_projected_points_m"]
    assert set(projected) == {"bottom", "top", "inboard"}
    for face, (x, y, z) in model.items():
        assert z == -drawing.PLATE_L / 2000.0
        assert projected[face] == (
            0.235 - state.projection_scale[0] * (x - drawing.PLATE_W / 1000.0),
            0.100 + y,
        )


def test_plate_thickness_malformed_raw_line_is_preserved_not_reparsed_as_a_witness(
    monkeypatch,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    data = case.state.data
    original = data.GetLineAtIndex2
    malformed = (0.0, 0.0, 0.0, 0.0, 0.234, 0.088, 0.0)
    monkeypatch.setattr(
        data, "GetLineAtIndex2", lambda index: malformed if index == 0 else original(index),
    )
    with pytest.raises(RuntimeError):
        case.capture()
    record = case.state.geometry_failures[0]["geometry"]
    assert record["dimension_display"]["lines"]["rows"] == [
        malformed, original(1), original(2),
    ]
    assert record["dimension_display"]["arrows"]["rows"] == [
        tuple(row) for row in case.state.arrows
    ]
    assert record["dimension_segments_m"]["error_type"] == "RuntimeError"


def test_plate_thickness_missing_dimension_display_does_not_use_annotation_ink(
    monkeypatch,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    monkeypatch.setattr(state.display, "GetDisplayData", lambda: None)
    with pytest.raises(RuntimeError):
        case.capture()
    record = state.geometry_failures[0]["geometry"]
    assert record["dimension_display"] == {"missing": True}
    assert record["annotation_display"]["lines"]["count"] == len(state.lines)
    assert record["annotation_display"]["arrows"]["rows"] == [
        tuple(row) for row in state.arrows
    ]
    assert record["native_model"]["SystemValue_m"] == state.value
    assert record["model_to_view_transform"] == state.transform
    assert set(record["expected_projected_points_m"]) == {"bottom", "top", "inboard"}


def test_plate_thickness_diagnostic_read_errors_do_not_hide_other_native_rows(
    monkeypatch,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    line, arrow = state.data.GetLineAtIndex2, state.data.GetArrowHeadAtIndex2

    def read_line(index):
        if index == 0:
            raise OSError("line-zero-unreadable")
        return line(index)

    def read_arrow(index):
        if index == 0:
            raise ValueError("arrow-zero-unreadable")
        return arrow(index)

    def read_position():
        raise OSError("position-unreadable")

    monkeypatch.setattr(state.data, "GetLineAtIndex2", read_line)
    monkeypatch.setattr(state.data, "GetArrowHeadAtIndex2", read_arrow)
    monkeypatch.setattr(case.annotation, "GetPosition", read_position)
    # A distinct native provider is diagnostic evidence, never a fallback.
    state.annotation_data = SimpleNamespace(
        GetLineCount=lambda: 1, GetLineAtIndex2=lambda _index: line(0),
        GetArrowHeadCount=lambda: 0, GetTextCount=lambda: 0,
    )
    with pytest.raises(RuntimeError) as refused:
        case.capture()
    assert isinstance(refused.value.__cause__, ValueError)
    record = state.geometry_failures[0]["geometry"]
    rows = record["dimension_display"]
    assert rows["lines"]["rows"][0]["error_type"] == "OSError"
    assert rows["lines"]["rows"][1:] == [line(1), line(2)]
    assert rows["arrows"]["rows"][0]["error_type"] == "ValueError"
    assert rows["arrows"]["rows"][1] == tuple(arrow(1))
    assert record["annotation_position_m"]["error_type"] == "OSError"
    assert record["annotation_display"]["lines"]["rows"] == [line(0)]
    assert record["annotation_display"]["arrows"]["count"] == 0
    assert record["model_to_view_transform"] == state.transform
    assert all(isinstance(point, tuple) for point in record["expected_projected_points_m"].values())


def test_plate_thickness_settled_witness_movement_records_original_and_current_ink(
    monkeypatch,
) -> None:
    case = _native_plate_thickness(monkeypatch)
    state = case.state
    check = case.capture()
    first, second = state.lines[0]
    state.lines[0] = (first, (second[0] - 0.001, second[1]))
    with pytest.raises(RuntimeError):
        check()
    record = state.geometry_failures[0]["geometry"]
    original, regenerated = record["original_ink"], record["regenerated_ink"]
    assert original[:2] == regenerated[:2]
    assert regenerated[2][0] == original[2][0] - 0.001
    assert regenerated[2][1] == original[2][1]
    assert record["dimension_display"]["lines"]["rows"][0][7:9] == (
        second[0] - 0.001, second[1],
    )


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


def test_rib_profile_leader_stays_with_its_native_wrap_arc(monkeypatch) -> None:
    annotations = []
    displays = {}
    for name in ("EdgeRibFrontUpperBlendR", "EdgeRibFrontLowerBlendR", "EdgeRibFrontArcR"):
        native_owner = object()
        display = SimpleNamespace(
            ArcExtensionLineOrOppositeSide=True, SolidLeader=True,
            GetDimension2=lambda _index, owner=native_owner: owner,
        )
        displays[name] = display, native_owner
        annotations.append(SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda display=display: display,
        ))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, raw: raw.name)
    drawing._attach_radial_leaders(
        object(), annotations, ("EdgeRibFrontArcR",), label="front",
    )
    for name, (display, native_owner) in displays.items():
        assert display.GetDimension2(0) is native_owner
        assert display.ArcExtensionLineOrOppositeSide is (name != "EdgeRibFrontArcR")
        assert display.SolidLeader is (name != "EdgeRibFrontArcR")


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
