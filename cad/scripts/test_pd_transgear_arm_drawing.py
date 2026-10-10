"""Offline contracts for the transgear arm (MHA-PD-018) drawing."""

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
    views = (drawing.FRONT_KEEP, drawing.SECTION_KEEP, drawing.LOCATOR_SECTION_KEEP,
             drawing.END_KEEP)
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
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
        and getattr(node.func, "attr", getattr(node.func, "id", "")) in {
            "curate_view_dimensions", "place_view",
        }
    ]
    imports = [
        call for call in calls if getattr(call.func, "attr", "") == "curate_view_dimensions"
    ]
    keep_sources = {
        ast.unparse(next(keyword.value for keyword in call.keywords if keyword.arg == "keep"))
        for call in imports
    }
    assert len(imports) == 4
    assert keep_sources == {"FRONT_KEEP", "SECTION_KEEP", "LOCATOR_SECTION_KEEP", "END_KEEP"}
    orientations = [
        call.args[2].value for call in calls
        if getattr(call.func, "id", "") == "place_view"
    ]
    assert sorted(orientations) == ["*Front", "*Isometric", "*Right"]
    for name in ("LocatorX1", "LocatorY1", "LocatorY2", "LocatorDia1"):
        assert name in drawing.FRONT_KEEP
    for view_keep in (
        drawing.FRONT_KEEP, drawing.SECTION_KEEP, drawing.LOCATOR_SECTION_KEEP, drawing.END_KEEP,
    ):
        assert all(len(xy) == 2 for xy in view_keep.values())
    # One frame per socket side, each landing on its own socket's rim.
    assert {int(math.copysign(1.0, y)) for _x, y in geometry.LOCATOR_SITES_MM} == set(
        drawing._LOCATOR_FRAMES
    )


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
        assert drawing.FRONT_KEEP[name][0] == pytest.approx(
            drawing._front_x(station / 2.0)
        )
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
    """The geometry module's wall and fit arithmetic uses rounded bands; each
    must cover the title-block row the printed places actually invoke."""
    for places, band in spec.BAND_BY_PLACES.items():
        assert band >= _band(places)
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
# rows, and the retired 3/4 pin's: with the latch hole's height at ±0.065
# (LATCH_PIN_HEIGHT_BAND) it barely clears in a 6.10 hole; 0.05 deeper it
# stops short of the face.
_PINNED_FAR_FACE_MARGIN = 0.811
_PINNED_OLD_PIN_MARGIN = 0.036
_PINNED_DEEPER_OLD_PIN_MARGIN = -0.014


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
    # Negative control: the 3/4 pin barely clears in a 6.10 hole and stops
    # short 0.05 deeper with the bends and the grade; without them it cleared.
    old = _printed_proud_range(0.75 * 25.4, 6.10)
    assert _worst_far_face_margin(printed, old) == pytest.approx(
        _PINNED_OLD_PIN_MARGIN, abs=1e-3
    )
    deeper = _printed_proud_range(0.75 * 25.4, 6.15)
    assert _worst_far_face_margin(printed, deeper) == pytest.approx(
        _PINNED_DEEPER_OLD_PIN_MARGIN, abs=1e-3
    )
    depth_only = (deeper[0] + _PIN_LENGTH_GRADE, deeper[1] - _PIN_LENGTH_GRADE)
    assert _worst_far_face_margin(printed, depth_only, bend_deg=0.0) > 0.0


def test_the_explicit_bands_are_the_spot_face_pin_ream_and_hole_positions() -> None:
    assert model_toleranced_dimensions(part) == {
        ("SpotFaceProfile", "SpotFaceDia"): "*deviations(SPOT_FACE_DIA_BAND)",
        ("SpotFaceProfile", "FloorDepth"): "SPOT_FACE_FLOOR_TOLERANCE",
        ("LocatorHoles", "LocatorDepth"): "LOCATOR_BLIND_DEPTH_BAND_MM",
        ("LocatorProfile", "f'LocatorDia{index}'"): "*deviations(LOCATOR_HOLE_BAND_MM)",
        ("PinHoleProfile", "PinHoleZ"): "LATCH_PIN_HEIGHT_TOLERANCE",
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
    assert lines[1] == f"PRESS FIT PIN {spec.LATCH_PIN_NUMBER}"
    assert lines[2] == f"{low:.4f}/{high:.4f} INTERFERENCE"
    assert lines[2] == "0.0025/0.0177 INTERFERENCE"


def test_the_pivot_bore_is_reamed_as_the_shoulder_running_fit() -> None:
    """A model reference cannot masquerade as a universal ±.130 bore zone."""
    lower, upper = geometry.PIVOT_BORE_DIAMETRAL_CLEARANCE
    assert (lower, upper) == pytest.approx((0.132, 0.152))
    assert geometry.PIVOT_BORE_DIA == pytest.approx(pivot_screw.SHOULDER_DIA + (lower + upper) / 2.0)
    assert joints.SHOULDER_RADIAL_CLEARANCE == pytest.approx(lower / 2.0)
    assert joints.PIVOT_RADIAL_FLOAT_MAX == pytest.approx(upper / 2.0)
    assert spec.PIVOT_BORE_CALLOUT.splitlines()[0] == "REAM TO MEASURED VN041"
    assert "SHOULDER +0.132/+0.152 DIA" in spec.PIVOT_BORE_CALLOUT
    assert "MATCHED SET; NOT INTERCHANGEABLE" in spec.PIVOT_BORE_CALLOUT
    # Rule 6: the matched fit rides the callout; no inspection-method note.
    assert not hasattr(spec, "PIVOT_FIT_INSPECTION_NOTE")
    assert "Pivot Fit Inspection" not in part._SAVED_DRAWING_PROPERTIES
    assert "BORE AXIS 90° TO FRONT FACE" in spec.PIVOT_BORE_CALLOUT
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
