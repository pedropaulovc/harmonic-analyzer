r"""Pure-data contract for the MHA-DT-VN-59 axial arm-to-hub seam pin.

The extraction feature is #0-80 UNF THRU in the unchanged Ø4 x 4 pin.
The through tap avoids a blind tap's lead and drill-bottom allowance; its
nominal axial length is the pin's length, about 2.625 basic thread diameters,
not a worst-case full-profile engagement guarantee. It only extracts the
short, light-drive pin. Owner ruling PW-01 (2026-10-19) accepts this pin's
computed 1.238 mm nominal thread-major wall, printed as 1.24 NOM.
The basic thread major is not a bounded maximum finished internal major, so
the computed wall is not proof of a finished-thread minimum.
"""

from __future__ import annotations

from _hole_spec import HoleSpec
from dt_crank_hub_geometry import AXIAL_PIN_DIA as PIN_DIA
from dt_crank_hub_geometry import AXIAL_PIN_LENGTH as PIN_LEN

# Pull thread (rule 16): the pin seats in a BLIND seam half-hole with no room
# for a knockout. The unified through-thread choice retains the seam, flush
# outer end and half-arm-thickness envelope. An extraction
# screw enters at that outer end; the through hole also vents the blind seat.
# Free-machining ISO 2338 unhardened dowel stock.
PULL_THREAD_TPI = 80
PULL_THREAD = f"#0-{PULL_THREAD_TPI}"
PULL_THREAD_MAJOR_IN = 0.060
PULL_THREAD_TAP_DRILL_IN = 0.0465  # #56 drill
PULL_THREAD_MAJOR = PULL_THREAD_MAJOR_IN * 25.4
PULL_THREAD_TAP_DRILL = PULL_THREAD_TAP_DRILL_IN * 25.4
PULL_THREAD_LEN = PIN_LEN  # tapped through
# The shared wizard table's legacy #0-80 drill is 3/64; this pin uses #56.
# The builder and saved-source guards must prove this native override survived.
PULL_THREAD_HOLE = HoleSpec(
    "tapped",
    PULL_THREAD,
    end="through_all",
    overrides_mm={"ThruTapDrillDiameter": PULL_THREAD_TAP_DRILL},
)
# IWizardHoleFeatureData2.Type uses swWzdHoleTypes_e, not the generic
# initialization enum. These are straight-through taps, cosmetic/through-thread
# variants and their countersinks; blind taps, pipe taps and drills are absent.
PULL_THREAD_NATIVE_THROUGH_TAP_TYPES = (33, 34, 35, 36, 48, 49, 50, 51, 52, 53, 54, 55)
PULL_THREAD_NOMINAL_LENGTH_DIAMETERS = PULL_THREAD_LEN / PULL_THREAD_MAJOR
# These are distinct nominal walls: the native model cuts the tap drill, but
# the finished thread removes material out to its larger major diameter.
# No maximum finished internal major is specified; do not infer a minimum
# wall from the basic thread major or invent a separate dowel fit band here.
PULL_THREAD_TAP_DRILL_WALL = (PIN_DIA - PULL_THREAD_TAP_DRILL) / 2.0
PULL_THREAD_MAJOR_WALL = (PIN_DIA - PULL_THREAD_MAJOR) / 2.0
PULL_THREAD_WALL_CALLOUT = f"THREAD-MAJOR WALL {PULL_THREAD_MAJOR_WALL:.2f} NOM"
if PULL_THREAD_NOMINAL_LENGTH_DIAMETERS < 2.0:
    raise AssertionError("MHA-VN-029 pull thread needs at least 2D nominal length")
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

DRAWING_NOTES = "\n".join(
    (
        "m6 DOWEL STOCK AS SUPPLIED, ISO 2338 UNHARDENED.",
        "THREAD IS FOR EXTRACTION ONLY.",
    )
)
