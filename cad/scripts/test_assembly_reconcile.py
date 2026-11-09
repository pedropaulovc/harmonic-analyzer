"""Pure regression coverage of the deliberately closed experimental mate planner."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from diagnostics._assembly_reconcile import plan, recipe

SCRIPT = Path(__file__).resolve().parent / "diagnostics" / "benchmark_assembly_reconcile.py"


def test_identical_serialized_recipe_is_noop():
    before = recipe()
    result = plan(before, json.loads(json.dumps(before)))
    assert result.decision == "noop"
    assert result.edits == ()


def test_distance_change_is_the_only_edit_without_mutating_inputs():
    before = recipe(30)
    after = recipe(40)
    snapshots = copy.deepcopy((before, after))
    result = plan(before, after)
    assert result.decision == "incremental"
    assert result.edits == (("distance", 40.0),)
    assert (before, after) == snapshots


@pytest.mark.parametrize("change", [
    lambda value: value.update(schema=2),
    lambda value: value["child"]["parameters_mm"].update(diameter=24.0),
    lambda value: value["child"]["features"][1].update(operation="through_all"),
    lambda value: value["configurations"].update(child="Other"),
    lambda value: value["configurations"].update(assembly="Other"),
    lambda value: value["components"].reverse(),
    lambda value: value["components"][1].update(fixed=True),
    lambda value: value["components"].append(copy.deepcopy(value["components"][1])),
    lambda value: value["mates"].reverse(),
    lambda value: value["mates"].pop(),
    lambda value: value["mates"].append(copy.deepcopy(value["mates"][0])),
    lambda value: value["mates"][0].update(name="Coincident1"),
    lambda value: value["mates"][0].update(base_plane="Front Plane"),
    lambda value: value["mates"][1].update(alignment="anti_aligned"),
    lambda value: value["mates"][2].update(flip=not value["mates"][2]["flip"]),
    lambda value: value["mates"][2].update(type="MateCoincident"),
    lambda value: value["mates"][2].update(unsupported_option=True),
    lambda value: value["dimensions"].update(distance="D1@OtherMate"),
])
def test_structural_change_refuses_entire_parameter_edit(change):
    after = recipe(40)
    change(after)
    result = plan(recipe(30), after)
    assert result.decision == "full_build"
    assert result.edits == ()  # never leak partial edits from a refused plan


def test_matching_but_unsupported_structures_do_not_become_noop():
    unsupported = recipe()
    unsupported["mates"][2]["flip"] = not unsupported["mates"][2]["flip"]
    result = plan(unsupported, copy.deepcopy(unsupported))
    assert result.decision == "full_build"
    assert result.edits == ()


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "40", None])
def test_invalid_distance_fails_before_any_edit_plan(value):
    after = recipe()
    after["parameters_mm"]["distance"] = value
    with pytest.raises(ValueError, match="finite positive"):
        plan(recipe(), after)


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(unknown=True),
    lambda value: value.pop("mates"),
    lambda value: value["parameters_mm"].update(extra=1),
    lambda value: value["parameters_mm"].pop("distance"),
    lambda value: value["child"].pop("features"),
    lambda value: value["child"]["parameters_mm"].update(depth=0),
])
def test_malformed_recipe_is_not_silently_treated_as_full_build(mutate):
    after = recipe()
    mutate(after)
    with pytest.raises(ValueError):
        plan(recipe(), after)


@pytest.mark.parametrize("value", [None, [], "recipe"])
def test_non_object_recipe_fails(value):
    with pytest.raises(ValueError):
        plan(recipe(), value)


def test_recipe_instances_do_not_share_structural_containers():
    first = recipe()
    declared_flip = first["mates"][2]["flip"]
    first["mates"][2]["flip"] = not declared_flip
    first["components"][0]["initial_translation_mm"].append(1.0)
    first["child"]["features"][1]["depends_on"].clear()
    second = recipe()
    assert second["mates"][2]["flip"] is declared_flip
    assert second["components"][0]["initial_translation_mm"] == [0.0, 0.0, 0.0]
    assert second["child"]["features"][1]["depends_on"] == ["profile"]


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          env=env, timeout=120, check=False)


def _without_seat() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("HARMONIC_COM_SEAT", None)
    return env


def test_help_loads_no_native_bindings():
    probe = (
        "import runpy, sys; sys.argv = [sys.argv[1], '--help']\n"
        "try:\n    runpy.run_path(sys.argv[0], run_name='__main__')\n"
        "except SystemExit as exit:\n    assert exit.code == 0, exit.code\n"
        "native = sorted(m for m in sys.modules if m.split('.')[0] in "
        "{'win32com', 'pythoncom', 'pywintypes', 'solidworks_mcp', '_session', '_com'})\n"
        "assert not native, native\n"
    )
    result = subprocess.run([sys.executable, "-c", probe, str(SCRIPT)], capture_output=True, text=True,
                            env=_without_seat(), timeout=120, check=False)
    assert result.returncode == 0, result.stderr
    assert "benchmark" in result.stdout and "plan" in result.stdout


def test_plan_cli_reads_persisted_manifest(tmp_path):
    manifest = tmp_path / "baseline-manifest.json"
    target = tmp_path / "target-recipe.json"
    manifest.write_text(json.dumps({"recipe": recipe(30)}), encoding="utf-8")
    target.write_text(json.dumps(recipe(40)), encoding="utf-8")
    result = _run("plan", str(manifest), str(target), env=_without_seat())
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"decision": "incremental", "reason": "supported mate dimension edit",
                                         "edits": [["distance", 40.0]]}


def test_plan_cli_rejects_malformed_target(tmp_path):
    manifest = tmp_path / "baseline-manifest.json"
    target = tmp_path / "target-recipe.json"
    manifest.write_text(json.dumps({"recipe": recipe(30)}), encoding="utf-8")
    malformed = recipe(40)
    malformed["parameters_mm"]["distance"] = -5
    target.write_text(json.dumps(malformed), encoding="utf-8")
    result = _run("plan", str(manifest), str(target), env=_without_seat())
    assert result.returncode != 0
    assert "finite positive" in result.stderr


def test_benchmark_refuses_standalone_launch_before_native_import():
    result = _run("benchmark", env=_without_seat())
    assert result.returncode != 0
    assert "canonical verify:assembly_reconcile task" in result.stderr
