"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import _config
import _fit_shaft_h
import build_dt_cone_gear_shaft as part
import build_dt_drive_train_assembly as drive
import dt_cone_gear_shaft_spec
import dt_cone_gear_spec
import dt_cone_gear_stack
import cone_line
import dt_cone_pivot_post_installation
import dt_cone_pivot_post_spec
import cone_shaft_land_bands
import cone_stack_end_play
import dt_cone_tip_block_spec
import vn_cone_tip_collar_spec
import draw_dt_cone_gear_shaft as drawing
import pytest
from _drawing_annotation_extent import CLEAR_GAP_M
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME


# Which NAMED band each land rides (U27, 2026-09-23): the two running lands
# keep the shared h band, the three gear seats open to GEAR_SEAT_BAND.
_EXPECTED_LAND_BANDS = (
    ("RUNNING_DIA_BAND", _fit_shaft_h.SHAFT_H),
    ("GEAR_SEAT_BAND", dt_cone_gear_shaft_spec.GEAR_SEAT_BAND),
    ("GEAR_SEAT_BAND", dt_cone_gear_shaft_spec.GEAR_SEAT_BAND),
    ("GEAR_SEAT_BAND", dt_cone_gear_shaft_spec.GEAR_SEAT_BAND),
    ("RUNNING_DIA_BAND", _fit_shaft_h.SHAFT_H),
)


def _lands_ride_named_bands(bands: tuple[tuple[float, float], ...]) -> bool:
    """True when every land's band IS its named class, not an equal retype."""
    return len(bands) == len(_EXPECTED_LAND_BANDS) and all(
        band is getattr(dt_cone_gear_shaft_spec, name) is expected
        for band, (name, expected) in zip(bands, _EXPECTED_LAND_BANDS)
    )


def test_section_fits_are_toleranced_on_the_model() -> None:
    """Each turned land rides its NAMED fit class, applied to the model.

    Spelled as callout text the band is frozen: SolidWorks prints it verbatim
    and never re-renders it, so the mm->inch flip in issue #290 would leave
    "+0.00/-0.02" reading as inches on every land. The identity assertion also
    stops a local retype from silently forking a named class.
    """
    spec = dt_cone_gear_shaft_spec
    assert spec.RUNNING_DIA_BAND is _fit_shaft_h.SHAFT_H
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
    # The custom collar preserves the terminal land's retained slip class.
    tip_max = spec.SECTION_DIAS[-1] + spec.SECTION_DIA_BANDS[-1][0]
    collar_min = vn_cone_tip_collar_spec.BORE_DIA + vn_cone_tip_collar_spec.BORE_DIA_BAND[1]
    assert collar_min - tip_max >= 0.025 - 1e-9
    # Every flat rides the one named across-flat band.
    assert spec.FLAT_AF_BAND is cone_shaft_land_bands.FLAT_AF_BAND
    # Applied in ONE loop per family over the named bands, so the AST reports
    # the f-string sources rather than nine literal keys.
    assert model_toleranced_dimensions(part) == {
        ("f'Sec{section}Profile'", "f'Sec{section}Dia'"): "*deviations(band)",
        ("f'Sec{land}FlatProfile'", "f'Sec{land}AF'"): "*deviations(FLAT_AF_BAND)",
    }


def test_terminal_torque_corners_are_a_drawing_break_limit_not_geometry():
    lands = cone_shaft_land_bands
    assert dt_cone_gear_shaft_spec.TERMINAL_FLAT_EDGE_BREAK_MAX is lands.TERMINAL_FLAT_EDGE_BREAK_MAX
    radius = (lands.TERMINAL_DIA_MM + lands.RUNNING_DIA_BAND[1]) / 2.0
    flat = lands.SECTION_FLAT_AF[-1] - radius
    half_chord = math.sqrt(radius**2 - flat**2)
    dog = (
        lands.TIP_SCREW_DOG_PROJECTED_RADIUS_MM
        + lands.TIP_COLLAR_MAX_RADIAL_FLOAT_MM + lands.TIP_SCREW_DOG_AXIS_OFFSET_MM
    )
    assert half_chord - lands.TERMINAL_FLAT_EDGE_BREAK_MAX > dog
    # The title block's R0.25 would eat the dog's flat: the override is real,
    # and no break above the land radius less the dog budget fits at all.
    assert half_chord - 0.25 < dog
    assert lands.TERMINAL_FLAT_EDGE_BREAK_MAX <= radius - dog
    assert lands.TERMINAL_REQUIRED_HALF_CHORD_MM == pytest.approx(
        dog + lands.TERMINAL_FLAT_EDGE_BREAK_MAX
    )
    # The model keeps the corners sharp; the limit is printed once, above the
    # terminal across-flat.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "InsertFeatureChamfer" not in source
    assert "TerminalTorqueEdge" not in source
    assert "TerminalFlatEdgeBreak" not in dt_cone_gear_shaft_spec.DRAWING_DIMENSIONS
    callout = drawing.TORQUE_CORNER_CALLOUT
    assert f"{lands.TERMINAL_FLAT_EDGE_BREAK_MAX:.2f} MAX" in callout
    # Run 20261010T071427837Z: the two-line above callout was in COM but not
    # in the PDF.  One line, behind main's printable-above guard.
    assert drawing._printable_above_callouts({"Sec4AF": callout})
    with pytest.raises(RuntimeError, match="do not print"):
        drawing._printable_above_callouts({"Sec4AF": "TORQUE CORNERS:\nSTONE"})
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_printable_above_callouts({name: TORQUE_CORNER_CALLOUT})" in drawing_source
    assert "TerminalTorqueEdge" not in drawing.D_SECTION_KEEP


def test_display_precision_is_owned_by_the_part() -> None:
    """Policy rule 2: the .SLDPRT carries the places, the sheet reads them back."""
    assert "draw_dt_cone_gear_shaft.py" in PRECISION_MIGRATED_DRAWINGS
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
    # grade they are held to: three for the land steps booked in the setback;
    # two for the tip (user ruling 2026-09-29), whose .XX band the cone-tip
    # adjuster's embed window absorbs (build_drive_train_assembly); one for the
    # journal length, which nothing seats against.
    by_name = dt_cone_gear_shaft_spec.DRAWING_PRECISION_BY_NAME
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
        "Sec4End": 2,
        "Sec1AF": 3,
        "Sec2AF": 3,
        "Sec3AF": 3,
        "Sec4AF": 3,
        "ShoulderR": 2,
        # #914: the collar web is the 64T's station toward MHA-DT-005, so it
        # prints .XXX (crank_boss_rim).  The collar diameter is the bar's as
        # supplied, a two-place reference (15.88).
        "CollarDia": 2,
        "CollarWidth": 3,
    }
    # Rule 12: the web holds the 2.0 target at the low limit it prints.
    web = dt_cone_gear_shaft_spec.COLLAR_THICKNESS
    assert web - _config.title_block("linear_3pl")["value_in"] * 25.4 >= 2.0


def _band(places: int) -> float:
    """The title-block band a length prints at ``places``."""
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


def _setback_margin(j: int, step_band: float) -> float:
    """What the setback leaves when the step behind gear j's north face and
    its root reach north, the collar is short, the stack is short onto the
    collar and the fleet spare is held."""
    spec = dt_cone_gear_shaft_spec
    return spec.SEAT_STEP_SETBACK - (
        step_band
        + spec.FILLET_RADIUS
        + _band(3)  # the collar web prints .XXX
        - dt_cone_gear_stack.face_band(j, "north")[1]
        + cone_stack_end_play.MARGIN_SPARE
    )


def test_the_gears_are_a_touching_stack_on_the_collar() -> None:
    """User ruling 2026-09-28: each gear is cone_gear_spec.FACE_WIDTH thick
    and bears on the next; the 64T bears on the collar and on T120."""
    spec = dt_cone_gear_shaft_spec
    tolerance = dt_cone_gear_stack.PITCH_LOCKSTEP_TOLERANCE
    faces = [spec.gear_faces(j) for j in range(20)]
    for (_south, north), (next_south, _north) in zip(faces, faces[1:]):
        assert 0.0 <= next_south - north <= tolerance
    assert all(
        north - south == pytest.approx(dt_cone_gear_spec.FACE_WIDTH)
        for south, north in faces
    )
    # T006's north face remains on the cone line's reference face.
    assert faces[19][1] == pytest.approx(
        spec.T006_CENTER_STATION + cone_line.CONE_FACE_STATION_REFERENCE / 2.0
    )
    assert faces[0][0] - spec.GEAR64_NORTH_FACE_STATION == pytest.approx(0.0, abs=tolerance)
    assert spec.GEAR64_SOUTH_FACE_STATION == pytest.approx(
        spec.COLLAR_END_STATION - spec.FRONT_STUB
    )


def test_each_step_sits_one_setback_inside_the_larger_gear() -> None:
    """The steps T030|T024, T024|T018 and T018|T012 sit 1.0 south of the
    smaller gear's south face, inside the larger gear, and at print-worst
    the step and its root stay south of the smaller gear (margins 0.065,
    0.090, 0.115 with the .XXX step band)."""
    spec = dt_cone_gear_shaft_spec
    for name, j, end in zip(("Sec1End", "Sec2End", "Sec3End"), (15, 16, 17), spec.SECTION_ENDS[1:4]):
        station = end - spec.FRONT_STUB
        south, north = spec.gear_faces(j)
        assert station == pytest.approx(north - 1.0), name
        assert south < station - _band(3) and station + _band(3) + spec.FILLET_RADIUS < north
        margin = _setback_margin(j, _band(spec.DRAWING_PRECISION_BY_NAME[name]))
        assert margin >= 0.0, name
        assert spec.SEAT_STEP_BUDGET[name]["margin"] == pytest.approx(margin), name


def test_two_place_steps_would_reach_the_smaller_gear() -> None:
    """Why Sec1End..Sec3End print three places: the .XX band eats the setback."""
    for j in (15, 16, 17):
        assert _setback_margin(j, _band(2)) < 0.0, j


def test_gear_face_model_follows_the_drive_train() -> None:
    """The spec's seat pitch, reference face and gear face are the assembly's."""
    spec = dt_cone_gear_shaft_spec
    assert spec.SEAT_PITCH is dt_cone_gear_spec.SEAT_PITCH
    assert spec.SEAT_PITCH == pytest.approx(drive.SEAT_PITCH, abs=1e-12)
    assert spec.CONE_FACE_STATION_REFERENCE == drive.CONE_FACE_STATION_REFERENCE
    assert spec.CONE_GEAR_FACE_WIDTH == drive.CONE_FACE
    assert spec.T006_CENTER_STATION == pytest.approx(cone_line.T006_CENTER_STATION, abs=1e-9)
    for j in range(20):
        # BDT's seed: seat station plus half the south-side growth.
        centre = (
            drive.SHAFT_T120_STATION
            + dt_cone_pivot_post_installation.GEAR_AXIS_SHIFT
            + (drive.CONE_FACE_STATION_REFERENCE - drive.CONE_FACE) / 2.0
            + j * drive.SEAT_PITCH
        )
        south, north = spec.gear_faces(j)
        assert (south + north) / 2.0 == pytest.approx(centre, abs=1e-9)
        assert north - south == pytest.approx(drive.CONE_FACE)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cone-gear-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cone-gear-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-cone-gear-shaft_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_cone_gear_shaft"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is dt_cone_gear_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_cone_gear_shaft_spec.DRAWING_DIMENSIONS.values())
    assert (
        set(drawing.SIDE_KEEP) | set(drawing.SIDE_DIAMETERS) | set(drawing.D_SECTION_KEEP)
        == marked
    )
    # Nothing is imported twice, and the donor hands over exactly the six
    # diameters it was placed for (five lands and the collar, #914).
    assert set(drawing.DONOR_KEEP) == set(drawing.SIDE_DIAMETERS)
    assert not set(drawing.SIDE_KEEP) & set(drawing.DONOR_KEEP)
    assert not set(drawing.D_SECTION_KEEP) & (set(drawing.SIDE_KEEP) | set(drawing.DONOR_KEEP))
    assert part.SECTIONS is dt_cone_gear_shaft_spec.SECTIONS
    assert drawing.SHAFT_LENGTH == dt_cone_gear_shaft_spec.SHAFT_LENGTH
    assert drawing.SECTION_DIAS == dt_cone_gear_shaft_spec.SECTION_DIAS


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

    ends = dt_cone_gear_shaft_spec.SECTION_ENDS
    big_end = drawing.SIDE_CENTER[0] + dt_cone_gear_shaft_spec.SHAFT_LENGTH / 2000.0
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
            y > drawing.SIDE_CENTER[1] + dt_cone_gear_shaft_spec.SECTION_DIAS[0] / 2000.0
        )


def test_collar_diameter_stands_on_the_collar() -> None:
    """#914: the collar ring is too narrow for a dimension line with two
    arrows, so its diameter line stands inside that ring, above the shaft,
    clear of the pivot-journal finish symbol."""
    spec = dt_cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    ring = (
        big_end - spec.COLLAR_END_STATION / 1000.0,
        big_end - spec.COLLAR_START_STATION / 1000.0,
    )
    x, y = drawing.SIDE_DIAMETERS["CollarDia"]
    assert ring[0] < x < ring[1]
    assert y > drawing.SIDE_CENTER[1] + spec.COLLAR_DIA / 2000.0 + 0.010


# The mha014-1 leaf's read-off of MHA-DT-004 (9ec43110c, before any move): the
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
    spec = dt_cone_gear_shaft_spec
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
        *dt_cone_gear_shaft_spec.COLLAR_STOCK_CALLOUT.split("\n"),
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
    spec = dt_cone_gear_shaft_spec
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
    spec = dt_cone_gear_shaft_spec
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
    (on its parent's sheet) from the land's ends, and past the land's
    surface; on the side view it keeps 2 mm off that land's diameter line,
    on the tip detail it stays inside the circle over the whole land.  Each D
    is enlarged to 15 mm or more so its actual AF reads, and the four, each with
    its across-flat over it and its caption under it, stand apart right of
    the side view, inside the frame and off the title block (codex review,
    #1128: in one row the captions ran onto the title block and below the
    border)."""
    spec = dt_cone_gear_shaft_spec
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    margin = 0.0127
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    starts = (spec.COLLAR_END_STATION, *spec.SECTION_ENDS[1:-1])
    sections = drawing.D_SECTIONS
    assert tuple(section.land for section in sections) == spec.FLAT_LANDS
    caption_w, caption_h = drawing.SECTION_CAPTION_SIZE
    cells = []
    for section, start in zip(sections, starts):
        scale = drawing.CUT_PARENT_SCALE[section.parent]
        enlarge = scale[0] / scale[1]
        end = spec.SECTION_ENDS[section.land]
        radius = spec.SECTION_DIAS[section.land] / 2.0
        assert (section.station_mm - start) * enlarge >= 2.0, section
        assert (end - section.station_mm) * enlarge >= 2.0, section
        assert section.reach * 1000.0 / enlarge > radius, section
        if section.parent is drawing.CutParent.SIDE:
            cut_x = big_end - section.station_mm / 1000.0
            dia_x = drawing.SIDE_DIAMETERS[f"Sec{section.land}Dia"][0]
            assert abs(cut_x - dia_x) >= 0.002, section
        else:
            offset = abs(section.station_mm - drawing.TIP_DETAIL_STATION_MM)
            chord = math.sqrt((drawing.TIP_DETAIL_RADIUS * 1000.0) ** 2 - offset**2)
            assert chord >= radius, section
        across = spec.SECTION_DIAS[section.land] * section.scale[0] / section.scale[1]
        assert across >= 15.0, section
        half = across / 2000.0
        x, y = section.centre
        text_x, text_y = drawing.D_SECTION_KEEP[f"Sec{section.land}AF"]
        assert text_x == x and text_y > y + half, section
        # The terminal land's across-flat carries the torque-corner callout,
        # centred on its text (20261010T071427837Z: the run reached 6.9 mm
        # past the right border, and over C-C's outline).
        terminal = section.land == max(spec.FLAT_LANDS)
        reach_x, reach_y = drawing.TORQUE_CALLOUT_REACH if terminal else (0.0, 0.005)
        cell = (
            min(x - caption_w / 2.0, text_x - reach_x),
            y - half - drawing.SECTION_CAPTION_GAP - caption_h,
            max(x + caption_w / 2.0, text_x + reach_x),
            text_y + reach_y,
        )
        assert cell[0] > big_end + 0.02, section
        assert margin <= cell[0] and cell[2] <= template.width_m - margin - CLEAR_GAP_M, section
        assert margin <= cell[1] and cell[3] <= template.height_m - margin, section
        assert cell[1] > template.title_block_top_m, section
        if terminal:
            assert text_x - reach_x > drawing.SECTION_C_OUTLINE_RIGHT + CLEAR_GAP_M
        cells.append(cell)
    for index, a in enumerate(cells):
        for b in cells[index + 1 :]:
            assert a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1], (a, b)


# How far past its line a detail cutting line's letter reaches toward the big
# end: 19.9..21.3 mm measured (leaves 20260929T221513Z-1-22b951a7 and
# 20260929T235413Z-1-6ebc5952), SolidWorks' own placement, varying by seat.
_SECTION_LETTER_RUN_M = 0.0213


def test_each_detail_cutting_line_clears_the_next_by_a_margin() -> None:
    """Every arrow looks toward the big end, so each detail line's arrows and
    letters run toward its big-end neighbour's line.  At 24 mm apart D's letter
    crowded C's arrow at 1.7 mm on one seat (#1136); the worst measured letter
    must now clear the next line's arrow by the proof's 2 mm and 1.5 mm more."""
    enlarge = drawing.TIP_DETAIL_SCALE[0] / drawing.TIP_DETAIL_SCALE[1]
    lines = sorted(
        (s for s in drawing.D_SECTIONS if s.parent is drawing.CutParent.TIP_DETAIL),
        key=lambda section: section.station_mm,
    )
    for ahead, behind in zip(lines, lines[1:]):
        spacing = (behind.station_mm - ahead.station_mm) * enlarge / 1000.0
        gap = spacing - _SECTION_LETTER_RUN_M - drawing.SECTION_ARROW_HALF_WIDTH
        assert gap >= CLEAR_GAP_M + 0.0015, (behind.label, ahead.label, gap)


# How far above a side-view cutting line's lower end its letter's top stands:
# 4.8 mm on most seats, 6.3 mm on swmaker00000a (the 19e33c6c2 build).
_SECTION_LETTER_RISE_M = 0.0063


def test_each_side_view_cutting_line_letter_clears_its_land() -> None:
    """A side-view line's lower letter rises from the line's end back toward
    the land it cuts.  At a 12.5 mm reach A's letter stood 1.4 mm under land
    1 on one seat and the section proof refused it (19e33c6c2); the worst
    measured letter must clear the land by the proof's 2 mm and 1.5 mm more."""
    lines = [s for s in drawing.D_SECTIONS if s.parent is drawing.CutParent.SIDE]
    assert lines
    scale = drawing.CUT_PARENT_SCALE[drawing.CutParent.SIDE]
    axis_y = drawing.SIDE_CENTER[1]
    for section in lines:
        half = dt_cone_gear_shaft_spec.SECTION_DIAS[section.land] / 2000.0
        land_bottom = axis_y - half * scale[0] / scale[1]
        letter_top = axis_y - section.reach + _SECTION_LETTER_RISE_M
        gap = land_bottom - letter_top
        assert gap >= CLEAR_GAP_M + 0.0015, (section.label, gap)


def test_the_tip_detail_stands_in_the_frame_above_the_side_view() -> None:
    """The tip detail's cutting lines, letters included, run inside the
    frame's top and clear above the side view's highest diameter text; its
    circle stays off the R0.10 step at the Ø6.350 to Ø9.525 shoulder."""
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    letter = 0.00635
    reach = max(
        section.reach
        for section in drawing.D_SECTIONS
        if section.parent is drawing.CutParent.TIP_DETAIL
    )
    top = drawing.TIP_DETAIL_CENTER[1] + reach + letter
    bottom = drawing.TIP_DETAIL_CENTER[1] - reach - letter
    highest_text = max(y for _x, y in drawing.SIDE_DIAMETERS.values()) + letter
    assert top <= template.height_m - 0.0127
    assert bottom > highest_text + 0.002
    circle = drawing.TIP_DETAIL_RADIUS * 1000.0
    shoulder = dt_cone_gear_shaft_spec.SECTION_ENDS[1]
    assert drawing.TIP_DETAIL_STATION_MM - circle >= shoulder + 2.0


# Tip detail E as swmaker000004 read it on leaf 20261009T165136Z-1-acbeda8d:
# CreateDetailViewAt4's Position and outline (bit-identical on all seven leaves
# that logged them), and the tip centre's offset from Position once the
# transform is current (every passing leaf: centre (0.09999997441408104,
# 0.236) at Position (0.24755930006504057, 0.23600000000000002)).
_SEAT_TIP_POSITION = (0.24717657096805057, 0.23644341806020072)
_SEAT_TIP_OUTLINE = (
    0.07242928077353916,
    0.2232354181522899,
    0.1268052610324808,
    0.24965141796811155,
)
_SEAT_TIP_CENTRE_FROM_POSITION = (
    0.09999997441408104 - 0.24755930006504057,
    0.236 - 0.23600000000000002,
)


class _SeatTipDetail:
    """A fresh detail whose ModelToViewTransform stays where
    CreateDetailViewAt4 first put the view (TIP_DETAIL_CENTER) through every
    rebuild, while Position and the outline follow SetViewPosition; only
    UpdateViewDisplayGeometry brings it up to date, unless ``refreshes`` is
    False."""

    def __init__(self, events: list[str], *, refreshes: bool) -> None:
        self.events = events
        self.refreshes = refreshes
        self.ScaleRatio = (4.0, 1.0)
        self.position = _SEAT_TIP_POSITION
        self.outline = _SEAT_TIP_OUTLINE
        self.transform_at = drawing.TIP_DETAIL_CENTER

    @property
    def Position(self) -> tuple[float, float]:  # noqa: N802
        return self.position

    def GetOutline(self) -> tuple[float, ...]:  # noqa: N802
        return self.outline

    def SetViewPosition(self, xy, _keep_relative) -> bool:  # noqa: N802
        dx, dy = xy[0] - self.position[0], xy[1] - self.position[1]
        x0, y0, x1, y1 = self.outline
        self.outline = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        self.position = (float(xy[0]), float(xy[1]))
        return True

    def UpdateViewDisplayGeometry(self) -> None:  # noqa: N802
        self.events.append("update display geometry")
        if self.refreshes:
            self.transform_at = self.position

    def project_centre(self) -> tuple[float, float]:
        self.events.append("project tip centre")
        return (
            self.transform_at[0] + _SEAT_TIP_CENTRE_FROM_POSITION[0],
            self.transform_at[1] + _SEAT_TIP_CENTRE_FROM_POSITION[1],
        )


def _tip_detail_on_seat(monkeypatch, *, refreshes: bool):
    """Run _create_tip_detail against the swmaker000004 seat, COM-free."""
    from types import SimpleNamespace

    events: list[str] = []
    detail = _SeatTipDetail(events, refreshes=refreshes)
    circle = SimpleNamespace(Select4=lambda _append, _data: True)
    draw = SimpleNamespace(
        ActivateView=lambda _name: True,
        ClearSelection2=lambda _all: None,
        SketchManager=SimpleNamespace(AddToDB=False, CreateCircle=lambda *_: circle),
        SelectionManager=SimpleNamespace(CreateSelectData=SimpleNamespace),
        CreateDetailViewAt4=lambda *_: detail,
    )
    side = object()

    def points_in_view(_adapter, view, points, *, label, names=None):
        if view is detail:
            return [detail.project_centre() for _point in points]
        return [(0.078, 0.15), (0.078, 0.159)][: len(points)]

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        drawing,
        "_sw_type_info",
        SimpleNamespace(early_bound_or_flag=lambda obj, *_members: obj),
    )
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "Drawing View1")
    monkeypatch.setattr(drawing, "model_points_in_view", points_in_view)
    monkeypatch.setattr(
        drawing,
        "_sheet_segment_in_parent_sketch",
        lambda _adapter, _parent, sheet: [(x, y, 0.0) for x, y in sheet],
    )
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(
        drawing,
        "rebuild_drawing",
        lambda _adapter, *, label: events.append(f"rebuild {label}"),
    )
    adapter = SimpleNamespace(currentModel=draw)
    return drawing._create_tip_detail(adapter, side, -1), detail, events


def test_the_tip_detail_projects_only_behind_the_display_barrier(monkeypatch) -> None:
    """Leaf 20261009T165136Z-1-acbeda8d: three settle rebuilds left the tip
    detail's transform where CreateDetailViewAt4 first put the view, so the
    centre read (-0.0476, 0.236) under ink centred on (0.1, 0.236).  Every
    projection read is now taken behind UpdateViewDisplayGeometry, so a seat
    whose rebuilds never refresh the transform reads it current."""
    built, detail, events = _tip_detail_on_seat(monkeypatch, refreshes=True)
    assert built is detail
    reads = [
        index for index, event in enumerate(events) if event == "project tip centre"
    ]
    assert reads == [events.index("rebuild place tip detail") + 2]
    assert events[reads[0] - 1] == "update display geometry"
    assert "rebuild settle tip detail" not in events
    assert detail.project_centre() == pytest.approx(drawing.TIP_DETAIL_CENTER, abs=1e-7)


def test_a_tip_detail_transform_that_never_catches_up_still_fails(monkeypatch) -> None:
    """The check is not loosened: a transform the barrier cannot refresh
    reproduces the farm's numbers and fails, naming the ink it disagrees with."""
    with pytest.raises(RuntimeError) as failure:
        _tip_detail_on_seat(monkeypatch, refreshes=False)
    message = str(failure.value)
    projected = re.search(r"projects its centre to \(([^,]+), ([^)]+)\)", message)
    assert projected is not None, message
    assert float(projected[1]) == pytest.approx(-0.04755932565095955, abs=1e-15)
    assert float(projected[2]) == pytest.approx(0.236, abs=1e-12)
    assert "outline (0.0728120098" in message and "Position (0.2475593000" in message


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
    sections = dt_cone_gear_shaft_spec.SECTIONS
    assert len(sections) == 5
    dias = dt_cone_gear_shaft_spec.SECTION_DIAS
    ends = dt_cone_gear_shaft_spec.SECTION_ENDS
    assert all(a > b for a, b in zip(dias, dias[1:]))
    assert all(a < b for a, b in zip(ends, ends[1:]))
    # The integral bearing journal fits the v2 post at 0.05 diametral
    # clearance; every downstream gear seat keeps its existing diameter.
    assert dt_cone_gear_shaft_spec.JOURNAL_BORE_DIA == pytest.approx(12.2808)
    assert dt_cone_gear_shaft_spec.JOURNAL_CLEARANCE == pytest.approx(0.05)
    assert dt_cone_gear_shaft_spec.JOURNAL_DIA == pytest.approx(12.2308)
    assert dt_cone_gear_shaft_spec.JOURNAL_END == pytest.approx(43.011)
    assert dias[-1] == cone_shaft_land_bands.TERMINAL_DIA_MM
    assert dias[:-1] == pytest.approx((12.2308, 9.525, 6.35, 3.175))
    assert dt_cone_gear_shaft_spec.FRONT_STUB == pytest.approx(
        -cone_line.POST_STATION
        + dt_cone_pivot_post_spec.CONE_BOSS_LENGTH / 2.0
        + dt_cone_gear_shaft_spec.JOURNAL_PROUD
    )
    # Convert the local collar face back to the shared cone station: it must
    # bear on the post's north boss face, independent of the incline/grid.
    assert (
        dt_cone_gear_shaft_spec.COLLAR_START_STATION
        - dt_cone_gear_shaft_spec.FRONT_STUB
    ) == pytest.approx(
        cone_line.POST_STATION + dt_cone_pivot_post_spec.CONE_BOSS_LENGTH / 2.0
    )
    # The tip chain (user ruling 2026-09-29): the MHA-VN-016 collar stands one
    # feeler off T006's north face; the block's north face stands the
    # pivot-screw head's air south of the pivot and the block grows south.
    # Every length is its owner's, not a copy.
    assert dt_cone_gear_shaft_spec.T006_NORTH_FACE_STATION == pytest.approx(
        cone_line.T006_NORTH_FACE
    )
    assert dt_cone_gear_shaft_spec.TIP_COLLAR_WIDTH == vn_cone_tip_collar_spec.WIDTH
    assert dt_cone_gear_shaft_spec.TIP_COLLAR_START_STATION == pytest.approx(
        dt_cone_gear_shaft_spec.T006_NORTH_FACE_STATION + cone_stack_end_play.COLLAR_FEELER
    )
    assert dt_cone_gear_shaft_spec.TIP_BLOCK_LENGTH == dt_cone_tip_block_spec.BLOCK_Z
    assert dt_cone_gear_shaft_spec.TIP_BLOCK_NORTH_FACE_STATION == pytest.approx(
        cone_line.TIP_BLOCK_NORTH_FACE
    )
    assert dt_cone_gear_shaft_spec.TIP_BLOCK_SOUTH_FACE_STATION + (
        dt_cone_gear_shaft_spec.TIP_BLOCK_LENGTH / 2.0
    ) == pytest.approx(cone_line.TIP_BLOCK_STATION)
    assert dt_cone_gear_shaft_spec.TIP_BLOCK_NORTH_FACE_STATION == pytest.approx(
        cone_line.PIVOT_STATION - cone_line.TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET
    )
    # Rule-12 E11: #10-32 94025A164 at the block spec's fit-up embed.
    assert dt_cone_gear_shaft_spec.ADJUSTER_EMBED == dt_cone_tip_block_spec.ADJUSTER_EMBED
    assert dt_cone_gear_shaft_spec.ADJUSTER_CUP_RIM_STATION == pytest.approx(
        cone_line.TIP_BLOCK_NORTH_FACE - dt_cone_tip_block_spec.ADJUSTER_EMBED
    )
    # Vendor Sketch2 Line7: the pure stock spec owns the actual cup, not this shaft.
    import _mcmaster_94025a164
    assert dt_cone_gear_shaft_spec.CUP_DEPTH == _mcmaster_94025a164.CUP_DEPTH
    assert dt_cone_gear_shaft_spec.T006_TIP_STATION == pytest.approx(
        dt_cone_gear_shaft_spec.ADJUSTER_CUP_RIM_STATION
        + _mcmaster_94025a164.CUP_DEPTH
    )
    assert dt_cone_gear_shaft_spec.SHAFT_LENGTH == (
        dt_cone_gear_shaft_spec.FRONT_STUB + dt_cone_gear_shaft_spec.T006_TIP_STATION
    )
    # Each land step sits one setback behind the larger gear's north face
    # (T030|T024, T024|T018, T018|T012), so the actual terminal land carries
    # T012 and T006 and runs on to the retained cup apex.
    assert ends[1:-1] == pytest.approx(
        tuple(
            dt_cone_gear_shaft_spec.FRONT_STUB + dt_cone_gear_shaft_spec.seat_step_station(j)
            for j in (15, 16, 17)
        )
    )
    # Native station knobs and printed baselines share the collar-face origin.
    assert dt_cone_gear_shaft_spec.SECTION_KNOBS[1:] == pytest.approx(
        tuple(end - dt_cone_gear_shaft_spec.COLLAR_START_STATION for end in ends[1:])
    )
    # The terminal stub starts at the T018 interface setback and extends to
    # the cup apex, rather than a frozen shaft-length snapshot.
    assert dt_cone_gear_shaft_spec.TIP_STUB_START_STATION == pytest.approx(
        cone_line.T006_NORTH_FACE
        - 2.0 * dt_cone_gear_spec.SEAT_PITCH
        - dt_cone_gear_shaft_spec.SEAT_STEP_SETBACK
    )
    assert dt_cone_gear_shaft_spec.TIP_STUB_LENGTH == pytest.approx(
        dt_cone_gear_shaft_spec.T006_TIP_STATION
        - dt_cone_gear_shaft_spec.TIP_STUB_START_STATION
    )
    assert ends[-1] - ends[-2] == pytest.approx(
        dt_cone_gear_shaft_spec.TIP_STUB_LENGTH
    )
    assert (
        dt_cone_gear_shaft_spec.TIP_STUB_START_STATION
        <= dt_cone_gear_shaft_spec.TIP_COLLAR_START_STATION
    )
    assert (
        dt_cone_gear_shaft_spec.TIP_COLLAR_END_STATION
        <= dt_cone_gear_shaft_spec.TIP_BLOCK_SOUTH_FACE_STATION
    )


def test_custom_tip_collar_stays_wholly_on_the_terminal_land_at_printed_limits() -> None:
    """Use the accepted stack owner, not a second axial budget or a stock width."""
    import dt_cone_gear_stack as stack

    shaft = dt_cone_gear_shaft_spec
    collar = vn_cone_tip_collar_spec
    face_upper, face_lower = stack.face_band(stack.COUNT - 1, "north")
    collar_south_min = (
        shaft.TIP_COLLAR_START_STATION - shaft.printed_band("CollarWidth")
        + face_lower - cone_stack_end_play.COLLAR_FEELER_BAND
    )
    collar_north_max = (
        shaft.TIP_COLLAR_END_STATION + shaft.printed_band("CollarWidth")
        + face_upper + cone_stack_end_play.COLLAR_FEELER_BAND + collar.WIDTH_BAND_MM
    )
    root_north_max = (
        shaft.TIP_STUB_START_STATION + shaft.printed_band("Sec3End")
        + shaft.FILLET_RADIUS + shaft.printed_band("ShoulderR")
    )
    shaft_tip_min = shaft.SHAFT_LENGTH - shaft.printed_band("Sec4End")
    assert shaft.TIP_COLLAR_END_STATION - shaft.TIP_COLLAR_START_STATION == pytest.approx(collar.WIDTH)
    assert collar_south_min >= root_north_max
    assert collar_north_max <= shaft_tip_min


def test_every_gear_land_carries_one_d_flat() -> None:
    """User ruling 2026-09-28: each gear land is a D whose across-flat is its
    section's; the flat's plane is the AF less the round half-diameter."""
    spec = dt_cone_gear_shaft_spec
    assert spec.FLAT_LANDS == (1, 2, 3, 4)
    assert spec.SECTION_FLAT_AF is cone_shaft_land_bands.SECTION_FLAT_AF
    assert spec.FLAT_OFFSETS == pytest.approx(tuple(
        None if af is None else af - dia / 2.0
        for af, dia in zip(cone_shaft_land_bands.SECTION_FLAT_AF, spec.SECTION_DIAS)
    ))
    assert spec.SECTION_FLAT_AF[-1] == cone_shaft_land_bands.TERMINAL_FLAT_AF_MM
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
    spec = dt_cone_gear_shaft_spec
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
    assert dt_cone_gear_shaft_spec.FILLET_RADIUS == pytest.approx(0.10)
    # Its run along the smaller land is booked in every step's setback.
    for budget in dt_cone_gear_shaft_spec.SEAT_STEP_BUDGET.values():
        assert budget["fillet"] == dt_cone_gear_shaft_spec.FILLET_RADIUS
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
    # (U40, 2026-09-23: the 25.24 mm Ø1.588 tip land at L/D 15.9 is only
    # turnable supported), so "TURN" is allowed in that one line only.  The
    # three-place-stations lines went in the U27 round: the places already
    # say it.
    notes = dt_cone_gear_shaft_spec.DRAWING_NOTES
    assert 1 <= len(notes.splitlines()) <= 4
    # The sheet's note text runs ~2.7 mm per character; a line from the
    # note anchor must end before the title block at x = 0.216 m (the
    # first render's 67-character line ran under the tolerance table).
    assert max(len(line) for line in notes.splitlines()) * 0.0027 < (
        0.216 - drawing.NOTES_XY[0]
    )
    cone = _config.parts("dt-cone-gear")["number"]
    crank = _config.parts("dt-crank-drive-gear")["number"]
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
    assert not hasattr(dt_cone_gear_shaft_spec, "PART_DATUMS")
    assert not hasattr(dt_cone_gear_shaft_spec, "GEOMETRIC_CONTROLS")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for banned in (
        "project_part_pmi(",
        "add_feature_control_frame(",
        "add_datum_feature(",
    ):
        assert banned not in source
    # The journal that runs and the tip land T012, T006 and the MHA-VN-016
    # collar ride keep their roughness symbol; nothing else does.
    assert source.count("add_surface_finish(") == 2
    assert tuple(control.key for control in dt_cone_gear_shaft_spec.SURFACE_FINISHES) == (
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
    assert '"*Front"' in source  # the donor, and only as a donor
    assert "delete_view(adapter, donor)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("dt-cone-gear-shaft")
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


def test_configured_tip_gears_require_tip_first_shaft_assembly() -> None:
    """The current cone tips cannot pass over the next inboard gear bore."""
    spec = dt_cone_gear_shaft_spec
    assert spec.outside_dia_mm is dt_cone_gear_spec.outside_dia_mm
    for teeth, next_bore_land in ((6, 4), (12, 3), (18, 2), (24, 1)):
        tip_dia = dt_cone_gear_spec.outside_dia_mm(teeth)
        assert tip_dia > spec.SECTION_DIAS[next_bore_land], teeth


def test_shaft_loading_preflight_reads_each_accepted_tip(monkeypatch) -> None:
    spec = dt_cone_gear_shaft_spec
    rows = ((6, 4), (12, 3), (18, 2), (24, 1))
    by_teeth = {teeth: spec.SECTION_DIAS[land] + 1.0 for teeth, land in rows}
    calls = []
    monkeypatch.setattr(spec, "outside_dia_mm", lambda teeth: calls.append(teeth) or by_teeth[teeth])
    spec.validate_gear_loading_clearances()
    assert calls == [teeth for teeth, _land in rows]
    for teeth, land in rows:
        previous = by_teeth[teeth]
        by_teeth[teeth] = spec.SECTION_DIAS[land]
        with pytest.raises(AssertionError, match=f"T{teeth:03d}"):
            spec.validate_gear_loading_clearances()
        by_teeth[teeth] = previous


def test_refused_cutter_family_reaches_no_native_shaft_geometry(monkeypatch) -> None:
    import asyncio
    from unittest.mock import AsyncMock

    def refused(_teeth):
        raise ValueError("cutter family refused")

    monkeypatch.setattr(dt_cone_gear_shaft_spec, "outside_dia_mm", refused)
    adapter = AsyncMock()
    with pytest.raises(ValueError, match="cutter family refused"):
        asyncio.run(part.build(adapter))
    adapter.create_part.assert_not_awaited()


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
    for land in dt_cone_gear_shaft_spec.FLAT_LANDS:
        assert owners[f"Sec{land}FlatLength@Sec{land}Flat"] == part.flat_length_expression(
            land
        )
        assert records[f"Sec{land}AF"] == f'"SecAF{land}"'
        assert records[f"Sec{land}FarSide"] == f'"SecDia{land}" / 2'


def test_station_owners_cover_every_knob_once() -> None:
    spec = dt_cone_gear_shaft_spec
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
        dt_cone_gear_shaft_spec.SECTION_KNOBS[4] + 1e-3
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
    spec = dt_cone_gear_shaft_spec
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
    spec = dt_cone_gear_shaft_spec
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
        dt_cone_gear_stack.PITCH_LOCKSTEP_TOLERANCE
    )


def test_the_collar_is_the_bar_as_supplied_and_its_thrust_ring_holds_the_floor() -> None:
    """Codex P1 on #916: a turned Ø15.0 at .X could come out Ø14.2 and leave a
    0.96 thrust ring on the post boss.  User ruling 2026-09-26: the collar is
    the 5/8 cold-finished bar's own OD, and both edges bounding the ring print
    a break small enough that the worst-case ring, breaks counted, holds 1.5."""
    import dt_cone_pivot_post_spec as post

    spec = dt_cone_gear_shaft_spec
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
    spec = dt_cone_gear_shaft_spec
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
    CollarEndPlane saved shown and failed part:dt_cone_gear_shaft).  The repo's
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
    spec = dt_cone_gear_shaft_spec
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
    spec = dt_cone_gear_shaft_spec
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
    spec = dt_cone_gear_shaft_spec
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
    # It prints at two places (user ruling 2026-09-29): the adjuster's embed
    # window absorbs its band.
    for i in (1, 2, 3, 4):
        assert spec.SECTION_KNOBS[i] == pytest.approx(
            spec.SECTION_ENDS[i] - spec.COLLAR_START_STATION
        )
    assert spec.DRAWING_PRECISION_BY_NAME["Sec4End"] == 2
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
    spec = dt_cone_gear_shaft_spec
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

    import build_dt_cone_pivot_post as post

    origin = drive.cone_station(drive.POST_STATION)
    origin[1] = drive.Y_BASE_TOP + drive.PLAT_T
    rows = drive.ROT_Y_180

    def placed(local: tuple[float, ...], shift: list[float]) -> list[float]:
        return [
            sum(local[i] * rows[i][k] for i in range(3)) + shift[k] for k in range(3)
        ]

    # The casting's incline is the cone line's rounded to 4 places, so the
    # face centre swings off the line by at most that angle times its lever.
    import dt_cone_pivot_post_spec

    skew = abs(math.radians(dt_cone_pivot_post_spec.INCLINE_DEG - drive.INCLINE_DEG))
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
    import build_dt_crank_drive_gear

    placed = {}

    async def place_component(_adapter, part_name, origin, *_args, **_kwargs):
        placed[part_name] = origin
        return f"{part_name}-1"

    monkeypatch.setattr(drive, "place_component", place_component)
    asyncio.run(
        drive._place_on_shaft(
            object(),
            "dt-crank-drive-gear",
            drive.GEAR64_CENTRE_STATION,
            drive.GEAR64_FACE,
        )
    )
    south = drive.cone_station(drive._GEAR64_SOUTH_STATION)
    assert placed["dt-crank-drive-gear"] == pytest.approx(south, abs=1e-9)

    blank = inspect.getsource(_gear._build_helical_stock_form_gear)
    assert 'check("create_sketch stock base", await adapter.create_sketch("Front"))' in blank
    assert "create_extrusion(ExtrusionParameters(depth=face_width))" in blank
    crank = inspect.getsource(build_dt_crank_drive_gear.build)
    assert "screw_sweep_bound_mm=NATIVE_SWEEP_BOUND_MM" in crank


def test_the_64t_native_stock_tooth_preserves_material_and_phase_gates(monkeypatch) -> None:
    """Record the released helper's real profile recipe, without native CAD."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import _gear
    import dt_crank_drive_gear_spec as gear

    profile = gear.STOCK_PROFILE
    face = gear.FACE_WIDTH
    assert profile.teeth == gear.TEETH
    assert profile.helix_angle_deg == cone_line.INCLINE_DEG
    assert profile.helix_angle_deg > 0.0
    base_radius = profile.foot_radius_mm
    twist = face * math.tan(math.radians(profile.helix_angle_deg)) / profile.pitch_radius_mm
    material_calls = []
    emitted = []
    events = []
    volumes = {}
    tooth_body = type(profile).tooth_body_segments

    def record_material_sector(self, **kwargs):
        segments = tooth_body(self, **kwargs)
        material_calls.append((kwargs, segments))
        return segments

    async def record_curve(_adapter, name, x, y):
        emitted.append((name, x, y))
        return name

    async def record_volume(_adapter, label, expected, tolerance):
        volumes[label] = (expected, tolerance)
        events.append(label)
        return expected

    async def record_sweep(_adapter, width, *, twist_deg):
        assert width == face
        assert twist_deg == pytest.approx(math.degrees(twist))
        events.append("sweep")
        return "StockSweep"

    def record_probe(_adapter, actual_profile, width, *, midface_tooth_phase_rad, tolerance_mm):
        assert tolerance_mm == gear.NATIVE_SWEEP_BOUND_MM
        assert actual_profile is profile
        assert width == face
        assert midface_tooth_phase_rad == 0.0
        events.append("native phase probe")

    async def record_pattern(_adapter, seed, teeth, radius, station):
        assert (seed, teeth, radius, station) == (
            "StockSweep", profile.teeth, profile.blank_radius_mm, face / 2.0
        )
        events.append("pattern")
        return SimpleNamespace(name="StockPattern")

    monkeypatch.setattr(type(profile), "tooth_body_segments", record_material_sector)
    monkeypatch.setattr(_gear, "check", lambda _label, value: value)
    for name in ("define_circle", "ensure_fully_defined"):
        monkeypatch.setattr(_gear, name, AsyncMock())
    monkeypatch.setattr(_gear, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(_gear, "equation_curve", record_curve)
    monkeypatch.setattr(_gear, "volume_check", record_volume)
    monkeypatch.setattr(_gear, "_sweep_tooth_sketch", record_sweep)
    monkeypatch.setattr(_gear, "assert_stock_screw_sweep_phase", record_probe)
    monkeypatch.setattr(_gear, "pattern_about_z", record_pattern)
    adapter = AsyncMock()
    disc = asyncio.run(
        _gear.build_stock_form_gear(
            adapter, profile, face, screw_sweep_bound_mm=gear.NATIVE_SWEEP_BOUND_MM
        )
    )

    assert adapter.create_sketch.await_args_list[0].args == ("Front",)
    extrusion = adapter.create_extrusion.await_args.args[0]
    assert extrusion.depth == face
    assert not extrusion.reverse_direction
    assert material_calls[0][0] == {
        "unit_scale": 1.0 / _gear.IN,
        "embed_radius_mm": base_radius - _gear._TOOTH_EMBED_MM,
        "rotate_rad": pytest.approx(-twist / 2.0),
    }
    assert len(material_calls) == 1
    assert emitted == [(s.name, s.x, s.y) for s in material_calls[0][1]]
    base_area = math.pi * base_radius**2
    blank_area = math.pi * profile.blank_radius_mm**2
    sector_area = (blank_area - base_area) / profile.teeth - profile.gap_area_mm2
    assert sector_area > 0.0
    seed_volume = (base_area + sector_area) * face
    final_volume = (blank_area - profile.teeth * profile.gap_area_mm2) * face
    assert volumes["seeded tooth/gap"] == (pytest.approx(seed_volume), 1.0)
    assert volumes["toothed disc"] == (
        pytest.approx(final_volume), pytest.approx(0.01 * final_volume)
    )
    assert events.index("seeded tooth/gap") < events.index("native phase probe")
    assert events.index("native phase probe") < events.index("pattern")
    assert events.index("pattern") < events.index("toothed disc")
    assert disc.volume == pytest.approx(final_volume)
    assert disc.tooth_features == ("StockSweep", "StockPattern")


@pytest.mark.parametrize(
    "twist_sign, phase_offset",
    [(1.0, 0.0), (0.0, 0.0), (-1.0, 0.0), (1.0, 0.2)],
)
def test_the_64t_phase_gate_samples_physical_flanks_and_rejects_wrong_sweeps(
    monkeypatch, twist_sign, phase_offset
) -> None:
    """Synthetic native flank points exercise the gate, not a sweep option bag."""
    from types import SimpleNamespace

    import _gear
    import dt_crank_drive_gear_spec as gear

    profile = gear.STOCK_PROFILE
    face_width = gear.FACE_WIDTH
    twist_per_mm = math.tan(math.radians(profile.helix_angle_deg)) / profile.pitch_radius_mm
    native_points = []
    for fraction in (0.25, 0.5, 0.75):
        z = face_width * fraction
        phase = phase_offset + twist_sign * (z - face_width / 2.0) * twist_per_mm
        for side in (-1, 1):
            for flank_fraction in (0.25, 0.75):
                parameter = profile.flank_parameter_min + flank_fraction * (
                    profile.flank_parameter_max - profile.flank_parameter_min
                )
                x, y = profile.flank_point(parameter, side=side)
                angle = phase - side * math.pi / profile.teeth
                cosine, sine = math.cos(angle), math.sin(angle)
                native_points.append((x * cosine - y * sine, x * sine + y * cosine, z))
    queries = []

    def closest_point(x, y, z):
        query = (x * 1000.0, y * 1000.0, z * 1000.0)
        queries.append(query)
        closest = min(native_points, key=lambda point: math.dist(query, point))
        return (*(value / 1000.0 for value in closest), 0.0, 0.0)

    native_face = SimpleNamespace(GetClosestPointOn=closest_point)
    body = SimpleNamespace(GetFaces=lambda: [native_face])
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetBodies2=lambda *_args: [body])
    )
    monkeypatch.setattr(_gear, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(_gear._telemetry, "info", lambda *_args: None)
    if twist_sign == 1.0 and phase_offset == 0.0:
        _gear.assert_stock_screw_sweep_phase(
            adapter, profile, face_width, tolerance_mm=gear.NATIVE_SWEEP_BOUND_MM
        )
        for query, native in zip(queries, native_points, strict=True):
            assert query == pytest.approx(native)
    else:
        with pytest.raises(RuntimeError, match="stock screw-sweep phase mismatch"):
            _gear.assert_stock_screw_sweep_phase(
                adapter, profile, face_width, tolerance_mm=gear.NATIVE_SWEEP_BOUND_MM
            )
    assert len(queries) == 12
    assert sorted({point[2] for point in queries}) == pytest.approx(
        [face_width / 4.0, face_width / 2.0, 3.0 * face_width / 4.0]
    )
