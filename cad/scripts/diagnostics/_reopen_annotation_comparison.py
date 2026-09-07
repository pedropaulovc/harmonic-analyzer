"""Cold-reopen annotation coordinates, separate from exact live/audit contracts.

The retained rocker audit has 187 coordinate differences no larger than eight
binary64 ULP and 1.943e-16 m, plus three real 7.225 mm title-origin differences.
Only explicitly mapped coordinate leaves get a 16-ULP AND 1e-14 m bound. This
is a narrow representation budget, not a manufacturing/layout tolerance. Raw
values and all differences are retained; unknown fields remain exact. Arc arrays
and text planes mix quantities and are deliberately not mapped.

This compares annotation observations, not persistent attachment identity. The
caller's existing source, attachment-signature and layout gates remain required.
Same-geometry reattachment needs a separate persistent-reference witness.
"""

from __future__ import annotations

import math

from diagnostics.audit_drawing_snapshot_delta import _pointer

MAX_COORDINATE_DELTA_M = 1e-14
MAX_COORDINATE_ULPS = 16
_RECT_FIELDS = frozenset({"xmin", "ymin", "xmax", "ymax"})


def _coordinate_path(path):
    """Path within one annotation row; never infer units from a numeric value."""
    match path:
        case ("position", int(axis)):
            return axis in (0, 1, 2)
        case ("native" | "measurement", "anchor", int(axis)):
            return axis in (0, 1)
        case ("generic", "texts", int(), "position", int(axis)):
            return axis in (0, 1, 2)
        case ("native" | "measurement", "text_runs", int(), "position", int(axis)):
            return axis in (0, 1)
        # IDisplayData.GetLineAtIndex3: color, type, style, weight, start/end XYZ.
        case ("generic", "lines", int(), int(slot)):
            return slot in (4, 5, 6, 7, 8, 9)
        case ("native", "lines" | "leaders", int(), "start" | "end", int(axis)):
            return axis in (0, 1)
        case (
            "measurement",
            "leader_segments" | "native_strokes" | "native_leader_segments",
            int(),
            "start" | "end",
            int(axis),
        ):
            return axis in (0, 1)
        case ("measurement", "body" | "envelope", field):
            return field in _RECT_FIELDS
        case ("measurement", "text_boxes" | "leader_decorations", int(), field):
            return field in _RECT_FIELDS
        case ("native", "leader_boxes" | "primitive_boxes", int(), field):
            return field in _RECT_FIELDS
        case ("native", "note_extent", int(axis)):
            return axis in (0, 1, 2, 3)
    return False


def compare_reopened_annotations(before, after):
    """Return exact rejected deltas and bounded coordinate deltas separately.

    Container types, keys, lengths and ordering remain significant. Numeric type
    changes (including bool/int and int/float) never receive a coordinate budget.
    Nonfinite observations fail even when both snapshots contain the same value.
    """
    rejected, roundoff = [], []

    def emit(path, kind, old, new):
        row = {"path": _pointer(path), "kind": kind, "before": old, "after": new}
        if kind == "numeric":
            row["delta"] = new - old
        if (
            kind == "numeric"
            and type(old) is float
            and type(new) is float
            and _coordinate_path(path[1:])
        ):
            budget = min(
                MAX_COORDINATE_DELTA_M,
                MAX_COORDINATE_ULPS * max(math.ulp(old), math.ulp(new)),
            )
            row["coordinate_budget_m"] = budget
            if abs(new - old) <= budget:
                roundoff.append(row)
                return
        rejected.append(row)

    def validate(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("cold-reopen snapshot contains a nonfinite value")
        if isinstance(value, dict):
            if any(type(key) is not str for key in value):
                raise TypeError("cold-reopen snapshot requires string dictionary keys")
            for item in value.values():
                validate(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                validate(item)
            return
        if type(value) not in (str, bool, int, float, type(None)):
            raise TypeError(f"unsupported cold-reopen snapshot type: {type(value)}")

    def walk(old, new, path):
        if type(old) is not type(new):
            emit(path, "type", old, new)
            return
        if isinstance(old, dict):
            for key in sorted(old.keys() | new.keys()):
                if key not in old or key not in new:
                    missing = {"missing": True}
                    emit(
                        path + (key,),
                        "missing",
                        old.get(key, missing),
                        new.get(key, missing),
                    )
                    continue
                walk(old[key], new[key], path + (key,))
            return
        if isinstance(old, (list, tuple)):
            if len(old) != len(new):
                emit(path, "length", len(old), len(new))
            for index in range(max(len(old), len(new))):
                if index >= len(old):
                    emit(path + (index,), "missing", {"missing": True}, new[index])
                    continue
                if index >= len(new):
                    emit(path + (index,), "missing", old[index], {"missing": True})
                    continue
                walk(old[index], new[index], path + (index,))
            return
        if old != new:
            emit(path, "numeric" if type(old) in (int, float) else "value", old, new)

    if type(before) is not dict or type(after) is not dict:
        raise TypeError("cold-reopen annotation inventories must be dictionaries")
    validate(before)
    validate(after)
    walk(before, after, ())
    return {
        "status": "failed" if rejected else "passed",
        "rejected": rejected,
        "coordinate_roundoff": roundoff,
        "scope": "annotation observations only; attachment/source gates remain separate",
    }
