r"""Strip section of the MHA-DT-24 pinion return leaf spring.

Split out of ``pinion_spring_geometry`` (Main, 2026-09-24): the swing-rig
layout (``SPRING_Z`` follows the pad and strip widths: the pad is set a
gage leaf off the back block) and the harmonic base (the foot screw passes
through the thickness, at its station east of the pivot) read only the section, so a change to the
spring's formed profile re-keys neither the layout importers nor the base.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit

MM_PER_IN = 25.4
# #290: the sheet prints decimal inch; the rig layout and the drive train read
# its printed rows through this unit.
UNIT = drawing_unit("parts/dt-pinion-spring", _config.parts("dt-pinion-spring"))

# 17-7 PH (UNS S17700) Condition C strip, 0.015 in thick, sheared 1/4 in wide
# from McMaster-Carr 2325K19 (6 in x 50 in roll).  #859 ruling 4 (Main,
# 2026-09-25) supersedes the C51000 H08 0.020 x 6.0 strip of O1-b: at that
# stock's thickness band no preset cleared both SF 1.5 on yield at the stiff
# corner and the 1.5x preload margin at the soft corner under the CAD-derived
# gravity moments (ruling 3 material search).
THICK = 0.015 * MM_PER_IN  # 0.381
WIDTH = 0.25 * MM_PER_IN  # 6.35
# The thickness band is (upper, lower) deviations in mm, read through
# ``_fit_deviations.deviations``: 2325K19 lists -0.00075 to +0.00075 in (vendor
# page read 2026-09-25).  The sheared width prints at .XX, so its readers take
# the band that print states (``_printed_tolerance.printed_deviations``).
THICK_BAND = (0.00075 * MM_PER_IN, -0.00075 * MM_PER_IN)
WIDTH_PLACES = 2  # StripWidth prints .XX (dt_pinion_spring_spec)

# Screw-down pad width (dt_pinion_spring_geometry has the rest of the pad).
# #290: .38, whose half (.19) is the printed hole station from the pad's edge.
PAD_WIDTH = 9.652  # .38
PAD_WIDTH_PLACES = 2  # PadWidth prints .XX (dt_pinion_spring_spec)

# The foot screw stands this far east of the swing pivot axis (O5, Main
# 2026-09-24, option c; dt_pinion_spring_geometry places the pad hole on it).
# The harmonic base seats the screw from it, so it lives with the section.
SCREW_EAST_OF_PIVOT = 20.0
