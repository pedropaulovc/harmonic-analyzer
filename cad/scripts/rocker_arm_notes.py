r"""Rocker-arm drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT and the isometric-view label.

Split OUT of ``rocker_arm_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the rocker's
geometry, so drawing prose living in that import closure made every notes edit
full-rebuild ``assembly:channel``.  Imported ONLY by ``build_rocker_arm`` and
the offline drawing test.
"""

from __future__ import annotations

# Native view dimensions own all geometry and bore tolerances.  The note block
# is only the symmetry statement and the final matched-joint cross-reference.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"BottomRodX", "RodTipLen"},
    "PivotHoleProfile": {"PivotDia", "PivotZ"},
    "HubProfile": {"HubDia"},
}

DIMENSION_PRECISION: dict[str, int] = {
    "BottomRodX": 2,
    "RodTipLen": 2,
    "PivotDia": 2,
    "PivotZ": 2,
    "HubDia": 2,
}

DIMENSION_CALLOUTS: dict[str, str] = {
    "PivotDia": "REAM THRU",
    "RodTipLen": "2X ENDS",
}

DRAWING_NOTES = "\n".join(
    (
        "PROFILE SYMMETRIC ABOUT PIVOT-BORE AXIS.",
        "ROD END MATES WITH CONNECTING ROD MHA-017.",
        "FINAL SIDEPLAY AND FREE PIVOT PER MHA-132.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
