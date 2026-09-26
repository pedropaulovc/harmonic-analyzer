"""MHA-151: the cone pivot post's dowel pins, McMaster 98381A304 (#917 S1).

SolidWorks-free: the stock identity, the tracked replay's section and its
analytic mass properties, and the registrations the production build and the
replica gate read.  The replay itself is untested on a seat.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_cone_post_dowel as part
import cone_post_dowel_spec as dowel
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_98381A304 as recipe

_MCMASTER = Path(__file__).resolve().parents[1] / "references" / "mcmaster"


def test_stock_identity_is_the_dowel_the_post_spec_names() -> None:
    spec = FASTENERS["cone-post-dowel"]
    assert spec.skus == (dowel.POST_DOWEL_SKU,) == ("98381A304",)
    assert spec.material == "Alloy Steel"
    assert spec.supplier == "McMaster-Carr"
    row = _config.parts("cone-post-dowel")
    assert row["number"] == dowel.POST_DOWEL_PART_NUMBER == "MHA-151"
    assert tuple(row["supplier_skus"]) == spec.skus
    assert row["stock_name"] == spec.stock_name
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == len(dowel.POST_DOWEL_PLATE_XZ) == 2
    notes = row["installation_notes"]
    for number in ("MHA-016", "MHA-091"):
        assert number in notes
    for token in ("0.", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."):
        assert token not in notes


def test_replay_section_matches_the_catalog_pin() -> None:
    """The vendor file's own section (read offline from its Parasolid
    partition): a 1/8 x 1/2 pin, a 16 deg lead-in on one end and an R.016
    crown blend on the other."""
    assert 2.0 * recipe.PIN_RADIUS == pytest.approx(dowel.POST_DOWEL_DIA)
    assert recipe.PIN_LENGTH == pytest.approx(dowel.POST_DOWEL_LENGTH)
    assert 2.0 * recipe.PIN_RADIUS < dowel.POST_DOWEL_PIN_DIA_RANGE[0]
    assert recipe.LEAD_HALF_ANGLE_DEG == 16.0
    lead_axial = recipe.LEAD_RADIAL / math.tan(math.radians(16.0))
    assert recipe.LEAD_START_Y == pytest.approx(-recipe.PIN_LENGTH / 2.0 + lead_axial)
    assert recipe.LEAD_START_Y == pytest.approx(-5.907098, abs=1e-6)
    assert recipe.LEAD_END_RADIUS == pytest.approx(1.4605)
    # The crown blend is tangent to the flank and to the end face.
    assert recipe.CROWN_CENTRE_R + recipe.CROWN_R == pytest.approx(recipe.PIN_RADIUS)
    assert recipe.CROWN_CENTRE_Y + recipe.CROWN_R == pytest.approx(recipe.PIN_LENGTH / 2.0)
    assert recipe.CROWN_R == pytest.approx(0.016 * 25.4)


def test_replay_mass_properties_are_analytic() -> None:
    r, re_ = recipe.PIN_RADIUS, recipe.LEAD_END_RADIUS
    a = recipe.LEAD_START_Y + recipe.PIN_LENGTH / 2.0
    flank = recipe.CROWN_CENTRE_Y - recipe.LEAD_START_Y
    rc, rr = recipe.CROWN_CENTRE_R, recipe.CROWN_R
    volume = (
        math.pi * r * r * flank
        + math.pi * a / 3.0 * (r * r + r * re_ + re_ * re_)
        + math.pi * (rc * rc * rr + rc * math.pi * rr * rr / 2.0 + 2.0 * rr**3 / 3.0)
    )
    area = (
        2.0 * math.pi * r * flank
        + math.pi * (r + re_) * math.hypot(a, r - re_)
        + math.pi * re_ * re_
        + math.pi * rc * rc
        + 2.0 * math.pi * rr * (rc * math.pi / 2.0 + rr)
    )
    assert recipe.VOLUME_MM3 == pytest.approx(volume)
    assert recipe.AREA_MM2 == pytest.approx(area)
    assert recipe.FACE_COUNT == 5
    assert round(recipe.VOLUME_MM3, 3) == 99.943
    assert round(recipe.AREA_MM2, 3) == 139.476


def test_stock_build_uses_its_registered_recipe() -> None:
    metadata = STOCK_RECIPES["98381A304"]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_98381A304.__name__
    assert part.SPEC is FASTENERS[part.PART_NAME]
    assert part.MATERIAL == "Alloy Steel"
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "build_stock_fastener" in source
    assert "screw_axis_planes=(\"Front Plane\", \"Right Plane\")" in source


def test_replica_gate_is_registered() -> None:
    from diagnostics import diag_build_mcmaster as driver

    assert driver.REGISTRY["98381A304"] is recipe.build_98381A304


def test_vendor_readme_lists_the_dowel() -> None:
    readme = (_MCMASTER / "README.md").read_text(encoding="utf-8")
    assert "| 98381A304 | `cone-post-dowel` |" in readme
    assert "35fe64b899c1807f6e88b717a781138962a78c24e92e548b1f0d4b250a27c6cb" in readme


def test_drawing_is_the_purchased_reference_sheet() -> None:
    from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
    from _drawing_registry import DRAWINGS_BY_NAME

    import draw_cone_post_dowel as drawing

    spec = DRAWINGS_BY_NAME["cone_post_dowel"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert "build_purchased_fastener_drawing" in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )
    assert "draw_cone_post_dowel.py" in PRECISION_MIGRATED_DRAWINGS
