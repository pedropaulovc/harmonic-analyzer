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
    ("ch_pivot_bracket", "bore", "zz-pins-2560-2600"),
    # Owner ruling 2026-11-23, tool audit Q7 and Q13.
    ("ch_fulcrum_keeper", "bore", "zz-pins-2560-2570"),
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


def test_the_knife_mount_datum_b_takes_no_zz_pins() -> None:
    """MHA-SM-02 datum B is a #30 drill at the title block's DRILLED HOLES row
    (owner ruling 2026-11-24, fit audit OQ19): its .1275/.1285 ZZ pins and
    their windows are retired."""
    plan = tomllib.loads(
        _process_plans.plan_path("sm_knife_mount").read_text(encoding="utf-8")
    )
    assert not any(key.startswith("dowel_go") or key.startswith("dowel_nogo") for key in plan["parameters"])
    assert "zz-pins-1273-1287" not in _process_plans.load_shop()["gauges"]
    assert not any(tool.get("ref") == "zz-pins-1273-1287" for tool in plan["tools"])
