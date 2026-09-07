"""Blank-template SF symbols are preserved, never normalized or omitted."""

from dataclasses import asdict, dataclass, replace
import json
from types import SimpleNamespace

import pytest

import _drawing_common as common
from _drawing_prepared_template import TemplateSpec
import _drawing_template_defaults as defaults
from _drawing_annotation_bounds import AnnotationBounds, Segment, TextRun
from _drawing_view_packing import Rect


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
    box = Rect(0.1, 0.03, 0.15, 0.055)
    measured = AnnotationBounds(
        "generated SF",
        7,
        (0.12, 0.04),
        box,
        box,
        (box,),
        (TextRun("3.2", (0.125, 0.045), 0.00635, "Century Gothic", 0.125, 0, 0),),
        (Segment((0.12, 0.04), (0.12, 0.035)),),
        ("Century Gothic", 0.00635, 24),
        (Segment((0.12, 0.04), (0.13, 0.045)),),
        (box,),
    )
    edge_note = SimpleNamespace(
        GetText=lambda: common._METRIC_EDGE_BREAK_NOTE,
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
        measured=measured,
    )
    monkeypatch.setattr(
        defaults,
        "annotation_box",
        lambda adapter, ann: result.measured if ann is annotation else NoteBounds(),
    )
    result.snapshot = lambda: defaults.snapshot_defaults(
        adapter, TemplateSpec((2, 1), 2)
    )
    return result


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
    assert row["measured"]["native_strokes"][0]["end"] == [0.13, 0.045]
    assert row["measured"]["leader_segments"] and row["measured"]["leader_decorations"]
    assert row["measured"]["text_runs"][0]["position"] == [0.125, 0.045]
    complete_measurement = asdict(scene.measured)
    complete_measurement.pop("name")
    assert row["measured"] == json.loads(json.dumps(complete_measurement))


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
    scene.measured = replace(scene.measured, name="new native generated identifier")
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
def test_symbol_semantics_formats_and_full_measured_geometry_are_exact(scene, change):
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
        scene.measured = replace(
            scene.measured,
            native_strokes=(Segment((0.12, 0.04), (0.13 + 1e-12, 0.045)),),
        )
    if change == "text_position":
        scene.measured = replace(
            scene.measured,
            text_runs=(
                replace(scene.measured.text_runs[0], position=(0.125 + 1e-12, 0.045)),
            ),
        )
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
