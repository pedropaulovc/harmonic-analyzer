"""Offline contracts for the purchased 9432K31 reference sheet."""

from __future__ import annotations

import math

import ch_vn_channel_spring_installed_notes as notes
import ch_vn_channel_spring_installed_spec as spec
from _purchased_fastener_drawing import note_lines
from spring_mount_geom import channel_force_n


def test_installed_spring_stays_within_catalogue_load_envelope() -> None:
    assert spec.FREE_LENGTH_MM <= spec.INSTALLED_LENGTH_MM <= spec.MAX_LENGTH_MM
    assert channel_force_n(spec.INSTALLED_LENGTH_MM) < spec.MAXIMUM_LOAD_N


def test_two_point_qc_measures_the_catalogue_rate() -> None:
    measured = (channel_force_n(80.0) - channel_force_n(60.0)) / 20.0
    assert math.isclose(measured, spec.SPRING_RATE_N_PER_MM, rel_tol=1e-12)


def test_matched_set_loads_stretch_a_catalogue_spring_to_the_qc_lengths() -> None:
    """The printed dead loads land a catalogue spring within 1 mm of each QC
    length, on its linear branch and under the catalogue maximum load."""
    lb = 4.4482216152605
    for load_lb, length in zip(notes.QC_LOADS_LB, notes.QC_LENGTHS_MM, strict=True):
        stretched = spec.FREE_LENGTH_MM + (
            load_lb * lb - spec.INITIAL_TENSION_N
        ) / spec.SPRING_RATE_N_PER_MM
        assert abs(stretched - length) < 1.0
        assert spec.FREE_LENGTH_MM < stretched < spec.MAX_LENGTH_MM
        assert load_lb * lb < spec.MAXIMUM_LOAD_N
    # The purchased-sheet footer's rule-7 budget, which raises on the farm.
    lines = note_lines(notes.DRAWING_NOTES, label="channel spring")
    assert all(len(line) <= 70 for line in lines), lines


def test_source_gauges_preserve_exact_values_and_supplier_spelling() -> None:
    assert math.isclose(spec.FREE_LENGTH_MM, 1.948 * 25.4)
    assert math.isclose(spec.MAX_LENGTH_MM, 5.448 * 25.4)
    assert math.isclose(spec.SUPPLIER_COIL_OD_MM, 0.25 * 25.4)
    assert math.isclose(spec.SUPPLIER_WIRE_DIA_MM, 0.026 * 25.4)
    assert spec.SUPPLIER_PRECISION == {
        "SupplierFreeLength": 3, "SupplierMaximumLength": 3,
        "SupplierCoilOD": 2, "SupplierWireDiameter": 3,
    }


def _preset(name: str) -> list[float]:
    import _config

    return list(_config.machine("springs", "presets")[name]["amplitudes_mm"])


def test_neutral_preset_saves_one_default_configuration() -> None:
    """#1610: one installed length keeps the single native configuration."""
    import settled_spring_seats

    neutral = _preset("neutral")
    (only,) = spec.installed_lengths(neutral)
    assert only.configuration == "Default"
    assert only.length_mm == settled_spring_seats.channel_seat(0.0).pose.length_mm
    assert spec.channel_configurations(neutral) == ("Default",) * len(neutral)


def test_square_preset_is_one_part_with_a_configuration_per_installed_length() -> None:
    """#1610 route (a): the square preset's eleven measured lengths are
    configurations of the one MHA-CH-VN-50 part, first-occurrence order, and
    every station names its own length's configuration."""
    import settled_spring_seats

    square = _preset("square")
    installed = spec.installed_lengths(square)
    assert len(installed) == len(dict.fromkeys(square)) == 11
    assert [length.configuration for length in installed] == [
        "Default",
        *(f"Installed{index:02d}" for index in range(1, 11)),
    ]
    assert len({length.length_mm for length in installed}) == len(installed)
    by_name = {length.configuration: length.length_mm for length in installed}
    stations = spec.channel_configurations(square)
    assert len(stations) == len(square)
    for amplitude, configuration in zip(square, stations, strict=True):
        seat = settled_spring_seats.channel_seat(amplitude).pose.length_mm
        assert by_name[configuration] == seat
        assert spec.FREE_LENGTH_MM <= seat <= spec.MAX_LENGTH_MM
        assert channel_force_n(seat) <= spec.MAXIMUM_LOAD_N
    assert stations.count("Default") == square.count(0)
