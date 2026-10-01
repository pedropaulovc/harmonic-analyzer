"""Pure-data manufacturing contract for the platen guide."""

from _hole_spec import HoleSpec

TAPPED_HOLE_SPEC = HoleSpec(
    "tapped_bottoming",
    "#4-40",
    end="blind",
    depth_mm=5.52,
    overrides_mm={"ThreadDepth": 5.2678},
)

# The rail's depth (``build_platen_guide.GUIDE_DEPTH``) sets how far behind the
# bar's back face the lock plates ride and how close their button heads come
# to the hanger arm and its plate. Both sit inside the paper-drive lock-station
# sweep, so the depth carries an explicit one-sided band, native on
# Depth@Guide: never deeper than 10 (the heads keep 0.15 to the arm plate at
# worst), and as loose as the .XX row on the shallow side (the plates keep
# 0.37 to the bar). It prints at the document's two places.
GUIDE_DEPTH_BAND = (0.0, -0.50)  # (upper, lower)
GUIDE_DEPTH_PLACES = 2


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "platen-mating face flatness": "0.10",
    "guide opposite-face parallelism": "0.10",
    "guide hole-pattern position": "0.20",
}
