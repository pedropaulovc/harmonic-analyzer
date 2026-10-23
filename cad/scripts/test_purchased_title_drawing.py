"""Offline native-cell contracts; never a substitute for settled farm/PDF proof.

Only COM binding is replaced. The actual fitter, ruled-cell extraction, rebuild,
zoom isolation, display-data collector and strict final checks remain active.
The expression/identity predicate cases below are reused from the exact owner
source 91022397a28fbfc307f24bfab0fcfdf2f08dffc1, not its whole jig branch.
"""
from __future__ import annotations

import ast
import copy
import math
from types import SimpleNamespace

import pytest

import _drawing_layout_audit as layout
import _purchased_fastener_drawing as purchased
import _purchased_title_fit as title


_STYLE_FIELDS = (
    "TypeFaceName", "CharHeight", "CharHeightInPts", "IsHeightSpecifiedInPts",
    "Bold", "Italic", "Underline", "Strikeout", "WidthFactor",
    "CharSpacingFactor", "LineSpacing", "LineLength", "Escapement",
    "ObliqueAngle", "BackWards", "UpsideDown", "Vertical",
)


class _Format:
    """Detached ITextFormat: 16 native properties and one height-mode method.

    These are the exact maintenance census fields; document-format authority is
    an additional IAnnotation getter, not an invented eighteenth font member.
    This fake does not rasterize fonts or predict native point-size rounding.
    """

    __slots__ = tuple(name for name in _STYLE_FIELDS if name != "IsHeightSpecifiedInPts") + (
        "_points_mode",
    )

    def __init__(self, height=0.004, length=0.006, face="Arial"):
        self.CharHeight = height
        self.CharHeightInPts = round(height / 0.0002645833333333333)
        self.LineLength = length
        self.TypeFaceName = face
        self.Bold = False
        self.Italic = False
        self.Underline = False
        self.Strikeout = False
        self.WidthFactor = 1.0
        self.CharSpacingFactor = 1.0
        self.LineSpacing = 0.001
        self.Escapement = 0
        self.ObliqueAngle = 0.0
        self.BackWards = False
        self.UpsideDown = False
        self.Vertical = False
        self._points_mode = False

    def IsHeightSpecifiedInPts(self):
        return self._points_mode


class _HeightModeFormat:
    """Detached native height-unit semantics, only for the measured mode cases.

    ITextFormat.CharHeight is a metre DOUBLE put selecting False mode;
    CharHeightInPts is an INTEGER put selecting True mode. Retain the supplied
    integer readback without inventing conversion, DPI or native rounding.
    Copy native storage directly: copying a points-mode format is not a put.
    """

    __slots__ = tuple(
        name for name in _STYLE_FIELDS
        if name not in ("CharHeight", "CharHeightInPts", "IsHeightSpecifiedInPts")
    ) + ("_height_m", "_height_points", "_points_mode", "height_writes", "point_writes")

    def __init__(self, original, *, points_mode):
        for name in _STYLE_FIELDS:
            if name not in ("CharHeight", "CharHeightInPts", "IsHeightSpecifiedInPts"):
                setattr(self, name, getattr(original, name))
        self._height_m = original.CharHeight
        self._height_points = original.CharHeightInPts
        assert type(self._height_points) is int
        self._points_mode = points_mode
        self.height_writes = ()
        self.point_writes = ()

    @property
    def CharHeight(self):
        return self._height_m

    @CharHeight.setter
    def CharHeight(self, value):
        self._height_m = value
        self._points_mode = False
        self.height_writes += (value,)

    @property
    def CharHeightInPts(self):
        return self._height_points

    @CharHeightInPts.setter
    def CharHeightInPts(self, value):
        assert type(value) is int, "native point-size puts require an INTEGER"
        self._height_points = value
        self._points_mode = True
        self.point_writes += (value,)

    def IsHeightSpecifiedInPts(self):
        return self._points_mode

    def __copy__(self):
        detached = type(self)(self, points_mode=self._points_mode)
        detached.height_writes = self.height_writes
        detached.point_writes = self.point_writes
        return detached

    def __deepcopy__(self, memo):
        detached = self.__copy__()
        memo[id(self)] = detached
        return detached


class _Line:
    def __init__(self, x1, y1, x2, y2):
        self.start = SimpleNamespace(X=x1, Y=y1)
        self.end = SimpleNamespace(X=x2, Y=y2)

    def GetType(self):
        return 0  # swSketchLINE

    def GetStartPoint2(self):
        return self.start

    def GetEndPoint2(self):
        return self.end


def _rules(cell):
    left, bottom, right, top = cell
    return (
        _Line(left, bottom, right, bottom), _Line(left, top, right, top),
        _Line(left, bottom, left, top), _Line(right, bottom, right, top),
    )


class _Display:
    """Real _dump_display consumes these native methods, not canned dump rows."""

    def __init__(self, note):
        self.note = note

    def GetLineCount(self):
        return 0

    GetArcCount = GetLineCount
    GetArrowHeadCount = GetLineCount
    GetPolyLineCount = GetLineCount
    GetPolygonCount = GetLineCount
    GetTriangleCount = GetLineCount
    GetEllipseCount = GetLineCount

    def GetTextCount(self):
        return 0 if self.note.empty_display else self.note.rows

    def GetTextAtIndex(self, index):
        return self.note._text[index::self.note.rows]

    def GetTextPositionAtIndex(self, index):
        if self.note.unreadable_display:
            return None
        return (self.note.anchor[0], self.note.anchor[1] -
                (index + 1) * 1.2 * self.note.annotation._format.CharHeight, 0.0)

    def GetTextHeightAtIndex(self, index):
        return self.note.annotation._format.CharHeight

    def GetTextRefPositionAtIndex(self, index):
        return 0

    def GetTextAngleAtIndex(self, index):
        return 0.0

    def GetTextFontAtIndex(self, index):
        return self.note.annotation._format.TypeFaceName

    def GetTextLineSpacingAtIndex(self, index):
        return 1.2

    def GetTextInBoxWidthAtIndex(self, index):
        return self.note.extent[3] - self.note.extent[0]


class _Annotation:
    def __init__(self, note):
        self.note = note
        self.OwnerType = 2  # swDrawingTemplate ownership, retained by the native census.
        self._format = _Format()
        self.extra_formats = []
        self.extra_use_doc = []
        self.format_count_reads = 0
        self.format_read_errors = {}
        self.use_doc = True
        self.setter_result = True
        self.ignore_setter = False
        self.formats = []
        self.position_result = True
        self.ignore_position_setter = False
        self.position_offset = (0.0, 0.0, 0.0)
        self.positions = []

    def GetPosition(self):
        return self.note.anchor

    def SetPosition2(self, x, y, z):
        self.positions.append((x, y, z))
        if self.position_result is True and not self.ignore_position_setter:
            self.note.anchor = tuple(
                value + offset
                for value, offset in zip((x, y, z), self.position_offset, strict=True)
            )
            self.note.refresh()
        return self.position_result

    def GetTextFormatCount(self):
        self.format_count_reads += 1
        return 1 + len(self.extra_formats)

    def GetTextFormat(self, index):
        if index in self.format_read_errors:
            raise self.format_read_errors[index]
        formats = (self._format, *self.extra_formats)
        return copy.copy(formats[index]) if 0 <= index < len(formats) else None

    def SetTextFormat(self, index, use_doc, text_format):
        assert index == 0 and use_doc is False
        self.formats.append(copy.copy(text_format))
        if self.setter_result is True and not self.ignore_setter:
            self._format = copy.copy(text_format)
            self.use_doc = use_doc
            # Captured native formatting may remove ONLY this FONT wrapper.
            expression = title.source_property_expression(self.note._link)
            if expression is not None:
                self.note._link = expression
        return self.setter_result

    def GetUseDocTextFormat(self, index):
        return (self.use_doc, *self.extra_use_doc)[index]

    def GetDisplayData(self):
        return _Display(self.note)


class _Note:
    def __init__(self, expression, text, cell, *, material=False):
        self._link = expression
        self._text = text
        self.name = f"Note:{expression}"
        self.Angle = 0.0
        self.horizontal_justification = 1  # swTextJustificationLeft
        self.vertical_justification = 0  # swTextAlignmentTop
        self.justification_reads = 0
        self.extent_reads = []
        self.extent_epochs = []
        self.draw = None
        self.cell = cell
        self.anchor = (cell[0] + 0.002, cell[3] - 0.002, 0.0)
        self.material = material
        self.annotation = _Annotation(self)
        self.next = None
        self.forced_rows = None
        self.extent_shift = (0.0, 0.0)
        self.empty_display = False
        self.unreadable_display = False
        self.refresh()

    @property
    def PropertyLinkedText(self):
        return self._link

    def GetName(self):
        return self.name

    def GetText(self):
        return self._text

    def GetAnnotation(self):
        return self.annotation

    def GetNext(self):
        return self.next

    def GetTextJustification(self):
        self.justification_reads += 1
        return self.horizontal_justification

    def GetTextVerticalJustification(self):
        self.justification_reads += 1
        return self.vertical_justification

    def GetExtent(self):
        self.extent_reads.append(self.extent)
        self.extent_epochs.append(self.draw.rebuilds if self.draw is not None else -1)
        return self.extent

    def refresh(self):
        height = self.annotation._format.CharHeight
        width = len(self._text) * height * 0.55
        # Captured material wrapping is native, not widened by LineLength.
        # The metadata remains distinct so an accidental write is observable.
        wrap = 0.034 if self.material else self.annotation._format.LineLength
        self.rows = self.forced_rows or max(1, math.ceil(width / wrap))
        x, y, _ = self.anchor
        dx, dy = self.extent_shift
        self.extent = (x + dx, y - self.rows * height * 1.2 + dy, 0.0,
                       x + min(width, wrap) + dx, y + dy, 0.0)


class _Drawing:
    def __init__(self, notes):
        self.notes = notes
        self.rebuilds = 0
        self.rebuild_result = True
        self.rebuild_actions = {}
        self.rules = tuple(segment for note in notes for segment in _rules(note.cell))
        self.sheet = SimpleNamespace(GetTemplateSketch=lambda: SimpleNamespace(
            GetSketchSegments=lambda: self.rules,
        ))
        self.sheet.SheetFormatVisible = True
        self.sheet_view = SimpleNamespace(GetFirstNote2=lambda: notes[0] if notes else None)
        self.relink()

    def relink(self):
        for index, note in enumerate(self.notes):
            note.draw = self
            note.next = self.notes[index + 1] if index + 1 < len(self.notes) else None

    def GetCurrentSheet(self):
        return self.sheet

    def GetFirstView(self):
        return self.sheet_view

    def EditRebuild3(self):
        self.rebuilds += 1
        action = self.rebuild_actions.pop(self.rebuilds, None)
        if action is not None:
            action()
        for note in self.notes:
            note.refresh()
        return self.rebuild_result

    def ViewZoomTo2(self, *coordinates):
        assert len(coordinates) == 6
        # Native VT_VOID: success is None, not a Boolean signal.

    def ViewZoomtofit2(self):
        pass  # Native VT_VOID.


@pytest.fixture
def native_title(monkeypatch):
    for module in (title, layout, purchased):
        monkeypatch.setattr(module, "_early_bound", lambda value, _kind: value)

    def make(material_property="Material Specification"):
        stem = "ch-rocker-arm-tl-oblique-carriage-screw"
        notes = [
            _Note('<FONT size=15PTS>' + title.property_link("SW-Title(Title)"),
                  stem, (0.010, 0.040, 0.090, 0.055)),
            _Note(title.property_link(material_property), "ALLOY STEEL, BLACK OXIDE",
                  (0.010, 0.010, 0.060, 0.025), material=True),
            _Note(title.property_link("Number"), "HA-CH-OBLIQUE-SCREW-106",
                  (0.100, 0.040, 0.150, 0.055)),
        ]
        draw = _Drawing(notes)
        return SimpleNamespace(
            notes=notes, name=notes[0], material=notes[1], number=notes[2],
            draw=draw, adapter=SimpleNamespace(currentModel=draw),
            spec=SimpleNamespace(artifact_stem=stem), selected=material_property,
        )

    return make


# Captured geometry from rolling-main-post-v44-20261021: b57f582e original
# and 2 mm floor candidates, e2736a7d settled value, and 08a546b3 static header.
# The 08a pre-format value height (3.284359 mm) is NOT the post-format height.
# Interpolation between captured font candidates and translation after setters
# are offline models, not repaired-native/PDF evidence or a font rasterizer.
_MATERIAL_CELL = (
    0.05834624965960972, 0.026063800868219113,
    0.15771712966333695, 0.03358693677109888,
)
_MATERIAL_ANCHOR = (0.060871386, 0.029527135, 0.0)
_MATERIAL_HEIGHT = 0.00238125
_MATERIAL_BOXES = (
    pytest.param(
        ((0.060840635746728294, 0.026195287749293993,
          0.07605240404159115, 0.02965250781630828),
         (0.060840635746728294, 0.026541009755995423,
          0.07363234999468116, 0.02965250781630828)),
        id="b57-five-family",
    ),
    pytest.param(
        ((0.060767717978353196, 0.026166222624836796,
          0.07616662488156331, 0.029672904394874737),
         (0.060767717978353196, 0.026623615899189573,
          0.07372719408501517, 0.029672904394874737)),
        id="b57-block",
    ),
)
_HEADER_ANCHOR = (0.0612717868804293, 0.0327876061983514, 0.0)
_HEADER_BOX = (
    0.0611863577534297, 0.0303439518297111,
    0.0705208519343683, 0.0329368668799719,
)
_E273_ANCHOR = (0.060871386498226154, 0.0314286057150094, 0.0)
_E273_BOX = (
    0.060840635746728294, 0.02809675878615185,
    0.07605240404159115, 0.03155397885316614,
)


class _MeasuredMaterialDisplay(_Display):
    def GetTextCount(self):
        return 0 if self.note.empty_display else self.note.rows * self.note.fragments

    def GetTextAtIndex(self, index):
        return self.note._text[index::self.GetTextCount()]

    def GetTextPositionAtIndex(self, index):
        if self.note.unreadable_display:
            return None
        left, bottom, _, right, top, _ = self.note.extent
        row, fragment = divmod(index, self.note.fragments)
        return (
            left + fragment * (right - left) / self.note.fragments,
            top - (row + 1) * (top - bottom) / (self.note.rows + 1),
            self.note.anchor[2],
        )

    def GetTextLineSpacingAtIndex(self, index):
        return self.note.annotation._format.LineSpacing


class _MeasuredMaterialAnnotation(_Annotation):
    def __init__(self, note):
        super().__init__(note)
        self._format = _Format(height=_MATERIAL_HEIGHT, length=0.0, face="Century Gothic")

    def GetDisplayData(self):
        return _MeasuredMaterialDisplay(self.note)


class _MeasuredMaterialNote(_Note):
    def __init__(self, expression, box, floor_box, *, header=False):
        self.reference_box = box
        self.floor_box = floor_box
        self.reference_anchor = _HEADER_ANCHOR if header else _MATERIAL_ANCHOR
        self.fragments = 1
        super().__init__(
            expression, "MATERIAL" if header else "Alloy Steel",
            _MATERIAL_CELL, material=not header,
        )
        self.anchor = self.reference_anchor
        self.name = "DetailItem279" if header else "DetailItem244"
        self.annotation = _MeasuredMaterialAnnotation(self)
        self.refresh()

    def refresh(self):
        # Preserve the actual floor ink: scaling the original box by 2/2.38125
        # would invent a smaller 2.904 mm box instead of native 3.111498 mm.
        fraction = (self.annotation._format.CharHeight - 0.002) / (
            _MATERIAL_HEIGHT - 0.002
        )
        box = tuple(
            floor + fraction * (original - floor)
            for original, floor in zip(self.reference_box, self.floor_box, strict=True)
        )
        x, y, z = self.anchor
        dx = x - self.reference_anchor[0] + self.extent_shift[0]
        dy = y - self.reference_anchor[1] + self.extent_shift[1]
        self.rows = self.forced_rows or 1
        self.extent = (
            box[0] + dx, box[1] + dy, z, box[2] + dx, box[3] + dy, z,
        )


@pytest.fixture(params=_MATERIAL_BOXES)
def measured_material_title(native_title, request):
    def make(selected="Material Specification"):
        scene = native_title(selected)
        initial, floor = request.param
        material = _MeasuredMaterialNote(title.property_link(selected), initial, floor)
        header = _MeasuredMaterialNote("MATERIAL", _HEADER_BOX, _HEADER_BOX, header=True)
        scene.notes[1] = material
        scene.notes.append(header)
        scene.material, scene.header = material, header
        scene.initial_material_box = initial
        scene.draw.rules = tuple(
            segment for note in scene.notes for segment in _rules(note.cell)
        )
        scene.draw.relink()
        return scene

    return make


def _styles(annotation):
    """Independent test snapshot; never delegates preservation to the fitter."""
    return tuple(
        tuple(
            (name, fmt.IsHeightSpecifiedInPts() if name == "IsHeightSpecifiedInPts"
             else getattr(fmt, name))
            for name in _STYLE_FIELDS
        )
        for fmt in (annotation.GetTextFormat(index)
                    for index in range(annotation.GetTextFormatCount()))
    )


def _material_readback(note):
    annotation = note.GetAnnotation()
    display = annotation.GetDisplayData()
    return (
        note.GetName(), annotation.OwnerType, note.PropertyLinkedText, note.GetText(),
        annotation.GetPosition(), _styles(annotation), note.Angle,
        note.GetTextJustification(), note.GetTextVerticalJustification(),
        tuple(annotation.GetUseDocTextFormat(index)
              for index in range(annotation.GetTextFormatCount())),
        note.GetExtent(),
        tuple(display.GetTextPositionAtIndex(index)
              for index in range(display.GetTextCount())),
    )


def _material_limit():
    left, bottom, right, top = _MATERIAL_CELL
    return left + 0.0006, bottom + 0.0006, right - 0.0006, top - 0.0006


def _right_region(header):
    return (header.GetExtent()[3] + 0.0006, *_material_limit()[1:])


def _assert_inside(note, region):
    left, bottom, _, right, top, _ = note.GetExtent()
    xmin, ymin, xmax, ymax = region
    assert xmin <= left <= right <= xmax
    assert ymin <= bottom <= top <= ymax


def _fit_label_right(scene):
    return title.fit_purchased_title_block(
        scene.adapter, spec=scene.spec, material_property=scene.selected,
        material_alignment="label_right",
    )


def _fit_material_only(scene):
    return title._fit_title_note(
        scene.adapter, scene.draw, scene.draw.sheet, scene.material,
        label="Material", minimum=0.002, material_property=scene.selected,
        alignment="label_right", label_note=scene.header,
    )


def _assert_readonly_material_proof(scene, settled):
    state = tuple(_material_readback(note) for note in (scene.material, scene.header))
    annotations = [note.GetAnnotation() for note in scene.notes]
    before = (
        scene.draw.rebuilds,
        [len(annotation.formats) for annotation in annotations],
        [len(annotation.positions) for annotation in annotations],
    )
    try:
        settled()
    finally:
        assert tuple(_material_readback(note) for note in (scene.material, scene.header)) == state
        assert (
            scene.draw.rebuilds,
            [len(annotation.formats) for annotation in annotations],
            [len(annotation.positions) for annotation in annotations],
        ) == before


def _with_native_material_height_mode(scene, *, points_mode, needs_reduction=False):
    note = scene.material
    note.annotation._format = _HeightModeFormat(
        note.annotation._format, points_mode=points_mode,
    )
    # Actual 18ab native metre readback, seeded without authoring either unit.
    note.annotation._format._height_m = 0.0023812499999999997
    scene.header.annotation._format = _HeightModeFormat(
        scene.header.annotation._format, points_mode=True,
    )
    for item in (note, scene.header):
        item.annotation.extra_formats = [
            _HeightModeFormat(_Format(height=0.0019, face="Arial Narrow"), points_mode=True),
        ]
        item.annotation.extra_use_doc = [False]
    if needs_reduction:
        left, _, right, top = note.reference_box
        note.reference_box = (left, top - 0.007, right, top)
    note.refresh()
    return scene


@pytest.fixture
def material_fit_events(monkeypatch):
    events = []
    monkeypatch.setattr(
        title._telemetry, "event",
        lambda name, **fields: events.append((name, fields)),
    )
    return events


@pytest.mark.parametrize(
    "alignment", (None, False, True, 0, 1, "", "centered", "center", "Label_right", (), {}),
)
def test_public_title_refuses_invalid_material_alignment_before_native_access(alignment):
    with pytest.raises(ValueError, match="material_alignment"):
        title.fit_purchased_title_block(
            object(), spec=object(), material_alignment=alignment,
        )


@pytest.mark.parametrize("selected", ("Material Specification", "Material"))
def test_public_title_default_alignment_is_exactly_fixed_without_label(native_title, selected):
    default, explicit = native_title(selected), native_title(selected)
    default_settled = title.fit_purchased_title_block(
        default.adapter, spec=default.spec, material_property=selected,
    )
    explicit_settled = title.fit_purchased_title_block(
        explicit.adapter, spec=explicit.spec, material_property=selected,
        material_alignment="fixed",
    )
    assert [_snapshot(note) for note in default.notes] == [
        _snapshot(note) for note in explicit.notes
    ]
    for scene, settled in ((default, default_settled), (explicit, explicit_settled)):
        _assert_native_fit(scene)
        scene.draw.EditRebuild3()
        settled()
        assert all(not note.annotation.positions for note in scene.notes)
        assert all(note.annotation.format_count_reads == 0 for note in scene.notes)
        assert all(note.justification_reads == 0 for note in scene.notes)


@pytest.mark.parametrize("selected", ("Material Specification", "Material"))
@pytest.mark.parametrize("fragments", (1, 3), ids=("whole-run", "same-baseline-fragments"))
def test_label_right_centres_complete_native_value_retaining_original_font(
    measured_material_title, selected, fragments,
):
    scene = measured_material_title(selected)
    note, header = scene.material, scene.header
    note.fragments = fragments
    other = "Material" if selected == "Material Specification" else "Material Specification"
    alias = _Note(title.property_link(other), "UNSELECTED SOURCE VALUE",
                  (0.200, 0.010, 0.260, 0.025), material=True)
    alias.annotation._format.CharHeight = 0.001
    alias.refresh()
    scene.notes.insert(0, alias)
    scene.draw.relink()
    untouched_alias = _snapshot(alias)
    fixed_anchors = [item.anchor for item in (scene.name, scene.number)]
    original = _material_readback(note)
    header_before = _material_readback(header)
    initial = scene.initial_material_box
    assert title._box(note.GetExtent(), label="Material", kind="note") == initial
    assert initial[1] < _material_limit()[1]
    assert header_before[0:4] == ("DetailItem279", 2, "MATERIAL", "MATERIAL")
    assert title._ruled_cell(scene.draw.sheet, header.anchor) == _MATERIAL_CELL
    assert title._ruled_cell(scene.draw.sheet, note.anchor) == _MATERIAL_CELL
    note.extent_reads.clear()
    header.extent_reads.clear()

    settled = _fit_label_right(scene)

    xmin, ymin, xmax, ymax = _right_region(header)
    left, bottom, right, top = initial
    dx = (xmin + xmax - left - right) / 2
    dy = (ymin + ymax - bottom - top) / 2
    expected_anchor = (_MATERIAL_ANCHOR[0] + dx, _MATERIAL_ANCHOR[1] + dy, 0.0)
    expected_box = (left + dx, bottom + dy, 0.0, right + dx, top + dy, 0.0)
    annotation = note.GetAnnotation()
    assert annotation.GetPosition() == pytest.approx(expected_anchor, abs=1e-12)
    assert dx > 0.04 and dy > 0.001  # Both approved sheet axes actually move.
    assert note.anchor[2] == _MATERIAL_ANCHOR[2]
    assert note.GetExtent() == pytest.approx(expected_box, abs=1e-12)
    assert _styles(annotation) == original[5]
    assert annotation._format.CharHeight == _MATERIAL_HEIGHT
    assert annotation._format.LineLength == 0.0
    assert note.PropertyLinkedText == original[2] and note.GetText() == original[3]
    assert note.Angle == original[6]
    assert (note.GetTextJustification(), note.GetTextVerticalJustification()) == original[7:9]
    assert annotation.GetUseDocTextFormat(0) is False
    assert len(annotation.formats) == len(annotation.positions) == 1
    assert annotation.positions[0] == pytest.approx(expected_anchor, abs=1e-12)
    assert note.GetExtent()[0] - xmin == pytest.approx(xmax - note.GetExtent()[3], abs=1e-12)
    assert note.GetExtent()[1] - ymin == pytest.approx(ymax - note.GetExtent()[4], abs=1e-12)
    assert note.GetExtent()[0] - header.GetExtent()[3] > 0.030
    _assert_inside(note, _right_region(header))
    _assert_inside(header, _material_limit())
    assert _material_readback(header) == header_before
    assert not header.annotation.formats and not header.annotation.positions
    assert [item.anchor for item in (scene.name, scene.number)] == fixed_anchors
    assert all(not item.annotation.positions for item in (scene.name, scene.number, alias))
    assert _snapshot(alias) == untouched_alias
    assert len(note.extent_reads) >= 3 and len(header.extent_reads) >= 3
    assert scene.draw.rebuilds in note.extent_epochs
    assert scene.draw.rebuilds in header.extent_epochs
    scene.draw.EditRebuild3()
    note.extent_epochs.clear()
    header.extent_epochs.clear()
    _assert_readonly_material_proof(scene, settled)
    assert scene.draw.rebuilds in note.extent_epochs
    assert scene.draw.rebuilds in header.extent_epochs


def test_e273_settled_value_still_requires_horizontal_foreign_header_clearance(
    measured_material_title,
):
    scene = measured_material_title("Material")
    note = scene.material
    note.reference_anchor = note.anchor = _E273_ANCHOR
    note.reference_box = _E273_BOX
    # Only this original-font candidate is used; no claim of a captured e273 floor.
    note.floor_box = _E273_BOX
    note.refresh()
    assert title.note_fits_cell(_E273_BOX, 1, _material_limit())
    assert _E273_BOX[0] < _HEADER_BOX[2] and _E273_BOX[3] > _HEADER_BOX[1]
    settled = _fit_label_right(scene)
    assert note.anchor[0] > _E273_ANCHOR[0] + 0.04
    assert note.anchor[1:] == pytest.approx(_E273_ANCHOR[1:], abs=1e-12)
    assert note.annotation._format.CharHeight == _MATERIAL_HEIGHT
    _assert_inside(note, _right_region(scene.header))
    _assert_readonly_material_proof(scene, settled)


def test_b57_floor_ink_cannot_be_replaced_with_a_smaller_y_only_fixture(
    measured_material_title,
):
    scene = measured_material_title("Material")
    note = scene.material
    note.annotation._format.CharHeight = 0.002
    note.refresh()
    box = title._box(note.GetExtent(), label="captured floor", kind="note")
    assert box == pytest.approx(note.floor_box, abs=1e-12)
    assert any(
        box[3] - box[1] == pytest.approx(height, abs=1e-12)
        for height in (0.003111498060312857, 0.003049288495685164)
    )
    below_header_height = _HEADER_BOX[1] - 0.0006 - _material_limit()[1]
    assert below_header_height == pytest.approx(0.003080150961491987, abs=1e-12)
    if box[3] - box[1] > below_header_height:
        assert box[3] - box[1] - below_header_height > 0.000031
    assert not title.note_fits_cell(box, 1, _material_limit())
    with pytest.raises(RuntimeError, match="cannot fit.*readable floor"):
        title._fit_title_note(
            scene.adapter, scene.draw, scene.draw.sheet, note,
            label="Material", minimum=0.002, material_property="Material",
        )
    assert not note.annotation.positions


@pytest.mark.parametrize("result", (False, None, 1))
def test_label_right_requires_boolean_position_setter_success(measured_material_title, result):
    scene = measured_material_title("Material")
    scene.material.annotation.position_result = result
    with pytest.raises(RuntimeError, match="position|anchor"):
        _fit_label_right(scene)
    assert scene.material.anchor == _MATERIAL_ANCHOR
    assert len(scene.material.annotation.positions) == 1
    assert scene.material.annotation._format.CharHeight == _MATERIAL_HEIGHT


@pytest.mark.parametrize("fault", ("ignored", "clamped-y", "clamped-x", "clamped-z"))
def test_label_right_refuses_unpersisted_requested_position(measured_material_title, fault):
    scene = measured_material_title("Material")
    annotation = scene.material.annotation
    if fault == "ignored":
        annotation.ignore_position_setter = True
    else:
        axis = {"clamped-x": 0, "clamped-y": 1, "clamped-z": 2}[fault]
        annotation.position_offset = tuple(0.00001 if index == axis else 0.0 for index in range(3))
    with pytest.raises(RuntimeError, match="position|anchor|did not persist"):
        _fit_label_right(scene)
    assert len(annotation.positions) == 1
    assert math.dist(annotation.GetPosition(), annotation.positions[0]) > 1e-7


@pytest.mark.parametrize("anchor", ((0.06, 0.03), (0.06, math.nan, 0), (math.inf, 0.03, 0)))
@pytest.mark.parametrize("field", ("material", "header"))
def test_label_right_refuses_unreadable_native_anchors(measured_material_title, field, anchor):
    scene = measured_material_title("Material")
    getattr(scene, field).anchor = anchor
    with pytest.raises(RuntimeError, match="anchor|position|ruled cell"):
        _fit_material_only(scene)
    assert not scene.material.annotation.positions


@pytest.mark.parametrize(
    "fault", ("missing", "duplicate", "wrong-owner", "linked-literal", "raw-prefix",
              "resolved-case", "foreign-cell", "header-outside-inset"),
)
def test_label_right_requires_unique_exact_format_owned_material_header(
    measured_material_title, fault,
):
    scene = measured_material_title("Material")
    header = scene.header
    if fault == "missing":
        scene.notes.remove(header)
    elif fault == "duplicate":
        duplicate = _MeasuredMaterialNote("MATERIAL", _HEADER_BOX, _HEADER_BOX, header=True)
        duplicate.name = "DetailItem999"
        scene.notes.append(duplicate)
    elif fault == "wrong-owner":
        header.annotation.OwnerType = 1
    elif fault == "linked-literal":
        header._link = '$PRPSHEET:"MATERIAL"'
    elif fault == "raw-prefix":
        header._link = " MATERIAL"
    elif fault == "resolved-case":
        header._text = "Material"
    elif fault == "foreign-cell":
        header.anchor = (0.202, 0.020, 0.0)
        scene.draw.rules += _rules((0.200, 0.010, 0.260, 0.025))
        header.refresh()
    else:
        header.extent_shift = (0.0, 0.001)
        header.refresh()
    scene.draw.relink()
    before = _material_readback(header)
    with pytest.raises(RuntimeError):
        _fit_label_right(scene)
    assert _material_readback(header) == before
    assert not header.annotation.formats and not header.annotation.positions
    assert not scene.material.annotation.positions


def test_private_label_right_requires_its_explicit_native_label_note(measured_material_title):
    scene = measured_material_title("Material")
    with pytest.raises(RuntimeError, match="label|MATERIAL"):
        title._fit_title_note(
            scene.adapter, scene.draw, scene.draw.sheet, scene.material,
            label="Material", minimum=0.002, material_property="Material",
            alignment="label_right",
        )
    assert not scene.material.annotation.positions


@pytest.mark.parametrize("fault", ("height", "width", "wrap"))
def test_label_right_refuses_complete_glyph_overflow_and_wrapping_at_original_floor(
    measured_material_title, fault,
):
    scene = measured_material_title("Material")
    note = scene.material
    if fault == "wrap":
        note.forced_rows = 2
    else:
        # Both complete captured candidates are enlarged, not just display-run
        # baselines: a tiny first fragment must not hide the rest of the ink.
        def oversized(box):
            left, bottom, right, top = box
            return (left, top - 0.010, right, top) if fault == "height" else (
                left, bottom, left + 0.110, top,
            )
        note.reference_box = oversized(note.reference_box)
        note.floor_box = oversized(note.floor_box)
        note.fragments = 3
    note.refresh()
    with pytest.raises(RuntimeError, match="cannot fit.*readable floor"):
        _fit_label_right(scene)
    heights = [fmt.CharHeight for fmt in note.annotation.formats]
    assert heights[0] == _MATERIAL_HEIGHT and heights[-1] == 0.002
    assert all(height >= 0.002 for height in heights)
    assert all(earlier > later for earlier, later in zip(heights, heights[1:]))
    assert all(position[2] == _MATERIAL_ANCHOR[2] for position in note.annotation.positions)
    assert note.GetText() == "Alloy Steel"
    assert not scene.header.annotation.formats and not scene.header.annotation.positions


def test_label_right_shrinks_only_when_complete_value_needs_unchanged_floor(
    measured_material_title,
):
    scene = measured_material_title("Material")
    note = scene.material
    left, bottom, right, top = note.reference_box
    note.reference_box = (left, top - 0.007, right, top)
    note.refresh()
    before = _styles(note.annotation)
    settled = _fit_label_right(scene)
    heights = [fmt.CharHeight for fmt in note.annotation.formats]
    assert heights[0] == _MATERIAL_HEIGHT
    assert 0.002 <= heights[-1] < heights[0]
    assert all(earlier > later for earlier, later in zip(heights, heights[1:]))
    after = _styles(note.annotation)
    assert tuple((name, value) for name, value in after[0]
                 if name not in ("CharHeight", "CharHeightInPts")) == tuple(
        (name, value) for name, value in before[0]
        if name not in ("CharHeight", "CharHeightInPts")
    )
    _assert_inside(note, _right_region(scene.header))
    _assert_readonly_material_proof(scene, settled)


@pytest.mark.parametrize("points_mode", (True, False), ids=("original-points", "original-metres"))
def test_label_right_native_height_mode_preserves_original_fitting_font_without_height_put(
    measured_material_title, material_fit_events, points_mode,
):
    scene = _with_native_material_height_mode(
        measured_material_title("Material"), points_mode=points_mode,
    )
    note, header = scene.material, scene.header
    annotation = note.annotation
    original = _material_readback(note)
    header_before = _material_readback(header)
    source_before = [
        (title.source_property_expression(item.PropertyLinkedText), item.GetText())
        for item in scene.notes if item is not header
    ]
    fixed_anchors = (scene.name.anchor, scene.number.anchor)
    for detached in (copy.copy(annotation._format), copy.deepcopy(annotation._format)):
        assert detached.IsHeightSpecifiedInPts() is points_mode
        assert detached.CharHeight == dict(original[5][0])["CharHeight"]
        assert not detached.height_writes and not detached.point_writes
        detached.CharHeight = detached.CharHeight
        assert detached.IsHeightSpecifiedInPts() is False
        assert annotation._format.IsHeightSpecifiedInPts() is points_mode
        assert not annotation._format.height_writes

    settled = _fit_label_right(scene)

    assert _styles(annotation) == original[5]  # Every field of every native format.
    assert annotation._format.CharHeight == 0.0023812499999999997
    assert annotation._format.IsHeightSpecifiedInPts() is points_mode
    assert not annotation._format.height_writes and not annotation._format.point_writes
    assert len(annotation.formats) == len(annotation.positions) == 1
    assert annotation.GetUseDocTextFormat(0) is False
    assert annotation.extra_use_doc == [False]
    assert _material_readback(note)[:4] == original[:4]
    assert _material_readback(note)[6:9] == original[6:9]
    assert _material_readback(header) == header_before
    assert not header.annotation.formats and not header.annotation.positions
    assert (scene.name.anchor, scene.number.anchor) == fixed_anchors
    assert [
        (title.source_property_expression(item.PropertyLinkedText), item.GetText())
        for item in scene.notes if item is not header
    ] == source_before
    _assert_inside(note, _right_region(header))
    _assert_inside(header, _material_limit())
    assert note.GetExtent()[0] - header.GetExtent()[3] >= 0.0006
    assert not [
        fields for event, fields in material_fit_events
        if event == "drawing.purchased_title_fit.height_write"
    ]
    candidates = [
        fields for event, fields in material_fit_events
        if event == "drawing.purchased_title_fit.candidate"
        and fields["alignment"] == "label_right"
    ]
    assert candidates
    assert all(
        fields["expected_height_in_points"] is points_mode
        and fields["actual_height_in_points"] is points_mode
        for fields in candidates
    )
    scene.draw.EditRebuild3()
    _assert_readonly_material_proof(scene, settled)
    assert _styles(annotation) == original[5]


@pytest.mark.parametrize("points_mode", (True, False), ids=("original-points", "original-metres"))
def test_label_right_native_height_reduction_verifies_owned_metres_transition_and_freezes_style(
    measured_material_title, material_fit_events, points_mode,
):
    scene = _with_native_material_height_mode(
        measured_material_title("Material"),
        points_mode=points_mode, needs_reduction=True,
    )
    note, header = scene.material, scene.header
    annotation = note.annotation
    original = _material_readback(note)
    header_before = _material_readback(header)
    foreign_before = tuple(_material_readback(item) for item in (scene.name, scene.number))
    assert note.GetExtent()[4] - note.GetExtent()[1] == pytest.approx(0.007, abs=1e-12)

    settled = _fit_material_only(scene)

    heights = [fmt.CharHeight for fmt in annotation.formats]
    assert heights[0] == 0.0023812499999999997
    assert 0.002 <= heights[-1] < heights[0]
    assert all(
        later == max(0.002, round(earlier - 0.0001, 7))
        for earlier, later in zip(heights, heights[1:])
    )
    assert annotation.formats[0].IsHeightSpecifiedInPts() is points_mode
    assert not annotation.formats[0].height_writes
    assert all(fmt.IsHeightSpecifiedInPts() is False for fmt in annotation.formats[1:])
    actual = annotation.GetTextFormat(0)
    assert actual.CharHeight == heights[-1]
    assert actual.IsHeightSpecifiedInPts() is False
    assert actual.height_writes == tuple(heights[1:])
    assert all(not fmt.point_writes for fmt in annotation.formats)
    after = _material_readback(note)
    assert after[:4] == original[:4]
    assert after[6:9] == original[6:9]
    assert after[9] == (False, *original[9][1:])
    for index, (before_style, after_style) in enumerate(zip(original[5], after[5], strict=True)):
        owned = ("CharHeight", "CharHeightInPts", "IsHeightSpecifiedInPts") if index == 0 else ()
        assert tuple(field for field in after_style if field[0] not in owned) == tuple(
            field for field in before_style if field[0] not in owned
        )
    assert _material_readback(header) == header_before
    assert tuple(_material_readback(item) for item in (scene.name, scene.number)) == foreign_before
    assert not header.annotation.formats and not header.annotation.positions
    _assert_inside(note, _right_region(header))
    _assert_inside(header, _material_limit())
    assert note.GetExtent()[0] - header.GetExtent()[3] >= 0.0006
    transitions = [
        fields for event, fields in material_fit_events
        if event == "drawing.purchased_title_fit.height_write"
    ]
    assert len(transitions) == len(heights) - 1
    for index, transition in enumerate(transitions):
        assert transition == {
            "label": "Material",
            "previous_height_m": heights[index],
            "requested_height_m": heights[index + 1],
            "actual_height_m": heights[index + 1],
            "previous_height_in_points": points_mode if index == 0 else False,
            "expected_height_in_points": False,
            "actual_height_in_points": False,
            "height_tolerance_m": 1e-7,
        }
    frozen_style = _styles(annotation)
    scene.draw.EditRebuild3()
    _assert_readonly_material_proof(scene, settled)
    assert _styles(annotation) == frozen_style
    assert annotation.GetTextFormat(0).IsHeightSpecifiedInPts() is False


def test_label_right_native_external_mode_flip_before_reduction_is_not_an_owned_transition(
    measured_material_title, material_fit_events, monkeypatch,
):
    scene = _with_native_material_height_mode(
        measured_material_title("Material"), points_mode=True, needs_reduction=True,
    )
    note, annotation = scene.material, scene.material.annotation
    original = _material_readback(note)
    header_before = _material_readback(scene.header)
    native_extent = note.GetExtent
    changed = False

    def extent_with_external_mode_change():
        nonlocal changed
        extent = native_extent()
        if scene.draw.rebuilds == 1 and not changed:
            # The first candidate's fresh style has already been checked.
            # Native extent collection observes an external mode-only edit;
            # the next candidate genuinely needs a smaller metre height.
            region = _right_region(scene.header)
            assert extent[4] - extent[1] > region[3] - region[1]
            annotation._format._points_mode = False
            changed = True
        return extent

    monkeypatch.setattr(note, "GetExtent", extent_with_external_mode_change)
    with pytest.raises(
        RuntimeError, match="MATERIAL label or protected value style/anchor changed",
    ) as refused:
        _fit_material_only(scene)
    assert changed
    message = str(refused.value)
    assert "phase='before-height-write', formatted=True" in message
    assert ast.literal_eval(message.split("differences=", 1)[1]) == {
        "material.protected_style[0].IsHeightSpecifiedInPts": {
            "expected": True, "actual": False, "tolerance": 0,
        },
    }
    assert annotation._format.CharHeight == dict(original[5][0])["CharHeight"]
    assert not annotation._format.height_writes and not annotation._format.point_writes
    assert len(annotation.formats) == 1 and not annotation.positions
    assert _material_readback(note)[:4] == original[:4]
    assert _material_readback(scene.header) == header_before
    assert not [
        fields for event, fields in material_fit_events
        if event == "drawing.purchased_title_fit.height_write"
    ]


@pytest.mark.parametrize("result", (False, None, 1), ids=("false", "none", "integer-one"))
def test_label_right_native_reduction_requires_boolean_setter_before_authorizing_mode(
    measured_material_title, material_fit_events, monkeypatch, result,
):
    scene = _with_native_material_height_mode(
        measured_material_title("Material"), points_mode=True, needs_reduction=True,
    )
    annotation = scene.material.annotation
    original = _material_readback(scene.material)
    header_before = _material_readback(scene.header)
    native_setter = annotation.SetTextFormat

    def refuse_reduction(index, use_doc, text_format):
        if text_format.CharHeight < dict(original[5][0])["CharHeight"]:
            annotation.setter_result = result
        return native_setter(index, use_doc, text_format)

    monkeypatch.setattr(annotation, "SetTextFormat", refuse_reduction)
    with pytest.raises(RuntimeError, match="local text format setter refused"):
        _fit_material_only(scene)
    assert len(annotation.formats) == 2
    assert annotation.formats[-1].CharHeight < annotation.formats[0].CharHeight
    assert annotation.formats[-1].IsHeightSpecifiedInPts() is False
    assert _styles(annotation) == original[5]
    assert annotation.GetUseDocTextFormat(0) is False  # Only the original candidate persisted.
    assert not annotation.positions
    assert _material_readback(scene.material)[:4] == original[:4]
    assert _material_readback(scene.header) == header_before
    assert not [
        fields for event, fields in material_fit_events
        if event == "drawing.purchased_title_fit.height_write"
    ]


@pytest.mark.parametrize(
    "fault", ("ignored-format", "ignored-height", "wrong-height", "retained-points-mode"),
)
def test_label_right_native_reduction_refuses_lying_height_or_mode_readback_before_move(
    measured_material_title, material_fit_events, monkeypatch, fault,
):
    scene = _with_native_material_height_mode(
        measured_material_title("Material"), points_mode=True, needs_reduction=True,
    )
    annotation = scene.material.annotation
    original = _material_readback(scene.material)
    original_height = dict(original[5][0])["CharHeight"]
    header_before = _material_readback(scene.header)
    native_setter = annotation.SetTextFormat

    def misapply_reduction(index, use_doc, text_format):
        reduction = text_format.CharHeight < original_height
        annotation.ignore_setter = reduction and fault == "ignored-format"
        result = native_setter(index, use_doc, text_format)
        if reduction:
            if fault == "ignored-height":
                annotation._format._height_m = original_height
            elif fault == "wrong-height":
                annotation._format._height_m = text_format.CharHeight + 2e-7
            elif fault == "retained-points-mode":
                annotation._format._points_mode = True
        return result

    monkeypatch.setattr(annotation, "SetTextFormat", misapply_reduction)
    with pytest.raises(RuntimeError, match="local height setter did not persist"):
        _fit_material_only(scene)
    assert len(annotation.formats) == 2
    requested = annotation.formats[-1]
    assert requested.CharHeight == max(0.002, round(original_height - 0.0001, 7))
    assert requested.IsHeightSpecifiedInPts() is False
    actual = annotation.GetTextFormat(0)
    expected_height = (
        original_height if fault in ("ignored-format", "ignored-height") else
        requested.CharHeight + (2e-7 if fault == "wrong-height" else 0)
    )
    assert actual.CharHeight == expected_height
    assert actual.IsHeightSpecifiedInPts() is (
        fault in ("ignored-format", "retained-points-mode")
    )
    assert not actual.point_writes
    assert not annotation.positions
    assert scene.material.anchor == original[4]
    assert _material_readback(scene.material)[:4] == original[:4]
    assert _material_readback(scene.header) == header_before
    assert not [
        fields for event, fields in material_fit_events
        if event == "drawing.purchased_title_fit.height_write"
    ]


@pytest.mark.parametrize("needs_reduction", (False, True), ids=("original-font", "owned-reduction"))
def test_label_right_native_final_frozen_mode_refuses_an_external_flip_readonly(
    measured_material_title, needs_reduction,
):
    scene = _with_native_material_height_mode(
        measured_material_title("Material"),
        points_mode=True, needs_reduction=needs_reduction,
    )
    settled = _fit_material_only(scene)
    annotation = scene.material.annotation
    accepted_mode = not needs_reduction
    assert annotation.GetTextFormat(0).IsHeightSpecifiedInPts() is accepted_mode
    _assert_inside(scene.material, _right_region(scene.header))
    _assert_inside(scene.header, _material_limit())
    frozen_style = _styles(annotation)
    annotation._format._points_mode = not accepted_mode
    scene.draw.EditRebuild3()
    with pytest.raises(
        RuntimeError, match="MATERIAL label or protected value style/anchor changed",
    ) as refused:
        _assert_readonly_material_proof(scene, settled)
    message = str(refused.value)
    assert "phase='settled', formatted=True" in message
    differences = ast.literal_eval(message.split("differences=", 1)[1])
    assert differences == {
        f"material.{kind}[0].IsHeightSpecifiedInPts": {
            "expected": accepted_mode, "actual": not accepted_mode, "tolerance": 0,
        }
        for kind in ("protected_style", "accepted_style")
    }
    assert _styles(annotation)[1:] == frozen_style[1:]


def test_label_right_refuses_a_native_header_leaving_no_right_value_region(measured_material_title):
    scene = measured_material_title("Material")
    left, bottom, _, top = scene.header.reference_box
    wide = (left, bottom, _material_limit()[2] - 0.0001, top)
    scene.header.reference_box = scene.header.floor_box = wide
    scene.header.refresh()
    _assert_inside(scene.header, _material_limit())
    with pytest.raises(RuntimeError):
        _fit_label_right(scene)
    assert not scene.material.annotation.positions


def _change_style(fmt, field):
    if field == "IsHeightSpecifiedInPts":
        fmt._points_mode = not fmt.IsHeightSpecifiedInPts()
        return
    value = getattr(fmt, field)
    changed = not value if type(value) is bool else (
        value + "-changed" if type(value) is str else value + (
            1 if type(value) is int else 0.00001
        )
    )
    setattr(fmt, field, changed)


@pytest.mark.parametrize("field", _STYLE_FIELDS)
@pytest.mark.parametrize("target,index", (("header", 0), ("header", 1), ("material", 0), ("material", 1)))
def test_label_right_final_proof_preserves_every_native_format_field(
    measured_material_title, target, index, field,
):
    scene = measured_material_title("Material")
    for note in (scene.header, scene.material):
        note.annotation.extra_formats = [_Format(height=0.0019, face="Arial Narrow")]
        note.annotation.extra_use_doc = [False]
    settled = _fit_label_right(scene)
    note = getattr(scene, target)
    fmt = note.annotation._format if index == 0 else note.annotation.extra_formats[index - 1]
    _change_style(fmt, field)
    scene.draw.EditRebuild3()
    with pytest.raises(RuntimeError):
        _assert_readonly_material_proof(scene, settled)


@pytest.mark.parametrize("target", ("header", "material"))
@pytest.mark.parametrize(
    "fault", ("raw", "text", "owner", "anchor-x", "anchor-y", "anchor-z",
              "angle", "horizontal", "vertical", "doc", "extra-doc",
              "format-count", "left", "right", "bottom", "top"),
)
def test_label_right_final_readonly_proof_refuses_native_identity_and_geometry_drift(
    measured_material_title, target, fault,
):
    scene = measured_material_title("Material")
    for note in (scene.header, scene.material):
        note.annotation.extra_formats = [_Format(height=0.0019)]
        note.annotation.extra_use_doc = [False]
    settled = _fit_label_right(scene)
    note = getattr(scene, target)
    if fault == "raw":
        note._link += " "
    elif fault == "text":
        note._text += " "
    elif fault == "owner":
        note.annotation.OwnerType = 1
    elif fault.startswith("anchor-"):
        axis = {"anchor-x": 0, "anchor-y": 1, "anchor-z": 2}[fault]
        note.anchor = tuple(value + (0.00001 if index == axis else 0.0)
                            for index, value in enumerate(note.anchor))
    elif fault == "angle":
        note.Angle = 0.01
    elif fault == "horizontal":
        note.horizontal_justification = 2
    elif fault == "vertical":
        note.vertical_justification = 1
    elif fault == "doc":
        note.annotation.use_doc = not note.annotation.use_doc
    elif fault == "extra-doc":
        note.annotation.extra_use_doc[0] = True
    elif fault == "format-count":
        note.annotation.extra_formats.append(_Format())
        note.annotation.extra_use_doc.append(False)
    else:
        note.extent_shift = {
            "left": (-0.100, 0.0), "right": (0.100, 0.0),
            "bottom": (0.0, -0.010), "top": (0.0, 0.010),
        }[fault]
    scene.draw.EditRebuild3()
    with pytest.raises(RuntimeError):
        _assert_readonly_material_proof(scene, settled)


@pytest.mark.parametrize("target", ("header", "material"))
@pytest.mark.parametrize("stage", ("format-rebuild", "position-rebuild"))
@pytest.mark.parametrize("fault", ("box", "style", "anchor", "text"))
def test_label_right_rereads_both_native_notes_after_each_candidate_rebuild(
    measured_material_title, target, stage, fault,
):
    scene = measured_material_title("Material")
    note = getattr(scene, target)

    def drift():
        if fault == "box":
            note.extent_shift = (0.100, 0.0)
        elif fault == "style":
            note.annotation._format.Italic = True
        elif fault == "anchor":
            x, y, z = note.anchor
            note.anchor = (x, y, z + 0.00001)
        else:
            note._text += " "

    # The private path isolates the actual candidate, not Name/Number rebuilds.
    scene.draw.rebuild_actions[1 if stage == "format-rebuild" else 2] = drift
    with pytest.raises(RuntimeError):
        _fit_material_only(scene)
    assert scene.draw.rebuilds >= (1 if stage == "format-rebuild" else 2)
    assert not scene.header.annotation.formats and not scene.header.annotation.positions


@pytest.mark.parametrize("target,index", (("header", 0), ("header", 1), ("material", 0), ("material", 1)))
def test_label_right_guard_diagnostic_names_rebuilt_format_member(
    measured_material_title, target, index,
):
    scene = measured_material_title("Material")
    annotation = getattr(scene, target).annotation
    annotation.extra_formats = [_Format(height=0.0019)]
    annotation.extra_use_doc = [False]
    baseline, fresh = 1.25, 1.25000005
    fmt = annotation._format if index == 0 else annotation.extra_formats[index - 1]
    fmt.CharSpacingFactor = baseline

    def drift():
        current = annotation._format if index == 0 else annotation.extra_formats[index - 1]
        current.CharSpacingFactor = fresh

    scene.draw.rebuild_actions[1] = drift
    with pytest.raises(
        RuntimeError, match="MATERIAL label or protected value style/anchor changed",
    ) as refused:
        _fit_material_only(scene)
    message = str(refused.value)
    assert "phase='after-fit-rebuild', formatted=True" in message
    differences = ast.literal_eval(message.split("differences=", 1)[1])
    prefix = "label.style" if target == "header" else "material.protected_style"
    assert differences == {
        f"{prefix}[{index}].CharSpacingFactor": {
            "expected": baseline, "actual": fresh, "delta": fresh - baseline, "tolerance": 0,
        },
    }
    assert 0 < fresh - baseline < 1e-7  # Exact formatting, not an anchor/height band.
    assert scene.draw.rebuilds == 1
    assert not scene.material.annotation.positions


@pytest.mark.parametrize("target", ("header", "material"))
def test_label_right_guard_diagnostic_reports_rebuilt_anchor_delta(
    measured_material_title, target,
):
    scene = measured_material_title("Material")
    note = getattr(scene, target)
    baseline = note.anchor
    fresh = (*baseline[:2], baseline[2] + 0.00001)
    scene.draw.rebuild_actions[1] = lambda: setattr(note, "anchor", fresh)
    with pytest.raises(
        RuntimeError, match="MATERIAL label or protected value style/anchor changed",
    ) as refused:
        _fit_material_only(scene)
    differences = ast.literal_eval(str(refused.value).split("differences=", 1)[1])
    change = {
        "expected": baseline, "actual": fresh, "delta": (0.0, 0.0, 0.00001),
        "tolerance": 0 if target == "header" else 1e-7,
    }
    if target == "material":
        change.update(distance=0.00001, comparison="euclidean")
    assert differences == {f"{'label' if target == 'header' else 'material'}.anchor_m": change}
    assert scene.draw.rebuilds == 1
    assert not scene.material.annotation.positions


@pytest.mark.parametrize("member,field", (("_link", "raw"), ("_text", "resolved")))
def test_label_right_guard_diagnostic_reports_literal_label_identity(
    measured_material_title, member, field,
):
    scene = measured_material_title("Material")
    scene.draw.rebuild_actions[1] = lambda: setattr(scene.header, member, "MATERIAL changed")
    with pytest.raises(
        RuntimeError, match="MATERIAL label or protected value style/anchor changed",
    ) as refused:
        _fit_material_only(scene)
    differences = ast.literal_eval(str(refused.value).split("differences=", 1)[1])
    assert differences == {
        f"label.{field}": {"expected": "MATERIAL", "actual": "MATERIAL changed", "tolerance": 0},
    }
    assert scene.draw.rebuilds == 1
    assert not scene.material.annotation.positions


@pytest.mark.parametrize("fault", ("missing", "duplicate", "renamed", "split-cell"))
def test_label_right_final_proof_rechecks_native_label_membership_and_original_grid(
    measured_material_title, fault,
):
    scene = measured_material_title("Material")
    settled = _fit_label_right(scene)
    if fault == "missing":
        scene.notes.remove(scene.header)
    elif fault == "duplicate":
        duplicate = _MeasuredMaterialNote("MATERIAL", _HEADER_BOX, _HEADER_BOX, header=True)
        duplicate.name = "DetailItem999"
        scene.notes.append(duplicate)
    elif fault == "renamed":
        scene.header.name = "DetailItem999"
    else:
        _, bottom, _, top = _MATERIAL_CELL
        scene.draw.rules += (_Line(0.080, bottom, 0.080, top),)
    scene.draw.relink()
    scene.draw.EditRebuild3()
    with pytest.raises(RuntimeError):
        _assert_readonly_material_proof(scene, settled)


def test_label_right_final_proof_uses_fresh_header_extent_even_inside_original_cell(
    measured_material_title,
):
    scene = measured_material_title("Material")
    settled = _fit_label_right(scene)
    scene.header.extent_shift = (0.040, 0.0)
    scene.draw.EditRebuild3()
    _assert_inside(scene.header, _material_limit())
    _assert_inside(scene.material, _material_limit())
    assert scene.header.GetExtent()[3] > scene.material.GetExtent()[0]
    with pytest.raises(RuntimeError):
        _assert_readonly_material_proof(scene, settled)


def test_label_right_refuses_native_rows_changing_during_position_rebuild(
    measured_material_title,
):
    scene = measured_material_title("Material")
    scene.draw.rebuild_actions[2] = lambda: setattr(scene.material, "forced_rows", 2)
    with pytest.raises(RuntimeError, match="row|placement"):
        _fit_material_only(scene)
    assert len(scene.material.annotation.positions) == 1
    assert scene.material.rows == 2


@pytest.mark.parametrize("target", ("header", "material"))
def test_label_right_after_position_rebuild_refuses_fresh_gap_violation_without_shrinking(
    measured_material_title, target,
):
    scene = measured_material_title("Material")
    note = getattr(scene, target)
    original_style = _styles(note.annotation)
    shift = (0.040, 0.0) if target == "header" else (-0.036, 0.0)
    scene.draw.rebuild_actions[2] = lambda: setattr(note, "extent_shift", shift)
    with pytest.raises(RuntimeError):
        _fit_material_only(scene)
    # Neither note leaves the original cell; no identity, style, row or anchor
    # guard can explain this refusal. The freshly measured foreign-header gap
    # is the failing invariant, before another font step or corrective move.
    _assert_inside(scene.header, _material_limit())
    _assert_inside(scene.material, _material_limit())
    assert scene.material.GetExtent()[0] < _right_region(scene.header)[0]
    assert scene.material.rows == 1
    assert scene.header.anchor == _HEADER_ANCHOR
    assert scene.material.anchor == scene.material.annotation.positions[0]
    assert _styles(note.annotation) == original_style
    assert len(scene.material.annotation.formats) == 1
    assert len(scene.material.annotation.positions) == 1
    assert scene.draw.rebuilds == 2


@pytest.mark.parametrize("result", (False, None, 1))
def test_label_right_requires_boolean_format_setter_success(measured_material_title, result):
    scene = measured_material_title("Material")
    scene.material.annotation.setter_result = result
    with pytest.raises(RuntimeError, match="format setter refused"):
        _fit_material_only(scene)
    assert scene.material.annotation.use_doc is True
    assert not scene.material.annotation.positions


def test_label_right_refuses_ignored_format_setter_even_when_height_already_fits(
    measured_material_title,
):
    scene = measured_material_title("Material")
    scene.material.annotation.ignore_setter = True
    with pytest.raises(RuntimeError):
        _fit_material_only(scene)
    assert scene.material.annotation.use_doc is True
    assert not scene.material.annotation.positions


@pytest.mark.parametrize("target", ("header", "material"))
@pytest.mark.parametrize(
    "extent", (None, (), (0.06, 0.03, 0.07),
               (0.06, math.nan, 0.0, 0.07, 0.03, 0.0),
               (0.07, 0.02, 0.0, 0.06, 0.03, 0.0)),
    ids=("unavailable", "empty", "incomplete", "nonfinite", "reversed"),
)
def test_label_right_requires_complete_finite_native_glyph_extents(
    measured_material_title, target, extent,
):
    scene = measured_material_title("Material")
    getattr(scene, target).extent = extent
    with pytest.raises(RuntimeError):
        _fit_material_only(scene)
    assert not scene.material.annotation.positions


@pytest.mark.parametrize("target", ("header", "material"))
@pytest.mark.parametrize("invalid", (None, object(), lambda: 1.0))
def test_label_right_does_not_coerce_or_call_nonprimitive_native_style_properties(
    measured_material_title, target, invalid,
):
    scene = measured_material_title("Material")
    getattr(scene, target).annotation._format.WidthFactor = invalid
    with pytest.raises((RuntimeError, TypeError)):
        _fit_material_only(scene)
    assert not scene.material.annotation.positions


@pytest.mark.parametrize("target", ("header", "material"))
def test_label_right_propagates_native_errors_in_later_text_formats(
    measured_material_title, target,
):
    scene = measured_material_title("Material")
    annotation = getattr(scene, target).annotation
    annotation.extra_formats = [_Format(height=0.0019)]
    annotation.extra_use_doc = [False]
    annotation.format_read_errors[1] = OSError("native text format unavailable")
    with pytest.raises(OSError, match="native text format unavailable"):
        _fit_material_only(scene)
    assert not scene.material.annotation.positions


def _snapshot(note):
    fmt = note.annotation._format
    return (note.PropertyLinkedText, note.GetText(), note.anchor, fmt.CharHeight,
            fmt.LineLength, fmt.TypeFaceName, note.annotation.use_doc, note.extent)


def _assert_native_fit(scene):
    for note, floor in zip(scene.notes[:3], (0.003, 0.002, 0.003), strict=True):
        fmt = note.annotation.GetTextFormat(0)
        assert floor <= fmt.CharHeight < 0.004
        assert note.rows == 1
        left, bottom, right, top = note.cell
        limit = (left + 0.0006, bottom + 0.0006, right - 0.0006, top - 0.0006)
        assert title.note_fits_cell(title._box(note.GetExtent(), label="test", kind="note"),
                                    note.rows, limit)
        assert note.annotation.GetUseDocTextFormat(0) is False
        assert fmt.TypeFaceName == "Arial"
        assert note.annotation.formats
        assert all(candidate.CharHeight >= floor for candidate in note.annotation.formats)
        assert title.source_property_expression(note.PropertyLinkedText) == (
            title.property_link(scene.selected) if note is scene.material else
            title.property_link("SW-Title(Title)" if note is scene.name else "Number")
        )
    assert scene.material.annotation._format.LineLength == 0.006
    for note in (scene.name, scene.number):
        assert note.annotation._format.LineLength == pytest.approx(
            note.cell[2] - 0.0006 - note.anchor[0] - 0.0003
        )


@pytest.mark.parametrize("selection", (None, "Material Specification", "Material"))
def test_public_title_fits_complete_values_and_persists_selected_native_format(
    native_title, selection,
):
    scene = native_title(selection or "Material Specification")
    originals = [(note.GetText(), note.anchor) for note in scene.notes]
    assert all(note.rows > 1 for note in scene.notes)
    options = {} if selection is None else {"material_property": selection}
    settled = title.fit_purchased_title_block(scene.adapter, spec=scene.spec, **options)
    _assert_native_fit(scene)
    before = [_snapshot(note) for note in scene.notes]
    scene.draw.EditRebuild3()
    rebuilds = scene.draw.rebuilds
    settled()
    assert scene.draw.rebuilds == rebuilds  # Final proof is read-only.
    assert [_snapshot(note) for note in scene.notes] == before
    assert [(note.GetText(), note.anchor) for note in scene.notes] == originals


@pytest.mark.parametrize("selected", ("Material", "Material Specification"))
def test_public_title_ignores_unselected_alias_without_rewriting_it(native_title, selected):
    scene = native_title(selected)
    other = "Material Specification" if selected == "Material" else "Material"
    alias = _Note(title.property_link(other), "UNSELECTED SOURCE VALUE",
                  (0.200, 0.010, 0.260, 0.025), material=True)
    alias.annotation._format.CharHeight = 0.001  # Unreadable if mistakenly fitted.
    alias.refresh()
    scene.notes.append(alias)
    scene.draw.relink()
    before = _snapshot(alias)
    settled = title.fit_purchased_title_block(
        scene.adapter, spec=scene.spec, material_property=selected,
    )
    _assert_native_fit(scene)
    settled()
    assert _snapshot(alias) == before


@pytest.mark.parametrize("selected", ("Number", "SW-Title(Title)"))
def test_public_title_refuses_material_authority_collisions_before_native_access(selected):
    # Neither object offers a native document or spec: a collision must be
    # refused before looking for either, not collapse a required field or floor.
    with pytest.raises(RuntimeError, match="three distinct source fields"):
        title.fit_purchased_title_block(
            object(), spec=object(), material_property=selected,
        )


@pytest.mark.parametrize("selected", ("Material", "Material Specification"))
@pytest.mark.parametrize("fault", ("missing", "other-property", "wrong-owner", "suffix", "duplicate"))
def test_public_title_requires_exactly_one_selected_material_field(native_title, selected, fault):
    scene = native_title(selected)
    if fault == "missing":
        scene.notes.remove(scene.material)
    elif fault == "duplicate":
        duplicate = _Note('<FONT size=15PTS>' + title.property_link(selected),
                          scene.material.GetText(), scene.material.cell, material=True)
        scene.notes.append(duplicate)
    elif fault == "other-property":
        other = "Material Specification" if selected == "Material" else "Material"
        scene.material._link = title.property_link(other)
    elif fault == "wrong-owner":
        scene.material._link = f'$PRP:"{selected}"'
    else:
        scene.material._link += " suffix"
    scene.draw.relink()
    before = [_snapshot(note) for note in scene.notes]
    with pytest.raises(RuntimeError, match="one note per source field"):
        title.fit_purchased_title_block(scene.adapter, spec=scene.spec, material_property=selected)
    assert [_snapshot(note) for note in scene.notes] == before
    assert scene.draw.rebuilds == 0


@pytest.mark.parametrize("field", ("name", "number"))
@pytest.mark.parametrize("fault", ("missing", "duplicate"))
def test_public_title_keeps_name_and_number_cardinality(native_title, field, fault):
    scene = native_title("Material")
    note = getattr(scene, field)
    if fault == "missing":
        scene.notes.remove(note)
    else:
        scene.notes.append(_Note(note.PropertyLinkedText, note.GetText(), note.cell))
    scene.draw.relink()
    with pytest.raises(RuntimeError, match="one note per source field"):
        title.fit_purchased_title_block(scene.adapter, spec=scene.spec, material_property="Material")
    assert scene.draw.rebuilds == 0


def test_public_title_keeps_exact_source_name_authority(native_title):
    scene = native_title("Material")
    scene.name._text += "-wrong"
    with pytest.raises(RuntimeError, match="not source identity"):
        title.fit_purchased_title_block(scene.adapter, spec=scene.spec, material_property="Material")
    assert scene.draw.rebuilds == 0


@pytest.mark.parametrize("selected", (None, "Material Specification", "Material"))
@pytest.mark.parametrize("linked", ("Material Specification", "Material", "Number"))
def test_private_material_length_exception_is_expression_selected_not_label_based(
    native_title, selected, linked,
):
    scene = native_title()
    note = scene.material
    note._link = title.property_link(linked)
    original_length = note.annotation._format.LineLength
    options = {} if selected is None else {"material_property": selected}
    settled = title._fit_title_note(
        scene.adapter, scene.draw, scene.draw.sheet, note,
        label="Material", minimum=0.002, **options,
    )
    expected_length = original_length if linked == (selected or "Material Specification") else (
        note.cell[2] - 0.0006 - note.anchor[0] - 0.0003
    )
    assert note.annotation._format.LineLength == pytest.approx(expected_length)
    assert note.rows == 1
    scene.draw.EditRebuild3()
    settled()


@pytest.mark.parametrize("field,floor", (("name", 0.003), ("material", 0.002), ("number", 0.003)))
def test_public_title_refuses_complete_value_overflow_at_unchanged_readable_floor(
    native_title, field, floor,
):
    scene = native_title("Material")
    note = getattr(scene, field)
    note._text = "X" * 300
    if field == "name":
        scene.spec.artifact_stem = note.GetText()
    with pytest.raises(RuntimeError, match="cannot fit.*readable floor"):
        title.fit_purchased_title_block(scene.adapter, spec=scene.spec, material_property="Material")
    assert note.annotation._format.CharHeight == pytest.approx(floor)
    assert min(fmt.CharHeight for fmt in note.annotation.formats) >= floor
    assert note.GetText() == "X" * 300


@pytest.mark.parametrize("field", ("name", "material", "number"))
@pytest.mark.parametrize("fault", ("height", "face", "doc", "anchor", "link", "value", "rows", "extent"))
def test_public_final_proof_refuses_native_format_identity_or_geometry_drift(
    native_title, field, fault,
):
    scene = native_title("Material")
    settled = title.fit_purchased_title_block(scene.adapter, spec=scene.spec, material_property="Material")
    note = getattr(scene, field)
    if fault == "height":
        note.annotation._format.CharHeight -= 0.00001
    elif fault == "face":
        note.annotation._format.TypeFaceName = "Courier New"
    elif fault == "doc":
        note.annotation.use_doc = True
    elif fault == "anchor":
        x, y, z = note.anchor
        note.anchor = (x + 0.00001, y, z)
    elif fault == "link":
        note._link = note.PropertyLinkedText.replace("$PRPSHEET:", "$PRP:")
    elif fault == "value":
        note._text += " "
    elif fault == "rows":
        note.forced_rows = 2
    else:
        note.extent_shift = (0.100, 0.0)
    scene.draw.EditRebuild3()
    with pytest.raises(RuntimeError, match="source property expression|did not persist"):
        settled()


@pytest.mark.parametrize("field", ("name", "number"))
def test_public_final_proof_keeps_nonmaterial_line_length_persistence(native_title, field):
    scene = native_title("Material")
    settled = title.fit_purchased_title_block(scene.adapter, spec=scene.spec, material_property="Material")
    getattr(scene, field).annotation._format.LineLength += 0.00001
    scene.draw.EditRebuild3()
    with pytest.raises(RuntimeError, match="did not persist"):
        settled()


@pytest.mark.parametrize("result", (False, None, 1))
def test_public_title_refuses_nonboolean_native_setter_success(native_title, result):
    scene = native_title("Material")
    scene.name.annotation.setter_result = result
    with pytest.raises(RuntimeError, match="local text format setter refused"):
        title.fit_purchased_title_block(scene.adapter, spec=scene.spec, material_property="Material")
    assert scene.name.annotation._format.CharHeight == 0.004


@pytest.mark.parametrize("fault", ("ignored-setter", "rebuild", "empty-display", "unreadable-display"))
def test_public_title_refuses_unapplied_format_and_unavailable_native_measurements(native_title, fault):
    scene = native_title("Material")
    if fault == "ignored-setter":
        scene.name.annotation.ignore_setter = True
    elif fault == "rebuild":
        scene.draw.rebuild_result = False
    elif fault == "empty-display":
        scene.name.empty_display = True
    else:
        scene.name.unreadable_display = True
    with pytest.raises(RuntimeError, match="cannot fit|rebuild failed|native text rows unavailable"):
        title.fit_purchased_title_block(scene.adapter, spec=scene.spec, material_property="Material")


# Exact owner cases: property identity, captured refusal, four edges and one row.

@pytest.mark.parametrize(
    ("raw", "expression"),
    [
        ('$PRPSHEET:"SW-Title(Title)"', '$PRPSHEET:"SW-Title(Title)"'),
        (
            '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"',
            '$PRPSHEET:"SW-Title(Title)"',
        ),
        ('<FONT size=15.5PTS>$PRPSHEET:"Material"', '$PRPSHEET:"Material"'),
        ('<FONT size=0.5PTS>$PRPSHEET:"Material"', '$PRPSHEET:"Material"'),
    ],
)
def test_source_property_expression_accepts_only_the_optional_font_wrapper(
    raw: str, expression: str
) -> None:
    from _purchased_title_fit import source_property_expression

    assert source_property_expression(raw) == expression

@pytest.mark.parametrize(
    "raw",
    [
        "",
        "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
        '$PRP:"SW-Title(Title)"',
        'NAME $PRPSHEET:"SW-Title(Title)"',
        '$PRPSHEET:"SW-Title(Title)" suffix',
        ' $PRPSHEET:"SW-Title(Title)"',
        '$PRPSHEET:"SW-Title(Title)" ',
        '$PRPSHEET:"SW-Title(Title)"$PRPSHEET:"Material"',
        '$PRPSHEET:"SW-Title(Title)"\n$PRPSHEET:"Material"',
        '$PRPSHEET:"SW-Title(Title)"\n',
        '$PRPSHEET:"SW-Title(Title)',
        '$PRPSHEET:SW-Title(Title)',
        '<B>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"</FONT>',
        '<FONT size=15PTS><FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS> $PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS>$PRP:"SW-Title(Title)"',
        '<FONT size=15PTS>literal',
        '<FONT size=0PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=-15PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=+15PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=1e1PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=NaNPTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=infPTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PX>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size="15PTS">$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS color=red>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS$PRPSHEET:"SW-Title(Title)"',
        '<font size=15PTS>$PRPSHEET:"SW-Title(Title)"',
    ],
)
def test_source_property_expression_refuses_noncontract_content(raw: str) -> None:
    from _purchased_title_fit import source_property_expression

    assert source_property_expression(raw) is None

def test_linked_value_preserves_captured_name_when_native_format_strips_font() -> None:
    from _purchased_title_fit import assert_linked_value

    # Captured native SetTextFormat readback: only FONT disappears; the full
    # source property and resolved Name remain intact. This is not a COM echo.
    assert_linked_value(
        '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"',
        "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
        '$PRPSHEET:"SW-Title(Title)"',
        "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
        label="Name",
    )

def test_linked_value_accepts_exact_wrapped_material_without_normalizing_text() -> None:
    from _purchased_title_fit import assert_linked_value

    # Synthetic identity control, not native after-fix evidence.
    assert_linked_value(
        '<FONT size=15PTS>$PRPSHEET:"Material"',
        "ALLOY STEEL",
        '$PRPSHEET:"Material"',
        "ALLOY STEEL",
        label="Material",
    )

@pytest.mark.parametrize(
    ("actual_link", "actual_text"),
    [
        pytest.param(
            '$PRPSHEET:"Title"',
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            id="different-property-even-with-identical-resolved-text",
        ),
        pytest.param(
            '$PRP:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            id="different-property-owner",
        ),
        pytest.param(
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            id="literal-replacement",
        ),
        pytest.param(
            'NAME $PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            id="extra-prefix",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)" suffix',
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            id="extra-suffix",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)"$PRPSHEET:"Material"',
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            id="second-link",
        ),
        pytest.param(
            '<B>$PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            id="unsupported-markup",
        ),
        pytest.param(
            '<FONT size=15PTS$PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin",
            id="malformed-font",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot",
            id="truncated-full-value",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin ",
            id="value-whitespace-is-not-normalized",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)"',
            "CH-ROCKER-ARM-TL-VN-OBLIQUE-PIVOT-CLEVIS-PIN",
            id="value-case-is-not-normalized",
        ),
    ],
)
def test_linked_value_refuses_true_identity_or_full_value_changes(
    actual_link: str, actual_text: str
) -> None:
    from _purchased_title_fit import assert_linked_value

    expected_link = '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"'
    expected_text = "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin"
    with pytest.raises(RuntimeError) as caught:
        assert_linked_value(
            expected_link, expected_text, actual_link, actual_text, label="Name"
        )
    message = str(caught.value)
    for raw in (expected_link, expected_text, actual_link, actual_text):
        assert repr(raw) in message

@pytest.mark.parametrize(
    "invalid_link",
    [
        'NAME $PRPSHEET:"SW-Title(Title)"',
        '<FONT size=0PTS>$PRPSHEET:"SW-Title(Title)"',
        '$PRP:"SW-Title(Title)"',
        "literal",
    ],
)
def test_linked_value_refuses_invalid_expected_link_even_when_unchanged(
    invalid_link: str,
) -> None:
    from _purchased_title_fit import assert_linked_value

    text = "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin"
    with pytest.raises(RuntimeError) as caught:
        assert_linked_value(invalid_link, text, invalid_link, text, label="Name")
    assert repr(invalid_link) in str(caught.value)
    assert repr(text) in str(caught.value)

def test_note_fits_cell_refuses_captured_native_name_overflow() -> None:
    from _purchased_title_fit import note_fits_cell

    box = (0.310260575, 0.032472074, 0.409863405, 0.042956582)
    ruled_cell = (0.3083506, 0.035906, 0.4191, 0.0475164)
    inset = 0.0006
    limit = (
        ruled_cell[0] + inset,
        ruled_cell[1] + inset,
        ruled_cell[2] - inset,
        ruled_cell[3] - inset,
    )
    assert not note_fits_cell(box, 2, limit)
    # The captured bottom edge also fails independently of its two-row state.
    assert not note_fits_cell(box, 1, limit)

@pytest.mark.parametrize(
    ("box", "fits"),
    [
        pytest.param((2.0, 3.0, 8.0, 7.0), True, id="interior"),
        pytest.param((1.0, 2.0, 9.0, 8.0), True, id="all-four-boundaries"),
        pytest.param((0.999, 3.0, 8.0, 7.0), False, id="left-overflow"),
        pytest.param((2.0, 1.999, 8.0, 7.0), False, id="bottom-overflow"),
        pytest.param((2.0, 3.0, 9.001, 7.0), False, id="right-overflow"),
        pytest.param((2.0, 3.0, 8.0, 8.001), False, id="top-overflow"),
        pytest.param((0.0, 1.0, 10.0, 9.0), False, id="center-inside-edges-outside"),
    ],
)
def test_note_fits_cell_synthetic_four_edge_predicate_controls(
    box: tuple[float, ...], fits: bool
) -> None:
    from _purchased_title_fit import note_fits_cell

    # Mathematical predicate controls only, never native after-fix proof.
    assert note_fits_cell(box, 1, (1.0, 2.0, 9.0, 8.0)) is fits

@pytest.mark.parametrize("rows", [-1, 0, 1, 2, 3])
def test_note_fits_cell_synthetic_row_count_predicate_controls(rows: int) -> None:
    from _purchased_title_fit import note_fits_cell

    # Mathematical predicate controls only, never native after-fix proof.
    assert note_fits_cell((2.0, 3.0, 8.0, 7.0), rows, (1.0, 2.0, 9.0, 8.0)) is (
        rows == 1
    )
