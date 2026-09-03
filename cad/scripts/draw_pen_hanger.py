r"""Create the curated machinist drawing for the pen hanger.

The SLDPRT remains authoritative.  This recipe supplies only the hanger's views,
strap/block dimensions, the hanger-screw callout and stations, and the
manufacturing notes; every shared sheet/template, import, curation, and export
behavior lives in ``_drawing_common``.

The pen hanger is a black tapered steel strap (3 thick, 10 -> 16 wide) rising
from a 12 x 12 x 22.1 guide block; the block carries a 5.4 square vertical
channel the pen rod slides in, and a #6-32 tapped hanger-screw hole passes
through the strap near its top.  The part is tall and narrow (~82 x 22), so the
FRONT profile is the main view at 2:1: the block's width and height, the
strap's two widths, rise and right-edge lean, the hole's native callout and its
two stations from the strap's top edge / top-right corner.  The TOP view (the
guide block seen from above, the strap's top face at its back) carries the
block depth, the strap thickness, and the channel's two sides and two stations
-- the channel is a visible square there, never a hidden line (policy rule 7).
An isometric sits to the right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pen_hanger.py pen-hanger
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
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    model_point_in_view,
    remove_notes_matching,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import TAP_DRILL_MM
from build_pen_hanger import (
    BLOCK_HALF,
    BLOCK_Z,
    GUIDE_HOLE_HALF,
    SCREW_HOLE_XY,
    STRAP_BOT_X,
    STRAP_TOP_X,
    STRAP_TOP_Y,
    STRAP_Z,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pen_hanger"]
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

SHEET_SCALE = (2.0, 1.0)  # 2:1 whole sheet (~82 mm tall part)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 2.0 sheet-mm per model-mm / 1000

# Front-view model bounding box (X-Y profile of the strap + block).
_BBOX_X = (
    min(STRAP_TOP_X[0], STRAP_BOT_X[0], -BLOCK_HALF),
    max(STRAP_TOP_X[1], STRAP_BOT_X[1], BLOCK_HALF),
)
_BBOX_Y = (-BLOCK_HALF, STRAP_TOP_Y)
_BBOX_CX = (_BBOX_X[0] + _BBOX_X[1]) / 2.0
_BBOX_CY = (_BBOX_Y[0] + _BBOX_Y[1]) / 2.0
# Top-view model bounding box (X-Z plan: block plus the strap's overhang).
_TOP_CX = _BBOX_CX
_TOP_CZ = (BLOCK_Z[0] + BLOCK_Z[1]) / 2.0

# Sheet layout (meters).  Tall front view hugs the left; the top view sits
# up-right of it, the isometric to the far right; the notes fill the clear
# mid band between the front view and the isometric.
FRONT_CENTER = (0.075, 0.150)
TOP_CENTER = (0.205, 0.200)
ISO_CENTER = (0.320, 0.170)


def _fx(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - _BBOX_CX) * VIEW_SCALE / 1000.0


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BBOX_CY) * VIEW_SCALE / 1000.0


def _tx(model_x_mm: float) -> float:
    return TOP_CENTER[0] + (model_x_mm - _TOP_CX) * VIEW_SCALE / 1000.0


def _tz(model_z_mm: float) -> float:
    # Top view: model +Z (toward the front-view viewer) reads sheet-DOWN.
    return TOP_CENTER[1] - (model_z_mm - _TOP_CZ) * VIEW_SCALE / 1000.0


# Hanger-screw hole (model mm) and its tap-drill rim.
SCREW_X, SCREW_Y = SCREW_HOLE_XY
SCREW_DRILL_R = TAP_DRILL_MM["#6-32"] / 2.0
SCREW_TOP_STATION = STRAP_TOP_Y - SCREW_Y  # 5.00 below the top edge
SCREW_CORNER_STATION = STRAP_TOP_X[1] - SCREW_X  # 8.50 from the top-right corner

# Front-view survivors of the marked-dimension import (Front-plane sketch
# dims).  Above the strap top: the 8.50 hole station (nearest, right of the
# corner-shared witness line) with the 5.00 right-edge lean chained through
# the top-right corner, the 16.00 top run outside them.  Under the block: the
# 10.00 strap foot nearest, the 12.00 block width outside it.  Left: the
# strap rise (outer) with the hole's 5.00 top station nested inside it.
# Right of the block: the block height.
FRONT_KEEP = {
    "StrapTopRun": (
        _fx((STRAP_TOP_X[0] + STRAP_TOP_X[1]) / 2.0),
        _fy(STRAP_TOP_Y) + 0.020,
    ),
    "StrapTaperDx": (
        _fx((STRAP_BOT_X[1] + STRAP_TOP_X[1]) / 2.0),
        _fy(STRAP_TOP_Y) + 0.010,
    ),
    "StrapTaperDy": (_fx(_BBOX_X[0]) - 0.018, FRONT_CENTER[1]),
    "StrapBotWidth": (_fx(0.0), _fy(-BLOCK_HALF) - 0.010),
    "BlockWidth": (_fx(0.0), _fy(-BLOCK_HALF) - 0.020),
    "BlockDepth": (_fx(BLOCK_HALF) + 0.012, _fy(0.0)),
}
# Top-view survivors (Top-plane channel sketch): the channel's width above
# the block (nearest lane; its 3.30 side station shares the outer lane), its
# depth left of the block (nearest; the 1.30 front station outside it).
TOP_KEEP = {
    "ChannelWidth": (_tx(0.0), _tz(BLOCK_Z[0]) + 0.010),
    "ChannelDepth": (_tx(-BLOCK_HALF) - 0.012, _tz(0.0)),
}

# Hole picks and text (front view).
STRAP_TOP_EDGE_PICK = (_fx(-12.0), _fy(STRAP_TOP_Y))
STRAP_TOP_RIGHT_CORNER = (_fx(STRAP_TOP_X[1]), _fy(STRAP_TOP_Y))
SCREW_TOP_RIM = (_fx(SCREW_X), _fy(SCREW_Y + SCREW_DRILL_R))
SCREW_RIGHT_RIM = (_fx(SCREW_X + SCREW_DRILL_R), _fy(SCREW_Y))
SCREW_TOP_STATION_TEXT_XY = (
    _fx(STRAP_TOP_X[0]) - 0.010,
    _fy((STRAP_TOP_Y + SCREW_Y) / 2.0),
)
SCREW_CORNER_STATION_TEXT_XY = (
    _fx((STRAP_TOP_X[1] + SCREW_X) / 2.0),
    _fy(STRAP_TOP_Y) + 0.010,
)
# Native #6-32 callout down-right of the hole, clear of the top-view lanes.
SCREW_CALLOUT_XY = (_fx(STRAP_TOP_X[1]) + 0.014, _fy(SCREW_Y) - 0.016)


def _model_frame(adapter: Any, view: Any, *, scale: float, label: str):
    """Model-mm -> sheet projection for ``view`` plus the sheet unit vectors of
    model +X/+Y/+Z, read from the view's own transform so no sign is guessed.
    The projected length of a 10 mm model step is checked against ``scale``
    so a transform that omitted the view scale fails loud instead of
    mis-picking."""

    def at(x_mm: float, y_mm: float, z_mm: float) -> tuple[float, float]:
        return model_point_in_view(
            adapter,
            view,
            (x_mm / 1000.0, y_mm / 1000.0, z_mm / 1000.0),
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


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-hanger source", await adapter.open_model(str(SOURCE)))
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
            "Front View Note",
            "Top View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Top View Note",
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
            0: "Pen Hanger Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen hanger; tapered strap; pen-rod guide block",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in every orthographic view: the front view shows the
    # square rod channel through the block and the tapped hole in the strap.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the hanger-screw hole")

    # Hanger-screw hole: the native #6-32 Hole Wizard callout (the tap end
    # condition is verified in the build, so a through tap prints THRU) and
    # two stations re-anchored to the arc CENTRE -- 5.00 down from the strap's
    # top edge, 8.50 in from its top-right corner (the strap edges beside the
    # hole are inclined, so the corner vertex is the horizontal origin).
    top_station = add_edge_dimension(
        adapter,
        front,
        p0=find_edge_near(
            adapter, front, STRAP_TOP_EDGE_PICK, axis="y", label="strap top edge"
        ),
        p1=find_edge_near(
            adapter, front, SCREW_TOP_RIM, axis="y", label="hanger-screw hole rim"
        ),
        text_xy=SCREW_TOP_STATION_TEXT_XY,
        label="hanger-screw top station",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, top_station, label="hanger-screw top station")
    corner_station = add_edge_dimension(
        adapter,
        front,
        p0=STRAP_TOP_RIGHT_CORNER,
        p1=find_edge_near(
            adapter, front, SCREW_RIGHT_RIM, axis="x", label="hanger-screw hole rim"
        ),
        text_xy=SCREW_CORNER_STATION_TEXT_XY,
        label="hanger-screw corner station",
        orientation="horizontal",
        entity_types=("VERTEX", "EDGE"),
    )
    set_arc_endpoints_to_center(
        adapter, corner_station, label="hanger-screw corner station"
    )
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=find_edge_near(
            adapter, front, SCREW_RIGHT_RIM, axis="x", label="hanger-screw hole rim"
        ),
        callout_xy=SCREW_CALLOUT_XY,
        label="hanger-screw tap",
    )
    # Dimension import creates SolidWorks' redundant generic "#6-32 Tapped
    # Hole" note.  Remove it only after curation and the complete native
    # callout have run; removing it before curation allowed the duplicate to be
    # recreated across the 8.50 / 5.00 upper annotation lanes.
    removed_tap_notes = remove_notes_matching(adapter, "Tapped Hole")
    _telemetry.info(
        f"removed {removed_tap_notes} redundant automatic tapped-hole note(s)"
    )
    if (
        not bool(adapter._attempt(lambda: tap_callout.IsHoleCallout(), default=False))
        or adapter._attempt(lambda: tap_callout.GetAnnotation(), default=None) is None
    ):
        raise RuntimeError(
            "native hanger-screw tap callout was removed with generic note"
        )

    # Top view: the block depth and strap thickness (extrude depths, so
    # drawing-added on real edges) and the channel's two stations from the
    # block's front and left faces.  Picks are projected through the view's
    # own transform; the block's back edge is picked at model x > 0, where the
    # strap's collinear top-face edge does not cover it.
    at_top, (top_x, _ty, top_z) = _model_frame(
        adapter, top, scale=VIEW_SCALE, label="top view"
    )
    add_edge_dimension(
        adapter,
        top,
        p0=find_edge_near(
            adapter,
            top,
            at_top(3.0, BLOCK_HALF, BLOCK_Z[0]),
            axis="y",
            label="block front edge",
        ),
        p1=find_edge_near(
            adapter,
            top,
            at_top(3.0, BLOCK_HALF, BLOCK_Z[1]),
            axis="y",
            label="block back edge",
        ),
        text_xy=_offset(at_top(BLOCK_HALF, BLOCK_HALF, _TOP_CZ), top_x, 0.014),
        label="block depth",
        orientation="vertical",
    )
    strap_mid_x = (STRAP_TOP_X[0] - BLOCK_HALF) / 2.0  # on the strap's overhang
    add_edge_dimension(
        adapter,
        top,
        p0=find_edge_near(
            adapter,
            top,
            at_top(strap_mid_x, STRAP_TOP_Y, STRAP_Z[0]),
            axis="y",
            label="strap front face",
        ),
        p1=find_edge_near(
            adapter,
            top,
            at_top(strap_mid_x, STRAP_TOP_Y, STRAP_Z[1]),
            axis="y",
            label="strap back face",
        ),
        text_xy=_offset(
            at_top(STRAP_TOP_X[0], STRAP_TOP_Y, (STRAP_Z[0] + STRAP_Z[1]) / 2.0),
            top_x,
            -0.012,
        ),
        label="strap thickness",
        orientation="vertical",
    )
    # Channel front station (1.30): block front face -> channel near wall,
    # the outer lane left of the block (the marked 5.40 depth is nearest).
    add_edge_dimension(
        adapter,
        top,
        p0=find_edge_near(
            adapter,
            top,
            at_top(0.0, BLOCK_HALF, BLOCK_Z[0]),
            axis="y",
            label="block front edge",
        ),
        p1=find_edge_near(
            adapter,
            top,
            at_top(0.0, BLOCK_HALF, -GUIDE_HOLE_HALF),
            axis="y",
            label="channel near wall",
        ),
        text_xy=_offset(
            at_top(-BLOCK_HALF, BLOCK_HALF, (BLOCK_Z[0] - GUIDE_HOLE_HALF) / 2.0),
            top_x,
            -0.024,
        ),
        label="channel front station",
        orientation="vertical",
    )
    # Channel side station (3.30): block left face -> channel left wall, the
    # outer lane above the block (the marked 5.40 width is nearest).
    add_edge_dimension(
        adapter,
        top,
        p0=find_edge_near(
            adapter,
            top,
            at_top(-BLOCK_HALF, BLOCK_HALF, 0.0),
            axis="x",
            label="block left edge",
        ),
        p1=find_edge_near(
            adapter,
            top,
            at_top(-GUIDE_HOLE_HALF, BLOCK_HALF, 0.0),
            axis="x",
            label="channel left wall",
        ),
        text_xy=_offset(
            at_top((-BLOCK_HALF - GUIDE_HOLE_HALF) / 2.0, BLOCK_HALF, BLOCK_Z[0]),
            top_z,
            -0.020,
        ),
        label="channel side station",
        orientation="horizontal",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.115, 0.150)
    add_property_linked_note(adapter, "Front View Note", 0.030, 0.036)
    add_property_linked_note(adapter, "Top View Note", 0.183, 0.164)
    add_property_linked_note(adapter, "Isometric View Note", 0.286, 0.104)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Hanger Manufacturing Drawing",
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
