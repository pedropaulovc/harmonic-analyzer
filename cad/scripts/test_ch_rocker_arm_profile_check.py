"""Offline contracts for the rocker arm's surface-profile check (plan F1 op 97)."""

from __future__ import annotations

import tomllib

import pytest

import _process_plans as plans
import ch_rocker_arm_profile_check as check
import ch_rocker_arm_tl_outline_template_spec as template
import export_features

STEM = "ch_rocker_arm"
_INVENTORY = tomllib.loads(
    (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_text(encoding="utf-8")
)["gauges"]


def _printed_zones() -> dict[str, tuple[float, float]]:
    """Each profiled feature's printed (t, U), from the exported manifest."""
    features = export_features.requirement_manifest(STEM)["features"]
    return {
        name: (fields["surface_profile"], fields["surface_profile_u"])
        for name, fields in features.items()
        if "surface_profile" in fields
    }


def _guard(point, normal) -> float:
    resolution = _INVENTORY["dti"]["resolution_in"]["value"] * 25.4
    return template.clocking_error(point, normal) + resolution


def _violations(windows: dict) -> list[str]:
    """Stations where an accepted reading, widened by the guard, could leave
    the printed zone (or touch its edge)."""
    zones = _printed_zones()
    found = []
    for name, segment in check.SEGMENTS.items():
        accept = windows[name]["accept"]
        for feature in segment["features"]:
            t, u = zones[feature]
            for point, normal in check.samples(name):
                tau = segment["tau"]((abs(point[0]), point[1]))
                low, high = tau - (t - u), tau + u
                guard = _guard(point, normal)
                if not (low < accept[0] - guard and accept[1] + guard < high):
                    found.append(f"{name} {feature} at {point}")
    return found


def test_plan_op_97_reads_every_profile_with_the_computed_procedure() -> None:
    plan = tomllib.loads(plans.plan_path(STEM).read_text(encoding="utf-8"))
    (op,) = [
        op
        for setup in plan["setups"]
        if setup["id"] == "F1"
        for op in setup["ops"]
        if op["op"] == 97
    ]
    assert op["checks"] == {"surface_profile": "dti"}
    assert sorted(op["feature"]) == sorted(_printed_zones())
    covered = {feature for s in check.SEGMENTS.values() for feature in s["features"]}
    assert covered == set(_printed_zones())
    assert op["inspection_methods"]["surface_profile"] == check.method_steps()


def test_op_97_uses_only_the_inventory_dti_and_height_gauge() -> None:
    assert _INVENTORY["dti"]["kind"] == "dial_test_indicator"
    assert check.DTI_RESOLUTION_MM == pytest.approx(0.0005 * 25.4)
    text = " ".join(check.method_steps())
    assert "gauges.dti" in text and "gauges.height-gauge" in text
    assert "AUTHOR'S CHOICE" in text


def test_every_accept_window_lies_strictly_inside_its_zone_after_the_guard() -> None:
    assert _violations(check.WINDOWS) == []
    for window in check.WINDOWS.values():
        # A tool-filed edge on the template's line, and the reject limits
        # outside the accept window.
        assert window["reject"][0] < window["accept"][0] < 0.0 < window["accept"][1]
        assert window["accept"][1] < window["reject"][1]


def test_window_check_goes_red_without_the_guard(monkeypatch) -> None:
    monkeypatch.setattr(check, "guard", lambda _point, _normal: 0.0)
    unguarded = {name: check.window(name) for name in check.SEGMENTS}
    assert _violations(unguarded)


def test_window_check_goes_red_with_a_wider_zone(monkeypatch) -> None:
    monkeypatch.setattr(check, "ZONE_MM", check.ZONE_MM + 0.1)
    widened = {name: check.window(name) for name in check.SEGMENTS}
    assert _violations(widened)


def test_the_template_edge_is_mid_zone_on_every_segment() -> None:
    """The windows are centred because the template aims at mid-zone: its
    edge sits half the zone in from either side, less the arcs' residual."""
    half = check.ZONE_MM / 2.0
    for name in check.SEGMENTS:
        for point, _normal in check.samples(name):
            low, high = check.zone_readings(name, point)
            assert low == pytest.approx(-half, abs=0.005)
            assert high == pytest.approx(half, abs=0.005)
