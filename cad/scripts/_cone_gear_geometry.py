"""Cone-family dimensional math shared by authoring and saved-model readback.

Separate from the builder so topology validation does not import simplified-part
derivation or saving machinery into drawing recipes.
"""

from __future__ import annotations

import math

from dt_cone_gear_spec import bore_dia_mm, bore_flat_segment_area_mm2

# Native equation curves evaluate document lengths in inches; core scales them.
R_CLEAR_MM = 60.0


def bore_area_mm2(teeth: int) -> float:
    """Area of the D-bore: the round bore less the segment the flat keeps."""
    return math.pi * (bore_dia_mm(teeth) / 2.0) ** 2 - bore_flat_segment_area_mm2(
        teeth
    )
