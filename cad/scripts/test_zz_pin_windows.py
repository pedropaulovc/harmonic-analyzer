"""The Class ZZ pin windows the reamed-bore travelers print (owner ruling
2026-11-23, tool audit Q1): GO a plus pin at the bore's low limit, NO-GO a
minus pin at its high limit, each pin's acceptable reading one Class ZZ
tolerance (.0002 in) wide, and the gauge record spanning the model's band."""

from __future__ import annotations

import math
import tomllib

import pytest

import _process_plans
import export_features

ZZ_TOL_MM = 0.0002 * 25.4

# (plan stem, the bore's feature key, the plan's gauge record)
BORES = [
    ("mg_wheel_bar", "axle_bore", "zz-pins-1865-1870"),

    ("sm_knife_mount", "knife_bore", "zz-pins-4985-5000"),
]


@pytest.mark.parametrize(("stem", "feature", "gauge"), BORES)
def test_the_pin_windows_sit_on_the_model_bore_band(stem, feature, gauge) -> None:
    plan = tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))
    p = plan["parameters"]
    manifest = export_features.requirement_manifest(stem)
    low, high = manifest["features"][feature]["dia"]
    expected = {
        "go_pin_min_mm": low,
        "go_pin_max_mm": low + ZZ_TOL_MM,
        "nogo_pin_min_mm": high - ZZ_TOL_MM,
        "nogo_pin_max_mm": high,
    }
    for key, value in expected.items():
        assert math.isclose(p[key], value, abs_tol=1e-4), (stem, key, p[key], value)
    record = _process_plans.load_shop()["gauges"][gauge]
    assert record["range_mm"] == pytest.approx([low, high], abs=1e-4)
    assert any(tool.get("ref") == gauge for tool in plan["tools"])


def test_the_knife_mount_datum_b_pins_sit_inside_its_band() -> None:
    """MHA-SM-02 datum B (.1273-.1287): GO a .1275 minus single, NO-GO a
    .1285 plus single (owner ruling 2026-11-23, tool audit Q1: ZZ singles per
    the record), each pin's window one ZZ tolerance wide and inside the band."""
    plan = tomllib.loads(
        _process_plans.plan_path("sm_knife_mount").read_text(encoding="utf-8")
    )
    p = plan["parameters"]
    manifest = export_features.requirement_manifest("sm_knife_mount")
    low, high = manifest["features"]["dowel_hole"]["dia"]
    go, nogo = 0.1275 * 25.4, 0.1285 * 25.4
    expected = {
        "dowel_go_pin_min_mm": go - ZZ_TOL_MM,
        "dowel_go_pin_max_mm": go,
        "dowel_nogo_pin_min_mm": nogo,
        "dowel_nogo_pin_max_mm": nogo + ZZ_TOL_MM,
    }
    for key, value in expected.items():
        assert math.isclose(p[key], value, abs_tol=1e-4), (key, p[key], value)
    assert low - 1e-4 <= p["dowel_go_pin_min_mm"] and p["dowel_nogo_pin_max_mm"] <= high + 1e-4
    record = _process_plans.load_shop()["gauges"]["zz-pins-1273-1287"]
    assert record["range_mm"] == pytest.approx([low, high], abs=1e-4)
