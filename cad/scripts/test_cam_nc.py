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
    # S3: ZERO EDGE is WCS Y0 at the back jaw and the bar lies at -Y, so the
    # drawing's bracket ordinates (54.909, 12.909 from ZERO EDGE) appear negated.
    ctx = _context()
    assert [c for xy in ctx["bracket"]["centres"] for c in xy] == pytest.approx([47.484, -54.909, 428.0, -12.909])
    assert [y for _x, y in ctx["rail"]["centres"]] == pytest.approx([-88.9] * 4)
    recipe = _cam_programs.load_recipe(STEM)
    slots = [kw for program, check, kw in recipe.expectations(ctx) if check == "bounds" and program == "BB02_S3_bar1@2"]
    assert [s["x"] for s in slots] == [pytest.approx((21.703, 22.465)), pytest.approx((389.509, 390.271))]
    # The envelope's ends are the cutter-centre arcs' apexes, e = 0.381 past the arc centres.
    assert slots[0]["y"] == pytest.approx((-53.721, -48.895))
    # Z0 is the parallels' top, so the slots cut through to the breakthrough
    # below Z0 and their stock top is the faced top, Z = finished thickness.
    assert slots[0]["z_top"] == pytest.approx(11.938)


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
    # A one-tool file names its stock top once; a file with M6 tool changes
    # names it for every tool section (the top drops at the side-2 face).
    ctx = _context()
    recipe = _cam_programs.load_recipe(STEM)
    tops = [program for program, check, _kw in recipe.expectations(ctx) if check == "air_feed"]
    expected = []
    for name, _ops in recipe.PROGRAMS:
        changes = ctx["tool_changes"].get(name)
        expected += [name] if changes is None else [f"{name}@{k}" for k in range(len(changes) + 1)]
    assert sorted(tops) == sorted(expected)


def test_one_file_per_bar_with_its_tools_speeds_and_stops():
    # Main relaying the owner, 2026-11-16: one file per bar, M6 tool changes;
    # bar 2 has no bracket holes. The Tri Fly faces at 2500 (both sides, the
    # flip stop between), the probe and the tap run with the spindle off, the
    # ends take the measured 2250 and the slots 1250, an M0 between them.
    ctx = _context()
    recipe = _cam_programs.load_recipe(STEM)
    expected = {(program, check): kw for program, check, kw in recipe.expectations(ctx)}
    assert expected[("BB02_S3_bar1", "tool_changes")]["tools"] == [8, 1, 3, 4, 5, 6, 7]
    assert expected[("BB03_S3_bar2", "tool_changes")]["tools"] == [8, 1, 3, 4, 6]
    assert expected[("BB02_S3_bar1", "spindle")]["rpm"] == [[2500], [], [2250, 1250], [2800], [2800], [2800], [], [2000]]
    assert expected[("BB03_S3_bar2", "spindle")]["rpm"] == [[2500], [], [2250, 1250], [2800], [2800], []]
    # The flip, the ends-to-slots speed change and one stop per rail hole tapped.
    assert expected[("BB02_S3_bar1", "pauses")]["count"] == 2 + len(ctx["rail"]["centres"])
    assert expected[("BB02_S3_bar1@0", "pauses")] == {"z_top": pytest.approx(ctx["blank_max"]), "count": 1, "spindle_off": True}
    assert expected[("BB02_S3_bar1@1", "probe_zero")]["value"] == pytest.approx(-(ctx["x_trim"] + 1.0))
    assert ctx["ends"]["feed"] == pytest.approx(400.05)


def test_side_1_faces_where_the_whole_blank_band_cleans_up():
    # Side 1 faces at a fixed Z, half the nominal allowance off; a band whose
    # thin end would not clean up there, or whose thick end cuts past the
    # planned depth of cut, is refused before anything is posted.
    ctx = _context()
    assert ctx["side1"] == pytest.approx((11.938 + 12.7) / 2)
    recipe = _cam_programs.load_recipe(STEM)
    for key, value, match in (("blank_thickness_min_in", 0.488, "may not clean up"),
                              ("blank_thickness_max_in", 0.510, "past the 'side 1 face'")):
        with _process_plans.plan_path(STEM).open("rb") as plan, _process_plans.SHOP_PATH.open("rb") as shop:
            data, shop_data = tomllib.load(plan), tomllib.load(shop)
        data["parameters"][key] = value
        with pytest.raises(ValueError, match=match):
            recipe.context(_features(), data, shop_data, "bar.STEP")


def test_m0_stops_need_a_retract_and_an_operator_comment(tmp_path):
    good = "M3 S2250\nG0 X0 Y0 Z5\nG1 Z-1 F100\nG0 Z5\n(PAUSE: SET SPINDLE TO 1250 RPM, THEN CYCLE START)\nM0\nM3 S1250\nG1 Z-1\n"
    program = _program(tmp_path, good)
    assert _gcode.check_pauses(program, 0.0, 1) == []
    assert _gcode.check_spindle(program, [[2250, 1250]]) == []
    assert [f.check for f in _gcode.check_spindle(program, 2250)] == ["spindle"]
    low = good.replace("G0 Z5\n(PAUSE", "(PAUSE")
    assert any("not retracted" in f.detail for f in _gcode.check_pauses(_program(tmp_path, low), 0.0, 1))
    silent = good.replace("(PAUSE: SET SPINDLE TO 1250 RPM, THEN CYCLE START)\n", "")
    assert any("operator comment" in f.detail for f in _gcode.check_pauses(_program(tmp_path, silent), 0.0, 1))
    assert [f.detail for f in _gcode.check_pauses(program, 0.0, 0)] == ["1 M0 stops, expected 0"]
    # The speed changes at the stop with the spindle running: refused where the
    # operator's hands go to the bar or tool.
    assert any("spindle on" in f.detail for f in _gcode.check_pauses(program, 0.0, 1, spindle_off=True))
    assert [f.check for f in _gcode.check_pauses(program, 0.0, 1, at=[(9.0, 0.0)])] == ["pauses"]
    assert _gcode.check_pauses(program, 0.0, 1, at=[(0.0, 0.0)]) == []


def test_cncjs_msg_is_the_stop_comment_and_other_directives_are_refused(tmp_path):
    # CNCjs strips comments before sending and shows a %msg at the next M0.
    program = _program(tmp_path, "G0 X0 Y0 Z5\nM5\n%msg PAUSE: FLIP THE BAR, THEN CYCLE START\nM0\n")
    assert program.pauses[0].comment == "PAUSE: FLIP THE BAR, THEN CYCLE START"
    assert _gcode.check_pauses(program, 0.0, 1, spindle_off=True) == []
    with pytest.raises(ValueError, match="%msg"):
        _program(tmp_path, "G0 X0 Y0 Z5\n%wait\n")


def test_tool_changes_split_the_program_into_tool_sections(tmp_path):
    # T2 loaded before the file runs; M6 T1 and M6 T3 each start a section.
    text = (
        "M3 S2500\nG0 X0 Y0 Z20\nG1 Z10 F100\nG1 X50\nG0 Z20\n"
        "M5\n(TOOL CHANGE: T1 END MILL, SET SPINDLE TO 2250 RPM)\nM6 T1\nM3 S2250\nG0 X60 Y0 Z20\nG1 Z5 F100\nG0 Z20\n"
        "M5\n(TOOL CHANGE: T3 CENTRE DRILL, SET SPINDLE TO 2800 RPM)\nM6 T3\nM3 S2800\nG0 X70 Y0 Z20\nG1 Z8 F100\nG0 Z20\n"
    )
    program = _program(tmp_path, text)
    sections = program.tool_sections()
    assert [s.name for s in sections] == ["p.nc@0", "p.nc@1", "p.nc@2"]
    assert [len(s.moves) for s in sections] == [4, 3, 3]
    assert _gcode.check_tool_changes(program, 12.0, [1, 3]) == []
    assert _gcode.check_spindle(program, [2500, 2250, 2800]) == []
    assert [f.detail for f in _gcode.check_tool_changes(program, 12.0, [1])] == ["M6 calls [1, 3], expected [1]"]
    # An M6 with the spindle running, without its comment or before a retract.
    hot = _program(tmp_path, text.replace("G0 Z20\nM5\n(TOOL CHANGE: T1 END MILL, SET SPINDLE TO 2250 RPM)\n", ""))
    details = " ".join(f.detail for f in _gcode.check_tool_changes(hot, 12.0, [1, 3]))
    assert "spindle on" in details and "operator comment" in details and "not retracted" in details
    # The new tool's first rapid across the stock below its top.
    low = _program(tmp_path, text.replace("M3 S2250\nG0 X60 Y0 Z20", "M3 S2250\nG0 Z8\nG0 X60 Y0"))
    assert any(f.detail.startswith("T1: G0 to X60.000") for f in _gcode.check_tool_changes(low, 12.0, [1, 3]))
    assert any("G28/G30/G53" in f.detail for f in _gcode.check_tool_changes(_program(tmp_path, text + "G53 G0 Z0\n"), 12.0, [1, 3]))


def test_probe_sets_one_work_zero_after_a_touch_along_its_axis(tmp_path):
    probe = (
        "G0 X0 Y0 Z20\nM5\n(TOOL CHANGE: T8 PROBE, SPINDLE OFF - PROBE IN)\nM6 T8\nG0 Z17\nG0 X-22 Y-70\n"
        "G38.3 Z6 F150\nG38.2 X19 F150\nG38.4 X-22 F150\nG38.2 X19 F50\nG10 L20 P1 X-2.5\nG38.4 X-22 F150\nG0 Z17\n"
    )
    program = _program(tmp_path, probe)
    assert [p.code for p in program.probes] == [38.3, 38.2, 38.4, 38.2, 10.0, 38.4]
    assert _gcode.check_probe_zero(program, "X", -2.5, 12.0) == []
    assert [f.check for f in _gcode.check_probe_zero(program, "X", -2.0, 12.0)] == ["probe"]
    # G10 after a move that is not a G38.2 touch along X.
    unprobed = probe.replace("G38.2 X19 F50\nG10", "G10")
    assert any("not straight after" in f.detail for f in _gcode.check_probe_zero(_program(tmp_path, unprobed), "X", -2.5, 12.0))
    spun = _program(tmp_path, probe.replace("G0 Z17\nG0 X-22", "M3 S1000\nG0 Z17\nG0 X-22"))
    assert any("spindle on" in f.detail for f in _gcode.check_probe_zero(spun, "X", -2.5, 12.0))
    # The probe's lateral move at the stock's height would hit the bar end.
    low = _program(tmp_path, probe.replace("G0 Z17\nG0 X-22 Y-70", "G0 Z5\nG0 X-22 Y-70"))
    assert any(f.detail.startswith("G0 to X-22.000") for f in _gcode.check_probe_zero(low, "X", -2.5, 12.0))
    with pytest.raises(ValueError, match="G10 L20 P1"):
        _program(tmp_path, "G10 L2 P1 X0\n")


def _equipment() -> dict:
    with (Path(__file__).resolve().parents[1] / "config" / "shop-equipment.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_setup_3_tools_fit_the_tool_setter_and_the_probe_has_a_holder():
    # CNCjs probes every M6 tool on the tool setter's 20 mm plate: each must
    # land on it; the 2 in Tri Fly cannot and is touched off by hand (it is
    # loaded before the file runs, never called by an M6). The probe's 6 mm
    # shank has no collet in the owned inch set: its holder is still to buy.
    equipment = _equipment()
    plate = equipment["fixtures"]["tool-setter-ets"]["plate_dia_mm"]
    ctx = _context()
    called = {n for tools in ctx["tool_changes"].values() for n in tools}
    n, t = ctx["numbers"], ctx["tools"]
    # What lands on the plate: the cutter, the tap's 8-32 major, the probe's 2 mm ball.
    tips = {n["em-half"]: t["em_half"], n["spot"]: t["centre_drill"]["body_mm"], n["rail-drill"]: t["rail_drill"],
            n["bracket-drill"]: t["bracket_drill"], n["tap"]: 0.164 * 25.4, n["counterbore"]: t["cbore"], n["probe"]: 2.0}
    assert called <= tips.keys() and max(tips[k] for k in called) <= plate
    assert ctx["face"]["dia"] > plate and ctx["numbers"]["face-mill"] not in called
    probe = equipment["gauges"]["touch-probe-diy0-tp05"]
    collets = equipment["holders"]["r8-collets-south-bend-sb1280"]
    assert probe["present"] and probe["shank_mm"] == 6.0 and "to buy" in probe["holder"]
    assert all(not size.endswith("mm") for size in collets["sizes_in"])


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


def _face(rows: list[float]) -> str:
    """Zigzag passes along X at ``rows`` (cutter-centre Y), in that order."""
    text = f"G0 X-30 Y{rows[0]} Z20\nG1 Z12 F100\n"
    for i, row in enumerate(rows):
        text += f"G1 Y{row}\nG1 X{470 if i % 2 == 0 else -30}\n"
    return text + "G0 Z20\n"


def test_face_passes_must_zigzag_within_the_engagement_and_cover_the_face(tmp_path):
    # Each pass may take at most the plan's radial width of uncut stock, the
    # first pass included: FreeCAD's MillFace cut its edge line first, nearly
    # full width, while its centres sat within the stepover.
    kwargs = {"z": 12.0, "y": (-140.0, 0.0), "max_engagement": 15.24, "radius": 9.525, "span": 200.0, "overhang": 0.5}
    # Ten 14 mm bites from Y0 down, the first cutter 4.475 below Y0, the last
    # reaching 0.5 past -140.
    rows = [9.525 - 14.0 * (k + 1) for k in range(9)] + [-131.025]
    assert _gcode.check_face_passes(_program(tmp_path, _face(rows)), **kwargs) == []
    edge_first = [-9.0] + [9.525 - 14.0 * (k + 1) for k in range(1, 9)] + [-131.025]
    details = [f.detail for f in _gcode.check_face_passes(_program(tmp_path, _face(edge_first)), **kwargs)]
    assert details == ["pass at Y -9.000 engages 18.525 > 15.240"]
    one_way = "G0 X-30 Y-130.5 Z20\nG1 Z12 F100\nG1 X470\nG0 Z20\nG0 X-30 Y-115.5\nG1 Z12\nG1 X470\nG0 Z20\n"
    details = [f.detail for f in _gcode.check_face_passes(_program(tmp_path, one_way), **kwargs)]
    assert details[0] == "passes at Y -130.500 and Y -115.500 run the same way"
    assert details[-1].startswith("cutter covers")
    # Bites within the engagement but a strip left uncut between two passes.
    gappy = rows[:4] + [rows[4] - 20.0] + [r - 20.0 for r in rows[5:]]
    assert any("clearing" in f.detail for f in _gcode.check_face_passes(_program(tmp_path, _face(gappy)), **kwargs))


def test_freecad_older_than_1_1_is_refused(tmp_path, monkeypatch):
    exe = tmp_path / "freecadcmd.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setenv(cam_nc.FREECAD_ENV, str(exe))
    monkeypatch.setattr(cam_nc, "freecad_version", lambda _path: (1, 0))
    with pytest.raises(cam_nc.FreeCadError, match="needs 1.1"):
        cam_nc.resolve_freecadcmd()
    monkeypatch.setattr(cam_nc, "freecad_version", lambda _path: (1, 1))
    assert cam_nc.resolve_freecadcmd() == exe

