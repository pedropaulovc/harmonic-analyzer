"""Offline contracts for the fulcrum shaft and its drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_ch_fulcrum_shaft as part
import ch_fulcrum_keeper_spec
import ch_fulcrum_shaft_spec
import draw_ch_fulcrum_shaft as drawing


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = ch_fulcrum_shaft_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == ch_fulcrum_shaft_spec.SHAFT_DIA


def test_every_marked_model_dimension_is_shown() -> None:
    marked = set().union(*ch_fulcrum_shaft_spec.DRAWING_DIMENSIONS.values())
    displayed = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert displayed == marked


def test_shaft_carries_no_frames_or_datums() -> None:
    # Policy rule 3: shafts carry no frames and no datums; the domed ends
    # leave no end face to square anyway.
    assert not hasattr(ch_fulcrum_shaft_spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(ch_fulcrum_shaft_spec, "PART_DATUMS")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi" not in source


def test_plain_shaft_domed_proud_of_each_keeper() -> None:
    spec = ch_fulcrum_shaft_spec
    keeper = ch_fulcrum_keeper_spec
    assert spec.SHAFT_DIA == keeper.BORE_DIA
    assert spec.CYLINDER_HALF == keeper.KEEPER_Z_OFF + keeper.LUG_HALF_T + 0.5
    assert spec.DOME_R == spec.SHAFT_DIA / 2.0
    assert math.isclose(spec.SHAFT_LENGTH, 161.35)


def test_flats_sit_under_the_keeper_taps() -> None:
    spec = ch_fulcrum_shaft_spec
    assert spec.FLAT_PITCH == 2.0 * ch_fulcrum_keeper_spec.KEEPER_Z_OFF
    assert spec.FLAT_DEPTH == 0.3
    assert math.isclose(spec.ACROSS_FLAT, 6.05)
    assert spec.FLAT_CHORD_MIN > spec.SET_SCREW_MAJOR_DIA


def test_flat_chord_guard_is_the_least_chord_over_printed_band_corners() -> None:
    # The print controls ShaftDia and AcrossFlat, never the depth, so the
    # shallowest flat comes from their band corners together.
    spec = ch_fulcrum_shaft_spec
    chords = []
    for dia_dev in spec.SHAFT_DIA_BAND:
        for af_dev in (-0.13, 0.13):
            r = (spec.SHAFT_DIA + dia_dev) / 2.0
            depth = 2.0 * r - (spec.ACROSS_FLAT + af_dev)
            chords.append(2.0 * math.sqrt(2.0 * r * depth - depth**2))
    assert math.isclose(spec.FLAT_CHORD_MIN, min(chords))
    assert min(chords) > spec.SET_SCREW_MAJOR_DIA


def test_flat_pair_is_located_from_the_end() -> None:
    # The print locates the -Z flat's outer edge off its dome tip and the +Z
    # flat by the like-edge pitch; both at .XXX keep one shaft station that
    # seats both cups, keeps each flat inside its lug and the cylinder past
    # both lug faces, at the worst case of every printed and fit-up band.
    spec = ch_fulcrum_shaft_spec
    assert math.isclose(spec.FLAT_FROM_END, 4.925)
    assert "FlatFromEnd" in spec.DRAWING_DIMENSIONS["FlatProfile"]
    assert "FlatFromEnd" in drawing.RIGHT_KEEP
    assert spec.DRAWING_PRECISION["FlatProfile"]["FlatFromEnd"] == 3
    assert spec.DRAWING_PRECISION["FlatProfile"]["FlatPitch"] == 3
    assert spec.FLAT_STATION_WINDOW_MM > 0.0
    assert round(spec.FLAT_STATION_WINDOW_MM, 3) == 0.14
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '\'"ShaftLength" / 2 - "FlatPitch" / 2 - "FlatLength" / 2\'' in source
    assert "FlatStation" not in source


def test_paired_keeper_bores_keep_a_running_fit_on_the_rail_seats() -> None:
    # Bored apart, the two keepers' .XX LugRise bands could put the bores
    # 1.02 out of line, far past the fit; reamed through in one pass at their
    # installed spacing they are one straight line, so a setup tilt of that
    # line costs nothing. GPT round 3 (PR #1311): the residual is the rail
    # under the two feet, faced in one setup on MHA-FR-002 to one 0.04 zone: a
    # step, opposite rolls across the 14 width (each lug centre 25.2 high) and
    # a pitch over the 16.5 seat; the shaft runs through both lug centres
    # 148 apart and each 6.0 lug spends its thickness x (pitch + slope).
    keeper = ch_fulcrum_keeper_spec
    spec = ch_fulcrum_shaft_spec
    assert math.isclose(spec.BORE_OFFSET_UNPAIRED_MM, 1.02)
    assert spec.BORE_OFFSET_UNPAIRED_MM > (
        keeper.BORE_DIA_BAND[0] - spec.SHAFT_DIA_BAND[1]
    )
    flatness = keeper.KEEPER_SEAT_FLATNESS_BUDGET_MM
    assert flatness == 0.04
    assert keeper.KEEPER_SEAT_LENGTH_MM == 16.5
    lug_t = 2.0 * keeper.LUG_HALF_T
    span = 2.0 * keeper.KEEPER_Z_OFF
    assert span == 148.0
    sideways = 2.0 * keeper.SHAFT_AXIS_H * flatness / keeper.KEEPER_WIDTH
    slope = math.hypot(flatness, sideways) / span
    pitch = flatness / keeper.KEEPER_SEAT_LENGTH_MM
    allowance = lug_t * (pitch + slope)
    assert math.isclose(keeper.BORE_SEAT_ALLOWANCE_MM, allowance)
    assert round(allowance, 4) == 0.0206
    least = keeper.BORE_DIA_BAND[1] - spec.SHAFT_DIA_BAND[0]
    assert least >= keeper.BORE_RUNNING_MIN_CLEARANCE_MM + allowance  # 0.035 >= 0.0306
    assert math.isclose(spec.PAIRED_MIN_CLEARANCE_MM, least - allowance)
    assert round(spec.PAIRED_MIN_CLEARANCE_MM, 4) == 0.0144
    assert spec.PAIRED_MIN_CLEARANCE_MM >= keeper.BORE_RUNNING_MIN_CLEARANCE_MM == 0.010


def test_the_pair_reamer_reaches_and_sizes_the_bores() -> None:
    # One pass through both lugs: a 12 in long-series 0.2514 chucking reamer,
    # made to order (Super Tool catalogue 2026 p.59, 9458EL: .2211-.2530,
    # 12 OAL, 1-1/2 flute, .2193 shank, NAS 897 Type C; p.42: +.0002/-.0000
    # in), gripped 1 in, carries its whole flute past the far lug's outer
    # face, 154.0 from the near one; the toleranced reamer lies in the band.
    keeper = ch_fulcrum_keeper_spec
    assert keeper.KEEPER_OUTER_FACE_SPAN_MM == 154.0
    assert keeper.PAIR_REAMER_OAL_IN == 12.0
    reach = (12.0 - 1.0 - 1.5) * 25.4
    assert math.isclose(keeper.PAIR_REAMER_REACH_MARGIN_MM, reach - 154.0)
    assert round(keeper.PAIR_REAMER_REACH_MARGIN_MM, 1) == 87.3
    # An 8 in OAL reamer would not carry the flute through.
    assert (8.0 - 1.0 - 1.5) * 25.4 < 154.0
    assert keeper.PAIR_REAMER_DIA_IN == 0.2514
    low, high = (
        (keeper.PAIR_REAMER_DIA_IN + plus) * 25.4 - keeper.BORE_DIA
        for plus in (0.0, 0.0002)
    )
    assert math.isclose(keeper.PAIR_REAMER_RANGE_MM[0], low)
    assert math.isclose(keeper.PAIR_REAMER_RANGE_MM[1], high)
    assert (round(low, 5), round(high, 5)) == (0.03556, 0.04064)
    assert keeper.BORE_DIA_BAND[1] <= low < high <= keeper.BORE_DIA_BAND[0]


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
    # One flat: a 0.3-deep segment of the Ø6.35 round, 3.5 long.
    assert math.isclose(part.V_FLAT, 1.905, abs_tol=0.001)


def test_precision_matches_the_marked_dimensions() -> None:
    spec = ch_fulcrum_shaft_spec
    assert spec.DRAWING_PRECISION["ShaftProfile"]["ShaftDia"] == 3
    assert spec.DRAWING_PRECISION["FlatProfile"]["AcrossFlat"] == 3
    assert len(spec.DRAWING_NOTES.splitlines()) <= 4


def test_interference_literals_track_the_set_screw_and_keeper() -> None:
    import _interference_contracts
    import vn_fulcrum_set_screw_spec as set_screw
    from _hole_spec import TAP_DRILL_MM

    assert _interference_contracts.FULCRUM_SET_SCREW_THREAD == (
        set_screw.MAJOR_DIA,
        TAP_DRILL_MM[set_screw.THREAD],
        set_screw.LENGTH,
    )
