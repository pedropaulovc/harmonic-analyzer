r"""Geometry-only contract for the separate MHA-DT-15 pinion grip crossrod."""

from __future__ import annotations

# Preserve the released crossrod local origin.  The installed rod axis passes
# through the component origin and spans local Y -32..+33.024; the integral
# head and cross-hole belong to MHA-DT-22.  #290 (owner ruling): the rod is
# 1/4 cold-finished bar (OnlineMetals 4791, 1018 CF) used as received,
# modelled at its .250 nominal, and is bonded into MHA-DT-22's reamed hole
# rather than pressed.
ROD_DIA = 6.35  # 1/4
# As-received cold-finished bar: the supplier states no diameter tolerance, so
# the bar's ASTM A108 standard governs (ASTM A29 cold-drawn rounds to 1-1/2 in,
# carbon .28 % max: .000/-.002 in).  Not printed (MHA-DT-15 is not machined on
# its diameter); it bounds the bond gap.
ROD_DIA_BAND = (0.0, -0.0508)  # (upper, lower) deviations
ROD_DOWN = 32.0
ROD_SPAN = 65.024  # 2.56
ROD_UP = ROD_SPAN - ROD_DOWN
