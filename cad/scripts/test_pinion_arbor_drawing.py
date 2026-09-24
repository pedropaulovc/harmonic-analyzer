"""Behavioral release contracts for the integral MHA-102 pinion arbor."""

from __future__ import annotations

from pathlib import Path

import pytest

import _drawing_marks
import _fit_limits
import build_pinion_arbor as part
import draw_pinion_arbor as drawing
import pinion_arbor_spec as spec
import pinion_handle_geometry as rod_geometry
import pinion_handle_spec as crossrod
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-arbor.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-arbor.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-arbor_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_arbor"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_every_printed_dimension() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.DONOR_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert not hasattr(spec, "DRAWING_REFERENCE_PRECISION")
    assert {"HeadDia", "NeckDia", "ShaftDia"} == set(drawing.DONOR_KEEP)
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_integral_arbor_keeps_the_released_stations_around_a_longer_head() -> None:
    # Rule 12 (audit W6): the head grows 9.0 -> 10.5 about the released
    # crossrod station; the neck shoulder, shaft and back crown stay put.
    assert spec.HEAD_CENTER_Z == pytest.approx(-6.5)
    assert spec.HEAD_FRONT_Z == pytest.approx(-11.75)
    assert spec.HEAD_REAR_Z == pytest.approx(-1.25)
    assert spec.NECK_END_Z == pytest.approx(10.0)
    assert spec.SHAFT_LEN == pytest.approx(226.25)
    assert spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG == pytest.approx(-14.75)
    assert spec.SHAFT_LEN + spec.BACK_CAP_SAG == pytest.approx(227.45)
    assert spec.OVERALL_LEN == pytest.approx(242.2)
    assert spec.EXPOSED_SHAFT_LEN == pytest.approx(216.25)
    assert spec.BACK_RIM_FROM_HEAD_REAR == pytest.approx(227.5)


def test_crossrod_hole_is_centred_with_a_rule_12_web() -> None:
    # Printed centred on the head length: only HeadLen's .X band reaches the
    # web, never a separate station band.
    assert "CrossHoleReference" not in spec.DRAWING_DIMENSIONS
    assert "CENTRED ON HEAD LENGTH" in spec.CROSS_HOLE_CALLOUT
    assert spec.CROSS_HOLE_WEB_WORST == pytest.approx(1.80)
    assert spec.CROSS_HOLE_WEB_WORST >= 1.5


def test_integral_head_owns_the_crossrod_interface() -> None:
    assert spec.HEAD_DIA == pytest.approx(15.0)
    assert spec.HEAD_LEN == pytest.approx(10.5)
    assert spec.NECK_DIA == pytest.approx(10.5)
    assert spec.NECK_LEN == pytest.approx(11.25)
    callout = drawing.DIMENSION_CALLOUTS["CrossHoleDia"]
    assert callout is spec.CROSS_HOLE_CALLOUT
    assert callout == "REAM THRU,\nCENTRED ON HEAD LENGTH"
    # Fable r-delta (Main ruling B): MHA-058's bond and acceptance are
    # instructions for a part not on this print; MHA-058 carries both.
    assert "MHA-058" not in spec.DRAWING_NOTES
    assert "SHALL NOT TURN OR SLIDE BY HAND" in crossrod.DRAWING_NOTES


def test_crossrod_is_a_bonded_slip_fit_not_a_press() -> None:
    """R1 (U27 precedent): a novice's stock reamer and as-received bar give
    clearance, so the hole is banded Ø6.00 +0.10/0 and the rod is bonded."""
    assert spec.CROSS_HOLE_DIA == pytest.approx(6.0)
    assert spec.CROSS_HOLE_DIA_BAND == (0.10, 0.0)
    assert crossrod.ROD_DIA == pytest.approx(spec.CROSS_HOLE_DIA)  # line to line
    assert (
        model_toleranced_dimensions(part)[("CrossHoleProfile", "CrossHoleDia")]
        == "*deviations(CROSS_HOLE_DIA_BAND)"
    )
    assert spec.DRAWING_PRECISION_BY_NAME["CrossHoleDia"] == 2
    tightest = (spec.CROSS_HOLE_DIA + spec.CROSS_HOLE_DIA_BAND[1]) - (
        crossrod.ROD_DIA + rod_geometry.ROD_DIA_BAND[0]
    )
    loosest = (spec.CROSS_HOLE_DIA + spec.CROSS_HOLE_DIA_BAND[0]) - (
        crossrod.ROD_DIA + rod_geometry.ROD_DIA_BAND[1]
    )
    assert spec.CROSSROD_MIN_CLEARANCE == pytest.approx(tightest)
    assert spec.CROSSROD_MAX_CLEARANCE == pytest.approx(loosest)
    assert tightest >= 0.0
    assert loosest <= spec.RETAINING_COMPOUND_MAX_GAP_MM
    assert "BOND INTO MHA-102 HEAD WITH LOCTITE 638." in crossrod.DRAWING_NOTES
    for retired in ("MATCH-REAM", "PRESS", "INTERNAL SHOULDERS SHARP"):
        assert retired not in spec.DRAWING_NOTES
        assert retired not in spec.CROSS_HOLE_CALLOUT


def test_only_the_two_journal_lands_carry_the_running_band_and_finish() -> None:
    assert spec.JOURNAL_DIA_BAND == (-0.01, -0.03)
    # Both stacked bands print at 2 places: "-0.01/-0.03" and "-0.01/-0.10".
    for band in (spec.JOURNAL_DIA_BAND, spec.SHAFT_DIA_BAND):
        assert _drawing_marks._tolerance_precision_mm(*_fit_limits.deviations(band)) == 2
    assert _fit_limits.band_text(spec.JOURNAL_DIA_BAND) == "-0.01/-0.03"
    assert spec.SHAFT_DIA_BAND == (-0.01, -0.10)
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("CrossHoleProfile", "CrossHoleDia"): "*deviations(CROSS_HOLE_DIA_BAND)",
        ("FrontJournalReference", "FrontJournalDia"): "*deviations(JOURNAL_DIA_BAND)",
        ("BackJournalReference", "BackJournalDia"): "*deviations(JOURNAL_DIA_BAND)",
    }
    lands = {
        "front_journal": spec.FRONT_JOURNAL_Z,
        "back_journal": spec.BACK_JOURNAL_Z,
    }
    assert {finish.key for finish in spec.SURFACE_FINISHES} == set(lands)
    for finish in spec.SURFACE_FINISHES:
        assert finish.roughness_um == 1.6
        assert finish.face.diameter_mm == spec.SHAFT_DIA
        station = lands[finish.key]
        assert station < finish.face.contains_z_mm < station + spec.JOURNAL_LEN
    assert set(drawing.JOURNAL_FINISHES) == set(lands)
    for key, (station_z, _symbol_xy) in drawing.JOURNAL_FINISHES.items():
        assert lands[key] < station_z < lands[key] + spec.JOURNAL_LEN
    assert "MHA-056" in spec.DRAWING_NOTES
    assert "PRESSES INTO" not in spec.DRAWING_NOTES
    assert not hasattr(spec, "PART_DATUMS")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")


def test_each_journal_land_covers_its_strap_with_axial_margin() -> None:
    """The lands must cover the MHA-056 straps where the assembly puts them."""
    import build_drive_train_assembly as assembly

    front_face = assembly.APINION_Z_FRONT - assembly.STRAP_AIR - assembly.ARBOR_Z0
    back_face = assembly.APINION_Z_BACK + assembly.STRAP_AIR - assembly.ARBOR_Z0
    # 9 mm is the thicker strap the pinion-cluster slice carries.
    for strap_t in {assembly.STRAP_T, 9.0}:
        for strap_lo, strap_hi, land_lo in (
            (front_face - strap_t, front_face, spec.FRONT_JOURNAL_Z),
            (back_face, back_face + strap_t, spec.BACK_JOURNAL_Z),
        ):
            assert strap_lo - land_lo >= 1.0
            assert land_lo + spec.JOURNAL_LEN - strap_hi >= 1.0


def test_journal_and_bond_zone_bands_leave_the_intended_fits() -> None:
    import alignment_pinion_spec as drum
    import pinion_bracket_spec as strap

    journal_upper, journal_lower = spec.JOURNAL_DIA_BAND
    strap_upper, strap_lower = strap.ARBOR_BORE_BAND
    # Running fit of each land in its MHA-056 REAM_SLIDE bore.
    assert strap.ARBOR_BORE_BAND is _fit_limits.REAM_SLIDE
    assert strap_lower - journal_upper == pytest.approx(0.020)
    assert strap_upper - journal_lower == pytest.approx(0.055)
    # Every bore slides on from the back crown, so no zone may exceed 8.00.
    # The drum keeps its stock-H7 bore, so the bond zone sits 0.01 under it
    # for a guaranteed slide, and the worst gap stays inside Loctite 638's 0.25.
    shaft_upper, shaft_lower = spec.SHAFT_DIA_BAND
    assert shaft_upper == pytest.approx(-0.010)
    drum_upper, drum_lower = drum.ARBOR_BORE_BAND
    assert drum_lower - shaft_upper == pytest.approx(0.010)
    assert drum_upper - shaft_lower <= 0.20 + 1e-9
    # The drum passes over the back land on its way on, so "SLIDES BY HAND"
    # must hold there too: every Ø8 zone it crosses stays 0.010 under its bore.
    assert drum_lower - journal_upper == pytest.approx(0.010)
    assert min(drum_lower - journal_upper, drum_lower - shaft_upper) >= 0.010 - 1e-9


def test_retired_socket_and_retention_pin_are_not_exported() -> None:
    retired = {
        "RETENTION_HOLE_DIA",
        "RETENTION_PIN_STATION",
        "TUBE_ID",
        "TUBE_OD",
        "TUBE_LEN",
        "WALL_T",
    }
    assert retired.isdisjoint(vars(spec))
    assert "RETENTION PIN" not in spec.CROSS_HOLE_CALLOUT


def test_every_post_import_name_is_carried_by_a_kept_or_moved_dimension() -> None:
    """Offline audit of the names the sheet looks up after the model import."""
    carried = (
        set(drawing.DONOR_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= carried
    assert set(spec.DRAWING_PRECISION_BY_NAME) == carried
    assert set(drawing.DIAMETER_POSITIONS) <= carried
    assert {"CrossHoleDia", "HeadCapSagDim", "BackCapSagDim", "OverallLen"} <= carried


def test_back_crown_radius_is_the_model_dimension_not_typed_text() -> None:
    assert spec.DRAWING_DIMENSIONS["BackCapProfile"] == {"BackCapR", "BackCapSagDim"}
    assert spec.DRAWING_PRECISION_BY_NAME["BackCapR"] == 1
    assert "BackCapR" in drawing.PRINCIPAL_KEEP
    assert drawing.DIMENSION_CALLOUTS["BackCapSagDim"] == "BACK CROWN"
    assert not any("SR" in text for text in drawing.DIMENSION_CALLOUTS.values())


def test_every_printed_length_is_exact_at_its_authored_places() -> None:
    """A one-place print of 11.25 reads 11.3: the sheet would not state the model."""
    nominal = {
        "HeadLen": spec.HEAD_LEN,
        "NeckLen": spec.NECK_LEN,
        "BackRimFromHeadRear": spec.BACK_RIM_FROM_HEAD_REAR,
        "OverallLen": spec.OVERALL_LEN,
        "FrontJournalFromHeadRear": spec.FRONT_JOURNAL_FROM_HEAD_REAR,
        "BackJournalFromHeadRear": spec.BACK_JOURNAL_FROM_HEAD_REAR,
        "FrontJournalLen": spec.JOURNAL_LEN,
        "BackJournalLen": spec.JOURNAL_LEN,
    }
    for name, value in nominal.items():
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        assert value == pytest.approx(round(value, places), abs=1e-9), name


def test_back_journal_text_sits_head_side_clear_of_the_crown_witnesses() -> None:
    """The back-crown/overall witnesses (sheet x 0.079-0.081) ran through the
    back journal's "8.00" and "JOURNAL" (Main, 30620a85): its text now sits on
    the head side, right of its Ra symbol and short of the bond-zone text."""
    text_x, text_y = drawing.PRINCIPAL_KEEP["BackJournalDia"]
    _station_z, (symbol_x, symbol_y) = drawing.JOURNAL_FINISHES["back_journal"]
    assert text_x > symbol_x + 0.015  # past the Ra symbol's ~17 mm width
    assert text_y < symbol_y  # its shelf runs under the symbol
    assert text_x + 0.030 < drawing.DIAMETER_POSITIONS["ShaftDia"][0] - 0.020


def test_detail_fence_audit_allows_only_the_downward_station_witnesses() -> None:
    from _layout_geometry import AnnotationGeometry, Segment

    center, radius = (0.3132, 0.171), 0.015

    def dim(*segments: Segment) -> AnnotationGeometry:
        return AnnotationGeometry(label="d", kind="dim", owner="p", segments=segments)

    station = Segment(0.308, 0.165, 0.308, 0.100)  # drops to the stack below
    inside = Segment(0.3190, 0.1785, 0.3250, 0.1785)  # Ø15 witness, in the fence
    leader = Segment(0.3238, 0.165, 0.3238, 0.192, "leader")  # own line to text
    drawing._assert_witnesses_clear_of_detail_fence(
        [dim(station, inside, leader)], center=center, radius=radius
    )
    outward = Segment(0.3190, 0.1785, 0.3420, 0.1785)  # the old Ø15 witness
    with pytest.raises(RuntimeError, match="detail-A fence"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [dim(outward)], center=center, radius=radius
        )
    upward = Segment(0.308, 0.175, 0.308, 0.200)
    with pytest.raises(RuntimeError, match="detail-A fence"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [dim(upward)], center=center, radius=radius
        )


def test_head_diameter_line_stands_between_crown_apex_and_fence() -> None:
    x = drawing.DIAMETER_POSITIONS["HeadDia"][0]
    to_x = lambda z: drawing.PRINCIPAL_CENTER[0] - (z - 106.725) / 1000.0  # noqa: E731
    apex = to_x(spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG)
    center = to_x(spec.HEAD_CENTER_Z)
    half = spec.HEAD_DIA / 2000.0
    fence = center + (drawing.DETAIL_RADIUS_MM**2 / 1e6 - half**2) ** 0.5
    assert apex + 0.0015 < x < fence - 0.0020


def test_layout_audit_gates_text_on_line_and_logs_the_rest() -> None:
    from _layout_geometry import Finding

    advisory = Finding(kind="leader-crosses-leader", sheet="Sheet1", detail="x")
    drawing._assert_no_text_on_line([advisory])
    blocking = Finding(kind="text-on-line", sheet="Sheet1", detail="journal")
    with pytest.raises(RuntimeError, match="text-on-line"):
        drawing._assert_no_text_on_line([advisory, blocking])


def test_drum_station_stack_derives_the_land_length_and_station_band() -> None:
    """Ruling A on the user's located cluster (option c): with the drum station
    at the general .X band, the lands are the smallest whole-mm length that
    keeps every land end over its strap by 0.5 at the worst band corner, at
    BOTH stops of the fit-up end play; no band is tightened (U27)."""
    import alignment_pinion_spec as drum
    import build_drive_train_assembly as assembly
    import pinion_bracket_geometry as strap
    import pinion_bracket_spec

    # The stack's inputs are the parts' and the assembly's own values.
    assert spec.DRUM_LEN == drum.FACE_WIDTH == assembly.APINION_DRUM_LEN
    assert spec.STRAP_T == strap.THICKNESS == assembly.STRAP_T
    assert spec.STRAP_T_BAND == pinion_bracket_spec.THICKNESS_BAND
    assert spec.STRAP_AXIAL_LOCATION == "block-stop-slot-set"
    assert spec.DRUM_STATION == pytest.approx(
        spec.DRUM_STATION_AS_BUILT + spec.DRUM_AFT_SHIFT
    )

    assert spec.JOURNAL_LEN == pytest.approx(19.0)
    assert spec.DRUM_STATION == pytest.approx(61.55)
    assert spec.DRUM_STATION_BAND == spec.LINEAR_X_BAND == pytest.approx(0.8)
    assert spec.END_PLAY == 0.25 and spec.END_PLAY_SET_ERROR == 0.10
    assert (spec.FRONT_JOURNAL_FROM_HEAD_REAR, spec.BACK_JOURNAL_FROM_HEAD_REAR) == (
        pytest.approx(47.4),
        pytest.approx(199.9),
    )
    assert set(spec.LAND_MARGINS_AT_STOPS) == {"drum forward", "drum aft"}
    for margins in spec.LAND_MARGINS_AT_STOPS.values():
        assert set(margins) == set(spec.LAND_ENDS)
        assert min(margins.values()) >= 0.5 - 1e-9
    # One millimetre shorter fails: the derivation picked the smallest length.
    assert spec.land_margin_slack(spec.JOURNAL_LEN - 1.0) < 0.0
    # The drum never binds between the straps.
    assert spec.END_PLAY - spec.END_PLAY_SET_ERROR >= 0.1
    assert spec.drum_total_air() == (
        pytest.approx(spec.END_PLAY - spec.END_PLAY_SET_ERROR),
        pytest.approx(spec.END_PLAY + spec.END_PLAY_SET_ERROR),
    )
    # The lands are centred on their straps (to the printed place) with the
    # drum mid-way through its play.
    air = spec.END_PLAY / 2.0
    front_mid = spec.FRONT_JOURNAL_FROM_HEAD_REAR + spec.JOURNAL_LEN / 2.0
    back_mid = spec.BACK_JOURNAL_FROM_HEAD_REAR + spec.JOURNAL_LEN / 2.0
    front_strap_mid = spec.DRUM_STATION - air - spec.STRAP_T / 2.0
    back_strap_mid = spec.DRUM_STATION + spec.DRUM_LEN + air + spec.STRAP_T / 2.0
    assert abs(front_mid - front_strap_mid) <= 0.05 + 1e-9
    assert abs(back_mid - back_strap_mid) <= 0.05 + 1e-9


def test_drum_bond_note_states_the_derived_station() -> None:
    assert spec.DRAWING_NOTES.splitlines() == [
        "JOURNALS RUN IN MHA-056 REAMED BORES.",
        "SHAFT SLIPS INTO MHA-002; BOND WITH LOCTITE 638, DRUM FRONT END",
        "  61.55 +/-0.8 FROM HEAD SHOULDER. WIPE SQUEEZE-OUT OFF JOURNAL LANDS.",
    ]
    assert f"{spec.DRUM_STATION:.2f} +/-{spec.DRUM_STATION_BAND:.1f}" in spec.DRAWING_NOTES



@pytest.mark.xfail(
    strict=True,
    reason=(
        "pinioncluster's option-(c) re-lay moves BDT APINION_Z_FRONT 0.3 aft "
        "(ARBOR_Z0 fixed); until then BDT carries the as-built 61.25. "
        "Flip to a plain test in the re-lay PR."
    ),
)
def test_drum_station_matches_the_assembled_drum_on_the_arbor() -> None:
    import build_drive_train_assembly as assembly

    shoulder_z = assembly.ARBOR_Z0 + spec.HEAD_REAR_Z
    assert assembly.APINION_Z_FRONT - shoulder_z == pytest.approx(spec.DRUM_STATION)


def test_drum_station_as_built_matches_the_current_assembly() -> None:
    """Until the re-lay lands, BDT still places the drum at the as-built
    station the 0.3 aft shift is measured from."""
    import build_drive_train_assembly as assembly

    shoulder_z = assembly.ARBOR_Z0 + spec.HEAD_REAR_Z
    assert assembly.APINION_Z_FRONT - shoulder_z == pytest.approx(
        spec.DRUM_STATION_AS_BUILT
    )
