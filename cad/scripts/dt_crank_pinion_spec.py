r"""Pure-data dimensional contract shared by the crank pinion and its drawing.

The 16T straight-spur pinion on the crankshaft that meshes the 64T crank-drive
gear (4:1 crank-to-cone reduction), with the plain hub boss on its outboard
face that the ch. 12 p. 19 photos show (page002_img02 / img06): a cylinder at
the tooth root, a little over half a face long, edge rounded, the crankshaft
end recessed inside it, and the small head of a radial retention pin on its
side. The pin is what keeps the "removable" pinion on the shaft.

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The sizes a
machinist turns, bores and drills -- outside diameter, face width, bore, boss
diameter, overall length, pin station -- are NATIVE model dimensions carrying
their own decimal places and bands (rules 1, 2, 4); the tooth system that a
cut-gear print cannot express as dimensions stays in the gear-data block rule 6
allows, with cutter inputs and derived diameters marked REF and the circular
tooth thickness carrying its own functional limit; nothing here restates the
title block.

PURE DATA, no SolidWorks/COM imports: ``build_dt_crank_pinion`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model,
``draw_dt_crank_pinion`` keeps exactly the same names, and the offline test
(``test_dt_crank_pinion_drawing.py``) fails the moment one side drifts.
"""

from __future__ import annotations

import math

import _config
import dt_crank_drive_gear_notes
import dt_crank_drive_gear_spec
import dt_crank_hub_geometry
from _fit_limits import deviations
from _gtol_spec import CylinderFace
from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 16
# Cut straight by the 64T's own cutter (#906): a straight gear's transverse
# section IS its normal section, so the cutter's DP and pressure angle are this
# gear's, and the pair's normal pitches match.
DIAMETRAL_PITCH = dt_crank_drive_gear_spec.CUTTER_DIAMETRAL_PITCH  # 26.306
PRESSURE_ANGLE_DEG = dt_crank_drive_gear_spec.CUTTER_PRESSURE_ANGLE_DEG
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
TRANSVERSE_CIRCULAR_TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0
# The crank-specific discrete voxel/phase study checks the shipped 0.150 mm
# tooth thinning at nominal geometry but does not sweep centre distance, helix,
# shaft-angle, face-offset or bore-clearance tolerances; its 0.100 mm sample is
# not a proven threshold.
# Do not let this member consume that unverified margin. Its maximum thickness
# therefore stays nominal, and its -0.020 mm side reuses MHA-DT-007's established
# tooth-control capability. At the nominal geometry the pair's tooth-thinning
# contribution remains 0.150..0.191 mm after converting the mate's normal-span
# band to transverse thickness.
TOOTH_THICKNESS_UPPER_DEVIATION = 0.000
TOOTH_THICKNESS_LOWER_DEVIATION = -0.020

# The blank tip circles retain the ruled +/-0.10 turning band. The fixed-centre
# mesh's nonbinding stack, rather than an eccentric fit-up, owns tip/root air.
OUTSIDE_DIA_TOLERANCE_MM = 0.10
MESH_C2C_SLACK_MM = _config.fit("crank_mesh")["c2c_slack_mm"]
TIP_CLEARANCE_MM = 0.157 / DIAMETRAL_PITCH * MM_PER_IN

# RULING (b), Main 2026-09-26 (#906): the crankshaft steps down to SEAT_DIA
# under this pinion, and the pinion is bored to match. A smaller 16T cut by
# the pair's one cutter would leave the boss wall under its 1.5 floor over
# the 3/8 in shaft; the step gives the wall back without tightening a band.
# The seat is turned to the through shaft's own size band
# (dt_crankshaft_spec.PINION_SEAT_DIA_BAND), so the fit below is the class it
# always was.
SEAT_DIA = 9.0

# The bore over the crankshaft's seat is the part's one critical fit, and the
# only reason anything here prints a third decimal: a slip fit exists only if
# the size limits on BOTH mating features are narrower than the clearance band
# it claims (tolerance-policy.md step 6b). The feature callout names the mate
# and publishes the required diametral-clearance range; the dimensional band is
# DERIVED -- never a per-part number -- from that named fit class and the
# seat's own published limits: bore_min = seat_max + clearance_min,
# bore_max = seat_min + clearance_max. Move either input and this moves with it.
BORE_DIA = SEAT_DIA
BORE_DIAMETRAL_CLEARANCE = tuple(
    _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
)
_CLEARANCE_MIN, _CLEARANCE_MAX = BORE_DIAMETRAL_CLEARANCE
_SHAFT_UPPER, _SHAFT_LOWER = dt_crank_hub_geometry.SHAFT_DIA_BAND
BORE_DIA_BAND = (  # (upper, lower) deviations
    round(_SHAFT_LOWER + _CLEARANCE_MAX, 3),
    round(_SHAFT_UPPER + _CLEARANCE_MIN, 3),
)

FACE_WIDTH = 11.6  # teeth grown north past the 64T row; south face stays seated
# The south face and boss length stay where they were. The 64T row is 7.2113
# wide. Codex P1 on #1128 (user ruling 2026-09-29) banded the tooth length
# at +0/-0.30; the user's c'' ruling (variant B, 2026-09-30) then grew the
# teeth 1.8 north so the row stays covered with the pinion on the boss and
# the cone stack floated north, and turned the grown north end down so it
# passes under the inclined T120 rim. Ruling R9-55 grew them a further 0.1
# north once the row was taken slice by slice: each 64T slice meshes at its
# own contact azimuth, and the floated north slices reach farther north than
# a translated nominal row. Ruling R9-56 grew them 0.2 more once the row
# also carried every permitted axis pose (build_dt_drive_train_assembly
# crank_row_engagement). FACE_WIDTH is the whole tooth length
# (the part's GearBlank extrusion) and still prints: it places the boss step.
# Functional reason for its band inside the .X row: at the row's -0.8 the
# teeth cover under 85% of the 64T row, and its long limit bounds the turned
# band's T120 clearance (build_dt_drive_train_assembly proves both).
FACE_WIDTH_BAND = (0.0, -0.30)  # (upper, lower) deviations
FACE_WIDTH_LIMITS = deviations(FACE_WIDTH_BAND)  # (lower, upper)
# Full-OD shoulder: the teeth run at OutsideDia SHOULDER_LENGTH from the south
# face, stated like FaceWidth (+0/-0.30 at .X). Functional reason for the band
# inside the .X row: at the row's +0.8 the full-OD shoulder runs into the
# inclined T120 (build_dt_drive_train_assembly proves the 0.25 axial air at the
# band's long limit with T120 on its nominal axis; the fit offsets and axis
# poses are the fit-up check below).
SHOULDER_LENGTH = 8.5
SHOULDER_LENGTH_BAND = (0.0, -0.30)  # (upper, lower) deviations
SHOULDER_LENGTH_LIMITS = deviations(SHOULDER_LENGTH_BAND)  # (lower, upper)
# North of the shoulder the teeth are turned to TURNED_DIA, stated like the
# OutsideDia it cuts into (+/-0.10 at .XX). Functional reason for the band
# inside the .XX row: build_dt_drive_train_assembly proves the T120 tip circle
# 0.25 radially clear of the turned band at its upper limit, T120 on its
# nominal axis; at the row's +0.51 that air falls to about 0.05.
TURNED_DIA = 16.21
TURNED_DIA_TOLERANCE_MM = 0.10
TURNED_LENGTH = FACE_WIDTH - SHOULDER_LENGTH
# Fit-up of the 16T under T120 (user, 2026-09-30, #1154).  With every fit
# offset and axis pose of the drive train summed at its worst, the shoulder
# and the turned band can close on T120 by these clearances (negative: an
# overlap), rounded down to 0.01 -- the policy's Named exceptions row
# "MHA-DT-010 ... T120"; build_dt_drive_train_assembly derives them and fails if
# they are not its figures.  Both sheets state them.
T120_SHOULDER_AIR_WORST = -0.10
T120_TURNED_BAND_RADIAL_WORST = -0.12
# So the pair is checked on a feeler at fit-up instead of by a tighter
# stack, MHA-DT-010 and T120 pushed toward each other: those two pushes take up
# every play that can still move afterwards, so what passes the feeler keeps
# it in service.  A band that stops the feeler is turned down, never under
# TURNED_DIA_FITUP_MIN: a band that size clears T120 by the feeler at every
# corner of that stack, and still meshes with the 64T wherever the check can
# call for it (build_dt_drive_train_assembly proves both).  A shoulder that
# stops it is faced back, never under its printed short limit, where the air
# again clears the feeler by geometry.
T120_FITUP_FEELER_MM = 0.10
TURNED_DIA_FITUP_MIN = 15.78
SHOULDER_LENGTH_FITUP_MIN = SHOULDER_LENGTH + SHOULDER_LENGTH_LIMITS[0]

# --- Hub boss + retention pin (ch. 12 p. 19, page002_img02 / img06) ---------
#
# The boss is the blank turned down to the ROOT circle beyond the toothed
# length: the photo reads it at the tooth roots, and the root circle is the
# largest diameter that can never meet the 64T's tips (they clear it by the
# tooth system's own tip clearance plus the mesh's centre-distance slack,
# exactly as they clear the gap floors). It runs from the toothed length to the
# overall length, covers the crankshaft's outboard overhang past the pinion's
# north face and leaves its end recessed inside the boss as photographed; its
# length is derived below (W15). The boss is
# extruded from the SAME faced end as the teeth, so the print carries one
# overall length from that end (rule 7: lengths from one faced end, the overall
# length real and conspicuous), and the toothed length is FaceWidth.
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN  # 13.21
BOSS_DIA = ROOT_DIA
# The boss's outer end edge takes the title block's edge break: the sized
# chamfer that once imitated the photo's rounding had no function, and at its
# general grade it could reach the bore (machinist review of 4d4e038e3).


def printed_band_mm(places: int) -> float:
    """The +/- the metric sheet PRINTS for a dimension shown at ``places``.

    An accepted part is checked against the title block's printed row (.X
    +/-0.8), not the inch grade behind it (0.03 in = 0.762): Codex P2 on #892.
    """
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


def printed_deviations(
    model: float, places: int, limits: tuple[float, float] | None = None
) -> tuple[float, float]:
    """``(lower, upper)`` deviations from the MODEL value an accepted part may
    show: the sheet prints the model rounded to ``places`` and checks the part
    against that number's limits -- the printed general row unless the
    dimension's own ``(lower, upper)`` limits (``deviations(band)``) are given."""
    if limits is None:
        grade = printed_band_mm(places)
        limits = (-grade, grade)
    lower, upper = limits
    printed = round(model, places)
    return printed + lower - model, printed + upper - model


def ceil_to_places(value: float, places: int) -> float:
    scale = 10.0**places
    return math.ceil(round(value * scale, 6)) / scale


def floor_to_places(value: float, places: int) -> float:
    scale = 10.0**places
    return math.floor(round(value * scale, 6)) / scale


# USER RULING 2026-09-25, MHA-DT-010 boss option C: the boss stays at the tooth
# root, where a form cutter runs out onto it untouched and the photo reads it;
# a boss proud of the root is scalloped by the cutter's arc up to the pin hole.
# Its worst wall -- the printed diameter at its general row over the bore's
# upper limit -- is therefore a ruled exception under the 2.0 wall target,
# held above the 1.5 floor here, so an OD, tooth or bore change that eats
# into the floor fails loud.
BOSS_DIA_PLACES = 1
BOSS_WALL_FLOOR_MM = 1.5
_BORE_LOWER, _BORE_UPPER = deviations(BORE_DIA_BAND)
_BOSS_DIA_LOWER, _BOSS_DIA_UPPER = printed_deviations(BOSS_DIA, BOSS_DIA_PLACES)
BOSS_WALL_WORST = (BOSS_DIA + _BOSS_DIA_LOWER - (BORE_DIA + _BORE_UPPER)) / 2.0  # 1.6725
if BOSS_WALL_WORST < BOSS_WALL_FLOOR_MM:
    raise AssertionError(
        f"16T boss worst wall {BOSS_WALL_WORST:.3f} is under the {BOSS_WALL_FLOOR_MM} "
        "floor of the 2026-09-25 option-C ruling"
    )

# Retention pin: a plain 1/8 in straight pin (stock drill rod) through the boss
# and crankshaft, match-drilled at assembly with the pinion on its seat. The
# drawing therefore governs the hole by its fit to the named pin, not by the
# model's nominal drill diameter: the shop drills undersize and reams until the
# actual pin is a light drive fit. The callout locates the operation at the
# boss mid-length and requires the fitted pin flush on both sides. The hole sits
# on the pinion's local -X; its clocking against the 64T tooth-in-gap seed is
# carried by the crankshaft hole, whose entry point is turned by
# PIN_CLOCKING_DEG. The assembly places the pinion rot_z(-seed) and asserts that
# this constant is its seed, so a re-derived mesh phase fails loud at import
# instead of drilling the shaft at the old angle.
PIN_HOLE_SPEC = HoleSpec("drilled_fractional", "1/8")
PIN_DIA = FRACTIONAL_DRILL_MM["1/8"]  # 3.175
PIN_LENGTH = BOSS_DIA  # flush both sides

# --- W15: shortest boss that still protects the match-drilled shaft end ----
#
# The ch12 photograph suggests a compact hub, but its length is controlled
# by the pin's print-worst 2.0-mm ligament to the recessed crankshaft end,
# not by a nominal 4.5-mm wall. The Ø3.175 pin stays at the actual boss
# mid-length, with the existing layout allowance.
PIN_EDGE_MIN_WORST = 2.0
PIN_STATION_LAYOUT_ALLOWANCE_MM = 0.25
# The toothed south face is set directly off the restored MHA-DT-005 north
# boss face with the assembly step-4 feeler. There is no spot-face retreat
# or eccentric sleeve in this stack.
SEAT_FEELER_MM = 0.25
SEAT_GAP_MAX_MM = 1.0
PINION_BOSS_NORTH_GAP_RANGE = (SEAT_FEELER_MM, SEAT_GAP_MAX_MM)
# The shaft end stays recessed inside the boss in the worst case too.  The
# overall length prints at OVERALL_LENGTH_PLACES, so an accepted pinion is as
# short as the printed row allows (.X +/-0.8).  Nothing else can shallow the
# recess: the pinion seats at the boss-north gap FLOOR
# (build_dt_drive_train_assembly), so the seat can only move it north, and the
# shaft length is +0/-0.40, so the shaft can only get shorter.  Both lengths
# are sized to print EXACTLY at their places, so no rounding of a printed
# nominal can eat the margin (Codex P2 on #892): dt_crankshaft_spec floors the
# shaft length to SHAFT_LENGTH_PLACES, which leaves the nominal recess between
# its minimum and one printed unit more, and the boss is sized for the most.
OVERALL_LENGTH_PLACES = 1
SHAFT_LENGTH_PLACES = 1  # dt_crankshaft_spec prints its Depth here
FACE_WIDTH_PLACES = 1
SHOULDER_LENGTH_PLACES = FACE_WIDTH_PLACES  # stated like FaceWidth
TURNED_DIA_PLACES = 2  # stated like the OutsideDia it cuts into
OVERALL_LENGTH_GRADE_MM = printed_band_mm(OVERALL_LENGTH_PLACES)
# W15 sizes the boss for a face accepted anywhere in the .X row. The printed
# band sits inside that row, so the boss keeps its length (no geometry change
# under the ruling) and every W15 stack only gains margin.
W15_FACE_ALLOWANCE_MM = printed_band_mm(FACE_WIDTH_PLACES)
_FACE_LOWER, _FACE_UPPER = FACE_WIDTH_LIMITS
if _FACE_LOWER < -W15_FACE_ALLOWANCE_MM or _FACE_UPPER > W15_FACE_ALLOWANCE_MM:
    raise AssertionError("the 16T face band left the .X row W15 sizes the boss for")
SHAFT_LENGTH_SHORT_MM = 0.40  # preserved W15 unilateral +0/-0.40 shaft band
SHAFT_END_RECESS_MIN_WORST = 0.25
SHAFT_END_RECESS_MIN = SHAFT_END_RECESS_MIN_WORST + OVERALL_LENGTH_GRADE_MM
SHAFT_END_RECESS_MAX = SHAFT_END_RECESS_MIN + 10.0**-SHAFT_LENGTH_PLACES
# The pin's drilled-hole grade grows its radius by half the printed oversize.
# At boss mid-length, each accepted face/overall row can shift the pin north
# by half its allowance; the seat gap can also open to its stated maximum.
_PIN_HOLE_RADIUS_GROWTH = float(_config.title_block("drilled_hole")["plus_mm"]) / 2.0
_PIN_EDGE_CLOSING_TERMS = (
    SHAFT_LENGTH_SHORT_MM
    + SEAT_GAP_MAX_MM - SEAT_FEELER_MM
    + (W15_FACE_ALLOWANCE_MM + OVERALL_LENGTH_GRADE_MM) / 2.0
    + PIN_STATION_LAYOUT_ALLOWANCE_MM
    + _PIN_HOLE_RADIUS_GROWTH
)
# The exact shaft recess depends on its one-place floor and installed post
# station; SHAFT_END_RECESS_MAX is the safe ceiling of that range. The shaft
# spec independently checks the actual floor and proves that the next shorter
# printable boss fails it. No tolerance or pin size is tightened for the photo.
BOSS_LENGTH_PLACES = OVERALL_LENGTH_PLACES
BOSS_LENGTH = ceil_to_places(
    2.0 * (
        PIN_EDGE_MIN_WORST
        + SHAFT_END_RECESS_MAX
        + PIN_DIA / 2.0
        + _PIN_EDGE_CLOSING_TERMS
    ),
    BOSS_LENGTH_PLACES,
)
OVERALL_LENGTH = round(FACE_WIDTH + BOSS_LENGTH, OVERALL_LENGTH_PLACES)
for _name, _value, _places in (
    ("FACE_WIDTH", FACE_WIDTH, FACE_WIDTH_PLACES),
    ("OVERALL_LENGTH", OVERALL_LENGTH, OVERALL_LENGTH_PLACES),
    ("SHOULDER_LENGTH", SHOULDER_LENGTH, SHOULDER_LENGTH_PLACES),
    ("TURNED_DIA", TURNED_DIA, TURNED_DIA_PLACES),
    ("TURNED_DIA_FITUP_MIN", TURNED_DIA_FITUP_MIN, TURNED_DIA_PLACES),
):
    if abs(_value - round(_value, _places)) > 1e-9:
        raise AssertionError(f"{_name} {_value!r} does not print exactly at {_places} places")
# The turned band is a real band of stub teeth at every accepted size: the
# shoulder ends short of the tooth end, and the turned diameter stays above
# the root (where the boss is) and below the tip.
if SHOULDER_LENGTH + SHOULDER_LENGTH_LIMITS[1] >= FACE_WIDTH + FACE_WIDTH_LIMITS[0]:
    raise AssertionError("the 16T full-OD shoulder reaches the tooth end")
if not (
    BOSS_DIA < TURNED_DIA - TURNED_DIA_TOLERANCE_MM
    and TURNED_DIA + TURNED_DIA_TOLERANCE_MM < OUTSIDE_DIA - OUTSIDE_DIA_TOLERANCE_MM
):
    raise AssertionError("the 16T turned band must lie between the root and the tip")
# The fit-up turn-down leaves stub teeth: above the pitch circle, below the band.
if not PITCH_DIA < TURNED_DIA_FITUP_MIN < TURNED_DIA - TURNED_DIA_TOLERANCE_MM:
    raise AssertionError("the 16T fit-up turn-down must stay over the pitch circle")
PIN_STATION = FACE_WIDTH + BOSS_LENGTH / 2.0
PIN_AXIAL_LIGAMENT_FLOOR_MM = 0.5
PIN_AXIAL_LIGAMENT_WORST = (
    (BOSS_LENGTH - W15_FACE_ALLOWANCE_MM - OVERALL_LENGTH_GRADE_MM) / 2.0
    - PIN_DIA / 2.0
    - _PIN_HOLE_RADIUS_GROWTH
    - PIN_STATION_LAYOUT_ALLOWANCE_MM
)
if PIN_AXIAL_LIGAMENT_WORST < PIN_AXIAL_LIGAMENT_FLOOR_MM:
    raise AssertionError("match-drilled pin breaks through the boss end at print-worst")
if SHAFT_END_RECESS_MAX <= SHAFT_END_RECESS_MIN:
    raise AssertionError("the pinion boss needs a positive printed shaft-recess range")
# The fixed-axis tooth-in-gap seed follows the installed 64T centre; the
# assembly asserts this cross-hole clock against its independently derived
# seed so the shaft's radial pin hole tracks a centre-station change.
PIN_CLOCKING_DEG = 12.037647012980765
if not 0.0 <= PIN_CLOCKING_DEG < 360.0 / 16.0:
    raise AssertionError("pinion retention-hole clocking must lie within one 16T pitch")
# The matched-hole callout on both part records identifies both seated parts,
# the shared boss-mid-length operation and the actual fitted pin. It deliberately
# omits the modeled hole nominal: reaming to a functional acceptance governs,
# and the pin identity plus flush condition stay on the feature callout.
# The part numbers are hard-coded, not read from ``_config.parts``: this module
# reaches the crank-mesh stack, and through it the cone-swing platform and every
# script that imports that, so a registry read here would make three part rows
# rebuild inputs of the frame (dt_crank_drive_gear_notes' precedent).
# test_dt_crank_pinion_drawing checks them against the registry offline.
CRANKSHAFT_NUMBER = "MHA-DT-011"
PINION_NUMBER = "MHA-DT-010"
PIN_NUMBER = "MHA-DT-029"
BORE_PROCESS_CALLOUT = "REAM THRU"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE SHAFT {CRANKSHAFT_NUMBER}",
        f"(\N{DIAMETER SIGN}{SEAT_DIA:.3f} "
        f"+{_SHAFT_UPPER:.3f}/{_SHAFT_LOWER:.3f})",
        f"(DIA CLR {_CLEARANCE_MIN:.3f}-{_CLEARANCE_MAX:.3f} mm)",
    )
)
# One matched-fit note, printed on BOTH sheets (machinist review of 4d4e038e3):
# a sheet stands alone, so each carries all four facts --
# match drill at assembly, ream to fit the named pin, the fit's acceptance,
# flush -- with the other part and where on this one the hole runs.
# Four lines, no dimensions (rule 6); MHA-DT-000 step 4 reads the shaft's.
PIN_FIT_LINES = (
    f"REAM TO FIT PIN {PIN_NUMBER}, LIGHT HAMMER FIT",
    "NOT REMOVABLE BY HAND, FLUSH BOTH SIDES",
)


def pin_hole_note(mate_number: str, where: str) -> str:
    return "\n".join((f"MATCH DRILL AT ASSY WITH {mate_number}", where, *PIN_FIT_LINES))


PIN_HOLE_PROCESS = pin_hole_note(CRANKSHAFT_NUMBER, "AT BOSS MID-LENGTH")
# The shaft's narrower field needs the reaming instruction split before the
# pin identity, without changing any process words or the four-line height.
CRANKSHAFT_PIN_HOLE_PROCESS = pin_hole_note(
    PINION_NUMBER, "AT ITS BOSS MID-LENGTH"
).replace("\nREAM TO FIT PIN ", " REAM TO FIT\nPIN ")

# One roughness, on the one surface whose function depends on it: the bore is
# a size-toleranced fit onto the crankshaft, and a fit lives on the peaks as
# much as on the limits, so the bore carries the project's general machined
# grade. Nothing runs on the teeth or the faces -- they are as the title
# block's process row states (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("crank_pinion_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_dt_crank_pinion`` marks exactly these; ``draw_dt_crank_pinion``
# keeps exactly their union across its per-view ``keep`` maps. The
# ``BossProfile`` is a Right-plane revolve profile with construction-only
# witnesses for the tooth blank and bore. It therefore owns all four printed
# turned diameters/lengths on the side view without changing the solid:
# ``BossDia`` and ``OverallLength`` drive the revolve, while ``OutsideDia`` and
# ``BoreDia`` are equation-driven native reference dimensions attached to the
# matching axial extents (rule 2's reference-sketch allowance and rule 7's
# turned-part layout). The ``TurnedBandProfile`` is the Right-plane revolve
# cut that turns the teeth down north of the shoulder; its shoulder length
# (from the same faced end) and turned diameter drive it. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "BossProfile": {"OutsideDia", "BoreDia", "BossDia", "OverallLength"},
    "TurnedBandProfile": {"ShoulderLength", "TurnedDia"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2: the places a dimension prints are part of the tolerance it
# claims, and the model owns both. ``build_dt_crank_pinion`` applies this table
# natively (``_drawing_marks.apply_drawing_precision``) right after the drawing
# marks, so ``draw_dt_crank_pinion`` imports each dimension verbatim and only reads
# ``GetPrimaryPrecision2()`` back off the sheet.
#
# The bore is the only size fit on the part and prints three places with its
# derived band. The outside diameter prints two with its own +/-0.10. The face
# width prints one place with its own +0/-0.30 (FACE_WIDTH_BAND): the assembly
# proves the 64T row overlap at its short limit and the turned band's T120
# clearance at its long one. The shoulder length prints one place and the
# turned diameter two, each with the band its reason is recorded at above.
# The boss diameter is routine .XX, not a running surface. The match-drilled
# pin station is absent: its callout locates it at boss mid-length and the
# crankshaft/pinion stack sets it. The overall length prints one place like
# the face, with the W15 boss sized for the recessed shaft-end condition.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "BossProfile": {
        "OutsideDia": 2,
        "BoreDia": 3,
        "BossDia": BOSS_DIA_PLACES,
        "OverallLength": OVERALL_LENGTH_PLACES,
    },
    "TurnedBandProfile": {
        "ShoulderLength": SHOULDER_LENGTH_PLACES,
        "TurnedDia": TURNED_DIA_PLACES,
    },
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])

# The pair's worst-case contact ratio, rounded down, as the MHA-DT-007 sheet
# prints it (dt_crank_drive_gear_notes owns the one value; user ruling 2026-09-30).
# Named exception: MHA-DT-010 contact ratio (drawing-simplicity-policy.md, "Named exceptions").
CONTACT_RATIO_ROW = (
    "CONTACT RATIO WITH MHA-DT-007, WORST CASE (REF)",
    f"{dt_crank_drive_gear_notes.WORST_CONTACT_RATIO:.2f}",
)

# Rule 6's gear-data block: the tooth system a cut-gear drawing cannot express
# as ordinary view dimensions. Cutter inputs and derived diameters are REF;
# circular tooth thickness is the shop's controlling acceptance and carries
# the explicit one-sided pair-derived limit above.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        (
            "DIAMETRAL PITCH",
            f"{DIAMETRAL_PITCH:.2f} (NONSTANDARD; MHA-DT-007'S CUTTER)",
        ),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.2f}"),
        (
            "CIRCULAR TOOTH THICKNESS (mm)",
            f"{TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f} "
            f"+{TOOTH_THICKNESS_UPPER_DEVIATION:.3f}/"
            f"{TOOTH_THICKNESS_LOWER_DEVIATION:.3f}",
        ),
        ("TOOTH FORM", "SPUR INVOLUTE, FULL DEPTH"),
        ("MATES WITH", "CRANK DRIVE GEAR MHA-DT-007, 64T"),
        CONTACT_RATIO_ROW,
    ]
)

# The title block's normal 0.25 edge break is a quarter of this fine tooth's
# whole depth, so the print carries the one part-specific exception it needs.
# The nonstandard cutter geometry is already explicit in the gear-data block;
# it needs no duplicate method prohibition.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
# The sheet states the thin boss wall as a plain fact, rounded down so it
# never claims more wall; its acceptance (user, option C, 2026-09-25) lives in
# the policy's Named exceptions table.
# Named exception: MHA-DT-010 boss wall (drawing-simplicity-policy.md, "Named exceptions").
BOSS_WALL_NOTE = (
    f"BOSS WALL {math.floor(BOSS_WALL_WORST * 100.0) / 100.0:.2f} MIN AT BORE."
)
# The drive-train fit-up may turn the band down past its printed band (the
# T120 feeler check, MHA-DT-000's crank step), and only when the band itself
# fails that check (a shoulder failure is the shoulder's to correct); the
# sheet permits it only as that check directs and states the floor, so the
# part stays conforming after the fit-up cut, and states the worst-case
# clearances to T120 that the check is there for.  Codex P1 on #1154
# (review 3).  The note names the check, not its step number: a part never
# reads the step registry (Main's TbPB ruling 2; test_part_isolation).
# Named exception: MHA-DT-010 turned band (drawing-simplicity-policy.md, "Named exceptions").
TURNED_BAND_FITUP_NOTE = "\n".join(
    (
        "TURNED BAND MAY BE TURNED DOWN PER MHA-DT-000 T120 CHECK, "
        f"Ø{TURNED_DIA_FITUP_MIN:.{TURNED_DIA_PLACES}f} MIN.",
        f"WORST-CASE CLEARANCE TO MHA-DT-003 T120: BAND {T120_TURNED_BAND_RADIAL_WORST:.2f}, "
        f"SHOULDER {T120_SHOULDER_AIR_WORST:.2f}.",
    )
)
DRAWING_NOTES = "\n".join((TOOTH_EDGE_NOTE, BOSS_WALL_NOTE, TURNED_BAND_FITUP_NOTE))
# The MHA-DT-000 crank step's T120 check (user, 2026-09-30, #1154), printed by
# draw_dt_drive_train_assembly: the pinion on its seat feeler, MHA-DT-010 and T120
# pushed toward each other (taking up every running play), turned by hand and
# read all round before the step's free-running revolution (it may rub until
# the check closes: Codex P2 on #1154, review 3).  Each cut answers its own
# reading only (build_dt_drive_train_assembly.t120_fitup_cuts).  Either fit-up
# limit passes the feeler at every corner (build_dt_drive_train_assembly asserts
# it), so the check always closes.  Its last line is short: the step carries
# on after it on the same line.
T120_FITUP_PUSHED = (PINION_NUMBER, "T120")
# Named exception: MHA-DT-010 turned band (drawing-simplicity-policy.md, "Named exceptions").
T120_FITUP_ASSEMBLY_CHECK = "\n".join(
    (
        f"   WORST-CASE T120 CLEARANCE: TURNED BAND {T120_TURNED_BAND_RADIAL_WORST:.2f}, "
        f"SHOULDER {T120_SHOULDER_AIR_WORST:.2f}. PUSH",
        f"   {T120_FITUP_PUSHED[0]} AND {T120_FITUP_PUSHED[1]} TOWARD EACH OTHER; "
        "TURN MHA-DT-007 SLOWLY BY HAND,",
        f"   READING A {T120_FITUP_FEELER_MM:.2f} FEELER ALL ROUND. BAND TO T120 TIPS: "
        "IF THE FEELER",
        "   STOPS, TURN BAND DOWN, "
        f"Ø{TURNED_DIA_FITUP_MIN:.{TURNED_DIA_PLACES}f} MIN. SHOULDER TO T120 SOUTH FACE: IF",
        "   THE FEELER STOPS, FACE SHOULDER BACK, "
        f"{SHOULDER_LENGTH_FITUP_MIN:.{SHOULDER_LENGTH_PLACES}f} MIN. RESET, RECHECK.",
    )
)
