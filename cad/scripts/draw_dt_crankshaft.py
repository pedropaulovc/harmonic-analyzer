r"""Create the crankshaft MHA-DT-011 manufacturing drawing under the simplicity policy.

The SLDPRT remains authoritative.  A shaft carries no datum and no
geometric-control frame (policy rule 3): the three running/seat diameters keep
their native size bands, the journal keeps one bearing-surface finish, and
every length is an ordinary model dimension at its part-authored places.

The model's shaft axis runs along +Y from the dome root (local y=0, the plane
where MHA-DT-006 and MHA-DT-031 finish flush).  The single longitudinal view is the
``*Right`` orientation rotated a quarter turn in the sheet so the shaft lies
horizontal, as it sits in the lathe: dome on the left, far end on the right,
the MHA-DT-009 cross-hole seen as a true circle.  The crank-end view is the
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
import sys
from typing import Any, Callable, Sequence

import _telemetry
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
    visible_component_entities,
)
from _drawing_annotation_extent import place_callout_clear
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from dt_crankshaft_spec import (
    COLLAR_DIA,
    COLLAR_REAR,
    CROSS_HOLE_PROCESS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRIVE_PIN_CIRCLE_RADIUS,
    DRIVE_PIN_HOLE_DIA,
    DRIVE_PIN_HOLE_PROCESS,
    PIN_HOLE_HEIGHT,
    PIN_HOLE_SPEC,
    PINION_SEAT_DIA,
    REFERENCE_DIMENSIONS,
    JOURNAL_DIA,
    JOURNAL_START,
    JOURNAL_END,
    RELIEF_START,
    RELIEF_END,
    SEAT_COLLAR,
    SEAT_STEP,
    SHAFT_CORE_LANDS,
    SHAFT_DIA,
    SHAFT_DOME_HEIGHT,
    SHAFT_LENGTH,
    SPHERICAL_DIMENSIONS,
    SPIGOT_END,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from build_dt_crankshaft import PINION_PIN_DIA, PINION_PIN_STATION_Y
from dt_crank_pinion_spec import CRANKSHAFT_PIN_HOLE_PROCESS
from dt_crankshaft_notes import (
    CROSS_HOLE_CALLOUT,
    DRIVE_PIN_CALLOUT,
    DRIVE_PIN_DEPTH_BAND,
    DRIVE_PIN_LOCATION_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    _SW_LENGTH_MM,
    _SW_PREF_UNITS_LINEAR,
    auto_center_marks,
    place_view,
)


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
# 2.0 dome height shares the first row at the far left, where no baseline
# reaches; the last row clears the title block.
_ROW_PITCH = 0.0095
_ROW_Y = tuple(round(0.162 - k * _ROW_PITCH, 4) for k in range(10))
# The six diameters are authored in end-profile sketches; the end view
# receives them first and they are then dragged onto the profile (rule 7:
# diameters on the side view).  Their temporary end-view spots are clear of
# everything else on the sheet.
END_DIAMETERS = {
    "ShaftDiaDim": (0.036, 0.215),
    "JournalDiaDim": (0.036, 0.228),
    "ReliefDiaDim": (0.036, 0.241),
    "PinionSeatDiaDim": (0.036, 0.254),
    "SpigotDiaDim": (0.024, 0.241),
    "CollarDiaDim": (0.024, 0.254),
}
# The drive-pin holes' locations stay in the end view, the one view that
# shows them as true (visible) circles: each hole from the shaft axis, its
# dimension line just right of the view, text beyond the view's top (+Z hole)
# and bottom (-Z hole), running right into the gap before the dome's
# extension lines.  That gap (dimension line to dome tip) is ~30 mm, just the
# 7.000 value's width, so the lower one's mate callout is set in rows no
# wider than it; the lower text sits 5 mm under the 2.0 dome height's shelf.
END_PIN_KEEP = {
    "DrivePinOffset1": (0.058, 0.210),
    "DrivePinOffset2": (0.058, 0.145),
}
END_KEEP = {**END_DIAMETERS, **END_PIN_KEEP}
SIDE_KEEP = {
    "DomeHeight": (DOME_TIP_X - 0.016, _ROW_Y[0]),
    "PinionSeatStation": ((SEAT_STEP_X + FAR_END_X) / 2.0, _ROW_Y[0]),
    "JournalInboardStation": ((JOURNAL_END_X + FAR_END_X) / 2.0, _ROW_Y[1]),
    "ReliefInboardStation": ((RELIEF_END_X + FAR_END_X) / 2.0, _ROW_Y[2]),
    "ReliefOutboardStation": ((RELIEF_START_X + FAR_END_X) / 2.0, _ROW_Y[3]),
    "JournalOutboardStation": ((JOURNAL_START_X + FAR_END_X) / 2.0 - 0.020, _ROW_Y[4]),
    "CollarRearStation": ((COLLAR_REAR_X + FAR_END_X) / 2.0, _ROW_Y[5]),
    "CollarSeatStation": ((COLLAR_SEAT_X + FAR_END_X) / 2.0 - 0.020, _ROW_Y[6]),
    "PinHoleStation": ((PIN_X + FAR_END_X) / 2.0, _ROW_Y[7]),
    # Its "0.0 / 135.4" block sits right of the overall's "(137.4) / OVERALL"
    # on the next row down, not over it: the two rows are 9.5 mm apart.
    "Depth": ((DOME_ROOT_X + FAR_END_X) / 2.0 + 0.035, _ROW_Y[8]),
    "OverallLength": ((DOME_TIP_X + FAR_END_X) / 2.0, _ROW_Y[9]),
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
# Ø9.525 on the core LEFT of the cross-hole, between the dome root (where its
# extension lines start) and the hole: placed right of the hole those lines
# ran along the silhouette over it, and the hole callout's leader had to cross
# one (leader-crosses-line, af13c8ff8).  The Ø9.0 seat's on the seat, left of
# the pinion pin hole. The Ø11.388's 2X/limit stack rises above its dimension:
# place its arrow on the outboard land 6.9 mm short of the relief shoulder,
# right of the rear-face finish symbol's text and left of the outboard land's
# own symbol, and lower its row 5 mm, so the 2X clears both LIGHT DRIVE FIT
# and the taper note's landing line.
_DIAMETER_ROW_Y = (0.212, 0.223)
# The spigot's Ø17.5 on the spigot and the collar body's Ø20.6 on the body
# (each sketch starts at its section's front face), the spigot's text a row
# above the body's so each dimension line stays clear of the other's text:
# right of them under the cross-hole callout's prose and left of the outboard
# journal's finish symbol.
DIAMETER_POSITIONS = {
    "ShaftDiaDim": (PIN_X - 0.016, _DIAMETER_ROW_Y[0]),
    "JournalDiaDim": (RELIEF_START_X - 0.0069, _DIAMETER_ROW_Y[1]),
    "ReliefDiaDim": (RELIEF_START_X + 0.030, _DIAMETER_ROW_Y[0]),
    "PinionSeatDiaDim": (SEAT_STEP_X + 0.010, _DIAMETER_ROW_Y[0]),
    "SpigotDiaDim": (COLLAR_SEAT_X + 0.002, _DIAMETER_ROW_Y[1]),
    "CollarDiaDim": (SPIGOT_END_X + 0.002, _DIAMETER_ROW_Y[0]),
}
# The Ø9.525 callout counts every bare core land (SHAFT_CORE_LANDS: the
# dome-side shank, the washer's land behind the collar and the land before
# the Ø9 seat step); machinist review of 8b5e1f354 found the 2X it carried
# named two of the three.  The 2X Ø11.388 names both bearing lands on either
# side of the relief; the displayed arrow picks the outboard land, and the
# equal-size callout also governs the inboard land.
CALLOUTS_ABOVE = {"ShaftDiaDim": f"{len(SHAFT_CORE_LANDS)}X", "JournalDiaDim": "2X"}
# The lower drive-pin location names the mate its +/-0.025 serves
# (crankshaft_notes), in the clear field under its text.
CALLOUTS_BELOW = {
    "OverallLength": "OVERALL",
    "DrivePinOffset2": DRIVE_PIN_LOCATION_CALLOUT,
}
# Both running lands carry separate part-owned finish symbols. The outboard
# symbol sits right of the Ø11.388 dimension line, its leader landing on the
# land just short of the relief shoulder; the inboard symbol retains its
# clear spot above the relief.  The collar's rear (washer) face takes its
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
# text's left end and runs down-left at ~53 deg through the hole centre, a
# clean crossing of the 118.0 station's extension line rather than a near
# parallel one (run 20260923T030252135Z-49e46990), 4 mm clear of the Ø9.525
# shoulder on its left.  18 mm right of its old spot so that leader clears
# the moved Ø9.525 text (leader-crosses-line, af13c8ff8).
HOLE_CALLOUT_XY = (PIN_X + 0.072, 0.247)
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
PINION_PIN_NOTE_XY = (0.270, 0.250)
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
ISO_NOTE_XY = (0.376, 0.108)


def _set_callout_below(display: Any, text: str, label: str) -> None:
    """Put the matched-operation prose UNDER a native hole callout.

    The drill size reads first, in the order the work is done; the fit and
    mate prose follows in the callout-below compartment (the Ø9.550 bore
    callout's order).  ``SetText`` reports nothing, so it is read back.
    """
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(4, text)  # swDimensionTextCalloutBelow
    applied = str(display.GetText(4) or "")
    if applied.replace("\r", "") != text:
        raise RuntimeError(f"{label}: callout-below text did not persist: {applied!r}")


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
) -> None:
    """Move a leadered note's text inside ``field`` from its measured box.

    Its leader must still end inside ``hole``.  Everything read is logged.
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
    _set_callout_below(cross_hole, CROSS_HOLE_CALLOUT, "tapered-pin cross-hole")
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
        process=DRIVE_PIN_HOLE_PROCESS,
    )
    _band_hole_depth(
        drive_pins,
        DRIVE_PIN_DEPTH_BAND,
        drawing_model,
        "seat-collar drive-pin holes",
    )
    _set_callout_below(drive_pins, DRIVE_PIN_CALLOUT, "seat-collar drive-pin holes")
    place_callout_clear(
        adapter,
        _early_bound(drive_pins, "IDisplayDimension").GetAnnotation(),
        label="seat-collar drive-pin holes",
        below={},
        beside={},
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
        label="crankshaft collar rear (thrust washer) face finish",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # The end view's hidden lines show the cross-hole running across the
    # dome end, which clocks the punched fiducial to it (rule 7: a cross-hole
    # through a turned part).  Re-asserted last so the export regenerates the
    # dashed edges after every annotation (layout-tuning refusal e).
    set_hidden_lines_visible(adapter, end)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crankshaft Manufacturing Drawing",
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
