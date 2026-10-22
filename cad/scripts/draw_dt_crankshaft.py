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
import json
import math
import sys
from typing import Any, Callable, Sequence

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    _SW_LENGTH_MM,
    _SW_PREF_UNITS_LINEAR,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
    visible_component_entities,
)

from _check import check
from _com import _com_invoke, _early_bound
from _drawing_annotation_extent import place_callout_clear
from _drawing_attachment import _assert_attached_to, _is_same_attachment
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
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import _project_through
from _drawing_selection import _select_view_entity
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from build_dt_crankshaft import PINION_PIN_DIA, PINION_PIN_STATION_Y
from dt_crank_pinion_spec import CRANKSHAFT_PIN_HOLE_PROCESS
from dt_crankshaft_notes import (
    CENTRES_NOTE,
    CHAIN_AIR_MATE,
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
    JOURNAL_DIA,
    JOURNAL_END,
    JOURNAL_START,
    NECK_DIA_PLACES,
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
# Ø20.6 (one place, no band) drops under the Ø17.50's landing line, and the
# Ø11.388 stands 4 mm right of the Ø17.50's block (layout audit of
# 902433a8d: 2.3 mm read as one callout), its landing line 2 mm over the
# outboard journal's finish symbol and its fit row 7 mm under the cross-hole
# callout's landing line; the relief's Ø10.4 stands right of it.
# The existing loose Ø9.5 remains on the inboard neck, over the Ø9.000's
# block. A separate measured diameter identifies the collar-side neck.
# The Ø9.000's line stays 2 mm past its step, clear of the retention-pin note.
DIAMETER_POSITIONS = {
    "ShaftDiaDim": (PIN_X - 0.016, 0.2195),
    "JournalDiaDim": (RELIEF_START_X - 0.0069, 0.224),
    "ReliefDiaDim": (RELIEF_START_X + 0.045, 0.212),
    "PinionSeatDiaDim": (SEAT_STEP_X + 0.002, 0.2125),
    "SpigotDiaDim": (COLLAR_SEAT_X + 0.0075, 0.2215),
    "CollarDiaDim": (SPIGOT_END_X + 0.002, 0.2065),
    "NeckDiaDim": (JOURNAL_END_X + 0.0006, 0.230),
}
# Approach the short neck from below, between its two physical shoulders.
# This local bay is above the collar/journal outboard baseline rows and
# left of the shorter rows; it avoids the collar-rear Ra and fit blocks.
OUTBOARD_NECK_DIAMETER_XY = ((COLLAR_REAR_X + JOURNAL_START_X) / 2.0, 0.1515)
OUTBOARD_NECK_ARROW_WINDOW = (
    COLLAR_REAR_X, _sheet_y(-SHAFT_DIA / 2.0),
    JOURNAL_START_X, _sheet_y(SHAFT_DIA / 2.0),
)
# Sheet-space display readback tolerance, not a model-size tolerance.
NECK_ARROW_LANDING_TOLERANCE_M = 1e-5  # 0.01 mm against a ~2.34 mm axial land
NECK_ARROW_DIRECTION_X_SLACK = 1e-6  # normalized-X roundoff near a vertical arrow
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
        (RELIEF_START_X - 0.003, 0.203),
    ),
    "inboard_journal": (
        (RELIEF_END_X + 0.015, JOURNAL_FLANK_Y),
        (RELIEF_END_X + 0.012, 0.200),
    ),
}
# The landing on the rear face's edge-on line at the collar's silhouette: the
# rim itself is selected as a model edge (_collar_rear_rim), and SolidWorks
# lands a point on an edge-on circle at its projected extreme, not 1 mm
# inside it (run 20261001T051043622Z: requested y 0.1986, landed 0.2006).
COLLAR_REAR_FINISH = (
    (COLLAR_REAR_X, _sheet_y(COLLAR_DIA / 2.0)),
    (COLLAR_REAR_X + 0.0069, 0.195),
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
    marker = f"<MOD-DIAM>{step_dia:.2f}"
    definitions = {
        part: str(display.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE
    }
    holders = [part for part, text in definitions.items() if marker in text]
    for part in holders:
        if not definitions[part].startswith(marker):
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


def _require_mm_sheet(draw: Any, label: str) -> None:
    """Refuse unless the drawing's linear unit is the millimetre.

    The depth band is typed text in mm: SolidWorks re-renders the callout's
    native depth in the sheet's units but never the text after it, so the
    band is only true on a mm sheet.  The callout has no native route for it:
    ``GetHoleCalloutVariables`` raised DISP_E_BADVARTYPE on this cut-extrude
    callout on the farm (run 20261003T001156794Z); every repo caller it works
    for is a Hole Wizard feature.  Reads the document preference
    ``set_units_mm`` writes (``IModelDoc2::GetUserPreferenceIntegerValue``).
    """
    doc = _early_bound(draw, "IModelDoc2")
    unit = doc.GetUserPreferenceIntegerValue(_SW_PREF_UNITS_LINEAR)
    if type(unit) is not int or unit != _SW_LENGTH_MM:
        raise RuntimeError(
            f"{label}: the typed depth band is mm, but the sheet's linear unit"
            f" is {unit!r} (swLengthUnit_e; swMM = {_SW_LENGTH_MM})"
        )


def _band_hole_depth(display: Any, band: str, draw: Any, label: str) -> None:
    """Print the part's depth band after the native callout's depth.

    The cut's depth carries the band in the part, but the callout prints the
    depth bare; the band joins the format text of the part holding the depth,
    where the native size and depth stay associative.  Read back like the
    prose.  The callout-below compartment is rewritten by the matched-fit
    prose afterwards, so a depth there is refused rather than lost.  The band
    is mm text, so the sheet must be mm (``_require_mm_sheet``).
    """
    _require_mm_sheet(draw, label)
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


def _outboard_neck_failure_census(
    adapter: Any, view: Any, *, strict_visible_matches: int
) -> None:
    """Temporary, read-only failure probe; never supplies a resolver candidate.

    Keep native duplicates as separate occurrences. Geometry signatures only
    shortlist IsSame calls, never establish identity or relax the real picker.
    Raw invocation avoids generated-wrapper type-info/QI work on every field.
    """
    marker = "NECK_GEOMETRY_CENSUS_JSON="
    report: dict[str, Any] = {
        "schema": 1,
        "marker": marker,
        "strict_visible_matches": strict_visible_matches,
        "units": {
            "native_lengths": "m", "sheet_coordinates": "m",
            "view_angle": "rad", "axes": "unitless",
            "trim_parameters": "native curve parameters",
            "face_boxes": "approximate model-space m; not identity evidence",
        },
        "expected": {
            "source_path": str(SOURCE),
            "collar_rear_mm": COLLAR_REAR,
            "journal_start_mm": JOURNAL_START,
            "neck_length_mm": JOURNAL_START - COLLAR_REAR,
            "shaft_diameter_mm": SHAFT_DIA,
            "journal_diameter_mm": JOURNAL_DIA,
            "circle_center_m": [0.0, JOURNAL_START / 1000.0, 0.0],
            "circle_axis": [0.0, 1.0, 0.0],
            "circle_radius_m": SHAFT_DIA / 2000.0,
            "position_radius_strict_tolerance_m": 1e-6,
            "axis_strict_tolerance": 1e-9,
        },
        "body_enumeration": "GetBodies2(-1, False): all solid/sheet bodies, including hidden",
        "signature_round_decimals_for_shortlisting_only": 12,
        "bodies": [], "faces": [], "circles": [], "visible_components": [],
        "projections": [],
    }
    error_count = 0

    def primitive(value: Any, depth: int = 0) -> Any:
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else {"nonfinite": repr(value)}
        if isinstance(value, (tuple, list)) and depth < 3:
            return [primitive(item, depth + 1) for item in value]
        raise TypeError(f"non-primitive diagnostic value: {type(value).__name__}")

    def read_field(
        row: dict[str, Any], key: str, operation: Callable[[], Any],
        encode: Callable[[Any], Any] = primitive,
    ) -> Any:
        nonlocal error_count
        try:
            value = operation()
            row[key] = {"value": encode(value), "error": None}
            return value
        except Exception as exc:
            error_count += 1
            row[key] = {
                "value": None,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
            return None

    def invoke(obj: Any, interface: str, member: str, *args: Any) -> Any:
        if obj is None:
            raise RuntimeError(f"{interface}.{member}: parent interface is null/unreadable")
        return _com_invoke(obj, interface, member, *args)

    def presence(value: Any) -> Any:
        return None if value is None else "present"

    def handles(value: Any) -> Any:
        return None if value is None else {
            "count": len(value),
            "null_indices": [index for index, item in enumerate(value) if item is None],
        }

    def numbers(value: Any) -> Any:
        return None if value is None else tuple(float(item) for item in value)

    def unavailable(reason: str) -> Any:
        raise RuntimeError(reason)

    point_cache: dict[tuple[float, ...], int] = {}

    def point(row: dict[str, Any], name: str, xyz: Any) -> None:
        def register() -> int:
            values = numbers(xyz)
            if values is None or len(values) != 3 or not all(map(math.isfinite, values)):
                raise ValueError(f"{name}: no readable finite model-space XYZ")
            if values not in point_cache:
                point_cache[values] = len(report["projections"])
                report["projections"].append({"model_m": list(values)})
            return point_cache[values]

        read_field(row.setdefault("projection_refs", {}), name, register)

    circle_cache: dict[tuple[float, ...], int] = {}

    def circle_record(params: Any, is_circle: Any) -> int:
        valid = params is not None and len(params) == 7 and all(map(math.isfinite, params))
        key = tuple(params) if valid else None
        if key is not None and key in circle_cache:
            return circle_cache[key]
        row: dict[str, Any] = {
            "id": len(report["circles"]), "raw_circle_params": primitive(params),
            "predicates": {
                "is_circle": is_circle,
                "parameter_count_is_seven": None if params is None else len(params) == 7,
                "all_parameters_finite": None if params is None else all(map(math.isfinite, params)),
            },
        }
        for name, index, expected, tolerance, absolute_axis in (
            ("center_x", 0, 0.0, 1e-6, False),
            ("center_z", 2, 0.0, 1e-6, False),
            ("station_y", 1, JOURNAL_START / 1000.0, 1e-6, False),
            ("radius", 6, SHAFT_DIA / 2000.0, 1e-6, False),
            ("axis_x", 3, 0.0, 1e-9, False),
            ("axis_z", 5, 0.0, 1e-9, False),
            ("absolute_axis_y", 4, 1.0, 1e-9, True),
        ):
            delta = None
            if valid:
                actual = abs(params[index]) if absolute_axis else params[index]
                delta = actual - expected
            row["predicates"][name] = {
                "delta": delta, "absolute_delta": None if delta is None else abs(delta),
                "strict_tolerance": tolerance,
                "passes": None if delta is None else abs(delta) < tolerance,
            }
        row["matches_resolver"] = bool(
            is_circle is True and valid
            and all(
                row["predicates"][name]["passes"] is True
                for name in (
                    "center_x", "center_z", "station_y", "radius",
                    "axis_x", "axis_z", "absolute_axis_y",
                )
            )
        )
        point(row, "center", params[:3] if params is not None and len(params) >= 3 else None)
        # Extrema of the supporting circle in each model coordinate, not a
        # claim that an arc's trim contains them. FRONT's Z extrema show its span.
        normal = None
        if valid:
            length = math.hypot(*params[3:6])
            if length > 0.0:
                normal = tuple(value / length for value in params[3:6])
        for index, axis in enumerate("xyz"):
            direction = None
            if normal is not None:
                radial = tuple(
                    (1.0 if index == coordinate else 0.0) - normal[index] * normal[coordinate]
                    for coordinate in range(3)
                )
                length = math.hypot(*radial)
                if length > 0.0:
                    direction = tuple(value / length for value in radial)
            for sign, suffix in ((-1.0, "min"), (1.0, "max")):
                name = f"supporting_circle_model_{axis}_{suffix}"
                if direction is None:
                    read_field(
                        row.setdefault("projection_refs", {}), name,
                        lambda: unavailable("unreadable circle/axis or degenerate radial extremum"),
                    )
                else:
                    point(row, name, tuple(
                        params[coordinate] + sign * params[6] * direction[coordinate]
                        for coordinate in range(3)
                    ))
        report["circles"].append(row)
        if key is not None:
            circle_cache[key] = row["id"]
        return row["id"]

    def curve_geometry(row: dict[str, Any], curve: Any) -> None:
        read_field(row, "curve_class", lambda: invoke(curve, "ICurve", "Identity"))
        circular = read_field(row, "is_circle", lambda: invoke(curve, "ICurve", "IsCircle"))
        linear = read_field(row, "is_line", lambda: invoke(curve, "ICurve", "IsLine"))
        params = read_field(
            row, "circle_params",
            lambda: numbers(invoke(curve, "ICurve", "CircleParams")) if circular is True
            else None if circular is False else unavailable("IsCircle unavailable"),
        )
        read_field(
            row, "line_params",
            lambda: numbers(invoke(curve, "ICurve", "LineParams")) if linear is True
            else None if linear is False else unavailable("IsLine unavailable"),
        )
        row["circle_id"] = circle_record(params, circular) if circular is True else None

    # Cache complete faces only after a native IsSame verdict. Approximate
    # bounds merely shortlist; every returned adjacency slot remains in the dump.
    face_candidates: dict[tuple[float, ...], list[tuple[Any, int]]] = {}

    def face_record(slot: dict[str, Any], face: Any) -> None:
        slot["face_present"] = face is not None
        slot["face_id"] = None
        if face is None:
            return
        bounds = read_field(slot, "box_m", lambda: numbers(invoke(face, "IFace2", "GetBox")))
        key = None
        if bounds is not None and len(bounds) == 6 and all(map(math.isfinite, bounds)):
            key = tuple(round(value, 12) for value in bounds)
        comparisons = slot["cache_identity_checks"] = []
        for prior, face_id in face_candidates.get(key, ()):
            comparison: dict[str, Any] = {"face_id": face_id}
            comparisons.append(comparison)
            same = read_field(
                comparison, "is_same_raw",
                lambda p=prior: invoke(adapter.swApp, "ISldWorks", "IsSame", face, p),
            )
            if type(same) is int and same == 1:
                slot["face_id"] = face_id
                return
        row: dict[str, Any] = {"id": len(report["faces"]), "box_m": slot["box_m"]}
        slot["face_id"] = row["id"]
        report["faces"].append(row)
        if key is not None:
            face_candidates.setdefault(key, []).append((face, row["id"]))
        read_field(row, "uv_bounds", lambda: numbers(invoke(face, "IFace2", "GetUVBounds")))
        read_field(row, "area_m2", lambda: invoke(face, "IFace2", "GetArea"))
        feature = read_field(
            row, "feature", lambda: invoke(face, "IFace2", "GetFeature"), presence,
        )
        read_field(row, "oldest_owning_feature_name", lambda: invoke(feature, "IFeature", "Name"))
        read_field(row, "feature_type", lambda: invoke(feature, "IFeature", "GetTypeName2"))
        surface = read_field(
            row, "surface", lambda: invoke(face, "IFace2", "GetSurface"), presence,
        )
        read_field(row, "surface_class", lambda: invoke(surface, "ISurface", "Identity"))
        cylinder = read_field(row, "is_cylinder", lambda: invoke(surface, "ISurface", "IsCylinder"))
        read_field(
            row, "cylinder_params",
            lambda: numbers(invoke(surface, "ISurface", "CylinderParams")) if cylinder is True
            else None if cylinder is False else unavailable("IsCylinder unavailable"),
        )

    def adjacent_faces(row: dict[str, Any], edge: Any) -> None:
        adjacent = read_field(
            row, "native_adjacent_faces",
            lambda: invoke(edge, "IEdge", "GetTwoAdjacentFaces2"), handles,
        )
        row["adjacent_faces"] = []
        for index, face in enumerate(adjacent or ()):
            slot: dict[str, Any] = {"slot": index}
            row["adjacent_faces"].append(slot)
            face_record(slot, face)

    def edge_geometry(edge: Any, identity: str) -> dict[str, Any]:
        row: dict[str, Any] = {"id": identity, "edge_present": edge is not None}
        curve = read_field(row, "curve", lambda: invoke(edge, "IEdge", "GetCurve"), presence)
        curve_geometry(row, curve)
        # GetCurve MUST precede GetCurveParams2. Packed final doubles are kept
        # raw (non-finite values are tagged), not decoded as guessed integers.
        trim = read_field(
            row, "trim_params",
            lambda: numbers(invoke(edge, "IEdge", "GetCurveParams2")),
        )
        row["trim_u"] = None if trim is None or len(trim) < 8 else primitive(trim[6:8])
        point(row, "trim_start", trim[:3] if trim is not None and len(trim) >= 6 else None)
        point(row, "trim_end", trim[3:6] if trim is not None and len(trim) >= 6 else None)
        for name, member in (("start", "GetStartVertex"), ("end", "GetEndVertex")):
            vertex = read_field(
                row, f"{name}_vertex", lambda m=member: invoke(edge, "IEdge", m), presence,
            )
            xyz = read_field(
                row, f"{name}_vertex_m", lambda v=vertex: numbers(invoke(v, "IVertex", "GetPoint")),
            )
            point(row, f"{name}_vertex", xyz)
        return row

    def signature(row: dict[str, Any]) -> Any:
        trim = row["trim_params"]["value"]
        if trim is None or len(trim) < 6 or not all(isinstance(v, (int, float)) for v in trim[:6]):
            return None
        ends = tuple(sorted(tuple(round(v, 12) for v in trim[start:start + 3]) for start in (0, 3)))
        params = row["circle_params"]["value"]
        circular = row["is_circle"]["value"]
        if circular is True:
            if params is None or len(params) != 7 or not all(isinstance(v, (int, float)) for v in params):
                return None
            # Opposite normal signs describe the same supporting circle.
            axis = params[3:6]
            sense = next((1.0 if v > 0.0 else -1.0 for v in axis if abs(v) > 1e-12), 1.0)
            geometry = tuple(round(v, 12) for v in (*params[:3], *(sense * v for v in axis), params[6]))
        else:
            geometry = None
        return row["curve_class"]["value"], circular, geometry, ends

    try:
        state: dict[str, Any] = {}
        report["front"] = state
        for key, member in (
            ("name", "GetName2"), ("orientation", "GetOrientationName"),
            ("angle_rad", "Angle"), ("scale_ratio", "ScaleRatio"),
            ("position_m", "Position"), ("display_state", "DisplayState"),
            ("display_mode", "GetDisplayMode2"),
            ("referenced_model_name", "GetReferencedModelName"),
            ("referenced_configuration", "ReferencedConfiguration"),
        ):
            read_field(state, key, lambda m=member: invoke(view, "IView", m))
        source: dict[str, Any] = {}
        report["referenced_source"] = source
        document = read_field(
            source, "document", lambda: _early_bound(view, "IView").ReferencedDocument, presence,
        )
        read_field(source, "path", lambda: invoke(document, "IModelDoc2", "GetPathName"))
        read_field(source, "title", lambda: invoke(document, "IModelDoc2", "GetTitle"))
        read_field(source, "document_type", lambda: invoke(document, "IModelDoc2", "GetType"))
        manager = read_field(
            source, "configuration_manager",
            lambda: invoke(document, "IModelDoc2", "ConfigurationManager"), presence,
        )
        configuration = read_field(
            source, "active_configuration",
            lambda: invoke(manager, "IConfigurationManager", "ActiveConfiguration"), presence,
        )
        read_field(source, "active_configuration_name", lambda: invoke(configuration, "IConfiguration", "Name"))
        utility = read_field(
            state, "math_utility",
            lambda: invoke(adapter.swApp, "ISldWorks", "GetMathUtility"), presence,
        )
        transform = read_field(
            state, "native_model_to_view_transform",
            lambda: invoke(view, "IView", "ModelToViewTransform"), presence,
        )
        read_field(
            state, "model_to_view_transform",
            lambda: numbers(invoke(transform, "IMathTransform", "ArrayData")),
        )
        expected_points: dict[str, Any] = {}
        report["expected_neck_boundary"] = expected_points
        for station_name, station in (("collar_rear", COLLAR_REAR), ("journal_start", JOURNAL_START)):
            for flank, z in (("axis", 0.0), ("lower", -SHAFT_DIA / 2000.0), ("upper", SHAFT_DIA / 2000.0)):
                point(expected_points, f"{station_name}_{flank}", (0.0, station / 1000.0, z))
        part = read_field(
            source, "part_interface", lambda: _early_bound(document, "IPartDoc"), presence,
        )
        bodies = read_field(
            source, "all_bodies",
            lambda: invoke(part, "IPartDoc", "GetBodies2", -1, False), handles,
        )
        body_index: dict[Any, list[tuple[Any, dict[str, Any]]]] = {}
        body_edges: list[dict[str, Any]] = []
        for body_index_number, body in enumerate(bodies or ()):
            body_row: dict[str, Any] = {"id": f"body/{body_index_number}", "edges": []}
            report["bodies"].append(body_row)
            read_field(body_row, "name", lambda b=body: invoke(b, "IBody2", "Name"))
            read_field(body_row, "visible", lambda b=body: invoke(b, "IBody2", "Visible"))
            read_field(body_row, "body_type", lambda b=body: invoke(b, "IBody2", "GetType"))
            read_field(body_row, "box_m", lambda b=body: numbers(invoke(b, "IBody2", "GetBodyBox")))
            edges = read_field(body_row, "native_edges", lambda b=body: invoke(b, "IBody2", "GetEdges"), handles)
            for index, edge in enumerate(edges or ()):
                row = edge_geometry(edge, f"{body_row['id']}/edge/{index}")
                body_row["edges"].append(row)
                body_edges.append(row)
                adjacent_faces(row, edge)
                key = signature(row)
                if key is not None:
                    body_index.setdefault(key, []).append((edge, row))
        # This scan is deliberately direct: unlike the picker, an accessor
        # exception must be distinguishable from a genuine null/empty result.
        components = read_field(
            state, "native_visible_components",
            lambda: invoke(view, "IView", "GetVisibleComponents"), handles,
        )
        visible_edges: list[dict[str, Any]] = []
        for component_index, component in enumerate(components or ()):
            component_row: dict[str, Any] = {
                "id": f"component/{component_index}", "edges": [], "silhouettes": [],
            }
            report["visible_components"].append(component_row)
            for key, member in (
                ("name", "Name2"), ("path", "GetPathName"),
                ("referenced_configuration", "ReferencedConfiguration"),
            ):
                read_field(component_row, key, lambda m=member, c=component: invoke(c, "IComponent2", m))
            for kind, field in ((1, "edges"), (4, "silhouettes")):
                entities = read_field(
                    component_row, f"native_kind_{kind}",
                    lambda k=kind, c=component: invoke(view, "IView", "GetVisibleEntities2", c, k),
                    handles,
                )
                for index, entity in enumerate(entities or ()):
                    identity = f"{component_row['id']}/kind/{kind}/{index}"
                    if kind == 1:
                        row = edge_geometry(entity, identity)
                        visible_edges.append(row)
                        component_row[field].append(row)
                        candidates = body_index.get(signature(row), ())
                        row["body_identity_shortlist_count"] = len(candidates)
                        row["body_identity_checks"] = []
                        row["same_body_edge_ids"] = []
                        for body_edge, body_row in candidates:
                            comparison = {"body_edge_id": body_row["id"]}
                            row["body_identity_checks"].append(comparison)
                            same = read_field(
                                comparison, "is_same_raw",
                                lambda b=body_edge, e=entity: invoke(adapter.swApp, "ISldWorks", "IsSame", e, b),
                            )
                            if type(same) is int and same == 1:
                                row["same_body_edge_ids"].append(body_row["id"])
                        if row["same_body_edge_ids"]:
                            row["adjacent_faces_from_body_edge_ids"] = list(row["same_body_edge_ids"])
                        else:
                            adjacent_faces(row, entity)
                    else:
                        row = {"id": identity, "silhouette_present": entity is not None}
                        component_row[field].append(row)
                        face = read_field(row, "owning_face", lambda e=entity: invoke(e, "ISilhouetteEdge", "GetFace"), presence)
                        face_record(row, face)
                        for name, member in (("start", "GetStartPoint"), ("end", "GetEndPoint")):
                            native_point = read_field(
                                row, f"{name}_point",
                                lambda e=entity, m=member: invoke(e, "ISilhouetteEdge", m), presence,
                            )
                            xyz = read_field(
                                row, f"{name}_model_m",
                                lambda p=native_point: numbers(invoke(p, "IMathPoint", "ArrayData")),
                            )
                            point(row, name, xyz)
        # One settled native projection frame for the complete batch, using
        # the shared helper per point so one bad read cannot erase other points.
        # Coordinate caching avoids reprojection of duplicate native geometry.
        for index, projection in enumerate(report["projections"]):
            read_field(
                projection, "sheet_m",
                lambda p=projection, i=index: _project_through(
                    utility, transform, p["model_m"],
                    label=f"collar-side neck census point {i}",
                ) if utility is not None and transform is not None
                else unavailable("native projection frame unavailable"),
            )
        for scope, rows in (("body", body_edges), ("visible", visible_edges)):
            report[f"{scope}_circle_match_ids"] = [
                row["id"] for row in rows
                if row["circle_id"] is not None
                and report["circles"][row["circle_id"]]["matches_resolver"]
            ]
            report[f"{scope}_circle_match_count"] = len(report[f"{scope}_circle_match_ids"])
            report[f"{scope}_edge_occurrences"] = len(rows)
    except Exception as exc:
        report["census_error"] = {"type": type(exc).__name__, "message": str(exc)}
    report["field_error_count"] = error_count
    _telemetry.info(marker + json.dumps(report, separators=(",", ":"), allow_nan=False))


def _outboard_neck_rim(adapter: Any, view: Any) -> Any:
    """Resolve the physical core rim where the collar-side neck meets the journal.

    The same-sized right neck and dome-root circle are not this feature.
    Select a true model circle visible edge-on in FRONT, never a projected
    shoulder line or a coordinate hit-test.
    """
    matches: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = visible_component_entities(view, component, 1) or ()  # edges
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(float(value) for value in (curve.CircleParams or ()))
            if len(params) != 7 or not all(math.isfinite(value) for value in params):
                raise RuntimeError(f"collar-side neck: unreadable circle parameters {params}")
            cx, cy, cz, ax, ay, az, radius = params
            if (
                abs(cx) < 1e-6
                and abs(cz) < 1e-6
                and abs(cy - JOURNAL_START / 1000.0) < 1e-6
                and abs(radius - SHAFT_DIA / 2000.0) < 1e-6
                and abs(ax) < 1e-9
                and abs(az) < 1e-9
                and abs(abs(ay) - 1.0) < 1e-9
            ):
                matches.append(edge)
    if len(matches) != 1:
        try:
            _outboard_neck_failure_census(
                adapter, view, strict_visible_matches=len(matches)
            )
        except Exception as exc:
            # Even a diagnostic/telemetry failure must leave the original
            # exact-one refusal authoritative.
            _telemetry.event(
                "drawing.neck_geometry_census_error",
                error_type=type(exc).__name__, error=str(exc),
            )
        raise RuntimeError(
            f"collar-side neck: FRONT shows {len(matches)} physical core rims at "
            f"journal start {JOURNAL_START}; expected exactly one"
        )
    return matches[0]


def _native_neck_view_dimensions(side: Any, *, label: str) -> list[tuple[Any, Any, Any]]:
    """Bind real view dimensions; a type-4 annotation without native data refuses."""
    dimensions = []
    for item in _early_bound(side, "IView").GetAnnotations() or ():
        annotation = _early_bound(item, "IAnnotation")
        if int(annotation.GetType()) != 4:  # swDisplayDimension
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


def _assert_plain_neck_size(
    display: Any, *, label: str, expected_driven_state: int
) -> float:
    """Prove a loose native size without rewriting the imported dimension."""
    native = display.GetDimension2(0)
    if native is None:
        raise RuntimeError(f"{label}: no native IDimension")
    dimension = _early_bound(native, "IDimension")
    if int(display.Type2) != 6:  # swDiameterDimension, not doubled linear (15)
        raise RuntimeError(f"{label}: native display is not a diameter")
    value = dimension.SystemValue
    if value is None:
        raise RuntimeError(f"{label}: no native measured value")
    measured_mm = float(value) * 1000.0
    if not math.isfinite(measured_mm) or abs(measured_mm - SHAFT_DIA) > 1e-5:
        raise RuntimeError(f"{label}: measures {measured_mm!r} mm, expected {SHAFT_DIA}")
    if type(dimension.DrivenState) is not int or dimension.DrivenState != expected_driven_state:
        raise RuntimeError(
            f"{label}: native driven state {dimension.DrivenState!r} "
            f"!= preserved/required state {expected_driven_state}"
        )
    places = display.GetPrimaryPrecision2()
    if places != NECK_DIA_PLACES:
        raise RuntimeError(f"{label}: primary places {places!r} != {NECK_DIA_PLACES}")
    tolerance = dimension.Tolerance
    if tolerance is None or int(_early_bound(tolerance, "IDimensionTolerance").Type) != 0:
        raise RuntimeError(f"{label}: unexpected explicit tolerance band")
    if display.GetOverride() is not False or display.ShowParenthesis is not False:
        raise RuntimeError(f"{label}: overridden or parenthesized value loses the general band")
    prefix = str(display.GetText(1) or "")
    prose = tuple(str(display.GetText(part) or "") for part in (2, 3, 4))
    if prefix not in ("", "<MOD-DIAM>") or any(prose):
        raise RuntimeError(f"{label}: unexpected native diameter text {prefix!r}, {prose!r}")
    return measured_mm


def _assert_neck_arrow_landing(display: Any, *, label: str) -> None:
    """Prove rendered diameter arrows identify the short neck, not the journal."""
    raw = display.GetDisplayData()
    if raw is None:
        raise RuntimeError(f"{label}: no native diameter display data")
    data = _early_bound(raw, "IDisplayData")
    count = data.GetArrowHeadCount()
    if type(count) is not int or count <= 0:
        raise RuntimeError(f"{label}: no readable native diameter arrowheads")
    arrows = []
    for index in range(count):
        values = tuple(float(value) for value in (data.GetArrowHeadAtIndex2(index) or ()))
        if len(values) != 12 or not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"{label}: malformed native arrowhead {index}: {values!r}")
        tip = values[0], values[1]
        tolerance = NECK_ARROW_LANDING_TOLERANCE_M
        x0, y0, x1, y1 = OUTBOARD_NECK_ARROW_WINDOW
        if not (
            x0 - tolerance <= tip[0] <= x1 + tolerance
            and y0 - tolerance <= tip[1] <= y1 + tolerance
        ):
            raise RuntimeError(f"{label}: diameter arrow {tip!r} does not identify the neck")
        # _layout_audit.arrowhead_segments records 125/125 calibrated PDF
        # arrows: the direction points from tip back to the arrow's base /
        # leader body. Positive sheet X therefore approaches from the journal.
        dx, dy = values[3:5]
        length = math.hypot(dx, dy)
        if not math.isfinite(length) or length == 0.0:
            raise RuntimeError(f"{label}: unreadable native arrow direction {values[3:6]!r}")
        direction = dx / length, dy / length
        if direction[0] > NECK_ARROW_DIRECTION_X_SLACK:
            raise RuntimeError(f"{label}: diameter arrow approaches from the journal side")
        arrows.append((tip, direction))
    _telemetry.info(f"{label}: native diameter arrows={arrows}, neck={OUTBOARD_NECK_ARROW_WINDOW}")


def _assert_outboard_neck_dimension(
    adapter: Any, side: Any, identity: Any, right_driven_state: int, *, phase: str
) -> None:
    """Re-read the view's native dimension and physical attachment, without writes.

    Diameter leaders are not note leaders: GetLeaderCount is diagnostic,
    not an invented one-leader contract. Type, one exact physical edge and
    its native measured value establish the dimension's correspondence.
    """
    label = f"collar-side neck ({phase})"
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
    for annotation, display, native in _native_neck_view_dimensions(side, label=label):
        if dimension_name(adapter, annotation) == "NeckDiaDim":
            inboard.append(display)
        if native.FullName == full_name and int(adapter.swApp.IsSame(native, reference)) == 1:
            matches.append((annotation, display))
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one native view dimension {full_name!r}")
    annotation, display = matches[0]
    measured_mm = _assert_plain_neck_size(display, label=label, expected_driven_state=1)
    if len(inboard) != 1:
        raise RuntimeError(f"{label}: expected one unchanged right-hand NeckDiaDim")
    _assert_plain_neck_size(
        inboard[0], label=f"right-hand NeckDiaDim ({phase})",
        expected_driven_state=right_driven_state,
    )
    rim = _outboard_neck_rim(adapter, side)
    attached = tuple(annotation.GetAttachedEntities3() or ())
    count = int(annotation.GetAttachedEntityCount3())
    types = tuple(int(value) for value in (annotation.GetAttachedEntityTypes() or ()))
    same = (
        count == 1
        and len(attached) == 1
        and types == (1,)  # swSelEDGES
        and attached[0] is not None
        and _is_same_attachment(adapter, attached[0], rim, "EDGE")
    )
    if not same or annotation.IsDangling() is not False:
        raise RuntimeError(
            f"{label}: lost exact physical rim attachment: count={count}, types={types}"
        )
    _assert_neck_arrow_landing(display, label=label)
    _telemetry.info(
        f"{label}: native diameter {full_name!r}, measured_mm={measured_mm}, "
        f"driven=1, places={NECK_DIA_PLACES}, tolerance=NONE, exact_rim=True, "
        f"native_leaders={annotation.GetLeaderCount()}"
    )


def _add_outboard_neck_dimension(
    adapter: Any, drawing_model: Any, side: Any
) -> tuple[Any, int]:
    """Add only a native driven measurement; never write a diameter value."""
    label = "collar-side neck"
    original = [
        native
        for annotation, _display, native in _native_neck_view_dimensions(side, label=label)
        if dimension_name(adapter, annotation) == "NeckDiaDim"
    ]
    if len(original) != 1:
        raise RuntimeError(f"{label}: expected one original right-hand NeckDiaDim")
    right_driven_state = original[0].DrivenState
    if type(right_driven_state) is not int or right_driven_state not in (1, 2):
        raise RuntimeError(f"{label}: unreadable original driven state {right_driven_state!r}")
    rim = _outboard_neck_rim(adapter, side)
    _select_view_entity(adapter, side, "EDGE", None, label=label, entity=rim)
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    display, status = extension.AddSpecificDimension(
        *OUTBOARD_NECK_DIAMETER_XY, 0.0, 6, 0  # swDiameterDimension; out status
    )
    if display is None or type(status) is not int or status != 0:  # success = 0
        raise RuntimeError(
            f"{label}: physical edge-on circle rejected native diameter (status={status!r}); "
            "no note or doubled-linear fallback is permitted"
        )
    display = _early_bound(display, "IDisplayDimension")
    native = display.GetDimension2(0)
    if native is None:
        raise RuntimeError(f"{label}: new display has no native IDimension")
    dimension = _early_bound(native, "IDimension")
    dimension.DrivenState = 1  # swDimensionDriven; only the new drawing dimension
    status = display.SetPrecision3(
        DRAWING_REFERENCE_PRECISION["OutboardNeckDia"], -1, -1, -1
    )
    if type(status) is not int or status != 0:
        raise RuntimeError(f"{label}: native precision assignment failed ({status!r})")
    # Driven is not a presentation setting: retain a plain, general-band
    # callout like the existing NeckDiaDim, not a parenthesized reference.
    display.ShowParenthesis = False
    if not isinstance(dimension.FullName, str) or not dimension.FullName:
        raise RuntimeError(f"{label}: new native dimension has no FullName")
    drawing_model.ClearSelection2(True)
    rebuild_drawing(adapter, label=label)
    _assert_outboard_neck_dimension(
        adapter, side, dimension, right_driven_state, phase="after insertion rebuild"
    )
    return dimension, right_driven_state


def _outboard_neck_checkpoint(
    adapter: Any, side: Any, identity: Any, right_driven_state: int, phase: str
) -> None:
    """Use the finalizer's existing save boundaries; never reopen the drawing."""
    if phase in (
        "after_drawing_save",
        "after_pdf_save",
    ):
        _assert_outboard_neck_dimension(
            adapter, side, identity, right_driven_state, phase=phase
        )


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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    native_side.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(native_side.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to lay the crankshaft profile horizontal")
    drawing_model.EditRebuild3()
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

    outboard_neck_dimension, right_neck_driven_state = _add_outboard_neck_dimension(
        adapter, drawing_model, side
    )

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
    add_surface_finish(
        adapter,
        side,
        edge_entity=_collar_rear_rim(adapter, side),
        leader_attach_xy=COLLAR_REAR_FINISH[0],
        symbol_xy=COLLAR_REAR_FINISH[1],
        control=surface_finish_by_key(SURFACE_FINISHES, "collar_rear_face"),
        label="crankshaft collar rear (post boss) face finish",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # The end view prints hidden lines removed with the rest (drawing-guidelines.md
    # rule 9 (show internal shape in solid lines)): the punch mark is flagged by
    # its own leader, so no dashed cross-hole is needed to clock it.

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crankshaft Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_outboard_neck_dimension(
                adapter, side, outboard_neck_dimension, right_neck_driven_state,
                phase="final settling rebuild",
            ),
        ),
        checkpoint=lambda phase: _outboard_neck_checkpoint(
            adapter, side, outboard_neck_dimension, right_neck_driven_state, phase
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
