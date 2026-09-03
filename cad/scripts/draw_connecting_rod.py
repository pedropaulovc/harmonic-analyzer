r"""Create the curated machinist drawing for the connecting rod.

The SLDPRT remains authoritative.  This recipe supplies only the connecting-rod
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The rod is a tall thin lollipop (~186 mm ring-bottom to head-crown), so the
sheet runs at 1:1 with a 1:2 isometric.  The front view carries the centre
distance, the (REF) overall and the pin hole; three enlarged details carry
what is too small or too crowded at 1:1 (policy rule 7, machinist review
2026-09-02):

* DETAIL A (2:1) -- the ring: a compact spec-derived note states the outer
  diameter, strap-bore limits and shank width beside the enlarged geometry;
  the bore also carries its roughness symbol.
* DETAIL B (3:1) -- the as-cast head: width across the cheeks, shoulder rise,
  height from the shoulder root, and the FULL R crown flag.
* DETAIL C (3:1, from the left view) -- the stepped thickness where the 3.00
  ring meets the 2.50 shank.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): the
pin hole is a centre distance plus a centreline offset that the block
tolerance holds identically on all 20 rods, so the sheet carries no datums,
no feature-control frames and no basic dimensions. The strap-bore limits come
from the same spec band as the model, and its roughness symbol remains on the
enlarged bore because it runs on the eccentric cam.

Run with SolidWorks open::

    uv run python cad\scripts\draw_connecting_rod.py connecting-rod
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    create_detail_view,
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
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from connecting_rod_notes import CROWN_CALLOUT, RING_GEOMETRY_NOTE
from connecting_rod_spec import (
    CENTER_DISTANCE,
    HEAD_CROWN_CY,
    HEAD_START_Y,
    HEAD_TOP_Y,
    HEAD_WIDTH,
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BORE_DIA_BAND,
    RING_BOTTOM_Y,
    RING_OUTER_RADIUS,
    RING_THICKNESS,
    SHANK_THICKNESS,
    SHANK_WIDTH,
    SHOULDER_TOP_Y,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["connecting_rod"]
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

SHEET_SCALE = (1.0, 1.0)  # 1:1

# Front-view model bbox: X symmetric about 0, Y from the ring bottom up to the
# head crown.
_BBOX_CY = (RING_BOTTOM_Y + HEAD_TOP_Y) / 2.0

FRONT_CENTER = (0.180, 0.135)
LEFT_CENTER = (0.080, 0.171)  # stepped-thickness profile, inside the top zone
ISO_CENTER = (0.385, 0.200)

# Details: the ring at 2:1 in the field right of the front view, the head at
# 3:1 above it, the thickness step at 3:1 left of the left view.
RING_DETAIL_SCALE = (2, 1)
RING_DETAIL_MODEL_RADIUS = 24.0  # encloses the ring and the shank's root
RING_DETAIL_CENTER = (0.290, 0.120)
HEAD_DETAIL_SCALE = (3, 1)
HEAD_DETAIL_MODEL_CY = 160.0
HEAD_DETAIL_MODEL_RADIUS = 8.0  # shoulder root (155.0) to crown top (165.5)
HEAD_DETAIL_CENTER = (0.310, 0.212)
STEP_DETAIL_SCALE = (3, 1)
STEP_DETAIL_MODEL_CY = RING_OUTER_RADIUS  # the 3.00 -> 2.50 step
STEP_DETAIL_MODEL_RADIUS = 8.0
STEP_DETAIL_CENTER = (0.045, 0.125)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + mx / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


def _left_xy(mz: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (Z, Y) point in the 1:1 left view.

    Every thickness is symmetric about the midplane, so the view's Z mirror
    (SolidWorks' choice) cannot matter.
    """
    return (
        LEFT_CENTER[0] + mz / 1000.0,
        LEFT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


def _detail_xy(
    center: tuple[float, float],
    model_cy: float,
    scale: tuple[int, int],
    mu: float,
    mv: float,
) -> tuple[float, float]:
    """Sheet (x, y) of a model point in a detail centred on ``(0, model_cy)``."""
    factor = scale[0] / scale[1] / 1000.0
    return (center[0] + mu * factor, center[1] + (mv - model_cy) * factor)


def _head_xy(mx: float, my: float) -> tuple[float, float]:
    return _detail_xy(
        HEAD_DETAIL_CENTER, HEAD_DETAIL_MODEL_CY, HEAD_DETAIL_SCALE, mx, my
    )


def _step_xy(mz: float, my: float) -> tuple[float, float]:
    return _detail_xy(
        STEP_DETAIL_CENTER, STEP_DETAIL_MODEL_CY, STEP_DETAIL_SCALE, mz, my
    )


# These sketch dimensions are unavailable in a derived detail view. Keep the
# useful enlarged ring geometry and render the part-owned manufacturing sizes
# adjacent to it.
RING_GEOMETRY_NOTE_XY = (
    RING_DETAIL_CENTER[0] + RING_DETAIL_MODEL_RADIUS * 2.0 / 1000.0 + 0.007,
    RING_DETAIL_CENTER[1] + 0.040,
)
# Ra on the strap bore, attached to the main front view's model rim because
# SolidWorks exposes no model edges through the derived detail on this seat.
_FRONT_RING_CENTER = _sheet_xy(0.0, 0.0)
BORE_FINISH_SYMBOL = (
    _FRONT_RING_CENTER[0] + 0.008,
    _FRONT_RING_CENTER[1] + 0.008,
)

CENTER_DISTANCE_TEXT_XY = (0.125, FRONT_CENTER[1])
OVERALL_TEXT_XY = (0.105, FRONT_CENTER[1])
PIN_CALLOUT_XY = (0.222, 0.246)
_TEXT_CALLOUT_BELOW = 4  # swDimensionTextParts_e.swDimensionTextCalloutBelow


def _set_below_text(adapter: Any, display: Any, text: str, *, label: str) -> None:
    """Append callout text beneath a drawing-added dimension's value."""
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "SetText", "GetText"
    )
    display.SetText(_TEXT_CALLOUT_BELOW, text)
    if str(display.GetText(_TEXT_CALLOUT_BELOW) or "") != text:
        raise RuntimeError(f"{label}: below-text {text!r} did not persist")
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open connecting-rod source", await adapter.open_model(str(SOURCE)))
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
            0: "Connecting Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "connecting rod; cast iron; cam strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    # The 1:1 left view (third angle: placed LEFT of the front) shows the
    # stepped thickness (ring 3.0 / shank+head 2.5); the right-hand column
    # belongs to the title block, so it lives on the left.
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)

    ring_detail = create_detail_view(
        adapter,
        front,
        center=_sheet_xy(0.0, 0.0),
        radius=RING_DETAIL_MODEL_RADIUS / 1000.0,
        view_xy=RING_DETAIL_CENTER,
        detail_label="A",
        scale=RING_DETAIL_SCALE,
        label="strap ring detail",
    )
    head_detail = create_detail_view(
        adapter,
        front,
        center=_sheet_xy(0.0, HEAD_DETAIL_MODEL_CY),
        radius=HEAD_DETAIL_MODEL_RADIUS / 1000.0,
        view_xy=HEAD_DETAIL_CENTER,
        detail_label="B",
        scale=HEAD_DETAIL_SCALE,
        label="as-cast head detail",
    )
    step_detail = create_detail_view(
        adapter,
        left,
        center=_left_xy(0.0, STEP_DETAIL_MODEL_CY),
        radius=STEP_DETAIL_MODEL_RADIUS / 1000.0,
        view_xy=STEP_DETAIL_CENTER,
        detail_label="C",
        scale=STEP_DETAIL_SCALE,
        label="ring-to-shank thickness step detail",
    )
    for view in (front, left, ring_detail, head_detail, step_detail):
        set_hidden_lines_visible(adapter, view)

    if add_note(adapter, RING_GEOMETRY_NOTE, *RING_GEOMETRY_NOTE_XY) is None:
        raise RuntimeError("failed to add ring geometry note")
    # Ra on the running strap bore. Resolve the rim from the model geometry in
    # the main front view; the derived detail exposes no model edges.
    bore_edge = visible_circle_edge(adapter, front, RING_BORE_DIA)
    add_surface_finish(
        adapter,
        front,
        edge_entity=bore_edge,
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "strap_bore"),
        label="strap bore finish",
    )

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Centre distance: ring bore edge to the rocker-pin bore edge (SolidWorks
    # dimensions circle edges centre-to-centre).  Pick each bore's LEFT rim --
    # the pin bore is tiny and sits inside the head crown, so a TOP pick
    # snapped to the crown arc (read 145.07); the left rim is unambiguously on
    # the pin circle, clear of the wider crown.  "C-C" says what it is.
    ring_rim = _sheet_xy(-RING_BORE_DIA / 2.0, 0.0)
    pin_rim = _sheet_xy(-PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    centre_distance = add_edge_dimension(
        adapter,
        front,
        p0=ring_rim,
        p1=pin_rim,
        text_xy=CENTER_DISTANCE_TEXT_XY,
        label="rod centre distance",
    )
    _set_below_text(adapter, centre_distance, "C-C", label="rod centre distance")

    # (REF) overall: ring bottom to crown top, both arc extremes.
    overall = add_edge_dimension(
        adapter,
        front,
        p0=_sheet_xy(0.0, RING_BOTTOM_Y),
        p1=_sheet_xy(0.0, HEAD_TOP_Y),
        text_xy=OVERALL_TEXT_XY,
        label="overall length",
        orientation="vertical",
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length")
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length",
    )

    # Rocker pin hole native callout (the #47 wizard hole in the head), the
    # drill riding as its prefix.
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=pin_rim,
        callout_xy=PIN_CALLOUT_XY,
        label="rocker pin hole",
        process="#47 DRILL",
    )

    # Pin centreline offset from the shank's left flank: ties the pin hole to
    # the shank centreline as an ordinary coordinate.
    shank_flank = _sheet_xy(-SHANK_WIDTH / 2.0, 100.0)
    add_edge_dimension(
        adapter,
        front,
        p0=shank_flank,
        p1=pin_rim,
        text_xy=(0.152, 0.224),
        label="pin C/L from shank flank",
        orientation="horizontal",
    )

    # DETAIL B, the as-cast head: width across the cheeks (above the crown),
    # shoulder rise (right), height from the shoulder root to the crown top
    # (left), and the crown flagged FULL R.
    half_head = HEAD_WIDTH / 2.0
    half_shank = SHANK_WIDTH / 2.0
    cheek_y = (SHOULDER_TOP_Y + HEAD_CROWN_CY) / 2.0
    add_edge_dimension(
        adapter,
        head_detail,
        p0=_head_xy(-half_head, cheek_y),
        p1=_head_xy(half_head, cheek_y),
        text_xy=(HEAD_DETAIL_CENTER[0], _head_xy(0.0, HEAD_TOP_Y)[1] + 0.012),
        label="head width",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        head_detail,
        p0=_head_xy(half_shank, HEAD_START_Y),
        p1=_head_xy(half_head, SHOULDER_TOP_Y),
        text_xy=(
            _head_xy(half_head, 0.0)[0] + 0.016,
            _head_xy(0.0, (HEAD_START_Y + SHOULDER_TOP_Y) / 2.0)[1],
        ),
        label="head shoulder rise",
        orientation="vertical",
        entity_types=("VERTEX", "VERTEX"),
    )
    head_height = add_edge_dimension(
        adapter,
        head_detail,
        p0=_head_xy(-half_shank, HEAD_START_Y),
        p1=_head_xy(0.0, HEAD_TOP_Y),
        text_xy=(
            _head_xy(-half_head, 0.0)[0] - 0.014,
            _head_xy(0.0, (HEAD_START_Y + HEAD_TOP_Y) / 2.0)[1],
        ),
        label="head height",
        orientation="vertical",
        entity_types=("VERTEX", "EDGE"),
    )
    set_arc_endpoints_to_max(adapter, head_height, label="head height")
    add_attached_note(
        adapter,
        head_detail,
        text=CROWN_CALLOUT,
        entity_xy=_head_xy(half_head * 0.6, HEAD_CROWN_CY + half_head * 0.8),
        note_xy=(HEAD_DETAIL_CENTER[0] + 0.020, _head_xy(0.0, HEAD_TOP_Y)[1] + 0.004),
        label="head crown full round",
    )

    # DETAIL C, the thickness step: the ring's 3.00 across its flat faces
    # (picked above the bore's projected span, so only the OD edge is there)
    # and the shank's 2.50 just above the step.
    ring_pick_y = RING_BORE_DIA / 2.0 + 1.6
    shank_pick_y = RING_OUTER_RADIUS + 5.6
    add_edge_dimension(
        adapter,
        step_detail,
        p0=_step_xy(-RING_THICKNESS / 2.0, ring_pick_y),
        p1=_step_xy(RING_THICKNESS / 2.0, ring_pick_y),
        text_xy=(STEP_DETAIL_CENTER[0], _step_xy(0.0, ring_pick_y)[1] - 0.026),
        label="ring thickness",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        step_detail,
        p0=_step_xy(-SHANK_THICKNESS / 2.0, shank_pick_y),
        p1=_step_xy(SHANK_THICKNESS / 2.0, shank_pick_y),
        text_xy=(STEP_DETAIL_CENTER[0], _step_xy(0.0, shank_pick_y)[1] + 0.014),
        label="shank thickness",
        orientation="horizontal",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.036)
    add_property_linked_note(adapter, "Isometric View Note", 0.365, 0.252)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Connecting Rod Manufacturing Drawing",
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
