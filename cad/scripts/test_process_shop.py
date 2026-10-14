"""The tracked shop inputs validate under the pinned prechips models and bind."""

from __future__ import annotations

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
# Shop-made rocker fixtures may carry the part's name; their TL CAD parts come
# with the fixtures themselves. Every other part-named table is a plan input.
SHOP_MADE_ROCKER_IDS = frozenset(
    {
        "rocker-riser-blocks",
        "rocker-filing-stand",
        "rocker-trammel",
        "rocker-trammel-setting-bar",
    }
)
_PART_ID = re.compile(r"(?:^|[-_])(?:rocker|cone|bracket)(?:[-_]|$)")


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


def test_tracked_shop_files_are_the_bound_set():
    assert tuple(MODELS) == plans.SHOP_FILES


@pytest.mark.parametrize("name", list(MODELS))
def test_shop_file_validates_under_pinned_prechips(name):
    MODELS[name].model_validate(_shop(name))


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


def test_no_inventory_table_names_a_part():
    inventory = _shop("inventory.toml")
    named = [
        f"{category}.{item}"
        for category, items in inventory.items()
        if isinstance(items, dict)
        for item in items
        if _PART_ID.search(item) and item not in SHOP_MADE_ROCKER_IDS
    ]
    assert not named, named
    present = {
        item
        for items in inventory.values()
        if isinstance(items, dict)
        for item in items
    }
    assert SHOP_MADE_ROCKER_IDS <= present
