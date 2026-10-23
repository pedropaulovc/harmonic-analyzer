"""Offline contracts of the shared music-wire purchase drawing."""

from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace

import pytest

import _supplier_wire_stock_drawing as section
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


def test_package_note_names_the_purchase_without_dimension_text() -> None:
    # The diameter is the native supplier dimension; notes carry no sizes.
    assert part.DRAWING_NOTES == "PURCHASED WIRE: McMASTER-CARR 9666K56"
    assert not re.search(r"Ø|<MOD-DIAM>|\bIN\b|\bMM\b|\d\.\d", part.DRAWING_NOTES)


def test_section_label_states_the_view_scale_inside_its_field() -> None:
    assert section.STOCK_LABEL == "WIRE SECTION SCALE 20:1"
    assert section.STOCK_SCALE == (20, 1)
    field = section.STOCK_FIELD
    for x, y in (section.STOCK_CENTER, section.STOCK_TEXT, section.STOCK_LABEL_XY):
        assert field[0] <= x <= field[2] and field[1] <= y <= field[3]
    # The label's top stays under the 20:1 circle's padded native outline
    # (radius 7.9 mm plus SolidWorks' ~5.6 mm outline padding).
    assert section.STOCK_LABEL_XY[1] < section.STOCK_CENTER[1] - 0.0136


class _Note:
    def __init__(self, text, x, y):
        self.text, self.x, self.y = text, x, y

    def GetText(self):
        return self.text

    def GetExtent(self):
        return (self.x, self.y - 0.004, 0.0, self.x + 0.1, self.y, 0.0)


def _package(monkeypatch, tmp_path, *, note_text=None, note_at=None):
    source = tmp_path / f"{STEM}.SLDPRT"
    source.write_bytes(b"offline native-path fixture")
    monkeypatch.setattr(drawing, "SOURCE", source)
    calls = SimpleNamespace(sections=[], settled=[], notes=[], finalize={})
    document = object()
    adapter = SimpleNamespace(currentModel=None)

    async def open_model(path):
        assert path == str(source)
        adapter.currentModel = "source"
        return True

    def read_properties(model, names, *, required):
        assert model == "source"
        assert "Manufacturing Notes" in required
        return {name: "native property" for name in names} | {
            "Manufacturing Notes": part.DRAWING_NOTES,
        }

    def new_drawing(_adapter, *, property_view, scale, layout):
        assert scale == section.STOCK_SCALE
        adapter.currentModel = document
        return document, None

    def wire_section(target, model_source):
        assert target is adapter and adapter.currentModel is document
        assert model_source == source
        calls.sections.append(model_source)
        return lambda: calls.settled.append("section")

    def linked_note(_adapter, key, x, y):
        assert key == "Manufacturing Notes"
        text = part.DRAWING_NOTES if note_text is None else note_text
        note = _Note(text, *(note_at or (x, y)))
        calls.notes.append(note)
        return note

    async def finalize(_adapter, _outputs, **kwargs):
        calls.finalize = kwargs
        for settled in kwargs["settled_checks"]:
            settled()
        return {"pdf": "offline-export"}

    adapter.open_model = open_model
    monkeypatch.setattr(drawing, "check", lambda _label, value: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(drawing, "read_required_properties", read_properties)
    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *args: None)
    monkeypatch.setattr(drawing, "add_wire_section", wire_section)
    monkeypatch.setattr(drawing, "add_property_linked_note", linked_note)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    return adapter, calls


def test_one_sheet_carries_the_section_and_the_purchase_note(monkeypatch, tmp_path):
    adapter, calls = _package(monkeypatch, tmp_path)
    assert asyncio.run(drawing.build(adapter)) == {"pdf": "offline-export"}
    assert calls.sections == [drawing.SOURCE]
    assert calls.settled == ["section"]
    assert [(note.x, note.y) for note in calls.notes] == [drawing.NOTES_XY]
    assert calls.finalize["scale"] == section.STOCK_SCALE
    assert "expected_sheet_names" not in calls.finalize


@pytest.mark.parametrize(
    "fault",
    ({"note_text": "PURCHASED WIRE: OTHER"}, {"note_at": (0.300, 0.060)},
     {"note_at": (-0.020, 0.075)}),
    ids=("text", "title-block", "off-sheet"),
)
def test_purchase_note_fails_closed_after_final_rebuild(monkeypatch, tmp_path, fault):
    adapter, _calls = _package(monkeypatch, tmp_path, **fault)
    with pytest.raises(RuntimeError, match="linked note"):
        asyncio.run(drawing.build(adapter))
