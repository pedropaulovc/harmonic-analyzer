"""Offline telemetry-shape tests for the release neutral-export loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import cut_release
import _telemetry


class _Document:
    def SaveAs3(self, path: str, _version: int, _options: int) -> int:
        Path(path).write_bytes(b"neutral")
        return 1


def _capture() -> InMemorySpanExporter:
    from typing import cast

    _telemetry.configure()
    exporter = InMemorySpanExporter()
    provider = cast(SdkTracerProvider, _telemetry.trace.get_tracer_provider())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def test_neutral_export_uses_document_events_not_per_document_spans(
    monkeypatch: Any, tmp_path: Path,
) -> None:
    part = tmp_path / "sample-part.SLDPRT"
    assembly = tmp_path / "sample-assembly.SLDASM"
    part.write_bytes(b"part")
    assembly.write_bytes(b"assembly")

    monkeypatch.setattr(
        cut_release,
        "_models",
        lambda _folder, ext, _manifest: [part] if ext == "SLDPRT" else [assembly],
    )
    monkeypatch.setattr(cut_release, "part_stems", lambda: ["sample_part"])
    monkeypatch.setattr(cut_release, "ASSEMBLY_ORDER", ("sample_assembly",))
    monkeypatch.setattr(cut_release, "_cfg_meshes_from_scene", lambda: {})
    monkeypatch.setattr(cut_release, "_discard_open_documents", lambda _sw: None)
    monkeypatch.setattr(cut_release, "_set_export_prefs", lambda _sw: {})
    monkeypatch.setattr(cut_release, "_restore_export_prefs", lambda _sw, _old: None)
    monkeypatch.setattr(cut_release, "_open_and_verify", lambda _sw, _src, _kind: _Document())
    monkeypatch.setattr(cut_release, "_close_active_documents", lambda _sw: None)
    monkeypatch.setattr(cut_release, "_png_key", lambda src, _stls, _colors: src.stem)
    monkeypatch.setattr(cut_release, "_staged_pngs", lambda *_args: True)
    monkeypatch.setattr(cut_release, "OUT_STL", tmp_path / "render-cache")
    monkeypatch.setattr(cut_release, "PNG_CACHE_DIR", tmp_path / "png-cache")
    monkeypatch.setattr(cut_release, "SLOW_NEUTRAL_DOCUMENT_SECONDS", 999.0)

    spans = _capture()
    with _telemetry.run_pipeline_span("test.release-neutral"):
        facts = cut_release.export_neutral(object(), tmp_path / "stage")

    assert facts["documents"] == 2
    finished = spans.get_finished_spans()
    neutral = [span for span in finished if span.name == "release.neutral_export"]
    assert len(neutral) == 1
    assert neutral[0].attributes["documents"] == 2
    assert neutral[0].attributes["png_cache.hits"] == 2
    assert neutral[0].attributes["png_cache.misses"] == 0

    events = [event for event in neutral[0].events
              if event.name == "release.neutral_document"]
    assert {event.attributes["document"] for event in events} == {
        part.name,
        assembly.name,
    }
    assert all(event.attributes["elapsed_seconds"] >= 0 for event in events)
    assert not [span for span in finished if span.name == "release.neutral_document"]
