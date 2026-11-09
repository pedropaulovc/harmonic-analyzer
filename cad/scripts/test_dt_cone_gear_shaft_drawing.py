"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import _config
from _printed_tolerance import printed_band_mm
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
    """Each turned land rides its NAMED fit class, applied to the model.

    Spelled as callout text the band is frozen: SolidWorks prints it verbatim
    and never re-renders it, so the mm->inch flip in issue #290 would leave
    "+0.00/-0.02" reading as inches on every land. The identity assertion also
    stops a local retype from silently forking a named class.
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
    # The socket rides the tip cluster's reamed stem-bore band.
    assert spec.SOCKET_DIA_BAND is cone_tip_cluster.STEM_BORE_BAND
    assert spec.SOCKET_DIA == cone_tip_cluster.STEM_BORE_DIA_MM
    # Applied in ONE loop over the named land bands, so the AST reports the
    # f-string sources rather than literal keys.
    assert model_toleranced_dimensions(part) == {
        ("f'Sec{section}Profile'", "f'Sec{section}Dia'"): "*deviations(band)",
        ("Sec1KeyseatProfile", "name"): "*deviations(band)",
        ("SocketProfile", "SocketDia"): "*deviations(SOCKET_DIA_BAND)",
        ("ShoulderFillets", "ShoulderR"): "*deviations(FILLET_R_BAND)",
    }


def test_the_build_rounds_only_the_step_root(monkeypatch):
    """Run the real part build with recording doubles: no chamfer is authored
    by any route (adapter, helper or raw COM chain), and the one edge
    rounding picks only the land-1 to land-2 step's edge on land 2."""
    adapter, stubs, _dims, _gated = _stubbed_build(monkeypatch)
    operations = [str(c[0]) for c in adapter.mock_calls] + [
        f"{name}.{c[0]}" for name, stub in stubs.items() for c in stub.mock_calls
    ]
    assert not [op for op in operations if "chamfer" in op.lower()]
    fillets = adapter.add_fillet.await_args_list
    assert len(fillets) == 1, "the step-root fillet is the positive control"
    picks = fillets[0].args[1]
    assert picks == [[-part.SECTION_DIAS[2] / 2.0, 0.0, part.SECTION_ENDS[1]]]


def _centre_mark_view(marks: list, deletes: bool):
    """A section view holding ``marks`` and a drawing whose EditDelete drops
    the selected one (or, ``deletes=False``, silently keeps it)."""
    from types import SimpleNamespace

    events: list[str] = []
    selected: list = []

    def select(mark):
        def _select(append, _data):
            assert append is False
            selected.append(mark)
            events.append("select")
            return True

        return _select

    for mark in marks:
        mark.Select2 = select(mark)

    def edit_delete():
        events.append("delete")
        if deletes:
            for mark in selected:
                marks.remove(mark)

    draw = SimpleNamespace(
        ClearSelection2=lambda _all: selected.clear() or True,
        EditDelete=edit_delete,
    )
    view = SimpleNamespace(
        GetAnnotationsByType=lambda kind: (
            tuple(marks) if kind == drawing._CENTER_MARK_ANNOTATION else ()
        )
    )
    return SimpleNamespace(currentModel=draw), view, events


def test_the_section_loses_its_centre_mark(monkeypatch):
    """Machinist review r7: the full A-A got SolidWorks' centre mark.  The
    mark is deleted and read back gone; a section with none is left alone; a
    delete that does not land fails the build."""
    from types import SimpleNamespace

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    a_a = drawing.D_SECTIONS[0]
    marks = [SimpleNamespace()]
    adapter, view, events = _centre_mark_view(marks, deletes=True)
    drawing._delete_centre_mark(adapter, view, a_a)
    assert marks == [] and events == ["select", "delete"]
    # no mark: nothing to delete, nothing selected
    adapter, view, events = _centre_mark_view([], deletes=True)
    drawing._delete_centre_mark(adapter, view, a_a)
    assert events == []
    # the delete is VT_VOID: only the re-read proves it
    adapter, view, _events = _centre_mark_view([SimpleNamespace()], deletes=False)
    with pytest.raises(RuntimeError, match="survived deletion"):
        drawing._delete_centre_mark(adapter, view, a_a)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_delete_centre_mark(adapter, view, section)" in source
    assert "carries a centre mark again" in source


def test_the_keyseat_section_flags_the_land_note(monkeypatch):
    """Run the real section loop with its native steps recorded: A-A prints
    the keyseat's S and width, the width flagged to the land note; nothing
    rides above them."""
    suffixes = []
    monkeypatch.setattr(drawing, "_cut_endpoints", lambda *_a: ((0.0, 0.0), (1.0, 0.0)))
    monkeypatch.setattr(drawing, "create_section_view", lambda *_a, label, **_k: label)
    monkeypatch.setattr(drawing, "_prepare_d_section", lambda *_a: None)
    monkeypatch.setattr(drawing, "_keyseat_width_text_position", lambda *_a: (0.0, 0.0))
    monkeypatch.setattr(
        drawing, "curate_view_dimensions", lambda _a, _view, *, keep, **_k: list(keep)
    )
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, dimension: dimension)
    monkeypatch.setattr(drawing, "_delete_centre_mark", lambda *_a: None)
    monkeypatch.setattr(drawing, "_section_face", lambda *_a: (0.0, 0.0, 1.0, 1.0))
    monkeypatch.setattr(drawing, "_place_view_caption", lambda *_a, **_k: None)
    monkeypatch.setattr(
        drawing,
        "set_dimension_callouts",
        lambda *_a, **_k: pytest.fail("no callout rides a section dimension"),
    )
    monkeypatch.setattr(
        drawing,
        "_set_dimension_suffixes",
        lambda _a, dimensions, texts: suffixes.append((tuple(dimensions), texts)),
    )
    placed = drawing._add_d_sections(object(), object(), 1)
    assert len(placed) == len(drawing.D_SECTIONS) == 1
    assert placed[0].dimensions == ("Sec1KeyseatS", "Sec1KeyseatWidth")
    assert suffixes == [
        (
            ("Sec1KeyseatS", "Sec1KeyseatWidth"),
            {"Sec1KeyseatWidth": f" NOTE {dt_cone_gear_shaft_spec.LAND_NOTE}"},
        )
    ]


def test_every_tight_band_names_its_mate_and_fit_route():
    """Rule 4: a band under its shop row names a fit route at the feature.
    The journal is a matched running fit to the MHA-DT-05 bore with the
    printed limits' clearance; land 1 and its keyseat link the land note,
    land 2 and the socket the bond note, each naming its mates by drawing
    number.  Lengths carry no words but the stack flag."""
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
    assert drawing.DIMENSION_SUFFIXES["Sec2Dia"] == f" SEE NOTE {spec.BOND_NOTE}"
    assert {drawing.DIMENSION_SUFFIXES[name] for name in drawing.STACK_LENGTHS} == {
        drawing.STACK_FLAG_SUFFIX
    }
    assert str(spec.STACK_NOTE) in drawing.STACK_FLAG_SUFFIX
    notes = spec.DRAWING_NOTES.splitlines()
    assert [note.split(".")[0] for note in notes] == [
        str(spec.LAND_NOTE), str(spec.BOND_NOTE), str(spec.STACK_NOTE)
    ]
    # Land 1's mates and its key (owner decision 2026-11-09, PR #1992) by
    # number.
    for mate in ("dt-cone-gear", "dt-crank-drive-gear", "dt-vn-cone-shaft-key"):
        assert _config.parts(mate)["number"] in notes[0]
    # Land 2 and the socket are bonded fits: their mates by number; the
    # compound is the assembly sheet's (rule 23).
    for mate in ("dt-cone-gear", "dt-cone-tip-gear"):
        assert _config.parts(mate)["number"] in notes[1]
    assert "BONDED FIT" in notes[1] and "LOCTITE" not in spec.DRAWING_NOTES
    # The three-place lengths name the stack they set once (rule 4).
    for mate in ("dt-cone-gear", "dt-crank-drive-gear"):
        assert _config.parts(mate)["number"] in notes[2]
    # Rule 7: notes carry no dimension and no method.
    assert not re.search(r"\d?\.\d{2,}", spec.DRAWING_NOTES)
    for word in ("TAILSTOCK", "MILL", "TURN"):
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
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_precision" not in source
    # The pure reference (the overall) takes its places from the existing
    # spec constant, never a literal or a new band.
    assert source.count("SetPrecision3") == 1
    assert source.count("SetPrecision3(DRAWING_REFERENCE_PRECISION, ") == 1
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in (
        Path(part.__file__).read_text(encoding="utf-8")
    )
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
    """The step T030|T024 sits 1.0 south of T030's north face, inside T030,
    and at print-worst the step and its root stay south of T024."""
    spec = dt_cone_gear_shaft_spec
    station = spec.SECTION_ENDS[1] - spec.FRONT_STUB
    south, north = spec.gear_faces(15)
    assert station == pytest.approx(north - 1.0)
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
_SEC1_LINES = [((0.1400, 0.1452), (0.1400, 0.1548))]


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
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "if name in NEAR_SIDE_DIAMETERS:" in source
    assert 'set_near_side_diameter(moved, f"{name} near-side diameter")' in source


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
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Front", *TIP_END_VIEW_CENTER, scale=SIDE_SCALE' in source
    assert set(drawing.TIP_END_VIEW_KEEP) == {"SocketDia"}
    text_x, text_y = drawing.TIP_END_VIEW_KEEP["SocketDia"]
    lines = 1 + len(spec.SOCKET_CALLOUT.split("\n"))
    width = max(
        drawing.DIAMETER_TEXT_WIDTH,
        *(len(line) * drawing.CALLOUT_CHAR_WIDTH for line in spec.SOCKET_CALLOUT.split("\n")),
    )
    assert margin <= text_x and text_y <= template.height_m - margin
    assert text_y - lines * 0.005 > y + half + CLEAR_GAP_M
    assert text_x + width < drawing.SIDE_DIAMETERS["Sec2Dia"][0] + 0.010
    assert text_y - lines * 0.005 > drawing.NOTES_XY[1]


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
    # The integral bearing journal fits the v2 post at 0.0127 diametral
    # clearance; the gear lands keep their diameters.
    assert spec.JOURNAL_BORE_DIA == pytest.approx(12.2682)
    assert spec.JOURNAL_CLEARANCE == pytest.approx(0.0127)
    assert spec.JOURNAL_DIA == pytest.approx(12.2555)
    assert spec.JOURNAL_END == pytest.approx(43.18)
    assert dias == pytest.approx((12.2555, 9.525, 6.35))
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


def test_the_swing_platform_pivot_station_is_bit_identical() -> None:
    """C1 keyed (owner decision 2026-11-09, PR #1992) moves no drilled hole in
    the harmonic base: the pivot keeps origin/main's exact float, its 8.0
    extension a literal now that the collar shift it summed is retired."""
    import cone_stations

    assert cone_stations.TIP_END_EXTENSION_MM == 8.0
    assert cone_stations.PIVOT_STATION == 160.02197937541507
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
    assert end_upper == pytest.approx(-end_lower, abs=0.01)
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
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '("Sec1KeyseatWidth", cone_land_key.KEYSEAT_WIDTH_BAND)' in source
    assert '("Sec1KeyseatS", cone_land_key.KEYSEAT_S_BAND)' in source
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


def test_each_cut_is_made_over_exactly_its_feature(monkeypatch) -> None:
    """Land 1's keyseat is sketched on its end plane and cut blind back over
    the land to the collar face; the socket is sketched on land 2's end plane
    (the shaft's end) and cut blind its depth back into land 2."""
    adapter, stubs, _sketch_dims, _gated = _stubbed_build(monkeypatch)
    spec = dt_cone_gear_shaft_spec
    sketched = [c.args[0] for c in adapter.create_sketch.call_args_list]
    assert sketched.count("Sec1EndPlane") == 2  # the land's profile and the keyseat
    assert sketched.count("Sec2EndPlane") == 2  # the land's profile and the socket
    cuts = [c.args[0] for c in adapter.create_cut_extrude.call_args_list]
    assert [params.depth for params in cuts] == pytest.approx(
        [spec.SECTION_ENDS[1] - spec.COLLAR_END_STATION, spec.SOCKET_DEPTH]
    )
    assert not any(params.reverse_direction for params in cuts)
    named = [c.args[1] for c in stubs["name_last_feature"].call_args_list]
    assert [name for name in named if name in {"Sec1Keyseat", "SocketProfile", "Socket"}] == [
        "Sec1Keyseat", "SocketProfile", "Socket"
    ]
    assert not [name for name in named if "Flat" in name or name.startswith(("Sec3", "Sec4"))]


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
    t024_south = spec.FRONT_STUB + spec.gear_faces(16)[0]
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
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "await adapter.add_fillet(\n            FILLET_RADIUS," in source
    assert 'name_last_feature(adapter, "ShoulderFillets")' in source
    assert 'name_dimensions(adapter, "ShoulderFillets", ["ShoulderR"])' in source
    assert "tolerance.Type = FILLET_R_TOL_TYPE" in source
    assert "_shoulder_root_max_limit(adapter)" in source
    # One root, one dimension, no quantity prefix (the collar's roots stay
    # sharp, #914).
    assert "ShoulderR" not in drawing.DIMENSION_CALLOUTS
    # The notes are numbered flag notes (rule 7): the land note, the bond
    # note and the stack note, each naming mates by drawing number.  No
    # design rationale, process, joint method or check of its own.
    notes = dt_cone_gear_shaft_spec.DRAWING_NOTES
    # The sheet's note text runs ~2.7 mm per character; a line from the
    # note anchor must end before the title block at x = 0.216 m (the
    # first render's 67-character line ran under the tolerance table).
    assert max(len(line) for line in notes.splitlines()) * 0.0027 < (
        0.216 - drawing.NOTES_XY[0]
    )
    numbered = [line.split(".")[0] for line in notes.splitlines() if not line.startswith(" ")]
    assert numbered == ["1", "2", "3"]
    assert len(notes.splitlines()) == 3
    for forbidden in (
        "R0.",
        "MUST",
        "DATUM",
        "BASIC",
        "FINISH",
        "GRIND",
        "SOLDER",
        "BRAZE",
        "LOCTITE",
        "RETAIN",
        "ADHESIVE",
        "TAILSTOCK",
        "TURN",
        "64T",
        "CLEAR OF",
    ):
        assert forbidden not in notes.upper()
    # The extension lines stop short of every section dimension's text foot.
    assert 0.0 < drawing.WITNESS_LINE_EXTENSION <= 0.0005
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_pin_witness_line_extension(drawing_model)" in drawing_source
    assert "THREE-PLACE" not in notes
    assert (
        'apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})'
        in source
    )
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)' in (
        Path(drawing.__file__).read_text(encoding="utf-8")
    )


def test_the_sheet_carries_no_datums_or_feature_control_frames() -> None:
    """drawing-guidelines.md rule 5 (avoid excessive GD&T): no GD&T on a hand-built hobby shaft."""
    assert not hasattr(dt_cone_gear_shaft_spec, "PART_DATUMS")
    assert not hasattr(dt_cone_gear_shaft_spec, "GEOMETRIC_CONTROLS")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for banned in (
        "project_part_pmi(",
        "add_feature_control_frame(",
        "add_datum_feature(",
    ):
        assert banned not in source
    # Only the journal that runs keeps its roughness symbol: every other
    # land's parts are fixed to it (rule 6, r5).
    assert source.count("add_surface_finish(") == 1
    assert tuple(control.key for control in dt_cone_gear_shaft_spec.SURFACE_FINISHES) == (
        "pivot_journal",
    )
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in part_source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.SIDE_SCALE == (1, 1)  # full length, no reduction
    assert drawing.ISO_SCALE == (1, 2)  # reduced pictorial
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The donor end view hands its diameters over and is deleted; the tip end
    # view, at the sheet scale, carries only the socket.
    assert source.count('"*Front"') == 2
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
    # The keyseat's length follows land 1's knob; its sketch is sized by the
    # land's diameter and the key globals.  The socket's diameter is its
    # global's.
    assert owners["Sec1KeyseatLength@Sec1Keyseat"] == '"SecEnd1"'
    (socket,) = [
        c
        for c in stubs["define_circle"].call_args_list
        if c.kwargs["names"][2] == "SocketDia"
    ]
    assert socket.kwargs["drives"] == (None, None, '"SocketDia"')
    assert socket.args[3] == pytest.approx(dt_cone_gear_shaft_spec.SOCKET_DIA / 2.0)
    assert records["Sec1KeyseatWidth"] == '"Sec1KeyseatW"'
    assert records["Sec1KeyseatS"] == '"Sec1KeyseatS"'
    assert records["Sec1FarSide"] == '"SecDia1" / 2'


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
            {"Sec2Station@Sec2EndPlane": ('"SecEnd2"', 2)},
            "SecEnd2: DrivenState differs",
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
    dims["Sec2Station@Sec2EndPlane"] = _Dim(
        dt_cone_gear_shaft_spec.SECTION_KNOBS[2] + 1e-3
    )
    del dims["CollarFaceStation@CollarFace"]
    adapter = _gate_fixture(monkeypatch, dims, equations)
    with pytest.raises(RuntimeError, match="expected one equation") as raised:
        part._assert_stations_single_owned(adapter)
    assert "Sec2Station@Sec2EndPlane: reads" in str(raised.value)
    assert "CollarFaceStation@CollarFace not found" in str(raised.value)


def test_station_gate_proves_the_depth_owner_too(monkeypatch) -> None:
    """Codex #839 P2: a depth that keeps its as-built value and DrivenState
    but is driven by the wrong global, or has lost its equation, must fail --
    as must a knob defined twice."""
    dims, equations = _machine({"Sec2End@Sec2": ('"SecEnd1"', 1)})
    del equations['"SocketDepth@Socket"']
    equations['"CollarWidth"'] *= 2
    adapter = _gate_fixture(monkeypatch, dims, equations)
    with pytest.raises(RuntimeError) as raised:
        part._assert_stations_single_owned(adapter)
    message = str(raised.value)
    assert "Sec2End@Sec2: owned by" in message
    assert "SocketDepth@Socket: expected one equation" in message
    assert "CollarWidth: expected one definition" in message
    assert "Sec1" not in message.replace("SecEnd1", "")


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
    # the title block's .010 break on both edges would take it under the floor
    assert ring - 2.0 * 0.254 < spec.THRUST_RING_FLOOR
    # the printed break is the largest three-place inch value that keeps the floor
    breaks = spec.THRUST_EDGE_BREAK_MAX
    assert ring - 2.0 * breaks >= spec.THRUST_RING_FLOOR
    assert ring - 2.0 * (breaks + 0.0254) < spec.THRUST_RING_FLOOR
    assert breaks / 25.4 == pytest.approx(round(breaks / 25.4, 3))
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
    # The keyseat end's plane maps the shaft axis onto its sketch's -x.
    monkeypatch.setattr(part, "_sketch_xy_mm", lambda _a, point: (-point[2], point[1]))
    stubs["add_line_chain"].side_effect = lambda _a, points, close=True: [
        f"L{k}" for k in range(len(points) if close else len(points) - 1)
    ]
    monkeypatch.setattr(part, "_shoulder_root_max_limit", lambda _a: None)
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


def test_every_land_is_placed_from_its_chucking_origin(monkeypatch) -> None:
    """Rule 11 (round 6): the collar's thrust face comes first, from the front
    face by the journal, then its tip-side face one web on; the collar is
    turned onto the journal, and lands 1-2 end on planes offset from the
    tip-side face and extrude back to it, so each depth IS the shoulder's
    station from that face.  The front-to-tip overall is only a reference."""
    spec = dt_cone_gear_shaft_spec
    adapter, stubs, _dims, _gated = _stubbed_build(monkeypatch)
    planes = _planes(adapter)
    assert planes[:2] == [
        ("Front Plane", spec.COLLAR_START_STATION),
        ("CollarFace", spec.COLLAR_THICKNESS),
    ]
    for i in range(1, len(spec.SECTIONS)):
        assert (spec.SECTION_ORIGINS[i], spec.SECTION_KNOBS[i]) in planes, i
    extrusions = [c.args[0] for c in adapter.create_extrusion.call_args_list]
    # journal, collar, then the two gear lands
    assert [e.depth for e in extrusions[: len(spec.SECTIONS) + 1]] == [
        spec.SECTION_KNOBS[0],
        spec.COLLAR_THICKNESS,
        *spec.SECTION_KNOBS[1:],
    ]
    assert [e.reverse_direction for e in extrusions[: len(spec.SECTIONS) + 1]] == [
        False,
        True,
        True,
        True,
    ]
    knobs = {c.args[1]: c.args[2] for c in stubs["set_global"].call_args_list}
    for i, knob in enumerate(spec.SECTION_KNOBS):
        assert knobs[f"SecEnd{i}"] == f"{knob}mm"
    assert knobs["SocketDia"] == f"{spec.SOCKET_DIA}mm"
    assert knobs["SocketDepth"] == f"{spec.SOCKET_DEPTH}mm"
    assert not [name for name in knobs if name.startswith("SecAF")]
    assert knobs["Sec1KeyseatW"] == f"{cone_land_key.KEYSEAT_WIDTH_MM}mm"
    assert knobs["Sec1KeyseatS"] == f"{cone_land_key.KEYSEAT_S_MM}mm"
    assert knobs["Sec1KeyseatEndSet"] == f"{cone_land_key.KEY_END_SET_MM}mm"
    assert "CollarEnd" not in knobs


def test_build_turns_the_collar_between_the_journal_and_the_64t(monkeypatch) -> None:
    """#914: the collar is its own land -- sketched on a plane one web north of
    the collar face, at the bar's own Ø15.875, extruded back one web.  Its roots stay sharp (the
    post and the 64T bear flat on its faces) and the old journal-to-3/8 step
    edge is buried under it."""
    spec = dt_cone_gear_shaft_spec
    adapter, stubs, _dims, _gated = _stubbed_build(monkeypatch)
    planes = _planes(adapter)
    assert ("CollarFace", spec.COLLAR_THICKNESS) in planes
    # The collar plane comes before every tip-side land plane measured from it.
    first_land = planes.index((spec.SECTION_ORIGINS[1], spec.SECTION_KNOBS[1]))
    assert planes.index(("CollarFace", spec.COLLAR_THICKNESS)) < first_land
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
    # The one step root is a full circle on land 2.
    assert edges == [[-spec.SECTION_DIAS[2] / 2.0, 0.0, spec.SECTION_ENDS[1]]]
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
    land 2's start circle share those diameters at other stations, and the
    socket's mouth shares the tip's station."""
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
        _Edge(_Curve(spec.SECTION_ENDS[1] / 1000.0, tip_r)),
        _Edge(_Curve(-length, spec.SOCKET_DIA / 2000.0)),
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


def test_the_64t_build_hands_the_stock_helper_its_profile_and_sweep_bound(monkeypatch) -> None:
    """Run the real 64T build up to its stock-form gear, recording the call."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    import build_dt_crank_drive_gear as crank

    class Reached(Exception):
        pass

    calls = []

    async def stock_form_gear(*args, **kwargs):
        calls.append((args[1:], kwargs))
        raise Reached

    monkeypatch.setattr(crank, "check", MagicMock())
    monkeypatch.setattr(crank, "set_global", AsyncMock())
    monkeypatch.setattr(crank, "apply_package_model_units", MagicMock())
    monkeypatch.setattr(crank, "build_stock_form_gear", stock_form_gear)
    with pytest.raises(Reached):
        asyncio.run(crank.build(AsyncMock()))
    assert calls == [(
        (crank.STOCK_PROFILE, crank.FACE_WIDTH),
        {"screw_sweep_bound_mm": crank.NATIVE_SWEEP_BOUND_MM},
    )]


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
