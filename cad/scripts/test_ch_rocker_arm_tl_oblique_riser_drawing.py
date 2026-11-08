"""Offline contracts for the oblique-trammel jig's 6061 riser (MHA-CH-06-TL-24)."""

from __future__ import annotations

import inspect
import math
import re

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_riser as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier_spec
import ch_rocker_arm_tl_oblique_riser_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_strap_spec as strap
import draw_ch_rocker_arm_tl_oblique_riser as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM

STEM = "ch_rocker_arm_tl_oblique_riser"
INCH = 25.4
_STOP_STATIONS = {"Stop1X", "Stop2X", "StopY"}


def _on_inch_grid(value_mm: float, places: int) -> bool:
    inches = value_mm / INCH
    return abs(inches - round(inches, places)) < 1e-9


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _carrier(xy: tuple[float, float]) -> tuple[float, float]:
    return (xy[0] + spec.BLANK_ORIGIN[0], xy[1] + spec.BLANK_ORIGIN[1])


def _close(a: tuple[float, float], b: tuple[float, float], tol: float) -> bool:
    return math.dist(a, b) <= tol


def test_hole_positions_map_back_to_the_calculator() -> None:
    # Presentation precision must not move the carrier-located model axes.
    tol = 1e-9
    assert len(spec.SCREW_HOLES) == len(trammel.RISER_SCREWS) == 4
    for riser, carrier in zip(spec.SCREW_HOLES, trammel.RISER_SCREWS, strict=True):
        assert _close(_carrier(riser), carrier, tol)
    assert _close(_carrier(spec.HUB_HOLE), trammel.HUB, tol)
    assert _close(_carrier(spec.CL_HOLE), trammel.CL, tol)
    assert _close(_carrier(spec.CR_HOLE), trammel.CR, tol)
    for riser, carrier in zip(
        spec.STOP_PIN_HOLES, spec.STOP_PIN_CARRIER_POINTS, strict=True
    ):
        assert _close(_carrier(riser), carrier, tol)
    features = _features()
    for name, carrier, y_field in (
        *(
            (f"screw_hole_{i}", xy, "width_nominal")
            for i, xy in enumerate(trammel.RISER_SCREWS, start=1)
        ),
        ("hub_hole", trammel.HUB, "width_nominal"),
        ("cl_hole", trammel.CL, "width_nominal"),
        ("cr_hole", trammel.CR, "width_nominal"),
        *(
            (f"stop_hole_{i}", xy, "height_nominal")
            for i, xy in enumerate(spec.STOP_PIN_CARRIER_POINTS, start=1)
        ),
    ):
        feature = features[name]
        exported = (feature["station_nominal"], feature[y_field])
        assert _close(_carrier(exported), carrier, tol), name
        assert feature["thru"] is True


def test_the_model_globals_are_the_spec_stations() -> None:
    g = spec.GLOBALS
    xs = [g[f"Screw{i}X"] for i in range(1, 5)]
    ys = [g["ScrewInnerY"]] * 2 + [g["ScrewOuterY"]] * 2
    assert list(zip(xs, ys, strict=True)) == list(spec.SCREW_HOLES)
    assert (g["HubX"], g["HubY"]) == spec.HUB_HOLE
    assert (g["ClX"], g["ClampY"]) == spec.CL_HOLE
    assert (g["CrX"], g["ClampY"]) == spec.CR_HOLE
    assert [(g["Stop1X"], g["StopY"]), (g["Stop2X"], g["StopY"])] == list(
        spec.STOP_PIN_HOLES
    )
    # The plain sketch circles are the carrier-spotted HUB, CL and CR only:
    # the stop holes are a native #30 wizard feature (actual cut).
    assert [xy for xy, _dia, _n, _d in spec.CIRCLES] == [
        spec.HUB_HOLE,
        spec.CL_HOLE,
        spec.CR_HOLE,
    ]
    assert [dia for _xy, dia, _n, _d in spec.CIRCLES] == [
        spec.HUB_DIA,
        spec.CLAMP_DIA,
        spec.CLAMP_DIA,
    ]


def test_blank_and_holes_are_the_part_sheet() -> None:
    assert spec.THICKNESS == trammel.RISER_THICK
    for name, value in (
        ("BlankLength", spec.BLANK_LENGTH),
        ("BlankWidth", spec.BLANK_WIDTH),
        ("BlankThick", spec.THICKNESS),
        ("ClampDia", spec.CLAMP_DIA),
        ("StopDia", spec.STOP_HOLE_DIA),
        ("Stop1X", spec.STOP_PIN_HOLES[0][0]),
        ("Stop2X", spec.STOP_PIN_HOLES[1][0]),
        ("StopY", spec.STOP_PIN_HOLES[0][1]),
    ):
        assert _on_inch_grid(value, spec.DRAWING_PRECISION_BY_NAME[name]), name
    assert spec.SCREW_SPEC.kind == "clearance" and spec.SCREW_SPEC.size == "#4"
    assert trammel.RISER_SCREW == "#4-40"
    # The literal metric HUB relief passes the in-place product-hole reamer.
    assert spec.HUB_DIA == 12.0
    assert spec.HUB_DIA > strap.HOLE_DIA
    assert part.MATERIAL == "6061 Alloy"


def test_hub_relief_cuts_the_12_mm_drill_and_prints_its_design_nominal() -> None:
    """The owner's literal 12 mm relief stays the model's cut (its reamer
    clearance is the drill's); the inch sheet prints the floored three-place
    design nominal .472 in the table, as the #30 holes do, so the DRILLED
    HOLES +.004/0 band contains the actual drill and every exported endpoint
    is a printed value. No millimetre value prints on the inch sheet."""
    assert spec.HUB_DIA_PRINTED == pytest.approx(0.472 * INCH)
    assert _on_inch_grid(spec.HUB_DIA_PRINTED, spec.HUB_PLACES)
    assert spec.DRAWING_PRECISION_BY_NAME["HubDia"] == spec.HUB_PLACES == 3
    assert spec.GLOBALS["HubDia"] == spec.HUB_DIA_PRINTED
    assert spec.GLOBALS["HubCutDia"] == spec.HUB_DIA
    assert spec.CIRCLES[0][2][2] == "HubCutDia" and spec.CIRCLES[0][3][2] == '"HubCutDia"'
    assert spec.DRAWING_DIMENSIONS["HubHoleReference"] == {"HubDia"}
    assert "HubDia" not in spec.DRAWING_DIMENSIONS["HoleProfile"]
    assert "HubCutDia" not in set().union(*spec.DRAWING_DIMENSIONS.values())
    rows = {row[0]: row for row in part._REFERENCE_CIRCLES}
    _sketch, centre, dia, names, drives = rows["HubHoleReference"]
    assert (centre, dia) == (spec.HUB_HOLE, spec.HUB_DIA_PRINTED)
    assert names[2] == "HubDia" and drives == ('"HubX"', '"HubY"', '"HubDia"')
    feature = _features()["hub_hole"]
    lo, hi = feature["dia"]
    assert (lo, hi) == pytest.approx((0.472 * INCH, 0.476 * INCH))
    assert lo <= spec.HUB_DIA <= hi
    assert feature["dia_nominal"] == spec.HUB_DIA_PRINTED
    assert lo > strap.HOLE_DIA
    assert drawing.PLAIN_CUT_SIZES["HUB"] == "\u00d8.472 DRILL THRU"
    # The native SIZE may print the cut's inch rounding, never millimetres.
    assert drawing.native_size_problem("HUB", "\u00d8.472 THRU ALL") is None
    assert drawing.native_size_problem("HUB", "<MOD-DIAM>.4724 THRU ALL") is None
    assert drawing.native_size_problem("HUB", "\u00d812 MM THRU ALL") is not None
    assert drawing.native_size_problem("HUB", "\u00d812.00 THRU ALL") is not None
    assert drawing.native_size_problem("HUB", "\u00d8.47 THRU ALL") is not None


def test_blank_sizes_are_finished_native_dimensions_not_stock() -> None:
    dimensions = {"BlankLength", "BlankWidth", "BlankThick"}
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert dimensions <= marked
    assert set(drawing.PLAN_KEEP) | set(drawing.SECTION_KEEP) == dimensions
    for name in dimensions:
        assert spec.DRAWING_PRECISION_BY_NAME[name] in (
            spec.BLANK_PLACES,
            spec.THICKNESS_PLACES,
        ), name
    assert not {
        (feature, name)
        for feature, name in model_toleranced_dimensions(part)
        if name in dimensions
    }


def test_flat_head_sinks_and_countersink_stays_in_the_blank() -> None:
    csk = _features()["screw_hole_1_countersink"]
    assert csk["angle_deg"] == 82.0
    assert csk["dia"][0] >= spec.SCREW_HEAD_DIA_MAX
    assert spec.CSK_DEPTH_MAX < spec.THICKNESS - spec.THICKNESS_BAND
    assert _features()["screw_hole_1"]["dia"][0] > spec.SCREW_BODY_DIA


def test_the_screw_hole_has_one_callout_naming_its_countersink() -> None:
    """Three-place design nominal, actual #30 cutter and unchanged countersink."""
    assert _on_inch_grid(spec.SCREW_DIA_PRINTED, spec.SCREW_DIA_PLACES)
    assert spec.SCREW_DIA_PLACES == spec.DRAWING_PRECISION_BY_NAME["ScrewDia"] == 3
    assert spec.SCREW_DIA_PRINTED == pytest.approx(0.128 * INCH)
    assert spec.SCREW_DRILL == "#30"
    assert spec.SCREW_DRILL_DIA == pytest.approx(0.1285 * INCH)
    assert spec.SCREW_DIA == round(spec.SCREW_DRILL_DIA, 3)
    assert spec.GLOBALS["ScrewDia"] == spec.SCREW_DIA_PRINTED
    lo, hi = _features()["screw_hole_1"]["dia"]
    assert lo <= spec.SCREW_DIA <= hi
    assert (lo, hi) == pytest.approx((0.128 * INCH, 0.132 * INCH))
    assert round(spec.SCREW_DIA / INCH, 3) * INCH > spec.SCREW_DIA
    assert drawing.CSK_TEXT == "<HOLE-SINK> \u00d8.25 X 82\u00b0"
    notes = drawing.row_notes({tag: "\u00d8.129 THRU ALL" for tag in drawing.TABLE_HOLES})
    assert {tag for tag, note in notes.items() if note} == {"R1", "R2", "R3", "R4"}
    assert all(notes[f"R{i}"] == drawing.CSK_TEXT for i in range(1, 5))
    assert "CskDia" not in set().union(*spec.DRAWING_DIMENSIONS.values())


def test_native_cut_readback_requires_both_design_limits() -> None:
    for printed in (spec.SCREW_DIA_PRINTED, spec.STOP_HOLE_DIA):
        lo, hi = printed, printed + spec.DRILLED_BAND[0]
        for diameter in (lo, spec.SCREW_DRILL_DIA, spec.SCREW_DIA, hi):
            part._require_cut_in_printed_band(diameter, printed, "holes")
        for diameter in (lo - 0.001, hi + 0.001):
            with pytest.raises(RuntimeError, match="outside the printed"):
                part._require_cut_in_printed_band(diameter, printed, "holes")


def test_stop_holes_cut_the_actual_30_drill_and_print_the_design_nominal() -> None:
    """The two loose end-stop pin holes follow the screw holes' prior fix: the
    native wizard cuts the actual #30 (.1285); a blanked reference circle on
    stop 2 prints the .128 design nominal under DRILLED HOLES +.004/0."""
    assert spec.STOP_DRILL == spec.SCREW_DRILL == "#30"
    assert spec.STOP_SPEC == spec.SCREW_SPEC
    assert spec.STOP_DIA == spec.SCREW_DIA
    assert spec.STOP_HOLE_DIA == pytest.approx(0.128 * INCH)
    assert spec.GLOBALS["StopDia"] == spec.STOP_HOLE_DIA
    assert spec.DRAWING_PRECISION_BY_NAME["StopDia"] == 3
    assert spec.DRAWING_DIMENSIONS["StopHoles"] == _STOP_STATIONS
    assert spec.DRAWING_DIMENSIONS["StopHoleReference"] == {"StopDia"}
    assert part.REFERENCE_SKETCHES == (
        "ScrewHoleReference",
        "HubHoleReference",
        "StopHoleReference",
    )
    rows = {row[0]: row for row in part._REFERENCE_CIRCLES}
    _sketch, centre, dia, names, drives = rows["StopHoleReference"]
    assert (centre, dia) == (spec.STOP_PIN_HOLES[1], spec.STOP_HOLE_DIA)
    assert names[2] == "StopDia" and drives == ('"Stop2X"', '"StopY"', '"StopDia"')
    for index in (1, 2):
        feature = _features()[f"stop_hole_{index}"]
        lo, hi = feature["dia"]
        assert (lo, hi) == pytest.approx((0.128 * INCH, 0.132 * INCH))
        assert lo <= spec.STOP_DIA <= hi
        assert lo <= spec.SCREW_DRILL_DIA <= hi
        # Loose: the largest supplier pin slips in the smallest hole.
        assert lo > spec.STOP_PIN_DIA_LIMITS[1]
    source = inspect.getsource(part.build)
    assert 'name="StopHoles"' in source and "STOP_SPEC" in source
    assert "SharedCoordinate(0)" in source[source.index('name="StopHoles"') :]
    # The wizard's native SIZE: the actual #30 rounded, or its drill number.
    for text in ("\u00d8.129 THRU ALL", "\u00d8.1285 THRU ALL", "\u00d8.128 THRU", "#30 THRU ALL"):
        assert drawing.native_size_problem("P1", text) is None, text
    for text in ("\u00d8.13 THRU ALL", "#29 THRU ALL", "\u00d83.26 THRU ALL", "", "\u00d8.129"):
        assert drawing.native_size_problem("P1", text) is not None, text
    assert spec.WALLS_MM["stop 1 to edges"] >= WALL_TARGET_MM
    assert spec.WALLS_MM["stop 2 to edges"] >= WALL_TARGET_MM


def test_spotted_holes_print_reference_table_locations_from_the_carrier() -> None:
    """TrammelJig ruling (L1 route): the carrier-located holes are spotted
    from TL-21 at assembly, so their table locations are REF (one note) and
    each row's MATE names the TL-21 hole it is spotted from, by the carrier
    table's own tag. The end-stop holes are drilled at ordinary .XX table
    locations that keep the title block's band."""
    assert drawing.SPOTTED == ("R1", "R2", "R3", "R4", "HUB", "CL", "CR")
    assert set(drawing.SPOTTED) <= set(carrier_spec.TABLE_HOLES)
    for tag in drawing.SPOTTED:
        x, y, _dia = carrier_spec.TABLE_HOLES[tag]
        assert _close(spec.to_riser((x, y)), drawing.TABLE_HOLES[tag][0], 1e-9), tag
        assert drawing.ROW_MATES[tag].split("\n")[0] == f"TL-21 {tag}"
    assert drawing.SPOT_NOTE == (
        "R1-R4, HUB, CL, CR: X/Y LOC REF; SPOT FROM TL-21 AT ASSEMBLY"
    )
    assert drawing.CARRIER_SHORT == "TL-21"
    assert spec.CARRIER_NUMBER == "MHA-CH-06-TL-21"
    assert drawing.TABLE_LOCATION_PLACES == spec.STATION_PLACES == 2
    assert not any("Location" in p for p in part._SAVED_DRAWING_PROPERTIES)
    for name, feature in _features().items():
        if name.startswith("stop_hole_"):
            assert {"station", "height"} <= set(feature["requirements"]), name
            assert feature["precision"]["station"] == drawing.TABLE_LOCATION_PLACES
            assert feature["precision"]["height"] == drawing.TABLE_LOCATION_PLACES
        elif name.endswith("_hole") or re.fullmatch(r"screw_hole_\d", name):
            assert "station" not in feature and "width" not in feature, name


def test_the_table_runs_from_the_blank_corner_and_identifies_every_row() -> None:
    """Rule 10 / owner review: X/Y LOC from the blank's lower-left corner (the
    model origin, an edge finder's pickup), never a hole centre; the nine
    .XX locations are distinct, so each generated row is one hole."""
    assert len(drawing.TABLE_HOLES) == len(spec.HOLES) == 9
    assert _close(spec.to_riser(spec.BLANK_ORIGIN), (0.0, 0.0), 1e-9)
    for tag, (xy, _dia) in drawing.TABLE_HOLES.items():
        assert drawing.table_location(tag) == xy
        assert 0.0 < xy[0] < spec.BLANK_LENGTH and 0.0 < xy[1] < spec.BLANK_WIDTH
    printed = drawing._PRINTED_LOCATIONS
    assert len(set(printed.values())) == 9
    assert printed["P1"] == (0.29, 0.19) and printed["P2"] == (13.51, 0.19)
    for (x, y), tag in zip(spec.STOP_PIN_HOLES, ("P1", "P2"), strict=True):
        assert _on_inch_grid(x, 2) and _on_inch_grid(y, 2), tag


class _FakeTable:
    """Generated TAG/X/Y cells, as SolidWorks prints them (leading zeros vary)."""

    def __init__(self, rows: list[tuple[str, str, str]]) -> None:
        self.cells = [["TAG", "X LOC", "Y LOC"], *[list(row) for row in rows]]
        self.RowCount = len(self.cells)

    def DisplayedText2(self, row: int, column: int, _calc: bool) -> str:
        return self.cells[row][column]


def _generated_rows(fmt: str = "{:.2f}") -> list[tuple[str, str, str]]:
    return [
        (
            f"A{index}",
            fmt.format(x / INCH),
            fmt.format(y / INCH),
        )
        for index, ((x, y), _dia) in enumerate(drawing.TABLE_HOLES.values(), start=1)
    ]


@pytest.mark.parametrize("fmt", ["{:.2f}", "{:.2f}_strip"])
def test_row_identity_reads_each_rows_own_corner_cells(fmt: str) -> None:
    rows = _generated_rows("{:.2f}")
    if fmt.endswith("_strip"):
        rows = [(tag, x.lstrip("0"), y.lstrip("0")) for tag, x, y in rows]
    table = _FakeTable(list(reversed(rows)))
    holes = drawing._row_holes(table)
    assert sorted(holes.values()) == sorted(drawing.TABLE_HOLES)
    assert holes[1] == list(drawing.TABLE_HOLES)[-1]


@pytest.mark.parametrize("fault", ["precision", "moved", "duplicate", "missing"])
def test_row_identity_refuses_a_wrong_table(fault: str) -> None:
    rows = _generated_rows()
    if fault == "precision":
        rows[0] = (rows[0][0], f"{float(rows[0][1]):.3f}", rows[0][2])
    elif fault == "moved":
        rows[0] = (rows[0][0], f"{float(rows[0][1]) + 0.02:.2f}", rows[0][2])
    elif fault == "duplicate":
        rows[1] = rows[0]
    else:
        rows.pop()
    with pytest.raises(RuntimeError):
        drawing._row_holes(_FakeTable(rows))


def test_generated_table_cells_are_only_read() -> None:
    """Farm r1: generated hole-table cells refuse SetText2. Only the inserted
    NOTE and MATE columns are written; SIZE is read, checked and frozen."""
    source = inspect.getsource(drawing._hole_table)
    writes = re.findall(r"_write_cell\(table, row, (\w+)", source)
    assert set(writes) == {"_TABLE_NOTE_COLUMN", "_TABLE_MATE_COLUMN"}
    assert drawing._TABLE_SIZE_COLUMN == 3
    assert (drawing._TABLE_NOTE_COLUMN, drawing._TABLE_MATE_COLUMN) == (4, 5)
    assert len(drawing.TABLE_WIDTHS) == 6
    assert source.index("generated = _native_sizes(table)") < source.index("InsertColumn2")


def test_view_circles_identify_their_holes_by_centre_axis_and_size() -> None:
    for tag, ((x, y), dia) in drawing.TABLE_HOLES.items():
        circle = (x / 1000.0, y / 1000.0, spec.THICKNESS / 1000.0, 0.0, 0.0, 1.0, dia / 2000.0)
        assert drawing._hole_tag(circle) == tag
    (x, y), dia = drawing.TABLE_HOLES["R1"]
    # The wizard's exact #30 still reads as its hole; the countersink's mouth
    # on the same axis does not.
    actual = spec.SCREW_DRILL_DIA / 2000.0
    assert drawing._hole_tag((x / 1000.0, y / 1000.0, 0.005, 0.0, 0.0, 1.0, actual)) == "R1"
    mouth = spec.CSK_DIA / 2000.0
    assert drawing._hole_tag((x / 1000.0, y / 1000.0, 0.006, 0.0, 0.0, 1.0, mouth)) is None
    assert drawing._hole_tag((x / 1000.0, 0.0, 0.006, 1.0, 0.0, 0.0, dia / 2000.0)) is None


def test_clamp_holes_pass_their_mates_and_meet_the_band_wall_target() -> None:
    """R4: the #9 CL/CR clearances, spotted through TL-21's ordinary #8-32
    taps, keep the .080 target to both self-cut edges with the carrier
    stations' error about the cut's centre. The owner Option B RV-01
    exception (.071 MIN, 2026-11-06) belonged to the retired .257 holes and
    is not carried: no below-target statement or exception remains."""
    lo, _hi = _features()["cl_hole"]["dia"]
    assert lo > THREAD_MAJOR_MM[carrier_spec.CLAMP_THREAD]
    centre = trammel.ARC_CENTRE
    radius = math.dist(trammel.CL, centre)
    hole_r = (spec.CLAMP_DIA + spec.DRILLED_BAND[0]) / 2.0
    error = spec.CLAMP_STATION_ERROR
    inner, outer = spec.CLAMP_BAND_WALLS
    assert inner == pytest.approx(radius - hole_r - error - trammel.RISER_INNER_RADIUS)
    assert outer == pytest.approx(trammel.RISER_OUTER_RADIUS - radius - hole_r - error)
    assert min(inner, outer) >= WALL_TARGET_MM
    assert drawing.PLAIN_CUT_SIZES["CL"] == drawing.PLAIN_CUT_SIZES["CR"] == (
        "\u00d8.196 DRILL THRU"
    )
    assert drawing.native_size_problem("CL", "\u00d8.196 THRU ALL") is None
    assert drawing.native_size_problem("CL", "\u00d8.20 THRU ALL") is not None
    assert drawing.ROW_MATES["CL"] == "TL-21 CL" and drawing.ROW_MATES["CR"] == "TL-21 CR"
    riser = _config.parts("ch-rocker-arm-tl-oblique-riser")
    assert not riser.get("machinist_exceptions")
    # The self-cut stays the approved 9/16 cutter on the strap cutter's centres.
    assert trammel.RISER_CUTTER_IN == "9/16"


# Sheet text at the template's height: about 2.05 mm a character, 4.5 mm tall
# (jig-r6 layout audit); the audit wants 2.26 mm of air between texts.
_CHAR_MM, _TEXT_MM, _AIR_MM = 2.05, 4.5, 2.26
_PLAN_SCALE = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]


def test_stock_width_stands_clear_of_section_a_a() -> None:
    """The stock width's text stands left of section A-A, which shows the
    cross-section upright at 2:1."""
    plan_left = drawing.PLAN_CENTER[0] * 1000.0 - spec.BLANK_LENGTH * _PLAN_SCALE / 2.0
    width_x = plan_left + drawing.PLAN_KEEP["BlankWidth"][0] * _PLAN_SCALE
    width_text = f"{spec.BLANK_WIDTH / INCH:.2f}".lstrip("0")
    section_scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    section_left = drawing.SECTION_CENTER[0] * 1000.0 - spec.THICKNESS * section_scale / 2.0
    assert section_left - (width_x + len(width_text) * _CHAR_MM / 2.0) >= _AIR_MM


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= WALL_TARGET_MM
    assert min(trammel.RISER_SCREW_WALLS) >= WALL_TARGET_MM


def test_drilled_holes_carry_the_title_block_band_only() -> None:
    assert model_toleranced_dimensions(part) == {}


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    """The overalls and thickness print as imported dimensions at their model
    places; every other marked station or size prints as a table row."""
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    printed = set(drawing.PLAN_KEEP) | set(drawing.SECTION_KEEP)
    assert not set(drawing.PLAN_KEEP) & set(drawing.SECTION_KEEP)
    assert printed < marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.IMPORTED_PRECISION == {
        name: spec.DRAWING_PRECISION_BY_NAME[name] for name in printed
    }


_DRAWING_NUMBER = re.compile(r"MHA-[A-Z]{2}(?:-[A-Z]{2})*-\d{2}(?:-[A-Z]{2})*(?:-\d{2})?")


def test_table_cells_and_notes_stay_short_and_name_mates_by_number() -> None:
    """Rule 7: a cell carries its size and process lines plus at most two
    lines of words, and the sheet at most four note lines. Rule 4: every mate
    is a drawing number or a same-parent short form, never a generic noun
    (review: "CL AND CR CLAMPS", "HUB REAMER RELIEF"). Rule 26: size first,
    no millimetres on the inch sheet, the countersink as its symbol."""
    assert len(drawing.TABLE_NOTES) <= 4
    assert spec.DRAWING_NOTES == ""
    for tag, mate in drawing.ROW_MATES.items():
        lines = mate.split("\n")
        assert len(lines) <= 2, tag
        assert lines[0].startswith("TL-21 ") or _DRAWING_NUMBER.search(lines[0]), tag
        assert "CLAMPS" not in mate and "RELIEF" not in mate, tag
    assert drawing.ROW_MATES["HUB"].split("\n")[1] == "CLEARS MHA-CH-13 HUB REAMER"
    assert drawing.STRAP_NUMBER == _config.parts("ch-rocker-strap")["number"]
    assert drawing.ROW_MATES["P1"] == "CLEARS MHA-SM-VN-53 STOP PIN"
    # A plain cut's blank native SIZE moves to its NOTE cell, size first; a
    # wizard row never prints a blank SIZE.
    blank = {tag: "" for tag in drawing.TABLE_HOLES}
    notes = drawing.row_notes(blank)
    for tag in ("HUB", "CL", "CR"):
        assert drawing.native_size_problem(tag, "") is None
        assert notes[tag] == drawing.PLAIN_CUT_SIZES[tag]
        assert notes[tag].startswith("\u00d8.") and notes[tag].endswith("DRILL THRU")
    for tag in ("R1", "P1"):
        assert drawing.native_size_problem(tag, "") is not None
    assert not notes["P1"] and not notes["P2"]
    for note in notes.values():
        assert " MM" not in note and "CSK" not in note
        glyphs = len(note.replace("<HOLE-SINK>", "V"))
        assert glyphs * _CHAR_MM <= drawing.TABLE_WIDTHS[drawing._TABLE_NOTE_COLUMN] * 1000.0
    for text in (*drawing.TABLE_NOTES, *drawing.ROW_MATES.values()):
        for line in text.split("\n"):
            assert len(line) <= 60, line


def test_the_table_and_its_notes_stand_clear_of_the_views_and_title_block() -> None:
    """Under the plan's length line (sheet y 0.180), left of the isometric, the
    MATE column wide enough for its longest line at about 2.05 mm a
    character."""
    plan_bottom = drawing.PLAN_CENTER[1] * 1000.0 - spec.BLANK_WIDTH * _PLAN_SCALE / 2.0
    length_line = plan_bottom + drawing.PLAN_KEEP["BlankLength"][1] * _PLAN_SCALE
    assert length_line - drawing.TABLE_ANCHOR[1] * 1000.0 >= _AIR_MM
    right = (drawing.TABLE_ANCHOR[0] + sum(drawing.TABLE_WIDTHS)) * 1000.0
    assert drawing.ISO_NOTE_XY[0] * 1000.0 - right >= 30.0
    longest = max(
        len(line) for mate in drawing.ROW_MATES.values() for line in mate.split("\n")
    )
    assert drawing.TABLE_WIDTHS[drawing._TABLE_MATE_COLUMN] * 1000.0 >= longest * _CHAR_MM
    assert drawing.TABLE_ANCHOR[0] * 1000.0 >= 12.7 + _AIR_MM


def test_tags_stand_off_the_part_and_clear_the_section_letters() -> None:
    """Rule 14: each tag sits outside the outline on its own leader, apart
    from its neighbours, and clear of A-A's line (through R3) and letters
    (arrows +X, letters 12-22 mm sheet right of the line)."""
    cut = drawing.CUT_X
    for tag, (x, y) in drawing.TAG_XY_MM.items():
        assert y > spec.BLANK_WIDTH or y < 0.0, tag
        assert -10.0 <= x * _PLAN_SCALE and x <= spec.BLANK_LENGTH, tag
        assert abs(x - cut) * _PLAN_SCALE >= 6.0, tag
        assert not cut + 22.0 < x < cut + 46.0, tag
    for side in (lambda y: y > 0.0, lambda y: y < 0.0):
        xs = sorted(x for x, y in drawing.TAG_XY_MM.values() if side(y))
        assert all((b - a) * _PLAN_SCALE >= 3 * _CHAR_MM + _AIR_MM for a, b in zip(xs, xs[1:]))
    assert drawing.SECTION_LINE_STYLE_PREFERENCE == 542
    assert drawing.SECTION_LINE_STYLE == 0
    assert -drawing.CUT_Y[0] * _PLAN_SCALE >= 6.0
    assert (drawing.CUT_Y[1] - spec.BLANK_WIDTH) * _PLAN_SCALE >= 6.0


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-24"


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """Each band endpoint and nominal is a value the inch sheet prints."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert _on_inch_grid(end, places), (name, requirement)
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
                assert _on_inch_grid(nominal, places), (name, requirement)
            checked += 1
    assert checked


def test_one_sheet_and_no_left_clamp_remnants() -> None:
    """R4 omits LEFT: no second sheet, hole, dimension or spec name survives."""
    assert not hasattr(drawing, "SHEET_NAMES")
    assert not hasattr(drawing, "LEFT_CLAMP_DIMENSIONS")
    assert not [n for n in dir(spec) if n.startswith("LEFT")]
    assert not [n for n in drawing.PLAN_KEEP if n.startswith("LeftClamp")]
    assert not [n for n in _features() if n.startswith("left_clamp")]
    assert len(spec.HOLES) == 9
