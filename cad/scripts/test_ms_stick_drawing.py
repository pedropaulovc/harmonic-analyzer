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
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP) | set(drawing.DEPTH_KEEP)
    assert kept == marked == set(spec.DRAWING_VALUES_BY_NAME) == set(spec.DRAWING_PRECISION_BY_NAME)
    assert all(places == 2 for places in spec.DRAWING_PRECISION_BY_NAME.values())
    assert set(spec.DRAWING_TOLERANCES) <= marked
    assert {"BodyThickness", "TickDepth", "FullTickLength", "MinorTickLength",
            "HalfTickLength", "FullTickPitch", "MinorTickPitch", "NumeralHeight",
            "NumeralXGap", "NumeralYGap"} <= marked
    assert drawing.SHEET_NAMES == ("BAR", "GRADUATIONS")
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


def test_build_projects_metre_scale_graduation_and_open_edge_depth_fences(monkeypatch, tmp_path) -> None:
    """Run real A/B callers and Back/Top projection without opening a COM seat."""
    source = tmp_path / "ms-stick.SLDPRT"
    source.write_bytes(b"offline source sentinel")
    monkeypatch.setattr(drawing, "SOURCE", source)
    utility = _StickMathUtility()
    circles, notes, placements, detail_calls, imports, clean_views = [], [], [], [], [], []
    sketch_transform = _StickAffine((2.0, -3.0, 1.0), (0.03, 0.04, 0.02))

    def make_view(position, scale, center_x, orientation="*Back"):
        ratio = scale[0] / scale[1]
        # Rotated Back projects X/-Y; Top projects X/-Z and looks along Y.
        axes = (0, 2, 1) if orientation == "*Top" else (0, 1, 2)
        vertical_center = 0.0015 if orientation == "*Top" else 0.004
        return SimpleNamespace(
            Position=position, ScaleRatio=scale, Angle=0.0, Orientation=orientation,
            GetName2=lambda: "offline-view",
            GetSketch=lambda: SimpleNamespace(ModelToSketchTransform=sketch_transform),
            ModelToViewTransform=_StickAffine(
                (ratio, -ratio, -ratio),
                (position[0] - ratio * center_x, position[1] + ratio * vertical_center, 0.0),
                axes=axes,
            ),
        )

    details = {
        "A": make_view(drawing.DETAIL_CENTER, drawing.DETAIL_SCALE, 0.0646),
        "B": make_view(drawing.DEPTH_CENTER, drawing.DETAIL_SCALE, 0.0575, "*Top"),
    }

    def circle(*points):
        circles.append(points)
        return object()

    def create_detail(*args):
        label = args[6]
        center = drawing.DETAIL_CENTER if label == "A" else drawing.DEPTH_CENTER
        assert args == (*center, 0.0, 0, *drawing.DETAIL_SCALE,
                        label, 1, True, False, False, 5)
        detail_calls.append(label)
        return details[label]

    document = SimpleNamespace(
        ActivateSheet=lambda name: True, ActivateView=lambda name: True,
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

    # Preserve model_point_in_view and its real projection internals; replace
    # only raw COM dispatch and early binding with the fake geometry members.
    monkeypatch.setattr(drawing_common, "_com_invoke", invoke)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "view_name", lambda adapter, view: view.GetName2())
    for name in (
        "read_required_properties", "create_blank_drawing_sheets", "stamp_drawing_summary",
        "set_dimension_callouts", "assert_manufacturing_dimensions", "add_property_linked_note",
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

    def note(adapter, text, x, y):
        notes.append((text, x, y))
        return object()

    async def finalize(adapter, outputs, **kwargs):
        return {"slddrw": str(outputs.slddrw)}

    monkeypatch.setattr(drawing, "add_note", note)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    assert asyncio.run(drawing.build(adapter)) == {"slddrw": str(drawing.OUTPUTS.slddrw)}
    assert source.read_bytes() == b"offline source sentinel"
    assert len(utility.points) == 17
    assert len(notes) == 11
    for value, (xyz, (text, x, y)) in enumerate(zip(
        utility.points[:11], notes, strict=True
    )):
        assert xyz == pytest.approx((0.0575 + value * 0.0142, 0.008, 0.0))
        assert text == str(value)
        assert (x, y) == pytest.approx((0.0795 + value * 0.0142, 0.201))
    assert utility.points[11] == pytest.approx((0.0646, 0.004, 0.0))
    assert utility.points[12] == pytest.approx((0.2123, 0.240, 0.0))
    assert utility.points[13] == pytest.approx((0.2188, 0.240, 0.0))
    assert detail_calls == ["A", "B"]
    assert len(circles) == 2
    assert circles[0] == pytest.approx((0.4546, -0.680, 0.02, 0.4676, -0.680, 0.02))
    # B looks straight at the groove's open long edge, centred through stock Z.
    assert utility.points[14] == pytest.approx((0.0575, 0.008, 0.0015))
    assert utility.points[14][1] == spec.BODY_WIDTH / 1000.0
    assert utility.points[14][2] == spec.BODY_THICKNESS / 2000.0
    assert utility.points[15] == pytest.approx((0.20875, 0.080, 0.0))
    assert utility.points[16] == pytest.approx((0.20975, 0.080, 0.0))
    assert circles[1] == pytest.approx((0.4475, -0.200, 0.02, 0.4495, -0.200, 0.02))
    depth_parent = placements[-1]
    assert depth_parent.Orientation == "*Top"
    assert depth_parent.Position == drawing.DEPTH_PARENT_CENTER
    assert depth_parent.ScaleRatio == (1.0, 2.0)
    assert depth_parent.Angle == 0.0
    projected_radius = utility.points[16][0] - utility.points[15][0]
    assert projected_radius == pytest.approx(
        drawing.DEPTH_RADIUS_MM / 1000.0 * depth_parent.ScaleRatio[0] / depth_parent.ScaleRatio[1],
    )
    assert drawing.DEPTH_RADIUS_MM > math.hypot(spec.TICK_WIDTH / 2.0, spec.BODY_THICKNESS / 2.0)
    assert placements[0].Angle == placements[3].Angle == pytest.approx(math.pi)
    assert all(tuple(getattr(view.ScaleRatio, "value", view.ScaleRatio)) == drawing.DETAIL_SCALE
               for view in details.values())
    assert imports[-2][0] is details["A"]
    assert imports[-2][1]["keep"] is drawing.DETAIL_KEEP
    assert imports[-1][0] is details["B"]
    assert imports[-1][1]["keep"] is drawing.DEPTH_KEEP
    assert imports[-1][1]["dimensions_by_feature"] is spec.DRAWING_DIMENSIONS
    assert any(view is depth_parent for view in clean_views)
    assert any(view is details["B"] for view in clean_views)
