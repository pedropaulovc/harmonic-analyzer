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

import drive_train_steps
import transgear_drive_collar_spec as collar
import transgear_stub_spec as stub

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
    "stud-fitted",
    "arm-plate-fitted",
    "arm-plate-screws-cut",
    "hanger-pivoted",
    # Disc cluster (R9-5, R9-8, R9-9).
    "disc-cluster-pressed",
    "disc-taps-transferred",
    # R9-47: tips cut inside the disc's rear face (transgear_disc_screw_spec).
    "disc-screws-cut",
    "oil-hole-drilled",
    "disc-cluster-hung",
    # Knob stack, front to rear (contract §1).
    "collar-pins-pressed",
    "knob-stack-fitted",
    # Latch (R9-15, R9-24).
    "latch-bracket-fitted",
    "hook-set-and-riveted",
    # Chain fit-up (contract §13.2 procedure (2)-(8)).
    "fitup-pose-set",
    # R9-47: the stud's arm seat faced to the F-to-disc window in that pose
    # (transgear_stub_spec.STUD_FIT_WINDOW).
    "stud-faced-to-fit",
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
# band is held at the solder joint (Main, 2026-10-01).
RACK_CREST_DROP = 2.0
RACK_CREST_TOL = 0.05
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
# collar's rearmost stop is the 12T's front face F, so the worst air is the
# stud fit window's minimum (R9-47, "stud-faced-to-fit").
COLLAR_DISC_AIR_MIN = stub.STUD_FIT_WINDOW[0]

# The printed forms of those bands: a drawing script only places them.
OFFSET_ACCEPT_TEXT = f"{collar.FIT_UP_OFFSET_TARGET:.2f} \u00b1{OFFSET_ACCEPT_TOL:.2f}"
COLLAR_DISC_AIR_TEXT = f"{COLLAR_DISC_AIR_MIN:.2f} MIN"
RACK_CREST_TEXT = f"{RACK_CREST_DROP:.2f} \u00b1{RACK_CREST_TOL:.2f}"
# The collar's seat limit (transgear_drive_collar_spec.SEAT_MAX_FROM_F).
T24_SEAT_MAX_TEXT = f"{collar.SEAT_MAX_FROM_F:.2f} MAX"
# The collar's rear face never passes the 12T's front face (the MHA-177
# fit-up note's "COLLAR REAR FACE TO 12T FRONT FACE 0 MIN").
COLLAR_GAP_MIN_TEXT = "0 MIN"
