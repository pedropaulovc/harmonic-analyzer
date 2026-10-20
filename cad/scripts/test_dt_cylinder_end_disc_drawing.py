"""Offline contracts for the south cylinder-bank end disc (MHA-DT-26) drawing."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_dt_cylinder_end_disc as part
import dt_cylinder_end_disc_spec as spec
import draw_dt_cylinder_end_disc as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cylinder-end-disc.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cylinder-end-disc.pdf")
    assert DRAWINGS_BY_NAME["dt_cylinder_end_disc"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_is_on_the_axial_section_with_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SECTION_KEEP) == marked
    assert {
        (feature, name) for feature, names in spec.DRAWING_PRECISION.items() for name in names
    } == {(feature, name) for feature, names in spec.DRAWING_DIMENSIONS.items() for name in names}
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": spec.BORE_CALLOUT,
        "DiscThick": spec.THICKNESS_CALLOUT,
    }


def test_loose_thickness_is_compensated_without_moving_the_gear_datum() -> None:
    import cylinder_bank_layout as bank
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(spec.THICKNESS_PLACES)
    assert spec.WASHER_THICK_TOLERANCE_MM == band
    assert spec.DRAWING_PRECISION_BY_NAME["DiscThick"] == spec.THICKNESS_PLACES == 1
    assert spec.WASHER_THICK - band >= 2.0 - 1e-9
    assert bank.DATUM_CHAIN_STACK["south disc, mic-compensated"] == bank.MIC_RESIDUAL
    assert bank.MIC_RESIDUAL < band
    assert bank.FRONT_STRAP_INNER_Z + spec.WASHER_THICK == pytest.approx(
        bank.G0_CAM_FACE_Z
    )


def test_drilled_bore_uses_the_title_block_band_and_clears_its_named_arbor() -> None:
    import dt_cylinder_gear_shaft_spec as arbor
    from _printed_tolerance import drilled_oversize_mm

    assert spec.WASHER_BORE_BAND == (drilled_oversize_mm(), 0.0)
    assert spec.WASHER_BORE > arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0]
    assert spec.BORE_CALLOUT == "DRILL THRU\nCLEARANCE ON MHA-DT-13"


def test_single_brass_disc_uses_the_owning_geometry_and_ordinary_od_band() -> None:
    import _config
    from _printed_tolerance import printed_band_mm

    row = _config.parts("dt-cylinder-end-disc")
    assert spec.WASHER_OD == part.DISC_DIA == 55.0
    assert spec.OUTSIDE_DIA_BAND_MM == printed_band_mm(spec.OUTSIDE_DIA_PLACES) == 0.8
    assert part.BORE_DIA == spec.WASHER_BORE == 9.6
    assert part.DISC_THICK == spec.WASHER_THICK
    assert part.MATERIAL == row["material"] == "Brass"
    assert row["material_specification"] == "C36000 free-machining brass"
    assert row["quantity"] == 1


def test_disc_has_running_air_and_continuous_ring_capture_at_the_worst_limits() -> None:
    import cylinder_bank_layout as bank
    import ch_connecting_rod_spec as rod
    import dt_cylinder_gear_spec as gear

    budget = bank.SOUTH_DISC_CLEARANCE
    for name in ("cone worst", "engaged pinion worst"):
        assert budget[name] > spec.RUNNING_AIR_MM + spec.CLEARANCE_SPARE_MM
    # The whole bore edge remains captured, although the outermost ring rim
    # extends beyond this disc. Full-rim coverage is not axial retention.
    assert spec.WASHER_OD / 2.0 < gear.ECCENTRICITY + rod.RING_OUTER_RADIUS
    assert budget["retaining land"] > 0.0


def test_gear_od_disc_fails_the_real_drive_envelope(monkeypatch) -> None:
    import cylinder_bank_layout as bank
    import dt_cylinder_gear_spec as gear

    monkeypatch.setattr(spec, "WASHER_OD", gear.OUTSIDE_DIA)
    with pytest.raises(AssertionError, match="south retaining disc cone worst"):
        spec.installed_clearance_budget(sum(bank.DATUM_CHAIN_STACK.values()))


def test_disc_envelope_books_the_actual_south_datum_band_once() -> None:
    import cone_line
    import cylinder_bank_layout as bank

    datum = sum(bank.DATUM_CHAIN_STACK.values())
    normal = spec.installed_clearance_budget(datum)
    shifted = spec.installed_clearance_budget(datum + 0.10)
    assert normal["cone worst"] - shifted["cone worst"] == pytest.approx(
        0.10 * cone_line.SIN_I
    )
    assert shifted["engaged pinion worst"] == normal["engaged pinion worst"]
    assert shifted["retaining land"] == normal["retaining land"]


def test_drawing_creates_and_dimensions_a_native_axial_section(
    monkeypatch, tmp_path
) -> None:
    source = tmp_path / "disc.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    front, section, iso = object(), object(), object()
    annotations = [object(), object(), object()]
    placed, sections, imported, hidden, callouts, precisions = [], [], [], [], [], []

    async def open_model(_path):
        return None

    async def finalize(*_args, **_kwargs):
        return {"slddrw": "disc.SLDDRW"}

    def place(_adapter, _source, orientation, *_xy, **_kwargs):
        placed.append(orientation)
        return {"*Front": front, "*Isometric": iso}[orientation]

    def cut(_adapter, parent, **kwargs):
        sections.append((parent, kwargs))
        return section

    def curate(_adapter, view, **kwargs):
        imported.append((view, kwargs))
        return annotations

    adapter = SimpleNamespace(currentModel=object(), open_model=open_model)
    monkeypatch.setattr(drawing, "check", lambda *_args: None)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        drawing, "new_project_drawing", lambda *_args, **_kwargs: (object(), object())
    )
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_args: None)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "create_section_view", cut)
    monkeypatch.setattr(
        drawing,
        "model_points_in_view",
        lambda _adapter, _view, points, **_kwargs: [(point[2], 0.0) for point in points],
    )
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(
        drawing,
        "set_hidden_lines_removed",
        lambda _adapter, view: hidden.append(view),
    )
    monkeypatch.setattr(
        drawing,
        "assert_imported_precision",
        lambda _adapter, items, places: precisions.append((items, places)),
    )
    monkeypatch.setattr(
        drawing,
        "set_dimension_callouts",
        lambda _adapter, items, texts, **kwargs: callouts.append((items, texts, kwargs)),
    )
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)

    assert asyncio.run(drawing.build(adapter)) == {"slddrw": "disc.SLDDRW"}
    assert placed == ["*Front", "*Isometric"]
    assert sections == [
        (
            front,
            {
                "line_start": drawing.SECTION_LINE[0],
                "line_end": drawing.SECTION_LINE[1],
                "view_xy": drawing.SECTION_CENTER,
                "section_label": "A",
                "scale": drawing.VIEW_SCALE,
                "label": "south end disc axial centre section",
            },
        )
    ]
    assert imported == [
        (
            section,
            {
                "keep": drawing.SECTION_KEEP,
                "view_label": "disc axial section",
                "dimensions_by_feature": spec.DRAWING_DIMENSIONS,
            },
        )
    ]
    assert hidden == [front, section, iso]
    assert precisions == [(annotations, spec.DRAWING_PRECISION_BY_NAME)]
    assert callouts == [(annotations, drawing.DIMENSION_CALLOUTS, {"location": "below"})]


@pytest.mark.parametrize("north", [(0.0, 0.0), (0.0, 0.01), (0.01, 0.01)])
def test_axial_section_rejects_a_nonhorizontal_or_degenerate_axis(
    monkeypatch, north
) -> None:
    monkeypatch.setattr(
        drawing, "model_points_in_view", lambda *_args, **_kwargs: ((0.0, 0.0), north)
    )
    with pytest.raises(RuntimeError, match="horizontal turning axis"):
        drawing._require_horizontal_axis(object(), object())
