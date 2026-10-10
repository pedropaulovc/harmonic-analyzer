"""Offline manufacturing contracts for the unchanged measuring-stick geometry."""

from __future__ import annotations

import asyncio
import ast
import math
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP) | set(drawing.SECTION_KEEP)
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
    def __init__(self, factors, offsets):
        self.factors = factors
        self.offsets = offsets

    def apply(self, xyz):
        return tuple(factor * value + offset for factor, value, offset in zip(
            self.factors, xyz, self.offsets, strict=True
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


@pytest.mark.parametrize(("cut_only", "partial", "error"), [
    (True, True, None),
    (False, True, "kept geometry beyond the cut"),
    (True, False, "not a partial section"),
])
def test_build_projects_metre_scale_fence_and_section_points(
    monkeypatch, tmp_path, cut_only, partial, error,
) -> None:
    """Run the real callers and projection math without opening a COM seat."""
    source = tmp_path / "ms-stick.SLDPRT"
    source.write_bytes(b"offline source sentinel")
    monkeypatch.setattr(drawing, "SOURCE", source)
    utility = _StickMathUtility()
    circles, notes, sections, views = [], [], [], []
    section_modes, rebuilds = [], []

    def set_cut_only(display):
        section_modes.append(display)
        # SetDisplayOnlySurfaceCut is void, including when persistence fails.

    def read_section_mode(value):
        assert rebuilds == ["engraving section cut face"]
        return value

    cut = SimpleNamespace(
        SetDisplayOnlySurfaceCut=set_cut_only,
        GetDisplayOnlySurfaceCut=lambda: read_section_mode(cut_only),
        GetPartialSection=lambda: read_section_mode(partial),
    )
    sketch_transform = _StickAffine((2.0, -3.0, 1.0), (0.03, 0.04, 0.02))

    def make_view(position, scale, center_x):
        ratio = scale[0] / scale[1]
        # Back followed by the recipe's pi rotation: +X and -Y on sheet.
        view = SimpleNamespace(
            Position=position, ScaleRatio=scale, Angle=0.0,
            GetName2=lambda: "offline-view",
            GetSketch=lambda: SimpleNamespace(ModelToSketchTransform=sketch_transform),
            ModelToViewTransform=_StickAffine(
                (ratio, -ratio, -ratio),
                (position[0] - ratio * center_x, position[1] + ratio * 0.004, 0.0),
            ),
        )
        views.append(view)
        return view

    detail = make_view(drawing.DETAIL_CENTER, drawing.DETAIL_SCALE, 0.0646)

    def circle(*points):
        circles.append(points)
        return object()

    def create_detail(*args):
        assert args == (*drawing.DETAIL_CENTER, 0.0, 0, *drawing.DETAIL_SCALE,
                        "A", 1, True, False, False, 5)
        return detail

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
        return make_view((x, y), scale, 0.1)

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
    monkeypatch.setattr(
        drawing, "rebuild_drawing", lambda adapter, *, label: rebuilds.append(label),
    )
    for name in (
        "read_required_properties", "create_blank_drawing_sheets", "stamp_drawing_summary",
        "set_hidden_lines_removed", "set_dimension_callouts", "assert_manufacturing_dimensions",
        "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *args, **kwargs: [])
    monkeypatch.setattr(drawing, "part_sketches_shown", lambda *args, **kwargs: nullcontext())

    def note(adapter, text, x, y):
        notes.append((text, x, y))
        return object()

    def section(adapter, view, **kwargs):
        sections.append((view, kwargs))
        return SimpleNamespace(GetSection=lambda: cut)

    async def finalize(adapter, outputs, **kwargs):
        return {"slddrw": str(outputs.slddrw)}

    monkeypatch.setattr(drawing, "add_note", note)
    monkeypatch.setattr(drawing, "create_section_view", section)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    if error is not None:
        with pytest.raises(RuntimeError, match=error):
            asyncio.run(drawing.build(adapter))
        assert section_modes == [True]
        assert source.read_bytes() == b"offline source sentinel"
        return
    assert asyncio.run(drawing.build(adapter)) == {"slddrw": str(drawing.OUTPUTS.slddrw)}
    assert section_modes == [True]
    assert rebuilds == ["engraving section cut face"]
    assert source.read_bytes() == b"offline source sentinel"
    assert len(utility.points) == 16
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
    assert len(circles) == 1
    assert circles[0] == pytest.approx((0.4546, -0.680, 0.02, 0.4676, -0.680, 0.02))
    assert utility.points[14] == pytest.approx((0.0563, 0.0065, 0.0))
    assert utility.points[15] == pytest.approx((0.0587, 0.0065, 0.0))
    start_x, start_y, _ = utility.points[14]
    end_x, end_y, _ = utility.points[15]
    assert start_y == end_y
    assert (spec.BODY_WIDTH - spec.TICK_LENGTH) / 1000.0 < start_y < spec.BODY_WIDTH / 1000.0
    assert start_x < (spec.SCALE_START_X - spec.TICK_WIDTH / 2.0) / 1000.0
    assert end_x > (spec.SCALE_START_X + spec.TICK_WIDTH / 2.0) / 1000.0
    assert len(sections) == 1
    section_view, arguments = sections[0]
    assert section_view is views[-1]
    assert section_view is not detail
    assert section_view.Position == drawing.DETAIL_PARENT_CENTER
    assert section_view.ScaleRatio == (1.0, 2.0)
    assert arguments["line_start"] == pytest.approx((0.20815, 0.23875))
    assert arguments["line_end"] == pytest.approx((0.20935, 0.23875))
    assert arguments["line_end"][0] - arguments["line_start"][0] == pytest.approx(
        (end_x - start_x) * section_view.ScaleRatio[0] / section_view.ScaleRatio[1],
    )
    assert arguments["view_xy"] == drawing.SECTION_CENTER
    assert arguments["section_label"] == "B"
    assert arguments["scale"] == drawing.DETAIL_SCALE
    assert arguments["partial"] is True
    assert views[1].Angle == views[-1].Angle == pytest.approx(math.pi)
    assert tuple(getattr(detail.ScaleRatio, "value", detail.ScaleRatio)) == drawing.DETAIL_SCALE
