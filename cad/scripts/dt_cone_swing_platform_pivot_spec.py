"""The cone swing platform's pivot bore on the stock 91829A560 shoulder.

Kept apart from ``dt_cone_swing_platform_spec`` (which reads the machine-frame
cone line) because the cone set stack carries this bore's float to the cone
tip-air stack, and the cone gear sheets print that stack: the gear must not
depend on the channel table that places the line.
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec, blind_cut_dia_mm

# The platform swings on the stock 1/4-in shoulder (6.3246-6.350). The feel
# set takes up the pivot's translation under the mesh load, but the cone tip
# air books its float (dt_cone_tip_air, via cone_set_stack.PIVOT_BORE_FLOAT_MM),
# so the bore is reamed Ø6.350 H7 on the shoulder: radial float <= 0.020
# (Main ruling 2026-10-10, critical bore running fit).
# Native Hole Wizard 1/4 drill-size hole carrying the band, called out REAM.
PIVOT_HOLE_SPEC = HoleSpec("drilled_fractional", "1/4")
PIVOT_HOLE_DIA = blind_cut_dia_mm(PIVOT_HOLE_SPEC)
PIVOT_HOLE_BAND = tuple(
    float(v) for v in _config.fit("cone_drum_oblique_mesh", "pivot_bore_band_mm")
)  # (upper, lower)
