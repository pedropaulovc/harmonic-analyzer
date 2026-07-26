r"""Pure pinion-cam geometry consumed by part and assembly recipes.

Keep drawing-only notes and annotation contracts out of this module so edits to
manufacturing-sheet text cannot invalidate the drive-train assembly recipe.
"""

from __future__ import annotations

CAM_OD = 10.32  # reclosed v2 collar OD: keeps 0.575 thin-side wall
CAM_LEN = 9.0  # collar length along the rod
ECC = 1.4  # v2 linkage closure: bore offset -> 2.8 full lift
BORE = 6.37  # nominal reamed running fit on the Ø6.35 lift rod
BOSS_DIA = 3.2  # set-pin dome, proud of the OD on the heavy (thick) side
BOSS_PROUD = 0.5  # boss height proud of the OD
BOSS_Z = 1.7  # boss axis station from the front face
TAP_DRILL_DIA = 2.05  # M2.5 x 0.45 coarse-thread tap drill

THIN_SIDE_WALL = CAM_OD / 2.0 - BORE / 2.0 - ECC
if THIN_SIDE_WALL < 0.5:
    raise AssertionError(
        f"pinion cam has only {THIN_SIDE_WALL:.3f} mm wall on its thin side"
    )
