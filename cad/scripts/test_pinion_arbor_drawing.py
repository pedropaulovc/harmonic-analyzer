"""Behavioral release contracts for the integral MHA-102 pinion arbor."""

from __future__ import annotations

import math
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
        | set(drawing.DETAIL_A_KEEP)
    )
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert not hasattr(spec, "DRAWING_REFERENCE_PRECISION")
    assert {"HeadDia"} == set(drawing.DONOR_KEEP)
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
        ("BondZoneReference", "BondZoneDia"): "*deviations(SHAFT_DIA_BAND)",
        ("DrumStationReference", "DrumStationFromHeadRear"): "DRUM_STATION_BAND",
        ("CrossHoleProfile", "CrossHoleDia"): "*deviations(CROSS_HOLE_DIA_BAND)",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_DIA_BAND)",
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
    for key, (station_z, _symbol_xy, _flank) in drawing.JOURNAL_FINISHES.items():
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
        | set(drawing.DETAIL_A_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= carried
    assert set(spec.DRAWING_PRECISION_BY_NAME) == carried
    # Every donor diameter moves onto the profile; detail A's is imported
    # into it, never moved (neckbisect-ecef).
    assert set(drawing.DIAMETER_POSITIONS) == set(drawing.DONOR_KEEP)
    assert set(drawing.DETAIL_DIAMETER_POSITIONS) <= set(drawing.DETAIL_A_KEEP)
    assert set(drawing.DETAIL_DIAMETER_POSITIONS).isdisjoint(drawing.DONOR_KEEP)
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
        "DrumStationFromHeadRear": spec.DRUM_STATION,
    }
    for name, value in nominal.items():
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        assert value == pytest.approx(round(value, places), abs=1e-9), name


def test_each_land_diameter_is_measured_a_short_extension_from_its_line() -> None:
    """Main (aab2b98b): the land diameters were measured at the land's
    head-side end, so their extensions ran 18-25 mm along the flank to the
    text.  Each is now measured at a witness just inside the crown-side end
    and its line stands 1 mm from it, so the extension cannot grow back."""
    assert part.JOURNAL_DIA_POINT_FROM_CROWN_END == drawing.JOURNAL_DIA_POINT_FROM_CROWN_END
    assert 0.0 < part.JOURNAL_DIA_POINT_FROM_CROWN_END <= 3.0
    for key, land_z in (("Front", spec.FRONT_JOURNAL_Z), ("Back", spec.BACK_JOURNAL_Z)):
        point_x = drawing._sheet_x(
            land_z + spec.JOURNAL_LEN - part.JOURNAL_DIA_POINT_FROM_CROWN_END
        )
        line_x = drawing.PRINCIPAL_KEEP[f"{key}JournalDia"][0]
        assert abs(line_x - point_x) <= 0.0015, key
        crown_end = drawing._sheet_x(land_z + spec.JOURNAL_LEN)
        head_end = drawing._sheet_x(land_z)
        assert min(crown_end, head_end) < line_x < max(crown_end, head_end), key


def test_back_journal_diameter_hangs_above_clear_of_the_crown_witnesses() -> None:
    """Below the shaft the back land is boxed in: the back-crown/overall
    witnesses (x 0.079-0.081) on its crown side ran through its text at
    30620a85, and the 199.9 witness and Ra leader sit on its head side.  Its
    diameter hangs above, text right of the line; its 19.0 goes below."""
    width, height = drawing.DIAMETER_BLOCK_SIZE
    x, y = drawing.PRINCIPAL_KEEP["BackJournalDia"]
    shaft_top = drawing.PRINCIPAL_CENTER[1] + spec.SHAFT_DIA / 2000.0
    # 12 -> 15 mm: the back Ra symbol now sits between block and shaft.
    assert 0.003 <= (y - height / 2.0) - shaft_top <= 0.015
    assert x - 0.081 >= 0.010  # clear of the crown witnesses rising to the sag
    detail_left = drawing.DETAIL_LABEL_XY[0] - 0.017
    assert detail_left - (x + width) >= 0.010
    # The 19.0 sits below, clear of the land's crown-side end.
    len_x, _len_y = drawing.PRINCIPAL_KEEP["BackJournalLen"]
    crown_end = drawing._sheet_x(spec.BACK_JOURNAL_Z + spec.JOURNAL_LEN)
    assert len_x - 0.0055 > crown_end


def test_back_ra_symbol_hangs_above_the_shaft_clear_of_every_witness() -> None:
    """c6eb7f6f: the back Ra leader's shoulder crossed the 199.9 / 19.0
    witness below the shaft, a line through the symbol (Main).  Above the
    shaft nothing rises from the back land, so the symbol hangs there."""
    edge_z, (symbol_x, symbol_y), flank = drawing.JOURNAL_FINISHES["back_journal"]
    assert flank == "upper"
    assert drawing.JOURNAL_FINISHES["front_journal"][2] == "lower"
    head_end = drawing._sheet_x(spec.BACK_JOURNAL_Z)
    crown_end = drawing._sheet_x(spec.BACK_JOURNAL_Z + spec.JOURNAL_LEN)
    arrow_x = drawing._sheet_x(edge_z)
    assert crown_end < arrow_x < head_end  # the arrow lands on the land
    left, right, top = drawing.RA_SYMBOL_EXTENT
    shaft_top = drawing.PRINCIPAL_CENTER[1] + spec.SHAFT_DIA / 2000.0
    # A leader rise long enough to carry its arrowhead.
    assert symbol_y - shaft_top >= 0.004
    # The shoulder runs head side from the arrow, right of the diameter line.
    dia_line_x = drawing.BACK_JOURNAL_DIA_POINT_X
    assert dia_line_x + 0.010 < arrow_x < symbol_x
    assert symbol_x + left - dia_line_x >= 0.010
    # Under the back JOURNAL block, with a gap.
    _width, height = drawing.DIAMETER_BLOCK_SIZE
    dia_bottom = drawing.PRINCIPAL_KEEP["BackJournalDia"][1] - height / 2.0
    assert dia_bottom - (symbol_y + top) >= 0.002
    # Clear of the DETAIL A label to its right.
    assert (drawing.DETAIL_LABEL_XY[0] - 0.017) - (symbol_x + right) >= 0.005
    assert "leader-crosses-leader" in drawing.BLOCKING_LAYOUT_FINDINGS


def test_bond_zone_callout_sits_above_the_shaft_clear_of_its_neighbours() -> None:
    """At 63468ee9 the BOND ZONE shelf ended 1 mm short of the front JOURNAL
    shelf below the shaft, so a novice could read -0.01/-0.10 as the
    journal's (Main, Fable).  It now hangs above the shaft, where no other
    diameter is, clear of detail A, its label and the front land's 19.0."""
    width, height = drawing.DIAMETER_BLOCK_SIZE
    x, y = drawing.PRINCIPAL_KEEP["BondZoneDia"]
    left, right, bottom, top = x, x + width, y - height / 2.0, y + height / 2.0
    shaft_top = drawing.PRINCIPAL_CENTER[1] + spec.SHAFT_DIA / 2000.0
    # Short witnesses: the block starts a few mm off the silhouette.
    assert 0.003 <= bottom - shaft_top <= 0.012
    # Right of the DETAIL A label and the detail circle.
    detail_x, detail_y = drawing.DETAIL_CENTER
    detail_r = drawing.DETAIL_RADIUS_MM * 2 / 1000.0
    near_x = max(left - detail_x, 0.0, detail_x - right)
    near_y = max(bottom - detail_y, 0.0, detail_y - top)
    assert (near_x**2 + near_y**2) ** 0.5 - detail_r >= 0.010
    assert left - (drawing.DETAIL_LABEL_XY[0] + 0.017) >= 0.010
    # Short of the front land's 19.0 witness and its outside arrow tail.
    front_land_end = drawing._sheet_x(spec.FRONT_JOURNAL_Z + spec.JOURNAL_LEN)
    assert front_land_end - 0.006 - right >= 0.005
    # Under detail A's "(3.0)" line (sheet y ~0.207).
    assert top <= 0.200


FENCE = {"center": (0.3132, 0.171), "radius": 0.015, "axis": (-1.0, 0.0)}


def _fence_dim(label: str, *segments):
    from _layout_geometry import AnnotationGeometry

    return AnnotationGeometry(label=label, kind="dim", owner="p", segments=segments)


def test_fence_lets_a_vertical_diameter_line_out_but_not_its_extension_lines() -> None:
    """Run 492a7be5: HeadDia's own vertical line runs up out of the fence to
    its text (allowed, a line crossing a line); a horizontal run off a
    vertical diameter is an extension line and may not leave (Main ruling)."""
    from _layout_geometry import Segment

    to_text = Segment(0.3238, 0.1775, 0.3238, 0.1892)  # the flagged run
    tail = Segment(0.3238, 0.1625, 0.3238, 0.1562)  # the outside-arrow tail
    inside = Segment(0.3190, 0.1785, 0.3250, 0.1785)  # extension, in the fence
    arrows = {"HeadDia": ((0.3238, 0.1775), (0.0, -1.0))}
    head = _fence_dim("HeadDia", to_text, tail, inside)
    drawing._assert_witnesses_clear_of_detail_fence([head], arrows=arrows, **FENCE)
    assert drawing._segment_kind(to_text, arrows["HeadDia"][1]) == "dimension-line"
    assert drawing._segment_kind(inside, arrows["HeadDia"][1]) == "extension-line"

    outward = Segment(0.3190, 0.1785, 0.3420, 0.1785)  # the old Ø15 witness
    with pytest.raises(RuntimeError, match="HeadDia' extension-line"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [_fence_dim("HeadDia", to_text, outward)], arrows=arrows, **FENCE
        )


def test_fence_lets_a_horizontal_station_out_on_its_witnesses_and_line() -> None:
    """A station from the head shoulder measures along the turning axis: its
    vertical extension lines drop to the stack and its horizontal dimension
    line may cross, while a run oblique to it may not."""
    from _layout_geometry import Segment

    witness = Segment(0.3080, 0.1650, 0.3080, 0.1280)  # drops to the stack
    upward = Segment(0.3080, 0.1750, 0.3080, 0.2000)  # still a station witness
    line = Segment(0.2600, 0.1600, 0.3100, 0.1600)  # its own dimension line
    arrows = {"FrontJournalFromHeadRear": ((0.3080, 0.1600), (1.0, 0.0))}
    station = _fence_dim("FrontJournalFromHeadRear", witness, upward, line)
    drawing._assert_witnesses_clear_of_detail_fence([station], arrows=arrows, **FENCE)
    assert drawing._segment_kind(witness, (1.0, 0.0)) == "extension-line"
    assert drawing._segment_kind(line, (1.0, 0.0)) == "dimension-line"

    oblique = Segment(0.3080, 0.1650, 0.3300, 0.1400)
    with pytest.raises(RuntimeError, match="oblique"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [_fence_dim("FrontJournalFromHeadRear", line, oblique)],
            arrows=arrows,
            **FENCE,
        )


def test_fence_judges_an_unread_or_misread_dimension_as_all_extension_lines() -> None:
    from _layout_geometry import Segment

    run = Segment(0.3080, 0.1650, 0.3080, 0.1280)
    with pytest.raises(RuntimeError, match="extension-line"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [_fence_dim("NoArrow", run)], arrows={}, **FENCE
        )
    # A run that stops at the arrow's base still carries the arrow's tip.
    short = Segment(0.3238, 0.1805, 0.3238, 0.1892)
    base = {"Base": ((0.3238, 0.1775), (0.0, -1.0))}
    drawing._assert_witnesses_clear_of_detail_fence(
        [_fence_dim("Base", short)], arrows=base, **FENCE
    )
    # An arrowhead off every one of its own parallel runs is a misread.
    stray = {"Stray": ((0.2000, 0.2000), (0.0, 1.0))}
    with pytest.raises(RuntimeError, match="unreadable"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [_fence_dim("Stray", run)], arrows=stray, **FENCE
        )
    # Leaders are the audit's, not the fence's.
    leader = Segment(0.3238, 0.1650, 0.3238, 0.1920, "leader")
    drawing._assert_witnesses_clear_of_detail_fence(
        [_fence_dim("Led", leader)], arrows={}, **FENCE
    )


def test_bond_zone_diameter_is_a_flank_dimension_on_the_drum() -> None:
    """The end-on Ø8 circle sat in the neck face, so its witnesses crossed the
    neck and the detail fence (run 492a7be5).  The bond zone now carries its
    own Top-plane diameter, printed over its witness, clear of the fence."""
    assert "ShaftProfile" not in spec.DRAWING_DIMENSIONS
    assert spec.DRAWING_DIMENSIONS["BondZoneReference"] == {"BondZoneDia"}
    assert drawing.DIMENSION_CALLOUTS["BondZoneDia"] == "BOND ZONE"
    station = spec.BOND_ZONE_DIA_FROM_HEAD_REAR
    clear = spec.BOND_ZONE_LAND_CLEARANCE
    assert spec.FRONT_JOURNAL_FROM_HEAD_REAR + spec.JOURNAL_LEN + clear <= station
    assert station <= spec.BACK_JOURNAL_FROM_HEAD_REAR - clear
    assert spec.DRUM_STATION < station < spec.DRUM_STATION + spec.DRUM_LEN
    text_x, _ = drawing.PRINCIPAL_KEEP["BondZoneDia"]
    assert text_x == pytest.approx(drawing._sheet_x(spec.BOND_ZONE_DIA_Z))
    fence_x = drawing._sheet_x(spec.HEAD_CENTER_Z)
    assert fence_x - text_x > drawing.DETAIL_RADIUS_MM / 1000.0 + 0.050


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

    advisory = Finding(kind="leader-crosses-view", sheet="Sheet1", detail="x")
    drawing._assert_no_text_on_line([advisory])
    for kind in ("text-on-line", "text-on-text", "leader-crosses-leader"):
        blocking = Finding(kind=kind, sheet="Sheet1", detail="journal")
        with pytest.raises(RuntimeError, match="blocking finding"):
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
    # The drum-end airs share the cluster's one end play with the block gaps.
    assert spec.drum_total_air() == (
        0.0,
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


def test_drum_station_is_a_model_dimension_the_note_only_names() -> None:
    """Codex P1 on #814: notes never carry dimensions.  The drum station is
    the model's own reference dimension from the Ø15 head rear face, printed
    at .X with the "DRUM STATION" callout the note points to."""
    assert spec.DRAWING_NOTES.splitlines() == [
        "JOURNALS RUN IN MHA-056 REAMED BORES.",
        "SHAFT SLIPS INTO MHA-002; BOND WITH LOCTITE 638, DRUM FRONT END",
        "  AT DRUM STATION. WIPE SQUEEZE-OUT OFF JOURNAL LANDS.",
    ]
    assert f"{spec.DRUM_STATION:.2f}" not in spec.DRAWING_NOTES
    assert f"{spec.DRUM_STATION_BAND:.1f}" not in spec.DRAWING_NOTES
    assert spec.DRAWING_DIMENSIONS["DrumStationReference"] == {"DrumStationFromHeadRear"}
    assert spec.DRAWING_PRECISION_BY_NAME["DrumStationFromHeadRear"] == 2
    assert drawing.DIMENSION_CALLOUTS["DrumStationFromHeadRear"] == "DRUM STATION"
    assert "DRUM STATION" in spec.DRAWING_NOTES
    assert spec.DRUM_STATION_BAND == spec.LINEAR_X_BAND


def test_every_station_names_the_same_head_rear_face() -> None:
    """Fable m1: the head end has two shoulders, so "HEAD SHOULDER" was
    ambiguous for the datum every station runs from."""
    assert "HEAD SHOULDER" not in spec.DRAWING_NOTES
    assert not any("HEAD SHOULDER" in text for text in drawing.DIMENSION_CALLOUTS.values())
    # c3419623 printed "TO  Ø15": <MOD-DIAM> brings its own leading gap.
    assert drawing.DIMENSION_CALLOUTS["BackRimFromHeadRear"] == (
        "FROM BACK CROWN ROOT TO<MOD-DIAM>15 HEAD REAR FACE"
    )


def test_front_journal_diameter_text_clears_the_drum_station_witness() -> None:
    """Run 059b5b0f: the drum station's witness (x 246.0) ran through the
    front land's "Ø8.00 -0.01/-0.03 JOURNAL", whose text hangs left of its
    line.  The line now stands on the land just inside its crown end."""
    x, _ = drawing.PRINCIPAL_KEEP["FrontJournalDia"]
    land_crown_end = drawing._sheet_x(spec.FRONT_JOURNAL_Z + spec.JOURNAL_LEN)
    land_head_end = drawing._sheet_x(spec.FRONT_JOURNAL_Z)
    assert land_crown_end + 0.0008 <= x < land_head_end  # on the land
    right = x + drawing.JOURNAL_DIA_TEXT_OVERHANG
    left = x - 0.026
    assert drawing.DRUM_STATION_WITNESS_X - right >= 0.0025
    # Clear of the bond-zone diameter's line (above the shaft, tail below).
    assert left - drawing.PRINCIPAL_KEEP["BondZoneDia"][0] >= 0.010


def test_drum_station_witness_starts_on_the_flank_not_the_axis() -> None:
    """c3419623: from an axis point the drum station's sheet witness drew a
    4 mm stub inside the Ø8 silhouette that read as a step (Main)."""
    import inspect

    assert part.DRUM_STATION_POINT_X == pytest.approx(spec.SHAFT_DIA / 2.0)
    source = inspect.getsource(part.build)
    call = source[source.index('feature_name="DrumStationReference"') :]
    call = call[: call.index("\n    )")]
    assert "end_on_flank=DRUM_STATION_POINT_X" in call
    helper = inspect.getsource(part._add_axial_reference)
    assert 'far_end = f"{line}.end" if flank is None else f"{flank}.start"' in helper


def test_reference_witnesses_are_drawn_in_the_outline_black() -> None:
    """5471a6ef: both standalone reference sketches' flank witnesses printed in
    the default construction grey over the black Ø8 outline, a break a
    machinist reads as a groove (Main)."""
    import inspect

    assert set(drawing.REFERENCE_WITNESSES) == {"DrumStationReference", "BondZoneReference"}
    assert drawing.REFERENCE_WITNESS_COLOR == 0
    assert drawing.DRUM_STATION_POINT_LEN == part.DRUM_STATION_POINT_LEN
    assert drawing.BOND_ZONE_WITNESS_LEN == part.BOND_ZONE_WITNESS_LEN
    drum = drawing.REFERENCE_WITNESSES["DrumStationReference"]
    assert drum[1] == pytest.approx(spec.HEAD_REAR_Z + spec.DRUM_STATION)
    assert drum[1] - drum[0] == pytest.approx(part.DRUM_STATION_POINT_LEN)
    bond = drawing.REFERENCE_WITNESSES["BondZoneReference"]
    assert bond[0] == pytest.approx(spec.BOND_ZONE_DIA_Z)
    assert bond[1] - bond[0] == pytest.approx(part.BOND_ZONE_WITNESS_LEN)
    helper = inspect.getsource(drawing._blacken_reference_witnesses)
    assert "drawing.SetLineColor(REFERENCE_WITNESS_COLOR)" in helper
    assert "SW_SEL_EXT_SKETCH_SEGS" in helper and "ConstructionGeometry" in helper
    # 7885c0d9: rebinding the ISketch as IFeature read a matrix for Name.
    assert '"IFeature"' not in helper and "segment.GetLength()" in helper
    source = inspect.getsource(drawing.build)
    detail = source.index("_dimensioned_head_detail(")
    blacken = source.index("adapter, principal, REFERENCE_WITNESSES, flank_dia=SHAFT_DIA")
    merged = source.index("**detail_spans,")
    finalize = source.index("await finalize_drawing(")
    gate = source.index("_assert_outline_unbroken(PNG, witness_spans, sheet_size)")
    assert detail < blacken < merged < finalize < gate


def _outline_raster(core: int):
    from PIL import Image, ImageDraw

    # 1 px per mm on a 100 x 50 mm sheet; the outline runs along sheet y = 20.
    raster = Image.new("L", (100, 50), 255)
    pen = ImageDraw.Draw(raster)
    pen.line([(0, 29), (99, 29)], fill=0)
    pen.line([(0, 30), (99, 30)], fill=0)
    pen.line([(40, 29), (44, 29)], fill=core)
    pen.line([(40, 30), (44, 30)], fill=core)
    return raster


def test_outline_raster_check_flags_a_grey_witness_and_passes_black() -> None:
    spans = {"DrumStationReference": ((0.039, 0.020), (0.045, 0.020))}
    grey = drawing._broken_outline_columns(_outline_raster(128), spans, (0.100, 0.050))
    assert grey == {"DrumStationReference": [40, 41, 42, 43, 44]}
    assert drawing._broken_outline_columns(_outline_raster(0), spans, (0.100, 0.050)) == {}


def test_drum_station_text_clears_the_station_stack() -> None:
    """The drum station's text sits left of its drum-end witness: between
    that witness and the head face, the neck-end witness drops through."""
    x, y = drawing.PRINCIPAL_KEEP["DrumStationFromHeadRear"]
    half = drawing.DRUM_STATION_TEXT_WIDTH / 2.0
    drum_end = drawing._sheet_x(spec.HEAD_REAR_Z + spec.DRUM_STATION)
    assert x + half <= drum_end - 0.003
    # Between the 47.4 (above) and 199.9 (below) station lines.
    assert drawing.PRINCIPAL_KEEP["BackJournalFromHeadRear"][1] < y
    assert y < drawing.PRINCIPAL_KEEP["FrontJournalFromHeadRear"][1]
    # The 199.9 text (about 18 mm wide) stays clear of it horizontally.
    back_x = drawing.PRINCIPAL_KEEP["BackJournalFromHeadRear"][0]
    assert back_x + 0.009 + 0.010 <= x - half



def test_drum_station_matches_the_assembled_drum_on_the_arbor() -> None:
    """pinioncluster's option-(c) re-lay (#855) moved BDT APINION_Z_FRONT 0.3
    aft with ARBOR_Z0 fixed, so the assembly now carries the printed station."""
    import build_drive_train_assembly as assembly

    shoulder_z = assembly.ARBOR_Z0 + spec.HEAD_REAR_Z
    assert assembly.APINION_Z_FRONT - shoulder_z == pytest.approx(spec.DRUM_STATION)


def test_collar_pin_hole_is_a_drilled_spring_pin_hole_clear_of_the_front_land() -> None:
    """R1a (user, 2026-09-24): the MHA-144 collar's 1/16 in spring-pin hole.

    It prints the rig's functional band (not the title block's drilled-hole
    band), stands at a .X station from the head rear face, never enters the
    front land or its Ra 1.6 run-out at the worst corner, and leaves the U27
    2.0 web target of steel beside it.
    """
    import pinion_arbor_pin_spec as pin_hole
    import pinion_strap_pin_spec as strap_pin

    # One pin family and one drill for the whole rig (pinioncluster's E-a).
    assert pin_hole.PIN_HOLE_DIA == strap_pin.HOLE_DIA == pytest.approx(25.4 / 16.0)
    assert pin_hole.PIN_HOLE_DIA_BAND == strap_pin.HOLE_BAND == (0.06, 0.0)
    assert pin_hole.PIN_HOLE_CALLOUT == strap_pin.DRILL_THRU_CALLOUT
    assert spec.PIN_STATION_FROM_HEAD_REAR == 39.0
    assert spec.PIN_STATION_BAND == spec.LINEAR_X_BAND
    assert spec.PIN_Z == pytest.approx(spec.HEAD_REAR_Z + 39.0)
    assert pin_hole.PIN_HOLE_LAND_CLEARANCE >= 2.0
    assert pin_hole.PIN_HOLE_NECK_CLEARANCE >= 2.0
    assert pin_hole.PIN_HOLE_LIGAMENT_WORST == pytest.approx(3.126, abs=1e-3)
    assert pin_hole.PIN_HOLE_LIGAMENT_WORST >= 2.0
    assert spec.DRAWING_DIMENSIONS["PinHoleProfile"] == {"PinHoleDia"}
    assert spec.DRAWING_DIMENSIONS["PinStationReference"] == {"PinStationFromHeadRear"}
    assert spec.DRAWING_PRECISION_BY_NAME["PinHoleDia"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["PinStationFromHeadRear"] == 1
    assert drawing.DIMENSION_CALLOUTS["PinHoleDia"] == "1/16 DRILL THRU"
    assert drawing.DIMENSION_CALLOUTS["PinStationFromHeadRear"] == "COLLAR PIN"
    assert part.V_PIN_HOLE > 0.0


def test_collar_pin_dimensions_stand_above_the_shaft_clear_of_the_front_ra() -> None:
    """Below the shaft at x 0.269 is the front land's Ra symbol, so the pin
    hole's station and diameter both stand above it: the station over the
    Ø15's text row, the diameter's leader left of the station witness and
    above the 19.0 land length."""
    pin_x = drawing._sheet_x(spec.PIN_Z)
    head_rear_x = drawing._sheet_x(spec.HEAD_REAR_Z)
    axis_y = drawing.PRINCIPAL_CENTER[1]
    station_x, station_y = drawing.PRINCIPAL_KEEP["PinStationFromHeadRear"]
    dia_x, dia_y = drawing.PRINCIPAL_KEEP["PinHoleDia"]
    assert pin_x < station_x < head_rear_x
    assert station_y > drawing.DIAMETER_POSITIONS["HeadDia"][1] + 0.010
    assert dia_x < pin_x
    assert dia_y > station_y + 0.010
    assert dia_y > drawing.PRINCIPAL_KEEP["FrontJournalLen"][1] + 0.030
    assert min(station_y, dia_y) > axis_y


# Measured witness overshoot past a dimension line: c486b6e1's NeckDia line
# at x 294.5 had its witnesses end at 293.5.
WITNESS_OVERSHOOT_M = 0.001


def _neck_text_box(xy: tuple[float, float]) -> tuple[float, float, float, float]:
    left, right, bottom, top = drawing.NECK_DIA_TEXT_BOX_FROM_POSITION
    return xy[0] + left, xy[0] + right, xy[1] + bottom, xy[1] + top


def test_neck_text_box_is_the_audit_box_stacktop_dbe47ae3_measured() -> None:
    # Text at (0.300, 0.194) audited as [284.4,191.2]..[311.5,194.7] mm.
    box = _neck_text_box((0.300, 0.194))
    assert box == pytest.approx((0.2844, 0.3115, 0.1912, 0.1947))


def test_every_profile_diameter_keeps_its_witnesses_inside_the_detail_fence() -> None:
    """A diameter on the 1:1 profile whose part lies inside detail A must
    stand its line on that part, inside the fence: its witnesses run from the
    part to the line and 1 mm past it, and the build's fence gate fails any
    that leaves the circle (c486b6e1: NeckDia's line at x 0.2945, ahead of
    the neck's front shoulder, ran both witnesses out through the fence)."""
    center_x = drawing._sheet_x(spec.HEAD_CENTER_Z)
    reach = drawing.DETAIL_RADIUS_MM / 1000.0 + drawing.FENCE_TOL_M
    half = {"HeadDia": spec.HEAD_DIA / 2000.0, "NeckDia": spec.NECK_DIA / 2000.0}
    for name, (x, _) in drawing.DIAMETER_POSITIONS.items():
        far = math.hypot(abs(x - center_x) + WITNESS_OVERSHOOT_M, half[name])
        assert far <= reach, f"{name} witnesses leave the fence ({far * 1000:.2f} mm)"


def test_no_profile_placement_clears_both_the_fence_and_the_collar_pin_witness() -> None:
    """Why the neck left the profile: the fence wants its line at x >= 0.300,
    and the audit box (11.5 mm right of the line) must end short of the
    collar-pin station's head-rear-face witness, which wants x < 0.296."""
    center_x = drawing._sheet_x(spec.HEAD_CENTER_Z)
    reach = drawing.DETAIL_RADIUS_MM / 1000.0 + drawing.FENCE_TOL_M
    half = spec.NECK_DIA / 2000.0
    fence_min_x = center_x - (reach**2 - half**2) ** 0.5 + WITNESS_OVERSHOOT_M
    witness_x = drawing._sheet_x(spec.HEAD_REAR_Z)
    witness_max_x = witness_x - drawing.NECK_DIA_TEXT_BOX_FROM_POSITION[1]
    assert fence_min_x > witness_max_x
    assert "NeckDia" not in drawing.DIAMETER_POSITIONS


def test_neck_diameter_is_dimensioned_on_the_neck_inside_detail_a() -> None:
    """Detail A (2:1) holds the neck from the fence to the head rear face.
    The line stands on that stretch, fence side of the NeckReference witness
    its extension lines start from, with the whole reference sketch, both
    witnesses and their overshoot inside the circle."""
    assert set(drawing.DETAIL_DIAMETER_POSITIONS) == {"NeckDia"}
    x, _ = drawing.DETAIL_DIAMETER_POSITIONS["NeckDia"]
    cx, cy = drawing.DETAIL_CENTER
    radius = drawing.DETAIL_RATIO * drawing.DETAIL_RADIUS_MM / 1000.0
    half = drawing.DETAIL_RATIO * spec.NECK_DIA / 2000.0
    # The head centre sits at the detail's centre.
    assert drawing._detail_x(spec.HEAD_CENTER_Z) == pytest.approx(cx)
    head_rear_x = drawing._detail_x(spec.HEAD_REAR_Z)
    witness_x = drawing._detail_x(spec.NECK_DIA_WITNESS_Z)
    witness_head_end_x = drawing._detail_x(spec.NECK_DIA_WITNESS_Z - spec.NECK_DIA_WITNESS_LEN)
    assert witness_x < witness_head_end_x < head_rear_x
    # The whole reference sketch (axis from the head rear face to the
    # witness, and the witness on the flank) lies inside the circle.
    assert math.hypot(cx - witness_x, half) < radius - 0.001
    # On the neck, fence side of the witness the extensions start from.
    assert witness_x - 0.004 < x < witness_x - 0.001
    assert (cx - x) ** 2 + half**2 < radius**2
    # Both witnesses and their overshoot inside the circle, 1 mm to spare.
    far = math.hypot(cx - x + WITNESS_OVERSHOOT_M, half)
    assert far <= radius - 0.001
    # In profile terms the line stands on the neck, inside the 1:1 fence.
    profile_x = drawing._sheet_x(spec.HEAD_CENTER_Z) + (x - cx) / drawing.DETAIL_RATIO
    assert drawing._sheet_x(spec.NECK_END_Z) < profile_x < drawing._sheet_x(spec.HEAD_REAR_Z)
    assert cy + half < drawing.DETAIL_DIAMETER_POSITIONS["NeckDia"][1]


def test_neck_diameter_text_rides_clear_of_detail_a_and_its_callouts() -> None:
    """The neck's text hangs above-left of the fence like the detail's other
    callouts: its audit box stays above the head's top edge, left of the
    SR10.9 leader (which leaves the head's top front corner) and inside the
    sheet border, and the rendered text, left of its line, clears the circle.
    The collar-pin station witness (stacktop-dbe47ae3) is on the profile, not
    here."""
    xy = drawing.DETAIL_DIAMETER_POSITIONS["NeckDia"]
    left, right, bottom, top = _neck_text_box(xy)
    cx, cy = drawing.DETAIL_CENTER
    radius = drawing.DETAIL_RATIO * drawing.DETAIL_RADIUS_MM / 1000.0
    head_top = cy + drawing.DETAIL_RATIO * spec.HEAD_DIA / 2000.0
    assert bottom > head_top + 0.003
    assert right < drawing._detail_x(spec.HEAD_FRONT_Z) - 0.010
    # Inner border at y 266.75 mm on this ASME B sheet (a1a694a6 render).
    assert top < 0.265
    # Rendered text: left of its line, ending ~1.3 mm short of it, in the rows
    # the a1a694a6 profile showed (1.9 mm below to 2.0 mm above the position).
    glyph_right, glyph_bottom = xy[0] - 0.0013, xy[1] - 0.0019
    assert math.hypot(cx - glyph_right, glyph_bottom - cy) > radius + 0.002
    # The line leaves the circle square: at its x the circle's top is below
    # the text row, so the jog to the text sits outside the fence.
    circle_top = cy + (radius**2 - (cx - xy[0]) ** 2) ** 0.5
    assert xy[1] - 0.003 > circle_top + 0.002
    # The detail's own callouts sit right of and below the neck text.
    for name in ("HeadCapR", "CrossHoleDia"):
        assert drawing.DETAIL_KEEP[name][0] > right + 0.030
    for name in ("HeadLen", "HeadCapSagDim"):
        assert drawing.DETAIL_KEEP[name][1] < bottom - 0.030


# --- Detail A imports the neck's Ø10.5 from a hidden reference sketch --------
# Farm bisect neckbisect-ecef (run 20260925T134711864Z-47d629b0): detail A
# refused every NeckDia moved or copied into it, and its selected-feature
# import of the end-on NeckProfile circle brought nothing, while its import
# of the model's other marked dimensions worked.

DETAIL_A_NAMES = {"CrossHoleDia", "HeadCapR", "HeadCapSagDim", "HeadLen", "NeckDia"}


def test_detail_a_prints_its_five_dimensions_and_no_other_view_does() -> None:
    import _drawing_common

    assert set(drawing.DETAIL_A_KEEP) == DETAIL_A_NAMES
    views = {
        "donor": drawing.DONOR_KEEP,
        "profile": drawing.PRINCIPAL_KEEP,
        "detail A": drawing.DETAIL_A_KEEP,
    }
    for name in set().union(*spec.DRAWING_DIMENSIONS.values()):
        owners = [view for view, keep in views.items() if name in keep]
        assert len(owners) == 1, (name, owners)
    # Detail A's import is feature by feature, and NeckDia comes from the
    # reference sketch, not the end-on circle.
    assert _drawing_common._features_owning(
        spec.DRAWING_DIMENSIONS, drawing.DETAIL_A_KEEP, view_label="detail A"
    ) == ("CrossHoleProfile", "FrontCapProfile", "Head", spec.NECK_REFERENCE_SKETCH)
    assert "NeckProfile" not in spec.DRAWING_DIMENSIONS
    assert spec.DRAWING_DIMENSIONS[spec.NECK_REFERENCE_SKETCH] == {"NeckDia"}
    assert spec.REFERENCE_SKETCHES == (spec.NECK_REFERENCE_SKETCH,)
    # No new band: the Ø10.5 prints under the title-block general tolerance,
    # at the one place the model authors.
    assert spec.DRAWING_PRECISION[spec.NECK_REFERENCE_SKETCH] == {"NeckDia": 1}
    assert all("NeckDia" not in key for key in model_toleranced_dimensions(part))


class _Annotation:
    def __init__(self, name: str, kind: int = 4) -> None:
        self.name = name
        self.kind = kind

    def GetType(self) -> int:
        return self.kind


class _DetailView:
    def __init__(self) -> None:
        self.annotations: list[_Annotation] = []

    def GetAnnotations(self):
        return self.annotations


def _detail_seat(monkeypatch, import_names):
    """Stand-ins for detail A's COM seams: the part-shown block, the detail's
    creation, its feature-by-feature import (which delivers ``import_names``)
    and the witness recolour."""
    import contextlib

    log: list[tuple] = []
    infos: list[str] = []
    view = _DetailView()

    @contextlib.contextmanager
    def shown(adapter, part_model, sketches, *, label):
        log.append(("show", part_model, tuple(sketches)))
        try:
            yield
        finally:
            log.append(("blank", tuple(sketches)))

    def head_detail(adapter, parent):
        log.append(("create", parent))
        return view

    def curate(adapter, target, *, keep, view_label, dimensions_by_feature):
        log.append(("curate", target, dict(keep), dimensions_by_feature))
        view.annotations = [_Annotation(name) for name in import_names]
        view.annotations.append(_Annotation("", kind=6))  # the detail label note
        missing = sorted(set(keep) - set(import_names))
        if missing:
            raise RuntimeError(f"{view_label} view is missing model dimensions: {missing}")
        return view.annotations[:-1]

    def blacken(adapter, target, witnesses, *, flank_dia):
        log.append(("blacken", target, witnesses, flank_dia))
        return {"NeckReference": ((0.1425, 0.2245), (0.1445, 0.2245))}

    monkeypatch.setattr(drawing.hidden_sketches, "part_sketches_shown", shown)
    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_head_detail", head_detail)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda a, v: log.append(("hlr", v)))
    monkeypatch.setattr(drawing, "_blacken_reference_witnesses", blacken)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, a: a.name)
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **_: infos.append(message))
    return log, infos, view


def test_detail_a_is_created_and_dimensioned_while_the_part_shows_neck_reference(
    monkeypatch,
) -> None:
    log, infos, view = _detail_seat(monkeypatch, sorted(DETAIL_A_NAMES))
    source, principal = object(), object()
    detail, kept, spans = drawing._dimensioned_head_detail(None, source, principal)
    assert detail is view
    assert sorted(a.name for a in kept) == sorted(DETAIL_A_NAMES)
    assert spans == {"NeckReference": ((0.1425, 0.2245), (0.1445, 0.2245))}
    assert log == [
        ("show", source, ("NeckReference",)),
        ("create", principal),
        ("hlr", view),
        ("curate", view, drawing.DETAIL_A_KEEP, spec.DRAWING_DIMENSIONS),
        ("blacken", view, drawing.DETAIL_REFERENCE_WITNESSES, spec.NECK_DIA),
        ("blank", ("NeckReference",)),
    ]
    assert log[3][3] is spec.DRAWING_DIMENSIONS
    arrived = [message for message in infos if "arrived=" in message]
    assert arrived == [
        "pinion-arbor detail A after its import: arrived=['CrossHoleDia', "
        "'HeadCapR', 'HeadCapSagDim', 'HeadLen', 'NeckDia'], expected=['CrossHoleDia', "
        "'HeadCapR', 'HeadCapSagDim', 'HeadLen', 'NeckDia']"
    ]


def test_a_neck_dia_that_does_not_import_fails_once_naming_what_arrived(
    monkeypatch,
) -> None:
    log, infos, _view = _detail_seat(monkeypatch, sorted(DETAIL_A_NAMES - {"NeckDia"}))
    with pytest.raises(RuntimeError) as error:
        drawing._dimensioned_head_detail(None, object(), object())
    message = str(error.value)
    assert message.startswith(
        "NeckDia did not import into detail A: arrived=['CrossHoleDia', 'HeadCapR', "
        "'HeadCapSagDim', 'HeadLen']; "
    )
    assert "missing model dimensions: ['NeckDia']" in message
    assert isinstance(error.value.__cause__, RuntimeError)
    # The part blanks its sketch again, and the leaf's log says what arrived.
    assert log[-1] == ("blank", ("NeckReference",))
    assert any("arrived=['CrossHoleDia', 'HeadCapR'" in m for m in infos)


def test_any_other_detail_a_miss_keeps_its_own_error(monkeypatch) -> None:
    _detail_seat(monkeypatch, sorted(DETAIL_A_NAMES - {"HeadLen"}))
    with pytest.raises(RuntimeError) as error:
        drawing._dimensioned_head_detail(None, object(), object())
    assert "missing model dimensions: ['HeadLen']" in str(error.value)
    assert "NeckDia did not import" not in str(error.value)


def test_the_neck_global_owns_both_neck_diameters_one_equation_each() -> None:
    owned = tuple(f"{name}@{feature}" for feature, name in part.NECK_DIA_OWNED)
    assert owned == ("NeckProfileDia@NeckProfile", "NeckDia@NeckReference")
    good = [
        '"NeckDia"= 10.5mm',
        '"ShaftDia"= 8mm',
        '"NeckProfileDia@NeckProfile" = "NeckDia"',
        '"NeckDia@NeckReference"= "NeckDia"',
        '"BondZoneDia@BondZoneReference" = "ShaftDia"',
    ]
    part.assert_single_owner(part.equation_owners(good), "NeckDia", owned)
    qualified = [
        equation.replace('@NeckReference"', '@NeckReference@pinion-arbor.Part"')
        for equation in good
    ]
    assert qualified != good
    part.assert_single_owner(part.equation_owners(qualified), "NeckDia", owned)
    broken = {
        "a second equation": [*good, '"NeckDia@NeckReference" = "NeckDia"'],
        "a typed value": [*good[:3], '"NeckDia@NeckReference" = 10.5mm'],
        "another global": [*good[:3], '"NeckDia@NeckReference" = "ShaftDia"'],
        "no equation": good[:3],
        "no global": good[1:],
        "the global twice": [*good, '"NeckDia"= 10.5mm'],
    }
    for case, equations in broken.items():
        with pytest.raises(RuntimeError, match="NeckDia must own"):
            part.assert_single_owner(part.equation_owners(equations), "NeckDia", owned)
            pytest.fail(case)
    with pytest.raises(RuntimeError, match="unreadable equation"):
        part.equation_owners(['"NeckDia" 10.5mm'])


def test_the_build_gates_neck_ownership_after_its_equations() -> None:
    import inspect

    source = inspect.getsource(part.build)
    # The circle keeps its size on the same global, under an unmarked name.
    assert (
        '        names=("NeckCx", "NeckCz", "NeckProfileDia"),\n'
        "        drives=(None, None, '\"NeckDia\"'),\n"
    ) in source
    drive = source.index("await drive_dimension(adapter, dimension_name, expression)")
    gate = source.index("_assert_neck_dia_single_owner(adapter)")
    assert drive < gate
    helper = inspect.getsource(part._assert_neck_dia_single_owner)
    assert "assert_single_owner(owners, \"NeckDia\", owned)" in helper
    # Equation-owned dimensions read DrivenState 1 (knife-cc-5): compare, never == 2.
    assert "states[f\"{name}@{feature}\"] = int(dimension.DrivenState)" in helper
    assert "len(set(states.values())) != 1" in helper
    assert "IsReference()" in helper


def test_neck_reference_is_a_hidden_flank_diameter_like_the_bond_zone() -> None:
    import inspect

    source = inspect.getsource(part.build)
    call = source[source.index("feature_name=NECK_REFERENCE_SKETCH") :]
    call = call[: call.index("\n    )")]
    for argument in (
        "station_from_head_rear=NECK_DIA_WITNESS_FROM_HEAD_REAR",
        "flank_r=NECK_R",
        "witness_run=-NECK_DIA_WITNESS_LEN",
        'dimension_name="NeckDia"',
        "drive_expression='\"NeckDia\"'",
    ):
        assert argument in call, argument
    bond = source[source.index('feature_name="BondZoneReference"') :]
    bond = bond[: bond.index("\n    )")]
    assert "witness_run=BOND_ZONE_WITNESS_LEN" in bond and "flank_r=SHAFT_R" in bond
    # A diametric linear dimension prints no Ø by itself.
    assert 'for prefix in ("FrontJournal", "BackJournal", "BondZone", "Neck"):' in source
    mark = source.index("mark_dimensions_for_drawing(adapter, feature_name, dimension_names)")
    blank = source.index("_blank_reference_sketches(adapter, REFERENCE_SKETCHES)")
    save = source.index("await save_part_and_images(adapter, PART_NAME)")
    assert mark < blank < save
    helper = inspect.getsource(part._blank_reference_sketches)
    assert "blank_sketch(adapter, sketch)" in helper and '"Visible"' in helper
    # The witness runs back towards the head from its station, on the neck.
    assert spec.NECK_DIA_WITNESS_Z == pytest.approx(
        spec.HEAD_REAR_Z + spec.NECK_DIA_WITNESS_FROM_HEAD_REAR
    )
    assert drawing.DETAIL_REFERENCE_WITNESSES == {
        "NeckReference": pytest.approx(
            (spec.NECK_DIA_WITNESS_Z - spec.NECK_DIA_WITNESS_LEN, spec.NECK_DIA_WITNESS_Z)
        )
    }
    assert spec.HEAD_REAR_Z < spec.NECK_DIA_WITNESS_Z - spec.NECK_DIA_WITNESS_LEN
    assert spec.NECK_DIA_WITNESS_Z < spec.NECK_END_Z


class _WitnessSeat:
    """Detail A as ``_blacken_reference_witnesses`` drives it: a 2:1 view of
    the neck's lower flank whose screen pick finds the 1 mm construction
    witness, and a line colour that records what was set."""

    def __init__(self) -> None:
        self.picks: list[tuple[float, float]] = []
        self.colors: list[int] = []
        self.Extension = self
        self.SelectionManager = self

    # IDrawingDoc / IModelDoc2
    def ActivateView(self, name: str) -> bool:
        return name == "Drawing View4"

    def ClearSelection2(self, _all: bool) -> None:
        pass

    def EditRebuild3(self) -> bool:
        return True

    def SetLineColor(self, color: int) -> None:
        self.colors.append(color)

    # IModelDocExtension
    def SelectByID2(self, name, kind, x, y, z, append, mark, callout, option) -> bool:
        self.picks.append((x, y))
        return kind == "EXTSKETCHSEGMENT"

    # ISelectionMgr
    def GetSelectedObjectType3(self, index: int, mark: int) -> int:
        return drawing.SW_SEL_EXT_SKETCH_SEGS

    def GetSelectedObject6(self, index: int, mark: int):
        return self

    # ISketchSegment
    ConstructionGeometry = True

    def GetName(self) -> str:
        return "Line2"

    def GetLength(self) -> float:
        return spec.NECK_DIA_WITNESS_LEN / 1000.0

    # IView
    def UpdateViewDisplayGeometry(self) -> None:
        pass


def _detail_projection(adapter, view, xyz, *, label):
    """Detail A's 2:1 model-to-sheet map: head centre at DETAIL_CENTER, the
    model's +x flank below the axis."""
    x, _y, z = xyz
    return (
        drawing._detail_x(z * 1000.0),
        drawing.DETAIL_CENTER[1] - drawing.DETAIL_RATIO * x,
    )


SHEET = (0.4318, 0.2794)  # ASME B
PX_PER_M = 5000  # 5 px per mm


def _detail_neck_raster(path: Path, spans, witness_color: int | None) -> None:
    """The detail's lower neck outline, black and 2 px thick, with the
    witness painted over it: grey unless the recolour ran."""
    from PIL import Image, ImageDraw

    raster = Image.new("L", (round(SHEET[0] * PX_PER_M), round(SHEET[1] * PX_PER_M)), 255)
    pen = ImageDraw.Draw(raster)
    (x0, y), (x1, _) = spans["NeckReference"]
    row = round((SHEET[1] - y) * PX_PER_M)
    left = round((drawing.DETAIL_CENTER[0] - 0.030) * PX_PER_M)
    right = round(drawing._detail_x(spec.HEAD_REAR_Z) * PX_PER_M)
    core = 128 if witness_color is None else witness_color
    for r in (row, row + 1):
        pen.line([(left, r), (right, r)], fill=0)
        pen.line([(round(x0 * PX_PER_M), r), (round(x1 * PX_PER_M), r)], fill=core)
    raster.save(path)


def test_detail_a_neck_witness_is_drawn_black_and_the_raster_gate_reads_it(
    monkeypatch, tmp_path
) -> None:
    """Ruling 4: at 2:1 the NeckReference witness paints construction grey
    over the Ø10.5 outline, a break a machinist reads as a groove.  The gate
    must fail on the unrecoloured sheet and pass once the witness is black."""
    seat = _WitnessSeat()
    adapter = type("Adapter", (), {"currentModel": seat})()
    monkeypatch.setattr(drawing, "model_point_in_view", _detail_projection)
    monkeypatch.setattr(drawing, "view_name", lambda adapter, view: "Drawing View4")
    spans = drawing._blacken_reference_witnesses(
        adapter, seat, drawing.DETAIL_REFERENCE_WITNESSES, flank_dia=spec.NECK_DIA
    )
    z0, z1 = drawing.DETAIL_REFERENCE_WITNESSES["NeckReference"]
    flank_y = drawing.DETAIL_CENTER[1] - drawing.DETAIL_RATIO * spec.NECK_DIA / 2000.0
    assert spans == {
        "NeckReference": (
            pytest.approx((drawing._detail_x(z0), flank_y)),
            pytest.approx((drawing._detail_x(z1), flank_y)),
        )
    }
    mid = ((drawing._detail_x(z0) + drawing._detail_x(z1)) / 2.0, flank_y)
    assert seat.picks == [pytest.approx(mid)]
    assert seat.colors == [drawing.REFERENCE_WITNESS_COLOR]

    unrecoloured = tmp_path / "grey.png"
    _detail_neck_raster(unrecoloured, spans, witness_color=None)
    with pytest.raises(RuntimeError, match="outline broken over reference witness: NeckReference"):
        drawing._assert_outline_unbroken(unrecoloured, spans, SHEET)

    recoloured = tmp_path / "black.png"
    _detail_neck_raster(recoloured, spans, witness_color=seat.colors[-1])
    drawing._assert_outline_unbroken(recoloured, spans, SHEET)


def test_the_raster_gate_reads_detail_a_and_the_profile_neck() -> None:
    import inspect

    source = inspect.getsource(drawing._dimensioned_head_detail)
    create = source.index("_head_detail(adapter, principal)")
    curate = source.index("hidden_sketches.curate_view_dimensions(")
    blacken = source.index("adapter, detail, DETAIL_REFERENCE_WITNESSES, flank_dia=NECK_DIA")
    assert source.index("hidden_sketches.part_sketches_shown(") < create < curate < blacken
    assert "keep=DETAIL_A_KEEP" in source
    assert "dimensions_by_feature=DRAWING_DIMENSIONS" in source
    build = inspect.getsource(drawing.build)
    spans = build[build.index("witness_spans = {") :]
    spans = spans[: spans.index("\n    }")]
    assert "**detail_spans," in spans and "PROFILE_NECK_WITNESS:" in spans
    # The neck never goes through _move_dimension any more.
    assert "DETAIL_DIAMETER_POSITIONS" not in build[: build.index("_dimensioned_head_detail(")]
