"""Saved-document reference visibility checks across configurations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import _telemetry
from _visibility import assert_reference_geometry_hidden


@_telemetry.traced(
    "appearance.assert_reference_geometry_hidden_every_configuration",
    label_param="label",
)
def assert_reference_geometry_hidden_in_every_configuration(
    adapter: Any, label: str, allowed: Mapping[str, str] | None = None
) -> None:
    """Run :func:`assert_reference_geometry_hidden` with each configuration active.

    Hide/show is per configuration and ``IFeature.Visible`` reads the active
    one: the cone gear's pattern axis, blanked with T120 active, passed the
    single-configuration check and rendered in T006..T114 (7e88be269).  Every
    configuration is checked, one error names them all, and the originally
    active configuration is active again at the end.  ``allowed`` applies to
    each configuration, so an allowance must be shown in all of them.
    """
    from _com import _early_bound
    from _rebuild import active_configuration_name

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    original = active_configuration_name(adapter, model)
    names = [str(name) for name in (model.GetConfigurationNames() or ())]
    if original not in names:
        raise RuntimeError(f"{label}: active configuration {original!r} not in {names}")
    problems: list[str] = []
    for name in [name for name in names if name != original] + [original]:
        if active_configuration_name(adapter, model) != name and not bool(
            model.ShowConfiguration2(name)
        ):
            problems.append(f"{name}: ShowConfiguration2 refused")
            continue
        try:
            assert_reference_geometry_hidden(adapter, f"{label} [{name}]", allowed)
        except RuntimeError as exc:
            problems.append(str(exc))
    if problems:
        raise RuntimeError(f"{label}: " + "; ".join(problems))
