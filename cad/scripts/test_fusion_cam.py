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


def _features(rail_requirements=("thread", "dia", "station", "height", "thru")) -> dict:
    """The base bar's exported features, reduced to what the recipe reads. Rail
    holes carry the drawing's export requirements, "station" included since the
    stations are held at ±0.05 mm; ``rail_requirements`` without it is the REF
    shape the recipe refuses."""
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
        f[f"rail_{i}"] = {"kind": "threaded_hole", "at": [9.964 + 60 * i, 0.0, 11.938], "nominal_dia": 3.4544,
                          "requirements": list(rail_requirements)}
    for name, x, y in (("b1", 47.484, -33.991), ("b2", 428.0, -75.991)):
        f[name] = {"kind": "hole", "at": [x, y, 11.938], "dia_nominal": 4.8006}
        f[f"{name}_cbore"] = {"kind": "counterbore", "parent": name, "dia_nominal": 7.9502, "depth_ref": 5.08}
    return {"features": f}


def _context() -> dict:
    recipe = _cam_programs.load_recipe(STEM)
    with _process_plans.plan_path(STEM).open("rb") as plan, _process_plans.SHOP_PATH.open("rb") as shop:
        return recipe.context(_features(), tomllib.load(plan), tomllib.load(shop), "bar.STEP")


def test_rail_programs_refuse_ref_stations():
    # A REF rail station is transferred from each bar's own rail; drilling the
    # nominal would miss the real rail holes (Codjiflo P1 on #2832).
    recipe = _cam_programs.load_recipe(STEM)
    with _process_plans.plan_path(STEM).open("rb") as plan, _process_plans.SHOP_PATH.open("rb") as shop:
        with pytest.raises(ValueError, match="REF"):
            recipe.context(_features(("thread", "dia", "height", "thru")), tomllib.load(plan), tomllib.load(shop), "bar.STEP")


def test_recipe_maps_features_into_the_drawing_frame():
    # S3/S4: ZERO EDGE is WCS Y0 at the back jaw and the bar lies at -Y, so the
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


def test_finish_pass_heavier_than_the_finish_step_is_caught(tmp_path):
    # Roughing steps within 2.032, but the last pass takes 0.5 where 0.254 is planned.
    program = _program(tmp_path, "G0 X0 Y-12.7 Z5\nG1 Z-14 F100\nG1 X400\nG1 Y-6.85\nG1 X0\nG1 Y-6.35\nG1 X400\nG0 Z5\n")
    kwargs = {"axis": "Y", "raw": -12.7, "span": 200.0, "below_z": 0.0, "max_step": 6.0, "direction": 1.0}
    assert _gcode.check_side_passes(program, final=-6.35, **kwargs) == []
    findings = _gcode.check_side_passes(program, final=-6.35, finish=0.254, **kwargs)
    assert [f.detail for f in findings] == ["Y -6.350 removes 0.500 > 0.254"]


def test_side_pass_deeper_than_the_measured_stepdown_is_caught(tmp_path):
    # The edge settings hold only within 7.62 mm deep (dechatter v11): one
    # 14.732 mm level fails, two even 7.366 mm levels pass.
    kwargs = {"axis": "Y", "final": -6.35, "raw": -10.0, "max_step": 4.1, "direction": 1.0,
              "span": 200.0, "below_z": 0.0, "max_stepdown": 7.62}
    one = _program(tmp_path, "G0 X0 Y-6.35 Z5\nG1 Z-14.732 F100\nG1 X400\nG0 Z5\n")
    assert [f.detail for f in _gcode.check_side_passes(one, **kwargs)] == ["Z -14.732 steps down 14.732 > 7.620"]
    two = _program(tmp_path, "G0 X0 Y-6.35 Z5\nG1 Z-7.366 F100\nG1 X400\nG0 Z5\nG0 X0\nG1 Z-14.732\nG1 X400\nG0 Z5\n")
    assert _gcode.check_side_passes(two, **kwargs) == []


def test_rapid_after_a_machine_retract_keeps_its_motion(tmp_path):
    # A G0 set on a machine-coordinate retract (G53) stays modal after a G1 cut,
    # and the Grbl post's G28 G91 Z0 / G90 pair leaves absolute mode. A rapid
    # straight into the stock from that unknown start, in one block or split
    # over several, is still caught.
    for descent in ("X30 Y5 Z-2", "X30 Y5\nZ5\nZ-2"):
        text = f"G0 X10 Y5 Z5\nG1 Z-1 F100\nG90 G53 G0 Z0\nG28 G91 Z0\nG90\n{descent}\n"
        findings = _gcode.check_rapids_clear(_program(tmp_path, text), 0.0)
        assert [f.check for f in findings] == ["rapid"], descent


def test_bare_home_forgets_every_axis(tmp_path):
    # A bare G28 homes every axis, so the G0 X/Y move after it is not a rapid at
    # the pre-home depth Z-3 (which the stale position would report).
    program = _program(tmp_path, "G0 X10 Y5 Z5\nG1 Z-3 F100\nG28\nG0 X40 Y5\n")
    assert _gcode.check_rapids_clear(program, 0.0, [(10.0, 5.0)]) == []


def test_incremental_part_moves_are_refused(tmp_path):
    with pytest.raises(ValueError, match="G91"):
        _program(tmp_path, "G0 X0 Y0 Z5\nG91\nG1 X10 F100\n")


def test_event_stream_replies_decode_to_their_response():
    from _fusion_mcp import _decode

    body = 'event: message\ndata: {"jsonrpc": "2.0", "method": "notifications/progress"}\n\nevent: message\ndata: {"jsonrpc": "2.0", "id": 3, "result": {"ok": 1}}\n\n'
    assert _decode(body, "text/event-stream") == {"jsonrpc": "2.0", "id": 3, "result": {"ok": 1}}
    with pytest.raises(FusionError):
        _decode("event: ping\n\n", "text/event-stream")


def test_lateral_feed_below_the_stock_top_is_caught(tmp_path):
    # A G1 link between two holes at Z-1 drags the drill through the part; a G0
    # check alone passes it (Codjiflo round 3 on #2832).
    text = "G0 X10 Y5 Z5\nG1 Z-3 F100\nG1 Z-1\nG1 X40\nG1 Z-3\nG0 Z5\n"
    program = _program(tmp_path, text)
    assert _gcode.check_rapids_clear(program, 0.0, [(10.0, 5.0), (40.0, 5.0)]) == []
    assert [f.check for f in _gcode.check_vertical_below_top(program, 0.0)] == ["lateral"]
