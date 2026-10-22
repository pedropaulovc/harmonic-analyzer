r"""Create the manufacturing drawing for the transgear arm plate (MHA-PD-19).

The plan is ``*Front``, looking at the REAR face: the outline from the bore
axis K (the end radius, the bar width, the top corners, the kink), the
reamed bore with its finish, both screw holes with their countersinks, and
the hole positions from the bore (the countersink Ø from the blanked
``CountersinkReference`` sketch round the +X hole, shown in this view only:
the drill callout leads to the -X hole from the upper left, the countersink
callout to the +X hole from the upper right).  The back view (``*Back``, the
mounting face) carries the notch face's two corner heights, the only view
where that edge is a solid line.  Section A-A cuts the plan on the bore axis
along Y -- the plane of the revolved hub and boss -- so the thickness over
the arm, the notch depth and the hub face's station (a baseline from the
mounting face), the hub-to-boss length and both diameters print on solid
cut edges, and the hub and boss thrust faces carry their finish.

Every kept dimension's text point is a model point (mm) projected through
its view, so the placement holds whichever way SolidWorks orients the
section.

The knob bore is the plate origin; screw stations, top corners and notch
corners come from ``pd_transgear_arm_plate_geometry`` at the current reducer
centre. The print imports those model dimensions rather than restating a
historical bore offset.

A second sheet shows the actual screw- and knob-bore sections with their
complete projected zones and the locator's attached matched-set acceptance.
It adds no geometry, tolerance or alternate numerical control.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any
from solidworks_mcp.adapters.com_variant import double_array

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    iter_views,
    place_view,
    view_name,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_annotation_extent import require_clear, require_inside, sheet_region
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
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_edges import scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
import _drawing_hidden_sketches as hidden_sketches
from _drawing_leader_notes import add_attached_note, add_leader_note
from _drawing_leaders import section_line_segments
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _native_projected_zone import require_saved_projected_gtols
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from pd_paper_drive_assembly_steps import matched_locator_notes
import pd_transgear_arm_spec as ARM_SPEC
from pd_transgear_arm_plate_geometry import (
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_DIA_MM,
    BORE_DIA,
    BOSS_DIA,
    BOSS_FACE_Z,
    EDGE_MINUS_X,
    EDGE_PLUS_X,
    END_R,
    FRONT_FACE_Z,
    HUB_DIA,
    HUB_FACE_Z,
    KINK,
    KINK_RIGHT,
    NOTCH_LEFT,
    NOTCH_RIGHT,
    REAR_FACE_Z,
    SCREW_HOLE_DIA,
    SCREW_HOLES,
    TOP_LEFT,
    TOP_RIGHT,
    arm_upper_edge_y,
)
from pd_transgear_arm_plate_spec import (
    LOCATOR_CALLOUT,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    KNOB_PROJECTED_ZONE_CALLOUT,
    SCREW_PROJECTED_ZONE_CALLOUT,
    HUB_STATION_CALLOUT,
    HUB_TO_BOSS_CALLOUT,
    BORE_CALLOUT,
    BORE_PLACES,
    CSK_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_COUNT_CALLOUT,
    ISO_VIEW_SCALE,
    SCREW_HOLE_CALLOUT,
    SURFACE_FINISHES,
)


SPEC = DRAWINGS_BY_NAME["pd_transgear_arm_plate"]
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

# The plate is 56 x 38 in plan and 29 deep: at 2:1 the plan, the back view
# and section A-A stand side by side above the title block (x > 0.216 below
# y 0.066). The section stands far enough right that its hub diameter clears
# the back view's notch height and its boss diameter ends inside the border
# (x 0.419), which leaves no room beside it for the isometric: that stands
# in the lower strip between the notes and the title block, its caption
# above it, under the back view's edge dimensions.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
SHEET_NAMES = ("Geometry", "Projected zones")
PROJECTION_CAPTION = "PROJECTED ZONES — CONTROLS ON SHEET 1"
# 12 mm lower than run 20261010T001620278Z, whose top frame row and locator
# callout printed above the border; section A-A's caption still clears the
# title block (it reached y 0.085).
PLAN_CENTER = (0.080, 0.153)
BACK_CENTER = (0.223, PLAN_CENTER[1])
SECTION_CENTER = (0.347, PLAN_CENTER[1])
ISO_CENTER = (0.180, 0.045)
ISO_NOTE_XY = (0.150, 0.081)
# The matched-pair acceptance belongs to the actual locator rim on the
# supplemental, un-dimensioned view, not to an ambiguous general note.
# Preserve the shared emitter's S-K value, acceptance and assembly step refs.
LOCATOR_MATCH_XY = (0.014, 0.195)
LOCATOR_MATCH_TEXT = "\n".join((
    f"S-K: ACTUAL Ø{BORE_DIA:.{BORE_PLACES}f} KNOB-BORE K TO ARM "
    f"Ø{ARM_SPEC.PIN_BORE_DIA:.{ARM_SPEC.PIN_BORE_DIA_PLACES}f} PIN-BORE S;",
    "NOT TAP / LOCATOR STATION OR ALONG-ARM X.",
    matched_locator_notes(
        "TRANSGEAR ARM " + _config.parts("pd-transgear-arm")["number"],
        _config.parts("pd-transgear-arm-plate")["number"],
        on_arm=False,
        width=62,
    ),
))

_TOP = TOP_LEFT[1]  # the plate's highest point (the top edge's -X corner)
_SECTION_TOP = arm_upper_edge_y(0.0)
_BOTTOM = -END_R
_Z_PLAN = BOSS_FACE_Z

# The cutting line: along Y on the bore axis, past both ends of the plate.
SECTION_LINE_OVERRUN_MM = 3.0
SECTION_LINE_MODEL = (
    (0.0, _BOTTOM - SECTION_LINE_OVERRUN_MM, _Z_PLAN),
    (0.0, _SECTION_TOP + SECTION_LINE_OVERRUN_MM, _Z_PLAN),
)

# Per-view survivors of the marked-dimension import, each at the MODEL point
# (mm) its text stands on.  Plan: positions stack above the top edge,
# nearest first, the first row clear of the cutting line's arrow and letter
# (they reach about 5 above the section's top edge); the heights from K
# stand outboard of each side, the hole height's wide toleranced text wholly
# between the edge and the top-corner height's dimension line.
# Rows 4 apart (8 mm on the sheet: 4.4 mm air between 3.6 mm texts) keep the
# locator's witness lines under the locator diameter's shoulder (at 5 apart
# a top row rose through it: farm run 20261009T224545531Z,
# shoulder-crosses-line). The width stands under the centre view instead:
# across the top it was the one dimension line the reamed-hole leader had
# to cross (machinist review of the r3 sheets).
PLAN_ROWS = tuple(_SECTION_TOP + 8.0 + 4.0 * row for row in range(3))
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    "ScrewHoleX2": (SCREW_HOLES[1][0] / 2.0, PLAN_ROWS[0], _Z_PLAN),
    "ScrewHoleX1": (SCREW_HOLES[0][0] / 2.0, PLAN_ROWS[1], _Z_PLAN),
    "KinkY": (EDGE_MINUS_X - 5.0, KINK[1] / 2.0, _Z_PLAN),
    "TopLeftY": (EDGE_MINUS_X - 11.0, TOP_LEFT[1] / 2.0, _Z_PLAN),
    "KinkRightY": (EDGE_PLUS_X + 5.0, KINK_RIGHT[1] / 2.0, _Z_PLAN),
    "ScrewHoleY": (EDGE_PLUS_X + 9.5, SCREW_HOLES[0][1] / 2.0, _Z_PLAN),
    "TopRightY": (EDGE_PLUS_X + 19.0, TOP_RIGHT[1] / 2.0, _Z_PLAN),
    "EndR": (0.7071 * END_R + 11.0, -0.7071 * END_R - 9.0, _Z_PLAN),
    "BoreDia": (EDGE_MINUS_X - 4.0, _BOTTOM - 6.0, _Z_PLAN),
    "ScrewHoleDia": (EDGE_MINUS_X - 6.0, _TOP + 8.0, _Z_PLAN),
    "CskDia": (EDGE_PLUS_X + 8.0, _TOP + 8.0, _Z_PLAN),
    "LocatorX1": (LOCATOR_SITES_MM[0][0] / 2.0, PLAN_ROWS[2], _Z_PLAN),
    # High enough that its callout lines clear the screw-hole callout; three
    # short lines keep its left edge inside the border. Its leader runs down
    # to locator 1 left of every location dimension line.
    "LocatorDia1": (EDGE_MINUS_X - 4.5, _TOP + 23.75, _Z_PLAN),
}
# Back view (the mounting face): the notch face's corner heights, outboard,
# and both side edges from K below the end round, clear of every leader.
BACK_KEEP: dict[str, tuple[float, float, float]] = {
    "EdgeLeftX": (EDGE_MINUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "EdgeRightX": (EDGE_PLUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "NotchLeftY": (EDGE_MINUS_X - 4.0, NOTCH_LEFT[1] / 2.0, FRONT_FACE_Z),
    "NotchRightY": (EDGE_PLUS_X + 4.0, NOTCH_RIGHT[1] / 2.0, FRONT_FACE_Z),
    "LocatorY1": (EDGE_MINUS_X - 8.0, LOCATOR_SITES_MM[0][1] / 2.0, 0.0),
    "LocatorY2": (EDGE_PLUS_X + 9.0, LOCATOR_SITES_MM[1][1] / 2.0, 0.0),
}
# Section A-A (x = 0): the stations along Z are a baseline from the mounting
# face (the face that seats on the arm), stacked above the plate nearest
# first -- the rear face, the front face, the hub face -- and the overall
# hub-to-boss length stands alone below, clear of the view's caption.  The
# diameters stand beyond the hub and boss faces, outboard of the faces'
# finish symbols.
SECTION_KEEP: dict[str, tuple[float, float, float]] = {
    "ThicknessOverArm": (0.0, _SECTION_TOP + 5.0, REAR_FACE_Z / 2.0),
    "NotchDepth": (0.0, _SECTION_TOP + 11.0, FRONT_FACE_Z / 2.0),
    "HubFaceToMounting": (0.0, _SECTION_TOP + 17.0, HUB_FACE_Z / 2.0),
    "HubToBoss": (0.0, _BOTTOM - 5.0, (HUB_FACE_Z + BOSS_FACE_Z) / 2.0),
    "HubDia": (0.0, 0.0, HUB_FACE_Z - 15.5),
    "BossDia": (0.0, 0.0, BOSS_FACE_Z + 17.0),
}
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "ScrewHoleDia": SCREW_HOLE_CALLOUT,
    "CskDia": CSK_CALLOUT,
    "LocatorDia1": LOCATOR_CALLOUT,
    "HubFaceToMounting": HUB_STATION_CALLOUT,
    "HubToBoss": HUB_TO_BOSS_CALLOUT,
}
CALLOUTS_ABOVE = {
    "ScrewHoleDia": HOLE_COUNT_CALLOUT,
    "CskDia": HOLE_COUNT_CALLOUT,
}
# The bore finish symbol stands below the end round, left of the bore axis:
# clear of the bore callout (lower left), the end radius (lower right) and
# the bore's projected-axis frame, whose leader rises right of this one.
BORE_FINISH_MODEL = (-9.0, _BOTTOM - 9.0, _Z_PLAN)
FINISH_CHAR_HEIGHT = 0.0025
# Position frames, sheet metres. A frame's xy is its top-left corner; it is
# about 59 mm wide with a projected zone (44 mm without), and its leader
# leaves the end nearer the feature through a 6.3 mm shoulder (measured on
# run 20261009T214031408Z). The frames stand in three rows above the back
# view, which mirrors X, so its hole frames sit outboard of their own holes
# (no crossing) and the two through-bore locator leaders drop between the
# hole leaders. The plan carries no frame: each countersink is coaxial with
# its hole, as required at the countersink callout.
FRAME_ROWS = (0.262, 0.250, 0.238)
# Move the mounting-face view 5 mm right to separate its boxed locator
# offsets from the rear-face outline heights. Section A-A stands 4 mm
# farther right, leaving both the hub-diameter lane and the boss-side
# border clear. The frame leaders follow the mounting view's position.
_BACK_FEATURE_SHIFT = 0.02375
FRAME_XY = {
    "plate_hole_1_position": (0.228 + _BACK_FEATURE_SHIFT, FRAME_ROWS[2]),
    "plate_hole_2_position": (0.1174 + _BACK_FEATURE_SHIFT, FRAME_ROWS[2]),
    "plate_locator_1_position": (0.2098 + _BACK_FEATURE_SHIFT, FRAME_ROWS[0]),
    "plate_locator_2_position": (0.2183 + _BACK_FEATURE_SHIFT, FRAME_ROWS[1]),
}
# The thrust faces' finish symbols, on section A-A where each face is
# edge-on: the pick lands on the face's own cut edge, midway across the
# annulus between the bore and the face's diameter (not at the bore mouth,
# where it read as a note on the diameter beside it), and the symbol stands
# level with it beyond the face, inside the diameters' extension lines.  A
# symbol reaches about 1 left and 7.5 right of its point (model mm at 2:1,
# the Ra text running right): the hub's stands far enough out that its text
# clears the hub face. Model points, mm.
FINISH_SYMBOL_REACH = (1.0, 7.5)
_ModelPoint = tuple[float, float, float]


def _annulus_mid_y(face_dia: float) -> float:
    """Below the axis, midway across a thrust face's annulus."""
    return -(BORE_DIA + face_dia) / 4.0


FACE_FINISHES: dict[str, tuple[_ModelPoint, _ModelPoint]] = {
    "hub_face": (
        (0.0, _annulus_mid_y(HUB_DIA), HUB_FACE_Z),
        (0.0, _annulus_mid_y(HUB_DIA), HUB_FACE_Z - 9.5),
    ),
    "boss_face": (
        (0.0, _annulus_mid_y(BOSS_DIA), BOSS_FACE_Z),
        (0.0, _annulus_mid_y(BOSS_DIA), BOSS_FACE_Z + 4.0),
    ),
}


def _sheet_xy(
    adapter: Any, view: Any, point_mm: _ModelPoint, label: str
) -> tuple[float, float]:
    """Project a model point (mm) onto the sheet through ``view``."""
    return model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in point_mm), label=label
    )


def _sheet_keep(
    adapter: Any, view: Any, keep: dict[str, _ModelPoint], label: str
) -> dict[str, tuple[float, float]]:
    """Project each kept dimension's model text point onto the sheet."""
    return {
        name: _sheet_xy(adapter, view, point, f"{label} {name}")
        for name, point in keep.items()
    }


def _face_view_labels(adapter: Any, plan: Any, back: Any, iso: Any) -> None:
    """Identify the deliberately removed rear view by a true viewing arrow."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateView(""):
        raise RuntimeError("failed to activate plate face-view captions")
    for text, x, y in (
        ("VIEW D (REAR FACE)", PLAN_CENTER[0] - 0.040, 0.070),
        ("MOUNTING FACE A", BACK_CENTER[0] - 0.022, 0.078),
    ):
        if add_note(adapter, text, x, y) is None:
            raise RuntimeError(f"failed to add plate {text.lower()} caption")
    # *Front looks along -Z at the rear face. Projecting two points with
    # the same X/Y makes the D arrow parallel to that actual viewing ray.
    tip_xy = _sheet_xy(adapter, iso, (10.0, 20.0, REAR_FACE_Z), "view D arrow tip")
    note = add_leader_note(
        adapter, "D",
        text_xy=_sheet_xy(adapter, iso, (10.0, 20.0, 22.0), "view D arrow tail"),
        attach_xy=tip_xy,
        view=iso, label="rear-face removed-view D direction",
    )
    # The pinned drawing.add_note ignores its height argument. Set the
    # actual format instead; CharHeight explicitly selects system units
    # (ITextFormat.IsHeightSpecifiedInPts), then re-read that authority.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError("plate view D arrow has no text format")
    text_format = _early_bound(text_format, "ITextFormat")
    text_format.CharHeight = 0.005
    if annotation.SetTextFormat(0, False, text_format) is not True:
        raise RuntimeError("failed to size plate view D arrow letter")
    rebuild_drawing(adapter, label="plate view D arrow letter")
    persisted = annotation.GetTextFormat(0)
    if persisted is None:
        raise RuntimeError("plate view D arrow lost its text format")
    persisted = _early_bound(persisted, "ITextFormat")
    if (
        persisted.IsHeightSpecifiedInPts() is not False
        or abs(float(persisted.CharHeight) - 0.005) > 1e-7
    ):
        raise RuntimeError("plate view D arrow height did not persist in system units")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or max(
        abs(float(points[-3]) - tip_xy[0]), abs(float(points[-2]) - tip_xy[1])
    ) > 0.001:
        raise RuntimeError("plate view D arrow tip moved when its letter was sized")


def _projected_axis_graphic(
    adapter: Any, view: Any, *, name: str, xy_mm: tuple[float, float],
    direction: float,
) -> None:
    """A source-length chain, owned by the actual side-on section view.

    As on the summing-lever drawing, map sheet points into the view sketch
    and bypass inference snaps. The native model FCF, not this graphic,
    remains the numerical control.
    """
    control = next(control for control in GEOMETRIC_CONTROLS if control.name == name)
    height = control.projected_zone_height_mm
    if height is None:
        raise RuntimeError(f"plate {name} has no native projected height")
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate plate {name} projection view")
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for z in (0.0, direction * height):
        x, y = _sheet_xy(
            adapter, view, (xy_mm[0], xy_mm[1], z), f"{name} projected endpoint"
        )
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError(f"failed to create plate {name} projected axis")
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
        placed = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
        actual = [float(adapter._get_attr_or_call(placed, axis)) for axis in "XYZ"]
        if max(abs(a - b) for a, b in zip(actual, expected)) > 1e-9:
            raise RuntimeError(f"plate {name} projected-axis endpoint moved")
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0
    if int(segment.Color) != 0:
        raise RuntimeError(f"plate {name} projected-axis color did not persist")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"plate {name} projected axis")


def _assert_projection_notes_clear(adapter: Any, notes: dict[str, Any]) -> None:
    """Refuse settled native note ink that overlaps or loses its attachment."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if drawing.ActivateSheet(SHEET_NAMES[1]) is not True:
        raise RuntimeError("failed to inspect plate projected-zone sheet")
    region = sheet_region(adapter)
    template = DRAWING_TEMPLATES[SPEC.layout]
    boxes = {
        "title block": (
            template.title_block_left_m, region.ymin,
            region.xmax, template.title_block_top_m,
        )
    }
    view_boxes = dict(boxes)
    section_labels: set[str] = set()
    for raw_view in iter_views(adapter):
        label = "view " + view_name(adapter, raw_view)
        view = _early_bound(raw_view, "IView")
        outline = tuple(float(value) for value in view.GetOutline() or ())
        if (
            len(outline) != 4
            or not all(math.isfinite(value) for value in outline)
            or outline[0] >= outline[2]
            or outline[1] >= outline[3]
        ):
            raise RuntimeError(f"plate {label} has no readable native outline")
        require_inside(f"plate {label}", outline, region)
        require_clear(f"plate {label}", outline, view_boxes)
        view_boxes[label] = outline
        boxes[label] = outline
        _telemetry.info(f"plate projected-zone {label} native outline: {outline!r}")
        sections = tuple(view.GetSectionLines() or ())
        if sections:
            strokes = section_line_segments(adapter, view)
            if not strokes:
                raise RuntimeError(f"plate {label} has no native section-line ink")
            for index, (start, end) in enumerate(strokes):
                stroke_box = (
                    min(start[0], end[0]), min(start[1], end[1]),
                    max(start[0], end[0]), max(start[1], end[1]),
                )
                require_inside(f"plate {label} section stroke {index}", stroke_box, region)
                boxes[f"{label} section stroke {index}"] = stroke_box
        for raw_section in sections:
            section = _early_bound(raw_section, "IDrSection")
            section_label = str(section.GetLabel())
            section_labels.add(section_label)
            text_format = _early_bound(section.GetTextFormat(), "ITextFormat")
            height = (
                float(text_format.CharHeightInPts) * 0.0254 / 72.0
                if text_format.IsHeightSpecifiedInPts()
                else float(text_format.CharHeight)
            )
            origins = tuple(float(value) for value in section.GetTextInfo() or ())
            if (
                not section_label or len(origins) != 6
                or not all(math.isfinite(value) for value in (*origins, height))
                or height <= 0.0
            ):
                raise RuntimeError(f"plate section {section_label!r} has no native label geometry")
            # Native API gives upper-left origins and height, not glyph width.
            # Reserve two heights per letter; exact ink stays a PDF-review gate.
            width = 2.0 * height * len(section_label)
            for index in range(2):
                x, y = origins[index * 3:index * 3 + 2]
                label_box = (x, y - height, x + width, y)
                require_inside(f"plate section {section_label} letter", label_box, region)
                boxes[f"section {section_label} letter {index}"] = label_box
    if section_labels != {"B", "C"}:
        raise RuntimeError(f"plate projected-zone section labels changed: {section_labels!r}")
    expected_text = {
        "screw zone": SCREW_PROJECTED_ZONE_CALLOUT,
        "knob zone": KNOB_PROJECTED_ZONE_CALLOUT,
        "matched pair": LOCATOR_MATCH_TEXT,
        "caption": PROJECTION_CAPTION,
    }
    if set(notes) != set(expected_text):
        raise RuntimeError("plate projected-zone note inventory changed before export")
    for label, raw_note in notes.items():
        note = _early_bound(raw_note, "INote")
        extent = tuple(float(value) for value in note.GetExtent() or ())
        if len(extent) != 6 or not all(math.isfinite(value) for value in extent):
            raise RuntimeError(f"plate {label} has no readable native ink extent")
        box = (
            min(extent[0], extent[3]), min(extent[1], extent[4]),
            max(extent[0], extent[3]), max(extent[1], extent[4]),
        )
        if box[0] >= box[2] or box[1] >= box[3]:
            raise RuntimeError(f"plate {label} has an empty native ink extent")
        if str(note.GetText()).replace("\r\n", "\n") != expected_text[label]:
            raise RuntimeError(f"plate {label} text changed before export")
        if label != "caption":
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            if (
                int(annotation.GetAttachedEntityCount3()) != 1
                or int(annotation.GetLeaderCount()) != 1
                or annotation.IsDangling() is not False
            ):
                raise RuntimeError(f"plate {label} lost its attached arrow")
        require_inside(f"plate {label}", box, region)
        require_clear(f"plate {label}", box, boxes)
        boxes[label] = box
        _telemetry.info(f"plate projected-zone {label} native ink: {box!r}")


def _projection_sheet(adapter: Any) -> dict[str, Any]:
    """Show each zone in its real section, not a fictitious off-plane bore.

    Section B cuts the two screw axes along X; C cuts the knob axis along
    Y. A separate sheet leaves the full 40.6 source extent visible without
    passing a chain through sheet 1's dimensions or shortening a zone.
    """
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate plate projected-zone sheet")
    # Keep all section geometry in the right-hand column; the long matched
    # acceptance and direction notes have their own left-hand ink column.
    plan = place_view(adapter, str(SOURCE), "*Front", 0.250, 0.205, scale=VIEW_SCALE)
    screw_y = SCREW_HOLES[0][1]
    screw_line = tuple(
        _sheet_xy(adapter, plan, point, "screw-axis section line")
        for point in (
            (EDGE_MINUS_X - SECTION_LINE_OVERRUN_MM, screw_y, _Z_PLAN),
            (EDGE_PLUS_X + SECTION_LINE_OVERRUN_MM, screw_y, _Z_PLAN),
        )
    )
    screw_section = create_section_view(
        adapter, plan, line_start=screw_line[0], line_end=screw_line[1],
        view_xy=(0.250, 0.100), section_label="B", scale=VIEW_SCALE,
        label="plate projected zones through both actual screw bores",
    )
    knob_line = tuple(
        _sheet_xy(adapter, plan, point, "knob-axis section line")
        for point in SECTION_LINE_MODEL
    )
    knob_section = create_section_view(
        adapter, plan, line_start=knob_line[0], line_end=knob_line[1],
        view_xy=(0.380, 0.150), section_label="C", scale=VIEW_SCALE,
        label="plate projected zone through actual knob bore",
    )
    for view in (plan, screw_section, knob_section):
        set_hidden_lines_removed(adapter, view)
    for index, xy in enumerate(SCREW_HOLES, 1):
        _projected_axis_graphic(
            adapter, screw_section, name=f"plate_hole_{index}_position",
            xy_mm=xy, direction=1.0,
        )
    _projected_axis_graphic(
        adapter, knob_section, name="knob_projected_axis",
        xy_mm=(0.0, 0.0), direction=-1.0,
    )
    notes: dict[str, Any] = {}
    notes["screw zone"] = add_attached_note(
        adapter, screw_section, text=SCREW_PROJECTED_ZONE_CALLOUT,
        entity_xy=_sheet_xy(
            adapter, screw_section,
            (SCREW_HOLES[0][0] - SCREW_HOLE_DIA / 2.0, screw_y, 1.0),
            "screw projected-zone wall",
        ),
        note_xy=(0.014, 0.043), label="screw projected-zone start and direction",
    )
    notes["knob zone"] = add_attached_note(
        adapter, knob_section, text=KNOB_PROJECTED_ZONE_CALLOUT,
        entity_xy=_sheet_xy(
            adapter, knob_section, (0.0, BORE_DIA / 2.0, -1.0),
            "knob projected-zone wall",
        ),
        note_xy=(0.014, 0.160), label="knob projected-zone start and direction",
    )
    locators = scan_view_edges(plan, label="matched plate locator callout")
    x, y = LOCATOR_SITES_MM[1]
    notes["matched pair"] = add_attached_note(
        adapter, plan, text=LOCATOR_MATCH_TEXT,
        entity=locators.circle_at(
            (x, y, REAR_FACE_Z), LOCATOR_HOLE_DIA_MM / 2.0,
            axis=(0.0, 0.0, 1.0), label="matched plate locator rear rim",
        ).edge,
        note_xy=LOCATOR_MATCH_XY, label="plate matched-pair acceptance",
    )
    if not drawing.ActivateView(""):
        raise RuntimeError("failed to activate plate projection-sheet caption")
    notes["caption"] = add_note(adapter, PROJECTION_CAPTION, 0.014, 0.260)
    if notes["caption"] is None:
        raise RuntimeError("failed to add plate projection-sheet caption")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to restore plate geometry sheet")
    return notes


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-arm-plate source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Arm Plate Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear arm plate; machined steel bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="transgear arm plate package"
    )
    drawing = _early_bound(drawing_model, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate plate geometry sheet")

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=VIEW_SCALE)
    line = [
        model_point_in_view(
            adapter,
            plan,
            tuple(value / 1000.0 for value in point),
            label="section line",
        )
        for point in SECTION_LINE_MODEL
    ]
    section = create_section_view(
        adapter,
        plan,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="plate section on the bore axis",
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (plan, back, section, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        annotation
        for view, keep, label in (
            (plan, PLAN_KEEP, "plan"),
            (back, BACK_KEEP, "back"),
            (section, SECTION_KEEP, "section A-A"),
        )
        for annotation in hidden_sketches.curate_view_dimensions(
            adapter,
            view,
            keep=_sheet_keep(adapter, view, keep, label),
            view_label=label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    ]
    # Decimal places and the explicit bands are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    # The coordinate values stay on their original native witnesses. Offset
    # only their text, into separate exterior lanes, so one baseline's
    # extension cannot cut another BASIC box or the reamed-hole leader.
    offset_dimension_text(
        adapter, annotations,
        _sheet_keep(adapter, plan, {
            "ScrewHoleX1": (EDGE_MINUS_X - 6.0, PLAN_ROWS[1], _Z_PLAN),
            "ScrewHoleX2": (EDGE_PLUS_X + 6.0, PLAN_ROWS[0], _Z_PLAN),
            "LocatorX1": (EDGE_MINUS_X - 6.0, PLAN_ROWS[2], _Z_PLAN),
        }, "offset basic text"),
    )
    # These are the same native feature datums and circular zones authored
    # on the part, not +/- positions retyped on a drawing. The drill mouths
    # and the through locator bores' rims on the Front sketch (z = 0) are
    # visible in *Back; the plan (*Front) carries datum C's clock edge.
    plan_edges = scan_view_edges(plan, label="plate rear-face locating PMI")
    back_edges = scan_view_edges(back, label="plate mounting-face drill PMI")
    placements = {
        # Above section A-A's station stack (its top text reaches y 0.2365),
        # so the tag's horizontal leader to the mounting face's extension
        # runs clear of the HubFaceToMounting text.
        "datum:A": PmiDrawingPlacement(
            section, (0.300, 0.244),
            attachment_xy=_sheet_xy(
                adapter, section, (0.0, SCREW_HOLES[0][1], 0.0),
                "plate mounting datum",
            ),
        ),
        "datum:B": PmiDrawingPlacement(
            plan, (0.037, 0.108),
            edge_entity=visible_circle_edge(adapter, plan, BORE_DIA),
        ),
        # C is the vertical +X side face, square to the X hole coordinates.
        # The tag stands 11 mm below the top corner so its horizontal leader
        # lands on that side face, not on the sloping top edge (machinist
        # review 2026-10-11 read the corner landing as the sloped face).
        "datum:C": PmiDrawingPlacement(
            plan, (0.128, 0.190),
            edge_entity=plan_edges.exact_line_through(
                (EDGE_PLUS_X, (TOP_RIGHT[1] + NOTCH_RIGHT[1]) / 2.0, REAR_FACE_Z),
                label="plate +X clock edge",
            ).edge,
        ),
        **{
            f"plate_hole_{index}_position": PmiDrawingPlacement(
                back, FRAME_XY[f"plate_hole_{index}_position"],
                edge_entity=back_edges.circle_at(
                    (x, y, 0.0), SCREW_HOLE_DIA / 2.0,
                    axis=(0.0, 0.0, 1.0), label=f"plate hole {index} position",
                ).edge,
            )
            for index, (x, y) in enumerate(SCREW_HOLES, 1)
        },
        # Below the end radius's text and right of the bore finish symbol.
        "knob_projected_axis": PmiDrawingPlacement(
            plan, (0.085, 0.088),
            edge_entity=visible_circle_edge(adapter, plan, BORE_DIA),
        ),
        **{
            f"plate_locator_{index}_position": PmiDrawingPlacement(
                back, FRAME_XY[f"plate_locator_{index}_position"],
                edge_entity=back_edges.circle_at(
                    (x, y, 0.0), LOCATOR_HOLE_DIA_MM / 2.0,
                    axis=(0.0, 0.0, 1.0), label=f"plate locator {index} position",
                ).edge,
                leader_attachment_xy=_sheet_xy(
                    adapter, back, (x - LOCATOR_HOLE_DIA_MM / 2.0, y, 0.0),
                    f"plate locator {index} outboard rim",
                ),
            ) for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1)
        },
    }
    project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="plate actual-bore locating frame",
    )
    _face_view_labels(adapter, plan, back, iso)
    for view, label in ((plan, "plan"), (back, "back")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME centre marks to the {label} view")

    add_surface_finish(
        adapter,
        plan,
        symbol_xy=model_point_in_view(
            adapter,
            plan,
            tuple(value / 1000.0 for value in BORE_FINISH_MODEL),
            label="bore finish symbol",
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "transgear_arm_plate_bore"),
        label="arm-plate bore finish",
        entity=visible_circle_edge(adapter, plan, BORE_DIA),
        char_height=FINISH_CHAR_HEIGHT,
    )
    for key, label in (
        ("hub_face", "arm-plate hub face finish"),
        ("boss_face", "arm-plate boss face finish"),
    ):
        pick, symbol = FACE_FINISHES[key]
        add_surface_finish(
            adapter,
            section,
            edge_xy=_sheet_xy(adapter, section, pick, f"{label} pick"),
            symbol_xy=_sheet_xy(adapter, section, symbol, f"{label} symbol"),
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=label,
            char_height=FINISH_CHAR_HEIGHT,
        )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    projection_notes = _projection_sheet(adapter)

    artefacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Plate Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        settled_checks=(lambda: _assert_projection_notes_clear(adapter, projection_notes),),
    )
    require_saved_projected_gtols(
        adapter, artefacts["drawing"], GEOMETRIC_CONTROLS,
        label="saved transgear arm plate drawing projected axes",
    )
    return artefacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
