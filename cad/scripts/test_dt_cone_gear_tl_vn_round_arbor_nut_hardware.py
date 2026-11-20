"""Catalogue-only contracts for dt-cone-gear-tl-vn-round-arbor-nut (MHA-DT-03-TL-VN-51).

Bought finished fixture hardware is modelled only when a fixture kit assembly
must run native interference against it (subsystem-identities.md); no kit
assembly places this nut, so it is its registry row and its HARDWARE.md row
(tier 1) only: no build script, no catalogue fastener row, no sheet. Its fit
on the round arbor (MHA-DT-03-TL-07) is the arbor spec's, from the same
``_mcmaster_90480a009`` catalogue sizes.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _buildgraph as bg
import _config
import _mcmaster_90480a009 as catalogue
import hardware_schedule
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS

STEM = "dt-cone-gear-tl-vn-round-arbor-nut"
NUMBER = "MHA-DT-03-TL-VN-51"
IN = 25.4
SCRIPTS = Path(__file__).resolve().parent


def test_registry_row_is_the_purchased_mcmaster_nut() -> None:
    row = _config.parts(STEM)
    assert row["number"] == NUMBER
    assert tuple(row["supplier_skus"]) == (catalogue.SKU,) == ("90480A009",)
    assert row["supplier"] == "McMaster-Carr"
    assert row["stock_name"] == "Low-Strength Zinc-Plated Steel Hex Nut"
    assert row["finish"] == "zinc plated"
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == 1
    assert "ASME B18.6.3" in row["material_specification"]


def test_it_is_catalogue_only() -> None:
    """No kit assembly runs interference against it, so nothing models it."""
    underscored = STEM.replace("-", "_")
    assert underscored not in bg.part_stems()
    assert not (SCRIPTS / f"build_{underscored}.py").exists()
    assert not (SCRIPTS / f"{underscored}_spec.py").exists()
    assert STEM not in FASTENERS
    assert underscored not in DRAWINGS_BY_NAME
    assert all(underscored not in bg.references_of(a) for a in bg.ASSEMBLY_ORDER)


def test_it_ships_as_a_tier_1_hardware_row() -> None:
    row = hardware_schedule.SCHEDULE[STEM]
    pen_nut = hardware_schedule.SCHEDULE["pn-vn-pen-hanger-nut"]
    for field in ("why", "designation", "standard", "envelope"):
        assert row[field] == pen_nut[field], field
    assert row["standard"] == "ASME B18.6.3"
    assert row["designation"].startswith("#8-32 UNC-2B hex machine screw nut")
    assert STEM in hardware_schedule.purchased_parts()
    assert hardware_schedule.envelope_mm(row["envelope"]["AC"]) == pytest.approx(
        catalogue.ACROSS_FLATS / math.cos(math.pi / 6)
    )
    assert hardware_schedule.envelope_mm(row["envelope"]["T"]) == pytest.approx(
        catalogue.THICKNESS
    )
    assert NUMBER in hardware_schedule.markdown()


def test_catalogue_facts() -> None:
    """McMaster 90480A009 (``_mcmaster_90480a009``): ASME B18.6.3 #8-32
    machine screw nut, 11/32 wide, 1/8 high."""
    assert catalogue.THREAD == "#8-32"
    assert catalogue.ACROSS_FLATS == pytest.approx(11.0 / 32.0 * IN)
    assert catalogue.THICKNESS == pytest.approx(1.0 / 8.0 * IN)


def test_the_nut_clamps_the_collar_on_full_thread_under_t024s_root() -> None:
    """The nut matches the arbor's #8-32 thread, bears on the collar's face,
    and its corners stand under T024's root by the air."""
    import dt_cone_gear_tl_round_arbor_spec as arbor

    assert catalogue.THREAD == arbor.THREAD
    assert catalogue.ACROSS_FLATS == pytest.approx(arbor.NUT_ACROSS_FLATS)
    assert catalogue.THICKNESS <= arbor.NUT_THICKNESS_MAX
    corners = catalogue.ACROSS_FLATS / math.cos(math.pi / 6)
    assert corners / 2.0 + arbor.AIR_MIN <= arbor.BLANK.root_min_dia / 2.0
    assert catalogue.ACROSS_FLATS > arbor.COLLAR_BORE + arbor._DRILL_PLUS
    assert arbor.THREAD_PAST_NUT_MIN >= 1.5 * arbor.THREAD_PITCH
    assert arbor.NUT_THREAD_MARGIN > 0.0
