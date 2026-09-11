"""Offline contracts for the simplicity-policy summing-lever sheet."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_summing_lever as lever
import draw_summing_lever as drawing
import summing_lever_notes as notes
import summing_lever_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import blind_cut_dia_mm
from _surface_finish import GROUND_UM


@pytest.fixture
def rendered_recipe(monkeypatch, tmp_path):
    """Exercise the recipe without COM, observing its manufacturing view package."""
    source = tmp_path / "summing-lever.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    model = SimpleNamespace(EditRebuild3=lambda: True)
    adapter = SimpleNamespace(currentModel=model)

    async def open_model(_path):
        return True

    adapter.open_model = open_model
    views, dimensions, datums, frames, finishes, callouts, notes_placed = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    monkeypatch.setattr(drawing, "check", lambda _label, result: result)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *a, **k: {})
    monkeypatch.setattr(
        drawing, "new_project_drawing", lambda *args, **kwargs: (model, None)
    )
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *args: None)

    def place(_adapter, _source, orientation, x, y, *, scale):
        view = SimpleNamespace(
            orientation=orientation,
            xy=(x, y),
            scale=scale,
            hidden=False,
            tangent_edges=None,
            annotations=[],
            SetDisplayTangentEdges2=lambda mode: setattr(view, "tangent_edges", mode),
            GetDisplayTangentEdges2=lambda: view.tangent_edges,
            UpdateViewDisplayGeometry=lambda: None,
        )
        views.append(view)
        return view

    def detail(_adapter, parent, **kwargs):
        view = place(
            _adapter, source, "detail", *kwargs["view_xy"], scale=kwargs["scale"]
        )
        view.parent = parent
        view.detail_label = kwargs["detail_label"]
        view.circle = (kwargs["center"], kwargs["radius"])
        return view

    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "create_detail_view", detail)
    monkeypatch.setattr(
        drawing,
        "set_hidden_lines_visible",
        lambda _a, view: setattr(view, "hidden", True),
    )
    # The plan projects model -Z upward, as the seat's Top view does.
    monkeypatch.setattr(
        drawing, "_point", lambda _a, _v, xyz: (xyz[0] / 1000, -xyz[2] / 1000)
    )

    def curate(_adapter, view, *, keep, view_label):
        result = [
            SimpleNamespace(name=name, view=view, text_xy=xy, reference=False)
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

    def precision(_adapter, annotations, values):
        for annotation in annotations:
            annotation.precision = values[annotation.name]

    def measured(_adapter, view, **kwargs):
        annotation = SimpleNamespace(
            name=kwargs.pop("label"),
            view=view,
            reference=False,
            basic=False,
            GetAnnotation=lambda: annotation,
            **kwargs,
        )
        dimensions.append(annotation)
        view.annotations.append(annotation)
        return annotation

    def reference(_adapter, annotation, *, label):
        annotation.reference = True

    def basic(_adapter, annotation, *, label):
        annotation.basic = True

    def bore(_adapter, view):
        annotation = SimpleNamespace(
            name="anchor bore", view=view, callout="DRILL THRU", precision=1
        )
        dimensions.append(annotation)
        return annotation

    def datum(_adapter, view, *, datum, label, **kwargs):
        datums.append((view, datum))

    def frame(_adapter, view, *, characteristic, tolerance, datums, quantity, **kwargs):
        frames.append((view, characteristic, tolerance, datums, quantity))

    def finish(_adapter, view, *, control, **kwargs):
        finishes.append((view, control.key, control.roughness_ra))

    def hole_callout(_adapter, view, *, process, **kwargs):
        callouts.append((view, process))

    def forbidden(*args, **kwargs):
        pytest.fail("only the spring-hole pattern control is allowlisted")

    for name in ("set_basic_dimensions", "project_part_pmi", "add_attached_note"):
        monkeypatch.setattr(drawing, name, forbidden, raising=False)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_move_dimension", move)
    monkeypatch.setattr(drawing, "set_dimension_precision", precision)
    monkeypatch.setattr(drawing, "_checked_dimension", measured)
    monkeypatch.setattr(drawing, "set_reference_dimension", reference)
    monkeypatch.setattr(drawing, "set_basic_dimension", basic)
    monkeypatch.setattr(drawing, "_add_anchor_bore", bore)
    monkeypatch.setattr(drawing, "add_datum_feature", datum)
    monkeypatch.setattr(drawing, "add_feature_control_frame", frame)
    monkeypatch.setattr(drawing, "add_surface_finish", finish)
    monkeypatch.setattr(drawing, "add_native_hole_callout", hole_callout)
    monkeypatch.setattr(
        drawing,
        "add_property_linked_note",
        lambda _a, name, *xy: notes_placed.append(name),
    )

    async def finalize(_adapter, outputs, **kwargs):
        return {"layout": kwargs["layout"], "outputs": outputs}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    result = asyncio.run(drawing.build(adapter))
    return SimpleNamespace(
        views=views,
        dimensions={item.name: item for item in dimensions},
        datums=datums,
        frames=frames,
        finishes=finishes,
        callouts=callouts,
        notes=notes_placed,
        result=result,
    )


def _views(package):
    by_orientation = {view.orientation: view for view in package.views}
    assert set(by_orientation) == {"*Top", "*Front", "detail", "*Isometric"}
    return (
        by_orientation["*Top"],
        by_orientation["*Front"],
        by_orientation["detail"],
        by_orientation["*Isometric"],
    )


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/summing-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/summing-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/summing-lever_drawing.png")
    assert DRAWINGS_BY_NAME["summing_lever"].script == Path(drawing.__file__).resolve()


def test_portrait_plan_over_end_profile_with_knife_edge_detail(rendered_recipe):
    top, front, detail, iso = _views(rendered_recipe)
    assert rendered_recipe.result["layout"] == DrawingLayout.PORTRAIT
    assert top.scale == front.scale == (1.0, 1.0)
    assert top.xy[0] == front.xy[0] and top.xy[1] > front.xy[1]
    for view in (top, front, detail):
        assert view.hidden
    assert top.tangent_edges == front.tangent_edges == 0
    assert detail.parent is front and detail.detail_label == "A"
    assert detail.scale == (4, 1)
    # The detail circle sits on the +Z trunnion hex, which faces the viewer.
    assert detail.circle == ((0.0, -spec.HEX_Z_OUTER / 1000), drawing.DETAIL_RADIUS)
    assert iso.scale == (1, 5)
    assert notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:5"
    assert rendered_recipe.notes == ["Manufacturing Notes", "Isometric View Note"]


def test_plan_reads_z_from_the_plate_end_and_x_from_the_knife_edge(rendered_recipe):
    top, front, detail, _iso = _views(rendered_recipe)
    dims = rendered_recipe.dimensions
    ridge = (0.0, spec.HEX_H / 2.0, -drawing.HEX_Z_MID)
    for name in ("anchor bore from knife edge", "spring-hole row X"):
        assert dims[name].view is top and dims[name].p0 == ridge
    assert dims["anchor bore from knife edge"].expected_mm == -spec.TIP_X
    assert dims["spring-hole row X"].expected_mm == spec.HOLE_X
    assert dims["spring-hole start Z"].expected_mm == pytest.approx(9.90)
    assert dims["spring-hole pitch"].expected_mm == spec.CHANNEL_PITCH
    trunnion = spec.HEX_Z_OUTER - spec.HEX_Z_INNER
    assert dims["upper trunnion length"].expected_mm == trunnion
    assert dims["lower trunnion length"].expected_mm == trunnion
    assert dims["body length"].expected_mm == spec.PLATE_L
    assert dims["overall length"].expected_mm == 2.0 * spec.HEX_Z_OUTER
    assert dims["overall length"].reference
    assert dims["trunnion across flats"].expected_mm == spec.HEX_W
    # The pivot diameter is authored on the Front plane, imported there, and
    # moved onto the plan where the cylinder reads as a band.
    assert dims["CylDia"].view is top and dims["CylDia"].text_xy == drawing.CYL_DIA_XY
    assert front.annotations == [dims["plate thickness"], dims["anchor eye height"]]
    assert dims["plate thickness"].expected_mm == spec.PLATE_T
    assert dims["anchor eye height"].expected_mm == 2.0 * spec.ANCHOR_R
    assert detail.annotations == [dims["trunnion vertex height"]]
    assert dims["trunnion vertex height"].expected_mm == spec.HEX_H


def test_only_the_spring_pattern_carries_geometric_control(rendered_recipe):
    top, _front, detail, _iso = _views(rendered_recipe)
    dims = rendered_recipe.dimensions
    assert rendered_recipe.frames == [(top, "position", "0.30", ("A", "B"), "20X")]
    assert rendered_recipe.datums == [(top, "A"), (top, "B")]
    assert {name for name, item in dims.items() if getattr(item, "basic", False)} == {
        "spring-hole row X",
        "spring-hole start Z",
        "spring-hole pitch",
    }
    assert spec.GEOMETRIC_TOLERANCES_MM == {"spring-hole pattern position": "0.30"}
    assert rendered_recipe.callouts == [(top, "#47 DRILL")]
    assert dims["anchor bore"].callout == "DRILL THRU"
    # Knife edge: the one running surface, at the ground grade the policy
    # reserves for it, on the enlarged detail.
    assert rendered_recipe.finishes == [(detail, "knife_edge_ridge", "0.8")]
    (control,) = spec.SURFACE_FINISHES
    assert control.roughness_um == GROUND_UM
    assert control.face.contains_z_mm == drawing.HEX_Z_MID


def test_decimals_carry_the_tolerance(rendered_recipe):
    dims = rendered_recipe.dimensions
    for name in (
        "PlateWidth",
        "CylDia",
        "AnchorOuterDia",
        "upper trunnion length",
        "body length",
        "lower trunnion length",
        "overall length",
        "anchor bore from knife edge",
        "plate thickness",
        "anchor eye height",
        "anchor bore",
    ):
        assert dims[name].precision == 1, name
    # The hex bears in the knife mount: two places hold it.
    for name in ("trunnion across flats", "trunnion vertex height"):
        assert dims[name].precision == 2, name


def test_notes_are_two_process_facts_and_the_marks_match_the_recipe() -> None:
    assert notes.DRAWING_NOTES.count("\n") == 1
    assert "DO NOT BREAK" in notes.DRAWING_NOTES
    assert "PER SUPPLIED MODEL" in notes.DRAWING_NOTES
    for restated in ("HEX", "THICK", "LONG", "#47", "PITCH", "MACHINE"):
        assert restated not in notes.DRAWING_NOTES
    assert lever.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) == marked
    assert marked == {"PlateWidth", "CylDia", "AnchorOuterDia"}


def test_part_and_drawing_share_the_spec() -> None:
    assert lever.HOLE_SPEC is spec.HOLE_SPEC
    assert blind_cut_dia_mm(spec.HOLE_SPEC) == pytest.approx(1.994)
    for name in (
        "PLATE_W",
        "PLATE_L",
        "PLATE_T",
        "CYL_R",
        "ANCHOR_R",
        "HEX_W",
        "HEX_H",
        "HEX_DEPTH",
        "HOLE_X",
        "HOLE_COUNT",
        "CHANNEL_PITCH",
    ):
        assert getattr(lever, name) == getattr(spec, name), name
    part_source = "".join(Path(lever.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    import _config

    config = _config.parts("summing-lever")
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["finish"] == "green enamel; knife edges + anchor bore machined"
    assert int(config["quantity"]) == 1
