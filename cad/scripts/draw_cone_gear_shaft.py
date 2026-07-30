r"""Create the curated machinist drawing for the stepped cone gear shaft."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    PmiDrawingPlacement,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    project_part_pmi,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED
from cone_gear_shaft_spec import (
    GEOMETRIC_CONTROLS,
    JOURNAL_DIA,
    JOURNAL_END,
    SECTION_DIAS,
    PART_DATUMS,
    SHAFT_LENGTH,
)
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
# Side (silhouette) view: the full 251.91 mm stepped profile at 1:1, axis
# horizontal. The end view shows the journal and four seat diameters as
# concentric circles (the tip is nearest the *Front camera), enlarged so the
# 0.79 mm tip circle is legible. SIDE_CENTER x is 0.155: the
# profile spans +/-0.127 m about its centre.  At x=0.155 it lands at
# x~0.028..0.282, clear of the left border and high enough to stay above the
# bottom-right title block.  The end view enlarges the tiny tip diameter.
SIDE_CENTER = (0.155, 0.215)
END_CENTER = (0.055, 0.105)
ISO_CENTER = (0.360, 0.200)

# Axial step stations (extrude depths Sec{i}End), all measured from the
# large-end datum face: baseline dimensioning, shortest nearest the part.
SIDE_KEEP = {
    "Sec0End": (0.205, 0.208),
    "Sec1End": (0.190, 0.196),
    "Sec2End": (0.175, 0.184),
    "Sec3End": (0.160, 0.172),
    "Sec4End": (0.145, 0.160),
}
# Section seat/journal diameters, staggered right of the end view.
END_KEEP = {
    "Sec0Dia": (0.105, 0.144),
    "Sec1Dia": (0.105, 0.132),
    "Sec2Dia": (0.105, 0.120),
    "Sec3Dia": (0.105, 0.108),
    "Sec4Dia": (0.105, 0.096),
}
# No callout overrides: the shared fit band is toleranced on each model
# dimension by build_cone_gear_shaft (cone_gear_shaft_spec.SECTION_DIA_BAND).
DIMENSION_CALLOUTS: dict[str, str] = {}
# The bearing journal is a metric 12.2308 fit dimension and needs four decimal
# places; the other four are exact inch conversions and display three.
DIMENSION_PRECISION = {name: 4 if name == "Sec0Dia" else 3 for name in END_KEEP}


def _outer_end_edge(adapter: Any, view: Any) -> Any:
    """Return the largest visible circular model edge in the end view."""
    circles: list[tuple[float, Any]] = []
    for edge in visible_view_entities(view, 1, label="gear-shaft end edges"):
        edge = _early_bound(edge, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        params = curve.CircleParams
        if params is not None and len(params) >= 7:
            circles.append((float(params[6]), edge))
    if not circles:
        raise RuntimeError("end view has no visible circular model edge")
    return max(circles, key=lambda item: item[0])[1]


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
    radius_mm, face = min(candidates, key=lambda item: abs(item[0] - target_radius))
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
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)
    for label, view in (("side", side), ("end", end), ("iso", iso)):
        outline = adapter._attempt(
            lambda v=view: adapter._get_attr_or_call(v, "GetOutline")
        )
        _telemetry.info(f"PROBE {label} outline={outline}")
    pivot_face = _cylindrical_face(adapter, side, JOURNAL_DIA)
    tip_face = _cylindrical_face(adapter, side, SECTION_DIAS[-1])
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

    pivot_edge = _outer_end_edge(adapter, end)
    # Leader anchor points for the surface-finish symbols (sheet meters).
    big_end_x = SIDE_CENTER[0] + SHAFT_LENGTH / 2000.0
    pivot_top = (big_end_x - 0.020, SIDE_CENTER[1] + SECTION_DIAS[0] / 2000.0)
    tip_top = (
        SIDE_CENTER[0] - SHAFT_LENGTH / 2000.0 + 0.016,
        SIDE_CENTER[1] + SECTION_DIAS[-1] / 2000.0,
    )
    # GD&T is model PMI (cone_gear_shaft_spec.PART_DATUMS/GEOMETRIC_CONTROLS,
    # authored by build_cone_gear_shaft) — project it and place it where the
    # hand-authored symbols used to sit. Which VIEW receives each annotation
    # depends on its attachment (a datum tag only lands in a view aligned
    # with its face), and the projection fails loud on any mismatch. The datum tag keeps its placement derived from
    # the journal's actual small-end station, not a frozen sheet number.
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=side,
                position=(big_end_x - JOURNAL_END / 1000.0, 0.252),
                entity=pivot_face,
                attachment_type="FACE",
            ),
            "journal_cylindricity": PmiDrawingPlacement(
                view=end,
                position=(0.150, 0.142),
                edge_entity=pivot_edge,
            ),
            "tip_runout": PmiDrawingPlacement(
                view=side,
                position=(0.070, 0.245),
                attachment_xy=tip_top,
                attachment_type="SILHOUETTE",
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="cone gear shaft PMI",
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.255, 0.242),
        roughness_ra=MACHINED,
        label="pivot journal finish",
        entity_type="FACE",
        entity=pivot_face,
        leader_attach_xy=pivot_top,
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.102, 0.240),
        roughness_ra=MACHINED,
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
