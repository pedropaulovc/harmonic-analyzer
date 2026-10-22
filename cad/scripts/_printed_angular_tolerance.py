"""The title block's general angular acceptance band, in degrees."""

from __future__ import annotations

import _config


def angular_band_deg() -> float:
    """The title block's general angular +/- in degrees."""
    return float(_config.title_block("angular")["value_deg"])
