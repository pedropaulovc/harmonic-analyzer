"""Native model-derived MHA-CH-06-TL-30 captured-flange cap drawing.

Top face shows actual open head pockets and wire channels; underside shows
the flange pocket and integral registers in solid lines. A-A shows the fitted
pocket, B-B the head-seat entry reliefs, and the side view the register ends.
Pocket/aperture centres share the real -X/-Y stock corner; bolt and register
coordinates are ordinary native dimensions from the actual pocket axis.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

from _check import check
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, stamp_drawing_summary
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _printed_limits import limits
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import ch_rocker_arm_tl_oblique_pivot_cap_spec as part_spec

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_pivot_cap"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
TOP_CENTER = (0.090, 0.170)
BOTTOM_CENTER = (0.260, 0.170)
RIGHT_CENTER = (0.365, 0.170)
SECTION_CENTER = (0.265, 0.085)
BOLT_SECTION_CENTER = (0.360, 0.095)
ISO_CENTER = (0.095, 0.052)
ISO_SCALE = (1, 1)
ISO_NOTE_XY = (0.052, 0.095)
TOP_KEEP = {
    "CapWidth": (0.090, 0.118), "CapLength": (0.145, 0.170),
    "CounterboreDia": (0.035, 0.250), "ApertureDia": (0.055, 0.225),
    "ApertureCenterX": (0.078, 0.127), "ApertureCenterY": (0.052, 0.151),
    "WireWidth": (0.137, 0.092),
    "EntryReliefDia": (0.170, 0.115),
}
# The bolts stay on the UNDERSIDE, from the actual visible pocket axis.
# The pocket and aperture's ordinary coordinates share the same stock corner;
# their native extension lines witness the real edges, not a datum frame.
BOTTOM_KEEP = {
    "PocketDia": (0.190, 0.260), "BoltHoleDia": (0.290, 0.260),
    "PocketCenterX": (0.273, 0.099), "PocketCenterY": (0.350, 0.152),
    "Bolt1X": (0.249, 0.123), "Bolt3X": (0.273, 0.108),
    "Bolt2X": (0.249, 0.222), "Bolt4X": (0.273, 0.237),
    "Bolt1Y": (0.214, 0.151), "Bolt2Y": (0.191, 0.185),
    "Bolt3Y": (0.311, 0.151), "Bolt4Y": (0.336, 0.185),
    "RegisterDia": (0.190, 0.231),
    "Register1X": (0.225, 0.120), "Register2X": (0.258, 0.253),
    "Register1Y": (0.220, 0.139), "Register2Y": (0.304, 0.201),
}
RIGHT_KEEP = {
    "CounterboreDepth": (0.342, 0.245), "WireDepth": (0.355, 0.122),
    "RegisterProjection": (0.390, 0.145), "RegisterEndChamfer": (0.390, 0.198),
}
SECTION_KEEP = {"CapHeight": (0.315, 0.085), "PocketDepth": (0.215, 0.107)}
BOLT_SECTION_KEEP = {"EntryReliefDepth": (0.405, 0.100)}
SECTION_LINE_MODEL = ((-part_spec.WIDTH / 2.0 - 4.0, 0.0, 0.0), (part_spec.WIDTH / 2.0 + 4.0, 0.0, 0.0))
BOLT_SECTION_LINE_MODEL = tuple(
    (x, min(y for _, y in part_spec.BOLT_POINTS), 0.0)
    for x in (-part_spec.WIDTH / 2.0 - 4.0, part_spec.WIDTH / 2.0 + 4.0)
)

part_metadata(
    precision_sources=("DRAWING_PRECISION_BY_NAME",),
    fields={
        "material.thickness": (part_spec.TOTAL_HEIGHT, ("TOTAL_HEIGHT", "HEIGHT", "REGISTER_PROJECTION")),
        "volume_mm3": (part_spec.VOLUME_MM3, ("VOLUME_MM3", "nominal_volume_mm3", "nominal_register_volume_mm3", "nominal_entry_relief_volume_mm3")),
    },
)
requirement(
    "block_seat", kind="face", faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),), requirements=("width", "length", "thickness"),
    fields={"normal": ([0.0, 0.0, -1.0], ("__frame__",)), "width": (limits(part_spec.WIDTH, part_spec.OUTLINE_PLACES), ("WIDTH",)), "width_nominal": (part_spec.WIDTH, ("WIDTH",)), "length": (limits(part_spec.LENGTH, part_spec.OUTLINE_PLACES), ("LENGTH",)), "length_nominal": (part_spec.LENGTH, ("LENGTH",)), "thickness": (limits(part_spec.HEIGHT, part_spec.HEIGHT_PLACES), ("HEIGHT",)), "thickness_nominal": (part_spec.HEIGHT, ("HEIGHT",))},
    precision={"width": part_spec.OUTLINE_PLACES, "length": part_spec.OUTLINE_PLACES, "thickness": part_spec.HEIGHT_PLACES},
)
requirement(
    "flange_chamber", kind="pocket", faces=(CylinderFace(part_spec.POCKET_DIA),), requirements=("dia", "station", "width", "note"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
        "station": (limits(part_spec.WIDTH / 2.0, part_spec.CENTER_LOCATION_PLACES), ("WIDTH", "CENTER_LOCATION_PLACES")),
        "station_nominal": (part_spec.WIDTH / 2.0, ("WIDTH",)),
        "width": (limits(part_spec.LENGTH / 2.0, part_spec.CENTER_LOCATION_PLACES), ("LENGTH", "CENTER_LOCATION_PLACES")),
        "width_nominal": (part_spec.LENGTH / 2.0, ("LENGTH",)),
        "dia": (limits(part_spec.POCKET_DIA, part_spec.DRAWING_PRECISION_BY_NAME["PocketDia"], part_spec.POCKET_BAND), ("POCKET_DIA", "POCKET_BAND")),
        "dia_nominal": (part_spec.POCKET_DIA, ("POCKET_DIA",)),
        "note": ("\n".join((part_spec.DIMENSION_CALLOUTS["PocketDepth"], part_spec.CENTER_LOCATION_NOTE)), ("DIMENSION_CALLOUTS", "CHAMBER_EXCESS_MIN", "CHAMBER_EXCESS_MAX", "LOWER_GAP_MIN", "LOWER_GAP_MAX", "CENTER_LOCATION_NOTE")),
    },
    precision={"dia": part_spec.DRAWING_PRECISION_BY_NAME["PocketDia"], "station": part_spec.CENTER_LOCATION_PLACES, "width": part_spec.CENTER_LOCATION_PLACES},
)
requirement(
    "journal_aperture", kind="hole", faces=(CylinderFace(part_spec.APERTURE_DIA),), requirements=("dia", "station", "width", "note"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
        "station": (limits(part_spec.WIDTH / 2.0, part_spec.CENTER_LOCATION_PLACES), ("WIDTH", "CENTER_LOCATION_PLACES")),
        "station_nominal": (part_spec.WIDTH / 2.0, ("WIDTH",)),
        "width": (limits(part_spec.LENGTH / 2.0, part_spec.CENTER_LOCATION_PLACES), ("LENGTH", "CENTER_LOCATION_PLACES")),
        "width_nominal": (part_spec.LENGTH / 2.0, ("LENGTH",)),
        "dia": (limits(part_spec.APERTURE_DIA, part_spec.DRAWING_PRECISION_BY_NAME["ApertureDia"], part_spec.APERTURE_BAND), ("APERTURE_DIA", "APERTURE_BAND")),
        "dia_nominal": (part_spec.APERTURE_DIA, ("APERTURE_DIA",)),
        "note": ("\n".join((part_spec.DIMENSION_CALLOUTS["ApertureDia"], part_spec.CENTER_LOCATION_NOTE)), ("DIMENSION_CALLOUTS", "CENTER_LOCATION_NOTE")),
    },
    precision={"dia": part_spec.DRAWING_PRECISION_BY_NAME["ApertureDia"], "station": part_spec.CENTER_LOCATION_PLACES, "width": part_spec.CENTER_LOCATION_PLACES},
)
for _index, (_x, _y) in enumerate(part_spec.BOLT_POINTS, 1):
    requirement(
        f"cap_bolt_{_index}", kind="hole", faces=(CylinderFace(part_spec.HOLE_DIA, contains_x_mm=_x, contains_y_mm=_y),), requirements=("dia", "station", "width", "note"),
        fields={
            "at": ([_x, _y, 0.0], ("BOLT_POINTS", "__frame__")),
            "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
            "dia": (limits(part_spec.HOLE_DIA, part_spec.DRAWING_PRECISION_BY_NAME["BoltHoleDia"], part_spec.DRILLED_BAND), ("HOLE_DIA", "DRILLED_BAND")),
            "dia_nominal": (part_spec.HOLE_DIA, ("HOLE_DIA",)),
            # Signed model X/Y from the actual pocket axis: the consumer's
            # station/width bands retain the ordinary coordinate tolerances.
            "station": (limits(_x, part_spec.POSITION_PLACES), ("BOLT_POINTS",)),
            "station_nominal": (_x, ("BOLT_POINTS",)),
            "width": (limits(_y, part_spec.POSITION_PLACES), ("BOLT_POINTS",)),
            "width_nominal": (_y, ("BOLT_POINTS",)),
            "note": (
                "\n".join((part_spec.DIMENSION_CALLOUTS["BoltHoleDia"], part_spec.DIMENSION_CALLOUTS[f"Bolt{_index}X"])),
                ("DIMENSION_CALLOUTS", "SCREW_MAJOR_LIMITS", "SCREW_THREAD_SOURCE_URL"),
            ),
        },
        precision={"dia": part_spec.DRAWING_PRECISION_BY_NAME["BoltHoleDia"], "station": part_spec.POSITION_PLACES, "width": part_spec.POSITION_PLACES},
    )
    requirement(
        f"head_recess_{_index}", kind="counterbore", faces=(CylinderFace(part_spec.COUNTERBORE_DIA, contains_x_mm=_x, contains_y_mm=_y),), requirements=("dia", "depth", "note"),
        # The controlled depth interval, bound STEP face and imported depth
        # dimension retain the machining depth; no separate nominal is needed.
        fields={"axis": ([0.0, 0.0, 1.0], ("__frame__",)), "dia": (limits(part_spec.COUNTERBORE_DIA, part_spec.COUNTERBORE_DIAMETER_PLACES), ("COUNTERBORE_DIA",)), "dia_nominal": (part_spec.COUNTERBORE_DIA, ("COUNTERBORE_DIA",)), "depth": (limits(part_spec.COUNTERBORE_DEPTH, part_spec.COUNTERBORE_DEPTH_PLACES), ("COUNTERBORE_DEPTH",)), "note": ("\n".join((part_spec.DIMENSION_CALLOUTS["CounterboreDia"], part_spec.DIMENSION_CALLOUTS["CounterboreDepth"])), ("DIMENSION_CALLOUTS",))},
        precision={"dia": part_spec.COUNTERBORE_DIAMETER_PLACES, "depth": part_spec.COUNTERBORE_DEPTH_PLACES},
    )
    requirement(
        f"head_entry_relief_{_index}", kind="counterbore",
        faces=(CylinderFace(
            part_spec.ENTRY_RELIEF_DIA, contains_x_mm=_x, contains_y_mm=_y,
            contains_z_mm=part_spec.HEIGHT - part_spec.COUNTERBORE_DEPTH - part_spec.ENTRY_RELIEF_DEPTH / 2.0,
        ),),
        requirements=("dia", "depth", "note"),
        fields={
            "at": ([_x, _y, part_spec.HEIGHT - part_spec.COUNTERBORE_DEPTH], ("BOLT_POINTS", "HEIGHT", "COUNTERBORE_DEPTH", "__frame__")),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "dia": (limits(part_spec.ENTRY_RELIEF_DIA, part_spec.ENTRY_RELIEF_DIAMETER_PLACES, part_spec.ENTRY_RELIEF_BAND), ("ENTRY_RELIEF_DIA", "ENTRY_RELIEF_BAND")),
            "dia_nominal": (part_spec.ENTRY_RELIEF_DIA, ("ENTRY_RELIEF_DIA",)),
            "depth": (limits(part_spec.ENTRY_RELIEF_DEPTH, part_spec.ENTRY_RELIEF_DEPTH_PLACES), ("ENTRY_RELIEF_DEPTH", "ENTRY_RELIEF_DEPTH_PLACES")),
            "note": ("\n".join((part_spec.DIMENSION_CALLOUTS["EntryReliefDia"], part_spec.DIMENSION_CALLOUTS["EntryReliefDepth"])), ("DIMENSION_CALLOUTS", "SCREW_SKU")),
        },
        precision={"dia": part_spec.ENTRY_RELIEF_DIAMETER_PLACES, "depth": part_spec.ENTRY_RELIEF_DEPTH_PLACES},
    )
requirement(
    "wire_channel", kind="pocket", faces=(PlanarFace((0.0, 1.0, 0.0), min(y for _, y in part_spec.BOLT_POINTS) - part_spec.CHANNEL_WIDTH / 2.0),), requirements=("width", "depth", "note"),
    fields={"width": (limits(part_spec.CHANNEL_WIDTH, part_spec.CHANNEL_PLACES), ("CHANNEL_WIDTH",)), "width_nominal": (part_spec.CHANNEL_WIDTH, ("CHANNEL_WIDTH",)), "depth": (limits(part_spec.CHANNEL_DEPTH, part_spec.CHANNEL_PLACES), ("CHANNEL_DEPTH",)), "note": ("\n".join((part_spec.DIMENSION_CALLOUTS["WireWidth"], part_spec.DIMENSION_CALLOUTS["WireDepth"])), ("DIMENSION_CALLOUTS",))},
    precision={"width": part_spec.CHANNEL_PLACES, "depth": part_spec.CHANNEL_PLACES},
)

for _index, (_x, _y) in enumerate(part_spec.REGISTER_POINTS, 1):
    requirement(
        f"integral_register_{_index}", kind="boss",
        faces=(CylinderFace(part_spec.REGISTER_DIA, contains_x_mm=_x, contains_y_mm=_y, contains_z_mm=-part_spec.REGISTER_PROJECTION / 2.0),),
        requirements=("dia", "station", "width", "length", "note"),
        fields={
            "at": ([_x, _y, 0.0], ("REGISTER_POINTS", "__frame__")),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "dia": (limits(part_spec.REGISTER_DIA, 2, part_spec.REGISTER_BAND), ("REGISTER_DIA", "REGISTER_BAND")),
            "dia_nominal": (part_spec.REGISTER_DIA, ("REGISTER_DIA",)),
            "station": (limits(_x, part_spec.REGISTER_LOCATION_PLACES), ("REGISTER_POINTS", "REGISTER_LOCATION_PLACES")),
            "station_nominal": (_x, ("REGISTER_POINTS",)),
            "width": (limits(_y, part_spec.REGISTER_LOCATION_PLACES), ("REGISTER_POINTS", "REGISTER_LOCATION_PLACES")),
            "width_nominal": (_y, ("REGISTER_POINTS",)),
            "length": (limits(part_spec.REGISTER_PROJECTION, part_spec.REGISTER_PROJECTION_PLACES), ("REGISTER_PROJECTION", "REGISTER_PROJECTION_PLACES")),
            "length_nominal": (part_spec.REGISTER_PROJECTION, ("REGISTER_PROJECTION",)),
            "note": ("\n".join((part_spec.DIMENSION_CALLOUTS["RegisterDia"], part_spec.DIMENSION_CALLOUTS[f"Register{_index}X"], part_spec.DIMENSION_CALLOUTS["RegisterProjection"])), ("DIMENSION_CALLOUTS",)),
        },
        precision={"dia": 2, "station": part_spec.REGISTER_LOCATION_PLACES, "width": part_spec.REGISTER_LOCATION_PLACES, "length": part_spec.REGISTER_PROJECTION_PLACES},
    )
    requirement(
        f"register_end_chamfer_{_index}", kind="chamfer",
        faces=(ConeFace(45.0, contains_x_mm=_x),),
        requirements=("length", "note"),
        fields={
            "at": ([_x, _y, -part_spec.REGISTER_PROJECTION], ("REGISTER_POINTS", "REGISTER_PROJECTION", "__frame__")),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "length": ([0.0, part_spec.REGISTER_END_CHAMFER_MAX], ("REGISTER_END_CHAMFER_MAX",)),
            "length_nominal": (part_spec.REGISTER_END_CHAMFER_MAX, ("REGISTER_END_CHAMFER_MAX",)),
            "note": (part_spec.DIMENSION_CALLOUTS["RegisterEndChamfer"], ("DIMENSION_CALLOUTS", "nominal_register_volume_mm3")),
        },
        precision={"length": part_spec.DRAWING_PRECISION_BY_NAME["RegisterEndChamfer"]},
    )


def _project(adapter, view, point, label):
    return model_point_in_view(adapter, view, tuple(value / 1000.0 for value in point), label=label)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open capture cap", await adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note")
    read_required_properties(adapter.currentModel, ("Revision", "Title", *required), required=required)
    drawing_model, _sheet = new_project_drawing(adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing_model, {0: "Rocker Oblique Pivot Capture Cap Drawing", 1: "Harmonic Analyzer shop fixture drawing", 2: "Harmonic Analyzer Project", 3: "MHA-CH-06-TL-30; steel captured-flange cap", 4: "Native model-derived ASME B manufacturing drawing"})
    top = place_view(adapter, str(SOURCE), "*Front", *TOP_CENTER, scale=VIEW_SCALE)
    bottom = place_view(adapter, str(SOURCE), "*Back", *BOTTOM_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    line = [_project(adapter, bottom, point, "cap section line") for point in SECTION_LINE_MODEL]
    section = create_section_view(adapter, bottom, line_start=line[0], line_end=line[1], view_xy=SECTION_CENTER, section_label="A", scale=VIEW_SCALE, label="cap central pocket section")
    bolt_line = [_project(adapter, bottom, point, "cap bolt-row section line") for point in BOLT_SECTION_LINE_MODEL]
    bolt_section = create_section_view(adapter, bottom, line_start=bolt_line[0], line_end=bolt_line[1], view_xy=BOLT_SECTION_CENTER, section_label="B", scale=VIEW_SCALE, label="cap flat-bottom underhead entry relief section")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, bottom, right, section, bolt_section, iso):
        set_hidden_lines_removed(adapter, view)
    annotations = []
    for view, keep, label in ((top, TOP_KEEP, "top head and wire access"), (bottom, BOTTOM_KEEP, "underside flange chamber and integral registers"), (right, RIGHT_KEEP, "open-mouth depths and register free ends"), (section, SECTION_KEEP, "A-A fitted flange chamber"), (bolt_section, BOLT_SECTION_KEEP, "B-B flat-bottom underhead entry relief")):
        annotations.extend(curate_view_dimensions(adapter, view, keep=keep, view_label=label, dimensions_by_feature=part_spec.DRAWING_DIMENSIONS))
    assert_imported_precision(adapter, annotations, part_spec.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, part_spec.DIMENSION_CALLOUTS, location="below")
    for view in (top, bottom):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError("failed to mark cap bore/pattern centres")
    add_surface_finish(adapter, section, edge_xy=_project(adapter, section, (22.0, 0.0, 0.0), "block seating face"), symbol_xy=_project(adapter, section, (25.0, 0.0, -7.0), "block-seat finish"), control=surface_finish_by_key(part_spec.SURFACE_FINISHES, "block_seat"), label="cap block seating face")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return await finalize_drawing(adapter, OUTPUTS, pdf_title="Rocker Oblique Pivot Capture Cap Drawing", scale=SHEET_SCALE, layout=SPEC.layout)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
