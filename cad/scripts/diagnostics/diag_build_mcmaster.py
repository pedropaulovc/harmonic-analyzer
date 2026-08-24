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

async def _asymmetric_fillet(adapter, edge_points_mm, r1_mm: float,
                             r2_mm: float, conic_rho: float,
                             feature_name: str, reverse: bool = False):
    """Constant asymmetric conic fillet: author a plain symmetric fillet
    through the adapter's proven path, then EDIT its definition via
    ISimpleFilletFeatureData2 (the same API the dump reads).

    Direct FeatureFillet3 authoring proved non-deterministic on this
    build -- runs with identical arguments produced different leg
    orientations (the positional call partially inherits SolidWorks
    session defaults), so the replica goes create-then-modify instead."""
    from _common import _early_bound, _feature_by_name

    check(f"fillet base {feature_name}", await adapter.add_fillet(
        r1_mm, [list(p) for p in edge_points_mm]))
    name_last_feature(adapter, feature_name)
    model = adapter.currentModel
    feat = _feature_by_name(adapter, feature_name)
    data = _early_bound(feat.GetDefinition(), "ISimpleFilletFeatureData2")
    if not data.AccessSelections(model, None):
        raise RuntimeError(f"AccessSelections failed for {feature_name}")
    data.AsymmetricFillet = True
    data.DefaultRadius = r1_mm / 1000.0
    data.DefaultDistance = r2_mm / 1000.0
    data.ConicTypeForCrossSectionProfile = 1  # swFeatureFilletConicRho
    data.DefaultConicRhoOrRadius = conic_rho
    if reverse:
        # Indexed property (WhichFaceList) -- flips Direction 1/2 for the
        # feature's face list; single-edge features use list 0.
        data.SetReverseFaceNormal(0, True)
    if not feat.ModifyDefinition(data, model, None):
        raise RuntimeError(f"ModifyDefinition failed for {feature_name}")
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
W_RHO = 0.65    # Fillet1 conic rho (conic_type=1 in the harvest)


async def build_90126A211(adapter, truth):
    check("create_sketch annulus", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, W_OD / 2.0, "washer OD")
    await define_circle(adapter, 0.0, 0.0, W_ID / 2.0, "washer ID")
    check("exit_sketch annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "AnnulusProfile")
    # MIDPLANE extrude like the vendor (end_cond 6) -- not blind from an
    # offset plane: a blind extrude's start-face edges orient opposite the
    # end-face ones, which flipped the asymmetric fillet's Direction 1 on
    # the bottom rim (the vendor needs no per-edge reverse, and with the
    # midplane body neither do we).
    from solidworks_mcp.adapters.base import ExtrusionParameters
    check("extrude washer", await adapter.create_extrusion(
        ExtrusionParameters(depth=W_T, both_directions=True)))
    name_last_feature(adapter, "WasherBody")
    v = math.pi * ((W_OD / 2.0) ** 2 - (W_ID / 2.0) ** 2) * W_T
    await volume_check(adapter, "washer annulus", v, 0.005 * v)

    # The four rim edges in one feature, like the vendor's Fillet1 (read
    # off the model: asymmetric=true, D1 0.34671 / D2 0.173355, conic-rho
    # profile rho=0.65; leg layout from the vendor faces: LONG leg radial
    # across the flats, SHORT leg axial down the cylinders).
    # The vendor's single Fillet1 reads no per-edge reverse, but on OUR
    # body the bottom edges' Direction 1 lands on the cylinder instead of
    # the flat (midplane vs blind extrude made no difference), and every
    # reverse knob probed inert (swFeatureFilletReverseFace1Dir,
    # SetReverseFaceNormal).  So: one feature per edge, with the D1/D2
    # values swapped on the bottom pair -- geometrically identical to the
    # vendor's one feature.
    h = W_T / 2.0
    for label, pt, r1, r2 in (
        ("RimFilletODTop", (W_OD / 2.0, h, 0.0), W_F2, W_F1),
        ("RimFilletODBot", (W_OD / 2.0, -h, 0.0), W_F1, W_F2),
        ("RimFilletIDTop", (W_ID / 2.0, h, 0.0), W_F1, W_F2),
        ("RimFilletIDBot", (W_ID / 2.0, -h, 0.0), W_F2, W_F1),
    ):
        await _asymmetric_fillet(adapter, [pt], r1, r2, W_RHO, label)

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
