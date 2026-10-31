r"""Pure pinion-cam geometry consumed by part and assembly recipes.

Keep drawing-only notes and annotation contracts out of this module so edits to
manufacturing-sheet text cannot invalidate the drive-train assembly recipe.

U28 (user, 2026-09-23): the lift rod moved out to 18.5 from the pivot so the
plain strap clears the collar by placement (U12), and the collar grew to keep a
2.0+ mm thin-side wall at the printed worst case (U27).  The photographed
collar reads ~2.4x the rod diameter (ch25 page002_img01), so Ø14.6 is also the
more faithful size.  The former raised set-pin dome is gone: a pad proud of a
turned OD cannot be turned, so the #2-56 set screw sits sub-flush in the
thick wall, which never meets the follower over the whole engage throw.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, THREAD_MAJOR_MM, blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM

CAM_OD = 14.6  # K = OD/2 - ECC = 5.3 above the bore axis -> 2.11 thin-side wall
CAM_LEN = 9.0  # collar length along the rod
ECC = 2.0  # bore offset -> 4.0 full lift; holds the photographed -71.8 deg lever
# U27 (Main, 2026-09-23): the cam is set-screwed to the lift rod, so its bore
# needs only a slip fit.  #290 (owner ruling): the owned .2510 reamer cuts it;
# the other nominals stay at their drive-train values and print in inches.
BORE = 6.3754  # .2510 in reamer; slip fit on the 1/4-in lift rod
# 4.1 balances the end-face walls at the printed .XX grade: the rear face
# stacks both the collar-length and station bands, while the front stacks one.
SET_SCREW_Z = 4.1  # #2-56 set-screw axis station from the front face
SET_SCREW_HOLE_SPEC = HoleSpec(
    kind="tapped", size="#2-56", end="through_next", thread_class="2B"
)
TAP_DRILL_DIA = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC)
SET_SCREW_MAJOR_DIA = THREAD_MAJOR_MM[SET_SCREW_HOLE_SPEC.size]

THIN_SIDE_WALL = CAM_OD / 2.0 - BORE / 2.0 - ECC
THICK_SIDE_WALL = CAM_OD / 2.0 - BORE / 2.0 + ECC  # seats the loose 3/16-in screw
if THIN_SIDE_WALL < WALL_FLOOR_MM:
    raise AssertionError(
        f"pinion cam has only {THIN_SIDE_WALL:.3f} mm wall on its thin side"
    )
