"""The dev dependency must support the strict exception-group assertions."""

from pathlib import Path
import tomllib

from packaging.requirements import Requirement


def test_pytest_floor_excludes_versions_without_public_exception_group_matchers():
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = [Requirement(item) for item in project["dependency-groups"]["dev"]]
    requirement, = [item for item in requirements if item.name == "pytest"]
    # Both public matchers were introduced in pytest 8.4. The viewport tests
    # also exercise their complete failure diagnostics, including plain errors.
    assert "8.4.0" in requirement.specifier
    for version in ("8.0.0", "8.1.0", "8.2.0", "8.3.5"):
        assert version not in requirement.specifier

    locked = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    package, = [item for item in locked["package"] if item["name"] == project["project"]["name"]]
    pytest_requirement, = [
        item for item in package["metadata"]["requires-dev"]["dev"]
        if item["name"] == "pytest"
    ]
    assert pytest_requirement["specifier"] == str(requirement.specifier)
