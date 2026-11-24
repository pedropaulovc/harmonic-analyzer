r"""Create the manufacturing drawing for the transgear pivot spacer (MHA-PD-20).

A turned brass ring: Ø.44 O.D. over a #11 drilled bore (a bonded slip fit,
LOCTITE 638, on the MHA-PD-VN-57 shoulder), .197 long under its explicit
band.  The profile lies as it sits in the lathe (axis horizontal): the
``*Top`` view turned a quarter turn, so model +Z runs LEFT and the bar-side
front face (z 0) is the profile's right end, the rear face (on the arm) its
left end.  The rear face carries its finish (the arm's bearing face); no
frame relates the faces, the length's band bounds their taper (rule 5);
the length sits under the profile and the O.D. moves onto the profile
(drawing-guidelines.md rule 11 (turned parts read like the lathe): diameters on the side view).  The end view to its left (third
angle, looking along -Z from the +Z end) keeps the bore, a solid circle only
end-on, and its axis is datum A (the O.D.'s runout).  The bore names the
bonded seat it makes on the screw's shoulder (rule 23), the length the
disc-to-platen air its band keeps (rule 4).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_transgear_pivot_spacer.py pd-transgear-pivot-spacer
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)
from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, offset_dimension_text
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _gtol_cylinder import CylinderFace
from _gtol_face_resolve import resolve_faces
from _gtol_planar import PlanarFace
from _drawing_layout_audit import annotation_display
from _layout_audit import (
    display_box,
    line_segment,
    polygon_segments,
    polyline_segments,
)
from _layout_geometry import Box, Segment, point_segment_distance
from _machinist_review_mode import MachinistReviewMode
from _native_axis_datum import _readback as read_native_datum
from _native_axis_datum import _validate_source_edge as validate_source_axis_edge
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from _feature_requirements import part_metadata, requirement
from _printed_limits import drilled_limits, limits
from _printed_tolerance import printed_deviations
import pd_transgear_pivot_spacer_callouts as callouts
from pd_transgear_pivot_spacer_spec import (
    BOND_GAP,
    BORE_DATUM,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_TOLERANCES_IN,
    ISOMETRIC_VIEW_SCALE,
    LENGTH,
    LENGTH_TOLERANCE,
    OD,
    OD_RUNOUT,
    SURFACE_FINISHES,
    UNIT,
    WALL_WORST,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_pivot_spacer"]
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

# A Ø11.0 x 5.0 ring: 5:1 keeps the three sizes and both face finishes legible
# on the landscape sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # model mm -> sheet m
# The *Top view turned -90 degrees: model +Z runs to paper-left.
PROFILE_ANGLE = -math.pi / 2.0
PROFILE_CENTER = (0.200, 0.165)
# Third angle: the end view seen from the +Z end sits LEFT of the profile, on
# its axis.
END_CENTER = (0.090, PROFILE_CENTER[1])
ISO_CENTER = (0.340, 0.185)

_PROFILE_FRONT_X = PROFILE_CENTER[0] + LENGTH * _S / 2.0  # z 0, right end
_PROFILE_REAR_X = PROFILE_CENTER[0] - LENGTH * _S / 2.0  # z LENGTH, left end
_PROFILE_TOP = PROFILE_CENTER[1] + OD * _S / 2.0
_PROFILE_BOTTOM = PROFILE_CENTER[1] - OD * _S / 2.0

# The bore stays on the end view, where it is a circle: a drilled through
# hole, fully defined by its callout (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)), it needs no section, and the
# profile is hidden-lines-removed (a dimension never lands on a hidden line).
# The O.D. arrives there too and is moved onto the profile below.
END_KEEP = {
    "BoreDia": (0.050, 0.222),
    "RingOd": (0.045, 0.120),  # donor: moved onto the profile
}
# Rule 23: the bonded seat names its mate
# (pd_transgear_pivot_spacer_callouts).  The part authors the
# below-callout on its source dimension; the sheet imports it and only
# reads it back (#1942).
DIMENSION_CALLOUTS = {
    name: lanes[callouts.CALLOUT_BELOW]
    for name, lanes in callouts.authored_by_name().items()
}
# The length under the profile; the O.D. right of the part.
PROFILE_KEEP = {
    "RingLength": (PROFILE_CENTER[0], _PROFILE_BOTTOM - 0.022),
}
# The length's text stands offset right of the front face's extension
# line, level with the dimension line and under the O.D.'s lower extension
# line (clarity, review 2026-10-23: text struck by both extension lines).
LENGTH_TEXT_XY = (_PROFILE_FRONT_X + 0.032, PROFILE_KEEP["RingLength"][1])
OD_ON_PROFILE = (_PROFILE_FRONT_X + 0.040, PROFILE_CENTER[1])

# The rear face's pick lies on its edge line between the bore and O.D. radii;
# its symbol stands above-left, clear of every dimension.
_FACE_PICK_UP = PROFILE_CENTER[1] + (BORE_DIA + OD) / 4.0 * _S
FACE_FINISHES = {
    "rear_face": (
        (_PROFILE_REAR_X, _FACE_PICK_UP),
        (_PROFILE_REAR_X - 0.022, _PROFILE_TOP + 0.014),
    ),
}
ISO_NOTE_XY = (0.315, 0.140)
# Datum A's tag stands outside the O.D. on the end view's lower-left ray,
# its leader crossing the annulus to the bore circle.  SolidWorks' native
# drop landed it on the Ø11.0 outline (farm run 20261027T131303762Z-7567dd7c,
# layout audit text-on-line), so the tag is placed: its centre this far off
# the end view's centre.
DATUM_A_ANGLE = math.radians(225.0)
DATUM_A_REACH = OD / 2.0 * _S + 0.0125
DATUM_A_SYMBOL = (
    END_CENTER[0] + DATUM_A_REACH * math.cos(DATUM_A_ANGLE),
    END_CENTER[1] + DATUM_A_REACH * math.sin(DATUM_A_ANGLE),
)
# The placed tag may not drift through the export's final rebuild by more
# than the native helper's limit.
DATUM_A_STABILITY_M = 0.0001
# Settled: everything of datum A but its leader stands this far outside the
# O.D., and the leader ends on the bore within this.
DATUM_A_AIR = 0.002
DATUM_A_LEADER_TOL = 0.0005
# The datum triangle (as lines or filled) lies within this of its tip.
DATUM_A_TRIANGLE_SPAN = 0.005
# Two leader primitives join where their ends meet within this.
_JOIN_TOL_M = 1e-5

# Datum A is the bore's axis, put on the end view's bore circle by
# SolidWorks' native placement, as the disc hub's is; only the O.D.'s runout
# reads it.  The end faces carry no datum and no frame.
# A frame's box as the hub's farm run drew its ⊥ 0.03 A (20261002T180658288Z):
# 7.03 tall and 26.75 wide on the sheet, its position its top-left corner,
# the leader leaving its side at mid-height.
FRAME_HEIGHT = 0.00703
FRAME_WIDTH = 0.02675
# The O.D.'s circular runout to A (coordinator ruling, #2014: it bounds the
# offset the wall charges) lands on the profile's upper O.D. line at z 0.7 L,
# its frame above the profile: right of the rear face's BEARING FACE symbol,
# left of the O.D.'s dimension line, over its upper extension line.
OD_RUNOUT_LANDING_Z_MM = 0.7 * LENGTH
OD_RUNOUT_FRAME = (_PROFILE_REAR_X + 0.0125, _PROFILE_TOP + 0.020)
OD_RUNOUT_LABEL = "spacer O.D. circular runout to bore"
# A projected landing may sit this far from its laid-out point.
_LANDING_TOL_M = 0.0005


def _profile_x(z_mm: float) -> float:
    """Sheet X of a model-Z station on the profile (+Z runs LEFT)."""
    return PROFILE_CENTER[0] - (z_mm - LENGTH / 2.0) * _S


# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (pd_transgear_pivot_spacer_spec: axis +Z; the front face, on the bar, at
# z = 0 is the datum end the length runs from; the rear face, the arm's
# bearing face, at z = LENGTH). The O.D. takes the title block's .XX row
# and its circular runout to the bore (datum A); the length its printed
# .197 ±.001 (the native band about the exact 5.0 mm model, read back as the
# printed limits); the bore its #11 drill under the DRILLED HOLES row, a
# bonded slip fit on MHA-PD-VN-57's shoulder (the clearance is the spec's
# analysis range, printed as REF). Each ``span`` is a diameter's model-Z extent.
# The sheet prints no manufacturing note. The declarations print nothing.
DRAWING_NOTES = ""
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pd_transgear_pivot_spacer"
_CALLOUTS = "pd_transgear_pivot_spacer_callouts"
_LENGTH_LOW, _LENGTH_HIGH = printed_deviations(
    LENGTH, _P["RingLength"], (-LENGTH_TOLERANCE, LENGTH_TOLERANCE), unit=UNIT
)
part_metadata(
    model_sources=("LENGTH", "OD", "BORE_DIA"),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "outward": ([0.0, 0.0, -1.0], ("__frame__",)),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), LENGTH),),
    requirements=("length",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": LENGTH}, ("LENGTH",)),
        "outward": ([0.0, 0.0, 1.0], ("LENGTH",)),
        "length": (
            limits(LENGTH, _P["RingLength"], (_LENGTH_HIGH, _LENGTH_LOW), unit=UNIT),
            ("LENGTH", "LENGTH_TOLERANCE", "UNIT", (_SELF, "PROFILE_KEEP")),
        ),
        "length_nominal": (LENGTH, ("LENGTH",)),
        "length_from": ("datum_end", ((_SELF, "PROFILE_KEEP"),)),
    },
    precision={"length": _P["RingLength"]},
)
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(OD),),
    requirements=("dia", "runout"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "span": ([0.0, LENGTH], ("LENGTH",)),
        "dia": (
            limits(OD, _P["RingOd"], unit=UNIT),
            ("OD", "UNIT", (_SELF, "OD_ON_PROFILE")),
        ),
        "dia_nominal": (OD, ("OD",)),
        "runout": (
            OD_RUNOUT,
            ("GEOMETRIC_TOLERANCES_IN", (_SELF, "OD_RUNOUT_FRAME")),
        ),
        "datum": ("bore", ("BORE_DATUM",)),
    },
    precision={"dia": _P["RingOd"]},
)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(BORE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "span": ([0.0, LENGTH], ("LENGTH",)),
        "dia": (
            drilled_limits(BORE_DIA, _P["BoreDia"], unit=UNIT),
            ("BORE_DIA", "BORE_DIA_BAND", "UNIT", (_SELF, "END_KEEP")),
        ),
        "nominal_dia": (BORE_DIA, ("BORE_DIA",)),
        "thru": (True, ("BORE_CALLOUT",)),
        "process": ("drill", ("BORE_CALLOUT",)),
        "wall_min": (WALL_WORST, ("WALL_WORST",)),
        "diametral_clearance_ref": (
            list(BOND_GAP),
            ("BOND_GAP", (_CALLOUTS, "BOND_CALLOUT")),
        ),
        "mate": (callouts.SCREW_NUMBER, ((_CALLOUTS, "SCREW_NUMBER"),)),
        "callout": (
            DIMENSION_CALLOUTS["BoreDia"],
            ((_CALLOUTS, "CALLOUTS"), (_SELF, "DIMENSION_CALLOUTS")),
        ),
    },
    precision={"dia": _P["BoreDia"]},
)


@_telemetry.traced("pivot_spacer.od_runout_landing")
def _od_runout_landing(adapter: Any, view: Any) -> tuple[float, float]:
    """The O.D.'s upper line on the profile at OD_RUNOUT_LANDING_Z_MM: of the
    O.D.'s two silhouette points at that station (model -X and +X), the one
    the view draws higher, proved to lie on the laid-out upper line."""
    r_m, z_m = OD / 2000.0, OD_RUNOUT_LANDING_Z_MM / 1000.0
    landing = max(
        model_points_in_view(
            adapter,
            view,
            ((-r_m, 0.0, z_m), (r_m, 0.0, z_m)),
            label="spacer O.D. runout landing",
            names=("-X line", "+X line"),
        ),
        key=lambda point: point[1],
    )
    expected = (_profile_x(OD_RUNOUT_LANDING_Z_MM), _PROFILE_TOP)
    if math.dist(landing, expected) > _LANDING_TOL_M:
        raise RuntimeError(
            f"spacer O.D. runout landing {landing!r} is off the laid-out upper "
            f"O.D. line at {expected!r}"
        )
    return landing


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a model dimension to the projection that shows its extension lines."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name,
        "DIMENSION",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    drawing.DragModelDimension(
        view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0
    )
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    matches = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


@_telemetry.traced("pivot_spacer.assert_part_authored_text")
def _assert_part_authored_text(adapter: Any, annotations: list[Any]) -> None:
    """Every authored dimension prints exactly once, with the text lanes its
    part wrote (draw_pd_transgear_pin).  Read-only: text set from the sheet
    would write through to the source part (#1942)."""
    wanted = callouts.authored_by_name()
    displays: dict[str, list[Any]] = {name: [] for name in wanted}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in displays:
            displays[name].append(
                _early_bound(
                    _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                    "IDisplayDimension",
                )
            )
    counts = {name: len(found) for name, found in displays.items() if len(found) != 1}
    if counts:
        raise RuntimeError(f"authored dimensions not printed exactly once: {counts!r}")
    wrong = {
        (name, lane): printed
        for name, lanes in wanted.items()
        for lane, text in lanes.items()
        if callouts.callout_rows(printed := str(displays[name][0].GetText(lane) or ""))
        != callouts.callout_rows(text)
    }
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )


def _datum_a_ink(
    adapter: Any, tag: Any
) -> tuple[list[Segment], list[tuple[float, float]], Box]:
    """Datum A's rendered ink from its own GetDisplayData, decoded by the
    layout audit's own primitives (_layout_audit): its strokes (lines with
    zero-length records dropped, polylines, polygons), the vertices of a
    filled triangle or arrowhead, and its letter's box (display_box, which
    estimates a run SolidWorks reports no width for)."""
    annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    display, refused = annotation_display(adapter, annotation)
    if refused or not display:
        raise RuntimeError(f"datum A has no readable display data: {refused!r}")
    strokes = [
        segment
        for raw in display.get("lines", ())
        if (segment := line_segment(raw)) is not None
    ]
    for raw in display.get("polylines", ()):
        strokes.extend(polyline_segments(raw))
    for raw in display.get("polygons", ()):
        strokes.extend(polygon_segments(raw))
    vertices = [
        (float(raw[i]), float(raw[i + 1]))
        for raw in display.get("triangles", ())
        if len(raw) >= 9
        for i in (0, 3, 6)
    ] + [
        (float(raw[0]), float(raw[1]))
        for raw in display.get("arrows", ())
        if len(raw) >= 3
    ]
    texts = display.get("texts", ())
    if not any(str(text.get("t", "")).strip() == BORE_DATUM for text in texts):
        raise RuntimeError(
            f"datum A renders no {BORE_DATUM!r} letter: "
            f"{[text.get('t') for text in texts]!r}"
        )
    letter = display_box({"texts": texts})
    if letter is None:
        raise RuntimeError("datum A's letter has no box")
    return strokes, vertices, letter


def _ends(segment: Segment) -> tuple[tuple[float, float], tuple[float, float]]:
    return (segment.x0, segment.y0), (segment.x1, segment.y1)


def _leader_path(near: list[Segment], tip: tuple[float, float]) -> list[Segment]:
    """The strokes of datum A's triangle and leader among ``near``: those
    touching the tip (the triangle drawn as lines, the leader's first piece),
    then every stroke joined end to end with the path and lying on the
    leader's line, however SolidWorks splits it into primitives."""
    path = [
        s
        for s in near
        if min(math.dist(end, tip) for end in _ends(s)) <= DATUM_A_TRIANGLE_SPAN
    ]
    if not path:
        return []
    far = max(
        (end for s in path for end in _ends(s)), key=lambda end: math.dist(end, tip)
    )
    length = math.dist(far, tip)
    ux, uy = (far[0] - tip[0]) / length, (far[1] - tip[1]) / length

    def on_leader(point: tuple[float, float]) -> bool:
        return (
            abs((point[0] - tip[0]) * uy - (point[1] - tip[1]) * ux)
            <= DATUM_A_LEADER_TOL
        )

    grown = True
    while grown:
        grown = False
        joints = [end for s in path for end in _ends(s)]
        for s in near:
            if s in path or not all(on_leader(end) for end in _ends(s)):
                continue
            if any(
                math.dist(end, joint) <= _JOIN_TOL_M
                for end in _ends(s)
                for joint in joints
            ):
                path.append(s)
                grown = True
    return path


@_telemetry.traced("pivot_spacer.datum_a_clear")
def _assert_datum_a_clear(adapter: Any, tag: Any) -> None:
    """Datum A's settled ink: its tip (the triangle's or leader's point
    nearest the axis, in whichever primitives SolidWorks draws it) lies on
    the bore; every stroke within DATUM_A_AIR of the O.D. belongs to the
    triangle or the leader path from that tip (_leader_path), and the leader
    leaves the O.D.; the frame, the shoulder and the rendered letter all
    stand DATUM_A_AIR outside the O.D. (the clearance
    test_datum_a_tag_stands_off_the_od_... sets on the requested point)."""
    strokes, vertices, letter = _datum_a_ink(adapter, tag)
    od_r = OD / 2.0 * _S
    bore_r = BORE_DIA / 2.0 * _S
    points = [end for s in strokes for end in _ends(s)] + vertices
    if not points:
        raise RuntimeError("datum A drew no ink")
    tip = min(points, key=lambda point: math.dist(point, END_CENTER))
    if abs(math.dist(tip, END_CENTER) - bore_r) > DATUM_A_LEADER_TOL:
        raise RuntimeError(f"datum A's tip is at {tip!r}, not on the bore")
    near = [
        s for s in strokes if point_segment_distance(END_CENTER, s) < od_r + DATUM_A_AIR
    ]
    path = _leader_path(near, tip)
    stray = [s for s in near if s not in path]
    if stray:
        raise RuntimeError(
            f"datum A's ink stands on the O.D. off its leader: {stray!r}"
        )
    if not any(
        math.dist(end, END_CENTER) >= od_r + DATUM_A_AIR
        for s in path
        for end in _ends(s)
    ):
        raise RuntimeError("datum A has no leader from outside the O.D. to the bore")
    nearest = (
        min(max(END_CENTER[0], letter.xmin), letter.xmax),
        min(max(END_CENTER[1], letter.ymin), letter.ymax),
    )
    if math.dist(nearest, END_CENTER) < od_r + DATUM_A_AIR:
        raise RuntimeError(f"datum A's letter {letter!r} stands on the O.D.")


def _datum_a_live(
    adapter: Any, view: Any, tag: Any, bore_edge: Any
) -> tuple[float, float]:
    """Datum A as the view holds it (the native helper's readback): the
    view's one live datum tag is ``tag``, labelled A, shouldered, attached to
    the bore edge alone and not dangling.  Returns its native position."""
    xy, shoulder, _equality = read_native_datum(
        adapter.swApp,
        _early_bound(view, "IView"),
        tag,
        bore_edge,
        datum=BORE_DATUM,
        label="spacer bore axis",
    )
    if shoulder != "shouldered":
        raise RuntimeError("datum A lost its shoulder")
    return xy


@_telemetry.traced("pivot_spacer.place_datum_a")
def _place_datum_a(
    adapter: Any, view: Any, bore_edge: Any
) -> tuple[Any, tuple[float, float]]:
    """Place datum A on the validated bore edge and prove the placement
    survives a rebuild within the native helper's 0.1 mm.

    ``add_datum_feature`` rebuilds before it returns, so the requested
    position is applied again and read before a second rebuild: a tag that
    re-solves on rebuild moves here and is refused."""
    tag = add_datum_feature(
        adapter,
        view,
        entity=bore_edge,
        symbol_xy=DATUM_A_SYMBOL,
        datum=BORE_DATUM,
        label="spacer bore axis",
        shoulder=True,
    )
    annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(DATUM_A_SYMBOL[0], DATUM_A_SYMBOL[1], 0.0):
        raise RuntimeError("failed to re-apply datum A's position")
    placed = _datum_a_live(adapter, view, tag, bore_edge)
    rebuild_drawing(adapter, label="datum A stability")
    rebuilt = _datum_a_live(adapter, view, tag, bore_edge)
    drift = math.dist(placed, rebuilt)
    if drift > DATUM_A_STABILITY_M:
        raise RuntimeError(f"datum A moved {drift * 1000.0:.3f} mm on rebuild")
    return tag, rebuilt


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-pivot-spacer source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("pd-transgear-pivot-spacer"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Pivot Spacer Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear hanger pivot spacer; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    profile = place_view(
        adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=VIEW_SCALE
    )
    native_profile = _early_bound(profile, "IView")
    native_profile.Angle = PROFILE_ANGLE
    if (
        abs(math.remainder(float(native_profile.Angle) - PROFILE_ANGLE, 2.0 * math.pi))
        > 1e-9
    ):
        raise RuntimeError("failed to lay the spacer profile horizontal")
    drawing_model.EditRebuild3()
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISOMETRIC_VIEW_SCALE
    )
    for view in (end, profile, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="spacer end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="spacer profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    od_donors = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) == "RingOd"
    ]
    if len(od_donors) != 1:
        raise RuntimeError("expected one spacer O.D. donor dimension")
    moved_od = _move_dimension(
        adapter, od_donors[0], profile, OD_ON_PROFILE, source_view=end
    )
    end_annotations = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) != "RingOd"
    ]
    annotations = [*end_annotations, *profile_annotations, moved_od]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the length's and bore's bands are authored on the part; the sheet
    # only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_authored_text(adapter, annotations)
    offset_dimension_text(adapter, profile_annotations, {"RingLength": LENGTH_TEXT_XY})
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add center marks to the spacer end view")
    # The turning axis, picked on the O.D. face above it.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0], PROFILE_CENTER[1] + OD * _S / 4.0),
        label="pivot spacer axis centerline",
    )
    pick, symbol = FACE_FINISHES["rear_face"]
    add_surface_finish(
        adapter,
        profile,
        edge_xy=pick,
        symbol_xy=symbol,
        control=surface_finish_by_key(SURFACE_FINISHES, "rear_face"),
        label="spacer rear (arm) face finish",
        char_height=0.0025,
    )
    # Datum A, the bore, on the end view where it shows round.  The edge is
    # first proved to be the source part's one bore cylinder at the spec's
    # radius (the native helper's validation), then the tag is placed.
    bore_edge = visible_circle_edge(adapter, end, BORE_DIA)
    validate_source_axis_edge(
        adapter.swApp,
        _early_bound(end, "IView"),
        bore_edge,
        SOURCE.resolve(strict=True),
        radius_m=BORE_DIA / 2000.0,
        label="spacer bore axis",
    )
    datum_a, datum_a_xy = _place_datum_a(adapter, end, bore_edge)
    # The O.D. runs true to A.
    od_face = resolve_faces(
        _early_bound(_early_bound(profile, "IView").ReferencedDocument, "IModelDoc2"),
        {"od": CylinderFace(OD, contains_z_mm=LENGTH / 2.0)},
    )["od"]
    add_feature_control_frame(
        adapter,
        profile,
        entity=od_face,
        entity_type="FACE",
        leader_attach_xy=_od_runout_landing(adapter, profile),
        frame_xy=OD_RUNOUT_FRAME,
        characteristic="circular_runout",
        tolerance=GEOMETRIC_TOLERANCES_IN["o.d. circular runout to bore"],
        datums=(BORE_DATUM,),
        label=OD_RUNOUT_LABEL,
    )
    # Re-assert the display mode now the last annotation has landed: an
    # annotation attached after placement can leave a view's edge set
    # unregenerated, and only a real mode change rebuilds it.
    for view in (end, profile):
        set_hidden_lines_removed(adapter, view)

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    def datum_a_settled() -> None:
        """After the export's last rebuild datum A is still the view's live,
        attached tag, stands where it was placed (0.1 mm), and its settled
        ink clears the O.D. (not only the requested point)."""
        drift = math.dist(_datum_a_live(adapter, end, datum_a, bore_edge), datum_a_xy)
        if drift > DATUM_A_STABILITY_M:
            raise RuntimeError(
                f"datum A moved {drift * 1000.0:.3f} mm after the final rebuild"
            )
        _assert_datum_a_clear(adapter, datum_a)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pivot Spacer Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(datum_a_settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
