"""Offline contracts for the pinion-return-leaf-spring drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_pinion_spring as spring
import draw_dt_pinion_spring as drawing
import dt_pinion_spring_geometry as geometry
import dt_pinion_spring_section as section
import dt_pinion_spring_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from machinist_exceptions import load_exceptions

_XX_BAND = printed_band_mm(2, unit="in")
_HOLE_OVERSIZE = drilled_oversize_mm(unit="in")
_WEB_TARGET = WALL_TARGET_MM  # machined webs >= .080 at the printed worst case


class _MarkDisplay:
    def __init__(self, lines):
        self.lines = lines

    def GetLineCount(self):
        return len(self.lines)

    def GetLineAtIndex2(self, index):
        return self.lines[index]


class _CentreMark:
    def __init__(self, data):
        self.data = data

    def GetDisplayData(self):
        return self.data


class _MarkedTop:
    def __init__(self, marks):
        self.marks = marks

    def GetAnnotationsByType(self, kind):
        assert kind == 13  # swCenterMark
        return self.marks


def _pad_mark(x=0.1147081, y=0.228):
    return _CentreMark(
        _MarkDisplay(
            [
                [0, 0, 0, 0, x - 0.003, y, 0, x + 0.003, y, 0],
                [0, 0, 0, 0, x, y - 0.003, 0, x, y + 0.003, 0],
            ]
        )
    )


@pytest.fixture
def pad_mark_projection(monkeypatch):
    adapter = object()
    calls = []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)

    def project(actual_adapter, view, point, *, label):
        assert actual_adapter is adapter
        assert point == pytest.approx(
            tuple(value / 1000.0 for value in drawing.HOLE_CENTER)
        )
        assert label == "pad hole axis"
        calls.append(view)
        return (0.1147081, 0.228, 0.0)

    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing._telemetry, "success", lambda message: None)
    return adapter, calls


@pytest.mark.parametrize("offset", [0.0, 0.00049])
def test_template_pad_mark_is_proved_from_printed_lines(pad_mark_projection, offset):
    adapter, calls = pad_mark_projection
    top = _MarkedTop([_pad_mark(x=0.1147081 + offset)])
    drawing._prove_pad_hole_centre_mark(adapter, top)
    assert calls == [top]


@pytest.mark.parametrize("marks", [None, [], [_pad_mark(), _pad_mark()]])
def test_template_pad_mark_census_fails_closed(pad_mark_projection, marks):
    adapter, calls = pad_mark_projection
    with pytest.raises(RuntimeError, match="centre marks"):
        drawing._prove_pad_hole_centre_mark(adapter, _MarkedTop(marks))
    assert calls == []


@pytest.mark.parametrize(
    ("mark", "message"),
    [
        (_pad_mark(x=0.1157081), "off the hole axis"),
        (_CentreMark(None), "no display data"),
        (_CentreMark(_MarkDisplay([])), "draws no lines"),
        (_CentreMark(_MarkDisplay([[0] * 9])), "invalid display lines"),
        (_pad_mark(x=float("nan")), "invalid display lines"),
    ],
)
def test_invalid_template_pad_mark_is_rejected(pad_mark_projection, mark, message):
    adapter, _calls = pad_mark_projection
    with pytest.raises(RuntimeError, match=message):
        drawing._prove_pad_hole_centre_mark(adapter, _MarkedTop([mark]))


def test_spring_contact_rises_with_pivot_while_foot_stays_on_base() -> None:
    from dt_pinion_pivot_block_geometry import BORE_UP
    from pinion_rig_park_geometry import STRAP_LEAN_DEG

    assert geometry.PIVOT_LY == BORE_UP
    assert geometry.STRAP_LEAN_DEG == STRAP_LEAN_DEG
    assert geometry.FOOT_Y == geometry.THICK
    crest = (
        geometry.CREST[0] - geometry.PIVOT_LX,
        geometry.CREST[1] - geometry.PIVOT_LY,
    )
    station = sum(a * b for a, b in zip(crest, geometry.STRAP_U, strict=True))
    assert station == pytest.approx(geometry.CONTACT_T)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-spring.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-spring.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-spring_drawing.png")
    assert DRAWINGS_BY_NAME["dt_pinion_spring"].script == Path(drawing.__file__).resolve()
    assert "draw_dt_pinion_spring.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert spring.DRAWING_DIMENSIONS is dt_pinion_spring_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_pinion_spring_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP)
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (spring.FOOT_LEN, spring.THICK, spring.WIDTH) == (
        dt_pinion_spring_spec.FOOT_LEN,
        dt_pinion_spring_spec.THICK,
        dt_pinion_spring_spec.WIDTH,
    )


def test_preload_setting_formed_features_carry_the_formed_band() -> None:
    # Main's r6 ruling (c): the dimensions that set the crest's preload carry
    # the +/-.020 band the drive train's corner walk books, at .XXX (their
    # millimetre nominals are kept); the flick's two ride the .XX and angular
    # rows (PR #1675, #290).
    assert dt_pinion_spring_spec.FORMED_TOLERANCE_MM == pytest.approx(0.020 * 25.4)
    assert model_toleranced_dimensions(spring) == {
        ("feature_name", "name"): "FORMED_TOLERANCE_MM"
    }
    banded = set().union(*dt_pinion_spring_spec.FORMED_BANDED_DIMENSIONS.values())
    assert banded == set(geometry.FORMED_CONTACT_BANDS)
    assert not banded & {"FlatLen", dt_pinion_spring_spec.FREE_KINK_ANGLE}
    for name in banded:
        assert "MHA-DT-14" in drawing.DIMENSION_CALLOUTS[name]
    precision = dt_pinion_spring_spec.DRAWING_PRECISION_BY_NAME
    assert {name: precision[name] for name in banded} == dict.fromkeys(banded, 3)
    assert precision["FlatLen"] == 2
    assert precision[dt_pinion_spring_spec.FREE_KINK_ANGLE] == 0
    assert (precision["PadWidth"], precision["PadLen"], precision["PadReliefR"]) == (
        2,
        2,
        3,
    )
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "_pad_relief_max_limit(adapter)" in source


def test_profile_and_wing_are_baselined_from_the_hole_axis() -> None:
    # drawing-guidelines.md rule 10 (dimension from a real feature): the bend
    # tangent, the kink start and the wing locate from the pad hole's axis --
    # the screw that fixes the foot -- never from the model origin, so the
    # hole's own .XX location from the free end moves none of them (Codex P1
    # and machinist review r13, PR #1675).
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "KinkStartX" not in source and "FlatTipX" not in source
    for needle in (
        'dims.record(f"{prefix}HoleAxisX", \'"HoleFromEnd"\')',
        'dims.record(f"{prefix}FootLen", \'"BendFromHole"\')',
        'pad.record("PadHoleAxisX", \'"HoleFromEnd"\')',
        'pad.record("PadLen", \'"WingFromHole"\')',
        '"kink start from the hole axis"',
    ):
        assert source.count(needle) == 1, needle
    assert geometry.FOOT_FROM_HOLE == geometry.FOOT_LEN - geometry.HOLE_FROM_END
    assert geometry.FREE_KINK_H == pytest.approx(
        geometry.HOLE_X - geometry.FREE_KINK_START[0]
    )
    # Re-baselining moves no formed edge: the nominal contact is the one the
    # free-end baseline gave.
    assert geometry.HOLE_X - geometry.FOOT_FROM_HOLE == pytest.approx(
        geometry.FOOT_TAN[0]
    )
    free = dt_pinion_spring_spec.FORMED_DIMENSIONS[dt_pinion_spring_spec.FREE_FORM_SKETCH]
    assert free == {"FreeKinkH", "FreeKinkV", dt_pinion_spring_spec.FREE_KINK_ANGLE}
    assert set(drawing.DETAIL_KEEP) == {
        "KinkR",
        "FlatLen",
        dt_pinion_spring_spec.FREE_KINK_ANGLE,
    }
    assert drawing.DETAIL_SCALE == (5, 1)
    # Both views print the datum as a centreline on the hole's axis.
    for ends in (drawing.FRONT_HOLE_AXIS_ENDS, drawing.TOP_HOLE_AXIS_ENDS):
        assert {end[0] for end in ends} == {geometry.HOLE_X}
    # The 4.50's arrows inside: its outside tail ran west past the hole
    # axis, under the hole callout's leader (spring r15).
    assert drawing._DIM_ARROWS_INSIDE == 0


def test_pad_webs_clear_two_millimetres_at_the_printed_worst_case() -> None:
    radius = (geometry.HOLE_DIA + _HOLE_OVERSIZE) / 2.0
    across = geometry.PAD_WIDTH / 2.0  # hole from the pad's lower edge
    webs = geometry.pad_hole_webs()
    assert webs["near side"] == pytest.approx(across - _XX_BAND - radius, abs=0.01)
    assert webs["end"] == pytest.approx(
        geometry.HOLE_FROM_END - _XX_BAND - radius, abs=0.01
    )
    toward = {name: web for name, web in webs.items() if name.startswith("toward")}
    assert min(set(webs.values()) - set(toward.values())) >= _WEB_TARGET, webs
    # The bend's clearance leaves the web to the wing's corner under target
    # but over rule 17's 1.5 floor at .XX: printed on PadLen (rule 20),
    # rounded down.
    assert geometry.PAD_HOLE_WEB_MIN == pytest.approx(
        math.floor(min(toward.values()) / 0.0254) * 0.0254
    )
    assert geometry.PAD_HOLE_WEB_MIN == pytest.approx(0.076 * 25.4)
    assert WALL_FLOOR_MM <= geometry.PAD_HOLE_WEB_MIN < _WEB_TARGET
    assert drawing.DIMENSION_CALLOUTS["PadLen"] == "HOLE WEB .076 MIN"


def test_owner_exception_matches_only_the_stated_hole_web() -> None:
    (exception,) = load_exceptions(
        Path(geometry.__file__).parents[1] / "config", "dt_pinion_spring", "part"
    )
    assert (exception.id, exception.kind) == ("RV-01", "minor")
    assert dt_pinion_spring_spec.PAD_LEN_CALLOUT in exception.where
    assert ".076 in minimum" in exception.finding
    assert "PAD_HOLE_WEB_MIN" in exception.reason
    assert WALL_FLOOR_MM <= geometry.PAD_HOLE_WEB_MIN < _WEB_TARGET


def test_pad_wing_and_its_round_clear_the_bend_at_the_printed_worst_case() -> None:
    # Codex P1 (PR #1675): the wing at its longest, the round at its MAX and the
    # bend tangent at FootLen's low limit still leave the round's end short of
    # the bend -- both from the hole's axis, at the title-block .XX row (r13:
    # a tight .XXX band rescuing the web is not allowed, rules 4 and 17).
    assert geometry.PAD_LEN_PLACES == 2
    longest = geometry.PAD_WING_FROM_HOLE + _XX_BAND
    nearest_bend = geometry.FOOT_FROM_HOLE - geometry.FORMED_BAND_MM
    assert longest + geometry.PAD_RELIEF_R <= nearest_bend + 1e-9
    assert geometry.PAD_WING_FROM_HOLE == pytest.approx(0.15 * 25.4)
    assert geometry.PAD_WING_LEN == pytest.approx(0.33 * 25.4)
    # Positive control: from the free end, the hole's band would join the chain
    # and leave the web under the target.
    from_end = (
        geometry.FOOT_LEN
        - geometry.FORMED_BAND_MM
        - 2 * _XX_BAND
        - geometry.PAD_RELIEF_R
        - (geometry.HOLE_FROM_END + _XX_BAND)
        - (geometry.HOLE_DIA + _HOLE_OVERSIZE) / 2.0
    )
    assert from_end < _WEB_TARGET


def test_screw_head_still_bears_on_the_shortened_wing() -> None:
    from sh_vn_fillister_screw_90280a108_spec import HEAD_DIA

    # The pad's working contact is the MHA-SH-VN-52 foot screw's head clamping it;
    # past the strip's forward edge the head lands on the wing.  At the worst
    # case (wing short, the hole nearest the strip edge) the head's rim stays
    # well inside the wing's edge.
    head_r = HEAD_DIA / 2.0
    wing_short = geometry.PAD_WING_FROM_HOLE - _XX_BAND
    margin = wing_short - head_r
    assert margin == pytest.approx(1.232, abs=0.01)
    assert margin >= 0.5


def test_hole_callout_picks_the_hole_rim_where_the_pad_puts_it() -> None:
    # pc-r11 (0c5636eab): the callout picked z HOLE_DIA/2, the rim of a hole on
    # the strip's centre plane.  The pad stands PAD_Z off it, so the point fell
    # inside the hole and SelectByID2 found no edge.  The pick must lie on the
    # rim of the hole the Hole Wizard places at the pad's centre.
    centre = (geometry.HOLE_X, geometry.FOOT_Y, geometry.PAD_Z)
    assert drawing.HOLE_CENTER == pytest.approx(centre)
    x, y, z = drawing.HOLE_EDGE_PICK
    assert y == pytest.approx(centre[1])
    assert math.hypot(x - centre[0], z - centre[2]) == pytest.approx(
        geometry.HOLE_DIA / 2.0
    )
    # Positive control: the pc-r11 pick is nowhere near the rim.
    stale = abs(geometry.HOLE_DIA / 2.0 - centre[2])
    assert geometry.HOLE_DIA / 2.0 - stale > 1.0


def test_screw_stands_outboard_east_of_the_back_strap() -> None:
    # 2026-09-24 re-derive: img01's far-left screw is on the DRUM side (east).
    # The base's seat is transferred from this hole: it stands 20.0 east of
    # the pivot bore, the pad and the bend wholly east of the strap flank.
    assert geometry.HOLE_X - geometry.PIVOT_LX == pytest.approx(20.0)
    flank = geometry.PIVOT_LX + geometry.STRAP_HALF_WIDTH
    assert geometry.FOOT_END[0] > geometry.HOLE_X > geometry.FOOT_TAN[0] > flank
    assert geometry.FOOT_END[0] - geometry.HOLE_X == pytest.approx(geometry.HOLE_FROM_END)
    assert geometry.FOOT_LEN == geometry.PAD_LEN + geometry.FOOT_FLAT


def test_blade_leans_in_to_its_flank_contact() -> None:
    # img04: the crest bears on the east flank about 5 below the arbor; img01
    # reads the blade about 11-13 deg to the flank, leaning in from the foot.
    assert geometry.CONTACT_T == 23.0
    assert 9.0 <= geometry.BLADE_TO_FLANK_DEG <= 13.0
    assert geometry.BLADE_LEAN_DEG > 0.0  # west of vertical, toward the strap
    assert geometry.KINK_START[0] < geometry.BEND_EXIT[0]


def test_free_form_presets_the_crest_into_the_flank() -> None:
    # O2: the part is the installed shape; the maker forms the free shape,
    # whose crest stands PRESET into the parked flank.  The band's low end
    # still leaves a preset.
    assert geometry.PRESET - geometry.FORMED_BAND_MM > 1.0
    assert geometry.FREE_KINK_START[0] < geometry.KINK_START[0]
    assert dt_pinion_spring_spec.FORMED_TOLERANCE_MM == geometry.FORMED_BAND_MM


def test_free_form_prints_from_the_hidden_reference_sketch() -> None:
    # O2 (a): the installed solid plus the FreeForm phantom; the free crest
    # prints from the hidden sketch in the front view and the kink angle in
    # detail A, each through the opt-in hidden-sketch curation.
    assert dt_pinion_spring_spec.REFERENCE_SKETCHES == ("FreeForm",)
    build_source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "blank_sketch(adapter, FREE_FORM_SKETCH)" in build_source
    assert 'prefix="Free", construction=True' in build_source
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert draw_source.count("hidden_sketches.curate_view_dimensions(") == 2
    assert {"FreeKinkH", "FreeKinkV"} <= set(drawing.FRONT_KEEP)
    assert dt_pinion_spring_spec.FREE_KINK_ANGLE in drawing.DETAIL_KEEP
    assert "FREE FORM" in dt_pinion_spring_spec.DRAWING_NOTES


def test_front_qualifier_text_clears_its_rows_extension_lines() -> None:
    # pc-r12's render struck FREE, BEND and TANGENT through with the front
    # view's vertical extension lines: each qualified text now sits wholly
    # between or wholly outside the lines at its row.
    for name, lines in drawing.FRONT_ROW_EXTENSION_X.items():
        half = drawing.callout_half_width(name)
        x = drawing.FRONT_KEEP[name][0]
        crossed = [line for line in lines if x - half < line < x + half]
        assert not crossed, (name, crossed)
    rows = {"FootLen", "FreeKinkH", "FreeKinkV"}
    assert set(drawing.FRONT_ROW_EXTENSION_X) == rows
    # Positive control: pc-r12's centred kink-row text crossed both lines.
    old_x = drawing._front_x(drawing._FOOT_MID_X)
    half = drawing.QUALIFIER_HALF_WIDTH["FREE, TO KINK TANGENT"]
    assert all(
        old_x - half < line < old_x + half
        for line in drawing.FRONT_ROW_EXTENSION_X["FreeKinkH"]
    )


def _unit(v: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(*v)
    return (v[0] / length, v[1] / length)


def test_kink_angle_drives_the_flick_as_its_included_angle() -> None:
    # PR #1675 review r2: the tip's location from the free end less the kink
    # start's (two .X dimensions) let the flick read flat, reversed or sharply
    # kinked.  The kink's included angle, blade to flat, now drives both
    # profiles and prints on the free one, between its drawn legs in detail A.
    build_source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "TipH" not in build_source
    assert (
        build_source.count('dims.record(f"{prefix}KinkAngle", \'"KinkIncludedAngle"\')')
        == 1
    )
    assert (
        'set_global(adapter, "KinkIncludedAngle", f"{KINK_INCLUDED_DEG}deg")'
        in build_source
    )
    assert geometry.KINK_INCLUDED_DEG == pytest.approx(180.0 - geometry.KINK_DEG)
    for start, bend_exit, kink_exit, tip, vertex, bisector, included in (
        (
            geometry.KINK_START,
            geometry.BEND_EXIT,
            geometry.KINK_EXIT,
            geometry.FLAT_TIP,
            geometry.KINK_VERTEX,
            geometry.KINK_ANGLE_BISECTOR,
            geometry.KINK_INCLUDED_BISECTOR,
        ),
        (
            geometry.FREE_KINK_START,
            geometry.FREE_BEND_EXIT,
            geometry.FREE_KINK_EXIT,
            geometry.FREE_FLAT_TIP,
            geometry.FREE_KINK_VERTEX,
            geometry.FREE_KINK_ANGLE_BISECTOR,
            geometry.FREE_KINK_INCLUDED_BISECTOR,
        ),
    ):
        blade_down = _unit((bend_exit[0] - start[0], bend_exit[1] - start[1]))
        flat_down = _unit((kink_exit[0] - tip[0], kink_exit[1] - tip[1]))
        for point, direction in ((start, blade_down), (kink_exit, flat_down)):
            offset = (vertex[0] - point[0], vertex[1] - point[1])
            assert offset[0] * direction[1] - offset[1] * direction[0] == pytest.approx(
                0.0, abs=1e-9
            )
        dot = blade_down[0] * flat_down[0] + blade_down[1] * flat_down[1]
        assert math.degrees(math.acos(dot)) == pytest.approx(geometry.KINK_DEG)
        # The sketch's text point (where SOLIDWORKS read the included angle).
        assert bisector == pytest.approx(
            _unit((blade_down[0] + flat_down[0], blade_down[1] + flat_down[1]))
        )
        # The convex-side included wedge: between the blade's line carried up
        # and the flat's carried down, away from the crest.
        assert included == pytest.approx(
            _unit((flat_down[0] - blade_down[0], flat_down[1] - blade_down[1]))
        )
        towards_crest = (start[0] - vertex[0], start[1] - vertex[1])
        assert included[0] * towards_crest[0] + included[1] * towards_crest[1] < 0.0
    # Detail A's keep sits on the bisector of the wedge between the free
    # form's drawn legs (blade down, flat up), on the crest's concave side:
    # machinist review 69eda6e4c could not tell which legs the convex-side
    # arc on the 2:1 phantom measured.
    vertex = drawing._detail_xy(geometry.FREE_KINK_VERTEX)
    keep = drawing.DETAIL_KEEP[dt_pinion_spring_spec.FREE_KINK_ANGLE]
    assert math.dist(keep, vertex) == pytest.approx(drawing.KINK_ANGLE_TEXT_RADIUS)
    assert drawing.KINK_ARC_BISECTOR == pytest.approx(
        tuple(-v for v in geometry.FREE_KINK_INCLUDED_BISECTOR)
    )
    assert keep[0] > vertex[0] + 0.010
    # Its arc ends on the drawn flat, so no extension line runs off a leg.
    low, high = drawing.KINK_ARC_RADIUS_RANGE
    assert low < drawing.KINK_ANGLE_TEXT_RADIUS < high
    assert dt_pinion_spring_spec.FREE_KINK_ANGLE not in drawing.FRONT_KEEP
    assert dt_pinion_spring_spec.FREE_KINK_ANGLE not in drawing.DIMENSION_CALLOUTS


def _arc(vertex, about_deg: float, half_deg: float, radius: float = 0.012):
    bisector_x, bisector_y = drawing.KINK_ARC_BISECTOR
    bisector = math.degrees(math.atan2(bisector_y, bisector_x))
    points = []
    for step in range(11):
        angle = math.radians(bisector + about_deg - half_deg + step * half_deg / 5.0)
        x, y = math.cos(angle), math.sin(angle)
        points.append((vertex[0] + radius * x, vertex[1] + radius * y))
    return [(vertex, points)]


def test_kink_arc_faults_reads_the_wedge_the_arc_sweeps() -> None:
    vertex = (0.087, 0.152)
    half = geometry.KINK_INCLUDED_DEG / 2
    acute = geometry.KINK_DEG / 2
    assert drawing.kink_arc_faults(_arc(vertex, 0.0, half), vertex) == []
    # Positive controls: either acute wedge, the opposite included wedge, an
    # arc about another centre, and no arc.
    assert drawing.kink_arc_faults(_arc(vertex, 90.0, acute), vertex)
    assert drawing.kink_arc_faults(_arc(vertex, -90.0, acute), vertex)
    assert drawing.kink_arc_faults(_arc(vertex, 180.0, half), vertex)
    shifted = (vertex[0] + 0.002, vertex[1])
    assert drawing.kink_arc_faults(_arc(shifted, 0.0, half), vertex)
    assert drawing.kink_arc_faults([], vertex) == ["no arc"]
    # An arc past the flat's tip (or short of its start) needs an extension
    # line off the drawn leg.
    high = drawing.KINK_ARC_RADIUS_RANGE[1]
    assert drawing.kink_arc_faults(_arc(vertex, 0.0, half, radius=high + 0.001), vertex)
    low = drawing.KINK_ARC_RADIUS_RANGE[0]
    assert drawing.kink_arc_faults(_arc(vertex, 0.0, half, radius=low - 0.001), vertex)
    # The r10 leaf's arcs as imported: the legs' own wedge plus an extension
    # arc out to text on the convex side.
    centre = (0.08715684620887239, 0.15211975644463)
    blade_down = (0.0890486683798352, 0.14028129645639575)
    flat_up = (0.09044542242555458, 0.16364856351590332)
    text_side = (0.0753884200079658, 0.1498323407033654)
    r10 = [
        (centre, drawing.minor_arc_points(centre, blade_down, flat_up)),
        (centre, drawing.minor_arc_points(centre, text_side, blade_down)),
    ]
    assert drawing.kink_arc_faults(r10, centre)
    # Its legs' arc alone is the wedge this print asks for.
    assert drawing.kink_arc_faults(r10[:1], centre) == []


def test_minor_arc_points_sweep_the_short_way_either_sense() -> None:
    # The legs' wedge's 155 deg arc, given end-first or start-first, reads
    # inside the wedge: the arc's sense flag is not consulted.
    vertex = (0.087, 0.152)
    half = geometry.KINK_INCLUDED_DEG / 2
    ((_, points),) = _arc(vertex, 0.0, half)
    for start, end in ((points[0], points[-1]), (points[-1], points[0])):
        arc = [(vertex, drawing.minor_arc_points(vertex, start, end))]
        assert drawing.kink_arc_faults(arc, vertex) == []
        swept = arc[0][1]
        assert swept[0] == pytest.approx(start)
        assert swept[-1] == pytest.approx(end)
    # The opposite included wedge stays opposite.
    ((_, across),) = _arc(vertex, 180.0, half)
    arc = [(vertex, drawing.minor_arc_points(vertex, across[0], across[-1]))]
    assert drawing.kink_arc_faults(arc, vertex)


class _KinkView:
    """A recording IView double for the kink detail's place-move-crop."""

    def __init__(self, *, crop_status: int = 1, crops: bool = True, moves: bool = True):
        self.ScaleRatio = (5.0, 1.0)
        self.Position = (0.300, 0.100)
        self.crop_status = crop_status
        self.crops = crops
        self.moves = moves
        self.cropped = False
        self.calls: list[str] = []
        self.CropViewJaggedOutline = False
        self.CropViewNoOutline = False

    def SetViewPosition(self, target, _update) -> bool:  # noqa: N802
        self.calls.append("SetViewPosition")
        if self.moves:
            self.Position = tuple(float(value) for value in target)
        return True

    def GetOutline(self):  # noqa: N802
        if self.cropped:
            return (0.2225, 0.1665, 0.2575, 0.2015)
        return (0.180, 0.050, 0.300, 0.290)

    def Crop2(self, jagged, no_outline, intensity) -> int:  # noqa: N802
        self.calls.append(f"Crop2({jagged}, {no_outline}, {intensity})")
        self.cropped = self.crops
        return self.crop_status

    def IsCropped(self) -> bool:  # noqa: N802
        return self.cropped

    def UpdateViewDisplayGeometry(self) -> None:  # noqa: N802
        self.calls.append("UpdateViewDisplayGeometry")


class _KinkModel:
    def ClearSelection2(self, _all) -> None:  # noqa: N802
        pass

    def EditRebuild3(self) -> None:  # noqa: N802
        pass


def _kink_seat(monkeypatch, view: _KinkView) -> list[tuple]:
    """Point draw_pinion_spring's COM helpers at ``view``; returns the log of
    placements and crop circles."""
    log: list[tuple] = []
    # The focus sits a fixed sheet offset from the view's position.
    offset = (-0.050, 0.070)

    def place(_adapter, source, orientation, x, y, *, scale):
        log.append(("place", orientation, (x, y), scale))
        return view

    def model_point(_adapter, _view, point, *, label):
        assert point[:2] == pytest.approx(
            (drawing.DETAIL_FOCUS[0] / 1000.0, drawing.DETAIL_FOCUS[1] / 1000.0)
        )
        return (view.Position[0] + offset[0], view.Position[1] + offset[1])

    def circle(_adapter, _view, center, radius, *, label, add_to_db=False):
        log.append(("circle", center, radius, add_to_db))
        return object()

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "model_point_in_view", model_point)
    monkeypatch.setattr(drawing, "_sketch_circle", circle)
    monkeypatch.setattr(drawing, "_activate_view", lambda *_a, **_k: "Drawing View4")
    return log


def _kink_adapter():
    return type("Adapter", (), {"currentModel": _KinkModel()})()


def _crop_kink(adapter, monkeypatch, view: _KinkView) -> list[tuple]:
    log = _kink_seat(monkeypatch, view)
    assert drawing._placed_kink_view(adapter) is view
    drawing._crop_kink_view(adapter, view)
    return log


def test_kink_detail_is_a_cropped_front_model_view(monkeypatch) -> None:
    # pc-r13 (leaf 20260927T001822Z-1-ba1f4546): the native detail's
    # targeted import brought KinkR but not FlatLen.  Detail A is now a *Front
    # model view at 5:1, its kink focus moved onto DETAIL_CENTER, cropped by
    # the fence's 5:1 circle with a plain circular outline.
    view = _KinkView()
    log = _crop_kink(_kink_adapter(), monkeypatch, view)
    assert log[0] == ("place", "*Front", drawing.DETAIL_CENTER, drawing.DETAIL_SCALE)
    kind, center, radius, add_to_db = log[1]
    assert kind == "circle" and not add_to_db
    assert center == pytest.approx(drawing.DETAIL_CENTER, abs=1e-12)
    assert radius == pytest.approx(5 * drawing.DETAIL_RADIUS_MM / 1000.0)
    assert view.calls[0] == "SetViewPosition"
    assert "Crop2(False, False, 1)" in view.calls
    assert not hasattr(drawing, "_kink_detail")
    assert "CreateDetailViewAt4" not in Path(drawing.__file__).read_text(encoding="utf-8")


class _Annotation:
    def __init__(self, name: str) -> None:
        self.name = name


class _DimensionedView:
    def __init__(self) -> None:
        self.names: list[str] = []

    def GetAnnotations(self):  # noqa: N802
        return [_Annotation(name) for name in self.names]


def _order_seat(monkeypatch, view: _DimensionedView, *, crop_drops: tuple[str, ...]):
    """Record import, read-back and crop order on ``view``; the crop drops
    ``crop_drops`` from it.  Returns the call log and the recorded events."""
    calls: list[str] = []
    events: list[tuple[str, dict]] = []

    def curate(_adapter, _view, *, keep, view_label, dimensions_by_feature):
        calls.append("import")
        view.names = sorted(keep)
        return ["curated"]

    def crop(_adapter, _view):
        calls.append("crop")
        view.names = [name for name in view.names if name not in crop_drops]

    def names(_adapter, _view):
        calls.append("read")
        return sorted(view.names)

    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_crop_kink_view", crop)
    monkeypatch.setattr(drawing, "_view_dimension_names", names)
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    return calls, events


def test_kink_detail_is_dimensioned_before_it_is_cropped(monkeypatch) -> None:
    # pc-r14 (6aebefd18, leaf 20260927T005429Z-1-555a9662): imported into the
    # cropped view, SpringProfile brought FlatLen but not KinkR; the uncropped
    # *Front imports both.  The detail imports while uncropped, then crops,
    # and the pair is read back on both sides of the crop.
    view = _DimensionedView()
    calls, events = _order_seat(monkeypatch, view, crop_drops=())
    assert drawing._dimension_then_crop_kink_view(object(), view) == ["curated"]
    assert calls == ["import", "read", "crop", "read"]
    assert events == [
        (
            "kink_detail.crop",
            {
                "dimensions_before": "FlatLen,FreeKinkAngle,KinkR",
                "dimensions_after": "FlatLen,FreeKinkAngle,KinkR",
                "lost": "",
            },
        )
    ]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert body.index("_placed_kink_view(adapter)") < body.index(
        "_dimension_then_crop_kink_view(adapter, detail)"
    ) < body.index("keep=FRONT_KEEP")


def test_kink_detail_fails_loud_when_the_crop_takes_a_dimension(monkeypatch) -> None:
    view = _DimensionedView()
    calls, events = _order_seat(monkeypatch, view, crop_drops=("KinkR",))
    with pytest.raises(RuntimeError, match=r"lost \['KinkR'\] to its crop"):
        drawing._dimension_then_crop_kink_view(object(), view)
    assert events[0][1]["lost"] == "KinkR"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"crop_status": 0}, "not cropped"),
        ({"crops": False}, "not cropped"),
        ({"moves": False}, "kink focus sits at"),
    ],
)
def test_kink_detail_fails_loud_when_the_seat_does_not_obey(
    monkeypatch, kwargs, message
) -> None:
    view = _KinkView(**kwargs)
    with pytest.raises(RuntimeError, match=message):
        _crop_kink(_kink_adapter(), monkeypatch, view)


def test_kink_crop_holds_its_dimensions_and_labels_clear_of_them() -> None:
    # The fence takes both crests: the phantom free crest with its angle's
    # arc ends on the drawn legs and the installed crest with its centre and
    # its flat's tip.
    focus = drawing.DETAIL_FOCUS
    radius = drawing.DETAIL_RADIUS_MM
    vertex = geometry.FREE_KINK_VERTEX
    arc_mm = drawing.KINK_ANGLE_TEXT_RADIUS * 1000.0 / drawing.DETAIL_RATIO
    legs_down_up = [
        math.atan2(point[1] - vertex[1], point[0] - vertex[0])
        for point in (geometry.FREE_BEND_EXIT, geometry.FREE_FLAT_TIP)
    ]
    arc_ends = [
        (vertex[0] + arc_mm * math.cos(a), vertex[1] + arc_mm * math.sin(a))
        for a in legs_down_up
    ]
    for point in (
        geometry.FLAT_TIP,
        geometry.KINK_C,
        vertex,
        geometry.FREE_FLAT_TIP,
        *arc_ends,
    ):
        assert math.dist(point, focus) < radius, point
    crop_bottom = drawing.DETAIL_CENTER[1] - drawing.DETAIL_CROP_RADIUS
    assert drawing.DETAIL_LABEL_XY[0] == drawing.DETAIL_CENTER[0]
    assert drawing.DETAIL_LABEL_XY[1] < crop_bottom
    assert drawing.DETAIL_LABEL_TEXT == "DETAIL A\nSCALE 5 : 1"
    # KinkR rides above-left of the circle, FlatLen right of it: neither
    # reaches down to the label.
    for name in ("KinkR", "FlatLen", dt_pinion_spring_spec.FREE_KINK_ANGLE):
        assert drawing.DETAIL_KEEP[name][1] > drawing.DETAIL_LABEL_XY[1]
    # The fence letter goes east of the front view's fence, off the phantom.
    assert drawing.PARENT_LETTER_OFFSET[0] > drawing.DETAIL_RADIUS_MM * drawing._S
    # ...and 2 mm west of the hole axis's extension line up to FreeKinkH's row.
    focus = drawing._front_x(drawing.DETAIL_FOCUS[0])
    letter_east = focus + drawing.PARENT_LETTER_OFFSET[0] + 0.0015  # half an "A"
    assert drawing._HOLE_AXIS_X - letter_east >= 0.002


def test_views_are_projected_and_hidden_lines_removed() -> None:
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] > drawing.FRONT_CENTER[1]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hidden_lines_visible" not in source
    assert "add_feature_control_frame" not in source
    assert "add_datum_feature" not in source
    assert "process=HOLE_PROCESS" in source
    assert drawing.HOLE_PROCESS == "#30 DRILL"
    assert geometry.HOLE_DIA == pytest.approx(0.1285 * 25.4, abs=1e-3)  # No. 30 drill
    assert source.count("add_edge_dimension(") == 1  # the blank's driven dimensions


def test_bend_coupon_qualifies_the_tightest_accepted_radius() -> None:
    # Codex #859 (PRRT_kwDOPHDy386mTao0): both R3.3 bends may be formed at
    # R3.3 - band, so the mandatory coupon bends over that low limit or under
    # it, never the nominal.  The mandrel is a 7/32 in drill rod.
    policy = (Path(__file__).parents[1] / "docs" / "tolerance-policy.md").read_text(
        encoding="utf-8"
    )
    mandrel_r = 7.0 / 32.0 * 25.4 / 2.0
    assert "7/32 in (Ø5.56) drill-rod mandrel, R2.78" in policy
    assert round(mandrel_r, 2) == 2.78
    low_limit = min(geometry.R_BEND, geometry.R_KINK) - geometry.FORMED_BAND_MM
    assert mandrel_r <= low_limit
    # Positive control: the nominal R3.3 mandrel the coupon used to name misses it.
    assert geometry.MIN_INSIDE_BEND_R > low_limit


def test_notes_carry_no_dimension_and_stay_short() -> None:
    notes = dt_pinion_spring_spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert "FORM" in notes
    assert "COIL" not in notes
    # The blank's orientation is the coupon's (Codex #859, PRRT_kwDOPHDy386mTtoA).
    assert "ALONG ROLL LENGTH (BENDS ACROSS ROLLING DIRECTION)" in notes
    policy = (Path(__file__).parents[1] / "docs" / "tolerance-policy.md").read_text(
        encoding="utf-8"
    )
    assert "bend line across the rolling direction, as the part is cut" in policy
    assert max(len(line) for line in notes.splitlines()) <= 63
    assert not any(ch.isdigit() for ch in notes)
    assert "+/-" not in "\n".join(drawing.DIMENSION_CALLOUTS.values())


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    spec = _config.parts("dt-pinion-spring")
    # The title-block cell holds one line (<= 30 characters); the full
    # stock callout stays in the material specification.
    assert len(spec["material"]) <= 30
    assert "17-7 PH" in spec["material"] and "Cond C" in spec["material"]
    assert "0.015 in +/-0.00075 in" in spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1


def test_registry_names_the_stock_the_section_models() -> None:
    # #859 ruling 4: 17-7 PH Condition C, 0.015 in, McMaster-Carr 2325K19
    # (+/-0.00075 in on the vendor page), sheared 1/4 in wide.  The width is a
    # sheared, .XX-printed dimension, so its band is the title block's.
    spec = _config.parts("dt-pinion-spring")["material_specification"]
    assert "McMaster-Carr 2325K19" in spec and "ASTM A693" in spec
    assert "Condition C" in spec and "+/-0.00075 in" in spec
    assert section.THICK == pytest.approx(0.015 * 25.4)
    assert section.THICK_BAND == pytest.approx((0.00075 * 25.4, -0.00075 * 25.4))
    assert section.WIDTH == pytest.approx(0.25 * 25.4)
    assert printed_deviations(
        section.WIDTH, section.WIDTH_PLACES, unit=section.UNIT
    ) == pytest.approx(
        (-_XX_BAND, _XX_BAND), abs=0.005
    )
    assert spring.MATERIAL == "AISI 304"  # the library's stainless stand-in


def test_every_inside_radius_meets_the_17_7_ph_bend_minimum() -> None:
    # No 17-7 PH source publishes a Condition C bend radius; the proxy is NASA
    # SP-5089 (1968) Table XXXI, 17-7 PH (STA) 0.012-0.016 in: R 0.13 in.
    # Condition C is less ductile than STA, so the bend trial is still due
    # (cad/docs/tolerance-policy.md).
    proxy = 0.13 * 25.4
    assert min(geometry.R_BEND, geometry.R_KINK) >= proxy - 1e-9
    assert geometry.MIN_INSIDE_BEND_R == pytest.approx(proxy)
    # The larger bend keeps the blade inside O5's 9-13 deg only with the bend
    # starting at the pad's edge.
    assert geometry.FOOT_FLAT == 0.0
