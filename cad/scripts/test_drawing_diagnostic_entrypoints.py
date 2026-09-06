"""New copy diagnostics cannot enter the production document-clearing runner."""

import ast
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).parent
MIGRATED = (
    "probe_drawing_annotation_performance.py",
    "diagnostics/probe_drawing_attachments.py",
    "diagnostics/benchmark_drawing_recipes.py",
    "probe_callout_obstacle_handoff.py",
    "probe_drawing_annotation_bounds.py",
    "probe_drawing_annotation_layout.py",
    "probe_drawing_dimension_selection.py",
    "probe_drawing_mixed_commands.py",
    "probe_drawing_primitive_annotations.py",
    "probe_drawing_right_gtol_column.py",
    "probe_drawing_thread_ink.py",
    "probe_native_gtol_selection.py",
)


@pytest.mark.parametrize("filename", MIGRATED)
def test_copy_entrypoint_uses_owned_runner_and_guards_parent_preflight(filename):
    tree = ast.parse((SCRIPTS / filename).read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    names = [
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in calls
        if isinstance(node.func, (ast.Name, ast.Attribute))
    ]
    assert "run_build" not in names
    bodies = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"main", "probe", "benchmark"}
    ]
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "CloseAllDocuments"
        for body in bodies
        for node in ast.walk(body)
    )
    assert "run_copy_diagnostic" in names
    main = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    parent = next(
        node
        for node in ast.walk(main)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.operand, ast.Attribute)
        and node.test.operand.attr == "worker"
    )
    first = parent.body[0]
    assert isinstance(first, ast.Expr)
    assert isinstance(first.value, ast.Call)
    assert first.value.func.id == "require_owned_diagnostic_environment"
