"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

from pathlib import Path

import _config
import _fit_limits
import build_cone_gear_shaft as part
import build_drive_train_assembly as drive
import cone_gear_shaft_spec
import cone_pivot_post_installation
import cone_tip_block_spec
import draw_cone_gear_shaft as drawing
import pytest
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


# Which NAMED band each land rides (U27, 2026-09-23): the two running lands
# keep the shared h band, the three soldered seats open to GEAR_SEAT_BAND.
_EXPECTED_LAND_BANDS = (
    ("RUNNING_DIA_BAND", _fit_limits.SHAFT_H),
    ("GEAR_SEAT_BAND", cone_gear_shaft_spec.GEAR_SEAT_BAND),
    ("GEAR_SEAT_BAND", cone_gear_shaft_spec.GEAR_SEAT_BAND),
    ("GEAR_SEAT_BAND", cone_gear_shaft_spec.GEAR_SEAT_BAND),
    ("RUNNING_DIA_BAND", _fit_limits.SHAFT_H),
)


def _lands_ride_named_bands(bands: tuple[tuple[float, float], ...]) -> bool:
    """True when every land's band IS its named class, not an equal retype."""
    return len(bands) == len(_EXPECTED_LAND_BANDS) and all(
        band is getattr(cone_gear_shaft_spec, name) is expected
        for band, (name, expected) in zip(bands, _EXPECTED_LAND_BANDS)
    )


def test_section_fits_are_toleranced_on_the_model() -> None:
    """Each turned land rides its NAMED fit class, applied to the model.

    Spelled as callout text the band is frozen: SolidWorks prints it verbatim
    and never re-renders it, so the mm->inch flip in issue #290 would leave
    "+0.00/-0.02" reading as inches on every land. The identity assertion also
    stops a local retype from silently forking a named class.
    """
    spec = cone_gear_shaft_spec
    assert spec.RUNNING_DIA_BAND is _fit_limits.SHAFT_H
    assert spec.GEAR_SEAT_BAND == (0.000, -0.050)
    assert _lands_ride_named_bands(spec.SECTION_DIA_BANDS)
    # Positive control: an equal-valued local retype of either class is caught.
    forked = list(spec.SECTION_DIA_BANDS)
    forked[2] = (0.000, -0.050)
    assert forked[2] == spec.GEAR_SEAT_BAND
    assert not _lands_ride_named_bands(tuple(forked))
    forked = list(spec.SECTION_DIA_BANDS)
    forked[0] = (0.000, -0.020)
    assert not _lands_ride_named_bands(tuple(forked))
    # The running tip land still clears the bushing bore it turns in.
    import build_cone_tip_bushing as bushing

    tip_max = spec.SECTION_DIAS[-1] + spec.SECTION_DIA_BANDS[-1][0]
    assert bushing.BORE_DIA + bushing.BORE_DIA_BAND[1] - tip_max >= 0.0
    # Applied in ONE loop over the named bands, so the AST reports the
    # f-string source rather than five literal keys.
    assert model_toleranced_dimensions(part) == {
        ("f'Sec{section}Profile'", "f'Sec{section}Dia'"): "*deviations(band)"
    }
    assert "for section, band in enumerate(SECTION_DIA_BANDS)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")


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


def _gear_faces() -> list[tuple[float, float]]:
    """Every cone gear's (south, north) face, in the shaft's station frame.

    The 6.0 gears sit on the historical 6.5 reference stations narrowed from
    the SOUTH face only; ``cone_gear_shaft_spec.gear_faces`` carries that
    shift in the pivot-end frame, and test_gear_face_model_follows_the_drive_train
    pins it to build_drive_train_assembly's seed placement.
    """
    stub = cone_gear_shaft_spec.FRONT_STUB
    return [
        (stub + south, stub + north)
        for south, north in map(cone_gear_shaft_spec.gear_faces, range(20))
    ]


def _shoulder_gaps() -> list[tuple[str, float, float, float, float]]:
    """(name, station, inboard north face, outboard south face, held band)."""
    grade = _config.title_block("linear_3pl")["value_in"] * 25.4
    faces = _gear_faces()
    ends = cone_gear_shaft_spec.SECTION_ENDS
    gaps = []
    for name, station in zip(("Sec1End", "Sec2End", "Sec3End"), ends[1:4]):
        assert cone_gear_shaft_spec.DRAWING_PRECISION_BY_NAME[name] == 3, name
        gaps.append(
            (
                name,
                station,
                max(north for _south, north in faces if north < station),
                min(south for south, _north in faces if south > station),
                grade,
            )
        )
    return gaps


def test_gear_seat_shoulders_are_held_inside_the_air_gap() -> None:
    """The .XXX grade is a location requirement, not a spelling choice.

    Gears are soldered at the seat pitch, so each seat step has to fall in
    the ~0.89 air gap between two neighbouring gear faces; otherwise the
    small-bore gear cannot pass the larger land to reach its station.  The
    title-block .XXX grade keeps every step in its gap.
    """
    for name, station, north_of_inboard, south_of_outboard, held in _shoulder_gaps():
        assert station - held > north_of_inboard, name
        assert station + held < south_of_outboard, name
    # The last seat's north face and the tip journal end share the terminal
    # land: the overall length locates nothing but an adjustable cup point.
    assert cone_gear_shaft_spec.SECTION_ENDS[4] > _gear_faces()[19][1]


def test_two_place_shoulders_would_leave_the_air_gap() -> None:
    """Why Sec1End..Sec3End print three places: the .XX band would not hold."""
    grade2 = _config.title_block("linear_2pl")["value_in"] * 25.4
    for name, station, north_of_inboard, south_of_outboard, _held in _shoulder_gaps():
        assert station - grade2 < north_of_inboard, name
        assert station + grade2 > south_of_outboard, name


def test_gear_face_model_follows_the_drive_train() -> None:
    """The spec's duplicated seat pitch and reference face are the assembly's."""
    spec = cone_gear_shaft_spec
    assert spec.CONE_SEAT_PITCH == pytest.approx(drive.SEAT_PITCH, abs=1e-12)
    assert spec.CONE_FACE_STATION_REFERENCE == drive.CONE_FACE_STATION_REFERENCE
    assert spec.CONE_GEAR_FACE_WIDTH == drive.CONE_FACE
    for j in range(20):
        # BDT's seed: seat station plus half the south-side narrowing.
        centre = (
            drive.SHAFT_T120_STATION
            + cone_pivot_post_installation.GEAR_AXIS_SHIFT
            + (drive.CONE_FACE_STATION_REFERENCE - drive.CONE_FACE) / 2.0
            + j * drive.SEAT_PITCH
        )
        south, north = spec.gear_faces(j)
        assert (south + north) / 2.0 == pytest.approx(centre, abs=1e-9)
        assert north - south == pytest.approx(drive.CONE_FACE)


def test_gear_seat_steps_are_centred_with_band_plus_quarter_air() -> None:
    """Main, 2026-09-25: each step sits mid-gap, >= .XXX band + 0.25 from both faces."""
    spec = cone_gear_shaft_spec
    band = _config.title_block("linear_3pl")["value_in"] * 25.4
    for name, j, end in zip(
        ("Sec1End", "Sec2End", "Sec3End"), (15, 16, 17), spec.SECTION_ENDS[1:4]
    ):
        station = end - spec.FRONT_STUB
        inboard_north = spec.gear_faces(j)[1]
        outboard_south = spec.gear_faces(j + 1)[0]
        assert station - inboard_north == pytest.approx(outboard_south - station), name
        assert station - inboard_north >= band + 0.25, name
        assert outboard_south - station >= band + 0.25, name


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

    A dragged diameter's text hangs to the RIGHT of its dimension line, so the
    text at (x, y) spans x..x+width; any other line inside that span rises
    from the shaft and must stop below the text.  The first render stepped
    the texts the other way and three leaders crossed (codex, 18395f30).
    """
    width = drawing.DIAMETER_TEXT_WIDTH
    text_height = 0.009  # nominal over a stacked two-line band
    items = list(drawing.SIDE_DIAMETERS.values())
    for x_a, y_a in items:
        for x_b, y_b in items:
            if (x_a, y_a) == (x_b, y_b):
                continue
            if x_a < x_b < x_a + width:
                assert y_b < y_a - text_height, ((x_a, y_a), (x_b, y_b))


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
    # Rule-12 E11: #10-32 94025A164 at the block spec's 9.5 fit-up embed.
    assert cone_gear_shaft_spec.ADJUSTER_EMBED == cone_tip_block_spec.ADJUSTER_EMBED
    assert cone_gear_shaft_spec.ADJUSTER_CUP_RIM_STATION == pytest.approx(
        137.77232594770454
    )
    # Vendor Sketch2 Line7 (harvested 2026-09-24): 45 deg cup, depth = rim radius.
    assert cone_gear_shaft_spec.MCM_94025A164_CUP_DEPTH == pytest.approx(1.2065)
    assert cone_gear_shaft_spec.T006_TIP_STATION == pytest.approx(138.97882594770454)
    assert cone_gear_shaft_spec.SHAFT_LENGTH == (
        cone_gear_shaft_spec.FRONT_STUB + cone_gear_shaft_spec.T006_TIP_STATION
    )
    # U40 (option S1, 2026-09-23): each gear-seat shoulder sits in the air gap
    # one seat nearer the big end than before (T030|T024, T024|T018,
    # T018|T012), so the 1/16-in land carries T012 and T006; the terminal
    # endpoint still follows the stock cup apex and the overall length is
    # unchanged.  Each step is centred in its gap (Main, 2026-09-25).
    assert ends[1:-1] == pytest.approx(
        tuple(
            cone_gear_shaft_spec.FRONT_STUB + cone_gear_shaft_spec.seat_gap_midpoint(j)
            for j in (15, 16, 17)
        )
    )
    # Printed baseline stations from the big (journal) end, as ruled; the
    # overall length follows the E11 #10-32 cup apex (202.267 before E11).
    assert ends[1:] == pytest.approx((164.068, 170.957, 177.846, 200.886), abs=1e-3)
    assert ends[-1] == pytest.approx(
        cone_gear_shaft_spec.FRONT_STUB + 138.97882594770454
    )
    # The longer terminal stub still supports the entire 4 mm bushing.
    assert cone_gear_shaft_spec.TIP_STUB_START_STATION == pytest.approx(
        115.939, abs=1e-3
    )
    assert cone_gear_shaft_spec.TIP_STUB_LENGTH == pytest.approx(23.040, abs=1e-3)
    assert ends[-1] - ends[-2] == pytest.approx(
        cone_gear_shaft_spec.TIP_STUB_LENGTH
    )
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
    # It has to clear the air on each side of every step.
    assert cone_gear_shaft_spec.FILLET_RADIUS < cone_gear_shaft_spec.SEAT_STEP_AIR
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "add_fillet(FILLET_RADIUS, fillet_edges, propagate=False)" in source
    assert 'name_last_feature(adapter, "ShoulderFillets")' in source
    assert 'name_dimensions(adapter, "ShoulderFillets", ["ShoulderR"])' in source
    # One feature, one dimension, one quantity prefix -- not four dimensions.
    assert drawing.DIMENSION_CALLOUTS == {"ShoulderR": "4X"}
    # The old "SHOULDER ROOTS R0.10 MAX" note is gone.  What remains names
    # the mate behind the gear-seat band -- the solder gap (rule 2; codex
    # 375a122c) -- without adding a check of its own (no MUST), and carries
    # no number but the mate's part number, no tolerance, datum or method
    # word -- except the tailstock line, a user-ruled process requirement
    # (U40, 2026-09-23: the 23.04 mm Ø1.588 tip land at L/D 14.5 is only
    # turnable supported), so "TURN" is allowed in that one line only.  The
    # three-place-stations lines went in the U27 round: the places already
    # say it.
    notes = cone_gear_shaft_spec.DRAWING_NOTES
    assert 1 <= len(notes.splitlines()) <= 4
    # The sheet's note text runs ~2.7 mm per character; a line from the
    # note anchor must end before the title block at x = 0.216 m (the
    # first render's 67-character line ran under the tolerance table).
    assert max(len(line) for line in notes.splitlines()) * 0.0027 < (
        0.216 - drawing.NOTES_XY[0]
    )
    mate_number = _config.parts("cone-gear")["number"]
    assert not any(character.isdigit() for character in notes.replace(mate_number, ""))
    tailstock = [line for line in notes.splitlines() if "TAILSTOCK" in line.upper()]
    assert len(tailstock) == 1
    for forbidden in (
        "R0.",
        "MAX",
        "MUST",
        "DATUM",
        "BASIC",
        "FINISH",
        "GRIND",
    ):
        assert forbidden not in notes.upper()
    # U40: "TURN" appears only in the ruled tailstock line.
    assert "TURN" not in notes.upper().replace(tailstock[0].upper(), "")
    assert "SOLDER GAP" in notes and f"CONE GEAR BORES, {mate_number}" in notes
    assert "THREE-PLACE" not in notes
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


def test_prose_quotes_the_printed_tip_gear_diameters() -> None:
    """The shaft prose cites the cone gears' deepened-mesh tip diameters."""
    import cone_gear_spec

    t006 = f"{cone_gear_spec.DEEPENED_MESH_MM[6][0]:.2f}"
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert part_source.count(f"T006 OD is {t006} mm") == 1
    assert f"T006 OD is now {t006} mm" in part_source
    spec_source = Path(cone_gear_shaft_spec.__file__).read_text(encoding="utf-8")
    for teeth in (6, 12, 18, 24):
        assert f"{cone_gear_spec.DEEPENED_MESH_MM[teeth][0]:.2f}" in spec_source
