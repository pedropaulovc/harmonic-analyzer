"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

from pathlib import Path

import _config
import _fit_limits
import build_cone_gear_shaft as part
import build_drive_train_assembly as drive
import cone_gear_shaft_spec
import cone_pivot_post_installation
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
    # Every diameter carries the shared band, so its places are only spelling.
    # The stations carry no band, so their places ARE the grade they are held
    # to: three for the gear-seat shoulders that must land in the air gap
    # between two gear faces, one for the journal length and overall length,
    # which nothing seats against.
    by_name = cone_gear_shaft_spec.DRAWING_PRECISION_BY_NAME
    assert by_name == {
        "Sec0Dia": 3,
        "Sec1Dia": 3,
        "Sec2Dia": 3,
        "Sec3Dia": 3,
        "Sec4Dia": 3,
        "Sec0End": 1,
        "Sec1End": 3,
        "Sec2End": 3,
        "Sec3End": 3,
        "Sec4End": 1,
        "ShoulderR": 2,
    }


def test_gear_seat_shoulders_are_held_inside_the_air_gap() -> None:
    """The .XXX grade is a location requirement, not a spelling choice.

    Gears are soldered at the seat pitch with 6.5 faces, so each seat step
    has to fall in the ~0.39 air gap between two neighbouring gear faces;
    otherwise the small-bore gear cannot pass the larger land to reach its
    station.  The title-block .XXX grade keeps every step in its gap and the
    .XX grade does not -- which is why Sec1End..Sec3End print three places.
    """
    grade = {
        places: _config.title_block(f"linear_{places}pl")["value_in"] * 25.4
        for places in (2, 3)
    }
    ends = cone_gear_shaft_spec.SECTION_ENDS
    seat0 = (
        cone_gear_shaft_spec.FRONT_STUB
        + cone_pivot_post_installation.GEAR_AXIS_SHIFT
        + drive.SHAFT_T120_STATION
    )
    faces = [
        (
            seat0 + j * drive.SEAT_PITCH - drive.CONE_FACE / 2.0,
            seat0 + j * drive.SEAT_PITCH + drive.CONE_FACE / 2.0,
        )
        for j in range(20)
    ]
    for name, station in zip(("Sec1End", "Sec2End", "Sec3End"), ends[1:4]):
        north_of_inboard = max(north for _south, north in faces if north < station)
        south_of_outboard = min(south for south, _north in faces if south > station)
        held = grade[cone_gear_shaft_spec.DRAWING_PRECISION_BY_NAME[name]]
        assert station - held > north_of_inboard, name
        assert station + held < south_of_outboard, name
        assert station + grade[2] > south_of_outboard, name
    # The last seat's north face and the tip journal end share the terminal
    # land: the overall length locates nothing but an adjustable cup point.
    assert ends[4] > faces[19][1]


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
    assert set(drawing.SIDE_KEEP) | set(drawing.SIDE_DIAMETERS) == marked
    # Nothing is imported twice, and the donor hands over exactly the five
    # diameters it was placed for.
    assert set(drawing.DONOR_KEEP) == set(drawing.SIDE_DIAMETERS)
    assert not set(drawing.SIDE_KEEP) & set(drawing.DONOR_KEEP)
    assert part.SECTIONS is cone_gear_shaft_spec.SECTIONS
    assert drawing.SHAFT_LENGTH == cone_gear_shaft_spec.SHAFT_LENGTH
    assert drawing.SECTION_DIAS == cone_gear_shaft_spec.SECTION_DIAS


def test_every_diameter_stands_on_its_own_land() -> None:
    """A diameter may only be dragged to the land its profile sketch measures.

    Land 0's circle is the large-end face; every other land is sketched on an
    offset plane at its END station and extruded back to that face, so the
    dimension lands on the shoulder it measures instead of piling up with the
    other four at z=0 (which is what forced the old leadered end view).  On
    the sheet a vertical linear dimension's line sits at its text x, so that
    x must fall inside the land: outside it the extension lines would run
    through a bigger neighbour and across its shoulder.
    """
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'mode="offset", base_plane="Front Plane", offset=end_z' in source
    assert "ExtrusionParameters(depth=end_z, reverse_direction=i > 0)" in source
    assert "await adapter.create_sketch(plane_name)" in source

    ends = cone_gear_shaft_spec.SECTION_ENDS
    big_end = drawing.SIDE_CENTER[0] + cone_gear_shaft_spec.SHAFT_LENGTH / 2000.0
    starts = (0.0, *ends[:-1])
    for index, (start, end) in enumerate(zip(starts, ends)):
        x, y = drawing.SIDE_DIAMETERS[f"Sec{index}Dia"]
        land = (big_end - end / 1000.0, big_end - start / 1000.0)
        if index == 0:
            # The faced end is the one place a line may stand off the part.
            assert land[0] < x < big_end + 0.025
        else:
            assert land[0] < x < land[1], index
        assert (
            y > drawing.SIDE_CENTER[1] + cone_gear_shaft_spec.SECTION_DIAS[0] / 2000.0
        )


def test_stacked_tip_diameters_never_run_a_line_through_a_text() -> None:
    """Three lands 6.9 mm apart carry three texts; each line clears the others.

    A line at x rises from the shaft to its own text, so it passes every text
    that sits lower than it; those texts must lie clear of x by half a text
    width.  Texts at the same height would collide outright.
    """
    half_text_width = 0.0075
    items = list(drawing.SIDE_DIAMETERS.values())
    for x_a, y_a in items:
        for x_b, y_b in items:
            if (x_a, y_a) == (x_b, y_b):
                continue
            assert abs(y_a - y_b) > 0.004 or abs(x_a - x_b) > 2 * half_text_width
            if y_b < y_a:
                assert abs(x_a - x_b) > half_text_width, (x_a, x_b)


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
    # The old "SHOULDER ROOTS R0.10 MAX" note is gone; the one note left
    # names the mate behind the three-place stations (rule 2) without adding
    # a check of its own (no MUST), and carries no number, tolerance, datum
    # or method word.
    notes = cone_gear_shaft_spec.DRAWING_NOTES
    assert 1 <= len(notes.splitlines()) <= 4
    # The sheet's note text runs ~2.7 mm per character; a line from the
    # note anchor must end before the title block at x = 0.216 m (the
    # first render's 67-character line ran under the tolerance table).
    assert max(len(line) for line in notes.splitlines()) * 0.0027 < (
        0.216 - drawing.NOTES_XY[0]
    )
    assert not any(character.isdigit() for character in notes)
    for forbidden in (
        "R0.",
        "MAX",
        "MUST",
        "DATUM",
        "BASIC",
        "FINISH",
        "TURN",
        "GRIND",
    ):
        assert forbidden not in notes.upper()
    assert "SOLDERED CONE GEAR SEATS" in notes
    assert (
        'apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})'
        in source
    )
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)' in (
        Path(drawing.__file__).read_text(encoding="utf-8")
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
    assert drawing.ISO_SCALE == (1, 2)  # reduced pictorial
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The end view is gone: its only content was a pile of leadered diameters.
    # The tip detail is gone too: DragModelDimension refuses to re-home a
    # model dimension into a detail view, so the five diameters share the
    # side view.
    assert '"*Front"' in source  # the donor, and only as a donor
    assert "delete_view(adapter, donor)" in source
    assert "CreateDetailViewAt4" not in source


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
