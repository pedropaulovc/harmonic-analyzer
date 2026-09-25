"""Fit-up settings for the pinion rig that the prints state and no build reads.

Codex #854 P1: MHA-A03 sets the front block with a feeler before its base
seats are spotted, and the worst-case axial gates read the same band.  It lives
here, outside pinion_rig_layout, so a printed band never re-keys the parts and
assemblies that import the layout.  Only tests and drawing steps import this
module.
"""

from __future__ import annotations

from pinion_rig_layout import FRONT_BLOCK_FEELER

# Ruled band on the fit-up feeler between the front strap's outer face and the
# front block.  The step prints FEELER +/- BAND, and that is also the cluster's
# whole axial end play.
FRONT_BLOCK_FEELER_BAND = 0.10

__all__ = ["FRONT_BLOCK_FEELER", "FRONT_BLOCK_FEELER_BAND"]
