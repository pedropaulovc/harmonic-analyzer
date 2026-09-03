r"""Create the curated machinist drawing for the connecting rod.

The SLDPRT remains authoritative.  This recipe supplies only the connecting-rod
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The rod is a tall thin lollipop (~186 mm ring-bottom to head-crown), so the
sheet runs at 1:1 with a 1:2 isometric.  The front view carries the centre
distance, the (REF) overall and the pin hole.  The ring, as-cast head, and
3.00/2.50 thickness transition are shown in directly placed cropped model
views.  Each view is translated by its actual model point before cropping, so
the enlarged ring/head/step geometry cannot drift out of an otherwise empty
SolidWorks derived-detail circle.  Decorative crop outlines and generated
captions are suppressed; adjacent specification-derived notes identify each
detail and its explicit scale.  The one finish symbol remains on the main
view's enlarged bore because it runs on the eccentric cam.

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
    _sheet_to_view_sketch,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from connecting_rod_notes import (
    CROWN_CALLOUT,
    RING_GEOMETRY_NOTE as RING_GEOMETRY_SPEC_NOTE,
)
from connecting_rod_spec import (
    CENTER_DISTANCE,
    HEAD_HEIGHT,
    HEAD_SHOULDER_RISE,
    HEAD_TOP_Y,
    HEAD_WIDTH,
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BOTTOM_Y,
    RING_OUTER_RADIUS,
    RING_THICKNESS,
    SHANK_THICKNESS,
    SHANK_WIDTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
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

# Cropped model views use only enough model-space context to show the complete
# feature.  With no decorative outline, these compact centres keep the actual
# enlarged profiles and their notes disjoint.
RING_DETAIL_SCALE = (2, 1)
RING_DETAIL_MODEL_RADIUS = 22.0  # ring OD plus the shank root line
RING_DETAIL_CENTER = (0.255, 0.150)
HEAD_DETAIL_SCALE = (3, 1)
HEAD_DETAIL_MODEL_CY = 160.0
HEAD_DETAIL_MODEL_RADIUS = 7.0  # shoulder root through crown top
HEAD_DETAIL_CENTER = (0.320, 0.215)
STEP_DETAIL_SCALE = (3, 1)
STEP_DETAIL_MODEL_CY = RING_OUTER_RADIUS  # the 3.00 -> 2.50 step
STEP_DETAIL_MODEL_RADIUS = 6.0
STEP_DETAIL_CENTER = (0.045, 0.145)
ISOMETRIC_VIEW_NOTE_XY = (0.345, 0.105)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + mx / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


def _place_feature_crop(
    adapter: Any,
    orientation: str,
    *,
    model_xyz: tuple[float, float, float],
    model_radius_mm: float,
    view_xy: tuple[float, float],
    scale: tuple[int, int],
    label: str,
) -> Any:
    """Place a real model view with ``model_xyz`` fixed at ``view_xy``."""
    view = place_view(adapter, str(SOURCE), orientation, *view_xy, scale=scale)
    draw = adapter.currentModel
    sw_view = _early_bound(view, "IView")
    projected = model_point_in_view(adapter, view, model_xyz, label=label)
    position = tuple(float(value) for value in (sw_view.Position or ()))
    if len(position) < 2:
        raise RuntimeError(f"feature crop has no view position ({label})")
    translated = (
        position[0] + view_xy[0] - projected[0],
        position[1] + view_xy[1] - projected[1],
    )
    if not sw_view.SetViewPosition(double_array(list(translated)), False):
        raise RuntimeError(f"failed to position feature crop ({label})")
    draw.EditRebuild3()

    crop_center = model_point_in_view(adapter, view, model_xyz, label=label)
    crop_radius = model_radius_mm * scale[0] / scale[1] / 1000.0
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate feature crop ({label})")
    draw.ClearSelection2(True)
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    centre = _sheet_to_view_sketch(adapter, view, crop_center, label=label)
    rim = _sheet_to_view_sketch(
        adapter,
        view,
        (crop_center[0] + crop_radius, crop_center[1]),
        label=label,
    )
    if (
        sketch_manager.CreateCircle(
            float(centre[0]),
            float(centre[1]),
            0.0,
            float(rim[0]),
            float(rim[1]),
            0.0,
        )
        is None
    ):
        raise RuntimeError(f"failed to create feature crop ({label})")
    if int(sw_view.Crop2(False, True, 5)) != 1:
        raise RuntimeError(f"failed to crop feature view ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return view

# The ring crop exposes no stable selectable sketch dimensions.  Its adjacent
# note names the detail and scale and carries the part-owned manufacturing sizes.
RING_GEOMETRY_NOTE = f"{RING_GEOMETRY_SPEC_NOTE}\nSCALE 2:1"
RING_GEOMETRY_NOTE_XY = (
    RING_DETAIL_CENTER[0]
    + RING_DETAIL_MODEL_RADIUS * RING_DETAIL_SCALE[0] / 1000.0
    + 0.006,
    RING_DETAIL_CENTER[1] - 0.005,
)

# The head crop likewise exposes no stable selectable edges on this seat.
HEAD_GEOMETRY_NOTE = "\n".join(
    (
        "DETAIL B AS-CAST HEAD — SCALE 3:1",
        f"WIDTH {HEAD_WIDTH:.2f}",
        f"HEIGHT {HEAD_HEIGHT:.2f} FROM SHOULDER ROOT",
        f"SHOULDER RISE {HEAD_SHOULDER_RISE:.2f}",
        f"CROWN {CROWN_CALLOUT}",
    )
)
HEAD_GEOMETRY_NOTE_XY = (0.285, 0.262)

# The step crop has no stable derived edges either.  Keep its enlarged model
# profile and state both spec-owned axial thicknesses immediately below it.
STEP_THICKNESS_NOTE = "\n".join(
    (
        "DETAIL C THICKNESS STEP — SCALE 3:1",
        f"RING REGION THICKNESS {RING_THICKNESS:.2f}",
        f"SHANK REGION THICKNESS {SHANK_THICKNESS:.2f}",
    )
)
STEP_THICKNESS_NOTE_XY = (
    STEP_DETAIL_CENTER[0],
    (
        STEP_DETAIL_CENTER[1]
        - STEP_DETAIL_MODEL_RADIUS
        * STEP_DETAIL_SCALE[0]
        / STEP_DETAIL_SCALE[1]
        / 1000.0
        - 0.014
    ),
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

    ring_detail = _place_feature_crop(
        adapter,
        "*Front",
        model_xyz=(0.0, 0.0, 0.0),
        model_radius_mm=RING_DETAIL_MODEL_RADIUS,
        view_xy=RING_DETAIL_CENTER,
        scale=RING_DETAIL_SCALE,
        label="strap ring detail",
    )
    head_detail = _place_feature_crop(
        adapter,
        "*Front",
        model_xyz=(0.0, HEAD_DETAIL_MODEL_CY / 1000.0, 0.0),
        model_radius_mm=HEAD_DETAIL_MODEL_RADIUS,
        view_xy=HEAD_DETAIL_CENTER,
        scale=HEAD_DETAIL_SCALE,
        label="as-cast head detail",
    )
    step_detail = _place_feature_crop(
        adapter,
        "*Left",
        model_xyz=(0.0, STEP_DETAIL_MODEL_CY / 1000.0, 0.0),
        model_radius_mm=STEP_DETAIL_MODEL_RADIUS,
        view_xy=STEP_DETAIL_CENTER,
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

    # DETAIL B, the as-cast head: the derived view exposes no stable edges on
    # this seat, so every head-profile size renders from the shared spec beside
    # the useful enlarged geometry.
    if (
        add_note(
            adapter,
            HEAD_GEOMETRY_NOTE,
            *HEAD_GEOMETRY_NOTE_XY,
        )
        is None
    ):
        raise RuntimeError("failed to add as-cast head geometry note")

    # DETAIL C's cropped model view keeps the actual step visible while both
    # region-specific thicknesses remain in the shared-spec note below it.
    if (
        add_note(
            adapter,
            STEP_THICKNESS_NOTE,
            *STEP_THICKNESS_NOTE_XY,
        )
        is None
    ):
        raise RuntimeError("failed to add thickness-step geometry note")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.036)
    add_property_linked_note(adapter, "Isometric View Note", *ISOMETRIC_VIEW_NOTE_XY)

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
