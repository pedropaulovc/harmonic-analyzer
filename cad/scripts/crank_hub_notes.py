r"""Crank-hub drawing prose -- the feature callouts only its sheet prints.

Split OUT of ``crank_hub_geometry`` / ``crank_hub_spec`` (codex #361): every
crank part recipe and every assembly (through ``_interference_contracts``)
imports those modules, so callout prose living there made a wording edit
rebuild all five crank parts.  This module is imported ONLY by the hub and arm
drawing scripts (the arm through ``crank_arm_notes``) and their offline tests,
so a prose edit re-keys drawings, never a part.

Callouts read in the order the work is done: the size and process line
first, the matched-fit prose after it (drawing-simplicity policy rule 6).
"""

from __future__ import annotations

from crank_hub_geometry import (
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    SHAFT_CLEARANCE_MAX,
    SHAFT_CLEARANCE_MIN,
)

# Seat-in-arm press (B1, Main 2026-09-25): the seat is turned to suit the
# MHA-020 bore as measured, for a light press.  A 1018 hub in a 1018 arm,
# 8.0 long and keyed by MHA-138 on the seam, needs the press only to hold the
# hub square and stop it turning while the seam is match-drilled.  The band
# sits inside ISO 286 H7/p6 at 18-30 mm (0.001-0.035 diametral, the
# locational-interference fit); its line-to-line end is raised to 0.010
# because the hub is turned to a measured bore, not drawn from stock.  No
# geometry reads it (the model seats line-to-line), so it lives here with the
# sheet that prints it, not in crank_hub_spec, which every assembly imports
# through _interference_contracts.
SEAT_PRESS_INTERFERENCE = (0.010, 0.030)  # diametral, mm (min, max)


def seat_callout(mate: str) -> str:
    """Hub-seat fit on MHA-137, turned second to press into ``mate``'s bore.

    Four lines (policy rule 6). FACES FLUSH is the acceptance; how the hub
    gets there (an arbor press) is a method, so the sheet does not say it.
    """
    low, high = SEAT_PRESS_INTERFERENCE
    return "\n".join(
        (
            f"TURN TO SUIT {mate} BORE",
            f"FOR LIGHT PRESS: {low:.3f}-{high:.3f}",
            "DIAMETRAL INTERFERENCE;",
            "FACES FLUSH",
        )
    )


def seat_bore_callout(mate: str) -> str:
    """The arm's seat bore, made first: ``mate`` is pressed into it."""
    return "\n".join(
        (f"{mate} IS A LIGHT", "PRESS FIT IN THIS BORE;", "FACES FLUSH")
    )


def seam_callout(mate: str, pin: str = "MHA-138") -> str:
    """MHA-138 seam, match-drilled with ``mate``: size first, then the process.

    ``pin`` names the pin as the sheet identifies it; the arm's print adds its
    part name (MHA-020 machinist review, 2026-09-29).
    """
    return "\n".join(
        (
            f"(<MOD-DIAM>{AXIAL_PIN_DIA:.1f}) <HOLE-DEPTH> {AXIAL_PIN_LENGTH:.1f}",
            f"MATCH-DRILL/REAM WITH {mate}",
            "AT ASSEMBLY, CENTRED ON THE SEAM",
            f"FOR {pin}: LIGHT DRIVE FIT",
        )
    )


# The printed band governs the bore; the shaft clearance it yields is a
# reference restatement.
BORE_CALLOUT = (
    "REAM THRU\n"
    f"({SHAFT_CLEARANCE_MIN:.3f}-{SHAFT_CLEARANCE_MAX:.3f} DIAMETRAL\n"
    "CLEARANCE ON MHA-026)"
)
# The arm bore is made first and carries the band; this seat is turned to fit
# it, so its nominal prints as a reference under the match-fit callout.
SEAT_CALLOUT = seat_callout("MHA-020")
SEAM_CALLOUT = seam_callout("MHA-020")
# The cross-hole is drilled, then taper-reamed through hub and shaft together.
# The ream fixes the hub on the shaft for good, so the front face is set flush
# with the crankshaft's end first (the arm front is already flush with the hub
# front from the seat press); the prose reads under the native #14 drill size,
# in the order the work is done.
CROSS_HOLE_CALLOUT = "\n".join(
    (
        "FRONT FACE FLUSH WITH",
        "CRANKSHAFT MHA-026 END;",
        "MATCH TAPER-REAM 1:48 FOR",
        "MHA-024: LIGHT DRIVE FIT",
    )
)

# Axial stack at the printed worst case (Main, 2026-09-30), machine z, -Z =
# FRONT, with a bought ANSI #25 chain on the crank T12.  Not printed: the
# drive train asserts both from the same names (build_drive_train_assembly).
# The hub is placed by the fitter (front face flush with the shaft end, the
# crank face z -183, before the match-ream), so its printed overall length --
# not the arm's stock thickness -- places its rear face.
#   Links:
#     crank face                    CRANK_FACE_Z                     -183
#     hub overall, front to rear    HUB_LENGTH +/- HUB_LENGTH_TOL    27 +/-0.05
#     relief, back from rear face   RELIEF_LENGTH +/- RELIEF_LENGTH_TOL
#                                                                    3.6 +/-0.05
#     removable seat face           transgear_removable_spec.SEAT_FACE_Z
#                                   + crankshaft_spec.SEAT_COLLAR_BAND
#                                                                    -152.5 +0.1/-0.5
#     T12 wheel plate               PLATE + PLATE_BAND               2.8 +0/-0.10
#     chain reach ahead of seat     CHAIN_REACH_FRONT = W/2 + G      6.2865
#                                   (ANSI_ROLLER_WIDTH 3.175 / 2 + ANSI_HALF_WIDTH
#                                   4.699, chain floated frontmost)
#   A  chain -> relief shoulder:
#        (SEAT_FACE_Z + min(SEAT_COLLAR_BAND) - CHAIN_REACH_FRONT)
#        - (CRANK_FACE_Z + HUB_LENGTH + HUB_LENGTH_TOL
#           - (RELIEF_LENGTH - RELIEF_LENGTH_TOL))
#        = (-152.5 - 0.5 - 6.2865) - (-183 + 27.05 - 3.55)
#        = -159.2865 - (-159.5)                   = 0.2135  (nominal 0.81)
#   B  hub rear face -> T12 front face:
#        (SEAT_FACE_Z + min(SEAT_COLLAR_BAND) - (PLATE + max(PLATE_BAND)))
#        - (CRANK_FACE_Z + HUB_LENGTH + HUB_LENGTH_TOL)
#        = (-152.5 - 0.5 - 2.8) - (-183 + 27.05)
#        = -155.8 - (-155.95)                     = 0.15    (nominal 0.7)
#   Worst case in both: seat collar at its forward limit, hub long; A with the
#   relief short, B with the plate thick.
