"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import _config
from _printed_tolerance import printed_band_mm, printed_deviations
import _fit_shaft_h
import build_dt_cone_gear_shaft as part
import build_dt_drive_train_assembly as drive
import dt_cone_gear_shaft_spec
import dt_cone_gear_spec
import dt_cone_gear_stack
import cone_line
import _cone_axis_constants
import dt_cone_pivot_post_spec
import cone_land_key
import cone_shaft_land_bands
import gear_seat_fit
import cone_stack_end_play
import cone_tip_cluster
import draw_dt_cone_gear_shaft as drawing
import pytest
from _drawing_annotation_extent import CLEAR_GAP_M
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES


# Which NAMED band each land rides (U27, 2026-09-23): the running journal
# keeps the shared h band, the two gear lands open to GEAR_SEAT_BAND.
_EXPECTED_LAND_BANDS = (
    ("RUNNING_DIA_BAND", _fit_shaft_h.SHAFT_H),
    ("GEAR_SEAT_BAND", dt_cone_gear_shaft_spec.GEAR_SEAT_BAND),
    ("GEAR_SEAT_BAND", dt_cone_gear_shaft_spec.GEAR_SEAT_BAND),
)


def _lands_ride_named_bands(bands: tuple[tuple[float, float], ...]) -> bool:
    """True when every land's band IS its named class, not an equal retype."""
    return len(bands) == len(_EXPECTED_LAND_BANDS) and all(
        band is getattr(dt_cone_gear_shaft_spec, name) is expected
        for band, (name, expected) in zip(bands, _EXPECTED_LAND_BANDS)
    )


def test_section_fits_are_toleranced_on_the_model() -> None:
    """Each turned land rides its NAMED fit class as its ANALYSIS band; the
    model carries no band on it: the journal and both lands are turned last
    to their mates and print as references, and the socket prints its
    reamer's size (fit audit 2026-11-23, rule 4 form 2). Only the keyseat
    and the root radius carry model bands.

    The identity assertion stops a local retype from silently forking a
    named class.
    """
    spec = dt_cone_gear_shaft_spec
    assert spec.RUNNING_DIA_BAND is _fit_shaft_h.SHAFT_H
    assert spec.GEAR_SEAT_BAND == (0.0, -0.0508)
    assert _lands_ride_named_bands(spec.SECTION_DIA_BANDS)
    # Positive control: an equal-valued local retype of either class is caught.
    forked = list(spec.SECTION_DIA_BANDS)
    forked[2] = (0.0, -0.0508)
    assert forked[2] == spec.GEAR_SEAT_BAND
    assert not _lands_ride_named_bands(tuple(forked))
    forked = list(spec.SECTION_DIA_BANDS)
    forked[0] = (0.0, -0.02032)
    assert not _lands_ride_named_bands(tuple(forked))
    # The socket's analysis band is the tip cluster's reamed stem-bore band.
    assert spec.SOCKET_DIA_BAND is cone_tip_cluster.STEM_BORE_BAND
    assert spec.SOCKET_DIA == cone_tip_cluster.STEM_BORE_DIA_MM
    assert spec.MADE_TO_FIT_DIAMETERS == ("Sec0Dia", "Sec1Dia", "Sec2Dia")
    assert model_toleranced_dimensions(part) == {
        ("Sec1KeyseatProfile", "name"): "*deviations(band)",
        ("ShoulderFillets", "ShoulderR"): "*deviations(FILLET_R_BAND)",
    }


def test_the_keyseat_section_flags_the_land_note(monkeypatch):
    """Run the real section loop with its native steps recorded: A-A prints
    the keyseat's S and width, both flagged to the land note: the width after
    its value, the S above it (PR 2 r5 machinist review, clarity)."""
    suffixes = []
    callouts = []
    monkeypatch.setattr(drawing, "_cut_endpoints", lambda *_a: ((0.0, 0.0), (1.0, 0.0)))
    monkeypatch.setattr(drawing, "create_section_view", lambda *_a, label, **_k: label)
    monkeypatch.setattr(drawing, "_prepare_d_section", lambda *_a: None)
    monkeypatch.setattr(
        drawing, "_keyseat_side_x", lambda _a, _view, section, _sign: section.centre[0] + 0.0095
    )
    keeps = []
    monkeypatch.setattr(
        drawing,
        "curate_view_dimensions",
        lambda _a, _view, *, keep, **_k: keeps.append(dict(keep)) or list(keep),
    )
    inside = []
    monkeypatch.setattr(drawing, "_set_arrows_inside", lambda dimension, _label: inside.append(dimension))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, dimension: dimension)
    monkeypatch.setattr(drawing, "_delete_centre_mark", lambda *_a: None)
    monkeypatch.setattr(drawing, "_section_face", lambda *_a: (0.0, 0.0, 1.0, 1.0))
    monkeypatch.setattr(drawing, "_place_view_caption", lambda *_a, **_k: None)
    monkeypatch.setattr(
        drawing,
        "set_dimension_callouts",
        lambda _a, dimensions, texts, *, location: callouts.append(
            (tuple(dimensions), texts, location)
        ),
    )
    monkeypatch.setattr(
        drawing,
        "_set_dimension_suffixes",
        lambda _a, dimensions, texts: suffixes.append((tuple(dimensions), texts)),
    )
    references = []
    monkeypatch.setattr(
        drawing,
        "set_reference_dimension",
        lambda _a, dimension, *, label: references.append(dimension),
    )
    placed = drawing._add_d_sections(object(), object(), 1)
    assert len(placed) == len(drawing.D_SECTIONS) == 1
    assert placed[0].dimensions == ("Sec1KeyseatS", "Sec1KeyseatWidth")
    flag = f"NOTE {dt_cone_gear_shaft_spec.LAND_NOTE}"
    # The width prints (.0625) REF and closes its parenthesis before the flag
    # (machinist review r1, farm run 20261124T110807008Z).
    assert references == ["Sec1KeyseatWidth"]
    assert suffixes == [
        (
            ("Sec1KeyseatS", "Sec1KeyseatWidth"),
            {"Sec1KeyseatWidth": f") {flag}"},
        )
    ]
    assert callouts == [(("Sec1KeyseatS",), {"Sec1KeyseatS": flag}, "above")]
    # A-A (machinist review of PR 1 5a4e41cb5f, clarity): the width's line
    # rises at the keyseat's edge, the S text steps away from it and the S
    # arrows stand inside, so neither crosses the other.
    (a_section,) = drawing.D_SECTIONS
    assert keeps == [
        {
            "Sec1KeyseatS": (
                a_section.centre[0] - drawing.KEYSEAT_S_SHIFT,
                a_section.centre[1] + 0.017 + drawing.KEYSEAT_S_FLAG_LIFT,
            ),
            "Sec1KeyseatWidth": (
                a_section.centre[0] + 0.0095,
                a_section.centre[1] + drawing.KEYSEAT_WIDTH_RISE,
            ),
        }
    ]
    assert inside == ["Sec1KeyseatS"]


def test_every_tight_band_names_its_mate_and_fit_route():
    """Rule 4, form 2: every fit on this shaft is made here, last, and
    prints its acceptance once, here. The journal is a running fit turned to
    the MHA-DT-05 bore with its clearance; land 1 and its keyseat link the
    land note (every gear slides on, no shake), land 2 and the socket the
    bond note (the bond's clearance, rule 23), each naming its mates by
    drawing number.  Lengths carry no words but the stack flag."""
    spec = dt_cone_gear_shaft_spec
    journal = drawing.DIMENSION_CALLOUTS["Sec0Dia"]
    assert _config.parts("dt-cone-pivot-post")["number"] in journal
    assert "CLEARANCE" in journal
    # The journal's text hangs right of its line only off the faced end
    # (round 3: dragged onto the journal its box hung left onto section A's
    # letter); its widest row, in the proof's 2.17 mm a character, ends at
    # least 3 mm short of section A-A's box (0.3141).
    x, _y = drawing.SIDE_DIAMETERS["Sec0Dia"]
    assert x > drawing.BIG_END_X
    widest = max(map(len, drawing.DIMENSION_CALLOUTS["Sec0Dia"].split("\n")))
    assert x + widest * 0.00217 <= 0.3141 - 0.003
    # Land 2 flags the bond note; the stack's lengths flag the stack note, at
    # every callout it serves (round 4).
    assert set(drawing.DIMENSION_SUFFIXES) == {"Sec2Dia"} | set(drawing.STACK_LENGTHS)
    # A reference diameter closes its parenthesis before its flag.
    assert drawing.DIMENSION_SUFFIXES["Sec2Dia"] == f") SEE NOTE {spec.BOND_NOTE}"
    assert {drawing.DIMENSION_SUFFIXES[name] for name in drawing.STACK_LENGTHS} == {
        drawing.STACK_FLAG_SUFFIX
    }
    assert str(spec.STACK_NOTE) in drawing.STACK_FLAG_SUFFIX
    # Each numbered note with its indented continuation lines.
    notes: list[str] = []
    for line in spec.DRAWING_NOTES.splitlines():
        if line.startswith(" "):
            notes[-1] += " " + line.strip()
        else:
            notes.append(line)
    assert [note.split(".")[0] for note in notes] == [
        str(spec.LAND_NOTE), str(spec.BOND_NOTE), str(spec.STACK_NOTE)
    ]
    # Land 1's mates and its key (owner decision 2026-11-09, PR #1992) by
    # number, and its acceptance by feel.
    for mate in ("dt-cone-gear", "dt-crank-drive-gear", "dt-vn-cone-shaft-key"):
        assert _config.parts(mate)["number"] in notes[0]
    assert "SLIDES ON, NO SHAKE" in notes[0]
    # Land 2 and the socket are bonded fits: their mates by number, the fit
    # named with its compound's grade (drawing-guidelines.md rule 26) and
    # land 2's clearance inside the compound's gap (rule 23).
    for mate in ("dt-cone-gear", "dt-cone-tip-gear"):
        assert _config.parts(mate)["number"] in notes[1]
    assert f"BONDED FIT, {cone_tip_cluster.RETAINING_COMPOUND}" in notes[1]
    low, high = spec.T024_BOND_CLEARANCE_MM
    assert 0.0 <= low < high <= cone_tip_cluster.RETAINING_COMPOUND_MAX_GAP_MM
    assert f"CLEARANCE {spec.inch_text(low, 4)}-{spec.inch_text(high, 4)}" in notes[1]
    assert "MHA-DT-37 SPIGOT IS TURNED TO THE SOCKET" in notes[1]
    # The three-place lengths name the stack they set once (rule 4).
    for mate in ("dt-cone-gear", "dt-crank-drive-gear"):
        assert _config.parts(mate)["number"] in notes[2]
    # Rule 7: notes carry no method; the only dimension is the bond's
    # clearance range.
    assert re.findall(r"\d?\.\d{2,}", spec.DRAWING_NOTES) == [
        spec.inch_text(low, 4), spec.inch_text(high, 4)
    ]
    for word in ("TAILSTOCK", "MILL", "TURN "):
        assert word not in spec.DRAWING_NOTES
    # The socket's callout (rule 12): the process, its .XX depth, its flag.
    assert spec.SOCKET_CALLOUT.split("\n") == [
        f"REAM <HOLE-DEPTH> {spec.inch_text(spec.SOCKET_DEPTH, 2)}",
        f"SEE NOTE {spec.BOND_NOTE}",
    ]
    assert drawing.SOCKET_CALLOUTS == {"SocketDia": spec.SOCKET_CALLOUT}
    # Every suffix is one line; every below callout carries at most two lines
    # of words (rule 7), a parenthesized REF clearance row beside them.
    assert not any("\n" in text for text in drawing.DIMENSION_SUFFIXES.values())
    assert not any("\n" in text for text in spec.KEYSEAT_MATE_SUFFIXES.values())
    for text in spec.SEAT_MATE_CALLOUTS.values():
        assert len([row for row in text.split("\n") if not row.startswith("(")]) <= 2


def test_display_precision_is_owned_by_the_part() -> None:
    """drawing-simplicity-policy.md `How the repository implements the guidelines`: the .SLDPRT carries the places, the sheet reads them back."""
    assert "draw_dt_cone_gear_shaft.py" in PRECISION_MIGRATED_DRAWINGS
    # Every diameter carries its named band, so its places are only spelling.
    # The stations carry no band, so their places ARE the grade they are held
    # to: three for the land step booked in the setback and for the tip booked
    # in the recess proof; two for the journal length, which the bearing-span
    # proof reads.
    by_name = dt_cone_gear_shaft_spec.DRAWING_PRECISION_BY_NAME
    assert by_name == {
        "Sec0Dia": 4,
        "Sec1Dia": 4,
        "Sec2Dia": 4,
        "Sec0End": 2,
        "Sec1End": 3,
        "Sec2End": 3,
        "Sec1KeyseatWidth": cone_land_key.KEYSEAT_PLACES,
        "Sec1KeyseatS": cone_land_key.KEYSEAT_PLACES,
        "SocketDia": cone_tip_cluster.STEM_PLACES,
        # The keyseat end's centre from the collar face: the title block's .XX.
        "Sec1KeyseatEndSet": 2,
        "ShoulderR": 3,
        # #914: the collar web is the 64T's station toward MHA-DT-05, so it
        # prints .XXX (crank_boss_rim).  The collar diameter is the bar's as
        # supplied, a 5/8 fraction reference.
        "CollarDia": 3,
        "CollarWidth": 3,
    }
    # drawing-guidelines.md rule 17 (walls and webs): the web holds the 2.0 target at the low limit it prints.
    web = dt_cone_gear_shaft_spec.COLLAR_THICKNESS
    assert web - _config.title_block("linear_3pl")["value_in"] * 25.4 >= 2.0


def _band(places: int) -> float:
    """The title-block band a length prints at ``places`` (decimal inch)."""
    return printed_band_mm(places, unit="in")


def _setback_margin(j: int, step_band: float, collar_band: float | None = None) -> float:
    """What the setback leaves when the step behind gear j's north face and
    its root reach north, the collar is short, the stack is short onto the
    collar and the fleet spare is held."""
    spec = dt_cone_gear_shaft_spec
    return spec.SEAT_STEP_SETBACK - (
        step_band
        + spec.FILLET_RADIUS
        + (_band(3) if collar_band is None else collar_band)  # the collar web prints .XXX
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


def test_the_step_sits_one_setback_inside_t030() -> None:
    """The step T030|T024 sits one setback south of T030's north face, inside
    T030, and at print-worst the step and its root stay south of T024."""
    spec = dt_cone_gear_shaft_spec
    station = spec.SECTION_ENDS[1] - spec.FRONT_STUB
    south, north = spec.gear_faces(15)
    assert station == pytest.approx(north - spec.SEAT_STEP_SETBACK)
    assert south < station - _band(3) and station + _band(3) + spec.FILLET_RADIUS < north
    margin = _setback_margin(
        15,
        spec.printed_length_deviations("Sec1End")[1],
        -spec.printed_length_deviations("CollarWidth")[0],
    )
    assert margin >= 0.0
    assert spec.SEAT_STEP_BUDGET["margin"] == pytest.approx(margin)


def test_a_two_place_step_would_reach_t024() -> None:
    """Why Sec1End prints three places: the .XX band eats the setback."""
    assert _setback_margin(15, _band(2)) < 0.0


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
            + _cone_axis_constants.GEAR_AXIS_SHIFT
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
    # The section prints SECTION_DIMENSION_NAMES; the keyseat width's text is
    # placed at build time on the keyseat's side, the rest at D_SECTION_KEEP.
    # The tip end view prints the socket.
    sections = set().union(*drawing.SECTION_DIMENSION_NAMES.values())
    assert set(drawing.D_SECTION_KEEP) <= sections
    assert (
        set(drawing.SIDE_KEEP)
        | set(drawing.SIDE_DIAMETERS)
        | sections
        | set(drawing.TIP_END_VIEW_KEEP)
        == marked
    )
    # Nothing is imported twice, and the donor hands over exactly the four
    # diameters it was placed for (three lands and the collar, #914).
    assert set(drawing.DONOR_KEEP) == set(drawing.SIDE_DIAMETERS)
    assert len(drawing.DONOR_KEEP) == 4
    keeps = (
        set(drawing.SIDE_KEEP),
        set(drawing.DONOR_KEEP),
        set(drawing.D_SECTION_KEEP),
        set(drawing.TIP_END_VIEW_KEEP),
    )
    assert sum(map(len, keeps)) == len(set().union(*keeps))
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
_MHA014_COLLAR_TEXT = (0.2088, 0.1676, 0.2565, 0.1844)


def _scaled_collar_text() -> tuple[float, float, float, float]:
    """The mha014-1 block grown to today's callout: its per-character width
    (widest line "5/8 BAR AS SUPPLIED") times today's widest line, and its
    per-line height times today's line count, from the same corner."""
    x0, y0, x1, y1 = _MHA014_COLLAR_TEXT
    lines = drawing.COLLAR_CALLOUT_LINES
    per_char = (x1 - x0) / len("5/8 BAR AS SUPPLIED")
    per_line = (y1 - y0) / 3
    return (x0, y0, x0 + per_char * max(map(len, lines)), y0 + per_line * len(lines))


_COLLAR_TEXT = _scaled_collar_text()
_PIVOT_FINISH_BOX = (0.2320, 0.1800, 0.2790, 0.1980)
_SEC1_TEXT = (0.1400, 0.1685, 0.1723, 0.1765)


def _pivot_finish_ink() -> tuple[tuple[float, float, float, float], list]:
    """The pivot finish as the build places it: the measured symbol box and
    its leader from PIVOT_FINISH_XY down onto the journal land's top flank."""
    spec = dt_cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    top = (
        big_end - drawing.PIVOT_FINISH_ATTACH_INSET,
        drawing.SIDE_CENTER[1] + spec.SECTION_DIAS[0] / 2000.0,
    )
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
    aside = [((text[2] + 0.010, 0.2500), (text[2] + 0.020, 0.2400))]
    assert drawing._collar_callout_dy(text, finish, aside) == pytest.approx(dy)


def test_the_collar_callout_read_guard_takes_the_whole_block() -> None:
    """The measured block must be all its lines, not the value line alone:
    the render's width per character of its widest line (mha014-1, widest
    "5/8 BAR AS SUPPLIED") at today's widest line passes the guard, a
    "(Ø5/8 in)"-only box does not."""
    assert drawing.COLLAR_CALLOUT_LINES == (
        "(Ø5/8 in)",
        *dt_cone_gear_shaft_spec.COLLAR_STOCK_CALLOUT.split("\n"),
    )
    x0, _y0, x1, _y1 = _MHA014_COLLAR_TEXT
    per_char = (x1 - x0) / len("5/8 BAR AS SUPPLIED")
    widest = max(len(line) for line in drawing.COLLAR_CALLOUT_LINES)
    assert per_char * widest >= drawing.COLLAR_CALLOUT_MIN_READ
    value_line_only = len("(Ø5/8 in)") * drawing.LENGTH_CHAR_WIDTH
    assert value_line_only < drawing.COLLAR_CALLOUT_MIN_READ


def test_lengths_are_baseline_from_each_chucking_face() -> None:
    """Rule 11 (round 6): the gear lands and the tip run from the collar's
    tip-side face, each on its own tier, the shortest nearest the part and the
    tip station (#917 R5 (a)) outermost; the web and the journal run from the
    thrust face on the first tier, and the front-to-tip overall, a REFERENCE,
    sits lowest, clear of the title block."""
    spec = dt_cone_gear_shaft_spec
    from_seat = {
        "Sec1End": spec.SECTION_KNOBS[1],
        "Sec2End": spec.SECTION_KNOBS[2],
    }
    tiers = [
        drawing.SIDE_KEEP[name][1]
        for name in ("CollarWidth", *sorted(from_seat, key=from_seat.get))
    ]
    assert tiers == sorted(tiers, reverse=True)
    assert len(set(tiers)) == len(tiers)
    shaft_bottom = drawing.SIDE_CENTER[1] - spec.COLLAR_DIA / 2000.0
    assert tiers[0] < shaft_bottom - 0.005
    journal = drawing.SIDE_KEEP["Sec0End"]
    assert journal[1] == tiers[0]
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    thrust_x = big_end - spec.COLLAR_START_STATION / 1000.0
    seat_x = big_end - spec.DATUM_STATION / 1000.0
    # the journal's text is right of the thrust face, the collar web's left
    # of the tip-side face (the web's span is too narrow for it)
    assert journal[0] > thrust_x + 0.010
    assert drawing.SIDE_KEEP["CollarWidth"][0] < seat_x
    overall = drawing.OVERALL_REFERENCE_TEXT_XY[1]
    assert overall < tiers[-1] and overall > 0.066 + 0.008
    tip_x = big_end - spec.SHAFT_LENGTH / 1000.0
    assert tip_x < drawing.OVERALL_REFERENCE_TEXT_XY[0] < big_end
    # each station's text stands inside its own span
    for name, span in from_seat.items():
        assert seat_x - span / 1000.0 < drawing.SIDE_KEEP[name][0] < seat_x, name


def test_every_length_tier_is_one_line() -> None:
    """final877: a callout below a length hung between two tiers and read as
    either's.  No length below the shaft carries a callout line."""
    assert not set(drawing.DIMENSION_CALLOUTS) & set(drawing.SIDE_KEEP) - {"ShoulderR"}


def _length_texts_crossed(side_keep, overall_xy):
    """Every (text, line x) pair where an extension line crossing a length
    text's tier passes within STATION_TEXT_CLEARANCE of that text's box.

    Each length hangs its two extension lines from the shaft down to its own
    tier, so a line crosses every tier ABOVE its own.  A text is centred on
    its x; its box is the value's character count times LENGTH_CHAR_WIDTH
    plus its function suffix's times CALLOUT_CHAR_WIDTH.
    """
    spec = dt_cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    thrust_x = big_end - spec.COLLAR_START_STATION / 1000.0
    seat_x = big_end - spec.DATUM_STATION / 1000.0
    tip_x = big_end - spec.SHAFT_LENGTH / 1000.0
    from_seat = {
        "Sec1End": spec.SECTION_KNOBS[1],
        "Sec2End": spec.SECTION_KNOBS[2],
    }
    places = spec.DRAWING_PRECISION_BY_NAME
    texts = {
        name: (f"{value:.{places[name]}f}", side_keep[name])
        for name, value in from_seat.items()
    }
    texts["CollarWidth"] = (
        f"{spec.COLLAR_THICKNESS:.{places['CollarWidth']}f}",
        side_keep["CollarWidth"],
    )
    texts["Sec0End"] = (
        f"{spec.JOURNAL_END:.{places['Sec0End']}f}",
        side_keep["Sec0End"],
    )
    texts["overall"] = (f"({spec.SHAFT_LENGTH:.1f})", overall_xy)
    # (line x, the lowest tier it reaches): each tip-side station's far line,
    # the tip-side face down to the lowest of its stations' tiers (the web's
    # far line too), and the thrust face down to the web's and journal's tier.
    lines = [(seat_x - value / 1000.0, side_keep[name][1]) for name, value in from_seat.items()]
    lines.append((seat_x, min(side_keep[name][1] for name in (*from_seat, "CollarWidth"))))
    lines.append((thrust_x, min(side_keep[name][1] for name in ("CollarWidth", "Sec0End"))))
    lines += [(big_end, overall_xy[1]), (tip_x, overall_xy[1])]
    crossed = []
    for name, (text, (x, y)) in texts.items():
        suffix = drawing.DIMENSION_SUFFIXES.get(name, "")
        width = (
            len(text) * drawing.LENGTH_CHAR_WIDTH
            + len(suffix) * drawing.CALLOUT_CHAR_WIDTH
        )
        half = width / 2.0
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


def test_the_keyseat_section_cuts_land_one_clear_of_its_neighbours() -> None:
    """Section A-A crosses land 1 at least 2 mm from its ends and past its
    surface, 2 mm off its diameter line; enlarged to 15 mm or more, with its
    S over it and its caption under it, it stands right of the side view,
    inside the frame and off the title block."""
    spec = dt_cone_gear_shaft_spec
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    margin = 0.0127
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    (section,) = drawing.D_SECTIONS
    assert section.land == spec.KEYED_LAND
    enlarge = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    end = spec.SECTION_ENDS[section.land]
    radius = spec.SECTION_DIAS[section.land] / 2.0
    assert (section.station_mm - spec.COLLAR_END_STATION) * enlarge >= 2.0
    assert (end - section.station_mm) * enlarge >= 2.0
    assert section.reach * 1000.0 / enlarge > radius
    cut_x = big_end - section.station_mm / 1000.0
    assert abs(cut_x - drawing.SIDE_DIAMETERS["Sec1Dia"][0]) >= 0.002
    across = spec.SECTION_DIAS[section.land] * section.scale[0] / section.scale[1]
    assert across >= 15.0
    half = across / 2000.0
    x, y = section.centre
    text_x, text_y = drawing.D_SECTION_KEEP["Sec1KeyseatS"]
    assert text_x == x and text_y > y + half
    caption_w, caption_h = drawing.SECTION_CAPTION_SIZE
    cell = (
        x - caption_w / 2.0,
        y - half - drawing.SECTION_CAPTION_GAP - caption_h,
        x + caption_w / 2.0,
        text_y + 0.005,
    )
    assert cell[0] > big_end + 0.02
    assert margin <= cell[0] and cell[2] <= template.width_m - margin - CLEAR_GAP_M
    assert margin <= cell[1] and cell[3] <= template.height_m - margin
    assert cell[1] > template.title_block_top_m
    # The keyseat width's text rides above the section (PR #2331's farm fix,
    # 5994f29c83): its line stands at the text's left edge on the keyseat's
    # side (either side of A), the text 46.1 mm wide, 4.5 mm under and 3.5 mm
    # over its position (PR #2331 farm proofs: 7f1dedc measured 0.3466..0.3927;
    # 5994f29 r2 0.1905..0.1985 at 0.195).  Either way it stays inside the
    # frame, above A's cell, and far right of the tip end view's socket text;
    # its row is bounded by A's measured S text top and the pictorial's
    # measured outline bottom (5994f29 r2), each kept CLEAR_GAP_M plus 1 mm off.
    s_text_top, iso_bottom = 0.1855, 0.2001
    rise_y = y + drawing.KEYSEAT_WIDTH_RISE
    assert rise_y - 0.0045 >= s_text_top + CLEAR_GAP_M + 0.001
    assert rise_y + 0.0035 <= iso_bottom - CLEAR_GAP_M - 0.001
    socket_x, _socket_y = drawing.TIP_END_VIEW_KEEP["SocketDia"]
    for side in (-1.0, 1.0):
        left = x + side * half
        rider = (left, rise_y - 0.0045, left + 0.0461, rise_y + 0.0035)
        assert rider[0] > big_end + 0.02
        assert rider[2] <= template.width_m - margin - CLEAR_GAP_M
        assert rider[3] <= template.height_m - margin
        assert rider[1] > cell[3], (rider, cell)
        assert rider[0] > socket_x + drawing.DIAMETER_TEXT_WIDTH + 0.1
    # The width's line rises at the keyseat's edge.  The S text (PR 1
    # 5a4e41cb5f r3 layout audit: 0.3227..0.3501 about its 0.3371 position,
    # 14.4 mm left and 13.0 mm right) steps away from it, ending CLEAR_GAP_M
    # plus 1 mm short of that line, its left end clear of the Ø.4825 block
    # (<= 0.3111, test_every_tight_band_names_its_mate_and_fit_route); with
    # its arrows inside, its dimension line ends at the floor's extension line,
    # inside the land's edge.
    keyseat_x = x + half
    s_x = x - drawing.KEYSEAT_S_SHIFT
    assert s_x + 0.0130 <= keyseat_x - CLEAR_GAP_M - 0.001
    assert s_x - 0.0144 >= 0.3111 + CLEAR_GAP_M
    # With its NOTE flag above, S's block is centred on its position, the
    # value pushed down by the flag's row: PR 1 r9 (9b8efb7876) and PR 2 r6
    # measured 0.3170..0.3424 x 0.1747..0.1872 about (0.3301, 0.182), its
    # foot 0.2 mm off the face (the proof refused it).  Lifted, the block
    # clears the face, the Ø.4825 text (to 0.3144) and the width's line by
    # CLEAR_GAP_M and stays under the pictorial's outline (0.2001).
    s_y = y + 0.017 + drawing.KEYSEAT_S_FLAG_LIFT
    block = (s_x - 0.0131, s_y - 0.0073, s_x + 0.0123, s_y + 0.0052)
    assert block[1] - (y + half) >= CLEAR_GAP_M + 0.001
    assert block[0] >= 0.3144 + CLEAR_GAP_M
    assert block[2] <= keyseat_x - CLEAR_GAP_M
    assert block[3] <= iso_bottom - CLEAR_GAP_M
    floor_x = x + cone_land_key.KEYSEAT_FLOOR_OFFSET_MM / 1000.0 * section.scale[0] / section.scale[1]
    assert floor_x < keyseat_x
    assert drawing.ARROWS_INSIDE == 0


# How far above a side-view cutting line's lower end its letter's top stands:
# 4.8 mm on most seats, 6.3 mm on swmaker00000a (the 19e33c6c2 build).
_SECTION_LETTER_RISE_M = 0.0063


def test_each_side_view_cutting_line_letter_clears_its_land() -> None:
    """A side-view line's lower letter rises from the line's end back toward
    the land it cuts.  At a 12.5 mm reach A's letter stood 1.4 mm under land
    1 on one seat and the section proof refused it (19e33c6c2); the worst
    measured letter must clear the land by the proof's 2 mm and 1.5 mm more."""
    scale = drawing.SIDE_SCALE
    axis_y = drawing.SIDE_CENTER[1]
    for section in drawing.D_SECTIONS:
        half = dt_cone_gear_shaft_spec.SECTION_DIAS[section.land] / 2000.0
        land_bottom = axis_y - half * scale[0] / scale[1]
        letter_top = axis_y - section.reach + _SECTION_LETTER_RISE_M
        gap = land_bottom - letter_top
        assert gap >= CLEAR_GAP_M + 0.0015, (section.label, gap)


def test_section_a_cutting_line_clears_the_root_radius_and_the_step_length() -> None:
    """PR 2 r2 (967cedb) measured, with A cut 25 mm north of land 1's step
    (line at sheet x 0.1150): the upper arrow 0.1133..0.1287 x 0.1633..0.1667
    (the proof's 1.7 mm pad included), the letters 0.1285..0.1349, the lower
    one 0.1334..0.1397 high, and the R.004 text 0.0862..0.1122 x
    0.1612..0.1647 about its (0.0996, 0.1640) position; the arrow crowded the
    text by 1.1 mm.  r3 (2aeedb78) drew the radius's shoulder wider, 0.0846..
    0.1130 at y 0.1612, across the Ø.2500 line at 0.0849 (layout audit
    shoulder-crosses-line).  Every box translated with its anchor, the arrow
    keeps CLEAR_GAP_M plus 1 mm off the radius text, the shoulder starts
    CLEAR_GAP_M right of land 2's diameter line, and the lower letter stays
    left of Sec1End's text (its value and flag, centred)."""
    spec = dt_cone_gear_shaft_spec
    big_end = drawing.SIDE_CENTER[0] + spec.SHAFT_LENGTH / 2000.0
    (section,) = drawing.D_SECTIONS
    line_x = big_end - section.station_mm / 1000.0
    arrow = (line_x - 0.0017, line_x + 0.0137)
    letter = (line_x + 0.0135, line_x + 0.0199)
    r_x, r_y = drawing.SIDE_KEEP["ShoulderR"]
    radius_text = (r_x - 0.0150, r_y - 0.0028, r_x + 0.0134, r_y + 0.0007)
    assert radius_text[0] - drawing.SIDE_DIAMETERS["Sec2Dia"][0] >= CLEAR_GAP_M
    upper_arrow_y = (
        drawing.SIDE_CENTER[1] + section.reach - 0.0017,
        drawing.SIDE_CENTER[1] + section.reach + 0.0017,
    )
    assert radius_text[1] < upper_arrow_y[1] and upper_arrow_y[0] < radius_text[3]
    assert arrow[0] - radius_text[2] >= CLEAR_GAP_M + 0.001
    # Sec1End's text keeps at least r2's offset from the lower letter, a pair
    # the r2 proof passed (text at 0.1560, A cut 25 mm from the step).
    s_x, _s_y = drawing.SIDE_KEEP["Sec1End"]
    r2_letter_right = big_end - (spec.SECTION_ENDS[1] - 25.0) / 1000.0 + 0.0199
    assert s_x - letter[1] >= 0.1560 - r2_letter_right - 1e-6
    # The cut stays on land 1, clear of its diameter line.
    assert abs(line_x - drawing.SIDE_DIAMETERS["Sec1Dia"][0]) >= 0.002


def test_the_tip_end_view_carries_the_socket_callout_in_the_frame() -> None:
    """Rules 9 and 12: the socket is a standard blind ream, so its callout on
    the end view facing it defines it.  The view is projected left of the
    side view on its axis at the sheet scale (third angle, no label), clear
    of the tip; the callout's text stands inside the frame, above the view
    and left of land 2's diameter line, off the note block."""
    spec = dt_cone_gear_shaft_spec
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    margin = 0.0127
    x, y = drawing.TIP_END_VIEW_CENTER
    assert y == drawing.SIDE_CENTER[1]
    half = spec.COLLAR_DIA / 2000.0
    assert x - half >= margin
    assert x + half < drawing.TIP_END_X - drawing.AXIS_OVERRUN - CLEAR_GAP_M
    assert set(drawing.TIP_END_VIEW_KEEP) == {"SocketDia"}
    text_x, text_y = drawing.TIP_END_VIEW_KEEP["SocketDia"]
    # Its box as measured on the PR 2 farm proof (6fda5a4): 16.3 mm left and
    # 26.8 mm right of its position, 10.1 mm under and 9.1 mm over.
    box = (text_x - 0.0163, text_y - 0.0101, text_x + 0.0268, text_y + 0.0091)
    assert box[0] >= margin + CLEAR_GAP_M and box[3] <= template.height_m - margin
    assert box[1] > y + half + CLEAR_GAP_M
    assert box[2] + CLEAR_GAP_M < drawing.SIDE_DIAMETERS["Sec2Dia"][0]
    assert box[1] > drawing.NOTES_XY[1]


def test_stacked_tip_diameters_never_run_a_line_through_a_text() -> None:
    """Each diameter's line clears every other diameter's text.

    A dragged diameter's text hangs to the RIGHT of its dimension line, so the
    text at (x, y) spans x..x+width, its mate suffix included; any other line
    inside that span rises from the shaft and must stop below the text.  The
    first render stepped the texts the other way and three leaders crossed
    (codex, 18395f30).
    """
    text_height = 0.009  # nominal over a stacked two-line band
    items = list(drawing.SIDE_DIAMETERS.items())
    for name_a, (x_a, y_a) in items:
        suffix = drawing.DIMENSION_SUFFIXES.get(name_a, "")
        width = drawing.DIAMETER_TEXT_WIDTH + len(suffix) * drawing.CALLOUT_CHAR_WIDTH
        for name_b, (x_b, y_b) in items:
            if name_a == name_b:
                continue
            if x_a < x_b < x_a + width:
                assert y_b < y_a - text_height, (name_a, name_b)


def test_sections_are_a_monotonic_stepped_shaft() -> None:
    """The v2 journal, the keyed land 1 and the round land 2 step down
    monotonically (owner decision C1 keyed, 2026-11-09, PR #1992)."""
    spec = dt_cone_gear_shaft_spec
    sections = spec.SECTIONS
    assert len(sections) == 3
    dias = spec.SECTION_DIAS
    ends = spec.SECTION_ENDS
    assert all(a > b for a, b in zip(dias, dias[1:]))
    assert all(a < b for a, b in zip(ends, ends[1:]))
    # The integral bearing journal fits the post's .4385 bore at .0010
    # diametral clearance (owner ruling 2026-11-23, tool audit Q11: journal
    # .4375 0/-.0008); the gear lands keep their diameters.
    assert spec.JOURNAL_BORE_DIA == pytest.approx(11.1379)
    assert spec.JOURNAL_CLEARANCE == pytest.approx(0.0254)
    assert spec.JOURNAL_DIA == pytest.approx(11.1125)
    assert spec.JOURNAL_DIAMETRAL_CLEARANCE_MM == pytest.approx((0.0254, 0.05842))
    assert spec.JOURNAL_END == pytest.approx(43.18)
    assert dias == pytest.approx((11.1125, 9.525, 6.35))
    assert spec.FRONT_STUB == pytest.approx(
        -cone_line.POST_STATION
        + dt_cone_pivot_post_spec.CONE_BOSS_LENGTH / 2.0
        + spec.JOURNAL_PROUD
    )
    # Convert the local collar face back to the shared cone station: it must
    # bear on the post's north boss face, independent of the incline/grid.
    assert spec.COLLAR_START_STATION - spec.FRONT_STUB == pytest.approx(
        cone_line.POST_STATION + dt_cone_pivot_post_spec.CONE_BOSS_LENGTH / 2.0
    )
    assert spec.T006_NORTH_FACE_STATION == pytest.approx(cone_line.T006_NORTH_FACE)
    # Land 1 ends one setback behind T030's north face; land 2 ends the tip
    # cluster's recess inside T024's bore, T024 one feeler north of layout.
    assert ends[1] == pytest.approx(spec.FRONT_STUB + spec.seat_step_station(15))
    assert spec.T024_NORTH_FACE_STATION == pytest.approx(
        spec.gear_faces(16)[1] + cone_stack_end_play.STACK_FEELER
    )
    assert spec.TIP_END_STATION == pytest.approx(
        spec.T024_NORTH_FACE_STATION - cone_tip_cluster.TIP_END_RECESS_MM
    )
    assert spec.SHAFT_LENGTH == ends[-1] == spec.FRONT_STUB + spec.TIP_END_STATION
    assert spec.SOCKET_FLOOR_STATION == pytest.approx(
        spec.TIP_END_STATION - cone_tip_cluster.SOCKET_DEPTH_MM
    )
    # Native station knobs and printed baselines share the collar's tip-side
    # face (rule 11, round 6).
    assert spec.SECTION_KNOBS[1:] == pytest.approx(
        tuple(end - spec.COLLAR_END_STATION for end in ends[1:])
    )


def test_the_swing_platform_pivot_stands_a_fixed_reach_north_of_t006() -> None:
    """The pivot's reach past T006's north face is fixed (23.0 plus the
    literal 8.0 extension, C1 keyed, PR #1992); its station follows T006,
    nineteen exact-tracking seat pitches from T120 (#1038: the pitch is a
    config input, so the station is derived, never a pinned float)."""
    import cone_pitch
    import cone_stations

    assert cone_stations.TIP_END_EXTENSION_MM == 8.0
    # The law: sin i = radius step / station pitch, seat pitch = pitch cos i.
    assert cone_pitch.RADIUS_STEP == 3.0 * 25.4 / 48.0
    seat_pitch = math.sqrt(cone_pitch.Z_PITCH**2 - cone_pitch.RADIUS_STEP**2)
    assert cone_pitch.SEAT_PITCH == pytest.approx(seat_pitch, abs=1e-12)
    t006_north = (
        cone_stations.SHAFT_T120_STATION
        + _cone_axis_constants.GEAR_AXIS_SHIFT
        + 19 * seat_pitch
        + cone_stations.CONE_FACE_STATION_REFERENCE / 2.0
    )
    assert cone_stations.T006_NORTH_FACE == pytest.approx(t006_north, abs=1e-9)
    assert cone_stations.PIVOT_STATION - cone_stations.T006_NORTH_FACE == (
        pytest.approx(23.0 + cone_stations.TIP_END_EXTENSION_MM, abs=1e-9)
    )
    assert cone_line.PIVOT_STATION == cone_stations.PIVOT_STATION


def test_the_shaft_end_stays_inside_t024_at_every_limit() -> None:
    """T024's north face moves with T030's (the stack on the collar), the
    feeler set and its own face width; the end moves with Sec2End's printed
    .XXX.  At every limit the end stays inside T024's bore, so T018 butts
    T024, and T024 keeps a bonded length on land 2."""
    spec = dt_cone_gear_shaft_spec
    north = dt_cone_gear_stack.face_band(15, "north")
    band = cone_stack_end_play.STACK_FEELER_BAND
    width = dt_cone_gear_spec.FACE_WIDTH_BAND
    assert spec.T024_NORTH_FACE_DEVIATION_MM == pytest.approx(
        (north[1] - band + width[1], north[0] + band + width[0])
    )
    end_lower, end_upper = spec.printed_length_deviations("Sec2End")
    # The title block's .XXX either side of the PRINTED value: the model
    # (a stack closure, off the inch grid) stands within half a thousandth
    # of it, so the two deviations differ by at most a thousandth.
    assert end_upper - end_lower == pytest.approx(2.0 * _band(3))
    assert abs(end_upper + end_lower) <= 0.001 * 25.4 + 1e-9
    recess = cone_tip_cluster.TIP_END_RECESS_MM
    low, high = spec.TIP_END_RECESS_LIMITS_MM
    assert low == pytest.approx(recess + spec.T024_NORTH_FACE_DEVIATION_MM[0] - end_upper)
    assert high == pytest.approx(recess + spec.T024_NORTH_FACE_DEVIATION_MM[1] - end_lower)
    assert 0.0 < low < high
    assert spec.T024_BOND_LENGTH_MIN_MM == pytest.approx(
        spec.CONE_GEAR_FACE_WIDTH + width[1] - high
    )
    assert spec.T024_BOND_LENGTH_MIN_MM > 0.5 * spec.CONE_GEAR_FACE_WIDTH
    # Positive control: at .XX the end could stand proud of T024.
    assert recess + spec.T024_NORTH_FACE_DEVIATION_MM[0] - _band(2) < 0.0
    # So the .XXX is functional, and the sheet says so: Sec2End carries the
    # stack note's flag (PR 2 r4 review: an unflagged three-place length).
    assert "Sec2End" in drawing.STACK_LENGTHS
    assert drawing.DIMENSION_SUFFIXES["Sec2End"] == drawing.STACK_FLAG_SUFFIX


def test_the_spigot_keeps_floor_air_and_engagement_in_the_socket() -> None:
    """Over the recess range, with the spigot and socket depth at their .XX
    limits and T012/T018 at their face-width limits, T006's spigot never
    bottoms and keeps 1.5 D in the socket."""
    spec = dt_cone_gear_shaft_spec
    tip = cone_tip_cluster
    width = (
        spec.CONE_GEAR_FACE_WIDTH + dt_cone_gear_spec.FACE_WIDTH_BAND[1],
        spec.CONE_GEAR_FACE_WIDTH + dt_cone_gear_spec.FACE_WIDTH_BAND[0],
    )
    spigot_band = _band(2) + 0.01  # .XX plus the inch rounding of .71
    depth_lower, _depth_upper = spec.printed_length_deviations("SocketDepth")
    low, high = spec.TIP_END_RECESS_LIMITS_MM
    air = low + 2.0 * width[0] - tip.SPIGOT_LENGTH_MM - spigot_band + spec.SOCKET_DEPTH + depth_lower
    engagement = tip.SPIGOT_LENGTH_MM - spigot_band - 2.0 * width[1] - high
    assert spec.SPIGOT_FLOOR_AIR_MIN_MM >= air - 1e-9
    assert spec.SPIGOT_ENGAGEMENT_MIN_MM >= engagement - 1e-9
    assert spec.SPIGOT_FLOOR_AIR_MIN_MM > 0.0
    assert spec.SPIGOT_ENGAGEMENT_MIN_MM >= tip.SPIGOT_SOCKET_ENGAGEMENT_MIN_MM
    assert tip.SPIGOT_SOCKET_ENGAGEMENT_MIN_MM == pytest.approx(1.5 * tip.STEM_DIA_MM)


def test_the_socket_wall_holds_the_rule_17_target() -> None:
    """Land 2 at its least printed diameter round the socket at its largest
    reamed size keeps rule 17's .080 target."""
    spec = dt_cone_gear_shaft_spec
    land_min = cone_shaft_land_bands.land_finished_dia_limits_mm(spec.SECTION_DIAS[2], 2)[0]
    socket_max = spec.SOCKET_DIA + max(spec.SOCKET_DIA_BAND)
    assert spec.SOCKET_WALL_MIN_MM == pytest.approx((land_min - socket_max) / 2.0)
    assert spec.SOCKET_WALL_MIN_MM >= 2.032


def test_land_one_keyseat_runs_off_over_land_two_with_the_key_bands() -> None:
    """The keyseat floor and the 64T/T030 keyway top stand outside land 2's
    round at every print limit, so the keyseat runs out into air and the
    keyed bores pass land 2; its two dimensions carry cone_land_key's bands
    and places; the removed area is the exact circular strip."""
    spec = dt_cone_gear_shaft_spec
    key = cone_land_key
    assert spec.SECTION_DIAS[spec.KEYED_LAND] == key.LAND_DIA_MM
    land2_max = (spec.SECTION_DIAS[2] + spec.SECTION_DIA_BANDS[2][0]) / 2.0
    land1_max = spec.SECTION_DIAS[1] + spec.SECTION_DIA_BANDS[1][0]
    floor_min = key.limits(key.KEYSEAT_S_MM, key.KEYSEAT_S_BAND)[0] - land1_max / 2.0
    assert floor_min > land2_max
    bore_max = spec.SECTION_DIAS[1] + gear_seat_fit.seat_bore_band(spec.SECTION_DIA_BANDS[1])[0]
    keyway_min = key.limits(key.KEYWAY_T_MM, key.KEYWAY_T_BAND)[0] - bore_max / 2.0
    assert keyway_min > land2_max
    assert spec.DRAWING_PRECISION["Sec1KeyseatProfile"] == {
        "Sec1KeyseatWidth": key.KEYSEAT_PLACES,
        "Sec1KeyseatS": key.KEYSEAT_PLACES,
    }
    # Exact strip area against a fine numerical integration.
    radius = key.LAND_DIA_MM / 2.0
    half = key.KEYSEAT_WIDTH_MM / 2.0
    steps = 20000
    dy = 2.0 * half / steps
    numeric = sum(
        (math.sqrt(radius**2 - (-half + (k + 0.5) * dy) ** 2) - key.KEYSEAT_FLOOR_OFFSET_MM) * dy
        for k in range(steps)
    )
    assert part.keyseat_area() == pytest.approx(numeric, rel=1e-6)


def test_the_keyseat_end_is_the_end_mill_radius_and_clears_the_key() -> None:
    """The end's radius is half the keyseat, its centre KEY_END_SET (.05) from
    the collar face, so in the model the radius stands clear of that face;
    the key's square south end sits on the radius's centre line, where the
    keyseat is full width, so the key's corners clear the end at every
    limit; and the end's volume is the exact half-disc integral."""
    key = cone_land_key
    spec = dt_cone_gear_shaft_spec
    assert key.KEY_END_SET_MM == pytest.approx(0.05 * 25.4)
    assert key.KEY_END_SET_MM > key.KEYSEAT_WIDTH_MM / 2.0
    assert part.KEYSEAT_END_STATION == pytest.approx(
        spec.COLLAR_END_STATION + key.KEY_END_SET_MM
    )
    # The key's widest half-width fits the end's least radius on its south line.
    key_half_max = key.limits(key.KEY_SIZE_MM, key.KEY_STOCK_BAND)[1] / 2.0
    end_radius_min = key.limits(key.KEYSEAT_WIDTH_MM, key.KEYSEAT_WIDTH_BAND)[0] / 2.0
    assert key_half_max <= end_radius_min
    # Volume: converged, and between the half disc times the floor-to-round
    # height at the keyseat's edge and at its centre.
    assert part.keyseat_end_volume() == pytest.approx(
        part.keyseat_end_volume(steps=40000), rel=1e-5
    )
    radius = spec.SECTION_DIAS[1] / 2.0
    half = key.KEYSEAT_WIDTH_MM / 2.0
    floor = key.KEYSEAT_FLOOR_OFFSET_MM
    assert (
        math.pi / 2.0 * half**2 * (math.sqrt(radius**2 - half**2) - floor)
        < part.keyseat_end_volume()
        < math.pi / 2.0 * half**2 * (radius - floor)
    )


def test_the_keyseat_end_is_located_from_the_collar_face_on_the_sheet() -> None:
    """Machinist review of 06460fb: the sheet gave no keyseat length or end
    location, so no mill stop.  The end radius's centre prints from the
    collar face at the title block's .XX in the side view, and at its printed
    limits, with the key's .XX length, the key's north end stays short of
    T024 (the key comes to rest against the end, so the band moves the key,
    never into the radius)."""
    spec = dt_cone_gear_shaft_spec
    key = cone_land_key
    assert spec.DRAWING_DIMENSIONS["Sec1KeyseatEndProfile"] == {"Sec1KeyseatEndSet"}
    assert spec.DRAWING_PRECISION_BY_NAME["Sec1KeyseatEndSet"] == 2
    assert "Sec1KeyseatEndSet" in drawing.SIDE_KEEP
    assert f"{key.KEY_END_SET_MM / 25.4:.2f}" == "0.05"
    # Codjiflo #2331 4521933063: at the printed low limit the widest end mill
    # keeps the collar's tip-side face (the 64T's seat) uncut, with margin.
    lower = spec.printed_length_deviations("Sec1KeyseatEndSet")[0]
    widest = key.limits(key.KEYSEAT_WIDTH_MM, key.KEYSEAT_WIDTH_BAND)[1]
    assert spec.KEYSEAT_END_COLLAR_CLEARANCE_MIN_MM == pytest.approx(
        key.KEY_END_SET_MM + lower - widest / 2.0
    )
    assert key.KEY_END_SET_MM + lower >= (
        key.KEYSEAT_WIDTH_MM / 2.0 + spec.KEYSEAT_END_COLLAR_MARGIN_MM
    )
    assert spec.KEYSEAT_END_COLLAR_CLEARANCE_MIN_MM >= spec.KEYSEAT_END_COLLAR_MARGIN_MM
    # Positive control: .03 (the model tangent) cut into the face.
    assert 0.03 * 25.4 + printed_deviations(0.03 * 25.4, 2, unit="in")[0] < widest / 2.0
    upper = spec.printed_length_deviations("Sec1KeyseatEndSet")[1]
    key_band = printed_band_mm(key.KEY_LENGTH_PLACES, unit="in")
    north = (
        spec.COLLAR_END_STATION
        + key.KEY_END_SET_MM
        + upper
        + key.KEY_LENGTH_MM
        + key_band
    )
    # T024's south face with the stack pushed onto the collar at its shortest.
    t024_south = (
        spec.FRONT_STUB
        + spec.gear_faces(16)[0]
        + cone_tip_cluster.TIP_SET_SHIFT_MM
        + dt_cone_gear_stack.face_band(16, "south")[1]
    )
    assert spec.KEY_NORTH_MARGIN_MM == pytest.approx(t024_south - north)
    assert spec.KEY_NORTH_MARGIN_MM > 0.0
    # Its text sits right of the web's and left of its own left arrow, its
    # line below the web's witnesses and the collar diameter's lower line.
    x, y = drawing.SIDE_KEEP["Sec1KeyseatEndSet"]
    seat_x = drawing.BIG_END_X - spec.COLLAR_END_STATION / 1000.0
    # PR 1 r8 (1b3d39ffbd16) boxes about their positions: the ".05" text
    # 2.8 mm left, 3.0 right, 1.8 under, 1.7 over; its line 2.8 mm under its
    # position, as the web's and Sec1End's are; the web's outside left arrow
    # 6.3 mm long and 0.76 mm wide on its line from the collar face.
    text = (x - 0.0028, y - 0.0018, x + 0.0030, y + 0.0017)
    web_line = drawing.SIDE_KEEP["CollarWidth"][1] - 0.0028
    web_arrow = (seat_x - 0.0063, web_line - 0.00038, seat_x, web_line + 0.00038)
    dx = max(web_arrow[0] - text[2], text[0] - web_arrow[2], 0.0)
    dy = max(web_arrow[1] - text[3], text[1] - web_arrow[3], 0.0)
    assert math.hypot(dx, dy) >= CLEAR_GAP_M  # r8: 0.41 mm, layout audit gating
    # Its own left arrow, from the radius centre's extension line, ends right
    # of the text; its line stays above Sec1End's.
    left_arrow = seat_x - key.KEY_END_SET_MM / 1000.0 - 0.0036
    assert text[2] < left_arrow
    sec1_line = drawing.SIDE_KEEP["Sec1End"][1] - 0.0028
    assert y - 0.0028 - sec1_line >= 0.0015 and text[1] - sec1_line >= CLEAR_GAP_M


def test_shoulder_roots_are_modelled_not_noted() -> None:
    """The root radius is geometry with a size, not a sentence in a note block."""
    assert dt_cone_gear_shaft_spec.FILLET_RADIUS == pytest.approx(0.1016)
    # Its run along land 2 is booked in the step's setback.
    assert dt_cone_gear_shaft_spec.SEAT_STEP_BUDGET["fillet"] == (
        dt_cone_gear_shaft_spec.FILLET_RADIUS
    )
    # A single limit, R.004 MAX, never the title block's +-.005: the setback
    # books the printed maximum, which is the model radius.
    assert dt_cone_gear_shaft_spec.printed_length_deviations("ShoulderR") == pytest.approx(
        (-0.1016, 0.0)
    )
    assert dt_cone_gear_shaft_spec.FILLET_R_TOL_TYPE == 6  # swTolMAX
    # One root, one dimension, no quantity prefix (the collar's roots stay
    # sharp, #914).
    assert "ShoulderR" not in drawing.DIMENSION_CALLOUTS
    # The notes are numbered flag notes (rule 7): the land note, the bond
    # note and the stack note, each naming mates by drawing number.  No
    # design rationale, process, joint method or check of its own; the bond
    # note's compound grade is part of the fit's name (rule 26).
    notes = dt_cone_gear_shaft_spec.DRAWING_NOTES
    # The sheet's note text runs ~2.7 mm per character; a line from the
    # note anchor must end before the title block at x = 0.216 m (the
    # first render's 67-character line ran under the tolerance table).
    assert max(len(line) for line in notes.splitlines()) * 0.0027 < (
        0.216 - drawing.NOTES_XY[0]
    )
    numbered = [line.split(".")[0] for line in notes.splitlines() if not line.startswith(" ")]
    assert numbered == ["1", "2", "3"]
    # Notes 1 and 2 each carry their acceptance on one continuation line
    # (rule 4, form 2): five lines from y = 0.060 end above the frame.
    assert len(notes.splitlines()) == 5
    assert drawing.NOTES_XY[1] - 5 * 0.0035 > 0.020
    for forbidden in (
        "R0.",
        "MUST",
        "DATUM",
        "BASIC",
        "FINISH",
        "GRIND",
        "SOLDER",
        "BRAZE",
        "RETAIN",
        "ADHESIVE",
        "TAILSTOCK",
        "TURN ",
        "64T",
        "CLEAR OF",
    ):
        assert forbidden not in notes.upper()
    # The extension lines stop short of every section dimension's text foot.
    assert 0.0 < drawing.WITNESS_LINE_EXTENSION <= 0.0005
    assert "THREE-PLACE" not in notes


def test_the_sheet_carries_no_datums_or_feature_control_frames() -> None:
    """drawing-guidelines.md rule 5 (avoid excessive GD&T): no GD&T on a hand-built hobby shaft."""
    assert not hasattr(dt_cone_gear_shaft_spec, "PART_DATUMS")
    assert not hasattr(dt_cone_gear_shaft_spec, "GEOMETRIC_CONTROLS")
    assert tuple(control.key for control in dt_cone_gear_shaft_spec.SURFACE_FINISHES) == (
        "pivot_journal",
    )


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.SIDE_SCALE == (1, 1)  # full length, no reduction
    assert drawing.ISO_SCALE == (1, 2)  # reduced pictorial


def test_part_stamps_make_critical_properties() -> None:
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


def test_t024_tips_clear_the_keyed_land() -> None:
    """T024, the first gear on, slides over land 2 and stops at T030; its
    tips stand outside the keyed land it stops short of."""
    spec = dt_cone_gear_shaft_spec
    assert spec.outside_dia_mm is dt_cone_gear_spec.outside_dia_mm
    assert dt_cone_gear_spec.outside_dia_mm(24) > spec.SECTION_DIAS[1]


def test_shaft_loading_preflight_reads_t024s_accepted_tip(monkeypatch) -> None:
    spec = dt_cone_gear_shaft_spec
    calls = []
    tip = {"dia": spec.SECTION_DIAS[1] + 1.0}
    monkeypatch.setattr(
        spec, "outside_dia_mm", lambda teeth: calls.append(teeth) or tip["dia"]
    )
    spec.validate_gear_loading_clearances()
    assert calls == [24]
    tip["dia"] = spec.SECTION_DIAS[1]
    with pytest.raises(AssertionError, match="T024"):
        spec.validate_gear_loading_clearances()


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
    assert rows["SocketDepth"] == (spec.SOCKET_DEPTH, ("SocketDepth@Socket",))
    assert set(rows) == {
        *(f"SecEnd{i}" for i in range(len(spec.SECTIONS))),
        "CollarWidth",
        "SocketDepth",
    }


# #914 (user ruling 2026-09-25): an integral collar captures the shaft.  The
# tip end screw pushes the shaft south; the collar's south face bears on the
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
    import dt_crank_drive_gear_spec as gear64

    south = (
        drive.GEAR64_STATION
        + drive.GEAR_AXIS_SHIFT
        - gear64.LAYOUT_FACE_WIDTH / 2.0
        + gear64.SOUTH_FACE_SHIFT_NORTH
    )
    assert spec.GEAR64_SOUTH_FACE_STATION == pytest.approx(south, abs=1e-9)
    assert gear64.SOUTH_FACE_SHIFT_NORTH == 1.5
    web_under_8 = spec.COLLAR_THICKNESS - gear64.SOUTH_FACE_SHIFT_NORTH
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
    # On the former Ø.483 bore the title block's .010 on both edges took the
    # ring under the floor; the Ø.4385 bore (tool audit Q11) widens it so the
    # general break would hold too.  The printed .004 MAX is kept as printed.
    assert ring - 2.0 * 0.254 >= spec.THRUST_RING_FLOOR
    breaks = spec.THRUST_EDGE_BREAK_MAX
    assert ring - 2.0 * breaks >= spec.THRUST_RING_FLOOR
    assert breaks == pytest.approx(0.004 * 25.4)
    # the thickest bar still bears inside the boss: no overhang toward the post body
    assert spec.STOCK_DIA + spec.STOCK_DIA_BAND[0] < post.CONE_BOSS_DIA


def test_the_sheet_states_the_collar_as_stock_with_its_break() -> None:
    """The as-supplied collar prints as a reference diameter with the stock
    statement and its edge break beside it (the U41 plate's form)."""
    spec = dt_cone_gear_shaft_spec
    assert drawing.REFERENCE_DIAMETERS == ("CollarDia",)
    assert drawing.DIMENSION_CALLOUTS["CollarDia"] is spec.COLLAR_STOCK_CALLOUT
    # Rule 3: the tight break and root limits sit at the collar, never in a
    # note; rule 7: two lines of words, the mates named once by number.
    callout = spec.COLLAR_STOCK_CALLOUT
    assert len(callout.split("\n")) <= 2
    for limit in (spec.THRUST_EDGE_BREAK_MAX, spec.COLLAR_ROOT_RADIUS_MAX):
        assert spec.inch_text(limit, 3) in callout
    for mate in ("dt-cone-pivot-post", "dt-crank-drive-gear"):
        assert _config.parts(mate)["number"] in callout
    assert "BREAK" not in spec.DRAWING_NOTES and "ROOTS" not in spec.DRAWING_NOTES
    assert spec.COLLAR_ROOT_RADIUS_MAX < spec.THRUST_EDGE_BREAK_MAX
    assert spec.DRAWING_PRECISION["CollarProfile"]["CollarDia"] == 3
    assert spec.COLLAR_DIA == pytest.approx(0.625 * 25.4)


def test_each_chucking_measures_from_its_own_collar_face() -> None:
    """Rule 11 (round 6, Main's delegated ruling (b)): the journal and the web
    run from the collar's thrust face; the gear lands and the tip from its
    tip-side face, the face the gear stack stands on."""
    spec = dt_cone_gear_shaft_spec
    assert spec.DATUM_STATION == spec.COLLAR_END_STATION
    assert spec.COLLAR_END_STATION - spec.COLLAR_START_STATION == spec.COLLAR_THICKNESS
    assert spec.SECTION_ORIGINS == ("Front Plane", "CollarEndPlane", "CollarEndPlane")
    assert spec.SECTION_KNOBS[0] == spec.JOURNAL_END
    for i in (1, 2):
        assert spec.SECTION_KNOBS[i] == pytest.approx(
            spec.SECTION_ENDS[i] - spec.COLLAR_END_STATION
        )
    # The tip prints at three places: the recess proof books its band.
    assert spec.DRAWING_PRECISION_BY_NAME["Sec2End"] == 3
    # The journal, the web and the tip station chain the two ends; the
    # front-to-tip overall is a reference, its places handed over by the spec.
    assert spec.SECTION_KNOBS[0] + spec.COLLAR_THICKNESS + spec.SECTION_KNOBS[2] == (
        pytest.approx(spec.SHAFT_LENGTH)
    )
    assert spec.DRAWING_REFERENCE_PRECISION == 2


def test_the_64t_straight_tooth_space_keeps_its_material_and_flank_gates(monkeypatch) -> None:
    """Record the helper's real recipe, without native CAD (owner ruling
    2026-11-10 on #2332: straight teeth inclined to the axis)."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import _straight_gash_gear as _gear
    import dt_crank_drive_gear_spec as gear

    form, gash = gear.TOOTH_SPACE_FORM, gear.TOOTH_SPACE
    assert gash.inclination_deg == cone_line.INCLINE_DEG
    face = gear.FACE_WIDTH
    events = []
    volumes = {}
    planes = []
    curves = []
    expressions = []

    def record_volume(_adapter, label, expected, tolerance):
        volumes[label] = (expected, tolerance)
        events.append(label)
        return expected

    def record_plane(_adapter, name, **kwargs):
        planes.append((name, kwargs))

    def record_crossing(_adapter, name, z_mm):
        planes.append((name, {"z_mm": z_mm}))

    def record_curve(_adapter, name, x, y):
        curves.append(name)
        expressions.append((x, y))
        return name

    def record_flanks(_adapter, section, actual, *, tolerance_mm):
        assert (section, actual, tolerance_mm) == (form, gash, gear.NATIVE_FLANK_BOUND_MM)
        events.append("flank gate")

    def record_pattern(_adapter, seed, teeth, radius, station):
        assert (seed, teeth, radius, station) == (
            "ToothSpaceCut", gear.TEETH, gash.blank_radius_mm, face / 2.0
        )
        events.append("pattern")
        return SimpleNamespace(name="ToothSpacePattern")

    monkeypatch.setattr(_gear, "check", lambda _label, value: value)
    for name in ("define_circle", "ensure_fully_defined"):
        monkeypatch.setattr(_gear, name, MagicMock())
    monkeypatch.setattr(_gear, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(_gear, "blank_reference_geometry", lambda *_args: None)
    monkeypatch.setattr(_gear, "volume_check", record_volume)
    monkeypatch.setattr(_gear, "_plane_through", record_plane)
    monkeypatch.setattr(_gear, "_crossing_plane", record_crossing)
    # The frame the farm read back (run 20261110T210742240Z): an off-origin
    # sketch with a 3.4e-18 residue, which ``.12g`` spelled as an exponent
    # the equation parser rejected.
    monkeypatch.setattr(
        _gear, "_sketch_mapper", lambda *_args: (
            (3.3881317890172014e-18, 0.39999645716715093, -2.1684043449710089e-16),
            (-0.9999999999999998, 0.0, 0.0),
            (0.0, -1.0000000000000002, 0.0),
        )
    )
    monkeypatch.setattr(_gear, "equation_curve", record_curve)
    monkeypatch.setattr(_gear, "assert_straight_gash_flanks", record_flanks)
    monkeypatch.setattr(_gear, "pattern_about_z", record_pattern)
    adapter = MagicMock()
    adapter.create_axis = MagicMock(
        side_effect=[SimpleNamespace(name="GearAxis"), SimpleNamespace(name="PivotAxis")]
    )
    adapter.create_cut_extrude = MagicMock(return_value=SimpleNamespace(name="ToothSpaceCut"))
    disc = _gear.build_straight_gash_gear(
            adapter, form, gash, gear.TEETH, flank_bound_mm=gear.NATIVE_FLANK_BOUND_MM
        )

    assert adapter.create_sketch.call_args_list[0].args == ("Front",)
    assert adapter.create_sketch.call_args_list[1].args == ("ToothSpaceCutterPlane",)
    assert adapter.create_extrusion.call_args.args[0].depth == face
    cut = adapter.create_cut_extrude.call_args.args[0]
    assert cut.both_directions and cut.depth == pytest.approx(2.0 * (face + 2.0))
    assert planes == [
        ("ToothSpaceRadialPlane", {
            "base_plane": "Top Plane", "pivot_axis": "GearAxis",
            "angle_deg": math.degrees(gash.azimuth_rad), "direction": gash.radial,
        }),
        ("ToothSpaceCrossingPlane", {"z_mm": gear.TOOTH_SPACE_CROSSING}),
        ("ToothSpaceCutterPlane", {
            "base_plane": "ToothSpaceCrossingPlane", "pivot_axis": "PivotAxis",
            "angle_deg": gash.inclination_deg, "direction": gash.section_tangential,
        }),
    ]
    assert curves == [
        segment.name
        for segment in form.cut_order_native_segments(
            unit_scale=1.0 / _gear.IN,
            clearance_radius_mm=max(_gear.R_CLEAR_IN * _gear.IN, form.blank_radius_mm + 1.0),
        )
    ]
    for x, y in expressions:
        assert not re.search(r"\d[eE][-+]?\d", x + y), (x, y)
    first_x, first_y = expressions[0]
    assert first_x.startswith("(0.000000000000)+(-1.000000000000)*(")
    assert first_y.startswith(f"({0.39999645716715093 / _gear.IN:.12f})+(-1.000000000000)*(")
    blank = math.pi * gash.blank_radius_mm**2 * face
    removed = gash.removed_volume_mm3(form)
    assert volumes["seeded tooth space"] == (pytest.approx(blank - removed), 1.0)
    final = blank - gear.TEETH * removed
    assert volumes["toothed disc"] == (pytest.approx(final), pytest.approx(0.01 * final))
    assert events.index("seeded tooth space") < events.index("flank gate")
    assert events.index("flank gate") < events.index("pattern") < events.index("toothed disc")
    assert disc.volume == pytest.approx(final)
    assert disc.tooth_features == ("ToothSpaceCut", "ToothSpacePattern")
    # The screw-section model is the printed data's, never the cut's.
    with pytest.raises(ValueError, match="own"):
        _gear.build_straight_gash_gear(
                adapter, gear.STOCK_PROFILE, gash, gear.TEETH,
                flank_bound_mm=gear.NATIVE_FLANK_BOUND_MM,
            )
