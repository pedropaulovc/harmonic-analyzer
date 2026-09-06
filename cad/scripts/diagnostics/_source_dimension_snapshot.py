"""Read the observed native source-dimension inventory without model mutation.

Extracted from the native-proven first-dirty probe (99eadbe7). Feature/display
enumeration is bounded, unsorted by the API and not a full BREP identity proof.
No visibility toggle or rebuild is added; explicitly required manufacturing
parameters must be observed. Exact native handle checks apply only while that
same document remains open, never across close/reopen.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from types import SimpleNamespace

from _common import _early_bound, _iter_features, _read_member


def tolerance(dimension):
    raw = dimension.Tolerance
    if raw is None:
        raise RuntimeError("dimension has no native tolerance interface")
    native = _early_bound(raw, "IDimensionTolerance")
    current, legacy = int(native.Type), int(dimension.GetToleranceType())
    if current != legacy:
        raise RuntimeError(
            f"native/legacy tolerance getters disagree: {current}/{legacy}"
        )
    return {
        "tolerance_type": current,
        "designation": "basic" if current == 1 else "other",
    }


def display_inventory(displays):
    return Counter(
        (row["feature"], row["dimension_type"], row["index"], row["marked_for_drawing"])
        for row in displays
    )


def compare_source(before, after, *, app=None, handles_before=None, handles_after=None):
    """Allow recorded presentation changes, never native parameter/identity drift."""
    if (
        before["configuration"] != after["configuration"]
        or sorted(before["features"]) != sorted(after["features"])
        or before["dimensions"].keys() != after["dimensions"].keys()
    ):
        raise RuntimeError("source configuration/feature/dimension inventory changed")
    changes = {}
    for name, old in before["dimensions"].items():
        new = after["dimensions"][name]
        if old["native"] != new["native"]:
            raise RuntimeError(f"source value/tolerance/BASIC changed: {name}")
        if display_inventory(old["displays"]) != display_inventory(new["displays"]):
            raise RuntimeError(
                f"source display identity/type/marking inventory changed: {name}"
            )
        if handles_before is not None:
            if (
                app is None
                or handles_after is None
                or name not in handles_after
                or int(app.IsSame(handles_before[name], handles_after[name])) != 1
            ):
                raise RuntimeError(f"source native dimension identity changed: {name}")
        if old["displays"] != new["displays"]:
            changes[name] = {"before": old["displays"], "after": new["displays"]}
    return changes


def finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise RuntimeError("source dimension contains a non-finite value")
    return value


def dimension_snapshot(app, model, path, *, required):
    """Read every observed feature dimension; do not toggle visibility or rebuild."""
    configuration = str(
        _early_bound(
            _early_bound(
                model.ConfigurationManager, "IConfigurationManager"
            ).ActiveConfiguration,
            "IConfiguration",
        ).Name
    )
    if not configuration:
        raise RuntimeError("source snapshot has no active configuration")
    rows, handles, features = {}, {}, []
    for feature in _iter_features(SimpleNamespace(currentModel=model)):
        feature = _early_bound(feature, "IFeature")
        feature_name = str(_read_member(feature, "Name"))
        features.append(feature_name)
        if len(features) >= 5000:
            raise RuntimeError("source feature enumeration reached its bound")
        display = _read_member(feature, "GetFirstDisplayDimension")
        seen = []
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            if len(seen) >= 1000 or any(
                int(app.IsSame(display, item)) == 1 for item in seen
            ):
                raise RuntimeError(
                    "source display-dimension enumeration repeats/exceeds bound"
                )
            seen.append(display)
            kind = int(display.Type2)
            # GetDimension2 index 1 is meaningful only for swChamferDimension.
            for index in range(2 if kind == 10 else 1):
                dimension = _early_bound(display.GetDimension2(index), "IDimension")
                if dimension is None:
                    raise RuntimeError(
                        "source display dimension has no model dimension"
                    )
                name = str(dimension.FullName)
                if not name.casefold().endswith(f"@{path.stem}.Part".casefold()):
                    raise RuntimeError(
                        f"source dimension has wrong exact part owner: {name}"
                    )
                values = tuple(dimension.GetSystemValue3(3, configuration) or ())
                if len(values) != 1:
                    raise RuntimeError(
                        f"source dimension value count is not one: {name}"
                    )
                tol = _early_bound(dimension.Tolerance, "IDimensionTolerance")
                native = {
                    "value_system": finite(values[0]),
                    **tolerance(dimension),
                    # Existing supported getter shape, no alternate-call fallback.
                    "tolerance_min": finite(tol.GetMinValue()),
                    "tolerance_max": finite(tol.GetMaxValue()),
                }
                if name in handles and int(app.IsSame(handles[name], dimension)) != 1:
                    raise RuntimeError(
                        f"source dimension name has ambiguous native identity: {name}"
                    )
                if name in rows and rows[name]["native"] != native:
                    raise RuntimeError(
                        f"source dimension changed during one snapshot: {name}"
                    )
                rows.setdefault(name, {"native": native, "displays": []})
                handles[name] = dimension
                rows[name]["displays"].append(
                    {
                        "feature": feature_name,
                        "dimension_type": kind,
                        "index": index,
                        "marked_for_drawing": bool(display.MarkedForDrawing),
                        "primary_precision": int(display.GetPrimaryPrecision2()),
                        "tolerance_precision": int(display.GetPrimaryTolPrecision2()),
                        "text": {
                            str(part): str(display.GetText(part) or "")
                            for part in range(1, 9)
                        }
                        if not display.IsHoleCallout()
                        else {"exclusion": "GetText does not support hole callouts"},
                    }
                )
            display = feature.GetNextDisplayDimension(display)
    required = {
        f"{name}@{feature}" for feature, names in required.items() for name in names
    }
    observed = {name.rsplit("@", 1)[0] for name in rows}
    if required - observed:
        raise RuntimeError(
            f"source dimension inventory misses manufacturing dimensions: {sorted(required - observed)}"
        )
    for row in rows.values():
        row["displays"].sort(key=lambda item: json.dumps(item, sort_keys=True))
    return {
        "configuration": configuration,
        "features": sorted(features),
        "dimensions": rows,
    }, handles
