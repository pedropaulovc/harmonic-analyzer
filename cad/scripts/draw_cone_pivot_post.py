r"""Create the curated machinist drawing for the v2 cone pivot post.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
machined casting carries no datums, no feature-control frames, no roughness
symbols and no basic dimensions.  The two running bores carry their bands on
the model dimensions; the as-cast body, collar and boss diameters print two
places under the title block.  The inclined journal is defined in SECTION
A-A, cut in the plan NORMAL to the journal axis, where its bore imports as a
true circle with its band and its axis height is dimensioned from the foot.
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
    add_attached_note,
    add_native_hole_callout,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
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
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
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
# plan carries the two body diameters, the boss length and the mounting-hole
# pattern; SECTION A-A (normal to the journal axis) sits between the elevation
# and the isometric.
FRONT_CENTER = (0.105, 0.145)
TOP_CENTER = (0.105, 0.235)
SECTION_CENTER = (0.235, 0.145)
ISO_CENTER = (0.340, 0.145)
# Half-length of the cutting line, model mm: past the collar radius (21.4)
# and the crank boss corner (21.7 along the trace) with margin.
SECTION_HALF_SPAN_MM = 35.0


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


FRONT_KEEP = {
    "MainBodyHt": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1]),
    "CrankAxisY": (FRONT_CENTER[0] - 0.035, _front_y(CRANK_BORE_HEIGHT / 2.0)),
    # Collar height on the right, close to the body: its span (59.4..86)
    # overlaps the crank-axis height's (0..72.7), so the two cannot share a
    # side without a witness line crossing a dimension line.
    "HeadHt": (FRONT_CENTER[0] + 0.032, _front_y(BLOCK_HEIGHT - HEAD_HEIGHT / 2.0)),
    # Crank boss and bore leadered from BELOW-right so both leaders pass under
    # the collar-height dimension line (the crank boss lies within its span).
    "CrankBoreDia": (FRONT_CENTER[0] + 0.040, _front_y(CRANK_BORE_HEIGHT) - 0.022),
    "CrankBossDia": (FRONT_CENTER[0] + 0.065, _front_y(CRANK_BORE_HEIGHT) - 0.047),
}
TOP_KEEP = {
    # Body diameter leadered from the lower-left, clear of the boss-length
    # dimension that runs beside the journal axis on the left of the plan.
    "MainBodyDia": (TOP_CENTER[0] - 0.055, TOP_CENTER[1] - 0.015),
    "HeadDia": (TOP_CENTER[0] + 0.045, TOP_CENTER[1]),
    # Cone boss length (mid-plane extrude along the journal axis): an aligned
    # dimension left of the plan, parallel to the 12.5-degree axis.
    "ConeBossLen": (TOP_CENTER[0] - 0.030, TOP_CENTER[1] + 0.007),
}
# Journal bore: imported into the axis-normal section (its sketch plane is
# parallel to the cut), leadered to the right of the section.
SECTION_BORE_TEXT_OFFSET = (0.040, 0.006)
SECTION_AXIS_HEIGHT_OFFSET_X = -0.014
DIMENSION_CALLOUTS = {
    "CrankBoreDia": "BORE THRU",
    "JournalBoreDia": "BORE THRU",
    "MainBodyDia": "BODY",
    "HeadDia": "COLLAR",
}
# Three decimals only on the two fitted bores (bands on the model dimension,
# build_cone_pivot_post); the as-cast diameters and every height print two
# places under the title block.
DIMENSION_PRECISION = {
    "MainBodyDia": 2,
    "HeadDia": 2,
    "CrankBossDia": 2,
    "CrankBoreDia": 3,
    "JournalBoreDia": 3,
}
CONE_BOSS_NOTE_XY = (0.150, 0.110)
ATTACHMENT_CALLOUT_XY = (0.175, 0.250)
PLAN_LABEL_XY = (0.070, 0.263)


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


def _journal_axis(rim_edge: Any) -> tuple[float, float, float]:
    """Unit direction of the journal axis, read off the rim's circle (model)."""
    curve = _early_bound(_early_bound(rim_edge, "IEdge").GetCurve(), "ICurve")
    if not curve.IsCircle():
        raise RuntimeError("journal rim edge is not circular")
    params = tuple(float(value) for value in curve.CircleParams)
    axis = params[3:6]
    norm = math.sqrt(sum(value * value for value in axis))
    if norm < 1e-9 or abs(axis[1]) > 0.05:
        raise RuntimeError(f"journal axis {axis!r} is not horizontal")
    return (axis[0] / norm, axis[1] / norm, axis[2] / norm)


def _journal_trace(axis: tuple[float, float, float]) -> tuple[float, float, float]:
    """Horizontal unit direction lying IN the journal-normal plane (model)."""
    trace = (axis[2], 0.0, -axis[0])
    norm = math.hypot(trace[0], trace[2])
    return (trace[0] / norm, 0.0, trace[2] / norm)


@_telemetry.traced("drawing.journal_section")
def _cut_journal_section(adapter: Any, top: Any, trace: tuple[float, float, float]) -> Any:
    """SECTION A-A: the plan cut through the post axis, normal to the journal.

    The cutting line is the plane's trace in the plan: through the post axis
    (origin) along ``trace``, past the casting on both sides.  Its direction
    comes from the model (the journal rim's circle axis), never from the sign
    of INCLINE_DEG, which the build passes negated against a reversed plane.
    """
    span = SECTION_HALF_SPAN_MM / 1000.0
    start = model_point_in_view(
        adapter,
        top,
        (-trace[0] * span, 0.0, -trace[2] * span),
        label="journal section start",
    )
    end = model_point_in_view(
        adapter,
        top,
        (trace[0] * span, 0.0, trace[2] * span),
        label="journal section end",
    )
    return create_section_view(
        adapter,
        top,
        line_start=start,
        line_end=end,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 1),
        label="journal-normal section",
    )


@_telemetry.traced("drawing.journal_axis_height")
def _add_journal_axis_height(
    adapter: Any, section: Any, trace: tuple[float, float, float]
) -> Any:
    """Journal axis height above the foot, dimensioned in SECTION A-A.

    The cut face's foot edge and the bore circle are section geometry, not
    model edges, so both are picked by SHEET coordinate projected from model
    points that lie in the cutting plane (``model_point_in_view`` maps through
    the section's own transform, whatever side it looks from).
    """
    foot_xy = model_point_in_view(
        adapter,
        section,
        (trace[0] * 0.008, 0.0, trace[2] * 0.008),
        label="section foot edge",
    )
    bore_r = BORE_DIA / 2000.0
    rim_xy = model_point_in_view(
        adapter,
        section,
        (trace[0] * bore_r, BORE_HEIGHT / 1000.0, trace[2] * bore_r),
        label="section bore rim",
    )
    center_xy = model_point_in_view(
        adapter, section, (0.0, BORE_HEIGHT / 1000.0, 0.0), label="section bore centre"
    )
    outline = tuple(
        float(value)
        for value in adapter._get_attr_or_call(section, "GetOutline")
    )
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate SECTION A-A for the axis height")
    draw.ClearSelection2(True)
    for index, (x, y) in enumerate((foot_xy, rim_xy)):
        if not draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, index > 0, 0, null_callout(), 0
        ):
            raise RuntimeError(
                f"failed to select section edge {index} at sheet ({x:g}, {y:g})"
            )
    display = draw.AddVerticalDimension2(
        outline[0] + SECTION_AXIS_HEIGHT_OFFSET_X,
        (foot_xy[1] + center_xy[1]) / 2.0,
        0.0,
    )
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to create the journal axis height dimension")
    set_arc_endpoints_to_center(adapter, display, label="journal axis height")
    return display


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

    # The journal axis, read off the model: the rim of the O12.2808 bore.
    journal_entity = _bore_rim_edge(adapter, front, diameter_mm=BORE_DIA)
    trace = _journal_trace(_journal_axis(journal_entity))
    section = _cut_journal_section(adapter, top, trace)
    # Hidden lines stay ON in every orthographic view (policy rule 7).
    for view in (front, top, section):
        set_hidden_lines_visible(adapter, view)

    # The section claims its bore first: SolidWorks imports each marked model
    # dimension into ONE view only (draw_pinion_bracket).
    bore_center = model_point_in_view(
        adapter, section, (0.0, BORE_HEIGHT / 1000.0, 0.0), label="journal bore"
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep={
            "JournalBoreDia": (
                bore_center[0] + SECTION_BORE_TEXT_OFFSET[0],
                bore_center[1] + SECTION_BORE_TEXT_OFFSET[1],
            )
        },
        view_label="section",
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    annotations = [*section_annotations, *front_annotations, *top_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    for view in (front, top, section):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError("failed to add ASME center marks")

    _add_journal_axis_height(adapter, section, trace)
    # The as-cast cone boss: flagged from its end rim in the elevation (the
    # boss merges into the body in the section, so it has no edge there).
    boss_entity = _bore_rim_edge(adapter, front, diameter_mm=CONE_BOSS_DIA)
    add_attached_note(
        adapter,
        front,
        text=f"BOSS <MOD-DIAM>{CONE_BOSS_DIA:.2f} AS CAST",
        entity=boss_entity,
        note_xy=CONE_BOSS_NOTE_XY,
        label="cone boss size",
    )
    _add_table_note(
        adapter,
        "UPPER PLAN SCALE 1:2 (+X RIGHT, +Z DOWN)",
        *PLAN_LABEL_XY,
        label="upper-plan view label",
    )
    # Attachment counterbores: the native Hole Wizard callout carries the
    # through, counterbore and depth sizes; its prefix says the process
    # (7.142 = 0.2812 in is the 9/32 drill).  The centre-to-centre spacing
    # is an entity-selected dimension below the plan, in the gap above the
    # elevation; the notes state the pair is centred on the post axis.
    west_rim, east_rim = _attachment_thru_rims(adapter, top)
    add_native_hole_callout(
        adapter,
        top,
        callout_xy=ATTACHMENT_CALLOUT_XY,
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
