"""Thumb supplier lane regressions at the native boundary, without COM.

The recorded abe9 thread-length ink crossed its 77 mm cell floor by
7.5895 mm. Synthetic display primitives below exercise the unchanged real
ink guard; they are not evidence of a successful native rerender.
"""

from __future__ import annotations

from math import isclose
from types import SimpleNamespace

import pytest

import _purchased_fastener_drawing as purchased
import draw_sh_vn_thumb_screw as thumb


class _ThumbView:
    """Exact supplier envelope plus 1 mm fixed synthetic native padding."""

    PADDING = 0.001

    def __init__(self, center):
        self.Position = tuple(center)
        self.ScaleRatio = (1.0, 1.0)
        self.UseSheetScale = 0
        self.displays = []

    def GetOrientationName(self):
        return "*Front"

    def GetOutline(self):
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        x, y = self.Position
        radius = thumb.supplier.HEAD_DIA / 2000.0 * ratio
        return (
            x - self.PADDING,
            y - radius - self.PADDING,
            x + thumb.supplier.OVERALL_LEN / 1000.0 * ratio + self.PADDING,
            y + radius + self.PADDING,
        )

    def SetViewPosition(self, position, _update):
        self.Position = tuple(position)
        return True

    def UpdateViewDisplayGeometry(self):
        pass

    def GetFirstDisplayDimension6(self):
        return self.displays[0] if self.displays else None

    def GetAnnotations(self):
        return ()

    def project(self, point):
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        return tuple(origin + value * ratio for origin, value in zip(self.Position, point))


def _fitted_front(monkeypatch, notes=""):
    monkeypatch.setattr(purchased, "double_array", tuple)
    cell = next(
        row for row in purchased.fastener_view_cells(
            purchased.view_band_bottom(notes, label="thumb regression")
        ) if row[0] == "*Front"
    )
    fit = purchased.supplier_fit_cells((cell,), thumb.SUPPLIER_MARGINS, label="thumb regression")[0]
    view = _ThumbView(cell[1])
    draw = SimpleNamespace(EditRebuild3=lambda: True)
    scale = purchased._fit_group(draw, [(view, fit)])
    return view, cell[2], fit[2], scale


def test_thumb_prefit_budget_intentionally_rejects_five_to_one(monkeypatch):
    view, outer, inner, scale = _fitted_front(monkeypatch)
    assert outer == pytest.approx((0.025, 0.077, 0.205, 0.182))
    assert thumb.SUPPLIER_MARGINS["*Front"] == pytest.approx((0.034, 0.024, 0.045, 0.034))
    # Independent exact-size calculation, not a remembered chosen scale:
    # 105 - 24 - 34 = 47 mm, less than the bare 47.625 mm head at 5:1.
    available = inner[3] - inner[1]
    assert available == pytest.approx(0.047)
    assert thumb.supplier.HEAD_DIA / 1000.0 * 5 > available
    assert scale == (4, 1)
    assert view.GetOutline()[1] >= inner[1]
    assert view.GetOutline()[3] <= inner[3]


@pytest.mark.parametrize("notes", ("", "FIRST\nSECOND\nTHIRD"))
def test_thumb_positions_use_fitted_outline_and_actual_caption_floor(monkeypatch, notes):
    view, cell, _inner, _scale = _fitted_front(monkeypatch, notes)
    stations = (0.0, thumb.supplier.HEAD_H, thumb.supplier.HEAD_STACK_LEN, thumb.supplier.OVERALL_LEN)
    axis = [view.project((value / 1000.0, 0.0)) for value in stations]
    outline = view.GetOutline()
    positions = thumb._supplier_positions(outline, axis)
    assert positions["SupplierThreadLength"][1] == pytest.approx(outline[1] - 0.010)
    assert positions["SupplierHeadHeight"][1] == pytest.approx(outline[3] + 0.009)
    assert positions["SupplierCollarHeight"][1] == pytest.approx(outline[3] + 0.020)
    assert positions["SupplierHeadDiameter"][0] == pytest.approx(outline[0] - 0.020)
    assert positions["SupplierCollarDiameter"][0] == pytest.approx(outline[2] + 0.027)
    assert positions["SupplierThreadDiameter"][0] == pytest.approx(outline[2] + 0.012)
    assert cell[1] < positions["SupplierThreadLength"][1] < outline[1]
    assert outline[3] < positions["SupplierCollarHeight"][1] < cell[3]


class _NativeDimension:
    def __init__(self, name, owner, value_mm):
        self.Name = name
        self.owner = owner
        self.SystemValue = value_mm / 1000.0
        self.Tolerance = SimpleNamespace(Type=0)

    @property
    def FullName(self):
        return f"{self.Name}@{self.owner}@sh-vn-thumb-screw.SLDPRT"


class _NativeDisplay:
    def __init__(self, state, name, owner, value_mm, points, entities, orientation):
        self.state = state
        self.native = _NativeDimension(name, owner, value_mm)
        self.points = points
        self.entities = entities
        self.orientation = orientation
        self.position = (0.12, 0.125, 0.0)
        self.line_position = self.position
        self.OffsetText = True
        self.OwnerType = 0
        self.Owner = state.view
        self.Visible = 1
        self.ShowDimensionValue = True

    def GetDimension2(self, index):
        assert index == 0
        return self.native

    def GetAnnotation(self):
        return self

    def GetSpecificAnnotation(self):
        return self

    def GetPosition(self):
        return self.position

    def SetPosition2(self, x, y, z):
        self.state.events.append(("place", self.native.Name, self.OffsetText))
        if self.state.defect == "refused":
            return False
        if self.state.defect != "ignored":
            self.position = (x, y, z)
        if not self.OffsetText and self.state.defect not in ("ignored", "stale-lines"):
            self.line_position = self.position
        return True

    def GetNext5(self):
        siblings = self.state.view.displays
        index = siblings.index(self) + 1
        return siblings[index] if index < len(siblings) else None

    def GetAttachedEntities3(self):
        return self.entities

    def IsDangling(self):
        return False

    def GetOverride(self):
        return False


def _line(a, b):
    return [0, 0, 0, 0, *a, 0.0, *b, 0.0]


def _display_ink(_adapter, display):
    """Independent text and whole-line state: moving text alone cannot pass."""
    x, y, _ = display.position
    lx, ly, _ = display.line_position
    a, b = display.points
    if display.orientation == "horizontal":
        lines = (_line(a, (a[0], ly)), _line((a[0], ly), (b[0], ly)), _line((b[0], ly), b))
    else:
        lines = (_line(a, (lx, a[1])), _line((lx, a[1]), (lx, b[1])), _line((lx, b[1]), b))
    return {
        "texts": [{"t": "(0.438 in)", "pos": (x, y, 0.0), "h": 0.003, "w": 0.018, "ang": 0.0, "ref": 2}],
        "lines": lines,
    }, {}


@pytest.fixture
def native_thumb(monkeypatch):
    view, cell, _inner, _scale = _fitted_front(monkeypatch)
    state = SimpleNamespace(view=view, cell=cell, defect=None, events=[], authored=[])
    state.adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    source_pose = (view.Position, view.ScaleRatio, view.GetOutline())
    stations = (0.0, thumb.supplier.HEAD_H, thumb.supplier.HEAD_STACK_LEN, thumb.supplier.OVERALL_LEN)
    edges = []
    for station in stations:
        params = (station / 1000.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.001)
        curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=params)
        edge = SimpleNamespace(station=station, GetCurve=lambda curve=curve: curve)
        edges.append(SimpleNamespace(edge=edge, circle=(station, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0)))

    for module in (thumb, purchased):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(thumb, "iter_views", lambda _adapter: (view,))
    monkeypatch.setattr(thumb, "model_points_in_view", lambda _adapter, _view, points, **_kwargs: [view.project(point[:2]) for point in points])
    monkeypatch.setattr(thumb, "scan_view_edges", lambda *_args, **_kwargs: SimpleNamespace(circles=edges))
    monkeypatch.setattr(thumb._config, "parts", lambda _name: {"installation_notes": ""})
    monkeypatch.setattr(thumb, "dimension_name", lambda _adapter, annotation: annotation.native.Name)
    monkeypatch.setattr(purchased, "annotation_display", _display_ink)

    def author(_adapter, _view, **options):
        entities = options["entities"]
        value = abs(entities[1].station - entities[0].station)
        display = _NativeDisplay(state, "unnamed", "Drawing View1", value, (options["p0"], options["p1"]), entities, options["orientation"])
        display.position = (*options["text_xy"], 0.0)
        display.line_position = display.position
        view.displays.append(display)
        state.authored.append((display, options))
        return display

    def measured(_adapter, display, *, expected_mm, entities, **_kwargs):
        assert entities == display.entities
        assert abs(entities[1].station - entities[0].station) == pytest.approx(expected_mm)
        assert display.native.SystemValue * 1000.0 == pytest.approx(expected_mm)

    def present(_adapter, display, **options):
        assert display.native.SystemValue * 1000.0 == pytest.approx(options["expected_mm"])
        state.events.append(("format", display.native.Name))
        return display

    def curate(_adapter, _view, *, keep, **_kwargs):
        # The native import/delete/rebuild comes AFTER physical dimension drops.
        # Retain the observed bad thread baseline until an explicit full-line move.
        thread = next(item for item in view.displays if item.native.Name == "SupplierThreadLength")
        thread.position = (thread.position[0], 0.0694105, 0.0)
        thread.line_position = thread.position
        state.events.append(("import-reflow",))
        result = []
        for name, diameter, _orientation in thumb.supplier.DIAMETER_REFERENCES:
            x, y = thumb.supplier.DIAMETER_REFERENCE_STARTS[name]
            points = (view.project((x / 1000.0, y / 1000.0)), view.project((x / 1000.0, (y + diameter) / 1000.0)))
            display = _NativeDisplay(state, name, "SupplierReference", diameter, points, (object(), object()), "vertical")
            display.position = (*keep[name], 0.0)
            display.line_position = display.position
            view.displays.append(display)
            result.append(display)
        return result

    def rebuild(_adapter, *, label):
        state.events.append(("rebuild", label))
        assert (view.Position, view.ScaleRatio, view.GetOutline()) == source_pose

    monkeypatch.setattr(thumb, "add_edge_dimension", author)
    monkeypatch.setattr(thumb, "assert_dimension_measures", measured)
    monkeypatch.setattr(thumb, "supplier_reference_dimension", present)
    monkeypatch.setattr(thumb, "assert_supplier_reference_dimension", present)
    monkeypatch.setattr(thumb, "curate_view_dimensions", curate)
    monkeypatch.setattr(thumb, "rebuild_drawing", rebuild)
    state.source_pose = source_pose
    return state


def test_thumb_reseats_complete_native_lines_after_import_and_formatting(native_thumb):
    state = native_thumb
    positions = thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    events = state.events
    first_placement = next(index for index, event in enumerate(events) if event[0] == "place")
    assert sum(event[0] == "format" for event in events[:first_placement]) == 6
    assert any(event[0] == "import-reflow" for event in events[:first_placement])
    assert all(event[2] is False for event in events if event[0] == "place")
    assert events[-1] == ("rebuild", "thumb supplier complete native lanes")
    assert (state.view.Position, state.view.ScaleRatio, state.view.GetOutline()) == state.source_pose
    # Preserve the exact physical source rim pairs, not replacement dimensions.
    assert [tuple(edge.station for edge in options["entities"]) for _display, options in state.authored] == [
        (0.0, 2.38125), (2.38125, 4.7625), (4.7625, 15.875),
    ]
    assert [display.native.SystemValue * 1000.0 for display, _options in state.authored] == pytest.approx([2.38125, 2.38125, 11.1125])
    thumb._assert_supplier_dimensions(state.adapter, positions)


@pytest.mark.parametrize("defect", ("refused", "ignored", "stale-lines"))
def test_thumb_refuses_unmoved_text_or_dimension_lines(native_thumb, defect):
    state = native_thumb
    state.defect = defect
    with pytest.raises(RuntimeError, match="failed to place|left its lane|leaves its cell/caption"):
        thumb.supplier_dimensions(state.adapter, {"*Front": state.view})


def test_thumb_final_readback_refuses_post_authoring_lane_drift(native_thumb):
    state = native_thumb
    positions = thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    display = next(item for item in state.view.displays if item.native.Name == "SupplierThreadLength")
    x, y, z = display.position
    display.position = (x, y - 0.0001, z)
    with pytest.raises(RuntimeError, match="settled thumb supplier dimension left its lane"):
        thumb._assert_supplier_dimensions(state.adapter, positions)
    assert isclose(display.native.SystemValue * 1000.0, 11.1125, abs_tol=1e-12)
