r"""Diagnostic: rebuild the McMaster-Carr reference fasteners from scratch --
the fleet-wide successor of ``diag_build_91829A560.py`` (which stays as the
validated single-part original).

Every replica is a PURE reverse-engineering of its vendor model in
``cad/references/mcmaster/``: all numbers come from that part's harvest JSON
(``diag_dump_part.py`` -> ``cad/out/reports/mcmaster-<part>-dump.json``) or
were read live off the open vendor document -- nothing is imported from the
repo's part specs.  Gates run against the vendor's own mass properties and
face-area multiset, loaded from the same harvest (see
``diag_mcmaster_lib.gate_and_save``).

Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\diag_build_mcmaster.py 90126A211
    uv run python cad\scripts\diagnostics\diag_build_mcmaster.py --all

Output (replica .SLDPRT + report JSON + render pairs) goes to the gitignored
``cad/out/reference/``.  The McMaster files are (c) McMaster-Carr,
reference-only: opened read-only for the render pair, never saved.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    check,
    define_circle,
    extrude_at_offset,
    name_last_feature,
    run_build,
    volume_check,
)
from diag_mcmaster_lib import (  # noqa: E402
    close_all,
    gate_and_save,
    render_vendor,
    vendor_truth,
)

# swFeatureFilletOptions_e
FILLET_ASYMMETRIC = 16384
FILLET_UNIFORM = 2
FILLET_PROPAGATE = 1
# swFeatureFilletType_e.swFeatureFilletType_Simple / profile Circular
FILLET_SIMPLE = 0
FILLET_PROFILE_CIRCULAR = 0  # elliptical when asymmetric


def _asymmetric_fillet(adapter, edge_points_mm, r1_mm: float, r2_mm: float,
                       feature_name: str):
    """Constant asymmetric (elliptical) fillet on the edges at the given
    points -- FeatureFillet3, which the adapter's symmetric add_fillet
    cannot express."""
    from solidworks_mcp.adapters.solidworks.features import (
        _flag_feature_methods,
        _select_by_point,
    )

    model = adapter.currentModel
    model.ClearSelection2(True)
    for i, pt in enumerate(edge_points_mm):
        if not _select_by_point(adapter, "EDGE", list(pt), 0, i > 0):
            raise RuntimeError(f"cannot select fillet edge at {pt}")
    fm = _flag_feature_methods(
        model.FeatureManager, "IFeatureManager", "FeatureFillet3")
    with _telemetry.span("feature.asymmetric_fillet", label=feature_name):
        feat = fm.FeatureFillet3(
            FILLET_ASYMMETRIC | FILLET_UNIFORM | FILLET_PROPAGATE,
            r1_mm / 1000.0,
            r2_mm / 1000.0,
            0.0,  # Rho
            FILLET_SIMPLE,
            0,    # OverflowType default
            FILLET_PROFILE_CIRCULAR,
            None, None, None, None, None, None, None,
        )
    model.ClearSelection2(True)
    if feat is None:
        raise RuntimeError(f"FeatureFillet3 returned None for {feature_name}")
    name_last_feature(adapter, feature_name)
    return feat


# --------------------------------------------------------------------------
# 90126A211 -- zinc-plated steel SAE washer for 1/2" screws
# Vendor tree: annulus sketch -> midplane Boss-Extrude1 -> asymmetric rim
# fillet (Fillet1: D1 0.34671 radial x D2 0.173355 axial, equations
# D2 = thickness*0.07, D1 = D2*2).
# --------------------------------------------------------------------------
W_OD = 26.9748  # OD@Sketch1 (diametric)
W_ID = 13.4874  # ID@Sketch1 (diametric)
W_T = 2.4765    # Thickness Range@Sketch2
W_F1 = 0.34671  # D1@Fillet1 (radial leg)
W_F2 = 0.173355  # D2@Fillet1 (axial leg)


async def build_90126A211(adapter, truth):
    check("create_sketch annulus", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, W_OD / 2.0, "washer OD")
    await define_circle(adapter, 0.0, 0.0, W_ID / 2.0, "washer ID")
    check("exit_sketch annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "AnnulusProfile")
    extrude_at_offset(adapter, W_T, -W_T / 2.0)
    name_last_feature(adapter, "WasherBody")
    v = math.pi * ((W_OD / 2.0) ** 2 - (W_ID / 2.0) ** 2) * W_T
    await volume_check(adapter, "washer annulus", v, 0.005 * v)

    # The four rim edges: OD and ID, top and bottom.
    h = W_T / 2.0
    _asymmetric_fillet(adapter, [
        (W_OD / 2.0, h, 0.0),
        (W_OD / 2.0, -h, 0.0),
        (W_ID / 2.0, h, 0.0),
        (W_ID / 2.0, -h, 0.0),
    ], W_F1, W_F2, "RimFillet")

    # Replica frame: extrude axis = model Y, vendor frame: axis = Z.
    adapter._mcm_com_map = lambda v: [v[0], v[2], v[1]]


REGISTRY = {
    "90126A211": build_90126A211,
}


def _selected_parts() -> list[str]:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv[1:]:
        return list(REGISTRY)
    if not args:
        raise SystemExit(
            f"usage: diag_build_mcmaster.py <part_no>...|--all "
            f"(known: {', '.join(REGISTRY)})")
    unknown = [a for a in args if a not in REGISTRY]
    if unknown:
        raise SystemExit(f"no builder for: {', '.join(unknown)} "
                         f"(known: {', '.join(REGISTRY)})")
    return args


async def build(adapter) -> dict[str, str]:
    artefacts: dict[str, str] = {}
    for part_no in _selected_parts():
        truth = vendor_truth(part_no)
        with _telemetry.span("replica.build", label=part_no):
            check(f"create_part {part_no}", await adapter.create_part())
            await REGISTRY[part_no](adapter, truth)
            artefacts.update(await gate_and_save(adapter, part_no, truth))
            await close_all(adapter)
            artefacts.update(await render_vendor(adapter, part_no))
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
