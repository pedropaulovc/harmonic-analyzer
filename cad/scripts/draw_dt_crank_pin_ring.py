r"""Create the manufacturing drawing for the crank-pin keeper ring (MHA-DT-27).

Under ``cad/docs/drawing-guidelines.md``: a round brass wire ring, its ends
butted and silver-soldered, closed through the taper pin's cross-hole. The
top view shows the ring at true shape with its one controlling size, the
inside diameter, from the part's blanked ``RingReference`` sketch (a torus has
no edge to dimension), and the solder bead as REFERENCE. The front view, below
it in projection, shows the ring edge-on with the wire's stock diameter as
REFERENCE. An isometric and the property-linked notes complete the sheet. No
datums, no frames, no roughness symbol: the part is ``visual_noncritical``,
so every value takes the title block's one-place band.

The decimal places are the PART's (``dt_crank_pin_ring_notes``, applied
natively by ``build_dt_crank_pin_ring``); this script only reads them back.

Drawn 5:1 -- an Ø13 ring of Ø1 wire is a speck on a B sheet at anything less.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimensions,
)
import _drawing_hidden_sketches as hidden_sketches
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_pin_ring_notes import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
    RING_ID,
)
from dt_crank_pin_ring_spec import MEAN_R, WIRE_DIA


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_pin_ring"]
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

SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm
# Third-angle: the top view (true shape) sits above the front view (edge-on).
# Both span the ring's same X range, so their bounding-box centres share x
# and the ring centre lands on it.
TOP_CENTER = (0.150, 0.190)
FRONT_CENTER = (0.150, 0.110)
ISO_CENTER = (0.335, 0.175)
NOTES_XY = (0.020, 0.080)  # left of the title block, below the views

# Printed half-sizes in sheet metres, which every dimension is placed clear of.
HALF_OD = (MEAN_R + WIRE_DIA / 2.0) * _S  # 0.0325
HALF_ID = RING_ID / 2.0 * _S  # 0.0275
HALF_WIRE = WIRE_DIA / 2.0 * _S  # 0.0025

# Top view: the inside diameter's text up and left of the ring; the bead,
# at the ring's bottom (the joint's side), labelled down and right in the
# open band between the two views. Front view: the wire's diameter at the
# ring's left end (the crown, where the wire circle lies), labelled left.
TOP_KEEP = {
    "RingID": (TOP_CENTER[0] - HALF_OD - 0.012, TOP_CENTER[1] + HALF_OD + 0.008),
    "JointDia": (TOP_CENTER[0] + HALF_OD + 0.022, TOP_CENTER[1] - HALF_OD - 0.012),
}
# The wire's callout block (18-character rows) stands up and left, clear of
# the edge view's left end.
FRONT_KEEP = {
    "WireDia": (FRONT_CENTER[0] - HALF_OD - 0.032, FRONT_CENTER[1] + 0.018),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open keeper-ring source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Pin Keeper Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank pin keeper ring; formed brass wire; silver-soldered",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # Solid wire has nothing inside: hidden lines off everywhere
    # (drawing-guidelines.md rule 9 (show internal shape in solid lines)).
    for view in (top, front, iso):
        set_hidden_lines_removed(adapter, view)

    # The inside diameter lives on a reference sketch the part saves hidden,
    # in the ring's own plane: the top view curates through
    # _drawing_hidden_sketches, which shows that sketch in this view only.
    top_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*top_annotations, *front_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # Descriptive words only; every value and its places are the model's.
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The wire is purchased stock and the bead the joint's size: both are
    # native diameters, so the plural helper keeps their Ø inside "( )".
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Pin Keeper Ring Manufacturing Drawing",
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
