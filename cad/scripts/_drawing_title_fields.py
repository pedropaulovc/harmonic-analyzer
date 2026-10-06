"""The title block's identity cells, proven on every finished sheet.

Each sheet prints its linked model's ``Number`` in the DWG. NO. cell and its
``Title`` slug in the PART cell, through the template's own ``$PRPSHEET``
notes. The template authored those notes once; the strings they print change
with every part, so only the finished sheet says whether a value printed
whole, on one line, inside its ruled cell. :func:`read_title_fields` reads
each linked note natively -- its unresolved link (``PropertyLinkedText``),
its resolved text (``GetText``), whether it prints that text in capitals
(``AllUpperCase``), its sheet-space box (``GetExtent``), how many text
items it and its display data hold, its text format -- beside the
linked model's stored value for the property the link names, and beside the
drawing's own frozen identity (:func:`registry_identity`).

Native ``FONT size=...PTS`` controls may surround the whole source-property
link; they are formatting, not visible identity text. The template's
``SW-Title(Title)`` names the source document's summary Title, not a custom
property with that spelling. Only a complete, single ``$PRPSHEET`` link is
recognized: extra visible text, mixed links and other property scopes do
not identify a source-model title cell.

:func:`assert_title_fields` holds each reading to the contract:

* every sheet documents the drawing's own source (``DrawingSpec.source``);
* that source's frozen identity is authoritative and whole: the Title a
  registry stem of a known category, the Number that category's
  ``MHA-XX-###`` (``_identity_shapes``) -- only dt-cone-gear's extended with
  its view configuration's ``-T###`` -- as ``_common.part_properties``
  stamps a part's, or an assembly's contract Number and stem;
* the linked model's property and the printed text both equal it, case
  included: a note set ``AllUpperCase`` may not print a lowercase Title in
  capitals;
* the note's extent lies inside its cell's rules
  (``DrawingTemplateSpec.title_cells_m``) with ``TITLE_FIELD_CLEARANCE_M`` of
  air;
* one line: the note and its display data each hold exactly one text item,
  the text carries no line break, and no wrap width narrower than the cell
  is set.

Reading the model changes nothing: the stored-value reads loop over no
configuration, and the model's active configuration and dirty flag are
read back unchanged. This code never changes a note's font, height, width
or text to make a value fit: a breach fails the drawing
(:class:`TitleFieldContractError`, its breaches by kind), and the fix is the
template's cell. It pins no typeface, height or width factor of its own; a
template edit that shrinks a note is caught where its print then leaves the
cell or its one line. The exported PDF proves the same fit a second way, on
the printed glyphs in their exact case
(``_layout_audit.find_title_field_misfits``), so a native read that stopped
tracking the print cannot pass alone.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import _telemetry
from _assembly_contract import assembly_contract
from _common import _early_bound, _read_member, part_properties
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout, DrawingSpec
from _identity_shapes import CATEGORIES, NUMBER, STEM
from _layout_audit import TITLE_FIELD_CLEARANCE_M

# The properties each identity cell's note may link, by cell. The PART cell
# prints the summary Title or custom Title; both are stamped from the slug.
# The official Get/Set Column Types example spells the built-in summary
# property SW-Title(Title), as the native template note does.
TITLE_FIELD_PROPERTIES: Mapping[str, frozenset[str]] = {
    "Number": frozenset({"Number"}),
    "Title": frozenset({"Title", "SW-Title", "SW-Title(Title)"}),
}
# A whole source-sheet property link, optionally surrounded by native font
# size controls. Never strip arbitrary tags or markup inside a property name:
# that could turn a literal/mixed note into an apparently valid source link.
_FONT_SIZE = r"<FONT size=[0-9]+(?:\.[0-9]+)?PTS>"
_LINK = re.compile(
    rf"(?:{_FONT_SIZE})*"
    + r'\$PRPSHEET:(?:"([^"<>]+)"|\{([^}<>]+)\}|([^"{}<>\s$]+))'
    + rf"(?:{_FONT_SIZE})*"
)
# swAnnotationOwner_e.swAnnotationOwner_DrawingTemplate, swAnnotationType_e.swNote
_OWNER_DRAWING_TEMPLATE = 2
_ANNOT_NOTE = 6
# Both SDK spellings denote swSummInfoField_e.swSumInfoTitle, not custom props.
_SUMMARY_FIELDS = {"SW-Title": 0, "SW-Title(Title)": 0}
# The one part whose sheets print a per-configuration Number: its build
# stamps ``dt_cone_gear_spec.configuration_number`` (registry Number +
# "-T###") on each configuration named "T###".
_CONFIGURATION_NUMBERED = frozenset({"dt-cone-gear"})
_CONFIGURATION = re.compile(r"T[0-9]{3}")


def _not_identity(source: str, number: str, title: str) -> str | None:
    """Why ``source``'s half of a sheet's ``(number, title)`` is not one
    frozen identity, or None. The Title is a registry stem of a known
    category; the Number is that category's ``MHA-XX-###``, which only
    dt-cone-gear's sheets extend with their configuration's ``-T###``."""
    if source == "Title":
        if STEM.fullmatch(title) is None or title[:2] not in CATEGORIES:
            return f"the registry Title {title!r} is not a registry stem"
        return None
    base = number
    if title in _CONFIGURATION_NUMBERED:
        base, dash, configuration = number.rpartition("-")
        if not dash or _CONFIGURATION.fullmatch(configuration) is None:
            return f"the registry Number {number!r} is not {title}'s Number with its -T### configuration"
    match = NUMBER.fullmatch(base)
    if match is None:
        return f"the registry Number {number!r} is not a full MHA-XX-### identity"
    if match[1].lower() != title[:2]:
        return f"the registry Number {number!r} is not of the Title {title!r}'s category"
    return None


@dataclass(frozen=True)
class TitleSource:
    """What one sheet's identity cells must print: the model its
    ``$PRPSHEET`` links resolve on, the configuration its property view
    shows, and the registry identity."""

    model: Any
    configuration: str
    number: str
    title: str

    def expected(self, source: str) -> str:
        return self.number if source == "Number" else self.title


@dataclass(frozen=True)
class TitleFieldBreach:
    """One breach of the contract: ``kind`` is one of ``foreign-source``,
    ``not-identity``, ``model-mismatch``, ``readback``, ``outside-cell``,
    ``multi-line``, ``wrap-width``, ``model-changed``."""

    sheet: str
    source: str
    kind: str
    detail: str

    def format(self) -> str:
        return f"sheet {self.sheet!r} {self.source} [{self.kind}]: {self.detail}"


class TitleFieldContractError(RuntimeError):
    """The title block identity contract failed; ``breaches`` says how."""

    def __init__(self, breaches: Sequence[TitleFieldBreach]) -> None:
        self.breaches = tuple(breaches)
        super().__init__("title block identity contract:\n" + "\n".join(b.format() for b in self.breaches))


@dataclass(frozen=True)
class TitleFieldReading:
    """One identity note on one sheet, as SolidWorks reports it.

    Boxes are ``(left, bottom, right, top)`` in sheet metres; ``extent`` is
    ``INote::GetExtent``, ``cell`` the template cell's rules. ``identity``
    is the sheet's registry ``(Number, Title)`` and ``expected`` this
    cell's half of it, ``model_value`` the linked model's stored property.
    ``all_upper_case`` is ``INote::AllUpperCase``: the note prints its text
    in capitals. ``text_count`` is ``INote::GetTextCount``,
    ``display_count`` ``IDisplayData::GetTextCount`` (-1 where SolidWorks
    answered no display data)."""

    sheet: str
    source: str
    link: str
    identity: tuple[str, str]
    model_value: str
    printed: str
    all_upper_case: bool
    extent: tuple[float, float, float, float]
    cell: tuple[float, float, float, float]
    char_height: float
    typeface: str
    line_length: float
    text_count: int
    display_count: int

    @property
    def expected(self) -> str:
        number, title = self.identity
        return number if self.source == "Number" else title

    @property
    def shown(self) -> str:
        """The text as the note prints it, capitals included."""
        return self.printed.upper() if self.all_upper_case else self.printed

    @property
    def clearance(self) -> float:
        """The extent's least distance inside the cell's rules (negative
        where it crosses one)."""
        (x0, y0, x1, y1), (cx0, cy0, cx1, cy1) = self.extent, self.cell
        return min(x0 - cx0, cx1 - x1, y0 - cy0, cy1 - y1)

    def problems(self, clearance: float = TITLE_FIELD_CLEARANCE_M) -> list[tuple[str, str]]:
        """``(kind, detail)`` for every breach (see :class:`TitleFieldBreach`)."""
        found = []
        not_identity = _not_identity(self.source, *self.identity)
        if not_identity is not None:
            found.append(("not-identity", not_identity))
        if self.model_value != self.expected:
            found.append(
                ("model-mismatch", f"the linked model holds {self.model_value!r} where the registry has {self.expected!r}")
            )
        if self.shown != self.expected:
            capitals = " (AllUpperCase)" if self.all_upper_case else ""
            found.append(("readback", f"prints {self.shown!r}{capitals} where the registry has {self.expected!r}"))
        if self.clearance < clearance:
            found.append(
                (
                    "outside-cell",
                    f"extent {_mm(self.extent)} is {self.clearance * 1000:.2f} mm inside its cell "
                    f"{_mm(self.cell)} (needs {clearance * 1000:.2f} mm)",
                )
            )
        if self.text_count != 1 or self.display_count != 1 or "\n" in self.printed or "\r" in self.printed:
            found.append(
                (
                    "multi-line",
                    f"the note holds {self.text_count} text item(s), its display data "
                    f"{self.display_count}: not one line",
                )
            )
        width = self.cell[2] - self.cell[0]
        if 0.0 < self.line_length < width:
            found.append(
                (
                    "wrap-width",
                    f"the note wraps at {self.line_length * 1000:.2f} mm, inside its "
                    f"{width * 1000:.2f} mm cell",
                )
            )
        return found


def _mm(box: Sequence[float]) -> str:
    x0, y0, x1, y1 = (value * 1000 for value in box)
    return f"[{x0:.2f},{y0:.2f}]..[{x1:.2f},{y1:.2f}]mm"


def _linked_name(link: str) -> str | None:
    """The exact property descriptor in one complete source-sheet link."""
    match = _LINK.fullmatch(link.strip())
    if match is None:
        return None
    return next(group for group in match.groups() if group is not None)


def _same_file(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def registry_identity(spec: DrawingSpec) -> tuple[str, str]:
    """The frozen ``(Number, Title)`` of ``spec``'s own source -- the only
    identity the contract ever reads: the parts-registry row
    ``dodo._expand_parts_token`` gives a drawing, or its assembly's contract.
    A part's are what its build stamps (``_common.part_properties``); an
    assembly's are its contract's frozen Number
    (``_assembly_contract.assembly_contract``) and its stem, as ``_assembly``
    stamps them."""
    stem = spec.source.stem
    if spec.source_kind == "assembly":
        return assembly_contract(stem).number, stem
    properties = part_properties(stem)
    if "Number" not in properties:
        raise KeyError(f"{stem} has no parts-registry Number")
    return properties["Number"], properties["Title"]


def registry_source(spec: DrawingSpec, identity: tuple[str, str], model: Any, configuration: str) -> TitleSource:
    """What a sheet of ``spec``'s drawing must print, its links resolving on
    ``model`` in ``configuration``: ``identity`` (:func:`registry_identity`),
    dt-cone-gear's Number alone extended with the configuration's ``-T###``."""
    number, title = identity
    if spec.source.stem in _CONFIGURATION_NUMBERED:
        if _CONFIGURATION.fullmatch(configuration) is None:
            raise RuntimeError(f"{spec.name} view shows configuration {configuration!r}, not a T### configuration")
        number = f"{number}-{configuration}"
    return TitleSource(model, configuration, number, title)


def linked_property(model: Any, configuration: str, name: str) -> str:
    """The stored value a ``$PRPSHEET`` link to ``name`` resolves on
    ``model``: either explicit summary-Title descriptor (``SW-Title`` or
    ``SW-Title(Title)``), else the view configuration's property, else the
    file's (cone-gear stamps each configuration's own Number).

    ``GetCustomInfoValue`` reads the stored value of one configuration;
    ``ICustomPropertyManager::Get6`` with ``UseCached=False`` instead loops
    through the model's configurations for one never activated and may
    leave another active."""
    document = _early_bound(model, "IModelDoc2")
    if name in _SUMMARY_FIELDS:
        return str(document.SummaryInfo(_SUMMARY_FIELDS[name]) or "")
    for scope in dict.fromkeys((configuration, "")):
        value = str(document.GetCustomInfoValue(scope, name) or "")
        if value:
            return value
    return ""


def _model_state(model: Any) -> tuple[str, bool]:
    """The model's active configuration and dirty flag."""
    document = _early_bound(model, "IModelDoc2")
    manager = _read_member(document, "ConfigurationManager")
    active = _read_member(manager, "ActiveConfiguration") if manager is not None else None
    name = str(_read_member(active, "Name") or "") if active is not None else ""
    return name, bool(document.GetSaveFlag())


def _display_count(annotation: Any) -> int:
    display = annotation.GetDisplayData()
    if display is None:
        return -1
    return int(_early_bound(display, "IDisplayData").GetTextCount())


def read_title_fields(
    ddoc: Any,
    spec: DrawingSpec,
    sources: Mapping[str, tuple[Any, str]],
    layouts: Mapping[str, DrawingLayout],
) -> list[TitleFieldReading]:
    """Every sheet of ``spec``'s drawing: its two identity notes, held to the
    drawing's own frozen identity.

    ``sources`` maps each sheet to the model its ``$PRPSHEET`` links resolve
    on and the configuration its property view shows; ``layouts`` to its
    template. Every sheet must document the drawing's own source
    (``spec.source``) -- one linked to any other model breaches
    ``foreign-source`` before any identity is read -- so the only identity
    read is the drawing's own (:func:`registry_identity`)."""
    foreign = []
    for sheet, (model, _configuration) in sources.items():
        linked = Path(str(_early_bound(model, "IModelDoc2").GetPathName() or ""))
        if not _same_file(linked, spec.source):
            foreign.append(
                TitleFieldBreach(sheet, "model", "foreign-source", f"links {linked} where {spec.name} documents {spec.source}")
            )
    if foreign:
        raise TitleFieldContractError(foreign)
    identity = registry_identity(spec)
    return _measure_title_fields(
        ddoc,
        {sheet: registry_source(spec, identity, model, configuration) for sheet, (model, configuration) in sources.items()},
        layouts,
    )


def _measure_title_fields(
    ddoc: Any,
    sources: Mapping[str, TitleSource],
    layouts: Mapping[str, DrawingLayout],
) -> list[TitleFieldReading]:
    """The native measurement under :func:`read_title_fields`, read without
    activating a sheet.

    ``IDrawingDoc::GetViews`` leads each sheet's row with the sheet view,
    whose ``GetAnnotations`` returns the template's notes (owner 2) beside
    the drawing's. A sheet with no note, or two, linking a cell's property
    raises: the template changed under the contract. So does a model whose
    active configuration or dirty flag the reads changed."""
    readings = []
    seen = []
    for row in ddoc.GetViews() or ():
        entries = list(row or ())
        if not entries:
            continue
        sheet_view = _early_bound(entries[0], "IView")
        sheet = str(sheet_view.GetName2() or "")
        source_of = sources[sheet]
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
        before = _model_state(source_of.model)
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
                    identity=(source_of.number, source_of.title),
                    model_value=linked_property(source_of.model, source_of.configuration, name),
                    printed=str(note.GetText() or ""),
                    all_upper_case=bool(note.AllUpperCase),
                    extent=(extent[0], extent[1], extent[3], extent[4]),
                    cell=cells[source],
                    char_height=float(note.GetHeight() or 0.0),
                    typeface=str(text_format.TypeFaceName or "") if text_format is not None else "",
                    line_length=float(text_format.LineLength or 0.0) if text_format is not None else 0.0,
                    text_count=int(note.GetTextCount()),
                    display_count=_display_count(annotation),
                )
            )
        after = _model_state(source_of.model)
        if after != before:
            raise TitleFieldContractError(
                [
                    TitleFieldBreach(
                        sheet,
                        "model",
                        "model-changed",
                        f"reading the linked model moved its (configuration, dirty) from {before!r} to {after!r}",
                    )
                ]
            )
        seen.append(sheet)
    if sorted(seen) != sorted(sources):
        raise RuntimeError(f"title fields read on sheets {sorted(seen)}, drawing has {sorted(sources)}")
    return readings


def assert_title_fields(readings: Sequence[TitleFieldReading]) -> None:
    """Record every reading, then raise :class:`TitleFieldContractError` on
    any breach."""
    breaches = []
    for reading in readings:
        x0, y0, x1, y1 = reading.extent
        _telemetry.event(
            "drawing.title_field",
            sheet=reading.sheet,
            source=reading.source,
            link=reading.link,
            expected=reading.expected,
            model_value=reading.model_value,
            printed=reading.printed,
            all_upper_case=reading.all_upper_case,
            chars=len(reading.printed),
            extent_left_mm=x0 * 1000,
            extent_bottom_mm=y0 * 1000,
            extent_right_mm=x1 * 1000,
            extent_top_mm=y1 * 1000,
            width_mm=(x1 - x0) * 1000,
            height_mm=(y1 - y0) * 1000,
            cell_right_mm=reading.cell[2] * 1000,
            clearance_mm=reading.clearance * 1000,
            char_height_mm=reading.char_height * 1000,
            typeface=reading.typeface,
            line_length_mm=reading.line_length * 1000,
            text_count=reading.text_count,
            display_count=reading.display_count,
        )
        breaches += [
            TitleFieldBreach(reading.sheet, reading.source, kind, detail) for kind, detail in reading.problems()
        ]
    if breaches:
        raise TitleFieldContractError(breaches)


def audit_records(readings: Sequence[TitleFieldReading]) -> dict[str, list[dict[str, Any]]]:
    """Per sheet, what the layout audit holds the printed page to."""
    records: dict[str, list[dict[str, Any]]] = {}
    for reading in readings:
        records.setdefault(reading.sheet, []).append(
            {"source": reading.source, "text": reading.expected, "cell": list(reading.cell)}
        )
    return records
