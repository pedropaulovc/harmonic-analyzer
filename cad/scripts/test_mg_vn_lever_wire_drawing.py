"""Offline contracts of the shared music-wire purchase drawing."""

from __future__ import annotations

import ast
import asyncio
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import _supplier_wire_stock_drawing as section
import build_sh_vn_music_wire as part
import draw_sh_vn_music_wire as drawing
import sh_vn_music_wire_lever_geom as geom
import sh_vn_music_wire_pen_geom as pen_geom

CONFIGURATION = "LeverWire"
STEM = "sh-vn-music-wire"
_DIMENSION_TEXT = re.compile(r"Ø|<MOD-DIAM>|\bIN\b|\bMM\b|\d\.\d")
_ASSEMBLIES = Path(__file__).resolve().parents[1] / "config" / "assemblies"


def test_wire_registry_quantities_count_installed_members() -> None:
    import _config

    row = _config.parts(STEM)
    assert row["process"] == "purchased"
    assert row["supplier_skus"] == ["9666K56"]
    assert int(row["quantity"]) == sum(row["configuration_quantities"].values())
    assert int(row["configuration_quantities"][CONFIGURATION]) == 1


def test_balloon_station_is_midway_along_the_free_run() -> None:
    assert part.BALLOON_RING_STATION == geom.WIRE_LEN / 2.0


def test_package_notes_carry_no_dimension_text() -> None:
    # The diameter is the native supplier dimension; notes carry no sizes.
    assert part.DRAWING_NOTES == "PURCHASED WIRE: McMASTER-CARR 9666K56"
    for text in (part.DRAWING_NOTES, drawing.ASSEMBLY_NOTE, drawing.ISO_LABEL):
        assert not _DIMENSION_TEXT.search(text), text


def _printed_step_sheets(module) -> dict[int, int]:
    """Step number -> 1-based sheet, read from where the assembly drawing
    actually places each wrapped sequence block (``_add_note_block`` calls
    naming ``SHEET_NAMES[i]`` and a module-level block)."""
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    placed: dict[str, int] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "_add_note_block"
            and len(node.args) >= 3
        ):
            continue
        sheet, block = node.args[1], node.args[2]
        if (
            isinstance(sheet, ast.Subscript)
            and getattr(sheet.value, "id", None) == "SHEET_NAMES"
            and isinstance(sheet.slice, ast.Constant)
            and isinstance(block, ast.Name)
            and block.id.startswith("ASSEMBLY_STEPS")
        ):
            assert block.id not in placed, block.id
            placed[block.id] = sheet.slice.value + 1
    assert placed, module.__name__
    printed: dict[int, int] = {}
    for block, sheet in placed.items():
        for line in getattr(module, block).splitlines():
            match = re.match(r"(\d+)\. ", line)
            if match:
                step = int(match.group(1))
                assert step not in printed, (module.__name__, step)
                printed[step] = sheet
    return printed


def _cited_groups(line: str, number: str) -> dict[int, set[int]]:
    """Sheet -> the step numbers the pointer prints after that SHEET."""
    _, *parts = re.split(r"\bSHEET (\d+)\b", line.replace(number, ""))
    assert parts and len(parts) % 2 == 0, line
    return {
        int(sheet): {int(value) for value in re.findall(r"\b\d+\b", text)}
        for sheet, text in zip(parts[::2], parts[1::2], strict=True)
    }


def test_assembly_pointer_cites_the_sheets_and_steps_that_cut_and_form_each_member():
    import draw_mg_magnifier_assembly as magnifier
    import draw_pn_pen_assembly as pen
    import mg_magnifier_assembly_sheet as magnifier_sheet
    import pn_pen_assembly_sheet as pen_sheet

    numbers = {
        stem: yaml.safe_load(
            (_ASSEMBLIES / f"{stem}.yaml").read_text(encoding="utf-8")
        )["number"]
        for stem in ("mg-magnifier", "pn-pen")
    }
    assert numbers == {
        "mg-magnifier": drawing.magnifier_steps.DRAWING_NUMBER,
        "pn-pen": drawing.PEN_DRAWING_NUMBER,
    }
    # The lever wire's steps are the keyed sequence's hook and tie steps.
    wire_keys = (
        drawing.magnifier_steps.WIRE_HOOKED_KEY,
        drawing.magnifier_steps.WIRE_TIED_KEY,
    )
    assert all("WIRE" in magnifier_sheet.STEP_TEXT[key] for key in wire_keys)
    lever_steps = {drawing.magnifier_steps.step_number(key) for key in wire_keys}
    # The pen sheet has no keyed sequence: its numbered steps naming the pen
    # wire are the ones the pointer must cite.
    pen_steps = {
        int(text.split(".", 1)[0])
        for text in pen_sheet.ASSEMBLY_STEPS
        if text[:1].isdigit() and "PEN WIRE" in text
    }
    assert pen_steps == {step for _sheet, step in drawing.PEN_WIRE_CITATIONS}
    printed = {
        "mg-magnifier": _printed_step_sheets(magnifier),
        "pn-pen": _printed_step_sheets(pen),
    }
    cited = {"mg-magnifier": lever_steps, "pn-pen": pen_steps}
    lines = drawing.ASSEMBLY_NOTE.splitlines()
    for stem, number in numbers.items():
        expected: dict[int, set[int]] = {}
        for step in cited[stem]:
            expected.setdefault(printed[stem][step], set()).add(step)
        [line] = [line for line in lines if number in line]
        assert _cited_groups(line, number) == expected, (stem, line)


def test_end_view_and_isometric_labels_state_their_scales_inside_their_fields() -> None:
    assert section.STOCK_LABEL == "WIRE END VIEW SCALE 20:1"
    assert section.STOCK_SCALE == (20, 1)
    field = section.STOCK_FIELD
    for x, y in (section.STOCK_CENTER, section.STOCK_TEXT, section.STOCK_LABEL_XY):
        assert field[0] <= x <= field[2] and field[1] <= y <= field[3]
    # The label's top stays under the 20:1 circle's padded native outline
    # (radius 7.9 mm plus SolidWorks' ~5.6 mm outline padding).
    assert section.STOCK_LABEL_XY[1] < section.STOCK_CENTER[1] - 0.0136
    assert drawing.ISO_LABEL.startswith("ISOMETRIC SCALE 2:1\n")
    assert "NOT TO LENGTH" in drawing.ISO_LABEL
    assert drawing.ISO_SCALE == (2, 1)
    assert drawing.ISO_FIELD[0] >= section.STOCK_FIELD[2]
    assert drawing.ISO_FIELD[1] >= drawing._TITLE_BLOCK[3]
    assert drawing.ISO_FIELD[3] <= drawing._BORDER[3]


class _Note:
    def __init__(self, text, x, y):
        self.text, self.x, self.y = text, x, y

    def GetText(self):
        return self.text

    def GetExtent(self):
        lines = self.text.splitlines()
        width = max(map(len, lines)) * 0.0022
        return (self.x, self.y - len(lines) * 0.0045, 0.0, self.x + width, self.y, 0.0)


class _IsoView:
    """An end-origin member: reconfiguration displaces its real outline."""

    def __init__(self, source, x, y, scale, fault):
        self.source, self.Position, self.fault = source, (x, y), fault
        self.ScaleRatio = tuple(scale)
        self.ReferencedConfiguration = "LeverWire"
        self.UseSheetScale = 1
        self.mode, self.edges = 2, False

    def GetReferencedModelName(self):
        return self.source

    def GetOrientationName(self):
        return "*Isometric"

    def GetDisplayMode2(self):
        return self.mode

    def GetDisplayEdgesInShadedMode(self):
        return self.edges

    def GetOutline(self):
        offset = (
            (0.012, -0.040) if self.ReferencedConfiguration == "PenWire" else (0.0, 0.0)
        )
        half = (0.007, pen_geom.WIRE_LEN / 1000 * math.sqrt(2 / 3) + 0.0056)
        cx, cy = (self.Position[i] + offset[i] for i in range(2))
        return (cx - half[0], cy - half[1], cx + half[0], cy + half[1])

    def SetViewPosition(self, position, _move_children):
        if self.fault != "ignored-recenter":
            self.Position = tuple(position)
        return True


def _package(
    monkeypatch,
    tmp_path,
    *,
    note_text=None,
    note_at=None,
    iso_fault=None,
    settled_fault=None,
    dirty_source=False,
    finalize_writes_source=False,
):
    source = tmp_path / f"{STEM}.SLDPRT"
    source.write_bytes(b"offline native-path fixture")
    monkeypatch.setattr(drawing, "SOURCE", source)
    calls = SimpleNamespace(
        sections=[],
        settled=[],
        notes=[],
        views=[],
        finalize={},
        opens=[],
    )
    document = SimpleNamespace(
        ActivateView=lambda _name: True,
        GetEditSheet=lambda: True,
        ActiveDrawingView=None,
    )
    adapter = SimpleNamespace(currentModel=None)
    source_model = SimpleNamespace(GetSaveFlag=lambda: dirty_source)

    def open_read_only(target, model_source, *, label):
        # The shared part is never opened writable through adapter.open_model.
        assert target is adapter and model_source == source and label == STEM
        calls.opens.append(model_source)
        adapter.currentModel = source_model
        return source_model

    def read_properties(model, names, *, required):
        assert model is source_model
        assert "Manufacturing Notes" in required
        return {name: "native property" for name in names} | {
            "Manufacturing Notes": part.DRAWING_NOTES,
        }

    def new_drawing(_adapter, *, property_view, scale, layout, unit):
        assert scale == section.STOCK_SCALE
        adapter.currentModel = document
        return document, None

    def wire_section(target, model_source):
        assert target is adapter and adapter.currentModel is document
        assert model_source == source and not calls.views
        calls.sections.append(model_source)
        return lambda: calls.settled.append("section")

    def place(_adapter, model_source, orientation, x, y, *, scale):
        assert orientation == "*Isometric" and calls.sections
        view = _IsoView(model_source, x, y, scale, iso_fault)
        calls.views.append(view)
        return view

    def shade(_adapter, view, *, label):
        view.mode, view.edges = 3, True

    def linked_note(_adapter, key, x, y):
        assert key == "Manufacturing Notes"
        text = part.DRAWING_NOTES if note_text is None else note_text
        note = _Note(text, *(note_at or (x, y)))
        calls.notes.append(note)
        return note

    def literal_note(_adapter, text, x, y):
        note = _Note(text, x, y)
        calls.notes.append(note)
        return note

    async def finalize(_adapter, _outputs, **kwargs):
        calls.finalize = kwargs
        view = calls.views[0]
        if settled_fault == "configuration":
            view.ReferencedConfiguration = "LeverWire"
        elif settled_fault == "wireframe":
            view.mode = 2
        elif settled_fault == "scale":
            view.ScaleRatio = (1, 1)
        if finalize_writes_source:
            source.write_bytes(b"part persisted by the drawing")
        for settled in kwargs["settled_checks"]:
            settled()
        return {"pdf": "offline-export"}

    monkeypatch.setattr(drawing, "_open_supplier_source_read_only", open_read_only)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "read_required_properties", read_properties)
    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *args: None)
    monkeypatch.setattr(drawing, "add_wire_section", wire_section)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "set_high_quality_shaded_with_edges", shade)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "add_property_linked_note", linked_note)
    monkeypatch.setattr(drawing, "add_note", literal_note)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    return adapter, calls


def test_one_sheet_carries_end_view_isometric_and_notes(monkeypatch, tmp_path):
    adapter, calls = _package(monkeypatch, tmp_path)
    assert asyncio.run(drawing.build(adapter)) == {"pdf": "offline-export"}
    assert calls.opens == [drawing.SOURCE]
    assert calls.sections == [drawing.SOURCE]
    assert calls.settled == ["section"]
    [iso] = calls.views
    assert iso.ReferencedConfiguration == pen_geom.CONFIGURATION
    assert iso.ScaleRatio == drawing.ISO_SCALE and iso.UseSheetScale == 0
    assert (iso.mode, iso.edges) == (3, True)
    box = iso.GetOutline()
    assert ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) == pytest.approx(
        drawing.ISO_CENTER
    )
    assert [(note.text, (note.x, note.y)) for note in calls.notes] == [
        (part.DRAWING_NOTES, drawing.NOTES_XY),
        (drawing.ASSEMBLY_NOTE, drawing.ASSEMBLY_NOTE_XY),
        (drawing.ISO_LABEL, drawing.ISO_LABEL_XY),
    ]
    assert calls.finalize["scale"] == section.STOCK_SCALE
    assert "expected_sheet_names" not in calls.finalize


@pytest.mark.parametrize(
    "fault",
    (
        {"note_text": "PURCHASED WIRE: OTHER"},
        {"note_at": (0.300, 0.060)},
        {"note_at": (-0.020, 0.075)},
        {"note_at": (0.020, 0.103)},
        {"note_at": (0.120, 0.170)},
    ),
    ids=("text", "title-block", "off-sheet", "on-assembly-note", "on-end-view"),
)
def test_purchase_note_fails_closed_after_final_rebuild(monkeypatch, tmp_path, fault):
    adapter, _calls = _package(monkeypatch, tmp_path, **fault)
    with pytest.raises(RuntimeError, match="purchase note|assembly pointer note"):
        asyncio.run(drawing.build(adapter))


@pytest.mark.parametrize(
    "fault",
    (
        {"iso_fault": "ignored-recenter"},
        {"settled_fault": "configuration"},
        {"settled_fault": "wireframe"},
        {"settled_fault": "scale"},
    ),
    ids=("ignored-recenter", "configuration", "wireframe", "scale"),
)
def test_isometric_fails_closed_after_final_rebuild(monkeypatch, tmp_path, fault):
    adapter, _calls = _package(monkeypatch, tmp_path, **fault)
    with pytest.raises(RuntimeError, match="wire isometric"):
        asyncio.run(drawing.build(adapter))


def test_dirty_read_only_source_is_refused_before_drawing(monkeypatch, tmp_path):
    adapter, calls = _package(monkeypatch, tmp_path, dirty_source=True)
    with pytest.raises(RuntimeError, match="must be clean"):
        asyncio.run(drawing.build(adapter))
    assert calls.opens == [drawing.SOURCE] and not calls.sections


def test_source_part_bytes_are_preserved_through_export(monkeypatch, tmp_path):
    adapter, calls = _package(monkeypatch, tmp_path, finalize_writes_source=True)
    with pytest.raises(RuntimeError, match="source part bytes changed"):
        asyncio.run(drawing.build(adapter))
    assert calls.settled == ["section"]
