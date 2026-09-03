r"""Create the curated machinist drawing for the v2 cone pivot post.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
machined casting carries no datums, no feature-control frames, no roughness
symbols and no basic dimensions -- the turned diameters and the crank bore
carry their bands on the model dimensions, the inclined journal is defined
by a leader note from the view, and the title block governs the rest.
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
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_pivot_post_spec import (
    ATTACHMENT_CBORE_DEPTH,
    ATTACHMENT_THRU_DIA,
    BLOCK_HEIGHT,
    BORE_DIA,
    BORE_HEIGHT,
    CONE_BOSS_DIA,
    CRANK_BORE_HEIGHT,
    HEAD_HEIGHT,
    INCLINE_DEG,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_pivot_post"]
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
_S = SHEET_SCALE[0] / 1000.0

# Third-angle: the front elevation carries the height and crank journal; the
# plan carries the two body diameters and mounting-hole pattern.
FRONT_CENTER = (0.105, 0.145)
TOP_CENTER = (0.105, 0.235)
ISO_CENTER = (0.340, 0.145)


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


FRONT_KEEP = {
    "MainBodyHt": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1]),
    "HeadHt": (FRONT_CENTER[0] + 0.055, _front_y(BLOCK_HEIGHT - HEAD_HEIGHT / 2.0)),
    "CrankAxisY": (FRONT_CENTER[0] - 0.035, _front_y(CRANK_BORE_HEIGHT / 2.0)),
    "CrankBossDia": (
        FRONT_CENTER[0] + 0.050,
        _front_y(CRANK_BORE_HEIGHT) + 0.018,
    ),
    "CrankBoreDia": (
        FRONT_CENTER[0] + 0.050,
        _front_y(CRANK_BORE_HEIGHT) - 0.012,
    ),
}
TOP_KEEP = {
    "MainBodyDia": (TOP_CENTER[0] - 0.040, TOP_CENTER[1]),
    "HeadDia": (TOP_CENTER[0] + 0.045, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "CrankBoreDia": "BORE THRU",
}
# Three decimals only on the fitted features -- the three turned diameters
# and the crank bore carry their bands on the model dimension
# (build_cone_pivot_post); the heights stay at the two-place block tolerance.
DIMENSION_PRECISION = {
    "MainBodyDia": 3,
    "HeadDia": 3,
    "CrankBossDia": 3,
    "CrankBoreDia": 3,
}


def _attachment_thru_rims(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the west and east attachment-hole through rims in the plan view.

    Both rims are the circular edges where the through hole meets the
    counterbore floor (radius ``ATTACHMENT_THRU_DIA / 2`` at model
    ``y = BLOCK_HEIGHT - ATTACHMENT_CBORE_DEPTH``), picked by ENTITY so the
    callout and the centre-to-centre dimension never depend on a sheet
    coordinate.  Sorted by model X so the pair is (west, east).
    """
    radius_mm = ATTACHMENT_THRU_DIA / 2.0
    center_y_mm = BLOCK_HEIGHT - ATTACHMENT_CBORE_DEPTH
    rims: list[tuple[float, Any]] = []
    for edge in visible_view_entities(view, 1, label="pivot-post attachment rims"):
        edge = _early_bound(edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        if abs(params[6] - radius_mm) > 0.01 or abs(params[1] - center_y_mm) > 0.01:
            continue
        rims.append((params[0], edge))
    if len(rims) != 2:
        raise RuntimeError(
            f"plan view shows {len(rims)} attachment through rims at radius "
            f"{radius_mm:.4f} mm, expected 2"
        )
    rims.sort(key=lambda item: item[0])
    return rims[0][1], rims[1][1]


@_telemetry.traced("drawing.attachment_spacing")
def _add_attachment_spacing(adapter: Any, view: Any, west_rim: Any, east_rim: Any) -> Any:
    """Centre-to-centre dimension between the two attachment holes.

    Entity-selected (the arbor-pedestal recipe): a sheet-picked dimension
    re-anchored to the circle centres was found to dangle.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate plan view for attachment spacing")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, west_rim), (True, east_rim)):
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        entity = _early_bound(raw_entity, "IEntity")
        if not entity.Select4(append, selection_data):
            raise RuntimeError("failed to select an attachment through rim")
    display = draw.AddHorizontalDimension2(TOP_CENTER[0], TOP_CENTER[1] - 0.026, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to create the attachment spacing dimension")
    set_arc_endpoints_to_center(adapter, display, label="attachment spacing")
    return display


@_telemetry.traced("drawing.bore_rim_scan")
def _bore_rim_edge(adapter: Any, view: Any, *, diameter_mm: float) -> Any:
    """Return a rim adjacent to the unique cylindrical bore of this diameter."""
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[Any] = []
    for edge in visible_view_entities(view, 1, label="pivot-post bore rims"):
        edge = _early_bound(edge, "IEdge")
        for face in edge.GetTwoAdjacentFaces2() or []:
            if face is None:
                continue
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            if abs(float(surface.CylinderParams[6]) - expected_radius_m) > 1e-6:
                continue
            candidates.append(edge)
            break
    if not candidates:
        raise RuntimeError(
            f"view has no rim adjacent to bore diameter {diameter_mm:.5f} mm"
        )
    return candidates[0]


def _format_table_note(note: Any, *, label: str) -> Any:
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} has no text format")
    text_format.CharHeight = 0.0025
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size {label}")
    return note


@_telemetry.traced("drawing.table_note", label_param="label")
def _add_table_note(adapter: Any, text: str, x: float, y: float, *, label: str) -> Any:
    note = add_note(adapter, text, x, y)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    return _format_table_note(note, label=label)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-pivot-post source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Pivot Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "bossed cast-iron post; inclined cone journal; crank journal",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (policy rule 7).
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    annotations = [*front_annotations, *top_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    for view in (front, top):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError("failed to add ASME center marks")

    # The inclined journal has no native dimension on the sheet (its sketch
    # plane is swung about the post axis), so a leader note from its rim
    # defines it: boss and bore sizes, axis height above the foot, and the
    # swing angle from the crank-bore axis.  The bore is the surface the
    # cone gear shaft turns in, so it is bored, not drilled.
    journal_entity = _bore_rim_edge(adapter, front, diameter_mm=BORE_DIA)
    add_attached_note(
        adapter,
        front,
        text=(
            # Short lines: the note is left-anchored at x=0.155 and must
            # stay clear of the isometric at x=0.340 in the same band.
            f"CONE BOSS <MOD-DIAM>{CONE_BOSS_DIA:.3f}\n"
            f"JOURNAL <MOD-DIAM>{BORE_DIA:.4f} BORE THRU\n"
            f"AXIS {BORE_HEIGHT:.3f} ABOVE FOOT\n"
            f"{INCLINE_DEG:.3f} DEG FROM CRANK BORE ABOUT POST AXIS"
        ),
        entity=journal_entity,
        note_xy=(0.155, _front_y(BORE_HEIGHT) + 0.020),
        label="inclined-journal size",
    )
    _add_table_note(
        adapter,
        "UPPER PLAN SCALE 1:2 (+X RIGHT, +Z DOWN)",
        0.070,
        0.263,
        label="upper-plan view label",
    )
    # Attachment counterbores: the native Hole Wizard callout carries the
    # through, counterbore and depth sizes; its prefix says the process
    # (7.142 = 0.2812 in is the 9/32 drill).  The centre-to-centre spacing
    # is an entity-selected dimension below the plan, in the gap above the
    # elevation.
    west_rim, east_rim = _attachment_thru_rims(adapter, top)
    add_native_hole_callout(
        adapter,
        top,
        callout_xy=(0.175, 0.250),
        label="attachment counterbores",
        edge=east_rim,
        process="9/32 DRILL",
    )
    _add_attachment_spacing(adapter, top, west_rim, east_rim)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.068)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Pivot Post Manufacturing Drawing",
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
