"""McMaster 90283A193 catalog dimensions in mm, without CAD dependencies.

MHA-158, the transgear knob retaining screw: zinc-plated steel slotted pan
head, 8-32 x 7/16, fully threaded, flat tip.  Source: the live McMaster
90283A pages (``transgear-evidence/mcmaster-skus.md``, R4, 2026-09-30).  The
90283A191 (5/16) and 90283A192 (3/8) rows are verified: 8-32 UNC class 2A,
length under the head, fully threaded, flat tip, zinc-plated steel, pan head
Ø0.322 in x 0.096 in high.  For 90283A193 the evidence records only that its
page resolves in the same series at 7/16; its head, thread class, tip and
finish are [INFERENCE] from those verified rows (one head across the series).
No vendor model is downloaded; the pan recipe
(``diagnostics/diag_mcmaster_pan.py``) builds it from these numbers.

Frame (the stock recipe's): axis +Y, head up, the under-head bearing face at
y = 0 (Top Plane).  It seats on the knob cup's counterbore floor
(``transgear_knob_cup_spec.FLOOR``) and the shank runs down (-Y) through the
cup's bore into the knob shaft's #8-32 rear tap.
"""

IN = 25.4

SKU = "90283A193"
THREAD = "#8-32"
THREAD_CLASS = "2A"
SHANK_DIA = 0.164 * IN
SHANK_LEN = 7.0 / 16.0 * IN  # under the head
# (plus, minus): ASME B18.6.3 machine-screw length tolerance, to 1 in long.
SHANK_LEN_BAND = (0.0, 0.03 * IN)
HEAD_DIA = 0.322 * IN
HEAD_H = 0.096 * IN
PITCH = IN / 32.0
# The incomplete first thread at the flat tip does not count toward
# engagement: one pitch, as the contract's §7 counts it.
FIRST_THREAD_LOSS = PITCH
