"""SolidWorks-free contracts for the saved-drawing audit runner."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import _common
import audit_drawing_layout
from _drawing_registry import DrawingLayout


def test_cli_parses_the_registry_layout_enum(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_drawing_layout.py", "platen-guide.SLDDRW", "landscape"],
    )

    assert audit_drawing_layout._parse_args().layout is DrawingLayout.LANDSCAPE


def test_empty_title_closes_the_matching_saved_drawing_by_filename(tmp_path):
    drawing_path = (tmp_path / "platen-guide.SLDDRW").resolve()
    state = {"open": True}

    model = SimpleNamespace(
        Visible=True,
        GetTitle=lambda: "",
        GetPathName=lambda: str(drawing_path),
        GetNext=lambda: None,
    )

    class App:
        closed_titles: list[str] = []

        def GetFirstDocument(self):
            return model if state["open"] else None

        def CloseDoc(self, title):
            self.closed_titles.append(title)
            if title == drawing_path.name:
                state["open"] = False

    app = App()
    adapter = SimpleNamespace(swApp=app, currentModel=model)

    _common._close_drawing_and_verify(adapter, drawing_path)

    assert app.closed_titles == [drawing_path.name]
    assert state["open"] is False
