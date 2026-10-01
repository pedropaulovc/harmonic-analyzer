r"""MHA-078 transgear-knob-shaft: the steel knob shaft with its integral 12T.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  ``build_transgear_knob_shaft`` marks and tolerances exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model and
``draw_transgear_knob_shaft`` keeps exactly the same names.

Contract §1.1 (round 10): one turned steel shaft, front to rear --

* a 1/4-20 stud end, die-cut on a Ø6.22 blank inside the 2A major limits
  (R9-54), full thread from the tip to ``PLAIN_CORE`` in front of F, its
  tip chamfered 45 degrees to the thread's basic minor; the die runs out
  into a Ø4.0 thread relief between ``PLAIN_CORE`` and ``CORE_LENGTH``
  (R9-53).  The thumbnut (MHA-126) runs on it and clamps the T24 on the
  drive collar's front face; the stud end is cut to fit at rearward collar
  settings (§13.2) and is modelled uncut at the nominal setting;
* a plain Ø6.35 core from F to ``CORE_LENGTH``, the sliding seat of the
  brass drive collar (MHA-177), which is set on it at assembly; the Ø1.6
  hole for the MHA-154 spring pin is drilled through the core AT ASSEMBLY
  along the collar's rear slot and is not on this sheet (R9-6);
* the integral 12T DP38 pinion, meshing the 120T disc (MHA-070).  Its front
  face F is the datum of the tip, plain-core and cutter stations and the
  collar's rearward stop.  The form cutter cuts full depth from F to
  ``FULL_DEPTH`` and its arc then runs out (R9-21): partial-depth gaps over
  the rest of the face and twelve run-out slots in the front of the journal,
  under the loose thrust ring (MHA-156), which bears on the rear tooth ends;
* the Ø8.5 journal, running straight in the arm plate's bore, between that
  ring and the cup (MHA-157) clamped to the rear end face by the retaining
  screw (MHA-158) in the rear #8-32 tap.

Part frame: the axis is local +Z through the origin (``Axis1``); +Z is
machine +Z (rearward), so the assembly places the part without rotation.  The
origin is F, the 12T's front face (machine z -148.1 at the stack pose, R9-17):
the teeth run z = 0..FACE_WIDTH, the journal FACE_WIDTH..REAR_END_Z, the
plain core -CORE_LENGTH..0, the relief -PLAIN_CORE..-CORE_LENGTH and the
thread -TIP_STATION..-PLAIN_CORE.  The
seed tooth gap and the seed run-out slot are centred on ``GAP_AZIMUTH_DEG``
(from local +X, CCW about +Z).

Named datums: ``Axis1`` (the shaft axis); ``Front Plane`` (F); planes
``PinionRear`` (the 12T's rear face, the thrust ring's seat), ``RearFace``
(the rear end face, the cup's seat), ``ThreadEnd`` (full thread ends) and
``StudTip`` (the tip face).
"""

from __future__ import annotations

import math

from _gtol_spec import CylinderFace
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import printed_band_mm, printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from transgear_arm_plate_geometry import HUB_TO_BOSS as PLATE_HUB_TO_BOSS
from transgear_knob_cup_spec import ENGAGEMENT_OWN_WORST, REACH_MAX
from transgear_knob_retaining_screw_spec import SHANK_DIA
from transgear_knob_retaining_screw_spec import THREAD as SCREW_THREAD
from transgear_knob_thrust_ring_spec import LENGTH as RING_LENGTH
from transgear_knob_thrust_ring_spec import LENGTH_TOL as RING_LENGTH_TOL

MM_PER_IN = 25.4
WALL_FLOOR = 2.0
ENGAGEMENT_FLOOR_D = 1.5

# --- The integral 12T DP38 pinion (meshes the 120T disc MHA-070) -------------
TEETH = 12
DIAMETRAL_PITCH = 38.0  # the 120T disc's pitch
PRESSURE_ANGLE_DEG = 14.5
# R9-17: F moved 0.1 rearward to -148.1; the rear tooth ends (-142.2, the
# thrust ring's seat) stay put.
FACE_WIDTH = 5.9
FACE_WIDTH_PLACES = 3  # 12T rear face -> F: the chain-plane stack (contract §13)
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN  # 8.021
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN  # 9.358
OUTSIDE_DIA_PLACES = 2
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
# The root-relieved gap floor _gear.build_fixed_gear cuts: the standard
# 1.157/P dedendum below the pitch circle.
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN  # 6.474
# The seed gap _gear.cut_tooth_gap cuts is centred half a pitch CCW of local
# +X (tooth 0 is centred on +X); the pattern repeats it every 30 degrees.
GAP_AZIMUTH_DEG = 180.0 / TEETH

# --- Stud end: 1/4-20, full thread from the tip to the thread relief --------
THREAD = "1/4-20"
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]  # 6.35 basic
THREADS_PER_IN = 20
THREAD_PITCH = MM_PER_IN / THREADS_PER_IN
# ASME B1.1 basic minor diameter (D1 = D - 1.082532 P): the tip chamfer runs
# 45 degrees down to it, so the first full thread starts at the chamfer.
THREAD_BASIC_MINOR = THREAD_MAJOR - 1.082532 * THREAD_PITCH  # 4.975
# 1/4-20 UNC-2A limits, ASME B1.1 as tabled by Engineers Edge (read
# 2026-10-01, https://www.engineersedge.com/screw_threads_chart.htm): major
# 0.2408..0.2489 in, pitch diameter min 0.2127 in.
THREAD_MAJOR_2A_IN = (0.2408, 0.2489)
THREAD_MAJOR_2A = tuple(v * MM_PER_IN for v in THREAD_MAJOR_2A_IN)  # 6.116..6.322
THREAD_PD_2A_MIN_IN = 0.2127
# The deepest root a die cuts.  ASSUMPTION, as in crank_handle_pivot_screw_spec:
# a root a full basic half-depth (0.649519 P) under the smallest 2A pitch
# diameter, 4.578, below the table's 2A minor maximum 0.1876 in (4.765).
THREAD_ROOT_2A_MIN = (THREAD_PD_2A_MIN_IN - 0.649519 / THREADS_PER_IN) * MM_PER_IN
# R9-54: the die cuts on a blank turned inside the 2A major limits, a step
# under the Ø6.35 core.  The model owns the ±0.10 band (rule 2).
THREAD_BLANK_DIA = 6.22
THREAD_BLANK_DIA_BAND = (0.10, -0.10)  # (upper, lower)
THREAD_BLANK_DIA_PLACES = 2
THREAD_BLANK_LIMITS = (
    THREAD_BLANK_DIA + min(THREAD_BLANK_DIA_BAND),
    THREAD_BLANK_DIA + max(THREAD_BLANK_DIA_BAND),
)  # 6.12..6.32
if not (
    THREAD_MAJOR_2A[0] <= THREAD_BLANK_LIMITS[0]
    and THREAD_BLANK_LIMITS[1] <= THREAD_MAJOR_2A[1]
):
    raise AssertionError(
        f"MHA-078 thread blank / 1/4-20 UNC-2A major: the blank "
        f"{THREAD_BLANK_LIMITS[0]:.3f}..{THREAD_BLANK_LIMITS[1]:.3f} leaves the "
        f"2A major {THREAD_MAJOR_2A[0]:.3f}..{THREAD_MAJOR_2A[1]:.3f}"
    )
TIP_CHAMFER = (THREAD_BLANK_DIA - THREAD_BASIC_MINOR) / 2.0  # 0.622, 45 degrees
TIP_CHAMFER_PLACES = 2
# The title block states the UN thread class, so the callout names no class.
THREAD_CALLOUT = f"{THREAD} UNC"
CHAMFER_CALLOUT = "X 45 DEG"
# The tip prints as its station from F (.XX, R9-17), not as a thread length.
TIP_STATION = 23.9
TIP_STATION_PLACES = 2

# --- Plain core: the drive collar's sliding seat -----------------------------
CORE_DIA = THREAD_MAJOR  # 6.35, the reamed collar's size
CORE_DIA_BAND = (-0.005, -0.015)  # (upper, lower): sliding under the reamed collar
CORE_DIA_PLACES = 3
# The core ends CORE_LENGTH in front of F (.XXX): the cross-pin hole, drilled
# at assembly, must stay in the full core at the furthest collar setting
# (MHA-177 asserts it).
CORE_LENGTH = 5.25
CORE_LENGTH_PLACES = 3

# --- Thread relief: the die's run-out lies in it (R9-53) -----------------------
# Full thread ends PLAIN_CORE in front of F, on the relief's front shoulder
# (.XXX).  The die runs rearward until its leading face meets the core's
# step, so it cuts full thread to the step plus its chamfered lead; the
# narrowest printed relief holds a lead of DIE_RUNOUT_PITCHES (a die run
# with its chamfer leading [INFERENCE: 1.5 P is the shorter of the common
# die leads]).  The relief's floor stands under the deepest die-cut root,
# so the lead's incomplete threads lie in air, and the thumbnut at the
# collar's rearward stop runs only on full thread or over the relief.
PLAIN_CORE = 7.5
PLAIN_CORE_PLACES = 3
THREAD_LENGTH_REF = TIP_STATION - PLAIN_CORE  # 16.4 REF
DIE_RUNOUT_PITCHES = 1.5
DIE_RUNOUT_MAX = DIE_RUNOUT_PITCHES * THREAD_PITCH  # 1.905
RELIEF_DIA = 4.0
RELIEF_DIA_PLACES = 2
_CORE_LENGTH_TOL = printed_band_mm(CORE_LENGTH_PLACES)
_PLAIN_CORE_TOL = printed_band_mm(PLAIN_CORE_PLACES)
RELIEF_DIA_MAX = RELIEF_DIA + printed_band_mm(RELIEF_DIA_PLACES)  # 4.51
RELIEF_DIA_MIN = RELIEF_DIA - printed_band_mm(RELIEF_DIA_PLACES)  # 3.49
RELIEF_WIDTH_MIN = (PLAIN_CORE - _PLAIN_CORE_TOL) - (
    CORE_LENGTH + _CORE_LENGTH_TOL
)  # 7.37 - 5.38 = 1.99
if RELIEF_WIDTH_MIN < DIE_RUNOUT_MAX - 1e-9:
    raise AssertionError(
        f"MHA-078 thread relief / die run-out: the narrowest relief "
        f"{RELIEF_WIDTH_MIN:.3f} is under the {DIE_RUNOUT_MAX:.3f} "
        f"({DIE_RUNOUT_PITCHES}P) a die's lead runs out over"
    )
if RELIEF_DIA_MAX > THREAD_ROOT_2A_MIN + 1e-9:
    raise AssertionError(
        f"MHA-078 thread relief / die root: the largest relief "
        f"Ø{RELIEF_DIA_MAX:.3f} stands above the deepest die-cut root "
        f"Ø{THREAD_ROOT_2A_MIN:.3f}"
    )
# The relief carries only the thumbnut's clamp (the drive enters the core
# behind it, at the cross pin): its smallest section against the thread's
# tensile-stress area, ASME B1.1 As = 0.7854 (D - 0.9743 / n)^2 (20.5 mm^2).
THREAD_STRESS_AREA = math.pi / 4.0 * (THREAD_MAJOR - 0.9743 * THREAD_PITCH) ** 2
RELIEF_AREA_MIN = math.pi / 4.0 * RELIEF_DIA_MIN**2  # 9.57
RELIEF_AREA_RATIO_MIN = RELIEF_AREA_MIN / THREAD_STRESS_AREA  # 0.47

# --- Journal: runs in the arm plate's Ø8.5 bore (K5, no bushing) -------------
JOURNAL_DIA = 8.5
JOURNAL_DIA_BAND = (-0.013, -0.035)  # (upper, lower): the running fit
JOURNAL_DIA_PLACES = 3
# 12T rear face to the rear end face (R9-25): the thrust ring + the plate's
# hub-to-boss + the 0.2 end float, the cup's front face running that far
# behind the rear boss at the stack pose.  Its own ±0.05 holds the knob float.
END_FLOAT = 0.2
JOURNAL_LENGTH = RING_LENGTH + PLATE_HUB_TO_BOSS + END_FLOAT  # 34.4375
JOURNAL_LENGTH_TOL = 0.05
JOURNAL_LENGTH_PLACES = 3
if abs(JOURNAL_LENGTH - 34.4375) > 1e-9:
    raise AssertionError(
        f"journal {JOURNAL_LENGTH:.4f} is off the contract's 34.4375 "
        "(ring 5.2 + hub-to-boss 29.0375 + 0.2 float, R9-25)"
    )

# --- Local stations along +Z, from F ------------------------------------------
TIP_Z = -TIP_STATION
CORE_END_Z = -CORE_LENGTH
THREAD_END_Z = -PLAIN_CORE
PINION_REAR_Z = FACE_WIDTH
REAR_END_Z = FACE_WIDTH + JOURNAL_LENGTH
OVERALL_LENGTH = REAR_END_Z - TIP_Z  # 64.24 REF

if not ROOT_DIA > CORE_DIA:
    raise AssertionError("the 12T's gap floors cut into the Ø6.35 core")
if not CORE_DIA < JOURNAL_DIA < OUTSIDE_DIA:
    raise AssertionError(
        "the journal must step up from the core and stay under the 12T"
    )

# --- 12T form-cutter run-out (R9-21) ------------------------------------------
# The 12T is cut with a form cutter on a dividing head: full depth from F to
# FULL_DEPTH, then the cutter's arc runs out behind that station, leaving
# partial-depth gaps over the rest of the face and slotting the Ø8.5 journal
# (proud of the gap floor) under the loose thrust ring.  The sheet prints the
# full-depth length as a window from F, the run-out's end as a limit and the
# largest cutter that keeps a window.
FULL_DEPTH = 4.65
FULL_DEPTH_PLACES = 3
CUTTER_RUNOUT_MAX = 10.5  # from F, a limit
CUTTER_DIA_MAX_IN = 1.25
CUTTER_DIA_MAX = CUTTER_DIA_MAX_IN * MM_PER_IN  # 31.75
_FULL_DEPTH_BAND = printed_band_mm(FULL_DEPTH_PLACES)
FULL_DEPTH_MIN = FULL_DEPTH - _FULL_DEPTH_BAND  # 4.52
FULL_DEPTH_MAX = FULL_DEPTH + _FULL_DEPTH_BAND  # 4.78
# Two sheet lines, each inside the 70-character note limit.
F_NOTE = (
    f"F = 12T FRONT FACE. FULL DEPTH FROM F TO {FULL_DEPTH:.3f} "
    f"\u00b1{_FULL_DEPTH_BAND:.2f}."
)
CUTTER_NOTE = (
    f"CUTTER RUN-OUT {CUTTER_RUNOUT_MAX:.2f} MAX FROM F; "
    f"CUTTER \u00d8{CUTTER_DIA_MAX_IN:.2f} in MAX."
)


def cutter_runout(cutter_dia: float, rise: float) -> float:
    """Axial length behind the full-depth station over which a form cutter of
    ``cutter_dia`` still cuts a surface ``rise`` above the gap floor: the
    chord half-length of its circle at that height, √(Rc² − (Rc − rise)²)."""
    radius = cutter_dia / 2.0
    if not 0.0 <= rise <= radius:
        raise ValueError(f"rise {rise} is off a Ø{cutter_dia} cutter")
    return (radius**2 - (radius - rise) ** 2) ** 0.5


# Window (i): full depth covers the disc's worst-corner rear face.  That face
# is the assembly stack's (contract §13.2): nominal 3.70 from F + arm 0.0254
# + plate 0.13 + ring 0.05 + 12T face 0.13 + stud 0.05 + disc seat 0.05 +
# the knob float forward 0.35.
DISC_REAR_FROM_F_WORST = 4.4854
# Window (ii): the run-out ends in front of the plate hub's running bore.  At
# the stack pose (12T rear tooth ends -> ring -> hub) the hub face lies the
# face width plus the ring behind F, nearest at their short limits.
HUB_BORE_FROM_F_WORST = (FACE_WIDTH - printed_band_mm(FACE_WIDTH_PLACES)) + (
    RING_LENGTH - RING_LENGTH_TOL
)  # 10.92
# The longest slot: the journal at its largest radius over the gap floor.
_JOURNAL_R_MAX = (JOURNAL_DIA + max(JOURNAL_DIA_BAND)) / 2.0  # 4.2435
RUNOUT_RISE_WORST = _JOURNAL_R_MAX - ROOT_DIA / 2.0  # 1.0065
CUTTER_RUNOUT_END_WORST = FULL_DEPTH_MAX + cutter_runout(
    CUTTER_DIA_MAX, RUNOUT_RISE_WORST
)  # 10.343
if FULL_DEPTH_MIN < DISC_REAR_FROM_F_WORST - 1e-9:
    raise AssertionError(
        f"12T full depth may stop at F + {FULL_DEPTH_MIN:.3f}, in front of the "
        f"disc's worst rear face F + {DISC_REAR_FROM_F_WORST:.4f}"
    )
if CUTTER_RUNOUT_END_WORST > CUTTER_RUNOUT_MAX + 1e-9:
    raise AssertionError(
        f"a Ø{CUTTER_DIA_MAX:.2f} cutter's run-out reaches F + "
        f"{CUTTER_RUNOUT_END_WORST:.3f}, past the printed {CUTTER_RUNOUT_MAX:.2f}"
    )
if CUTTER_RUNOUT_MAX >= HUB_BORE_FROM_F_WORST:
    raise AssertionError(
        f"the printed run-out limit F + {CUTTER_RUNOUT_MAX:.2f} reaches the plate "
        f"hub bore (F + {HUB_BORE_FROM_F_WORST:.2f} worst)"
    )

# The model cuts at the nominal full depth with the largest cutter: its axis
# lies across the seed gap's centre line, CUTTER_AXIS_R from the shaft axis
# at z = FULL_DEPTH, and the slots end RUNOUT_SLOT_END_Z behind F.
CUTTER_AXIS_R = ROOT_DIA / 2.0 + CUTTER_DIA_MAX / 2.0  # 19.112
CUTTER_AXIS_Z = FULL_DEPTH
RUNOUT_SLOT_END_Z = FULL_DEPTH + cutter_runout(
    CUTTER_DIA_MAX, JOURNAL_DIA / 2.0 - ROOT_DIA / 2.0
)  # 10.23
if not PINION_REAR_Z < RUNOUT_SLOT_END_Z < HUB_BORE_FROM_F_WORST:
    raise AssertionError("the modelled run-out slots leave the thrust ring's span")


def gap_chord(radius: float) -> float:
    """Chordal width of a standard 12T tooth gap at ``radius`` (mm): the gap
    angle is π/N − 2 inv φ at the pitch circle plus 2 inv φ at ``radius``
    (radial flanks below the base circle)."""
    phi = math.radians(PRESSURE_ANGLE_DEG)
    base_r = PITCH_DIA / 2.0 * math.cos(phi)
    inv_r = 0.0
    if radius > base_r:
        phi_r = math.acos(base_r / radius)
        inv_r = math.tan(phi_r) - phi_r
    angle = math.pi / TEETH - 2.0 * (math.tan(phi) - phi) + 2.0 * inv_r
    return 2.0 * radius * math.sin(angle / 2.0)


# The model's slots are flat-walled at the gap's width where the cutter
# leaves the journal surface (a simplification: the form cutter's walls
# follow the gap's involute, narrower below).  Hidden under the thrust ring.
RUNOUT_SLOT_WIDTH = gap_chord(JOURNAL_DIA / 2.0)

# --- Rear tap: #8-32 blind, for the MHA-158 retaining screw ------------------
TAP_SIZE = SCREW_THREAD
TAP_MAJOR = THREAD_MAJOR_MM[TAP_SIZE]
TAP_DRILL_DIA = TAP_DRILL_MM[TAP_SIZE]
TAP_PITCH = MM_PER_IN / 32.0
# Depths print at .X (policy rule 12, the cone-tip-block foot-tap precedent).
# The contract's nominal 9.2 full thread / 10.4 drill leaves the longest
# screw reach 0.18 inside the full thread at nominal, but at .X the full
# thread may stop 8.4 deep, and the screw would jam in the tap's lead: the
# depths are deepened so the printed worst case keeps TAP_TIP_MARGIN.
TAP_DEPTH_PLACES = 1
TAP_TIP_MARGIN = 0.25
TAP_FULL_THREAD = 10.1
# The drill runs 1.5 P past the deepest full thread at both printed limits,
# so a plug tap's lead never eats it.
TAP_DRILL_DEPTH = 12.9
TAP_SPEC = HoleSpec(
    "tapped",
    TAP_SIZE,
    end="blind",
    depth_mm=TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": TAP_FULL_THREAD},
)
# 90-degree entry countersink, one chamfer on the tap-drill edge.
TAP_CSK_DIA = 4.3
TAP_CSK_BAND = (0.10, 0.0)  # (upper, lower): drilled-hole class
TAP_CSK = (TAP_CSK_DIA - TAP_DRILL_DIA) / 2.0  # 45-degree leg
TAP_CSK_QUALIFIER = f"90\u00b0 CSK \u00d8{TAP_CSK_DIA:.1f} +{TAP_CSK_BAND[0]:.2f}/0"

_TAP_BAND = printed_band_mm(TAP_DEPTH_PLACES)
TAP_FULL_THREAD_MIN = TAP_FULL_THREAD - _TAP_BAND
TAP_TIP_CLEARANCE_WORST = TAP_FULL_THREAD_MIN - REACH_MAX
if TAP_TIP_CLEARANCE_WORST < TAP_TIP_MARGIN - 1e-9:
    raise AssertionError(
        f"MHA-158 can reach {REACH_MAX:.3f} into the tap, within "
        f"{TAP_TIP_MARGIN} of the shallowest printed full thread "
        f"{TAP_FULL_THREAD_MIN:.2f}"
    )
if (TAP_DRILL_DEPTH - _TAP_BAND) - (
    TAP_FULL_THREAD + _TAP_BAND
) < 1.5 * TAP_PITCH - 1e-9:
    raise AssertionError("the rear tap drill leaves no lead room past the full thread")

# The screw's side (MHA-157 floor, first-thread loss) comes from the cup; the
# shaft's own term is the thread its entry countersink removes, at the
# largest printed countersink.
TAP_CSK_LOSS_WORST = (TAP_CSK_DIA + max(TAP_CSK_BAND) - TAP_MAJOR) / 2.0
ENGAGEMENT_WORST = ENGAGEMENT_OWN_WORST - TAP_CSK_LOSS_WORST
if ENGAGEMENT_WORST < ENGAGEMENT_FLOOR_D * SHANK_DIA - 1e-9:
    raise AssertionError(
        f"MHA-158 engages {ENGAGEMENT_WORST:.3f} "
        f"({ENGAGEMENT_WORST / SHANK_DIA:.2f} D) in the rear tap, under "
        f"{ENGAGEMENT_FLOOR_D} D"
    )

# --- Walls at the printed worst case (contract §8) ---------------------------
_JOURNAL_MIN = JOURNAL_DIA + min(JOURNAL_DIA_BAND)
# Journal over the tap's thread major, and over the countersink at the mouth.
JOURNAL_TAP_WALL = (JOURNAL_DIA - TAP_MAJOR) / 2.0  # 2.167
JOURNAL_TAP_WALL_WORST = (_JOURNAL_MIN - TAP_MAJOR) / 2.0
JOURNAL_CSK_WALL_WORST = (_JOURNAL_MIN - (TAP_CSK_DIA + max(TAP_CSK_BAND))) / 2.0
# Solid from the tap-drill point to the 12T's rear face (not a load wall).
TAP_TO_PINION_WORST = (
    JOURNAL_LENGTH - JOURNAL_LENGTH_TOL - (TAP_DRILL_DEPTH + _TAP_BAND)
)
for _name, _wall in (
    ("journal over the rear tap", JOURNAL_TAP_WALL_WORST),
    ("journal over the tap countersink", JOURNAL_CSK_WALL_WORST),
    ("tap drill to the 12T rear face", TAP_TO_PINION_WORST),
):
    if _wall < WALL_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-078 {_name} {_wall:.3f} at the printed worst case is under "
            f"the {WALL_FLOOR} floor"
        )

# The tip chamfer at its printed worst never grows past the one pitch the
# thumbnut's engagement budget already takes off for it (contract §7).
_CHAMFER_LOWER, _CHAMFER_UPPER = printed_deviations(TIP_CHAMFER, TIP_CHAMFER_PLACES)
TIP_CHAMFER_MAX = TIP_CHAMFER + _CHAMFER_UPPER
if TIP_CHAMFER_MAX > THREAD_PITCH + 1e-9:
    raise AssertionError(
        f"the stud tip chamfer can reach {TIP_CHAMFER_MAX:.2f}, past the one "
        f"pitch ({THREAD_PITCH:.2f}) the thumbnut engagement allows for it"
    )


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


DISC_NUMBER = "MHA-070"
DISC_TEETH = 120
# Rule 6's gear-data block: the tooth system the view dimensions cannot state.
# Cutter inputs and derived diameters are REF; the outside diameter and face
# width are native dimensions on the views.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.2f}"),
        ("TOOTH FORM", "SPUR INVOLUTE, FULL DEPTH"),
        ("MATES WITH", f"DISC {DISC_NUMBER}, {DISC_TEETH}T"),
    ]
)

# The title block's 0.25 edge break is a sixth of this fine tooth's whole
# depth, so the sheet carries the one part-specific exception it needs.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
DRAWING_NOTES = "\n".join((TOOTH_EDGE_NOTE, F_NOTE, CUTTER_NOTE))

# Two running surfaces: the journal in the plate bore and the core under the
# sliding collar.  Nothing else runs; the rest is the title block's process.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("journal", MACHINED_UM, CylinderFace(JOURNAL_DIA)),
    SurfaceFinishControl(
        "core",
        MACHINED_UM,
        CylinderFace(CORE_DIA, contains_z_mm=CORE_END_Z / 2.0),
    ),
)

# --- Marked-dimension contract ------------------------------------------------
# ``StudProfile`` is the Right-plane revolve in front of F (the core, the
# thread relief, the thread blank and the tip chamfer); it also carries one
# construction-only witness, the tooth-tip blank across the face (OutsideDia,
# rule 2's reference-sketch allowance), so every turned size imports natively
# beside its axial extent.  ``JournalProfile`` is the revolve behind the
# teeth.  ``GearBlank`` owns the face width.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "StudProfile": {
        "CoreDia",
        "CoreLength",
        "ReliefDia",
        "PlainCore",
        "ThreadBlankDia",
        "TipStation",
        "TipChamfer",
        "OutsideDia",
    },
    "JournalProfile": {"JournalDia", "JournalLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "StudProfile": {
        "CoreDia": CORE_DIA_PLACES,
        "CoreLength": CORE_LENGTH_PLACES,
        "ReliefDia": RELIEF_DIA_PLACES,
        "PlainCore": PLAIN_CORE_PLACES,
        "ThreadBlankDia": THREAD_BLANK_DIA_PLACES,
        "TipStation": TIP_STATION_PLACES,
        "TipChamfer": TIP_CHAMFER_PLACES,
        "OutsideDia": OUTSIDE_DIA_PLACES,
    },
    "JournalProfile": {
        "JournalDia": JOURNAL_DIA_PLACES,
        "JournalLength": JOURNAL_LENGTH_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(map(len, DRAWING_PRECISION.values())):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _names in DRAWING_PRECISION.items():
    if set(_names) != DRAWING_DIMENSIONS[_feature]:
        raise AssertionError(f"{_feature}: marked dimensions without places")

# The tap's callout prints its two depths at TAP_DEPTH_PLACES, the band the
# reach stack above reads, not the native two places.
TAP_DEPTH_PRECISION = {
    "hw-threaddepth": TAP_DEPTH_PLACES,
    "hw-tapdrldepth": TAP_DEPTH_PLACES,
}
