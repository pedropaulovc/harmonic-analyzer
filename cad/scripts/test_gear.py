"""Offline contracts for shared gear feature construction."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import _common
import _gear

from _gear import pattern_about_z


class _Result:
    def __init__(self, data: object) -> None:
        self.is_success = True
        self.data = data
        self.error = None


class _Model:
    """Records the hide of the created axis (IModelDoc2 surface)."""

    def __init__(self) -> None:
        self.selected: list[tuple[str, str]] = []
        self.blanked: list[tuple[str, str]] = []
        self.Extension = SimpleNamespace(SelectByID2=self._select)

    def _select(self, name, kind, *_rest) -> bool:
        self.selected.append((name, kind))
        return True

    def ClearSelection2(self, _all: bool) -> None:
        self.selected = []

    def BlankRefGeom(self) -> None:
        self.blanked.extend(self.selected)


class _Adapter:
    def __init__(self) -> None:
        self.pattern_params = None
        self.currentModel = _Model()

    async def create_axis(self, _params: object) -> _Result:
        return _Result(SimpleNamespace(name="Axis17"))

    async def circular_pattern_feature(self, params: object) -> _Result:
        self.pattern_params = params
        return _Result(SimpleNamespace(name="CirPattern1"))


@pytest.mark.asyncio
async def test_pattern_selects_created_reference_axis_by_name() -> None:
    adapter = _Adapter()

    pattern = await pattern_about_z(adapter, "Cut-Extrude1", 120, 31.1, 1.5)

    assert pattern.name == "CirPattern1"
    assert adapter.pattern_params.axis_name == "Axis17"
    assert adapter.pattern_params.axis_point == []
    assert adapter.pattern_params.features == ["Cut-Extrude1"]
    assert adapter.pattern_params.count == 120
    assert adapter.pattern_params.geometry_pattern is True
    # The created axis is hidden so it does not print in renders.
    assert adapter.currentModel.blanked == [("Axis17", "AXIS")]


# These fakes model declared methods/properties, not a native execution. They
# deliberately expose no relation SolveStatus/Status/IsDangling member.
class _SketchEntity:
    __slots__ = ("_status", "_id")

    def __init__(self, status: object, native_id: tuple[int, int]) -> None:
        self._status = status
        self._id = native_id

    @property
    def Status(self) -> object:
        return self._status

    def GetID(self) -> tuple[int, int]:
        return self._id


class _SketchRelation:
    __slots__ = ("_kind", "_entities", "_types")

    def __init__(self, kind: int, entities: tuple, types: tuple[int, ...]) -> None:
        self._kind, self._entities, self._types = kind, entities, types

    def GetRelationType(self) -> int:
        return self._kind

    def GetEntities(self) -> tuple:
        return self._entities

    def GetEntitiesType(self) -> tuple[int, ...]:
        return self._types


class _RelationManager:
    __slots__ = ("relations", "calls", "refuse_all", "deleted")

    def __init__(self, relations: dict[int, tuple]) -> None:
        self.relations = relations
        self.calls: list[int] = []
        self.refuse_all = False
        self.deleted: list[object] = []

    def DeleteRelation(self, relation: object) -> bool:
        self.deleted.append(relation)
        return True

    def GetRelations(self, filter_value: int) -> tuple:
        self.calls.append(filter_value)
        if self.refuse_all and filter_value == 0:
            raise RuntimeError("native GetRelations refused")
        return self.relations.get(filter_value, ())


class _SketchManager:
    __slots__ = ("_value", "writes", "refuse_enable", "refuse_restore", "initial")

    def __init__(self, initial: object = False) -> None:
        self.initial = self._value = initial
        self.writes: list[bool] = []
        self.refuse_enable = self.refuse_restore = False

    @property
    def AutoInference(self) -> bool:
        return True

    @property
    def AutoSolve(self) -> bool:
        return True

    @property
    def AddToDB(self) -> object:
        return self._value

    @AddToDB.setter
    def AddToDB(self, value: bool) -> None:
        self.writes.append(value)
        if self.refuse_enable and value is True:
            return
        if self.refuse_restore and value is self.initial:
            return
        self._value = value


class _NativeSketch:
    __slots__ = ("_status", "_relations")

    def __init__(self, relations: _RelationManager) -> None:
        self._relations = relations
        self._status = 2

    @property
    def RelationManager(self) -> _RelationManager:
        return self._relations

    def GetConstrainedStatus(self) -> int:
        return self._status


class _SketchModel:
    __slots__ = ("sketch",)

    def __init__(self, sketch: _NativeSketch) -> None:
        self.sketch = sketch

    def GetActiveSketch2(self) -> _NativeSketch:
        return self.sketch

    def GetPathName(self) -> str:
        return ""  # valid native result for an unsaved part


class _SketchAdapter:
    def __init__(self, states: list[str], statuses: tuple[object, ...] = (2,)) -> None:
        self._states = iter(states)
        self._sketch_entities = {
            f"EquationCurve_{index + 1}": _SketchEntity(status, (0, index + 1))
            for index, status in enumerate(statuses)
        }
        segment = next(iter(self._sketch_entities.values()))
        point = _SketchEntity(3, (0, 1))  # same ID, DIFFERENT native entity type
        relation = _SketchRelation(9, (segment, point, None), (7, 2, 0))
        filtered_relation = _SketchRelation(9, (segment, point, None), (7, 2, 0))
        self.relations = _RelationManager({
            0: (relation, None), 2: (filtered_relation,), 1: (), 6: (),
        })
        self.sketch = _NativeSketch(self.relations)
        self.currentModel = _SketchModel(self.sketch)
        self.currentSketchManager = _SketchManager()
        self.fixed: list[str] = []
        self.filtered_probe_refused = False

    async def check_sketch_fully_defined(self) -> _Result:
        state = next(self._states)
        self.sketch._status = {"under_defined": 2, "fully_defined": 3, "over_defined": 4}[state]
        return _Result({"definition_state": state, "raw_status": self.sketch._status})

    async def get_over_defining_relations(self) -> _Result:
        if self.filtered_probe_refused:
            raise RuntimeError("filtered adapter probe refused")
        return _Result({"relations": [{"relation_type": 9}]})

    async def add_sketch_constraint(self, entity: str, other: None, kind: str) -> _Result:
        assert other is None and kind == "fix"
        self.fixed.append(entity)
        return _Result("Constraint_1")


@pytest.fixture
def sketch_logs(monkeypatch):
    logs: dict[str, list[str]] = {"error": [], "warn": [], "debug": []}
    for severity in logs:
        monkeypatch.setattr(
            _common._telemetry, severity,
            lambda message, severity=severity, **_fields: logs[severity].append(message),
        )
    return logs


@pytest.mark.asyncio
@pytest.mark.parametrize("after_fix", [False, True])
async def test_over_defined_logs_every_relation_before_raising(after_fix, sketch_logs) -> None:
    states = ["under_defined", "over_defined"] if after_fix else ["over_defined"]
    adapter = _SketchAdapter(states)

    with pytest.raises(RuntimeError, match="sketch OVER-defined; over-defining relations"):
        await _common.ensure_fully_defined(
            adapter, "stock gap sketch",
            fix_entities=["EquationCurve_1"], allow_fix_escalation=True,
        )

    error = next(line for line in sketch_logs["error"] if "(over_defined)" in line)
    snapshot = json.loads(error.split(": ", 2)[2])
    assert snapshot["sketch_status"] == 4
    assert snapshot["path"] == ""
    assert snapshot["AddToDB"] is False
    assert snapshot["AutoInference"] is True
    assert snapshot["AutoSolve"] is True
    assert len(snapshot["relations"]["swAll"]) == 2
    row = snapshot["relations"]["swAll"][0]
    assert row["relation_type"] == 9
    assert row["relation_solve_status"] == "UNKNOWN (no native accessor)"
    assert row["entities"][0]["interface"] == "ISketchSegment"
    assert row["entities"][1]["interface"] == "ISketchPoint"
    assert row["entities"][0]["native_id"] == row["entities"][1]["native_id"]
    assert row["entities"][0]["status"] == 2
    assert row["entities"][1]["status"] == 3
    assert row["entities"][2]["null_entity"] is True
    assert snapshot["relations"]["swAll"][1]["null_relation"] is True
    assert snapshot["relations"]["swOverDefining"][0]["returned_by_filter"] == "swOverDefining"
    assert snapshot["relations"]["swDangling"] == []
    assert snapshot["relations"]["swBroken"] == []
    assert set(adapter.relations.calls) == {0, 1, 2, 6}
    assert adapter.fixed == (["EquationCurve_1"] if after_fix else [])


@pytest.mark.asyncio
async def test_over_defined_keeps_failure_when_diagnostics_refuse(sketch_logs) -> None:
    adapter = _SketchAdapter(["over_defined"])
    adapter.relations.refuse_all = True
    adapter.filtered_probe_refused = True

    with pytest.raises(RuntimeError, match="stock gap sketch: sketch OVER-defined"):
        await _common.ensure_fully_defined(adapter, "stock gap sketch")

    assert "native GetRelations refused" in sketch_logs["error"][0]
    assert set(adapter.relations.calls) == {0, 1, 2, 6}


@pytest.mark.asyncio
async def test_over_defined_keeps_failure_when_logger_refuses(monkeypatch) -> None:
    def refuse(*_args, **_kwargs):
        raise RuntimeError("logging refused")

    monkeypatch.setattr(_common._telemetry, "error", refuse)
    with pytest.raises(RuntimeError, match="sketch OVER-defined"):
        await _common.ensure_fully_defined(_SketchAdapter(["over_defined"]), "gap")


@pytest.mark.asyncio
async def test_fix_skips_already_constrained_equation_curve(sketch_logs) -> None:
    adapter = _SketchAdapter(["under_defined", "fully_defined"], statuses=(3, 2))
    await _common.ensure_fully_defined(
        adapter, "gap", fix_entities=["EquationCurve_1", "EquationCurve_2"],
        allow_fix_escalation=True,
    )
    assert adapter.fixed == ["EquationCurve_2"]
    assert any("(before_fix)" in line for line in sketch_logs["debug"])
    assert any("(after_fix)" in line for line in sketch_logs["debug"])
    assert not any("native sketch relations" in line for line in sketch_logs["warn"])


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [1, 4, 5, 6, 7, None, True, "2", lambda: 2])
async def test_fix_refuses_non_underconstrained_entity(status, sketch_logs) -> None:
    adapter = _SketchAdapter(["under_defined"], statuses=(status,))
    with pytest.raises(RuntimeError, match="cannot fix EquationCurve_1 with native Status"):
        await _common.ensure_fully_defined(
            adapter, "gap", fix_entities=["EquationCurve_1"], allow_fix_escalation=True,
        )
    assert adapter.fixed == []


@pytest.mark.asyncio
@pytest.mark.parametrize("entity_id", ["Line_1", "EquationCurve_999"])
async def test_fix_refuses_non_owned_equation_entity(entity_id, sketch_logs) -> None:
    adapter = _SketchAdapter(["under_defined"])
    adapter._sketch_entities["Line_1"] = _SketchEntity(2, (0, 2))
    with pytest.raises(RuntimeError, match="not an owned equation curve"):
        await _common.ensure_fully_defined(
            adapter, "gap", fix_entities=[entity_id], allow_fix_escalation=True,
        )
    assert adapter.fixed == []


@pytest.mark.asyncio
async def test_nonwhitelisted_sketch_stays_strict(sketch_logs) -> None:
    adapter = _SketchAdapter(["under_defined"])
    with pytest.raises(RuntimeError, match="legacy fix escalation disabled"):
        await _common.ensure_fully_defined(adapter, "gap", fix_entities=["EquationCurve_1"])
    assert adapter.fixed == []
    assert adapter.relations.calls == []


class _CurveAdapter:
    def __init__(self, manager: _SketchManager) -> None:
        self.currentSketchManager = manager
        self.calls: list[object] = []
        self.fail_creation = False
        self.fail_result = False

    async def create_equation_driven_curve(self, parameters: object) -> _Result:
        assert self.currentSketchManager.AddToDB is True
        self.calls.append(parameters)
        if self.fail_creation:
            raise RuntimeError("equation parser refused")
        if self.fail_result:
            failed = _Result(None)
            failed.is_success = False
            failed.error = "equation parser refused"
            return failed
        return _Result("EquationCurve_1")


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [False, True])
async def test_shared_equation_curve_uses_direct_db_and_restores(initial, sketch_logs) -> None:
    manager = _SketchManager(initial)
    adapter = _CurveAdapter(manager)
    assert _gear.equation_curve is _common.equation_curve
    assert await _common.equation_curve(adapter, "floor", "t", "1-t") == "EquationCurve_1"
    parameters = adapter.calls[0]
    assert (parameters.x_expression, parameters.y_expression) == ("t", "1-t")
    assert (parameters.range_start, parameters.range_end) == ("0", "1")
    assert parameters.lock_start is True and parameters.lock_end is True
    assert manager.AddToDB is initial
    assert manager.writes == [True, initial]
    assert any("AddToDB before=" in line for line in sketch_logs["debug"])
    assert any("AddToDB enabled=True" in line for line in sketch_logs["debug"])
    assert any(f"AddToDB restored={initial!r}" in line for line in sketch_logs["debug"])


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_result", [False, True])
async def test_equation_curve_restores_direct_db_on_creator_failure(
    failed_result, sketch_logs
) -> None:
    manager = _SketchManager()
    adapter = _CurveAdapter(manager)
    adapter.fail_creation = not failed_result
    adapter.fail_result = failed_result
    with pytest.raises(RuntimeError, match="equation parser refused"):
        await _common.equation_curve(adapter, "floor", "t", "1-t")
    assert manager.AddToDB is False
    assert manager.writes == [True, False]


@pytest.mark.asyncio
async def test_equation_curve_refuses_failed_direct_db_write(sketch_logs) -> None:
    manager = _SketchManager()
    manager.refuse_enable = True
    adapter = _CurveAdapter(manager)
    with pytest.raises(RuntimeError, match="AddToDB write refused"):
        await _common.equation_curve(adapter, "floor", "t", "1-t")
    assert adapter.calls == []
    assert manager.AddToDB is False


@pytest.mark.asyncio
async def test_equation_curve_refuses_failed_direct_db_restore(sketch_logs) -> None:
    manager = _SketchManager()
    manager.refuse_restore = True
    with pytest.raises(RuntimeError, match="AddToDB restore refused"):
        await _common.equation_curve(_CurveAdapter(manager), "floor", "t", "1-t")
    assert manager.AddToDB is True


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [None, 0, "False", lambda: False])
async def test_equation_curve_requires_native_bool_direct_db(initial, sketch_logs) -> None:
    manager = _SketchManager(initial)
    adapter = _CurveAdapter(manager)
    with pytest.raises(RuntimeError, match="AddToDB is not a native bool"):
        await _common.equation_curve(adapter, "floor", "t", "1-t")
    assert adapter.calls == []
    assert manager.writes == []


class _UnreadableRelation(_SketchRelation):
    __slots__ = ()

    def GetRelationType(self) -> int:
        raise RuntimeError("native relation type refused")


def test_relation_inventory_continues_after_one_getter_refuses(sketch_logs) -> None:
    adapter = _SketchAdapter(["over_defined"])
    good = adapter.relations.relations[0][0]
    bad = _UnreadableRelation(9, (), ())
    adapter.relations.relations[0] = (bad, good)

    snapshot = _common._sketch_relation_snapshot(adapter, "gap")

    rows = snapshot["relations"]["swAll"]
    assert len(rows) == 2
    assert rows[0]["relation_type"] == {"unavailable": "native relation type refused"}
    assert rows[1]["relation_type"] == 9
    assert rows[1]["entities"][0]["status"] == 2
    assert set(adapter.relations.calls) == {0, 1, 2, 6}


def test_relation_inventory_does_not_join_fresh_wrappers_by_python_identity() -> None:
    adapter = _SketchAdapter(["over_defined"])
    all_relation = adapter.relations.relations[0][0]
    filtered_relation = adapter.relations.relations[2][0]
    assert all_relation is not filtered_relation

    snapshot = _common._sketch_relation_snapshot(adapter, "gap")

    assert snapshot["relations"]["swAll"][0]["relation_solve_status"].startswith("UNKNOWN")
    filtered = snapshot["relations"]["swOverDefining"][0]
    assert filtered["returned_by_filter"] == "swOverDefining"
    assert filtered["entities"][0]["native_id"] == (0, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["before", "enabled", "restored"])
@pytest.mark.parametrize("failed_result", [False, True])
async def test_creator_failure_survives_selective_direct_db_debug_refusal(
    phase, failed_result, monkeypatch, sketch_logs
) -> None:
    selector = f"AddToDB {phase}="
    attempted: list[str] = []

    def debug(message, **_fields):
        attempted.append(message)
        if selector in message:
            raise RuntimeError("selected DEBUG refused")

    monkeypatch.setattr(_common._telemetry, "debug", debug)
    manager = _SketchManager()
    adapter = _CurveAdapter(manager)
    adapter.fail_creation = not failed_result
    adapter.fail_result = failed_result

    with pytest.raises(RuntimeError, match="equation parser refused"):
        await _common.equation_curve(adapter, "floor", "t", "1-t")

    assert len(adapter.calls) == 1
    assert manager.AddToDB is False
    assert manager.writes == [True, False]
    assert any(selector in message for message in attempted)


@pytest.mark.asyncio
async def test_restore_refusal_precedes_restored_debug_logging(
    monkeypatch, sketch_logs
) -> None:
    attempted: list[str] = []

    def debug(message, **_fields):
        attempted.append(message)
        if "AddToDB restored=" in message:
            raise RuntimeError("restored DEBUG refused")

    monkeypatch.setattr(_common._telemetry, "debug", debug)
    manager = _SketchManager()
    manager.refuse_restore = True

    with pytest.raises(RuntimeError, match="AddToDB restore refused"):
        await _common.equation_curve(_CurveAdapter(manager), "floor", "t", "1-t")

    assert manager.AddToDB is True
    assert not any("AddToDB restored=" in message for message in attempted)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selector", ["EquationCurve_1.Status=", "fixed EquationCurve_1 -> over_defined"]
)
async def test_post_fix_overdefined_inventory_precedes_refusable_debug(
    selector, monkeypatch, sketch_logs
) -> None:
    attempted: list[str] = []

    def debug(message, **_fields):
        attempted.append(message)
        if selector in message:
            raise RuntimeError("selected FIX DEBUG refused")

    monkeypatch.setattr(_common._telemetry, "debug", debug)
    adapter = _SketchAdapter(["under_defined", "over_defined"])

    with pytest.raises(RuntimeError, match="gap: sketch OVER-defined"):
        await _common.ensure_fully_defined(
            adapter, "gap", fix_entities=["EquationCurve_1"],
            allow_fix_escalation=True,
        )

    error = next(line for line in sketch_logs["error"] if "(over_defined)" in line)
    snapshot = json.loads(error.split(": ", 2)[2])
    assert snapshot["sketch_status"] == 4
    assert len(snapshot["relations"]["swAll"]) == 2
    assert set(adapter.relations.calls) == {0, 1, 2, 6}
    assert adapter.fixed == ["EquationCurve_1"]
    assert adapter.relations.deleted == []  # no relation is ever deleted
    assert not any("fixed EquationCurve_1 -> over_defined" in line for line in attempted)


@pytest.mark.parametrize("module", ["dt_cylinder_gear_spec", "dt_alignment_pinion_spec"])
def test_stock_gap_fix_order_leaves_the_perpendicular_closing_pair_last(module) -> None:
    # Farm 20261009T214825987Z: the drum's native-order closure (closing ray
    # + nearly radial flank) was singular; the closing pair is not.
    import importlib
    import math

    segments = importlib.import_module(module).STOCK_FORM.native_segments()
    order = _gear.stock_gap_fix_order([s.name for s in segments])
    assert sorted(order) == list(range(len(segments)))
    # One chain: each FIX after the first touches the previous one.
    assert all((b - a) % len(segments) == 1 for a, b in zip(order, order[1:]))
    ray, arc = segments[order[-2]], segments[order[-1]]
    assert (ray.name, arc.name) == ("LowerClosingRay", "ClearanceArc")
    u = (ray.start_mm[0] - ray.end_mm[0], ray.start_mm[1] - ray.end_mm[1])
    v = (arc.end_mm[0] - arc.start_mm[0], arc.end_mm[1] - arc.start_mm[1])
    sine = abs(u[0] * v[1] - u[1] * v[0]) / (math.hypot(*u) * math.hypot(*v))
    assert sine > 0.9
    with pytest.raises(ValueError):
        _gear.stock_gap_fix_order([s.name for s in reversed(segments)])


@pytest.mark.asyncio
async def test_entity_status_refusal_survives_eligibility_debug_refusal(
    monkeypatch, sketch_logs
) -> None:
    def debug(message, **_fields):
        if "EquationCurve_1.Status=" in message:
            raise RuntimeError("eligibility DEBUG refused")

    monkeypatch.setattr(_common._telemetry, "debug", debug)
    adapter = _SketchAdapter(["under_defined"], statuses=(4,))

    with pytest.raises(RuntimeError, match="cannot fix EquationCurve_1 with native Status=4"):
        await _common.ensure_fully_defined(
            adapter, "gap", fix_entities=["EquationCurve_1"],
            allow_fix_escalation=True,
        )

    assert adapter.fixed == []
