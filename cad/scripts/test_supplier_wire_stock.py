"""SolidWorks-free behaviour of the wire parts' sketch-only stock configuration.

Drives the real ``_isolate_stock_configuration`` lifecycle and the real
``_rebuild`` readers (``active_configuration_name``, ``force_rebuild``,
``_hard_fault_names``/``whats_wrong``) against a seat double.  Only the COM
wrapper (``_early_bound``) and the feature-tree walk are stood in.

The double keeps each native member's declared shape (sldworks_2026 gen_py):
``IConfigurationManager.AddConfiguration2`` method (VT_DISPATCH, None on
refusal) and ``ActiveConfiguration`` property; ``IConfiguration.GetParent``
method and ``Name`` property; ``IModelDoc2.ShowConfiguration2`` method
(VT_BOOL; SolidWorks 2026 returns False for the already-active configuration);
``IFeature.SetSuppression2`` (VT_BOOL) and ``IsSuppressed2`` (VARIANT array)
methods holding state per configuration; ``IPartDoc.GetBodies2`` method (None
for no bodies); ``IModelDocExtension.GetWhatsWrong`` with its outs in the
return tuple.  AddConfiguration2 with Options = 0 activates the derived child,
which starts with its parent's feature states.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _rebuild
import _supplier_wire_stock as stock
from _mcmaster_9666k56_reference import (
    SUPPLIER_REFERENCE_CONFIGURATION as STOCK,
    SUPPLIER_REFERENCE_FEATURE as STOCK_SKETCH,
)

INSTALLED = "Default"
LEVER = (
    "WireProfile",
    "Wire",
    "BalloonRingReference",
    "BalloonRingSplit",
    "HookPoint",
    "HubPoint",
)
PEN = ("WireProfile", "Wire")
SUPPRESS = 0  # swFeatureSuppressionAction_e.swSuppressFeature
THIS_CONFIGURATION = 1  # swInConfigurationOpts_e.swThisConfiguration
DONT_ACTIVATE = 128  # swConfigurationOptions2_e.swConfigOption_DontActivate
# SolidWorks suppresses a feature's children with it.
LEVER_CHILDREN = {
    "WireProfile": ("Wire",),
    "Wire": ("BalloonRingSplit", "HookPoint", "HubPoint"),
    "BalloonRingReference": ("BalloonRingSplit",),
}


class Configuration:
    """IConfiguration: ``Name`` property, ``GetParent`` method."""

    def __init__(self, name: str, parent: Configuration | None = None) -> None:
        self.Name = name
        self._parent = parent

    def GetParent(self) -> Configuration | None:
        return self._parent


class Named:
    """A What's Wrong row's IFeature: only ``Name`` is read."""

    def __init__(self, name: str) -> None:
        self.Name = name


class Feature:
    """IFeature suppression, held per configuration."""

    def __init__(self, seat: Seat, name: str) -> None:
        self.seat = seat
        self.Name = name

    def SetSuppression2(self, action, option, _names) -> bool:
        assert (action, option) == (SUPPRESS, THIS_CONFIGURATION)
        seat = self.seat
        seat.set_calls.append((self.Name, seat.active))
        if self.Name in seat.refuse_suppression:
            return False
        if self.Name not in seat.drop_suppression:
            seat.suppress(self.Name, seat.active)
        return True

    def IsSuppressed2(self, option, _names) -> tuple[bool, ...]:
        assert option == THIS_CONFIGURATION
        return (self.seat.states[self.seat.active][self.Name],)


class Manager:
    """IConfigurationManager: ``ActiveConfiguration`` property and the
    ``AddConfiguration2`` method; it has no ShowConfiguration2."""

    def __init__(self, seat: Seat) -> None:
        self.seat = seat

    @property
    def ActiveConfiguration(self) -> Configuration:
        return Configuration(self.seat.active)

    def AddConfiguration2(
        self, name, _comment, _alternate, options, parent, _description, rebuild
    ) -> Configuration | None:
        seat = self.seat
        seat.added.append((name, options, parent, rebuild))
        if name in seat.parents or parent not in seat.parents:
            return None
        seat.parents[name] = parent
        seat.states[name] = dict(seat.states[parent])
        if seat.auto_activates and not options & DONT_ACTIVATE:
            seat.active = name
        if seat.reported_parent == "truth":
            reported = Configuration(parent)
        elif seat.reported_parent is None:
            reported = None
        else:
            reported = Configuration(seat.reported_parent)
        return Configuration(name, reported)


class Extension:
    """IModelDocExtension.GetWhatsWrong: outs ride the return tuple."""

    def __init__(self, seat: Seat) -> None:
        self.seat = seat

    def GetWhatsWrong(self):
        rows = self.seat.faults.get(self.seat.active, ())
        if not rows:
            return False, None, None, None
        names, codes, warnings = zip(*rows)
        return True, tuple(Named(name) for name in names), codes, warnings


class Seat:
    """IModelDoc2 + IPartDoc of a built wire with one installed configuration."""

    def __init__(
        self,
        features: tuple[str, ...],
        *,
        solids: tuple[str, ...] = ("Wire",),
        children: dict[str, tuple[str, ...]] | None = None,
        auto_activates: bool = True,
        refuse_show: frozenset[str] = frozenset(),
        show_ignored: frozenset[str] = frozenset(),
        reported_parent: str | None = "truth",
        refuse_suppression: frozenset[str] = frozenset(),
        drop_suppression: frozenset[str] = frozenset(),
        leaks_to_parent: bool = False,
        faults: dict[str, tuple[tuple[str, int, bool], ...]] | None = None,
        suppressed: frozenset[str] = frozenset(),
    ) -> None:
        names = (*features, STOCK_SKETCH)
        self.features = {name: Feature(self, name) for name in names}
        self.parents: dict[str, str | None] = {INSTALLED: None}
        self.states = {INSTALLED: {name: name in suppressed for name in names}}
        self.active = INSTALLED
        self.solids = solids
        self.children = children or {}
        self.auto_activates = auto_activates
        self.refuse_show = refuse_show
        self.show_ignored = show_ignored
        self.reported_parent = reported_parent
        self.refuse_suppression = refuse_suppression
        self.drop_suppression = drop_suppression
        self.leaks_to_parent = leaks_to_parent
        self.faults = faults or {}
        self.added: list[tuple[str, int, str, bool]] = []
        self.shown: list[str] = []
        self.set_calls: list[tuple[str, str]] = []
        self.rebuilt: list[str] = []
        self.ConfigurationManager = Manager(self)
        self.Extension = Extension(self)

    def suppress(self, name: str, configuration: str) -> None:
        targets = [configuration]
        if self.leaks_to_parent and self.parents[configuration] is not None:
            targets.append(self.parents[configuration])
        for target in targets:
            pending = [name]
            while pending:
                current = pending.pop()
                self.states[target][current] = True
                pending.extend(self.children.get(current, ()))

    def ShowConfiguration2(self, name: str) -> bool:
        self.shown.append(name)
        if name not in self.parents or name == self.active or name in self.refuse_show:
            return False
        if name not in self.show_ignored:
            self.active = name
        return True

    def GetBodies2(self, body_type, visible_only):
        assert (body_type, visible_only) == (0, False)
        live = [name for name in self.solids if not self.states[self.active][name]]
        return (object(),) if live else None

    def view(self, configuration: str) -> dict[str, bool]:
        return dict(self.states[configuration])


class Adapter:
    def __init__(self, seat: Seat) -> None:
        self.currentModel = seat

    def _attempt(self, fn, default=None):
        return fn()

    async def rebuild_model(self):
        self.currentModel.rebuilt.append(self.currentModel.active)
        return SimpleNamespace(is_success=True, error=None, data=None)


@pytest.fixture
def seat(monkeypatch):
    def lookup(adapter, name):
        try:
            return adapter.currentModel.features[name]
        except KeyError:
            raise RuntimeError(
                f"feature {name!r} not found in the active document"
            ) from None

    monkeypatch.setattr(stock, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_rebuild, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(stock, "_feature_by_name", lookup)

    def make(features=LEVER, **native):
        native.setdefault("children", LEVER_CHILDREN if features == LEVER else None)
        part = Seat(features, **native)
        return Adapter(part), part

    return make


def isolate(adapter, features=LEVER) -> None:
    asyncio.run(stock._isolate_stock_configuration(adapter, features))


def assert_installed_restored(part: Seat) -> None:
    assert part.active == INSTALLED
    assert not any(part.view(INSTALLED).values())
    assert part.GetBodies2(0, False) is not None
    assert part.rebuilt[-1] == INSTALLED


@pytest.mark.parametrize("features", [LEVER, PEN], ids=["lever", "pen"])
def test_autoactivated_stock_suppresses_every_inventoried_feature_explicitly(
    seat, features
) -> None:
    adapter, part = seat(features)
    isolate(adapter, features)
    assert part.added == [(STOCK, 0, INSTALLED, False)]
    # The child was already active: no ShowConfiguration2 of it, which the
    # seat would refuse.  Only the restore switches.
    assert part.shown == [INSTALLED]
    # Dependents first, every feature by its own call, all in the stock child.
    assert part.set_calls == [(name, STOCK) for name in reversed(features)]
    assert part.view(STOCK) == {
        **{name: True for name in features},
        STOCK_SKETCH: False,
    }
    assert part.rebuilt == [STOCK, INSTALLED]
    assert_installed_restored(part)


def test_seat_that_leaves_the_parent_active_is_switched_once(seat) -> None:
    adapter, part = seat(auto_activates=False)
    isolate(adapter)
    assert part.shown == [STOCK, INSTALLED]
    assert all(configuration == STOCK for _name, configuration in part.set_calls)
    assert_installed_restored(part)


@pytest.mark.parametrize(
    ("native", "message"),
    [
        ({"refuse_show": frozenset({STOCK})}, "cannot activate supplier nominal stock"),
        ({"show_ignored": frozenset({STOCK})}, "stock configuration is not active"),
    ],
    ids=["refused", "accepted-but-not-active"],
)
def test_unactivated_stock_never_suppresses_installed_features(
    seat, native, message
) -> None:
    adapter, part = seat(auto_activates=False, **native)
    with pytest.raises(RuntimeError, match=message) as raised:
        isolate(adapter)
    assert part.set_calls == []
    assert not hasattr(raised.value, "__notes__")
    assert_installed_restored(part)


@pytest.mark.parametrize("reported", ["Other", None], ids=["misparented", "orphan"])
def test_misparented_stock_is_refused_and_installed_restored(seat, reported) -> None:
    adapter, part = seat(reported_parent=reported)
    with pytest.raises(
        RuntimeError, match="must derive from the installed configuration"
    ):
        isolate(adapter)
    assert part.set_calls == []
    assert part.shown == [INSTALLED]
    assert_installed_restored(part)


@pytest.mark.parametrize(
    ("native", "message"),
    [
        ({"refuse_suppression": frozenset({"HookPoint"})}, "cannot suppress HookPoint"),
        (
            {"drop_suppression": frozenset({"BalloonRingReference"})},
            r"retained installed features \['BalloonRingReference'\]",
        ),
    ],
    ids=["refused", "accepted-but-not-persisted"],
)
def test_suppression_failure_raises_and_restores(seat, native, message) -> None:
    adapter, part = seat(**native)
    with pytest.raises(RuntimeError, match=message) as raised:
        isolate(adapter)
    assert not hasattr(raised.value, "__notes__")
    assert_installed_restored(part)


def test_root_only_suppression_is_not_trusted_for_independent_features(seat) -> None:
    # A seat that does not propagate Wire's suppression at all: every feature
    # still ends suppressed, because each one is asked for by name.
    adapter, part = seat(children={})
    isolate(adapter)
    assert part.view(STOCK) == {**{name: True for name in LEVER}, STOCK_SKETCH: False}
    assert_installed_restored(part)


def test_stock_sketch_dragged_into_suppression_is_refused(seat) -> None:
    adapter, part = seat(
        children={**LEVER_CHILDREN, "Wire": (*LEVER_CHILDREN["Wire"], STOCK_SKETCH)}
    )
    with pytest.raises(RuntimeError, match="stock circle is suppressed"):
        isolate(adapter)
    assert_installed_restored(part)


def test_stock_hard_fault_is_refused_but_a_warning_is_not(seat) -> None:
    adapter, part = seat(faults={STOCK: (("HookPoint", 3, True),)})
    isolate(adapter)
    assert_installed_restored(part)

    adapter, part = seat(faults={STOCK: (("BalloonRingSplit", 3, False),)})
    with pytest.raises(
        RuntimeError,
        match=r"hard faults: \['BalloonRingSplit \(dangling-no-members\)'\]",
    ):
        isolate(adapter)
    assert_installed_restored(part)


def test_uninventoried_solid_left_in_stock_is_refused(seat) -> None:
    adapter, part = seat(PEN, solids=("Wire", "Boss"), children=None)
    part.features["Boss"] = Feature(part, "Boss")
    part.states[INSTALLED]["Boss"] = False
    with pytest.raises(RuntimeError, match="contains an installed solid"):
        isolate(adapter, PEN)
    assert_installed_restored(part)


@pytest.mark.parametrize(
    ("native", "message"),
    [
        (
            {"suppressed": frozenset({"HubPoint"})},
            "installed wire configuration has suppressed",
        ),
        (
            {"suppressed": frozenset({STOCK_SKETCH})},
            "installed wire configuration has suppressed",
        ),
    ],
    ids=["installed-feature", "stock-sketch"],
)
def test_suppressed_original_state_is_refused_before_creation(
    seat, native, message
) -> None:
    adapter, part = seat(**native)
    with pytest.raises(RuntimeError, match=message):
        isolate(adapter)
    assert part.added == []
    assert part.shown == []


def test_inventory_naming_a_missing_feature_is_refused_before_creation(seat) -> None:
    adapter, part = seat(PEN)
    with pytest.raises(RuntimeError, match="'HookPoint' not found"):
        isolate(adapter, (*PEN, "HookPoint"))
    assert part.added == []


def test_refused_creation_switches_nothing(seat) -> None:
    adapter, part = seat()
    part.parents[STOCK] = INSTALLED  # the name already exists
    part.states[STOCK] = part.view(INSTALLED)
    with pytest.raises(RuntimeError, match="cannot create supplier nominal stock"):
        isolate(adapter)
    assert part.shown == []
    assert part.set_calls == []
    assert part.rebuilt == []


def test_primary_failure_survives_a_failed_restore(seat) -> None:
    adapter, part = seat(
        faults={STOCK: (("BalloonRingSplit", 1, False),)},
        refuse_show=frozenset({INSTALLED}),
    )
    with pytest.raises(
        RuntimeError, match="supplier stock configuration has hard faults"
    ) as raised:
        isolate(adapter)
    assert raised.value.__notes__ == [
        "restoration also failed: cannot restore installed wire configuration"
    ]
    assert part.active == STOCK


@pytest.mark.parametrize(
    ("native", "message"),
    [
        ({"leaks_to_parent": True}, "stock suppression leaked into the installed wire"),
        (
            {"faults": {INSTALLED: (("Wire", 2, False),)}},
            r"restored installed wire has hard faults: \['Wire \(rebuild-error\)'\]",
        ),
        (
            {"show_ignored": frozenset({INSTALLED})},
            "installed wire configuration is not active",
        ),
    ],
    ids=["leaked-suppression", "installed-hard-fault", "restore-not-active"],
)
def test_restore_readback_failure_raises_without_a_primary(
    seat, native, message
) -> None:
    adapter, part = seat(**native)
    with pytest.raises(RuntimeError, match=message) as raised:
        isolate(adapter)
    assert not hasattr(raised.value, "__notes__")
    assert part.set_calls  # the stock child itself was authored


@pytest.mark.parametrize(
    "inventory",
    [
        ["WireProfile", "Wire"],
        (),
        ("Wire", "Wire"),
        ("Wire", ""),
        ("Wire", 3),
        ("Wire", STOCK_SKETCH),
    ],
    ids=["list", "empty", "duplicate", "blank", "non-string", "stock-sketch"],
)
def test_invalid_inventory_is_refused_before_any_native_call(inventory) -> None:
    # ``object()`` has no adapter surface: reaching any native call would
    # raise AttributeError instead.
    with pytest.raises(ValueError, match="installed_features must be"):
        asyncio.run(
            stock.author_nominal_stock_cross_section(
                object(), installed_features=inventory
            )
        )


def test_inventory_has_no_default() -> None:
    with pytest.raises(TypeError, match="installed_features"):
        asyncio.run(stock.author_nominal_stock_cross_section(object()))
