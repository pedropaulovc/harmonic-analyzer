r"""Pure-data contract for the MHA-DT-VN-59 axial arm-to-hub seam pin.

The approved extraction feature is M2x0.4 THRU in the unchanged Ø4 x 4 pin.
M2.5 would require 5 mm at 2D and cannot fit this envelope. The through tap
avoids a blind tap's lead and drill-bottom allowance; its nominal full length
is the pin's length, exactly 2D. It only extracts the short, light-drive pin.

The drawing looks onto the extraction entry at local Z=0. Its native Hole
Wizard callout must name the thread, not just the drill at the opposite exit.
Only the single redundant automatic tapped-hole label is removed.
"""

from __future__ import annotations

from _hole_spec import HoleSpec
from dt_crank_hub_geometry import AXIAL_PIN_DIA as PIN_DIA
from dt_crank_hub_geometry import AXIAL_PIN_LENGTH as PIN_LEN

# Pull thread (rule 16): the pin seats in a BLIND seam half-hole with no room
# for a knockout. The coordinator's corrected M2 through-thread choice retains
# the seam, flush outer end and half-arm-thickness envelope. An extraction
# screw enters at that outer end; the through hole also vents the blind seat.
# Free-machining ISO 2338 unhardened dowel stock.
PULL_THREAD = "M2x0.4"
PULL_THREAD_MAJOR = 2.0
PULL_THREAD_TAP_DRILL = 1.6
PULL_THREAD_LEN = PIN_LEN  # tapped through
PULL_THREAD_HOLE = HoleSpec("tapped_metric", PULL_THREAD, end="through_all")
PULL_THREAD_MIN_ENGAGEMENT_DIAMETERS = 2.0
# These are distinct nominal walls: the native model cuts the tap drill, but
# the finished thread removes material out to its larger major diameter.
PULL_THREAD_TAP_DRILL_WALL = (PIN_DIA - PULL_THREAD_TAP_DRILL) / 2.0
PULL_THREAD_MAJOR_WALL = (PIN_DIA - PULL_THREAD_MAJOR) / 2.0
if PULL_THREAD_LEN < PULL_THREAD_MIN_ENGAGEMENT_DIAMETERS * PULL_THREAD_MAJOR:
    raise AssertionError("MHA-VN-029 pull thread needs at least 2D of full thread")
if PULL_THREAD_TAP_DRILL_WALL < 1.2:
    raise AssertionError("MHA-VN-029 tap drill must leave a 1.2 mm nominal wall")
if PULL_THREAD_MAJOR_WALL < 1.0:
    raise AssertionError("MHA-VN-029 thread major must leave a 1.0 mm nominal wall")
if not PULL_THREAD_TAP_DRILL < PULL_THREAD_MAJOR:
    raise AssertionError("MHA-VN-029 tap drill must sit inside the thread major")


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 1, "PinLen": 1},
}
# The diameter is the as-supplied m6 dowel, so it prints as a reference: its
# one place must not read as a .X band to machine to.
REFERENCE_DIMENSIONS = frozenset({"PinDia"})
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked MHA-DT-VN-59 dimension needs authored places")

DRAWING_TITLE = "Crank Hub Axial Pin Manufacturing Drawing"
DRAWING_SUMMARY = {
    0: DRAWING_TITLE,
    1: "Harmonic Analyzer hobby-machinist book drawing",
    2: "Harmonic Analyzer Project",
    3: "crank hub seam pin; axial key; straight gauge; steel",
    4: "Generated from the project-owned ASME B drawing standard",
}
REDUNDANT_NOTE_SUBSTRINGS = ("Tapped Hole",)

DRAWING_NOTES = "\n".join(
    (
        "m6 DOWEL STOCK AS SUPPLIED, ISO 2338 UNHARDENED.",
        "THREAD IS FOR EXTRACTION ONLY.",
    )
)
