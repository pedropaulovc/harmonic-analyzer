r"""Crank-hub drawing prose -- the feature callouts only its sheet prints.

Split OUT of ``dt_crank_hub_geometry`` / ``dt_crank_hub_spec`` (codex #361):
every crank part recipe and every assembly (through ``_interference_contracts``)
imports those modules, so callout prose living there made a wording edit
rebuild all five crank parts.  This module is imported by the hub, arm and shaft
drawing scripts (the arm through ``dt_crank_arm_notes``), the MHA-DT-00
assembly drawing and their offline tests. A prose edit re-keys drawings,
never a part.

Callouts read in the order the work is done: the size and process line
first, the matched-fit prose after it (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
"""

from __future__ import annotations

from dt_crank_hub_geometry import (
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    SEAT_PRESS_INTERFERENCE,
    SHAFT_CLEARANCE_MAX,
    SHAFT_CLEARANCE_MIN,
)
from dt_crank_pin_spec import BIG_END_DIA, PIN_LENGTH, SMALL_END_DIA
from dt_crankshaft_spec import PIN_HOLE_SPEC as SHAFT_PIN_HOLE_SPEC


def seat_callout(name: str, number: str) -> str:
    """Hub-seat fit on MHA-DT-31, turned second to press into the bore of
    ``name`` ``number`` (the mate by name and number, drawing-guidelines.md
    rule 4 (tighten only for function, and name the mate)).

    Four lines (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)). FRONT FACES FLUSH is the acceptance (the
    hub's labelled front face and the arm's); how the hub gets there (an
    arbor press) is a method, so the sheet does not say it.
    """
    low, high = SEAT_PRESS_INTERFERENCE
    return "\n".join(
        (
            f"TURN TO SUIT {name}",
            f"{number} BORE; {low:.3f}-{high:.3f}",
            "DIAMETRAL INTERFERENCE;",
            "FRONT FACES FLUSH",
        )
    )


def seat_bore_callout(mate: str) -> str:
    """The arm's seat bore, made first: ``mate`` is pressed into it."""
    return "\n".join(
        (f"{mate} IS A LIGHT", "PRESS FIT IN THIS BORE;", "FACES FLUSH")
    )


def seam_callout(mate: str, pin: str = "MHA-DT-VN-59") -> str:
    """MHA-DT-VN-59 seam, match-drilled with ``mate``: size first, then the process.

    ``mate`` and ``pin`` name the parts as the sheet identifies them (name
    and number, drawing-guidelines.md rule 4 (tighten only for function, and name the mate)).
    """
    return "\n".join(
        (
            f"(<MOD-DIAM>{AXIAL_PIN_DIA:.1f}) <HOLE-DEPTH> {AXIAL_PIN_LENGTH:.1f}, "
            "MATCH-DRILL/REAM AT ASSY",
            f"WITH {mate} ON THE SEAM",
            f"FOR {pin}:",
            "LIGHT DRIVE FIT",
        )
    )


# The printed band governs the bore; the shaft clearance it yields is a
# reference restatement.
BORE_CALLOUT = (
    "REAM THRU\n"
    f"({SHAFT_CLEARANCE_MIN:.3f}-{SHAFT_CLEARANCE_MAX:.3f} DIAMETRAL\n"
    "CLEARANCE ON MHA-DT-11)"
)
# The arm bore is made first and carries the band; this seat is turned to fit
# it, so its nominal prints as a reference under the match-fit callout.
SEAT_CALLOUT = seat_callout("CRANK ARM", "MHA-DT-06")
# The seam is blind in the hub, so the dowel names its pull thread: the way
# it comes out (machinist review r2b of 383c31baa, rule 16).
SEAM_CALLOUT = seam_callout("CRANK ARM MHA-DT-06", pin="PULL-THREAD DOWEL MHA-DT-VN-59")
# The cross-hole: this hub is drilled alone with its #14 pilot (the native
# size and its station from the arm shoulder).  The shaft is NOT drilled
# alone (#1678): drilled separately, the shaft's .X station and the hub's own
# location could set the two holes up to ~1.8 mm apart, while the 1:48 ream
# cleans up only ~0.2 mm radially round a #9 hole.  So at assembly, the front
# face set flush with the crankshaft's dome root first -- the crank face,
# CRANK_FACE_Z, where the 3/8 in cylinder meets the dome; the dome stands
# proud of the hub (the arm front is already flush with the hub front from the
# seat press) -- the shaft's #9 is drilled through this pilot, opening it, and
# the pair is taper-reamed together.  The #9's DRILLED HOLES limit stays inside
# the reamed taper along the whole pin (thinnest at the far hub wall).  The
# drill and taper come from their owners (the shaft's hole spec and the pin's
# end diameters); MHA-DT-00 step 6 and the shaft's callout read the same
# names.  The prose reads under the native #14 drill size, in the order the
# work is done; three rows, so the block stays four rows tall.
FRONT_FACE_DATUM = "MHA-DT-11 DOME ROOT"
CROSS_HOLE_DRILL = SHAFT_PIN_HOLE_SPEC.size
CROSS_HOLE_TAPER = f"1:{PIN_LENGTH / (BIG_END_DIA - SMALL_END_DIA):.0f}"
CROSS_HOLE_CALLOUT = "\n".join(
    (
        f"AT ASSY DRILL {CROSS_HOLE_DRILL} THRU CRANKSHAFT",
        f"MHA-DT-11; TAPER-REAM {CROSS_HOLE_TAPER} BOTH FOR",
        "CRANK PIN MHA-DT-09: LIGHT DRIVE FIT",
    )
)
# The front face carries the setting the cross-hole is drilled at, on a
# leader to the face itself (the end view looks at it), so no text has to say
# which end is the front (machinist review r1 of 114fa71c1).
FRONT_FACE_NOTE = "\n".join(
    ("FRONT FACE: AT ASSY,", "SET FLUSH WITH", FRONT_FACE_DATUM)
)

# The two axial bands name the stack each sets, under their dimensions
# (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the overall places the rear face against the removable sprocket
# (stack B below), the relief places the barrel's rear shoulder ahead of the
# #25 chain wrapping it (stack A).  The overall's rows stay narrower than its
# span, so its extension lines run clear of them.
HUB_LENGTH_CALLOUT = "SETS SPROCKET\nMHA-PD-09 AIR"
RELIEF_LENGTH_CALLOUT = "SETS #25 CHAIN AIR ON\nSPROCKET MHA-PD-09"

# Axial stack at the printed worst case (Main, 2026-09-30), machine z, -Z =
# FRONT, with a bought ANSI #25 chain on the crank T12.  Not printed: the
# drive train asserts both from the same names (build_drive_train_assembly).
# The hub is placed by the fitter (front face flush with the shaft's dome
# root, the crank face z -183, before the match-ream), so its printed
# overall length -- not the arm's stock thickness -- places its rear face.
#   Links:
#     crank face                    CRANK_FACE_Z                     -183
#     hub overall, front to rear    HUB_LENGTH +/- HUB_LENGTH_TOL    25.2 +/-0.10
#     relief, back from rear face   RELIEF_LENGTH +/- RELIEF_LENGTH_TOL
#                                                                    3.85 +/-0.05
#     removable seat face           pd_transgear_removable_spec.SEAT_FACE_Z
#                                   + dt_crankshaft_spec.SEAT_COLLAR_BAND
#                                                                    -154.3 +0.1/-0.5
#     T12 wheel plate               PLATE + PLATE_BAND               2.8 +0/-0.10
#     chain reach ahead of seat     CHAIN_REACH_FRONT = W/2 + G      6.2865
#                                   (ANSI_ROLLER_WIDTH 3.175 / 2 + ANSI_HALF_WIDTH
#                                   4.699, chain floated frontmost)
#   A  chain -> relief shoulder, in two poses (dt_crank_hub_geometry.
#      chain_shoulder_axial_air; floor CHAIN_SHOULDER_AIR_MIN 0.2135):
#      seated, the wheel on the seat face:
#        (SEAT_FACE_Z + min(SEAT_COLLAR_BAND) - CHAIN_REACH_FRONT)
#        - (CRANK_FACE_Z + HUB_LENGTH + HUB_LENGTH_TOL
#           - (RELIEF_LENGTH - RELIEF_LENGTH_TOL))
#        = (-154.3 - 0.5 - 6.2865) - (-183 + 25.30 - 3.80)
#        = -161.0865 - (-161.50)                  = 0.4135  (nominal 1.0635)
#      floated, the wheel walked forward off its pins onto the hub rear face
#      (the hub and seat stations cancel):
#        (RELIEF_LENGTH - RELIEF_LENGTH_TOL) + (PLATE + min(PLATE_BAND))
#        - CHAIN_REACH_FRONT
#        = 3.80 + 2.70 - 6.2865                   = 0.2135  (nominal 0.3635)
#      The floated pose governs and sizes the relief: 3.6 left it -0.0365.
#   B  hub rear face -> T12 front face:
#        (SEAT_FACE_Z + min(SEAT_COLLAR_BAND) - (PLATE + max(PLATE_BAND)))
#        - (CRANK_FACE_Z + HUB_LENGTH + HUB_LENGTH_TOL)
#        = (-154.3 - 0.5 - 2.8) - (-183 + 25.30)
#        = -157.6 - (-157.70)                     = 0.10    (nominal 0.7)
#   Worst case: A seated and B with the seat collar at its forward limit and
#   the hub long, A with the relief short, B with the plate thick; A floated
#   with the relief short and the plate thin.
