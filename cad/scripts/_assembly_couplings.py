"""Specialized mechanical couplings, separate from shared placement and mates."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import _telemetry
from _assembly import _mate, _mate_hard_error, suspend_automatic_assembly_rebuilds
from _common import _MATE_TOL_MM, _early_bound

# swMateType_e.swMateTANGENT, swSelectType_e.swSelFACES, swBodyType_e.swSolidBody.
_SW_MATE_TANGENT = 4
_SW_SEL_FACES = 2
_SW_SOLID_BODY = 0
# ITangentMateFeatureData.EntitiesToMate remarks: tangent mate entities are
# pre-selected with Mark 1 -- both of them; the roles differ only by order.
_TANGENT_MARK = 1
# A modelled radius reads back exactly; a different face differs by far more.
_RADIUS_TOL_MM = 1e-3
# Sine of the angle a read-back axis may make with its modelled axis.
_AXIS_SIN_TOL = 1e-2
# swMateAlign_e.swMateAlignCLOSEST.
_SW_MATE_ALIGN_CLOSEST = 2


@dataclass(frozen=True)
class CylinderFace:
    """The one cylindrical face of radius ``radius_mm`` on ``component``.

    ``component`` is the component's ``Name2``.  ``axis_point_mm``/``axis``
    are the modelled axis in the assembly frame (millimetres), which the
    persisted mate entity must read back as.
    """

    component: str
    axis_point_mm: tuple[float, float, float]
    axis: tuple[float, float, float]
    radius_mm: float


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _axis_distance(point: Sequence[float], face: CylinderFace) -> float:
    """Distance from ``point`` to the modelled axis line of ``face``."""
    rel = [p - o for p, o in zip(point, face.axis_point_mm, strict=True)]
    return math.hypot(*_cross(rel, face.axis)) / math.hypot(*face.axis)


def _axis_sine(axis: Sequence[float], face: CylinderFace) -> float:
    """Sine of the angle between ``axis`` and the modelled axis of ``face``."""
    norm = math.hypot(*axis) * math.hypot(*face.axis)
    return math.hypot(*_cross(axis, face.axis)) / norm if norm else 1.0


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


async def tangent_contact_mate(
    adapter: Any,
    cam: CylinderFace,
    follower: CylinderFace,
    *,
    label: str = "tangent contact",
) -> dict[str, Any]:
    """Persist a standard tangent mate between two cylindrical faces, then prove it.

    Each face is the component part's only solid-body cylinder of its radius,
    mapped into the assembly with ``IComponent2.GetCorrespondingEntity`` --
    never a view-dependent point pick.  Both are selected under Mark 1, the
    ITangentMateFeatureData.EntitiesToMate remarks' pre-selection mark, and
    written cam-first as that property's ``object[]`` array (the generated
    wrapper declares it a writable VARIANT property, as in the SDK's
    *Create Standard Mates* example), then created and rebuilt like ``_mate``.
    The SDK lists cylinder face / cylinder face as a tangent combination.
    A refused ``CreateMate`` reports ``IMateFeatureData.ErrorStatus``: the
    CreateMate remarks make IMateFeatureData the base the mate-specific data is
    cast from, and ITangentMateFeatureData itself does not declare it.
    The persisted mate is read back as an unordered pair of the cam's and
    follower's modelled cylinders; SolidWorks may reorder symmetric mates.
    """
    from solidworks_mcp.adapters.com_variant import dispatch_array
    from solidworks_mcp.adapters.solidworks import assembly as _sw_asm

    if cam.component == follower.component:
        raise ValueError(f"{label}: cam and follower are both on {cam.component!r}")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    assembly = _early_bound(model, "IAssemblyDoc")
    async with _telemetry.aspan(label, kind="tangent", label=label):
        faces = [_component_cylinder(adapter, face, label) for face in (cam, follower)]
        selection = _early_bound(model.SelectionManager, "ISelectionMgr")
        model.ClearSelection2(True)
        for face, entity in zip((cam, follower), faces, strict=True):
            data = _early_bound(selection.CreateSelectData(), "ISelectData")
            data.Mark = _TANGENT_MARK
            if not bool(_early_bound(entity, "IEntity").Select4(True, data)):
                raise RuntimeError(f"{label}: cannot select the {face.component} face")
        selected = int(selection.GetSelectedObjectCount2(-1))
        if selected != 2:
            raise RuntimeError(f"{label}: {selected} entities selected, not 2")

        raw_data = adapter._attempt(
            lambda: assembly.CreateMateData(_SW_MATE_TANGENT), default=None
        )
        if raw_data is None:
            raise Exception(
                f"CreateMateData({_SW_MATE_TANGENT}) returned None for tangent mate"
            )
        mate_data = _early_bound(raw_data, "ITangentMateFeatureData")
        entities = []
        for index in (1, 2):
            entity = adapter._attempt(
                lambda i=index: selection.GetSelectedObject6(i, -1), default=None
            )
            if entity is None:
                raise Exception(f"{label}: mate entity {index} did not resolve")
            entities.append(entity)
        mate_data.EntitiesToMate = dispatch_array(entities)
        mate_data.MateAlignment = _SW_MATE_ALIGN_CLOSEST

        mate = adapter._attempt(lambda: assembly.CreateMate(mate_data), default=None)
        if mate is None:
            status = int(_early_bound(raw_data, "IMateFeatureData").ErrorStatus)
            reason = _sw_asm._MATE_ERRORS.get(status, f"error status {status}")
            raise Exception(f"CreateMate failed for tangent mate: {reason}")
        model.ClearSelection2(True)
        name = _sw_asm._mate_feature_name(adapter, mate)
        if not bool(model.EditRebuild3()):
            raise RuntimeError(f"{label}: EditRebuild3 failed after {name!r}")
        error = _mate_hard_error(adapter, name)
        if error:
            raise RuntimeError(f"{label}: {name!r} has hard feature error {error}")
        _assert_tangent_faces(adapter, label, name, cam, follower)
    return {"name": name, "mate_type": "tangent", "alignment": "closest"}


def _component_cylinder(adapter: Any, face: CylinderFace, label: str) -> Any:
    """Assembly-context entity of the only cylinder of ``face.radius_mm``.

    Radius is frame-free, so the part-space walk needs no transform; zero or
    several matches raise instead of guessing.
    """
    from solidworks_mcp.adapters.solidworks import assembly as _sw_asm

    component = _early_bound(
        _sw_asm._get_component(adapter, face.component), "IComponent2"
    )
    if component is None:
        raise RuntimeError(f"{label}: no component {face.component!r}")
    part = _early_bound(component.GetModelDoc2(), "IPartDoc")
    if part is None:
        raise RuntimeError(f"{label}: {face.component} has no loaded part document")
    matches = []
    for body in part.GetBodies2(_SW_SOLID_BODY, False) or ():
        for candidate in _early_bound(body, "IBody2").GetFaces() or ():
            surface = _early_bound(
                _early_bound(candidate, "IFace2").GetSurface(), "ISurface"
            )
            if surface is None or not bool(surface.IsCylinder()):
                continue
            radius = float(surface.CylinderParams[6]) * 1000.0
            if abs(radius - face.radius_mm) <= _RADIUS_TOL_MM:
                matches.append(candidate)
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: {face.component} has {len(matches)} cylinders of radius "
            f"{face.radius_mm:g} mm; the mate needs exactly one"
        )
    mapped = component.GetCorrespondingEntity(matches[0])
    if mapped is None:
        raise RuntimeError(f"{label}: {face.component} face has no assembly entity")
    return mapped


def _assert_tangent_faces(
    adapter: Any, label: str, name: str, cam: CylinderFace, follower: CylinderFace
) -> None:
    """Require the unordered native tangent pair to bind the intended cylinders.

    SOLIDWORKS may reorder a symmetric tangent mate's entities when saving it.
    Identify each role by its owning component, then verify its cylinder in
    assembly coordinates (metres); a duplicate or foreign owner fails closed.
    """
    if not name:
        raise RuntimeError(f"{label}: CreateMate returned no mate name")
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    feature = _early_bound(assembly.FeatureByName(name), "IFeature")
    if feature is None:
        raise RuntimeError(f"{label}: mate {name!r} is not in the assembly")
    mate = _early_bound(feature.GetSpecificFeature2(), "IMate2")
    if mate is None:
        raise RuntimeError(f"{label}: {name!r} has no IMate2 definition")
    mate_type = int(mate.Type)
    if mate_type != _SW_MATE_TANGENT:
        raise RuntimeError(f"{label}: {name!r} is swMateType {mate_type}, not tangent")
    count = int(mate.GetMateEntityCount())
    if count != 2:
        raise RuntimeError(f"{label}: {name!r} has {count} entities, not 2")
    roles = {cam.component: ("cam", cam), follower.component: ("follower", follower)}
    for index in range(count):
        entity = _early_bound(mate.MateEntity(index), "IMateEntity2")
        if entity is None:
            raise RuntimeError(f"{label}: {name!r} entity {index} did not resolve")
        owner = _early_bound(entity.ReferenceComponent, "IComponent2")
        component = str(owner.Name2) if owner is not None else ""
        if component not in roles:
            raise RuntimeError(
                f"{label}: {name!r} entity {index} is on {component!r}, "
                f"expected one each of {sorted(roles)}"
            )
        role, face = roles.pop(component)
        kind = int(entity.ReferenceType2)
        if kind != _SW_SEL_FACES:
            raise RuntimeError(
                f"{label}: {role} entity is swSelectType {kind}, not FACE"
            )
        params = [float(value) for value in entity.EntityParams]
        if len(params) < 7:
            raise RuntimeError(f"{label}: {role} face has no cylinder params {params}")
        point = [value * 1000.0 for value in params[0:3]]
        radius = params[6] * 1000.0
        if abs(radius - face.radius_mm) > _RADIUS_TOL_MM:
            raise RuntimeError(
                f"{label}: {role} face radius {radius:.4f} != {face.radius_mm:.4f} mm"
            )
        if _axis_sine(params[3:6], face) > _AXIS_SIN_TOL:
            raise RuntimeError(
                f"{label}: {role} face axis {params[3:6]} is off {face.axis}"
            )
        offset = _axis_distance(point, face)
        if offset > _MATE_TOL_MM:
            raise RuntimeError(
                f"{label}: {role} face axis sits {offset:.3f} mm off its model"
            )
    _telemetry.success(
        f"{label}: {name} binds {cam.component} cam OD to {follower.component} follower"
    )


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
