"""Saved-part display cleanup for semantic mating references."""

from __future__ import annotations

from typing import Any

import _telemetry


@_telemetry.traced("appearance.hide_reference_geometry")
def blank_reference_geometry(
    adapter: Any, references: tuple[tuple[str, str], ...]
) -> None:
    """Keep named planes/axes selectable while hiding them from saved renders."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    for index, (name, kind) in enumerate(references):
        selected = model.Extension.SelectByID2(
            name,
            kind,
            0,
            0,
            0,
            index > 0,
            0,
            null_callout(),
            0,
        )
        if not selected:
            raise RuntimeError(f"cannot select {name!r} to hide reference geometry")
    model.BlankRefGeom()
    model.ClearSelection2(True)
    _telemetry.success(f"blanked {len(references)} reference entities")
