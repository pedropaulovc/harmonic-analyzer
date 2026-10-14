"""Pure-data manufacturing contract for the platen guide."""

from _gtol_planar import PlanarFace
from _hole_spec import HoleSpec
from _inch import inch
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_platen_spec import GUIDE_HOLE_X, PLATE_WIDTH

# The rail section and stations (``build_pd_platen_guide`` builds from these
# and re-exports them; paper_drive_geom reads them here, COM-free).
GUIDE_LENGTH = PLATE_WIDTH  # the full platen width, 10-5/8
GUIDE_HEIGHT = inch(3, 16)
# 7/16: 1/16 past the 3/8 bar so the lock plates clear it. 13/32 (1/32
# past) would leave the as-made lock gap under LOCK_GAP_FIT's max at the
# printed band (build_pd_platen_guide asserts it).
GUIDE_DEPTH = inch(7, 16)
# The guide screws' stations: the platen's guide-screw columns.
SCREW_STATION_X = GUIDE_HOLE_X
# 3/10 and 7/10 of the width (the 2nd and 4th screw columns); inboard of the
# east column clamp.
LOCK_STATION_X = (GUIDE_HOLE_X[1], GUIDE_HOLE_X[3])
LOCK_SCREW_DX = inch(1, 4)  # 2 screws per lock flank its centre

# R9-64: the guide screws' front receivers are #4-40 tapped THROUGH the rail,
# as R9-48 made the rear row. A blind tap cannot hold full thread to the
# screw's 5.42 reach and keep a bottoming tap's lead above the drill bottom
# without the drill point breaking through a faced lock seat, so the hole has
# no thread or drill depth to stack. The tips stop inside the rail
# (build_pd_platen_guide asserts the reach).
TAPPED_HOLE_SPEC = HoleSpec("tapped", "#4-40")

# The guide-lock screws' rear receivers (R9-48): #4-40 tapped THROUGH the
# rail, so the full 7/16 depth carries thread and no depth band can starve
# the 3/8 in MHA-VN-046 screws (vn_guide_lock_screw_spec.ENGAGEMENT_WORST). The
# tips stop inside the rail (build_pd_platen_guide asserts the reach).
LOCK_TAP_SPEC = HoleSpec("tapped", "#4-40")

# The rail's depth (``build_pd_platen_guide.GUIDE_DEPTH``) sets how far behind the
# bar's back face the lock plates ride and how close their slotted pan heads
# come to the hanger arm and its plate. Both sit inside the paper-drive
# lock-station sweep, so the depth carries an explicit one-sided band, native
# on Depth@Guide: never deeper than nominal (the heads keep their margin to
# the arm plate at worst), and as loose as the .XX row on the shallow side.
# It prints at the document's two places.
GUIDE_DEPTH_BAND = (0.0, -0.50)  # (upper, lower)
GUIDE_DEPTH_PLACES = 2

# The print's dimensions, by owning feature (the build marks exactly these and
# the sheet imports only these), and the places each carries, authored on the
# model (drawing-simplicity-policy.md `How the repository implements the guidelines`). The height prints at the depth's places (the
# lock-station sweep reads it so). The length prints .X: the rail ends only
# meet the platen's edges, and the holes locate from the left end at basic
# stations, so no stack reads its band.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GuideProfile": {"Length", "Height"},
    "Guide": {"Depth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GuideProfile": {"Length": 1, "Height": GUIDE_DEPTH_PLACES},
    "Guide": {"Depth": GUIDE_DEPTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {f: set(d) for f, d in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked platen-guide dimension needs native precision")

# R9-47 (Main-approved fit-up): the lock gap, lock-plate front face to the
# bar's back face, as fitted by facing the rail backs under the lock plates
# (the lock seats; pd_paper_drive_assembly_steps "lock-seats-faced"). It is the
# platen's float: (min, max), on feelers. Its max bounds how far the platen
# can come forward toward the 120T disc. The as-made gap is never
# under the max (build_pd_platen_guide asserts it), so the facing always cuts.
LOCK_GAP_FIT = (0.05, 0.25)
LOCK_GAP_FIT_TEXT = f"{LOCK_GAP_FIT[0]:.2f}-{LOCK_GAP_FIT[1]:.2f}"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "platen-mating face flatness": "0.10",
    "guide opposite-face parallelism": "0.10",
    "guide hole-pattern position": "0.20",
}

# The one running surface (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)): the platen HANGS by the top rail's
# bottom face (local y 0, datum B) on the support bar's top edge and slides
# along it across the feed. Both rails are this part, so the face is cut on
# both. Every other face is cast/machined per the title block.
SURFACE_FINISHES = (
    SurfaceFinishControl("bar_slide", MACHINED_UM, PlanarFace((0, -1, 0), 0.0)),
)
