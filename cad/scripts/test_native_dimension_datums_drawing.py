"""Exact source-size attachment is distinct from merely selecting a dimension."""

from types import SimpleNamespace
from pathlib import Path

import pytest

import _drawing_native_datums as module
from test_native_callouts_drawing import stationary_setup


def setup_constructor(monkeypatch):
    setup, dimension = stationary_setup(monkeypatch)
    adapter, view, datum, annotations, *_ = setup
    annotations.remove(datum)
    calls = []
    monkeypatch.setattr(module, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(module, "annotation_box", setup[-1])
    monkeypatch.setattr(module, "null_callout", lambda: None)
    monkeypatch.setattr(
        module,
        "dispatch_array",
        lambda values: SimpleNamespace(varianttype=8201, values=values),
    )
    dimension.dimension.Name = "BoreCutDia"
    dimension.dimension.FullName = "BoreCutDia@BoreProfile@cone-gear.Part"
    dimension.specific.IsReferenceDim = lambda: False
    dimension.specific.GetNameForSelection = lambda: (
        "BoreCutDia@BoreProfile@DrawingView1"
    )
    source = SimpleNamespace(
        GetType=lambda: 1, GetPathName=lambda: "C:/guarded/cone-gear.SLDPRT"
    )
    view.ReferencedDocument = source
    view.ReferencedConfiguration = "T120"

    def named(_adapter, feature, name):
        assert _adapter.currentModel is source
        assert (feature, name) == ("BoreProfile", "BoreCutDia")
        return object(), dimension.dimension

    monkeypatch.setattr(module, "_named_dimension", named)
    adapter.currentModel.Extension = SimpleNamespace(
        SelectByID2=lambda *args: calls.append(("select", args)) or True,
    )
    adapter.currentModel.SelectionManager = SimpleNamespace(
        GetSelectedObjectCount2=lambda _mark: 1,
        GetSelectedObjectType3=lambda _index, _mark: 14,
        GetSelectedObject6=lambda _index, _mark: dimension.specific,
    )

    def insert():
        calls.append(("insert",))
        annotations.append(datum)
        datum.entities = ()
        return datum.specific

    def attach(payload):
        calls.append(("attach", payload.varianttype))
        datum.entities = tuple(payload.values)
        return True

    datum.SetAttachedEntities = attach
    datum.specific.SetLabel = lambda label: calls.append(("label", label)) or True
    adapter.currentModel.InsertDatumTag2 = insert
    adapter.currentModel.ClearSelection2 = lambda _all: calls.append(("clear",))
    adapter.currentModel.EditRebuild3 = lambda: calls.append(("rebuild",)) or True
    return setup, dimension, calls


def create(setup, dimension):
    return module.add_dimension_datum(
        setup[0],
        setup[1],
        dimension_annotation=dimension,
        source_feature="BoreProfile",
        source_dimension="BoreCutDia",
        datum="A",
        label="cone gear bore axis",
    )


def test_explicit_typed_attachment_occurs_after_insertion_finalization(monkeypatch):
    setup, dimension, calls = setup_constructor(monkeypatch)
    assert create(setup, dimension) is setup[2].specific
    assert [call[0] for call in calls] == [
        "clear",
        "select",
        "insert",
        "label",
        "clear",
        "rebuild",
        "attach",
        "rebuild",
    ]
    assert next(call for call in calls if call[0] == "attach") == ("attach", 8201)
    assert not setup[2].moves


def test_same_dimension_name_cannot_substitute_for_exact_source_identity(monkeypatch):
    setup, dimension, calls = setup_constructor(monkeypatch)
    monkeypatch.setattr(module, "_named_dimension", lambda *_: (object(), object()))
    with pytest.raises(RuntimeError, match="exact source feature"):
        create(setup, dimension)
    assert not calls


def test_reference_dimension_is_not_an_imported_source_size(monkeypatch):
    setup, dimension, calls = setup_constructor(monkeypatch)
    dimension.specific.IsReferenceDim = lambda: True
    with pytest.raises(RuntimeError, match="imported source size"):
        create(setup, dimension)
    assert not calls


def test_wrong_selection_identity_fails_before_insert(monkeypatch):
    setup, dimension, calls = setup_constructor(monkeypatch)
    setup[0].currentModel.SelectionManager.GetSelectedObject6 = lambda *_: object()
    with pytest.raises(RuntimeError, match="exact source display"):
        create(setup, dimension)
    assert "insert" not in [call[0] for call in calls]


def test_failed_named_selector_has_no_fallback(monkeypatch):
    setup, dimension, calls = setup_constructor(monkeypatch)
    setup[0].currentModel.Extension.SelectByID2 = lambda *_: False
    with pytest.raises(RuntimeError, match="selection failed"):
        create(setup, dimension)
    assert "insert" not in [call[0] for call in calls]


def test_unbound_insertion_is_not_accepted_when_explicit_attachment_rejects(
    monkeypatch,
):
    setup, dimension, _calls = setup_constructor(monkeypatch)
    setup[2].SetAttachedEntities = lambda _payload: False
    with pytest.raises(RuntimeError, match="attachment failed"):
        create(setup, dimension)


def test_untyped_dispatch_array_is_rejected(monkeypatch):
    setup, dimension, calls = setup_constructor(monkeypatch)
    monkeypatch.setattr(
        module, "dispatch_array", lambda values: SimpleNamespace(varianttype=8204)
    )
    with pytest.raises(RuntimeError, match="typed dispatch"):
        create(setup, dimension)
    assert "attach" not in [call[0] for call in calls]


def test_existing_datum_label_cannot_be_duplicated(monkeypatch):
    setup, dimension, calls = setup_constructor(monkeypatch)
    setup[3].append(setup[2])
    with pytest.raises(RuntimeError, match="already exists"):
        create(setup, dimension)
    assert not calls


def test_attachment_source_value_change_is_rejected(monkeypatch):
    setup, dimension, _calls = setup_constructor(monkeypatch)
    attach = setup[2].SetAttachedEntities

    def change_value(payload):
        dimension.dimension_value += 0.001
        return attach(payload)

    setup[2].SetAttachedEntities = change_value
    with pytest.raises(RuntimeError, match="configuration/value changed"):
        create(setup, dimension)


def test_legacy_audit_requires_actual_generic_bounds_for_dimension_datums():
    import _drawing_common as common

    adapter = SimpleNamespace(
        _attempt=lambda call: call(),
        _get_attr_or_call=lambda obj, name: getattr(obj, name)(),
    )
    annotation = SimpleNamespace(GetAttachedEntityTypes=lambda: (14,))
    with pytest.raises(RuntimeError, match="explicit generic GD&T"):
        common._measured_gdt_box(adapter, annotation, 2)
    assert common._measured_gdt_box(
        adapter,
        annotation,
        2,
        measure_gdt=lambda *_: (0.177, 0.144, 0.184, 0.151),
    ) == (0.177, 0.144, 0.184, 0.151)


@pytest.mark.parametrize("bounds", [(), (0, 0, 0, 1), (0, 0, float("nan"), 1)])
def test_legacy_generic_callback_never_falls_back_on_invalid_bounds(bounds):
    import _drawing_common as common

    with pytest.raises(RuntimeError, match="invalid native bounds"):
        common._measured_gdt_box(None, None, 2, measure_gdt=lambda *_: bounds)


def test_explicit_audit_threads_measurement_callback_without_importing_pilot(
    monkeypatch,
):
    import _drawing_common as common
    from _drawing_layout_check import DrawableRegion

    observed = []
    callback = object()
    monkeypatch.setattr(
        common,
        "collect_layout_elements",
        lambda _adapter, **kwargs: (
            observed.append(kwargs["measure_gdt"]) or [],
            [],
            DrawableRegion(0, 0, 1, 1),
        ),
    )
    common.check_drawing_layout(None, measure_gdt=callback)
    assert observed == [callback]


def test_native_datum_constructor_stays_out_of_other_drawing_helper_closures():
    from _buildgraph import module_deps_of

    scripts = Path(__file__).parent
    users = tuple(
        script.name
        for script in scripts.glob("draw_*.py")
        if any(
            Path(dep).name == "_drawing_native_datums.py"
            for dep in module_deps_of(script)
        )
    )
    assert users == ("draw_cone_gear.py",)
    assert not any(
        Path(dep).name.startswith("_drawing_native")
        for dep in module_deps_of(scripts / "_drawing_common.py")
    )
