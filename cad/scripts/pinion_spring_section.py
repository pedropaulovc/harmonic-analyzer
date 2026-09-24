r"""Strip section of the MHA-114 pinion return leaf spring.

Split out of ``pinion_spring_geometry`` (Main, 2026-09-24): the swing-rig
layout (``SPRING_Z`` follows the width) and the harmonic base (the foot screw
passes through the thickness) read only the section, so a change to the
spring's formed profile re-keys neither the layout importers nor the base.
"""

from __future__ import annotations

# C51000 phosphor bronze, spring temper, 0.020 in strip (user, O1, 2026-09-24).
THICK = 0.5
WIDTH = 5.0
