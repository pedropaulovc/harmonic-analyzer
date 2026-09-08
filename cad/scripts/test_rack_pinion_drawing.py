"""Offline contracts for the rack-pinion drawing (batch gear pattern)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import _rack_bore_finish as finish_helper
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
    assert source.count("add_rack_bore_finish(adapter, front, bore_edge, symbol_xy=BORE_FINISH_POSITION)") == 1
    helper_source = Path(finish_helper.__file__).read_text(encoding="utf-8")
    assert helper_source.count("InsertSurfaceFinishSymbol3(") == 1
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
    assert "add_rack_bore_finish(adapter, front, bore_edge, symbol_xy=BORE_FINISH_POSITION)" in source
    finish = Path(finish_helper.__file__).read_text(encoding="utf-8")
    assert "*symbol_xy" in finish
    assert "_early_bound(bore_edge, \"IEntity\").Select4(False, data)" in finish
    assert "rim_xy = model_point_in_view(" in finish
    assert "(BORE_DIA / 2000.0, 0.0, FACE_WIDTH / 1000.0)" in finish
    assert "_validate_surface_finish_control_face(" in finish
    for forbidden in ("SetPosition", "SetLeaderAttachmentPointAtIndex", "SetAttachedEntities"):
        assert forbidden not in finish
    assert "IsSame(finish_entities[0], bore_edge)) != 1" in finish
    assert "finish_annotation.IsDangling()" in finish


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spec.BORE_DIA
    assert part.BORE_DIAMETER == spec.BORE_DIA
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    helper_source = "".join(Path(finish_helper.__file__).read_text(encoding="utf-8").split())
    assert drawing.add_rack_bore_finish is finish_helper.add_rack_bore_finish
    assert finish_helper.SURFACE_FINISHES is spec.SURFACE_FINISHES
    assert finish_helper.BORE_DIA == spec.BORE_DIA
    assert finish_helper.FACE_WIDTH == spec.FACE_WIDTH
    assert 'control=surface_finish_by_key(SURFACE_FINISHES,"bore")' in helper_source
    assert "roughness_ra=" not in sheet_source


@pytest.fixture
def finish_insertion(monkeypatch):
    """No fake exposes position, endpoint, or reattachment setters."""
    state = SimpleNamespace(
        calls=[], data=SimpleNamespace(), select_result=True, selected_count=1,
        rebuild_result=True, inventory_mode="insert", inventory=[],
        dangling=False, equality_mode="identity", after_rebuild=None,
        text_result=True, text_mode="write", texts={}, style_result=0, symbol=1,
        leader_count=1, points=(.278, .113, .0015, .23, .15, .0015, .222499999953, .175, .0015),
        face_result="valid", fail_rebuild_at=None, mutate_rebuild_at=2, activate_result=True,
    )
    front = SimpleNamespace(GetAnnotations=lambda: state.inventory, GetName2=lambda: "Front test view")

    def select(append, data):
        state.calls.append("select")
        assert append is False and data is state.data and data.View is front
        assert (data.X, data.Y, data.Z) == (.2225, .175, spec.FACE_WIDTH / 2000.0)
        return state.select_result

    edge = SimpleNamespace(Select4=select)
    state.selected, state.entities, state.types = edge, (edge,), (1,)

    def selected_count(mark):
        state.calls.append("selection-count")
        assert mark == -1
        return state.selected_count

    def selected_object(index, mark):
        state.calls.append("selected-object")
        assert (index, mark) == (1, -1)
        return state.selected

    manager = SimpleNamespace(CreateSelectData=lambda: state.data,
                              GetSelectedObjectCount2=selected_count, GetSelectedObject6=selected_object)

    def style(*arguments):
        state.calls.append("style")
        assert arguments == (2, 0, True, False, False, False)
        return state.style_result

    annotation = SimpleNamespace(
        GetType=lambda: 7, SetLeader3=style, GetAttachedEntities3=lambda: state.entities,
        GetAttachedEntityTypes=lambda: state.types, IsDangling=lambda: state.dangling,
        GetLeaderCount=lambda: state.leader_count, GetLeaderPointsAtIndex=lambda _index: state.points,
    )
    state.annotation = annotation

    def set_text(slot, value):
        state.calls.append(f"text-{slot}")
        assert slot == 8 and value == f"Ra {spec.SURFACE_FINISHES[0].roughness_ra}"
        if state.text_mode == "write":
            state.texts[slot] = value
        return state.text_result

    finish = SimpleNamespace(GetAnnotation=lambda: state.annotation, SetText=set_text,
                             GetText=lambda slot: state.texts.get(slot, ""), GetSymbol=lambda: state.symbol)
    state.finish = finish

    def insert(*arguments):
        state.calls.append("insert")
        assert arguments == (1, 2, *drawing.BORE_FINISH_POSITION, 0., 0, 10, "", "", "", "", "", "", "")
        if state.inventory_mode == "insert":
            state.inventory = [annotation]
        return state.finish

    def rebuild():
        state.calls.append("rebuild")
        if state.after_rebuild is not None and state.calls.count("rebuild") == state.mutate_rebuild_at:
            state.after_rebuild()
        if state.calls.count("rebuild") == state.fail_rebuild_at:
            return False
        return state.rebuild_result

    def clear(all_selections):
        assert all_selections is True
        state.calls.append("clear")

    def activate(name):
        state.calls.append("activate")
        assert name == front.GetName2()
        return state.activate_result

    def same(left, right):
        phase = "inventory" if right is annotation else "attachment" if "rebuild" in state.calls else "selection"
        state.calls.append(f"{phase}-identity")
        assert right is edge or right is annotation
        if state.equality_mode == f"unknown-{phase}":
            return -1
        return int(left is right)

    model = SimpleNamespace(SelectionManager=manager, ClearSelection2=clear, EditRebuild3=rebuild,
                            Extension=SimpleNamespace(InsertSurfaceFinishSymbol3=insert), ActivateView=activate)
    adapter = SimpleNamespace(currentModel=model, swApp=SimpleNamespace(IsSame=same))

    def project(actual_adapter, view, xyz, *, label):
        state.calls.append("project")
        assert actual_adapter is adapter and view is front
        assert xyz == (spec.BORE_DIA / 2000.0, 0., spec.FACE_WIDTH / 1000.0)
        assert label == "rack bore finish semantic rim point"
        return (.2225, .175)

    def validate(entity, *, entity_type, control, label):
        state.calls.append("validate-face")
        assert entity is edge and entity_type == "EDGE"
        assert control is spec.SURFACE_FINISHES[0]
        assert label == "rack pinion bore finish"
        if state.face_result == "reject":
            raise RuntimeError("test face control mismatch")

    monkeypatch.setattr(finish_helper, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(finish_helper, "_validate_surface_finish_control_face", validate)
    monkeypatch.setattr(finish_helper, "model_point_in_view", project)
    state.run = lambda: finish_helper.add_rack_bore_finish(adapter, front, edge, symbol_xy=drawing.BORE_FINISH_POSITION)
    state.edge = edge
    return state


def test_finish_insertion_validates_face_then_selects_and_inserts_once(finish_insertion):
    state = finish_insertion
    assert state.run() is state.finish
    assert state.calls == [
        "validate-face", "activate", "clear", "project", "select", "selection-count", "selected-object",
        "selection-identity", "insert", "rebuild", "text-8", "style", "clear", "rebuild",
        "inventory-identity", "attachment-identity",
    ]
    assert state.entities == (state.edge,) and state.types == (1,)
    for forbidden in ("SetPosition2", "SetPosition", "SetLeaderAttachmentPointAtIndex", "SetAttachedEntities"):
        assert not hasattr(state.annotation, forbidden)


def test_finish_face_mismatch_rejected_before_any_selection_or_insertion(finish_insertion):
    state = finish_insertion
    state.face_result = "reject"
    with pytest.raises(RuntimeError, match="face control mismatch"):
        state.run()
    assert state.calls == ["validate-face"]


@pytest.mark.parametrize(("field", "value", "message"), [
    ("activate_result", False, "view activation failed"),
    ("data", None, "no selection data"),
    ("select_result", False, "semantic edge selection failed"),
    ("selected_count", 0, "exactly one selected edge"),
    ("selected_count", 2, "exactly one selected edge"),
    ("selected", None, "wrong semantic edge"),
    ("selected", object(), "wrong semantic edge"),
    ("equality_mode", "unknown-selection", "wrong semantic edge"),
])
def test_finish_insertion_rejects_bad_selection_before_insertion(finish_insertion, field, value, message):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert "insert" not in state.calls and "rebuild" not in state.calls


@pytest.mark.parametrize(("field", "value", "message", "rebuilds"), [
    ("finish", None, "insertion returned null", 0),
    ("annotation", None, "no annotation", 1),
    ("text_result", False, "roughness assignment failed", 1),
    ("style_result", 1, "leader style failed", 1),
])
def test_finish_insertion_checks_each_mutation_result(finish_insertion, field, value, message, rebuilds):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == rebuilds


@pytest.mark.parametrize(("field", "value", "message"), [
    ("inventory_mode", "noop", "insertion inventory mismatch"),
    ("equality_mode", "unknown-inventory", "insertion inventory mismatch"),
    ("text_mode", "noop", "manufacturing content changed"),
    ("symbol", 0, "manufacturing content changed"),
])
def test_finish_insertion_rejects_noops_and_readback_failure(finish_insertion, field, value, message):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == 2


@pytest.mark.parametrize("phase", [1, 2])
def test_finish_each_rebuild_result_is_required(finish_insertion, phase):
    state = finish_insertion
    state.fail_rebuild_at = phase
    with pytest.raises(RuntimeError, match="rebuild failed"):
        state.run()
    assert state.calls.count("rebuild") == phase
    if phase == 1:
        assert "text-8" not in state.calls and "style" not in state.calls


@pytest.mark.parametrize("phase", [1, 2])
@pytest.mark.parametrize(("field", "value"), [
    ("entities", ()), ("entities", None), ("entities", (None,)),
    ("entities", (object(),)), ("entities", (object(), object())),
    ("types", ()), ("types", None), ("types", (2,)), ("types", (1, 1)),
    ("equality_mode", "unknown-attachment"), ("dangling", True),
])
def test_finish_insertion_rechecks_semantic_attachment_after_rebuild(finish_insertion, field, value, phase):
    state = finish_insertion
    state.mutate_rebuild_at = phase
    state.after_rebuild = lambda: setattr(state, field, value)
    with pytest.raises(RuntimeError, match="lost its semantic edge attachment"):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == 2


@pytest.mark.parametrize("inventory", [[], [SimpleNamespace(GetType=lambda: 7)],
                                        [SimpleNamespace(GetType=lambda: 7), SimpleNamespace(GetType=lambda: 7)]])
def test_finish_inventory_after_rebuild_must_be_exact_returned_annotation(finish_insertion, inventory):
    state = finish_insertion
    state.after_rebuild = lambda: setattr(state, "inventory", inventory)
    with pytest.raises(RuntimeError, match="insertion inventory mismatch"):
        state.run()


@pytest.mark.parametrize(("field", "value", "message"), [
    ("leader_count", 0, "exactly one leader"), ("leader_count", 2, "exactly one leader"),
    ("points", (), "points are invalid"), ("points", None, "points are invalid"),
    ("points", (0, 0, 0), "points are invalid"),
    ("points", (float("nan"), 0, 0, .2225, .175, .0015), "points are invalid"),
    ("points", (.278, .113, 0, .2225, .175, float("inf")), "points are invalid"),
    ("points", (.278, .113, 0, 0, 0, 0), "off the intended right rim"),
    ("points", (.278, .113, 0, .22250002, .175, .0015), "off the intended right rim"),
    ("points", (.278, .113, 0, .2225, .17500002, .0015), "off the intended right rim"),
])
def test_finish_leader_requires_finite_shape_and_exact_right_rim(finish_insertion, field, value, message):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()


def test_finish_straight_leader_with_native_readback_point_is_valid(finish_insertion):
    state = finish_insertion
    state.points = (.278, .113, .0015, .222499999953, .175, .0015)
    assert state.run() is state.finish
