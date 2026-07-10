r"""Create the machinist drawing for the platen guide.

The SLDPRT remains authoritative.  This exporter places curated model views and
imports only the named model dimensions needed to manufacture MHA-111; it does
not auto-export the part feature tree onto a sheet.

Run (SolidWorks already open)::

    uv run python cad\scripts\export_part_drawing.py platen-guide
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from _common import CAD_ROOT, check, run_build
from _hole_wizard import BA6
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    add_third_angle_symbol,
    auto_center_marks,
    curate_dimensions,
    dimension_name,
    new_drawing,
    place_view,
    save_drawing,
    set_units_mm,
    setup_sheet,
    view_name,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout

import _telemetry

PART_STEM = "platen-guide"
TASK_STEM = "platen_guide"
SHEET_WIDTH = 0.4318
SHEET_HEIGHT = 0.2794
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
SLDDRW = CAD_ROOT / "out" / "slddrw" / f"{PART_STEM}.SLDDRW"
PDF = CAD_ROOT / "out" / "pdf" / f"{PART_STEM}.pdf"
PNG = CAD_ROOT / "out" / "png" / f"{PART_STEM}_drawing.png"

THROUGH_X = (53.0, 67.0, 233.0, 247.0)
BLIND_X = (30.0, 90.0, 150.0, 210.0, 270.0)
BLIND_HOLE_DEPTH = 3.0
BLIND_THREAD_DEPTH = 2.4


def _custom_properties(model: Any) -> dict[str, str]:
    names = (
        "Number",
        "Revision",
        "Title",
        "Material Specification",
        "Finish",
        "Quantity",
    )
    return {name: str(model.GetCustomInfoValue("", name) or "") for name in names}


def _set_source_sketch_visibility(model: Any, name: str, *, visible: bool) -> None:
    model.ClearSelection2(True)
    selected = model.Extension.SelectByID2(
        name, "SKETCH", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select source sketch {name!r}")
    if visible:
        model.UnblankSketch()
    else:
        model.BlankSketch()
    model.ClearSelection2(True)


def _set_hlr(adapter: Any, view: Any) -> None:
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 2, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-removed drawing view")


def _sheet_line(sm: Any, x0: float, y0: float, x1: float, y1: float) -> None:
    # The Drawing.drwdot sheet sketch retains its original 1:2 transform even
    # after ISheet reports 1:1. Double sketch coordinates to land at true sheet
    # positions; annotation positions are already true sheet coordinates.
    factor = 2.0
    sm.CreateLine(
        x0 * factor, y0 * factor, 0.0, x1 * factor, y1 * factor, 0.0
    )


def _draw_border_and_title_block(
    adapter: Any, title_rows: list[str], *, margin: float = 0.006
) -> None:
    draw = adapter.currentModel
    sm = draw.SketchManager
    width = SHEET_WIDTH
    height = SHEET_HEIGHT
    block_w = 0.145
    row_h = 0.008
    x0 = width - margin - block_w
    y0 = margin
    x1 = width - margin
    y1 = y0 + len(title_rows) * row_h
    for ax, ay, bx, by in (
        (margin, margin, width - margin, margin),
        (width - margin, margin, width - margin, height - margin),
        (width - margin, height - margin, margin, height - margin),
        (margin, height - margin, margin, margin),
        (x0, y0, x1, y0),
        (x1, y0, x1, y1),
        (x1, y1, x0, y1),
        (x0, y1, x0, y0),
    ):
        _sheet_line(sm, ax, ay, bx, by)
    for row in range(1, len(title_rows)):
        y = y0 + row * row_h
        _sheet_line(sm, x0, y, x1, y)
    for index, text in enumerate(title_rows):
        y = y1 - (index + 0.5) * row_h
        add_note(adapter, text, x0 + 0.004, y)
    draw.ClearSelection2(True)
    draw.EditRebuild3()


def _insert_marked_model_dimensions(adapter: Any, view: Any) -> list[Any]:
    """Import only model dimensions explicitly marked in the SLDPRT."""
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
            0,  # entire model
            0x8000,  # dimensions marked for drawing
            False,
            True,   # eliminate duplicates
            True,   # include absorbed/hidden feature dimensions
            False,
        )
    )
    if not result or isinstance(result, str):
        return []
    return list(result)


def _curate_front_dimensions(adapter: Any, annotations: list[Any]) -> list[Any]:
    keep = {
        "Length",
        "Height",
        "T0X",
        "T1X",
        "T2X",
        "T3X",
        "T0Y",
        "B0X",
        "B1X",
        "B2X",
        "B3X",
        "B4X",
    }
    reposition = {
        "Length": (0.190, 0.145),
        "Height": (0.032, 0.185),
        "T0Y": (0.046, 0.207),
        "T0X": (0.071, 0.160),
        "T1X": (0.086, 0.151),
        "T2X": (0.245, 0.151),
        "T3X": (0.260, 0.160),
        "B0X": (0.058, 0.221),
        "B1X": (0.112, 0.230),
        "B2X": (0.190, 0.239),
        "B3X": (0.268, 0.230),
        "B4X": (0.322, 0.221),
    }
    annotations = _delete_unnamed_imports(adapter, annotations)
    names = {dimension_name(adapter, ann) for ann in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=reposition
    )
    present = {dimension_name(adapter, ann) for ann in curated}
    missing = sorted(keep - present)
    if missing:
        raise RuntimeError(
            f"drawing is missing model dimensions: {missing}; available={sorted(present)}"
        )
    curated = curate_dimensions(adapter, curated, reposition=reposition)
    return curated


def _curate_right_dimensions(adapter: Any, annotations: list[Any]) -> None:
    annotations = _delete_unnamed_imports(adapter, annotations)
    names = {dimension_name(adapter, ann) for ann in annotations}
    delete = tuple(sorted(name for name in names if name and name != "Depth"))
    curated = curate_dimensions(
        adapter,
        annotations,
        delete=delete,
        reposition={"Depth": (0.375, 0.151)},
    )
    if "Depth" not in {dimension_name(adapter, ann) for ann in curated}:
        raise RuntimeError("drawing is missing the model-driven 10 mm depth")


def _delete_unnamed_imports(adapter: Any, annotations: list[Any]) -> list[Any]:
    """Remove automatic cosmetic-thread callouts from a marked-dimension import."""
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


def _manufacturing_notes() -> str:
    through = ", ".join(f"{x:g}" for x in THROUGH_X)
    blind = ", ".join(f"{x:g}" for x in BLIND_X)
    return "\n".join(
        (
            "UNLESS OTHERWISE SPECIFIED:",
            "1. DIMENSIONS ARE IN MILLIMETRES. INTERPRET PER ASME Y14.5.",
            "2. TOLERANCES: X +/-0.5; X.X +/-0.25; X.XX +/-0.10; ANGLES +/-0.5 DEG.",
            "3. REMOVE BURRS AND BREAK SHARP EDGES 0.2 MAX.",
            (
                f"4. 6 BA BASIC: MAJOR DIA {BA6.major_diameter_mm:.2f}, "
                f"PITCH {BA6.pitch_mm:.2f}, INCLUDED ANGLE {BA6.angle_deg:.1f} DEG."
            ),
            f"5. THRU TAPS AT X = {through}; BLIND TAPS AT X = {blind}.",
            "6. PLATEN FACE FLAT WITHIN 0.10; SURFACE FINISH Ra 3.2 OR BETTER.",
            "7. OPPOSITE FACE PARALLEL TO PLATEN FACE WITHIN 0.10.",
            "8. APPLY BLACK OXIDE AFTER MACHINING.",
        )
    )


def _assert_sheet(adapter: Any, sheet: Any, *, phase: str) -> None:
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties") or [])
    if len(properties) < 7:
        raise RuntimeError(f"{phase}: incomplete drawing sheet properties {properties!r}")
    if properties[2:4] != [1.0, 1.0]:
        raise RuntimeError(f"{phase}: drawing sheet scale is not 1:1: {properties!r}")
    if abs(properties[5] - SHEET_WIDTH) > 1e-6 or abs(properties[6] - SHEET_HEIGHT) > 1e-6:
        raise RuntimeError(f"{phase}: drawing sheet is not ASME B size: {properties!r}")


async def _reopen_drawing(adapter: Any) -> tuple[Any, Any]:
    model = adapter.currentModel
    title = str(adapter._get_attr_or_call(model, "GetTitle") or "")
    if not title:
        raise RuntimeError("saved drawing has no document title")
    adapter.swApp.CloseDoc(title)
    check("reopen saved platen-guide drawing", await adapter.open_model(str(SLDDRW)))
    reopened = adapter.currentModel
    sheet = adapter._get_attr_or_call(reopened, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("reopened drawing has no current sheet")
    return reopened, sheet


def _render_pdf_png() -> None:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(PDF))
    if len(document) != 1:
        raise RuntimeError(f"drawing PDF has {len(document)} pages, expected 1")
    page = document[0]
    image = page.render(scale=300.0 / 72.0).to_pil()
    page.close()
    document.close()
    if image.size == (5100, 3301):
        image = image.crop((0, 0, 5100, 3300))
    PNG.parent.mkdir(parents=True, exist_ok=True)
    image.save(PNG, dpi=(300, 300))
    if image.size != (5100, 3300):
        raise RuntimeError(
            f"ASME B PNG is {image.size}, expected 5100x3300 at 300 dpi"
        )


def _add_hole_callout(
    adapter: Any,
    view: Any,
    text: str,
    *,
    edge_x: float,
    edge_y: float,
    note_x: float,
    note_y: float,
) -> Any:
    """Attach a leadered group callout to a representative circular hole edge."""
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        "", "EDGE", edge_x, edge_y, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(
            f"failed to select representative hole edge at ({edge_x}, {edge_y})"
        )
    selection = draw.SelectionManager
    edge = selection.GetSelectedObject6(1, -1)
    if edge is None:
        raise RuntimeError("representative hole selection did not return an edge")

    note = draw.InsertNote(text)
    if note is None:
        raise RuntimeError(f"failed to insert hole callout {text!r}")
    note = _sw_type_info.flagged(note, "INote")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"hole callout has no annotation: {text!r}")
    annotation = _sw_type_info.flagged(annotation, "IAnnotation")
    attached = list(annotation.GetAttachedEntities3() or [])
    if not attached:
        annotation.SetAttachedEntities([edge])
        attached = list(annotation.GetAttachedEntities3() or [])
    if not attached:
        raise RuntimeError(f"failed to attach hole callout to its circular edge: {text!r}")
    leader_status = annotation.SetLeader3(
        1,  # swSTRAIGHT
        0,  # swLS_SMART
        True,
        False,
        False,
        False,
    )
    if leader_status != 0:
        raise RuntimeError(
            f"failed to create callout arrow leader: status={leader_status}, text={text!r}"
        )
    if not annotation.SetPosition2(note_x, note_y, 0.0):
        raise RuntimeError(f"failed to position hole callout: {text!r}")
    if annotation.GetLeaderCount() < 1:
        raise RuntimeError(f"hole callout has no arrow leader: {text!r}")
    draw.ClearSelection2(True)
    return note


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen-guide source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    props = _custom_properties(source_model)
    required = ("Number", "Material Specification", "Finish", "Quantity")
    missing = [name for name in required if not props[name]]
    if missing:
        raise RuntimeError(f"source part properties are missing: {missing}")
    _set_source_sketch_visibility(
        source_model, "BlindDrawingLocatorProfile", visible=True
    )

    new_drawing(adapter, width=SHEET_WIDTH, height=SHEET_HEIGHT)
    if not setup_sheet(
        adapter,
        template=13,
        scale=(1.0, 1.0),
        first_angle=False,
        property_view=PART_STEM,
        paper_width=SHEET_WIDTH,
        paper_height=SHEET_HEIGHT,
    ):
        raise RuntimeError("failed to configure ASME B-size drawing sheet")
    set_units_mm(adapter, decimals=2)
    drawing_model = adapter.currentModel
    sheet = adapter._get_attr_or_call(drawing_model, "GetCurrentSheet")
    if sheet is None or not sheet.SetScale(1.0, 1.0, True, False):
        raise RuntimeError("failed to force the B-size sheet to 1:1")
    _assert_sheet(adapter, sheet, phase="initial setup")
    drawing_model.ForceRebuild3(False)
    drawing_model.EditRebuild3()
    drawing_model.CreateLayer2(
        "BORDER", "ASME border and title block", 0, 0, 0, True, True
    )
    drawing_model.SetCurrentLayer("BORDER")
    _draw_border_and_title_block(
        adapter,
        [
            "PLATEN GUIDE",
            f"DWG NO. {props['Number']}  REV {props['Revision'] or '-'}",
            f"MATERIAL: {props['Material Specification']}",
            f"FINISH: {props['Finish']}",
            f"QTY: {props['Quantity']}",
            "SCALE AS SHOWN  THIRD ANGLE",
            "SHEET 1 OF 1",
        ],
    )
    drawing_model.SetCurrentLayer("")
    add_third_angle_symbol(adapter, 0.490, 0.078, size=0.008)

    front = place_view(adapter, str(SOURCE), "*Back", 0.190, 0.190, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", 0.375, 0.190, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", 0.190, 0.055, scale=(1, 3))
    for view in (front, right, iso):
        _set_hlr(adapter, view)

    front_annotations = _insert_marked_model_dimensions(adapter, front)
    _curate_front_dimensions(adapter, front_annotations)
    _set_source_sketch_visibility(
        source_model, "BlindDrawingLocatorProfile", visible=False
    )
    right_annotations = _insert_marked_model_dimensions(adapter, right)
    _curate_right_dimensions(adapter, right_annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    _add_hole_callout(
        adapter,
        front,
        (
            "4X 6 BA THRU\n"
            f"DRILL DIA {BA6.tap_drill_diameter_mm:.2f} THRU\n"
            "TAP FROM REAR; NO CHAMFER ON PLATEN FACE"
        ),
        edge_x=0.287,
        edge_y=0.1911,
        note_x=0.260,
        note_y=0.132,
    )
    _add_hole_callout(
        adapter,
        front,
        (
            f"5X 6 BA x {BLIND_THREAD_DEPTH:g} FULL THREAD\n"
            f"DRILL DIA {BA6.tap_drill_diameter_mm:.2f} x {BLIND_HOLE_DEPTH:g} DEEP\n"
            "ENTER FROM PLATEN FACE"
        ),
        edge_x=0.310,
        edge_y=0.1911,
        note_x=0.322,
        note_y=0.096,
    )

    add_note(adapter, _manufacturing_notes(), 0.014, 0.112)
    add_note(adapter, "PLATEN FACE", 0.176, 0.174)
    add_note(adapter, "RIGHT (SCALE 3:1)", 0.350, 0.163)
    add_note(adapter, "ISOMETRIC (SCALE 1:3, REFERENCE)", 0.135, 0.018)

    drawing_model.ClearSelection2(True)
    drawing_model.EditRebuild3()
    sheet_name = adapter._get_attr_or_call(sheet, "GetName")
    if not sheet_name or not drawing_model.ActivateSheet(sheet_name):
        raise RuntimeError("failed to activate the drawing sheet for export")

    if not sheet.SetScale(1.0, 1.0, False, False):
        raise RuntimeError("failed to set final drawing sheet scale to 1:1")
    _assert_sheet(adapter, sheet, phase="before save")
    artifacts = save_drawing(adapter, str(SLDDRW))
    drawing_model, sheet = await _reopen_drawing(adapter)
    if not sheet.SetScale(1.0, 1.0, False, False):
        raise RuntimeError("failed to persist reopened drawing sheet scale")
    check("save final 1:1 drawing sheet", await adapter.save_file(str(SLDDRW)))
    drawing_model, sheet = await _reopen_drawing(adapter)
    _assert_sheet(adapter, sheet, phase="post-save reopen")
    artifacts.update(save_drawing(adapter, "", pdf_path=str(PDF)))
    _render_pdf_png()
    artifacts["png"] = str(PNG.resolve())
    expected = {"drawing", "pdf", "png"}
    if set(artifacts) != expected:
        raise RuntimeError(f"drawing export incomplete: {artifacts!r}")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
