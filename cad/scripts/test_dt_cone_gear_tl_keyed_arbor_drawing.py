"""Offline contracts for the keyed tooth-cutting arbor (MHA-DT-03-TL-03)."""

from __future__ import annotations

import math
import sys

import pytest

import _buildgraph as bg
import _config
import build_dt_cone_gear_tl_keyed_arbor as part
import cone_land_key
import draw_dt_cone_gear_tl_keyed_arbor as drawing
import dt_cone_gear_tl_keyed_arbor_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _inch_wall_limits import WALL_FLOOR_MM
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import angular_band_deg, printed_band_mm

INCH = 25.4
XX = printed_band_mm(2, unit="in")
XXX = printed_band_mm(3, unit="in")
KIT = "dt_cone_gear_tl_arbor"


def test_registry_row_is_tooling_in_inch_inside_its_kit_only() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-03"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    entry = DRAWINGS_BY_NAME["dt_cone_gear_tl_keyed_arbor"]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    stem = "dt_cone_gear_tl_keyed_arbor"
    assert bg.is_shop_fixture(stem)
    assert stem in bg.references_of(KIT)
    for machine in bg.MACHINE_ASSEMBLIES:
        assert stem not in bg.references_of(machine)


def test_the_arbor_serves_every_keyed_cone_and_the_64t() -> None:
    import dt_cone_gear_spec as cone
    import dt_crank_drive_gear_spec as crank

    tags = [blank.tag for blank in spec.KEYED_GEARS]
    assert tags == [f"T{t:03d}" for t in cone.KEYED_TEETH] + [f"{crank.TEETH}T"]


def test_one_seat_fits_every_blank_inside_the_tir_share() -> None:
    """The seat is a matched sliding fit: line to line with the smallest bore
    (it prints the supply size at .XXX) and never more play than the share
    in the largest, so one seat serves every keyed bore."""
    low, high = spec.SEAT_CLEARANCE_MM
    assert low == 0.0
    assert high <= spec.PLAY_SHARE * spec.TOOTH_RUNOUT_TIR_MM + 1e-9
    assert spec.SEAT_DIA == spec.BORE_MIN_MM
    assert spec.SEAT_DIA_MIN <= spec.SEAT_DIA
    for blank in spec.KEYED_GEARS:
        assert blank.bore[0] - spec.SEAT_DIA >= low - 1e-9, blank.tag
        assert blank.bore[1] - spec.SEAT_DIA_MIN <= high + 1e-9, blank.tag
    assert spec.PLAY_SHARE < 1.0
    assert spec.SEAT_RUNOUT_ALLOWANCE_MM > 0.0
    assert spec.DRAWING_PRECISION_BY_NAME["SeatDia"] == 3
    assert ("SeatProfile", "SeatDia") not in spec.MODEL_BANDS_MM
    assert spec.CALLOUTS_BELOW["SeatDia"] == spec.SEAT_NOTE_FLAG
    assert (
        "MATCHED" in spec.SHEET_NOTES and ".0000-.0013 IN EACH BORE" in spec.SHEET_NOTES
    )


def test_the_note_names_every_mate_by_its_drawing_number() -> None:
    """The seat's mates are the kit sheet's setup table rows, every blank by
    drawing number; the note points there, and names the key's bond."""
    import dt_cone_gear_tl_arbor_assembly_spec as kit

    note = " ".join(spec.SHEET_NOTES.split())
    assert f"KEYED BORES LISTED ON {spec.KIT_NUMBER}" in note
    for blank in spec.KEYED_GEARS:
        assert blank.number in (row[0] for row in kit.SETUP_TABLE_ROWS), blank.tag
    assert f"KEY {spec.KEY_NUMBER} BONDED WITH {spec.KEY_BOND}" in note
    assert f"COAT ITEM 5 WITH {spec.KEY_BOND}." in kit.ASSEMBLY_STEPS
    assert len(spec.SHEET_NOTES.splitlines()) <= 4
    # The pilot only carries the loose collars: a clearance size at the title
    # block's .XXX band, never a fit name.
    pilot = spec.CALLOUTS_BELOW["PilotDia"]
    assert pilot == "CLEARS TL-04"
    assert "FIT" not in pilot
    assert spec.COLLAR_BORE - (spec.PILOT_DIA + XXX) > 0.0  # a clearance
    # The shoulder root prints the repo's MAX form and links the seat's note,
    # which names the bores that seat on the shoulder.
    assert spec.SHOULDER_R_TOL_TYPE == 0 and spec.SHOULDER_R_SUFFIX == " MAX"
    assert spec.CALLOUTS_BELOW["ShoulderR"] == spec.SEAT_NOTE_FLAG
    assert spec.THREAD_CALLOUT == "1/4-28 UNF"


def test_no_two_place_pilot_clears_the_collar_bore_and_backs_t030() -> None:
    """The pilot keeps .XXX: either .XX grid neighbour of Ø.275 fails at the
    title block's limits. Ø.28 meets the Ø.290 drilled bore line to line and
    its keyseat run-out cuts it; Ø.27 floats the Ø.50 collar over T030's root.
    """
    assert spec.DRAWING_PRECISION_BY_NAME["PilotDia"] == 3
    t030 = spec.KEYED_GEARS[0]
    assert t030.tag == "T030"
    for nominal in (0.27 * INCH, 0.28 * INCH):
        bore_clears = spec.COLLAR_BORE - (nominal + XX) > 1e-9
        under_floor = spec.KEYSEAT_FLOOR_MIN - (nominal + XX) / 2.0 > 0.0
        floating = (spec.COLLAR_BORE + spec._DRILL_PLUS - (nominal - XX)) / 2.0
        reach = spec.COLLAR_DIAS[0] / 2.0 + XX + floating
        backs_t030 = reach <= t030.root_min_dia / 2.0 - spec.AIR_MIN
        assert not (bore_clears and under_floor and backs_t030), nominal


def test_the_blank_stands_clear_of_the_jaws_and_the_seat_ends_inside_it() -> None:
    """Every station is from the grip's end face, so a length between two of
    them holds twice the .XX band."""
    assert spec.STANDOFF - 2.0 * XX >= 0.75 * INCH - 1e-9
    for blank in spec.KEYED_GEARS:
        assert spec.SEAT_LENGTH + 2.0 * XX < blank.face[0], blank.tag
        assert spec.PILOT_END - 2.0 * XX > blank.face[1], blank.tag


def test_every_blank_is_backed_under_its_root_by_the_largest_clear_collar() -> None:
    """The cutter runs out past both faces: the shoulder and the collar stand
    under the root by the air at every limit, and each setup takes the largest
    collar that does."""
    floating = (spec.COLLAR_BORE + spec._DRILL_PLUS - (spec.PILOT_DIA - XXX)) / 2.0
    reach = [d / 2.0 + XX + floating for d in spec.COLLAR_DIAS]
    shoulder = spec.STANDOFF_DIA / 2.0 + XX
    for blank in spec.KEYED_GEARS:
        limit = blank.root_min_dia / 2.0 - spec.AIR_MIN
        index = spec.COLLAR_BY_GEAR[blank.tag]
        assert reach[index] <= limit, blank.tag
        assert shoulder <= limit, blank.tag
        if index + 1 < len(reach):
            assert reach[index + 1] > limit, blank.tag
        share = spec.COLLAR_DIAS[index] / blank.root_min_dia
        assert share >= spec.BACKING_SHARE_MIN, blank.tag
    assert set(spec.COLLAR_BY_GEAR.values()) == set(range(len(spec.COLLAR_DIAS)))


def test_the_nut_clamps_on_full_thread_with_thread_to_spare() -> None:
    pitch = INCH / 28.0
    smallest_root = min(blank.root_min_dia for blank in spec.KEYED_GEARS)
    corners = spec.NUT_ACROSS_FLATS / math.cos(math.radians(30.0))
    assert corners / 2.0 + spec.AIR_MIN <= smallest_root / 2.0
    assert spec.NUT_ACROSS_FLATS > spec.COLLAR_BORE + spec._DRILL_PLUS
    thinnest = min(blank.face[0] for blank in spec.KEYED_GEARS)
    thickest = max(blank.face[1] for blank in spec.KEYED_GEARS)
    nearest_collar_face = thinnest + spec.COLLAR_LENGTH - XX
    farthest_collar_face = thickest + spec.COLLAR_LENGTH + XX
    past = (spec.ARBOR_END - 2.0 * XX) - (farthest_collar_face + spec.NUT_THICKNESS_MAX)
    assert past >= 1.5 * pitch
    assert nearest_collar_face - (spec.RELIEF_END + 2.0 * XX) > 2.0 * pitch
    assert spec.PILOT_END + 2.0 * XX < nearest_collar_face
    assert spec.RELIEF_DIA + XX < spec.THREAD_ROOT_MIN
    assert (spec.RELIEF_END - XX) - (spec.PILOT_END + XX) >= pitch


def test_both_centres_hold_their_walls() -> None:
    assert spec.HEAD_CENTRE_DIA + XX <= 0.125 * INCH + 1e-9
    wall = (spec.THREAD_ROOT_MIN - (spec.TAIL_CENTRE_DIA + XXX)) / 2.0
    assert wall >= WALL_FLOOR_MM
    assert spec.TAIL_CENTRE_DIA - XXX > spec.CENTRE_PILOT_MAX


def test_the_key_carries_the_clock_and_lies_under_every_blank() -> None:
    play = math.degrees(
        cone_land_key.KEYWAY_SIDE_CLEARANCE_MM[1] / 2.0 / (spec.BORE_MIN_MM / 2.0)
    )
    assert play < angular_band_deg(unit="in")
    far_end = spec.KEY_END_SET + XX + spec.KEY_LENGTH + XX
    assert far_end <= spec.SEAT_LENGTH - 2.0 * XX + 1e-9
    assert far_end < min(blank.face[0] for blank in spec.KEYED_GEARS)
    # The keyseat's straight run passes out over the pilot, under its floor.
    assert spec.KEYSEAT_FLOOR_MIN > (spec.PILOT_DIA + XXX) / 2.0
    assert spec.KEYSEAT_WIDTH == cone_land_key.KEYSEAT_WIDTH_MM
    assert spec.KEYSEAT_S == cone_land_key.KEYSEAT_S_MM


def test_the_stations_and_volume_close_on_the_sections() -> None:
    lengths = [
        (spec.GRIP_DIA, spec.GRIP_LENGTH),
        (spec.STANDOFF_DIA, spec.STANDOFF),
        (spec.SEAT_DIA, spec.SEAT_LENGTH),
        (spec.PILOT_DIA, spec.PILOT_END - spec.SEAT_LENGTH),
        (spec.RELIEF_DIA, spec.RELIEF_END - spec.PILOT_END),
        (spec.THREAD_MAJOR, spec.ARBOR_END - spec.RELIEF_END),
    ]
    assert sum(length for _dia, length in lengths) == pytest.approx(spec.OVERALL_LENGTH)
    turned = sum(math.pi / 4.0 * dia**2 * length for dia, length in lengths)
    assert spec.TURNED_VOLUME == pytest.approx(turned, rel=1e-9)
    assert 0.0 < spec.FINISHED_VOLUME < spec.TURNED_VOLUME
    names = {name for name, *_rest in spec.SECTIONS}
    assert names == set(spec.SECTION_DIMENSIONS)


def test_every_printed_length_is_a_baseline_from_the_grip_end() -> None:
    """Rule 10/11: one datum, the grip's end face; the overall ties the
    thread's end; the thread's own length is left off the sheet."""
    printed = {
        name
        for names in spec.DRAWING_DIMENSIONS.values()
        for name in names
        if name in spec.LENGTH_DRIVES or name == "CentreOverall"
    }
    assert printed == {*spec.SHEET_LENGTHS, "CentreOverall"}
    assert "ThreadLength" not in printed
    stations = {
        "GripLength": spec.GRIP_LENGTH,
        "Shoulder": spec.SHOULDER_Z,
        "SeatEnd": spec.SEAT_END_Z,
        "PilotEnd": spec.PILOT_END_Z,
        "ReliefEnd": spec.RELIEF_END_Z,
        "CentreOverall": spec.OVERALL_LENGTH,
    }
    for name, value in stations.items():
        assert spec.DRAWING_VALUES_BY_NAME[name] == pytest.approx(value), name
        a, b, _tier = drawing.LENGTH_SPANS_Z[name]
        assert a == 0.0 and b == pytest.approx(value), name
    starts = {name: start for name, _dia, start, _end in spec.SECTIONS}
    assert all(starts[s] == 0.0 for s in ("Standoff", "Seat", "Pilot", "Relief"))


def test_the_tight_bands_live_on_the_model_dimensions() -> None:
    assert model_toleranced_dimensions(part)
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    for (feature, name), band in spec.MODEL_BANDS_MM.items():
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert band[1] < band[0]
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.DRAWING_VALUES_BY_NAME) == marked
    assert set(spec.CALLOUTS_BELOW) <= marked
    assert len(spec.SHEET_NOTES.splitlines()) <= 4
    for callout in spec.CALLOUTS_BELOW.values():
        assert len(callout.splitlines()) <= 2


class _CentreRecorder:
    """A fake SolidWorks for the centre-hole sketch: every call it gets."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.currentModel = None

    async def create_sketch(self, plane):
        self.calls.append(("create_sketch", plane))
        return "ok"

    async def add_centerline(self, *xy):
        self.calls.append(("centerline", xy))
        return "Axis"

    async def add_sketch_constraint(self, first, second, relation):
        self.calls.append(("constraint", first, second, relation))
        return "ok"

    async def add_sketch_dimension(self, first, second, kind, value):
        self.calls.append(("dimension", first, second, kind, value))
        return "ok"

    async def exit_sketch(self):
        self.calls.append(("exit_sketch",))
        return "ok"

    async def create_revolve(self, params):
        self.calls.append(("revolve", params))
        return "ok"


def test_centre_holes_are_sized_by_axial_depth_never_an_angle(monkeypatch) -> None:
    """Both cones are fixed by their mouth diameter and an axial depth driven
    as mouth/2 / tan(30), so the solver keeps each apex inside its end face;
    no angular dimension can flip a cone across its face into air."""
    import asyncio

    adapter = _CentreRecorder()
    recorded: list[tuple[str | None, str | None]] = []

    class _Dims:
        def record(self, name, drive=None):
            recorded.append((name, drive))

        def apply(self, _adapter, _feature):
            return [(name, drive) for name, drive in recorded if drive]

    lines = iter(f"L{i}" for i in range(6))

    async def chain(_adapter, points, close=True):
        adapter.calls.append(("chain", tuple(points)))
        return [next(lines) for _ in points]

    async def diametric(_adapter, axis, point, **kwargs):
        adapter.calls.append(("diametric", axis, point))

    async def anchor(_adapter, ref, x, y, label):
        adapter.calls.append(("anchor", ref, x, y))

    async def between(_adapter, first, second, kind, value, label):
        adapter.calls.append(("dimension", first, second, kind, value))
        return "ok"

    async def defined(_adapter, _label):
        return None

    # The Right Plane's sketch: u = -Z, v = Y (model mm).
    monkeypatch.setattr(part, "_sketch_xy_mm", lambda _a, p: (-p[2], p[1]))
    monkeypatch.setattr(part, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "SketchDims", _Dims)
    monkeypatch.setattr(part, "add_line_chain", chain)
    monkeypatch.setattr(part, "add_diametric_linear_dimension", diametric)
    monkeypatch.setattr(part, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(part, "dimension_between", between)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda *_a: None)
    monkeypatch.setattr(part, "name_last_feature", lambda *_a: None)
    jobs: list[tuple[str, str]] = []
    removed = asyncio.run(part._cut_centres(adapter, jobs))
    assert removed == pytest.approx(spec.CENTRE_VOLUME)
    dims = [c for c in adapter.calls if c[0] == "dimension"]
    assert not [c for c in dims if c[3] == "angular"]
    depths = [c for c in dims if c[1].startswith("L") and c[2].startswith("L")]
    assert [c[3] for c in depths] == ["horizontal_distance"] * 2
    assert [c[4] for c in depths] == pytest.approx(
        [
            spec.centre_depth_mm(spec.HEAD_CENTRE_DIA),
            spec.centre_depth_mm(spec.TAIL_CENTRE_DIA),
        ]
    )
    # Each depth runs along its own triangle's axis line, apex inside the part.
    chains = [c[1] for c in adapter.calls if c[0] == "chain"]
    for (apex, mouth, face), end_z in zip(chains, (0.0, spec.OVERALL_LENGTH)):
        assert apex[1] == face[1] == 0.0
        assert mouth[0] == face[0] == -end_z
        assert 0.0 < -apex[0] < spec.OVERALL_LENGTH
    # The drives keep the 60 degree cone whatever the mouth.
    drives = dict(recorded)
    for name, dia in (
        ("HeadCentreDepth", spec.HEAD_CENTRE_DIA),
        ("TailCentreDepth", spec.TAIL_CENTRE_DIA),
    ):
        expression = drives[name]
        assert expression.startswith(f'"{name.replace("Depth", "Dia")}" / 2')
        half = float(expression.rsplit("tan(", 1)[1].rstrip(")"))
        assert dia / 2.0 / math.tan(math.radians(half)) == pytest.approx(
            spec.centre_depth_mm(dia)
        )
        assert 2.0 * half == spec.CENTRE_INCLUDED_ANGLE_DEG
    (revolve,) = [c[1] for c in adapter.calls if c[0] == "revolve"]
    assert revolve.is_cut and revolve.angle == 360.0


def _fake_projection(_adapter, _view, points_m, label, names):
    """The side view at 3:1, the axis horizontal, head right, model +Y up;
    the end view at 3:1, model +X right, +Y up."""
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    if label.startswith("end view"):
        cx, cy = drawing.END_CENTER
        return [(cx + x * scale, cy + y * scale) for x, y, _z in points_m]
    half = spec.OVERALL_LENGTH / 2000.0
    cx, cy = drawing.SIDE_CENTER
    return [(cx + (half - z) * scale, cy + y * scale) for _x, y, z in points_m]


def test_the_side_view_places_every_marked_dimension_off_the_part(
    monkeypatch,
) -> None:
    monkeypatch.setattr(drawing, "model_points_in_view", _fake_projection)
    keep = drawing._side_keep(None, None)
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    in_end_view = spec.DRAWING_DIMENSIONS[spec.KEYSEAT_SKETCH]
    assert set(keep) == marked - in_end_view
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    top = drawing.SIDE_CENTER[1] + spec.GRIP_DIA / 1000.0 / 2.0 * scale
    bottom = drawing.SIDE_CENTER[1] - spec.GRIP_DIA / 1000.0 / 2.0 * scale
    for name, (_x, y) in keep.items():
        assert not bottom < y < top, name
    positions = list(keep.values())
    assert len(set(positions)) == len(positions)
    # At the tail face the thread's line stands on the threaded step and the
    # tail centre's outside it: never one line (rule 14).
    tail = {
        name: side
        for name, (z, side, _r) in drawing.DIA_TEXT.items()
        if z == spec.ARBOR_END_Z
    }
    assert tail == {
        "ThreadDia": drawing.TOWARD_HEAD,
        "TailCentreDia": drawing.TOWARD_TAIL,
    }
    assert keep["ThreadDia"][0] - keep["TailCentreDia"][0] >= 2.0 * drawing.TEXT_GAP
    # The relief's text, toward the tail, stands over the thread's.
    assert keep["ReliefDia"][1] - keep["ThreadDia"][1] >= 0.009
    # Baselines: each tier's span holds every nearer tier's span.
    spans = sorted(drawing.LENGTH_SPANS_Z.values(), key=lambda span: span[2])
    assert [tier for _a, _b, tier in spans] == list(range(1, len(spans) + 1))
    for (_a0, b0, _t0), (_a1, b1, _t1) in zip(spans, spans[1:], strict=False):
        assert b0 < b1
    # Lengths stay above the title block (top 0.066 m).
    assert (
        min(y for name, (_x, y) in keep.items() if name in drawing.LENGTH_SPANS_Z)
        > 0.075
    )


def test_the_end_view_puts_the_keyseat_toward_the_side_view(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "model_points_in_view", _fake_projection)
    keep = drawing._end_keep(None, None)
    assert set(keep) == spec.DRAWING_DIMENSIONS[spec.KEYSEAT_SKETCH]
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    grip = spec.GRIP_DIA / 2000.0 * scale
    end_right = drawing.END_CENTER[0] + grip
    side_left = drawing.SIDE_CENTER[0] - spec.OVERALL_LENGTH / 2000.0 * scale
    width_x = keep["KeyseatWidth"][0]
    assert end_right < width_x < side_left
    # The width's text ends short of the tail centre's dimension line,
    # TEXT_GAP off the arbor's tail face (rule 14).
    tail_line = side_left - drawing.TEXT_GAP
    assert width_x + drawing.END_WIDTH_TEXT < tail_line - 0.002
    assert keep["KeyseatS"][1] < drawing.END_CENTER[1] - grip
    # S's text stands wholly outside its extension lines, right of the
    # floor's, so neither strikes its stacked limits (rule 14).
    floor_x = drawing.END_CENTER[0] + spec.KEYSEAT_FLOOR_OFFSET / 1000.0 * scale
    s_x = keep["KeyseatS"][0]
    assert s_x - drawing.END_S_TEXT / 2.0 > floor_x
    assert s_x + drawing.END_S_TEXT / 2.0 < side_left - 0.002


def test_the_standoff_diameter_line_clears_the_keyseat_end_set(monkeypatch) -> None:
    """The Ø.50's dimension line stands on the standoff, far from the
    shoulder where the .05 keyseat-end set's outside arrow runs (rule 14)."""
    monkeypatch.setattr(drawing, "model_points_in_view", _fake_projection)
    keep = drawing._side_keep(None, None)
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    cx = drawing.SIDE_CENTER[0] + spec.OVERALL_LENGTH / 2000.0 * scale

    def x_of(z: float) -> float:
        return cx - z / 1000.0 * scale

    line = keep["StandoffDia"][0]
    assert x_of(spec.SHOULDER_Z) + 0.010 < line < x_of(spec.GRIP_LENGTH) - 0.010


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
    monkeypatch.setattr(sys, "argv", ["draw", "dt-cone-gear"])
    with pytest.raises(SystemExit):
        drawing._parse_args()
