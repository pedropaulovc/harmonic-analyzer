r"""Channel-lever dimensional contract -- the single source of truth shared by
the part build (``build_ch_channel_lever.py``) and its manufacturing drawing
(``draw_ch_channel_lever.py``).

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the pattern).
The nominal geometry MUST match the constants in build_ch_channel_lever.py (the
test cross-checks the load-bearing ones).
"""

from __future__ import annotations
from _hole_spec import HoleSpec
from _inch import inch


# --- Nominal geometry (DIMENSIONS.md "Chapter 17"), all-inch experiment. ---
# The spring-hole reach is SET BY THE VERTICAL SPRING AXIS, not by a round 7":
# the channel spring must hang plumb in the saved neutral pose, so the lever's
# spring hole has to sit on the summing-lever anchor's machine X. A CLOSURE
# OUTPUT, so it stays decimal: fulcrum 200.025 (7-7/8 in,
# channel_frame_geom.LEVER_FULCRUM_XY) - anchor 24.85
# (spring_mount_geom.CHANNEL_ANCHOR_XY = knife -15 + sm_summing_lever_spec.HOLE_X
# 39.85, both held for the spring calibration) = 175.175 (was 199.9 - 24.85 =
# 175.05). The neutral lever tilt is ~0.01 deg, so the projection correction
# is far below the +/-0.10 hook-arm allocation (error_budget.yaml), hence the
# flat nominal. Was 177.8 (7"), which left the spring 2.75 mm off plumb.
LEVER_SPRING_X = 175.175  # fulcrum -> spring-hole c2c, plumb over the anchor
BAR_TALL = inch(3, 8)  # bar height (was 9.5)
LEVER_THICKNESS = inch(1, 8)  # was 3.0
PIVOT_HOLE_DIA = 6.5  # fulcrum bore riding the 1/4 in fulcrum shaft (existing fit)
BAR_PIN_X = inch(5)  # fulcrum -> bar-pin c2c, 5"
BAR_PIN_HOLE_SPEC = HoleSpec("drilled_number", "#47")
SPRING_EYE_HOLE_SPEC = HoleSpec("drilled_number", "#21")
TAB_START_X = inch(6.625)  # 6-5/8 (was 169.0): bar steps down to the end tab
TAB_HALF = inch(1, 8)  # tab 1/4 tall (was 6.0)
TIP_RADIUS = inch(1, 8)  # rounded tab tip (was 3.0)
TIP_OVERHANG = inch(3, 16)  # tip arc centre past the spring hole (was 5.0)
TIP_ARC_CX = LEVER_SPRING_X + TIP_OVERHANG

# --- Derived spans. ---
NOSE_RADIUS = BAR_TALL / 2.0  # 3/16 fulcrum nose
TIP_END_X = TIP_ARC_CX + TIP_RADIUS  # overall length


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_ch_channel_lever marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LeverOutline": {"BarLength", "TipCentreX", "NoseRadius", "TipRadius"},
    "FulcrumProfile": {"FulcrumDia"},
}

# Integral fulcrum hub (2026-09-02 photo re-derive, ch17 p.40 page002_img03):
# the levers stack hub-to-hub on the fulcrum shaft at the station pitch; the
# 19 `lever-bushing` spacers are retired. OD = the old bushing's O12.
HUB_DIA = inch(1, 2)  # was 12.0
HUB_LENGTH = 7.0565  # == machine channels.station_pitch_mm (asserted by the build)

DRAWING_NOTES = "\n".join(
    (
        "1. MACHINE FROM CONTINUOUS-CAST FLAT STOCK.",
        "2. INDICATED BROAD FACE ESTABLISHES DATUM A;",
        "   MACHINE OPPOSITE FACE TO 3.00 +/-0.10 OVERALL.",
        "3. DATUM B IS THE DERIVED AXIS OF THE FULCRUM BORE:",
        "   REAM DIA 6.50 +0.03/0 THRU, Ra 1.6.",
        "4. DATUM C IS THE LONG TOP FACE; ALL HOLE AXES AND TIP R3 CENTRE",
        "   ARE BASIC 4.75 BELOW C.",
        f"5. BASIC FROM B: BAR-PIN {BAR_PIN_X:.2f}; SHOULDER {TAB_START_X:.2f};",
        f"   SPRING-HOLE {LEVER_SPRING_X:.2f}; TIP R3 CENTRE {TIP_ARC_CX:.2f}.",
        "6. SPRING-HOLE AND TIP R3 CENTRES ARE NOT CONCENTRIC.",
        "7. PROFILE FCF APPLIES ALL AROUND OUTER PERIMETER",
        "   EXCEPT DATUM C; STRAIGHTS TANGENT TO RADII.",
        f"8. INTEGRAL HUB DIA {HUB_DIA:.2f} X {HUB_LENGTH:.2f} LONG ON THE",
        "   FULCRUM BORE, PROUD 2.03 EACH FACE; HUB FACES",
        "   SET THE STATION PITCH (NO SPACERS).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "outer perimeter profile": "0.50",
    "fulcrum bore perpendicularity": "0.05",
    "opposite broad face parallelism": "0.05",
    "bar-pin hole position": "0.20",
    "spring-eye hole position": "0.20",
}
