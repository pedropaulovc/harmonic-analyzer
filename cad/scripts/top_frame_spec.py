r"""Pure-data dimensional contract shared by the top-frame casting and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_top_frame`` imports the marked-
dimension NAME map + notes from here; ``draw_top_frame`` keeps exactly
``DRAWING_DIMENSIONS`` and imports the casting's plan geometry (column
stations, bore diameters) from ``build_top_frame`` for its view math.

2026-08-02 rederive (ch30 px measurement anchored on the 394x224 column pitch
+ GT bundle rescale + ch19 closeups): the ring absorbed the old top-crossbar
(full-height integral bar) and the gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side), grew its rails to 34.2/38.0, gained webbed
faces, proud corner bosses, side-screw taps, hanger-stud holes and the
west-rail fulcrum-keeper taps.
"""

from __future__ import annotations


# --- Marked-dimension contract -------------------------------------------------
#
# The hole sizes remain associative callouts; named Hole Wizard placement
# dimensions expose the stations without duplicating those sizes.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth", "WinWidth", "WinDepth"},
    "WebProfile": {
        "WebOuterWidth",
        "WebOuterDepth",
        "WebInnerWidth",
        "WebInnerDepth",
    },
    "WebRing": {"RingHeight"},
    "BossUpProfile": {"C0Dia"},
    "BossesUpper": {"BossTopExtent"},
    "BossesLower": {"BossBottomExtent"},
    "BoreProfile": {"B0X", "B0Z", "B0Dia"},
    "BarProfile": {
        "BarAnchorX",
        "BarAnchorZ",
        "BarFootSpan",
        "GussetRunE",
        "BarSideE",
    },
    "HubBossProfile": {"HubDia"},
    "HubBoss": {"HubBossExtent"},
    "RibProfile": {"RibWidth"},
    "SetPocketProfile": {"PocketRun", "PocketRise"},
    "GooseneckTap": {"SetTapZ"},
    "GooseneckProfile": {"GnX", "GnZ"},
    "StudHoles": {"StudFrontX", "StudFrontZ", "StudRearX", "StudRearZ"},
    "KeeperTaps": {
        "KeeperFrontX",
        "KeeperFrontZ",
        "KeeperRearX",
        "KeeperRearZ",
    },
    "CapRecessProfile": {"CapRecessDia"},
    "CapRecesses": {"CapRecessDepth"},
}


# The nominal socket geometry stays fixed; the assigned actual tube governs fit.
DRAWING_NOTES = (
    "MATCH EACH SOCKET TO ITS ASSIGNED ACTUAL MHA-083 TUBE.\n"
    "CLOSE HAND-SLIP; NO PERCEPTIBLE ROCK.\n"
    "RETAIN CORNER AND ORIENTATION MATCH MARKS."
)
DRAWING_NOTES_B = ""
