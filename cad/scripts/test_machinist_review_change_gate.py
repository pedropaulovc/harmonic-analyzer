"""Behavior of the shadow drawing-change gate on small generated PDFs.

Both judge variants run their real sessions; only the reviewer CLI boundary
(``machinist_review._run_reviewer``) is faked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import machinist_review as mr
import machinist_review_change_gate as gate
from test_machinist_review import _claude_stdout, _flag, _text_pdf
from test_machinist_review_precheck import _decision, _Reviewer

ChangeVerdict = gate.ChangeVerdict
GateStage = gate.GateStage


def _sheet(path: Path, *, x: float = 100.0, value: str = "12.50") -> Path:
    return _text_pdf(path, [(x, 700.0, value), (100.0, 600.0, "BREAK EDGES")])


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> _Reviewer:
    reviewer = _Reviewer(_decision("skip", "rendering_noise"))
    monkeypatch.setattr(mr, "_run_reviewer", reviewer)
    return reviewer


class _SideBySide:
    """Fake routed-Claude result: views every sheet, then returns ``answer``."""

    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> Any:
        config = json.loads(
            Path(_flag(command, "--mcp-config")).read_text(encoding="utf-8")
        )
        sheets = [
            arg
            for arg in config["mcpServers"]["sheets"]["args"][1:]
            if arg != "--preserve-color"
        ]
        self.calls.append(
            {"command": list(command), "prompt": kwargs["input"], "sheets": sheets}
        )
        if isinstance(self.answer, Exception):
            raise self.answer
        stdout = _claude_stdout(len(sheets), self.answer)
        return mr.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


def _gate(
    tmp_path: Path,
    before: Path,
    after: Path,
    *,
    kind: str = "part",
    layouts: tuple[Path, Path] | None = None,
    variant: gate.JudgeVariant = gate.JudgeVariant.PRECHECK,
) -> gate.GateResult:
    return gate.run_gate(
        before,
        after,
        name="sample",
        kind=kind,
        out_dir=tmp_path / "out",
        layouts=layouts,
        judge=gate.JudgeSettings(variant, retries=0),
    )


def _moved(tmp_path: Path) -> tuple[Path, Path]:
    return _sheet(tmp_path / "before.pdf", x=100.0), _sheet(
        tmp_path / "after.pdf", x=160.0
    )


def _layout(path: Path, findings: list[dict[str, Any]]) -> Path:
    path.write_text(json.dumps({"schema": 1, "findings": findings}), encoding="utf-8")
    return path


def _finding(at_mm: list[float]) -> dict[str, Any]:
    return {
        "kind": "text_clearance",
        "sheet": "Sheet1",
        "a": "D1@Drawing View1",
        "b": "Note2",
        "detail": "text too close",
        "at_mm": at_mm,
    }


@pytest.fixture
def spans(monkeypatch: pytest.MonkeyPatch):
    """Capture real SDK spans without sending telemetry to a collector."""
    for name in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    ):
        monkeypatch.setenv(name, "")
    gate._telemetry.configure(force=True)
    exporter = InMemorySpanExporter()
    cast(
        TracerProvider, gate._telemetry.trace.get_tracer_provider()
    ).add_span_processor(SimpleSpanProcessor(exporter))
    yield exporter
    gate._telemetry.shutdown()


@pytest.mark.parametrize(
    "variant,stage",
    [("same-bytes", GateStage.BYTES), ("same-render", GateStage.RENDER)],
)
def test_unchanged_sheet_never_calls_judge(tmp_path, harness, variant, stage):
    before = _sheet(tmp_path / "before.pdf")
    content = before.read_bytes()
    if variant == "same-render":
        content = content.replace(b"%PDF-1.4", b"%PDF-1.5", 1)
    after = tmp_path / "after.pdf"
    after.write_bytes(content)

    result = _gate(tmp_path, before, after)

    assert (result.stage, result.verdict) == (stage, ChangeVerdict.UNCHANGED)
    assert harness.calls == []
    sidecar = json.loads(result.sidecar.read_text(encoding="utf-8"))
    assert sidecar["verdict"] == "unchanged"
    assert sidecar["judge_model"] is None


def test_changed_digit_is_meaningful_without_judge(tmp_path, harness):
    before = _sheet(tmp_path / "before.pdf", value="12.50")
    after = _sheet(tmp_path / "after.pdf", value="12.60")

    result = _gate(tmp_path, before, after)

    assert (result.stage, result.verdict) == (GateStage.TEXT, ChangeVerdict.MEANINGFUL)
    assert harness.calls == []
    assert result.anchor_sha256 != result.current_sha256


@pytest.mark.parametrize(
    "kind,decision,skip_kind,verdict",
    [
        ("part", "skip", "rendering_noise", ChangeVerdict.NOISE),
        ("part", "review", "none", ChangeVerdict.MEANINGFUL),
        # Not yet an enablement decision: meaningful, skip kind kept verbatim.
        ("assembly", "skip", "assembly_single_part", ChangeVerdict.MEANINGFUL),
    ],
)
def test_moved_text_runs_the_haiku_precheck_and_maps_its_decision(
    tmp_path, harness, spans, kind, decision, skip_kind, verdict
):
    harness.precheck = _decision(decision, skip_kind)
    before, after = _moved(tmp_path)

    result = _gate(tmp_path, before, after, kind=kind)

    assert (result.stage, result.verdict) == (GateStage.JUDGE, verdict)
    [call] = harness.calls
    assert call["phase"] == "precheck"
    assert (_flag(call["command"], "--model"), _flag(call["command"], "--effort")) == (
        "claude-haiku-5-5",
        "low",
    )
    # The precheck package: the AFTER sheet, then its overlay.
    assert [source.suffix for source in call["sources"]] == [".pdf", ".png"]
    sidecar = json.loads(result.sidecar.read_text(encoding="utf-8"))
    assert sidecar["verdict"] == verdict.value
    assert sidecar["precheck_skip_kind"] == skip_kind
    assert sidecar["judge_model"] == "claude-haiku-5-5"
    assert sidecar["judge_variant"] == "precheck"
    assert sidecar["prompt_sha256"] == gate._sha256(call["prompt"].encode("utf-8"))
    [span] = [
        span
        for span in spans.get_finished_spans()
        if span.name == "drawing_change_gate"
    ]
    assert span.attributes["verdict"] == verdict.value
    assert span.attributes["stage"] == "judge"
    assert span.attributes["judge_variant"] == "precheck"


@pytest.mark.parametrize(
    "failure", ["precheck_provider", "precheck_inspection", "schema"]
)
def test_failed_precheck_is_unsure(tmp_path, harness, failure):
    if failure == "schema":
        harness.precheck = {"decision": "skip"}
    else:
        harness.failure = failure
    before, after = _moved(tmp_path)

    result = _gate(tmp_path, before, after)

    assert (result.stage, result.verdict) == (GateStage.JUDGE, ChangeVerdict.UNSURE)
    assert len(harness.calls) == 1
    assert result.precheck_skip_kind is None
    assert result.judge_error


@pytest.mark.parametrize("answer", [verdict.value for verdict in gate.JUDGE_VERDICTS])
def test_side_by_side_judge_sees_before_after_and_overlay(
    tmp_path, monkeypatch, spans, answer
):
    judge = _SideBySide({"verdict": answer, "reason": "The 12.50 text moved right."})
    monkeypatch.setattr(mr, "_run_reviewer", judge)
    before, after = _moved(tmp_path)

    result = _gate(tmp_path, before, after, variant=gate.JudgeVariant.SIDE_BY_SIDE)

    assert (result.stage, result.verdict) == (GateStage.JUDGE, ChangeVerdict(answer))
    [call] = judge.calls
    assert (_flag(call["command"], "--model"), _flag(call["command"], "--effort")) == (
        "claude-haiku-5-5",
        "low",
    )
    # BEFORE page, AFTER page, then the overlay, all PNG on one pixel grid.
    assert [Path(sheet).suffix for sheet in call["sheets"]] == [".png"] * 3
    sidecar = json.loads(result.sidecar.read_text(encoding="utf-8"))
    assert sidecar["judge_variant"] == "side_by_side"
    assert sidecar["precheck_skip_kind"] is None
    assert sidecar["prompt_sha256"] == gate._sha256(call["prompt"].encode("utf-8"))
    [span] = [
        span
        for span in spans.get_finished_spans()
        if span.name == "drawing_change_gate"
    ]
    assert span.attributes["judge_variant"] == "side_by_side"


@pytest.mark.parametrize(
    "answer",
    [
        RuntimeError("provider unavailable"),
        {"verdict": "unchanged", "reason": "not permitted"},
    ],
    ids=["provider-error", "invalid-output"],
)
def test_failed_side_by_side_judge_is_unsure(tmp_path, monkeypatch, answer):
    judge = _SideBySide(answer)
    monkeypatch.setattr(mr, "_run_reviewer", judge)
    before, after = _moved(tmp_path)

    result = _gate(tmp_path, before, after, variant=gate.JudgeVariant.SIDE_BY_SIDE)

    assert (result.stage, result.verdict) == (GateStage.JUDGE, ChangeVerdict.UNSURE)
    assert result.judge_error
    assert len(judge.calls) == 1


@pytest.mark.parametrize(
    "anchor_findings,stage",
    [
        ([], GateStage.LAYOUT),
        # The same finding at a moved position is not new: the precheck decides.
        ([_finding([10.0, 20.0])], GateStage.JUDGE),
    ],
    ids=["new-finding", "moved-finding"],
)
def test_new_layout_finding_is_meaningful_without_judge(
    tmp_path, harness, anchor_findings, stage
):
    before, after = _moved(tmp_path)
    layouts = (
        _layout(tmp_path / "before.json", anchor_findings),
        _layout(tmp_path / "after.json", [_finding([30.0, 20.0])]),
    )

    result = _gate(tmp_path, before, after, layouts=layouts)

    assert result.stage is stage
    if stage is GateStage.LAYOUT:
        assert result.verdict is ChangeVerdict.MEANINGFUL
        assert harness.calls == []
    else:
        assert result.verdict is ChangeVerdict.NOISE
        assert len(harness.calls) == 1
