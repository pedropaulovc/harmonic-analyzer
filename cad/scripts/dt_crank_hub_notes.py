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
    SEAT_PRESS_INTERFERENCE,
    SHAFT_CLEARANCE_MAX,
    SHAFT_CLEARANCE_MIN,
)


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as the inch sheet prints it, without a leading zero."""
    return f"{value_mm / MM_PER_IN:.{places}f}".removeprefix("0")


def seat_callout(mate: str, name: str = "CRANK ARM") -> str:
    """Hub-seat fit on MHA-DT-31, turned second to press into ``mate``'s bore.

    Two lines of words under the reference size (drawing-guidelines.md rule 7
    (notes: few, flagged, never a method): at most two).  The arm bore is
    made first, so the reference nominal, the named mate and the stated
    interference define the matched fit (rule 4).  ``name`` is the mate's
    part name, printed with its number (r7 review of farm run
    20261101T022045634Z).  The fit is the seat's IN the arm: "BORE FOR LIGHT
    PRESS" on a turned OD read as this part's bore (review of farm run
    20261101T081735465Z).  The seat end flush with the arm's front is the
    MHA-DT-00 press step's acceptance, not this sheet's: rule 7 names "END
    FLUSH WITH CRANK ARM FRONT" as an assembly instruction.
    """
    low, high = SEAT_PRESS_INTERFERENCE
    return "\n".join(
        (
            f"LIGHT PRESS IN {name} {mate}:",
            f"{inch_text(low, 4)}-{inch_text(high, 4)} DIAMETRAL INTERFERENCE",
        )
    )


def seat_bore_callout(mate: str) -> str:
    """The arm's seat bore, made first: ``mate`` is pressed into it."""
    return "\n".join(
        (f"{mate} IS A LIGHT", "PRESS FIT IN THIS BORE;", "FACES FLUSH")
    )


def seam_callout(mate: str, depth: str = "", pin: str = "SEAM PIN MHA-DT-VN-59") -> str:
    """MHA-DT-VN-59 seam, match-drilled with ``mate``: size first, then the process.

    ``mate`` and ``pin`` name the parts by name and number (rule 4; MHA-DT-06
    machinist review, 2026-09-29; review of farm run 20261101T081735465Z:
    SEAM PIN says what the pin is).  The blind pin makes hub and arm a
    permanent pair, taken apart at the MHA-DT-09 taper pin (owner rulings
    2026-11-01; r9 review: say it plainly).  The depth is never typed here:
    the hub's side view prints it as a native dimension, and ``depth`` lets
    the arm's sheet refer to it (Codjiflo review of 831be7869).
    """
    return "\n".join(
        (
            f"(<MOD-DIAM>{inch_text(AXIAL_PIN_DIA, 3)}){depth} ON SEAM, MATCH-DRILL/REAM",
            f"WITH {mate} AT ASSEMBLY;",
            f"{pin} LIGHT DRIVE FIT;",
            "PERMANENT PAIR; DISASSEMBLE AT MHA-DT-09",
        )
    )


# The printed band governs the bore; the shaft clearance it yields is a
# reference restatement.
BORE_CALLOUT = (
    "REAM THRU\n"
    f"({inch_text(SHAFT_CLEARANCE_MIN, 4)}-{inch_text(SHAFT_CLEARANCE_MAX, 4)} DIAMETRAL\n"
    "CLEARANCE ON MHA-DT-11)"
)
# The arm bore is made first and carries the band; this seat is turned to fit
# it, so its nominal prints as a reference under the match-fit callout.
SEAT_CALLOUT = seat_callout("MHA-DT-06")
# The hub's own seam callout: the size and process line, then two lines of
# words (rule 7).  The final process is REAM, at assembly with the arm, so
# the hole is matched to its mate (rule 4); the pin is named by part name
# and number.  The hole's centre is drawn on the Ø.76 edge and the view's
# vertical centreline, so no words locate it (rule 26: a location is not a
# sentence, and ON SEAM is a private phrase).  The depth prints natively on
# the side view, never typed here (Codjiflo review of 831be7869).  The
# permanent-pair and disassembly line is an assembly instruction on a part
# sheet (rule 7), so it is gone.  The arm's sheet keeps ``seam_callout``.
SEAM_CALLOUT = "\n".join(
    (
        f"(<MOD-DIAM>{inch_text(AXIAL_PIN_DIA, 3)}) REAM AT ASSEMBLY",
        "WITH CRANK ARM MHA-DT-06 FOR",
        "DOWEL PIN MHA-DT-VN-59, LIGHT DRIVE FIT",
    )
)
# The seat length is the arm's thickness as made, not a turned size (owner
# ruling 2026-11-01; r9 review: a toleranced seat length read against the
# flush condition), so it prints as a plain reference.  The faces-flush
# acceptance is the MHA-DT-00 press step's; rule 7 names END FLUSH on a part
# sheet an assembly instruction.
#
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

# The overall and the relief print their value and band only: a reason on an
# overall size, or on a plain .XX length, is narration (rule 7).  The stacks
# they hold (A and B below) are checked on the drive-train assembly.

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
#                                                                    -154.3 +0.1/-0.5
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
#        = (-154.3 - 0.5 - 6.2865) - (-183 + 25.2476 - 3.81)
#        = -161.0865 - (-161.5624)                = 0.4759  (nominal 1.3315)
#      floated, the wheel walked forward off its pins onto the hub rear face
#      (the hub and seat stations cancel):
#        (RELIEF_LENGTH - RELIEF_LENGTH_TOL) + (PLATE + min(PLATE_BAND))
#        - CHAIN_REACH_FRONT
#        = 3.81 + 2.70 - 6.2865                   = 0.2235  (nominal 0.5775)
#      The floated pose governs and sizes the relief: .15 would leave it -0.0305.
#   B  hub rear face -> T12 front face:
#        (SEAT_FACE_Z + min(SEAT_COLLAR_BAND) - (PLATE + max(PLATE_BAND)))
#        - (CRANK_FACE_Z + HUB_LENGTH + HUB_LENGTH_TOL)
#        = (-154.3 - 0.5 - 2.8) - (-183 + 25.2476)
#        = -157.6 - (-157.7524)                   = 0.1524  (nominal 0.754)
#   Worst case: A seated and B with the seat collar at its forward limit and
#   the hub long, A with the relief short, B with the plate thick; A floated
#   with the relief short and the plate thin.
