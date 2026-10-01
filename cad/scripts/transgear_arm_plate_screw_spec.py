r"""McMaster 91790A196 catalog dimensions in mm, without CAD dependencies.

MHA-166, the transgear arm-plate screws (two): 18-8 stainless steel slotted
oval head, 82 deg, 8-32 UNC class 2A x 5/8, fully threaded, bright, ASME
B18.6.3, CUT TO FIT at assembly (R9-44): each tip is cut flush with the
MHA-164 arm's front face and the cut edge broken.  With the B18.6.3 length
band (+0/-0.03 in) no fixed-length screw gives 1.5D engagement in the arm's
through tap and also keeps its tip out of the guide-lock sweep, so the screw
is bought long and cut, as MHA-142 is (``post_mount_screw_spec``: built at
its supplied length, trimmed at a cut length, the cut end broken) with
MHA-139's flush tip (``build_drive_train_assembly.HANDLE_SCREW_TIP_Z``).

SKU provenance: 91790A196 is [INFERENCE], the 5/8 in length of the 91790A
series by the 90280A numbering the repo has verified (194 = 1/2 in,
197 = 3/4 in, so 196 = 5/8 in).  It has NOT been read live; the vendor check
is pending.  The series facts were read live on its 3/8 in and 1/2 in
lengths (``transgear-evidence/mcmaster-skus.md``, R3 and the round-7 family
check, 2026-09-30): head Ø0.312 in, total head height 0.152 in of which the
oval top (crown) is 0.052 in; the length is measured from the TOP OF THE
BEVEL (not from the crown, not from under the head).  The page gives no slot,
tip or crown-radius figures: the slot and tip follow the repo's
slotted-machine-screw laws and the crown is a spherical cap through the head
rim, all [INFERENCE] (``diagnostics/diag_mcmaster_oval.py``).  No vendor
model is downloaded.

Frame (the stock recipe's): axis +Y, head up, the top of the bevel -- the
plane that sits flush with the plate's rear face -- at y = 0 (Top Plane).
The crown rises above it to y = CROWN_H; the modelled (installed, cut)
shank runs down to y = -LENGTH = -CUT_LENGTH.  The joint is judged in
``transgear_hanger_joints``.
"""

from __future__ import annotations

import transgear_arm_geometry as ARM
import transgear_arm_plate_geometry as PLATE

IN = 25.4

SKU = "91790A196"  # [INFERENCE] 5/8 in by the 90280A numbering; not read live
THREAD = "#8-32"
THREAD_CLASS = "2A"
THREAD_MAJOR = 0.164 * IN
THREAD_MAJOR_MIN = 0.1571 * IN  # UNC-2A minimum major (ASME B1.1)
PITCH = IN / 32.0
HEAD_DIA = 0.312 * IN  # at the top of the bevel
HEAD_H = 0.152 * IN  # total, crown included
CROWN_H = 0.052 * IN
BEVEL_H = HEAD_H - CROWN_H
HEAD_ANGLE_DEG = 82.0
# The incomplete first thread at the tip does not count toward engagement:
# one pitch, as the contract's §7 counts it.
FIRST_THREAD_LOSS = PITCH

# --- As supplied ---------------------------------------------------------------
STOCK_LENGTH = 0.625 * IN  # from the top of the bevel
# (+, -): ASME B18.6.3 machine-screw length tolerance, as
# rocker_bracket_seat_layout.SCREW_LENGTH_BAND.
STOCK_LENGTH_BAND = (0.0, 0.03 * IN)

# --- As installed: cut to fit ----------------------------------------------------
# The bevel top sits flush with the plate's rear face, so the tip is flush
# with the arm's front face at the plate's over-arm section plus the arm.
CUT_LENGTH = PLATE.THICKNESS_OVER_ARM + ARM.THICKNESS
# The modelled screw is the installed one: placement, interference and the
# joint stack read LENGTH as its length.
LENGTH = CUT_LENGTH
# The cut end's 45 deg deburr, its radial leg; a single MAX limit, as MHA-142's
# CUT_END_BREAK_MAX_MM.  The model carries the maximum.  The part sheet's
# installation note (the registry's ``installation_notes``) prints it.
CUT_END_BREAK_MAX = 0.1
# What the A06 cut step prints for it.
CUT_END_BREAK_TEXT = f"{CUT_END_BREAK_MAX:.1f} MAX"
