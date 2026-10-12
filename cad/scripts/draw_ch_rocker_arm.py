r"""Create the curated machinist drawing for the rocker arm.

The SLDPRT remains authoritative.  This recipe supplies only the rocker-arm
views, dimension layout, hole callouts, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The strap is a long thin curved seesaw (~292 mm tip to tip, 16 mm deep, 2.5 mm
thick). The print shows the profile (front), with BASIC radii and height feeding
two unequally disposed surface-profile frames, a 1:1 end view carrying the
strap's thickness and hub length natively, and a 1:4 isometric. Sheet scale 1:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm.py ch-rocker-arm
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

import _config
import _surface_finish
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_spec as rocker
from _feature_requirements import part_metadata, requirement
from _printed_limits import drilled_limits as _drilled_band
from _printed_limits import limits as _band
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame

# The part saves TopEdgeReference hidden (#880): this form shows it in the
# view that imports its dimension.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_layout_collect import check_drawing_layout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _drawing_projection import model_points_in_view
from _drawing_scan import _zoomed_on
from _drawing_selection import _select_view_entity
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _gear_drawing_entities import visible_circle_edge
from _hole_spec import blind_cut_dia_mm, drill_process
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from ch_rocker_arm_notes import (
    DEFAULT_DRAWING_PRECISION,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
)
from ch_rocker_arm_spec import (
    ARM_DEPTH,
    ARM_THICKNESS,
    BOT_END_X,
    CENTER_Y,
    GEOMETRIC_TOLERANCES_MM,
    HUB_DIA,
    HUB_LENGTH,
    PIVOT_HOLE_DIA,
    PIVOT_HOLE_BAND,
    PIVOT_MID_Y,
    R_TOP,
    R_BOTTOM,
    ROD_HOLE_SPEC,
    ROD_HOLE_X,
    ROD_HOLE_Y,
    ROD_TIP_X,
    SURFACE_FINISHES,
    TIP_FACE,
    TOP_ARC_LEN,
    TOP_EDGE_ABOVE_PIVOT,
    TOP_EDGE_BAND,
    TOP_END_X,
    TOP_END_Y,
    _ALPHA_TOP,
)


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front-view model bbox: X symmetric about 0, Y from the centre bottom (0) up to
# the top-arc tip (TOP_END_Y).
_PIVOT_MID_Y = PIVOT_MID_Y
_ROD_HOLE_DIA = blind_cut_dia_mm(ROD_HOLE_SPEC)

_P = rocker_notes.DEFAULT_DRAWING_PRECISION
_AXIS = ((0.0, 0.0, 1.0), ("__frame__",))
_CENTRE = ([0.0, rocker.PIVOT_MID_Y, 0.0], ("PIVOT_MID_Y",))

part_metadata(
    fields={
        "precision": (_P, (("ch_rocker_arm_notes", "DEFAULT_DRAWING_PRECISION"),)),
        "material.thickness": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
    },
    model_sources=("ARM_THICKNESS", "HUB_LENGTH"),
    precision_sources=(("ch_rocker_arm_notes", "DRAWING_PRECISION"), ("ch_rocker_arm_notes", "DEFAULT_DRAWING_PRECISION"), ("ch_rocker_arm_notes", "DRAWING_NOTES"), ("_surface_finish", "ra")),
)
_BBOX_CY = TOP_END_Y / 2.0

FRONT_CENTER = (0.180, 0.175)
RIGHT_CENTER = (0.300, 0.165)
ISO_CENTER = (0.345, 0.205)
# The rod-pin frame approaches the upper-right rim, opposite the drilled-hole
# callout's upper-left approach. Short angular witnesses leave its path clear.
FCF_XY = (0.300, 0.232)

ROD_HOLE = requirement(
    "rod_hole", kind="hole", faces=(CylinderFace(blind_cut_dia_mm(rocker.ROD_HOLE_SPEC)),),
    requirements=("at", "dia", "thru", "position_dia"), fields={
        "at": ([rocker.ROD_HOLE_X, rocker.ROD_HOLE_Y, 0.0], ("ROD_HOLE_X", "ROD_HOLE_Y")),
        "axis": _AXIS, "drill": (rocker.ROD_HOLE_SPEC.size, ("ROD_HOLE_SPEC",)),
        "dia": (_drilled_band(blind_cut_dia_mm(rocker.ROD_HOLE_SPEC), _P), ("ROD_HOLE_SPEC", ("_hole_spec", "NUMBER_DRILL_MM"), ("_drawing_hole_callout", "add_native_hole_callout"))),
        "nominal_dia": (blind_cut_dia_mm(rocker.ROD_HOLE_SPEC), ("ROD_HOLE_SPEC", ("_hole_spec", "NUMBER_DRILL_MM"))),
        "thru": (rocker.ROD_HOLE_SPEC.end == "through_all", ("ROD_HOLE_SPEC", ("_drawing_hole_callout", "add_native_hole_callout"))),
        "position_dia": (float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]), ("GEOMETRIC_TOLERANCES_MM",)),
        "position_datums": (["A", "B", "C"], (("draw_ch_rocker_arm", "build"),)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"at": "unknown", "dia": _P, "position_dia": _P},
)
# The iso caption's top-left, under the iso's right half and right of the end
# view. Beside the end view (0.315, 0.150) it read as that
# view's label, 0.4 mm from HubLength's "+0.05" (r743-p1s-B2 render).
ISO_CAPTION_XY = (0.325, 0.183)

# Re-express the part-owned one-sided height envelope as a normal profile zone:
# no second numeric tolerance lives in the drawing prose. The zero lower limit
# is pinned by the rocker contract; it is Ⓤ0 on the lower (inside-material) arc.
ARC_PROFILE_ZONE_MM = f"{TOP_EDGE_BAND[0]:g}"
ARC_PROFILE_OUTSIDE_MM = {
    "TopRadius": ARC_PROFILE_ZONE_MM,
    "BottomRadius": f"{TOP_EDGE_BAND[1]:g}",
}

# The two frames control one nominal concentric arc system. Their material
# sides differ: top outside is +Y, bottom inside is +Y. A single shared frame
# would put one of the zones on the wrong side of its basic arc.
ARC_PROFILE_FRAME_XY = {
    "TopRadius": (0.114, 0.228),
    "BottomRadius": (0.112, 0.122),
}
ARC_PROFILE_PICK_X_MM = {"TopRadius": -110.0, "BottomRadius": -100.0}

# General notes. The linked block renders ~4.1 mm a line, so its 18 lines run
# ~75 mm. Anchored by its top at y 0.082, the last two ran past the bottom
# border into the zone band (r743-p1s-B2 render). The block is now seated from
# its MEASURED extent: rendered bottom NOTES_BORDER_CLEARANCE above the
# sheet's drawable region, left edge on NOTES_LEFT. A block that then reaches
# NOTES_CEILING, under the front view's O6.50 text (y ~0.117), fails the build.
NOTES_LEFT = 0.020
NOTES_BORDER_CLEARANCE = 0.003
NOTES_CEILING = 0.110
NOTES_SEAT_PASSES = 3
NOTES_SEAT_SETTLE = 0.00005
# Below any note text height this sheet prints (the linked block pitches ~4.1).
NOTES_MIN_LINE_PITCH = 0.0025

# Tip-face midpoint (model mm): the top-arc endpoint pushed half the tip face
# outward along the end radius -- where datum C (clocking) attaches.
_TIP_FACE_MID_X = TOP_END_X + (TIP_FACE / 2.0) * (TOP_END_X / R_TOP)
_TIP_FACE_MID_Y = TOP_END_Y - (TIP_FACE / 2.0) * math.cos(TOP_ARC_LEN / 2.0 / R_TOP)
_ROD_TIP_Y = TOP_END_Y - TIP_FACE * math.cos(_ALPHA_TOP)
_BOT_END_Y = CENTER_Y - math.sqrt(R_BOTTOM**2 - BOT_END_X**2)

# Keep the overall witnesses short and above the callouts: full-height tip
# witnesses would cut datum C's outward-normal leader and the local land angle.
OVERALL_WIDTH_TEXT_XY = (FRONT_CENTER[0], 0.250)
OVERALL_WITNESS_LENGTH = 0.012
TAPER_INTERSECTION_TEXT_XY = (0.219, 0.124)
LAND_ANGLE_TEXT_REACH = 0.032
LAND_ANGLE_WITNESS_LENGTH = 0.008
LAND_DATUM_STANDOFF = 0.014
STRAP_OFFSET_TEXT_XY = (RIGHT_CENTER[0] - 0.018, RIGHT_CENTER[1] + 0.030)
STRAP_OFFSET_WITNESS_LENGTH = 0.010


def _plane_between(
    start: tuple[float, float], end: tuple[float, float],
) -> PlanarFace:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    normal = (-dy / length, dx / length, 0.0)
    return PlanarFace(normal, normal[0] * start[0] + normal[1] * start[1])


def _rocker_points() -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    top = (rocker.TOP_END_X, rocker.TOP_END_Y)
    bottom = (rocker.BOT_END_X, rocker.CENTER_Y - math.sqrt(rocker.R_BOTTOM**2 - rocker.BOT_END_X**2))
    tip = (rocker.ROD_TIP_X, rocker.TOP_END_Y + rocker.TIP_FACE * (rocker.TOP_END_Y - rocker.CENTER_Y) / rocker.R_TOP)
    return top, tip, bottom


_TOP, _TIP, _BOTTOM = _rocker_points()
_RIGHT = (_plane_between(_TOP, _TIP), _plane_between(_TIP, _BOTTOM))
_TIPS = tuple(PlanarFace((-face.normal[0], face.normal[1], 0.0), face.offset_mm) for face in _RIGHT)
_LAND_ANGLE = math.degrees(math.acos(
    sum((_TIP[i] - _TOP[i]) * _RIGHT[0].normal[i] for i in (0, 1)) / rocker.TIP_FACE
))
_ANGULAR = float(_config.title_block("angular")["value_deg"])

for _name, _sign, _face in (("tip_land_pos_x", 1, _RIGHT[0]), ("tip_land_neg_x", -1, _TIPS[0])):
    requirement(
        _name, kind="face", faces=(_face,), requirements=("tip_land", "land_angle_deg"), fields={
            "tip_land": (_band(rocker.TIP_FACE, _P), ("TIP_FACE", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
            "land_angle_deg": ([round(_LAND_ANGLE, 0) - _ANGULAR, round(_LAND_ANGLE, 0) + _ANGULAR], ("TIP_FACE", "TOP_END_X", "TOP_END_Y", "ROD_TIP_X", "R_TOP", "CENTER_Y", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
            "land_angle_nominal_deg": (_LAND_ANGLE, ("TOP_END_X", "TOP_END_Y", "ROD_TIP_X", "TIP_FACE", "R_TOP", "CENTER_Y", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
            "radial_tip_end": ([_sign * _TIP[0], _TIP[1]], ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", "R_TOP", "CENTER_Y")),
            "top_edge_feature": ("top_edge", (("ch_rocker_arm_notes", "DRAWING_NOTES"),)),
            **({"datum": ("C", (("draw_ch_rocker_arm", "build"),))} if _sign == 1 else {}),
        }, precision={"tip_land": _P, "land_angle_deg": 0},
    )

part_metadata(datums={
    "C": ({"feature": "tip_land_pos_x", "surface": "rod-side (+X) radial tip land"}, (("draw_ch_rocker_arm", "build"),)),
})


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:2)."""
    return (
        FRONT_CENTER[0] + mx * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


# Datum A on the pivot bore. Three leaders land on that 3.25 mm circle, one
# per quadrant (r743-1RC eye pass: they converged): datum A from the upper
# left, the O6.50 dimension from the lower left (its line runs on through the
# centre to the upper-right rim), the Ra from the lower right.
#
# The tag is COORDINATE-picked, because only a coordinate-picked tag puts its
# frame box where it is asked: r743-4D printed it up-left of the pivot, clear
# above the strap, and channel_lever's datum B reads 0.002 mm off its request.
# An entity-attached tag drops its box at SolidWorks' default instead: r743-1RC
# printed it on the strap beside the bore, and the vm2 datum probe measured
# the same behaviour 34.7 mm off its request.
#
# A coordinate pick hit-tests with a PIXEL aperture mapped through the current
# zoom (see new_project_drawing), and at fit-to-sheet that aperture spans the
# 0.875 mm (sheet) between the O6.5 bore and the concentric O10 hub rims:
# r743-4D's pick, exactly on the bore rim, put the triangle on the hub. Its
# render has the pivot centre within 0.05 mm of _sheet_xy, so the mapping is
# not the cause. The pick is therefore made zoomed in on the pivot, checked
# against the diameter-picked bore edge before the tag goes in, and the tag's
# attachment is checked again after it does. The triangle then re-attaches at
# the bore point nearest the box, on the 135-degree ray (see
# draw_platen_guide's datum C note).
PIVOT_DATUM_STANDOFF = 0.020
PIVOT_DATUM_ANGLE = math.radians(135.0)
PIVOT_BORE_SHEET_R = PIVOT_HOLE_DIA / 2.0 * _S / 1000.0
PIVOT_HUB_SHEET_R = HUB_DIA / 2.0 * _S / 1000.0
# The zoomed pick window's half-span: the hub and a hub radius of margin. That
# is ~40x the fit-to-sheet scale (432 mm across), so an aperture that reached
# the hub 0.875 mm off now covers about 0.02 mm.
PIVOT_PICK_ZOOM_HALF = 2.0 * PIVOT_HUB_SHEET_R
# Pick candidates on the 135-degree ray as fractions of the bore radius: the
# rim first, then a point further from the hub rim. Each result is recorded,
# and a pick that never resolves to the bore fails the build.
PIVOT_PICK_FRACTIONS = (1.0, 0.6)

PIVOT_BORE = requirement(
    "pivot_bore", kind="hole", faces=(CylinderFace(rocker.PIVOT_HOLE_DIA),),
    requirements=("dia", "thru", "finish_ra", "process"), fields={
        "at": _CENTRE, "axis": _AXIS,
        "dia": (_band(rocker.PIVOT_HOLE_DIA, _P, rocker.PIVOT_HOLE_BAND), ("PIVOT_HOLE_DIA", "PIVOT_HOLE_BAND")),
        "nominal_dia": (rocker.PIVOT_HOLE_DIA, ("PIVOT_HOLE_DIA",)),
        "thru": (True, (("ch_rocker_arm_notes", "DRAWING_NOTES"),)),
        "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        "process": ("ream", (("ch_rocker_arm_notes", "DRAWING_NOTES"),)), "datum": ("A", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"dia": _P, "finish_ra": 1},
)

part_metadata(
    frames={
        name: ({"origin": [0.0, rocker.PIVOT_MID_Y, sign * rocker.HUB_LENGTH / 2], "x": [1.0, 0.0, 0.0], "y": [0.0, float(sign), 0.0], "z": [0.0, 0.0, float(sign)], "binding": "unknown"}, ("PIVOT_MID_Y", "HUB_LENGTH"))
        for name, sign in (("A", 1), ("B", -1))
    },
    datums={"A": ({"feature": "pivot_bore", "surface": "pivot bore cylinder"}, (("draw_ch_rocker_arm", "build"),))},
)


def _assert_pivot_precision(
    adapter: Any, drawing_model: Any, annotations: list[Any]
) -> None:
    """Read PivotDia's effective primary precision without rewriting its import."""
    expected = PIVOT_BORE.precision["dia"]
    for annotation in annotations:
        annotation = adapter._attempt(
            lambda a=annotation: _early_bound(a, "IAnnotation")
        )
        name = adapter._attempt(lambda a=annotation: dimension_name(adapter, a))
        if type(name) is not str or not name:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; unreadable dimension name"
            )
        if name != "PivotDia":
            continue
        display = adapter._attempt(
            lambda a=annotation: _early_bound(
                a.GetSpecificAnnotation(), "IDisplayDimension"
            )
        )
        primary = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if type(primary) is not int:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"unreadable primary precision {primary!r}"
            )
        effective = primary
        # swDimensionPrecisionSettings_e.swPrecisionFollowsDocumentSetting = -2.
        if primary == -2:
            extension = adapter._attempt(
                lambda: _early_bound(
                    _early_bound(drawing_model, "IModelDoc2").Extension,
                    "IModelDocExtension",
                )
            )
            # swconst R2026x: swDetailingLinearDimPrecision = 24;
            # swDetailingDiameterDimension = 204. Units decimals are not this getter.
            effective = adapter._attempt(
                lambda: extension.GetUserPreferenceInteger(24, 204)
            )
        if type(effective) is not int or effective < 0:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"unreadable effective precision {effective!r} (primary {primary})"
            )
        if effective != expected:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"effective {effective} decimal places (primary {primary})"
            )
        return
    raise RuntimeError(
        f"PivotDia precision: expected {expected}; missing dimension, "
        "effective precision unreadable"
    )


def _pivot_datum_request(centre: tuple[float, float]) -> tuple[float, float]:
    """The sheet point datum A's leader meets its frame, on the 135-degree ray."""
    reach = PIVOT_BORE_SHEET_R + PIVOT_DATUM_STANDOFF
    return (
        centre[0] + reach * math.cos(PIVOT_DATUM_ANGLE),
        centre[1] + reach * math.sin(PIVOT_DATUM_ANGLE),
    )


def _pick_pivot_bore(
    adapter: Any, view: Any, bore_edge: Any, centre: tuple[float, float]
) -> tuple[float, float]:
    """Return a sheet point whose EDGE pick resolves to the pivot bore."""
    results = []
    for fraction in PIVOT_PICK_FRACTIONS:
        radius = PIVOT_BORE_SHEET_R * fraction
        xy = (
            centre[0] + radius * math.cos(PIVOT_DATUM_ANGLE),
            centre[1] + radius * math.sin(PIVOT_DATUM_ANGLE),
        )
        try:
            picked = _select_view_entity(
                adapter, view, "EDGE", xy, label="pivot bore datum pick"
            )
        except RuntimeError as error:
            results.append((fraction, str(error)))
            _telemetry.event("datum.bore_pick", fraction=fraction, same=-2)
            continue
        same = int(adapter.swApp.IsSame(picked, bore_edge))
        results.append((fraction, same))
        _telemetry.event("datum.bore_pick", fraction=fraction, same=same)
        adapter.currentModel.ClearSelection2(True)
        if same == 1:
            return xy
    raise RuntimeError(
        "no pick on datum A's ray resolves to the O6.5 pivot bore "
        f"(fraction of bore radius, IsSame or error): {results!r}"
    )


def _require_datum_on_bore(app: Any, tag: Any, bore_edge: Any) -> None:
    """Raise unless datum A is attached to the pivot bore edge alone."""
    annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 1 or attached[0] is None:
        raise RuntimeError(
            f"datum A needs one attached edge, has {len(attached)}: {attached!r}"
        )
    # swObjectSame = 1; different (0) and unknown (-1) both fail.
    if int(app.IsSame(attached[0], bore_edge)) != 1:
        raise RuntimeError(
            "datum A is attached to an edge other than the O6.5 pivot bore "
            "(r743-4D: the concentric O10 hub)"
        )
    if annotation.IsDangling():
        raise RuntimeError("datum A is dangling")


# Pivot-bore Ra. The symbol's body always draws up-right of its leader end
# (r743-p1s-B2: from the 7:30 rim the leader ran up through the body). It
# lands on the rim at 4:30 -- oblique to both centre-mark axes, in the one
# quadrant no other pivot leader uses -- from a symbol down-right of it, below
# the strap. At 1:30 it met the O6.50 dimension line where that runs on past
# the centre (r743-1RC). Note text height, as on the other part sheets.
PIVOT_FINISH_ANGLE = math.radians(-45.0)
PIVOT_FINISH_OFFSET = (0.012, -0.013)
PIVOT_FINISH_CHAR_HEIGHT = 0.0025


def _pivot_finish_placement() -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet (rim, symbol) points of the pivot-bore finish leader."""
    radius = PIVOT_HOLE_DIA / 2.0
    rim = _sheet_xy(
        radius * math.cos(PIVOT_FINISH_ANGLE),
        _PIVOT_MID_Y + radius * math.sin(PIVOT_FINISH_ANGLE),
    )
    return rim, (rim[0] + PIVOT_FINISH_OFFSET[0], rim[1] + PIVOT_FINISH_OFFSET[1])


# The native BASIC radii feed the arc-system profile frames. Suppress their
# off-sheet centre witnesses and dimension-line tails, retaining the radial
# arrow/leader (drawing-layout-tuning refusal a), rather than typing values in
# the manufacturing notes.
# The O6.50 text sits down-left of the pivot, left of the rod-pin X location
# dimension (pivot to rod-pin hole, its line at y 0.138): from (0.180, 0.120),
# straight below the bore, its leader crossed that dimension's line and ran up
# its extension line (r743-4D render).
# The top edge's BASIC height over the pivot axis runs up the mirror axis from
# the pivot centre, feeding the profile zone that preserves the former +0.50/0;
# text straight above the strap, left of the rod-pin frame and datum C. It
# prints LEFT of the axis, so it rides above datum A's box (top y ~0.1905):
# at a 10 mm rise its rows sat on datum A's 135-degree leader
# (leader-through-text, 5.12 mm); at 22 mm its underline clears the box by
# ~2.7 mm.
TOP_ABOVE_PIVOT_TEXT_RISE = 0.022
FRONT_KEEP = {
    "PivotDia": (0.130, 0.148),
    "HubDia": (0.157, 0.139),
    "RodTipLen": (0.280, 0.188),
    # A radius text box inside this large parent circle still printed a
    # centre-directed line off-sheet, even with the outside-arrow flags.
    # Keep its exterior leader to the right of the pivot-bore finish callout.
    "TopRadius": (0.235, 0.157),
    "BottomRadius": (0.090, 0.154),
    "TopAbovePivot": (
        _sheet_xy(0.0, _PIVOT_MID_Y + TOP_EDGE_ABOVE_PIVOT)[0],
        _sheet_xy(0.0, _PIVOT_MID_Y + TOP_EDGE_ABOVE_PIVOT)[1]
        + TOP_ABOVE_PIVOT_TEXT_RISE,
    ),
}

_TOP_P = rocker_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"]
TOP_EDGE = requirement(
    "top_edge", kind="profile", faces=(CylinderFace(2 * rocker.R_TOP),),
    requirements=("height_above_pivot", "radius", "profile_zone", "arc_len"), fields={
        "height_above_pivot": (rocker.TOP_EDGE_ABOVE_PIVOT, ("TOP_EDGE_ABOVE_PIVOT", ("draw_ch_rocker_arm", "_basic_profile_dimensions"))),
        "height_from": ("pivot_bore", (("draw_ch_rocker_arm", "build"),)),
        "radius": (rocker.R_TOP, ("R_TOP", ("draw_ch_rocker_arm", "_basic_profile_dimensions"))), "radius_nominal": (rocker.R_TOP, ("R_TOP",)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "_basic_profile_dimensions"),)),
        "profile_zone": (float(ARC_PROFILE_ZONE_MM), (("ch_rocker_arm_notes", "ARC_PROFILE_ZONE_MM"),)),
        "outside_disposition": (float(ARC_PROFILE_OUTSIDE_MM["TopRadius"]), (("ch_rocker_arm_notes", "ARC_PROFILE_OUTSIDE_MM"),)),
        "profile_datums": (["A", "B", "C"], (("draw_ch_rocker_arm", "_add_arc_profiles"),)),
        "arc_len": (_band(rocker.TOP_ARC_LEN, _P), ("TOP_ARC_LEN", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "arc_centre": ([0.0, rocker.CENTER_Y, 0.0], ("CENTER_Y",)),
        "centre_from_pivot_ref": (rocker.CENTER_Y - rocker.PIVOT_MID_Y, ("CENTER_Y", "PIVOT_MID_Y", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "end": (list(_TOP), ("TOP_END_X", "TOP_END_Y")),
    }, precision={"height_above_pivot": _TOP_P, "radius": _P, "arc_len": _P},
)
PROFILE_OUTER = requirement(
    "profile_outer", kind="profile", faces=(CylinderFace(2 * rocker.R_BOTTOM), _RIGHT[1], _TIPS[1]),
    requirements=("bottom_radius", "profile_zone", "bottom_arc_len", "mirror_symmetric"), fields={
        "bottom_radius": (rocker.R_BOTTOM, ("R_BOTTOM", ("draw_ch_rocker_arm", "_basic_profile_dimensions"))),
        "bottom_radius_nominal": (rocker.R_BOTTOM, ("R_BOTTOM",)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "_basic_profile_dimensions"),)),
        "profile_zone": (float(ARC_PROFILE_ZONE_MM), (("ch_rocker_arm_notes", "ARC_PROFILE_ZONE_MM"),)),
        "outside_disposition": (float(ARC_PROFILE_OUTSIDE_MM["BottomRadius"]), (("ch_rocker_arm_notes", "ARC_PROFILE_OUTSIDE_MM"),)),
        "profile_datums": (["A", "B", "C"], (("draw_ch_rocker_arm", "_add_arc_profiles"),)),
        "arc_centre": ([0.0, rocker.CENTER_Y, 0.0], ("CENTER_Y",)), "top_edge_feature": ("top_edge", (("ch_rocker_arm_notes", "DRAWING_NOTES"),)),
        "bottom_arc_len": (_band(rocker.BOT_ARC_LEN, _P), ("BOT_ARC_LEN", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "mirror_symmetric": (True, (("ch_rocker_arm_notes", "DRAWING_NOTES"),)), "depth_ref": (rocker.ARM_DEPTH, ("ARM_DEPTH", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "bottom_end": (list(_BOTTOM), ("BOT_END_X", "R_BOTTOM", "CENTER_Y")),
        "radial_tip_end": (list(_TIP), ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", "R_TOP", "CENTER_Y")),
    }, precision={"bottom_radius": _P, "bottom_arc_len": _P},
)
HUB_OD = requirement(
    "hub_od", kind="boss", faces=(CylinderFace(rocker.HUB_DIA),),
    requirements=("dia", "coaxiality_dia"), fields={
        "at": _CENTRE, "axis": _AXIS,
        "dia": (_band(rocker.HUB_DIA, _P), ("HUB_DIA",)),
        "dia_nominal": (rocker.HUB_DIA, ("HUB_DIA",)),
        "coaxiality_dia": (rocker_notes.HUB_COAXIALITY_DIA, (("ch_rocker_arm_notes", "HUB_COAXIALITY_DIA"),)),
        "coaxial_to": ("pivot_bore", (("ch_rocker_arm_notes", "DRAWING_NOTES"),)),
    }, precision={"dia": _P, "coaxiality_dia": _P},
)
# The hub length (+0.05/0, #743 PR2) under the end view, where the hub shows
# its full length (the end view is 1:1, centred on the pivot mid-depth).
# The strap thickness (+/-0.025, ARM_THICKNESS_BAND, Main ruling 2026-10
# option b) right of the end view, its line across the strap ABOVE the hub
# and 3 mm above datum B's attachment (broad_face, RIGHT_CENTER y + 0.007),
# so its outside arrows clear datum B's down-left leader; the text sits under
# the iso caption (top y 0.183) and right of the end view.
STRAP_THICKNESS_TEXT_XY = (RIGHT_CENTER[0] + 0.017, RIGHT_CENTER[1] + 0.010)
RIGHT_KEEP: dict[str, tuple[float, float]] = {
    "HubLength": (RIGHT_CENTER[0], RIGHT_CENTER[1] - (_PIVOT_MID_Y + 12.0) / 1000.0),
    "StrapThickness": STRAP_THICKNESS_TEXT_XY,
}

_HUB_P = rocker_notes.DRAWING_PRECISION["Hub"]["HubLength"]
_STRAP_P = rocker_notes.DRAWING_PRECISION["Strap"]["StrapThickness"]
_STRAP_BAND = (_band(rocker.ARM_THICKNESS, _STRAP_P, rocker.ARM_THICKNESS_BAND), ("ARM_THICKNESS", "ARM_THICKNESS_BAND"))
HUB_FACES = requirement(
    "hub_faces", kind="face",
    faces=tuple(PlanarFace((0, 0, sign), rocker.HUB_LENGTH / 2) for sign in (-1, 1)),
    requirements=("length",), fields={
        "length": (_band(rocker.HUB_LENGTH, _HUB_P, rocker.HUB_LENGTH_BAND), ("HUB_LENGTH", "HUB_LENGTH_BAND")),
        "length_nominal": (rocker.HUB_LENGTH, ("HUB_LENGTH",)),
        "upper_z": (rocker.HUB_LENGTH / 2, ("HUB_LENGTH",)),
        "lower_z": (-rocker.HUB_LENGTH / 2, ("HUB_LENGTH",)),
    }, precision={"length": _HUB_P},
)
STRAP_FACES = requirement(
    "strap_faces", kind="face", faces=(PlanarFace((0, 0, -1), rocker.ARM_THICKNESS / 2),),
    requirements=("thickness",), fields={
        "thickness": _STRAP_BAND,
        "thickness_nominal": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
        "upper_z": (rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)),
        "lower_z": (-rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)),
    }, precision={"thickness": _STRAP_P},
)
STRAP_DATUM_B = requirement(
    "strap_datum_b", kind="face", faces=(PlanarFace((0, 0, 1), rocker.ARM_THICKNESS / 2),),
    requirements=("thickness",), fields={
        "thickness": _STRAP_BAND,
        "thickness_nominal": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
        "plane": ({"frame": "model", "axis": "z", "value": rocker.ARM_THICKNESS / 2}, ("ARM_THICKNESS",)),
        "datum": ("B", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"thickness": _STRAP_P},
)
part_metadata(datums={
    "B": ({"feature": "strap_datum_b", "surface": "+Z broad strap face"}, (("draw_ch_rocker_arm", "build"),)),
})
TOP_KEEP: dict[str, tuple[float, float]] = {}
BASIC_PROFILE_DIMENSIONS = {"TopRadius", "BottomRadius", "TopAbovePivot"}


def _basic_profile_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Make the imported profile nominals BASIC without saving the source part."""
    remaining = set(BASIC_PROFILE_DIMENSIONS)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        set_basic_dimension(adapter, display, label=f"arc-system {name}")
        if name in ARC_PROFILE_OUTSIDE_MM:
            # Dress exterior radius callouts with the pinion-arbor and
            # arbor-pedestal leader pattern. The text must also be outside
            # its parent circle: these flags alone did not remove the centre
            # line when the R800 text was inside that circle.
            display.ShortenedRadius = False
            display.ArcExtensionLineOrOppositeSide = False
            display.ArrowSide = 1  # swDimArrowsOutside
            display.SolidLeader = False
            if (
                bool(display.ShortenedRadius)
                or bool(display.ArcExtensionLineOrOppositeSide)
                or int(display.ArrowSide) != 1
                or bool(display.SolidLeader)
            ):
                raise RuntimeError(f"{name} retained its centre-directed radius leader")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"arc-system BASIC dimensions missing: {sorted(remaining)}")


def _dress_front_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Read imported land/OD sizes and add process without replacing any nominal."""
    remaining = {"RodTipLen": TIP_FACE, "HubDia": HUB_DIA, "PivotDia": PIVOT_HOLE_DIA}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        assert_dimension_measures(
            adapter, display, expected_mm=remaining.pop(name), label=f"imported {name}"
        )
        if name == "RodTipLen":
            continue
        # Single exterior arrows, not diametral lines through both concentric
        # circles: otherwise the new hub OD and pivot bore leaders intersect.
        display.ArrowSide = 1  # swDimArrowsOutside
        display.SetSecondArrow(False, False)
        display.SolidLeader = False
        if (
            int(display.ArrowSide) != 1
            or display.GetUseDocSecondArrow()
            or display.GetSecondArrow()
            or display.SolidLeader
        ):
            raise RuntimeError(f"{name} retained a centre-crossing diameter leader")
        if name != "PivotDia":
            continue
        model_dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(model_dimension.Tolerance, "IDimensionTolerance")
        band = (float(tolerance.GetMaxValue()), float(tolerance.GetMinValue()))
        if not all(math.isfinite(value) for value in band) or any(
            abs(actual - expected / 1000.0) > 1e-9
            for actual, expected in zip(band, PIVOT_HOLE_BAND)
        ):
            raise RuntimeError(f"pivot bore lost its part-owned ream tolerance: {band}")
        tolerance_type = int(model_dimension.GetToleranceType())
        prefix = str(display.GetText(5) or "")  # native prefix definition
        suffix = str(display.GetText(6) or "")  # native suffix definition
        callouts = (str(display.GetText(7) or ""), str(display.GetText(8) or ""))
        # A custom prefix replaces the automatic diameter glyph, so retain its
        # native symbol token when the original prefix compartment is empty.
        ream_prefix = "REAM " + (prefix if prefix else "<MOD-DIAM>")
        through_suffix = suffix + (" " if suffix else "") + "THRU"
        display.SetText(1, ream_prefix)
        display.SetText(2, through_suffix)
        if (
            str(display.GetText(5) or "") != ream_prefix
            or str(display.GetText(6) or "") != through_suffix
            or (str(display.GetText(7) or ""), str(display.GetText(8) or "")) != callouts
            or not display.ShowDimensionValue
            or int(model_dimension.GetToleranceType()) != tolerance_type
            or (float(tolerance.GetMaxValue()), float(tolerance.GetMinValue())) != band
        ):
            raise RuntimeError("pivot ream/through text did not preserve its native dimension")
    if remaining:
        raise RuntimeError(f"front source dimensions missing: {sorted(remaining)}")
    assert_imported_precision(
        adapter, annotations, {"HubDia": DEFAULT_DRAWING_PRECISION}
    )


def _require_native_angle(
    display: Any, *, expected_degrees: float, label: str
) -> float:
    """Read native radians, never a formatted text value or a supplementary guess."""
    if display is None:
        raise RuntimeError(f"{label} has no native angular display dimension")
    display = _early_bound(display, "IDisplayDimension")
    if display.Type2 != 3:  # swAngularDimension
        raise RuntimeError(f"{label} is not a native angular dimension")
    native_dimension = display.GetDimension2(0)
    if native_dimension is None:
        raise RuntimeError(f"{label} has no native model dimension")
    dimension = _early_bound(native_dimension, "IDimension")
    value = dimension.SystemValue
    if value is None:
        raise RuntimeError(f"{label} has no measured native angle")
    radians = abs(float(value))
    expected = math.radians(expected_degrees)
    if not math.isfinite(radians) or abs(radians - expected) > 1e-8:
        raise RuntimeError(
            f"{label} measures {math.degrees(radians):g} degrees, "
            f"expected {expected_degrees:g} degrees"
        )
    return math.degrees(radians)


def _land_vertical(adapter: Any, front: Any, points: list[tuple[float, float]]) -> Any:
    """A short view-owned vertical ray through F, parallel to the mirror axis.

    The upper endpoint has the CAD land's top height; no model dimension or
    nominal is introduced. Map sheet points into the active view sketch as in
    draw_dt_cone_tip_block._add_adjuster_axis, never feed raw sheet coordinates
    to a view-owned CreateCenterLine.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate front view for the land angle")
    draw.ClearSelection2(True)
    sketch = _early_bound(front.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    mapped = []
    for x, y in points:
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        mapped.append(
            tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData)
        )
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    old_add_to_db = bool(manager.AddToDB)
    old_display = bool(manager.DisplayWhenAdded)
    manager.AddToDB = True
    manager.DisplayWhenAdded = True
    try:
        centerline = manager.CreateCenterLine(*mapped[0], *mapped[1])
    finally:
        manager.AddToDB = old_add_to_db
        manager.DisplayWhenAdded = old_display
    if centerline is None:
        raise RuntimeError("failed to create the front-view land angle ray")
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0
    if int(segment.Color) != 0:
        raise RuntimeError("land angle centreline colour did not persist")
    draw.ClearSelection2(True)
    return segment


def _add_land_angle(adapter: Any, front: Any, land: ViewEdge) -> Any:
    """Measure the CAD radial land against a local parallel to the mirror axis.

    Use the outer endpoint F, not the top-arc endpoint T: the upward acute
    sector at F is outside the material. The actual mirror-axis line intersects
    this land at the off-sheet R800 parent centre, so it is not a usable witness.
    """
    outer, upper = sorted(land.line, key=lambda point: point[0], reverse=True)
    outer_xy, upper_xy = model_points_in_view(
        adapter, front, [tuple(v / 1000.0 for v in point) for point in (outer, upper)],
        label="rod land angular endpoints",
    )
    vertical_end = (outer_xy[0], upper_xy[1])
    vertical = _land_vertical(adapter, front, [outer_xy, vertical_end])
    dx, dy = upper_xy[0] - outer_xy[0], upper_xy[1] - outer_xy[1]
    length = math.hypot(dx, dy)
    bisector = (dx / length, dy / length + 1.0)
    reach = LAND_ANGLE_TEXT_REACH / math.hypot(*bisector)
    text_xy = (
        outer_xy[0] + bisector[0] * reach,
        outer_xy[1] + bisector[1] * reach,
    )
    display = add_edge_dimension(
        adapter, front,
        p0=((outer_xy[0] + upper_xy[0]) / 2.0, (outer_xy[1] + upper_xy[1]) / 2.0),
        p1=((outer_xy[0] + vertical_end[0]) / 2.0, (outer_xy[1] + vertical_end[1]) / 2.0),
        text_xy=text_xy, label="radial land angle to mirror axis",
        orientation="angular", entities=(land.edge, vertical),
        entity_types=("EDGE", "SKETCHSEGMENT"),
    )
    display = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = list(annotation.GetAttachedEntities3() or ())
    if (
        len(attached) != 2
        or annotation.IsDangling()
        or not all(
            any(int(adapter.swApp.IsSame(actual, entity)) == 1 for actual in attached)
            for entity in (land.edge, vertical)
        )
    ):
        raise RuntimeError("land angle is not attached to its exact land and local vertical")
    _require_native_angle(
        display, expected_degrees=math.degrees(_ALPHA_TOP), label="radial land angle"
    )
    display.MaxWitnessLineLength = LAND_ANGLE_WITNESS_LENGTH
    if abs(float(display.MaxWitnessLineLength) - LAND_ANGLE_WITNESS_LENGTH) > 1e-9:
        raise RuntimeError("land angle retained crossing full-height witnesses")
    display.SetText(4, "TO MIRROR AXIS")
    if str(display.GetText(4) or "") != "TO MIRROR AXIS":
        raise RuntimeError("land angle direction callout did not persist")
    return display


def _add_rocker_outline_dimensions(adapter: Any, front: Any) -> ViewEdge:
    """Import the part-owned sizes and measure the remaining actual CAD outline."""
    annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _basic_profile_dimensions(adapter, annotations)
    _dress_front_dimensions(adapter, annotations)
    edges = scan_view_edges(front, label="rocker front outline")
    land = edges.exact_line_through(
        (_TIP_FACE_MID_X, _TIP_FACE_MID_Y, ARM_THICKNESS / 2.0),
        label="+Z rod-side radial land",
    )
    width_points = (
        (-ROD_TIP_X, _ROD_TIP_Y, ARM_THICKNESS / 2.0),
        (ROD_TIP_X, _ROD_TIP_Y, ARM_THICKNESS / 2.0),
    )
    vertices = tuple(
        edges.exact_vertex_at(point, label=f"overall width tip {index}")
        for index, point in enumerate(width_points)
    )
    width_xy = model_points_in_view(
        adapter, front, [tuple(v / 1000.0 for v in point) for point in width_points],
        label="overall width vertices",
    )
    width = add_edge_dimension(
        adapter, front, p0=width_xy[0], p1=width_xy[1],
        text_xy=OVERALL_WIDTH_TEXT_XY, label="rocker overall width",
        orientation="horizontal", entities=vertices, entity_type="VERTEX",
    )
    assert_dimension_measures(
        adapter, width, expected_mm=2.0 * ROD_TIP_X, label="rocker overall width",
        entities=vertices, entity_types=("VERTEX", "VERTEX"),
    )
    width = _early_bound(width, "IDisplayDimension")
    width.MaxWitnessLineLength = OVERALL_WITNESS_LENGTH
    if abs(float(width.MaxWitnessLineLength) - OVERALL_WITNESS_LENGTH) > 1e-9:
        raise RuntimeError("overall width retained crossing full-height witnesses")
    _add_land_angle(adapter, front, land)
    pivot = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    taper_point = (BOT_END_X, _BOT_END_Y, ARM_THICKNESS / 2.0)
    taper = edges.exact_vertex_at(taper_point, label="+Z taper/lower-arc intersection")
    taper_xy, pivot_xy = model_points_in_view(
        adapter, front,
        [tuple(v / 1000.0 for v in taper_point), (0.0, PIVOT_MID_Y / 1000.0, 0.0)],
        label="taper intersection and pivot mirror axis",
    )
    taper_dimension = add_edge_dimension(
        adapter, front, p0=pivot_xy, p1=taper_xy,
        text_xy=TAPER_INTERSECTION_TEXT_XY, label="taper intersection X",
        orientation="horizontal", entities=(pivot, taper),
        entity_types=("EDGE", "VERTEX"),
    )
    set_arc_endpoints_to_center(adapter, taper_dimension, label="taper mirror-axis origin")
    assert_dimension_measures(
        adapter, taper_dimension, expected_mm=BOT_END_X, label="taper intersection X",
        entities=(pivot, taper), entity_types=("EDGE", "VERTEX"),
    )
    return land


def _add_strap_offset_dimension(adapter: Any, right: Any) -> Any:
    """Measure hub +Z end to strap +Z face, as a band-free parenthesized reference."""
    edges = scan_view_edges(right, label="rocker right offset")
    strap = edges.exact_line_through(
        (_TIP_FACE_MID_X, _TIP_FACE_MID_Y, ARM_THICKNESS / 2.0),
        label="+Z strap face at radial land",
    )
    hub = edges.circle_at(
        (0.0, PIVOT_MID_Y, HUB_LENGTH / 2.0), HUB_DIA / 2.0,
        axis=(0.0, 0.0, 1.0), label="+Z hub end rim",
    )
    points = model_points_in_view(
        adapter, right,
        [
            (0.0, (PIVOT_MID_Y + HUB_DIA / 2.0) / 1000.0, HUB_LENGTH / 2000.0),
            tuple(v / 1000.0 for v in strap.midpoint_mm),
        ],
        label="hub end and strap face offset",
    )
    dimension = add_edge_dimension(
        adapter, right, p0=points[0], p1=points[1],
        text_xy=STRAP_OFFSET_TEXT_XY, label="strap offset from hub end",
        orientation="horizontal", entities=(hub.edge, strap.edge),
    )
    set_arc_endpoints_to_center(adapter, dimension, label="hub end-plane offset origin")
    assert_dimension_measures(
        adapter, dimension, expected_mm=(HUB_LENGTH - ARM_THICKNESS) / 2.0,
        label="strap offset from hub end", entities=(hub.edge, strap.edge),
    )
    display = _early_bound(dimension, "IDisplayDimension")
    model_dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if int(model_dimension.GetToleranceType()) != 0:  # swTolNONE
        raise RuntimeError("strap offset reference acquired an acceptance band")
    display.SetPrecision3(DEFAULT_DRAWING_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DEFAULT_DRAWING_PRECISION:
        raise RuntimeError("strap offset reference lost normal drawing precision")
    display.MaxWitnessLineLength = STRAP_OFFSET_WITNESS_LENGTH
    if abs(float(display.MaxWitnessLineLength) - STRAP_OFFSET_WITNESS_LENGTH) > 1e-9:
        raise RuntimeError("strap offset retained crossing full-height witnesses")
    set_reference_dimension(
        adapter, display.GetAnnotation(), label="strap offset from hub end"
    )
    return display


def _add_land_datum(adapter: Any, front: Any, land: ViewEdge) -> Any:
    """Attach C to the exact +Z radial land, with its triangle on the midpoint."""
    if (
        land.line is None
        or any(abs(point[2] - ARM_THICKNESS / 2.0) > 1e-5 for point in land.line)
        or abs(land.length_mm - TIP_FACE) > 1e-5
    ):
        raise RuntimeError("datum C needs the exact +Z radial land edge")
    start, end = model_points_in_view(
        adapter, front, [tuple(v / 1000.0 for v in point) for point in land.line],
        label="datum C exact land endpoints",
    )
    midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    dx, dy = end[0] - start[0], end[1] - start[1]
    nx, ny = -dy, dx
    if nx < 0.0:
        nx, ny = -nx, -ny
    reach = LAND_DATUM_STANDOFF / math.hypot(nx, ny)
    return add_datum_feature(
        adapter, front, edge_entity=land.edge, leader_attach_xy=midpoint,
        symbol_xy=(midpoint[0] + nx * reach, midpoint[1] + ny * reach),
        datum="C", label="+Z rod-side radial land",
    )


def _arc_profile_point(name: str) -> tuple[float, float]:
    """A point on each nominal arc, away from bores, datums and radius leaders."""
    radius = {"TopRadius": R_TOP, "BottomRadius": R_BOTTOM}[name]
    x = ARC_PROFILE_PICK_X_MM[name]
    centre_y = _PIVOT_MID_Y + TOP_EDGE_ABOVE_PIVOT + R_TOP
    return _sheet_xy(x, centre_y - math.sqrt(radius**2 - x**2))


def _add_arc_profiles(adapter: Any, front: Any) -> None:
    """Attach separate native frames: Ⓤ0.5 top, Ⓤ0 bottom, total zone 0.5."""
    for name, radius in (("TopRadius", R_TOP), ("BottomRadius", R_BOTTOM)):
        edge = visible_circle_edge(adapter, front, 2.0 * radius)
        add_feature_control_frame(
            adapter,
            front,
            edge_entity=edge,
            leader_attach_xy=_arc_profile_point(name),
            frame_xy=ARC_PROFILE_FRAME_XY[name],
            characteristic="profile_surface",
            tolerance=ARC_PROFILE_ZONE_MM,
            outside_disposition=ARC_PROFILE_OUTSIDE_MM[name],
            datums=("A", "B", "C"),
            label=f"arc-system {name} profile",
        )



def _note_extent(adapter: Any, note: Any) -> tuple[float, float, float, float]:
    """The rendered sheet-space box (x0, y0, x1, y1) of a free note."""
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(
        float(value) for value in (_early_bound(note, "INote").GetExtent() or ())
    )
    if len(extent) != 6 or extent[3] <= extent[0] or extent[4] <= extent[1]:
        raise RuntimeError(f"manufacturing notes have no rendered extent: {extent!r}")
    return (extent[0], extent[1], extent[3], extent[4])


def _seat_notes_on_border(
    adapter: Any, note: Any, sheet: Any
) -> tuple[float, float, float, float]:
    """Steer the notes' RENDERED bottom-left corner onto NOTES_LEFT,
    NOTES_BORDER_CLEARANCE above the sheet's drawable region (the insertion
    point is neither the text box's corner nor tracked by it 1:1)."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    region = sheet_drawable_region(
        adapter, sheet, width=template.width_m, height=template.height_m
    )
    target = (NOTES_LEFT, region.ymin + NOTES_BORDER_CLEARANCE)
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    # A property-linked note shows its resolved text only after a rebuild; an
    # extent read before it would seat the one-line link token, not the block.
    rebuild_drawing(adapter, label="manufacturing notes link resolve")
    extent = _note_extent(adapter, note)
    lines = len(DRAWING_NOTES.splitlines())
    if extent[3] - extent[1] < lines * NOTES_MIN_LINE_PITCH:
        raise RuntimeError(
            f"manufacturing notes render {(extent[3] - extent[1]) * 1000.0:.1f} mm "
            f"tall, under {lines} lines at {NOTES_MIN_LINE_PITCH * 1000.0:.1f} mm: "
            "the property link has not resolved"
        )
    for _pass in range(NOTES_SEAT_PASSES):
        shift = (target[0] - extent[0], target[1] - extent[1])
        if max(abs(shift[0]), abs(shift[1])) <= NOTES_SEAT_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"manufacturing notes position unreadable: {position!r}")
        if not annotation.SetPosition(
            position[0] + shift[0], position[1] + shift[1], position[2]
        ):
            raise RuntimeError("manufacturing notes SetPosition failed")
        extent = _note_extent(adapter, note)
    extent_mm = tuple(round(value * 1000.0, 2) for value in extent)
    _telemetry.info(
        f"manufacturing notes seated: extent_mm={extent_mm!r}, "
        f"drawable bottom {region.ymin * 1000.0:.2f} mm"
    )
    if extent[1] < region.ymin or extent[3] > NOTES_CEILING:
        raise RuntimeError(
            "manufacturing notes do not fit between the border "
            f"({region.ymin * 1000.0:.2f} mm) and the front view's annotations "
            f"({NOTES_CEILING * 1000.0:.1f} mm): rendered extent {extent_mm!r}"
        )
    return extent


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm; tapered strap; seesaw pivot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale (an auto-scaled view shifts every coordinate pick).
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    # 1:1 right end view: the 2.50 x ~29 strap section -- prints the strap
    # thickness and hub length, gives the through direction, and carries datum B
    # (the broad face) so the rod-pin position frame has an orientation datum.
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    # Import the source radii and top height too: these are the BASIC nominal
    # geometry of the profile zone, not independent radius/height bands.
    rod_land = _add_rocker_outline_dimensions(adapter, front)
    # The hub length and the strap thickness only show in the end view; the
    # front looks down their direction. Codex #936 (PRRT_kwDOPHDy386mRk__):
    # RIGHT_KEEP was declared but never curated, so the +0.05/0 band that sets
    # all 20 channel stations never printed. Targeted by feature, so only
    # Hub's and Strap's dimensions arrive, each selected by its feature name.
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported_annotations = [*front_annotations, *right_annotations]
    _assert_pivot_precision(adapter, drawing_model, imported_annotations)
    assert_imported_precision(
        adapter,
        imported_annotations,
        {
            "TopAbovePivot": TOP_EDGE.precision["height_above_pivot"],
            "HubLength": HUB_FACES.precision["length"],
            "StrapThickness": STRAP_DATUM_B.precision["thickness"],
        },
    )
    _add_strap_offset_dimension(adapter, right)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Rod-pin hole native callout (the #47 wizard hole near the +X tip).
    # Both bores are picked by DIAMETER (the visible-entity walk), never by a
    # rim coordinate: r743-p1s-B's coordinate pick on the #47 rim resolved to
    # the strap's tapered end-face line 1.6 mm (sheet) away, so AddHoleCallout2
    # had no hole to call out; the pivot bore's rim pick already had the same
    # fate against the concentric hub (see its finish below).
    rod_rim = _sheet_xy(ROD_HOLE_X, ROD_HOLE_Y - _ROD_HOLE_DIA / 2.0)
    rod_hole_edge = visible_circle_edge(adapter, front, _ROD_HOLE_DIA)
    pivot_bore_edge = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    add_native_hole_callout(
        adapter,
        front,
        edge=rod_hole_edge,
        # Above the strap, up-left of the hole: from (0.300, 0.128) below it
        # the leader crossed the rod-pin Y location's pivot-rim extension
        # line (y 0.1717, leader-crosses-line). The leader now drops ~57 deg
        # onto the rim from above, >= 3.3 mm off every line bar the landing.
        callout_xy=(0.216, 0.194),
        label="rod-pin hole",
        process=drill_process(ROD_HOLE_SPEC) + "\n",
    )

    # Locate the rod-pin hole from the pivot bore with X and Y BASIC coordinate
    # components.  The rod-pin centre is NOT collinear with the pivot (7.30 mm
    # above its mid-height), so a single slant centre distance would leave the
    # angular component uninspectable; two component dimensions fully define
    # the true position the FCF below controls.
    pivot_rim = _sheet_xy(0.0, _PIVOT_MID_Y - PIVOT_HOLE_DIA / 2.0)
    rod_location_x = add_edge_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.180, 0.138),
        label="rod-pin X location",
        orientation="horizontal",
        entities=(pivot_bore_edge, rod_hole_edge),
    )
    set_basic_dimension(adapter, rod_location_x, label="rod-pin X location")
    rod_location_y = add_edge_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.267, 0.162),
        label="rod-pin Y location",
        orientation="vertical",
        entities=(pivot_bore_edge, rod_hole_edge),
    )
    set_basic_dimension(adapter, rod_location_y, label="rod-pin Y location")

    # Datum A identifies the pivot bore's cylindrical surface.  Keep its leader
    # oblique to both centre-mark axes so the triangle unmistakably terminates
    # on the circumference rather than appearing to identify the bore centre.
    # Picked by coordinate under a zoom and proven against the bore edge picked
    # by DIAMETER (see PIVOT_DATUM_STANDOFF's note).
    pivot_centre = _sheet_xy(0.0, _PIVOT_MID_Y)
    with _zoomed_on(adapter, pivot_centre, PIVOT_PICK_ZOOM_HALF):
        pivot_datum_pick = _pick_pivot_bore(
            adapter, front, pivot_bore_edge, pivot_centre
        )
        datum_a = add_datum_feature(
            adapter,
            front,
            edge_xy=pivot_datum_pick,
            symbol_xy=_pivot_datum_request(pivot_centre),
            datum=PIVOT_BORE.fields["datum"][0],
            label="pivot bore cylindrical datum feature",
            shoulder=True,
        )
    _require_datum_on_bore(adapter.swApp, datum_a, pivot_bore_edge)
    # The bore circle picked by DIAMETER above (the visible-entity walk the
    # cone-gear drawing uses): a coordinate pick on the concentric O6.5 / O10
    # rims resolves to the hub's outer circle within SolidWorks' tolerance.
    pivot_finish_rim, pivot_finish_symbol = _pivot_finish_placement()
    add_surface_finish(
        adapter,
        front,
        edge_entity=pivot_bore_edge,
        symbol_xy=pivot_finish_symbol,
        leader_attach_xy=pivot_finish_rim,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
        char_height=PIVOT_FINISH_CHAR_HEIGHT,
    )
    # Then a position FCF tying the rod-pin hole to the complete A-B-C frame.
    # Datum B (broad face, on the end view) orients the hole axes; datum C
    # (the +X tip face) clocks rotation about the pivot axis, so the X/Y BASIC
    # coordinates above have an inspectable direction.
    # Datum B on the strap's broad face in the end view, picked ABOVE the hub
    # band (the O10 hub hides the flank over y 3..13 since 2026-09-02); the
    # end view is centred on the strap's mid-depth (_PIVOT_MID_Y).
    broad_face = (
        RIGHT_CENTER[0] - ARM_THICKNESS / 2000.0,
        RIGHT_CENTER[1]
        + (ARM_DEPTH - 1.0 - _PIVOT_MID_Y) / 1000.0,  # right view is 1:1,
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=broad_face,
        symbol_xy=(broad_face[0] - 0.016, broad_face[1] - 0.014),
        datum=STRAP_DATUM_B.fields["datum"][0],
        label="broad face",
    )
    _add_land_datum(adapter, front, rod_land)
    add_feature_control_frame(
        adapter,
        front,
        edge_entity=rod_hole_edge,
        leader_attach_xy=_sheet_xy(
            ROD_HOLE_X + _ROD_HOLE_DIA / (2.0 * math.sqrt(2.0)),
            ROD_HOLE_Y + _ROD_HOLE_DIA / (2.0 * math.sqrt(2.0)),
        ),
        frame_xy=FCF_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["rod-pin hole position"],
        datums=tuple(ROD_HOLE.fields["position_datums"][0]),
        diameter=True,
        label="rod-pin hole position",
    )
    _add_arc_profiles(adapter, front)

    notes = add_property_linked_note(
        adapter, "Manufacturing Notes", NOTES_LEFT, NOTES_CEILING
    )
    _seat_notes_on_border(adapter, notes, sheet)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_XY)
    # The shared gate: no overlaps, border crossings or leader crossings.
    rebuild_drawing(adapter, label="rocker-arm layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
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
