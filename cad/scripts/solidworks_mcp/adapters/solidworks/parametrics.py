"""Parametrics mixin for PyWin32 SolidWorks operations (Phase 4).

Implements equation-driven sketch curves (``ISketchManager::CreateEquationSpline2``),
equation-manager globals and driving equations (``IEquationMgr::Add3`` /
``SetEquationAndConfigurationOption``), and configuration management
(``IConfigurationManager::AddConfiguration2`` /
``IModelDoc2::ShowConfiguration2``).
"""

from __future__ import annotations

from typing import Any, cast

from ..base import (
    AdapterResult,
    AdapterResultStatus,
    CreateConfigurationParameters,
    CreateEquationCurveParameters,
    CreateEquationParameters,
    SetGlobalVariableParameters,
)
from ..com_variant import bstr_array, null_variant
from .features import _flag_feature_methods, _read_member

# swInConfigurationOpts_e
_ALL_CONFIGURATIONS = 2
_SPECIFY_CONFIGURATION = 3


class SolidWorksParametricsMixin:
    """Expose SolidWorks parametric-variant methods via mixin-local helpers."""

    async def create_equation_driven_curve(
        self, params: CreateEquationCurveParameters
    ) -> AdapterResult[str]:
        return _create_equation_driven_curve_impl(self, params)

    async def set_global_variable(
        self, params: SetGlobalVariableParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _set_global_variable_impl(self, params)

    async def create_equation(
        self, params: CreateEquationParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _create_equation_impl(self, params)

    async def create_configuration(
        self, params: CreateConfigurationParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _create_configuration_impl(self, params)

    async def set_active_configuration(
        self, name: str
    ) -> AdapterResult[dict[str, Any]]:
        return _set_active_configuration_impl(self, name)


def _active_configuration_name(adapter: Any) -> str:
    """Return the active configuration's name, or empty when unreadable.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.

    Returns:
        str: The active configuration name.
    """

    def _read() -> str:
        manager = adapter.currentModel.ConfigurationManager
        active = _read_member(manager, "ActiveConfiguration")
        return str(_read_member(active, "Name")) if active else ""

    return adapter._attempt(_read, default="") or ""


def _activate_configuration(adapter: Any, name: str) -> None:
    """Make ``name`` the active configuration (no-op when already active).

    ``IModelDoc2::ShowConfiguration2`` returns ``False`` both for unknown
    configurations and when the requested configuration is **already
    active** (live-verified on SW 2026), so the already-active case must be
    short-circuited before treating ``False`` as failure.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        name: Configuration name to activate.

    Raises:
        Exception: When SolidWorks cannot switch to the configuration.
    """
    if _active_configuration_name(adapter) == name:
        return
    if not bool(adapter.currentModel.ShowConfiguration2(name)):
        raise Exception(f"Failed to activate configuration: {name}")


def _equation_manager(adapter: Any) -> Any:
    """Return the model's method-flagged ``IEquationMgr``.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.

    Returns:
        Any: The equation manager dispatch.

    Raises:
        Exception: When the model exposes no equation manager.
    """
    manager = adapter._attempt(
        lambda: adapter.currentModel.GetEquationMgr(), default=None
    )
    if manager is None:
        raise Exception("Equation manager unavailable on the active model")
    return _flag_feature_methods(manager, "IEquationMgr")


def _configuration_scope(configuration: str) -> tuple[int, Any]:
    """Map a configuration name to ``Add3``'s scope arguments.

    Args:
        configuration: Configuration name, or empty for all configurations.

    Returns:
        tuple[int, Any]: ``(WhichConfigurations, ConfigNames)`` —
        ``swAllConfiguration`` with a typed-null array when empty,
        ``swSpecifyConfiguration`` with a BSTR SAFEARRAY otherwise.
    """
    if configuration:
        return _SPECIFY_CONFIGURATION, bstr_array([configuration])
    return _ALL_CONFIGURATIONS, null_variant()


def _equation_index_by_lhs(manager: Any, lhs: str) -> int:
    """Return the index of the equation whose left-hand side matches.

    Args:
        manager: Method-flagged ``IEquationMgr``.
        lhs: Exact left-hand side including embedded quotes, e.g.
            ``'"ToothCount"'``.

    Returns:
        int: 0-based equation index, or -1 when absent.
    """
    count = int(_read_member(manager, "GetCount") or 0)
    for index in range(count):
        text = str(manager.Equation(index) or "")
        head, _, _ = text.partition("=")
        if head.strip() == lhs:
            return index
    return -1


def _upsert_equation(adapter: Any, equation: str, configuration: str) -> dict[str, Any]:
    """Add the equation, or update it in place when its LHS already exists.

    Four live-verified quirks of the equation manager (SW 2026) shape this
    flow:

    1. ``Add3`` returns -1 on a model with a single configuration regardless
       of arguments — ``Add2`` is the only working add there, so it is the
       fallback (scope is moot with one configuration).
    2. Configuration-scoped calls (``swSpecifyConfiguration``) only succeed
       when the **target configuration is active**, so it is activated first
       and the manager re-acquired afterwards (required per the API remarks).
    3. ``SetEquationAndConfigurationOption`` returns -1 with
       ``swAllConfiguration`` scope — it only works for per-configuration
       replacement. Unscoped updates go through the ``Equation`` property
       put instead, which edits in place and cascades re-evaluation to
       referencing equations.
    4. ``Delete`` + re-add is NOT a viable update path: once any other
       equation references the variable, every re-add (``Add2``/``Add3``)
       returns -1 while the dangling reference exists.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        equation: Full equation text with embedded quoted names.
        configuration: Configuration scope; empty for all configurations.

    Returns:
        dict[str, Any]: ``index``, ``equation``, ``updated`` and ``value``.

    Raises:
        Exception: When SolidWorks rejects the equation.
    """
    if configuration:
        _activate_configuration(adapter, configuration)

    manager = _equation_manager(adapter)
    which, config_names = _configuration_scope(configuration)
    lhs, _, _ = equation.partition("=")
    existing = _equation_index_by_lhs(manager, lhs.strip())

    if existing >= 0 and configuration:
        index = int(
            manager.SetEquationAndConfigurationOption(
                existing, equation, which, config_names
            )
        )
        if index < 0:
            raise Exception(
                f"Failed to update equation for configuration "
                f"{configuration!r}: {equation}"
            )
        return _equation_payload(adapter, manager, index, equation, True)

    if existing >= 0:
        # Equation is an indexed property: early binding exposes Equation(i) as
        # the getter only; the PUT is the separate SetEquation(i, value) method.
        # Equation(i, value) as a put worked only under late binding.
        manager.SetEquation(existing, equation)
        written = str(manager.Equation(existing) or "")
        if "".join(written.split()) != "".join(equation.split()):
            raise Exception(f"Failed to update equation: {equation}")
        return _equation_payload(adapter, manager, existing, equation, True)

    index = int(manager.Add3(-1, equation, True, which, config_names))
    if index < 0:
        # Single-configuration models reject Add3 outright; Add2 is
        # equivalent there because one configuration is every configuration.
        index = int(manager.Add2(-1, equation, True))
    if index < 0:
        raise Exception(f"Failed to add equation: {equation}")
    return _equation_payload(adapter, manager, index, equation, False)


def _equation_payload(
    adapter: Any, manager: Any, index: int, equation: str, updated: bool
) -> dict[str, Any]:
    """Build the result payload for an equation upsert.

    Args:
        adapter: Connected adapter (for ``_attempt``).
        manager: Method-flagged ``IEquationMgr``.
        index: Row index of the equation.
        equation: The equation text written.
        updated: Whether an existing row was replaced.

    Returns:
        dict[str, Any]: ``index``, ``equation``, ``updated`` and ``value``.
    """
    value = adapter._attempt(lambda: manager.Value(index), default=None)
    return {
        "index": index,
        "equation": equation,
        "updated": updated,
        "value": float(value) if value is not None else None,
    }


def _create_equation_driven_curve_impl(
    adapter: Any, params: CreateEquationCurveParameters
) -> AdapterResult[str]:
    """Create an equation-driven curve in the active sketch.

    Calls ``ISketchManager::CreateEquationSpline2``. Expressions and the
    range are passed verbatim -- lengths evaluate in DOCUMENT units (not
    metres; see ``CreateEquationCurveParameters``), trig in radians; the
    rotation/offset legacy parameters are pinned to zero per the API
    remarks.

    Args:
        adapter: A ``PyWin32Adapter`` with an open sketch.
        params: Expressions, range and end-lock flags.

    Returns:
        AdapterResult[str]: Registered sketch-entity ID (e.g.
        ``"EquationCurve_1"``) or error.
    """
    if not adapter.currentSketchManager:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active sketch")

    def _curve_operation() -> str:
        segment = adapter.currentSketchManager.CreateEquationSpline2(
            params.x_expression,
            params.y_expression,
            params.z_expression,
            params.range_start,
            params.range_end,
            params.is_angle_range,
            0.0,  # RotationAngle — legacy positioning, unused
            0.0,  # XOffset — legacy positioning, unused
            0.0,  # YOffset — legacy positioning, unused
            params.lock_start,
            params.lock_end,
        )
        if not segment:
            raise Exception(
                "Failed to create equation-driven curve (check expression "
                "syntax and range)"
            )
        return cast(str, adapter._register_sketch_entity("EquationCurve", segment))

    return cast(
        AdapterResult[str],
        adapter._handle_com_operation("create_equation_driven_curve", _curve_operation),
    )


def _set_global_variable_impl(
    adapter: Any, params: SetGlobalVariableParameters
) -> AdapterResult[dict[str, Any]]:
    """Add or update a global variable assignment.

    Builds the ``"name" = expression`` equation text and upserts it through
    the equation manager. When ``configuration`` is set, that configuration
    is **activated** as a side effect (configuration-scoped equation calls
    only succeed on the active configuration).

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Variable name (unquoted), RHS expression, scope.

    Returns:
        AdapterResult[dict[str, Any]]: Equation index/text/value or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _global_operation() -> dict[str, Any]:
        equation = f'"{params.name}" = {params.expression}'
        return _upsert_equation(adapter, equation, params.configuration)

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("set_global_variable", _global_operation),
    )


def _create_equation_impl(
    adapter: Any, params: CreateEquationParameters
) -> AdapterResult[dict[str, Any]]:
    """Add or update a full driving equation.

    When ``configuration`` is set, that configuration is **activated** as a
    side effect (configuration-scoped equation calls only succeed on the
    active configuration).

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Equation text (quoted names embedded) and scope.

    Returns:
        AdapterResult[dict[str, Any]]: Equation index/text/value or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _equation_operation() -> dict[str, Any]:
        return _upsert_equation(adapter, params.equation, params.configuration)

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("create_equation", _equation_operation),
    )


def _create_configuration_impl(
    adapter: Any, params: CreateConfigurationParameters
) -> AdapterResult[dict[str, Any]]:
    """Create a configuration via ``IConfigurationManager::AddConfiguration2``.

    The new configuration becomes the active one (SolidWorks activates it on
    creation); ``Rebuild`` is requested so configured values resolve.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Configuration name, comment, parent, description.

    Returns:
        AdapterResult[dict[str, Any]]: Created configuration name or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _configuration_operation() -> dict[str, Any]:
        manager = adapter._attempt(
            lambda: adapter.currentModel.ConfigurationManager, default=None
        )
        if manager is None:
            raise Exception("Configuration manager unavailable on the active model")
        manager = _flag_feature_methods(manager, "IConfigurationManager")

        configuration = manager.AddConfiguration2(
            params.name,
            params.comment,
            "",  # AlternateName — unused without swConfigOption_UseAlternateName
            0,  # Options — no suppress/hide/alternate-name behaviour
            params.parent,
            params.description,
            True,  # Rebuild so configured values resolve immediately
        )
        if configuration is None:
            raise Exception(f"Failed to create configuration: {params.name}")
        name = str(_read_member(configuration, "Name") or params.name)
        return {"name": name, "parent": params.parent}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("create_configuration", _configuration_operation),
    )


def _set_active_configuration_impl(
    adapter: Any, name: str
) -> AdapterResult[dict[str, Any]]:
    """Activate a configuration and force-rebuild the model.

    ``IModelDoc2::ShowConfiguration2`` switches the active configuration;
    the follow-up rebuild must be ``ForceRebuild3(False)`` — a plain
    ``EditRebuild3`` only rebuilds features flagged dirty and leaves
    equation-driven curve geometry (``CreateEquationSpline2`` profiles
    referencing global variables) at the previous configuration's shape
    (observed live on SW 2026: the sketch kept stale coordinates and the
    dependent cut removed nothing until a force rebuild).

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        name: Configuration name to activate.

    Returns:
        AdapterResult[dict[str, Any]]: Activation/rebuild flags or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _activate_operation() -> dict[str, Any]:
        _activate_configuration(adapter, name)
        rebuilt = bool(
            adapter._attempt(
                lambda: adapter.currentModel.ForceRebuild3(False), default=False
            )
        )
        if not rebuilt:
            rebuilt = bool(
                adapter._attempt(
                    lambda: adapter.currentModel.EditRebuild3(), default=False
                )
            )
        return {"name": name, "rebuilt": rebuilt}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("set_active_configuration", _activate_operation),
    )
