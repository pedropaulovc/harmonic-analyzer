r"""Pure-data dimensional contract shared by the feed-pinion sleeve and its drawing.

The transgear pinion sleeve (MHA-PD-010, R9-68): one turned steel sleeve that
runs on the MHA-PD-023 pin's Ø3.9 shank and carries, rear to front, the 12T
DP30 feed pinion that meshes the platen rack and, past one step, the Ø9 h6
boss.  The brass hub (MHA-PD-017) slides on the boss: its rear spigot passes
the 120T disc's (MHA-PD-006) bore, which pilots on it, and seats its end on the
step face, so the step is the rear stop of hub and disc; the hub drives
through the boss's D-flat, which is drive only (its end wall stands behind
the hub's own flat and never touches it).  The hub's front face is faced to
stand just behind the nose, so the MHA-PD-025 front bushing bears on the nose
and traps hub and disc against the step.  The rear face runs on the MHA-PD-024
rear bushing; both bushings and the hub are faced to fit
(``transgear_cluster_fit``, which reads this module).

Local frame: origin on the axis at the sleeve's REAR face, +Z toward the
machine FRONT.  The teeth occupy z 0..FACE_WIDTH, the boss
FACE_WIDTH..OVERALL_LENGTH; the D-flat (local -Y) runs from the nose back to
its end wall at FLAT_END_STATION.  Datums: ``RearFace`` is the Front Plane
(z 0), ``GearFace`` (the step face) an offset plane, ``Axis1`` the tooth
pattern's Top × Right axis; the sheet's datum A is the bore.

PURE DATA, no SolidWorks/COM imports: ``build_pd_transgear_feed_pinion`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION``;
``draw_pd_transgear_feed_pinion`` keeps exactly the same names.  Nothing here
imports ``transgear_cluster_fit``, the hub's spec or a bushing spec (they
import this; the hub's spec owns the hub-to-sleeve fits and the match-drilled
oil hole's location); the hub's spigot comes from the joint's pure-data
``pd_transgear_disc_hub_geometry``.
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec
import pd_transgear_pin_spec
from _fit_deviations import deviations
from _gtol_spec import CylinderFace
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_transgear_disc_hub_geometry import SPIGOT_LENGTH, SPIGOT_LENGTH_BAND

MM_PER_IN = 25.4

# The part numbers the sheet names.  Hard-coded, not read from ``_config.parts``
# (dt_crank_pinion_spec's precedent: a registry read would make the part rows
# rebuild inputs of every importer); test_pd_transgear_feed_pinion_drawing checks
# them against the registry offline.
SLEEVE_NUMBER = "MHA-PD-010"
PIN_NUMBER = pd_transgear_pin_spec.PIN_NUMBER
HUB_NUMBER = "MHA-PD-017"
DISC_NUMBER = "MHA-PD-006"
RACK_NUMBER = "MHA-PD-005"
if pd_rack_pinion_spec.HUB_NUMBER != HUB_NUMBER:
    raise AssertionError("the disc's fit note names another hub than this sheet")

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
# OVERALL_LENGTH and FLAT_END_STATION print ±0.05 (R9-5; the knob chain and
# the fitted bands read the overall: transgear_cluster_fit).  The tooth length
# prints .XXX: its end is the step face the hub's spigot seats on, so it
# places hub and disc with the spigot's own .XXX length (the bushings and the
# hub are faced to fit over both bands).
STATION_TOL = 0.05
STATION_PLACES = 2
FACE_WIDTH = 13.60  # the tooth length: rear face to the step onto the boss
FACE_WIDTH_PLACES = 3
FACE_WIDTH_BAND = printed_band_mm(FACE_WIDTH_PLACES)
OVERALL_LENGTH = 27.35

# --- diameters -----------------------------------------------------------------
# The boss is the hub's locating fit: turned h6 under the hub's Ø9 H7 bore
# (pd_transgear_disc_hub_spec checks the pair).
BOSS_DIA = 9.0
BOSS_DIA_BAND = (0.0, -0.009)  # (upper, lower) deviations, h6
BOSS_DIA_PLACES = 3

# --- the step face: the hub's seat ----------------------------------------------
# The hub's spigot bears on the step face's tooth ends, so the face is held
# square to the bore (datum A), faced in the setup that reams the bore; the
# zone is the face's extent, the 12T's tip circle.
BORE_DATUM = "A"
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "step face perpendicularity to bore": "0.005",
}
STEP_FACE_PERPENDICULARITY = float(
    GEOMETRIC_TOLERANCES_MM["step face perpendicularity to bore"]
)
STEP_FACE_PERPENDICULARITY_ZONE_DIA = OUTSIDE_DIA

# --- D-flat (local -Y): drive only ------------------------------------------------
# The hub drives through it.  The flat plane prints from the boss axis with
# its own (0, −0.015): the hub's flat sits 0.020..0.050 off it (the hub owns
# its band and checks the pair).
FLAT_TO_AXIS = 3.5
FLAT_TO_AXIS_BAND = (0.0, -0.015)  # (upper, lower) deviations
FLAT_TO_AXIS_PLACES = 3
FLAT_DEPTH = BOSS_DIA / 2.0 - FLAT_TO_AXIS  # 1.0
# The flat runs from the nose rearward to an end wall at FLAT_END_STATION,
# cut by an end mill on an axis parallel to the sleeve's, plunged from the
# nose.  The wall stops nothing: the hub's flat starts at its flange's rear
# face, the spigot's length ahead of the step, so the wall stands clear
# behind it (pd_transgear_disc_hub_spec.FLAT_END_CLEARANCE_WORST).
FLAT_END_STATION = 16.60
FLAT_LENGTH = OVERALL_LENGTH - FLAT_END_STATION  # 10.75
FLAT_LENGTH_MAX = FLAT_LENGTH + 2.0 * STATION_TOL  # 10.85
FLAT_CUTTER_FLUTE_MIN = 12.0
if FLAT_CUTTER_FLUTE_MIN < FLAT_LENGTH_MAX + 0.5:
    raise AssertionError("the flat's end mill cannot reach the end wall on its flutes")

# --- bore: a running fit on the MHA-PD-023 pin ----------------------------------------
# A running fit exists only if both size bands are narrower than the clearance
# they claim (tolerance-policy step 6b): +0.030/+0.012 over the pin's
# 0/−0.008 gives 0.012..0.038 diametral.
BORE_DIA = pd_transgear_pin_spec.DIA  # 3.9
BORE_DIA_BAND = (0.030, 0.012)  # (upper, lower) deviations, reamed
BORE_PLACES = 3
_PIN_UPPER, _PIN_LOWER = pd_transgear_pin_spec.DIA_BAND
BORE_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_BAND[1] - _PIN_UPPER, 3),
    round(BORE_DIA_BAND[0] - _PIN_LOWER, 3),
)  # 0.012 .. 0.038
if BORE_DIAMETRAL_CLEARANCE[0] <= 0.0:
    raise AssertionError(f"sleeve bore binds on the pin: {BORE_DIAMETRAL_CLEARANCE}")
BORE_PROCESS_CALLOUT = "REAM THRU"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE PIN {PIN_NUMBER}",
        f"(\N{DIAMETER SIGN}{BORE_DIA:.3f} +{_PIN_UPPER:.3f}/{_PIN_LOWER:.3f})",
        f"(DIA CLR {BORE_DIAMETRAL_CLEARANCE[0]:.3f}-{BORE_DIAMETRAL_CLEARANCE[1]:.3f} mm)",
    )
)

_BAND = {places: printed_band_mm(places) for places in (1, 2, 3)}

# --- the hub and disc on the step ------------------------------------------------
# The hub's spigot seats on the step face and passes the disc's bore; the
# hub's flange clamps the disc's front face, so that face stands the
# spigot's length ahead of the step and the disc's rear face stands in air
# ahead of it, the spigot's length less the disc's thickness (0.65 nominal;
# the hub's spec takes the worst case with the tilts).  The disc's bore is
# the spigot's, outside the 12T's tips, so the two never overlap radially.
DISC_THICKNESS = pd_rack_pinion_spec.FACE_WIDTH
DISC_FRONT_STATION = FACE_WIDTH + SPIGOT_LENGTH  # 17.25, the hub flange's seat
DISC_FRONT_STATION_BAND = FACE_WIDTH_BAND + SPIGOT_LENGTH_BAND  # 0.26
DISC_REAR_STATION = DISC_FRONT_STATION - DISC_THICKNESS  # 14.25
DISC_REAR_MIN = (
    DISC_FRONT_STATION - DISC_FRONT_STATION_BAND - pd_rack_pinion_spec.FACE_WIDTH_MAX
)  # 13.86
if pd_rack_pinion_spec.BORE_DIA_MIN <= OUTSIDE_DIA + OUTSIDE_DIA_BAND[0]:
    raise AssertionError("the disc's bore overlaps the 12T's tips radially")

# --- 12T form-cutter run-out (R9-67, on the knob shaft's R9-21) ---------------
# The 12T is cut with a form cutter on a dividing head from the open rear
# face: full depth from the rear face to FULL_DEPTH, then the cutter's arc runs
# out behind that station, leaving partial-depth gaps over the rest of the
# teeth and, at its deepest, short slots in the boss ahead of the step,
# under the hub spigot's bore.  The section prints the full-depth station as a
# native baseline dimension from the rear face with its .XXX band, and the
# run-out's end (where the cutter rises clear of the Ø9 boss) as a native MAX
# limit (construction witnesses in ``SleeveProfile``, each named by its model
# prefix); the note gives the largest cutter that keeps that window.  The
# model cuts full depth over the whole tooth length and leaves the slots out
# (0.05 long at the nominal cutter).
FULL_DEPTH = 10.20
FULL_DEPTH_PLACES = 3
CUTTER_RUNOUT_MAX = 13.80  # from the rear face, a limit
CUTTER_RUNOUT_PLACES = 2
CUTTER_DIA_MAX_IN = 1.00
CUTTER_DIA_MAX = CUTTER_DIA_MAX_IN * MM_PER_IN  # 25.4
FULL_DEPTH_BAND = printed_band_mm(FULL_DEPTH_PLACES)
FULL_DEPTH_MIN = FULL_DEPTH - FULL_DEPTH_BAND  # 10.07
FULL_DEPTH_MAX = FULL_DEPTH + FULL_DEPTH_BAND  # 10.33
# swTolMAX prints the dimension's NOMINAL followed by "MAX", so the witness
# sits at the limit; its deviations record "anywhere behind the shortest full
# depth, up to the limit".
CUTTER_RUNOUT_TOL_TYPE = 6  # swTolType_e.swTolMAX
CUTTER_RUNOUT_DEVIATIONS = (FULL_DEPTH_MIN - CUTTER_RUNOUT_MAX, 0.0)
if round(CUTTER_RUNOUT_MAX, CUTTER_RUNOUT_PLACES) != CUTTER_RUNOUT_MAX:
    raise AssertionError("the run-out limit does not print at its places")
FULL_DEPTH_PREFIX = "12T FULL DEPTH "
CUTTER_RUNOUT_PREFIX = "CUTTER RUN-OUT "
CUTTER_NOTE = f"12T FORM CUTTER \u00d8{CUTTER_DIA_MAX_IN:.2f} in MAX."


def cutter_runout(cutter_dia: float, rise: float) -> float:
    """Axial length behind the full-depth station over which a form cutter of
    ``cutter_dia`` still cuts a surface ``rise`` above the gap floor: the
    chord half-length of its circle at that height, √(Rc² − (Rc − rise)²)."""
    radius = cutter_dia / 2.0
    if not 0.0 <= rise <= radius:
        raise ValueError(f"rise {rise} is off a Ø{cutter_dia} cutter")
    return (radius**2 - (radius - rise) ** 2) ** 0.5


# The rack's worst reach from the rear face is the assembly's stack
# (build_pd_paper_drive_assembly.RACK_FRONT_FROM_SLEEVE_REAR_WORST), which
# asserts FULL_DEPTH_MIN covers it.  The boss at its largest radius over the
# shallowest-printed gap floor (the root's MIN), 4.500 − 4.020 = 0.48, runs
# out 3.46 behind the deepest full-depth station, 13.79, inside the 13.80
# limit.  The slots end under the hub's spigot (the hub's spec takes them off
# its round engagement, ROUND_ENGAGEMENT_MIN) and stand behind the disc's
# nearest rear face (13.86) by RUNOUT_DISC_CLEARANCE: the disc sits on the
# spigot, radially outside the boss, so the margin only keeps the slots'
# end behind the disc's plane.
RUNOUT_RISE_WORST = (BOSS_DIA + BOSS_DIA_BAND[0]) / 2.0 - ROOT_DIA_MIN / 2.0
CUTTER_RUNOUT_END_WORST = FULL_DEPTH_MAX + cutter_runout(
    CUTTER_DIA_MAX, RUNOUT_RISE_WORST
)  # 13.79
RUNOUT_DISC_CLEARANCE = 0.05
if FULL_DEPTH_MAX >= FACE_WIDTH - _BAND[FACE_WIDTH_PLACES]:
    raise AssertionError("the 12T full-depth window reaches the step")
if CUTTER_RUNOUT_END_WORST > CUTTER_RUNOUT_MAX + 1e-9:
    raise AssertionError(
        f"a Ø{CUTTER_DIA_MAX_IN:.2f} in cutter runs out to "
        f"{CUTTER_RUNOUT_END_WORST:.3f}, past the {CUTTER_RUNOUT_MAX} limit"
    )
if CUTTER_RUNOUT_END_WORST > DISC_REAR_MIN - RUNOUT_DISC_CLEARANCE + 1e-9:
    raise AssertionError(
        f"the cutter runs out to {CUTTER_RUNOUT_END_WORST:.3f}, within "
        f"{RUNOUT_DISC_CLEARANCE} of the disc's rear face {DISC_REAR_MIN:.3f}"
    )
if CUTTER_RUNOUT_MAX > DISC_REAR_MIN - RUNOUT_DISC_CLEARANCE + 1e-9:
    raise AssertionError("the run-out limit reaches the disc's rear face")

# --- oil hole (R9-8) -----------------------------------------------------------
# Ø1.2 drilled (+0.10/0) on +Y, centred on the hub body (R9-60), through hub
# and boss wall in one operation at assembly.  The hub's spec owns its size,
# its sleeve-local station (pd_transgear_disc_hub_spec.OIL_HOLE_SLEEVE_Z) and
# the ligament to this nose; this sheet's drawing carries the drill note
# (draw_pd_transgear_feed_pinion.OIL_HOLE_NOTE, which reads the hub's size).
OIL_HOLE_AZIMUTH_DEG = 90.0  # local +Y, opposite the flat

# Tooth phase: the seed gap is centred half a pitch CCW of local +X
# (involute_gear.gear_facts: (ThetaL + ThetaU) / 2 = Gamma / 2) and the pattern
# steps a pitch, so gap centres sit at 15° + k·30°.  +Y (90°) is a TOOTH
# centre; the oil hole is on the boss well in front of the teeth anyway, so
# no clocking is needed.
TOOTH_PITCH_DEG = 360.0 / TEETH
GAP_CENTRE_PHASE_DEG = TOOTH_PITCH_DEG / 2.0
OIL_HOLE_TOOTH_OFFSET_DEG = (
    OIL_HOLE_AZIMUTH_DEG - GAP_CENTRE_PHASE_DEG
) % TOOTH_PITCH_DEG
if abs(OIL_HOLE_TOOTH_OFFSET_DEG - GAP_CENTRE_PHASE_DEG) > 1e-9:
    raise AssertionError("the +Y oil hole is no longer on a tooth centre")

# --- walls (rule 12: target 2.0, floor 1.5, at the printed bands) --------------
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
_BORE_MAX = BORE_DIA + BORE_DIA_BAND[0]  # 3.930
# Under the root: (8.0433 − 3.900)/2 = 2.072 nominal; (8.04 MIN − 3.930)/2 = 2.055.
ROOT_WALL = (ROOT_DIA - BORE_DIA) / 2.0
ROOT_WALL_WORST = (ROOT_DIA_MIN - _BORE_MAX) / 2.0
# Boss: (9 − 3.9)/2 = 2.55; (8.991 − 3.93)/2 = 2.53.
BOSS_WALL = (BOSS_DIA - BORE_DIA) / 2.0
BOSS_WALL_WORST = (BOSS_DIA + BOSS_DIA_BAND[1] - _BORE_MAX) / 2.0
WALLS = (
    ("under the root", ROOT_WALL, ROOT_WALL_WORST),
    ("boss", BOSS_WALL, BOSS_WALL_WORST),
)
for _name, _nominal, _worst in WALLS:
    if _worst < WALL_TARGET:
        raise AssertionError(f"sleeve wall {_name} {_worst:.3f} under {WALL_TARGET}")
# Under the flat: 3.5 − 1.95 = 1.55 nominal; 3.485 − 1.965 = 1.52 at the
# worst case, under the 2.0 target (the Named exceptions row): it is judged
# against the 1.5 floor and printed as a MIN, floored at two places.
FLAT_WALL = FLAT_TO_AXIS - BORE_DIA / 2.0
FLAT_WALL_WORST = round(FLAT_TO_AXIS + FLAT_TO_AXIS_BAND[1] - _BORE_MAX / 2.0, 6)
FLAT_WALL_PRINTED = math.floor(FLAT_WALL_WORST * 100.0) / 100.0  # 1.52
if FLAT_WALL_WORST < WALL_FLOOR:
    raise AssertionError(f"the D-flat wall {FLAT_WALL_WORST:.3f} is under the floor")

# One roughness, on the one running surface: the bore.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

# --- Marked-dimension contract -------------------------------------------------
# ``GearBlank`` is the tooth blank's extrude (its depth is the tooth length).
# ``SleeveProfile`` is the Right-plane revolve of the boss, with
# construction-only witnesses for the tooth tip, the root and the bore, so
# every turned diameter prints beside its axial extent on the longitudinal
# section (rules 2 and 7), and for the cutter's full-depth station, its
# run-out limit (R9-67).  Lengths are baselined from the rear face.
# ``FlatProfile`` is the flat's cut sketch on the Right plane (the section
# plane): the flat from the axis and its end wall from the rear face print on
# the section, where the flat shows edge-on.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "SleeveProfile": {
        "OutsideDia",
        "RootDia",
        "BoreDia",
        "BossDia",
        "OverallLength",
        "FullDepth",
        "CutterRunout",
    },
    "FlatProfile": {"FlatToAxis", "FlatEnd"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "SleeveProfile": {
        "OutsideDia": 3,
        "RootDia": ROOT_DIA_PLACES,
        "BoreDia": BORE_PLACES,
        "BossDia": BOSS_DIA_PLACES,
        "OverallLength": STATION_PLACES,
        "FullDepth": FULL_DEPTH_PLACES,
        "CutterRunout": CUTTER_RUNOUT_PLACES,
    },
    "FlatProfile": {
        "FlatToAxis": FLAT_TO_AXIS_PLACES,
        "FlatEnd": STATION_PLACES,
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
BOSS_DIA_DEVIATIONS = deviations(BOSS_DIA_BAND)
FLAT_TO_AXIS_DEVIATIONS = deviations(FLAT_TO_AXIS_BAND)
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

# The title block's 0.25 edge break is 14% of this fine tooth's whole depth,
# and the tooth ends seat the hub's spigot.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
# Named exception: MHA-PD-010 flat wall (drawing-simplicity-policy.md, "Named exceptions").
FLAT_WALL_NOTE = f"D-FLAT WALL TO BORE {FLAT_WALL_PRINTED:.2f} MIN."
DRAWING_NOTES = "\n".join((TOOTH_EDGE_NOTE, CUTTER_NOTE, FLAT_WALL_NOTE))
