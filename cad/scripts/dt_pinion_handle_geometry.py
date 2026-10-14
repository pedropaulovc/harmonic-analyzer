r"""Geometry-only contract for the separate MHA-DT-015 pinion grip crossrod."""

from __future__ import annotations

from _inch import inch

# Preserve the released crossrod local origin.  The installed rod axis passes
# through the component origin and spans local Y -1-1/4..+1-5/16; the integral
# head and cross-hole belong to MHA-DT-022.  R1 (U27 precedent): the rod is
# Ø1/4 cold-finished bar used as received, modelled at its nominal, and is
# bonded into MHA-DT-022's reamed hole rather than pressed.
ROD_DIA = inch(1, 4)
# As-received cold-finished bar: ISO h11 for drawn bright bar (0/-0.075).
# Not printed (MHA-DT-015 is not machined on its diameter); it bounds the bond gap.
ROD_DIA_BAND = (0.000, -0.075)  # (upper, lower) deviations
ROD_DOWN = inch(5, 4)
ROD_UP = inch(21, 16)
ROD_SPAN = ROD_DOWN + ROD_UP
