"""The pen assembly's layout and tolerance stacks, checked offline.

These guards ran at import of ``build_pn_pen_assembly.py``, so a COM leaf on the farm
paid for them before SolidWorks opened.  They are pure functions of the
spec modules and the builder's own placement constants, so they run here
under ``check:recipe`` instead.  Each stack reads the values the builder
places from; ``STACKS`` also re-checks a freshly executed builder (negative
controls perturb an upstream spec and observe these gates).
"""

from __future__ import annotations

import pytest

import build_pn_pen_assembly
import math
import mg_wheel_bar_geom
import pn_pen_assembly_spec as spec
import pn_pen_carriage_geom
import pn_pen_hanger_spec
import pn_vn_hanger_screw_spec
import pn_vn_pen_hanger_jam_nut_spec
import sh_vn_music_wire_pen_geom


def _assembly_identity(pen) -> None:
    assert pen.ASM_NAME == spec.ASM_NAME, (pen.ASM_NAME, spec.ASM_NAME)


def _hanger_guides(pen) -> None:
    assert (
        pn_pen_carriage_geom.ROD_SQUARE_TOP_Y[0]
        >= pn_pen_hanger_spec.GUIDE_SPAN_Y[1] + pn_pen_hanger_spec.GUIDE_ENGAGE_MARGIN
    ), "pen-rod square leaves the upper U guide at the bottom of travel"
    assert (
        pn_pen_carriage_geom.CARRIAGE_TOP_Y[1]
        <= pn_pen_hanger_spec.GUIDE_SPAN_Y[0] - pn_pen_hanger_spec.GUIDE_ENGAGE_MARGIN
    ), "pen carriage reaches the lower U guide at the top of travel"


def _amplification_wire(pen) -> None:
    # The run's top rides the rim groove's tangent at the wheel-axis height; it hangs
    # plumb onto the stud's eye head, which stays below the rim at the top of travel.
    assert math.isclose(
        pen.PEN_WIRE_BOTTOM[1] + sh_vn_music_wire_pen_geom.WIRE_LEN,
        pen.WHEEL_BAR_Y,
        abs_tol=1e-9,
    ), "pen-wire top drifted from the wheel-axis tangent height"
    _RIM_LOW_Y_AT_WIRE = pen.WHEEL_BAR_Y - math.sqrt(
        pen._RIM_R**2 - (pen.WHEEL_X - pen.PEN_WIRE_BOTTOM[0]) ** 2
    )
    assert pn_pen_carriage_geom.STUD_HEAD_TOP_Y[1] <= _RIM_LOW_Y_AT_WIRE - 2.0, (
        "adjuster stud eye reaches the magnifying-wheel rim at the top of travel"
    )


def _hanger_screw(pen) -> None:
    assert math.isclose(
        pen.HANGER_SCREW_POS[0], mg_wheel_bar_geom.HANGER_SCREW_MACHINE_X, abs_tol=1e-9
    )
    assert math.isclose(pen.HANGER_SCREW_POS[1], pen.WHEEL_BAR_Y, abs_tol=1e-9)
    assert (
        pen.HANGER_THREAD_PAST_NUT
        >= pn_vn_pen_hanger_jam_nut_spec.THREAD_PAST_MIN_PITCHES
        * pn_vn_hanger_screw_spec.THREAD_PITCH
    ), "stock hanger screw stands under two full pitches past the jam nut"
    assert pen.HANGER_TIP_TO_RIM > 0.0, (
        "stock hanger screw tip reaches the magnifying-wheel rim"
    )
    assert pen.HANGER_NUT_RIM_RADIAL > 0.0, (
        "hanger nut corners reach the magnifying-wheel rim"
    )


STACKS = (
    _assembly_identity,
    _hanger_guides,
    _amplification_wire,
    _hanger_screw,
)


@pytest.mark.parametrize("stack", STACKS, ids=lambda stack: stack.__name__.lstrip("_"))
def test_stack_closes(stack) -> None:
    stack(build_pn_pen_assembly)
