"""Stateful offline consumers of the shared wire drawing's native readbacks."""

from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace

import pytest
import _drawing_dimensions as dimensions
import _drawing_projection as projection
import _drawing_view_display as view_display

import _drawing_sheets as sheets
import build_sh_vn_music_wire as part
import draw_sh_vn_music_wire as drawing
import sh_vn_music_wire_lever_geom as geom
import sh_vn_music_wire_pen_geom as pen_geom

CONFIGURATION = "LeverWire"
STEM = "sh-vn-music-wire"


def test_wire_registry_quantities_count_installed_members() -> None:
    import _config

    row = _config.parts(STEM)
    assert row["process"] == "purchased"
    assert row["supplier_skus"] == ["9666K56"]
    assert int(row["quantity"]) == sum(row["configuration_quantities"].values())
    assert int(row["configuration_quantities"][CONFIGURATION]) == 1


def test_balloon_station_is_midway_along_the_free_run() -> None:
    assert part.BALLOON_RING_STATION == geom.WIRE_LEN / 2.0


LENGTHS = {"LeverWire": geom.WIRE_LEN, "PenWire": pen_geom.WIRE_LEN}
FIELDS = {
    ("LeverWire", "*Front"): (0.025, 0.105, 0.205, 0.198),
    ("LeverWire", "*Isometric"): (0.018, 0.205, 0.414, 0.244),
    ("PenWire", "*Front"): (0.025, 0.091, 0.205, 0.236),
    ("PenWire", "*Isometric"): (0.225, 0.110, 0.410, 0.244),
}
CENTERS = {
    ("LeverWire", "*Front"): (0.135, 0.150),
    ("LeverWire", "*Isometric"): (0.216, 0.222),
    ("PenWire", "*Front"): (0.110, 0.155),
    ("PenWire", "*Isometric"): (0.300, 0.170),
}
SCALES = {
    ("LeverWire", "*Front"): (1, 5),
    ("LeverWire", "*Isometric"): (1, 1),
    ("PenWire", "*Front"): (2, 1),
    ("PenWire", "*Isometric"): (2, 1),
}


def _inside(point, field):
    return field[0] <= point[0] <= field[2] and field[1] <= point[1] <= field[3]


def _package(
    monkeypatch, tmp_path, *, initial_fault=None, settled_fault=None,
    target=("PenWire", "*Front"), initially_shaded=False, text_anchor=1,
    precision_fault=None,
):
    """A native end-origin cylinder, not a canned outline or setter-call spy.

    Insertion starts from the source's saved LeverWire. Reconfiguration to
    PenWire at 2:1 displaces its actual center by about -298 mm in Front and
    -243 mm in Isometric, as in the native audit. Rebuild commits configuration,
    ratio and angle; moving the view translates its real projection and every
    view-owned dimension. Its text can still be explicitly positioned on-sheet
    while the two associative end targets remain off-sheet.
    """
    source = tmp_path / f"{STEM}.SLDPRT"
    source.write_bytes(b"offline native-path fixture")
    monkeypatch.setattr(drawing, "SOURCE", source)
    views = []
    notes = []
    annotations = []

    class Sheet:
        def __init__(self, name):
            self.name = name
            self.CustomPropertyView = ""
            self.scale = (1, 1)

        def GetName(self):
            return self.name

        def SetName(self, name):
            self.name = name

    class Document:
        def __init__(self):
            self.sheets = [Sheet("Sheet1")]
            self.active = self.sheets[0]
            self.Extension = SimpleNamespace(SelectByID2=lambda *args: True)

        def GetCurrentSheet(self):
            return self.active

        def GetSheetNames(self):
            return tuple(sheet.name for sheet in self.sheets)

        def ActivateSheet(self, name):
            for sheet in self.sheets:
                if sheet.name == name:
                    self.active = sheet
                    return True
            return False

        def ClearSelection2(self, _all):
            pass

        def EditCopy(self):
            pass

        def PasteSheet(self, _position, _options):
            self.sheets.append(Sheet("CopiedSheet"))
            return True

        def EditRebuild3(self):
            for view in views:
                view.settle()
            return True

        def GraphicsRedraw2(self):
            pass

    class View:
        def __init__(self, model_source, orientation, x, y, scale):
            self.sheet = document.active
            self.orientation = orientation
            self.name = f"{self.sheet.name} {orientation}"
            self.model_source = model_source
            self.Position = (x, y)
            self._configuration = "LeverWire"
            self._ratio = tuple(scale)
            self._angle = 0.0
            self.pending = {}
            self.UseSheetScale = 1
            self.mode, self.edges, self.parent_mode, self.threads = 2, False, False, True
            if initially_shaded:
                self.mode, self.edges, self.threads = 3, True, False
            self.fault = initial_fault if self.key == target else None
            # Insertion centers the initially saved member. Its origin is at
            # one end: a later configuration change does not recenter it.
            initial_midpoint = self._project_vector((0.0, geom.WIRE_LEN / 2000, 0.0))
            self.origin_offset = tuple(-value for value in initial_midpoint)

        @property
        def key(self):
            return self.sheet.name, self.orientation

        @property
        def ReferencedConfiguration(self):
            return self._configuration

        @ReferencedConfiguration.setter
        def ReferencedConfiguration(self, value):
            if self.fault != "configuration":
                self.pending["configuration"] = value

        @property
        def ScaleRatio(self):
            return self._ratio

        @ScaleRatio.setter
        def ScaleRatio(self, value):
            self.pending["ratio"] = tuple(value)

        @property
        def Angle(self):
            return self._angle

        @Angle.setter
        def Angle(self, value):
            self.pending["angle"] = float(value)

        def settle(self):
            self._configuration = self.pending.pop("configuration", self._configuration)
            self._ratio = self.pending.pop("ratio", self._ratio)
            self._angle = self.pending.pop("angle", self._angle)
            if self.fault == "scale":
                self._ratio = (1, 1)
            elif self.fault == "angle":
                self._angle = 0.0
            elif self.fault == "sheet-scale":
                self.UseSheetScale = 1

        def _project_vector(self, xyz):
            x, y, z = xyz
            if self.orientation == "*Isometric":
                x, y = (x - z) / math.sqrt(2), (2 * y - x - z) / math.sqrt(6)
            scale = self._ratio[0] / self._ratio[1]
            c, s = math.cos(self._angle), math.sin(self._angle)
            return (scale * (c * x - s * y), scale * (s * x + c * y))

        def project(self, xyz):
            vector = self._project_vector(xyz)
            return tuple(self.Position[i] + self.origin_offset[i] + vector[i]
                         for i in range(2))

        @property
        def ModelToViewTransform(self):
            return self

        def ends(self):
            configuration = self._configuration
            if self.fault == "native-configuration":
                configuration = "PenWire" if configuration == "LeverWire" else "LeverWire"
            return (self.project((0.0, 0.0, 0.0)),
                    self.project((0.0, LENGTHS[configuration] / 1000, 0.0)))

        def GetOutline(self):
            if self.fault == "missing-outline":
                return None
            if self.fault == "nan-outline":
                return (0.1, 0.1, math.nan, 0.2)
            if self.fault == "zero-outline":
                return (0.1, 0.1, 0.1, 0.2)
            ends = self.ends()
            radius = 0.0004 * self._ratio[0] / self._ratio[1]
            # SolidWorks' native outline includes roughly 5.6 mm padding.
            pad = radius + 0.005588
            return (min(p[0] for p in ends) - pad,
                    min(p[1] for p in ends) - pad,
                    max(p[0] for p in ends) + pad,
                    max(p[1] for p in ends) + pad)

        def SetViewPosition(self, position, _move_children):
            if self.fault == "recenter-false":
                return False
            if self.fault != "ignored-recenter":
                self.Position = tuple(position)
            return True

        def GetReferencedModelName(self):
            return self.model_source

        def GetOrientationName(self):
            return self.orientation

        def SetDisplayMode4(self, parent, mode, _faceted, edges, threads):
            # A same-mode write can be a native no-op, leaving old cosmetic
            # thread quality untouched until the view leaves Shaded first.
            if (self.parent_mode, self.mode, self.edges) == (parent, mode, edges):
                return False
            self.parent_mode, self.mode = parent, mode
            self.edges, self.threads = edges, threads
            return True

        def GetDisplayMode2(self):
            return self.mode

        def GetDisplayEdgesInShadedMode(self):
            return self.edges

        def GetUseParentDisplayMode(self):
            return self.parent_mode

        def GetCThreadQuality(self):
            return self.threads

    class ModelDimension:
        __slots__ = ("annotation",)

        def __init__(self, annotation):
            self.annotation = annotation

        @property
        def FullName(self):
            feature = "OtherFeature" if self.annotation.fault == "association" else "Wire"
            return f"Depth@{feature}@{STEM}.SLDPRT"

        @property
        def SystemValue(self):
            raise AssertionError("a multi-configuration source needs qualified readback")

        @property
        def DrivenState(self):
            return 0

        @DrivenState.setter
        def DrivenState(self, _value):
            raise AssertionError("drawing reference presentation must not edit the model")

        def GetSystemValue3(self, which, configuration):
            if which != 3:
                raise AssertionError("expected swSpecifyConfiguration")
            fault = self.annotation.fault
            if fault == "missing-value":
                return None
            if fault == "multiple-values":
                return tuple(value / 1000 for value in LENGTHS.values())
            if fault == "nonfinite-value":
                return (math.nan,)
            if fault == "configuration-length":
                configuration = "PenWire" if configuration == "LeverWire" else "LeverWire"
            return (LENGTHS[configuration] / 1000,)

    class DisplayData:
        def __init__(self, annotation):
            self.annotation = annotation

        def tips(self):
            annotation = self.annotation
            ends = annotation.view.ends()
            x = annotation.GetPosition()[0]
            tips = [(x, end[1]) for end in ends]
            if annotation.fault == "offsheet-arrows":
                tips = [(x, y - 0.300) for x, y in tips]
            elif annotation.fault == "arrow-span":
                tips[1] = (tips[1][0], tips[1][1] + 0.001)
            return tips

        def lines(self):
            annotation = self.annotation
            tips, ends = self.tips(), annotation.view.ends()
            lines = [(ends[0], tips[0]), (ends[1], tips[1]), (tips[0], tips[1])]
            if annotation.fault == "offsheet-stroke":
                lines.append(((0.078, -0.20), (0.078, 0.155)))
            elif annotation.fault == "nonfinite-stroke":
                lines.append(((math.nan, 0.155), (0.078, 0.155)))
            return [] if annotation.fault == "missing-strokes" else lines

        def GetLineCount(self):
            return len(self.lines())

        def GetLineAtIndex2(self, index):
            start, end = self.lines()[index]
            return (0.0, 0.0, 0.0, 0.0, *start, 0.0002, *end, 0.0002)

        def GetArrowHeadCount(self):
            return 1 if self.annotation.fault == "missing-arrow" else 2

        def GetArrowHeadAtIndex2(self, index):
            tip = self.tips()[index]
            direction = 1.0 if index == 0 else -1.0
            width = 0.003556
            if self.annotation.fault == "offsheet-barbs":
                direction *= -1
                width = 0.020
            elif self.annotation.fault == "long-inward-barbs":
                width = 0.020
            values = (*tip, 0.0002, 0.0, direction, 0.0,
                      width, 0.000762, 0.0, 0.0, 0.0, 1.0)
            if self.annotation.fault == "nonfinite-arrow":
                values = (*values[:6], math.nan, *values[7:])
            return values[:6] if self.annotation.fault == "incomplete-arrow" else values

        def GetTextCount(self):
            return 0 if self.annotation.fault == "missing-text" else 1

        def GetTextAtIndex(self, _index):
            display = self.annotation.display
            configuration = self.annotation.view.ReferencedConfiguration
            length = 999.0 if self.annotation.fault == "displayed-length" else LENGTHS[configuration]
            return f"{display.GetText(1)} {length:.2f} {display.GetText(2)}"

        def GetTextHeightAtIndex(self, _index):
            return 0.0002 if self.annotation.fault == "hairline-text" else 0.0035

        def GetTextInBoxWidthAtIndex(self, _index):
            return 0.020

        def GetTextRefPositionAtIndex(self, _index):
            if self.annotation.fault == "right-anchor-offsheet-text":
                return 4  # swLOWER_RIGHT
            if self.annotation.fault == "center-anchor-offsheet-text":
                return 2  # swCENTER
            return text_anchor

        def GetTextPositionAtIndex(self, index):
            x, y, z = self.annotation.GetPosition()
            if self.annotation.fault == "anchor-offsheet-text":
                field = FIELDS[self.annotation.view.key]
                # Upper/center/right anchors are inside, but their glyphs
                # cross the left or bottom edge. LOWER_LEFT must itself leave.
                dx = -0.001 if text_anchor == 1 else 0.001
                return (field[0] + dx, field[1] + 0.001, z)
            if self.annotation.fault in (
                "right-anchor-offsheet-text", "center-anchor-offsheet-text",
            ):
                # The anchor is inside the field; its true glyph box is not.
                return (0.030, y - 0.0027781, z)
            if self.annotation.fault == "offsheet-text":
                x = -0.02
            fx, fy = {
                0: (0.0, 1.0), 1: (0.0, 0.0), 2: (0.5, 0.5),
                3: (1.0, 1.0), 4: (1.0, 0.0), 5: (0.5, 1.0),
            }[self.GetTextRefPositionAtIndex(index)]
            return (x - 0.020 + fx * 0.020, y - 0.0027781 + fy * 0.0035, z)

        def GetTextAngleAtIndex(self, _index):
            return math.pi / 2 if self.annotation.fault == "text-angle" else 0.0

    class DisplayDimension:
        def __init__(self, annotation):
            self.annotation = annotation
            self.text = {1: "", 2: ""}
            self.ShowDimensionValue = True
            self.dimension = ModelDimension(annotation)
            self.precision = -2  # swPrecisionFollowsDocumentSetting

        def GetDimension2(self, _index):
            return self.dimension

        def SetText(self, part, text):
            self.text[part] = text

        def GetText(self, part):
            return "" if self.annotation.fault == "reference" else self.text[part]

        def SetPrecision3(self, primary, dual, primary_tol, dual_tol):
            assert (dual, primary_tol, dual_tol) == (-1, -1, -1)
            if precision_fault != "ignored":
                self.precision = primary
            return -1 if precision_fault == "failed" else (
                1 if precision_fault == "invalid" else 0
            )

        def GetPrimaryPrecision2(self):
            return -2 if self.annotation.fault == "precision-reset" else self.precision

        def GetDisplayData(self):
            if self.annotation.fault == "missing-display":
                return None
            return DisplayData(self.annotation)

    class Annotation:
        def __init__(self, view, text_xy):
            self.view = view
            self.text_offset = tuple(text_xy[i] - view.Position[i] for i in range(2))
            self.fault = None
            self.Visible = 1
            self.display = DisplayDimension(self)

        def GetPosition(self):
            x, y = (self.view.Position[i] + self.text_offset[i] for i in range(2))
            if self.fault == "text-drift":
                x += 0.001
            return (x, y, 0.0002)

        def GetSpecificAnnotation(self):
            return self.display

        def IsDangling(self):
            return self.fault == "dangling"

    class Note:
        def __init__(self, text, x, y):
            self.sheet = document.active.name
            self.text, self.x, self.y = text, x, y
            self.fault = None
            notes.append(self)

        def GetText(self):
            return self.text

        def GetExtent(self):
            lines = self.text.splitlines()
            width = max(map(len, lines)) * 0.0022
            x = -0.02 if self.fault == "offsheet-note" else self.x
            y = 0.160 if self.fault == "note-overlap" else self.y
            if self.fault == "missing-note-extent":
                return ()
            return (x - 0.0004, y - len(lines) * 0.0045257 + 0.0003, 0.0,
                    x + width, y + 0.0003, 0.0)

    class MathPoint:
        def __init__(self, xyz):
            self.ArrayData = tuple(xyz)

        def MultiplyTransform(self, transform):
            return MathPoint((*transform.project(self.ArrayData), 0.0))

    document = Document()
    adapter = SimpleNamespace(
        currentModel=object(),
        swApp=SimpleNamespace(
            GetMathUtility=lambda: SimpleNamespace(CreatePoint=MathPoint)
        ),
    )

    def attr_or_call(obj, name, *args):
        value = getattr(obj, name)
        return value(*args) if callable(value) else value

    def attempt(fn, *, default=None):
        try:
            return fn()
        except Exception:
            return default

    def attempt_with_error(fn):
        try:
            return fn(), None
        except Exception as error:
            return None, error

    adapter._get_attr_or_call = attr_or_call
    adapter._attempt = attempt
    adapter._attempt_with_error = attempt_with_error

    async def open_model(_path):
        return True

    def read_properties(_model, names, *, required):
        properties = {name: "native property" for name in names}
        properties.update({
            "LeverWire Manufacturing Notes": drawing.lever_spec.DRAWING_NOTES,
            "LeverWire Front View Note": drawing.lever_spec.FRONT_VIEW_NOTE,
            "LeverWire Isometric View Note": drawing.lever_spec.ISOMETRIC_VIEW_NOTE,
            "PenWire Manufacturing Notes": drawing.pen_spec.DRAWING_NOTES,
            "PenWire Elevation View Note": drawing.pen_spec.ELEVATION_VIEW_NOTE,
            "PenWire Isometric View Note": drawing.pen_spec.ISOMETRIC_VIEW_NOTE,
        })
        return properties

    properties = read_properties(None, (), required=())

    def new_drawing(_adapter, **kwargs):
        adapter.currentModel = document
        return document, document.active

    def place(_adapter, model_source, orientation, x, y, *, scale):
        view = View(model_source, orientation, x, y, scale)
        views.append(view)
        return view

    def curate(_adapter, view, *, keep, dimensions_by_feature=None, **kwargs):
        marked = {"Wire": {"Depth"}} if dimensions_by_feature is None else dimensions_by_feature
        if "Depth" not in marked.get("Wire", ()) or "Depth" not in keep:
            return []
        annotation = Annotation(view, keep["Depth"])
        annotations.append(annotation)
        return [annotation]

    async def finalize(_adapter, _outputs, **kwargs):
        for sheet in document.sheets:
            sheet.scale = kwargs["sheet_scales"][sheet.name]
        view = next(view for view in views if view.key == target)
        fault = settled_fault
        if fault == "configuration":
            view.ReferencedConfiguration = "LeverWire" if target[0] == "PenWire" else "PenWire"
        elif fault == "source":
            view.model_source = str(tmp_path / "wrong-native.SLDPRT")
        elif fault == "orientation":
            view.orientation = "*Top"
        elif fault == "scale":
            view.ScaleRatio = (3, 1)
        elif fault == "angle":
            view.Angle = view.Angle + 0.01
        elif fault == "sheet-scale":
            view.UseSheetScale = 1
        elif fault == "position":
            view.Position = (view.Position[0], view.Position[1] - 0.001)
        elif fault == "offsheet-outline":
            view.Position = (view.Position[0], view.Position[1] - 0.300)
        elif fault == "shading":
            view.mode, view.edges = 2, False
        elif fault == "shaded-no-edges":
            view.mode, view.edges = 3, False
        elif fault in ("nan-outline", "missing-outline", "zero-outline"):
            view.fault = fault
        elif fault is not None:
            annotation = next(
                annotation for annotation in annotations if annotation.view.key == target
            ) if "*Front" == target[1] else None
            if fault == "hidden":
                annotation.Visible = 3
            elif fault == "hidden-value":
                annotation.display.ShowDimensionValue = False
            elif fault in ("offsheet-note", "note-overlap", "missing-note-extent"):
                note = next(note for note in notes if note.sheet == target[0])
                note.fault = fault
            else:
                annotation.fault = fault
        document.EditRebuild3()
        for settled_check in kwargs["settled_checks"]:
            settled_check()
        return {"pdf": "offline-export"}

    adapter.open_model = open_model
    monkeypatch.setattr(drawing, "check", lambda _label, value: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(sheets, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(view_display, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(
        dimensions._sw_type_info, "early_bound_or_flag",
        lambda obj, _interface, *methods: obj,
    )
    monkeypatch.setattr(sheets, "iter_views", lambda _adapter: iter(()))
    monkeypatch.setattr(sheets, "null_callout", lambda: None)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(projection, "double_array", tuple)
    monkeypatch.setattr(
        projection, "_com_invoke",
        lambda obj, _interface, name, *args: attr_or_call(obj, name, *args),
    )
    monkeypatch.setattr(drawing, "read_required_properties", read_properties)
    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *args: None)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)

    def rebuild(*args, **kwargs):
        return document.EditRebuild3()

    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    monkeypatch.setattr(dimensions, "rebuild_drawing", rebuild)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(
        drawing, "add_property_linked_note",
        lambda _adapter, key, x, y: Note(properties[key], x, y),
    )
    monkeypatch.setattr(
        drawing, "add_note", lambda _adapter, text, x, y: Note(text, x, y),
    )
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    return SimpleNamespace(
        adapter=adapter, document=document, views=views,
        annotations=annotations, notes=notes,
    )


def test_wire_package_recenters_real_member_geometry_before_dimensioning(
    monkeypatch, tmp_path
):
    package = _package(monkeypatch, tmp_path)
    assert asyncio.run(drawing.build(package.adapter)) == {"pdf": "offline-export"}
    assert package.document.GetSheetNames() == ("LeverWire", "PenWire")
    assert len(package.views) == 4
    for view in package.views:
        box = view.GetOutline()
        assert view.ReferencedConfiguration == view.sheet.name
        assert view.ScaleRatio == SCALES[view.key]
        assert view.UseSheetScale == 0
        assert ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) == pytest.approx(
            CENTERS[view.key], abs=1e-6
        )
        assert _inside(box[:2], FIELDS[view.key])
        assert _inside(box[2:], FIELDS[view.key])
        first, last = view.ends()
        expected_length = LENGTHS[view.sheet.name] / 1000 * SCALES[view.key][0] / SCALES[view.key][1]
        if view.orientation == "*Isometric":
            expected_length *= math.sqrt(2 / 3)
            # Mode 3 plus Edges=True IS Shaded With Edges.
            assert view.mode == 3 and view.edges
        assert math.dist(first, last) == pytest.approx(expected_length)
    lever_iso = next(view for view in package.views if view.key == ("LeverWire", "*Isometric"))
    first, last = lever_iso.ends()
    assert first[1] == pytest.approx(last[1])
    assert abs(first[0] - last[0]) > 0.28  # readable full-width 1:1 rest run
    assert lever_iso.GetOutline()[2] - lever_iso.GetOutline()[0] > 0.29
    assert {sheet.name: sheet.scale for sheet in package.document.sheets} == {
        "LeverWire": (1, 1), "PenWire": (2, 1),
    }
    assert len(package.annotations) == 2
    for annotation in package.annotations:
        view, display = annotation.view, annotation.display
        data = display.GetDisplayData()
        assert display.dimension.FullName.split("@")[:2] == ["Depth", "Wire"]
        assert display.dimension.GetSystemValue3(3, view.sheet.name) == pytest.approx(
            (LENGTHS[view.sheet.name] / 1000,)
        )
        assert (display.GetText(1), display.GetText(2)) == ("(", ")")
        assert display.GetPrimaryPrecision2() == 2
        assert display.ShowDimensionValue and not annotation.IsDangling()
        tips = data.tips()
        assert abs(tips[1][1] - tips[0][1]) == pytest.approx(
            LENGTHS[view.sheet.name] / 1000 * SCALES[view.key][0] / SCALES[view.key][1]
        )
        for tip, end in zip(tips, view.ends()):
            assert tip[1] == pytest.approx(end[1])
            assert _inside(tip, FIELDS[view.key])
        assert all(_inside(point, FIELDS[view.key])
                   for segment in drawing.dimension_segments(annotation) for point in segment)


def test_fixture_exposes_the_native_configuration_displacement(monkeypatch, tmp_path):
    package = _package(monkeypatch, tmp_path)
    package.adapter.currentModel = package.document
    package.document.active.SetName("PenWire")
    front = drawing.place_view(
        package.adapter, str(drawing.SOURCE), "*Front", 0.110, 0.155, scale=(2, 1)
    )
    front.ReferencedConfiguration = "PenWire"
    front.UseSheetScale = 0
    package.document.EditRebuild3()
    box = front.GetOutline()
    assert (box[1] + box[3]) / 2 == pytest.approx(
        0.155 + (pen_geom.WIRE_LEN - geom.WIRE_LEN) / 1000, abs=1e-6
    )
    assert box[3] < 0.0
    annotation = drawing.curate_view_dimensions(
        package.adapter, front, keep={"Depth": (0.078, 0.155)}
    )[0]
    assert annotation.GetPosition()[1] == pytest.approx(0.155)
    assert all(tip[1] < 0 for tip in annotation.display.GetDisplayData().tips())


def test_already_shaded_views_regenerate_before_high_quality_readback(
    monkeypatch, tmp_path
):
    package = _package(monkeypatch, tmp_path, initially_shaded=True)
    asyncio.run(drawing.build(package.adapter))
    assert len(package.views) == 4
    assert all(view.GetCThreadQuality() for view in package.views)
    for view in package.views:
        if view.orientation == "*Isometric":
            assert view.GetDisplayMode2() == 3
            assert view.GetDisplayEdgesInShadedMode()
        else:
            assert view.GetDisplayMode2() == 2


@pytest.mark.parametrize("reference", (0, 1, 2, 3, 4, 5))
def test_dimension_text_bounds_follow_native_reference_anchor(
    monkeypatch, tmp_path, reference
):
    measured = []
    require_field = drawing._require_field

    def record_bounds(box, field, label):
        if label.endswith("straight rest-run REF") and box[2] > box[0]:
            measured.append(tuple(box))
        require_field(box, field, label)

    monkeypatch.setattr(drawing, "_require_field", record_bounds)
    package = _package(monkeypatch, tmp_path, text_anchor=reference)
    asyncio.run(drawing.build(package.adapter))
    for annotation in package.annotations:
        x, y, _ = annotation.GetPosition()
        expected = (x - 0.020, y - 0.0027781, x, y - 0.0027781 + 0.0035)
        # These are the actual production-normalized bounds, not a fake's
        # second implementation of its own native anchor conversion.
        assert any(box == pytest.approx(expected) for box in measured)


@pytest.mark.parametrize("reference", (0, 1, 2, 3, 4, 5))
@pytest.mark.parametrize("configuration", ("LeverWire", "PenWire"))
def test_native_anchor_cannot_hide_offsheet_dimension_ink(
    monkeypatch, tmp_path, reference, configuration
):
    package = _package(
        monkeypatch, tmp_path, text_anchor=reference,
        settled_fault="anchor-offsheet-text", target=(configuration, "*Front"),
    )
    with pytest.raises(RuntimeError, match="leaves its printable field"):
        asyncio.run(drawing.build(package.adapter))


@pytest.mark.parametrize("fault", ("ignored", "failed", "invalid"))
def test_native_precision_write_must_succeed_and_persist(monkeypatch, tmp_path, fault):
    package = _package(monkeypatch, tmp_path, precision_fault=fault)
    with pytest.raises(RuntimeError, match="precision did not persist"):
        asyncio.run(drawing.build(package.adapter))


@pytest.mark.parametrize("configuration", ("LeverWire", "PenWire"))
def test_empty_native_dimension_marks_cannot_create_depth(
    monkeypatch, tmp_path, configuration
):
    package = _package(monkeypatch, tmp_path)
    monkeypatch.setitem(drawing._DRAWING_DIMENSIONS, configuration, {})
    with pytest.raises(RuntimeError, match="expected one native rest-run Depth"):
        asyncio.run(drawing.build(package.adapter))


@pytest.mark.parametrize("configuration", ("LeverWire", "PenWire"))
def test_calibrated_arrow_bases_point_into_native_dimension_span(
    monkeypatch, tmp_path, configuration
):
    package = _package(
        monkeypatch, tmp_path, settled_fault="long-inward-barbs",
        target=(configuration, "*Front"),
    )
    assert asyncio.run(drawing.build(package.adapter)) == {"pdf": "offline-export"}


@pytest.mark.parametrize(
    "fault,target",
    (
        ("configuration", ("PenWire", "*Front")),
        ("native-configuration", ("PenWire", "*Front")),
        ("native-configuration", ("LeverWire", "*Front")),
        ("ignored-recenter", ("PenWire", "*Front")),
        ("ignored-recenter", ("PenWire", "*Isometric")),
        ("ignored-recenter", ("LeverWire", "*Isometric")),
        ("recenter-false", ("LeverWire", "*Front")),
        ("scale", ("PenWire", "*Front")),
        ("angle", ("LeverWire", "*Isometric")),
        ("sheet-scale", ("LeverWire", "*Front")),
        ("missing-outline", ("PenWire", "*Front")),
        ("nan-outline", ("PenWire", "*Isometric")),
        ("zero-outline", ("LeverWire", "*Isometric")),
    ),
)
def test_wire_package_refuses_unsettled_native_placement(monkeypatch, tmp_path, fault, target):
    package = _package(monkeypatch, tmp_path, initial_fault=fault, target=target)
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(package.adapter))


@pytest.mark.parametrize("target", tuple(FIELDS))
@pytest.mark.parametrize(
    "fault",
    ("configuration", "source", "orientation", "scale", "angle", "sheet-scale",
     "position", "offsheet-outline", "missing-outline", "nan-outline", "zero-outline"),
)
def test_wire_package_rechecks_all_native_views_after_finalization(
    monkeypatch, tmp_path, fault, target
):
    package = _package(monkeypatch, tmp_path, settled_fault=fault, target=target)
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(package.adapter))


@pytest.mark.parametrize("configuration", ("LeverWire", "PenWire"))
@pytest.mark.parametrize(
    "fault",
    ("association", "dangling", "hidden", "hidden-value", "configuration-length",
     "missing-value", "multiple-values", "nonfinite-value", "reference", "text-drift",
     "missing-display", "missing-text", "displayed-length", "hairline-text",
     "text-angle", "offsheet-text", "offsheet-stroke", "nonfinite-stroke",
     "missing-strokes", "offsheet-arrows", "arrow-span", "missing-arrow",
     "incomplete-arrow", "nonfinite-arrow", "offsheet-barbs", "precision-reset",
     "right-anchor-offsheet-text", "center-anchor-offsheet-text"),
)
def test_both_rest_run_references_fail_closed_on_native_dimension_corruption(
    monkeypatch, tmp_path, fault, configuration
):
    package = _package(
        monkeypatch, tmp_path, settled_fault=fault, target=(configuration, "*Front")
    )
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(package.adapter))


@pytest.mark.parametrize("configuration", ("LeverWire", "PenWire"))
@pytest.mark.parametrize("fault", ("shading", "shaded-no-edges"))
def test_wire_isometrics_require_readable_shaded_edges(
    monkeypatch, tmp_path, configuration, fault
):
    package = _package(
        monkeypatch, tmp_path, settled_fault=fault, target=(configuration, "*Isometric")
    )
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(package.adapter))


@pytest.mark.parametrize("fault", ("offsheet-note", "note-overlap", "missing-note-extent"))
def test_native_note_bounds_must_remain_on_sheet_and_clear(
    monkeypatch, tmp_path, fault
):
    package = _package(monkeypatch, tmp_path, settled_fault=fault)
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(package.adapter))
