"""Offline contracts for the oblique-trammel carrier plate (MHA-CH-06-TL-21)."""

from __future__ import annotations

import inspect
import math
import re
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_carrier as part
import ch_rocker_arm_tl_oblique_carrier_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_carrier as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _feature_requirements import requirements_for
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm

STEM = "ch_rocker_arm_tl_oblique_carrier"
INCH = 25.4


def _printed(value_mm: float, places: int) -> float:
    """``value_mm`` as the inch sheet prints it at ``places``, in mm."""
    return round(value_mm / INCH, places) * INCH


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _at(feature: dict) -> tuple[float, float]:
    """A feature's model point back in the carrier frame (X, Y)."""
    x, _y, z = feature["at"]
    return x, -z


def test_interface_contract() -> None:
    # The outline is symmetric about the tap axis and every edge the sheet
    # prints lands on its inch grid.
    assert spec.OUTLINE_X[0] == -spec.OUTLINE_X[1]
    places = spec.DRAWING_PRECISION_BY_NAME
    assert spec.prints_exactly(spec.PLATE_LENGTH, places["PlateLength"])
    assert spec.prints_exactly(spec.PLATE_WIDTH, places["PlateWidth"])
    assert spec.prints_exactly(-spec.OUTLINE_Y[0], places["PlateNearY"])
    assert spec.THICKNESS == trammel.CARRIER_THICK
    # The lever taps stand on the tap axis, below the pin line, inside the
    # plate, the inner one past the lever's slot end.
    for x, y in spec.LEVER_HOLES:
        assert x == 0.0 and spec.OUTLINE_Y[0] < y < spec.LEVER_INNER_END_Y < 0.0
        assert spec.prints_exactly(y, places["LeverY1"])


def test_every_calculator_position_is_the_calculators() -> None:
    features = _features()
    expected = {
        "pin_hole_a1": trammel.A1,
        "pin_hole_b1": trammel.B1,
        "pin_hole_a2": trammel.A2,
        "pin_hole_b2": trammel.B2,
        "hub_spot": trammel.HUB,
        "cl_spot": trammel.CL,
        "cr_tap_1": trammel.CR,
        **{
            f"riser_tap_{i}": point
            for i, point in enumerate(trammel.RISER_SCREWS, start=1)
        },
    }
    for name, point in expected.items():
        assert _at(features[name]) == tuple(point), name
    assert spec.PIN_HOLES == trammel.PIN_HOLES
    assert (spec.HUB, spec.CL, spec.CR) == (trammel.HUB, trammel.CL, trammel.CR)
    assert spec.RISER_SCREWS == trammel.RISER_SCREWS
    assert spec.D1 == trammel.D1
    assert math.isclose(-spec.A2_DX, (trammel.D2 - trammel.D1) / 2.0)
    assert spec.A2_DY == trammel.A2[1]
    # The chain prints what the calculator gives.
    b1, a2 = features["pin_hole_b1"], features["pin_hole_a2"]
    assert b1["station_nominal"] == pytest.approx(_printed(trammel.D1, 4))
    assert a2["station_nominal"] == pytest.approx(_printed(abs(trammel.A2[0] - trammel.A1[0]), 4))
    assert a2["height_nominal"] == pytest.approx(_printed(trammel.A2[1], 4))


def test_pin_chain_runs_from_a1_b1_with_banded_mates() -> None:
    features = _features()
    assert features["pin_hole_b1"]["parent"] == "pin_hole_a1"
    assert features["pin_hole_a2"]["parent"] == "pin_hole_a1"
    assert features["pin_hole_b2"]["height_from"] == "pin_hole_b1"
    for name in ("pin_hole_b1", "pin_hole_a2", "pin_hole_b2"):
        low, high = features[name]["station"]
        assert math.isclose(high - low, 2.0 * spec.POSITION_BAND)
    # Rule 4 (jig-r3): each band names what it sets and on which part, not
    # its sensitivity.
    assert spec.SPACING_CALLOUT == "SETS R800 ON\nMHA-CH-13"
    assert spec.DX_CALLOUT == spec.DY_CALLOUT == "SETS R816 ON\nMHA-CH-13"
    for text in spec.CALLOUTS_BELOW.values():
        assert "ERROR" not in text and "1:1" not in text
    # The tap axis (lever taps and HUB) is located from A1, the X datum, at
    # HubX's places: HubX prints it from A1 to the HUB spot (driven equal to
    # A1X, the model's unprinted driver).
    a1 = features["pin_hole_a1"]
    places = spec.DRAWING_PRECISION_BY_NAME["HubX"]
    assert a1["station_nominal"] == pytest.approx(_printed(abs(trammel.A1[0]), places))
    assert a1["precision"]["station"] == places
    assert "A1X" not in spec.DRAWING_DIMENSIONS["PinHoleProfile"]
    assert "HubX" in spec.DRAWING_DIMENSIONS[spec.STATION_REFERENCE]
    assert set(spec.POSITION_BANDED) <= set(spec.CALLOUTS_BELOW)
    toleranced = model_toleranced_dimensions(part)
    assert toleranced[("PinHoleProfile", "PinHoleDia")] == "*deviations(PIN_HOLE_BAND)"
    assert ("PinHoleProfile", "dimension_name") in toleranced


def test_pin_holes_are_slide_reamed_and_name_the_pin() -> None:
    hole = _features()["pin_hole_a1"]
    assert hole["dia"] == pytest.approx(
        [spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[1], spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[0]]
    )
    # The REAM_SLIDE hole always clears the bought shoulder (the trammel's
    # radius error reads this clearance).
    assert 0.0 < spec.PIN_CLEARANCE_MIN < spec.PIN_CLEARANCE_MAX
    assert (spec.PIN_CLEARANCE_MIN, spec.PIN_CLEARANCE_MAX) == pytest.approx(
        trammel.SHOULDER_CARRIER_CLEARANCE
    )
    assert "MHA-CH-06-TL-VN-77 SHOULDER SCREW" in hole["note"]
    assert "REAM THRU" in hole["note"]


def test_taps_are_unc_and_hold_rule_18() -> None:
    features = _features()
    assert features["cr_tap_1"]["thread"] == "1/4-20 UNC-2B"
    assert features["riser_tap_1"]["thread"] == "#4-40 UNC-2B"
    assert features["lever_tap_1"]["thread"] == "5/16-18 UNC-2B"
    # Full thread only: the plate at its .X low limit less the tap mouth's
    # edge break and one pitch of incomplete lead.
    for thread in (spec.CR_THREAD, spec.RISER_THREAD, spec.LEVER_THREAD):
        pitch = 25.4 / float(thread.rsplit("-", 1)[1])
        band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["StockThick"], unit=spec.UNIT)
        full = spec.THICKNESS - band - spec.TAP_MOUTH_BREAK - pitch
        assert math.isclose(spec.ENGAGEMENT_MM[thread], full), thread
    for thread in (spec.CR_THREAD, spec.RISER_THREAD):
        assert spec.ENGAGEMENT_MM[thread] >= 1.5 * THREAD_MAJOR_MM[thread]
    # A finished 12 plate still cannot hold 1.5D of 5/16-18. The lever callout
    # retains the existing RV-01 shortfall as a plain fact, floored (rule 20).
    lever = spec.LEVER_THREAD
    assert spec.ENGAGEMENT_MM[lever] < 1.5 * THREAD_MAJOR_MM[lever]
    assert spec.SHORT_ENGAGEMENT == (lever,)
    assert "part_spec.LEVER_TAP_CALLOUT" in inspect.getsource(drawing.build)
    assert spec.CR_HEAD_DIA_MAX <= spec.CR_HEAD_CLEAR_DIA


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= WALL_TARGET_MM


def test_no_skid_sag_is_negligible() -> None:
    assert round(spec.SAG_SELF_WEIGHT, 2) == 0.02
    assert round(spec.SAG_CUTTING_LOAD, 3) == 0.015
    assert "No skid" in spec.__doc__


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.TOP_KEEP) | set(drawing.SECTION_KEEP_MODEL_MM) == marked
    assert not set(drawing.TOP_KEEP) & set(drawing.SECTION_KEEP_MODEL_MM)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.CALLOUT_SUFFIXES) <= marked
    assert set(spec.CALLOUT_PREFIXES) <= marked
    assert set(spec.CALLOUTS_BELOW) <= marked
    # Above-callouts cannot print a line break (pn_pen_v_block_spec): none.
    assert not hasattr(spec, "CALLOUTS_ABOVE")


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """Each band endpoint is a value the inch sheet prints at its places."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                inches = end / INCH
                assert abs(inches - round(inches, places)) < 1e-9, (name, requirement)
            checked += 1
    assert checked


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-21"


def test_cl_dowel_is_a_press_in_its_finished_hole() -> None:
    # The bought 1/4 dowel always presses into the in-place reamed hole.
    low, high = spec.CL_DOWEL_INTERFERENCE
    assert 0.0 < low < high
    assert (low, high) == pytest.approx((
        min(spec.CL_DOWEL_BAND) - max(spec.CL_HOLE_BAND),
        max(spec.CL_DOWEL_BAND) - min(spec.CL_HOLE_BAND),
    ))


def test_bottom_face_preserves_the_finished_plate_thickness() -> None:
    bottom = requirements_for(drawing)["bottom_face"]
    (face,) = bottom.faces
    assert face.normal == (0.0, -1.0, 0.0)
    assert face.offset_mm == spec.THICKNESS
    feature = _features()["bottom_face"]
    assert feature["normal"] == [0.0, -1.0, 0.0]
    assert feature["plane"] == {
        "frame": "model",
        "axis": "y",
        "value": -spec.THICKNESS,
    }
    assert feature["height_nominal"] == spec.THICKNESS
    assert feature["height"] == pytest.approx([
        spec.THICKNESS - spec.THICKNESS_BAND,
        spec.THICKNESS + spec.THICKNESS_BAND,
    ])


def test_spot_stations_print_from_the_hidden_reference_sketch() -> None:
    """A reference plane cannot be imported into a drawing (farm jig-r1)."""
    assert spec.DRAWING_DIMENSIONS[spec.SPOT_REFERENCE] == {
        "SpotDia",
        "SpotDiaCl",
        "HubY",
        "ClY",
    }
    # jig-r3: each spot has its own leader and callout, no "2X".
    for name in ("SpotDia", "SpotDiaCl"):
        assert "2X" not in spec.CALLOUTS_BELOW[name]
    assert set(spec.CALLOUT_SUFFIXES) == {"SpotDia", "SpotDiaCl"}
    assert not any("Plane" in feature for feature in spec.DRAWING_DIMENSIONS)


def test_hub_station_moves_the_strap_pivot_inside_its_top_edge_band() -> None:
    """The HUB sits on the arcs' centreline, so its Y station moves the
    strap's pivot radially 1:1 against the R800 edge; its print band must
    stay strictly inside half the strap's one-sided top-edge band."""
    import ch_rocker_arm_spec as rocker

    assert spec.HUB[0] == trammel.ARC_CENTRE[0] == 0.0
    half = (max(rocker.TOP_EDGE_BAND) - min(rocker.TOP_EDGE_BAND)) / 2.0
    places = spec.DRAWING_PRECISION_BY_NAME["HubY"]
    assert spec.HUB_RADIAL_BAND == pytest.approx(printed_band_mm(places, unit=spec.UNIT))
    assert spec.HUB_RADIAL_BAND < half
    # One place fewer would take the whole half band.
    assert printed_band_mm(places - 1, unit=spec.UNIT) >= half


def test_three_place_hub_and_cr_stations_state_true_functions() -> None:
    """mr4: 8.861 and CR's 15.195/1.156 printed 3-place with no stated
    function. HubX runs to the HUB spot (mr8: named by the spot's callout,
    not the undefined A1-B1); CR is CL mirrored about the tap axis, so the
    CR callout (whose lanes hold no row) names it."""
    assert spec.STATIONS["HubX"] == spec.HUB
    assert spec.HUB[0] == trammel.ARC_CENTRE[0] == 0.0
    assert spec.CR == pytest.approx((-spec.CL[0], spec.CL[1]))


def test_pin_chamfer_retains_the_spacer_thrust_seat() -> None:
    """The entry break leaves a broad seat on the purchased spacer."""
    import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer

    mouth = (spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[0]) / 2.0 + spec.PIN_CHAMFER
    assert mouth + spec.PIN_CHAMFER_BAND[0] < (
        pivot_spacer.OD + pivot_spacer.OD_BAND[1]
    ) / 2.0
    assert spec.SECTION_REFERENCE in spec.REFERENCE_SKETCHES
    assert spec.DRAWING_DIMENSIONS[spec.SECTION_REFERENCE] == {
        "PinChamferSize",
        "StockThick",
    }
    assert spec.prints_exactly(
        spec.PIN_CHAMFER, spec.DRAWING_PRECISION_BY_NAME["PinChamferSize"]
    )
    callout = spec.CALLOUTS_BELOW["PinChamferSize"]
    assert "UNDERSIDE" in callout and "TL-VN-78 SPACER" in callout
    assert spec.PIN_CHAMFER_TOL_TYPE == 5  # swTolMIN
    assert part.V_PIN_CHAMFER > 0.0


def test_section_reference_is_on_its_own_hidden_cutting_plane() -> None:
    """jig-r6: on the bare Front plane the section's import came back empty;
    every fleet section that imports a sketch has it on a dedicated named
    plane in the cut (pd_platen, the pivot block, fr_nameplate)."""
    assert spec.SECTION_PLANE == "SectionAPlane"
    source = inspect.getsource(part._section_reference)
    assert "create_sketch(SECTION_PLANE)" in source
    assert 'create_sketch("Front")' not in source
    assert "_require_on_section_plane(adapter, feature)" in source
    plane = inspect.getsource(part._section_plane)
    assert "InsertRefPlane(4," in plane
    assert 'blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))' in plane




def test_section_imports_one_hidden_sketch_and_no_body_feature() -> None:
    """jig-r4/r5: asked for Plate's depth and the reference sketch's leg, the
    section imported nothing at all; the finished thickness is a
    SectionReference dimension driven from Plate's depth, so the section's
    import stays one hidden sketch in its plane (pd_platen A-A, pivot block
    B-B)."""
    owners = {
        feature
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        if names & set(drawing.SECTION_KEEP_MODEL_MM)
    }
    assert owners == {spec.SECTION_REFERENCE}
    assert "Plate" not in spec.DRAWING_DIMENSIONS
    assert "StockThick" not in spec.CALLOUTS_BELOW
    assert (spec.SECTION_REFERENCE, "StockThick") not in model_toleranced_dimensions(
        part
    )
    source = inspect.getsource(part)
    assert '"StockThick", \'"PlateThick@Plate"\'' in source
    assert "PIN_CHAMFER_REFERENCE" not in source
    # The stock line stands in A1's +X wall, inside the cut, near its end.
    wall = spec.PIN_HOLE_DIA / 2.0
    assert wall + 2.0 <= spec.STOCK_REFERENCE_DX < drawing._SECTION_HALF
    assert drawing._SECTION_HALF == spec.SECTION_HALF_SPAN
    # Carrier r11/r13: the 12.0's extension lines ran from ~863 mm right of
    # the slab whatever the view's place. The text stands on A1's -X side and
    # its extension lines are capped to stop 1.5 sheet mm short of the slab's
    # -X end, so an origin anywhere on the +X side leaves the same short pair.
    text_dx = drawing.SECTION_KEEP_MODEL_MM["StockThick"][0] - spec.PIN_HOLES["A1"][0]
    assert -text_dx > drawing._SECTION_HALF
    scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    gap = (-text_dx - drawing._SECTION_HALF) * scale
    assert math.isclose(drawing.STOCK_WITNESS_MAX_M * 1000.0, gap - 1.5)
    assert drawing.STOCK_WITNESS_MAX_M > 0.005
    again = inspect.getsource(drawing._reposition_section_dimensions)
    assert "display.MaxWitnessLineLength = STOCK_WITNESS_MAX_M" in again


def test_section_is_full_and_cropped_to_the_cut_span() -> None:
    """carrier-diag: through this short interior line the PARTIAL section
    imported no marked dimension at all, while a full section through the
    same line, same base-view selection, imported PinChamferSize and
    StockThick. So A-A is full and cropped to A1's slab (fr_nameplate A-A's
    Crop2 fence). jig-r9/c4-r4: imported after the crop it lost StockThick,
    so it is curated first, then cropped, centred and placed again."""
    source = inspect.getsource(drawing._pin_section)
    assert "partial=False" in source
    assert "partial=True" not in source
    order = [
        source.index(call)
        for call in (
            "create_section_view(",
            "curate_view_dimensions(",
            "_crop_section(adapter, section)",
            "_centre_section(adapter, section)",
            "_reposition_section_dimensions(adapter, section, annotations)",
        )
    ]
    assert order == sorted(order)
    again = inspect.getsource(drawing._reposition_section_dimensions)
    assert "reposition=keep" in again and ".Visible" in again
    crop = inspect.getsource(drawing._crop_section)
    assert "Crop2(False, True, 0)" in crop
    assert "IsCropped()" in crop
    # jig-r8: the outline ran 25.6 mm past the 72 mm fence, so the check is
    # containment plus the shrink, not width equality.
    assert "not contains" in crop
    assert "width + 0.025" not in crop
    a1x = spec.PIN_HOLES["A1"][0]
    (x0, y0, _), (x1, y1, _) = drawing.SECTION_CROP_MODEL_MM
    assert math.isclose(x0, a1x - drawing._SECTION_HALF)
    assert math.isclose(x1, a1x + drawing._SECTION_HALF)
    assert y0 < -spec.THICKNESS and y1 > 0.0
    # Both kept texts' features lie inside the fence: the chamfer at A1's
    # wall and the stock line inside the cut's +X end.
    assert x0 < a1x - spec.PIN_HOLE_DIA / 2.0
    assert a1x + spec.STOCK_REFERENCE_DX < x1


def test_riser_tap_stations_print_their_walls_band_and_name_the_riser() -> None:
    """The riser is self-cut along the jig's band and spotted through these
    taps, so trammel.RISER_SCREW_WALLS assumes their stations at its places."""
    places = trammel.RISER_TAP_STATION_PLACES
    assert spec.RISER_STATION_PLACES == places == 3
    for name in ("RiserX1", "RiserX1R", "RiserY1", "RiserX2", "RiserX2R", "RiserY2"):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == places, name
    features = _features()
    for index, (x, y) in enumerate(spec.RISER_SCREWS, start=1):
        tap = features[f"riser_tap_{index}"]
        assert tap["precision"]["station"] == tap["precision"]["height"] == places
        assert tap["station_nominal"] == pytest.approx(
            _printed(x - spec.PIN_HOLES["A1"][0], places)
        )
        assert tap["height_nominal"] == pytest.approx(_printed(y, places))
    riser = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
    assert riser == "MHA-CH-06-TL-24"
    assert spec.RISER_TAP_CALLOUT == (f"HOLDS {riser} SCREWS\nCLEAR OF ITS CUT EDGES")
    # Rule 4 (carrier r11): each 3-place station names what it locates, by
    # the tool number the hole callout spells out in full.
    assert spec.DRAWING_DIMENSIONS["RiserTaps"] == {"RiserY1", "RiserY2"}
    assert set(spec.RISER_STATIONS) - {"RiserY1", "RiserY2"} <= set(spec.STATIONS)
    assert riser.endswith(spec.RISER_TOOL_ID) and spec.RISER_TOOL_ID == "TL-24"
    for name in spec.RISER_STATIONS:
        assert spec.CALLOUTS_BELOW[name] == "LOCATES TL-24", name
    assert min(trammel.RISER_SCREW_WALLS) >= WALL_TARGET_MM
    # From A1 the station error about the cut's centre adds half the D1 band.
    assert WALL_TARGET_MM <= spec.RISER_WALLS_FROM_A1 < min(trammel.RISER_SCREW_WALLS)
    # Four rows (the native two and these two), ~4.5 mm each, centred on the
    # anchor: under the border, over the HUB spot's callout.
    rows = 2 + len(spec.RISER_TAP_CALLOUT.splitlines())
    x, y = (value * 1000.0 for value in drawing.RISER_CALLOUT_XY)
    assert y + 4.5 * rows / 2.0 + 3.0 < _BORDER[3]
    half = 2.36 * max(len(row) for row in spec.RISER_TAP_CALLOUT.splitlines()) / 2.0
    assert x + half < drawing.CR_CALLOUT_XY[0] * 1000.0 - 25.0 + 2.0
    source = inspect.getsource(drawing.build)
    assert "part_spec.RISER_TAP_CALLOUT" in source


def test_riser_heights_cover_both_holes_of_their_row() -> None:
    """Carrier-r1 review: the +X riser pair read as unlocated in Y. Each +X
    screw shares its -X twin's height in the tap sketch, so each printed
    height is 2X."""
    screws = spec.RISER_SCREWS
    assert screws[1][1] == screws[0][1] and screws[3][1] == screws[2][1]
    assert screws[1][0] == -screws[0][0] and screws[3][0] == -screws[2][0]
    source = inspect.getsource(part)
    assert '(("RiserX1ROrigin", _origin_x("RiserX1R")), SharedCoordinate(0))' in source
    assert '(("RiserX2ROrigin", _origin_x("RiserX2R")), SharedCoordinate(2))' in source
    assert spec.CALLOUT_PREFIXES == {"RiserY1": "2X ", "RiserY2": "2X "}
    build = inspect.getsource(drawing.build)
    assert "_set_callout_texts(adapter, annotations, CALLOUT_PREFIXES, part=1)" in build


def test_every_x_station_is_a_baseline_from_a1() -> None:
    """Machinist review 41bbeec (r1/r2 clarity.1): X ran from three origins
    (the left end, A1 and the tap axis). One X datum, A1's axis: every X
    station prints from it (rule 10)."""
    a1x = spec.PIN_HOLES["A1"][0]
    assert spec.DRAWING_DIMENSIONS[spec.STATION_REFERENCE] == set(spec.STATIONS)
    other_x = {
        name
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        if feature != spec.STATION_REFERENCE
        for name in names
        if "X" in name
    }
    # The pin chain stays on the pin-hole sketch, A1 its root; the tap axis
    # prints from A1 as a station (HubX), not as the unprinted A1X.
    assert other_x == {"A2DX", "B2DX"}
    assert "PlateHalfLength" not in spec.DRAWING_DIMENSIONS["PlateProfile"]
    assert spec.DRAWING_DIMENSIONS["CrTap"] == {"CrY"}
    assert spec.STATION_REFERENCE in spec.REFERENCE_SKETCHES
    assert spec.STATIONS["EdgeX"] == (spec.OUTLINE_X[0], spec.OUTLINE_Y[0])
    assert spec.STATIONS["ClX"] == spec.CL and spec.STATIONS["CrX"] == spec.CR
    assert spec.STATIONS["HubX"] == spec.HUB
    features = _features()
    located = ("hub_spot", "cl_spot", "cr_tap_1", "lever_tap_1", "lever_tap_2")
    for name in located + tuple(f"riser_tap_{i}" for i in range(1, 5)):
        feature = features[name]
        places = feature["precision"]["station"]
        assert feature["parent"] == "pin_hole_a1", name
        assert feature["station_nominal"] == pytest.approx(
            _printed(_at(feature)[0] - a1x, places)
        ), name
    # The tap axis prints once, as HubX: its point on the HUB spot, so its
    # extension line rises through the lever taps to it (machinist review
    # 54e5c9a: A1X's line stopped at the pin line, short of HUB).
    hub_x = features["hub_spot"]["station_nominal"]
    assert features["lever_tap_1"]["station_nominal"] == hub_x
    assert hub_x == features["pin_hole_a1"]["station_nominal"]
    stations = inspect.getsource(part._station_reference)
    assert '"HubX": _pin_dim("A1X")' in stations
    assert '"HubX": f\'"HubY@{SPOT_REFERENCE}"\'' in stations
    # Each origin-based placement evaluates to the feature's |X| from its
    # printed station less A1X.
    values = {"A1X@PinHoleProfile": abs(a1x)} | {
        f"{name}@{spec.STATION_REFERENCE}": abs(x - a1x)
        for name, (x, _y) in spec.STATIONS.items()
    }
    for name, (x, _y) in spec.STATIONS.items():
        if name in ("EdgeX", "HubX"):
            continue
        expression = part._origin_x(name)
        for key, value in values.items():
            expression = expression.replace(f'"{key}"', repr(value))
        assert math.isclose(eval(expression), abs(x), abs_tol=1e-9), name
    # Each X text stands within its own span, between A1 and its feature.
    a1_sheet = _on_sheet(a1x, 0.0)[0]
    for name, (x, _y) in spec.STATIONS.items():
        ends = sorted((a1_sheet, _on_sheet(x, 0.0)[0]))
        assert ends[0] < _top_text(name)[0] < ends[1], name
    # Machinist review 07a6786: the 34.9's arrows went outside its short span
    # and its line ran on into the REAM leader; they are held inside.
    assert '_arrows_inside(adapter, annotations, "EdgeX")' in inspect.getsource(
        drawing.build
    )
    assert drawing._ARROWS_INSIDE == 0  # swDimArrowsInside


def test_section_line_prints_its_ends_only() -> None:
    """Carrier-r1 review: A-A's chain line along the pin line read as the
    origin of every Y dimension. swDetailingSectionViewLineStyleDisplay (542)
    StandardWithoutConnector (1) prints its end segments only, set before the
    section is cut."""
    build = inspect.getsource(drawing.build)
    assert "SetUserPreferenceInteger(542, 0, 1)" in build
    assert "GetUserPreferenceInteger(542, 0) != 1" in build
    assert build.index("SetUserPreferenceInteger(542") < build.index("_pin_section(")


def test_hole_callouts_carry_no_process_words() -> None:
    """TL-20 convention: the native callout alone, no "DRILL, THEN TAP"."""
    for name in ("CR_PROCESS", "RISER_PROCESS", "LEVER_PROCESS"):
        assert not hasattr(spec, name)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "process=" not in source


def _on_sheet(x: float, y: float) -> tuple[float, float]:
    """Carrier (X, Y) mm -> top-view sheet mm (1:2 about the outline centre)."""
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    cx = sum(spec.OUTLINE_X) / 2.0
    cy = sum(spec.OUTLINE_Y) / 2.0
    return (
        drawing.TOP_CENTER[0] * 1000.0 + (x - cx) * scale,
        drawing.TOP_CENTER[1] * 1000.0 + (y - cy) * scale,
    )


def _top_text(name: str) -> tuple[float, float]:
    x, _zero, minus_y = drawing.TOP_KEEP[name]
    return _on_sheet(x, -minus_y)


def _segment_hits_box(a, b, box) -> bool:
    (x0, y0), (x1, y1) = a, b
    for i in range(201):
        t = i / 200.0
        x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
            return True
    return False


# B landscape (sheet mm): the drawing border and the title block's corner.
_BORDER = (12.7, 12.7, 419.1, 266.7)
_TITLE_BLOCK = (216.0, 12.7, 419.1, 65.0)
_CALLOUT_HALF_WIDTH = 25.0  # "5/16-18 UNC THRU ALL" ~ 21 chars x 2.36 mm


def _callout_box(anchor) -> tuple[float, float, float, float]:
    x, y = anchor[0] * 1000.0, anchor[1] * 1000.0
    return (x - _CALLOUT_HALF_WIDTH, y - 7.4, x + _CALLOUT_HALF_WIDTH, y + 1.8)


def _boxes_overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_every_location_text_stands_outside_the_outline() -> None:
    """jig-r3: hole-location dimensions sat inside the outline, crossing
    holes and each other. Every top-view text but the diameters stands
    outside it, in its lane (CL's spot callout stands in the plate's free
    band under the pin line)."""
    diameters = {"PinHoleDia", "SpotDia", "SpotDiaCl"}
    x0, y0 = _on_sheet(spec.OUTLINE_X[0], spec.OUTLINE_Y[0])
    x1, y1 = _on_sheet(spec.OUTLINE_X[1], spec.OUTLINE_Y[1])
    for name in set(drawing.TOP_KEEP) - diameters:
        tx, ty = _top_text(name)
        assert not (x0 - 3.0 < tx < x1 + 3.0 and y0 - 3.0 < ty < y1 + 3.0), name
    for name in drawing.TOP_KEEP:
        tx, ty = _top_text(name)
        assert _BORDER[0] + 6.0 <= tx <= _BORDER[2] - 6.0, name
        assert _BORDER[1] <= ty <= _BORDER[3], name
    # One sheet: the left lanes fit between the outline and the border.
    outermost = min(_top_text(name)[0] for name in drawing.TOP_KEEP)
    assert outermost - 7.0 > _BORDER[0]


def test_single_row_y_texts_clear_their_arrows_and_neighbours() -> None:
    """Carrier r13: the 45.53's top arrow ran into its text (y 192), the
    38.00's bottom arrow struck its (y 161.5), and the CL 29.35 (centred on
    lane x 86, 12.9 wide) touched the outline at x 92. Each single-row Y
    text, centred on its lane, stands within its span clear of both arrows
    (3.56 long) when the span holds them inside, and clear of the outline and
    the next lane's dimension line."""
    arrow, half_h, half_w = 3.56, 1.75, 6.45
    spans = {
        "HubY": spec.HUB[1],
        "LeverY2": spec.LEVER_HOLES[1][1],
    }
    for name, far in spans.items():
        _tx, ty = _top_text(name)
        y_pin, y_far = sorted((_on_sheet(0.0, 0.0)[1], _on_sheet(0.0, far)[1]))
        assert y_pin + arrow + 1.0 < ty - half_h, name
        assert ty + half_h + 1.0 < y_far - arrow, name
    # The right lanes' neighbours: HUB over CR, the 38.00 under the 22.00.
    assert _top_text("HubY")[1] - _top_text("CrY")[1] > 2 * half_h + 1.5
    assert _top_text("LeverY1")[1] - _top_text("LeverY2")[1] > 2 * half_h + 1.5
    cl_x, _cl_y = _top_text("ClY")
    outline_left_x = _on_sheet(spec.OUTLINE_X[0], 0.0)[0]
    assert cl_x + half_w + 2.0 <= outline_left_x
    assert cl_x - half_w - 2.0 >= _on_sheet(drawing._LEFT[1], 0.0)[0]


def test_callouts_and_iso_clear_the_title_block() -> None:
    """jig-r3: the iso and its note ran into the title block."""
    for anchor in (
        drawing.CR_CALLOUT_XY,
        drawing.RISER_CALLOUT_XY,
        drawing.LEVER_CALLOUT_XY,
    ):
        box = _callout_box(anchor)
        assert not _boxes_overlap(box, _TITLE_BLOCK), anchor
        assert _BORDER[0] < box[0] and box[2] < _BORDER[2], anchor
    iso_half = (30.0, 18.0)  # ~58 x 34 mm at 1:8 (jig-r3 render)
    cx, cy = drawing.ISO_CENTER[0] * 1000.0, drawing.ISO_CENTER[1] * 1000.0
    iso = (cx - iso_half[0], cy - iso_half[1], cx + iso_half[0], cy + iso_half[1])
    assert not _boxes_overlap(iso, _TITLE_BLOCK)
    assert iso[2] < _BORDER[2]
    note_x, note_y = (value * 1000.0 for value in drawing.ISO_NOTE_XY)
    assert note_y - 4.0 > _TITLE_BLOCK[3]
    assert note_x + 2.36 * len(spec.ISOMETRIC_VIEW_NOTE) < _BORDER[2]
    assert spec.ISOMETRIC_VIEW_NOTE.endswith(
        f"{drawing.ISO_SCALE[0]}:{drawing.ISO_SCALE[1]}"
    )
    # Section A-A and its caption stand left of the title block.
    assert drawing.SECTION_CENTER[0] * 1000.0 + 40.0 < _TITLE_BLOCK[0]
    assert drawing.SECTION_CAPTION_XY[0] * 1000.0 + 25.0 < _TITLE_BLOCK[0]


def _section_sheet(point, sign: float) -> tuple[float, float]:
    """Model mm in section A-A -> sheet mm, +Y up, +X right (sign 1) or
    left (-1): the cut keeps SolidWorks' direction, so either may print."""
    scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    ax, ay, _az = drawing._SECTION_ANCHOR_MM
    cx, cy = (value * 1000.0 for value in drawing.SECTION_CENTER)
    return cx + sign * (point[0] - ax) * scale, cy + (point[1] - ay) * scale


def test_section_is_never_reversed_and_fits_either_way() -> None:
    """jig-r4: the reversed section imported nothing (PlateThick and
    PinChamferSize missing, available=[]). The cut keeps its direction, so
    every text must clear the slab, the bottom lanes, the border and the
    title block whichever way +X reads."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SetReversedCutDirection" not in source
    # Carrier r11: through an 18 mm line inside the plate the cut did not
    # close (the slab printed unhatched). The line crosses the whole plate,
    # its ends on the sheet, and the crop keeps A1's slab.
    (right, y0, z0), (left, y1, z1) = drawing.SECTION_LINE_MODEL_MM
    assert y0 == z0 == y1 == z1 == 0.0
    assert right > spec.OUTLINE_X[1] and left < spec.OUTLINE_X[0]
    assert _BORDER[0] + 6.0 < _on_sheet(left, 0.0)[0]
    assert _on_sheet(right, 0.0)[0] < _BORDER[2] - 3.0
    a1x = spec.PIN_HOLES["A1"][0]
    assert math.isclose(drawing._SECTION_ANCHOR_MM[0], a1x)
    lowest_lane_y = min(_top_text(name)[1] for name in drawing.TOP_KEEP)
    for sign in (1.0, -1.0):
        x0, y0 = _section_sheet((a1x - drawing._SECTION_HALF, -spec.THICKNESS), sign)
        x1, y1 = _section_sheet((a1x + drawing._SECTION_HALF, 0.0), sign)
        slab = (min(x0, x1), y0, max(x0, x1), y1)
        assert slab[3] + 5.0 < lowest_lane_y
        assert slab[2] < _TITLE_BLOCK[0]
        tx, ty = _section_sheet(drawing.SECTION_KEEP_MODEL_MM["StockThick"], sign)
        assert not (slab[0] - 6.0 < tx < slab[2] + 6.0), sign
        assert _BORDER[0] + 10.0 < tx < _TITLE_BLOCK[0] - 10.0, sign
        # Machinist review (3 runs FIX): beside the slab, the chamfer text's
        # dimension line ran back along the underside as its shelf. The line
        # stands under the -X chamfer; the text hangs under the slab, above
        # the border, on a short OffsetText leader from it.
        lx, ly = _section_sheet(drawing.SECTION_KEEP_MODEL_MM["PinChamferSize"], sign)
        assert slab[0] < lx < slab[2] and slab[1] - 4.0 < ly < slab[1] - 2.0, sign
        cx, cy = _section_sheet(drawing.SECTION_CHAMFER_TEXT_MODEL_MM, sign)
        rows = spec.CALLOUTS_BELOW["PinChamferSize"].splitlines()
        half = 2.36 * max(len(row) for row in rows) / 2.0
        half_height = 5.0 * (1 + len(rows)) / 2.0  # value row + callout rows
        assert cy + half_height < ly and cy - half_height > _BORDER[1], sign
        assert 0.0 < (cx - lx) * sign - half < 25.0, sign
        assert _BORDER[0] < cx - half and cx + half < _TITLE_BLOCK[0]
    # Carrier r13: the caption printed above the 520.0's lane, cut off from
    # the slab by its extension line. It (top-centre anchor, ~46 x 15 mm)
    # stands in the section's own band, level with the slab, left of the
    # thickness text as +X reads (right, jig-r5 and r13), inside the border.
    caption_x, caption_y = (value * 1000.0 for value in drawing.SECTION_CAPTION_XY)
    x0, y0 = _section_sheet((a1x - drawing._SECTION_HALF, -spec.THICKNESS), 1.0)
    x1, y1 = _section_sheet((a1x + drawing._SECTION_HALF, 0.0), 1.0)
    tx, _ty = _section_sheet(drawing.SECTION_KEEP_MODEL_MM["StockThick"], 1.0)
    assert _BORDER[0] + 3.0 < caption_x - 23.0
    assert caption_x + 23.0 < tx - 6.5 - 3.0
    assert y0 < caption_y - 15.0 and caption_y < y1
    assert caption_y + 3.0 < lowest_lane_y


def test_tap_callout_leaders_clear_every_station_text() -> None:
    """jig-r2 leader-through-text: a leader runs from its hole to the near
    end of its callout's first line, ~5 mm below the anchor. Each must clear
    every top-view dimension text (approximated as 24 x 6 mm)."""
    leaders = {
        "CR": (spec.CR, drawing.CR_CALLOUT_XY),
        "riser": (spec.RISER_SCREWS[3], drawing.RISER_CALLOUT_XY),
        "lever": (spec.LEVER_HOLES[1], drawing.LEVER_CALLOUT_XY),
    }
    for name, (hole, anchor) in leaders.items():
        start = _on_sheet(*hole)
        ax, ay = anchor[0] * 1000.0, anchor[1] * 1000.0
        side = -1.0 if start[0] < ax else 1.0
        end = (ax + side * _CALLOUT_HALF_WIDTH, ay - 5.3)
        for dim in drawing.TOP_KEEP:
            tx, ty = _top_text(dim)
            box = (tx - 12.0, ty - 3.0, tx + 12.0, ty + 3.0)
            assert not _segment_hits_box(start, end, box), (name, dim)
        box = _callout_box(anchor)
        for dim in drawing.TOP_KEEP:
            tx, ty = _top_text(dim)
            assert not _boxes_overlap(box, (tx - 6.0, ty - 2.0, tx + 6.0, ty + 2.0)), (
                name,
                dim,
            )



def test_all_four_bores_keep_the_unchanged_size_and_locations() -> None:
    bottom = _features()["bottom_face"]
    assert bottom["normal"] == [0.0, -1.0, 0.0]
    exported = _features()
    for key, (x, y) in spec.PIN_HOLES.items():
        name = f"pin_hole_{key.lower()}"
        feature = exported[name]
        assert feature["axis"] == bottom["normal"]
        assert feature["at"] == [x, 0.0, -y]
        assert feature["dia"] == pytest.approx(
            [spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[1], spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[0]]
        )
        assert feature["thru"] is True
        assert "note" in feature["requirements"]
        assert feature["note"] == " ".join(spec.CALLOUTS_BELOW["PinHoleDia"].splitlines())
        (face,) = requirements_for(drawing)[name].faces
        assert face.contains_x_mm == x
        assert face.contains_z_mm == -y
    assert 0.0 < spec.PIN_CLEARANCE_MIN < spec.PIN_CLEARANCE_MAX


def test_relocated_b2dx_clears_outline_border_and_isometric() -> None:
    b2x, b2y = _top_text("B2DX")
    assert b2y + 10.0 < _on_sheet(0.0, spec.OUTLINE_Y[0])[1] - 3.0
    # Review 88c6d: B2DX's rows (~28 wide, "SETS R816 ON") stand wholly
    # outboard of B2's extension line and the 520.0's at the plate's +X end,
    # so neither strikes the text, and above the isometric.
    half_width = len("SETS R816 ON") * 2.36 / 2.0
    assert b2x - half_width - 3.0 > _on_sheet(spec.OUTLINE_X[1], 0.0)[0]
    assert b2x + half_width < _BORDER[2] - 3.0
    iso_top = drawing.ISO_CENTER[1] * 1000.0 + 17.0
    assert b2y - 8.0 - 3.0 > iso_top

