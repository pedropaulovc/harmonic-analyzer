r"""Create the curated machinist drawing for the magnifying vertical rod.

The rod is a revolved Ø5 x 150 brass capsule with hemispherical ends -- a
smooth, tangent-continuous body with NO flat face, no end-face circle and no
selectable silhouette edge, so coordinate picks are unreliable (the dome-tip
pick fails) and the print rests on the auto-imported profile marks only: the
tip-to-tip overall length (the profile's axis line) and the dome radius R2.5.  The outside diameter rides the stock
note (the dome radius implies it); the overall is a real dimension between the
two tips, with a longitudinal centreline.  The rod axis is local +X, so
the FRONT view is the long side elevation and the RIGHT view is the circular end.

The print is plain (cad/docs/drawing-simplicity-policy.md): a plain rod is not
on the GD&T allowlist and it is lock-mated in service, so it carries no datum,
frame, roughness or basic dimension.

Run with SolidWorks open::

    uv run python cad\scripts\draw_magnifying_vertical_rod.py magnifying-vertical-rod
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
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from magnifying_vertical_rod_spec import ROD_DIA, ROD_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["magnifying_vertical_rod"]
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

SHEET_SCALE = (1.0, 1.0)
END_VIEW_SCALE = 4.0
FRONT_CENTER = (0.115, 0.150)
RIGHT_CENTER = (
    FRONT_CENTER[0] + ROD_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.055,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.350, 0.185)
ISO_SCALE = (1, 2)

# The two native profile dims the print keeps: the overall length, tip to tip
# on the profile's axis line (below the side view, the conspicuous controlling
# length), and the dome radius (above the right dome).
FRONT_KEEP = {
    "RodOverall": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.032),
    "DomeRadius": (RIGHT_CENTER[0] - 0.075, FRONT_CENTER[1] + 0.028),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
# Longitudinal centreline: the rod's cylindrical face picked at the view
# centre (a revolved outline is a silhouette, so the FACE is the pick).
AXIS_FACE_PICK = (FRONT_CENTER[0], FRONT_CENTER[1])
# The stock Ø rides the note; the dome instruction stays at the leader.
DIMENSION_CALLOUTS = {"DomeRadius": "FULL R, BOTH ENDS"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-vertical-rod source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Vertical Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying vertical rod; turned brass rod; domed ends",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in every orthographic view (policy rule 7).
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    add_view_centerline(
        adapter, front, face_xy=AXIS_FACE_PICK, label="rod longitudinal axis"
    )
    # The end silhouette is circular; SolidWorks files it under the same
    # "hole" bit as a bored circle, so a disabled bit makes the API a no-op.
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to rod end view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.100)
    add_property_linked_note(adapter, "End View Note", RIGHT_CENTER[0] - 0.022, 0.100)
    add_property_linked_note(adapter, "Iso View Note", 0.320, 0.140)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Vertical Rod Manufacturing Drawing",
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
