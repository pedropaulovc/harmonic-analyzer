"""Components are visited by name, never in the seat's enumeration order
(issue #2686). SolidWorks-free."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _assembly
from _component_order import by_name, drawing_components_by_name, natural_key
from _component_references import component_reference_names


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


@pytest.mark.parametrize("name", [None, ""])
def test_an_unnamed_component_fails_closed(name):
    components = [SimpleNamespace(Name2="gear-1"), SimpleNamespace(Name2=name)]
    with pytest.raises(
        RuntimeError, match="IComponent2 enumeration: element 1 of 2 has no Name2"
    ):
        by_name(components)


def test_a_missing_component_fails_closed():
    with pytest.raises(
        RuntimeError, match="IComponent2 enumeration: element 0 of 1 is None"
    ):
        by_name([None])


def test_an_unnamed_drawing_component_fails_closed():
    with pytest.raises(
        RuntimeError, match="IDrawingComponent enumeration: element 0 of 1 has no Name"
    ):
        drawing_components_by_name([SimpleNamespace(Name=None)])


def test_an_unnamed_member_never_binds_the_top_level_selector():
    # A name read answering None once became the name "None", so the nested
    # member bound the top-level selector @LeverWire:1.
    member = SimpleNamespace(Name2=None, ComponentReference="LeverWire:1")
    model = SimpleNamespace(GetComponents=lambda _top_level_only: (member,))
    with pytest.raises(RuntimeError, match="has no Name2"):
        component_reference_names(
            model, {"@LeverWire:1": ("sh-vn-music-wire", "LeverWire")}
        )


class _ReportedComponent:
    """A component as an interference result hands it back: logs each read."""

    def __init__(self, log: list, name: str) -> None:
        self._log = log
        self._name = name

    @property
    def Name2(self) -> str:
        self._log.append((self._name, "Name2"))
        return self._name

    @property
    def ReferencedConfiguration(self) -> str:
        self._log.append((self._name, "ReferencedConfiguration"))
        return "Default"


class _Interference:
    def __init__(self, log: list, components: list, volume_mm3: float) -> None:
        self._log = log
        self._components = components
        self._volume = volume_mm3 / 1e9
        self._label = "&".join(sorted(component._name for component in components))

    @property
    def Components(self) -> list:
        self._log.append((self._label, "Components"))
        return self._components

    @property
    def Volume(self) -> float:
        self._log.append((self._label, "Volume"))
        return self._volume


def _interference_pass(reversed_report: bool) -> tuple[list, str]:
    """Run the interference gate over three clashes the seat reports in one
    order, or in the reverse order with each pair's members swapped."""
    log: list = []
    pairs = [
        ("plate-1", "gear-1", 2.0),
        ("gear-10", "gear-2", 3.0),
        ("shaft-1", "gear-1", 4.0),
    ]
    results = [
        _Interference(
            log,
            [
                _ReportedComponent(log, name)
                for name in (pair[::-1] if reversed_report else pair)
            ],
            volume,
        )
        for *pair, volume in pairs
    ]
    if reversed_report:
        results.reverse()
    manager = SimpleNamespace(
        GetInterferences=lambda: results, Done=lambda: log.append(("manager", "Done"))
    )
    model = SimpleNamespace(
        InterferenceDetectionManager=manager,
        ToolsCheckInterference=lambda: None,
        GetComponents=lambda _top_level_only: [],
    )
    adapter = SimpleNamespace(
        currentModel=model, _attempt=lambda action, default=None: action()
    )
    with pytest.raises(RuntimeError, match="3 interference") as raised:
        _assembly.check_no_interference(adapter)
    return log, str(raised.value)


def test_interference_results_are_read_in_name_pair_order():
    # Issue #2759: only the name reads follow the report's order; every later
    # read, and the failure text, follow the sorted name pairs.
    (first, first_error), (second, second_error) = map(
        _interference_pass, (False, True)
    )
    names = sum(1 for entry in first if entry[1] in ("Components", "Name2"))
    assert first[names:] == second[names:]
    assert first_error == second_error
    assert first_error.endswith(
        "gear-1 & plate-1: 2 mm^3; gear-1 & shaft-1: 4 mm^3; gear-2 & gear-10: 3 mm^3"
    )
