"""Offline behavior of the raw-matrix branch's source-only producer refusal.

Extract real action bodies without importing dodo or its host-facing modules.
Every native/dispatch/publication collaborator is a fail-closed fake; unlike the
legacy dormant-path tests, these tests never replace the source policy helper.
"""

import ast
import contextlib
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import pytest


_DODO = Path(__file__).resolve().parents[2] / "dodo.py"
_KEY = "a" * 64
_PRODUCERS = ("part", "assembly", "generic-part", "generic-assembly")


@cache
def _action_code():
    names = {
        "_refuse_raw_matrix_producer",
        "_tag_cache_key",
        "_probe_cache",
        "_cached_com_action",
        "_cached_part_action",
        "build_or_refresh",
        "_farm_build",
    }
    source = ast.parse(_DODO.read_text(encoding="utf-8"), filename=str(_DODO))
    functions = [
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in functions} == names
    for node in functions:
        node.decorator_list = []  # Marker decorators only; import no project code.
    module = ast.parse("from __future__ import annotations\n")
    module.body.extend(functions)
    return compile(ast.fix_missing_locations(module), str(_DODO), "exec")


@pytest.fixture
def actions(tmp_path):
    namespace = {}
    exec(_action_code(), namespace)
    state = SimpleNamespace(
        farm=False,
        outcome=False,
        forced=None,
        restores=[],
        keys=[],
        writes=[],
        forbidden=[],
        phases=[],
        attributes=[],
        refreshes=[],
        deps=["unchanged-original-recipe"],
        outputs=[tmp_path / "model.SLDASM"],
        ledger=tmp_path / ".model.inputs.json",
        inputs={"recipe": "original-digest"},
    )

    class RestoreLocked(RuntimeError):
        pass

    class Span:
        def set_attribute(self, key, value):
            state.attributes.append((key, value))

    @contextlib.contextmanager
    def span(name, **_attributes):
        state.phases.append(name)
        yield Span()

    def forbidden(name):
        def call(*_args, **_kwargs):
            state.forbidden.append(name)
            raise AssertionError(f"restore-only producer reached {name}")

        return call

    def restore(key, outputs, label):
        state.restores.append((key, outputs, label))
        if isinstance(state.outcome, BaseException):
            raise state.outcome
        return state.outcome

    def cache_key(deps, label):
        state.keys.append((deps, label))
        return _KEY

    namespace.update(
        _telemetry=SimpleNamespace(span=span, BUILD_INFRA_SERVICE="build-infra"),
        _cache=SimpleNamespace(
            RestoreLocked=RestoreLocked,
            restore=restore,
            forced_refresh=lambda _label: state.forced,
            note_refresh=lambda *args: state.refreshes.append(args),
            store=forbidden("cache publication"),
            require_refresh_store=forbidden("refresh publication check"),
            key_input_paths=forbidden("dispatch key inputs"),
        ),
        _farm=SimpleNamespace(
            enabled=lambda: state.farm,
            checkout_drift=forbidden("farm checkout probe"),
            run_leaf=forbidden("farm leaf dispatch"),
        ),
        _cache_key=cache_key,
        _part_file_deps=lambda *_args: state.deps,
        _assembly_file_deps=lambda *_args: state.deps,
        _part_cache_outputs=lambda _stem: state.outputs,
        _assembly_cache_outputs=lambda _stem: state.outputs,
        _input_ledger=lambda _stem: state.ledger,
        _ledger_inputs=lambda _deps: state.inputs,
        _stamp_part_execution=lambda stem: state.writes.append(("part-token", stem)),
        _stamp_assembly_execution=lambda stem: state.writes.append(
            ("assembly-token", stem)
        ),
        _write_input_ledger=lambda *args: state.writes.append(("ledger", *args)),
        _com_seat=forbidden("COM seat/lock"),
        _reprobe_under_seat=forbidden("under-seat reprobe"),
        _release_seat_documents=forbidden("seat document release"),
        _sw_ensure_once=forbidden("SolidWorks startup/preflight"),
        _exec_com=forbidden("native producer"),
        explode_plan=forbidden("assembly refresh/explode planning"),
        _explode_base_key=forbidden("explode-base key"),
        _assembly_tier=forbidden("assembly refresh tier"),
        _write_stamp=forbidden("gate stamp"),
    )
    direct_dispatch = namespace["_farm_build"]
    namespace["_farm_build"] = forbidden("farm dispatch boundary")

    def run(kind, *, label=None, stamp=None):
        if kind == "part":
            return namespace["_cached_part_action"](
                "model", tmp_path / "build_model.py"
            )
        if kind == "assembly":
            return namespace["build_or_refresh"](
                "model", [], [], [str(state.outputs[0])]
            )
        if label is None:
            label = "part:model" if kind == "generic-part" else "assembly:model"
        return namespace["_cached_com_action"](
            label,
            ["fake-native-command"],
            state.deps,
            state.outputs,
            "model",
            stamp,
        )

    return SimpleNamespace(
        state=state,
        namespace=namespace,
        run=run,
        direct_dispatch=direct_dispatch,
        RestoreLocked=RestoreLocked,
    )


@pytest.mark.parametrize("kind", _PRODUCERS)
@pytest.mark.parametrize("farm", [False, True], ids=["local", "farm"])
@pytest.mark.parametrize(
    "disposition", ["miss", "locked", "disabled", "off", "error", "hit-after-wait"]
)
def test_every_nonexact_disposition_refuses_before_any_producer_boundary(
    actions,
    kind,
    farm,
    disposition,
):
    case = actions
    case.state.farm = farm
    case.namespace["_probe_cache"] = lambda *_args: disposition
    with pytest.raises(RuntimeError, match="source-explicit restore-only") as caught:
        case.run(kind)
    assert repr(disposition) in str(caught.value)
    assert case.state.forbidden == []
    assert case.state.writes == []
    assert case.state.restores == []
    assert len(case.state.keys) == 1
    assert case.state.keys[0][0] is case.state.deps
    assert case.state.phases == [f"cache.probe {case.state.keys[0][1]}"]


@pytest.mark.parametrize("kind", _PRODUCERS)
@pytest.mark.parametrize("farm", [False, True], ids=["local", "farm"])
@pytest.mark.parametrize("outcome", ["miss", "disabled", "error", "locked"])
def test_real_probe_failures_never_dispatch_reprobe_build_or_publish(
    actions, kind, farm, outcome
):
    case = actions
    case.state.farm = farm
    if outcome == "error":
        case.state.outcome = OSError("cache transport failed")
    elif outcome == "locked":
        case.state.outcome = case.RestoreLocked("cached artifact share-locked")
    # Misses and disabled caches both return False from the ordinary restore API.
    expected_error = OSError if outcome == "error" else RuntimeError
    with pytest.raises(expected_error) as caught:
        case.run(kind)
    if outcome == "error" or (outcome == "locked" and farm):
        assert caught.value is case.state.outcome
    else:
        assert "source-explicit restore-only" in str(caught.value)
    assert case.state.forbidden == []
    assert case.state.writes == []
    assert len(case.state.restores) == 1
    key, outputs, label = case.state.restores[0]
    assert key == _KEY
    assert outputs is case.state.outputs
    assert case.state.keys == [(case.state.deps, label)]
    assert case.state.phases == [f"cache.probe {label}"]


@pytest.mark.parametrize("kind", _PRODUCERS)
@pytest.mark.parametrize("farm", [False, True], ids=["local", "farm"])
def test_forced_refresh_cannot_turn_a_producer_into_a_build(actions, kind, farm):
    case = actions
    case.state.farm = farm
    case.state.forced = "refresh requested"
    case.state.outcome = True  # Even a present artifact is bypassed by refresh.
    with pytest.raises(RuntimeError, match="source-explicit restore-only"):
        case.run(kind)
    assert case.state.restores == []
    assert case.state.forbidden == []
    assert case.state.writes == []
    assert len(case.state.refreshes) == 1


@pytest.mark.parametrize("kind", _PRODUCERS)
@pytest.mark.parametrize("farm", [False, True], ids=["local", "farm"])
def test_ordinary_exact_hit_retains_identity_and_ledger_semantics(actions, kind, farm):
    case = actions
    case.state.farm = farm
    case.state.outcome = True
    case.run(kind)
    expected_writes = []
    if kind == "part":
        expected_writes = [("part-token", "model")]
    elif kind == "assembly":
        expected_writes = [
            ("assembly-token", "model"),
            ("ledger", case.state.ledger, case.state.inputs),
        ]
    assert case.state.writes == expected_writes
    assert case.state.forbidden == []
    assert len(case.state.restores) == 1
    assert case.state.restores[0][:2] == (_KEY, case.state.outputs)
    assert case.state.keys == [(case.state.deps, case.state.restores[0][2])]
    assert ("cache", "hit") in case.state.attributes


@pytest.mark.parametrize(
    "label", ["part:model", "assembly:model", "assembly:model explode-base"]
)
def test_direct_farm_producer_dispatch_is_refused_before_key_or_checkout_probes(
    actions, label
):
    with pytest.raises(RuntimeError, match="source-explicit restore-only"):
        actions.direct_dispatch(label, _KEY, actions.state.outputs)
    assert actions.state.forbidden == []
    assert actions.state.restores == []
    assert actions.state.writes == []


@pytest.mark.parametrize("label", ["verify:kinematics", "verify_soundness:model"])
def test_nonproducer_verify_can_execute_stamp_and_store(actions, label):
    case = actions
    events = []

    @contextlib.contextmanager
    def seat(_label):
        events.append("seat")
        yield 0.0

    case.namespace.update(
        _com_seat=seat,
        _reprobe_under_seat=lambda *_args: events.append("reprobe") or False,
        _sw_ensure_once=lambda: events.append("ensure"),
        _stage_name=lambda _label: "verify",
        _tag_seat_wait=lambda *_args: None,
        _exec_com=lambda *_args, **_kwargs: events.append("verify"),
        _write_stamp=lambda *_args: events.append("stamp"),
    )
    case.namespace["_cache"].store = lambda *_args: events.append("store") or "stored"
    case.namespace["_cache"].require_refresh_store = lambda *_args: events.append(
        "store-required"
    )
    case.run("generic", label=label, stamp="reports/verify.ok")
    assert events == [
        "seat",
        "reprobe",
        "ensure",
        "verify",
        "stamp",
        "store",
        "store-required",
    ]
    assert case.state.forbidden == []
    assert case.state.writes == []
    assert case.state.phases == [
        f"cache.probe {label}",
        f"task {label}",
        f"cache.store {label}",
    ]


def test_nonproducer_verify_can_still_dispatch_to_the_farm(actions):
    case = actions
    case.state.farm = True
    dispatched = []
    case.namespace["_farm_build"] = lambda *args: dispatched.append(args)
    case.run("generic", label="verify:kinematics")
    assert dispatched == [("verify:kinematics", _KEY, case.state.outputs)]
    assert len(case.state.restores) == 1
    assert case.state.forbidden == []
    assert case.state.writes == []
    assert case.state.phases == ["cache.probe verify:kinematics"]
