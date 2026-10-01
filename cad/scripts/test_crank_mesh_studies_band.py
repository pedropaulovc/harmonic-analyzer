"""The crank-mesh diagnostics model the pinion's turned band as shipped."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "diagnostics"))

import crank_mesh_backlash_study as backlash  # noqa: E402
import crossed_mesh_study as cms  # noqa: E402
from crank_pinion_spec import FACE_WIDTH, SHOULDER_LENGTH, TURNED_DIA  # noqa: E402


@pytest.fixture(scope="module")
def yawed_pose() -> backlash.Pose:
    """The shipped mesh with the crank bore yawed +1 deg, crank phase 0."""
    case = backlash.Case("yaw16=+1", yaw16=1.0)
    return backlash.Pose(
        case.extra,
        case.widen16,
        case.widen64,
        0.0,
        {},
        case.gear16,
        case.gear64,
        case.hand16,
        case.skew64,
        case.yaw16,
        case.tilt16,
        case.crank_xy(),
    )


def test_band_removes_tooth_material_past_the_turned_diameter(
    yawed_pose: backlash.Pose,
) -> None:
    g16 = yawed_pose.g16
    assert TURNED_DIA / 2.0 < g16.ra
    # A tooth point between the turned diameter and the tip: tooth material on
    # the full-OD shoulder, cut away north of it.
    r = np.array([(TURNED_DIA / 2.0 + g16.ra) / 2.0])
    sweep = np.linspace(0.0, g16.gamma, 2048, endpoint=False)
    tooth = np.flatnonzero(g16.material(sweep, np.full_like(sweep, r[0])))
    theta = sweep[tooth[len(tooth) // 2]][None]
    on_shoulder = cms.pinion_material(g16, theta, r, np.array([SHOULDER_LENGTH / 2.0]))
    in_band = cms.pinion_material(
        g16, theta, r, np.array([(SHOULDER_LENGTH + FACE_WIDTH) / 2.0])
    )
    assert on_shoulder.all()
    assert not in_band.any()
    # Under the turned diameter the band keeps its tooth.
    r_under = np.array([TURNED_DIA / 2.0 - 0.05])
    assert cms.pinion_material(
        g16, theta, r_under, np.array([(SHOULDER_LENGTH + FACE_WIDTH) / 2.0])
    ).all()


def test_pinion_boundary_stops_at_the_turned_diameter_in_the_band(
    yawed_pose: backlash.Pose,
) -> None:
    (_, r_full, z_full), (_, r_band, z_band) = yawed_pose.p_sections
    assert z_full.max() == pytest.approx(SHOULDER_LENGTH)
    assert z_band.min() > SHOULDER_LENGTH
    assert z_band.max() == pytest.approx(FACE_WIDTH)
    assert r_full.max() == pytest.approx(
        yawed_pose.g16.ra
    )  # full-OD teeth reach the tip
    assert r_band.max() <= TURNED_DIA / 2.0
    assert r_band.max() > TURNED_DIA / 2.0 - 0.05  # the turned circle itself


def test_yawed_backlash_window_honors_the_band(yawed_pose: backlash.Pose) -> None:
    # Full-OD teeth over the whole face close the window at -2.991 deg
    # (2.468 wide); the shipped band clears that north-end tip contact.
    res = backlash.window(yawed_pose, backlash.dta.MESH_WINDOW_CENTRE_DEG)
    assert res["width_deg"] == pytest.approx(2.4902, abs=0.002)
