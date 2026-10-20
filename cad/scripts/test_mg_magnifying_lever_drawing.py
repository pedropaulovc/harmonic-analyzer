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
from _printed_tolerance import drilled_oversize_mm
from _layout_geometry import Box, Segment, segment_box_overlap_length


def _intersection(first, second):
    return max(0.0, min(first[1], second[1]) - max(first[0], second[0]))


def test_installed_full_thread_excludes_both_leads_and_both_mouths() -> None:
    overlaps = []
    for length, thread, thickness in itertools.product(
        (joint.ROD_LENGTH - joint.ROD_LENGTH_TOL, joint.ROD_LENGTH + joint.ROD_LENGTH_TOL),
        (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL, joint.THREAD_LENGTH + joint.THREAD_LENGTH_TOL),
        (joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL, joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL),
    ):
        receiver = (geom.BRACKET_LOCAL_X - thickness / 2.0 + joint.MOUTH_CHAMFER_MAX, geom.BRACKET_LOCAL_X + thickness / 2.0 - joint.MOUTH_CHAMFER_MAX)
        male = (length - thread + joint.INCOMPLETE_THREAD_MAX, length - joint.INCOMPLETE_THREAD_MAX)
        overlaps.append(_intersection(receiver, male))
        assert length >= geom.BRACKET_LOCAL_X + thickness / 2.0
    assert geom.FULL_THREAD_OVERLAP_MIN <= min(overlaps) + 1e-9
    assert geom.FULL_THREAD_OVERLAP_MIN >= joint.REQUIRED_FULL_ENGAGEMENT
    assert geom.FULL_THREAD_OVERLAP_MIN == pytest.approx(10.745)


def test_native_tip_projection_guarantees_full_overlap_independently_of_part_length() -> None:
    overlaps = []
    for thickness, projection, thread in itertools.product(
        (joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL, joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL),
        (installed.THREAD_PROJECTION - installed.THREAD_PROJECTION_TOL, installed.THREAD_PROJECTION + installed.THREAD_PROJECTION_TOL),
        (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL, joint.THREAD_LENGTH + joint.THREAD_LENGTH_TOL),
    ):
        tip = thickness + projection
        overlaps.append(_intersection((joint.MOUTH_CHAMFER_MAX, thickness - joint.MOUTH_CHAMFER_MAX), (tip - thread + joint.INCOMPLETE_THREAD_MAX, tip - joint.INCOMPLETE_THREAD_MAX)))
    assert installed.INSTALLED_FULL_ENGAGEMENT_MIN <= min(overlaps) + 1e-9
    assert installed.INSTALLED_FULL_ENGAGEMENT_MIN >= joint.REQUIRED_FULL_ENGAGEMENT
    assert installed.THREAD_PROJECTION - installed.THREAD_PROJECTION_TOL > 0.0


@pytest.mark.parametrize("change", ({"thickness": 11.0}, {"thread_length": 14.0}, {"incomplete": 3.5}, {"projection_tol": 2.0}))
def test_full_thread_proof_detects_short_neck_thread_and_overlong_runout(change) -> None:
    arguments = {"projection_tol": installed.THREAD_PROJECTION_TOL, **change}
    overlap = joint.installation_full_overlap(installed.THREAD_PROJECTION, **arguments)
    assert overlap < joint.REQUIRED_FULL_ENGAGEMENT


def test_root_runout_is_wholly_outside_receiver_at_actual_printed_corners() -> None:
    latest_full_start = joint.ROD_LENGTH + joint.ROD_LENGTH_TOL - (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL) + joint.INCOMPLETE_THREAD_MAX
    earliest_near_face = geom.BRACKET_LOCAL_X - (joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL) / 2.0
    assert latest_full_start < earliest_near_face
    assert geom.ROOT_RUNOUT_CLEARANCE_MIN == pytest.approx(earliest_near_face - latest_full_start)
    assert spec.SINGLE_LIMITS["ThreadExtent", "IncompleteLength"][0] == joint.INCOMPLETE_THREAD_MAX


def test_quarter_inch_body_has_real_drilled_slip_clearance() -> None:
    stock_low = joint.ROD_DIA + joint.ROD_DIA_BAND[1]
    stock_high = joint.ROD_DIA + joint.ROD_DIA_BAND[0]
    minimum = clamp.LEVER_BORE_DIA - stock_high
    maximum = clamp.LEVER_BORE_DIA + drilled_oversize_mm() - stock_low
    assert minimum == pytest.approx(0.15)
    assert maximum == pytest.approx(0.30)
    assert minimum > 0.0 and maximum < 0.5


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
    for length, threaded, thickness, diameter, width, fraction, radius in itertools.product(
        (joint.ROD_LENGTH - joint.ROD_LENGTH_TOL, joint.ROD_LENGTH + joint.ROD_LENGTH_TOL),
        (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL, joint.THREAD_LENGTH + joint.THREAD_LENGTH_TOL),
        (joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL, joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL),
        (joint.ROD_DIA + joint.ROD_DIA_BAND[1], joint.ROD_DIA + joint.ROD_DIA_BAND[0]),
        (clamp.BLOCK_DEPTH, clamp.STOCK_WIDTH_MAX),
        (0.0, 0.25, 0.5, 0.75, 1.0),
        (operating[0], operating[2]),
    ):
        station = geom.KNIFE_LOCAL_X - radius
        # The point is inside the material envelope, but not necessarily at
        # its centre. Either directed distance may consume the FULL width.
        west = station - fraction * width
        east = station + (1.0 - fraction) * width
        assert west >= diameter / 2.0 - 1e-9
        assert east <= length - threaded + 1e-9
        assert east <= geom.BRACKET_LOCAL_X - thickness / 2.0 + 1e-9
    # Mutation controls: neither symmetric half-width nor nominal thread
    # root can replace the conservative one-sided accepted-part endpoint.
    earliest = joint.ROD_LENGTH - joint.ROD_LENGTH_TOL - joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL
    wrong_half_width = geom.KNIFE_LOCAL_X - earliest + clamp.STOCK_WIDTH_MAX / 2.0
    wrong_nominal_root = geom.KNIFE_LOCAL_X - joint.THREAD_ROOT_X + clamp.STOCK_WIDTH_MAX
    for wrong_radius in (wrong_half_width, wrong_nominal_root):
        assert geom.KNIFE_LOCAL_X - wrong_radius + clamp.STOCK_WIDTH_MAX > earliest
    assert geom.KNIFE_LOCAL_X - (geom.KNIFE_LOCAL_X - clamp.STOCK_WIDTH_MAX) - clamp.STOCK_WIDTH_MAX < joint.ROD_DIA / 2.0


@pytest.mark.parametrize("field", ("STOCK_WIDTH_MAX", "WALL_TARGET"))
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


@pytest.mark.parametrize("fault", (None, "selection_rejected", "wrong_attachment", "dangling"))
def test_real_recipe_selects_and_verifies_the_visible_free_hemisphere_face(monkeypatch, tmp_path, fault) -> None:
    """Run real detail/callout ordering, FACE attachment and drawing-thread rewrite."""
    hemisphere = _LeverFace()
    front = _LeverVisibleView("front", (_LeverFace(identity=4002), hemisphere))
    iso, detail = _LeverVisibleView("iso"), _LeverVisibleView("detail")
    document = _LeverNoteDocument((front, iso, detail), fault)
    hemisphere.document = document
    _thread_adapter, _thread_view, native_thread = _native_thread_note_adapter(view=front)
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
        annotations[name] = SimpleNamespace(GetSpecificAnnotation=lambda display=display: display)
    detail.ScaleRatio = drawing.DETAIL_SCALE
    detail.Position = drawing.DETAIL_CENTER
    detail.SetViewPosition = lambda *_a: True
    detail.GetAnnotations = lambda: tuple(annotations[name] for name in drawing.DETAIL_KEEP)
    detail.Crop2 = lambda *_a: trace.append("crop") or 1
    detail.IsCropped = lambda: True
    detail.CropViewJaggedOutline = detail.CropViewNoOutline = False
    detail.UpdateViewDisplayGeometry = lambda: None
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
    def curate_detail(_adapter, view, *, keep, **_kwargs):
        assert view is detail
        trace.append("detail import")
        captured["detail_keep"] = dict(keep)
        return [annotations[name] for name in keep]

    def curate_front(_adapter, view, *, keep, **_kwargs):
        assert view is front
        trace.append("front import")
        return [annotations[name] for name in keep]

    def project(_adapter, view, point, **_kwargs):
        if view is detail:
            scale = drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1]
            return (
                drawing.DETAIL_CENTER[0] + (point[0] - drawing.DETAIL_FOCUS[0]) * scale,
                drawing.DETAIL_CENTER[1] + point[1] * scale,
            )
        return point[:2]

    monkeypatch.setattr(drawing, "curate_hidden_dimensions", curate_detail)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate_front)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "import_cosmetic_threads", lambda *_a: (1, 1))
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    for name in ("read_required_properties", "stamp_drawing_summary", "set_hidden_lines_removed", "assert_imported_precision", "add_property_linked_note", "rebuild_drawing"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    monkeypatch.setattr(leader_notes, "rebuild_drawing", lambda *_a, **_kw: None)
    monkeypatch.setattr(drawing, "_circle", lambda *_a, mark=False: None if mark else trace.append("crop boundary"))
    monkeypatch.setattr(drawing, "_note", lambda _a, view, text, xy: captured.setdefault("notes", []).append((view, text, xy)))
    monkeypatch.setattr(drawing, "add_surface_finish", lambda _a, view, **kwargs: captured.update(finish=(view, kwargs)))

    def attach(_adapter, view, **kwargs):
        if kwargs["text"] == spec.FREE_END_CALLOUT:
            return leader_notes.add_attached_note(_adapter, view, **kwargs)
        assert view is detail and kwargs["entity_type"] == "SILHOUETTE"
        captured["thread"] = kwargs
        return None

    monkeypatch.setattr(drawing, "add_attached_note", attach)
    if fault is not None:
        message = "failed to select free end hemisphere face by entity" if fault == "selection_rejected" else "lost its face attachment"
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
        assert trace.index("crop") < trace.index("callout:TipChamfer")
        assert trace.index("front import") < trace.index("callout:RodDia")
        assert set(qualifiers) == {"RodDia", "TipChamfer", "IncompleteLength"}
        fit = qualifiers["RodDia"]
        assert "MHA-MG-02 CLAMP BORE" in fit and "SLIDING FIT" in fit and "BRASS" not in fit
        chamfer = qualifiers["TipChamfer"]
        assert "MHA-MG-01 THREAD ENTRY" in chamfer and "FULL ENGAGEMENT" in chamfer
        assert "45°" in chamfer
        assert {name: dimension.SystemValue * 1000.0 for name, dimension in dimensions.items()} == pytest.approx(values)
        assert captured["finish"][0] is front
        assert captured["finish"][1]["control"] is spec.SURFACE_FINISHES[0]
        assert captured["notes"][0][1] == "MHA-MG-02 SCREW SEAT"
        thread = captured["thread"]
        assert thread["entity_xy"] == pytest.approx((0.316, 0.199525))  # Actual R6 thread flank, unchanged.
        assert joint.THREAD in thread["text"] and "MATES MHA-MG-01 BRACKET" in thread["text"]
        assert "2A" not in thread["text"] and "2A" not in native_thread.note.GetText()
        assert "UNC-2A" in native_thread.model_thread.ThreadCallout
        assert native_thread.thread.ThreadCallout is native_thread.note
        # Replay the R6 18 mm dimension lane as a negative control. This checks
        # the recipe's route, not native leader elbow or glyph extents.
        length_lane = Box(0.2905, 0.2199, 0.3445, 0.2201)
        assert segment_box_overlap_length(Segment(0.350, 0.244, *thread["entity_xy"]), length_lane) > 0
        assert segment_box_overlap_length(Segment(*thread["note_xy"], *thread["entity_xy"]), length_lane) == 0
        # Both fixed extension lines must be left of every wrapped qualifier
        # row, even using a conservative 3.5 mm advance per character.
        incomplete_xy = captured["detail_keep"]["IncompleteLength"]
        rows = qualifiers["IncompleteLength"].splitlines()
        assert " ".join(rows) == "INCOMPLETE THREAD, EACH END" and len(rows) == 2
        assert incomplete_xy[0] - max(map(len, rows)) * 0.0035 / 2.0 > 0.3445
        assert captured["finalize"]["layout"] is drawing.SPEC.layout
    assert hemisphere.selection_attempts == 1
    assert front.entity_kinds == [3, 4]


def _native_thread_note_adapter(*, view=None, attachment_types=(), sheet_owned=False, fault=None):
    """Expose a drawing ICThread/INote graph, separate from native part metadata."""
    view = SimpleNamespace() if view is None else view
    state = SimpleNamespace(
        text=spec.THREAD_CALLOUT, writes=[], entities=tuple(object() for _ in attachment_types),
        entity_types=tuple(attachment_types), dangling=False,
        model_thread=SimpleNamespace(ThreadCallout=spec.THREAD_CALLOUT, thread_class="2A"),
    )
    annotation = SimpleNamespace(
        OwnerType=int(sheet_owned), Owner=object() if sheet_owned else view,
        GetAttachedEntities3=lambda: state.entities,
        GetAttachedEntityTypes=lambda: state.entity_types,
        GetAttachedEntityCount3=lambda: len(state.entities) + int(fault == "incomplete_attachments"),
        IsDangling=lambda: state.dangling,
    )

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
        elif fault == "attachment_type_changed":
            state.entity_types = tuple(46 for _ in state.entity_types)
        elif fault == "dangling":
            state.dangling = True
        elif fault == "note_replaced":
            state.thread.ThreadCallout = SimpleNamespace()
        return True

    state.note = SimpleNamespace(
        GetText=lambda: state.text, GetAnnotation=lambda: annotation, SetText=set_text,
    )
    state.thread = SimpleNamespace(ThreadCallout=state.note, GetNext=lambda: None)
    view.GetCThreadCount = lambda: 0 if fault == "no_seed" else 1
    view.GetFirstCThread = lambda: state.thread
    if fault == "no_note":
        state.thread.ThreadCallout = None
    elif fault == "unexpected_text":
        state.text = "M6 X 1-6g"
    elif fault == "part_owner":
        annotation.OwnerType = 3
    elif fault == "other_view_owner":
        annotation.Owner = object()
    adapter = SimpleNamespace(swApp=SimpleNamespace(
        IsSame=lambda first, second: 2 if fault == "identity_unsupported" else int(first is second),
    ))
    return adapter, view, state


@pytest.mark.parametrize("sheet_owned", (False, True))
@pytest.mark.parametrize("attachment_types", ((), (1,), (2,)))
def test_printed_thread_class_override_keeps_the_actual_drawing_note_and_native_metadata(monkeypatch, attachment_types, sheet_owned) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=attachment_types, sheet_owned=sheet_owned)
    original_entities, original_owner = state.entities, state.note.GetAnnotation().Owner
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    drawing._print_native_thread_callout(adapter, view)
    assert state.thread.ThreadCallout is state.note
    assert state.note.GetAnnotation().Owner is original_owner
    assert state.note.GetAnnotation().OwnerType == int(sheet_owned)
    assert state.entities == original_entities and state.entity_types == attachment_types
    assert state.writes == [state.note.GetText()]
    assert joint.THREAD in state.note.GetText() and "MATES MHA-MG-01 BRACKET" in state.note.GetText()
    assert "2A" not in state.note.GetText()
    assert state.model_thread.ThreadCallout == f"{joint.THREAD} UNC-2A\nMATES MHA-MG-01 BRACKET"
    assert state.model_thread.thread_class == "2A"


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
))
def test_thread_class_override_refuses_unsupported_or_changed_native_identity(monkeypatch, fault, message) -> None:
    adapter, view, state = _native_thread_note_adapter(attachment_types=(2,), fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match=message):
        drawing._print_native_thread_callout(adapter, view)
    assert state.model_thread.ThreadCallout.endswith("MATES MHA-MG-01 BRACKET")
    assert "UNC-2A" in state.model_thread.ThreadCallout and state.model_thread.thread_class == "2A"
