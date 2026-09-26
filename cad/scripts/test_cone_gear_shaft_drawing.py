"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

import re
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
    # The contract's one exception: the front-to-tip REFERENCE (#917 R5 (a))
    # takes its places from the spec constant, never a literal.
    assert source.count("SetPrecision3") == 1
    assert "SetPrecision3(DRAWING_REFERENCE_PRECISION, " in source
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
        # #914: the collar web holds the 1.5 floor at .XXX (not at .XX), and
        # the solder stations carry the user-ruled +-0.13.  The collar
        # diameter is the bar's as supplied, a two-place reference (15.88).
        "CollarDia": 2,
        "CollarWidth": 3,
        "T120Station": 3,
        "T006Station": 3,
    }
    web = cone_gear_shaft_spec.COLLAR_THICKNESS
    assert web - _config.title_block("linear_3pl")["value_in"] * 25.4 >= 1.5
    assert web - _config.title_block("linear_2pl")["value_in"] * 25.4 < 1.5


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
    # land: the tip station locates nothing but an adjustable cup point.
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
    # Nothing is imported twice, and the donor hands over exactly the six
    # diameters it was placed for (five lands and the collar, #914).
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
    assert "base_plane=SECTION_ORIGINS[i], offset=knob" in source
    assert "ExtrusionParameters(depth=knob, reverse_direction=i > 0)" in source
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


def test_collar_diameter_stands_on_the_collar() -> None:
    """#914: the collar is 1.681 wide, so its diameter line stands inside
    that ring, above the shaft, clear of the pivot-journal finish symbol."""
    spec = cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    ring = (
        big_end - spec.COLLAR_END_STATION / 1000.0,
        big_end - spec.COLLAR_START_STATION / 1000.0,
    )
    x, y = drawing.SIDE_DIAMETERS["CollarDia"]
    assert ring[0] < x < ring[1]
    assert y > drawing.SIDE_CENTER[1] + spec.COLLAR_DIA / 2000.0 + 0.010
    assert x + drawing.COLLAR_DIA_TEXT_WIDTH < drawing.PIVOT_FINISH_XY[0] - 0.010


def test_lengths_are_baseline_from_the_collar_face() -> None:
    """Option A (#914): one origin, the collar face.  Every length below the
    shaft that starts there stands on its own tier, the shortest nearest the
    part, the tip station (#917 R5 (a)) outermost; the journal runs the other
    way on the first tier, and the front-to-tip overall, now a REFERENCE,
    sits lowest, clear of the title block."""
    spec = cone_gear_shaft_spec
    from_datum = {
        "CollarWidth": spec.COLLAR_THICKNESS,
        "T120Station": spec.SOLDER_T120_STATION,
        "Sec1End": spec.SECTION_KNOBS[1],
        "Sec2End": spec.SECTION_KNOBS[2],
        "Sec3End": spec.SECTION_KNOBS[3],
        "T006Station": spec.SOLDER_T006_STATION,
        "Sec4End": spec.SECTION_KNOBS[4],
    }
    tiers = [
        drawing.SIDE_KEEP[name][1] for name in sorted(from_datum, key=from_datum.get)
    ]
    assert tiers == sorted(tiers, reverse=True)
    assert len(set(tiers)) == len(tiers)
    shaft_bottom = drawing.SIDE_CENTER[1] - spec.COLLAR_DIA / 2000.0
    assert tiers[0] < shaft_bottom - 0.005
    journal = drawing.SIDE_KEEP["Sec0End"]
    assert journal[1] == tiers[0]
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    datum_x = big_end - spec.DATUM_STATION / 1000.0
    # the journal's text is right of the datum, the collar web's left of it
    assert journal[0] > datum_x + 0.010
    assert (
        drawing.SIDE_KEEP["CollarWidth"][0] < datum_x - spec.COLLAR_THICKNESS / 1000.0
    )
    overall = drawing.OVERALL_REFERENCE_TEXT_XY[1]
    assert overall < tiers[-1] and overall > 0.066 + 0.008
    tip_x = big_end - spec.SHAFT_LENGTH / 1000.0
    assert tip_x < drawing.OVERALL_REFERENCE_TEXT_XY[0] < big_end
    # each station's text stands inside its own span, unless the span is too
    # narrow for it (the web's and the T120's): then left of that span
    for name, span in from_datum.items():
        x = drawing.SIDE_KEEP[name][0]
        if name in ("CollarWidth", "T120Station"):
            assert x < datum_x - span / 1000.0, name
            continue
        assert datum_x - span / 1000.0 < x < datum_x, name
    assert drawing.DIMENSION_CALLOUTS["T006Station"] == "20X EQ SP"


def _length_texts_crossed(side_keep, overall_xy):
    """Every (text, line x) pair where an extension line crossing a length
    text's tier passes within STATION_TEXT_CLEARANCE of that text's box.

    Each length hangs its two extension lines from the shaft down to its own
    tier, so a line crosses every tier ABOVE its own.  A text is centred on
    its x; its box is the character count times LENGTH_CHAR_WIDTH (the
    T006 callout's "20X EQ SP" line is the wider of its two).
    """
    spec = cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    datum_x = big_end - spec.DATUM_STATION / 1000.0
    tip_x = big_end - spec.SHAFT_LENGTH / 1000.0
    from_datum = {
        "CollarWidth": spec.COLLAR_THICKNESS,
        "T120Station": spec.SOLDER_T120_STATION,
        "Sec1End": spec.SECTION_KNOBS[1],
        "Sec2End": spec.SECTION_KNOBS[2],
        "Sec3End": spec.SECTION_KNOBS[3],
        "T006Station": spec.SOLDER_T006_STATION,
        "Sec4End": spec.SECTION_KNOBS[4],
    }
    places = spec.DRAWING_PRECISION_BY_NAME
    texts = {
        name: (f"{value:.{places[name]}f}", side_keep[name])
        for name, value in from_datum.items()
    }
    texts["T006Station"] = ("20X EQ SP", side_keep["T006Station"])
    texts["Sec0End"] = (
        f"{spec.DATUM_STATION:.{places['Sec0End']}f}",
        side_keep["Sec0End"],
    )
    texts["overall"] = (f"({spec.SHAFT_LENGTH:.1f})", overall_xy)
    # (line x, the lowest tier it reaches)
    lines = [(datum_x - value / 1000.0, side_keep[name][1]) for name, value in from_datum.items()]
    lines.append((datum_x, min(y for _x, y in side_keep.values())))
    lines += [(big_end, overall_xy[1]), (tip_x, overall_xy[1])]
    crossed = []
    for name, (text, (x, y)) in texts.items():
        half = len(text) * drawing.LENGTH_CHAR_WIDTH / 2.0
        for line_x, line_bottom in lines:
            if line_bottom >= y:
                continue
            if x - half - drawing.STATION_TEXT_CLEARANCE < line_x < (
                x + half + drawing.STATION_TEXT_CLEARANCE
            ):
                crossed.append((name, round(line_x, 4)))
    return crossed


def test_no_extension_line_strikes_a_length_text() -> None:
    """The 916a render had the datum line through "10.781" and the web's
    "1.681" against the collar's witness line (Main's eye-pass); a text
    keeps 2 mm of ink from every extension line crossing its tier."""
    assert _length_texts_crossed(drawing.SIDE_KEEP, drawing.OVERALL_REFERENCE_TEXT_XY) == []
    # Positive control: the 916a positions are caught.
    before = {
        **drawing.SIDE_KEEP,
        "CollarWidth": (0.2020, 0.1355),
        "T120Station": (0.2042, 0.1275),
    }
    crossed = {
        name for name, _x in _length_texts_crossed(before, drawing.OVERALL_REFERENCE_TEXT_XY)
    }
    assert crossed == {"CollarWidth", "T120Station"}


def test_the_collar_diameter_draws_nothing_inside_the_ring() -> None:
    """The 1.7 mm collar cannot hold a dimension line and two arrows (916a
    eye-pass): its diameter alone takes the near-side single-arrow style."""
    assert drawing.NEAR_SIDE_DIAMETERS == ("CollarDia",)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_leaders import set_near_side_diameter" in source
    assert "if name in NEAR_SIDE_DIAMETERS:" in source
    assert 'set_near_side_diameter(moved, f"{name} near-side diameter")' in source


class _FakePart:
    """A part document that records a sketch blank and reports its visibility."""

    def __init__(self, *, hides: bool) -> None:
        self.hides = hides
        self.selected: list[tuple[str, str]] = []
        self.blanked = False
        self.Extension = self

    def ClearSelection2(self, _all: bool) -> None:
        pass

    def SelectByID2(self, name: str, kind: str, *_args: object) -> bool:
        self.selected.append((name, kind))
        return True

    def BlankSketch(self) -> None:
        self.blanked = True

    def FeatureByName(self, name: str) -> object:
        assert name == cone_gear_shaft_spec.SOLDER_STATION_SKETCH
        # swVisibilityState_e: 1 hidden, 2 shown
        return type("Feature", (), {"Visible": 1 if self.blanked and self.hides else 2})


class _FakeAdapter:
    def __init__(self, model: _FakePart) -> None:
        self.currentModel = model


def test_the_part_saves_the_solder_station_witnesses_hidden() -> None:
    """Codex P1 on #916: a sketch hidden only in the drawing's pictorial still
    renders in the part images and every assembly instance, so the part
    blanks it before its save and reads the blank back."""
    assert set(cone_gear_shaft_spec.DRAWING_DIMENSIONS[
        cone_gear_shaft_spec.SOLDER_STATION_SKETCH
    ]) == {"T120Station", "T006Station"}
    model = _FakePart(hides=True)
    part._blank_solder_stations(_FakeAdapter(model))
    assert model.selected == [(cone_gear_shaft_spec.SOLDER_STATION_SKETCH, "SKETCH")]
    assert model.blanked
    source = Path(part.__file__).read_text(encoding="utf-8")
    build_body = source[source.index("async def build(") :]
    assert build_body.index("_blank_solder_stations(adapter)") < build_body.index(
        "save_part_and_images("
    )


def test_a_blank_that_does_not_take_fails_the_part_build() -> None:
    with pytest.raises(RuntimeError, match="still visible after BlankSketch"):
        part._blank_solder_stations(_FakeAdapter(_FakePart(hides=False)))


def test_only_the_side_view_shows_the_part_hidden_stations() -> None:
    """The station dimensions live on the side view, which takes the opt-in
    import; no other view opts in, so the pictorial shows the part as saved."""
    stations = cone_gear_shaft_spec.DRAWING_DIMENSIONS[
        cone_gear_shaft_spec.SOLDER_STATION_SKETCH
    ]
    assert set(stations) <= set(drawing.SIDE_KEEP)
    assert not set(stations) & set(drawing.DONOR_KEEP)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert body.count("hidden_sketches.curate_view_dimensions(") == 1
    side_call = body[body.index("hidden_sketches.curate_view_dimensions(") :]
    assert side_call.index("side,") < side_call.index(")")
    assert "BlankSketch" not in source


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
    # U40 (option S1, 2026-09-23): each gear-seat shoulder sits one seat
    # station nearer the big end than the old (154.2, 161.1, 168.0) map,
    # so the 1/16-in land carries T012 and T006; the terminal endpoint still
    # follows the stock cup apex and the overall length is unchanged.
    stub_delta = cone_gear_shaft_spec.FRONT_STUB - 12.3
    assert ends[1:-1] == pytest.approx(
        tuple(
            old_end + stub_delta + cone_gear_shaft_spec.GEAR_AXIS_SHIFT
            for old_end in (147.3, 154.2, 161.1)
        )
    )
    # Printed baseline stations from the big (journal) end, as ruled; the
    # overall length follows the E11 #10-32 cup apex (202.267 before E11).
    assert ends[1:] == pytest.approx((163.792, 170.692, 177.592, 200.886), abs=1e-3)
    assert ends[-1] == pytest.approx(
        cone_gear_shaft_spec.FRONT_STUB + 138.97882594770454
    )
    # The longer terminal stub still supports the entire 4 mm bushing.
    assert cone_gear_shaft_spec.TIP_STUB_START_STATION == pytest.approx(
        115.6853574197016
    )
    assert cone_gear_shaft_spec.TIP_STUB_LENGTH == pytest.approx(23.293468528)
    assert ends[-1] - ends[-2] == pytest.approx(cone_gear_shaft_spec.TIP_STUB_LENGTH)
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
    # One feature, one dimension, one quantity prefix -- not three dimensions
    # (the gear-seat steps; the collar's roots stay sharp, #914).
    assert drawing.DIMENSION_CALLOUTS["ShoulderR"] == "3X"
    # The old "SHOULDER ROOTS R0.10 MAX" note is gone.  What remains names
    # the gear seats' mate (rule 2; codex 375a122c) without the joint method
    # (rule 6, Main 2026-09-26: soldering is the drive-train assembly step's)
    # or a check of its own (no MUST), and carries
    # no number but the mate's part number, no tolerance, datum or method
    # word -- except the tailstock line, a user-ruled process requirement
    # (U40, 2026-09-23: the 23.293 mm Ø1.588 tip land at L/D 14.7 is only
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
        "SOLDER",
        "BRAZE",
        "LOCTITE",
    ):
        assert forbidden not in notes.upper()
    # U40: "TURN" appears only in the ruled tailstock line.
    assert "TURN" not in notes.upper().replace(tailstock[0].upper(), "")
    assert notes.splitlines()[0] == f"GEAR SEATS MATE {mate_number} BORES."
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
    # The MATERIAL cell holds one line and names the material only.  The
    # collar IS the 5/8 bar's OD as supplied (user ruling 2026-09-26, Codex P1
    # on #916), so the U41 treatment applies: the size prints beside the
    # collar's reference diameter (COLLAR_STOCK_CALLOUT), never in this cell.
    for field in ("material", "material_specification"):
        assert not re.search(r"\d+/\d+|\bin\b|\bround\b", str(config[field])), field
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_every_station_knob_owns_its_plane_and_depth(monkeypatch) -> None:
    """Every length knob (Tools > Equations) is the ONE owner of each dimension
    that carries it: SecEnd{i} owns land i's end plane AND its depth (Codex
    #839 PRRT_kwDOPHDy386mKNTW), SecEnd0 the journal and the CollarFace plane,
    CollarWidth the collar's plane and web.  Run the real build() against
    recording stubs; the seat-side ownership gate runs once, after every drive
    is authored."""
    _adapter, stubs, sketch_dims, gated_after = _stubbed_build(monkeypatch)
    drives = stubs["drive_dimension"].call_args_list
    assert gated_after == [len(drives)]
    owners = {c.args[1]: c.args[2] for c in drives}
    records = {
        c.args[0]: c.args[1] if len(c.args) > 1 else None
        for c in sketch_dims.return_value.record.call_args_list
    }
    for global_name, _value, names in part.STATION_OWNERS:
        for name in names:
            dim, _, feature = name.partition("@")
            if feature == "SolderStations":
                assert records[dim] == f'"{global_name}"', name
                continue
            assert owners[name] == f'"{global_name}"', name
    assert records["DatumStation"] == '"SecEnd0"'


def test_station_owners_cover_every_knob_once() -> None:
    spec = cone_gear_shaft_spec
    rows = {
        global_name: (value, names) for global_name, value, names in part.STATION_OWNERS
    }
    assert len(rows) == len(part.STATION_OWNERS)
    for i, knob in enumerate(spec.SECTION_KNOBS):
        assert rows[f"SecEnd{i}"][0] == knob
    assert rows["SecEnd0"][1] == (
        "Sec0End@Sec0",
        "CollarFaceStation@CollarFace",
        "DatumStation@SolderStations",
    )
    assert rows["CollarWidth"] == (
        spec.COLLAR_THICKNESS,
        ("CollarStation@CollarEndPlane", "CollarWidth@Collar"),
    )
    assert rows["SolderT120"] == (
        spec.SOLDER_T120_STATION,
        ("T120Station@SolderStations",),
    )
    assert rows["SolderT006"] == (
        spec.SOLDER_T006_STATION,
        ("T006Station@SolderStations",),
    )


class _Dim:
    def __init__(self, mm: float, driven_state: int = 1, reference: bool = False):
        self.SystemValue = mm / 1000.0
        self.DrivenState = driven_state
        self._reference = reference

    def IsReference(self) -> bool:
        return self._reference


def _gate_fixture(monkeypatch, dims, equations):
    from unittest.mock import MagicMock

    model = MagicMock()
    model.Parameter.side_effect = dims.get
    adapter = MagicMock()
    adapter.currentModel = model
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(
        part, "_equations_for", lambda _adapter, lhs: equations.get(lhs, [])
    )
    return adapter


def _machine(override=None):
    """As-built dims and equations for every STATION_OWNERS row.  ``override``
    maps a dimension name to its (right-hand side, DrivenState)."""
    dims, equations = {}, {}
    for global_name, value, names in part.STATION_OWNERS:
        equations[f'"{global_name}"'] = [f'"{global_name}" = {value}mm']
        for name in names:
            owner, state = (override or {}).get(name, (f'"{global_name}"', 1))
            dims[name] = _Dim(value, state)
            equations[f'"{name}"'] = [f'"{name}" = {owner}']
    return dims, equations


def test_station_gate_accepts_single_ownership_at_driven_state_1(
    monkeypatch, caplog
) -> None:
    """Equation-owned dimensions read DrivenState 1 (driven), never 2: the
    gate compares the dimensions one knob owns with each other, not with a
    literal.  Each knob's definition, with its value, lands in the leaf log."""
    dims, equations = _machine()
    with caplog.at_level("INFO"):
        part._assert_stations_single_owned(_gate_fixture(monkeypatch, dims, equations))
    for global_name, _value, _names in part.STATION_OWNERS:
        assert equations[f'"{global_name}"'][0] in caplog.text


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"Sec2Station@Sec2EndPlane": ('"SecEnd1"', 1)}, 'not "SecEnd2"'),
        (
            {"Sec3Station@Sec3EndPlane": ('"SecEnd3"', 2)},
            "SecEnd3: DrivenState differs",
        ),
        ({"CollarWidth@Collar": ('"SecEnd0"', 1)}, 'not "CollarWidth"'),
        ({"T006Station@SolderStations": ('"SolderT120"', 1)}, 'not "SolderT006"'),
    ],
)
def test_station_gate_rejects_a_wrong_owner_or_state(
    monkeypatch, override, message
) -> None:
    dims, equations = _machine(override)
    adapter = _gate_fixture(monkeypatch, dims, equations)
    with pytest.raises(RuntimeError, match=message):
        part._assert_stations_single_owned(adapter)


def test_station_gate_rejects_a_missing_or_moved_dimension(monkeypatch) -> None:
    dims, equations = _machine()
    del equations['"Sec1Station@Sec1EndPlane"']
    dims["Sec4Station@Sec4EndPlane"] = _Dim(
        cone_gear_shaft_spec.SECTION_KNOBS[4] + 1e-3
    )
    del dims["CollarFaceStation@CollarFace"]
    adapter = _gate_fixture(monkeypatch, dims, equations)
    with pytest.raises(RuntimeError, match="expected one equation") as raised:
        part._assert_stations_single_owned(adapter)
    assert "Sec4Station@Sec4EndPlane: reads" in str(raised.value)
    assert "CollarFaceStation@CollarFace not found" in str(raised.value)


def test_station_gate_proves_the_depth_owner_too(monkeypatch) -> None:
    """Codex #839 P2: a depth that keeps its as-built value and DrivenState
    but is driven by the wrong global, or has lost its equation, must fail --
    as must a knob defined twice."""
    dims, equations = _machine({"Sec2End@Sec2": ('"SecEnd1"', 1)})
    del equations['"Sec3End@Sec3"']
    equations['"SecEnd4"'] *= 2
    adapter = _gate_fixture(monkeypatch, dims, equations)
    with pytest.raises(RuntimeError) as raised:
        part._assert_stations_single_owned(adapter)
    message = str(raised.value)
    assert "Sec2End@Sec2: owned by" in message
    assert "Sec3End@Sec3: expected one equation" in message
    assert "SecEnd4: expected one definition" in message
    assert "Sec1" not in message.replace("SecEnd1", "")


# #914 (user ruling 2026-09-25): an integral collar captures the shaft.  The
# tip adjuster pushes the shaft south; the collar's south face bears on the
# post's north boss face, and the 64T is soldered against its north face.
def test_collar_fills_the_gap_between_the_post_boss_and_the_64t() -> None:
    spec = cone_gear_shaft_spec
    post_north_face = (
        drive.POST_STATION
        + drive.POST_CONE_BOSS_LENGTH / 2.0
        - drive.SHAFT_FRONT_STATION
    )
    gear64_south_face = (
        drive.GEAR64_STATION
        + drive.GEAR_AXIS_SHIFT
        - drive.GEAR64_FACE / 2.0
        - drive.SHAFT_FRONT_STATION
    )
    assert spec.COLLAR_START_STATION == pytest.approx(post_north_face, abs=1e-9)
    assert spec.COLLAR_START_STATION == spec.JOURNAL_END
    assert spec.COLLAR_END_STATION == pytest.approx(gear64_south_face, abs=1e-9)
    # user ruling: accept the 1.681 web (novice floor 1.5, no station moves)
    assert spec.COLLAR_THICKNESS == pytest.approx(1.681, abs=5e-4)
    assert spec.COLLAR_THICKNESS >= 1.5


def test_the_collar_is_the_bar_as_supplied_and_its_thrust_ring_holds_the_floor() -> None:
    """Codex P1 on #916: a turned Ø15.0 at .X could come out Ø14.2 and leave a
    0.96 thrust ring on the post boss.  User ruling 2026-09-26: the collar is
    the 5/8 cold-finished bar's own OD, and both edges bounding the ring print
    a break small enough that the worst-case ring, breaks counted, holds 1.5."""
    import cone_pivot_post_spec as post

    spec = cone_gear_shaft_spec
    assert spec.STOCK_DIA == pytest.approx(0.625 * 25.4)
    assert spec.COLLAR_DIA == spec.STOCK_DIA
    assert spec.STOCK_DIA_BAND == pytest.approx((0.0, -0.002 * 25.4))
    assert max(spec.SECTION_DIAS) < spec.COLLAR_DIA
    assert spec.JOURNAL_BORE_DIA == post.BORE_DIA
    # worst case: the thinnest bar in the widest bore
    thinnest = spec.STOCK_DIA + spec.STOCK_DIA_BAND[1]
    widest = post.BORE_DIA + spec.POST_JOURNAL_BORE_BAND[0]
    ring = (thinnest - widest) / 2.0
    assert spec.THRUST_RING_MIN == pytest.approx(ring)
    # the title block's 0.25 break on both edges would take it under the floor
    assert ring - 2.0 * 0.25 < spec.THRUST_RING_FLOOR
    # the printed break is the largest one-place value that keeps the floor
    breaks = spec.THRUST_EDGE_BREAK_MAX
    assert ring - 2.0 * breaks >= spec.THRUST_RING_FLOOR
    assert ring - 2.0 * (breaks + 0.1) < spec.THRUST_RING_FLOOR
    assert breaks == pytest.approx(round(breaks, 1))
    # the thickest bar still bears inside the boss: no overhang toward the post body
    assert spec.STOCK_DIA + spec.STOCK_DIA_BAND[0] < post.CONE_BOSS_DIA


def test_the_sheet_states_the_collar_as_stock_with_its_break() -> None:
    """The as-supplied collar prints as a reference diameter with the stock
    statement and its edge break beside it (the U41 plate's form)."""
    spec = cone_gear_shaft_spec
    assert drawing.REFERENCE_DIAMETERS == ("CollarDia",)
    assert drawing.DIMENSION_CALLOUTS["CollarDia"] is spec.COLLAR_STOCK_CALLOUT
    callout = spec.COLLAR_STOCK_CALLOUT.upper()
    assert "5/8" in callout and "AS SUPPLIED" in callout
    assert f"{spec.THRUST_EDGE_BREAK_MAX:.1f} MAX" in callout
    assert spec.DRAWING_PRECISION["CollarProfile"]["CollarDia"] == 2
    assert f"{spec.COLLAR_DIA:.2f}" == "15.88"


def _stubbed_build(monkeypatch):
    """Run the real build() with every imported helper stubbed.  Returns the
    adapter mock, the stubs by name, the shared SketchDims mock (every sketch's
    ``record`` calls) and how many drives existed when the gate ran."""
    import asyncio
    import inspect
    from unittest.mock import AsyncMock, MagicMock

    stubs = {}
    for attr, value in list(vars(part).items()):
        if not callable(value) or attr.startswith("__") or attr == "build":
            continue
        if getattr(value, "__module__", "") == part.__name__:
            continue
        if not inspect.isfunction(value) and not inspect.isclass(value):
            continue
        stub = AsyncMock() if inspect.iscoroutinefunction(value) else MagicMock()
        stubs[attr] = stub
        monkeypatch.setattr(part, attr, stub)
    monkeypatch.setattr(
        part,
        "name_dimensions",
        lambda _a, feature, names: [f"{n}@{feature}" for n in names],
    )
    sketch_dims = MagicMock()
    sketch_dims.return_value.apply.return_value = []
    monkeypatch.setattr(part, "SketchDims", sketch_dims)
    monkeypatch.setattr(part, "_sketch_x_per_model_z", lambda _a: -1.0)
    gated_after: list[int] = []
    monkeypatch.setattr(
        part,
        "_assert_stations_single_owned",
        lambda _a: gated_after.append(len(stubs["drive_dimension"].call_args_list)),
    )
    adapter = AsyncMock()
    asyncio.run(part.build(adapter))
    return adapter, stubs, sketch_dims, gated_after


def _planes(adapter) -> list[tuple[str, float]]:
    return [
        (c.args[0].base_plane, c.args[0].offset)
        for c in adapter.create_plane.call_args_list
    ]


def test_every_land_is_placed_from_the_one_origin(monkeypatch) -> None:
    """Option A (#914): the collar face is the one length origin.  Its plane
    comes first, from the front face by the journal; lands 1-3 end on planes
    offset from it and extrude back to it, so each depth IS the shoulder's
    station from the collar face.  The tip land ends on a plane from the same
    face (#917 R5 (a)); the front-to-tip overall is only a reference."""
    spec = cone_gear_shaft_spec
    adapter, stubs, _dims, _gated = _stubbed_build(monkeypatch)
    planes = _planes(adapter)
    assert planes[0] == ("Front Plane", spec.COLLAR_START_STATION)
    for i in range(1, len(spec.SECTIONS)):
        assert (spec.SECTION_ORIGINS[i], spec.SECTION_KNOBS[i]) in planes, i
    extrusions = [c.args[0] for c in adapter.create_extrusion.call_args_list]
    assert [e.depth for e in extrusions[: len(spec.SECTIONS)]] == list(
        spec.SECTION_KNOBS
    )
    assert [e.reverse_direction for e in extrusions[: len(spec.SECTIONS)]] == [
        False,
        True,
        True,
        True,
        True,
    ]
    knobs = {c.args[1]: c.args[2] for c in stubs["set_global"].call_args_list}
    for i, knob in enumerate(spec.SECTION_KNOBS):
        assert knobs[f"SecEnd{i}"] == f"{knob}mm"
    assert knobs["SolderT120"] == f"{spec.SOLDER_T120_STATION}mm"
    assert knobs["SolderT006"] == f"{spec.SOLDER_T006_STATION}mm"
    assert "CollarEnd" not in knobs


def test_build_turns_the_collar_between_the_journal_and_the_64t(monkeypatch) -> None:
    """#914: the collar is its own land -- sketched on a plane one web north of
    the collar face, at the bar's own Ø15.875, extruded back one web.  Its roots stay sharp (the
    post and the 64T bear flat on its faces) and the old journal-to-3/8 step
    edge is buried under it."""
    spec = cone_gear_shaft_spec
    adapter, stubs, _dims, _gated = _stubbed_build(monkeypatch)
    assert ("CollarFace", spec.COLLAR_THICKNESS) in _planes(adapter)
    radii = [c.args[3] for c in stubs["define_circle"].call_args_list]
    assert spec.COLLAR_DIA / 2.0 in [pytest.approx(r) for r in radii]
    extrusions = [c.args[0] for c in adapter.create_extrusion.call_args_list]
    collar = [e for e in extrusions if e.depth == pytest.approx(spec.COLLAR_THICKNESS)]
    assert len(collar) == 1 and collar[0].reverse_direction
    edges = adapter.add_fillet.call_args.args[1]
    land = 0.375 * spec.MM_PER_IN / 2.0
    assert [spec.JOURNAL_DIA / 2.0, 0.0, spec.COLLAR_START_STATION] not in edges
    assert [land, 0.0, spec.COLLAR_END_STATION] not in edges
    assert [land, 0.0, spec.JOURNAL_END] not in edges
    assert len(edges) == len(spec.SECTIONS) - 2
    assert spec.FILLET_CALLOUT == f"{len(edges)}X"
    named = [c.args[1] for c in stubs["name_last_feature"].call_args_list]
    assert "CollarFace" in named


def test_solder_station_witnesses_stand_on_the_axis(monkeypatch) -> None:
    """The reference sketch's witness lines stand at the collar face and at
    T120's and T006's south faces, placed along the sketch's own x direction
    (stubbed -1 here); the stations are measured from the collar-face line."""
    spec = cone_gear_shaft_spec
    adapter, stubs, _dims, _gated = _stubbed_build(monkeypatch)
    xs = [c.args[0] for c in adapter.add_line.call_args_list]
    datum = spec.DATUM_STATION
    assert xs == [
        -datum,
        -(datum + spec.SOLDER_T120_STATION),
        -(datum + spec.SOLDER_T006_STATION),
    ]
    spans = [
        c.args[4]
        for c in stubs["dimension_between"].call_args_list
        if c.args[3] == "horizontal_distance"
    ]
    assert spans == [datum, spec.SOLDER_T120_STATION, spec.SOLDER_T006_STATION]


def test_sketch_x_direction_is_read_from_the_sketch(monkeypatch) -> None:
    """The Right plane's sketch x runs along model Z; its sign comes from the
    sketch's ModelToSketchTransform, never assumed.  The fake reads a bare
    list as zeros, as the seat does (memory: COM double[] needs double_array)."""
    from types import SimpleNamespace

    class _Point:
        def __init__(self, data):
            self.ArrayData = tuple(data)

        def MultiplyTransform(self, transform):
            return _Point(transform(self.ArrayData))

    class _Utility:
        def CreatePoint(self, values):
            if isinstance(values, list):
                return _Point((0.0, 0.0, 0.0))
            return _Point(values.value)

    def right_plane(xyz):  # Right plane: sketch x = -model Z, y = model Y
        return (-xyz[2], xyz[1], xyz[0])

    sketch = SimpleNamespace(ModelToSketchTransform=right_plane)
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            SketchManager=SimpleNamespace(ActiveSketch=sketch)
        ),
        swApp=SimpleNamespace(GetMathUtility=_Utility),
    )
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    assert part._sketch_x_per_model_z(adapter) == -1.0
    sketch.ModelToSketchTransform = lambda xyz: (xyz[2], xyz[1], -xyz[0])
    assert part._sketch_x_per_model_z(adapter) == 1.0
    sketch.ModelToSketchTransform = lambda xyz: (xyz[1], xyz[2], xyz[0])
    with pytest.raises(RuntimeError, match="not along model Z"):
        part._sketch_x_per_model_z(adapter)


def test_one_length_origin_is_the_collar_face() -> None:
    spec = cone_gear_shaft_spec
    assert spec.DATUM_STATION == spec.COLLAR_START_STATION
    assert spec.SECTION_ORIGINS == (
        "Front Plane",
        "CollarFace",
        "CollarFace",
        "CollarFace",
        "CollarFace",
    )
    assert spec.SECTION_KNOBS[0] == spec.JOURNAL_END
    # #917 R5 (a): the tip is a station from the collar face too, so the
    # collar-to-tip chain is one .X length, not the journal plus the overall.
    for i in (1, 2, 3, 4):
        assert spec.SECTION_KNOBS[i] == pytest.approx(
            spec.SECTION_ENDS[i] - spec.COLLAR_START_STATION
        )
    assert spec.DRAWING_PRECISION_BY_NAME["Sec4End"] == 1
    # The front-to-tip overall is the one sheet-derived dimension: a read-only
    # sum with its places handed over by the spec (drawing contract).
    assert spec.DRAWING_REFERENCE_PRECISION == 1


class _Curve:
    def __init__(self, centre_z_m: float, radius_m: float, circle: bool = True):
        self.CircleParams = (0.0, 0.0, centre_z_m, 0.0, 0.0, 1.0, radius_m)
        self._circle = circle

    def IsCircle(self) -> bool:
        return self._circle


class _Edge:
    def __init__(self, curve):
        self._curve = curve

    def GetCurve(self):
        return self._curve


def test_the_overall_reference_picks_each_end_face_circle(monkeypatch) -> None:
    """The REF overall runs between the two END-FACE circles, picked by
    station and diameter: the journal's own circle at the collar face and
    the tip land's start circle share those diameters at other stations."""
    spec = cone_gear_shaft_spec
    length = spec.SHAFT_LENGTH / 1000.0
    journal_r = spec.SECTION_DIAS[0] / 2000.0
    tip_r = spec.SECTION_DIAS[-1] / 2000.0
    front = _Edge(_Curve(0.0, journal_r))
    tip = _Edge(_Curve(-length, tip_r))  # the sign of model Z is not assumed
    edges = [
        _Edge(None),
        _Edge(_Curve(0.0, journal_r, circle=False)),
        _Edge(_Curve(spec.COLLAR_START_STATION / 1000.0, journal_r)),
        _Edge(_Curve(spec.SECTION_ENDS[3] / 1000.0, tip_r)),
        front,
        tip,
    ]
    monkeypatch.setattr(drawing, "visible_view_entities", lambda *a, **k: edges)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    assert (
        drawing._end_circle(
            object(), station_mm=0.0, diameter_mm=spec.SECTION_DIAS[0], label="front"
        )
        is front
    )
    assert (
        drawing._end_circle(
            object(),
            station_mm=spec.SHAFT_LENGTH,
            diameter_mm=spec.SECTION_DIAS[-1],
            label="tip",
        )
        is tip
    )
    edges.append(_Edge(_Curve(0.0, journal_r)))
    with pytest.raises(RuntimeError, match="2 end-face circles"):
        drawing._end_circle(
            object(), station_mm=0.0, diameter_mm=spec.SECTION_DIAS[0], label="front"
        )


def test_the_overall_is_added_as_a_checked_reference() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_add_overall_reference(adapter, side)" in source
    assert "set_reference_dimension(" in source
    assert "SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)" in source
    assert 'orientation="horizontal"' in source


def test_solder_stations_ride_the_drive_train_seat_ladder() -> None:
    """T120 and T006 south faces, from the collar face, where the drive train
    seats them; the twenty stations between are one exact seat pitch apart."""
    spec = cone_gear_shaft_spec
    assert spec.T120_CENTER_STATION == pytest.approx(
        drive.SHAFT_T120_STATION + drive.GEAR_AXIS_SHIFT, abs=1e-9
    )
    span = spec.SOLDER_T006_STATION - spec.SOLDER_T120_STATION
    assert span == pytest.approx(
        (spec.SOLDER_STATION_COUNT - 1) * drive.SEAT_PITCH, abs=1e-6
    )
    south = (
        drive.SHAFT_T120_STATION
        + drive.GEAR_AXIS_SHIFT
        + spec.CONE_FACE_REFERENCE / 2.0
        - spec.CONE_GEAR_FACE_WIDTH
        - drive.SHAFT_FRONT_STATION
        - spec.DATUM_STATION
    )
    assert spec.SOLDER_T120_STATION == pytest.approx(south, abs=1e-9)
    # the 64T sits between the collar and T120's south face
    assert spec.SOLDER_T120_STATION > spec.COLLAR_THICKNESS + drive.GEAR64_FACE


def test_drive_train_seats_the_shaft_and_64t_on_the_collar(monkeypatch) -> None:
    """#914: contacts, not distances -- the collar face ON the post's north
    boss face (picked on the annulus outside the collar) and the 64T's south
    face ON the collar's north face."""
    import asyncio
    import math
    from unittest.mock import AsyncMock

    pick = drive._POST_BOSS_NORTH_PICK
    north = drive.cone_station(drive._POST_NORTH_STATION)
    axis = (drive.SIN_I, 0.0, drive.COS_I)
    offset = [pick[k] - north[k] for k in range(3)]
    assert sum(offset[k] * axis[k] for k in range(3)) == pytest.approx(0.0, abs=1e-9)
    radius = math.hypot(*offset)
    assert cone_gear_shaft_spec.COLLAR_DIA / 2.0 < radius
    assert radius < drive.POST_CONE_BOSS_DIA / 2.0
    assert offset[1] == 0.0  # horizontal: vertical lies on the body tangent

    source = Path(drive.__file__).read_text(encoding="utf-8")
    assert 'named_ref(f"CollarFace@{cone_shaft}", "PLANE")' in source
    assert 'bore_axis_ref(_POST_BOSS_NORTH_PICK, "FACE")' in source
    assert (
        'named_ref(f"ConeShaftNormal@{pivot_post}", "PLANE"),\r\n        d_axial'
        not in source
    )
    assert 'seat_plane="CollarEndPlane"' in source

    coincident = AsyncMock()
    distance = AsyncMock()
    monkeypatch.setattr(drive, "coincident_mate", coincident)
    monkeypatch.setattr(drive, "distance_driver", distance)
    origin = [0.0, 0.0, 0.0]
    asyncio.run(
        drive._axial_seat(
            object(),
            "g-1",
            "s-1",
            origin,
            [0.0, 0.0, 1.0],
            origin,
            "64T",
            "CollarEndPlane",
        )
    )
    distance.assert_not_awaited()
    refs = coincident.await_args.args[1:3]
    assert [r.name for r in refs] == ["Front Plane@g-1", "CollarEndPlane@s-1"]
    asyncio.run(
        drive._axial_seat(
            object(), "g-1", "s-1", origin, [0.0, 0.0, 1.0], [0, 0, 5.0], "T120", ""
        )
    )
    assert distance.await_args.args[3] == pytest.approx(5.0)


def test_the_64t_front_plane_is_its_south_face(monkeypatch) -> None:
    """The 64T's collar seat is Front coincident with CollarEndPlane, which is
    a contact only because the gear's Front plane IS its south face: its blank
    is sketched on Front and extruded +z by the face width, and
    _place_on_shaft puts that origin face/2 south of the gear's centre."""
    import asyncio
    import inspect

    import _gear
    import build_crank_drive_gear

    placed = {}

    async def place_component(_adapter, part_name, origin, *_args, **_kwargs):
        placed[part_name] = origin
        return f"{part_name}-1"

    monkeypatch.setattr(drive, "place_component", place_component)
    asyncio.run(
        drive._place_on_shaft(
            object(),
            "crank-drive-gear",
            drive.GEAR64_STATION + drive.GEAR_AXIS_SHIFT,
            drive.GEAR64_FACE,
        )
    )
    south = drive.cone_station(drive._GEAR64_SOUTH_STATION)
    assert placed["crank-drive-gear"] == pytest.approx(south, abs=1e-9)

    blank = inspect.getsource(_gear.build_fixed_gear)
    assert 'check("create_sketch blank", await adapter.create_sketch("Front"))' in blank
    assert "create_extrusion(ExtrusionParameters(depth=face_width))" in blank
    crank = inspect.getsource(build_crank_drive_gear.build)
    assert "build_fixed_gear(\n        adapter, TEETH, FACE_WIDTH," in crank.replace(
        "\r\n", "\n"
    )
