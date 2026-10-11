r"""MHA-VN-051 knife-mount-dowel: McMaster 98381A473 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Four are used, two per knife mount: each is pressed chamfer end
first to the flat floor of a blind reamed hole in the MHA-SM-002 top seat and
slips, at assembly, into the underside of the MHA-FR-002 crossbar, one into a
round hole, the other into a slot along the dowel line.  The pair keys the
block against turning about its #6-32 knife-hanger screw (MHA-VN-024): the
screw clamps the seat to the casting underside, the pins react the torque and
hold the block's yaw.

Catalogue: 1/8 x 3/4 alloy-steel dowel, Round x Chamfer ends, diameter
+0.0001/+0.0003 in, Rockwell C47 min, ASME B18.8.2; the size row, the end
forms (read off the vendor model ``cad/references/mcmaster/98381A473.SLDPRT``)
and the diameter band are ``_mcmaster_98381a473``'s.  No
recommended hole size is stated; the press is the knife mount's own reamed
hole (``sm_knife_mount_spec.PIN_HOLE_DIA_BAND``), the slip the crossbar's
(``fr_top_frame_spec.HANGER_PIN_HOLE_DIA``).

This module owns the pin's interface between the two parts it joins: the
station of its axis from the screw axis, the press depth and the crossbar
hole's depth, as ``vn_crank_seat_drive_pin_spec`` owns its press depth for
``dt_crankshaft_spec``.

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.  The Front and Right
Planes contain the axis, published as ``ScrewAxis`` (Front x Right); the Top
Plane is the pressed end face, so an assembly places the pin by that plane
on the knife mount's hole floor.
"""

from __future__ import annotations

import _config
from _mcmaster_98381a473 import (
    DIA_BAND_IN,
    ENDS,
    DOWEL_SIZE,
    MM_PER_IN,
)

SKU = "98381A473"
DIA, LENGTH = DOWEL_SIZE  # 3.175 x 19.05
# Catalogue diameter band over nominal, mm, as (upper, lower) deviations:
# +0.00762 / +0.00254 (the catalogue row lists it low-first).
DIA_BAND = tuple(band * MM_PER_IN for band in reversed(DIA_BAND_IN))
DIA_MAX = DIA + max(DIA_BAND)  # 3.18262
DIA_MIN = DIA + min(DIA_BAND)  # 3.17754
# The pressed end's chamfer: the length of it that grips nothing.
CHAMFER_LEN = ENDS.chamfer_len(DIA)  # 0.443
# The family's length grade, +/-0.010 in (``dt_crankshaft_spec``'s
# DRIVE_PIN_LENGTH_GRADE for the same 98381A family).
LENGTH_GRADE = 0.010 * MM_PER_IN  # 0.254

# General tolerances the two holes' printed places claim (title block).
_X = float(str(_config.title_block("linear_1pl")["display"]).lstrip("\u00b1"))
_XXX = float(str(_config.title_block("linear_3pl")["display"]).lstrip("\u00b1"))

# Two pins per knife mount, their axes HANGER_OFFSET either side of the
# knife-hanger screw axis along machine X in BOTH parts (block local X is
# machine X: the mounts are placed unrotated).  The crossbar prints each
# station .XXX from its screw axis (HANGER_OFFSET_TOL); the knife mount holds
# the pair as its datum pattern B -- the 2X ream carries a position frame to
# the top seat, its SPAN BASIC -- and positions its tap to it.  The crossbar's slot takes up the spacing, its #6 clearance hole the
# rest (``fr_top_frame_spec``, ``build_sm_summing_assembly``).
PER_MOUNT = 2
MOUNTS = 2
QUANTITY = PER_MOUNT * MOUNTS
HANGER_OFFSET = 0.25 * MM_PER_IN  # 6.350
HANGER_OFFSET_PLACES = 3
HANGER_OFFSET_TOL = _XXX  # 0.13
# The pair's centre-to-centre span along the dowel line, BASIC.  Each hole's
# axis stands within half the frame's zone of its true position, so the span
# varies by the full zone: the knife mount's Ø0.13
# (``sm_knife_mount_spec.GEOMETRIC_TOLERANCES_MM``, which asserts it equals
# SPAN_TOL) keeps the 0.13 the .XXX span gave, and with it every stack the
# pair feeds (the 2026-10-09 ruling).
SPAN = 2.0 * HANGER_OFFSET  # 12.700
SPAN_PLACES = 3
SPAN_TOL = 0.13
# Pressed to the flat floor of the knife mount's blind hole, printed .X.
PRESS_DEPTH = 9.5
PRESS_DEPTH_PLACES = 1
PRESS_DEPTH_TOL = _X  # 0.8
# The crossbar's blind slip hole from its underside, printed .X.
SLIP_DEPTH = 12.0
SLIP_DEPTH_PLACES = 1
SLIP_DEPTH_TOL = _X  # 0.8
# A press-fit dowel grips at least 1.5 D (the rule-12 engagement floor,
# applied to the press as ``vn_transgear_latch_pin_spec`` does), counted over
# the full diameter only: the chamfer inside the hole carries no interference.
PRESS_ENGAGEMENT_MIN_D = 1.5


def proud_length(hole_depth: float, length_dev: float = 0.0) -> float:
    """The pin's length out of the knife mount's top seat when it is pressed
    to the floor of a blind hole ``hole_depth`` deep, the pin ``length_dev``
    off its nominal length."""
    return LENGTH + length_dev - hole_depth


def press_engagement_d(hole_depth: float) -> float:
    """Full-diameter press engagement, in D, of the pin bottomed in a blind
    hole ``hole_depth`` deep."""
    return (hole_depth - CHAMFER_LEN) / DIA


# The seat is clamped to the casting underside (no gap), so the pin's proud
# length goes straight up the crossbar hole: 9.55 nominal, 8.496..10.604.
PROUD = proud_length(PRESS_DEPTH)
PROUD_MIN = proud_length(PRESS_DEPTH + PRESS_DEPTH_TOL, -LENGTH_GRADE)
PROUD_MAX = proud_length(PRESS_DEPTH - PRESS_DEPTH_TOL, LENGTH_GRADE)
# The shallowest crossbar hole still takes the longest proud pin, or the pin
# would bottom and hold the seat off the casting: 11.2 - 10.604 = 0.596.
SLIP_DEPTH_CLEARANCE_MIN = SLIP_DEPTH - SLIP_DEPTH_TOL - PROUD_MAX
if SLIP_DEPTH_CLEARANCE_MIN <= 0.0:
    raise AssertionError(
        f"the longest proud knife-mount dowel ({PROUD_MAX:.3f}) bottoms in the"
        f" shallowest crossbar hole ({SLIP_DEPTH - SLIP_DEPTH_TOL:.3f})"
    )
# (8.7 - 0.443) / 3.175 = 2.60 D at the shallowest printed press depth.
PRESS_ENGAGEMENT_D_MIN = press_engagement_d(PRESS_DEPTH - PRESS_DEPTH_TOL)
if PRESS_ENGAGEMENT_D_MIN < PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"knife-mount dowel grips {PRESS_ENGAGEMENT_D_MIN:.2f} D in the block,"
        f" under {PRESS_ENGAGEMENT_MIN_D} D"
    )
