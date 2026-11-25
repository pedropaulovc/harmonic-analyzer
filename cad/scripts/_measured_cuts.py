"""Measured cutting settings and the envelope each is valid inside.

``cad/config/shop-equipment/measured-cuts.toml`` keys each record by the
prechips setting it bounds (``cad/process/shop/`` ``settings.<key>``): the
tool assembly's stick-out (and, where the record allows a shorter or a longer
one, ``stickout_min_mm`` and ``stickout_max_mm``), the plan parameter that
pins it, and the deepest and widest cut the dechatter report found stable. ``problems`` reads a plan as
authored and names every operation that uses such a setting outside its
envelope.
"""

from __future__ import annotations

import re
from typing import Any

import _shop_equipment

SECTION = "measured_cuts"
_PROCESS_REF = re.compile(r"\{\{process\.(\w+)\}\}")
_TOLERANCE_MM = 1e-9


def records() -> dict[str, dict[str, Any]]:
    """Setting key -> its measured envelope."""
    return _shop_equipment.load().get(SECTION, {})


def _number(parameters: dict[str, Any], value: Any) -> float | None:
    """A cut field's value: a number, or one ``{{process.<name>}}`` reference.
    Anything else (a CAD reference, an expression) is not provable from the
    plan alone and reads as None."""
    if isinstance(value, str):
        match = _PROCESS_REF.fullmatch(value.strip())
        value = parameters.get(match.group(1)) if match else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def problems(plan: dict[str, Any], measured: dict[str, dict[str, Any]]) -> list[str]:
    """Every way ``plan`` uses a measured setting outside its envelope. In a
    family plan an operation reads the parameters of the part it (or its
    setup) names laid over the plan's, as prechips binds them; one that names
    no part reads the plan's alone."""
    shared = plan.get("parameters", {})
    own = {
        part["id"]: shared | part.get("parameters", {})
        for part in plan.get("parts", ())
    }
    found: list[str] = []
    for setup_index, setup in enumerate(plan.get("setups", []), 1):
        for op_index, operation in enumerate(setup.get("operations", []), 1):
            key = operation.get("settings")
            if key not in measured:
                continue
            parameters = own.get(operation.get("part", setup.get("part")), shared)
            record = measured[key]
            where = f"setups[{setup_index}].operations[{op_index}] ({key})"
            pin = record["stickout_parameter"]
            stickout = _number(parameters, parameters.get(pin))
            shortest = record.get("stickout_min_mm", record["stickout_mm"])
            longest = record.get("stickout_max_mm", record["stickout_mm"])
            if stickout is None or not shortest <= stickout <= longest:
                allowed = (
                    f"{longest:g}"
                    if shortest == longest
                    else f"{shortest:g} to {longest:g}"
                )
                found.append(
                    f"{where}: parameters.{pin} is {parameters.get(pin)!r}, "
                    f"the record allows {allowed} mm stick-out"
                )
            cuts = operation.get("milling_cuts", [])
            if not cuts:
                found.append(f"{where}: declares no milling_cuts to bound")
            for cut in cuts:
                for field, limit in (
                    ("axial_doc_mm", record["axial_doc_max_mm"]),
                    ("radial_woc_mm", record["radial_woc_max_mm"]),
                ):
                    value = _number(parameters, cut.get(field))
                    name = cut.get("name")
                    if value is None:
                        found.append(
                            f"{where}: cut {name!r} {field} is {cut.get(field)!r}, "
                            "not a number or one process parameter"
                        )
                    elif value > limit + _TOLERANCE_MM:
                        found.append(
                            f"{where}: cut {name!r} {field} {value:g} exceeds "
                            f"the measured {limit:g} mm"
                        )
    return found
