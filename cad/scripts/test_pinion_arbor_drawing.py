"""Behavioral release contracts for the integral MHA-102 pinion arbor."""

from __future__ import annotations

import inspect
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_leaders
import _drawing_marks
import _fit_limits
import _surface_finish
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
        set(drawing.END_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert not hasattr(spec, "DRAWING_REFERENCE_PRECISION")
    assert {"HeadDia", "NeckDia"} == set(drawing.END_KEEP)
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
    assert spec.JOURNAL_LANDS_FINISH_NOTE in spec.DRAWING_NOTES
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


def test_every_post_import_name_is_carried_by_a_kept_dimension() -> None:
    """Offline audit of the names the sheet looks up after the model import."""
    carried = (
        set(drawing.END_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= carried
    assert set(spec.DRAWING_PRECISION_BY_NAME) == carried
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
        "JOURNAL LANDS Ra 1.6.",
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
    # 7885c0d9: rebinding the ISketch as IFeature read a matrix for Name.
    assert '"IFeature"' not in inspect.getsource(drawing._selection_problem)
    source = inspect.getsource(drawing.build)
    blacken = source.index("_blacken_reference_witnesses(adapter, principal)")
    finalize = source.index("await finalize_drawing(")
    gate = source.index("_assert_outline_unbroken(PNG, witness_spans, sheet_size)")
    assert blacken < finalize < gate


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


def test_collar_pin_dimensions_stand_above_the_shaft() -> None:
    """Below the shaft at x 0.269 run the front land's stations, so the pin
    hole's station and diameter both stand above it: the station well over
    the Ø15 head, the diameter's callout left of the station witness and
    above the 19.0 land length, its leader leaning in from the upper left."""
    pin_x = drawing._sheet_x(spec.PIN_Z)
    head_rear_x = drawing._sheet_x(spec.HEAD_REAR_Z)
    axis_y = drawing.PRINCIPAL_CENTER[1]
    station_x, station_y = drawing.PRINCIPAL_KEEP["PinStationFromHeadRear"]
    dia_x, dia_y = drawing.PRINCIPAL_KEEP["PinHoleDia"]
    assert pin_x < station_x < head_rear_x
    assert station_y > axis_y + spec.HEAD_DIA / 2000.0 + 0.020
    assert dia_x < pin_x
    assert dia_y > station_y + 0.005
    assert dia_y > drawing.PRINCIPAL_KEEP["FrontJournalLen"][1] + 0.020
    assert min(station_y, dia_y) > axis_y


# --- Option C: the Ø15 and Ø10.5 print on a projected end view -------------


def test_neck_dia_is_the_one_driving_dimension_on_the_neck_circle() -> None:
    """The hidden NeckReference route is retired: the neck circle's own
    NeckDia is the printed dimension again, at one place, with no band."""
    import inspect

    assert spec.DRAWING_DIMENSIONS.get("NeckProfile") == {"NeckDia"}
    assert spec.DRAWING_DIMENSIONS.get("HeadProfile") == {"HeadDia"}
    assert "NeckReference" not in spec.DRAWING_DIMENSIONS
    assert not hasattr(spec, "REFERENCE_SKETCHES")
    assert spec.DRAWING_PRECISION_BY_NAME["NeckDia"] == 1
    assert spec.DRAWING_PRECISION_BY_NAME["HeadDia"] == 1
    assert all(name != "NeckDia" for _, name in model_toleranced_dimensions(part))
    source = inspect.getsource(part)
    assert "NeckReference" not in source
    assert "NeckProfileDia" not in source
    assert 'names=("NeckCx", "NeckCz", "NeckDia")' in source


def test_end_view_is_the_profiles_third_angle_left_view_on_its_row() -> None:
    """*Front looks from +Z, and the profile runs +Z to the left: the end view
    stands left of the back crown, on the axis row, at the profile's scale."""
    back_end_x = drawing._sheet_x(drawing.BACK_APEX_Z)
    # Leaf neckc2-07af measured the (1.2)'s apex extension at x 78.9 mm.
    assert back_end_x == pytest.approx(0.0789, abs=5e-5)
    assert drawing.END_CENTER[1] == drawing.PRINCIPAL_CENTER[1]
    assert drawing.END_SCALE == drawing.SHEET_SCALE
    assert drawing.VIEW_ANGLE == pytest.approx(-3.141592653589793 / 2.0)
    head_r = spec.HEAD_DIA / 2000.0
    assert drawing.END_CENTER[0] + head_r + 0.020 < back_end_x
    assert drawing.END_CENTER[0] - head_r > drawing.SHEET_INNER_LEFT + 0.020


def _projection_points(*, end_axis=(0.047, 0.170), end_x=(0.0, -0.0075), end_y=(0.0075, 0.0)):
    end = {
        "axis": end_axis,
        "+x": (end_axis[0] + end_x[0], end_axis[1] + end_x[1]),
        "+y": (end_axis[0] + end_y[0], end_axis[1] + end_y[1]),
    }
    profile = {
        "axis": (0.3131, 0.170),
        "+x": (0.3131, 0.1625),
        "left end": (0.0793, 0.170),
    }
    return end, profile


def test_projection_check_passes_the_left_view_and_names_every_other_shape() -> None:
    radius = 0.0075
    end, profile = _projection_points()
    assert drawing.end_view_projection_problems(end, profile, radius=radius) == []
    cases = {
        "off the profile's row": _projection_points(end_axis=(0.047, 0.172)),
        "not left of the profile": _projection_points(end_axis=(0.330, 0.170)),
        # Unturned *Front: model +X runs right, +Y up.
        "model +x maps": _projection_points(end_x=(0.0075, 0.0), end_y=(0.0, 0.0075)),
        # The mirror image (a right view's handedness): +Y away from the profile.
        "model +y maps": _projection_points(end_y=(-0.0075, 0.0)),
    }
    for expected, (end, profile) in cases.items():
        problems = drawing.end_view_projection_problems(end, profile, radius=radius)
        assert any(expected in problem for problem in problems), (expected, problems)


def test_end_view_prints_the_head_and_neck_diameters_and_no_other_view_does() -> None:
    assert set(drawing.END_KEEP) == {"HeadDia", "NeckDia"}
    assert set(drawing.END_KEEP).isdisjoint(drawing.PRINCIPAL_KEEP)
    assert set(drawing.END_KEEP).isdisjoint(drawing.DETAIL_KEEP)
    assert set(drawing.END_KEEP).isdisjoint(drawing.DIMENSION_CALLOUTS)
    assert set(drawing.DETAIL_KEEP) == {"CrossHoleDia", "HeadCapR", "HeadCapSagDim", "HeadLen"}
    assert not hasattr(drawing, "DIAMETER_POSITIONS")
    assert not hasattr(drawing, "DONOR_KEEP")


def test_owner_check_wants_each_diameter_once_on_the_end_view_only() -> None:
    good = {
        "End": ["HeadDia", "NeckDia"],
        "Profile": ["BackCapR", "OverallLen"],
        "Detail A": ["HeadLen"],
    }
    assert drawing.end_view_owner_problems(good, "End") == []
    bad = {
        "on the profile too": {**good, "Profile": ["NeckDia", "OverallLen"]},
        "missing": {**good, "End": ["HeadDia"]},
        "twice": {**good, "End": ["HeadDia", "HeadDia", "NeckDia"]},
        "in the detail instead": {**good, "End": ["NeckDia"], "Detail A": ["HeadDia"]},
    }
    for case, names_by_view in bad.items():
        assert drawing.end_view_owner_problems(names_by_view, "End"), case


def _corner_findings(
    keep: dict[str, tuple[float, float]],
    principal: dict[str, tuple[float, float]] = drawing.PRINCIPAL_KEEP,
    **arrows: tuple[float, float],
) -> list[str]:
    lines, tips = drawing.sheet_corner_ink(keep, principal=principal)
    return drawing.end_view_ink_collisions(
        drawing.end_view_text_boxes(keep, principal),
        drawing.sheet_view_outlines(),
        lines,
        {**tips, **arrows},
    )


def test_end_view_ink_is_clear_of_its_neighbours() -> None:
    assert _corner_findings(drawing.END_KEEP) == []
    drawing.assert_end_view_ink_clear()


def test_end_view_ink_audit_catches_each_collision_class() -> None:
    probe = drawing.END_KEEP["HeadDia"]
    cases = {
        # 07afe186b's Ø10.5, up-right of the view: onto the (1.2)'s extensions.
        "text-on-line": ({"NeckDia": (0.062, 0.188)}, {}),
        # Inside the Ø15 circle.
        "text-on-outline": ({"HeadDia": (0.047, 0.172)}, {}),
        # Onto the other diameter's text.
        "text-on-text": ({"HeadDia": (0.028, 0.160)}, {}),
        # An arrowhead tip 1 mm under the Ø15's text.
        "text-on-arrow": ({}, {"probe arrow": (probe[0], probe[1] - 0.0038)}),
        # Past the sheet's inner border.
        "outside-border": ({"HeadDia": (0.020, 0.196)}, {}),
        # Up-right of the view, the Ø10.5's leader crosses the SR7.3's shoulder.
        "leader-crosses-line": ({"NeckDia": (0.070, 0.200)}, {}),
    }
    for kind, (moves, arrows) in cases.items():
        principal = _LEAF_07AF_PRINCIPAL if kind == "text-on-line" else drawing.PRINCIPAL_KEEP
        findings = _corner_findings({**drawing.END_KEEP, **moves}, principal, **arrows)
        assert any(finding.startswith(kind) for finding in findings), (kind, findings)


def test_the_two_diameter_lines_meet_only_at_the_common_centre() -> None:
    lines, _ = drawing.sheet_corner_ink()
    assert drawing._lines_cross(lines["HeadDia line"], lines["NeckDia line"])
    for name in drawing.END_KEEP:
        for run in ("shoulder", "leader"):
            own = lines[f"{name} {run}"]
            for owner, line in lines.items():
                if not owner.startswith(name):
                    assert not drawing._lines_cross(own, line), (name, run, owner)


# Leaf neckc2-07af (07afe186b): the layout audit's text boxes, the printed text
# inside them, the shoulders and the (1.2)'s apex extension, in sheet mm, for
# the positions that build commanded.
_LEAF_07AF_KEEP = {"HeadDia": (0.030, 0.196), "NeckDia": (0.062, 0.188)}
# The profile callouts' positions then: the (1.2) above the part, the SR7.3
# below-left.
_LEAF_07AF_PRINCIPAL = {
    **drawing.PRINCIPAL_KEEP,
    "BackCapSagDim": (0.055, 0.220),
    "BackCapR": (0.045, 0.140),
}
_LEAF_07AF_AUDIT_BOX = {
    "HeadDia": (22.8, 193.2, 47.9, 196.7),
    "NeckDia": (54.8, 185.2, 79.9, 188.7),
}
_LEAF_07AF_CORE_BOX = {
    "HeadDia": (28.1, 193.2, 40.6, 196.7),
    "NeckDia": (60.1, 185.2, 72.6, 188.7),
}
_LEAF_07AF_SHOULDER = {
    "HeadDia": ((21.5, 193.2), (40.0, 193.2)),
    "NeckDia": ((52.0, 185.2), (70.5, 185.2)),
}
_LEAF_07AF_APEX_EXTENSION = ((78.9, 171.0), (78.9, 215.4))


def _mm(value):
    if isinstance(value, float):
        return value * 1000.0
    return tuple(_mm(item) for item in value)


def test_ink_extents_are_the_boxes_the_leaf_measured() -> None:
    """The module's text, shoulder and (1.2) extension ink reproduce what the
    layout audit measured on neckc2-07af, to its 0.1 mm print."""
    audit = drawing.end_view_text_boxes(_LEAF_07AF_KEEP, _LEAF_07AF_PRINCIPAL)
    lines, _ = drawing.sheet_corner_ink(_LEAF_07AF_KEEP, principal=_LEAF_07AF_PRINCIPAL)
    for name, point in _LEAF_07AF_KEEP.items():
        assert _mm(audit[name]) == pytest.approx(_LEAF_07AF_AUDIT_BOX[name], abs=0.051)
        core = drawing._ink_box(point, drawing.END_DIA_CORE_EXTENT)
        assert _mm(core) == pytest.approx(_LEAF_07AF_CORE_BOX[name], abs=0.051)
        shoulder = sorted(_mm(lines[f"{name} shoulder"]))
        for got, want in zip(shoulder, sorted(_LEAF_07AF_SHOULDER[name]), strict=True):
            assert got == pytest.approx(want, abs=0.051), name
    extension = sorted(_mm(lines["BackCapSagDim apex extension"]), key=lambda p: p[1])
    for got, want in zip(extension, _LEAF_07AF_APEX_EXTENSION, strict=True):
        assert got == pytest.approx(want, abs=0.051)


def test_the_measured_leaf_boxes_fail_and_the_shipped_positions_clear_them() -> None:
    """Plant the leaf's measured boxes: at 07afe186b's positions the Ø10.5 is
    crossed by the (1.2)'s apex extension; moved with END_KEEP, every measured
    box stands 2 mm clear of that line and of every other ink."""
    extension = tuple(
        (x / 1000.0, y / 1000.0) for x, y in _LEAF_07AF_APEX_EXTENSION
    )
    neighbours = {
        name: box
        for name, box in drawing.end_view_text_boxes().items()
        if name not in _LEAF_07AF_AUDIT_BOX
    }

    def planted(keep):
        texts = dict(neighbours)
        for name, box in _LEAF_07AF_AUDIT_BOX.items():
            dx = keep[name][0] - _LEAF_07AF_KEEP[name][0]
            dy = keep[name][1] - _LEAF_07AF_KEEP[name][1]
            texts[name] = (
                box[0] / 1000.0 + dx,
                box[1] / 1000.0 + dy,
                box[2] / 1000.0 + dx,
                box[3] / 1000.0 + dy,
            )
        return texts

    lines, _ = drawing.sheet_corner_ink(_LEAF_07AF_KEEP, principal=_LEAF_07AF_PRINCIPAL)
    lines = {**lines, "BackCapSagDim apex extension": extension}
    leaf = drawing.end_view_ink_collisions(
        planted(_LEAF_07AF_KEEP), drawing.sheet_view_outlines(), lines
    )
    assert any(
        finding.startswith("text-on-line: BackCapSagDim apex extension")
        and "'NeckDia'" in finding
        for finding in leaf
    ), leaf

    shipped = planted(drawing.END_KEEP)
    lines, arrows = drawing.sheet_corner_ink()
    lines = {**lines, "BackCapSagDim apex extension": extension}
    assert (
        drawing.end_view_ink_collisions(
            shipped, drawing.sheet_view_outlines(), lines, arrows
        )
        == []
    )
    for name in drawing.END_KEEP:
        assert extension[0][0] - shipped[name][2] >= drawing.END_LINE_CLEARANCE


def test_end_view_texts_stand_clear_of_the_back_crown_callouts() -> None:
    """The back crown's SR7.3 comes in from the upper left and its (1.2) sits
    under the part: the end-view texts stand left of the crown's witnesses,
    the Ø15 above the view and the Ø10.5 below it, clear of both callouts
    with Main's 2 mm of air."""
    boxes = drawing.end_view_text_boxes()
    apex_x = drawing._sheet_x(drawing.BACK_APEX_Z)
    head_r = spec.HEAD_DIA / 2000.0
    for name in drawing.END_KEEP:
        assert boxes[name][2] < apex_x - drawing.END_LINE_CLEARANCE
        assert drawing._box_gap(boxes[name], boxes["BackCapR"]) >= 0.002
        assert drawing._box_gap(boxes[name], boxes["BackCapSagDim"]) >= 0.002
    assert boxes["HeadDia"][1] > drawing.END_CENTER[1] + head_r
    assert boxes["NeckDia"][3] < drawing.END_CENTER[1] - head_r


def test_only_the_two_diameters_crossing_at_the_end_view_centre_are_excused() -> None:
    from _layout_geometry import Finding

    center_mm = (drawing.END_CENTER[0] * 1000.0, drawing.END_CENTER[1] * 1000.0)

    def crossing(a: str, b: str, at: tuple[float, float], kind: str = "leader-crosses-leader"):
        return Finding(kind=kind, sheet="Sheet1", detail="x", a=a, b=b, at_mm=at)

    drawing._assert_no_text_on_line([crossing("HeadDia", "NeckDia", center_mm)])
    drawing._assert_no_text_on_line(
        [crossing("NeckDia", "HeadDia", (center_mm[0] + 1.0, center_mm[1] - 1.0))]
    )
    blocking = [
        crossing("HeadDia", "NeckDia", (center_mm[0] + 20.0, center_mm[1])),
        crossing("HeadDia", "BackCapR", center_mm),
        crossing("HeadDia", "NeckDia", None),
        crossing("HeadDia", "NeckDia", center_mm, kind="text-on-line"),
    ]
    for finding in blocking:
        with pytest.raises(RuntimeError, match="blocking finding"):
            drawing._assert_no_text_on_line([finding])


# --- Round 4 (neckc3-a652): no leader meets a dimension or extension line ---

# a652's sheet (neckc3-a652, 300 dpi export, 11.811 px/mm), measured off the
# PNG in sheet mm.  An end hidden under other ink (an extension line's start
# under the part or a centre mark, one under an arrowhead) is the model's.
_A652_KEEP = {
    **drawing.PRINCIPAL_KEEP,
    "BackCapSagDim": (0.055, 0.220),
    "BackCapR": (0.045, 0.140),
    "PinHoleDia": (0.250, 0.222),
    "NeckLen": (0.340, 0.100),
}
_A652_RUNS = {
    "PinHoleDia": ("dim", ((232.33, 214.7), (269.16, 214.7)), ((269.16, 214.7), (268.6, 170.8))),
    "PinStationFromHeadRear": (
        "dim",
        ((262.13, 201.5), (313.94, 201.5)),
        ((268.48, 171.0), (268.48, 202.44)),
        ((307.6, 178.5), (307.6, 202.44)),
    ),
    "FrontJournalLen": (
        "dim",
        ((234.78, 185.2), (266.53, 185.2)),
        ((241.17, 175.0), (241.17, 186.3)),
        ((260.14, 175.0), (260.14, 186.3)),
    ),
    "BackCapR": (
        "dim",
        ((37.85, 137.2), (53.72, 137.2)),
        ((53.72, 137.2), (80.86, 164.6)),
        ((80.86, 164.6), (86.1, 170.0)),
    ),
    "BackCapSagDim": (
        "dim",
        ((38.65, 214.42), (86.4, 214.42)),
        ((78.87, 171.0), (78.87, 215.48)),
        ((80.05, 175.0), (80.05, 215.48)),
    ),
    "OverallLen": (
        "dim",
        ((78.82, 74.45), (321.14, 74.45)),
        ((78.87, 169.0), (78.87, 73.32)),
        ((321.06, 169.08), (321.06, 74.17)),
    ),
    "BackRimFromHeadRear": (
        "dim",
        ((80.01, 89.4), (307.59, 89.4)),
        ((80.05, 165.0), (80.05, 88.39)),
        ((307.55, 162.05), (307.55, 88.4)),
    ),
    "FrontJournalFromHeadRear": (
        "dim",
        ((260.1, 127.2), (307.59, 127.2)),
        ((260.14, 165.02), (260.14, 126.2)),
        ((307.55, 162.05), (307.55, 126.2)),
    ),
    "DrumStationFromHeadRear": (
        "dim",
        ((207.8, 117.45), (307.59, 117.45)),
        ((246.0, 165.02), (246.0, 116.45)),
        ((307.55, 162.05), (307.55, 116.45)),
    ),
    "BackJournalFromHeadRear": (
        "dim",
        ((107.53, 112.2), (307.59, 112.2)),
        ((107.65, 165.02), (107.65, 111.17)),
        ((307.55, 162.05), (307.55, 111.2)),
    ),
    "NeckLen": (
        "dim",
        ((296.25, 97.2), (347.05, 97.2)),
        ((296.3, 163.75), (296.3, 96.2)),
        ((307.55, 162.05), (307.55, 96.2)),
    ),
    "BackJournalLen": (
        "dim",
        ((82.3, 140.2), (114.05, 140.2)),
        ((88.65, 165.0), (88.65, 139.2)),
        ((107.65, 165.02), (107.65, 139.19)),
    ),
    # The front land's Ra 1.6: its leader rising to the land and its shoulder.
    "Surface Finish2": (
        "surface-finish",
        ((257.05, 150.0), (257.6, 166.0)),
        ((257.05, 150.0), (264.67, 150.0)),
    ),
}
# The sweep's verdict on a652: Main's two leaders, the front Ra's shoulder and
# the 11.25's run to its text, and nothing else.
_A652_FINDINGS = {
    ("leader-crossing", "PinHoleDia", "PinStationFromHeadRear"),
    ("leader-crossing", "BackCapR", "OverallLen"),
    ("leader-crossing", "BackCapR", "BackRimFromHeadRear"),
    ("leader-crossing", "Surface Finish2", "FrontJournalFromHeadRear"),
    ("line-crossing", "NeckLen", "OverallLen"),
}


def _annotations(runs_by_label):
    from _layout_geometry import AnnotationGeometry, Segment

    return [
        AnnotationGeometry(
            label=label,
            kind=kind,
            owner="Drawing View2",
            segments=tuple(
                Segment(x0 / 1000.0, y0 / 1000.0, x1 / 1000.0, y1 / 1000.0)
                for (x0, y0), (x1, y1) in runs
            ),
        )
        for label, (kind, *runs) in runs_by_label.items()
    ]


def _pairs(findings):
    pairs = set()
    for finding in findings:
        kind, rest = finding.split(": ", 1)
        first = rest.split("'s ", 1)[0]
        second = rest.split(" meets ", 1)[1].split("'s ", 1)[0]
        pairs.add((kind, first, second))
    return pairs


def test_the_a652_sheet_fails_the_leader_rule_on_its_measured_ink() -> None:
    ink = drawing.sheet_ink(_annotations(_A652_RUNS))
    assert _pairs(drawing.leader_line_findings(ink)) == _A652_FINDINGS
    # The neck witness's three crossings are reported, not gated.
    assert len(drawing.expected_crossings_found(ink)) == 3


def test_the_seat_check_raises_on_the_a652_ink_and_names_the_ra_symbol() -> None:
    sheets = [SimpleNamespace(annotations=_annotations(_A652_RUNS))]
    with pytest.raises(RuntimeError) as failure:
        drawing._assert_sheet_leaders_clear(sheets)
    message = str(failure.value)
    assert "PinHoleDia's leader" in message
    assert "surface-finish symbols on the sheet: ['Surface Finish2']" in message


def test_the_model_reproduces_the_a652_crossings_and_clears_them_now() -> None:
    """profile_ink at a652's positions and arrow sides meets the same lines the
    PNG shows (the Ra symbols are no longer modelled: they are a note now);
    at the shipped positions it meets none, and only the three report-only
    neck-witness crossings remain."""
    a652 = drawing.profile_ink(_A652_KEEP, drawing.ARROWS_OUTSIDE)
    expected = {f for f in _A652_FINDINGS if f[1] != "Surface Finish2"}
    assert _pairs(drawing.leader_line_findings(a652)) == expected
    shipped = drawing.profile_ink()
    assert drawing.leader_line_findings(shipped) == []
    assert sorted(drawing.expected_crossings_found(shipped)) == [
        "NeckLen x BackJournalFromHeadRear: the neck witness drops through the 199.9",
        "NeckLen x DrumStationFromHeadRear: the neck witness drops through the 61.55",
        "NeckLen x FrontJournalFromHeadRear: the neck witness drops through the 47.4",
    ]
    drawing.assert_profile_leaders_clear()


def test_the_model_matches_the_a652_ink_it_was_measured_from() -> None:
    """Every modelled stroke at a652's positions lies on the stroke the PNG
    shows, to 1.2 mm (arrowheads hide an extension line's last 0-1 mm)."""
    a652 = drawing.profile_ink(_A652_KEEP, drawing.ARROWS_OUTSIDE)
    for name, (_role, runs) in a652.items():
        measured = [
            tuple((x / 1000.0, y / 1000.0) for x, y in run) for run in _A652_RUNS[name][1:]
        ]
        for run in runs:
            if name in ("PinHoleDia", "BackCapR") and run is runs[-1]:
                continue  # the diameter's far side / the radius's run to its centre
            best = min(
                max(
                    min(math.dist(end, other) for other in candidate)
                    for end in run
                )
                for candidate in measured
            )
            assert best <= 0.0012, (name, run, best)


def test_leaders_get_no_allowance_a_t_junction_or_an_overlap_is_a_crossing() -> None:
    line = ((0.100, 0.100), (0.100, 0.150))
    cases = {
        "crossing": ((0.090, 0.120), (0.110, 0.125)),
        "t-junction": ((0.090, 0.120), (0.100, 0.120)),
        "lying along": ((0.100, 0.110), (0.100, 0.130)),
    }
    for case, leader in cases.items():
        ink = {"Lead": ("leader", [leader]), "Dim": ("linear", [line])}
        assert drawing.leader_line_findings(ink), case
    clear = {"Lead": ("leader", [((0.090, 0.120), (0.0995, 0.120))]), "Dim": ("linear", [line])}
    assert drawing.leader_line_findings(clear) == []
    assert drawing.LEADER_TOUCHING == {}


def test_only_named_witnesses_may_be_shared_and_only_along_the_witness() -> None:
    apex = ((0.0789, 0.169), (0.0789, 0.073))
    shared = ((0.0789, 0.169), (0.0789, 0.127))
    ink = {
        "OverallLen": ("linear", [apex]),
        "BackCapSagDim": ("linear", [shared, ((0.0386, 0.128), (0.0864, 0.128))]),
    }
    assert drawing.leader_line_findings(ink) == []
    unnamed = {"OverallLen": ink["OverallLen"], "HeadLen": ink["BackCapSagDim"]}
    assert drawing.leader_line_findings(unnamed)
    # A named pair still may not meet off the witness they share.
    stray = {
        "OverallLen": ("linear", [apex, ((0.060, 0.100), (0.090, 0.100))]),
        "BackCapSagDim": ("linear", [shared, ((0.070, 0.090), (0.070, 0.110))]),
    }
    assert drawing.leader_line_findings(stray)
    assert set(drawing.SHARED_WITNESSES["back crown apex"]) == {"BackCapSagDim", "OverallLen"}
    assert set(drawing.SHARED_WITNESSES["back crown root"]) == {
        "BackCapSagDim",
        "BackRimFromHeadRear",
    }


def test_the_expected_crossings_cover_only_the_neck_witness_through_a_line() -> None:
    neck = ((0.2963, 0.16375), (0.2963, 0.0962))
    row = ((0.2601, 0.1272), (0.30759, 0.1272))
    ink = {"NeckLen": ("linear", [neck]), "FrontJournalFromHeadRear": ("linear", [row])}
    assert drawing.leader_line_findings(ink) == []
    # The same pair meeting any other way is a finding.
    swapped = {
        "NeckLen": ("linear", [((0.280, 0.130), (0.300, 0.130))]),
        "FrontJournalFromHeadRear": ("linear", [((0.290, 0.140), (0.290, 0.120))]),
    }
    assert drawing.leader_line_findings(swapped)


def test_sr73_lands_on_the_crown_at_its_radius_inside_the_arc() -> None:
    center = drawing.BACK_CAP_CENTER
    assert center[0] == pytest.approx(drawing._sheet_x(drawing.BACK_APEX_Z - spec.BACK_CAP_R))
    assert drawing.BACK_CAP_R_M == pytest.approx(spec.BACK_CAP_R / 1000.0)
    assert drawing.BACK_CAP_HALF_ANGLE_DEG == pytest.approx(33.4, abs=0.05)
    landing = drawing.BACK_CAP_R_LANDING
    assert math.dist(landing, center) == pytest.approx(drawing.BACK_CAP_R_M, abs=1e-9)
    assert drawing.back_crown_landing_problems(center, landing) == []
    # Under the (1.2)'s old apex extension (x 78.9 from y 171.0 up) it would
    # have to land within 7.8° of the axis; at 25° it lands 3.1 mm up the crown,
    # with nothing standing over it once the (1.2) is under the part.
    assert landing[1] - drawing.PROFILE_AXIS_Y == pytest.approx(0.00307, abs=5e-5)
    assert 20.0 <= drawing.BACK_CAP_R_LANDING_DEG <= drawing.BACK_CAP_HALF_ANGLE_DEG - 5.0
    # a652's 45° leader landed on the arc's extension, past the Ø8 flank.
    a652 = drawing._on_radius(center, drawing.BACK_CAP_R_M, 45.0)
    assert any(
        "outside the crown" in problem
        for problem in drawing.back_crown_landing_problems(center, a652)
    )


def test_the_seat_landing_check_passes_the_model_and_fails_a652() -> None:
    center = drawing.BACK_CAP_CENTER
    _role, runs = drawing.profile_ink()["BackCapR"]
    shipped = {"BackCapR": ("dim", *(tuple(tuple(v * 1000 for v in p) for p in run) for run in runs))}
    drawing._assert_back_crown_radius_lands([SimpleNamespace(annotations=_annotations(shipped))], center)
    a652 = {"BackCapR": _A652_RUNS["BackCapR"]}
    with pytest.raises(RuntimeError, match="outside the crown"):
        drawing._assert_back_crown_radius_lands(
            [SimpleNamespace(annotations=_annotations(a652))], (0.0861, 0.170)
        )
    with pytest.raises(RuntimeError, match="no ink"):
        drawing._assert_back_crown_radius_lands([SimpleNamespace(annotations=[])], center)


# Glyph boxes measured on the a652 PNG (sheet mm): the 39.0 / COLLAR PIN, the
# 227.5 block's text, the BOND ZONE block, and the front land's "19.0".
_A652_TEXT = {
    "PinStationFromHeadRear": (274.74, 202.44, 300.99, 211.41),
    "BackRimFromHeadRear": (171.4, 90.09, 264.5, 99.4),
    "BondZoneDia": (194.99, 183.64, 221.57, 197.19),
    "FrontJournalLen": (247.0, 186.1, 256.29, 189.65),
}
GLYPH_CLEARANCE = 0.002


def _box(point, extent):
    return drawing._ink_box(point, extent)


def _mm_box(box):
    return tuple(v / 1000.0 for v in box)


def _gap(first, second):
    """Closest approach of two strokes (0 when they meet)."""
    if _drawing_leaders.segments_cross(first, second):
        return 0.0
    return min(
        *(_drawing_leaders.distance_to_point(second, end) for end in first),
        *(_drawing_leaders.distance_to_point(first, end) for end in second),
    )


def _box_to_line(box, line):
    x0, y0, x1, y1 = box
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    edges = list(zip(corners, corners[1:] + corners[:1]))
    if drawing._line_meets_box(line, box):
        return 0.0
    return min(_gap(edge, line) for edge in edges)


def test_moved_texts_keep_two_mm_of_air_to_every_neighbour() -> None:
    keep = drawing.PRINCIPAL_KEEP
    sr = _box(keep["BackCapR"], drawing.BACK_CAP_R_TEXT_EXTENT)
    sag = _box(keep["BackCapSagDim"], drawing.BACK_CAP_SAG_TEXT_EXTENT)
    pin = _box(keep["PinHoleDia"], drawing.PIN_HOLE_TEXT_EXTENT)
    neck_len = _box(keep["NeckLen"], (0.00514, 0.00179, 0.00553, 0.0016))
    end_texts = drawing.end_view_text_boxes()
    end_lines, end_arrows = drawing.sheet_corner_ink()
    outlines = drawing.sheet_view_outlines()
    # SR7.3: above-right of the end view, clear of the Ø15's text, leader and
    # arrow, the end view's outline and the profile.
    for name in ("HeadDia", "NeckDia"):
        assert drawing._box_gap(sr, end_texts[name]) >= GLYPH_CLEARANCE
        for run in ("shoulder", "leader", "line"):
            assert _box_to_line(sr, end_lines[f"{name} {run}"]) >= GLYPH_CLEARANCE, (name, run)
    for tip in end_arrows.values():
        assert not drawing._in_box(tip, drawing._grown(sr, GLYPH_CLEARANCE))
    for outline in ("end view", "profile"):
        assert drawing._box_gap(sr, outlines[outline]) >= GLYPH_CLEARANCE
    # (1.2) BACK CROWN under the part: clear of the end view's texts, the
    # SR7.3 and the back land's 19.0 row, text and witness.
    _role, back_len = drawing.profile_ink()["BackJournalLen"]
    _role, sag_runs = drawing.profile_ink()["BackCapSagDim"]
    for name in ("HeadDia", "NeckDia"):
        assert drawing._box_gap(sag, end_texts[name]) >= GLYPH_CLEARANCE
    assert drawing._box_gap(sag, sr) >= GLYPH_CLEARANCE
    assert drawing._box_gap(sag, outlines["end view"]) >= GLYPH_CLEARANCE
    for line in back_len:
        assert _box_to_line(sag, line) >= GLYPH_CLEARANCE
        for run in sag_runs:
            assert _gap(run, line) >= GLYPH_CLEARANCE
    # The pin hole's callout: clear of the 39.0, the bond zone and the 19.0.
    for name in ("PinStationFromHeadRear", "BondZoneDia", "FrontJournalLen"):
        assert drawing._box_gap(pin, _mm_box(_A652_TEXT[name])) >= GLYPH_CLEARANCE, name
    # The 11.25: clear of the 227.5 block and of the (242.2)'s front-apex witness.
    assert drawing._box_gap(neck_len, _mm_box(_A652_TEXT["BackRimFromHeadRear"])) >= GLYPH_CLEARANCE
    assert drawing._sheet_x(drawing.FRONT_APEX_Z) - neck_len[2] >= GLYPH_CLEARANCE


def test_the_pin_hole_leader_clears_the_39_tail_and_the_19_witness_by_two_mm() -> None:
    ink = drawing.profile_ink()
    _role, (shoulder, leader, _through) = ink["PinHoleDia"]
    _role, (pin_line, pin_extension, _head) = ink["PinStationFromHeadRear"]
    _role, (land_line, _crown_end, land_head_end) = ink["FrontJournalLen"]
    assert _gap(leader, pin_line) >= GLYPH_CLEARANCE
    assert _gap(shoulder, pin_line) >= GLYPH_CLEARANCE
    assert _gap(leader, land_head_end) >= GLYPH_CLEARANCE
    assert _gap(leader, land_line) >= GLYPH_CLEARANCE
    # It lands on the hole's rim along the radius, left of the station witness.
    (_bend, tip) = leader
    assert math.dist(tip, drawing.PIN_HOLE_CENTER) == pytest.approx(drawing.PIN_HOLE_DIA / 2000.0)
    assert tip[0] < pin_extension[0][0]
    assert drawing.FRONT_LAND_ARROWS_INSIDE == ("FrontJournalLen",)
    assert drawing.DIM_ARROWS_INSIDE == 0


def test_the_build_stands_the_19_arrows_inside_and_gates_the_sheet() -> None:
    source = inspect.getsource(drawing.build)
    assert "_set_arrow_sides(" in source
    assert "FRONT_LAND_ARROWS_INSIDE" in source
    assert "_assert_sheet_leaders_clear(sheets)" in source
    assert "_assert_back_crown_radius_lands(" in source
    assert "assert_profile_leaders_clear()" in source
    assert "add_surface_finish" not in inspect.getsource(drawing)


def test_every_ra_was_a_journal_land_and_the_note_carries_their_one_grade() -> None:
    """Main's round-4 ruling (iii): the two journal-land Ra 1.6 symbols become
    one general note.  Before, the sheet drew one symbol per SURFACE_FINISHES
    control; every control is a journal land at one grade, and the note prints
    that grade through the controls' own roughness_ra."""
    keys = {control.key for control in spec.SURFACE_FINISHES}
    assert keys == {"front_journal", "back_journal"}
    lands = {"front_journal": spec.FRONT_JOURNAL_Z, "back_journal": spec.BACK_JOURNAL_Z}
    for control in spec.SURFACE_FINISHES:
        assert lands[control.key] < control.face.contains_z_mm < lands[control.key] + spec.JOURNAL_LEN
        assert control.face.diameter_mm == spec.SHAFT_DIA
    grades = {control.roughness_ra for control in spec.SURFACE_FINISHES}
    assert grades == {_surface_finish.ra(_surface_finish.MACHINED_UM)}
    assert spec.JOURNAL_LANDS_FINISH_NOTE == f"JOURNAL LANDS Ra {grades.pop()}."
    assert spec.JOURNAL_LANDS_FINISH_NOTE in spec.DRAWING_NOTES.splitlines()
    assert not hasattr(drawing, "JOURNAL_FINISHES")
    # The bond zone keeps its own diameter callout.
    assert "BondZoneDia" in drawing.PRINCIPAL_KEEP
    assert drawing.DIMENSION_CALLOUTS["BondZoneDia"] == "BOND ZONE"


# --- Reference witnesses are selected by identity, not by a screen pick ------


class _FakeSegment:
    """A part sketch line: its model ends (m), selectable into a view."""

    def __init__(self, seat, name, model_ends, *, construction=True, selectable=True):
        self.seat = seat
        self.name = name
        self.model_ends = model_ends
        self.construction = construction
        self.selectable = selectable

    @property
    def ConstructionGeometry(self):  # noqa: N802 - COM member name
        return self.construction

    def GetName(self):  # noqa: N802
        return self.name

    def GetType(self):  # noqa: N802
        return drawing.SW_SKETCH_LINE

    def GetLength(self):  # noqa: N802
        (x0, y0, z0), (x1, y1, z1) = self.model_ends
        return ((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5

    def Select4(self, append, data):  # noqa: N802
        if not self.selectable or data.View is not self.seat.view:
            return False
        self.seat.selected = [self]
        return True


class _FakeSeat:
    """The profile view, its part's reference sketches, and one decoy: the
    227.5 mm BackRimReference axis a midpoint screen pick returned on the
    56fa631bc leaf."""

    def __init__(self, *, witness_select4=True, qualified_names=True, extra=()):
        from types import SimpleNamespace

        mm = 0.001
        flank = spec.SHAFT_DIA / 2000.0
        head_rear = spec.HEAD_REAR_Z * mm
        self.selected = []
        self.colored = []
        self.qualified_names = qualified_names
        self.sketches = {}
        for sketch_name, (z0, z1) in drawing.REFERENCE_WITNESSES.items():
            axis = _FakeSegment(self, "Line1", ((0.0, 0.0, head_rear), (0.0, 0.0, z1 * mm)))
            witness = _FakeSegment(
                self,
                "Line2",
                ((flank, 0.0, z1 * mm), (flank, 0.0, z0 * mm)),
                selectable=witness_select4,
            )
            self.sketches[sketch_name] = [axis, witness, *extra]
        self.decoy = _FakeSegment(
            self,
            "Line1",
            ((0.0, 0.0, head_rear), (0.0, 0.0, spec.SHAFT_LEN * mm)),
        )
        seat = self

        class Part:
            def FeatureByName(self, name):  # noqa: N802
                if name not in seat.sketches:
                    return None
                sketch = SimpleNamespace(GetSketchSegments=lambda: tuple(seat.sketches[name]))
                return SimpleNamespace(GetSpecificFeature2=lambda: sketch, Visible=2)

        self.view = SimpleNamespace(
            ReferencedDocument=Part(),
            GetName2=lambda: "Drawing View2",
            UpdateViewDisplayGeometry=lambda: None,
            RootDrawingComponent2=lambda _child: SimpleNamespace(Name="pinion-arbor-2"),
        )

        class Manager_:
            def CreateSelectData(self):  # noqa: N802
                return SimpleNamespace(View=None)

            def GetSelectedObjectCount2(self, _mark):  # noqa: N802
                return len(seat.selected)

            def GetSelectedObjectType3(self, _index, _mark):  # noqa: N802
                return drawing.SW_SEL_EXT_SKETCH_SEGS

            def GetSelectedObject6(self, _index, _mark):  # noqa: N802
                return seat.selected[0]

        class Ext:
            def SelectByID2(self, name, kind, x, y, z, append, mark, callout, option):  # noqa: N802
                if kind != "EXTSKETCHSEGMENT":
                    return False
                if not name:
                    # Any screen pick on the flank resolves to the decoy axis.
                    seat.selected = [seat.decoy]
                    return True
                if not seat.qualified_names:
                    return False
                line, sketch_name, component, view = name.split("@")
                if (component, view) != ("pinion-arbor-2", "Drawing View2"):
                    return False
                matches = [s for s in seat.sketches.get(sketch_name, ()) if s.name == line]
                seat.selected = matches[:1]
                return bool(matches)

        class Draw:
            SelectionManager = Manager_()
            Extension = Ext()

            def ActivateView(self, name):  # noqa: N802
                return name == "Drawing View2"

            def ClearSelection2(self, _all):  # noqa: N802
                seat.selected = []

            def SetLineColor(self, color):  # noqa: N802
                seat.colored.append((tuple(seat.selected), color))

            def EditRebuild3(self):  # noqa: N802
                return True

        self.adapter = SimpleNamespace(
            currentModel=Draw(),
            _get_attr_or_call=lambda obj, name: (
                getattr(obj, name)() if callable(getattr(obj, name)) else getattr(obj, name)
            ),
        )


def _profile_projection(_adapter, _view, xyz, *, label):
    """The 1:1 profile: model z runs left from x 0.200 at z 106.725, +x down."""
    x, _y, z = xyz
    return (
        drawing.PRINCIPAL_CENTER[0] - (z * 1000.0 - drawing.MODEL_Z_AT_SHEET_ORIGIN_X) / 1000.0,
        drawing.PRINCIPAL_CENTER[1] - x,
    )


@pytest.fixture
def witness_seat(monkeypatch):
    monkeypatch.setattr(drawing, "model_point_in_view", _profile_projection)
    monkeypatch.setattr(
        drawing,
        "_sketch_line_model_ends",
        lambda _adapter, _sketch, segment: segment.model_ends,
        raising=False,
    )
    return _FakeSeat


def test_witnesses_are_selected_by_identity_past_a_decoy_axis(witness_seat) -> None:
    """56fa631bc's midpoint pick returned the 227.5 mm BackRimReference axis;
    the witness is now read off its own sketch and selected as itself."""
    seat = witness_seat()
    spans = drawing._blacken_reference_witnesses(seat.adapter, seat.view)
    assert set(spans) == set(drawing.REFERENCE_WITNESSES)
    witnesses = [seat.sketches[name][1] for name in drawing.REFERENCE_WITNESSES]
    assert seat.colored == [((witness,), drawing.REFERENCE_WITNESS_COLOR) for witness in witnesses]
    assert all(seat.decoy not in selected for selected, _ in seat.colored)
    for name, (z0, z1) in drawing.REFERENCE_WITNESSES.items():
        (x0, y0), (x1, y1) = spans[name]
        assert y0 == pytest.approx(drawing.PRINCIPAL_CENTER[1] - spec.SHAFT_DIA / 2000.0)
        assert abs(x1 - x0) == pytest.approx((z1 - z0) / 1000.0)


def test_witness_selection_falls_back_to_its_qualified_name(witness_seat) -> None:
    seat = witness_seat(witness_select4=False)
    drawing._blacken_reference_witnesses(seat.adapter, seat.view)
    assert [selected[0].name for selected, _ in seat.colored] == ["Line2", "Line2"]


def test_an_unselectable_witness_fails_naming_every_attempt(witness_seat) -> None:
    seat = witness_seat(witness_select4=False, qualified_names=False)
    with pytest.raises(RuntimeError, match="could not be selected by identity") as error:
        drawing._blacken_reference_witnesses(seat.adapter, seat.view)
    assert "Select4 in view: returned False" in str(error.value)
    assert "SelectByID2 'Line2@DrumStationReference@pinion-arbor-2@Drawing View2'" in str(
        error.value
    )
    assert seat.colored == []


def test_no_or_two_matching_lines_fail_naming_the_candidates(witness_seat) -> None:
    seat = witness_seat()
    for segments in seat.sketches.values():
        segments[1].construction = False
    with pytest.raises(RuntimeError, match=r"visibility 2\): 0 of 2 sketch lines match") as e:
        drawing._blacken_reference_witnesses(seat.adapter, seat.view)
    assert "Line2 1.000 mm construction=False" in str(e.value)
    assert "Line1 61.550 mm" in str(e.value)

    seat = witness_seat()
    twin = seat.sketches["DrumStationReference"][1]
    seat.sketches["DrumStationReference"].append(
        _FakeSegment(seat, "Line3", tuple(reversed(twin.model_ends)))
    )
    with pytest.raises(RuntimeError, match=r"2 of 3 sketch lines match"):
        drawing._blacken_reference_witnesses(seat.adapter, seat.view)
    assert seat.colored == []


def test_witness_ranges_are_the_parts_own_flank_lines() -> None:
    """The part authors each witness on a Top-plane sketch, v = -z: the drum
    station's from its station 1 mm back towards the head, the bond zone's
    from its station 4 mm away from it.  Both drawing ranges are that line."""
    drum = drawing.REFERENCE_WITNESSES["DrumStationReference"]
    end_v = -(spec.HEAD_REAR_Z + spec.DRUM_STATION)
    assert sorted(-v for v in (end_v, end_v + part.DRUM_STATION_POINT_LEN)) == pytest.approx(
        list(drum)
    )
    bond = drawing.REFERENCE_WITNESSES["BondZoneReference"]
    end_v = -spec.BOND_ZONE_DIA_Z
    assert sorted(-v for v in (end_v, end_v - part.BOND_ZONE_WITNESS_LEN)) == pytest.approx(
        list(bond)
    )
    assert part.DRUM_STATION_POINT_X == pytest.approx(spec.SHAFT_DIA / 2.0)
