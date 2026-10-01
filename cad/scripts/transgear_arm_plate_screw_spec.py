r"""McMaster 91790A194 catalog dimensions in mm, without CAD dependencies.

MHA-166, the transgear arm-plate screws (two): 18-8 stainless steel slotted
oval head, 82 deg, 8-32 UNC class 2A x 1/2, fully threaded, bright, ASME
B18.6.3.  Live page (``transgear-evidence/mcmaster-skus.md``, R3 and the
round-7 family check, 2026-09-30): head Ø0.312 in, total head height 0.152
in of which the oval top (crown) is 0.052 in; the length is measured from the
TOP OF THE BEVEL (not from the crown, not from under the head).  The page
gives no slot, tip or crown-radius figures: the slot and tip follow the
repo's slotted-machine-screw laws and the crown is a spherical cap through
the head rim, all [INFERENCE] (``diagnostics/diag_mcmaster_oval.py``).  No
vendor model is downloaded.

Frame (the stock recipe's): axis +Y, head up, the top of the bevel -- the
plane that sits flush with the plate's rear face -- at y = 0 (Top Plane).
The crown rises above it to y = CROWN_H; the shank runs down to
y = -LENGTH.  The joint is judged in ``transgear_hanger_joints``.
"""

from __future__ import annotations

IN = 25.4

SKU = "91790A194"
THREAD = "#8-32"
THREAD_CLASS = "2A"
THREAD_MAJOR = 0.164 * IN
THREAD_MAJOR_MIN = 0.1571 * IN  # UNC-2A minimum major (ASME B1.1)
LENGTH = 0.5 * IN  # from the top of the bevel
PITCH = IN / 32.0
HEAD_DIA = 0.312 * IN  # at the top of the bevel
HEAD_H = 0.152 * IN  # total, crown included
CROWN_H = 0.052 * IN
BEVEL_H = HEAD_H - CROWN_H
HEAD_ANGLE_DEG = 82.0
# The incomplete first thread at the tip does not count toward engagement:
# one pitch, as the contract's §7 counts it.
FIRST_THREAD_LOSS = PITCH
