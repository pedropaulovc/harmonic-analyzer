"""Cone-family dimensional math shared by authoring and saved-model readback.

Separate from the builder so topology validation does not import simplified-part
derivation or saving machinery into drawing recipes.
"""

from __future__ import annotations

import math

from dt_cone_gear_spec import (
    MM_PER_IN,
    STANDARD_TOOTH_THICKNESS,
    bore_dia_mm,
    bore_flat_segment_area_mm2,
    floor_dip_mm,
    floor_tmin,
    outside_dia_mm,
    tooth_thickness_mm,
)
from involute_gear import DP, gap_area_in_disc, gear_facts


def bore_area_mm2(teeth: int) -> float:
    """Area of the D-bore: the round bore less the segment the flat keeps."""
    return math.pi * (bore_dia_mm(teeth) / 2.0) ** 2 - bore_flat_segment_area_mm2(teeth)


def thicken_in(teeth: int) -> float:
    """Modelled tooth thickness over standard, inches (deepened mesh)."""
    return (tooth_thickness_mm(teeth) - STANDARD_TOOTH_THICKNESS) / MM_PER_IN


def addendum_extra_in(teeth: int) -> float:
    """Tip radius over the standard ``(N + 2) / DP / 2``, inches."""
    return outside_dia_mm(teeth) / MM_PER_IN / 2.0 - (teeth + 2.0) / DP / 2.0


def _mesh_kwargs(teeth: int) -> dict[str, float]:
    return {
        "thicken_in": thicken_in(teeth),
        "addendum_extra_in": addendum_extra_in(teeth),
        "tmin": floor_tmin(teeth),
        "floor_dip_in": floor_dip_mm(teeth) / MM_PER_IN,
    }


def cone_facts(teeth: int) -> dict[str, float]:
    """``gear_facts`` for one configuration of the deepened cone mesh."""
    return gear_facts(teeth, **_mesh_kwargs(teeth))


def cone_gap_area_in_disc(teeth: int) -> float:
    """``gap_area_in_disc`` for one configuration of the deepened cone mesh."""
    return gap_area_in_disc(teeth, **_mesh_kwargs(teeth))
