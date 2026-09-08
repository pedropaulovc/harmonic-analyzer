"""Offline contracts for the rack-pinion drawing (batch gear pattern)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import build_rack_pinion as part
import draw_rack_pinion as drawing
import rack_pinion_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rack-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rack-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rack-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["rack_pinion"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia"}


def test_gear_data_block_specifies_the_tooth_system() -> None:
    data = spec.GEAR_DATA
    for field in (
        "GEAR DATA",
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "MODULE (mm",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (mm",
        "OUTSIDE DIAMETER (mm)",
        "WHOLE DEPTH (mm)",
        "FACE WIDTH (mm)",
        "TOOTH FORM",
    ):
        assert field in data, field
    assert "120" in data
    assert "X.XX" not in data
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_manufacturing_notes_present() -> None:
    assert "CUT TEETH PER GEAR DATA" in spec.DRAWING_NOTES
    assert "DEBUR" not in spec.DRAWING_NOTES
    assert "X.XX" not in spec.DRAWING_NOTES


def test_native_gdt_controls_bore_datum_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_native_axis_datum(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert source.count("add_surface_finish(") == 1
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "THRU - REAM"}
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_native_axis_datum_preserves_stability_limit_and_clear_layout() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    datum_a = source[source.index("add_native_axis_datum("):]
    datum_a = datum_a[:datum_a.index("    )")]
    assert "entity=bore_edge" in datum_a
    assert "source_path=SOURCE" in datum_a
    assert "radius_m=BORE_DIA / 2000.0" in datum_a
    assert "stability_tolerance_m=0.0001" in datum_a
    assert "shoulder=True" in datum_a
    assert "edge_xy=" not in datum_a
    assert "symbol_xy=" not in datum_a
    assert drawing.FRONT_KEEP["BoreDia"] == (
        drawing.FRONT_CENTER[0] - 0.062, drawing.FRONT_CENTER[1] + 0.038,
    )
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 2}


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("rack-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "gear teeth cut; polished brass"
    assert int(config["quantity"]) == 1


def test_finish_layout_preserves_semantic_bore_and_separates_native_datum() -> None:
    assert drawing.BORE_FINISH_POSITION == (
        drawing.FRONT_CENTER[0] + 0.058, drawing.FRONT_CENTER[1] - 0.062,
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    finish = source[source.index("finish = add_surface_finish("):]
    assert "symbol_xy=BORE_FINISH_POSITION" in finish
    assert "entity=bore_edge" in finish
    assert "leader_attach_xy=model_point_in_view(" in finish
    assert "(BORE_DIA / 2000.0, 0.0, FACE_WIDTH / 1000.0)" in finish
    assert "_reattach_bore_finish(adapter, front, bore_edge, finish)" in finish
    assert "IsSame(finish_entities[0], bore_edge)) != 1" in source
    assert "finish_annotation.IsDangling()" in source


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spec.BORE_DIA
    assert part.BORE_DIAMETER == spec.BORE_DIA
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert 'control=surface_finish_by_key(SURFACE_FINISHES,"bore")' in sheet_source
    assert "roughness_ra=" not in sheet_source


@pytest.fixture
def finish_reattachment(monkeypatch):
    """Exercise the recipe helper without loading a SolidWorks COM object."""
    state = SimpleNamespace(
        calls=[], data=SimpleNamespace(), select_result=True, selected_count=1,
        attach_result=True, rebuild_result=True, attachment_mode="replace",
        entities=(), types=(), dangling=False, equality_mode="identity",
        after_rebuild=None,
    )
    front = object()

    def select(append, data):
        state.calls.append("select")
        assert append is False
        assert data is state.data
        assert data.View is front
        assert (data.X, data.Y, data.Z) == (0.2225, 0.175, spec.FACE_WIDTH / 2000.0)
        return state.select_result

    edge = SimpleNamespace(Select4=select)
    state.selected = edge

    def selected_count(mark):
        state.calls.append("selection-count")
        assert mark == -1
        return state.selected_count

    def selected_object(index, mark):
        state.calls.append("selected-object")
        assert (index, mark) == (1, -1)
        return state.selected

    manager = SimpleNamespace(
        CreateSelectData=lambda: state.data,
        GetSelectedObjectCount2=selected_count,
        GetSelectedObject6=selected_object,
    )
    typed_entities = object()

    def dispatch(entities):
        state.calls.append("dispatch-array")
        assert len(entities) == 1 and entities[0] is edge
        return typed_entities

    def attach(entities):
        state.calls.append("reattach")
        assert entities is typed_entities
        if state.attachment_mode == "replace":
            state.entities, state.types = (edge,), (1,)
        return state.attach_result

    annotation = SimpleNamespace(
        SetAttachedEntities=attach,
        GetAttachedEntities3=lambda: state.entities,
        GetAttachedEntityTypes=lambda: state.types,
        IsDangling=lambda: state.dangling,
    )
    state.annotation = annotation
    finish = SimpleNamespace(GetAnnotation=lambda: state.annotation)

    def rebuild():
        state.calls.append("rebuild")
        if state.after_rebuild is not None:
            state.after_rebuild()
        return state.rebuild_result

    def clear(all_selections):
        assert all_selections is True
        state.calls.append("clear")

    def same(left, right):
        phase = "attachment" if "rebuild" in state.calls else "selection"
        state.calls.append(f"{phase}-identity")
        assert right is edge
        if state.equality_mode == f"unknown-{phase}":
            return -1
        return int(left is right)

    model = SimpleNamespace(
        SelectionManager=manager, ClearSelection2=clear, EditRebuild3=rebuild,
    )
    adapter = SimpleNamespace(currentModel=model, swApp=SimpleNamespace(IsSame=same))

    def project(actual_adapter, view, xyz, *, label):
        state.calls.append("project")
        assert actual_adapter is adapter and view is front
        assert xyz == (spec.BORE_DIA / 2000.0, 0.0, spec.FACE_WIDTH / 1000.0)
        assert label == "rack bore finish semantic rim point"
        return (0.2225, 0.175)

    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "dispatch_array", dispatch)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    state.run = lambda: drawing._reattach_bore_finish(adapter, front, edge, finish)
    state.edge = edge
    return state


def test_finish_reattachment_selects_semantic_edge_at_projected_point(finish_reattachment):
    state = finish_reattachment
    state.run()
    assert state.calls == [
        "clear", "project", "select", "selection-count", "selected-object",
        "selection-identity", "dispatch-array", "reattach", "clear", "rebuild",
        "attachment-identity",
    ]
    assert state.entities == (state.edge,)
    assert state.types == (1,)


@pytest.mark.parametrize(("field", "value", "message"), [
    ("data", None, "no selection data"),
    ("select_result", False, "semantic edge selection failed"),
    ("selected_count", 0, "exactly one selected edge"),
    ("selected_count", 2, "exactly one selected edge"),
    ("selected", None, "wrong semantic edge"),
    ("selected", object(), "wrong semantic edge"),
    ("equality_mode", "unknown-selection", "wrong semantic edge"),
    ("annotation", None, "no annotation"),
])
def test_finish_reattachment_rejects_bad_selection_before_mutation(
    finish_reattachment, field, value, message,
):
    state = finish_reattachment
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert "reattach" not in state.calls
    assert "rebuild" not in state.calls


@pytest.mark.parametrize(("field", "message", "rebuild_count"), [
    ("attach_result", "semantic reattachment failed", 0),
    ("rebuild_result", "reattachment rebuild failed", 1),
])
def test_finish_reattachment_checks_mutation_results(
    finish_reattachment, field, message, rebuild_count,
):
    state = finish_reattachment
    setattr(state, field, False)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert state.calls.count("rebuild") == rebuild_count


@pytest.mark.parametrize(("field", "value"), [
    ("entities", ()),
    ("entities", None),
    ("entities", (None,)),
    ("entities", (object(),)),
    ("entities", (object(), object())),
    ("types", ()),
    ("types", None),
    ("types", (2,)),
    ("types", (1, 1)),
    ("equality_mode", "unknown-attachment"),
    ("dangling", True),
])
def test_finish_reattachment_rechecks_exact_semantic_attachment_after_rebuild(
    finish_reattachment, field, value,
):
    state = finish_reattachment
    state.after_rebuild = lambda: setattr(state, field, value)
    with pytest.raises(RuntimeError, match="lost its semantic edge attachment"):
        state.run()
    assert state.calls.count("reattach") == state.calls.count("rebuild") == 1


def test_finish_reattachment_rejects_successful_noop(finish_reattachment):
    state = finish_reattachment
    state.attachment_mode = "noop"
    with pytest.raises(RuntimeError, match="lost its semantic edge attachment"):
        state.run()
    assert state.calls.count("reattach") == state.calls.count("rebuild") == 1
