"""Fusion CAM driver, recipe frame and posted-G-code checks, without Fusion.

The G-code cases are the errors Fusion produced with valid-looking toolpaths
while the base-bar programs were first written (2026-11-16): a spot drill
measured from the counterbore floor, a feed height below the stock top, a slot
cut from the outside, and an oversized radial step.
"""

from __future__ import annotations

import base64
import json
import re
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _gcode
import _process_plans
import fusion_cam
from _fusion_mcp import FusionError

STEM = "ch_rocker_arm_tl_oblique_base_bar"


def _program(tmp_path: Path, text: str) -> _gcode.Program:
    path = tmp_path / "p.nc"
    path.write_text(text, encoding="utf-8")
    return _gcode.read_program(path)


def test_long_source_lines_reach_fusion_as_short_lines(tmp_path):
    # Fusion skips a script with a >4096-character line and still reports success.
    recipe = tmp_path / "cam.py"
    source = f"TABLE = {'x' * 10_000!r}\n"
    recipe.write_text(source, encoding="utf-8")
    script = fusion_cam.compose_script(recipe, {"post": "Grbl"}, [("P1", ["a"])], tmp_path)
    assert max(len(line) for line in script.splitlines()) <= fusion_cam.MAX_SCRIPT_LINE
    encoded = "".join(re.findall(r'^    "([A-Za-z0-9+/=]+)",?$', script, re.MULTILINE))
    payload = json.loads(base64.b64decode(encoded))
    assert payload["recipe"] == source
    assert payload["programs"] == [["P1", ["a"]]]


def test_silent_fusion_output_is_a_failure():
    with pytest.raises(FusionError):
        fusion_cam.parse_result("")
    assert fusion_cam.parse_result(f"noise\n{fusion_cam.RESULT_MARKER}{{\"files\": []}}\n") == {"files": []}


def _features() -> dict:
    """The v49 manifest's base-bar features, reduced to what the recipe reads."""
    def plane(value):
        return {"kind": "plane", "plane": {"value": value}}

    f = {
        "bar_spindle_end": plane(0.0), "bar_far_end": plane(439.928),
        "bar_low_side": plane(-88.9), "bar_high_side": plane(50.8),
        "underside_seat": plane(0.0), "top_seat": plane(11.938),
        "near_slot": {"kind": "slot", "at": [22.084, -39.624, 11.938], "separation": [3.81, 4.318], "width_nominal": 13.462},
        "far_slot": {"kind": "slot", "at": [389.89, 35.56, 11.938], "separation": [3.81, 4.318], "width_nominal": 13.462},
    }
    for i in range(4):
        f[f"rail_{i}"] = {"kind": "threaded_hole", "at": [9.964 + 60 * i, 0.0, 11.938], "nominal_dia": 3.4544}
    for name, x, y in (("b1", 47.484, -33.991), ("b2", 428.0, -75.991)):
        f[name] = {"kind": "hole", "at": [x, y, 11.938], "dia_nominal": 4.8006}
        f[f"{name}_cbore"] = {"kind": "counterbore", "parent": name, "dia_nominal": 7.9502, "depth_ref": 5.08}
    return {"features": f}


def _context() -> dict:
    recipe = _cam_programs.load_recipe(STEM)
    with _process_plans.plan_path(STEM).open("rb") as plan, _process_plans.SHOP_PATH.open("rb") as shop:
        return recipe.context(_features(), tomllib.load(plan), tomllib.load(shop), "bar.STEP")


def test_recipe_maps_features_into_the_drawing_frame():
    # ZERO EDGE is WCS Y0 with +Y into the bar, and the C'BORE SIDE is up, so the
    # drawing's bracket ordinates (54.909, 12.909 from ZERO EDGE) appear negated.
    ctx = _context()
    assert [c for xy in ctx["bracket"]["centres"] for c in xy] == pytest.approx([47.484, -54.909, 428.0, -12.909])
    assert [y for _x, y in ctx["rail"]["centres"]] == pytest.approx([-88.9] * 4)
    recipe = _cam_programs.load_recipe(STEM)
    slots = [kw for program, check, kw in recipe.expectations(ctx) if check == "bounds"]
    assert [s["x"] for s in slots] == [pytest.approx((21.703, 22.465)), pytest.approx((389.509, 390.271))]
    assert slots[0]["y"] == pytest.approx((-53.34, -49.276))


def test_spot_depth_measured_from_the_counterbore_floor_is_caught(tmp_path):
    program = _program(tmp_path, "G0 X10 Y5 Z5\nG1 Z-8.095 F100\nG0 Z5\n")
    findings = _gcode.check_holes(program, [(10.0, 5.0)], z_bottom=-3.015)
    assert [f.check for f in findings] == ["holes"]
    assert _gcode.check_holes(_program(tmp_path, "G0 X10 Y5 Z5\nG1 Z-3.015 F100\nG0 Z5\n"), [(10.0, 5.0)], -3.015) == []


def test_rapid_below_the_stock_top_is_caught_but_peck_reentry_is_not(tmp_path):
    entering = _program(tmp_path, "G0 X10 Y5 Z5\nG0 Z-0.5\nG1 Z-4 F100\nG0 Z5\n")
    assert [f.check for f in _gcode.check_rapids_clear(entering, 0.0, [(10.0, 5.0)])] == ["rapid"]
    pecking = _program(tmp_path, "G0 X10 Y5 Z5\nG1 Z-4 F100\nG0 Z5\nG0 Z-3.9\nG1 Z-8 F100\nG0 Z5\n")
    assert _gcode.check_rapids_clear(pecking, 0.0, [(10.0, 5.0)]) == []


def test_slot_cut_from_the_outside_is_caught(tmp_path):
    # Cutter-centre X 9.003–35.165 and counter-clockwise: the outside contour.
    program = _program(tmp_path, "G0 X9.003 Y-50 Z5\nG1 Z-12.446 F100\nG3 X35.165 Y-50 I13.081 J0\nG0 Z5\n")
    window = ((0.0, 45.0), (-60.0, -40.0))
    findings = _gcode.check_bounds(program, window, (21.703, 22.465), (-50.0, -50.0), -12.446, "G2")
    assert {f.check for f in findings} == {"bounds"}
    assert len(findings) == 2


def test_side_step_over_the_plan_limit_is_caught(tmp_path):
    program = _program(tmp_path, "G0 X0 Y-12.7 Z5\nG1 Z-14 F100\nG1 X400\nG1 Y-6.35\nG1 X0\nG0 Z5\n")
    kwargs = {"axis": "Y", "raw": -12.7, "span": 200.0, "below_z": 0.0}
    findings = _gcode.check_side_passes(program, final=-6.35, max_step=2.0, direction=-1.0, **kwargs)
    assert any("removes" in f.detail for f in findings)
