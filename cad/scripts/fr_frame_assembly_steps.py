"""The MHA-FR-00 frame fit-up sequence, numbered in one place.

The ch_channel_assembly_steps pattern: a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer
that cites a step by key follows. The sheet prints the step text
(draw_fr_frame_assembly.STEP_TEXT); this module holds only the order, so the
joint table (joint_retention) and other sheets cite a step without importing
the sheet. Pure data: no SolidWorks, no config reads.

Each step does one thing (drawing-guidelines.md rule 22): a check and its
remedy are their own steps, each check right after the action it checks.
The nameplate is spotted through onto the base and its seats tapped on the
mill before the columns go in. The columns are then fitted and match-marked
in the base, the top frame set to the controlling height, the columns
match-cut to the cap stack, the tube cross holes transfer-punched through
each casting's clearance hole and drilled on the mill, and the frame screwed
together before the support goes on.
"""

from __future__ import annotations

DRAWING_NUMBER = "MHA-FR-00"

COLUMNS_ROUGH_CUT_KEY = "columns-rough-cut"
LOWER_HOLES_MARKED_KEY = "lower-holes-marked"
LOWER_HOLES_DRILLED_KEY = "lower-holes-drilled"
LOWER_HOLES_CHECKED_KEY = "lower-holes-checked"
COLUMNS_RESEATED_KEY = "columns-reseated"
# The controlling setting: every top socket's cross-hole axis at the sheet-1
# height above the base underside, before the columns are cut and the upper
# tube holes transfer-punched.
TOP_AXIS_SET_KEY = "top-axis-set"
TOP_FRAME_CLAMPED_KEY = "top-frame-clamped"
COLUMNS_CUT_KEY = "columns-cut"
FRAME_RESEATED_KEY = "frame-reseated"
UPPER_HOLES_CHECKED_KEY = "upper-holes-checked"
CROSS_SCREWS_DRIVEN_KEY = "cross-screws-driven"
# MHA-DT-00 sets the north pivot bracket on the screwed-down support.
SUPPORT_SCREWED_KEY = "support-screwed"
NAMEPLATE_SET_KEY = "nameplate-set"
NAMEPLATE_SPOTTED_KEY = "nameplate-spotted"
NAMEPLATE_SEATS_TAPPED_KEY = "nameplate-seats-tapped"
NAMEPLATE_SCREWED_KEY = "nameplate-screwed"
# MHA-HA-00 tightens the set screw on the MHA-SM-01 post.
GOOSENECK_STARTED_KEY = "gooseneck-set-screw-started"

SEQUENCE: tuple[str, ...] = (
    # The nameplate on the bare base, its seats tapped on the mill before the
    # base stands under the frame (#2390).
    NAMEPLATE_SET_KEY,
    "nameplate-clamped",
    NAMEPLATE_SPOTTED_KEY,
    "nameplate-lifted",
    NAMEPLATE_SEATS_TAPPED_KEY,
    NAMEPLATE_SCREWED_KEY,
    "nameplate-flat-checked",
    "nameplate-heads-checked",
    # Columns fitted, marked and their lower cross holes transferred, then
    # checked with the columns back in their sockets, where a tube hole off
    # the casting's screw line shows (#2388).
    COLUMNS_ROUGH_CUT_KEY,
    "base-sockets-fitted",
    "base-match-marked",
    LOWER_HOLES_MARKED_KEY,
    "lower-columns-lifted",
    LOWER_HOLES_DRILLED_KEY,
    COLUMNS_RESEATED_KEY,
    LOWER_HOLES_CHECKED_KEY,
    "lower-holes-reworked",
    # The top frame on the columns, at the controlling height.
    "top-frame-lowered",
    "top-sockets-fitted",
    "top-match-marked",
    TOP_AXIS_SET_KEY,
    TOP_FRAME_CLAMPED_KEY,
    # Columns match-cut to the cap stack at that height.
    "columns-marked",
    "frame-lifted-for-cut",
    COLUMNS_CUT_KEY,
    "columns-chamfered",
    FRAME_RESEATED_KEY,
    "top-axis-reset",
    # The upper tube holes, transferred from the top frame and checked with
    # the frame reassembled.
    "upper-holes-marked",
    "frame-lifted-for-drill",
    "upper-holes-drilled",
    "frame-reassembled",
    UPPER_HOLES_CHECKED_KEY,
    "upper-holes-reworked",
    # The frame screwed together and capped.
    "cross-screws-measured",
    "cross-screws-replaced",
    CROSS_SCREWS_DRIVEN_KEY,
    "cross-screw-heads-checked",
    "cross-screw-taps-chased",
    "cap-recesses-checked",
    "caps-pushed-on",
    "caps-checked",
    "column-ends-checked",
    # The support on the deck.
    "support-seated",
    SUPPORT_SCREWED_KEY,
    "support-flat-checked",
    "support-heads-checked",
    # The loose set screw and the final checks.
    GOOSENECK_STARTED_KEY,
    "post-bore-checked",
    "columns-seated-checked",
    "match-marks-checked",
    "top-axis-checked",
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("fr_frame_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-FR-00 STEP 37``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"
