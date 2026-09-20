"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

from pathlib import Path

import _fit_limits
import build_cone_gear_shaft as part
import cone_gear_shaft_spec
import draw_cone_gear_shaft as drawing
import pytest
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_section_fits_are_toleranced_on_the_model() -> None:
    """All five turned lands ride ONE shared fit class, applied to the model.

    Spelled as callout text the band is frozen: SolidWorks prints it verbatim
    and never re-renders it, so the mm->inch flip in issue #290 would leave
    "+0.00/-0.02" reading as inches on every land. The identity assertion also
    stops a local retype from silently forking the shared class.
    """
    assert cone_gear_shaft_spec.SECTION_DIA_BAND is _fit_limits.SHAFT_H
    # Applied in a loop over the five sections, so the AST reports the f-string
    # source rather than five literal keys.
    assert model_toleranced_dimensions(part) == {
        ("f'Sec{section}Profile'", "f'Sec{section}Dia'"): (
            "*deviations(SECTION_DIA_BAND)"
        )
    }
    assert "for section in range(5)" in Path(part.__file__).read_text(encoding="utf-8")


def test_display_precision_is_owned_by_the_part() -> None:
    """Policy rule 2: the .SLDPRT carries the places, the sheet reads them back."""
    assert "draw_cone_gear_shaft.py" in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in (
        Path(part.__file__).read_text(encoding="utf-8")
    )
    # Every diameter carries the shared band, so its places are only spelling;
    # the stations carry no band, so their places ARE the grade they are held
    # to, and the .XXX grade is what keeps a 6.900 land longer than the
    # 6.5-wide gear face that has to sit between its two shoulders.
    by_name = cone_gear_shaft_spec.DRAWING_PRECISION_BY_NAME
    assert by_name == {
        "Sec0Dia": 3,
        "Sec1Dia": 3,
        "Sec2Dia": 3,
        "Sec3Dia": 3,
        "Sec4Dia": 3,
        "Sec0End": 3,
        "Sec1End": 3,
        "Sec2End": 3,
        "Sec3End": 3,
        "Sec4End": 3,
        "ShoulderR": 2,
    }
    ends = cone_gear_shaft_spec.SECTION_ENDS
    land_lengths = [b - a for a, b in zip(ends, ends[1:])]
    assert min(land_lengths) - 2 * 0.13 > 6.5


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-gear-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-gear-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-gear-shaft_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_gear_shaft"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_gear_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_gear_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.SIDE_KEEP)
        | set(drawing.SIDE_DIAMETERS)
        | set(drawing.DETAIL_DIAMETERS)
    )
    assert kept == marked
    # Nothing is imported twice, and the donor hands over exactly the five
    # diameters it was placed for.
    assert set(drawing.DONOR_KEEP) == set(drawing.SIDE_DIAMETERS) | set(
        drawing.DETAIL_DIAMETERS
    )
    assert not set(drawing.SIDE_KEEP) & set(drawing.DONOR_KEEP)
    assert part.SECTIONS is cone_gear_shaft_spec.SECTIONS
    assert drawing.SHAFT_LENGTH == cone_gear_shaft_spec.SHAFT_LENGTH
    assert drawing.SECTION_DIAS == cone_gear_shaft_spec.SECTION_DIAS


def test_every_diameter_stands_on_its_own_shoulder() -> None:
    """A diameter may only be dragged to the station its profile sketch is on.

    Land 0's circle is the large-end face; every other land is sketched on an
    offset plane at its END station and extruded back to that face, so the
    dimension lands on the shoulder it measures instead of piling up with the
    other four at z=0 (which is what forced the old leadered end view).
    """
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'mode="offset", base_plane="Front Plane", offset=end_z' in source
    assert "ExtrusionParameters(depth=end_z, reverse_direction=i > 0)" in source
    assert "await adapter.create_sketch(plane_name)" in source

    ends = cone_gear_shaft_spec.SECTION_ENDS
    sheet = drawing.SIDE_CENTER[0] + cone_gear_shaft_spec.SHAFT_LENGTH / 2000.0
    # Sec1Dia's text sits on the Ø9.525 shoulder; the three tip diameters live
    # in the detail, whose fence covers every station they attach to.
    assert drawing.SIDE_DIAMETERS["Sec1Dia"][0] == pytest.approx(
        sheet - ends[1] / 1000.0, abs=5e-4
    )
    fence_lo = drawing.DETAIL_MODEL_Z - drawing.DETAIL_RADIUS_MM
    fence_hi = drawing.DETAIL_MODEL_Z + drawing.DETAIL_RADIUS_MM
    assert fence_lo < ends[1] and ends[-1] < fence_hi


def test_sections_are_a_monotonic_stepped_shaft() -> None:
    """The v2 journal and four legacy gear sections step down monotonically."""
    sections = cone_gear_shaft_spec.SECTIONS
    assert len(sections) == 5
    dias = cone_gear_shaft_spec.SECTION_DIAS
    ends = cone_gear_shaft_spec.SECTION_ENDS
    assert all(a > b for a, b in zip(dias, dias[1:]))
    assert all(a < b for a, b in zip(ends, ends[1:]))
    # The integral bearing journal fits the v2 post at 0.05 diametral
    # clearance; every downstream gear seat keeps its existing diameter.
    assert cone_gear_shaft_spec.JOURNAL_BORE_DIA == pytest.approx(12.2808)
    assert cone_gear_shaft_spec.JOURNAL_CLEARANCE == pytest.approx(0.05)
    assert cone_gear_shaft_spec.JOURNAL_DIA == pytest.approx(12.2308)
    assert cone_gear_shaft_spec.JOURNAL_END == pytest.approx(43.011)
    assert dias == pytest.approx((12.2308, 9.525, 6.35, 3.175, 1.5875))
    assert cone_gear_shaft_spec.FRONT_STUB == pytest.approx(61.9068609979)
    assert cone_gear_shaft_spec.TIP_BLOCK_NORTH_FACE_STATION == pytest.approx(
        147.27232594770454
    )
    assert cone_gear_shaft_spec.ADJUSTER_EMBED == pytest.approx(6.0)
    assert cone_gear_shaft_spec.ADJUSTER_CUP_RIM_STATION == pytest.approx(
        141.27232594770454
    )
    assert cone_gear_shaft_spec.MCM_94025A150_CUP_DEPTH == pytest.approx(1.98755)
    assert cone_gear_shaft_spec.T006_TIP_STATION == pytest.approx(143.25987594770454)
    assert cone_gear_shaft_spec.SHAFT_LENGTH == (
        cone_gear_shaft_spec.FRONT_STUB + cone_gear_shaft_spec.T006_TIP_STATION
    )
    # The journal and all preceding gear-seat endpoints stay put; only the
    # terminal 1/16-in endpoint follows the stock cup apex.
    stub_delta = cone_gear_shaft_spec.FRONT_STUB - 12.3
    assert ends[1:-1] == pytest.approx(
        tuple(
            old_end + stub_delta + cone_gear_shaft_spec.GEAR_AXIS_SHIFT
            for old_end in (154.2, 161.1, 168.0)
        )
    )
    assert ends[-1] == pytest.approx(
        cone_gear_shaft_spec.FRONT_STUB + 143.25987594770454
    )
    # The shortened terminal stub still supports the entire 4 mm bushing.
    assert cone_gear_shaft_spec.TIP_STUB_START_STATION == pytest.approx(
        122.5853574197016
    )
    assert cone_gear_shaft_spec.TIP_STUB_LENGTH == pytest.approx(20.6745185280)
    assert (
        cone_gear_shaft_spec.TIP_STUB_START_STATION
        <= cone_gear_shaft_spec.TIP_BUSHING_START_STATION
    )
    assert (
        cone_gear_shaft_spec.TIP_BUSHING_END_STATION
        <= cone_gear_shaft_spec.T006_TIP_STATION
    )


def test_shoulder_roots_are_modelled_not_noted() -> None:
    """The root radius is geometry with a size, not a sentence in a note block."""
    assert cone_gear_shaft_spec.FILLET_RADIUS == pytest.approx(0.10)
    # It has to clear the ~0.19 mm of air on each side of every step.
    assert cone_gear_shaft_spec.FILLET_RADIUS < 0.19
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "add_fillet(FILLET_RADIUS, fillet_edges, propagate=False)" in source
    assert 'name_last_feature(adapter, "ShoulderFillets")' in source
    assert 'name_dimensions(adapter, "ShoulderFillets", ["ShoulderR"])' in source
    # One feature, one dimension, one quantity prefix -- not four dimensions.
    assert drawing.DIMENSION_CALLOUTS == {"ShoulderR": "4X"}
    assert not hasattr(cone_gear_shaft_spec, "DRAWING_NOTES")
    assert "add_property_linked_note" not in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )


def test_the_sheet_carries_no_datums_or_feature_control_frames() -> None:
    """Simplicity policy rule 3: no GD&T on a hand-built hobby shaft."""
    assert not hasattr(cone_gear_shaft_spec, "PART_DATUMS")
    assert not hasattr(cone_gear_shaft_spec, "GEOMETRIC_CONTROLS")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for banned in (
        "project_part_pmi(",
        "add_feature_control_frame(",
        "add_datum_feature(",
    ):
        assert banned not in source
    # The two lands that RUN keep their roughness symbol; nothing else does.
    assert source.count("add_surface_finish(") == 2
    assert tuple(control.key for control in cone_gear_shaft_spec.SURFACE_FINISHES) == (
        "pivot_journal",
        "tip_journal",
    )
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in part_source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.SIDE_SCALE == (1, 1)  # full length, no reduction
    assert drawing.DETAIL_SCALE == (3, 1)  # the Ø1.588 tip cluster
    assert drawing.ISO_SCALE == (1, 2)  # reduced pictorial
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The end view is gone: its only content was a pile of leadered diameters.
    assert '"*Front"' in source  # the donor, and only as a donor
    assert "delete_view(adapter, donor)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-gear-shaft")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
