"""The turned shafts' lathe travelers agree with their models and shop records.

Each ``cad/process/<stem>/plan.toml`` here is a prechips ``turned_shaft``
adapter plan: the adapter binds every printed size, band and station, the
drawing number and revision from the part's feature export (prechips is not
an HA dependency; the adapter's own tests hold its bindings). Here each plan
is held to what prechips cannot see, read from the drawing's requirement
manifest (no SolidWorks seat): a form tool's radius is the drawing's dome
radius and, fed to the centre on the bar, cuts a dome of the drawn height; a
die cuts a die-cut drawn thread and a threading tool bit single-points the
rest; every bar it is cut from is a stock record of that diameter, or the
plan says it has none.
"""

from __future__ import annotations

import math
import re
import tomllib
from pathlib import Path

import pytest

import _process_plans
import _shop_equipment
import export_features
import mg_wheel_axle_callouts

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


def _records(*names: str) -> dict:
    return _shop_equipment.merge(EQUIPMENT / name for name in names)


STOCK = _records("stock-bought.toml", "stock-to-order.toml")["stock"]
DIES = _records("tools-reamers-taps.toml")["tools"]
BITS = _records("tools-special-cutters.toml")["tools"]


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
def test_each_dome_is_cut_to_the_drawn_radius(stem: str) -> None:
    """Each dome this traveler cuts is cut to a radius in the drawn radius band
    (or the REF radius as printed, to .XX): the plan's ``dome_form_radius_in``
    (a form tool's, or the radius the ball turner sweeps, owner ruling
    2026-11-23 tool audit Q5), else, stepped from the adapter's table and
    filed (``dome_steps``), the drawing's own. Fed to the centre on the
    diameter it ends, that radius cuts a dome whose height lies in the drawn
    height band, if one is drawn; a form tool the plan still names is of that
    radius."""
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
    parameters = _plan(stem)["parameters"]
    ends = {
        end: features[end]
        for end in ("datum_end", "far_end")
        if features[end]["kind"] == "dome"
        and features[end].get("made_at") != "assembly"
    }
    if any(f"dome_{end[:-4]}_form_radius_in" in parameters for end in ends):
        _each_end_takes_its_own_form_tool(features, parameters, ends, forms)
        return
    if "dome_form_radius_in" in parameters:
        # The adapter derives the dome heights and the faced length from it.
        radius = parameters["dome_form_radius_in"] * IN
        assert all(math.isclose(form, radius, abs_tol=1e-6) for form in forms)
    else:
        # Stepped and filed: the table is on the drawing's own radius.
        assert "dome_steps" in parameters and not forms
        radius = None
    root = features.get("step", features["outer"])
    root_dia = (
        root["dia_nominal"]
        if "dia_nominal" in root
        else (sum(root["dia"]) / 2 if "dia" in root else root["dia_ref"])
    )
    for dome in domes:
        cut = radius or dome.get("radius_nominal", dome.get("radius_ref"))
        if "radius" in dome:
            assert dome["radius"][0] - 1e-6 <= cut <= dome["radius"][1] + 1e-6
        else:
            assert math.isclose(cut, dome["radius_ref"], abs_tol=0.005 * IN)
        height = cut - math.sqrt(cut**2 - min(root_dia / 2, cut) ** 2)
        if "height" in dome:
            assert dome["height"][0] <= height <= dome["height"][1]
    if radius is not None and "dome_form_dia_min_in" in parameters:
        # Formed on each blank's own Ø: the band is the domed diameter's.
        assert [
            parameters[f"dome_form_dia_{side}_in"] * IN for side in ("min", "max")
        ] == pytest.approx(root["dia"], abs=1e-6)
    # Apex readings: a drawn band read from a dome's apex instead of its
    # root (an edge) is that band plus the dome's height. Cut to one radius,
    # the thread's is widened over the blank's diameter band (the op prints
    # the per-blank height); the flat's is on the bar's nominal Ø. Filed and
    # screened between two radius-gauge leaves (``leaf_radius_min_in`` /
    # ``_max_in``), the window holds the band for every leaf radius and every
    # diameter: the band's low end plus the tallest cap, its high end plus
    # the shallowest.
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
        if "leaf_radius_min_in" in parameters:
            leaves = [parameters[f"leaf_radius_{s}_in"] * IN for s in ("min", "max")]
            caps = [
                r - math.sqrt(r**2 - (dia / 2) ** 2)
                for r in leaves
                for dia in root_band
            ]
            window = (band[0] + max(caps), band[1] + min(caps))
        else:
            low, high = (
                radius - math.sqrt(radius**2 - (dia / 2) ** 2) for dia in root_band
            )
            window = (band[0] + low, band[1] + high)
        for side, value in zip(("min", "max"), window, strict=True):
            assert math.isclose(parameters[f"{key}_{side}_mm"], value, abs_tol=0.003)
            assert math.isclose(
                parameters[f"{key}_{side}_in"] * IN, value, abs_tol=0.003
            )


def _each_end_takes_its_own_form_tool(
    features: dict, parameters: dict, ends: dict, forms: set
) -> None:
    """Per-end form tools (``dome_<end>_form_radius_in``): each dome's tool is
    in the plan, its radius in the drawn band, and its cap on the diameter the
    dome ends (the plan's per-end Ø band when it gives one) in a drawn height
    band, if one is drawn."""
    diameters = [
        item
        for item in features.values()
        if item.get("kind") == "diameter" and "span" in item
    ]
    used = set()
    for end, dome in ends.items():
        key = f"dome_{end[:-4]}_form"
        radius = parameters[f"{key}_radius_in"] * IN
        if forms:
            assert any(math.isclose(radius, form, abs_tol=1e-6) for form in forms), end
        used |= {form for form in forms if math.isclose(radius, form, abs_tol=1e-6)}
        if "radius" in dome:
            assert dome["radius"][0] - 1e-6 <= radius <= dome["radius"][1] + 1e-6
        else:
            assert math.isclose(radius, dome["radius_ref"], abs_tol=0.005 * IN)
        plane = dome["plane"]["value"]
        root = min(
            diameters, key=lambda item: min(abs(s - plane) for s in item["span"])
        )
        if f"{key}_dia_min_in" in parameters:
            band = [parameters[f"{key}_dia_{side}_in"] * IN for side in ("min", "max")]
            assert band == pytest.approx(root["dia"], abs=1e-6)
        else:
            band = [root.get("dia_nominal", root.get("dia_ref"))] * 2
        if "height" in dome:
            for dia in band:
                height = radius - math.sqrt(radius**2 - (dia / 2) ** 2)
                assert dome["height"][0] <= height <= dome["height"][1]
    assert used == forms


@pytest.mark.parametrize("stem", STEMS)
def test_the_die_cuts_the_drawn_thread(stem: str) -> None:
    features = _features(stem).values()
    threads = {item["thread"] for item in features if "thread" in item}
    pointed = {
        item["thread"]
        for item in features
        if item.get("thread_process") == "single_point"
    }
    tools = _tools(_plan(stem)).values()
    dies = [
        tool["ref"]
        for tool in tools
        if tool["ref"] in DIES and DIES[tool["ref"]].get("kind") == "die_set"
    ]
    bits = [
        tool["ref"]
        for tool in tools
        if BITS.get(tool["ref"], {}).get("kind") == "threading_tool_bit"
    ]
    assert bool(bits) == bool(pointed)
    threads -= pointed
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


def test_the_axle_rod_band_is_the_printed_fits_limits() -> None:
    parameters = _plan("mg_wheel_axle")["parameters"]
    low, high = mg_wheel_axle_callouts.PIN_LIMITS
    assert math.isclose(_features("mg_wheel_axle")["outer"]["stock_dia_min"], low)
    assert math.isclose(parameters["stock_dia_max_mm"], high, abs_tol=1e-6)
    assert math.isclose(parameters["stock_dia_max_in"] * IN, high, abs_tol=1e-6)
