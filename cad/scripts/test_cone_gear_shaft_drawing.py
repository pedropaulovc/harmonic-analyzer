"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import _config
import _fit_limits
import build_cone_gear_shaft as part
import build_drive_train_assembly as drive
import cone_gear_shaft_spec
import cone_gear_spec
import cone_gear_stack
import cone_line
import cone_pivot_post_installation
import cone_shaft_land_bands
import cone_stack_end_play
import cone_tip_block_spec
import cone_tip_bushing_spec
import draw_cone_gear_shaft as drawing
import pytest
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


# Which NAMED band each land rides (U27, 2026-09-23): the two running lands
# keep the shared h band, the three gear seats open to GEAR_SEAT_BAND.
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
    # The tip land's round still clears the MHA-096 spacer's round bore.
    import build_cone_tip_bushing as bushing

    tip_max = spec.SECTION_DIAS[-1] + spec.SECTION_DIA_BANDS[-1][0]
    assert bushing.BORE_DIA + bushing.BORE_DIA_BAND[1] - tip_max >= 0.0
    # Every flat rides the one named across-flat band.
    assert spec.FLAT_AF_BAND is cone_shaft_land_bands.FLAT_AF_BAND
    # Applied in ONE loop per family over the named bands, so the AST reports
    # the f-string sources rather than nine literal keys.
    assert model_toleranced_dimensions(part) == {
        ("f'Sec{section}Profile'", "f'Sec{section}Dia'"): "*deviations(band)",
        ("f'Sec{land}FlatProfile'", "f'Sec{land}AF'"): "*deviations(FLAT_AF_BAND)",
    }


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
    # Every diameter and across-flat carries its named band, so its places
    # are only spelling.  The stations carry no band, so their places ARE the
    # grade they are held to: three for the land steps booked in the setback
    # and for the tip, which sits in the axial stack, one for the journal
    # length, which nothing seats against.
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
        "Sec4End": 3,
        "Sec1AF": 3,
        "Sec2AF": 3,
        "Sec3AF": 3,
        "Sec4AF": 3,
        "ShoulderR": 2,
        # #914: the collar web is the 64T's station toward MHA-016, so it
        # prints .XXX (crank_boss_rim).  The collar diameter is the bar's as
        # supplied, a two-place reference (15.88).
        "CollarDia": 2,
        "CollarWidth": 3,
    }
    # Rule 12: the web holds the 2.0 target at the low limit it prints.
    web = cone_gear_shaft_spec.COLLAR_THICKNESS
    assert web - _config.title_block("linear_3pl")["value_in"] * 25.4 >= 2.0


def _band(places: int) -> float:
    """The title-block band a length prints at ``places``."""
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


def _setback_margin(j: int, step_band: float) -> float:
    """What the setback leaves when the step behind gear j's north face and
    its root reach north, the collar is short, the stack is short onto the
    collar and the fleet spare is held."""
    spec = cone_gear_shaft_spec
    return spec.SEAT_STEP_SETBACK - (
        step_band
        + spec.FILLET_RADIUS
        + _band(3)  # the collar web prints .XXX
        - cone_gear_stack.face_band(j, "north")[1]
        + cone_stack_end_play.MARGIN_SPARE
    )


def test_the_gears_are_a_touching_stack_on_the_collar() -> None:
    """User ruling 2026-09-28: each gear is cone_gear_spec.FACE_WIDTH thick
    and bears on the next; the 64T bears on the collar and on T120."""
    spec = cone_gear_shaft_spec
    tolerance = cone_gear_stack.PITCH_LOCKSTEP_TOLERANCE
    faces = [spec.gear_faces(j) for j in range(20)]
    for (_south, north), (next_south, _north) in zip(faces, faces[1:]):
        assert 0.0 <= next_south - north <= tolerance
    assert all(north - south == pytest.approx(6.8887) for south, north in faces)
    # T006's north face, the tip spacer's seat, stays on the 6.5 reference.
    assert faces[19][1] == pytest.approx(spec.T006_CENTER_STATION + 3.25)
    assert faces[0][0] - spec.GEAR64_NORTH_FACE_STATION == pytest.approx(0.0, abs=tolerance)
    assert spec.GEAR64_SOUTH_FACE_STATION == pytest.approx(
        spec.COLLAR_END_STATION - spec.FRONT_STUB
    )


def test_each_step_sits_one_setback_inside_the_larger_gear() -> None:
    """The steps T030|T024, T024|T018 and T018|T012 sit 1.0 south of the
    smaller gear's south face, inside the larger gear, and at print-worst
    the step and its root stay south of the smaller gear (margins 0.065,
    0.090, 0.115 with the .XXX step band)."""
    spec = cone_gear_shaft_spec
    for name, j, end in zip(("Sec1End", "Sec2End", "Sec3End"), (15, 16, 17), spec.SECTION_ENDS[1:4]):
        station = end - spec.FRONT_STUB
        south, north = spec.gear_faces(j)
        assert station == pytest.approx(north - 1.0), name
        assert south < station - _band(3) and station + _band(3) + spec.FILLET_RADIUS < north
        margin = _setback_margin(j, _band(spec.DRAWING_PRECISION_BY_NAME[name]))
        assert margin >= 0.0, name
        assert spec.SEAT_STEP_BUDGET[name]["margin"] == pytest.approx(margin), name
    assert [round(row["margin"], 3) for row in spec.SEAT_STEP_BUDGET.values()] == [
        0.065,
        0.090,
        0.115,
    ]


def test_two_place_steps_would_reach_the_smaller_gear() -> None:
    """Why Sec1End..Sec3End print three places: the .XX band eats the setback."""
    for j in (15, 16, 17):
        assert _setback_margin(j, _band(2)) < 0.0, j


def test_gear_face_model_follows_the_drive_train() -> None:
    """The spec's seat pitch, reference face and gear face are the assembly's."""
    spec = cone_gear_shaft_spec
    assert spec.SEAT_PITCH is cone_gear_spec.SEAT_PITCH
    assert spec.SEAT_PITCH == pytest.approx(drive.SEAT_PITCH, abs=1e-12)
    assert spec.CONE_FACE_STATION_REFERENCE == drive.CONE_FACE_STATION_REFERENCE
    assert spec.CONE_GEAR_FACE_WIDTH == drive.CONE_FACE
    assert spec.T006_CENTER_STATION == pytest.approx(cone_line.T006_CENTER_STATION, abs=1e-9)
    for j in range(20):
        # BDT's seed: seat station plus half the south-side growth.
        centre = (
            drive.SHAFT_T120_STATION
            + cone_pivot_post_installation.GEAR_AXIS_SHIFT
            + (drive.CONE_FACE_STATION_REFERENCE - drive.CONE_FACE) / 2.0
            + j * drive.SEAT_PITCH
        )
        south, north = spec.gear_faces(j)
        assert (south + north) / 2.0 == pytest.approx(centre, abs=1e-9)
        assert north - south == pytest.approx(drive.CONE_FACE)


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
    assert (
        set(drawing.SIDE_KEEP) | set(drawing.SIDE_DIAMETERS) | set(drawing.D_SECTION_KEEP)
        == marked
    )
    # Nothing is imported twice, and the donor hands over exactly the six
    # diameters it was placed for (five lands and the collar, #914).
    assert set(drawing.DONOR_KEEP) == set(drawing.SIDE_DIAMETERS)
    assert not set(drawing.SIDE_KEEP) & set(drawing.DONOR_KEEP)
    assert not set(drawing.D_SECTION_KEEP) & (set(drawing.SIDE_KEEP) | set(drawing.DONOR_KEEP))
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
    """#914: the collar ring is too narrow for a dimension line with two
    arrows, so its diameter line stands inside that ring, above the shaft,
    clear of the pivot-journal finish symbol."""
    spec = cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    ring = (
        big_end - spec.COLLAR_END_STATION / 1000.0,
        big_end - spec.COLLAR_START_STATION / 1000.0,
    )
    x, y = drawing.SIDE_DIAMETERS["CollarDia"]
    assert ring[0] < x < ring[1]
    assert y > drawing.SIDE_CENTER[1] + spec.COLLAR_DIA / 2000.0 + 0.010


# The mha014-1 leaf's read-off of MHA-014 (9ec43110c, before any move): the
# collar's three-line callout hangs right from its dimension line at the ring,
# the pivot-journal Ra 1.6 box, and the Ø9.525 text on land 1.  final877 had
# the same block (0.2094, 0.1683, 0.2565, 0.1834): the Ra sat on "15.88)" and
# its leader crossed the block.
_COLLAR_TEXT = (0.2088, 0.1676, 0.2565, 0.1844)
_PIVOT_FINISH_BOX = (0.2320, 0.1800, 0.2790, 0.1980)
_SEC1_TEXT = (0.1400, 0.1685, 0.1723, 0.1765)
_SEC1_LINES = [((0.1400, 0.1452), (0.1400, 0.1548))]


def _pivot_finish_ink() -> tuple[tuple[float, float, float, float], list]:
    """The pivot finish as the build places it: the measured symbol box and
    its leader from PIVOT_FINISH_XY down onto the journal land's top flank."""
    spec = cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    top = (big_end - 0.020, drawing.SIDE_CENTER[1] + spec.SECTION_DIAS[0] / 2000.0)
    return _PIVOT_FINISH_BOX, [(drawing.PIVOT_FINISH_XY, top)]


def _lifted(text, dy):
    return (text[0], text[1] + dy, text[2], text[3] + dy)


def test_the_collar_callout_lifts_clear_of_the_pivot_finish() -> None:
    """final877: the collar's stock callout is wider than the whole journal
    land, so the pivot finish's leader, which lands on that journal, crossed it
    wherever the symbol stood.  The planner lifts the block above the symbol
    and its leader, never sideways: mha014-1 moved it left and it landed on
    the Ø9.525 text, dragging the dimension line off the ring."""
    from _drawing_annotation_extent import CLEAR_GAP_M, boxes_clear
    from _drawing_leaders import distance_to_box

    finish, leader = _pivot_finish_ink()
    text = _COLLAR_TEXT
    assert not boxes_clear(text, finish)  # positive control: the render's clash
    dy = drawing._collar_callout_dy(text, finish, leader)
    lifted = _lifted(text, dy)
    assert dy > 0.0
    assert boxes_clear(lifted, finish)
    assert all(distance_to_box(segment, lifted) >= CLEAR_GAP_M for segment in leader)
    assert boxes_clear(lifted, _SEC1_TEXT)
    # a block already clear stays put
    assert drawing._collar_callout_dy(lifted, finish, leader) == 0.0
    # a leader running above the symbol under the block's span lifts it further
    high = [((0.2300, finish[3] + 0.003), (0.2326, 0.1564))]
    assert drawing._collar_callout_dy(text, finish, high) == pytest.approx(dy + 0.003)
    # ink outside the block's span does not
    aside = [((0.3000, 0.2500), (0.3100, 0.2400))]
    assert drawing._collar_callout_dy(text, finish, aside) == pytest.approx(dy)


def test_the_collar_callout_read_guard_takes_the_whole_block() -> None:
    """The measured block must be the three lines, not the value line alone:
    the render's width passes the guard, a "(Ø15.88)"-only box does not."""
    assert drawing.COLLAR_CALLOUT_LINES == (
        "(Ø15.88)",
        *cone_gear_shaft_spec.COLLAR_STOCK_CALLOUT.split("\n"),
    )
    measured = _COLLAR_TEXT[2] - _COLLAR_TEXT[0]
    assert measured >= drawing.COLLAR_CALLOUT_MIN_READ
    value_line_only = len("(Ø15.88)") * drawing.LENGTH_CHAR_WIDTH
    assert value_line_only < drawing.COLLAR_CALLOUT_MIN_READ


def _clear_collar_with(monkeypatch, texts, dimensions=None):
    """Run _clear_collar_callout against fakes: each collar read returns the
    next text box, each neighbour dimension its (text box, lines); returns the
    recorded moves."""
    from types import SimpleNamespace

    if dimensions is None:
        dimensions = {"Sec1Dia": (_SEC1_TEXT, _SEC1_LINES)}
    finish, leader = _pivot_finish_ink()
    reads = iter(texts)
    moves = []
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "gdt_box", lambda *_a, **_k: finish)
    monkeypatch.setattr(drawing, "leader_segments", lambda _a: leader)
    monkeypatch.setattr(drawing, "_dimension_text_box", lambda name, _l: dimensions[name][0])
    monkeypatch.setattr(drawing, "dimension_segments", lambda name: dimensions[name][1])
    monkeypatch.setattr(
        drawing,
        "callout_ink",
        lambda *_a, **_k: SimpleNamespace(label="collar", text=next(reads), leader=()),
    )
    monkeypatch.setattr(drawing, "dimension_text_points", lambda _a: [])
    monkeypatch.setattr(
        drawing,
        "move_annotation",
        lambda _ad, _an, dx, dy, **_k: moves.append((dx, dy)),
    )
    monkeypatch.setattr(
        drawing,
        "sheet_region",
        lambda _a: SimpleNamespace(xmin=0.01, ymin=0.01, xmax=0.42, ymax=0.27),
    )
    finish_symbol = SimpleNamespace(GetAnnotation=lambda: object())
    # each neighbour's fake annotation is its own name
    drawing._clear_collar_callout(
        object(), object(), finish_symbol, {name: name for name in dimensions}
    )
    return moves


def test_the_build_lifts_and_proves_the_collar_callout(monkeypatch) -> None:
    text = _COLLAR_TEXT
    finish, leader = _pivot_finish_ink()
    dy = drawing._collar_callout_dy(text, finish, leader)
    lifted = _lifted(text, dy)
    assert _clear_collar_with(monkeypatch, [text, lifted]) == [(0.0, dy)]
    # a move that does not land (the text reads back where it was) fails
    with pytest.raises(RuntimeError, match="crowds"):
        _clear_collar_with(monkeypatch, [text, text])
    # a block that reads back moved sideways took its dimension line off the ring
    drifted = (lifted[0] - 0.005, lifted[1], lifted[2] - 0.005, lifted[3])
    with pytest.raises(RuntimeError, match="left the collar ring"):
        _clear_collar_with(monkeypatch, [text, drifted])
    # a box around the value line alone is refused, never "cleared"
    value_only = (0.2088, 0.1783, 0.2088 + 0.019, 0.1844)
    with pytest.raises(RuntimeError, match="misread"):
        _clear_collar_with(monkeypatch, [value_only])


def test_the_collar_proof_measures_every_dimension_beside_it(monkeypatch) -> None:
    """The proof reads the other dimensions' ink rather than trusting nominal
    widths: a text measured where the lifted block lands, or a dimension line
    rising into it, fails the build.  mha014-1 is the positive control: its
    leftward move landed on the measured Ø9.525 text and the proof refused
    it."""
    text = _COLLAR_TEXT
    finish, leader = _pivot_finish_ink()
    dy = drawing._collar_callout_dy(text, finish, leader)
    lifted = _lifted(text, dy)
    land1_line = [((0.2000, 0.1452), (0.2000, 0.1350))]
    clear = {
        "Sec1Dia": (_SEC1_TEXT, _SEC1_LINES),
        "Sec1End": ((0.1400, 0.1170, 0.1600, 0.1210), land1_line),
    }
    assert _clear_collar_with(monkeypatch, [text, lifted], clear) == [(0.0, dy)]
    from _drawing_annotation_extent import require_clear

    mha014_1 = (0.1344, 0.1676, 0.1821, 0.1844)
    with pytest.raises(RuntimeError, match=r"crowds \['Sec1Dia'\]"):
        require_clear("collar stock callout", mha014_1, {"Sec1Dia": _SEC1_TEXT})
    above = (lifted[2] - 0.004, lifted[1] + 0.002, lifted[2] + 0.020, lifted[3])
    with pytest.raises(RuntimeError, match=r"crowds \['Sec0Dia'\]"):
        _clear_collar_with(
            monkeypatch, [text, lifted], {**clear, "Sec0Dia": (above, [])}
        )
    rising = [((0.2200, 0.1579), (0.2200, lifted[1] + 0.004))]
    with pytest.raises(RuntimeError, match=r"\['Sec1End'\] lines run by"):
        _clear_collar_with(
            monkeypatch, [text, lifted], {**clear, "Sec1End": (clear["Sec1End"][0], rising)}
        )


def test_a_dimension_text_box_spans_every_text_item() -> None:
    """The value and its stacked band are separate text items; the box a
    neighbour is proved against spans both."""
    from types import SimpleNamespace

    from _layout_geometry import estimate_text_box

    items = [("Ø9.525", (0.1410, 0.1760), 0.0025), ("+0.000", (0.1560, 0.1730), 0.0018)]
    data = SimpleNamespace(
        GetTextCount=lambda: len(items),
        GetTextAtIndex=lambda i: items[i][0],
        GetTextPositionAtIndex=lambda i: (*items[i][1], 0.0),
        GetTextHeightAtIndex=lambda i: items[i][2],
        GetTextRefPositionAtIndex=lambda _i: 1,
        GetTextAngleAtIndex=lambda _i: 0.0,
    )
    display = SimpleNamespace(GetDisplayData=lambda: data)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    boxes = [
        estimate_text_box(text, anchor=anchor, height=height, reference=1)
        for text, anchor, height in items
    ]
    assert drawing._dimension_text_box(annotation, "Sec1Dia") == (
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )
    no_text = SimpleNamespace(GetTextCount=lambda: 0)
    empty = SimpleNamespace(
        GetSpecificAnnotation=lambda: SimpleNamespace(GetDisplayData=lambda: no_text)
    )
    with pytest.raises(RuntimeError, match="draws no text"):
        drawing._dimension_text_box(empty, "Sec1Dia")


def test_lengths_are_baseline_from_the_collar_face() -> None:
    """Option A (#914): one origin, the collar face.  Every length below the
    shaft that starts there stands on its own tier, the shortest nearest the
    part, the tip station (#917 R5 (a)) outermost; the journal runs the other
    way on the first tier, and the front-to-tip overall, now a REFERENCE,
    sits lowest, clear of the title block."""
    spec = cone_gear_shaft_spec
    from_datum = {
        "CollarWidth": spec.COLLAR_THICKNESS,
        "Sec1End": spec.SECTION_KNOBS[1],
        "Sec2End": spec.SECTION_KNOBS[2],
        "Sec3End": spec.SECTION_KNOBS[3],
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
    # narrow for it (the web's): then left of that span
    for name, span in from_datum.items():
        x = drawing.SIDE_KEEP[name][0]
        if name == "CollarWidth":
            assert x < datum_x - span / 1000.0, name
            continue
        assert datum_x - span / 1000.0 < x < datum_x, name


def test_every_length_tier_is_one_line() -> None:
    """final877: a callout below a length hung between two tiers and read as
    either's.  No length below the shaft carries a callout line."""
    assert not set(drawing.DIMENSION_CALLOUTS) & set(drawing.SIDE_KEEP) - {"ShoulderR"}


def _length_texts_crossed(side_keep, overall_xy):
    """Every (text, line x) pair where an extension line crossing a length
    text's tier passes within STATION_TEXT_CLEARANCE of that text's box.

    Each length hangs its two extension lines from the shaft down to its own
    tier, so a line crosses every tier ABOVE its own.  A text is centred on
    its x; its box is the character count times LENGTH_CHAR_WIDTH.
    """
    spec = cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    datum_x = big_end - spec.DATUM_STATION / 1000.0
    tip_x = big_end - spec.SHAFT_LENGTH / 1000.0
    from_datum = {
        "CollarWidth": spec.COLLAR_THICKNESS,
        "Sec1End": spec.SECTION_KNOBS[1],
        "Sec2End": spec.SECTION_KNOBS[2],
        "Sec3End": spec.SECTION_KNOBS[3],
        "Sec4End": spec.SECTION_KNOBS[4],
    }
    places = spec.DRAWING_PRECISION_BY_NAME
    texts = {
        name: (f"{value:.{places[name]}f}", side_keep[name])
        for name, value in from_datum.items()
    }
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
    """The 916a render had the datum line through a station text and the
    web's text against the collar's witness line (Main's eye-pass); a text
    keeps 2 mm of ink from every extension line crossing its tier."""
    assert _length_texts_crossed(drawing.SIDE_KEEP, drawing.OVERALL_REFERENCE_TEXT_XY) == []
    # Positive control: the 916a web position is caught by the datum line.
    before = {**drawing.SIDE_KEEP, "CollarWidth": (0.2020, 0.1355)}
    crossed = {
        name for name, _x in _length_texts_crossed(before, drawing.OVERALL_REFERENCE_TEXT_XY)
    }
    assert crossed == {"CollarWidth"}


def test_the_collar_diameter_draws_nothing_inside_the_ring() -> None:
    """The 1.7 mm collar cannot hold a dimension line and two arrows (916a
    eye-pass): its diameter alone takes the near-side single-arrow style."""
    assert drawing.NEAR_SIDE_DIAMETERS == ("CollarDia",)
    import _drawing_leaders

    assert drawing.set_near_side_diameter is _drawing_leaders.set_near_side_diameter
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "if name in NEAR_SIDE_DIAMETERS:" in source
    assert 'set_near_side_diameter(moved, f"{name} near-side diameter")' in source


def test_each_d_section_cuts_its_own_land_clear_of_its_neighbours() -> None:
    """User ruling 2026-09-28: every flatted land shows its D end-on, with its
    across-flat.  Each cutting line crosses the land it names at least 2 mm
    from the land's ends (the step root, the collar) and from that land's
    diameter line; each D is enlarged to 15 mm or more so the 1.460 reads;
    and the four stand apart, right of the side view and above the title
    block with room for their captions."""
    spec = cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    starts = (spec.COLLAR_END_STATION, *spec.SECTION_ENDS[1:-1])
    sections = drawing.D_SECTIONS
    assert tuple(section.land for section in sections) == spec.FLAT_LANDS
    boxes = []
    for section, start in zip(sections, starts):
        tip_side = big_end - spec.SECTION_ENDS[section.land] / 1000.0
        big_side = big_end - start / 1000.0
        assert tip_side + 0.002 <= section.cut_x <= big_side - 0.002, section
        dia_x = drawing.SIDE_DIAMETERS[f"Sec{section.land}Dia"][0]
        assert abs(section.cut_x - dia_x) >= 0.002, section
        across = spec.SECTION_DIAS[section.land] * section.scale[0] / section.scale[1]
        assert across >= 15.0, section
        half = across / 2000.0
        x, y = section.centre
        assert x - half > big_end + 0.02, section
        assert y - half - 0.012 > 0.066, section  # caption above the title block
        text_x, text_y = drawing.D_SECTION_KEEP[f"Sec{section.land}AF"]
        assert text_x == x and text_y > y + half, section
        boxes.append((x - half, x + half))
    for (_left, right), (left, _right) in zip(boxes, boxes[1:]):
        assert left > right
    texts = [drawing.D_SECTION_KEEP[f"Sec{section.land}AF"][0] for section in sections]
    assert all(b - a > drawing.DIAMETER_TEXT_WIDTH for a, b in zip(texts, texts[1:]))


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
    # The tip chain stacks from the touching gears (user ruling 2026-09-28):
    # T006's north face, the 4 mm bushing against it, the feeler-set gap,
    # the 12 mm block.  Every length is its owner's, not a copy.
    assert cone_gear_shaft_spec.T006_NORTH_FACE_STATION == pytest.approx(
        cone_line.T006_NORTH_FACE
    )
    assert cone_gear_shaft_spec.TIP_BUSHING_LENGTH == cone_tip_bushing_spec.LENGTH
    assert cone_gear_shaft_spec.TIP_BLOCK_LENGTH == cone_tip_block_spec.BLOCK_Z
    assert cone_gear_shaft_spec.TIP_BLOCK_SOUTH_FACE_STATION == pytest.approx(
        cone_gear_shaft_spec.TIP_BUSHING_END_STATION + cone_stack_end_play.TIP_BLOCK_FEELER
    )
    assert cone_gear_shaft_spec.TIP_BLOCK_SOUTH_FACE_STATION + (
        cone_gear_shaft_spec.TIP_BLOCK_LENGTH / 2.0
    ) == pytest.approx(cone_line.TIP_BLOCK_STATION)
    assert cone_gear_shaft_spec.TIP_BLOCK_NORTH_FACE_STATION == pytest.approx(
        145.72232594770454
    )
    # Rule-12 E11: #10-32 94025A164 at the block spec's 9.5 fit-up embed.
    assert cone_gear_shaft_spec.ADJUSTER_EMBED == cone_tip_block_spec.ADJUSTER_EMBED
    assert cone_gear_shaft_spec.ADJUSTER_CUP_RIM_STATION == pytest.approx(
        136.22232594770454
    )
    # Vendor Sketch2 Line7 (harvested 2026-09-24): 45 deg cup, depth = rim radius.
    assert cone_gear_shaft_spec.MCM_94025A164_CUP_DEPTH == pytest.approx(1.2065)
    assert cone_gear_shaft_spec.T006_TIP_STATION == pytest.approx(137.42882594770452)
    assert cone_gear_shaft_spec.SHAFT_LENGTH == (
        cone_gear_shaft_spec.FRONT_STUB + cone_gear_shaft_spec.T006_TIP_STATION
    )
    # Each land step sits one setback behind the larger gear's north face
    # (T030|T024, T024|T018, T018|T012), so the 1/16-in land carries T012
    # and T006 and runs on to the stock cup apex.
    assert ends[1:-1] == pytest.approx(
        tuple(
            cone_gear_shaft_spec.FRONT_STUB + cone_gear_shaft_spec.seat_step_station(j)
            for j in (15, 16, 17)
        )
    )
    # Printed baseline stations from the big (journal) end.
    assert ends[1:] == pytest.approx((162.624, 169.513, 176.402, 199.336), abs=1e-3)
    assert ends[-1] == pytest.approx(
        cone_gear_shaft_spec.FRONT_STUB + 137.42882594770452
    )
    # The terminal stub supports the entire 4 mm bushing.
    assert cone_gear_shaft_spec.TIP_STUB_START_STATION == pytest.approx(
        114.495, abs=1e-3
    )
    assert cone_gear_shaft_spec.TIP_STUB_LENGTH == pytest.approx(22.934, abs=1e-3)
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


def test_every_gear_land_carries_one_d_flat() -> None:
    """User ruling 2026-09-28: each gear land is a D whose across-flat is its
    section's; the flat's plane is the AF less the round half-diameter."""
    spec = cone_gear_shaft_spec
    assert spec.FLAT_LANDS == (1, 2, 3, 4)
    assert spec.SECTION_FLAT_AF is cone_shaft_land_bands.SECTION_FLAT_AF
    assert spec.FLAT_OFFSETS == pytest.approx((None, 4.0005, 2.667, 1.3335, 0.66625))
    # Each flat's plane stays OUTSIDE the next land's round, and each bore's
    # flat lets the next land pass (every flat runs off its land into air).
    for land in spec.FLAT_LANDS[:-1]:
        assert spec.FLAT_OFFSETS[land] > spec.SECTION_DIAS[land + 1] / 2.0, land
    # The tip land's flat runs out through the end face (the end is a D).
    assert max(spec.FLAT_LANDS) == len(spec.SECTIONS) - 1


def test_each_flat_is_cut_over_exactly_its_land(monkeypatch) -> None:
    """Each flat is sketched on its land's end plane and cut blind back over
    the land (the tip's from the end face): land 1 stops at the collar face,
    every other at the step behind it."""
    adapter, stubs, _sketch_dims, _gated = _stubbed_build(monkeypatch)
    spec = cone_gear_shaft_spec
    sketched = [c.args[0] for c in adapter.create_sketch.call_args_list]
    for land in spec.FLAT_LANDS:
        assert f"Sec{land}EndPlane" in sketched, land
    cuts = [c.args[0] for c in adapter.create_cut_extrude.call_args_list]
    assert len(cuts) == len(spec.FLAT_LANDS)
    starts = (spec.COLLAR_END_STATION, *spec.SECTION_ENDS[1:-1])
    for params, land, start in zip(cuts, spec.FLAT_LANDS, starts):
        assert params.depth == pytest.approx(spec.SECTION_ENDS[land] - start), land
        assert not params.reverse_direction, land
    # The tip flat's cut starts at the end face: it runs out through the tip.
    assert spec.SECTION_ENDS[-1] == pytest.approx(spec.SHAFT_LENGTH)
    named = [c.args[1] for c in stubs["name_last_feature"].call_args_list]
    assert [f"Sec{land}Flat" for land in spec.FLAT_LANDS] == [
        name for name in named if name.endswith("Flat")
    ]


def test_shoulder_roots_are_modelled_not_noted() -> None:
    """The root radius is geometry with a size, not a sentence in a note block."""
    assert cone_gear_shaft_spec.FILLET_RADIUS == pytest.approx(0.10)
    # Its run along the smaller land is booked in every step's setback.
    for budget in cone_gear_shaft_spec.SEAT_STEP_BUDGET.values():
        assert budget["fillet"] == cone_gear_shaft_spec.FILLET_RADIUS
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "add_fillet(FILLET_RADIUS, fillet_edges, propagate=False)" in source
    assert 'name_last_feature(adapter, "ShoulderFillets")' in source
    assert 'name_dimensions(adapter, "ShoulderFillets", ["ShoulderR"])' in source
    # One feature, one dimension, one quantity prefix -- not three dimensions
    # (the gear-seat steps; the collar's roots stay sharp, #914).
    assert drawing.DIMENSION_CALLOUTS["ShoulderR"] == "3X"
    # The old "SHOULDER ROOTS R0.10 MAX" note is gone.  What remains names
    # the gear seats' and flats' mates (rule 2; codex 375a122c) without any
    # joint method (rule 6; user ruling 2026-09-28: the gears are a solid
    # touching stack keyed by the flats, nothing holds them but the D)
    # or a check of its own (no MUST), and carries
    # no number but the mates' part numbers, no tolerance, datum or method
    # word -- except the tailstock line, a user-ruled process requirement
    # (U40, 2026-09-23: the 22.93 mm Ø1.588 tip land at L/D 14.4 is only
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
    cone = _config.parts("cone-gear")["number"]
    crank = _config.parts("crank-drive-gear")["number"]
    bare = notes.replace(cone, "").replace(crank, "")
    assert not any(character.isdigit() for character in bare)
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
        "BOND",
        "RETAIN",
        "ADHESIVE",
    ):
        assert forbidden not in notes.upper()
    # U40: "TURN" appears only in the ruled tailstock line.
    assert "TURN" not in notes.upper().replace(tailstock[0].upper(), "")
    assert notes.splitlines()[0] == f"GEAR SEATS AND FLATS MATE {cone} AND {crank} BORES."
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
    # The journal that runs and the tip land the bushing and thrust spacer
    # ride keep their roughness symbol; nothing else does.
    assert source.count("add_surface_finish(") == 2
    assert tuple(control.key for control in cone_gear_shaft_spec.SURFACE_FINISHES) == (
        "pivot_journal",
        "tip_land",
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
            assert owners[name] == f'"{global_name}"', name
    # Each flat's length follows its land's knobs; its sketch is sized by the
    # land's diameter and across-flat globals.
    for land in cone_gear_shaft_spec.FLAT_LANDS:
        assert owners[f"Sec{land}FlatLength@Sec{land}Flat"] == part.flat_length_expression(
            land
        )
        assert records[f"Sec{land}AF"] == f'"SecAF{land}"'
        assert records[f"Sec{land}FarSide"] == f'"SecDia{land}" / 2'


def test_station_owners_cover_every_knob_once() -> None:
    spec = cone_gear_shaft_spec
    rows = {
        global_name: (value, names) for global_name, value, names in part.STATION_OWNERS
    }
    assert len(rows) == len(part.STATION_OWNERS)
    for i, knob in enumerate(spec.SECTION_KNOBS):
        assert rows[f"SecEnd{i}"][0] == knob
    assert rows["SecEnd0"][1] == ("Sec0End@Sec0", "CollarFaceStation@CollarFace")
    assert rows["CollarWidth"] == (
        spec.COLLAR_THICKNESS,
        ("CollarStation@CollarEndPlane", "CollarWidth@Collar"),
    )
    assert set(rows) == {*(f"SecEnd{i}" for i in range(len(spec.SECTIONS))), "CollarWidth"}


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
# post's north boss face, and the 64T stands on its north face.
def test_collar_fills_the_gap_between_the_post_boss_and_the_64t() -> None:
    spec = cone_gear_shaft_spec
    post_north_face = (
        drive.POST_STATION
        + drive.POST_CONE_BOSS_LENGTH / 2.0
        - drive.SHAFT_FRONT_STATION
    )
    gear64_south_face = (
        drive.GEAR64_CENTRE_STATION
        - drive.GEAR64_FACE / 2.0
        - drive.SHAFT_FRONT_STATION
    )
    assert spec.COLLAR_START_STATION == pytest.approx(post_north_face, abs=1e-9)
    assert spec.COLLAR_START_STATION == spec.JOURNAL_END
    assert spec.COLLAR_END_STATION == pytest.approx(gear64_south_face, abs=1e-9)
    assert spec.GEAR64_CENTER_STATION == pytest.approx(drive.GEAR64_CENTRE_STATION, abs=1e-9)


def test_the_64t_stands_on_the_collar_and_bears_on_t120() -> None:
    """User ruling 2026-09-28: the 64T's south face moves 1.5 north of the 8.0
    layout face's, the collar grows by exactly that, and the 64T's north face
    touches T120's south face (the stack is solid from the collar on)."""
    spec = cone_gear_shaft_spec
    south = (
        drive.GEAR64_STATION
        + drive.GEAR_AXIS_SHIFT
        - drive.GEAR64_LAYOUT_FACE / 2.0
        + drive.GEAR64_SOUTH_FACE_SHIFT_NORTH
    )
    assert spec.GEAR64_SOUTH_FACE_STATION == pytest.approx(south, abs=1e-9)
    assert drive.GEAR64_SOUTH_FACE_SHIFT_NORTH == 1.5
    web_under_8 = spec.COLLAR_THICKNESS - drive.GEAR64_SOUTH_FACE_SHIFT_NORTH
    assert web_under_8 == pytest.approx(1.681, abs=5e-4)
    assert spec.COLLAR_THICKNESS == pytest.approx(3.181, abs=5e-4)
    north = drive.GEAR64_CENTRE_STATION + drive.GEAR64_FACE / 2.0
    assert spec.GEAR64_NORTH_FACE_STATION == pytest.approx(north, abs=1e-9)
    t120_south = spec.gear_faces(0)[0]
    assert -1e-9 <= t120_south - spec.GEAR64_NORTH_FACE_STATION <= (
        cone_gear_stack.PITCH_LOCKSTEP_TOLERANCE
    )


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
    monkeypatch.setattr(part, "_sketch_x_per_model_x", lambda _a: -1.0)
    stubs["add_line_chain"].side_effect = lambda _a, points, close=True: [
        f"L{k}" for k in range(len(points) if close else len(points) - 1)
    ]
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


def test_the_build_hides_every_plane_it_creates(monkeypatch) -> None:
    """#950's save gate refuses a shown plane (cg-916: CollarFace and
    CollarEndPlane saved shown and failed part:cone_gear_shaft).  The repo's
    creator sweep only asks that a module hide SOME reference geometry, so it
    passed on the Sec planes; this pins every plane the shaft build creates,
    the two collar mate references included, as blanked by name."""
    adapter, stubs, _dims, _gated = _stubbed_build(monkeypatch)
    blanked = {
        name
        for c in stubs["blank_reference_geometry"].call_args_list
        for name, kind in c.args[1]
        if kind == "PLANE"
    }
    assert {"CollarFace", "CollarEndPlane"} <= blanked
    assert len(blanked) == len(adapter.create_plane.call_args_list)


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
    for land in spec.FLAT_LANDS:
        assert knobs[f"SecAF{land}"] == f"{spec.SECTION_FLAT_AF[land]}mm"
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
    # Each flatted step root is two edges: the round arc and the flat's line.
    assert len(edges) == 2 * (len(spec.SECTIONS) - 2)
    for step in (1, 2, 3):
        station = spec.SECTION_ENDS[step]
        assert [-spec.SECTION_DIAS[step + 1] / 2.0, 0.0, station] in edges, step
        assert [spec.FLAT_OFFSETS[step + 1], 0.0, station] in edges, step
    assert spec.FILLET_CALLOUT == f"{len(edges) // 2}X"
    named = [c.args[1] for c in stubs["name_last_feature"].call_args_list]
    assert "CollarFace" in named


def test_sketch_x_direction_is_read_from_the_sketch(monkeypatch) -> None:
    """A land end plane's sketch x runs along model X; its sign comes from the
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

    sketch = SimpleNamespace(ModelToSketchTransform=lambda xyz: tuple(xyz))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            SketchManager=SimpleNamespace(ActiveSketch=sketch)
        ),
        swApp=SimpleNamespace(GetMathUtility=_Utility),
    )
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    assert part._sketch_x_per_model_x(adapter) == 1.0
    sketch.ModelToSketchTransform = lambda xyz: (-xyz[0], xyz[1], -xyz[2])
    assert part._sketch_x_per_model_x(adapter) == -1.0
    sketch.ModelToSketchTransform = lambda xyz: (xyz[1], xyz[0], xyz[2])
    with pytest.raises(RuntimeError, match="not along model X"):
        part._sketch_x_per_model_x(adapter)
    monkeypatch.setattr(part, "double_array", list)
    with pytest.raises(RuntimeError, match="CreatePoint did not echo"):
        part._sketch_x_per_model_x(adapter)


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
    # collar-to-tip chain is one length, not the journal plus the overall.
    # It prints at three places: the tip flat's stack is held to it.
    for i in (1, 2, 3, 4):
        assert spec.SECTION_KNOBS[i] == pytest.approx(
            spec.SECTION_ENDS[i] - spec.COLLAR_START_STATION
        )
    assert spec.DRAWING_PRECISION_BY_NAME["Sec4End"] == 3
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


def test_drive_train_seats_the_shaft_and_64t_on_the_collar(monkeypatch) -> None:
    """#914: contacts, not distances -- the collar face ON the post's north
    boss face and the 64T's south face ON the collar's north face.  #916: both
    collar-seat faces are named planes; the post's BossNorth, carried through
    the post's installed placement, is the collar face's station on the cone
    line and faces north along it (the collar side)."""
    import asyncio
    from unittest.mock import AsyncMock

    import build_cone_pivot_post as post

    origin = drive.cone_station(drive.POST_STATION)
    origin[1] = drive.Y_BASE_TOP + drive.PLAT_T
    rows = drive.ROT_Y_180

    def placed(local: tuple[float, ...], shift: list[float]) -> list[float]:
        return [
            sum(local[i] * rows[i][k] for i in range(3)) + shift[k] for k in range(3)
        ]

    # The casting's incline is the cone line's rounded to 4 places, so the
    # face centre swings off the line by at most that angle times its lever.
    import cone_pivot_post_spec

    skew = abs(math.radians(cone_pivot_post_spec.INCLINE_DEG - drive.INCLINE_DEG))
    lever = math.hypot(*post.BOSS_NORTH_CENTRE[0::2])
    centre = placed(post.BOSS_NORTH_CENTRE, origin)
    assert centre == pytest.approx(
        drive.cone_station(drive._POST_NORTH_STATION), abs=skew * lever + 1e-9
    )
    normal = placed(post.BOSS_NORTH_NORMAL, [0.0, 0.0, 0.0])
    assert normal == pytest.approx([drive.SIN_I, 0.0, drive.COS_I], abs=skew + 1e-12)

    source = Path(drive.__file__).read_text(encoding="utf-8")
    assert 'named_ref(f"CollarFace@{cone_shaft}", "PLANE")' in source
    assert 'named_ref(f"BossNorth@{pivot_post}", "PLANE")' in source
    assert "bore_axis_ref" not in source
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
            drive.GEAR64_CENTRE_STATION,
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
