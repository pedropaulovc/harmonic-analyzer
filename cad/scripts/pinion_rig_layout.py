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
The saved pose IS that fit-up stack (Codex #854/#858 P1): the cluster hard on
the back block with its three contacts line to line and the one feeler at the
front block, so every station a part is made or drilled at -- base seats,
strap cross holes, shaft holes -- is the station the assembly shows.  The
worst-case gates sweep every split of P (``test_drive_train_support_layout``).
"""

from __future__ import annotations

import math

from cone_pivot_post_installation import MECHANISM_Z_SHIFT
from pinion_bracket_geometry import THICKNESS as STRAP_T
from pinion_pivot_block_geometry import BLOCK_DEPTH
from pinion_spring_geometry import WIDTH as SPRING_W

# The back block is the axial reference: its outer face stays at the released
# machine z 88.  At fit-up the cluster is pushed hard against its inner face,
# so the back strap, the drum and the front strap close up line to line behind
# it and every other station below derives from this one.
BACK_BLOCK_OUTER_Z = 88.0 + MECHANISM_Z_SHIFT
BACK_BLOCK_Z0 = BACK_BLOCK_OUTER_Z - BLOCK_DEPTH

# MHA-002 drum.  The length is alignment_pinion_spec.FACE_WIDTH (a drawing
# contract this module must not import); a lockstep test pins the two.  It is
# trapped between the straps' inner faces, so the back stop sets its station
# (61.55 from the MHA-102 head shoulder, ruling (c)'s bond station).
DRUM_LEN = 143.2
DRUM_BACK_Z = BACK_BLOCK_Z0 - STRAP_T
DRUM_FRONT_Z = DRUM_BACK_Z - DRUM_LEN
STRAP_Z_INNER = (DRUM_FRONT_Z, DRUM_BACK_Z)
STRAP_Z_OUTER = (DRUM_FRONT_Z - STRAP_T, BACK_BLOCK_Z0)

# Fit-up feeler between the front strap's outer face and the front block: the
# one axial gap the fit-up stack carries.
FRONT_BLOCK_FEELER = 0.25
FRONT_BLOCK_Z0 = STRAP_Z_OUTER[0] - FRONT_BLOCK_FEELER - BLOCK_DEPTH
BLOCK_Z0 = (FRONT_BLOCK_Z0, BACK_BLOCK_Z0)
# Each block's two #8 hold-down seats sit at its mid-depth (the base spots
# them through the block holes at assembly).
BLOCK_SEAT_Z = tuple(z0 + BLOCK_DEPTH / 2.0 for z0 in BLOCK_Z0)

# The span between the blocks' inner faces: the solid stack plus the one
# feeler (Codex #854 P1), the same in the pose and on the machine.
INNER_SPAN = BACK_BLOCK_Z0 - (FRONT_BLOCK_Z0 + BLOCK_DEPTH)  # 161.45
if abs(INNER_SPAN - (2.0 * STRAP_T + DRUM_LEN + FRONT_BLOCK_FEELER)) > 1e-9:
    raise AssertionError("the block span is not the solid stack plus one feeler")


# Torque shaft and lift rod: back ends flush with the back block's outer face,
# both printed at .X (title-block +/-0.8, U27) and rounded UP.  The shaft is
# flush with the front block's outer face to within that rounding; the rod
# stands >= LEVER_SEAT_PROUD proud of it as the MHA-059 lever hub's seat.
def _up_to_tenth(length: float) -> float:
    return math.ceil(length * 10.0 - 1e-6) / 10.0


TORQUE_SHAFT_LEN = _up_to_tenth(BACK_BLOCK_OUTER_Z - FRONT_BLOCK_Z0)
TORQUE_SHAFT_Z0 = BACK_BLOCK_OUTER_Z - TORQUE_SHAFT_LEN
LEVER_SEAT_PROUD = 10.0
LIFT_ROD_LEN = _up_to_tenth(BACK_BLOCK_OUTER_Z - FRONT_BLOCK_Z0 + LEVER_SEAT_PROUD)
LIFT_ROD_Z0 = BACK_BLOCK_OUTER_Z - LIFT_ROD_LEN

# MHA-114 return spring: the blade rides the back strap's flank.  The inset
# from the strap's inner face keeps the whole 4.0-wide blade on the flank at
# every split of P and every strap thickness in its .X band (the worst case is
# the thinnest strap hard back: inner face 0.8 aft of the nominal one), which
# the support-layout gate proves.
SPRING_BLADE_INSET = 1.0
SPRING_Z = STRAP_Z_INNER[1] + SPRING_BLADE_INSET + SPRING_W / 2.0
