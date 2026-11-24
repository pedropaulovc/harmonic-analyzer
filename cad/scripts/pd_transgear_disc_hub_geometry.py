r"""The hub-flange ↔ reducer-disc joint: three #0-80 disc screws on one circle,
and the hub's spigot the disc pilots on.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` import.  The one
authority for what two parts cut and must agree on: the brass hub's flange
(MHA-PD-17, ``transgear_disc_hub_spec``) carries the #51 (.067) clearance
holes and the reducer disc (MHA-PD-06, ``rack_pinion_spec``) the #0-80 taps;
the three 91794A055 fillister screws (MHA-PD-VN-55) join them on a Ø.75
circle, which keeps the disc's taps clear of its Ø.501 bore at the worst
case (``rack_pinion_spec`` checks the web; the heads stand clear of the hub
body).  The hub's rear spigot passes the disc's bore and seats on
the MHA-PD-10 sleeve's step face (R9-68): its diameter clears the disc's
bore (the disc is centred at assembly) and its length is the disc front
face's station ahead of the step, so the disc's, the sleeve's and the hub's
specs and the cluster fit read it here.
Nothing here imports either part's spec, so the disc's spec reads the joint
without reaching the hub's (which reads the cluster fit, which reads the
disc).

Decimal inch (#290): both sheets print inches; every nominal below is the
exact millimetre value of its printed inch size.

Both parts' local frames put the gear axis on Z through the origin, with the
pattern's 0° on local +X and the angles counter-clockwise seen from +Z.  Both
parts sit in the machine unrotated, so local +X is the machine's +X.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN

# The hub sheet prints the bolt circle; the disc reads the same unit.
UNIT = drawing_unit(
    "parts/pd-transgear-disc-hub", _config.parts("pd-transgear-disc-hub")
)


SCREW_THREAD = "#0-80"
# MHA-PD-VN-55, McMaster 91794A055 (_mcmaster_91794a055 sizes it).
SCREW_COUNT = 3
SCREW_ANGLES_DEG = (0.0, 120.0, 240.0)
# The flange's drilled clearance hole the disc's taps are spotted through:
# a #51 drill.
SCREW_HOLE_DIA = 1.7018  # .067
BOLT_CIRCLE_DIA = 19.05  # .75
# Printed at .XX: ±.01 on the diameter is the ±.005 radial hole-position
# band every stack of the joint uses (contract §8, "hole position"); the
# walls hold the .080 target at it, the flange sized to suit.
BOLT_CIRCLE_PLACES = 2
BOLT_CIRCLE_POSITION_TOL = printed_band_mm(BOLT_CIRCLE_PLACES, unit=UNIT) / 2.0

if len(SCREW_ANGLES_DEG) != SCREW_COUNT:
    raise AssertionError("one pattern angle per disc screw")

# The retained hub spigot (R9-68): Ø.498 REF in the disc's bore, made to fit
# (fit audit 2026-11-23, pending owner confirmation; drawing-guidelines.md
# rule 4, form 2): the disc's bore is reamed with the .501 chucking reamer
# (tools.reamer-5010, to order, not owned) and prints no band, and the
# spigot is turned last to that bore, so its size prints REF with no limits
# and SPIGOT_CLEARANCE, the diametral clearance in the bore, is the printed
# requirement.  It was a printed +.000/-.002 at three places (and
# +.000/-.001 at four before, delegated ruling 2026-11-07 L2).
# What each end of the clearance protects: under the least the disc cannot
# be tapped central to its assembled tooth-space runout
# (pd_rack_pinion_spec.PART_TOOTH_SPACE_RUNOUT_TIR_MM); over the greatest
# the disc floats further off the hub's axis while its taps are spotted and
# the taps' finished web to the disc's bore falls
# (pd_rack_pinion_spec.TAP_TO_BORE_WALL_FINISHED), and a smaller spigot
# thins its own wall over the hub's bore under the .071 of MHA-PD-17 RV-02
# (delegated ruling 2026-11-12, owner review #2144; the owner's ruling of
# 2026-11-08 kept .073) (pd_transgear_disc_hub_spec.BORE_WALLS_FINISHED).
# SPIGOT_DIA_BAND is the ANALYSIS band, the modelled result of that fit
# under the disc bore's own analysis band (.501-.503): .496 (the least bore
# less the greatest clearance) to .500 (the greatest bore less the least),
# never a printed limit; pd_rack_pinion_spec proves the pair.
# Its length runs from the flange's
# rear face to its end on the sleeve's step: a term of the disc cluster's
# stack (transgear_cluster_fit) that sets the collar-to-disc air, so it
# prints +/-.001 (the shims set the end float: owner ruling 2026-11-01,
# #2124).
SPIGOT_DIA = 12.6492  # .498 REF
SPIGOT_CLEARANCE = (0.0762, 0.127)  # printed (least, greatest) diametral: .003-.005
SPIGOT_DIA_BAND = (0.0508, -0.0508)  # analysis (upper, lower) deviations: +.002/-.002
SPIGOT_DIA_PLACES = 3
SPIGOT_LENGTH = 3.6576  # .144
SPIGOT_LENGTH_PLACES = 3
SPIGOT_LENGTH_BAND = FIT_LENGTH_BAND_IN


def screw_centres() -> tuple[tuple[float, float], ...]:
    """``(x, y)`` of each screw axis in either part's local frame (mm)."""
    radius = BOLT_CIRCLE_DIA / 2.0
    return tuple(
        (radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle)))
        for angle in SCREW_ANGLES_DEG
    )


# The equation factors both parts' sketches use to drive the 120° and 240°
# centres from the one "BoltCircleDia" global: x = BC / 4, |y| = BC · √3 / 4.
BOLT_CIRCLE_X_FACTOR = 0.25
BOLT_CIRCLE_Y_FACTOR = math.sqrt(3.0) / 4.0
