r"""Create the manufacturing drawing for the rocker strap (MHA-CH-013).

Under ``cad/docs/drawing-guidelines.md``: the flat strap of the built-up rocker
arm MHA-CH-006 (``ch_rocker_strap_spec``), every size a native model dimension
of its one profile sketch, located from the Ø10.200 H7 hub hole's centre
(rule 10): the top edge's height over the hole with the MHA-CH-006 band and
mate, the R800 top edge and the concentric R816 bottom edge, both tip corners'
and both taper feet's offsets, and the 2X tip land. The hole's H7 band names
the MHA-CH-012 hub and the fit (rule 4); the 2.500 thickness, on the end view,
names the rod fork it runs in. One property-linked note says what the views
cannot (the arcs' centre is ~808 mm off the sheet). No datums, no frames, no
roughness symbol (rule 6: a pressed bore carries none). The decimal places
and bands are the PART's (``ch_rocker_strap_notes.DRAWING_PRECISION``); this
script only reads them back off the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_strap.py ch-rocker-strap
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
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
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from ch_rocker_strap_notes import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
)
from ch_rocker_strap_spec import BOT_END_X, PIVOT_MID_Y, ROD_TIP_X, TOP_END_Y

SPEC = DRAWINGS_BY_NAME["ch_rocker_strap"]
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

# The 292.5 mm strap at full size across the sheet's upper band, its 2.5 mm
# end view to the right; the isometric at 1:4 (captioned, it differs from the
# sheet scale) and the note sit left of the title block below.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 4)
FRONT_CENTER = (0.185, 0.185)
RIGHT_CENTER = (0.385, FRONT_CENTER[1])  # projected: same row as the front
ISO_CENTER = (0.110, 0.100)
ISO_CAPTION_XY = (0.080, 0.078)
NOTES_XY = (0.020, 0.040)


def _front(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, y) on the 1:1 front view, whose box is
    centred on FRONT_CENTER: x spans +-ROD_TIP_X, y 0..TOP_END_Y."""
    return (
        FRONT_CENTER[0] + x_mm / 1000.0,
        FRONT_CENTER[1] + (y_mm - TOP_END_Y / 2.0) / 1000.0,
    )


_HOLE = _front(0.0, PIVOT_MID_Y)
# The tip corners' offsets on one dimension line above the strap, the taper
# feet's on one below it, each pair meeting on the hole centre's extension
# line. Between the strap and the lower line: both radii's texts (left, below
# both arcs, so each leader stays outside its circle -- draw_ch_rocker_arm
# _dress_arc_radii) and the hole's callout (right, its leader short). The top
# edge's height reads left of the hole, under the upper line.
TIP_LINE_Y = 0.232
FOOT_LINE_Y = 0.125
FRONT_KEEP = {
    "TailTipX": (FRONT_CENTER[0] - ROD_TIP_X / 2000.0, TIP_LINE_Y),
    "RodTipX": (FRONT_CENTER[0] + ROD_TIP_X / 2000.0, TIP_LINE_Y),
    "BottomTailX": (FRONT_CENTER[0] - BOT_END_X / 2000.0, FOOT_LINE_Y),
    "BottomRodX": (FRONT_CENTER[0] + BOT_END_X / 2000.0, FOOT_LINE_Y),
    "TopRadius": (FRONT_CENTER[0] - 0.085, 0.158),
    "BottomRadius": (FRONT_CENTER[0] - 0.045, 0.158),
    "HoleDia": (_HOLE[0] + 0.060, 0.160),
    "TopAbovePivot": (_HOLE[0] - 0.035, 0.207),
    # Right of the land's own dimension line, between its extension lines:
    # at +0.020 (r1) the text sat on the upper extension line.
    "RodTipLen": (_front(ROD_TIP_X, 0.0)[0] + 0.034, 0.200),
}
# The 2.5 mm end view is narrower than its four-row callout: centred over it
# (r1) both extension lines ran through the text, so the text stands below
# the view, left of its left extension line, the dimension line carried out.
RIGHT_KEEP = {"StrapThickness": (RIGHT_CENTER[0] - 0.027, 0.150)}
ARC_RADIUS_NAMES = ("TopRadius", "BottomRadius")


def _exterior_radius_leaders(adapter: Any, annotations: list[Any]) -> None:
    """Exterior leaders on both radii (draw_ch_rocker_arm._dress_arc_radii):
    the ~808 mm centres are off the sheet, so no centre-directed leader."""
    remaining = set(ARC_RADIUS_NAMES)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = False
        display.ArcExtensionLineOrOppositeSide = False
        display.ArrowSide = 1  # swDimArrowsOutside
        display.SolidLeader = False
        if (
            bool(display.ShortenedRadius)
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != 1
            or bool(display.SolidLeader)
        ):
            raise RuntimeError(f"{name} retained its centre-directed radius leader")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"strap radius dimensions missing: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-strap source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Strap Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker strap; 1018 flat; hub hole H7",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # A flat plate: every edge reads on the face view; hidden lines off
    # everywhere (drawing-guidelines.md rule 9).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *right_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _exterior_radius_leaders(adapter, front_annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The template centre-marks the hub hole as the view is placed
    # (draw_mg_wheel_drum: a second AutoInsertCenterMarks2 printed a duplicate).
    add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_XY)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Strap Manufacturing Drawing",
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
