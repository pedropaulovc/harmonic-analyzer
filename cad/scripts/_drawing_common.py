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

from _common import check
from _drawing_registry import ASME_B_DRWDOT, ASME_B_SLDDRT
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import dispatch_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    new_drawing,
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


def new_project_drawing(adapter: Any, *, property_view: str) -> tuple[Any, Any]:
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
        1.0,
        1.0,
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
    set_units_mm(adapter, decimals=3)
    sheet = adapter._get_attr_or_call(draw, "GetCurrentSheet")
    if sheet is None or not sheet.SetScale(1.0, 1.0, True, False):
        raise RuntimeError("failed to force ASME B sheet to 1:1")
    template_name = str(adapter._get_attr_or_call(sheet, "GetTemplateName") or "")
    if Path(template_name).resolve() != ASME_B_SLDDRT.resolve():
        raise RuntimeError(
            f"sheet format provenance mismatch: {template_name!r} != {ASME_B_SLDDRT}"
        )
    assert_asme_b_sheet(adapter, sheet, phase="initial setup")
    draw.ForceRebuild3(False)
    draw.EditRebuild3()
    return draw, sheet


def set_hidden_lines_removed(adapter: Any, view: Any) -> None:
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 2, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-removed drawing view")


def assert_asme_b_sheet(adapter: Any, sheet: Any, *, phase: str) -> None:
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties") or [])
    if len(properties) < 7:
        raise RuntimeError(f"{phase}: incomplete drawing sheet properties {properties!r}")
    if properties[2:4] != [1.0, 1.0]:
        raise RuntimeError(f"{phase}: drawing sheet scale is not 1:1: {properties!r}")
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
