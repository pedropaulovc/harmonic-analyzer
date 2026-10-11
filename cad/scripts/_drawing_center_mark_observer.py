"""Process-global drawing center-mark observation.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
import _telemetry
from solidworks_mcp.adapters.solidworks import drawing as _sw_drawing


def _record_center_marks(counts: dict[str, Any]) -> None:
    """Every auto_center_marks call's centre-mark count, before and after
    AutoInsertCenterMarks2, as a span event (#913: each mark printed twice on
    30 views). after == 2 x before would point at a template auto-insert the
    explicit call repeats; before == 0 at duplicates made some other way.

    The observer is process-global and set when this module is imported, so
    a script that never imports _drawing_center_mark_observer records nothing (every
    auto_center_marks caller does). OTel attributes must be primitives: a
    count whose read raised arrives as None and is sent as -1, named in
    ``read_failed``.
    """
    attributes = {key: value for key, value in counts.items() if value is not None}
    failed = sorted(key for key, value in counts.items() if value is None)
    for key in failed:
        attributes[key] = -1
    if failed:
        attributes["read_failed"] = failed
    _telemetry.event("center_marks.auto_insert", **attributes)
    _telemetry.debug(
        f"center marks {counts.get('view')!r}: {counts.get('before')} -> {counts.get('after')}"
        f" (holes={counts.get('holes')}, slots={counts.get('slots')}, ok={counts.get('ok')})"
    )


_sw_drawing.CENTER_MARK_OBSERVER = _record_center_marks
