r"""Create the curated machinist drawing for the platen guide.

The SLDPRT remains authoritative.  This recipe supplies only the platen-guide
views, dimensions, hole groups, and manufacturing notes; shared sheet/template,
leader, reopen, and artifact behavior lives in ``_drawing_common``.

Run with SolidWorks open::

    uv run python cad\scripts\draw_platen_guide.py platen-guide
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_hole_group_tags,
    assert_asme_b_sheet,
    draw_note_table,
    import_cosmetic_threads,
    new_project_drawing,
    read_required_properties,
    render_pdf_png,
    reopen_drawing,
    sanitize_pdf_metadata,
    set_hidden_lines_removed,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_wizard import BA6
from build_platen_guide import HOLE_X as THROUGH_X
from build_platen_guide import SCREW_HOLE_DEPTH as BLIND_HOLE_DEPTH
from build_platen_guide import SCREW_STATION_X as BLIND_X
from build_platen_guide import SCREW_THREAD_DEPTH as BLIND_THREAD_DEPTH
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    curate_dimensions,
    dimension_name,
    place_view,
    remove_notes_matching,
    save_drawing,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["platen_guide"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# The 1:1 front view is 300 mm long and centred at sheet X=0.190 m, so its
# left end is X=0.040 m.  The circular-edge pick Y was measured and then
# read-validated against every expected attached entity in live SolidWorks.
FRONT_LEFT_X_M = 0.040
FRONT_HOLE_Y_M = 0.1911


def _insert_marked_model_dimensions(adapter: Any, view: Any) -> list[Any]:
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
            0,
            0x8000,
            False,
            True,
            True,
            False,
        )
    )
    if not result or isinstance(result, str):
        return []
    annotations = list(result)
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


def _delete_unnamed_imports(adapter: Any, annotations: list[Any]) -> list[Any]:
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


def _curate_front_dimensions(adapter: Any, annotations: list[Any]) -> list[Any]:
    """Keep only overall size and common Y; X stations live in the schedule.

    The former print placed nine independent X dimensions from the same left
    origin.  Moving text could not separate their coincident dimension lines.
    A two-row coordinate schedule is both shorter and unambiguous.
    """
    keep = {"Length", "Height", "T0Y"}
    reposition = {
        "Length": (0.190, 0.150),
        "Height": (0.026, 0.190),
        "T0Y": (0.046, 0.215),
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
    return curate_dimensions(adapter, curated, reposition=reposition)


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


def _manufacturing_notes() -> str:
    return "\n".join(
        (
            "UNLESS OTHERWISE SPECIFIED:",
            "1. DIMENSIONS ARE IN MILLIMETRES. INTERPRET PER ASME Y14.5.",
            (
                "2. TOLERANCES: LENGTH +/-0.5; STOCK SECTION +/-0.25; "
                "HOLE CENTRES +/-0.10; CORE DIAMETERS +/-0.05; "
                "ANGLES +/-0.5 DEG."
            ),
            "3. REMOVE BURRS AND BREAK SHARP EDGES 0.2 MAX.",
            (
                f"4. 6 BA BASIC: MAJOR DIA {BA6.major_diameter_mm:.2f}, "
                f"PITCH {BA6.pitch_mm:.2f}, CORE DIA {BA6.core_diameter_mm:.3f}, "
                f"INCLUDED ANGLE {BA6.angle_deg:.1f} DEG."
            ),
            "5. DATUM A IS THE PLATEN-MATING FACE (BLIND-HOLE ENTRY FACE).",
            "6. DATUM A FACE: FLATNESS 0.10; SURFACE FINISH Ra 3.2 OR BETTER.",
            "7. OPPOSITE FACE: PARALLELISM 0.10 TO DATUM A.",
            "8. APPLY BLACK OXIDE AFTER MACHINING.",
        )
    )


def _add_hole_schedule(adapter: Any) -> None:
    draw_note_table(
        adapter,
        rows=(
            (
                "HOLE SET",
                "QTY",
                "CENTRES: X FROM LEFT END; Y=2.50",
                "THREAD / CORE",
            ),
            (
                "T",
                "4",
                "53.00, 67.00, 233.00, 247.00",
                (
                    f"6 BA THRU; CORE DIA {BA6.core_diameter_mm:.3f} THRU; "
                    "TAP FROM REAR"
                ),
            ),
            (
                "B",
                "5",
                "30.00, 90.00, 150.00, 210.00, 270.00",
                (
                    f"6 BA x {BLIND_THREAD_DEPTH:g} FULL; CORE DIA "
                    f"{BA6.core_diameter_mm:.3f} x {BLIND_HOLE_DEPTH:g} DEEP; "
                    "ENTER PLATEN-MATING FACE"
                ),
            ),
        ),
        column_x=(0.014, 0.050, 0.071, 0.202),
        row_y=(0.264, 0.254, 0.243),
    )


def _edge_points(stations_mm: tuple[float, ...]) -> tuple[tuple[float, float], ...]:
    return tuple(
        (FRONT_LEFT_X_M + station / 1000.0, FRONT_HOLE_Y_M)
        for station in stations_mm
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen-guide source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        source_model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, sheet = new_project_drawing(adapter, property_view=PART_STEM)
    summary = {
        0: "Platen Guide Manufacturing Drawing",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project",
        3: "platen guide; manufacturing drawing; 6 BA",
        4: "Generated from the project-owned ASME B drawing standard",
    }
    model_doc = _sw_type_info.flagged(drawing_model, "IModelDoc2")
    for field, value in summary.items():
        model_doc.SummaryInfo(field, value)
        if model_doc.SummaryInfo(field) != value:
            raise RuntimeError(f"drawing summary field {field} did not persist")
    front = place_view(adapter, str(SOURCE), "*Back", 0.190, 0.190, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", 0.375, 0.190, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", 0.205, 0.043, scale=(1, 4))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    thread_callout = (
        f"{BA6.designation}, {BA6.pitch_mm:.2f} PITCH, "
        f"{BA6.angle_deg:.1f} DEG INCLUDED ANGLE"
    )
    thread_seeds, thread_instances = import_cosmetic_threads(adapter, front)
    expected_thread_instances = len(THROUGH_X) + len(BLIND_X)
    if thread_instances != expected_thread_instances:
        raise RuntimeError(
            f"front view has {thread_seeds} cosmetic-thread seed(s) / "
            f"{thread_instances} instance(s); expected {expected_thread_instances}"
        )
    removed_thread_notes = remove_notes_matching(adapter, thread_callout)
    _telemetry.info(
        f"front view imported {thread_seeds} cosmetic-thread seed(s) as "
        f"{thread_instances} instance(s); removed {removed_thread_notes} "
        "automatic callout note(s)"
    )

    front_annotations = _insert_marked_model_dimensions(adapter, front)
    _curate_front_dimensions(adapter, front_annotations)
    right_annotations = _insert_marked_model_dimensions(adapter, right)
    _curate_right_dimensions(adapter, right_annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    _add_hole_schedule(adapter)
    add_hole_group_tags(
        adapter,
        front,
        "T",
        edge_points=_edge_points(THROUGH_X),
        note_positions=tuple(
            (x + (-0.004 if index % 2 == 0 else 0.004), 0.211)
            for index, (x, _y) in enumerate(_edge_points(THROUGH_X))
        ),
    )
    add_hole_group_tags(
        adapter,
        front,
        "B",
        edge_points=_edge_points(BLIND_X),
        note_positions=tuple((x, 0.173) for x, _y in _edge_points(BLIND_X)),
    )

    add_note(adapter, _manufacturing_notes(), 0.014, 0.105)
    add_note(adapter, "PLATEN-MATING FACE — DATUM A", 0.144, 0.224)
    add_note(adapter, "SCALE 3:1", 0.352, 0.163)
    add_note(adapter, "REFERENCE — SCALE 1:4", 0.170, 0.014)

    drawing_model.ClearSelection2(True)
    drawing_model.EditRebuild3()
    sheet_name = adapter._get_attr_or_call(sheet, "GetName")
    if not sheet_name or not drawing_model.ActivateSheet(sheet_name):
        raise RuntimeError("failed to activate drawing sheet for export")
    if not sheet.SetScale(1.0, 1.0, False, False):
        raise RuntimeError("failed to set final drawing sheet scale to 1:1")
    assert_asme_b_sheet(adapter, sheet, phase="before save")

    artifacts = save_drawing(adapter, str(OUTPUTS.slddrw))
    drawing_model, sheet = await reopen_drawing(adapter, OUTPUTS.slddrw)
    if not sheet.SetScale(1.0, 1.0, False, False):
        raise RuntimeError("failed to persist reopened drawing sheet scale")
    check("save final 1:1 drawing sheet", await adapter.save_file(str(OUTPUTS.slddrw)))
    drawing_model, sheet = await reopen_drawing(adapter, OUTPUTS.slddrw)
    assert_asme_b_sheet(adapter, sheet, phase="post-save reopen")
    artifacts.update(save_drawing(adapter, "", pdf_path=str(OUTPUTS.pdf)))
    sanitize_pdf_metadata(OUTPUTS.pdf, title="Platen Guide Manufacturing Drawing")
    render_pdf_png(OUTPUTS.pdf, OUTPUTS.png)
    artifacts["png"] = str(OUTPUTS.png.resolve())
    if set(artifacts) != {"drawing", "pdf", "png"}:
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
