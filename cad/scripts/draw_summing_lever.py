r"""Create the curated machinist drawing for the summing lever.

The SLDPRT remains authoritative.  This recipe supplies only the summing-lever
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

A large green cast-iron first-class lever hung on hex knife-edge trunnions (no
bore): a coefficients plate on the +X arm carrying the 20 channel-spring holes,
a solid pivot cylinder (152.4 long, along Z), and a summation arm reaching to
the counter-spring anchor eye on the -X arm.  The sheet runs at 1:2 and shows:

* a 1:2 **front** profile with the rib outline, R15.24 rib arc, the hex
  trunnion end face, and a nearby three-value knife-edge geometry block;
* a 1:2 **top** plan (plate width/length off the pivot axis, the summation
  arm's side-arc radii, the anchor eye, the 20-hole pattern);
* a 1:2 **right** view (pivot diameter, coefficients-plate and rib
  thicknesses, trunnion length and vertex height, datum A on the ridge);
* a 1:4 isometric.

GD&T is limited to the rule-3 allowlist (cad/docs/drawing-simplicity-policy.md):
ONE position frame on the 20-hole spring pattern, with the two datums it
references (A = knife-edge pivot axis, B = plate -Z end) and the three basic
coordinates that feed it.  The knife edge keeps its roughness symbol; the
anchor bore is an ordinary toleranced coordinate.

Run with SolidWorks open::

    uv run python cad\scripts\draw_summing_lever.py summing-lever
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from summing_lever_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    place_view,
    view_name,
)
from summing_lever_spec import (
    ANCHOR_BORE_R,
    ANCHOR_R,
    CHANNEL_PITCH,
    CYL_R,
    HEX_DEPTH,
    HEX_H,
    HEX_W,
    HEX_Z_INNER,
    HEX_Z_OUTER,
    HOLE_DIA,
    HOLE_X,
    HOLE_Z_FIRST,
    HOLE_Z_LAST,
    PLATE_L,
    PLATE_T,
    PLATE_W,
    SURFACE_FINISHES,
    TIP_X,
)


SPEC = DRAWINGS_BY_NAME["summing_lever"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front (down -Z) and top (down -Y) share the same X extent: anchor eye
# (TIP_X - ANCHOR_R) on the left to the plate right edge (PLATE_W).
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

# Rib geometry the front view dimensions (build_summing_lever: the edge ribs'
# semicircle and the middle rib's coradial arcs share ARC_R = CYL_R + RIB_PAD).
RIB_PAD = 2.54
RIB_T = 5.08
RIB_ARC_R = CYL_R + RIB_PAD  # 15.24
RIB_OFFSET = PLATE_L / 2.0 - RIB_T  # 71.12: edge-rib inner face along Z
# Summation-arm side arcs: three-point arcs through (0, PLATE_L/2),
# (TIP_X/2, PLATE_L/4 - 7.62) and (TIP_X, ANCHOR_R); R = 138.85 (both sides).
SUM_ARC_MID = (TIP_X / 2.0, PLATE_L / 4.0 - 7.62)  # (-38.1, 30.48)

# Third-angle layout: front and right views above the top plan, with the
# knife-edge geometry block in the free upper-left field and the isometric
# at the top-right.
FRONT_CENTER = (0.155, 0.225)
TOP_CENTER = (0.155, 0.125)
RIGHT_CENTER = (0.265, 0.225)
ISO_CENTER = (0.380, 0.235)
HEX_FLAT_LENGTH = HEX_H / 2.0
HEX_INCLUDED_ANGLE_DEG = 180.0 - 2.0 * math.degrees(
    math.atan2(HEX_H / 4.0, HEX_W / 2.0)
)
KNIFE_EDGE_GEOMETRY_NOTE = "\n".join(
    (
        "BOTH HEX KNIFE EDGES AT PIVOT",
        f"{HEX_W:.2f} ACROSS FLATS",
        f"{HEX_FLAT_LENGTH:.2f} FLAT LENGTH",
        f"{HEX_INCLUDED_ANGLE_DEG:.2f} DEG INCLUDED KNIFE ANGLE",
    )
)
KNIFE_EDGE_NOTE_XY = (0.055, 0.205)


def _front_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Y) point in the front profile view (1:2)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + my * _S / 1000.0,
    )


def _top_xy(mx: float, up_mm: float) -> tuple[float, float]:
    """Sheet (x, y) of a plan point in the top view (1:2).

    ``up_mm`` is the SHEET-UP offset from the pivot axis in model mm.  A
    SolidWorks Top view reverses model Z on the sheet, so sheet-up is model
    -Z: ``up_mm = +82`` is the -Z trunnion ridge, ``up_mm = -HOLE_Z_LAST`` the
    spring hole nearest the +Z plate end (the 8.43 end offset the sheet
    shows).  The lever is symmetric in Z, so every pick below is described
    by its sheet side.
    """
    return (
        TOP_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        TOP_CENTER[1] + up_mm * _S / 1000.0,
    )


def _right_xy(mz: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (Z, Y) point in the right view (1:2).

    The view's bounding box (trunnion tips +-HEX_Z_OUTER, rib crowns
    +-RIB_ARC_R) is centred on the pivot axis in both directions, and the
    lever is symmetric in Z, so a mirrored Z cannot move a pick.
    """
    return (
        RIGHT_CENTER[0] + mz * _S / 1000.0,
        RIGHT_CENTER[1] + my * _S / 1000.0,
    )


def _add_radial_dimension(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Radius-dimension one arc edge picked at a sheet point.

    ``IModelDoc2.AddRadialDimension2`` only works inside an active sketch, so
    a drawing radius is the smart dimension (``AddDimension2``) with a single
    arc edge selected -- SolidWorks emits ``R<value>`` for an arc.
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
            f"failed to select {label} arc at sheet ({edge_xy[0]:g}, {edge_xy[1]:g})"
        )
    dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} radius dimension")
    return dimension


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


FRONT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP = {
    # Plate width off the pivot axis: the plate's X=0 edge lies inside the
    # cylinder's plan rectangle, so the view carries the axis centerline
    # (below) as that extension line's terminus; lane above the 76.20/39.85
    # lane that shares the same origin.
    "PlateWidth": (0.176, 0.186),
    "PlateLength": (0.268, TOP_CENTER[1]),
    # Left of the anchor eye with a horizontal leader to its leftmost point
    # (the part's -X extreme), so the leader crosses no arm outline.
    "AnchorOuterDia": (0.098, TOP_CENTER[1]),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}

# Sheet-top lanes of the top view, above the -Z trunnion tip (0.174):
# 0.178 carries the anchor X (left of the axis) and the BASIC hole-row X
# (right of it) as one chain through the origin; 0.186 the plate width.
TOP_LANE_CHAIN_Y = 0.178
TOP_LANE_WIDTH_Y = TOP_KEEP["PlateWidth"][1]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
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
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; gray iron; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (front, top, right):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")

    # --- Front profile: the rib arc that wraps the pivot.  Both ribs' arcs
    # are coradial (R15.24) and coincide in this view; pick the edge rib's
    # semicircle on its -X side at ~135 deg, where the frontmost edge rib
    # owns the outline (its tangent lines leave the arc near 12 o'clock).
    rib_arc = _front_xy(-RIB_ARC_R * 0.7071, RIB_ARC_R * 0.7071)
    _add_radial_dimension(
        adapter,
        front,
        edge_xy=rib_arc,
        text_xy=(0.135, 0.250),
        label="rib arc radius",
    )

    # The front projection shows the non-regular hex inside the larger pivot
    # cylinder silhouette. State the three values needed to mill or file both
    # knife edges in a compact block beside that view. An enlarged detail of
    # the whole pivot projected the cylinder silhouette instead of clarifying
    # the smaller trunnion, so it is intentionally omitted.
    if add_note(adapter, KNIFE_EDGE_GEOMETRY_NOTE, *KNIFE_EDGE_NOTE_XY) is None:
        raise RuntimeError("failed to add knife-edge geometry block")

    # --- Top plan.  Axis centerline of the pivot cylinder: the plate's X=0
    # edge is buried inside the cylinder's plan rectangle (plate +-2.54 <
    # R12.7), so without the centerline the marked 44.45 has one extension
    # line landing on nothing.  Picked on the cylinder face above the
    # coefficients plate, clear of both ribs.
    add_view_centerline(
        adapter, top, face_xy=_top_xy(5.0, 30.0), label="pivot axis centerline"
    )

    # Anchor bore (Ø3.0) native callout, lower-left of the eye, terminating on
    # the bore's sheet-bottom rim so its leader stays clear of the Ø19.05
    # leader (which comes in horizontally from the left).
    anchor_bore_edge = _top_xy(TIP_X, -ANCHOR_BORE_R)
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=anchor_bore_edge,
        callout_xy=(0.090, 0.107),
        label="anchor bore",
        process="DRILL",
    )

    # Summation-arm side arcs (R138.85 each): radius dimensions with the text
    # on the arc's concave (outside) side, so the leader reaches the arc from
    # clear space.  One per side -- the plan is symmetric about the axis but
    # the print says so with two radii, not a note.
    for side, text_y in ((1.0, 0.165), (-1.0, 0.085)):
        _add_radial_dimension(
            adapter,
            top,
            edge_xy=_top_xy(SUM_ARC_MID[0], side * SUM_ARC_MID[1]),
            text_xy=(0.140, text_y),
            label=f"summation arc radius ({'upper' if side > 0 else 'lower'})",
        )

    # Sheet-top lanes: the sheet-top (-Z) trunnion ridge line at X=0 is the
    # ONE origin of every X station in this view (it is collinear with the
    # centerline).  76.20 to the anchor bore runs left, the BASIC 39.85 hole
    # row runs right -- one chain through the origin on lane 0.178; the
    # marked 44.45 plate width sits on lane 0.186 above it.
    ridge_dim_edge = _top_xy(0.0, PLATE_L / 2.0 + 0.3 * HEX_DEPTH)
    anchor_bore_top = _top_xy(TIP_X, ANCHOR_BORE_R)
    add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=anchor_bore_top,
        text_xy=(0.146, TOP_LANE_CHAIN_Y),
        label="anchor bore X location",
        orientation="horizontal",
    )
    top_hole_up = -HOLE_Z_FIRST  # the spring hole nearest the sheet-top end
    top_hole_rim_right = _top_xy(HOLE_X + HOLE_DIA / 2.0, top_hole_up)
    row_x = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=top_hole_rim_right,
        text_xy=(0.1758, TOP_LANE_CHAIN_Y),
        label="spring-hole row X",
        orientation="horizontal",
    )
    set_basic_dimension(adapter, row_x, label="spring-hole row X")

    # Sheet-bottom (+Z) end: datum B on the plate end face, the BASIC end
    # offset and pitch off it, the 20X frame and the #47 callout, and the
    # knife-edge roughness on the +Z ridge -- each attached to a DIFFERENT
    # hole or edge so no leader crosses another leader or an extension line.
    plate_end_edge = _top_xy(PLATE_W - 0.45, -PLATE_L / 2.0)
    add_datum_feature(
        adapter,
        top,
        edge_xy=plate_end_edge,
        symbol_xy=(0.198, 0.068),
        datum="B",
        label="plate -Z end face",
    )
    knife_edge = _top_xy(0.0, -(PLATE_L / 2.0 + HEX_DEPTH / 2.0))
    add_surface_finish(
        adapter,
        top,
        edge_xy=knife_edge,
        symbol_xy=(0.182, 0.079),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge ridge finish",
    )
    end_hole_up = -HOLE_Z_LAST  # the spring hole nearest the sheet-bottom end
    end_hole_rim_top = _top_xy(HOLE_X, end_hole_up + HOLE_DIA / 2.0)
    start_z = add_edge_dimension(
        adapter,
        top,
        p0=_top_xy(PLATE_W - 20.0, -PLATE_L / 2.0),
        p1=end_hole_rim_top,
        text_xy=(0.212, 0.0955),
        label="spring-hole start Z",
        orientation="vertical",
    )
    set_basic_dimension(adapter, start_z, label="spring-hole start Z")
    second_rim_bottom = _top_xy(HOLE_X, end_hole_up + CHANNEL_PITCH - HOLE_DIA / 2.0)
    pitch = add_edge_dimension(
        adapter,
        top,
        p0=end_hole_rim_top,
        p1=second_rim_bottom,
        text_xy=(0.224, 0.1035),
        label="spring-hole pitch",
        orientation="vertical",
    )
    set_basic_dimension(adapter, pitch, label="spring-hole pitch")
    third_rim_top = _top_xy(HOLE_X, end_hole_up + 2.0 * CHANNEL_PITCH + HOLE_DIA / 2.0)
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=third_rim_top,
        frame_xy=(0.204, 0.112),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"],
        datums=("A", "B"),
        diameter=True,
        quantity="20X",
        label="spring-hole pattern position",
    )
    fifth_rim_right = _top_xy(
        HOLE_X + HOLE_DIA / 2.0, end_hole_up + 4.0 * CHANNEL_PITCH
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=fifth_rim_right,
        callout_xy=(0.232, 0.126),
        label="spring-hole seed",
        process="#47 DRILL",
    )

    # --- Right view (looking down -X): the pivot cylinder's silhouettes,
    # the coefficients plate's end face, both rib kinds as bands proud of the
    # cylinder, and the hex trunnions overhanging each end.
    pivot_dia = add_edge_dimension(
        adapter,
        right,
        p0=_right_xy(-40.0, CYL_R),
        p1=_right_xy(-40.0, -CYL_R),
        text_xy=(0.208, 0.243),
        label="pivot diameter",
        orientation="vertical",
        entity_type="SILHOUETTE",
    )
    _display_as_diameter(adapter, pivot_dia, label="pivot diameter")
    add_edge_dimension(
        adapter,
        right,
        p0=_right_xy(50.0, PLATE_T / 2.0),
        p1=_right_xy(50.0, -PLATE_T / 2.0),
        text_xy=(0.320, 0.212),
        label="coefficients plate thickness",
        orientation="vertical",
    )
    # Rib bands picked on their LOWER crowns with the texts below the view:
    # above it, the edge rib's Z=76.2 extension line would run through datum
    # A's box on the trunnion ridge.
    add_edge_dimension(
        adapter,
        right,
        p0=_right_xy(-RIB_T / 2.0, -14.0),
        p1=_right_xy(RIB_T / 2.0, -14.0),
        text_xy=(0.252, 0.190),
        label="middle rib thickness",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        right,
        p0=_right_xy(RIB_OFFSET, -14.0),
        p1=_right_xy(PLATE_L / 2.0, -14.0),
        text_xy=(0.290, 0.190),
        label="edge rib thickness",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        right,
        p0=_right_xy(HEX_Z_INNER, 8.0),
        p1=_right_xy(HEX_Z_OUTER, 0.0),
        text_xy=(0.326, 0.203),
        label="trunnion length",
        orientation="horizontal",
    )
    trunnion_mid_z = HEX_Z_INNER + 0.72 * HEX_DEPTH
    add_edge_dimension(
        adapter,
        right,
        p0=_right_xy(trunnion_mid_z, HEX_H / 2.0),
        p1=_right_xy(trunnion_mid_z, -HEX_H / 2.0),
        text_xy=(0.332, 0.243),
        label="hex vertex height",
        orientation="vertical",
    )
    # Datum A = the knife-edge pivot axis, tagged on the +Z trunnion's top
    # ridge line here, where it is a clean visible edge with clear space
    # above it (the top view's ridges carry the station origin and the
    # roughness symbol).  Kept ONLY as the primary datum of the spring-pattern
    # position frame (policy rule 3 allowlist).
    knife_edge_datum = _right_xy(HEX_Z_INNER + 0.2 * HEX_DEPTH, HEX_H / 2.0)
    add_datum_feature(
        adapter,
        right,
        edge_xy=knife_edge_datum,
        symbol_xy=(knife_edge_datum[0], 0.240),
        datum="A",
        label="knife-edge pivot axis",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.345, 0.205)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
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
