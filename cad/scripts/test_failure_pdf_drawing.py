r"""Offline contract: a drawing recipe that fails leaves its sheets as a PDF.

A recipe failure (a layout-audit abort, a BOM row that did not persist) never
reaches ``capture_com_failure``, so on a farm worker the half-built sheets died
with the disposable workspace and a failed drawing could not be eye-passed.
``_drawing_common.run_drawing_build`` exports the open drawing under
``cad/out/reports/failures/`` before ``run_build``'s teardown closes it.

    uv run --frozen pytest cad/scripts/test_failure_pdf_drawing.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _drawing_common  # noqa: E402


class _Model:
    def __init__(self, doc_type: int, *, fails: Exception | None = None) -> None:
        self.doc_type = doc_type
        self.fails = fails
        self.saved: list[str] = []
        self.open = True

    def GetType(self) -> int:
        return self.doc_type

    def SaveAs3(self, path: str, version: int, options: int) -> int:
        assert self.open, "the PDF must be exported before teardown closes the drawing"
        if self.fails is not None:
            raise self.fails
        Path(path).write_bytes(b"%PDF-sheets")
        self.saved.append(path)
        return 0


@pytest.fixture
def events(tmp_path, monkeypatch):
    monkeypatch.setattr(_drawing_common, "OUT_FAILURES", tmp_path / "failures")
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda obj, _name: obj)
    recorded: list[dict] = []
    monkeypatch.setattr(
        _drawing_common._telemetry,
        "event",
        lambda name, **attrs: recorded.append({"name": name, **attrs}),
    )
    return recorded


def test_the_open_drawing_is_exported_under_the_failure_tree(tmp_path, events) -> None:
    model = _Model(3)
    path = _drawing_common.export_failure_pdf(
        type("Adapter", (), {"currentModel": model})(), "drive_train_assembly"
    )

    assert path is not None and path.read_bytes() == b"%PDF-sheets"
    relative = path.relative_to(tmp_path / "failures")
    assert relative.parts[0] == "drawing-drive_train_assembly"
    assert relative.parts[2] == "drive-train-assembly.pdf"
    assert events == [
        {
            "name": "drawing.failure_pdf",
            "target": "drive_train_assembly",
            "path": str(path),
            "outcome": "exported",
        }
    ]


def test_nothing_is_exported_before_a_drawing_is_open(events) -> None:
    """A failure while the SOURCE part is still the active document."""
    model = _Model(1)
    path = _drawing_common.export_failure_pdf(
        type("Adapter", (), {"currentModel": model})(), "pinion_arbor"
    )

    assert path is None
    assert model.saved == []
    assert [event["outcome"] for event in events] == ["no_drawing"]


def test_an_export_that_fails_is_reported_and_swallowed(events) -> None:
    model = _Model(3, fails=RuntimeError("SaveAs3 refused"))
    path = _drawing_common.export_failure_pdf(
        type("Adapter", (), {"currentModel": model})(), "pinion_arbor"
    )

    assert path is None
    (event,) = events
    assert event["outcome"].startswith("error: RuntimeError('SaveAs3 refused')")


def _run_like_run_build(adapter, model):
    """``run_build``'s shape: run the build, then close every document."""

    def run(build) -> int:
        try:
            asyncio.run(build(adapter))
        except RuntimeError:
            return 1
        finally:
            model.open = False
        return 0

    return run


def test_a_failed_recipe_exports_its_sheets_and_still_fails(
    monkeypatch, events
) -> None:
    model = _Model(3)
    adapter = type("Adapter", (), {"currentModel": model})()
    monkeypatch.setattr(sys, "argv", ["C:/w/cad/scripts/draw_cone_swing_platform.py"])
    monkeypatch.setattr(_drawing_common, "run_build", _run_like_run_build(adapter, model))

    async def build(_adapter):
        raise RuntimeError("drawing layout audit failed (1 overlap(s))")

    assert _drawing_common.run_drawing_build(build) == 1
    (saved,) = model.saved
    assert Path(saved).name == "cone-swing-platform.pdf"
    assert [event["outcome"] for event in events] == ["exported"]


def test_a_passing_recipe_exports_nothing(monkeypatch, events) -> None:
    model = _Model(3)
    adapter = type("Adapter", (), {"currentModel": model})()
    monkeypatch.setattr(sys, "argv", ["draw_pinion_arbor.py"])
    monkeypatch.setattr(_drawing_common, "run_build", _run_like_run_build(adapter, model))

    async def build(_adapter):
        return {}

    assert _drawing_common.run_drawing_build(build) == 0
    assert model.saved == []
    assert events == []


def test_every_drawing_recipe_runs_through_run_drawing_build() -> None:
    """A recipe on bare ``run_build`` would fail without leaving its sheets."""
    scripts = sorted(Path(__file__).resolve().parent.glob("draw_*.py"))
    assert len(scripts) > 50
    bare = [
        path.name
        for path in scripts
        if "run_drawing_build(build)" not in path.read_text(encoding="utf-8")
    ]
    assert bare == []
