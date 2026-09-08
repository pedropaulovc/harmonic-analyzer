"""Retired external-worktree closure arguments fail before native execution."""

from __future__ import annotations

import builtins
import importlib.util
from pathlib import Path
import sys

import pytest


@pytest.fixture
def ownership(monkeypatch):
    # Loading this CLI is read-only. Restore its path insertion after each test.
    monkeypatch.setattr(sys, "path", list(sys.path))
    path = Path(__file__).with_name("probe_vm2_datum_ownership.py")
    spec = importlib.util.spec_from_file_location("vm2_ownership_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    imports = []
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"_common", "dodo", "diagnostics._owned_native_session"}:
            imports.append(name)
            raise AssertionError(f"CLI reached native execution import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    return module, imports


@pytest.mark.parametrize("worker", ("parent", "worker"))
@pytest.mark.parametrize("spelling", ("separate", "equals", "alongside_probe"))
def test_retired_failure_closure_rejected_before_com_or_output(
    ownership, monkeypatch, tmp_path, capsys, worker, spelling,
):
    module, imports = ownership
    output = tmp_path / "never-created" / "receipt.json"
    witness = tmp_path / "absent-witness.json"
    args = ["ownership", str(output)]
    if worker == "worker":
        args.append("--worker")
    if spelling == "equals":
        args.append(f"--close-owned-failure-from={witness}")
    if spelling != "equals":
        args.extend(["--close-owned-failure-from", str(witness)])
    if spelling == "alongside_probe":
        args.extend(["--close-owned-probe-from", str(witness)])
    monkeypatch.setattr(sys, "argv", args)
    # No valid environment/PID/witness is supplied: argparse must reject the
    # retired action before those checks or any native module import.
    with pytest.raises(SystemExit) as result:
        module.main()
    assert result.value.code == 2
    error = capsys.readouterr().err
    assert "unrecognized arguments" in error
    assert "--close-owned-failure-from" in error
    assert imports == []
    assert not output.exists()
    assert not output.parent.exists()
    assert not witness.exists()


def test_help_retains_only_current_closure_options(
    ownership, monkeypatch, capsys,
):
    module, imports = ownership
    monkeypatch.setattr(sys, "argv", ["ownership", "--help"])
    with pytest.raises(SystemExit) as result:
        module.main()
    assert result.value.code == 0
    output = capsys.readouterr().out
    assert "--close-owned-probe-from" in output
    assert "--close-production-from" in output
    assert "--inventory-witness" in output
    assert "--close-owned-failure-from" not in output
    assert imports == []
