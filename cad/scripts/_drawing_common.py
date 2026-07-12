"""Project drawing framework shared by every manufacturing print.

Raw project-agnostic COM calls remain in ``solidworks_mcp``.  This layer owns
the harmonic-analyzer book policy: ASME B landscape, the checked-in template,
reopen validation, exact PDF/PNG output, and fail-loud multi-leader callouts.
Part-specific views, dimensions, and notes belong in ``draw_<part>.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.etree import ElementTree

import _telemetry
from _common import check
from _drawing_registry import ASME_B_DRWDOT, ASME_B_SLDDRT
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import dispatch_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    curate_dimensions,
    dimension_name,
    new_drawing,
    save_drawing,
    set_units_mm,
    view_name,
)


ASME_B_WIDTH_M = 0.4318
ASME_B_HEIGHT_M = 0.2794
ASME_B_PNG_SIZE = (5100, 3300)
ASME_B_DPI = 300


@dataclass(frozen=True)
class DrawingOutputs:
    slddrw: Path
    pdf: Path
    png: Path


_GTOL_SYMBOLS = {
    "flatness": "GTOL-FLAT",
    "parallelism": "GTOL-PARA",
    "position": "GTOL-POSI",
    "perpendicularity": "GTOL-PERP",
}


def property_link(property_name: str) -> str:
    """Return a source-model property link suitable for a drawing note."""
    if not property_name or '"' in property_name:
        raise ValueError(f"invalid drawing property name: {property_name!r}")
    return f'$PRPSHEET:"{property_name}"'


def _gtol_frame_xml(
    characteristic: str,
    tolerance: str,
    *,
    datums: Sequence[str] = (),
    diameter: bool = False,
) -> str:
    """Build the SOLIDWORKS-2022+ feature-control-frame XML payload."""
    symbol = _GTOL_SYMBOLS.get(characteristic)
    if symbol is None:
        raise ValueError(f"unsupported geometric characteristic: {characteristic!r}")
    if not tolerance:
        raise ValueError("feature-control-frame tolerance cannot be blank")
    if len(datums) > 3 or any(not d or len(d) > 2 for d in datums):
        raise ValueError(f"invalid datum reference sequence: {tuple(datums)!r}")
    root = ElementTree.Element("GtolFrame")
    ElementTree.SubElement(root, "ToleranceSymbol").text = symbol
    range_info = ElementTree.SubElement(root, "ToleranceRangeInfo")
    ElementTree.SubElement(range_info, "PrimaryToleranceValue").text = tolerance
    if diameter:
        ElementTree.SubElement(range_info, "PrimaryRangeSymbol").text = "phi"
    for datum in datums:
        compartment = ElementTree.SubElement(root, "DatumCompartment")
        detail = ElementTree.SubElement(compartment, "DatumDetail")
        ElementTree.SubElement(detail, "DatumLetter").text = datum
    return ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)


def _select_view_entity(
    adapter: Any,
    view: Any,
    entity_type: str,
    xy: tuple[float, float],
    *,
    label: str,
) -> None:
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        "", entity_type, xy[0], xy[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select {label} {entity_type.lower()} at "
            f"sheet ({xy[0]:g}, {xy[1]:g})"
        )


@_telemetry.traced("drawing.datum_feature", label_param="label")
def add_datum_feature(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    symbol_xy: tuple[float, float],
    datum: str,
    label: str,
) -> Any:
    """Attach a native datum-feature symbol to a drawing-view edge."""
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    draw = adapter.currentModel
    tag = draw.InsertDatumTag2()
    if tag is None:
        raise RuntimeError(f"failed to insert datum {datum} ({label})")
    tag = _sw_type_info.flagged(tag, "IDatumTag")
    if not tag.SetLabel(datum):
        raise RuntimeError(f"failed to label datum feature {datum} ({label})")
    annotation = _sw_type_info.flagged(tag.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position datum {datum} ({label})")
    if str(tag.GetLabel()) != datum:
        raise RuntimeError(f"datum feature label did not persist ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return tag


@_telemetry.traced("drawing.feature_control_frame", label_param="label")
def add_feature_control_frame(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    frame_xy: tuple[float, float],
    characteristic: str,
    tolerance: str,
    datums: Sequence[str] = (),
    diameter: bool = False,
    label: str,
) -> Any:
    """Attach a native SOLIDWORKS-2022+ feature-control frame to an edge."""
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    draw = adapter.currentModel
    gtol = draw.InsertGtol()
    if gtol is None:
        raise RuntimeError(f"failed to insert feature-control frame ({label})")
    gtol = _sw_type_info.flagged(gtol, "IGtol")
    frame_count = int(gtol.GetFrameCount() or 0)
    if frame_count == 0:
        if not gtol.AddFrame():
            raise RuntimeError(f"failed to create feature-control frame ({label})")
        frame_count = int(gtol.GetFrameCount() or 0)
    if frame_count < 1:
        raise RuntimeError(f"feature-control frame has no frame ({label})")
    frame = _sw_type_info.flagged(gtol.GetFrame(1), "IGtolFrame")
    xml = _gtol_frame_xml(
        characteristic, tolerance, datums=datums, diameter=diameter
    )
    if not frame.SetSymbolXml(xml):
        raise RuntimeError(f"SOLIDWORKS rejected feature-control frame XML ({label})")
    annotation = _sw_type_info.flagged(gtol.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(frame_xy[0], frame_xy[1], 0.0):
        raise RuntimeError(f"failed to position feature-control frame ({label})")
    applied = str(frame.GetSymbolXml() or "")
    if _GTOL_SYMBOLS[characteristic] not in applied or tolerance not in applied:
        raise RuntimeError(f"feature-control frame did not persist ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return gtol


@_telemetry.traced("drawing.surface_finish", label_param="label")
def add_surface_finish(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    symbol_xy: tuple[float, float],
    roughness_ra: str,
    label: str,
) -> Any:
    """Attach a native machining-required surface-finish symbol to an edge."""
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    draw = adapter.currentModel
    symbol = draw.Extension.InsertSurfaceFinishSymbol3(
        9,  # swSFSymType_e.swSFMachining_Req
        1,  # swLeaderStyle_e.swSTRAIGHT
        symbol_xy[0],
        symbol_xy[1],
        0.0,
        0,  # swSFLaySym_e.swSFNone
        1,  # swArrowStyle_e.swCLOSED_ARROWHEAD
        "",
        "",
        "",
        "",
        roughness_ra,
        "",
        "",
    )
    if symbol is None:
        raise RuntimeError(f"failed to insert Ra {roughness_ra} symbol ({label})")
    annotation = _sw_type_info.flagged(symbol.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position surface-finish symbol ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return symbol


@_telemetry.traced("drawing.linked_note", label_param="property_name")
def add_property_linked_note(
    adapter: Any, property_name: str, x: float, y: float
) -> Any:
    """Place one note whose displayed text resolves from the source SLDPRT."""
    note = add_note(adapter, property_link(property_name), x, y)
    if note is None:
        raise RuntimeError(f"failed to add linked drawing note {property_name!r}")
    return note


def read_required_properties(
    model: Any, names: Sequence[str], *, required: Iterable[str]
) -> dict[str, str]:
    properties = {
        name: str(model.GetCustomInfoValue("", name) or "") for name in names
    }
    missing = [name for name in required if not properties.get(name)]
    if missing:
        raise RuntimeError(f"source part properties are missing: {missing}")
    return properties


def import_cosmetic_threads(adapter: Any, view: Any) -> tuple[int, int]:
    """Import a view's cosmetic threads and count seed plus pattern instances.

    ``IDrawingDoc.InsertModelAnnotations3`` with ``swInsertCThreads`` makes this
    independent of each seat's drawing annotation preferences.
    ``GetCThreadCount`` counts seed objects, while each
    ``ICThread.GetPatternedTransformsCount`` supplies its repeated instances.
    """
    view = _sw_type_info.flagged(view, "IView")
    draw = adapter.currentModel
    name = view_name(adapter, view)
    draw.ActivateView(name)
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select drawing view {name!r}")
    adapter._attempt(
        lambda: draw.InsertModelAnnotations3(
            0,      # swImportModelItemsFromEntireModel
            0x1,    # swInsertCThreads
            False,
            True,
            True,
            False,
        )
    )
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3())
    seed_count = int(adapter._get_attr_or_call(view, "GetCThreadCount") or 0)
    instance_count = 0
    thread = adapter._get_attr_or_call(view, "GetFirstCThread")
    visited = 0
    while thread is not None:
        visited += 1
        if visited > 10_000:
            raise RuntimeError("cosmetic-thread traversal exceeded 10,000 entries")
        thread = _sw_type_info.flagged(thread, "ICThread")
        patterns = int(
            adapter._get_attr_or_call(thread, "GetPatternedTransformsCount") or 0
        )
        instance_count += 1 + patterns
        thread = adapter._get_attr_or_call(thread, "GetNext")
    if visited != seed_count:
        raise RuntimeError(
            f"cosmetic-thread count mismatch: API={seed_count}, traversed={visited}"
        )
    return seed_count, instance_count


def new_project_drawing(
    adapter: Any,
    *,
    property_view: str,
    scale: tuple[float, float] = (1.0, 1.0),
    decimals: int = 2,
) -> tuple[Any, Any]:
    for asset in (ASME_B_DRWDOT, ASME_B_SLDDRT):
        if not asset.is_file() or asset.stat().st_size == 0:
            raise FileNotFoundError(f"project drawing standard is missing: {asset}")

    draw = new_drawing(
        adapter,
        template=str(ASME_B_DRWDOT),
        width=ASME_B_WIDTH_M,
        height=ASME_B_HEIGHT_M,
    )
    sheet = adapter._get_attr_or_call(draw, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("project drawing template has no current sheet")
    sheet_name = adapter._get_attr_or_call(sheet, "GetName")
    if not sheet_name:
        raise RuntimeError("project drawing template has no sheet name")
    configured = draw.SetupSheet6(
        sheet_name,
        2,  # swDwgPaperBsize
        12,  # swDwgTemplateCustom
        float(scale[0]),
        float(scale[1]),
        False,
        str(ASME_B_SLDDRT.resolve()),
        ASME_B_WIDTH_M,
        ASME_B_HEIGHT_M,
        property_view,
        True,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        0,
    )
    if not configured:
        raise RuntimeError("SetupSheet6 rejected the project ASME B sheet format")
    # 2 decimals by default: 3-decimal display (76.000) reads as false precision
    # next to the ±0.25 blanket tolerance. A drawing that genuinely needs finer
    # display (an exact inch conversion like 9.525) can pass decimals=3.
    set_units_mm(adapter, decimals=decimals)
    sheet = adapter._get_attr_or_call(draw, "GetCurrentSheet")
    if sheet is None or not sheet.SetScale(float(scale[0]), float(scale[1]), True, False):
        raise RuntimeError(f"failed to force ASME B sheet to {scale[0]:g}:{scale[1]:g}")
    template_name = str(adapter._get_attr_or_call(sheet, "GetTemplateName") or "")
    if Path(template_name).resolve() != ASME_B_SLDDRT.resolve():
        raise RuntimeError(
            f"sheet format provenance mismatch: {template_name!r} != {ASME_B_SLDDRT}"
        )
    assert_asme_b_sheet(adapter, sheet, phase="initial setup", scale=scale)
    draw.ForceRebuild3(False)
    draw.EditRebuild3()
    return draw, sheet


def set_hidden_lines_removed(adapter: Any, view: Any) -> None:
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 2, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-removed drawing view")


def set_hidden_lines_visible(adapter: Any, view: Any) -> None:
    """Show hidden edges (greyed) in ``view`` — for a view whose job is to
    communicate internal/cross-drilled features."""
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 1, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-visible drawing view")


def assert_asme_b_sheet(
    adapter: Any, sheet: Any, *, phase: str, scale: tuple[float, float] = (1.0, 1.0)
) -> None:
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties") or [])
    if len(properties) < 7:
        raise RuntimeError(f"{phase}: incomplete drawing sheet properties {properties!r}")
    if properties[2:4] != [float(scale[0]), float(scale[1])]:
        raise RuntimeError(
            f"{phase}: drawing sheet scale is not "
            f"{scale[0]:g}:{scale[1]:g}: {properties!r}"
        )
    if (
        abs(properties[5] - ASME_B_WIDTH_M) > 1e-6
        or abs(properties[6] - ASME_B_HEIGHT_M) > 1e-6
    ):
        raise RuntimeError(f"{phase}: drawing sheet is not ASME B size: {properties!r}")


async def reopen_drawing(adapter: Any, path: Path) -> tuple[Any, Any]:
    model = adapter.currentModel
    title = str(adapter._get_attr_or_call(model, "GetTitle") or "")
    if not title:
        raise RuntimeError("saved drawing has no document title")
    adapter.swApp.CloseDoc(title)
    check(f"reopen saved drawing {path.name}", await adapter.open_model(str(path)))
    reopened = adapter.currentModel
    sheet = adapter._get_attr_or_call(reopened, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("reopened drawing has no current sheet")
    return reopened, sheet


def render_pdf_png(pdf: Path, png: Path) -> None:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf))
    if len(document) != 1:
        raise RuntimeError(f"drawing PDF has {len(document)} pages, expected 1")
    page = document[0]
    image = page.render(scale=ASME_B_DPI / 72.0).to_pil()
    page.close()
    document.close()
    if image.size == (ASME_B_PNG_SIZE[0], ASME_B_PNG_SIZE[1] + 1):
        image = image.crop((0, 0, *ASME_B_PNG_SIZE))
    png.parent.mkdir(parents=True, exist_ok=True)
    image.save(png, dpi=(ASME_B_DPI, ASME_B_DPI))
    if image.size != ASME_B_PNG_SIZE:
        raise RuntimeError(
            f"ASME B PNG is {image.size}, expected {ASME_B_PNG_SIZE}"
        )


def sanitize_pdf_metadata(pdf: Path, *, title: str) -> None:
    """Replace seat/user PDF metadata while preserving the vector page."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(pdf)
    if len(reader.pages) != 1:
        raise RuntimeError(f"drawing PDF has {len(reader.pages)} pages, expected 1")
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    metadata = {
        "/Title": title,
        "/Author": "Harmonic Analyzer Project",
        "/Subject": "Hobby-machinist manufacturing drawing",
        "/Keywords": "harmonic analyzer, manufacturing drawing, #4-40 UNC",
        "/Creator": "Harmonic Analyzer SolidWorks drawing pipeline",
        "/Producer": "Harmonic Analyzer Project",
    }
    writer.add_metadata(metadata)
    temporary = pdf.with_suffix(".sanitized.pdf")
    try:
        writer.write(temporary)
        temporary.replace(pdf)
    finally:
        temporary.unlink(missing_ok=True)
    reread = PdfReader(pdf).metadata or {}
    for key, value in metadata.items():
        if reread.get(key) != value:
            raise RuntimeError(f"PDF metadata {key} did not sanitize")


def _select_edge(adapter: Any, x: float, y: float, *, append: bool) -> Any:
    draw = adapter.currentModel
    selected = draw.Extension.SelectByID2(
        "", "EDGE", x, y, 0.0, append, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select hole edge at sheet point ({x}, {y})")
    index = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    edge = draw.SelectionManager.GetSelectedObject6(index, -1)
    if edge is None:
        raise RuntimeError(f"hole-edge selection {index} returned no entity")
    return edge


def add_hole_group_tags(
    adapter: Any,
    view: Any,
    tag: str,
    *,
    edge_points: Sequence[tuple[float, float]],
    note_positions: Sequence[tuple[float, float]],
) -> list[Any]:
    """Put the same short arrowed group tag on every hole in a group.

    ``IAnnotation.SetAttachedEntities`` throws for multiple edges on a note in
    SolidWorks 2026.  One leadered note per hole is both supported and clearer:
    the nearby schedule owns the full specification while every individual hole
    visibly carries its group letter.
    """
    if not edge_points:
        raise ValueError("hole group tags require at least one edge")
    if len(edge_points) != len(note_positions):
        raise ValueError("hole edge and tag-position counts differ")
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    notes: list[Any] = []
    for edge_point, note_position in zip(edge_points, note_positions, strict=True):
        draw.ClearSelection2(True)
        edge = _select_edge(adapter, *edge_point, append=False)
        note = draw.InsertNote(tag)
        if note is None:
            raise RuntimeError(f"failed to insert hole group tag {tag!r}")
        note = _sw_type_info.flagged(note, "INote")
        annotation = note.GetAnnotation()
        if annotation is None:
            raise RuntimeError(f"hole group tag has no annotation: {tag!r}")
        annotation = _sw_type_info.flagged(annotation, "IAnnotation")
        if int(annotation.GetAttachedEntityCount3()) != 1:
            if not annotation.SetAttachedEntities(dispatch_array([edge])):
                raise RuntimeError(f"failed to attach hole group tag {tag!r}")
        leader_status = annotation.SetLeader3(1, 0, True, False, False, False)
        if leader_status != 0:
            raise RuntimeError(
                f"failed to create hole-group tag leader: status={leader_status}"
            )
        if not annotation.SetPosition2(*note_position, 0.0):
            raise RuntimeError(f"failed to position hole group tag {tag!r}")
        draw.EditRebuild3()
        if (
            int(annotation.GetAttachedEntityCount3()) != 1
            or int(annotation.GetLeaderCount()) != 1
        ):
            raise RuntimeError(f"hole group tag {tag!r} lacks one attached arrow")
        notes.append(note)
    draw.ClearSelection2(True)
    return notes


def insert_marked_dimensions(adapter: Any, view: Any) -> list[Any]:
    """Import the source part's marked-for-drawing dimensions into ``view``.

    Parts mark exactly their manufacturing dimensions
    (``_drawing_marks.mark_dimensions_for_drawing``), so the import mask is
    ``swInsertDimensionsMarkedForDrawing`` only.
    """
    draw = adapter.currentModel
    name = view_name(adapter, view)
    draw.ActivateView(name)
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select drawing view {name!r}")
    result = adapter._attempt(
        lambda: draw.InsertModelAnnotations3(
            0,       # swImportModelItemsFromEntireModel
            0x8000,  # swInsertDimensionsMarkedForDrawing
            False,
            True,
            True,
            False,
        )
    )
    if not result or isinstance(result, str):
        return []
    annotations = [
        _sw_type_info.flagged(annotation, "IAnnotation") for annotation in result
    ]
    names = sorted(
        name
        for name in (dimension_name(adapter, annotation) for annotation in annotations)
        if name
    )
    _telemetry.info(
        f"model-item import {name}: annotations={len(annotations)}, "
        f"dimensions={names}"
    )
    return annotations


def delete_unnamed_imports(adapter: Any, annotations: list[Any]) -> list[Any]:
    """Remove automatic cosmetic-thread callouts from model annotation import."""
    draw = adapter.currentModel
    survivors: list[Any] = []
    for annotation in annotations:
        annotation = _sw_type_info.flagged(annotation, "IAnnotation")
        if dimension_name(adapter, annotation):
            survivors.append(annotation)
            continue
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select an automatic model annotation")
        draw.EditDelete()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return survivors


def curate_view_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Import a view's marked model dimensions and keep exactly ``keep``.

    ``keep`` maps each surviving dimension's parametric name to its sheet
    position (meters).  Everything else the import produced is deleted; a
    missing expected dimension fails loud — the print must carry every
    manufacturing dimension the recipe promises.
    """
    annotations = delete_unnamed_imports(
        adapter, insert_marked_dimensions(adapter, view)
    )
    names = {dimension_name(adapter, annotation) for annotation in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=dict(keep)
    )
    present = {dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} view is missing model dimensions: {missing}; "
            f"available={sorted(present)}"
        )
    return curate_dimensions(adapter, curated, reposition=dict(keep))


def set_dimension_callouts(
    adapter: Any, annotations: Iterable[Any], below_text: dict[str, str]
) -> None:
    """Append callout text below named dimensions (e.g. THRU / depth notes).

    A bare Ø does not tell the machinist whether a hole is through or blind;
    ASME hole callouts carry that below the value.  Keyed on the parametric
    dimension name, so a value collision can never stamp the wrong hole.
    """
    remaining = dict(below_text)
    for annotation in annotations:
        annotation = _sw_type_info.flagged(annotation, "IAnnotation")
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.flagged(display, "IDisplayDimension")
        adapter._attempt(
            lambda d=display, s=text: d.SetText(4, s)  # swDimensionTextCalloutBelow
        )
    if remaining:
        raise RuntimeError(
            f"dimension callouts not applied: {sorted(remaining)}"
        )
    adapter.currentModel.EditRebuild3()


def set_dimension_precision(
    adapter: Any, annotations: Iterable[Any], precision: dict[str, int]
) -> None:
    """Override the primary decimal places of specific NAMED dimensions.

    The document default (``set_units_mm``) is 2 decimals, which reads as false
    precision on most dims.  A dimension whose value is an exact conversion the
    notes cite to 3 places — e.g. the crank shaft bore, Ø9.525 = 3/8 in — must
    display 3 so the view matches the note (otherwise 9.53-on-view vs
    9.525-in-note reads as a contradiction).  Keyed on the parametric dimension
    name so a value collision can never repick the wrong dimension.
    """
    # swDimensionPrecisionSettings_e.swDoNotChangePrecisionSetting: leave the
    # dual / tolerance precisions untouched, override only the primary.
    do_not_change = -1
    remaining = dict(precision)
    for annotation in annotations:
        annotation = _sw_type_info.flagged(annotation, "IAnnotation")
        name = dimension_name(adapter, annotation)
        digits = remaining.pop(name, None)
        if digits is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.flagged(display, "IDisplayDimension")
        result = adapter._attempt(
            lambda d=display, n=digits: d.SetPrecision3(
                n, do_not_change, do_not_change, do_not_change
            )
        )
        if result is None:
            raise RuntimeError(f"failed to set precision on dimension {name!r}")
        # SetPrecision3 reports rejection via its RETURN STATUS, not by raising, so a
        # None-only check treats a failure code as success -- and the dim would ship
        # at the 2-decimal sheet default (Ø9.53) against a Ø9.525 note (codex #246).
        # The status enum's success value is undocumented, so verify the SIDE EFFECT:
        # read the primary precision back and confirm it took.
        applied = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if applied != digits:
            raise RuntimeError(
                f"precision override on dimension {name!r} did not take: "
                f"requested {digits} decimals, dimension reports {applied}"
            )
    if remaining:
        raise RuntimeError(
            f"dimension precision not applied: {sorted(remaining)}"
        )
    adapter.currentModel.EditRebuild3()


def add_edge_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Dimension across two edges picked at explicit sheet points (meters).

    The adapter's ``add_overall_dimension`` derives its picks from
    ``IView.GetOutline``, which pads the geometry with a whitespace margin, so
    its coordinate picks can miss.  Recipes know their layout exactly — the
    explicit points make the pick deterministic.  Fails loud on either pick or
    on dimension creation.
    """
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    for index, (x, y) in enumerate((p0, p1)):
        selected = draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, index > 0, 0, null_callout(), 0
        )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} edge {index} at sheet ({x:g}, {y:g})"
            )
    dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} dimension")
    return dimension


def hole_table_template(adapter: Any) -> Path:
    executable = adapter._attempt(
        lambda: adapter.swApp.GetExecutablePath(), default=None
    )
    if not executable:
        raise RuntimeError("SolidWorks executable path is unavailable")
    install_root = Path(str(executable)).parent
    relative = Path("lang") / "english" / "standard hole table--letters.sldholtbt"
    candidates = (install_root / relative, install_root / "SOLIDWORKS" / relative)
    for template in candidates:
        if template.is_file():
            return template
    raise FileNotFoundError(
        "native hole-table template is missing; checked "
        + ", ".join(str(path) for path in candidates)
    )


def insert_hole_table(
    adapter: Any,
    view: Any,
    *,
    datum_xy: tuple[float, float],
    hole_points: Sequence[tuple[float, float]],
    anchor_xy: tuple[float, float],
    label: str,
) -> Any:
    """Insert the model-associated TAG/X LOC/Y LOC/SIZE hole table on ``view``.

    ``datum_xy`` picks the origin VERTEX and each ``hole_points`` entry picks a
    hole EDGE, all in sheet meters.  The table lands with its top-left corner at
    ``anchor_xy`` and is validated (row/column count + header) before returning.
    """
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate hole-table view {name!r}")
    draw.ClearSelection2(True)
    datum = draw.Extension.SelectByID2(
        "", "VERTEX", datum_xy[0], datum_xy[1], 0.0, False, 1, null_callout(), 0
    )
    if not datum:
        raise RuntimeError(f"failed to select {label} hole-table datum vertex")
    for x, y in hole_points:
        selected = draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, True, 2, null_callout(), 0
        )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} hole-table edge at sheet ({x:g}, {y:g})"
            )
    table = view.InsertHoleTable3(
        False,
        anchor_xy[0],
        anchor_xy[1],
        1,  # swBOMConfigurationAnchor_TopLeft
        "A",
        str(hole_table_template(adapter)),
        1,  # swHoleTableTagOrder_XY
        1,  # swHoleTable_AlphaNumericTags
        None,
    )
    draw.ClearSelection2(True)
    if table is None:
        raise RuntimeError(f"SolidWorks failed to create the {label} hole table")
    table = _sw_type_info.flagged(table, "IHoleTableAnnotation")
    feature = table.HoleTable
    if feature is None:
        raise RuntimeError("native hole table annotation has no feature")
    feature = _sw_type_info.flagged(feature, "IHoleTable")
    feature.CombineSameSize = False
    feature.CombineTags = False
    adapter.currentModel.EditRebuild3()
    table = _sw_type_info.flagged(table, "ITableAnnotation")
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    contents = tuple(
        tuple(
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText(row, column)
                )
                or ""
            )
            for column in range(columns)
        )
        for row in range(rows)
    )
    expected_rows = 1 + len(hole_points)
    if (rows, columns) != (expected_rows, 4):
        raise RuntimeError(
            f"native hole table is {rows}x{columns}, "
            f"expected {expected_rows}x4: {contents!r}"
        )
    header = contents[0]
    expected = ("TAG", "X LOC", "Y LOC", "SIZE")
    if tuple(value.upper() for value in header) != expected:
        raise RuntimeError(f"native hole-table header is unexpected: {header!r}")
    _telemetry.success(
        f"native hole table inserted: {rows - 1} holes, header={header}"
    )
    return table


def stamp_drawing_summary(adapter: Any, drawing_model: Any, fields: dict[int, str]) -> None:
    """Write and read-verify the drawing document summary metadata."""
    model_doc = _sw_type_info.flagged(drawing_model, "IModelDoc2")
    for field, value in fields.items():
        model_doc.SummaryInfo(field, value)
        if model_doc.SummaryInfo(field) != value:
            raise RuntimeError(f"drawing summary field {field} did not persist")


async def finalize_drawing(
    adapter: Any,
    outputs: DrawingOutputs,
    *,
    pdf_title: str,
    scale: tuple[float, float] = (1.0, 1.0),
) -> dict[str, str]:
    """Save, reopen-validate, and export the finished drawing (SLDDRW/PDF/PNG).

    The reopen round-trips make the saved artifact prove its own sheet scale
    and format; the PDF is metadata-sanitized and rendered to the exact ASME B
    PNG.  Returns the artifact dict every drawing recipe returns from build().
    """
    drawing_model = adapter.currentModel
    drawing_model.ClearSelection2(True)
    drawing_model.EditRebuild3()
    sheet = adapter._get_attr_or_call(drawing_model, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("finished drawing has no current sheet")
    sheet_name = adapter._get_attr_or_call(sheet, "GetName")
    if not sheet_name or not drawing_model.ActivateSheet(sheet_name):
        raise RuntimeError("failed to activate drawing sheet for export")
    if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
        raise RuntimeError("failed to set final drawing sheet scale")
    assert_asme_b_sheet(adapter, sheet, phase="before save", scale=scale)

    artifacts = save_drawing(adapter, str(outputs.slddrw))
    drawing_model, sheet = await reopen_drawing(adapter, outputs.slddrw)
    if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
        raise RuntimeError("failed to persist reopened drawing sheet scale")
    check(
        "save final drawing sheet scale",
        await adapter.save_file(str(outputs.slddrw)),
    )
    drawing_model, sheet = await reopen_drawing(adapter, outputs.slddrw)
    assert_asme_b_sheet(adapter, sheet, phase="post-save reopen", scale=scale)
    artifacts.update(save_drawing(adapter, "", pdf_path=str(outputs.pdf)))
    sanitize_pdf_metadata(outputs.pdf, title=pdf_title)
    render_pdf_png(outputs.pdf, outputs.png)
    artifacts["png"] = str(outputs.png.resolve())
    if set(artifacts) != {"drawing", "pdf", "png"}:
        raise RuntimeError(f"drawing export incomplete: {artifacts!r}")
    return artifacts


def draw_note_table(
    adapter: Any,
    *,
    rows: Sequence[Sequence[str]],
    column_x: Sequence[float],
    row_y: Sequence[float],
) -> None:
    """Place a compact schedule using aligned notes.

    Geometry stays in the checked-in sheet format.  The drawing recipe supplies
    only row content, so future prints can reuse the same uncluttered schedule
    layout without adding table objects or template-specific anchors.
    """
    if len(rows) != len(row_y):
        raise ValueError("table row content and row positions differ")
    for y, row in zip(row_y, rows, strict=True):
        if len(row) != len(column_x):
            raise ValueError("table row has the wrong number of columns")
        for x, text in zip(column_x, row, strict=True):
            if add_note(adapter, text, x, y) is None:
                raise RuntimeError(f"failed to add schedule cell {text!r}")
