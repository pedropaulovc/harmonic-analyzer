"""Purchased-data contract for McMaster-Carr 9432K31.

This module is pure Python data: catalogue geometry comes from the verified
supplier-geometry module, the installed lengths come from the actual mount
poses, and force values come from the purchased part row.  Lengths are
catalogue inside-hook measurements, never coil-body or eye-centre distances.

``INSTALLED_LENGTH_MM`` is the analytic catalogue seed of the rest pose.  The
part itself is preset-dependent (#1610): one configuration per distinct
measured installed length among the amplitude preset's channels
(``installed_lengths``), so the channel assembly places one part, and its BOM
prints one MHA-CH-VN-50 row, whatever the preset.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import _config
import ch_vn_channel_spring_stock_geom as stock
import settled_spring_seats
from spring_mount_geom import (
    CHANNEL_INITIAL_TENSION_N,
    CHANNEL_NOMINAL_POSE,
    CHANNEL_RATE_N_PER_MM,
    channel_force_n,
)


_PART = _config.parts("ch-vn-channel-spring-installed")

FREE_LENGTH_MM = stock.FREE_LENGTH_MM
MAX_LENGTH_MM = stock.MAX_LENGTH_MM
INSTALLED_LENGTH_MM = stock.check_length_mm(CHANNEL_NOMINAL_POSE.length_mm)
SPRING_RATE_N_PER_MM = CHANNEL_RATE_N_PER_MM
INITIAL_TENSION_N = CHANNEL_INITIAL_TENSION_N
MAXIMUM_LOAD_N = float(_PART["maximum_load_n"])

# The first installed length keeps the part's native first configuration, so
# a one-length preset (neutral) saves a single installed configuration.
DEFAULT_CONFIGURATION = "Default"


@dataclass(frozen=True, slots=True)
class InstalledLength:
    """One installed configuration: its name and catalogue inside-hook length."""

    configuration: str
    length_mm: float


def configuration_name(index: int) -> str:
    """``Default`` for the first distinct length, then ``Installed01``..."""
    if index < 0:
        raise ValueError(f"installed configuration index {index} is negative")
    return DEFAULT_CONFIGURATION if index == 0 else f"Installed{index:02d}"


def installed_lengths(amplitudes: Sequence[float]) -> tuple[InstalledLength, ...]:
    """One configuration per distinct measured seat length, first-occurrence order.

    Every station's fixed measured seat (``settled_spring_seats``) is read and
    checked against the catalogue length band and maximum load before any
    native work, so an unsupported preset fails without building anything.
    """
    if not amplitudes:
        raise ValueError("the channel spring needs at least one amplitude station")
    lengths: list[float] = []
    for amplitude in amplitudes:
        length = settled_spring_seats.channel_seat(amplitude).pose.length_mm
        stock.check_length_mm(length)
        if channel_force_n(length) > MAXIMUM_LOAD_N:
            raise RuntimeError(
                f"settled channel spring at a={amplitude:g} mm exceeds catalog load"
            )
        if length not in lengths:
            lengths.append(length)
    return tuple(
        InstalledLength(configuration_name(index), length)
        for index, length in enumerate(lengths)
    )


def channel_configurations(amplitudes: Sequence[float]) -> tuple[str, ...]:
    """Each station's installed configuration, in station order."""
    by_length = {
        installed.length_mm: installed.configuration
        for installed in installed_lengths(amplitudes)
    }
    return tuple(
        by_length[settled_spring_seats.channel_seat(amplitude).pose.length_mm]
        for amplitude in amplitudes
    )


# Supplier-stated scatter.  This is catalogue acceptance data, not the tighter
# 20-spring common-set matching requirement used by the analyzer.
SPRING_RATE_TOLERANCE_FRACTION = float(_PART["spring_rate_tolerance_fraction"])
INITIAL_TENSION_TOLERANCE_N = float(_PART["initial_tension_tolerance_n"])

# Inspected supplier drawing; these nominal gauges do not measure the installed pose.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260617/4210389D/"
    "9432K31_Music-Wire%20Steel%20Extension%20Springs%20with%20Hook%20EndsX.GIF"
)
SUPPLIER_PRECISION = {
    "SupplierFreeLength": 3,
    "SupplierMaximumLength": 3,
    "SupplierCoilOD": 2,
    "SupplierWireDiameter": 3,
}
SUPPLIER_COIL_OD_MM = stock.COIL_OD_MM
SUPPLIER_WIRE_DIA_MM = stock.WIRE_DIA_MM
# Supplier coil OD tolerance, +/-0.008 in: "OD Tolerance -0.008" to 0.008"",
# https://www.mcmaster.com/9432K31/ (read live 2026-11-17 with the Scrapfly
# CLI). The page states no free-length, maximum-length or wire tolerance.
SUPPLIER_COIL_OD_TOLERANCE_MM = 0.008 * 25.4
