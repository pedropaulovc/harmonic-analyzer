"""Pure, deliberately closed cylinder recipe planner (no COM imports)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

SCHEMA = 1
FEATURES = (
    {"key": "profile", "name": "ReconcileProfile", "type": "ProfileFeature", "depends_on": [], "operation": "origin_circle_front"},
    {"key": "body", "name": "ReconcileBody", "type": "Boss", "depends_on": ["profile"], "operation": "blind_extrusion_positive_z"},
)
DIMENSIONS = {"diameter": "Diameter@ReconcileProfile", "depth": "Depth@ReconcileBody"}


def recipe(diameter_mm: float = 20.0, depth_mm: float = 12.0) -> dict[str, Any]:
    # Independent containers: a caller's structural edit cannot alter the contract.
    import copy
    result = {"schema": SCHEMA, "features": copy.deepcopy(list(FEATURES)),
              "dimensions": dict(DIMENSIONS),
              "parameters_mm": {"diameter": diameter_mm, "depth": depth_mm}}
    validate_recipe(result)
    return result


def validate_recipe(value: dict[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != {"schema", "features", "dimensions", "parameters_mm"}:
        raise ValueError("recipe must contain exactly schema, features, dimensions, parameters_mm")
    params = value["parameters_mm"]
    if not isinstance(params, dict) or set(params) != set(DIMENSIONS):
        raise ValueError("recipe parameters must be diameter and depth")
    for key, number in params.items():
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
            raise ValueError(f"{key} must be a finite positive millimetre value")


@dataclass(frozen=True)
class Plan:
    decision: str
    reason: str
    edits: tuple[tuple[str, float], ...] = ()


def plan(before: dict[str, Any], after: dict[str, Any]) -> Plan:
    """Refuse unsupported structure BEFORE producing any mutation instructions."""
    validate_recipe(before)
    validate_recipe(after)
    for key, expected in (("schema", SCHEMA), ("features", list(FEATURES)), ("dimensions", DIMENSIONS)):
        if before[key] != expected or after[key] != expected:
            return Plan("full_build", f"unsupported or changed {key}")
    edits = tuple((key, float(after["parameters_mm"][key])) for key in DIMENSIONS
                  if before["parameters_mm"][key] != after["parameters_mm"][key])
    return Plan("incremental" if edits else "noop", "supported parameter edit" if edits else "identical recipe", edits)
