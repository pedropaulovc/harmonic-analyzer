r"""Purchased transgear arm-plate screws: McMaster 91790A199, 18-8 stainless,
cut to fit.

8-32 x 1 in slotted 82 deg oval head, fully threaded, length measured from
the top of the bevel, verified live 2026-10-09 at mcmaster.com/91790A199
(``vn_transgear_arm_plate_screw_spec``).  Two hold the arm plate
(MHA-PD-019) on the arm (MHA-PD-018): each bevel seats in one of the plate's
82 deg countersinks and the shank runs through the plate's clearance
hole into the arm's #8-32 through tap.  The tips are trimmed and deburred
off the mechanism before installation near the guide locks; the installed
tips are flush with the arm's front face (R9-44).

Configurations:

- the default (installed) one, which assemblies place: CUT_LENGTH long with a
  CUT_END_BREAK_MAX 45 deg break.  The recipe builds the supplied screw and
  trims it with ONE revolve cut (``diag_mcmaster_oval.CUT_FEATURE``), whose
  cut end and break it reads back from the B-rep;
- ``SupplierStock`` (``SUPPLIER_STOCK_CONFIGURATION``), derived from it with
  only that trim suppressed: the full 1 in stock with its factory tip, which
  the purchased reference sheet shows beside its cut-to-suit note so the
  supplier's own sizes land on the solid's own spans;
- ``Default Simplified``, the installed one with the thread suppressed.  The
  supplier stock gets no simplified child: nothing places it.

The hidden supplier reference sketches (``_supplier_screw_reference``) carry
the supplier drawing's sizes from the exact spec constants that drive the
solid; they add no solid feature.

Geometry source: the chosen live McMaster stock page plus, for the underhead
neck, fillet and thread start, the supplier STEP inspected out of tree
(``diagnostics/diag_mcmaster_oval.py``; no replica gate, no vendor model
committed).  The rest of the native shape is a catalogue/reference
construction, not a measurement of individual bought hardware.

Frame: axis +Y, head up, the top of the bevel at y = 0 (Top Plane), the
plane that sits flush with the plate's rear face; the crown rises above it
and the installed cut end is at y = -LENGTH (= -CUT_LENGTH).  The assembly
mates the Top Plane to the plate's ``RearFace`` plane and the screw axis
(Front Plane ∩ Right Plane) to the plate's screw-hole axis.
"""

from __future__ import annotations

import sys

from solidworks_mcp.adapters.com_variant import null_variant

from _check import check
from _com import _early_bound
from _session import run_build
from _configuration_material import require_material_in_every_configuration
from _fastener_catalog import fastener
from _feature_tree import _feature_by_name
from _part_save import save_part_and_images
from _rebuild import (
    active_configuration_name,
    assert_saved_configurations_regenerate,
    force_rebuild,
)
from _simplified_part import (
    assert_simplified_configurations,
    derive_simplified_on_saved_part,
)
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_reference import add_supplier_reference_sketch
from diagnostics.diag_build_91790A199 import build_91790A199
from diagnostics.diag_mcmaster_oval import CUT_FEATURE, CUT_READBACK_TOL, lowest_y_mm
from vn_transgear_arm_plate_screw_spec import (
    CUT_END_BREAK_MAX,
    CUT_LENGTH,
    SKU,
    STOCK_LENGTH,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_STOCK_CONFIGURATION,
)

PART_NAME = "vn-transgear-arm-plate-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


def _require_end(adapter, expected_y: float, label: str) -> None:
    end = lowest_y_mm(adapter, label)
    if abs(end - expected_y) > CUT_READBACK_TOL:
        raise RuntimeError(f"{PART_NAME} {label}: lowest point y={end}, expected {expected_y}")


def _require_cut_suppressed(adapter, suppressed: bool, label: str) -> None:
    # IFeature.IsSuppressed2(swThisConfiguration): one state, the active one's.
    states = _feature_by_name(adapter, CUT_FEATURE).IsSuppressed2(1, null_variant())
    if tuple(states or ()) != (suppressed,):
        raise RuntimeError(
            f"{PART_NAME} {label}: {CUT_FEATURE} suppression {states!r}, expected {suppressed}"
        )


async def _supplier_stock(adapter) -> None:
    """Supplier references, then the full-stock configuration; the installed
    configuration is active again on return."""
    await add_supplier_reference_sketch(
        adapter,
        SUPPLIER_REFERENCE_DIMENSIONS,
        starts=SUPPLIER_REFERENCE_STARTS,
        planes=SUPPLIER_REFERENCE_PLANES,
    )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    installed = active_configuration_name(adapter, model)
    if not installed or installed == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError(f"{PART_NAME}: no installed configuration to derive stock from")
    # AddConfiguration2 with Options = 0 also ACTIVATES the new configuration,
    # and ShowConfiguration2 of the already-active one returns False: compare
    # the active name first.  The try starts at creation, so any failure from
    # here on returns to the installed configuration.
    created = manager.AddConfiguration2(
        SUPPLIER_STOCK_CONFIGURATION,
        f"McMaster {SKU} as supplied: full stock length, factory tip",
        "",
        0,
        installed,
        "Supplier stock; the installed screw is cut to fit",
        False,
    )
    if created is None:
        raise RuntimeError(f"{PART_NAME}: cannot create the supplier stock configuration")
    try:
        parent = _early_bound(created, "IConfiguration").GetParent()
        if parent is None or str(_early_bound(parent, "IConfiguration").Name) != installed:
            raise RuntimeError(
                f"{PART_NAME}: {SUPPLIER_STOCK_CONFIGURATION} is not derived from {installed}"
            )
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            if model.ShowConfiguration2(SUPPLIER_STOCK_CONFIGURATION) is not True:
                raise RuntimeError(f"{PART_NAME}: cannot activate the supplier stock configuration")
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError(f"{PART_NAME}: the supplier stock configuration is not active")
        # swSuppressFeature in swThisConfiguration: the trim only, here only.
        if _feature_by_name(adapter, CUT_FEATURE).SetSuppression2(
            0, 1, null_variant()
        ) is not True:
            raise RuntimeError(f"{PART_NAME}: cannot suppress {CUT_FEATURE} in the stock")
        await force_rebuild(adapter)
        _require_cut_suppressed(adapter, True, SUPPLIER_STOCK_CONFIGURATION)
        _require_end(adapter, -STOCK_LENGTH, SUPPLIER_STOCK_CONFIGURATION)
    finally:
        if active_configuration_name(adapter, model) != installed:
            if model.ShowConfiguration2(installed) is not True:
                raise RuntimeError(f"{PART_NAME}: cannot restore the installed configuration")
        if active_configuration_name(adapter, model) != installed:
            raise RuntimeError(f"{PART_NAME}: the installed configuration is not active")
        await force_rebuild(adapter)
    _require_cut_suppressed(adapter, False, installed)
    _require_end(adapter, -CUT_LENGTH, installed)
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, (installed, SUPPLIER_STOCK_CONFIGURATION)
    )


async def _save_installed(adapter, part_name, suppressed_features):
    """Simplify the installed configuration only, never the supplier stock."""
    installed = active_configuration_name(adapter, adapter.currentModel)
    if installed == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError(f"{part_name}: cannot save with the supplier stock active")
    parents = (installed,)
    artefacts = await save_part_and_images(adapter, part_name)
    await derive_simplified_on_saved_part(
        adapter, part_name, suppressed_features, artefacts["part"], parents=parents
    )
    check(f"reopen saved {part_name}", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, part_name)
    assert_simplified_configurations(
        adapter, part_name, suppressed_features, parents=parents
    )
    return artefacts


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_91790A199,
                parameters={
                    "cut_length": CUT_LENGTH,
                    "cut_end_break": CUT_END_BREAK_MAX,
                },
            ),
        ),
        material=MATERIAL,
        save_threaded_part=_save_installed,
        screw_axis_planes=("Front Plane", "Right Plane"),
        before_save=_supplier_stock,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
