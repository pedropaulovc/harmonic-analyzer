"""Offline contracts for the transgear arm (MHA-PD-018) drawing."""

from __future__ import annotations

import ast
import itertools
import math
import re
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import build_pd_transgear_arm as part
import draw_pd_transgear_arm as drawing
import pd_latch_hook_geometry as hook
import pd_latch_hook_spec as hook_spec
import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as geometry
import pd_transgear_arm_spec as spec
import transgear_hanger_joints as joints
import vn_transgear_latch_pin_spec as pin
import pd_transgear_pin_spec as cluster_pin
import vn_transgear_pivot_screw_spec as pivot_screw
from _drawing_common import DRAWING_TEMPLATES
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _band(places: int) -> float:
    return _config.title_block(f"linear_{places}pl")["value_in"] * 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-arm.pdf")
    assert DRAWINGS_BY_NAME["pd_transgear_arm"].script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (drawing.FRONT_KEEP, drawing.SECTION_KEEP, drawing.END_KEEP)
    assert set().union(*views) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_the_walls_were_judged_at_no_less_than_the_printed_title_block_band() -> None:
    """The geometry module's wall and fit arithmetic uses rounded bands; each
    must cover the title-block row the printed places actually invoke."""
    for places, band in spec.BAND_BY_PLACES.items():
        assert band >= _band(places)
    precision = spec.DRAWING_PRECISION_BY_NAME
    for name, judged in (
        ("TipStation", geometry.TIP_STATION_BAND),
        ("PivotBoreDia", geometry.PIVOT_BORE_DIA_BAND),
        ("PinHoleDepth", geometry.PIN_HOLE_DEPTH_BAND),
    ):
        assert judged >= _band(precision[name]), name


def test_the_thickness_prints_as_the_ground_stock_reference() -> None:
    """The stock's band governs the thickness, so its dimension prints in
    parentheses after the stock's own size, which is the modelled one."""
    prefix, suffix = spec.STOCK_TEXT_PREFIX, spec.STOCK_TEXT_SUFFIX
    assert prefix.endswith("(") and suffix.startswith(")")
    stock_in = Fraction(prefix.rstrip("( "))
    assert float(stock_in) * 25.4 == pytest.approx(geometry.THICKNESS)
    assert "Depth" in drawing.END_KEEP


# The latched arm's angular play about the pivot (IntegratorE's coupled
# stack), rad.
_ARM_ANGLE_PLAY = 0.00305


# The dowel family's length grade, +/-0.010 in (the 98381A catalogue rows).
_PIN_LENGTH_GRADE = 0.010 * 25.4


def _printed_proud_range(pin_length: float, hole_depth: float) -> tuple[float, float]:
    """The pin pressed to the hole floor: its length at either end of the
    family's grade less the depth at either end of its printed row."""
    depth_band = _band(spec.DRAWING_PRECISION_BY_NAME["PinHoleDepth"])
    return (
        pin_length - _PIN_LENGTH_GRADE - (hole_depth + depth_band),
        pin_length + _PIN_LENGTH_GRADE - (hole_depth - depth_band),
    )


# The worst far-face margin this test's restatement finds at the printed
# rows, and the retired 3/4 pin's: in the 6.05 hole it barely clears with the
# hook's screw holes at ±0.05; 0.05 deeper it stops short of the face.
_PINNED_FAR_FACE_MARGIN = 0.741
_PINNED_OLD_PIN_MARGIN = 0.016
_PINNED_DEEPER_OLD_PIN_MARGIN = -0.034


def _worst_far_face_margin(
    tip_band: float,
    proud_range: tuple[float, float] | None = None,
    bend_deg: float | None = None,
) -> float:
    """Least axial distance by which the latch pin's full diameter passes
    the hook strip's far face, over every corner of the coupled stack: the
    MHA-PD-014 ear bent to either end of its angular row, turning the arm it
    carries about the bend line (machine Y through the ear's outer face at
    the bar's back face).  The pin is carried into the unbent hook's frame by
    the inverse turn, where the far face is the plane square to U at the
    hole's far station, moved along U by the hook's screw drift
    (``joints.HOOK_DRIFT_ALONG_U``), its formed band and the sheet's band."""
    if proud_range is None:
        proud_range = _printed_proud_range(pin.LENGTH, geometry.PIN_HOLE_DEPTH)
    if bend_deg is None:
        bend_deg = _config.title_block("angular")["value_deg"]
    pivot = (bar.PIVOT_TAP_X, hook.BAR_CENTRE_Y + bar.HANGER_TAP_Y)
    theta0 = math.atan2(
        hook.PIN_AXIS_XY[1] - pivot[1], hook.PIN_AXIS_XY[0] - pivot[0]
    )
    u0 = (math.cos(theta0), math.sin(theta0))
    station = math.hypot(
        hook.PIN_AXIS_XY[0] - pivot[0], hook.PIN_AXIS_XY[1] - pivot[1]
    )
    face0 = station + hook.SHEET_T / 2.0  # along u0 from the pivot
    bore_float = (
        geometry.PIVOT_BORE_DIA
        + geometry.PIVOT_BORE_DIA_BAND
        - pivot_screw.SHOULDER_DIA
        - min(pivot_screw.SHOULDER_DIA_LIMITS)
    ) / 2.0
    hinge = (hook.X_B, hook.BAR_BACK_FACE_Z)  # the bend line, in machine (x, z)
    radii = [(pin.DIA + band) / 2.0 for band in pin.DIA_BAND]
    signs = (-1.0, 1.0)
    margins = []
    corners = itertools.product(
        signs,
        proud_range,
        radii,
        signs,
        (-hook.SHEET_T_MINUS, hook.SHEET_T_PLUS),
        signs,
        signs,
        signs,
        signs,
        (-math.radians(bend_deg), math.radians(bend_deg)),
    )
    for tip, proud, r, drift, sheet, tap, float_, lateral, angle, bend in corners:
        theta = theta0 + angle * _ARM_ANGLE_PLAY
        ux, uy = math.cos(theta), math.sin(theta)
        # The pivot's tap (either axis at its band) and the shoulder's float,
        # taken along u0, the face's normal.
        reach = tap * bar.HOLE_POSITION_BAND * (abs(u0[0]) + abs(u0[1]))
        reach += float_ * bore_float
        px, py = pivot[0] + reach * u0[0], pivot[1] + reach * u0[1]
        # The crowned end's full-diameter circle, the pin off the arm's
        # centreline by its position band, at the pin's machine z.
        full = geometry.TIP_STATION + tip * tip_band + proud - pin.CROWN_R
        side = lateral * geometry.HOLE_POSITION_BAND
        centre = (px + full * ux - uy * side, py + full * uy + ux * side)
        # Into the unbent hook: turn the pin by -bend about the bend line.
        c, s = math.cos(bend), math.sin(bend)
        dx, dz = centre[0] - hinge[0], geometry.PIN_MACHINE_Z - hinge[1]
        centre_x = hinge[0] + dx * c - dz * s
        axis = (ux * c, uy, ux * s)
        along = axis[0] * u0[0] + axis[1] * u0[1]
        across = math.sqrt(max(0.0, 1.0 - along**2))
        # The far face along u0 from the pivot's model, moved by its bands.
        face = (
            face0
            + drift * (joints.HOOK_DRIFT_ALONG_U + hook_spec.FORMED_BAND)
            + sheet
        )
        gap = (
            (centre_x - pivot[0]) * u0[0] + (centre[1] - pivot[1]) * u0[1] - face
        )
        margins.append((gap - r * across) / along)
    return min(margins)


def test_the_latch_pin_full_diameter_passes_the_hook_at_the_printed_tip_band() -> None:
    """R9-23 / R9-50: the hook's pin hole is match-drilled across the pin, so
    nothing takes up the pin's reach along its axis: the tip station's band,
    the pin's length grade, the hole depth's row, the hook's screw drift and
    formed band, and the ear's bend all reach the pin's grip on the strip; the
    7/8 pin in the 8.50 hole keeps the full diameter through the strip at
    every corner of the printed rows."""
    printed = _band(spec.DRAWING_PRECISION_BY_NAME["TipStation"])  # 0.508
    margin = _worst_far_face_margin(printed)
    assert margin == pytest.approx(_PINNED_FAR_FACE_MARGIN, abs=1e-3)
    # The spec judges the rounder 0.51 rows and leans the face by a tangent
    # rather than this test's exact turn, so it agrees within 0.01.
    assert 0.0 < joints.LATCH_PIN_FAR_FACE_MARGIN_WORST
    assert joints.LATCH_PIN_FAR_FACE_MARGIN_WORST == pytest.approx(margin, abs=0.01)
    # The spec judges the bend at the title block's angular row or wider.
    assert hook_spec.BEND_TOL_DEG >= _config.title_block("angular")["value_deg"]
    # The screws' float turns the hook about the pin as well as sliding it,
    # so the drift along U at the hole exceeds the pure slide.
    assert joints.HOOK_DRIFT_ALONG_U > joints.HOOK_SCREW_SHIFT
    # Negative control: the 3/4 pin barely clears in the 6.05 hole and stops
    # short 0.05 deeper with the bends and the grade; without them it cleared.
    old = _printed_proud_range(0.75 * 25.4, 6.05)
    assert _worst_far_face_margin(printed, old) == pytest.approx(
        _PINNED_OLD_PIN_MARGIN, abs=1e-3
    )
    deeper = _printed_proud_range(0.75 * 25.4, 6.10)
    assert _worst_far_face_margin(printed, deeper) == pytest.approx(
        _PINNED_DEEPER_OLD_PIN_MARGIN, abs=1e-3
    )
    depth_only = (deeper[0] + _PIN_LENGTH_GRADE, deeper[1] - _PIN_LENGTH_GRADE)
    assert _worst_far_face_margin(printed, depth_only, bend_deg=0.0) > 0.0


def test_the_explicit_bands_are_the_spot_face_pin_ream_and_hole_positions() -> None:
    assert model_toleranced_dimensions(part) == {
        ("SpotFaceProfile", "SpotFaceDia"): "*deviations(SPOT_FACE_DIA_BAND)",
        ("SpotFaceProfile", "FloorDepth"): "SPOT_FACE_FLOOR_TOLERANCE",
        ("StationReference", "PinStation"): "HOLE_POSITION_TOLERANCE",
        ("StationReference", "PlateTapStation1"): "HOLE_POSITION_TOLERANCE",
        ("StationReference", "PlateTapStation2"): "HOLE_POSITION_TOLERANCE",
        ("PinHoleProfile", "PinHoleZ"): "HOLE_POSITION_TOLERANCE",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_DIA_BAND)",
        ("PinBoreProfile", "PinBoreDia"): "*deviations(PIN_BORE_DIA_BAND)",
    }
    # The piloted counterbore only cuts oversize; the pin's press hole must
    # never end up larger than nominal.
    assert min(spec.SPOT_FACE_DIA_BAND) == 0.0 < max(spec.SPOT_FACE_DIA_BAND)
    assert max(geometry.PIN_HOLE_DIA_BAND) == 0.0 > min(geometry.PIN_HOLE_DIA_BAND)


def test_the_section_cuts_through_the_pivot_and_the_square_end() -> None:
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert y0 == y1 == drawing.FRONT_CENTER[1]
    assert x0 < drawing._front_x(-geometry.PIVOT_END_R)
    assert x1 > drawing._front_x(geometry.TIP_STATION)


def test_the_qualifier_lines_ride_the_tap_thread_compartment() -> None:
    definitions = {
        5: "",
        6: "<MOD-DIAM><hw-tapdrilldia> THRU\n<hw-tapsize> - <hw-threadclass> THRU",
        7: "",
        8: "",
    }
    updated = drawing.tap_callout_definitions(definitions, drawing.PLATE_TAP_QUALIFIER)
    assert "<hw-threadclass>" not in updated[6].lower()
    assert updated[6].endswith(f"\n{drawing.PLATE_TAP_QUALIFIER}")
    assert {part: updated[part] for part in (5, 7, 8)} == {5: "", 7: "", 8: ""}
    with pytest.raises(RuntimeError):
        drawing.tap_callout_definitions({5: "", 6: "", 7: "", 8: ""}, "X")


_ENGAGEMENT_LINE = re.compile(r"ENGAGEMENT (\d+\.\d{2}) MIN \((\d\.\d{2})D\)")


def test_each_tap_callout_states_its_worst_case_full_thread_engagement() -> None:
    """Review of 19e33c6c2 (blocker): the sheet gave no engagement, so a blind
    reviewer charged 1.5 incomplete pitches at each end of the 5/16 stock.
    Each callout states the build's worst case, floored, at 1.5D or more."""
    worst = {
        "plate taps": (
            joints.PLATE_SCREW_ENGAGEMENT_WORST,
            joints.PLATE_SCREW.THREAD_MAJOR,
        ),
    }
    assert {row[0] for row in drawing.TAP_CALLOUTS} == set(worst)
    for label, *_, qualifier in drawing.TAP_CALLOUTS:
        match = _ENGAGEMENT_LINE.fullmatch(qualifier.splitlines()[-1])
        assert match, label
        printed_mm, printed_d = float(match[1]), float(match[2])
        worst_mm, major = worst[label]
        assert worst_mm - 0.01 < printed_mm <= worst_mm, label
        assert worst_mm / major - 0.01 < printed_d <= worst_mm / major, label
        assert printed_d >= joints.ENGAGEMENT_TARGET_D, label
    # A MIN never rounds up.
    assert spec.engagement_line(7.749, 1.599) == "ENGAGEMENT 7.74 MIN (1.59D)"


def test_the_pin_bore_presses_the_mha_179_pin_at_every_limit() -> None:
    """R9-68: the #10-32 stud tap at S became a reamed bore that holds the
    MHA-PD-023 pin by a press at both limit pairs, and its ream band only cuts
    oversize."""
    loosest = cluster_pin.DIA_MIN - geometry.PIN_BORE_DIA_MAX
    tightest = cluster_pin.DIA_MAX - geometry.PIN_BORE_DIA_MIN
    assert (loosest, tightest) == pytest.approx((0.010, 0.026))
    assert spec.PIN_PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    assert min(geometry.PIN_BORE_DIA_BAND) == 0.0 < max(geometry.PIN_BORE_DIA_BAND)


def test_the_latch_pin_hole_names_its_press_on_mha_169() -> None:
    """Review of 6de7230aa (blocker): the blind ream said PRESS FIT with no
    interference.  Smallest dowel in the largest hole and the reverse, both
    from printed bands, the callout rounding outward so it holds them."""
    loosest = (
        pin.DIA
        + min(pin.DIA_BAND)
        - geometry.PIN_HOLE_DIA
        - max(geometry.PIN_HOLE_DIA_BAND)
    )
    tightest = (
        pin.DIA
        + max(pin.DIA_BAND)
        - geometry.PIN_HOLE_DIA
        - min(geometry.PIN_HOLE_DIA_BAND)
    )
    assert (loosest, tightest) == pytest.approx((0.00254, 0.01762))
    assert spec.LATCH_PIN_PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    assert joints.LATCH_PIN_PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    assert _config.parts("vn-transgear-latch-pin")["number"] == spec.LATCH_PIN_NUMBER
    low, high = spec.LATCH_PIN_PRESS_PRINTED
    assert 0.0 < low <= loosest < tightest <= high < tightest + 1e-4
    lines = spec.PIN_HOLE_CALLOUT.splitlines()
    assert lines[1] == f"PRESS PIN {spec.LATCH_PIN_NUMBER} TO FLOOR"
    assert lines[2] == f"{low:.4f}/{high:.4f} INTERFERENCE"
    assert lines[2] == "0.0025/0.0177 INTERFERENCE"


def test_the_pivot_bore_is_reamed_as_the_shoulder_running_fit() -> None:
    """Review of 19e33c6c2: the Ø4.900 named no operation.  At the smallest
    bore its band accepts, the MHA-VN-041 shoulder keeps less radial air than a
    drill's oversize, so the bore is a fit bore and the callout names REAM."""
    drilled_growth = _config.title_block("drilled_hole")["plus_mm"]
    assert 0.0 < joints.SHOULDER_RADIAL_CLEARANCE < drilled_growth / 2.0
    assert spec.PIVOT_BORE_CALLOUT.split()[0] == "REAM"


# Default-format text, measured on r743-rocker-fix3's render (as
# test_transgear_drive_collar_drawing uses them); the landscape border.
_CHAR_WIDTH = 0.00276
_LINE_PITCH = 0.0045
_BORDER = 0.0127


def _centred_box(lines: list[str], xy: tuple[float, float]) -> tuple[float, ...]:
    half_width = max(map(len, lines)) * _CHAR_WIDTH / 2.0
    half_height = len(lines) * _LINE_PITCH / 2.0
    return (
        xy[0] - half_width,
        xy[1] - half_height,
        xy[0] + half_width,
        xy[1] + half_height,
    )


# Measured on 8b5e1f354's render (transgear-arm.pdf, 300 dpi): outside its
# witnesses the floor depth's text hangs LEFT of its dimension line, right
# edge on the line; "FLOOR FROM" set 30.0 mm wide, and the 14.0 8.8 mm wide,
# centred on its line.  The section arrow stands 5 mm past the square end.
_CAPS_CHAR_WIDTH = 0.0030
_END_WIDTH_TEXT = 0.0088


def _hanging_left_box(lines: list[str], xy: tuple[float, float]) -> tuple[float, ...]:
    width = max(map(len, lines)) * _CAPS_CHAR_WIDTH
    half_height = len(lines) * _LINE_PITCH / 2.0
    return (xy[0] - width, xy[1] - half_height, xy[0], xy[1] + half_height)


def test_the_section_texts_stand_inside_the_left_border_and_off_the_section() -> None:
    """Machinist reviews of 19e33c6c2 and 8b5e1f354: the floor-depth text
    crossed the left border (rendered at x 1.5 mm), and the counterbore text
    crossed it before."""
    lines = ["6.40 \u00b10.05", *spec.FLOOR_DEPTH_CALLOUT.splitlines()]
    floor = _hanging_left_box(lines, drawing.SECTION_KEEP["FloorDepth"])
    section_bottom = (
        drawing.SECTION_CENTER[1] - geometry.THICKNESS * drawing._S / 2000.0
    )
    assert floor[0] > _BORDER + 0.0015
    assert floor[3] < section_bottom - 0.002
    # The line stands off the pivot end it dimensions.
    pivot_end_x = drawing._front_x(-geometry.PIVOT_END_R)
    assert drawing.SECTION_KEEP["FloorDepth"][0] < pivot_end_x
    # Positive control: 8b5e1f354's keep reproduces its rendered left edge.
    old_line_x = pivot_end_x - (drawing.FRONT_CENTER[0] - 0.178) - 0.005
    assert _hanging_left_box(lines, (old_line_x, 0.0))[0] == pytest.approx(
        0.0015, abs=0.001
    )
    counterbore = _centred_box(
        ["\u00d811.500 +0.1", *spec.SPOT_FACE_CALLOUT.splitlines()],
        drawing.SECTION_KEEP["SpotFaceDia"],
    )
    assert counterbore[0] > _BORDER + 0.003


def test_the_end_width_text_clears_the_section_arrow_and_the_end_view() -> None:
    """The front view moved right for the floor-depth text; its 14.0 still
    stands between the A-A arrow and the end view's outline."""
    line_x = drawing.FRONT_KEEP["EndWidth"][0]
    text = (line_x - _END_WIDTH_TEXT / 2.0, line_x + _END_WIDTH_TEXT / 2.0)
    arrow_x = drawing.SECTION_LINE[1][0]
    end_left = drawing.END_CENTER[0] - geometry.THICKNESS * drawing._S / 2000.0
    assert text[0] - arrow_x >= 0.002
    assert end_left - text[1] >= 0.002


def test_the_tap_callouts_stand_inside_the_upper_border() -> None:
    """Review of 19e33c6c2: both tap callouts touched the upper border."""
    sheet_top = DRAWING_TEMPLATES[drawing.SPEC.layout].height_m - _BORDER
    for label, _station, _radius, xy, qualifier in drawing.TAP_CALLOUTS:
        # Drill and thread lines, then the qualifier's.
        lines = ["\u00d83.45 THRU ALL", "8-32 UNC THRU ALL", *qualifier.splitlines()]
        assert _centred_box(lines, xy)[3] + 0.001 < sheet_top - 0.003, label


def test_the_overall_reference_spans_the_pivot_round_to_the_square_end() -> None:
    """Review of 19e33c6c2: the 128.90 from the bore axis read as the overall
    length.  The reference runs from the pivot round's far extreme to the
    square end, under the station stack and over the section's callouts."""
    assert spec.OVERALL_LENGTH == pytest.approx(
        geometry.PIVOT_END_R + geometry.TIP_STATION
    )
    arc_pick, end_pick = drawing.OVERALL_PICKS
    pivot = (drawing._front_x(0.0), drawing._front_y(0.0))
    assert math.dist(arc_pick, pivot) == pytest.approx(
        geometry.PIVOT_END_R * drawing._S / 1000.0
    )
    assert arc_pick[0] < pivot[0]
    assert end_pick[0] == pytest.approx(drawing._front_x(geometry.TIP_STATION))
    end_half = geometry.TIP_END_R * drawing._S / 1000.0
    assert abs(end_pick[1] - drawing.FRONT_CENTER[1]) < end_half
    lowest_station = min(xy[1] for xy in drawing.FRONT_KEEP.values())
    assert drawing.OVERALL_TEXT_XY[1] <= lowest_station - drawing.STATION_PITCH + 1e-9
    counterbore_top = drawing.SECTION_KEEP["SpotFaceDia"][1] + 0.006
    assert drawing.OVERALL_TEXT_XY[1] - _LINE_PITCH > counterbore_top


def test_registry_row_is_the_made_steel_mha_164() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-018"
    assert int(row["quantity"]) == 1
    assert "ASTM A108" in row["material_specification"]
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = eval(ast.unparse(stamp.args[2]), vars(part)) if len(stamp.args) > 2 else {}
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert set(required) <= set(part._SAVED_DRAWING_PROPERTIES)
