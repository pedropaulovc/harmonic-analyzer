r"""Create the curated machinist drawing for the fulcrum-shaft end keeper.

The SLDPRT remains authoritative.  This recipe supplies only the keeper's
views, dimension layout, hole callout, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the bracket is ~28 x 32 x 14 with the proud ball);
the isometric carries an explicit 1:1 override so it stays clear of the
title block.  Four views: the side profile (front), the plan (top, which
carries the counterbored screw-hole callout), the end view (right, which
carries the width / shaft-axis-height / crown stack), and the isometric.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
screwed-down shaft-end bracket carries no datums, no feature-control frames
and no roughness symbols; the block tolerances govern.

Run with SolidWorks open::

    uv run python cad\scripts\draw_fulcrum_keeper.py fulcrum-keeper
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
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
from fulcrum_keeper_spec import (
    CBORE_DIA_MM,
    FOOT_REACH,
    SCREW_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["fulcrum_keeper"]
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

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The front (side-profile) view's model bbox is
# X -23..+4.75 (ball proud of the lug) by Y 0..32.2; at 2:1 that is
# ~55.5 x 64.4 mm.  Third angle: the plan (top view) rides above the front,
# the end view (right) sits to its right, the isometric top-right.
FRONT_CENTER = (0.110, 0.130)
TOP_CENTER = (0.110, 0.228)
RIGHT_CENTER = (0.225, 0.130)
ISO_CENTER = (0.330, 0.190)

# Model bbox centre the projected views are laid out around.
_X_MID = (-FOOT_REACH + 4.75) / 2.0  # -9.125 (ball cap at +4.75)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - _X_MID) * SHEET_SCALE[0] / 1000.0


# Handy picks derived from the layout above.
HOLE_X_SHEET = _front_x(SCREW_X)  # screw-hole station, shared by the top view
CBORE_R_SHEET = CBORE_DIA_MM * SHEET_SCALE[0] / 2000.0

# Per-view survivors of the marked-dimension import: parametric name ->
# sheet position.  The profile pair stacks below the front view; the end
# view carries the width plus the shaft-axis / crown stack.
FRONT_KEEP = {
    "FootReach": (0.096, 0.086),
    "PadLen": (0.084, 0.078),
}
RIGHT_KEEP = {
    "Depth": (0.225, 0.172),
    "ShaftAxisH": (0.196, 0.126),
    "CrownDia": (0.225, 0.180),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-keeper source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Keeper Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum keeper; shaft end bracket; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, top, right):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")

    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Counterbored screw hole ships as the native wizard callout on the plan
    # view, where it projects as its true circles; the drill rides as its
    # prefix.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(HOLE_X_SHEET, TOP_CENTER[1] + CBORE_R_SHEET),
        callout_xy=(0.040, 0.238),
        label="keeper foot screw hole",
        process="DRILL",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.062)
    add_property_linked_note(adapter, "Isometric View Note", 0.310, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Keeper Manufacturing Drawing",
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
