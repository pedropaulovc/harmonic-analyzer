"""Offline contracts for shared gear feature construction."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import _common

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
    __slots__ = ("relations", "calls", "refuse_all")

    def __init__(self, relations: dict[int, tuple]) -> None:
        self.relations = relations
        self.calls: list[int] = []
        self.refuse_all = False

    def GetRelations(self, filter_value: int) -> tuple:
        self.calls.append(filter_value)
        if self.refuse_all and filter_value == 0:
            raise RuntimeError("native GetRelations refused")
        return self.relations.get(filter_value, ())


class _SketchManager:
    """Read-only sketch-manager properties the relation snapshot logs."""

    AutoInference = True
    AutoSolve = True
    AddToDB = False


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

    async def check_sketch_fully_defined(self) -> _Result:
        state = next(self._states)
        self.sketch._status = {"under_defined": 2, "fully_defined": 3, "over_defined": 4}[state]
        return _Result({"definition_state": state, "raw_status": self.sketch._status})

    async def get_over_defining_relations(self) -> _Result:
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
    # Main's loop: an over-definition after a FIX ends escalation as "not
    # fully defined"; either way the native inventories are logged first.
    states = ["under_defined", "over_defined"] if after_fix else ["over_defined"]
    adapter = _SketchAdapter(states)
    message = "not fully defined .state='over_defined'" if after_fix else "sketch OVER-defined"
    phase = "(not_fully_defined)" if after_fix else "(over_defined)"

    with pytest.raises(RuntimeError, match=message):
        await _common.ensure_fully_defined(
            adapter, "stock gap sketch",
            fix_entities=["EquationCurve_1"], allow_fix_escalation=True,
        )

    error = next(line for line in sketch_logs["error"] if phase in line)
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
async def test_nonwhitelisted_sketch_stays_strict(sketch_logs) -> None:
    adapter = _SketchAdapter(["under_defined"])
    with pytest.raises(RuntimeError, match="legacy fix escalation disabled"):
        await _common.ensure_fully_defined(adapter, "gap", fix_entities=["EquationCurve_1"])
    assert adapter.fixed == []
    assert adapter.relations.calls == []


@pytest.mark.parametrize("teeth", [None, *range(6, 121, 6)])
def test_stock_gaps_are_authored_in_mains_cut_tooth_gap_order(teeth) -> None:
    """Every stock gap (drum, alignment pinion, each cone row) follows main's
    _gear.cut_tooth_gap: flanks base->tip first, lower ray, clearance arc,
    upper ray, then the floor from the upper foot to the lower foot. T006's
    DT6-FORM1 trochoid relief takes the below-base lines' place in the floor."""
    import dt_alignment_pinion_spec
    import dt_cone_gear_spec
    import dt_cylinder_gear_spec

    profiles = (
        [dt_cylinder_gear_spec.STOCK_FORM, dt_alignment_pinion_spec.STOCK_FORM]
        if teeth is None else [dt_cone_gear_spec.stock_form_profile(teeth)]
    )
    for profile in profiles:
        loop = profile.native_segments()
        ordered = profile.cut_order_native_segments()
        names = [s.name for s in ordered]
        roles = ["LowerFiniteFlank", "UpperFiniteFlank", "LowerClosingRay", "ClearanceArc",
                 "UpperClosingRay", "UpperBelowBase", "UpperRelief", "RootArc",
                 "LowerBelowBase", "LowerRelief"]
        assert names == [r for r in roles if r in {s.name for s in loop}]
        by = {s.name: s for s in ordered}
        upper_floor = by.get("UpperBelowBase", by.get("UpperRelief"))
        lower_floor = by.get("LowerBelowBase", by.get("LowerRelief"))
        lower_foot = (lower_floor or by["RootArc"]).end_mm
        upper_foot = (upper_floor or by["RootArc"]).start_mm
        joints = [
            (lower_foot, by["LowerFiniteFlank"].start_mm),
            (by["LowerFiniteFlank"].end_mm, by["LowerClosingRay"].start_mm),
            (by["LowerClosingRay"].end_mm, by["ClearanceArc"].start_mm),
            (by["ClearanceArc"].end_mm, by["UpperClosingRay"].start_mm),
            (by["UpperClosingRay"].end_mm, by["UpperFiniteFlank"].end_mm),
            (by["UpperFiniteFlank"].start_mm, upper_foot),
        ]
        if upper_floor is not None:
            joints += [(upper_floor.end_mm, by["RootArc"].start_mm),
                       (by["RootArc"].end_mm, lower_floor.start_mm)]
        for a, b in joints:
            assert a == pytest.approx(b, abs=1e-9)
