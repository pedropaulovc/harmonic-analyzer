"""Pure-data manufacturing contract for the platen guide."""


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    'platen-mating face flatness': '0.10',
    'guide opposite-face parallelism': '0.10',
    'guide hole-pattern position': '0.20',
}
