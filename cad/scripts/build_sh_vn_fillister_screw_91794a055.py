r"""Build MHA-SH-VN-59: McMaster 91794A055 #0-80 x 1/4 fillisters, 18-8 (7 used).

One purchased slotted fillister, fully threaded (contract §2.6, ruling 4), in
two installed members (``sh_vn_fillister_screw_91794a055_spec``):

- ``DiscScrew`` (x3, ``pd_transgear_disc_screw_spec``): each passes the
  brass hub's flange clearance hole (MHA-PD-17) and threads into a #0-80
  through tap in the reducer disc (MHA-PD-06).  CUT TO FIT at assembly
  (R9-47): each tip is cut TIP_BELOW_REAR_FACE under the disc's rear face and
  the cut end broken, so the member is modelled as installed: CUT_LENGTH long
  with a CUT_END_BREAK_MAX 45 deg break.
- ``RackScrew`` (x4, ``pd_feed_rack_screw_spec``): the screw as supplied,
  its head on a MHA-PD-27 counterbore floor and its thread in a MHA-PD-26
  strip tap, untrimmed.

Geometry source: the vendor-model replica ``diagnostics/diag_build_91794A055``
(replica-gated against the local-only harvest; no .SLDPRT committed) builds
the supplied screw, which is ``RackScrew``.  ``DiscScrew`` owns one more
feature, ``DiscCut``: a revolve cut that removes the shank below CUT_LENGTH
and breaks the cut end.  Above the cut the supplied profile is the cut
profile, so the member is the solid the replica's own ``cut_length`` /
``cut_end_break`` build draws (the groove's set difference commutes with the
cut); ``RackScrew`` suppresses ``DiscCut``.

Frame (both members, the fillister family's): axis +Y, head up, the
under-head bearing face at y = 0 (Top Plane); the tip at y = -LENGTH of the
member.  The assembly mates the Top Plane to the seating face and the screw
axis (``ScrewAxis``, Front Plane ∩ Right Plane) to a hole's axis.
"""

from __future__ import annotations

import math
import sys
from functools import wraps

import _mcmaster_91794a055 as supplier
import pd_feed_rack_screw_spec as rack
import pd_transgear_disc_screw_spec as disc
import sh_vn_fillister_screw_91794a055_spec as shared
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _configuration_material import require_material_in_every_configuration
from _fastener_catalog import fastener
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties
from _part_configuration_exports import export_member_configurations
from _purchased_part_variants import (
    activate_member,
    apply_member_properties,
    create_member_configurations,
    require_member_configurations,
    select_member_features,
)
from _rebuild import force_rebuild
from _session import run_build
from _simplified_part import save_simplified_part
from _sketch import add_line_chain
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_reference import add_supplier_reference_sketch
from diagnostics.diag_build_91794A055 import build_91794A055, shank_end
from diagnostics.diag_mcmaster_lib import no_sketch_inference

PART_NAME = shared.PART_STEM
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
SKU = supplier.SKU
if SPEC.skus != (SKU,):
    raise AssertionError(f"{PART_NAME} catalogues {SPEC.skus}, not {SKU}")
CONFIGURATIONS = shared.CONFIGURATIONS
# Each member's length under the head, the tip at y = -length.
LENGTHS = {
    rack.CONFIGURATION: rack.LENGTH,
    disc.CONFIGURATION: disc.CUT_LENGTH,
}
DESCRIPTIONS = {
    rack.CONFIGURATION: rack.BOM_DESCRIPTION,
    disc.CONFIGURATION: disc.BOM_DESCRIPTION,
}
# Parents before dependents (set_member_suppression hides in reverse).
DISC_CUT_FEATURES = ("DiscCutProfile", "DiscCut")
MEMBER_FEATURES: dict[str, tuple[str, ...]] = {
    rack.CONFIGURATION: (),
    disc.CONFIGURATION: DISC_CUT_FEATURES,
}
if tuple(LENGTHS) != CONFIGURATIONS or tuple(MEMBER_FEATURES) != CONFIGURATIONS:
    raise AssertionError("each registered member needs its length and features")
if rack.LENGTH != supplier.SHANK_LEN:
    raise AssertionError("RackScrew is the supplied screw, untrimmed")
# The modelled cut lies on full thread of every in-band supplied screw, so
# the break is the cut member's only end chamfer.
if (
    disc.SHANK_LEN - disc.STOCK_LENGTH_BAND[1] - disc.TIP_CHAMFER
    <= disc.CUT_LENGTH
):
    raise ValueError("the DiscScrew cut does not clear the shortest stock's factory tip")
# The replica's own cut rules (no shank lost, a real break) hold for it.
shank_end(disc.CUT_LENGTH, disc.CUT_END_BREAK_MAX)


def disc_cut_profile() -> list[tuple[float, float]]:
    """The closed half-section DiscCut revolves away (x radius, y axial, mm):
    everything under the cut plane plus the break's triangle, out to a
    margin past the major."""
    major_r = disc.SHANK_DIA / 2.0
    length = disc.CUT_LENGTH
    brk = disc.CUT_END_BREAK_MAX
    outer = 2.0 * major_r
    floor = -(disc.SHANK_LEN + disc.PITCH)
    return [
        (0.0, -length),
        (major_r - brk, -length),
        (major_r, -(length - brk)),
        (outer, -(length - brk)),
        (outer, floor),
        (0.0, floor),
    ]


async def _author_disc_cut(adapter) -> None:
    from solidworks_mcp.adapters.base import RevolveParameters

    profile = disc_cut_profile()
    check("create_sketch disc cut", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCenterLine(
                0.0, profile[0][1] / 1000.0, 0.0, 0.0, profile[-1][1] / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{PART_NAME} disc cut: CreateCenterLine failed")
        await add_line_chain(adapter, profile)
    check("exit_sketch disc cut", await adapter.exit_sketch())
    name_last_feature(adapter, DISC_CUT_FEATURES[0])
    check(
        "cut the disc screw to fit",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, DISC_CUT_FEATURES[1])


def _require_tip(adapter, configuration: str) -> None:
    """The active member's lowest point is its tip, -LENGTH under the head."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"{configuration}: the screw must be one solid body")
    tip = _early_bound(bodies[0], "IBody2").GetExtremePoint(0, -1, 0)
    if not tip[0] or not math.isclose(
        float(tip[2]), -LENGTHS[configuration] / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError(
            f"{configuration}: tip is not at y = -{LENGTHS[configuration]} mm"
        )


@wraps(build_91794A055)
async def _supplied_with_disc_cut(adapter, truth=None, **parameters):
    """The supplied screw, then the DiscScrew cut as its own feature."""
    receipt = await build_91794A055(adapter, truth, **parameters)
    await _author_disc_cut(adapter)
    await force_rebuild(adapter)
    _require_tip(adapter, disc.CONFIGURATION)
    return receipt


async def _save_members(adapter, part_name, suppressed_features):
    """Split the members, then the supplier references, the normal save and
    the member STEP/PNG exports on the reopened native.

    Members are split after the stock pipeline's material, so each carries it;
    each is still given it and its BOM identity while active.  The full
    catalogue references print on the purchase sheet's RackScrew views.
    """
    require_member_configurations(part_name, CONFIGURATIONS)
    await create_member_configurations(adapter, part_name, CONFIGURATIONS)
    for configuration in CONFIGURATIONS:
        await select_member_features(adapter, configuration, MEMBER_FEATURES)
        await force_rebuild(adapter)
        _require_tip(adapter, configuration)
        await apply_material(adapter, MATERIAL)
        apply_member_properties(
            adapter, part_name, configuration, DESCRIPTIONS[configuration], {}
        )
        await report_mass_properties(adapter)
    await activate_member(adapter, CONFIGURATIONS[0])
    require_material_in_every_configuration(
        adapter, part_name, MATERIAL, CONFIGURATIONS
    )
    await add_supplier_reference_sketch(
        adapter,
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=supplier.SUPPLIER_REFERENCE_STARTS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
    )
    artefacts = await save_simplified_part(adapter, part_name, suppressed_features)
    # save_simplified_part leaves the saved native open, RackScrew active; no
    # native save may follow the member exports.
    await export_member_configurations(adapter, part_name, CONFIGURATIONS)
    return artefacts


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=_supplied_with_disc_cut),),
        material=MATERIAL,
        save_threaded_part=_save_members,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
