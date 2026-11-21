"""The turned shafts' lathe travelers agree with their models and shop records.

Each ``cad/process/<stem>/plan.toml`` here is a prechips ``turned_shaft``
adapter plan: the adapter binds every printed size, band and station, the
drawing number and revision from the part's feature export (prechips is not
an HA dependency; the adapter's own tests hold its bindings). Here each plan
is held to what prechips cannot see, read from the drawing's requirement
manifest (no SolidWorks seat): a form tool's radius is the drawing's dome
radius and, fed to the centre on the bar, cuts a dome of the drawn height; a
die cuts the drawn thread; every bar it is cut from is a stock record of that
diameter, or the plan says it has none.
"""

from __future__ import annotations

import math
import re
import tomllib
from pathlib import Path

import pytest

import _process_plans
import export_features

ROOT = Path(__file__).resolve().parents[2]
EQUIPMENT = ROOT / "cad" / "config" / "shop-equipment"
IN = 25.4
STEMS = tuple(
    stem
    for stem in _process_plans.TRAVELER_STEMS
    if tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))[
        "cad"
    ].get("adapter")
    == "turned_shaft"
)
SHOP = _process_plans.load_shop()


def _records(*names: str) -> dict:
    records: dict = {}
    for name in names:
        records |= tomllib.loads((EQUIPMENT / name).read_text(encoding="utf-8"))
    return records


STOCK = _records("stock-bought.toml", "stock-to-order.toml")["stock"]
DIES = _records("tools-reamers-taps.toml")["tools"]


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _features(stem: str) -> dict:
    return export_features.requirement_manifest(stem)["features"]


def _tools(plan: dict) -> dict:
    """The plan's tools its operations use, by id."""
    tools = {tool["id"]: tool for tool in plan["tools"]}
    used = {
        op["tool"]
        for setup in plan["setups"]
        for op in setup.get("operations", ())
        if "tool" in op
    }
    return {key: tools[key] for key in used}


def _form_radius_mm(ref: str) -> float | None:
    """A convex form tool's radius from its shop key, form-tool-rNNN (thousandths)."""
    match = re.fullmatch(r"form-tool-r(\d{3})", ref)
    return int(match.group(1)) / 1000 * IN if match else None


def test_the_turned_shafts_are_enrolled() -> None:
    assert set(STEMS) >= {
        "dt_cylinder_gear_shaft",
        "dt_pinion_pivot_shaft",
        "mg_wheel_axle",
    }


@pytest.mark.parametrize("stem", STEMS)
def test_plan_binds_the_part_from_its_feature_export(stem: str) -> None:
    plan = _plan(stem)
    assert plan["cad"] == {
        "file": f"../../out/features/{stem}/features.toml",
        "adapter": "turned_shaft",
        "part": stem.replace("_", "-"),
    }
    assert (plan["part"], plan["revision"]) == (
        "{{cad.drawing_number}}",
        "{{cad.revision}}",
    )


@pytest.mark.parametrize("stem", STEMS)
def test_each_form_tool_cuts_the_drawn_dome(stem: str) -> None:
    """The form's radius is in the drawn radius band (or is the REF radius as
    printed, to .XX), and fed to the centre on the diameter it ends cuts a dome whose
    height lies in the drawn height band, if one is drawn."""
    features = _features(stem)
    forms = {
        _form_radius_mm(tool["ref"])
        for tool in _tools(_plan(stem)).values()
        if _form_radius_mm(tool["ref"]) is not None
    }
    domes = [
        features[end]
        for end in ("datum_end", "far_end")
        if features[end]["kind"] == "dome"
        and features[end].get("made_at") != "assembly"
    ]
    if not domes:
        assert not forms
        return
    assert len(forms) == 1, forms
    (radius,) = forms
    root = features.get("step", features["outer"])
    root_dia = (
        root["dia_nominal"]
        if "dia_nominal" in root
        else (sum(root["dia"]) / 2 if "dia" in root else root["dia_ref"])
    )
    for dome in domes:
        if "radius" in dome:
            assert dome["radius"][0] - 1e-6 <= radius <= dome["radius"][1] + 1e-6
        else:
            assert math.isclose(radius, dome["radius_ref"], abs_tol=0.005 * IN)
        height = radius - math.sqrt(radius**2 - (root_dia / 2) ** 2)
        if "height" in dome:
            assert dome["height"][0] <= height <= dome["height"][1]
    parameters = _plan(stem)["parameters"]
    # The adapter derives the dome heights and the faced length from the
    # form's radius: it must be the form tool's.
    assert math.isclose(parameters["dome_form_radius_in"] * IN, radius, abs_tol=1e-6)
    # Apex readings: a drawn band read from a dome's apex instead of its
    # root (an edge) is that band plus the form's height. The thread's is
    # widened over the blank's diameter band (the op prints the per-blank
    # height); the flat's is on the bar's nominal Ø.
    for key, band, root_band in (
        (
            "thread_apex",
            features.get("step", {}).get("thread_length"),
            features.get("step", {}).get("dia"),
        ),
        (
            "flat_back_apex",
            features.get("flat_back", {}).get("station"),
            [root_dia, root_dia],
        ),
    ):
        if f"{key}_min_in" not in parameters:
            continue
        low, high = (
            radius - math.sqrt(radius**2 - (dia / 2) ** 2) for dia in root_band
        )
        for side, value in (("min", band[0] + low), ("max", band[1] + high)):
            assert math.isclose(parameters[f"{key}_{side}_mm"], value, abs_tol=0.003)
            assert math.isclose(
                parameters[f"{key}_{side}_in"] * IN, value, abs_tol=0.003
            )


@pytest.mark.parametrize("stem", STEMS)
def test_the_die_cuts_the_drawn_thread(stem: str) -> None:
    threads = {item["thread"] for item in _features(stem).values() if "thread" in item}
    dies = [
        tool["ref"]
        for tool in _tools(_plan(stem)).values()
        if tool["ref"] in DIES and DIES[tool["ref"]].get("kind") == "die_set"
    ]
    if not threads:
        assert not dies
        return
    assert len(dies) == 1
    members = {member["thread"] for member in DIES[dies[0]]["members"].values()}
    assert threads <= members


@pytest.mark.parametrize("stem", STEMS)
def test_every_bar_is_a_stock_record_of_its_diameter_or_flagged(stem: str) -> None:
    plan = _plan(stem)
    bar = plan["parameters"]["stock_dia_in"]
    if not plan.get("stock_refs"):
        assert not any(
            record.get("form") == "round_bar" and record["dia_in"][0] == bar
            for record in STOCK.values()
        )
        assert "no stock record" in plan["stock"]
        return
    for ref in plan["stock_refs"]:
        assert STOCK[ref]["form"] == "round_bar", ref
        assert STOCK[ref]["dia_in"][0] == bar, ref
