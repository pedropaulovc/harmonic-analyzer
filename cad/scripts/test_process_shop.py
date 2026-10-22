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
        f'[fixtures.bound]\ncad = "{_BOUND_SPEC_STEM}"\n'
        f"# {plans.PLACEHOLDER_BY}: a comment-declared value\n"
        'note = "kept"\n',
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
    assert set(plans.shop_placeholders()) == spliced | {
        "inventory.toml:fixtures.bound line 2 (comment)"
    }
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
