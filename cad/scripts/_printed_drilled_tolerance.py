"""The title block's drilled-hole acceptance allowance, in millimetres."""

from __future__ import annotations

import _config


def drilled_oversize_mm() -> float:
    """The title block's DRILLED HOLES plus allowance (its minus is 0)."""
    return float(_config.title_block("drilled_hole")["plus_mm"])
