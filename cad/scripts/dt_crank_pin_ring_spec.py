r"""Crank-pin keeper ring (MHA-DT-27) nominals, pure data.

No SolidWorks/COM calls and no ``build_*`` module in the import closure: the
ring build, the keeper chain and the drive-train assembly read these here, so
the ring's build recipe never rides a consumer's cache key (#880).

A round brass wire ring, Ø.47 on the wire centreline, threaded through the
taper pin's cross-hole (ch11 p.14 page002_img01). A round ring's wire follows
its own arc through the straight hole, so the hole is sized for that arc: across
the pin's section the arc bows ARC_SAGITTA off its chord, and the hole takes half
of that either side of the wire plus RING_HOLE_AIR (asserted below, at the
worst printed limits of both parts). The ring lies in the pin's axial plane
and reaches ~.46 outboard of the hole, past the pin's big end and the crank
arm's edge, where the keeper chain loops it (owner ruling 2026-10-15 A1;
``dt_vn_keeper_chain_spec`` owns the pose and its arm clearance).

Issue #290: the sheet prints decimal inch (``drawing_unit: in``); the wire is
.040 in brass wire and the inside diameter prints at .XX, since the ring must
thread the cross-hole at its limits.

Part frame: the origin is on the cross-hole axis at the pin's centre, the hole
axis is local Z, and the ring lies in the local XZ plane hanging toward local
+X. Its centre is RING_CENTRE_X along +X, which centres the arc in the hole.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm, printed_deviations
from dt_crank_pin_spec import BIG_END_DIA, PIN_LENGTH, RING_HOLE_DIA, RING_HOLE_X, SMALL_END_DIA
from dt_crank_pin_spec import UNIT as PIN_UNIT

UNIT = drawing_unit("parts/dt-crank-pin-ring", _config.parts("dt-crank-pin-ring"))

WIRE_DIA = 1.016  # .040 brass wire (photo-scaled, low); thin enough for the #45 hole
# Ø.43 inside diameter on the printed grid (Ø.47 on the wire centreline): its
# .XX lower limit still threads the pin's cross-hole with RING_HOLE_AIR at the
# pin's own worst printed limits (asserted below). Owner ruling 2026-10-15,
# option A: the smaller ring left no air at those limits; the larger ring
# re-solves the keeper chain.
MEAN_R = (10.922 + WIRE_DIA) / 2.0  # .43 ID
# The pin stands proud of the hub barrel so the ring clears it by this.
HUB_CLEARANCE = 0.254  # .010
RING_HOLE_AIR = 0.05  # least radial air between the wire and the hole wall
# How far the pin's big end stands out of the hub barrel: the ring's wire, in
# the hole RING_HOLE_X from the end, clears the barrel by HUB_CLEARANCE. The
# drive train, the keeper chain and the interference contract all read it here.
PIN_PROUD = RING_HOLE_X + WIRE_DIA / 2.0 + HUB_CLEARANCE
PIN_DIA_AT_HOLE = BIG_END_DIA - (
    (BIG_END_DIA - SMALL_END_DIA) * RING_HOLE_X / PIN_LENGTH
)
ARC_SAGITTA = MEAN_R - math.sqrt(MEAN_R**2 - (PIN_DIA_AT_HOLE / 2.0) ** 2)
# The arc is centred in the hole: its crown sits half the sagitta above the
# hole axis, and its ends at the pin surface half the sagitta below.
RING_CENTRE_X = MEAN_R - ARC_SAGITTA / 2.0
RING_FAR_X = RING_CENTRE_X + MEAN_R  # the wire centreline's far point along +X
V_RING = 2.0 * math.pi**2 * MEAN_R * (WIRE_DIA / 2.0) ** 2
# The silver-soldered butt joint, on the ring's side away from the arm: a
# JOINT_DIA bead centred on the wire centreline. It also gives the drawings a
# real edge to balloon, which a plain torus lacks.
JOINT_DIA = 1.27  # .05
_JOINT_H = math.sqrt((JOINT_DIA / 2.0) ** 2 - (WIRE_DIA / 2.0) ** 2)
# The bead less the wire it swallows (a straight-wire approximation; the ring's
# 5 mm bend changes it by well under 0.1 %).
V_JOINT = 4.0 / 3.0 * math.pi * _JOINT_H**3

HOLE_AIR = RING_HOLE_DIA / 2.0 - WIRE_DIA / 2.0 - ARC_SAGITTA / 2.0
if HOLE_AIR < RING_HOLE_AIR - 1e-9:
    raise AssertionError(
        f"keeper ring's wire arc leaves {HOLE_AIR:.3f} air in the "
        f"Ø{RING_HOLE_DIA} cross-hole, under {RING_HOLE_AIR}"
    )

# The ring's inside diameter prints at the title block's two places; the pin's
# end diameters and the hole's station print at two (dt_crank_pin_spec), and
# the drilled hole only cuts oversize. The governing case is the smallest
# ring (tightest arc) through the fattest pin section at the hole, the hole
# at its station's big-end limit and drilled to its nominal size.
RING_ID = 2.0 * MEAN_R - WIRE_DIA
RING_ID_PLACES = 2
RING_ID_MIN, RING_ID_MAX = (
    round(RING_ID + d, 12)
    for d in printed_deviations(RING_ID, RING_ID_PLACES, unit=UNIT)
)
# The pin's end diameters and the hole's station print at two places.
PIN_BAND = printed_band_mm(2, unit=PIN_UNIT)
_TAPER_PER_MM = (BIG_END_DIA - SMALL_END_DIA) / PIN_LENGTH
PIN_DIA_AT_HOLE_MAX = BIG_END_DIA + PIN_BAND - _TAPER_PER_MM * (RING_HOLE_X - PIN_BAND)
_MEAN_R_MIN = (RING_ID_MIN + WIRE_DIA) / 2.0
_HALF_CHORD = PIN_DIA_AT_HOLE_MAX / 2.0
ARC_SAGITTA_WORST = _MEAN_R_MIN - math.sqrt(_MEAN_R_MIN**2 - _HALF_CHORD**2)
HOLE_AIR_WORST = RING_HOLE_DIA / 2.0 - WIRE_DIA / 2.0 - ARC_SAGITTA_WORST / 2.0
if HOLE_AIR_WORST < RING_HOLE_AIR - 1e-9:
    raise AssertionError(
        f"the smallest printed keeper ring (Ø{RING_ID_MIN}) through the pin's "
        f"Ø{PIN_DIA_AT_HOLE_MAX:.3f} worst section leaves {HOLE_AIR_WORST:.3f} "
        f"air in the Ø{RING_HOLE_DIA} cross-hole, under {RING_HOLE_AIR}"
    )
