"""Build the installed McMaster-Carr 9432K31 channel spring, MHA-CH-VN-50.

The supplier-native recipe is authored in its vendor frame: spring axis +X,
origin at mid-length, hook-eye axes +Z.  The production body is not rotated;
assembly placement owns the vendor-to-machine transform.

One SLDPRT carries one configuration per distinct measured installed length
of the amplitude preset (``spec.installed_lengths``, owner ruling 2026-11-20,
#1610 route a): ``Default`` holds the first, ``Installed01``... the rest, so
the channel assembly places this one part per channel with that channel's
configuration and its BOM groups all twenty under MHA-CH-VN-50.  The
``neutral`` preset has one length, so it saves the single ``Default``.

Each length is the full vendor recipe under its own feature names
(``diag_build_9432K31.feature_names``); every installed configuration
suppresses the other lengths' features, so each holds exactly one spring.

Run with SolidWorks open::

    uv run python cad\\scripts\\build_ch_vn_channel_spring_installed.py
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any

from solidworks_mcp.adapters.com_variant import null_variant

import _config
from _check import check
from _com import _early_bound
from _configuration_material import require_material_in_every_configuration
from _custom_properties import apply_custom_properties
from _document_units import keep_equation_places_exact
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing
from _grouped_bom_properties import apply_grouped_bom_properties
from _part_checks import report_mass_properties
from _part_save import save_part_and_images
from _rebuild import (
    active_configuration_name,
    assert_saved_configurations_regenerate,
    force_rebuild,
)
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _spring import MATERIAL, STOCK_PROPERTIES, author_spring, finish_spring
from _stock_fastener import _blank_recipe_references
from _supplier_extension_spring import add_extension_spring_references
from _visibility import assert_reference_geometry_hidden
from ch_vn_channel_spring_installed_notes import DRAWING_NOTES
import ch_vn_channel_spring_installed_spec as spec
from diagnostics.diag_build_9432K31 import check_spring_body, feature_names


PART_NAME = "ch-vn-channel-spring-installed"
_SUPPRESS = 0  # swFeatureSuppressionAction_e.swSuppressFeature
_UNSUPPRESS = 1  # swFeatureSuppressionAction_e.swUnSuppressFeature
_THIS_CONFIGURATION = 1  # swInConfigurationOpts_e.swThisConfiguration


def _suffix(installed: spec.InstalledLength) -> str:
    """The Default length keeps the vendor's own feature names."""
    if installed.configuration == spec.DEFAULT_CONFIGURATION:
        return ""
    return f"-{installed.configuration}"


def _show(adapter: Any, model: Any, configuration: str) -> None:
    if active_configuration_name(adapter, model) != configuration and (
        model.ShowConfiguration2(configuration) is not True
    ):
        raise RuntimeError(f"{PART_NAME}: cannot activate {configuration}")
    if active_configuration_name(adapter, model) != configuration:
        raise RuntimeError(f"{PART_NAME}: {configuration} is not active")


def _feature(adapter: Any, name: str) -> Any:
    raw = _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(name)
    if raw is None:
        raise RuntimeError(f"{PART_NAME}: missing spring feature {name}")
    return _early_bound(raw, "IFeature")


def _suppressed(adapter: Any, name: str) -> bool:
    states = tuple(
        _feature(adapter, name).IsSuppressed2(_THIS_CONFIGURATION, null_variant()) or ()
    )
    if len(states) != 1 or type(states[0]) is not bool:
        raise RuntimeError(f"{PART_NAME}: {name} suppression is unreadable: {states!r}")
    return states[0]


def _set_suppressed(
    adapter: Any, configuration: str, names: Sequence[str], suppressed: bool
) -> None:
    """Set ``names`` in the ACTIVE configuration only, each read back.

    Suppression specified for another configuration can return True and leave
    the feature live (build_dt_cone_gear's probe 3), so each configuration is
    activated and edits itself."""
    action = _SUPPRESS if suppressed else _UNSUPPRESS
    for name in names:
        if _suppressed(adapter, name) is suppressed:
            continue
        if (
            _feature(adapter, name).SetSuppression2(
                action, _THIS_CONFIGURATION, null_variant()
            )
            is not True
        ):
            raise RuntimeError(
                f"{configuration}: cannot set {name} suppressed={suppressed}"
            )
        if _suppressed(adapter, name) is not suppressed:
            raise RuntimeError(
                f"{configuration}: {name} suppressed={suppressed} did not persist"
            )


def _isolate_length(
    adapter: Any, installed: Sequence[spec.InstalledLength], own: spec.InstalledLength
) -> None:
    """In the active configuration: every other length suppressed (dependents
    first), then this length live (parents first)."""
    for other in installed:
        if other != own:
            _set_suppressed(
                adapter, own.configuration, feature_names(_suffix(other))[::-1], True
            )
    _set_suppressed(adapter, own.configuration, feature_names(_suffix(own)), False)


def _author_lengths(adapter: Any, installed: Sequence[spec.InstalledLength]) -> None:
    """Author every length in ``Default``, each on an otherwise empty solid tree.

    All recipes exist, construction references hidden, before any other
    configuration is copied from ``Default``, so every configuration starts
    from the same hidden references."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if active_configuration_name(adapter, model) != spec.DEFAULT_CONFIGURATION:
        raise RuntimeError(
            f"{PART_NAME}: a new part must open in {spec.DEFAULT_CONFIGURATION}"
        )
    for index, length in enumerate(installed):
        if index:
            previous = feature_names(_suffix(installed[index - 1]))[::-1]
            _set_suppressed(adapter, spec.DEFAULT_CONFIGURATION, previous, True)
        author_spring(adapter, length.length_mm, suffix=_suffix(length))


def _configure_lengths(adapter: Any, installed: Sequence[spec.InstalledLength]) -> None:
    """One configuration per length, each holding exactly its own spring.

    ``AddConfiguration2`` copies the active configuration; each copy is then
    isolated with itself active. ``Default`` is isolated last and stays active.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    for length in (*installed[1:], installed[0]):
        if length.configuration != spec.DEFAULT_CONFIGURATION:
            created = manager.AddConfiguration2(
                length.configuration,
                f"9432K31 installed at {length.length_mm:.6f} mm inside hooks",
                "",
                0,
                "",
                "Installed channel spring length",
                False,
            )
            if created is None:
                raise RuntimeError(f"{PART_NAME}: cannot create {length.configuration}")
        _show(adapter, model, length.configuration)
        _isolate_length(adapter, installed, length)
        force_rebuild(adapter)
        check_spring_body(adapter, length.length_mm)
        finish_spring(adapter)
        _blank_recipe_references(adapter)
        assert_reference_geometry_hidden(
            adapter, f"{PART_NAME} [{length.configuration}]"
        )


def _add_supplier_references(adapter: Any) -> None:
    add_extension_spring_references(
        adapter,
        free_length_mm=spec.FREE_LENGTH_MM,
        max_length_mm=spec.MAX_LENGTH_MM,
        coil_od_mm=spec.SUPPLIER_COIL_OD_MM,
        wire_dia_mm=spec.SUPPLIER_WIRE_DIA_MM,
        body_count=1,
    )


def build(adapter) -> dict[str, str]:
    installed = spec.installed_lengths(_config.amplitudes())
    names = [length.configuration for length in installed]
    check("create_part", adapter.create_part())
    keep_equation_places_exact(adapter, label=PART_NAME)
    _author_lengths(adapter, installed)
    _configure_lengths(adapter, installed)
    require_material_in_every_configuration(adapter, PART_NAME, MATERIAL, names)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    clear_dimensions_for_drawing(adapter)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    _add_supplier_references(adapter)
    if (
        int(adapter.swApp.IsSame(adapter.currentModel, model)) != 1
        or active_configuration_name(adapter, model) != spec.DEFAULT_CONFIGURATION
    ):
        raise RuntimeError(
            f"{PART_NAME}: supplier references changed the installed document/configuration"
        )
    # The CH-00 BOM groups the installed configurations by this Number; the
    # stamped description wins over the drawing's written cell, so it is the
    # registry text the channel BOM prints.
    row = _config.parts(PART_NAME)
    apply_grouped_bom_properties(
        adapter,
        names,
        part_number=str(row["number"]),
        description=str(row["description"]),
    )

    report_mass_properties(adapter)
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
            "Manufacturing Notes",
        ),
    )
    check(f"reopen saved {PART_NAME}", adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
