"""A root pytest run never collects the vendored SolidworksMCP-python suite.

That suite can launch SolidWorks (its docs-discovery smoke test falls through
to the 3DEXPERIENCE Start-menu shortcut when nothing is running). On amet a
launch takes the licence farm worker w15 shares, so it must never run from here.
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


def _ini() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["tool"]["pytest"]["ini_options"]


def _testpaths() -> list[str]:
    return _ini()["testpaths"]


def test_bare_pytest_runs_only_this_repositorys_suites():
    for path in _testpaths():
        assert (ROOT / path).is_dir(), path
        assert not (ROOT / path).resolve().is_relative_to(ROOT / SUBMODULE), path


@pytest.mark.parametrize(
    "directory",
    [SUBMODULE, "references", ".git", ".venv", ".claude", "node_modules"],
)
def test_pytest_dot_does_not_recurse_into(directory):
    patterns = _ini()["norecursedirs"]
    assert any(fnmatch(directory, pattern) for pattern in patterns), directory


def test_pytest_reads_the_root_configuration(pytestconfig):
    assert Path(pytestconfig.inipath) == ROOT / "pyproject.toml"
    assert pytestconfig.getini("testpaths") == _testpaths()
    assert SUBMODULE in pytestconfig.getini("norecursedirs")
