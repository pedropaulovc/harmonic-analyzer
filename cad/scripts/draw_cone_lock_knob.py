r"""Create the curated machinist drawing for the cone platform lock knob."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_lock_knob_spec import (
    BODY_DIA,
    BODY_TOP,
    DOME_R,
    STUD_DIA,
    STUD_LEN,
    STUD_THREAD,
    WASHER_DIA,
    WASHER_T,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
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


FRONT_KEEP = {
    "WasherT": (
        FRONT_CENTER[0] + WASHER_DIA * _S / 2.0 + 0.028,
        _front_y(WASHER_T / 2.0),
    ),
    "BodyTop": (
        FRONT_CENTER[0] - WASHER_DIA * _S / 2.0 - 0.024,
        _front_y(BODY_TOP / 2.0),
    ),
    "StudLen": (
        FRONT_CENTER[0] - WASHER_DIA * _S / 2.0 - 0.024,
        _front_y(-STUD_LEN / 2.0),
    ),
    "DomeR": (
        FRONT_CENTER[0] + BODY_DIA * _S / 2.0 + 0.026,
        _front_y(BODY_TOP) + 0.012,
    ),
}
TOP_KEEP = {
    "WasherDia": (
        TOP_CENTER[0] - WASHER_DIA * _S / 2.0 - 0.030,
        TOP_CENTER[1] - 0.016,
    ),
    "BodyDia": (
        TOP_CENTER[0] - WASHER_DIA * _S / 2.0 - 0.030,
        TOP_CENTER[1] + 0.018,
    ),
    "StudDia": (
        TOP_CENTER[0] + WASHER_DIA * _S / 2.0 + 0.026,
        TOP_CENTER[1] - 0.012,
    ),
}
DIMENSION_CALLOUTS = {
    "StudDia": f"{STUD_THREAD} UNC-2A",
    "WasherT": "+/-0.10",
}


def _outline_center(adapter: Any, view: Any) -> tuple[float, float]:
    """A view's actual on-sheet geometry center, read from its outline.

    ``CreateDrawViewFromModelView3`` documents its LocX/LocY as the view
    center, but the achieved center can differ from the requested one (the
    proven failure: every model-mapped edge pick missing by one constant
    offset).  The outline pads the geometry with a uniform whitespace margin,
    so its midpoint IS the geometry center; measuring it and shifting every
    pick keeps the recipe correct whatever the placement anchored.
    """
    x0, y0, x1, y1 = (
        float(v) for v in adapter._get_attr_or_call(view, "GetOutline")
    )
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _shifted(
    positions: dict[str, tuple[float, float]], delta: tuple[float, float]
) -> dict[str, tuple[float, float]]:
    return {
        name: (x + delta[0], y + delta[1])
        for name, (x, y) in positions.items()
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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(3, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, top)

    # Measured before any annotation lands (dims would grow the outline).
    front_center = _outline_center(adapter, front)
    top_center = _outline_center(adapter, top)
    front_delta = (
        front_center[0] - FRONT_CENTER[0],
        front_center[1] - FRONT_CENTER[1],
    )
    top_delta = (top_center[0] - TOP_CENTER[0], top_center[1] - TOP_CENTER[1])
    _telemetry.info(
        f"view-center deltas: front=({front_delta[0]:.4f}, {front_delta[1]:.4f}) "
        f"top=({top_delta[0]:.4f}, {top_delta[1]:.4f})"
    )

    front_annotations = curate_view_dimensions(
        adapter, front, keep=_shifted(FRONT_KEEP, front_delta), view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=_shifted(TOP_KEEP, top_delta), view_label="top"
    )
    annotations = [*front_annotations, *top_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Every GD&T anchor is a REAL model edge seen edge-on (a face boundary
    # projecting to a line).  A cylinder's side outline is an HLR silhouette,
    # not a model edge, so it is NOT selectable via SelectByID2("EDGE", ...).
    fdx, fdy = front_delta
    seat_y = _front_y(0.0) + fdy
    seat_half_x = (STUD_DIA / 2.0 + WASHER_DIA / 2.0) / 2.0 * _S
    seat_right = (FRONT_CENTER[0] + fdx + seat_half_x, seat_y)
    seat_left = (FRONT_CENTER[0] + fdx - seat_half_x, seat_y)
    stud_end = (FRONT_CENTER[0] + fdx, _front_y(-STUD_LEN) + fdy)
    crown_flat = (FRONT_CENTER[0] + fdx, _front_y(BODY_TOP) + fdy)
    add_datum_feature(
        adapter,
        front,
        edge_xy=seat_right,
        symbol_xy=(seat_right[0] + 0.012, seat_y - 0.014),
        datum="A",
        label="washer clamp seat",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=stud_end,
        frame_xy=(FRONT_CENTER[0] + fdx + 0.045, stud_end[1] - 0.010),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="clamp stud perpendicularity",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=seat_left,
        symbol_xy=(seat_left[0] - 0.028, seat_y - 0.038),
        roughness_ra="3.2",
        label="washer clamp seat finish",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=crown_flat,
        symbol_xy=(crown_flat[0] + 0.024, crown_flat[1] + 0.012),
        roughness_ra="1.6",
        label="dome crown finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.100)
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
