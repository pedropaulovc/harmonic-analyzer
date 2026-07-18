"""Offline telemetry-shape tests for COM-free release neutral staging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
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
    glb = tmp_path / "cad/out/gltf/sample-assembly.glb"
    for path, body in ((part, b"part"), (assembly, b"assembly"),
                       (step, b"step"), (glb, b"glb")):
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
                "sha256": export_models._file_sha256(step),
            },
            "gltf/sample-assembly.glb": {
                "source": glb.relative_to(tmp_path).as_posix(), "bytes": glb.stat().st_size,
                "sha256": export_models._file_sha256(glb),
            },
        },
    }), encoding="utf-8")

    monkeypatch.setattr(export_models, "REPO", tmp_path)
    monkeypatch.setattr(export_models, "NEUTRAL_MANIFEST", manifest_path)
    monkeypatch.setattr(export_models, "part_stems", lambda: ["sample_part"])
    monkeypatch.setattr(export_models, "ASSEMBLY_ORDER", ("sample_assembly",))
    monkeypatch.setattr(export_models, "all_scene_part_meshes", lambda _scenes: {})
    monkeypatch.setattr(
        export_models, "_release_sources",
        lambda _parts, _assemblies, _scene: {
            "sample-part": part, "sample-assembly": assembly,
        },
    )
    monkeypatch.setattr(
        export_models, "_release_inventory",
        lambda _parts, _assemblies, _cfg, _scenes: {
            "step/sample-part.STEP": step,
            "gltf/sample-assembly.glb": glb,
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
    assert (tmp_path / "stage/gltf/sample-assembly.glb").read_bytes() == b"glb"

    finished = spans.get_finished_spans()
    neutral = [span for span in finished if span.name == "release.neutral_stage"]
    assert len(neutral) == 1
    assert neutral[0].attributes["documents"] == 2
    assert neutral[0].attributes["files"] == 2
    assert not neutral[0].events
    assert {span.name for span in finished} >= {
        "release.neutral_validate_sources",
        "release.neutral_copy",
    }
    assert not [span for span in finished if span.name == "release.neutral_document"]

    step.write_bytes(b"xxxx")
    with pytest.raises(RuntimeError, match="digest changed"):
        export_models.stage_release_neutral(tmp_path / "corrupt-stage")
