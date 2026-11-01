"""Pure geometry regressions for supplier-state annotation room, without COM."""

from __future__ import annotations

import asyncio
from copy import copy
from dataclasses import replace
import hashlib
from itertools import combinations
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_projection
import _purchased_fastener_drawing as purchased
import _supplier_chain_dimensions as chain_dimensions
import _supplier_spring_drawing as supplier_drawing
from _supplier_reference_geometry import NativeSketchGeometry
from _supplier_spring_drawing import supplier_state_cells
import ch_vn_channel_spring_installed_spec as channel_installed
import ch_vn_channel_spring_stock_geom as channel
import sm_vn_counter_spring_spec as counter_installed


# Representative annotation requirements, independent of the layout coordinates.
_EXTENSION_MARGINS = {
    "free_front": (0.0, 0.0, 0.0, 0.018),
    "free_right": (0.0, 0.018, 0.045, 0.018),
    "max_front": (0.0, 0.0, 0.0, 0.018),
}
_DIAGRAM_MARGINS = {
    "free_front": (0.035, 0.0, 0.035, 0.0),
    "free_top": (0.040, 0.0, 0.040, 0.0),
    "free_right": (0.035, 0.0, 0.035, 0.0),
}


def _annotation_envelope(bounds, margins):
    left, bottom, right, top = margins
    return (
        bounds[0] - left,
        bounds[1] - bottom,
        bounds[2] + right,
        bounds[3] + top,
    )


def _contains(outer, inner):
    return (
        outer[0] <= inner[0] < inner[2] <= outer[2]
        and outer[1] <= inner[1] < inner[3] <= outer[3]
    )


@pytest.mark.parametrize(
    "maximum,margins",
    [
        pytest.param(True, _EXTENSION_MARGINS, id="extension-free-and-maximum"),
        pytest.param(False, _DIAGRAM_MARGINS, id="nominal-diagrams"),
    ],
)
@pytest.mark.parametrize(
    "notes", ["", "FIRST\nSECOND\nTHIRD"], ids=["bare-footer", "full-footer"]
)
def test_state_cells_leave_positive_geometry_and_all_annotation_budgets(
    maximum, margins, notes
):
    caption_y = purchased.view_band_bottom(notes, label="supplier layout")
    cells = supplier_state_cells(caption_y, maximum=maximum)
    fitted = purchased.supplier_fit_cells(cells, margins, label="supplier layout")
    originals = {name: (center, bounds) for name, center, bounds in cells}
    expected_names = {"free_front", "free_right", "installed_iso"}
    expected_names.add("max_front" if maximum else "free_top")
    assert {name for name, _, _ in fitted} == set(originals) == expected_names

    for name, center, inner in fitted:
        outer_center, outer = originals[name]
        assert _contains(outer, inner), name
        assert center == pytest.approx(
            ((inner[0] + inner[2]) / 2.0, (inner[1] + inner[3]) / 2.0)
        ), name
        if name not in margins:
            # Every installed pictorial keeps its whole cell; unused views
            # must not pay another view's annotation budget.
            assert inner == outer, name
            assert center == outer_center, name
            continue

        left, bottom, right, top = margins[name]
        available = (
            inner[0] - outer[0],
            inner[1] - outer[1],
            outer[2] - inner[2],
            outer[3] - inner[3],
        )
        assert available == pytest.approx(margins[name]), name
        assert _annotation_envelope(inner, margins[name]) == pytest.approx(outer), name
        assert center == pytest.approx(
            (
                outer_center[0] + (left - right) / 2.0,
                outer_center[1] + (bottom - top) / 2.0,
            )
        ), name

    # Insets cannot hide overlapping outer view/caption plans. In particular,
    # the maximum-state Right and installed Iso need separate sheet regions.
    for (name_a, _, a), (name_b, _, b) in combinations(cells, 2):
        assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (
            name_a,
            name_b,
        )


@pytest.mark.parametrize(
    "spec,scale",
    [
        pytest.param(counter_installed, (1, 2), id="1330K524-1:2"),
        pytest.param(channel_installed, (2, 1), id="9432K31-2:1"),
    ],
)
def test_extension_installed_cell_holds_the_pictorial_at_a_legible_scale(
    spec, scale
):
    # At 1:8 the counter spring's turns merged into a solid bar. A box around
    # the installed coil (axis +X, loops/hooks inside the OD) bounds its
    # standard isometric: X projects (sqrt(1/2), -1/sqrt(6)), Y (0, sqrt(2/3)).
    caption_y = purchased.view_band_bottom("", label="installed scale")
    cell = next(
        bounds
        for name, _, bounds in supplier_state_cells(caption_y, maximum=True)
        if name == "installed_iso"
    )
    diameter = spec.SUPPLIER_COIL_OD_MM
    run = spec.INSTALLED_LENGTH_MM + 2.0 * spec.SUPPLIER_WIRE_DIA_MM + diameter
    ratio = scale[0] / scale[1] / 1000.0
    width = math.sqrt(0.5) * run * ratio
    height = (run / math.sqrt(6.0) + math.sqrt(2.0 / 3.0) * diameter) * ratio
    assert width <= cell[2] - cell[0]
    assert height <= cell[3] - cell[1]


@pytest.mark.parametrize(
    "maximum,legacy_width,margins",
    [
        pytest.param(True, 0.032, _EXTENSION_MARGINS, id="old-32mm-extension-right"),
        pytest.param(False, 0.042, _DIAGRAM_MARGINS, id="old-42mm-diagram-right"),
    ],
)
def test_old_right_widths_cannot_reserve_the_requested_annotation_room(
    maximum, legacy_width, margins
):
    caption_y = purchased.view_band_bottom("", label="legacy supplier layout")
    cells = supplier_state_cells(caption_y, maximum=maximum)
    old_cells = []
    for name, center, bounds in cells:
        if name == "free_right":
            # Change only the historical insufficient width, not a copied
            # coordinate table: 45 mm cannot fit in 32 mm, nor 35+35 in 42 mm.
            x0, y0, _, y1 = bounds
            bounds = (x0, y0, x0 + legacy_width, y1)
            center = ((bounds[0] + bounds[2]) / 2.0, (y0 + y1) / 2.0)
        old_cells.append((name, center, bounds))

    right_budget = margins["free_right"]
    assert right_budget[0] + right_budget[2] > legacy_width
    with pytest.raises(
        ValueError, match="free_right: supplier margins leave no geometry space"
    ):
        purchased.supplier_fit_cells(
            tuple(old_cells), margins, label="legacy supplier layout"
        )


class _CoilEndView:
    """A real coil's circular end span plus fixed synthetic native padding.

    The outline is calculated from the supplier model diameter and candidate
    scale, never from a target cell or a remembered outline. A 1 mm per-edge
    sheet-space pad stays fixed while the model scales, as in nearby fit tests.
    """

    PADDING_M = 0.001

    def __init__(self, center):
        self.Position = center
        self.ScaleRatio = (1.0, 1.0)
        self.UseSheetScale = 1

    def UpdateViewDisplayGeometry(self):
        return None  # Native VT_VOID; the fake outline already uses current scale.

    def GetOutline(self):
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        radius = channel.COIL_OD_MM / 2000.0 * ratio + self.PADDING_M
        x, y = self.Position
        return (x - radius, y - radius, x + radius, y + radius)

    def SetViewPosition(self, position, _update):
        self.Position = tuple(position)
        return True


def test_largest_scale_is_chosen_with_annotation_room_not_the_bare_outer_cell(
    monkeypatch,
):
    monkeypatch.setattr(purchased, "double_array", tuple)
    caption_y = purchased.view_band_bottom("", label="extension scale")
    cells = supplier_state_cells(caption_y, maximum=True)
    fitted = purchased.supplier_fit_cells(
        cells, _EXTENSION_MARGINS, label="extension scale"
    )
    outer_cell = next(cell for cell in cells if cell[0] == "free_right")
    inner_cell = next(cell for cell in fitted if cell[0] == "free_right")
    draw = SimpleNamespace(EditRebuild3=lambda: True)
    bare_view = _CoilEndView(outer_cell[1])
    annotated_view = _CoilEndView(outer_cell[1])

    bare_scale = purchased._fit_group(draw, [(bare_view, outer_cell)])
    annotated_scale = purchased._fit_group(draw, [(annotated_view, inner_cell)])
    ratio = annotated_scale[0] / annotated_scale[1]
    assert bare_scale[0] / bare_scale[1] > ratio

    # Prove maximality from model geometry and fixed padding independently of
    # the fake's GetOutline and the fitter's position/scale readback checks.
    inner = inner_cell[2]
    available_span = min(inner[2] - inner[0], inner[3] - inner[1])
    fitting_ratios = [
        numerator / denominator
        for numerator, denominator in purchased._SCALES
        if channel.COIL_OD_MM / 1000.0 * numerator / denominator
        + 2.0 * _CoilEndView.PADDING_M
        <= available_span
    ]
    assert ratio == max(fitting_ratios)
    assert _contains(inner, annotated_view.GetOutline())
    margins = _EXTENSION_MARGINS["free_right"]
    assert _contains(
        outer_cell[2], _annotation_envelope(annotated_view.GetOutline(), margins)
    )
    assert not _contains(
        outer_cell[2], _annotation_envelope(bare_view.GetOutline(), margins)
    )


class _ReferenceFeature:
    def __init__(self, name, sketch, kind="ProfileFeature"):
        self.Name = name
        self.sketch = sketch
        self.kind = kind
        self.Visible = 1  # Saved MODEL-hidden, independent of the drawing override.
        self.suppressed = False
        self.error_state = (0, False)
        self.native_identity = object()

    def GetTypeName2(self):
        return self.kind

    def GetSpecificFeature2(self):
        return self.sketch

    def GetErrorCode2(self):
        return self.error_state

    def IsSuppressed2(self, configuration_option, _configuration_names):
        assert configuration_option == 1
        return (self.suppressed,)


class _ReferenceModel:
    """All document operations are in-memory; no adapter/COM connection exists."""

    def __init__(self, features):
        self.features = features
        self.path = Path("supplier-test-part.SLDPRT").resolve()
        self.native_identity = object()
        self.active = "Installed"
        self.dirty = False
        self.read_only = True
        self.events = []
        self.configurations = ("Installed", "SupplierReference", "MaximumReference")
        self.Extension = SimpleNamespace(NeedsRebuild2=0)
        self.rebuild_on_switch = 0
        self.bodies = {
            "Installed": {0: (object(),), 1: ()},
            "SupplierReference": {0: (), 1: ()},
            "MaximumReference": {0: (), 1: ()},
        }

    @property
    def ConfigurationManager(self):
        return SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name=self.active))

    def GetPathName(self):
        return str(self.path)

    def GetTitle(self):
        return self.path.name

    def GetConfigurationNames(self):
        return self.configurations

    def GetSaveFlag(self):
        return self.dirty

    def IsOpenedReadOnly(self):
        return self.read_only

    def ShowConfiguration2(self, name):
        self.events.append(("switch", name))
        self.active = name
        self.Extension.NeedsRebuild2 = self.rebuild_on_switch
        return True

    def EditRebuild3(self):
        self.events.append(("rebuild", self.active))
        self.Extension.NeedsRebuild2 = 0
        return True

    def GetBodies2(self, kind, visible_only):
        assert kind in (0, 1) and visible_only is False
        return self.bodies[self.active][kind]


def _source_sketch(points, model):
    segments = tuple(object() for _ in range(len(points) - 1))
    return SimpleNamespace(
        points=tuple(points),
        model=model,
        capture_count=0,
        GetSketchSegments=lambda: segments,
    )


class _ReferenceInkView:
    OUTLINE_FLOOR_M = 0.011176  # a27 observed sheet-space outline floor.

    def __init__(self, points, *, outline="padded", name="reference"):
        self.Name = name
        self.native_identity = object()
        self.ReferencedDocument = _ReferenceModel([])
        self.source = _source_sketch(points, self.ReferencedDocument)
        self.owner = _ReferenceFeature("SupplierSection", self.source)
        self.ReferencedDocument.features.append(self.owner)
        self.referenced_path = self.ReferencedDocument.path
        self.ReferencedConfiguration = "SupplierReference"
        self.Position = (0.07, 0.13)
        self.ScaleRatio = (1.0, 1.0)
        self.UseSheetScale = 1
        self.outline = outline
        self.outline_calls = 0
        self.position_writes = []
        self.refreshes = []
        self.correspondence_reads = []
        self._transform = None
        self.drawing_segments = []
        self.drawing_blocks = self.drawing_user_points = 0
        self.drawing_text = ()
        self.correspondence = {
            id(self.owner): SimpleNamespace(Visible=1),
            **{id(segment): object() for segment in self.source.GetSketchSegments()},
        }

    def GetReferencedModelName(self):
        return str(self.referenced_path)

    def GetOrientationName(self):
        return "*Right"

    def UpdateViewDisplayGeometry(self):
        self.refreshes.append((tuple(self.Position), tuple(self.ScaleRatio)))
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        x, y = self.Position
        self._transform = SimpleNamespace(
            apply=lambda xyz: (x + ratio * xyz[0], y + ratio * xyz[1], ratio * xyz[2]),
        )
        # Native void return deliberately remains None.

    @property
    def ModelToViewTransform(self):
        assert self.refreshes[-1] == (tuple(self.Position), tuple(self.ScaleRatio))
        return self._transform

    def GetBodiesCount(self):
        return 0  # Not a substitute for actual configured source body counts.

    def GetCorresponding(self, native):
        self.correspondence_reads.append((self.ReferencedDocument.active, native))
        if self.ReferencedDocument.active != self.ReferencedConfiguration:
            return None  # Real correspondence can disappear after source restore.
        return self.correspondence.get(id(native))

    def GetSketch(self):
        return SimpleNamespace(
            GetSketchSegments=lambda: tuple(self.drawing_segments),
            GetSketchBlockInstanceCount=lambda: self.drawing_blocks,
            GetSketchTextSegments=lambda: self.drawing_text,
            GetUserPointsCount=lambda: self.drawing_user_points,
        )

    def SetViewPosition(self, position, update):
        assert update is False
        self.Position = tuple(position)
        self.position_writes.append(self.Position)
        return True

    def GetOutline(self):
        self.outline_calls += 1
        ratio = (
            self.ScaleRatio[0] / self.ScaleRatio[1] if self.outline == "padded" else 1
        )
        xs, ys = zip(*self.source.points)
        width = (max(xs) - min(xs)) * ratio + self.OUTLINE_FLOOR_M
        height = (max(ys) - min(ys)) * ratio + self.OUTLINE_FLOOR_M
        x, y = self.Position
        return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)


class _ReferenceDrawing:
    def __init__(self, views):
        self.views = views
        self.native_identity = object()
        self.sheet = "SupplierSheet"
        self.ActiveDrawingView = next(iter(views.values()))
        self.edit_sheet = True

    def GetTitle(self):
        return "supplier-test-drawing.SLDDRW"

    def GetCurrentSheet(self):
        return SimpleNamespace(GetName=lambda: self.sheet)

    def GetEditSheet(self):
        return self.edit_sheet

    def ActivateSheet(self, name):
        self.sheet = name
        return True

    def ActivateView(self, name):
        self.ActiveDrawingView = (
            next(view for view in self.views.values() if view.Name == name)
            if name else None
        )
        if not name:
            self.edit_sheet = True
        # Native ActivateView returns False for sheet context, unlike a named view.
        return bool(name)

    def EditRebuild3(self):
        return True


class _MathPoint:
    def __init__(self, xyz):
        self.ArrayData = tuple(xyz)

    def MultiplyTransform(self, transform):
        return _MathPoint(transform.apply(self.ArrayData))


class _ReferenceApplication:
    def __init__(self, model, draw):
        self.documents = {model.GetTitle(): model, draw.GetTitle(): draw}
        self.ActiveDoc = draw
        self.activations = []

    def IsSame(self, left, right):
        return int(
            getattr(left, "native_identity", left)
            is getattr(right, "native_identity", right)
        )

    def ActivateDoc3(self, name, use_preferences, rebuild_option, error_seed):
        assert (use_preferences, rebuild_option, error_seed) == (False, 1, 0)
        self.activations.append(name)
        self.ActiveDoc = self.documents[name]
        return self.ActiveDoc, 0

    def GetMathUtility(self):
        return SimpleNamespace(CreatePoint=_MathPoint)


def _capture_source_curve_geometry(sketch, *, label):
    """Fake native capture boundary only; real DTO/projection/fitter stay in use."""
    assert label
    sketch.capture_count += 1
    sketch.model.events.append(("capture", sketch.model.active, sketch.points))
    # Each source polyline segment supplies its own two endpoints; no cell,
    # scale, GetOutline or view position participates in this immutable capture.
    points = tuple(
        (float(point[0]), float(point[1]), 0.0)
        for start, end in zip(sketch.points, sketch.points[1:])
        for point in (start, end)
    )
    return NativeSketchGeometry(points, tuple(range(0, len(points), 2)), ())


class _CaptureHarness:
    def __init__(self, views):
        self.views = views
        self.view = next(iter(views.values()))
        self.model = self.view.ReferencedDocument
        self.source = self.model.path
        self.draw = _ReferenceDrawing(views)
        self.adapter = SimpleNamespace(
            swApp=_ReferenceApplication(self.model, self.draw),
            currentModel=self.draw,
        )
        self.features = {key: ("SupplierSection",) for key in views}
        self.configurations = {
            key: view.ReferencedConfiguration for key, view in views.items()
        }
        self.captures = None

    def capture(self):
        self.captures = supplier_drawing._capture_reference_views(
            self.adapter,
            self.draw,
            self.views,
            source=self.source,
            model=self.model,
            features=self.features,
            configurations=self.configurations,
            label="supplier capture",
        )
        return self.captures

    def project(self, key=None, **overrides):
        assert self.captures is not None, "capture must finish before any fitting"
        key = next(iter(self.views)) if key is None else key
        arguments = {
            "capture": self.captures[key],
            "source": self.source,
            "model": self.model,
            "configuration": self.configurations[key],
            "features": self.features[key],
            "label": f"supplier projected {key}",
        }
        view = overrides.pop("view", self.views[key])
        arguments.update(overrides)
        return supplier_drawing._reference_view_bounds(self.adapter, view, **arguments)

    def read(self, view, label):
        key = next(key for key, known in self.views.items() if known is view)
        return self.project(key, label=label)


@pytest.fixture
def reference_scene(monkeypatch):
    monkeypatch.setattr(purchased, "double_array", tuple)
    monkeypatch.setattr(_drawing_projection, "double_array", tuple)
    monkeypatch.setattr(
        supplier_drawing, "FeatureWalk", lambda model: iter(model.features)
    )
    monkeypatch.setattr(supplier_drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(
        supplier_drawing,
        "capture_native_sketch_geometry",
        _capture_source_curve_geometry,
    )

    def make(points=((0.002, 0.003), (0.015, 0.004)), *, outline="padded", views=None):
        if views is None:
            view = _ReferenceInkView(points, outline=outline)
            views = {view.Name: view}
        return _CaptureHarness(views)

    return make


def _sibling_view(first, name, configuration="SupplierReference"):
    view = _ReferenceInkView(first.source.points, name=name)
    view.ReferencedDocument = first.ReferencedDocument
    view.source, view.owner = first.source, first.owner
    view.correspondence = dict(first.correspondence)
    view.ReferencedConfiguration = configuration
    return view


@pytest.mark.parametrize("outline", ["padded", "stale"])
@pytest.mark.parametrize(
    "maximum,key,margins,points,cell_size",
    [
        pytest.param(
            True,
            "free_right",
            _EXTENSION_MARGINS,
            ((-0.003, 0.002), (0.005, 0.002), (0.005, 0.008), (-0.003, 0.008)),
            (0.183, 0.010),
            id="spring-right",
        ),
        pytest.param(
            False,
            "free_top",
            # A 4 mm TOP lane (the connecting link's margins before it moved
            # to a 2:1 fit): shorter than the native outline floor.
            {"free_top": (0.030, 0.016, 0.045, 0.020)},
            ((0.002, 0.001), (0.015, 0.001), (0.015, 0.0025), (0.002, 0.0025)),
            (0.132, 0.004),
            id="short-top",
        ),
    ],
)
def test_actual_reference_ink_fits_current_cells_that_native_outline_floor_cannot(
    reference_scene, outline, maximum, key, margins, points, cell_size
):
    cells = supplier_state_cells(
        purchased.view_band_bottom("", label="supplier reference"), maximum=maximum
    )
    fitted = purchased.supplier_fit_cells(cells, margins, label="supplier reference")
    cell = next(cell for cell in fitted if cell[0] == key)
    _, center, bounds = cell
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    assert (width, height) == pytest.approx(cell_size)
    assert _ReferenceInkView.OUTLINE_FLOOR_M > height
    old = _ReferenceInkView(points, outline=outline)
    with pytest.raises(RuntimeError, match="no project-standard scale"):
        purchased._fit_group(SimpleNamespace(EditRebuild3=lambda: True), [(old, cell)])
    assert not old.position_writes

    harness = reference_scene(points, outline=outline)
    harness.capture()
    source_events = tuple(harness.model.events)
    native = harness.view
    scale = purchased._fit_group(
        harness.draw, [(native, cell)], read_bounds=harness.read
    )
    xs, ys = zip(*points)
    span = (max(xs) - min(xs), max(ys) - min(ys))
    feasible = [
        numerator / denominator
        for numerator, denominator in purchased._SCALES
        if span[0] * numerator / denominator <= width
        and span[1] * numerator / denominator <= height
    ]
    ratio = scale[0] / scale[1]
    assert ratio == max(feasible)
    assert native.UseSheetScale == 0
    assert native.Position == pytest.approx(
        (
            center[0] - ratio * (min(xs) + max(xs)) / 2,
            center[1] - ratio * (min(ys) + max(ys)) / 2,
        )
    )
    actual = harness.project()
    assert _contains(bounds, actual)
    assert ((actual[0] + actual[2]) / 2, (actual[1] + actual[3]) / 2) == pytest.approx(
        center
    )
    assert native.position_writes and native.outline_calls == 0
    assert tuple(harness.model.events) == source_events
    assert native.source.capture_count == 1


@pytest.mark.parametrize(
    "points",
    [((0.002, 0.003), (0.015, 0.003)), ((0.004, 0.001), (0.004, 0.014))],
    ids=["zero-height", "zero-width"],
)
def test_validated_one_dimensional_reference_ink_is_fitted_and_centered(
    reference_scene, points
):
    cells = supplier_state_cells(
        purchased.view_band_bottom("", label="1D reference"), maximum=False
    )
    fitted = purchased.supplier_fit_cells(
        cells, chain_dimensions.SUPPLIER_MARGINS, label="1D reference"
    )
    cell = next(cell for cell in fitted if cell[0] == "free_top")
    harness = reference_scene(points)
    harness.capture()
    scale = purchased._fit_group(
        harness.draw, [(harness.view, cell)], read_bounds=harness.read
    )
    box = harness.project()
    assert scale in purchased._SCALES and purchased._inside(box, cell[2])
    assert ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) == pytest.approx(cell[1])
    assert (box[0] == box[2]) != (box[1] == box[3])
    assert harness.view.outline_calls == 0


def test_reference_fit_refreshes_each_projection_without_source_switch_or_live_correspondence(
    monkeypatch, reference_scene
):
    harness = reference_scene(((0.002, 0.003), (0.010, 0.009)))
    harness.capture()
    native, model = harness.view, harness.model
    events, correspondence_reads = (
        tuple(model.events),
        tuple(native.correspondence_reads),
    )
    original_position = native.Position
    native.refreshes.clear()

    def forbidden(*_args, **_kwargs):
        pytest.fail(
            "postcapture projection must not touch configuration-dependent source data"
        )

    for name in ("ShowConfiguration2", "EditRebuild3"):
        monkeypatch.setattr(model, name, forbidden)
    monkeypatch.setattr(supplier_drawing, "FeatureWalk", forbidden)
    native.GetCorresponding = forbidden
    native.source.GetSketchSegments = forbidden
    native.source.points = ((400.0, 500.0), (600.0, 700.0))
    cells = supplier_state_cells(
        purchased.view_band_bottom("", label="refresh reference"), maximum=True
    )
    fitted = purchased.supplier_fit_cells(
        cells, _EXTENSION_MARGINS, label="refresh reference"
    )
    cell = next(cell for cell in fitted if cell[0] == "free_right")
    scale = purchased._fit_group(
        harness.draw, [(native, cell)], read_bounds=harness.read
    )
    candidates = purchased._SCALES[: purchased._SCALES.index(scale) + 1]
    assert native.refreshes[:-1] == [
        (original_position, candidate) for candidate in candidates
    ]
    assert native.refreshes[-1] == (native.Position, scale)
    assert native.Position != original_position
    assert purchased._inside(harness.project(), cell[2])
    assert tuple(model.events) == events
    assert tuple(native.correspondence_reads) == correspondence_reads
    assert model.active == "Installed"
    assert harness.adapter.currentModel is harness.draw


def test_reference_capture_deduplicates_shared_owner_across_views_before_restoring(
    reference_scene,
):
    first = _ReferenceInkView(((0.002, 0.003), (0.015, 0.004)), name="front")
    second = _sibling_view(first, "top")
    harness = reference_scene(views={"front": first, "top": second})
    captures = harness.capture()
    assert captures["front"].geometry[0] is captures["top"].geometry[0]
    assert first.source.capture_count == 1
    assert [event for event in harness.model.events if event[0] == "switch"] == [
        ("switch", "SupplierReference"),
        ("switch", "Installed"),
    ]
    assert not any(event[0] == "rebuild" for event in harness.model.events)
    assert harness.adapter.swApp.activations == [
        harness.model.GetTitle(),
        harness.draw.GetTitle(),
    ]
    assert harness.adapter.swApp.ActiveDoc is harness.draw
    assert harness.draw.ActiveDrawingView is first
    assert harness.draw.sheet == "SupplierSheet"


def test_reference_capture_reacquires_each_configuration_then_projects_only_immutable_values(
    monkeypatch, reference_scene
):
    first = _ReferenceInkView(((0.2, 0.3), (0.4, 0.5)), name="free")
    second = _sibling_view(first, "maximum", "MaximumReference")
    harness = reference_scene(views={"free": first, "maximum": second})
    model = harness.model
    points = {
        "Installed": ((0.2, 0.3), (0.4, 0.5)),
        "SupplierReference": ((0.002, 0.003), (0.005, 0.007)),
        "MaximumReference": ((-0.006, 0.002), (0.010, 0.008)),
    }
    show = model.ShowConfiguration2
    acquired = []

    def expired():
        pytest.fail("old configuration feature proxies must not be retained")

    def switch(name):
        result = show(name)
        for feature in model.features:
            feature.GetSpecificFeature2 = expired
        sketch = _source_sketch(points[name], model)
        feature = _ReferenceFeature("SupplierSection", sketch)
        model.features = [feature]
        acquired.append(feature)
        for view in harness.views.values():
            view.correspondence = {
                id(feature): SimpleNamespace(Visible=1),
                **{id(segment): object() for segment in sketch.GetSketchSegments()},
            }
        return result

    monkeypatch.setattr(model, "ShowConfiguration2", switch)
    harness.capture()
    assert model.active == "Installed"
    assert [event for event in model.events if event[0] == "capture"] == [
        ("capture", "SupplierReference", points["SupplierReference"]),
        ("capture", "MaximumReference", points["MaximumReference"]),
    ]
    events = tuple(model.events)
    assert harness.project("free") == pytest.approx((0.072, 0.133, 0.075, 0.137))
    assert harness.project("maximum") == pytest.approx((0.064, 0.132, 0.080, 0.138))
    assert tuple(model.events) == events
    assert len(acquired) == 3
    assert all(acquired[index] is not acquired[index + 1] for index in (0, 1))


@pytest.mark.parametrize("original", ["Installed", "SupplierReference"])
def test_reference_capture_restores_original_clean_source_state(
    reference_scene, original
):
    harness = reference_scene()
    harness.model.active = original
    harness.capture()
    assert harness.model.active == original
    assert harness.model.GetSaveFlag() is False
    assert harness.model.IsOpenedReadOnly() is True
    assert harness.adapter.currentModel is harness.draw
    assert harness.captures["reference"].source.body_counts == (
        (1, 0) if original == "Installed" else (0, 0)
    )
    switches = [event for event in harness.model.events if event[0] == "switch"]
    assert switches == (
        [("switch", "SupplierReference"), ("switch", "Installed")]
        if original == "Installed"
        else []
    )


@pytest.mark.parametrize("original", ["Installed", "SupplierReference"])
def test_reference_capture_refuses_initially_dirty_source_before_any_mutation(
    reference_scene, original
):
    harness = reference_scene()
    harness.model.active, harness.model.dirty = original, True
    with pytest.raises(
        RuntimeError, match="source must be clean before native reference capture"
    ):
        harness.capture()
    assert harness.model.active == original
    assert harness.model.GetSaveFlag() is True
    assert not any(
        event[0] in ("switch", "rebuild", "capture") for event in harness.model.events
    )
    assert harness.adapter.swApp.activations == []
    assert harness.adapter.currentModel is harness.draw
    assert harness.view.source.capture_count == 0


@pytest.mark.parametrize("status", [0, 1, 2, 3])
def test_reference_capture_rebuilds_only_when_native_status_requires_it(
    reference_scene, status
):
    harness = reference_scene()
    harness.model.rebuild_on_switch = status
    harness.capture()
    rebuilt = [event for event in harness.model.events if event[0] == "rebuild"]
    assert rebuilt == (
        []
        if status == 0
        else [("rebuild", "SupplierReference"), ("rebuild", "Installed")]
    )


@pytest.mark.parametrize("status", [None, True, -1, 4])
def test_reference_capture_refuses_invalid_native_rebuild_status(
    reference_scene, status
):
    harness = reference_scene()
    harness.model.Extension.NeedsRebuild2 = status
    with pytest.raises(RuntimeError, match="invalid native source rebuild status"):
        harness.capture()
    assert harness.view.source.capture_count == 0


@pytest.mark.parametrize(
    "fault,match",
    [
        ("configuration", "source document/path/configuration changed"),
        ("source-solid", "has solid/sheet bodies"),
        ("source-sheet", "has solid/sheet bodies"),
        ("wrong-owner-kind", "source reference|source sketch|source owner"),
        ("source-unhidden", "hidden"),
        ("suppressed-owner", "suppressed"),
        ("missing-owner", "missing|owner|reference"),
        ("missing-segment-correspondence", "no drawing-view correspondence"),
        ("unreadable-source-visibility", "hidden"),
    ],
)
def test_reference_capture_rejects_unproven_native_inventory(
    reference_scene, fault, match
):
    harness = reference_scene()
    native, model = harness.view, harness.model
    if fault == "configuration":
        native.ReferencedConfiguration = "Installed"
    elif fault in ("source-solid", "source-sheet"):
        model.bodies["SupplierReference"][0 if fault == "source-solid" else 1] = (
            object(),
        )
        assert native.GetBodiesCount() == 0
    elif fault == "suppressed-owner":
        native.owner.suppressed = True
    elif fault == "wrong-owner-kind":
        native.owner.kind = "RefPlane"
    elif fault == "source-unhidden":
        native.owner.Visible = 2
    elif fault == "missing-owner":
        model.features.clear()
    elif fault == "missing-segment-correspondence":
        del native.correspondence[id(native.source.GetSketchSegments()[0])]
    else:
        native.owner.Visible = None
    with pytest.raises(RuntimeError, match=match):
        harness.capture()
    assert model.active == "Installed"
    assert native.outline_calls == 0


@pytest.mark.parametrize("corresponding_visibility", [None, 1, 2, -1])
def test_reference_capture_does_not_infer_render_visibility_from_corresponding_feature(
    reference_scene, corresponding_visibility
):
    harness = reference_scene()
    if corresponding_visibility is None:
        del harness.view.correspondence[id(harness.view.owner)]
    else:
        harness.view.correspondence[id(harness.view.owner)].Visible = corresponding_visibility
    harness.capture()
    assert harness.model.active == "Installed"
    assert harness.view.owner.Visible == 1
    # Actual source geometry is independent of the corresponding feature's state.
    assert harness.project() == pytest.approx((0.072, 0.133, 0.085, 0.134))


@pytest.mark.parametrize("duplicate", ["same", "alias", "distinct"])
def test_reference_capture_deduplicates_only_proven_native_feature_identity(
    reference_scene, duplicate
):
    harness = reference_scene()
    owner = harness.view.owner
    other = (
        owner
        if duplicate == "same"
        else (
            copy(owner)
            if duplicate == "alias"
            else _ReferenceFeature(owner.Name, owner.sketch)
        )
    )
    harness.model.features.append(other)
    if duplicate == "distinct":
        with pytest.raises(RuntimeError, match="ambiguous native reference identity"):
            harness.capture()
    else:
        harness.capture()
        assert harness.view.source.capture_count == 1


def test_reference_capture_unions_distinct_expected_source_owners(reference_scene):
    harness = reference_scene()
    sketch = _source_sketch(((-0.006, 0.007), (0.008, 0.012)), harness.model)
    feature = _ReferenceFeature("SecondOwner", sketch)
    harness.model.features.append(feature)
    harness.view.correspondence[id(feature)] = SimpleNamespace(Visible=1)
    harness.view.correspondence.update(
        {id(segment): object() for segment in sketch.GetSketchSegments()}
    )
    harness.features["reference"] = ("SupplierSection", "SecondOwner")
    harness.capture()
    assert harness.project() == pytest.approx((0.064, 0.133, 0.085, 0.142))
    assert sketch.capture_count == harness.view.source.capture_count == 1


@pytest.mark.parametrize(
    "fault",
    [
        "foreign-view",
        "foreign-model",
        "foreign-path",
        "foreign-configuration",
        "foreign-features",
        "changed-view-name",
        "changed-view-document",
        "changed-view-path",
        "changed-source-path",
        "changed-view-configuration",
        "changed-source-configuration",
        "new-dirty",
        "read-only",
        "members",
    ],
)
def test_reference_projection_rejects_foreign_capture_and_changed_preserved_state(
    reference_scene, fault
):
    harness = reference_scene()
    harness.capture()
    overrides = {}
    if fault == "foreign-view":
        overrides["view"] = _sibling_view(harness.view, harness.view.Name)
    elif fault == "foreign-model":
        overrides["model"] = _ReferenceModel([])
    elif fault == "foreign-path":
        overrides["source"] = Path("different-source.SLDPRT")
    elif fault == "foreign-configuration":
        overrides["configuration"] = "MaximumReference"
    elif fault == "foreign-features":
        overrides["features"] = ("DifferentOwner",)
    elif fault == "changed-view-name":
        harness.view.Name = "RenamedView"
    elif fault == "changed-view-document":
        harness.view.ReferencedDocument = _ReferenceModel([])
    elif fault == "changed-view-path":
        harness.view.referenced_path = Path("different-source.SLDPRT")
    elif fault == "changed-source-path":
        harness.model.path = Path("different-source.SLDPRT")
    elif fault == "changed-view-configuration":
        harness.view.ReferencedConfiguration = "Installed"
    elif fault == "changed-source-configuration":
        harness.model.active = "MaximumReference"
    elif fault == "new-dirty":
        harness.model.dirty = True
    elif fault == "read-only":
        harness.model.read_only = False
    else:
        harness.model.configurations = ("Installed", "SupplierReference")
    with pytest.raises(
        RuntimeError,
        match="foreign or incomplete|source document/path/configuration changed|member state changed",
    ):
        harness.project(**overrides)


def test_reference_projection_accepts_distinct_wrappers_with_proven_native_identity(
    reference_scene,
):
    harness = reference_scene()
    harness.capture()
    view_alias, model_alias = copy(harness.view), copy(harness.model)
    assert view_alias is not harness.view and model_alias is not harness.model
    assert harness.project(view=view_alias, model=model_alias) == pytest.approx(
        (0.072, 0.133, 0.085, 0.134)
    )
    foreign = replace(
        harness.captures["reference"],
        view=_sibling_view(harness.view, harness.view.Name),
    )
    with pytest.raises(RuntimeError, match="foreign or incomplete"):
        harness.project(capture=foreign)


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("drawing_segments", [object()]),
        ("drawing_blocks", 1),
        ("drawing_text", (object(),)),
        ("drawing_user_points", 1),
    ],
)
def test_reference_projection_rechecks_added_drawing_sketch_ink(
    reference_scene, attribute, value
):
    harness = reference_scene()
    harness.capture()
    events = tuple(harness.model.events)
    setattr(harness.view, attribute, value)
    with pytest.raises(RuntimeError, match="drawing-sketch geometry"):
        harness.project()
    assert tuple(harness.model.events) == events


@pytest.mark.parametrize("primary_type", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("restore_fails", [False, True])
def test_reference_capture_restores_on_baseexception_and_notes_separate_restore_failures(
    monkeypatch, reference_scene, primary_type, restore_fails
):
    harness = reference_scene()
    primary = primary_type("native capture unreadable")

    def unreadable(_sketch, *, label):
        assert label and harness.model.active == "SupplierReference"
        raise primary

    monkeypatch.setattr(supplier_drawing, "capture_native_sketch_geometry", unreadable)
    if restore_fails:
        show = harness.model.ShowConfiguration2
        harness.model.ShowConfiguration2 = lambda name: (
            False if name == "Installed" else show(name)
        )
        harness.draw.ActivateSheet = lambda _name: False
    with pytest.raises(primary_type, match="native capture unreadable") as caught:
        harness.capture()
    assert caught.value is primary
    assert harness.adapter.currentModel is harness.draw
    if restore_fails:
        assert len(caught.value.__notes__) == 2
        assert all("restoration also failed" in note for note in caught.value.__notes__)
    else:
        assert harness.model.active == "Installed"
        assert not getattr(caught.value, "__notes__", ())


def test_reference_capture_restore_failure_is_not_swallowed_by_outer_exception_handler(
    reference_scene,
):
    harness = reference_scene()
    show = harness.model.ShowConfiguration2
    harness.model.ShowConfiguration2 = lambda name: (
        False if name == "Installed" else show(name)
    )
    try:
        raise RuntimeError("unrelated outer exception")
    except RuntimeError as outer:
        with pytest.raises(
            RuntimeError, match="cannot activate source configuration 'Installed'"
        ):
            harness.capture()
        assert not getattr(outer, "__notes__", ())


@pytest.mark.parametrize(
    "fault,match",
    [
        ("switch-refused", "cannot activate source configuration"),
        ("switch-readback", "source configuration readback differs"),
        ("source-rebuild", "cannot rebuild source configuration"),
        ("source-rebuild-drift", "did not settle after rebuilding"),
        ("rebuild-still-needed", "did not settle after rebuilding"),
        ("restore-rebuild", "cannot rebuild source configuration 'Installed'"),
        ("newly-dirty", "member state changed"),
        ("read-only", "member state changed"),
        ("members", "member state changed"),
        ("original-body-count", "member state changed"),
        (
            "geometry-config-drift",
            "geometry capture changed the requested source configuration",
        ),
        ("missing-active", "source path/active configuration is unreadable"),
        ("sheet-restore", "cannot restore supplier drawing sheet/view context"),
    ],
)
def test_reference_capture_configuration_and_preservation_failures_refuse(
    monkeypatch, reference_scene, fault, match
):
    harness = reference_scene()
    model = harness.model
    show, rebuild = model.ShowConfiguration2, model.EditRebuild3
    if fault in ("switch-refused", "switch-readback"):
        model.ShowConfiguration2 = lambda name: (
            fault == "switch-readback" if name == "SupplierReference" else show(name)
        )
    elif fault in (
        "source-rebuild",
        "source-rebuild-drift",
        "rebuild-still-needed",
        "restore-rebuild",
    ):
        model.rebuild_on_switch = 1

        def broken_rebuild():
            if model.active == "SupplierReference":
                if fault == "source-rebuild":
                    return False
                if fault == "source-rebuild-drift":
                    model.active = "UnexpectedConfiguration"
                    return True
                if fault == "rebuild-still-needed":
                    return True
            elif fault == "restore-rebuild":
                return False
            return rebuild()

        model.EditRebuild3 = broken_rebuild
    elif fault == "missing-active":
        model.active = ""
    elif fault == "sheet-restore":
        harness.draw.ActivateSheet = lambda _name: False
    else:

        def changed_source(sketch, *, label):
            geometry = _capture_source_curve_geometry(sketch, label=label)
            if fault == "newly-dirty":
                model.dirty = True
            elif fault == "read-only":
                model.read_only = False
            elif fault == "members":
                model.configurations = ("Installed", "SupplierReference")
            elif fault == "original-body-count":
                model.bodies["Installed"][0] = ()
            else:
                model.active = "UnexpectedConfiguration"
            return geometry

        monkeypatch.setattr(
            supplier_drawing, "capture_native_sketch_geometry", changed_source
        )
    with pytest.raises(RuntimeError, match=match):
        harness.capture()
    assert harness.view.outline_calls == 0


@pytest.mark.parametrize(
    "error_state",
    [
        (1, False),
        (7, True),
        None,
        0,
        (0,),
        (0, False, False),
        (False, False),
        (0.0, False),
        ("0", False),
        [0, False],
    ],
)
def test_reference_capture_refuses_feature_error_before_reading_geometry(
    reference_scene, error_state
):
    harness = reference_scene()
    harness.view.owner.error_state = error_state
    harness.view.owner.GetSpecificFeature2 = lambda: pytest.fail(
        "errorful feature may omit source entities"
    )
    with pytest.raises(
        RuntimeError, match="source sketch 'SupplierSection' error state"
    ):
        harness.capture()
    assert harness.view.source.capture_count == 0
    assert harness.model.active == "Installed"


@pytest.mark.parametrize("missing", [False, True])
def test_reference_capture_refuses_missing_or_unreadable_feature_error_status(
    reference_scene, missing
):
    harness = reference_scene()
    owner = harness.view.owner

    def unreadable():
        raise RuntimeError("native feature error state unreadable")

    if missing:
        feature = SimpleNamespace(
            Name=owner.Name,
            Visible=owner.Visible,
            GetTypeName2=owner.GetTypeName2,
            IsSuppressed2=owner.IsSuppressed2,
            GetSpecificFeature2=lambda: pytest.fail(
                "feature status must precede source reads"
            ),
        )
        harness.model.features = [feature]
        harness.view.correspondence[id(feature)] = SimpleNamespace(Visible=2)
    else:
        owner.GetErrorCode2 = unreadable
    with pytest.raises(
        AttributeError if missing else RuntimeError,
        match="GetErrorCode2|native feature error state unreadable",
    ):
        harness.capture()
    assert harness.model.active == "Installed"
    assert harness.view.source.capture_count == 0


def test_reference_capture_ignores_undefined_warning_flag_for_zero_feature_error(
    reference_scene,
):
    class UndefinedWarning:
        def __bool__(self):
            pytest.fail("IsWarning is undefined for error code zero")

    harness = reference_scene()
    harness.view.owner.error_state = (0, UndefinedWarning())
    harness.capture()
    assert harness.project() == pytest.approx((0.072, 0.133, 0.085, 0.134))


def test_reference_fit_diagnostics_reuse_capture_and_continue_after_projection_failure(
    monkeypatch, reference_scene
):
    harness = reference_scene()
    harness.capture()
    events = tuple(harness.model.events)
    original_scale, original_sheet_scale = (
        harness.view.ScaleRatio,
        harness.view.UseSheetScale,
    )
    messages, calls = [], []
    monkeypatch.setattr(supplier_drawing._telemetry, "info", messages.append)
    monkeypatch.setattr(supplier_drawing, "double_array", tuple)

    def read(view, key):
        calls.append(tuple(view.ScaleRatio))
        if len(calls) == 1:
            raise RuntimeError("one projected frame unreadable")
        return harness.read(view, key)

    cell = purchased._cell("reference", 0.02, 0.10, 0.15, 0.15)
    supplier_drawing._record_supplier_fit_candidates(
        harness.adapter,
        harness.draw,
        [(harness.view, cell)],
        read_bounds=read,
    )
    assert calls == list(purchased._SCALES)
    assert len(messages) == len(purchased._SCALES)
    assert "one projected frame unreadable" in messages[0]
    assert all("bounds_source='captured-native'" in message for message in messages)
    assert all("bounds_size_excess_m=" in message for message in messages[1:])
    assert harness.view.ScaleRatio == original_scale
    assert harness.view.UseSheetScale == original_sheet_scale
    assert tuple(harness.model.events) == events


@pytest.mark.parametrize("read_only", [False, 1, None])
def test_reference_capture_requires_exact_native_readonly_before_any_mutation(
    reference_scene, read_only
):
    harness = reference_scene()
    harness.model.read_only = read_only
    with pytest.raises(RuntimeError, match="requires a read-only source"):
        harness.capture()
    assert harness.adapter.swApp.activations == []
    assert harness.model.events == []
    assert harness.model.dirty is False
    assert harness.view.source.capture_count == 0


def test_reference_presentation_dirty_requires_explicit_phase_and_never_clears_flag(
    reference_scene,
):
    harness = reference_scene()
    harness.capture()
    harness.model.dirty = True  # Native model-owned annotation SetText effect.
    with pytest.raises(RuntimeError, match="member state changed"):
        harness.project()  # Preparation/fitting/default callers remain strict.
    events = tuple(harness.model.events)
    for _ in range(2):  # Presentation and subsequent settled callback.
        assert harness.project(allow_presentation_dirty=True) == pytest.approx(
            (0.072, 0.133, 0.085, 0.134)
        )
        assert harness.model.dirty is True
        assert harness.model.read_only is True
        assert harness.model.active == "Installed"
    assert tuple(harness.model.events) == events


@pytest.mark.parametrize(
    "fault",
    ["writable", "nonbool-readonly", "nonbool-dirty", "body-count", "configuration"],
)
def test_reference_presentation_phase_does_not_relax_source_identity_or_preservation(
    reference_scene, fault
):
    harness = reference_scene()
    harness.capture()
    harness.model.dirty = True
    if fault == "writable":
        harness.model.read_only = False
    elif fault == "nonbool-readonly":
        harness.model.read_only = 1
    elif fault == "nonbool-dirty":
        harness.model.dirty = 1
    elif fault == "body-count":
        harness.model.bodies["Installed"][0] = ()
    else:
        harness.model.active = "SupplierReference"
    with pytest.raises(RuntimeError, match="member state changed"):
        harness.project(allow_presentation_dirty=True)


def test_supplier_builder_hashes_before_readonly_open_and_stops_if_open_refuses(
    monkeypatch, tmp_path
):
    source = tmp_path / "supplier.SLDPRT"
    source.write_bytes(b"offline supplier source")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    calls = []
    real_hash = supplier_drawing._source_file_sha256

    def hash_source(path):
        assert path == source
        calls.append("hash")
        value = real_hash(path)
        assert value == expected
        return value

    def refuse_open(adapter, path, *, label):
        assert path == source and label == "supplier"
        assert calls == ["hash"]
        calls.append("readonly-open")
        raise RuntimeError("already-open source is writable")

    def forbidden(*_args, **_kwargs):
        pytest.fail(
            "source opening refusal must precede any presentation or drawing creation"
        )

    monkeypatch.setattr(supplier_drawing, "_source_file_sha256", hash_source)
    monkeypatch.setattr(
        supplier_drawing, "_open_supplier_source_read_only", refuse_open
    )
    monkeypatch.setattr(supplier_drawing, "new_project_drawing", forbidden)
    monkeypatch.setattr(supplier_drawing, "read_required_properties", forbidden)
    spec = SimpleNamespace(source=source, source_kind="part", artifact_stem="supplier")
    with pytest.raises(RuntimeError, match="already-open source is writable"):
        asyncio.run(
            supplier_drawing.build_supplier_spring_drawing(
                SimpleNamespace(),
                spec,
                item="1",
                supplier_dimensions=forbidden,
                supplier_margins={},
                supplier_reference_features={},
            )
        )
    assert calls == ["hash", "readonly-open"]
    assert source.read_bytes() == b"offline supplier source"


@pytest.mark.parametrize("changed", [False, True])
def test_reference_finalization_guard_checks_actual_source_bytes(tmp_path, changed):
    source = tmp_path / "supplier.SLDPRT"
    source.write_bytes(b"original source bytes")
    expected = supplier_drawing._source_file_sha256(source)

    def finalize_fake():
        if changed:
            source.write_bytes(b"unexpected saved presentation")

    if changed:
        with pytest.raises(
            RuntimeError, match="source part bytes changed during drawing finalization"
        ):
            with supplier_drawing._preserve_reference_source_file(
                source, expected, label="supplier"
            ):
                finalize_fake()
    else:
        with supplier_drawing._preserve_reference_source_file(
            source, expected, label="supplier"
        ):
            finalize_fake()
        assert source.read_bytes() == b"original source bytes"


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_reference_finalization_guard_preserves_primary_and_notes_changed_bytes(
    tmp_path, changed, error_type
):
    source = tmp_path / "supplier.SLDPRT"
    source.write_bytes(b"original source bytes")
    expected = supplier_drawing._source_file_sha256(source)
    primary = error_type("drawing finalization failed")
    with pytest.raises(error_type, match="drawing finalization failed") as caught:
        with supplier_drawing._preserve_reference_source_file(
            source, expected, label="supplier"
        ):
            if changed:
                source.write_bytes(b"unexpected drawing-save source write")
            raise primary
    assert caught.value is primary
    notes = getattr(primary, "__notes__", ())
    if changed:
        assert len(notes) == 1
        assert "source file preservation also failed" in notes[0]
        assert "source part bytes changed" in notes[0]
    else:
        assert not notes


def test_reference_finalization_hash_failure_is_not_swallowed_by_outer_handler(
    tmp_path,
):
    source = tmp_path / "supplier.SLDPRT"
    source.write_bytes(b"original source bytes")
    expected = supplier_drawing._source_file_sha256(source)
    try:
        raise RuntimeError("unrelated outer exception")
    except RuntimeError as outer:
        with pytest.raises(RuntimeError, match="source part bytes changed"):
            with supplier_drawing._preserve_reference_source_file(
                source, expected, label="supplier"
            ):
                source.write_bytes(b"changed source bytes")
        assert not getattr(outer, "__notes__", ())


@pytest.mark.parametrize("dirty", [True, 1, None])
def test_supplier_builder_rejects_nonclean_opened_source_before_metadata_or_prepare(
    monkeypatch, tmp_path, reference_scene, dirty
):
    source = tmp_path / "supplier.SLDPRT"
    source.write_bytes(b"offline source")
    harness = reference_scene()
    harness.model.dirty = dirty
    calls = []

    def open_readonly(adapter, path, *, label):
        assert path == source and label == "supplier"
        calls.append("readonly-open")
        adapter.currentModel = harness.model
        return harness.model

    def forbidden(*_args, **_kwargs):
        pytest.fail(
            "nonclean opened source must be rejected before presentation preparation"
        )

    monkeypatch.setattr(
        supplier_drawing, "_open_supplier_source_read_only", open_readonly
    )
    monkeypatch.setattr(supplier_drawing, "read_required_properties", forbidden)
    monkeypatch.setattr(supplier_drawing, "new_project_drawing", forbidden)
    spec = SimpleNamespace(source=source, source_kind="part", artifact_stem="supplier")
    with pytest.raises(RuntimeError, match="clean"):
        asyncio.run(
            supplier_drawing.build_supplier_spring_drawing(
                harness.adapter,
                spec,
                item="1",
                supplier_dimensions=forbidden,
                prepare_views=forbidden,
                supplier_margins={},
                supplier_reference_features={},
            )
        )
    assert calls == ["readonly-open"]
    assert harness.model.dirty is dirty
    assert harness.model.events == []


@pytest.mark.parametrize("dirty_stage", ["prepare", "fit", "presentation"])
def test_supplier_builder_enables_dirty_allowance_only_at_annotation_callback(
    monkeypatch, tmp_path, reference_scene, dirty_stage
):
    import _seat_forensics

    def forbidden_native_diagnostic(*_args, **_kwargs):
        pytest.fail("offline phase regression must not enter native seat diagnostics")

    monkeypatch.setattr(
        _seat_forensics, "capture_com_failure", forbidden_native_diagnostic
    )
    source = tmp_path / "supplier.SLDPRT"
    source.write_bytes(b"offline supplier bytes")
    first = _ReferenceInkView(((0.002, 0.003), (0.015, 0.004)), name="front")
    installed = _sibling_view(first, "installed", "Installed")
    harness = reference_scene(views={"free_front": first, "installed_iso": installed})
    harness.model.path = source.resolve()
    for view in harness.views.values():
        view.referenced_path = source.resolve()
    # The application's document lookup was constructed before the tmp path
    # was assigned. Re-register only these fake documents; never open a seat.
    harness.adapter.swApp.documents = {
        harness.model.GetTitle(): harness.model,
        harness.draw.GetTitle(): harness.draw,
    }
    events, callbacks = [], []
    sheet = SimpleNamespace(
        GetProperties2=lambda: (0, 0, 1.0, 1.0, False, 0.43, 0.28, False),
        SetProperties2=lambda *_args: None,
    )
    harness.adapter._get_attr_or_call = lambda obj, name: getattr(obj, name)()

    def open_readonly(adapter, path, *, label):
        assert path == source and label == "supplier"
        events.append("open")
        adapter.currentModel = harness.model
        return harness.model

    def drawing(_adapter, *, layout, unit):
        events.append("drawing")
        harness.adapter.currentModel = harness.draw
        return harness.draw, sheet

    placed = iter((first, installed))

    def place(_adapter, path, orientation, x, y, *, scale):
        assert path == str(source)
        view = next(placed)
        view.Position = (x, y)
        view.ScaleRatio = scale
        return view

    def prepare(_adapter, views, *, reference_bounds):
        events.append("prepare")
        callbacks.append(reference_bounds)
        with pytest.raises(RuntimeError, match="capture is not ready"):
            reference_bounds("free_front")
        if dirty_stage == "prepare":
            harness.model.dirty = True

        def ready():
            events.append("prepared-check")
            reference_bounds("free_front")

        return (ready,)

    def fit(_draw, members, *, read_bounds):
        events.append("fit")
        assert harness.model.active == "Installed"
        if read_bounds is not None:
            for view, cell in members:
                read_bounds(view, cell[0])
        # No exception here: the final pre-presentation clean assertion must
        # catch this rather than entering a native failure-diagnostic path.
        if dirty_stage == "fit":
            harness.model.dirty = True
        return (1, 1)

    class PresentationReached(Exception):
        pass

    def dimensions(_adapter, views, *, reference_bounds):
        events.append("dimensions")
        assert reference_bounds is callbacks[0]
        assert harness.model.dirty is False
        assert harness.model.active == "Installed"
        reference_bounds("free_front")
        harness.model.dirty = True  # Expected native SetText presentation effect.
        reference_bounds("free_front")
        assert harness.model.dirty is True
        assert harness.model.read_only is True
        raise PresentationReached

    monkeypatch.setattr(
        supplier_drawing, "_open_supplier_source_read_only", open_readonly
    )
    monkeypatch.setattr(
        supplier_drawing,
        "read_required_properties",
        lambda *_args, **_kw: {
            "Material Specification": "Steel",
            "Finish": "None",
            "Manufacturing Notes": "",
            "Title": "Supplier",
            "Supplier": "Vendor",
            "Supplier SKUs": "SKU",
        },
    )
    monkeypatch.setattr(supplier_drawing, "check_item", lambda *_args, **_kw: None)
    monkeypatch.setattr(supplier_drawing, "new_project_drawing", drawing)
    monkeypatch.setattr(
        supplier_drawing, "_purchased_title_block", lambda *_args, **_kw: ()
    )
    monkeypatch.setattr(
        supplier_drawing, "stamp_drawing_summary", lambda *_args, **_kw: None
    )
    monkeypatch.setattr(supplier_drawing, "place_view", place)
    monkeypatch.setattr(
        supplier_drawing, "set_hidden_lines_removed", lambda *_args: None
    )
    monkeypatch.setattr(supplier_drawing, "double_array", tuple)
    monkeypatch.setattr(supplier_drawing, "_fit_group", fit)
    monkeypatch.setattr(
        supplier_drawing,
        "_center_marks_without_lines",
        lambda _views, cells: {key: 0 for key, _, _ in cells},
    )
    monkeypatch.setattr(
        supplier_drawing, "assert_asme_b_sheet", lambda *_args, **_kw: None
    )
    spec = SimpleNamespace(
        source=source, source_kind="part", artifact_stem="supplier", layout="test"
    )
    expected_error = (
        PresentationReached if dirty_stage == "presentation" else RuntimeError
    )
    with pytest.raises(expected_error):
        asyncio.run(
            supplier_drawing.build_supplier_spring_drawing(
                harness.adapter,
                spec,
                item="1",
                supplier_dimensions=dimensions,
                prepare_views=prepare,
                supplier_margins={"free_front": _EXTENSION_MARGINS["free_front"]},
                supplier_reference_features={"free_front": ("SupplierSection",)},
                stock_configuration="SupplierReference",
                include_right=False,
                include_top=False,
                spring_metadata=True,
            )
        )
    assert events[:3] == ["open", "drawing", "prepare"]
    assert ("dimensions" in events) is (dirty_stage == "presentation")
    assert ("prepared-check" in events) is (dirty_stage != "prepare")
    assert ("fit" in events) is (dirty_stage != "prepare")
    assert harness.model.dirty is True
    assert source.read_bytes() == b"offline supplier bytes"


@pytest.mark.parametrize("missing", [False, True], ids=["extra-segment", "missing-sketch"])
def test_reference_projection_rejects_additional_drawing_sketch_ink(reference_scene, missing):
    harness = reference_scene()
    if missing:
        harness.view.GetSketch = lambda: None
    else:
        harness.view.drawing_segments.append(object())
    harness.capture()
    with pytest.raises(RuntimeError, match="drawing-sketch geometry"):
        harness.project()
