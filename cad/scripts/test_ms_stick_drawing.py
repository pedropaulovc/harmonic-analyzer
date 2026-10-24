"""Offline contracts for Option B scale placement and the V-engraved numerals."""

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

import _sketch as sketch

import _drawing_projection as drawing_projection
import _dxf_text as dxf_text
import build_ms_stick as builder
import draw_ms_stick as drawing
import ms_stick_callouts as callouts
import ms_stick_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import Box


def test_numeral_detail_ink_clears_border_and_placement_note() -> None:
    """Translate r4 native ink/extents, not guessed annotation anchor boxes.

    Evidence: 20261011T045740079Z run's layout-audit/ms-stick.json,
    ENGRAVING Detail F. Retaining scale and relative dimension placement makes
    these measured offsets reusable; acceptance is clearance, not coordinates.
    """
    dx = drawing.NUMERAL_CENTER[0] - 0.140
    dy = drawing.NUMERAL_CENTER[1] - 0.135
    for name, old_xy in (
        ("NumeralXGap", (0.075, 0.170)),
        ("NumeralYGap", (0.075, 0.155)),
    ):
        # A rigid move preserves witness geometry and space between callouts.
        assert math.dist(drawing.NUMERAL_KEEP[name],
                         (old_xy[0] + dx, old_xy[1] + dy)) < 1e-9
    assert drawing.DETAIL_SCALE == (6.0, 1.0)
    # The NUMERAL HEIGHT text sits wholly right of its own extension lines
    # (the r3 review saw them strike through the centred text).
    height_text_left = drawing.NUMERAL_KEEP["NumeralHeight"][0] - len("NUMERAL HEIGHT") * 0.00275 / 2.0
    right_extension = drawing.NUMERAL_CENTER[0] + spec.NUMERAL_HEIGHT_MM * drawing.DETAIL_SCALE[0] / 2000.0
    assert height_text_left - right_extension >= 0.005
    # The label's measured leader/witness start is farther left than PDF ink.
    end_gap_left = drawing.NUMERAL_KEEP["NumeralYGap"][0] - 0.0618528
    assert end_gap_left - 0.0127 >= 0.005
    title_and_scale = Box(
        0.1239223 + dx, 0.0721882 + dy,
        0.1552167 + dx, 0.0887072 + dy,
    )
    note_x, note_y = drawing.NUMERAL_NOTE_XY
    placement_note = Box(
        note_x - 0.0001881, note_y - 0.0135771,
        note_x + 0.0793988, note_y + 0.0001369,
    )
    assert title_and_scale.gap(placement_note) >= 0.004
    assert placement_note.ymax <= title_and_scale.ymin - 0.004
    assert placement_note.xmin >= 0.0127 + 0.005
    assert placement_note.ymin >= 0.0127 + 0.005


def test_numeral_font_note_frees_the_shop_single_stroke_font() -> None:
    """A V bit follows centrelines: the model's strokes are representative."""
    import gen_ms_stick_numerals_dxf as numeral_generator

    assert spec.DRAWING_NOTES == "NUMERALS: ANY SINGLE-STROKE SANS FONT"
    assert "SLDPRT" not in spec.DRAWING_NOTES and "DEJAVU" not in spec.DRAWING_NOTES
    assert sorted(numeral_generator.DIGIT_STROKES) == [str(digit) for digit in range(10)]
    for strokes in numeral_generator.DIGIT_STROKES.values():
        assert all(len(stroke) >= 2 for stroke in strokes)


def test_builder_authors_model_owned_numeral_placement_property(monkeypatch) -> None:
    """Exercise the builder's actual property call without executing geometry."""
    tree = ast.parse(Path(builder.__file__).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "apply_drawing_properties"
    ]
    assert len(calls) == 1
    authored = {}
    adapter = object()

    def apply(actual_adapter, part_name, properties):
        assert actual_adapter is adapter
        assert part_name == builder.PART_NAME
        authored.update(properties)

    monkeypatch.setattr(builder, "apply_drawing_properties", apply)
    expression = ast.Expression(body=calls[0])
    eval(compile(expression, builder.__file__, "eval"), vars(builder), {"adapter": adapter})
    assert authored["Numeral Placement Note"] == spec.NUMERAL_PLACEMENT_NOTE
    assert authored["Manufacturing Notes"] == spec.DRAWING_NOTES
    assert "Numeral Tool Note" not in authored
    assert "Scale End Note" not in authored
    assert spec.NUMERAL_PLACEMENT_NOTE == (
        "NUMERALS 0-9 RIGHT OF FULL TICKS;\n"
        "10 LEFT OF FINAL FULL TICK.\n"
        "BOTH USE SHOWN GAPS"
    )


def test_current_identity_and_drawing_paths() -> None:
    assert builder.PART_NAME == drawing.PART_STEM == "ms-stick"
    assert DRAWINGS_BY_NAME["ms_stick"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.name == "ms-stick.SLDDRW"
    assert drawing.PDF.name == "ms-stick.pdf"
    assert drawing.PNG.name == "ms-stick_drawing.png"
    assert [path.name for path in spec.NUMERAL_LAYER_DXFS] == [
        "ms-stick-numerals-1.dxf", "ms-stick-numerals-2.dxf", "ms-stick-numerals-3.dxf",
    ]


def test_option_b_preserves_blank_and_grooves_and_relocates_whole_scale() -> None:
    # 2026-10-23 owner ruling: 202 blank, scale zero and stations unchanged.
    assert (spec.BODY_LENGTH, spec.BODY_WIDTH, spec.BODY_THICKNESS) == (202.0, 8.0, 3.0)
    assert (spec.TICK_WIDTH, spec.TICK_DEPTH, spec.TICK_LENGTH) == (0.4, 0.5, 3.0)
    assert (spec.MINOR_TICK_LENGTH, spec.HALF_TICK_LENGTH) == (1.8, 4.0)
    assert spec.DIVISION_COUNT == 11 and spec.MINOR_PER_DIVISION == 10
    assert spec.SCALE_END_MARGIN == pytest.approx(3.5)
    assert spec.SCALE_START_X == pytest.approx(56.5)
    assert spec.NUMERALS_BBOX == (57.300, 1.770, 197.700, 4.400)
    assert spec.SCALE_SPAN == pytest.approx(
        (spec.DIVISION_COUNT - 1) * spec.DIVISION_SPACING, rel=0.0, abs=1e-12,
    )
    assert spec.SCALE_START_X + spec.SCALE_SPAN + spec.SCALE_END_MARGIN == pytest.approx(
        spec.BODY_LENGTH, rel=0.0, abs=1e-12,
    )
    assert (spec.NUMERAL_HEIGHT_MM, spec.NUMERAL_GAP_MM, spec.NUMERAL_ROTATION_DEG) == (2.0, 0.6, 90)
    for name in ("BODY_LENGTH", "BODY_WIDTH", "BODY_THICKNESS", "SCALE_START_X",
                 "TICK_WIDTH", "TICK_DEPTH", "NUMERAL_LAYER_DXFS"):
        assert getattr(builder, name) == getattr(spec, name)


def test_every_printed_size_is_owned_and_precisioned_by_model() -> None:
    assert builder.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert builder.DRAWING_PRECISION is spec.DRAWING_PRECISION
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP)
            | set(drawing.NUMERAL_KEEP) | set(drawing.DEPTH_KEEP)
            | set(drawing.NUMERAL_DEPTH_KEEP)
            | set().union(*(set(row[4]) for row in drawing.LENGTH_DETAILS)))
    assert kept == marked == set(spec.DRAWING_VALUES_BY_NAME) == set(spec.DRAWING_PRECISION_BY_NAME)
    # The overall length is noncritical: one place, the .X title-block band.
    assert {name: places for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places != 2} == {
        "BodyLength": 1}
    assert set(spec.DRAWING_TOLERANCES) <= marked
    assert {"BodyThickness", "TickDepth", "FullTickLength", "MinorTickLength",
            "HalfTickLength", "FullTickPitch", "MinorTickPitch", "NumeralHeight",
            "NumeralXGap", "NumeralYGap", "NumeralDepth"} <= marked
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
    """Noncumulative pitch allows one station error, not ten chained errors.

    The overall length takes the .X title block (2026-10-23 owner ruling);
    the graduation width is a MIN limit, so the land bounds the widest
    groove that still leaves the last graduation whole."""
    values, bands = spec.DRAWING_VALUES_BY_NAME, spec.DRAWING_TOLERANCES
    assert "BodyLength" not in bands
    assert spec.DRAWING_PRECISION_BY_NAME["BodyLength"] == 1
    stock_min = values["BodyLength"] - spec.TITLE_BLOCK_X_TOLERANCE_MM
    last_center_max = (
        values["ScaleStartX"] + bands["ScaleStartX"]
        + (spec.DIVISION_COUNT - 1) * values["FullTickPitch"] + bands["FullTickPitch"]
    )
    assert stock_min == pytest.approx(201.2)
    assert last_center_max == pytest.approx(198.6)
    # Rule 17 at the worst case: the widest stated groove keeps 2.0+ to the end.
    end_land = stock_min - (last_center_max + spec.GRADUATION_WIDTH_MAX_MM / 2.0)
    assert end_land == pytest.approx(2.29) and end_land >= 2.0
    # The stated 0.62 MAX keeps neighbours apart on the 1.42 minor pitch even
    # with both stations at their band.
    land_min = spec.MINOR_SPACING - 2.0 * spec.GRADUATION_POSITION_TOLERANCE_MM - spec.GRADUATION_WIDTH_MAX_MM
    assert land_min == pytest.approx(0.70)
    assert spec.GRADUATION_WIDTH_CALLOUT == "0.62 MAX ON 1.42 PITCH"
    assert callouts.CALLOUTS["Tick0Width"].endswith(spec.GRADUATION_WIDTH_CALLOUT)
    last_edge_nominal = (
        values["ScaleStartX"] + (spec.DIVISION_COUNT - 1) * values["FullTickPitch"]
        + values["Tick0Width"] / 2.0
    )
    assert values["BodyLength"] - last_edge_nominal == pytest.approx(3.30)


def test_engraving_sizes_are_min_limits_and_graduation_depth_keeps_its_stock() -> None:
    """No mate needs a band on the engraving: width and both depths are
    single MIN limits (model value = printed limit) that hold the fill, and
    the graduation depth's ceiling is the stated 2.0 of stock under it."""
    assert spec.MIN_LIMIT_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert spec.MIN_LIMIT_DEVIATIONS_MM == {
        "Tick0Width": (0.0, spec.TICK_WIDTH),
        "TickDepth": (0.0, spec.TICK_DEPTH),
        "NumeralDepth": (0.0, spec.NUMERAL_DEPTH),
    }
    assert not set(spec.MIN_LIMIT_DEVIATIONS_MM) & set(spec.DRAWING_TOLERANCES)
    for name in spec.MIN_LIMIT_DEVIATIONS_MM:
        assert callouts.CALLOUTS[name].count("HOLDS ENAMEL FILL") == 1, name
    values, bands = spec.DRAWING_VALUES_BY_NAME, spec.DRAWING_TOLERANCES
    assert spec.GRADUATION_FLOOR_CALLOUT == "STOCK UNDER GROOVE 2.0 MIN"
    assert callouts.CALLOUTS["TickDepth"].endswith(spec.GRADUATION_FLOOR_CALLOUT)
    # The V depth states the same stock under it, so it is bounded too.
    assert callouts.CALLOUTS["NumeralDepth"].endswith(spec.NUMERAL_FLOOR_CALLOUT)
    assert spec.NUMERAL_FLOOR_CALLOUT == "STOCK UNDER 2.0 MIN"
    depth_max = values["BodyThickness"] - bands["BodyThickness"] - spec.GRADUATION_FLOOR_MIN_MM
    assert depth_max == pytest.approx(0.90)
    assert values["TickDepth"] == pytest.approx(0.50)
    assert values["TickDepth"] < depth_max




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
    monkeypatch.setattr(sketch, "check", lambda label, value: value)
    monkeypatch.setattr(builder, "set_sketch_direct_db", lambda *args: None)
    monkeypatch.setattr(builder, "dimension_between", dimension)
    monkeypatch.setattr(sketch, "dimension_between", dimension)
    monkeypatch.setattr(builder, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(builder, "name_last_feature", name_feature)
    monkeypatch.setattr(sketch, "_feature_by_name", lambda adapter, name: features[name])
    monkeypatch.setattr(sketch, "_display_dimensions", lambda feature, name: feature)
    monkeypatch.setattr(sketch, "_rename_dimensions", rename)
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
    imports = [
        name
        for node in ast.walk(tree)
        for name in (
            [node.module or ""] if isinstance(node, ast.ImportFrom)
            else [alias.name for alias in node.names] if isinstance(node, ast.Import)
            else []
        )
    ]
    assert not any(name.startswith((
        "build_", "solidworks", "_appearance", "_assembly", "_check", "_com",
        "_custom_properties", "_dimensions", "_drawing", "_feature_tree",
        "_holes", "_part_", "_rebuild", "_session", "_sketch", "_visibility",
    )) for name in imports)
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
        return SimpleNamespace(centre=points[:3], radius=math.dist(points[:3], points[3:]),
                               Select4=lambda append, data: data.View is active["parent"])

    def create_detail(*args):
        label = args[6]
        parent = active["parent"]
        scale = drawing.DEPTH_SCALE if label == "B" else drawing.DETAIL_SCALE
        assert args[2:] == (0.0, 0, *scale, label, 1, True, False, False, 5)
        parent.Circles.append(DetailCircle(label))
        detail = make_view(args[:2], scale, 0.0646, parent.Orientation)
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
        SketchManager=SimpleNamespace(CreateCircle=circle, AddToDB=False),
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: SimpleNamespace(View=None)),
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

    monkeypatch.setattr(drawing_projection, "_com_invoke", invoke)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "native_circle_geometry", lambda circle, label: (circle.centre, circle.radius))
    # The fake has no COM property marshaller: store the SAFEARRAY payload.
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "view_name", lambda adapter, view: view.GetName2())
    for name in (
        "read_required_properties", "create_blank_drawing_sheets", "stamp_drawing_summary",
        "_assert_dimension_contract",
        "rebuild_drawing",
    ):
        monkeypatch.setattr(drawing, name, lambda *args, **kwargs: None)
    required_properties, linked_notes = [], []
    monkeypatch.setattr(
        drawing, "read_required_properties",
        lambda model, properties, *, required: required_properties.extend(required),
    )
    monkeypatch.setattr(
        drawing, "add_property_linked_note",
        lambda adapter, name, x, y: linked_notes.append((active["sheet"], name, (x, y))),
    )
    monkeypatch.setattr(
        drawing, "set_hidden_lines_removed", lambda adapter, view: clean_views.append(view),
    )

    def curate(adapter, view, **kwargs):
        imports.append((view, kwargs))
        if kwargs["keep"] is drawing.NUMERAL_DEPTH_KEEP:
            dimension = SimpleNamespace(
                FullName="NumeralDepth@Numerals@ms-stick",
                SystemValue=spec.NUMERAL_DEPTH / 1000.0,
            )
            display = SimpleNamespace(GetDimension2=lambda config: dimension)
            return [SimpleNamespace(GetSpecificAnnotation=lambda: display)]
        return []

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "part_sketches_shown", lambda *args, **kwargs: nullcontext())
    profiles = []
    section_moves = []

    def create_section(adapter, parent, **kwargs):
        definition = SimpleNamespace(
            SetDisplayOnlySurfaceCut=lambda value: setattr(definition, "surface", value),
            GetDisplayOnlySurfaceCut=lambda: definition.surface,
            GetPartialSection=lambda: kwargs.get("partial", False),
        )
        # Start displaced so the real G-G helper must move the native view and
        # re-project the physical centre; make_view's model frame is in metres.
        initial_xy = (kwargs["view_xy"][0] + 0.006, kwargs["view_xy"][1] - 0.004)
        section = make_view(initial_xy, kwargs["scale"], drawing.NUMERAL_SECTION_X / 1000.0, "*Top")

        def set_view_position(position, move_children):
            assert move_children is False
            target = tuple(position)
            dx, dy = (target[index] - section.Position[index] for index in range(2))
            transform = section.ModelToViewTransform
            transform.offsets = (transform.offsets[0] + dx, transform.offsets[1] + dy,
                                 transform.offsets[2])
            section.Position = target
            section_moves.append((section, target, move_children))
            return True

        section.SetViewPosition = set_view_position
        section.GetSection = lambda: definition
        profiles.append((active["sheet"], parent, kwargs, section))
        return section

    monkeypatch.setattr(drawing, "create_section_view", create_section)

    async def finalize(adapter, outputs, **kwargs):
        assert kwargs["expected_sheet_names"] == drawing.SHEET_NAMES
        assert set(kwargs["sheet_layouts"]) == set(drawing.SHEET_NAMES)
        return {"slddrw": str(outputs.slddrw)}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    assert asyncio.run(drawing.build(adapter)) == {"slddrw": str(drawing.OUTPUTS.slddrw)}
    assert source.read_bytes() == b"offline source sentinel"
    assert "Numeral Placement Note" in required_properties
    assert "Scale End Note" not in required_properties
    assert ("ENGRAVING", "Numeral Placement Note", drawing.NUMERAL_NOTE_XY) in linked_notes
    assert "Numeral Tool Note" not in required_properties
    assert all(name != "Numeral Tool Note" for _sheet, name, _xy in linked_notes)
    assert ("BAR", "Manufacturing Notes", (0.045, 0.075)) in linked_notes
    assert len(profiles) == 1
    sheet, profile_parent, profile_args, profile = profiles[0]
    assert sheet == "ENGRAVING"
    assert profile_parent.Position == drawing.NUMERAL_PROFILE_PARENT_CENTER
    assert profile_parent.ScaleRatio == drawing.SHEET_SCALE
    assert not profile_args.get("partial") and profile_args["section_label"] == "G"
    assert profile_args["view_xy"] == drawing.NUMERAL_PROFILE_CENTER
    assert profile_args["scale"] == drawing.NUMERAL_PROFILE_SCALE == (10.0, 1.0)
    # The cutting line crosses the whole bar width at the zero's mid-height.
    start, end = utility.points[15:17]
    assert start == pytest.approx((drawing.NUMERAL_SECTION_X / 1000.0, -0.004, 0.0))
    assert end == pytest.approx((drawing.NUMERAL_SECTION_X / 1000.0, 0.012, 0.0))
    assert tuple(profile.ScaleRatio) == drawing.NUMERAL_PROFILE_SCALE
    assert profile.UseParentScale is False
    assert len(section_moves) == 1
    moved_profile, moved_xy, move_children = section_moves[0]
    assert moved_profile is profile and move_children is False
    assert moved_xy == pytest.approx(drawing.NUMERAL_PROFILE_CENTER)
    assert profile.Position == pytest.approx(drawing.NUMERAL_PROFILE_CENTER)
    numeral_depth_imports = [
        (view, args) for view, args in imports if args["keep"] is drawing.NUMERAL_DEPTH_KEEP
    ]
    assert len(numeral_depth_imports) == 1
    depth_import_view, depth_import_args = numeral_depth_imports[0]
    # The V depth is dimensioned where the V reads: on section G-G.
    assert depth_import_view is profile
    assert depth_import_args["dimensions_by_feature"] is spec.DRAWING_DIMENSIONS
    assert spec.DRAWING_DIMENSIONS["Numerals"] == set(depth_import_args["keep"])
    assert not profile.GetSection().GetDisplayOnlySurfaceCut()
    assert any(view is profile for view in clean_views)
    assert len(utility.points) == 22  # six fences, profile endpoints, centre and placement readback
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
        scale = drawing.DEPTH_SCALE if label == "B" else drawing.DETAIL_SCALE
        assert tuple(getattr(detail.ScaleRatio, "value", detail.ScaleRatio)) == scale
        projection_index = 3 * index + (4 if label == "B" else 0)
        assert utility.points[projection_index] == pytest.approx(model_xyz)
        projected = parent.ModelToViewTransform.apply(model_xyz)
        center = (projected[0], projected[1], 0.0)
        rim = (center[0] + radius / 2000.0, center[1], 0.0)
        assert utility.points[projection_index + 1] == pytest.approx(center)
        assert utility.points[projection_index + 2] == pytest.approx(rim)
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


def test_graduation_location_chords_terminate_at_groove_centres() -> None:
    zero = spec.REFERENCE_DIMENSIONS["ScaleStartReference"]
    assert zero[2] == (spec.SCALE_START_X, spec.BODY_WIDTH)
    for feature, spacing in (
        ("FullPitchReference", spec.DIVISION_SPACING),
        ("MinorPitchReference", spec.MINOR_SPACING),
    ):
        _, start, end = spec.REFERENCE_DIMENSIONS[feature]
        assert start == zero[2]
        assert end == (spec.SCALE_START_X + spacing, spec.BODY_WIDTH)


def test_numeral_fence_contains_real_full_tick_endpoint() -> None:
    centre = (
        spec.SCALE_START_X + spec.TICK_WIDTH / 2.0
        + spec.NUMERAL_GAP_MM + spec.NUMERAL_HEIGHT_MM / 2.0,
        spec.BODY_WIDTH - spec.TICK_LENGTH - spec.NUMERAL_GAP_MM,
    )
    endpoint = (spec.SCALE_START_X, spec.BODY_WIDTH - spec.TICK_LENGTH)
    assert math.dist(centre, endpoint) < drawing.NUMERAL_RADIUS_MM / 2.0


def test_local_length_fences_include_owned_ticks_without_cross_strip_routing() -> None:
    lengths = {
        "FullTickLength": spec.TICK_LENGTH,
        "MinorTickLength": spec.MINOR_TICK_LENGTH,
        "HalfTickLength": spec.HALF_TICK_LENGTH,
    }
    def outside(centre, radius, x0, x1, y0, y1):
        nearest = (min(max(centre[0], x0), x1), min(max(centre[1], y0), y1))
        return math.dist(centre, nearest) > radius

    def inside(centre, radius, x0, x1, y0, y1):
        return all(math.dist(centre, corner) < radius for corner in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)))

    half = spec.TICK_WIDTH / 2.0
    for label, _parent, detail, model, keep, diameter in drawing.LENGTH_DETAILS:
        name = next(name for name in keep if name in lengths)
        assert keep[name][0] < detail[0] - diameter * drawing.DETAIL_SCALE[0] / 1000.0
        if label != "D":
            assert diameter > math.hypot(half, lengths[name] / 2.0)
            assert model[1] == pytest.approx(spec.BODY_WIDTH - lengths[name] / 2.0)
            continue
        # Exact fence (EXACT_FENCES): sheet radius radius_mm / 2 at the 1:2
        # parent, so the model radius is radius_mm.
        assert label in drawing.EXACT_FENCES
        radius = diameter
        tick = spec.SCALE_START_X + spec.MINOR_SPACING
        edge = spec.BODY_WIDTH
        assert inside(model, radius, tick - half, tick + half, edge - spec.MINOR_TICK_LENGTH, edge)
        assert outside(model, radius, spec.SCALE_START_X - half, spec.SCALE_START_X + half,
                       edge - spec.TICK_LENGTH, edge)  # tick zero stays out
        nxt = spec.SCALE_START_X + 3 * spec.MINOR_SPACING
        assert outside(model, radius, nxt - half, nxt + half, edge - spec.MINOR_TICK_LENGTH, edge)
        assert 2.0 * math.sqrt(radius**2 - (edge - model[1]) ** 2) >= 2.0  # the edge reads as an edge


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
            adapter, parent,
            model_center=(spec.SCALE_START_X / 1000.0, 0.004, 0.0),
            view_xy=drawing.DETAIL_CENTER, radius_mm=drawing.DETAIL_RADIUS_MM,
            detail_label="A",
        )


@pytest.mark.parametrize("fault, match", [
    ("snapped", "moved or changed radius"),
    ("unselectable", "cannot select its fence"),
])
def test_exact_fence_refuses_a_snapped_or_unselected_circle(monkeypatch, fault, match) -> None:
    db_writes = []
    manager = SimpleNamespace(AddToDB=False)

    def create(*points):
        db_writes.append(manager.AddToDB)
        shift = 0.0002 if fault == "snapped" else 0.0
        return SimpleNamespace(centre=(points[0] + shift, points[1], points[2]),
                               radius=math.dist(points[:3], points[3:]),
                               Select4=lambda append, data: fault != "unselectable")

    manager.CreateCircle = create
    parent = SimpleNamespace(GetSketch=lambda: SimpleNamespace(
        ModelToSketchTransform=_StickAffine((1.0, 1.0, 1.0), (0.0, 0.0, 0.0))))
    document = SimpleNamespace(
        ActivateView=lambda name: True, ClearSelection2=lambda clear: None,
        SketchManager=manager,
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: SimpleNamespace(View=None)),
        CreateDetailViewAt4=lambda *args: pytest.fail("detail created from a bad fence"),
    )
    adapter = SimpleNamespace(currentModel=document,
                              swApp=SimpleNamespace(GetMathUtility=lambda: _StickMathUtility()))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "native_circle_geometry", lambda circle, label: (circle.centre, circle.radius))
    monkeypatch.setattr(drawing, "view_name", lambda *args: "offline-parent")
    monkeypatch.setattr(drawing, "model_point_in_view", lambda *args, **kwargs: (0.100, 0.200))
    with pytest.raises(RuntimeError, match=match):
        drawing._engraving_detail(
            adapter, parent, model_center=(0.06, 0.007, 0.0), view_xy=(0.22, 0.155),
            radius_mm=1.8, detail_label="D", exact=True)
    assert db_writes == [True]  # authored without sketch inference
    assert manager.AddToDB is False  # restored


def test_numeral_v_contract_is_independent_of_graduations() -> None:
    import math as _math

    assert spec.NUMERAL_DEPTH == 0.40
    assert spec.NUMERAL_V_INCLUDED_ANGLE_DEG == 30.0
    assert spec.NUMERAL_STROKE_WIDTH_MM == 0.24
    # A true V: the 15-degree walls leave under 0.03 mm of root at 0.40 deep.
    assert spec.NUMERAL_TIP_FLAT_MM == pytest.approx(
        0.24 - 0.80 * _math.tan(_math.radians(15.0)), abs=1e-12)
    assert 0.0 < spec.NUMERAL_TIP_FLAT_MM < 0.03
    assert spec.DRAWING_DIMENSIONS["Numerals"] == {"NumeralDepth"}
    assert spec.DRAWING_PRECISION["Numerals"] == {"NumeralDepth": 2}
    assert spec.DRAWING_VALUES_BY_NAME["NumeralDepth"] == spec.NUMERAL_DEPTH
    assert (spec.TICK_WIDTH, spec.TICK_DEPTH) == (0.4, 0.5)
    assert "GRADUATIONS ONLY" in callouts.CALLOUTS["TickDepth"]
    assert "ALL ENGRAVING" not in callouts.CALLOUTS["TickDepth"]
    assert callouts.CALLOUTS["NumeralDepth"].splitlines()[:3] == [
        "NUMERAL DEPTH", "30° INCLUDED V", "HOLDS ENAMEL FILL"]
    assert not hasattr(spec, "NUMERAL_TOOL_NOTE")
    assert not hasattr(drawing, "NUMERAL_TOOL_NOTE_XY")


def test_every_tight_band_states_its_function() -> None:
    """Rule 4: a band tighter than the title block names its mate or purpose."""
    reasons = {
        "BodyWidth": "SLIDES IN MS-STOP-BLOCK\nMHA-MS-02 REBATE",
        "BodyThickness": "SLIDES IN MS-STOP-BLOCK\nMHA-MS-02 REBATE",
        "ScaleStartX": "SETS CH-AMPLITUDE-BAR\nMHA-CH-01 STATIONS",
        "FullTickPitch": "SETS CH-AMPLITUDE-BAR\nMHA-CH-01 STATIONS",
        "MinorTickPitch": "SETS CH-AMPLITUDE-BAR\nMHA-CH-01 STATIONS",
    }
    assert set(reasons) == set(spec.DRAWING_TOLERANCES)
    for name, reason in reasons.items():
        assert callouts.CALLOUTS[name].endswith(reason), name
    for name in ("BodyLength", "FullTickLength", "MinorTickLength", "HalfTickLength",
                 "NumeralHeight", "NumeralXGap", "NumeralYGap", *spec.MIN_LIMIT_DEVIATIONS_MM):
        assert name not in spec.DRAWING_TOLERANCES, name


class _NumeralDefinition:
    def __init__(self, depth=None, drafted=True, outward=False, angle_deg=15.0):
        self.depth = spec.NUMERAL_DEPTH if depth is None else depth
        self.drafted, self.outward, self.angle_deg = drafted, outward, angle_deg

    def GetDepth(self, forward):  # noqa: N802 - COM member name
        return self.depth / 1000.0

    def GetDraftWhileExtruding(self, forward):  # noqa: N802 - COM member name
        return self.drafted

    def GetDraftOutward(self, forward):  # noqa: N802 - COM member name
        return self.outward

    def GetDraftAngle(self, forward):  # noqa: N802 - COM member name
        return math.radians(self.angle_deg)


class _CutSeat:
    """Seat fake: FeatureCut3 removes a volume chosen per form."""

    def __init__(self, removed_by_form, arity=26):
        self.removed_by_form, self.arity = removed_by_form, arity
        self.volume, self.cuts, self.selected, self.undone = 4800.0, [], [], 0
        seat = self

        class Model:
            FeatureManager = SimpleNamespace(FeatureCut3=seat.cut)
            Extension = SimpleNamespace(SelectByID2=lambda *args: seat.selected.append(args[:2]) or True)

            @staticmethod
            def ClearSelection2(clear):  # noqa: N802 - COM member name
                return None

            @staticmethod
            def EditUndo2(steps):  # noqa: N802 - COM member name
                seat.undone += steps
                seat.volume = 4800.0

        async def mass():
            return SimpleNamespace(is_success=True, data=SimpleNamespace(volume=seat.volume))

        def attempt(fn):
            try:
                return fn(), None
            except Exception as exc:  # noqa: BLE001
                return None, exc

        self.adapter = SimpleNamespace(currentModel=Model, get_mass_properties=mass, _attempt_with_error=attempt)

    def cut(self, *args):
        if len(args) != self.arity:
            raise TypeError(f"{len(args)} arguments")
        self.cuts.append(args)
        removed = self.removed_by_form.get((args[2], args[9], args[7]))
        if removed is None:
            return None
        self.volume -= removed
        return object()


def _patch_cut_bookkeeping(monkeypatch, names):
    import solidworks_mcp.adapters.pywin32_adapter as pywin32_adapter

    feature = SimpleNamespace(GetDefinition=lambda: _NumeralDefinition())
    monkeypatch.setattr(pywin32_adapter, "null_callout", lambda: None)
    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(builder, "_feature_by_name", lambda actual, name: feature)
    monkeypatch.setattr(builder, "name_last_feature", lambda actual, name: name)
    monkeypatch.setattr(builder, "dump_dimensions", lambda actual, name: [
        {"index": 0, "full_name": f"D3@{name}", "value_mm": 261.8},
        {"index": 1, "full_name": f"D1@{name}", "value_mm": spec.NUMERAL_DEPTH},
        {"index": 2, "full_name": f"D2@{name}", "value_mm": spec.NUMERAL_DEPTH},
    ])
    monkeypatch.setattr(builder, "name_dimensions", lambda actual, feature, values: names.append((feature, values)))


def test_first_layer_finds_the_form_that_removes_exactly_the_v(monkeypatch) -> None:
    v = spec.NUMERAL_LAYER_VOLUMES_MM3[0]
    # Keyed (reversed, Ddir1, drafted): Ddir1 False flares (2x), Ddir1 True is
    # the V -- the volume, not the flag, decides.
    seat = _CutSeat({(True, False, True): 3.35 * v / 1.56, (True, True, True): v})
    names = []
    _patch_cut_bookkeeping(monkeypatch, names)
    jobs = []
    form = asyncio.run(builder._cut_numerals(seat.adapter, jobs, "Numerals", None, seat.volume))
    assert [(args[2], args[9]) for args in seat.cuts] == [(True, False), (True, True)]
    assert seat.undone == 1 and seat.selected[0] == ("NumeralsSketch", "SKETCH")
    assert form == builder._v_cut_args(True)
    args = seat.cuts[-1]
    # Single-ended, reversed into the bar, blind, both walls drafted 15 deg.
    assert args[:7] == (True, False, True, 0, 0, spec.NUMERAL_DEPTH / 1000.0, 0.0)
    assert args[7] is True and args[11] == pytest.approx(math.radians(15.0))
    assert names == [("Numerals", [None, "NumeralDepth"])]
    assert jobs == [("NumeralDepth@Numerals", '"NumeralDepth"')]
    # Later layers reuse the proved form without re-probing.
    builder_form = asyncio.run(builder._cut_numerals(seat.adapter, jobs, "Numerals2", form, seat.volume))
    assert builder_form is form and seat.cuts[-1] == form
    assert seat.selected[-1] == ("Numerals2Sketch", "SKETCH")
    assert builder.numeral_feature_names() == ["Numerals", "Numerals2", "Numerals3"]


def test_no_form_that_removes_the_v_fails_with_discriminating_probes(monkeypatch) -> None:
    seat = _CutSeat({(True, False, True): 3.0, (True, False, False): 3.1352})
    _patch_cut_bookkeeping(monkeypatch, [])
    with pytest.raises(RuntimeError, match="no FeatureCut3 form removed") as raised:
        asyncio.run(builder._cut_numerals(seat.adapter, [], "Numerals", None, seat.volume))
    message = str(raised.value)
    assert "single-ended reversed, Ddir1 False: removed 3.0000" in message
    assert "single-ended reversed, Ddir1 True: FeatureCut3 returned None" in message
    assert "probe undrafted reversed: created, removed 3.1352" in message
    assert "probe undrafted default direction: FeatureCut3 returned None" in message
    # Every cut a form or probe made was undone.
    assert seat.volume == 4800.0


def test_numeral_readback_requires_one_draft_sense(monkeypatch) -> None:
    senses = iter([False, True, False])
    monkeypatch.setattr(builder, "_assert_one_numeral_cut", lambda adapter, name: next(senses))
    with pytest.raises(RuntimeError, match="disagree on draft direction"):
        builder._assert_numeral_cut(object())


@pytest.mark.parametrize("proved", [None, True, False])
def test_numeral_readback_holds_the_volume_proved_sense(monkeypatch, proved) -> None:
    monkeypatch.setattr(builder, "_assert_one_numeral_cut", lambda adapter, name: True)
    if proved is False:
        with pytest.raises(RuntimeError, match="sense flipped"):
            builder._assert_numeral_cut(object(), proved)
    else:
        assert builder._assert_numeral_cut(object(), proved) is True


@pytest.mark.parametrize("definition,message", [
    (_NumeralDefinition(depth=spec.TICK_DEPTH), "expected depth"),
    (_NumeralDefinition(drafted=False), "draft on every wall"),
    (_NumeralDefinition(angle_deg=30.0), "draft on every wall"),
])
def test_native_numeral_readback_refuses_square_or_wrong_v(monkeypatch, definition, message) -> None:
    feature = SimpleNamespace(GetDefinition=lambda: definition)
    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(builder, "_feature_by_name", lambda actual, name: feature)
    with pytest.raises(RuntimeError, match=message):
        builder._assert_numeral_cut(object())


@pytest.mark.parametrize("removed", [0.0, 2.0 * spec.NUMERAL_VOLUME_MM3])
def test_numeral_volume_gate_refuses_missed_or_square_cuts(removed) -> None:
    allowance = builder.NUMERAL_VOLUME_ALLOWANCE_MM3
    builder._check_numeral_volume("all numerals", spec.NUMERAL_VOLUME_MM3, spec.NUMERAL_VOLUME_MM3, allowance)
    with pytest.raises(RuntimeError, match="V cut removed"):
        builder._check_numeral_volume("all numerals", removed, spec.NUMERAL_VOLUME_MM3, allowance)


@pytest.mark.parametrize("layer", range(len(spec.NUMERAL_LAYER_VOLUMES_MM3)))
def test_numeral_layer_gate_refuses_one_dropped_stroke(layer) -> None:
    expected = spec.NUMERAL_LAYER_VOLUMES_MM3[layer]
    allowance = builder.NUMERAL_LAYER_ALLOWANCES_MM3[layer]
    # Run 20261024T020813087Z-49ce2da4: the seat read each layer within 7e-4.
    builder._check_numeral_volume("layer", expected + 7e-4, expected, allowance)
    builder._check_numeral_volume("layer", expected - 7e-4, expected, allowance)
    with pytest.raises(RuntimeError, match="dropped stroke"):
        builder._check_numeral_volume("layer", expected - spec.NUMERAL_LAYER_MIN_STROKE_MM3[layer], expected, allowance)
    # The aggregate gate is no looser than its tightest layer.
    assert builder.NUMERAL_VOLUME_ALLOWANCE_MM3 <= allowance


def test_min_limit_refuses_a_nominal_that_is_not_the_printed_limit(monkeypatch) -> None:
    dimension = SimpleNamespace(SystemValue=(spec.TICK_DEPTH + 0.1) / 1000.0, Tolerance=None)
    monkeypatch.setattr(builder, "_named_dimension", lambda adapter, feature, name: (None, dimension))
    with pytest.raises(RuntimeError, match="is not the limit"):
        builder._min_limit(object(), "Tick0Cut", "TickDepth")


class _TextDisplay:
    """Display-dimension fake: one text lane per part, optionally dropping writes."""

    def __init__(self, text: str = "", keeps: bool = True, tol_type: int = spec.MIN_LIMIT_TOL_TYPE):
        self.lanes, self.keeps = {callouts.CALLOUT_BELOW: text}, keeps
        self.dimension = SimpleNamespace(Tolerance=SimpleNamespace(Type=tol_type))

    def SetText(self, lane, text):
        if self.keeps:
            self.lanes[lane] = text

    def GetText(self, lane):
        return self.lanes.get(lane, "")

    def GetDimension2(self, config):
        return self.dimension


def test_part_authors_every_callout_on_its_own_feature(monkeypatch) -> None:
    displays, asked = {}, []

    def named(adapter, feature, names):
        asked.append(feature)
        return {name: (displays.setdefault(name, _TextDisplay()), None) for name in names}

    monkeypatch.setattr(builder, "_named_dimensions", named)
    builder.author_dimension_callouts(None)
    assert {name: display.GetText(callouts.CALLOUT_BELOW) for name, display in displays.items()} == callouts.CALLOUTS
    assert sorted(asked) == sorted(set(callouts.FEATURE_OF.values()))
    monkeypatch.setattr(builder, "_named_dimensions",
                        lambda adapter, feature, names: {name: (_TextDisplay(keeps=False), None) for name in names})
    with pytest.raises(RuntimeError, match="callout did not persist"):
        builder.author_dimension_callouts(None)


def _imported(monkeypatch, displays):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, annotation: annotation.name)
    return [SimpleNamespace(name=name, GetSpecificAnnotation=lambda d=display: d)
            for name, display in displays.items()]


def test_drawing_reads_back_part_callouts_and_min_limit_types(monkeypatch) -> None:
    good = {name: _TextDisplay(text.replace("\n", "\r\n")) for name, text in callouts.CALLOUTS.items()}
    drawing._assert_imported_text_and_limits(None, _imported(monkeypatch, good))
    lost = {**good, "TickDepth": _TextDisplay(callouts.CALLOUTS["TickDepth"].rsplit("\n", 1)[0])}
    with pytest.raises(RuntimeError, match="differ from the part"):
        drawing._assert_imported_text_and_limits(None, _imported(monkeypatch, lost))
    retyped = {**good, "NumeralDepth": _TextDisplay(callouts.CALLOUTS["NumeralDepth"], tol_type=0)}
    with pytest.raises(RuntimeError, match="tolerance type"):
        drawing._assert_imported_text_and_limits(None, _imported(monkeypatch, retyped))
    with pytest.raises(RuntimeError, match="missing from the sheet"):
        drawing._assert_imported_text_and_limits(
            None, _imported(monkeypatch, {k: v for k, v in good.items() if k != "BodyWidth"}))


def test_dimension_contract_refuses_a_hidden_dimension_and_reruns_the_audit(monkeypatch) -> None:
    audited = []
    monkeypatch.setattr(drawing, "_assert_imported_text_and_limits", lambda adapter, annotations: audited.append("text"))
    monkeypatch.setattr(drawing, "assert_manufacturing_dimensions",
                        lambda adapter, annotations, values, precision, *, bands: audited.append("values"))
    shown = _imported(monkeypatch, {"BodyWidth": _TextDisplay(), "TickDepth": _TextDisplay()})
    for annotation in shown:
        annotation.Visible = 1
    drawing._assert_dimension_contract(None, shown)
    assert audited == ["text", "values"]
    shown[1].Visible = 0
    with pytest.raises(RuntimeError, match=r"hidden: \['TickDepth'\]"):
        drawing._assert_dimension_contract(None, shown)


class _Placed:
    """Sketch, math point and transform fakes: model = sketch + offset (m).
    ``native_skew`` makes the native MultiplyTransform disagree."""

    def __init__(self, points_mm, offset_m=(0.0, 0.0), native_skew=0.0, offset_z_m=0.0):
        self.points = [SimpleNamespace(X=x / 1000.0, Y=y / 1000.0, Z=0.0) for x, y in points_mm]
        self.offset = offset_m
        self.native_skew = native_skew
        self.native_calls = 0
        self.offset_z = offset_z_m
        inverse = SimpleNamespace(ArrayData=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
                                             offset_m[0], offset_m[1], offset_z_m, 1.0, 0.0, 0.0, 0.0))
        self.ModelToSketchTransform = SimpleNamespace(Inverse=lambda: inverse)

    def GetSpecificFeature2(self):
        return self

    def GetSketchPoints2(self):
        return self.points

    def CreatePoint(self, xyz):
        self.native_calls += 1
        x, y, z = xyz
        return SimpleNamespace(MultiplyTransform=lambda inverse: SimpleNamespace(
            ArrayData=(x + self.offset[0] + self.native_skew, y + self.offset[1], z + self.offset_z)))


def _place(monkeypatch, placed, path):
    monkeypatch.setattr(builder, "_feature_by_name", lambda adapter, name: placed)
    adapter = SimpleNamespace(swApp=SimpleNamespace(GetMathUtility=lambda: placed))
    builder._assert_layer_placement(adapter, "NumeralsSketch", path)


def test_layer_placement_reads_back_the_imported_sketch(monkeypatch) -> None:
    path = spec.NUMERAL_LAYER_DXFS[0]
    rings = [ring for ring, _closed in dxf_text.read_lwpolylines(path.read_text(encoding="ascii"))]
    vertices = [vertex for ring in rings for vertex in ring]
    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(builder, "double_array", tuple)
    placed = _Placed(vertices)
    _place(monkeypatch, placed, path)
    assert placed.native_calls == 1  # the transform is applied locally, not per vertex
    for offset in ((0.0, 0.01e-3), (0.5e-3, 0.0)):
        with pytest.raises(RuntimeError, match="not where"):
            _place(monkeypatch, _Placed(vertices, offset), path)
    with pytest.raises(RuntimeError, match="!= native"):
        _place(monkeypatch, _Placed(vertices, native_skew=1e-6), path)
    # Buried 0.10 below the ruled face: XY and volume would still match.
    with pytest.raises(RuntimeError, match="off the z=0 ruled face"):
        _place(monkeypatch, _Placed(vertices, offset_z_m=0.1e-3), path)
    # One interior numeral moved 0.05 along the bar: the layer bbox is unchanged.
    x0, _y0, x1, _y1 = dxf_text.bbox(rings)
    inner = [ring for ring in rings if x0 + 20 < min(x for x, _ in ring) and max(x for x, _ in ring) < x1 - 20]
    assert inner
    moved = [vertex for ring in rings if not any(ring is r for r in inner) for vertex in ring] + [
        (x + 0.05, y) for ring in inner for x, y in ring]
    assert dxf_text.bbox([moved]) == pytest.approx((x0, _y0, x1, _y1))
    with pytest.raises(RuntimeError, match="not where"):
        _place(monkeypatch, _Placed(moved), path)
    # Shared endpoints read back twice are fine; a dropped vertex is not.
    _place(monkeypatch, _Placed(vertices + vertices[:50]), path)
    with pytest.raises(RuntimeError, match="1 DXF vertices were not imported"):
        _place(monkeypatch, _Placed(vertices[1:]), path)


def test_feature_cut3_raises_for_both_failures(monkeypatch) -> None:
    def adapter(selected):
        model = SimpleNamespace(
            ClearSelection2=lambda flag: None,
            Extension=SimpleNamespace(SelectByID2=lambda *args: selected),
            FeatureManager=SimpleNamespace(FeatureCut3=lambda *args: None),
        )
        return SimpleNamespace(currentModel=model, _attempt_with_error=lambda fn: (fn(), "refused"))

    with pytest.raises(builder.FeatureCutRefused, match="returned None"):
        builder._feature_cut3(adapter(True), "NumeralsSketch", ())
    with pytest.raises(RuntimeError, match="select sketch") as failure:
        builder._feature_cut3(adapter(False), "NumeralsSketch", ())
    assert not isinstance(failure.value, builder.FeatureCutRefused)


@pytest.mark.parametrize("depth_m, angle_rad", [(math.nan, math.radians(15.0)), (0.0004, math.nan)])
def test_numeral_cut_readback_refuses_non_finite_readings(monkeypatch, depth_m, angle_rad) -> None:
    definition = SimpleNamespace(GetDepth=lambda first: depth_m, GetDraftWhileExtruding=lambda first: True,
                                 GetDraftAngle=lambda first: angle_rad, GetDraftOutward=lambda first: False)
    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(builder, "_feature_by_name",
                        lambda adapter, name: SimpleNamespace(GetDefinition=lambda: definition))
    with pytest.raises(RuntimeError, match="expected"):
        builder._assert_one_numeral_cut(None, "Numerals")


def _mass_seat(volume):
    async def mass():
        return SimpleNamespace(is_success=True, data=SimpleNamespace(volume=volume))

    return SimpleNamespace(get_mass_properties=mass)


def test_rebuild_and_save_hold_the_volume_to_one_stroke() -> None:
    built = 4805.9
    asyncio.run(builder._check_volume_unchanged(_mass_seat(built + 1e-4), "driven", built))
    with pytest.raises(RuntimeError, match="moved from the as-built"):
        asyncio.run(builder._check_volume_unchanged(
            _mass_seat(built + spec.NUMERAL_FINAL_MIN_STROKE_MM3), "saved", built))
    with pytest.raises(RuntimeError, match="returned volume nan"):
        asyncio.run(builder._check_volume_unchanged(_mass_seat(math.nan), "saved", built))


def test_numeral_volume_gate_refuses_a_non_finite_reading() -> None:
    with pytest.raises(RuntimeError, match="V cut removed"):
        builder._check_numeral_volume("layer", math.nan, spec.NUMERAL_LAYER_VOLUMES_MM3[0],
                                      builder.NUMERAL_LAYER_ALLOWANCES_MM3[0])


@pytest.mark.parametrize("full_name,value", [
    ("NumeralDepth@Tick0Cut@ms-stick", 0.0001),
    ("TickDepth@Numerals@ms-stick", 0.0001),
    ("NumeralDepth@Numerals@ms-stick", 0.0005),
])
def test_print_refuses_numeral_depth_bound_to_tick_or_old_value(monkeypatch, full_name, value) -> None:
    dimension = SimpleNamespace(FullName=full_name, SystemValue=value)
    display = SimpleNamespace(GetDimension2=lambda config: dimension)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    with pytest.raises(RuntimeError, match="wrong feature|V-engraved cut"):
        drawing._assert_numeral_depth_owner(annotation)


def test_numeral_definition_is_proved_after_drives_and_final_save() -> None:
    tree = ast.parse(Path(builder.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    save_index = next(
        index for index, node in enumerate(build.body)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Await)
        and isinstance(node.value.value, ast.Call)
        and isinstance(node.value.value.func, ast.Name)
        and node.value.value.func.id == "save_part_and_images"
    )
    after_save = build.body[save_index + 1]
    assert isinstance(after_save, ast.Expr) and isinstance(after_save.value, ast.Call)
    assert isinstance(after_save.value.func, ast.Name)
    assert after_save.value.func.id == "_assert_numeral_cut"
    # ...against the sense read when the per-layer volumes proved the V.
    assert [ast.unparse(arg) for arg in after_save.value.args] == ["adapter", "numeral_sense"]


@pytest.mark.parametrize("refusal", ["surface", "partial", "parent-scale", "scale", "centering"])
def test_numeral_profile_refuses_ignored_native_display_or_placement(monkeypatch, refusal) -> None:
    class Section:
        """Match the two writable native properties; the setter is VT_VOID."""
        def __init__(self):
            object.__setattr__(self, "UseParentScale", True)
            object.__setattr__(self, "ScaleRatio", (1.0, 2.0))
            object.__setattr__(self, "surface", True)
            object.__setattr__(self, "Position", drawing.NUMERAL_PROFILE_CENTER)

        def __setattr__(self, name, value):
            assert name in {"UseParentScale", "ScaleRatio"}
            if (name, refusal) in {("UseParentScale", "parent-scale"), ("ScaleRatio", "scale")}:
                return
            object.__setattr__(self, name, value)

        def GetSection(self):  # noqa: N802 - COM member name
            return self

        def SetDisplayOnlySurfaceCut(self, value):  # noqa: N802 - COM member name
            if refusal != "surface":
                object.__setattr__(self, "surface", value)
            return None

        def GetDisplayOnlySurfaceCut(self):  # noqa: N802 - COM member name
            return self.surface

        def GetPartialSection(self):  # noqa: N802 - COM member name
            return refusal == "partial"

        def SetViewPosition(self, position, move_children):  # noqa: N802 - COM member name
            return False

    section = Section()
    parent = object()
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "create_section_view", lambda *args, **kwargs: section)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda adapter, view, point, **kwargs: (
            (drawing.NUMERAL_PROFILE_CENTER[0] + 0.01, drawing.NUMERAL_PROFILE_CENTER[1])
            if view is section and refusal == "centering" else drawing.NUMERAL_PROFILE_CENTER
        ),
    )
    with pytest.raises(RuntimeError, match="full section|scale|centred"):
        drawing._numeral_profile(object(), parent)


def test_numeral_profile_scale_makes_the_v_readable_without_crowding() -> None:
    ratio = drawing.NUMERAL_PROFILE_SCALE[0] / drawing.NUMERAL_PROFILE_SCALE[1]
    assert spec.NUMERAL_DEPTH * ratio >= 4.0
    assert spec.NUMERAL_STROKE_WIDTH_MM * ratio >= 2.4
    # The full 8 x 3 bar section reads upright: thickness across, width up.
    half_width = spec.BODY_THICKNESS * ratio / 2000.0
    half_height = spec.BODY_WIDTH * ratio / 2000.0
    x, y = drawing.NUMERAL_PROFILE_CENTER
    profile = Box(x - half_width, y - half_height, x + half_width, y + half_height)
    assert (profile.xmin, profile.ymin, profile.xmax, profile.ymax) == pytest.approx(
        (0.265, 0.085, 0.295, 0.165),
    )
    numeral_right = drawing.NUMERAL_CENTER[0] + drawing.NUMERAL_RADIUS_MM * drawing.DETAIL_SCALE[0] / 1000.0
    depth_left = drawing.DEPTH_CENTER[0] - drawing.DEPTH_RADIUS_MM * drawing.DEPTH_SCALE[0] / 1000.0
    # The V depth callout (placed by its centre) sits between detail F's circle
    # and the section, its dimension line level with the V grooves.
    depth_x, depth_y = drawing.NUMERAL_DEPTH_KEEP["NumeralDepth"]
    half_text = max(map(len, callouts.CALLOUTS["NumeralDepth"].splitlines())) * 0.00275 / 2.0
    assert numeral_right < depth_x - half_text and depth_x + half_text < profile.xmin - 0.005
    assert profile.ymin < depth_y < profile.ymax
    assert depth_left - profile.xmax > 0.020
    # Detail B's callout block runs left from its keep point over G-G's
    # columns (rendered 0.292-0.380 m), so its shoulder, about 2.5 line
    # pitches below the keep height, must pass above the section.
    _tick_x, tick_y = drawing.DEPTH_KEEP["TickDepth"]
    assert tick_y - 2.5 * 0.0034 > profile.ymax + 0.008
    # The cutting line misses every graduation.
    minor = spec.SCALE_START_X + spec.MINOR_SPACING
    assert drawing.NUMERAL_SECTION_X - (minor + spec.TICK_WIDTH / 2.0) > 0.1
