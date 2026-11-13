"""Components are visited by name, never in the seat's enumeration order
(issue #2686). SolidWorks-free."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _assembly
from _component_order import by_name, natural_key


def test_instance_numbers_order_as_numbers_and_a_parent_precedes_its_children():
    names = [
        "sub-10",
        "gear-10",
        "sub-1/gear-1",
        "gear-2",
        "sub-2/gear-1",
        "gear-1",
        "sub-1",
    ]
    assert sorted(names, key=natural_key) == [
        "gear-1",
        "gear-2",
        "gear-10",
        "sub-1",
        "sub-1/gear-1",
        "sub-2/gear-1",
        "sub-10",
    ]


class _Component:
    """A top-level component that logs every request made of it."""

    def __init__(self, log: list, name: str, path: str, model, referenced: str) -> None:
        self._log = log
        self._name = name
        self._path = path
        self._model = model
        self._referenced = referenced

    def _ask(self, member: str, *args) -> None:
        self._log.append((self._name, member, args))

    @property
    def Name2(self) -> str:
        self._ask("Name2")
        return self._name

    def GetPathName(self) -> str:
        self._ask("GetPathName")
        return self._path

    @property
    def ReferencedConfiguration(self) -> str:
        self._ask("ReferencedConfiguration")
        return self._current()

    @ReferencedConfiguration.setter
    def ReferencedConfiguration(self, value: str) -> None:
        self._ask("ReferencedConfiguration=", value)
        self._referenced = value

    def _current(self) -> str:
        return self._referenced

    def IsSuppressed(self) -> bool:
        self._ask("IsSuppressed")
        return False

    def GetModelDoc2(self):
        self._ask("GetModelDoc2")
        return self._model


class _PatternInstance(_Component):
    """Follows its seed's configuration until set on its own, as a native
    pattern instance does."""

    def __init__(self, log: list, name: str, seed: _Component) -> None:
        super().__init__(log, name, seed._path, seed._model, "")
        self._seed = seed

    def _current(self) -> str:
        return self._referenced or self._seed._referenced


class _Configuration:
    def __init__(self, name: str, parent: _Configuration | None = None) -> None:
        self.Name = name
        self.parent = parent
        self.Comment = ""

    def GetParent(self) -> _Configuration | None:
        return self.parent


class _Model:
    def __init__(self, *names: str, components=()) -> None:
        self.configurations = {name: _Configuration(name) for name in names}
        self.components = list(components)
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=self.configurations[names[0]],
            AddConfiguration2=self._add,
        )

    def _add(
        self, name, _comment, _alternate, _options, parent, _description, _rebuild
    ):
        self.configurations[name] = _Configuration(name, self.configurations[parent])
        return self.configurations[name]

    def GetConfigurationNames(self) -> list[str]:
        return list(self.configurations)

    def GetConfigurationByName(self, name: str) -> _Configuration | None:
        return self.configurations.get(name)

    def ShowConfiguration2(self, name: str) -> bool:
        self.ConfigurationManager.ActiveConfiguration = self.configurations[name]
        return True

    def GetComponents(self, _top_level: bool) -> list[_Component]:
        return self.components


def _simplified_pass(order: tuple[str, ...]) -> tuple[list, int]:
    """Run the Default Simplified pass over one assembly whose components the
    seat enumerates in ``order``: a pattern seed and its instance (one part
    file) and a plate, as in the measuring stick of #2686."""
    log: list = []
    gear = _Model("T24", "T24 Simplified")
    plate = _Model("Default", "Default Simplified")
    seed = _Component(log, "gear-1", "gear.SLDPRT", gear, "T24")
    components = {
        "gear-1": seed,
        "gear-2": _PatternInstance(log, "gear-2", seed),
        "plate-1": _Component(log, "plate-1", "plate.SLDPRT", plate, "Default"),
    }
    files = {"gear.SLDPRT": gear, "plate.SLDPRT": plate}

    def configuration_names(path: str) -> list[str]:
        log.append(("app", "GetConfigurationNames", (path,)))
        return files[path].GetConfigurationNames()

    model = _Model("Default", components=[components[name] for name in order])
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(GetConfigurationNames=configuration_names),
    )
    changes = _assembly.sync_simplified_configuration(adapter, "fixture", verify=False)
    return log, changes


_ORDERS = (("gear-1", "gear-2", "plate-1"), ("plate-1", "gear-2", "gear-1"))


def test_a_reordered_enumeration_issues_the_same_requests():
    (first, first_changes), (second, second_changes) = map(_simplified_pass, _ORDERS)
    # The names are read first, one each, in the seat's order: only those
    # answers follow the seat.
    count = len(_ORDERS[0])
    for log, order in ((first, _ORDERS[0]), (second, _ORDERS[1])):
        assert log[:count] == [(name, "Name2", ()) for name in order]
    # Every later request goes to the same component in the same order, so
    # the two seats' recordings pair by name; without that pairing (handles
    # erased) the whole sequences match.
    assert first[count:] == second[count:]
    assert [entry[1:] for entry in first] == [entry[1:] for entry in second]
    assert first_changes == second_changes
    # The seed is visited before its instance, which then follows it with no
    # write of its own.
    assert ("gear-2", "ReferencedConfiguration=", ("T24 Simplified",)) not in first


def test_following_the_enumeration_order_would_not(monkeypatch):
    monkeypatch.setattr(
        _assembly, "by_name", lambda components: [(c.Name2, c) for c in components]
    )
    first, second = (_simplified_pass(order)[0] for order in _ORDERS)
    assert [entry[1:] for entry in first] != [entry[1:] for entry in second]


@pytest.mark.parametrize("given", [(), None])
def test_an_empty_or_failed_enumeration_names_nothing(given):
    assert by_name(given) == []
