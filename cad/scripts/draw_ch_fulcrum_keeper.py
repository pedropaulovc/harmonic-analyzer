r"""Create the curated machinist drawing for the fulcrum-shaft end keeper.

The SLDPRT remains authoritative.  This recipe supplies only the keeper's
views, dimension layout, hole callout, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the bracket is ~16.5 x 32.2 x 14); the isometric
carries an explicit 1:1 override so it stays clear of the title block.  Four
views: the side profile (front), the plan (top, which carries the foot
screw's stations and the counterbored screw-hole and crown set-screw tap
callouts), the end view (right, which carries the width / shaft-axis-height /
crown / bore stack), and the isometric.  A bracket carries no frames and no
datums (drawing-simplicity-policy.md): every location is a plain coordinate
dimension off a named face.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_fulcrum_keeper.py ch-fulcrum-keeper
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
import ch_channel_assembly_steps as steps
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from ch_fulcrum_keeper_spec import (
    BORE_PAIR_CALLOUT,
    CBORE_DIA_MM,
    CROWN_ABOUT_BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    FOOT_TIP_X,
    LUG_HALF_T,
    SCREW_FROM_SIDE,
    SCREW_X,
    SET_SCREW_HOLE_SPEC,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["ch_fulcrum_keeper"]
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
# X -3..+13.5 (lug inner face to foot tip) by Y 0..32.2; at 2:1 that is
# ~33 x 64.4 mm.  Third angle: the plan (top view) rides above the front,
# the end view (right) sits to its right, the isometric top-right.
FRONT_CENTER = (0.110, 0.130)
TOP_CENTER = (0.110, 0.228)
RIGHT_CENTER = (0.225, 0.130)
ISO_CENTER = (0.330, 0.190)

# Model bbox centre the projected views are laid out around (front and plan
# share model X).
_X_MID = (-LUG_HALF_T + FOOT_TIP_X) / 2.0  # 5.25


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - _X_MID) * SHEET_SCALE[0] / 1000.0


# Handy picks derived from the layout above.
HOLE_X_SHEET = _front_x(SCREW_X)  # screw-hole station, shared by the top view
CBORE_R_SHEET = CBORE_DIA_MM * SHEET_SCALE[0] / 2000.0
# The crown tap seen end-on in the plan, on the lug mid-plane (x = 0).
TAP_X_SHEET = _front_x(0.0)
TAP_R_SHEET = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC) * SHEET_SCALE[0] / 2000.0
# The tap is cut at the bench; its mouth is staked over the seated set screw
# at the channel assembly (policy rule 9's lock, joint_retention), so the
# callout says so ahead of the native size row.
SET_SCREW_PROCESS = (
    f"TAP TO BORE; STAKE MOUTH 2 PLACES\n"
    f"AT ASSEMBLY PER {steps.step_ref(steps.SET_SCREWS_STAKED_KEY)}\n"
)
# The two keepers' bores are drilled and reamed together (one axis whatever
# LugRise prints) and each crown is then rounded about its own bore: bench
# instructions of the pair-ream step, so each rides its own dimension.
_PAIR_REAM_STEP = steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)
DIMENSION_CALLOUTS = {
    "BoreDia": f"{BORE_PAIR_CALLOUT},\nPER {_PAIR_REAM_STEP}",
    "CrownDia": f"{CROWN_ABOUT_BORE_CALLOUT},\nPER {_PAIR_REAM_STEP}",
}

# Per-view survivors of the marked-dimension import: parametric name ->
# sheet position.  The front view carries the lug thickness and the crown
# tap's station off the outer lug face (both stacked above the crown), the
# foot length below the seat and the foot height right of the foot tip; the
# plan carries the foot screw's station off the outer lug face (above the
# plan) and off the -Z side face (right of the foot tip); the end view
# carries the width plus the shaft-axis / crown stack and the reamed bore.
FRONT_KEEP = {
    "SetScrewLocation": (_front_x(1.5), 0.170),
    "LugThickness": (_front_x(0.0), 0.178),
    "FootLength": (_front_x(SCREW_X), 0.086),
    "FootRise": (0.140, 0.106),
}
# The plan projects model -Z to sheet UP, so the -Z side face is the
# plan's top edge, SCREW_FROM_SIDE above the screw axis.
TOP_KEEP = {
    "ScrewFromLug": (_front_x((LUG_HALF_T + SCREW_X) / 2.0), 0.252),
    "ScrewFromSide": (
        _front_x(FOOT_TIP_X) + 0.014,
        TOP_CENTER[1] + SCREW_FROM_SIDE * SHEET_SCALE[0] / 2000.0,
    ),
}
RIGHT_KEEP = {
    "Depth": (0.225, 0.172),
    "LugRise": (0.196, 0.126),
    "CrownDia": (0.225, 0.180),
    "BoreDia": (0.258, 0.156),
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    for view in (front, top, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The tap and foot-screw stations are owned by reference sketches the
    # part saves blanked (ch_fulcrum_keeper_spec.REFERENCE_SKETCHES); the
    # hidden-owner curate shows each in the view that dimensions it.
    curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, right_annotations, DIMENSION_CALLOUTS)

    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Counterbored screw hole ships as the native wizard callout on the plan
    # view, where it projects as its true circles.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(HOLE_X_SHEET, TOP_CENTER[1] + CBORE_R_SHEET),
        callout_xy=(0.040, 0.238),
        label="keeper foot screw hole",
    )
    # Crown set-screw tap: the plan sees it end-on at the crown top on the
    # lug mid-plane; its callout sits in the band between the front view
    # and the plan, left of both.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TAP_X_SHEET - TAP_R_SHEET, TOP_CENTER[1]),
        callout_xy=(0.050, 0.200),
        label="crown set-screw tap",
        process=SET_SCREW_PROCESS,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.062)
    add_property_linked_note(adapter, "Isometric View Note", 0.310, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Keeper Manufacturing Drawing",
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
