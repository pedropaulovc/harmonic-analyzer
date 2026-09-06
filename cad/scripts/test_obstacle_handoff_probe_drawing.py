"""Copy isolation and profiling contracts for the native A/B measurement probe."""

from pathlib import Path
from types import SimpleNamespace
import json

import pytest

import probe_callout_obstacle_handoff as control
from solidworks_mcp.adapters.solidworks import drawing as native_drawing


@pytest.mark.parametrize("outcome", ["success", "witness_failure"])
def test_layout_profile_is_retained_on_success_and_failure(
    monkeypatch, tmp_path, outcome
):
    def layout(*args):
        sum(range(10))
        if outcome == "witness_failure":
            raise RuntimeError("strict final witness rejected")

    monkeypatch.setattr(control, "_run_layout", layout)
    evidence = {}
    if outcome == "witness_failure":
        with pytest.raises(RuntimeError, match="strict final witness"):
            control._profiled_layout(
                None, {}, (), control.Mode.FRESH, evidence, tmp_path
            )
    if outcome == "success":
        control._profiled_layout(None, {}, (), control.Mode.FRESH, evidence, tmp_path)
    assert Path(evidence["profile"]["path"]).is_file()
    assert evidence["profile"]["total_calls"] > 0
    assert any(row["function"] == "layout" for row in evidence["profile"]["functions"])


def test_worker_requires_explicit_seat_before_run_build(monkeypatch, tmp_path):
    source = tmp_path / "source.SLDDRW"
    source.write_bytes(b"unmodified source")
    monkeypatch.setattr(control.sys, "argv", ["probe", str(source), "--worker"])
    monkeypatch.delenv("HARMONIC_COM_SEAT", raising=False)
    monkeypatch.setattr(
        control,
        "run_copy_diagnostic",
        lambda *_: pytest.fail("worker reached COM without seat"),
    )
    with pytest.raises(RuntimeError, match="machine-global COM seat"):
        control.main()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "none",
        "handoff_only",
        "wrong_copy",
        "source_mutation",
        "witness_failure",
        "missing_pdf",
        "reopen_semantics",
        "no_reads_saved",
    ],
)
async def test_ab_copies_preserve_originals_and_retain_failed_checkpoints(
    monkeypatch, tmp_path, change
):
    root = tmp_path / "cad"
    source, part = tmp_path / "original.SLDDRW", tmp_path / "source.SLDPRT"
    source.write_bytes(b"original drawing")
    part.write_bytes(b"original part")
    source_hash = control.hashlib.sha256(source.read_bytes()).hexdigest()
    paths, comparisons = [], []
    state = {"phase": "open"}
    from contextlib import nullcontext
    from unittest.mock import Mock

    adapter = SimpleNamespace(
        currentModel=None,
        swApp=object(),
        ownership=SimpleNamespace(
            register_directory=Mock(),
            register_source=Mock(),
            saving_as=lambda _: nullcontext(),
        ),
    )

    async def open_model(path):
        resolved = Path(path).resolve()
        assert resolved.is_relative_to(root / "out/reports")
        assert resolved not in (source, part)
        assert resolved.is_file()
        paths.append(resolved)
        state["phase"] = "reopened" if resolved.stem.endswith("-observed") else "open"
        actual = source if change == "wrong_copy" else resolved
        adapter.currentModel = SimpleNamespace(GetPathName=lambda: str(actual))
        return SimpleNamespace(is_success=True, data={})

    async def close_model(*, save):
        assert save is False
        assert Path(adapter.currentModel.GetPathName()) not in (source, part)
        adapter.currentModel = None
        return SimpleNamespace(is_success=True, data={})

    adapter.open_model, adapter.close_model = open_model, close_model
    view = SimpleNamespace(
        ReferencedDocument=SimpleNamespace(GetPathName=lambda: str(part))
    )

    def save_drawing(_adapter, target, *, pdf_path):
        current = Path(adapter.currentModel.GetPathName())
        output = Path(target)
        assert output != current  # Native SaveAs must not delete its open input.
        assert (
            output.parent == current.parent
            and output.parent.parent == root / "out/reports"
        )
        output.write_bytes(b"observed drawing")
        if change != "missing_pdf":
            Path(pdf_path).write_bytes(b"observed pdf")
        adapter.currentModel = SimpleNamespace(GetPathName=lambda: str(output))

    def run_layout(_adapter, views, notes, mode, row, directory):
        assert views == {"front": view} and notes == ()
        assert directory == paths[-1].parent
        row["full_measurement_total"] = (
            5 if mode is control.Mode.FRESH or change == "no_reads_saved" else 3
        )
        row["layout_seconds"] = 2 if mode is control.Mode.FRESH else 1
        if mode is control.Mode.HANDOFF:
            row["reused_obstacle_count"] = 2
        if change == "source_mutation":
            part.write_bytes(b"unintended native source save")
        if change == "witness_failure":
            raise RuntimeError("strict actual geometry failed")

    def semantics(_views):
        return {
            "native": "changed"
            if change == "reopen_semantics" and state["phase"] == "reopened"
            else "unchanged"
        }

    def compare(before, after, phase):
        assert before == after == {"geometry": "native", "basic": 1, "value": 0.012}
        comparisons.append(phase)

    monkeypatch.setattr(control, "CAD_ROOT", root)
    monkeypatch.setattr(control, "_context", lambda *_: (None, {"front": view}, ()))
    monkeypatch.setattr(control, "_semantic_fields", semantics)
    monkeypatch.setattr(control, "_profiled_layout", run_layout)
    monkeypatch.setattr(
        control,
        "snapshot",
        lambda _model, *, app: {"geometry": "native", "basic": 1, "value": 0.012},
    )
    monkeypatch.setattr(control, "compare", compare)
    monkeypatch.setattr(control, "layout", lambda *_: {"view": (0.1, 0.2)})
    monkeypatch.setattr(native_drawing, "save_drawing", save_drawing)
    success = change in ("none", "handoff_only")
    if not success:
        patterns = {
            "wrong_copy": "wrong obstacle copy",
            "source_mutation": "original source bytes",
            "witness_failure": "actual geometry failed",
            "missing_pdf": "missing or empty",
            "reopen_semantics": "save/reopen changed",
            "no_reads_saved": "exactly its recorded obstacle reads",
        }
        with pytest.raises(RuntimeError, match=patterns[change]):
            await control.probe(adapter, source)
    if success:
        modes = (
            (control.Mode.HANDOFF,) if change == "handoff_only" else tuple(control.Mode)
        )
        await control.probe(adapter, source, modes)
        assert len(paths) == 2 * len(modes) and len(set(paths)) == len(paths)
        assert len(comparisons) == (2 if change == "handoff_only" else 5)
    reports = list((root / "out/reports").glob("callout-handoff-*/handoff.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["stage"] == ("passed" if success else "failed")
    assert report["source_sha256"][str(source)] == source_hash
    assert report["source_unchanged"][str(source)] is True
    assert source.read_bytes() == b"original drawing"
    if change != "wrong_copy":
        assert adapter.currentModel is None
    if change == "none":
        assert report["measurement_reads_saved"] == 2
        assert report["layout_seconds_saved"] == 1
        assert all(report["source_unchanged"].values())
    if change == "handoff_only":
        assert report["selected_policies"] == ["handoff"]
        assert set(report["modes"]) == {"handoff"}
        assert report["modes"]["handoff"]["stage"] == "passed"
        assert "measurement_reads_saved" not in report
        assert "layout_seconds_saved" not in report
        assert all(report["source_unchanged"].values())


@pytest.mark.asyncio
@pytest.mark.parametrize("modes", [(), ("handoff",), (control.Mode.HANDOFF,) * 2])
async def test_invalid_policy_selection_fails_before_copy_or_com(modes):
    with pytest.raises(ValueError, match="distinct explicit"):
        await control.probe(None, None, modes)
