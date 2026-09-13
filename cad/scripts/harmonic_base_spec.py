r"""Dimensional contract shared by the harmonic base and its drawing.

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the reference
split). ``build_harmonic_base`` imports the plate nominal geometry + the
marked-dimension NAME map from here; ``draw_harmonic_base`` imports the same
geometry for its view math and keeps exactly ``DRAWING_DIMENSIONS`` across its
per-view ``keep`` maps, so the part-side marks and the drawing-side keeps cannot
silently drift.
"""

from __future__ import annotations

MM_PER_IN = 25.4

# --- Two-plate welded base (book ch. 6), centred on the part origin. ---
BOTTOM_LENGTH = 18.0 * MM_PER_IN  # 457.2 (46 cm callout)
FORMER_BOTTOM_WIDTH = 11.0 * MM_PER_IN  # 279.4 (28 cm callout)
BOTTOM_FRONT_Z = -FORMER_BOTTOM_WIDTH / 2.0
BOTTOM_REAR_Z = FORMER_BOTTOM_WIDTH / 2.0
BOTTOM_WIDTH = BOTTOM_REAR_Z - BOTTOM_FRONT_Z
BOTTOM_CENTER_Z = (BOTTOM_FRONT_Z + BOTTOM_REAR_Z) / 2.0
BOTTOM_THICKNESS = 0.5 * MM_PER_IN  # 12.7
TOP_LENGTH = 17.5 * MM_PER_IN  # 444.5 (0.25 in reveal per side)
FORMER_TOP_WIDTH = 10.5 * MM_PER_IN  # 266.7
TOP_FRONT_Z = -FORMER_TOP_WIDTH / 2.0
TOP_REAR_Z = FORMER_TOP_WIDTH / 2.0
TOP_WIDTH = TOP_REAR_Z - TOP_FRONT_Z
TOP_CENTER_Z = (TOP_FRONT_Z + TOP_REAR_Z) / 2.0
TOP_THICKNESS = 1.5 * MM_PER_IN  # 38.1
STACK_HEIGHT = BOTTOM_THICKNESS + TOP_THICKNESS  # 50.8: the deck (pad top)
LIP_W = 7.0  # raised rim width, in from the pad outline (2026-09 photo re-derive)
LIP_H = 2.5  # raised rim height above the deck
RIM_TOP = STACK_HEIGHT + LIP_H  # 53.3: the casting's overall height

if abs(BOTTOM_CENTER_Z) > 1e-12 or abs(TOP_CENTER_Z) > 1e-12:
    raise AssertionError("base plates are not centred")

# --- Marked-dimension contract. The plan carries the overall footprint and
# one representative socket's centre coordinates/4X diameter. Section A-A
# carries the socket and spotface depths; the cross tap is a native Hole Wizard
# callout from the same section. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BottomProfile": {"BottomLen", "BottomWid"},
    "ColumnSocketProfile": {"Socket0X", "Socket0Z", "SocketDia"},
    "ColumnSockets": {"SocketDepth"},
    "BaseSpotFaceRearProfile": {"SpotFaceDia"},
    "BaseSpotFaceRear": {"SpotFaceDepth"},
}

# Lines stay short so two lower-field note columns remain clear of the side
# elevation and title block.
DRAWING_NOTES = "\n".join(
    (
        "1. MACHINE FROM SOLID STOCK TO THE FINISHED PROFILE SHOWN; NO DRAFT.",
        "   PAD-TO-FLANGE ROOT R0.50 MAX; LOWER FLANGE 12.70 THICK;",
        "   DECK 50.80, TOTAL HEIGHT 53.30 OVER THE RIM.",
        "2. UPPER PAD 444.50 X 266.70;",
        "   NEAR LONG SIDE 6.35 +/-0.10 FROM B;",
        "   NEAR LEFT END 6.35 +/-0.10 FROM C.",
        "3. TOP-VIEW HOLE-TABLE LOCATIONS ORIGINATE AT THE FINISHED",
        "   REAR LONG-SIDE / LEFT-END THEORETICAL SHARP CORNER.",
        "4. FOUR DIA 13.00 THRU / DIA 23.00 C'BORES FROM UNDERSIDE,",
        "   9.52 +/-0.10 DEEP. PLAN RIMS ARE THE DIA 13.00 THRU FEATURES.",
        "   C'BORE AND THRU-HOLE AXES: LEAST-SQUARES CYLINDER FITS OVER",
        "   FULL SURFACES; SEPARATION AT C'BORE MOUTH/BOTTOM: 0.05 MAX.",
    )
)
DRAWING_NOTES_B = "\n".join(
    (
        "5. BLIND UNC-2B TAPS: FULL THREAD / CYLINDRICAL DRILL DEPTH.",
        "   BOTTOMING: PIVOT #10-24 9.775/12; BLOCK #8-32 6.90/10;",
        "   FOOT #4-40 8.975/11; NAMEPLATE #4-40 6/9. LEAD >=2P.",
        "   PLUG: LOCK 1/4-20 19.30/25.65; STOP #8-32 16/20.",
        "   PLUG LEAD >=5P; P = THREAD PITCH; DRILL POINT EXTRA.",
        '5A. STAMP SERIAL "2" 3.50 HIGH X 0.30 DEEP ON THE RIM TOP',
        "   BESIDE THE NAMEPLATE (SEE MODEL); BRIGHT, UNPAINTED.",
        "6. DURING COATING, MASK FINISHED FACES AND ALL BORES/THREADS;",
        "   COAT PAD SIDES, ROOTS AND RIM. DECK INSIDE THE RIM: BLACK",
        "   ENAMEL, SAME SYSTEM AND DFT AS THE FINISH CALLOUT.",
        "7. VERTICAL PLAN CORNERS: FLANGE R22.22, PAD AND RIM R15.88",
        "   (CONCENTRIC), RIM INNER CORNERS R8.88, ALL FULL HEIGHT.",
        "   FLANGE TOP RIM, RIM TOP AND UNDERSIDE RIM C1.59 X 45 DEG.",
        "8. RAISED RIM 7.00 WIDE X 2.50 HIGH, OUTER FACES FLUSH WITH THE",
        "   PAD SIDES; DECK STAYS AT 50.80.",
        "9. SECTION A-A: FOUR DIA25.50 +0.05/0 SOCKETS, 25.40 DEEP;",
        "   MATCH FIT MHA-083 TUBE COLUMN, 0.10 TO 0.20 DIAMETRAL CLEARANCE.",
        "   FOUR #10-32 UNF-2B BOTTOMING TAPS: 46.00 FULL THREAD / 48.00",
        "   CYLINDRICAL TAP-DRILL DEPTH FROM DIA9.00 SPOT-FACED SEATS.",
    )
)
SECTION_VIEW_NOTE = "SECTION A-A SCALE 1:4"
SIDE_VIEW_NOTE = "FRONT VIEW 1:4"

# Base/frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
