r"""Strip section of the MHA-114 pinion return leaf spring.

Split out of ``pinion_spring_geometry`` (Main, 2026-09-24): the swing-rig
layout (``SPRING_Z`` follows the pad and strip widths: the pad is set a
gage leaf off the back block) and the harmonic base (the foot screw passes
through the thickness, at its station east of the pivot) read only the section, so a change to the
spring's formed profile re-keys neither the layout importers nor the base.
"""

from __future__ import annotations

# C51000 phosphor bronze, spring temper, 0.020 in strip (user, O1, 2026-09-24).
THICK = 0.5
WIDTH = 5.0
WIDTH_PLACES = 2  # StripWidth prints .XX (pinion_spring_spec)

# Screw-down pad width (pinion_spring_geometry has the rest of the pad).
PAD_WIDTH = 9.5
PAD_WIDTH_PLACES = 2  # PadWidth prints .XX (pinion_spring_spec)

# The foot screw stands this far east of the swing pivot axis (O5, Main
# 2026-09-24, option c; pinion_spring_geometry places the pad hole on it).
# The harmonic base seats the screw from it, so it lives with the section.
SCREW_EAST_OF_PIVOT = 20.0
