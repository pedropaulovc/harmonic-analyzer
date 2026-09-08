"""Rack finish experiment CLI conflicts reject before native imports or writes."""

import builtins
import importlib.util
from pathlib import Path
import sys

import pytest


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    path = Path(__file__).with_name("probe_vm2_rack_finish_attachment.py")
    spec = importlib.util.spec_from_file_location("vm2_rack_finish_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    imports = []
    original_import = builtins.__import__

    def prohibit_native_import(name, *args, **kwargs):
        if name in {"_common", "_gear_drawing_entities", "dodo", "diagnostics._owned_native_session",
                    "diagnostics.probe_vm2_datum_lifecycle"}:
            imports.append(name)
            raise AssertionError(f"CLI reached native execution import: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", prohibit_native_import)
    return module, imports


INVALID_COMBINATIONS = [
    (["--point-trials"], "--point-trials requires --reattach-failed"),
    (["--fresh-insert"], "--fresh-insert requires --saved-candidate"),
    (["--fresh-insert", "--saved-candidate", "CANDIDATE", "--reattach-failed"],
     "excludes --reattach-failed"),
    (["--save-reopen"], "--save-reopen requires --saved-candidate and a placement experiment"),
    (["--save-reopen", "--saved-candidate", "CANDIDATE"], "a placement experiment"),
    (["--save-reopen", "--saved-candidate", "CANDIDATE", "--reattach-failed"], "a placement experiment"),
    (["--save-reopen", "--point-trials", "--reattach-failed"], "--save-reopen requires --saved-candidate"),
    (["--fresh-insert", "--save-reopen"], "--fresh-insert requires --saved-candidate"),
    (["--fresh-insert", "--saved-candidate", "CANDIDATE", "--save-reopen", "--close-failed"],
     "--save-reopen excludes --close-failed"),
    (["--point-trials", "--reattach-failed", "--saved-candidate", "CANDIDATE", "--save-reopen", "--close-failed"],
     "--save-reopen excludes --close-failed"),
    (["--fresh-insert", "--point-trials", "--saved-candidate", "CANDIDATE"],
     "--point-trials requires --reattach-failed"),
    (["--fresh-insert", "--point-trials", "--reattach-failed", "--saved-candidate", "CANDIDATE"],
     "excludes --reattach-failed"),
]


def render_flags(flags, candidate, spelling):
    result = [str(candidate) if value == "CANDIDATE" else value for value in flags]
    if spelling == "equals" and "--saved-candidate" in result:
        index = result.index("--saved-candidate")
        result[index:index + 2] = [f"--saved-candidate={candidate}"]
    return result


@pytest.mark.parametrize("spelling", ["separate", "equals"])
@pytest.mark.parametrize("flags, message", INVALID_COMBINATIONS)
def test_conflicting_flags_reject_before_com_witness_read_or_output(
    probe, monkeypatch, tmp_path, capsys, spelling, flags, message,
):
    module, imports = probe
    witness = tmp_path / "missing-witness.json"
    candidate = tmp_path / "missing-candidate.SLDDRW"
    output = tmp_path / "never-created" / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["probe", str(witness), str(output),
                                      *render_flags(flags, candidate, spelling)])
    # Deliberately supply no valid files, environment or COM session. Argparse
    # must reject the mode conflict before even resolving the missing witness.
    with pytest.raises(SystemExit) as result:
        module.main()
    assert result.value.code == 2
    assert message in capsys.readouterr().err
    assert imports == []
    assert not output.exists()
    assert not output.parent.exists()
    assert not witness.exists()
    assert not candidate.exists()


@pytest.mark.parametrize("flags", [
    [],
    ["--fresh-insert", "--saved-candidate", "CANDIDATE"],
    ["--fresh-insert", "--saved-candidate", "CANDIDATE", "--save-reopen"],
    ["--reattach-failed", "--point-trials", "--saved-candidate", "CANDIDATE", "--save-reopen"],
])
def test_supported_combinations_reach_input_validation_without_com(
    probe, monkeypatch, tmp_path, flags,
):
    module, imports = probe
    witness = tmp_path / "missing-witness.json"
    output = tmp_path / "never-created" / "receipt.json"
    candidate = tmp_path / "candidate.SLDDRW"
    monkeypatch.setattr(sys, "argv", ["probe", str(witness), str(output),
                                      *render_flags(flags, candidate, "separate")])
    with pytest.raises(FileNotFoundError):
        module.main()
    assert imports == []
    assert not output.parent.exists()


def test_help_documents_current_experiment_modes(probe, monkeypatch, capsys):
    module, imports = probe
    monkeypatch.setattr(sys, "argv", ["probe", "--help"])
    with pytest.raises(SystemExit) as result:
        module.main()
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    for flag in ("--fresh-insert", "--saved-candidate", "--save-reopen", "--reattach-failed", "--point-trials", "--close-failed"):
        assert flag in help_text
    assert imports == []


@pytest.mark.parametrize("spelling", ["separate", "equals"])
@pytest.mark.parametrize("relative", [
    "other-checkout/candidate.SLDDRW",
    "cad/out/slddrw/rack-pinion.SLDDRW",
    "cad/out/reports/candidate.SLDDRW",
    "cad/out/reports/datum-placement-other/candidate.SLDDRW",
    "cad/out/reports/datum-placement/candidate.json",
])
def test_unowned_or_wrong_suffix_candidate_rejected_before_com_or_output(
    probe, monkeypatch, tmp_path, spelling, relative,
):
    module, imports = probe
    monkeypatch.setattr(module, "ROOT", tmp_path.resolve())
    witness = tmp_path / "cad/out/reports/inventory.json"
    witness.parent.mkdir(parents=True)
    witness.write_text("{}", encoding="utf-8")
    candidate = tmp_path / relative
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_bytes(b"test candidate")
    output = tmp_path / "cad/out/reports/new-result/receipt.json"
    flags = render_flags(["--fresh-insert", "--saved-candidate", "CANDIDATE", "--save-reopen"],
                         candidate, spelling)
    monkeypatch.setattr(sys, "argv", ["probe", str(witness), str(output), *flags])
    with pytest.raises(RuntimeError, match="candidate must be an own diagnostic drawing copy"):
        module.main()
    assert imports == []
    assert not output.parent.exists()
    assert candidate.read_bytes() == b"test candidate"
    assert witness.read_text(encoding="utf-8") == "{}"


@pytest.mark.parametrize("spelling", ["separate", "equals"])
def test_missing_saved_candidate_rejected_before_com_or_output(probe, monkeypatch, tmp_path, spelling):
    module, imports = probe
    monkeypatch.setattr(module, "ROOT", tmp_path.resolve())
    witness = tmp_path / "cad/out/reports/inventory.json"
    witness.parent.mkdir(parents=True)
    witness.write_text("{}", encoding="utf-8")
    candidate = tmp_path / "cad/out/reports/datum-placement/missing.SLDDRW"
    output = tmp_path / "cad/out/reports/new-result/receipt.json"
    flags = render_flags(["--fresh-insert", "--saved-candidate", "CANDIDATE"], candidate, spelling)
    monkeypatch.setattr(sys, "argv", ["probe", str(witness), str(output), *flags])
    with pytest.raises(FileNotFoundError):
        module.main()
    assert imports == []
    assert not output.parent.exists()
    assert not candidate.exists()


@pytest.mark.parametrize("suffix", ["SLDDRW", "slddrw"])
def test_owned_candidate_passes_path_guard_and_reaches_environment_guard(probe, monkeypatch, tmp_path, suffix):
    module, imports = probe
    monkeypatch.setattr(module, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    witness = tmp_path / "cad/out/reports/inventory.json"
    witness.parent.mkdir(parents=True)
    witness.write_text("{}", encoding="utf-8")
    candidate = tmp_path / f"cad/out/reports/datum-placement/candidate.{suffix}"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"test owned candidate")
    output = tmp_path / "cad/out/reports/new-result/receipt.json"
    monkeypatch.setattr(sys, "argv", ["probe", str(witness), str(output), "--fresh-insert",
                                      "--saved-candidate", str(candidate), "--save-reopen"])
    with pytest.raises(RuntimeError, match="own uv and attach-only mode required"):
        module.main()
    assert imports == []
    assert not output.parent.exists()
