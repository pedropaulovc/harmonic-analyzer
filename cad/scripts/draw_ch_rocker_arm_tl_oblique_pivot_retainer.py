"""Native model-derived MHA-CH-06-TL-31 fitted top-retainer drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, dimension_name, place_view

from _check import check
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing, stamp_drawing_summary
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _printed_limits import limits
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import ch_rocker_arm_tl_oblique_pivot_retainer_spec as part_spec

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_pivot_retainer"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
FACE_CENTER = (0.100, 0.175)
PROFILE_CENTER = (0.240, 0.175)
ISO_CENTER = (0.365, 0.190)
ISO_SCALE = (2, 1)
ISO_NOTE_XY = (0.328, 0.235)
# Review 88c6d: WasherBore's text ran over the left border (r1-r3 clarity.1);
# it stands below-right of the face view, wholly inside the free paper left
# of the profile view. Both diameters keep one arrow on the rim nearest their
# text (set_near_side_diameter), so neither line runs through the centre or
# crosses the other (r1/r2 clarity.2).
FACE_KEEP = {"WasherDia": (0.050, 0.225), "WasherBore": (0.140, 0.120)}
NEAR_SIDE_DIAMETERS = ("WasherDia", "WasherBore")
# Review 88c6d (r1-r3 clarity.3/4): each thickness's text stood between its
# own extension lines and the other's. The supply allowance's text stands
# left of its extension lines, the reference thickness's right of the part
# and below the Ra symbol; only their dimension lines run out to the text.
PROFILE_KEEP = {"FinishedThickness": (0.303, 0.115), "SupplyThickness": (0.190, 0.230)}

part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))
requirement(
    "outside", kind="boss", faces=(CylinderFace(part_spec.OUTER_DIA),), requirements=("dia",),
    fields={"axis": ([0.0, 0.0, 1.0], ("__frame__",)), "dia": (limits(part_spec.OUTER_DIA, part_spec.DRAWING_PRECISION_BY_NAME["WasherDia"]), ("OUTER_DIA",)), "dia_nominal": (part_spec.OUTER_DIA, ("OUTER_DIA",))},
    precision={"dia": part_spec.DRAWING_PRECISION_BY_NAME["WasherDia"]},
)
requirement(
    "journal_clearance", kind="hole", faces=(CylinderFace(part_spec.BORE_DIA),), requirements=("dia", "note"),
    fields={"axis": ([0.0, 0.0, 1.0], ("__frame__",)), "dia": (limits(part_spec.BORE_DIA, part_spec.DRAWING_PRECISION_BY_NAME["WasherBore"], part_spec.DRILLED_BAND), ("BORE_DIA", "DRILLED_BAND")), "dia_nominal": (part_spec.BORE_DIA, ("BORE_DIA",)), "note": (part_spec.DIMENSION_CALLOUTS["WasherBore"], ("DIMENSION_CALLOUTS",))},
    precision={"dia": part_spec.DRAWING_PRECISION_BY_NAME["WasherBore"]},
)
requirement(
    "fitted_top", kind="face", faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.THICKNESS),), requirements=("note",),
    fields={"normal": ([0.0, 0.0, 1.0], ("__frame__",)), "note": (part_spec.DIMENSION_CALLOUTS["FinishedThickness"], ("DIMENSION_CALLOUTS", "RUNNING_GAP_MIN", "RUNNING_GAP_MAX", "CROSS_HOLE_FROM_SEAT", "CROSS_HOLE_DIA", "CLEVIS_DIA", "CARRIER_THICKNESS", "THICKNESS"))},
)
requirement(
    "carrier_running_face", kind="face", faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),), requirements=("finish_ra",),
    fields={"normal": ([0.0, 0.0, -1.0], ("__frame__",)), "finish_ra": (part_spec.MACHINED_UM, ("SURFACE_FINISHES",))},
    precision={"finish_ra": 1},
)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open fitted retainer", await adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note")
    read_required_properties(adapter.currentModel, ("Revision", "Title", *required), required=required)
    drawing_model, _sheet = new_project_drawing(adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing_model, {0: "Rocker Oblique Pivot Retainer Drawing", 1: "Harmonic Analyzer shop fixture drawing", 2: "Harmonic Analyzer Project", 3: "MHA-CH-06-TL-31; fitted removable top washer", 4: "Native model-derived ASME B manufacturing drawing"})
    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    profile = place_view(adapter, str(SOURCE), "*Right", *PROFILE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (face, profile, iso):
        set_hidden_lines_removed(adapter, view)
    annotations = []
    for view, keep, label in ((face, FACE_KEEP, "washer face"), (profile, PROFILE_KEEP, "fitted profile and supply allowance")):
        annotations.extend(curate_view_dimensions(adapter, view, keep=keep, view_label=label, dimensions_by_feature=part_spec.DRAWING_DIMENSIONS))
    assert_imported_precision(adapter, annotations, part_spec.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, part_spec.DIMENSION_CALLOUTS, location="below")
    for name in NEAR_SIDE_DIAMETERS:
        matches = [annotation for annotation in annotations if dimension_name(adapter, annotation) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        set_near_side_diameter(matches[0], f"retainer {name}")
    rebuild_drawing(adapter, label="retainer diameters' near-side leaders")
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to mark the retainer bore centre")
    def projected(point, label):
        return model_point_in_view(adapter, profile, tuple(value / 1000.0 for value in point), label=label)
    add_surface_finish(adapter, profile, edge_xy=projected((0.0, 0.0, 0.0), "carrier-side face"), symbol_xy=projected((0.0, -17.0, -5.0), "carrier-face finish symbol"), control=surface_finish_by_key(part_spec.SURFACE_FINISHES, "carrier_running_face"), label="retainer running face")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return await finalize_drawing(adapter, OUTPUTS, pdf_title="Rocker Oblique Pivot Retainer Drawing", scale=SHEET_SCALE, layout=SPEC.layout)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
