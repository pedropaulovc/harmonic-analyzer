"""Pure-data manufacturing contract for the platen guide."""

from _hole_spec import HoleSpec

TAPPED_HOLE_SPEC = HoleSpec(
    "tapped_bottoming",
    "#4-40",
    end="blind",
    depth_mm=5.52,
    overrides_mm={"ThreadDepth": 5.2678},
)


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "platen-mating face flatness": "0.10",
    "guide opposite-face parallelism": "0.10",
    "guide hole-pattern position": "0.20",
}
