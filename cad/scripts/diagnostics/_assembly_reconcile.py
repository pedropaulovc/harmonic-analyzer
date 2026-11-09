"""Pure, deliberately closed two-occurrence mate recipe planner (no COM imports).

One generated cylinder (the keyed-feature experiment's baseline part) is
inserted twice. ``base`` is fixed at the assembly origin; ``mover`` is fully
constrained to it by Top/Right coincident planes and one Front-plane distance
mate. Only that named distance value is an incremental edit; every structural
change (keys, names, types, planes, alignment, flip, child recipe or
configurations) is refused as ``full_build`` without edit instructions.
"""
from __future__ import annotations

import copy
import math
from typing import Any

try:  # imported as ``diagnostics._assembly_reconcile`` by pytest
    from ._feature_reconcile import Plan, recipe as part_recipe, validate_recipe as validate_part_recipe
except ImportError:  # imported as a top-level sibling by the benchmark script
    from _feature_reconcile import Plan, recipe as part_recipe, validate_recipe as validate_part_recipe

SCHEMA = 1
CONFIGURATIONS = {"assembly": "Default", "child": "Default"}
COMPONENTS = (
    {"key": "base", "fixed": True, "initial_translation_mm": [0.0, 0.0, 0.0]},
    {"key": "mover", "fixed": False, "initial_translation_mm": "distance_on_positive_z"},
)
# Entity order is [mover plane, base plane] for every mate.
MATES = (
    {"key": "top", "name": "ReconcileTop", "type": "MateCoincident", "mate_type": "coincident",
     "mover_plane": "Top Plane", "base_plane": "Top Plane", "alignment": "aligned"},
    {"key": "right", "name": "ReconcileRight", "type": "MateCoincident", "mate_type": "coincident",
     "mover_plane": "Right Plane", "base_plane": "Right Plane", "alignment": "aligned"},
    {"key": "distance", "name": "ReconcileDistance", "type": "MateDistanceDim", "mate_type": "distance",
     "mover_plane": "Front Plane", "base_plane": "Front Plane", "alignment": "aligned", "flip": False},
)
DIMENSIONS = {"distance": "D1@ReconcileDistance"}
_KEYS = {"schema", "child", "configurations", "components", "mates", "dimensions", "parameters_mm"}


def recipe(distance_mm: float = 30.0) -> dict[str, Any]:
    # Independent containers: a caller's structural edit cannot alter the contract.
    result = {"schema": SCHEMA, "child": part_recipe(),
              "configurations": dict(CONFIGURATIONS),
              "components": copy.deepcopy(list(COMPONENTS)),
              "mates": copy.deepcopy(list(MATES)),
              "dimensions": dict(DIMENSIONS),
              "parameters_mm": {"distance": distance_mm}}
    validate_recipe(result)
    return result


def validate_recipe(value: dict[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != _KEYS:
        raise ValueError(f"assembly recipe must contain exactly {sorted(_KEYS)}")
    validate_part_recipe(value["child"])
    params = value["parameters_mm"]
    if not isinstance(params, dict) or set(params) != set(DIMENSIONS):
        raise ValueError("assembly recipe parameters must be exactly distance")
    for key, number in params.items():
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
            raise ValueError(f"{key} must be a finite positive millimetre value")


def plan(before: dict[str, Any], after: dict[str, Any]) -> Plan:
    """Refuse unsupported structure BEFORE producing any mutation instructions."""
    validate_recipe(before)
    validate_recipe(after)
    expected = {"schema": SCHEMA, "child": part_recipe(), "configurations": CONFIGURATIONS,
                "components": list(COMPONENTS), "mates": list(MATES), "dimensions": DIMENSIONS}
    for key, value in expected.items():
        if before[key] != value or after[key] != value:
            return Plan("full_build", f"unsupported or changed {key}")
    edits = tuple((key, float(after["parameters_mm"][key])) for key in DIMENSIONS
                  if before["parameters_mm"][key] != after["parameters_mm"][key])
    return Plan("incremental" if edits else "noop",
                "supported mate dimension edit" if edits else "identical recipe", edits)
