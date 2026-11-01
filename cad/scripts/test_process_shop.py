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
import _rocker_interface as rocker_interface
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


# Shop-process acceptance retained from fcfc947c4:cad/scripts/
# ch_rocker_arm_tl_{filing_button,filing_stud,filing_stand}_spec.py and their
# drawing requirements. These are no longer CAD contracts; the live inventory
# and rocker route must still meet the same limits.
_HUB_FILING_BANDS_MM = {
    "button_dia_limits_mm": (10.030, 10.290),
    "button_bore_limits_mm": (6.505, 6.515),
    "pin_dia_limits_mm": (6.485, 6.490),
}
_HUB_FILING_RUNOUT_TIR_MM = 0.025
_FILING_STAND_STEP_LIMITS_MM = (0.39, 0.49)


def _rocker_plan() -> dict[str, Any]:
    return tomllib.loads(plans.plan_path("ch_rocker_arm").read_text(encoding="utf-8"))


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


def test_rocker_mill_clamp_studs_enter_the_centre_t_slot():
    inventory = _shop("inventory.toml")
    members = inventory["fixtures"]["clamping-kit-pm-52pcck-14mm"]["members"]
    risers = _fixture_solids("rocker-riser-blocks")
    table = risers["table"]
    centre_slot = risers["table slot 2 neck"]
    slot_y = centre_slot["at_mm"][1] + centre_slot["size_mm"][1] / 2
    local_table_top = table["at_mm"][2] + table["size_mm"][2]
    blocks = [solid for name, solid in risers.items() if name.endswith("riser")]
    assert len(blocks) == 6
    for block in blocks:
        assert block["at_mm"][2] == local_table_top
        assert block["at_mm"][2] + block["size_mm"][2] == 0.0
    checked: dict[str, int] = {}
    for setup in _rocker_plan()["setups"]:
        hold = setup["hold"]
        if hold["fixture"] != "rocker-riser-blocks":
            continue
        hold_pose = hold["pose"]
        table_y = hold_pose["origin_mm"][1] + hold_pose["x"][0] * slot_y
        table_top = hold_pose["origin_mm"][2] + local_table_top
        checked[setup["id"]] = 0
        for clamp in hold["clamps"]:
            kit, member = (
                clamp["ref"].split("/", 1) if "/" in clamp["ref"] else ("", "")
            )
            if kit != "clamping-kit-pm-52pcck-14mm":
                continue
            assert member == (
                "strap-pad-mill-raised" if setup["id"] == "S1" else "strap-pad-mill"
            )
            solids = {solid["name"]: solid for solid in members[member]["solids"]}
            stud = solids["stud"]
            assert stud["length_mm"] == 101.6
            pose = clamp["pose"]
            stud_y = pose["origin_mm"][1] + stud["at_mm"][0] * pose["x"][1]
            assert abs(stud_y - table_y) + stud["dia_mm"] / 2 < 7.0
            bottom = pose["origin_mm"][2] + stud["at_mm"][2]
            assert table_top - 24.0 < bottom < table_top - 14.0
            foot = solids["T-nut foot"]
            foot_top = pose["origin_mm"][2] + foot["at_mm"][2] + foot["size_mm"][2]
            assert abs(foot_top - (table_top - 14.0)) < 1e-9
            foot_width = (
                abs(pose["x"][1]) * foot["size_mm"][0]
                + abs(pose["x"][0]) * foot["size_mm"][1]
            )
            assert foot_width < 25.0
            checked[setup["id"]] += 1
    assert checked == {"S1": 2, "S2": 2, "S3": 2, "S4": 2}


def test_pedestal_top_carries_the_lower_hub_face():
    plan = _rocker_plan()
    setups = {setup["id"]: setup for setup in plan["setups"]}
    solids = _fixture_solids("rocker-filing-stand")
    pedestal = solids["hub pedestal"]
    lower_hub_face = (plan["stock"]["section_mm"][1] - rocker.HUB_LENGTH) / 2
    assert abs(lower_hub_face - 0.4405) < 1e-9
    hub_face_op = next(op for op in setups["S1"]["ops"] if op["op"] == 10)
    assert hub_face_op["to_z"] - rocker.HUB_LENGTH == pytest.approx(lower_hub_face)
    low, high = _FILING_STAND_STEP_LIMITS_MM
    assert low <= lower_hub_face <= high
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
    assert setups["S5"]["hold"]["fixture"] == "rocker-filing-stand"
    held_top = setups["S5"]["hold"]["pose"]["origin_mm"][2] + pedestal_top
    assert abs(held_top + rocker.HUB_LENGTH) <= rocker.HUB_LENGTH_BAND[0]


def test_end_blocks_sit_under_the_blank_ends_clear_of_the_arm():
    stock = _rocker_plan()["stock"]
    solids = _fixture_solids("rocker-filing-stand")
    raw_left = stock["origin_mm"][0]
    raw_right = raw_left + stock["length_mm"]
    assert raw_right == -raw_left
    for side in ("left", "right"):
        block = solids[f"{side} end block"]
        length_max = limits(block["size_mm"][0], 1)[1]
        if side == "left":
            assert block["at_mm"][0] == raw_left
            assert block["at_mm"][0] + length_max < -rocker.ROD_TIP_X
        else:
            assert block["at_mm"][0] + block["size_mm"][0] == raw_right
            assert raw_right - length_max > rocker.ROD_TIP_X


def test_stack_height_seats_the_centred_strap_on_the_raw_ends():
    plan = _rocker_plan()
    setups = {setup["id"]: setup for setup in plan["setups"]}
    raw_thickness = plan["stock"]["section_mm"][1]
    strap_face_op = next(op for op in setups["S3"]["ops"] if op["op"] == 10)
    strap_face_z = strap_face_op["to_z"]
    assert strap_face_z == pytest.approx((raw_thickness + rocker.ARM_THICKNESS) / 2)
    stack = _fixture_solids("strap-shim-stack")["stack"]
    height = stack["size_mm"][2]
    assert stack["shim"] is True and stack["bears"] == "face"
    assert height == pytest.approx(raw_thickness - strap_face_z)
    ground_flat = 3 / 32 * 25.4  # approved 3/32 in stock, inventory purchase
    assert 0 < height - ground_flat < height
    for setup_id, seat_z in (("S1", 0.0), ("S4", raw_thickness - strap_face_z)):
        hold = setups[setup_id]["hold"]
        supports = [
            clamp for clamp in hold["clamps"] if clamp["ref"] == "strap-shim-stack"
        ]
        assert len(supports) == 4
        for support in supports:
            pose = support["pose"]
            assert pose["z"] == [0.0, 0.0, 1.0]
            top = pose["origin_mm"][2] + stack["at_mm"][2] + height
            assert top == pytest.approx(seat_z)


def test_s4_stacks_stay_inside_the_arm_strap_band():
    plan = _rocker_plan()
    setup = next(setup for setup in plan["setups"] if setup["id"] == "S4")
    stack = _fixture_solids("strap-shim-stack")["stack"]
    supports = [
        clamp for clamp in setup["hold"]["clamps"] if clamp["ref"] == "strap-shim-stack"
    ]
    assert len(supports) == 4
    assert plan["frames"][setup["frame"]]["y"] == [0.0, -1.0, 0.0]
    stations = []
    for support in supports:
        pose = support["pose"]
        assert pose["x"] == [1.0, 0.0, 0.0]
        stations.append((abs(pose["origin_mm"][0]), -pose["origin_mm"][1]))

    def strap_band(x: float) -> tuple[float, float]:
        bottom = rocker_interface.CENTER_Y - math.sqrt(
            rocker_interface.R_BOTTOM**2 - x**2
        )
        top = rocker_interface.CENTER_Y - math.sqrt(rocker.R_TOP**2 - x**2)
        return bottom - rocker_interface.PIVOT_MID_Y, top - rocker_interface.PIVOT_MID_Y

    half_l = limits(stack["size_mm"][0], 1)[1] / 2
    for width, fits in (
        (limits(stack["size_mm"][1], 1)[1], True),
        (0.75 * 25.4, False),  # the as-bought width must still fail at X120
    ):
        inside = all(
            strap_band(x + half_l)[0] < y - width / 2
            and y + width / 2 < strap_band(x - half_l)[1]
            for x, y in stations
        )
        assert inside is fits, width
    for x, y in stations:
        bottom, top = strap_band(x)
        assert top - bottom == pytest.approx(rocker_interface.ARM_DEPTH, abs=0.5)
        assert bottom < y < top


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
