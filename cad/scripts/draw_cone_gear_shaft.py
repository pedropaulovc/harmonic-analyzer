r"""Create the curated machinist drawing for the stepped cone gear shaft."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_gear_shaft_spec import SECTION_DIAS, SHAFT_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_gear_shaft"]
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
END_VIEW_SCALE = 4.0
# Side (silhouette) view: the full 202.3 mm stepped profile at 1:1, axis
# horizontal. The end view shows all four seat diameters as concentric
# circles (the tip is nearest the *Front camera), enlarged so the 0.79 mm
# tip circle is legible. SIDE_CENTER x is 0.155, not the original 0.115: the
# 202.3 mm profile at 1:1 spans +/-0.101 m about its centre, so at 0.115 its
# tip end reached x~0.014 and the padded view outline crossed the left zone
# border (audit: "left by 1.4 mm"). 0.155 lands the span at x 0.054..0.256 --
# clear of the left border and short of the title block / iso on the right.
SIDE_CENTER = (0.155, 0.215)
END_CENTER = (0.055, 0.105)
ISO_CENTER = (0.360, 0.200)

# Axial step stations (extrude depths Sec{i}End), all measured from the
# large-end datum face: baseline dimensioning, shortest nearest the part.
SIDE_KEEP = {
    "Sec0End": (0.190, 0.196),
    "Sec1End": (0.175, 0.184),
    "Sec2End": (0.160, 0.172),
    "Sec3End": (0.145, 0.160),
}
# Section seat/journal diameters, staggered right of the end view.
END_KEEP = {
    "Sec0Dia": (0.105, 0.132),
    "Sec1Dia": (0.105, 0.120),
    "Sec2Dia": (0.105, 0.108),
    "Sec3Dia": (0.105, 0.096),
}
DIMENSION_CALLOUTS = {name: "+0.00/-0.02" for name in END_KEEP}
# The four diameters are exact inch conversions (0.375/0.25/0.125/0.03125 in);
# 3 decimals so the view matches the notes (9.525, not 9.53).
DIMENSION_PRECISION = {name: 3 for name in END_KEEP}


def _outer_end_edge(adapter: Any, view: Any) -> Any:
    """Return the largest visible circular model edge in the end view."""
    circles: list[tuple[float, Any]] = []
    for edge in visible_view_entities(view, 1, label="gear-shaft end edges"):
        edge = _early_bound(edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = curve.CircleParams
        if params is None or len(params) < 7:
            continue
        circles.append((float(params[6]), edge))
    if not circles:
        raise RuntimeError("end view has no visible circular model edge")
    circles.sort(key=lambda item: item[0])
    _telemetry.info(
        "end-view circular edge radii (mm): "
        + ", ".join(f"{radius * 1000.0:.4f}" for radius, _edge in circles)
    )
    return circles[-1][1]


@_telemetry.traced("drawing.cylindrical_face_scan")
def _cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible cylindrical face for one shaft diameter."""
    candidates: list[tuple[float, Any]] = []
    for face in visible_view_entities(view, 3, label="gear-shaft side faces"):
        face = _early_bound(face, "IFace2")
        surface = face.GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if not surface.IsCylinder():
            continue
        radius_mm = float(surface.CylinderParams[6]) * 1000.0
        candidates.append((radius_mm, face))
    if not candidates:
        raise RuntimeError("side view has no visible cylindrical faces")
    target_radius = diameter_mm / 2.0
    radius_mm, face = min(
        candidates, key=lambda item: abs(item[0] - target_radius)
    )
    if abs(radius_mm - target_radius) > 0.01:
        raise RuntimeError(
            f"no cylindrical face matches radius {target_radius:.4f} mm; "
            f"nearest is {radius_mm:.4f} mm"
        )
    return face


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear-shaft source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Gear Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear shaft; stepped turned steel; gear seats",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(1, 1))
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for label, view in (("side", side), ("end", end), ("iso", iso)):
        outline = adapter._attempt(
            lambda v=view: adapter._get_attr_or_call(v, "GetOutline")
        )
        _telemetry.info(f"PROBE {label} outline={outline}")
    pivot_face = _cylindrical_face(adapter, side, SECTION_DIAS[0])
    tip_face = _cylindrical_face(adapter, side, SECTION_DIAS[3])
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0] + 0.050, SIDE_CENTER[1]),
        label="shaft longitudinal axis",
        entity=pivot_face,
    )
    curate_view_dimensions(adapter, side, keep=SIDE_KEEP, view_label="side")
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    set_dimension_callouts(adapter, end_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, end_annotations, DIMENSION_PRECISION)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    # Sheet geometry the GD&T picks attach to (meters). The end view shows the
    # Ø9.525 pivot journal as its outermost circle; the side view's tip journal
    # silhouette hugs the axis line (half-height 0.79 mm x scale / 2).
    pivot_circle = (
        END_CENTER[0]
        + SECTION_DIAS[0] * END_VIEW_SCALE / (2000.0 * math.sqrt(2.0)),
        END_CENTER[1]
        + SECTION_DIAS[0] * END_VIEW_SCALE / (2000.0 * math.sqrt(2.0)),
    )
    pivot_edge = _outer_end_edge(adapter, end)
    big_end_x = SIDE_CENTER[0] + SHAFT_LENGTH / 2000.0
    pivot_top = (big_end_x - 0.020, SIDE_CENTER[1] + SECTION_DIAS[0] / 2000.0)
    tip_top = (
        SIDE_CENTER[0] - SHAFT_LENGTH / 2000.0 + 0.016,
        SIDE_CENTER[1] + SECTION_DIAS[3] / 2000.0,
    )
    add_datum_feature(
        adapter,
        side,
        symbol_xy=(0.215, 0.252),
        datum="A",
        label="pivot journal datum feature",
        entity_type="FACE",
        entity=pivot_face,
    )
    add_feature_control_frame(
        adapter,
        end,
        frame_xy=(0.150, 0.142),
        characteristic="cylindricity",
        tolerance="0.01",
        label="pivot journal cylindricity",
        entity=pivot_edge,
    )
    add_feature_control_frame(
        adapter,
        side,
        edge_xy=tip_top,
        frame_xy=(0.070, 0.245),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("A",),
        label="tip journal runout",
        # Attach to the cylindrical outline itself.  A face attachment lets
        # SolidWorks terminate the leader at the nearest end corner, which is
        # visually ambiguous between radial runout and end-face runout.
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.230, 0.242),
        roughness_ra="1.6",
        label="pivot journal finish",
        entity_type="FACE",
        entity=pivot_face,
        leader_attach_xy=pivot_top,
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.102, 0.240),
        roughness_ra="1.6",
        label="tip journal finish",
        entity_type="FACE",
        entity=tip_face,
        leader_attach_xy=(tip_top[0] + 0.010, tip_top[1]),
    )

    # Notes block sits lower-left, below the enlarged end view (its bottom
    # ~0.086) and clear of the bottom-right title block; the lines are kept
    # short (spec) so none reaches the title-block x-band.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.072)
    add_property_linked_note(adapter, "End View Note", 0.030, 0.140)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Shaft Manufacturing Drawing",
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
