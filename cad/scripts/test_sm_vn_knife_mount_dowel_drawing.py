"""Offline contracts for the MHA-SM-VN-53 knife-mount dowel (McMaster 98381A473)."""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import build_sm_vn_knife_mount_dowel as part
import sm_vn_knife_mount_dowel_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_98381A473 as recipe
from _dowel_dimensions import MM_PER_IN

STEM = "sm-vn-knife-mount-dowel"


def test_catalogue_row_is_the_registered_mcmaster_dowel() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert row["number"] == "MHA-SM-VN-53"
    assert int(row["quantity"]) == spec.QUANTITY == 4  # two per knife mount
    metadata = recipe_declaration(spec.SKU, recipe.build_98381A473)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98381A473
    assert metadata.threaded is False


def test_standalone_recipe_run_is_the_replica_gate() -> None:
    """98381A473 has a user-supplied vendor model, so the standalone run is
    the replica gate, not a catalog-only build."""
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_98381A473
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main(PART_NO, build_98381A473)" in source


def test_recipe_is_the_size_the_registry_names() -> None:
    text = _config.parts(STEM)["material_specification"]
    assert spec.SKU in text
    match = re.search(r"(\d+/\d+) x (\d+/\d+)", text)
    assert match, text
    dia, length = (float(Fraction(size)) * MM_PER_IN for size in match.groups())
    assert spec.DIA == pytest.approx(dia)
    assert spec.LENGTH == pytest.approx(length)


def test_pressed_and_proud_lengths_are_the_whole_pin() -> None:
    assert spec.PRESS_DEPTH + spec.PROUD == pytest.approx(spec.LENGTH)
    assert spec.PRESS_ENGAGEMENT_D_MIN >= spec.PRESS_ENGAGEMENT_MIN_D
    assert spec.SLIP_DEPTH_CLEARANCE_MIN > 0.0
    assert min(spec.DIA_BAND) > 0.0  # a press dowel is oversize, never under


def test_the_chamfered_end_is_the_pressed_end() -> None:
    from diagnostics.diag_mcmaster_dowel import dowel_section

    section = dowel_section((spec.DIA, spec.LENGTH), spec.ENDS)
    pressed_face = max(rad for rad, y in section if y == 0.0)
    lead_face = max(rad for rad, y in section if y == spec.LENGTH)
    assert pressed_face == pytest.approx(spec.ENDS.point_dia / 2.0)
    assert lead_face == pytest.approx(spec.DIA / 2.0 - spec.ENDS.crown_r)
    assert (spec.DIA / 2.0, spec.CHAMFER_LEN) in section


def test_the_installation_note_names_both_holes_and_fits_the_sheet() -> None:
    from _purchased_fastener_drawing import note_lines

    lines = note_lines(_config.parts(STEM)["installation_notes"], label=STEM)
    assert all(len(line) <= 70 for line in lines), lines
    flat = " ".join(lines)
    assert "MHA-SM-02" in flat and "MHA-FR-02" in flat
    assert "UNDERSIDE REAM, CHAMFER END FIRST." in flat
    # Owner ruling 2026-10-24 (T+H3): the crossbar holds the press, the knife
    # mount the slip.
    assert "PRESS FIT IN THE MHA-FR-02 CROSSBAR" in flat
    assert "INTO THE MHA-SM-02 KNIFE MOUNT" in flat


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_sm_vn_knife_mount_dowel as drawing

    sheet = DRAWINGS_BY_NAME["sm_vn_knife_mount_dowel"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
