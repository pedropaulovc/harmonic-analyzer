"""Offline contracts for the oblique-trammel jig's acetal riser (MHA-CH-006-TL-24)."""

from __future__ import annotations

import math
import re

import _config
import build_ch_rocker_arm_tl_oblique_riser as part
import ch_rocker_arm_tl_oblique_riser_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_riser as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions

STEM = "ch_rocker_arm_tl_oblique_riser"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _carrier(xy: tuple[float, float]) -> tuple[float, float]:
    return (
        xy[0] + trammel.RISER_BLANK_ORIGIN[0],
        xy[1] + trammel.RISER_BLANK_ORIGIN[1],
    )


def _close(a: tuple[float, float], b: tuple[float, float], tol: float) -> bool:
    return math.dist(a, b) <= tol


def test_hole_positions_map_back_to_the_calculator() -> None:
    # Reference stations at 2 places: within half a unit of the second place.
    tol = 0.005 * math.sqrt(2.0)
    assert len(spec.SCREW_HOLES) == len(trammel.RISER_SCREWS) == 4
    for riser, carrier in zip(spec.SCREW_HOLES, trammel.RISER_SCREWS, strict=True):
        assert _close(_carrier(riser), carrier, tol)
    assert _close(_carrier(spec.HUB_HOLE), trammel.HUB, tol)
    assert _close(_carrier(spec.CL_HOLE), trammel.CL, tol)
    assert _close(_carrier(spec.CR_HOLE), trammel.CR, tol)
    features = _features()
    for name, carrier in (
        *(
            (f"screw_hole_{i}", xy)
            for i, xy in enumerate(trammel.RISER_SCREWS, start=1)
        ),
        ("hub_hole", trammel.HUB),
        ("cl_hole", trammel.CL),
        ("cr_hole", trammel.CR),
    ):
        feature = features[name]
        exported = (feature["station_nominal"], feature["width_nominal"])
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
    for xy, dia, _names, _drives in spec.CIRCLES:
        assert xy in (spec.HUB_HOLE, spec.CL_HOLE, spec.CR_HOLE)
        assert dia in (spec.HUB_DIA, spec.CLAMP_DIA)


def test_blank_and_holes_are_the_part_sheet() -> None:
    assert (
        (spec.BLANK_LENGTH, spec.BLANK_WIDTH, spec.THICKNESS)
        == (
            trammel.RISER_BLANK_LENGTH,
            trammel.RISER_BLANK_WIDTH,
            trammel.RISER_THICK,
        )
        == (340.0, 40.0, 6.0)
    )
    assert spec.HUB_DIA == 12.0 and spec.CLAMP_DIA == 6.6
    assert spec.SCREW_SPEC.kind == "clearance" and spec.SCREW_SPEC.size == "#4"
    assert trammel.RISER_SCREW == "#4-40"
    # The HUB clearance passes the HUB pin's Ø10.20 section.
    assert spec.HUB_DIA > 10.20


def test_flat_head_sinks_and_countersink_stays_in_the_blank() -> None:
    csk = _features()["screw_hole_1_countersink"]
    assert csk["angle_deg"] == 82.0
    assert csk["dia"][0] >= spec.SCREW_HEAD_DIA_MAX
    assert spec.CSK_DEPTH_MAX < spec.THICKNESS
    assert _features()["screw_hole_1"]["dia"][0] > spec.SCREW_BODY_DIA


def test_the_screw_hole_has_one_callout_naming_its_countersink() -> None:
    """Review r5: one callout, Ø3.26 at 2 places (the DRILLED HOLES row bands
    it) with the countersink below it."""
    assert spec.SCREW_DIA_PRINTED == 3.26 and spec.SCREW_DIA_PLACES == 2
    assert spec.GLOBALS["ScrewDia"] == spec.SCREW_DIA_PRINTED
    lo, hi = _features()["screw_hole_1"]["dia"]
    assert lo <= spec.SCREW_DIA <= hi
    assert spec.CALLOUTS_ABOVE["ScrewDia"] == "4X"
    assert spec.CALLOUTS_BELOW["ScrewDia"].split("\n")[:2] == [
        "DRILL THRU",
        "CSK<MOD-DIAM>6.30 X 82°",
    ]
    assert "CskDia" not in set().union(*spec.DRAWING_DIMENSIONS.values())


def test_hole_locations_are_reference_values_from_the_carrier() -> None:
    """TrammelJig ruling: every hole is spotted from TL-21 at assembly, so its
    stations print as parenthesised 2-place references and each hole callout
    ends in the location rows (review r7: not a general note); only the sizes
    stay banded."""
    stations = set().union(*spec.DRAWING_DIMENSIONS.values()) - {
        "BlankLength",
        "BlankWidth",
        "BlankThick",
        *spec.HOLE_CALLOUTS,
    }
    assert spec.REFERENCE_DIMENSIONS == stations
    assert all(spec.DRAWING_PRECISION_BY_NAME[n] == 2 for n in stations)
    carrier_number = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
    rows = [f"LOCATE FROM {carrier_number}", "AT ASSEMBLY"]
    assert set(spec.HOLE_CALLOUTS) == {"ScrewDia", "HubDia", "ClampDia"}
    for name in spec.HOLE_CALLOUTS:
        assert spec.CALLOUTS_BELOW[name].split("\n")[-2:] == rows, name
    assert spec.DRAWING_NOTES == ""
    assert not any("Location" in p for p in part._SAVED_DRAWING_PROPERTIES)
    for name, feature in _features().items():
        if name.endswith("_hole") or re.fullmatch(r"screw_hole_\d", name):
            assert "station" not in feature and "width" not in feature, name


def test_clamp_holes_pass_their_mates_and_hold_the_band_walls() -> None:
    lo, _hi = _features()["cl_hole"]["dia"]
    assert lo > spec.CL_DOWEL_MAX == 6.012
    assert lo > spec.CR_SCREW_MAJOR == 6.35
    inner, outer = spec.CLAMP_BAND_WALLS
    assert f"{outer:.3f}" == "2.019" and inner > outer >= 2.0


def test_each_row_count_matches_the_holes_on_that_row() -> None:
    """Review r5: a 2X row height names exactly the two holes on its row, and
    its dimension stands right of the view so the extension line from the
    dimensioned left hole runs through its partner."""
    rows = {
        "ScrewInnerY": [
            xy for xy in spec.SCREW_HOLES if xy[1] == spec.GLOBALS["ScrewInnerY"]
        ],
        "ScrewOuterY": [
            xy for xy in spec.SCREW_HOLES if xy[1] == spec.GLOBALS["ScrewOuterY"]
        ],
        "ClampY": [spec.CL_HOLE, spec.CR_HOLE],
    }
    all_holes = [*spec.SCREW_HOLES, spec.HUB_HOLE, spec.CL_HOLE, spec.CR_HOLE]
    for name, holes in rows.items():
        on_row = [xy for xy in all_holes if xy[1] == spec.GLOBALS[name]]
        assert on_row == holes and len(holes) == 2, name
        assert spec.ROW_COUNTS[name] == "2X"
        assert drawing.PLAN_KEEP[name][0] > spec.BLANK_LENGTH
    assert [xy for xy in all_holes if xy[1] == spec.GLOBALS["HubY"]] == [spec.HUB_HOLE]
    assert "HubY" not in spec.ROW_COUNTS
    assert not set(spec.ROW_COUNTS) & set(spec.CALLOUTS_ABOVE)


# Sheet text at the template's height: about 2.05 mm a character, 4.5 mm tall
# (jig-r6 layout audit); the audit wants 2.26 mm of air between texts.
_CHAR_MM, _TEXT_MM, _AIR_MM = 2.05, 4.5, 2.26
_PLAN_SCALE = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]


def test_row_heights_stand_a_text_width_apart() -> None:
    """jig-r6: the right-hand row heights overprinted each other. Each one-line
    "2X (dd.dd)" clears its neighbour's, and the first clears the outline."""
    names = ["ClampY", "ScrewOuterY", "ScrewInnerY"]
    xs = [drawing.PLAN_KEEP[n][0] * _PLAN_SCALE for n in names]
    assert xs == sorted(xs)
    half = len("2X (00.00)") * _CHAR_MM / 2.0
    assert xs[0] - half - spec.BLANK_LENGTH * _PLAN_SCALE >= _AIR_MM
    assert all(b - a >= 2.0 * half + _AIR_MM for a, b in zip(xs, xs[1:]))
    width_x = drawing.PLAN_KEEP["BlankWidth"][0] * _PLAN_SCALE
    assert width_x - xs[-1] >= half + len("STOCK") * _CHAR_MM / 2.0 + _AIR_MM
    # Each count's text fits between its own extension lines.
    for name in names:
        assert spec.GLOBALS[name] * _PLAN_SCALE > _TEXT_MM + 1.0, name


def test_x_stack_rows_leave_air_and_the_section_letters_clear() -> None:
    """jig-r6: the X stack's texts stood 0.48 mm apart, CL's text sat on the
    baseline extension, and the section letter sat on HubX's extension."""
    rows = [
        drawing.PLAN_KEEP[n][1] * _PLAN_SCALE
        for n in (
            "ClX",
            "Screw3X",
            "Screw1X",
            "HubX",
            "Screw2X",
            "Screw4X",
            "CrX",
            "BlankLength",
        )
    ]
    assert all(a - b - _TEXT_MM >= 4.52 for a, b in zip(rows, rows[1:]))
    cl_text_right = (
        drawing.PLAN_KEEP["ClX"][0] * _PLAN_SCALE + len("(9.11)") * _CHAR_MM / 2.0
    )
    assert cl_text_right <= -_AIR_MM
    # Review r7: the HUB row height's dimension line and arrows ran down
    # through "(9.11)"; its line and its own text stand left of CL's text.
    cl_text_left = (
        drawing.PLAN_KEEP["ClX"][0] * _PLAN_SCALE - len("(9.11)") * _CHAR_MM / 2.0
    )
    hub_x = drawing.PLAN_KEEP["HubY"][0] * _PLAN_SCALE
    assert cl_text_left - (hub_x + len("(29.53)") * _CHAR_MM / 2.0) >= _AIR_MM
    # The arrows point +X; each letter stands 14-20 mm (sheet) past the line.
    cut = drawing.CUT_X * _PLAN_SCALE
    stations = sorted(
        x * _PLAN_SCALE
        for x, _y in (*spec.SCREW_HOLES, spec.HUB_HOLE, spec.CL_HOLE, spec.CR_HOLE)
    )
    assert not [s for s in stations if cut + 12.0 < s < cut + 22.0]
    assert -drawing.CUT_Y[0] * _PLAN_SCALE >= 6.0
    assert (drawing.CUT_Y[1] - spec.BLANK_WIDTH) * _PLAN_SCALE >= 6.0


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= 2.0
    assert min(trammel.RISER_SCREW_WALLS) >= 2.0


def test_drilled_holes_carry_the_title_block_band_only() -> None:
    assert model_toleranced_dimensions(part) == {}


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PLAN_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.PLAN_KEEP) & set(drawing.SECTION_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.CALLOUTS_ABOVE) | set(spec.CALLOUTS_BELOW) <= marked


def test_sheet_carries_no_notes_and_short_callouts() -> None:
    """No general notes; callout rows stay short (the location row, naming the
    carrier's number, is the longest)."""
    assert spec.DRAWING_NOTES == ""
    for text in (*spec.CALLOUTS_ABOVE.values(), *spec.CALLOUTS_BELOW.values()):
        for line in text.split("\n"):
            assert len(line.replace("<MOD-DIAM>", " Ø")) <= 28, line


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-006-TL-24"


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (name, requirement)
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
                assert abs(nominal - round(nominal, places)) < 1e-9, (name, requirement)
            checked += 1
    assert checked


def test_clamp_callout_stands_left_of_and_above_the_cutting_plane() -> None:
    # Review r12: at model X -20 the CL block's shelf ended on the upper A-A
    # arrow's tail and its leader crossed the plane at screw 3.
    x, y, _ = drawing.PLAN_KEEP["ClampDia"]
    assert x == -26.0
    assert y == drawing._CALLOUT_Y + 10.0
    assert x < drawing.CUT_X
