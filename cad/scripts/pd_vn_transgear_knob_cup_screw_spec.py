"""Pure stock specification for the MHA-PD-VN-71 knob-cup screw.

McMaster 91794A079, 18-8 stainless slotted fillister #2-56 UNC-2A x 3/8,
fully threaded, flat tip, ASME B18.6.3 (product page read live 2026-11-20,
https://www.mcmaster.com/91794A079/; see ``_mcmaster_91794a079``).  One screw on the
knob axis holds the MHA-PD-16 cup on the MHA-PD-08 journal's rear end (owner
ruling 2026-11-20 (Pedro), #2425).  The stock recipe retains its supplied
frame: head +Y, shank -Y, under-head plane Y=0.

This module reads no part: the joint (the grip in the cup's web, the
engagement and the reach in the journal's rear tap, the web hole round the
under-head fillet) is asserted in ``pd_transgear_knob_cup_spec``, which
reads it.
"""

from __future__ import annotations

from _mcmaster_91794a079 import FILLISTER_SIZE

SKU = "91794A079"
THREAD = "#2-56"
MAJOR_DIA, LENGTH, HEAD_H, HEAD_DIA, PITCH = FILLISTER_SIZE

_IN = 25.4
# ASME B18.6.3-2013 (https://www.finesz.com/pic/ASMEB18.6.3-2013.pdf, the
# source pd_vn_transgear_arm_plate_screw_spec reads): a machine screw to
# 1 in long is supplied +0/-.03 on its length; the under-head fillet runs to
# R .15D, so its envelope under the head is Ø1.3D; the point chamfer runs to
# two pitches, threads that are not full.
LENGTH_MINUS = 0.03 * _IN
LENGTH_MIN = LENGTH - LENGTH_MINUS
UNDER_HEAD_FILLET_RADIUS_MAX = 0.15 * MAJOR_DIA
UNDER_HEAD_FILLET_ENVELOPE_DIA = MAJOR_DIA + 2.0 * UNDER_HEAD_FILLET_RADIUS_MAX
POINT_CHAMFER_LENGTH_MAX = 2.0 * PITCH
