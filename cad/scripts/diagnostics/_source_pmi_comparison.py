"""Source annotation serialization coordinates, never source geometry tolerance.

Only cold position_m XYZ leaves receive the existing 16-ULP / 1e-14 m caps.
ULP scale is the finite position vector's largest component, so near-zero axes
are not treated as independent length scales. Same-session comparisons are exact.
All content, native identity witnesses, types, keys and ordering remain exact.
"""

from enum import StrEnum
import math

from diagnostics._reopen_annotation_comparison import (
    MAX_COORDINATE_DELTA_M,
    MAX_COORDINATE_ULPS,
    compare_reopened_annotations,
)


class SourcePmiBoundary(StrEnum):
    LIVE = "same_session"
    COLD = "cold_reopen"


def compare_source_pmi(before, after, *, boundary):
    boundary = SourcePmiBoundary(boundary)
    if type(before) is not list or type(after) is not list:
        raise TypeError("source PMI inventories must be lists")
    # This path is outside the drawing comparator's coordinate whitelist. Reuse
    # its exact structural/type/nonfinite audit, not its drawing-leaf tolerance.
    exact = compare_reopened_annotations({"source_pmi": before}, {"source_pmi": after})
    if exact["coordinate_roundoff"]:
        raise RuntimeError("source PMI unexpectedly matched a drawing-coordinate path")
    budgets = {}
    if boundary == SourcePmiBoundary.COLD:
        # The exact comparator already reports a length mismatch as rejected.
        # Pair the overlap only; strict=True would discard that failure receipt.
        for index, (old, new) in enumerate(zip(before, after, strict=False)):
            if type(old) is not dict or type(new) is not dict:
                continue
            first, last = old.get("position_m"), new.get("position_m")
            if type(first) not in (list, tuple) or type(last) is not type(first):
                continue
            if len(first) != 3 or len(last) != 3:
                continue
            if any(type(value) is not float for value in (*first, *last)):
                continue
            scale = max(abs(value) for value in (*first, *last))
            budget = min(MAX_COORDINATE_DELTA_M, MAX_COORDINATE_ULPS * math.ulp(scale))
            for axis in range(3):
                budgets[f"/source_pmi/{index}/position_m/{axis}"] = (scale, budget)
    rejected, roundoff = [], []
    for change in exact["rejected"]:
        rule = budgets.get(change["path"])
        if (
            rule is not None
            and change["kind"] == "numeric"
            and type(change["before"]) is float
            and type(change["after"]) is float
        ):
            scale, budget = rule
            change = {
                **change,
                "position_vector_scale_m": scale,
                "coordinate_budget_m": budget,
            }
            if abs(change["delta"]) <= budget:
                roundoff.append(change)
                continue
        rejected.append(change)
    return {
        "status": "failed" if rejected else "passed",
        "boundary": boundary.value,
        "rejected": rejected,
        "coordinate_roundoff": roundoff,
        "scope": "source PMI position serialization only; all other fields exact; source dimension/geometry/hash gates remain separate",
    }
