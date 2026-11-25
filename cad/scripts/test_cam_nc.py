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
from pathlib import Path

import pytest

import _gcode
import cam_nc


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


def test_a_program_that_loads_its_first_tool_does_so_before_any_move(tmp_path):
    body = "M3 S2250\nG0 X0 Y0 Z20\nG1 Z5 F100\nG0 Z20\n"
    change = "M5\n%msg TOOL CHANGE: T1 END MILL, SET SPINDLE TO 2250 RPM\nM6 T1\n"
    loaded = _program(tmp_path, "G17 G90\nG21\nG54\n" + change + body)
    assert [s.name for s in loaded.tool_sections()] == ["p.nc@0"]
    assert _gcode.check_tool_changes(loaded, 12.0, [1], loads_first=True) == []
    # The same cut on whatever tool and length the previous file left.
    carried = _program(tmp_path, "G17 G90\nG21\nG54\n" + body)
    found = _gcode.check_tool_changes(carried, 12.0, [1], loads_first=True)
    assert [f.detail for f in found] == [
        "M6 calls [], expected [1]",
        "moves or spindle words before the first M6: the program runs on the previous tool's length",
    ]
    # A move before the load.
    early = _program(tmp_path, "G54\nG0 X0 Y0 Z20\n" + change + body)
    assert len(_gcode.check_tool_changes(early, 12.0, [1], loads_first=True)) == 1


_TAP_STOP = (
    "(SP03_tap_clamp_1)\n(T6 Fisher spring tap guide)\n(Begin preamble)\nG17 G90\nG21\nG54\n"
    "M5\n%msg TOOL CHANGE: T6 Fisher spring tap guide, SPINDLE STAYS OFF. NEXT: 4-40 TAP IN CLAMP HOLE 1\n"
    "M6 T6\nG53 G0 Z0.000\nG0 X25.400 Y-41.910\n(4-40 TAP IN CLAMP HOLE 1)\nM30\n"
)


@pytest.mark.parametrize(
    ("fault", "seeded", "detail"),
    [
        ("no retract", ("G53 G0 Z0.000\n", ""), "first motion is not a G53 G0 Z retract"),
        ("XY before the retract", ("G53 G0 Z0.000\nG0 X25.400 Y-41.910\n", "G0 X25.400 Y-41.910\nG53 G0 Z0.000\n"), "first motion is not a G53"),
        ("motion before the M6", ("M5\n", "G0 X0 Y0\nM5\n"), "motion before the M6"),
        ("a part-coordinate Z", ("(4-40", "G0 Z5\n(4-40"), "a Z move in part coordinates"),
        ("a feed move", ("G0 X25.400 Y-41.910\n", "G0 X25.400 Y-41.910 Z1\nG1 X26 Y-41.910 Z1 F100\n"), "only G0 in part coordinates"),
        ("an M0 stop", ("M30\n", "M0\nM30\n"), "an M0 holds the controller"),
        ("no M30", ("M30\n", "M2\n"), "last command is not M30"),
        ("the wrong hole", ("X25.400", "X26.400"), "expected over"),
        ("the spindle on", ("M6 T6\n", "M6 T6\nM3 S900\n"), "the spindle stays off"),
        ("a bare M3", ("M6 T6\n", "M6 T6\nM3\n"), "M3/M4 starts the spindle"),
        ("a bare G28", ("M30\n", "G28\nM30\n"), "G28/G30 moves the guide"),
        ("the wrong tool", ("M6 T6", "M6 T5"), "M6 calls [5]"),
    ],
)
def test_a_tap_stop_file_ends_idle_over_its_hole_after_a_machine_retract(tmp_path, fault, seeded, detail):
    good = _program(tmp_path, _TAP_STOP)
    assert _gcode.check_tap_stop(good, 6, (25.4, -41.91), 0.0) == []
    assert _TAP_STOP.count(seeded[0]) == 1, fault
    bad = _program(tmp_path, _TAP_STOP.replace(seeded[0], seeded[1]))
    found = [f.detail for f in _gcode.check_tap_stop(bad, 6, (25.4, -41.91), 0.0)]
    assert any(detail in f for f in found), (fault, found)


def test_text_left_outside_a_nested_comment_is_refused(tmp_path):
    nested = _TAP_STOP.replace("(4-40 TAP IN CLAMP HOLE 1)", "(4-40 TAP IN CLAMP HOLE 1 (TOP END): JOG Z DOWN)")
    with pytest.raises(ValueError, match="text outside a comment"):
        _program(tmp_path, nested)


def test_a_tap_stop_retract_must_reach_the_machine_top(tmp_path):
    low = _program(tmp_path, _TAP_STOP.replace("G53 G0 Z0.000", "G53 G0 Z-50.000"))
    found = [f.detail for f in _gcode.check_tap_stop(low, 6, (25.4, -41.91), 0.0)]
    assert found == ["the G53 retract names Z-50.000, below the machine top 0.000"]


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


# A 10 x 10 outline whose top edge is a minor arc about (5, -20), anticlockwise
# (conventional outside with a clockwise spindle), each element held to 0.05.
_OUTLINE = [
    {"name": "bottom", "start": (0.0, 0.0), "end": (10.0, 0.0), "tol": 0.05},
    {"name": "right", "start": (10.0, 0.0), "end": (10.0, 10.0), "tol": 0.05},
    {
        "name": "top",
        "start": (10.0, 10.0),
        "end": (0.0, 10.0),
        "centre": (5.0, -20.0),
        "tol": 0.05,
    },
    {"name": "left", "start": (0.0, 10.0), "end": (0.0, 0.0), "tol": 0.05},
]
# The top arc's outward normal at (10, 10).
_N = (5.0 / math.hypot(5.0, 30.0), 30.0 / math.hypot(5.0, 30.0))
_ONE_PASS = {
    "elements": _OUTLINE,
    "passes": [{"offset": 1.0, "levels": [-1.0, -2.0]}],
    "z_top": 0.0,
}


def _loop(z: float, r: float = 1.0) -> str:
    """One anticlockwise lap at cutter-centre offset ``r`` round ``_OUTLINE``,
    from and back to (5, -r), at depth ``z``; its corners are radius-r arcs."""
    nx, ny = _N
    return (
        f"G1 X5 Y{-r:g} Z{z} F100\nG1 X10 Y{-r:g}\nG3 X{10 + r:g} Y0 I0 J{r:g}\n"
        f"G1 X{10 + r:g} Y10\nG3 X{10 + r * nx:.4f} Y{10 + r * ny:.4f} I{-r:g} J0\n"
        f"G3 X{-r * nx:.4f} Y{10 + r * ny:.4f} I{-5 - r * nx:.4f} J{-30 - r * ny:.4f}\n"
        f"G3 X{-r:g} Y10 I{r * nx:.4f} J{-r * ny:.4f}\nG1 X{-r:g} Y0\n"
        f"G3 X0 Y{-r:g} I{r:g} J0\nG1 X5 Y{-r:g}\n"
    )


def _outline(tmp_path: Path, text: str, **kwargs) -> list[str]:
    return [
        f.detail
        for f in _gcode.check_outline(_program(tmp_path, text), **_ONE_PASS, **kwargs)
    ]


def test_outline_passes_hold_their_offset_direction_levels_and_coverage(tmp_path):
    good = "G0 X5 Y-1 Z5\n" + _loop(-1.0) + _loop(-2.0) + "G0 Z5\n"
    assert _outline(tmp_path, good) == []
    # The bottom run 0.2 mm into the part: a gouge, and that side left uncut.
    first = "G1 X5 Y-1 Z-2.0 F100\nG1 X10 Y-1\nG3 X11 Y0 I0 J1"
    gouge = good.replace(
        first, "G1 X5 Y-0.8 Z-2.0 F100\nG1 X10 Y-0.8\nG3 X11 Y0.2 I0 J1"
    )
    assert any(
        "off every pass offset" in d and "0.800 from bottom" in d
        for d in _outline(tmp_path, gouge)
    )
    # The second lap clockwise round the part (climb), on the same offset path.
    nx, ny = _N
    clockwise = (
        "G1 X5 Y-1 Z-2.0 F100\nG1 X0 Y-1\nG2 X-1 Y0 I0 J1\nG1 X-1 Y10\n"
        f"G2 X{-nx:.4f} Y{10 + ny:.4f} I1 J0\n"
        f"G2 X{10 + nx:.4f} Y{10 + ny:.4f} I{5 + nx:.4f} J{-30 - ny:.4f}\n"
        f"G2 X11 Y10 I{-nx:.4f} J{-ny:.4f}\nG1 X11 Y0\nG2 X10 Y-1 I-1 J0\nG1 X5 Y-1\n"
    )
    climb = _outline(tmp_path, "G0 X5 Y-1 Z5\n" + _loop(-1.0) + clockwise + "G0 Z5\n")
    assert len(climb) == 1 and "against the outline's way" in climb[0]
    # A level the plan does not list, and a listed level never cut.
    stray = _outline(tmp_path, "G0 X5 Y-1 Z5\n" + _loop(-1.0) + _loop(-1.5) + "G0 Z5\n")
    assert any("off the levels" in d for d in stray)
    assert any("uncut at Z-2.000" in d for d in stray)


def test_outline_passes_run_in_order_after_the_clearing(tmp_path):
    passes = [{"offset": 1.0, "levels": [-1.0]}, {"offset": 1.0, "levels": [-2.0]}]
    # Waste 4 from the bottom edge, cleared +X (the bottom's way) at Z-2.
    clear = "G0 X2 Y-4 Z5\nG1 Z-2 F100\nG1 X8\nG0 Z5\n"
    zone = [{"x": (1.0, 9.0), "levels": [-2.0]}]

    def check(text, clearing=zone):
        program = _program(tmp_path, text + "G0 Z5\n")
        found = _gcode.check_outline(
            program, _OUTLINE, passes, 0.0, clearing=clearing
        )
        return [f.detail for f in found]

    laps = "G0 X5 Y-1 Z5\n" + _loop(-1.0) + _loop(-2.0)
    assert check(clear + laps) == []
    assert any("off every pass offset" in d for d in check(clear + laps, ()))
    late = check(laps + clear)
    assert len(late) == 1 and "cut after a later pass" in late[0]
    swapped = check("G0 X5 Y-1 Z5\n" + _loop(-2.0) + _loop(-1.0))
    assert len(swapped) == 1 and "cut after a later pass" in swapped[0]


def test_a_lead_out_through_cleared_waste_is_not_clearing_after_a_pass(tmp_path):
    passes = [{"offset": 1.0, "levels": [-1.0]}, {"offset": 1.0, "levels": [-2.0]}]
    clear = "G0 X2 Y-4 Z5\nG1 Z-2 F100\nG1 X8\nG0 Z5\n"
    zone = [{"x": (1.0, 9.0), "levels": [-2.0]}]
    # After the last lap, back out from its offset into the cleared waste.
    text = clear + "G0 X5 Y-1 Z5\n" + _loop(-1.0) + _loop(-2.0) + "G1 Y-4\nG0 Z5\n"
    lead = [{"centre": (5.0, -4.0), "radius": 3.0, "levels": [-2.0]}]

    def check(leads=()):
        found = _gcode.check_outline(
            _program(tmp_path, text), _OUTLINE, passes, 0.0, clearing=zone, leads=leads
        )
        return [f.detail for f in found]

    late = check()
    assert len(late) == 1 and "cut after a later pass" in late[0]
    assert check(lead) == []


# One tab on the bottom edge, X4-6: its box spans the edge and the cutter
# centres at offset 1; the part's floor is the deepest level, Z-2.
_TAB = {
    "name": "bottom",
    "x": (4.0, 6.0),
    "y": (-2.0, 0.5),
    "top": -1.5,
    "floor": -2.0,
    "thickness": 0.5,
}


def _tabbed_loop(
    z: float,
    hops: tuple[tuple[float, float, float], ...] = ((4.0, 6.0, -1.5),),
    r: float = 1.0,
) -> str:
    """``_loop`` at depth ``z`` entered at (10, -r) after ``_loop``'s lap,
    lifting to each hop's Z over its X range on the bottom run."""
    nx, ny = _N
    bottom = "".join(f"G1 X{x0}\nG1 Z{hz}\nG1 X{x1}\nG1 Z{z}\n" for x0, x1, hz in hops)
    return (
        f"G1 X10 Y{-r:g} F100\nG1 Z{z}\nG3 X{10 + r:g} Y0 I0 J{r:g}\n"
        f"G1 X{10 + r:g} Y10\nG3 X{10 + r * nx:.4f} Y{10 + r * ny:.4f} I{-r:g} J0\n"
        f"G3 X{-r * nx:.4f} Y{10 + r * ny:.4f} I{-5 - r * nx:.4f} J{-30 - r * ny:.4f}\n"
        f"G3 X{-r:g} Y10 I{r * nx:.4f} J{-r * ny:.4f}\nG1 X{-r:g} Y0\n"
        f"G3 X0 Y{-r:g} I{r:g} J0\n{bottom}G1 X10 Y{-r:g}\n"
    )


def _tabs(tmp_path: Path, deep: str, tabs=(_TAB,)) -> list[str]:
    text = "G0 X5 Y-1 Z5\n" + _loop(-1.0) + deep + "G0 Z5\n"
    return _outline(tmp_path, text, tabs=list(tabs))


def test_a_tab_is_left_standing_at_its_top_over_its_floor(tmp_path):
    assert _tabs(tmp_path, _tabbed_loop(-2.0)) == []
    # The same file with no tab declared: the hop is off the levels and the
    # gap leaves the bottom edge uncut.
    undeclared = _tabs(tmp_path, _tabbed_loop(-2.0), ())
    assert any("off the levels" in d for d in undeclared)
    assert any("uncut at Z-2.000: bottom at X5.000" in d for d in undeclared)


@pytest.mark.parametrize(
    ("fault", "deep", "tab", "found"),
    [
        # Cut straight through: nothing hops, the cutter bites the tab.
        (
            "cut through",
            _loop(-2.0),
            _TAB,
            ["no pass hops it", "cutter centres below tab bottom's top"],
        ),
        # Hops above the top: the hop is off the levels and never at the top.
        (
            "hop high",
            _tabbed_loop(-2.0, ((4.0, 6.0, -1.2),)),
            _TAB,
            ["off the levels", "no pass hops it"],
        ),
        # Hops below the top: a thinner tab than declared.
        (
            "hop low",
            _tabbed_loop(-2.0, ((4.0, 6.0, -1.8),)),
            _TAB,
            ["off the levels", "cutter centres below"],
        ),
        # A second hop where no tab is declared, at the tab's top.
        (
            "stray hop",
            _tabbed_loop(-2.0, ((4.0, 6.0, -1.5), (7.5, 9.5, -1.5))),
            _TAB,
            ["off the levels", "uncut at Z-2.000: bottom at X8.000"],
        ),
        # The recipe's thickness differs from top less floor.
        (
            "thickness",
            _tabbed_loop(-2.0),
            {**_TAB, "thickness": 0.4},
            ["is 0.500 thick, the recipe's 0.400"],
        ),
        # No level reaches the floor: the part never breaks free elsewhere.
        (
            "floor",
            _tabbed_loop(-2.0),
            {**_TAB, "floor": -2.5, "thickness": 1.0},
            ["no level reaches its floor Z-2.500"],
        ),
        # The box beside the path holds no outline and is never hopped.
        (
            "off the outline",
            _tabbed_loop(-2.0),
            {**_TAB, "y": (-5.0, -3.0)},
            ["its box holds no outline", "no pass hops it", "off the levels"],
        ),
        # The box at X2-3.5, the hop at X4-6: the cut runs through the box.
        (
            "moved",
            _tabbed_loop(-2.0),
            {**_TAB, "x": (2.0, 3.5)},
            ["no pass hops it", "cutter centres below", "off the levels"],
        ),
        # A plunge to depth inside the box between two hops.
        (
            "plunge",
            _tabbed_loop(-2.0, ((4.0, 5.0, -1.5), (5.0, 6.0, -1.5))),
            _TAB,
            ["cutter centres below tab bottom's top"],
        ),
        # The drop to depth comes 0.1 mm inside the box's exit edge.
        (
            "early drop",
            _tabbed_loop(-2.0, ((4.0, 5.9, -1.5),)),
            _TAB,
            ["cutter centres below tab bottom's top"],
        ),
    ],
)
def test_a_tab_fault_is_caught(tmp_path, fault, deep, tab, found):
    details = _tabs(tmp_path, deep, (tab,))
    for text in found:
        assert any(text in d for d in details), (fault, text, details)


def test_every_declared_tab_must_stand(tmp_path):
    second = {**_TAB, "name": "right", "x": (10.5, 11.5), "y": (3.0, 5.0)}
    details = _tabs(tmp_path, _tabbed_loop(-2.0), (_TAB, second))
    assert any("tab right: no pass hops it" in d for d in details)
    assert any("cutter centres below tab right's top" in d for d in details)
    assert not any("tab bottom" in d for d in details)


@pytest.mark.parametrize(
    ("box_y", "found"),
    [
        # The box spans both passes' paths and both hop it.
        ((-2.5, 0.5), []),
        # The box spans only the finishing path: the roughing pass, offset 2,
        # cuts across the tab outside the box and never hops it.
        ((-1.5, 0.5), ["tab bottom: the offset-2.000 pass, cut below its top"]),
    ],
)
def test_every_pass_must_hop_the_tab(tmp_path, box_y, found):
    passes = [{"offset": 2.0, "levels": [-2.0]}, {"offset": 1.0, "levels": [-2.0]}]
    if box_y[0] < -2.0:
        rough = "G0 X10 Y-2 Z5\n" + _tabbed_loop(-2.0, r=2.0)
    else:
        rough = "G0 X5 Y-2 Z5\n" + _loop(-2.0, r=2.0)
    finish = "G0 Z5\nG0 X10 Y-1\n" + _tabbed_loop(-2.0) + "G0 Z5\n"
    program = _program(tmp_path, rough + finish)
    tab = {**_TAB, "y": box_y}
    checked = _gcode.check_outline(program, _OUTLINE, passes, 0.0, tabs=[tab])
    details = [f.detail for f in checked]
    assert len(details) == len(found), details
    for text in found:
        assert any(text in d for d in details), (text, details)


def test_cleared_waste_is_swept_at_depth(tmp_path):
    program = _program(tmp_path, "G0 X0 Y-4 Z5\nG1 Z-2 F100\nG1 X10\nG0 Z5\n")
    assert _gcode.check_cleared(program, [(5.0, -4.5), (10.0, -3.0)], 1.0, -2.0) == []
    found = _gcode.check_cleared(program, [(5.0, -5.5), (5.0, -4.0)], 1.0, -2.0)
    assert [f.detail for f in found] == [
        "1 points no cut at Z-2.000 clears: X5.000 Y-5.500"
    ]
    assert _gcode.check_cleared(program, [(5.0, -4.0)], 1.0, -1.0) != []


def test_keep_out_catches_the_cutter_entering_a_fixture_below_its_top(tmp_path):
    fence = {"name": "fence", "x": (0.0, 10.0), "y": (0.0, 5.0), "z_top": 2.0}
    flange = {"name": "flange", "centre": (20.0, -5.0), "radius": 3.0, "z_top": 6.0}

    def hits(text):
        found = _gcode.check_keep_out(
            _program(tmp_path, text), 1.0, boxes=[fence], circles=[flange]
        )
        return [f.detail.split(" into ")[1].split(":")[0] for f in found]

    # Beside the fence and the flange by more than the cutter radius, then
    # over both above their tops.
    clear = (
        "G0 X5 Y-2 Z5\nG1 Z1 F100\nG1 X12\nG0 Z7\nG0 X15 Y-9.5\nG1 Z1\nG1 X25\n"
        "G0 Z7\nG0 X20 Y-5\nG0 X5 Y2\n"
    )
    assert hits(clear) == []
    assert hits("G0 X5 Y-0.5 Z5\nG0 Z1\nG1 X6 F100\n") == ["fence"]
    assert hits("G0 X20 Y-1.5 Z7\nG0 Z5\n") == ["flange"]


def test_keep_out_band_catches_a_tool_part_crossing_an_overhang(tmp_path):
    # A plate overhanging its support from Z0 to Z6: a part of the tool
    # under it misses it, one through its band does not.
    ledge = {"name": "ledge", "x": (0.0, 10.0), "y": (0.0, 5.0), "z_top": 6.0, "z_bottom": 0.0}

    def hits(text):
        found = _gcode.check_keep_out(_program(tmp_path, text), 1.0, boxes=[ledge])
        return [f.detail.split(" into ")[1].split(":")[0] for f in found]

    assert hits("G0 X5 Y-5 Z-3\nG1 Y2 F100\nG0 Z-3\nG1 Y-5\nG0 Z8\nG0 Y2\n") == []
    assert hits("G0 X5 Y-5 Z3\nG1 Y2 F100\n") == ["ledge"]
    # Straight down through the band, no sampled point inside it.
    assert hits("G0 X5 Y2 Z8\nG0 Z-3\n") == ["ledge"]
    # A steep diagonal through the band, in reach at its start, out at its end.
    assert hits("G0 X5 Y5.8 Z8\nG0 Y6.05 Z-3\n") == ["ledge"]


_JAW = {"name": "fixed jaw", "x": (0.0, 20.0), "y": (0.0, 25.4), "z_top": 6.0}


def test_jaw_clearance_floor_passes_a_cutter_clear_of_the_jaw(tmp_path):
    # A 1/2 in end mill's pass past the jaw face, 1.2 mm over the jaw's top.
    program = _program(tmp_path, "G0 X5 Y-10 Z12\nG0 Z7.2\nG1 Y3 F500\nG0 Z12\n")
    assert _gcode.check_keep_out(program, 6.35, boxes=[_JAW], clearance=1.0) == []


def test_jaw_clearance_floor_catches_a_cutter_0_5_mm_over_the_jaw(tmp_path):
    program = _program(tmp_path, "G0 X5 Y-10 Z12\nG0 Z6.5\nG1 Y3 F500\nG0 Z12\n")
    found = _gcode.check_keep_out(program, 6.35, boxes=[_JAW], clearance=1.0)
    assert [(f.program, f.check) for f in found] == [("p.nc", "jaw_clearance")]
    assert "least 0.500 mm (0.020 in) at line 3" in found[0].detail
    # Without the floor the same pass is clear: it never goes below the top.
    assert _gcode.check_keep_out(program, 6.35, boxes=[_JAW]) == []
    # Supports beside the jaw and stock between the jaws are not jaws.
    for name in ("fixed-jaw parallel", "fixed-jaw stack", "the bars between the jaws", "vise bed"):
        assert not _gcode.is_jaw_shape(name), name
        other = {**_JAW, "name": name}
        assert _gcode.check_keep_out(program, 6.35, boxes=[other], clearance=1.0) == []
    for name in ("moving jaw", "jaw", "toe clamp"):
        assert _gcode.is_jaw_shape(name), name


# Every keep-out shape name the posted recipes declare with "jaw", "clamp" or
# "strap" in it (census of every cam.py's keep_out checks, 2026-11-25; the
# arbor recipes' per-part copies once, with their part). The jaws, clamps and
# straps keep the floor; the supports, the vise body and the stock do not.
_FLEET_JAWS = (
    "fixed jaw",
    "moving jaw",
    "fixed jaw (the arbor's body above the saw)",
    "moving jaw (the arbor's cap below the saw, proved in air)",
    "fixed jaw (the arbor's cap and screw below the saw)",
    "moving jaw (the cap's screw head)",
    "left clamp",
    "middle clamp",
    "waste clamp",
    "left step clamps",
    "right step clamps",
    "step clamp 1",
    "step clamp 4",
    "plate strap left",
    "plate strap right",
    "remainder strap left",
    "remainder strap right",
)
_FLEET_NOT_JAWS = (
    "fixed-jaw parallel",
    "fixed-jaw parallels",
    "moving-jaw parallel",
    "moving-jaw parallels",
    "fixed-jaw stack",
    "moving-jaw stack",
    "moving-jaw stack (the arbor's body above the saw)",
    "fixed-jaw stack (the arbor's cap and screw below the saw, proved in air)",
    "stack at the fixed jaw",
    "stacks at the fixed jaw",
    "stacks at the moving jaw",
    "the bars between the jaws",
    "the bars between the jaws (the cap's screw head)",
    "the vise past the plate",
    "the vise past the plate (the arbor's body above the saw)",
    "vise bed",
    "plate block left",
    "remainder block right",
)


@pytest.mark.parametrize("name", _FLEET_JAWS)
def test_every_fleet_jaw_clamp_and_strap_keeps_the_floor(name):
    assert _gcode.is_jaw_shape(name)


@pytest.mark.parametrize("name", _FLEET_NOT_JAWS)
def test_fleet_supports_vise_body_and_stock_do_not(name):
    assert not _gcode.is_jaw_shape(name)


def test_verify_applies_the_shop_floor_and_reads_the_known_list(tmp_path):
    assert cam_nc.jaw_clearance_min_mm() == 1.0
    (tmp_path / "A1.nc").write_text("G0 X5 Y-10 Z12\nG0 Z6.5\nG1 Y3 F500\nG0 Z12\n", encoding="utf-8")
    (tmp_path / "B1.nc").write_text("G0 X5 Y-10 Z12\nG0 Z7.2\nG1 Y3 F500\nG0 Z12\n", encoding="utf-8")
    checks = [
        (name, "keep_out", {"radius": 6.35, "boxes": [_JAW]}) for name in ("A1", "B1")
    ]
    # Unlisted: the 0.5 mm pass fails.
    found = cam_nc.verify(checks, tmp_path, known={})
    assert [(f.program, f.check) for f in found] == [("A1.nc", "jaw_clearance")]
    # Listed: reported as known, not returned.
    assert cam_nc.verify(checks, tmp_path, known={"A1.nc": "#3607"}) == []
    # Listed but clear: the entry is stale and fails.
    stale = cam_nc.verify(checks, tmp_path, known={"A1.nc": "#3607", "B1.nc": "#3607"})
    assert [(f.program, f.check) for f in stale] == [("B1.nc", "jaw_clearance")]
    assert "remove its entry" in stale[0].detail
    # A recipe may raise the floor, never lower it.
    raised = [("B1", "keep_out", {"radius": 6.35, "boxes": [_JAW], "clearance": 1.5})]
    assert [f.check for f in cam_nc.verify(raised, tmp_path, known={})] == ["jaw_clearance"]
    lowered = [("B1", "keep_out", {"radius": 6.35, "boxes": [_JAW], "clearance": 0.5})]
    with pytest.raises(ValueError, match="under the shop floor"):
        cam_nc.verify(lowered, tmp_path, known={})


def test_the_known_jaw_clearance_list_names_its_issue():
    assert cam_nc.KNOWN_JAW_CLEARANCE_VIOLATIONS.keys() == {"CL01_face_b.nc", "PG15_height.nc"}
    assert all("#3607" in why for why in cam_nc.KNOWN_JAW_CLEARANCE_VIOLATIONS.values())


def test_a_reamer_rapided_out_of_its_bore_is_caught(tmp_path):
    fed = _program(tmp_path, "G0 X10 Y5 Z5\nG0 Z1\nG1 Z-7 F80\nG1 Z1 F80\nG0 Z5\n")
    assert _gcode.check_feed_out(fed, 0.0) == []
    rapided = _program(tmp_path, "G0 X10 Y5 Z5\nG0 Z1\nG1 Z-7 F80\nG0 Z5\n")
    assert [f.detail for f in _gcode.check_feed_out(rapided, 0.0)] == [
        "G0 from X10.000 Y5.000 Z-7.000, below the stock top 0.000"
    ]


def test_freecad_older_than_1_1_is_refused(tmp_path, monkeypatch):
    exe = tmp_path / "freecadcmd.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setenv(cam_nc.FREECAD_ENV, str(exe))
    monkeypatch.setattr(cam_nc, "freecad_version", lambda _path: (1, 0))
    with pytest.raises(cam_nc.FreeCadError, match="needs 1.1"):
        cam_nc.resolve_freecadcmd()
    monkeypatch.setattr(cam_nc, "freecad_version", lambda _path: (1, 1))
    assert cam_nc.resolve_freecadcmd() == exe



def test_engagement_sees_what_a_finish_pass_really_meets(tmp_path):
    stock = ((0.0, 20.0), (0.0, 10.0), (0.0, 5.0))
    # A wall at Y5 (the part beyond it): one rough pass leaves 0.5 on it, the
    # finish pass along -X has the wall on its right (climb).
    rough = "G0 X-5 Y1.5 Z5\nG1 Z2 F100\nG1 X25\nG0 Z8\n"
    finish = "G0 X25 Y2 Z8\nG0 Z5\nG1 Z2 F100\nG1 X-5\nG0 Z8\n"
    kwargs = {
        "stock": stock, "radius": 3.0, "max_radial": 0.5, "z": 2.0,
        "window": ((-10.0, 30.0), (2.0, 2.0)), "min_length": 25.0, "side": "climb",
    }
    good = _program(tmp_path, rough + finish)
    assert _gcode.check_engagement(good, **kwargs) == []
    last = _gcode.engagements(good, stock, 3.0)[-1]
    assert last.radial == pytest.approx(0.5, abs=0.06) and last.axial == pytest.approx(3.0) and last.side == "climb"
    # The rough pass stopped short of the far end: the finish meets the full 5 there.
    short = _program(tmp_path, rough.replace("X25", "X12") + finish)
    assert any("radial > 0.500" in f.detail for f in _gcode.check_engagement(short, **kwargs))
    # The finish run +X: the wall on its left, conventional.
    backward = _program(tmp_path, rough + finish.replace("X25", "XA").replace("X-5", "X25").replace("XA", "X-5"))
    assert [f.detail for f in _gcode.check_engagement(backward, **kwargs)] == [
        "X-5.000 Y2.000 -> X25.000 Y2.000 Z2.000 cuts conventional, expected climb"
    ]
    # Nothing selected is a finding, not a pass.
    assert _gcode.check_engagement(good, **{**kwargs, "z": 1.0})[0].check == "engagement"


def test_engagement_follows_an_arc_and_a_slot(tmp_path):
    stock = ((-20.0, 20.0), (-20.0, 20.0), (0.0, 5.0))
    # G2 rings round the origin: R11 cuts 10..12, then R10.5 meets 9.5..10,
    # inside its circle: on the right of clockwise travel, climb.
    rings = (
        "G0 X11 Y0 Z5\nG1 Z2 F100\nG2 X11 Y0 I-11 J0\nG0 Z8\n"
        "G0 X10.5 Y0\nG0 Z5\nG1 Z2 F100\nG2 X10.5 Y0 I-10.5 J0\nG0 Z8\n"
    )
    first, second = [e for e in _gcode.engagements(_program(tmp_path, rings), stock, 1.0) if e.move.centre]
    assert first.side == "both" and first.radial == pytest.approx(2.0, abs=0.06)
    assert second.side == "climb" and second.radial == pytest.approx(0.5, abs=0.06)
