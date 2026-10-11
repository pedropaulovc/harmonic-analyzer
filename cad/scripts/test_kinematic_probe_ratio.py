"""The kinematic probe's selected crank -> knob chain-ratio check, SolidWorks-free.

The probe must tell the selected tooth ratio from wrong couplings a Belt/
Chain feature can bake in: the #25 outside (tip) diameters, or the pitch-circle
diameters p/sin(180/N) typed instead of the per-tooth N*p/pi.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path
import runpy

import pytest

import pd_transgear_removable_spec as removable
import _chain as chain
import build_kinematic_probe as probe
import build_pd_paper_drive_assembly as assembly
import paper_drive_geom as law
from build_kinematic_probe import (
    CHAIN_RATIO,
    CRANK_TOL,
    DRIVE_DEG,
    READ_SLACK_DEG,
    check_chain_ratio,
)

OD_RATIO = (
    removable.outside_dia(removable.CRANK_TEETH)
    / removable.outside_dia(removable.KNOB_TEETH)
)
PITCH_CIRCLE_RATIO = (
    removable.pitch_dia(removable.CRANK_TEETH)
    / removable.pitch_dia(removable.KNOB_TEETH)
)


def test_mounted_feed_law_and_inverse_swap_follow_the_selection() -> None:
    expected_chain = (
        removable.configuration_teeth(removable.CRANK_CONFIG)
        / removable.configuration_teeth(removable.KNOB_CONFIG)
    )
    assert law.CHAIN_RATIO == pytest.approx(expected_chain)
    assert law.COARSE_FEED_RATIO == pytest.approx((1.0 / expected_chain) ** 2)
    assert law.NET_RACK_TRAVEL_PER_CRANK_REV == pytest.approx(
        expected_chain * law.GEAR_RATIO * math.pi * law.FEED_PITCH_DIA
    )


@pytest.mark.parametrize("crank_config", [name for name, _ in removable.CONFIGS])
@pytest.mark.parametrize("knob_config", [name for name, _ in removable.CONFIGS])
def test_registered_selections_drive_feed_and_chain_profiles(
    monkeypatch: pytest.MonkeyPatch, crank_config: str, knob_config: str
) -> None:
    """Changing only mounted configuration data changes the pure consumers."""
    crank_teeth = removable.configuration_teeth(crank_config)
    knob_teeth = removable.configuration_teeth(knob_config)
    monkeypatch.setattr(removable, "CRANK_CONFIG", crank_config)
    monkeypatch.setattr(removable, "KNOB_CONFIG", knob_config)
    monkeypatch.setattr(removable, "CRANK_TEETH", crank_teeth)
    monkeypatch.setattr(removable, "KNOB_TEETH", knob_teeth)
    selected_law = runpy.run_path(law.__file__)
    # Selection changes the radii, never the installed physical chain count.
    # Some registered pairs cannot even fit the inherited visual guide; keep
    # those cases as explicit refusals rather than silently choosing more links.
    ra, rb = removable.pitch_dia(knob_teeth) / 2.0, removable.pitch_dia(crank_teeth) / 2.0
    distance = math.dist(chain.KNOB_CENTRE, chain.CRANK_CENTRE)
    dr = ra - rb
    visual_taut = (
        2.0 * math.sqrt(distance * distance - dr * dr)
        + math.pi * (ra + rb)
        + 2.0 * dr * math.asin(dr / distance)
    )
    if removable.CHAIN_LINK_COUNT * removable.CHAIN_PITCH <= visual_taut:
        with pytest.raises(ValueError, match="visual guide cannot fit"):
            runpy.run_path(chain.__file__)
        selected_chain = None
    else:
        selected_chain = runpy.run_path(chain.__file__)
    ratio = crank_teeth / knob_teeth
    assert selected_law["CHAIN_RATIO"] == pytest.approx(ratio)
    assert selected_law["COARSE_FEED_RATIO"] == pytest.approx((1.0 / ratio) ** 2)
    assert selected_law["NET_RACK_TRAVEL_PER_CRANK_REV"] == pytest.approx(
        ratio * law.GEAR_RATIO * math.pi * law.FEED_PITCH_DIA
    )
    if selected_chain is None:
        return
    for role, teeth in (("CRANK", crank_teeth), ("KNOB", knob_teeth)):
        assert selected_chain[f"{role}_PITCH_R"] == pytest.approx(
            removable.pitch_dia(teeth) / 2.0
        )
        assert selected_chain[f"{role}_TIP_R"] == pytest.approx(
            removable.outside_dia(teeth) / 2.0
        )
    assert selected_chain["WRAP_R_A"] == selected_chain["KNOB_PITCH_R"]
    assert selected_chain["WRAP_R_B"] == selected_chain["CRANK_PITCH_R"]
    assert selected_chain["LINK_PITCH"] == removable.CHAIN_PITCH
    assert selected_chain["LINK_COUNT"] == removable.CHAIN_LINK_COUNT
    assert selected_chain["CENTRELINE_LEN"] == pytest.approx(
        selected_chain["LINK_COUNT"] * removable.CHAIN_PITCH
    )
    assert selected_chain["_loop_length"](selected_chain["SAG"]) == pytest.approx(
        selected_chain["CENTRELINE_LEN"], abs=1e-6
    )


def test_mounted_chain_radii_and_coupling_diameters_share_the_counts() -> None:
    for configuration, teeth, pitch_r, tip_r in (
        (
            removable.CRANK_CONFIG, removable.CRANK_TEETH,
            chain.CRANK_PITCH_R, chain.CRANK_TIP_R,
        ),
        (
            removable.KNOB_CONFIG, removable.KNOB_TEETH,
            chain.KNOB_PITCH_R, chain.KNOB_TIP_R,
        ),
    ):
        assert pitch_r == pytest.approx(removable.pitch_dia(teeth) / 2.0)
        assert tip_r == pytest.approx(removable.outside_dia(teeth) / 2.0)
        assert assembly.REMOVABLE_TIP_R[configuration] == pytest.approx(tip_r)
        assert assembly.CHAIN_PULLEY_DIA[configuration] == pytest.approx(
            teeth * removable.CHAIN_PITCH / math.pi
        )
    assert (
        assembly.CHAIN_PULLEY_DIA[removable.CRANK_CONFIG]
        / assembly.CHAIN_PULLEY_DIA[removable.KNOB_CONFIG]
    ) == pytest.approx(law.CHAIN_RATIO)
    assert assembly.KNOB_CHAIN_INNER_R == pytest.approx(min(
        removable.chain_plate_inner_radius(removable.KNOB_TEETH, height)
        for height in (chain.PLATE_HEIGHT, removable.ANSI_PLATE_HEIGHT)
    ))


def test_knob_clearance_checks_the_selected_wheel_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_config = next(
        name for name, _ in removable.CONFIGS if name != removable.KNOB_CONFIG
    )
    monkeypatch.setattr(removable, "KNOB_CONFIG", other_config)
    reach = math.dist(assembly.KNOB_SHAFT_XY, assembly.STUD_XY)
    monkeypatch.setitem(assembly.REMOVABLE_TIP_R, other_config, reach)
    with pytest.raises(RuntimeError, match=f"mounted knob {other_config}"):
        assembly._assert_knob_shaft_clearance()


def test_removable_roles_follow_centres_not_configuration_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    centres = {
        "pd-transgear-removable-1": assembly.KNOB_SHAFT_XY,
        "pd-transgear-removable-2": (
            -assembly.CHAIN_CRANK_CENTRE[0], assembly.CHAIN_CRANK_CENTRE[1]
        ),
        "pd-transgear-removable-3": assembly.SPARE_GEAR_POS[:2],
    }
    monkeypatch.setattr(probe, "component_names", lambda _: list(reversed(centres)))
    monkeypatch.setattr(probe, "_origin_xy", lambda _, name: centres[name])
    assert probe._removables_by_role(None) == {
        "crank": "pd-transgear-removable-2",
        "knob": "pd-transgear-removable-1",
        "spare": "pd-transgear-removable-3",
    }


def test_assembly_placement_belt_and_free_dof_use_the_selected_roles() -> None:
    """Protect the native recipe's configuration, coupling order and crank DOF."""
    source = Path(assembly.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    placements = {
        node.targets[0].id: node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Await)
        and isinstance(node.value.value, ast.Call)
        and getattr(node.value.value.func, "id", None) == "place_component"
    }
    for role, configuration in (
        ("crank_wheel", "CRANK_CONFIG"), ("knob_wheel", "KNOB_CONFIG")
    ):
        call = placements[role]
        assert ast.literal_eval(call.args[1]) == "pd-transgear-removable"
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        assert ast.unparse(keywords["configuration"]) == f"REMOVABLE.{configuration}"
        assert ast.literal_eval(keywords["ground"]) is False
    belts = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "BeltChainParameters"
    ]
    assert len(belts) == 1
    belt = {keyword.arg: keyword.value for keyword in belts[0].keywords}
    assert ast.unparse(belt["pulley_components"]) == "[crank_wheel, knob_wheel]"
    assert [ast.unparse(value) for value in belt["pulley_diameters"].elts] == [
        "CHAIN_PULLEY_DIA[REMOVABLE.CRANK_CONFIG]",
        "CHAIN_PULLEY_DIA[REMOVABLE.KNOB_CONFIG]",
    ]
    assert [
        value.value.id
        for axis in belt["pulley_member_axes"].elts
        for value in axis.values
        if isinstance(value, ast.FormattedValue)
    ] == ["crank_wheel", "knob_wheel"]
    assert ast.literal_eval(belt["engage_belt"]) is True
    necessity = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "assert_free_dof_necessity"
    ]
    assert len(necessity) == 1
    required = next(
        keyword.value for keyword in necessity[0].keywords
        if keyword.arg == "required_instances"
    )
    assert ast.unparse(required) == "(crank_wheel,)"


def test_exact_tooth_ratio_passes() -> None:
    check_chain_ratio(DRIVE_DEG * CHAIN_RATIO, DRIVE_DEG)


def test_worst_admitted_reading_slack_passes() -> None:
    # The least crank the drive gate admits, both readings off by (just under)
    # the per-reading slack in opposite directions: a legitimate solve.
    crank = DRIVE_DEG - CRANK_TOL
    slack = 0.99 * READ_SLACK_DEG
    check_chain_ratio(crank * CHAIN_RATIO + slack, crank - slack)
    check_chain_ratio(crank * CHAIN_RATIO - slack, crank + slack)


@pytest.mark.parametrize(
    "wrong_ratio",
    [
        pytest.param(OD_RATIO, id="outside-diameter"),
        pytest.param(PITCH_CIRCLE_RATIO, id="pitch-circle"),
        # Halfway to each wrong coupling must already read as wrong, so the
        # band cannot straddle the midpoint between right and wrong.
        pytest.param((OD_RATIO + CHAIN_RATIO) / 2.0, id="outside-diameter-midpoint"),
        pytest.param(
            (PITCH_CIRCLE_RATIO + CHAIN_RATIO) / 2.0, id="pitch-circle-midpoint"
        ),
    ],
)
def test_wrong_diameter_coupling_is_rejected(wrong_ratio: float) -> None:
    with pytest.raises(RuntimeError, match="chain ratio"):
        check_chain_ratio(DRIVE_DEG * wrong_ratio, DRIVE_DEG)


def test_dropped_belt_mate_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="chain ratio"):
        check_chain_ratio(0.0, DRIVE_DEG)


def _sw_rotation(m: list[list[float]]) -> list[float]:
    """``Transform2.ArrayData``'s rotation for column-vector matrix ``m``:
    the part's axes are its rows, i.e. ``m`` transposed, flattened."""
    return [m[c][r] for r in range(3) for c in range(3)]


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)
    ]


def _rz(deg: float) -> list[list[float]]:
    import math

    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


@pytest.mark.parametrize(
    "frame",
    [
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],  # identity disc
        [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]],  # Ry180 feed sleeve
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]],  # Rx180
    ],
)
def test_signed_spin_reads_alike_whatever_the_insertion_frame(
    frame: list[list[float]],
) -> None:
    """Two parts Lock-mated on one global Z axis spin by the same signed angle
    even when one was inserted flipped (run 20261001T051043622Z read the Ry180
    feed sleeve +1.50 against its identity disc's -1.50)."""
    from build_kinematic_probe import _rel_z_angle_deg

    for spin in (1.5, -7.0, 30.0):
        before = _sw_rotation(_matmul(_rz(40.0), frame))
        after = _sw_rotation(_matmul(_rz(40.0 + spin), frame))
        # The identity frame keeps the sign the probe's constants were set on.
        assert _rel_z_angle_deg(after, before) == pytest.approx(-spin)
