"""Offline physical interval/fit/travel checks for the threaded MG lever."""

from __future__ import annotations

import asyncio
import itertools
import json
import math
from types import SimpleNamespace

import pytest

import build_mg_magnifier_assembly as assembly
import build_mg_magnifying_lever as part
import draw_mg_magnifying_lever as drawing
import mg_lever_thread_joint as joint
import mg_magnifier_assembly_spec as installed
import mg_magnifying_clamp_geom as clamp
import mg_magnifying_lever_geom as geom
import mg_magnifying_lever_spec as spec
import _drawing_leader_notes as leader_notes
import _drawing_dimension_import as dimension_import
from _drawing_layout_check import DrawableRegion
from _drawing_registry import DRAWING_TEMPLATES
from _layout_audit import (
    find_leader_across_lines,
    find_leader_through_text,
    find_text_clearance,
    find_text_separation,
)
from _printed_tolerance import drilled_oversize_mm
from _layout_geometry import (
    ARROW_TEXT_CLEARANCE_M,
    AnnotationGeometry,
    Box,
    segment_box_distance,
    Segment,
    SheetGeometry,
    find_border_breaches,
    find_text_on_line,
    find_text_on_text,
)


def _physical_projection_fixture(monkeypatch, tmp_path):
    import _assembly
    import _gtol_face_read
    import _gtol_face_resolve

    def bind(value, _interface):
        return value

    def invoke(value, _interface, member, *args):
        native = getattr(value, member)
        return native(*args) if callable(native) else native

    for module in (_assembly, _gtol_face_resolve):
        monkeypatch.setattr(module, "_early_bound", bind)
    monkeypatch.setattr(_gtol_face_resolve, "_bind", bind)
    monkeypatch.setattr(_gtol_face_resolve, "_com_invoke", invoke)
    monkeypatch.setattr(_gtol_face_read, "_com_invoke", invoke)
    monkeypatch.setattr(assembly, "_early_bound", bind)
    monkeypatch.setattr(part, "_early_bound", bind)
    models, components = {}, {}
    dimensions = {}
    for name, stem, normal, local_x, shift in (
        ("lever-actual", "mg-magnifying-lever", (1.0, 0.0, 0.0), joint.ROD_LENGTH / 1000.0, -joint.ROD_LENGTH / 1000.0),
        ("bracket-actual", "mg-magnifying-bracket", (-1.0, 0.0, 0.0), -joint.NECK_THICKNESS / 2000.0, (joint.NECK_THICKNESS / 2.0 + installed.THREAD_PROJECTION) / 1000.0),
    ):
        surface = SimpleNamespace(Identity=lambda: 4001, PlaneParams=(*normal, local_x, 0.0, 0.0))
        face = SimpleNamespace(GetSurface=lambda value=surface: value, FaceInSurfaceSense=False, GetBox=lambda: (), GetNextFace=lambda: None)
        body = SimpleNamespace(GetFirstFace=lambda value=face: value)
        model = SimpleNamespace(GetPathName=lambda value=stem: str(tmp_path / f"{value}.SLDPRT"), GetBodies2=lambda *_args, value=body: (value,),
                                ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")))
        transform = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, shift, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
        component = SimpleNamespace(GetModelDoc2=lambda value=model: value, ReferencedConfiguration="Default", Transform2=SimpleNamespace(ArrayData=transform))
        models[stem], components[name] = model, component
        if stem == "mg-magnifying-lever":
            dimensions[id(model)] = {"OverallLength": joint.ROD_LENGTH / 1000.0, "TipChamfer": joint.TIP_CHAMFER / 1000.0, "ThreadLength": joint.THREAD_LENGTH / 1000.0}
        else:
            dimensions[id(model)] = {"NeckThickness": joint.NECK_THICKNESS / 1000.0}
    line = SimpleNamespace(GetType=lambda: 0, ConstructionGeometry=True,
                           GetStartPoint2=lambda: SimpleNamespace(X=0.0),
                           GetEndPoint2=lambda: SimpleNamespace(X=installed.THREAD_PROJECTION / 1000.0))
    feature = SimpleNamespace(GetSpecificFeature2=lambda: SimpleNamespace(GetSketchSegments=lambda: (line,)))
    document = SimpleNamespace(GetComponentByName=components.get, FeatureByName=lambda _name: feature)
    dimensions[id(document)] = {installed.THREAD_PROJECTION_DIMENSION: installed.THREAD_PROJECTION / 1000.0}
    adapter = SimpleNamespace(currentModel=document)

    def named_dimension(owner, _feature, name):
        return None, SimpleNamespace(SystemValue=dimensions[id(owner.currentModel)][name])

    monkeypatch.setattr(assembly, "_named_dimension", named_dimension)
    monkeypatch.setattr(part, "_named_dimension", named_dimension)
    monkeypatch.setattr(assembly, "part_path", lambda stem: tmp_path / f"{stem}.SLDPRT")
    return SimpleNamespace(adapter=adapter, models=models, components=components, dimensions=dimensions, line=line)


def test_projection_measures_actual_native_planes_in_live_component_frames(monkeypatch, tmp_path) -> None:
    fixture = _physical_projection_fixture(monkeypatch, tmp_path)
    names = ("lever-actual", "bracket-actual")
    assert assembly._physical_thread_projection(fixture.adapter, *names) == pytest.approx((0.0, 1.25))
    assembly._assert_thread_projection_faces(fixture.adapter, *names)
    # A rigid translation preserves the fitted separation, but a constant
    # witness at the former coordinates must no longer pass.
    for component in fixture.components.values():
        component.Transform2.ArrayData[9] += 0.025
    assert assembly._physical_thread_projection(fixture.adapter, *names) == pytest.approx((25.0, 26.25))
    with pytest.raises(RuntimeError, match="endpoints"):
        assembly._assert_thread_projection_faces(fixture.adapter, *names)


@pytest.mark.parametrize("change", ("pose", "source-dimension", "configuration", "path", "nonaxial", "witness"))
def test_projection_refuses_physical_or_source_drift_even_when_nominal_constants_are_unchanged(monkeypatch, tmp_path, change) -> None:
    fixture = _physical_projection_fixture(monkeypatch, tmp_path)
    lever = fixture.components["lever-actual"]
    if change == "pose":
        lever.Transform2.ArrayData[9] += 0.0002
    elif change == "source-dimension":
        fixture.dimensions[id(fixture.models["mg-magnifying-lever"])]["OverallLength"] += 0.001
    elif change == "configuration":
        lever.ReferencedConfiguration = "Other"
    elif change == "path":
        fixture.models["mg-magnifying-lever"].GetPathName = lambda: str(tmp_path / "other.SLDPRT")
    elif change == "nonaxial":
        lever.Transform2.ArrayData[0:3] = [0.0, 1.0, 0.0]
    else:
        fixture.line.GetStartPoint2 = lambda: SimpleNamespace(X=0.0002)
    with pytest.raises(RuntimeError):
        assembly._assert_thread_projection_faces(fixture.adapter, "lever-actual", "bracket-actual")


@pytest.mark.parametrize("change", (None, "depth", "apply-thread", "end-condition", "physical-tip"))
def test_thread_extent_readback_is_bound_to_actual_tip_and_native_thread_definition(monkeypatch, tmp_path, change) -> None:
    fixture = _physical_projection_fixture(monkeypatch, tmp_path)
    model = fixture.models["mg-magnifying-lever"]
    definition = SimpleNamespace(BlindDepth=(joint.THREAD_LENGTH - joint.TIP_CHAMFER) / 1000.0, ApplyThread=0, EndCondition=0)
    model.FeatureByName = lambda _name: SimpleNamespace(GetDefinition=lambda: definition)
    if change == "depth":
        definition.BlindDepth += 0.0002
    elif change == "apply-thread":
        definition.ApplyThread = 1
    elif change == "end-condition":
        definition.EndCondition = 1
    elif change == "physical-tip":
        fixture.dimensions[id(model)]["OverallLength"] += 0.00002
    adapter = SimpleNamespace(currentModel=model)
    if change is None:
        part._assert_native_thread(adapter, "native-thread")
    else:
        with pytest.raises(RuntimeError):
            part._assert_native_thread(adapter, "native-thread")



@pytest.mark.parametrize("previous", (False, True))
@pytest.mark.parametrize("fault", (None, "creation", "selection"))
def test_crop_circle_keeps_actual_geometry_and_selects_only_the_authored_entity(monkeypatch, previous, fault) -> None:
    manager = SimpleNamespace(AddToDB=previous)
    document = SimpleNamespace(SketchManager=manager, selected=None)
    center, radius = (0.245, 0.180), 0.018

    def create_circle(x, y, z, ex, ey, ez):
        if fault == "creation":
            raise RuntimeError("native circle creation refused")
        # Creation-time inference would move the real curve, not merely its
        # selection. The production routine must prevent that geometry change.
        if not manager.AddToDB:
            x += 0.0002
        circle = SimpleNamespace(geometry=(x, y, z, ex, ey, ez))

        def select(_append, _data):
            if fault == "selection":
                return False
            document.selected = circle
            return True

        circle.Select4 = select
        return circle

    manager.CreateCircle = create_circle

    def point(values):
        native = SimpleNamespace(ArrayData=values)
        native.MultiplyTransform = lambda _transform: native
        return native

    adapter = SimpleNamespace(currentModel=document, swApp=SimpleNamespace(GetMathUtility=lambda: SimpleNamespace(CreatePoint=point)))
    view = SimpleNamespace(GetSketch=lambda: SimpleNamespace(ModelToSketchTransform=object()))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_activate", lambda *_args: None)
    monkeypatch.setattr(drawing, "double_array", tuple)
    if fault is None:
        drawing._circle(adapter, view, center, radius)
        assert document.selected.geometry == pytest.approx((*center, 0.0, center[0] + radius, center[1], 0.0))
    else:
        with pytest.raises(RuntimeError):
            drawing._circle(adapter, view, center, radius)
        assert document.selected is None
    assert manager.AddToDB is previous


@pytest.mark.parametrize("fault", (None, "short", "nonfinite", "center", "radius", "kind"))
def test_detail_checks_the_native_persisted_crop_instead_of_trusting_success_status(monkeypatch, fault) -> None:
    center = drawing.DETAIL_CENTER
    radius = drawing.DETAIL_RADIUS_MM * drawing.DETAIL_SCALE[0] / 1000.0
    fence = [1.0, 0.0, *center, 0.0, center[0] + radius, center[1], 0.0, 0.0, 0.0, 0.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    if fault == "short":
        fence = fence[:-1]
    elif fault == "nonfinite":
        fence[4] = math.nan
    elif fault == "center":
        fence[2] += 0.0002
    elif fault == "radius":
        fence[5] += 0.0002
    elif fault == "kind":
        fence[11] = 1.0
    view = SimpleNamespace(ScaleRatio=drawing.DETAIL_SCALE, Position=center, SetViewPosition=lambda *_args: True,
                           Crop2=lambda *_args: 1, IsCropped=lambda: True, CropViewJaggedOutline=False, CropViewNoOutline=False,
                           GetDetailCircleInfo2=lambda: fence, UpdateViewDisplayGeometry=lambda: None,
                           GetAnnotations=lambda: tuple(SimpleNamespace(name=name) for name in drawing.DETAIL_KEEP))
    adapter = SimpleNamespace(currentModel=SimpleNamespace(ClearSelection2=lambda _all: None))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "place_view", lambda *_args, **_kwargs: view)
    monkeypatch.setattr(drawing, "model_point_in_view", lambda *_args, **_kwargs: center)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "curate_hidden_dimensions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(drawing, "_circle", lambda *_args: None)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    if fault is None:
        assert drawing._detail(adapter)[0] is view
    else:
        with pytest.raises(RuntimeError, match="native crop fence"):
            drawing._detail(adapter)

def _intersection(first, second):
    return max(0.0, min(first[1], second[1]) - max(first[0], second[0]))


def test_native_tip_projection_guarantees_full_overlap_independently_of_part_length() -> None:
    overlaps = []
    for thickness, projection, thread in itertools.product(
        (joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL, joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL),
        (installed.THREAD_PROJECTION - installed.THREAD_PROJECTION_TOL, installed.THREAD_PROJECTION + installed.THREAD_PROJECTION_TOL),
        (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL, joint.THREAD_LENGTH + joint.THREAD_LENGTH_TOL),
    ):
        tip = thickness + projection
        overlaps.append(_intersection((joint.CHAMFER_LEG_MAX, thickness - joint.CHAMFER_LEG_MAX), (tip - thread + joint.INCOMPLETE_THREAD_MAX, tip - joint.INCOMPLETE_THREAD_MAX - joint.CHAMFER_LEG_MAX)))
    assert installed.INSTALLED_FULL_ENGAGEMENT_MIN <= min(overlaps) + 1e-9
    assert installed.INSTALLED_FULL_ENGAGEMENT_MIN >= joint.REQUIRED_FULL_ENGAGEMENT
    assert installed.THREAD_PROJECTION - installed.THREAD_PROJECTION_TOL > 0.0
    assert installed.INSTALLED_FULL_ENGAGEMENT_MIN == pytest.approx(min(overlaps))
    # The neck prints .49 +/-.01 over its 12.5 mm model; the wider side is charged.
    assert joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL == pytest.approx(0.48 * 25.4)
    assert installed.INSTALLED_FULL_ENGAGEMENT_MIN == pytest.approx(10.736950600594392)
    assert geom.INSTALLED_ROOT_CLEARANCE_MIN == pytest.approx(1.543)
    assert geom.operating_clamp_radius_band() == pytest.approx((82.980, 165.0, 194.265))


def test_tip_chamfer_loss_is_additive_to_the_incomplete_thread_limit() -> None:
    fitted = joint.installation_full_overlap(installed.THREAD_PROJECTION, installed.THREAD_PROJECTION_TOL)
    fitted_without_tip = joint.installation_full_overlap(
        installed.THREAD_PROJECTION, installed.THREAD_PROJECTION_TOL, tip_chamfer=0.0,
    )
    assert joint.CHAMFER_LEG_MAX > joint.TIP_CHAMFER_MAX
    assert joint.TIP_CHAMFER + joint.TIP_CHAMFER_BAND[1] == pytest.approx(0.0)
    assert joint.TIP_CHAMFER + joint.TIP_CHAMFER_BAND[0] == pytest.approx(joint.TIP_CHAMFER_MAX)
    assert joint.THREAD_LENGTH_TOL == pytest.approx(joint.printed_band_mm(spec.DRAWING_PRECISION["ThreadExtent"]["ThreadLength"], unit=spec.UNIT))
    assert fitted_without_tip - fitted == pytest.approx(joint.CHAMFER_LEG_MAX)


@pytest.mark.parametrize("change", ({"thickness": 11.0}, {"thread_length": 14.0}, {"incomplete": 3.5}, {"projection_tol": 2.0}))
def test_full_thread_proof_detects_short_neck_thread_and_overlong_runout(change) -> None:
    arguments = {"projection_tol": installed.THREAD_PROJECTION_TOL, **change}
    overlap = joint.installation_full_overlap(installed.THREAD_PROJECTION, **arguments)
    assert overlap < joint.REQUIRED_FULL_ENGAGEMENT


def test_root_runout_is_wholly_outside_receiver_at_actual_printed_corners() -> None:
    # In the receiver frame the near face is zero. The latest full thread
    # starts at N + P - T + incomplete, independently of overall rod length.
    starts = [
        thickness + projection - thread + joint.INCOMPLETE_THREAD_MAX
        for thickness, projection, thread in itertools.product(
            (joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL, joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL),
            (installed.THREAD_PROJECTION - installed.THREAD_PROJECTION_TOL, installed.THREAD_PROJECTION + installed.THREAD_PROJECTION_TOL),
            (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL, joint.THREAD_LENGTH + joint.THREAD_LENGTH_TOL),
        )
    ]
    assert max(starts) < 0.0
    assert geom.INSTALLED_ROOT_CLEARANCE_MIN == pytest.approx(-max(starts))
    assert spec.SINGLE_LIMITS["ThreadExtent", "IncompleteLength"][0] == joint.INCOMPLETE_THREAD_MAX
    # The shortest accepted .71 thread (.70) less both .075 incomplete ends.
    assert spec.FULL_THREAD_MIN == pytest.approx((0.70 - 2.0 * 0.075) * 25.4)
    assert "FULL THREAD .55 MIN" in spec.LEAD_CALLOUT


def test_quarter_inch_body_has_real_drilled_slip_clearance() -> None:
    stock_low = joint.ROD_DIA + joint.ROD_DIA_BAND[1]
    stock_high = joint.ROD_DIA + joint.ROD_DIA_BAND[0]
    minimum = clamp.LEVER_BORE_DIA - stock_high
    maximum = clamp.LEVER_BORE_DIA + drilled_oversize_mm(unit=clamp.UNIT) - stock_low
    # Letter F (.257 +.004/0) over the 1/4 rod's .000/-.002.
    assert minimum == pytest.approx(0.007 * 25.4)
    assert maximum == pytest.approx(0.013 * 25.4)
    assert minimum > 0.0 and maximum < 0.5
    # The sheet's stated clearance is that same fit.
    assert spec.ROD_BORE_CLEARANCE == pytest.approx((minimum, maximum))


def test_clamp_entire_bore_stays_on_plain_body_at_nominal_travel_limits() -> None:
    radii = geom.clamp_radius_band(clamp.BLOCK_DEPTH)
    centres = [geom.KNIFE_LOCAL_X - radius for radius in radii]
    half = clamp.BLOCK_DEPTH / 2.0
    assert max(centres) + half <= joint.THREAD_ROOT_X
    assert min(centres) - half >= joint.ROD_DIA / 2.0 - 1e-9
    assert centres[1] == geom.CLAMP_LOCAL_X
    assert assembly.LEVER_X0 - geom.BRACKET_LOCAL_X == assembly.BRACKET_X
    assert assembly.LEVER_X0 - geom.KNIFE_LOCAL_X == assembly.KNIFE[0]


def test_operating_travel_covers_unbalanced_clamps_at_every_accepted_rod_corner() -> None:
    operating = geom.operating_clamp_radius_band()
    nominal = geom.clamp_radius_band(clamp.BLOCK_DEPTH)
    assert nominal[0] < operating[0] < operating[1] < operating[2] < nominal[2]
    assert operating[1] == nominal[1] == geom.KNIFE_LOCAL_X - geom.CLAMP_LOCAL_X
    assert assembly.CLAMP_X == assembly.LEVER_X0 - geom.CLAMP_LOCAL_X
    knife_to_bracket = geom.KNIFE_LOCAL_X - geom.BRACKET_LOCAL_X
    for length, threaded, thickness, projection, diameter, width, fraction, radius in itertools.product(
        (joint.ROD_LENGTH - joint.ROD_LENGTH_TOL, joint.ROD_LENGTH + joint.ROD_LENGTH_TOL),
        (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL, joint.THREAD_LENGTH + joint.THREAD_LENGTH_TOL),
        (joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL, joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL),
        (installed.THREAD_PROJECTION - installed.THREAD_PROJECTION_TOL, installed.THREAD_PROJECTION + installed.THREAD_PROJECTION_TOL),
        (joint.ROD_DIA + joint.ROD_DIA_BAND[1], joint.ROD_DIA + joint.ROD_DIA_BAND[0]),
        (clamp.BLOCK_DEPTH, clamp.STOCK_ENVELOPE_MAX),
        (0.0, 0.25, 0.5, 0.75, 1.0),
        (operating[0], operating[2]),
    ):
        # Independent machine coordinates: knife at zero, bracket at C.
        # Fitting the flat tip fixes its coordinate at the far face minus P.
        threaded_tip = knife_to_bracket - thickness / 2.0 - projection
        free_tip = threaded_tip + length
        block_min = radius - fraction * width
        block_max = radius + (1.0 - fraction) * width
        assert block_min >= threaded_tip + threaded - 1e-9
        assert block_min >= knife_to_bracket + thickness / 2.0 - 1e-9
        assert block_max <= free_tip - diameter / 2.0 + 1e-9
    # The former fixed-free-tip bound admits a real unsupported setting.
    short_rod_free_tip = (
        knife_to_bracket
        - (joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL) / 2.0
        - (installed.THREAD_PROJECTION + installed.THREAD_PROJECTION_TOL)
        + joint.ROD_LENGTH - joint.ROD_LENGTH_TOL
    )
    old_upper = geom.KNIFE_LOCAL_X - joint.ROD_DIA / 2.0 - clamp.STOCK_ENVELOPE_MAX
    assert old_upper + clamp.STOCK_ENVELOPE_MAX > short_rod_free_tip - joint.ROD_DIA / 2.0
    assert operating[2] + clamp.STOCK_ENVELOPE_MAX <= short_rod_free_tip - joint.ROD_DIA / 2.0 + 1e-9


@pytest.mark.parametrize("field", ("STOCK_ENVELOPE_MAX", "WALL_FLOOR"))
def test_operating_travel_refuses_an_unbounded_or_noninterior_clamp(monkeypatch, field) -> None:
    monkeypatch.setattr(clamp, field, 0.0)
    with pytest.raises(AssertionError, match="inside"):
        geom.operating_clamp_radius_band()


def test_small_thread_requirements_have_a_legible_enlarged_native_home() -> None:
    kept = [*drawing.FRONT_KEEP, *drawing.DETAIL_KEEP]
    assert len(kept) == len(set(kept))
    assert set(kept) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] > drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]
    # Every actual rod corner at the threaded flat end lies inside its circle.
    tip_offset = joint.ROD_LENGTH - drawing.DETAIL_FOCUS[0] * 1000.0
    assert math.hypot(tip_offset, joint.ROD_DIA / 2.0) < drawing.DETAIL_RADIUS_MM


_EXTENT_VALUES = {
    "ThreadLengthTip": joint.ROD_LENGTH,
    "ThreadLengthHeight": joint.ROD_DIA / 2.0,
    "ThreadLength": joint.THREAD_LENGTH,
    "IncompleteLengthTip": joint.ROD_LENGTH,
    "IncompleteLengthHeight": joint.ROD_DIA / 2.0,
    "IncompleteLength": joint.INCOMPLETE_THREAD_MAX,
}


def test_thread_witness_native_dimensions_are_driving_and_exact_before_equations(monkeypatch) -> None:
    reads = []

    def dimension(_adapter, feature, name):
        assert feature == "ThreadExtent"
        reads.append(name)
        return None, SimpleNamespace(DrivenState=2, SystemValue=_EXTENT_VALUES[name] / 1000.0)

    monkeypatch.setattr(part, "_named_dimension", dimension)
    part._assert_thread_extent_driving(None)
    assert set(reads) == set(_EXTENT_VALUES)


@pytest.mark.parametrize("name", tuple(_EXTENT_VALUES))
@pytest.mark.parametrize("state,offset", ((1, 0.0), (3, 0.0), (2, -0.2)))
def test_thread_witness_rejects_reference_or_inference_shifted_native_dimensions(monkeypatch, name, state, offset) -> None:
    def dimension(_adapter, feature, requested):
        assert feature == "ThreadExtent"
        changed = requested == name
        return None, SimpleNamespace(DrivenState=state if changed else 2, SystemValue=(_EXTENT_VALUES[requested] + (offset if changed else 0.0)) / 1000.0)

    monkeypatch.setattr(part, "_named_dimension", dimension)
    with pytest.raises(RuntimeError, match=name):
        part._assert_thread_extent_driving(None)


@pytest.mark.parametrize("fail_creation", (False, True))
def test_thread_witness_creation_suppresses_chamfer_snap_and_restores_add_to_db(monkeypatch, fail_creation) -> None:
    manager = SimpleNamespace(AddToDB=False)
    segments = {}
    created = []

    def result(data=None):
        return SimpleNamespace(is_success=True, data=data)

    async def create_sketch(plane):
        assert plane == "Front"
        return result()

    async def add_line(x1, y1, x2, y2):
        created.append((manager.AddToDB, (x1, y1), (x2, y2)))
        if fail_creation:
            raise RuntimeError("native line creation failed")
        # Mutation control: the former bare add_line snaps the endpoint onto
        # the existing 0.2 mm chamfer root when inference is allowed.
        native_end = x2 if manager.AddToDB else x2 - joint.TIP_CHAMFER
        key = f"line{len(segments)}"
        segments[key] = SimpleNamespace(ConstructionGeometry=False, end_x=native_end)
        return result(key)

    async def constraint(*_args):
        return result()

    async def anchor(_adapter, endpoint, x, _y, _label):
        assert segments[endpoint.split(".")[0]].end_x == pytest.approx(x)

    async def dimension(*_args):
        return None

    async def fully_defined(*_args):
        assert len(segments) == 2

    class Dims:
        def record(self, *_args):
            pass

        def apply(self, _adapter, feature):
            assert feature == "ThreadExtent"
            return []

    adapter = SimpleNamespace(
        currentSketchManager=manager, _sketch_entities=segments,
        create_sketch=create_sketch, add_line=add_line,
        add_sketch_constraint=constraint, exit_sketch=constraint,
    )
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "SketchDims", Dims)
    monkeypatch.setattr(part, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(part, "dimension_between", dimension)
    monkeypatch.setattr(part, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(part, "name_last_feature", lambda _adapter, _name: None)
    if fail_creation:
        with pytest.raises(RuntimeError, match="native line creation failed"):
            asyncio.run(part._thread_extent(adapter))
    else:
        asyncio.run(part._thread_extent(adapter))
        assert [row[2][0] for row in created] == [joint.ROD_LENGTH, joint.ROD_LENGTH]
        assert all(segment.ConstructionGeometry for segment in segments.values())
    assert created and all(row[0] for row in created)
    assert manager.AddToDB is False


class _LeverFace:
    """Native face/selection boundary; the real geometry matcher reads this."""

    def __init__(self, *, center_mm=None, diameter_mm=joint.ROD_DIA, identity=4004):
        self.center_mm = (joint.ROD_DIA / 2.0, 0.0, 0.0) if center_mm is None else center_mm
        radius = diameter_mm / 2000.0
        center = tuple(value / 1000.0 for value in self.center_mm)
        self.surface = SimpleNamespace(
            Identity=lambda: identity,
            SphereParams=(*center, radius),
            CylinderParams=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0, radius),
        )
        self.box = (*tuple(value - radius for value in center), *tuple(value + radius for value in center))
        if identity == 4002:
            self.box = (radius, -radius, -radius, joint.THREAD_ROOT_X / 1000.0, radius, radius)
        self.document = None
        self.selection_attempts = 0

    def GetSurface(self):
        return self.surface

    def GetBox(self):
        return self.box

    def Select4(self, append, data):
        assert append is False
        assert data.View is self.document.active_view
        self.selection_attempts += 1
        if self.document.fault == "selection_rejected":
            return False
        self.document.selected = self
        return True


class _LeverVisibleView:
    def __init__(self, name, faces=(), *, direct_faces=()):
        self.name = name
        self.faces = faces
        self.direct_faces = direct_faces
        self.entity_kinds = []
        self.component = object()

    def GetName2(self):
        return self.name

    def GetVisibleComponents(self):
        return (self.component,)

    def GetVisibleEntities2(self, component, kind):
        assert component is self.component
        self.entity_kinds.append(kind)
        if kind == 3:
            return self.direct_faces
        assert kind == 4
        return tuple(SimpleNamespace(GetFace=lambda face=face: face) for face in self.faces)


def _face_census_adapter():
    def read_member(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value

    return SimpleNamespace(
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
        _attempt=lambda fn, default=None: fn(), _get_attr_or_call=read_member,
    )


@pytest.mark.parametrize("direct_enumeration", (False, True))
def test_free_end_matcher_uses_actual_silhouette_faces_even_when_face_enumeration_is_empty(direct_enumeration) -> None:
    hemisphere = _LeverFace()
    body = _LeverFace(identity=4002)
    view = _LeverVisibleView("front", (
        body,
        _LeverFace(diameter_mm=joint.ROD_DIA + 1.0),
        _LeverFace(center_mm=(joint.ROD_LENGTH - joint.ROD_DIA / 2.0, 0.0, 0.0)),
        hemisphere, hemisphere,  # Two silhouette flanks may share one face.
    ), direct_faces=(body, hemisphere) if direct_enumeration else ())
    assert drawing._free_end_face(_face_census_adapter(), view, []) is hemisphere
    assert view.entity_kinds == [3, 4]


@pytest.mark.parametrize("faces", (
    (),
    (_LeverFace(center_mm=(0.0, 0.0, 0.0)),),
    (_LeverFace(diameter_mm=joint.ROD_DIA + 1.0),),
    (_LeverFace(), _LeverFace()),
))
def test_free_end_matcher_refuses_absent_wrong_or_ambiguous_visible_hemispheres(faces) -> None:
    view = _LeverVisibleView("front", (_LeverFace(identity=4002), *faces))
    with pytest.raises(RuntimeError, match="expected one visible spherical face"):
        drawing._free_end_face(_face_census_adapter(), view, [])


def test_free_end_census_distinguishes_empty_enumeration_from_non_spherical_native_geometry(monkeypatch) -> None:
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)
    with pytest.raises(RuntimeError, match="plain-body positive control"):
        drawing._free_end_face(_face_census_adapter(), _LeverVisibleView("front"), [])
    empty = json.loads(messages[-1].split(": ", 1)[1])
    assert empty["direct_faces"] == empty["silhouettes"] == empty["unique_faces"] == 0
    assert empty["plain_body_matches"] == 0 and empty["faces"] == []

    unknown = _LeverVisibleView("front", (_LeverFace(identity=4002), _LeverFace(identity=4006)))
    with pytest.raises(RuntimeError, match="expected one visible spherical face"):
        drawing._free_end_face(_face_census_adapter(), unknown, [])
    census = json.loads(messages[-1].split(": ", 1)[1])
    assert census["direct_faces"] == 0 and census["silhouettes"] == 2
    assert census["plain_body_matches"] == 1 and census["hemisphere_matches"] == 0
    assert {face["identity"] for face in census["faces"]} == {4002, 4006}
    cylinder = next(face for face in census["faces"] if face["identity"] == 4002)
    assert cylinder["parameters"][6] == pytest.approx(joint.ROD_DIA / 2000.0)
    assert len(cylinder["box"]) == 6
    unknown_face = next(face for face in census["faces"] if face["identity"] == 4006)
    assert len(unknown_face["box"]) == 6
    assert unknown_face["surface_type"] == "unhandled native surface identity"


@pytest.mark.parametrize("source_fault", (None, "stale_dimension", "missing_dimension", "stale_path", "missing_reference", "missing_transform"))
def test_free_end_census_compares_saved_geometry_source_transform_and_imported_dimension_owners(monkeypatch, source_fault) -> None:
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)
    hemisphere = _LeverFace()
    view = _LeverVisibleView("front", (_LeverFace(identity=4002), hemisphere))
    values = {
        "RodDia@RodProfile": joint.ROD_DIA, "OverallLength@RodProfile": joint.ROD_LENGTH,
        "TipChamfer@RodProfile": joint.TIP_CHAMFER, "ThreadLength@ThreadExtent": joint.THREAD_LENGTH,
        "IncompleteLength@ThreadExtent": joint.INCOMPLETE_THREAD_MAX,
    }
    if source_fault == "stale_dimension":
        values["RodDia@RodProfile"] += 0.1
    if source_fault == "missing_dimension":
        del values["RodDia@RodProfile"]

    def parameter(name):
        if name not in values:
            return None
        return SimpleNamespace(FullName=f"{name}@saved-lever", SystemValue=values[name] / 1000.0)

    actual_path = "C:/unrelated/stale-lever.SLDPRT" if source_fault == "stale_path" else str(drawing.SOURCE)
    view.ReferencedDocument = None if source_fault == "missing_reference" else SimpleNamespace(GetPathName=lambda: actual_path, Parameter=parameter)
    # Deliberately non-default native transform: diagnostics must report what
    # was actually read, not reconstruct an assumed *Front/1:1 transform.
    matrix = (0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.08, 0.09, 0.0, 3.0, 0.0, 0.0, 0.0)
    if source_fault != "missing_transform":
        view.ModelToViewTransform = SimpleNamespace(ArrayData=matrix)
    view.GetOrientationName = lambda: "actual saved orientation"
    imported = []
    for full_name in ("RodDia@RodProfile@saved-lever", "ThreadLength@ThreadExtent@saved-lever"):
        native_dimension = SimpleNamespace(FullName=full_name)
        display = SimpleNamespace(GetDimension=lambda dimension=native_dimension: dimension)
        imported.append(SimpleNamespace(GetSpecificAnnotation=lambda display=display: display))

    assert drawing._free_end_face(_face_census_adapter(), view, imported) is hemisphere
    census = json.loads(messages[-1].split(": ", 1)[1])
    assert census["coordinate_frame"] == "referenced part model" and census["length_units"] == "metres"
    sphere = next(face for face in census["faces"] if face["identity"] == 4004)
    assert sphere["sphere_center_m"] == pytest.approx((joint.ROD_DIA / 2000.0, 0.0, 0.0))
    assert sphere["sphere_radius_m"] == pytest.approx(joint.ROD_DIA / 2000.0)
    assert sphere["sphere_center_mm"] == pytest.approx((joint.ROD_DIA / 2.0, 0.0, 0.0))
    assert sphere["sphere_diameter_mm"] == pytest.approx(joint.ROD_DIA)
    assert census["imported_dimensions"] == [
        {"full_name": "RodDia@RodProfile@saved-lever", "source_feature": "RodProfile"},
        {"full_name": "ThreadLength@ThreadExtent@saved-lever", "source_feature": "ThreadExtent"},
    ]
    source = census["source"]
    assert source["all_dimensions_match"] is (source_fault not in ("stale_dimension", "missing_dimension", "missing_reference"))
    if source_fault == "missing_reference":
        assert "read_error" in source
    else:
        assert source["actual_path"] == actual_path
        assert source["path_matches"] is (source_fault != "stale_path")
        diameter = next(row for row in source["dimensions"] if row["requested_name"] == "RodDia@RodProfile")
        if source_fault == "missing_dimension":
            assert diameter["read_error"] == "native source dimension unavailable"
        else:
            assert diameter["actual_mm"] == pytest.approx(values["RodDia@RodProfile"])
            assert diameter["full_name"] == "RodDia@RodProfile@saved-lever"
    if source_fault == "missing_transform":
        assert "read_error" in census["view"]
    else:
        assert census["view"]["model_to_view"] == list(matrix)
        assert census["view"]["translation_m"] == list(matrix[9:12])
        assert census["view"]["scale"] == 3.0
        assert census["view"]["orientation"] == "actual saved orientation"


class _LeverNoteAnnotation:
    def __init__(self, face, fault):
        self.face = _LeverFace() if fault == "wrong_attachment" else face
        self.fault = fault
        self.leaders = 0
        self.position = None

    def GetAttachedEntityCount3(self):
        return 1

    def GetAttachedEntities3(self):
        return (self.face,)

    def GetAttachedEntityTypes(self):
        return (2,)  # swSelFACES, not swSelEDGES or swSelSILHOUETTES

    def GetLeaderCount(self):
        return self.leaders

    def IsDangling(self):
        return self.fault == "dangling"

    def SetLeader3(self, *_args):
        self.leaders = 1
        return 0

    def SetPosition2(self, x, y, z):
        self.position = (x, y, z)
        return True


class _LeverNoteDocument:
    def __init__(self, views, fault):
        self.views = {view.name: view for view in views}
        self.fault = fault
        self.active_view = None
        self.selected = None
        self.notes = []
        self.SelectionManager = SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(View=None),
            GetSelectedObjectCount2=lambda _mark: int(self.selected is not None),
            GetSelectedObject6=lambda _index, _mark: self.selected,
        )
        self.Extension = SimpleNamespace(SelectByID2=self._reject_hit_test)

    def _reject_hit_test(self, *_args):
        raise AssertionError("the hemisphere note must select the identified face, not hit-test an EDGE at its silhouette")

    def ActivateView(self, name):
        self.active_view = self.views[name]
        return True

    def ClearSelection2(self, _all):
        self.selected = None

    def InsertNote(self, text):
        assert text == spec.FREE_END_CALLOUT
        assert self.active_view.name == "front" and self.selected is not None
        annotation = _LeverNoteAnnotation(self.selected, self.fault)
        note = SimpleNamespace(GetAnnotation=lambda: annotation)
        self.notes.append(note)
        return note


@pytest.mark.parametrize("fault", (None, "selection_rejected", "wrong_attachment", "dangling", "shared_native_note"))
def test_real_recipe_selects_and_verifies_the_visible_free_hemisphere_face(monkeypatch, tmp_path, fault) -> None:
    """Run real detail/callout ordering, FACE attachment and drawing-thread rewrite."""
    hemisphere = _LeverFace()
    front = _LeverVisibleView("front", (_LeverFace(identity=4002), hemisphere))
    iso, detail = _LeverVisibleView("iso"), _LeverVisibleView("detail")
    document = _LeverNoteDocument((front, iso, detail), fault)
    document.EditRebuild3 = lambda: True
    hemisphere.document = document
    _thread_adapter, _thread_view, native_thread = _native_thread_note_adapter(view=detail, sheet_owned=fault == "shared_native_note")
    other_threads = [_native_thread_note_adapter(view=view)[2] for view in (front, iso)]
    if fault == "shared_native_note":
        for state in other_threads:
            state.thread.ThreadCallout = native_thread.note
    trace, qualifiers, captured = [], {}, {}
    values = {
        "OverallLength": joint.ROD_LENGTH, "RodDia": joint.ROD_DIA,
        "TipChamfer": joint.TIP_CHAMFER, "ThreadLength": joint.THREAD_LENGTH,
        "IncompleteLength": joint.INCOMPLETE_THREAD_MAX,
    }
    dimensions, annotations = {}, {}
    for name, value in values.items():
        feature = "RodProfile" if name in ("OverallLength", "RodDia", "TipChamfer") else "ThreadExtent"
        dimension = SimpleNamespace(Name=name, FullName=f"{name}@{feature}@mg-magnifying-lever.SLDPRT", SystemValue=value / 1000.0)
        dimensions[name] = dimension

        def set_text(location, text, *, name=name):
            assert location == 4  # Native below-callout text, never a detached note.
            trace.append(f"callout:{name}")
            qualifiers[name] = text

        display = SimpleNamespace(GetDimension=lambda dimension=dimension: dimension, SetText=set_text)
        annotation = SimpleNamespace(
            GetSpecificAnnotation=lambda display=display: display, position=None,
        )

        def set_position(x, y, z, *, annotation=annotation):
            annotation.position = (x, y, z)
            return True

        annotation.SetPosition = set_position
        annotation.GetPosition = lambda annotation=annotation: annotation.position

        def select_annotation(append, mark, *, annotation=annotation):
            assert not append and mark == 0
            document.selected = annotation
            return True

        annotation.Select2 = select_annotation
        annotations[name] = annotation
    deleted = []

    def delete_selected():
        deleted.append(document.selected.GetSpecificAnnotation().GetDimension().Name)
        trace.append(f"delete:{deleted[-1]}")
        document.selected = None

    document.EditDelete = delete_selected
    detail.ScaleRatio = drawing.DETAIL_SCALE
    detail.Position = drawing.DETAIL_CENTER
    detail.SetViewPosition = lambda *_a: True
    detail.GetAnnotations = lambda: tuple(annotations[name] for name in drawing.DETAIL_KEEP)
    detail.Crop2 = lambda *_a: trace.append("crop") or 1
    detail.IsCropped = lambda: True
    detail.CropViewJaggedOutline = detail.CropViewNoOutline = False
    detail.UpdateViewDisplayGeometry = lambda: None
    cx, cy = drawing.DETAIL_CENTER
    radius = drawing.DETAIL_RADIUS_MM * drawing.DETAIL_SCALE[0] / 1000.0
    detail.GetDetailCircleInfo2 = lambda: (1, 0, cx, cy, 0, cx + radius, cy, 0, cx + radius, cy, 0, 3, 0, 0, 0, 0, 0)
    source = tmp_path / "lever.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)

    async def open_model(_path):
        return SimpleNamespace(is_success=True, data=None)

    async def finalize(*_args, **kwargs):
        captured["finalize"] = kwargs
        return {"slddrw": "lever.SLDDRW"}

    def read_member(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value

    adapter = SimpleNamespace(
        currentModel=document, open_model=open_model,
        _attempt=lambda fn, default=None: fn(), _get_attr_or_call=read_member,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    views = iter((front, iso, detail))
    monkeypatch.setattr(drawing, "place_view", lambda *_a, **_kw: next(views))
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_a, **_kw: (document, object()))
    def inserted(_adapter, view, features):
        keep = drawing.DETAIL_KEEP if view is detail else drawing.FRONT_KEEP
        assert set(keep) <= set().union(*(spec.DRAWING_DIMENSIONS[name] for name in features))
        captured.setdefault("imports", []).append((view, tuple(features)))
        # Real feature import can also deliver its hidden modeled chamfer.
        # Exercise actual curation/deletion, not a prefiltered keep-list copy.
        return [
            (name, annotation) for name, annotation in annotations.items()
            if dimensions[name].FullName.split("@")[1] in features
        ]

    monkeypatch.setattr(dimension_import, "insert_feature_dimensions", inserted)
    monkeypatch.setattr(
        dimension_import._sw_type_info, "early_bound_or_flag", lambda obj, *_a, **_kw: obj,
    )

    def curate_detail(_adapter, view, *, keep, **kwargs):
        assert view is detail
        trace.append("detail import")
        captured["detail_keep"] = dict(keep)
        return dimension_import.curate_view_dimensions(_adapter, view, keep=keep, **kwargs)

    def curate_front(_adapter, view, *, keep, **kwargs):
        assert view is front
        trace.append("front import")
        return dimension_import.curate_view_dimensions(_adapter, view, keep=keep, **kwargs)

    def project(_adapter, view, point, **_kwargs):
        if view is detail:
            scale = drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1]
            return (
                drawing.DETAIL_CENTER[0] + (point[0] - drawing.DETAIL_FOCUS[0]) * scale,
                drawing.DETAIL_CENTER[1] + point[1] * scale,
            )
        scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]
        return (
            drawing.FRONT_CENTER[0] + (point[0] - dimensions["OverallLength"].SystemValue / 2.0) * scale,
            drawing.FRONT_CENTER[1] + point[1] * scale,
        )

    monkeypatch.setattr(drawing, "curate_hidden_dimensions", curate_detail)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate_front)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "import_cosmetic_threads", lambda *_a: (1, 1))
    monkeypatch.setattr(drawing, "_sketch_thread_lines", lambda _a, view, *, label: captured.setdefault("thread_lines", []).append((view, label)))
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    for name in ("read_required_properties", "stamp_drawing_summary", "set_hidden_lines_removed", "assert_imported_precision", "add_property_linked_note", "rebuild_drawing"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    monkeypatch.setattr(leader_notes, "rebuild_drawing", lambda *_a, **_kw: None)
    monkeypatch.setattr(drawing, "_circle", lambda *_a, mark=False: None if mark else trace.append("crop boundary"))
    monkeypatch.setattr(drawing, "_note", lambda _a, view, text, xy: captured.setdefault("notes", []).append((view, text, xy)))
    monkeypatch.setattr(drawing, "add_surface_finish", lambda _a, view, **kwargs: captured.update(finish=(view, kwargs)))

    def stock_reference(_adapter, display, **kwargs):
        captured["stock"] = kwargs
        display.SetText(4, kwargs["callout"])

    monkeypatch.setattr(drawing, "supplier_reference_dimension", stock_reference)

    def attach(_adapter, view, **kwargs):
        assert kwargs["text"] == spec.FREE_END_CALLOUT and view is front
        return leader_notes.add_attached_note(_adapter, view, **kwargs)

    monkeypatch.setattr(drawing, "add_attached_note", attach)
    if fault is not None:
        message = ("native detail authority" if fault == "shared_native_note" else
                   "failed to select free end hemisphere face by entity" if fault == "selection_rejected" else "lost its face attachment")
        with pytest.raises(RuntimeError, match=message):
            asyncio.run(drawing.build(adapter))
    else:
        assert asyncio.run(drawing.build(adapter)) == {"slddrw": "lever.SLDDRW"}
        assert len(document.notes) == 1
        annotation = document.notes[0].GetAnnotation()
        assert annotation.GetAttachedEntities3() == (hemisphere,)
        assert annotation.GetAttachedEntityTypes() == (2,)
        assert annotation.position == (0.030, 0.185, 0.0)
        assert annotation.GetLeaderCount() == 1 and not annotation.IsDangling()
        assert trace.index("detail import") < trace.index("crop boundary") < trace.index("crop") < trace.index("front import")
        assert trace.index("crop") < trace.index("callout:IncompleteLength")
        assert trace.index("front import") < trace.index("delete:TipChamfer") < trace.index("callout:RodDia")
        assert set(qualifiers) == {"RodDia", "IncompleteLength"}
        assert captured["imports"] == [(detail, ("ThreadExtent",)), (front, ("RodProfile",))]
        assert deleted == ["TipChamfer"] and annotations["TipChamfer"].position is None
        fit = qualifiers["RodDia"]
        assert fit == spec.ROD_DIA_CALLOUT and "BRASS" not in fit
        stock = captured["stock"]
        assert (stock["units"], stock["expected_mm"], stock["fraction_denominator"]) == ("in", joint.ROD_DIA, 4)
        assert {name: dimension.SystemValue * 1000.0 for name, dimension in dimensions.items()} == pytest.approx(values)
        assert captured["finish"][0] is front
        assert captured["finish"][1]["control"] is spec.SURFACE_FINISHES[0]
        assert captured["notes"][0][1] == "MHA-MG-02 SCREW SEAT"
        finish = captured["finish"][1]
        assert finish["entity_type"] == "FACE" and finish["char_height"] == 0.0025
        assert finish["edge_xy"] == finish["leader_attach_xy"]
        controlled = drawing.face_geometry(front.faces[0])
        assert finish["control"].face.matches(controlled)
        assert not finish["control"].face.matches(drawing.face_geometry(hemisphere))
        left = project(None, front, (controlled.box[0], 0.0, 0.0))[0]
        right = project(None, front, (controlled.box[3], 0.0, 0.0))[0]
        assert left < finish["edge_xy"][0] < right
        _assert_finish_ink_routes(annotations, finish, captured["notes"][0][2], project, front)
        assert native_thread.writes == [spec.PRINT_THREAD_CALLOUT.replace("\n", "\r\n")]
        assert native_thread.note.GetText() == native_thread.writes[0]
        assert native_thread.note.GetAnnotation().Visible == 1
        assert native_thread.note.GetAnnotation().GetPosition() == (*drawing.DETAIL_THREAD_NOTE_XY, 0.0)
        _assert_detail_thread_ink_routes(annotations, native_thread.note, project, detail)
        assert all(state.note.GetAnnotation().Visible == 3 for state in other_threads)
        assert all(state.writes == [] and "UNC-2A" in state.note.GetText() for state in other_threads)
        assert native_thread.note.GetAnnotation().Owner is detail
        assert native_thread.thread.ThreadCallout is native_thread.note
        assert "UNC-2A" in native_thread.model_thread.ThreadCallout
        # The incomplete-length qualifier also stays beyond its actual,
        # source-derived tip witness; no fixed sheet-x surrogate.
        incomplete_xy = annotations["IncompleteLength"].GetPosition()
        tip_x = project(None, detail, (joint.ROD_LENGTH / 1000.0, 0.0, 0.0))[0]
        rows = qualifiers["IncompleteLength"].splitlines()
        assert rows == spec.LEAD_CALLOUT.splitlines() and len(rows) == 3
        assert incomplete_xy[0] - max(map(len, rows)) * 0.0035 / 2.0 > tip_x
        assert captured["finalize"]["layout"] is drawing.SPEC.layout
        assert captured["thread_lines"] == [(detail, "Detail A"), (front, "front")]
    assert hemisphere.selection_attempts == 1
    assert front.entity_kinds == [3, 4]

def _assert_detail_thread_ink_routes(annotations, native_note, project, detail):
    """R10 measured glyph/witness replay, not proof of a new native font/leader.

    Retained R10 detail ink is recorded in the pre-cutover replay. Its glyph
    advances/row offsets expose the unwrapped mate row crossing the tip witness.
    Transfer those envelopes to the actual recipe's one native note and native
    dimension station. The new native callout still needs a full ink audit.
    """
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    region = DrawableRegion.from_margins(
        template.width_m, template.height_m,
        left=0.0127, right=0.0127, top=0.0127, bottom=0.0127,
    )
    values = {
        name: annotation.GetSpecificAnnotation().GetDimension().SystemValue
        for name, annotation in annotations.items()
    }
    root = project(None, detail, (
        values["OverallLength"] - values["ThreadLength"], values["RodDia"] / 2.0, 0.0,
    ))
    tip = project(None, detail, (values["OverallLength"], values["RodDia"] / 2.0, 0.0))
    x, y, _z = native_note.GetAnnotation().GetPosition()
    text = native_note.GetText()
    assert text.splitlines() == [f"{joint.THREAD} UNC", "MATES MHA-MG-01", "BRACKET"]
    dx, dy = x - 0.273, y - 0.213
    rows = (
        Box(0.2736628 + dx, 0.2090349 + dy, 0.2982645 + dx, 0.2129736 + dy),
        Box(x + 0.0002567, 0.2048825 + dy, x + 0.0423395, 0.2084479 + dy),
        # BRACKET measured19.5154mm; conservative20.5mm envelope.
        Box(x, 0.2048825 + dy - 0.0045257, x + 0.0205, 0.2084479 + dy - 0.0045257),
    )
    lx, ly, _z = annotations["ThreadLength"].GetPosition()
    length = AnnotationGeometry(
        label="ThreadLength", kind="dim", owner="detail",
        text_boxes=(Box(lx - 0.0051559, ly - 0.0018442, lx + 0.0056694, ly + 0.0017211),),
        segments=(
            Segment(root[0], root[1] + 0.001, root[0], ly - 0.0017781, "ext-line"),
            Segment(tip[0], tip[1] + 0.001, tip[0], ly - 0.0017781, "ext-line"),
            Segment(root[0], ly - 0.0027781, tip[0], ly - 0.0027781, "dim-line"),
        ),
    )
    # Under the rod, the incomplete-thread witnesses run down from the rod to
    # their dimension line below the qualifier station; charge them to 10 mm
    # below that station.
    ix, iy, _z = annotations["IncompleteLength"].GetPosition()
    bottom = -values["RodDia"] / 2.0
    incomplete = AnnotationGeometry(
        label="IncompleteLength", kind="dim", owner="detail",
        segments=tuple(
            Segment(px, py - 0.001, px, iy - 0.010, "ext-line")
            for px, py in (
                project(None, detail, (values["OverallLength"] - values["IncompleteLength"], bottom, 0.0)),
                project(None, detail, (values["OverallLength"], bottom, 0.0)),
            )
        ),
    )
    # The R10 unwrapped mate/BRACKET row spans64.3701mm. It crosses the
    # source-derived incomplete-thread witness at this station; keep the control.
    unwrapped = AnnotationGeometry(
        label="native detail thread", kind="note", owner="detail",
        text_boxes=(Box(x + 0.0002567, rows[1].ymin, x + 0.0646268, rows[1].ymax),),
    )
    before = SheetGeometry("Sheet1", template.width_m, template.height_m, region, annotations=(length, incomplete, unwrapped))
    assert any(item.a == unwrapped.label for item in find_text_on_line(before))
    wrapped = AnnotationGeometry(label=unwrapped.label, kind="note", owner="detail", text_boxes=rows)
    after = SheetGeometry("Sheet1", template.width_m, template.height_m, region, annotations=(length, incomplete, wrapped))
    assert find_text_on_line(after) == []
    assert find_text_on_text(after) == []
    assert find_border_breaches(after) == []
    # The rows sit wholly under the rod: the leader rises to its near edge.
    assert max(row.ymax for row in rows) < project(None, detail, (0.0, bottom, 0.0))[1]
    witnesses = (*length.segments[:2], *incomplete.segments)
    assert min(segment_box_distance(witness, row) for witness in witnesses for row in rows) >= ARROW_TEXT_CLEARANCE_M



def _assert_finish_ink_routes(annotations, finish, seat_note_xy, project, front):
    """R24/779's actual crossing, then real curation's shorter diameter witness.

    Frozen PDF 5248c090... / native audit bd245427... supply symbol strokes
    and glyph ink. The finish stays fixed; only the imported dimension moves.
    New native witness routing and printed clearance remain a seat gate.
    """
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    region = DrawableRegion.from_margins(
        template.width_m, template.height_m,
        left=0.0127, right=0.0127, top=0.0127, bottom=0.0127,
    )

    def sheet(*items):
        return SheetGeometry(
            "Sheet1", template.width_m, template.height_m, region, annotations=items,
        )

    diameter = annotations["RodDia"].GetSpecificAnnotation().GetDimension().SystemValue
    body_y = project(None, front, (0.0, 0.0, 0.0))[1]
    witness_x = project(None, front, (diameter / 2.0, 0.0, 0.0))[0] + 0.001
    upper, lower = body_y + diameter / 2.0, body_y - diameter / 2.0

    # Measured R24 ink: an 86.9 mm block for the 34-glyph "MHA-MG-02 CLAMP
    # BORE - SLIDING FIT" row; the stated-clearance row scales it by glyphs.
    width = 0.0868955 * max(map(len, spec.ROD_DIA_CALLOUT.splitlines())) / 34

    def diameter_ink(x, y):
        underline = y - 0.0100819
        return AnnotationGeometry(
            label="RodDia", kind="dim", owner="front",
            text_boxes=(Box(x + 0.0002566, y - 0.009148,
                            x + width, y + 0.0100555),),
            segments=(
                Segment(witness_x, lower, x + 0.001, lower, "ext-line"),
                Segment(witness_x, upper, x + 0.001, upper, "ext-line"),
                Segment(x + width + 0.0000746, underline, x, underline, "dim-line"),
                Segment(x, underline, x, upper, "dim-line"),
                Segment(x, lower, x, lower - diameter, "dim-line"),
            ),
            exact=True,
        )

    # These are native GetDisplayData strokes, not the view's padded outline.
    finish_strokes = (
        (0.060, 0.140, 0.0676, 0.140, "shoulder"),
        (0.0676, 0.140, 0.0709518, 0.1216352, "leader"),
        (0.06125, 0.140, 0.059085, 0.14375, "line"),
        (0.063415, 0.14375, 0.059085, 0.14375, "line"),
        (0.06125, 0.140, 0.0654635, 0.1471425, "line"),
        (0.0627805, 0.1456118, 0.0597195, 0.1456118, "line"),
        (0.0654635, 0.1471425, 0.0757125, 0.1471425, "line"),
    )
    old_finish = AnnotationGeometry(
        label="seat finish", kind="surface-finish", owner="front",
        text_boxes=(Box(0.0665535, 0.1442383, 0.0759737, 0.146785),),
        segments=tuple(Segment(*stroke) for stroke in finish_strokes), exact=True,
    )
    before_dia = diameter_ink(0.118, 0.150)
    before = find_leader_across_lines(sheet(before_dia, old_finish))
    crossing = next(item for item in before if item.a == old_finish.label and item.b == before_dia.label)
    assert crossing.kind == "leader-crosses-line"
    assert crossing.at_mm == pytest.approx((70.67076771867922, 123.175))

    # Keep the proven native finish x, physical landing and mate label; the
    # symbol and its label sit 2.5 mm under the measured R24 station.
    drop = 0.140 - finish["symbol_xy"][1]
    assert finish["symbol_xy"] == pytest.approx((0.06125, 0.1375))
    assert finish["leader_attach_xy"] == pytest.approx(
        project(None, front, (0.040, diameter / 4.0, 0.0))
    )
    assert seat_note_xy == pytest.approx((0.05875, 0.153 - drop))
    new_finish = AnnotationGeometry(
        label=old_finish.label, kind="surface-finish", owner="front",
        text_boxes=(Box(0.0665535, 0.1442383 - drop, 0.0759737, 0.146785 - drop),),
        segments=tuple(
            Segment(x0, y0 - drop, x1, y1 if kind == "leader" else y1 - drop, kind)
            for x0, y0, x1, y1, kind in finish_strokes
        ),
        exact=True,
    )
    dx, dy, _z = annotations["RodDia"].GetPosition()
    rod_dia = diameter_ink(dx, dy)
    nx, ny = seat_note_xy
    seat_label = AnnotationGeometry(
        label="seat mate", kind="note", owner="front",
        text_boxes=(Box(nx + 0.0002567, ny - 0.0035918,
                        nx + 0.0562705, ny - 0.0000264),), exact=True,
    )
    # Actual neighboring R24 ink: the front native thread note and parent A.
    thread_note = AnnotationGeometry(
        label="front thread", kind="note", owner="front",
        text_boxes=(Box(0.203237, 0.1176522, 0.2677471, 0.130269),), exact=True,
    )
    parent_a = AnnotationGeometry(
        label="parent A", kind="note", owner="front",
        text_boxes=(Box(0.203362, 0.1324876, 0.2065895, 0.1358896),), exact=True,
    )
    free_end = AnnotationGeometry(
        label="free hemisphere", kind="note", owner="front",
        text_boxes=(Box(0.030406, 0.1814082, 0.1025834, 0.1849736),),
        segments=(Segment(0.0291609, 0.183542, 0.0335495, 0.1169481, "leader"),),
        exact=True,
    )
    after = sheet(rod_dia, new_finish, seat_label, thread_note, parent_a, free_end)
    assert find_leader_across_lines(after) == []
    assert find_text_on_line(after) == []
    assert find_text_on_text(after) == []
    assert find_leader_through_text(after) == []
    assert find_border_breaches(after) == []
    moved = {rod_dia.label, new_finish.label, seat_label.label}
    for check in (find_text_clearance, find_text_separation):
        assert not [
            item for item in check(after) if item.a in moved or item.b in moved
        ]
    assert min(min(line.x0, line.x1) for line in new_finish.segments) - (dx + 0.001) > 0.003
    # The seat label stands 5 mm clear of the callout's underline, not a third row.
    assert dy - 0.0100819 - seat_label.text_boxes[0].ymax > 0.005
    assert rod_dia.text_boxes[0].ymin - seat_label.text_boxes[0].ymax > 0.0038
    assert free_end.text_boxes[0].ymin - rod_dia.text_boxes[0].ymax > 0.0053




def _native_thread_note_adapter(*, view=None, attachment_types=(), sheet_owned=False, nullable_empty_arrays=False, fault=None, null_entity_index=0, missing_callout=False):
    """Expose a drawing ICThread/INote graph, separate from native part metadata."""
    view = SimpleNamespace() if view is None else view
    state = SimpleNamespace(
        text=spec.THREAD_CALLOUT, writes=[], reads=[], entities=tuple(object() for _ in attachment_types),
        entity_types=tuple(attachment_types), dangling=False,
        model_thread=SimpleNamespace(ThreadCallout=spec.THREAD_CALLOUT, thread_class="2A"),
    )
    def observed(field, value):
        if state.writes:
            state.reads.append(field)
        return value

    def attached_types():
        observed("attached_types", None)
        if fault in ("post_types_unavailable", "post_multiple_readers_unavailable") and state.writes:
            raise RuntimeError("native attached-type getter refused after mutation")
        return None if nullable_empty_arrays else state.entity_types

    def attached_entities():
        observed("attached_entities", None)
        if fault == "post_entities_unavailable" and state.writes:
            raise RuntimeError("native attached-entity getter refused after mutation")
        return None if nullable_empty_arrays else state.entities

    annotation = SimpleNamespace(
        OwnerType=int(sheet_owned), Owner=object() if sheet_owned else view,
        GetAttachedEntities3=attached_entities,
        GetAttachedEntityTypes=attached_types,
        GetAttachedEntityCount3=lambda: observed("attached_count", len(state.entities) + int(fault == "incomplete_attachments")),
        IsDangling=lambda: observed("dangling", state.dangling),
    )
    annotation.Visible = 1
    annotation.position = None
    annotation.SetPosition2 = lambda x, y, z: setattr(annotation, "position", (x, y, z)) is None
    annotation.GetPosition = lambda: annotation.position

    def set_text(text):
        state.writes.append(text)
        if fault == "setter_refused":
            return False
        if fault != "ignored_text":
            state.text = text
        if fault == "owner_changed":
            annotation.Owner = object()
        elif fault == "owner_type_changed":
            annotation.OwnerType = 3
        elif fault == "attachment_lost":
            state.entities, state.entity_types = (), ()
        elif fault == "attachment_changed":
            state.entities = tuple(object() for _ in state.entities)
        elif fault == "post_null_entity":
            if state.entities:
                state.entities = tuple(None if index == null_entity_index else entity for index, entity in enumerate(state.entities))
            else:
                state.entities, state.entity_types = (None,), (2,)
        elif fault == "attachment_type_changed":
            state.entity_types = tuple(46 for _ in state.entity_types)
        elif fault == "dangling":
            state.dangling = True
        elif fault == "note_replaced":
            state.thread.ThreadCallout = SimpleNamespace(
                GetText=lambda: state.text, GetAnnotation=lambda: annotation,
            )
        elif fault == "note_removed":
            state.thread.ThreadCallout = None
        elif fault == "owner_removed":
            annotation.Owner = None
        elif fault == "windows_newlines":
            state.text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        elif fault == "changed_thread_text":
            state.text = text.replace(joint.THREAD, "1/4-28", 1)
        elif fault == "malformed_line_endings":
            state.text = text.replace("\r\n", "\r\r\n")
        elif fault == "collapsed_blank_line":
            state.text = text.replace("\r\n\r\n", "\r\n")
        elif fault == "changed_spacing":
            state.text = text.replace("  MATES", "MATES").rstrip(" ")
        elif fault == "multiple_post_changes":
            state.text = "native returned text\r\nwith extra row"
            annotation.Owner, annotation.OwnerType = object(), 3
            state.entities, state.entity_types = (object(), object()), (46, 46)
            state.dangling = True
        elif fault == "post_text_unavailable":
            state.text = None
        elif fault == "post_text_empty":
            state.text = ""
        elif fault == "post_dangling_unavailable":
            state.dangling = None
        elif fault == "post_multiple_readers_unavailable":
            state.text, state.dangling = None, None
        return True

    state.note = SimpleNamespace(
        GetText=lambda: observed("text", state.text),
        GetAnnotation=lambda: observed("annotation_handle", None if fault == "post_annotation_unavailable" and state.writes else annotation),
        SetText=set_text,
    )
    state.creation_calls, state.selection, state.active_view = [], None, None
    thread_annotation = SimpleNamespace()

    def select_thread(_append, _mark):
        state.selection = SimpleNamespace(GetAnnotation=lambda: object()) if fault == "creation_wrong_selection" else state.thread
        return fault != "creation_selection_refused"

    thread_annotation.Select2 = select_thread
    state.thread = SimpleNamespace(ThreadCallout=state.note, GetNext=lambda: None, GetAnnotation=lambda: thread_annotation)
    state.original_thread = state.thread
    view.GetCThreadCount = lambda: 0 if fault == "no_seed" else 1
    view.GetFirstCThread = lambda: state.thread
    if not hasattr(view, "GetName2"):
        view.GetName2 = lambda: "Detail A"
    if not hasattr(view, "UpdateViewDisplayGeometry"):
        view.UpdateViewDisplayGeometry = lambda: state.creation_calls.append("update_geometry")

    def insert_thread_callout():
        state.creation_calls.append("insert")
        assert state.active_view == "Detail A" and state.selection is state.thread
        assert not state.writes  # Creation precedes the print-only mutation.
        if fault != "no_note":
            state.thread.ThreadCallout = state.note
        if fault == "creation_thread_replaced":
            state.thread = SimpleNamespace(ThreadCallout=state.note, GetNext=lambda: None, GetAnnotation=lambda: object())
        return None  # IDrawingDoc.InsertThreadCallout is VT_VOID.

    def activate_view(name):
        state.active_view = name
        return True

    def clear_selection(_all):
        state.selection = None

    manager = SimpleNamespace(
        GetSelectedObjectCount2=lambda _mark: int(state.selection is not None),
        GetSelectedObjectType3=lambda _index, _mark: 1 if fault == "creation_wrong_type" else 39,
        GetSelectedObject6=lambda _index, _mark: state.selection,
    )
    draw = SimpleNamespace(
        SelectionManager=manager, ClearSelection2=clear_selection,
        ActivateView=activate_view, InsertThreadCallout=insert_thread_callout,
    )
    if missing_callout:
        state.thread.ThreadCallout = None
    if fault == "no_note":
        state.thread.ThreadCallout = None
    elif fault == "unexpected_text":
        state.text = "M6 X 1-6g"
    elif fault == "part_owner":
        annotation.OwnerType = 3
    elif fault == "other_view_owner":
        annotation.Owner = object()
    def same(first, second):
        observed("identity", None)
        if fault == "identity_unsupported":
            return 2
        if fault == "owner_comparison_unsupported" and state.writes and first is annotation.Owner and second is annotation.Owner:
            return 2
        return int(first is second)

    adapter = SimpleNamespace(
        swApp=SimpleNamespace(IsSame=same), currentModel=draw,
        _get_attr_or_call=lambda native, member: getattr(native, member)(),
    )
    return adapter, view, state


@pytest.mark.parametrize("sheet_owned", (False, True))
@pytest.mark.parametrize("attachment_types, nullable_empty_arrays", (((), False), ((), True), ((1,), False), ((2,), False)))
def test_printed_thread_class_override_keeps_the_actual_drawing_note_and_native_metadata(monkeypatch, attachment_types, nullable_empty_arrays, sheet_owned) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=attachment_types, nullable_empty_arrays=nullable_empty_arrays, sheet_owned=sheet_owned)
    original_entities, original_owner = state.entities, state.note.GetAnnotation().Owner
    original_model_text = state.model_thread.ThreadCallout
    records = []
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **fields: records.append((message, fields)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    drawing._print_native_thread_callout(adapter, view)
    assert state.thread.ThreadCallout is state.note
    assert state.note.GetAnnotation().Owner is original_owner
    assert state.note.GetAnnotation().OwnerType == int(sheet_owned)
    assert state.entities == original_entities and state.entity_types == attachment_types
    assert state.writes == [state.note.GetText()]
    assert state.writes == [spec.PRINT_THREAD_CALLOUT.replace("\n", "\r\n")]
    assert joint.THREAD in state.note.GetText() and "MATES MHA-MG-01 BRACKET" in " ".join(state.note.GetText().split())
    assert "2A" not in state.note.GetText()
    assert state.model_thread.ThreadCallout == original_model_text
    assert state.model_thread.thread_class == "2A"
    assert state.creation_calls == []  # Existing native INote must not be duplicated.
    if nullable_empty_arrays:
        assert state.note.GetAnnotation().GetAttachedEntities3() is None
        assert state.note.GetAnnotation().GetAttachedEntityTypes() is None
        assert state.note.GetAnnotation().GetAttachedEntityCount3() == 0
    for message, attributes in records:
        payload = message.split("audit: ", 1)[1]
        audit = json.loads(payload)
        assert audit["portable_text"] == spec.PRINT_THREAD_CALLOUT
        assert audit["requested_text"] == state.writes[0]
        assert attributes["auditJSON"] == payload
        assert attributes["operation_stage"] == audit["stage"]
        assert json.loads(attributes["failed_conditions"]) == audit.get("failed", [])


@pytest.mark.parametrize("fault, message", (
    (None, None),
    ("no_note", "no native drawing callout note"),
    ("creation_selection_refused", "cannot select its native cosmetic thread"),
    ("creation_wrong_type", "cannot select its native cosmetic thread"),
    ("creation_wrong_selection", "cannot select its native cosmetic thread"),
    ("creation_thread_replaced", "lost identity after callout insertion"),
    ("identity_unsupported", "annotation identity is unavailable"),
    ("unexpected_text", "unexpected native lever thread callout"),
))
def test_missing_native_thread_callout_is_created_only_on_the_verified_thread(monkeypatch, fault, message):
    """Replay R2's missing INote; this is a native-object protocol mock, not COM proof."""
    adapter, view, state = _native_thread_note_adapter(missing_callout=True, attachment_types=(2,), fault=fault)
    messages = []
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, native: native.GetName2())
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **fields: messages.append((message, fields)))
    if message is not None:
        with pytest.raises(RuntimeError, match=message):
            drawing._print_native_thread_callout(adapter, view)
        assert state.writes == []
    else:
        annotation = drawing._print_native_thread_callout(adapter, view)
        assert annotation is state.note.GetAnnotation()
        assert state.thread is state.original_thread and state.thread.ThreadCallout is state.note
        assert state.writes == [spec.PRINT_THREAD_CALLOUT.replace("\n", "\r\n")]
        assert len(state.writes[0].splitlines()) == 3
        assert state.entities == state.note.GetAnnotation().GetAttachedEntities3()
        assert state.model_thread.ThreadCallout == spec.THREAD_CALLOUT
        assert state.model_thread.thread_class == "2A"
        creation = [json.loads(message.split("creation: ", 1)[1]) for message, _fields in messages if "creation: " in message]
        assert creation[-1] == {
            "callout_before": False, "callout_after": True, "requested": True,
            "selection_count": 1, "selection_type": 39, "same_thread": True,
        }
    assert state.creation_calls.count("insert") == int(fault in (None, "no_note", "creation_thread_replaced", "unexpected_text"))
    assert state.selection is None


@pytest.mark.parametrize("fault, message", (
    ("no_seed", "one native cosmetic-thread seed"),
    ("no_note", "no native drawing callout note"),
    ("unexpected_text", "unexpected native lever thread callout"),
    ("part_owner", "not owned by a drawing view"),
    ("other_view_owner", "belongs to another drawing view"),
    ("incomplete_attachments", "attachment census is incomplete"),
    ("identity_unsupported", "identity comparison unsupported: self=2"),
    ("setter_refused", "refused its print-only text"),
    ("ignored_text", "lost its text, ownership or native attachment"),
    ("owner_changed", "lost its text, ownership or native attachment"),
    ("owner_type_changed", "lost its text, ownership or native attachment"),
    ("attachment_lost", "lost its text, ownership or native attachment"),
    ("attachment_changed", "lost its text, ownership or native attachment"),
    ("attachment_type_changed", "lost its text, ownership or native attachment"),
    ("dangling", "lost its text, ownership or native attachment"),
    ("note_replaced", "replaced its native drawing callout"),
    ("note_removed", "native thread callout readback failed"),
    ("owner_removed", "native thread callout readback failed"),
    ("changed_thread_text", "lost its text, ownership or native attachment"),
    ("malformed_line_endings", "lost its text, ownership or native attachment"),
    ("multiple_post_changes", "lost its text, ownership or native attachment"),
    ("owner_comparison_unsupported", "lost its text, ownership or native attachment"),
    ("post_types_unavailable", "native thread callout readback failed"),
    ("post_text_unavailable", "native thread callout readback failed"),
    ("post_dangling_unavailable", "native thread callout readback failed"),
    ("post_entities_unavailable", "native thread callout readback failed"),
    ("post_annotation_unavailable", "native thread callout readback failed"),
    ("post_multiple_readers_unavailable", "native thread callout readback failed"),
    ("post_text_empty", "lost its text, ownership or native attachment"),
))
def test_thread_class_override_refuses_unsupported_or_changed_native_identity(monkeypatch, fault, message) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=(2,), fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match=message):
        drawing._print_native_thread_callout(adapter, view)
    assert state.model_thread.ThreadCallout.endswith("MATES MHA-MG-01 BRACKET")
    assert "UNC-2A" in state.model_thread.ThreadCallout and state.model_thread.thread_class == "2A"


@pytest.mark.parametrize("fault, failed", (
    ("ignored_text", {"text"}),
    ("changed_thread_text", {"text"}),
    ("malformed_line_endings", {"text"}),
    ("post_text_empty", {"text"}),
    ("owner_changed", {"owner_identity"}),
    ("owner_comparison_unsupported", {"owner_identity"}),
    ("attachment_changed", {"entity_identity"}),
    ("multiple_post_changes", {
        "text", "owner_type", "owner_identity", "attached_count",
        "attached_types", "entities_reported", "entity_identity", "dangling",
    }),
))
def test_native_thread_audit_records_every_actual_postcondition_before_refusing(monkeypatch, fault, failed) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=(2,), fault=fault)
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **fields: messages.append((message, fields)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError) as caught:
        drawing._print_native_thread_callout(adapter, view)
    audit = json.loads(str(caught.value).split("; audit=", 1)[1])
    assert json.loads(messages[-1][0].split("audit: ", 1)[1]) == audit
    assert messages[-1][1]["operation_stage"] == audit["stage"]
    assert json.loads(messages[-1][1]["auditJSON"]) == audit
    assert set(json.loads(messages[-1][1]["failed_conditions"])) == failed
    assert audit["stage"] == "readback_complete" and audit["setter_result"] is True
    assert set(audit["failed"]) == failed
    assert audit["before"]["text"] == spec.THREAD_CALLOUT
    assert audit["before"]["attached_count"] == 1 and audit["before"]["attached_types"] == [2]
    assert audit["before"]["self_comparisons"] == [
        {"role": "callout", "field": "before.note_self", "code": 1},
        {"role": "owner", "field": "before.owner_self", "code": 1},
        {"role": "attachment", "field": "before.entity_self[0]", "code": 1},
    ]
    after = audit["after"]
    assert after["text"] == state.text
    assert after["owner_type"] == state.note.GetAnnotation().OwnerType
    assert after["attached_count"] == after["entities_reported"] == len(state.entities)
    assert after["attached_types"] == list(state.entity_types)
    assert after["dangling"] is state.dangling
    assert after["note_same"] == after["note_self"] == 1
    assert len(after["entity_same"]) == 1
    assert after["entity_self"] == [{"index": index, "code": 1} for index in range(len(state.entities))]
    if fault == "owner_comparison_unsupported":
        assert after["owner_same"] == after["owner_self"] == 2
    if fault == "multiple_post_changes":
        assert after["owner_same"] == 0 and after["entity_same"] == [{"index": 0, "code": 0}]
        assert after["text"] == "native returned text\r\nwith extra row"
    assert audit["portable_text"] == spec.PRINT_THREAD_CALLOUT
    assert audit["requested_text"] == state.writes[0]
    assert audit["read_errors"] == [] and audit["unavailable"] == {}


def test_native_thread_audit_names_unavailable_post_reader_without_inventing_zero_state(monkeypatch) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=(2,), fault="post_types_unavailable")
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **fields: messages.append((message, fields)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="readback failed") as caught:
        drawing._print_native_thread_callout(adapter, view)
    audit = json.loads(str(caught.value).split("; audit=", 1)[1])
    assert audit["read_errors"] == [{
        "field": "attached_types", "member": "IAnnotation.GetAttachedEntityTypes", "kind": "exception",
        "type": "RuntimeError", "message": "native attached-type getter refused after mutation",
    }]
    assert audit["before"]["attached_types"] == [2]
    after = audit["after"]
    assert after["attached_count"] == after["entities_reported"] == 1
    assert after["note_same"] == after["note_self"] == 1 and after["text"] == state.text
    assert after["owner_same"] == after["owner_self"] == 1
    assert "attached_types" not in after and after["dangling"] is False
    assert after["entity_same"] == after["entity_self"] == [{"index": 0, "code": 1}]
    assert state.reads.index("attached_types") < state.reads.index("dangling")
    assert "identity" in state.reads[state.reads.index("attached_types") + 1:]
    assert audit["unavailable"] == {} and audit["stage"] == "readback_complete"
    assert set(audit["failed"]) == {"attached_types", "reader_unavailable"}
    assert json.loads(messages[-1][0].split("audit: ", 1)[1]) == audit
    assert messages[-1][1]["operation_stage"] == audit["stage"]
    assert json.loads(messages[-1][1]["auditJSON"]) == audit
    assert set(json.loads(messages[-1][1]["failed_conditions"])) == {"attached_types", "reader_unavailable"}


@pytest.mark.parametrize("fault, field, reader", (
    ("post_text_unavailable", "text", "INote.GetText"),
    ("post_dangling_unavailable", "dangling", "IAnnotation.IsDangling"),
))
def test_native_thread_audit_preserves_null_scalar_readback_and_marks_the_exact_reader(monkeypatch, fault, field, reader) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=(2,), fault=fault)
    records = []
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **fields: records.append((message, fields)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="readback failed") as caught:
        drawing._print_native_thread_callout(adapter, view)
    audit = json.loads(str(caught.value).split("; audit=", 1)[1])
    assert audit["after"][field] is None
    assert audit["read_errors"] == [{"field": field, "member": reader, "kind": "returned_none", "value": None}]
    assert audit["stage"] == "readback_complete"
    assert set(audit["failed"]) == {field, "reader_unavailable"}
    assert audit["before"]["dangling"] is False
    after = audit["after"]
    assert after["note_same"] == after["note_self"] == after["owner_same"] == after["owner_self"] == 1
    assert after["attached_count"] == after["entities_reported"] == 1
    assert after["attached_types"] == [2]
    assert after["entity_same"] == after["entity_self"] == [{"index": 0, "code": 1}]
    assert audit["unavailable"] == {}
    assert all(name in state.reads for name in ("text", "annotation_handle", "attached_entities", "attached_count", "attached_types", "dangling"))
    if field == "text":
        assert after["dangling"] is False
    else:
        assert after["text"] == state.text == spec.PRINT_THREAD_CALLOUT.replace("\n", "\r\n")
    message, attributes = records[-1]
    assert json.loads(message.split("audit: ", 1)[1]) == audit
    assert json.loads(attributes["auditJSON"]) == audit
    assert attributes["operation_stage"] == audit["stage"]
    assert set(json.loads(attributes["failed_conditions"])) == {field, "reader_unavailable"}


@pytest.mark.parametrize("portable", (
    spec.PRINT_THREAD_CALLOUT,
    f"{joint.THREAD} UNC\n\n  MATES MHA-MG-01 BRACKET  \n",
))
def test_native_thread_boundary_sends_exact_crlf_and_preserves_the_portable_rows(monkeypatch, portable) -> None:
    """Replay R8's native CRLF behavior without normalizing its readback."""
    adapter, view, state = _native_thread_note_adapter(fault="windows_newlines")
    state.text = spec.THREAD_CALLOUT.replace("\n", "\r\n")
    records = []
    monkeypatch.setattr(drawing, "PRINT_THREAD_CALLOUT", portable)
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **fields: records.append((message, fields)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    drawing._print_native_thread_callout(adapter, view)
    native = portable.replace("\n", "\r\n")
    assert state.writes == [native] and state.text == native
    assert native.split("\r\n") == portable.split("\n")
    assert "\r\r\n" not in native and "\r" not in spec.PRINT_THREAD_CALLOUT
    assert state.model_thread.ThreadCallout == spec.THREAD_CALLOUT and state.model_thread.thread_class == "2A"
    for message, attributes in records:
        audit = json.loads(attributes["auditJSON"])
        assert audit == json.loads(message.split("audit: ", 1)[1])
        assert audit["portable_text"] == portable and audit["requested_text"] == native
    assert audit["after"]["text"] == native and audit["conditions"]["text"] is True
    assert audit["after"]["note_same"] == audit["after"]["owner_same"] == 1
    assert audit["after"]["attached_count"] == audit["after"]["entities_reported"] == 0
    assert audit["after"]["attached_types"] == audit["after"]["entity_same"] == []
    assert audit["after"]["dangling"] is False and audit["failed"] == audit["read_errors"] == []


@pytest.mark.parametrize("fault", ("changed_thread_text", "collapsed_blank_line", "changed_spacing"))
def test_native_thread_exact_crlf_contract_still_rejects_changed_ink_or_row_structure(monkeypatch, fault) -> None:
    portable = f"{joint.THREAD} UNC\n\n  MATES MHA-MG-01 BRACKET  "
    adapter, view, state = _native_thread_note_adapter(fault=fault)
    monkeypatch.setattr(drawing, "PRINT_THREAD_CALLOUT", portable)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="lost its text, ownership or native attachment") as caught:
        drawing._print_native_thread_callout(adapter, view)
    audit = json.loads(str(caught.value).split("; audit=", 1)[1])
    native = portable.replace("\n", "\r\n")
    assert state.writes == [native] and state.text != native
    assert audit["after"]["text"] == state.text
    assert audit["portable_text"] == portable and audit["requested_text"] == native
    assert audit["failed"] == ["text"] and audit["read_errors"] == []
    if fault != "changed_thread_text":
        assert state.text.split() == native.split()  # Whitespace-collapsing readback would wrongly accept.


def test_native_thread_census_retains_all_reader_errors_and_independent_native_fields(monkeypatch) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=(2,), fault="post_multiple_readers_unavailable")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="readback failed") as caught:
        drawing._print_native_thread_callout(adapter, view)
    audit = json.loads(str(caught.value).split("; audit=", 1)[1])
    assert [(error["field"], error["member"], error["kind"]) for error in audit["read_errors"]] == [
        ("text", "INote.GetText", "returned_none"),
        ("attached_types", "IAnnotation.GetAttachedEntityTypes", "exception"),
        ("dangling", "IAnnotation.IsDangling", "returned_none"),
    ]
    after = audit["after"]
    assert after["text"] is None and after["dangling"] is None and "attached_types" not in after
    assert after["note_same"] == after["note_self"] == after["owner_same"] == after["owner_self"] == 1
    assert after["owner_type"] == 0 and after["attached_count"] == after["entities_reported"] == 1
    assert after["entity_same"] == after["entity_self"] == [{"index": 0, "code": 1}]
    assert audit["unavailable"] == {}
    assert set(audit["failed"]) == {"text", "attached_types", "dangling", "reader_unavailable"}
    assert state.reads.index("text") < state.reads.index("annotation_handle")
    assert state.reads.index("attached_types") < state.reads.index("dangling")
    assert "identity" in state.reads[state.reads.index("attached_types") + 1:]


@pytest.mark.parametrize("fault, dependency", (
    ("note_removed", "note_handle"),
    ("post_annotation_unavailable", "annotation_handle"),
    ("owner_removed", "owner_handle"),
    ("post_entities_unavailable", "attached_entities"),
))
def test_native_thread_census_skips_only_reads_depending_on_an_unavailable_handle(monkeypatch, fault, dependency) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=(2,), fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="readback failed") as caught:
        drawing._print_native_thread_callout(adapter, view)
    audit = json.loads(str(caught.value).split("; audit=", 1)[1])
    assert [error["field"] for error in audit["read_errors"]] == [dependency]
    assert set(audit["unavailable"].values()) == {dependency}
    after = audit["after"]
    if dependency == "note_handle":
        assert after["note_present"] is False and state.reads == []
        assert "text" not in after and audit["unavailable"]["text"] == dependency
    else:
        assert after["text"] == state.writes[0] and after["note_same"] == after["note_self"] == 1
        if dependency == "annotation_handle":
            assert after["annotation_present"] is False
            assert "attached_count" not in after and "dangling" not in state.reads
        else:
            assert after["attached_count"] == 1 and after["attached_types"] == [2] and after["dangling"] is False
            if dependency == "owner_handle":
                assert after["owner_present"] is False
                assert set(audit["unavailable"]) == {"owner_same", "owner_self"}
                assert after["entity_same"] == after["entity_self"] == [{"index": 0, "code": 1}]
            else:
                assert after["owner_same"] == after["owner_self"] == 1
                assert set(audit["unavailable"]) == {"entities_reported", "entity_handles", "entity_same", "entity_self"}
                assert "entities_reported" not in after and "entity_same" not in after
                assert state.reads.index("attached_entities") < state.reads.index("attached_count") < state.reads.index("dangling")


@pytest.mark.parametrize("attachment_types, null_entity_index", (((2, 2, 2), 1), ((2,), 0), ((), 0)))
def test_native_thread_census_preserves_null_entity_slots_without_native_comparison(monkeypatch, attachment_types, null_entity_index) -> None:
    adapter, view, state = _native_thread_note_adapter(
        attachment_types=attachment_types, fault="post_null_entity", null_entity_index=null_entity_index,
    )
    original_entities, original_same, comparisons = state.entities, adapter.swApp.IsSame, []

    def same(first, second):
        if state.writes:
            comparisons.append((first, second))
        return original_same(first, second)

    adapter.swApp.IsSame = same
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="readback failed") as caught:
        drawing._print_native_thread_callout(adapter, view)
    audit = json.loads(str(caught.value).split("; audit=", 1)[1])
    dependency = f"attached_entities[{null_entity_index}]"
    assert audit["read_errors"] == [{
        "field": dependency, "member": "IAnnotation.GetAttachedEntities3",
        "kind": "missing_entity_handle", "index": null_entity_index, "value": None,
        "reason": "native attachment array entry is None",
    }]
    assert comparisons and all(first is not None and second is not None for first, second in comparisons)
    after = audit["after"]
    assert after["attached_count"] == after["entities_reported"] == len(state.entities)
    assert after["attached_types"] == list(state.entity_types) and after["dangling"] is False
    assert after["entity_handles"] == [
        {"index": index, "present": entity is not None} for index, entity in enumerate(state.entities)
    ]
    assert after["note_same"] == after["note_self"] == after["owner_same"] == after["owner_self"] == 1
    assert after["text"] == state.writes[0] and after["owner_type"] == 0
    assert after["entity_self"][null_entity_index] == {"index": null_entity_index, "unavailable": True}
    expected_unavailable = {f"entity_self[{null_entity_index}]": dependency}
    if original_entities:
        expected_unavailable[f"entity_same[{null_entity_index}]"] = dependency
        assert after["entity_same"][null_entity_index] == {"index": null_entity_index, "unavailable": True}
    else:
        assert after["entity_same"] == []  # No paired comparisons must not mean verified identity.
    assert audit["unavailable"] == expected_unavailable
    for index, entity in enumerate(state.entities):
        if entity is not None:
            assert after["entity_same"][index] == after["entity_self"][index] == {"index": index, "code": 1}
            assert sum(first is entity and second is entity for first, second in comparisons) == 2
    assert audit["conditions"]["entity_identity"] is False
    expected_failed = {"entity_identity", "reader_unavailable"}
    if not original_entities:
        expected_failed.update(("attached_count", "attached_types", "entities_reported"))
    assert set(audit["failed"]) == expected_failed
    assert state.reads.index("attached_entities") < state.reads.index("attached_types") < state.reads.index("dangling")


@pytest.mark.parametrize("field, target_kind, occurrence, member", (
    ("note_same", "note", 1, "ISldWorks.IsSame(note,current)"),
    ("note_self", "note", 2, "ISldWorks.IsSame(current,current)"),
    ("owner_same", "owner", 1, "ISldWorks.IsSame(owner,current_owner)"),
    ("owner_self", "owner", 2, "ISldWorks.IsSame(current_owner,current_owner)"),
    ("entity_same[1]", "entity", 1, "ISldWorks.IsSame(before_entity[1],current_entity[1])"),
    ("entity_self[1]", "entity", 2, "ISldWorks.IsSame(current_entity[1],current_entity[1])"),
))
def test_native_thread_census_identifies_each_actual_same_and_self_reader_separately(monkeypatch, field, target_kind, occurrence, member) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=(2, 2))
    target = {"note": state.note, "owner": view, "entity": state.entities[1]}[target_kind]
    original_same, calls = adapter.swApp.IsSame, 0

    def same(first, second):
        nonlocal calls
        if state.writes and first is target and second is target:
            calls += 1
            if calls == occurrence:
                raise RuntimeError("native identity reader refused")
        return original_same(first, second)

    adapter.swApp.IsSame = same
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="readback failed") as caught:
        drawing._print_native_thread_callout(adapter, view)
    audit = json.loads(str(caught.value).split("; audit=", 1)[1])
    assert audit["read_errors"] == [{
        "field": field, "member": member, "kind": "exception",
        "type": "RuntimeError", "message": "native identity reader refused",
    }]
    after = audit["after"]
    assert after["text"] == state.writes[0] and after["owner_type"] == 0
    assert after["attached_count"] == after["entities_reported"] == 2 and after["attached_types"] == [2, 2]
    assert after["dangling"] is False and audit["unavailable"] == {}
    for family in ("entity_same", "entity_self"):
        assert after[family][0] == {"index": 0, "code": 1}
        expected = {"index": 1, "unavailable": True} if field == f"{family}[1]" else {"index": 1, "code": 1}
        assert after[family][1] == expected
    for scalar in ("note_same", "note_self", "owner_same", "owner_self"):
        if field == scalar:
            assert scalar not in after
        else:
            assert after[scalar] == 1
    assert "reader_unavailable" in audit["failed"]


@pytest.mark.parametrize("fault", (None, "refused", "snapped"))
def test_thread_limit_and_minor_lines_are_sketched_where_the_thread_length_starts(monkeypatch, fault) -> None:
    # Simplified external thread: the limit line sits at ThreadLength's root
    # witness across the major diameter; minor lines run from it to the tip.
    limit, upper, lower = drawing.THREAD_LINES_MM
    assert limit == ((joint.ROD_LENGTH - joint.THREAD_LENGTH, -joint.ROD_DIA / 2.0), (joint.ROD_LENGTH - joint.THREAD_LENGTH, joint.ROD_DIA / 2.0))
    assert 2.0 * drawing.THREAD_MINOR_R == pytest.approx((0.25 - 1.299038 / 20.0) * 25.4)
    assert upper == ((limit[0][0], drawing.THREAD_MINOR_R), (joint.ROD_LENGTH, drawing.THREAD_MINOR_R))
    assert lower == ((limit[0][0], -drawing.THREAD_MINOR_R), (joint.ROD_LENGTH, -drawing.THREAD_MINOR_R))

    def project(_adapter, _view, point, **_kwargs):
        return (drawing.DETAIL_CENTER[0] + (point[0] - drawing.DETAIL_FOCUS[0]) * 3.0, drawing.DETAIL_CENTER[1] + point[1] * 3.0)

    class Transform:
        def __init__(self, sign):
            self.sign = sign

        def Inverse(self):
            return Transform(-self.sign)

    def create_point(values):
        def multiply(transform):
            return SimpleNamespace(ArrayData=(values[0] - transform.sign * 0.3, values[1] - transform.sign * 0.2, values[2]))
        return SimpleNamespace(MultiplyTransform=multiply)

    created = []

    def create_line(x0, y0, z0, x1, y1, z1):
        if fault == "refused":
            return None
        nudge = 0.0001 if fault == "snapped" and not created else 0.0
        created.append(((x0, y0), (x1, y1)))
        start, end = SimpleNamespace(X=x0 + nudge, Y=y0, Z=z0), SimpleNamespace(X=x1, Y=y1, Z=z1)
        return SimpleNamespace(GetStartPoint2=lambda: start, GetEndPoint2=lambda: end)

    manager = SimpleNamespace(AddToDB=False, CreateLine=create_line)
    view = SimpleNamespace(GetSketch=lambda: SimpleNamespace(ModelToSketchTransform=Transform(1.0)))
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(GetMathUtility=lambda: SimpleNamespace(CreatePoint=create_point)),
        currentModel=SimpleNamespace(SketchManager=manager, ClearSelection2=lambda _all: None),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(drawing, "_activate", lambda *_a: None)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    if fault is None:
        drawing._sketch_thread_lines(adapter, view, label="Detail A")
        sheet = [(x + 0.3, y + 0.2) for line in created for x, y in line]
        root_witness_x = project(None, view, ((joint.ROD_LENGTH - joint.THREAD_LENGTH) / 1000.0, 0.0, 0.0))[0]
        # The limit line runs across the rod at the .71's root witness.
        assert [value for point in sheet[:2] for value in point] == pytest.approx(
            [root_witness_x, 0.190 - 3 * joint.ROD_DIA / 2000.0, root_witness_x, 0.190 + 3 * joint.ROD_DIA / 2000.0]
        )
        assert [sheet[i][0] for i in (0, 2, 4)] == pytest.approx([root_witness_x] * 3)
        assert manager.AddToDB is False
    else:
        with pytest.raises(RuntimeError, match="could not sketch" if fault == "refused" else "read back"):
            drawing._sketch_thread_lines(adapter, view, label="Detail A")
        assert manager.AddToDB is False
