"""Every root pytest module has a required, opt-in, or test-runner disposition.

Gate reach is derived from the actual commands produced by ``dodo.task_check``.
Discovery follows the root pytest paths recursively, keyed by repository-relative
path rather than basename. A new module must be enrolled or given a concrete
test-runner-only reason; there is no grandfathered orphan allowance.
"""

from __future__ import annotations

from fnmatch import fnmatch
import importlib.util
from pathlib import Path
import tomllib

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[1]

# These test root-runner/launcher infrastructure rather than CAD recipes. Keep
# their root-pytest invocation separate from the local CAD check commands.
TEST_RUNNER_ONLY = {
    "tests/test_solidworks_launch_guard.py": (
        "Exercises the root conftest process/launch refusal boundary; run with "
        "the contained root pytest runner, not a CAD recipe check."
    ),
    "tests/test_pytest_scope.py": (
        "Validates root pytest discovery and vendored-suite exclusions, not CAD output."
    ),
    "tests/test_farm_mode.py": (
        "Farm executor/CLI selection contracts belong to the root launcher suite."
    ),
    "tests/test_farm_launcher.py": (
        "Farm launcher submission, retries and output-handling contracts belong "
        "to the contained root launcher suite, not the offline CAD check."
    ),
    "tests/test_farm_checkout_drift.py": (
        "Worker checkout/identity drift contracts belong to the root launcher suite."
    ),
    "cad/comparisons/tools/test_pose_to_meshprobe.py": (
        "Comparison-tool pose conversion is not on the CAD build/release gate path; "
        "run explicitly or through root pytest."
    ),
}
OPT_IN = {
    "cad/scripts/test_verify_telemetry.py": (
        "check:verify_telemetry simulates calibrated COM latency to audit span "
        "shape; deliberately excluded from the every-build/release checks."
    ),
}


def _inventory(root: Path) -> set[str]:
    options = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"
    ]["pytest"]["ini_options"]
    excluded = options["norecursedirs"]
    return {
        path.relative_to(root).as_posix()
        for testpath in options["testpaths"]
        for path in (root / testpath).rglob("test_*.py")
        if not any(
            fnmatch(part, pattern)
            for part in path.relative_to(root).parts[:-1]
            for pattern in excluded
        )
    }


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collected_by_check_gates(dodo) -> dict[str, set[str]]:
    """Repository-relative module path -> gates that actually invoke pytest."""
    collected: dict[str, set[str]] = {}
    for task in dodo.task_check():
        _run, (cmd, *_rest) = task["actions"][0]
        if "-m" not in cmd or cmd[cmd.index("-m") + 1] != "pytest":
            continue
        for arg in cmd:
            path = Path(str(arg))
            if path.suffix != ".py" or not path.name.startswith("test_"):
                continue
            if not path.is_absolute():
                path = REPO_ROOT / path
            relative = path.resolve().relative_to(REPO_ROOT).as_posix()
            collected.setdefault(relative, set()).add(task["name"])
    return collected


def test_every_root_pytest_module_has_a_gate_disposition() -> None:
    dodo = _load_dodo()
    collected = _collected_by_check_gates(dodo)
    on_disk = _inventory(REPO_ROOT)
    required = set(dodo._CHECK_NAMES)
    optional = set(dodo._OPTIONAL_CHECK_NAMES)
    assert on_disk and collected and required and optional
    assert not required & optional
    assert set(collected) <= on_disk, "gates name tests outside maintained root discovery"
    default = {
        path for path, gates in collected.items() if gates & required
    }
    opt_in = set(collected) - default
    assert default, "no root tests execute under the required checks"
    assert opt_in == set(OPT_IN), (
        f"opt-in module dispositions drifted: {sorted(opt_in ^ set(OPT_IN))}"
    )
    assert all(collected[path] <= optional for path in opt_in)
    assert not set(TEST_RUNNER_ONLY) & set(collected), (
        "a test-runner-only module is now gated; remove its old disposition"
    )
    assert set(TEST_RUNNER_ONLY) <= on_disk, "stale test-runner-only dispositions"
    assert all(reason.strip() for reason in (*TEST_RUNNER_ONLY.values(), *OPT_IN.values()))
    orphans = sorted(on_disk - default - opt_in - set(TEST_RUNNER_ONLY))
    assert not orphans, (
        "root pytest modules with no default/opt-in/test-runner-only disposition: "
        f"{orphans}"
    )


def test_recursive_inventory_preserves_collisions_and_pytest_exclusions(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\n'
        'testpaths = ["cad/scripts", "tests"]\n'
        'norecursedirs = [".*", "references"]\n',
        encoding="utf-8",
    )
    maintained = {
        "cad/scripts/test_contract.py",
        "cad/scripts/diagnostics/test_contract.py",
        "tests/test_contract.py",
    }
    excluded = {
        "cad/scripts/references/test_contract.py",
        "cad/scripts/.scratch/test_contract.py",
    }
    for relative in maintained | excluded:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    assert _inventory(tmp_path) == maintained
