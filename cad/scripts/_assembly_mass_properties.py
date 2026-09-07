"""Strict mass-property reads from an already-resolved active assembly.

No activation, rebuild, save, cached native object, or fallback read occurs here.
The caller owns the COM seat and document and supplies their expected identity.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import _telemetry
from _common import _early_bound, active_configuration_name

if TYPE_CHECKING:
    from solidworks_mcp.adapters.base import MassProperties


def _assert_resolved_state(adapter: Any, model: Any, configuration: str) -> None:
    if model is None or not configuration:
        raise RuntimeError("mass-property read requires a model and configuration")
    app = _early_bound(adapter.swApp, "ISldWorks")
    current = adapter.currentModel
    active = app.ActiveDoc
    if current is None or active is None:
        raise RuntimeError("mass-property read requires an active document")
    if int(app.IsSame(model, current)) != 1 or int(app.IsSame(model, active)) != 1:
        raise RuntimeError("mass-property read document identity changed")
    actual = active_configuration_name(adapter, model)
    if actual != configuration:
        raise RuntimeError(
            f"mass-property read configuration {actual!r}, expected {configuration!r}"
        )
    extension = _early_bound(model.Extension, "IModelDocExtension")
    if extension is None:
        raise RuntimeError("mass-property read has no model extension")
    status = extension.NeedsRebuild2
    if status is None or int(status) != 0:
        raise RuntimeError(f"mass-property read requires resolved state; NeedsRebuild2={status}")


def _finite_values(raw: Any, count: int, label: str) -> list[float]:
    if not isinstance(raw, (list, tuple)) or len(raw) != count:
        raise RuntimeError(f"mass-property {label} requires exactly {count} values")
    try:
        values = [float(value) for value in raw]
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError(f"mass-property {label} contains a nonnumeric value") from error
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"mass-property {label} contains a nonfinite value")
    return values


def read_resolved_mass_properties(
    adapter: Any, *, expected_model: Any, expected_configuration: str
) -> MassProperties:
    """Return adapter-unit mass properties without another whole-model rebuild.

    The configuration and native document must remain the expected, fully rebuilt
    ones throughout the read. Units and inertia order match get_mass_properties;
    the caller retains ownership of fingerprint rounding and component-pose rows.
    """
    from solidworks_mcp.adapters.base import MassProperties

    model = _early_bound(expected_model, "IModelDoc2")
    _assert_resolved_state(adapter, model, expected_configuration)
    with _telemetry.span(
        "assembly.mass_properties.direct_read", configuration=expected_configuration
    ):
        extension = _early_bound(model.Extension, "IModelDocExtension")
        raw = extension.CreateMassProperty()
        if raw is None:
            raise RuntimeError("CreateMassProperty returned no mass-property object")
        mass = _early_bound(raw, "IMassProperty")
        volume, area, weight = _finite_values(
            [mass.Volume, mass.SurfaceArea, mass.Mass], 3, "volume/area/mass"
        )
        center = _finite_values(mass.CenterOfMass, 3, "center of mass")
        inertia = _finite_values(mass.GetMomentOfInertia(0), 9, "inertia")
        volume, area, weight = _finite_values(
            [volume * 1e9, area * 1e6, weight], 3, "converted volume/area/mass"
        )
        center = _finite_values([value * 1000 for value in center], 3, "converted center")
    _assert_resolved_state(adapter, model, expected_configuration)
    return MassProperties(
        volume=volume,
        surface_area=area,
        mass=weight,
        center_of_mass=center,
        moments_of_inertia={
            key: inertia[index]
            for key, index in (
                ("Ixx", 0), ("Iyy", 4), ("Izz", 8),
                ("Ixy", 1), ("Ixz", 2), ("Iyz", 5),
            )
        },
    )
