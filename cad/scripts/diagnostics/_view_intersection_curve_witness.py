"""Exact raw 3004 curve data for the diagnostic VIEW attachment observer only.

The source control zj92q9yo captured the actual PinHole INTERSECTION_TYPE as
IsBcurve with complete parameters. That is API evidence, not drawing-context
or cold equality evidence. Native IsSame and fresh role resolution remain
mandatory in the caller; equal coefficients never substitute for identity.
"""

from copy import deepcopy

from _common import _early_bound
from diagnostics import _raw_edge_curve as raw


def snapshot(entity, evidence):
    """Retain every raw return on rejection; do not sample, round or convert."""
    edge = _early_bound(entity, "IEdge")
    curve = edge.GetCurve()
    if curve is None:
        raise RuntimeError("VIEW intersection edge has no native curve")
    identity = _early_bound(curve, "ICurve").Identity()
    evidence["requested_identity"] = identity
    raw.integer(identity, 3004, 3004, "VIEW intersection curve identity")
    raw.read_edge(edge, evidence)
    if (
        evidence["identity"] != identity
        or evidence["trim"]["CurveType"] != identity
        or evidence["is_line"] is not False
        or evidence["is_circle"] is not False
        or evidence["is_bcurve"] is not True
        or evidence["bcurve_return"] != "ISplineParamData"
    ):
        raise RuntimeError("VIEW intersection curve type/representation changed")
    # Keep a detached initial bank so later native arrays cannot mutate it.
    # All numeric values and native statuses are preserved, including CurveTag,
    # edge sense and full parameter domains. No serialization epsilon applies.
    return ("intersection_curve", deepcopy(evidence))
