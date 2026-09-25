"""Fit-up settings for the pinion rig that the prints state and no build reads.

Codex #854 P1: MHA-A03 sets the front block with a feeler before its base
seats are spotted, and the worst-case axial gates read the same band.  Both
values live in pinion_rig_layout, because the worst fitted stack there sizes
the torque shaft from the band; this module is the print-facing import point
for the fit-up step.  Only tests and drawing steps import it.
"""

from __future__ import annotations

from pinion_rig_layout import (
    DRUM_END_SHIM,
    DRUM_END_SHIM_SET_ERROR,
    FRONT_BLOCK_FEELER,
    FRONT_BLOCK_FEELER_BAND,
)

# MHA-062's drilling shim is its own leaf (Main, #858), printed on the
# shaft's drilling note; the fit-up step names both.  Both are stock leaves of
# one purchased set, pinned like any other bought part: Starrett 66MA metric
# thickness gage, 20 straight tempered-steel leaves 0.05-1.00 mm in 0.05 steps
# (starrett.com cat-no 66MA, EDP 55974, read 2026-09-25).
FEELER_GAGE = "STARRETT 66MA METRIC THICKNESS GAGE (EDP 55974)"
FEELER_GAGE_LEAVES_MM = tuple(round(0.05 * k, 2) for k in range(1, 21))
for _leaf in (FRONT_BLOCK_FEELER, DRUM_END_SHIM):
    if round(_leaf, 2) not in FEELER_GAGE_LEAVES_MM:
        raise AssertionError(f"{_leaf} mm is not a leaf of the {FEELER_GAGE}")

__all__ = [
    "DRUM_END_SHIM",
    "DRUM_END_SHIM_SET_ERROR",
    "FEELER_GAGE",
    "FEELER_GAGE_LEAVES_MM",
    "FRONT_BLOCK_FEELER",
    "FRONT_BLOCK_FEELER_BAND",
]
