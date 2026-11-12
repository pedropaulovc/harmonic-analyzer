"""Offline contracts for the fulcrum shaft and its drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_ch_fulcrum_shaft as part
import ch_fulcrum_keeper_spec
import ch_fulcrum_shaft_notes as notes
import ch_fulcrum_shaft_spec
import draw_ch_fulcrum_shaft as drawing


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = ch_fulcrum_shaft_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == ch_fulcrum_shaft_spec.SHAFT_DIA


def test_every_marked_model_dimension_is_shown() -> None:
    marked = set().union(*ch_fulcrum_shaft_spec.DRAWING_DIMENSIONS.values())
    displayed = set(drawing.RIGHT_KEEP)
    assert displayed == marked


def test_shaft_carries_no_frames_or_datums() -> None:
    # drawing-guidelines.md rule 5 (avoid excessive GD&T): shafts carry no frames and no datums; the domed ends
    # leave no end face to square anyway.
    assert not hasattr(ch_fulcrum_shaft_spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(ch_fulcrum_shaft_spec, "PART_DATUMS")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi" not in source


def test_plain_shaft_domed_proud_of_each_keeper() -> None:
    spec = ch_fulcrum_shaft_spec
    keeper = ch_fulcrum_keeper_spec
    # #2338: the keeper bore is a .2525 reamer's size over the .2500 shaft.
    assert spec.SHAFT_DIA + spec.SHAFT_DIA_BAND[0] < keeper.BORE_DIA + keeper.BORE_DIA_BAND[1]
    assert math.isclose(
        spec.CYLINDER_HALF, keeper.KEEPER_Z_OFF + keeper.LUG_HALF_T + 1.016
    )
    assert spec.DOME_R == spec.SHAFT_DIA / 2.0
    assert math.isclose(spec.SHAFT_LENGTH, 178.054)  # 7.01


def test_flats_sit_under_the_keeper_taps() -> None:
    spec = ch_fulcrum_shaft_spec
    assert spec.FLAT_PITCH == 2.0 * ch_fulcrum_keeper_spec.KEEPER_Z_OFF
    assert spec.FLAT_DEPTH == 0.3048
    assert math.isclose(spec.ACROSS_FLAT, 6.0452)  # .238
    assert spec.FLAT_CHORD_MIN > spec.SET_SCREW_MAJOR_DIA


def test_flat_chord_guard_is_the_least_chord_over_printed_band_corners() -> None:
    # The print controls ShaftDia and AcrossFlat, never the depth, so the
    # shallowest flat comes from their band corners together.
    spec = ch_fulcrum_shaft_spec
    chords = []
    for dia_dev in spec.SHAFT_DIA_BAND:
        for af_dev in (-0.127, 0.127):
            r = (spec.SHAFT_DIA + dia_dev) / 2.0
            depth = 2.0 * r - (spec.ACROSS_FLAT + af_dev)
            chords.append(2.0 * math.sqrt(2.0 * r * depth - depth**2))
    assert math.isclose(spec.FLAT_CHORD_MIN, min(chords))
    assert min(chords) > spec.SET_SCREW_MAJOR_DIA


def test_flat_pair_is_baselined_from_one_end() -> None:
    # Machinist review (baseline r1, rule 10): the stations were a chain
    # (tip -> 4.925 -> 148.000). Both now run from the -Z dome tip: the -Z
    # flat's outer edge and the +Z flat's inner edge, at .XX on the .01 grid
    # (owner ruling Q11-B's lug: the .17 flat), with the flat length and the
    # overall length at .XX; one shaft station still seats both cups, keeps
    # each flat inside its lug and the cylinder past both lug faces, at the
    # worst case of every printed and fit-up band.
    spec = ch_fulcrum_shaft_spec
    assert math.isclose(spec.FLAT_LENGTH, 4.318)
    assert math.isclose(spec.FLAT_FROM_END, 6.096)
    assert math.isclose(spec.FLAT_BASELINE, 167.64)
    assert {"FlatFromEnd", "FlatBaseline"} <= spec.DRAWING_DIMENSIONS["FlatProfile"]
    assert {"FlatFromEnd", "FlatBaseline"} <= set(drawing.RIGHT_KEEP)
    assert spec.DRAWING_PRECISION["ShaftProfile"]["OverallLength"] == 2
    assert spec.DRAWING_PRECISION["FlatProfile"]["FlatFromEnd"] == 2
    assert spec.DRAWING_PRECISION["FlatProfile"]["FlatBaseline"] == 2
    assert spec.DRAWING_PRECISION["FlatProfile"]["FlatLength"] == 2
    assert round(spec.FLAT_STATION_WINDOW_MM, 3) == 1.219
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '\'"ShaftLength" / 2 - "FlatPitch" / 2 - "FlatLength" / 2\'' in source
    assert '\'"ShaftLength" / 2 + "FlatPitch" / 2 - "FlatLength" / 2\'' in source
    assert 'dims.record("FlatPitch"' not in source


def _station_window(spec) -> float:
    return min(
        spec._worst(spec._sum((1, high), (-1, low)))
        for high in spec._T_HIGH.values()
        for low in spec._T_LOW.values()
    )


def test_the_flat_length_cannot_drop_a_place(monkeypatch) -> None:
    # Band sensitivity at unchanged nominals: the stations and the overall
    # length print .XX; loosening the flat length to .X closes the
    # flat-station window (drawing-guidelines.md rule 17).
    spec = ch_fulcrum_shaft_spec
    assert math.isclose(_station_window(spec), spec.FLAT_STATION_WINDOW_MM)
    for key in ("flat_from_end", "flat_baseline", "length"):
        assert spec._STATION_BANDS[key] == spec._BAND_BY_PLACES[2]
    with monkeypatch.context() as patch:
        for key in ("front_flat", "rear_flat"):
            patch.setitem(spec._STATION_BANDS, key, spec._BAND_BY_PLACES[1])
        assert round(_station_window(spec), 3) == -2.337


def test_both_flats_print_one_length_and_one_across_flat() -> None:
    # Machinist review r8 (blocker): the left flat had no length. The cut
    # sketch drives both flats from one FlatLength and one AcrossFlat, so
    # the part prefixes each "2X" and the drawing imports it.
    spec = ch_fulcrum_shaft_spec
    assert spec.DIMENSION_PREFIXES == {
        ("FlatProfile", "FlatLength"): "2X ",
        ("FlatProfile", "AcrossFlat"): "2X ",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'dims.record("FlatLengthB", \'"FlatLength"\')' in source
    assert "AcrossFlat dim sets both flats' height" in source
    assert (
        "set_dimension_prefix(adapter, feature_name, dimension_name, prefix)" in source
    )
    assert source.index("set_dimension_prefix(adapter") < source.index(
        "clear_dimensions_for_drawing(adapter)"
    )


def test_side_view_texts_stand_clear_of_extension_lines() -> None:
    # Machinist review (baseline r1): the 4.925 text was struck by the 148
    # pitch's extension line. ~2.1 mm a character; each station text stands
    # where no other dimension's extension line runs.
    keep = drawing.RIGHT_KEEP
    char = 0.0021
    left_tip, right_tip = drawing._LEFT_TIP_X, drawing._RIGHT_TIP_X
    from_end_x, _ = keep["FlatFromEnd"]
    # Outboard of the left tip, inside the left zone margin.
    assert from_end_x + len(".24") * char / 2.0 <= left_tip - 0.001
    assert from_end_x - len(".24") * char / 2.0 >= 0.0127 + 0.003
    # Left of the right flat's inner edge, whose extension line rises to the
    # baseline row; the right tip's only extension line rises past it.
    flat_x, flat_y = keep["FlatLength"]
    assert flat_x + len("2X .17") * char / 2.0 <= drawing._RIGHT_FLAT_INNER_X - 0.001
    rows = [keep[name][1] for name in ("FlatLength", "FlatBaseline", "OverallLength")]
    assert rows == sorted(rows) and flat_y == keep["FlatFromEnd"][1]
    # Machinist review r1: the across-flat value and callout sat between its
    # own extension lines, which struck them. They now hang below the shaft,
    # right of the dome tip. The block is left-aligned on the dimension line
    # and stays inside the border. The PR1709 PDF's parent-vendor identity
    # and shelf span ~45 mm: the older per-character estimate missed the
    # final "55" and shelf touching the border.
    across_x, across_y = keep["AcrossFlat"]
    widest = max(
        len(line) for line in notes.ACROSS_FLAT_CALLOUT.splitlines()
    )
    assert across_y + 0.004 <= drawing._SHAFT_BOTTOM_Y - 0.010
    assert across_x > right_tip + 0.005
    assert across_x + max(widest * 0.00235, 0.045) <= 0.4318 - 0.0127 - 0.003
    # Machinist review r1: the Ø callout block (hanging left of its line,
    # ~36 characters) printed over the dome radius, and its upper limit
    # (~7 mm over the anchor) inside the outline.
    dia_x, dia_y = keep["ShaftDia"]
    dia_widest = max(len(line) for line in drawing.SHAFT_DIA_CALLOUT_ROWS.splitlines())
    dome_x, _ = keep["DomeRadius"]
    assert dome_x + len("2X (SR.125)") * char / 2.0 + 0.005 <= dia_x - dia_widest * char
    assert dia_y + 0.007 + 0.003 <= drawing._SHAFT_BOTTOM_Y
    # The Ra symbol (~9 mm tall up from its anchor) stands on the upper
    # silhouette right of the Ø line, left of the across-flat callout, between
    # the shaft and the second row's dimension line (~3 mm under its text).
    finish_x, finish_y = drawing.FINISH_SYMBOL
    assert finish_x > dia_x + 0.005
    assert finish_x + 0.035 < across_x
    assert finish_y > drawing._SHAFT_TOP_Y + 0.004
    assert finish_y + 0.009 < keep["FlatBaseline"][1] - 0.003
    assert math.isclose(drawing.FINISH_EDGE[1], drawing._SHAFT_TOP_Y)
    # Machinist review r2: a row's last glyph meets the dimension's vertical
    # leader, and a trailing ';' touched it.
    for callout in (notes.SHAFT_DIA_CALLOUT, notes.ACROSS_FLAT_CALLOUT):
        assert all(line[-1].isalnum() for line in callout.splitlines())
    # Post-v46 review: the final E of the widest Ø row still met that line;
    # every printed row carries two trailing spaces of ink air.
    assert drawing.SHAFT_DIA_CALLOUT_ROWS.splitlines() == [
        f"{line}  " for line in notes.SHAFT_DIA_CALLOUT.splitlines()
    ]
    # #2108 review: the S of SETS met the across-flat block's vertical line
    # on its left; every row there leads with one space of ink air.
    assert drawing.ACROSS_FLAT_CALLOUT_ROWS.splitlines() == [
        f" {line}" for line in notes.ACROSS_FLAT_CALLOUT.splitlines()
    ]


def test_three_place_sizes_name_their_mates() -> None:
    # Rule 4: the shaft is the first-made part of the keeper fit, so its band
    # stays here and the callout names the bores by the standard fit and,
    # the SHAFT_H band being narrower than the turned-diameter row, its route
    # (fan-out F1: bought ground stock); the across-flat size sets the set
    # screw's engagement. Rule 7: one fit statement, two lines of words.
    assert notes.SHAFT_DIA_CALLOUT.splitlines() == [
        "SLIDING FIT IN MHA-CH-07 BORES",
        "1/4 GROUND STOCK OK",
    ]
    assert "MHA-CH-VN-55" in notes.ACROSS_FLAT_CALLOUT
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"ShaftDia": SHAFT_DIA_CALLOUT_ROWS' in source
    assert '"AcrossFlat": ACROSS_FLAT_CALLOUT_ROWS' in source
    # The sheet's drawing text lives off the spec the assembly imports.
    for name in ("SHAFT_DIA_CALLOUT", "ACROSS_FLAT_CALLOUT", "DRAWING_NOTES", "ISO_VIEW_NOTE"):
        assert not hasattr(ch_fulcrum_shaft_spec, name)


def test_dome_prints_as_a_spherical_reference() -> None:
    # Rule 7: the hemisphere is drawn and dimensioned, not a note.
    spec = ch_fulcrum_shaft_spec
    assert "HEMISPHERE" not in notes.DRAWING_NOTES
    assert "DomeRadius" in spec.DRAWING_DIMENSIONS["FlatProfile"]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'dims.record("DomeRadius", \'"ShaftDia" / 2\')' in source
    assert '"2X (S" + existing' in Path(drawing.__file__).read_text(encoding="utf-8")


def test_every_orthographic_view_is_at_sheet_scale() -> None:
    assert drawing.SHEET_SCALE == (3.0, 2.0)
    assert not hasattr(ch_fulcrum_shaft_spec, "END_VIEW_NOTE")
    assert notes.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert drawing.ISO_SCALE == (1, 1)


def test_keeper_bores_reamed_apart_still_pass_the_shaft() -> None:
    # #2338: each keeper is reamed alone, so the two bores stand up to both
    # .XX LugRise bands (.020) plus the rail seats' 0.04 zone apart in height
    # (a roll across the width only moves a lug sideways, which the fit-up
    # takes with the shaft through both); each seat may also pitch its zone
    # over its .65 length. The shaft runs through both lug centres 6.360
    # apart and each .32 lug spends its thickness x (pitch + slope); the
    # .2525 bore keeps the slip minimum after that.
    keeper = ch_fulcrum_keeper_spec
    spec = ch_fulcrum_shaft_spec
    flatness = keeper.KEEPER_SEAT_FLATNESS_BUDGET_MM
    assert flatness == 0.04
    assert math.isclose(keeper.KEEPER_SEAT_LENGTH_MM, 16.51)
    lug_t = 2.0 * keeper.LUG_HALF_T
    span = 2.0 * keeper.KEEPER_Z_OFF
    assert math.isclose(span, 161.544)
    slope = (2.0 * 0.254 + flatness) / span
    pitch = flatness / keeper.KEEPER_SEAT_LENGTH_MM
    allowance = lug_t * (pitch + slope)
    assert math.isclose(keeper.BORE_ALIGNMENT_ALLOWANCE_MM, allowance)
    assert round(allowance, 4) == 0.0473
    least = keeper.BORE_DIA + keeper.BORE_DIA_BAND[1] - spec.SHAFT_DIA - spec.SHAFT_DIA_BAND[0]
    assert round(least / 25.4, 4) == 0.0025
    assert math.isclose(spec.ALIGNED_MIN_CLEARANCE_MM, least - allowance)
    assert round(spec.ALIGNED_MIN_CLEARANCE_MM, 4) == 0.0162
    assert spec.ALIGNED_MIN_CLEARANCE_MM >= keeper.BORE_RUNNING_MIN_CLEARANCE_MM == 0.010
    # The owned .2510 reamer would not do it: its least clearance is under the
    # slip minimum plus the allowance.
    assert (0.2510 - 0.2500) * 25.4 < keeper.BORE_RUNNING_MIN_CLEARANCE_MM + allowance


def test_installed_set_screw_meets_rule_12() -> None:
    spec = ch_fulcrum_shaft_spec
    assert spec.SET_SCREW_ENGAGEMENT_D >= 1.5
    # Below the crown apex at nominal; at most 0.4 proud at the worst case.
    assert spec.SET_SCREW_PROUD_NOMINAL < 0.0
    assert spec.SET_SCREW_PROUD_WORST <= 0.4


def test_analytic_volumes() -> None:
    r = ch_fulcrum_shaft_spec.SHAFT_R
    length = ch_fulcrum_shaft_spec.SHAFT_LENGTH
    assert math.isclose(
        part.V_BODY, math.pi * r * r * (length - 2 * r) + 4 / 3 * math.pi * r**3
    )
    # One flat: a .012-deep segment of the Ø.250 round, .17 long.
    assert math.isclose(part.V_FLAT, 2.406, abs_tol=0.001)


def test_precision_matches_the_marked_dimensions() -> None:
    spec = ch_fulcrum_shaft_spec
    assert spec.DRAWING_PRECISION["ShaftProfile"]["ShaftDia"] == 4
    assert spec.DRAWING_PRECISION["FlatProfile"]["AcrossFlat"] == 3
    assert len(notes.DRAWING_NOTES.splitlines()) <= 4


def test_interference_literals_track_the_set_screw_and_keeper() -> None:
    import _ch_channel_interference
    import ch_vn_fulcrum_set_screw_spec as set_screw
    from _hole_spec import TAP_DRILL_MM

    assert _ch_channel_interference.FULCRUM_SET_SCREW_THREAD == (
        set_screw.MAJOR_DIA,
        TAP_DRILL_MM[set_screw.THREAD],
        set_screw.LENGTH,
    )
