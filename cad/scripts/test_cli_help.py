"""Offline contracts for the cmdhelp v0.1 task inventory."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from doit import loader
from jsonschema import Draft202012Validator, FormatChecker

from harmonic_analyzer import cli
from harmonic_analyzer.cmdhelp import (
    BINARY,
    command_catalog,
    normalize_scope,
    render_json,
    render_markdown,
    schema_document,
    select_commands,
    selector_from_example,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = Path(__file__).resolve().parent / "fixtures" / "cmdhelp.schema.json"


def _load_dodo():
    spec = importlib.util.spec_from_file_location("cmdhelp_test_dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capability_discovery_is_exact_and_does_not_load_dodo(capsys):
    sys.modules.pop("harmonic_analyzer_dodo", None)

    assert cli.main(["--cmdhelp-capabilities"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "cmdhelp/0.1: text, md, json, llm\n"
    assert captured.err == ""
    assert "harmonic_analyzer_dodo" not in sys.modules


def test_full_json_matches_canonical_cmdhelp_schema():
    selection = select_commands((), None, "all")
    document = schema_document(selection)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    assert document["cmdhelp_version"] == "0.1"
    assert document["binary"] == BINARY
    assert "part:cone_gear" in document["commands"]
    assert "check:cli" in document["commands"]


def test_depth_and_scope_select_the_expected_detail():
    root = schema_document(select_commands((), None))
    assert root["commands"]
    assert all(":" not in selector for selector in root["commands"])
    assert all(set(command) == {"summary"} for command in root["commands"].values())

    parts = schema_document(select_commands(normalize_scope(["part"]), None))
    assert parts["commands"]
    assert all(selector.startswith("part:") for selector in parts["commands"])
    assert all(set(command) == {"summary"} for command in parts["commands"].values())

    leaf = schema_document(select_commands(normalize_scope(["part", "cone_gear"]), None))
    assert list(leaf["commands"]) == ["part:cone_gear"]
    assert "examples" in leaf["commands"]["part:cone_gear"]

    expanded = schema_document(select_commands((), 1))
    assert "part:cone_gear" in expanded["commands"]
    assert "examples" in expanded["commands"]["part:cone_gear"]


def test_markdown_and_json_are_deterministic():
    selection = select_commands((), 1)
    assert render_json(selection) == render_json(selection)
    assert render_markdown(selection) == render_markdown(selection)
    assert "## `harmonic-analyzer part:cone_gear`" in render_markdown(selection)


def test_every_canonical_example_selects_a_live_command():
    for command in command_catalog():
        for example, _note in command.examples:
            assert selector_from_example(example) is not None, example


def test_catalog_matches_public_doit_tasks_exactly():
    dodo = _load_dodo()
    actual = {task.name for task in loader.load_tasks(vars(dodo), allow_delayed=True)}
    documented = {command.selector for command in command_catalog()} - {"help"}
    internal = {
        "verify_soundness",
        *(f"verify_soundness:{stem}" for stem in dodo.ASSEMBLY_ORDER),
    }

    assert actual - documented == internal
    assert documented - actual == set()


def test_installed_entrypoint_emits_clean_json_outside_checkout(tmp_path):
    executable = Path(sys.executable).with_name(
        "harmonic-analyzer.exe" if os.name == "nt" else "harmonic-analyzer"
    )
    result = subprocess.run(
        [str(executable), "help", "--format", "json", "--depth", "1"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["binary"] == BINARY
    assert "part:cone_gear" in document["commands"]
    assert result.stderr == ""


def test_unknown_scope_and_negative_depth_fail_on_stderr(capsys):
    assert cli.main(["help", "not-a-task"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown help scope" in captured.err

    assert cli.main(["help", "--depth", "-1"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--depth must be zero or greater" in captured.err
