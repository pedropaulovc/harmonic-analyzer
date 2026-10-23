"""Offline CAD tests and selected execution regressions have real check:* coverage.

``dodo`` enrolls tests explicitly (plus the ``test_*_drawing.py`` glob), so a new
test file that nobody enrolls passes in the local suite and never runs in a
``doit`` build -- a green gate that checks nothing.  Codex on #844 and #814:
``test_mirror_retirement_expectations.py`` shipped that way.  This guard reads
the pytest arguments of every ``check:*`` task and fails on any ``test_*.py``
that none of them collects, unless it is exempted below with a reason.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[1]
_SCAN_ANCHORS = frozenset({"test_check_gate_enrollment.py", "test_dodo_recipe.py"})
# Retain the existing root regressions and add only selected execution.
_ROOT_REGRESSIONS = frozenset(
    {
        "tests/test_saved_display_data.py",
        "tests/test_solidworks_launch_guard.py",
        "tests/test_selected_execution.py",
    }
)
_REQUIRED_RECIPE_INPUTS = _ROOT_REGRESSIONS | {
    "conftest.py",
    "build.py",
    "dodo.py",
    "tests/_child_guard/sitecustomize.py",
    "tests/_child_guard/harmonic_solidworks_guard.py",
    "cad/scripts/test_selected_factories.py",
    "cad/scripts/_selected_execution.py",
    "cad/scripts/_buildgraph.py",
    "cad/scripts/_local_check.py",
    "cad/scripts/test_supplier_native_contracts.py",
    "cad/scripts/test_supplier_native_repair.py",
    "cad/scripts/test_supplier_top_text_shelves.py",
    "cad/scripts/test_supplier_washer_native_paint.json",
    "cad/scripts/testdata/supplier_top_r44.json",
}

# Test files that deliberately run in no check:* gate, each with its reason.
EXEMPT: dict[str, str] = {}

# Pre-existing orphans found when this guard landed (all on main before #844).
# Main assigns their triage (enroll, or move to EXEMPT with a reason); until
# then they are listed here so the guard fails only on NEW orphans.
PENDING_TRIAGE: frozenset[str] = frozenset(
    {
        "test_base_serial.py",
        "test_channel_installation_cascade.py",
        "test_diag_dump_part.py",
        "test_face_identity_diff.py",
        "test_frame_fastener_fit.py",
        "test_hole_spec.py",
        "test_holes_face_selection.py",
        "test_layout_geometry.py",
        "test_machinist_review_eval.py",
        "test_motion_study_default_free_pen.py",
        "test_named_views.py",
        "test_or_flag_fallback_names.py",
        "test_owned_assembly_health_session.py",
        "test_stock_spring_mounts.py",
        "test_targeted_model_items.py",
        "test_vm2_rack_source_save.py",
    }
)


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _offline_test_names(pattern: str = "test_*.py") -> set[str]:
    paths = tuple(SCRIPTS.glob(pattern))
    assert all(path.parent == SCRIPTS for path in paths), (
        "enrollment scan must inspect top-level cad/scripts tests"
    )
    names = {path.name for path in paths}
    assert _SCAN_ANCHORS <= names, (
        "enrollment scan missed required source anchors: "
        f"{sorted(_SCAN_ANCHORS - names)}"
    )
    return names


def _collected_by_check_gates() -> dict[str, list[str]]:
    """Test file -> gates that collect it, auditing selected recipe inputs too."""
    collected: dict[str, list[str]] = {}
    dodo = _load_dodo()
    for task in dodo.task_check():
        _run, (cmd, *_rest) = task["actions"][0]
        if _run is not dodo._run_stamped:
            continue
        if task["name"] == "recipe":
            inputs = {str(Path(path).resolve()) for path in task["file_dep"]}
            missing = sorted(
                path
                for path in _REQUIRED_RECIPE_INPUTS
                if str((REPO_ROOT / path).resolve()) not in inputs
            )
            assert not missing, f"check:recipe omits runtime input files: {missing}"
            root_tests = [
                path.relative_to(REPO_ROOT).as_posix()
                for arg in cmd
                if (path := Path(str(arg)).resolve()).parent == REPO_ROOT / "tests"
                and path.suffix == ".py" and path.name.startswith("test_")
            ]
            assert set(root_tests) == _ROOT_REGRESSIONS, (
                "check:recipe must retain baseline root tests and add only selected "
                f"execution: {sorted(set(root_tests) ^ _ROOT_REGRESSIONS)}"
            )
            assert len(root_tests) == len(_ROOT_REGRESSIONS), (
                "check:recipe must collect each root regression exactly once"
            )
            factory = SCRIPTS / "test_selected_factories.py"
            assert sum(Path(str(arg)).resolve() == factory for arg in cmd) == 1, (
                "check:recipe must collect selected factory coverage exactly once"
            )
            assert str((REPO_ROOT / "tests" / "test_preparation_publication.py").resolve()) not in inputs, (
                "selected execution must not depend on preparation/publication coverage"
            )
        for arg in cmd:
            path = Path(str(arg)).resolve()
            if path.suffix != ".py" or not path.name.startswith("test_"):
                continue
            if path.parent == SCRIPTS:
                key = path.name
            elif path.is_relative_to(REPO_ROOT):
                key = path.relative_to(REPO_ROOT).as_posix()
                if key not in _ROOT_REGRESSIONS:
                    continue
            else:
                continue
            collected.setdefault(key, []).append(task["name"])
    return collected


def test_every_offline_test_file_runs_in_a_check_gate() -> None:
    collected = _collected_by_check_gates()
    on_disk = _offline_test_names()
    orphans = sorted(on_disk - set(collected) - set(EXEMPT) - PENDING_TRIAGE)
    assert not orphans, (
        "test files no check:* gate collects (enroll them in dodo.task_check, "
        f"or exempt them with a reason): {orphans}"
    )
    for relative in sorted(_ROOT_REGRESSIONS):
        assert (REPO_ROOT / relative).is_file(), f"missing root regression: {relative}"
        assert "recipe" in collected.get(relative, []), (
            f"check:recipe does not collect required root regression: {relative}"
        )


def test_exemptions_name_real_uncollected_files() -> None:
    collected = _collected_by_check_gates()
    on_disk = _offline_test_names()
    listed = set(EXEMPT) | PENDING_TRIAGE
    assert not (listed - on_disk), (
        f"exempted files that no longer exist: {sorted(listed - on_disk)}"
    )
    assert not (listed & set(collected)), (
        f"exempted files a gate now collects -- drop them: {sorted(listed & set(collected))}"
    )
    assert all(reason.strip() for reason in EXEMPT.values())
    assert not (set(EXEMPT) & PENDING_TRIAGE)


@pytest.mark.parametrize(
    "pattern",
    ["__missing_enrollment_tests__/test_*.py", "*/test_*.py"],
)
def test_enrollment_scan_rejects_empty_or_deeper_patterns(pattern) -> None:
    with pytest.raises(AssertionError, match="enrollment scan"):
        _offline_test_names(pattern)
