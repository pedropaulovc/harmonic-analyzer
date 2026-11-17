"""The magnifier assembly's layout and tolerance stacks, checked offline.

These guards ran at import of ``build_mg_magnifier_assembly.py``, so a COM leaf on the farm
paid for them before SolidWorks opened.  They are pure functions of the
spec modules and the builder's own placement constants, so they run here
under ``check:recipe`` instead.  Each stack reads the values the builder
places from; ``STACKS`` also re-checks a freshly executed builder (negative
controls perturb an upstream spec and observe these gates).
"""

from __future__ import annotations

import pytest

import build_mg_magnifier_assembly
import _cone_axis_constants
import magnifying_bracket_joint_layout
import math
import mg_magnifier_assembly_spec as stack_spec
import mg_magnifying_lever_geom
import mg_magnifying_vertical_rod_geom
import mg_magnifying_wheel_geom
import mg_output_fixture_geom
import mg_wheel_bar_geom
import sh_vn_music_wire_lever_geom
import sm_summing_lever_spec


def _machine_anchors(magnifier) -> None:
    # The wheel stack (mg_wheel_group) and the axle's gauge read the bar's front
    # face from mg_wheel_bar_geom: it must be the clamp chain's.
    assert math.isclose(
        magnifier.BAR_FRONT_Z, mg_wheel_bar_geom.BAR_FRONT_Z, abs_tol=1e-9
    ), "wheel-bar front face drifted from mg_wheel_bar_geom.BAR_FRONT_Z"


def _magnifying_group(magnifier) -> None:
    assert math.isclose(
        magnifier.LEVER_ROD_Z, sh_vn_music_wire_lever_geom.DRUM_END_Z, abs_tol=1e-9
    ), (
        f"magnifying group plane {magnifier.LEVER_ROD_Z} left the drum wire lane {sh_vn_music_wire_lever_geom.DRUM_END_Z}"
    )
    # The lever is placed Ry(180) (local +x -> machine -x), so the knife lands at
    # LEVER_X0 - KNIFE_LOCAL_X.
    assert math.isclose(
        magnifier.LEVER_X0 - mg_magnifying_lever_geom.KNIFE_LOCAL_X,
        magnifier.KNIFE[0],
        abs_tol=1e-9,
    ), "magnifying-lever KnifeAxis x drifted from the summing knife line"
    assert math.isclose(
        magnifier.LEVER_ROD_Y + mg_magnifying_lever_geom.KNIFE_LOCAL_Y,
        magnifier.KNIFE_CONTACT_Y,
        abs_tol=1e-9,
    ), "magnifying-lever KnifeAxis y drifted from the knife-edge contact ridge"
    _MIN_THUMB_RAIL_CLEARANCE = 0.25
    assert magnifier.THUMB_SCREW_RAIL_CLEARANCE_WORST >= _MIN_THUMB_RAIL_CLEARANCE, (
        f"thumb-screw head clears the top-frame rail by only "
        f"{magnifier.THUMB_SCREW_RAIL_CLEARANCE_WORST:.4f} mm at the contact/head angle bound"
    )
    assert math.isclose(
        magnifying_bracket_joint_layout.SEAT_PLANE_Z,
        _cone_axis_constants.SUMMING_Z + sm_summing_lever_spec.PLATE_Z_MINUS,
        abs_tol=1e-9,
    ), "magnifying-bracket seat drifted from the summing-lever front face"
    assert all(
        math.isclose(actual, expected, abs_tol=1e-9)
        for actual, expected in zip(
            magnifier.BRACKET_ORIGIN,
            (magnifier.BRACKET_X, magnifier.LEVER_ROD_Y, magnifier.LEVER_ROD_Z),
            strict=True,
        )
    ), "magnifying-bracket joint origin drifted from its live placement"
    assert math.isclose(
        magnifier.VROD_TOP_Y,
        magnifier.LEVER_ROD_Y
        - magnifier.CLAMP_BORE_Y
        + mg_magnifying_vertical_rod_geom.SHOULDER_X,
        abs_tol=1e-9,
    ), "vertical-rod thread tip drifted from the clamp's bottom face + SHOULDER_X"
    assert math.isclose(
        magnifier.VROD_Z, mg_output_fixture_geom.VROD_Z, rel_tol=0.0, abs_tol=1e-9
    ), (
        f"fixture vertical-rod Z datum {mg_output_fixture_geom.VROD_Z} drifted from clamp datum {magnifier.VROD_Z}"
    )
    assert all(
        math.isclose(actual, expected, abs_tol=1e-9)
        for actual, expected in (
            (stack_spec.LEVER_TIP_X, magnifier.LEVER_X0),
            (stack_spec.LEVER_AXIS_Y, magnifier.LEVER_ROD_Y),
            (stack_spec.CLAMP_CENTRE_X, magnifier.CLAMP_X),
            (stack_spec.FIXTURE_AXIS_Y, magnifier.FIXTURE_POSITION[1]),
        )
    ), "mg_magnifier_assembly_spec's lever settings drifted from the placed lever group"
    assert magnifier.FIXTURE_SCREW_STANDOFF > 0.0, (
        "fixture screw collar must stand off the spigot"
    )


def _wheel(magnifier) -> None:
    # The bar's clamp holes must land on those screw lines: the bar is placed at
    # IDENTITY, so book hole x = centre + local station.
    assert sorted(
        round(magnifier.WHEEL_BAR_X0 + lx, 6) for lx in mg_wheel_bar_geom.CLAMP_HOLE_X
    ) == sorted(round(x, 6) for x in magnifier.CLAMP_SCREW_X), (
        "wheel-bar clamp holes drifted off the column clamp-screw lines"
    )
    assert (stack_spec.AXLE_X, stack_spec.AXLE_Y, stack_spec.BAR_FRONT_Z) == (
        magnifier.WHEEL_X,
        magnifier.WHEEL_BAR_Y,
        magnifier.BAR_FRONT_Z,
    ), "mg_magnifier_assembly_spec's axle line drifted from the placed axle"


def _amplification_wire(magnifier) -> None:
    assert all(
        math.isclose(a, b, abs_tol=1e-9)
        for a, b in zip(magnifier.HUB_WIRE_START, magnifier._HOOK_EXPECTED, strict=True)
    ), (
        f"lever-wire hook {magnifier.HUB_WIRE_START} drifted from the fixture anchor {magnifier._HOOK_EXPECTED}"
    )
    # The run grazes the brass drum at the 0.25 stand-off tangent ...
    assert math.isclose(
        math.hypot(
            magnifier.HUB_WIRE_END[0] - magnifier.WHEEL_X,
            magnifier.HUB_WIRE_END[1] - magnifier.WHEEL_BAR_Y,
        ),
        magnifier.DRUM_DIA / 2.0
        + magnifier.HUB_WIRE_DIA / 2.0
        + magnifier.WIRE_CLEARANCE,
        abs_tol=1e-9,
    ), "lever-wire end is not tangent to the drum"
    # ... inside the drum's axial span (boss front face .. spigot front end, wire
    # r inside each), and the slanted run clears the rim, spokes and boss pen-side
    # faces it passes (RUN_GAPS, asserted >= CLEARANCE in sh_vn_music_wire_lever_geom).
    assert (
        magnifier.WHEEL_MID_Z
        + mg_magnifying_wheel_geom.HUB_STEP_Z
        - magnifier.HUB_WIRE_DIA / 2.0
        > magnifier.HUB_WIRE_END[2]
        > magnifier.WHEEL_MID_Z
        + mg_magnifying_wheel_geom.HUB_FRONT_Z
        + magnifier.HUB_WIRE_DIA / 2.0
    ), "lever-wire end z outside the drum span"
    assert (
        min(sh_vn_music_wire_lever_geom.RUN_GAPS.values()) >= magnifier.WIRE_CLEARANCE
    ), f"lever-wire run gaps {sh_vn_music_wire_lever_geom.RUN_GAPS}"


STACKS = (
    _machine_anchors,
    _magnifying_group,
    _wheel,
    _amplification_wire,
)


@pytest.mark.parametrize("stack", STACKS, ids=lambda stack: stack.__name__.lstrip("_"))
def test_stack_closes(stack) -> None:
    stack(build_mg_magnifier_assembly)
