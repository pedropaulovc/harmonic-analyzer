r"""Create the curated machinist drawing for the channel-spring plate hook.

A small formed-wire open J-hook.  The print shows a 5:1 front (profile) view, a
5:1 top view for the wire diameter and the overall width, and a 5:1 isometric.
Shared behavior lives in ``_drawing_common``.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
hanging hook carries no datums, no feature-control frames and no roughness
symbols -- its shank SEATS in the plate bore, nothing runs on it.

What the machinist checks is the formed ENVELOPE (machinist review
2026-09-02): the overall height (shank end to the arm's top) is a sheet
dimension on the front view, the overall width (shank flank to the arm tip) a
sheet dimension on the top view; the tangent-length rise and arm run are kept
as REFERENCE values.  The elbow angle is the model's driven ``ElbowAngle``
(carrying its loose forming band) and the bend radius is flagged from the
elbow's outer arc.

Run with SolidWorks open::

    uv run python cad\scripts\draw_spring_hook.py spring-hook
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view
from spring_hook_notes import ELBOW_CALLOUT
from spring_hook_spec import (
    ARM_HEIGHT,
    ARM_RUN,
    ARM_TIP_X,
    ELBOW_R,
    ROD_DIA,
    SHANK_RISE,
)


SPEC = DRAWINGS_BY_NAME["spring_hook"]
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

SHEET_SCALE = (5.0, 1.0)  # 5:1
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (5.0)

# Front-view model bbox (X-Y), wire radius included: the shank's left flank to
# the arm tip, the flat shank end to the arm's top silhouette.
_BBOX_X = (-ROD_DIA / 2.0, ARM_TIP_X)
_BBOX_Y = (0.0, ARM_HEIGHT + ROD_DIA / 2.0)
_BBOX_CX = (_BBOX_X[0] + _BBOX_X[1]) / 2.0
_BBOX_CY = (_BBOX_Y[0] + _BBOX_Y[1]) / 2.0
OVERALL_HEIGHT = _BBOX_Y[1]  # 9.80
OVERALL_WIDTH = _BBOX_X[1] - _BBOX_X[0]  # 4.70

FRONT_CENTER = (0.110, 0.150)
TOP_CENTER = (0.210, 0.150)
ISO_CENTER = (0.300, 0.150)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (5:1)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


def _top_xy(mx: float, mz: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Z) point in the top view (5:1).

    The wire is symmetric about Z = 0, so the view's Z mirror cannot matter.
    """
    return (
        TOP_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        TOP_CENTER[1] + mz * _S / 1000.0,
    )


# Front view: the (REF) rise on the left, the (REF) arm run above the arm, the
# elbow angle inside the L (its text sets the arc radius about the shank/arm
# axis intersection; 6.8 mm out keeps the arc clear of the arm's end).
FRONT_KEEP = {
    "Rise": (0.078, _sheet_xy(0.0, SHANK_RISE / 2.0)[1]),
    "ArmRun": (_sheet_xy(ELBOW_R + ARM_RUN / 2.0, 0.0)[0], 0.192),
    "ElbowAngle": _sheet_xy(3.0, 3.0),
}
TOP_KEEP = {
    "RodDia": (0.210, 0.110),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
REFERENCE_DIMENSIONS = ("Rise", "ArmRun")

# Overall height: the flat shank end (an edge-on circular EDGE) up to the arm's
# top SILHOUETTE, dimension line right of the hook.
HEIGHT_END_XY = _sheet_xy(0.0, 0.0)
HEIGHT_ARM_TOP_XY = _sheet_xy(ELBOW_R + ARM_RUN / 2.0, OVERALL_HEIGHT)
HEIGHT_TEXT_XY = (0.150, _sheet_xy(0.0, OVERALL_HEIGHT / 2.0)[1])
# Overall width on the top view: the shank's wire circle (its left half is
# visible beside the elbow) out to the arm tip's end face, arc condition MAX so
# the value runs to the flank, not the shank axis.
WIDTH_SHANK_XY = _top_xy(-ROD_DIA / 2.0, 0.0)
WIDTH_TIP_XY = _top_xy(ARM_TIP_X, 0.0)
WIDTH_TEXT_XY = (_top_xy(_BBOX_CX, 0.0)[0], 0.172)

# The elbow's OUTER arc (centre (ElbowR, ShankRise), radius ElbowR + wire
# radius) at its 135-degree point: the torus silhouette the bend callout lands
# on, away from both tangent points.  The note sits top-left of the hook, so
# its leader clears the rise dimension and the arm-run extension lines.
_OUTER_ELBOW_R = ELBOW_R + ROD_DIA / 2.0
OUTER_ELBOW_XY = _sheet_xy(
    ELBOW_R - _OUTER_ELBOW_R * math.cos(math.radians(45.0)),
    SHANK_RISE + _OUTER_ELBOW_R * math.sin(math.radians(45.0)),
)
ELBOW_NOTE_XY = (0.050, 0.205)


def _reference_dimensions(
    adapter: Any, annotations: list[Any], names: tuple[str, ...]
) -> None:
    """Parenthesize the named LINEAR dimensions (no diameter glyph)."""
    remaining = set(names)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        set_reference_dimension(adapter, annotation, label=f"{name} reference")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"reference dimensions not found: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open spring-hook source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Spring Hook Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "spring hook; formed wire; plate hook",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(5, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(5, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(5, 1))
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    # The tangent lengths are forming inputs, not what gets inspected: the
    # overalls below are the controlling envelope.
    _reference_dimensions(adapter, front_annotations, REFERENCE_DIMENSIONS)

    add_edge_dimension(
        adapter,
        front,
        p0=HEIGHT_END_XY,
        p1=HEIGHT_ARM_TOP_XY,
        text_xy=HEIGHT_TEXT_XY,
        label="overall height",
        orientation="vertical",
        entity_types=("EDGE", "SILHOUETTE"),
    )
    width = add_edge_dimension(
        adapter,
        top,
        p0=WIDTH_SHANK_XY,
        p1=WIDTH_TIP_XY,
        text_xy=WIDTH_TEXT_XY,
        label="overall width",
        orientation="horizontal",
    )
    set_arc_endpoints_to_max(adapter, width, label="overall width")

    # Bend callout on the elbow's outer arc: the centreline radius, flagged
    # from the feature it governs (policy rule 6).
    add_attached_note(
        adapter,
        front,
        text=ELBOW_CALLOUT,
        entity_xy=OUTER_ELBOW_XY,
        note_xy=ELBOW_NOTE_XY,
        label="elbow radius callout",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.280, 0.100)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Spring Hook Manufacturing Drawing",
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
