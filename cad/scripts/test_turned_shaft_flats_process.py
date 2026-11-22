"""The turned shafts' flat-milling CAM recipes agree with their models and plans.

``cad/process/<stem>/cam.py`` for the fulcrum shaft, the pivot shaft and the
pinion lift rod
writes every path itself; its ``context`` runs here on the drawing's
requirement manifest (the features the part's export binds) with no FreeCAD
and no SolidWorks, and refuses any plan number that disagrees with the
model, the shop or the holding. The posted program is stood in for by the
recipe's own lines under the grbl post's tool-change block, so every check
the recipe declares runs on it, and seeded faults show each check catches
what it guards.
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

STEMS = ("ch_fulcrum_shaft", "ch_pivot_shaft", "dt_pinion_lift_rod")
SHOP = _process_plans.load_shop()


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _context(stem: str, plan: dict | None = None) -> dict:
    recipe = _cam_programs.load_recipe(stem)
    features = export_features.requirement_manifest(stem)
    return recipe.context(features, plan or _plan(stem), SHOP, "shaft.step")


def _post(stem: str, ctx: dict, out: Path) -> None:
    """The program as the runtime posts it: the grbl preamble, the M6 block
    (M5, the operator's %msg, M6, M3) and the lines, feeds in mm/min."""
    recipe = _cam_programs.load_recipe(stem)
    ((name, _keys),) = recipe.PROGRAMS
    (job,) = ctx["jobs"]
    number = ctx["numbers"][job["tool"]]
    text = [
        f"({name})",
        f"({ctx['comment']})",
        "(Begin preamble)",
        "G17 G90",
        "G21",
        "G54",
        "M5",
        f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
        f"M6 T{number}",
        f"M3 S{job['rpm']:g}",
    ]
    for _key, _label, lines in job["ops"]:
        text += [
            line.format(feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}")
            for line in lines
        ]
    text += ["M5", "G17 G90", "M2"]
    (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(stem: str, ctx: dict, out: Path) -> list:
    return cam_nc.verify(_cam_programs.load_recipe(stem).expectations(ctx), out)


def test_the_flat_parts_have_recipes() -> None:
    assert set(STEMS) <= set(_cam_programs.CAM_STEMS)


@pytest.mark.parametrize("stem", STEMS)
def test_the_recipes_program_passes_every_check_it_declares(
    stem: str, tmp_path
) -> None:
    ctx = _context(stem)
    assert ctx["numbers"] == {"em-eighth": 1}
    _post(stem, ctx, tmp_path)
    assert _findings(stem, ctx, tmp_path) == []
    recipe = _cam_programs.load_recipe(stem)
    times = cam_nc.cycle_times(recipe.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in recipe.PROGRAMS}


@pytest.mark.parametrize("stem", STEMS)
@pytest.mark.parametrize(
    ("key", "delta", "detail"),
    [
        ("flat_depth_mm", 0.05, "axial_doc_mm"),
        ("jaw_top_over_od_mm", 1.0, "jaw_top_over_od_mm"),
        ("vise_jaw_from_x0_mm", 2.0, "vise_jaw_(from|to)_x0_mm"),
        ("vise_jaw_to_x0_mm", -2.0, "vise_jaw_to_x0_mm"),
        ("flat_stepover_max_mm", 1.0, "over half the cutter"),
        ("stock_dia_in", 0.0625, "stock_dia_in"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(
    stem: str, key: str, delta: float, detail: str
) -> None:
    plan = copy.deepcopy(_plan(stem))
    plan["parameters"][key] += delta
    with pytest.raises(ValueError, match=detail):
        _context(stem, plan)


@pytest.mark.parametrize("stem", STEMS)
def test_a_flat_station_off_the_model_is_refused(stem: str) -> None:
    plan = copy.deepcopy(_plan(stem))
    recipe = _cam_programs.load_recipe(stem)
    # One flat per file (the pivot shaft's) or every flat in one clamping.
    key = f"{recipe.FLATS[0]}_from_mm" if hasattr(recipe, "FLATS") else "flat_from_mm"
    plan["parameters"][key] += 0.5
    with pytest.raises(ValueError, match=key):
        _context(stem, plan)


def _seed(ctx: dict, old_prefix: str, new: str) -> dict:
    """``ctx`` with the first line starting ``old_prefix`` replaced by ``new``."""
    seeded = copy.deepcopy(ctx)
    lines = seeded["jobs"][0]["ops"][0][2]
    index = next(i for i, line in enumerate(lines) if line.startswith(old_prefix))
    lines[index] = new
    return seeded


def _first(ctx: dict, prefix: str) -> str:
    return next(line for line in ctx["jobs"][0]["ops"][0][2] if line.startswith(prefix))


@pytest.mark.parametrize("stem", STEMS)
def test_a_seeded_fault_in_the_program_is_caught(stem: str, tmp_path) -> None:
    ctx = _context(stem)
    depth = min(
        float(line.split("Z")[1].split()[0])
        for line in ctx["jobs"][0]["ops"][0][2]
        if line.startswith("G1") and " Z" in line
    )
    cases = [
        # The first ramp leg cut .05 mm under the flat: the flat over-depth.
        (_first(ctx, "G1 Y"), f"G1 Y0.000 Z{depth - 0.05:.3f} F{{feed}}", "depth"),
        # The cutter rapided down into the O.D. before the first flat.
        ("G0 Z0.100", "G0 Z-0.200", "rapid"),
        # The second X station pushed past the flat's end into the kept O.D.
        (
            _first(ctx, "G1 X"),
            "G1 X" + str(float(_first(ctx, "G1 X")[4:].split()[0]) + 3.0) + " F{feed}",
            "keep_out",
        ),
    ]
    for old, new, check in cases:
        seeded = _seed(ctx, old, new)
        _post(stem, seeded, tmp_path)
        assert check in {
            finding.check for finding in _findings(stem, seeded, tmp_path)
        }, (old, new, check)


def test_the_pivot_shafts_one_file_cuts_both_flats_each_from_its_own_tip(
    tmp_path,
) -> None:
    stem = "ch_pivot_shaft"
    features = export_features.requirement_manifest(stem)
    recipe = _cam_programs.load_recipe(stem)
    # The south flat moved along the shaft is no longer the north one's twin.
    moved = copy.deepcopy(features)
    moved["features"]["flat_south"]["span"] = [
        z + 0.5 for z in moved["features"]["flat_south"]["span"]
    ]
    with pytest.raises(ValueError, match="flat_south: not flat_north's place"):
        recipe.context(moved, _plan(stem), SHOP, "shaft.step")
    # Centred on the jaws, as the fulcrum shaft is held, the flat's inner end
    # sits between the jaw faces: the cutter's sweep reaches a jaw.
    plan = copy.deepcopy(_plan(stem))
    length = 173.996
    width = plan["parameters"]["vise_jaw_width_mm"]
    plan["parameters"]["vise_jaw_from_x0_mm"] = round((length - width) / 2, 3)
    plan["parameters"]["vise_jaw_to_x0_mm"] = round((length + width) / 2, 3)
    ctx = recipe.context(features, plan, SHOP, "shaft.step")
    _post(stem, ctx, tmp_path)
    assert "keep_out" in {finding.check for finding in _findings(stem, ctx, tmp_path)}
