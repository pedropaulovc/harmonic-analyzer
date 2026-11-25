"""The turned parts' lathe travelers agree with their models and shop records.

Each ``cad/process/<stem>/plan.toml`` here is a prechips ``turned_bush``
adapter plan: the adapter binds every printed size, band and station, the
drawing number and revision from the part's feature export (prechips is not
an HA dependency; the adapter's own tests hold its bindings). Here each plan
is held to what prechips cannot see: the drill it names lands inside the
drawing's hole band (from the drawing's requirement manifest, so no
SolidWorks seat), and every bar it turns from is a stock record of that
diameter.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import _process_plans
import export_features

ROOT = Path(__file__).resolve().parents[2]
EQUIPMENT = ROOT / "cad" / "config" / "shop-equipment"
STEMS = tuple(
    stem
    for stem in _process_plans.TRAVELER_STEMS
    if tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))
    # A family plan binds its parts under [[parts]] and has no [cad].
    .get("cad", {})
    .get("adapter")
    == "turned_bush"
)
SHOP = _process_plans.load_shop()


def _stock() -> dict:
    records: dict = {}
    for name in ("stock-bought.toml", "stock-to-order.toml"):
        data = tomllib.loads((EQUIPMENT / name).read_text(encoding="utf-8"))
        records |= data.get("stock", {})
    return records


STOCK = _stock()


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _drills(plan: dict) -> list[str]:
    tools = {tool["id"]: tool for tool in plan["tools"]}
    return [
        tools[op["tool"]]["ref"]
        for setup in plan["setups"]
        for op in setup.get("operations", ())
        if op.get("drilling") == "twist_drill"
    ]


def _assembly_bore(stem: str) -> bool:
    bore = export_features.requirement_manifest(stem)["features"].get("bore", {})
    return bore.get("made_at") == "assembly"


# A plan that drills must land its drill in the drawing's bore band; the
# sawn-and-faced pins drill nothing. A bore the drawing reams at assembly
# (MHA-PD-28, reamed after pressing) is drilled under its band instead.
_DRILLING = tuple(stem for stem in STEMS if _drills(_plan(stem)))
ASSEMBLY_BORED = tuple(stem for stem in _DRILLING if _assembly_bore(stem))
DRILLED = tuple(stem for stem in _DRILLING if stem not in ASSEMBLY_BORED)


def test_the_turned_parts_are_enrolled() -> None:
    assert set(STEMS) >= {
        "ch_rocker_hub",
        "ch_rocker_strap_tl_hub_plug",
        "dt_cone_gear_tl_arbor_collar",
        "dt_crank_handle_ferrule",
        "dt_crank_handle_butt_cup",
        "sm_gooseneck_end_plug",
        "dt_cylinder_end_disc",
        "mg_wheel_drum",
        "dt_cone_tip_bushing",
    }


@pytest.mark.parametrize("stem", STEMS)
def test_plan_binds_the_part_from_its_feature_export(stem: str) -> None:
    plan = _plan(stem)
    assert plan["cad"] == {
        "file": f"../../out/features/{stem}/features.toml",
        "adapter": "turned_bush",
        "part": stem.replace("_", "-"),
    }
    assert (plan["part"], plan["revision"]) == (
        "{{cad.drawing_number}}",
        "{{cad.revision}}",
    )


# The adapter binding a twist drill's sizing band names, and the feature
# whose hole band that is: the bore, or the tap's drill.
SIZED = {
    "{{cad.bore_dia_band_mm}}": "bore",
    "{{cad.tap_drill_dia_band_mm}}": "tap",
}


@pytest.mark.parametrize("stem", DRILLED)
def test_the_drill_lands_in_the_drawings_hole_band(stem: str) -> None:
    plan = _plan(stem)
    features = export_features.requirement_manifest(stem)["features"]
    tools = {tool["id"]: tool for tool in plan["tools"]}
    # A drill or reamer sized to a band must land in its hole band (an
    # unmapped band fails on SIZED); a pre-drill (sizing "other", under a
    # reamer) is not the finished hole.
    drills = [
        (tools[op["tool"]]["ref"], SIZED[op["sizing"]["band_mm"]])
        for setup in plan["setups"]
        for op in setup.get("operations", ())
        if isinstance(op.get("sizing"), dict)
        and (
            op.get("drilling") == "twist_drill"
            or tools[op["tool"]]["ref"].startswith("reamer-")
        )
    ]
    assert drills
    for ref, feature in drills:
        band = features[feature]["dia"]
        assert band[0] <= SHOP["tools"][ref]["diameter_mm"] <= band[1], ref


@pytest.mark.parametrize("stem", ASSEMBLY_BORED)
def test_an_assembly_bore_is_drilled_under_its_band(stem: str) -> None:
    band = export_features.requirement_manifest(stem)["features"]["bore"]["dia"]
    for ref in _drills(_plan(stem)):
        assert SHOP["tools"][ref]["diameter_mm"] < band[0], ref


# A plan turns its part from round bar (stock_dia_in) or from a squared blank
# sawn off flat bar (blank_side_in, blank_axial_in; the 4-jaw route).
BLOCK = tuple(stem for stem in STEMS if "blank_side_in" in _plan(stem)["parameters"])


@pytest.mark.parametrize("stem", tuple(stem for stem in STEMS if stem not in BLOCK))
def test_every_bar_is_a_stock_record_of_its_diameter(stem: str) -> None:
    plan = _plan(stem)
    bars = {
        value
        for key, value in plan["parameters"].items()
        if key.startswith("stock_dia") and key.endswith("_in")
    }
    recorded = {STOCK[ref]["dia_in"][0] for ref in plan["stock_refs"]}
    for ref in plan["stock_refs"]:
        assert STOCK[ref]["form"] == "round_bar", ref
    assert bars == recorded


@pytest.mark.parametrize("stem", BLOCK)
def test_every_squared_blank_is_sawn_from_a_flat_of_its_thickness(stem: str) -> None:
    plan = _plan(stem)
    side = plan["parameters"]["blank_side_in"] * 25.4
    axial = plan["parameters"]["blank_axial_in"] * 25.4
    assert plan["stock_refs"]
    for ref in plan["stock_refs"]:
        stock = STOCK[ref]
        assert stock["form"] == "flat_bar", ref
        width, thickness = stock["section_mm"]
        assert abs(thickness - axial) < 1e-6, ref
        assert width >= side - 1e-6, ref


def test_the_pivot_spacer_plan_mikes_the_length_round_the_rim_and_tries_the_mate() -> (
    None
):
    """MHA-PD-20 (fit audit 2026-11-23, pending owner confirmation): the
    sheet carries no frame between the faces, so the plan authors no zone:
    the length's limits read at four places round the rim bound the taper;
    the #12 hole is accepted by the screw's shoulder and, for the drawing's
    bonded clearance, by the .001-step pin set against the miked shoulder
    (traveler review 2026-11-24), with no reamer and no plug pair."""
    plan = _plan("pd_transgear_pivot_spacer")
    far = export_features.requirement_manifest("pd_transgear_pivot_spacer")["features"][
        "far_end"
    ]
    assert "parallelism" not in far
    assert "face_parallelism_in" not in plan["parameters"]
    assert _drills(plan) == ["drill-12"]
    refs = {tool["ref"] for tool in plan["tools"]}
    assert not {ref for ref in refs if "reamer" in ref or "plug" in ref}
    import pd_transgear_pivot_spacer_callouts as callouts

    low, high = (
        plan["parameters"][f"bond_clearance_{end}_in"] for end in ("min", "max")
    )
    assert (
        f"(CLEARANCE {low:.4f}-{high:.4f})".replace("0.", ".") in callouts.BOND_CALLOUT
    )
    text = _process_plans.plan_path("pd_transgear_pivot_spacer").read_text(
        encoding="utf-8"
    )
    assert "bore_dia_min_in" not in text and "bore_dia_max_in" not in text
    assert "shoulder enters the hole by hand" in text
    assert "at each of the four places, micrometer" in text
    assert "face_parallelism" not in text
