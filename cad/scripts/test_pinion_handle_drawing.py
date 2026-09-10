"""Behavioral release contract for the simplicity-policy pinion-handle sheet."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import draw_pinion_handle as drawing
import pinion_handle_spec as spec
from _drawing_registry import DrawingLayout


@pytest.fixture
def rendered_recipe(monkeypatch, tmp_path):
    """Exercise the recipe without COM, observing its manufacturing view package."""
    source = tmp_path / "pinion-handle.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    model = SimpleNamespace(EditRebuild3=lambda: True)
    adapter = SimpleNamespace(currentModel=model)

    async def open_model(_path):
        return True

    adapter.open_model = open_model
    views, dimensions, notes = [], [], []
    monkeypatch.setattr(drawing, "check", lambda _label, result: result)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_source_bodies", lambda _model: ("body", "rod"))
    monkeypatch.setattr(drawing, "read_required_properties", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        drawing, "new_project_drawing", lambda *args, **kwargs: (model, None)
    )
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *args: None)

    def place(_adapter, _source, orientation, x, y, *, scale):
        view = SimpleNamespace(
            orientation=orientation,
            xy=(x, y),
            scale=scale,
            body=None,
            hidden=False,
            Angle=0.0,
            annotations=[],
            section=False,
        )
        views.append(view)
        return view

    def section(_adapter, parent, **kwargs):
        view = place(
            _adapter, source, "section", *kwargs["view_xy"], scale=kwargs["scale"]
        )
        view.section = True
        view.parent = parent
        view.body = parent.body
        return view

    def delete(_adapter, view):
        views.remove(view)
        return True

    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "create_section_view", section)
    monkeypatch.setattr(drawing, "delete_view", delete)
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: iter(views))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: str(id(view)))
    monkeypatch.setattr(
        drawing,
        "_isolate_body",
        lambda _a, view, body, **kw: setattr(view, "body", body),
    )
    monkeypatch.setattr(
        drawing,
        "set_hidden_lines_visible",
        lambda _a, view: setattr(view, "hidden", True),
    )
    monkeypatch.setattr(
        drawing, "_point", lambda _a, _v, xyz: (xyz[0] / 1000, xyz[1] / 1000)
    )

    def curate(_adapter, view, *, keep, view_label):
        result = [
            SimpleNamespace(name=name, view=view, text_xy=xy)
            for name, xy in keep.items()
        ]
        view.annotations.extend(result)
        dimensions.extend(result)
        return result

    def move(_adapter, annotation, target, position, *, source_view):
        annotation.view.annotations.remove(annotation)
        annotation.view = target
        annotation.text_xy = position
        target.annotations.append(annotation)
        return annotation

    def callouts(_adapter, annotations, values):
        for annotation in annotations:
            annotation.callout = values.get(annotation.name, "")

    def precision(_adapter, annotations, values):
        for annotation in annotations:
            annotation.precision = values[annotation.name]

    def measured(_adapter, view, **kwargs):
        annotation = SimpleNamespace(name=kwargs.pop("label"), view=view, **kwargs)
        dimensions.append(annotation)
        return annotation

    def forbidden(*args, **kwargs):
        pytest.fail(
            "pinion handle is not allowlisted for geometric controls or roughness"
        )

    for name in (
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish",
        "set_basic_dimension",
        "set_basic_dimensions",
        "project_part_pmi",
    ):
        monkeypatch.setattr(drawing, name, forbidden, raising=False)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(
        drawing, "dimension_name", lambda _a, annotation: annotation.name
    )
    monkeypatch.setattr(drawing, "_move_dimension", move)
    monkeypatch.setattr(drawing, "set_dimension_callouts", callouts)
    monkeypatch.setattr(drawing, "set_dimension_precision", precision)
    monkeypatch.setattr(drawing, "_checked_dimension", measured)
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *args, **kwargs: True)
    monkeypatch.setattr(drawing, "_add_body_centerline", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "add_note", lambda *args: object())
    monkeypatch.setattr(
        drawing, "add_property_linked_note", lambda _a, name, *xy: notes.append(name)
    )

    async def finalize(_adapter, outputs, **kwargs):
        return {"layout": kwargs["layout"], "outputs": outputs}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    result = asyncio.run(drawing.build(adapter))
    return SimpleNamespace(
        views=views,
        dimensions={item.name: item for item in dimensions},
        notes=notes,
        result=result,
    )


def test_policy_views_expose_both_components_and_blind_socket(rendered_recipe):
    package = rendered_recipe
    orthographic = [view for view in package.views if view.orientation != "*Isometric"]
    assert all(view.hidden for view in orthographic)
    (iso,) = [view for view in package.views if view.orientation == "*Isometric"]
    assert iso.body is None and iso.Angle == 0.0
    assert package.result["layout"] == DrawingLayout.LANDSCAPE
    (section,) = [view for view in package.views if view.section]
    assert section.body == section.parent.body == "body"
    hole = package.dimensions["RodHoleDia"]
    assert hole.view.body == "body" and hole.view.orientation == "*Top"
    assert "REAM" in hole.callout and "THRU" in hole.callout
    bore = package.dimensions["TubeId"]
    assert (
        bore.view is section and "REAM" in bore.callout and "THRU" not in bore.callout
    )
    assert package.dimensions["TubeLen"].view is section
    rod = package.dimensions["RodDia"]
    assert rod.view is package.dimensions["RodSpan"].view
    assert abs(rod.view.Angle) == pytest.approx(1.5707963267948966)
    for name in ("GripDia", "TubeOd"):
        assert package.dimensions[name].view.orientation == "*Right"
    front = section.parent
    top = hole.view
    right = package.dimensions["GripDia"].view
    assert front.xy[0] == top.xy[0]
    assert front.xy[1] == right.xy[1]
    assert not spec.SURFACE_FINISHES


def test_body_dimensions_are_direct_baselines_not_note_substitutes(rendered_recipe):
    dimensions = rendered_recipe.dimensions
    axial = [
        dimensions[name]
        for name in (
            "hub projection",
            "socket end to crown root",
            "body overall length",
        )
    ]
    assert {item.p0 for item in axial} == {(0.0, spec.TUBE_OD / 4.0, drawing.HUB_END_Z)}
    assert all(item.orientation == "horizontal" for item in axial)
    assert [item.expected_mm for item in axial] == pytest.approx([12.0, 21.0, 24.0])
    assert dimensions["socket end to cross-hole axis"].expected_mm == pytest.approx(
        16.5
    )
    assert dimensions["socket end to cross-hole axis"].center
    assert dimensions["rod placement from body axis"].expected_mm == pytest.approx(32.0)
    assert dimensions["rod placement from body axis"].center
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked <= dimensions.keys()
    assert "Manufacturing Notes" in rendered_recipe.notes
    assert 1 <= len(spec.DRAWING_NOTES.splitlines()) <= 4
    assert not any(character.isdigit() for character in spec.DRAWING_NOTES)
    for forbidden in (
        "DATUM",
        "BASIC",
        "+/-",
        "MATERIAL",
        "TOLERANCE",
        "FINISH",
        "TURN ",
    ):
        assert forbidden not in spec.DRAWING_NOTES.upper()


def test_body_hole_and_socket_fit_limits_remain_native():
    hole_low = spec.ROD_HOLE_DIA + spec.ROD_HOLE_REAM_BAND[1]
    hole_high = spec.ROD_HOLE_DIA + spec.ROD_HOLE_REAM_BAND[0]
    assert (hole_low, hole_high) == pytest.approx((6.000, 6.010))
    assert (
        spec.TUBE_ID + spec.TUBE_ID_BAND[1],
        spec.TUBE_ID + spec.TUBE_ID_BAND[0],
    ) == pytest.approx((8.010, 8.025))


def test_recipe_preserves_fine_fit_digits_without_tightening_routine_features(
    rendered_recipe,
):
    dims = rendered_recipe.dimensions
    assert dims["RodDia"].precision == 1
    assert dims["RodHoleDia"].precision == dims["TubeId"].precision == 3
    assert dims["GripDia"].precision == dims["TubeOd"].precision == 2
    assert dims["CapR"].precision == 2
    assert dims["RodSpan"].precision == 1


def test_wrong_native_edge_measurement_blocks_release(monkeypatch):
    display = SimpleNamespace(
        GetDimension2=lambda _index: SimpleNamespace(SystemValue=0.023)
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_point", lambda _a, _v, xyz: xyz[:2])
    monkeypatch.setattr(drawing, "add_edge_dimension", lambda *args, **kwargs: display)
    with pytest.raises(RuntimeError, match="measured 23, expected 24"):
        drawing._checked_dimension(
            None,
            None,
            p0=(0, 0, 16.5),
            p1=(0, 0, -7.5),
            text_xy=(0.1, 0.2),
            label="body overall",
            expected_mm=24.0,
            orientation="horizontal",
        )


def test_refused_native_dimension_move_blocks_release(monkeypatch):
    display = SimpleNamespace(
        GetNameForSelection=lambda: "TubeId@TubeProfile@Drawing View1"
    )
    annotation = SimpleNamespace(name="TubeId", GetSpecificAnnotation=lambda: display)
    target = SimpleNamespace(GetAnnotations=lambda: ())
    model = SimpleNamespace(
        ClearSelection2=lambda *_args: None,
        EditRebuild3=lambda: True,
        DragModelDimension=lambda *_args: None,
        ActivateView=lambda *_args: True,
        Extension=SimpleNamespace(SelectByID2=lambda *_args: True),
    )
    adapter = SimpleNamespace(currentModel=model)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: item.name)
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "socket section")
    monkeypatch.setattr(drawing, "null_callout", lambda: None)
    with pytest.raises(RuntimeError, match="native dimension did not move"):
        drawing._move_dimension(
            adapter, annotation, target, (0.3, 0.14), source_view=object()
        )
