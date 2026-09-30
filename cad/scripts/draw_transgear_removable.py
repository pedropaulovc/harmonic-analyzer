r"""Create the manufacturing drawing for the removable #25 sprocket (MHA-081).

One sheet for the three configurations: the views draw the saved T24, and
the property-linked SPROCKET DATA block lists what differs between T12, T18
and T24 (the tooth count and the diameters it sets).  The face view
(``*Front``) carries the bore, the two drive-pin holes and their locations;
the edge view (``*Top``, third-angle above it) carries the plate thickness,
whose dimension lies in the revolve sketch's Top plane.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)
from transgear_removable_spec import (
    DEFAULT_CONFIG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PLATE,
)

SPEC = DRAWINGS_BY_NAME["transgear_removable"]
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

# The T24 is Ø52 over the tips: 2:1 draws it 104 wide and the Ø2.5 pin holes
# 5 wide, with room for the pin-location chain beside the face view.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.110, 0.150)
# Third-angle top view: the plate seen edge-on, 5.6 tall, above the face view.
TOP_CENTER = (FRONT_CENTER[0], 0.228)
ISO_CENTER = (0.335, 0.150)
GEAR_DATA_XY = (0.225, 0.262)
MANUFACTURING_NOTES_XY = (0.018, 0.060)

# Each pin centre dimension runs from the bore axis to its hole; the two
# stack into one vertical chain right of the teeth.  Each one's text sits
# beyond its own hole, above the chain for +Y and below it for -Y: printed
# inside the chain, each text was struck by the other's outside arrow tail.
_PIN_CHAIN_X = FRONT_CENTER[0] + 0.070
FRONT_KEEP = {
    "BoreDiaDim": (FRONT_CENTER[0] + 0.070, FRONT_CENTER[1] - 0.052),
    "PinPosDia": (FRONT_CENTER[0] - 0.075, FRONT_CENTER[1] + 0.060),
    "PinPosY": (_PIN_CHAIN_X, FRONT_CENTER[1] + 0.021),
    "PinNegY": (_PIN_CHAIN_X, FRONT_CENTER[1] - 0.021),
}
TOP_KEEP = {
    "BlankWidth": (TOP_CENTER[0] + 0.065, TOP_CENTER[1] + PLATE * _S / 2000.0),
}
# The two pin holes share one size: the +Y hole's diameter prints for both.
# Both holes and the bore are drilled through: the title block's DRILLED
# HOLES row governs their sizes.
CALLOUTS_ABOVE = {"PinPosDia": "2X"}
CALLOUTS_BELOW = {"BoreDiaDim": "DRILL THRU", "PinPosDia": "DRILL THRU"}


def _configure_views(adapter: Any, views: tuple[Any, ...]) -> None:
    """Point every view at the saved default configuration and read it back."""
    bound_views = tuple(_early_bound(view, "IView") for view in views)
    for view in bound_views:
        view.ReferencedConfiguration = DEFAULT_CONFIG
    rebuild_drawing(adapter, label=f"{DEFAULT_CONFIG} view configuration")
    for view in bound_views:
        observed = str(view.ReferencedConfiguration)
        if observed != DEFAULT_CONFIG:
            raise RuntimeError(
                f"view configuration readback {observed!r} != {DEFAULT_CONFIG!r}"
            )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-removable source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Removable Chain Sprocket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "removable ANSI #25 sprocket; T12 / T18 / T24; steel plate",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    _configure_views(adapter, (front, top, iso))
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="edge",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the two bands are authored on the part; the sheet only proves the
    # import kept the places.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the sprocket face view")

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_XY, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_XY, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Removable Chain Sprocket Manufacturing Drawing",
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
