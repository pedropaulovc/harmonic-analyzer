"""Native model-derived MHA-CH-06-TL-30 captured-flange cap drawing.

Access and envelope, fitted sections, cap-screw locations, and integral
registers have separate full-scale sheets. The underside views show the actual
flange pocket, bolt holes and registers in solid lines. A-A shows the fitted
pocket and B-B the head-seat entry reliefs.
The register sheet's aligned XZ (*Top) projection retains the register
free-end chamfer's native dimension; it cannot transfer into the YZ view.
Pocket/aperture centres share the real -X/-Y stock corner; bolt and register
coordinates remain ordinary native dimensions from the actual pocket axis.

Paper-layout repair measured from the 20261021T085834832Z native PDF/audit:
keep full callout blocks inside the border and off their own witnesses, the
section-sheet heading/context, and the register side-view edge. Coordinates
below are requested placements, not a claim of native after-fix acceptance.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import add_note, dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, stamp_drawing_summary
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
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
SHEET_NAMES = ("ACCESS", "SECTIONS", "BOLT-LOCATIONS", "REGISTERS")
TOP_CENTER = (0.180, 0.190)
RIGHT_CENTER = (0.335, TOP_CENTER[1])
BOTTOM_CENTER = (0.115, 0.170)
SECTION_CENTER = (0.300, 0.180)
BOLT_SECTION_CENTER = (0.300, 0.100)
BOLT_CENTER = (0.210, 0.170)
REGISTER_FRONT_CENTER = (0.115, 0.175)
REGISTER_BOTTOM_CENTER = (0.320, 0.175)
REGISTER_RIGHT_CENTER = (0.205, REGISTER_FRONT_CENTER[1])
# The native circular-rim chamfer imports in XZ, not the YZ side view.
# Its undimensioned *Front parent context keeps this a true third-angle set.
REGISTER_END_CENTER = (REGISTER_FRONT_CENTER[0], 0.235)
ISO_CENTER = (0.080, 0.059)
ISO_SCALE = (1, 1)
ISO_NOTE_XY = (0.025, 0.110)
SHEET_HEADING_XY = (0.025, 0.260)
# The long head, aperture and relief callouts fan out left of their rims.
# Ordinary centre coordinates and the mouth-width lane occupy the right/bottom.
TOP_KEEP = {
    "CapWidth": (0.180, 0.110), "CapLength": (0.285, 0.190),
    "CounterboreDia": (0.065, 0.175), "ApertureDia": (0.080, 0.245),
    "ApertureCenterX": (0.1675, 0.140), "ApertureCenterY": (0.225, 0.175),
    "WireWidth": (0.245, 0.120),
    "EntryReliefDia": (0.075, 0.130),
}
RIGHT_KEEP = {"CounterboreDepth": (0.280, 0.245), "WireDepth": (0.370, 0.145)}
# A dedicated underside owns the corner-to-pocket coordinates and fitted
# sections; neither bolt nor register callout shoulders share these lanes.
BOTTOM_KEEP = {
    "PocketDia": (0.060, 0.233),
    "PocketCenterX": (0.1275, 0.115), "PocketCenterY": (0.070, 0.15125),
}
SECTION_KEEP = {"CapHeight": (0.365, 0.180), "PocketDepth": (0.330, 0.240)}
BOLT_SECTION_KEEP = {"EntryReliefDepth": (0.365, 0.140)}
# Signed bolt coordinates still witness the actual pocket axis. Allocate lanes
# for the entire three-row block, not just its numeric anchor: the native left
# Y blocks extended 61 mm leftward and the lower right X/Y rows touched.
BOLT_KEEP = {
    "BoltHoleDia": (0.300, 0.080),
    "Bolt1X": (0.300, 0.100), "Bolt3X": (0.120, 0.095),
    "Bolt2X": (0.300, 0.245), "Bolt4X": (0.120, 0.215),
    "Bolt1Y": (0.285, 0.135), "Bolt2Y": (0.285, 0.215),
    "Bolt3Y": (0.100, 0.135), "Bolt4Y": (0.100, 0.240),
}
REGISTER_KEEP = {
    "RegisterDia": (0.260, 0.115),
    "Register1X": (0.370, 0.095), "Register2X": (0.310, 0.240),
    "Register1Y": (0.350, 0.135), "Register2Y": (0.240, 0.228),
}
REGISTER_PROJECTION_KEEP = {"RegisterProjection": (0.160, 0.110)}
REGISTER_END_KEEP = {"RegisterEndChamfer": (0.220, 0.252)}
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


def _assert_pocket_corner_callout(adapter: Any, annotations: list[Any]) -> None:
    """Read the local manufacturing MAX on the real chamber size dimension."""
    pocket = [annotation for annotation in annotations
              if dimension_name(adapter, annotation) == "PocketDia"]
    if len(pocket) != 1:
        raise RuntimeError(f"expected one native chamber size dimension, found {len(pocket)}")
    annotation = _early_bound(pocket[0], "IAnnotation")
    display = adapter._attempt(lambda: annotation.GetSpecificAnnotation())
    if display is None:
        raise RuntimeError("native chamber size dimension has no display annotation")
    display = _early_bound(display, "IDisplayDimension")
    actual = str(adapter._attempt(lambda: display.GetText(4)) or "").replace("\r", "")
    if actual != part_spec.DIMENSION_CALLOUTS["PocketDia"]:
        raise RuntimeError("native chamber floor/wall corner instruction did not persist")


def _project(adapter, view, point, label):
    return model_point_in_view(adapter, view, tuple(value / 1000.0 for value in point), label=label)


def _assert_template_center_marks(view: Any, *, expected: int, label: str) -> None:
    """Keep the template's one mark per visible circular feature, not a second set."""
    marks = _early_bound(view, "IView").GetAnnotationsByType(13)  # swCenterMarkSym
    if not isinstance(marks, (tuple, list)) or len(marks) != expected:
        count = len(marks) if isinstance(marks, (tuple, list)) else marks
        raise RuntimeError(f"{label}: expected {expected} template centre marks, got {count!r}")


def _annotate_views(adapter: Any, views: tuple[tuple[Any, dict[str, tuple[float, float]], str], ...]) -> None:
    """Apply each sheet's subset of the same model-owned precision/callouts."""
    annotations = []
    names = set()
    for view, keep, label in views:
        set_hidden_lines_removed(adapter, view)
        annotations.extend(curate_view_dimensions(
            adapter, view, keep=keep, view_label=label,
            dimensions_by_feature=part_spec.DRAWING_DIMENSIONS,
        ))
        names.update(keep)
    assert_imported_precision(adapter, annotations, {
        name: part_spec.DRAWING_PRECISION_BY_NAME[name] for name in names
    })
    set_dimension_callouts(adapter, annotations, {
        name: text for name, text in part_spec.DIMENSION_CALLOUTS.items() if name in names
    }, location="below")
    if "PocketDia" in names:
        _assert_pocket_corner_callout(adapter, annotations)


def _activate_sheet(adapter: Any, drawing: Any, name: str, heading: str) -> None:
    if not drawing.ActivateSheet(name):
        raise RuntimeError(f"failed to activate cap drawing sheet {name!r}")
    if add_note(adapter, heading, *SHEET_HEADING_XY) is None:
        raise RuntimeError(f"failed to label cap drawing sheet {name!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open capture cap", await adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note")
    read_required_properties(adapter.currentModel, ("Revision", "Title", *required), required=required)
    drawing_model, _sheet = new_project_drawing(adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing_model, {0: "Rocker Oblique Pivot Capture Cap Drawing", 1: "Harmonic Analyzer shop fixture drawing", 2: "Harmonic Analyzer Project", 3: "MHA-CH-06-TL-30; steel captured-flange cap", 4: "Native model-derived ASME B manufacturing drawing"})
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="capture-cap manufacturing sheets")
    drawing = _early_bound(drawing_model, "IDrawingDoc")

    _activate_sheet(adapter, drawing, SHEET_NAMES[0], "ACCESS AND ENVELOPE")
    top = place_view(adapter, str(SOURCE), "*Front", *TOP_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    _annotate_views(adapter, (
        (top, TOP_KEEP, "top head and wire access"),
        (right, RIGHT_KEEP, "open-mouth depths"),
    ))
    set_hidden_lines_removed(adapter, iso)
    _assert_template_center_marks(top, expected=1 + len(part_spec.BOLT_POINTS), label="top access")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    _activate_sheet(adapter, drawing, SHEET_NAMES[1], "FITTED CHAMBER AND ENTRY RELIEFS - UNDERSIDE")
    bottom = place_view(adapter, str(SOURCE), "*Back", *BOTTOM_CENTER, scale=VIEW_SCALE)
    line = [_project(adapter, bottom, point, "cap section line") for point in SECTION_LINE_MODEL]
    section = create_section_view(adapter, bottom, line_start=line[0], line_end=line[1], view_xy=SECTION_CENTER, section_label="A", scale=VIEW_SCALE, label="cap central pocket section")
    bolt_line = [_project(adapter, bottom, point, "cap bolt-row section line") for point in BOLT_SECTION_LINE_MODEL]
    bolt_section = create_section_view(adapter, bottom, line_start=bolt_line[0], line_end=bolt_line[1], view_xy=BOLT_SECTION_CENTER, section_label="B", scale=VIEW_SCALE, label="cap flat-bottom underhead entry relief section")
    _annotate_views(adapter, (
        (bottom, BOTTOM_KEEP, "underside flange chamber"),
        (section, SECTION_KEEP, "A-A fitted flange chamber"),
        (bolt_section, BOLT_SECTION_KEEP, "B-B flat-bottom underhead entry relief"),
    ))
    underside_centres = 1 + len(part_spec.BOLT_POINTS) + len(part_spec.REGISTER_POINTS)
    _assert_template_center_marks(bottom, expected=underside_centres, label="fitted-chamber underside")
    add_surface_finish(adapter, section, edge_xy=_project(adapter, section, (22.0, 0.0, 0.0), "block seating face"), symbol_xy=_project(adapter, section, (25.0, 0.0, -7.0), "block-seat finish"), control=surface_finish_by_key(part_spec.SURFACE_FINISHES, "block_seat"), label="cap block seating face")

    _activate_sheet(adapter, drawing, SHEET_NAMES[2], "CAP-SCREW LOCATIONS - UNDERSIDE")
    bolts = place_view(adapter, str(SOURCE), "*Back", *BOLT_CENTER, scale=VIEW_SCALE)
    _annotate_views(adapter, ((bolts, BOLT_KEEP, "underside cap-screw coordinates"),))
    _assert_template_center_marks(bolts, expected=underside_centres, label="cap-screw underside")

    _activate_sheet(adapter, drawing, SHEET_NAMES[3], "INTEGRAL REGISTERS - UNDERSIDE AND FREE-END PROFILE")
    register_front = place_view(adapter, str(SOURCE), "*Front", *REGISTER_FRONT_CENTER, scale=VIEW_SCALE)
    register_bottom = place_view(adapter, str(SOURCE), "*Back", *REGISTER_BOTTOM_CENTER, scale=VIEW_SCALE)
    register_right = place_view(adapter, str(SOURCE), "*Right", *REGISTER_RIGHT_CENTER, scale=VIEW_SCALE)
    register_ends = place_view(adapter, str(SOURCE), "*Top", *REGISTER_END_CENTER, scale=VIEW_SCALE)
    set_hidden_lines_removed(adapter, register_front)
    _annotate_views(adapter, (
        (register_bottom, REGISTER_KEEP, "underside integral-register coordinates"),
        (register_right, REGISTER_PROJECTION_KEEP, "integral-register projection"),
        (register_ends, REGISTER_END_KEEP, "register free-end XZ profile"),
    ))
    for text, xy in (
        ("TOP FACE", (0.090, 0.125)),
        ("REGISTER FREE ENDS", (0.075, 0.223)),
        ("UNDERSIDE", (0.300, 0.260)),
    ):
        if add_note(adapter, text, *xy) is None:
            raise RuntimeError(f"failed to label register view {text!r}")
    _assert_template_center_marks(register_front, expected=1 + len(part_spec.BOLT_POINTS), label="register front context")
    _assert_template_center_marks(register_bottom, expected=underside_centres, label="register underside")
    return await finalize_drawing(
        adapter, OUTPUTS, pdf_title="Rocker Oblique Pivot Capture Cap Drawing",
        scale=SHEET_SCALE, layout=SPEC.layout, expected_sheet_names=SHEET_NAMES,
        sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
