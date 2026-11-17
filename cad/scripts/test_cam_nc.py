"""CAM driver, recipe frame, posted-G-code checks and cycle times, without
FreeCAD (the end-to-end post through FreeCAD is ``test_cam_nc_freecad.py``).

The G-code cases are the errors CAM produced with valid-looking toolpaths
while the base-bar programs were first written (2026-11-16): a spot drill
measured from the counterbore floor, a feed height below the stock top, a slot
cut from the outside, and an oversized radial step; and the speed losses the
FreeCAD cutover removed: feed moves through the air above the stock, one-way
edge passes with full-length returns, one-way facing.
"""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _gcode
import _process_plans
import cam_nc

STEM = "ch_rocker_arm_tl_oblique_base_bar"


def _program(tmp_path: Path, text: str) -> _gcode.Program:
    path = tmp_path / "p.nc"
    path.write_text(text, encoding="utf-8")
    return _gcode.read_program(path)


def test_silent_freecad_output_is_a_failure():
    # freecadcmd exits 0 even when its script raised: only the marker line counts.
    with pytest.raises(cam_nc.FreeCadError):
        cam_nc.parse_result("FreeCAD 1.1.4\n")
    with pytest.raises(cam_nc.FreeCadError, match="boom"):
        cam_nc.parse_result(f"{cam_nc.RESULT_MARKER}{{\"error\": \"Traceback: boom\"}}\n")
    assert cam_nc.parse_result(f"noise\n{cam_nc.RESULT_MARKER}{{\"files\": []}}\n") == {"files": []}


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
    # The envelope's ends are the cutter-centre arcs' apexes, e = 0.381 past the arc centres.
    assert slots[0]["y"] == pytest.approx((-53.721, -48.895))


def test_slots_plunge_at_the_corner_nearest_their_jack():
    # Plan S3: largest X (S1 .885 in, S2 15.365 in), and the Y end nearer the
    # slot's jack (left jack Y -4.4 in, right jack Y -1.8 in).
    items = _context()["slots"]["items"]
    assert [s["plunge"] for s in items] == [pytest.approx([22.465, -53.34]), pytest.approx([390.271, -124.46])]


def test_side_passes_step_evenly_without_air_passes():
    ctx = _context()
    edge, ends = ctx["edge"], ctx["ends"]
    # Edges: equal roughing steps within .100 in down to the .010 finish, then
    # the finish pass; the first step starts at the raw face, so none cuts air.
    offsets = edge["offsets"]
    steps = [a - b for a, b in zip([ctx["y_trim"], *offsets], offsets)]
    assert offsets[-2:] == pytest.approx([edge["finish"], 0.0])
    assert max(steps[:-1]) <= edge["step"] + 1e-9 and steps[-1] == pytest.approx(edge["finish"])
    assert min(steps) > 0
    # Two equal depth levels no deeper than 7.62 (plan): edges 7.366, ends 6.477.
    assert edge["levels"] == pytest.approx([-7.366, -14.732])
    assert ends["levels"] == pytest.approx([-6.477, -12.954])
    for side, step in (("left", ends["left_step"]), ("right", ends["right_step"])):
        stations = ends[side]
        assert stations[-1] == 0.0 and stations[0] < ctx["x_trim"]
        assert max(a - b for a, b in zip([ctx["x_trim"], *stations], stations)) <= step + 1e-9


def test_every_program_names_its_stock_top_for_the_air_check():
    ctx = _context()
    recipe = _cam_programs.load_recipe(STEM)
    tops = [program for program, check, _kw in recipe.expectations(ctx) if check == "air_feed"]
    assert sorted(tops) == sorted(name for name, _ops in recipe.PROGRAMS)


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
    program = _program(tmp_path, (
        "G0 X0 Y-12.7 Z5\nG1 Z-14 F100\nG1 X400\nG0 Z5\nG0 X0 Y-6.85\nG1 Z-14\nG1 X400\nG0 Z5\n"
        "G0 X0 Y-6.35\nG1 Z-14\nG1 X400\nG0 Z5\n"
    ))
    kwargs = {"axis": "Y", "raw": -12.7, "span": 200.0, "below_z": 0.0, "max_step": 6.0, "direction": 1.0}
    assert _gcode.check_side_passes(program, final=-6.35, **kwargs) == []
    findings = _gcode.check_side_passes(program, final=-6.35, finish=0.254, **kwargs)
    assert [f.detail for f in findings] == ["Y -6.350 removes 0.500 > 0.254"]


def test_a_climb_roughing_pass_is_caught(tmp_path):
    # The edge settings were measured conventional: a roughing pass cut the
    # other way (a zigzag edge) fails even when the final pass is right.
    program = _program(tmp_path, "G0 X0 Y-8 Z5\nG1 Z-7 F100\nG1 X400\nG1 Y-6.35\nG1 X0\nG0 Z5\nG0 X0\nG1 Z-7\nG1 X400\nG0 Z5\n")
    kwargs = {"axis": "Y", "final": -6.35, "raw": -9.0, "max_step": 2.0, "direction": 1.0, "span": 200.0, "below_z": 0.0}
    assert [f.detail for f in _gcode.check_side_passes(program, **kwargs)] == ["Y -6.350 Z -7.000: pass does not run +X"]


def test_side_pass_deeper_than_the_measured_stepdown_is_caught(tmp_path):
    # The edge settings hold only within 7.62 mm deep (dechatter v11): one
    # 14.732 mm level fails, two even 7.366 mm levels pass, and each station is
    # judged alone, so a roughing station's two levels cannot cover a finish
    # pass cut at full depth (Codjiflo on #2846).
    kwargs = {"axis": "Y", "final": -6.35, "raw": -10.0, "max_step": 4.1, "direction": 1.0,
              "span": 200.0, "below_z": 0.0, "max_stepdown": 7.62}
    one = _program(tmp_path, "G0 X0 Y-6.35 Z5\nG1 Z-14.732 F100\nG1 X400\nG0 Z5\n")
    assert [f.detail for f in _gcode.check_side_passes(one, **kwargs)] == ["Y -6.350: Z -14.732 steps down 14.732 > 7.620"]
    two = _program(tmp_path, "G0 X0 Y-6.35 Z5\nG1 Z-7.366 F100\nG1 X400\nG0 Z5\nG0 X0\nG1 Z-14.732\nG1 X400\nG0 Z5\n")
    assert _gcode.check_side_passes(two, **kwargs) == []
    rough_levels_finish_full = _program(tmp_path, (
        "G0 X0 Y-8 Z5\nG1 Z-7.366 F100\nG1 X400\nG0 Z5\nG0 X0\nG1 Z-14.732\nG1 X400\nG0 Z5\n"
        "G0 X0 Y-6.35\nG1 Z-14.732\nG1 X400\nG0 Z5\n"
    ))
    findings = _gcode.check_side_passes(rough_levels_finish_full, **kwargs)
    assert [f.detail for f in findings] == ["Y -6.350: Z -14.732 steps down 14.732 > 7.620"]


def test_rapid_after_a_machine_retract_keeps_its_motion(tmp_path):
    # A G0 set on a machine-coordinate retract (G53) stays modal after a G1 cut,
    # and a G28 G91 Z0 / G90 pair leaves absolute mode. A rapid straight into
    # the stock from that unknown start, in one block or split over several,
    # is still caught.
    for descent in ("X30 Y5 Z-2", "X30 Y5\nZ5\nZ-2"):
        text = f"G0 X10 Y5 Z5\nG1 Z-1 F100\nG90 G53 G0 Z0\nG28 G91 Z0\nG90\n{descent}\n"
        findings = _gcode.check_rapids_clear(_program(tmp_path, text), 0.0)
        assert [f.check for f in findings] == ["rapid"], descent


def test_bare_home_forgets_every_axis(tmp_path):
    # A bare G28 homes every axis, so the G0 X/Y move after it is not a rapid at
    # the pre-home depth Z-3 (which the stale position would report).
    program = _program(tmp_path, "G0 X10 Y5 Z5\nG1 Z-3 F100\nG28\nG0 X40 Y5\n")
    assert _gcode.check_rapids_clear(program, 0.0, [(10.0, 5.0)]) == []


def test_incremental_moves_and_radius_arcs_are_refused(tmp_path):
    with pytest.raises(ValueError, match="G91"):
        _program(tmp_path, "G0 X0 Y0 Z5\nG91\nG1 X10 F100\n")
    with pytest.raises(ValueError, match="R-form"):
        _program(tmp_path, "G0 X0 Y0 Z5\nG1 Z-1 F100\nG2 X10 Y0 R5\n")


def test_lateral_feed_below_the_stock_top_is_caught(tmp_path):
    # A G1 link between two holes at Z-1 drags the drill through the part; a G0
    # check alone passes it (Codjiflo round 3 on #2832).
    text = "G0 X10 Y5 Z5\nG1 Z-3 F100\nG1 Z-1\nG1 X40\nG1 Z-3\nG0 Z5\n"
    program = _program(tmp_path, text)
    assert _gcode.check_rapids_clear(program, 0.0, [(10.0, 5.0), (40.0, 5.0)]) == []
    assert [f.check for f in _gcode.check_vertical_below_top(program, 0.0)] == ["lateral"]


def test_arcs_measure_their_true_length_in_every_plane(tmp_path):
    # A clockwise quarter in XY, Fusion's G18 ramp-in quarter (from the base-bar
    # face program), a full circle and a helix.
    program = _program(tmp_path, (
        "G0 X0 Y10 Z5\nG1 Z0 F100\nG2 X10 Y0 I0 J-10\n"
        "G0 X-13.875 Z14.224\nG18 G2 X-11.97 Z12.319 I1.905 K0\n"
        "G17 G0 X10 Y0 Z0\nG3 X10 Y0 I-10 J0\n"
        "G2 X10 Y0 Z-3 I-10 J0\n"
    ))
    arcs = [m.length for m in program.cutting if m.centre is not None]
    assert arcs == pytest.approx([5 * math.pi, 1.905 * math.pi / 2, 20 * math.pi, math.hypot(20 * math.pi, 3)])


def test_cycle_time_splits_cutting_air_and_rapid(tmp_path):
    # 10 mm rapid; a 10 mm plunge from Z5 to Z-5 at 100 mm/min, half above the
    # top; a 100 mm cut at 200; a 50 mm feed move at Z5 (air) at 200.
    program = _program(tmp_path, "G0 X0 Y0 Z5\nG0 X10\nG1 Z-5 F100\nG1 X110 F200\nG1 Z5\nG1 X60\n")
    t = _gcode.cycle_time(program, rapid_mm_min=1000.0, z_top=0.0)
    assert t.rapid == pytest.approx(10 / 1000)
    assert t.cutting == pytest.approx(5 / 100 + 100 / 200 + 5 / 200)
    assert t.air == pytest.approx(5 / 100 + 5 / 200 + 50 / 200)
    assert t.total == pytest.approx(t.cutting + t.air + t.rapid)


def test_feed_through_the_air_above_the_stock_is_caught(tmp_path):
    # Fusion Personal's S2 links: a 444 mm G1 return at Z5 above the blank.
    program = _program(tmp_path, "G0 X0 Y0 Z5\nG1 Z-7 F400\nG1 X444\nG1 Z5\nG1 X0\nG1 Z-7\n")
    findings = _gcode.check_air_feed(program, 0.0)
    assert [f.check for f in findings] == ["air_feed"]
    assert "444.000 mm" in findings[0].detail
    # A plunge that crosses the top is never wholly above it.
    assert _gcode.check_air_feed(_program(tmp_path, "G0 X0 Y0 Z3\nG1 Z-7 F60\nG1 X444 F400\nG0 Z60\n"), 0.0) == []


def test_full_length_return_is_caught(tmp_path):
    one_way = _program(tmp_path, "G0 X0 Y-8 Z5\nG1 Z-7 F400\nG1 X444\nG0 Z60\nG0 X0\nG0 Z5\nG1 Z-7\nG1 X444\nG0 Z60\n")
    assert [f.check for f in _gcode.check_no_return(one_way, "X", 220.0)] == ["return"]
    alternating = _program(tmp_path, "G0 X0 Y-8 Z5\nG1 Z-7 F400\nG1 X444\nG0 Z60\nG0 Y148\nG0 Z5\nG1 Z-7\nG1 X0\nG0 Z60\n")
    assert _gcode.check_no_return(alternating, "X", 220.0) == []


def test_face_passes_must_zigzag_within_the_stepover_and_cover_the_face(tmp_path):
    kwargs = {"z": 12.0, "y": (-140.0, 0.0), "max_stepover": 15.24, "radius": 9.525, "span": 200.0}
    rows = [f"{-130.475 + 120.95 * i / 8:.4f}" for i in range(9)]  # cutter covers -140 .. 0 exactly
    zigzag = "G0 X-30 Y-130.5 Z20\nG1 Z12 F100\n" + "".join(
        f"G1 X{470 if i % 2 == 0 else -30}\nG1 Y{rows[i + 1]}\n" for i in range(8)) + "G1 X470\nG0 Z20\n"
    assert _gcode.check_face_passes(_program(tmp_path, zigzag), **kwargs) == []
    one_way = "G0 X-30 Y-130.5 Z20\nG1 Z12 F100\nG1 X470\nG0 Z20\nG0 X-30 Y-115.5\nG1 Z12\nG1 X470\nG0 Z20\n"
    details = [f.detail for f in _gcode.check_face_passes(_program(tmp_path, one_way), **kwargs)]
    assert details[0] == "passes at Y -130.500 and Y -115.500 run the same way"
    assert details[1].startswith("cutter covers")
    wide = "G0 X-30 Y-130.5 Z20\nG1 Z12 F100\nG1 X470\nG1 Y-110\nG1 X-30\nG0 Z20\n"
    assert any(f.detail.startswith("stepover 20.500") for f in _gcode.check_face_passes(_program(tmp_path, wide), **kwargs))


def test_freecad_older_than_1_1_is_refused(tmp_path, monkeypatch):
    exe = tmp_path / "freecadcmd.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setenv(cam_nc.FREECAD_ENV, str(exe))
    monkeypatch.setattr(cam_nc, "freecad_version", lambda _path: (1, 0))
    with pytest.raises(cam_nc.FreeCadError, match="needs 1.1"):
        cam_nc.resolve_freecadcmd()
    monkeypatch.setattr(cam_nc, "freecad_version", lambda _path: (1, 1))
    assert cam_nc.resolve_freecadcmd() == exe

