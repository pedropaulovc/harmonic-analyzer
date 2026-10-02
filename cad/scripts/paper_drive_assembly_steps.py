"""The MHA-A06 paper-drive (transgear) assembly sequence, numbered in one place.

The drive_train_steps pattern (MHA-A03): a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer that
cites a step by key follows. The sheet prints the step text
(draw_paper_drive_assembly); this module holds the order and the few fit-up
values no part spec owns, because they belong to the assembly procedure, not
to a part. The collar setting, core drill and stud cut are the MHA-177
collar's (its sheet prints the same fit-up, R9-30). Pure data: no
SolidWorks, no config reads.
"""

from __future__ import annotations

import math

import numpy as np

import drive_train_steps
import latch_hook_bracket_spec as hook_bracket
import transgear_drive_collar_spec as collar
import transgear_cluster_fit as cluster_fit
import transgear_feed_pinion_spec as feed_pinion

DRAWING_NUMBER = "MHA-A06"

# The chain fit-up starts from the crank side complete per its own fit-up
# (CONTRACT-paper-drive.md §13.2 procedure (1)): the 16T set on its feeler and
# the seat washer faced (MHA-A03 "crank-mesh-checked"), then the T12 chain
# wheel on the crankshaft (MHA-A03 "paper-drive-wheel"). Cited by key so the
# pointer follows any renumbering of MHA-A03; both print on its cone-and-crank
# sequence sheet (draw_drive_train_assembly.SEQUENCE_SHEET).
CRANK_SIDE_KEYS = ("crank-mesh-checked", "paper-drive-wheel")
CRANK_SIDE_SHEET = 6
CRANK_SIDE_REF = (
    f"{drive_train_steps.DRAWING_NUMBER} SHEET {CRANK_SIDE_SHEET}, STEPS "
    + " AND ".join(str(drive_train_steps.step_number(key)) for key in CRANK_SIDE_KEYS)
)

SEQUENCE: tuple[str, ...] = (
    # Platen and support, on the exploded sheet: the bar on the columns at its
    # height, the platen built up on the bench, then hung with its locks.
    "bar-clamped",
    "rack-soldered",
    "guides-screwed",
    "clips-fitted",
    "platen-hung",
    # Platen on the bar (R9-49: the locks set clear of the hanger; R9-47: the
    # seats faced to the platen's float, platen_guide_spec.LOCK_GAP_FIT).
    "guide-locks-set",
    "lock-seats-faced",
    # Hanger, on the bench, then hung (R9-6: the spacer is fitted as made).
    "latch-pin-pressed",
    # R9-68: the plain pin pressed into the arm's reamed hole, head on the
    # arm's rear face (transgear_pin_spec).
    "pin-pressed",
    "arm-plate-fitted",
    "arm-plate-screws-cut",
    "hanger-pivoted",
    # Disc cluster, on the bench (R9-68: the disc on the sleeve's seat
    # shoulder, the hub's D-bore on its D-flat; R9-8, R9-9). The hub is then
    # faced to stand inside transgear_cluster_fit.HUB_NOSE_WINDOW behind the
    # sleeve nose, so the front bushing bears on the steel nose and traps the
    # hub and disc against the shoulder.
    "disc-cluster-assembled",
    "hub-faced-to-nose",
    "disc-taps-transferred",
    # R9-47: tips cut inside the disc's rear face (transgear_disc_screw_spec).
    "disc-screws-cut",
    "oil-hole-drilled",
    # R9-68: on the pin between the two bushing blanks, the ring last.
    "disc-cluster-hung",
    # Knob stack, front to rear (contract §1).
    "collar-pins-pressed",
    "knob-stack-fitted",
    # Latch (R9-15, R9-24). The hanger is meshed in the rack and run over the
    # platen's travel first; the hook is then set to hold that mesh.
    "latch-bracket-fitted",
    "hanger-meshed",
    "hook-set-and-riveted",
    # Chain fit-up (contract §13.2 procedure (2)-(8)).
    "fitup-pose-set",
    # R9-68: in that pose, the MHA-181 front bushing faced to m (the F-to-disc
    # window, cluster forward), then the MHA-180 rear bushing faced to the
    # cluster's float (transgear_cluster_fit).
    "front-bushing-faced-to-fit",
    "rear-bushing-faced-to-fit",
    "collar-gap-measured",
    "collar-pinned",
    "stud-end-cut",
    "fitup-accepted",
    # The chain closed over both wheels and run (contract §13.2, ch. 23).
    "chain-closed",
    "chain-run-accepted",
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("paper_drive_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-A06 STEP 4``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"


# --- Values the procedure owns (CONTRACT-paper-drive.md §13.2) --------------
# The bar's top above the base deck: the builder's BAR_TOP_Y less the deck's
# BASE_DECK_Y. It sets only the chain's centre distance (0.83 per mm of bar
# height; the 68-pitch loop goes taut 4.80 over nominal), so the title
# block's .X band holds it (Main, 2026-10-01).
BAR_TOP_ABOVE_DECK = 266.934
# The rack's crests below the platen's bottom edge (the builder's PLATE_Y0
# less RACK_TIP_Y). The latched hanger cannot take up a rack set off this: the
# hook's set range (0.51 at the hook) spans only ±0.25 of rack height, so the
# band is held at the solder joint (Main, 2026-10-01). R9-62: 2.25, which puts
# the feed mesh at its 0.55 centre extension (contact ratio 1.25).
RACK_CREST_DROP = 2.25
RACK_CREST_TOL = 0.05
# R9-62a: the feed pinion's mesh in the rack, set before the hook is
# match-drilled: the platen's shake along the rack with the knob held, i.e. the
# backlash at the pitch line, 2 * e * tan(pressure angle) for a centre
# extension e over the standard centres. The band's ends are checked below
# against the form-cut 12T's interference (feed_mesh_penetration) and the 1.1
# contact-ratio rule at the printed smallest tip (feed_mesh_contact_ratio).
MESH_BACKLASH_RANGE = (0.28, 0.32)
MESH_CONTACT_RATIO_FLOOR = 1.1
# The rack's addendum and the pinion's flank, in the pinion's frame.
_PHI = math.radians(feed_pinion.PRESSURE_ANGLE_DEG)
_RACK_ADDENDUM = feed_pinion.MODULE_MM
_PITCH_R = feed_pinion.PITCH_DIA / 2.0
_BASE_R = _PITCH_R * math.cos(_PHI)
_BASE_PITCH = math.pi * feed_pinion.MODULE_MM * math.cos(_PHI)
_TOOTH_ANGLE = 2.0 * math.pi / feed_pinion.TEETH
_INTERFERENCE_TOL = 1e-5  # mm: the sweep's sampling floor


def mesh_extension(backlash: float) -> float:
    """The feed pinion's centre extension that gives ``backlash``."""
    return backlash / (2.0 * math.tan(_PHI))


def feed_mesh_contact_ratio(
    extension: float, outside_dia: float = feed_pinion.OUTSIDE_DIA
) -> float:
    """The 12T-on-rack contact ratio at centre ``extension``."""
    tip_r = outside_dia / 2.0
    approach = math.sqrt(tip_r**2 - _BASE_R**2) - _PITCH_R * math.sin(_PHI)
    recess = (_RACK_ADDENDUM - extension) / math.sin(_PHI)
    return (approach + recess) / _BASE_PITCH


def feed_mesh_penetration(extension: float, samples: int = 20001) -> float:
    """Deepest reach (mm, > 0 interferes) of the rack into the MHA-110 12T at
    centre ``extension``, the rack pushed to flank contact.  The 12T is form
    cut (R9-67): involute above the base circle, radial below it to the 1.25/P
    root (the model's flank).  The rack's tip corners are what reach the
    radial flank, so they are rolled through three pitches of mesh."""
    roll = np.linspace(-1.5, 1.5, samples) * _TOOTH_ANGLE / 2.0
    cos, sin = np.cos(roll), np.sin(roll)
    tip_r = feed_pinion.OUTSIDE_DIA / 2.0
    root_r = feed_pinion.ROOT_DIA / 2.0
    corner_half = math.pi * feed_pinion.MODULE_MM / 4.0 - _RACK_ADDENDUM * math.tan(
        _PHI
    )
    pitch = math.pi * feed_pinion.MODULE_MM
    worst = -math.inf
    for tooth in (-1, 0, 1):
        for side in (-1.0, 1.0):
            # Half the backlash, extension * tan(PA), takes the rack to contact.
            x = -_PITCH_R * roll + extension * math.tan(_PHI)
            x = x + tooth * pitch + side * corner_half
            y = _PITCH_R + extension - _RACK_ADDENDUM
            px, py = cos * x + sin * y, -sin * x + cos * y
            radius = np.hypot(px, py)
            pressure = np.arccos(_BASE_R / np.maximum(radius, _BASE_R))
            half = (
                _TOOTH_ANGLE / 4.0
                + math.tan(_PHI)
                - _PHI
                - (np.tan(pressure) - pressure)
            )
            off_centre = np.abs(
                np.remainder(np.arctan2(px, py), _TOOTH_ANGLE) - _TOOTH_ANGLE / 2.0
            )
            reach = np.where(
                (radius <= tip_r) & (radius >= root_r),
                (half - off_centre) * radius,
                -math.inf,
            )
            worst = max(worst, float(reach.max()))
    return worst


def _least_clear_extension() -> float:
    low, high = 0.0, _RACK_ADDENDUM
    if feed_mesh_penetration(high) > _INTERFERENCE_TOL:
        raise AssertionError("the rack reaches into the 12T at every mesh depth")
    for _ in range(30):
        mid = (low + high) / 2.0
        if feed_mesh_penetration(mid) > _INTERFERENCE_TOL:
            low = mid
        else:
            high = mid
    return high


# The mesh's working window in centre extension: the rack clear of the form
# cut flank from MESH_EXTENSION_MIN (0.521), the contact ratio at the printed
# smallest tip down to the 1.1 rule at MESH_EXTENSION_MAX (0.624).
MESH_EXTENSION_MIN = _least_clear_extension()
TIP_DIA_MIN = feed_pinion.OUTSIDE_DIA + feed_pinion.OUTSIDE_DIA_BAND[1]
MESH_EXTENSION_MAX = _RACK_ADDENDUM - (
    MESH_CONTACT_RATIO_FLOOR * _BASE_PITCH
    - math.sqrt((TIP_DIA_MIN / 2.0) ** 2 - _BASE_R**2)
    + _PITCH_R * math.sin(_PHI)
) * math.sin(_PHI)


def check_mesh_band(band: tuple[float, float]) -> None:
    """Raise unless both ends of a platen-shake ``band`` mesh: the rack clear
    of the 12T's flank at the tight end, the contact ratio at the printed
    smallest tip within the 1.1 rule at the loose end."""
    low, high = (mesh_extension(b) for b in band)
    if not MESH_EXTENSION_MIN <= low < high <= MESH_EXTENSION_MAX:
        raise ValueError(
            f"mesh band e {low:.3f}..{high:.3f} leaves the working window "
            f"{MESH_EXTENSION_MIN:.3f}..{MESH_EXTENSION_MAX:.3f}"
        )
    if feed_mesh_penetration(low) > _INTERFERENCE_TOL:
        raise ValueError(f"the rack reaches into the 12T at e {low:.3f}")
    if feed_mesh_contact_ratio(high, TIP_DIA_MIN) < MESH_CONTACT_RATIO_FLOOR:
        raise ValueError(f"contact ratio under the 1.1 rule at e {high:.3f}")


check_mesh_band(MESH_BACKLASH_RANGE)

# The collar is set to transgear_drive_collar_spec.FIT_UP_OFFSET_SET_TEXT and
# accepted within OFFSET_ACCEPT_TOL of the same target at the re-check
# (procedure (8): "-0.05 ±0.10" in machine z, forward is -z).
OFFSET_ACCEPT_TOL = 0.10
# Procedure (5): the clamp sleeve over the stud bears on the collar's pilot
# face while the core is drilled, tightened by the thumbnut. A shop fixture,
# not a released part.
CLAMP_SLEEVE_OD = 10.4
CLAMP_SLEEVE_ID = 6.5
# Procedure (8): collar to 120T disc face air, accepted at this minimum.  The
# collar's rearmost stop is the 12T's front face F, so the worst air is m's
# fitted minimum (R9-47, R9-68: "front-bushing-faced-to-fit").
COLLAR_DISC_AIR_MIN = cluster_fit.FIT_WINDOW[0]

# The printed forms of those bands: a drawing script only places them.
OFFSET_ACCEPT_TEXT = f"{collar.FIT_UP_OFFSET_TARGET:.2f} \u00b1{OFFSET_ACCEPT_TOL:.2f}"
COLLAR_DISC_AIR_TEXT = f"{COLLAR_DISC_AIR_MIN:.2f} MIN"
RACK_CREST_TEXT = f"{RACK_CREST_DROP:.2f} \u00b1{RACK_CREST_TOL:.2f}"
MESH_BACKLASH_TEXT = f"{MESH_BACKLASH_RANGE[0]:.2f} TO {MESH_BACKLASH_RANGE[1]:.2f}"
HOOK_SET_TEXT = f"\u00b1{hook_bracket.HOOK_SET_RANGE:.2f}"
# The collar's seat limit (transgear_drive_collar_spec.SEAT_MAX_FROM_F).
T24_SEAT_MAX_TEXT = f"{collar.SEAT_MAX_FROM_F:.2f} MAX"
# The collar's rear face never passes the 12T's front face (the MHA-177
# fit-up note's "COLLAR REAR FACE TO 12T FRONT FACE 0 MIN").
COLLAR_GAP_MIN_TEXT = "0 MIN"
