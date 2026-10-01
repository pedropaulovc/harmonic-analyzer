r"""Pure-data dimensional contract shared by the feed-pinion sleeve and its drawing.

The transgear pinion sleeve (MHA-110, contract §2.3): one turned steel sleeve
that runs on the fixed stud's Ø3.9 journal (MHA-082) and carries, rear to
front, the 12T DP30 feed pinion that meshes the platen rack, the Ø10 spigot
that locates the 120T disc (MHA-070), and the Ø8.2 shank the brass hub
(MHA-159) is pressed on.  Its nose stands proud of the hub and is the
cluster's front thrust face; its rear end runs on the stud's Ø9 step.

Local frame: origin on the axis at the sleeve's REAR end (the face that runs
on the stud's Ø9 step, machine z −135.15 as fitted), +Z toward the machine
FRONT.  The teeth occupy z 0..GEAR_FACE_STATION, the spigot GEAR_FACE_STATION..
SPIGOT_FRONT_STATION, the shank SPIGOT_FRONT_STATION..OVERALL_LENGTH.  Datums:
``RearFace`` is the Front Plane (z 0), ``GearFace`` and ``SpigotFront`` are
offset planes, ``Axis1`` is the tooth pattern's Top × Right axis.

Round-10 rulings R9-5 (cluster float, nose proud, functional stations) and
R9-8 (the Ø1.2 oil hole, match-drilled through hub and sleeve after pressing)
supersede the contract where they differ.

PURE DATA, no SolidWorks/COM imports: ``build_transgear_feed_pinion`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION``;
``draw_transgear_feed_pinion`` keeps exactly the same names.
"""

from __future__ import annotations

import math

import rack_pinion_spec
import transgear_disc_hub_spec
import transgear_stub_spec
from _fit_limits import deviations
from _gtol_spec import CylinderFace
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

MM_PER_IN = 25.4

# The part numbers the sheet names.  Hard-coded, not read from ``_config.parts``
# (crank_pinion_spec's precedent: a registry read would make the part rows
# rebuild inputs of every importer); test_transgear_feed_pinion_drawing checks
# them against the registry offline.
SLEEVE_NUMBER = "MHA-110"
STUD_NUMBER = "MHA-082"
HUB_NUMBER = "MHA-159"
DISC_NUMBER = "MHA-070"
RACK_NUMBER = "MHA-069"

# --- 12T DP30 feed pinion ------------------------------------------------------
TEETH = 12
DIAMETRAL_PITCH = 30.0  # meshes the DP30 platen rack (the ch. 23 scale anchor)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN  # 10.160
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN  # 11.853
# Printed .XXX with its own +0/-0.10.  Functional reason for the band inside
# the .XXX row: the row's +0.13 on the diameter would take half the 0.133
# standard tip clearance (0.157/P) to the rack's roots, so the tip may only
# shrink.
OUTSIDE_DIA_BAND = (0.0, -0.10)  # (upper, lower)
# Root at the 1.25/P full-depth dedendum (contract §2.3, root 8.043); the
# model cuts exactly this floor (``_gear.build_fixed_gear`` dedendum 1.25).
DEDENDUM_FACTOR = 1.25
ROOT_DIA = (TEETH - 2.0 * DEDENDUM_FACTOR) / DIAMETRAL_PITCH * MM_PER_IN  # 8.0433
WHOLE_DEPTH = (OUTSIDE_DIA - ROOT_DIA) / 2.0
# The root prints as a single MIN limit, the floor of the cutter's depth, so
# the wall under it holds whatever deeper-rooted cutter the shop uses above
# it.  swTolMIN prints the dimension's NOMINAL followed by "MIN", so the
# nominal rounds to the floor at the places it prints.
ROOT_DIA_PLACES = 2
ROOT_DIA_MIN = math.floor(ROOT_DIA * 10**ROOT_DIA_PLACES) / 10**ROOT_DIA_PLACES  # 8.04
ROOT_DIA_TOL_TYPE = 5  # swTolType_e.swTolMIN (offline API docs, enums/swTolType_e)
if round(ROOT_DIA, ROOT_DIA_PLACES) != ROOT_DIA_MIN:
    raise AssertionError(
        f"root Ø{ROOT_DIA:.4f} does not print as its {ROOT_DIA_MIN} MIN"
    )

# --- axial stations from the rear face (z 0) -----------------------------------
# All three print ±0.05 (R9-5).  Functional reasons:
#   GEAR_FACE_STATION: the disc seat; it sets where the disc, hub flange and hub
#     front face land, so it is a term of the nose-proud stack below.
#   SPIGOT_FRONT_STATION: the spigot may never stand proud of the disc's front
#     face, or the hub flange would seat on the spigot step instead of clamping
#     the disc; that stack (SPIGOT_RECESS_WORST) cannot hold at the .X row.
#   OVERALL_LENGTH: the cluster float against the stud journal and the nose
#     proud of the hub.
STATION_TOL = 0.05
STATION_PLACES = 2
GEAR_FACE_STATION = 9.5
FACE_WIDTH = GEAR_FACE_STATION  # the tooth length: rear face to the disc seat
# Rule-11 (FeedSleevePart): 12.2, not the contract's 12.5.  The disc is 3.00
# .XXX (±0.13), so a spigot as long as the disc is thick stands proud of it at
# the worst case; 12.2 ±0.05 keeps it 0.07 inside the disc's front face.
SPIGOT_FRONT_STATION = 12.2
OVERALL_LENGTH = 22.6
SLEEVE_LENGTH = OVERALL_LENGTH
SLEEVE_LENGTH_TOL = STATION_TOL

# --- diameters -----------------------------------------------------------------
# The spigot is the disc's slip fit: turned to the SHAFT_H band under the
# disc's REAM_SLIDE bore (rack_pinion_spec owns the pair, so the disc sheet's
# fit note and this model band are one constant).  The shank is the hub's
# press seat, turned to the band transgear_disc_hub_spec sets over the hub's
# reamed bore (that module owns the pair and its interference, R9-45).
SPIGOT_DIA = rack_pinion_spec.SPIGOT_DIA
SPIGOT_DIA_BAND = rack_pinion_spec.SPIGOT_DIA_BAND  # (upper, lower) deviations
SHANK_DIA = transgear_disc_hub_spec.SHANK_DIA
SHANK_DIA_BAND = transgear_disc_hub_spec.SHANK_DIA_BAND  # (upper, lower) deviations
DIA_PLACES = 3
if rack_pinion_spec.SLEEVE_NUMBER != SLEEVE_NUMBER:
    raise AssertionError("the disc's fit note names another part than this sleeve")

# The bore runs on the stud journal.  A running fit exists only if both size
# bands are narrower than the clearance they claim (tolerance-policy step 6b):
# +0.030/+0.012 over the journal's 0/−0.020 gives 0.012..0.050 diametral.
BORE_DIA = transgear_stub_spec.JOURNAL_DIA  # 3.9
BORE_DIA_BAND = (0.030, 0.012)  # (upper, lower) deviations, reamed
BORE_PLACES = 3
_JOURNAL_UPPER, _JOURNAL_LOWER = transgear_stub_spec.JOURNAL_DIA_BAND
BORE_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_BAND[1] - _JOURNAL_UPPER, 3),
    round(BORE_DIA_BAND[0] - _JOURNAL_LOWER, 3),
)
if BORE_DIAMETRAL_CLEARANCE[0] <= 0.0:
    raise AssertionError(
        f"sleeve bore binds on the journal: {BORE_DIAMETRAL_CLEARANCE}"
    )
BORE_PROCESS_CALLOUT = "REAM THRU"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE STUD {STUD_NUMBER}",
        f"(\N{DIAMETER SIGN}{BORE_DIA:.3f} +{_JOURNAL_UPPER:.3f}/{_JOURNAL_LOWER:.3f})",
        f"(DIA CLR {BORE_DIAMETRAL_CLEARANCE[0]:.3f}-{BORE_DIAMETRAL_CLEARANCE[1]:.3f} mm)",
    )
)

_BAND = {places: printed_band_mm(places) for places in (1, 2, 3)}
_DRILL_OVERSIZE = drilled_oversize_mm()

# --- R9-5 checks (worst case at the printed bands) -----------------------------
# Cluster float = stud journal (Ø9 step → shoulder, 22.9 ±0.05) − sleeve length
# (22.6 ±0.05) = 0.3 nominal, 0.2..0.4.
_JOURNAL_LENGTH = transgear_stub_spec.JOURNAL_LENGTH
_JOURNAL_LENGTH_TOL = transgear_stub_spec.JOURNAL_LENGTH_TOL
CLUSTER_FLOAT = _JOURNAL_LENGTH - SLEEVE_LENGTH
CLUSTER_FLOAT_RANGE = (
    (_JOURNAL_LENGTH - _JOURNAL_LENGTH_TOL) - (SLEEVE_LENGTH + SLEEVE_LENGTH_TOL),
    (_JOURNAL_LENGTH + _JOURNAL_LENGTH_TOL) - (SLEEVE_LENGTH - SLEEVE_LENGTH_TOL),
)
if not (0.2 - 1e-9 <= CLUSTER_FLOAT_RANGE[0] and CLUSTER_FLOAT_RANGE[1] <= 0.4 + 1e-9):
    raise AssertionError(f"cluster float {CLUSTER_FLOAT_RANGE} left the ruled 0.2..0.4")

# Nose proud of the hub front face = 22.6 − (9.5 + disc 3.00 + hub 9.40) = 0.70;
# worst 22.55 − (9.55 + 3.13 + 9.53) = 0.34 (disc and hub print .XXX).
DISC_THICKNESS = rack_pinion_spec.FACE_WIDTH
_DISC_BAND = _BAND[rack_pinion_spec.FACE_WIDTH_PLACES]
HUB_LENGTH = transgear_disc_hub_spec.HUB_LENGTH
_HUB_BAND = _BAND[transgear_disc_hub_spec.HUB_LENGTH_PLACES]
HUB_FRONT_STATION = GEAR_FACE_STATION + DISC_THICKNESS + HUB_LENGTH  # 21.9
NOSE_PROUD = OVERALL_LENGTH - HUB_FRONT_STATION
NOSE_PROUD_WORST = (OVERALL_LENGTH - SLEEVE_LENGTH_TOL) - (
    GEAR_FACE_STATION
    + STATION_TOL
    + DISC_THICKNESS
    + _DISC_BAND
    + HUB_LENGTH
    + _HUB_BAND
)
if NOSE_PROUD_WORST < 0.34 - 1e-9:
    raise AssertionError(
        f"hub can stand proud of the sleeve nose: {NOSE_PROUD_WORST:.3f}"
    )

# The spigot stays inside the disc bore, so the flange clamps the disc:
# (9.45 + 2.87) − 12.25 = 0.07 at the worst case; it still locates the disc
# over 12.15 − 9.55 = 2.60.
SPIGOT_RECESS_WORST = (
    GEAR_FACE_STATION - STATION_TOL + DISC_THICKNESS - _DISC_BAND
) - (SPIGOT_FRONT_STATION + STATION_TOL)
SPIGOT_LENGTH_MIN = (
    SPIGOT_FRONT_STATION - STATION_TOL - (GEAR_FACE_STATION + STATION_TOL)
)
if SPIGOT_RECESS_WORST <= 0.0:
    raise AssertionError(f"spigot stands proud of the disc: {SPIGOT_RECESS_WORST:.3f}")

# --- walls (rule 12: target 2.0, floor 1.5, at the printed bands) --------------
WALL_TARGET = 2.0
_BORE_MAX = BORE_DIA + BORE_DIA_BAND[0]  # 3.930
# Under the root: (8.0433 − 3.900)/2 = 2.072 nominal; (8.04 MIN − 3.930)/2 = 2.055.
ROOT_WALL = (ROOT_DIA - BORE_DIA) / 2.0
ROOT_WALL_WORST = (ROOT_DIA_MIN - _BORE_MAX) / 2.0
# Shank: (8.2 − 3.9)/2 = 2.15; (8.225 − 3.93)/2 = 2.147 (its band lies above it).
SHANK_WALL = (SHANK_DIA - BORE_DIA) / 2.0
SHANK_WALL_WORST = (SHANK_DIA + SHANK_DIA_BAND[1] - _BORE_MAX) / 2.0
# Spigot: (10 − 3.9)/2 = 3.05; (9.98 − 3.93)/2 = 3.025.
SPIGOT_WALL = (SPIGOT_DIA - BORE_DIA) / 2.0
SPIGOT_WALL_WORST = (SPIGOT_DIA + SPIGOT_DIA_BAND[1] - _BORE_MAX) / 2.0

# --- oil hole (R9-8) -----------------------------------------------------------
# Ø1.2 drilled (+0.10/0) on +Y, centred on the hub body (R9-60: 3.5 nominal
# behind the hub front face), through hub and shank wall in one operation
# after pressing.  The hub sheet owns its size and location; this sheet carries
# the match-drill note (the crank pinion's pin-hole wording,
# crank_pinion_spec.pin_hole_note).  Sleeve-local z = 21.9 − 3.5 = 18.4.
OIL_HOLE_DIA = transgear_disc_hub_spec.OIL_HOLE_DIA
OIL_HOLE_Z = HUB_FRONT_STATION - transgear_disc_hub_spec.OIL_HOLE_STATION
OIL_HOLE_AZIMUTH_DEG = 90.0  # local +Y
# (least, greatest) station behind the hub front face: half the hub body the
# hub's printed lengths leave, plus the centring at fit-up (3.12..3.88).
_OIL_STATION_RANGE = transgear_disc_hub_spec.OIL_HOLE_STATION_RANGE
_OIL_HOLE_MAX_R = (OIL_HOLE_DIA + _DRILL_OVERSIZE) / 2.0
# Ligament from the hole to the sleeve nose: 22.6 − 18.4 − 0.6 = 3.6 nominal;
# worst 0.34 (nose) + 3.12 − 0.65 = 2.81.
OIL_HOLE_TO_NOSE = OVERALL_LENGTH - OIL_HOLE_Z - OIL_HOLE_DIA / 2.0
OIL_HOLE_TO_NOSE_WORST = NOSE_PROUD_WORST + _OIL_STATION_RANGE[0] - _OIL_HOLE_MAX_R
# The hole stays on the shank, clear of the spigot step: its rear edge lies at
# least (9.45 + 2.87 + 9.27) − 3.88 − 0.65 = 17.06 from the rear face.
OIL_HOLE_REAR_EDGE_WORST = (
    GEAR_FACE_STATION
    - STATION_TOL
    + DISC_THICKNESS
    - _DISC_BAND
    + HUB_LENGTH
    - _HUB_BAND
    - _OIL_STATION_RANGE[1]
    - _OIL_HOLE_MAX_R
)
if OIL_HOLE_REAR_EDGE_WORST <= SPIGOT_FRONT_STATION + STATION_TOL:
    raise AssertionError("the oil hole can reach the spigot step")

# Tooth phase: the seed gap is centred half a pitch CCW of local +X
# (involute_gear.gear_facts: (ThetaL + ThetaU) / 2 = Gamma / 2) and the pattern
# steps a pitch, so gap centres sit at 15° + k·30°.  +Y (90°) is a TOOTH
# centre; the oil hole is on the shank 8.9 in front of the teeth anyway, so no
# clocking is needed.
TOOTH_PITCH_DEG = 360.0 / TEETH
GAP_CENTRE_PHASE_DEG = TOOTH_PITCH_DEG / 2.0
OIL_HOLE_TOOTH_OFFSET_DEG = (
    OIL_HOLE_AZIMUTH_DEG - GAP_CENTRE_PHASE_DEG
) % TOOTH_PITCH_DEG
if abs(OIL_HOLE_TOOTH_OFFSET_DEG - GAP_CENTRE_PHASE_DEG) > 1e-9:
    raise AssertionError("the +Y oil hole is no longer on a tooth centre")

WALLS = (
    ("under the root", ROOT_WALL, ROOT_WALL_WORST),
    ("shank", SHANK_WALL, SHANK_WALL_WORST),
    ("spigot", SPIGOT_WALL, SPIGOT_WALL_WORST),
    ("oil hole to nose", OIL_HOLE_TO_NOSE, OIL_HOLE_TO_NOSE_WORST),
)
for _name, _nominal, _worst in WALLS:
    if _worst < WALL_TARGET:
        raise AssertionError(f"sleeve wall {_name} {_worst:.3f} under {WALL_TARGET}")

# --- sheet text ------------------------------------------------------------------
OIL_HOLE_NOTE = "\n".join(
    (
        f"MATCH DRILL AT ASSY WITH {HUB_NUMBER}",
        "THRU HUB AND SHANK WALL AFTER PRESSING",
        f"HOLE SIZE AND LOCATION PER {HUB_NUMBER}",
    )
)

# One roughness, on the one running surface: the bore.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

# --- Marked-dimension contract -------------------------------------------------
# ``GearBlank`` is the tooth blank's extrude (its depth is the gear-face
# station).  ``SleeveProfile`` is the Right-plane revolve of the spigot and
# shank, with construction-only witnesses for the tooth tip, the root and the
# bore, so every turned diameter prints beside its axial extent on the
# longitudinal section (rules 2 and 7).  Lengths are baselined from the rear
# face.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "SleeveProfile": {
        "OutsideDia",
        "RootDia",
        "BoreDia",
        "SpigotDia",
        "ShankDia",
        "SpigotFront",
        "OverallLength",
    },
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": STATION_PLACES},
    "SleeveProfile": {
        "OutsideDia": 3,
        "RootDia": ROOT_DIA_PLACES,
        "BoreDia": BORE_PLACES,
        "SpigotDia": DIA_PLACES,
        "ShankDia": DIA_PLACES,
        "SpigotFront": STATION_PLACES,
        "OverallLength": STATION_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(len(d) for d in DRAWING_PRECISION.values()):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    if set(_dimensions) != DRAWING_DIMENSIONS[_feature]:
        raise AssertionError(f"{_feature}: precision and marks disagree")

# The bands the build applies, by dimension (``(lower, upper)`` deviations).
STATION_DEVIATIONS = (-STATION_TOL, STATION_TOL)
BORE_DEVIATIONS = deviations(BORE_DIA_BAND)
SPIGOT_DIA_DEVIATIONS = deviations(SPIGOT_DIA_BAND)
SHANK_DIA_DEVIATIONS = deviations(SHANK_DIA_BAND)
OUTSIDE_DIA_DEVIATIONS = deviations(OUTSIDE_DIA_BAND)
# swTolMIN records the floor as its lower deviation from the model nominal.
ROOT_DIA_DEVIATIONS = (ROOT_DIA_MIN - ROOT_DIA, 0.0)


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# Rule 6's gear-data block: the tooth system the views cannot dimension.  The
# tip, root and tooth length print as native dimensions on the section.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.2f}"),
        ("TOOTH FORM", "SPUR INVOLUTE, FULL DEPTH"),
        ("MATES WITH", f"PLATEN RACK {RACK_NUMBER}"),
    ]
)

# The title block's 0.25 edge break is 14% of this fine tooth's whole depth.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
DRAWING_NOTES = TOOTH_EDGE_NOTE
