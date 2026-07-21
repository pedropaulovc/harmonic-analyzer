r"""Pure pinion-cam geometry consumed by part and assembly recipes.

Keep drawing-only notes and annotation contracts out of this module so edits to
manufacturing-sheet text cannot invalidate the drive-train assembly recipe.
"""

from __future__ import annotations

CAM_OD = 9.2  # collar OD
CAM_LEN = 9.0  # collar length along the rod
ECC = 1.0  # bore offset from the collar OD axis -> 2.0 full lift
BORE = 6.35  # rides the Ø6.35 lift rod
BOSS_DIA = 3.2  # set-pin dome, proud of the OD on the heavy (thick) side
BOSS_PROUD = 0.5  # boss height proud of the OD
BOSS_Z = 1.7  # boss axis station from the front face
