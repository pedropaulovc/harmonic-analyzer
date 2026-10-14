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

from _inch import inch

# All-inch experiment: Ø9/16 x 1/16 eccentricity (1/8 full lift), each the
# nearest 1/16.  The park gap closes on the strap's 7/32 follower drop
# (dt_pinion_bracket_geometry) and the engaged lever on the parked tip gap
# (alignment_pinion.disengaged_tip_gap_mm).
CAM_OD = inch(9, 16)
CAM_LEN = inch(3, 8)  # collar length along the rod
ECC = inch(1, 16)  # bore offset; the parked tip gap closes the engaged lever
# U27 (Main, 2026-09-23): the cam is set-screwed to the lift rod, so its bore
# needs only a slip fit -- a stock 6.4 mm reamer, not a 15 um band.  Fit size:
# it follows the Ø1/4 in lift rod plus the 0.02-0.10 slip (dt_pinion_cam_spec).
BORE = 6.40  # stock 6.4 mm reamer; slip fit on the Ø6.35 lift rod
SET_SCREW_Z = CAM_LEN / 2.0  # M2.5 set-screw axis station from the front face
TAP_DRILL_DIA = 2.05  # M2.5 x 0.45 coarse-thread tap drill (vendor M2.5 screw)

THIN_SIDE_WALL = CAM_OD / 2.0 - BORE / 2.0 - ECC
THICK_SIDE_WALL = CAM_OD / 2.0 - BORE / 2.0 + ECC  # holds the sub-flush M2.5 x 5
if THIN_SIDE_WALL < 1.5:
    raise AssertionError(
        f"pinion cam has only {THIN_SIDE_WALL:.3f} mm wall on its thin side"
    )
