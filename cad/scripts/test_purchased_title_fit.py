"""Offline linked-note behavior, not a claim of native font/export qualification."""
from __future__ import annotations

import copy
import math
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

import _purchased_title_fit as title_fit
from _drawing_notes import property_link
from _drawing_registry import DRAWINGS_BY_NAME


_FAMILIES = (("block", "63"), ("bracket", "62"), ("carriage", "64"),
             ("clamp", "68"), ("lever", "69"), ("rail", "61"))
# Name/number rules are the existing landscape-template measurements. The
# Material cell and font-dependent extents below are synthetic stress geometry;
# only the authorized native run can qualify actual ink and font readbacks.
_CELLS = ((0.3083506, 0.035906, 0.4191, 0.0475164),
          (0.216, 0.035906, 0.3083506, 0.0475164),
          (0.3083506, 0.019969, 0.37231, 0.035906))


class _Note:
    def __init__(self, expression, text, cell, height, width, line_length):
        self.PropertyLinkedText = f'<FONT size=15PTS>{expression}'
        self.text = text
        self.cell = cell
        self.anchor = (cell[0] + 0.0021, cell[3] - 0.005, 0.0)
        self.format = SimpleNamespace(
            CharHeight=height, TypeFaceName="Century Gothic", LineLength=line_length
        )
        self.initial_height = height
        self.width = width
        self.use_doc = True
        self.next = None
        self.forced_rows = None
        self.extra_width = 0.0
        self.accepts = True

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return self.anchor

    def GetTextFormat(self, _index):
        return copy.copy(self.format)

    def SetTextFormat(self, _index, use_doc, text_format):
        if not self.accepts:
            return False
        self.format, self.use_doc = copy.copy(text_format), use_doc
        # The existing fitter permits precisely this native formatting effect.
        self.PropertyLinkedText = title_fit.source_property_expression(self.PropertyLinkedText)
        return True

    def GetUseDocTextFormat(self, _index):
        return self.use_doc

    def GetText(self):
        return self.text

    def GetNext(self):
        return self.next

    def rows(self):
        width = self.width * self.format.CharHeight / self.initial_height
        return self.forced_rows or max(1, math.ceil(width / self.format.LineLength))

    def GetExtent(self):
        width = self.width * self.format.CharHeight / self.initial_height
        x, top, z = self.anchor
        return (x, top - self.rows() * self.format.CharHeight * 1.3, z,
                x + min(width, self.format.LineLength) + self.extra_width, top, z)


def _line(start, end):
    return SimpleNamespace(
        GetType=lambda: 0,
        GetStartPoint2=lambda: SimpleNamespace(X=start[0], Y=start[1]),
        GetEndPoint2=lambda: SimpleNamespace(X=end[0], Y=end[1]),
    )


def _sheet(monkeypatch, family, number):
    spec = DRAWINGS_BY_NAME[f"ch_rocker_arm_tl_vn_oblique_{family}_screw"]
    source_values = (spec.artifact_stem, "Alloy Steel", f"MHA-CH-06-TL-VN-{number}")
    notes = [
        _Note(property_link("SW-Title(Title)"), source_values[0], _CELLS[0],
              0.00396875, 0.114, 0.100),
        _Note(property_link("Material Specification"), source_values[1], _CELLS[1],
              0.003, 0.033, 0.080),
        _Note(property_link("Number"), source_values[2], _CELLS[2],
              0.0047625, 0.064, 0.080),
    ]
    notes[0].next, notes[1].next = notes[1], notes[2]
    segments = []
    for x1, y1, x2, y2 in _CELLS:
        segments.extend((_line((x1, y1), (x2, y1)), _line((x1, y2), (x2, y2)),
                         _line((x1, y1), (x1, y2)), _line((x2, y1), (x2, y2))))
    sheet = SimpleNamespace(GetTemplateSketch=lambda: SimpleNamespace(
        GetSketchSegments=lambda: segments
    ))
    draw = SimpleNamespace(
        GetCurrentSheet=lambda: sheet,
        GetFirstView=lambda: SimpleNamespace(GetFirstNote2=lambda: notes[0]),
        EditRebuild3=lambda: True,
    )
    adapter = SimpleNamespace(currentModel=draw)
    monkeypatch.setattr(title_fit, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(title_fit, "_zoomed_on", lambda *_args: nullcontext())
    monkeypatch.setattr(title_fit, "_number_state", lambda *_args: {"offline": True})
    monkeypatch.setattr(title_fit, "annotation_display", lambda _adapter, note: (
        {"texts": [{"pos": [note.anchor[0], note.anchor[1] - row * 0.005]}
                   for row in range(note.rows())]}, []
    ))
    return adapter, spec, notes, source_values


@pytest.mark.parametrize("family,number", _FAMILIES)
def test_full_linked_values_fit_measured_cells_and_remain_checked(monkeypatch, family, number):
    adapter, spec, notes, values = _sheet(monkeypatch, family, number)
    before = tuple((note.PropertyLinkedText, note.text, note.anchor) for note in notes)
    assert notes[0].rows() == 2
    assert notes[2].GetExtent()[3] > _CELLS[2][2]
    settled = title_fit.fit_purchased_title_block(adapter, spec=spec)
    adapter.currentModel.EditRebuild3()
    settled()
    for note, (link, text, anchor), cell, minimum in zip(
        notes, before, _CELLS, (0.003, 0.002, 0.003), strict=True
    ):
        assert note.text == text
        assert note.anchor == anchor
        assert title_fit.source_property_expression(note.PropertyLinkedText) == (
            title_fit.source_property_expression(link)
        )
        assert note.format.CharHeight >= minimum
        limit = (cell[0] + 0.0006, cell[1] + 0.0006,
                 cell[2] - 0.0006, cell[3] - 0.0006)
        box = title_fit._box(note.GetExtent(), label="offline", kind="note")
        assert title_fit.note_fits_cell(box, note.rows(), limit)
    assert tuple(note.text for note in notes) == values


@pytest.mark.parametrize("family,number", _FAMILIES)
@pytest.mark.parametrize("change", ("name-wrap", "number-rev", "name-link",
                                   "number-value", "name-anchor", "material-value",
                                   "number-format"))
def test_final_rebuild_refuses_title_collisions_or_identity_drift(
    monkeypatch, family, number, change
):
    adapter, spec, notes, _values = _sheet(monkeypatch, family, number)
    settled = title_fit.fit_purchased_title_block(adapter, spec=spec)
    name, material, drawing_number = notes
    if change == "name-wrap":
        name.forced_rows = 2
    elif change == "number-rev":
        drawing_number.extra_width = 0.010
    elif change == "name-link":
        name.PropertyLinkedText = property_link("Title")
    elif change == "number-value":
        drawing_number.text = drawing_number.text[:-1]
    elif change == "name-anchor":
        name.anchor = (name.anchor[0] + 0.001, *name.anchor[1:])
    elif change == "material-value":
        material.text = "Steel"
    else:
        drawing_number.format.CharHeight += 0.0002
    adapter.currentModel.EditRebuild3()
    with pytest.raises(RuntimeError):
        settled()


@pytest.mark.parametrize("field", (0, 2))
def test_fitter_refuses_unreadable_floor_instead_of_shortening_value(monkeypatch, field):
    adapter, spec, notes, values = _sheet(monkeypatch, "bracket", "62")
    notes[field].width = 0.500
    with pytest.raises(RuntimeError):
        title_fit.fit_purchased_title_block(adapter, spec=spec)
    assert tuple(note.text for note in notes) == values


def test_fitter_refuses_native_format_setter_failure(monkeypatch):
    adapter, spec, notes, values = _sheet(monkeypatch, "carriage", "64")
    notes[0].accepts = False
    with pytest.raises(RuntimeError):
        title_fit.fit_purchased_title_block(adapter, spec=spec)
    assert tuple(note.text for note in notes) == values
