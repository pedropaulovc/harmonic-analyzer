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


def seat_callout(mate: str) -> str:
    """Hub-seat fit on MHA-137, the part turned second to fit ``mate``'s bore."""
    return "\n".join(
        (
            f"MATCH-FIT TO {mate}",
            "LIGHT ARBOR-PRESS TO SHOULDER",
            "FACES FLUSH",
            "NO TURN OR SLIDE BY HAND",
        )
    )


def seat_bore_callout(mate: str) -> str:
    """The arm's seat bore, made first: its printed size governs, ``mate`` fits it."""
    return "\n".join((f"{mate} IS MATCH-FIT", "TO THIS BORE; FACES FLUSH"))


def seam_callout(mate: str) -> str:
    """MHA-138 seam, match-drilled with ``mate``: size first, then the process."""
    return "\n".join(
        (
            f"(<MOD-DIAM>{AXIAL_PIN_DIA:.1f}) <HOLE-DEPTH> {AXIAL_PIN_LENGTH:.1f}",
            f"MATCH-DRILL/REAM WITH {mate}",
            "AT ASSEMBLY, CENTRED ON THE SEAM",
            "FOR MHA-138: LIGHT DRIVE FIT",
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
SEAT_CALLOUT = seat_callout("MHA-020 ARM BORE")
SEAM_CALLOUT = seam_callout("MHA-020")
# The cross-hole is drilled, then taper-reamed through hub and shaft together;
# the prose reads under the native #14 drill size and matches the crankshaft
# MHA-026 callout for the same operation.
CROSS_HOLE_CALLOUT = "\n".join(
    (
        "MATCH TAPER-REAM 1:48",
        "WITH CRANKSHAFT MHA-026",
        "TO TAPER PIN MHA-024:",
        "LIGHT DRIVE FIT",
    )
)
