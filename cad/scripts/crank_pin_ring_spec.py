r"""Crank-pin keeper ring (MHA-128) nominals, pure data.

No SolidWorks/COM calls and no ``build_*`` module in the import closure: the
ring build, the keeper chain and the drive-train assembly read these here, so
the ring's build recipe never rides a consumer's cache key (#880).

A round brass wire ring, Ø10 on the wire centreline, threaded through the
taper pin's cross-hole (ch11 p.14 page002_img01). A round ring's wire follows
its own arc through the straight hole, so the hole is sized for that arc: across
the pin's section the arc bows ARC_SAGITTA off its chord, and the hole takes half
of that either side of the wire plus RING_HOLE_AIR (asserted below). The ring
hangs ~9.5 below the pin, where the keeper chain loops it and its hub-side beads
clear the Ø25.4 hub barrel.

Part frame: the origin is on the cross-hole axis at the pin's centre, the hole
axis is local Z, and the ring lies in the local XZ plane hanging toward local
+X. Its centre is RING_CENTRE_X along +X, which centres the arc in the hole.
"""

from __future__ import annotations

import math

from crank_pin_spec import BIG_END_DIA, PIN_LENGTH, RING_HOLE_DIA, RING_HOLE_X, SMALL_END_DIA

WIRE_DIA = 1.0  # brass wire (photo-scaled, low); thin enough for a Ø2.1 hole
MEAN_R = 5.0  # Ø10 on the wire centreline
# The pin stands proud of the hub barrel so the ring clears it by this.
HUB_CLEARANCE = 0.25
RING_HOLE_AIR = 0.05  # least radial air between the wire and the hole wall
PIN_DIA_AT_HOLE = BIG_END_DIA - (
    (BIG_END_DIA - SMALL_END_DIA) * RING_HOLE_X / PIN_LENGTH
)
ARC_SAGITTA = MEAN_R - math.sqrt(MEAN_R**2 - (PIN_DIA_AT_HOLE / 2.0) ** 2)
# The arc is centred in the hole: its crown sits half the sagitta above the
# hole axis, and its ends at the pin surface half the sagitta below.
RING_CENTRE_X = MEAN_R - ARC_SAGITTA / 2.0
RING_BOTTOM_X = RING_CENTRE_X + MEAN_R  # the wire centreline's lowest point
V_RING = 2.0 * math.pi**2 * MEAN_R * (WIRE_DIA / 2.0) ** 2
# The silver-soldered butt joint, on the ring's side away from the arm: a
# JOINT_DIA bead centred on the wire centreline. It also gives the drawings a
# real edge to balloon, which a plain torus lacks.
JOINT_DIA = 1.3
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
