"""The knife mount's CAM recipe agrees with its model and plan.

``cad/process/sm_knife_mount/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``drilled_block`` adapter binds) with no FreeCAD and no SolidWorks, and
refuses any plan number that disagrees with the model, the shop or the
holding. The posted programs are stood in for by the recipe's own section
lines under the grbl post's tool-change block (the tap file's under its own
M6, ending with its M30), so every check the recipe declares runs on them,
and seeded faults show each check catches what it guards.
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "sm_knife_mount"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
IN = 25.4


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "block.step")


@pytest.fixture(scope="module")
def context() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a tap stop's lines after its M6, ending with its M30."""
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
        flat = not any(isinstance(group, tuple) for group in groups)
        sections = [groups] if flat else groups
        for keys in sections:
            first = keys[0]
            if first in ctx["manual"]:
                manual = ctx["manual"][first]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
            job = jobs[first]
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


def _centres(ctx: dict, program: str) -> list:
    return next(
        kwargs["centres"]
        for name, check, kwargs in ctx["expect"]
        if name.startswith(program) and check == "holes"
    )


def test_context_numbers_the_tools_and_places_the_holes_from_the_model(context) -> None:
    assert context["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-30": 3,
        "drill-25": 4,
        "drill-31-64": 5,
        "reamer-4990": 6,
        "tap-guide": 7,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    f = FEATURES["features"]
    s_end = f["plus_x_side"]["plane"]["value"]
    front = f["front_face"]["plane"]["value"]
    top = f["top_seat"]["plane"]["value"]
    # KM06: X from S, Y back from F at the fixed jaw: B at .200 and .275, the
    # tap .300 BASIC beyond B.
    assert _centres(context, "KM06_top_holes@1") == [
        [round(s_end - f[h]["at"][0], 3), round(f[h]["at"][2] - front, 3)]
        for h in ("dowel_hole", "stud_tap")
    ]
    b, tap = _centres(context, "KM06_top_holes@1")
    assert b == [pytest.approx(0.200 * IN), pytest.approx(-0.275 * IN)]
    assert tap[0] - b[0] == pytest.approx(0.300 * IN)
    # KM08: X down from A, Y back from S: .824 BASIC from A, .300 from B.
    bore = f["knife_bore"]["at"]
    assert _centres(context, "KM08_bore") == [
        [round(top - bore[1], 3), round(bore[0] - s_end, 3)]
    ]
    assert top - bore[1] == pytest.approx(0.824 * IN, abs=1e-3)
    # The tap file ends over the tap hole.
    assert context["manual"]["tap_stud"]["at"] == tap


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_every_cut_runs_at_a_cited_4140_ht_setting() -> None:
    for setup in PLAN["setups"]:
        for op in setup["operations"]:
            if op.get("speed_kind") != "spindle":
                continue
            record = SHOP["settings"][op["settings"]]
            assert record["material"] == PLAN["material_key"] == "4140-ht-28-32-hrc"
            assert "rpm" not in op and "feed" not in op


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("front_top_max_mm", 16.0, "front_top_max_mm"),
        ("top_top_max_mm", 33.0, "top_top_max_mm"),
        ("end_top_max_mm", 27.0, "end_top_max_mm"),
        ("blank_thickness_min_in", 0.55, "thinnest bar"),
        ("blank_width_min_in", 1.17, "narrowest bar"),
        ("blank_length_min_in", 1.02, "shortest blank"),
        ("dowel_drill_tip_height_mm", 19.0, "dowel_drill_tip_height_mm"),
        ("tap_drill_tip_height_mm", 18.0, "tap_drill_tip_height_mm"),
        ("bore_drill_tip_height_mm", -3.0, "bore_drill_tip_height_mm"),
        ("bore_ream_tip_height_mm", -5.0, ".4990 reamer tip"),
        ("spot_dia_mm", 3.5, "not under the #30"),
        ("b_pin_step_mm", 0.0508, "bore_err_b_mm"),
        ("tap_x_mm", 12.0, "tap_x_mm"),
        ("bore_y_mm", 12.0, "bore_y_mm"),
        ("bore_from_a_max_mm", 20.701, "bore_from_a_max_mm"),
        ("bore_err_b_mm", 0.0369, "bore_err_b_mm"),
        ("tap_ref_x_mm", 6.35, "reference station"),
        ("bore_ream_feed_mm_min", 30.0, "bore_ream_feed_mm_min"),
        ("tap_from_b_min_mm", 7.5, "tap_from_b_min_mm"),
        ("tap_chamfer_max_mm", 2.0, "tap_chamfer_max_mm"),
        ("bore_parallelism_mm", 0.1, "bore_parallelism_mm"),
        ("edge_grip_mm", 20.0, "edge_grip_mm"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
        ("tap_stack_max_mm", 272.0, "tap_stack_max_mm"),
        ("vise_bore_inset_mm", -60.0, "vise_bore_inset_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    if (
        key.startswith("blank_")
        and key.endswith("_in")
        and key[:-3] + "_mm" in PLAN["parameters"]
    ):
        # A blank band moves in both units, so the size check speaks.
        plan["parameters"][key[:-3] + "_mm"] = value * IN
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_a_cut_at_the_wrong_material_setting_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    for setup in plan["setups"]:
        for op in setup["operations"]:
            if op.get("settings") == "endmill-carbide-3fl-1-2-4140-ht":
                op["settings"] = "endmill-carbide-3fl-1-2-1018-cf"
    with pytest.raises(ValueError, match="is not for 4140-ht-28-32-hrc"):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change, last: bool = False) -> dict:
    """``ctx`` with the first (``last``: the last) line of operation ``key``
    that ``pick`` accepts replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    picked = [i for i, line in enumerate(lines) if pick(line)]
    index = picked[-1] if last else picked[0]
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The first front-face pass moved onto the block's middle: a full-width slot.
        (
            "front_face",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-16.000",
            "face",
        ),
        # The top seat faced with the cutter plunging into the parallels.
        (
            "top_face",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z-1.000 F{feed}",
            "keep_out",
        ),
        # Datum B's drill stopped short of its depth (its last peck).
        (
            "dowel_drill",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z25.000 F{feed}",
            "holes",
        ),
        # The tap drill driven on through the block toward the parallels.
        (
            "tap_drill",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z-1.000 F{feed}",
            "depth",
        ),
        # The 31/64 drill stopped above K.
        (
            "bore_drill",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    context, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(context, key, pick, change, last=key in ("dowel_drill", "tap_drill"))
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}


@pytest.mark.parametrize("key", ["bore_ream"])
def test_a_reamer_rapided_out_of_its_hole_is_caught(context, tmp_path, key) -> None:
    lines = next(op[2] for job in context["jobs"] for op in job["ops"] if op[0] == key)
    out_line = [line for line in lines if line.startswith("G1 Z")][-1]
    seeded = _seed(
        context,
        key,
        lambda line: line == out_line,
        lambda line: line.replace("G1", "G0").replace(" F{feed}", ""),
    )
    _post(seeded, tmp_path)
    assert "feed_out" in {finding.check for finding in _findings(seeded, tmp_path)}


def test_a_tap_file_that_lowers_the_guide_is_caught(context, tmp_path) -> None:
    seeded = copy.deepcopy(context)
    seeded["manual"]["tap_stud"]["gcode"].insert(2, "G0 Z5.000")
    _post(seeded, tmp_path)
    assert "tap_stop" in {finding.check for finding in _findings(seeded, tmp_path)}
