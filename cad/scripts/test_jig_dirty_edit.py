"""Seat-free behavioral proofs for the bounded E04D diagnostic.

The consumer loops, equation recognizer, feature walker and same-call capture are
real. Only native receivers and external provenance/input locations are inert.
No sleeps, SolidWorks connection, subprocesses or production output are needed.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import types
from pathlib import Path

import pytest

import _assembly
import _assembly_postbuild
import _jig_dirty_edit as dirty
import _telemetry
import verify
from solidworks_mcp.adapters.solidworks import assembly as sdk_assembly

_REPO_ROOT = Path(__file__).resolve().parents[2]

assert Path(sdk_assembly.__file__).resolve().is_relative_to(_REPO_ROOT), (
    "behavioral proof must import this isolated worktree's pinned SDK"
)


@pytest.fixture(autouse=True)
def _offline_telemetry(monkeypatch):
    for signal in ("", "_TRACES", "_LOGS", "_METRICS"):
        monkeypatch.setenv(f"OTEL_EXPORTER_OTLP{signal}_ENDPOINT", "")
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: None)


class RecordingBudget:
    def __init__(self):
        self.checks = []
        self.units = []

    def check(self, label, cleanup=False):
        self.checks.append((label, cleanup))

    @contextlib.contextmanager
    def unit(self, label, cleanup=False):
        self.check(label, cleanup=cleanup)
        self.units.append((label, cleanup))
        yield


def recording_checkpoint(records=None):
    """Direct-admission port only; these receipts are not persistence proof."""
    publication = {
        "status": "inactive",
        "attempts": 0,
        "last_success": None,
        "errors": [],
    }

    def publish(evidence, phase):
        assert publication["status"] != "unavailable"
        publication["attempts"] += 1
        if records is not None:
            records.append((phase, copy.deepcopy(evidence)))
        publication["status"] = "published"
        publication["last_success"] = {"phase": phase}

    return {"publication": publication, "publish": publish}


class Feature:
    """IFeature: Name is a property; all graph/identity/type access is a method."""

    def __init__(self, identity, name="same-name", kind="Boss"):
        self.identity = identity
        self.name = name
        self.kind = kind
        self.next = None
        self.sub = None
        self.next_sub = None
        self.calls = []
        self.error = None

    @property
    def Name(self):
        self.calls.append("Name")
        return self.name

    def GetID(self):
        self.calls.append("GetID")
        return self.identity

    def GetTypeName2(self):
        self.calls.append("GetTypeName2")
        return self.kind

    def GetNextFeature(self):
        self.calls.append("GetNextFeature")
        if self.error:
            raise self.error
        return self.next

    def GetFirstSubFeature(self):
        self.calls.append("GetFirstSubFeature")
        return self.sub

    def GetNextSubFeature(self):
        self.calls.append("GetNextSubFeature")
        return self.next_sub


def feature_receiver(first):
    return types.SimpleNamespace(FirstFeature=lambda: first)


def feature_graph(*features):
    return {
        "scope": "child:Default",
        "nodes": {
            str(f.identity): {"id": f.identity, "name": f.name, "type": f.kind}
            for f in features
        },
        "occurrences": [],
        "terminations": [],
    }


class LocalDimension:
    def __init__(self, name, owner):
        self._name = name
        self.owner = owner
        self.full_name = f"{name}@{owner.name}@local.SLDPRT"

    @property
    def Name(self):
        return self._name

    @property
    def FullName(self):
        return self.full_name

    def GetFeatureOwner(self):
        return self.owner


class Equations:
    def __init__(self, rows, globals_=None):
        self.rows = rows
        self.globals = globals_ if globals_ is not None else [True] * len(rows)
        self.LinkToFile = False
        self.reads = []

    def GetCount(self):
        self.reads.append(("GetCount",))
        return len(self.rows)

    def Equation(self, index):
        self.reads.append(("Equation", index))
        return self.rows[index]

    def GlobalVariable(self, index):
        self.reads.append(("GlobalVariable", index))
        return self.globals[index]

    def EvaluateAll(self):
        raise AssertionError("qualification must not evaluate equations")


class EquationModel:
    def __init__(self, manager, *, configuration="Default", dimensions=None, path=None):
        self.manager = manager
        self.ConfigurationManager = types.SimpleNamespace(
            ActiveConfiguration=types.SimpleNamespace(Name=configuration)
        )
        self.dimensions = dimensions or {}
        self.lookups = []
        self.manager_reads = 0
        self.path = path

    def GetEquationMgr(self):
        self.manager_reads += 1
        return self.manager

    def GetPathName(self):
        assert self.path is not None, "dimension fixture must name its native part"
        return str(self.path)

    def Parameter(self, name):
        self.lookups.append(name)
        return self.dimensions.get(name)

    def ShowConfiguration2(self, name):
        raise AssertionError(f"qualification activated {name}")


def parse(model, budget=None, features=None):
    return dirty.parse_equations(
        model,
        budget or RecordingBudget(),
        referenced_configuration="Default",
        features=features or feature_graph(),
    )


def test_equations_accept_complete_local_dependency_grammar_without_evaluation(
    tmp_path,
):
    owner = Feature(7, "Sketch 1", "ProfileFeature")
    path = tmp_path / "local.SLDPRT"
    path.write_bytes(b"inert equation model")
    manager = Equations(
        [
            '"base length" = +2.5e+1mm',
            '"angle" = -(.25 + 2E-2) / 3',
            '"gain" = tan(("angle")) * "base length"',
            '"D1@Sketch 1" = "gain" + "D2@Sketch 1" - 1mm',
        ],
        [True, True, True, False],
    )
    model = EquationModel(
        manager,
        dimensions={
            "D1@Sketch 1": LocalDimension("D1", owner),
            "D2@Sketch 1": LocalDimension("D2", owner),
        },
        path=path,
    )
    budget = RecordingBudget()
    evidence = parse(model, budget, feature_graph(owner))
    assert isinstance(evidence, dict)
    for i in range(4):
        assert ("Equation", i) in manager.reads
        assert ("GlobalVariable", i) in manager.reads
    assert set(model.lookups) == {"D1@Sketch 1", "D2@Sketch 1"}
    assert model.manager_reads == 1
    assert len(budget.checks) >= 4
    assert '"D1@Sketch 1" = "gain"' in json.dumps(evidence).replace('\\"', '"')


@pytest.mark.parametrize(
    "literal",
    ["1.7976931348623157e308", "-1.7976931348623157e308mm", "5e-324", "0e999"],
)
def test_equations_accept_finite_native_double_literals_without_evaluation(literal):
    equation = f'"x" = {literal}'
    evidence = parse(EquationModel(Equations([equation])))
    assert evidence["count"] == 1
    assert evidence["entries"][0]["text"] == equation
    assert evidence["dependencies"] == {"x": []}


@pytest.mark.parametrize(
    "equation",
    [
        '"x" = 1 trailing',
        '"x" = 1 // comment',
        '"x" = 1; "y" = 2',
        '"x" = sin(1)',
        '"x" = TAN(1)',
        '"x" = tan()',
        '"x" = tan(1,2)',
        '"x" = 2^3',
        '"x" = 1in',
        '"x" = 1MM',
        '"x" = 1 mm',
        '"x" = 1e999',
        '"x" = 1.7976931348623159e308',
        '"x" = -1e309mm',
        '"x" = nan',
        '"x" = +',
        '"x" = (1 + 2',
        '"x" = 1 > 0',
        '"x" = if(1,2,3)',
        '"x" = "unknown"',
        '"x" = "D1@Sketch@assembly"',
        '"x" = "D1@part.SLDPRT"',
        '"x" = "C:\\part"',
        '"x" = "a/b"',
        '"x" = "a.b"',
        '"x" = "bad\tname"',
        '"x" = "a\\b"',
        '"x" = ""',
        '"x" = "a"b"',
        '"x" = external_command',
        '"@Sketch" = 1',
        '"D1@" = 1',
        '"x" = 1 = 2',
        "x = 1",
    ],
)
def test_equations_refuse_unknown_grammar_or_scope(equation):
    with pytest.raises(dirty.Inconclusive):
        parse(EquationModel(Equations([equation])))


@pytest.mark.parametrize(
    "rows,flags",
    [
        (['"x" = 1', '"x" = 2'], [True, True]),
        (['"x" = "y"', '"y" = "x"'], [True, True]),
        (['"x" = "x"'], [True]),
        (['"x" = 1'], [False]),
        (['"D1@Sketch" = 1'], [True]),
    ],
)
def test_equations_refuse_ambiguous_declarations_and_cycles(rows, flags):
    with pytest.raises(dirty.Inconclusive):
        parse(EquationModel(Equations(rows, flags)))


def test_equations_configuration_is_checked_before_manager_acquisition():
    model = EquationModel(Equations([]), configuration="Other")
    with pytest.raises(dirty.Inconclusive):
        parse(model)
    assert model.manager_reads == 0


@pytest.mark.parametrize(
    "fault", ["linked", "missing-manager", "wrong-count", "wrong-flag", "row-error"]
)
def test_equations_native_unavailability_is_not_empty(fault):
    manager = Equations(['"x" = 1'])
    model = EquationModel(manager)
    if fault == "linked":
        manager.LinkToFile = True
    elif fault == "missing-manager":
        model.manager = None
    elif fault == "wrong-count":
        manager.GetCount = lambda: True
    elif fault == "wrong-flag":
        manager.globals = [None]
    else:

        def fail(_index):
            raise RuntimeError("native equation read unavailable")

        manager.Equation = fail
    with pytest.raises(dirty.Inconclusive):
        parse(model)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "wrong-name",
        "wrong-owner",
        "missing-owner",
        "full-leaf",
        "full-feature",
        "full-model",
        "full-qualification",
    ],
)
def test_dimension_resolution_requires_local_name_and_scoped_owner(tmp_path, fault):
    owner = Feature(7, "Sketch", "ProfileFeature")
    dimension = LocalDimension("D1", owner)
    path = tmp_path / "local.SLDPRT"
    path.write_bytes(b"inert dimension model")
    if fault == "missing":
        dimension = None
    elif fault == "wrong-name":
        dimension._name = "Other"
    elif fault == "wrong-owner":
        dimension.owner = Feature(8, "Sketch", "ProfileFeature")
    elif fault == "missing-owner":
        dimension.owner = None
    else:
        dimension.full_name = {
            "full-leaf": "D2@Sketch@local.SLDPRT",
            "full-feature": "D1@Other@local.SLDPRT",
            "full-model": "D1@Sketch@different.SLDPRT",
            "full-qualification": "D1@Sketch@sub@local.SLDPRT",
        }[fault]
    model = EquationModel(
        Equations(['"D1@Sketch" = 1'], [False]),
        dimensions={"D1@Sketch": dimension},
        path=path,
    )
    with pytest.raises(dirty.Inconclusive):
        parse(model, features=feature_graph(owner))


def test_feature_traversal_descends_folders_and_keeps_same_name_distinct_ids():
    folder = Feature(1, "folder", "FtrFolder")
    first = Feature(2)
    second = Feature(3)
    grandchild = Feature(4)
    tail = Feature(5)
    folder.sub = first
    first.next_sub = second
    second.sub = grandchild
    folder.next = tail
    budget = RecordingBudget()
    graph = dirty.traverse_features(feature_receiver(folder), "child:Default", budget)
    assert set(graph["nodes"]) == {"1", "2", "3", "4", "5"}
    assert len(graph["occurrences"]) == 5
    assert graph["terminations"]
    assert "GetNextSubFeature" in second.calls
    assert "GetFirstSubFeature" in grandchild.calls
    assert "GetNextFeature" in tail.calls
    assert len(budget.checks) >= 5


def test_feature_reappearance_keeps_edges_and_explores_new_descendants():
    first = Feature(1, "folder", "FtrFolder")
    repeated = Feature(2)
    other_appearance = Feature(2)
    extra = Feature(3)
    first.sub = repeated
    first.next = other_appearance
    other_appearance.sub = extra
    graph = dirty.traverse_features(
        feature_receiver(first), "same-doc", RecordingBudget()
    )
    assert len(graph["occurrences"]) == 4
    assert sum(row["id"] == 2 for row in graph["occurrences"]) == 2
    assert "3" in graph["nodes"]
    assert "GetFirstSubFeature" in other_appearance.calls


@pytest.mark.parametrize(
    "fault",
    ["next-cycle", "sub-cycle", "id", "name", "type", "exception", "identity-conflict"],
)
def test_feature_malformed_or_unterminated_native_graph_is_inconclusive(fault):
    first = Feature(1)
    if fault == "next-cycle":
        first.next = first
    elif fault == "sub-cycle":
        first.sub = first
    elif fault == "id":
        first.identity = None
    elif fault == "name":
        first.name = None
    elif fault == "type":
        first.kind = None
    elif fault == "exception":
        first.error = RuntimeError("native next unavailable")
    else:
        first.next = Feature(1, "conflicting-name", "Cut")
    with pytest.raises(dirty.Inconclusive):
        dirty.traverse_features(feature_receiver(first), "child", RecordingBudget())


def test_feature_occurrence_cap_is_shared_between_inventories():
    state = {"occurrences": 4998}
    dirty.traverse_features(
        feature_receiver(Feature(1)), "first", RecordingBudget(), state
    )
    with pytest.raises(dirty.Inconclusive):
        dirty.traverse_features(
            feature_receiver(Feature(2)), "second", RecordingBudget(), state
        )


def test_feature_depth_cap_cannot_certify_a_partial_inventory():
    first = Feature(1)
    current = first
    for i in range(2, 35):
        current.sub = Feature(i)
        current = current.sub
    with pytest.raises(dirty.Inconclusive):
        dirty.traverse_features(feature_receiver(first), "deep", RecordingBudget())


class NativeContactComponent:
    def __init__(self, name, configuration="Default"):
        self.name = name
        self.configuration = configuration
        self.reads = []

    @property
    def Name2(self):
        self.reads.append("Name2")
        return self.name

    @property
    def ReferencedConfiguration(self):
        self.reads.append("ReferencedConfiguration")
        return self.configuration


class NativeInterference:
    def __init__(self, components, volume):
        self.components = components
        self.volume = volume
        self.reads = []
        self.error = None

    @property
    def Components(self):
        self.reads.append("Components")
        if self.error:
            raise self.error
        return self.components

    @property
    def Volume(self):
        self.reads.append("Volume")
        return self.volume


SETTINGS = {
    "TreatCoincidenceAsInterference": False,
    "TreatSubAssembliesAsComponents": True,
    "IncludeMultibodyPartInterferences": True,
    "MakeInterferingPartsTransparent": False,
    "CreateFastenersFolder": False,
    "UseTransform": False,
}


class NativeManager:
    def __init__(self, result):
        self.result = result
        self.compute_calls = 0
        self.done_calls = 0
        self.compute_error = None
        self.done_error = None
        for key, value in SETTINGS.items():
            setattr(self, key, value)

    def GetInterferences(self):
        self.compute_calls += 1
        if self.compute_error:
            raise self.compute_error
        return self.result

    def Done(self):
        self.done_calls += 1
        if self.done_error:
            raise self.done_error
        return None  # Generated binding VT_VOID: success is not truthy.


class AttemptAdapter:
    def __init__(self, model=None):
        self.currentModel = model
        self.swallowed = []

    def _attempt(self, fn, default=None):
        try:
            return fn()
        except Exception as exc:
            self.swallowed.append(exc)
            return default


def test_capture_forwards_identical_result_rows_components_and_void_done(
    monkeypatch, tmp_path
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    components = [NativeContactComponent("left"), NativeContactComponent("right")]
    rows = [NativeInterference(components, 1.234567890123e-9)]
    manager = NativeManager(rows)
    entry = {}
    capture = dirty.Capture(
        manager, RecordingBudget(), entry, component_limit=len(expected)
    )
    assert entry["settings"] == {}
    capture.observe_settings()
    assert entry["settings"] == SETTINGS
    returned = capture.GetInterferences()
    assert returned is rows
    assert returned[0] is rows[0]
    assert returned[0].Components is components
    assert returned[0].Components[0] is components[0]
    assert manager.compute_calls == 1
    assert capture.Done() is None
    assert manager.done_calls == 1
    assert entry["compute_calls"] == 1
    assert entry["errors"] == []
    assert entry["rows"][0]["volume_m3"] == rows[0].volume


def test_scoped_capture_keeps_real_factory_settings_and_real_policy_reads(
    monkeypatch, tmp_path
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    components = [NativeContactComponent("left"), NativeContactComponent("right")]
    row = NativeInterference(components, 1e-9)
    manager = NativeManager([row])
    for name, value in SETTINGS.items():
        setattr(manager, name, not value)
    model = types.SimpleNamespace(
        InterferenceDetectionManager=manager,
        ToolsCheckInterference=lambda: None,
    )
    adapter = AttemptAdapter(model)
    original = _assembly.configured_interference_manager
    ledger = []
    with dirty.scoped_capture(
        adapter, RecordingBudget(), ledger, "initial", component_limit=len(expected)
    ):
        _assembly.check_no_interference(
            adapter, allowed_pairs={frozenset({"left", "right"}): 2.0}
        )
    assert _assembly.configured_interference_manager is original
    assert manager.compute_calls == manager.done_calls == 1
    assert {name: getattr(manager, name) for name in SETTINGS} == SETTINGS
    assert ledger[0]["settings"] == SETTINGS
    assert not dirty._capture_errors(ledger)
    # The capture duplicates metadata observation, not the calculating call.
    assert row.reads.count("Volume") == 2
    assert row.reads.count("Components") == 2
    assert components[0].reads.count("Name2") == 2


@pytest.mark.parametrize(
    "fault",
    [
        "missing-name",
        "missing-config",
        "missing-volume",
        "nan",
        "infinity",
        "negative",
        "components-shape",
        "getter",
    ],
)
def test_capture_records_unavailable_native_metadata_without_replacing_result(
    monkeypatch, tmp_path, fault
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    components = [NativeContactComponent("left"), NativeContactComponent("right")]
    row = NativeInterference(components, 1e-9)
    if fault == "missing-name":
        components[0].name = None
    elif fault == "missing-config":
        components[0].configuration = ""
    elif fault == "missing-volume":
        row.volume = None
    elif fault == "nan":
        row.volume = float("nan")
    elif fault == "infinity":
        row.volume = float("inf")
    elif fault == "negative":
        row.volume = -1.0
    elif fault == "components-shape":
        row.components = "not a native array"
    else:
        row.error = RuntimeError("component getter unavailable")
    result = [row]
    manager = NativeManager(result)
    entry = {}
    capture = dirty.Capture(
        manager, RecordingBudget(), entry, component_limit=len(expected)
    )
    capture.observe_settings()
    assert capture.GetInterferences() is result
    assert entry["errors"], (
        "strict availability must precede the permissive production reads"
    )
    assert manager.compute_calls == 1
    assert capture.Done() is None


def test_capture_refuses_one_shot_results_without_consuming_or_substituting_them(
    monkeypatch, tmp_path
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    result = iter([NativeInterference([], 0.0)])
    manager = NativeManager(result)
    entry = {}
    capture = dirty.Capture(
        manager, RecordingBudget(), entry, component_limit=len(expected)
    )
    capture.observe_settings()
    assert capture.GetInterferences() is result
    assert entry["errors"]
    assert next(result).volume == 0.0
    capture.Done()


def test_compute_exception_is_recorded_before_attempt_swallows_it(
    monkeypatch, tmp_path
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    manager = NativeManager([])
    primary = RuntimeError("native compute failed")
    manager.compute_error = primary
    entry = {}
    capture = dirty.Capture(
        manager, RecordingBudget(), entry, component_limit=len(expected)
    )
    capture.observe_settings()
    adapter = AttemptAdapter()
    assert (
        adapter._attempt(capture.GetInterferences, default="swallowed") == "swallowed"
    )
    assert adapter.swallowed == [primary]
    assert manager.compute_calls == 1
    assert entry["errors"][0]["message"] == str(primary)
    assert dirty._capture_errors([entry])
    capture.Done()


def test_secondary_release_failure_does_not_mask_primary_and_restores_factory(
    monkeypatch, tmp_path
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    primary = ValueError("original consumer getter failure")
    row = NativeInterference([], 0.0)
    row.error = primary
    manager = NativeManager([row])
    manager.done_error = RuntimeError("secondary release failure")
    adapter = AttemptAdapter(
        types.SimpleNamespace(
            InterferenceDetectionManager=manager,
            ToolsCheckInterference=lambda: None,
        )
    )
    original = _assembly.configured_interference_manager
    ledger = []
    with pytest.raises(ValueError) as caught:
        with dirty.scoped_capture(
            adapter, RecordingBudget(), ledger, "sweep", component_limit=len(expected)
        ):
            _assembly.check_no_interference(adapter)
    assert caught.value is primary
    assert _assembly.configured_interference_manager is original
    assert dirty._capture_errors(ledger)
    assert manager.compute_calls == manager.done_calls == 1


def chain(features, *, sub=False):
    for current, following in zip(features, features[1:]):
        if sub:
            current.next_sub = following
        else:
            current.next = following
    if features:
        setattr(features[-1], "next_sub" if sub else "next", None)
    return features[0] if features else None


class NativeBody:
    def __init__(self, name="normal solid"):
        self.name = name
        self.kind = 0
        self.fault = None
        self.reads = []

    @property
    def Name(self):
        self.reads.append("Name")
        return self.name

    @property
    def Check3(self):
        self.reads.append("Check3")
        return self.fault

    def GetType(self):
        self.reads.append("GetType")
        return self.kind


class NativePart(EquationModel):
    def __init__(self, path):
        super().__init__(Equations([]))
        self.path = path
        self.feature = Feature(1, "native boss", "Boss")
        self.first_feature_calls = 0

    def GetType(self):
        return 1

    def GetPathName(self):
        return str(self.path)

    def GetTitle(self):
        return self.path.name

    def FirstFeature(self):
        self.first_feature_calls += 1
        return self.feature


IDENTITY = [
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
]


class NativeComponent(NativeContactComponent):
    def __init__(self, name, part, root=None):
        super().__init__(name)
        self.part = part
        self.root = root
        self.body = NativeBody()
        self.bodies = [self.body]
        self.body_info = [1]
        self.body_calls = []
        self.suppression = 3
        self.external_count = 0
        self.external_rows = (None, (), [], None, (), [], None, 0, "")
        self.children = None
        self.transform_reads = 0
        self.array_reads = 0
        self.transform_override = None
        self.first_feature_calls = 0
        self.external_calls = []

    def GetPathName(self):
        return str(self.part.path)

    def GetModelDoc2(self):
        return self.part

    def GetChildren(self):
        return self.children

    def GetSuppression2(self):
        return self.suppression

    def GetBodies3(self, kind):
        self.body_calls.append(kind)
        return (self.bodies, self.body_info)

    def ListExternalFileReferencesCount(self):
        self.external_calls.append("count")
        return self.external_count

    def ListExternalFileReferences2(self):
        self.external_calls.append("list")
        return self.external_rows

    def FirstFeature(self):
        self.first_feature_calls += 1
        return self.part.FirstFeature()

    def IsFixed(self):
        return False

    def IsPatternInstance(self):
        return False

    def GetConstrainedStatus(self):
        import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec

        stem = self.name.rsplit("-", 1)[0]
        return 2 if stem in spec.MOVING else 3

    @property
    def Transform2(self):
        self.transform_reads += 1
        component = self

        class FreshTransform:
            @property
            def ArrayData(self):
                component.array_reads += 1
                if component.transform_override is not None:
                    return component.transform_override
                matrix = list(IDENTITY)
                if component.root is not None:
                    origin = component.root.origin_for(component.name)
                    matrix[9:12] = [value / 1000.0 for value in origin]
                return matrix

        return FreshTransform()


class DriveParameter:
    def __init__(self, root):
        self.root = root
        self.value = 0.0

    @property
    def SystemValue(self):
        return self.value

    @SystemValue.setter
    def SystemValue(self, value):
        self.root.phase = "pose"
        self.root.writes.append(value)
        self.root.events.append(("write", self.root.generation, value))
        self.value = value


class NativeRoot(EquationModel):
    def __init__(self, path, parts, sweep, events, generation):
        import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec

        super().__init__(Equations([]), configuration="Authored")
        self.path = path
        self.sweep = sweep
        self.events = events
        self.generation = generation
        self.phase = "static"
        self.writes = []
        self.forces = []
        self.edits = []
        self.consumer_reads = []
        self.suppressions = []
        self.coincidents = []
        self.managers = []
        self.tools_calls = 0
        self.outer = False
        self.edit_result = True
        self.force_result = True
        self.compute_error = None
        self.saved_status = 0
        self.selected = []
        self.created_features = {}
        self.first_feature_calls = 0
        root = self

        class Extension:
            @property
            def NeedsRebuild2(self):
                root.events.append(("saved-status", root.generation))
                return root.saved_status

            def SelectByID2(self, name, kind, x, y, z, append, mark, callout, options):
                assert kind in {"AXIS", "PLANE"} and append is True and mark == 1
                assert (x, y, z, options) == (0.0, 0.0, 0.0, 0)
                root.selected.append(types.SimpleNamespace(name=name, kind=kind))
                root.events.append(("select", root.generation, name))
                return True

        self.Extension = Extension()
        self.SelectionManager = types.SimpleNamespace(
            GetSelectedObject6=lambda index, mark: (
                self.selected[index - 1] if mark == -1 else None
            ),
        )
        self.drive = DriveParameter(self)
        self.components = {
            spec.instance_name(stem, index): NativeComponent(
                spec.instance_name(stem, index),
                parts[stem],
                self,
            )
            for stem, placements in spec.PLACEMENTS.items()
            for index, _placement in enumerate(placements)
        }
        features = [
            Feature(1, "Origin", "OriginProfileFeature"),
            Feature(2, "Front Plane", "RefPlane"),
            Feature(3, "Top Plane", "RefPlane"),
            Feature(4, "Right Plane", "RefPlane"),
            Feature(5, "carrier seat datum", "RefPlane"),
            Feature(6, spec.CL_TIP_FEATURE, "ProfileFeature"),
        ]
        for index, component in enumerate(self.components.values(), 100):
            reference = Feature(index, component.name, "Reference")
            reference.GetSpecificFeature2 = lambda c=component: c
            features.append(reference)
        group = Feature(1000, "Mates", "MateGroup")
        mates = [
            Feature(1100 + i, label, "MateCoincident")
            for i, (label, _hole, _pin) in enumerate(spec.PIN_MATES["inner"])
        ]
        remaining = 2 * len(spec.CARRIAGE_PLACEMENTS) + 1
        mates += [
            Feature(1200 + i, f"seat {i}", "MateCoincident") for i in range(remaining)
        ]
        mates += [
            Feature(1300 + i, f"lock {i}", "MateLock")
            for i in range(sum(spec.QUANTITIES[stem] for stem in spec.LOCKED_TO))
        ]
        self.prepared_feature = None
        self.mate_group = group
        self.mate_features = mates
        group.sub = chain(mates, sub=True)
        features.append(group)
        self.first = chain(features)
        self.extra_features = features

    def GetType(self):
        return 2

    def GetPathName(self):
        return str(self.path)

    def GetTitle(self):
        return self.path.name

    def FirstFeature(self):
        self.first_feature_calls += 1
        return self.first

    def GetComponents(self, top_level_only):
        assert top_level_only is True
        return list(self.components.values())

    def GetComponentByName(self, name):
        self.consumer_reads.append(name)
        self.events.append(("carriage-read", self.generation, name))
        return self.components.get(name)

    def Parameter(self, name):
        return self.drive if name == "D1@DRIVE_carriage_slide" else None

    def ClearSelection2(self, all_marks):
        assert all_marks is True
        self.selected.clear()
        return None

    def CreateMateData(self, mate_type):
        assert type(mate_type) is int
        return types.SimpleNamespace(ErrorStatus=0, mate_type=mate_type)

    def CreateMate(self, data):
        assert len(data.EntitiesToMate) == 2
        if data.mate_type == sdk_assembly._MATE_TYPES["distance"]:
            assert self.prepared_feature is None
            feature = Feature(1500, "NativeDistance1", "MateDistanceDim")
            self.prepared_feature = feature
            self.drive.value = data.Distance
            self.phase = "prepare"
            self.events.append(("author", self.generation, feature.name, "distance"))
        else:
            assert data.mate_type == sdk_assembly._MATE_TYPES["coincident"]
            feature = Feature(
                1600 + len(self.coincidents),
                f"NativeCoincident{len(self.coincidents) + 1}",
                "MateCoincident",
            )
            self.coincidents.append(
                tuple(entity.name for entity in data.EntitiesToMate)
            )
            self.events.append(("coincident", self.generation, feature.name))
            self.phase = "native-remate"
            if len(self.coincidents) == 2:
                self.outer = True
        feature.GetErrorCode2 = lambda: (0, False)
        self.created_features[feature.name] = feature
        self.mate_features.append(feature)
        self.mate_group.sub = chain(self.mate_features, sub=True)
        return feature

    def FeatureByName(self, name):
        if self.prepared_feature is not None and name == self.prepared_feature.name:
            return self.prepared_feature
        return self.created_features.get(name)

    def ForceRebuild3(self, top_only):
        assert top_only is False
        self.forces.append((self.phase, len(self.writes)))
        self.events.append(("force", self.generation, self.phase, len(self.writes)))
        return self.force_result

    def EditRebuild3(self):
        self.edits.append((self.phase, len(self.writes)))
        self.events.append(("edit", self.generation, self.phase, len(self.writes)))
        return self.edit_result

    def ToolsCheckInterference(self):
        self.tools_calls += 1
        self.events.append(("tools", self.generation))
        return None

    @property
    def InterferenceDetectionManager(self):
        pairs = verify.allowed_interference_pairs(verify.SWEEP_OWNER)
        rows = []
        for pair, limit in pairs.items():
            if len(pair) == 2 and limit > 0 and pair <= self.components.keys():
                components = [self.components[name] for name in sorted(pair)]
                volume = min(float(limit) / 10.0, 1.0) * 1e-9
                rows.append(NativeInterference(components, volume))
        manager = NativeManager(rows)
        manager.compute_error = self.compute_error
        self.managers.append(manager)
        return manager

    def origin_for(self, name):
        if not self.writes:
            poses = self.sweep["passes"][0]["poses"]
            return poses[0]["carriages"].get(name, [0.0, 0.0, 0.0])
        poses = self.sweep["passes"][int(self.outer)]["poses"]
        drive_mm = self.drive.value * 1000.0
        pose = min(poses, key=lambda row: abs(row["drive_mm"] - drive_mm))
        return pose["carriages"].get(name, [0.0, 0.0, 0.0])


class NativeApp:
    def __init__(self, adapter):
        self.adapter = adapter

    @property
    def ActiveDoc(self):
        return self.adapter.currentModel

    @property
    def IActiveDoc2(self):
        return self.adapter.currentModel

    def GetFirstDocument(self):
        root = self.adapter.currentModel
        self.adapter.events.append(("residents", root.generation if root else None))
        if self.adapter.enumeration_error:
            raise self.adapter.enumeration_error
        documents = self.adapter.resident_docs
        return documents[0] if documents else None

    def CloseDoc(self, title):
        root = self.adapter.currentModel
        assert root is not None and title == root.GetTitle()
        if self.adapter.before_close_hook:
            self.adapter.before_close_hook(root)
        self.adapter.events.append(("close", root.generation))
        self.adapter.currentModel = None
        self.adapter.resident_docs.clear()
        if self.adapter.close_hook:
            self.adapter.close_hook(root)

    def CloseAllDocuments(self, include_unsaved):
        assert include_unsaved is True
        root = self.adapter.currentModel
        self.adapter.events.append(("close-all", root.generation if root else None))
        self.adapter.currentModel = None
        self.adapter.resident_docs.clear()
        return True


class NativeAdapter(AttemptAdapter, sdk_assembly.SolidWorksAssemblyMixin):
    def __init__(self, path, parts, sweep):
        super().__init__()
        self.path = path
        self.parts = parts
        self.sweep = sweep
        self.events = []
        self.roots = []
        self.resident_docs = []
        self.enumeration_error = None
        self.swApp = NativeApp(self)
        self.open_hook = None
        self.close_hook = None
        self.before_close_hook = None

    def _handle_com_operation(self, operation, callback):
        from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

        assert operation == "add_mate"
        try:
            return AdapterResult(status=AdapterResultStatus.SUCCESS, data=callback())
        finally:
            if self.currentModel.phase != "prepare":
                self.currentModel.phase = "pose"

    async def open_model(self, path):
        assert self.currentModel is None, (
            "candidate must be discarded before reference open"
        )
        assert not self.resident_docs, (
            "hidden children must be discarded before reference open"
        )
        assert Path(path).resolve() == self.path.resolve()
        parts = {stem: NativePart(part.path) for stem, part in self.parts.items()}
        root = NativeRoot(self.path, parts, self.sweep, self.events, len(self.roots))
        self.resident_docs = [root, *parts.values()]
        for index, document in enumerate(self.resident_docs):
            following = (
                self.resident_docs[index + 1]
                if index + 1 < len(self.resident_docs)
                else None
            )
            document.GetNext = lambda next_document=following: next_document
        self.currentModel = root
        self.roots.append(root)
        self.events.append(("open", root.generation))
        if self.open_hook:
            self.open_hook(root)
        return types.SimpleNamespace(is_success=True, data=True)

    async def list_configurations(self):
        return types.SimpleNamespace(is_success=True, data=["Authored", verify.REST])

    async def set_active_configuration(self, configuration):
        root = self.currentModel
        self.events.append(("activate", root.generation, configuration))
        root.ConfigurationManager.ActiveConfiguration.Name = configuration
        return types.SimpleNamespace(is_success=True, data=True)

    async def rename_feature(self, parameters):
        root = self.currentModel
        self.events.append(("rename", root.generation, parameters.new_name))
        feature = root.created_features.pop(parameters.old_name)
        feature.name = parameters.new_name
        root.created_features[feature.name] = feature
        return types.SimpleNamespace(is_success=True, data=True)

    async def suppress_mate(self, parameters):
        root = self.currentModel
        root.suppressions.append((parameters.name, parameters.suppress))
        self.events.append(("suppress", root.generation, parameters.name))
        return types.SimpleNamespace(is_success=True, data=True)


def install_native_case(monkeypatch, tmp_path):
    """Install inert ports; never replace either real verification consumer."""
    import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec

    tmp_path.mkdir(parents=True, exist_ok=True)
    parts = {}
    for stem in spec.PLACEMENTS:
        path = tmp_path / f"{stem}.SLDPRT"
        path.write_bytes(f"inert part {stem}".encode())
        parts[stem] = NativePart(path)
    root_path = tmp_path / f"{verify.SWEEP_OWNER}.SLDASM"
    root_path.write_bytes(b"inert saved assembly")
    sweep = spec.sweep_sidecar()
    sweep_path = tmp_path / f".{verify.SWEEP_OWNER}.sweep.json"
    sweep_path.write_text(json.dumps(sweep), encoding="utf-8")
    manifest = [
        {
            "key": spec.SLIDE_KEY,
            "kind": "distance",
            "entities": [
                {
                    "entity_type": "PLANE",
                    "name": f"Right Plane@{spec.instance_name(stem, 0)}",
                }
                for stem in (spec.RAIL, spec.CARRIAGE)
            ],
            "params": {"distance": sweep["passes"][0]["poses"][0]["drive_mm"]},
            "verify": None,
            "witness": None,
            "flip": False,
        }
    ]
    dof_path = tmp_path / f".{verify.SWEEP_OWNER}.dof.json"
    dof_path.write_text(json.dumps({"specs": manifest}), encoding="utf-8")
    policy = tmp_path / "interference-policy.yaml"
    policy.write_text("inert pinned policy\n", encoding="utf-8")
    expected = {
        spec.instance_name(stem, i): parts[stem].path
        for stem, placements in spec.PLACEMENTS.items()
        for i, _placement in enumerate(placements)
    }
    paths = [root_path, sweep_path, dof_path, policy, *[p.path for p in parts.values()]]
    adapter = NativeAdapter(root_path, parts, sweep)

    monkeypatch.setattr(
        sdk_assembly, "dispatch_array", lambda entities: tuple(entities)
    )
    monkeypatch.setattr(sdk_assembly, "null_callout", lambda: None)
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(verify, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(dirty, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(verify, "_assert_fresh", lambda _name, _report: True)
    monkeypatch.setattr(_assembly, "whats_wrong", lambda _adapter, _model: [])
    monkeypatch.setattr(
        dirty,
        "_provenance",
        lambda: {
            "source": "862ec3315ce0449e85021b719b70ff0283be1698",
            "sdk": "1ec68e3d12e0518e9bb152eff3d91b4bebd2b229",
        },
    )
    monkeypatch.setattr(dirty, "_input_paths", lambda _name: (expected, paths))
    monkeypatch.setattr(dirty, "REPORT_PATH", tmp_path / "diagnostic.json")
    monkeypatch.setattr(dirty, "BUDGET_PATH", tmp_path / "budget.json")
    monkeypatch.setattr(dirty, "FAILURE_PATH", tmp_path / "failure.json")
    # All graph methods remain real; Python inert receivers bypass makepy binding.
    from solidworks_mcp.adapters import sw_type_info

    monkeypatch.setattr(sw_type_info, "flag_methods", lambda *_args: 0)

    return adapter, expected, paths


async def open_prepared_root(adapter):
    """Exercise actual authoring and pinned SDK Edit before direct admission."""
    await adapter.open_model(str(adapter.path))
    await adapter.set_active_configuration(verify.REST)
    names = await _assembly_postbuild.author_dof_drives(
        adapter,
        _assembly_postbuild.load_dof_manifest(verify.SWEEP_OWNER),
    )
    assert names == ["DRIVE_carriage_slide"]
    return adapter.currentModel


def test_actual_admission_accepts_full_native_inventory_and_all_configured_solids(
    monkeypatch, tmp_path
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    root = asyncio.run(open_prepared_root(adapter))
    evidence = dirty.admit(
        adapter,
        expected,
        RecordingBudget(),
        "DRIVE_carriage_slide",
        adapter.sweep,
        checkpoint=recording_checkpoint(),
    )
    assert set(evidence["instances"]) == set(expected)
    assert evidence["root_features"]["terminations"]
    assert len(evidence["child_inventories"]) == len(adapter.parts)
    for name, component in root.components.items():
        assert component.body_calls == [-1]
        assert component.body.reads.count("Check3") == 1
        assert "Name" in component.body.reads
        assert Path(evidence["instances"][name]["path"]) == expected[name].resolve()


@pytest.mark.parametrize(
    "fault",
    [
        "sheet",
        "user-body",
        "body-info-cardinality",
        "body-fault",
        "suppressed",
        "suppression-error",
        "nested",
        "external-count",
        "external-shape",
        "external-row-mismatch",
        "wrong-path",
        "unknown-feature",
        "hidden-unknown-descendant",
    ],
)
def test_actual_admission_does_not_turn_unknown_native_availability_into_clean(
    monkeypatch, tmp_path, fault
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    root = asyncio.run(open_prepared_root(adapter))
    component = next(iter(root.components.values()))
    if fault == "sheet":
        component.body.kind = 1
    elif fault == "user-body":
        component.body_info = [0]
    elif fault == "body-info-cardinality":
        component.body_info = []
    elif fault == "body-fault":
        component.body.fault = types.SimpleNamespace(Count=1)
    elif fault == "suppressed":
        component.suppression = 0
    elif fault == "suppression-error":
        component.suppression = 5
    elif fault == "nested":
        component.children = [object()]
    elif fault == "external-count":
        component.external_count = 1
    elif fault == "external-shape":
        component.external_rows = (True, [], [], [])
    elif fault == "external-row-mismatch":
        component.external_rows = (["other.SLDPRT"], (), (), (), (), (), (), 0, "")
    elif fault == "wrong-path":
        component.GetPathName = lambda: str(adapter.path)
    elif fault == "unknown-feature":
        component.part.feature.kind = "MacroFeature"
    else:
        component.part.feature.sub = Feature(2, "hidden child", "Sensor")
    with pytest.raises(dirty.Inconclusive):
        dirty.admit(
            adapter,
            expected,
            RecordingBudget(),
            "DRIVE_carriage_slide",
            adapter.sweep,
            checkpoint=recording_checkpoint(),
        )


EXPECTED_KEYS = (
    [f"inner:{i}:visit" for i in range(7)]
    + ["outer:0:pre-remate", "outer:0:post-remate"]
    + [f"outer:{i}:visit" for i in range(7)]
)
GATE_SUFFIXES = [
    "saved-rebuild-clean",
    "dof-free-necessity",
    "no-over-constrained",
    "model-healthy",
    "interference-free",
    "pass-sweep-interference-free",
]


def assert_full_pair(adapter, expected, evidence, outer_report):
    """Assert native work independently of the diagnostic's own count fields."""
    assert evidence["status"] == "complete-parent-decision-required", evidence
    assert not evidence["errors"]
    assert not outer_report.failed
    assert evidence["census_publication"] == {
        "status": "inactive",
        "attempts": 0,
        "last_success": None,
        "errors": [],
    }
    assert [row["variant"] for row in evidence["trajectories"]] == ["B", "A"]
    assert len(adapter.roots) == 2
    b_root, a_root = adapter.roots
    assert b_root is not a_root
    for name in expected:
        assert b_root.components[name] is not a_root.components[name]
        assert b_root.components[name].body is not a_root.components[name].body
        assert b_root.components[name].part is not a_root.components[name].part

    for root, row in zip(adapter.roots, evidence["trajectories"], strict=True):
        assert [boundary["key"] for boundary in row["boundaries"]] == EXPECTED_KEYS
        assert row["counts"] == {
            "writes": 15,
            "visits": 14,
            "reads": 28,
            "suppressions": 2,
            "coincidences": 2,
        }
        assert len(root.writes) == 15
        assert len(root.consumer_reads) == 28
        assert len(root.suppressions) == len(root.coincidents) == 2
        assert root.tools_calls == 11
        assert len(root.managers) == 11
        assert all(
            manager.compute_calls == manager.done_calls == 1
            for manager in root.managers
        )
        assert row["gates"] == {
            "passed": [f"{verify.SWEEP_OWNER}:{suffix}" for suffix in GATE_SUFFIXES],
            "failed": [],
        }
        assert row["cleanup"]["confirmed"] is True
        assert row["cleanup"]["after"] == []
        assert row["admission"]["admitted"] is True
        admission = row["admission"]
        census = admission["census"]
        assert (
            census["authentication_status"] == census["children_status"] == "complete"
        )
        assert (
            census["identity_seen_count"]
            == census["authenticated_instance_count"]
            == len(expected)
        )
        assert (
            census["expected_scope_count"]
            == census["discovered_scope_count"]
            == len(adapter.parts)
        )
        assert census["completed_graph_count"] == len(adapter.parts)
        assert census["unknown_categories"] == []
        assert (
            census["root_graph_status"]
            == census["root_category_scan_status"]
            == census["root_validation_status"]
            == "complete"
        )
        assert root.first_feature_calls == root.manager_reads == 1
        assert sum(
            component.first_feature_calls for component in root.components.values()
        ) == len(adapter.parts)
        for part in {
            component.part.path: component.part
            for component in root.components.values()
        }.values():
            assert part.first_feature_calls == part.manager_reads == 1
            assert part.feature.calls.count("GetID") == 1
        for component in root.components.values():
            assert component.body_calls == [-1]
            assert component.body.reads.count("Check3") == 1
            assert component.external_calls == ["count", "list"]
        for child in admission["child_inventories"].values():
            assert (
                child["graph_status"]
                == child["category_scan_status"]
                == child["validation_status"]
                == "complete"
            )
            assert child["category_records_scanned"] == len(child["features"]["nodes"])
        assert not row["validation_errors"]
        assert len(row["interferences"]) == 11
        assert (
            sum(entry["label"] == "initial/static" for entry in row["interferences"])
            == 1
        )
        assert all(entry["checked_outside_attempt"] for entry in row["interferences"])
        assert all(not entry["errors"] for entry in row["interferences"])
        assert all(entry["canonical"] for entry in row["interferences"])
        assert root.forces[:2] == [("static", 0), ("prepare", 0)]
        pose_forces = [item for item in root.forces if item[0] == "pose"]
        assert len(pose_forces) == (16 if row["variant"] == "A" else 0)
        assert len(root.forces) == (18 if row["variant"] == "A" else 2)
        assert (
            len(root.edits) == 19
        )  # Sixteen explicit + one prepare + two remate SDK Edits.
        assert len(row["remate_attempts"]) == 2
        assert all(item["recognized_pinned_form"] for item in row["remate_attempts"])
        assert all(
            Path(item["callsite"]["path"]) == Path(sdk_assembly.__file__).resolve()
            for item in row["remate_attempts"]
        )
        assert len(row["prepare_attempts"]) == 2
        assert [item["rebuild_members"] for item in row["prepare_attempts"]] == [
            ["EditRebuild3"],
            ["ForceRebuild3"],
        ]
        assert all(item["recognized_pinned_form"] for item in row["prepare_attempts"])
        assert (
            Path(row["prepare_attempts"][0]["callsite"]["path"])
            == Path(sdk_assembly.__file__).resolve()
        )
        assert root.edits[0] == ("prepare", 0)
        aggregate = row["original_aggregate_timings"]
        assert aggregate["jig.drive_write_attempts"] == 15
        assert aggregate["jig.transform_readback_attempts"] == 28
        assert aggregate["jig.edit_rebuild_attempts"] == 16
        assert aggregate["jig.force_rebuild_attempts"] == (
            16 if row["variant"] == "A" else 0
        )
        for boundary in row["boundaries"]:
            assert set(boundary["instances"]) == set(expected)
            assert [item["operation"] for item in boundary["rebuilds"]] == (
                ["explicit_force", "explicit_edit"]
                if row["variant"] == "A"
                else ["explicit_edit"]
            )
            for instance in boundary["instances"].values():
                assert len(instance["array_data"]) == 16
                assert len(instance["meaningful"]) == 13
                assert len(instance["unused"]) == 3
        pre, post = row["boundaries"][7:9]
        assert pre["key"] == "outer:0:pre-remate"
        assert post["key"] == "outer:0:post-remate"
        assert pre is not post
        # Every instance read obtains a fresh transform and then fresh ArrayData.
        for component in root.components.values():
            assert component.transform_reads == component.array_reads
            assert component.transform_reads >= 16
        events = [
            event
            for event in adapter.events
            if len(event) > 1 and event[1] == root.generation
        ]
        saved = next(i for i, event in enumerate(events) if event[0] == "saved-status")
        activation = next(i for i, event in enumerate(events) if event[0] == "activate")
        first_force = next(i for i, event in enumerate(events) if event[0] == "force")
        assert saved < activation < first_force
        mutations = [
            event[0] for event in events if event[0] in {"suppress", "coincident"}
        ]
        assert mutations == ["suppress", "suppress", "coincident", "coincident"]
    close_b = adapter.events.index(("close", 0))
    open_a = adapter.events.index(("open", 1))
    assert close_b < open_a
    assert any(
        event[0] == "residents" for event in adapter.events[close_b + 1 : open_a]
    )
    assert evidence["cleanup"]["confirmed"] is True
    assert adapter.currentModel is None
    assert adapter.resident_docs == []
    assert "_attempt" not in adapter.__dict__
    assert [snapshot["stage"] for snapshot in evidence["input_snapshots"]] == [
        "before-B",
        "after-B-cleanup",
        "before-A",
        "after-A-cleanup",
        "final-cleanup",
    ]
    assert all(
        snapshot["files"] == evidence["input_snapshots"][0]["files"]
        for snapshot in evidence["input_snapshots"]
    )
    assert not evidence["comparison"]["unclassified_differences"]
    assert evidence["comparison"]["alarms_are_acceptance_thresholds"] is False


def test_run_executes_both_real_consumers_exact_work_and_independent_cleanup(
    monkeypatch, tmp_path
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    writes = []
    original_write = dirty._write_json

    def record_write(path, value):
        writes.append(path)
        return original_write(path, value)

    monkeypatch.setattr(dirty, "_write_json", record_write)
    outer_report = verify.Report()
    evidence = asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, outer_report))
    assert_full_pair(adapter, expected, evidence, outer_report)
    assert json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8")) == evidence
    persisted_budget = json.loads(dirty.BUDGET_PATH.read_text(encoding="utf-8"))
    assert persisted_budget["submission"] == 1
    assert persisted_budget["hard_deadline"] is False
    assert not dirty.FAILURE_PATH.exists()
    assert writes.count(dirty.REPORT_PATH) == 1
    assert writes.count(dirty.FAILURE_PATH) == 0
    assert not dirty.FAILURE_PATH.with_suffix(".json.tmp").exists()

    # Delete an observation only after the complete real consumer ran. Full
    # pose/gate/count evidence cannot substitute for the SDK prepare Edit.
    missing_prepare_edit = copy.deepcopy(evidence["trajectories"][0])
    missing_prepare_edit["prepare_attempts"] = [
        item
        for item in missing_prepare_edit["prepare_attempts"]
        if item["rebuild_members"] != ["EditRebuild3"]
    ]
    issues = dirty._validate_trajectory(
        missing_prepare_edit, expected, verify.SWEEP_OWNER
    )
    assert {
        "phase": "helper_rebuild_counts",
        "prepare_forces": 1,
        "prepare_edits": 0,
        "remate_edits": 2,
    } in issues


@pytest.mark.parametrize(
    "stage", ["before-B", "before-A", "after-B-discard", "final-cleanup"]
)
def test_actual_run_rejects_unrelated_residents_without_reference_reopen_or_green_cleanup(
    monkeypatch, tmp_path, stage
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    unrelated = NativePart(tmp_path / "unrelated.SLDPRT")
    unrelated.GetNext = lambda: None
    unrelated_row = {
        "path": str(unrelated.path.resolve()),
        "title": unrelated.GetTitle(),
    }
    if stage == "before-B":
        adapter.resident_docs.append(unrelated)
    original_hash = dirty._hash_inputs
    original_close_all = adapter.swApp.CloseAllDocuments
    original_close_doc = adapter.swApp.CloseDoc
    original_static = verify._verify_static_one
    original_walk = verify._walk_pass_sweep
    injected = False
    close_titles = []

    def inject_after_cleanup(paths):
        nonlocal injected
        snapshot = original_hash(paths)
        target = {"before-A": 1, "final-cleanup": 2}.get(stage)
        if (
            target is not None
            and not injected
            and len(adapter.roots) == target
            and adapter.currentModel is None
        ):
            assert not adapter.resident_docs
            adapter.resident_docs.append(unrelated)
            injected = True
        return snapshot

    def close_all_with_unrelated_survivor(include_unsaved):
        surviving = unrelated in adapter.resident_docs
        result = original_close_all(include_unsaved)
        if surviving or (stage == "after-B-discard" and len(adapter.roots) == 1):
            adapter.resident_docs.append(unrelated)
        return result

    def record_owned_close(title):
        close_titles.append(title)
        return original_close_doc(title)

    monkeypatch.setattr(dirty, "_hash_inputs", inject_after_cleanup)
    monkeypatch.setattr(
        adapter.swApp, "CloseAllDocuments", close_all_with_unrelated_survivor
    )
    monkeypatch.setattr(adapter.swApp, "CloseDoc", record_owned_close)
    outer_report = verify.Report()
    if stage == "final-cleanup":
        evidence = asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, outer_report))
    else:
        with pytest.raises(dirty.Inconclusive, match="resident|cleanup"):
            asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, outer_report))
        evidence = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert evidence["status"] == "inconclusive"
    assert outer_report.failed
    assert json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8")) == evidence
    assert json.loads(dirty.FAILURE_PATH.read_text(encoding="utf-8")) == evidence
    variants = (
        [] if stage == "before-B" else ["B", "A"] if stage == "final-cleanup" else ["B"]
    )
    assert [row["variant"] for row in evidence["trajectories"]] == variants
    assert len(adapter.roots) == len(variants)
    assert verify._verify_static_one is original_static
    assert verify._walk_pass_sweep is original_walk
    for root, row in zip(adapter.roots, evidence["trajectories"], strict=True):
        assert [boundary["key"] for boundary in row["boundaries"]] == EXPECTED_KEYS
        assert row["counts"] == {
            "writes": 15,
            "visits": 14,
            "reads": 28,
            "suppressions": 2,
            "coincidences": 2,
        }
        assert len(root.writes) == 15
        assert len(root.consumer_reads) == 28
        assert len(root.suppressions) == len(root.coincidents) == 2
        assert len(root.edits) == 19
        assert len(root.forces) == (18 if row["variant"] == "A" else 2)
        assert root.tools_calls == len(root.managers) == 11
        assert all(
            manager.compute_calls == manager.done_calls == 1
            for manager in root.managers
        )
        assert row["gates"] == {
            "passed": [f"{verify.SWEEP_OWNER}:{suffix}" for suffix in GATE_SUFFIXES],
            "failed": [],
        }
    assert evidence["cleanup"]["confirmed"] is False
    assert evidence["cleanup"]["after"] == [unrelated_row]
    assert any(
        error["phase"] == "cleanup.verify"
        and "document remains resident" in error["message"]
        for error in evidence["cleanup"]["errors"]
    )
    assert adapter.currentModel is None
    assert adapter.resident_docs == [unrelated]
    assert unrelated.GetTitle() not in close_titles
    if stage == "before-A":
        assert evidence["trajectories"][0]["cleanup"]["confirmed"] is True
    if stage == "after-B-discard":
        assert evidence["trajectories"][0]["cleanup"]["confirmed"] is False
    if stage == "final-cleanup":
        assert all(row["cleanup"]["confirmed"] for row in evidence["trajectories"])
        assert evidence["comparison"] is not None


@pytest.mark.parametrize("previous_reports", [False, True])
def test_actual_run_refuses_existing_submission_without_touching_prior_evidence_or_native_state(
    monkeypatch, tmp_path, previous_reports
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    prior_document = NativePart(tmp_path / "preexisting.SLDPRT")
    prior_document.GetNext = lambda: None
    adapter.currentModel = prior_document
    resident_docs = adapter.resident_docs
    resident_docs.append(prior_document)
    previous = {dirty.BUDGET_PATH: b'{"submission": 1, "prior": true}\r\n'}
    if previous_reports:
        previous.update(
            {
                dirty.REPORT_PATH: b"prior report bytes\r\n\xff",
                dirty.FAILURE_PATH: b"prior failure bytes\x00\n",
            }
        )
    for path, payload in previous.items():
        path.write_bytes(payload)
    existing_files = set(tmp_path.iterdir())
    writes = []
    original_write = dirty._write_json

    def record_write(path, value):
        writes.append(path)
        return original_write(path, value)

    monkeypatch.setattr(dirty, "_write_json", record_write)
    discovery = []
    original_provenance = dirty._provenance
    original_inputs = dirty._input_paths
    original_hash = dirty._hash_inputs

    def record_provenance():
        discovery.append("provenance")
        return original_provenance()

    def record_inputs(name):
        discovery.append("inputs")
        return original_inputs(name)

    def record_hash(paths):
        discovery.append("hash")
        return original_hash(paths)

    monkeypatch.setattr(dirty, "_provenance", record_provenance)
    monkeypatch.setattr(dirty, "_input_paths", record_inputs)
    monkeypatch.setattr(dirty, "_hash_inputs", record_hash)
    outer_report = verify.Report()
    outer_report.passed.append("previous-pass")
    outer_report.failed.append(("previous-failure", "previous-reason"))
    with pytest.raises(dirty.Inconclusive, match="already exists|resubmission"):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, outer_report))
    for path, payload in previous.items():
        assert path.read_bytes() == payload
    if not previous_reports:
        assert not dirty.REPORT_PATH.exists()
        assert not dirty.FAILURE_PATH.exists()
    assert discovery == []
    assert writes == []
    assert set(tmp_path.iterdir()) == existing_files
    assert not dirty.FAILURE_PATH.with_suffix(".json.tmp").exists()
    assert not dirty.REPORT_PATH.with_suffix(".json.tmp").exists()
    assert adapter.events == []
    assert adapter.roots == []
    assert adapter.currentModel is prior_document
    assert adapter.resident_docs is resident_docs
    assert resident_docs == [prior_document]
    assert outer_report.passed == ["previous-pass"]
    assert outer_report.failed == [("previous-failure", "previous-reason")]
    assert "_attempt" not in adapter.__dict__


@pytest.mark.parametrize(
    "fault", ["false-edit", "swallowed-edit", "swallowed-compute", "missing-volume"]
)
def test_native_false_or_swallowed_failure_cannot_be_green(
    monkeypatch, tmp_path, fault, caplog
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    annotations = []
    monkeypatch.setattr(
        _telemetry, "annotate", lambda **fields: annotations.append(fields)
    )

    def inject(root):
        if fault == "false-edit":
            root.edit_result = False
        elif fault == "swallowed-edit":

            def fail():
                raise RuntimeError("native pose edit unavailable")

            root.EditRebuild3 = fail
        elif fault == "swallowed-compute":
            root.compute_error = RuntimeError("native interference compute unavailable")
        else:
            original = type(root).InterferenceDetectionManager.fget

            class MissingVolumeRoot(type(root)):
                @property
                def InterferenceDetectionManager(self):
                    manager = original(self)
                    manager.result[0].volume = None
                    return manager

            root.__class__ = MissingVolumeRoot

    adapter.open_hook = inject
    outer_report = verify.Report()
    evidence = asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, outer_report))
    assert evidence["status"] != "complete-parent-decision-required"
    assert outer_report.failed
    assert evidence["cleanup"]["confirmed"] is True
    assert any(row["validation_errors"] for row in evidence["trajectories"])
    if fault == "false-edit":
        outcomes = evidence["trajectories"][0]["native_outcomes"]
        assert any(item.get("result") is False for item in outcomes)
    elif fault == "swallowed-compute":
        entries = evidence["trajectories"][0]["interferences"]
        assert all(entry["errors"] for entry in entries)
        assert all(entry["checked_outside_attempt"] for entry in entries)
        assert not evidence["trajectories"][0]["gates"]["failed"]
    assert (
        json.loads(dirty.FAILURE_PATH.read_text(encoding="utf-8"))["status"]
        == evidence["status"]
    )
    summary = dirty._rejection_summary(evidence)
    rejection_logs = [
        record.message
        for record in caplog.records
        if record.message.startswith("dirty-Edit diagnostic rejected [")
    ]
    assert len(rejection_logs) == 1
    assert summary in rejection_logs[0]
    assert annotations[-1]["jig.diagnostic.rejection"] == summary
    assert (
        f"{verify.SWEEP_OWNER}:dirty-edit-diagnostic",
        f"{summary}; inspect jig-dirty-edit.json",
    ) in outer_report.failed


def test_rejection_summary_bounds_only_log_projection_and_preserves_first_cause():
    first = {"phase": "prepare", "message": "original failure " + "x" * 1024}
    evidence = {
        "status": "inconclusive",
        "trajectories": [
            {
                "variant": "B",
                "errors": [first, {"phase": "secondary", "message": "later"}],
                "gates": {"failed": []},
                "validation_errors": [{"phase": "helper_rebuild_counts"}],
            }
        ],
        "errors": [{"phase": "secondary.final_cleanup", "message": "later cleanup"}],
        "comparison": None,
    }
    before = copy.deepcopy(evidence)
    assert dirty._rejection_summary(evidence) == f"B:prepare: {first['message']}"[:512]
    assert evidence == before


def test_disk_mutation_stops_before_reference_reopen_and_preserves_failure_evidence(
    monkeypatch, tmp_path
):
    adapter, _expected, paths = install_native_case(monkeypatch, tmp_path)
    target = next(path for path in paths if path.suffix == ".SLDPRT")
    adapter.close_hook = lambda _root: target.write_bytes(b"unexpected modified input")
    outer_report = verify.Report()
    with pytest.raises(dirty.Inconclusive, match="bytes changed|closure changed"):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, outer_report))
    report = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert report["status"] == "inconclusive"
    assert len(adapter.roots) == 1
    assert report["errors"]
    assert report["cleanup"]["confirmed"] is True
    assert (
        report["input_snapshots"][0]["files"] != report["input_snapshots"][-1]["files"]
    )


def test_early_incomplete_real_sweep_cannot_be_certified_by_passing_static_gates(
    monkeypatch, tmp_path
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    original_transform = verify.component_transform
    reads = []

    def off_station(actual_adapter, name):
        reads.append(name)
        values = original_transform(actual_adapter, name)
        values[9] += 0.001  # 1 mm, beyond the unchanged original 0.05 mm criterion.
        return values

    monkeypatch.setattr(verify, "component_transform", off_station)
    with pytest.raises(dirty.Inconclusive, match="incomplete|ineligible"):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    report = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert report["status"] != "complete-parent-decision-required"
    assert len(adapter.roots) == 1
    row = report["trajectories"][0]
    assert row["counts"]["visits"] == 1
    assert len(reads) == row["counts"]["reads"] == 2
    assert len(row["boundaries"]) == 1
    assert row["gates"]["failed"][-1][0].endswith(":pass-sweep-interference-free")
    assert row["cleanup"]["confirmed"] is True


def test_cleanup_enumeration_failure_is_unconfirmed_without_masking_primary(
    monkeypatch, tmp_path
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    asyncio.run(adapter.open_model(str(adapter.path)))
    adapter.enumeration_error = RuntimeError("hidden resident enumeration unavailable")
    cleanup = dirty._cleanup(adapter, {str(adapter.path.resolve())}, RecordingBudget())
    assert cleanup["confirmed"] is False
    assert cleanup["errors"]
    assert adapter.currentModel is None


def test_cumulative_budget_reserves_cleanup_and_never_restarts_allowance(tmp_path):
    now = [100.0]
    path = tmp_path / "budget.json"
    budget = dirty.Budget(path, clock=lambda: now[0])
    with budget.unit("native-start"):
        now[0] += 2999.0
    budget.check("last-admissible-unit")
    with budget.offline():
        now[0] += 1.0
    with pytest.raises(dirty.Inconclusive, match="budget"):
        budget.check("next-mutation")
    with budget.unit("discard", cleanup=True):
        now[0] += 20.0
    snapshot = budget.snapshot()
    assert snapshot["elapsed_conservative_seat_work_s"] == 3020.0
    assert snapshot["planning_stop"] == "next-mutation"
    assert snapshot["offline_while_holding_seat_s"] == 1.0
    assert snapshot["phases"]["discard"]["attempts"] == 1
    assert (
        json.loads(path.read_text(encoding="utf-8"))["elapsed_conservative_seat_work_s"]
        == 3020.0
    )
    with pytest.raises(dirty.Inconclusive, match="resubmission|already exists"):
        dirty.Budget(path, clock=lambda: now[0])


def test_real_saved_state_gate_failure_is_a_consumer_failure_not_qualification_success(
    monkeypatch, tmp_path
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    adapter.open_hook = lambda root: setattr(root, "saved_status", 1)
    report = verify.Report()
    evidence = asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
    assert evidence["status"] == "failed-consumer"
    assert len(adapter.roots) == 2
    for row in evidence["trajectories"]:
        assert len(row["boundaries"]) == 16
        assert row["gates"]["failed"][0][0].endswith(":saved-rebuild-clean")
        assert "NeedsRebuild2=1" in row["gates"]["failed"][0][1]
        assert len(row["gates"]["passed"]) == 5
        assert row["cleanup"]["confirmed"] is True


def test_actual_run_primary_exception_survives_secondary_cleanup_unavailability(
    monkeypatch, tmp_path
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    primary = ValueError("original open failure")

    def fail_after_open(_root):
        adapter.enumeration_error = RuntimeError(
            "secondary resident enumeration failure"
        )
        raise primary

    adapter.open_hook = fail_after_open
    with pytest.raises(ValueError) as caught:
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    assert caught.value is primary
    evidence = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert evidence["status"] == "inconclusive"
    assert evidence["errors"][0]["message"] == str(primary)
    assert evidence["cleanup"]["confirmed"] is False
    assert len(adapter.roots) == 1


def test_capture_canonicalization_preserves_raw_rows_multiplicity_and_configuration(
    monkeypatch, tmp_path
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    left = NativeContactComponent("left", "A")
    right = NativeContactComponent("right", "B")
    rows = [
        NativeInterference([left, right], 1.234567890123e-9),
        NativeInterference([right, left], 2.345678901234e-9),
        NativeInterference([left, left, right], 3.456789012345e-9),
    ]
    manager = NativeManager(rows)
    entry = {}
    capture = dirty.Capture(
        manager, RecordingBudget(), entry, component_limit=len(expected)
    )
    capture.observe_settings()
    assert capture.manager is manager
    assert capture.GetInterferences() is rows
    assert [row["ordinal"] for row in entry["rows"]] == [0, 1, 2]
    assert entry["rows"][2]["components"] == [
        ["left", "A"],
        ["left", "A"],
        ["right", "B"],
    ]
    canonical = {
        tuple(tuple(identity) for identity in row["components"]): row
        for row in entry["canonical"]
    }
    pair = canonical[(("left", "A"), ("right", "B"))]
    assert pair["multiplicity"] == 2
    assert pair["volumes_m3"] == [rows[0].volume, rows[1].volume]
    assert pair["total_m3"] == rows[0].volume + rows[1].volume
    assert len(canonical) == 2
    assert not entry["errors"]
    assert manager.compute_calls == 1
    capture.Done()


@pytest.mark.parametrize("instance_override", [False, True])
@pytest.mark.parametrize("phase", ["prepare", "remate"])
def test_scoped_helper_observation_restores_exact_attempt_attribute_state(
    instance_override, phase
):
    adapter = AttemptAdapter()
    original = adapter._attempt
    if instance_override:
        adapter._attempt = original
    before = dict(adapter.__dict__)
    row = {}
    diagnostic = dirty._Diagnostic(adapter, "B", {}, RecordingBudget(), row)
    scope = (
        diagnostic.preparing()
        if phase == "prepare"
        else diagnostic.remating("coincident:test")
    )
    primary = ValueError("leave observation scope")
    with pytest.raises(ValueError) as caught:
        with scope:
            assert adapter._attempt is not original
            raise primary
    assert caught.value is primary
    assert adapter.__dict__ == before
    if instance_override:
        assert adapter.__dict__["_attempt"] is original
    else:
        assert "_attempt" not in adapter.__dict__


def test_unpinned_helper_lambda_is_unavailable_but_original_native_call_runs_once():
    calls = []
    model = types.SimpleNamespace(EditRebuild3=lambda: calls.append("edit") or True)
    adapter = AttemptAdapter(model)
    row = {}
    diagnostic = dirty._Diagnostic(adapter, "B", {}, RecordingBudget(), row)
    with diagnostic.remating("coincident:test"):
        result = adapter._attempt(lambda: adapter.currentModel.EditRebuild3())
    assert result is True
    assert calls == ["edit"]
    assert row["remate_attempts"][0]["recognized_pinned_form"] is False
    assert any(error["type"] == "UnrecognizedHelperRebuild" for error in row["errors"])
    form = row["remate_attempts"][0]["code_form"]
    assert form["name"] == "<lambda>"
    assert form["argument_count"] == form["keyword_only_argument_count"] == 0
    assert "EditRebuild3" in form["names_repr"]
    assert "_attempt" not in adapter.__dict__


@pytest.mark.parametrize("failure", ["return", "raise", "unprintable-raise"])
def test_unavailable_callback_metadata_never_replaces_raw_result_or_primary_exception(
    failure,
):
    class UnprintableError(RuntimeError):
        def __str__(self):
            raise RuntimeError("exception text unavailable")

    primary = (
        UnprintableError()
        if failure == "unprintable-raise"
        else RuntimeError("native primary")
    )
    raw_result = object()
    calls = []

    class UnclassifiableCallback:
        @property
        def __code__(self):
            raise RuntimeError("callback metadata unavailable")

        def __call__(self):
            calls.append("original")
            if failure != "return":
                raise primary
            return raw_result

    adapter = AttemptAdapter()
    row = {}
    diagnostic = dirty._Diagnostic(adapter, "B", {}, RecordingBudget(), row)
    swallowed_default = object()
    with diagnostic.preparing():
        actual = adapter._attempt(UnclassifiableCallback(), default=swallowed_default)
    assert calls == ["original"]
    assert actual is (raw_result if failure == "return" else swallowed_default)
    assert adapter.swallowed == ([] if failure == "return" else [primary])
    assert "classification_error" in row["prepare_attempts"][0]
    assert any(
        error["phase"] == "prepare.helper_classification" for error in row["errors"]
    )
    assert "_attempt" not in adapter.__dict__


def test_hidden_input_children_outside_cad_out_are_enumerated_and_discarded(
    monkeypatch, tmp_path
):
    adapter, _expected, paths = install_native_case(monkeypatch, tmp_path)
    asyncio.run(adapter.open_model(str(adapter.path)))
    adapter.currentModel = None
    adapter.resident_docs = adapter.resident_docs[1:]
    relevant = {
        str(path.resolve()) for path in paths if path.suffix in {".SLDASM", ".SLDPRT"}
    }
    cleanup = dirty._cleanup(adapter, relevant, RecordingBudget())
    assert cleanup["confirmed"] is True
    assert len(cleanup["before"]) == len(adapter.parts)
    assert all(Path(row["path"]).is_relative_to(tmp_path) for row in cleanup["before"])
    assert cleanup["after"] == []
    assert adapter.resident_docs == []


@pytest.mark.parametrize("secondary_release_error", [False, True])
def test_acquired_manager_setting_base_exception_releases_once_and_preserves_primary(
    monkeypatch, tmp_path, secondary_release_error
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)

    class SettingsAbort(BaseException):
        pass

    primary = SettingsAbort("native setting access interrupted")

    class InterruptedManager(NativeManager):
        def __getattribute__(self, name):
            if name == "UseTransform":
                raise primary
            return super().__getattribute__(name)

    manager = InterruptedManager([])
    if secondary_release_error:
        manager.done_error = RuntimeError("secondary release unavailable")
    adapter = AttemptAdapter(
        types.SimpleNamespace(
            InterferenceDetectionManager=manager,
            ToolsCheckInterference=lambda: None,
        )
    )
    original = _assembly.configured_interference_manager
    ledger = []
    with pytest.raises(SettingsAbort) as caught:
        with dirty.scoped_capture(
            adapter, RecordingBudget(), ledger, "initial", component_limit=len(expected)
        ):
            _assembly.check_no_interference(adapter)
    assert caught.value is primary
    assert _assembly.configured_interference_manager is original
    assert manager.compute_calls == 0
    assert manager.done_calls == 1, "ownership starts when the real factory returns"
    assert len(ledger) == 1
    assert ledger[0]["errors"][0]["phase"] == "settings"
    assert ledger[0]["errors"][0]["type"] == "SettingsAbort"
    assert ledger[0]["done"][-1]["success"] is not secondary_release_error
    assert (
        any(
            error["phase"] == "secondary_scoped_release"
            for error in ledger[0]["errors"]
        )
        is secondary_release_error
    )


def test_real_sdk_mate_name_fallback_recovers_without_diagnostic_rejection(monkeypatch):
    primary = RuntimeError("direct returned-feature Name unavailable")

    class RecoveringName(Feature):
        def __init__(self):
            super().__init__(2, "recovered mate", "MateCoincident")
            self.name_reads = 0

        @property
        def Name(self):
            self.name_reads += 1
            if self.name_reads == 1:
                raise primary
            return self.name

    mate = RecoveringName()
    group = Feature(1, "Mates", "MateGroup")
    group.sub = mate
    adapter = AttemptAdapter(feature_receiver(group))
    from solidworks_mcp.adapters import sw_type_info

    monkeypatch.setattr(sw_type_info, "flag_methods", lambda *_args: 0)
    row = {}
    diagnostic = dirty._Diagnostic(adapter, "B", {}, RecordingBudget(), row)
    with diagnostic.remating("coincident:recovered-name"):
        recovered = sdk_assembly._mate_feature_name(adapter, mate)
    assert recovered == "recovered mate"
    assert mate.name_reads == 2  # Direct read failed, real MateGroup fallback won.
    assert adapter.swallowed == [primary]
    assert row["errors"] == []
    assert row["remate_attempts"] == [], "a recoverable Name read is not a rebuild"
    assert "_attempt" not in adapter.__dict__


def test_real_admission_comparison_uses_semantics_not_native_enumeration_identity(
    monkeypatch, tmp_path
):
    adapter, expected, paths = install_native_case(monkeypatch, tmp_path)
    original = asyncio.run(open_prepared_root(adapter))

    def add_equivalent_inventory(root, *, permuted):
        component = next(iter(root.components.values()))
        component.bodies = [
            NativeBody("first native body"),
            NativeBody("second native body"),
        ]
        component.body_info = [1, 1]
        component.part.feature.next = Feature(2, "native cut", "Cut")
        equations = ['"width" = 1mm', '"height" = 2mm']
        component.part.manager = Equations(equations[::-1] if permuted else equations)
        if permuted:
            component.bodies = tuple(reversed(component.bodies))
            component.body_info = (1, 1)
            for index, body in enumerate(component.bodies):
                body.name = f"new native body name {index}"
            for child in root.components.values():
                child.children = ()
                child.external_rows = ([], None, (), [], None, (), None, 0, "")
            root.extra_features.reverse()
            root.first = chain(root.extra_features)
            root.mate_features.reverse()
            root.mate_group.sub = chain(root.mate_features, sub=True)
            for feature in [*root.extra_features, *root.mate_features]:
                feature.identity += 10000
            unique_parts = {
                child.part.path: child.part for child in root.components.values()
            }
            for part in unique_parts.values():
                features = []
                feature = part.feature
                while feature is not None:
                    features.append(feature)
                    feature = feature.next
                for feature in features:
                    feature.identity += 10000
                part.feature = chain(list(reversed(features)))
        return component

    component_b = add_equivalent_inventory(original, permuted=False)
    admission_b = dirty.admit(
        adapter,
        expected,
        RecordingBudget(),
        "DRIVE_carriage_slide",
        adapter.sweep,
        checkpoint=recording_checkpoint(),
    )
    relevant = {
        str(path.resolve())
        for path in paths
        if path.suffix.lower() in {".sldasm", ".sldprt"}
    }
    assert dirty._cleanup(adapter, relevant, RecordingBudget())["confirmed"] is True
    reference = asyncio.run(open_prepared_root(adapter))
    component_a = add_equivalent_inventory(reference, permuted=True)
    admission_a = dirty.admit(
        adapter,
        expected,
        RecordingBudget(),
        "DRIVE_carriage_slide",
        adapter.sweep,
        checkpoint=recording_checkpoint(),
    )
    assert admission_b["admitted"] is admission_a["admitted"] is True
    assert original is not reference
    assert component_b is not component_a
    assert component_b.bodies[0] is not component_a.bodies[0]

    def compare(admission):
        return dirty._compare(
            {"admission": admission_b, "boundaries": [], "interferences": []},
            {"admission": admission, "boundaries": [], "interferences": []},
            RecordingBudget(),
        )

    equivalent = compare(admission_a)
    assert equivalent["admission_raw_equal"] is False
    assert equivalent["admission_equal"] is True
    assert equivalent["admission_comparison_is_geometry_digest"] is False
    assert equivalent["unclassified_differences"] == []
    assert (
        equivalent["admission_semantic_projection"]["B"]
        == equivalent["admission_semantic_projection"]["A"]
    )

    name = component_a.name
    scope = admission_a["instances"][name]["child_inventory"]
    # Mutate real admitted records, not a hand-invented comparison skeleton.
    # Raw order/identity varied above; health and dependency facts remain strict.
    for change in (
        "body-count",
        "body-type",
        "body-fault",
        "feature-type",
        "feature-edge",
        "equation-text",
        "equation-dependency",
    ):
        changed = copy.deepcopy(admission_a)
        bodies = changed["instances"][name]["configured_bodies"]
        child = changed["child_inventories"][scope]
        if change == "body-count":
            bodies["bodies"].append(copy.deepcopy(bodies["bodies"][0]))
            bodies["count"] += 1
            bodies["info_count"] += 1
        elif change == "body-type":
            bodies["bodies"][0]["type"] = 1
        elif change == "body-fault":
            bodies["bodies"][0]["fault_count"] = 1
        elif change == "feature-type":
            next(iter(child["features"]["nodes"].values()))["type"] = "Boss"
        elif change == "feature-edge":
            first, second = child["features"]["occurrences"][:2]
            second["parent"] = first["id"]
        elif change == "equation-text":
            child["equations"]["entries"][0]["text"] = '"height" = 3mm'
        else:
            child["equations"]["dependencies"]["height"] = ["width"]
        difference = compare(changed)
        assert difference["admission_raw_equal"] is False, change
        assert difference["admission_equal"] is False, change
        assert difference["unclassified_differences"] == [
            "admission inventories differ"
        ], change
    assert dirty._cleanup(adapter, relevant, RecordingBudget())["confirmed"] is True


def native_scope_representatives(root):
    """Choose fixture receivers without performing any extra native reads."""
    scopes = {}
    for component in root.components.values():
        scopes.setdefault(
            (str(component.part.path.resolve()), component.configuration), component
        )
    return list(scopes.values())


def assert_refused_prepared_start(root, row):
    assert row["admission"] is None
    assert "admission_progress" not in row
    assert row["boundaries"] == []
    assert row["counts"] == {
        "writes": 0,
        "visits": 0,
        "reads": 0,
        "suppressions": 0,
        "coincidences": 0,
    }
    assert root.writes == root.consumer_reads == []
    assert root.suppressions == root.coincidents == []
    assert root.forces == [("static", 0), ("prepare", 0)]
    assert root.edits == [("prepare", 0)]
    assert root.tools_calls == len(root.managers) == 1
    assert root.managers[0].compute_calls == root.managers[0].done_calls == 1
    assert [item["rebuild_members"] for item in row["prepare_attempts"]] == [
        ["EditRebuild3"],
        ["ForceRebuild3"],
    ]
    assert all(item["recognized_pinned_form"] for item in row["prepare_attempts"])
    assert row["cleanup"]["confirmed"] is True


def assert_precleanup_checkpoint(snapshot, variant, trajectories, boundaries):
    assert snapshot["status"] == "inconclusive"
    assert snapshot["qualification_status"] == "not-established"
    publication = snapshot["census_publication"]
    assert publication["status"] == "published"
    assert snapshot["census_checkpoint"] == publication["last_success"]
    assert snapshot["census_checkpoint"] == {
        "attempt": publication["attempts"],
        "phase": snapshot["census_checkpoint"]["phase"],
        "trajectory": variant,
        "trajectory_count": trajectories,
        "boundary_count": boundaries,
        "capture_stage": "before-consumer-cleanup",
    }
    assert len(snapshot["trajectories"]) == trajectories
    assert sum(len(row["boundaries"]) for row in snapshot["trajectories"]) == boundaries
    assert snapshot["cleanup"] is None or snapshot["cleanup"]["confirmed"] is False
    row = snapshot["trajectories"][-1]
    assert row["variant"] == variant
    assert row["admission"] is None
    assert row["admission_progress"]["admitted"] is False
    return row["admission_progress"]


def test_actual_run_aggregates_all_unknown_scopes_descendants_and_root_once(
    monkeypatch, tmp_path, caplog
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    snapshots = []
    original_write = dirty._write_json

    def record_write(path, value):
        original_write(path, value)
        if path == dirty.FAILURE_PATH:
            snapshots.append(json.loads(path.read_text(encoding="utf-8")))

    def inject(root):
        first, second, *_rest = native_scope_representatives(root)
        first.part.feature.kind = "NotesAreaFtrFolder"
        first.part.feature.sub = Feature(2, "annotation view", "AnnotationViewFeat")
        repeated = Feature(2, "annotation view", "AnnotationViewFeat")
        repeated.sub = Feature(3, "hidden sensor", "Sensor")
        first.part.feature.next = repeated
        second.part.feature.kind = "MacroFeature"
        notes = Feature(8000, "root notes", "NotesAreaFtrFolder")
        notes.sub = Feature(8001, "root descendant", "Sensor")
        root.extra_features[-1].next = notes

    adapter.open_hook = inject
    monkeypatch.setattr(dirty, "_write_json", record_write)
    report = verify.Report()
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert final["status"] == "inconclusive"
    assert final["qualification_status"] == "not-established"
    assert len(adapter.roots) == len(final["trajectories"]) == 1
    root = adapter.roots[0]
    row = final["trajectories"][0]
    assert_refused_prepared_start(root, row)
    admission = row["admission_failure"]["evidence"]
    census = admission["census"]
    assert census["authentication_status"] == census["children_status"] == "complete"
    assert (
        census["identity_seen_count"]
        == census["authenticated_instance_count"]
        == len(expected)
    )
    assert (
        census["expected_scope_count"]
        == census["discovered_scope_count"]
        == len(adapter.parts)
    )
    assert census["completed_graph_count"] == len(adapter.parts)
    assert (
        census["root_graph_status"]
        == census["root_category_scan_status"]
        == census["root_validation_status"]
        == "complete"
    )
    unknowns = census["unknown_categories"]
    assert len(unknowns) == 6
    assert len({record["scope"] for record in unknowns}) == 3
    first, second, *_rest = native_scope_representatives(root)
    scope = admission["instances"][first.name]["child_inventory"]
    second_scope = admission["instances"][second.name]["child_inventory"]
    assert unknowns == [
        {
            "scope": record_scope,
            "id": identity,
            "name": name,
            "type": kind,
            "context": context,
        }
        for record_scope, identity, name, kind, context in [
            (scope, 1, "native boss", "NotesAreaFtrFolder", "child"),
            (scope, 2, "annotation view", "AnnotationViewFeat", "child"),
            (scope, 3, "hidden sensor", "Sensor", "child"),
            (second_scope, 1, "native boss", "MacroFeature", "child"),
            ("root", 8000, "root notes", "NotesAreaFtrFolder", "root"),
            ("root", 8001, "root descendant", "Sensor", "root"),
        ]
    ]
    graph = admission["child_inventories"][scope]["features"]
    assert [edge["id"] for edge in graph["occurrences"]] == [1, 2, 2, 3]
    assert [edge["parent"] for edge in graph["occurrences"]] == [None, 1, None, 2]
    assert graph["terminations"]
    root_edge = next(
        edge for edge in admission["root_features"]["occurrences"] if edge["id"] == 8001
    )
    assert root_edge["parent"] == 8000
    for child in admission["child_inventories"].values():
        assert (
            child["graph_status"]
            == child["category_scan_status"]
            == child["validation_status"]
            == "complete"
        )
    assert root.first_feature_calls == root.manager_reads == 1
    assert sum(
        component.first_feature_calls for component in root.components.values()
    ) == len(adapter.parts)
    assert all(component.body_calls == [-1] for component in root.components.values())
    assert all(
        component.external_calls == ["count", "list"]
        for component in root.components.values()
    )
    assert all(
        component.part.manager_reads == 1 for component in root.components.values()
    )
    assert len(snapshots) == len(adapter.parts) + 3
    assert [snapshot["census_checkpoint"]["phase"] for snapshot in snapshots] == (
        ["child-graph-scanned"] * len(adapter.parts)
        + ["children-complete", "root-graph-scanned", "admission-aborted"]
    )
    early = assert_precleanup_checkpoint(snapshots[-1], "B", 1, 0)
    assert early["census"]["unknown_categories"] == unknowns
    assert json.loads(dirty.FAILURE_PATH.read_text(encoding="utf-8")) == snapshots[-1]
    assert final["cleanup"]["confirmed"] is True
    assert report.failed
    assert "NotesAreaFtrFolder" in row["admission_failure"]["error"]["message"]
    assert (
        len(
            [
                record
                for record in caplog.records
                if record.message.startswith("dirty-Edit diagnostic rejected [")
            ]
        )
        == 1
    )


@pytest.mark.parametrize("fault", ["unknown", "native"])
def test_actual_run_a_only_refusal_retains_completed_b_and_real_progress(
    monkeypatch, tmp_path, fault
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    early = []

    def inject(root):
        if root.generation == 1:
            first = native_scope_representatives(root)[0]
            if fault == "unknown":
                first.part.feature.kind = "AnnotationViewFeat"
            else:
                first.part.feature.error = RuntimeError("A native next unavailable")

    def before_close(root):
        if root.generation == 1:
            assert adapter.currentModel is root
            assert root in adapter.resident_docs
            early.append(dirty.FAILURE_PATH.read_bytes())

    adapter.open_hook = inject
    adapter.before_close_hook = before_close
    report = verify.Report()
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert final["status"] == "inconclusive"
    assert final["qualification_status"] == "not-established"
    assert [row["variant"] for row in final["trajectories"]] == ["B", "A"]
    b, a = final["trajectories"]
    b_root, a_root = adapter.roots
    assert b["admission"]["admitted"] is True
    assert b["complete"] is True
    assert [item["key"] for item in b["boundaries"]] == EXPECTED_KEYS
    assert b["counts"] == {
        "writes": 15,
        "visits": 14,
        "reads": 28,
        "suppressions": 2,
        "coincidences": 2,
    }
    assert len(b_root.writes) == 15
    assert len(b_root.consumer_reads) == 28
    assert b_root.tools_calls == len(b_root.managers) == 11
    assert all(
        manager.compute_calls == manager.done_calls == 1 for manager in b_root.managers
    )
    assert b_root.forces == [("static", 0), ("prepare", 0)]
    assert len(b_root.edits) == 19
    assert len(b["prepare_attempts"]) == len(b["remate_attempts"]) == 2
    assert all(
        item["recognized_pinned_form"]
        for item in b["prepare_attempts"] + b["remate_attempts"]
    )
    assert b["gates"] == {
        "passed": [f"{verify.SWEEP_OWNER}:{suffix}" for suffix in GATE_SUFFIXES],
        "failed": [],
    }
    assert b["cleanup"]["confirmed"] is True
    assert_refused_prepared_start(a_root, a)
    assert len(early) == 1
    checkpoint = json.loads(early[0])
    admission = assert_precleanup_checkpoint(checkpoint, "A", 2, 16)
    assert checkpoint["trajectories"][0]["counts"] == b["counts"]
    assert checkpoint["trajectories"][0]["boundaries"] == b["boundaries"]
    assert admission["admitted"] is False
    assert dirty.FAILURE_PATH.read_bytes() == early[0]
    assert final["cleanup"]["confirmed"] is True
    assert adapter.currentModel is None and adapter.resident_docs == []
    assert report.failed
    if fault == "native":
        assert "A native next unavailable" in a["admission_failure"]["error"]["message"]
        assert a_root.first_feature_calls == 0
        assert (
            sum(
                component.first_feature_calls
                for component in a_root.components.values()
            )
            == 1
        )
    else:
        assert len(admission["census"]["unknown_categories"]) == 1
        assert admission["census"]["authenticated_instance_count"] == len(expected)


@pytest.mark.parametrize(
    ("fault", "reason", "inserted", "identity_obtained"),
    [
        ("identity", "unexpected root component", False, True),
        ("path", "resolved file differs", False, True),
        ("configuration", "active child configuration", True, True),
        ("suppressed", "unresolved/suppressed/error", False, False),
        ("nested", "nested/malformed child", True, True),
        ("model-path", "component/model document path", True, True),
        ("body", "solid", True, True),
        ("external", "external references", True, True),
        ("equation", "equation", True, True),
    ],
)
def test_actual_run_later_unsafe_input_stops_before_any_later_scope(
    monkeypatch, tmp_path, fault, reason, inserted, identity_obtained
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    selected = {}

    def inject(root):
        first, target, later, *_rest = native_scope_representatives(root)
        first.part.feature.kind = "NotesAreaFtrFolder"
        selected.update(first=first, target=target, later=later)
        selected["target_name"] = target.name
        selected["before"] = list(root.components.values()).index(target)
        if fault == "identity":
            target.name = "foreign-identity"
        elif fault == "path":
            target.GetPathName = lambda: str(first.part.path)
        elif fault == "configuration":
            target.configuration = "unseen-config"
        elif fault == "suppressed":
            target.suppression = 0
        elif fault == "nested":
            target.children = [object()]
        elif fault == "model-path":
            target.part.GetPathName = lambda: str(first.part.path)
        elif fault == "body":
            target.body.kind = 1
        elif fault == "external":
            target.external_count = 1
        else:
            target.part.manager = Equations(['"width" = unsupported(1)'])

    adapter.open_hook = inject
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert len(adapter.roots) == 1
    row = final["trajectories"][0]
    assert_refused_prepared_start(adapter.roots[0], row)
    failure = row["admission_failure"]
    assert reason in failure["error"]["message"]
    admission = failure["evidence"]
    census = admission["census"]
    before = selected["before"]
    authenticated = before + (fault == "equation")
    assert census["identity_seen_count"] == before + identity_obtained
    assert census["authenticated_instance_count"] == authenticated
    assert len(admission["instances"]) == before + inserted
    assert (selected["target_name"] in admission["instances"]) is inserted
    assert census["authentication_status"] == census["children_status"] == "incomplete"
    assert census["expected_scope_count"] is None
    assert census["discovered_scope_count"] == (2 if fault == "equation" else 1)
    assert census["completed_graph_count"] == (2 if fault == "equation" else 1)
    assert len(census["unknown_categories"]) == 1
    assert selected["later"].body_calls == []
    assert selected["later"].external_calls == []
    assert selected["later"].part.first_feature_calls == 0
    assert selected["later"].part.manager_reads == 0
    assert adapter.roots[0].first_feature_calls == 0
    if fault == "equation":
        scope = admission["instances"][selected["target_name"]]["child_inventory"]
        child = admission["child_inventories"][scope]
        assert child["graph_status"] == child["category_scan_status"] == "complete"
        assert child["validation_status"] == "incomplete"
    else:
        assert selected["target"].first_feature_calls == 0
    assert final["census_publication"]["status"] == "published"
    assert final["cleanup"]["confirmed"] is True


@pytest.mark.parametrize(
    "fault", ["native", "malformed", "cycle", "depth", "global-cap"]
)
def test_actual_run_partial_walker_keeps_scoped_raw_graph_and_global_limits(
    monkeypatch, tmp_path, fault
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    selected = {}

    def inject(root):
        first, target, later, *_rest = native_scope_representatives(root)
        selected.update(first=first, target=target, later=later)
        first.part.feature.kind = "NotesAreaFtrFolder"
        if fault == "global-cap":
            first.part.feature = chain(
                [Feature(index, f"earlier {index}", "Boss") for index in range(2500)]
            )
            first.part.feature.kind = "NotesAreaFtrFolder"
            target.part.feature = chain(
                [Feature(index, f"later {index}", "Boss") for index in range(2500)]
            )
        elif fault == "native":
            target.part.feature.error = RuntimeError("later native next unavailable")
        elif fault == "malformed":
            target.part.feature.next = Feature(None, "unresolved identity", "Boss")
        elif fault == "cycle":
            target.part.feature.next = target.part.feature
        else:
            current = target.part.feature
            for index in range(2, 35):
                current.sub = Feature(index, f"deep {index}", "Boss")
                current = current.sub

    adapter.open_hook = inject
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    row = final["trajectories"][0]
    assert_refused_prepared_start(adapter.roots[0], row)
    admission = row["admission_failure"]["evidence"]
    census = admission["census"]
    first, target, later = (selected[key] for key in ("first", "target", "later"))
    earlier_scope = admission["instances"][first.name]["child_inventory"]
    scope = admission["instances"][target.name]["child_inventory"]
    earlier = admission["child_inventories"][earlier_scope]
    child = admission["child_inventories"][scope]
    assert (
        earlier["graph_status"]
        == earlier["category_scan_status"]
        == earlier["validation_status"]
        == "complete"
    )
    assert (
        child["graph_status"]
        == child["category_scan_status"]
        == child["validation_status"]
        == "incomplete"
    )
    assert "features" not in child
    partial = admission["failed_step_evidence"]
    assert partial["scope"] == scope
    assert census["failed_scope"] == {
        "scope": scope,
        "path": str(target.part.path.resolve()),
        "configuration": target.configuration,
        "instance": target.name,
        "graph_status": "incomplete",
        "category_scan_status": "incomplete",
        "validation_status": "incomplete",
    }
    assert census["completed_graph_count"] == 1
    assert census["expected_scope_count"] is None
    assert census["discovered_scope_count"] == 2
    assert target.first_feature_calls == target.part.first_feature_calls == 1
    assert target.part.manager_reads == 0
    assert later.part.first_feature_calls == 0
    assert later.body_calls == []
    assert adapter.roots[0].first_feature_calls == 0
    if fault == "global-cap":
        assert len(earlier["features"]["occurrences"]) == 2500
        assert len(partial["occurrences"]) == 2499
        assert admission["feature_occurrences"] == 5000
        assert target.part.feature.calls.count("GetID") == 1
        assert (
            "global feature occurrence cap"
            in row["admission_failure"]["error"]["message"]
        )
    elif fault == "depth":
        assert len(partial["occurrences"]) == 32
        assert max(edge["depth"] for edge in partial["occurrences"]) == 31
        assert "depth cap" in row["admission_failure"]["error"]["message"]
    else:
        assert len(partial["nodes"]) == len(partial["occurrences"]) == 1
        assert partial["nodes"]["1"]["name"] == target.part.feature.name
    assert final["cleanup"]["confirmed"] is True


def test_actual_run_budget_stop_during_plain_scan_does_not_erase_completed_graph(
    monkeypatch, tmp_path
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    original_budget = dirty.Budget
    primary = dirty.Inconclusive("native planning budget exhausted mid plain scan")
    selected = {}

    class ScanStopBudget(original_budget):
        def __init__(self, path):
            self.category_checks = 0
            super().__init__(path, clock=lambda: 100.0)

        def check(self, label, cleanup=False):
            if label == "admission.child_category":
                self.category_checks += 1
                if self.category_checks == 3:
                    self.stopped = label
                    raise primary
            return super().check(label, cleanup=cleanup)

    def inject(root):
        first, target, later, *_rest = native_scope_representatives(root)
        first.part.feature.kind = "NotesAreaFtrFolder"
        target.part.feature.next = Feature(2, "second category", "Sensor")
        target.part.feature.next.next = Feature(3, "third category", "MacroFeature")
        selected.update(target=target, later=later)

    monkeypatch.setattr(dirty, "Budget", ScanStopBudget)
    adapter.open_hook = inject
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    failure = final["trajectories"][0]["admission_failure"]
    assert failure["error"]["message"] == str(primary)
    admission = failure["evidence"]
    census = admission["census"]
    target = selected["target"]
    scope = admission["instances"][target.name]["child_inventory"]
    child = admission["child_inventories"][scope]
    assert child["graph_status"] == "complete"
    assert child["category_scan_status"] == child["validation_status"] == "incomplete"
    assert child["category_records_scanned"] == 1
    assert len(child["features"]["nodes"]) == 3
    assert census["failed_scope"]["scope"] == scope
    assert census["failed_scope"]["graph_status"] == "complete"
    assert census["failed_scope"]["category_scan_status"] == "incomplete"
    assert census["completed_graph_count"] == 2
    assert census["children_status"] == "incomplete"
    assert census["expected_scope_count"] is None
    assert target.part.manager_reads == 0
    assert selected["later"].part.first_feature_calls == 0
    assert adapter.roots[0].first_feature_calls == 0
    assert final["cleanup"]["confirmed"] is True


def test_actual_run_last_alias_checkpoint_finishes_children_before_first_root_interrupt(
    monkeypatch, tmp_path
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    child_bytes = []
    primary = RuntimeError("first root native read interrupted")

    def inject(root):
        first = native_scope_representatives(root)[0]
        first.part.feature.kind = "NotesAreaFtrFolder"
        ordered = list(root.components.values())
        last = next(
            component
            for index, component in enumerate(ordered)
            if any(prior.part is component.part for prior in ordered[:index])
        )
        root.components.pop(last.name)
        root.components[last.name] = last
        original_first = root.FirstFeature

        def interrupt_first_root():
            payload = dirty.FAILURE_PATH.read_bytes()
            snapshot = json.loads(payload)
            admission = assert_precleanup_checkpoint(snapshot, "B", 1, 0)
            assert snapshot["census_checkpoint"]["phase"] == "children-complete"
            census = admission["census"]
            assert (
                census["authentication_status"]
                == census["children_status"]
                == "complete"
            )
            assert census["authenticated_instance_count"] == len(expected)
            assert (
                census["expected_scope_count"]
                == census["completed_graph_count"]
                == len(adapter.parts)
            )
            assert census["root_graph_status"] == "collecting"
            assert last.body_calls == [-1]
            assert last.first_feature_calls == 0
            child_bytes.append(payload)
            original_first()
            raise primary

        root.FirstFeature = interrupt_first_root

    adapter.open_hook = inject
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    assert len(child_bytes) == 1
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    failure = final["trajectories"][0]["admission_failure"]
    assert str(primary) in failure["error"]["message"]
    census = failure["evidence"]["census"]
    assert census["children_status"] == "complete"
    assert census["expected_scope_count"] == len(adapter.parts)
    assert census["root_graph_status"] == "incomplete"
    assert census["failed_scope"] == {
        "scope": "root",
        "graph_status": "incomplete",
        "category_scan_status": "incomplete",
        "validation_status": "incomplete",
    }
    assert failure["evidence"]["failed_step_evidence"]["scope"] == "root"
    assert adapter.roots[0].first_feature_calls == 1


@pytest.mark.parametrize("fault", ["missing-reference", "unsafe-root-equation"])
def test_actual_run_root_validation_stays_hard_after_complete_unknown_category_scan(
    monkeypatch, tmp_path, fault
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)

    def inject(root):
        root.extra_features[-1].next = Feature(8000, "root notes", "AnnotationViewFeat")
        if fault == "missing-reference":
            removed = next(
                feature
                for feature in root.extra_features
                if feature.kind == "Reference"
            )
            root.first = chain(
                [feature for feature in root.extra_features if feature is not removed]
            )
            root.extra_features[-1].next = Feature(
                8000, "root notes", "AnnotationViewFeat"
            )
        else:
            root.manager = Equations(['"unsafe" = unsupported(1)'])

    adapter.open_hook = inject
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    row = final["trajectories"][0]
    assert_refused_prepared_start(adapter.roots[0], row)
    admission = row["admission_failure"]["evidence"]
    census = admission["census"]
    assert census["authenticated_instance_count"] == len(expected)
    assert census["children_status"] == "complete"
    assert (
        census["root_graph_status"] == census["root_category_scan_status"] == "complete"
    )
    assert census["root_validation_status"] == "incomplete"
    assert census["root_category_records_scanned"] == len(
        admission["root_features"]["nodes"]
    )
    assert len(census["unknown_categories"]) == 1
    assert "unknown" not in row["admission_failure"]["error"]["message"]
    assert adapter.roots[0].first_feature_calls == 1


def test_actual_run_cancellation_persists_partial_graph_before_first_original_close(
    monkeypatch, tmp_path
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)

    class NativeAbort(BaseException):
        pass

    primary = NativeAbort("native enumeration cancelled")
    selected = {}
    early = []
    writes = []
    original_write = dirty._write_json
    original_close = type(adapter.swApp).CloseDoc

    def inject(root):
        first, target, later, *_rest = native_scope_representatives(root)
        target.part.feature.error = primary
        selected.update(first=first, target=target, later=later)

    def before_close(root):
        assert type(adapter.swApp).CloseDoc is original_close
        assert adapter.currentModel is root
        assert root in adapter.resident_docs
        assert selected["target"].part in adapter.resident_docs
        assert ("close", root.generation) not in adapter.events
        payload = dirty.FAILURE_PATH.read_bytes()
        snapshot = json.loads(payload)
        admission = assert_precleanup_checkpoint(snapshot, "B", 1, 0)
        first_scope = admission["instances"][selected["first"].name]["child_inventory"]
        target_scope = admission["instances"][selected["target"].name][
            "child_inventory"
        ]
        assert (
            admission["child_inventories"][first_scope]["validation_status"]
            == "complete"
        )
        assert (
            admission["child_inventories"][target_scope]["graph_status"] == "incomplete"
        )
        assert admission["failed_step_evidence"]["scope"] == target_scope
        assert len(admission["failed_step_evidence"]["occurrences"]) == 1
        assert admission["census"]["completed_graph_count"] == 1
        assert admission["census"]["failed_scope"]["scope"] == target_scope
        assert admission["census"]["stopped"]["type"] == "NativeAbort"
        assert selected["later"].part.first_feature_calls == 0
        early.append(payload)

    def prevent_final_report(path, value):
        writes.append(path)
        if path == dirty.REPORT_PATH:
            raise OSError("final REPORT deliberately unavailable")
        return original_write(path, value)

    adapter.open_hook = inject
    adapter.before_close_hook = before_close
    monkeypatch.setattr(dirty, "_write_json", prevent_final_report)
    report = verify.Report()
    with pytest.raises(NativeAbort) as caught:
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
    assert caught.value is primary
    assert len(early) == 1
    assert writes.count(dirty.FAILURE_PATH) == writes.count(dirty.REPORT_PATH) == 1
    assert dirty.FAILURE_PATH.read_bytes() == early[0]
    assert not dirty.REPORT_PATH.exists()
    assert adapter.currentModel is None and adapter.resident_docs == []
    assert adapter.events.count(("close", 0)) == 1
    assert report.failed
    assert primary.evidence["census"]["stopped"]["type"] == "NativeAbort"


@pytest.mark.parametrize(
    ("failure_number", "failure_kind", "stale"),
    [
        (1, "io", False),
        (1, "size", False),
        (1, "io", True),
        (1, "size", True),
        (2, "io", False),
        (2, "size", False),
    ],
)
def test_actual_run_checkpoint_writer_failure_is_terminal_and_preserves_last_bytes(
    monkeypatch, tmp_path, failure_number, failure_kind, stale
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    previous = b"stale prior-run failure; not a current checkpoint\r\n"
    if stale:
        dirty.FAILURE_PATH.write_bytes(previous)
    initial_files = set(tmp_path.iterdir())
    selected = {}
    failure_attempts = []
    report_attempts = []
    last_good = []
    original_write = dirty._write_json
    original_replace = Path.replace

    def inject(root):
        first, target, later, *_rest = native_scope_representatives(root)
        first.part.feature.kind = "NotesAreaFtrFolder"
        selected.update(first=first, target=target, later=later)

    def fail_replace(path, target):
        if path == dirty.FAILURE_PATH.with_suffix(".json.tmp"):
            raise OSError("checkpoint atomic replacement denied")
        return original_replace(path, target)

    def fail_one_checkpoint(path, value):
        if path == dirty.REPORT_PATH:
            report_attempts.append(copy.deepcopy(value))
        if path != dirty.FAILURE_PATH:
            return original_write(path, value)
        failure_attempts.append(copy.deepcopy(value))
        if len(failure_attempts) == failure_number:
            with monkeypatch.context() as limited:
                if failure_kind == "size":
                    # Exercise the unchanged real serialization/size rejection,
                    # scaled to a tiny bound rather than allocating 64 MiB.
                    limited.setattr(dirty, "_MAX_REPORT_BYTES", 1)
                else:
                    limited.setattr(Path, "replace", fail_replace)
                return original_write(path, value)
        original_write(path, value)
        last_good.append(path.read_bytes())

    adapter.open_hook = inject
    monkeypatch.setattr(dirty, "_write_json", fail_one_checkpoint)
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    assert len(failure_attempts) == failure_number
    assert len(report_attempts) == 1
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    publication = final["census_publication"]
    assert publication["status"] == "unavailable"
    assert publication["attempts"] == failure_number
    assert len(publication["errors"]) == 1
    message = publication["errors"][0]["message"]
    assert (
        "64 MiB" if failure_kind == "size" else "atomic replacement denied"
    ) in message
    assert final["status"] == "inconclusive"
    row = final["trajectories"][0]
    assert_refused_prepared_start(adapter.roots[0], row)
    assert message in json.dumps(row["admission_failure"])
    assert selected["first"].part.first_feature_calls == 1
    assert selected["target"].part.first_feature_calls == (failure_number == 2)
    stopped_part = selected["first" if failure_number == 1 else "target"].part
    assert stopped_part.manager_reads == 0
    assert selected["later"].body_calls == []
    assert selected["later"].part.first_feature_calls == 0
    assert adapter.roots[0].first_feature_calls == 0
    assert len(adapter.roots) == 1
    if failure_number == 2:
        assert len(last_good) == 1
        assert dirty.FAILURE_PATH.read_bytes() == last_good[0]
        checkpoint = json.loads(last_good[0])
        assert_precleanup_checkpoint(checkpoint, "B", 1, 0)
        assert checkpoint["census_checkpoint"]["attempt"] == 1
        assert publication["last_success"] == checkpoint["census_checkpoint"]
    else:
        assert last_good == []
        assert publication["last_success"] is None
        if stale:
            assert dirty.FAILURE_PATH.read_bytes() == previous
        else:
            assert not dirty.FAILURE_PATH.exists()
    added = set(tmp_path.iterdir()) - initial_files
    assert added <= {
        dirty.BUDGET_PATH,
        dirty.REPORT_PATH,
        dirty.FAILURE_PATH,
        dirty.FAILURE_PATH.with_suffix(".json.tmp"),
    }, "no alternate receipt, spill, manifest or fallback artifact is permitted"
    assert not dirty.REPORT_PATH.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("earlier_checkpoint", [False, True])
def test_actual_run_native_cancellation_survives_failing_checkpoint_sink(
    monkeypatch, tmp_path, earlier_checkpoint
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)

    class NativeAbort(BaseException):
        pass

    primary = NativeAbort("original native cancellation")
    attempts = []
    last_good = []
    report_attempts = []
    original_write = dirty._write_json

    def inject(root):
        first, target, *_rest = native_scope_representatives(root)
        if earlier_checkpoint:
            first.part.feature.kind = "NotesAreaFtrFolder"
        target.part.feature.error = primary

    def fail_abort_checkpoint(path, value):
        if path == dirty.REPORT_PATH:
            report_attempts.append(copy.deepcopy(value))
        if path == dirty.FAILURE_PATH:
            attempts.append(copy.deepcopy(value))
            if value["census_checkpoint"]["phase"] == "admission-aborted":
                raise OSError("secondary checkpoint sink unavailable")
            original_write(path, value)
            last_good.append(path.read_bytes())
            return
        return original_write(path, value)

    adapter.open_hook = inject
    monkeypatch.setattr(dirty, "_write_json", fail_abort_checkpoint)
    with pytest.raises(NativeAbort) as caught:
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    assert caught.value is primary
    assert len(attempts) == 1 + earlier_checkpoint
    assert len(report_attempts) == 1
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    publication = final["census_publication"]
    assert publication["status"] == "unavailable"
    assert publication["attempts"] == 1 + earlier_checkpoint
    assert "secondary checkpoint sink unavailable" in json.dumps(publication["errors"])
    failure = final["trajectories"][0]["admission_failure"]
    assert failure["error"]["type"] == "NativeAbort"
    assert failure["error"]["message"] == str(primary)
    assert failure["evidence"]["census"]["stopped"]["message"] == str(primary)
    assert "secondary checkpoint sink unavailable" in json.dumps(
        failure["evidence"]["census"]["persistence_errors"]
    )
    assert final["errors"][0]["type"] == "NativeAbort"
    assert adapter.currentModel is None and adapter.resident_docs == []
    if earlier_checkpoint:
        assert len(last_good) == 1
        assert dirty.FAILURE_PATH.read_bytes() == last_good[0]
    else:
        assert last_good == []
        assert not dirty.FAILURE_PATH.exists()


@pytest.mark.parametrize("earlier_checkpoint", [False, True])
@pytest.mark.parametrize(
    "permission", ["reserve", "exhausted", "nonfinite", "snapshot-error"]
)
def test_actual_run_budget_stop_uses_one_existing_allowance_snapshot_without_retry(
    monkeypatch, tmp_path, permission, earlier_checkpoint
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    original_budget = dirty.Budget
    original_write = dirty._write_json
    primary = dirty.Inconclusive("native planning budget exhausted before held scan")
    now = [17.0]
    budgets = []
    failure_bytes = []
    writes_after_stop = []
    report_attempts = []
    selected = {}

    class ExistingAllowanceBudget(original_budget):
        def __init__(self, path):
            self.saving = False
            self.category_checks = 0
            self.permission_snapshots = 0
            self.ordinary_after_stop = []
            super().__init__(path, clock=lambda: now[0])
            budgets.append(self)

        def save(self):
            self.saving = True
            try:
                return super().save()
            finally:
                self.saving = False

        def snapshot(self):
            snapshot = super().snapshot()
            if self.stopped and not self.saving and adapter.currentModel is not None:
                self.permission_snapshots += 1
                if permission == "snapshot-error":
                    raise RuntimeError("existing allowance snapshot unavailable")
                if permission == "nonfinite":
                    snapshot["elapsed_conservative_seat_work_s"] = float("nan")
            return snapshot

        def check(self, label, cleanup=False):
            if self.stopped and not cleanup:
                self.ordinary_after_stop.append(label)
                raise primary
            if label == "admission.child_category":
                self.category_checks += 1
                if self.category_checks == 2:
                    now[0] += 3600.0 if permission == "exhausted" else 3001.0
                    self.stopped = label
                    raise primary
            return super().check(label, cleanup=cleanup)

    def inject(root):
        first, target, later, *_rest = native_scope_representatives(root)
        if earlier_checkpoint:
            first.part.feature.kind = "NotesAreaFtrFolder"
        selected.update(target=target, later=later)

    def record_write(path, value):
        if path == dirty.REPORT_PATH:
            report_attempts.append(path)
        if path == dirty.FAILURE_PATH and budgets[0].stopped:
            writes_after_stop.append(path)
        original_write(path, value)
        if path == dirty.FAILURE_PATH:
            failure_bytes.append(path.read_bytes())

    adapter.open_hook = inject
    monkeypatch.setattr(dirty, "Budget", ExistingAllowanceBudget)
    monkeypatch.setattr(dirty, "_write_json", record_write)
    with pytest.raises(dirty.Inconclusive):
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, verify.Report()))
    assert len(budgets) == 1
    budget = budgets[0]
    permitted = permission == "reserve"
    assert budget.permission_snapshots == 1
    denied_gate = "original.gate:pass-sweep-interference-free"
    assert budget.ordinary_after_stop == [denied_gate]
    assert denied_gate not in budget.phases
    assert budget.started == 17.0
    assert now[0] == 17.0 + (3600.0 if permission == "exhausted" else 3001.0)
    assert budget.stopped == "admission.child_category"
    assert len(writes_after_stop) == int(permitted)
    expected_attempts = int(earlier_checkpoint) + int(permitted)
    assert len(failure_bytes) == expected_attempts
    assert len(report_attempts) == 1
    if failure_bytes:
        assert dirty.FAILURE_PATH.read_bytes() == failure_bytes[-1]
    else:
        assert not dirty.FAILURE_PATH.exists()
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert len(adapter.roots) == len(final["trajectories"]) == 1
    row = final["trajectories"][0]
    assert_refused_prepared_start(adapter.roots[0], row)
    assert row["gates"] == {
        "passed": [f"{verify.SWEEP_OWNER}:{suffix}" for suffix in GATE_SUFFIXES[:-1]],
        "failed": [],
    }
    publication = final["census_publication"]
    assert publication["status"] == ("published" if permitted else "unavailable")
    assert publication["attempts"] == expected_attempts
    failure = final["trajectories"][0]["admission_failure"]
    assert failure["error"]["message"] == str(primary)
    assert failure["evidence"]["census"]["stopped"]["message"] == str(primary)
    assert selected["target"].part.first_feature_calls == 1
    assert selected["target"].part.manager_reads == 0
    assert selected["later"].body_calls == []
    assert selected["later"].part.first_feature_calls == 0
    assert adapter.roots[0].first_feature_calls == 0
    assert final["cleanup"]["confirmed"] is True
    assert final["budget"]["submission"] == 1
    assert final["budget"]["elapsed_conservative_seat_work_s"] == now[0] - 17.0
    if permitted:
        checkpoint = json.loads(failure_bytes[-1])
        assert_precleanup_checkpoint(checkpoint, "B", 1, 0)
        assert checkpoint["census_checkpoint"]["phase"] == "admission-aborted"
        assert checkpoint["census_publication"]["attempts"] == expected_attempts
    elif earlier_checkpoint:
        assert (
            publication["last_success"]
            == json.loads(failure_bytes[0])["census_checkpoint"]
        )
    else:
        assert publication["last_success"] is None


@pytest.mark.parametrize("interruption", ["ordinary", "cancellation"])
def test_actual_run_last_authenticated_scope_equation_interrupt_keeps_complete_child_census(
    monkeypatch, tmp_path, interruption
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)

    class EquationAbort(BaseException):
        pass

    primary = (
        EquationAbort("last configured equation cancelled")
        if interruption == "cancellation"
        else RuntimeError("last configured equation unavailable")
    )
    selected = {}

    def inject(root):
        ordered = list(root.components.values())
        last = next(
            component
            for index, component in enumerate(ordered)
            if any(prior.part is component.part for prior in ordered[:index])
        )
        root.components.pop(last.name)
        root.components[last.name] = last
        configured = NativePart(last.part.path)
        configured.ConfigurationManager.ActiveConfiguration.Name = "LastConfigured"
        configured.manager = Equations(['"width" = 1mm', '"height" = 2mm'])
        original_equation = configured.manager.Equation

        def interrupt_second_row(index):
            if index == 1:
                configured.manager.reads.append(("Equation", index))
                raise primary
            return original_equation(index)

        configured.manager.Equation = interrupt_second_row
        last.part = configured
        last.configuration = "LastConfigured"
        selected.update(last=last, configured=configured)

    adapter.open_hook = inject
    report = verify.Report()
    if interruption == "cancellation":
        with pytest.raises(EquationAbort) as caught:
            asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
        assert caught.value is primary
    else:
        with pytest.raises(dirty.Inconclusive):
            asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    row = final["trajectories"][0]
    assert_refused_prepared_start(adapter.roots[0], row)
    admission = row["admission_failure"]["evidence"]
    census = admission["census"]
    assert (
        census["identity_seen_count"]
        == census["authenticated_instance_count"]
        == len(expected)
    )
    assert census["authentication_status"] == census["children_status"] == "complete"
    assert (
        census["expected_scope_count"]
        == census["discovered_scope_count"]
        == len(adapter.parts) + 1
    )
    assert census["completed_graph_count"] == len(adapter.parts) + 1
    last = selected["last"]
    scope = admission["instances"][last.name]["child_inventory"]
    child = admission["child_inventories"][scope]
    assert child["graph_status"] == child["category_scan_status"] == "complete"
    assert child["validation_status"] == "incomplete"
    assert census["failed_scope"] == {
        "scope": scope,
        "path": str(last.part.path.resolve()),
        "configuration": "LastConfigured",
        "instance": last.name,
        "graph_status": "complete",
        "category_scan_status": "complete",
        "validation_status": "incomplete",
    }
    partial = admission["failed_step_evidence"]
    assert partial["configuration"] == "LastConfigured"
    assert partial["count"] == 2
    assert partial["entries"] == [
        {
            "index": 0,
            "text": '"width" = 1mm',
            "global": True,
            "lhs": "width",
            "references": [],
        }
    ]
    assert selected["configured"].manager.reads == [
        ("GetCount",),
        ("Equation", 0),
        ("GlobalVariable", 0),
        ("Equation", 1),
    ]
    assert selected["configured"].first_feature_calls == 1
    assert adapter.roots[0].first_feature_calls == 0
    assert str(primary) in row["admission_failure"]["error"]["message"]
    checkpoint = json.loads(dirty.FAILURE_PATH.read_text(encoding="utf-8"))
    held = assert_precleanup_checkpoint(checkpoint, "B", 1, 0)
    assert held["census"]["children_status"] == "complete"
    assert held["failed_step_evidence"] == partial
    assert report.failed


@pytest.mark.parametrize("earlier_checkpoint", [False, True])
def test_actual_run_cancellation_survives_snapshot_failure_persisting_through_finalization(
    monkeypatch, tmp_path, earlier_checkpoint
):
    adapter, _expected, _paths = install_native_case(monkeypatch, tmp_path)
    original_budget = dirty.Budget
    original_write = dirty._write_json
    budgets = []
    selected = {}
    writes = []
    last_good = []
    close_observations = []

    class NativeAbort(BaseException):
        pass

    primary = NativeAbort("native graph cancelled before persistent snapshot failure")
    snapshot_error = RuntimeError("all subsequent budget snapshots unavailable")

    class PersistentSnapshotBudget(original_budget):
        def __init__(self, path):
            self.saving = False
            self.snapshots_unavailable = False
            self.failed_direct_snapshots = []
            super().__init__(path, clock=lambda: 100.0)
            budgets.append(self)

        def save(self):
            self.saving = True
            try:
                return super().save()
            finally:
                self.saving = False

        def snapshot(self):
            if self.snapshots_unavailable:
                if not self.saving:
                    self.failed_direct_snapshots.append(adapter.currentModel is None)
                raise snapshot_error
            return super().snapshot()

    def inject(root):
        first, target, later, *_rest = native_scope_representatives(root)
        if earlier_checkpoint:
            first.part.feature.kind = "NotesAreaFtrFolder"
        original_next = target.part.feature.GetNextFeature

        def cancel_after_native_next():
            original_next()
            budgets[0].snapshots_unavailable = True
            raise primary

        target.part.feature.GetNextFeature = cancel_after_native_next
        selected.update(first=first, target=target, later=later)

    def before_close(root):
        assert adapter.currentModel is root
        assert root in adapter.resident_docs
        assert budgets[0].snapshots_unavailable is True
        if earlier_checkpoint:
            assert dirty.FAILURE_PATH.read_bytes() == last_good[0]
        else:
            assert not dirty.FAILURE_PATH.exists()
        close_observations.append(root.generation)

    def record_write(path, value):
        writes.append(path)
        if path == dirty.FAILURE_PATH:
            assert budgets[0].snapshots_unavailable is False
        original_write(path, value)
        if path == dirty.FAILURE_PATH:
            last_good.append(path.read_bytes())

    adapter.open_hook = inject
    adapter.before_close_hook = before_close
    monkeypatch.setattr(dirty, "Budget", PersistentSnapshotBudget)
    monkeypatch.setattr(dirty, "_write_json", record_write)
    report = verify.Report()
    with pytest.raises(NativeAbort) as caught:
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
    assert caught.value is primary
    assert len(budgets) == 1
    budget = budgets[0]
    assert budget.snapshots_unavailable is True
    # One denied publication snapshot while resident, then exactly one final
    # direct snapshot after discard. Persisting saves also fail, never recover.
    assert budget.failed_direct_snapshots == [False, True]
    assert budget.clock() == budget.started == 100.0
    assert budget.persistence_errors
    assert all(
        error["message"] == str(snapshot_error) for error in budget.persistence_errors
    )
    assert writes.count(dirty.REPORT_PATH) == 1
    assert writes.count(dirty.FAILURE_PATH) == int(earlier_checkpoint)
    assert close_observations == [0]
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert final["status"] == "inconclusive"
    assert final["qualification_status"] == "not-established"
    assert final["budget"] is None
    assert final["errors"][0]["type"] == "NativeAbort"
    assert final["errors"][0]["message"] == str(primary)
    assert [
        error
        for error in final["errors"]
        if error["phase"] == "secondary.final_budget_snapshot"
    ] == [
        {
            "phase": "secondary.final_budget_snapshot",
            "type": "RuntimeError",
            "message": str(snapshot_error),
        }
    ]
    assert any(
        error["phase"] == "budget.persist" and error["message"] == str(snapshot_error)
        for error in final["errors"]
    )
    publication = final["census_publication"]
    assert publication["status"] == "unavailable"
    assert publication["attempts"] == int(earlier_checkpoint)
    assert len(publication["errors"]) == 1
    assert publication["errors"][0]["message"] == str(snapshot_error)
    row = final["trajectories"][0]
    assert_refused_prepared_start(adapter.roots[0], row)
    assert row["admission_failure"]["error"]["type"] == "NativeAbort"
    admission = row["admission_failure"]["evidence"]
    assert admission["census"]["stopped"]["message"] == str(primary)
    assert str(snapshot_error) in json.dumps(admission["census"]["persistence_errors"])
    assert admission["census"]["completed_graph_count"] == 1
    target = selected["target"]
    scope = admission["instances"][target.name]["child_inventory"]
    assert admission["failed_step_evidence"]["scope"] == scope
    assert admission["child_inventories"][scope]["graph_status"] == "incomplete"
    assert target.part.feature.calls.count("GetNextFeature") == 1
    assert selected["later"].body_calls == []
    assert selected["later"].part.first_feature_calls == 0
    assert adapter.roots[0].first_feature_calls == 0
    assert adapter.currentModel is None and adapter.resident_docs == []
    assert final["cleanup"]["confirmed"] is True
    assert report.failed
    if earlier_checkpoint:
        assert len(last_good) == 1
        assert dirty.FAILURE_PATH.read_bytes() == last_good[0]
        checkpoint = json.loads(last_good[0])
        assert_precleanup_checkpoint(checkpoint, "B", 1, 0)
        assert publication["last_success"] == checkpoint["census_checkpoint"]
    else:
        assert last_good == []
        assert not dirty.FAILURE_PATH.exists()
        assert publication["last_success"] is None


def test_actual_run_final_snapshot_failure_after_complete_pair_becomes_primary(
    monkeypatch, tmp_path
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    original_budget = dirty.Budget
    original_hash = dirty._hash_inputs
    original_write = dirty._write_json
    primary = RuntimeError("final budget snapshot unavailable after complete pair")
    budgets = []
    snapshots_after_a_discard = []
    writes = []

    class FinalSnapshotBudget(original_budget):
        def __init__(self, path):
            self.saving = False
            self.snapshots_unavailable = False
            self.failed_direct_snapshots = 0
            super().__init__(path, clock=lambda: 100.0)
            budgets.append(self)

        def save(self):
            self.saving = True
            try:
                return super().save()
            finally:
                self.saving = False

        def snapshot(self):
            if self.snapshots_unavailable:
                if not self.saving:
                    self.failed_direct_snapshots += 1
                raise primary
            return super().snapshot()

    def fail_snapshots_after_final_hash(paths):
        files = original_hash(paths)
        if len(adapter.roots) == 2 and adapter.currentModel is None:
            snapshots_after_a_discard.append(files)
            if len(snapshots_after_a_discard) == 2:
                # The original after-A hash is first; the original final-cleanup
                # hash follows both validation and the real A/B comparison.
                assert not dirty.FAILURE_PATH.exists()
                assert writes.count(dirty.FAILURE_PATH) == 0
                budgets[0].snapshots_unavailable = True
        return files

    def record_write(path, value):
        writes.append(path)
        return original_write(path, value)

    monkeypatch.setattr(dirty, "Budget", FinalSnapshotBudget)
    monkeypatch.setattr(dirty, "_hash_inputs", fail_snapshots_after_final_hash)
    monkeypatch.setattr(dirty, "_write_json", record_write)
    report = verify.Report()
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
    assert caught.value is primary
    assert len(budgets) == 1
    assert budgets[0].snapshots_unavailable is True
    assert budgets[0].failed_direct_snapshots == 1
    assert budgets[0].clock() == budgets[0].started == 100.0
    assert len(snapshots_after_a_discard) == 2
    assert snapshots_after_a_discard[0] == snapshots_after_a_discard[1]
    assert writes.count(dirty.REPORT_PATH) == writes.count(dirty.FAILURE_PATH) == 1
    final = json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8"))
    assert json.loads(dirty.FAILURE_PATH.read_text(encoding="utf-8")) == final
    assert final["status"] == "inconclusive"
    assert final["qualification_status"] == "not-established"
    assert final["budget"] is None
    assert final["census_publication"] == {
        "status": "inactive",
        "attempts": 0,
        "last_success": None,
        "errors": [],
    }
    assert not any(error["phase"] == "primary" for error in final["errors"])
    assert [
        error
        for error in final["errors"]
        if error["phase"] == "secondary.final_budget_snapshot"
    ] == [
        {
            "phase": "secondary.final_budget_snapshot",
            "type": "RuntimeError",
            "message": str(primary),
        }
    ]
    assert any(
        error["phase"] == "budget.persist" and error["message"] == str(primary)
        for error in final["errors"]
    )
    assert len(adapter.roots) == 2
    assert [row["variant"] for row in final["trajectories"]] == ["B", "A"]
    for root, row in zip(adapter.roots, final["trajectories"], strict=True):
        assert row["complete"] is True
        assert row["admission"]["admitted"] is True
        assert row["errors"] == row["validation_errors"] == []
        assert [boundary["key"] for boundary in row["boundaries"]] == EXPECTED_KEYS
        assert all(
            set(boundary["instances"]) == set(expected)
            for boundary in row["boundaries"]
        )
        assert row["counts"] == {
            "writes": 15,
            "visits": 14,
            "reads": 28,
            "suppressions": 2,
            "coincidences": 2,
        }
        assert len(root.writes) == 15
        assert len(root.consumer_reads) == 28
        assert root.tools_calls == len(root.managers) == 11
        assert all(
            manager.compute_calls == manager.done_calls == 1
            for manager in root.managers
        )
        assert len(root.edits) == 19
        assert len(root.forces) == (18 if row["variant"] == "A" else 2)
        assert len(row["prepare_attempts"]) == len(row["remate_attempts"]) == 2
        assert all(
            attempt["recognized_pinned_form"]
            for attempt in row["prepare_attempts"] + row["remate_attempts"]
        )
        assert row["gates"] == {
            "passed": [f"{verify.SWEEP_OWNER}:{suffix}" for suffix in GATE_SUFFIXES],
            "failed": [],
        }
        assert row["cleanup"]["confirmed"] is True
    assert not final["comparison"]["unclassified_differences"]
    assert final["cleanup"]["confirmed"] is True
    assert adapter.currentModel is None and adapter.resident_docs == []
    assert report.failed
    assert not dirty.REPORT_PATH.with_suffix(".json.tmp").exists()
    assert not dirty.FAILURE_PATH.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("oversize", [False, True])
def test_capture_bounds_raw_component_multiplicity_by_expected_inventory(
    monkeypatch, tmp_path, oversize
):
    _adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    component_limit = len(expected)
    components = [NativeContactComponent(name) for name in list(expected)[:-1]]
    components.append(components[0])
    if oversize:
        components.append(components[0])
    assert len(components) == component_limit + int(oversize)
    identities = [[component.name, component.configuration] for component in components]
    row = NativeInterference(components, 1.234567890123e-9)
    result = (row,)
    manager = NativeManager(result)
    budget = RecordingBudget()
    entry = {}
    capture = dirty.Capture(manager, budget, entry, component_limit=component_limit)
    capture.observe_settings()
    returned = capture.GetInterferences()
    assert returned is result
    assert returned[0] is row
    assert row.components is components
    assert capture.manager is manager
    assert manager.compute_calls == entry["compute_calls"] == 1
    assert entry["settings"] == SETTINGS
    assert entry["row_count"] == len(entry["rows"]) == 1
    recorded = entry["rows"][0]
    assert recorded["ordinal"] == 0
    if oversize:
        assert len(entry["errors"]) == 1
        assert recorded["error"] is entry["errors"][0]
        assert recorded["error"]["phase"] == "row:0"
        assert (
            "component multiplicity exceeds jig inventory"
            in (recorded["error"]["message"])
        )
        assert entry["canonical"] == []
        assert "components" not in recorded
        assert "raw_volume" not in recorded
        assert "volume_m3" not in recorded
        assert row.reads == ["Components"]
        assert all(component.reads == [] for component in components)
        assert budget.checks.count(("interference.component_metadata", False)) == 0
    else:
        assert entry["errors"] == []
        assert recorded["components"] == identities
        assert recorded["components"].count(identities[0]) == 2
        assert recorded["raw_volume"] == recorded["volume_m3"] == row.volume
        assert row.reads == ["Components", "Volume"]
        assert entry["canonical"] == [
            {
                "components": sorted(identities),
                "multiplicity": 1,
                "volumes_m3": [row.volume],
                "total_m3": row.volume,
            }
        ]
        for receiver in components[: component_limit - 1]:
            occurrences = sum(component is receiver for component in components)
            assert receiver.reads == ["Name2", "ReferencedConfiguration"] * occurrences
        assert (
            budget.checks.count(("interference.component_metadata", False))
            == component_limit
        )
    assert capture.Done() is None
    assert manager.compute_calls == manager.done_calls == 1
    assert entry["done"] == [{"success": True, "result": None}]


@pytest.mark.parametrize("oversize", [False, True])
def test_actual_run_static_capture_uses_expected_limit_before_native_admission(
    monkeypatch, tmp_path, oversize
):
    adapter, expected, _paths = install_native_case(monkeypatch, tmp_path)
    component_limit = len(expected)
    original_manager = NativeRoot.InterferenceDetectionManager.fget
    original_factory = _assembly.configured_interference_manager
    wide = {}

    class WideStaticRoot(NativeRoot):
        @property
        def InterferenceDetectionManager(self):
            manager = original_manager(self)
            if self.phase == "static" and not wide:
                assert self.prepared_feature is None
                assert self.first_feature_calls == 0
                assert all(
                    component.body_calls == [] for component in self.components.values()
                )
                assert self.writes == []
                assert not dirty.FAILURE_PATH.exists()
                components = [
                    NativeContactComponent(name, self.components[name].configuration)
                    for name in list(expected)[:-1]
                ]
                components.append(components[0])
                if oversize:
                    components.append(components[0])
                row = NativeInterference(components, 1e-9)
                wide.update(
                    manager=manager,
                    result=manager.result,
                    original_rows=tuple(manager.result),
                    components=components,
                    row=row,
                )
                manager.result.append(row)
            return manager

    def inject(root):
        if root.generation == 0:
            root.__class__ = WideStaticRoot

    adapter.open_hook = inject
    report = verify.Report()
    evidence = asyncio.run(dirty.run(adapter, verify.SWEEP_OWNER, report))
    assert evidence["status"] == "failed-consumer"
    assert evidence["qualification_status"] == "not-established"
    assert evidence["census_publication"] == {
        "status": "inactive",
        "attempts": 0,
        "last_success": None,
        "errors": [],
    }
    assert [row["variant"] for row in evidence["trajectories"]] == ["B", "A"]
    assert len(adapter.roots) == 2
    assert sum(len(row["boundaries"]) for row in evidence["trajectories"]) == 32
    for root, row in zip(adapter.roots, evidence["trajectories"], strict=True):
        assert row["admission"]["admitted"] is True
        assert [boundary["key"] for boundary in row["boundaries"]] == EXPECTED_KEYS
        assert all(
            set(boundary["instances"]) == set(expected)
            for boundary in row["boundaries"]
        )
        assert row["counts"] == {
            "writes": 15,
            "visits": 14,
            "reads": 28,
            "suppressions": 2,
            "coincidences": 2,
        }
        assert len(root.writes) == 15
        assert len(root.consumer_reads) == 28
        assert len(root.suppressions) == len(root.coincidents) == 2
        assert root.forces[:2] == [("static", 0), ("prepare", 0)]
        assert len(root.forces) == (18 if row["variant"] == "A" else 2)
        assert len(root.edits) == 19
        assert root.tools_calls == len(root.managers) == 11
        assert len(row["interferences"]) == 11
        assert all(
            manager.compute_calls == manager.done_calls == 1
            for manager in root.managers
        )
        assert all(entry["checked_outside_attempt"] for entry in row["interferences"])
        assert len(row["prepare_attempts"]) == len(row["remate_attempts"]) == 2
        assert all(
            attempt["recognized_pinned_form"]
            for attempt in row["prepare_attempts"] + row["remate_attempts"]
        )
        aggregate = row["original_aggregate_timings"]
        assert aggregate["jig.drive_write_attempts"] == 15
        assert aggregate["jig.transform_readback_attempts"] == 28
        assert aggregate["jig.edit_rebuild_attempts"] == 16
        assert aggregate["jig.force_rebuild_attempts"] == (
            16 if row["variant"] == "A" else 0
        )
        assert row["cleanup"]["confirmed"] is True
    b, a = evidence["trajectories"]
    assert b["gates"]["passed"] == [
        f"{verify.SWEEP_OWNER}:{suffix}"
        for suffix in GATE_SUFFIXES
        if suffix != "interference-free"
    ]
    assert len(b["gates"]["failed"]) == 1
    assert b["gates"]["failed"][0][0] == (f"{verify.SWEEP_OWNER}:interference-free")
    assert "1 interference(s):" in b["gates"]["failed"][0][1]
    assert a["gates"] == {
        "passed": [f"{verify.SWEEP_OWNER}:{suffix}" for suffix in GATE_SUFFIXES],
        "failed": [],
    }
    static = next(
        entry for entry in b["interferences"] if entry["label"] == "initial/static"
    )
    manager = wide["manager"]
    components = wide["components"]
    native_row = wide["row"]
    original_rows = wide["original_rows"]
    assert len(components) == component_limit + int(oversize)
    assert manager.result is wide["result"]
    assert manager.result[-1] is native_row
    assert all(
        actual is original
        for actual, original in zip(manager.result[:-1], original_rows, strict=True)
    )
    assert manager.compute_calls == manager.done_calls == static["compute_calls"] == 1
    assert static["settings"] == SETTINGS
    assert static["row_count"] == len(original_rows) + 1
    assert static["done"] == [{"success": True, "result": None}]
    recorded = static["rows"][-1]
    assert recorded["ordinal"] == len(original_rows)
    identities = [[component.name, component.configuration] for component in components]
    if oversize:
        assert len(static["errors"]) == 1
        assert recorded["error"] == static["errors"][0]
        assert (
            "component multiplicity exceeds jig inventory"
            in (recorded["error"]["message"])
        )
        assert "components" not in recorded
        assert "raw_volume" not in recorded
        assert "volume_m3" not in recorded
        assert native_row.reads == ["Components", "Components", "Volume"]
    else:
        assert static["errors"] == []
        assert recorded["components"] == identities
        assert recorded["components"].count(identities[0]) == 2
        assert recorded["raw_volume"] == recorded["volume_m3"] == native_row.volume
        assert native_row.reads == ["Components", "Volume", "Components", "Volume"]
        assert any(
            entry["components"] == sorted(identities) for entry in static["canonical"]
        )
    # The unchanged original consumer reads the same metadata even when the
    # observer refuses the oversized array; only the duplicate decode is bounded.
    reads_per_occurrence = 1 if oversize else 2
    for receiver in components[: component_limit - 1]:
        occurrences = sum(component is receiver for component in components)
        assert receiver.reads == ["Name2", "ReferencedConfiguration"] * (
            reads_per_occurrence * occurrences
        )
    assert _assembly.configured_interference_manager is original_factory
    assert adapter.events.index(("close", 0)) < adapter.events.index(("open", 1))
    assert evidence["cleanup"]["confirmed"] is True
    assert adapter.currentModel is None and adapter.resident_docs == []
    assert report.failed
    assert json.loads(dirty.REPORT_PATH.read_text(encoding="utf-8")) == evidence
    assert json.loads(dirty.FAILURE_PATH.read_text(encoding="utf-8")) == evidence
