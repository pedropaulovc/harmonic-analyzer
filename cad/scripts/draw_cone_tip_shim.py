r"""Create the machinist drawing for the MHA-141 cone tip shim pack.

One plan view carries the whole blank at 3:1: the 15.0 x 31.3 outline
(I31: the pack runs under the tip block's foot flange), the horseshoe slot's
width with its full-radius callout, and the radius centre located from the
+X edge and the lower (north) edge (policy rule 7: a location
starts on a face the shop can pick up, never the model origin).  An edge
view below it carries the thickness dimension, which reads the stack-to-fit
range around the model's nominal ("0.05–2.20 STACK (1.10 NOM)"): the fitted
thickness is set at assembly, not machined, and rule 6 keeps the range out
of a note.  The leaf stock is the material specification; the one general
note points at the MHA-A03 step that fits the pack.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_tip_shim.py cone-tip-shim
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    offset_dimension_text,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_shim_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SHIM_NORTH_Z,
    SHIM_SOUTH_Z,
    SHIM_T,
    SHIM_X,
    SHIM_Z,
    SLOT_CENTRE_Z,
    SLOT_OPEN_EDGE,
    THICKNESS_TEXT_PREFIX,
    THICKNESS_TEXT_SUFFIX,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["cone_tip_shim"]
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

# I31: 31.3 long, the plan no longer fits over the edge view at 4:1.
SHEET_SCALE = (3.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0
# Third-angle: the plan (Top) above the edge view (Front).
TOP_CENTER = (0.120, 0.170)
FRONT_CENTER = (TOP_CENTER[0], 0.100)
ISO_CENTER = (0.320, 0.180)
HALF_X = SHIM_X * _S / 2.0  # 0.0225 on the sheet
HALF_Z = SHIM_Z * _S / 2.0  # 0.0469 on the sheet
# The view centres on the plan's box; the *Top view shows model +Z (north,
# the heel-trimmed edge) at the bottom and the south (open) edge at the top.
_MID_Z = (SHIM_NORTH_Z + SHIM_SOUTH_Z) / 2.0


def plan_y(model_z: float) -> float:
    """Sheet y of a block-frame station on the plan."""
    return TOP_CENTER[1] - (model_z - _MID_Z) * _S


SLOT_CENTRE_Y = plan_y(SLOT_CENTRE_Z)
PLAN_TOP = plan_y(SHIM_SOUTH_Z)
PLAN_BOTTOM = plan_y(SHIM_NORTH_Z)

if SLOT_OPEN_EDGE != "south":
    raise ValueError("the plan layout assumes the slot opens to the south edge")

# Larger dimensions stand outside smaller ones: the 31.3 depth outboard of
# the 13.2 radius-centre location on the right; the 15.0 width above the
# slot's width at the open (top) edge.
TOP_KEEP = {
    "Width": (TOP_CENTER[0], PLAN_TOP + 0.020),
    "Depth": (TOP_CENTER[0] + HALF_X + 0.024, TOP_CENTER[1]),
    # Past the open mouth, above the top edge.
    "SlotWidth": (TOP_CENTER[0], PLAN_TOP + 0.008),
    # The radius centre from the +X (right) edge and the lower (north)
    # edge, model-owned (the part's hidden reference sketches).  Each value
    # sits midway along its span, off both witnesses (the tip block's
    # 5637ac42 lesson).
    "SlotCentreX": (TOP_CENTER[0] + HALF_X / 2.0, PLAN_BOTTOM - 0.012),
    "SlotCentreZ": (
        TOP_CENTER[0] + HALF_X + 0.010,
        (SLOT_CENTRE_Y + PLAN_BOTTOM) / 2.0,
    ),
}
FRONT_KEEP = {"Thickness": (TOP_CENTER[0] + HALF_X + 0.016, FRONT_CENTER[1])}
# The 1.10 span is 4.4 mm on the sheet, so its value cannot sit between the
# arrows: r1 printed it across its own dimension line.  Lead it out to the
# right and a little below.  The text is one line of ~26 characters (about
# 60 mm at the sheet's character height), positioned by its centre, so the
# centre stands far enough right that the left end clears the line.
THICKNESS_TEXT = (FRONT_KEEP["Thickness"][0] + 0.044, FRONT_CENTER[1] - 0.010)
DIMENSION_CALLOUTS = {"SlotWidth": "SLOT, FULL R"}

NOTES_XY = (0.190, 0.120)


def _set_stack_text(adapter: Any, annotations: list[Any]) -> None:
    """Wrap the imported thickness in the stack range: prefix + value + suffix.

    Rule 6 keeps the range out of a note, so it rides the dimension's own
    text.  Prefix and suffix, not a whole-text override: the value between
    them stays the model's dimension at its model-owned places, so the sheet
    cannot print a nominal the part does not carry.  The parentheses mark
    that nominal as reference; the range is the requirement.  Same native
    channel (``SetText`` prefix/suffix, read back) as
    ``_drawing_common.set_reference_dimension``.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != "Thickness":
            continue
        annotation = _early_bound(annotation, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - SHIM_T / 1000.0) > 1e-9:
            raise RuntimeError(
                f"stack thickness nominal {float(dimension.SystemValue)!r} m "
                f"is not the modelled {SHIM_T} mm"
            )
        display.SetText(1, THICKNESS_TEXT_PREFIX)  # swDimensionTextPrefix
        display.SetText(2, THICKNESS_TEXT_SUFFIX)  # swDimensionTextSuffix
        readback = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if readback != (THICKNESS_TEXT_PREFIX, THICKNESS_TEXT_SUFFIX):
            raise RuntimeError(f"stack thickness text did not persist: {readback!r}")
        rebuild_drawing(adapter, label="stack thickness text")
        return
    raise RuntimeError("stack edge view has no Thickness dimension to label")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-shim source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Shim Pack Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip shim pack; fit-up stack; shim stock",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (top, front, iso):
        set_hidden_lines_removed(adapter, view)

    # The plan imports the part-hidden SlotCentre reference sketches, so it
    # takes the opt-in curation that shows them in this view only.
    top_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="stack edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*top_annotations, *front_annotations]
    _set_stack_text(adapter, front_annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    offset_dimension_text(adapter, front_annotations, {"Thickness": THICKNESS_TEXT})
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    for view in (top, front):
        set_hidden_lines_removed(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Shim Pack Manufacturing Drawing",
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
