r"""Pure pinion-cam geometry consumed by part and assembly recipes.

Keep drawing-only notes and annotation contracts out of this module so edits to
manufacturing-sheet text cannot invalidate the drive-train assembly recipe.

U28 (user, 2026-09-23): the lift rod moved out to 18.5 from the pivot so the
plain strap clears the collar by placement (U12), and the collar grew to keep a
2.0+ mm thin-side wall at the printed worst case (U27).  The photographed
collar reads ~2.4x the rod diameter (ch25 page002_img01), so Ø14.6 is also the
more faithful size.  The former raised set-pin dome is gone: a pad proud of a
turned OD cannot be turned, so the M2.5 set screw now sits sub-flush in the
thick wall, which never meets the follower over the whole engage throw.
"""

from __future__ import annotations

CAM_OD = 14.6  # K = OD/2 - ECC = 5.3 above the bore axis -> 2.10 thin-side wall
CAM_LEN = 9.0  # collar length along the rod
ECC = 2.0  # bore offset -> 4.0 full lift; holds the photographed -71.8 deg lever
# U27 (Main, 2026-09-23): the cam is set-screwed to the lift rod, so its bore
# needs only a slip fit -- a stock 6.4 mm reamer, not a 15 um band.
BORE = 6.40  # stock 6.4 mm reamer; slip fit on the Ø6.35 lift rod
SET_SCREW_Z = 4.5  # M2.5 set-screw axis station from the front face (mid-length)
TAP_DRILL_DIA = 2.05  # M2.5 x 0.45 coarse-thread tap drill

THIN_SIDE_WALL = CAM_OD / 2.0 - BORE / 2.0 - ECC
THICK_SIDE_WALL = CAM_OD / 2.0 - BORE / 2.0 + ECC  # holds the sub-flush M2.5 x 5
if THIN_SIDE_WALL < 1.5:
    raise AssertionError(
        f"pinion cam has only {THIN_SIDE_WALL:.3f} mm wall on its thin side"
    )
