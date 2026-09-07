"""The static recount's CLI correctness check survives Python optimization."""

from pathlib import Path
import os
import subprocess
import sys

import pytest


RECOUNT = (
    Path(__file__).resolve().parents[1]
    / "docs/pipeline/recount-coordinate-selections.py"
)


def _fixture(root, *, registry_count, coordinate_count):
    scripts = root / "cad/scripts"
    scripts.mkdir(parents=True)
    entries = [
        f"DrawingSpec(name='recipe_{index:02}', script_name='{script}.py')"
        for index in range(registry_count)
        for script in ["coordinate" if index < coordinate_count else "empty"]
    ]
    (scripts / "_drawing_registry.py").write_text(
        "DRAWINGS = (" + ",".join(entries) + ")\n", encoding="utf-8"
    )
    (scripts / "coordinate.py").write_text("add_edge_dimension()\n", encoding="utf-8")
    (scripts / "empty.py").write_text("pass\n", encoding="utf-8")


def _run(root, flags):
    environment = dict(os.environ)
    environment.pop("PYTHONOPTIMIZE", None)
    return subprocess.run(
        [sys.executable, *flags, "-B", str(RECOUNT), "--root", str(root)],
        capture_output=True, text=True, encoding="utf-8", check=False,
        env=environment, timeout=20,
    )


@pytest.mark.parametrize("flags", [(), ("-O",)], ids=["normal", "optimized"])
@pytest.mark.parametrize("registry_count,coordinate_count", [(91, 43), (92, 42)])
def test_count_drift_fails_with_observed_counts(
    tmp_path, flags, registry_count, coordinate_count
):
    _fixture(tmp_path, registry_count=registry_count, coordinate_count=coordinate_count)
    result = _run(tmp_path, flags)
    assert result.returncode != 0
    assert "expected registry=92 and coordinate_recipes=43" in result.stderr
    assert (
        f"observed registry={registry_count} and coordinate_recipes={coordinate_count}"
        in result.stderr
    )
    assert f"Registry: {registry_count}" in result.stdout
    assert f"Coordinate union: {coordinate_count}" in result.stdout


def test_matching_inventory_stdout_is_identical_with_optimization(tmp_path):
    _fixture(tmp_path, registry_count=92, coordinate_count=43)
    normal, optimized = _run(tmp_path, ()), _run(tmp_path, ("-O",))
    assert normal.returncode == optimized.returncode == 0
    assert normal.stderr == optimized.stderr == ""
    assert normal.stdout == optimized.stdout
    assert "Registry: 92 {'part': 92}" in normal.stdout
    assert "Coordinate union: 43\n" in normal.stdout
    assert "add_edge_dimension sites 43 recipes 43\n" in normal.stdout
