"""Offline contracts for the oblique-trammel carrier plate (MHA-CH-06-TL-21)."""

from __future__ import annotations

import ast
import inspect
import math
import re
from pathlib import Path
from types import SimpleNamespace

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
        assert spec.prints_exactly(y, spec.TABLE_LOCATION_PLACES)


def test_every_calculator_position_is_the_calculators() -> None:
    features = _features()
    expected = {
        "pin_hole_a1": trammel.A1,
        "pin_hole_b1": trammel.B1,
        "pin_hole_a2": trammel.A2,
        "pin_hole_b2": trammel.B2,
        "cl_spot": trammel.CL,
        "cr_tap_1": trammel.CR,
        "assembly_hub_bore": trammel.HUB,
        **{
            f"riser_tap_{i}": point
            for i, point in enumerate(trammel.RISER_SCREWS, start=1)
        },
    }
    for name, point in expected.items():
        assert _at(features[name]) == tuple(point), name
    assert spec.PIN_HOLES == trammel.PIN_HOLES
    assert (spec.CL, spec.CR) == (trammel.CL, trammel.CR)
    # The finished model includes HUB, still drilled in situ at assembly.
    assert "hub_spot" not in features and set(spec.SPOTS) == {"Cl"}
    assert spec.RISER_SCREWS == trammel.RISER_SCREWS
    assert spec.D1 == trammel.D1
    assert math.isclose(-spec.A2_DX, (trammel.D2 - trammel.D1) / 2.0)
    assert spec.A2_DY == trammel.A2[1]
    # Every printed X is a baseline from A1, including B2 (not B1 + dX).
    for key in ("B1", "A2", "B2"):
        feature = features[f"pin_hole_{key.lower()}"]
        assert feature["station_nominal"] == pytest.approx(
            _printed(trammel.PIN_HOLES[key][0] - trammel.A1[0], 3)
        )


def test_pin_table_uses_title_band_and_one_model_owned_local_control() -> None:
    features = _features()
    assert not hasattr(spec, "POSITION_BAND")
    assert not hasattr(spec, "POSITION_BANDED")
    for key in ("B1", "A2", "B2"):
        feature = features[f"pin_hole_{key.lower()}"]
        assert feature["parent"] == "pin_hole_a1"
        assert feature["station"][1] - feature["station"][0] == pytest.approx(.010 * INCH)
        assert feature["precision"]["station"] == 3
    for key in ("a2", "b2"):
        feature = features[f"pin_hole_{key}"]
        assert feature["height_from"] == "pin_hole_a1"
        assert feature["height"] == pytest.approx([.962 * INCH, .966 * INCH])
    assert spec.OUTER_Y_NOTE == "A2, B2: Y .964 ±.002 FROM THE A1-B1 AXIS LINE"
    assert tuple(spec.A2_DY + v for v in spec.OUTER_Y_DEVIATIONS) == pytest.approx(
        [.962 * INCH, .966 * INCH]
    )
    assert "station" not in features["pin_hole_a1"]
    assert spec.DRAWING_DIMENSIONS["PinHoleProfile"] == {"PinHoleDia"}
    source = inspect.getsource(part._author_outer_pin_rows)
    assert 'for dimension_name in ("A2DY", "B2DY")' in source
    assert "OUTER_Y_DEVIATIONS" in source and "tolerance.SetValues(lower, upper)" in source
    build_source = inspect.getsource(part.build)
    assert "_author_outer_pin_rows(adapter)" in build_source
    assert "Outer Pin Row Note" in build_source
    toleranced = model_toleranced_dimensions(part)
    assert toleranced[("PinHoleProfile", "PinHoleDia")] == "*deviations(PIN_HOLE_BAND)"


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
    assert set(drawing.TOP_KEEP) | set(drawing.SECTION_KEEP_MODEL_MM) | set(drawing.HUB_KEEP) == marked
    assert not set(drawing.TOP_KEEP) & set(drawing.SECTION_KEEP_MODEL_MM)
    assert not set(drawing.HUB_KEEP) & (set(drawing.TOP_KEEP) | set(drawing.SECTION_KEEP_MODEL_MM))
    assert marked <= set(spec.DRAWING_PRECISION_BY_NAME)
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
    assert spec.DRAWING_DIMENSIONS[spec.SPOT_REFERENCE] == {"SpotDia"}
    # jig-r3: the spot has its own leader and callout, no "2X".
    assert "2X" not in spec.CALLOUTS_BELOW["SpotDia"]
    assert spec.CALLOUTS_BELOW["SpotDia"] == "SPOT FOR\nMHA-CH-13 CL"
    assert set(spec.CALLOUT_SUFFIXES) == {"SpotDia"}
    assert not any("Plane" in feature for feature in spec.DRAWING_DIMENSIONS)


def test_in_situ_hub_fit_up_closes_inside_the_strap_top_edge_band() -> None:
    """Owner ruling 5 (option A, 2026-11-01). The HUB on the arcs' centreline
    moves the strap's pivot radially 1:1 against the R800 edge. Drilled in
    situ from the apex (the spindle origin) +Y by HUB_OFFSET, the pin spacing
    moves it with the cut; what reaches the edge at the worst case is the
    DRO setting of the printed offset and the carrier's shift on its pins
    (rule 19: a fit-up that covers the whole range, never root-sum-square)."""
    import ch_rocker_arm_spec as rocker

    assert trammel.HUB[0] == trammel.ARC_CENTRE[0] == 0.0
    assert trammel.HUB[1] - trammel.APEX_Y == pytest.approx(trammel.HUB_OFFSET)
    half = (max(rocker.TOP_EDGE_BAND) - min(rocker.TOP_EDGE_BAND)) / 2.0
    assert half == pytest.approx(0.010 * trammel.INCH)  # .020 one-sided profile
    # The setting: the printed .5125 at a .0001 DRO, held to ±.0005.
    assert spec.inch_text(spec.HUB_OFFSET_PRINTED, spec.HUB_OFFSET_PLACES) == ".5125"
    assert spec.HUB_OFFSET_BAND == pytest.approx(0.0005 * trammel.INCH)
    # The shift: the widest pin clearance, x 1.77 on R.
    shift = trammel.RADIUS_PER_SPACING * spec.PIN_CLEARANCE_MAX
    worst = (
        spec.HUB_OFFSET_BAND + abs(spec.HUB_OFFSET_PRINTED - trammel.HUB_OFFSET) + shift
    )
    assert spec.HUB_RADIAL_STACK == pytest.approx(worst)
    assert f"{spec.HUB_RADIAL_STACK:.3f}" == "0.126"
    assert spec.HUB_RADIAL_STACK < half
    assert max(spec.PIN_RELATIVE_ERROR.values()) < spec.PIN_RELATIVE_ALLOWANCE
    assert spec.PIN_RELATIVE_ALLOWANCE == pytest.approx(.005 * INCH)
    assert spec.HUB_RADIAL_STACK + max(spec.PIN_RELATIVE_ERROR.values()) < half


def test_functions_are_condensed_into_native_table_rows() -> None:
    assert spec.CR == pytest.approx((-spec.CL[0], spec.CL[1]))
    assert set(spec.TABLE_ROW_NOTES) == set(spec.TABLE_HOLES)
    assert spec.TABLE_ROW_NOTES["A1"].endswith("R800 / MHA-CH-13")
    assert spec.TABLE_ROW_NOTES["A2"].endswith("R816 / MHA-CH-13; NOTE 1")
    assert spec.TABLE_ROW_NOTES["B2"] == spec.TABLE_ROW_NOTES["A2"]
    assert all(spec.TABLE_ROW_NOTES[f"R{i}"] == "LOCATES TL-24 RISER" for i in range(1, 5))


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
    assert "RiserTaps" not in spec.DRAWING_DIMENSIONS
    assert spec.RISER_WALLS_FROM_A1 >= WALL_TARGET_MM
    assert all(spec.TABLE_ROW_NOTES[f"R{i}"] == "LOCATES TL-24 RISER" for i in range(1, 5))
    # Four rows (the native two and these two), ~4.5 mm each, centred on the
    # anchor: under the border.
    rows = 2 + len(spec.RISER_TAP_CALLOUT.splitlines())
    x, y = (value * 1000.0 for value in drawing.RISER_CALLOUT_XY)
    assert y + 4.5 * rows / 2.0 + 3.0 < _BORDER[3]
    half = 2.36 * max(len(row) for row in spec.RISER_TAP_CALLOUT.splitlines()) / 2.0
    assert x + half < drawing.CR_CALLOUT_XY[0] * 1000.0 - 25.0 + 2.0
    source = inspect.getsource(drawing.build)
    assert "part_spec.RISER_TAP_CALLOUT" in source


def test_riser_table_has_each_hole_even_when_model_heights_are_shared() -> None:
    screws = spec.RISER_SCREWS
    assert screws[1][1] == screws[0][1] and screws[3][1] == screws[2][1]
    assert screws[1][0] == -screws[0][0] and screws[3][0] == -screws[2][0]
    source = inspect.getsource(part)
    assert '(("RiserX1ROrigin", _origin_x("RiserX1R")), SharedCoordinate(0))' in source
    assert '(("RiserX2ROrigin", _origin_x("RiserX2R")), SharedCoordinate(2))' in source
    assert not spec.CALLOUT_PREFIXES
    for i, point in enumerate(screws, 1):
        assert spec.TABLE_HOLES[f"R{i}"][:2] == point


def test_every_x_station_is_a_baseline_from_a1() -> None:
    """Machinist review 41bbeec (r1/r2 clarity.1): X ran from three origins
    (the left end, A1 and the tap axis). One X datum, A1's axis: every X
    station prints from it (rule 10)."""
    a1x = spec.PIN_HOLES["A1"][0]
    assert spec.DRAWING_DIMENSIONS[spec.STATION_REFERENCE] == {"EdgeX"}
    assert not {"A2DX", "B2DX", "PinSpacing", "LeverX"} & set(drawing.TOP_KEEP)
    assert "PlateHalfLength" not in spec.DRAWING_DIMENSIONS["PlateProfile"]
    assert spec.STATION_REFERENCE in spec.REFERENCE_SKETCHES
    assert spec.STATIONS["EdgeX"] == (spec.OUTLINE_X[0], spec.OUTLINE_Y[0])
    assert spec.STATIONS["ClX"] == spec.CL and spec.STATIONS["CrX"] == spec.CR
    assert spec.STATIONS["LeverX"] == spec.LEVER_HOLES[0]
    features = _features()
    located = ("cl_spot", "cr_tap_1", "left_clamp_tap_1", "lever_tap_1", "lever_tap_2")
    for name in located + tuple(f"riser_tap_{i}" for i in range(1, 5)):
        feature = features[name]
        places = feature["precision"]["station"]
        assert feature["parent"] == "pin_hole_a1", name
        assert feature["station_nominal"] == pytest.approx(
            _printed(_at(feature)[0] - a1x, places)
        ), name
    stations = inspect.getsource(part._station_reference)
    assert '"LeverX": _pin_dim("A1X")' in stations
    # Each origin-based placement evaluates to the feature's |X| from its
    # printed station less A1X.
    values = {"A1X@PinHoleProfile": abs(a1x)} | {
        f"{name}@{spec.STATION_REFERENCE}": abs(x - a1x)
        for name, (x, _y) in spec.STATIONS.items()
    }
    for name, (x, _y) in spec.STATIONS.items():
        if name in ("EdgeX", "LeverX"):
            continue
        expression = part._origin_x(name)
        for key, value in values.items():
            expression = expression.replace(f'"{key}"', repr(value))
        assert math.isclose(eval(expression), abs(x), abs_tol=1e-9), name
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
    diameters = {"PinHoleDia", "SpotDia"}
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




def test_added_left_clamp_is_a_blind_full_thread_receiver_in_the_table() -> None:
    from _hole_spec import HoleSpec

    assert spec.LEFT_CLAMP == trammel.LEFT_CLAMP
    assert spec.LEFT_CLAMP_THREAD == "#10-24"
    assert spec.LEFT_CLAMP_SPEC.end == "blind"
    assert spec.LEFT_CLAMP_SPEC.drill_angle_deg == 180.0
    assert HoleSpec("tapped", "#10-24").drill_angle_deg == 118.0
    assert spec.LEFT_CLAMP_FLOOR_MIN == pytest.approx(WALL_TARGET_MM)
    assert spec.LEFT_CLAMP_FULL_THREAD_MIN >= 1.5 * THREAD_MAJOR_MM["#10-24"]
    feature = _features()["left_clamp_tap_1"]
    assert feature["thru"] is False
    assert feature["depth"] == pytest.approx([9.144, 9.652])
    assert "thread_depth_min" not in feature
    assert "note" in feature["requirements"]
    assert feature["note"] == (
        "THREAD DEPTH 7.874 mm MIN FROM ENTRY FACE; "
        "USABLE FULL THREAD 7.620 mm MIN AFTER THE 0.254 mm ENTRY BREAK. "
        "FLAT-BOTTOM PILOT."
    )
    assert f"{spec.LEFT_CLAMP_THREAD_DEPTH:.3f} mm MIN" in feature["note"]
    assert f"{spec.LEFT_CLAMP_FULL_THREAD_MIN:.3f} mm MIN" in feature["note"]
    declaration = requirements_for(drawing)["left_clamp_tap_1"]
    assert declaration.fields["note"][1] == (
        "LEFT_CLAMP_THREAD_DEPTH", "LEFT_CLAMP_FULL_THREAD_MIN", "LEFT_CLAMP_SPEC",
    )
    assert feature["precision"]["depth"] == 2
    assert "thread_depth_min" not in feature["precision"]
    assert drawing.SHEET_NAMES == ("CARRIER", "HOLE TABLE", "ASSEMBLY HUB")
    assert spec.TABLE_HOLES["LEFT"][:2] == spec.LEFT_CLAMP
    assert not {"LeftClampX", "LeftClampY"} & set(drawing.TOP_KEEP)
    source = inspect.getsource(drawing.build)
    assert "add_native_hole_callout" in source
    assert "_left_clamp_depth_callout(callout)" in source
    assert "expected_sheet_names=SHEET_NAMES" in inspect.getsource(drawing.build)


@pytest.fixture
def raw_dimension_binding(monkeypatch):
    """Model _com_invoke's bare PyIDispatch, not a prewrapped dimension fake."""
    import _com

    class RawDispatch:
        def InvokeTypes(self, *_args):
            raise AssertionError("raw dispatch must be bound before member access")

    wrappers = {}

    def retained(wrapper, interface):
        raw = RawDispatch()
        wrappers[raw] = (interface, wrapper)
        return raw

    def early_bound(value, interface):
        # Match the real passthrough: bare raw dispatch has no _oleobj_.
        # Only _bind supplies the envelope needed to select a native wrapper.
        raw = getattr(value, "_oleobj_", None)
        if raw in wrappers:
            expected, wrapper = wrappers[raw]
            assert interface == expected
            return wrapper
        return value

    monkeypatch.setattr(_com, "_early_bound", early_bound)
    monkeypatch.setattr(part, "_early_bound", early_bound)
    return retained


@pytest.mark.parametrize("persisted_precision", [3, 2])
def test_thread_min_is_authored_and_read_back_on_the_model(
    monkeypatch, raw_dimension_binding, persisted_precision: int,
) -> None:
    values = []

    def set_values(lower, upper):
        values.append((lower, upper))
        return True

    tolerance = SimpleNamespace(
        Type=0, SetValues=set_values, GetMinValue=lambda: 0.0, GetMaxValue=lambda: 0.0,
    )
    requested_precision = []
    display = SimpleNamespace(
        SetPrecision3=lambda *args: requested_precision.append(args),
        GetPrimaryPrecision2=lambda: persisted_precision,
    )
    dimension = SimpleNamespace(Tolerance=tolerance)
    raw_display = raw_dimension_binding(display, "IDisplayDimension")
    raw_dimension = raw_dimension_binding(dimension, "IDimension")
    assert not hasattr(raw_dimension, "_oleobj_")
    assert not hasattr(raw_dimension, "Tolerance")
    monkeypatch.setattr(
        part, "_left_clamp_thread_dimension",
        lambda _adapter: (raw_display, raw_dimension),
    )
    if persisted_precision == 3:
        part._author_left_clamp_thread_min(None)
    else:
        with pytest.raises(RuntimeError, match="source-model thread-depth MIN did not persist"):
            part._author_left_clamp_thread_min(None)
    assert tolerance.Type == spec.LEFT_CLAMP_THREAD_TOL_TYPE == 5
    assert values == [(0.0, 0.0)]
    assert requested_precision == [(3, -1, -1, -1)]
    source = inspect.getsource(part.build)
    assert "_author_left_clamp_thread_min(adapter)" in source
    assert "_require_left_clamp_thread_min(adapter)" in source


@pytest.mark.parametrize("source_thread_tolerance", [5, 0])
def test_drawing_preserves_source_min_and_never_repairs_it(
    monkeypatch, source_thread_tolerance: int,
) -> None:
    import win32com.client.dynamic

    class Variable:
        def __init__(self, name, nominal, tolerance):
            self.VariableName = name
            self.Length = nominal / 1000.0
            self.Precision = 0
            self._tolerance = tolerance
            self._oleobj_ = self

        @property
        def ToleranceType(self):
            return self._tolerance

        @ToleranceType.setter
        def ToleranceType(self, _value):
            raise AssertionError("drawing must not assign a source-model tolerance")

    thread = Variable("hw-threaddepth", spec.LEFT_CLAMP_THREAD_DEPTH, source_thread_tolerance)
    pilot = Variable("hw-tapdrldepth", spec.LEFT_CLAMP_DRILL_DEPTH, 0)
    callout = SimpleNamespace(GetHoleCalloutVariables=lambda: (thread, pilot))
    monkeypatch.setattr(win32com.client.dynamic, "Dispatch", lambda value: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    if source_thread_tolerance == 5:
        drawing._left_clamp_depth_callout(callout)
        assert thread.Precision == 3
        assert pilot.Precision == 2
    else:
        with pytest.raises(RuntimeError, match="source depth precision/tolerance was not preserved"):
            drawing._left_clamp_depth_callout(callout)
    assert thread.ToleranceType == source_thread_tolerance


def test_finished_hub_bore_and_controlled_chamfer_clear_the_stud_root() -> None:
    assert spec.HUB == trammel.HUB
    assert spec.HUB_HOLE_DIA == pytest.approx(10.16)
    assert spec.HUB_CHAMFER == pytest.approx(0.02 * INCH)
    assert spec.HUB_CHAMFER_BAND == printed_band_mm(2, unit=spec.UNIT)
    assert spec.HUB_ROOT_CLEARANCE_MIN > 0.04
    assert spec.HUB_FLANGE_SEAT_WIDTH_MIN >= WALL_TARGET_MM
    assert spec.DRAWING_PRECISION["HubHoleProfile"]["HubHoleDia"] == 4
    assert spec.DRAWING_PRECISION["HubChamfer"]["HubChamferSize"] == 2
    assert "HubX" not in drawing.HUB_KEEP and "HubY" not in drawing.HUB_KEEP
    assert "AT ASSEMBLY" in spec.HUB_HOLE_CALLOUT
    assert "TL-00 STEP 10" in spec.HUB_HOLE_CALLOUT
    assert "UNDERSIDE" in spec.HUB_CHAMFER_CALLOUT
    source = inspect.getsource(part._finished_hub_bore)
    assert "volume_check" in source
    assert '"HubChamfer", "HubChamferSize"' in source
    assert "-THICKNESS" in source  # underside edge, not the top entry edge
    assert "an explicit size band" in source
    features = _features()
    assert "assembly_hub_bore" in features
    assert "assembly_hub_underside_chamfer" in features


def test_pin_chamfer_binds_raw_named_dimension_before_value_and_tolerance(
    monkeypatch, raw_dimension_binding,
) -> None:
    values = {}

    def set_values(lower, upper):
        values.update(lower=lower, upper=upper)
        return True

    tolerance = SimpleNamespace(
        Type=0, SetValues=set_values,
        GetMinValue=lambda: values["lower"], GetMaxValue=lambda: values["upper"],
    )
    raw = raw_dimension_binding(
        SimpleNamespace(SystemValue=spec.PIN_CHAMFER / 1000.0, Tolerance=tolerance),
        "IDimension",
    )
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (None, raw))
    part._pin_chamfer_min_limit(None)
    assert tolerance.Type == spec.PIN_CHAMFER_TOL_TYPE
    assert values == pytest.approx({
        "lower": spec.PIN_CHAMFER_BAND[1] / 1000.0,
        "upper": spec.PIN_CHAMFER_BAND[0] / 1000.0,
    })
    assert '_early_bound(_bind(size, "IDimension"), "IDimension")' in inspect.getsource(
        part._finished_hub_bore
    )


def test_finished_hub_is_cut_once_and_updates_the_running_volume() -> None:
    """A rebase must not retain two copies of the destructive bore operation."""
    build = ast.parse(inspect.getsource(part.build)).body[0]
    calls = [
        node for node in ast.walk(build)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_finished_hub_bore"
    ]
    assert len(calls) == 1, "the finished HUB bore/chamfer must be cut exactly once"
    call = calls[0]
    assert [ast.unparse(argument) for argument in call.args] == [
        "adapter", "drive_jobs", "volume",
    ]
    assignments = [
        node for node in build.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Await)
        and node.value.value is call
    ]
    assert len(assignments) == 1, "the single bore operation must be unconditional and awaited"
    assert [ast.unparse(target) for target in assignments[0].targets] == ["volume"]
