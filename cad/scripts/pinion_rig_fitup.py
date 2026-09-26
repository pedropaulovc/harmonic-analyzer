"""Fit-up settings for the pinion rig that the prints state and no build reads.

Codex #854 P1: MHA-A03 sets the front block with a feeler before its base
seats are spotted, and the worst-case axial gates read the same band.  Both
values live in pinion_rig_layout, because the worst fitted stack there sizes
the torque shaft from the band; this module is the print-facing import point
for the fit-up step.  Only tests and drawing steps import it.
"""

from __future__ import annotations

from pinion_rig_layout import FRONT_BLOCK_FEELER, FRONT_BLOCK_FEELER_BAND

__all__ = ["FRONT_BLOCK_FEELER", "FRONT_BLOCK_FEELER_BAND"]
