"""The pen hanger's CAM recipe agrees with its model and plan.

``cad/process/pn_pen_hanger/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
posted programs are stood in for by the recipe's own section lines under the
grbl post's tool-change block, so every check the recipe declares runs on
them, and seeded faults show each check catches what it guards.
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

STEM = "pn_pen_hanger"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "hanger.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min."""
    sections = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
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
        keys = [group[0] if isinstance(group, tuple) else group for group in groups]
        for index, key in enumerate(keys):
            job = sections[key]
            number = ctx["numbers"][job["tool"]]
            if index or name in RECIPE.LOAD_FIRST_TOOL:
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                    f"M6 T{number}",
                ]
            text += [
                f"M3 S{job['rpm']:g}",
                *(
                    line.format(
                        feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}"
                    )
                    for line in lines_of[key]
                ),
            ]
        text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def _lines(ctx: dict, key: str) -> list[str]:
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def _expect(ctx: dict, program: str, check: str) -> dict:
    return next(kw for p, c, kw in ctx["expect"] if p == program and c == check)


def test_context_numbers_the_tools_and_places_the_cuts(ctx) -> None:
    assert ctx["numbers"] == {"spot": 1, "drill-15": 2, "em-eighth": 3}
    assert "endmill-carbide-3fl-3-16" not in SHOP["tools"]
    assert "pn-em-3-16-1018-cf" not in SHOP["settings"]
    assert "endmill-hss-tin-2fl-3-16" not in SHOP["tools"]
    assert "lathe-plunge-3-16-c360" not in SHOP["settings"]
    # The screw hole 5.0 mm below the strap's top end (X0 + .315 in) and
    # 6.80 mm in from its outer top corner, the strap centred on the bar.
    spot = _expect(ctx, "PH01_strap@0", "holes")
    drill = _expect(ctx, "PH01_strap@1", "holes")
    assert spot["centres"] == drill["centres"] == [[13.0, -20.895]]
    # The #15's full diameter .5 mm into the spoil plate; the spot on the
    # thinnest bar's top.
    assert drill["z_bottom"] == -1.874
    assert spot["z_bottom"] == 1.18
    # Fourteen tabs on the strap, four on each plate, all .050 thick on the
    # bar's underside.
    strap = _expect(ctx, "PH01_strap@2", "outline")
    plates = _expect(ctx, "PH02_plates", "outline")
    assert len(strap["tabs"]) == 14
    assert len(plates["tabs"]) == 8
    assert {
        (t["top"], t["floor"], t["thickness"]) for t in strap["tabs"] + plates["tabs"]
    } == {(1.27, 0.0, 1.27)}
    # The outlines' four levels from the thickest bar's top to .010 into
    # the spoil plate.
    assert strap["passes"][0]["levels"] == [2.375, 1.499, 0.622, -0.254]
    # The slots: 22 levels to the drawn depth, two passes .9652 either side
    # of the plates' centre line.
    slots = _lines(ctx, "slots")
    assert slots.count("G1 Z-10.668 F{feed}") == 1
    assert sum(line.startswith("G1 Z") for line in slots) == 22
    assert {line.split()[2] for line in slots if line.startswith("G1 X")} == {
        "Y-7.061",
        "Y-5.131",
    }


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"blank_length_in": 6.9, "blank_length_min_mm": 175.26}, "right end strip"),
        ({"top_waste_mm": 7.0}, "left end strip"),
        ({"bar_edge_offset_mm": 15.0}, "bar_edge_offset_mm"),
        ({"spoil_plate_width_mm": 40.0}, "narrower than the bar"),
        ({"jaw_top_mm": 7.0}, "jaw_top_mm"),
        ({"spot_dia_mm": 4.8}, "under the #15"),
        ({"tab_station_7_mm": 168.0}, "corners at the strap's ends"),
        ({"tab_station_4_mm": 100.0}, "tab_pitch_max_mm"),
        ({"plate_end_waste_mm": 8.0}, "plate_end_waste_mm"),
        ({"plate_tab_station_1_mm": 20.0}, "plate_tab_station_1_mm"),
        ({"plate_gap_mm": 36.0}, "plate_gap_mm"),
        ({"slot_offset_mm": 1.1, "slot_width_mm": 5.375}, "inside its band"),
        ({"slot_levels": 20, "slot_level_mm": 0.5334}, "slot_level_max_mm"),
        ({"slot_projection_min_mm": 13.0}, "gripped on its flutes"),
        ({"packing_block_mm": 19.05}, "packing_top_mm"),
        ({"em_feed_per_min_mm": 250.0}, "em_feed_per_min_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(changes, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"].update(changes)
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` that ``pick`` accepts
    replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # A strap tab cut through: the hop's lift left at the level below it.
        (
            "strap_outline",
            lambda line: line == "G1 Z1.270 F{feed}",
            lambda line: "G1 Z0.622 F{feed}",
            "outline",
        ),
        # A plate tab cut thin: the hop too low.
        (
            "plate_outline",
            lambda line: line == "G1 Z1.270 F{feed}",
            lambda line: "G1 Z1.000 F{feed}",
            "outline",
        ),
        # The #15 stopped short of the spoil plate.
        (
            "strap_drill",
            lambda line: line == "G1 Z-1.874 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # A slot pass run .3 mm off line, into the upper plate's outer arm.
        (
            "slots",
            lambda line: line == "G1 X46.013 Y-5.131 F{feed}",
            lambda line: "G1 X46.013 Y-4.831 F{feed}",
            "keep_out",
        ),
        # The slots' last level left .37 mm short of the drawn depth.
        (
            "slots",
            lambda line: line == "G1 Z-10.668 F{feed}",
            lambda line: "G1 Z-10.300 F{feed}",
            "cleared",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}
