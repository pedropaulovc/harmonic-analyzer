"""Offline contracts for the transgear pivot spacer (MHA-PD-20) and its drawing."""

from __future__ import annotations

import math
from pathlib import Path
import re

import pytest

import _config
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _layout_geometry import Box, estimate_text_box
from _surface_finish import MACHINED_UM
import build_pd_transgear_pivot_spacer as part
import draw_pd_transgear_pivot_spacer as drawing
import pd_transgear_pivot_spacer_spec as spec
import _mcmaster_90325a174 as screw


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-pivot-spacer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-pivot-spacer.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-transgear-pivot-spacer_drawing.png")
    row = DRAWINGS_BY_NAME["pd_transgear_pivot_spacer"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.PROFILE_KEEP)
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    # The length (on the .001 grid) holds its own band; the bore prints its
    # drill's size (.XXX) under the DRILLED HOLES row; the O.D., an outside
    # profile no stack reads, takes the loosest row (.XX).
    assert spec.DRAWING_PRECISION_BY_NAME == {"RingOd": 2, "BoreDia": 3, "RingLength": 3}


def test_the_length_carries_its_band_on_the_model_and_the_bore_none() -> None:
    """The length's band is a native model tolerance from the spec (policy
    drawing-simplicity-policy.md `How the repository implements the guidelines`): ±.001, the shop's row for a turned length.  The O.D. prints at .XX and the title block's row governs it;
    the bore is a #11 drill under the DRILLED HOLES row: restating either row
    on the dimension is what drawing-guidelines.md rule 2 (the title block is the general specification) forbids."""
    assert model_toleranced_dimensions(part) == {
        ("Ring", "RingLength"): "LENGTH_TOLERANCE",
    }
    row = printed_band_mm(3, unit=spec.UNIT)
    assert 0.0 < spec.LENGTH_TOLERANCE <= spec.LENGTH_BAND < row
    assert spec.LENGTH_TOLERANCE == pytest.approx(0.001 * 25.4)
    # The analysis band is what the drill cuts: never under size, up to the
    # DRILLED HOLES row's growth.
    drilled_growth = drilled_oversize_mm(unit=spec.UNIT)
    assert spec.BORE_DRILL == "#11" and spec.BORE_DIA == pytest.approx(0.191 * 25.4)
    assert spec.BORE_DIA_BAND == pytest.approx((drilled_growth, 0.0))
    assert (spec.BORE_DIA_MIN, spec.BORE_DIA_MAX) == pytest.approx((4.8514, 4.953))


def test_the_bore_is_a_bonded_slip_fit_on_the_shoulder_at_every_limit() -> None:
    """The ring is bonded flush on the MHA-PD-VN-57 shoulder (Ø4.7625 -0.0254/0)
    so screw and spacer seat on the bar as one body: the largest shoulder
    still slips into the smallest drilled hole, and the smallest in the
    largest stays inside LOCTITE 638's gap limit, the one the repo's other
    638 joints are held to (owner ruling 2026-11-24, fit audit question
    6)."""
    import cone_tip_cluster
    import dt_pinion_arbor_geometry
    import sm_gooseneck_spring_joint

    shoulder_min = screw.SHOULDER_DIA + screw.SHOULDER_DIA_LIMITS[0]
    shoulder_max = screw.SHOULDER_DIA + screw.SHOULDER_DIA_LIMITS[1]
    tightest = spec.BORE_DIA_MIN - shoulder_max
    loosest = spec.BORE_DIA_MAX - shoulder_min
    assert spec.BOND_GAP == pytest.approx((tightest, loosest))
    assert (tightest, loosest) == pytest.approx((0.0035 * 25.4, 0.0085 * 25.4), abs=1e-6)
    assert (
        spec.LOCTITE_638_GAP_MAX
        == sm_gooseneck_spring_joint.LOCTITE_638_GAP_MAX
        == dt_pinion_arbor_geometry.RETAINING_COMPOUND_MAX_GAP_MM
        == cone_tip_cluster.RETAINING_COMPOUND_MAX_GAP_MM
    )
    assert 0.0 < tightest < loosest <= spec.LOCTITE_638_GAP_MAX
    # The ring may cure off the screw's axis by half the widest gap.
    assert spec.SEAT_OFFSET_MAX == pytest.approx(loosest / 2.0)
    assert not hasattr(spec, "PRESS_INTERFERENCE")


def test_the_tightest_bond_gap_absorbs_the_drilled_bore_squareness() -> None:
    """Codjiflo r2 on #3487: the front face cures in one plane with the
    shoulder's end only if the ring can tilt on the shoulder, inside its
    tightest gap over its shortest land, as far as its bore is off square to
    that face.  The sheet holds the drilled bore at the title block's
    angular row alone, so the #11's tightest gap must let the ring lean the
    whole row: 1.14 degrees against 1 (delegated ruling 2026-11-24 (Main),
    D17: owner question Q7b; the #12 gave 0.49)."""
    tilt = math.degrees(math.atan(spec.BOND_GAP[0] / spec.BOND_LAND_MIN))
    assert spec.BOND_GAP_TILT_DEG == pytest.approx(tilt)
    assert tilt == pytest.approx(
        math.degrees(math.atan(0.0889 / (5.0 - 0.0254 - 2 * 0.254))), rel=1e-3
    )
    assert tilt == pytest.approx(1.14, abs=0.005)
    assert tilt >= angular_band_deg(unit=spec.UNIT) == 1.0


def test_wall_holds_the_target_at_the_full_worst_case() -> None:
    """Rule 17 with every allowance the shop sees: the O.D. at its .XX row's
    low limit, the bore at its largest drilled size offset from the O.D. by
    half the printed O.D. runout to A (which holds at every section, so it
    encloses the drill's run-off), and the title block's larger permitted
    break (radius or chamfer) on both rims of an end face."""
    row = printed_band_mm(2, unit=spec.UNIT)
    setback = max(edge_break_radius_mm(unit=spec.UNIT), edge_break_chamfer_mm(unit=spec.UNIT))
    assert spec.OD_BAND == pytest.approx(row)
    assert spec.EDGE_BREAK == pytest.approx(setback)
    # Runout's full indicator movement is twice the axes' offset.
    assert spec.OD_RUNOUT == pytest.approx(0.016 * 25.4)
    assert spec.BORE_ECCENTRICITY == pytest.approx(spec.OD_RUNOUT / 2.0)
    worst = (
        (spec.OD - row - spec.BORE_DIA_MAX) / 2.0
        - spec.OD_RUNOUT / 2.0
        - 2.0 * setback
    )
    assert spec.WALL_WORST == pytest.approx(worst) == pytest.approx(0.0895 * 25.4)
    assert spec.WALL_WORST >= spec.WALL_TARGET == WALL_TARGET_MM


def test_a_larger_permitted_radius_break_charges_the_wall(monkeypatch) -> None:
    """The wall charges whichever permitted break sets back further: an R.020
    break with the .010 chamfer kept leaves 2.2987 - 2 x 0.254 < 2.032, so
    the spec refuses rather than missing the radius."""
    import importlib.util

    real = _config.title_block

    def title_block(key, *, unit="mm"):
        row = real(key, unit=unit)
        return {**row, "radius_in": 0.020} if key == "edge_break" and unit == "in" else row

    monkeypatch.setattr(_config, "title_block", title_block)
    # Execute a private copy: reloading the shared module would rebind its
    # band tuples, and test_fit_bands matches consumers to bands by id().
    probe_spec = importlib.util.spec_from_file_location(
        "_pivot_spacer_spec_probe", spec.__file__
    )
    probe = importlib.util.module_from_spec(probe_spec)
    with pytest.raises(AssertionError, match=r"MHA-PD-20 wall 1\.765 < the 2\.032"):
        probe_spec.loader.exec_module(probe)
    assert spec.EDGE_BREAK == pytest.approx(0.254)


def test_the_sheet_states_no_shortfall_and_no_facing_step() -> None:
    """The wall holds the target, so no WALL MIN line; R9-6: fitted as made,
    never faced.  The sheet carries no general notes at all."""
    assert not hasattr(spec, "DRAWING_NOTES")
    assert not hasattr(spec, "WALL_NOTE")
    assert "Manufacturing Notes" not in part._SAVED_DRAWING_PROPERTIES


def test_the_arm_runs_on_the_rear_face_and_the_front_face_carries_no_symbol() -> None:
    """Rule 6: the arm swings on the shoulder against the rear face, which
    runs (Ra 1.6, labelled BEARING FACE).  The front face, clamped on the bar,
    and the bonded bore carry no symbol (machinist review
    20261124T013305458Z)."""
    controls = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(controls) == {"rear_face"} == set(drawing.FACE_FINISHES)
    rear = controls["rear_face"].face
    assert controls["rear_face"].roughness_um == MACHINED_UM
    assert controls["rear_face"].production_method == "BEARING FACE"
    # Part frame: axis +Z, the bar-side face at z 0, the arm-side face at
    # z LENGTH (the RearFace plane).
    assert (tuple(rear.normal), rear.offset_mm) == ((0.0, 0.0, 1.0), spec.LENGTH)


def test_face_symbols_attach_to_their_own_end_of_the_lathe_profile() -> None:
    """The profile turns *Top a quarter turn, so model +Z runs LEFT: the front
    (bar) face is the right end, the rear (arm) face the left end.  A pick on
    the other end would hang the symbol on the wrong face."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    centre_x = drawing.PROFILE_CENTER[0]

    def sheet_x(z_mm: float) -> float:
        return centre_x - (z_mm - spec.LENGTH / 2.0) * scale

    assert drawing.PROFILE_ANGLE == pytest.approx(-0.5 * 3.141592653589793)
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    for key, (pick, _symbol) in drawing.FACE_FINISHES.items():
        assert pick[0] == pytest.approx(sheet_x(faces[key].offset_mm))
        radius = abs(pick[1] - drawing.PROFILE_CENTER[1]) / scale
        assert spec.BORE_DIA / 2.0 < radius < spec.OD / 2.0
    # Third angle: the end view seen from the +Z (left) end sits left of the
    # profile, on its axis.
    assert drawing.END_CENTER[0] < drawing.PROFILE_CENTER[0]
    assert drawing.END_CENTER[1] == drawing.PROFILE_CENTER[1]


def test_no_frame_relates_the_faces_and_the_length_band_bounds_their_taper() -> None:
    """Rule 5 (machinist review 20261124T013305458Z): a plain spacer carries
    no face-to-face frame and no datum on a face.  Bonded with its front face
    and the shoulder's end down on a flat plate, the ring seats on the bar by
    its front face and the arm seats on the rear face, so the hanger tilts by
    the faces' taper over the smallest flat the arm seats on; with no frame
    that taper is the printed length's whole spread, high limit at one place
    of the rim and low limit opposite.  The bore (datum A) serves the O.D.'s
    runout alone."""
    assert spec.BORE_DATUM == "A" and not hasattr(spec, "SEAT_DATUM")
    assert spec.GEOMETRIC_TOLERANCES_IN == {"o.d. circular runout to bore": ".016"}
    assert spec.REAR_FACE_PARALLELISM == pytest.approx(2.0 * spec.LENGTH_TOLERANCE)
    assert spec.REAR_FACE_PARALLELISM == pytest.approx(0.002 * 25.4)
    # The arm seats on the face's flat inside the O.D. rim's break.
    assert spec.FACE_PARALLELISM_ZONE_DIA == pytest.approx(
        spec.OD - spec.OD_BAND - 2.0 * spec.EDGE_BREAK
    )
    assert spec.SEATED_FACE_TILT == pytest.approx(
        math.atan(spec.REAR_FACE_PARALLELISM / spec.FACE_PARALLELISM_ZONE_DIA)
    )
    for gone in ("REAR_FACE_FRAME", "FRONT_FACE_DATUM", "frame_position", "face_rim"):
        assert not hasattr(drawing, gone)


def test_the_looser_length_band_would_close_the_disc_to_platen_air() -> None:
    """The necessity answer the length's register entry gives: at the ±.002 the sheet carried
    under its parallelism frame, the taper alone (the band's spread over the
    seat flat, levered to the disc's rim) takes the MHA-PD-06 disc's
    statistical air to the MHA-PD-02 platen under its floor; at ±.001 the
    stack holds it."""
    import build_pd_paper_drive_assembly as assembly
    from _printed_tolerance import printed_deviations

    air = assembly.PLATEN_AIR
    length, taper = "MHA-PD-20 spacer length", "MHA-PD-20 spacer rear face parallelism"
    assert air.terms[length] == spec.LENGTH_BAND
    assert air.statistical_mm >= air.minimum_mm
    # The old ±.002 through the spec's own rules: the printed length's reach,
    # and the taper as the band's whole spread (it scales with the band).
    old = 2.0 * spec.LENGTH_TOLERANCE
    old_band = max(
        abs(deviation)
        for deviation in printed_deviations(
            spec.LENGTH, spec.LENGTH_PLACES, (-old, old), unit=spec.UNIT
        )
    )
    looser = dict(air.terms)
    looser[length] = old_band
    looser[taper] = air.terms[taper] * 2.0 * old / spec.REAR_FACE_PARALLELISM
    closed = type(air)(air.name, air.nominal_mm, looser, air.minimum_mm)
    assert closed.statistical_mm < air.minimum_mm
    # Only the spacer's two terms grow: the air drops by their share of the RSS.
    rest = air.tolerance_rss_mm**2 - air.terms[length] ** 2 - air.terms[taper] ** 2
    growth = math.sqrt(rest + old_band**2 + looser[taper] ** 2) - air.tolerance_rss_mm
    assert closed.statistical_mm == pytest.approx(air.statistical_mm - growth)


_S = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
# A finish symbol's ink from its insertion point at 2.5 mm text, measured on
# the feed pinion's run 20261001T110844152Z: left of the root by 2.1, right to
# the "Ra" text's corner at 14.7, up 7.2.
_FINISH_INK = (-0.0021, 0.0, 0.0147, 0.0072)
# Dimension text as the fleet's sheets print it (test_arbor_pedestal_drawing).
_CAP_M = 0.0035
_ADVANCE = 109.7 / (42 * 3.5)
_AIR = 0.002


def _sheet_point(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, z) on the profile: *Top turned a quarter
    turn clockwise, so model +Z runs left and model +X down."""
    return (
        drawing.PROFILE_CENTER[0] - (z_mm - spec.LENGTH / 2.0) * _S,
        drawing.PROFILE_CENTER[1] - x_mm * _S,
    )


def _text_box(text: str, anchor: tuple[float, float], reference: int) -> Box:
    box = estimate_text_box(
        text, anchor=anchor, height=_CAP_M, reference=reference, advance_ratio=_ADVANCE
    )
    assert box is not None
    return box


# A dimension's text block with its callout rows, as farm run
# 20261027T121009040Z-eda67c82 printed them (layout-audit text runs): the
# block centres near the annotation position SetPosition2 takes (the
# length's rows on 0.2445, 0.1205 against its 0.2445, 0.1215; the bore's on
# 0.0500, 0.2215 against 0.050, 0.222), so each box grows by 1.5 of anchor
# slip; its rows stand 5.55 apart at 3.5 text, and the widest row's advance
# reaches 0.80 of the cap height ("MHA-PD-VN-57 SHOULDER" ran 58.6 wide).
# The bore's stacked +0.008 is one more row on top.
_ROW_PITCH = 0.00555 / _CAP_M
_CALLOUT_ADVANCE = 0.80
_ANCHOR_SLIP = 0.0015


def _callout_block(text: str, anchor: tuple[float, float]) -> Box:
    box = estimate_text_box(
        text,
        anchor=anchor,
        height=_CAP_M,
        reference=2,
        advance_ratio=_CALLOUT_ADVANCE,
        line_spacing=_ROW_PITCH,
    )
    assert box is not None
    return Box(
        box.xmin - _ANCHOR_SLIP,
        box.ymin - _ANCHOR_SLIP,
        box.xmax + _ANCHOR_SLIP,
        box.ymax + _ANCHOR_SLIP,
    )


def _length_text_box() -> Box:
    return _callout_block(
        f"{spec.LENGTH:.3f} ±{spec.LENGTH_BAND:.2f}",
        drawing.LENGTH_TEXT_XY,
    )


def _bore_text_box() -> Box:
    return _callout_block(
        f"\u00d8{spec.BORE_DIA:.3f}\n"
        f"{drawing.DIMENSION_CALLOUTS['BoreDia']}",
        drawing.END_KEEP["BoreDia"],
    )


def test_the_runout_frame_stands_inside_the_sheet_clear_of_every_annotation() -> None:
    """The O.D.'s runout frame and its leader keep 2 mm of air from every
    other annotation's box and line on the sheet (the dimensions' text and
    extension lines, the rear face's finish, the notes, the axis centreline
    and both views), and stand inside the inner border, off the title
    block."""
    s = _S
    centre_x, axis_y = drawing.PROFILE_CENTER
    rear_x, front_x = _sheet_point(0.0, spec.LENGTH)[0], _sheet_point(0.0, 0.0)[0]
    top, bottom = axis_y + spec.OD / 2.0 * s, axis_y - spec.OD / 2.0 * s
    length_y = drawing.PROFILE_KEEP["RingLength"][1]
    od_x = drawing.OD_ON_PROFILE[0]
    end_r = spec.OD / 2.0 * s
    obstacles = {
        "profile": Box(rear_x, bottom, front_x, top),
        "end view": Box(
            drawing.END_CENTER[0] - end_r,
            drawing.END_CENTER[1] - end_r,
            drawing.END_CENTER[0] + end_r,
            drawing.END_CENTER[1] + end_r,
        ),
        "length text": _length_text_box(),
        "length dimension line": Box(rear_x, length_y, drawing.LENGTH_TEXT_XY[0], length_y),
        "O.D. text": _text_box(
            f"\u00d8{spec.OD:.{spec.OD_PLACES}f}", drawing.OD_ON_PROFILE, 2
        ),
        "bore text": _bore_text_box(),
        "isometric note": _text_box(spec.ISOMETRIC_VIEW_NOTE, drawing.ISO_NOTE_XY, 0),
        # Lines: the axis centreline, the length's extension lines down from
        # the part's lower corners, the O.D.'s out from its two corners.
        "centreline": Box(drawing.END_CENTER[0], axis_y, od_x, axis_y),
        "length rear extension": Box(rear_x, length_y, rear_x, bottom),
        "length front extension": Box(front_x, length_y, front_x, bottom),
        "O.D. upper extension": Box(front_x, top, od_x, top),
        "O.D. lower extension": Box(front_x, bottom, od_x, bottom),
        "O.D. dimension line": Box(od_x, bottom, od_x, top),
    }
    dx0, dy0, dx1, dy1 = _FINISH_INK
    for key, (pick, (sx, sy)) in drawing.FACE_FINISHES.items():
        obstacles[f"{key} finish"] = Box(sx + dx0, sy + dy0, sx + dx1, sy + dy1)
        obstacles[f"{key} finish leader"] = Box(
            min(pick[0], sx), min(pick[1], sy), max(pick[0], sx), max(pick[1], sy)
        )
    symbols: dict[str, Box] = {}
    # The O.D.'s runout frame above the profile, its leader down to the upper
    # O.D. line (the leader leaves the frame's left side at mid-height).
    rx, ry = drawing.OD_RUNOUT_FRAME
    runout = Box(rx, ry - drawing.FRAME_HEIGHT, rx + drawing.FRAME_WIDTH, ry)
    landing_x = drawing._profile_x(drawing.OD_RUNOUT_LANDING_Z_MM)
    assert rear_x < landing_x < front_x
    symbols["runout frame"] = runout
    symbols["runout frame leader"] = Box(
        min(rx, landing_x), top, max(rx, landing_x), ry - drawing.FRAME_HEIGHT / 2.0
    )
    for name, box in symbols.items():
        for other, obstacle in obstacles.items():
            if name.endswith("leader") and other == "profile":
                continue  # a leader ends on the part's face
            assert box.gap(obstacle) >= _AIR, (name, other)
    for name, box in symbols.items():
        for other, neighbour in symbols.items():
            if name.split()[0] != other.split()[0]:
                assert box.gap(neighbour) >= _AIR, (name, other)
    template = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
    margin = 0.0127
    left, right = margin + _AIR, template.width_m - margin - _AIR
    bottom_edge, top_edge = margin + _AIR, template.height_m - margin - _AIR
    title_block = Box(
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )
    for key, box in (("runout", runout),):
        assert left <= box.xmin and box.xmax <= right, key
        assert bottom_edge <= box.ymin and box.ymax <= top_edge, key
        assert box.gap(title_block) >= _AIR, key


def test_turned_part_diameters_follow_the_machinist() -> None:
    # drawing-guidelines.md rule 11 (turned parts read like the lathe): the O.D. is moved onto the lathe profile; the bore, a solid
    # circle only end-on, keeps the end view.
    assert set(drawing.PROFILE_KEEP) == {"RingLength"}
    assert set(drawing.END_KEEP) == {"BoreDia", "RingOd"}
    profile_right = drawing.PROFILE_CENTER[0] + spec.LENGTH * drawing._S / 2.0
    assert drawing.OD_ON_PROFILE[0] > profile_right
    assert drawing.OD_ON_PROFILE[1] == drawing.PROFILE_CENTER[1]
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE {}:{}".format(
        *spec.ISOMETRIC_VIEW_SCALE
    )


def test_the_bore_callout_names_the_drill_and_the_bonded_seat() -> None:
    """The bore is a bonded slip fit on the MHA-PD-VN-57 shoulder: a named
    drill at the DRILLED HOLES row (drawing-guidelines.md rule 4, form 1; rule 12 (hole and slot callouts say what to do)), no REAM and no band; its callout
    rides the end-view diameter, the hole's defining view, names the bonded
    seat on the screw, and gives the clearance both limits produce (rule
    23), in two lines of words (rule 7)."""
    assert set(drawing.DIMENSION_CALLOUTS) == {"BoreDia"}
    assert "BoreDia" in drawing.END_KEEP and "RingLength" in drawing.PROFILE_KEEP
    text = drawing.DIMENSION_CALLOUTS["BoreDia"]
    rows = text.split("\n")
    assert rows[0] == "#11 DRILL THRU" and len(rows) == 3
    screw = _config.parts("pd-vn-transgear-pivot-screw")["number"]
    assert rows[1] == f"BONDED FIT ON {screw}"
    assert "REAM" not in text and "PRESS" not in text and "DIAMETRAL" not in text
    # The printed window encloses the spec's gap at both limits and is at
    # least .001 wide (rule 4: no fit range narrower).
    (window,) = re.findall(r"^\(CLEARANCE (\d*\.\d+)-(\d*\.\d+)\)$", rows[2])
    low, high = (float(v) * 25.4 for v in window)
    assert 0.0 < low <= spec.BOND_GAP[0] < spec.BOND_GAP[1] <= high
    assert high - spec.BOND_GAP[1] < 0.00254
    assert spec.BOND_GAP[0] - low < 0.00254
    assert high - low >= 0.001 * 25.4


def test_the_length_band_answers_necessity_in_the_register_not_on_the_sheet() -> None:
    """Rule 4 (owner ruling 2026-11-24: "In the part's registry file, not on
    the sheet."): the ±.001 length prints no reason; the package's necessity
    register carries its one entry, a gap."""
    import machinist_necessity

    assert "RingLength" not in drawing.DIMENSION_CALLOUTS
    (entry,) = machinist_necessity.load_necessity(
        Path(_config.__file__).resolve().parents[1] / "config",
        "pd_transgear_pivot_spacer",
    )
    assert entry.kind == "gap"
    assert "±.001" in entry.feature


# The rows run 20261027T121009040Z-eda67c82 printed (layout audit: each
# row's lower-left anchor, plus its width and the 3.5 cap), with the text
# and SetPosition2 anchor that produced them.
_PRINTED_BLOCKS = (
    (
        "5.000 ±0.05\nSETS MHA-PD-VN-63\nSPRING ROOM",
        (0.2445, 0.1215),
        (0.2224, 0.1132, 0.2665, 0.1278),
    ),
    (
        "+0.008\nØ4.727 0.000\nREAM THRU\n0.002-0.036 DIAMETRAL\n"
        "INTERFERENCE ON\nMHA-PD-VN-57 SHOULDER",
        (0.050, 0.222),
        (0.0207, 0.2064, 0.0793, 0.2366),
    ),
)


def test_callout_block_model_encloses_the_rows_the_farm_printed() -> None:
    """The calibration behind _callout_block, on the text and anchors the
    farm printed, independent of where the sheet places them now."""
    for text, anchor, (xmin, ymin, xmax, ymax) in _PRINTED_BLOCKS:
        box = _callout_block(text, anchor)
        assert box.xmin <= xmin and xmax <= box.xmax
        assert box.ymin <= ymin and ymax <= box.ymax


def test_offset_length_text_clears_every_extension_line() -> None:
    """Review 2026-10-23 (clarity): the length's text filled the 25 between
    its extension lines.  Offset right of the front face's extension line, it
    keeps 2 mm of air from both length extension lines and the O.D.'s lower
    extension line and dimension line."""
    rear_x, front_x = _sheet_point(0.0, spec.LENGTH)[0], _sheet_point(0.0, 0.0)[0]
    bottom = drawing.PROFILE_CENTER[1] - spec.OD / 2.0 * _S
    top = drawing.PROFILE_CENTER[1] + spec.OD / 2.0 * _S
    length_y = drawing.PROFILE_KEEP["RingLength"][1]
    od_x = drawing.OD_ON_PROFILE[0]
    text = _length_text_box()
    for name, line in {
        "rear extension": Box(rear_x, length_y, rear_x, bottom),
        "front extension": Box(front_x, length_y, front_x, bottom),
        "O.D. lower extension": Box(front_x, bottom, od_x, bottom),
        "O.D. dimension line": Box(od_x, bottom, od_x, top),
    }.items():
        assert text.gap(line) >= _AIR, name
    assert text.xmin > front_x


def test_bore_callout_clears_the_end_view() -> None:
    end_r = spec.OD / 2.0 * _S
    circle = Box(
        drawing.END_CENTER[0] - end_r,
        drawing.END_CENTER[1] - end_r,
        drawing.END_CENTER[0] + end_r,
        drawing.END_CENTER[1] + end_r,
    )
    assert _bore_text_box().gap(circle) >= _AIR


# Datum tag box as run 20261027T131303762Z-7567dd7c printed it: 3.2 x 3.4 of
# text in a ~7 mm square frame.
_DATUM_TAG = 0.007


def test_datum_a_tag_stands_off_the_od_and_the_bore_callout() -> None:
    """The native drop put datum A's tag on the Ø11.0 outline (text-on-line).
    The placed tag stands outside the O.D. circle with air, whichever corner
    of the tag SolidWorks anchors at the requested point, and clear of the
    bore callout and the vertical centreline."""
    cx, cy = drawing.END_CENTER
    od_r = spec.OD / 2.0 * _S
    x, y = drawing.DATUM_A_SYMBOL
    for dx in (-_DATUM_TAG, 0.0):
        for dy in (-_DATUM_TAG, 0.0):
            tag = Box(x + dx, y + dy, x + dx + _DATUM_TAG, y + dy + _DATUM_TAG)
            nearest = (
                min(max(cx, tag.xmin), tag.xmax),
                min(max(cy, tag.ymin), tag.ymax),
            )
            assert math.dist(nearest, (cx, cy)) >= od_r + _AIR
            assert tag.gap(_bore_text_box()) >= _AIR
            assert tag.xmax <= cx - _AIR


def test_registry_row_is_the_turned_brass_mha_167() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-20"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"
    assert "fit_class" not in row
