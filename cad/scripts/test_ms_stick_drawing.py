"""Offline manufacturing contracts for the unchanged measuring-stick geometry."""

from __future__ import annotations

import asyncio
import ast
import math
import re
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import _common as common

import _drawing_common as drawing_common
import build_ms_stick as builder
import draw_ms_stick as drawing
import ms_stick_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_current_identity_and_drawing_paths() -> None:
    assert builder.PART_NAME == drawing.PART_STEM == "ms-stick"
    assert DRAWINGS_BY_NAME["ms_stick"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.name == "ms-stick.SLDDRW"
    assert drawing.PDF.name == "ms-stick.pdf"
    assert drawing.PNG.name == "ms-stick_drawing.png"
    assert spec.NUMERALS_DXF.name == "ms-stick-numerals.dxf"


def test_bar_and_engraving_geometry_are_unchanged() -> None:
    assert (spec.BODY_LENGTH, spec.BODY_WIDTH, spec.BODY_THICKNESS) == (200.0, 8.0, 3.0)
    assert (spec.TICK_WIDTH, spec.TICK_DEPTH, spec.TICK_LENGTH) == (0.4, 0.5, 3.0)
    assert (spec.MINOR_TICK_LENGTH, spec.HALF_TICK_LENGTH) == (1.8, 4.0)
    assert spec.DIVISION_COUNT == 11 and spec.MINOR_PER_DIVISION == 10
    assert spec.SCALE_SPAN == pytest.approx(
        (spec.DIVISION_COUNT - 1) * spec.DIVISION_SPACING, rel=0.0, abs=1e-12,
    )
    assert spec.SCALE_START_X + spec.SCALE_SPAN + spec.SCALE_END_MARGIN == pytest.approx(
        spec.BODY_LENGTH, rel=0.0, abs=1e-12,
    )
    assert (spec.NUMERAL_HEIGHT_MM, spec.NUMERAL_GAP_MM, spec.NUMERAL_ROTATION_DEG) == (2.0, 0.6, 90)
    for name in ("BODY_LENGTH", "BODY_WIDTH", "BODY_THICKNESS", "SCALE_START_X",
                 "TICK_WIDTH", "TICK_DEPTH", "NUMERALS_DXF"):
        assert getattr(builder, name) == getattr(spec, name)


def test_every_printed_size_is_owned_and_precisioned_by_model() -> None:
    assert builder.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert builder.DRAWING_PRECISION is spec.DRAWING_PRECISION
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP)
            | set(drawing.NUMERAL_KEEP) | set(drawing.DEPTH_KEEP)
            | set().union(*(set(row[4]) for row in drawing.LENGTH_DETAILS)))
    assert kept == marked == set(spec.DRAWING_VALUES_BY_NAME) == set(spec.DRAWING_PRECISION_BY_NAME)
    assert all(places == 2 for places in spec.DRAWING_PRECISION_BY_NAME.values())
    assert set(spec.DRAWING_TOLERANCES) <= marked
    assert {"BodyThickness", "TickDepth", "FullTickLength", "MinorTickLength",
            "HalfTickLength", "FullTickPitch", "MinorTickPitch", "NumeralHeight",
            "NumeralXGap", "NumeralYGap"} <= marked
    assert drawing.SHEET_NAMES == ("BAR", "GRADUATIONS", "TICK LENGTHS", "ENGRAVING")
    assert drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] > drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]


def test_reference_chords_measure_real_sizes_not_profile_overhangs() -> None:
    assert spec.DRAWING_VALUES_BY_NAME["FullTickLength"] == pytest.approx(
        spec.TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["MinorTickLength"] == pytest.approx(
        spec.MINOR_TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["HalfTickLength"] == pytest.approx(
        spec.HALF_TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["MinorTickPitch"] == pytest.approx(
        spec.DIVISION_SPACING / spec.MINOR_PER_DIVISION, rel=0.0, abs=1e-12,
    )
    for _name, start, end in spec.REFERENCE_DIMENSIONS.values():
        assert (start[0] == end[0]) != (start[1] == end[1])
        assert 0.0 <= min(start[0], end[0]) <= max(start[0], end[0]) <= spec.BODY_LENGTH
        assert 0.0 <= min(start[1], end[1]) <= max(start[1], end[1]) <= spec.BODY_WIDTH

def test_scale_has_one_printed_origin_without_closing_chain() -> None:
    assert drawing.FRONT_KEEP.keys() == {"BodyLength", "BodyWidth", "ScaleStartX"}
    assert "ScaleEndMargin" not in spec.DRAWING_VALUES_BY_NAME
    assert "ScaleEndMargin" not in spec.DRAWING_TOLERANCES
    assert "ScaleEndReference" not in spec.REFERENCE_DIMENSIONS
    start = spec.REFERENCE_DIMENSIONS["ScaleStartReference"]
    assert start[1] == (0.0, spec.BODY_WIDTH)
    assert start[2] == (spec.SCALE_START_X, spec.BODY_WIDTH)


def test_last_graduation_is_complete_at_printed_band_extremes() -> None:
    """Noncumulative pitch allows one station error, not ten chained errors."""
    values, bands = spec.DRAWING_VALUES_BY_NAME, spec.DRAWING_TOLERANCES
    stock_min = values["BodyLength"] - bands["BodyLength"]
    last_center_max = (
        values["ScaleStartX"] + bands["ScaleStartX"]
        + (spec.DIVISION_COUNT - 1) * values["FullTickPitch"] + bands["FullTickPitch"]
    )
    last_edge_max = last_center_max + (values["Tick0Width"] + bands["Tick0Width"]) / 2.0
    assert spec.DRAWING_PRECISION_BY_NAME["BodyLength"] == 2
    assert stock_min == pytest.approx(199.90)
    assert last_edge_max == pytest.approx(199.825)
    assert stock_min >= last_edge_max


def test_loose_cosmetic_depth_keeps_the_structural_floor() -> None:
    values, bands = spec.DRAWING_VALUES_BY_NAME, spec.DRAWING_TOLERANCES
    floor_min = values["BodyThickness"] - bands["BodyThickness"] - values["TickDepth"] - bands["TickDepth"]
    assert bands["TickDepth"] == pytest.approx(0.1)
    assert bands["Tick0Width"] == pytest.approx(0.05)
    assert floor_min == pytest.approx(2.3)
    assert floor_min >= 2.0




def test_reference_equations_follow_editable_tick_geometry(monkeypatch) -> None:
    """Capture actual emitted dimensions and deferred jobs without a COM seat."""
    features = {}

    class Adapter:
        def __init__(self):
            self._sketch_entities = {}
            self.dimensions = []

        async def create_sketch(self, plane):
            assert plane == "Front"
            self.dimensions = []
            return True

        async def add_line(self, *coordinates):
            self._sketch_entities["line"] = SimpleNamespace(ConstructionGeometry=False)
            return "line"

        async def add_sketch_constraint(self, *args):
            return True

        async def exit_sketch(self):
            return True

    adapter = Adapter()

    async def dimension(adapter, first, second, kind, value, label):
        adapter.dimensions.append(SimpleNamespace(value_mm=value))

    async def fully_defined(adapter, label):
        return None

    def name_feature(adapter, feature):
        features[feature] = adapter.dimensions
        return feature

    def rename(dimensions, feature, names):
        for dim, name in zip(dimensions, names, strict=True):
            dim.name = name

    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(builder, "check", lambda label, value: value)
    monkeypatch.setattr(common, "check", lambda label, value: value)
    monkeypatch.setattr(builder, "set_sketch_direct_db", lambda *args: None)
    monkeypatch.setattr(builder, "dimension_between", dimension)
    monkeypatch.setattr(common, "dimension_between", dimension)
    monkeypatch.setattr(builder, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(builder, "name_last_feature", name_feature)
    monkeypatch.setattr(common, "_feature_by_name", lambda adapter, name: features[name])
    monkeypatch.setattr(common, "_display_dimensions", lambda feature, name: feature)
    monkeypatch.setattr(common, "_rename_dimensions", rename)
    jobs = []
    asyncio.run(builder._manufacturing_chords(adapter, jobs))
    equations = dict(jobs)
    knobs = {
        "BodyLength": spec.BODY_LENGTH, "BodyWidth": spec.BODY_WIDTH,
        "ScaleEndMargin": spec.SCALE_END_MARGIN, "TickWidth": spec.TICK_WIDTH,
        "TickLength": spec.TICK_LENGTH, "MinorTickLength": spec.MINOR_TICK_LENGTH,
        "HalfTickLength": spec.HALF_TICK_LENGTH,
        "DivisionSpacing": spec.DIVISION_SPACING,
    }

    def values(**edits):
        globals_ = knobs | edits
        globals_["ScaleStartX"] = (
            globals_["BodyLength"] - (spec.DIVISION_COUNT - 1)
            * globals_["DivisionSpacing"] - globals_["ScaleEndMargin"]
        )
        result = {}
        for name, expression in equations.items():
            expression = re.sub(
                r'"([^"]+)"', lambda match: str(globals_[match[1]]), expression,
            ).replace("mm", "")
            result[name] = eval(expression, {"__builtins__": {}}, {})
        return result

    baseline = values()
    for feature, dimensions in features.items():
        for dim in dimensions:
            assert baseline[f"{dim.name}@{feature}"] == pytest.approx(dim.value_mm)
    for knob, name, feature in (
        ("TickLength", "FullTickLength", "FullLengthReference"),
        ("MinorTickLength", "MinorTickLength", "MinorLengthReference"),
        ("HalfTickLength", "HalfTickLength", "HalfLengthReference"),
    ):
        edited = values(**{knob: knobs[knob] + 0.2})
        assert edited[f"{name}@{feature}"] == pytest.approx(knobs[knob] + 0.2)
        assert (edited[f"{name}AnchorY@{feature}"] + edited[f"{name}@{feature}"]
                == pytest.approx(spec.BODY_WIDTH))
    edited = values(DivisionSpacing=spec.DIVISION_SPACING + 0.1)
    assert edited["FullTickPitch@FullPitchReference"] == pytest.approx(spec.DIVISION_SPACING + 0.1)
    assert edited["MinorTickPitch@MinorPitchReference"] == pytest.approx(
        (spec.DIVISION_SPACING + 0.1) / spec.MINOR_PER_DIVISION,
    )
    assert values(TickLength=3.2)["NumeralYGap@NumeralYGapReference"] == pytest.approx(0.4)
    assert values(TickWidth=0.6)["NumeralXGap@NumeralXGapReference"] == pytest.approx(0.5)
    assert edited["NumeralXGap@NumeralXGapReference"] == pytest.approx(1.6)
    assert edited["NumeralHeight@NumeralHeightReference"] == pytest.approx(spec.NUMERAL_HEIGHT_MM)
    assert not any("ScaleEndReference" in name for name in equations)
    changed_margin = values(ScaleEndMargin=spec.SCALE_END_MARGIN + 0.1)
    assert changed_margin["ScaleStartX@ScaleStartReference"] == pytest.approx(spec.SCALE_START_X - 0.1)
    assert changed_margin["FullTickPitchAnchorX@FullPitchReference"] == pytest.approx(spec.SCALE_START_X - 0.1)


def test_finish_preserves_polish_and_black_enamel_engraving_fill() -> None:
    registry = Path(builder.__file__).resolve().parents[1] / "config" / "parts" / "ms-stick.yaml"
    finish = yaml.safe_load(registry.read_text(encoding="utf-8"))["ms-stick"]["finish"]
    assert "polished brass" in finish
    assert "flat black enamel" in finish
    assert "all engraving" in finish
    assert "cured before final polish" in finish


def test_spec_is_pure_and_drawing_never_reauthors_dimensions() -> None:
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name.startswith(("build_", "solidworks", "_common", "_drawing")) for name in imports)
    drawing_tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    calls = {node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
             for node in ast.walk(drawing_tree) if isinstance(node, ast.Call)
             and isinstance(node.func, (ast.Attribute, ast.Name))}
    assert not calls & {"SetPrecision3", "set_dimension_precision", "SetValues", "set_basic_dimensions", "add_gdt_frame", "add_datum_tag"}
    assert not any(character.isdigit() for character in spec.DRAWING_NOTES)


class _StickAffine:
    def __init__(self, factors, offsets, axes=(0, 1, 2)):
        self.factors = factors
        self.offsets = offsets
        self.axes = axes

    def apply(self, xyz):
        return tuple(factor * value + offset for factor, value, offset in zip(
            self.factors, (xyz[axis] for axis in self.axes), self.offsets, strict=True
        ))


class _StickMathPoint:
    def __init__(self, xyz):
        self.ArrayData = tuple(xyz)

    def MultiplyTransform(self, transform):  # noqa: N802 - COM member name
        return _StickMathPoint(transform.apply(self.ArrayData))


class _StickMathUtility:
    def __init__(self):
        self.points = []

    def CreatePoint(self, values):  # noqa: N802 - COM member name
        xyz = tuple(getattr(values, "value", values))
        self.points.append(xyz)
        return _StickMathPoint(xyz)


def test_build_projects_metre_scale_local_details_and_open_edge_depth_fences(monkeypatch, tmp_path) -> None:
    """Exercise real callers, sheet routing, fences and label readback offline."""
    source = tmp_path / "ms-stick.SLDPRT"
    source.write_bytes(b"offline source sentinel")
    monkeypatch.setattr(drawing, "SOURCE", source)
    utility = _StickMathUtility()
    circles, placements, detail_calls, imports, clean_views, letters = [], [], [], [], [], []
    sketch_transform = _StickAffine((2.0, -3.0, 1.0), (0.03, 0.04, 0.02))
    active = {"sheet": None, "parent": None}
    views = {}

    class DetailCircle:
        def __init__(self, label):
            self.label = label
            self.position = None

        def GetLabel(self):  # noqa: N802 - COM member name
            return self.label

        def SetLabelPosition(self, x, y):  # noqa: N802 - COM member name
            self.position = (x, y)
            letters.append((self.label, self.position))

        def GetLabelPosition(self):  # noqa: N802 - COM member name
            return self.position

    def make_view(position, scale, center_x, orientation="*Back"):
        ratio = scale[0] / scale[1]
        axes = (0, 2, 1) if orientation == "*Top" else (0, 1, 2)
        vertical_center = 0.0015 if orientation == "*Top" else 0.004
        name = f"offline-view-{len(views)}"
        detail_circles = []
        view = SimpleNamespace(
            Position=position, ScaleRatio=scale, Angle=0.0, Orientation=orientation,
            Sheet=active["sheet"], Circles=detail_circles,
            GetName2=lambda: name, GetDetailCircles=lambda: detail_circles,
            GetSketch=lambda: SimpleNamespace(ModelToSketchTransform=sketch_transform),
            ModelToViewTransform=_StickAffine(
                (ratio, -ratio, -ratio),
                (position[0] - ratio * center_x, position[1] + ratio * vertical_center, 0.0),
                axes=axes,
            ),
        )
        views[name] = view
        return view

    def circle(*points):
        circles.append(points)
        return object()

    def create_detail(*args):
        label = args[6]
        parent = active["parent"]
        assert args[2:] == (0.0, 0, *drawing.DETAIL_SCALE, label, 1, True, False, False, 5)
        parent.Circles.append(DetailCircle(label))
        detail = make_view(args[:2], drawing.DETAIL_SCALE, 0.0646, parent.Orientation)
        detail_calls.append((label, active["sheet"], parent, detail))
        return detail

    def activate_sheet(name):
        active["sheet"] = name
        return True

    def activate_view(name):
        active["parent"] = views[name]
        return True

    document = SimpleNamespace(
        ActivateSheet=activate_sheet, ActivateView=activate_view,
        ClearSelection2=lambda clear: None, EditRebuild3=lambda: True,
        SketchManager=SimpleNamespace(CreateCircle=circle),
        CreateDetailViewAt4=create_detail,
    )

    async def open_model(path):
        assert path == str(source)
        return SimpleNamespace(is_success=True, data=None)

    adapter = SimpleNamespace(
        currentModel=object(), open_model=open_model,
        swApp=SimpleNamespace(GetMathUtility=lambda: utility),
    )

    def new_drawing(*args, **kwargs):
        adapter.currentModel = document
        return document, object()

    def place_view(adapter, path, orientation, x, y, *, scale):
        assert path == str(source)
        assert orientation in ("*Back", "*Top", "*Isometric")
        view = make_view((x, y), scale, 0.1, orientation)
        placements.append(view)
        return view

    def invoke(obj, _interface, member, *args):
        value = getattr(obj, member)
        return value(*args) if callable(value) else value

    monkeypatch.setattr(drawing_common, "_com_invoke", invoke)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "view_name", lambda adapter, view: view.GetName2())
    for name in (
        "read_required_properties", "create_blank_drawing_sheets", "stamp_drawing_summary",
        "set_dimension_callouts", "assert_manufacturing_dimensions", "add_property_linked_note",
        "rebuild_drawing",
    ):
        monkeypatch.setattr(drawing, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(
        drawing, "set_hidden_lines_removed", lambda adapter, view: clean_views.append(view),
    )

    def curate(adapter, view, **kwargs):
        imports.append((view, kwargs))
        return []

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "part_sketches_shown", lambda *args, **kwargs: nullcontext())

    async def finalize(adapter, outputs, **kwargs):
        assert kwargs["expected_sheet_names"] == drawing.SHEET_NAMES
        assert set(kwargs["sheet_layouts"]) == set(drawing.SHEET_NAMES)
        return {"slddrw": str(outputs.slddrw)}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    assert asyncio.run(drawing.build(adapter)) == {"slddrw": str(drawing.OUTPUTS.slddrw)}
    assert source.read_bytes() == b"offline source sentinel"
    assert len(utility.points) == 18  # three transforms per fence, no floating labels
    expected = [
        ("A", "GRADUATIONS", drawing.DETAIL_CENTER, drawing.DETAIL_RADIUS_MM,
         ((spec.SCALE_START_X + spec.DIVISION_SPACING / 2.0) / 1000.0, spec.BODY_WIDTH / 2000.0, 0.0),
         drawing.DETAIL_KEEP),
        *((label, "TICK LENGTHS", xy, radius,
           (model[0] / 1000.0, model[1] / 1000.0, 0.0), keep)
          for label, _parent, xy, model, keep, radius in drawing.LENGTH_DETAILS),
        ("F", "ENGRAVING", drawing.NUMERAL_CENTER, drawing.NUMERAL_RADIUS_MM,
         ((spec.SCALE_START_X + spec.TICK_WIDTH / 2.0 + spec.NUMERAL_GAP_MM
           + spec.NUMERAL_HEIGHT_MM / 2.0) / 1000.0,
          (spec.BODY_WIDTH - spec.TICK_LENGTH - spec.NUMERAL_GAP_MM) / 1000.0, 0.0),
         drawing.NUMERAL_KEEP),
        ("B", "ENGRAVING", drawing.DEPTH_CENTER, drawing.DEPTH_RADIUS_MM,
         (spec.SCALE_START_X / 1000.0, spec.BODY_WIDTH / 1000.0, spec.BODY_THICKNESS / 2000.0),
         drawing.DEPTH_KEEP),
    ]
    for index, (actual, wanted) in enumerate(zip(detail_calls, expected, strict=True)):
        label, sheet, parent, detail = actual
        wanted_label, wanted_sheet, xy, radius, model_xyz, keep = wanted
        assert (label, sheet) == (wanted_label, wanted_sheet)
        assert detail.Position == xy
        assert parent.ScaleRatio == (1.0, 2.0)
        assert tuple(getattr(detail.ScaleRatio, "value", detail.ScaleRatio)) == drawing.DETAIL_SCALE
        assert utility.points[3 * index] == pytest.approx(model_xyz)
        projected = parent.ModelToViewTransform.apply(model_xyz)
        center = (projected[0], projected[1], 0.0)
        rim = (center[0] + radius / 2000.0, center[1], 0.0)
        assert utility.points[3 * index + 1] == pytest.approx(center)
        assert utility.points[3 * index + 2] == pytest.approx(rim)
        assert circles[index] == pytest.approx(
            (*sketch_transform.apply(center), *sketch_transform.apply(rim)))
        assert letters[index] == (label, (center[0], center[1] + 0.015))
        imported = next(kwargs for view, kwargs in imports if view is detail)
        assert imported["keep"] is keep
        assert imported["dimensions_by_feature"] is spec.DRAWING_DIMENSIONS
        assert any(view is detail for view in clean_views)
    depth_parent = placements[-1]
    assert depth_parent.Orientation == "*Top"
    assert depth_parent.Position == drawing.DEPTH_PARENT_CENTER
    assert depth_parent.Angle == 0.0
    assert drawing.DEPTH_RADIUS_MM > math.hypot(spec.TICK_WIDTH / 2.0, spec.BODY_THICKNESS / 2.0)
    assert all(view.Angle == pytest.approx(math.pi)
               for view in placements if view.Orientation == "*Back")
    assert placements[0].Position[0] == placements[1].Position[0]


def test_local_length_fences_include_owned_ticks_without_cross_strip_routing() -> None:
    lengths = {
        "FullTickLength": spec.TICK_LENGTH,
        "MinorTickLength": spec.MINOR_TICK_LENGTH,
        "HalfTickLength": spec.HALF_TICK_LENGTH,
    }
    for label, _parent, detail, model, keep, radius in drawing.LENGTH_DETAILS:
        name = next(name for name in keep if name in lengths)
        assert radius > math.hypot(spec.TICK_WIDTH / 2.0, lengths[name] / 2.0)
        assert keep[name][0] < detail[0] - radius * drawing.DETAIL_SCALE[0] / 1000.0
        assert model[1] == pytest.approx(spec.BODY_WIDTH - lengths[name] / 2.0)
        if label == "D":
            assert radius < spec.MINOR_SPACING - spec.TICK_WIDTH / 2.0


@pytest.mark.parametrize("labels,readback", [
    ((), (0.100, 0.215)),
    (("B",), (0.100, 0.215)),
    (("A", "A"), (0.100, 0.215)),
    (("A",), (0.100, 0.200)),
    (("A",), (0.100,)),
])
def test_detail_letter_refuses_missing_ambiguous_or_ignored_native_placement(
    monkeypatch, labels, readback,
) -> None:
    circles = tuple(SimpleNamespace(
        GetLabel=lambda label=label: label,
        SetLabelPosition=lambda *xy: None,
        GetLabelPosition=lambda: readback,
    ) for label in labels)
    parent = SimpleNamespace(
        GetDetailCircles=lambda: circles,
        GetSketch=lambda: SimpleNamespace(
            ModelToSketchTransform=_StickAffine((1.0, 1.0, 1.0), (0.0, 0.0, 0.0))),
    )
    document = SimpleNamespace(
        ActivateView=lambda name: True, ClearSelection2=lambda clear: None,
        EditRebuild3=lambda: True,
        SketchManager=SimpleNamespace(CreateCircle=lambda *args: object()),
        CreateDetailViewAt4=lambda *args: SimpleNamespace(ScaleRatio=None),
    )
    adapter = SimpleNamespace(
        currentModel=document,
        swApp=SimpleNamespace(GetMathUtility=lambda: _StickMathUtility()),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "view_name", lambda *args: "offline-parent")
    monkeypatch.setattr(drawing, "model_point_in_view", lambda *args, **kwargs: (0.100, 0.200))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="matching parent circle|placement rejected"):
        drawing._engraving_detail(
            adapter, parent, model_center=(0.0575, 0.004, 0.0),
            view_xy=drawing.DETAIL_CENTER, radius_mm=drawing.DETAIL_RADIUS_MM,
            detail_label="A",
        )
