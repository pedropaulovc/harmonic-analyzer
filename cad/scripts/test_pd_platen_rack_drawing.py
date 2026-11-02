"""Offline manufacturing contracts for the composite platen-rack package."""

from __future__ import annotations

import asyncio
import importlib
import math
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import _config
import _gear_quality as quality

import build_pd_platen_rack as builder
import draw_pd_platen_rack as drawing
import pd_platen_rack_spec as spec
import pd_transgear_feed_pinion_spec as feed
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
)
from _test_stubbed_build import offline_adapter, stub_seat
from _drawing_registry import DrawingLayout
from _printed_tolerance import printed_deviations
from pd_platen_spec import PLATE_WIDTH


def test_rack_form_comes_from_the_feed_spec_without_profile_shift() -> None:
    assert spec.DP == feed.DIAMETRAL_PITCH
    assert spec.PA_DEG == feed.PRESSURE_ANGLE_DEG
    assert spec.MODULE_MM == feed.MODULE_MM
    assert spec.PITCH == pytest.approx(math.pi * feed.MODULE_MM)
    assert spec.ADDENDUM == feed.MODULE_MM
    assert spec.DEDENDUM == feed.DEDENDUM_FACTOR * feed.MODULE_MM
    assert spec.PITCH_LINE_Y == spec.BAR_HEIGHT - spec.ADDENDUM
    assert spec.ROOT_Y == spec.PITCH_LINE_Y - spec.DEDENDUM
    assert spec.half_width(spec.PITCH_LINE_Y) == pytest.approx(spec.PITCH / 4.0)
    assert spec.half_width(spec.BAR_HEIGHT) - spec.half_width(
        spec.ROOT_Y
    ) == pytest.approx(
        (spec.ADDENDUM + spec.DEDENDUM)
        * math.tan(math.radians(feed.PRESSURE_ANGLE_DEG))
    )
    assert spec.GAP_COUNT == math.floor(spec.BAR_LENGTH / spec.PITCH)
    assert spec.FIRST_GAP_X == pytest.approx(spec.PITCH / 2.0)
    assert builder.half_width is spec.half_width


def test_square_strip_is_centred_on_the_backer_and_ends_flush() -> None:
    assert spec.BAR_LENGTH == PLATE_WIDTH
    assert spec.RACK_HEIGHT == pytest.approx(3.0 / 16.0 * feed.MM_PER_IN)
    assert spec.RACK_THICKNESS == spec.RACK_HEIGHT
    assert spec.BACKER_HEIGHT + spec.RACK_HEIGHT == pytest.approx(spec.BAR_HEIGHT)
    assert 0.0 < spec.RACK_Z0 < spec.BAR_THICKNESS
    assert spec.RACK_Z0 + spec.RACK_THICKNESS < spec.BAR_THICKNESS
    assert spec.RACK_Z0 == pytest.approx(
        spec.BAR_THICKNESS - spec.RACK_Z0 - spec.RACK_THICKNESS
    )
    assert spec.BACKER_HEIGHT < spec.ROOT_Y < spec.BAR_HEIGHT
    # The nominal CAD end keeps a crest for its section view; this does not
    # turn the bought strip's physical end phase into a cutting requirement.
    assert spec.FIRST_GAP_X - spec.half_width(spec.BAR_HEIGHT) > 0.0
    last_gap = spec.FIRST_GAP_X + (spec.GAP_COUNT - 1) * spec.PITCH
    assert last_gap + spec.half_width(spec.BAR_HEIGHT) < spec.BAR_LENGTH
    for name in (
        "BAR_LENGTH",
        "BAR_HEIGHT",
        "BAR_THICKNESS",
        "RACK_HEIGHT",
        "RACK_THICKNESS",
        "BACKER_HEIGHT",
        "RACK_Z0",
        "ROOT_Y",
        "GAP_COUNT",
    ):
        assert getattr(builder, name) == getattr(spec, name), name


def test_composite_sizes_have_native_controls_and_stock_references() -> None:
    assert spec.DRAWING_DIMENSIONS["EndStockProfile"] == {
        "RackDepth",
        "RackHeight",
        "RackInset",
        "SeamHeight",
    }
    assert spec.DRAWING_NOMINALS_MM == {
        "Length": spec.BAR_LENGTH,
        "BackerDepth": spec.BAR_THICKNESS,
        "RackDepth": spec.RACK_THICKNESS,
        "RackHeight": spec.RACK_HEIGHT,
        "RackInset": spec.RACK_Z0,
        "SeamHeight": spec.BACKER_HEIGHT,
        "OverallHeight": spec.BAR_HEIGHT,
    }
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    kept = set(drawing.FRONT_KEEP) | set(drawing.END_KEEP)
    assert marked == kept == spec.DRAWING_NOMINALS_MM.keys()
    assert not (set(drawing.FRONT_KEEP) & set(drawing.END_KEEP))
    assert builder.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert builder.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert drawing.DRAWING_PRECISION_BY_NAME is spec.DRAWING_PRECISION_BY_NAME
    assert marked == spec.DRAWING_PRECISION_BY_NAME.keys()
    assert spec.DRAWING_REFERENCE_DIMENSIONS == {
        "RackDepth", "RackHeight", "OverallHeight",
    }
    assert "Length" not in spec.DRAWING_REFERENCE_DIMENSIONS
    assert drawing.DRAWING_REFERENCE_DIMENSIONS is spec.DRAWING_REFERENCE_DIMENSIONS
    assert builder.DRAWING_REFERENCE_DIMENSIONS is spec.DRAWING_REFERENCE_DIMENSIONS


def test_the_retired_first_gap_witness_is_neither_dimensioned_nor_kept() -> None:
    assert "FirstGap" not in spec.DRAWING_NOMINALS_MM
    assert "FirstGap" not in drawing.FRONT_KEEP


_SOLID_FEATURES = (
    "create_extrusion", "create_cut_extrude", "create_plane", "create_revolve",
    "linear_pattern_feature",
)


def test_end_and_overall_witnesses_carry_the_sheet_sizes_and_add_no_solid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The real _drawing_witnesses, seat stubbed: the end-stock rectangle and
    # the overall-height line are sketches whose dimensions are the ones the
    # sheet imports, named on their features, then blanked; nothing solid.
    seat = stub_seat(monkeypatch, builder, keep=("_drawing_witnesses",))
    sketches: list = []

    class Dims:
        def __init__(self) -> None:
            self.names: list[str] = []
            self.feature = None
            sketches.append(self)

        def record(self, name, _drive=None) -> None:
            self.names.append(name)

        def apply(self, _adapter, feature):
            self.feature = feature
            return []

    monkeypatch.setattr(builder, "SketchDims", Dims)
    seat.define_rectilinear_chain.side_effect = (
        lambda *_args, dims, names, **_kwargs: dims.names.extend(names)
    )
    seat.name_last_feature.side_effect = lambda _adapter, name: name
    adapter = offline_adapter()
    asyncio.run(builder._drawing_witnesses(adapter))

    witnesses = ("EndStockProfile", "OverallHeightReference")
    assert {sketch.feature: set(sketch.names) for sketch in sketches} == {
        feature: set(spec.DRAWING_DIMENSIONS[feature]) for feature in witnesses
    }
    (between,) = seat.dimension_between.call_args_list
    start, end = between.args[1:3]
    assert start.endswith(".start") and end == start.removesuffix(".start") + ".end"
    assert between.args[3:5] == ("vertical_distance", builder.BAR_HEIGHT)
    names = [name for name, _args, _kwargs in seat.mock_calls]
    (blanked,) = seat.blank_reference_sketches.call_args_list
    assert set(blanked.args[1]) == set(witnesses)
    named = [
        args[1] for name, args, _kwargs in seat.mock_calls if name == "name_last_feature"
    ]
    assert named == list(witnesses)
    assert names.index("blank_reference_sketches") > max(
        k for k, name in enumerate(names) if name == "name_last_feature"
    )
    for method in _SOLID_FEATURES:
        getattr(adapter, method).assert_not_awaited()


def test_build_marks_the_sheet_dimensions_and_saves_a_simplified_plain_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seat = stub_seat(monkeypatch, builder)
    seat.name_last_feature.side_effect = lambda _adapter, name: name
    seat._named_dimension.side_effect = lambda *_args: (MagicMock(), MagicMock())
    adapter = offline_adapter()
    seat.attach_mock(adapter, "adapter")
    saved = asyncio.run(builder.build(adapter))

    calls = seat.mock_calls
    names = [name for name, _args, _kwargs in calls]

    def named_after(method: str) -> str:
        at = len(names) - 1 - names[::-1].index(f"adapter.{method}")
        return next(args[1] for name, args, _ in calls[at:] if name == "name_last_feature")

    # The witnesses follow the patterned teeth; the driven model is re-checked.
    assert names.index("_drawing_witnesses") > names.index("adapter.linear_pattern_feature")
    last_rebuild = len(names) - 1 - names[::-1].index("force_rebuild")
    assert "volume_check" in names[last_rebuild:]
    # Drawing precision, then a clean slate, then exactly the sheet's marks.
    precision = names.index("apply_drawing_precision")
    cleared = names.index("clear_dimensions_for_drawing")
    marks = [k for k, name in enumerate(names) if name == "mark_dimensions_for_drawing"]
    assert precision < cleared < min(marks)
    assert {
        (calls[k].args[1], frozenset(calls[k].args[2])) for k in marks
    } == {
        (feature, frozenset(dimensions))
        for feature, dimensions in spec.DRAWING_DIMENSIONS.items()
    }
    # The simplified configuration suppresses the seed gap and its pattern.
    (simplified,) = seat.save_simplified_part.await_args_list
    assert simplified.args[1] == builder.PART_NAME
    assert tuple(simplified.args[2]) == (
        named_after("create_cut_extrude"), named_after("linear_pattern_feature")
    )
    assert saved is seat.save_simplified_part.return_value


def test_sheet_has_aligned_clean_views_and_a_legible_stepped_end() -> None:
    assert drawing.SPEC.layout == DrawingLayout.LANDSCAPE
    assert drawing.SPEC.source_kind == "part"
    assert drawing.SPEC.part == "pd_platen_rack"
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.END_SCALE[0] / drawing.END_SCALE[1] > (
        drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    )
    assert drawing.ISO_SCALE == (1, 2)
    assert drawing.curate_view_dimensions.__module__ == "_drawing_hidden_sketches"
    assert "draw_pd_platen_rack.py" in PRECISION_MIGRATED_DRAWINGS
    assert not drawing_specification_violations(
        Path(drawing.__file__).read_text(encoding="utf-8"),
        filename="draw_pd_platen_rack.py",
    )


def test_purchase_and_joint_properties_do_not_prescribe_tooth_manufacture() -> None:
    assert builder.GEAR_DATA is spec.GEAR_DATA
    assert builder.PURCHASED_RACK_NOTE is spec.PURCHASED_RACK_NOTE
    assert spec.PURCHASED_RACK_NOTE in spec.GEAR_DATA
    assert builder.DRAWING_NOTES is spec.DRAWING_NOTES
    assert builder.MATERIAL == spec.PURCHASED_RACK_MATERIAL
    assert spec.PURCHASED_RACK_DP == feed.DIAMETRAL_PITCH
    assert spec.PURCHASED_RACK_PA_DEG == feed.PRESSURE_ANGLE_DEG
    assert spec.PURCHASED_RACK_SUPPLIER in spec.PURCHASED_RACK_NOTE
    assert spec.PURCHASED_RACK_SKU in spec.PURCHASED_RACK_NOTE
    assert f"{spec.PURCHASED_RACK_LENGTH_IN:g} IN" in spec.PURCHASED_RACK_NOTE
    assert f"{feed.DIAMETRAL_PITCH:g} DP" in spec.GEAR_DATA
    assert f"{feed.PRESSURE_ANGLE_DEG:g}\N{DEGREE SIGN} PA" in spec.GEAR_DATA
    assert spec.PURCHASED_RACK_MATERIAL.upper() not in spec.GEAR_DATA.upper()
    assert "SOFT-SOLDERED" in spec.DRAWING_NOTES
    assert "PHASE NOT CONTROLLED" in spec.DRAWING_NOTES
    assert "SET MESH AT ASSEMBLY" in spec.DRAWING_NOTES
    assert sum(len(block.splitlines()) for block in (spec.GEAR_DATA, spec.DRAWING_NOTES)) <= 4
    text = "\n".join(
        (spec.PURCHASED_RACK_NOTE, spec.GEAR_DATA, spec.DRAWING_NOTES)
    ).upper()
    for claim in (
        "FORM CUTTER", "RACK FORM", "135T", "STOCKED", "DROP-IN", "BRAZE",
        "WAIVER", "ACCEPTED", "EXCEPTION",
    ):
        assert claim not in text
    assert not any(char.isdigit() for char in spec.DRAWING_NOTES)
    row = _config.parts(builder.PART_NAME)
    assert row["finish"] == "rack as purchased; backer and solder fillet cleaned"
    installation = row["installation_notes"]
    lines = installation.splitlines()
    assert len(lines) <= 4 and all(len(line) <= 70 for line in lines)
    assert "SOFT-SOLDER TO BACKER" in installation
    assert "SET MESH AT ASSEMBLY" in installation
    for method in ("WIRE", "SECANT", "INDICATOR", " U +/-"):
        assert method not in installation
    # The purchased rack's flanks are as purchased: neither the sheet nor the
    # installation note adds a flank requirement, and the assembly's rack step
    # carries no measuring method.
    assert "FLANK" not in installation
    assembly = importlib.import_module("draw_pd_paper_drive_assembly")
    rack_setup = importlib.import_module("paper_drive_rack_setup")
    soldered = assembly._step_text(
        operating_domain=rack_setup.feed_rack_operating_domain()
    )["rack-soldered"]
    for method in ("WIRE", "SECANT", "INDICATOR", "U +/-"):
        assert method not in soldered


def test_rack_index_and_face_lead_fit_the_feed_opposite_flank_budget() -> None:
    """tolerances.yaml derivation: with two pairs in contact the second
    pair's clearance is the set datum backlash less every lateral term."""
    import paper_drive_geom

    closing = quality.rack_pitch_index_deviation_mm() + paper_drive_geom.feed_lateral_deviation_mm()
    assert closing <= min(feed.RACK_BACKLASH_RANGE)
    assert quality.rack_pitch_index_deviation_mm() >= 0.002 * 25.4  # SDP/SI accumulated


def test_one_millimetre_gauge_pin_seats_on_both_source_flanks_clear_of_root() -> None:
    diameter = spec.INCOMING_GAUGE_PIN_DIA_MM
    seat = spec.rack_gauge_pin_contact_mm(diameter)
    assert spec.ROOT_Y < seat.flank_contact_y_mm < spec.BAR_HEIGHT
    assert seat.root_clearance_mm > 0.0
    assert spec.half_width(seat.flank_contact_y_mm) == pytest.approx(
        diameter / 2.0 * math.cos(math.radians(spec.PA_DEG))
    )
    assert seat.centre_y_mm - diameter / 2.0 - spec.ROOT_Y == pytest.approx(
        seat.root_clearance_mm
    )


@pytest.mark.parametrize("diameter", [True, 0.0, -1.0, 0.1, 3.0, math.nan, math.inf])
def test_unseatable_or_unknown_gauge_pins_cannot_supply_incoming_evidence(diameter):
    with pytest.raises(ValueError, match="pin"):
        spec.rack_gauge_pin_contact_mm(diameter)


@pytest.mark.parametrize("intervals", [1, 20])
def test_over_pin_span_corrects_actual_pin_diameters_in_machine_x(intervals):
    first, second = 1.0004, 1.0002
    span = spec.rack_over_pins_span_mm(
        pitch_intervals=intervals, actual_pin_diameters_mm=(first, second)
    )
    assert span == pytest.approx(
        intervals * spec.PITCH + (first + second) / 2.0, rel=0.0, abs=1e-12
    )
    first_seat = spec.rack_gauge_pin_contact_mm(first)
    second_seat = spec.rack_gauge_pin_contact_mm(second)
    assert second_seat.centre_y_mm - first_seat.centre_y_mm == pytest.approx(
        (second - first) / (2.0 * math.sin(math.radians(spec.PA_DEG)))
    )
    centre_x_span = intervals * spec.PITCH
    assert math.hypot(
        centre_x_span, second_seat.centre_y_mm - first_seat.centre_y_mm
    ) > centre_x_span


@pytest.mark.parametrize("intervals", [True, 0, -1, 1.5])
def test_over_pin_span_needs_actual_positive_integer_pitch_count(intervals):
    with pytest.raises(ValueError, match="counted pitch"):
        spec.rack_over_pins_span_mm(
            pitch_intervals=intervals, actual_pin_diameters_mm=(1.0, 1.0)
        )


def test_purchased_identity_and_cut_length_follow_the_primary_product_fields() -> None:
    # Product identity facts, not numerical pins for the feed or rack mesh.
    assert spec.PURCHASED_RACK_SKU == "A 1B12-Y324"
    assert spec.PURCHASED_RACK_MATERIAL == "Brass"
    assert spec.PURCHASED_RACK_LENGTH_IN == 48.0
    assert spec.PURCHASED_RACK_QUALITY_CLASS == "Commercial"
    assert spec.RACK_HEIGHT == pytest.approx(
        spec.PURCHASED_RACK_HEIGHT_IN * spec.MM_PER_IN
    )
    assert spec.RACK_THICKNESS == pytest.approx(
        spec.PURCHASED_RACK_FACE_WIDTH_IN * spec.MM_PER_IN
    )
    assert spec.CUT_LENGTH_MM == spec.BAR_LENGTH == PLATE_WIDTH
    assert spec.CUT_LENGTH_MM < spec.PURCHASED_RACK_LENGTH_MM


@pytest.fixture
def synthetic_stock_section_record():
    # Required uncertainty is explicit synthetic data, not a calibration claim.
    return {
        "measured_stock_height_max_mm": spec.RACK_HEIGHT,
        "stock_height_measurement_uncertainty_mm": 0.001,
        "measured_face_width_max_mm": spec.RACK_THICKNESS,
        "face_width_measurement_uncertainty_mm": 0.001,
    }


def test_incoming_stock_height_and_width_are_separately_paid(synthetic_stock_section_record):
    height, width = spec.require_rack_stock_section_measurements_mm(
        **synthetic_stock_section_record
    )
    assert height > synthetic_stock_section_record["measured_stock_height_max_mm"]
    assert width > synthetic_stock_section_record["measured_face_width_max_mm"]
    assert height <= quality.rack_stock_height_max_mm()
    assert width <= quality.rack_face_width_max_mm()


@pytest.mark.parametrize(
    ("field", "limit_reader", "label"),
    (
        ("measured_stock_height_max_mm", quality.rack_stock_height_max_mm, "stock height"),
        ("measured_face_width_max_mm", quality.rack_face_width_max_mm, "face width"),
    ),
)
def test_measured_at_source_ceiling_still_rejects_uncertainty(
    synthetic_stock_section_record, field, limit_reader, label
):
    record = {**synthetic_stock_section_record, field: limit_reader()}
    with pytest.raises(ValueError, match=f"REJECT incoming rack {label}"):
        spec.require_rack_stock_section_measurements_mm(**record)


@pytest.mark.parametrize(
    "field",
    (
        "measured_stock_height_max_mm", "measured_face_width_max_mm",
        "stock_height_measurement_uncertainty_mm", "face_width_measurement_uncertainty_mm",
    ),
)
@pytest.mark.parametrize("invalid", [True, 0.0, -0.001, math.nan, math.inf, "unknown"])
def test_unknown_stock_receiving_values_do_not_become_zero_or_reference_fallbacks(
    synthetic_stock_section_record, field, invalid
):
    with pytest.raises(ValueError, match="finite positive"):
        spec.require_rack_stock_section_measurements_mm(
            **{**synthetic_stock_section_record, field: invalid}
        )


def test_incoming_stock_uncertainty_cannot_be_omitted(synthetic_stock_section_record):
    del synthetic_stock_section_record["stock_height_measurement_uncertainty_mm"]
    with pytest.raises(TypeError, match="stock_height_measurement_uncertainty_mm"):
        spec.require_rack_stock_section_measurements_mm(**synthetic_stock_section_record)


@pytest.fixture
def synthetic_full_form_receipt():
    """Analytical fixture only; neither stock measurement nor shop capability."""
    from _platen_rack_receiving import (
        feed_rack_receiving_boundary_uncertainty_mm,
        feed_rack_receiving_constraint_uncertainty_mm,
        feed_rack_receiving_root_uncertainty_mm,
    )

    shortest = spec.CUT_LENGTH_MM + printed_deviations(
        spec.CUT_LENGTH_MM, spec.DRAWING_PRECISION_BY_NAME["Length"], unit=spec.UNIT
    )[0]
    count = math.floor(shortest / spec.PITCH) - 1
    stations = tuple(range(count))
    boundary = spec.RackMeasuredUpperBound(0.0, feed_rack_receiving_boundary_uncertainty_mm())
    root = spec.RackMeasuredUpperBound(0.0, feed_rack_receiving_root_uncertainty_mm())
    constraint_uncertainty = feed_rack_receiving_constraint_uncertainty_mm()
    chain = [("crest", 0)]
    for station in stations:
        chain.extend((("left-flank", station), ("root", station),
                      ("right-flank", station), ("crest", station + 1)))
    enclosures = []
    for index, (kind, station) in enumerate(chain):
        mapping = spec.RackFeatureMapping(
            f"synthetic-feature-{index}", kind, station,
            f"vertex-{index}", f"vertex-{index + 1}",
            ((0.0, 0.5, 0.0, 1.0), (0.5, 1.0, 0.0, 0.5), (0.5, 1.0, 0.5, 1.0)),
            "synthetic-independent-datum", "synthetic-whole-native-mapping",
        )
        if kind == "root":
            enclosure = spec.RackRootEnclosure(mapping, root)
        elif kind == "crest":
            enclosure = spec.RackCrestEnclosure(mapping, boundary)
        else:
            # Synthetic same-wire centres, in the one source material frame.
            # Their common radius offset cancels under the straight-side model.
            sign = -1 if kind == "left-flank" else 1
            separation = quality.rack_flank_secant_minimum_height_mm()
            side_secant = (
                spec.RackWireSecantReading(
                    (0., 0.), quality.wire_measurement_uncertainty_mm(),
                    quality.pitch_index_measurement_uncertainty_mm(), "synthetic-same-wire", .5,
                ),
                spec.RackWireSecantReading(
                    (sign * separation * math.tan(math.radians(spec.PA_DEG)), separation),
                    quality.wire_measurement_uncertainty_mm(),
                    quality.pitch_index_measurement_uncertainty_mm(), "synthetic-same-wire", .5,
                ),
            )
            enclosure = spec.RackFlankEnclosure(
                mapping, (0.0, 0.0), constraint_uncertainty, boundary, side_secant,
            )
        enclosures.append(enclosure)
    return spec.RackFormInspectionReceipt(
        stock_id="synthetic-analytical-profile",
        global_datum_id="synthetic-independent-datum",
        datum_reference_kind="independent-fixture",
        datum_reference_xy_mm=(0.0, spec.PITCH_LINE_Y),
        method_ref="synthetic-whole-point-analytic-method",
        calibration_ref="synthetic-calibration-not-hardware",
        trace_ref="synthetic-complete-analytic-trace",
        whole_point_enclosure_ref="synthetic-complete-material-point-envelope-proof",
        inspection_basis="qualified-extrusion-process",
        boundary_partition_ref="synthetic-all-material-boundary-partition",
        native_mapping_ref="synthetic-whole-native-mapping",
        parameterization="full-native-u/full-actual-face-v",
        physical_gap_stations=stations,
        stock_height_mm=spec.RackMeasuredUpperBound(spec.RACK_HEIGHT, 0.005),
        face_width_mm=spec.RackMeasuredUpperBound(spec.RACK_THICKNESS, 0.005),
        measured_usable_face_min_mm=spec.RACK_THICKNESS,
        usable_face_measurement_uncertainty_mm=0.005,
        enclosures=tuple(enclosures),
    )


def _receive_synthetic_form(receipt):
    return spec.require_rack_form_admission_mm(
        receipt=receipt, required_gap_stations=receipt.physical_gap_stations
    )


def _replace_synthetic_feature(receipt, index, replacement):
    records = list(receipt.enclosures)
    records[index] = replacement
    return receipt._replace(enclosures=tuple(records))


def test_whole_point_envelope_returns_paid_data_not_a_hardware_boolean(
    synthetic_full_form_receipt,
):
    from _platen_rack_receiving import (
        feed_rack_receiving_boundary_uncertainty_mm,
        feed_rack_receiving_constraint_uncertainty_mm,
        feed_rack_receiving_root_uncertainty_mm,
    )

    report = _receive_synthetic_form(synthetic_full_form_receipt)
    assert report.scope == "whole-point-envelope"
    assert report.constraint_relative_mm > 2.0 * feed_rack_receiving_constraint_uncertainty_mm()
    assert report.constraint_relative_mm < quality.rack_flank_constraint_deviation_mm()
    assert report.active_boundary_mm > feed_rack_receiving_boundary_uncertainty_mm()
    assert report.root_intrusion_mm > feed_rack_receiving_root_uncertainty_mm()
    assert report.usable_face_lower_mm > 0.0
    assert report.receipt is synthetic_full_form_receipt
    assert report.station_ids == synthetic_full_form_receipt.physical_gap_stations
    assert len(report.feature_ids) == 4 * len(report.station_ids) + 1
    assert report.status_text == quality.stock_form_receiving_status_text()
    assert not hasattr(report, "qualified") and not hasattr(report, "C1")


def test_uniform_tooth_width_error_rejects_even_when_all_index_spans_pass(
    synthetic_full_form_receipt,
):
    g = quality.rack_flank_constraint_deviation_mm()
    enclosures = tuple(
        enclosure._replace(
            constraint_error_band_mm=((0.6 * g, 0.6 * g)
                                      if enclosure.mapping.kind == "left-flank"
                                      else (-0.6 * g, -0.6 * g))
        ) if isinstance(enclosure, spec.RackFlankEnclosure) else enclosure
        for enclosure in synthetic_full_form_receipt.enclosures
    )
    # Both gap-centre errors remain zero; index-only receipt really can pass.
    quality.require_pitch_index_measurements_mm(
        measured_index_errors_mm={station: 0.0 for station in synthetic_full_form_receipt.physical_gap_stations},
        required_stations=synthetic_full_form_receipt.physical_gap_stations,
        relative_deviation_limit_mm=quality.rack_pitch_index_deviation_mm(),
        absolute_measurement_uncertainty_mm=quality.pitch_index_measurement_uncertainty_mm(),
    )
    with pytest.raises(ValueError, match="BOTH-flank relative"):
        _receive_synthetic_form(synthetic_full_form_receipt._replace(enclosures=enclosures))


@pytest.mark.parametrize("index", [0, 1])
def test_each_active_point_boundary_pays_its_own_uncertainty(
    synthetic_full_form_receipt, index,
):
    from _platen_rack_receiving import feed_rack_form_admission_controls

    enclosure = synthetic_full_form_receipt.enclosures[index]
    controls = feed_rack_form_admission_controls()
    boundary = enclosure.boundary_mm._replace(measured_maximum=controls["active_boundary_mm"])
    receipt = _replace_synthetic_feature(
        synthetic_full_form_receipt, index, enclosure._replace(boundary_mm=boundary)
    )
    with pytest.raises(ValueError, match="REJECT"):
        _receive_synthetic_form(receipt)


@pytest.mark.parametrize("field", ["boundary", "constraint", "root"])
@pytest.mark.parametrize("invalid", [True, False, 0.0, -1.0, math.nan, math.inf, "unknown", 1e-8])
def test_each_calibration_rejects_unknown_or_sub_shop_floor_uncertainty(
    synthetic_full_form_receipt, field, invalid,
):
    index = 2 if field == "root" else 1
    enclosure = synthetic_full_form_receipt.enclosures[index]
    if field == "constraint":
        replacement = enclosure._replace(constraint_uncertainty_mm=invalid)
    elif field == "root":
        replacement = enclosure._replace(intrusion_mm=spec.RackMeasuredUpperBound(0.0, invalid))
    else:
        replacement = enclosure._replace(boundary_mm=spec.RackMeasuredUpperBound(0.0, invalid))
    receipt = _replace_synthetic_feature(synthetic_full_form_receipt, index, replacement)
    with pytest.raises(ValueError, match="UNKNOWN"):
        _receive_synthetic_form(receipt)


@pytest.mark.parametrize("invalid", [True, math.nan, math.inf, "unknown"])
def test_boolean_or_unknown_point_measurement_is_not_zero(
    synthetic_full_form_receipt, invalid,
):
    enclosure = synthetic_full_form_receipt.enclosures[0]
    boundary = enclosure.boundary_mm._replace(measured_maximum=invalid)
    receipt = _replace_synthetic_feature(
        synthetic_full_form_receipt, 0, enclosure._replace(boundary_mm=boundary)
    )
    with pytest.raises(ValueError, match="UNKNOWN"):
        _receive_synthetic_form(receipt)


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_missing_crest_either_flank_or_root_rejects(synthetic_full_form_receipt, index):
    receipt = synthetic_full_form_receipt._replace(
        enclosures=tuple(record for i, record in enumerate(synthetic_full_form_receipt.enclosures)
                         if i != index)
    )
    with pytest.raises(ValueError, match="missing either flank/crest/root"):
        _receive_synthetic_form(receipt)


@pytest.mark.parametrize(
    "patches",
    (
        ((0.0, 0.49, 0.0, 1.0), (0.5, 1.0, 0.0, 1.0)),
        ((0.0, 1.0, 0.0, 0.49), (0.0, 1.0, 0.5, 1.0)),
        ((0.0, 0.5, 0.0, 0.5), (0.5, 1.0, 0.5, 1.0)),
        ((True, 1.0, 0.0, 1.0),),
        (),
    ),
)
def test_full_feature_and_full_face_coverage_is_not_inferred_from_samples(
    synthetic_full_form_receipt, patches,
):
    enclosure = synthetic_full_form_receipt.enclosures[1]
    mapping = enclosure.mapping._replace(parameter_patches=patches)
    receipt = _replace_synthetic_feature(
        synthetic_full_form_receipt, 1, enclosure._replace(mapping=mapping)
    )
    with pytest.raises(ValueError, match="UNKNOWN"):
        _receive_synthetic_form(receipt)


@pytest.mark.parametrize("field", ["global_datum_id", "native_mapping_ref"])
def test_per_station_or_per_side_refits_are_forbidden(synthetic_full_form_receipt, field):
    enclosure = synthetic_full_form_receipt.enclosures[1]
    mapping = enclosure.mapping._replace(**{field: "independent-side-fit"})
    receipt = _replace_synthetic_feature(
        synthetic_full_form_receipt, 1, enclosure._replace(mapping=mapping)
    )
    with pytest.raises(ValueError, match="per-feature datum/refit"):
        _receive_synthetic_form(receipt)


def test_even_global_pin_seat_y_fit_cannot_hide_uniform_thickness(synthetic_full_form_receipt):
    with pytest.raises(ValueError, match="no flank/pin fitting"):
        _receive_synthetic_form(synthetic_full_form_receipt._replace(datum_reference_kind="pin-seat-fit"))


def test_native_boundary_mapping_must_really_connect(synthetic_full_form_receipt):
    enclosure = synthetic_full_form_receipt.enclosures[1]
    mapping = enclosure.mapping._replace(start_vertex_id="disconnected-vertex")
    receipt = _replace_synthetic_feature(
        synthetic_full_form_receipt, 1, enclosure._replace(mapping=mapping)
    )
    with pytest.raises(ValueError, match="partition is disconnected"):
        _receive_synthetic_form(receipt)


@pytest.mark.parametrize(
    "field",
    ("method_ref", "calibration_ref", "trace_ref", "whole_point_enclosure_ref",
     "boundary_partition_ref", "native_mapping_ref"),
)
def test_full_form_requires_actual_method_calibration_and_mapping_provenance(
    synthetic_full_form_receipt, field,
):
    with pytest.raises(ValueError, match="actual evidence reference"):
        _receive_synthetic_form(synthetic_full_form_receipt._replace(**{field: "unknown"}))


def test_root_intrusion_is_paid_not_an_inactive_root_assumption(synthetic_full_form_receipt):
    enclosure = synthetic_full_form_receipt.enclosures[2]
    receipt = _replace_synthetic_feature(
        synthetic_full_form_receipt, 2,
        enclosure._replace(intrusion_mm=enclosure.intrusion_mm._replace(
            measured_maximum=quality.rack_root_material_intrusion_mm()
        )),
    )
    with pytest.raises(ValueError, match="whole root-material intrusion"):
        _receive_synthetic_form(receipt)


def test_nonempty_actual_usable_face_is_required_after_uncertainty(synthetic_full_form_receipt):
    receipt = synthetic_full_form_receipt._replace(
        measured_usable_face_min_mm=0.001, usable_face_measurement_uncertainty_mm=0.001
    )
    with pytest.raises(ValueError, match="nonempty calibrated"):
        _receive_synthetic_form(receipt)


def test_patch_local_coordinates_cannot_replace_whole_feature_parameters(synthetic_full_form_receipt):
    with pytest.raises(ValueError, match="parameterization"):
        _receive_synthetic_form(synthetic_full_form_receipt._replace(parameterization="patch-local-u-v"))


def test_three_station_receipt_cannot_certify_the_whole_finite_rack(synthetic_full_form_receipt):
    receipt = synthetic_full_form_receipt._replace(physical_gap_stations=(0, 1, 2))
    with pytest.raises(ValueError, match="sample-only"):
        _receive_synthetic_form(receipt)


@pytest.mark.parametrize(
    "basis", ["sampled-pins", "point-cloud", "filtered-CMM", "C1", "unknown", True]
)
def test_samples_or_filtered_flags_do_not_supply_whole_material_process_evidence(
    synthetic_full_form_receipt, basis,
):
    with pytest.raises(ValueError, match="whole-point process/functional"):
        _receive_synthetic_form(synthetic_full_form_receipt._replace(inspection_basis=basis))


@pytest.mark.parametrize("basis", ["qualified-extrusion-process", "actual-functional-roll"])
def test_supported_process_basis_still_requires_all_explicit_envelopes(
    synthetic_full_form_receipt, basis,
):
    receipt = synthetic_full_form_receipt._replace(inspection_basis=basis)
    assert _receive_synthetic_form(receipt).receipt is receipt
    with pytest.raises(ValueError, match="actual evidence reference"):
        _receive_synthetic_form(receipt._replace(whole_point_enclosure_ref="unknown"))


@pytest.mark.parametrize(
    "unsupported", [True, {"points": ((0.0, 0.0), (1.0, 1.0)), "C1": True}, {"roll_error": 0.0}]
)
def test_raw_pins_cloud_or_roll_scalar_is_not_a_material_envelope_certificate(unsupported):
    with pytest.raises(ValueError, match="whole-point-envelope inspection receipt"):
        spec.require_rack_form_admission_mm(receipt=unsupported, required_gap_stations=(0, 1, 2))


@pytest.fixture
def synthetic_right_side_secant():
    """Analytic wire-centre inputs, not actual stock or calibration evidence."""
    separation = quality.rack_flank_secant_minimum_height_mm()
    return (
        spec.RackWireSecantReading(
            (0., 0.), quality.wire_measurement_uncertainty_mm(),
            quality.pitch_index_measurement_uncertainty_mm(), "synthetic-common-wire", .5,
        ),
        spec.RackWireSecantReading(
            (separation * math.tan(math.radians(spec.PA_DEG)), separation),
            quality.wire_measurement_uncertainty_mm(),
            quality.pitch_index_measurement_uncertainty_mm(), "synthetic-common-wire", .5,
        ),
    )


def test_working_side_secant_pays_both_xy_readings_and_retains_model_scope(
    synthetic_right_side_secant,
    synthetic_full_form_receipt,
):
    readings = synthetic_right_side_secant
    band = spec.require_rack_working_side_secant_angle_band_rad(
        readings=readings, flank_kind="right-flank",
    )
    dy = readings[1].xy_mm[1] - readings[0].xy_mm[1]
    dx = readings[1].xy_mm[0] - readings[0].xy_mm[0]
    ux = sum(reading.x_uncertainty_mm for reading in readings)
    uy = sum(reading.y_uncertainty_mm for reading in readings)
    assert band[0] <= math.atan2(dx - ux, dy + uy)
    assert band[1] >= math.atan2(dx + ux, dy - uy)
    assert band[0] < math.radians(spec.PA_DEG) < band[1]
    report = _receive_synthetic_form(synthetic_full_form_receipt)
    assert report.working_side_form_model_premise == quality.purchased_rack_working_side_form_model_premise()
    assert len(report.working_side_angle_bands_rad) == 2 * len(report.station_ids)
    assert not hasattr(report, "received_local_normals")


def test_same_wire_radius_offset_cancels_without_nominal_diameter_correction(
    synthetic_right_side_secant,
):
    readings = synthetic_right_side_secant
    reference = spec.require_rack_working_side_secant_angle_band_rad(
        readings=readings, flank_kind="right-flank",
    )
    other_common_diameter = tuple(reading._replace(wire_diameter_mm=.7) for reading in readings)
    assert spec.require_rack_working_side_secant_angle_band_rad(
        readings=other_common_diameter, flank_kind="right-flank",
    ) == reference
    translated = tuple(reading._replace(
        xy_mm=(reading.xy_mm[0] + 7.3, reading.xy_mm[1]),
    ) for reading in readings)
    assert spec.require_rack_working_side_secant_angle_band_rad(
        readings=translated, flank_kind="right-flank",
    ) == pytest.approx(reference, abs=1e-14)


@pytest.mark.parametrize("field, value, reason", [
    ("wire_id", "other-wire", "SAME physical wire"),
    ("wire_diameter_mm", .6, "SAME physical wire"),
    ("x_uncertainty_mm", .004, "instrument floors"),
    ("y_uncertainty_mm", .001, "instrument floors"),
    ("x_uncertainty_mm", 0., "positive"),
    ("wire_diameter_mm", True, "numeric"),
    ("xy_mm", (math.nan, .8), "numeric"),
])
def test_working_side_secant_rejects_unpaid_or_foreign_wire_inputs(
    synthetic_right_side_secant, field, value, reason,
):
    first, second = synthetic_right_side_secant
    with pytest.raises(ValueError, match=reason):
        spec.require_rack_working_side_secant_angle_band_rad(
            readings=(first, second._replace(**{field: value})), flank_kind="right-flank",
        )


@pytest.mark.parametrize("nominal_angle", [18., 22.])
def test_nominal_side_at_angle_limit_rejects_the_paid_uncertainty(
    synthetic_right_side_secant, nominal_angle,
):
    first, second = synthetic_right_side_secant
    second = second._replace(xy_mm=(
        second.xy_mm[1] * math.tan(math.radians(nominal_angle)), second.xy_mm[1],
    ))
    with pytest.raises(ValueError, match="complete paid secant-angle interval"):
        spec.require_rack_working_side_secant_angle_band_rad(
            readings=(first, second), flank_kind="right-flank",
        )


def test_short_or_wrong_side_secant_is_not_a_direction_or_calibration_fallback(
    synthetic_right_side_secant,
):
    first, second = synthetic_right_side_secant
    with pytest.raises(ValueError, match="height separation"):
        spec.require_rack_working_side_secant_angle_band_rad(
            readings=(first, second._replace(xy_mm=(.79 * math.tan(math.radians(spec.PA_DEG)), .79))),
            flank_kind="right-flank",
        )
    with pytest.raises(ValueError, match="native flank/height direction"):
        spec.require_rack_working_side_secant_angle_band_rad(
            readings=(first, second), flank_kind="left-flank",
        )
