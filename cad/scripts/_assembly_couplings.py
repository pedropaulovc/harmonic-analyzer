"""Specialized mechanical couplings, separate from shared placement and mates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import _telemetry
from _assembly import _mate, _mate_hard_error, suspend_automatic_assembly_rebuilds


async def gear_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    ratio: Iterable[float],
    *,
    alignment: str = "closest",
    label: str = "",
) -> Any:
    """Gear mate coupling two rotations at ``ratio=[numerator, denominator]``.

    The ratio is tooth counts (driver:driven); verify the sign/direction with a
    kinematic rotate after meshing, per the plan's gear-ratio risk.
    """
    ratio = list(ratio)
    label = label or f"gear {ratio[0]:g}:{ratio[1]:g}"
    return await _mate(
        adapter, label, "gear", [ref_a, ref_b], gear_ratio=ratio, alignment=alignment
    )


def gear_mates_batch(
    adapter: Any,
    specs: Iterable[tuple[Any, Any, Iterable[float], str]],
    *,
    label: str = "gear-mate bank",
) -> list[dict[str, Any]]:
    """Create a bank of gear mates with one closing assembly solve.

    The normal adapter path ends every mate with ``EditRebuild3``.  That is a
    severe quadratic cost in a mature assembly and is redundant here:
    ``IAssemblyDoc.CreateMate`` seats each new gear relationship immediately,
    while one closing rebuild proves the complete coupled system.  This is the
    production form of ``diagnostics/diag_mate_rebuild_cost.py``'s H4 result.
    """
    from solidworks_mcp.adapters.base import AddMateParameters
    from solidworks_mcp.adapters.solidworks import assembly as _sw_asm

    rows = list(specs)
    model = adapter.currentModel
    results: list[dict[str, Any]] = []
    names: list[tuple[str, str]] = []
    with _telemetry.span(label, mates=len(rows)):
        with suspend_automatic_assembly_rebuilds(adapter):
            for ref_a, ref_b, raw_ratio, mate_label in rows:
                ratio = [float(value) for value in raw_ratio]
                if len(ratio) != 2:
                    raise ValueError(f"{mate_label}: gear ratio must have two values")
                params = AddMateParameters(
                    mate_type="gear",
                    entities=[ref_a, ref_b],
                    alignment="closest",
                    gear_ratio=ratio,
                )
                model.ClearSelection2(True)
                for ref in params.entities:
                    if not _sw_asm._select_mate_entity(adapter, ref, 1):
                        located = ref.name or ref.point
                        raise RuntimeError(
                            f"{mate_label}: failed to select gear entity {located!r}"
                        )
                # CreateMate/CreateMateData are IAssemblyDoc members; the flagged
                # handle MUST be reassigned and passed on (a discarded result is a
                # silent no-op → the mate calls fall back on the IModelDoc2 model).
                asm_h = _sw_asm._flag_feature_methods(model, "IAssemblyDoc")
                mate = _sw_asm._create_standard_mate(
                    adapter, asm_h, params, _sw_asm._MATE_TYPES["gear"]
                )
                model.ClearSelection2(True)
                name = _sw_asm._mate_feature_name(adapter, mate)
                names.append((name, mate_label))
                results.append(
                    {
                        "name": name,
                        "mate_type": "gear",
                        "alignment": "closest",
                        "entities": 2,
                        "gear_ratio": ratio,
                    }
                )
                _telemetry.event("mate.created", label=mate_label, kind="gear")

        if not bool(adapter._attempt(lambda: model.EditRebuild3(), default=False)):
            raise RuntimeError(f"{label}: closing EditRebuild3 failed")
        for name, mate_label in names:
            error = _mate_hard_error(adapter, name)
            if error:
                raise RuntimeError(
                    f"{label}: {mate_label!r} has hard feature error {error}"
                )
    return results


async def cam_follower_mate(
    adapter: Any, cam_ref: Any, follower_ref: Any, *, label: str = "cam_follower"
) -> Any:
    """Cam-follower mate; the adapter applies the cam selection mark (8)."""
    return await _mate(adapter, label, "cam_follower", [cam_ref, follower_ref])


async def rack_pinion_mate(
    adapter: Any,
    rack_ref: Any,
    pinion_ref: Any,
    *,
    pinion_pitch_diameter: float = 0.0,
    rack_travel_per_revolution: float = 0.0,
    flip: bool = False,
    label: str = "rack_pinion",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Rack-pinion mate coupling a linear rack to a rotating pinion.

    ``rack_ref`` selects a linear rack edge/axis, ``pinion_ref`` the pinion's
    cylindrical face/axis. Set EITHER ``pinion_pitch_diameter`` (mm) OR
    ``rack_travel_per_revolution`` (mm) -- the adapter writes it into the mate
    definition (AddMate5 has no parameter for it). ``flip`` sets the mate's
    ``Reverse`` member when the solver's derived engagement sense runs the rack
    backward vs the physical tooth contact -- calibrate it from the
    verify:kinematics gate (the probe's signed feed assert), per the
    GEAR_SENSE/FEED_SIGN precedent.
    """
    return await _mate(
        adapter,
        label,
        "rack_pinion",
        [rack_ref, pinion_ref],
        pinion_pitch_diameter=pinion_pitch_diameter,
        rack_travel_per_revolution=rack_travel_per_revolution,
        flip=flip,
        verify=verify,
    )
