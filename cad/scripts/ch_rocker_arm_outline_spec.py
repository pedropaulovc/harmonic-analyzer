r"""Stable rocker-arm outline shared by native recipes and inspection checks.

Pure dimensional data, independent of the hub, fit and GD&T implementation in
``ch_rocker_arm_spec``. The live oblique-trammel carrier consumes the outline
without that guarded owner; consumers needing hub or fit data import it directly.
The retired standalone tooling has no native recipe or cache key.
"""

from __future__ import annotations

import math

import _rocker_interface

# --- Nominal geometry (DIMENSIONS.md "Chapter 14"). These MUST match the
# constants in build_ch_rocker_arm.py (the test cross-checks the load-bearing
# ones), so the drawing's view math reads the same solid the part builds. ---
ARM_THICKNESS = 2.5  # plate thickness, Z (p.27 callout)
TOP_ARC_LEN = 292.1  # top edge arc length = 11.5" (ch.30 back view)
BOT_ARC_LEN = 266.7  # bottom edge arc length = 10.5" (ch.30 back-view sketch)
TIP_FACE = 5.588  # 0.22" tip face, perpendicular to the top edge

# --- Derived spans (equations of the primitives; mirror build_ch_rocker_arm). ---
R_TOP = _rocker_interface.CURVE_RADIUS

_ALPHA_TOP = (TOP_ARC_LEN / 2.0) / R_TOP
_ALPHA_BOT = (BOT_ARC_LEN / 2.0) / _rocker_interface.R_BOTTOM
TOP_END_X = R_TOP * math.sin(_ALPHA_TOP)
TOP_END_Y = _rocker_interface.CENTER_Y - R_TOP * math.cos(_ALPHA_TOP)
BOT_END_X = _rocker_interface.R_BOTTOM * math.sin(_ALPHA_BOT)

# Rod tip: the top-arc endpoint pushed out along the radius by the tip face.
_RAD_X = TOP_END_X / R_TOP
ROD_TIP_X = TOP_END_X + TIP_FACE * _RAD_X  # widest half-span (~146.25)

# The amplitude bar's foot rides the top edge, and at d = 0 its cheeks pass
# over this arm's hub, so the print controls the edge's height over the pivot
# axis directly, on the nominal mirror plane, one-sided: the edge may only come out
# high (user ruling 2026-09-26). The 808.00 centre distance is then REF, and
# the R800 governs only the curvature. With the amplitude bar's one-sided
# notch (ch_amplitude_bar_spec.BOTTOM_NOTCH_DEPTH_BAND) a bar can rest at most
# 1.0 higher than nominal: a steady lever tilt of ~0.45 deg on that channel.
# Its fundamental moves at most 0.0036 mm (0.04 % of the d = 88 term) across
# the stations: error_budget.hook_displacement with the edge 0.5 high and the
# notch 0.5 shallow (test_rocker_bank_layout pins both numbers).
# drawing-simplicity-policy.md `How the repository implements the guidelines` (Codex #936 PRRT_kwDOPHDy386mV3AO): the band is the part's,
# on a model dimension -- build_ch_rocker_arm's hidden TopEdgeReference sketch,
# whose one printed dimension IS this height and drives the arcs' centre.
TOP_EDGE_ABOVE_PIVOT = _rocker_interface.CENTER_Y - _rocker_interface.PIVOT_MID_Y - R_TOP  # 8.0
TOP_EDGE_BAND = (0.50, 0.0)  # (upper, lower)
