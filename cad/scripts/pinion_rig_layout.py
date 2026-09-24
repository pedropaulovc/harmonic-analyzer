r"""Axial (machine-z) stations of the alignment-pinion swing rig -- one source
for the drive-train assembly, the harmonic base's transferred seats and the
torque-shaft / lift-rod lengths.

GEOMETRY ONLY: no drawing notes, no annotation contract, no drawing spec
imports (the ``pinion_cam_geometry`` precedent), so a print-wording edit can
never re-key the base or the drive train.

User ruling (c), 2026-09-24: the two pivot blocks locate the swing cluster
(strap / drum / strap) axially, as the ch25 photos show -- no collar, no
spacer.  At fit-up the cluster is pushed hard against the BACK block and the
FRONT block is stood off the front strap with a 0.25 feeler before its base
seats are spotted through it (the existing U28 transfer-at-assembly step).
The same ruling moved the drum's bond station 0.3 aft on the MHA-102 arbor
(drum front end 61.55 from the head shoulder), so j = 19 reads full face at
nominal.

Physical end play is the one feeler setting, P = 0.25 +/- 0.10, shared by the
four axial gaps (front block/strap, strap/drum, drum/strap, strap/back block).
``STRAP_AIR`` below is only the MODEL pose's drum-end air (Main M2): it is NOT
additional hardware clearance, and the worst-case gates sweep every split of P
instead (``test_drive_train_support_layout``).
"""

from __future__ import annotations

from cone_pivot_post_installation import MECHANISM_Z_SHIFT
from pinion_bracket_geometry import THICKNESS as STRAP_T
from pinion_pivot_block_geometry import BLOCK_DEPTH
from pinion_spring_geometry import WIDTH as SPRING_W

# MHA-002 drum.  The length is alignment_pinion_spec.FACE_WIDTH (a drawing
# contract this module must not import); a lockstep test pins the two.
DRUM_LEN = 143.2
DRUM_FRONT_Z = -74.7 + MECHANISM_Z_SHIFT  # 0.3 aft of the released -75.0
DRUM_BACK_Z = DRUM_FRONT_Z + DRUM_LEN

# Model-pose air at each drum end (see the module docstring).
STRAP_AIR = 0.25
STRAP_Z_INNER = (DRUM_FRONT_Z - STRAP_AIR, DRUM_BACK_Z + STRAP_AIR)
STRAP_Z_OUTER = (STRAP_Z_INNER[0] - STRAP_T, STRAP_Z_INNER[1] + STRAP_T)

# The back block is the axial reference: its outer face stays at the released
# machine z 88, and the cluster sits hard against its inner face.
BACK_BLOCK_OUTER_Z = 88.0 + MECHANISM_Z_SHIFT
BACK_BLOCK_Z0 = BACK_BLOCK_OUTER_Z - BLOCK_DEPTH
if abs(STRAP_Z_OUTER[1] - BACK_BLOCK_Z0) > 1e-9:
    raise AssertionError("back strap is not hard against the back block")

# Fit-up feeler between the front strap's outer face and the front block.
FRONT_BLOCK_FEELER = 0.25
FRONT_BLOCK_Z0 = STRAP_Z_OUTER[0] - FRONT_BLOCK_FEELER - BLOCK_DEPTH
BLOCK_Z0 = (FRONT_BLOCK_Z0, BACK_BLOCK_Z0)
# Each block's two #8 hold-down seats sit at its mid-depth (the base spots
# them through the block holes at assembly).
BLOCK_SEAT_Z = tuple(z0 + BLOCK_DEPTH / 2.0 for z0 in BLOCK_Z0)

# Torque shaft and lift rod: back ends flush with the back block's outer face,
# lengths printed at one decimal place.  The shaft's front end sits flush with
# the front block's outer face to within that rounding; the rod stands ~10
# proud of it as the MHA-059 lever hub's seat.
TORQUE_SHAFT_LEN = round(BACK_BLOCK_OUTER_Z - FRONT_BLOCK_Z0, 1)
TORQUE_SHAFT_Z0 = BACK_BLOCK_OUTER_Z - TORQUE_SHAFT_LEN
LEVER_SEAT_PROUD = 10.0
LIFT_ROD_LEN = round(BACK_BLOCK_OUTER_Z - FRONT_BLOCK_Z0 + LEVER_SEAT_PROUD, 1)
LIFT_ROD_Z0 = BACK_BLOCK_OUTER_Z - LIFT_ROD_LEN

# MHA-114 return spring: the blade rides the back strap's flank.  The inset
# from the model strap's inner face keeps the whole 4.0-wide blade on the
# flank at every split of P and every strap thickness in its .X band (the
# worst case is T = 8.2 with the strap hard back: inner face 0.8 aft of the
# model's), which the support-layout gate proves.
SPRING_BLADE_INSET = 1.0
SPRING_Z = STRAP_Z_INNER[1] + SPRING_BLADE_INSET + SPRING_W / 2.0
