"""Four-view purchased-part reference sheets, linked to the native source part.

Every view is hidden-lines-removed: the sheets carry no dimensions, so a dashed
edge never names a feature (drawing-guidelines rule 9).  Front/Top/Right share
the largest standard scale that fits their cells, which is the sheet scale; the
Isometric takes its own largest fitting scale, printed in its caption.

The footer, bottom-left above the border and left of the title block, reads
top to bottom: the part's own notes (installation, or a spring's acceptance
data), one general line, then ITEM (the catalogue designation in plain text,
passed by each drawing script), SUPPLIER and SKU (linked to the source part).
The title block alone gives material and finish (rule 2), so the supplier's
stock name, which restates the material, is read and checked but not printed.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    iter_views,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
import _config
from _custom_properties import apply_custom_properties
from _drawing_common import (
    TITLE_BLOCK_TOLERANCE_PROPERTIES,
    DrawingOutputs,
    assert_asme_b_sheet,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_notes import add_property_linked_note, property_link
from _drawing_registry import DRAWING_TEMPLATES, DrawingSpec
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed
from _fastener_catalog import fastener
import _telemetry

# Project-used scales, largest first, tried against actual native outlines;
# no catalogue dimension/axis heuristics.
_SCALES = ((8, 1), (5, 1), (4, 1), (2, 1), (1, 1), (1, 2), (1, 4), (1, 8))
_ISOMETRIC = "*Isometric"
_PROPERTIES = (
    "Number",
    "Revision",
    "Title",
    "Material",
    "Stock Name",
    "Supplier",
    "Supplier SKUs",
    *TITLE_BLOCK_TOLERANCE_PROPERTIES,
)

# Footer geometry, ASME B landscape (431.8 x 279.4), sheet metres.  The border
# is 12.7 mm in; the title block fills x >= 215.9 mm below y = 65.1 mm, so every
# footer row stops at _FOOTER_RIGHT.  Note y is the text's top edge; 3 mm text
# advances at most _LINE_PITCH a line.
_NOTE_X = 0.018
_VALUE_X = 0.052
_FOOTER_RIGHT = 0.2155
_LINE_PITCH = 0.0045
_FOOTER_ROWS = (("ITEM:", 0.044), ("SUPPLIER:", 0.034), ("SKU:", 0.024))
_GENERAL_Y = 0.054
# The general line's box bottom; the notes above it end at or over this.
_GENERAL_BOTTOM = _GENERAL_Y - 0.007
_NOTES_BOTTOM = _GENERAL_Y + 0.0015
# Footer notes stay within rule 7's four lines with the general line.
MAX_NOTE_LINES = 3
# One plain-text designation line: _VALUE_X.._FOOTER_RIGHT holds about 68
# characters of 3 mm text at the repo's widest 2.36 mm a character.
MAX_ITEM_CHARS = 64
_GENERAL_TEXT = {
    False: "PURCHASED PART, USED AS SUPPLIED. VIEWS ARE REFERENCE ONLY.",
    True: "PURCHASED PART, CUT AT ASSEMBLY PER NOTE ABOVE. VIEWS ARE REFERENCE ONLY.",
}
# The lowest caption of the bottom view row: clear of the title block's top
# (65.1 mm) and of the footer notes by _CAPTION_CLEARANCE.
_LOWEST_CAPTION_Y = 0.073
_CAPTION_CLEARANCE = 0.011
# A caption's top edge sits this far under its cell; its text hangs below.
_CAPTION_TO_CELL = 0.004
_CAPTION_BELOW = 0.006


def _box(
    values: Any, *, label: str, kind: Literal["view", "note"] = "view"
) -> tuple[float, float, float, float]:
    """Decode documented IView.GetOutline / INote.GetExtent sheet coordinates."""
    coordinates = tuple(float(value) for value in (values or ()))
    expected = 6 if kind == "note" else 4
    if len(coordinates) != expected or not all(map(math.isfinite, coordinates)):
        raise RuntimeError(f"{label}: invalid native extent {coordinates!r}")
    if kind == "note":
        coordinates = (coordinates[0], coordinates[1], coordinates[3], coordinates[4])
    if coordinates[0] >= coordinates[2] or coordinates[1] >= coordinates[3]:
        raise RuntimeError(f"{label}: empty or inverted native extent {coordinates!r}")
    return coordinates


def _inside(box: tuple[float, ...], container: tuple[float, ...]) -> bool:
    return (
        box[0] >= container[0]
        and box[1] >= container[1]
        and box[2] <= container[2]
        and box[3] <= container[3]
    )


def _rebuild(draw: Any, *, phase: str) -> None:
    if not draw.EditRebuild3():
        raise RuntimeError(f"purchased drawing rebuild failed: {phase}")


def note_lines(notes: str, *, label: str) -> tuple[str, ...]:
    """The footer note's lines, held to rule 7's budget beside the general line."""
    lines = tuple(line for line in notes.strip().splitlines() if line.strip())
    if len(lines) > MAX_NOTE_LINES:
        raise ValueError(
            f"{label}: purchased-sheet notes run {len(lines)} lines; "
            f"at most {MAX_NOTE_LINES} fit beside the general line (rule 7)"
        )
    return lines


def check_item(item: str, *, label: str) -> str:
    """One plain-text catalogue designation line that fits the ITEM row."""
    text = item.strip()
    if not text or "\n" in text or len(text) > MAX_ITEM_CHARS:
        raise ValueError(
            f"{label}: ITEM must be one line of 1-{MAX_ITEM_CHARS} characters: {item!r}"
        )
    return text


def footer_top(notes: str, *, label: str) -> float:
    """The footer's top edge: its notes' first line, or the general line."""
    lines = note_lines(notes, label=label)
    if not lines:
        return _GENERAL_Y
    return _NOTES_BOTTOM + len(lines) * _LINE_PITCH + 0.001


def view_band_bottom(notes: str, *, label: str) -> float:
    """The bottom view row's caption height: clear of the footer and title block."""
    return max(footer_top(notes, label=label) + _CAPTION_CLEARANCE, _LOWEST_CAPTION_Y)


def _cell(
    name: str, x0: float, y0: float, x1: float, y1: float
) -> tuple[str, tuple[float, float], tuple[float, float, float, float]]:
    return (name, ((x0 + x1) / 2, (y0 + y1) / 2), (x0, y0, x1, y1))


def fastener_view_cells(caption_y: float) -> tuple:
    """Third-angle Front/Top/Right with the Isometric upper right.

    Front and Right fill the band from their captions (``caption_y``) up to the
    Top/Isometric captions; Top and Isometric fill the band under the border.
    The Isometric's cell reaches 6 mm lower, its caption ending on the Right
    cell's top, so a 1:1 pictorial of a long part (the 67 mm keeper chain)
    is not shrunk to 1:2, where small round features show their facets.
    """
    bottom = caption_y + _CAPTION_TO_CELL
    return (
        _cell("*Front", 0.025, bottom, 0.205, 0.182),
        _cell("*Top", 0.025, 0.198, 0.205, 0.262),
        _cell("*Right", 0.225, bottom, 0.405, 0.182),
        _cell(_ISOMETRIC, 0.225, 0.192, 0.415, 0.262),
    )


def spring_view_cells(caption_y: float) -> tuple:
    """Long coils: wide Front/Top, a narrow end view and a tall Isometric column."""
    bottom = caption_y + _CAPTION_TO_CELL
    return (
        _cell("*Front", 0.015, bottom, 0.207, 0.150),
        _cell("*Top", 0.015, 0.168, 0.207, 0.262),
        _cell("*Right", 0.212, bottom, 0.262, 0.150),
        _cell(_ISOMETRIC, 0.270, bottom, 0.418, 0.262),
    )


def _fit_group(draw: Any, members: list[tuple[Any, tuple]]) -> tuple[int, int]:
    """The largest standard scale at which every member's outline fits its cell.

    Native outlines include fixed sheet-space padding, so scaling a 1:1 outline
    can reject a larger view that actually fits; measure each standard scale.
    """
    for scale in _SCALES:
        with _telemetry.span(
            "drawing.purchased_scale_candidate", scale=f"{scale[0]}:{scale[1]}"
        ):
            for view, _ in members:
                view.UseSheetScale = 0
                view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
            _rebuild(draw, phase="apply view scale")
            bounds = [
                _box(view.GetOutline(), label=name) for view, (name, _, _) in members
            ]
            if any(
                box[2] - box[0] > cell[2] - cell[0]
                or box[3] - box[1] > cell[3] - cell[1]
                for box, (_, (_, _, cell)) in zip(bounds, members, strict=True)
            ):
                continue
            for (view, (name, center, _)), box in zip(members, bounds, strict=True):
                position = tuple(float(value) for value in view.Position)
                if len(position) != 2 or not all(map(math.isfinite, position)):
                    raise RuntimeError(
                        f"{name}: invalid native view position {position!r}"
                    )
                # Center the actual outline, not a presumed model-origin/axis.
                target = [
                    position[0] + center[0] - (box[0] + box[2]) / 2,
                    position[1] + center[1] - (box[1] + box[3]) / 2,
                ]
                if not view.SetViewPosition(double_array(target), False):
                    raise RuntimeError(f"{name}: failed to position purchased view")
            _rebuild(draw, phase="center purchased views")
            fits = True
            for view, (name, center, cell) in members:
                ratio = tuple(float(value) for value in view.ScaleRatio)
                if (
                    ratio != tuple(float(value) for value in scale)
                    or view.UseSheetScale != 0
                ):
                    raise RuntimeError(
                        f"{name}: independent view scale did not persist: {ratio!r}"
                    )
                box = _box(view.GetOutline(), label=name)
                if (
                    abs((box[0] + box[2]) / 2 - center[0]) > 1e-6
                    or abs((box[1] + box[3]) / 2 - center[1]) > 1e-6
                ):
                    raise RuntimeError(f"{name}: native view failed to center: {box!r}")
                fits = fits and _inside(box, cell)
            if fits:
                return scale
    names = ", ".join(name for _, (name, _, _) in members)
    raise RuntimeError(f"purchased part has no project-standard scale fitting {names}")


@_telemetry.traced("drawing.purchased_fit_views")
def _fit_views(draw: Any, views: list[Any], cells: tuple) -> dict[str, tuple[int, int]]:
    """Per-view scales: one shared by the orthographic views, one for the Isometric."""
    _rebuild(draw, phase="initial view extents")
    for view, (name, _, _) in zip(views, cells, strict=True):
        ratio = tuple(float(value) for value in view.ScaleRatio)
        if len(ratio) != 2 or ratio != (1.0, 1.0):
            raise RuntimeError(
                f"{name}: initial 1:1 view scale did not persist: {ratio!r}"
            )
        _box(view.GetOutline(), label=name)
    members = list(zip(views, cells, strict=True))
    scales: dict[str, tuple[int, int]] = {}
    for group in (
        [member for member in members if member[1][0] != _ISOMETRIC],
        [member for member in members if member[1][0] == _ISOMETRIC],
    ):
        if not group:
            continue
        scale = _fit_group(draw, group)
        scales.update({cell[0]: scale for _, cell in group})
    return scales


@_telemetry.traced("drawing.purchased_center_marks")
def _center_marks_without_lines(views: list[Any], cells: tuple) -> dict[str, int]:
    """Drop the extension lines of every template-inserted centre mark.

    The template auto-inserts a centre mark on each view of a circle, its arms
    scaled with the view (8:1 washers: arms ~11 mm past the rim, outside the
    view outline the cells fit). Captions sit on the view's vertical axis, so
    those arms struck the FRONT caption and the TOP caption above it (r3
    review, rule 14). The centre cross stays; the reference views need no
    more. Even the cross is scaled (8:1 pins: ~20 mm arms), so the count of
    marks per view tells the caption pass which views to leave at the cell
    floor.
    """
    counts: dict[str, int] = {}
    for view, (name, _, _) in zip(views, cells, strict=True):
        counts[name] = 0
        mark = view.GetFirstCenterMark2()
        while mark is not None:
            mark = _early_bound(mark, "ICenterMark")
            mark.UseDocDisplaySettings = False
            mark.ShowLines = False
            if mark.UseDocDisplaySettings or mark.ShowLines:
                raise RuntimeError(
                    f"{name}: centre mark still shows its extension lines"
                )
            counts[name] += 1
            mark = mark.GetNext()
    return counts


@_telemetry.traced("drawing.purchased_note")
def _literal_note(adapter: Any, text: str, x: float, y: float) -> Any:
    note = add_note(adapter, text, x, y)
    if note is None:
        raise RuntimeError(f"failed to insert purchased drawing note {text!r}")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"purchased drawing note has no text format: {text!r}")
    text_format.CharHeight = 0.003
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size purchased drawing note {text!r}")
    if not annotation.SetPosition(x, y, 0.0):
        raise RuntimeError(f"failed to position purchased drawing note {text!r}")
    return note


@_telemetry.traced("drawing.purchased_title_block")
def _purchased_title_block(
    adapter: Any,
    draw: Any,
    *,
    material: str,
    finish: str,
    material_property: str = "Material",
) -> list[tuple[Any, str, str]]:
    """Retarget this drawing's material/finish cells, never the saved template."""
    apply_custom_properties(adapter, {"Finish": finish}, model=draw)
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet_view = ddoc.GetFirstView()
    if sheet_view is None:
        raise RuntimeError("purchased drawing template has no sheet view")
    sheet_view = _early_bound(sheet_view, "IView")
    replacements = {
        property_link("Material"): (property_link(material_property), material),
        property_link("Finish"): ('$PRP:"Finish"', finish),
    }
    matched = {token: 0 for token in replacements}
    notes = []
    for annotation in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(annotation, "IAnnotation")
        if annotation.GetType() != 6:  # swAnnotationType_e.swNote
            continue
        specific = annotation.GetSpecificAnnotation()
        if specific is None:
            raise RuntimeError("purchased title-block note has no INote")
        note = _early_bound(specific, "INote")
        raw = str(note.PropertyLinkedText)
        linked_text = raw
        resolved_text = raw
        for token, (replacement, value) in replacements.items():
            occurrences = raw.count(token)
            if occurrences:
                matched[token] += occurrences
                linked_text = linked_text.replace(token, replacement)
                resolved_text = resolved_text.replace(token, value)
        if resolved_text == raw:
            continue
        # Preserve the existing note, annotation formatting and all surrounding
        # label text; only these exact property-link tokens change ownership.
        if linked_text != raw:
            note.PropertyLinkedText = linked_text
        if note.PropertyLinkedText != linked_text:
            raise RuntimeError(f"purchased title-block link did not persist: {raw!r}")
        notes.append((note, linked_text, resolved_text))
    if any(count != 1 for count in matched.values()):
        raise RuntimeError(
            "purchased template must contain exactly one Material "
            f"and one Finish property link: {matched!r}"
        )
    return notes


@_telemetry.traced("drawing.purchased_footer")
def add_purchased_footer(
    adapter: Any,
    draw: Any,
    properties: dict[str, str],
    *,
    item: str,
    notes: str = "",
    cut_to_suit: bool = False,
    label: str,
) -> list[tuple[Any, str, str, tuple[float, float, float, float]]]:
    """Notes, general line, ITEM, SUPPLIER and SKU rows, bottom-left of the sheet.

    Returns (note, linked text, resolved text, reserved box) for the native
    readback.  ``cut_to_suit`` says the part is cut at assembly (its note says
    where); otherwise the general line says it is used as supplied.
    """
    item = check_item(item, label=label)
    lines = note_lines(notes, label=label)
    placed = []
    if lines:
        # The part's own requirements are drawing-local, like purchased
        # Finish: never forced into title-block cells.
        text = "\n".join(lines)
        apply_custom_properties(adapter, {"Installation Notes": text}, model=draw)
        # $PRP (this drawing), not $PRPSHEET (the model in view).
        link = '$PRP:"Installation Notes"'
        top = footer_top(text, label=label)
        note = _literal_note(adapter, link, _NOTE_X, top)
        placed.append(
            (
                note,
                link,
                text,
                (0.015, _NOTES_BOTTOM - 0.001, _FOOTER_RIGHT, top + 0.001),
            )
        )
    general = _GENERAL_TEXT[cut_to_suit]
    note = _literal_note(adapter, general, _NOTE_X, _GENERAL_Y)
    placed.append(
        (
            note,
            general,
            general,
            (0.015, _GENERAL_BOTTOM, _FOOTER_RIGHT, _GENERAL_Y + 0.001),
        )
    )
    for row, y in _FOOTER_ROWS:
        row_note = _literal_note(adapter, row, _NOTE_X, y)
        placed.append(
            (row_note, row, row, (0.015, y - 0.007, _VALUE_X - 0.002, y + 0.001))
        )
        box = (_VALUE_X - 0.002, y - 0.007, _FOOTER_RIGHT, y + 0.001)
        if row == "ITEM:":
            value = _literal_note(adapter, item, _VALUE_X, y)
            placed.append((value, item, item, box))
            continue
        name = "Supplier" if row == "SUPPLIER:" else "Supplier SKUs"
        value = add_property_linked_note(adapter, name, _VALUE_X, y, char_height=0.003)
        placed.append(
            (_early_bound(value, "INote"), property_link(name), properties[name], box)
        )
    return placed


async def build_purchased_fastener_drawing(
    adapter: Any, spec: DrawingSpec, *, item: str, cut_to_suit: bool = False
) -> dict[str, str]:
    """Export Front/Top/Right plus Isometric without fabrication dimensions or PMI.

    ``item`` is the catalogue designation printed on the ITEM row, e.g.
    ``#4-40 x 1/4 SOCKET SET SCREW, CUP POINT``.  ``cut_to_suit`` marks a
    fastener its registry installation note cuts at assembly.
    """
    stock = fastener(spec.artifact_stem)
    source = spec.source

    if spec.source_kind != "part" or source.stem != stock.part_name:
        raise ValueError(f"purchased drawing source identity mismatch: {spec!r}")
    if not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")

    with _telemetry.span("drawing.purchased_source", part=stock.part_name):
        check(f"open {stock.part_name} source", await adapter.open_model(str(source)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        if Path(model.GetPathName()).resolve() != source.resolve():
            raise RuntimeError(f"opened purchased part is not {source}")
        properties = read_required_properties(model, _PROPERTIES, required=_PROPERTIES)
        registry = _config.parts(stock.part_name)
        finish = registry["finish"]
        if not isinstance(finish, str) or not finish.strip():
            raise RuntimeError(
                f"{stock.part_name}: registered purchased finish is empty"
            )
        expected = {
            "Number": str(registry["number"]),
            # The PART cell prints the slug (_part_properties.part_properties).
            "Title": stock.part_name,
            "Material": str(registry["material"]),
            "Stock Name": stock.stock_name,
            "Supplier": stock.supplier,
            "Supplier SKUs": ", ".join(stock.skus),
        }
        for name, value in expected.items():
            if properties[name] != value:
                raise RuntimeError(
                    f"{stock.part_name}: stale source {name} {properties[name]!r} != {value!r}"
                )

    return await _build_reference_sheet(
        adapter,
        spec,
        properties=properties,
        finish=finish,
        item=item,
        notes=str(registry.get("installation_notes", "")),
        cut_to_suit=cut_to_suit,
        document_title=str(registry["title"]),
    )


async def build_purchased_spring_drawing(
    adapter: Any, spec: DrawingSpec, *, item: str
) -> dict[str, str]:
    """Use spring metadata without treating the part as a catalogued fastener.

    The part's Manufacturing Notes print as the footer notes; the Front view
    shows the coil at its installed length.
    """
    source = spec.source
    if spec.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(f"source purchased spring is missing: {source}")
    check(f"open {spec.artifact_stem} source", await adapter.open_model(str(source)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if Path(model.GetPathName()).resolve() != source.resolve():
        raise RuntimeError(f"opened purchased spring is not {source}")
    names = (*_PROPERTIES, "Material Specification", "Finish", "Manufacturing Notes")
    properties = read_required_properties(model, names, required=names)
    return await _build_reference_sheet(
        adapter,
        spec,
        properties=properties,
        finish=properties["Finish"],
        item=item,
        material_property="Material Specification",
        notes=properties["Manufacturing Notes"],
        spring=True,
    )


async def _build_reference_sheet(
    adapter: Any,
    spec: DrawingSpec,
    *,
    properties: dict[str, str],
    finish: str,
    item: str,
    material_property: str = "Material",
    notes: str = "",
    cut_to_suit: bool = False,
    document_title: str | None = None,
    spring: bool = False,
) -> dict[str, str]:
    source = spec.source
    template = DRAWING_TEMPLATES[spec.layout]
    label = spec.artifact_stem
    # Validate the footer text before any native work.
    check_item(item, label=label)
    caption_y = view_band_bottom(notes, label=label)
    cells = (spring_view_cells if spring else fastener_view_cells)(caption_y)
    draw, sheet = new_project_drawing(adapter, layout=spec.layout)
    title_block_notes = _purchased_title_block(
        adapter,
        draw,
        material=properties[material_property],
        finish=finish,
        material_property=material_property,
    )
    # The registry title still names the drawing document and PDF; only the
    # sheet's PART cell moved to the slug.
    title = (
        f"{document_title or properties['Title']} — Purchased Part Reference Drawing"
    )
    with _telemetry.span("drawing.purchased_summary"):
        stamp_drawing_summary(
            adapter,
            draw,
            {
                0: title,
                1: "Harmonic Analyzer purchased-part identification; reference only",
                2: "Harmonic Analyzer Project",
                3: f"{spec.artifact_stem}; {properties['Supplier']}; {properties['Supplier SKUs']}",
                4: "Front, Top, Right and Isometric; no fabrication dimensions or PMI",
            },
        )

    views = []
    with _telemetry.span("drawing.purchased_create_views"):
        for name, center, _ in cells:
            view = _early_bound(
                place_view(adapter, str(source), name, *center, scale=(1, 1)), "IView"
            )
            set_hidden_lines_removed(adapter, view)
            views.append(view)
        # Later insertions may auto-adjust the sheet scale. Pin all views only
        # after insertion so the measurement pass is genuinely at native 1:1.
        for view in views:
            view.UseSheetScale = 0
            view.ScaleRatio = double_array([1.0, 1.0])
    scales = _fit_views(draw, views, cells)
    center_marks = _center_marks_without_lines(views, cells)
    scale = scales["*Front"]

    with _telemetry.span("drawing.purchased_property_link"):
        values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
        if len(values) != 8:
            raise RuntimeError(
                f"purchased drawing has incomplete sheet properties: {values!r}"
            )
        # Preserve template dimensions/format while explicitly selecting third
        # angle and the first view's source for every title-block property link.
        sheet.SetProperties2(
            int(values[0]),
            int(values[1]),
            float(scale[0]),
            float(scale[1]),
            False,
            float(values[5]),
            float(values[6]),
            False,
        )
        first_name = view_name(adapter, views[0])
        if not first_name:
            raise RuntimeError("purchased front view has no native name")
        sheet.CustomPropertyView = first_name
        values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
        if (
            len(values) != 8
            or bool(values[4])
            or bool(values[7])
            or sheet.CustomPropertyView != first_name
        ):
            raise RuntimeError(
                "purchased drawing third-angle/property-source settings did not persist"
            )
        assert_asme_b_sheet(
            adapter,
            sheet,
            layout=spec.layout,
            phase="purchased layout",
            scale=scale,
        )

    placed = []
    with _telemetry.span("drawing.purchased_annotations"):
        for view, (name, center, cell) in zip(views, cells, strict=True):
            view_scale = scales[name]
            caption = f"{name[1:].upper()}  {view_scale[0]}:{view_scale[1]}"
            if spring and name == "*Front":
                caption += "  (SHOWN AT INSTALLED LENGTH)"
            # Under the view itself, not the cell's floor: a short view in a
            # tall cell (the counter spring's TOP) left its caption stranded
            # mid-field (r4 review, rule 15). The fit keeps outlines in cells,
            # so this only ever lifts a caption toward its own view. A view
            # with a centre mark keeps the cell floor: the mark's scaled cross
            # reaches past the outline and struck lifted captions (r5, 8:1
            # pins, rule 14).
            floor = cell[1]
            if not center_marks[name]:
                floor = max(_box(view.GetOutline(), label=name)[1], floor)
            caption_at = floor - _CAPTION_TO_CELL
            note = _literal_note(adapter, caption, center[0], caption_at)
            bounds = _box(note.GetExtent(), label=caption, kind="note")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            x = 2 * center[0] - (bounds[0] + bounds[2]) / 2
            if not annotation.SetPosition(x, caption_at, 0.0):
                raise RuntimeError(f"{caption}: failed to center view caption")
            placed.append(
                (
                    note,
                    caption,
                    caption,
                    (cell[0], caption_at - _CAPTION_BELOW, cell[2], caption_at + 0.001),
                )
            )
        placed.extend(
            add_purchased_footer(
                adapter,
                draw,
                properties,
                item=item,
                notes=notes,
                cut_to_suit=cut_to_suit,
                label=label,
            )
        )
    with _telemetry.span("drawing.purchased_native_contract"):
        _rebuild(draw, phase="linked notes and final layout")
        for note, linked_text, resolved_text in title_block_notes:
            if (
                note.PropertyLinkedText != linked_text
                or note.GetText() != resolved_text
            ):
                raise RuntimeError(
                    "purchased title-block property did not resolve from its "
                    f"expected source: {linked_text!r}"
                )
        actual = list(iter_views(adapter))
        orientations = tuple(view.GetOrientationName() for view in actual)
        if len(actual) != 4 or set(orientations) != {name for name, _, _ in cells}:
            raise RuntimeError(
                f"purchased drawing must have exactly four native views: {orientations!r}"
            )
        views_by_orientation = dict(zip(orientations, actual, strict=True))
        region = sheet_drawable_region(
            adapter,
            sheet,
            width=template.width_m,
            height=template.height_m,
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        for name, _, cell in cells:
            view = views_by_orientation[name]
            if Path(view.GetReferencedModelName()).resolve() != source.resolve():
                raise RuntimeError(f"{name}: purchased view references the wrong model")
            if tuple(view.ScaleRatio) != scales[name]:
                raise RuntimeError(f"{name}: final purchased view scale changed")
            box = _box(view.GetOutline(), label=name)
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"{name}: purchased view leaves its cell/border: {box!r}"
                )
        for note, linked_text, resolved_text, cell in placed:
            actual_link = note.PropertyLinkedText
            actual_text = note.GetText()
            # INote.GetText uses CRLF; PropertyLinkedText preserves authored LF.
            if (
                actual_link != linked_text
                or actual_text.replace("\r\n", "\n") != resolved_text
            ):
                raise RuntimeError(
                    f"purchased note readback mismatch: expected link={linked_text!r}, "
                    f"actual link={actual_link!r}, expected text={resolved_text!r}, "
                    f"actual text={actual_text!r}"
                )
            box = _box(note.GetExtent(), label=linked_text, kind="note")
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"purchased note leaves its reserved space/border: {linked_text!r}: {box!r}"
                )

    paths = spec.outputs
    return await finalize_drawing(
        adapter,
        DrawingOutputs(slddrw=paths["slddrw"], pdf=paths["pdf"], png=paths["png"]),
        layout=spec.layout,
        pdf_title=title,
        scale=scale,
    )
