"""Offline native-cell contracts; never a substitute for settled farm/PDF proof.

Only COM binding is replaced. The actual fitter, ruled-cell extraction, rebuild,
zoom isolation, display-data collector and strict final checks remain active.
The expression/identity predicate cases below are reused from the exact owner
source 91022397a28fbfc307f24bfab0fcfdf2f08dffc1, not its whole jig branch.
"""
from __future__ import annotations

import copy
import math
from types import SimpleNamespace

import pytest

import _drawing_layout_audit as layout
import _purchased_fastener_drawing as purchased
import _purchased_title_fit as title


class _Format:
    """Detached native format: edits do not persist until SetTextFormat succeeds."""

    __slots__ = ("CharHeight", "LineLength", "TypeFaceName")

    def __init__(self, height=0.004, length=0.006, face="Arial"):
        self.CharHeight = height
        self.LineLength = length
        self.TypeFaceName = face


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
        self._format = _Format()
        self.use_doc = True
        self.setter_result = True
        self.ignore_setter = False
        self.formats = []

    def GetPosition(self):
        return self.note.anchor

    def GetTextFormat(self, index):
        assert index == 0
        return copy.copy(self._format)

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
        assert index == 0
        return self.use_doc

    def GetDisplayData(self):
        return _Display(self.note)


class _Note:
    def __init__(self, expression, text, cell, *, material=False):
        self._link = expression
        self._text = text
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

    def GetText(self):
        return self._text

    def GetAnnotation(self):
        return self.annotation

    def GetNext(self):
        return self.next

    def GetExtent(self):
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
        self.sheet = SimpleNamespace(GetTemplateSketch=lambda: SimpleNamespace(
            GetSketchSegments=lambda: tuple(
                segment for note in notes for segment in _rules(note.cell)
            )
        ))
        self.sheet_view = SimpleNamespace(GetFirstNote2=lambda: notes[0] if notes else None)
        self.relink()

    def relink(self):
        for index, note in enumerate(self.notes):
            note.next = self.notes[index + 1] if index + 1 < len(self.notes) else None

    def GetCurrentSheet(self):
        return self.sheet

    def GetFirstView(self):
        return self.sheet_view

    def EditRebuild3(self):
        self.rebuilds += 1
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
