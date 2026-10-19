"""Read and log native Hole Wizard data before the pin's release assertions."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import _telemetry


def read_hole_wizard_metadata(definition: Any, *, label: str) -> SimpleNamespace:
    """Log every native scalar once, then re-raise any failed property read."""
    values: dict[str, Any] = {}
    first_error: Exception | None = None
    for member in (
        "Type",
        "FastenerType2",
        "Standard2",
        "FastenerSize",
        "ThreadClass",
        "ThruTapDrillDiameter",
        "EndCondition",
        "ThreadEndCondition",
    ):
        try:
            values[member] = getattr(definition, member)
        except Exception as exc:
            values[member] = f"<{type(exc).__name__}: {exc}>"
            if first_error is None:
                first_error = exc
    # INFO is hidden from task.log at the farm's default warning verbosity.
    _telemetry.warn(
        f"{label} native Hole Wizard readback (drill in metres): {values!r}",
        label=label,
        drill_units="m",
        **values,
    )
    _telemetry.event(
        "hole_wizard.native_metadata",
        label=label,
        drill_units="m",
        **values,
    )
    if first_error is not None:
        raise first_error
    return SimpleNamespace(**values)
