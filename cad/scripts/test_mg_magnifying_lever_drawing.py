"""Offline physical interval/fit/travel checks for the threaded MG lever."""

from __future__ import annotations

import asyncio
import itertools
import math
from types import SimpleNamespace

import pytest

import build_mg_magnifier_assembly as assembly
import draw_mg_magnifying_lever as drawing
import mg_lever_thread_joint as joint
import mg_magnifier_assembly_spec as installed
import mg_magnifying_clamp_geom as clamp
import mg_magnifying_lever_geom as geom
import mg_magnifying_lever_spec as spec
import _drawing_leader_notes as leader_notes
import _drawing_dimension_import as dimension_import
from _drawing_types import DRAWING_TEMPLATES
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
    DrawableRegion,
    segment_box_distance,
    Segment,
    SheetGeometry,
    find_border_breaches,
    find_text_on_line,
)


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
    # The callout carries words only: the MAX is native, and no derived
    # full-thread minimum prints as free text.
    assert spec.LEAD_CALLOUT == "INCOMPLETE THREAD,\nEACH END OF THREAD"


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
        assert fit == drawing.ROD_DIA_CALLOUT and "BRASS" not in fit
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
        assert rows == spec.LEAD_CALLOUT.splitlines() and len(rows) == 2
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
    assert find_text_clearance(after) == []
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
    width = 0.0868955 * max(map(len, drawing.ROD_DIA_CALLOUT.splitlines())) / 34

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
    assert find_text_clearance(after) == []
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
