"""Test-only native configuration state behind the source-stock helpers.

Shared by the knife-hanger stud and transgear pivot screw suites; it drives
each part's real ``_add_stock_configuration`` with the real
``active_configuration_name`` and ``_suppression`` readers.
"""

from __future__ import annotations

from types import SimpleNamespace

import _simplified_part

FINISHED = "Default"
FINISHED_SIMPLIFIED = "Default Simplified"
STOCK_FEATURES = ("StockDeburr", "StockTrim", "ThreadGroove")
DONT_ACTIVATE = 128  # swConfigurationOptions2_e.swConfigOption_DontActivate
SPECIFY_CONFIGURATION = 3  # swInConfigurationOpts_e.swSpecifyConfiguration
SUPPRESS = 0  # swFeatureSuppressionAction_e.swSuppressFeature


class Configuration:
    """IConfiguration: ``Name`` property and ``GetParent`` method."""

    def __init__(self, name: str, parent: Configuration | None) -> None:
        self.Name = name
        self._parent = parent

    def GetParent(self) -> Configuration | None:
        return self._parent


class Feature:
    """IFeature suppression held per configuration, as SolidWorks does."""

    def __init__(self, part: StockConfigurationPart, name: str) -> None:
        self.part = part
        self.Name = name
        self.states = {configuration: False for configuration in part.parents}

    def SetSuppression2(self, action, option, names) -> bool:
        assert (action, option) == (SUPPRESS, SPECIFY_CONFIGURATION)
        if self.Name in self.part.refuse_suppression:
            return False
        if self.Name in self.part.drop_suppression:
            return True  # accepted, but the state does not persist
        for name in names:
            self.states[name] = True
        return True

    def IsSuppressed2(self, option, names) -> tuple[bool, ...]:
        assert option == SPECIFY_CONFIGURATION
        return tuple(self.states[name] for name in names)


class StockConfigurationPart:
    """IModelDoc2 + IConfigurationManager for a saved finished-only part.

    As SolidWorks 2026: AddConfiguration2 without swConfigOption_DontActivate
    activates the derived child, which starts with its parent's feature
    states; ShowConfiguration2 of the already-active configuration returns
    False.  ``auto_activates=False`` models a seat whose AddConfiguration2
    leaves the parent active, ``refuse_show`` configurations ShowConfiguration2
    refuses even when a switch is needed, and ``reported_parent`` is what the
    created configuration's GetParent reads back (``"finished"`` = truth).
    """

    def __init__(
        self,
        *,
        auto_activates: bool = True,
        refuse_show: frozenset[str] = frozenset(),
        reported_parent: str | None = "finished",
        refuse_suppression: frozenset[str] = frozenset(),
        drop_suppression: frozenset[str] = frozenset(),
        rebuild_fails: bool = False,
    ) -> None:
        self.parents: dict[str, str | None] = {FINISHED: None, FINISHED_SIMPLIFIED: FINISHED}
        self.active = FINISHED
        self.auto_activates = auto_activates
        self.refuse_show = refuse_show
        self.reported_parent = reported_parent
        self.refuse_suppression = refuse_suppression
        self.drop_suppression = drop_suppression
        self.rebuild_fails = rebuild_fails
        self.shown: list[str] = []
        self.rebuilt: list[str] = []
        self.ConfigurationManager = self
        self.features = {name: Feature(self, name) for name in STOCK_FEATURES}
        # The finished-only Simplified child already drops the factory thread.
        self.features["ThreadGroove"].states[FINISHED_SIMPLIFIED] = True

    @property
    def ActiveConfiguration(self) -> Configuration:
        return Configuration(self.active, None)

    def GetConfigurationNames(self) -> tuple[str, ...]:
        return tuple(self.parents)

    def GetConfigurationByName(self, name: str) -> Configuration | None:
        return Configuration(name, None) if name in self.parents else None

    def AddConfiguration2(self, name, _comment, _alternate, options, parent, _description,
                          _rebuild) -> Configuration | None:
        if name in self.parents or parent not in self.parents:
            return None
        self.parents[name] = parent
        for feature in self.features.values():
            feature.states[name] = feature.states[parent]
        if self.auto_activates and not options & DONT_ACTIVATE:
            self.active = name
        if self.reported_parent is None:
            reported = None
        elif self.reported_parent == "finished":
            reported = Configuration(parent, None)
        else:
            reported = Configuration(self.reported_parent, None)
        return Configuration(name, reported)

    def ShowConfiguration2(self, name: str) -> bool:
        self.shown.append(name)
        if name not in self.parents or name == self.active or name in self.refuse_show:
            return False
        self.active = name
        return True

    def ForceRebuild3(self, top_only: bool) -> bool:
        assert top_only is False
        self.rebuilt.append(self.active)
        return not self.rebuild_fails

    def states(self, configuration: str) -> dict[str, bool]:
        return {name: feature.states[configuration] for name, feature in self.features.items()}


def stock_configuration_adapter(module, monkeypatch, *, bom_fails: bool = False, **native):
    """Bind ``module``'s helper to a ``StockConfigurationPart``; return
    ``(adapter, part, bom_copies)``.  Only the COM wrapper, the feature
    lookup and the BOM-identity copy are stood in; the active-name and
    per-configuration suppression readers are the production ones."""
    part = StockConfigurationPart(**native)
    copies: list[tuple[str, str, str]] = []

    def copy_bom_identity(model, parent, child) -> None:
        assert model is part
        copies.append((parent, child, part.active))
        if bom_fails:
            raise RuntimeError("BOM identity did not persist")

    monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(module, "_bstr_array", tuple)
    monkeypatch.setattr(_simplified_part, "_bstr_array", tuple)
    monkeypatch.setattr(module, "_feature_by_name", lambda _adapter, name: part.features[name])
    monkeypatch.setattr(module, "_copy_bom_identity", copy_bom_identity)
    return SimpleNamespace(currentModel=part), part, copies
