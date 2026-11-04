"""Shared bar section and column-clamp seating depths, in millimetres.

Pure interface constants only: bar, latch and clamp consumers must not depend
on the clamp's bore, ear-hole contract or drawing checks.
"""

from __future__ import annotations

# The two clamped bars (MHA-PD-07 support bar, the magnifier's wheel bar)
# are one stock section deep: the user's 2026-10-15 ruling thickened it to 9.5
# (rule 18 engagement for the MHA-PD-VN-57 pivot screw), growing REARWARD so
# both front faces stay on the platen-back plane. #290 snaps it to .374.
BAR_DEPTH = 9.4996
# The column-axis plane to the bars' front faces (machine z -112.014 to the
# shared -138.9126 platen-back plane): fixed, so the arc gives up what the bar
# gains. #290 snaps it to 1.059, which leaves the arc exactly .685.
BAR_FRONT_DEPTH = 26.8986
ARC_DEPTH = BAR_FRONT_DEPTH - BAR_DEPTH  # bar back face to the column-axis plane
