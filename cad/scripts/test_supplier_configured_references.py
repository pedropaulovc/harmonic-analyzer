"""Offline native-inventory regressions; not a claim of SOLIDWORKS parity."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _supplier_chain_dimensions as chain_dimensions
import _supplier_chain_stock as chain_stock
import _supplier_spring_drawing as supplier_drawing


class _NativeDimension:
    def __init__(self, name, owner, value_mm):
        self.FullName = f"{name}@{owner}@native-part.SLDPRT"
        self.value_mm = value_mm
        self.Tolerance = SimpleNamespace(Type=0)

    def GetSystemValue3(self, which, configuration_names):
        assert which == 3
        raw_names = getattr(configuration_names, "value", configuration_names)
        names = (raw_names,) if isinstance(raw_names, str) else tuple(raw_names)
        if names != (chain_stock.SUPPLIER_REFERENCE_CONFIGURATION,):
            # An unqualified/installed-member lookup must not happen to pass.
            return (1.3 / 1000.0,)
        return (self.value_mm / 1000.0,)


class _Display:
    def __init__(self, name, owner, value_mm):
        self.native = _NativeDimension(name, owner, value_mm)
        self.options = None

    def GetDimension2(self, index):
        assert index == 0
        return self.native


class _Annotation:
    def __init__(self, display):
        self.display = display

    def GetType(self):
        return 4

    def GetSpecificAnnotation(self):
        return self.display


class _View:
    def __init__(self, name, configuration):
        self.Name = name
        self.ReferencedConfiguration = configuration
        self.annotations = []

    def GetOutline(self):
        return (0.05, 0.12, 0.15, 0.16)

    def GetAnnotations(self):
        return tuple(self.annotations)

    def GetDisplayDimensionCount(self):
        return len(self.annotations)


def _chain_sheet(monkeypatch, *, connecting):
    views = {
        "free_front": _View("front", chain_stock.SUPPLIER_REFERENCE_CONFIGURATION),
        "free_top": _View("top", chain_stock.SUPPLIER_REFERENCE_CONFIGURATION),
        "installed_iso": _View("installed", "InnerLink"),
    }
    values = {
        chain_stock.PIN_DIMENSION: chain_stock.PIN_DIAMETER,
        chain_stock.ROLLER_DIMENSION: chain_stock.ROLLER_DIAMETER,
        chain_stock.PITCH_DIMENSION: chain_stock.PITCH,
        chain_stock.WIDTH_DIMENSION: chain_stock.ROLLER_WIDTH,
        chain_stock.PLATE_DIMENSION: chain_stock.PLATE_THICKNESS,
        chain_stock.LENGTH_DIMENSION: chain_stock.CONNECTING_PIN_LENGTH,
    }
    for module in (chain_dimensions, supplier_drawing):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(supplier_drawing, "iter_views", lambda _adapter: tuple(views.values()))
    monkeypatch.setattr(supplier_drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(
        chain_dimensions, "dimension_name",
        lambda _adapter, annotation: annotation.display.native.FullName.split("@")[0],
    )

    def curate(_adapter, view, *, keep, dimensions_by_feature, **_kwargs):
        owner = (chain_stock.FRONT_FEATURE if view is views["free_front"]
                 else chain_stock.SECTION_FEATURE)
        assert set(keep) <= dimensions_by_feature[owner]
        view.annotations = [
            _Annotation(_Display(name, owner, values[name])) for name in keep
        ]
        return view.annotations

    def present(_adapter, display, **options):
        # Presentation is covered by the shared supplier-dimension tests. This
        # collaborator retains its actual inputs while the real family reader
        # below owns configured values, owner/inventory and rebuild reacquisition.
        display.options = options

    def assert_presentation(_adapter, display, **options):
        assert display.options == options

    monkeypatch.setattr(chain_dimensions, "curate_view_dimensions", curate)
    monkeypatch.setattr(chain_dimensions, "supplier_reference_dimension", present)
    monkeypatch.setattr(chain_dimensions, "assert_supplier_reference_dimension", assert_presentation)
    checks = chain_dimensions.annotate_chain_stock(
        SimpleNamespace(), views, connecting=connecting,
    )
    return views, checks[0]


@pytest.mark.parametrize("connecting,expected_count", [(False, 4), (True, 6)])
def test_supplier_inventory_retains_exact_nominals_and_reacquires_rebuilt_annotations(
    monkeypatch, connecting, expected_count,
):
    views, settled = _chain_sheet(monkeypatch, connecting=connecting)
    assert sum(view.GetDisplayDimensionCount() for view in views.values()) == expected_count
    assert not views["installed_iso"].annotations
    pin = next(
        annotation.display for annotation in views["free_front"].annotations
        if annotation.display.native.FullName.startswith(chain_stock.PIN_DIMENSION + "@")
    )
    assert pin.native.value_mm == pytest.approx(2.2987, abs=1e-12)
    assert pin.native.value_mm != pytest.approx(0.091 * 25.4, abs=1e-8)
    assert pin.options["precision"] == 3
    assert pin.options["presentation"] == "diameter"
    # Rebuild replaces annotation COM objects. A retained pre-rebuild handle
    # cannot prove the final inventory: only newly returned objects survive.
    for view in views.values():
        replacements = []
        for annotation in view.annotations:
            old = annotation.display
            name, owner, _ = old.native.FullName.split("@")
            new = _Display(name, owner, old.native.value_mm)
            new.options = dict(old.options)
            replacements.append(_Annotation(new))
            old.native.value_mm = -1.0
        view.annotations = replacements
    settled()


@pytest.mark.parametrize("fault", ["owner", "value", "band", "missing", "foreign", "configuration"])
def test_final_supplier_readback_rejects_source_or_inventory_drift(monkeypatch, fault):
    views, settled = _chain_sheet(monkeypatch, connecting=True)
    front = views["free_front"]
    display = front.annotations[0].display
    if fault == "owner":
        display.native.FullName = f"{chain_stock.PIN_DIMENSION}@InstalledPin@part"
    elif fault == "value":
        display.native.value_mm = 1.3  # Installed stand-in pin is not supplier stock.
    elif fault == "band":
        display.native.Tolerance.Type = 2
    elif fault == "missing":
        front.annotations.pop()
    elif fault == "foreign":
        views["installed_iso"].annotations.append(
            _Annotation(_Display("ForeignSize", "InstalledPin", 1.3)),
        )
    elif fault == "configuration":
        front.ReferencedConfiguration = "OuterLink"
    with pytest.raises(RuntimeError):
        settled()


def test_connecting_application_references_are_explicit_not_physical_roller_claims(monkeypatch):
    views, settled = _chain_sheet(monkeypatch, connecting=True)
    displays = {
        annotation.display.native.FullName.split("@")[0]: annotation.display
        for view in views.values() for annotation in view.annotations
    }
    assert displays[chain_stock.ROLLER_DIMENSION].options["callout"] == "FOR ROLLER"
    assert displays[chain_stock.WIDTH_DIMENSION].options["callout"] == "FOR ROLLER WIDTH"
    assert displays[chain_stock.LENGTH_DIMENSION].native.value_mm == pytest.approx(8.509)
    assert displays[chain_stock.PLATE_DIMENSION].native.value_mm == pytest.approx(0.762)
    settled()


def test_wire_nominal_cannot_be_read_from_the_installed_envelope(monkeypatch):
    from _mcmaster_9666k56 import DIA
    from _mcmaster_9666k56_reference import (
        SUPPLIER_REFERENCE_CONFIGURATION,
        SUPPLIER_REFERENCE_DIMENSION,
        SUPPLIER_REFERENCE_FEATURE,
    )

    monkeypatch.setattr(supplier_drawing, "_early_bound", lambda value, _interface: value)
    display = _Display(SUPPLIER_REFERENCE_DIMENSION, SUPPLIER_REFERENCE_FEATURE, DIA)
    supplier_drawing.assert_supplier_configuration_value(
        display, SUPPLIER_REFERENCE_CONFIGURATION, 0.7874, label="supplier wire circle",
    )
    display.native.value_mm = 0.8
    with pytest.raises(RuntimeError, match="configured supplier dimension changed"):
        supplier_drawing.assert_supplier_configuration_value(
            display, SUPPLIER_REFERENCE_CONFIGURATION, DIA, label="supplier wire circle",
        )
