r"""Pure-data dimensional contract shared by the pinion engage lever and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A hub seated over the lift rod, with a
tapered grip rod rising out of it -- turned steel.  The nominals drive the part's
named equation globals AND the drawing's coordinate math; the marked-dimension
map keeps the part marks and drawing keeps in lockstep
(``test_pinion_lever_drawing.py``).
"""

from __future__ import annotations

ROD_ROOT_DIA = 4.0  # rod diameter where it leaves the clamp hub (thin end)
ROD_TIP_DIA = 6.0  # rod diameter at the grip tip (fat end)
ROD_LEN = 86.0  # hub centre to tip
ROD_Y0 = 3.5  # rod base above the hub centre (buried under the hub OD)
HUB_OD = 13.0  # clamp hub cylinder OD
HUB_LEN = 10.0  # hub length along the lift rod (z -5..+5)
BORE = 6.35  # clamp bore -- grips the Ø6.35 lift rod
WALL_T = 2.0  # blind wall behind the bore (south end)
CAP_SAG = 1.5  # domed south cap crown height
CAP_RADIUS = ((HUB_OD / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarrelProfile": {"HubOd", "HubBore"},
    "RodProfile": {"RodRootR", "RodTipR", "RodTipY"},
}

DRAWING_NOTES = "\n".join(
    (
        "HUB CYLINDRICAL LENGTH 10.00+/-0.10 FROM FLAT FACE TO CROWN ROOT PLANE;",
        "  CROWN ADDS 1.50+/-0.05 (11.50 REF OVERALL). BORE FINAL LIMITS",
        "  REAM 6.360-6.375 X 8.0 DEEP MIN FULL-DIAMETER FROM FLAT FACE, Ra 1.6; SLIDING FIT.",
        "INTEGRAL GRIP: R2.00 AT HUB TO R3.00 AT TIP, STRAIGHT TAPER;",
        "  86.00+/-0.25 FROM HUB AXIS TO TIP. GRIP MID-PLANE WITHIN 0.05 OF HUB MID-PLANE.",
        f"CROWN SR{CAP_RADIUS:.2f}; HUB OD TO BORE TIR 0.05; FLAT FACE SQUARE 0.05.",
        "AT ASSEMBLY, DRILL/REAM <MOD-DIAM>3.000-3.012 THRU HUB AND LIFT ROD,",
        "  5.00+/-0.10 FROM FLAT FACE, NORMAL TO GRIP PLANE; FIT ISO 8734 <MOD-DIAM>3 m6 X 16 PIN.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
