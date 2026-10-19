"""Reference callbacks cannot change the assembly's saved active state."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _spring
import _stock_fastener
import build_vn_counter_spring as counter
import diagnostics.diag_mcmaster_lib as replica


@pytest.mark.parametrize("module", [_spring, _stock_fastener, counter])
@pytest.mark.parametrize("installed_configuration", ["Default", "Installed-Length", ""])
@pytest.mark.parametrize(
    "callback_configuration", [None, "Supplier-Free", "Supplier-Max", "Supplier-Dimensions"],
)
def test_reference_callback_active_configuration_guard_controls_saving(
    monkeypatch, module, installed_configuration, callback_configuration,
):
    saved = False
    configuration = SimpleNamespace(Name=installed_configuration)
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            ClearSelection2=lambda all: None,
            ConfigurationManager=SimpleNamespace(ActiveConfiguration=configuration),
        ),
    )

    async def no_op(*args, **kwargs):
        return True

    async def save(*args, **kwargs):
        nonlocal saved
        saved = True

    async def before_save(target, **kwargs):
        if callback_configuration is not None:
            target.currentModel.ConfigurationManager.ActiveConfiguration.Name = callback_configuration

    adapter.create_part = no_op
    monkeypatch.setattr(module, "check", lambda label, result: result)
    monkeypatch.setattr(module, "force_rebuild", no_op)
    monkeypatch.setattr(module, "apply_material", no_op)
    monkeypatch.setattr(module, "apply_color", no_op)
    monkeypatch.setattr(module, "apply_custom_properties", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_blank_recipe_references", lambda *args: None)
    monkeypatch.setattr(module, "report_mass_properties", no_op)
    if module is _spring:
        monkeypatch.setattr(module, "build_9432K31", no_op)
        monkeypatch.setattr(module, "save_part_and_images", save)
        run = module.build_spring(adapter, "vn-channel-spring-installed", 80.0, before_save=before_save)
    elif module is counter:
        monkeypatch.setattr(module, "build_1330K524", no_op)
        monkeypatch.setattr(module, "clear_dimensions_for_drawing", lambda *args: None)
        monkeypatch.setattr(module, "apply_drawing_properties", lambda *args: None)
        monkeypatch.setattr(module, "add_extension_spring_references", before_save)
        monkeypatch.setattr(module, "save_part_and_images", save)
        monkeypatch.setattr(module, "require_saved_drawing_properties", lambda *args: None)
        run = module.build(adapter)
    else:
        monkeypatch.setattr(module, "_early_bound", lambda value, interface: value)
        monkeypatch.setattr(module, "recipe_declaration", lambda *args: SimpleNamespace(threaded=False))
        monkeypatch.setattr(module, "_solid_bodies", lambda *args: ())
        monkeypatch.setattr(module, "_new_bodies", lambda *args: ())
        monkeypatch.setattr(module, "_transform_new_bodies", lambda *args: None)
        monkeypatch.setattr(replica, "assert_seat_sketch_baseline", lambda *args: None)
        monkeypatch.setattr(module, "fastener", lambda *args: SimpleNamespace(stock_name="Spring", supplier="McMaster", skus=("test",)))
        monkeypatch.setattr(module, "_save_stock_part", save)
        component = SimpleNamespace(sku="test", author=no_op, parameters=None)
        run = module.build_stock_fastener(adapter, part_name="spring", components=(component,),
                                           material="Steel", before_save=before_save)
    if not installed_configuration:
        with pytest.raises(RuntimeError, match="installed configuration identity is unavailable"):
            asyncio.run(run)
        assert saved is False
    elif callback_configuration is not None:
        with pytest.raises(RuntimeError, match="before_save changed the installed active configuration"):
            asyncio.run(run)
        assert saved is False
    else:
        asyncio.run(run)
        assert saved is True
        assert configuration.Name == installed_configuration
