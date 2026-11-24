r"""Crank-hub drawing prose -- the feature callouts only its sheet prints.

Split OUT of ``crank_hub_geometry`` / ``crank_hub_spec`` (codex #361): every
crank part recipe and the drive train's table (``_dt_drive_train_interference``)
imports those modules, so callout prose living there made a wording edit
rebuild all five crank parts.  This module is imported ONLY by the hub and arm
drawing scripts (the arm through ``crank_arm_notes``) and their offline tests,
so a prose edit re-keys drawings, never a part.

Callouts read in the order the work is done: the size and process line
first, the matched-fit prose after it (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
"""

from __future__ import annotations

from dt_crank_hub_geometry import (
    AXIAL_PIN_DIA,
    MM_PER_IN,
    HUB_SEAT_LENGTH,
    SEAM_DEPTH,
)


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as the inch sheet prints it, without a leading zero."""
    return f"{value_mm / MM_PER_IN:.{places}f}".removeprefix("0")


def seat_callout(mate: str, name: str = "CRANK ARM") -> str:
    """Hub-seat fit on MHA-DT-31, turned last to slide into ``mate``'s bore.

    Two lines of words under the reference size (drawing-guidelines.md rule 7
    (notes: few, flagged, never a method): at most two).  The arm bore is
    made first, so the reference nominal, the named mate and the acceptance
    by feel define the made-to-fit seat (rule 4); the joint is bonded with
    LOCTITE 638 (owner ruling 2026-11-24, fit audit question 21: a bonded
    slip fit, not the light press).  ``name`` is the mate's part name,
    printed with its number (r7 review of farm run 20261101T022045634Z).  The
    seat end flush with the arm's front and the bond's preparation and cure
    are the MHA-DT-00 bond step's, not this sheet's (rule 7).
    """
    return "\n".join(
        (
            f"TURN TO {name} {mate} BORE:",
            "ARM SLIDES ON BY HAND; BONDED",
        )
    )


# The bore comes off the owned .3760 reamer and prints that size with no
# band; MHA-DT-11's shank is made last, turned to it, and carries the fit's
# acceptance on its own sheet (fit audit 2026-11-23, MHA-DT-31.bore: the
# acceptance prints once, on the member made last).
BORE_CALLOUT = "REAM THRU\nMHA-DT-11 IS TURNED\nTO THIS BORE"
# The arm bore is made first and carries the band; this seat is turned to fit
# it, so its nominal prints as a reference under the made-to-fit callout.
SEAT_CALLOUT = seat_callout("MHA-DT-06")
# The hub's own seam callout: the size, process and depth line, then two
# lines of words (rule 7).  The hole is drilled 5/32 at assembly with the
# arm, so it is matched to its mate (rule 4), and the pin is bonded in
# (fit audit 2026-11-23, MHA-DT-06_DT-31.seam_pin: the joint is bonded under
# question 21, so the seam needs no reamed drive fit and the .1562 reamer is retired); the
# pin is named by part name and number.  The depth sits in the callout (rule
# 26: size, process, depth; a depth is never deferred to a view), read from
# SEAM_DEPTH, the constant the model's seam cut is built to; the side view's
# native depth then prints as a reference.  The hole's radial station is a
# native dimension on the end view (rule 26: a location is a dimension, not a
# sentence).
SEAM_DEPTH_TEXT = inch_text(SEAM_DEPTH, 2)
SEAM_CALLOUT = "\n".join(
    (
        f"(<MOD-DIAM>{inch_text(AXIAL_PIN_DIA, 3)}) 5/32 DRILL <HOLE-DEPTH> {SEAM_DEPTH_TEXT} AT ASSEMBLY",
        "WITH CRANK ARM MHA-DT-06 FOR",
        "DOWEL PIN MHA-DT-VN-59, BONDED",
    )
)
# The seat length is the arm's thickness as made, not a turned size (owner
# ruling 2026-11-01; r9 review: a toleranced seat length read against the
# flush condition): its nominal prints as a reference flagged to numbered
# note 2, the matched length with its mate by name and number and its
# acceptance (rule 4).  A plain reference left the shoulder with no
# controlling value (round-1 review, 2 of 3 runs), and MATCH alone gave no
# acceptance (round-2 review, 2 of 3 runs).  The acceptance is one-sided,
# +.000/-.010 to the arm's measured thickness, so the hub end is never proud
# of the arm's front face (owner ruling 2026-11-06; fit audit 2026-11-23,
# MHA-DT-31.seat_length: nothing needs the old -.002, the face is not a
# stack term).  END FLUSH on a part sheet is an assembly instruction (rule
# 7), so the faces-flush check stays on the MHA-DT-00 bond step.
SEAT_LENGTH_MATCH_BAND = "+.000/-.010"
SEAT_LENGTH_NOTE_NUMBER = 2
SEAT_LENGTH_CALLOUT = f"SEE NOTE {SEAT_LENGTH_NOTE_NUMBER}"
SEAT_LENGTH_NOTE = (
    f"{SEAT_LENGTH_NOTE_NUMBER}. SEAT LENGTH ({inch_text(HUB_SEAT_LENGTH, 2)}): "
    f"MEASURED THICKNESS OF CRANK ARM MHA-DT-06 {SEAT_LENGTH_MATCH_BAND}."
)
# The cross-hole is drilled, then taper-reamed through hub and shaft together
# at assembly.  Its callout carries SEE NOTE 1 and the numbered note states
# the matched ream: the mate by name and number, the pin it takes, and the
# acceptance -- the driven pin's keeper ring MHA-DT-27 still clear of the hub
# (rule 4: a matched fit states its acceptance; dt_crank_pin_ring_spec.
# PIN_PROUD books that clearance, and the MHA-DT-00 hub step reads the same
# condition).  No number: no hub dimension carries the pin's position, and a
# spec constant typed into the text is not model-owned (drawing-simplicity-
# policy, Codjiflo P2 on #2095).  Where the hub sits on the shaft before the
# ream (its front face flush with the crankshaft's dome root, the crank face
# CRANK_FACE_Z) is an assembly setting the MHA-DT-00 hub step states, reading
# FRONT_FACE_DATUM (pipeline review of 49287772c).  The note is too long for
# a two-line callout, so it is numbered and flagged (rule 7).
FRONT_FACE_DATUM = "MHA-DT-11 DOME ROOT"
CROSS_HOLE_NOTE_NUMBER = 1
CROSS_HOLE_CALLOUT = f"SEE NOTE {CROSS_HOLE_NOTE_NUMBER}"
CROSS_HOLE_NOTE = "\n".join(
    (
        f"{CROSS_HOLE_NOTE_NUMBER}. AT ASSEMBLY, TAPER-REAM 1:48 WITH CRANKSHAFT MHA-DT-11 FOR",
        "   TAPER PIN MHA-DT-09. STOP WHILE KEEPER RING MHA-DT-27, HUNG",
        "   FROM THE DRIVEN PIN, STILL CLEARS THE HUB.",
    )
)
# The sheet's numbered notes, in one block (rule 7: at most four lines).
SHEET_NOTES = f"{CROSS_HOLE_NOTE}\n{SEAT_LENGTH_NOTE}"

# The relief prints its value only: a reason on a plain .XX length is
# narration (rule 7).  The overall's +.004 is functional (stack B below and
# the drive-pin tips; owner ruling 2026-10-31), so the band names the stack
# it sets and its mate (rule 4: a width that sets a stack names the stack).
# Value and band alone read as an unneeded explicit band (round-3 review, 2
# of 3 runs); v47's "REAR FACE CLEARS SPROCKET MHA-PD-09" read as a reason
# on an overall size (rule 7, 3 of 3 runs).  No AIR (rule 26).
HUB_LENGTH_CALLOUT = "SETS CLEARANCE TO\nSPROCKET MHA-PD-09"

# Axial stack at the printed worst case (Main, 2026-09-30), machine z, -Z =
# FRONT, with a bought ANSI #25 chain on the crank T12.  Not printed: the
# drive train asserts both from the same names (build_drive_train_assembly).
# The hub is placed by the fitter (front face flush with the shaft's dome
# root, the crank face z -183, before the match-ream), so its printed
# overall length -- not the arm's stock thickness -- places its rear face.
#   Links:
#     crank face                    CRANK_FACE_Z                     -183
#     hub overall, front to rear    HUB_LENGTH + HUB_LENGTH_BAND     25.146 +0.1016/-0.254
#     relief, back from rear face   RELIEF_LENGTH +/- RELIEF_LENGTH_TOL
#                                                                    4.064 +/-0.254
#     removable seat face           transgear_removable_spec.SEAT_FACE_Z
#                                   + crankshaft_spec.SEAT_COLLAR_BAND
#                                                                    -154.3 +0.129/-0.531
#     T12 wheel plate               PLATE + PLATE_BAND               2.8 +0/-0.10
#     chain reach ahead of seat     CHAIN_REACH_FRONT = W/2 + G      6.2865
#                                   (ANSI_ROLLER_WIDTH 3.175 / 2 + ANSI_HALF_WIDTH
#                                   4.699, chain floated frontmost)
#   A  chain -> relief shoulder, in two poses (crank_hub_geometry.
#      chain_shoulder_axial_air; floor CHAIN_SHOULDER_AIR_MIN 0.2135):
#      seated, the wheel on the seat face:
#        (SEAT_FACE_Z + min(SEAT_COLLAR_BAND) - CHAIN_REACH_FRONT)
#        - (CRANK_FACE_Z + HUB_LENGTH + HUB_LENGTH_TOL
#           - (RELIEF_LENGTH - RELIEF_LENGTH_TOL))
#        = (-154.3 - 0.5314 - 6.2865) - (-183 + 25.2476 - 3.81)
#        = -161.1179 - (-161.5624)                = 0.4445  (nominal 1.3315)
#      floated, the wheel walked forward off its pins onto the hub rear face
#      (the hub and seat stations cancel):
#        (RELIEF_LENGTH - RELIEF_LENGTH_TOL) + (PLATE + min(PLATE_BAND))
#        - CHAIN_REACH_FRONT
#        = 3.81 + 2.70 - 6.2865                   = 0.2235  (nominal 0.5775)
#      The floated pose governs and sizes the relief: .15 would leave it -0.0305.
#   B  hub rear face -> T12 front face:
#        (SEAT_FACE_Z + min(SEAT_COLLAR_BAND) - (PLATE + max(PLATE_BAND)))
#        - (CRANK_FACE_Z + HUB_LENGTH + HUB_LENGTH_TOL)
#        = (-154.3 - 0.5314 - 2.8) - (-183 + 25.2476)
#        = -157.6314 - (-157.7524)                = 0.1210  (nominal 0.754)
#   Worst case: A seated and B with the seat collar at its forward limit and
#   the hub long, A with the relief short, B with the plate thick; A floated
#   with the relief short and the plate thin.
