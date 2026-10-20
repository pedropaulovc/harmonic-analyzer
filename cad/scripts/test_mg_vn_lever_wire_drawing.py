"""Offline contracts for the lever-wire drawing."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _drawing_sheets as sheets
import build_sh_vn_music_wire as part
import draw_sh_vn_music_wire as drawing
import sh_vn_music_wire_lever_geom as geom

CONFIGURATION = "LeverWire"
STEM = "sh-vn-music-wire"


def test_wire_registry_quantities_count_installed_members() -> None:
    import _config

    row = _config.parts(STEM)
    assert row["process"] == "purchased"
    assert row["supplier_skus"] == ["9666K56"]
    assert int(row["quantity"]) == sum(row["configuration_quantities"].values())
    assert int(row["configuration_quantities"][CONFIGURATION]) == 1


def test_balloon_station_is_midway_along_the_free_run() -> None:
    assert part.BALLOON_RING_STATION == geom.WIRE_LEN / 2.0


@pytest.mark.parametrize(
    "corruption",
    (None, "initial-configuration", "configuration", "source"),
)
def test_wire_package_refuses_wrong_native_members_or_sources(
    monkeypatch, tmp_path, corruption
) -> None:
    source = tmp_path / f"{STEM}.SLDPRT"
    source.write_bytes(b"offline native-path fixture")
    monkeypatch.setattr(drawing, "SOURCE", source)
    properties = {}
    views = []

    class Sheet:
        def __init__(self, name):
            self.name = name
            self.CustomPropertyView = ""

        def GetName(self):
            return self.name

        def SetName(self, name):
            self.name = name

    class Document:
        def __init__(self):
            self.sheets = [Sheet("Sheet1")]
            self.active = self.sheets[0]
            self.Extension = SimpleNamespace(SelectByID2=lambda *args: True)

        def GetCurrentSheet(self):
            return self.active

        def GetSheetNames(self):
            return tuple(sheet.name for sheet in self.sheets)

        def ActivateSheet(self, name):
            for sheet in self.sheets:
                if sheet.name == name:
                    self.active = sheet
                    return True
            return False

        def ClearSelection2(self, _all):
            pass

        def EditCopy(self):
            pass

        def PasteSheet(self, _position, _options):
            self.sheets.append(Sheet("CopiedSheet"))
            return True

    class View:
        def __init__(self, model_source, orientation):
            self.sheet = document.active.name
            self.name = f"{self.sheet} {orientation}"
            self.model_source = model_source
            self._configuration = "Default"

        @property
        def ReferencedConfiguration(self):
            return self._configuration

        @ReferencedConfiguration.setter
        def ReferencedConfiguration(self, value):
            if corruption == "initial-configuration" and self.sheet == "PenWire":
                return
            self._configuration = value

        def GetReferencedModelName(self):
            return self.model_source

    class Note:
        def __init__(self, text):
            self.text = text

        def GetText(self):
            return self.text

    def attr_or_call(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value

    document = Document()
    adapter = SimpleNamespace(currentModel=object(), _get_attr_or_call=attr_or_call)

    async def open_model(_path):
        return True

    def read_properties(_model, names, *, required):
        properties.update((name, "offline property") for name in names)
        return properties

    def new_drawing(_adapter, **kwargs):
        adapter.currentModel = document
        return document, document.active

    def place(_adapter, model_source, orientation, x, y, *, scale):
        view = View(model_source, orientation)
        views.append(view)
        return view

    def curate(_adapter, view, **kwargs):
        assert view.ReferencedConfiguration == document.active.name

    async def finalize(_adapter, _outputs, **kwargs):
        if corruption == "configuration":
            views[-1].ReferencedConfiguration = "Default"
        elif corruption == "source":
            views[-1].model_source = str(tmp_path / "wrong-native.SLDPRT")
        for settled_check in kwargs["settled_checks"]:
            settled_check()
        return {}

    adapter.open_model = open_model
    monkeypatch.setattr(drawing, "check", lambda _label, value: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(sheets, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(sheets, "iter_views", lambda _adapter: iter(()))
    monkeypatch.setattr(sheets, "null_callout", lambda: None)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "read_required_properties", read_properties)
    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *args: None)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *args: None)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(
        drawing, "add_property_linked_note",
        lambda _adapter, key, x, y: Note(properties[key]),
    )
    monkeypatch.setattr(
        drawing, "add_note", lambda _adapter, text, x, y: Note(text),
    )
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)

    if corruption is not None:
        with pytest.raises(RuntimeError):
            asyncio.run(drawing.build(adapter))
    else:
        asyncio.run(drawing.build(adapter))
        assert all(view.ReferencedConfiguration == view.sheet for view in views)
