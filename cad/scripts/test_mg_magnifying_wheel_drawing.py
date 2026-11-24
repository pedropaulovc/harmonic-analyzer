"""Offline contracts for the magnifying-wheel drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_mg_magnifying_wheel as part
import draw_mg_magnifying_wheel as drawing
import sh_vn_music_wire_lever_geom
import mg_magnifying_wheel_geom as geom
import _mg_wheel_rim_geometry as rim
import mg_magnifying_wheel_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-wheel.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-wheel.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-wheel_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_wheel"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is mg_magnifying_wheel_spec.DRAWING_DIMENSIONS
    marked = set().union(*mg_magnifying_wheel_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.SECTION_KEEP)
        | set(drawing.SECTION_DIAMETER_KEEP)
        | set(drawing.TIE1_SECTION_TEXT_MM)
    )
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.SECTION_KEEP)
    # TIE 1's counter-drill prints on B-B alone, from its own profile.
    assert set(drawing.TIE1_SECTION_TEXT_MM) == set(
        mg_magnifying_wheel_spec.DRAWING_DIMENSIONS["Tie1CdrillProfile"]
    )
    assert not set(drawing.TIE1_SECTION_TEXT_MM) & (
        set(drawing.FRONT_KEEP) | set(drawing.SECTION_KEEP)
    )
    # The rim's Ø and the spokes' back face print on A-A from the hidden
    # reference sketch alone.
    assert set(drawing.SECTION_DIAMETER_KEEP) == set(
        mg_magnifying_wheel_spec.DRAWING_DIMENSIONS[
            mg_magnifying_wheel_spec.DIAMETER_REFERENCE
        ]
    )
    assert not set(drawing.SECTION_DIAMETER_KEEP) & (
        set(drawing.FRONT_KEEP) | set(drawing.SECTION_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS) | set(drawing.CALLOUTS_ABOVE) <= kept


def test_every_marked_dimension_has_model_places() -> None:
    spec = mg_magnifying_wheel_spec
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        name: digits
        for names in spec.DRAWING_PRECISION.values()
        for name, digits in names.items()
    }
    # The spigot and the bore are matched fits: a reference nominal, the
    # acceptance on the callout.  The web's plane, cast, prints .61 +/-.03.
    assert spec.REFERENCE_DIMENSIONS == {"SpigotDia", "BoreDiaDim"}
    print_shift = 0.03 * 25.4 + abs(-0.61 * 25.4 - geom.HUB_FRONT_Z)
    route_gaps = sh_vn_music_wire_lever_geom.run_gaps(
        sh_vn_music_wire_lever_geom.WIRE_START, sh_vn_music_wire_lever_geom.WIRE_END
    )
    expected_gap = min(route_gaps["rim"], route_gaps["spokes"]) - print_shift
    assert spec.LEVER_WIRE_WEB_GAP == pytest.approx(expected_gap, abs=1e-9)
    assert spec.LEVER_WIRE_WEB_GAP >= sh_vn_music_wire_lever_geom.CLEARANCE


def test_tight_bands_sit_on_the_model_dimensions() -> None:
    # The boss Ø and TIE 1's two coordinates ride the title block's .XX: the
    # boss is sized for TIE 1's wall, so none carries a band of its own.
    assert model_toleranced_dimensions(part) == {
        ("feature_name", "dimension_name"): "CAST_TOL",
    }
    # The as-cast sizes carry the explicit +/-.03 casting band.
    assert geom.CAST_TOL == pytest.approx(0.03 * 25.4)
    precision = mg_magnifying_wheel_spec.DRAWING_PRECISION
    assert precision["HubProfile"]["HubDia"] == 2
    tie1 = precision["Tie1Profile"]
    assert tie1["Tie1X"] == tie1["Tie1Y"] == 2


def test_walls_and_groove_hold_at_the_printed_bands() -> None:
    spec = mg_magnifying_wheel_spec
    inch = 25.4
    # Every wall holds rule 17's .080 in target at the printed limits.
    assert min(spec.WALLS.values()) >= spec.MIN_WALL - 1e-9
    assert spec.MIN_WALL == pytest.approx(0.080 * inch)
    # TIE 1's axis may stand off by both .XX coordinates' +/-.01, and tilt by
    # the title block's 1 deg plus 0.3 deg drill wander over the boss (the
    # hub's .776 max less the spigot's .XXX min).
    offset = math.hypot(0.01 * inch, 0.01 * inch) + (
        geom.HUB_LEN_LIMITS[1] - geom.SPIGOT_LEN_LIMITS[0]
    ) * math.tan(math.radians(1.3))
    assert geom.TIE1_OFFSET_MAX == pytest.approx(offset)
    tie1_r = math.hypot(0.38, 0.22) * inch
    assert geom.TIE1_R == pytest.approx(tie1_r)
    # TIE 1's walls take its #50 counter-drill (Ø.070) at the title block's
    # drilled row, +.004: it runs from the boss front face past the spokes'
    # plane, so it is TIE 1's widest Ø at the boss OD, the fillets and the bore.
    tie1_r_max = (0.070 + 0.004) * inch / 2.0
    assert spec.WALLS["tie1_to_hub_od"] == pytest.approx(
        (1.18 - 0.01) * inch / 2.0 - (tie1_r + offset) - tie1_r_max
    )
    assert spec.WALLS["tie1_to_hub_od"] == pytest.approx(0.0851 * inch, abs=1e-4 * inch)
    assert spec.WALLS["tie1_to_bore"] == pytest.approx(
        tie1_r - offset - tie1_r_max - mg_magnifying_wheel_spec.WHEEL_BORE_MAX / 2.0
    )
    # The cast spokes, fillets and rim bore at their +/-.03 casting band.
    assert spec.WALLS["tie2_to_rim_fillet"] == pytest.approx(2.6006, abs=1e-3)
    assert spec.WALLS["tie1_to_hub_fillet"] >= spec.MIN_WALL
    # TIE 1 stands outboard of the drum it sits behind: its smallest
    # drum-side mouth, the #50, at its worst offset, still opens a wire
    # diameter past the largest printed drum, whatever the drum's O.D.
    drum_r_max = (geom.DRUM_OD + geom.DRUM_OD_DEVIATIONS[1]) / 2.0
    assert geom.TIE1_DRUM_OPENING == pytest.approx(
        tie1_r - offset + 0.035 * inch - drum_r_max
    )
    assert geom.TIE1_DRUM_OPENING >= geom.LEVER_WIRE_DIA
    # 8 o'clock seen from the front, midway between two spokes.
    assert geom.TIE1_CLOCK_DEG == pytest.approx(-150.0, abs=0.1)
    # TIE 2 breaks into the bore at mid-width: its ligament ends at the
    # rim-bore rounds, R.03 MAX (no model band), on a rim .31 wide at .XX.
    assert spec.WALLS["tie2_to_rim_faces"] == pytest.approx(2.4599, abs=1e-3)
    assert geom.CAST_ROUND_R == pytest.approx(0.03 * inch)
    assert not hasattr(geom, "CAST_ROUND_BAND")
    assert spec.ROUND_TEXT_SUFFIX == " MAX"
    # The fits' worst pair: the smallest spigot (.500 drilled drum bore less
    # the .0025 bond clearance) over the largest bore (.1877 pin + .0017).
    assert spec.WALLS["spigot_to_bore"] == pytest.approx((0.4975 - 0.1894) * inch / 2.0)
    assert "RimRounds" not in spec.DRAWING_DIMENSIONS
    assert geom.TIE2_CLOCK_DEG == -43.0
    # The Ø.008 pen wire seats at every printed groove corner: the narrowest
    # groove (R at its .XXX min) is wider than the wire, and the shallowest
    # (the .XX rim at its min over the .XXX bottom at its max) still buries it.
    assert spec.GROOVE_WIDTH_MIN == pytest.approx(0.038 * inch)
    assert spec.GROOVE_DEPTH_MIN == pytest.approx((3.93 - 3.871) * inch / 2.0)
    assert spec.GROOVE_WIDTH_MIN > rim.PEN_WIRE_DIA
    assert spec.GROOVE_DEPTH_MIN >= rim.PEN_WIRE_DIA
    # The drum is never proud of the spigot face: .000-.020 below it.
    assert geom.DRUM_RECESS == pytest.approx((0.0, 0.020 * inch))


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hub stations the assembly imports live in the drawing-FREE geom
    # module, so a print-note edit cannot enter the assembly recipe.
    assert (rim.RIM_OUTER_DIA, geom.HUB_DIA, geom.SPOKE_COUNT) == (100.0, 30.0, 6)


def test_feature_volumes_are_consistent() -> None:
    # The fillet gates sum to the geom's own fillet volume; the groove matches
    # a direct section integral; TIE 2 is a #60 hole a little over the floor wall.
    assert part.V_HUB_FILLETS + part.V_RIM_FILLETS == pytest.approx(
        geom.fillets_volume()
    )
    floor = rim.GROOVE_BOTTOM_DIA / 2.0 - rim.RIM_INNER_DIA / 2.0
    hole = 3.141592653589793 / 4.0 * geom.TIE_HOLE_DIA**2
    assert hole * floor < part.V_TIE2 < hole * (floor + 2.0 * rim.GROOVE_R)
    assert part.V_GROOVE == pytest.approx(292.88, abs=0.05)
    assert part.V_SPOKE_FREE > part.V_SPOKE_WEB > 0.0


def test_tie1_counter_drill_leaves_a_short_60_at_the_back_face() -> None:
    # Owner ruling on #2406 (A): #50 (.070) from the drum face, leaving about
    # .10 of #60 (2.5 x D) at the back face, not the whole .417 boss.
    inch = 25.4
    boss = geom.HUB_BACK_Z - geom.HUB_STEP_Z
    assert geom.TIE1_CDRILL_DIA == pytest.approx(0.070 * inch)
    assert (boss - geom.TIE1_CDRILL_DEPTH) / inch == pytest.approx(0.10, abs=0.005)
    assert (boss - geom.TIE1_CDRILL_DEPTH) / geom.TIE_HOLE_DIA < 2.6
    # The depth's only function is that land, so it prints at the title
    # block's .XX: its model value is exact at two places.
    assert geom.TIE1_CDRILL_DEPTH_PLACES == 2
    assert round(geom.TIE1_CDRILL_DEPTH / inch, 2) * inch == pytest.approx(
        geom.TIE1_CDRILL_DEPTH
    )
    # At the shortest printed boss, the deepest printed shoulder (+.01) and
    # the largest drilled #50's 118 deg point, full #60 is still left.
    point = (0.070 + 0.004 - 0.040) * inch / 2.0 / math.tan(math.radians(59.0))
    boss_min = geom.HUB_LEN_LIMITS[0] - geom.SPIGOT_LEN_LIMITS[1]
    assert geom.TIE1_LAND_MIN == pytest.approx(
        boss_min - geom.TIE1_CDRILL_DEPTH - 0.01 * inch - point
    )
    assert geom.TIE1_LAND_MIN > 0.0
    # The shallowest printed shoulder (-.01) still stands past the spokes'
    # front face, so the #50 is the Ø the boss walls are judged on.
    assert (
        geom.HUB_STEP_Z + geom.TIE1_CDRILL_DEPTH - 0.01 * inch
        > -mg_magnifying_wheel_spec.SPOKE_AXIAL / 2.0
    )


def test_tie1_volume_gates_prove_the_counter_drill_and_its_point() -> None:
    # The #60 through the boss, then the #50 with its 118 deg point beyond
    # the #60's air: together the union integrated along TIE 1's axis.
    r60, r50 = geom.TIE_HOLE_DIA / 2.0, geom.TIE1_CDRILL_DIA / 2.0
    boss = geom.HUB_BACK_Z - geom.HUB_STEP_Z
    depth = geom.TIE1_CDRILL_DEPTH
    assert part.V_TIE1 == pytest.approx(math.pi * r60**2 * boss)
    k = 1.0 / math.tan(math.radians(59.0))
    steps = 200000
    dz = (depth + r50 * k) / steps
    removed = math.pi * r60**2 * (boss - depth - r50 * k)
    for i in range(steps):
        z = (i + 0.5) * dz
        r = r50 if z <= depth else r50 - (z - depth) / k
        removed += math.pi * max(r, r60) ** 2 * dz
    assert part.V_TIE1 + part.V_TIE1_CDRILL == pytest.approx(removed, rel=1e-6)
    # The counter-drill's gate band is half its point: a flat-bottomed #50
    # misses the gate.
    flat = math.pi * (r50**2 - r60**2) * depth
    assert part.V_TIE1_CDRILL - flat == pytest.approx(part.V_TIE1_POINT)
    assert part.V_TIE1_POINT > 0.0


def test_tie1_section_b_b_cuts_through_tie1_clear_of_the_spigot() -> None:
    # B-B runs along TIE 1's row (the counter-drill profile's plane, y =
    # TIE1_Y), from just outside the spigot out past the boss's O.D. into
    # the spoke window, so it crosses the hole whole and cuts the boss alone.
    (x0, y0), (x1, y1) = drawing.TIE1_SECTION_LINE_MM
    r50 = geom.TIE1_CDRILL_DIA / 2.0
    assert y0 == y1 == geom.TIE1_Y
    assert x0 < geom.TIE1_X - r50 < geom.TIE1_X + r50 < x1
    assert x1 > mg_magnifying_wheel_spec.HUB_DIA / 2.0
    assert math.hypot(x0, y0) > mg_magnifying_wheel_spec.SPIGOT_DIA / 2.0
    # The bore-side arrow prints at that end, down the 270 deg window: its
    # 3 mm head and its letter clear TIE 1's #50.
    assert geom.TIE1_X - r50 - (x0 + 2.3) > 0.5
    # Its far end stands in air between the 0 and 300 deg spokes' fillets.
    bearing = math.degrees(math.atan2(y1, x1))
    assert -mg_magnifying_wheel_spec.SPOKE_PITCH_DEG < bearing < 0.0
    # Drawn left to right on the sheet, whichever order the ends come in.
    assert drawing.tie1_section_line_ends(((0.3, 0.2), (0.1, 0.2))) == (
        (0.1, 0.2),
        (0.3, 0.2),
    )
    # The counter-drill's Ø reads the whole callout: size, process, depth REF.
    assert drawing.TIE1_SECTION_SUFFIX == " #50 DRILL <HOLE-DEPTH> (.32)"
    assert drawing.TIE1_CALLOUT.splitlines()[1] == (
        "<MOD-DIAM>.070 #50 DRILL <HOLE-DEPTH> .32 FAR SIDE"
    )
    precision = mg_magnifying_wheel_spec.DRAWING_PRECISION["Tie1CdrillProfile"]
    assert precision == {"Tie1CdrillDia": 3, "Tie1CdrillDepth": 2}
    assert drawing.TIE1_SECTION_SCALE == (2, 1)


def test_tie2_profile_runs_radially_and_ends_in_air() -> None:
    p_in, p_out, q_out, q_in = part._tie2_profile()
    cross = p_in[0] * p_out[1] - p_in[1] * p_out[0]
    assert cross == pytest.approx(0.0, abs=1e-9)  # the axis passes the origin
    assert q_in[1] == pytest.approx(p_in[1])  # the inner end runs horizontal
    assert (p_out[0] ** 2 + p_out[1] ** 2) ** 0.5 > rim.GROOVE_BOTTOM_DIA / 2.0
    assert (q_out[0] ** 2 + q_out[1] ** 2) ** 0.5 < rim.RIM_OUTER_DIA / 2.0
    # The spoke reference's Tie2Clock stub lies on this axis.
    axis = math.degrees(math.atan2(p_out[1] - p_in[1], p_out[0] - p_in[0]))
    spec = mg_magnifying_wheel_spec
    clock = spec.TIE2_CLOCK_SPOKE * spec.SPOKE_PITCH_DEG + spec.TIE2_FROM_SPOKE_DEG
    assert axis % 360.0 == pytest.approx(clock % 360.0)


def _inside(polygon: list[tuple[float, float]], point: tuple[float, float]) -> bool:
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _distance(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def test_tie2_window_shows_the_hole_and_keeps_hatch_off_the_angle_leg() -> None:
    window = [drawing.tie2_window_point(s, t) for s, t in drawing.TIE2_WINDOW]
    tie_r = mg_magnifying_wheel_spec.TIE_HOLE_DIA / 2.0
    # Both cut walls, rim bore to groove bottom, lie inside the window.
    for r in (rim.RIM_INNER_DIA / 2.0, rim.GROOVE_BOTTOM_DIA / 2.0):
        along = math.sqrt(r * r - tie_r * tie_r)
        for across in (-tie_r, tie_r):
            assert _inside(window, drawing.tie2_window_point(along, across))
    # The angle's horizontal leg leaves the axis's inner end toward the
    # 180 deg side and stays clear of the window up to the rim's far wall.
    x0, y = part._tie2_profile()[0]
    x1 = -math.sqrt((rim.GROOVE_BOTTOM_DIA / 2.0) ** 2 - y * y)
    edges = list(zip(window, window[1:] + window[:1]))
    for k in range(101):
        point = (x0 + (x1 - x0) * k / 100.0, y)
        assert not _inside(window, point)
        assert min(_distance(point, a, b) for a, b in edges) > 0.4


@pytest.mark.parametrize(
    ("circle_r", "printed", "fillet_name"),
    [
        ("_HUB_R", "HUB_FILLET_PRINTED", "_HUB_FILLET"),
        ("_RIM_IN_R", "RIM_FILLET_PRINTED", "_RIM_FILLET"),
    ],
)
def test_each_fillet_r_prints_on_the_builders_first_pick(
    circle_r: str, printed: str, fillet_name: str
) -> None:
    # The imported R lands on the first pick's edge, so the drawing's landing
    # proof must target the fillet the builder picks first.
    picks = part._spoke_edge_picks(
        getattr(part, circle_r), getattr(mg_magnifying_wheel_spec, printed)
    )
    centre = getattr(drawing, fillet_name)[0]
    gaps = [math.dist(pick[:2], centre) for pick in picks]
    assert len(picks) == 12 and min(gaps) == gaps[0]


def test_linked_notes_specify_the_fits_the_ties_and_the_angle_the_spokes() -> None:
    spec = mg_magnifying_wheel_spec
    notes = spec.DRAWING_NOTES
    lines = notes.splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 80 for line in lines)
    assert "SPOKES" not in notes and "CAST" not in notes
    # The spokes' count, pitch and clocking print on their own angle between
    # two spoke centrelines, and the two spokes on the horizontal (the
    # model's seed spoke on local +X) lie on A-A's cutting line through the
    # bore: no sentence states the clocking (rule 26).
    assert spec.SPOKE_PITCH_PREFIX == "6X " and spec.SPOKE_PITCH_DEG == 60.0
    assert spec.DRAWING_PRECISION[spec.SPOKE_REFERENCE] == {
        "SpokePitch": 0,
        "Tie2Clock": 0,
    }
    assert "SpokePitch" in drawing.FRONT_KEEP
    assert "SpokePitch" not in drawing.CALLOUTS_ABOVE
    # TIE 2's clock reads from the 180 deg spoke on that cutting line,
    # vertex on the bore axis (rule 10): not from a construction leg.
    assert spec.TIE2_CLOCK_SPOKE * spec.SPOKE_PITCH_DEG == 180.0
    assert spec.TIE2_FROM_SPOKE_DEG == pytest.approx(43.0)
    assert "Tie2Clock" in drawing.FRONT_KEEP
    assert "Tie2Angle" not in set().union(*spec.DRAWING_DIMENSIONS.values())
    assert not hasattr(spec, "SPOKE_PITCH_CALLOUT")
    assert not hasattr(drawing, "SPOKE_CENTRELINE")
    assert spec.SPOKE_REFERENCE in spec.REFERENCE_SKETCHES
    # The .61 locates the groove, web and rim's shared mid-plane, drawn on
    # A-A; the location carries its value and band alone (rule 7).  The
    # plane is one centreline across the whole cut, past both grooves, so
    # the line through the R's upper groove runs on to the .61's extension
    # line at the lower one (release v49 review: a reader of the upper groove
    # alone found no dimension on its centreline).
    assert "HubFrontZ" not in drawing.CALLOUTS_ABOVE
    assert "HubFrontZ" not in drawing.DIMENSION_CALLOUTS
    ((a, b),) = drawing.WEB_CENTRELINES.values()
    assert a[1] == b[1] == a[2] == b[2] == 0.0
    assert a[0] == -b[0] > rim.RIM_OUTER_DIA / 2.0
    # Its centre-plane extension line runs up into the lower groove to the
    # groove's bottom, so the .61 visibly lands on the groove (integration
    # proof 20261109T105251629Z, r1).
    assert drawing._GROOVE_BOTTOM_R == pytest.approx(
        rim.GROOVE_BOTTOM_DIA * drawing.SHEET_SCALE[0] / 2000.0
    )
    assert drawing._GROOVE_BOTTOM_R < drawing._RIM_R
    # Each tie hole is named plainly at its own callout (rule 26: WIRE TIE
    # HOLE, no coined label), size before process, at most two lines of
    # words (rule 7): no project label, so no key.
    assert drawing.DIMENSION_CALLOUTS["Tie1HoleDia"] == (
        "#60 DRILL THRU\n<MOD-DIAM>.070 #50 DRILL <HOLE-DEPTH> .32 FAR SIDE\nWIRE TIE HOLE"
    )
    # TIE 2 states where it runs: radial, from the groove's bottom.
    assert drawing.DIMENSION_CALLOUTS["Tie2HoleDia"] == (
        "DRILL THRU\nRADIAL WIRE TIE HOLE\nFROM GROOVE BOTTOM"
    )
    assert "Tie2HoleDia" not in drawing.CALLOUTS_ABOVE
    assert "TIE 1" not in notes and "TIE 2" not in notes
    for callout in drawing.DIMENSION_CALLOUTS.values():
        assert "TIE 1" not in callout and "TIE 2" not in callout
    # Each matched fit is a numbered note its callout links, so neither
    # callout runs past two lines of words (rule 7); the note names the
    # standard fit and the mate by number, the resulting clearance or
    # interference as REF (rule 4).  The groove's two tight bands serve one
    # mate, named once in a note both link (rule 4).
    assert lines == [
        "1. RUNNING FIT ON AXLE MHA-MG-07: AXLE TURNS FREE, NO SHAKE.",
        "2. BONDED FIT IN DRUM MHA-MG-10: TURN TO ITS BORE (CLEARANCE .0005-.0025).",
        "3. GROOVE SEATS PEN WIRE OF MHA-SH-VN-56.",
    ]
    assert "DIAMETRAL" not in notes
    assert drawing.DIMENSION_CALLOUTS["BoreDiaDim"] == "REAM THRU\nSEE NOTE 1"
    assert drawing.DIMENSION_CALLOUTS["SpigotDia"] == "SEE NOTE 2"
    assert drawing.DIMENSION_CALLOUTS["GrooveBottomDia"] == "SEE NOTE 3"
    # The groove's R links the same note and nothing else: the .61 is its one
    # axial location, and a "CENTRED ON RIM" line read as a second, prose one
    # (release v49 run 20261113T004939203Z; rule 26).
    assert drawing.DIMENSION_CALLOUTS["GrooveR"] == drawing.GROOVE_CALLOUT
    assert "GrooveR" not in drawing.CALLOUTS_ABOVE
    # The literal mate numbers keep the axle, drum and wire out of the part's
    # recipe; they are the config rows' numbers.
    assert (spec.AXLE_NUMBER, spec.DRUM_NUMBER, spec.WIRE_NUMBER) == (
        drawing.AXLE_NUMBER,
        drawing.DRUM_NUMBER,
        drawing.WIRE_NUMBER,
    )
    # The bore's REAM THRU callout carries the process; the notes do not.
    assert "REAMED" not in notes
    assert "RUNS ON" not in notes
    # No design rationale on the round or the overall OD (rule 7).
    assert drawing.ROUND_CALLOUT == "2X RIM BORE EDGES"
    assert "RimOuterDiaDim" not in drawing.DIMENSION_CALLOUTS
    assert drawing.CALLOUTS_ABOVE["HubLength"] == "MHA-MG-07 LOCKNUT STACK"
    # An above-callout prints one line only.
    assert not any("\n" in text for text in drawing.CALLOUTS_ABOVE.values())
    assert drawing.CALLOUTS_ABOVE["SpigotLength"] == "DRUM MHA-MG-10 NOT PROUD"
    # The rim OD reads between its extension lines at the hub's height, with
    # A-A, clear of the front view's rim.
    od_x, od_y = drawing.SECTION_DIAMETER_KEEP["RimOuterDiaDim"]
    assert od_y == drawing.SECTION_CENTER[1]
    assert od_x < drawing._GROOVE_DIA_X - drawing._TEXT_OFF_LINE
    assert od_x > drawing.FRONT_CENTER[0] + drawing._RIM_R + 0.01
    assert "CLEAR OF" not in notes and "BAND" not in notes
    assert "DO NOT" not in notes and "RELEASE" not in notes
    assert "GRAY-IRON" not in notes and "BLACK" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes


def test_no_gdt_frames_and_one_sheet_dimension() -> None:
    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the running bore takes the machined grade; the
    # spigot is bonded in the drum and takes none.
    finishes = {
        control.key: control.roughness_um
        for control in mg_magnifying_wheel_spec.SURFACE_FINISHES
    }
    assert finishes == {"mg_wheel_bore": MACHINED_UM}
    spec = mg_magnifying_wheel_spec
    assert spec.SPOKE_FACE_OFFSET == pytest.approx(
        (rim.RIM_AXIAL - geom.SPOKE_AXIAL) / 2.0
    )
    reference = spec.DIAMETER_REFERENCE
    assert "SpokeFaceOffset" in spec.DRAWING_DIMENSIONS[reference]
    assert "SpokeFaceOffset" in spec.CAST_DIMENSIONS[reference]
    assert spec.DRAWING_PRECISION[reference]["SpokeFaceOffset"] == 2
    assert "spoke face" not in spec.DRAWING_REFERENCE_PRECISION
    assert "SpokeFaceOffset" in drawing.SECTION_DIAMETER_KEEP
    assert "SpokeFaceOffset" not in spec.REFERENCE_DIAMETERS
    assert "SpokeAxial" in spec.CAST_DIMENSIONS["Spoke"]
    assert not hasattr(mg_magnifying_wheel_spec, "GEOMETRIC_TOLERANCES_MM")


def test_part_stamps_make_critical_properties() -> None:
    import _config

    config = _config.parts("mg-magnifying-wheel")
    assert config["material"] == config["material_specification"]
    # Paint never reaches a fitted or wire-bearing surface (drawing-guidelines.md rule 2 (the title block is the general specification)).
    assert config["finish"] == (
        "BLACK ENAMEL; MASK BORE, SPIGOT, HUB ENDS, RIM AND GROOVE; OIL BARE SURFACES"
    )
    assert int(config["quantity"]) == 1
