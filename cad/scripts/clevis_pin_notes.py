r"""Drawing-only contracts for the connecting-rod clevis pin.

Kept outside ``clevis_pin_spec`` because the channel assembly imports the pure
geometry contract; drawing prose must not force a channel rebuild.
"""

from __future__ import annotations

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShankProfile": {"ShankDia"},
    "Shank": {"GripLength"},
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadThickness"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. TURN FROM AISI 1018 COLD-FINISHED STEEL.",
        "2. HEAD SEATS ON THE VISIBLE NEAR CLEVIS CHEEK.",
        "3. BREAK SHARP EDGES 0.10 MAX; DEBURR SHANK.",
        "4. POLISH BRIGHT AND APPLY LIGHT OIL.",
    )
)
END_VIEW_NOTE = "HEAD END VIEW"
