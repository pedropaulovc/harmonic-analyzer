r"""Pure-data contract for the rocker arm filing stand (MHA-CH-06-TL-12).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's S5 fitting-bench setup (prechips plan ch_rocker_arm S5) the
hacksaw parts the taper-and-land tabs, so the arm and the blank-end frame must
each stay pressed onto a support. Two end blocks carry the raw blank ends and
a pedestal carries the arm's lower hub face, so one clamp on the hub holds the
arm and the 2.5 strap is never clamped. The three pieces stand loose on the
fitting bench and are clamped to it; the outline overhangs them all round for
the saw and the file.

The hub is centred in the raw 5/16 in bar: S1 op 10 faces the upper hub face
to (raw + hub length) / 2 above the raw underside, and the lower hub face is
the hub length below it, (raw - hub length) / 2 above the raw underside. That
is the pedestal's step over the end blocks.

SolidWorks part frame: +Y up, origin on the bench top, the pieces laid out
side by side along +X for the sheet (LAYOUT_*, not their S5 stations; the
spacing is not a requirement). Every face requirement is a top face (+Y).
PRECHIPS_SOLIDS states the set at its S5 stations in the inventory's fixture
frame (fixtures.rocker-filing-stand: origin under the rocker's pivot axis,
+X along the blank, +Y as the rocker frame ``top``, +Z up, Z0 = end-block
tops = raw blank underside).
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
from _printed_tolerance import printed_band_mm

INCH = 25.4
# Prechips plan ch_rocker_arm [stock]: Online Metals pid 12035, 1018 CR
# 5/16 x 1-1/2 in flat, one 336 blank centred on the pivot axis.
RAW_THICKNESS = 5.0 / 16.0 * INCH  # 7.9375
RAW_LENGTH = 336.0

# The pedestal stands this far above the end blocks: the lower hub face over
# the raw underside, printed at two places (0.4405 rounds to 0.44; the half
# micrometre is far inside the step's acceptance).
STEP = round((RAW_THICKNESS - rocker.HUB_LENGTH) / 2.0, 2)
if abs(STEP - (RAW_THICKNESS - rocker.HUB_LENGTH) / 2.0) > 0.001:
    raise AssertionError("filing-stand step drifted from the centred hub's lower face")
# The lower hub face lands within the hub's own length band of its nominal
# (S4 faces it last), so a pedestal inside the same band either side springs
# the clamped arm no more than the hub tolerance already allows.
STEP_BAND = (rocker.HUB_LENGTH_BAND[0], -rocker.HUB_LENGTH_BAND[0])  # (upper, lower)
STEP_LIMITS = (round(STEP + STEP_BAND[1], 2), round(STEP + STEP_BAND[0], 2))
if not 0.0 < STEP_LIMITS[0] < STEP < STEP_LIMITS[1] < rocker.HUB_LENGTH:
    raise AssertionError("filing-stand step limits are not a band about the step")

# End blocks: one under each raw blank end, flush with it, clear of the arm
# outline, centred on the S5 blank-end clamp station (plan S5 clamps at
# X +-158, Y 6.65).
BLOCK_LENGTH = 20.0  # along the blank
BLOCK_WIDTH = 1.5 * INCH  # across the blank: the raw width
BLOCK_HEIGHT = 30.0  # lifts the work clear of the bench for the hacksaw
BLOCK_CENTRE_Y = 6.65
BLOCK_SOUTH_Y = round(BLOCK_CENTRE_Y - BLOCK_WIDTH / 2.0, 4)
BLOCK_OUTER_X = RAW_LENGTH / 2.0
BLOCK_INNER_X = BLOCK_OUTER_X - BLOCK_LENGTH
BLOCK_WEST_X = (-BLOCK_OUTER_X, BLOCK_INNER_X)  # left block, right block
_X = printed_band_mm(1)
if BLOCK_INNER_X - _X <= rocker.ROD_TIP_X:
    raise AssertionError("an end block reaches under the rocker arm outline")
if abs(BLOCK_INNER_X + BLOCK_LENGTH / 2.0 - 158.0) > 1e-9:
    raise AssertionError("end blocks left the S5 blank-end clamp station")

# Pedestal: a short steel round under the lower hub face, its top wholly
# inside that face at the largest printed diameter.
PEDESTAL_DIA = 9.5
PEDESTAL_LENGTH = round(BLOCK_HEIGHT + STEP, 2)
_XX = printed_band_mm(2)
if PEDESTAL_DIA + _XX >= rocker.HUB_DIA_MIN:
    raise AssertionError("filing-stand pedestal overhangs the rocker lower hub face")
if abs(PEDESTAL_LENGTH - BLOCK_HEIGHT - STEP) > 1e-9:
    raise AssertionError(
        "filing-stand pedestal length is not the block height plus the step"
    )

# Sheet arrangement only (the drawing's views, never a requirement): the
# pedestal's axis on the model Y axis (a revolved round, so the elevation
# carries its diameter, rule 11), the two blocks side by side west of it,
# all standing on the bench (Y0) and centred on Z0.
LAYOUT_BLOCK_WEST_X = (-75.0, -45.0)  # left block, right block
if -PEDESTAL_DIA / 2.0 <= LAYOUT_BLOCK_WEST_X[1] + BLOCK_LENGTH:
    raise AssertionError("filing-stand layout overlaps the pedestal and a block")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LeftBlockProfile": {"BlockLength", "BlockWidth"},
    "LeftBlock": {"BlockHeight"},
    "PedestalProfile": {"PedestalDia", "PedestalLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LeftBlockProfile": {"BlockLength": 1, "BlockWidth": 1},
    "LeftBlock": {"BlockHeight": 1},
    "PedestalProfile": {"PedestalDia": 2, "PedestalLength": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked filing-stand dimension needs authored places")

# drawing-guidelines.md rule 4 (tighten only for function, and name the mate)
# and rule 19 (absorb stacks at fit-up): the pedestal's length is a reference;
# what is held is its step over the end blocks, on the dimension it governs,
# naming the face it carries. The pedestal round is stock-sized. Short lines:
# the callout sits right of the pedestal, inside its length.
ROCKER_NUMBER = "MHA-CH-06"
PEDESTAL_LENGTH_CALLOUT = "\n".join(
    (
        f"{STEP_LIMITS[0]:.2f}-{STEP_LIMITS[1]:.2f} LONGER THAN",
        "EACH END BLOCK: CARRIES",
        f"{ROCKER_NUMBER} HUB FACE",
    )
)
PEDESTAL_DIA_CALLOUT = "STOCK OK"
BLOCK_COUNT_CALLOUT = "2X"

SURFACE_FINISHES = ()
DRAWING_NOTES = "\n".join(
    (
        "LOOSE SET: TWO END BLOCKS AND ONE PEDESTAL.",
        "VIEW SPACING IS NOT A REQUIREMENT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

# The fitting bench top under the set: clearance envelope only, never made.
BENCH_SIZE = (500.0, 160.0, 30.0)

# Prechips fixture solids in the inventory's fixture frame (Z0 = end-block
# tops), from the same constants the SolidWorks part is built from.
_FIXTURE_Z = -BLOCK_HEIGHT
# The #1413 placeholder provenance every solid carries: ``by`` is
# _process_plans.PLACEHOLDER_BY verbatim (test_process_shop pins the spelling)
# and bind_shop refuses a solid without a measured status (#1462).
_MEASURED = {
    "status": "measured",
    "by": "placeholder (realistic, remeasure: #1413)",
    "date": "2026-10-12",
    "instrument": (
        "digital calipers, height gauge and indicator; physical component sizes/fit only"
    ),
}
PRECHIPS_SOLIDS: list[dict[str, object]] = [
    {
        "name": "bench top",
        "shape": "box",
        "supply": "existing",
        "at_mm": [
            -BENCH_SIZE[0] / 2.0,
            -BENCH_SIZE[1] / 2.0,
            _FIXTURE_Z - BENCH_SIZE[2],
        ],
        "size_mm": list(BENCH_SIZE),
        "note": "fitting bench top, drawn for clearance",
        "measured": dict(_MEASURED),
    },
    *(
        {
            "name": f"{side} end block",
            "shape": "box",
            "at_mm": [west_x, BLOCK_SOUTH_Y, _FIXTURE_Z],
            "size_mm": [BLOCK_LENGTH, BLOCK_WIDTH, BLOCK_HEIGHT],
            "label": "end blocks",
            "locates": f"raw blank underside, {side} end",
            "note": "low-carbon steel offcut",
            "measured": dict(_MEASURED),
        }
        for side, west_x in zip(("left", "right"), BLOCK_WEST_X, strict=True)
    ),
    {
        "name": "hub pedestal",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, _FIXTURE_Z],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": PEDESTAL_DIA,
        "length_mm": PEDESTAL_LENGTH,
        "locates": "lower hub face (P01)",
        "note": f"low-carbon steel round, its top {STEP:.2f} above the end blocks",
        "measured": dict(_MEASURED),
    },
]
