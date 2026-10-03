r"""Create the curated machinist drawing for the platen guide lock plate.

The SLDPRT remains authoritative.  This recipe supplies only the guide-lock
views, dimension layout and hole callout; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The sheet runs at 4:1 (the plate is 22 x 15.65 x 2); the isometric carries an
explicit 2:1 override so it stays clear of the title block.  A flat plate
needs only the face view (front), one thickness view (right) and the iso.
No frames and no datums (policy rule 3): the screw holes locate by +/-
coordinates from the plate's corner, authored on the part.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_guide_lock.py guide-lock
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm

from pd_guide_lock_spec import (
    DRAWING_PRECISION_BY_NAME,
    HOLE_SPEC,
    HOLE_XY,
    LOCK_HEIGHT,
    LOCK_WIDTH,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pd_guide_lock"]
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

SHEET_SCALE = (4.0, 1.0)

# Sheet layout (meters).  The front view's model bbox is 22 x 15.65 (the plate
# face); at 4:1 the view is 88 x 62.6 mm, x 0.091..0.179.  Third angle: the
# right view (the 2-thick strip edge-on) sits to its right, past the hole
# callout; the isometric rides top-right.
FRONT_CENTER = (0.135, 0.150)
RIGHT_CENTER = (0.265, 0.150)
ISO_CENTER = (0.340, 0.200)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - LOCK_WIDTH / 2.0) * SHEET_SCALE[0] / 1000.0


def _sheet_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - LOCK_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


# Handy picks derived from the layout above.
LEFT_EDGE_X = _sheet_x(0.0)
RIGHT_EDGE_X = _sheet_x(LOCK_WIDTH)
BOTTOM_EDGE_Y = _sheet_y(0.0)
HOLE_R_SHEET = blind_cut_dia_mm(HOLE_SPEC) * SHEET_SCALE[0] / 2000.0
HOLE_Y_SHEET = _sheet_y(HOLE_XY[0][1])
HOLE_2_X_SHEET = _sheet_x(HOLE_XY[1][0])

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Width stacks below the front view under the two hole X
# coordinates; Height sits left of the plate and the shared hole Y outboard
# of it, its text under the plate's bottom-left corner; the strip thickness
# rides above the right view.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], 0.088),
    "Height": (0.071, FRONT_CENTER[1]),
    "Hole1X": (0.103, 0.104),
    "Hole2X": (0.127, 0.096),
    "Hole1Y": (0.061, 0.110),
}
RIGHT_KEEP = {"Depth": (RIGHT_CENTER[0], 0.196)}
# Both holes stand on the one Y coordinate the part prints (Hole1Y).
DIMENSION_PREFIXES = {"Hole1Y": "2X "}
# The bent leader elbows at the text's LEFT end and enters hole 2 from its
# upper-right quadrant, crossing only the plate's right edge; the text stands
# between that edge and the right view.
HOLE_CALLOUT_XY = (0.215, 0.160)
HOLE_CALLOUT_PROCESS = "DRILL"


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open guide-lock source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Guide Lock Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "guide lock; manufacturing drawing; 1/8 drill screw holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    # The through holes are fully defined by their callout; the strip seen
    # edge-on needs no hidden bores.
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The places and the explicit bands (height, hole coordinates) are
    # authored on the part (the paper-drive lock-station sweep and the screw
    # set window read the same spec); the sheet only proves the import kept
    # the places. The hole size ships as a native wizard callout below.
    annotations = [
        *curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front"),
        *curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right"),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            HOLE_2_X_SHEET + 0.6 * HOLE_R_SHEET,
            HOLE_Y_SHEET + 0.8 * HOLE_R_SHEET,
        ),
        callout_xy=HOLE_CALLOUT_XY,
        label="guide-lock screw holes",
        process=HOLE_CALLOUT_PROCESS,
    )
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.160)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Guide Lock Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
