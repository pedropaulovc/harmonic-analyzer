r"""Pure-data dimensional contract shared by the gooseneck post and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_sm_gooseneck`` imports the marked-
dimension NAME map + notes from here; ``draw_sm_gooseneck`` keeps exactly
``DRAWING_DIMENSIONS`` for its elevation-view import.
"""

from __future__ import annotations

import sm_gooseneck_geom
from sm_gooseneck_spring_joint import (
    DRILL_WANDER_MAX,
    EDGE_BREAK,
    ENGAGEMENT_MIN,
    ENGAGEMENT_NOMINAL,
    PLUG_DIA,
    PLUG_DIAMETER_BAND,
    PLUG_LENGTH_BAND,
    TAP_SPEC,
    THREAD_AXIS_OFFSET_MAX,
)


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The bend RADIUS (R51) and the horizontal ARM RUN are marked --
# both live on the Front-plane sweep-path sketch (BendPath), so they project
# cleanly to the elevation view. This legacy sheet retains its note-based
# tube-stock, leg-length and brazed-plug/tap schedule; it is not a simplicity-
# policy migration. EndPlugProfile owns the native plug length, while ThreadBore
# owns the native through-tap identity. The Ø14 union envelope is modelling
# overlap only: the notes specify the physical Ø12 plug. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BendPath": {"BendRadius", "ArmRun"},
}

# Lines kept short so the left-anchored block clears the elevation and title
# block; it grows DOWNWARD. The plug belongs to this brazed weldment, while the
# made MHA-SM-004 spring screw and spring-eye clamping instructions belong to
# the assembly package.
DRAWING_NOTES = "\n".join(
    (
        "1. TUBE <MOD-DIAM>16.00 +/-0.10 X 2.0 WALL; CUT ENDS",
        "   SQUARE.",
        f"2. FORM CENTERLINE (R{sm_gooseneck_geom.BEND_R:.0f} = CENTERLINE RADIUS):",
        f"   442.3 STRAIGHT LEG TO BEND TANGENT, R{sm_gooseneck_geom.BEND_R:.0f}"
        " 90-DEG",
        f"   BEND, {sm_gooseneck_geom.ARM_RUN:.2f} STRAIGHT ARM TO END FACE. LINEAR",
        "   +/-0.5; RADIUS +/-0.5; ANGLE +/-1 DEG. LEG + ARM",
        "   CENTERLINES COPLANAR (ELEVATION PLANE) WITHIN 1.0.",
        f"3. END PLUG: AISI 1018 <MOD-DIAM>{PLUG_DIA:.2f} +/-{PLUG_DIAMETER_BAND:.2f}",
        f"   X {sm_gooseneck_geom.PLUG_LENGTH:.2f} +/-{PLUG_LENGTH_BAND:.2f};"
        " FLUSH WITH ARM END +/-0.10.",
        "   SILVER-BRAZE BAg-7 PER AWS A5.8, FULL",
        "   FAYING-SURFACE PENETRATION.",
        f"4. AFTER BRAZE: {TAP_SPEC.size} UNC-{TAP_SPEC.thread_class} THRU PLUG.",
        f"   THREAD AXIS TO TUBE AXIS +/-{THREAD_AXIS_OFFSET_MAX:.2f};",
        f"   DRILL WANDER {DRILL_WANDER_MAX:.2f} MAX; SQUARE TO END FACE.",
        f"   BREAK BOTH TAP ENDS {EDGE_BREAK:.2f} X 45 DEG.",
        f"   FULL THREAD {ENGAGEMENT_NOMINAL:.2f} NOMINAL; {ENGAGEMENT_MIN:.2f} MIN.",
        "5. MHA-SM-004 SPRING SCREW: MADE SEPARATELY;",
        "   NOT INCLUDED IN THIS WELDMENT. SEE ASSEMBLY.",
        "6. BEND OVALITY 5% MAX; NO FLATS, KINKS OR CRACKS.",
        "7. PLATE ALL SURFACES; NO MASKING. DIMS PRE-PLATE.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
