r"""Create the curated machinist drawing for the lever wire (WIRE 1).

The lever wire is a Ø0.8 drawn-steel cylinder ~353 long.  The sheet runs 1:5;
at that scale the front view is a hairline, so its diameter is read on a 10:1
END view
(the *Top orientation, looking down the wire axis) carrying the marked profile
circle ``WireDiaDim`` with the bought-wire band printed natively from the
model.  The FRONT view carries the marked extrusion depth as a REFERENCE
dimension, captioned as the straight rest-run from the hub end to the hook
end: it is not a cut length -- the source model defines neither the formed
hook nor the hub wrap, so the note has the maker form them at assembly and
cut long.  The print is plain (cad/docs/drawing-simplicity-policy.md): no
datum, frame, roughness or basic dimension.

Run with SolidWorks open::

    uv run python cad\scripts\draw_lever_wire.py lever-wire
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from lever_wire_geom import WIRE_LEN
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view


SPEC = DRAWINGS_BY_NAME["lever_wire"]
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

# The sheet IS 1:5 (machinist review 2026-09-02: the title block said 1:1
# while its principal view said 1:5); the front view rides that scale
# explicitly, and the end view is enlarged 10:1 so the Ø0.8 circle is 8 mm.
SHEET_SCALE = (1.0, 5.0)
WIRE_SCALE = (1, 5)  # ~353 long reduced to ~71 mm on the sheet
END_SCALE = (10, 1)
FRONT_CENTER = (0.135, 0.150)
END_CENTER = (0.215, 0.150)

_HALF_RUN = WIRE_LEN * WIRE_SCALE[0] / WIRE_SCALE[1] / 2000.0  # sheet metres

# Front view: the rest-run length stands right of the hairline.  End view:
# the diameter leads up-right of the circle.
FRONT_KEEP = {
    "Depth": (FRONT_CENTER[0] + 0.022, FRONT_CENTER[1]),
}
END_KEEP = {
    "WireDiaDim": (END_CENTER[0] + 0.016, END_CENTER[1] + 0.012),
}
# The rest-run is a reference figure between two assembly-defined points,
# never a cut length; its callout names both ends.
REFERENCE_DIMENSIONS = ("Depth",)
DIMENSION_CALLOUTS = {
    "Depth": "STRAIGHT REST RUN, HUB END TO HOOK END",
}
# The banded wire diameter is a bought size, not a held one: two places, the
# native +/- band printed beside it (policy rule 2).
DIMENSION_PRECISION = {"WireDiaDim": 2}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open lever-wire source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Lever Wire (WIRE 1) Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lever wire; drawn steel wire; amplification chain",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=WIRE_SCALE)
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=END_SCALE)
    # Hidden lines ON in every orthographic view (policy rule 7).
    for view in (front, end):
        set_hidden_lines_visible(adapter, view)

    # The end view claims the profile circle's banded diameter FIRST (a
    # Top-plane circle could otherwise import into the front view as a width
    # across the hairline and be deleted there); the front view then claims
    # the extrusion depth (the straight rest-run).
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, end_annotations, DIMENSION_PRECISION)
    # (352.80): the rest-run between the hub tangency and the hook mouth is
    # informational -- the wire is cut long and formed at assembly.
    for annotation in front_annotations:
        if dimension_name(adapter, annotation) in REFERENCE_DIMENSIONS:
            set_reference_dimension(
                adapter, annotation, label="straight rest-run reference"
            )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Front View Note", 0.118, 0.100)
    add_property_linked_note(adapter, "End View Note", 0.196, 0.128)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lever Wire (WIRE 1) Manufacturing Drawing",
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
