"""Explicit, volume-bounded interference-fit contract for the cam turning fixture kit.

MHA-DT-12-TL-00 (``build_dt_cylinder_gear_tl_cam_turning_assembly``). Its
nominal solids overlap in exactly three intended fits: the stub dowel
pressed through the body's .3745 ream, the clock pin pressed to the floor of
the body's .0365 ream, and the clamp screw's thread in the stub's 10-32 tap
(modelled at the tap drill). Every other overlap is a defect. Only this
kit's builder and ``verify_soundness:dt_cylinder_gear_tl_cam_turning`` fold
this module.
"""

from __future__ import annotations

from collections.abc import Mapping

import dt_cylinder_gear_tl_cam_fixture_spec as fixture
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _interference_common import numbered_pairs, smooth_annulus_limit_mm3
from _mcmaster_97175a344 import THREAD as STUB_THREAD

_BODY = "dt-cylinder-gear-tl-cam-fixture"
_VENDOR = "dt-cylinder-gear-tl-vn-cam"
# (pin diameter, hole diameter, overlap length), mm: each fit's nominal
# annulus; smooth_annulus_limit_mm3 adds 10% headroom.
STUB_PRESS = (
    fixture.DOWEL_DIA,
    fixture.STUB_HOLE_DIA,
    fixture.STUB_PRESS_DEPTH_IN_BODY,
)
PIN_PRESS = (fixture.PIN_DIA, fixture.PIN_HOLE_DIA, fixture.PIN_HOLE_DEPTH)
SCREW_THREAD = (
    THREAD_MAJOR_MM[STUB_THREAD],
    TAP_DRILL_MM[STUB_THREAD],
    fixture.SCREW_ENGAGEMENT,
)
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
        f"{_VENDOR}-stub", range(1, 2), _BODY, smooth_annulus_limit_mm3(*STUB_PRESS)
    ),
    **numbered_pairs(
        f"{_VENDOR}-clock-pin", range(1, 2), _BODY, smooth_annulus_limit_mm3(*PIN_PRESS)
    ),
    **numbered_pairs(
        f"{_VENDOR}-clamp-screw",
        range(1, 2),
        f"{_VENDOR}-stub",
        smooth_annulus_limit_mm3(*SCREW_THREAD),
    ),
}
