r"""Create the drawing for MHA-CH-13-TL-02, the rocker strap's hub plug.

Shop tooling (the rocker-strap sub-plate fixture MHA-CH-13-TL-00). The PART
owns the print (``ch_rocker_strap_tl_hub_plug_spec``): places, the pilot's
limits, the body Ø's reference brackets and every callout; this recipe
places the marked dimensions and proves the import kept them.

At 4:1 (the arbor collar's recipe, ``draw_dt_cone_gear_tl_arbor_collar``):

* the END VIEW (``*Front``, looking down on the pilot's top) keeps the bore
  with its DRILL THRU callout and stated wall;
* the SIDE VIEW (``*Right``, model +Z to the left, so the pilot stands left
  of the body as on the lathe; rule 11) carries both diameters, moved from
  the end view where every diameter crosses the centre: the pilot's limits
  above it with its fit, the body's reference Ø right of it with its matched
  clearance on MHA-CH-13-TL-01; the body and overall lengths under it and
  the pilot's chamfer below-left;
* the isometric at 2:1 with its scale note.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_strap_tl_hub_plug.py ch-rocker-strap-tl-hub-plug
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
import ch_rocker_strap_tl_hub_plug_spec as spec
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

SPEC = DRAWINGS_BY_NAME["ch_rocker_strap_tl_hub_plug"]
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
END_CENTER = (0.065, 0.190)
SIDE_CENTER = (0.165, 0.190)
ISO_CENTER = (0.370, 0.140)
ISO_NOTE_XY = (0.335, 0.105)
BODY_HALF = spec.BODY_DIA / 2.0 * _S
PILOT_HALF = spec.PILOT_DIA / 2.0 * _S
HALF_LENGTH = spec.OVERALL_LENGTH / 2.0 * _S


def side_x(model_z: float) -> float:
    """Sheet x of model z on the side view, which centres the plug's box
    (z 0..OVERALL_LENGTH) and lays model +Z to the left."""
    return SIDE_CENTER[0] - (model_z - spec.OVERALL_LENGTH / 2.0) * _S


BOTTOM_X = side_x(0.0)  # the body's bottom face, the view's right edge
TOP_X = side_x(spec.OVERALL_LENGTH)  # the pilot's top, its left edge
PILOT_MID_X = side_x((spec.BODY_LENGTH + spec.OVERALL_LENGTH) / 2.0)
BODY_MID_X = side_x(spec.BODY_LENGTH / 2.0)

# The end view keeps the bore, its two rows up and right of the circles; the
# two diameters import there too and are parked below it until they move.
END_KEEP = {
    "BoreDia": (END_CENTER[0] + BODY_HALF + 0.010, END_CENTER[1] + BODY_HALF + 0.012),
    "BodyDia": (END_CENTER[0] - 0.020, END_CENTER[1] - BODY_HALF - 0.012),
    "PilotDia": (END_CENTER[0] + 0.020, END_CENTER[1] - BODY_HALF - 0.012),
}
# The side view: both lengths stacked under the plug (the body length
# nearer), the chamfer's leg below-left of the pilot's top corner.
SIDE_KEEP = {
    "BodyLength": (BODY_MID_X, SIDE_CENTER[1] - BODY_HALF - 0.012),
    "OverallLength": (SIDE_CENTER[0], SIDE_CENTER[1] - BODY_HALF - 0.026),
    "ChamferSize": (TOP_X - 0.018, SIDE_CENTER[1] - PILOT_HALF - 0.010),
}
# The moved diameters: the pilot's three-row block (two limits, fit, REF
# clearance) above the plug clear of the body's top, the body's three-row
# block right of the body's bottom face.
PILOT_ON_SIDE = (PILOT_MID_X, SIDE_CENTER[1] + BODY_HALF + 0.030)
BODY_ON_SIDE = (BOTTOM_X + 0.015, SIDE_CENTER[1])
MOVED = {"BodyDia": BODY_ON_SIDE, "PilotDia": PILOT_ON_SIDE}
if set(END_KEEP) | set(SIDE_KEEP) != set().union(*spec.DRAWING_DIMENSIONS.values()):
    raise AssertionError("the hub plug sheet does not place every marked dimension")
if set(MOVED) | set(SIDE_KEEP) | {"BoreDia"} != set(spec.DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every hub plug dimension ends on exactly one view")


def _assert_part_text(adapter: Any, annotations: list[Any]) -> None:
    """The part authors every callout below its value and the body Ø's
    reference brackets; the import must carry each unchanged (the drawing
    never writes them, #1942)."""
    # swDimensionTextPrefix 1, Suffix 2, CalloutBelow 4.
    expected = {
        (4, name): text for name, text in spec.DIMENSION_CALLOUTS_BY_NAME.items()
    }
    for names in spec.REFERENCE_DIMENSIONS.values():
        for name in names:
            expected[(1, name)] = "(<MOD-DIAM>"
            expected[(2, name)] = ")"
    found: dict[tuple[int, str], str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        slots = [slot for slot, expected_name in expected if expected_name == name]
        if not slots:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        for slot in slots:
            found[(slot, name)] = str(display.GetText(slot) or "").replace("\r\n", "\n")
    if found != expected:
        raise RuntimeError(
            f"hub plug dimension text did not import: {found!r} != {expected!r}"
        )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub plug source", adapter.open_model(str(SOURCE)))
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
            0: "Rocker Strap Hub Plug Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: f"rocker strap hub plug; turned; {spec.PART_NUMBER}",
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
    moved = []
    for name, text_xy in MOVED.items():
        donors = [a for a in end_annotations if dimension_name(adapter, a) == name]
        if len(donors) != 1:
            raise RuntimeError(f"expected one {name} donor dimension on the end view")
        moved.append(
            move_model_dimension(adapter, donors[0], side, text_xy, source_view=end)
        )
    annotations = [
        *(a for a in end_annotations if dimension_name(adapter, a) not in MOVED),
        *side_annotations,
        *moved,
    ]
    # Places (and so each dimension's title-block row) are the part's; the
    # sheet only proves the import kept them, and its text.
    assert_imported_precision(adapter, annotations, spec.DRAWING_PRECISION_BY_NAME)
    _assert_part_text(adapter, annotations)
    # The side view's axis (the template centre-marks the end view's circles
    # as the view is placed, draw_mg_wheel_drum).
    add_view_centerline(
        adapter,
        side,
        face_xy=(BODY_MID_X, SIDE_CENTER[1] + BODY_HALF / 2.0),
        label="hub plug axis centerline",
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Strap Hub Plug Drawing",
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
