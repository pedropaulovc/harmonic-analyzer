r"""Create the curated machinist drawing for the stepped cone gear shaft.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
stepped shaft carries no datums and no feature-control frames -- every land
is a size tolerance on the model dimension, and the one roughness symbol
sits on the bearing journal that turns in the pivot post.  It is dimensioned
as it sits in the lathe (policy rule 7): every diameter reads as a linear
diameter on its own cylindrical segment of the side view -- the journal and
the 3/8 seat on the 1:1 silhouette, the three small tip lands in DETAIL A
(3:1), where they are legible -- and every station chains from the big-end
face.  There is no end view: from either end the shoulders hide each other,
and a diameter dimensioned to an occluded circle is exactly what the
machinist review rejected.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    create_detail_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_gear_shaft_spec import (
    JOURNAL_DIA,
    SECTION_DIAS,
    SECTION_ENDS,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


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
DETAIL_SCALE = (3, 1)
# Side (silhouette) view: the full 208 mm stepped profile at 1:1, axis
# horizontal, big end on the right.  SIDE_CENTER x is 0.155: the profile
# spans +/-0.104 m about its centre, clear of the left border and high enough
# to stay above the bottom-right title block.  DETAIL A (3:1) of the tip
# lands sits under the side view's station chain, left of the title block;
# the isometric top right.
SIDE_CENTER = (0.155, 0.215)
DETAIL_CENTER = (0.110, 0.098)
ISO_CENTER = (0.360, 0.200)

# DETAIL A boundary on the side view: centred on the axis at the middle of
# the 1/8 in land, wide enough to take in the end of the 1/4 in land and 23
# mm of the 1/32 in tip (model mm / metres on the 1:1 side view).
DETAIL_MODEL_CENTER_Z = (SECTION_ENDS[2] + SECTION_ENDS[3]) / 2.0 + 7.0
DETAIL_MODEL_RADIUS = 16.0
DETAIL_RADIUS = DETAIL_MODEL_RADIUS * SHEET_SCALE[0] / 1000.0

# Axial step stations (extrude depths Sec{i}End), all measured from the
# large-end datum face: baseline dimensioning, shortest nearest the part.
SIDE_STATION_KEEP = {
    "Sec0End": (0.205, 0.208),
    "Sec1End": (0.190, 0.196),
    "Sec2End": (0.175, 0.184),
    "Sec3End": (0.160, 0.172),
    "Sec4End": (0.145, 0.160),
}
# Diameters on their own lands as linear diameters: the dimension line
# crosses the land at the given station, the text stands above the shaft.
# Side view (1:1): the journal and the 3/8 in seat.
SIDE_DIAMETER_STATIONS_MM = {
    "Sec0Dia": SECTION_ENDS[0] / 2.0,
    "Sec1Dia": (SECTION_ENDS[0] + SECTION_ENDS[1]) / 2.0,
}
SIDE_DIAMETER_TEXT_Y = SIDE_CENTER[1] + 0.021
# DETAIL A (3:1): the 1/4, 1/8 and 1/32 in lands, texts staggered so the
# neighbouring two-line stacked-tolerance values never touch (model mm along
# the axis, sheet metres above the axis).
DETAIL_DIAMETER_STATIONS_MM = {
    "Sec2Dia": ((SECTION_ENDS[1] + SECTION_ENDS[2]) / 2.0, 0.030),
    "Sec3Dia": ((SECTION_ENDS[2] + SECTION_ENDS[3]) / 2.0, 0.018),
    "Sec4Dia": (SECTION_ENDS[3] + 11.0, 0.030),
}
# No callout overrides: the shared fit band is toleranced on each model
# dimension by build_cone_gear_shaft (cone_gear_shaft_spec.SECTION_DIA_BAND).
DIMENSION_CALLOUTS: dict[str, str] = {}
# Every land is a fitted diameter (h band on the model dimension): three
# decimals say "hold it" -- the journal's 12.2308 nominal rounds to 12.231
# beside the post bore's 12.281, the four inch seats are exact conversions.
DIMENSION_PRECISION = {
    name: 3 for name in (*SIDE_DIAMETER_STATIONS_MM, *DETAIL_DIAMETER_STATIONS_MM)
}
# Roughness symbol at the big end, right of the journal's diameter
# dimension, its leader down to the journal OD just inboard of the end face.
JOURNAL_FINISH_SYMBOL_XY = (0.275, 0.245)
JOURNAL_FINISH_ATTACH_INBOARD_MM = 10.0
# Notes right of DETAIL A, above the title block; the isometric stays above
# them.
NOTES_XY = (0.225, 0.110)


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


def _axis_point(adapter: Any, view: Any, z_mm: float, *, label: str) -> tuple[float, float]:
    """Sheet point of the shaft axis at station ``z_mm`` in ``view``."""
    return model_point_in_view(adapter, view, (0.0, 0.0, z_mm / 1000.0), label=label)


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
            0: "Cone Gear Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear shaft; stepped turned steel; gear seats",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    # DETAIL A: the three tip lands at 3:1, where the 0.79 mm tip is a
    # dimensionable land instead of a hairline (policy rule 7).
    detail = create_detail_view(
        adapter,
        side,
        center=_axis_point(adapter, side, DETAIL_MODEL_CENTER_Z, label="detail centre"),
        radius=DETAIL_RADIUS,
        view_xy=DETAIL_CENTER,
        detail_label="A",
        scale=DETAIL_SCALE,
        label="tip lands detail",
    )
    # Hidden lines stay ON in every orthographic view (policy rule 7).
    for view in (side, detail):
        set_hidden_lines_visible(adapter, view)
    pivot_face = _cylindrical_face(adapter, side, JOURNAL_DIA)
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0] + 0.050, SIDE_CENTER[1]),
        label="shaft longitudinal axis",
        entity=pivot_face,
    )

    # The detail claims its three lands FIRST: SolidWorks imports each marked
    # model dimension into one view only (draw_pinion_bracket, 2026-09-02).
    # Positions come from the detail's own projection of the axis stations.
    detail_keep = {}
    for name, (station_mm, above) in DETAIL_DIAMETER_STATIONS_MM.items():
        axis_xy = _axis_point(adapter, detail, station_mm, label=name)
        detail_keep[name] = (axis_xy[0], axis_xy[1] + above)
    detail_annotations = curate_view_dimensions(
        adapter, detail, keep=detail_keep, view_label="detail"
    )
    side_keep = dict(SIDE_STATION_KEEP)
    for name, station_mm in SIDE_DIAMETER_STATIONS_MM.items():
        axis_xy = _axis_point(adapter, side, station_mm, label=name)
        side_keep[name] = (axis_xy[0], SIDE_DIAMETER_TEXT_Y)
    side_annotations = curate_view_dimensions(
        adapter, side, keep=side_keep, view_label="side"
    )
    annotations = [*detail_annotations, *side_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)

    # Leader anchor for the journal's surface-finish symbol: the journal OD
    # (top silhouette) just inboard of the big-end face.
    journal_top = _axis_point(
        adapter, side, JOURNAL_FINISH_ATTACH_INBOARD_MM, label="journal finish attach"
    )
    pivot_top = (journal_top[0], journal_top[1] + SECTION_DIAS[0] / 2000.0)
    add_surface_finish(
        adapter,
        side,
        symbol_xy=JOURNAL_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_journal"),
        label="pivot journal finish",
        entity_type="FACE",
        entity=pivot_face,
        leader_attach_xy=pivot_top,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

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
