r"""Geometry-only contract for the separate MHA-058 pinion grip crossrod."""

from __future__ import annotations

# Preserve the released crossrod local origin.  The installed rod axis passes
# through the component origin and spans local Y -32..+33; the integral head
# and cross-hole belong to MHA-102.  R1 (U27 precedent): the rod is Ø6
# cold-finished bar used as received, modelled at its 6.000 nominal, and is
# bonded into MHA-102's reamed hole rather than pressed.
ROD_DIA = 6.0
# As-received cold-finished bar: ISO h11 for drawn bright bar (0/-0.075).
# Not printed (MHA-058 is not machined on its diameter); it bounds the bond gap.
ROD_DIA_BAND = (0.000, -0.075)  # (upper, lower) deviations
ROD_DOWN = 32.0
ROD_UP = 33.0
ROD_SPAN = ROD_DOWN + ROD_UP
