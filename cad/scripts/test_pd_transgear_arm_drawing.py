"""Offline contracts for the transgear arm (MHA-PD-18) drawing."""

from __future__ import annotations

import ast
import itertools
import math
import re
import runpy
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import build_pd_transgear_arm as part
import draw_pd_transgear_arm as drawing
import pd_latch_hook_geometry as hook
import pd_latch_hook_spec as hook_spec
import pd_rack_pinion_spec as disc
import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as geometry
import pd_transgear_arm_spec as spec
import transgear_hanger_joints as joints
import pd_vn_transgear_latch_pin_spec as pin
import pd_transgear_pin_spec as cluster_pin
import _mcmaster_90325a174 as pivot_screw
from _drawing_registry import DRAWING_TEMPLATES
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm


def _band(places: int) -> float:
    return printed_band_mm(places, unit=geometry.UNIT)


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


def test_locating_sockets_print_in_the_front_view() -> None:
    """The sockets open in the rear face *Front looks at: no second rear view
    (run 7's 1:1 rear view crowded the sheet), every survivor a sheet pair."""
    for name in ("LocatorX1", "LocatorY1", "LocatorY2", "LocatorDia1"):
        assert name in drawing.FRONT_KEEP
    for view_keep in (drawing.FRONT_KEEP, drawing.SECTION_KEEP, drawing.END_KEEP):
        assert all(len(xy) == 2 for xy in view_keep.values())


def test_plate_tap_stations_follow_the_current_reducer_bore() -> None:
    """The pivot and pressed pin stay fixed; the knob bore and plate taps
    follow the live reducer centre distance in the arm's local frame."""
    theta = math.radians(disc.MESH_ANGLE_DEG) - math.radians(geometry.ARM_ANGLE_DEG)
    bore_station = geometry.PIN_STATION + disc.CENTRE_DISTANCE * math.cos(theta)
    bore_offset = disc.CENTRE_DISTANCE * math.sin(theta)
    assert geometry.KNOB_BORE_STATION == pytest.approx(bore_station)
    assert geometry.KNOB_BORE_OFFSET == pytest.approx(bore_offset)
    midpoint = bore_station + geometry.PLATE_CENTRELINE_OFFSET
    stations = tuple(
        midpoint + side * geometry.PLATE_SCREW_PITCH / 2.0 for side in (-1.0, 1.0)
    )
    assert geometry.PLATE_TAP_STATIONS == pytest.approx(stations)
    assert part.PLATE_TAP_STATIONS == pytest.approx(stations)
    for index, station in enumerate(stations, start=1):
        name = f"PlateTapStation{index}"
        assert name in spec.DRAWING_DIMENSIONS["StationReference"]
        text_x = drawing.FRONT_KEEP[name][0]
        middle = drawing._front_x(station / 2.0)
        if index == 1:
            # Mid-line unless the lower 6.850's box needs it further left
            # (test_the_socket_offsets_and_frames_stand_outside_the_arm); it
            # stays on its own line, well inside the pivot's extension line.
            assert drawing._front_x(0.0) + 0.007 < text_x <= middle + 1e-12
        else:
            assert text_x == pytest.approx(middle)
    assert drawing.TAP_CALLOUTS[0][1] == pytest.approx(stations[0])


@pytest.mark.parametrize("centre_change", (-0.5, 0.5))
def test_physical_centre_moves_the_bearing_not_the_pivot_latch_fixture(
    monkeypatch: pytest.MonkeyPatch, centre_change: float
) -> None:
    # This is a source-mutation control, not an admitted manufacturing grade.
    monkeypatch.setattr(disc, "CENTRE_DISTANCE", disc.CENTRE_DISTANCE + centre_change)
    fresh = runpy.run_path(geometry.__file__)
    theta = math.radians(disc.MESH_ANGLE_DEG) - math.radians(geometry.ARM_ANGLE_DEG)
    assert fresh["KNOB_BORE_STATION"] == pytest.approx(
        geometry.KNOB_BORE_STATION + centre_change * math.cos(theta)
    )
    assert fresh["KNOB_BORE_OFFSET"] == pytest.approx(
        geometry.KNOB_BORE_OFFSET + centre_change * math.sin(theta)
    )
    for name in ("PIN_STATION", "TIP_STATION", "PIN_MACHINE_Z", "ARM_U", "ARM_N"):
        assert fresh[name] == getattr(geometry, name)
    assert fresh["PLATE_TAP_STATIONS"] != geometry.PLATE_TAP_STATIONS


def test_the_walls_were_judged_at_no_less_than_the_printed_title_block_band() -> None:
    """The geometry module's wall and fit arithmetic uses printed reaches; each
    must cover the title-block row the printed places actually invoke."""
    precision = spec.DRAWING_PRECISION_BY_NAME
    for name, judged in (
        ("TipStation", geometry.TIP_STATION_BAND),
        ("PinHoleDepth", geometry.PIN_HOLE_DEPTH_BAND),
    ):
        assert judged >= _band(precision[name]), name


def test_the_thickness_prints_as_the_ground_stock_reference() -> None:
    """The stock's band governs the thickness, so its dimension prints in
    parentheses after the stock's own size, which is the modelled one."""
    prefix, suffix = spec.STOCK_TEXT_PREFIX, spec.STOCK_TEXT_SUFFIX
    assert prefix.endswith("(") and suffix.startswith(")")
    stock, band = prefix.rstrip("( ").split()
    assert float(Fraction(stock)) * 25.4 == pytest.approx(geometry.THICKNESS)
    # The stock's thickness band, which the seat tilt is judged at, prints.
    assert float(band.lstrip("±")) * 25.4 == pytest.approx(geometry.THICKNESS_BAND)
    assert "Depth" in drawing.END_KEEP
    # Machinist review r3 (rule 14): the dimension line ran along the
    # text's foot and its extension lines struck it. The text stands offset
    # above the line by more than a text line, under the top border.
    line_y = drawing.END_KEEP["Depth"][1]
    assert drawing.STOCK_TEXT_XY[1] - line_y >= 2.0 * _LINE_PITCH
    assert drawing.STOCK_TEXT_XY[1] + _LINE_PITCH < 0.2794 - _BORDER


# The latched arm's angular play about the pivot (IntegratorE's coupled
# stack), rad.
_ARM_ANGLE_PLAY = 0.00305


# The dowel family's length grade, +/-0.010 in (the 98381A catalogue rows).
_PIN_LENGTH_GRADE = 0.010 * 25.4


def _printed_proud_range(pin_length: float, hole_depth: float) -> tuple[float, float]:
    """The pin pressed to the hole floor: its length at either end of the
    family's grade less the depth at either end of its printed row's reach
    (the mm model printed rounded to inches)."""
    depth_band = geometry.PIN_HOLE_DEPTH_BAND
    assert depth_band >= _band(spec.DRAWING_PRECISION_BY_NAME["PinHoleDepth"])
    return (
        pin_length - _PIN_LENGTH_GRADE - (hole_depth + depth_band),
        pin_length + _PIN_LENGTH_GRADE - (hole_depth - depth_band),
    )


# The worst far-face margin this test's restatement finds at the printed
# reaches, and the retired 3/4 pin's: it barely clears in a 6.20 hole; 0.05
# deeper it stops short of the face.  #290: the tip station and the hole
# depth print rounded to .XX inch (reach 0.376 / 0.372), the hook its formed
# .XX ±.02 (FORMED_BAND .024 with the rounding, MHA-PD-14).
_PINNED_FAR_FACE_MARGIN = 0.890
_PINNED_OLD_PIN_MARGIN = 0.015
_PINNED_DEEPER_OLD_PIN_MARGIN = -0.035


def _worst_far_face_margin(
    tip_band: float,
    proud_range: tuple[float, float] | None = None,
    bend_deg: float | None = None,
) -> float:
    """Least axial distance by which the latch pin's full diameter passes
    the hook strip's far face, over every corner of the coupled stack: the
    MHA-PD-14 ear bent to either end of its angular row, turning the arm it
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
    bore_float = geometry.PIVOT_BORE_DIAMETRAL_CLEARANCE[1] / 2.0
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
        side = lateral * geometry.LATCH_PIN_HEIGHT_BAND
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
    printed = geometry.TIP_STATION_BAND  # the 128.9 model printed 5.07 ±.01
    assert printed >= _band(spec.DRAWING_PRECISION_BY_NAME["TipStation"])
    margin = _worst_far_face_margin(printed)
    assert margin == pytest.approx(_PINNED_FAR_FACE_MARGIN, abs=1e-3)
    # The spec leans the face by a tangent rather than this test's exact
    # turn, so it agrees within 0.01.
    assert 0.0 < joints.LATCH_PIN_FAR_FACE_MARGIN_WORST
    assert joints.LATCH_PIN_FAR_FACE_MARGIN_WORST == pytest.approx(margin, abs=0.01)
    # The spec judges the bend at the title block's angular row or wider.
    assert hook_spec.BEND_TOL_DEG >= _config.title_block("angular")["value_deg"]
    # The screws' float turns the hook about the pin as well as sliding it,
    # so the drift along U at the hole exceeds the pure slide.
    assert joints.HOOK_DRIFT_ALONG_U > joints.HOOK_SCREW_SHIFT
    # Negative control: the 3/4 pin barely clears in a 6.20 hole and stops
    # short 0.05 deeper with the bends and the grade; without them it cleared.
    old = _printed_proud_range(0.75 * 25.4, 6.20)
    assert _worst_far_face_margin(printed, old) == pytest.approx(
        _PINNED_OLD_PIN_MARGIN, abs=1e-3
    )
    deeper = _printed_proud_range(0.75 * 25.4, 6.25)
    assert _worst_far_face_margin(printed, deeper) == pytest.approx(
        _PINNED_DEEPER_OLD_PIN_MARGIN, abs=1e-3
    )
    depth_only = (deeper[0] + _PIN_LENGTH_GRADE, deeper[1] - _PIN_LENGTH_GRADE)
    assert _worst_far_face_margin(printed, depth_only, bend_deg=0.0) > 0.0


def test_the_explicit_bands_are_the_spot_face_and_the_reams() -> None:
    """The latch-pin hole's height has no explicit band: its .XXX title-block
    row governs (coordinator ruling (a), #2019)."""
    assert model_toleranced_dimensions(part) == {
        ("SpotFaceProfile", "SpotFaceDia"): "*deviations(SPOT_FACE_DIA_BAND)",
        ("SpotFaceProfile", "FloorDepth"): "SPOT_FACE_FLOOR_TOLERANCE",
        ("LocatorProfile", "f'LocatorDia{index}'"): "LOCATOR_HOLE_PRINT_TOLERANCE_MM",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_DIA_BAND)",
        ("PinBoreProfile", "PinBoreDia"): "*deviations(PIN_BORE_DIA_BAND)",
    }
    assert geometry.LATCH_PIN_HEIGHT_BAND == geometry.printed_reach_mm(
        geometry.PIN_HOLE_Z, spec.DRAWING_PRECISION_BY_NAME["PinHoleZ"]
    )
    assert not hasattr(spec, "LATCH_PIN_HEIGHT_TOLERANCE")
    # The piloted counterbore only cuts oversize; the pin's press hole must
    # never end up larger than nominal.
    assert min(spec.SPOT_FACE_DIA_BAND) == 0.0 < max(spec.SPOT_FACE_DIA_BAND)
    assert 0.0 >= max(geometry.PIN_HOLE_DIA_BAND) > min(geometry.PIN_HOLE_DIA_BAND)


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


_ENGAGEMENT_LINE = re.compile(r"ENGAGEMENT (\.\d{3}) MIN \((\d\.\d{2})D\)")


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
        printed_mm, printed_d = float(match[1]) * 25.4, float(match[2])
        worst_mm, major = worst[label]
        assert worst_mm - 0.0254 < printed_mm <= worst_mm + 1e-9, label
        assert worst_mm / major - 0.01 < printed_d <= worst_mm / major, label
        assert printed_d >= joints.ENGAGEMENT_TARGET_D, label
    # A MIN never rounds up.
    assert spec.engagement_line(7.749, 1.599) == "ENGAGEMENT .305 MIN (1.59D)"


def test_the_pin_bore_presses_the_mha_179_pin_at_every_limit() -> None:
    """R9-68: the #10-32 stud tap at S became a reamed bore that holds the
    MHA-PD-23 pin by a press at both limit pairs, and its ream band only cuts
    oversize."""
    loosest = cluster_pin.DIA_MIN - geometry.PIN_BORE_DIA_MAX
    tightest = cluster_pin.DIA_MAX - geometry.PIN_BORE_DIA_MIN
    assert (loosest, tightest) == pytest.approx((0.00762, 0.02794))
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
    assert (loosest, tightest) == pytest.approx((0.01524, 0.03302))
    assert spec.LATCH_PIN_PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    assert joints.LATCH_PIN_PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    assert _config.parts("pd-vn-transgear-latch-pin")["number"] == spec.LATCH_PIN_NUMBER
    low, high = spec.LATCH_PIN_PRESS_PRINTED
    assert 0.0 < low <= loosest + 1e-9
    assert loosest < tightest <= high + 1e-9 < tightest + 0.00254
    lines = spec.PIN_HOLE_CALLOUT.splitlines()
    assert lines[1] == f"PRESS FIT PIN {spec.LATCH_PIN_NUMBER}"
    assert lines[2] == ".0006/.0013 INTERFERENCE"
    # The owner-accepted ligament shortfall prints as a plain fact, rounded
    # down so the sheet never promises more wall than the budget holds.
    worst = geometry.WALLS["pin hole to faces"][1]
    assert spec.LATCH_PIN_WALL_PRINTED <= worst < spec.LATCH_PIN_WALL_PRINTED + 0.0254
    assert "PIN HOLE TO FACES .065 MIN" in lines


def test_the_pivot_bore_is_reamed_as_the_shoulder_running_fit() -> None:
    """A model reference cannot masquerade as a universal ±.130 bore zone."""
    lower, upper = geometry.PIVOT_BORE_DIAMETRAL_CLEARANCE
    assert (lower, upper) == pytest.approx((0.14224, 0.16256))
    assert geometry.PIVOT_BORE_DIA == pytest.approx(pivot_screw.SHOULDER_DIA + (lower + upper) / 2.0)
    assert joints.SHOULDER_RADIAL_CLEARANCE == pytest.approx(lower / 2.0)
    assert joints.PIVOT_RADIAL_FLOAT_MAX == pytest.approx(upper / 2.0)
    screw = _config.parts("pd-vn-transgear-pivot-screw")["number"]
    # The fit's facts, not its wording: reamed to the measured shoulder, the
    # diametral clearance band, the named screw and the matched set.
    flat = " ".join(spec.PIVOT_BORE_CALLOUT.split())
    for fact in (
        "MEASURED SHOULDER",
        ".0056-.0064 DIAMETRAL CLEARANCE",
        screw,
        "MATCHED SET",
    ):
        assert fact in flat, fact
    assert screw == "MHA-PD-VN-57"
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the matched fit rides the callout; no inspection-method note.
    assert not hasattr(spec, "PIVOT_FIT_INSPECTION_NOTE")
    assert "Pivot Fit Inspection" not in part._SAVED_DRAWING_PROPERTIES
    # Machinist review: the implied 90° to the front face is the title
    # block's angular row; a line restating it adds nothing.
    assert "90°" not in spec.PIVOT_BORE_CALLOUT
    assert geometry.PIVOT_AXIS_BINDING_SWEEP_MAX < lower
    assert lower - geometry.PIVOT_AXIS_BINDING_SWEEP_MAX >= 0.004


def test_pivot_fit_pays_the_real_general_angle_before_reducing_loaded_play(monkeypatch) -> None:
    # No hidden zero-angle assumption, and no stock shoulder variation added
    # twice to an acceptance fitted to the measured shaft.
    original = geometry.PIVOT_BORE_DIAMETRAL_CLEARANCE
    monkeypatch.setattr(geometry, "PIVOT_AXIS_BINDING_SWEEP_MAX",
                        geometry.PIVOT_AXIS_BINDING_SWEEP_MAX + 0.01)
    wider = geometry.pivot_running_clearance_mm()
    assert wider[0] > original[0]
    assert wider[1] - wider[0] == pytest.approx(original[1] - original[0])


@pytest.mark.parametrize("stock_deviation", pivot_screw.SHOULDER_DIA_LIMITS)
def test_matched_pivot_acceptance_follows_each_measured_stock_shoulder(stock_deviation) -> None:
    shaft = pivot_screw.SHOULDER_DIA + stock_deviation
    lower, upper = geometry.pivot_bore_limits_mm(shaft)
    clearance = geometry.PIVOT_BORE_DIAMETRAL_CLEARANCE
    assert (lower - shaft, upper - shaft) == pytest.approx(clearance)
    assert geometry.require_pivot_running_fit(lower, shaft) == pytest.approx(clearance[0])
    assert geometry.require_pivot_running_fit(upper, shaft) == pytest.approx(clearance[1])
    for rejected in (lower - 0.001, upper + 0.001):
        with pytest.raises(ValueError, match="measured-shoulder running clearance"):
            geometry.require_pivot_running_fit(rejected, shaft)


def test_replacement_stock_shoulder_needs_its_own_paired_fit_check() -> None:
    smallest = pivot_screw.SHOULDER_DIA + min(pivot_screw.SHOULDER_DIA_LIMITS)
    largest = pivot_screw.SHOULDER_DIA + max(pivot_screw.SHOULDER_DIA_LIMITS)
    bore = geometry.pivot_bore_limits_mm(smallest)[0]
    with pytest.raises(ValueError, match="measured-shoulder running clearance"):
        geometry.require_pivot_running_fit(bore, largest)
    with pytest.raises(ValueError, match="as-supplied stock limits"):
        geometry.pivot_bore_limits_mm(smallest - 0.001)


@pytest.mark.parametrize("persist", (False, True))
def test_native_pivot_ref_and_conditional_callout_check_void_side_effect(monkeypatch, persist) -> None:
    class NativeDisplay:
        def __init__(self):
            self.text = {}

        def SetText(self, channel, text):
            if persist:
                self.text[channel] = text
            return None  # IDisplayDimension::SetText is VT_VOID.

        def GetText(self, channel):
            return self.text.get(channel, "")

    display = NativeDisplay()
    monkeypatch.setattr(part, "_named_dimension", lambda *_: (display, object()))
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    if not persist:
        with pytest.raises(RuntimeError, match="did not persist"):
            part._author_pivot_fit_annotation(object())
        return
    part._author_pivot_fit_annotation(object())
    assert display.text == {1: "(<MOD-DIAM>", 2: ")", 4: spec.PIVOT_BORE_CALLOUT}


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


# Measured on 8b5e1f354's render (transgear-arm.pdf, 300 dpi): "FLOOR FROM"
# set 30.0 mm wide, and the 14.0 8.8 mm wide, centred on its line.  The
# section arrow stands 5 mm past the square end.
_CAPS_CHAR_WIDTH = 0.0030
_END_WIDTH_TEXT = 0.0088


def test_the_section_texts_stand_inside_the_left_border_and_off_the_section() -> None:
    """Machinist reviews of 19e33c6c2 and 8b5e1f354: the floor-depth text
    crossed the left border (rendered at x 1.5 mm), and the counterbore text
    crossed it before. Review of 2ac1bdb28: the floor's text names its
    spring, wider than the room left of its line, so it stands off the line
    on a leader, under the section and clear of the plate tap's frame. Run
    20261027T223014650Z: left of its line, the leader ran to the underline's
    right end up through the text, so the text stands right of its line,
    clear of section A-A's caption (centred under the section, about 46 mm
    wide); the isometric moved to sheet 2 (review of 67d749fb4)."""
    lines = ["6.40 \u00b10.05", *spec.FLOOR_DEPTH_CALLOUT.splitlines()]
    width = max(map(len, lines)) * _CAPS_CHAR_WIDTH
    half_height = len(lines) * _LINE_PITCH / 2.0
    x, y = drawing.FLOOR_TEXT_XY
    floor = (x - width / 2.0, y - half_height, x + width / 2.0, y + half_height)
    section_bottom = (
        drawing.SECTION_CENTER[1] - geometry.THICKNESS * drawing._S / 2000.0
    )
    assert floor[0] > _BORDER + 0.0015
    assert floor[1] > _BORDER + 0.0015
    assert floor[3] < section_bottom - 0.008
    assert floor[2] < drawing.SECTION_CENTER[0] - 0.023 - 0.005
    # Too wide to hang left of its line inside the border: hence the leader.
    line_x = drawing.SECTION_KEEP["FloorDepth"][0]
    assert line_x - width < _BORDER
    assert floor[0] > line_x + 0.005
    # The line stands off the pivot end it dimensions.
    pivot_end_x = drawing._front_x(-geometry.PIVOT_END_R)
    assert line_x < pivot_end_x
    # The counterbore's text stands right of its extension lines, above the
    # section (machinist review: between them, the lines struck it).
    counterbore = _counterbore_box()
    assert counterbore[0] > _BORDER + 0.003
    right_extension = drawing._front_x(geometry.SPOT_FACE_DIA / 2.0)
    assert counterbore[0] > right_extension + 0.002
    section_top = drawing.SECTION_CENTER[1] + geometry.THICKNESS * drawing._S / 2000.0
    assert counterbore[1] > section_top + 0.001
    # Datum A's tag stands right of it.
    assert counterbore[2] + 0.006 < drawing._front_x(56.0)


def _counterbore_box() -> tuple[float, ...]:
    return _centred_box(
        ["+0.1", "\u00d811.500 0.0", *spec.SPOT_FACE_CALLOUT.splitlines()],
        drawing.SECTION_KEEP["SpotFaceDia"],
    )


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


# "\u2316 \u00d80.050 A B C" as rendered on the stack sheet (1c103499e).
_POSITION_FRAME_WIDTH = 0.0446
_POSITION_FRAME_HEIGHT = 0.0069
# The boxed "6.850" basic with its leader shoulder, as rendered (run
# 20261027T124924064Z's audit: shoulder 137.0..151.5 mm, line at 151.5).
_BOXED_BASIC_WIDTH = 0.0145


def _front_station(sheet_x: float) -> float:
    return (sheet_x - drawing.FRONT_CENTER[0]) * 1000.0 / drawing._S + drawing._BBOX_CENTER_X


def test_the_socket_offsets_and_frames_stand_outside_the_arm() -> None:
    """Machinist review of the stack sheet: both 6.850 basics and both
    socket position frames sat inside the front view's silhouette, crowding
    the sockets and section line B."""
    for name, (_x, offset) in zip(("LocatorY1", "LocatorY2"), geometry.LOCATOR_SITES_MM):
        side = math.copysign(1.0, offset)
        # The boxed 6.850 and its shoulder hang LEFT of the dimension line.
        # Above the arm no witness line runs; below it, every station
        # witness line does, so the lower one stands left of plate tap 1's.
        line_x, text_y = drawing.FRONT_KEEP[name]
        box = (line_x - _BOXED_BASIC_WIDTH, text_y - 0.00175, line_x, text_y + 0.00175)
        tap_1 = drawing._front_x(geometry.PLATE_TAP_STATIONS[0])
        if side > 0:
            assert tap_1 < line_x < drawing._LOCATOR_X, name
        else:
            tap_hole_r = drawing.blind_cut_dia_mm(geometry.PLATE_TAP_SPEC) * drawing._S / 2000.0
            assert box[2] + 0.001 < tap_1 - tap_hole_r, name
            # Clear of plate tap 1's 32.929 on the first station row.
            assert box[0] > drawing.FRONT_KEEP["PlateTapStation1"][0] + 0.010, name
        edges = [
            drawing._front_y(side * geometry.edge_half_width(_front_station(x)))
            for x in (box[0], box[2])
        ]
        if side > 0:
            assert box[1] > max(edges) + 0.002, name
        else:
            assert box[3] < min(edges) - 0.002, name
    sheet_right = DRAWING_TEMPLATES[drawing.SPEC.layout].width_m - _BORDER
    mouth = drawing.LOCATOR_SECTION_CENTER[0] + geometry.THICKNESS * drawing._S / 2000.0
    radius = geometry.LOCATOR_HOLE_DIA_MM * drawing._S / 2000.0
    for _x, offset in geometry.LOCATOR_SITES_MM:
        side = math.copysign(1.0, offset)
        left, top = drawing._locator_frame_xy(offset)
        centre_y = top - _POSITION_FRAME_HEIGHT / 2.0
        axis_y = drawing.LOCATOR_SECTION_CENTER[1] + offset * drawing._S / 1000.0
        # Right of section B-B and inside the border, on its socket's side.
        assert mouth + 0.004 < left
        assert left + _POSITION_FRAME_WIDTH < sheet_right - 0.002
        assert side * (centre_y - axis_y) > 0.0
        # The leader from the frame's near end to the inner wall 1 mm in
        # crosses the mouth inside the socket's opening.
        land = (mouth - 1.0 * drawing._S / 1000.0, axis_y - side * radius)
        at_mouth = land[1] + (centre_y - land[1]) * (mouth - land[0]) / (left - land[0])
        assert abs(at_mouth - axis_y) < radius
    frames = [drawing._locator_frame_xy(offset) for _x, offset in geometry.LOCATOR_SITES_MM]
    assert abs(frames[0][1] - frames[1][1]) > _POSITION_FRAME_HEIGHT + 0.002


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
    assert drawing.OVERALL_TEXT_XY[1] - _LINE_PITCH > _counterbore_box()[3]


def test_registry_row_is_the_made_steel_mha_164() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-18"
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
    import _part_properties
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
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


def test_the_counterbore_and_its_floor_name_the_pivot_spring() -> None:
    """Machinist review (blocker): the counterbore's +0.1/0 and its floor's
    ±0.05 named no mate. The spring seats in it; the floor sets its room."""
    spring = _config.parts("pd-vn-transgear-pivot-spring")["number"]
    assert spring == "MHA-PD-VN-63"
    # The mate is named on the counterbore, and again on the floor whose
    # band sets its preload (review of 2ac1bdb28: a tight band names its
    # mate at its own callout).
    assert spring in " ".join(spec.SPOT_FACE_CALLOUT.split())
    floor = " ".join(spec.FLOOR_DEPTH_CALLOUT.split())
    assert spring in floor and "PRELOAD" in floor


def test_the_locating_holes_name_their_dowel_press_and_match_drill() -> None:
    """Machinist review (blocker and clarity): the reamed sockets named no
    dowel or fit, the mouth break no reason, and the match-drill sat in a
    general note with the pair's setting. The setting is MHA-PD-00 VIEW K's
    native S-K dimension; the callout points at it and prints no centre
    distance of its own (#1388 policy)."""
    import pd_vn_transgear_arm_plate_locating_pin_spec as dowel
    import _transgear_arm_plate_locating_interface as interface
    import pd_rack_pinion_spec as disc
    from pd_paper_drive_assembly_steps import knob_setting_ref

    loosest = min(dowel.DIA_LIMITS) - max(geometry.LOCATOR_HOLE_PRINTED_LIMITS_MM)
    tightest = max(dowel.DIA_LIMITS) - min(geometry.LOCATOR_HOLE_PRINTED_LIMITS_MM)
    assert spec.LOCATOR_PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    # The printed ream lies inside the interface's press limits.
    assert min(interface.PRESS_HOLE_LIMITS_MM) <= min(geometry.LOCATOR_HOLE_PRINTED_LIMITS_MM)
    assert max(geometry.LOCATOR_HOLE_PRINTED_LIMITS_MM) <= max(interface.PRESS_HOLE_LIMITS_MM)
    assert _config.parts("pd-vn-transgear-arm-plate-locating-pin")["number"] == dowel.PART_NUMBER
    plate = _config.parts("pd-transgear-arm-plate")["number"]
    flat = " ".join(drawing.LOCATOR_CALLOUT_TEXT.split())
    # The contract, not the wording: the through ream, the mouth break's
    # limit, the dowel and its interference, and the match-drill partner and
    # the assembly view that sets it.
    for fact in (
        "THRU",
        ".0019 MAX",
        dowel.PART_NUMBER,
        ".0002/.0007",
        plate,
        knob_setting_ref(),
    ):
        assert fact in flat, fact
    assert f"{disc.CENTRE_DISTANCE:.3f}" not in flat
    assert drawing.DIMENSION_CALLOUTS["LocatorDia1"] == drawing.LOCATOR_CALLOUT_TEXT


def test_the_locating_dowels_punch_out_from_the_front() -> None:
    """Machinist review (rule 16): a dowel pressed into a blind hole had no
    way out. The reams run through; the dowel, pressed from the rear to its
    proud set, stops short of the front face's mouth break on the thinnest
    stock, so a punch from the front drives it out."""
    import pd_vn_transgear_arm_plate_locating_pin_spec as dowel

    assert "LocatorDepth" not in drawing.DIMENSION_CALLOUTS
    assert "LocatorHoles" not in spec.DRAWING_DIMENSIONS
    deepest = max(dowel.INSERTION_LIMITS_MM)
    front_break = geometry.LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM
    thinnest = geometry.THICKNESS - geometry.THICKNESS_BAND
    assert spec.LOCATOR_PUNCH_AIR_MIN_MM == pytest.approx(thinnest - front_break - deepest)
    assert spec.LOCATOR_PUNCH_AIR_MIN_MM > 3.0
    assert geometry.LOCATOR_FULL_CYLINDER_SPAN_MIN_MM == pytest.approx(thinnest - 2.0 * front_break)


def test_each_projected_zone_is_a_dimensioned_chain_line_from_its_mating_face() -> None:
    """Machinist review of f4a5f03a1 (clarity, rule 7; all three runs): the
    frames gave each zone's height, but where it starts and which way it
    runs was printed only in general note 1. Each zone is drawn at its
    feature as a chain line on its own side, dimensioned with its height as
    the frame prints it, and the note is gone. Review of d5d1298b0: the pin
    bore's 32.6 rose through the plan's dimension lines (gating), so it is
    drawn in section D-D; no MIN. Review r7 (gating): each zone starts at the
    face its mating part seats on and runs outward, clear of the part (the
    taps' ran through the stock from face A), and D-D names its face."""
    import paper_drive_arm_registration as registration

    projected = {
        control.key: control
        for control in spec.GEOMETRIC_CONTROLS
        if control.projected_zone_height_mm is not None
    }
    assert set(drawing.PROJECTED_ZONE_CHAINS) == set(projected)
    assert set(spec.PROJECTED_ZONE_DIRECTION) == set(projected)
    # Face A is z = 0 with its outward normal -Z, so +Z runs rearward.
    face_a = spec.PART_DATUMS[0].face
    assert (face_a.normal, face_a.offset_mm) == ((0.0, 0.0, -1.0), 0.0)
    assert spec.PROJECTED_ZONE_REARWARD > 0.0 > spec.PROJECTED_ZONE_FORWARD
    taps = [key for key in projected if key.startswith("plate_tap_")]
    assert len(taps) == len(geometry.PLATE_TAP_STATIONS)
    for key in taps:
        # Rearward from the rear face, where the MHA-PD-19 plate seats, past
        # the seated screw head's contact.
        assert spec.PROJECTED_ZONE_DIRECTION[key] == spec.PROJECTED_ZONE_REARWARD
        assert spec.PROJECTED_ZONE_START_Z[key] == geometry.THICKNESS
        height = projected[key].projected_zone_height_mm
        assert geometry.THICKNESS + height >= joints.PLATE_SCREW_CONTACT_ARM_LOCAL_Z_MAX_MM
    # The pin bore's runs forward, to the chain plane in front of face A
    # (machine +Z runs rearward too).
    assert (
        registration.CHAIN_PLANE_MACHINE_Z_LIMITS_MM[0] < registration.ARM_FRONT_MACHINE_Z_MM
    )
    assert spec.PROJECTED_ZONE_DIRECTION["feed_stud_projected_axis"] == spec.PROJECTED_ZONE_FORWARD
    assert spec.PROJECTED_ZONE_START_Z["feed_stud_projected_axis"] == 0.0
    assert (
        projected["feed_stud_projected_axis"].projected_zone_height_mm
        == registration.S_PROJECTED_HEIGHT_MM
    )
    # Each line stands on its own hole's axis, in a view that cuts the hole
    # on that axis: the taps' in section A-A, the pin bore's in section D-D.
    stations = dict(zip(taps, geometry.PLATE_TAP_STATIONS))
    for key, chain in drawing.PROJECTED_ZONE_CHAINS.items():
        assert chain.x_mm == projected[key].face.contains_x_mm
        assert chain.view == ("A-A" if key in stations else "D-D"), key
        assert key not in stations or chain.x_mm == stations[key]
    # Every zone's height is printed: by its own dimension, or by one that
    # counts it ("2X") because it has the same height the same way.
    counts = {
        key: drawing.projected_zone_count(key)
        for key, chain in drawing.PROJECTED_ZONE_CHAINS.items() if chain.dimension is not None
    }
    assert sum(counts.values()) == len(projected)
    assert counts == {"plate_tap_1_position": 2, "feed_stud_projected_axis": 1}
    for control in projected.values():
        # The frame and its chain line print the height on the .001 in grid.
        inches = control.projected_zone_height_mm / 25.4
        assert inches == pytest.approx(round(inches, spec.DRAWING_REFERENCE_PRECISION), abs=1e-9)
        assert control.projection_unit == "in"
    assert not hasattr(spec, "PROJECTED_ZONE_HEIGHT_SUFFIX")
    # Section A-A (2:1, face A up): the taps' dimension line runs beside tap
    # 1's chain line, below the rear face, so its arrows land on the zone's
    # own ends; the "2X" value stands between the taps, within the zones.
    tap = drawing.PROJECTED_ZONE_CHAINS["plate_tap_1_position"]
    assert tap.dimension is not None and tap.dimension[1] == 0.0
    assert tap.dimension[0] >= 0.001
    assert tap.face_callout == ""
    rear_y = drawing.SECTION_CENTER[1] - geometry.THICKNESS * drawing._S / 2000.0
    tap_end_y = rear_y - projected["plate_tap_1_position"].projected_zone_height_mm * drawing._S / 1000.0
    assert tap.text_xy is not None
    assert tap_end_y < tap.text_xy[1] < rear_y - 0.004
    tap_x = [drawing._front_x(station) for station in geometry.PLATE_TAP_STATIONS]
    assert tap.text_xy[0] == pytest.approx(sum(tap_x) / 2.0)
    # Section D-D (rule 15: its own sheet at the sheet's 2:1, not shrunk
    # into a corner of sheet 1; looking toward the pivot, forward to the
    # right): the cut face and the 32.6 line under the sheet-2 plan (on
    # sheet 1's plan centre) and over the title block, with room for the
    # caption under them; D is not a datum letter.
    assert drawing.PIN_SECTION_LABEL not in {datum.letter for datum in spec.PART_DATUMS}
    assert len(drawing.SHEET_NAMES) == 2
    pin_height = projected["feed_stud_projected_axis"].projected_zone_height_mm * drawing._S / 1000.0
    thickness = geometry.THICKNESS * drawing._S / 1000.0
    centre_x, axis_y = drawing.PIN_SECTION_ZONE_CENTER
    face_x = centre_x - (pin_height - thickness) / 2.0
    left, right = face_x - thickness, face_x + pin_height
    half = geometry.edge_half_width(geometry.PIN_STATION) * drawing._S / 1000.0
    assert left > _BORDER + 0.020 and right < 0.4318 - _BORDER - 0.020
    plan_bottom = drawing._front_y(-geometry.PIVOT_END_R)
    assert axis_y + half + 0.020 < plan_bottom
    pin = drawing.PROJECTED_ZONE_CHAINS["feed_stud_projected_axis"]
    assert pin.dimension is not None and pin.dimension[0] == 0.0
    # Its dimension line clears the bore's mouth, beside the cut face; no
    # datum tag stands in D-D, so the value names its start face.
    assert geometry.PIN_BORE_DIA * drawing._S / 2000.0 < pin.dimension[1] < half
    assert pin.face_callout
    caption_top = axis_y - half - drawing._PIN_CAPTION_GAP_M
    title_block_top = 0.065
    assert caption_top - 0.016 > title_block_top + 0.005
    # No general notes remain (rule 7).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_note(" not in source
    assert not hasattr(drawing, "NOTES_TEXT")
    assert not hasattr(spec, "PROJECTED_ZONE_NOTE")


def test_the_rear_face_has_no_frame_and_the_stock_band_carries_its_parallelism() -> None:
    """Machinist review (over-specification): a // 0.050 A frame sat on the
    rear face of 5/16 ground stock. Owner ruling 2026-10-27 (#1379): no
    face carries a frame. The stock's thickness band bounds the plate seat's
    tilt to the arm's own surface under it (bow bends both faces together),
    and the plate screw's worst engagement still meets 1.5D at that tilt."""
    import paper_drive_arm_registration as registration

    assert all(
        control.characteristic not in ("parallelism", "flatness")
        for control in spec.GEOMETRIC_CONTROLS
    )
    assert registration.ARM_OPPOSITE_FACE_PARALLELISM_MM == pytest.approx(
        2.0 * geometry.THICKNESS_BAND
    )
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST_D >= joints.ENGAGEMENT_TARGET_D


def test_the_drawing_enforces_machinist_review() -> None:
    from _machinist_review_mode import MachinistReviewMode

    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
