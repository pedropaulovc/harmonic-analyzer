"""check:budget -- the coefficient-error budget closes and stays tied to the CAD.

Pins the CONTRACT of cad/config/error_budget.yaml + error_budget.py rather than
its arithmetic: the linear sensitivities agree with the exact kinematics, the
readout procedure really cancels common-mode error, the second-harmonic
correction really removes the nominal-design residual, every toleranced nominal
still resolves to the spec constant the CAD builds from, the drawing limits
match the budget, and the Monte Carlo lands inside the targets. SolidWorks-free.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import math

import numpy as np
import pytest

import error_budget as eb

NOMINAL_FIELD = {
    "cam_eccentricity": "ecc",
    "rocker_rod_pin_radius": "pin_x",
    "lever_bar_pin_arm": "bar_pin_arm",
    "lever_spring_hook_arm": "hook_arm",
    "summing_hook_arm": "sum_arm",
    "spring_rate": "spring_rate",
}


@pytest.fixture(scope="module")
def budget():
    """The allocation config under test."""
    return eb.load_budget()


@pytest.fixture(scope="module")
def nom():
    """The as-designed inputs from the spec modules."""
    return eb.nominal()


@pytest.fixture(scope="module")
def report(budget):
    """One full model run, shared across the module."""
    return eb.build_report(budget)


def _resolve(dotted: str) -> float:
    """``module.ATTR`` -> its value, for the yaml's ``nominal`` references."""
    module, attr = dotted.rsplit(".", 1)
    return float(getattr(importlib.import_module(module), attr))


def test_every_toleranced_nominal_is_the_cad_constant(budget, nom):
    """A feature's `nominal` must be the spec symbol the build reads -- the
    budget cannot silently drift from the geometry it tolerances."""
    for key, feat in budget["critical_features"].items():
        if feat["nominal"] is None:
            assert key in ("cam_phase", "mesh_lag_spread", "station_setting"), key
            continue
        assert key in NOMINAL_FIELD, f"{key}: no Nominal field mapped"
        assert _resolve(feat["nominal"]) == pytest.approx(
            getattr(nom, NOMINAL_FIELD[key])
        )


def test_analytic_gain_sensitivities_match_exact_kinematics(report):
    """The closed-form gain sensitivities agree with central differences of the
    exact fundamental amplitude."""
    for key, (analytic, numeric) in report["finite_difference_check"].items():
        assert numeric == pytest.approx(analytic, rel=0.02), key


def test_calibrated_readout_cancels_common_mode_gain(nom):
    """Every channel 1 % strong -> zero coefficient error after the scale
    calibration; only channel-to-channel differences survive. The spring
    sensitivity is the numerator's 1 %/% -- the common denominator of the force
    balance is what this calibration removes, so it must not be pre-cancelled."""
    x = eb.reference_inputs()["gaussian_a0p1"]
    draws = 1
    sens = eb.gain_sensitivities(nom)
    assert sens["spring_rate"] == 1.0
    dev = {"spring_rate": np.full((draws, eb.N_ELEMENTS), 1.0)}
    cal = np.zeros((draws, eb.N_ELEMENTS))
    e = eb._channel_model(x, nom, dev, sens, cal)
    assert np.max(np.abs(e)) < 1e-9


def test_second_harmonic_correction_removes_the_nominal_residual(report):
    """The slider-crank distortion is the largest nominal term (>1 % of a
    channel's amplitude) and the readout correction takes the broad-input
    residual below 0.05 % MAE -- the claim tolerance-policy.md rests on."""
    h = report["harmonics"]["+88"]
    assert 0.010 < h["c2"] / h["c1"] < 0.020
    nde = report["nominal_design_errors"]
    for name in ("all_ones", "rect_half", "gaussian_a0p1"):
        assert nde["stick_zero_at_null_station"][name]["max"] > 1.0
        assert nde["null_station_and_c2_corrected"][name]["mae"] < 0.05
        assert nde["null_station_and_c2_corrected"][name]["max"] < 0.10


def test_null_station_is_below_the_pivot_zero(report, nom):
    """The slide arc sits above the pivot centreline, so a bar at the pivot
    zero still moves: the stick zero belongs at the null station."""
    d0 = report["null_station_mm"]
    assert -1.0 < d0 < -0.2
    assert (
        abs(eb.harmonic_content(d0, nom)["c1"]) < 1e-3 * eb.linear_gain(nom) * nom.d_max
    )


def test_budget_closes(report):
    """The Monte Carlo of the configured tolerances lands inside its targets."""
    assert eb.budget_closes(report) == []


def test_drawing_limits_agree_with_the_budget(budget):
    """Every budgeted limit that reaches a manufacturing output (drawing note,
    GD&T zone, fit band) carries the SAME number as error_budget.yaml."""
    import channel_spring_installed_notes
    import cylinder_gear_spec
    import summing_lever_spec

    feats = budget["critical_features"]
    ecc_tol = feats["cam_eccentricity"]["tolerance"]
    assert (
        f"AXIS OFFSET {cylinder_gear_spec.ECCENTRICITY:.3f} +/-{ecc_tol:.3f}"
        in cylinder_gear_spec.DRAWING_NOTES
    ), "cylinder-gear drawing note carries a different eccentricity tolerance"
    assert (
        f"NOTCH CENTERLINE\n  WITHIN +/-{feats['cam_phase']['tolerance']:.2f} DEG"
        in cylinder_gear_spec.DRAWING_NOTES
    ), "cylinder-gear drawing note carries a different cam-phase tolerance"
    assert (
        f"ALL 20 WITHIN +/-{feats['spring_rate']['tolerance']:.1f}% OF THE SET MEAN"
        in channel_spring_installed_notes.DRAWING_NOTES
    ), "spring spec sheet carries a different matching requirement"
    zone = float(
        summing_lever_spec.GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"]
    )
    assert zone == pytest.approx(
        2.0 * budget["critical_features"]["summing_hook_arm"]["tolerance"]
    )
    backlash_lo, backlash_hi = eb._config.fit("gear_mesh", "backlash_mm")
    pitch_r = (
        eb.cylinder_gear_spec.TEETH
        / (2.0 * eb.cylinder_gear_spec.DIAMETRAL_PITCH)
        * 25.4
    )
    spread_deg = math.degrees((backlash_hi - backlash_lo) / 2.0 / pitch_r)
    assert budget["critical_features"]["mesh_lag_spread"]["tolerance"] == pytest.approx(
        spread_deg, abs=0.01
    )


def test_assembly_imports_the_shared_stations_instead_of_copying():
    """build_channel_assembly imports SolidWorks, so it cannot be imported in
    this gate; pin at the SOURCE level that its PIVOT / FULCRUM / arc centre /
    slide radius come from the shared modules error_budget reads, never from a
    literal."""
    src = (pathlib.Path(eb.__file__).with_name("build_channel_assembly.py")).read_text(
        encoding="utf-8"
    )
    assert re.search(r"^\s*LEVER_FULCRUM_XY as FULCRUM,\s*$", src, re.M)
    assert re.search(r"^\s*ROCKER_PIVOT_XY as PIVOT,\s*$", src, re.M)
    assert re.search(
        r"^from rocker_arm_spec import CENTER_Y as ARM_ARC_CENTER_LOCAL_Y", src, re.M
    )
    assert re.search(
        r"^from rocker_arm_spec import CURVE_RADIUS as ARM_TOP_RADIUS", src, re.M
    )
    for name in ("PIVOT", "FULCRUM", "ARM_ARC_CENTER_LOCAL_Y", "ARM_TOP_RADIUS"):
        assert not re.search(rf"^{name}\s*=", src, re.M), (
            f"{name} is copied, not imported"
        )


def test_unsupported_distribution_fails_loud(budget, nom):
    """A distribution the model does not implement raises instead of sampling uniform."""
    bad = {**budget, "monte_carlo": {**budget["monte_carlo"], "distribution": "normal"}}
    with pytest.raises(ValueError, match="distribution"):
        eb.monte_carlo(bad, nom)
