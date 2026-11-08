"""The tracked shop inputs validate under the pinned prechips models and bind."""

from __future__ import annotations

import importlib
import math
import re
import tomllib
from collections.abc import Iterator
from typing import Any

import pytest
from prechips.model import CuttingData, Inventory, Policy

import _process_plans as plans
import ch_rocker_arm_spec as rocker
from _printed_limits import limits

MODELS = {
    "inventory.toml": Inventory,
    "shop-policy.toml": Policy,
    "cutting-data.toml": CuttingData,
}
# Every shop-made inventory record, enumerated: only these may name a part (the
# part they are made for, or their own TL CAD part where one exists), and a new
# shop-made record is a deliberate addition here. Every other part-named table
# is a plan input.
SHOP_MADE_IDS = frozenset(
    {
        "fixtures.angle-plate",
        "fixtures.hub-filing-buttons",
        "fixtures.rocker-filing-stand",
        "fixtures.rocker-oblique-trammel",
        "fixtures.rocker-riser-blocks",
        "fixtures.strap-shim-stack",
        "fixtures.trammel-pivot-plate",
        "gauges.arm-outline-template",
        "gauges.rocker-trammel-setting-bar",
        "tools.ring-laps",
        "tools.rocker-trammel",
    }
)


def _words(text: str) -> str:
    return " " + " ".join(re.findall(r"[a-z0-9]+", text.lower())) + " "


def _part_identities() -> frozenset[str]:
    """Every registered part's stem (without system prefix) and drawing number."""
    import _config

    return frozenset(
        _words(identity)
        for stem, row in _config.parts().items()
        for identity in (stem.split("-", 1)[1], str(row["number"]))
    )


def _names_part(item: str, record: dict[str, Any], identities: frozenset[str]) -> bool:
    text = _words(f"{item} {record.get('name', '')}")
    return any(identity in text for identity in identities)


def _shop(name: str) -> dict[str, Any]:
    return tomllib.loads((plans.PROCESS_ROOT / "shop" / name).read_bytes().decode())


def _measurements(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        if "measured" in node:
            yield path, node["measured"]
        for key, value in node.items():
            yield from _measurements(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _measurements(value, f"{path}[{index}]")


def _without_cad(node: Any) -> Any:
    """Drop the HA-only fixture ``cad`` tag; the bound-shop test covers its solids."""
    if isinstance(node, dict):
        return {k: _without_cad(v) for k, v in node.items() if k != "cad"}
    if isinstance(node, list):
        return [_without_cad(value) for value in node]
    return node


def test_tracked_shop_files_are_the_bound_set():
    assert tuple(MODELS) == plans.SHOP_FILES


@pytest.mark.parametrize("name", list(MODELS))
def test_shop_file_validates_under_pinned_prechips(name):
    MODELS[name].model_validate(_without_cad(_shop(name)))


def test_bound_shop_validates_and_preserves_tracked_inventory(tmp_path):
    inventory, policy, cutting = plans.bind_shop(directory=tmp_path)
    bound = tomllib.loads(inventory.read_text(encoding="utf-8"))
    Inventory.model_validate(bound)
    if not plans.shop_spec_modules():
        assert bound == _shop("inventory.toml")
    assert (
        policy.read_bytes() == (plans.PROCESS_ROOT / "shop" / policy.name).read_bytes()
    )
    assert (
        cutting.read_bytes()
        == (plans.PROCESS_ROOT / "shop" / cutting.name).read_bytes()
    )


def test_zoro_order_is_owned_but_not_installed_or_measured():
    inventory = _shop("inventory.toml")
    ordered = {
        row["sku"]: row
        for category in ("tools", "holders")
        for row in inventory[category].values()
        if "WB7365521946" in row.get("purchase", "")
    }
    quantities = {
        "1000100": 2,
        "1010700": 2,
        "1011008": 2,
        "1011108": 2,
        "1012200": 5,
        "1023700": 3,
        "1024300": 4,
        "1024400": 1,
        "1024901": 1,
        "1025000": 1,
        "1025200": 1,
        "1025308": 1,
        "015326AS": 2,
        "008320AS": 2,
        "1120408": 1,
        "1120500": 1,
        "1120700": 1,
        "DWTH1316-080": 1,
        "DWTH1316-440": 1,
        "3000DS1": 1,
    }
    assert {sku: row["pieces"] for sku, row in ordered.items()} == quantities
    assert sum(row["pieces"] for row in ordered.values() if row["kind"] == "tap") == 32
    for row in ordered.values():
        assert row["present"] is False
        assert row["verify"] is True
        assert row["make"]
        assert row["source"].startswith("https://www.zoro.com/i/G")
        assert row["source"].endswith("/")
        assert "2026-11-06" in row["purchase"]
        assert "ordered, not yet received" in row["purchase"]
        for _, measured in _measurements(row):
            assert measured["status"] == "assumed"


def test_owned_kit_members_follow_the_photo_not_the_hypothetical_kit():
    kit = _shop("inventory.toml")["tools"]["tap-die-set-40"]
    sizes = {
        "4-36",
        "6-32",
        "8-32",
        "10-32",
        "10-24",
        "12-24",
        "1-4-20",
        "1-4-28",
        "5-16-18",
        "3-8-16",
        "7-16-20",
        "7-16-14",
        "5-16-24",
        "3-8-24",
        "1-2-20",
        "1-2-13",
    }
    assert set(kit["sizes"]) == sizes
    assert set(kit["members"]) == {
        f"{kind}-{size}" for kind in ("tap", "die") for size in sizes
    } | {"tap-1-8-pipe"}
    assert kit["present"] is True
    assert kit["verify"] is True
    assert "NOT trust its taps or dies for project work" in kit["note"]
    assert not list(_measurements(kit))
    assert all(set(row) == {"kind", "name"} for row in kit["members"].values())


def test_owned_kit_holders_replace_the_catalogue_example():
    inventory = _shop("inventory.toml")
    holders = inventory["holders"]
    assert "tap-wrench-t-1-16-1-4" not in holders
    for name in ("tap-wrench-kit-40-t", "tap-wrench-kit-40-bar", "die-handle-kit-40"):
        row = holders[name]
        assert row["present"] is True
        assert row["verify"] is True
        assert "tools.tap-die-set-40" in row["note"]
        assert "sku" not in row
        assert not list(_measurements(row))
    assert "#0-80 square remains unverified" in holders["tap-wrench-kit-40-t"]["note"]


@pytest.mark.parametrize("name", list(MODELS))
def test_every_measured_record_names_who_measured(name):
    records = list(_measurements(_shop(name)))
    missing = [
        path
        for path, measured in records
        if measured != "unknown"
        and not (isinstance(measured, dict) and str(measured.get("by", "")).strip())
    ]
    assert not missing, missing


def _spec_solids() -> Iterator[tuple[str, dict[str, Any]]]:
    """Every solid a cad-tagged inventory table splices from its TL spec."""
    for module in plans.shop_spec_modules():
        for index, solid in enumerate(importlib.import_module(module).PRECHIPS_SOLIDS):
            yield f"{module}.PRECHIPS_SOLIDS[{index}]", solid


def _solids(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Every entry of every ``solids`` list, wherever its table nests."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else key
            if key == "solids" and isinstance(value, list):
                for index, solid in enumerate(value):
                    yield f"{here}[{index}]", solid
            else:
                yield from _solids(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _solids(value, f"{path}[{index}]")


def test_placeholder_marker_is_the_shared_constant():
    marker = plans.PLACEHOLDER_BY
    assert plans.PLACEHOLDER_ISSUE in marker
    # No variant spelling escapes the count: every #1413 `by` is the constant,
    # in the tracked files and in the TL specs' PRECHIPS_SOLIDS alike.
    measurements = [
        measured for name in MODELS for _, measured in _measurements(_shop(name))
    ] + [
        measured for _, solid in _spec_solids() for _, measured in _measurements(solid)
    ]
    variants = {
        str(measured["by"])
        for measured in measurements
        if isinstance(measured, dict)
        and plans.PLACEHOLDER_ISSUE in str(measured.get("by", ""))
    } - {marker}
    assert not variants, variants
    # Binding counts every occurrence: values, prose and comments in the tracked
    # files, plus solids spliced from TL specs.
    tracked = sum(
        (plans.PROCESS_ROOT / "shop" / name).read_text(encoding="utf-8").count(marker)
        for name in MODELS
    )
    spliced = sum(
        repr(importlib.import_module(module).PRECHIPS_SOLIDS).count(marker)
        for module in plans.shop_spec_modules()
    )
    assert len(plans.shop_placeholders()) == tracked + spliced > 0


# A surviving TL spec that publishes prechips solids. The tracked inventory
# carries every fixture's solids inline, so the cad-tag splice is exercised on
# a shop built here around this spec.
_BOUND_SPEC_STEM = "ch_rocker_arm_tl_oblique_end_bracket"


def test_spec_solid_placeholders_are_counted_where_they_bind(tmp_path, monkeypatch):
    shop = tmp_path / "shop"
    shop.mkdir()
    for name in plans.SHOP_FILES:
        (shop / name).write_text("version = 1\n", encoding="utf-8")
    (shop / "inventory.toml").write_text(
        f'[fixtures.bound]\ncad = "{_BOUND_SPEC_STEM}"\nnote = "kept"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(plans, "PROCESS_ROOT", tmp_path)
    module = f"{_BOUND_SPEC_STEM}_spec"
    assert plans.shop_spec_modules() == (module,)
    solids = importlib.import_module(module).PRECHIPS_SOLIDS
    spliced = {
        f"inventory.toml:fixtures.bound.solids[{index}].measured.by"
        for index, solid in enumerate(solids)
        if solid["measured"]["by"] == plans.PLACEHOLDER_BY
    }
    assert spliced
    assert set(plans.shop_placeholders()) == spliced
    inventory, _, _ = plans.bind_shop(directory=tmp_path / "bound")
    fixture = tomllib.loads(inventory.read_text(encoding="utf-8"))["fixtures"]["bound"]
    assert "cad" not in fixture
    assert fixture["solids"] == solids
    assert fixture["note"] == "kept"


def test_every_bound_solid_states_its_measured_status(tmp_path):
    """#1462: prechips trusts a solid with no measured record as installed
    nominal geometry, and an omitted status reads as assumed."""
    inventory, _, _ = plans.bind_shop(directory=tmp_path)
    bound = list(_solids(tomllib.loads(inventory.read_text(encoding="utf-8"))))
    tracked = list(_solids(_shop("inventory.toml")))
    assert len(bound) == len(tracked) + len(list(_spec_solids()))
    missing = [
        path
        for path, solid in bound
        if not (
            isinstance(solid.get("measured"), dict) and "status" in solid["measured"]
        )
    ]
    assert not missing, missing


# Retained fixture acceptance from fcfc947c4:cad/scripts/
# ch_rocker_arm_tl_{filing_button,filing_stud,filing_stand}_spec.py and their
# drawing requirements. These check the surviving inventory records only;
# they do not prescribe the superseded one-piece rocker process route.
_HUB_FILING_BANDS_MM = {
    "button_dia_limits_mm": (10.030, 10.290),
    "button_bore_limits_mm": (6.505, 6.515),
    "pin_dia_limits_mm": (6.485, 6.490),
}
_HUB_FILING_RUNOUT_TIR_MM = 0.025
_FILING_STAND_STEP_LIMITS_MM = (0.39, 0.49)


def test_cad_trammel_identity_does_not_claim_a_commissioned_installation():
    fixture = _shop("inventory.toml")["fixtures"]["rocker-oblique-trammel"]
    assert fixture["shop_made"] is True
    assert fixture["present"] == "unknown"
    assert fixture["verify"] is True
    assert fixture["make_document"]["id"] == "MHA-CH-06-TL-00"
    assert fixture["make_document"]["revision"] == "v47"
    assert fixture["commissioning_record"] == "unknown"
    for field in (
        "rail_angle_deg",
        "rail_angle_error_deg",
        "pin_spacing_error_mm",
        "pin_clearance_mm",
        "rail_offset_mm",
        "rail_travel_mm",
    ):
        assert fixture[field] == "unknown", field
    assert fixture["pin_spacing_mm"] == {"inner": "unknown", "outer": "unknown"}
    assert not list(_measurements(fixture))


def _rocker_plan() -> dict[str, Any]:
    return tomllib.loads(plans.plan_path("ch_rocker_arm").read_text(encoding="utf-8"))


def test_rocker_makes_two_components_before_forming_the_pressed_hub_root():
    plan = _rocker_plan()
    assert plan["construction"] == plan["stock"]["form"] == "built_up"
    components = {row["id"]: row for row in plan["stock"]["components"]}
    assert {key: row["form"] for key, row in components.items()} == {
        "hub": "round_bar",
        "strap": "flat_bar",
    }
    setups = {row["id"]: row for row in plan["setups"]}
    assert setups["H1"]["stock_in"] == "stock.hub"
    assert setups["P1"]["stock_in"] == "stock.strap"
    assert setups["J1"]["stock_in"] == ["H1", "T4"]
    joint = setups["J1"]["joint"]
    assert joint["kind"] == "cylindrical"
    assert joint["method"] == "press"
    assert joint["fit"] == "interference"
    assert joint["forms"] == ["hub_root"]
    transient = plan["joint_features"]
    assert transient[joint["socket"]]["component"] == "strap"
    assert transient[joint["spigot"]]["component"] == "hub"
    assert transient[joint["socket"]]["kind"] == "cylinder_bore"
    assert transient[joint["spigot"]]["kind"] == "cylinder_spigot"
    assert joint["interference_mm"][0] > 0
    assert "ch_rocker_arm" not in plans.TRAVELER_STEMS


def test_rocker_finishes_strap_before_press_and_final_bore_and_rod_hole_after_press():
    setups = {row["id"]: row for row in _rocker_plan()["setups"]}
    for sid, source in (
        ("P1E", "P1"),
        ("P2", "P1E"),
        ("P2E", "P2"),
        ("P3", "P2E"),
    ):
        assert setups[sid]["stock_in"] == source
    for sid in ("P1", "P1E", "P2", "P2E"):
        clamps = setups[sid]["hold"]["clamps"]
        assert len(clamps) >= 2
        assert all(clamp["restraint"] == "press" for clamp in clamps)
    for sid, feature in (("P1", "strap_datum_b"), ("P2", "strap_faces")):
        assert any(
            op["do"] == "face" and op.get("feature") == feature
            for op in setups[sid]["ops"]
        )
    for sid, source in (("F1", "J1"), ("F2", "F1"), ("D1", "F2")):
        assert setups[sid]["stock_in"] == source
        assert not any(
            op["do"] == "face"
            and op.get("feature") in ("strap_datum_b", "strap_faces")
            for op in setups[sid]["ops"]
        )
    assert any(
        op["do"] == "ream" and op.get("feature") == "pivot_bore"
        for op in setups["F1"]["ops"]
    )
    assert any(
        op["do"] == "drill"
        and op.get("feature") == "rod_hole"
        and op["tool"] == "drill-index-115/#47"
        for op in setups["D1"]["ops"]
    )


def test_rocker_releases_supported_upper_scrap_and_clocks_each_tip_cut():
    setups = {row["id"]: row for row in _rocker_plan()["setups"]}
    rough = setups["R1"]
    assert len(rough["hold"]["clamps"]) >= 3
    assert all(
        clamp["restraint"] == "press" for clamp in rough["hold"]["clamps"]
    )
    assert any(
        op["do"] == "release" and op["keep"] == "strap_datum_b"
        for op in rough["ops"]
    )
    for sid, source, frame in (
        ("T4A", "T3", "TIP_POS"),
        ("T4B", "T4A", "TIP_NEG"),
        ("T4C", "T4B", "TAPER_POS"),
        ("T4", "T4C", "TAPER_NEG"),
    ):
        assert setups[sid]["stock_in"] == source
        assert setups[sid]["frame"] == frame


def test_rocker_finishes_both_arcs_on_the_current_oblique_trammel():
    plan = _rocker_plan()
    guided = [
        (setup, op)
        for setup in plan["setups"]
        for op in setup["ops"]
        if op.get("contour", {}).get("method") == "guided_sweep"
    ]
    assert len(guided) == 2
    assert {
        (op["feature"], op["contour"]["sweep"]["pin_pair"])
        for _, op in guided
    } == {("top_edge", "inner"), ("profile_outer", "outer")}
    for setup, op in guided:
        sweep = op["contour"]["sweep"]
        assert op["do"] == "finish_profile"
        assert sweep["guide"] == "trammel"
        assert setup["hold"]["fixture"] == sweep["fixture"] == "rocker-oblique-trammel"


def _fixture_solids(fixture: str) -> dict[str, dict[str, Any]]:
    solids = _shop("inventory.toml")["fixtures"][fixture]["solids"]
    named = {solid["name"]: solid for solid in solids}
    assert len(named) == len(solids), fixture
    return named


def test_pm30mv_table_models_share_the_manual_slot_section():
    # PM-30MV manual v3 2020-10 p6, cited beside the inline slot solids:
    # three 14 mm mouths on 63.5 mm centres, 14 deep, over a 25 x 10 undercut.
    for fixture in ("pm30mv-table", "rocker-riser-blocks"):
        solids = _fixture_solids(fixture)
        table = solids["table"]
        slots = [solid for solid in solids.values() if solid.get("void")]
        assert len(slots) == 6
        table_top = table["at_mm"][2] + table["size_mm"][2]
        centre_y = table["at_mm"][1] + table["size_mm"][1] / 2
        sections = []
        for slot in slots:
            assert slot["cuts"] == ["table"]
            assert slot["at_mm"][0] < table["at_mm"][0]
            assert slot["at_mm"][0] + slot["size_mm"][0] > (
                table["at_mm"][0] + table["size_mm"][0]
            )
            sections.append(
                (
                    round(slot["at_mm"][1] + slot["size_mm"][1] / 2 - centre_y, 3),
                    slot["size_mm"][1],
                    round(table_top - slot["at_mm"][2], 3),
                    slot["size_mm"][2],
                )
            )
        assert sorted(sections) == sorted(
            (centre, width, depth, height)
            for centre in (-63.5, 0.0, 63.5)
            for width, depth, height in ((14.0, 14.0, 15.0), (25.0, 24.0, 10.0))
        )


def test_filing_stand_pedestal_retains_its_independent_step_limits():
    solids = _fixture_solids("rocker-filing-stand")
    pedestal = solids["hub pedestal"]
    low, high = _FILING_STAND_STEP_LIMITS_MM
    assert high - low <= 2 * rocker.HUB_LENGTH_BAND[0] + 1e-9
    assert limits(pedestal["dia_mm"], 2)[1] < rocker.HUB_DIA_MIN
    pedestal_height = pedestal["length_mm"] * pedestal["axis"][2]
    pedestal_top = pedestal["at_mm"][2] + pedestal_height
    for side in ("left", "right"):
        block = solids[f"{side} end block"]
        block_top = block["at_mm"][2] + block["size_mm"][2]
        assert block_top == 0.0
        assert pedestal["at_mm"][2] == block["at_mm"][2]
        assert low <= pedestal_top - block_top <= high


def test_kit_holds_the_hub_coaxiality_and_filed_band():
    solids = _fixture_solids("hub-filing-buttons")
    body_min = _HUB_FILING_BANDS_MM["pin_dia_limits_mm"][0]
    bore_max = _HUB_FILING_BANDS_MM["button_bore_limits_mm"][1]
    shift = (
        (rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0] - body_min) / 2
        + (bore_max - body_min) / 2
        + _HUB_FILING_RUNOUT_TIR_MM / 2
    )
    assert 2 * shift <= rocker.HUB_COAXIALITY_DIA + 1e-9
    rim_low, rim_high = _HUB_FILING_BANDS_MM["button_dia_limits_mm"]
    hub_low, hub_high = (
        rocker.HUB_DIA - rocker.LINEAR_2PL,
        rocker.HUB_DIA + rocker.LINEAR_2PL,
    )
    assert hub_low <= rim_low - 2 * shift and rim_high + 2 * shift <= hub_high
    # The inline kit still registers both rims on the same pin and seats on
    # the current hub, rather than retaining an unrelated old hub length.
    assert solids["upper button"]["at_mm"] == [0.0, 0.0, 0.0]
    assert solids["lower button"]["at_mm"] == [0.0, 0.0, -rocker.HUB_LENGTH]
    for name in ("upper button", "lower button", "stud pin"):
        assert solids[name]["at_mm"][:2] == [0.0, 0.0]
        assert solids[name]["axis"][:2] == [0.0, 0.0]


def test_inventory_kit_limit_facts_lie_inside_the_process_bands():
    kit = _shop("inventory.toml")["fixtures"]["hub-filing-buttons"]
    for field, (low, high) in _HUB_FILING_BANDS_MM.items():
        least, greatest = kit[field]["value"]
        assert low - 1e-9 <= least <= greatest <= high + 1e-9, (field, low, high)
    assert 0 <= kit["button_runout_mm"]["value"] <= _HUB_FILING_RUNOUT_TIR_MM
    solids = _fixture_solids("hub-filing-buttons")
    for names, field in (
        (("upper button", "lower button"), "button_dia_limits_mm"),
        (("upper button bore", "lower button bore"), "button_bore_limits_mm"),
        (("stud pin",), "pin_dia_limits_mm"),
    ):
        low, high = _HUB_FILING_BANDS_MM[field]
        for name in names:
            assert low <= solids[name]["dia_mm"] <= high, name


def _nested(
    qualified: str, item: str, record: dict[str, Any]
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    yield qualified, item, record
    for key, value in record.items():
        if isinstance(value, dict):
            yield from _nested(f"{qualified}.{key}", key, value)


def _records() -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Every inventory record: tables, array-of-tables rows such as `[[stock]]`,
    and nested ones such as a kit's members."""
    for category, items in _shop("inventory.toml").items():
        if isinstance(items, dict):
            rows = items.items()
        elif isinstance(items, list):
            rows = ((str(index), row) for index, row in enumerate(items))
        else:
            continue
        for item, record in rows:
            if isinstance(record, dict):
                yield from _nested(f"{category}.{item}", item, record)


def test_shop_made_records_are_enumerated():
    made = {qualified for qualified, _, record in _records() if record.get("shop_made")}
    assert made == SHOP_MADE_IDS


def test_part_identities_catch_a_part_named_gauge():
    gauge = _shop("inventory.toml")["gauges"]["arm-outline-template"]
    assert _names_part("arm-outline-template", gauge, _part_identities())


def test_no_inventory_table_names_a_part():
    identities = _part_identities()
    named = [
        qualified
        for qualified, item, record in _records()
        if _names_part(item, record, identities) and qualified not in SHOP_MADE_IDS
    ]
    assert not named, named


def test_records_cover_array_of_table_rows():
    assert any(qualified.startswith("stock.") for qualified, _, _ in _records())


# A parenthesised list of record ids (three or more kebab words) in a note, e.g.
# "(rocker-hub-strap, rocker-rail-clamp)": the make tables a record is bought for.
_ID = r"[a-z][a-z0-9]*(?:-[a-z0-9]+){2,}"
_CITED_TABLES = re.compile(rf"\(({_ID}(?:, {_ID})*)\)")


def test_no_inventory_record_supplies_a_table_outside_the_shop():
    """A record bought for a make table the shared shop does not hold is that part's
    plan input, not shared inventory (it returns with the part's migration)."""
    items = {item for _, item, _ in _records()}
    dangling = [
        (qualified, table)
        for qualified, _, record in _records()
        for cited in _CITED_TABLES.findall(str(record.get("note", "")))
        for table in cited.split(", ")
        if table not in items
    ]
    assert not dangling, dangling


def _rows(kind: str) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    """`[[cut]]` rows by (material, tool material, operation); `[[plunge]]` as "plunge"."""
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in _shop("cutting-data.toml")[kind]:
        key = (row["material_class"], row["tool_material"], row.get("operation", kind))
        groups.setdefault(key, []).append(row)
    return groups


CUTTING_GROUPS = {**_rows("cut"), **_rows("plunge")}


@pytest.mark.parametrize("key", list(CUTTING_GROUPS), ids="/".join)
def test_cutting_rows_tile_their_diameter_span(key):
    """prechips matches lo <= d <= hi; a row below its neighbour ends on the float just
    under the neighbour's lo, so the rows are half-open [lo, hi) with no gap or overlap."""
    bands = sorted(tuple(row["diameter_range"]) for row in CUTTING_GROUPS[key])
    for (lo, hi), (next_lo, _) in zip(bands, bands[1:]):
        assert lo <= hi
        assert hi == math.nextafter(next_lo, -math.inf), (hi, next_lo)


# Inventory kit (or member) kinds whose cutters each cutting-data operation feeds.
_OPERATION_KINDS = {
    "face": {"endmill_set"},
    "profile": {"endmill_set"},
    "plunge": {"endmill_set"},
    "drill": {"drill_index", "drill_set", "drill"},
    "spot": {"center_drill_set"},
    "ream": {"reamers"},
}


def _cutters(operation: str) -> Iterator[tuple[str, float]]:
    for kit_id, kit in _shop("inventory.toml")["tools"].items():
        for member_id, member in kit.get("members", {}).items():
            dia = member.get("dia_mm")
            kind = member.get("kind", kit.get("kind"))
            if kind in _OPERATION_KINDS[operation] and dia:
                value = dia["value"] if isinstance(dia, dict) else dia
                yield f"{kit_id}.{member_id}", value


@pytest.mark.parametrize("key", list(CUTTING_GROUPS), ids="/".join)
def test_every_inventory_cutter_in_span_matches_one_row(key):
    bands = [row["diameter_range"] for row in CUTTING_GROUPS[key]]
    span = (min(lo for lo, _ in bands), max(hi for _, hi in bands))
    unresolved = [
        (cutter, dia, hits)
        for cutter, dia in _cutters(key[2])
        if span[0] <= dia <= span[1]
        and (hits := sum(lo <= dia <= hi for lo, hi in bands)) != 1
    ]
    assert not unresolved, unresolved
