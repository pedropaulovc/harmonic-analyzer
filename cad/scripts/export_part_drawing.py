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
    add_overall_dimension,
    add_third_angle_symbol,
    auto_center_marks,
    curate_dimensions,
    dimension_name,
    draw_border_and_title_block,
    insert_model_dims,
    new_drawing,
    place_view,
    save_drawing,
    set_units_mm,
    setup_sheet,
)

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


def _set_hlr(adapter: Any, view: Any) -> None:
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 2, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-removed drawing view")


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
    names = {dimension_name(adapter, ann) for ann in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
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
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=reposition
    )
    present = {dimension_name(adapter, ann) for ann in curated}
    missing = sorted(keep - present)
    if missing:
        raise RuntimeError(f"drawing is missing model dimensions: {missing}")
    return curated


def _manufacturing_notes() -> str:
    through = ", ".join(f"{x:g}" for x in THROUGH_X)
    blind = ", ".join(f"{x:g}" for x in BLIND_X)
    return "\n".join(
        (
            "UNLESS OTHERWISE SPECIFIED:",
            "1. DIMENSIONS ARE IN MILLIMETRES. INTERPRET PER ASME Y14.5.",
            "2. REMOVE BURRS AND BREAK SHARP EDGES 0.2 MAX.",
            "3. 4X 6 BA THRU, ENTER FROM REAR; X = " + through + ".",
            (
                f"4. 5X 6 BA x {BLIND_THREAD_DEPTH:g} FULL THREAD; "
                f"TAP DRILL DIA {BA6.tap_diameter_mm:.3f} x {BLIND_HOLE_DEPTH:g} DEEP; "
                f"X = {blind}."
            ),
            (
                f"5. 6 BA BASIC: MAJOR DIA {BA6.major_diameter_mm:.2f}, "
                f"PITCH {BA6.pitch_mm:.2f}, INCLUDED ANGLE {BA6.angle_deg:.1f} DEG."
            ),
            "6. ALL HOLE CENTRES LIE 2.5 FROM THE LOWER EDGE.",
            "7. APPLY BLACK OXIDE AFTER MACHINING.",
        )
    )


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
    draw_border_and_title_block(
        adapter,
        [
            "PLATEN GUIDE",
            f"DWG NO. {props['Number']}  REV {props['Revision'] or '-'}",
            f"MATERIAL: {props['Material Specification']}",
            f"FINISH: {props['Finish']}",
            f"QTY: {props['Quantity']}",
            "SCALE 1:1  THIRD ANGLE",
            "SHEET 1 OF 1",
        ],
        width=SHEET_WIDTH,
        height=SHEET_HEIGHT,
        block_w=0.145,
        row_h=0.008,
    )
    add_third_angle_symbol(adapter, 0.267, 0.039, size=0.004)

    front = place_view(adapter, str(SOURCE), "*Front", 0.190, 0.190, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", 0.375, 0.190, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", 0.085, 0.075, scale=(1, 2))
    for view in (front, right, iso):
        _set_hlr(adapter, view)

    annotations = insert_model_dims(
        adapter, front, marked_only=False, hole_callouts=False, all_views=False
    )
    _curate_front_dimensions(adapter, annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    if add_overall_dimension(adapter, right, vertical=False, offset=0.012) is None:
        raise RuntimeError("failed to add the 10 mm thickness dimension")

    add_note(adapter, _manufacturing_notes(), 0.014, 0.112)
    add_note(adapter, "FRONT", 0.184, 0.174)
    add_note(adapter, "RIGHT", 0.366, 0.163)
    add_note(adapter, "ISOMETRIC (REFERENCE)", 0.040, 0.031)

    artifacts = save_drawing(
        adapter, str(SLDDRW), pdf_path=str(PDF), png_path=str(PNG)
    )
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
    sys.exit(run_build(build, kind=None))
