"""Offline contracts for the measuring-stick drawing."""

from __future__ import annotations

from pathlib import Path
import asyncio
from types import SimpleNamespace

import pytest

import build_measuring_stick as part
import draw_measuring_stick as drawing
import measuring_stick_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/measuring-stick.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/measuring-stick.pdf")
    assert drawing.PNG.as_posix().endswith("/png/measuring-stick_drawing.png")
    assert (
        DRAWINGS_BY_NAME["measuring_stick"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is measuring_stick_spec.DRAWING_DIMENSIONS
    marked = set().union(*measuring_stick_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked


def test_notes_cover_the_scale_and_graduations() -> None:
    notes = measuring_stick_spec.DRAWING_NOTES
    assert "FINISHED BAR" in notes
    assert "11 FULL TICKS" in notes
    assert "HALF-DIVISION" in notes
    assert "SQUARE BOTTOM" in notes
    assert "NONCUMULATIVE" in notes
    assert "STROKE WIDTH 0.30" in notes
    assert "ASME Y14.2 VERTICAL GOTHIC" in notes
    # Numeral note tracks the build (build_measuring_stick.NUMERAL_*): height,
    # depth (== TICK_DEPTH), tick gap and the 90-degree turn read off the photo.
    assert f"ENGRAVE {part.NUMERAL_HEIGHT_MM:.2f} +/-0.10 HIGH" in notes
    assert f"DEPTH {part.TICK_DEPTH:.2f} +/-0.05" in notes
    assert f"START {part.NUMERAL_GAP_MM:.2f} +/-0.10 PAST THEIR" in notes
    assert part.NUMERAL_ROTATION_DEG == 90 and "TURNED\n   90 DEG" in notes
    tick_side_end = part.TICK_LENGTH + part.NUMERAL_GAP_MM  # from the edge the ticks hang from
    assert f"{tick_side_end:.2f} +/-0.10 ABOVE THE BOTTOM EDGE SHOWN" in notes
    assert "CDA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source
    assert "scale=(1, 2)" in source
    assert measuring_stick_spec.FRONT_VIEW_NOTE == "RULED FACE SCALE 1:1"
    assert '"*Back"' in source
    assert "_rotate_ruled_face(adapter, front)" in source
    assert "_add_scale_labels(adapter)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("measuring-stick")
    assert config["material"] == "C26000 brass, half-hard"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1


@pytest.fixture
def note_layout(monkeypatch, tmp_path):
    """Synthetic native extents, not measurements of the production sheet."""
    import _drawing_common as common

    events = []
    notes = {}
    state = SimpleNamespace(
        note_width=0.190, note_height=0.140, extent_state="valid",
        movement="apply", identity_state="same", visibility=True,
        zone_margin=0.0127, switch_at="never",
    )

    class Note:
        def __init__(self, name, x, y):
            self.name = name
            self.position = (x, y, 0.0)

        def GetAnnotation(self):
            return self

        def GetSpecificAnnotation(self):
            return self

        def GetLeaderCount(self):
            return 0

        def IsBomBalloon(self):
            return False

        def GetText(self):
            return {
                "Manufacturing Notes": measuring_stick_spec.DRAWING_NOTES,
                "Front View Note": measuring_stick_spec.FRONT_VIEW_NOTE,
                "Isometric View Note": measuring_stick_spec.ISOMETRIC_VIEW_NOTE,
            }[self.name]

        def GetExtent(self):
            events.append(("extent", self.name))
            if state.switch_at == self.name:
                adapter.swApp.ActiveDoc = object()
            if state.extent_state == "missing":
                return None
            if state.extent_state == "nonfinite":
                return (0, 0, 0, float("nan"), 1, 0)
            x, y, _z = self.position
            width, height = (0.070, 0.004)
            if self.name == "Manufacturing Notes":
                width, height = state.note_width, state.note_height
            return (x, y - height, 0.0, x + width, y, 0.0)

        def GetPosition(self):
            return self.position

        def SetPosition2(self, x, y, z):
            events.append(("move", self.name, (x, y, z)))
            if state.movement == "reject":
                return False
            if state.movement == "apply":
                self.position = (x, y, z)
            return True

    sheet = SimpleNamespace(
        GetProperties2=lambda: (3, 0, 1, 1, 0, 0.4318, 0.2794, 0),
        GetZoneMargin=lambda code: state.zone_margin,
    )
    class CallableModel(SimpleNamespace):
        def __call__(self):
            raise AssertionError("ActiveDoc is a COM property, not a callable method")

    model = CallableModel(
        GetType=lambda: 3, GetCurrentSheet=lambda: sheet,
    )

    def get_attr(obj, name):
        if obj is model and name == "Visible":
            return state.visibility
        value = getattr(obj, name)
        return value() if callable(value) else value

    app = SimpleNamespace(
        ActiveDoc=model,
        IsSame=lambda left, right: int(left is right and state.identity_state == "same"),
    )
    source = tmp_path / "measuring-stick.SLDPRT"
    source.touch()
    adapter = SimpleNamespace(
        currentModel=model, swApp=app,
        _get_attr_or_call=get_attr,
        _attempt=lambda call, default=None: call(),
    )

    async def open_model(path):
        assert path == str(source)
        return SimpleNamespace(is_success=True, data={})

    adapter.open_model = open_model

    def factory(actual, **kwargs):
        assert actual is adapter
        assert kwargs == {"property_view": "measuring-stick", "scale": (1.0, 1.0)}
        return model, sheet

    def linked(actual, name, x, y):
        assert actual is adapter
        events.append(("linked", name, (x, y)))
        notes[name] = Note(name, x, y)
        return notes[name]

    async def finalize(actual, outputs, **kwargs):
        assert actual is adapter
        assert outputs is drawing.OUTPUTS
        assert kwargs["scale"] == (1.0, 1.0)
        events.append(("finalize",))
        return {"status": "saved"}

    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *a, **k: {})
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *a: None)
    monkeypatch.setattr(drawing, "place_view", lambda *a, **k: SimpleNamespace(
        GetOutline=lambda: (0.250, 0.115, 0.350, 0.145),
    ))
    monkeypatch.setattr(drawing, "_rotate_ruled_face", lambda *a: None)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *a: None)
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *a, **k: None)
    monkeypatch.setattr(drawing, "_add_scale_labels", lambda *a: None)
    monkeypatch.setattr(drawing, "add_property_linked_note", linked)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    monkeypatch.setattr(common._sw_type_info, "early_bound_or_flag", lambda obj, *a: obj)
    return SimpleNamespace(
        state=state, events=events, notes=notes, adapter=adapter, factory=factory,
        run=lambda: asyncio.run(drawing.build(adapter, drawing_factory=factory)),
    )


def test_build_translates_full_native_note_once_before_save(note_layout):
    assert note_layout.run() == {"status": "saved"}
    moves = [event for event in note_layout.events if event[0] == "move"]
    assert len(moves) == 1
    assert moves[0][1] == "Manufacturing Notes"
    note = note_layout.notes["Manufacturing Notes"]
    assert note.GetText() == measuring_stick_spec.DRAWING_NOTES
    x0, y0, _z0, x1, y1, _z1 = note.GetExtent()
    assert 0.0157 <= x0 < x1 <= 0.247
    assert 0.0157 <= y0 < y1 <= 0.177
    assert note_layout.events.index(moves[0]) < note_layout.events.index(("finalize",))
    assert [event[1] for event in note_layout.events if event[0] == "linked"] == [
        "Manufacturing Notes", "Front View Note", "Isometric View Note",
    ]


@pytest.mark.parametrize("field,value", [
    ("note_height", 0.200), ("note_width", 0.300),
    ("extent_state", "missing"), ("extent_state", "nonfinite"),
    ("movement", "reject"), ("movement", "no_op"),
])
def test_build_rejects_unfitted_note_before_save(note_layout, field, value):
    setattr(note_layout.state, field, value)
    with pytest.raises((RuntimeError, ValueError), match="note|rectangle"):
        note_layout.run()
    assert ("finalize",) not in note_layout.events
    assert len([event for event in note_layout.events if event[0] == "move"]) <= 1


@pytest.mark.parametrize("field,value", [
    ("visibility", False), ("visibility", None),
    ("identity_state", "different"),
])
def test_build_rejects_invalid_document_before_extent(note_layout, field, value):
    setattr(note_layout.state, field, value)
    with pytest.raises(RuntimeError, match="drawing"):
        note_layout.run()
    assert not any(event[0] in {"extent", "move", "finalize"} for event in note_layout.events)


def test_already_fitted_native_note_needs_no_setter(note_layout):
    note_layout.state.note_height = 0.080
    assert note_layout.run() == {"status": "saved"}
    assert not any(event[0] == "move" for event in note_layout.events)
    assert ("extent", "Manufacturing Notes") in note_layout.events


def test_translation_uses_changed_native_sheet_margin(note_layout):
    note_layout.state.zone_margin = 0.020
    assert note_layout.run() == {"status": "saved"}
    x0, y0, _z0, x1, y1, _z1 = note_layout.notes["Manufacturing Notes"].GetExtent()
    assert 0.023 <= x0 < x1 <= 0.247
    assert 0.023 <= y0 < y1 <= 0.177
    assert len([event for event in note_layout.events if event[0] == "move"]) == 1


@pytest.mark.parametrize("name", [
    "Manufacturing Notes", "Front View Note", "Isometric View Note",
])
def test_native_measurement_switch_cannot_reach_setter_or_save(note_layout, name):
    note_layout.state.switch_at = name
    with pytest.raises(RuntimeError, match="active drawing"):
        note_layout.run()
    assert not any(event[0] in {"move", "finalize"} for event in note_layout.events)


def test_callable_active_document_is_read_as_property(note_layout):
    assert callable(note_layout.adapter.swApp.ActiveDoc)
    assert note_layout.run() == {"status": "saved"}
    assert ("finalize",) in note_layout.events
