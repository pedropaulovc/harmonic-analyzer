"""Offline contracts for the transgear arm (MHA-PD-18) drawing."""

from __future__ import annotations

import ast
import itertools
import math
import re
import runpy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _drawing_dimensions
import build_pd_transgear_arm as part
import draw_pd_transgear_arm as drawing
import pd_transgear_arm_notes as arm_notes
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
from _drawing_types import DRAWING_TEMPLATES
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import drilled_oversize_mm, printed_band_mm


def _band(places: int) -> float:
    return printed_band_mm(places, unit=geometry.UNIT)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-arm.pdf")
    assert DRAWINGS_BY_NAME["pd_transgear_arm"].script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (
        drawing.FRONT_KEEP,
        drawing.SECTION_KEEP,
        drawing.END_KEEP,
        drawing.PIN_SECTION_KEEP,
        drawing.PIN_PLAN_KEEP,
    )
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
    assert set(arm_notes.DIMENSION_CALLOUTS) <= marked


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
    assert geometry.TIP_STATION_BAND >= _band(precision["TipStation"])


def test_the_latch_pin_hole_depth_is_a_min_over_a_drill_point() -> None:
    """#3124: drilled and reamed to a drill point, the full-diameter depth a
    native MIN on the model (swTolMIN, the model value the limit, on the .XX
    grid) past the deepest-set pin.  Section A-A prints it as the controlling
    dimension and the callout carries it as REF (Codjiflo #3127 round 1).
    The pin is set proud at MHA-PD-00 step 10, and the part sheet carries no
    assembly instruction for it (machinist review of run
    20261119T200330557Z, rule 7)."""
    depth_in = geometry.PIN_HOLE_DEPTH / 25.4
    assert depth_in == pytest.approx(round(depth_in, spec.PIN_HOLE_DEPTH_PLACES))
    assert geometry.PIN_HOLE_DEPTH > max(pin.INSERTION_LIMITS)
    assert geometry.PIN_HOLE_POINT_LENGTH == pytest.approx(
        geometry.PIN_HOLE_DIA / 2.0 / math.tan(math.radians(59.0)), abs=1e-4
    )
    # The MIN prints as the model value with " MIN" its suffix and no native
    # tolerance (swTolMIN prints a lowercase "min."; fit batch review r1).
    calls = [
        node
        for node in ast.walk(ast.parse(Path(part.__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "_author_dimension_text"
    ]
    authored = {
        ast.unparse(call.args[2]): {kw.arg: ast.unparse(kw.value) for kw in call.keywords}
        for call in calls
    }
    assert authored == {
        "'SpotFaceDia'": {"lane": "1", "text": "COUNTERBORE_PREFIX"},
        "'PinHoleDepth'": {"lane": "2", "text": "MIN_SUFFIX", "limit": "PIN_HOLE_DEPTH"},
        "'PinMouthChamfer'": {"lane": "2", "text": "MIN_SUFFIX", "limit": "PIN_MOUTH_CHAMFER"},
    }
    assert spec.MIN_SUFFIX == " MIN"
    assert "set_single_limit" not in Path(part.__file__).read_text(encoding="utf-8")
    # The MIN's analysis record: the deepest hole that still holds the wall
    # target at the faces (run-off charged) and from its point to the pin
    # bore; on the 3/8 bar the pin bore governs (#2019).
    upper, lower = spec.PIN_HOLE_DEPTH_BAND
    assert lower == 0.0 and upper > 0.0
    run_off = math.tan(math.radians(geometry.DRILL_RUN_OFF_DEG))
    assert geometry.WALLS["pin hole to faces"][1] - upper * run_off >= geometry.WALL_TARGET
    assert geometry.WALLS["latch-pin hole point to pin bore"][1] - upper == pytest.approx(
        geometry.WALL_TARGET, abs=1e-6
    )
    assert "PinHoleDepth" in drawing.SECTION_KEEP
    assert "PinHoleDepth" not in drawing.REFERENCE_DIMENSIONS
    callout = arm_notes.PIN_HOLE_CALLOUT.splitlines()[0]
    assert callout == f"REAM <HOLE-DEPTH> ({depth_in:.2f})".replace("(0.", "(.", 1)
    assert "FLAT" not in arm_notes.PIN_HOLE_CALLOUT
    assert "MIN" not in arm_notes.PIN_HOLE_CALLOUT
    note = " ".join(arm_notes.NOTES[arm_notes.LATCH_PIN_NOTE - 1].split())
    assert "ASSEMBLY" not in note and "MHA-PD-00" not in note


def test_the_thickness_prints_as_the_ground_stock_reference() -> None:
    """The stock's catalogue tolerance governs the thickness, so its
    dimension prints in parentheses after the stock's own size, which is the
    modelled one, with no band (#2147: a supplier size is untoleranced REF)."""
    prefix, suffix = spec.STOCK_TEXT_PREFIX, spec.STOCK_TEXT_SUFFIX
    assert prefix.endswith("(") and suffix.startswith(")")
    (stock,) = prefix.rstrip("( ").split()
    assert float(Fraction(stock)) * 25.4 == pytest.approx(geometry.THICKNESS)
    assert "±" not in prefix + suffix and "REF" in suffix
    # The seat tilt and the screw engagement are judged at the precision-
    # ground bar's catalogue tolerance, ±.001 in (#2019).
    assert geometry.THICKNESS_BAND == pytest.approx(0.001 * 25.4)
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
# The retired pressed-to-floor hole's depth row: the 8.50 model printed .33,
# reaching 0.372 (the negative controls below restate the retired pins).
_FLOOR_DEPTH_REACH = 8.50 - (0.33 - 0.01) * 25.4


def _floor_pressed_proud_range(pin_length: float, hole_depth: float) -> tuple[float, float]:
    """A pin pressed to a flat floor (the retired design): its length at
    either end of the family's grade less the depth at either end of its
    printed .XX row's reach."""
    return (
        pin_length - _PIN_LENGTH_GRADE - (hole_depth + _FLOOR_DEPTH_REACH),
        pin_length + _PIN_LENGTH_GRADE - (hole_depth - _FLOOR_DEPTH_REACH),
    )


# The worst far-face margin this test's restatement finds at the printed
# reaches, and the retired 3/4 pin's: it stops short of the face in a 6.20
# hole and further short 0.05 deeper.  #290: the tip station prints rounded
# to .XX inch (reach 0.376), the hook its formed .XX ±.02 (FORMED_BAND .024
# with the rounding, MHA-PD-14).  The hook's screw holes take the title
# block's ±.005 (delegated ruling 2026-11-07, the bar's taps spotted through
# them), so the hook's screw drift grew; the MHA-PD-20 rear face parallel
# .001 to its front (fit audit 2026-11-23, pending owner confirmation)
# seats the pivot; the #9 drilled pivot bore floats the pivot .0135 at most
# (#2413's ream floated it .0085).  #3124: the 7/8 pin is set
# .516-.565 proud at assembly (owner decision 2026-11-19).  #2019: on the 3/8
# arm (latch height .188, hook hole on the moved axis) each margin is about
# 0.011 smaller.  #2422: the bar's pivot tap prints the title block's ±.005
# (it was ±.002; owner ruling 2026-11-20), which the pin's reach spends.
_SET_PROUD_WINDOW = (0.516 * 25.4, 0.565 * 25.4)
_PINNED_FAR_FACE_MARGIN = 0.221
_PINNED_OLD_PIN_MARGIN = -0.661
_PINNED_DEEPER_OLD_PIN_MARGIN = -0.711


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
        proud_range = _SET_PROUD_WINDOW
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
    the pin's set proud window, the hook's screw drift and formed band, and
    the ear's bend all reach the pin's grip on the strip; the 7/8 pin set
    .516-.565 proud keeps the full diameter through the strip at every
    corner of the printed rows."""
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
    assert joints.LATCH_PIN_PROUD_RANGE == pytest.approx(_SET_PROUD_WINDOW)
    # Negative control: the retired 3/4 pin pressed to a floor stops short in
    # a 6.20 hole, and further short 0.05 deeper, with the bends and the
    # grade; without them it stops less short.
    old = _floor_pressed_proud_range(0.75 * 25.4, 6.20)
    assert _worst_far_face_margin(printed, old) == pytest.approx(
        _PINNED_OLD_PIN_MARGIN, abs=1e-3
    )
    deeper = _floor_pressed_proud_range(0.75 * 25.4, 6.25)
    assert _worst_far_face_margin(printed, deeper) == pytest.approx(
        _PINNED_DEEPER_OLD_PIN_MARGIN, abs=1e-3
    )
    depth_only = (deeper[0] + _PIN_LENGTH_GRADE, deeper[1] - _PIN_LENGTH_GRADE)
    assert _worst_far_face_margin(
        printed, depth_only, bend_deg=0.0
    ) > _worst_far_face_margin(printed, deeper)


def test_the_explicit_bands_are_the_floor_and_the_rear_mouth() -> None:
    """The latch-pin hole's height has no explicit band: its .XXX title-block
    row governs (coordinator ruling (a), #2019).  The locating reams and the
    latch-pin ream print their set reamer's size and no band: their dowels
    are the gauges (fit audit 2026-11-23).  The counterbore's Ø prints at
    the title block's .XX (fit batch review r1: its +.004/0 answered no
    necessity test)."""
    assert model_toleranced_dimensions(part) == {
        ("SpotFaceProfile", "FloorDepth"): "SPOT_FACE_FLOOR_TOLERANCE",
    }
    assert geometry.LATCH_PIN_HEIGHT_BAND == geometry.printed_reach_mm(
        geometry.PIN_HOLE_Z, spec.DRAWING_PRECISION_BY_NAME["PinHoleZ"]
    )
    assert not hasattr(spec, "LATCH_PIN_HEIGHT_TOLERANCE")
    # The counterbore's Ø is the title block's .XX row, both ways.  The latch
    # pin's hole is modelled at its .1240 reamer's size, under the 1/8 dowel
    # at every size the reamer is modelled to cut.
    assert spec.SPOT_FACE_DIA_PLACES == spec.DRAWING_PRECISION_BY_NAME["SpotFaceDia"] == 2
    assert spec.SPOT_FACE_DIA_BAND == pytest.approx((0.254, -0.254))
    assert spec.COUNTERBORE_PREFIX == "<HOLE-SPOT> <MOD-DIAM>"
    assert geometry.PIN_HOLE_DIA == pytest.approx(0.1240 * 25.4)
    assert geometry.PIN_HOLE_DIA + max(geometry.PIN_HOLE_DIA_BAND) < pin.DIA + min(pin.DIA_BAND)


def test_the_section_cuts_through_the_pivot_and_the_square_end() -> None:
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert y0 == y1 == drawing.FRONT_CENTER[1]
    assert x0 < drawing._front_x(-geometry.PIVOT_END_R)
    assert x1 > drawing._front_x(geometry.TIP_STATION)


def test_the_tap_callout_drops_the_title_block_thread_class() -> None:
    definitions = {
        5: "",
        6: "<MOD-DIAM><hw-tapdrilldia> THRU\n<hw-tapsize> - <hw-threadclass> THRU",
        7: "",
        8: "",
    }
    updated = drawing.tap_callout_definitions(definitions, arm_notes.PLATE_TAP_QUALIFIER)
    assert "<hw-threadclass>" not in updated[6].lower()
    assert "<hw-tapsize>" in updated[6]
    assert updated[6].endswith(f"\n{arm_notes.PLATE_TAP_QUALIFIER}")
    assert {part: updated[part] for part in (5, 7, 8)} == {5: "", 7: "", 8: ""}
    with pytest.raises(RuntimeError):
        drawing.tap_callout_definitions({5: "", 6: "", 7: "", 8: ""}, "X")


@pytest.mark.parametrize("persist", (False, True))
def test_the_tap_callout_text_is_proved_by_its_readback(monkeypatch, persist) -> None:
    """IDisplayDimension::SetText is void: only the definitions and the
    resolved text read back prove the qualifier line took."""
    thread = "<MOD-DIAM><hw-tapdrilldia> THRU\n<hw-tapsize> - <hw-threadclass> THRU"

    class NativeCallout:
        def __init__(self):
            self.text = {6: thread, 2: thread}

        def SetText(self, part, text):
            if persist:
                self.text[part] = text
                self.text[part + 4] = text

        def GetText(self, part):
            return self.text.get(part, "")

    callout = NativeCallout()
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    if not persist:
        with pytest.raises(RuntimeError, match="did not persist"):
            drawing._set_tap_callout_text(callout, arm_notes.PLATE_TAP_QUALIFIER, label="taps")
        return
    drawing._set_tap_callout_text(callout, arm_notes.PLATE_TAP_QUALIFIER, label="taps")
    assert callout.text[2].endswith(arm_notes.PLATE_TAP_QUALIFIER)


def test_the_pin_is_bonded_in_the_bore_with_clearance_at_every_limit() -> None:
    """Owner ruling 2026-11-24, fit audit question 4: the reamed bore at
    S takes the one-diameter MHA-PD-23 pin, bonded.  The bore prints the
    reamer's size with no band and says the pin is turned to it; the pin,
    made last, prints rule 23's clearance and the trial on its own sheet
    (fit batch review r2).  The set pin that bounds the gap is the
    traveler's."""
    assert not hasattr(spec, "PIN_PRESS_INTERFERENCE")
    least, greatest = spec.PIN_BOND_GAP
    assert (least, greatest) == pytest.approx(cluster_pin.BOND_GAP)
    assert 0.0 < least < greatest <= spec.PIN_BOND_GAP_ACCEPTED_MAX
    assert spec.PIN_BOND_GAP_ACCEPTED_MAX == pytest.approx(
        spec.PIN_BORE_NO_GO_PIN_DIA - cluster_pin.DIA_MIN
    )
    assert spec.PIN_BOND_GAP_ACCEPTED_MAX < cluster_pin.LOCTITE_638_GAP_MAX
    assert spec.PIN_BOND_CLEARANCE_PRINTED == (least, spec.PIN_BOND_GAP_ACCEPTED_MAX)
    # Owner ruling 2026-11-24: the reason the bore is reamed is in the
    # part's necessity file, not on the sheet.
    assert arm_notes.PIN_BORE_CALLOUT.split("\n") == [
        "REAM THRU",
        f"{cluster_pin.PIN_NUMBER} BONDED, TURNED TO THIS BORE",
    ]
    assert "CLEARANCE" not in arm_notes.PIN_BORE_CALLOUT
    # The pin station's extension line stands left of the text and the
    # square end's right of it (r1 and r2 each struck a row), at the
    # 2.61 mm a character r2's sheet printed.
    text_x = drawing.FRONT_KEEP["PinBoreDia"][0]
    half = max(map(len, arm_notes.PIN_BORE_CALLOUT.split("\n"))) * 0.00261 / 2.0
    assert text_x - half > drawing._front_x(geometry.PIN_STATION) + 0.005
    assert text_x + half < drawing._front_x(geometry.TIP_STATION) - 0.005
    assert not hasattr(arm_notes, "PIN_NOTE")
    assert "PIN BORE" not in arm_notes.NOTES_TEXT
    assert cluster_pin.RETAINING_COMPOUND not in arm_notes.NOTES_TEXT
    assert "DOES NOT ENTER" not in arm_notes.PIN_BORE_CALLOUT
    assert not hasattr(arm_notes, "PIN_BORE_NECESSITY")
    # #2174: the rear mouth's band is its own native leg dimension's, in
    # section D-D, not callout text.
    assert "MOUTH" not in arm_notes.PIN_BORE_CALLOUT
    # The band is analysis only: the reamer only cuts oversize.
    assert min(geometry.PIN_BORE_DIA_BAND) == 0.0 < max(geometry.PIN_BORE_DIA_BAND)


def test_the_rear_mouth_prints_its_minimum_on_its_native_leg_in_d_d() -> None:
    """#2174 (Codjiflo on #2124): the rear mouth's leg is the revolved
    profile's native dimension, and the pin's root-clearance check reads its
    limits. Fit batch review r3: it prints one limit, .006 MIN (the model
    value with a MIN suffix); its upper limit is the title block's break.
    Section D-D cuts on the profile's plane; its text stands off the line,
    left of the cut face, its shoulder at the mouth's height, clear of the
    border, the plan and the title block."""
    assert spec.DRAWING_DIMENSIONS["PinBoreRearMouthProfile"] == {"PinMouthChamfer"}
    assert set(drawing.PIN_SECTION_KEEP) == {"PinMouthChamfer"}
    assert not hasattr(geometry, "PIN_MOUTH_CHAMFER_TOLERANCE")
    assert geometry.PIN_MOUTH_CHAMFER_LIMITS[0] == geometry.PIN_MOUTH_CHAMFER
    assert geometry.PIN_MOUTH_CHAMFER_LIMITS == pytest.approx((0.1524, 0.254))
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        'adapter, "PinBoreRearMouthProfile", "PinMouthChamfer", lane=2,\n'
        "        text=MIN_SUFFIX, limit=PIN_MOUTH_CHAMFER,"
    ) in source
    # Round 4: the mouth is named by the datum its face is opposite, never by
    # the undefined direction word REAR.
    assert arm_notes.PIN_MOUTH_CALLOUT.splitlines()[0] == "X 45\u00b0 MOUTH OPPOSITE DATUM A"
    assert "REAR" not in arm_notes.PIN_MOUTH_CALLOUT
    assert cluster_pin.PIN_NUMBER in arm_notes.PIN_MOUTH_CALLOUT
    lines = [".008 \u00b1.002", *arm_notes.PIN_MOUTH_CALLOUT.splitlines()]
    width = max(map(len, lines)) * _CAPS_CHAR_WIDTH
    half_height = len(lines) * _LINE_PITCH / 2.0
    x, y = drawing.PIN_MOUTH_TEXT_XY
    box = (x - width / 2.0, y - half_height, x + width / 2.0, y + half_height)
    line_x, mouth_y = drawing.PIN_SECTION_KEEP["PinMouthChamfer"]
    assert line_x < drawing.PIN_SECTION_REAR_X - 0.004
    assert box[2] < line_x - 0.002
    assert box[0] > _BORDER + 0.003
    assert box[1] <= mouth_y <= box[1] + _LINE_PITCH
    assert box[1] > 0.065 + 0.005
    assert box[3] < drawing._front_y(-geometry.PIVOT_END_R) - 0.010


@pytest.mark.parametrize("dropped", (None, "arm sheet", "section D-D", "sheet-2 plan"))
def test_each_import_phase_proves_the_precision_of_the_dimensions_it_imports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dropped: str | None
) -> None:
    """Run 20261105T023327427Z: sheet 1's guard demanded the whole package's
    places, D-D's PinMouthChamfer among them, before sheet 2 existed, and
    failed a sound import.  The real guard runs at each phase on what that
    phase's views import; together the phases cover every marked dimension,
    and a dimension a phase fails to import still fails the build."""
    sheet_one_names = [*drawing.FRONT_KEEP, *drawing.SECTION_KEEP, *drawing.END_KEEP]
    lost = {
        None: None,
        "arm sheet": sheet_one_names[0],
        "section D-D": "PinMouthChamfer",
        "sheet-2 plan": "FlankAngle",
    }[dropped]

    def annotation(name: str) -> SimpleNamespace:
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        display = SimpleNamespace(GetPrimaryPrecision2=lambda: places)
        return SimpleNamespace(name=name, GetSpecificAnnotation=lambda: display)

    def curate(_adapter, _view, *, keep, view_label, dimensions_by_feature):
        assert dimensions_by_feature is spec.DRAWING_DIMENSIONS
        return [annotation(name) for name in keep if name != lost]

    guarded: list[tuple[set[str], dict[str, int]]] = []

    def guard(adapter, annotations, precision):
        annotations = list(annotations)
        guarded.append(({a.name for a in annotations}, dict(precision)))
        _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)

    def open_model(_path):
        return True

    def finalize(*_args, **_kwargs):
        return {"drawing": "arm.SLDDRW"}

    source = tmp_path / "pd-transgear-arm.SLDPRT"
    source.write_bytes(b"")
    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "assert_imported_precision", guard)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda _adapter, a: a.name)
    monkeypatch.setattr(
        _drawing_dimensions._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
    )
    sheets = SimpleNamespace(ActivateSheet=lambda _name: True, ActivateView=lambda _name: True)
    returns = {
        "new_project_drawing": (object(), object()),
        "_early_bound": sheets,
        "place_view": object(),
        "create_section_view": object(),
        "_rim_point": (0.0, 0.0),
        "_wall_point": (0.0, 0.0),
        "model_point_in_view": (0.0, 0.0),
        "auto_center_marks": True,
        "add_native_hole_callout": object(),
        "_rear_rim": object(),
        "_pin_bore_section": object(),
        "add_note": object(),
    }
    for name in (
        "check", "read_required_properties", "create_blank_drawing_sheets",
        "stamp_drawing_summary", "set_hidden_lines_removed", "set_dimension_callouts",
        "_reference_dimensions", "_set_stock_text",
        "_end_radius_to_arc", "offset_dimension_text", "project_part_pmi",
        "_one_frame_per_dowel_group", "_overall_reference", "_set_tap_callout_text",
        "set_hole_callout_precision", "_section_captions_without_scale",
        "add_property_linked_note", *returns,
    ):
        monkeypatch.setattr(
            drawing, name, lambda *_a, _r=returns.get(name), **_k: _r
        )
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    adapter = SimpleNamespace(
        open_model=open_model, currentModel=object(), _attempt=lambda fn: fn()
    )

    if lost is not None:
        with pytest.raises(RuntimeError, match=rf"never reached the sheet: \['{lost}'\]"):
            drawing.build(adapter)
        return
    assert drawing.build(adapter) == {"drawing": "arm.SLDDRW"}
    assert [set(precision) for _names, precision in guarded] == [
        set(sheet_one_names),
        set(drawing.PIN_SECTION_KEEP),
        set(drawing.PIN_PLAN_KEEP),
    ]
    assert all(names == set(precision) for names, precision in guarded)
    for first, second in itertools.combinations([p for _n, p in guarded], 2):
        assert first.keys().isdisjoint(second)
    assert {k: v for _n, p in guarded for k, v in p.items()} == spec.DRAWING_PRECISION_BY_NAME


def test_the_flank_angle_stands_in_its_wedge_over_the_arm() -> None:
    """#2424 B (machinist review r1): the (2.4°) stands outside the outline,
    between the upper edge and the horizontal through its tangent point, on
    sheet 2's plan, short of cutting line D-D, and prints as a reference."""
    assert "FlankAngle" not in drawing.FRONT_KEEP
    assert "FlankAngle" in drawing.REFERENCE_DIMENSIONS
    x, y = drawing.PIN_PLAN_KEEP["FlankAngle"]
    station = (x - drawing.FRONT_CENTER[0]) * 1000.0 / drawing._S + drawing._BBOX_CENTER_X
    height = (y - drawing.FRONT_CENTER[1]) * 1000.0 / drawing._S
    assert geometry.edge_half_width(station) < height < geometry.PIVOT_TANGENT_Y
    assert station < geometry.PIN_STATION - 10.0
    assert part.FLANK_ANGLE_TEXT_XY == pytest.approx((station, height))


def test_the_latch_pin_hole_names_its_press_on_mha_169() -> None:
    """Fit audit 2026-11-23 (rule 4, reamed to the bought mate): the blind
    ream prints the .1240 set reamer's size with no band and no interference
    range; the MHA-PD-VN-58 dowel is the gauge (it does not enter by hand)
    and the note says what the press protects.  The range below is analysis:
    what the reamer is modelled to cut against the dowel's catalogue band."""
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
    assert not hasattr(spec, "LATCH_PIN_PRESS_PRINTED")
    # The callout links the note that names the pin, its acceptance by trial
    # and the necessity answer; no band, range or gauge is printed.
    # On the 3/8 bar the ligament to the faces holds the wall target, so the
    # note no longer prints the 5/16 bar's owner-accepted shortfall (#2019).
    assert spec.LATCH_PIN_NUMBER in arm_notes.NOTES[arm_notes.LATCH_PIN_NOTE - 1]
    assert f"SEE NOTE {arm_notes.LATCH_PIN_NOTE}" in arm_notes.PIN_HOLE_CALLOUT
    note = " ".join(arm_notes.NOTES[arm_notes.LATCH_PIN_NOTE - 1].split())
    assert "DOES NOT ENTER BY HAND" in note
    assert "HOLDS" not in note and "FASTENER" not in note
    assert "INTERFERENCE" not in note and not any(char.isdigit() for char in note[2:].replace(
        spec.LATCH_PIN_NUMBER, ""
    ))
    assert geometry.WALLS["pin hole to faces"][1] >= geometry.WALL_TARGET
    assert "PIN HOLE TO FACES" not in note


def test_the_pivot_bore_is_one_drill_running_clear_on_any_shoulder() -> None:
    """Owner ruling 2026-11-24, fit audit question 6: the rocking pivot
    takes a named drill under the DRILLED HOLES row, not a ream under a
    pin-gauge band; every as-supplied shoulder runs free in every hole the
    drill cuts."""
    lower, upper = geometry.PIVOT_BORE_DIAMETRAL_CLEARANCE
    bore_min, bore_max = geometry.PIVOT_BORE_FULL_LIMITS
    shoulder_min = pivot_screw.SHOULDER_DIA + min(pivot_screw.SHOULDER_DIA_LIMITS)
    shoulder_max = pivot_screw.SHOULDER_DIA + max(pivot_screw.SHOULDER_DIA_LIMITS)
    assert (lower, upper) == pytest.approx((bore_min - shoulder_max, bore_max - shoulder_min))
    assert (lower, upper) == pytest.approx((0.0085 * 25.4, 0.0135 * 25.4))
    assert geometry.PIVOT_BORE_DRILL == "#9"
    assert geometry.PIVOT_BORE_DIA == pytest.approx(0.196 * 25.4)
    # The analysis band is the drill's growth: the title block's row.
    assert geometry.PIVOT_BORE_DIA_BAND == pytest.approx(
        (drilled_oversize_mm(unit=geometry.UNIT), 0.0)
    )
    # The tightest pair still clears the bore's sweep at the angular row.
    assert lower >= geometry.PIVOT_RUNNING_CLEARANCE_MIN > geometry.PIVOT_AXIS_BINDING_SWEEP_MAX
    # What the tightest pair leaves for the bought screw's shoulder end,
    # which no drawing here controls: about .0015 out of square over the
    # shoulder's diameter (the MHA-PD-20 spacer's taper, its length band's
    # spread, is charged first).  MHA-PD-00 proves the arm swings free
    # before the spacer is bonded.
    allowed = geometry.PIVOT_SHOULDER_END_SQUARENESS_ALLOWED
    assert allowed == pytest.approx(0.00149 * 25.4, abs=0.0005)
    assert geometry.PIVOT_SHOULDER_END_ANGLE_ALLOWED == pytest.approx(0.00798, abs=1e-5)
    assert allowed == pytest.approx(
        shoulder_min * math.tan(geometry.PIVOT_SHOULDER_END_ANGLE_ALLOWED)
    )
    assert joints.SHOULDER_RADIAL_CLEARANCE == pytest.approx(lower / 2.0)
    assert joints.PIVOT_RADIAL_FLOAT_MAX == pytest.approx(upper / 2.0)
    screw = _config.parts("pd-vn-transgear-pivot-screw")["number"]
    # The fit's facts, not its wording: the named drill on the callout and
    # the named screw in the note it links; no number in the note.
    assert arm_notes.PIVOT_BORE_CALLOUT.startswith("#9 DRILL THRU")
    assert "REAM" not in arm_notes.PIVOT_BORE_CALLOUT
    assert f"SEE NOTE {arm_notes.PIVOT_NOTE}" in arm_notes.PIVOT_BORE_CALLOUT
    flat = " ".join(arm_notes.NOTES[arm_notes.PIVOT_NOTE - 1].split())
    assert screw in flat and "RUNNING CLEARANCE" in flat
    assert not re.search(r"\d", flat.removeprefix(f"{arm_notes.PIVOT_NOTE}.").replace(screw, ""))
    assert "MEASURED" not in flat
    assert screw == "MHA-PD-VN-57"
    assert not hasattr(spec, "PIVOT_FIT_INSPECTION_NOTE")
    assert "Pivot Fit Inspection" not in part._SAVED_DRAWING_PROPERTIES
    # Machinist review: the implied 90° to the front face is the title
    # block's angular row; a line restating it adds nothing.
    assert "90°" not in flat


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
    lines = [".2717 \u00b1.002", *arm_notes.FLOOR_CALLOUT.splitlines()]
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
    # It stands off its line on a leader, right of the line.
    line_x = drawing.SECTION_KEEP["FloorDepth"][0]
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
    return _centred_box(["\u2334 \u00d8.50"], drawing.SECTION_KEEP["SpotFaceDia"])


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
    """Review of 19e33c6c2: both tap callouts touched the upper border. The
    transfer line under the thread keeps the block inside it, and clear of
    the locating holes' callout to its right."""
    sheet_top = DRAWING_TEMPLATES[drawing.SPEC.layout].height_m - _BORDER
    locator_lines = [".1240", *arm_notes.LOCATOR_CALLOUT_TEXT.splitlines()]
    locator = _centred_box(locator_lines, drawing.FRONT_KEEP["LocatorDia1"])
    for label, _station, _radius, xy, qualifier in drawing.TAP_CALLOUTS:
        # Drill and thread lines, then the qualifier's.
        lines = ["\u00d8 .136 THRU ALL", "8-32 UNC THRU ALL", *qualifier.splitlines()]
        box = _centred_box(lines, xy)
        assert box[3] + 0.001 < sheet_top - 0.003, label
        assert box[2] + 0.005 < locator[0], label


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


def test_the_counterbore_and_its_floor_name_the_pivot_spring() -> None:
    """Machinist review (blocker): the counterbore's +0.1/0 and its floor's
    ±0.05 named no mate. The spring seats in it; the floor sets its room.
    Fit batch review r1: the Ø is a clearance pocket at the title block's
    row and carries no words; the floor's row names the spring it seats.
    Owner ruling 2026-11-24: why the floor's band is tight is in the part's
    necessity file, not on the sheet."""
    spring = _config.parts("pd-vn-transgear-pivot-spring")["number"]
    assert spring == "MHA-PD-VN-63"
    assert "SpotFaceDia" not in arm_notes.DIMENSION_CALLOUTS
    assert arm_notes.DIMENSION_CALLOUTS["FloorDepth"] == arm_notes.FLOOR_CALLOUT
    assert arm_notes.FLOOR_CALLOUT == f"SEATS SPRING {spring}"
    assert "SPRING" not in arm_notes.NOTES_TEXT
    # The registry reason: the room leaves the spring's working range at
    # the title block's ±.005.
    import transgear_hanger_joints as joints

    loosened = joints.SPRING_ROOM_MIN + geometry.SPOT_FACE_FLOOR_BAND - 0.127
    assert joints.SPRING_ROOM_MIN >= joints.SPRING.WORKING_HEIGHT > loosened


def test_every_sheet_one_note_link_names_the_notes_sheet() -> None:
    """Round 4 (clarity, rule 7): sheet 1's flags pointed to notes printed only
    on sheet 2. Every link names that sheet."""
    links = [
        line
        for text in arm_notes.DIMENSION_CALLOUTS.values()
        for line in text.splitlines()
        if "SEE NOTE" in line
    ]
    assert len(links) == 3
    assert all(line.endswith(f", SHEET {arm_notes.NOTES_SHEET}") for line in links)
    assert arm_notes.NOTES_SHEET == 2 == len(drawing.SHEET_NAMES)


def test_the_locating_holes_name_their_dowel_press_and_match_drill() -> None:
    """Machinist review (blocker and clarity): the reamed sockets named no
    dowel or fit, the mouth break no reason, and the match-drill sat in a
    general note with the pair's setting. The setting is MHA-PD-00 DETAIL K's
    native S-K dimension; the callout points at it and prints no centre
    distance of its own (#1388 policy)."""
    import pd_vn_transgear_arm_plate_locating_pin_spec as dowel
    import _transgear_arm_plate_locating_interface as interface
    import pd_rack_pinion_spec as disc
    from pd_paper_drive_assembly_steps import knob_setting_ref

    loosest = min(dowel.DIA_LIMITS) - max(geometry.LOCATOR_HOLE_REAMED_LIMITS_MM)
    tightest = max(dowel.DIA_LIMITS) - min(geometry.LOCATOR_HOLE_REAMED_LIMITS_MM)
    assert spec.LOCATOR_PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    assert (loosest, tightest) == pytest.approx((0.0006 * 25.4, 0.0013 * 25.4))
    # The holes are the .1240 set reamer's (analysis band +.0005/0), the
    # interface's press limits; the sheet prints the size and no band.
    assert geometry.LOCATOR_HOLE_DIA_MM == pytest.approx(0.1240 * 25.4)
    assert geometry.LOCATOR_HOLE_REAMED_LIMITS_MM == tuple(interface.PRESS_HOLE_LIMITS_MM)
    # .504 apart (12.8; fit audit 2026-11-23): the 1/8 holes keep the wall
    # target to both parts' edges.
    assert geometry.LOCATOR_PAIR_BASELINE_MM == 12.8
    assert _config.parts("pd-vn-transgear-arm-plate-locating-pin")["number"] == dowel.PART_NUMBER
    plate = _config.parts("pd-transgear-arm-plate")["number"]
    flat = " ".join(
        (arm_notes.LOCATOR_CALLOUT_TEXT + " " + arm_notes.NOTES[arm_notes.LOCATOR_NOTE - 1]).split()
    )
    # The contract, not the wording: the through ream, the dowel, its
    # acceptance by trial, what the press protects, and the match-drill
    # partner and the assembly view that sets it.  No interference range is
    # printed, and no mouth break: the title block's governs (fit batch
    # review r1).
    assert "MOUTH" not in flat and "MAX" not in flat
    assert geometry.LOCATOR_MOUTH_BREAK_MAX_MM == geometry.OUTLINE_EDGE_BREAK_MAX_MM
    for fact in (
        "THRU",
        dowel.PART_NUMBER,
        "DOES NOT ENTER BY HAND",
        plate,
        knob_setting_ref(),
    ):
        assert fact in flat, fact
    assert "INTERFERENCE" not in flat
    assert f"{disc.CENTRE_DISTANCE:.3f}" not in flat
    assert f"SEE NOTE {arm_notes.LOCATOR_NOTE}" in arm_notes.LOCATOR_CALLOUT_TEXT
    assert arm_notes.DIMENSION_CALLOUTS["LocatorDia1"] == arm_notes.LOCATOR_CALLOUT_TEXT


def test_the_locating_dowels_punch_out_from_the_front() -> None:
    """Machinist review (rule 16): a dowel pressed into a blind hole had no
    way out. The reams run through; the dowel, pressed from the rear to its
    proud set, stops short of the front face's mouth break on the thinnest
    stock, so a punch from the front drives it out."""
    import pd_vn_transgear_arm_plate_locating_pin_spec as dowel

    assert "LocatorDepth" not in arm_notes.DIMENSION_CALLOUTS
    assert "LocatorHoles" not in spec.DRAWING_DIMENSIONS
    deepest = max(dowel.INSERTION_LIMITS_MM)
    front_break = geometry.LOCATOR_MOUTH_BREAK_MAX_MM
    thinnest = geometry.THICKNESS - geometry.THICKNESS_BAND
    assert spec.LOCATOR_PUNCH_AIR_MIN_MM == pytest.approx(thinnest - front_break - deepest)
    assert spec.LOCATOR_PUNCH_AIR_MIN_MM > 1.0
    assert geometry.LOCATOR_FULL_CYLINDER_SPAN_MIN_MM == pytest.approx(thinnest - 2.0 * front_break)


def test_no_frame_carries_a_projected_zone_and_the_controls_are_as_ruled() -> None:
    """Delegated ruling 2026-11-07 (Main, no precedent; owner review #2144):
    rule 26 bars the projected-zone modifier, so no frame on MHA-PD-18
    carries one. The pin bore S (datum C) takes ⌖ Ø.004 to A|B and a plain
    ⊥ Ø.001 to A, the reamed row (owner ruling 2026-11-08, #2144 item 4.1);
    the 2X dowel reams ⌖ Ø.004 to A|B|C; the plate taps take no frame. The
    bore's axis, run on from the thinnest stock to the chain plane, is the S
    axis zone the stacks charge."""
    import paper_drive_arm_registration as registration
    from _gtol_frame import gtol_frame_signature

    controls = {control.key: control for control in spec.GEOMETRIC_CONTROLS}
    for control in controls.values():
        assert control.projected_zone_height_mm is None, control.key
        assert gtol_frame_signature(control.frame_xml).projected_zone_height_mm is None
        assert "ProjectedToleranceZone" not in control.frame_xml, control.key
        assert control.tolerance_zone == "diametral", control.key
    locators = [f"arm_locator_{index}_position" for index in range(1, len(geometry.LOCATOR_SITES_MM) + 1)]
    assert set(controls) == {"feed_stud_position", "feed_stud_perpendicularity", *locators}
    position, square = controls["feed_stud_position"], controls["feed_stud_perpendicularity"]
    assert (position.characteristic, position.tolerance, position.datums) == ("position", ".004", ("A", "B"))
    assert (square.characteristic, square.tolerance, square.datums) == ("perpendicularity", ".001", ("A",))
    for control in (position, square):
        assert control.face.diameter_mm == geometry.PIN_BORE_DIA
        assert control.face.contains_x_mm == geometry.PIN_STATION
    for key, xy in zip(locators, geometry.LOCATOR_SITES_MM, strict=True):
        control = controls[key]
        assert (control.characteristic, control.tolerance, control.datums) == ("position", ".004", ("A", "B", "C"))
        assert (control.face.contains_x_mm, control.face.contains_y_mm) == xy
    assert float(position.tolerance) * 25.4 <= geometry.REDUCER_POSITION_DIAMETER + 1e-12
    # Fit audit 2026-11-23: the bonded pin's axis leans by the bore's tilt
    # plus the widest accepted gap over the shortest bond.
    assert registration.S_AXIS_ZONE_DIAMETER_MM == pytest.approx(
        (float(square.tolerance) * 25.4 + spec.PIN_BOND_GAP_ACCEPTED_MAX)
        * registration.S_AXIS_RUN_ON_MM
        / cluster_pin.BOND_LENGTH_MIN
    )
    assert registration.S_AXIS_RUN_ON_MM > registration.S_PROJECTED_HEIGHT_MM
    assert cluster_pin.BOND_LENGTH_MIN < geometry.THICKNESS - geometry.THICKNESS_BAND
    # The datums the frames name are the part's: A the front face, B the
    # pivot bore, C the pin bore.
    assert [datum.letter for datum in spec.PART_DATUMS] == ["A", "B", "C"]
    assert spec.PART_DATUMS[2].face.diameter_mm == geometry.PIN_BORE_DIA
    # No projected-zone machinery is left on the spec or the sheet.
    for name in ("PROJECTED_ZONE_DIRECTION", "PROJECTED_ZONE_START_Z", "PROJECTED_ZONE_NOTE"):
        assert not hasattr(spec, name), name
    for name in ("PROJECTED_ZONE_CHAINS", "ZoneChain", "projected_zone_count", "_add_projected_zone_chains"):
        assert not hasattr(drawing, name), name


def test_the_plate_taps_are_transferred_from_the_plate_with_no_frame() -> None:
    """Q2-A: the 2X 8-32 taps are spotted and drilled through MHA-PD-19's
    screw holes at assembly with the plate doweled on, so PD-19's holes are
    the master: no frame, the transfer named on the tap callout, and their
    stations printed as references rather than BASIC."""
    assert not any("tap" in control.key for control in spec.GEOMETRIC_CONTROLS)
    stations = set(drawing.TAP_STATION_REFERENCES)
    assert stations == {f"PlateTapStation{index}" for index in range(1, len(geometry.PLATE_TAP_STATIONS) + 1)}
    assert stations <= spec.DRAWING_DIMENSIONS["StationReference"]
    assert stations.isdisjoint(name for _feature, name in spec.BASIC_REDUCER_DIMENSIONS)
    assert ("StationReference", "PinStation") in spec.BASIC_REDUCER_DIMENSIONS
    plate = _config.parts("pd-transgear-arm-plate")["number"]
    assert {row[4] for row in drawing.TAP_CALLOUTS} == {arm_notes.PLATE_TAP_QUALIFIER}
    assert plate in arm_notes.PLATE_TAP_QUALIFIER and "SPOT" in arm_notes.PLATE_TAP_QUALIFIER
    # The arm's walls pay the transferred taps' location.
    assert joints.PLATE_TAP_LOCATION_RADIUS_MAX_MM <= geometry.PLATE_TAP_LOCATION_RADIUS_MM


def test_the_dowel_group_prints_one_frame_with_its_count() -> None:
    """Machinist screen (clarity): identical frames were repeated on each
    hole instead of given once for the 2X group. The first socket's frame
    prints, with the count above it; the others' identical frames are
    hidden. The count stands clear of the latch-pin callout above it."""
    shown, hidden, count = drawing.dowel_group_frames()
    assert shown == "arm_locator_1_position"
    assert hidden == tuple(
        f"arm_locator_{index}_position" for index in range(2, len(geometry.LOCATOR_SITES_MM) + 1)
    )
    assert count == f"{len(geometry.LOCATOR_SITES_MM)}X" == "2X"
    left, top = drawing._locator_frame_xy(geometry.LOCATOR_SITES_MM[0][1])
    latch_lines = [".1240", *arm_notes.PIN_HOLE_CALLOUT.splitlines()]
    latch = _centred_box(latch_lines, drawing.END_KEEP["PinHoleDia"])
    assert top + _LINE_PITCH < latch[1] - 0.002
    sheet_right = DRAWING_TEMPLATES[drawing.SPEC.layout].width_m - _BORDER
    assert left + len(count) * _CHAR_WIDTH < sheet_right


def test_latch_pin_callout_stands_right_of_its_hole() -> None:
    """Round 3 (clarity): the latch-pin leader rose up-left from the text's
    left end through the "B" of BLIND. The text now starts at the hole's
    axis, so the leader rises straight up from its left end, and its right
    end stays inside the border."""
    lines = [
        line.replace("<HOLE-DEPTH>", "\N{DOWNWARDS ARROW}")
        for line in arm_notes.PIN_HOLE_CALLOUT.splitlines()
    ]
    left, _bottom, right, _top = _centred_box(lines, drawing.END_KEEP["PinHoleDia"])
    assert left >= drawing.END_CENTER[0] - 0.001
    sheet_right = DRAWING_TEMPLATES[drawing.SPEC.layout].width_m - _BORDER
    assert right <= sheet_right - 0.001


class _FakeGtol:
    def __init__(self, *, accept: bool, keep: bool):
        self.accept, self.keep, self.text = accept, keep, {}

    def SetText(self, part, text):
        if self.keep:
            self.text[part] = text
        return self.accept

    def GetText(self, part):
        return self.text.get(part, "")


class _FakeFrame:
    def __init__(self, gtol=None, *, sticky: bool = True):
        self._visible, self.gtol, self.sticky = 1, gtol, sticky

    @property
    def Visible(self):
        return self._visible

    @Visible.setter
    def Visible(self, value):
        if self.sticky:
            self._visible = value

    def GetSpecificAnnotation(self):
        return self.gtol


@pytest.mark.parametrize("defect", (None, "hide-lost", "count-refused", "count-lost"))
def test_the_dowel_group_frame_is_proved_by_readback(monkeypatch, defect) -> None:
    """IAnnotation::Visible and IGtol::SetText are read back after the
    rebuild: a frame that stays shown, or a count refused or lost, fails."""
    gtol = _FakeGtol(accept=defect != "count-refused", keep=defect != "count-lost")
    frames = {
        "arm_locator_1_position": _FakeFrame(gtol),
        "arm_locator_2_position": _FakeFrame(sticky=defect != "hide-lost"),
    }
    rebuilt = []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda _adapter, *, label: rebuilt.append(label))
    if defect is not None:
        with pytest.raises(RuntimeError):
            drawing._one_frame_per_dowel_group(object(), frames)
        return
    drawing._one_frame_per_dowel_group(object(), frames)
    assert frames["arm_locator_2_position"].Visible == 3  # swAnnotationHidden
    assert frames["arm_locator_1_position"].Visible == 1
    assert gtol.text == {3: "2X"}  # swGTolTextCalloutAbove
    assert rebuilt


def test_section_d_d_carries_the_rear_mouth_on_its_own_sheet() -> None:
    """Section D-D (rule 15: its own sheet at the sheet's 2:1, looking toward
    the pivot, the rear face left): its cut face under the sheet-2 plan (on
    sheet 1's plan centre) and over the title block, with room for the
    caption under it; D is not a datum letter."""
    assert drawing.PIN_SECTION_LABEL not in {datum.letter for datum in spec.PART_DATUMS}
    assert len(drawing.SHEET_NAMES) == 2
    thickness = geometry.THICKNESS * drawing._S / 1000.0
    centre_x, axis_y = drawing.PIN_SECTION_CENTER
    assert drawing.PIN_SECTION_REAR_X == pytest.approx(centre_x - thickness / 2.0)
    half = geometry.edge_half_width(geometry.PIN_STATION) * drawing._S / 1000.0
    assert drawing.PIN_SECTION_REAR_X > _BORDER + 0.020
    assert centre_x + thickness / 2.0 < 0.4318 - _BORDER - 0.020
    plan_bottom = drawing._front_y(-geometry.PIVOT_END_R)
    assert axis_y + half + 0.020 < plan_bottom
    caption_top = axis_y - half - drawing._PIN_CAPTION_GAP_M
    title_block_top = 0.065
    assert caption_top - 0.016 > title_block_top + 0.005


def test_sheet_one_captions_hang_under_their_own_cuts() -> None:
    """Round 4 (clarity): B-B's caption sat against section A-A's right end
    beside its (.33), and A-A's on the title block's top edge. Each now hangs
    under its own cut: B-B's stacked name (~32 mm wide) stands ~10 mm right
    of A-A's end, and A-A's one line stays above the title block."""
    targets = drawing.section_caption_targets()
    assert {label: sheet for label, (sheet, _xy) in targets.items()} == {
        "A-A": 0, "B-B": 0, "D-D": 1,
    }
    assert drawing.SECTION_CAPTION_TEXTS["B-B"].splitlines() == ["<VLNAME>", "<VLLABEL>"]
    section_right = drawing._front_x(geometry.TIP_STATION)
    bb_x, bb_top = targets["B-B"][1]
    assert bb_x - 0.032 / 2.0 > section_right + 0.008
    a_a_bottom = drawing.SECTION_CENTER[1] - geometry.THICKNESS * drawing._S / 2000.0
    assert bb_top < drawing.LOCATOR_SECTION_CENTER[1] and bb_top - 0.016 > 0.065 + 0.005
    aa_x, aa_top = targets["A-A"][1]
    assert aa_top < a_a_bottom
    assert aa_top - 0.008 > 0.065 + 0.003


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


def _in(value: float) -> float:
    return value * 25.4


def test_the_arm_declares_one_owner_per_face() -> None:
    import export_features
    from _gtol_face import FaceGeometry

    def plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
        point = tuple(value * offset_mm / 1000 for value in normal)
        return FaceGeometry(None, 4001, (*normal, *point), normal, ())

    def cylinder(dia_mm: float, box_mm: tuple[float, ...]) -> FaceGeometry:
        box = tuple(value / 1000 for value in box_mm)
        return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, 0, 0, 1, dia_mm / 2000), None, box)

    def cone(half_angle_deg: float, box_mm: tuple[float, ...]) -> FaceGeometry:
        box = tuple(value / 1000 for value in box_mm)
        parameters = (0.0, 0.0, 0.0, 0, 0, 1, 0.002, math.radians(half_angle_deg), 1, 0, 0)
        return FaceGeometry(None, 4003, parameters, None, box)

    manifest = export_features.requirement_manifest("pd_transgear_arm")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == {
        "front_face": "face",
        "rear_face": "face",
        "end_face": "face",
        "pivot_end": "arc",
        "flanks": "tapered_side",
        "pivot_bore": "hole",
        "spot_face": "counterbore",
        "pin_bore": "hole",
        "pin_mouth": "chamfer",
        "latch_pin_hole": "hole",
        "dowel_holes": "assembly_hole",
        "plate_taps": "assembly_hole",
    }
    t, s = geometry.THICKNESS, geometry.PIN_STATION
    lean = geometry.EDGE_LEAN
    tip, depth = geometry.TIP_STATION, geometry.PIN_HOLE_DEPTH
    tap = drawing._PLATE_TAP_DRILL
    (lx, ly), (_lx2, ly2) = geometry.LOCATOR_SITES_MM
    floor = geometry.SPOT_FACE_FLOOR_FROM_FRONT
    faces = {
        "front_face": plane((0.0, 0.0, -1.0), 0.0),
        "rear_face": plane((0.0, 0.0, 1.0), t),
        "end_face": plane((1.0, 0.0, 0.0), tip),
        "pivot_end": cylinder(2 * geometry.PIVOT_END_R, (-12.5, -12.5, 0.0, 0.6, 12.5, t)),
        "flanks/upper": plane((math.sin(lean), math.cos(lean), 0.0), geometry.PIVOT_END_R),
        "flanks/lower": plane((math.sin(lean), -math.cos(lean), 0.0), geometry.PIVOT_END_R),
        "pivot_bore": cylinder(geometry.PIVOT_BORE_DIA, (-2.5, -2.5, 0.0, 2.5, 2.5, floor)),
        "spot_face/wall": cylinder(geometry.SPOT_FACE_DIA, (-6.4, -6.4, floor, 6.4, 6.4, t)),
        "spot_face/floor": plane((0.0, 0.0, 1.0), floor),
        "pin_bore": cylinder(geometry.PIN_BORE_DIA, (s - 1.6, -1.6, 0.0, s + 1.6, 1.6, t - 0.2)),
        "pin_mouth": cone(45.0, (s - 1.8, -1.8, t - 0.2, s + 1.8, 1.8, t)),
        "latch_pin_hole": cylinder(geometry.PIN_HOLE_DIA, (tip - depth, -1.6, 3.2, tip, 1.6, 6.4)),
        "dowel_holes/1": cylinder(geometry.LOCATOR_HOLE_DIA_MM, (lx - 1.2, ly - 1.2, 0.0, lx + 1.2, ly + 1.2, t)),
        "dowel_holes/2": cylinder(geometry.LOCATOR_HOLE_DIA_MM, (lx - 1.2, ly2 - 1.2, 0.0, lx + 1.2, ly2 + 1.2, t)),
        **{
            f"plate_taps/{index}": cylinder(tap, (x - 1.8, -1.8, 0.2, x + 1.8, 1.8, t - 0.2))
            for index, x in enumerate(geometry.PLATE_TAP_STATIONS, 1)
        },
    }
    # The tap mouths' 90-degree breaks and the latch hole's drill point are
    # nobody's: no declared selector takes them.
    strays = {
        "tap break": cone(45.0, (geometry.PLATE_TAP_STATIONS[0] - 2.0, -2.0, t - 0.3, geometry.PLATE_TAP_STATIONS[0] + 2.0, 2.0, t)),
        "drill point": cone(59.0, (tip - depth - 1.0, -1.6, 3.2, tip - depth, 1.6, 6.4)),
    }
    selectors = export_features.feature_selectors("pd_transgear_arm")
    for name, face in faces.items():
        owners = [owner for owner, specs in selectors.items() if any(spec_.matches(face) for spec_ in specs)]
        assert owners == [name.split("/")[0]], name
    for name, face in strays.items():
        assert not [owner for owner, specs in selectors.items() if any(spec_.matches(face) for spec_ in specs)], name


def test_arm_feature_bands_are_the_printed_ones() -> None:
    import export_features

    features = export_features.requirement_manifest("pd_transgear_arm")["features"]
    end = features["end_face"]
    assert end["station"] == pytest.approx([_in(5.06), _in(5.08)])
    assert end["width"] == pytest.approx([_in(0.54), _in(0.56)])
    assert features["pivot_end"]["radius"] == pytest.approx([_in(0.48), _in(0.50)])
    assert features["flanks"]["angle_ref_deg"] == pytest.approx(2.4, abs=0.05)
    assert features["rear_face"]["thickness_stock"] == pytest.approx([_in(0.374), _in(0.376)])
    assert features["rear_face"]["callout"] == "3/8 (.3750) GROUND STOCK REF"
    pivot = features["pivot_bore"]
    assert pivot["dia"] == pytest.approx([_in(0.196), _in(0.200)])
    assert pivot["process"] == "drill" and pivot["thru"] is True and pivot["datum"] == "B"
    spot = features["spot_face"]
    assert spot["dia"] == pytest.approx([_in(0.49), _in(0.51)])
    # The native ±.002 qualifies the 6.9 model floor (.2717 printed).
    assert spot["floor"] == pytest.approx([6.9 - _in(0.002), 6.9 + _in(0.002)])
    assert spot["floor_from"] == "front_face"
    pin = features["pin_bore"]
    assert pin["dia"] == pytest.approx([_in(0.1260), _in(0.1265)])
    assert pin["station_basic"] == pytest.approx(_in(2.7093), abs=_in(0.00005))
    assert pin["position_dia_max"] == pytest.approx(_in(0.004))
    assert pin["perpendicularity_dia_max"] == pytest.approx(_in(0.001))
    assert features["pin_mouth"]["leg"] == pytest.approx([_in(0.006), _in(0.010)])
    latch = features["latch_pin_hole"]
    assert latch["dia"] == pytest.approx([_in(0.1240), _in(0.1245)])
    assert latch["depth"][0] == pytest.approx(_in(0.38)) and latch["depth_printed"] == "MIN"
    assert latch["height"] == pytest.approx([_in(0.18), _in(0.20)])
    dowels = features["dowel_holes"]
    assert dowels["dia"] == pytest.approx([_in(0.1240), _in(0.1245)])
    assert dowels["made_at"] == "assembly" and dowels["count"] == 2
    assert "process" not in dowels
    taps = features["plate_taps"]
    assert taps["thread"] == "#8-32 UNC-2B" and taps["made_at"] == "assembly"
    assert taps["dia"][0] == pytest.approx(_in(0.136), abs=1e-3)
    assert "process" not in taps
