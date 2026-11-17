r"""Create the drawing for MHA-CH-13-TL-03, the rocker strap's hub washer.

Shop tooling (the rocker-strap sub-plate fixture MHA-CH-13-TL-00). The PART
owns the print (``ch_rocker_strap_tl_hub_washer_spec``): places and the
bore's callout; this recipe places the marked dimensions and proves the
import kept them.

At 4:1 (the arbor collar's recipe, ``draw_dt_cone_gear_tl_arbor_collar``):
the END VIEW (``*Front``) keeps the drilled bore; the outside diameter, which
imports there too, moves onto the SIDE VIEW (``*Right``) right of the washer,
where a turned part's diameter reads beside its thickness (rule 11); the
thickness stands over the side view. Every size takes the title block's band
(OD and thickness .XX, the bore DRILLED HOLES). The isometric at 2:1 with
its scale note.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_strap_tl_hub_washer.py ch-rocker-strap-tl-hub-washer
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
import ch_rocker_strap_tl_hub_washer_spec as spec
from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, move_model_dimension
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build

MACHINIST_REVIEW = MachinistReviewMode.LEARN

SPEC = DRAWINGS_BY_NAME["ch_rocker_strap_tl_hub_washer"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = spec.ISOMETRIC_VIEW_SCALE
if tuple(ISO_SCALE) == VIEW_SCALE:
    raise AssertionError("the isometric's label would repeat the sheet scale")
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm
END_CENTER = (0.070, 0.175)
SIDE_CENTER = (0.170, 0.175)
ISO_CENTER = (0.320, 0.175)
ISO_NOTE_XY = (0.290, 0.130)
HALF_OD = spec.OUTER_DIA / 2.0 * _S
HALF_THICKNESS = spec.THICKNESS / 2.0 * _S

# The bore keeps the end view, its callout up and right of the circles; the
# outside diameter is a donor there, parked below until it moves.
END_KEEP = {
    "BoreDia": (END_CENTER[0] + HALF_OD + 0.010, END_CENTER[1] + HALF_OD + 0.010),
    "OuterDia": (END_CENTER[0], END_CENTER[1] - HALF_OD - 0.012),
}
SIDE_KEEP = {
    "Thickness": (SIDE_CENTER[0], SIDE_CENTER[1] + HALF_OD + 0.012),
}
OD_ON_SIDE = (SIDE_CENTER[0] + HALF_THICKNESS + 0.018, SIDE_CENTER[1])
if set(END_KEEP) | set(SIDE_KEEP) != set().union(*spec.DRAWING_DIMENSIONS.values()):
    raise AssertionError("the hub washer sheet does not place every marked dimension")


def _assert_part_callouts(adapter: Any, annotations: list[Any]) -> None:
    """The part authors the bore's callout below its value; the import must
    carry it unchanged (the drawing never writes it, #1942)."""
    # swDimensionTextCalloutBelow = 4.
    found: dict[str, str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in spec.DIMENSION_CALLOUTS_BY_NAME:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        found[name] = str(display.GetText(4) or "").replace("\r\n", "\n")
    if found != spec.DIMENSION_CALLOUTS_BY_NAME:
        raise RuntimeError(
            f"hub washer callouts did not import: {found!r} != "
            f"{spec.DIMENSION_CALLOUTS_BY_NAME!r}"
        )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub washer source", adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity")
    read_required_properties(
        adapter.currentModel,
        ("Revision", "Title", *required, "Isometric View Note"),
        required=(*required, "Isometric View Note"),
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
            0: "Rocker Strap Hub Washer Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: f"rocker strap hub washer; turned; {spec.PART_NUMBER}",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # A turned part needs no hidden lines (drawing-guidelines.md rule 9).
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    od_donors = [a for a in end_annotations if dimension_name(adapter, a) == "OuterDia"]
    if len(od_donors) != 1:
        raise RuntimeError("expected one OuterDia donor dimension on the end view")
    moved_od = move_model_dimension(
        adapter, od_donors[0], side, OD_ON_SIDE, source_view=end
    )
    annotations = [
        *(a for a in end_annotations if dimension_name(adapter, a) != "OuterDia"),
        *side_annotations,
        moved_od,
    ]
    assert_imported_precision(adapter, annotations, spec.DRAWING_PRECISION_BY_NAME)
    _assert_part_callouts(adapter, annotations)
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0], SIDE_CENTER[1] + HALF_OD / 2.0),
        label="hub washer axis centerline",
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Strap Hub Washer Drawing",
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
