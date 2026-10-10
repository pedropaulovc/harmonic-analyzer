r"""Create the curated machinist drawing for the fulcrum-shaft end keeper.

The SLDPRT remains authoritative.  This recipe supplies only the keeper's
views, dimension layout, hole callout, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the bracket is ~16.5 x 32.2 x 14); the isometric
carries an explicit 1:1 override so it stays clear of the title block.  Four
views: the side profile (front), the plan (top, which carries the
counterbored screw-hole and crown set-screw tap callouts), the end view
(right, which carries the width / shaft-axis-height / crown / bore stack),
and the isometric.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_fulcrum_keeper.py ch-fulcrum-keeper
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    _edge_endpoint_key,
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from ch_fulcrum_keeper_spec import (
    CBORE_DIA_MM,
    CROWN_TOP_Y,
    DRAWING_DIMENSIONS,
    FOOT_TIP_X,
    GEOMETRIC_TOLERANCES_MM,
    LUG_HALF_T,
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

# Model bbox centres the projected views are laid out around.
_X_MID = (-LUG_HALF_T + FOOT_TIP_X) / 2.0  # 5.25
_Y_MID = CROWN_TOP_Y / 2.0  # 16.1 (crown top 32.2)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - _X_MID) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - _Y_MID) * SHEET_SCALE[0] / 1000.0


@_telemetry.traced("drawing.pick_lug_edge")
def _visible_outboard_lug_edge(adapter: Any, view: Any) -> Any:
    """Return the deterministic front-view edge at the lug's outboard face."""
    target_x = LUG_HALF_T / 1000.0
    candidates: list[tuple[tuple[float, ...], Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="fulcrum front edges"):
        edge = _early_bound(raw_edge, "IEdge")
        endpoints = _edge_endpoint_key(adapter, edge)
        if endpoints is None:
            continue
        x0, y0, z0, x1, y1, z1 = endpoints
        if abs(x0 - target_x) > 1e-6 or abs(x1 - target_x) > 1e-6:
            continue
        if abs(y1 - y0) < 0.005 or abs(z1 - z0) > 1e-6:
            continue
        geometry = tuple(sorted((endpoints[:3], endpoints[3:])))
        candidates.append((geometry[0] + geometry[1], edge))

    span = _telemetry.trace.get_current_span()
    span.set_attribute("matched", len(candidates))
    if not candidates:
        raise RuntimeError("front view has no vertical edge at the lug outboard face")
    return min(candidates, key=lambda candidate: candidate[0])[1]


# Handy picks derived from the layout above.
SEAT_EDGE_Y = _front_y(0.0)  # the foot seating face (datum A)
LUG_FACE_X = _front_x(LUG_HALF_T)  # outboard lug face (datum B)
HOLE_X_SHEET = _front_x(SCREW_X)  # screw-hole station, shared by the top view
CBORE_R_SHEET = CBORE_DIA_MM * SHEET_SCALE[0] / 2000.0
# The crown tap seen end-on in the plan, on the lug mid-plane (x = 0).
TAP_X_SHEET = _front_x(0.0)
TAP_R_SHEET = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC) * SHEET_SCALE[0] / 2000.0
SET_SCREW_PROCESS = "TAP TO BORE"

# Per-view survivors of the marked-dimension import: parametric name ->
# sheet position.  The front view carries the lug thickness and the crown
# tap's station off the outer lug face (both stacked above the crown), the
# foot length below the seat and the foot height right of the foot tip; the
# end view carries the width plus the shaft-axis / crown stack and the
# reamed bore.
FRONT_KEEP = {
    "SetScrewLocation": (_front_x(1.5), 0.170),
    "LugThickness": (_front_x(0.0), 0.178),
    "FootLength": (_front_x(SCREW_X), 0.086),
    "FootRise": (0.140, 0.106),
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
    drawing_model, sheet = new_project_drawing(
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

    # The tap station is owned by a reference sketch the part saves blanked
    # (ch_fulcrum_keeper_spec.REFERENCE_SKETCHES); the hidden-owner curate
    # shows it in the front view that dimensions it.
    curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )

    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Native datum/GD&T annotations.  Datum A is the foot seating face (the
    # part sits on the rail top face and the screw clamps normal to it),
    # attached on the END view's edge-on seat line beside the flatness frame:
    # below the front view the seat line is boxed in by the FootLength extension
    # lines.  Datum B is the outboard lug face (the foot screw's station).
    add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - 0.006, SEAT_EDGE_Y),
        symbol_xy=(RIGHT_CENTER[0] - 0.006, SEAT_EDGE_Y - 0.010),
        datum="A",
        label="keeper seating face",
    )
    # Datum B is attached to the actual vertical model edge at x=+3 mm.  It is
    # not a silhouette edge: the front-view outline scanner returns only the
    # horizontal crown/foot transitions, while the locating edge is a visible
    # model edge.  Resolve it by model-space endpoints so view projection drift
    # cannot move the annotation to another edge.
    lug_edge = _visible_outboard_lug_edge(adapter, front)
    add_datum_feature(
        adapter,
        front,
        edge_entity=lug_edge,
        symbol_xy=(LUG_FACE_X + 0.014, _front_y(12.0)),
        datum="B",
        label="outboard lug face",
    )
    # Flatness rides the END view's edge-on seat line: in the front view the
    # seat is boxed in by the FootLength extension lines, so any leader to it
    # crosses them.  Attach right of the LugRise extension and datum A,
    # frame below-right of the view.
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.005, SEAT_EDGE_Y),
        frame_xy=(0.248, 0.088),
        characteristic="flatness",
        tolerance=GEOMETRIC_TOLERANCES_MM["foot seating face flatness"],
        label="seating face flatness",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=(HOLE_X_SHEET, TOP_CENTER[1] + CBORE_R_SHEET),
        frame_xy=(0.052, 0.252),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["screw-hole position"],
        datums=("A", "B"),
        diameter=True,
        label="screw-hole position",
    )
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
