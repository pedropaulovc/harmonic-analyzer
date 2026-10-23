"""Offline contracts for the oblique-trammel carrier plate (MHA-CH-06-TL-21)."""

from __future__ import annotations

import inspect
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _drawing_edge_dimensions
import build_ch_rocker_arm_tl_oblique_carrier as part
import ch_rocker_arm_tl_oblique_carrier_spec as spec
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_carrier as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _drawing_layout_check import LeaderSegment, _proper_crossing
from _gtol_face import FaceGeometry, SURFACE_CYLINDER, SURFACE_PLANE
from _feature_requirements import requirements_for
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm

STEM = "ch_rocker_arm_tl_oblique_carrier"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _at(feature: dict) -> tuple[float, float]:
    """A feature's model point back in the carrier frame (X, Y)."""
    x, _y, z = feature["at"]
    return x, -z


def test_interface_contract() -> None:
    assert spec.OUTLINE_X == (-260.0, 260.0)
    assert spec.OUTLINE_Y == (-45.0, 85.0)
    assert spec.THICKNESS == trammel.CARRIER_THICK
    assert spec.LEVER_HOLES == ((0.0, -22.0), (0.0, -38.0))
    assert spec.LEVER_INNER_END_Y == -15.0


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
    assert b1["station_nominal"] == round(trammel.D1, 3) == 450.135
    assert a2["station_nominal"] == 7.224
    assert a2["height_nominal"] == 24.481


def test_pin_chain_runs_from_a1_b1_with_banded_mates() -> None:
    features = _features()
    assert features["pin_hole_b1"]["parent"] == "pin_hole_a1"
    assert features["pin_hole_a2"]["parent"] == "pin_hole_a1"
    assert features["pin_hole_b2"]["height_from"] == "pin_hole_b1"
    for name in ("pin_hole_b1", "pin_hole_a2", "pin_hole_b2"):
        low, high = features[name]["station"]
        assert math.isclose(high - low, 0.04)
    # Rule 4 (jig-r3): each band names what it sets and on which part, not
    # its sensitivity.
    assert spec.SPACING_CALLOUT == "SETS R800 ON\nMHA-CH-13"
    assert spec.DX_CALLOUT == spec.DY_CALLOUT == "SETS R816 ON\nMHA-CH-13"
    for text in spec.CALLOUTS_BELOW.values():
        assert "ERROR" not in text and "1:1" not in text
    # A1 is located from the HUB axis (the X datum) at the .XX band.
    a1 = features["pin_hole_a1"]
    assert a1["station_nominal"] == round(abs(trammel.A1[0]), 2) == 225.07
    assert a1["precision"]["station"] == 2
    assert "A1X" in spec.DRAWING_DIMENSIONS["PinHoleProfile"]
    assert set(spec.POSITION_BANDED) <= set(spec.CALLOUTS_BELOW)
    toleranced = model_toleranced_dimensions(part)
    assert toleranced[("PinHoleProfile", "PinHoleDia")] == "*deviations(PIN_HOLE_BAND)"
    assert ("PinHoleProfile", "dimension_name") in toleranced


def test_pin_holes_are_h7_and_name_the_pin() -> None:
    hole = _features()["pin_hole_a1"]
    assert hole["dia"] == [10.0, 10.015]
    assert (spec.PIN_CLEARANCE_MIN, round(spec.PIN_CLEARANCE_MAX, 3)) == (0.0, 0.024)
    assert "MHA-CH-06-TL-23 PIVOT PIN" in hole["note"]
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
        band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["StockThick"])
        full = spec.THICKNESS - band - 0.25 - pitch
        assert math.isclose(spec.ENGAGEMENT_MM[thread], full), thread
    for thread in (spec.CR_THREAD, spec.RISER_THREAD):
        assert spec.ENGAGEMENT_MM[thread] >= 1.5 * THREAD_MAJOR_MM[thread]
    # A finished 12 plate still cannot hold 1.5D of 5/16-18. The lever callout
    # retains the existing RV-01 shortfall as a plain fact, floored (rule 20).
    lever = spec.LEVER_THREAD
    assert spec.ENGAGEMENT_MM[lever] < 1.5 * THREAD_MAJOR_MM[lever]
    assert spec.SHORT_ENGAGEMENT == (lever,)
    assert spec.LEVER_TAP_CALLOUT == "ENGAGEMENT 9.53 MIN (1.20D)"
    assert "part_spec.LEVER_TAP_CALLOUT" in inspect.getsource(drawing.build)
    assert spec.CR_HEAD_DIA_MAX <= spec.CR_HEAD_CLEAR_DIA


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= 2.0


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
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (name, requirement)
            checked += 1
    assert checked


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-21"


def test_cl_dowel_is_a_press_in_its_finished_hole() -> None:
    # Bought Ø6 m6 dowel (6.004/6.012) in the in-place N7 hole (5.984/5.996).
    assert spec.CL_DOWEL_INTERFERENCE == (0.008, 0.028)


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
    assert feature["height"] == [
        spec.THICKNESS - spec.THICKNESS_BAND,
        spec.THICKNESS + spec.THICKNESS_BAND,
    ]


def test_spot_stations_print_from_the_hidden_reference_sketch() -> None:
    """A reference plane cannot be imported into a drawing (farm jig-r1)."""
    assert spec.DRAWING_DIMENSIONS[spec.SPOT_REFERENCE] == {
        "SpotDia",
        "SpotDiaCl",
        "HubY",
        "ClX",
        "ClY",
    }
    # jig-r3: each spot has its own leader and callout, no "2X".
    assert spec.CALLOUTS_BELOW["SpotDia"] == spec.CALLOUTS_BELOW["SpotDiaCl"]
    assert "2X" not in spec.CALLOUTS_BELOW["SpotDia"]
    assert set(spec.CALLOUT_SUFFIXES) == {"SpotDia", "SpotDiaCl"}
    assert not any("Plane" in feature for feature in spec.DRAWING_DIMENSIONS)


def test_pin_chamfer_clears_the_pivot_pin_collar_fillet() -> None:
    """jig-r3 interference: 0.272 mm^3 per pin, the collar's R0.2 shoulder
    fillet against the hole's sharp underside edge."""
    import ch_rocker_arm_tl_oblique_pivot_pin_spec as pin

    radius = pin.SHOULDER_FILLET_RADIUS
    # The fillet's corner ring, what the sharp edge interfered with.
    corner = (1.0 - math.pi / 4.0) * radius**2 * math.pi * spec.PIN_HOLE_DIA
    assert math.isclose(corner, 0.272086274, rel_tol=0.01)
    assert spec.PIN_CHAMFER - radius * (2.0 - math.sqrt(2.0)) >= 0.1
    mouth = (spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[0]) / 2.0 + spec.PIN_CHAMFER
    assert mouth + spec.PIN_CHAMFER_BAND[0] < pin.COLLAR_DIA / 2.0
    assert spec.SECTION_REFERENCE in spec.REFERENCE_SKETCHES
    assert spec.DRAWING_DIMENSIONS[spec.SECTION_REFERENCE] == {
        "PinChamferSize",
        "StockThick",
    }
    assert spec.DRAWING_PRECISION_BY_NAME["PinChamferSize"] == 1
    callout = spec.CALLOUTS_BELOW["PinChamferSize"]
    assert "UNDERSIDE" in callout and f"CLEARS {pin_number()}" in callout
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


def pin_number() -> str:
    return _config.parts("ch-rocker-arm-tl-oblique-pivot-pin")["number"]


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
        assert tap["station_nominal"] == round(x, places)
        assert tap["height_nominal"] == round(y, places)
    riser = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
    assert riser == "MHA-CH-06-TL-24"
    assert spec.RISER_TAP_CALLOUT == (f"HOLDS {riser} SCREWS\nCLEAR OF ITS CUT EDGES")
    # Rule 4 (carrier r11): each 3-place station names what it locates.
    assert set(spec.RISER_STATIONS) == spec.DRAWING_DIMENSIONS["RiserTaps"]
    for name in spec.RISER_STATIONS:
        assert spec.CALLOUTS_BELOW[name] == f"LOCATES\n{riser}", name
    assert min(trammel.RISER_SCREW_WALLS) >= 2.0
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
    assert '(("RiserX1R", None), SharedCoordinate(0))' in source
    assert '(("RiserX2R", None), SharedCoordinate(2))' in source
    assert spec.CALLOUT_PREFIXES == {"RiserY1": "2X ", "RiserY2": "2X "}
    build = inspect.getsource(drawing.build)
    assert "_set_callout_texts(adapter, annotations, CALLOUT_PREFIXES, part=1)" in build


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
    outside it, in its lane."""
    x0, y0 = _on_sheet(spec.OUTLINE_X[0], spec.OUTLINE_Y[0])
    x1, y1 = _on_sheet(spec.OUTLINE_X[1], spec.OUTLINE_Y[1])
    for name in drawing.TOP_KEEP:
        tx, ty = _top_text(name)
        assert not (x0 - 3.0 < tx < x1 + 3.0 and y0 - 3.0 < ty < y1 + 3.0), name
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
        # Carrier r11: the chamfer text under the slab was struck by its own
        # extension lines. It stands beside the slab, opposite the stock
        # text, its dimension line (its last row, 2.78 mm per row under the
        # anchor) below the underside.
        cx, cy = _section_sheet(drawing.SECTION_KEEP_MODEL_MM["PinChamferSize"], sign)
        rows = spec.CALLOUTS_BELOW["PinChamferSize"].splitlines()
        half = 2.36 * max(len(row) for row in rows) / 2.0
        assert cx + half + 2.0 < slab[0] or cx - half - 2.0 > slab[2], sign
        assert (cx < slab[0]) != (tx < slab[0]), sign
        lane = cy - (1 + len(rows)) * 2.778
        assert lane < slab[1] and lane - 2.5 > _BORDER[1], sign
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



def test_all_four_bore_axes_own_the_bottom_normal_inspection() -> None:
    assert (
        spec.PIN_AXIS_DEVIATION_MAX
        == retention.CARRIER_AXIS_DEVIATION_MAX
        == 0.05
    )
    assert (
        spec.PIN_AXIS_MEASUREMENT_SPAN
        == retention.CARRIER_AXIS_MEASUREMENT_SPAN
        == 10.5
    )
    bottom = _features()["bottom_face"]
    assert bottom["normal"] == [0.0, -1.0, 0.0]
    exported = _features()
    for key, (x, y) in spec.PIN_HOLES.items():
        name = f"pin_hole_{key.lower()}"
        feature = exported[name]
        assert feature["axis"] == bottom["normal"]
        assert feature["at"] == [x, 0.0, -y]
        assert feature["dia"] == [10.0, 10.015]
        assert feature["thru"] is True
        assert "note" in feature["requirements"]
        assert feature["note"] == " ".join(
            (spec.CALLOUTS_BELOW["PinHoleDia"] + "\n" + spec.PIN_LAND_CALLOUT).splitlines()
        )
        (face,) = requirements_for(drawing)[name].faces
        assert face.contains_x_mm == x
        assert face.contains_z_mm == -y
    assert spec.PIN_AXIS_MEASUREMENT_SPAN <= retention.CARRIER_ENGAGEMENT_MIN
    # The normal reference is the same physical underside the two pin collars
    # seat on; no added support, skid or change to the H7/h6 fit is involved.
    assert spec.PIN_CLEARANCE_MIN == 0.0
    assert math.isclose(spec.PIN_CLEARANCE_MAX, 0.024)


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


def _b9e4_native_layout():
    """Complete observed native/PDF sheet, never an after-fix native claim."""
    import json
    from dataclasses import replace
    from _layout_audit import sheet_model
    from _layout_geometry import AnnotationGeometry, Segment

    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "ch_rocker_arm_tl_oblique_carrier_b9e4.json").read_text(
            encoding="utf-8"
        )
    )
    assert fixture["pdf_sha256"] == (
        "fb5665173e2e05055de59018d92c8fbeebdb0cf9fde4e7201e82647b5113c744"
    )
    assert fixture["coordinate_quantum_m"] == 1e-7
    (dump,) = fixture["sheets"]
    model = sheet_model(dump)
    # Includes every native dimension, all centre marks, the section pointers,
    # linked caption and notes. No hand-picked obstacle census replaces it.
    assert len(model.geometry.annotations) == 50
    assert fixture["pdf_lines"]["coordinates"] == "sheet_metres"
    pdf_lines = tuple(
        Segment(*row[1:]) for row in fixture["pdf_lines"]["segments"]
    )
    assert len(pdf_lines) == 1645
    section_lines = tuple(
        Segment(*row[1:]) for row in fixture["pdf_lines"]["segments"]
        if row[0] == fixture["section_outline_pdf_path"]
    )
    assert len(section_lines) == 42
    section = AnnotationGeometry(
        label="PDF actual section outline", kind="geometry",
        owner=dump["views"][2]["name"], segments=section_lines,
    )
    geometry = replace(
        model.geometry, annotations=(*model.geometry.annotations, section)
    )
    return SimpleNamespace(
        dump=dump, geometry=geometry, section=section, pdf_lines=pdf_lines,
        unmatched=model.unmatched,
    )


def _b9e4_annotation(layout, name, view_index=0):
    matches = [
        annotation for annotation in layout.dump["views"][view_index]["annotations"]
        if annotation["name"] == name
    ]
    assert len(matches) == 1, name
    return matches[0]


def _b9e4_named(layout, name, view_index=0):
    owner = layout.dump["views"][view_index]["name"]
    matches = [
        annotation for annotation in layout.geometry.annotations
        if annotation.owner == owner
        and annotation.label.split(" ", 2)[1] == name
    ]
    assert len(matches) == 1, (owner, name)
    return matches[0]


def _b9e4_translated(annotation, old_xy, new_xy):
    from dataclasses import replace
    from _layout_geometry import Box

    dx, dy = new_xy[0] - old_xy[0], new_xy[1] - old_xy[1]
    return replace(
        annotation, position=new_xy,
        text_boxes=tuple(
            Box(box.xmin + dx, box.ymin + dy, box.xmax + dx, box.ymax + dy)
            for box in annotation.text_boxes
        ),
    )


def _b9e4_crossing(a, b):
    return _proper_crossing(
        LeaderSegment("candidate", "dim", a.x0, a.y0, a.x1, a.y1),
        LeaderSegment("neighbor", "dim", b.x0, b.y0, b.x1, b.y1),
        tol=1e-4,
    )


def _conditional_b9e4_layout():
    """Translate observed glyphs; conditionally reroute, not native elbow proof.

    REAM keeps its measured shoulder dimensions and the real bore centre/radius,
    but its new diameter angle is conditional. The linear OffsetText route has
    NOT been observed: bound its connector and shoulder separately below.
    UNDERSIDE keeps the real native attachment; only its text-relative leader
    start translates, and its arrow rotates conditionally toward that start.
    A fresh native audit/PDF remains necessary for all three regenerated routes.
    """
    from dataclasses import replace
    from _layout_audit import arrowhead_segments
    from _layout_geometry import Segment

    layout = _b9e4_native_layout()
    changes = {}
    ream = _b9e4_named(layout, "PinHoleDia")
    raw = _b9e4_annotation(layout, "PinHoleDia")
    ream_xy = tuple(value / 1000.0 for value in _top_text("PinHoleDia"))
    moved = _b9e4_translated(ream, raw["pos"], ream_xy)
    dx, dy = (ream_xy[i] - raw["pos"][i] for i in (0, 1))
    first, diameter, shoulder = raw["display"]["lines"]
    centre = tuple((diameter[4 + i] + diameter[7 + i]) / 2.0 for i in (0, 1))
    radius = math.dist(diameter[4:6], diameter[7:9]) / 2.0
    elbow = (first[7] + dx, first[8] + dy)
    direction = tuple((elbow[i] - centre[i]) / math.dist(elbow, centre) for i in (0, 1))
    near = tuple(centre[i] + radius * direction[i] for i in (0, 1))
    far = tuple(centre[i] - radius * direction[i] for i in (0, 1))
    approach = Segment(*near, *elbow, "dim-line")
    ream_shoulder = Segment(
        shoulder[4] + dx, shoulder[5] + dy,
        shoulder[7] + dx, shoulder[8] + dy, "shoulder",
    )
    arrow = list(raw["display"]["arrows"][0])
    arrow[:2], arrow[3:5] = near, direction
    changes[ream.label] = replace(
        moved, segments=(
            approach, Segment(*far, *near, "dim-line"), ream_shoulder,
            *arrowhead_segments(arrow),
        ),
    )

    land = _b9e4_named(layout, "RD1", 2)
    raw_land = _b9e4_annotation(layout, "RD1", 2)
    moved = _b9e4_translated(land, raw_land["pos"], drawing.PIN_LAND_TEXT_XY)
    line_x, line_y = drawing.PIN_LAND_LINE_XY
    # Actual native wall endpoints remain fixed. The 1 mm witness overrun is
    # measured in b9e4; these new right-side witnesses/routes are conditional.
    tips = tuple(
        (line_x, arrow[1]) for arrow in raw_land["display"]["arrows"]
    )
    witnesses = tuple(
        Segment(row[4], row[5], line_x + 0.001, row[8], "ext-line")
        for row in raw_land["display"]["lines"][:2]
    )
    arrows = []
    for raw_arrow, tip in zip(raw_land["display"]["arrows"], tips, strict=True):
        arrow = list(raw_arrow)
        arrow[:2] = tip
        arrows.extend(arrowhead_segments(arrow))
    text_dx = drawing.PIN_LAND_TEXT_XY[0] - raw_land["pos"][0]
    text_dy = drawing.PIN_LAND_TEXT_XY[1] - raw_land["pos"][1]
    left = min(run["pos"][0] for run in raw_land["display"]["texts"]) + text_dx
    right = max(
        run["pos"][0] + run["w"] for run in raw_land["display"]["texts"]
    ) + text_dx
    baseline = min(run["pos"][1] for run in raw_land["display"]["texts"]) + text_dy
    connector = Segment(line_x, line_y, left, baseline, "leader")
    land_shoulder = Segment(left, baseline, right, baseline, "shoulder")
    changes[land.label] = replace(
        moved, segments=(
            *witnesses, Segment(*tips[0], *tips[1], "dim-line"),
            connector, land_shoulder, *arrows,
        ),
    )

    underside = _b9e4_named(layout, "DetailItem364", 2)
    raw_under = _b9e4_annotation(layout, "DetailItem364", 2)
    # The captured note was authored with (-20,-7) mm. Its actual edge landing
    # is NOT the ideal projected selection point and must never translate.
    delta = (
        drawing.UNDERSIDE_LABEL_OFFSET[0] - (-0.020),
        drawing.UNDERSIDE_LABEL_OFFSET[1] - (-0.007),
    )
    note_xy = tuple(raw_under["pos"][i] + delta[i] for i in (0, 1))
    moved = _b9e4_translated(underside, raw_under["pos"], note_xy)
    (native_leader,) = raw_under["leaders"]
    start = tuple(native_leader[i] + delta[i] for i in (0, 1))
    landing = tuple(native_leader[3:5])
    under_route = Segment(*start, *landing, "leader")
    arrow = list(raw_under["display"]["arrows"][0])
    arrow[3:5] = tuple(
        (start[i] - landing[i]) / math.dist(start, landing) for i in (0, 1)
    )
    changes[underside.label] = replace(
        moved, segments=(under_route, *arrowhead_segments(arrow)),
        leader_spans=((start, landing),),
    )
    proposed = replace(
        layout.geometry,
        annotations=tuple(changes.get(a.label, a) for a in layout.geometry.annotations),
    )
    return SimpleNamespace(
        observed=layout, proposed=proposed, changes=changes, ream=changes[ream.label],
        land=changes[land.label], underside=changes[underside.label],
        approach=approach, ream_shoulder=ream_shoulder,
        land_routes=(connector, land_shoulder), land_witnesses=witnesses,
        land_tips=tips, bore=(centre, radius), underside_route=under_route,
    )


def test_b9e4_complete_native_rows_record_the_actual_three_layout_defects() -> None:
    from _layout_geometry import Box, segment_box_overlap_length

    layout = _b9e4_native_layout()
    ream = _b9e4_named(layout, "PinHoleDia")
    raw = _b9e4_annotation(layout, "PinHoleDia")
    assert len(raw["display"]["texts"]) == 14
    assert len(ream.text_boxes) == 10  # +.015 row, diameter/.000, all eight below
    # b9e4 printed the earlier nine-row REAM block. The plain squareness
    # wording keeps its fit rows and has fewer, no wider rows, so the observed
    # glyph block still bounds the current text for the layout replay below.
    recorded = [run["t"] for run in raw["display"]["texts"][6:]]
    current = spec.CALLOUTS_BELOW["PinHoleDia"].splitlines()
    fit_rows = spec.PIN_HOLE_CALLOUT.splitlines()
    assert recorded[: len(fit_rows)] == current[: len(fit_rows)] == fit_rows
    assert len(current) <= len(recorded)
    assert max(map(len, current)) <= max(map(len, recorded))
    assert not [item for item in layout.unmatched if "PinHoleDia" in item[0]]
    near_y = _b9e4_named(layout, "PlateNearY")
    assert "45.00" in near_y.label
    # The +.015 stack shares the 45.00's printed row, close enough to read as
    # its tolerance; the actual 45 line/arrow cross the diameter and THRU row.
    assert near_y.text_boxes[0].gap(ream.text_boxes[0]) < 0.0035
    for role in ("dim-line", "arrow"):
        assert any(
            segment_box_overlap_length(segment, box) > 0.00015
            for segment in near_y.segments if segment.role == role
            for box in ream.text_boxes[1:3]
        ), role
    bottom_extension = next(
        segment for segment in near_y.segments
        if segment.role == "ext-line"
        and abs(segment.y0 - 0.1525) < 1e-7
        and abs(segment.y1 - 0.1525) < 1e-7
    )
    assert segment_box_overlap_length(bottom_extension, ream.text_boxes[2]) > 0.01

    land = _b9e4_named(layout, "RD1", 2)
    assert len(land.text_boxes) == 4
    top = max(segment.y0 for segment in layout.section.segments)
    top_edges = [
        segment for segment in layout.section.segments
        if abs(segment.y0 - top) < 1e-7 and abs(segment.y1 - top) < 1e-7
    ]
    assert any(
        segment_box_overlap_length(edge, land.text_boxes[0]) > 0.00015
        for edge in top_edges
    )
    assert any(
        segment_box_overlap_length(arrow, land.text_boxes[0]) > 0.00015
        for arrow in land.segments if arrow.role == "arrow"
    )
    slab = layout.section.box()
    assert slab is not None
    for box in land.text_boxes[1:]:
        assert slab.xmin < box.xmin < box.xmax < slab.xmax
        assert slab.ymin < box.ymin < box.ymax < slab.ymax

    underside = _b9e4_named(layout, "DetailItem364", 2)
    (box,) = underside.text_boxes
    # A cap-height-wide strip at the word's E end, not fabricated per-glyph
    # bounds: the captured PDF run and native leader prove the terminal strike.
    terminal_ink = Box(box.xmax - box.height, box.ymin, box.xmax, box.ymax)
    assert any(
        segment_box_overlap_length(segment, terminal_ink) > 0.00015
        for segment in underside.segments if segment.role == "leader"
    )


def test_conditional_b9e4_all_rows_and_routes_clear_every_native_neighbor() -> None:
    from _layout_audit import (
        find_arrows_near_text, find_leader_across_lines, find_leader_through_text,
        find_lines_through_own_text, find_merged_blocks, find_text_clearance,
        find_text_separation,
    )
    from _layout_geometry import (
        find_border_breaches, find_leader_crossings, find_text_on_line,
        find_text_on_text, segment_box_overlap_length,
    )

    candidate = _conditional_b9e4_layout()
    observed = candidate.observed.geometry
    proposed = candidate.proposed
    # Every original annotation and all its rows/segments remain unless one of
    # the three repaired controls owns them. In particular, 45.00, stock,
    # chamfer, caption, all location blocks and every centre mark remain.
    assert [a.label for a in observed.annotations] == [a.label for a in proposed.annotations]
    for old, new in zip(observed.annotations, proposed.annotations, strict=True):
        assert len(new.text_boxes) == len(old.text_boxes)
        if old.label not in candidate.changes:
            assert new == old
    assert len(candidate.ream.text_boxes) == 10
    assert len(candidate.land.text_boxes) == 4
    assert candidate.bore[0] == pytest.approx((0.10946615, 0.175))
    assert candidate.bore[1] == pytest.approx(0.0025, abs=1e-7)
    for predicate in (
        find_text_clearance, find_text_separation, find_merged_blocks,
        find_leader_through_text, find_leader_across_lines,
        find_lines_through_own_text, find_arrows_near_text, find_text_on_line,
        find_text_on_text, find_leader_crossings, find_border_breaches,
    ):
        affected = [
            finding for finding in predicate(proposed)
            if finding.a in candidate.changes or finding.b in candidate.changes
        ]
        assert affected == [], (predicate.__name__, affected)
    # Also retain the full 1645-segment PDF vector census, including model
    # edges not present in the native display arrays, against every moved row.
    # These are OLD printed vectors, not evidence of future native regeneration.
    for annotation in candidate.changes.values():
        for box in annotation.text_boxes:
            assert all(
                segment_box_overlap_length(segment, box) <= 0.00015
                for segment in candidate.observed.pdf_lines
            ), annotation.label

    crossings = []
    for annotation in proposed.annotations:
        if annotation.label == candidate.ream.label:
            continue
        for line in annotation.segments:
            if line.role not in ("line", "dim-line", "ext-line"):
                continue
            # The text shoulder may cross NOTHING. The diameter's approach
            # may cross genuine witness extensions, never a dimension line.
            assert _b9e4_crossing(candidate.ream_shoulder, line) is None, annotation.label
            if _b9e4_crossing(candidate.approach, line) is not None:
                assert line.role == "ext-line", (annotation.label, line)
                crossings.append(annotation.label)
    for name in ("PlateLength", "PlateHalfLength"):
        assert _b9e4_named(candidate.observed, name).label in crossings
    for box in candidate.ream.text_boxes:
        assert box.xmin - proposed.region.xmin > 0.003
    # The old complete block, not just its diameter value, is now below the
    # real Y152.5 extension and clear of the unchanged 45.00 glyph and arrow.
    near_y = _b9e4_named(candidate.observed, "PlateNearY")
    assert 0.1525 - max(box.ymax for box in candidate.ream.text_boxes) > 0.003
    assert all(box.gap(near_y.text_boxes[0]) > 0.0035 for box in candidate.ream.text_boxes)


def test_captured_land_arrow_corridor_has_margin_from_chamfer_and_section() -> None:
    from _layout_audit import arrowhead_segments
    from _layout_geometry import segment_box_distance

    candidate = _conditional_b9e4_layout()
    raw = _b9e4_annotation(candidate.observed, "RD1", 2)
    chamfer = _b9e4_named(candidate.observed, "PinChamferSize", 2)
    # Parent's focused run found the old x149 placement too close: use every
    # captured arrow edge and every complete chamfer row, not just arrow tips.
    crowded_arrows = tuple(
        edge
        for arrow in raw["display"]["arrows"]
        for edge in arrowhead_segments([0.149, *arrow[1:]])
    )
    crowded_gap = min(
        segment_box_distance(edge, box)
        for edge in crowded_arrows for box in chamfer.text_boxes
    )
    assert crowded_gap == pytest.approx(0.001897, abs=1e-7)
    assert crowded_gap < 0.002
    proposed_arrows = tuple(
        edge for edge in candidate.land.segments if edge.role == "arrow"
    )
    assert min(
        segment_box_distance(edge, box)
        for edge in proposed_arrows for box in chamfer.text_boxes
    ) > 0.0025
    slab = candidate.observed.section.box()
    assert slab is not None
    assert min(min(edge.x0, edge.x1) for edge in proposed_arrows) - slab.xmax > 0.0025


def test_conditional_b9e4_land_is_exterior_with_fixed_arrows_and_route_air() -> None:
    from _layout_geometry import segment_box_overlap_length

    candidate = _conditional_b9e4_layout()
    slab = candidate.observed.section.box()
    assert slab is not None
    # Merely lowering the old block within the bore is not a repair. ALL four
    # complete rows must stand to the right of the real section silhouette.
    assert all(box.xmin - slab.xmax > 0.0035 for box in candidate.land.text_boxes)
    for box in candidate.land.text_boxes:
        for line in candidate.land.segments:
            if line.role in ("arrow", "ext-line", "dim-line"):
                assert box.gap(line.box()) > 0.002
        assert box.gap(slab) > 0.0035
    raw = _b9e4_annotation(candidate.observed, "RD1", 2)
    assert candidate.land_tips == tuple(
        (drawing.PIN_LAND_LINE_XY[0], arrow[1]) for arrow in raw["display"]["arrows"]
    )
    assert sorted(tip[1] for tip in candidate.land_tips) == pytest.approx([0.0279, 0.063])
    # The unknown native offset elbow is constrained by TWO envelopes, not an
    # invented verified route: connector corridor, then the text shoulder.
    # Keeping them separate avoids treating empty paper under the whole text
    # block as a leader that could strike the chamfer's first row.
    for route in candidate.land_routes:
        envelope = route.box()
        for annotation in candidate.proposed.annotations:
            if annotation.label == candidate.land.label:
                continue
            for box in annotation.text_boxes:
                assert envelope.gap(box) > 0.002, annotation.label
            for line in annotation.segments:
                assert segment_box_overlap_length(line, envelope) <= 0.00015, annotation.label
        assert envelope.gap(slab) > 0.002
    underside = candidate.underside_route
    (under_box,) = candidate.underside.text_boxes
    assert segment_box_overlap_length(underside, under_box) == 0.0
    # The translated native text-relative start stays to the RIGHT of final E,
    # and the real native attachment does not follow the label.
    assert underside.x0 > under_box.xmax
    native_under = _b9e4_annotation(candidate.observed, "DetailItem364", 2)
    assert (underside.x1, underside.y1) == tuple(native_under["leaders"][0][3:5])
    chamfer = _b9e4_named(candidate.observed, "PinChamferSize", 2)
    for line in chamfer.segments:
        if line.role == "dim-line":
            assert _b9e4_crossing(underside, line) is None


def _native_axis_fixture(monkeypatch):
    """Replace only COM reads; retain the production vector and rim algorithms."""
    model = object()
    faces, geometries, rims, resolved = {}, {}, {}, []

    def bore(name, axis=(0.0, -1.0, 0.0), land=11.7):
        length = math.hypot(*axis)
        axis = tuple(component / length for component in axis)
        x, y = spec.PIN_HOLES[name]
        origin = (x / 1000.0, 0.0, -y / 1000.0)
        rims[name] = [
            (*origin, *axis, 0.005),
            (*(p + a * land / 1000.0 for p, a in zip(origin, axis)), *axis, 0.005),
        ]
        faces[name] = SimpleNamespace(
            GetEdges=lambda: tuple(
                SimpleNamespace(
                    GetCurve=lambda circle=circle: SimpleNamespace(
                        IsCircle=lambda: True, CircleParams=circle
                    )
                )
                for circle in rims[name]
            )
        )
        geometries[name] = FaceGeometry(
            faces[name], SURFACE_CYLINDER, (*origin, *axis, 0.005), None, ()
        )

    def plane(normal=(0.0, -1.0, 0.0), offset=12.0, identity=SURFACE_PLANE):
        faces["underside"] = object()
        geometries["underside"] = FaceGeometry(
            faces["underside"], identity,
            (*normal, *(component * offset / 1000.0 for component in normal)),
            normal, (),
        )

    def resolve(actual_model, requests):
        assert actual_model is model
        assert set(requests) == {"underside", "A1", "B1", "A2", "B2"}
        resolved.append(requests)
        return faces

    def geometry(face):
        return next(geometries[key] for key, value in faces.items() if value is face)

    plane()
    for name in spec.PIN_HOLES:
        bore(name)
    monkeypatch.setattr(drawing, "resolve_faces", resolve)
    monkeypatch.setattr(drawing, "face_geometry", geometry)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    return SimpleNamespace(
        model=model, bore=bore, plane=plane, rims=rims,
        geometries=geometries, resolved=resolved,
    )


def test_native_axes_return_all_four_actual_lands_with_one_resolution(monkeypatch):
    native = _native_axis_fixture(monkeypatch)
    for index, name in enumerate(spec.PIN_HOLES):
        native.bore(name, land=10.5 + index * 0.3)
    assert drawing._assert_pin_axis_geometry(native.model) == pytest.approx(
        dict(zip(spec.PIN_HOLES, (10.5, 10.8, 11.1, 11.4)))
    )
    assert len(native.resolved) == 1


@pytest.mark.parametrize("name", ("A1", "B1", "A2", "B2"))
def test_each_native_bore_rejects_resultant_diagonal_tilt(monkeypatch, name):
    native = _native_axis_fixture(monkeypatch)
    component = 0.04 / 10.5
    assert component < 0.05 / 10.5 < math.hypot(component, component)
    native.bore(name, axis=(component, -1.0, component))
    with pytest.raises(RuntimeError, match=f"{name}: native axis exceeds resultant"):
        drawing._assert_pin_axis_geometry(native.model)


@pytest.mark.parametrize("azimuth", (0.0, 0.37, 1.19, 2.31, 4.81))
@pytest.mark.parametrize("factor", (0.999, 1.0, 1.001))
def test_native_axis_boundary_is_azimuth_independent(monkeypatch, azimuth, factor):
    native = _native_axis_fixture(monkeypatch)
    slope = factor * 0.05 / 10.5
    # A reversed cylinder axis describes the same physical bore.
    native.bore("B2", axis=(slope * math.cos(azimuth), 1.0, slope * math.sin(azimuth)))
    if factor > 1.0:
        with pytest.raises(RuntimeError, match="B2: native axis exceeds resultant"):
            drawing._assert_pin_axis_geometry(native.model)
    else:
        assert drawing._assert_pin_axis_geometry(native.model)["B2"] == pytest.approx(11.7)


def test_axes_use_native_underside_not_world_y(monkeypatch):
    native = _native_axis_fixture(monkeypatch)
    angle = 0.01  # Within the plane selector, outside the axis acceptance.
    normal = (math.sin(angle), -math.cos(angle), 0.0)
    native.plane(normal=normal)
    with pytest.raises(RuntimeError, match="A1: native axis exceeds resultant"):
        drawing._assert_pin_axis_geometry(native.model)
    for name in spec.PIN_HOLES:
        native.bore(name, axis=normal)
    assert drawing._assert_pin_axis_geometry(native.model) == pytest.approx(
        {name: 11.7 for name in spec.PIN_HOLES}
    )


@pytest.mark.parametrize(
    "normal,offset,identity",
    (
        ((0.0, 1.0, 0.0), 12.0, SURFACE_PLANE),
        ((0.0, -1.0, 0.0), 0.0, SURFACE_PLANE),
        ((0.0, -1.0, 0.0), 12.0, SURFACE_CYLINDER),
        ((0.1, -math.sqrt(0.99), 0.0), 12.0, SURFACE_PLANE),
    ),
)
def test_native_underside_must_match_real_seating_plane(
    monkeypatch, normal, offset, identity
):
    native = _native_axis_fixture(monkeypatch)
    native.plane(normal=normal, offset=offset, identity=identity)
    with pytest.raises(RuntimeError, match="native underside plane"):
        drawing._assert_pin_axis_geometry(native.model)


@pytest.mark.parametrize("name", ("A1", "B1", "A2", "B2"))
def test_actual_native_land_not_nominal_stock_controls_minimum(monkeypatch, name):
    native = _native_axis_fixture(monkeypatch)
    native.bore(name, land=10.49)
    with pytest.raises(RuntimeError, match=f"{name}: native straight land"):
        drawing._assert_pin_axis_geometry(native.model)


@pytest.mark.parametrize(
    "failure",
    ("missing", "duplicate", "third_station", "truncated", "nonfinite", "radius", "axis"),
)
def test_malformed_native_straight_land_rims_are_rejected(monkeypatch, failure):
    native = _native_axis_fixture(monkeypatch)
    circles = native.rims["A2"]
    if failure == "missing":
        circles.clear()
    elif failure == "duplicate":
        circles[1] = circles[0]
    elif failure == "third_station":
        circles.append((circles[0][0], -0.006, circles[0][2], 0.0, -1.0, 0.0, 0.005))
    elif failure == "truncated":
        circles[1] = circles[1][:-1]
    elif failure == "nonfinite":
        circles[1] = (math.nan, *circles[1][1:])
    elif failure == "radius":
        circles[1] = (*circles[1][:-1], 0.0053)
    elif failure == "axis":
        circles[1] = (*circles[1][:3], 1.0, 0.0, 0.0, 0.005)
    with pytest.raises(RuntimeError, match="A2: .*straight-land rim"):
        drawing._assert_pin_axis_geometry(native.model)


def _native_dimension_fixture(monkeypatch, *, land=False):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        _drawing_edge_dimensions._sw_type_info, "early_bound_or_flag",
        lambda value, *_args: value,
    )
    vertices = (object(), object())
    state = SimpleNamespace(attached=vertices, dangling=False, low=0.0, high=0.000015)
    owner = SimpleNamespace(Name="PinHoleProfile")
    tolerance = SimpleNamespace(
        Type=0, GetMinValue=lambda: state.low, GetMaxValue=lambda: state.high
    )
    dimension = SimpleNamespace(
        FullName="PinHoleDia@PinHoleProfile@carrier.SLDPRT",
        SystemValue=spec.PIN_STRAIGHT_LAND / 1000.0 if land else 0.010,
        Tolerance=tolerance, DrivenState=1, GetFeatureOwner=lambda: owner,
    )
    texts = {
        1: "(" if land else "", 2: ")" if land else "",
        4: spec.PIN_LAND_CALLOUT if land else spec.CALLOUTS_BELOW["PinHoleDia"],
        8: spec.PIN_LAND_CALLOUT if land else spec.CALLOUTS_BELOW["PinHoleDia"],
    }
    annotation = SimpleNamespace(
        Visible=1, IsDangling=lambda: state.dangling,
        GetAttachedEntities3=lambda: state.attached,
        GetAttachedEntityTypes=lambda: (3, 3),
    )
    state.precision = 1
    display = SimpleNamespace(
        Type2=2 if land else 6, ShowDimensionValue=True,
        GetDimension2=lambda _index: dimension, GetAnnotation=lambda: annotation,
        GetText=lambda index: texts.get(index, ""),
        GetPrimaryPrecision2=lambda: state.precision,
    )
    annotation.GetSpecificAnnotation = lambda: display
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    return SimpleNamespace(
        adapter=adapter, annotation=annotation, display=display, dimension=dimension,
        owner=owner, tolerance=tolerance, state=state, texts=texts, vertices=vertices,
    )


@pytest.mark.parametrize(
    "failure",
    (
        None, "owner", "name", "name_owner", "kind", "value", "low", "high",
        "symmetric_band", "hidden_value", "hidden_annotation", "dangling",
        "native_below", "resolved_below",
    ),
)
def test_ream_control_rejects_native_manufacturing_mutations(monkeypatch, failure):
    native = _native_dimension_fixture(monkeypatch)
    if failure == "owner":
        native.owner.Name = "SpotReference"
    elif failure == "name":
        native.dimension.FullName = "SpotDia@PinHoleProfile@carrier"
    elif failure == "name_owner":
        native.dimension.FullName = "PinHoleDia@SpotReference@carrier"
    elif failure == "kind":
        native.display.Type2 = 2
    elif failure == "value":
        native.dimension.SystemValue = 0.0101
    elif failure == "low":
        native.state.low = -0.000015
    elif failure == "high":
        native.state.high = 0.0
    elif failure == "symmetric_band":
        native.state.low, native.state.high = -0.000015, 0.000015
    elif failure == "hidden_value":
        native.display.ShowDimensionValue = False
    elif failure == "hidden_annotation":
        native.annotation.Visible = 0
    elif failure == "dangling":
        native.state.dangling = True
    elif failure == "native_below":
        native.texts[4] = spec.PIN_HOLE_CALLOUT
    elif failure == "resolved_below":
        native.texts[8] = spec.PIN_HOLE_CALLOUT
    if failure is None:
        drawing._assert_ream_control(native.adapter, native.annotation)
    else:
        with pytest.raises(RuntimeError, match="4X REAM lost"):
            drawing._assert_ream_control(native.adapter, native.annotation)


@pytest.mark.parametrize("kind", (2, 11, 12))
def test_native_land_accepts_linear_reference_with_actual_endpoints(monkeypatch, kind):
    native = _native_dimension_fixture(monkeypatch, land=True)
    native.display.Type2 = kind
    assert spec.PIN_STRAIGHT_LAND == pytest.approx(spec.THICKNESS - spec.PIN_CHAMFER)
    assert spec.PIN_STRAIGHT_LAND == pytest.approx(11.7)
    drawing._assert_land_control(native.adapter, native.display, native.vertices)


@pytest.mark.parametrize(
    "failure",
    (
        "angular", "diameter", "wrong_endpoint", "duplicate_endpoint",
        "extra_endpoint", "dangling", "fake_min_value", "chamfer_included",
        "nonfinite_value", "banded", "driving", "hidden_value", "hidden_annotation",
        "no_parentheses", "precision", "native_min", "resolved_min",
    ),
)
def test_native_land_rejects_false_reference_and_minimum_controls(monkeypatch, failure):
    native = _native_dimension_fixture(monkeypatch, land=True)
    if failure in ("angular", "diameter"):
        native.display.Type2 = 3 if failure == "angular" else 6
        native.display.GetAnnotation = lambda: pytest.fail("kind guard ran too late")
    elif failure == "wrong_endpoint":
        native.state.attached = (native.vertices[0], object())
    elif failure == "duplicate_endpoint":
        native.state.attached = (native.vertices[0], native.vertices[0])
    elif failure == "extra_endpoint":
        native.state.attached = (*native.vertices, object())
    elif failure == "dangling":
        native.state.dangling = True
    elif failure == "fake_min_value":
        native.dimension.SystemValue = 0.0105
    elif failure == "chamfer_included":
        native.dimension.SystemValue = spec.THICKNESS / 1000.0
    elif failure == "nonfinite_value":
        native.dimension.SystemValue = math.nan
    elif failure == "banded":
        native.tolerance.Type = 2
    elif failure == "driving":
        native.dimension.DrivenState = 0
    elif failure == "hidden_value":
        native.display.ShowDimensionValue = False
    elif failure == "hidden_annotation":
        native.annotation.Visible = 0
    elif failure == "no_parentheses":
        native.texts[1], native.texts[2] = "", ""
    elif failure == "precision":
        native.state.precision = 2
    elif failure == "native_min":
        native.texts[4] = "4X STRAIGHT\nLAND"
    elif failure == "resolved_min":
        native.texts[8] = "4X STRAIGHT\nLAND"
    with pytest.raises(RuntimeError, match="straight.land"):
        drawing._assert_land_control(native.adapter, native.display, native.vertices)


@pytest.mark.parametrize("section_sign", (-1.0, 1.0))
@pytest.mark.parametrize(
    "failure",
    (
        None, "endpoint_after_rebuild", "value_after_rebuild", "ref_after_rebuild",
        "wrong_label_edge", "missing_leader", "dangling_label", "moved_landing",
        "hidden_label", "changed_label", "ignored_offset", "ignored_offset_reset",
        "ignored_line_move", "malformed_line_arrow", "ignored_text_move",
        "line_follows_text", "nonfinite_offset_text",
        "malformed_offset_arrow", "offset_after_rebuild", "text_after_rebuild",
        "arrow_after_rebuild", "duplicate_arrow_after_rebuild",
        "missing_arrow_after_rebuild", "nonfinite_arrow_after_rebuild",
    ),
)
def test_native_land_authoring_and_settled_physical_underside(
    monkeypatch, section_sign, failure
):
    native = _native_dimension_fixture(monkeypatch, land=True)
    import _drawing_dimensions

    # Model native OffsetText semantics, not a monkeypatched offset helper:
    # moving an un-offset dimension moves its line AND text; OffsetText moves
    # text only. Start inherited-offset, so the explicit reset is exercised.
    native.state.offset = True
    native.state.position = (0.118, 0.0555, 0.1275)
    native.state.line_position = native.state.position[:2]
    native.state.arrows = []
    native.state.position_calls = []
    native.state.rebuilds = []

    class NativeDisplay(SimpleNamespace):
        @property
        def OffsetText(self):
            return native.state.offset

        @OffsetText.setter
        def OffsetText(self, value):
            if (failure == "ignored_offset" and value) or (
                failure == "ignored_offset_reset" and not value
            ):
                return
            native.state.offset = bool(value)

    native.display = NativeDisplay(**vars(native.display))
    native.display.GetDimension = lambda: native.dimension
    native.display.GetDisplayData = lambda: SimpleNamespace(
        GetArrowHeadCount=lambda: len(native.state.arrows),
        GetArrowHeadAtIndex2=lambda index: native.state.arrows[index],
    )
    native.dimension.Name = "RD1"
    native.annotation.GetSpecificAnnotation = lambda: native.display
    native.annotation.GetPosition = lambda: native.state.position
    native.adapter._attempt = lambda operation: operation()
    native.adapter._get_attr_or_call = lambda obj, name: getattr(obj, name)
    for module in (drawing, _drawing_dimensions):
        monkeypatch.setattr(
            module, "rebuild_drawing",
            lambda _adapter, *, label: native.state.rebuilds.append(label),
        )
    section = object()
    wall_x = spec.PIN_HOLES["A1"][0] + spec.PIN_HOLE_DIA / 2.0
    endpoints = (
        (wall_x, 0.0, 0.0),
        (wall_x, -spec.THICKNESS + spec.PIN_CHAMFER, 0.0),
    )
    underside_point = (
        spec.PIN_HOLES["A1"][0] - section_sign * 7.0, -spec.THICKNESS, 0.0
    )
    underside = object()
    picked = []

    def vertex_at(point, *, label):
        picked.append(point)
        return native.vertices[endpoints.index(point)]

    def line_through(point, *, label):
        assert point == underside_point
        return SimpleNamespace(edge=underside)

    scanner = SimpleNamespace(exact_vertex_at=vertex_at, exact_line_through=line_through)
    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_args, **_kwargs: scanner)
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, **_kwargs: [point[:2] for point in points],
    )
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda _adapter, _view, point, **_kwargs: point[:2],
    )
    monkeypatch.setattr(
        drawing, "_section_axes",
        lambda *_args: ((section_sign, 0.0, 0.0), (0.0, 1.0, 0.0)),
    )

    def refresh_arrows():
        native.state.arrows = [
            (
                native.state.line_position[0], point[1] / 1000.0, 0.1275,
                0.0, direction, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0,
            )
            for point, direction in zip(endpoints, (-1.0, 1.0), strict=True)
        ]

    def set_position(x, y, z):
        native.state.position_calls.append((native.display.OffsetText, (x, y, z)))
        if (
            not native.display.OffsetText and failure != "ignored_line_move"
        ) or failure == "line_follows_text":
            native.state.line_position = (x, y)
            refresh_arrows()
        if not (native.display.OffsetText and failure == "ignored_text_move"):
            native.state.position = (x, y, z)
        if native.display.OffsetText and failure == "nonfinite_offset_text":
            native.state.position = (x, math.nan, z)
        if native.display.OffsetText and failure == "malformed_offset_arrow":
            native.state.arrows[0] = native.state.arrows[0][:-1]
        if not native.display.OffsetText and failure == "malformed_line_arrow":
            native.state.arrows[0] = native.state.arrows[0][:-1]
        return True  # Even the ignored native operations report success.

    native.annotation.SetPosition2 = set_position

    def add_dimension(adapter, view, **kwargs):
        assert adapter is native.adapter and view is section
        assert kwargs["entities"] == native.vertices
        assert kwargs["entity_types"] == ("VERTEX", "VERTEX")
        assert kwargs["orientation"] == "vertical"
        assert kwargs["p0"] == tuple(value / 1000.0 for value in endpoints[0][:2])
        assert kwargs["p1"] == tuple(value / 1000.0 for value in endpoints[1][:2])
        assert kwargs["text_xy"] == drawing.PIN_LAND_LINE_XY
        native.state.line_position = (
            (kwargs["text_xy"][0] + 0.005, kwargs["text_xy"][1])
            if failure == "ignored_line_move" else kwargs["text_xy"]
        )
        refresh_arrows()
        return native.display

    def reference(adapter, annotation, **_kwargs):
        assert adapter is native.adapter and annotation is native.annotation
        native.texts[1], native.texts[2] = "(", ")"

    def precision(places, *_args):
        native.state.precision = places
        return True

    def text(index, value):
        assert index == 4
        native.texts[4] = native.texts[8] = value
        return True

    native.dimension.DrivenState = 0
    native.texts.update({1: "", 2: "", 4: "", 8: ""})
    native.state.precision = 3
    native.display.SetPrecision3 = precision
    native.display.SetText = text
    monkeypatch.setattr(drawing, "add_edge_dimension", add_dimension)
    monkeypatch.setattr(drawing, "set_reference_dimension", reference)
    under_xy = tuple(value / 1000.0 for value in underside_point[:2])
    label_state = SimpleNamespace(
        edge=underside, text="UNDERSIDE", leaders=1, dangling=False, landing=under_xy
    )
    label_annotation = SimpleNamespace(
        Visible=1, GetAttachedEntities3=lambda: (label_state.edge,),
        GetAttachedEntityCount3=lambda: 1, GetAttachedEntityTypes=lambda: (1,),
        GetLeaderCount=lambda: label_state.leaders,
        IsDangling=lambda: label_state.dangling,
        GetLeaderPointsAtIndex=lambda _index: (0.0, 0.0, 0.0, *label_state.landing, 0.0),
    )

    def add_label(adapter, view, **kwargs):
        assert adapter is native.adapter and view is section
        assert kwargs["text"] == "UNDERSIDE"
        assert kwargs["attached_to"] is underside
        assert kwargs["entity_xy"] == under_xy
        assert kwargs["note_xy"] == tuple(
            value + delta
            for value, delta in zip(under_xy, drawing.UNDERSIDE_LABEL_OFFSET, strict=True)
        )
        return SimpleNamespace(
            GetAnnotation=lambda: label_annotation, GetText=lambda: label_state.text
        )

    monkeypatch.setattr(drawing, "add_attached_note", add_label)
    immediate_failures = {
        "ignored_offset", "ignored_offset_reset", "ignored_text_move",
        "ignored_line_move", "malformed_line_arrow", "line_follows_text",
        "nonfinite_offset_text", "malformed_offset_arrow",
    }
    if failure in immediate_failures:
        with pytest.raises(RuntimeError, match="straight.land") as caught:
            drawing._add_pin_land_control(native.adapter, section)
        message = str(caught.value)
        if failure in ("ignored_line_move", "malformed_line_arrow"):
            assert "phase=before-text-offset" in message
            assert repr((drawing.PIN_LAND_LINE_XY[0], 0.0)) in message
            assert len(native.state.position_calls) == 1
            assert native.state.rebuilds == ["carrier straight-land dimension-line anchor"]
        elif failure in ("line_follows_text", "malformed_offset_arrow"):
            assert "phase=after-text-offset" in message
            assert repr((drawing.PIN_LAND_LINE_XY[0], 0.0)) in message
            assert len(native.state.position_calls) == 2
        if failure in ("ignored_line_move", "line_follows_text"):
            assert repr(tuple(tuple(arrow[:2]) for arrow in native.state.arrows)) in message
        elif failure in ("malformed_line_arrow", "malformed_offset_arrow"):
            assert repr(tuple(native.state.arrows[0])) in message
        return
    settled = drawing._add_pin_land_control(native.adapter, section)
    assert picked == list(endpoints)
    assert native.display.OffsetText is True
    assert native.state.position[:2] == drawing.PIN_LAND_TEXT_XY
    assert native.state.line_position == drawing.PIN_LAND_LINE_XY
    assert native.state.position_calls == [
        (False, (*drawing.PIN_LAND_LINE_XY, 0.1275)),
        (True, (*drawing.PIN_LAND_TEXT_XY, 0.0)),
    ]
    assert native.state.rebuilds == [
        "carrier straight-land dimension-line anchor", "offset_dimension_text"
    ]
    settled()
    # Model the final rebuild changing evaluated native state, not Python wiring.
    if failure == "endpoint_after_rebuild":
        native.state.attached = (native.vertices[0], object())
    elif failure == "value_after_rebuild":
        native.dimension.SystemValue = 0.0105
    elif failure == "ref_after_rebuild":
        native.dimension.DrivenState = 0
    elif failure == "offset_after_rebuild":
        native.state.offset = False
    elif failure == "text_after_rebuild":
        native.state.position = (
            drawing.PIN_LAND_TEXT_XY[0] - 0.005,
            drawing.PIN_LAND_TEXT_XY[1], 0.1275,
        )
    elif failure == "arrow_after_rebuild":
        arrow = native.state.arrows[1]
        native.state.arrows[1] = (arrow[0] + 0.005, *arrow[1:])
    elif failure == "duplicate_arrow_after_rebuild":
        native.state.arrows[1] = native.state.arrows[0]
    elif failure == "missing_arrow_after_rebuild":
        native.state.arrows.pop()
    elif failure == "nonfinite_arrow_after_rebuild":
        arrow = native.state.arrows[0]
        native.state.arrows[0] = (math.nan, *arrow[1:])
    elif failure == "wrong_label_edge":
        label_state.edge = object()
    elif failure == "missing_leader":
        label_state.leaders = 0
    elif failure == "dangling_label":
        label_state.dangling = True
    elif failure == "moved_landing":
        label_state.landing = (under_xy[0] + 0.005, under_xy[1])
    elif failure == "hidden_label":
        label_annotation.Visible = 0
    elif failure == "changed_label":
        label_state.text = "TOP"
    if failure is None:
        settled()
    else:
        with pytest.raises(RuntimeError, match="straight.land|underside.plane"):
            settled()


@pytest.mark.parametrize(
    "failure",
    (
        None, "auxiliary_arrow", "offset_false", "text_missing", "text_short", "text_extra",
        "text_nonfinite_z", "text_diagonal_drift", "text_just_outside",
        "arrow_missing", "arrow_duplicate", "arrow_short", "arrow_extra_field",
        "arrow_nonfinite_direction", "arrow_y_drift", "arrow_x_drift",
    ),
)
def test_native_land_layout_reads_complete_text_and_both_real_arrow_arrays(
    monkeypatch, failure
):
    native = _native_dimension_fixture(monkeypatch, land=True)
    layout = _b9e4_native_layout()
    captured = _b9e4_annotation(layout, "RD1", 2)
    projected = [(0.133, arrow[1]) for arrow in captured["display"]["arrows"]]
    position = [*drawing.PIN_LAND_TEXT_XY, captured["pos"][2]]
    arrows = [list(arrow) for arrow in captured["display"]["arrows"]]
    for arrow in arrows:
        arrow[0] = drawing.PIN_LAND_LINE_XY[0]
    # Native ordering and auxiliary offset-leader arrows are not promised.
    # Match BOTH physical endpoints, not indexes or a duplicate endpoint.
    arrows.reverse()
    native.display.OffsetText = failure != "offset_false"
    if failure == "text_missing":
        position = []
    elif failure == "text_short":
        position.pop()
    elif failure == "text_extra":
        position.append(0.0)
    elif failure == "text_nonfinite_z":
        position[2] = math.nan
    elif failure == "text_diagonal_drift":
        position[0] += 0.00004
        position[1] += 0.00004  # each axis < .05 mm; resultant exceeds it
    elif failure == "text_just_outside":
        position[0] += 0.0000501
    elif failure == "arrow_missing":
        arrows.pop()
    elif failure == "arrow_duplicate":
        arrows[1] = list(arrows[0])
    elif failure == "arrow_short":
        arrows[0].pop()
    elif failure == "arrow_extra_field":
        arrows[0].append(0.0)
    elif failure == "arrow_nonfinite_direction":
        arrows[0][3] = math.inf
    elif failure == "arrow_y_drift":
        arrows[0][1] += 0.0000501
    elif failure == "arrow_x_drift":
        arrows[0][0] += 0.0000501
    else:
        # Accept a finite native readback inside the real radial tolerance,
        # including nonzero z and small movement at both independent arrowtips.
        position[0] += 0.000049
        arrows[0][0] += 0.000049
        arrows[1][1] -= 0.000049
    if failure == "auxiliary_arrow":
        arrows.append([
            0.160, 0.050, 0.1275, -1.0, 0.0, 0.0,
            0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0,
        ])
    native.annotation.GetPosition = lambda: position
    native.display.GetDisplayData = lambda: SimpleNamespace(
        GetArrowHeadCount=lambda: len(arrows),
        GetArrowHeadAtIndex2=lambda index: arrows[index],
    )
    if failure in (None, "auxiliary_arrow"):
        drawing._assert_land_layout(native.display, projected)
    else:
        with pytest.raises(RuntimeError, match="straight.land native") as caught:
            drawing._assert_land_layout(native.display, projected)
        message = str(caught.value)
        if failure == "offset_false" or failure.startswith("text_"):
            assert f"OffsetText={native.display.OffsetText!r}" in message
            assert f"actual={tuple(position)!r}" in message
            assert f"requested={drawing.PIN_LAND_TEXT_XY!r}" in message
            error = re.search(r"error_m=([^,\s]+)", message)
            assert error is not None
            actual_error = float(error.group(1))
            expected_error = (
                math.dist(position[:2], drawing.PIN_LAND_TEXT_XY)
                if len(position) >= 2 and all(math.isfinite(value) for value in position[:2])
                else math.inf
            )
            if math.isinf(expected_error):
                assert math.isinf(actual_error)
            else:
                assert actual_error == pytest.approx(expected_error)
        else:
            assert "phase=after-text-offset" in message
            requested = tuple((drawing.PIN_LAND_LINE_XY[0], y) for _x, y in projected)
            assert f"requested={requested!r}" in message
            if failure in ("arrow_short", "arrow_extra_field", "arrow_nonfinite_direction"):
                assert repr(tuple(arrows[0])) in message
            else:
                assert f"actual={tuple(tuple(arrow[:2]) for arrow in arrows)!r}" in message
