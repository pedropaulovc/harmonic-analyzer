"""Blank-template SF symbols are preserved, never normalized or omitted."""

import _drawing_sheet_setup as sheet_setup

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from _drawing_prepared_template import TemplateSpec
import _drawing_template_defaults as defaults


class NativeDisplay:
    """Documented native array shapes; no derived bounds or GDI substitution."""

    def __init__(self):
        self.primitives = {
            "Line": [[0, 0, 0, 0, 0.12, 0.04, 0, 0.13, 0.045, 0]],
            "Arc": [
                [0, 0, 0, 0, 0.13, 0.04, 0, 0.12, 0.05, 0, 0.12, 0.04, 0, 0, 0, 1, 1]
            ],
            "PolyLine": [[0, 0, 0, 0, 0, 0, 2, 0.12, 0.04, 0, 0.13, 0.045, 0]],
            "Triangle": [[0.12, 0.04, 0, 0.13, 0.04, 0, 0.13, 0.05, 0, 1, 0]],
            "ArrowHead": [[0.12, 0.04, 0, 1, 0, 0, 0.002, 0.001, 0, 0, 0, 1]],
            "Polygon": [[0, 0, 0, 0, 3, 0.12, 0.04, 0, 0.13, 0.04, 0, 0.13, 0.05, 0]],
            "Ellipse": [],
            "Parabola": [],
            "Point": [],
        }
        self.text = {
            "value": "3.2",
            "position": [0.125, 0.045, 0],
            "height_m": 0.0013229166666666667,
            "font": "Century Gothic",
            "angle_rad": 0.125,
            "reference": 1,
            "inverted": 0,
            "plane": None,
            "line_spacing": 1.0,
        }
        self.leaders = [[0.12, 0.04, 0, 0.12, 0.035, 0, 0.115, 0.035, 0]]
        for kind, rows in self.primitives.items():
            setattr(self, f"Get{kind}Count", lambda rows=rows: len(rows))
        for kind, method in (
            ("Line", "GetLineAtIndex3"),
            ("Arc", "GetArcAtIndex2"),
            ("PolyLine", "GetPolylineAtIndex2"),
            ("Triangle", "GetTriangleAtIndex"),
            ("ArrowHead", "GetArrowHeadAtIndex2"),
            ("Polygon", "GetPolygonAtIndex"),
        ):
            setattr(self, method, lambda index, kind=kind: self.primitives[kind][index])
        for field, method in (
            ("value", "GetTextAtIndex"),
            ("position", "GetTextPositionAtIndex"),
            ("height_m", "GetTextHeightAtIndex"),
            ("font", "GetTextFontAtIndex"),
            ("angle_rad", "GetTextAngleAtIndex"),
            ("reference", "GetTextRefPositionAtIndex"),
            ("inverted", "GetTextInvertAtIndex"),
            ("plane", "GetTextPlaneAtIndex"),
            ("line_spacing", "GetTextLineSpacingAtIndex"),
        ):
            setattr(self, method, lambda index, field=field: self.text[field])

    def GetTextCount(self):
        return 1

    def GetPolylineSizeAtIndex2(self, index):
        return len(self.primitives["PolyLine"][index])

    def GetPolygonSizeAtIndex(self, index):
        return len(self.primitives["Polygon"][index])


@pytest.fixture
def scene(monkeypatch):
    calls = []
    state = {
        "symbol": 1,
        "texture": 4,
        "all_around": False,
        "position": (0.12, 0.04, 0),
        "text": {index: "3.2" if index == 5 else "" for index in range(1, 11)},
    }
    fmt = SimpleNamespace(
        TypeFaceName="Century Gothic",
        CharHeight=0.00635,
        CharHeightInPts=24,
        IsHeightSpecifiedInPts=lambda: False,
        WidthFactor=1.0,
        Bold=False,
        Italic=False,
        BackWards=False,
        CharSpacingFactor=1.0,
        Escapement=0.0,
        LineLength=0.015,
        LineSpacing=0.003,
        ObliqueAngle=0.0,
        Strikeout=False,
        Underline=False,
        UpsideDown=False,
        Vertical=False,
    )

    def count():
        calls.append("GetTextCount")
        return 2

    def text(index):
        assert calls and "GetTextCount" in calls
        calls.append(index)
        return state["text"][index]

    def all_around():
        assert state["symbol"] in {0, 2, 9}
        calls.append("all_around")
        return state["all_around"]

    def texture():
        assert state["symbol"] in {7, 8}
        calls.append("texture")
        return state["texture"]

    specific = SimpleNamespace(
        GetSymbol=lambda: state["symbol"],
        GetTextCount=count,
        GetText=text,
        GetSymbolAllAround=all_around,
        GetSymbolSurfaceTexture=texture,
        GetDirectionOfLay=lambda: 0,
        Orientation=3,
        GetAngle=lambda: 0.125,
        ProfileDirection=0,
        ProfileAngle=0.25,
        GOSTNotation=False,
        GOSTDefaultSymbol=False,
        IsAttached=lambda: False,
        HasExtraLeader=lambda: False,
    )
    annotation = SimpleNamespace(
        GetType=lambda: 7,
        GetSpecificAnnotation=lambda: specific,
        GetPosition=lambda: state["position"],
        Visible=1,
        GetTextFormatCount=lambda: 1,
        GetTextFormat=lambda index: fmt,
        GetUseDocTextFormat=lambda index: True,
    )
    specific.GetAnnotation = lambda: annotation
    data = NativeDisplay()
    data.text["height_m"] = fmt.CharHeight
    annotation.GetDisplayData = lambda: data
    annotation.GetName = lambda: "generated SF"
    annotation.GetLeaderCount = lambda: len(data.leaders)
    annotation.GetMultiJogLeaderCount = lambda: 0
    annotation.GetLeaderStyle = lambda: 2
    annotation.GetLeaderPointsAtIndex = lambda index: data.leaders[index]
    edge_note = SimpleNamespace(
        GetText=lambda: sheet_setup._METRIC_EDGE_BREAK_NOTE,
        PropertyLinkedText="",
        GetExtent=lambda: (0.2, 0.04, 0, 0.3, 0.045, 0),
        GetTextJustification=lambda: 1,
        GetTextVerticalJustification=lambda: 1,
        LockPosition=True,
    )
    edge = SimpleNamespace(
        GetType=lambda: 6, GetSpecificAnnotation=lambda: edge_note, Visible=1
    )

    @dataclass
    class NoteBounds:
        name: str = "generated edge-break"
        kind: int = 6

    annotations = [edge, annotation, annotation]
    view = SimpleNamespace(GetAnnotations=lambda: annotations)
    sheet = SimpleNamespace(
        GetProperties2=lambda: (2, 12, 2, 1, 0, 0.4318, 0.2794, 1),
        SheetFormatVisible=True,
    )
    model = SimpleNamespace(
        GetCurrentSheet=lambda: sheet,
        GetFirstView=lambda: view,
        GetViews=lambda: ((view,),),
        GetEditSheet=lambda: True,
        GetUserPreferenceIntegerValue=lambda key: {263: 4, 47: 0, 49: 2}[key],
        Extension=SimpleNamespace(GetUserPreferenceInteger=lambda *args: 2),
    )
    adapter = SimpleNamespace(
        currentModel=model,
        _get_attr_or_call=lambda obj, name: getattr(obj, name)(),
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
    )
    result = SimpleNamespace(
        adapter=adapter,
        annotation=annotation,
        specific=specific,
        fmt=fmt,
        state=state,
        calls=calls,
        annotations=annotations,
        data=data,
    )

    def note_bounds_only(adapter, ann):
        assert ann is edge, "SF preservation must not depend on a derived box"
        return NoteBounds()

    monkeypatch.setattr(
        defaults,
        "annotation_box",
        note_bounds_only,
    )
    result.snapshot = lambda: defaults.snapshot_defaults(
        adapter, TemplateSpec((2, 1), 2)
    )
    return result


@pytest.fixture
def raw_scene(scene):
    scene.fmt.CharHeight = 0.0013229166666666667
    scene.data.text["height_m"] = scene.fmt.CharHeight
    scene.fmt.CharHeightInPts = 5
    scene.fmt.IsHeightSpecifiedInPts = lambda: True
    scene.adapter.currentModel.GetType = lambda: 3
    scene.adapter.swApp.RevisionNumber = lambda: "34.3.0"
    return scene


def test_native_five_point_template_sf_uses_raw_data_not_font_calibration(
    raw_scene, monkeypatch
):
    from _drawing_annotation_bounds import annotation_box

    # Same native format tuple as receipt y18kfdkk: this production estimator
    # really rejects it, before any GDI call. Raw equality needs no estimator.
    with pytest.raises(ValueError, match="uncalibrated native text font/style"):
        annotation_box(raw_scene.adapter, raw_scene.annotation)
    monkeypatch.setattr(defaults, "annotation_box", annotation_box)
    row = defaults._surface_finish_snapshot(raw_scene.adapter, raw_scene.annotation)
    assert row["native_display"]["texts"][0] == raw_scene.data.text
    assert row["format"]["height_points"] == 5


def test_real_shaped_blank_template_preserves_both_surface_finishes(scene):
    snapshot = scene.snapshot()
    symbols = snapshot["sheet_surface_finishes"]
    assert len(symbols) == 2 and symbols[0] == symbols[1]
    row = symbols[0]
    assert row["kind"] == 7 and row["visible"] == 1
    assert row["symbol"] == 1 and row["orientation"] == 3
    assert row["text_count"] == 2
    assert row["text_fields"]["maximum_roughness"] == "3.2"
    assert row["text_fields"]["minimum_roughness"] == ""
    assert scene.calls[:11] == ["GetTextCount", *range(1, 11)]
    assert row["position"] == [0.12, 0.04, 0]
    assert row["format"]["font"] == "Century Gothic"
    assert row["format"]["use_document_format"] is True
    display = row["native_display"]
    assert display["texts"] == [scene.data.text]
    assert display["leaders"] == scene.data.leaders
    assert display["primitives"] == {
        kind: rows
        for kind, rows in scene.data.primitives.items()
        if kind not in {"Ellipse", "Parabola", "Point"}
    }
    assert display["counts"] == {
        "Text": 1,
        **{kind: len(rows) for kind, rows in scene.data.primitives.items()},
    }
    assert snapshot["sheet_notes"][0]["measured"] == {"kind": 6}


@pytest.mark.parametrize(
    "symbol,branch",
    [
        (0, "all_around"),
        (2, "all_around"),
        (9, "all_around"),
        (1, "neither"),
        (7, "texture"),
        (8, "texture"),
    ],
)
def test_only_the_documented_symbol_family_subtype_getter_runs(scene, symbol, branch):
    scene.state["symbol"] = symbol
    scene.snapshot()
    assert ("all_around" in scene.calls) == (branch == "all_around")
    assert ("texture" in scene.calls) == (branch == "texture")


@pytest.mark.parametrize(
    "symbol,field,new", [(0, "all_around", True), (7, "texture", 5)]
)
def test_symbol_subtype_changes_are_preserved_and_rejected(scene, symbol, field, new):
    scene.state["symbol"] = symbol
    before = scene.snapshot()
    scene.state[field] = new
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, scene.snapshot())


def test_generated_name_and_enumeration_order_are_not_cross_document_identity(scene):
    before = scene.snapshot()
    scene.annotations.reverse()
    scene.annotation.GetName = lambda: "new native generated identifier"
    defaults.compare_defaults(before, scene.snapshot())


@pytest.mark.parametrize(
    "property_name,new",
    [
        ("BackWards", True),
        ("CharSpacingFactor", 1 + 1e-12),
        ("Escapement", 1e-12),
        ("LineLength", 0.015 + 1e-12),
        ("LineSpacing", 0.003 + 1e-12),
        ("ObliqueAngle", 1e-12),
        ("Strikeout", True),
        ("Underline", True),
        ("UpsideDown", True),
        ("Vertical", True),
    ],
)
def test_remaining_native_font_properties_are_not_dropped(scene, property_name, new):
    before = scene.snapshot()
    setattr(scene.fmt, property_name, new)
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, scene.snapshot())


@pytest.mark.parametrize(
    "change",
    [
        "text",
        "empty_to_none",
        "font",
        "font_inheritance",
        "orientation",
        "position",
        "profile",
        "gost",
        "visibility",
        "stroke",
        "text_position",
        "multiplicity",
    ],
)
def test_symbol_semantics_formats_and_raw_native_geometry_are_exact(scene, change):
    before = scene.snapshot()
    if change == "text":
        scene.state["text"][5] = "1.6"
    if change == "empty_to_none":
        scene.state["text"][6] = None
    if change == "font":
        scene.fmt.CharHeight += 1e-12
    if change == "font_inheritance":
        scene.annotation.GetUseDocTextFormat = lambda index: False
    if change == "orientation":
        scene.specific.Orientation = 1
    if change == "position":
        scene.state["position"] = (0.12 + 1e-12, 0.04, 0)
    if change == "profile":
        scene.specific.ProfileAngle += 1e-12
    if change == "gost":
        scene.specific.GOSTNotation = True
    if change == "visibility":
        scene.annotation.Visible = 3
    if change == "stroke":
        scene.data.primitives["Line"][0][7] += 1e-12
    if change == "text_position":
        scene.data.text["position"][0] += 1e-12
    if change == "multiplicity":
        scene.annotations.pop()
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, scene.snapshot())


@pytest.mark.parametrize("kind", [1, 2, 4, 5, 13, 15])
def test_unknown_non_note_template_annotations_still_fail(scene, kind):
    scene.annotation.GetType = lambda: kind
    with pytest.raises(RuntimeError, match="unsupported"):
        scene.snapshot()


@pytest.mark.parametrize(
    "bad",
    [
        "symbol",
        "texture",
        "orientation",
        "lay",
        "profile",
        "visibility",
        "null_specific",
        "foreign_annotation",
        "position",
        "format",
        "null_font",
        "empty_font",
        "font_height",
        "text_count",
        "text_type",
        "angle",
    ],
)
def test_unresolved_surface_finish_capture_is_not_accepted(scene, bad):
    if bad == "symbol":
        scene.state["symbol"] = 100
    if bad == "texture":
        scene.state.update(symbol=7, texture=100)
    if bad == "orientation":
        scene.specific.Orientation = 0
    if bad == "lay":
        scene.specific.GetDirectionOfLay = lambda: 8
    if bad == "profile":
        scene.specific.ProfileDirection = 5
    if bad == "visibility":
        scene.annotation.Visible = 4
    if bad == "null_specific":
        scene.annotation.GetSpecificAnnotation = lambda: None
    if bad == "foreign_annotation":
        scene.specific.GetAnnotation = lambda: object()
    if bad == "position":
        scene.state["position"] = (float("nan"), 0.04, 0)
    if bad == "format":
        scene.annotation.GetTextFormatCount = lambda: 0
    if bad == "null_font":
        scene.annotation.GetTextFormat = lambda index: None
    if bad == "empty_font":
        scene.fmt.TypeFaceName = ""
    if bad == "font_height":
        scene.fmt.CharHeight = float("nan")
    if bad == "text_count":
        scene.specific.GetTextCount = lambda: -1
    if bad == "text_type":
        scene.state["text"][5] = 32
    if bad == "angle":
        scene.specific.GetAngle = lambda: float("nan")
    with pytest.raises((RuntimeError, ValueError)):
        scene.snapshot()


@pytest.mark.parametrize(
    "kind,index",
    [
        (kind, index)
        for kind, rows in NativeDisplay().primitives.items()
        for row in rows
        for index in range(len(row))
        if (kind, index)
        not in {("PolyLine", 0), ("PolyLine", 1), ("PolyLine", 6), ("Polygon", 4)}
    ],
)
def test_every_raw_primitive_slot_is_compared_without_projection_or_rounding(
    scene, kind, index
):
    before = scene.snapshot()
    scene.data.primitives[kind][0][index] += 1e-12
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, scene.snapshot())


@pytest.mark.parametrize(
    "field,new",
    [
        ("value", "1.6"),
        ("position", [0.125, 0.045, 1e-12]),
        ("height_m", 0.00635 + 1e-12),
        ("font", "Arial"),
        ("angle_rad", 0.125 + 1e-12),
        ("reference", 0),
        ("inverted", 1),
        ("plane", [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]),
        ("plane", []),
        ("line_spacing", 1.0 + 1e-12),
    ],
)
def test_all_raw_text_fields_are_preserved_without_font_calibration(scene, field, new):
    before = scene.snapshot()
    scene.data.text[field] = new
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, scene.snapshot())


@pytest.mark.parametrize("index", range(9))
def test_raw_nine_element_text_plane_drift_is_not_dropped(scene, index):
    scene.data.text["plane"] = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    before = scene.snapshot()
    scene.data.text["plane"][index] += 1e-12
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, scene.snapshot())


@pytest.mark.parametrize("index", range(9))
def test_every_native_leader_xyz_coordinate_is_exact(scene, index):
    before = scene.snapshot()
    scene.data.leaders[0][index] += 1e-12
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, scene.snapshot())


@pytest.mark.parametrize("kind", ["Ellipse", "Parabola", "Point"])
def test_unimplemented_native_primitives_fail_instead_of_partial_capture(scene, kind):
    scene.data.primitives[kind].append([0])
    with pytest.raises(ValueError, match="unsupported native primitive"):
        scene.snapshot()


@pytest.mark.parametrize("kind", ["Text", *NativeDisplay().primitives])
@pytest.mark.parametrize("count", [-1, 0.5, float("nan")])
def test_raw_native_counts_must_be_complete_and_integral(scene, kind, count):
    setattr(scene.data, f"Get{kind}Count", lambda: count)
    with pytest.raises(ValueError, match="native primitive inventory"):
        scene.snapshot()


@pytest.mark.parametrize(
    "kind", ["Line", "Arc", "PolyLine", "Triangle", "ArrowHead", "Polygon"]
)
def test_unknown_raw_primitive_array_shape_is_not_accepted(scene, kind):
    scene.data.primitives[kind][0].append(0.0)
    with pytest.raises(ValueError, match="native"):
        scene.snapshot()


@pytest.mark.parametrize(
    "bad",
    [
        "null_data",
        "nonfinite_unused",
        "polyline_type",
        "polyline_datasize",
        "polyline_count",
        "polygon_count",
        "polyline_size",
        "polygon_size",
        "text_xyz",
        "text_plane",
        "text_plane_nan",
        "text_height",
        "text_value",
        "text_font",
        "text_reference",
        "text_spacing",
        "multi_jog",
        "leader_style",
        "leader_count",
        "leader_points",
        "no_leader_nonzero_count",
    ],
)
def test_malformed_raw_native_data_is_rejected(scene, bad):
    if bad == "null_data":
        scene.annotation.GetDisplayData = lambda: None
    if bad == "nonfinite_unused":
        scene.data.primitives["Arc"][0][2] = float("nan")
    if bad == "polyline_type":
        scene.data.primitives["PolyLine"][0][0] = 100
    if bad == "polyline_datasize":
        scene.data.primitives["PolyLine"][0][1] = 1
    if bad == "polyline_count":
        scene.data.primitives["PolyLine"][0][6] = 2.5
    if bad == "polygon_count":
        scene.data.primitives["Polygon"][0][4] = 3.5
    if bad == "polyline_size":
        scene.data.GetPolylineSizeAtIndex2 = lambda index: 14
    if bad == "polygon_size":
        scene.data.GetPolygonSizeAtIndex = lambda index: 15
    if bad == "text_xyz":
        scene.data.text["position"] = [0.12, 0.04]
    if bad == "text_plane":
        scene.data.text["plane"] = [0.0]
    if bad == "text_plane_nan":
        scene.data.text["plane"] = [float("nan")] * 9
    if bad == "text_height":
        scene.data.text["height_m"] = 0.0
    if bad == "text_value":
        scene.data.text["value"] = 3.2
    if bad == "text_font":
        scene.data.text["font"] = None
    if bad == "text_reference":
        scene.data.text["reference"] = 6
    if bad == "text_spacing":
        scene.data.text["line_spacing"] = float("nan")
    if bad == "multi_jog":
        scene.annotation.GetMultiJogLeaderCount = lambda: 1
    if bad == "leader_style":
        scene.annotation.GetLeaderStyle = lambda: 4
    if bad == "leader_count":
        scene.annotation.GetLeaderCount = lambda: -1
    if bad == "leader_points":
        scene.data.leaders[0].append(0.0)
    if bad == "no_leader_nonzero_count":
        scene.annotation.GetLeaderStyle = lambda: 0
    with pytest.raises(ValueError, match="native"):
        scene.snapshot()
