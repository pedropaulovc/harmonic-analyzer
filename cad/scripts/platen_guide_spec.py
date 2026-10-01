"""Pure-data manufacturing contract for the platen guide."""

from _hole_spec import HoleSpec

TAPPED_HOLE_SPEC = HoleSpec(
    "tapped_bottoming",
    "#4-40",
    end="blind",
    depth_mm=5.52,
    overrides_mm={"ThreadDepth": 5.2678},
)

# The guide-lock screws' rear receivers (R9-48): #4-40 tapped THROUGH the
# rail, so the full 10.00 depth carries thread and no depth band can starve
# the 3/8 in MHA-176 screws (guide_lock_screw_spec.ENGAGEMENT_WORST). The
# tips stop inside the rail (build_platen_guide asserts the reach).
LOCK_TAP_SPEC = HoleSpec("tapped", "#4-40")

# The rail's depth (``build_platen_guide.GUIDE_DEPTH``) sets how far behind the
# bar's back face the lock plates ride and how close their button heads come
# to the hanger arm and its plate. Both sit inside the paper-drive lock-station
# sweep, so the depth carries an explicit one-sided band, native on
# Depth@Guide: never deeper than 10 (the heads keep 0.15 to the arm plate at
# worst), and as loose as the .XX row on the shallow side (the plates keep
# 0.37 to the bar). It prints at the document's two places.
GUIDE_DEPTH_BAND = (0.0, -0.50)  # (upper, lower)
GUIDE_DEPTH_PLACES = 2
# R9-47 (Main-approved fit-up): the lock gap, lock-plate front face to the
# bar's back face, as fitted by facing the rail backs under the lock plates
# (the lock seats; paper_drive_assembly_steps "lock-seats-faced"). It is the
# platen's float: (min, max), on feelers. Its max bounds how far the platen
# can come forward toward the 120T disc. The as-made gap is never
# under the max (build_platen_guide asserts it), so the facing always cuts.
LOCK_GAP_FIT = (0.05, 0.25)
LOCK_GAP_FIT_TEXT = f"{LOCK_GAP_FIT[0]:.2f}-{LOCK_GAP_FIT[1]:.2f}"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "platen-mating face flatness": "0.10",
    "guide opposite-face parallelism": "0.10",
    "guide hole-pattern position": "0.20",
}
