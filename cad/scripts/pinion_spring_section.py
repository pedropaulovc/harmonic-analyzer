r"""Strip section of the MHA-114 pinion return leaf spring.

Split out of ``pinion_spring_geometry`` (Main, 2026-09-24): the swing-rig
layout (``SPRING_Z`` follows the pad and strip widths: the pad is set a
gage leaf off the back block) and the harmonic base (the foot screw passes
through the thickness, at its station east of the pivot) read only the section, so a change to the
spring's formed profile re-keys neither the layout importers nor the base.
"""

from __future__ import annotations

MM_PER_IN = 25.4

# 17-7 PH (UNS S17700) Condition C strip, 0.015 in thick, sheared 6.50 mm
# wide from McMaster-Carr 2325K19 (6 in x 50 in roll).  #859 ruling 4
# (Main, 2026-09-25) supersedes the C51000 H08 0.020 x 6.0 strip of O1-b:
# at that stock's thickness band no preset cleared both SF 1.5 on yield at
# the stiff corner and the 1.5x preload margin at the soft corner under the
# CAD-derived gravity moments.  The 6.50-mm cut still uses the original
# 6-in-wide Condition-C roll, not a wider purchased strip.
THICK = 0.015 * MM_PER_IN  # 0.381
WIDTH = 6.50
# The thickness band is (upper, lower) deviations in mm, read through
# ``_fit_limits.deviations``: 2325K19 lists -0.00075 to +0.00075 in (vendor
# page read 2026-09-25).  The sheared width prints at .XX, so its readers take
# the band that print states (``_printed_tolerance.printed_deviations``).
THICK_BAND = (0.00075 * MM_PER_IN, -0.00075 * MM_PER_IN)
WIDTH_PLACES = 2  # StripWidth prints .XX (pinion_spring_spec)

# Screw-down pad width (pinion_spring_geometry has the rest of the pad).
PAD_WIDTH = 9.5
PAD_WIDTH_PLACES = 2  # PadWidth prints .XX (pinion_spring_spec)

# The foot screw stands this far east of the swing pivot axis.  Moving it
# 0.7 mm outboard accommodates the higher crest while keeping the blade
# within the photographed 9-13 deg lean into the parked flank.  The harmonic
# base seats the screw from it, so it lives with the section.
SCREW_EAST_OF_PIVOT = 20.7
