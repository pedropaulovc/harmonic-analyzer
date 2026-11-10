"""Pure, deliberately closed one-part drawing recipe planner (no COM imports).

The keyed-feature experiment's cylinder is drawn on the project landscape
template with two keyed model views (``*Front`` and ``*Right``), its two keyed
model dimensions imported as native associative display dimensions (diameter
in the front view, depth in the side view) and one free sheet note. Only the
part's keyed dimension values are incremental edits; any drawing structure
change (template, sheet, views, annotations, note) or part structure change is
refused as ``full_build`` without edit instructions.
"""
from __future__ import annotations

import copy
from typing import Any

try:  # imported as ``diagnostics._drawing_reconcile`` by pytest
    from ._feature_reconcile import Plan, plan as plan_part, recipe as part_recipe, validate_recipe as validate_part_recipe
except ImportError:  # imported as a top-level sibling by the benchmark script
    from _feature_reconcile import Plan, plan as plan_part, recipe as part_recipe, validate_recipe as validate_part_recipe

SCHEMA = 1
# Resolved exactly as _drawing_common.new_project_drawing does: the repository
# DRAWING_TEMPLATES[layout] .DRWDOT, never the seat's default preference.
TEMPLATE = {"layout": "landscape"}
SHEET = {"scale": [1.0, 1.0], "units": "mm", "decimals": 2}
# View centres are sheet millimetres from the lower-left corner (B landscape is
# 431.8 x 279.4 mm); keyed names are applied with IView.SetName2. ``Default``
# is the generated cylinder's only configuration (natively observed by the
# assembly experiment's explicit child configuration).
VIEWS = (
    {"key": "front", "name": "ReconcileFront", "orientation": "*Front", "configuration": "Default",
     "position_mm": [110.0, 170.0], "scale": [1.0, 1.0]},
    {"key": "side", "name": "ReconcileSide", "orientation": "*Right", "configuration": "Default",
     "position_mm": [200.0, 170.0], "scale": [1.0, 1.0]},
)
# Model dimension keys refer to the part recipe's DIMENSIONS; each is imported
# (InsertModelAnnotations3) into exactly the declared view.
ANNOTATIONS = (
    {"key": "diameter", "kind": "model_dimension", "view": "front", "dimension": "diameter"},
    {"key": "depth", "kind": "model_dimension", "view": "side", "dimension": "depth"},
    {"key": "note", "kind": "note", "owner": "sheet", "text": "EXPERIMENTAL KEYED DRAWING RECONCILIATION",
     "position_mm": [40.0, 250.0]},
)
_KEYS = {"schema", "part", "template", "sheet", "views", "annotations"}


def recipe(diameter_mm: float = 20.0, depth_mm: float = 12.0) -> dict[str, Any]:
    # Independent containers: a caller's structural edit cannot alter the contract.
    result = {"schema": SCHEMA, "part": part_recipe(diameter_mm, depth_mm),
              "template": dict(TEMPLATE), "sheet": copy.deepcopy(SHEET),
              "views": copy.deepcopy(list(VIEWS)),
              "annotations": copy.deepcopy(list(ANNOTATIONS))}
    validate_recipe(result)
    return result


def validate_recipe(value: dict[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != _KEYS:
        raise ValueError(f"drawing recipe must contain exactly {sorted(_KEYS)}")
    validate_part_recipe(value["part"])


def plan(before: dict[str, Any], after: dict[str, Any]) -> Plan:
    """Refuse unsupported structure BEFORE producing any mutation instructions."""
    validate_recipe(before)
    validate_recipe(after)
    expected = {"schema": SCHEMA, "template": TEMPLATE, "sheet": SHEET,
                "views": list(VIEWS), "annotations": list(ANNOTATIONS)}
    for key, value in expected.items():
        if before[key] != value or after[key] != value:
            return Plan("full_build", f"unsupported or changed {key}")
    part = plan_part(before["part"], after["part"])
    if part.decision == "full_build":
        return Plan("full_build", f"part: {part.reason}")
    return Plan(part.decision, "supported part dimension edit" if part.edits else "identical recipe", part.edits)
