r"""Create the curated machinist drawing for the column clamp, back arc.

The SLDPRT remains authoritative.  This recipe supplies only the back-arc
views, dimension layout and hole callout; sheet/template and export behavior
lives in ``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``.

The sheet runs at 2:1 (the arc is 48 mm ear tip to ear tip); the isometric
carries an explicit 1:1 override so it stays clear of the title block.  Third
angle: the top view (the 15 x 48 plan carrying the column-relief arc) sits
above the front view; the left view (the 48 x 16 back face carrying the two
tapped ear holes) sits to its left.  No frames and no datums
(drawing-guidelines.md rule 5; clamps are not on the drawing-simplicity
allowlist): the bore axis locates the mating face, one side face and the ear
holes by +/- dimensions authored on the part.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sh_column_clamp_back.py sh-column-clamp-back
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
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_reference_dimensions,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from sh_column_clamp_back_spec import (
    ARC_HEIGHT,
    BORE_DIAMETRAL_CLEARANCE,
    COLUMN_MATE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    EAR_HOLE_HEIGHT,
    EAR_HOLE_Z,
    FRONT_ARC_MATE,
    TAP_DRILL_DIA,
)


SPEC = DRAWINGS_BY_NAME["sh_column_clamp_back"]
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
_M = SHEET_SCALE[0] / 1000.0  # model mm -> sheet meters

# Sheet layout (meters).  The model bbox runs -15.5..-0.5 in X (back face to
# mating face), +/-8 in Y (height) and +/-24 in Z (width); at 2:1 the front
# view is 30 x 32 mm, the top view 30 x 96 mm, the left view 96 x 32 mm.
# Each view centres on that bbox.
FRONT_CENTER = (0.200, 0.100)
TOP_CENTER = (0.200, 0.190)
LEFT_CENTER = (0.085, 0.100)
ISO_CENTER = (0.355, 0.205)
ISO_NOTE_XY = (0.330, 0.168)


def _left_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in the left view (+Z toward the front view)."""
    return LEFT_CENTER[0] + model_z_mm * _M


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Top view (the block and bore sketches lie on the Top plane): the
# depth above the view, the grip offset just under it (bore axis to the mating
# face, text outboard right), the width left of the view, the bore axis to
# the near side face right of it, the bore's reference Ø leadered off the
# relief arc through the open mouth, its matched-fit callout under the value.
# Front view: the collar height right of the profile.  Left view (the back
# face): the ear-hole station from the bore axis above the view.
TOP_KEEP = {
    "Depth": (TOP_CENTER[0], 0.257),
    "GripOffset": (0.236, 0.248),
    "Width": (0.165, TOP_CENTER[1]),
    "AnchorZ": (0.240, 0.214),
    "BoreDia": (0.252, 0.172),
}
FRONT_KEEP = {"Height": (0.232, FRONT_CENTER[1])}
LEFT_KEEP = {"EarHole1Z": (_left_x(EAR_HOLE_Z / 2.0), 0.126)}

# Both ear holes stand on the one station the part prints (EarHole1Z).
DIMENSION_PREFIXES = {"EarHole1Z": "2X "}
REFERENCE_DIMENSIONS = ("BoreDia",)
# The bands that are tighter than the title block name their mate and why
# (drawing-guidelines.md rule 4): the bore is matched to the purchased column
# (sh_column_clamp_fit), the grip offset keeps the clamp faces apart once both
# bores seat, and the ear stations line up with the front arc's clearance
# holes.
DIMENSION_CALLOUTS = {
    "BoreDia": (
        f"{BORE_DIAMETRAL_CLEARANCE[0]:.2f}-{BORE_DIAMETRAL_CLEARANCE[1]:.2f} "
        f"DIAMETRAL\nCLEARANCE ON\n{COLUMN_MATE}"
    ),
    "GripOffset": f"GRIP GAP TO\n{FRONT_ARC_MATE}",
}
ABOVE_CALLOUTS = {"EarHole1Z": f"ALIGNS WITH\n{FRONT_ARC_MATE} EARS"}

# Ear-hole height: the placement sketch ties both holes to the bar's centre
# plane, which carries no dimension, so the sheet locates them from the bottom
# face with one drawing dimension, left of the left view.
_TAP_R_SHEET = TAP_DRILL_DIA * _M / 2.0
_EAR_2 = (_left_x(-EAR_HOLE_Z), LEFT_CENTER[1])
_EAR_1 = (_left_x(EAR_HOLE_Z), LEFT_CENTER[1])
_BOTTOM_EDGE = (_left_x(-EAR_HOLE_Z / 2.0), LEFT_CENTER[1] - ARC_HEIGHT / 2.0 * _M)
EAR_HEIGHT_TEXT_XY = (0.026, LEFT_CENTER[1] - 0.004)
HOLE_CALLOUT_XY = (0.120, 0.064)


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

    check("open column-clamp-back source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Column Clamp Back Arc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "column clamp; back arc; tapped #8-32 ears; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(2, 1))
    # finalize_drawing shades the pictorial isometric with edges; the iso
    # first gets local HLR settings so its cosmetic threads export at full
    # quality (_drawing_common.set_high_quality_shaded_with_edges).
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, top, left, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            left,
            keep=LEFT_KEEP,
            view_label="left",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places and bands are authored on the part; the sheet only proves the
    # import kept the places, then marks the reference bore, the pair count
    # and the mates.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, ABOVE_CALLOUTS, location="above")

    if not auto_center_marks(adapter, left, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the left view")

    # Ear-hole height off the bottom face: picked on the bottom edge clear of
    # the holes and on ear 2's tap-drill rim, re-anchored to the hole centre,
    # then the value is proven (the coordinate picks name no entity, so the
    # check is value-only: no other edge pair in this view measures 8.0
    # vertically to a rim).
    ear_height = add_edge_dimension(
        adapter,
        left,
        p0=_BOTTOM_EDGE,
        p1=(_EAR_2[0] - 0.6 * _TAP_R_SHEET, _EAR_2[1] - 0.8 * _TAP_R_SHEET),
        text_xy=EAR_HEIGHT_TEXT_XY,
        label="ear-hole height",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, ear_height, label="ear-hole height")
    assert_dimension_measures(
        adapter, ear_height, expected_mm=EAR_HOLE_HEIGHT, label="ear-hole height"
    )

    add_native_hole_callout(
        adapter,
        left,
        edge_xy=(_EAR_1[0] + 0.6 * _TAP_R_SHEET, _EAR_1[1] - 0.8 * _TAP_R_SHEET),
        callout_xy=HOLE_CALLOUT_XY,
        label="ear taps",
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Column Clamp Back Arc Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#8-32 Tapped Hole" note to the face view
        # once the tap carries a hole callout; the callout already states it.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
