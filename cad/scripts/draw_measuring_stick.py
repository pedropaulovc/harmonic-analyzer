r"""Create the curated machinist drawing for the ruled measuring stick.

The SLDPRT remains authoritative.  This recipe supplies only the bar's ruled-face
view, the overall envelope dimensions, and the graduation notes; every shared
sheet/template, import, curation, and export behavior lives in ``_drawing_common``.

The stick is a half-hard brass bar (200 x 8 x 3) with a 0-10 scale engraved 0.5
deep across a 142 mm span (14.2 mm pitch, ``build_measuring_stick``), one longer
0.5 tick and the 0..10 numerals beside the full ticks.  The bar lies along +X on
the Front plane and the graduations cut the z=0 BACK face, so ``*Back`` (rotated
so tick 0 is at the left) shows the ruled face; the sheet runs 1:1 and the
isometric drops to 1:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_measuring_stick.py measuring-stick
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import build_measuring_stick as part
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["measuring_stick"]
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

SHEET_SCALE = (1.0, 1.0)   # 1:1 whole sheet (200 mm bar)

# Sheet layout (meters).  The ruled face (front) runs full width across the top;
# the isometric (1:2) sits mid-right; the notes fill the lower-left.
FRONT_CENTER = (0.122, 0.215)
ISO_CENTER = (0.300, 0.130)

# Per-view survivors of the marked-dimension import: the bar envelope only.  The
# length reads 200 (above the bar), the width 8 (right of the right end).
FRONT_KEEP = {
    "BodyLength": (0.122, 0.234),
    "BodyWidth": (0.250, 0.215),
}

SCALE_LABEL_Y = 0.201
# Tick-value labels ride the part's own scale layout (1:1 view, mm -> m): tick 0
# sits SCALE_START_X from the bar's left end, the rest at DIVISION_SPACING pitch.
SCALE_LABEL_X0 = FRONT_CENTER[0] + (part.SCALE_START_X - part.BODY_LENGTH / 2.0) / 1000.0
SCALE_LABEL_PITCH = part.DIVISION_SPACING / 1000.0


def _rotate_ruled_face(adapter: Any, view: Any) -> None:
    """Orient tick zero at the left and the grooves from the lower edge."""
    adapter._attempt(lambda: setattr(view, "Angle", math.pi))
    applied = float(adapter._get_attr_or_call(view, "Angle") or 0.0)
    if abs(abs(applied) - math.pi) > 1e-9:
        raise RuntimeError(f"failed to rotate ruled-face view (reads {applied:g})")
    adapter.currentModel.EditRebuild3()


def _add_scale_labels(adapter: Any) -> None:
    """Show the 0..10 tick values below the bar (the engraved numerals on the
    face are turned 90 degrees and 2 mm tall, so they read poorly at 1:1)."""
    for value in range(part.DIVISION_COUNT):
        x = SCALE_LABEL_X0 + value * SCALE_LABEL_PITCH
        if add_note(adapter, str(value), x, SCALE_LABEL_Y) is None:
            raise RuntimeError(f"failed to add measuring-stick scale label {value}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open measuring-stick source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Measuring Stick Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "measuring stick; ruled brass bar; 0-10 scale",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Tick cuts are engraved into the back broad face, so the back view is the
    # actual ruled face.  The old front view showed an untouched rectangle and
    # forced the machinist to infer every graduation from prose.
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    _rotate_ruled_face(adapter, front)
    set_hidden_lines_removed(adapter, iso)
    set_hidden_lines_visible(adapter, front)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    _add_scale_labels(adapter)

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.110)
    add_property_linked_note(adapter, "Front View Note", 0.040, 0.184)
    add_property_linked_note(adapter, "Isometric View Note", 0.250, 0.092)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Measuring Stick Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
