"""Console-level contracts for the repository build entry point."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


BUILD_PY = Path(__file__).resolve().parents[2] / "build.py"
SPEC = importlib.util.spec_from_file_location("build_entrypoint", BUILD_PY)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {BUILD_PY}")
build_entrypoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_entrypoint)


@pytest.mark.parametrize("verbosity", build_entrypoint._LEVELS)
def test_main_passes_doit_arguments_unchanged_and_sets_verbosity(
    monkeypatch: pytest.MonkeyPatch,
    verbosity: str,
) -> None:
    captured: list[list[str]] = []

    class FakeDoitMain:
        def run(self, args: list[str]) -> int:
            captured.append(args)
            return 17

    monkeypatch.delenv("HARMONIC_VERBOSITY", raising=False)
    monkeypatch.setattr(build_entrypoint, "DoitMain", FakeDoitMain)
    args = ["clean", "part:wheel_axle"]

    assert build_entrypoint.main(["--verbosity", verbosity, *args]) == 17
    assert captured == [args]
    assert build_entrypoint.os.environ["HARMONIC_VERBOSITY"] == verbosity


def test_main_defaults_to_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[str]] = []

    class FakeDoitMain:
        def run(self, args: list[str]) -> int:
            captured.append(args)
            return 0

    monkeypatch.delenv("HARMONIC_VERBOSITY", raising=False)
    monkeypatch.setattr(build_entrypoint, "DoitMain", FakeDoitMain)

    assert build_entrypoint.main(["check:config"]) == 0
    assert captured == [["check:config"]]
    assert build_entrypoint.os.environ["HARMONIC_VERBOSITY"] == "warning"


def test_main_forwards_explicit_reporter_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[list[str]] = []

    class FakeDoitMain:
        def run(self, args: list[str]) -> int:
            captured.append(args)
            return 0

    monkeypatch.setattr(build_entrypoint, "DoitMain", FakeDoitMain)
    args = ["--reporter", "console", "check:config"]

    assert build_entrypoint.main(["--verbosity", "warning", *args]) == 0
    assert captured == [args]
