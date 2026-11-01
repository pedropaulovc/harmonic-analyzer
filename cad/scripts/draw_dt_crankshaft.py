r"""Create the crankshaft MHA-DT-11 manufacturing drawing under drawing-guidelines.md.

The SLDPRT remains authoritative.  A shaft carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the three running/seat diameters keep
their native size bands, the journal keeps one bearing-surface finish, and
every length is an ordinary model dimension at its part-authored places.

The model's shaft axis runs along +Y from the dome root (local y=0, the plane
where MHA-DT-06 and MHA-DT-31 finish flush).  The single longitudinal view is the
``*Right`` orientation rotated a quarter turn in the sheet so the shaft lies
horizontal, as it sits in the lathe: dome on the left, far end on the right,
the MHA-DT-09 cross-hole seen as a true circle.  The crank-end view is the
``*Bottom`` orientation, which is exactly the third-angle LEFT view of that
rotated profile, so it sits on the profile's axis to its left at sheet scale.
It looks onto the seat spigot's face, so the two drive-pin holes show there
as true circles and are located and called out in that view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crankshaft.py dt-crankshaft
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any, Callable, Sequence

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    _SW_PREF_UNITS_LINEAR,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
    visible_component_entities,
)

from _check import check
from _com import _early_bound
from _drawing_annotation_extent import place_callout_clear
from _drawing_attachment import _assert_attached_to, _assert_leader_lands
from _drawing_centerline import add_view_centerline
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
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_selection import _select_view_entity
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_read import face_geometry
from _hole_spec import blind_cut_dia_mm
from _layout_audit import (
    COLLINEAR_TOL_M,
    InkSpan,
    TextItem,
    _segment_crossing,
    arrowhead_segments,
    ink_key,
    line_segment,
    match_ink_indices,
)
from _layout_geometry import (
    ARROW_TEXT_CLEARANCE_M,
    Box as InkBox,
    Segment,
    point_segment_distance,
    segment_box_distance,
)
from _pdf_ink import read_pdf_ink
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from build_dt_crankshaft import PINION_PIN_DIA, PINION_PIN_STATION_Y
from dt_crank_drive_gear_spec import inch_text
from dt_crank_pinion_spec import CRANKSHAFT_PIN_HOLE_PROCESS
from dt_crankshaft_notes import (
    CENTRES_NOTE,
    CHAIN_AIR_MATE,
    COLLAR_REAR_FINISH_TEXT,
    COLLAR_REAR_MATE,
    COLLAR_SEAT_MATE,
    CROSS_HOLE_CALLOUT,
    DRIVE_PIN_CALLOUT,
    DRIVE_PIN_DEPTH_BAND,
    DRIVE_PIN_LOCATION_CALLOUT,
    FIDUCIAL_NOTE,
    JOURNAL_FIT,
    JOURNAL_MATE,
    KNOCKOUT_CALLOUT_ABOVE,
    KNOCKOUT_CALLOUT_BELOW,
    PINION_SEAT_MATE,
    SHAFT_LENGTH_MATE,
    SHANK_MATE,
    SLIDING_FIT,
    SPIGOT_AIR,
    SPIGOT_AIR_MATE,
)
from dt_crankshaft_spec import (
    COLLAR_DIA,
    COLLAR_REAR,
    CROSS_HOLE_PROCESS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    DRIVE_PIN_CIRCLE_RADIUS,
    DRIVE_PIN_FLOOR,
    DRIVE_PIN_HOLE_DIA,
    DRIVE_PIN_HOLE_PROCESS,
    DRIVE_PIN_KNOCKOUT_DIA,
    FIDUCIAL_MODEL_DIA,
    HOLE_CALLOUT_PLACES,
    JOURNAL_DIA,
    JOURNAL_END,
    JOURNAL_START,
    NECK_DIA_PLACES,
    NECK_DIA_TOL,
    PIN_HOLE_HEIGHT,
    PIN_HOLE_SPEC,
    PINION_SEAT_DIA,
    REFERENCE_DIMENSIONS,
    RELIEF_END,
    RELIEF_START,
    SEAT_COLLAR,
    SEAT_STEP,
    SHAFT_DIA,
    SHAFT_DOME_HEIGHT,
    SHAFT_LENGTH,
    SPHERICAL_DIMENSIONS,
    SPIGOT_END,
    SURFACE_FINISHES,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["dt_crankshaft"]
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
_PIN_HOLE_DIA = blind_cut_dia_mm(PIN_HOLE_SPEC)

# Both orthographic views print at the sheet scale, so neither needs a caption.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# The profile sits 18 mm right of the sheet's middle so the gap between the
# end view and the dome tip holds the drive-pin locations' text left of the
# dome's extension lines; the isometric moves 8 mm right to keep clear of it.
SIDE_CENTER = (0.228, 0.180)
# Third-angle left view of the dome end, on the profile's axis.
END_CENTER = (0.036, SIDE_CENTER[1])
ISO_CENTER = (0.398, SIDE_CENTER[1])
ISO_SCALE = (1, 1)
# The *Right view rotated -90 degrees: model +Y runs to paper-right.
SIDE_VIEW_ANGLE = -math.pi / 2.0

# The side view is centred on the model bbox, dome tip (-DomeHeight) through
# the far end (+ShaftLength).
_BBOX_MID_Y = (SHAFT_LENGTH - SHAFT_DOME_HEIGHT) / 2.0


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the horizontal side view."""
    return SIDE_CENTER[0] + (model_y_mm - _BBOX_MID_Y) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the shaft axis (model +Z up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


DOME_TIP_X = _sheet_x(-SHAFT_DOME_HEIGHT)
DOME_ROOT_X = _sheet_x(0.0)
PIN_X = _sheet_x(PIN_HOLE_HEIGHT)
JOURNAL_START_X = _sheet_x(JOURNAL_START)
JOURNAL_END_X = _sheet_x(JOURNAL_END)
RELIEF_START_X = _sheet_x(RELIEF_START)
RELIEF_END_X = _sheet_x(RELIEF_END)
SEAT_STEP_X = _sheet_x(SEAT_STEP)
COLLAR_SEAT_X = _sheet_x(SEAT_COLLAR)
SPIGOT_END_X = _sheet_x(SPIGOT_END)
COLLAR_REAR_X = _sheet_x(COLLAR_REAR)
FAR_END_X = _sheet_x(SHAFT_LENGTH)
JOURNAL_FLANK_Y = _sheet_y(JOURNAL_DIA / 2.0)

# Baseline rows below the profile, all from the FAR END and stacked
# shortest-first so no extension line crosses a dimension line.  The text
# sits ~3 mm above its requested point and the dimension line ~5 mm below
# it; the two seat-collar stations make ten rows between the Ø20.6 collar's
# underside and the title block, so the pitch closes from 12 to 9.5 mm.  The
# 2.0 dome height stands over the first row at the far left, where no
# baseline reaches; the last row clears the title block.
_ROW_PITCH = 0.0095
_ROW_Y = tuple(round(0.162 - k * _ROW_PITCH, 4) for k in range(10))
# The seven diameters are authored in end-profile sketches; the end view
# receives them first and they are then dragged onto the profile (drawing-guidelines.md rule 11 (turned parts read like the lathe):
# diameters on the side view).  Their temporary end-view spots are clear of
# everything else on the sheet.
END_DIAMETERS = {
    "ShaftDiaDim": (0.036, 0.215),
    "JournalDiaDim": (0.036, 0.228),
    "ReliefDiaDim": (0.036, 0.241),
    "PinionSeatDiaDim": (0.036, 0.254),
    "SpigotDiaDim": (0.024, 0.241),
    "CollarDiaDim": (0.024, 0.254),
    "NeckDiaDim": (0.024, 0.228),
}
# The drive-pin holes' locations stay in the end view, the one view that
# shows them as true (visible) circles: each hole from the shaft axis, its
# dimension line just right of the view, text beyond the view's top (+Z hole)
# and bottom (-Z hole), running right into the gap before the dome's
# extension lines.  That gap (dimension line to dome tip) is ~30 mm, just the
# 7.000 value's width, so each one's mate callout is set in rows no wider
# than it (machinist review of 902433a8d: the upper one named no mate).  The
# upper block runs down from 6 mm under the (SR6.7) to 5 mm over the upper
# hole's extension line; the lower text sits 7 mm under the 2.0 dome
# height's text.
END_PIN_KEEP = {
    "DrivePinOffset1": (0.058, 0.210),
    "DrivePinOffset2": (0.058, 0.145),
}
END_KEEP = {**END_DIAMETERS, **END_PIN_KEEP}
SIDE_KEEP = {
    # Below the dome, 6 mm over the lower 7.000's text (machinist review of
    # 5a219a81904f: on the first row the 2.0 read as stacked on the 7.000).
    "DomeHeight": (DOME_TIP_X - 0.016, 0.168),
    "PinionSeatStation": ((SEAT_STEP_X + FAR_END_X) / 2.0, _ROW_Y[0]),
    "JournalInboardStation": ((JOURNAL_END_X + FAR_END_X) / 2.0, _ROW_Y[1]),
    "ReliefInboardStation": ((RELIEF_END_X + FAR_END_X) / 2.0, _ROW_Y[2]),
    "ReliefOutboardStation": ((RELIEF_START_X + FAR_END_X) / 2.0, _ROW_Y[3]),
    "JournalOutboardStation": ((JOURNAL_START_X + FAR_END_X) / 2.0 - 0.020, _ROW_Y[4]),
    "CollarRearStation": ((COLLAR_REAR_X + FAR_END_X) / 2.0, _ROW_Y[5]),
    "CollarSeatStation": ((COLLAR_SEAT_X + FAR_END_X) / 2.0 - 0.020, _ROW_Y[6]),
    "PinHoleStation": ((PIN_X + FAR_END_X) / 2.0, _ROW_Y[7]),
    # The shaft length's native unilateral block sits right of the reference
    # overall on the next row down, not over it; its stack suffix widens it
    # left to x ~0.213, so the overall's text stands left of that (layout
    # audit of 902433a8d: 1.3 mm text clearance).
    "Depth": ((DOME_ROOT_X + FAR_END_X) / 2.0 + 0.035, _ROW_Y[8]),
    "OverallLength": ((DOME_TIP_X + FAR_END_X) / 2.0 - 0.030, _ROW_Y[9]),
    # Above the dome, between the +Z drive-pin location's text and the
    # Ø9.525 dimension: the radial leader runs down, right of the one and
    # left of the other, to the dome's sphere.
    "DomeSphereRadius": (DOME_TIP_X - 0.005, 0.230),
    # The seat spigot's length from the seat face: text below-left of the
    # spigot, between the cross-hole's and the collar seat's extension lines,
    # above every row that spans it.
    "SpigotLength": ((PIN_X + COLLAR_SEAT_X) / 2.0, 0.148),
}
# A dragged diameter prints its dimension line at the requested X with the
# text running to its RIGHT (run 20260923T030252135Z-49e46990).  Its
# extension lines run parallel to the axis from the profile SKETCH that owns
# it, so each must sit on the section that sketch starts: the Ø9.525 circle
# lies at the dome root, and placed on the far-end seat its extension lines
# drew solid through the journal (run 20260923T031747843Z-94724e44).
# The Ø9.525 sits on the core LEFT of the cross-hole, so its lines stop short
# of the hole the callout's leader leaves (leader-crosses-line, af13c8ff8);
# the Ø9.0 seat's sits on the seat, left of the pinion pin hole.
# Each banded diameter is a four-row block (fit / upper limit / value /
# mate) whose left edge stands on its dimension line and whose landing line
# runs under its widest row; each request is the block's centre.  The
# cross-hole callout's leader climbs from the hole at ~1.45 (dy/dx) to its
# block (HOLE_CALLOUT_XY): left of it the Ø9.525's block lands 3.5 mm clear
# of it, right of it the Ø17.50's block tops out 6 mm under it (machinist
# review of b5c02e5d6: the leader crossed the Ø9.525's landing line).  The
# Ø20.6 (one place, no band) drops under the Ø17.50's landing line, 1 mm
# higher than its first spot so the collar-rear finish symbol under its
# shelf's end can rise with it (COLLAR_REAR_FINISH), and the
# Ø11.388 stands 4 mm right of the Ø17.50's block (layout audit of
# 902433a8d: 2.3 mm read as one callout), its landing line 2 mm over the
# outboard journal's finish symbol and its fit row 7 mm under the cross-hole
# callout's landing line; the relief's Ø10.4 stands right of it.
# The inch sliding band (0/-0.02032) widened the Ø9.525's block 6 mm to the
# right, onto the leader, so the block stands 4 mm higher, where the leader
# has climbed 2.8 mm past its landing line's end (machinist review, #290
# batch 0).
# The existing loose Ø9.5 remains on the inboard neck, over the Ø9.000's
# block. A separate measured diameter identifies the collar-side neck.
# The Ø9.000's line stays 2 mm past its step, clear of the retention-pin note.
DIAMETER_POSITIONS = {
    "ShaftDiaDim": (PIN_X - 0.016, 0.2235),
    # Right of the collar-side neck's .375 ±.010 (its native advance ends
    # left of this leader), left of the journal finish symbol's V.
    "JournalDiaDim": (RELIEF_START_X - 0.0035, 0.224),
    "ReliefDiaDim": (RELIEF_START_X + 0.045, 0.212),
    "PinionSeatDiaDim": (SEAT_STEP_X + 0.002, 0.2125),
    "SpigotDiaDim": (COLLAR_SEAT_X + 0.0075, 0.2215),
    "CollarDiaDim": (SPIGOT_END_X + 0.002, 0.2075),
    "NeckDiaDim": (JOURNAL_END_X + 0.0006, 0.230),
}
# Keep the complete native arrowheads inside the real short land, with text
# above the journal and below the collar-rear finish leader. Both annotations
# must prove actual ink clearance; nominal positions are not a layout waiver.
OUTBOARD_NECK_DIAMETER_XY = ((COLLAR_REAR_X + JOURNAL_START_X) / 2.0, 0.1948)
OUTBOARD_NECK_ARROW_WINDOW = (
    COLLAR_REAR_X, _sheet_y(-SHAFT_DIA / 2.0),
    JOURNAL_START_X, _sheet_y(SHAFT_DIA / 2.0),
)
# Sheet-space display readback tolerance, not a model-size tolerance.
NECK_ARROW_LANDING_TOLERANCE_M = 1e-5  # 0.01 mm against a ~2.34 mm axial land
NECK_ARROW_DIRECTION_X_SLACK = 1e-6  # normalized-X roundoff for vertical arrows
NECK_GEOMETRY_TOLERANCE_M = 1e-8  # native endpoint/face-box roundoff, not a size band
NECK_PDF_GLYPH_BAY_TOP_M = 0.1972
# The shank's band is the hub's fit; each bare neck has its own loose
# diameter. The 2X Ø11.388 still names both bearing lands across the relief.
CALLOUTS_ABOVE = {
    "ShaftDiaDim": SLIDING_FIT,
    "JournalDiaDim": JOURNAL_FIT,
    "PinionSeatDiaDim": SLIDING_FIT,
    "SpigotDiaDim": SPIGOT_AIR,
    "NeckDiaDim": "",
}
# Each drive-pin location names the mate its +/-0.025 serves
# (crankshaft_notes), in the clear field under its text; the spigot's length
# names the chain it keeps clear, between the cross-hole's and the collar
# seat's extension lines.  Each banded diameter names its mate under its
# value.
CALLOUTS_BELOW = {
    "OverallLength": "OVERALL",
    "DrivePinOffset1": DRIVE_PIN_LOCATION_CALLOUT,
    "DrivePinOffset2": DRIVE_PIN_LOCATION_CALLOUT,
    "SpigotLength": CHAIN_AIR_MATE,
    "ShaftDiaDim": SHANK_MATE,
    "JournalDiaDim": JOURNAL_MATE,
    "PinionSeatDiaDim": PINION_SEAT_MATE,
    "SpigotDiaDim": SPIGOT_AIR_MATE,
}
# The banded far-end stations name their stack on their own row: a callout
# below would lift the value into the row above.
SUFFIXES = {
    "CollarRearStation": COLLAR_REAR_MATE,
    "CollarSeatStation": COLLAR_SEAT_MATE,
    "Depth": SHAFT_LENGTH_MATE,
}
# Both running lands carry separate part-owned finish symbols. The outboard
# symbol sits right of the Ø11.388 dimension line, its leader landing on the
# land just short of the relief shoulder; the inboard symbol retains its
# clear spot above the relief.  The collar's rear (boss) face takes its
# own symbol on that face's edge-on line ABOVE the axis, the symbol in the
# pocket over the outboard land under the collar's Ø20.6 text: under the axis
# every way to that face crosses a station's extension line.
JOURNAL_FINISHES = {
    "outboard_journal": (
        (RELIEF_START_X - 0.0009, JOURNAL_FLANK_Y),
        # The V's tip over the land's right end: its left arm (2.1 mm) stays
        # right of the journal diameter's leader.
        (RELIEF_START_X - 0.0003, 0.203),
    ),
    "inboard_journal": (
        (RELIEF_END_X + 0.015, JOURNAL_FLANK_Y),
        (RELIEF_END_X + 0.012, 0.200),
    ),
}
# The landing on the rear (thrust) face's edge-on line, 0.8 mm (1.6 mm on the
# sheet) inside the collar's silhouette, so the head ends on that face and not
# on the corner it shares with the Ø20.6 OD (machinist review of e04fd60ab:
# a corner landing read as either surface).  The leader attaches to the
# planar face itself (_collar_rear_face): selected by its rim, SolidWorks
# lands a point on an edge-on circle at its projected extreme, the corner
# (run 20261001T051043622Z: requested y 0.1986, landed 0.2006).  The symbol
# sits 1 mm higher than when it landed on the corner, with the Ø20.6 over it,
# so the near-level leader keeps the head 2 mm clear of the Ø9.5's printed
# Ø; any lower a landing and the head closes on that Ø.
COLLAR_REAR_FINISH = (
    (COLLAR_REAR_X, _sheet_y(COLLAR_DIA / 2.0 - 0.8)),
    (COLLAR_REAR_X + 0.0069, 0.1983),
)
# The drive-pin holes' native REAM callout (size and depth from the cut, the
# depth's band appended by _band_hole_depth)
# with the press prose under it on two long rows (four rows in all): its
# leader picks the upper hole's rim and the text sits above the end view and
# the dome, left of the cross-hole callout, inside the top border.  The text
# centres on this anchor, and the press row runs ~110 mm wide, so its left end
# printed 3 mm past the inner border (run 15 and 06a20f94c): the callout is
# moved from its read-back box to clear the zone frame, and the placement is
# asserted (place_callout_clear).
DRIVE_PIN_CALLOUT_XY = (0.066, 0.250)
# Text centred up-right of the cross-hole: the callout's leader leaves the
# text's left end and runs down-left at ~55 deg to the hole, a clean
# crossing of the 122.7 station's extension line rather than a near
# parallel one (run 20260923T030252135Z-49e46990).  Its three prose rows and
# drill row centre on y 0.251; its left end (~36 mm left of the centre) sets
# the leader's slope that the diameter blocks under it are laid out around
# (DIAMETER_POSITIONS).
HOLE_CALLOUT_XY = (PIN_X + 0.077, 0.251)
# The Hole Wizard drills' (#9 cross-hole, #54 knockouts) native size prints
# the title block's .XXX on the inch sheet.
WIZARD_CALLOUT_PRECISION = {"hw-diam": 3}
# The knockouts' native callout (drill above, size, purpose below; ~44 mm
# wide) centres under the end view, below the lower 7.000 row's PINS SLIP
# block (bottom ~0.131) and left of the dome's extension line (x 0.0897).
# Its leader leaves the text's left end up-left to the lower hole's floor.
KNOCKOUT_CALLOUT_XY = (0.064, 0.115)
# The punch-mark note sits, anchored upper-left, in the narrow field at the
# end view's lower-left, left of the knockout leader: its leader rises
# from the text's right end to the mark at about 225 deg on the dome, 2 mm
# clear of the lower pin hole.
FIDUCIAL_NOTE_XY = (0.0145, 0.152)
# The 16T retention-pin hole is match-drilled through the seated pinion's
# boss at assembly, so the sheet prints the pinion sheet's own matched-fit
# note with the mates swapped (crank_pinion_spec.CRANKSHAFT_PIN_HOLE_PROCESS,
# also the part property checked below): the operation, where it runs, the
# pin it is reamed to, the fit's acceptance and flush -- no size, no station.
# A bare transfer note gave the shaft's machinist none of these (machinist
# review of 4d4e038e3).  The note is attached to the hole's own visible rim edge: a radial hole in a
# round shaft has a saddle rim, not a circle, so a native Hole Wizard
# callout cannot bind to it (run1-61671871a).  Its TEXT sits, anchored
# upper-left, in the free field above the far-end seat, right of the cross-hole
# callout's text (which spans ~30 mm right of its centre) and left of the
# isometric; it is placed from its own measured box.
# Its leader must end on the hole, which the side view shows straddling the
# axis -- below the field's floor -- so the leader is held to the hole's
# window instead (run1b-e7fd1a2ec: the leader tip, not the text, read 0.3 mm
# under the floor).
PINION_PIN_X = _sheet_x(PINION_PIN_STATION_Y)
# High in its field (top row ~4.5 mm under the border), so the right neck's
# Ø9.5 and the Ø9.000's block stand under it, and its leader to the hole
# passes right of the Ø9.000's block.
PINION_PIN_NOTE_XY = (0.273, 0.264)
PINION_PIN_NOTE_FIELD = (
    HOLE_CALLOUT_XY[0] + 0.032,
    SIDE_CENTER[1],
    ISO_CENTER[0] - 0.012,
    0.2657,  # 1 mm inside the ASME B inner border
)
# Every point of the rim lies within the hole's half-width (plus 0.5 mm of
# pick slack) of its station and inside the shaft's silhouette.
PINION_PIN_HOLE_WINDOW = (
    PINION_PIN_X - (PINION_PIN_DIA / 2.0 + 0.5) * _S / 1000.0,
    _sheet_y(-PINION_SEAT_DIA / 2.0),
    PINION_PIN_X + (PINION_PIN_DIA / 2.0 + 0.5) * _S / 1000.0,
    _sheet_y(PINION_SEAT_DIA / 2.0),
)
NOTE_FIELD_MARGIN = 0.001
NOTES_XY = (0.016, 0.062)
# The plain Ø9.000 end is the right-hand edge of FRONT (the horizontal
# ``side`` view), not the top end of the pictorial. Pick its lower half so
# the centre permission's leader stays away from MATCH DRILL above the axis.
FAR_END_FRONT_RIM_PICK = (
    FAR_END_X,
    _sheet_y(-PINION_SEAT_DIA / 4.0),
)
FAR_END_FRONT_RIM_WINDOW = (
    FAR_END_FRONT_RIM_PICK[0] - 0.0005,
    FAR_END_FRONT_RIM_PICK[1] - 0.0005,
    FAR_END_FRONT_RIM_PICK[0] + 0.0005,
    FAR_END_FRONT_RIM_PICK[1] + 0.0005,
)
# The unchanged four-row note sits below the isometric caption, above the
# title block. Its leader rises in the corridor RIGHT of the FRONT station
# witnesses and LEFT of the pictorial/caption, directly to the plain end.
CENTRES_NOTE_XY = (0.372, 0.093)
NOTE_TEXT_GAP = 0.0035  # one 3.5 mm note-text height
ISO_NOTE_XY = (0.376, 0.108)


def _set_callout_text(display: Any, which: int, text: str, label: str) -> None:
    """Put prose ABOVE (``which`` 3) or UNDER (4) a native hole callout.

    The drill size reads first, in the order the work is done; the fit and
    mate prose follows in the callout-below compartment (the Ø9.550 bore
    callout's order).  ``SetText`` reports nothing, so it is read back.
    """
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(which, text)  # swDimensionTextCalloutAbove/Below
    applied = str(display.GetText(which) or "")
    if applied.replace("\r", "") != text:
        raise RuntimeError(f"{label}: callout text {which} did not persist: {applied!r}")


def _set_dimension_suffixes(
    adapter: Any, annotations: list[Any], suffixes: dict[str, str]
) -> None:
    """Append each named dimension's mate to its value on the same line.

    ``SetText`` reports nothing, so each suffix is read back.
    """
    remaining = dict(suffixes)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(2, text)  # swDimensionTextSuffix
        applied = str(display.GetText(2) or "")
        if applied.replace("\r", "") != text:
            raise RuntimeError(f"{name}: suffix did not persist: {applied!r}")
    if remaining:
        raise RuntimeError(f"dimension suffixes not applied: {sorted(remaining)}")


# Format-definition parts of a display dimension and the writable part each
# one is set through (swDimensionTextParts_e): prefix, suffix, callout above,
# callout below.
_DEFINITION_TO_WRITABLE = {5: 1, 6: 2, 7: 3, 8: 4}


def _depth_banded_definition(definitions: dict[int, str], band: str) -> tuple[int, str]:
    """The one format part ending on the callout's depth, with ``band`` after it.

    A native hole callout splits its text across the prefix, suffix and
    callout compartments; on the farm the drive-pin callout's prefix read
    ``REAM <MOD-DIAM>`` and its depth sat in another part (run
    20261001T011714683Z).  Exactly one part may carry ``<HOLE-DEPTH>``, once,
    followed by the depth alone; anything else (no depth, two, text after it,
    a band already there) fails loud.
    """
    if set(definitions) != set(_DEFINITION_TO_WRITABLE):
        raise RuntimeError(f"unexpected hole callout parts: {definitions!r}")
    holders = [part for part, text in definitions.items() if "<HOLE-DEPTH>" in text]
    joined = "\n".join(definitions.values())
    if len(holders) != 1 or band in joined:
        raise RuntimeError(f"hole callout has no single closing depth: {definitions!r}")
    part = holders[0]
    definition = definitions[part]
    head, _marker, tail = definition.rpartition("<HOLE-DEPTH>")
    if "<HOLE-DEPTH>" in head or len(tail.split()) != 1:
        raise RuntimeError(f"hole callout has no single closing depth: {definitions!r}")
    return part, f"{definition.rstrip()} {band}"


def _drop_coaxial_step(display: Any, step_dia: float, label: str) -> None:
    """Clear the coaxial hole's step SolidWorks folds into a native callout.

    Each pin hole and its knockout meet end to end, so a callout on either
    reads the pair as one stepped hole: on the farm the drive-pin callout
    carried ``<MOD-DIAM>1.40<HOLE-DEPTH>12.63`` in its callout-above part (run
    20261018T110810560Z-720787ec).  Each hole has its own callout naming its
    process, so the other's step is cleared.  Only a part holding nothing but
    that step is cleared; the step anywhere else fails loud.  The stepped
    reading also put a bare counterbore symbol (``<HOLE-SPOT>``) before the
    size (machinist review of b5c02e5d6), so it goes with the step.  Read
    back.
    """
    display = _early_bound(display, "IDisplayDimension")
    definitions = {
        part: str(display.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE
    }
    holders = [
        part for part, text in definitions.items() if _has_coaxial_step(text, step_dia)
    ]
    for part in holders:
        if not _has_coaxial_step(definitions[part], step_dia, leading=True):
            raise RuntimeError(f"{label}: coaxial step mixed into part {part}: {definitions!r}")
        display.SetText(_DEFINITION_TO_WRITABLE[part], "")
        if str(display.GetText(part) or ""):
            raise RuntimeError(f"{label}: coaxial step in part {part} did not clear")
    if not holders:
        return
    prefix = definitions[5]
    if "<HOLE-SPOT>" in prefix:
        bare = prefix.replace("<HOLE-SPOT>", "")
        display.SetText(_DEFINITION_TO_WRITABLE[5], bare)
        applied = str(display.GetText(5) or "")
        if applied.replace("\r", "") != bare:
            raise RuntimeError(f"{label}: counterbore symbol did not clear: {applied!r}")
    _telemetry.info(f"{label}: cleared coaxial step from parts {holders}: {definitions!r}")


# swLengthUnit_e.swINCHES: the unit ``set_units_inch`` writes.
_SW_LENGTH_INCHES = 3
# Every step SolidWorks folds into a callout prints as ``<MOD-DIAM>`` and a
# decimal at the sheet's places.
_STEP_SIZE = re.compile(r"<MOD-DIAM>(\d*\.\d+)")


def _has_coaxial_step(text: str, step_dia: float, *, leading: bool = False) -> bool:
    """Whether ``text`` prints ``step_dia`` (mm) as an inch ``<MOD-DIAM>``
    size -- anywhere, or (``leading``) as its first characters."""
    matches = [_STEP_SIZE.match(text)] if leading else _STEP_SIZE.finditer(text)
    for match in matches:
        if match is None:
            continue
        printed = match.group(1)
        if printed == inch_text(step_dia, len(printed.partition(".")[2])):
            return True
    return False


def _require_inch_sheet(draw: Any, label: str) -> None:
    """Refuse unless the drawing's linear unit is the inch.

    The depth band is typed text in inches: SolidWorks re-renders the
    callout's native depth in the sheet's units but never the text after it,
    so the band is only true on an inch sheet.  The callout has no native route for it:
    ``GetHoleCalloutVariables`` raised DISP_E_BADVARTYPE on this cut-extrude
    callout on the farm (run 20261003T001156794Z); every repo caller it works
    for is a Hole Wizard feature.  Reads the document preference
    ``set_units_inch`` writes (``IModelDoc2::GetUserPreferenceIntegerValue``).
    """
    doc = _early_bound(draw, "IModelDoc2")
    unit = doc.GetUserPreferenceIntegerValue(_SW_PREF_UNITS_LINEAR)
    if type(unit) is not int or unit != _SW_LENGTH_INCHES:
        raise RuntimeError(
            f"{label}: the typed depth band is inches, but the sheet's linear unit"
            f" is {unit!r} (swLengthUnit_e; swINCHES = {_SW_LENGTH_INCHES})"
        )


def _band_hole_depth(display: Any, band: str, draw: Any, label: str) -> None:
    """Print the part's depth band after the native callout's depth.

    The cut's depth carries the band in the part, but the callout prints the
    depth bare; the band joins the format text of the part holding the depth,
    where the native size and depth stay associative.  Read back like the
    prose.  The callout-below compartment is rewritten by the matched-fit
    prose afterwards, so a depth there is refused rather than lost.  The band
    is inch text, so the sheet must be inch (``_require_inch_sheet``).
    """
    _require_inch_sheet(draw, label)
    display = _early_bound(display, "IDisplayDimension")
    definitions = {
        part: str(display.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE
    }
    part, updated = _depth_banded_definition(definitions, band)
    if part == 8:
        raise RuntimeError(
            f"{label}: depth is in the callout-below text: {definitions!r}"
        )
    display.SetText(_DEFINITION_TO_WRITABLE[part], updated)
    applied = str(display.GetText(part) or "")
    if applied.replace("\r", "") != updated.replace("\r", ""):
        raise RuntimeError(f"{label}: depth band did not persist: {applied!r}")
    _telemetry.info(f"{label}: depth band joined format part {part}: {updated!r}")


Box = tuple[float, float, float, float]


def _shift_into_field(text: Box, field: Box, margin: float) -> tuple[float, float]:
    """Return the (dx, dy) that brings a measured text box ``margin`` inside ``field``.

    Boxes are (x0, y0, x1, y1) in sheet metres.  A box already inside moves
    (0, 0); one too big for the field fails loud, naming the overflow.
    """
    x0, y0, x1, y1 = text
    fx0, fy0, fx1, fy1 = field
    spare_x = (fx1 - fx0 - 2.0 * margin) - (x1 - x0)
    spare_y = (fy1 - fy0 - 2.0 * margin) - (y1 - y0)
    if spare_x < 0.0 or spare_y < 0.0:
        raise RuntimeError(
            f"text box {text} cannot sit {margin} inside field {field}: "
            f"over by {max(-spare_x, 0.0):.4f} wide, {max(-spare_y, 0.0):.4f} tall"
        )
    dx = max(0.0, fx0 + margin - x0) - max(0.0, x1 - (fx1 - margin))
    dy = max(0.0, fy0 + margin - y0) - max(0.0, y1 - (fy1 - margin))
    return dx, dy


def _leader_tip(points: Sequence[float], target: tuple[float, float]) -> tuple[float, float]:
    """Return the leader point (flat x, y, z triples) nearest ``target``."""
    triples = [
        (float(points[i]), float(points[i + 1])) for i in range(0, len(points) - 2, 3)
    ]
    if not triples:
        raise RuntimeError("note reports no leader points")
    return min(triples, key=lambda p: math.hypot(p[0] - target[0], p[1] - target[1]))


def _inside(point: tuple[float, float], box: Box) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _note_text_box(drawing_model: Any, annotation: Any, note: Any, label: str) -> Box:
    """Measure a leadered note's TEXT box: GetExtent includes the leader.

    The leader is hidden for the read and restored (straight, as
    ``add_attached_note`` makes it), then re-verified to still attach once.
    """
    if annotation.SetLeader3(0, 0, True, False, False, False) != 0:  # swNO_LEADER
        raise RuntimeError(f"{label}: could not hide the leader to measure the text")
    drawing_model.GraphicsRedraw2()
    extent = tuple(float(v) for v in (note.GetExtent() or ()))
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:  # swSTRAIGHT
        raise RuntimeError(f"{label}: could not restore the leader")
    drawing_model.GraphicsRedraw2()
    if int(annotation.GetLeaderCount()) != 1 or int(annotation.GetAttachedEntityCount3()) != 1:
        raise RuntimeError(f"{label}: note lost its one attached leader while measured")
    if len(extent) < 5:
        raise RuntimeError(f"{label}: note text extent unreadable: {extent}")
    return extent[0], extent[1], extent[3], extent[4]


def _place_note_text_in_field(
    drawing_model: Any, note: Any, field: Box, *, hole: Box, label: str
) -> Box:
    """Move a leadered note's text inside ``field`` from its measured box.

    Its leader must still end inside ``hole``.  Everything read is logged.
    Returns the placed text box.
    """
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text = _note_text_box(drawing_model, annotation, note, label)
    dx, dy = _shift_into_field(text, field, NOTE_FIELD_MARGIN)
    if dx or dy:
        x, y = (float(v) for v in tuple(annotation.GetPosition())[:2])
        if not annotation.SetPosition2(x + dx, y + dy, 0.0):
            raise RuntimeError(f"{label}: failed to move the note by ({dx}, {dy})")
        text = _note_text_box(drawing_model, annotation, note, label)
    leader = tuple(float(v) for v in (note.GetLeaderInfo() or ()))
    centre = ((hole[0] + hole[2]) / 2.0, (hole[1] + hole[3]) / 2.0)
    tip = _leader_tip(leader, centre)
    _telemetry.info(
        f"{label}: text box {text} moved ({dx:.4f}, {dy:.4f}); leader {leader}; tip {tip}"
    )
    if _shift_into_field(text, field, 0.0) != (0.0, 0.0):
        raise RuntimeError(f"{label}: text box {text} left its field {field}")
    if not _inside(tip, hole):
        raise RuntimeError(f"{label}: leader tip {tip} is off the hole window {hole}")
    return text


def _visible_cross_hole_edge(
    adapter: Any,
    view: Any,
    diameter_mm: float,
    *,
    view_label: str = "side",
    accept: Callable[[Any], bool] | None = None,
) -> Any:
    """Return a visible rim edge adjacent to a modeled hole cylinder.

    ``accept`` narrows the candidates further (an ``IEdge`` predicate) when a
    view shows more than one rim of that size.
    """
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            adjacent_faces = edge.GetTwoAdjacentFaces2() or ()
            for face in adjacent_faces:
                if face is None:
                    continue
                face = _early_bound(face, "IFace2")
                surface = _early_bound(face.GetSurface(), "ISurface")
                if not surface.IsCylinder():
                    continue
                parameters = surface.CylinderParams
                if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                    continue
                if accept is None or accept(edge):
                    candidates.append(edge)
                break
    if not candidates:
        raise RuntimeError(
            f"crankshaft {view_label} view has no visible edge adjacent to a "
            f"hole cylindrical face at radius {expected_radius_m:g} m"
        )
    return candidates[0]


def _is_upper_seat_rim(edge: Any) -> bool:
    """Whether an edge is the +Z drive-pin hole's rim on the spigot's seat face.

    The *Bottom end view prints model +Z up, so the +Z hole is the upper one,
    nearest its callout above the view; its seat-face rim, not its floor.
    """
    curve = _early_bound(edge.GetCurve(), "ICurve")
    if not curve.IsCircle():
        return False
    cx, cy, cz = (float(v) * 1000.0 for v in tuple(curve.CircleParams)[:3])
    return (
        abs(cx) < 1e-3
        and abs(cy - SEAT_COLLAR) < 1e-3
        and abs(cz - DRIVE_PIN_CIRCLE_RADIUS) < 1e-3
    )


def _is_lower_knockout_floor(edge: Any) -> bool:
    """Whether an edge is the -Z knockout's circle on its drive-pin hole floor.

    The lower hole is the knockout callout's nearest; the floor circle, not
    the knockout's exit on the collar's rear face, is what the end view sees.
    """
    curve = _early_bound(edge.GetCurve(), "ICurve")
    if not curve.IsCircle():
        return False
    cx, cy, cz = (float(v) * 1000.0 for v in tuple(curve.CircleParams)[:3])
    return (
        abs(cx) < 1e-3
        and abs(cy - DRIVE_PIN_FLOOR) < 1e-3
        and abs(cz + DRIVE_PIN_CIRCLE_RADIUS) < 1e-3
    )


def _collar_rear_rim(adapter: Any, view: Any) -> Any:
    """Return the Ø20.6 collar's rear-face rim, seen edge-on in the side view.

    A sheet pick on that vertical line found no edge natively (run
    20261001T035353825Z) though the same pick passed on f7c9771b3.  The
    model circle centred on the shaft axis at the rear-face station is
    unambiguous; the collar's other Ø20.6 rim sits at its seat face,
    SEAT_COLLAR.
    """
    radius_mm = COLLAR_DIA / 2.0
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(curve.CircleParams)
            cx, cy, cz = (float(v) * 1000.0 for v in params[:3])
            if (
                abs(cx) < 1e-3
                and abs(cz) < 1e-3
                and abs(cy - COLLAR_REAR) < 1e-3
                and abs(float(params[6]) * 1000.0 - radius_mm) < 1e-3
            ):
                return edge
    raise RuntimeError(
        f"crankshaft side view has no visible Ø{COLLAR_DIA} rim at the collar "
        f"rear station {COLLAR_REAR}"
    )


def _collar_rear_face(rim: Any) -> Any:
    """Return the controlled planar rear (thrust) face that ``rim`` bounds.

    The rim joins that face and the Ø20.6 OD; only the face matches the
    part-owned ``collar_rear_face`` finish control.  None or both fail.
    """
    control = surface_finish_by_key(SURFACE_FINISHES, "collar_rear_face")
    faces = tuple(
        face for face in (_early_bound(rim, "IEdge").GetTwoAdjacentFaces2() or ())
        if face is not None
    )
    geometries = [face_geometry(face) for face in faces]
    matches = [
        face for face, geometry in zip(faces, geometries)
        if geometry is not None and control.face.matches(geometry)
    ]
    if len(faces) != 2 or len(matches) != 1:
        raise RuntimeError(
            f"crankshaft collar rear rim: expected one {control.face!r} of its two "
            f"faces, matched {len(matches)} of {len(faces)}"
        )
    return matches[0]


def _far_end_rim(adapter: Any, view: Any) -> Any:
    """Return the plain far end's Ø9.000 rim, the end a lathe centre may enter.

    The model circle centred on the shaft axis at SHAFT_LENGTH with the
    seat's radius is that end face's only boundary; the seat step's Ø9.000
    circle sits at SEAT_STEP.  None or several fail rather than land the
    note's leader on another edge.
    """
    radius_mm = PINION_SEAT_DIA / 2.0
    matches: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(curve.CircleParams)
            cx, cy, cz = (float(v) * 1000.0 for v in params[:3])
            if (
                abs(cx) < 1e-3
                and abs(cz) < 1e-3
                and abs(cy - SHAFT_LENGTH) < 1e-3
                and abs(float(params[6]) * 1000.0 - radius_mm) < 1e-3
            ):
                matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(
            f"crankshaft FRONT shows {len(matches)} visible Ø{PINION_SEAT_DIA} "
            f"rims at the plain end station {SHAFT_LENGTH}; expected exactly one"
        )
    return matches[0]


def _neck_numbers(raw: Any, count: int, *, label: str) -> tuple[float, ...]:
    """Require complete finite native numeric evidence, without coercing nulls/bools."""
    if (
        type(raw) not in (tuple, list) or len(raw) != count
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in raw)
    ):
        raise RuntimeError(f"{label}: malformed native geometry {raw!r}")
    return tuple(float(value) for value in raw)


def _is_outboard_neck_cylinder(face: Any, *, label: str) -> bool:
    """Identify the exact short core land, not another equal-radius shaft face."""
    face = _early_bound(face, "IFace2")
    raw = face.GetSurface()
    if raw is None:
        raise RuntimeError(f"{label}: face has no native surface")
    surface = _early_bound(raw, "ISurface")
    cylinder = surface.IsCylinder()
    if type(cylinder) is not bool:
        raise RuntimeError(f"{label}: IsCylinder did not return a native BOOL")
    if not cylinder:
        return False
    ox, _oy, oz, ax, ay, az, radius = _neck_numbers(
        surface.CylinderParams, 7, label=f"{label} cylinder"
    )
    box = _neck_numbers(face.GetBox(), 6, label=f"{label} face box")
    expected_radius = SHAFT_DIA / 2000.0
    expected_box = (
        -expected_radius, COLLAR_REAR / 1000.0, -expected_radius,
        expected_radius, JOURNAL_START / 1000.0, expected_radius,
    )
    # GetBox is approximate: it is a bounded source-face discriminator, never
    # the measured diameter. Native silhouette endpoints and SystemValue below
    # independently establish the stations, radial normals and full width.
    return (
        max(abs(ox), abs(oz), abs(radius - expected_radius)) <= NECK_GEOMETRY_TOLERANCE_M
        and max(abs(ax), abs(az), abs(abs(ay) - 1.0)) <= 1e-9
        and all(abs(actual - expected) <= NECK_GEOMETRY_TOLERANCE_M
                for actual, expected in zip(box, expected_box))
    )


def _outboard_neck_source_face(side: Any) -> Any:
    """Independently resolve the physical source cylinder from all part bodies."""
    source = _early_bound(side, "IView").ReferencedDocument
    if source is None or source == "":
        raise RuntimeError("collar-side neck: FRONT has no referenced source")
    model = _early_bound(source, "IModelDoc2")
    kind = model.GetType()
    if type(kind) is not int or kind != 1:  # swDocPART
        raise RuntimeError(f"collar-side neck: referenced source is not a part ({kind!r})")
    bodies = tuple(_early_bound(source, "IPartDoc").GetBodies2(-1, False) or ())
    if not bodies:
        raise RuntimeError("collar-side neck: referenced source has no bodies")
    matches = []
    for body in bodies:
        if body is None:
            raise RuntimeError("collar-side neck: null source body")
        faces = tuple(_early_bound(body, "IBody2").GetFaces() or ())
        if not faces or any(face is None for face in faces):
            raise RuntimeError("collar-side neck: source body has no complete face inventory")
        for face in faces:
            if _is_outboard_neck_cylinder(face, label="collar-side neck source"):
                matches.append(face)
    if len(matches) != 1:
        raise RuntimeError(f"collar-side neck: expected one physical short-neck cylinder, got {len(matches)}")
    return matches[0]


def _neck_silhouette_points(entity: Any, *, label: str) -> tuple[tuple[float, ...], ...]:
    """Read MathPoint endpoints as evidence, never as selectable IVertex objects."""
    silhouette = _early_bound(entity, "ISilhouetteEdge")
    points = []
    for raw in (silhouette.GetStartPoint(), silhouette.GetEndPoint()):
        if raw is None:
            raise RuntimeError(f"{label}: silhouette has no native endpoint")
        points.append(_neck_numbers(_early_bound(raw, "IMathPoint").ArrayData, 3, label=label))
    return tuple(sorted(points, key=lambda point: point[1]))


def _assert_neck_silhouette(
    adapter: Any, side: Any, entity: Any, source_face: Any, sign: int, *, label: str,
) -> tuple[Any, tuple[tuple[float, ...], ...]]:
    """Prove one exact generatrix and its required inverse source-face identity."""
    if entity is None:
        raise RuntimeError(f"{label}: null neck silhouette")
    silhouette = _early_bound(entity, "ISilhouetteEdge")
    owner = silhouette.GetView()
    if (
        owner is None or int(adapter.swApp.IsSame(owner, side)) != 1
        or int(adapter.swApp.IsSame(side, owner)) != 1
    ):
        raise RuntimeError(f"{label}: silhouette owner is not FRONT")
    points = _neck_silhouette_points(silhouette, label=label)
    radius = sign * SHAFT_DIA / 2000.0
    expected = ((0.0, COLLAR_REAR / 1000.0, radius), (0.0, JOURNAL_START / 1000.0, radius))
    if any(math.dist(actual, target) > NECK_GEOMETRY_TOLERANCE_M
           for actual, target in zip(points, expected)):
        raise RuntimeError(f"{label}: silhouette is not the exact opposite short-neck generatrix")
    face = silhouette.GetFace()
    if face is None or not _is_outboard_neck_cylinder(face, label=label):
        raise RuntimeError(f"{label}: silhouette has the wrong short-neck cylinder")
    source = _early_bound(side, "IView").ReferencedDocument
    if source is None or source == "":
        raise RuntimeError(f"{label}: silhouette has no referenced source")
    canonical = _early_bound(
        _early_bound(source, "IModelDoc2").Extension, "IModelDocExtension"
    ).GetCorrespondingEntity2(face)
    # Drawing-context face 49 is NOT directly IsSame to physical face 6.
    # Require the documented inverse map; geometry alone or a null forward
    # map cannot substitute for source-context identity in both directions.
    if canonical is None:
        raise RuntimeError(f"{label}: neck face has no source correspondence")
    if (
        int(adapter.swApp.IsSame(canonical, source_face)) != 1
        or int(adapter.swApp.IsSame(source_face, canonical)) != 1
    ):
        raise RuntimeError(f"{label}: neck face maps to a different source cylinder")
    return face, points


def _assert_neck_silhouette_pair(
    adapter: Any, side: Any, entities: tuple[Any, Any], source_face: Any, *, label: str,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Require both opposite flanks of one cylinder and the actual FRONT projection."""
    lower_face, lower = _assert_neck_silhouette(
        adapter, side, entities[0], source_face, -1, label=label,
    )
    upper_face, upper = _assert_neck_silhouette(
        adapter, side, entities[1], source_face, 1, label=label,
    )
    if (
        int(adapter.swApp.IsSame(lower_face, upper_face)) != 1
        or int(adapter.swApp.IsSame(upper_face, lower_face)) != 1
    ):
        raise RuntimeError(f"{label}: opposite silhouettes do not own the same native cylinder")
    station = COLLAR_REAR / 1000.0
    radius = SHAFT_DIA / 2000.0
    points = (*lower, *upper, (0.0, station, 0.0), (radius, station, 0.0))
    projected = model_points_in_view(adapter, side, points, label=label)
    if len(projected) != len(points):
        raise RuntimeError(f"{label}: incomplete native FRONT projection")
    sheet = [_neck_numbers(point, 2, label=label) for point in projected]
    expected = [
        (_sheet_x(point[1] * 1000.0), _sheet_y(point[2] * 1000.0)) for point in points
    ]
    if any(math.dist(actual, target) > NECK_GEOMETRY_TOLERANCE_M
           for actual, target in zip(sheet, expected)):
        raise RuntimeError(f"{label}: native FRONT axis/normal/separation projection changed")
    # The two extra points prove model X is the view normal, not a hidden
    # transverse component; Y is horizontal and the full model Z width is vertical.
    if abs((upper[0][2] - lower[0][2]) * 1000.0 - SHAFT_DIA) > 1e-5:
        raise RuntimeError(f"{label}: opposite silhouette separation is not the full diameter")
    return sheet[0], sheet[2]


def _outboard_neck_silhouettes(adapter: Any, side: Any) -> tuple[Any, tuple[Any, Any]]:
    """Find exactly the two real outlines on the spec-owned left-hand short land."""
    source_face = _outboard_neck_source_face(side)
    matches: dict[int, list[Any]] = {-1: [], 1: []}
    view = _early_bound(side, "IView")
    for component in view.GetVisibleComponents() or ():
        for entity in visible_component_entities(view, component, 4):
            points = _neck_silhouette_points(entity, label="collar-side neck enumeration")
            for sign in (-1, 1):
                expected = (
                    (0.0, COLLAR_REAR / 1000.0, sign * SHAFT_DIA / 2000.0),
                    (0.0, JOURNAL_START / 1000.0, sign * SHAFT_DIA / 2000.0),
                )
                if all(math.dist(actual, target) <= NECK_GEOMETRY_TOLERANCE_M
                       for actual, target in zip(points, expected)):
                    matches[sign].append(entity)
    if any(len(flanks) != 1 for flanks in matches.values()):
        raise RuntimeError("collar-side neck: expected exactly two opposite short-neck silhouettes")
    pair = matches[-1][0], matches[1][0]
    _assert_neck_silhouette_pair(adapter, side, pair, source_face, label="collar-side neck source")
    return source_face, pair


def _native_neck_annotations(side: Any, *, label: str) -> tuple[tuple[Any, int], ...]:
    """Read the counted native array; absent or malformed evidence is not empty."""
    view = _early_bound(side, "IView")
    count = view.GetAnnotationCount()
    if type(count) is not int or not 0 <= count <= 2147483647:
        raise RuntimeError(f"{label}: invalid native annotation count {count!r}")
    raw = view.GetAnnotations()
    if raw is None:
        if count != 0:
            raise RuntimeError(f"{label}: native annotation count {count} returned no array")
        return ()
    if type(raw) not in (tuple, list):
        raise RuntimeError(f"{label}: invalid native annotation array {raw!r}")
    if len(raw) != count:
        raise RuntimeError(f"{label}: native annotation array length {len(raw)} != count {count}")
    annotations = []
    for index, item in enumerate(raw):
        if item is None:
            raise RuntimeError(f"{label}: native annotation #{index} is null")
        annotation = _early_bound(item, "IAnnotation")
        kind = annotation.GetType()
        if type(kind) is not int or not -2147483648 <= kind <= 2147483647:
            raise RuntimeError(f"{label}: invalid native annotation type {kind!r}")
        annotations.append((annotation, kind))
    return tuple(annotations)


def _initialize_neck_true_measurements(side: Any) -> None:
    """Change the measurement domain only at the proven empty-view boundary."""
    label = "crankshaft fresh SIDE"
    view = _early_bound(side, "IView")
    count = view.GetDimensionCount4()
    if type(count) is not int or count != 0:
        raise RuntimeError(f"{label}: expected native dimension count 0, got {count!r}")
    annotations = _native_neck_annotations(view, label=label)
    if any(kind == 4 for _annotation, kind in annotations):  # swDisplayDimension
        raise RuntimeError(f"{label}: type-4 dimension exists before measurement initialization")
    # SDK: changing ProjectedDimensions deletes existing dimensions. Never
    # reach this setter on a populated or unqualified template view.
    view.ProjectedDimensions = False
    if view.ProjectedDimensions is not False:
        raise RuntimeError(f"{label}: ProjectedDimensions did not read back False")


def _assert_neck_measurement_domain(side: Any, *, label: str) -> None:
    """Retain true measurements without changing the intended 2:1 paper scale."""
    view = _early_bound(side, "IView")
    if view.ProjectedDimensions is not False:
        raise RuntimeError(f"{label}: ProjectedDimensions must remain False")
    ratio = view.ScaleRatio
    decimal = view.ScaleDecimal
    if (
        type(ratio) not in (tuple, list)
        or len(ratio) != 2
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in ratio)
        or tuple(ratio) != VIEW_SCALE
        or type(decimal) not in (int, float)
        or not math.isfinite(decimal)
        or decimal != VIEW_SCALE[0] / VIEW_SCALE[1]
    ):
        raise RuntimeError(f"{label}: native scale must remain 2:1 / 2, got {ratio!r} / {decimal!r}")


def _native_neck_view_dimensions(side: Any, *, label: str) -> list[tuple[Any, Any, Any]]:
    """Bind real view dimensions; a type-4 annotation without native data refuses."""
    dimensions = []
    for annotation, kind in _native_neck_annotations(side, label=label):
        if kind != 4:  # swDisplayDimension
            continue
        specific = annotation.GetSpecificAnnotation()
        if specific is None:
            raise RuntimeError(f"{label}: type-4 annotation has no native display")
        display = _early_bound(specific, "IDisplayDimension")
        native = display.GetDimension2(0)
        if native is None:
            raise RuntimeError(f"{label}: no native IDimension")
        dimensions.append((annotation, display, _early_bound(native, "IDimension")))
    return dimensions


def _neck_dimension_record(native: Any, *, label: str) -> tuple[Any, str, float, int]:
    """Retain native identity and the complete preexisting scalar/state record."""
    name = native.FullName
    value = native.SystemValue
    state = native.DrivenState
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{label}: preexisting native dimension has no FullName")
    if type(value) not in (int, float) or not math.isfinite(value):
        raise RuntimeError(f"{label}: preexisting dimension {name!r} has invalid value {value!r}")
    if type(state) is not int or not -2147483648 <= state <= 2147483647:
        raise RuntimeError(f"{label}: preexisting dimension {name!r} has invalid driven state {state!r}")
    return native, name, float(value), state


def _assert_preexisting_neck_inventory(
    adapter: Any, current: list[tuple[Any, Any, Any]],
    preexisting: tuple[tuple[Any, str, float, int, Any], ...], *, label: str,
) -> None:
    """Require every prior native dimension, including drawing-authored callouts."""
    try:
        if len(current) != len(preexisting):
            raise RuntimeError(f"{label}: preexisting dimension inventory missing/extra entries")
        by_name: dict[str, list[tuple[int, Any, float, int]]] = {}
        for index, (_owner, _display, native) in enumerate(current):
            native, name, actual_value, actual_state = _neck_dimension_record(native, label=label)
            by_name.setdefault(name, []).append((index, native, actual_value, actual_state))
        matched = set()
        for reference, captured_name, value, state, _annotation in preexisting:
            # SaveAs may update the native reference's title component. Match
            # its live FullName and native identity, never captured text alone.
            live_name = reference.FullName
            if not isinstance(live_name, str) or not live_name:
                raise RuntimeError(f"{label}: preexisting dimension {captured_name!r} lost its FullName")
            matches = [
                (index, actual_value, actual_state)
                for index, native, actual_value, actual_state in by_name.get(live_name, ())
                if int(adapter.swApp.IsSame(native, reference)) == 1
                and int(adapter.swApp.IsSame(reference, native)) == 1
            ]
            if len(matches) != 1 or matches[0][0] in matched:
                raise RuntimeError(f"{label}: expected one preserved preexisting dimension {captured_name!r}")
            index, actual_value, actual_state = matches[0]
            matched.add(index)
            if actual_value != value or actual_state != state:
                raise RuntimeError(
                    f"{label}: preexisting dimension {captured_name!r} changed value/state "
                    f"from {(value, state)!r} to {(actual_value, actual_state)!r}"
                )
    except Exception as original:
        # Read diagnostic ownership only on refusal, from the actual captured
        # and current annotation rows. Wrapper IDs are explicitly diagnostic,
        # never a substitute for the native IsSame checks above.
        def row(annotation: Any, native: Any) -> dict[str, Any]:
            owner = annotation.Owner
            return {
                "FullName": native.FullName,
                "native_wrapper_id": hex(id(native)),
                "OwnerType": annotation.OwnerType,
                "owner_wrapper_id": None if owner is None else hex(id(owner)),
            }

        try:
            expected_rows = [
                {"captured_FullName": name, **row(annotation, native)}
                for native, name, _value, _state, annotation in preexisting
            ]
            current_rows = [
                row(annotation, native) for annotation, _display, native in current
            ]
        except Exception as receipt_error:
            original.add_note(
                f"{label}: preexisting inventory receipt getter failed: "
                f"{type(receipt_error).__name__}: {receipt_error}"
            )
            raise original from None
        raise RuntimeError(
            f"{original}; expected_native_rows={expected_rows!r}; current_native_rows={current_rows!r}"
        ) from original


def _assert_plain_neck_size(
    display: Any, *, label: str, expected_driven_state: int, linear: bool,
) -> float:
    """Prove a loose native size without rewriting the imported dimension."""
    native = display.GetDimension2(0)
    if native is None:
        raise RuntimeError(f"{label}: no native IDimension")
    dimension = _early_bound(native, "IDimension")
    expected_types = (2, 12) if linear else (6,)  # swLinear/VertLinear versus imported diameter
    if type(display.Type2) is not int or display.Type2 not in expected_types:
        raise RuntimeError(f"{label}: native display type {display.Type2!r} not in {expected_types}")
    value = dimension.SystemValue
    if type(value) not in (int, float) or not math.isfinite(value):
        raise RuntimeError(f"{label}: no finite native measured value {value!r}")
    measured_mm = value * 1000.0
    if abs(measured_mm - SHAFT_DIA) > 1e-5:
        raise RuntimeError(f"{label}: measures {measured_mm!r} mm, expected {SHAFT_DIA}")
    if type(dimension.DrivenState) is not int or dimension.DrivenState != expected_driven_state:
        raise RuntimeError(
            f"{label}: native driven state {dimension.DrivenState!r} "
            f"!= preserved/required state {expected_driven_state}"
        )
    places = display.GetPrimaryPrecision2()
    if type(places) is not int or places != NECK_DIA_PLACES:
        raise RuntimeError(f"{label}: primary places {places!r} != {NECK_DIA_PLACES}")
    tolerance = None if dimension.Tolerance is None else _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if (
        tolerance is None or type(tolerance.Type) is not int or tolerance.Type != 4  # swTolSYMMETRIC
        or abs(float(tolerance.GetMaxValue()) * 1000.0 - NECK_DIA_TOL) > 1e-6
        or abs(float(tolerance.GetMinValue()) * 1000.0 + NECK_DIA_TOL) > 1e-6
    ):
        raise RuntimeError(f"{label}: the neck's native band is not +/-{NECK_DIA_TOL} mm")
    if display.GetOverride() is not False or display.ShowParenthesis is not False:
        raise RuntimeError(f"{label}: overridden or parenthesized value loses the neck's band")
    prefix = str(display.GetText(1) or "")
    prose = tuple(str(display.GetText(part) or "") for part in (2, 3, 4))
    allowed_prefixes = ("<MOD-DIAM>",) if linear else ("", "<MOD-DIAM>")
    if prefix not in allowed_prefixes or any(prose):
        raise RuntimeError(f"{label}: unexpected native diameter text {prefix!r}, {prose!r}")
    if linear and display.ShowDimensionValue is not True:
        raise RuntimeError(f"{label}: native dimension value is hidden")
    return measured_mm


def _assert_neck_arrow_landing(display: Any, *, label: str) -> tuple[Any, tuple[Segment, ...]]:
    """Require both physical flank tips and complete heads inside the neck's X trim."""
    raw = display.GetDisplayData()
    if raw is None:
        raise RuntimeError(f"{label}: no native diameter display data")
    data = _early_bound(raw, "IDisplayData")
    count = data.GetArrowHeadCount()
    if type(count) is not int or count != 2:
        raise RuntimeError(f"{label}: expected two readable native diameter arrowheads")
    arrows = []
    head_bounds = []
    x_clearances_mm = []
    complete_heads = []
    tolerance = NECK_ARROW_LANDING_TOLERANCE_M
    x0, y0, x1, y1 = OUTBOARD_NECK_ARROW_WINDOW
    for index in range(count):
        values = _neck_numbers(data.GetArrowHeadAtIndex2(index), 12, label=f"{label} arrowhead")
        tip = values[0], values[1]
        if not (
            x0 - tolerance <= tip[0] <= x1 + tolerance
            and min(abs(tip[1] - y0), abs(tip[1] - y1)) <= tolerance
        ):
            raise RuntimeError(f"{label}: diameter arrow {tip!r} does not identify a physical neck flank")
        dx, dy, dz = values[3:6]
        length = math.hypot(dx, dy)
        if length == 0.0 or abs(dz) > 1e-9:
            raise RuntimeError(f"{label}: unreadable native arrow direction {values[3:6]!r}")
        if abs(dx / length) > NECK_ARROW_DIRECTION_X_SLACK:
            raise RuntimeError(f"{label}: full-width dimension arrows are not vertical")
        nx, ny, nz = values[9:12]
        if max(abs(nx), abs(ny), abs(abs(nz) - 1.0)) > 1e-9:
            raise RuntimeError(f"{label}: arrowhead normal is not sheet-normal")
        width, height = values[6:8]
        if width <= 0.0 or height <= 0.0:
            raise RuntimeError(f"{label}: native arrowhead width/height must be positive")
        segments = arrowhead_segments(values)
        bounds = (
            min(min(segment.x0, segment.x1) for segment in segments),
            min(min(segment.y0, segment.y1) for segment in segments),
            max(max(segment.x0, segment.x1) for segment in segments),
            max(max(segment.y0, segment.y1) for segment in segments),
        )
        if bounds[0] < x0 or bounds[2] > x1:
            raise RuntimeError(
                f"{label}: complete native arrowhead X envelope {bounds[0], bounds[2]} "
                f"escapes physical neck trim {x0, x1}"
            )
        head_bounds.append(bounds)
        complete_heads.extend(segments)
        x_clearances_mm.append(min(bounds[0] - x0, x1 - bounds[2]) * 1000.0)
        arrows.append(tip)
    lower, upper = sorted(arrows, key=lambda point: point[1])
    if (
        abs(lower[1] - y0) > tolerance or abs(upper[1] - y1) > tolerance
        or abs(lower[0] - upper[0]) > tolerance
    ):
        raise RuntimeError(f"{label}: arrowheads do not bracket both opposite physical neck flanks")
    _telemetry.info(
        f"{label}: native full-width arrows={arrows}, neck={OUTBOARD_NECK_ARROW_WINDOW}, "
        f"head_bounds_m={head_bounds}, "
        f"min_physical_x_clearance_mm={min(x_clearances_mm)}"
    )
    return data, tuple(complete_heads)


def _neck_native_lines(data: Any, *, label: str) -> tuple[Segment, ...]:
    count = data.GetLineCount()
    if type(count) is not int or count <= 0:
        raise RuntimeError(f"{label}: expected readable native line primitives")
    lines = []
    for index in range(count):
        values = _neck_numbers(data.GetLineAtIndex3(index), 10, label=f"{label} line {index}")
        segment = line_segment(values)
        # SOLIDWORKS may interleave well-formed zero-length display sentinels.
        # They draw no ink; the owning route still proves its real primitives.
        if segment is not None:
            lines.append(segment)
    return tuple(lines)


def _neck_native_texts(data: Any, *, label: str) -> tuple[dict[str, Any], ...]:
    """Read actual nonblank advances, never a calibrated or estimated ink box."""
    count = data.GetTextCount()
    if type(count) is not int or count <= 0:
        raise RuntimeError(f"{label}: expected readable native text primitives")
    texts = []
    for index in range(count):
        text = data.GetTextAtIndex(index)
        if not isinstance(text, str):
            raise RuntimeError(f"{label}: unreadable native text {index}")
        if not text.strip():
            continue
        position = _neck_numbers(
            data.GetTextPositionAtIndex(index), 3, label=f"{label} text position {index}",
        )
        height, width, angle = _neck_numbers(
            [data.GetTextHeightAtIndex(index), data.GetTextInBoxWidthAtIndex(index),
             data.GetTextAngleAtIndex(index)], 3, label=f"{label} text metrics {index}",
        )
        reference = data.GetTextRefPositionAtIndex(index)
        if height <= 0.0 or width <= 0.0 or angle != 0.0 or type(reference) is not int or reference != 1:
            raise RuntimeError(f"{label}: expected positive actual horizontal native ADVANCE {index}")
        texts.append({
            "text": text, "position": position, "height": height, "width": width,
            "angle": angle, "reference": reference,
            "advance": InkBox(position[0], position[1], position[0] + width, position[1] + height),
        })
    if not texts:
        raise RuntimeError(f"{label}: no nonblank native text")
    return tuple(texts)


def _neck_crossing(first: Segment, second: Segment) -> tuple[float, float] | None:
    crossing = _segment_crossing(first, second)
    if crossing is not None:
        return crossing
    # The shared nonparallel crossing helper intentionally excludes collinear
    # runs. A true coincident endpoint/overlap must not escape this local guard.
    for point, other in (
        ((first.x0, first.y0), second), ((first.x1, first.y1), second),
        ((second.x0, second.y0), first), ((second.x1, second.y1), first),
    ):
        if point_segment_distance(point, other) == 0.0:
            return point
    return None


def _neck_root_point_contact(
    first: Segment, second: Segment, root: tuple[float, float],
) -> bool:
    """Exempt only a shared root point, never a positive collinear stretch."""
    crossing = _neck_crossing(first, second)
    tolerance = NECK_GEOMETRY_TOLERANCE_M
    if crossing is None or math.dist(crossing, root) > tolerance or any(
        min(math.dist(root, (line.x0, line.y0)), math.dist(root, (line.x1, line.y1))) > tolerance
        for line in (first, second)
    ):
        return False
    ux, uy = (first.x1 - first.x0) / first.length, (first.y1 - first.y0) / first.length
    ends = ((second.x0, second.y0), (second.x1, second.y1))
    if max(abs((x - first.x0) * uy - (y - first.y0) * ux) for x, y in ends) <= tolerance:
        low, high = sorted((x - first.x0) * ux + (y - first.y0) * uy for x, y in ends)
        if min(high, first.length) > max(low, 0.0):
            return False
    return True


def _neck_native_ge(left: float, right: float) -> bool:
    """Inclusive native bay boundary only: finite, relative tolerance zero, at most two ULPs."""
    return (
        math.isfinite(left) and math.isfinite(right)
        and (left >= right or right - left <= 2 * max(math.ulp(left), math.ulp(right)))
    )


def _assert_neck_right_advance(
    data: Any, heads: tuple[Segment, ...], foreign_lines: tuple[Segment, ...], *, label: str,
) -> tuple[tuple[Segment, ...], tuple[dict[str, Any], ...]]:
    lines = _neck_native_lines(data, label=label)
    texts = _neck_native_texts(data, label=label)
    words = tuple(row["text"].strip() for row in texts)
    if words[:1] != ("<MOD-DIAM>",) or "".join(words[1:]).replace("<MOD-PM>", "\N{PLUS-MINUS SIGN}").replace(
        " ", ""
    ) != f"{inch_text(SHAFT_DIA, NECK_DIA_PLACES)}\N{PLUS-MINUS SIGN}{inch_text(NECK_DIA_TOL, NECK_DIA_PLACES)}":
        raise RuntimeError(f"{label}: native diameter text primitives changed: {words!r}")
    shelves = [line for line in lines if line.y0 == line.y1]
    if len(lines) != 3 or len(shelves) != 1 or any(
        line.x0 != line.x1 and line.y0 != line.y1 for line in lines
    ):
        raise RuntimeError(
            f"{label}: expected the three ordinary native diameter primitives, got "
            f"{[(line.x0, line.y0, line.x1, line.y1) for line in lines]!r}"
        )
    shelf = shelves[0]
    x = OUTBOARD_NECK_DIAMETER_XY[0]
    roof = _sheet_y(JOURNAL_DIA / 2.0)
    walls = [
        line.x0 for line in foreign_lines
        if line.x0 == line.x1 and line.x0 > x
        and min(line.y0, line.y1) <= roof <= max(line.y0, line.y1)
    ]
    if not walls or not roof < shelf.y0 < COLLAR_REAR_FINISH[1][1]:
        raise RuntimeError(f"{label}: unreadable actual journal-roof/right-wall bay")
    right = min(walls)
    shelf_min_x, shelf_max_x = min(shelf.x0, shelf.x1), max(shelf.x0, shelf.x1)
    left = not _neck_native_ge(shelf_min_x, x)
    right_overflow = not _neck_native_ge(right, shelf_max_x)
    if left or right_overflow:
        raise RuntimeError(
            f"{label}: ordinary native diameter shelf is not RIGHT: "
            f"shelf_x_m={(shelf_min_x, shelf_max_x)!r}, authored_x_m={x!r}, right_wall_m={right!r}, "
            f"LEFT={left}, RIGHT_OVERFLOW={right_overflow}, "
            f"raw_min_minus_authored_x_m={shelf_min_x - x!r}, "
            f"raw_max_minus_wall_m={shelf_max_x - right!r}"
        )
    if not any(abs(endpoint - x) <= NECK_GEOMETRY_TOLERANCE_M for endpoint in (shelf.x0, shelf.x1)):
        raise RuntimeError(f"{label}: ordinary native shelf lost its actual vertical root")
    if any(abs(line.x0 - x) > NECK_GEOMETRY_TOLERANCE_M for line in lines if line not in shelves):
        raise RuntimeError(f"{label}: ordinary native diameter vertical primitives moved")
    intervals = sorted(
        (min(line.y0, line.y1), max(line.y0, line.y1)) for line in lines if line not in shelves
    )
    lower_tip, upper_tip = sorted(heads[index].y0 for index in (0, 3))
    tolerance = NECK_GEOMETRY_TOLERANCE_M
    if (
        abs(intervals[0][0] - lower_tip) > tolerance
        or abs(max(high for _, high in intervals) - shelf.y0) > tolerance
        or intervals[1][0] > intervals[0][1] + tolerance
        or any(low < lower_tip - tolerance or high > shelf.y0 + tolerance for low, high in intervals)
        or not any(low - tolerance <= upper_tip <= high + tolerance for low, high in intervals)
    ):
        raise RuntimeError(f"{label}: ordinary native vertical route does not connect both tips to the shelf")
    for row in texts:
        box = row["advance"]
        if not (
            _neck_native_ge(box.xmin, x) and _neck_native_ge(right, box.xmax)
            and _neck_native_ge(box.ymin, shelf.y0)
            and _neck_native_ge(COLLAR_REAR_FINISH[1][1], box.ymax)
        ):
            deltas = (
                box.xmin - x, box.xmax - right,
                box.ymin - shelf.y0, box.ymax - COLLAR_REAR_FINISH[1][1],
            )
            raise RuntimeError(
                f"{label}: complete nonblank native ADVANCE escaped the RIGHT bay: "
                f"text={row['text']!r}, advance_m={(box.xmin, box.ymin, box.xmax, box.ymax)!r}, "
                f"inclusive_bay_m={(x, shelf.y0, right, COLLAR_REAR_FINISH[1][1])!r}, "
                f"raw_boundary_deltas_m={deltas!r}"
            )
    for line in lines:
        for foreign in foreign_lines:
            if _neck_crossing(line, foreign) is not None:
                raise RuntimeError(f"{label}: ordinary native diameter route intersects a preexisting dimension")
    _telemetry.info(
        f"{label}: RIGHT native_ADVANCE_only_m={[row['advance'] for row in texts]}, "
        f"ordinary_lines_m={lines}, journal_roof_m={roof}, actual_right_wall_m={right}; "
        "printed glyph bounds require the final exported PDF"
    )
    return lines, texts


def _assert_outboard_neck_dimension(
    adapter: Any, side: Any, identity: Any, right_driven_state: int,
    preexisting: tuple[tuple[Any, str, float, int, Any], ...], *, phase: str,
) -> tuple[tuple[Segment, ...], tuple[Segment, ...], tuple[dict[str, Any], ...], tuple[Segment, ...]]:
    """Reacquire the native linear size and both exact physical silhouettes."""
    label = f"collar-side neck ({phase})"
    _assert_neck_measurement_domain(side, label=label)
    reference = _early_bound(identity, "IDimension")
    # Read the live FullName from the captured native object: SaveAs may
    # update its model/title component. A stale selection-name string is
    # not the persistence identity.
    full_name = reference.FullName
    if not isinstance(full_name, str) or not full_name:
        raise RuntimeError(f"{label}: missing native dimension FullName")
    # Precision/parenthesis setters explicitly require a redraw for current
    # display data. EditRebuild3 alone does not promise a fresh arrow buffer.
    # One void redraw per proof also covers the finalizer's settling rebuild.
    _early_bound(adapter.currentModel, "IModelDoc2").GraphicsRedraw2()
    matches: list[tuple[Any, Any]] = []
    inboard: list[Any] = []
    current_preexisting: list[tuple[Any, Any, Any]] = []
    for annotation, display, native in _native_neck_view_dimensions(side, label=label):
        if dimension_name(adapter, annotation) == "NeckDiaDim":
            inboard.append(display)
        if (
            native.FullName == full_name
            and int(adapter.swApp.IsSame(native, reference)) == 1
            and int(adapter.swApp.IsSame(reference, native)) == 1
        ):
            matches.append((annotation, display))
        else:
            current_preexisting.append((annotation, display, native))
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one native view dimension {full_name!r}")
    annotation, display = matches[0]
    owner = annotation.Owner
    if (
        type(annotation.OwnerType) is not int or annotation.OwnerType != 0  # drawing view
        or owner is None
        or int(adapter.swApp.IsSame(owner, side)) != 1
        or int(adapter.swApp.IsSame(side, owner)) != 1
    ):
        raise RuntimeError(f"{label}: native annotation owner is not FRONT")
    measured_mm = _assert_plain_neck_size(
        display, label=label, expected_driven_state=1, linear=True,
    )
    if len(inboard) != 1:
        raise RuntimeError(f"{label}: expected one unchanged right-hand NeckDiaDim")
    _assert_plain_neck_size(
        inboard[0], label=f"right-hand NeckDiaDim ({phase})",
        expected_driven_state=right_driven_state, linear=False,
    )
    _assert_preexisting_neck_inventory(adapter, current_preexisting, preexisting, label=label)
    source_face, entities = _outboard_neck_silhouettes(adapter, side)
    attached = tuple(annotation.GetAttachedEntities3() or ())
    count = annotation.GetAttachedEntityCount3()
    types = tuple(annotation.GetAttachedEntityTypes() or ())
    if (
        type(count) is not int or count != 2 or len(attached) != 2
        or types != (46, 46)  # swSelSILHOUETTES
        or any(type(kind) is not int for kind in types)
        or any(entity is None for entity in attached)
        or annotation.IsDangling() is not False
    ):
        raise RuntimeError(f"{label}: lost exact two-silhouette attachment: count={count}, types={types}")
    ordered = tuple(sorted(
        attached, key=lambda entity: _neck_silhouette_points(entity, label=label)[0][2],
    ))
    _assert_neck_silhouette_pair(adapter, side, ordered, source_face, label=f"{label} attachment")
    # Shared silhouette identity is owning-face identity, not unsupported
    # ISldWorks.IsSame on ISilhouetteEdge. The stricter endpoints above
    # distinguish the two flanks even though they share the same face.
    assert_dimension_measures(
        adapter, display, expected_mm=SHAFT_DIA, label=label,
        entities=entities, entity_types=("SILHOUETTE", "SILHOUETTE"),
    )
    data, heads = _assert_neck_arrow_landing(display, label=label)
    if any(
        abs(heads[index].x0 - OUTBOARD_NECK_DIAMETER_XY[0]) > NECK_GEOMETRY_TOLERANCE_M
        for index in (0, 3)
    ):
        raise RuntimeError(f"{label}: actual diameter tips moved from the approved native origin X")
    foreign_lines = []
    for _, prior_display, _ in current_preexisting:
        raw_data = prior_display.GetDisplayData()
        if raw_data is None:
            raise RuntimeError(f"{label}: preexisting dimension has no native display data")
        foreign_lines.extend(_neck_native_lines(_early_bound(raw_data, "IDisplayData"), label=label))
    lines, texts = _assert_neck_right_advance(data, heads, tuple(foreign_lines), label=label)
    _telemetry.info(
        f"{label}: native diameter {full_name!r}, measured_mm={measured_mm}, "
        f"driven=1, places={NECK_DIA_PLACES}, tolerance=+/-{NECK_DIA_TOL}mm, opposite_silhouettes=True, "
        f"native_leaders={annotation.GetLeaderCount()}"
    )
    return lines, heads, texts, tuple(foreign_lines)


def _add_outboard_neck_dimension(
    adapter: Any, drawing_model: Any, side: Any, collar_rear_face: Any, collar_rear_symbol: Any,
) -> tuple[Any, int, tuple[tuple[Any, str, float, int, Any], ...]]:
    """Add only a native driven measurement; never write a diameter value."""
    label = "collar-side neck"
    original = [
        (annotation, _display, native)
        for annotation, _display, native in _native_neck_view_dimensions(side, label=label)
        if dimension_name(adapter, annotation) == "NeckDiaDim"
    ]
    if len(original) != 1:
        raise RuntimeError(f"{label}: expected one original right-hand NeckDiaDim")
    right_driven_state = original[0][2].DrivenState
    if type(right_driven_state) is not int or right_driven_state not in (1, 2):
        raise RuntimeError(f"{label}: unreadable original driven state {right_driven_state!r}")
    _assert_neck_measurement_domain(side, label=label)
    source_face, entities = _outboard_neck_silhouettes(adapter, side)
    selection = _early_bound(drawing_model.SelectionManager, "ISelectionMgr")
    selected = []
    for sign, entity in zip((-1, 1), entities):
        picked = _select_view_entity(
            adapter, side, "SILHOUETTE", None, label=label, entity=entity,
        )
        count = selection.GetSelectedObjectCount2(-1)
        kind = selection.GetSelectedObjectType3(1, -1)
        if type(count) is not int or count != 1 or type(kind) is not int or kind != 46:
            raise RuntimeError(f"{label}: exact silhouette selection count/type is invalid")
        owner = selection.GetSelectedObjectsDrawingView2(1, -1)
        if (
            owner is None or int(adapter.swApp.IsSame(owner, side)) != 1
            or int(adapter.swApp.IsSame(side, owner)) != 1
        ):
            raise RuntimeError(f"{label}: selected silhouette owner is not FRONT")
        _assert_neck_silhouette(
            adapter, side, picked, source_face, sign, label=f"{label} selection",
        )
        selected.append(picked)
    # Capture every preexisting native dimension before the factory can change
    # anything. The shared helper then selects these exact two objects using
    # ISilhouetteEdge.Select2 + SelectData.View and checks the pair's count.
    preexisting = tuple(
        (*_neck_dimension_record(native, label=label), annotation)
        for annotation, _display, native in _native_neck_view_dimensions(side, label=label)
    )
    display = add_edge_dimension(
        adapter, side, p0=(COLLAR_REAR_X, _sheet_y(-SHAFT_DIA / 2.0)),
        p1=(COLLAR_REAR_X, _sheet_y(SHAFT_DIA / 2.0)),
        text_xy=OUTBOARD_NECK_DIAMETER_XY, label=label, orientation="vertical",
        entities=(selected[0], selected[1]), entity_types=("SILHOUETTE", "SILHOUETTE"),
    )
    if display is None:
        raise RuntimeError(f"{label}: native vertical linear factory returned no display")
    display = _early_bound(display, "IDisplayDimension")
    native = display.GetDimension2(0)
    if native is None:
        raise RuntimeError(f"{label}: new display has no native IDimension")
    dimension = _early_bound(native, "IDimension")
    value = dimension.SystemValue  # FIRST native value read, before any new-dimension writes
    actual_type = display.Type2
    mode = _early_bound(side, "IView").ProjectedDimensions
    _telemetry.info(
        f"{label}: vertical linear factory type={actual_type!r}, "
        f"SystemValue={value!r}, ProjectedDimensions={mode!r}"
    )
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or abs(value * 1000.0 - SHAFT_DIA) > 1e-5
    ):
        raise RuntimeError(f"{label}: immediate native value {value!r} m, expected {SHAFT_DIA} mm")
    if type(actual_type) is not int or actual_type not in (2, 12):  # linear / vertical linear
        raise RuntimeError(f"{label}: factory native display is not linear (2 or 12)")
    if mode is not False:
        raise RuntimeError(f"{label}: factory ProjectedDimensions must remain False")
    dimension.DrivenState = 1  # swDimensionDriven; only the new drawing dimension
    if type(dimension.DrivenState) is not int or dimension.DrivenState != 1:
        raise RuntimeError(f"{label}: new native dimension did not become driven")
    display.SetText(1, "<MOD-DIAM>")  # symbol-only prefix; never swDimensionTextAll
    if display.GetText(1) != "<MOD-DIAM>":
        raise RuntimeError(f"{label}: native diameter-symbol prefix did not persist")
    # The same explicit loose band as the right-hand NeckDiaDim (the build's
    # NECK_DIA_TOL), printed at the value's places, never a parenthesized
    # reference.
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 4  # swTolSYMMETRIC
    if not tolerance.SetValues(-NECK_DIA_TOL / 1000.0, NECK_DIA_TOL / 1000.0):
        raise RuntimeError(f"{label}: native symmetric band rejected")
    status = display.SetPrecision3(
        DRAWING_REFERENCE_PRECISION["OutboardNeckDia"], -1,
        DRAWING_REFERENCE_PRECISION["OutboardNeckDia"], -1,
    )
    if type(status) is not int or status != 0:
        raise RuntimeError(f"{label}: native precision assignment failed ({status!r})")
    display.ShowParenthesis = False
    if not isinstance(dimension.FullName, str) or not dimension.FullName:
        raise RuntimeError(f"{label}: new native dimension has no FullName")
    drawing_model.ClearSelection2(True)
    rebuild_drawing(adapter, label=label)
    _outboard_neck_checkpoint(
        adapter, side, dimension, right_driven_state, preexisting,
        collar_rear_face, collar_rear_symbol, "after insertion rebuild",
    )
    return dimension, right_driven_state, preexisting


def _assert_collar_rear_finish(
    adapter: Any, face: Any, symbol: Any,
    neck: tuple[tuple[Segment, ...], tuple[Segment, ...], tuple[dict[str, Any], ...], tuple[Segment, ...]],
    *, phase: str,
) -> tuple[tuple[Segment, ...], tuple[Segment, ...], tuple[dict[str, Any], ...], Segment, tuple[float, float]]:
    """Prove the one straight finish, its native ADVANCE and its unchanged face."""
    label = f"crankshaft collar rear (post boss) face finish ({phase})"
    if symbol is None or face is None:
        raise RuntimeError(f"{label}: missing captured native symbol or face")
    symbol = _early_bound(symbol, "ISFSymbol")
    symbol_type = symbol.GetSymbol()
    roughness = symbol.GetText(8)
    if type(symbol_type) is not int or symbol_type != 1:
        raise RuntimeError(f"surface-finish symbol type did not persist ({label})")
    if not isinstance(roughness, str) or roughness.strip() != COLLAR_REAR_FINISH_TEXT:
        raise RuntimeError(f"surface-finish roughness did not persist ({label})")
    raw_annotation = symbol.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError(f"{label}: captured native symbol has no annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    style = annotation.GetLeaderStyle()
    leader_count = annotation.GetLeaderCount()
    attached_count = annotation.GetAttachedEntityCount3()
    arrow_style = annotation.GetArrowHeadStyleAtIndex(0)
    if (
        type(style) is not int or style != 1
        or type(leader_count) is not int or leader_count != 1
        or type(attached_count) is not int or attached_count != 1
        or annotation.IsDangling() is not False
    ):
        raise RuntimeError(f"{label}: expected one attached native STRAIGHT leader")
    if (
        annotation.GetSmartArrowHeadStyle() is not False
        or type(arrow_style) is not int or arrow_style != 1  # swCLOSED_ARROWHEAD
    ):
        raise RuntimeError(f"{label}: expected the explicit filled arrowhead, not a smart one")
    _assert_attached_to(
        adapter, annotation, face, entity_type="FACE",
        what="surface-finish symbol", label=label,
    )
    _assert_leader_lands(
        annotation, COLLAR_REAR_FINISH[0], what="surface-finish symbol", label=label,
    )
    points = _neck_numbers(
        annotation.GetLeaderPointsAtIndex(0), 6, label=f"{label} native straight leader",
    )
    attached = annotation.GetAttachedEntities3()
    same_face = int(adapter.swApp.IsSame(attached[0], face))
    if same_face != 1:
        raise RuntimeError(f"{label}: native face identity did not persist")
    raw_data = annotation.GetDisplayData()
    if raw_data is None:
        raise RuntimeError(f"{label}: no native surface-finish display data")
    data = _early_bound(raw_data, "IDisplayData")
    lines = _neck_native_lines(data, label=label)
    texts = _neck_native_texts(data, label=label)
    if "".join(ink_key(row["text"]) for row in texts) != ink_key(COLLAR_REAR_FINISH_TEXT):
        raise RuntimeError(f"{label}: native surface-finish display roughness changed")
    leader = Segment(points[0], points[1], points[3], points[4])
    registered = [
        line for line in lines
        if min(
            max(math.hypot(line.x0 - leader.x0, line.y0 - leader.y0),
                math.hypot(line.x1 - leader.x1, line.y1 - leader.y1)),
            max(math.hypot(line.x1 - leader.x0, line.y1 - leader.y0),
                math.hypot(line.x0 - leader.x1, line.y0 - leader.y1)),
        ) <= NECK_GEOMETRY_TOLERANCE_M
    ]
    if len(registered) != 1 or len(lines) != 6:
        raise RuntimeError(f"{label}: native straight leader/complete symbol primitives are unreadable")
    root = (leader.x0, leader.y0)
    for line in lines:
        if line is registered[0]:
            continue
        crossing = _neck_crossing(leader, line)
        if crossing is not None and not _neck_root_point_contact(leader, line, root):
            raise RuntimeError(f"{label}: straight leader crosses its own surface-finish legs")
    count = data.GetArrowHeadCount()
    if type(count) is not int or count != 1:
        raise RuntimeError(f"{label}: expected one readable native surface-finish head")
    arrow = _neck_numbers(data.GetArrowHeadAtIndex2(0), 12, label=f"{label} arrowhead")
    if (
        math.dist(arrow[:2], points[3:5]) > NECK_GEOMETRY_TOLERANCE_M
        or math.hypot(*arrow[3:5]) == 0.0 or abs(arrow[5]) > 1e-9
        or arrow[6] <= 0.0 or arrow[7] <= 0.0 or arrow[8] != 1.0
        or max(abs(arrow[9]), abs(arrow[10]), abs(abs(arrow[11]) - 1.0)) > 1e-9
    ):
        raise RuntimeError(f"{label}: malformed native surface-finish head geometry")
    heads = tuple(arrowhead_segments(arrow))
    neck_lines, neck_heads, neck_texts, foreign_lines = neck
    for line in lines:
        for other in (*neck_lines, *foreign_lines):
            if _neck_crossing(line, other) is not None:
                raise RuntimeError(f"{label}: native surface-finish route intersects a dimension")
        if any(segment_box_distance(line, row["advance"]) == 0.0 for row in neck_texts):
            raise RuntimeError(f"{label}: native surface-finish route intersects diameter ADVANCE")
    for other in foreign_lines:
        if any(segment_box_distance(other, row["advance"]) == 0.0 for row in texts):
            raise RuntimeError(f"{label}: native surface-finish ADVANCE intersects a dimension")
    advance_clearance = _neck_pdf_head_clearance(
        heads, {head: ((head, 0.0),) for head in heads},
        tuple(row["advance"] for row in neck_texts), (),
    )
    reciprocal_clearance = _neck_pdf_head_clearance(
        neck_heads, {head: ((head, 0.0),) for head in neck_heads},
        tuple(row["advance"] for row in texts), (),
    )
    if min(advance_clearance, reciprocal_clearance) < ARROW_TEXT_CLEARANCE_M:
        raise RuntimeError(f"{label}: full native head-to-ADVANCE clearance is below 2 mm")
    _telemetry.info(
        f"{label}: native_symbol_type={symbol_type}, native_roughness={roughness!r}, "
        f"same_face={same_face}, native_leader_style=1, leader_points_m={points}, "
        f"actual_tip_m={points[-3:]}, requested_tip_m={COLLAR_REAR_FINISH[0]}, "
        f"native_ADVANCE_only_m={[row['advance'] for row in texts]}, "
        f"full_head_to_native_ADVANCE_mm={advance_clearance * 1000.0}, "
        f"reciprocal_full_head_to_native_ADVANCE_mm={reciprocal_clearance * 1000.0}, "
        f"native_full_head_record={arrow}, native_full_head_segments_m={heads}, "
        f"native_symbol_lines_m={lines}; printed glyph proof remains separate"
    )
    return lines, heads, texts, registered[0], root


def _neck_segment_distance(first: Segment, second: Segment) -> float:
    if _neck_crossing(first, second) is not None:
        return 0.0
    return min(
        point_segment_distance((first.x0, first.y0), second),
        point_segment_distance((first.x1, first.y1), second),
        point_segment_distance((second.x0, second.y0), first),
        point_segment_distance((second.x1, second.y1), first),
    )


def _neck_pdf_line_overlap(segment: Segment, line: Segment) -> tuple[float, float, Segment] | None:
    """Actual aligned paint projected onto its native owner, including middles."""
    if not segment.length or not line.length:
        return None
    ux, uy = (line.x1 - line.x0) / line.length, (line.y1 - line.y0) / line.length
    dx, dy = segment.x1 - segment.x0, segment.y1 - segment.y0
    # Retain the existing _same_run angular and perpendicular attribution bands,
    # without requiring either piece endpoint to be a native endpoint.
    if abs(dx * uy - dy * ux) > segment.length * math.sin(math.radians(2.0)):
        return None
    ends = ((segment.x0, segment.y0), (segment.x1, segment.y1))
    if max(abs((x - line.x0) * uy - (y - line.y0) * ux) for x, y in ends) > COLLINEAR_TOL_M:
        return None
    start, end = ((x - line.x0) * ux + (y - line.y0) * uy for x, y in ends)
    low, high = max(min(start, end), 0.0), min(max(start, end), line.length)
    if high <= low:
        return None
    if min(start, end) < 0.0 or max(start, end) > line.length:
        # Do not claim a collinear model edge's out-of-owner tail. Clip on the
        # actual PDF stroke, preserving its real perpendicular offset and pen.
        first = segment.point_at((low - start) / (end - start))
        last = segment.point_at((high - start) / (end - start))
        segment = Segment(*first, *last)
    return low, high, segment


def _neck_pdf_owned_lines(
    strokes: tuple[tuple[Segment, float], ...], native: tuple[Segment, ...], *, label: str,
) -> dict[Segment, tuple[tuple[Segment, float], ...]]:
    """Require continuous projected paint coverage, retaining every owned piece."""
    owned = {}
    for line in native:
        matches = []
        intervals = []
        for segment, radius in strokes:
            overlap = _neck_pdf_line_overlap(segment, line)
            if overlap is not None:
                low, high, piece = overlap
                intervals.append((low, high))
                matches.append((piece, radius))
        covered = 0.0
        for low, high in sorted(intervals):
            if low > covered + COLLINEAR_TOL_M:
                break
            covered = max(covered, high)
        if not matches or covered < line.length - COLLINEAR_TOL_M:
            raise RuntimeError(f"{label}: complete native primitive has no actual PDF owner: {line!r}")
        owned[line] = tuple(matches)
    return owned


def _neck_pdf_owned_heads(
    strokes: tuple[tuple[Segment, float], ...], native: tuple[Segment, ...], *, label: str,
) -> dict[Segment, tuple[tuple[Segment, float], ...]]:
    """Bound coverage to the native edge, but never shorten actual head paint."""
    owned = _neck_pdf_owned_lines(strokes, native, label=label)
    for line in native:
        ux, uy = (line.x1 - line.x0) / line.length, (line.y1 - line.y0) / line.length
        matches = []
        for segment, radius in strokes:
            if _neck_pdf_line_overlap(segment, line) is None:
                continue
            projections = tuple(
                (x - line.x0) * ux + (y - line.y0) * uy
                for x, y in ((segment.x0, segment.y0), (segment.x1, segment.y1))
            )
            if min(projections) < -COLLINEAR_TOL_M or max(projections) > line.length + COLLINEAR_TOL_M:
                raise RuntimeError(f"{label}: ambiguous actual head stroke extends beyond its native edge")
            # Keep complete attributable endpoints, displacement and pen radius,
            # including allowed overhang: all of it participates in clearance.
            matches.append((segment, radius))
        owned[line] = tuple(matches)
    return owned


def _neck_pdf_diameter_paths(
    strokes: tuple[tuple[Segment, float], ...], prefix: InkBox, bay: InkBox,
) -> tuple[tuple[Segment, float], ...]:
    """Require a unique complete closed ring and its separate crossing slash."""
    paths = tuple(
        (line, radius) for line, radius in strokes
        if line.box().xmax >= prefix.xmin and line.box().xmin <= prefix.xmax
        and line.box().ymax > bay.ymin and line.box().ymin < bay.ymax
    )
    graph: dict[tuple[float, float], set[tuple[float, float]]] = {}
    edges = set()
    for line, radius in paths:
        bounds = line.box()
        if (
            bounds.xmin - radius < prefix.xmin or bounds.xmax + radius > prefix.xmax
            or bounds.ymin - radius < bay.ymin or bounds.ymax + radius > bay.ymax
        ):
            raise RuntimeError("collar-side neck PDF: diameter vector contour escaped its complete glyph bay")
        start, end = (line.x0, line.y0), (line.x1, line.y1)
        edge = frozenset((start, end))
        if start == end or edge in edges:
            raise RuntimeError("collar-side neck PDF: degenerate/duplicate diameter vector contour")
        edges.add(edge)
        graph.setdefault(start, set()).add(end)
        graph.setdefault(end, set()).add(start)
    components = []
    remaining = set(graph)
    while remaining:
        pending = [next(iter(remaining))]
        nodes = set()
        while pending:
            point = pending.pop()
            if point not in nodes:
                nodes.add(point)
                pending.extend(graph[point] - nodes)
        remaining.difference_update(nodes)
        components.append(nodes)
    rings = [nodes for nodes in components if len(nodes) >= 3 and all(len(graph[p]) == 2 for p in nodes)]
    slashes = [
        nodes for nodes in components
        if sum(len(graph[p]) == 1 for p in nodes) == 2 and all(len(graph[p]) in (1, 2) for p in nodes)
    ]
    if len(components) != 2 or len(rings) != 1 or len(slashes) != 1:
        raise RuntimeError("collar-side neck PDF: missing/open/extra diameter ring or slash")
    ring = [line for line, _ in paths if (line.x0, line.y0) in rings[0]]
    slash = [line for line, _ in paths if (line.x0, line.y0) in slashes[0]]
    crossings = []
    for first in ring:
        for second in slash:
            point = _segment_crossing(first, second)
            if point is not None and not any(
                math.dist(point, prior) <= NECK_GEOMETRY_TOLERANCE_M for prior in crossings
            ):
                crossings.append(point)
    if len(crossings) != 2:
        raise RuntimeError("collar-side neck PDF: diameter slash does not cross the complete ring twice")
    return paths


def _neck_pdf_head_clearance(
    native: tuple[Segment, ...], owned: dict[Segment, tuple[tuple[Segment, float], ...]],
    boxes: tuple[InkBox, ...], paths: tuple[tuple[Segment, float], ...],
) -> float:
    distances = []
    for offset in range(0, len(native), 3):
        group = native[offset:offset + 3]
        painted = tuple(stroke for edge in group for stroke in owned[edge])
        points = tuple(point for line, _ in painted for point in ((line.x0, line.y0), (line.x1, line.y1)))
        vertices = tuple(min(points, key=lambda point: math.dist(point, (edge.x0, edge.y0))) for edge in group)

        def inside(point: tuple[float, float]) -> bool:
            turns = [
                (second[0] - first[0]) * (point[1] - first[1])
                - (second[1] - first[1]) * (point[0] - first[0])
                for first, second in zip(vertices, (*vertices[1:], vertices[0]))
            ]
            return min(turns) >= 0.0 or max(turns) <= 0.0

        # A glyph entirely inside a filled triangle never crosses its boundary.
        # Treat the whole native triangle as paint even for an open arrow style.
        if any(inside(point) for box in boxes for point in (
            (box.xmin, box.ymin), (box.xmin, box.ymax), (box.xmax, box.ymin), (box.xmax, box.ymax),
        )) or any(inside(point) for line, _ in paths for point in ((line.x0, line.y0), (line.x1, line.y1))):
            return 0.0
        distances.extend(
            segment_box_distance(head, box) - pen for head, pen in painted for box in boxes
        )
        distances.extend(
            _neck_segment_distance(head, path) - pen - radius
            for head, pen in painted for path, radius in paths
        )
    return min(distances)


def _assert_neck_pdf_presentation(
    neck: tuple[tuple[Segment, ...], tuple[Segment, ...], tuple[dict[str, Any], ...], tuple[Segment, ...]],
    finish: tuple[
        tuple[Segment, ...], tuple[Segment, ...], tuple[dict[str, Any], ...], Segment, tuple[float, float],
    ],
) -> None:
    """Qualify the existing export using actual glyphs and vector Ø, not COM height."""
    pages = read_pdf_ink(OUTPUTS.pdf)
    if len(pages) != 1:
        raise RuntimeError("collar-side neck PDF: expected the one complete crankshaft sheet")
    page = pages[0]
    page_width, page_height = _neck_numbers([page.width, page.height], 2, label="actual PDF page")
    if page_width <= 0.0 or page_height <= 0.0:
        raise RuntimeError("collar-side neck PDF: invalid actual page dimensions")
    lines, heads, texts, foreign_lines = neck
    finish_lines, finish_heads, finish_texts, leader, native_root = finish
    spans = [InkSpan(ink_key(span.text), InkBox(span.xmin, span.ymin, span.xmax, span.ymax)) for span in page.spans]
    rows = (*texts, *finish_texts)
    matches = match_ink_indices([
        (index, TextItem(row["text"], *row["position"][:2], row["height"], row["angle"], row["reference"]))
        for index, row in enumerate(rows)
    ], spans)
    glyphs = {}
    for index, row in enumerate(rows):
        if row["text"].strip() == "<MOD-DIAM>":
            continue
        indices = matches.get(index, ())
        actual = tuple(glyph for number in indices for glyph in page.spans[number].glyphs)
        # SOLIDWORKS's plus-minus may print as a glyph or as a path.
        if not actual or ink_key("".join(glyph.char for glyph in actual)).replace(
            "\N{PLUS-MINUS SIGN}", ""
        ) != ink_key(row["text"]).replace("\N{PLUS-MINUS SIGN}", ""):
            raise RuntimeError("collar-side neck PDF: complete native numeric/roughness glyph owner is missing")
        boxes = []
        for glyph in actual:
            coordinates = _neck_numbers(
                [glyph.xmin, glyph.ymin, glyph.xmax, glyph.ymax], 4, label="actual PDF glyph",
            )
            box = InkBox(*coordinates)
            if box.width <= 0.0 or box.height <= 0.0:
                raise RuntimeError("collar-side neck PDF: malformed actual glyph bounds")
            if box.xmin < row["advance"].xmin or box.xmax > row["advance"].xmax:
                raise RuntimeError("collar-side neck PDF: numeric/roughness glyph belongs to another native advance")
            boxes.append(box)
        glyphs[index] = tuple(boxes)
    shelf = next(line.y0 for line in lines if line.y0 == line.y1)
    roof = _sheet_y(JOURNAL_DIA / 2.0)
    right = min(
        line.x0 for line in foreign_lines if line.x0 == line.x1
        and line.x0 > OUTBOARD_NECK_DIAMETER_XY[0] and min(line.y0, line.y1) <= roof <= max(line.y0, line.y1)
    )
    bay = InkBox(OUTBOARD_NECK_DIAMETER_XY[0], shelf, right, NECK_PDF_GLYPH_BAY_TOP_M)
    numeric_boxes = tuple(box for index in range(len(texts)) for box in glyphs.get(index, ()))
    finish_boxes = tuple(box for index in range(len(texts), len(rows)) for box in glyphs[index])
    if bay.xmin < 0.0 or bay.ymin < 0.0 or bay.xmax > page_width or bay.ymax > page_height:
        raise RuntimeError("collar-side neck PDF: complete glyph bay escapes the actual page")
    for box in numeric_boxes:
        if box.xmin < bay.xmin or box.xmax > bay.xmax or box.ymin < bay.ymin or box.ymax > bay.ymax:
            raise RuntimeError("collar-side neck PDF: complete numeric glyph escaped the RIGHT glyph bay")
    strokes = []
    token_strokes = []
    for stroke in page.strokes:
        # PDF clip paths and dashed centre lines are not owned annotation ink.
        # Filter before reading their geometry/width, not as a whole-page error.
        if (
            stroke.rgb != (0, 0, 0)
            or type(stroke.stroked) is not bool or type(stroke.filled) is not bool
            or type(stroke.dashed) is not bool or stroke.dashed
            or not (stroke.stroked or stroke.filled)
        ):
            continue
        values = _neck_numbers(
            [stroke.x0, stroke.y0, stroke.x1, stroke.y1, stroke.width], 5, label="actual PDF stroke",
        )
        if values[4] < 0.0:
            raise RuntimeError("collar-side neck PDF: malformed actual stroke width/style")
        segment = Segment(*values[:4])
        if segment.length == 0.0:
            continue
        radius = values[4] / 2.0 if stroke.stroked else 0.0
        strokes.append((segment, radius))
        if stroke.stroked and not stroke.filled:
            if values[4] <= 0.0:
                raise RuntimeError("collar-side neck PDF: unreadable actual stroked diameter width")
            token_strokes.append((segment, radius))
    actual_neck = _neck_pdf_owned_lines(tuple(strokes), lines, label="collar-side neck PDF")
    actual_finish = _neck_pdf_owned_lines(tuple(strokes), finish_lines, label="collar rear finish PDF")
    actual_heads = _neck_pdf_owned_heads(tuple(strokes), finish_heads, label="collar rear finish PDF head")
    actual_neck_heads = _neck_pdf_owned_heads(tuple(strokes), heads, label="collar-side neck PDF head")
    actual_foreign = _neck_pdf_owned_lines(tuple(strokes), foreign_lines, label="preexisting dimension PDF")
    owned_lines = (*lines, *finish_lines, *heads, *finish_heads, *foreign_lines)
    unowned = tuple(
        stroke for stroke in token_strokes
        if not any(_neck_pdf_line_overlap(stroke[0], line) is not None for line in owned_lines)
    )
    diameter = _neck_pdf_diameter_paths(unowned, texts[0]["advance"], bay)
    clearance = min(
        _neck_pdf_head_clearance(finish_heads, actual_heads, numeric_boxes, diameter),
        _neck_pdf_head_clearance(heads, actual_neck_heads, finish_boxes, ()),
    )
    if clearance < ARROW_TEXT_CLEARANCE_M:
        raise RuntimeError(f"collar-side neck PDF: complete actual head-to-glyph clearance below 2 mm ({clearance})")
    root = min(
        (point for line, _ in actual_finish[leader] for point in ((line.x0, line.y0), (line.x1, line.y1))),
        key=lambda point: math.dist(point, native_root),
    )
    for line, _ in actual_finish[leader]:
        for native, group in actual_finish.items():
            if native == leader:
                continue
            for bar, _ in group:
                crossing = _neck_crossing(line, bar)
                if crossing is not None and not _neck_root_point_contact(line, bar, root):
                    raise RuntimeError("collar rear finish PDF: straight route crosses its own legs")
    for group in (*actual_finish.values(), *actual_neck.values()):
        for line, pen in group:
            for other_group in actual_foreign.values():
                if any(_neck_segment_distance(line, other) <= pen + width for other, width in other_group):
                    raise RuntimeError("collar-side neck PDF: actual annotation route intersects a preexisting dimension")
    finish_routes = tuple(stroke for group in actual_finish.values() for stroke in group)
    neck_routes = tuple(stroke for group in actual_neck.values() for stroke in group)
    finish_head_paint = tuple(stroke for group in actual_heads.values() for stroke in group)
    neck_head_paint = tuple(stroke for group in actual_neck_heads.values() for stroke in group)
    if (
        any(
            _neck_segment_distance(line, other) <= pen + width
            for line, pen in finish_routes for other, width in neck_routes
        )
        or _neck_pdf_head_clearance(finish_heads, actual_heads, (), (*neck_routes, *neck_head_paint)) <= 0.0
        or _neck_pdf_head_clearance(heads, actual_neck_heads, (), (*finish_routes, *finish_head_paint)) <= 0.0
    ):
        raise RuntimeError("collar-side neck PDF: actual finish and neck primitives intersect")
    for group in actual_finish.values():
        for line, pen in group:
            if (
                any(segment_box_distance(line, box) <= pen for box in numeric_boxes)
                or any(_neck_segment_distance(line, path) <= pen + width for path, width in diameter)
            ):
                raise RuntimeError("collar rear finish PDF: actual route intersects diameter glyph ink")
    _telemetry.info(
        f"collar-side neck (after_pdf_save): actual_PDF_numeric_glyphs_m={numeric_boxes}, "
        f"actual_PDF_diameter_paths_m={diameter}, actual_PDF_roughness_glyphs_m={finish_boxes}, "
        f"actual_full_head_to_glyph_clearance_mm={clearance * 1000.0}, glyph_bay_m={bay}"
    )


def _outboard_neck_checkpoint(
    adapter: Any, side: Any, identity: Any, right_driven_state: int,
    preexisting: tuple[tuple[Any, str, float, int, Any], ...],
    collar_rear_face: Any, collar_rear_symbol: Any, phase: str,
) -> None:
    """Prove both annotations at existing rebuild/save boundaries without reopening."""
    if phase in (
        "after insertion rebuild",
        "final settling rebuild",
        "after_drawing_save",
        "after_pdf_save",
    ):
        neck = _assert_outboard_neck_dimension(
            adapter, side, identity, right_driven_state, preexisting, phase=phase
        )
        finish = _assert_collar_rear_finish(
            adapter, collar_rear_face, collar_rear_symbol, neck, phase=phase,
        )
        if phase == "after_pdf_save":
            _assert_neck_pdf_presentation(neck, finish)


def _centres_note_field() -> Box:
    """Text below the pictorial caption, right of FRONT's station witnesses."""
    return (
        FAR_END_X + NOTE_TEXT_GAP,
        0.068,
        0.4181,
        ISO_NOTE_XY[1] - 2.0 * 0.005 - NOTE_TEXT_GAP,  # both caption rows
    )


def _add_centres_note(adapter: Any, drawing_model: Any, side: Any) -> Any:
    """Flag the FRONT plain end where a lathe centre hole may go."""
    label = "lathe centre hole end"
    # An edge-on rim can miss coordinate hit-testing. Use the same exact-edge
    # selection + pre-insertion landing pattern as add_toothspace_callout.
    rim = _far_end_rim(adapter, side)
    _select_view_entity(adapter, side, "EDGE", None, label=label, entity=rim)
    selection = _early_bound(drawing_model.SelectionManager, "ISelectionMgr")
    x, y = FAR_END_FRONT_RIM_PICK
    if selection.SetSelectionPoint2(1, -1, x, y, 0.0) is not True:
        raise RuntimeError(f"{label}: failed to set the FRONT plain-end landing")
    note = drawing_model.InsertNote(CENTRES_NOTE)
    if note is None:
        raise RuntimeError(f"{label}: failed to insert the note")
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
        raise RuntimeError(f"{label}: failed to create the leader")
    if not annotation.SetPosition2(*CENTRES_NOTE_XY, 0.0):
        raise RuntimeError(f"{label}: failed to position the note")
    rebuild_drawing(adapter, label=label)
    _place_note_text_in_field(
        drawing_model,
        note,
        _centres_note_field(),
        hole=FAR_END_FRONT_RIM_WINDOW,
        label=label,
    )
    _assert_attached_to(
        adapter, annotation, rim, entity_type="EDGE", what="attached note", label=label
    )
    drawing_model.ClearSelection2(True)
    return note


def _visible_cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the requested modeled OD face in the crankshaft side view."""
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        faces = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 3
                ),  # swViewEntityType_Face
                default=(),
            )
            or ()
        )
        for face in faces:
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            parameters = surface.CylinderParams
            if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                continue
            candidates.append((float(face.GetArea()), face))
    if not candidates:
        raise RuntimeError(
            f"crankshaft side view has no visible cylindrical face at "
            f"radius {expected_radius_m:g} m"
        )
    return max(candidates, key=lambda candidate: candidate[0])[1]


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a native model dimension and verify its new drawing-view owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
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
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
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


def _set_spherical_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Print a model radius as the ASME spherical reference ``(SR6.7)``.

    The radius is read-only: a spherical cap of the printed dome height on the
    toleranced end diameter already fixes it.  Whatever radius prefix the
    display carries is kept behind the ``(S``; the readback proves it stuck.
    """
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    prefix = "(S" + existing
    display.SetText(1, prefix)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    _telemetry.info(
        f"{label}: spherical reference prefix {existing!r} -> {applied[0]!r}, "
        f"suffix {applied[1]!r}"
    )
    if applied != (prefix, ")"):
        raise RuntimeError(f"failed to mark {label} as a spherical reference: {applied}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crankshaft source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
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
            "Pinion Pin Hole Process",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Pinion Pin Hole Process",
        ),
    )
    # The note prints the property's words re-wrapped; a part built from a
    # different process text must not be printed with this one.
    pinion_process = properties["Pinion Pin Hole Process"].replace("\r", "")
    if pinion_process != CRANKSHAFT_PIN_HOLE_PROCESS:
        raise RuntimeError(
            f"crankshaft Pinion Pin Hole Process {pinion_process!r} != "
            f"crank_pinion_spec {CRANKSHAFT_PIN_HOLE_PROCESS!r}"
        )
    # Inch sheet (#290).  The drive-pin holes are a cut, not a Hole Wizard
    # feature, so their native callout prints at the document's places: the
    # sheet opens at HOLE_CALLOUT_PLACES, and every Hole Wizard callout is set
    # back to the title block's three below.
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        decimals=HOLE_CALLOUT_PLACES,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crankshaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crankshaft; domed nose; hub taper pin; punched fiducial",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    native_side = _early_bound(side, "IView")
    _initialize_neck_true_measurements(native_side)
    native_side.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(native_side.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to lay the crankshaft profile horizontal")
    drawing_model.EditRebuild3()
    _assert_neck_measurement_domain(native_side, label="crankshaft SIDE after angle rebuild")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="crank-end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    moved = [
        _move_dimension(
            adapter,
            annotation,
            side,
            DIAMETER_POSITIONS[dimension_name(adapter, annotation)],
            source_view=end,
        )
        for annotation in end_annotations
        if dimension_name(adapter, annotation) in END_DIAMETERS
    ]
    end_kept = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) in END_PIN_KEEP
    ]
    if len(end_kept) != len(END_PIN_KEEP):
        raise RuntimeError("the end view lost a drive-pin hole location dimension")
    annotations = [*moved, *end_kept, *side_annotations]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    _set_dimension_suffixes(adapter, annotations, SUFFIXES)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one crankshaft {name} reference dimension")
        if name in SPHERICAL_DIMENSIONS:
            _set_spherical_reference(adapter, matches[0], label=f"crankshaft {name}")
            continue
        set_reference_dimension(adapter, matches[0], label=f"crankshaft {name}")

    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; the end view gets the
    # ASME centre mark, the side view marks the cross-hole circle.
    for view, label in ((end, "end"), (side, "side")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    add_view_centerline(
        adapter,
        side,
        label="crankshaft turning axis",
        face=_visible_cylindrical_face(adapter, side, SHAFT_DIA),
    )

    cross_hole = add_native_hole_callout(
        adapter,
        side,
        callout_xy=HOLE_CALLOUT_XY,
        label="tapered-pin cross-hole",
        edge=_visible_cross_hole_edge(adapter, side, _PIN_HOLE_DIA),
        process=CROSS_HOLE_PROCESS,
    )
    _set_callout_text(cross_hole, 4, CROSS_HOLE_CALLOUT, "tapered-pin cross-hole")
    set_hole_callout_precision(
        cross_hole, WIZARD_CALLOUT_PRECISION, label="tapered-pin cross-hole"
    )
    drive_pins = add_native_hole_callout(
        adapter,
        end,
        callout_xy=DRIVE_PIN_CALLOUT_XY,
        label="seat-collar drive-pin holes",
        edge=_visible_cross_hole_edge(
            adapter,
            end,
            DRIVE_PIN_HOLE_DIA,
            view_label="end",
            accept=_is_upper_seat_rim,
        ),
        process=f"2X {DRIVE_PIN_HOLE_PROCESS}",
    )
    _drop_coaxial_step(drive_pins, DRIVE_PIN_KNOCKOUT_DIA, "seat-collar drive-pin holes")
    _band_hole_depth(
        drive_pins,
        DRIVE_PIN_DEPTH_BAND,
        drawing_model,
        "seat-collar drive-pin holes",
    )
    _set_callout_text(drive_pins, 4, DRIVE_PIN_CALLOUT, "seat-collar drive-pin holes")
    place_callout_clear(
        adapter,
        _early_bound(drive_pins, "IDisplayDimension").GetAnnotation(),
        label="seat-collar drive-pin holes",
        below={},
        beside={},
    )
    knockouts = add_native_hole_callout(
        adapter,
        end,
        callout_xy=KNOCKOUT_CALLOUT_XY,
        label="drive-pin knockout holes",
        edge=_visible_cross_hole_edge(
            adapter,
            end,
            DRIVE_PIN_KNOCKOUT_DIA,
            view_label="end",
            accept=_is_lower_knockout_floor,
        ),
    )
    _drop_coaxial_step(knockouts, DRIVE_PIN_HOLE_DIA, "drive-pin knockout holes")
    _set_callout_text(knockouts, 3, KNOCKOUT_CALLOUT_ABOVE, "drive-pin knockout holes")
    _set_callout_text(knockouts, 4, KNOCKOUT_CALLOUT_BELOW, "drive-pin knockout holes")
    set_hole_callout_precision(
        knockouts, WIZARD_CALLOUT_PRECISION, label="drive-pin knockout holes"
    )
    add_attached_note(
        adapter,
        end,
        text=FIDUCIAL_NOTE,
        entity=_visible_cross_hole_edge(
            adapter, end, FIDUCIAL_MODEL_DIA, view_label="end"
        ),
        note_xy=FIDUCIAL_NOTE_XY,
        label="dome punch mark",
    )
    pinion_note = add_attached_note(
        adapter,
        side,
        text=CRANKSHAFT_PIN_HOLE_PROCESS,
        entity=_visible_cross_hole_edge(adapter, side, PINION_PIN_DIA),
        note_xy=PINION_PIN_NOTE_XY,
        label="16T retention-pin transfer",
    )
    _place_note_text_in_field(
        drawing_model,
        pinion_note,
        PINION_PIN_NOTE_FIELD,
        hole=PINION_PIN_HOLE_WINDOW,
        label="16T retention-pin transfer",
    )
    _add_centres_note(adapter, drawing_model, side)
    add_surface_finish(
        adapter,
        side,
        edge_xy=JOURNAL_FINISHES["outboard_journal"][0],
        symbol_xy=JOURNAL_FINISHES["outboard_journal"][1],
        control=surface_finish_by_key(SURFACE_FINISHES, "outboard_journal"),
        label="crankshaft outboard journal finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=JOURNAL_FINISHES["inboard_journal"][0],
        symbol_xy=JOURNAL_FINISHES["inboard_journal"][1],
        control=surface_finish_by_key(SURFACE_FINISHES, "inboard_journal"),
        label="crankshaft inboard journal finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    collar_rear_face = _collar_rear_face(_collar_rear_rim(adapter, side))
    collar_rear_symbol = add_surface_finish(
        adapter,
        side,
        entity=collar_rear_face,
        entity_type="FACE",
        leader_attach_xy=COLLAR_REAR_FINISH[0],
        symbol_xy=COLLAR_REAR_FINISH[1],
        control=surface_finish_by_key(SURFACE_FINISHES, "collar_rear_face"),
        label="crankshaft collar rear (post boss) face finish",
        char_height=0.0025,
    )
    if collar_rear_symbol is None:
        raise RuntimeError("crankshaft collar rear finish: missing captured native symbol")
    collar_rear_annotation = _early_bound(collar_rear_symbol, "ISFSymbol").GetAnnotation()
    if collar_rear_annotation is None:
        raise RuntimeError("crankshaft collar rear finish: missing captured native annotation")
    # This one symbol needs a straight native route; keep the shared finish
    # factory's default, the symbol origin, and the exact physical tip intact.
    # A smart arrowhead on a FACE attachment prints a dot (swDOT_ARROWHEAD,
    # farm run 20261023T182235406Z); the edge-on face line takes the filled
    # arrow it carried when attached to the rim.
    collar_rear_annotation = _early_bound(collar_rear_annotation, "IAnnotation")
    status = collar_rear_annotation.SetLeader3(1, 0, False, False, False, False)
    if type(status) is not int or status != 0:
        raise RuntimeError(f"crankshaft collar rear finish: SetLeader3 failed ({status!r})")
    status = collar_rear_annotation.SetArrowHeadStyleAtIndex(0, 1)  # swCLOSED_ARROWHEAD
    if type(status) is not int or status != 0:
        raise RuntimeError(
            f"crankshaft collar rear finish: SetArrowHeadStyleAtIndex failed ({status!r})"
        )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # The end view prints hidden lines removed with the rest (drawing-guidelines.md
    # rule 9 (show internal shape in solid lines)): the punch mark is flagged by
    # its own leader, so no dashed cross-hole is needed to clock it.

    (
        outboard_neck_dimension, right_neck_driven_state, preexisting_side_dimensions,
    ) = _add_outboard_neck_dimension(
        adapter, drawing_model, side, collar_rear_face, collar_rear_symbol,
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crankshaft Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _outboard_neck_checkpoint(
                adapter, side, outboard_neck_dimension, right_neck_driven_state,
                preexisting_side_dimensions, collar_rear_face, collar_rear_symbol,
                "final settling rebuild",
            ),
        ),
        checkpoint=lambda phase: _outboard_neck_checkpoint(
            adapter, side, outboard_neck_dimension, right_neck_driven_state,
            preexisting_side_dimensions, collar_rear_face, collar_rear_symbol, phase
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
