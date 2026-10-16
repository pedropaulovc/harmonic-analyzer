r"""Magnifying-bracket dimensional contract -- the single source of truth shared
by the part build (``build_mg_magnifying_bracket.py``) and its manufacturing
drawing (``draw_mg_magnifying_bracket.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else imports this bracket's
nominals -- the magnifier assembly places it BY NAME and mates it by named
references (never a Python constant), so one ``_spec`` module is right here (no
``_geom`` split, unlike the magnifying LEVER whose knife-axis station an
assembly imports).  The offline lockstep test asserts the part marks and the
drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.

The bracket is a three-feature fitting: an extruded COLLAR tube (Ø12 OD, 10
long about local X) whose bore is the PRESS seat for the Ø6 magnifying lever
(nominal and bands from ``mg_lever_press_fit_geom``, the joint's one read
point), a rectangular ARM cantilevering +Z to the summing plate, and a mounting
FLANGE whose +Z face butts the plate's front face.  The two plan rectangles
carry the auto-importable marked dimensions, including the flange thickness
band; the collar's end-view circles carry the OD and the banded bore, and its
extrude the banded length; the blanked ``ArmSection`` witness carries the
arm's section and the bore axis's one datum chain (the mounting face and the
arm's end, both from the axis) in the side view.  Native counterbore callouts
define the through bore and head seat.
"""

from __future__ import annotations
from magnifying_bracket_joint_layout import (
    POSITION_BAND,
    GRIP_MIN,
)
from mg_lever_press_fit_geom import PRESS_INSTALLATION_NOTES

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The two extruded PLAN rectangles auto-import to the front view
# exactly like column_clamp_front's BlockProfile; the arm and flange chains are
# NAME-DISAMBIGUATED in the build (ArmWidth/ArmDepth vs FlangeWidth/FlangeDepth)
# because a shared bare "Width"/"Depth" would collide in the front view's keep
# map.  The arm's depth (its Z extent from a start buried inside the collar)
# stays unmarked: the arm's end is located from the bore axis instead
# (mreview09 blocker 3, two origins for the collar).  The collar's annulus
# sketch (Right plane) imports to the side view -- the OD and the press-seat
# bore with its native band -- and the mid-plane extrude's one dimension, the
# collar length with its band (COLLAR_LENGTH_BAND: the press contact is the
# collar's length less the lever's dome), to the front view.  The blanked
# ArmSection witness (Right plane) imports to the same side view: the arm's
# face nearest the bore axis (Y -3 versus the other face at Y +4.5,
# controlling ArmBelowAxis), the flange's mounting face
# from the bore axis and the arm's end past that face -- the ONE toleranced
# chain along Z (mreview10 blocker 2); its thickness and offset copies and
# its closing dimension (the flange above the arm) stay unmarked.  The
# blanked ArmFootprint witness (Front plane) imports to the BOTTOM view,
# where the arm's end face prints face-on inside the flange's outline: the
# arm's thickness and its lower face from the flange's hole-datum edge (both
# controlling: the arm face is the machinist's measurable datum for the
# holes' row, mreview10 blocker 1), toleranced where the footprint is seen,
# not edge-on. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarBore"},
    "Collar": {"CollarLen"},
    "ArmProfile": {"ArmWidth"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
    "Flange": {"FlangeHeight"},
    "MountingCoordinates": {"MountingX0", "MountingX1", "MountingY0"},
    "ArmSection": {"ArmBelowAxis", "SeatToAxis", "ArmPastSeat"},
    "ArmFootprint": {"FootprintThickness", "FootprintOffset"},
}

# Wizard callout precision is applied in the build through observed native
# dimension names; those identifiers must never be renamed for this contract.
DRAWING_PRECISION = {
    "CollarProfile": {"CollarOd": 2, "CollarBore": 3},
    "Collar": {"CollarLen": 2},
    "ArmProfile": {"ArmWidth": 2},
    "FlangeProfile": {"FlangeWidth": 2, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 2},
    "ArmSection": {"ArmBelowAxis": 2, "SeatToAxis": 2, "ArmPastSeat": 2},
    "ArmFootprint": {"FootprintThickness": 2, "FootprintOffset": 2},
}
# The pure SHEET-derived reference is SeatToAxis + ArmPastSeat (arm end).
# It reads actual model entities and prints in parentheses; its places remain
# spec-owned under drawing-simplicity-policy.md `How the repository implements the guidelines`.  FootprintOffset + ArmBelowAxis already
# locate the bore axis from the lower flange edge without a duplicate REF.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "arm end from bore axis": 2,
}
# The collar's length band, like the bore's, is read by the build straight
# from mg_lever_press_fit_geom (COLLAR_LENGTH_BAND) onto the extrude's CollarLen.
DRAWING_POSITION_BAND = POSITION_BAND

# True free-text instructions only (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)): the collar's sizes and the
# bore's band, the arm's section and the mounting pattern are native dimensions
# on the sheet (the bore's callout names the MHA-MG-003 lever), so the notes
# carry the assembly-time press and its retention -- the press contract's own
# wording, shared with the lever print and the assembly (user ruling
# 2026-10-11) -- and the one named floor exception, nothing the views show.
DRAWING_NOTES = "\n".join(
    (
        PRESS_INSTALLATION_NOTES,
        # Pending exception ruling: MHA-MG-001 counterbore floor 1.525 MIN (#1294).
        f"COUNTERBORE FLOOR {GRIP_MIN:.3f} MIN.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
