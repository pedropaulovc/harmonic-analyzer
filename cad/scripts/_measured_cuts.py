"""Measured cutting settings and the envelope each is valid inside.

``cad/config/shop-equipment/measured-cuts.toml`` keys each record by the
prechips setting it bounds (``cad/process/shop/`` ``settings.<key>``): the
deepest and widest cut the dechatter report found stable, the stick-out it was
cut at and the direction it ran. One record set holds per cutter (owner ruling
2026-11-25): ``measured_cutters.<tool>`` gives the band of stick-outs every
record of that tool holds in and the plan parameters that pin the stick-out.

``problems`` reads a plan as authored and names every operation that uses a
measured setting outside its envelope or outside its cutter's stick-out band.
``unmeasured`` names every side or end cut a measured cutter makes, in its
records' material and at a stick-out inside its band, in an operation that
names no measured setting: such a cut must fit a record.
"""

from __future__ import annotations

import re
from typing import Any

import _shop_equipment

SECTION = "measured_cuts"
CUTTERS = "measured_cutters"
# The cut kinds a record bounds: a side-milled wall or an end-milled face.
# A record is cut with the cutter's side into a block's face, never full width,
# so slots (and plunges, drills) are not bounded by one.
BOUNDED_KINDS = frozenset({"side", "end"})
_PROCESS_REF = re.compile(r"\{\{process\.(\w+)\}\}")
_PROCESS_NAME = re.compile(r"\{\{process\.(\w+)")
_TOLERANCE_MM = 1e-9


def records() -> dict[str, dict[str, Any]]:
    """Setting key -> its measured envelope."""
    return _shop_equipment.load().get(SECTION, {})


def cutters() -> dict[str, dict[str, Any]]:
    """Tool key -> the stick-out band its measured records hold in."""
    return _shop_equipment.load().get(CUTTERS, {})


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


def _band(cutter: dict[str, Any]) -> tuple[float, float]:
    return cutter["stickout_min_mm"], cutter["stickout_max_mm"]


def _referenced(value: Any) -> set[str]:
    """Every ``{{process.<name>}}`` a setup's text and numbers name."""
    if isinstance(value, str):
        return set(_PROCESS_NAME.findall(value))
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return set().union(*map(_referenced, value)) if value else set()
    return set()


def _pinned(
    parameters: dict[str, Any], cutter: dict[str, Any], setup: set[str]
) -> dict[str, Any]:
    """The stick-out the cutter runs at in a setup, name -> value: those of
    the cutter's stick-out parameters the setup names (its envelope's tool
    lengths, its touch-off text), or, where it names none, every one the plan
    defines. A plan may pin two (the magnifying bracket's neck runs nearly
    2 in out to reach past its foot, the rest at 28.45)."""
    names = [n for n in cutter["stickout_parameters"] if n in parameters]
    named = [n for n in names if n in setup]
    return {name: parameters[name] for name in named or names}


def _operations(plan: dict[str, Any]):
    """(where, operation, its parameters, the names its setup references) of
    every operation. In a family plan an operation reads the parameters of the
    part it (or its setup) names laid over the plan's, as prechips binds them;
    one that names no part reads the plan's alone."""
    shared = plan.get("parameters", {})
    own = {
        part["id"]: shared | part.get("parameters", {})
        for part in plan.get("parts", ())
    }
    for setup_index, setup in enumerate(plan.get("setups", []), 1):
        names = _referenced(setup)
        for op_index, operation in enumerate(setup.get("operations", []), 1):
            parameters = own.get(operation.get("part", setup.get("part")), shared)
            where = f"setups[{setup_index}].operations[{op_index}]"
            yield where, operation, parameters, names


def problems(
    plan: dict[str, Any],
    measured: dict[str, dict[str, Any]],
    measured_cutters: dict[str, dict[str, Any]],
) -> list[str]:
    """Every way ``plan`` uses a measured setting outside its envelope or its
    cutter's stick-out band."""
    found: list[str] = []
    for at, operation, parameters, names in _operations(plan):
        key = operation.get("settings")
        if key not in measured:
            continue
        record = measured[key]
        where = f"{at} ({key})"
        cutter = measured_cutters[record["tool"]]
        shortest, longest = _band(cutter)
        pinned = _pinned(parameters, cutter, names)
        if not pinned:
            found.append(
                f"{where}: pins no stick-out in any of "
                f"{', '.join(cutter['stickout_parameters'])}"
            )
        for name, value in pinned.items():
            stickout = _number(parameters, value)
            if stickout is None or not (
                shortest - _TOLERANCE_MM <= stickout <= longest + _TOLERANCE_MM
            ):
                found.append(
                    f"{where}: parameters.{name} is {value!r}, the cutter's "
                    f"records hold from {shortest:g} to {longest:g} mm stick-out"
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


def unmeasured(
    plan: dict[str, Any],
    measured: dict[str, dict[str, Any]],
    measured_cutters: dict[str, dict[str, Any]],
    settings: dict[str, dict[str, Any]],
) -> list[str]:
    """Every side or end cut ``plan`` makes with a measured cutter, in a
    material its records were cut in, in an operation that names no measured
    setting, unless its setup runs that cutter at a stick-out outside its band
    (no record holds there). ``settings`` is the shop's settings section."""
    materials: dict[str, set[str]] = {}
    for key, record in measured.items():
        materials.setdefault(record["tool"], set()).add(settings[key]["material"])
    tool_refs = {tool["id"]: tool.get("ref") for tool in plan.get("tools", ())}
    material = plan.get("material_key")
    found: list[str] = []
    for at, operation, parameters, names in _operations(plan):
        key = operation.get("settings")
        if key in measured:
            continue
        tool = settings[key]["tool"] if key in settings else tool_refs.get(
            operation.get("tool")
        )
        if tool not in measured_cutters or material not in materials.get(tool, ()):
            continue
        cutter = measured_cutters[tool]
        shortest, longest = _band(cutter)
        stickouts = [
            _number(parameters, value)
            for value in _pinned(parameters, cutter, names).values()
        ]
        # Exempt only a setup whose every stick-out resolves to a number
        # outside the band, by the same tolerance problems() allows; an
        # unresolvable one proves nothing and stays checked.
        if stickouts and all(
            s is not None
            and not shortest - _TOLERANCE_MM <= s <= longest + _TOLERANCE_MM
            for s in stickouts
        ):
            continue
        for cut in operation.get("milling_cuts", []):
            if cut.get("kind") in BOUNDED_KINDS:
                found.append(
                    f"{at}: {cut.get('kind')} cut {cut.get('name')!r} with "
                    f"{tool} names no measured setting ({key or 'no setting'})"
                )
    return found
