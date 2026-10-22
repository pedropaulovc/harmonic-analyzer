"""Offline contracts for the oblique-trammel carrier plate (MHA-CH-06-TL-21)."""

from __future__ import annotations

import inspect
import math
import re
from pathlib import Path

import _config
import build_ch_rocker_arm_tl_oblique_carrier as part
import ch_rocker_arm_tl_oblique_carrier_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_carrier as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
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


def test_planar_selectors_use_offset_along_their_normal() -> None:
    """PlanarFace.offset_mm is n·p (farm jig-r1): the underside at y = -12
    seen along -Y sits at +12."""
    seat = requirements_for(drawing)["pin_collar_seat"].faces[0]
    assert seat.normal == (0.0, -1.0, 0.0)
    assert seat.offset_mm == spec.THICKNESS


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
