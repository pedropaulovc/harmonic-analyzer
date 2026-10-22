r"""Create the curated machinist drawing for the platen guide lock plate.

The SLDPRT remains authoritative.  This recipe supplies only the guide-lock
views, dimension layout and hole callout;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The sheet runs at 4:1 (the plate is 22 x 9.6, cut from 1/16 sheet, its four
corners rounded); the isometric carries an explicit 2:1 override so it stays
clear of the title block.  A flat plate needs only the face view (front), one
thickness view (right) and the iso.
No frames and no datums (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the screw holes locate by +/-
coordinates from the plate's corner, authored on the part.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_guide_lock.py pd-guide-lock
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pd_guide_lock_spec import (
    DRAWING_PRECISION_BY_NAME,
    HOLE_SPEC,
    HOLE_XY,
    LOCK_HEIGHT,
    LOCK_STOCK_CALLOUT,
    LOCK_WIDTH,
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

# Sheet layout (meters).  The front view's model bbox is 22 x 9.6 (the plate
# face); at 4:1 the view is 88 x 38.4 mm, x 0.106..0.194, y 0.156..0.194.
# Third angle: the right view (the 1/16 sheet edge-on) sits to its right,
# past the hole callout; the isometric rides top-right.  The whole group sits
# centred between the border and the title block (it sat 25 mm low and 15 mm
# left under an empty upper field, machinist review of 40e51b9a7).
FRONT_CENTER = (0.150, 0.175)
RIGHT_CENTER = (0.280, 0.175)
ISO_CENTER = (0.355, 0.225)
ISO_NOTE_XY = (0.330, 0.195)


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
# coordinates, the 4.000's text outboard of the plate's left edge (between
# its extension lines the hole's own extension cut through it); the shared
# hole Y stands left of the plate, its text under the plate's bottom-left
# corner, and Height outboard of it (smaller dimension nearer the part), its
# value mid-way between the top and bottom extension lines and left of the
# hole Y dimension line, where the hole Y extension stops (inboard of it, the
# value sat on the top extension line, machinist review of 1c9f9b2a6); the 4X
# corner radius stands off the top-right corner, its leader landing on that
# arc clear of the Height's extension lines on the left and the hole callout
# below; the sheet thickness rides above the right view, its one-line
# as-supplied stock callout in the clear field above the value.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], 0.125),
    "Height": (0.057, FRONT_CENTER[1]),
    "Hole1X": (0.087, 0.138),
    "Hole2X": (0.142, 0.133),
    "Hole1Y": (0.076, 0.147),
    "CornerR": (0.215, 0.211),
}
RIGHT_KEEP = {"Depth": (RIGHT_CENTER[0], 0.209)}
# Native witnesses at X276.825/283.175 ended at Y204.444 through the value.
# Offset the whole stock/value block left and above, without moving the span.
THICKNESS_TEXT_OFFSET = {"Depth": (0.245, 0.226)}
# Both holes stand on the one Y coordinate the part prints (Hole1Y); the one
# printed fillet stands for all four equal corners (CornerR). A custom prefix
# replaces SolidWorks' own radius "R", so it carries it ("4X 1.8" printed
# without, farm run 20261012T061737079Z).
DIMENSION_PREFIXES = {"Hole1Y": "2X ", "CornerR": "4X R"}
DIMENSION_CALLOUTS = {"Depth": LOCK_STOCK_CALLOUT}
# The bent leader elbows at the text's LEFT end and enters hole 2 from its
# upper-right quadrant, crossing only the plate's right edge; the text stands
# between that edge and the right view.
HOLE_CALLOUT_XY = (0.233, 0.185)
HOLE_CALLOUT_PROCESS = "DRILL"
# pd_vn_guide_lock_screw_spec spends these coordinate bands against the
# rail's tap position in LOCK_SET_OFFSET; this is a screw-clearance set window,
# not a locating/reamed fit and not a support-bar hole pattern.
HOLE_MATE_CALLOUT = (
    f"{_config.parts('pd-vn-guide-lock-screw')['number']} SCREWS\n"
    f"{_config.parts('pd-platen-guide')['number']} PLATEN GUIDE\n"
    "CLEARANCE FOR BIAS SETTING"
)


def _name_hole_mate(display: Any) -> None:
    """Append the mate while preserving the Hole Wizard's live definitions.

    As on draw_ch_channel_lever, writable below-text slot 4 corresponds to
    definition slot 8; prefix, suffix and above definitions 5–7 stay native.
    """
    display = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    below = definitions[8].replace("\r", "").rstrip()
    updated = f"{below}\n{HOLE_MATE_CALLOUT}" if below else HOLE_MATE_CALLOUT
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(
            "guide-lock hole mate or native definitions did not persist: "
            f"{[str(display.GetText(part) or '') for part in (5, 6, 7, 8)]!r}"
        )


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

    # The places and the explicit bands (sheet thickness, hole coordinates)
    # are authored on the part (the paper-drive lock-station
    # sweep and the screw set window read the same spec); the sheet only
    # proves the import kept the places. The hole size ships as a native
    # wizard callout below.
    annotations = [
        *curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front"),
        *curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right"),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="above")
    offset_dimension_text(adapter, annotations, THICKNESS_TEXT_OFFSET)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    hole_callout = add_native_hole_callout(
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
    _name_hole_mate(hole_callout)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

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
