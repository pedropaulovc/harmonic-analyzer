r"""Strip section of the MHA-114 pinion return leaf spring.

Split out of ``pinion_spring_geometry`` (Main, 2026-09-24): the swing-rig
layout (``SPRING_Z`` follows the width) and the harmonic base (the foot screw
passes through the thickness) read only the section, so a change to the
spring's formed profile re-keys neither the layout importers nor the base.
"""

from __future__ import annotations

# C51000 phosphor bronze, spring temper, 0.020 in strip.  O1-b, user
# 2026-09-24, supersedes 0.5 x 5.0: the 6.0 width lets the preset clear both
# the 1.5x preload margin at the formed band's low end and SF 1.5 on yield
# engaged, which 5.0 could not do at once.
THICK = 0.5
WIDTH = 6.0
