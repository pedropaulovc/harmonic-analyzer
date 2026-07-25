r"""Create the curated machinist drawing for the cone platform lock knob."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    auto_center_marks,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_lock_knob_spec import (
    BODY_DIA,
    BODY_TOP,
    DOME_R as DOME_R,
    STUD_DIA,
    STUD_LEN,
    STUD_THREAD,
    WASHER_DIA,
    WASHER_T,  # noqa: F401 - drawing contract re-export
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_lock_knob"]
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

SHEET_SCALE = (3.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

FRONT_CENTER = (0.075, 0.150)
TOP_CENTER = (0.075, 0.235)
ISO_CENTER = (0.195, 0.190)

# The front view centres on the part bounding box (dome apex at BODY_TOP,
# stud end at -STUD_LEN below the washer seat / model origin), so a model
# height y projects on-sheet at FRONT_CENTER[1] + (y - _MID_Y) * _S.
_MID_Y = (BODY_TOP - STUD_LEN) / 2.0

# Measured with a one-off edge probe (2026-07-15): the placed view's washer
# seat silhouette sits 0.725 mm (sheet) BELOW the bbox-midpoint prediction
# (probe hits at y=0.13855/0.14305 -- their 4.5 mm gap is exactly
# WasherT * 3, so the scale is right and the whole map is shifted).  Edge
# picks tolerate only ~0.3 mm, so the map carries the measured offset.
_FRONT_Y_OFFSET = -0.000725


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - _MID_Y) * _S + _FRONT_Y_OFFSET


FRONT_KEEP = (
    "WasherT",
    "BodyTop",
    "StudLen",
    "DomeR",
)
TOP_KEEP = (
    "WasherDia",
    "BodyDia",
    "StudDia",
)
DIMENSION_CALLOUTS = {
    "StudDia": f"{STUD_THREAD} UNC-2A",
    "WasherT": "+/-0.10",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-lock-knob source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Lock Knob Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone lock knob; turned thumb knob; chromed steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(3, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(3, 1))

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    annotations = [*front_annotations, *top_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, top, holes=True):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Every GD&T anchor is a REAL model edge seen edge-on or as a circle (a
    # face boundary).  A cylinder's side outline is an HLR silhouette, not a
    # model edge, so it is NOT selectable via SelectByID2("EDGE", ...).
    #
    # Datum A is the turned AXIS (from the body OD circle in the top view,
    # the fulcrum-shaft/lever-bushing convention); the clamp seat is held
    # perpendicular to it and the washer OD holds runout to it, so the
    # thread line, body and flange are tied to one inspectable axis.
    seat_y = _front_y(0.0)
    seat_half_x = (STUD_DIA / 2.0 + WASHER_DIA / 2.0) / 2.0 * _S
    seat_right = (FRONT_CENTER[0] + seat_half_x, seat_y)
    crown_flat = (FRONT_CENTER[0], _front_y(BODY_TOP))
    _diag = 2.0**-0.5
    body_circle = (
        TOP_CENTER[0] + BODY_DIA * _S / 2.0 * _diag,
        TOP_CENTER[1] + BODY_DIA * _S / 2.0 * _diag,
    )
    washer_circle = (
        TOP_CENTER[0] + WASHER_DIA * _S / 2.0,
        TOP_CENTER[1],
    )
    # Both top-view symbols sit RIGHT of the view, not above it: the washer OD
    # is 18 at 3:1, so the top view already reaches y=0.262 against the zone
    # margin at 0.2667 and nothing clears above it.  (Their old +0.014/+0.024
    # offsets stacked on the 45-deg body-circle anchor put them at y=0.2628 and
    # 0.259, whose 8 mm half-boxes overran the top border by 4.1 and 0.3 mm.)
    #
    # STALE ARITHMETIC, placement still good: the "8 mm half-box" was the audit's
    # old model, so those two top-border overruns were false alarms -- an FCF's
    # anchor is its frame's TOP-LEFT corner and a datum tag's is its box top, so
    # neither reaches more than ~0.1 mm above its anchor. Kept as-is: the Y bands
    # below are what keep these three annotations off each other, which is a real
    # constraint independent of the box model. The side that under-read was the
    # RIGHT (a frame grows right by its full 20-30 mm width).
    #
    # The right side carries THREE annotations, so each gets its own Y band:
    # datum A at 0.255, this frame at 0.238, and the StudDia callout, whose
    # drawn text occupies x=0.111..0.145 / y=0.218..0.228.  None of that is
    # mechanically checked -- GD&T and dims both carry CollisionScope.NONE, so
    # a frame printed straight through a callout (which 0.228 did) is invisible
    # to the audit and only shows up on the render.
    # SolidWorks restricts this circular-axis tag and live readback normalizes
    # the requested sheet point by 3.335 mm.  Bound that annotation placement
    # behavior without changing any part dimension or geometric tolerance.
    add_datum_feature(
        adapter,
        top,
        edge_xy=body_circle,
        symbol_xy=(0.128, 0.255),
        datum="A",
        label="knob body axis",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=washer_circle,
        frame_xy=(0.140, 0.238),
        characteristic="circular_runout",
        tolerance="0.10",
        datums=("A",),
        label="washer flange runout",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=seat_right,
        frame_xy=(seat_right[0] + 0.026, seat_y - 0.020),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="clamp seat perpendicularity",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=crown_flat,
        symbol_xy=(crown_flat[0] + 0.024, crown_flat[1] + 0.012),
        roughness_ra="1.6",
        label="dome crown finish",
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.100)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Lock Knob Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
