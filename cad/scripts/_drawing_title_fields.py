"""The title block's identity cells, proven on every finished sheet.

Each sheet prints its linked model's ``Number`` in the DWG. NO. cell and its
``Title`` slug in the PART cell, through the template's own ``$PRPSHEET``
notes. The template authored those notes once; the strings they print change
with every part, so only the finished sheet says whether a value printed
whole, on one line, inside its ruled cell. :func:`read_title_fields` reads
each linked note natively -- its unresolved link (``PropertyLinkedText``),
its resolved text (``GetText``), its sheet-space box (``GetExtent``), its
character height and text format -- beside the linked model's own value for
the property the link names. :func:`assert_title_fields` holds each reading
to the contract:

* the linked property is a full identity (``MHA-XX-###``, cone-gear's
  ``-T###`` configuration suffix included; a ``xx-`` slug whose category
  matches the Number's), and the note prints exactly it: the readback;
* the note's extent lies inside its cell's rules
  (``DrawingTemplateSpec.title_cells_m``) with ``TITLE_FIELD_CLEARANCE_M`` of
  air;
* one line: the extent is less than two character heights tall.

Nothing shortens, hides or shrinks an identity to make it fit: a misfit fails
the drawing, and the fix is the template's cell. The exported PDF proves the
same fit a second way, on the printed glyphs
(``_layout_audit.find_title_field_misfits``), so an extent that stopped
tracking the print cannot pass alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import _telemetry
from _common import _early_bound, _read_member
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
from _layout_audit import TITLE_FIELD_CLEARANCE_M

# The properties each identity cell's note may link, by cell. The PART cell
# prints the summary Title (``SW-Title``) or the custom ``Title``; both carry
# the slug (``_common.part_properties``, ``_common.apply_summary_info``).
TITLE_FIELD_PROPERTIES: Mapping[str, frozenset[str]] = {
    "Number": frozenset({"Number"}),
    "Title": frozenset({"Title", "SW-Title"}),
}
# A note whose whole text is one sheet-property link: $PRPSHEET:"Number",
# $PRPSHEET:{Number} or $PRPSHEET:Number.
_LINK = re.compile(r'\$PRPSHEET:(?:"([^"]+)"|\{([^}]+)\}|(\S+))')
# swAnnotationOwner_e.swAnnotationOwner_DrawingTemplate, swAnnotationType_e.swNote
_OWNER_DRAWING_TEMPLATE = 2
_ANNOT_NOTE = 6
# swSummInfoField_e for the built-in property a "SW-" link names.
_SUMMARY_FIELDS = {"SW-Title": 0}
# swCustomInfoGetResult_e.swCustomInfoGetResult_NotPresent
_NOT_PRESENT = 1
# The identity shapes (the registry's, ``_identity``): a configuration may
# extend its part's Number with a tooth count (``dt_cone_gear_spec``).
_NUMBER = re.compile(r"MHA-([A-Z]{2})-[0-9]{3}(?:-T[0-9]{3})?")
_TITLE = re.compile(r"([a-z]{2})-[a-z0-9]+(?:-[a-z0-9]+)*")
# A wrapped value is at least two lines of its character height tall.
_LINES_TALL = 2.0


@dataclass(frozen=True)
class TitleFieldReading:
    """One identity note on one sheet, as SolidWorks reports it.

    Boxes are ``(left, bottom, right, top)`` in sheet metres; ``extent`` is
    ``INote::GetExtent``, ``cell`` the template cell's rules."""

    sheet: str
    source: str
    link: str
    expected: str
    printed: str
    extent: tuple[float, float, float, float]
    cell: tuple[float, float, float, float]
    char_height: float
    typeface: str
    line_length: float

    @property
    def clearance(self) -> float:
        """The extent's least distance inside the cell's rules (negative
        where it crosses one)."""
        (x0, y0, x1, y1), (cx0, cy0, cx1, cy1) = self.extent, self.cell
        return min(x0 - cx0, cx1 - x1, y0 - cy0, cy1 - y1)

    def problems(self, clearance: float = TITLE_FIELD_CLEARANCE_M) -> list[str]:
        shape = _NUMBER if self.source == "Number" else _TITLE
        found = []
        if shape.fullmatch(self.expected) is None:
            found.append(f"the linked model's {self.source} {self.expected!r} is not a full identity")
        if self.printed != self.expected:
            found.append(f"prints {self.printed!r} where the linked model has {self.expected!r}")
        if self.clearance < clearance:
            found.append(
                f"extent {_mm(self.extent)} is {self.clearance * 1000:.2f} mm inside its cell "
                f"{_mm(self.cell)} (needs {clearance * 1000:.2f} mm)"
            )
        height = self.extent[3] - self.extent[1]
        if not self.char_height > 0.0 or height >= _LINES_TALL * self.char_height:
            found.append(
                f"extent is {height * 1000:.2f} mm tall for {self.char_height * 1000:.2f} mm "
                "characters: not one line"
            )
        return found


def _mm(box: Sequence[float]) -> str:
    x0, y0, x1, y1 = (value * 1000 for value in box)
    return f"[{x0:.2f},{y0:.2f}]..[{x1:.2f},{y1:.2f}]mm"


def _linked_name(link: str) -> str | None:
    match = _LINK.fullmatch(link.strip())
    if match is None:
        return None
    return next(group for group in match.groups() if group is not None)


def linked_property(model: Any, configuration: str, name: str) -> str:
    """The value a ``$PRPSHEET`` link to ``name`` resolves on ``model``: a
    built-in ``SW-`` summary field, else the view configuration's property,
    else the file's (cone-gear stamps each configuration's own Number over
    the file-level one)."""
    if name in _SUMMARY_FIELDS:
        return str(_early_bound(model, "IModelDoc2").SummaryInfo(_SUMMARY_FIELDS[name]) or "")
    extension = _read_member(model, "Extension")
    if extension is None:
        raise RuntimeError(f"linked model has no Extension to read {name!r}")
    for scope in dict.fromkeys((configuration, "")):
        manager = extension.CustomPropertyManager(scope)
        if manager is None:
            raise RuntimeError(f"CustomPropertyManager unavailable for {scope!r}")
        result = _early_bound(manager, "ICustomPropertyManager").Get6(name, False)
        if int(result[0]) != _NOT_PRESENT:
            return str(result[2] or "")
    return ""


def read_title_fields(
    ddoc: Any,
    sources: Mapping[str, tuple[Any, str]],
    layouts: Mapping[str, DrawingLayout],
) -> list[TitleFieldReading]:
    """Every sheet's two identity notes, read without activating a sheet.

    ``sources`` maps each sheet to the model its ``$PRPSHEET`` links resolve
    on and the configuration its property view shows; ``layouts`` to its
    template. ``IDrawingDoc::GetViews`` leads each sheet's row with the sheet
    view, whose ``GetAnnotations`` returns the template's notes (owner 2)
    beside the drawing's. A sheet with no note, or two, linking a cell's
    property raises: the template changed under the contract."""
    readings = []
    seen = []
    for row in ddoc.GetViews() or ():
        entries = list(row or ())
        if not entries:
            continue
        sheet_view = _early_bound(entries[0], "IView")
        sheet = str(sheet_view.GetName2() or "")
        model, configuration = sources[sheet]
        cells = dict(DRAWING_TEMPLATES[layouts[sheet]].title_cells_m)
        found: dict[str, tuple[Any, Any, str, str]] = {}
        for raw in sheet_view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.OwnerType) != _OWNER_DRAWING_TEMPLATE or int(annotation.GetType()) != _ANNOT_NOTE:
                continue
            note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
            link = str(note.PropertyLinkedText or "")
            name = _linked_name(link)
            source = next((cell for cell, names in TITLE_FIELD_PROPERTIES.items() if name in names), None)
            if source is None:
                continue
            if source in found:
                raise RuntimeError(
                    f"sheet {sheet!r}: two template notes link the {source} cell "
                    f"({found[source][2]!r}, {link!r})"
                )
            found[source] = (annotation, note, link, name)
        missing = sorted(set(TITLE_FIELD_PROPERTIES) - set(found))
        if missing:
            raise RuntimeError(f"sheet {sheet!r}: no template note links the {missing} cell(s)")
        for source, (annotation, note, link, name) in sorted(found.items()):
            extent = [float(value) for value in note.GetExtent() or ()]
            if len(extent) < 6:
                raise RuntimeError(f"sheet {sheet!r}: the {source} note answered no extent ({extent!r})")
            text_format = annotation.GetTextFormat(0)
            text_format = _early_bound(text_format, "ITextFormat") if text_format is not None else None
            readings.append(
                TitleFieldReading(
                    sheet=sheet,
                    source=source,
                    link=link,
                    expected=linked_property(model, configuration, name),
                    printed=str(note.GetText() or ""),
                    extent=(extent[0], extent[1], extent[3], extent[4]),
                    cell=cells[source],
                    char_height=float(note.GetHeight() or 0.0),
                    typeface=str(text_format.TypeFaceName or "") if text_format is not None else "",
                    line_length=float(text_format.LineLength or 0.0) if text_format is not None else 0.0,
                )
            )
        seen.append(sheet)
    if sorted(seen) != sorted(sources):
        raise RuntimeError(f"title fields read on sheets {sorted(seen)}, drawing has {sorted(sources)}")
    return readings


def assert_title_fields(readings: Sequence[TitleFieldReading]) -> None:
    """Record every reading, then raise on any breach of the contract."""
    failures = []
    for reading in readings:
        x0, y0, x1, y1 = reading.extent
        _telemetry.event(
            "drawing.title_field",
            sheet=reading.sheet,
            source=reading.source,
            link=reading.link,
            expected=reading.expected,
            printed=reading.printed,
            chars=len(reading.printed),
            extent_left_mm=x0 * 1000,
            extent_bottom_mm=y0 * 1000,
            extent_right_mm=x1 * 1000,
            extent_top_mm=y1 * 1000,
            width_mm=(x1 - x0) * 1000,
            cell_right_mm=reading.cell[2] * 1000,
            clearance_mm=reading.clearance * 1000,
            char_height_mm=reading.char_height * 1000,
            typeface=reading.typeface,
            line_length_mm=reading.line_length * 1000,
        )
        failures += [f"sheet {reading.sheet!r} {reading.source}: {problem}" for problem in reading.problems()]
    by_sheet: dict[str, dict[str, str]] = {}
    for reading in readings:
        by_sheet.setdefault(reading.sheet, {})[reading.source] = reading.expected
    for sheet, values in sorted(by_sheet.items()):
        number = _NUMBER.fullmatch(values.get("Number", ""))
        title = _TITLE.fullmatch(values.get("Title", ""))
        if number is not None and title is not None and number[1].lower() != title[1]:
            failures.append(
                f"sheet {sheet!r}: Number {values['Number']!r} and Title {values['Title']!r} "
                "name different categories"
            )
    if failures:
        raise RuntimeError("title block identity contract:\n" + "\n".join(failures))


def audit_records(readings: Sequence[TitleFieldReading]) -> dict[str, list[dict[str, Any]]]:
    """Per sheet, what the layout audit holds the printed page to."""
    records: dict[str, list[dict[str, Any]]] = {}
    for reading in readings:
        records.setdefault(reading.sheet, []).append(
            {"source": reading.source, "text": reading.expected, "cell": list(reading.cell)}
        )
    return records
