"""Offline contracts for the simplicity-policy arbor-pedestal sheet."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import arbor_pedestal_spec as spec
import build_arbor_pedestal as part
import draw_arbor_pedestal as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import blind_cut_dia_mm


@pytest.fixture
def rendered_recipe(monkeypatch, tmp_path):
    """Exercise the recipe without COM, observing its manufacturing view package."""
    source = tmp_path / "arbor-pedestal.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    model = SimpleNamespace(EditRebuild3=lambda: True)
    adapter = SimpleNamespace(currentModel=model)

    async def open_model(_path):
        return True

    adapter.open_model = open_model
    views, dimensions, finishes, callouts = [], [], [], []
    monkeypatch.setattr(drawing, "check", lambda _label, result: result)
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
            shaded=False,
            tangent_edges=None,
            annotations=[],
            SetDisplayTangentEdges2=lambda mode: setattr(view, "tangent_edges", mode),
            GetDisplayTangentEdges2=lambda: view.tangent_edges,
            UpdateViewDisplayGeometry=lambda: None,
        )
        views.append(view)
        return view

    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(
        drawing,
        "set_hidden_lines_visible",
        lambda _a, view: setattr(view, "hidden", True),
    )
    monkeypatch.setattr(
        drawing,
        "set_high_quality_shaded_with_edges",
        lambda _a, view, *, label: setattr(view, "shaded", True),
    )
    monkeypatch.setattr(
        drawing, "_point", lambda _a, _v, xyz: (xyz[0] / 1000, xyz[1] / 1000)
    )

    def curate(_adapter, view, *, keep, view_label):
        result = [
            SimpleNamespace(name=name, view=view, text_xy=xy, reference=False)
            for name, xy in keep.items()
        ]
        view.annotations.extend(result)
        dimensions.extend(result)
        return result

    def set_callouts(_adapter, annotations, values):
        for annotation in annotations:
            annotation.callout = values.get(annotation.name, "")

    def precision(_adapter, annotations, values):
        for annotation in annotations:
            annotation.precision = values[annotation.name]

    def measured(_adapter, view, **kwargs):
        annotation = SimpleNamespace(
            name=kwargs.pop("label"), view=view, reference=False, **kwargs
        )
        dimensions.append(annotation)
        view.annotations.append(annotation)
        return annotation

    def reference(_adapter, annotation, *, label):
        annotation.reference = True

    def finish(_adapter, view, *, control, **kwargs):
        finishes.append((view, control.key, control.roughness_ra))

    def hole_callout(_adapter, view, *, process, **kwargs):
        callouts.append((view, process))

    def forbidden(*args, **kwargs):
        pytest.fail("a pedestal is not allowlisted for geometric controls")

    for name in (
        "add_datum_feature",
        "add_feature_control_frame",
        "set_basic_dimension",
        "set_basic_dimensions",
        "project_part_pmi",
        "add_attached_note",
        "add_note",
        "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, forbidden, raising=False)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "set_dimension_callouts", set_callouts)
    monkeypatch.setattr(drawing, "set_dimension_precision", precision)
    monkeypatch.setattr(drawing, "set_reference_dimension", reference)
    monkeypatch.setattr(drawing, "_checked_dimension", measured)
    monkeypatch.setattr(drawing, "_point_bore_leader_at_near_edge", lambda *a: None)
    monkeypatch.setattr(
        drawing,
        "_add_crown_radius",
        lambda _a, view: measured(
            _a, view, label="crown radius", expected_mm=spec.TOP_RADIUS, precision=1
        ),
    )
    monkeypatch.setattr(
        drawing,
        "_add_taper_angle",
        lambda _a, view: setattr(
            measured(
                _a,
                view,
                label="taper angle",
                expected_mm=spec.TAPER_ANGLE_DEG,
                precision=2,
            ),
            "reference",
            True,
        ),
    )
    monkeypatch.setattr(drawing, "add_surface_finish", finish)
    monkeypatch.setattr(drawing, "add_native_hole_callout", hole_callout)
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *args, **kwargs: True)

    async def finalize(_adapter, outputs, **kwargs):
        return {"layout": kwargs["layout"], "outputs": outputs}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    result = asyncio.run(drawing.build(adapter))
    return SimpleNamespace(
        views=views,
        dimensions={item.name: item for item in dimensions},
        finishes=finishes,
        callouts=callouts,
        result=result,
    )


def _views(package):
    by_orientation = {view.orientation: view for view in package.views}
    assert set(by_orientation) == {"*Front", "*Top", spec.PICTORIAL_VIEW}
    return (
        by_orientation["*Front"],
        by_orientation["*Top"],
        by_orientation[spec.PICTORIAL_VIEW],
    )


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/arbor-pedestal_drawing.png")
    assert DRAWINGS_BY_NAME["arbor_pedestal"].script == Path(drawing.__file__).resolve()


def test_views_are_aligned_hidden_line_orthographics_plus_rear_pictorial(
    rendered_recipe,
):
    front, top, pictorial = _views(rendered_recipe)
    assert rendered_recipe.result["layout"] == DrawingLayout.LANDSCAPE
    assert top.xy[0] == front.xy[0] and top.xy[1] > front.xy[1]
    for view in (front, top):
        assert view.hidden and view.tangent_edges == 0 and not view.shaded
    # The hold-down hole sits on the -Z flange; the part-owned rear isometric
    # is the only octant that shows it, and it is held to the shaded policy.
    assert pictorial.shaded and not pictorial.hidden
    assert spec.PICTORIAL_VIEW == part.PICTORIAL_VIEW
    assert "name_rear_isometric(adapter, PICTORIAL_VIEW)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")


def test_each_view_dimensions_from_one_origin(rendered_recipe):
    front, top, _pictorial = _views(rendered_recipe)
    dims = rendered_recipe.dimensions
    seat = (-spec.FOOT_WIDTH / 4.0, 0.0, spec.FOOT_DEPTH / 2.0)
    for name in ("bore height from foot seat", "overall height"):
        assert dims[name].view is front and dims[name].p0 == seat
    assert dims["bore height from foot seat"].expected_mm == spec.BORE_HEIGHT
    assert dims["overall height"].expected_mm == spec.BORE_HEIGHT + spec.TOP_RADIUS
    assert dims["overall height"].reference and dims["overall height"].precision == 1
    flush = (spec.FOOT_WIDTH / 4.0, spec.FOOT_HEIGHT, spec.FOOT_DEPTH / 2.0)
    for name in ("strap depth", "hold-down hole from flush face"):
        assert dims[name].view is top and dims[name].p0 == flush
    assert dims["strap depth"].expected_mm == spec.STRAP_T
    assert dims["hold-down hole from flush face"].expected_mm == 13.0
    assert dims["hold-down hole from left side"].expected_mm == spec.FOOT_WIDTH / 2.0
    assert {name for name, item in dims.items() if item.view is front} == {
        "FootHt",
        "BoreDia",
        "bore height from foot seat",
        "overall height",
        "crown radius",
        "taper angle",
    }
    assert {name for name, item in dims.items() if item.view is top} == {
        "Width",
        "Depth",
        "strap depth",
        "hold-down hole from flush face",
        "hold-down hole from left side",
    }


def test_only_the_reamed_bore_carries_a_fit_and_the_taper_is_reference(
    rendered_recipe,
):
    dims = rendered_recipe.dimensions
    assert dims["BoreDia"].callout == "REAM THRU; ON C/L"
    assert dims["BoreDia"].precision == 2
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }
    assert spec.BORE_DIA_BAND == (0.03, 0.0)
    for name in ("Width", "Depth", "FootHt", "strap depth", "crown radius"):
        assert dims[name].precision == 1, name
    # The 6 mm lip leaves ~1.4 mm of wall around the hole; the two-place band
    # (+-0.51) keeps it inside, the one-place band (+-0.8) would not.
    assert dims["hold-down hole from flush face"].precision == 2
    assert dims["taper angle"].reference
    assert 3.0 < spec.TAPER_ANGLE_DEG < 4.0
    assert not any(
        getattr(item, "callout", "") for name, item in dims.items() if name != "BoreDia"
    )


def test_hold_down_hole_is_a_native_drill_callout_on_the_lip_centre(rendered_recipe):
    _front, top, _pictorial = _views(rendered_recipe)
    assert rendered_recipe.callouts == [(top, "DRILL")]
    assert spec.SCREW_Z == -5.0
    assert part.SCREW_Z == spec.SCREW_Z
    hole = spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is hole
    assert (hole.kind, hole.size, hole.fit) == ("clearance", "#4", "normal")
    assert spec.SCREW_HOLE_DIA == part.SCREW_HOLE_DIA == blind_cut_dia_mm(hole)


def test_running_bore_and_mating_seat_are_the_only_finish_symbols(rendered_recipe):
    front, _top, _pictorial = _views(rendered_recipe)
    assert rendered_recipe.finishes == [
        (front, "arbor_bore", "1.6"),
        (front, "foot_seat", "3.2"),
    ]
    by_key = {control.key: control for control in spec.SURFACE_FINISHES}
    assert by_key["arbor_bore"].face.contains_y_mm == spec.BORE_HEIGHT
    assert by_key["foot_seat"].face.normal == (0, -1, 0)
    assert by_key["foot_seat"].face.offset_mm == 0.0


def test_spec_is_the_single_source_of_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) == marked
    assert marked == {"Width", "Depth", "FootHt", "BoreDia"}
    assert not hasattr(spec, "DRAWING_NOTES")
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")


def test_no_dead_band_between_wizard_correction_and_the_builder_assert() -> None:
    """What the wizard will FORCE must cover what the builder will ACCEPT.

    These were two different literals -- `_holes` only corrected a drift over
    0.05 mm, while `build_arbor_pedestal` rejected anything over 0.005. A #4
    clearance initialized at 3.2512 instead of 3.264 drifts 0.0128 and lands in
    the gap: the wizard leaves it, the builder refuses it, and NO value of the
    spec pin can satisfy both (Codex #422). Both now read one constant.
    """
    import _holes

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "DIAMETER_TOLERANCE_MM" in source, "builder must use the shared tolerance"
    assert not re.search(r"[<>]=?\s*0\.0*5\b|[<>]=?\s*0\.005\d*", source), (
        "builder compares the cut diameter against a numeric literal; use "
        "_holes.DIAMETER_TOLERANCE_MM so the wizard's correction threshold and "
        "this acceptance threshold cannot separate into a dead band again"
    )
    holes_source = Path(_holes.__file__).read_text(encoding="utf-8")
    assert (
        "abs(initialized_dia_mm - pinned_dia_mm) > DIAMETER_TOLERANCE_MM"
        in holes_source
    )
    rounding_gap = abs(3.2639 - _holes.CLEARANCE_MM[("#4", "normal")])
    wrong_row_drift = abs(
        _holes.CLEARANCE_MM[("#4", "normal")] - _holes.CLEARANCE_MM[("#3", "loose")]
    )
    assert rounding_gap < _holes.DIAMETER_TOLERANCE_MM < wrong_row_drift


def test_part_stamps_make_flexible_material_and_protective_finish() -> None:
    import _config

    assert part.MATERIAL == "Plain Carbon Steel"
    config = _config.parts("arbor-pedestal")
    assert config["material"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["finish"] == (
        "BLACK JAPAN/ENAMEL; MASK BORE AND FOOT SEAT; OIL BARE MACHINED SURFACES"
    )
    assert config["process"] == "machined from solid stock or casting"
    # Two identical pedestals: the south support plus the north one rotated
    # 180 about Y (build_drive_train_assembly places both).
    assert int(config["quantity"]) == 2
