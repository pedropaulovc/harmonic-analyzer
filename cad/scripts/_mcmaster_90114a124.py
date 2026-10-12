"""Pure McMaster 90114A124 catalogue dimensions for its recipe and assemblies.

McMaster 90114A124 product table and 2-D drawing read live on 2026-10-09:
https://www.mcmaster.com/90114A124/. The smallest brass fillister in that
series is #2-56, close to M2. Head +Y, shank -Y, bearing plane Y=0.
No vendor solid was harvested; secondary head/thread details use the existing
catalogue-only fillister-family recipe, not a claimed vendor replica.
"""

from __future__ import annotations

SKU = "90114A124"
THREAD = "#2-56"
MAJOR_DIA = 0.086 * 25.4
LENGTH = 0.25 * 25.4
HEAD_H = 0.083 * 25.4
HEAD_DIA = 0.14 * 25.4
PITCH = 25.4 / 56.0

FILLISTER_SIZE = (MAJOR_DIA, LENGTH, HEAD_H, HEAD_DIA, PITCH)
