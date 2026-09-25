"""A root pytest run never collects the vendored SolidworksMCP-python suite.

That suite can launch SolidWorks (its docs-discovery smoke test falls through
to the 3DEXPERIENCE Start-menu shortcut when nothing is running). On amet a
launch takes the licence farm worker w6 shares, so it must never run from here.
A bare ``pytest`` uses ``testpaths``; ``pytest .`` names the root explicitly
and is kept out only by ``norecursedirs``. Both are checked, as pytest itself
read them.
"""

import tomllib
from fnmatch import fnmatch
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = "SolidworksMCP-python"
EXPECTED_TESTPATHS = ["cad/scripts", "cad/comparisons/tools", "tests"]


def _ini() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["tool"]["pytest"]["ini_options"]


def test_bare_pytest_runs_only_this_repositorys_suites():
    assert _ini()["testpaths"] == EXPECTED_TESTPATHS
    for path in EXPECTED_TESTPATHS:
        assert (ROOT / path).is_dir(), path
        assert not path.startswith(SUBMODULE)


@pytest.mark.parametrize(
    "directory",
    [SUBMODULE, "references", ".git", ".venv", ".claude", "node_modules"],
)
def test_pytest_dot_does_not_recurse_into(directory):
    patterns = _ini()["norecursedirs"]
    assert any(fnmatch(directory, pattern) for pattern in patterns), directory


def test_pytest_reads_the_root_configuration(pytestconfig):
    assert Path(pytestconfig.inipath) == ROOT / "pyproject.toml"
    assert pytestconfig.getini("testpaths") == EXPECTED_TESTPATHS
    assert SUBMODULE in pytestconfig.getini("norecursedirs")
