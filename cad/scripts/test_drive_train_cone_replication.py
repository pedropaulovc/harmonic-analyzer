from __future__ import annotations

import ast
import inspect

import pytest

import build_drive_train_assembly as drive


class _RebuildModel:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[bool] = []

    def ForceRebuild3(self, top_only: bool) -> object:
        self.calls.append(top_only)
        return self.result


class _Adapter:
    @staticmethod
    def _attempt(operation, *, default=None):
        try:
            return operation()
        except Exception:
            return default


def _function(name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(inspect.getsource(getattr(drive, name)))
    return next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _calls(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(item, ast.Call)
        and (
            (isinstance(item.func, ast.Name) and item.func.id == name)
            or (isinstance(item.func, ast.Attribute) and item.func.attr == name)
        )
        for item in ast.walk(node)
    )


def test_cone_replication_keeps_seed_plus_nineteen_copies() -> None:
    build = _function("build")
    seed = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "cone_gears"
    )
    assert isinstance(seed.value, ast.List) and len(seed.value.elts) == 1

    copy_loop = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.For) and _calls(node, "copy_with_mates")
    )
    assert isinstance(copy_loop.iter, ast.Call)
    assert (
        isinstance(copy_loop.iter.func, ast.Name)
        and copy_loop.iter.func.id == "range"
    )
    assert [
        arg.value for arg in copy_loop.iter.args if isinstance(arg, ast.Constant)
    ] == [1, 20]


def test_all_cone_switches_precede_force_rebuild_and_status_scan() -> None:
    build = _function("build")
    replication = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and any(
                isinstance(arg, ast.Constant) and arg.value == "cone.replicate"
                for arg in item.context_expr.args
            )
            for item in node.items
        )
    )
    copy_loop = next(
        statement
        for statement in replication.body
        if isinstance(statement, ast.For) and _calls(statement, "copy_with_mates")
    )
    assert any(
        isinstance(target, ast.Attribute)
        and target.attr == "ReferencedConfiguration"
        for node in ast.walk(copy_loop)
        if isinstance(node, ast.Assign)
        for target in node.targets
    )

    force = next(
        statement
        for statement in replication.body
        if _calls(statement, "_force_rebuild_after_cone_replication")
    )
    assert replication.body.index(copy_loop) < replication.body.index(force)

    replication_index = build.body.index(replication)
    status_scan_index = next(
        index
        for index, statement in enumerate(build.body)
        if index > replication_index
        and _calls(statement, "component_constrained_status")
    )
    assert replication_index < status_scan_index


def test_cone_replication_uses_one_authoritative_deep_force_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _RebuildModel(True)
    monkeypatch.setattr(
        drive,
        "whats_wrong",
        lambda *_: pytest.fail(
            "successful ForceRebuild3 must not enter fault reporting"
        ),
    )

    drive._force_rebuild_after_cone_replication(_Adapter(), model)

    assert model.calls == [False]
    helper = _function("_force_rebuild_after_cone_replication")
    assert sum(_calls(node, "ForceRebuild3") for node in helper.body) == 1
    assert not _calls(helper, "EditRebuild3")


@pytest.mark.parametrize("result", [False, None])
def test_cone_replication_rebuild_failure_reports_component_faults(
    monkeypatch: pytest.MonkeyPatch, result: object
) -> None:
    model = _RebuildModel(result)
    monkeypatch.setattr(
        drive,
        "whats_wrong",
        lambda *_: [("cone-gear-2", 1, False), ("under-defined", 2, True)],
    )

    with pytest.raises(RuntimeError) as raised:
        drive._force_rebuild_after_cone_replication(_Adapter(), model)

    assert model.calls == [False]
    message = str(raised.value)
    assert f"returned {result!r}" in message
    assert "cone-gear-2 [code=1]" in message
    assert "under-defined [code=2]" in message
