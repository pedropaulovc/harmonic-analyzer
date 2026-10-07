"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

import _drawing_common as common
import draw_sm_summing_lever as drawing
import sm_summing_lever_spec
from _drawing_common import ViewEdge, ViewEdges, assert_dimension_measures
from _hole_spec import blind_cut_dia_mm
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
    # Each anchor's thread must span the seat it screws into.
    assert ANCHOR_9489T111.thread_length_mm > sm_summing_lever_spec.PLATE_T
    assert ANCHOR_9490T1.thread_length_mm >= sm_summing_lever_spec.ANCHOR_H
    # ...and each tap must fit the feature it passes through.
    assert blind_cut_dia_mm(boss) < 2.0 * sm_summing_lever_spec.ANCHOR_R
    assert blind_cut_dia_mm(plate) < sm_summing_lever_spec.HOLE_EDGE_OFFSET


def _line(start, end):
    return ViewEdge(object(), (start, end), None, None)


def test_end_face_edge_is_the_rib_top_edge_not_the_flange_or_underside() -> None:
    """Datum B and the start-Z BASIC hang on the +Z END face: the rib flange
    5.08 mm inboard reads 3.35 for 8.43 (#1105), and the rib's underside edge
    shares the end plane but is hidden under the plate."""
    z = sm_summing_lever_spec.PLATE_L / 2.0
    top = _line((0.0, 15.24, z), (sm_summing_lever_spec.PLATE_W, 0.0, z))
    flange = _line((0.0, 15.24, z - sm_summing_lever_spec.PLATE_T), (44.45, 0.0, z - 5.08))
    underside = _line((sm_summing_lever_spec.PLATE_W, 0.0, z), (0.0, -15.24, z))
    plate_end = _line((37.04, 2.54, z), (sm_summing_lever_spec.PLATE_W, 2.54, z))
    edges = ViewEdges(label="plan", edges=(flange, underside, plate_end, top))
    assert drawing._end_face_edge(edges, x_mm=10.0) is top
    # The plate's own end edge only shows past the rib taper: two lines there.
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(edges, x_mm=40.0)
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
    monkeypatch.setattr(common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        common._sw_type_info, "early_bound_or_flag", lambda value, *_args: value
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


def _tap_rim(
    *,
    center=None,
    radius=None,
    axis=(0.0, 1.0, 0.0),
    native_id=None,
) -> ViewEdge:
    """Geometry already read from a visible edge; wrappers may alias an edge."""
    center = center or (drawing.TIP_X, drawing.ANCHOR_H / 2.0, 0.0)
    radius = drawing.COUNTER_R if radius is None else radius
    edge = SimpleNamespace(native_id=object() if native_id is None else native_id)
    return ViewEdge(edge, None, (*center, *axis, radius), None)


def _unique_anchor_rim(items) -> ViewEdge:
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(
            IsSame=lambda first, second: int(first.native_id is second.native_id)
        )
    )
    return ViewEdges(label="summing lever top", edges=tuple(items)).circle_at(
        (drawing.TIP_X, drawing.ANCHOR_H / 2.0, 0.0),
        drawing.COUNTER_R,
        axis=(0.0, 1.0, 0.0),
        label="counter-anchor tap rim",
        selection="unique",
        adapter=adapter,
    )


def test_anchor_rim_is_the_tap_entry_not_the_exit_boss_or_other_plane() -> None:
    """The exit shares the sheet centre, but only the boss's +Y rim is the
    Hole Wizard entry the drawing asks to annotate."""
    entry = _tap_rim()
    exit_rim = _tap_rim(center=(drawing.TIP_X, -drawing.ANCHOR_H / 2.0, 0.0))
    boss = _tap_rim(radius=drawing.ANCHOR_R)
    other_plane = _tap_rim(axis=(0.0, 0.0, 1.0))
    for items in (
        (exit_rim, boss, other_plane, entry),
        (entry, other_plane, boss, exit_rim),
    ):
        assert _unique_anchor_rim(items) is entry
    with pytest.raises(RuntimeError, match="no visible circle"):
        _unique_anchor_rim((exit_rim, boss, other_plane))
    with pytest.raises(RuntimeError, match="no circular edge"):
        _unique_anchor_rim(())


def test_anchor_rim_refuses_distinct_coincident_edges_in_either_order() -> None:
    """Equal geometry is not native identity: an enumeration-order tie must
    never choose which edge owns an associative hole callout."""
    first, second = _tap_rim(), _tap_rim()
    for items in ((first, second), (second, first)):
        with pytest.raises(RuntimeError, match="2 distinct native edges"):
            _unique_anchor_rim(items)
    # Existing dimension consumers retain their explicit nearest contract.
    edges = ViewEdges(label="plan", edges=(second, first))
    assert edges.circle_at(
        (drawing.TIP_X, drawing.ANCHOR_H / 2.0, 0.0),
        drawing.COUNTER_R,
        axis=(0.0, 1.0, 0.0),
        label="legacy nearest rim",
    ) is second


def test_repeated_native_edge_wrappers_are_one_anchor_candidate() -> None:
    native_id = object()
    first, alias = _tap_rim(native_id=native_id), _tap_rim(native_id=native_id)
    assert first.edge is not alias.edge
    assert _unique_anchor_rim((first, alias, first)) is first


class _PersistenceReached(Exception):
    """Stop at an offline persistence tripwire, never at a native SaveAs."""


@pytest.fixture
def callout_scene(monkeypatch, tmp_path):
    """Bound the COM surface without replacing the callout or finalizer guards.

    The visible geometry is predetermined, but ViewEdges still chooses the
    unique anchor and all the named dimension entities. The real selection
    helper, native callout helper, attachment guards, view traversal and
    finalizer run against these fakes; no host drawing or PDF can be written.
    """
    source = tmp_path / "sm-summing-lever.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    scene = SimpleNamespace(
        settled=False,
        fault=None,
        target="anchor",
        insertion_fault=None,
        selected=None,
        selected_view=None,
        callouts={},
        originals={},
        views=[],
        enumerations=[],
        annotation_reads=[],
        attachment_reads=[],
        comparisons=[],
        indeterminate=set(),
        events=[],
        boundaries=[],
        rebuilds=[],
        registered_leaders=0,
    )

    class Edge:
        def __init__(self, name, circle=None, native_id=None):
            self.name = name
            self.circle = circle
            self.native_id = ("edge", name) if native_id is None else native_id

        def Select4(self, _append, data):
            scene.selected = self
            scene.selected_view = data.View
            return True

        def GetCurve(self):
            if self.circle is None:
                return None
            x, y, z, nx, ny, nz, radius = self.circle
            return SimpleNamespace(
                IsCircle=lambda: True,
                IsLine=lambda: False,
                CircleParams=(x / 1000, y / 1000, z / 1000, nx, ny, nz, radius / 1000),
            )

        def GetTwoAdjacentFaces2(self):
            return ()

    class Display:
        def __init__(self, native_id, *, hole=True):
            self.native_id = native_id
            self.hole = hole
            self.annotation = None
            # Native RD3 readback: stub, sloped run, horizontal shoulder.
            self.lines = [
                (0, 0, 0, 0, 0.0693, 0.20429, 0, 0.0707, 0.20571, 0),
                (0, 0, 0, 0, 0.0707, 0.20571, 0, 0.08389, 0.2192, 0),
                (0, 0, 0, 0, 0.08389, 0.2192, 0, 0.12252, 0.2192, 0),
            ]
            self.display_data = True
            # Tip Z deliberately differs from line Z; the native joint is XY.
            self.arrows = [
                (0.0707, 0.20571, -0.0015875, 0.7, 0.7, 0,
                 0.003556, 0.000762, 0, 0, 0, -1),
            ]

        def IsHoleCallout(self):
            return self.hole

        def GetAnnotation(self):
            return self.annotation

        def GetDisplayData(self):
            if not self.display_data:
                return None
            return SimpleNamespace(
                GetLineCount=lambda: len(self.lines),
                GetLineAtIndex2=lambda index: self.lines[index],
                GetArrowHeadCount=lambda: len(self.arrows),
                GetArrowHeadAtIndex2=lambda index: self.arrows[index],
            )

    class Annotation:
        def __init__(self, display, edge, native_id):
            self.native_id = native_id
            self.display = display
            self.Visible = 1  # swAnnotationVisible
            self.kind = 4  # swDisplayDimension
            self.entities = (edge,)
            self.count = 1
            self.types = (1,)  # swSelEDGES
            self.leaders = scene.registered_leaders
            self.dangling = False
            self.position = (0.0, 0.0, 0.0)

        def GetType(self):
            return self.kind

        def GetSpecificAnnotation(self):
            return self.display

        def SetPosition2(self, x, y, z):
            self.position = (x, y, z)
            return True

        def GetPosition(self):
            return self.position

        def GetAttachedEntities3(self):
            scene.attachment_reads.append((self, scene.settled))
            return self.entities

        def GetAttachedEntityCount3(self):
            return self.count

        def GetAttachedEntityTypes(self):
            return self.types

        def GetLeaderCount(self):
            return self.leaders

        def IsDangling(self):
            return self.dangling

    model = SimpleNamespace(GetPathName=lambda: str(source))

    class View:
        def __init__(self, orientation, native_id=None):
            self.orientation = orientation
            self.native_id = (
                ("view", orientation) if native_id is None else native_id
            )
            self.annotations = []
            self.next_view = None
            self.ReferencedDocument = model
            self.ScaleDecimal = 0.5
            self.Position = drawing.TOP_CENTER
            self.ModelToViewTransform = SimpleNamespace(
                ArrayData=(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0.5, 0, 0, 0)
            )

        def GetName2(self):
            return self.orientation

        def GetOrientationName(self):
            return self.orientation

        def GetNextView(self):
            return self.next_view

        def GetAnnotations(self):
            scene.annotation_reads.append((self, scene.settled))
            return self.annotations

        def GetOutline(self):
            return (0.1, 0.1, 0.3, 0.2)

        def UpdateViewDisplayGeometry(self):
            pass

    front, top, iso = (View(name) for name in ("*Front", "*Top", "*Isometric"))
    scene.original_views = (front, top, iso)
    scene.views[:] = scene.original_views
    sheet_view = SimpleNamespace(GetNextView=lambda: scene.views[0] if scene.views else None)

    def link_views():
        for index, view in enumerate(scene.views):
            view.next_view = (
                scene.views[index + 1] if index + 1 < len(scene.views) else None
            )

    def first_view():
        scene.enumerations.append(scene.settled)
        link_views()
        return sheet_view

    def clear_selection(_all):
        scene.selected = None
        scene.selected_view = None

    def coordinate_pick(*_args):
        scene.selected = scene.rims["anchor"].edge
        scene.selected_view = top
        return True

    selection = SimpleNamespace(
        CreateSelectData=lambda: SimpleNamespace(View=None),
        GetSelectedObjectCount2=lambda _mark: int(scene.selected is not None),
        GetSelectedObject6=lambda _index, _mark: scene.selected,
        GetSelectedObjectType3=lambda _index, _mark: 1,
        GetSelectionPoint2=lambda _index, _mark: (0.0, 0.0, 0.0),
        GetSelectedObjectsDrawingView2=lambda _index, _mark: scene.selected_view,
    )

    def add_callout(x, y, z):
        name = scene.selected.name
        edge = scene.selected
        if scene.insertion_fault == "returned_wrong_edge" and name == scene.target:
            edge = scene.rims["middle" if name == "anchor" else "anchor"].edge
        display = Display(("display", name))
        annotation = Annotation(display, edge, ("annotation", name))
        annotation.position = (x, y, z)
        display.annotation = annotation
        scene.callouts[name] = display
        scene.originals[name] = annotation
        scene.selected_view.annotations.append(annotation)
        scene.pending = name
        return display

    sheet = SimpleNamespace(
        GetProperties2=lambda: (0, 0, 1, 2, False, 0.4318, 0.2794, False),
        SetScale=lambda *_args: True,
        GetViews=lambda: tuple(scene.views),
    )
    draw = SimpleNamespace(
        ActivateView=lambda _name: True,
        ClearSelection2=clear_selection,
        SelectionManager=selection,
        Extension=SimpleNamespace(SelectByID2=coordinate_pick),
        AddHoleCallout2=add_callout,
        GetFirstView=first_view,
        GetSheetNames=lambda: ("Sheet1",),
        ActivateSheet=lambda _name: True,
        GetCurrentSheet=lambda: sheet,
        Sheet=lambda _name: sheet,
    )

    def is_same(first, second):
        result = (
            -1
            if first.native_id in scene.indeterminate or second.native_id in scene.indeterminate
            else int(first.native_id == second.native_id)
        )
        scene.comparisons.append((first, second, result, scene.settled))
        return result

    class Adapter:
        currentModel = draw
        swApp = SimpleNamespace(IsSame=is_same, RunCommand=lambda *_args: True)

        async def open_model(self, _path):
            self.currentModel = model
            return AdapterResult(status=AdapterResultStatus.SUCCESS, data=model)

        def _attempt(self, operation, **_kwargs):
            return operation()

        def _get_attr_or_call(self, obj, name):
            value = getattr(obj, name)
            return value() if callable(value) else value

    scene.adapter = Adapter()
    scene.top = top

    def circle(name, center, radius, axis=(0.0, 1.0, 0.0)):
        edge = Edge(name, (*center, *axis, radius))
        return ViewEdge(edge, None, edge.circle, None)

    def line(name, start, end):
        return ViewEdge(Edge(name), (start, end), None, None)

    anchor = circle("anchor", (drawing.TIP_X, drawing.ANCHOR_H / 2, 0), drawing.COUNTER_R)
    middle_z = drawing.HOLE_Z_LAST - (drawing.HOLE_COUNT // 2) * drawing.CHANNEL_PITCH
    scene.rims = {
        "anchor": anchor,
        "middle": circle(
            "middle", (drawing.HOLE_X, drawing.PLATE_T / 2, middle_z), drawing.HOLE_DIA / 2
        ),
    }
    anchor_alias = ViewEdge(
        Edge("anchor", anchor.circle, anchor.edge.native_id), None, anchor.circle, None
    )
    z = drawing.PLATE_L / 2
    geometry = ViewEdges(
        label="summing lever top plan",
        edges=(
            circle("exit", (drawing.TIP_X, -drawing.ANCHOR_H / 2, 0), drawing.COUNTER_R),
            circle("boss", (drawing.TIP_X, drawing.ANCHOR_H / 2, 0), drawing.ANCHOR_R),
            circle(
                "other-plane", (drawing.TIP_X, drawing.ANCHOR_H / 2, 0),
                drawing.COUNTER_R, (0.0, 0.0, 1.0),
            ),
            anchor,
            anchor_alias,
            line("negative-ridge", (0, drawing.HEX_H / 2, -z - drawing.HEX_DEPTH),
                 (0, drawing.HEX_H / 2, -z)),
            line("positive-ridge", (0, drawing.HEX_H / 2, z),
                 (0, drawing.HEX_H / 2, z + drawing.HEX_DEPTH)),
            line("end", (0, 15.24, z), (drawing.PLATE_W, 0, z)),
            circle("seed", (drawing.HOLE_X, drawing.PLATE_T / 2, drawing.HOLE_Z_LAST),
                   drawing.HOLE_DIA / 2),
            circle(
                "second",
                (drawing.HOLE_X, drawing.PLATE_T / 2, drawing.HOLE_Z_LAST - drawing.CHANNEL_PITCH),
                drawing.HOLE_DIA / 2,
            ),
            scene.rims["middle"],
        ),
    )

    def fresh_annotation(name):
        original = scene.originals[name]
        display = Display(scene.callouts[name].native_id)
        selected = scene.rims[name].edge
        edge = Edge(name, selected.circle, selected.native_id)
        annotation = Annotation(display, edge, original.native_id)
        annotation.position = original.position
        display.annotation = annotation
        return annotation

    def settle(_adapter, *, label):
        scene.rebuilds.append(label)
        if label == "add_native_hole_callout":
            if scene.pending != scene.target:
                return
            display = scene.callouts[scene.pending]
            if scene.insertion_fault == "rebuilt_wrong_edge":
                # The pre-rebuild annotation remains healthy and readable.
                original = display.annotation
                current = fresh_annotation(scene.pending)
                other = "middle" if scene.pending == "anchor" else "anchor"
                current.entities = (scene.rims[other].edge,)
                display.annotation = current
                top.annotations[top.annotations.index(original)] = current
            elif scene.insertion_fault == "missing_annotation":
                display.annotation = None
            elif scene.insertion_fault == "no_rendered_leader":
                display.lines = []
            elif scene.insertion_fault == "no_rendered_arrow":
                display.arrows = []
            return
        if label != "finalize_drawing":
            return
        scene.settled = True
        # A rebuild returns fresh wrappers, NOT updated cached handles.
        scene.views[:] = [View(view.orientation, view.native_id) for view in scene.original_views]
        current_top = scene.views[1]
        live = {name: fresh_annotation(name) for name in scene.callouts}
        # Unrelated notes, ordinary dimensions and null specific annotations
        # must not be mistaken for either named live native hole callout.
        note = Annotation(None, anchor.edge, ("annotation", "note"))
        note.kind = 6  # swNote
        ordinary = Annotation(Display(("display", "ordinary"), hole=False),
                              anchor.edge, ("annotation", "ordinary"))
        current_top.annotations = [note, ordinary, *live.values()]
        scene.live = live
        current = live[scene.target]
        other = "middle" if scene.target == "anchor" else "anchor"
        fault = scene.fault
        if fault == "wrong_edge":
            current.entities = (live[other].entities[0],)
        elif fault == "coincident_rim":
            current.entities = (Edge("coincident", current.entities[0].circle),)
        elif fault == "removed":
            current_top.annotations.remove(current)
        elif fault == "dangling":
            current.dangling = True
        elif fault == "missing_attachments":
            current.entities, current.count, current.types = (), 0, ()
        elif fault == "null_attachment_array":
            current.entities = None
        elif fault == "extra_attachments":
            current.entities += (live[other].entities[0],)
            current.count, current.types = 2, (1, 1)
        elif fault == "null_attachment":
            current.entities = (None,)
        elif fault == "wrong_type":
            current.types = (2,)  # swSelFACES
        elif fault == "missing_types":
            current.types = ()
        elif fault == "extra_types":
            current.types = (1, 1)
        elif fault == "zero_count":
            current.count = 0
        elif fault == "extra_count":
            current.count = 2
        elif fault == "no_leader":
            current.display.lines = []
        elif fault == "unreadable_leader":
            current.display.display_data = False
        elif fault == "malformed_leader":
            current.display.lines = [(0, 0)]
        elif fault == "nonfinite_leader":
            current.display.lines = [(0, 0, 0, 0, float("nan"), 0, 0, 1, 1, 0)]
        elif fault == "degenerate_leader":
            current.display.lines = [(0, 0, 0, 0, 0.1, 0.2, 0, 0.1, 0.2, 0)]
        elif fault == "hidden_callout":
            current.Visible = 3  # swAnnotationHidden
        elif fault == "half_hidden_callout":
            current.Visible = 2  # swAnnotationHalfHidden
        elif fault == "unknown_visibility":
            current.Visible = 0  # swAnnotationVisibilityUnknown
        elif fault == "partial_leader":
            current.display.lines.append((0, 0))
        elif fault == "no_arrow":
            current.display.arrows = []
        elif fault == "extra_arrow":
            current.display.arrows *= 2
        elif fault == "hidden_arrow":
            arrow = list(current.display.arrows[0])
            arrow[8] = 10  # swNO_ARROWHEAD
            current.display.arrows = [arrow]
        elif fault == "unreadable_arrow":
            current.display.arrows = [(0, 0)]
        elif fault == "nonfinite_arrow":
            arrow = list(current.display.arrows[0])
            arrow[0] = float("nan")
            current.display.arrows = [arrow]
        elif fault == "disconnected_arrow":
            arrow = list(current.display.arrows[0])
            arrow[0] += 0.050
            current.display.arrows = [arrow]
        elif fault == "zero_size_arrow":
            arrow = list(current.display.arrows[0])
            arrow[6] = 0
            current.display.arrows = [arrow]
        elif fault == "zero_direction_arrow":
            arrow = list(current.display.arrows[0])
            arrow[3:6] = [0, 0, 0]
            current.display.arrows = [arrow]
        elif fault == "wrong_annotation_owner":
            current.display.annotation = live[other]
        elif fault == "missing_annotation_owner":
            current.display.annotation = None
        elif fault == "wrong_view":
            current_top.annotations.remove(current)
            scene.views[0].annotations.append(current)
        elif fault == "missing_view":
            scene.views.pop(1)
        elif fault == "replaced_view":
            current_top.native_id = ("view", "replacement")
        elif fault == "missing_display":
            current.display = None
        elif fault == "replaced_display":
            current.display = Display(("display", "replacement"))
            current.display.annotation = current
        elif fault == "wrong_annotation_type":
            current.kind = 6
        elif fault == "not_hole_callout":
            current.display.hole = False
        elif fault == "duplicate_display":
            current_top.annotations.append(fresh_annotation(scene.target))
        elif fault == "duplicate_view":
            scene.views.append(View(current_top.orientation, current_top.native_id))
        elif fault == "indeterminate_edge":
            scene.indeterminate.add(current.entities[0].native_id)
        elif fault == "indeterminate_display":
            scene.indeterminate.add(current.display.native_id)
        elif fault == "indeterminate_view":
            scene.indeterminate.add(current_top.native_id)
        elif fault is not None:
            raise AssertionError(f"unknown callout fault: {fault}")

    def new_sheet(*_args, **_kwargs):
        scene.adapter.currentModel = draw
        return draw, sheet

    def edge_dimension(_adapter, _view, *, label, entities, **_kwargs):
        values = {
            "anchor tap X location": -drawing.TIP_X,
            "spring-hole row X": drawing.HOLE_X,
            "spring-hole start Z": drawing.HOLE_END_OFFSET_LAST,
            "spring-hole pitch": drawing.CHANNEL_PITCH,
        }
        return _dimension(values[label], entities)

    def tripwire(boundary):
        def reached(*_args, **_kwargs):
            scene.boundaries.append(boundary)
            raise _PersistenceReached(boundary)
        return reached

    monkeypatch.setattr(drawing, "new_project_drawing", new_sheet)
    monkeypatch.setattr(drawing, "place_view",
                        lambda _adapter, _source, name, *_args, **_kwargs:
                        next(view for view in scene.original_views if view.orientation == name))
    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_args, **_kwargs: geometry)
    monkeypatch.setattr(drawing, "add_edge_dimension", edge_dimension)
    for name in (
        "stamp_drawing_summary", "set_hidden_lines_removed", "curate_view_dimensions",
        "add_datum_feature", "add_surface_finish", "add_feature_control_frame",
        "set_basic_dimension", "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, lambda *_args, **_kwargs: None)
    for module in (drawing, common):
        monkeypatch.setattr(module, "read_required_properties", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(common._sw_type_info, "early_bound", lambda value, _kind: value)
    monkeypatch.setattr(common._sw_type_info, "early_bound_or_flag",
                        lambda value, *_args: value)
    monkeypatch.setattr(common, "null_callout", lambda: None)
    monkeypatch.setattr(common, "apply_custom_properties", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(common, "assert_asme_b_sheet", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(common, "set_high_quality_shaded_with_edges",
                        lambda *_args, **_kwargs: None)
    monkeypatch.setattr(common, "remove_notes_matching", lambda *_args: 3)
    monkeypatch.setattr(common, "rebuild_drawing", settle)
    monkeypatch.setattr(common._telemetry, "event",
                        lambda name, **fields: scene.events.append((name, fields)))
    monkeypatch.setattr(common, "save_drawing", tripwire("save"))
    monkeypatch.setattr(common, "sanitize_pdf_metadata", tripwire("pdf"))
    monkeypatch.setattr(common, "render_pdf_png", tripwire("render"))
    return scene


@pytest.mark.parametrize("target", ["anchor", "middle"])
@pytest.mark.parametrize(
    "fault",
    [
        "wrong_edge", "coincident_rim", "removed", "dangling",
        "missing_attachments", "null_attachment_array", "extra_attachments",
        "null_attachment", "wrong_type", "missing_types", "extra_types",
        "zero_count", "extra_count", "no_leader", "unreadable_leader",
        "malformed_leader", "nonfinite_leader", "degenerate_leader",
        "partial_leader", "no_arrow", "extra_arrow", "hidden_arrow",
        "unreadable_arrow", "nonfinite_arrow", "disconnected_arrow",
        "zero_size_arrow", "zero_direction_arrow",
        "hidden_callout", "half_hidden_callout", "unknown_visibility",
        "wrong_annotation_owner", "missing_annotation_owner",
        "wrong_view", "missing_view", "replaced_view",
        "missing_display", "replaced_display", "wrong_annotation_type",
        "not_hole_callout", "duplicate_display", "duplicate_view",
        "indeterminate_edge", "indeterminate_display", "indeterminate_view",
    ],
)
def test_final_settling_refuses_current_callout_damage_before_persistence(
    callout_scene, target, fault
):
    """Only the final rebuild damages ownership or the live attachment.

    Old view/display/annotation handles still read as valid. A consumer that
    skips settled_checks, or a guard that trusts those handles, reaches save.
    """
    scene = callout_scene
    scene.target, scene.fault = target, fault
    with pytest.raises(RuntimeError, match="native hole callout"):
        asyncio.run(drawing.build(scene.adapter))
    assert scene.boundaries == []
    assert scene.settled
    assert set(scene.callouts) == {"anchor", "middle"}
    assert scene.rebuilds[-1] == "finalize_drawing"
    assert True in scene.enumerations  # real iter_views ran after the rebuild
    if fault not in {"missing_view", "replaced_view", "duplicate_view", "indeterminate_view"}:
        assert any(view is scene.views[1] and settled
                   for view, settled in scene.annotation_reads)
    original = scene.originals[target]
    assert scene.callouts[target].IsHoleCallout()
    assert scene.callouts[target].GetAnnotation() is original
    assert original.GetAttachedEntities3() == (scene.rims[target].edge,)
    assert original.GetAttachedEntityCount3() == 1
    assert original.GetLeaderCount() == 0
    assert not original.IsDangling()
    assert original in scene.top.GetAnnotations()


@pytest.mark.parametrize("registered_leaders", [0, 1, 2])
def test_final_settling_accepts_fresh_native_aliases_before_save(
    callout_scene, registered_leaders
):
    """Fresh edge, annotation, dimension and view wrappers retain native IDs."""
    scene = callout_scene
    scene.registered_leaders = registered_leaders
    with pytest.raises(_PersistenceReached, match="save"):
        asyncio.run(drawing.build(scene.adapter))
    assert scene.boundaries == ["save"]
    assert scene.settled
    assert True in scene.enumerations
    assert any(view is scene.views[1] and settled
               for view, settled in scene.annotation_reads)
    for name in ("anchor", "middle"):
        original, current = scene.originals[name], scene.live[name]
        assert current is not original
        assert current.native_id == original.native_id
        assert current.display is not scene.callouts[name]
        assert current.display.native_id == scene.callouts[name].native_id
        assert current.entities[0] is not scene.rims[name].edge
        assert current.entities[0].native_id == scene.rims[name].edge.native_id
        assert any(annotation is current and settled
                   for annotation, settled in scene.attachment_reads)
    assert scene.views[1] is not scene.top
    assert scene.views[1].native_id == scene.top.native_id
    for kind in ("edge", "display", "view"):
        assert any(first is not second and first.native_id[0] == kind and result == 1 and settled
                   for first, second, result, settled in scene.comparisons)


@pytest.mark.parametrize("target", ["anchor", "middle"])
@pytest.mark.parametrize(
    "fault", [
        "returned_wrong_edge", "rebuilt_wrong_edge", "missing_annotation",
        "no_rendered_leader", "no_rendered_arrow",
    ]
)
def test_insertion_refuses_wrong_native_attachment_not_just_diagnostics(
    callout_scene, target, fault
):
    scene = callout_scene
    scene.target, scene.insertion_fault = target, fault
    label = "anchor tap" if target == "anchor" else "spring-hole middle"
    with pytest.raises(RuntimeError, match=rf"native hole callout.*{label}"):
        asyncio.run(drawing.build(scene.adapter))
    assert scene.boundaries == []
    assert not scene.settled  # insertion must fail before finalization
    if fault in {"returned_wrong_edge", "rebuilt_wrong_edge"}:
        reports = [
            fields for name, fields in scene.events
            if name == "drawing.hole_callout_attachment" and fields["label"] == label
        ]
        assert len(reports) == 1
        assert json.loads(reports[0]["attached_same_requested_edge"]) == [False]
    if fault == "rebuilt_wrong_edge":
        # The old annotation is still valid, so only the fresh read can refuse.
        assert scene.originals[target].GetAttachedEntities3() == (scene.rims[target].edge,)
        assert scene.callouts[target].GetAnnotation() is not scene.originals[target]


def test_coordinate_only_callout_keeps_legacy_wrong_edge_compatibility(callout_scene):
    """Only explicitly named edges acquire the new strict identity contract."""
    scene = callout_scene
    scene.insertion_fault = "returned_wrong_edge"
    display = common.add_native_hole_callout(
        scene.adapter,
        scene.top,
        edge_xy=(0.145, 0.130),
        callout_xy=(0.145, 0.155),
        label="coordinate-only compatibility",
    )
    assert display.IsHoleCallout()
    assert display.GetAnnotation().GetAttachedEntities3() == (scene.rims["middle"].edge,)
    assert scene.boundaries == []
    assert not scene.settled
