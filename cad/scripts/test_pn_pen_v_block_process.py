"""The pen V block's CAM recipe agrees with its model and plan.

``cad/process/pn_pen_v_block/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
block's export binds) with no FreeCAD and no SolidWorks, and refuses any plan
number that disagrees with the model, the shop or the holding. The posted
programs are stood in for by the recipe's own section lines under the grbl
post's tool-change block, so every check the recipe declares runs on them,
and seeded faults show each check catches what it guards.
"""

from __future__ import annotations

import copy
import math
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "pn_pen_v_block"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "block.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _sections(groups: tuple) -> list[tuple[str, ...]]:
    """A program's sections: each tuple group one section; a flat program
    one section holding all its keys."""
    if any(isinstance(group, tuple) for group in groups):
        return [group if isinstance(group, tuple) else (group,) for group in groups]
    return [tuple(groups)]


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section one M6 block (M5, the operator's %msg, M6, M3) and the lines of
    each of its operations, the feeds in mm/min; a tap stop's lines after its
    M6, ending with its M30."""
    jobs = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    lines_of = {op[0]: op[2] for job in ctx["jobs"] for op in job["ops"]}
    for name, groups in RECIPE.PROGRAMS:
        text = [
            f"({name})",
            f"({ctx['comment']})",
            "(Begin preamble)",
            "G17 G90",
            "G21",
            "G54",
        ]
        sections = _sections(groups)
        for keys in sections:
            if keys[0] in ctx["manual"]:
                manual = ctx["manual"][keys[0]]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
            job = jobs[keys[0]]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
            ]
            for key in keys:
                text += [
                    line.format(
                        feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}"
                    )
                    for line in lines_of[key]
                ]
        if not any(keys[0] in ctx["manual"] for keys in sections):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "chamfer": 2,
        "em-eighth": 3,
        "spot": 4,
        "drill-30": 5,
        "drill-43": 6,
        "tap-guide": 7,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    stop = ctx["manual"]["tap"]
    assert stop["tool"] == 7 and stop["at"] == [12.446, -11.938]
    assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_the_v_passes_put_the_cone_on_both_flanks(ctx) -> None:
    """Each level's outer passes hold the pointed 90° cone tangent to both
    45° flanks (tip offset = mouth half-width less the tip depth), no two
    passes further apart than the plan's stepover; the last level reaches the
    flat, its outer passes on the flat's edges."""
    v = ctx["v"]
    stepover = PLAN["parameters"]["v_stepover_max_mm"]
    depths = [t for t, _offsets in v["passes"]]
    assert depths == sorted(depths)
    assert depths[-1] == pytest.approx(
        FEATURES["features"]["v_groove"]["flat_height_ref"]
    )
    for t, offsets in v["passes"]:
        assert offsets[0] == pytest.approx(-(v["mouth_half"] - t))
        assert offsets[-1] == pytest.approx(v["mouth_half"] - t)
        assert max(b - a for a, b in zip(offsets, offsets[1:])) <= stepover + 1e-9
    flat = FEATURES["features"]["v_groove"]["flat_width_nominal"] / 2
    assert v["passes"][-1][1][-1] == pytest.approx(flat)
    assert math.isclose(v["centre_y"], -10.922, abs_tol=1e-6)


def test_the_tip_sweeps_the_flat_edge_to_edge_within_the_ridge_limit(ctx) -> None:
    """Owner ruling 2026-11-23, tool audit Q9: no 5/64 cutter. The chamfer
    mill's point sweeps the flat at the last level, its outer passes on the
    flat's edges (the flat at its nominal .080, inside its printed .07-.09),
    the passes no further apart than twice the ridge limit: a 90° cone's
    ridge between two tip passes stands half their spacing."""
    v = ctx["v"]
    groove = FEATURES["features"]["v_groove"]
    half = groove["flat_width_nominal"] / 2
    flat = v["flat"]
    assert flat[0] == pytest.approx(-half) and flat[-1] == pytest.approx(half)
    lo, hi = groove["flat_width"]
    assert lo <= flat[-1] - flat[0] <= hi
    spacing = max(b - a for a, b in zip(flat, flat[1:]))
    assert spacing / 2 <= RECIPE.V_FLAT_RIDGE_MAX_MM + 1e-9
    assert spacing == pytest.approx(PLAN["parameters"]["v_flat_stepover_mm"])
    assert len(flat) == 41


def test_the_neck_breaks_run_each_neck_face_to_the_stop(ctx) -> None:
    """Owner seat ruling 2026-11-23: the neck's two top edges .080 X 45°
    with the chamfer mill. Its point runs along each neck face (VB06 Y
    -.080 and -.780 from the front face) in three equal levels to the .080
    leg, from a ramp beside P to the export's stop (.33), and is fed up
    there; the whole cone starts clear of P."""
    lines = next(
        op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == "neck_breaks"
    )
    job = next(job for job in ctx["jobs"] if job["ops"][0][0] == "bore_chamfer")
    assert [op[0] for op in job["ops"]] == ["bore_chamfer", "neck_breaks"]
    breaks = FEATURES["features"]["neck_edge_breaks"]
    height = FEATURES["features"]["top_face"]["plane"]["value"]
    ramps = [line for line in lines if line.startswith("G1 X-5.715 Z")]
    depths = sorted(
        {round(height - float(line.split("Z")[1].split()[0]), 3) for line in ramps}
    )
    assert depths == pytest.approx([0.677, 1.355, 2.032])
    assert len(ramps) == 6
    stops = [line for line in lines if line.startswith("G1 X") and " Z" not in line]
    assert stops == [f"G1 X{breaks['full_to_x']:.3f} F{{feed}}"] * 6
    ys = [line.split("Y")[1] for line in lines if line.startswith("G0 X")]
    assert sorted(set(ys)) == ["-19.812", "-2.032"]
    # The cone's top radius at the deepest level clears P at the ramp's end.
    assert -5.715 + breaks["leg_nominal"] < 0.0


def test_no_5_64_cutter_and_a_corner_cutter_off_the_corner_band_is_refused() -> None:
    """The slot's step corners print R.065 (.060-.070): the 1/8 in end mill's
    R.0625 is in the band; a 1/4 in end mill's R.125 is refused, and no tool
    of the plan is the 5/64 in end mill."""
    assert not any(tool["ref"] == "endmill-5-64-long" for tool in PLAN["tools"])
    plan = copy.deepcopy(PLAN)
    tool = next(t for t in plan["tools"] if t["id"] == "em-eighth")
    tool["ref"] = "endmill-carbide-3fl-1-4"
    with pytest.raises(ValueError, match="slot corners' printed band"):
        _context(plan)


def _v_plunge_xs(ctx: dict) -> list[float]:
    """X of the chamfer mill at each of the V section's Z feeds."""
    lines = next(
        op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == "v_groove"
    )
    x, xs = None, []
    for line in lines:
        words = dict((w[0], w[1:]) for w in line.split()[1:] if w[0] in "XYZ")
        if "X" in words:
            x = float(words["X"])
        if line.startswith("G1") and "Z" in words:
            xs.append(x)
    return xs


@pytest.mark.parametrize("stepover", [1.0, 1.1])
def test_every_v_level_plunges_beside_p(stepover) -> None:
    """Each V level plunges in the air beside P, also when a level has an odd
    count of passes (stepover 1.1 gives one) and so ends at the V's far end,
    where a plunge would put the cone past the flank."""
    plan = copy.deepcopy(PLAN)
    plan["parameters"]["v_stepover_max_mm"] = stepover
    ctx = _context(plan)
    counts = [len(offsets) for _t, offsets in ctx["v"]["passes"]]
    assert any(n % 2 for n in counts) == (stepover == 1.1)
    assert set(_v_plunge_xs(ctx)) == {round(ctx["v"]["x"][0], 3)}


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"upright_top_max_mm": 30.0}, "upright_top_max_mm"),
        ({"blank_x_in": 1.0}, "under the length"),
        ({"spot_bore_dia_mm": 3.3}, "not under the #30"),
        ({"spot_tap_dia_mm": 1.9}, "between the pilot"),
        ({"bore_tip_height_mm": 5.5}, "bore_tip_height_mm"),
        ({"tap_tip_height_mm": 11.0}, "tap_tip_height_mm"),
        ({"tap_reach_min_mm": 10.5}, "bottoming tap's chamfer"),
        ({"bore_drill_depth_mm": 12.0}, "bore_drill_depth_mm"),
        ({"tap_drill_depth_mm": 10.0}, "tap_drill_depth_mm"),
        ({"tap_reach_max_mm": 12.6}, "far wall"),
        ({"tap_reach_mm": 12.3}, "tap_reach_mm is not between"),
        ({"bar_thick_min_mm": 18.6}, "bar_thick_min_mm"),
        ({"bar_width_max_mm": 32.5}, "bar_width_max_mm"),
        ({"bar_skim_max_mm": 2.5}, "one face level"),
        ({"back_step_depth_mm": 2.54}, "back_step_depth_mm"),
        ({"drill_30_feed_per_min_mm": 100.0}, "not its setting"),
        ({"lying_grip_mm": 17.0}, "lying_grip_mm"),
        ({"v_level_mm": 0.8}, "level step"),
        ({"corner_cutter_dia_mm": 2.38125}, "the tool is"),
        ({"corner_step_max_mm": 1.4}, "corner_step_max_mm"),
        ({"v_flat_stepover_mm": 0.1}, "v_flat_stepover_mm"),
        ({"break_level_mm": 1.016}, "break_level_mm"),
        ({"break_full_to_mm": 8.89}, "break_full_to_mm"),
        # One inch parallels lying: the front step's floor sits at the jaw tops.
        (
            {
                "stack_height_mm": 25.4,
                "lying_grip_mm": 19.5453,
                "tap_stack_max_mm": 279.908,
            },
            "above the jaw tops",
        ),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(changes, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"].update(changes)
    with pytest.raises(ValueError, match=detail):
        _context(plan)


@pytest.mark.parametrize(
    ("cut", "field", "value", "detail"),
    [
        ("bore drill", "hole_depth_mm", 12.396, "hole_depth_mm is not"),
        ("bore drill", "peck", {"step_mm": 2.54, "retract": "full"}, "peck is not"),
        (
            "tap drill",
            "peck",
            {"step_mm": "{{process.peck_43_mm}}", "retract": "partial"},
            "peck is not",
        ),
    ],
)
def test_a_printed_hole_depth_or_peck_not_bound_is_refused(
    cut, field, value, detail
) -> None:
    plan = copy.deepcopy(PLAN)
    op = RECIPE._op_with_cut(plan, cut)[0]
    op[field] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line ``old`` of operation ``key`` (or of a tap
    stop) replaced."""
    seeded = copy.deepcopy(ctx)
    if key in seeded["manual"]:
        lines = seeded["manual"][key]["gcode"]
    else:
        lines = next(
            op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key
        )
    assert old in lines, (key, old)
    lines[lines.index(old)] = new
    return seeded


@pytest.mark.parametrize(
    ("key", "old", "new", "check"),
    [
        # The top's first face pass moved in: a wider than half-cutter pass.
        ("top", "G0 X-8.890 Y0.764", "G0 X-8.890 Y-3.000", "face"),
        # The back step's pass stopped short of the fixed-jaw side.
        ("back", "G1 Y8.890 F{feed}", "G1 Y-5.000 F{feed}", "cleared"),
        # A relief pass run into the step face.
        ("bottom", "G1 X15.240 F{feed}", "G1 X8.000 F{feed}", "keep_out"),
        # The V's last level cut below the flat.
        ("v_groove", "G1 Z13.558 F{feed}", "G1 Z12.558 F{feed}", "depth"),
        # The flat's middle tip pass moved .1 mm: a ridge over .001 in.
        ("v_groove", "G1 Y-10.922 F{feed}", "G1 Y-10.822 F{feed}", "cleared"),
        # A corner pass into the slot's near wall.
        (
            "corners",
            "G1 X10.478 Y-17.209 F{feed}",
            "G1 X10.478 Y-18.300 F{feed}",
            "keep_out",
        ),
        # The #30 stopped short of the slot.
        ("bore_drill", "G1 Z4.623 F{feed}", "G1 Z6.000 F{feed}", "holes"),
        # A #43 peck re-entry rapided past the depth already drilled.
        ("tap_drill", "G0 Z20.312", "G0 Z18.000", "rapid"),
        # A neck break run on past its stop, into the body.
        ("neck_breaks", "G1 X8.382 F{feed}", "G1 X9.500 F{feed}", "keep_out"),
        # A neck break plunged straight down instead of ramped beside P: a
        # second hole in the bore chamfer's section.
        ("neck_breaks", "G1 X-5.715 Z17.323 F{feed}", "G1 Z17.323 F{feed}", "holes"),
        # A neck break's last level short of the leg.
        (
            "neck_breaks",
            "G1 X-5.715 Z15.968 F{feed}",
            "G1 X-5.715 Z16.200 F{feed}",
            "cleared",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        ("tap", "M30", "M0", "tap_stop"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}
