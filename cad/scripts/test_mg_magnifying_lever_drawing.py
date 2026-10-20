"""Offline physical interval/fit/travel checks for the threaded MG lever."""

from __future__ import annotations

import asyncio
import itertools
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
    assert min(centres) - half >= -1e-9
    assert centres[1] == geom.CLAMP_LOCAL_X
    assert assembly.LEVER_X0 - geom.BRACKET_LOCAL_X == assembly.BRACKET_X
    assert assembly.LEVER_X0 - geom.KNIFE_LOCAL_X == assembly.KNIFE[0]


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
    def __init__(self, name, faces=()):
        self.name = name
        self.faces = faces
        self.entity_kinds = []
        self.component = object()

    def GetName2(self):
        return self.name

    def GetVisibleComponents(self):
        return (self.component,)

    def GetVisibleEntities2(self, component, kind):
        assert component is self.component
        self.entity_kinds.append(kind)
        assert kind == 3, "the free hemisphere must be resolved as a visible face"
        return self.faces


def test_free_end_matcher_identifies_the_actual_visible_sphere_not_a_cylinder_or_other_sphere() -> None:
    hemisphere = _LeverFace()
    view = _LeverVisibleView("front", (
        _LeverFace(identity=4002),
        _LeverFace(diameter_mm=joint.ROD_DIA + 1.0),
        _LeverFace(center_mm=(joint.ROD_LENGTH - joint.ROD_DIA / 2.0, 0.0, 0.0)),
        hemisphere,
    ))
    assert drawing._free_end_face(view) is hemisphere
    assert view.entity_kinds == [3]


@pytest.mark.parametrize("faces", (
    (),
    (_LeverFace(identity=4002),),
    (_LeverFace(center_mm=(0.0, 0.0, 0.0)),),
    (_LeverFace(diameter_mm=joint.ROD_DIA + 1.0),),
    (_LeverFace(), _LeverFace()),
))
def test_free_end_matcher_refuses_absent_wrong_or_ambiguous_visible_hemispheres(faces) -> None:
    with pytest.raises(RuntimeError, match="expected one visible spherical face"):
        drawing._free_end_face(_LeverVisibleView("front", faces))


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
    """Run the recipe's actual note call through real selection/attachment code."""
    hemisphere = _LeverFace()
    front = _LeverVisibleView("front", (_LeverFace(identity=4002), hemisphere))
    iso, detail = _LeverVisibleView("iso"), _LeverVisibleView("detail")
    document = _LeverNoteDocument((front, iso, detail), fault)
    hemisphere.document = document
    source = tmp_path / "lever.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)

    async def open_model(_path):
        return SimpleNamespace(is_success=True, data=None)

    async def finalize(*_args, **_kwargs):
        return {"slddrw": "lever.SLDDRW"}

    def read_member(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value

    adapter = SimpleNamespace(
        currentModel=document, open_model=open_model,
        _attempt=lambda fn, default=None: fn(), _get_attr_or_call=read_member,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    views = iter((front, iso))
    monkeypatch.setattr(drawing, "place_view", lambda *_a, **_kw: next(views))
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_a, **_kw: (document, object()))
    monkeypatch.setattr(drawing, "_detail", lambda _adapter: (detail, []))
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_a, **_kw: [])
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, _v, point, **_kw: point[:2])
    monkeypatch.setattr(drawing, "import_cosmetic_threads", lambda *_a: (1, 1))
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    for name in ("read_required_properties", "stamp_drawing_summary", "set_hidden_lines_removed", "assert_imported_precision", "set_dimension_callouts", "add_surface_finish", "_note", "_circle", "add_property_linked_note"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    monkeypatch.setattr(leader_notes, "rebuild_drawing", lambda *_a, **_kw: None)

    def attach(_adapter, view, **kwargs):
        if kwargs["text"] == spec.FREE_END_CALLOUT:
            return leader_notes.add_attached_note(_adapter, view, **kwargs)
        return None  # The already-successful thread-end note is not this regression.

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
    assert hemisphere.selection_attempts == 1
    assert front.entity_kinds == [3]
