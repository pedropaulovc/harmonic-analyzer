"""Offline telemetry-shape tests for COM-free release neutral staging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import export_models
import _telemetry


def _capture() -> InMemorySpanExporter:
    from typing import cast

    _telemetry.configure()
    exporter = InMemorySpanExporter()
    provider = cast(SdkTracerProvider, _telemetry.trace.get_tracer_provider())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def test_neutral_stage_is_one_aggregate_span_without_document_work(
    monkeypatch: Any, tmp_path: Path,
) -> None:
    part = tmp_path / "cad/out/sldprt/sample-part.SLDPRT"
    assembly = tmp_path / "cad/out/sldasm/sample-assembly.SLDASM"
    step = tmp_path / "cad/out/step/sample-part.STEP"
    stl = tmp_path / "cad/out/stl/sample-assembly.STL"
    for path, body in ((part, b"part"), (assembly, b"assembly"),
                       (step, b"step"), (stl, b"stl")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    manifest_path = tmp_path / "cad/out/reports/release-neutral.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({
        "schema": export_models.NEUTRAL_SCHEMA,
        "exporter": "exporter-v1",
        "sources": {"sample-part": "part-v1", "sample-assembly": "assembly-v1"},
        "files": {
            "step/sample-part.STEP": {
                "source": step.relative_to(tmp_path).as_posix(), "bytes": step.stat().st_size,
            },
            "stl/sample-assembly.STL": {
                "source": stl.relative_to(tmp_path).as_posix(), "bytes": stl.stat().st_size,
            },
        },
    }), encoding="utf-8")

    monkeypatch.setattr(export_models, "REPO", tmp_path)
    monkeypatch.setattr(export_models, "NEUTRAL_MANIFEST", manifest_path)
    monkeypatch.setattr(export_models, "part_stems", lambda: ["sample_part"])
    monkeypatch.setattr(export_models, "ASSEMBLY_ORDER", ("sample_assembly",))
    monkeypatch.setattr(export_models, "scene_config_meshes", lambda: {})
    monkeypatch.setattr(
        export_models, "_release_sources",
        lambda _parts, _assemblies: {
            "sample-part": part, "sample-assembly": assembly,
        },
    )
    monkeypatch.setattr(
        export_models, "_release_inventory",
        lambda _parts, _assemblies, _cfg: {
            "step/sample-part.STEP": step,
            "stl/sample-assembly.STL": stl,
        },
    )
    monkeypatch.setattr(export_models, "_exporter_digest", lambda: "exporter-v1")
    monkeypatch.setattr(
        export_models, "src_digest",
        lambda source: "part-v1" if source == part else "assembly-v1",
    )

    spans = _capture()
    with _telemetry.run_pipeline_span("test.release-neutral"):
        facts = export_models.stage_release_neutral(tmp_path / "stage")

    assert facts == {
        "documents": 2,
        "parts": 1,
        "assemblies": 1,
        "pngs": 2,
        "views": 1,
        "config_meshes": 0,
    }
    assert (tmp_path / "stage/step/sample-part.STEP").read_bytes() == b"step"
    assert (tmp_path / "stage/stl/sample-assembly.STL").read_bytes() == b"stl"

    finished = spans.get_finished_spans()
    neutral = [span for span in finished if span.name == "release.neutral_stage"]
    assert len(neutral) == 1
    assert neutral[0].attributes["documents"] == 2
    assert neutral[0].attributes["files"] == 2
    assert not neutral[0].events
    assert not [span for span in finished if span.name == "release.neutral_document"]
