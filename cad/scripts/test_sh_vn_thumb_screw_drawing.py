"""Thumb supplier lane regressions at the native boundary, without COM.

The recorded abe9 thread-length ink crossed its 77 mm cell floor by
7.5895 mm. Native 9aae then passed containment at 2:1 but printed two
overlapping .094 spans. Synthetic display primitives exercise the real ink
and path guards below; they are not evidence of a successful native rerender.
Native 34eb subsequently refused a station transition without numeric evidence;
these synthetic failures require full before/after data and live-sheet capture,
not a relaxed station tolerance or a claimed native layout fix.
Native 012dd showed that enabling offset mode relocates its line to the prior
annotation anchor, which is above the text baseline by a measured font offset.
The primitive fixture models that transition independently of text-only moves.
"""

from __future__ import annotations

import asyncio
import json
from math import isclose
from types import SimpleNamespace

import pytest

import _drawing_layout_audit as native_audit
from _drawing_layout_check import DrawableRegion
import _purchased_fastener_drawing as purchased
import draw_sh_vn_thumb_screw as thumb


class _ThumbView:
    """Supplier envelope plus the fixed native outline padding read on 9aae."""

    X_PADDING = 0.0058302
    Y_PADDING = 0.0057014

    def __init__(self, center):
        self.Position = tuple(center)
        self.ScaleRatio = (1.0, 1.0)
        self.UseSheetScale = 0
        self.displays = []

    def GetOrientationName(self):
        return "*Front"

    def GetName2(self):
        return "Drawing View1"

    def GetOutline(self):
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        x, y = self.Position
        radius = thumb.supplier.HEAD_DIA / 2000.0 * ratio
        return (
            x - self.X_PADDING,
            y - radius - self.Y_PADDING,
            x + thumb.supplier.OVERALL_LEN / 1000.0 * ratio + self.X_PADDING,
            y + radius + self.Y_PADDING,
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
        return tuple(
            origin + value * ratio for origin, value in zip(self.Position, point)
        )


def _fitted_front(monkeypatch, notes=""):
    monkeypatch.setattr(purchased, "double_array", tuple)
    cell = next(
        row
        for row in purchased.fastener_view_cells(
            purchased.view_band_bottom(notes, label="thumb regression")
        )
        if row[0] == "*Front"
    )
    fit = purchased.supplier_fit_cells(
        (cell,), thumb.SUPPLIER_MARGINS, label="thumb regression"
    )[0]
    view = _ThumbView(cell[1])
    draw = SimpleNamespace(EditRebuild3=lambda: True)
    scale = purchased._fit_group(draw, [(view, fit)])
    return view, cell[2], fit[2], scale


def test_thumb_prefit_reserves_native_text_and_intentionally_chooses_four_to_one(
    monkeypatch,
):
    view, outer, inner, scale = _fitted_front(monkeypatch)
    assert outer == pytest.approx((0.025, 0.077, 0.205, 0.182))
    assert thumb.SUPPLIER_MARGINS["*Front"] == pytest.approx(
        (0.0345, 0.016, 0.0665, 0.020)
    )
    # The outer diameter line must clear the inner native text as well as
    # reserving its own text. Include fixed padding rather than scaling it.
    available_width, available_height = inner[2] - inner[0], inner[3] - inner[1]
    assert available_width == pytest.approx(0.079)
    assert available_height == pytest.approx(0.069)
    assert (
        thumb.supplier.OVERALL_LEN / 1000.0 * 4 + 2 * view.X_PADDING < available_width
    )
    assert (
        thumb.supplier.OVERALL_LEN / 1000.0 * 5 + 2 * view.X_PADDING > available_width
    )
    assert scale == (4, 1)
    assert view.GetOutline()[1] >= inner[1]
    assert view.GetOutline()[3] <= inner[3]


@pytest.mark.parametrize("notes", ("", "FIRST\nSECOND\nTHIRD"))
def test_thumb_positions_use_fitted_outline_and_actual_caption_floor(
    monkeypatch, notes
):
    view, cell, _inner, _scale = _fitted_front(monkeypatch, notes)
    stations = (
        0.0,
        thumb.supplier.HEAD_H,
        thumb.supplier.HEAD_STACK_LEN,
        thumb.supplier.OVERALL_LEN,
    )
    axis = [view.project((value / 1000.0, 0.0)) for value in stations]
    outline = view.GetOutline()
    positions = thumb._supplier_positions(outline, axis)
    assert positions["SupplierThreadLength"][1] == pytest.approx(outline[3] + 0.016)
    assert positions["SupplierHeadHeight"][1] == pytest.approx(outline[1] - 0.008)
    assert positions["SupplierCollarHeight"][1] == pytest.approx(outline[3] + 0.006)
    assert positions["SupplierHeadDiameter"][0] == pytest.approx(outline[0] - 0.020)
    assert positions["SupplierCollarDiameter"][0] == pytest.approx(outline[2] + 0.040)
    assert positions["SupplierThreadDiameter"][0] == pytest.approx(outline[2] + 0.012)
    assert cell[1] < positions["SupplierHeadHeight"][1] < outline[1]
    assert (
        outline[3]
        < positions["SupplierCollarHeight"][1]
        < positions["SupplierThreadLength"][1]
        < cell[3]
    )
    assert positions["SupplierThreadDiameter"][1] == pytest.approx(axis[0][1])


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
        self._offset_text = True
        self._pending_offset_anchor = False
        self.OwnerType = 0
        self.Owner = state.view
        self.Visible = 1
        self.ShowDimensionValue = True
        self.Layer = ""
        self.SmartWitness = state.defect == "mode-witness-tail"
        self.ArrowSide = 0
        self.LeaderVisibility = 0
        self.MaxWitnessLineLength = 0.05

    @property
    def OffsetText(self):
        return self._offset_text

    @OffsetText.setter
    def OffsetText(self, enabled):
        if not enabled:
            self._pending_offset_anchor = False
        elif not self._offset_text and self.orientation == "horizontal":
            # 012dd observed the transition only after toggle + same-point
            # SetPosition2. Exercise either possible snap point, then freeze the
            # line for later text-only moves. Physical rim starts/X never move.
            if self.state.offset_anchor_phase == "toggle":
                x, y, z = self.position
                self.line_position = (x, y + self.text_line_offset, z)
            else:
                self._pending_offset_anchor = True
        self._offset_text = enabled

    @property
    def text_line_offset(self):
        return self.state.text_line_offsets.get(self.native.Name, 0.0027781)

    def GetWitnessLineGap(self, index, use_doc, gap):
        assert index in (0, 1)
        assert type(use_doc) is bool and type(gap) is float
        if self.state.defect == "witness-policy-refusal":
            return False, False, 0.0
        return True, True, 0.001

    def GetType(self):
        return 4

    def GetName(self):
        return self.native.Name

    def IsHoleCallout(self):
        return False

    def GetDisplayData(self):
        return self

    def GetLeaderCount(self):
        # Native 012dd reports NoLeader: the connector/underline exist ONLY as
        # display-data lines, not as registered IAnnotation leaders.
        return 0

    def offset_path_points(self):
        override = self.state.native_path_overrides.get(self.native.Name)
        if override is not None:
            return override
        x, y, _ = self.position
        baseline = self.line_position[1] - self.text_line_offset
        center = sum(point[0] for point in self.points) / 2
        left = x + self.state.text_mode_shift - 0.0227354 / 2
        return (
            (center, baseline),
            (left, y - self.text_line_offset),
            (left + 0.0227354, y - self.text_line_offset),
        )

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
        if self.state.defect == "refused":
            return False
        if self.state.defect != "ignored" and not (
            self.state.defect == "ignored-shelf" and self.OffsetText
        ):
            self.position = (x, y, z)
        if not self.OffsetText and self.state.defect not in ("ignored", "stale-lines"):
            self.line_position = self.position
        if self.OffsetText and self._pending_offset_anchor:
            self.line_position = (x, y + self.text_line_offset, z)
            self._pending_offset_anchor = False
        if self.OffsetText and (
            self.state.defect == "mode-line-drift"
            or (
                self.state.defect == "shelf-line-drift"
                and abs(x - self.line_position[0]) > 0.001
            )
        ):
            lx, ly, lz = self.line_position
            self.line_position = (lx, ly + 0.0001, lz)
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
    """Native-shaped lines/text, with independently moving text and witnesses."""
    x, y, _ = display.position
    lx, ly, _ = display.line_position
    name = display.native.Name
    a, b = display.points
    if name in thumb._AXIAL_NAMES and display.OffsetText:
        x += display.state.text_mode_shift
    arrows = []
    if display.orientation == "horizontal":
        width, height = 0.0227354, 0.0035
        text = " (0.438 in) " if name == "SupplierThreadLength" else " (0.094 in) "
        baseline = ly - display.text_line_offset
        outward = 1 if baseline > a[1] else -1
        lines = [
            _line(a, (a[0], baseline + outward * 0.001)),
            _line(b, (b[0], baseline + outward * 0.001)),
        ]
        if display.OffsetText and display.state.defect == "mode-witness-tail":
            lines[0][-2] += outward * 0.0001
        outside = b[0] - a[0] < width + 0.007112
        if outside:
            lines.extend(
                (
                    _line(
                        (a[0], baseline),
                        (a[0] - 0.00635 - display.state.tail_extra, baseline),
                    ),
                    _line(
                        (b[0], baseline),
                        (b[0] + 0.00635 + display.state.tail_extra, baseline),
                    ),
                )
            )
        # Native 012dd retains the central run even with both arrows outside.
        lines.append(_line((a[0], baseline), (b[0], baseline)))
        for point, direction in ((a, -1 if outside else 1), (b, 1 if outside else -1)):
            if display.OffsetText:
                direction = -direction  # Native smart-arrow direction may change.
            arrows.append(
                [
                    point[0],
                    baseline,
                    0.0,
                    direction,
                    0.0,
                    0.0,
                    0.003556,
                    0.000762,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ]
            )
        if display.OffsetText and display.state.defect == "mode-arrow-inventory":
            arrows.append(list(arrows[0]))
        texts = [
            {
                "t": text,
                "pos": (x - width / 2, y - display.text_line_offset, 0.0),
                "h": height,
                "w": width,
                "ang": 0.0,
                "ref": 1,
            }
        ]
    else:
        width = 0.0280138 if name == "SupplierHeadDiameter" else 0.0254278
        left = x - width / 2 if name == "SupplierHeadDiameter" else x
        texts = [
            {
                "t": "<MOD-DIAM>0.375 in",
                "pos": (left, y - 0.0027781, 0.0),
                "h": 0.0035,
                "w": width,
                "ang": 0.0,
                "ref": 1,
            }
        ]
        if name == "SupplierThreadDiameter":
            texts = [
                {
                    "t": "<MOD-DIAM>0.112 in",
                    "pos": (left, y + 0.0000267, 0.0),
                    "h": 0.0035,
                    "w": width,
                    "ang": 0.0,
                    "ref": 1,
                },
                {
                    "t": "4-40",
                    "pos": (left + 0.0080594, y - 0.005583, 0.0),
                    "h": 0.0035,
                    "w": 0.009309,
                    "ang": 0.0,
                    "ref": 1,
                },
            ]
        low = min(row["pos"][1] for row in texts) - 0.0005
        high = max(row["pos"][1] + row["h"] for row in texts) + 0.0005
        lines = [
            _line(a, (lx + 0.001, a[1])),
            _line(b, (lx + 0.001, b[1])),
        ]
        if a[1] < low:
            lines.append(_line((lx, a[1]), (lx, low)))
        if b[1] > high:
            lines.append(_line((lx, high), (lx, b[1])))
        for point, direction in ((a, 1), (b, -1)):
            arrows.append(
                [
                    lx,
                    point[1],
                    0.0,
                    0.0,
                    direction,
                    0.0,
                    0.003556,
                    0.000762,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ]
            )
    if display.OffsetText and name in thumb._AXIAL_NAMES:
        points = display.offset_path_points()
        lines.extend(_line(a, b) for a, b in zip(points, points[1:]))
        if display.state.defect == "merged-offset-tail" and x < a[0] - 0.01:
            # Native post-shelf topology is unobserved: refuse a hypothetical
            # single merged physical tail that actually reaches the text.
            lines.append(_line((a[0], baseline), points[1]))
    return {"texts": texts, "lines": lines, "arrows": arrows}, {}


@pytest.fixture
def native_thumb(monkeypatch, request):
    scale, notes = getattr(request, "param", ((4, 1), ""))
    monkeypatch.setattr(purchased, "_SCALES", (scale,))
    view, cell, _inner, _scale = _fitted_front(monkeypatch, notes)
    state = SimpleNamespace(
        view=view,
        cell=cell,
        defect=None,
        authored=[],
        text_mode_shift=0.004,
        tail_extra=0.0,
        native_path_overrides={},
        other_views=[],
        native_transitions=[],
        offset_anchor_phase="toggle",
        text_line_offsets={
            "SupplierHeadHeight": 0.0027781,
            "SupplierCollarHeight": 0.0027782,
            "SupplierThreadLength": 0.0027782,
        },
    )
    state.adapter = SimpleNamespace(
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b))
    )
    constants = {"swDetailingWitnessLineGap": 1, "swDetailingNoOptionSpecified": 0}
    monkeypatch.setattr(
        thumb, "sw_type_info", SimpleNamespace(constant=constants.__getitem__)
    )

    def document_gap(preference, option):
        assert preference == constants["swDetailingWitnessLineGap"]
        assert option == constants["swDetailingNoOptionSpecified"]
        return 0.001

    state.adapter.currentModel = SimpleNamespace(
        Extension=SimpleNamespace(GetUserPreferenceDouble=document_gap)
    )

    def native_log(message, **_kwargs):
        prefix = "thumb_supplier_native_geometry_transition "
        if message.startswith(prefix):
            state.native_transitions.append(json.loads(message.removeprefix(prefix)))

    monkeypatch.setattr(thumb._telemetry, "info", native_log)
    source_pose = (view.Position, view.ScaleRatio, view.GetOutline())
    stations = (
        0.0,
        thumb.supplier.HEAD_H,
        thumb.supplier.HEAD_STACK_LEN,
        thumb.supplier.OVERALL_LEN,
    )
    edges = []
    for station in stations:
        params = (station / 1000.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.001)
        curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=params)
        edge = SimpleNamespace(station=station, GetCurve=lambda curve=curve: curve)
        edges.append(
            SimpleNamespace(edge=edge, circle=(station, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0))
        )

    for module in (thumb, purchased, native_audit):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        thumb, "iter_views", lambda _adapter: (view, *state.other_views)
    )
    monkeypatch.setattr(
        thumb,
        "model_points_in_view",
        lambda _adapter, _view, points, **_kwargs: [
            view.project(point[:2]) for point in points
        ],
    )
    monkeypatch.setattr(
        thumb,
        "scan_view_edges",
        lambda *_args, **_kwargs: SimpleNamespace(circles=edges),
    )
    monkeypatch.setattr(
        thumb._config, "parts", lambda _name: {"installation_notes": notes}
    )
    monkeypatch.setattr(
        thumb, "dimension_name", lambda _adapter, annotation: annotation.native.Name
    )
    monkeypatch.setattr(purchased, "annotation_display", _display_ink)
    # Exercise the real annotation collector, including native leader getters;
    # only the IDisplayData primitive accessor boundary is synthetic.
    monkeypatch.setattr(
        native_audit,
        "_dump_display",
        lambda _reader, display: _display_ink(None, display)[0],
    )
    monkeypatch.setattr(thumb, "sheet_region", lambda _adapter: DrawableRegion(*cell))

    def author(_adapter, _view, **options):
        entities = options["entities"]
        value = abs(entities[1].station - entities[0].station)
        display = _NativeDisplay(
            state,
            "unnamed",
            "Drawing View1",
            value,
            (options["p0"], options["p1"]),
            entities,
            options["orientation"],
        )
        display.position = (*options["text_xy"], 0.0)
        display.line_position = display.position
        view.displays.append(display)
        state.authored.append((display, options))
        return display

    def measured(_adapter, display, *, expected_mm, entities, **_kwargs):
        assert entities == display.entities
        assert abs(entities[1].station - entities[0].station) == pytest.approx(
            expected_mm
        )
        assert display.native.SystemValue * 1000.0 == pytest.approx(expected_mm)

    def present(_adapter, display, **options):
        assert display.native.SystemValue * 1000.0 == pytest.approx(
            options["expected_mm"]
        )
        return display

    def curate(_adapter, _view, *, keep, **_kwargs):
        # The native import/delete/rebuild comes AFTER physical dimension drops.
        # Retain the observed bad thread baseline until an explicit full-line move.
        thread = next(
            item for item in view.displays if item.native.Name == "SupplierThreadLength"
        )
        thread.position = (thread.position[0], 0.0694105, 0.0)
        thread.line_position = thread.position
        result = []
        for name, diameter, _orientation in thumb.supplier.DIAMETER_REFERENCES:
            x, y = thumb.supplier.DIAMETER_REFERENCE_STARTS[name]
            points = (
                view.project((x / 1000.0, y / 1000.0)),
                view.project((x / 1000.0, (y + diameter) / 1000.0)),
            )
            display = _NativeDisplay(
                state,
                name,
                "SupplierReference",
                diameter,
                points,
                (object(), object()),
                "vertical",
            )
            display.position = (*keep[name], 0.0)
            display.line_position = display.position
            view.displays.append(display)
            result.append(display)
        return result

    def rebuild(_adapter, *, label):
        assert (view.Position, view.ScaleRatio, view.GetOutline()) == source_pose

    monkeypatch.setattr(thumb, "add_edge_dimension", author)
    monkeypatch.setattr(thumb, "assert_dimension_measures", measured)
    monkeypatch.setattr(thumb, "supplier_reference_dimension", present)
    monkeypatch.setattr(thumb, "assert_supplier_reference_dimension", present)
    monkeypatch.setattr(thumb, "curate_view_dimensions", curate)
    monkeypatch.setattr(thumb, "rebuild_drawing", rebuild)
    state.source_pose = source_pose
    return state


@pytest.mark.parametrize(
    "native_thumb", [((4, 1), ""), ((2, 1), "FIRST\nSECOND\nTHIRD")], indirect=True
)
def test_thumb_settled_native_geometry_and_drawn_offset_paths_remain_clear(
    native_thumb,
):
    state = native_thumb
    positions, short_geometry = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    for display in state.view.displays:
        if short_geometry.get(display.native.Name, {}).get("shelved"):
            assert display.OffsetText is True
            record = thumb._supplier_annotation_record(state.adapter, display)
            assert "leaders" not in record
            drawn = [thumb.line_segment(row) for row in record["display"]["lines"]]
            for start, end in zip(
                display.offset_path_points(), display.offset_path_points()[1:]
            ):
                assert any(
                    segment is not None
                    and (segment.x0, segment.y0) == pytest.approx(start)
                    and (segment.x1, segment.y1) == pytest.approx(end)
                    for segment in drawn
                )
            assert display.line_position[0] > display.position[0]
            assert display.line_position[1] == pytest.approx(display.position[1])
        else:
            assert display.OffsetText is False
    assert (
        thumb._diameter_text_gap(state.adapter, thumb._supplier_displays(state.adapter))
        >= 0.002
    )
    assert all(
        gap >= 0.002
        for gap in thumb._diameter_vertical_gaps(
            state.adapter, thumb._supplier_displays(state.adapter)
        )
    )
    assert short_geometry["SupplierThreadLength"]["shelved"] is (
        state.view.ScaleRatio == (2.0, 1.0)
    )
    assert (
        state.view.Position,
        state.view.ScaleRatio,
        state.view.GetOutline(),
    ) == state.source_pose
    # Preserve the exact physical source rim pairs, not replacement dimensions.
    assert {
        display.native.Name: tuple(edge.station for edge in options["entities"])
        for display, options in state.authored
    } == {
        "SupplierHeadHeight": (0.0, 2.38125),
        "SupplierCollarHeight": (2.38125, 4.7625),
        "SupplierThreadLength": (4.7625, 15.875),
    }
    assert {
        display.native.Name: display.native.SystemValue * 1000.0
        for display, _options in state.authored
    } == pytest.approx(
        {
            "SupplierHeadHeight": 2.38125,
            "SupplierCollarHeight": 2.38125,
            "SupplierThreadLength": 11.1125,
        }
    )
    thumb._assert_supplier_dimensions(state.adapter, positions, short_geometry)


@pytest.mark.parametrize(
    "defect", ("refused", "ignored", "ignored-shelf", "stale-lines", "mode-line-drift")
)
def test_thumb_refuses_unmoved_text_or_dimension_lines(native_thumb, defect):
    state = native_thumb
    state.defect = defect
    with pytest.raises(
        RuntimeError,
        match="failed to place|left its lane|leaves its cell/caption|axial text crowds|witness/arrow station moved|collar witness",
    ):
        thumb.supplier_dimensions(state.adapter, {"*Front": state.view})


def test_thumb_final_readback_refuses_post_authoring_lane_drift(native_thumb):
    state = native_thumb
    positions, short_geometry = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    display = next(
        item
        for item in state.view.displays
        if item.native.Name == "SupplierThreadLength"
    )
    x, y, z = display.position
    display.position = (x, y - 0.0001, z)
    with pytest.raises(
        RuntimeError, match="settled thumb supplier dimension left its lane"
    ):
        thumb._assert_supplier_dimensions(state.adapter, positions, short_geometry)
    assert isclose(display.native.SystemValue * 1000.0, 11.1125, abs_tol=1e-12)


def test_thumb_native_path_guard_rejects_centered_short_text_crossed_by_witness(
    native_thumb,
):
    state = native_thumb
    thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    outline = state.view.GetOutline()
    for display in state.view.displays:
        if display.native.Name in ("SupplierHeadHeight", "SupplierCollarHeight"):
            center_x = sum(point[0] for point in display.points) / 2
            above = 0.009 if display.native.Name == "SupplierHeadHeight" else 0.020
            display.OffsetText = False
            display.SetPosition2(center_x, outline[3] + above, 0.0)
    with pytest.raises(
        RuntimeError, match="thumb supplier dimension paths are not clear"
    ):
        thumb._assert_supplier_paths(
            state.adapter, thumb._supplier_displays(state.adapter)
        )


@pytest.mark.parametrize(
    "native_thumb", [((4, 1), ""), ((2, 1), "FIRST\nSECOND\nTHIRD")], indirect=True
)
def test_thumb_measures_outer_line_spacing_after_native_formatting(
    native_thumb, monkeypatch
):
    state = native_thumb
    original = thumb._supplier_positions

    def tight_initial_lane(outline, axis):
        positions = original(outline, axis)
        _x, y = positions["SupplierCollarDiameter"]
        positions["SupplierCollarDiameter"] = (outline[2] + 0.027, y)
        return positions

    monkeypatch.setattr(thumb, "_supplier_positions", tight_initial_lane)
    positions, short_geometry = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    found = thumb._supplier_displays(state.adapter)
    assert thumb._diameter_text_gap(state.adapter, found) == pytest.approx(
        0.0022, abs=1e-7
    )
    thumb._assert_supplier_dimensions(state.adapter, positions, short_geometry)


@pytest.mark.parametrize(
    "native_thumb", [((4, 1), ""), ((2, 1), "FIRST\nSECOND\nTHIRD")], indirect=True
)
def test_thumb_native_audit_rejects_old_collar_line_through_thread_text(native_thumb):
    state = native_thumb
    thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    found = thumb._supplier_displays(state.adapter)
    thread_x = found["SupplierThreadDiameter"].GetPosition()[0]
    # Reproduce the old on-axis thread block as well as its too-tight outer
    # line; the measured layout now keeps this block below collar witnesses.
    thread = found["SupplierThreadDiameter"]
    thread.SetPosition2(thread_x, state.view.project((0.0, 0.0))[1], 0.0)
    collar = found["SupplierCollarDiameter"]
    collar.SetPosition2(thread_x + 0.015, collar.GetPosition()[1], 0.0)
    with pytest.raises(RuntimeError, match="text-on-line"):
        thumb._assert_supplier_paths(state.adapter, found)


def test_thumb_final_readback_refuses_native_short_witness_motion(native_thumb):
    state = native_thumb
    positions, short_geometry = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    display = thumb._supplier_displays(state.adapter)["SupplierHeadHeight"]
    x, y, z = display.line_position
    display.line_position = (x, y + 0.0001, z)
    with pytest.raises(RuntimeError, match="witness/arrow station moved"):
        thumb._assert_supplier_dimensions(state.adapter, positions, short_geometry)


def test_thumb_final_readback_measures_changed_native_arrow_tail_reach(native_thumb):
    state = native_thumb
    positions, short_geometry = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    state.tail_extra = 0.001
    with pytest.raises(RuntimeError, match="supplier axial text crowds"):
        thumb._assert_supplier_dimensions(state.adapter, positions, short_geometry)


def test_thumb_native_audit_reads_draw_only_offset_path_crossing_foreign_text(
    native_thumb,
):
    state = native_thumb
    positions, short_geometry = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    found = thumb._supplier_displays(state.adapter)
    head = found["SupplierHeadHeight"]
    records = {
        name: thumb._supplier_annotation_record(state.adapter, display)
        for name, display in found.items()
    }
    target_geometry = thumb.annotation_geometry(
        records["SupplierThreadDiameter"],
        owner=state.view.GetName2(),
        advance=thumb.calibrate_sheet_advance(records.values()),
    )
    assert target_geometry is not None and target_geometry.text_boxes
    # The two-row union's centre is in blank inter-row space, not glyph ink.
    # Land inside a real row, using the same calibrated row model as the audit.
    target = target_geometry.text_boxes[0]
    origin = head.offset_path_points()[0]
    state.native_path_overrides["SupplierHeadHeight"] = (origin, target.center())
    with pytest.raises(RuntimeError, match="text-on-line"):
        thumb._assert_supplier_dimensions(state.adapter, positions, short_geometry)


def test_thumb_native_audit_includes_foreign_live_view_outlines(native_thumb):
    state = native_thumb
    thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    found = thumb._supplier_displays(state.adapter)
    text = thumb.display_box(
        {"texts": _display_ink(None, found["SupplierThreadDiameter"])[0]["texts"]}
    )
    assert text is not None
    state.other_views.append(
        SimpleNamespace(
            GetOrientationName=lambda: "*Top",
            GetName2=lambda: "Foreign View",
            GetOutline=lambda: (
                text.xmin - 0.005,
                text.ymin - 0.005,
                text.xmax + 0.005,
                text.ymax + 0.005,
            ),
            GetFirstDisplayDimension6=lambda: None,
        )
    )
    with pytest.raises(RuntimeError, match="text-on-view"):
        thumb._assert_supplier_paths(state.adapter, found)


@pytest.mark.parametrize(
    "native_thumb", [((4, 1), ""), ((2, 1), "FIRST\nSECOND\nTHIRD")], indirect=True
)
def test_thumb_diameter_ink_clears_measured_native_witness_stations(native_thumb):
    state = native_thumb
    thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    found = thumb._supplier_displays(state.adapter)
    collar_record = thumb._supplier_annotation_record(
        state.adapter, found["SupplierCollarDiameter"]
    )
    _x, lower, upper = thumb._collar_native_stations(collar_record)
    collar = thumb.display_box({"texts": collar_record["display"]["texts"]})
    thread = thumb.display_box(
        {
            "texts": thumb._supplier_display_data(
                state.adapter, found["SupplierThreadDiameter"]
            )["texts"]
        }
    )
    assert collar is not None and thread is not None
    assert collar.center()[1] == pytest.approx((lower + upper) / 2, abs=1e-7)
    assert collar.ymin >= lower + 0.002
    assert collar.ymax <= upper - 0.002
    assert thread.ymax == pytest.approx(lower - 0.0037, abs=1e-7)
    # The 4:1 two-row block is lowest; native containment still must hold.
    assert thread.ymin >= state.cell[1]
    assert thread.xmax <= state.cell[2]


def test_thumb_native_audit_rejects_legacy_fixed_collar_text_station(native_thumb):
    state = native_thumb
    thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    found = thumb._supplier_displays(state.adapter)
    collar = found["SupplierCollarDiameter"]
    collar.SetPosition2(
        collar.GetPosition()[0], state.view.project((0.0, 0.0))[1] + 0.013, 0.0
    )
    with pytest.raises(RuntimeError, match="extension-through-own-text"):
        thumb._assert_supplier_paths(state.adapter, found)


@pytest.mark.parametrize(
    "native_thumb", [((2, 1), "FIRST\nSECOND\nTHIRD")], indirect=True
)
def test_thumb_native_audit_rejects_unshelved_thread_length_at_two_to_one(native_thumb):
    state = native_thumb
    thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    found = thumb._supplier_displays(state.adapter)
    thread = found["SupplierThreadLength"]
    thread.OffsetText = False
    midpoint = sum(point[0] for point in thread.points) / 2
    thread.SetPosition2(midpoint, thread.GetPosition()[1], 0.0)
    with pytest.raises(RuntimeError, match="extension-through-own-text"):
        thumb._assert_supplier_paths(state.adapter, found)


@pytest.mark.parametrize(
    "defect, moved_key",
    [("mode-line-drift", "tips"), ("mode-witness-tail", "witnesses")],
)
def test_thumb_station_refusal_logs_complete_native_transition(
    native_thumb, defect, moved_key
):
    state = native_thumb
    state.defect = defect
    with pytest.raises(RuntimeError, match="witness/arrow station moved") as refused:
        thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    baseline = next(
        event
        for event in state.native_transitions
        if event["phase"] == "before_offset_text_mode"
    )
    transition = next(
        event
        for event in state.native_transitions
        if event["phase"] == "after_offset_text_mode"
    )
    assert set(transition["dimensions"]) == set(thumb._AXIAL_NAMES)
    head = transition["dimensions"]["SupplierHeadHeight"]
    assert head["before"] == baseline["dimensions"]["SupplierHeadHeight"]["before"]
    before, after = head["before"], head["after"]
    for snapshot in (before, after):
        assert snapshot["native"]["display"]["texts"]
        assert snapshot["native"]["display"]["lines"]
        assert snapshot["native"]["display"]["arrows"]
        assert snapshot["native"]["pos"]
        assert snapshot["classified_segments"]
        assert snapshot["per_tip_runs"]
        assert all(run["classified_witness_runs"] for run in snapshot["per_tip_runs"])
        assert all(run["raw_vertical_runs"] for run in snapshot["per_tip_runs"])
        assert snapshot["document_witness_gap_m"] == pytest.approx(0.001)
        assert snapshot["witness_gaps"]["0"]["success"] is True
        assert snapshot["witness_gaps"]["1"]["uses_document"] is True
    assert "leaders" not in before["native"]
    assert "leaders" not in after["native"]
    assert before["properties"]["OffsetText"] is False
    assert after["properties"]["OffsetText"] is True
    comparison = head["comparison"]
    assert comparison[moved_key]["changed"] is True
    assert comparison[moved_key]["max_distance_m"] == pytest.approx(0.0001)
    assert comparison["tips"]["changed"] is (defect == "mode-line-drift")
    assert any(
        abs(value) == pytest.approx(0.0001)
        for pair in comparison[moved_key]["pairs"]
        for value in pair["delta_m"]
    )
    assert "phase=after_offset_text_mode" in str(refused.value)
    assert f"key={moved_key}" in str(refused.value)


def test_thumb_unreadable_arrow_inventory_still_logs_raw_native_records(native_thumb):
    state = native_thumb
    state.defect = "mode-arrow-inventory"
    with pytest.raises(RuntimeError, match="unreadable native arrows"):
        thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    transition = next(
        event
        for event in state.native_transitions
        if event["phase"] == "after_offset_text_mode"
    )
    head = transition["dimensions"]["SupplierHeadHeight"]
    assert len(head["before"]["native"]["display"]["arrows"]) == 2
    assert len(head["after"]["native"]["display"]["arrows"]) == 3
    assert head["after"]["native"]["display"]["lines"]
    assert "leaders" not in head["after"]["native"]
    assert head["after"]["classified_segments"]
    assert "unreadable native arrows" in head["after"]["guard_error"]["message"]
    assert set(transition["dimensions"]) == set(thumb._AXIAL_NAMES)


def test_thumb_refused_diagnostic_policy_read_cannot_approve_or_refuse_geometry(
    native_thumb,
):
    state = native_thumb
    state.defect = "witness-policy-refusal"
    positions, short_geometry = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    thumb._assert_supplier_dimensions(state.adapter, positions, short_geometry)
    transition = next(
        event
        for event in state.native_transitions
        if event["phase"] == "after_final_rebuild"
    )
    gaps = transition["dimensions"]["SupplierHeadHeight"]["after"]["witness_gaps"]
    assert all(row["success"] is False for row in gaps.values())
    assert all(
        row["unmeasured"] is True and row["gap_m"] is None for row in gaps.values()
    )


@pytest.mark.parametrize("phase", ["annotation", "settled"])
@pytest.mark.parametrize("capture_refuses", [False, True])
def test_thumb_build_preserves_original_failure_and_requests_sheet_capture(
    monkeypatch, phase, capture_refuses
):
    adapter = object()
    original = RuntimeError("native supplier failure")
    captures = []

    def author(_adapter, _views):
        if phase == "annotation":
            raise original
        return {}, {}

    def settled(*_args):
        raise original

    async def purchased_drawing(current_adapter, _spec, **options):
        options["supplier_dimensions"](current_adapter, {})
        for check in options["settled_checks"]:
            check()
        raise AssertionError("synthetic supplier failure was not reached")

    def capture(current_adapter, label, message, **options):
        captures.append((current_adapter, label, message, options))
        if capture_refuses:
            raise OSError("synthetic forensic capture refusal")
        raise options["exception"]

    monkeypatch.setattr(thumb, "supplier_dimensions", author)
    monkeypatch.setattr(thumb, "_assert_supplier_dimensions", settled)
    monkeypatch.setattr(thumb, "build_purchased_fastener_drawing", purchased_drawing)
    monkeypatch.setattr(thumb._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(RuntimeError) as refused:
        asyncio.run(thumb.build(adapter))
    assert refused.value is original
    # Each failed callback requests one native drawing/PNG forensic bundle;
    # retrying the capture would duplicate those artifacts, not add proof.
    assert len(captures) == 1
    assert any(
        current_adapter is adapter
        and options["exception"] is original
        and options["sheet_png"] is True
        and options["supplier_phase"] == phase
        for current_adapter, _label, _message, options in captures
    )
    if capture_refuses:
        assert any("forensic capture failed" in note for note in original.__notes__)


@pytest.mark.parametrize(
    "native_thumb", [((4, 1), ""), ((2, 1), "FIRST\nSECOND\nTHIRD")], indirect=True
)
@pytest.mark.parametrize(
    "offsets",
    [
        {
            "SupplierHeadHeight": 0.0027781,
            "SupplierCollarHeight": 0.0027782,
            "SupplierThreadLength": 0.0027782,
        },
        {
            "SupplierHeadHeight": 0.0017,
            "SupplierCollarHeight": 0.0031,
            "SupplierThreadLength": 0.0023,
        },
    ],
)
@pytest.mark.parametrize("anchor_phase", ("toggle", "first-offset-position"))
def test_thumb_measured_offset_anchor_preserves_original_line_stations(
    native_thumb, offsets, anchor_phase
):
    state = native_thumb
    state.offset_anchor_phase = anchor_phase
    state.text_line_offsets = offsets
    positions, expected = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    found = thumb._supplier_displays(state.adapter)
    for name in thumb._AXIAL_NAMES:
        before = expected[name]["native_before"]
        original_position = before["native"]["pos"]
        original_tips = expected[name]["tips"]
        original_baseline = original_tips[0][1]
        assert original_tips[1][1] == pytest.approx(original_baseline)
        assert original_position[1] - original_baseline == pytest.approx(offsets[name])
        after = thumb._short_native_geometry(
            thumb._supplier_annotation_record(state.adapter, found[name])
        )
        for key in ("tips", "witnesses"):
            for original, actual in zip(expected[name][key], after[key], strict=True):
                assert actual == pytest.approx(original, abs=1e-7)
        assert found[name].GetPosition()[1] == pytest.approx(original_position[1])
        if expected[name]["shelved"]:
            prepared = next(
                event
                for event in state.native_transitions
                if event["phase"] == "prepared_offset_text_anchors"
            )["dimensions"][name]
            assert prepared["measured_offset_anchor_m"][1] == pytest.approx(
                original_baseline
            )
            assert prepared["prepared"]["native"]["pos"][1] == pytest.approx(
                original_baseline
            )
        else:
            assert name == "SupplierThreadLength"
            assert found[name].GetPosition() == pytest.approx(original_position)
        assert positions[name][1] == pytest.approx(original_position[1])
    thumb._assert_supplier_dimensions(state.adapter, positions, expected)


@pytest.mark.parametrize("anchor_phase", ("toggle", "first-offset-position"))
def test_thumb_native_offset_transition_reproduces_012dd_without_anchor_preparation(
    native_thumb, anchor_phase
):
    state = native_thumb
    state.offset_anchor_phase = anchor_phase
    thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    for name in ("SupplierHeadHeight", "SupplierCollarHeight"):
        display = thumb._supplier_displays(state.adapter)[name]
        display.OffsetText = False
        before = thumb._supplier_annotation_record(state.adapter, display)
        prior = thumb._short_native_geometry(before)
        old_anchor = display.GetPosition()
        display.OffsetText = True
        assert display.SetPosition2(*old_anchor) is True
        after = thumb._short_native_geometry(
            thumb._supplier_annotation_record(state.adapter, display)
        )
        assert after["tips"][0][1] == pytest.approx(old_anchor[1])
        assert after["tips"][0][1] - prior["tips"][0][1] == pytest.approx(
            state.text_line_offsets[name]
        )
        assert [tip[0] for tip in after["tips"]] == pytest.approx(
            [tip[0] for tip in prior["tips"]]
        )
        expected = {
            other: {
                **thumb._short_native_geometry(
                    thumb._supplier_annotation_record(state.adapter, current)
                ),
                "native_before": thumb._short_native_snapshot(
                    state.adapter,
                    current,
                    thumb._supplier_annotation_record(state.adapter, current),
                ),
                "shelved": current.OffsetText,
            }
            for other, current in thumb._supplier_displays(state.adapter).items()
            if other in thumb._AXIAL_NAMES
        }
        expected[name] = {**prior, "native_before": {"native": before}, "shelved": True}
        with pytest.raises(RuntimeError, match="witness/arrow station moved"):
            thumb._read_settled_short_geometry(
                state.adapter,
                thumb._supplier_displays(state.adapter),
                expected,
                phase="legacy_unprepared_offset_transition",
            )


def test_thumb_station_guard_still_refuses_line_motion_during_later_text_move(
    native_thumb,
):
    state = native_thumb
    state.defect = "shelf-line-drift"
    with pytest.raises(RuntimeError, match="phase=after_text_shelves; key=tips"):
        thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    after_mode = next(
        event
        for event in state.native_transitions
        if event["phase"] == "after_offset_text_mode"
    )
    assert not any(
        change["changed"]
        for dimension in after_mode["dimensions"].values()
        for change in dimension["comparison"].values()
    )
    after_shelf = next(
        event
        for event in state.native_transitions
        if event["phase"] == "after_text_shelves"
    )
    head = after_shelf["dimensions"]["SupplierHeadHeight"]["comparison"]
    assert head["tips"]["changed"] is True
    assert head["tips"]["max_distance_m"] == pytest.approx(0.0001)


def test_thumb_draw_only_connector_and_underline_do_not_change_physical_reach(
    native_thumb,
):
    state = native_thumb
    _positions, expected = thumb.supplier_dimensions(
        state.adapter, {"*Front": state.view}
    )
    found = thumb._supplier_displays(state.adapter)
    for name in ("SupplierHeadHeight", "SupplierCollarHeight"):
        record = thumb._supplier_annotation_record(state.adapter, found[name])
        assert "leaders" not in record
        actual = thumb._short_native_geometry(record)
        assert actual["left"] == pytest.approx(expected[name]["left"])
        points = found[name].offset_path_points()
        assert min(point[0] for point in points) < actual["left"] - 0.002


def test_thumb_merged_tip_to_text_native_run_is_refused_not_filtered_out(native_thumb):
    state = native_thumb
    state.defect = "merged-offset-tail"
    with pytest.raises(RuntimeError, match="supplier axial text crowds"):
        thumb.supplier_dimensions(state.adapter, {"*Front": state.view})


def test_thumb_native_audit_refuses_draw_only_path_through_own_text(native_thumb):
    state = native_thumb
    thumb.supplier_dimensions(state.adapter, {"*Front": state.view})
    found = thumb._supplier_displays(state.adapter)
    records = {
        name: thumb._supplier_annotation_record(state.adapter, display)
        for name, display in found.items()
    }
    head = found["SupplierHeadHeight"]
    geometry = thumb.annotation_geometry(
        records["SupplierHeadHeight"],
        owner=state.view.GetName2(),
        advance=thumb.calibrate_sheet_advance(records.values()),
    )
    assert geometry is not None and geometry.text_boxes
    state.native_path_overrides["SupplierHeadHeight"] = (
        head.offset_path_points()[0],
        geometry.text_boxes[0].center(),
    )
    with pytest.raises(RuntimeError, match="extension-through-own-text"):
        thumb._assert_supplier_paths(state.adapter, found)
