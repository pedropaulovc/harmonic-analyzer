r"""Create the curated machinist drawing for the magnifying-lever bracket.

The bracket is the black fitting that affixes the Ø6 magnifying-lever rod to the
summing plate: a revolved COLLAR tube (Ø12 OD, Ø6.2 bore, 10 long about local X)
that the rod slips through, a rectangular ARM cantilevering +Z, and a mounting
FLANGE that butts the summing-plate front face.

Views and what each carries (cad/docs/drawing-simplicity-policy.md rule 7,
one origin per view -- the collar axis):

* TOP (plan): the marked arm/flange rectangles -- arm width, the arm's far end
  and the flange's far edge and far side from the collar axis, flange width
  and depth -- with the collar axis drawn as a centreline so the axis-based
  stations read against a line;
* FRONT: the marked collar length (labelled, since the arm is as wide as the
  collar is long), the collar OD across its silhouettes as a Ø, the arm's top
  face from the collar OD (the arm is NOT centred on the axis: y -3..+4.5)
  and the flange thickness on the flange's visible face;
* RIGHT (collar end): the bore as a Ø on its visible circle (with the ASME
  centre mark) and the arm thickness at the arm's free end.

The print is plain: a bracket is not on the GD&T allowlist and it is
lock-mated to the lever rod in service, so it carries no datum, frame,
roughness or basic dimension.

Run with SolidWorks open::

    uv run python cad\scripts\draw_magnifying_bracket.py magnifying-bracket
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from magnifying_bracket_spec import (
    ARM_HALF_X,
    ARM_Y,
    ARM_Z,
    COLLAR_BORE,
    COLLAR_HALF_LEN,
    COLLAR_OD,
    FLANGE_X,
    FLANGE_Y,
    FLANGE_Z,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["magnifying_bracket"]
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

SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
# Third angle: plan above the front view, the collar-end view beside the
# front view at its height (review 2026-09-02: it sat beside the plan).
TOP_CENTER = (0.115, 0.180)
FRONT_CENTER = (0.115, 0.110)
RIGHT_CENTER = (0.240, 0.110)
ISO_CENTER = (0.345, 0.160)

# Model bounding boxes (mm) the views are centred on.
_PLAN_CX = (FLANGE_X[0] + ARM_HALF_X) / 2.0  # -7.5
_PLAN_CZ = (-COLLAR_OD / 2.0 + ARM_Z[1]) / 2.0  # 26.15


def _tx(model_x_mm: float) -> float:
    return TOP_CENTER[0] + (model_x_mm - _PLAN_CX) * VIEW_SCALE / 1000.0


def _tz(model_z_mm: float) -> float:
    # Top view: model +Z (toward the front-view viewer) reads sheet-DOWN.
    return TOP_CENTER[1] - (model_z_mm - _PLAN_CZ) * VIEW_SCALE / 1000.0


def _fx(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - _PLAN_CX) * VIEW_SCALE / 1000.0


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + model_y_mm * VIEW_SCALE / 1000.0


# Top view: the arm width under the arm's far end (nearest lane) with the
# flange width outside it; the flange depth right of the arm; the two
# far-edge stations from the collar axis left of the flange (the flange's
# nearest, the arm's outside); the flange's far side from the axis above the
# collar.
TOP_KEEP = {
    "ArmWidth": (_tx(0.0), _tz(ARM_Z[1]) - 0.008),
    "FlangeWidth": (_tx((FLANGE_X[0] + FLANGE_X[1]) / 2.0), _tz(ARM_Z[1]) - 0.018),
    "FlangeDepth": (_tx(ARM_HALF_X) + 0.012, _tz((FLANGE_Z[0] + FLANGE_Z[1]) / 2.0)),
    "FlangeCornerZ": (_tx(FLANGE_X[0]) - 0.012, _tz(FLANGE_Z[1] / 2.0)),
    "ArmCornerZ": (_tx(FLANGE_X[0]) - 0.024, _tz(ARM_Z[1] / 2.0)),
    "FlangeCornerX": (_tx(FLANGE_X[0] / 2.0), _tz(-COLLAR_OD / 2.0) + 0.010),
}
# Front view: the collar length above the collar.
FRONT_KEEP = {
    "WallLen": (_fx(0.0), _fy(COLLAR_OD / 2.0) + 0.010),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
# The arm is exactly as wide as the collar is long (both 10), so the two
# values are labelled with the feature each controls.
TOP_CALLOUTS = {"ArmWidth": "ARM WIDTH"}
FRONT_CALLOUTS = {"WallLen": "COLLAR LENGTH"}
DIMENSION_CALLOUTS = {**TOP_CALLOUTS, **FRONT_CALLOUTS}

# Collar-axis centreline in the plan: the collar's cylindrical face picked
# ahead of the arm (the arm starts at z 4).
COLLAR_AXIS_FACE_XY = (_tx(0.0), _tz(-3.0))

_DIAMETER_DIMENSION = 6  # swDimensionType_e.swDiameterDimension

# Derived thicknesses the views carry (mm).
ARM_THICKNESS = ARM_Y[1] - ARM_Y[0]  # 7.5
FLANGE_THICKNESS = FLANGE_Y[1] - FLANGE_Y[0]  # 5.08
ARM_TOP_FROM_COLLAR_OD = COLLAR_OD / 2.0 - ARM_Y[1]  # 1.5


def _model_frame(adapter: Any, view: Any, *, scale: float, label: str):
    """Model-mm -> sheet projection for ``view`` plus the sheet unit vectors of
    model +X/+Y/+Z, read from the view's own transform so no sign is guessed.
    The projected length of a 10 mm model step is checked against ``scale``
    so a transform that omitted the view scale fails loud instead of
    mis-picking."""

    def at(x_mm: float, y_mm: float, z_mm: float) -> tuple[float, float]:
        return model_point_in_view(
            adapter, view, (x_mm / 1000.0, y_mm / 1000.0, z_mm / 1000.0),
            label=f"{label} pick",
        )

    origin = at(0.0, 0.0, 0.0)
    units: list[tuple[float, float]] = []
    for axis in ((10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 10.0)):
        point = at(*axis)
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        norm = math.hypot(dx, dy)
        if norm < 1e-6:  # the axis normal to the view
            units.append((0.0, 0.0))
            continue
        if abs(norm - 0.010 * scale) > 0.0002 * scale:
            raise RuntimeError(
                f"{label}: a 10 mm model step projects to {norm * 1000:.2f} mm on "
                f"the sheet; expected {10.0 * scale:.2f} mm at {scale:g}:1"
            )
        units.append((dx / norm, dy / norm))
    return at, tuple(units)


def _offset(
    point: tuple[float, float], direction: tuple[float, float], distance: float
) -> tuple[float, float]:
    return (point[0] + direction[0] * distance, point[1] + direction[1] * distance)


def _display_as_diameter(adapter: Any, dimension: Any, *, label: str) -> None:
    """Prefix a silhouette-to-silhouette width with the ASME diameter symbol."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "SetText", "GetText"
    )
    adapter._attempt(lambda: display.SetText(1, "<MOD-DIAM>"))  # swDimensionTextPrefix
    applied = str(adapter._attempt(lambda: display.GetText(1)) or "")
    if "<MOD-DIAM>" not in applied:
        raise RuntimeError(f"{label} dimension did not take the diameter prefix")
    adapter.currentModel.EditRebuild3()


def _add_circle_diameter(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Diameter-dimension one full circular edge picked at a sheet point.

    ``IModelDoc2.AddDiameterDimension2`` is the API's explicit diameter call
    (its radial sibling is sketch-only; the smart ``AddDimension2`` the fleet
    uses for an arc emits ``R<value>``).  The result is VERIFIED to be a
    diameter type -- a radius on a fitted bore would print half the size.
    Selecting the circle twice would DESELECT it (SelectByID2 with Append
    toggles an already-selected entity), so this is a one-pick primitive.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r} ({label})")
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        "", "EDGE", edge_xy[0], edge_xy[1], 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(
            f"failed to select {label} circle at sheet ({edge_xy[0]:g}, {edge_xy[1]:g})"
        )
    dimension = adapter._attempt(
        lambda: draw.AddDiameterDimension2(text_xy[0], text_xy[1], 0.0), default=None
    )
    if dimension is None:
        # Fall back to the smart dimension on the still-selected circle.
        dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} diameter dimension")
    display = _sw_type_info.early_bound_or_flag(dimension, "IDisplayDimension", "Type2")
    dimension_type = int(display.Type2)
    if dimension_type != _DIAMETER_DIMENSION:
        raise RuntimeError(
            f"{label}: dimension type {dimension_type} is not a diameter "
            f"(swDimensionType_e {_DIAMETER_DIMENSION}); a radius would print half"
        )
    return dimension


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-bracket source", await adapter.open_model(str(SOURCE)))
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
            0: "Magnifying Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying bracket; collar + arm + flange; steel fitting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in every orthographic view (policy rule 7): the top +
    # front views carry the collar bore + arm/flange hidden edges, the right
    # view the flange behind the arm.
    for view in (top, front, right):
        set_hidden_lines_visible(adapter, view)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, top_annotations, TOP_CALLOUTS)
    set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)

    # The collar axis is the plan's origin (every station is measured from
    # it): draw it as a centreline off the collar's cylindrical face.
    add_view_centerline(
        adapter, top, face_xy=COLLAR_AXIS_FACE_XY, label="collar axis centreline"
    )

    # ASME centre mark on the collar bore (a real circular edge in the end view).
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the collar bore")

    # FRONT view (projected picks): the collar OD across its two silhouettes
    # (outer lane, right of the collar) as a Ø; the arm's top face from the
    # collar's top silhouette (nearest lane, same side) -- with the OD that
    # places the axis in the 7.5 arm; the flange thickness on the flange's
    # visible front face, left of the flange.
    at_front, (front_x, _fy_unit, _fz) = _model_frame(
        adapter, front, scale=VIEW_SCALE, label="front view"
    )
    collar_top = at_front(3.0, COLLAR_OD / 2.0, 0.0)
    collar_od = add_edge_dimension(
        adapter,
        front,
        p0=collar_top,
        p1=at_front(3.0, -COLLAR_OD / 2.0, 0.0),
        text_xy=_offset(at_front(ARM_HALF_X, 0.0, 0.0), front_x, 0.022),
        label="collar OD",
        orientation="vertical",
        entity_type="SILHOUETTE",
    )
    _display_as_diameter(adapter, collar_od, label="collar OD")
    add_edge_dimension(
        adapter,
        front,
        p0=collar_top,
        p1=find_edge_near(
            adapter, front, at_front(3.0, ARM_Y[1], ARM_Z[1]),
            axis="y", label="arm top face",
        ),
        text_xy=_offset(
            at_front(ARM_HALF_X, (COLLAR_OD / 2.0 + ARM_Y[1]) / 2.0, 0.0), front_x, 0.010
        ),
        label="arm top face from collar OD",
        orientation="vertical",
        entity_types=("SILHOUETTE", "EDGE"),
    )
    add_edge_dimension(
        adapter,
        front,
        p0=find_edge_near(
            adapter, front, at_front(-12.0, FLANGE_Y[1], FLANGE_Z[1]),
            axis="y", label="flange top face",
        ),
        p1=find_edge_near(
            adapter, front, at_front(-12.0, FLANGE_Y[0], FLANGE_Z[1]),
            axis="y", label="flange bottom face",
        ),
        text_xy=_offset(at_front(FLANGE_X[0], 0.0, 0.0), front_x, -0.010),
        label="flange thickness",
        orientation="vertical",
    )

    # RIGHT view (projected picks): the arm thickness at the arm's free end
    # (short witness lines, text beyond the end) and the bore Ø on its
    # visible circle, leadered down-right of the collar.
    at_right, (_rx, right_y, right_z) = _model_frame(
        adapter, right, scale=VIEW_SCALE, label="right view"
    )
    arm_pick_z = ARM_Z[1] - 1.3
    add_edge_dimension(
        adapter,
        right,
        p0=find_edge_near(
            adapter, right, at_right(ARM_HALF_X, ARM_Y[1], arm_pick_z),
            axis="y", label="arm top face",
        ),
        p1=find_edge_near(
            adapter, right, at_right(ARM_HALF_X, ARM_Y[0], arm_pick_z),
            axis="y", label="arm bottom face",
        ),
        text_xy=_offset(
            at_right(ARM_HALF_X, (ARM_Y[0] + ARM_Y[1]) / 2.0, ARM_Z[1]), right_z, 0.012
        ),
        label="arm thickness",
        orientation="vertical",
    )
    bore_text = _offset(
        _offset(at_right(COLLAR_HALF_LEN, -COLLAR_OD / 2.0, -COLLAR_OD / 2.0), right_z, -0.012),
        right_y,
        -0.010,
    )
    _add_circle_diameter(
        adapter,
        right,
        edge_xy=find_edge_near(
            adapter, right, at_right(COLLAR_HALF_LEN, COLLAR_BORE / 2.0, 0.0),
            axis="y", label="collar bore rim",
        ),
        text_xy=bore_text,
        label="collar bore",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.320, 0.108)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Bracket Manufacturing Drawing",
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
