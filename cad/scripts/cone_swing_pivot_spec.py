"""Machine-frame station of the cone swing pivot screw.

The cone swing platform turns on its #10-24 shoulder screw, which threads into
the harmonic base.  The base drills that seat here; the drive train derives the
same point as the cone journal line at ``PIVOT_STATION`` and asserts the two
agree exactly, so a cone-line move that strands the seat fails the drive-train
build instead of drifting.

Pure data: the base's part recipe reads the point without pulling the gear-train
geometry that derives the cone line.
"""

from __future__ import annotations


# (x, z) in the machine frame, mm.  Equal to the drive train's
# cone_station(PIVOT_STATION) to the last bit.
PIVOT_SCREW_XZ = (-87.68263981674521, 96.01937088764276)
