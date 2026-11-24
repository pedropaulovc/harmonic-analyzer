"""The cone swing platform's pivot bore on the stock 91829A560 shoulder.

Kept apart from ``dt_cone_swing_platform_spec`` (which reads the machine-frame
cone line) because the cone set stack carries this bore's float to the cone
tip-air stack, and the cone gear sheets print that stack: the gear must not
depend on the channel table that places the line.
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec

# The platform swings on the stock 1/4-in shoulder (6.3246-6.350).  The feel
# set takes up the pivot's translation under the mesh load, but the cone tip
# air books its float (dt_cone_tip_air, via cone_set_stack.PIVOT_BORE_FLOAT_MM).
# Owner ruling 2026-11-24, fit audit question 10: the bore is reamed with the
# .2510 over reamer of the set and prints no band; the shoulder is the gauge
# (it enters and the platform swings free).  This retires the .2500 +.0005
# reamed bore of 2026-10-10 and its 0.020 mm radial float limit: the float is
# now 0.032 mm and the least tip air (the bushing tier) 0.128 mm.
# Native Hole Wizard 1/4 drill-size hole with its diameter overridden to the
# reamer's .2510, called out REAM; the feature carries no tolerance.
PIVOT_HOLE_DIA = 0.2510 * 25.4  # 6.3754, the .2510 reamer
PIVOT_HOLE_SPEC = HoleSpec(
    "drilled_fractional", "1/4", overrides_mm={"HoleDiameter": PIVOT_HOLE_DIA}
)
# ANALYSIS band, never printed: what the .2510 reamer is modelled to cut
# (.2510-.2515).  The float and transfer-punch stacks read it.
PIVOT_HOLE_BAND = tuple(
    float(v) for v in _config.fit("cone_drum_oblique_mesh", "pivot_bore_band_mm")
)  # (upper, lower)
