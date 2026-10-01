r"""McMaster 91829A205 catalog dimensions in mm, without CAD dependencies.

MHA-168, the transgear pivot screw: slotted precision shoulder screw, 18-8
stainless steel, passivated (MS51575-11).  Live page (``transgear-evidence/
mcmaster-skus.md``, R1, re-verified 2026-09-30): shoulder Ø3/16 (-0.001/0 in)
x 1/2 (0/+0.002 in); 8-32 UNC-2A x 3/16; slotted head Ø5/16 x 5/32.  The
slot, thread neck and chamfers are the vendor model's
(``cad/references/mcmaster/91829A205.SLDPRT``, SHA-256 bb7a805e...4601c,
harvested 2026-09-30; dump ``cad/out/reports/mcmaster-91829A205-dump.json``,
coordinator ruling R9-7): under the shoulder's END face (y = -SHOULDER_LEN)
a R0.5715 fillet runs into a Ø3.0226 neck, flat to 1.1938 below that face,
then a 45° ramp back to the thread major, so the full thread starts 1.7653
below the shoulder's end face.

Frame (the stock recipe's): axis +Y, head up, the under-head shoulder face at
y = 0 (Top Plane); the shoulder runs down to y = -SHOULDER_LEN and the thread
below it.  The joint it makes with the arm, spacer and bar is judged in
``transgear_hanger_joints``.
"""

from __future__ import annotations

IN = 25.4

SKU = "91829A205"
SHOULDER_DIA = 3.0 / 16.0 * IN
SHOULDER_DIA_LIMITS = (-0.001 * IN, 0.0)
SHOULDER_LEN = 0.5 * IN
SHOULDER_LEN_LIMITS = (0.0, 0.002 * IN)
THREAD = "#8-32"
THREAD_CLASS = "2A"
THREAD_MAJOR = 0.164 * IN
THREAD_LEN = 3.0 / 16.0 * IN
PITCH = IN / 32.0
HEAD_DIA = 5.0 / 16.0 * IN
HEAD_H = 5.0 / 32.0 * IN
SLOT_WIDTH = 1.27  # vendor: 0.16 x head Ø
SLOT_DEPTH = 1.5875  # vendor: 0.4 x head height
HEAD_CHAMFER = 0.257969  # vendor: 0.0325 x head Ø, 45°
TIP_CHAMFER = 0.374904  # vendor: 0.09 x thread major, 45°
# Thread neck under the shoulder's end face (the vendor's Cut-Revolve1).
NECK_DIA = 3.0226
NECK_FILLET_R = 0.5715  # shoulder end-face corner into the neck
NECK_FLAT_END = 1.1938  # flat neck ends this far below the shoulder end face
# The 45° ramp regains the major here, measured from the shoulder end face.
FULL_THREAD_START = NECK_FLAT_END + (THREAD_MAJOR - NECK_DIA) / 2.0
# The incomplete first thread at the tip does not count toward engagement:
# one pitch, as the contract's §7 counts it.
FIRST_THREAD_LOSS = PITCH
