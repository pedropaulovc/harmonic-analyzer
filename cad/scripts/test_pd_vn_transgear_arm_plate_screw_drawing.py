"""Offline contracts for the MHA-PD-VN-56 transgear arm-plate screws."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path

import pytest

import _config
import build_pd_vn_transgear_arm_plate_screw as part
import draw_pd_vn_transgear_arm_plate_screw as drawing
import pd_transgear_arm_geometry as arm
import pd_transgear_arm_plate_geometry as plate
import pd_vn_transgear_arm_plate_screw_spec as screw
import transgear_hanger_joints as joints
from _drawing_registry import DRAWINGS_BY_NAME
from diagnostics import diag_build_91790A199 as entry
from diagnostics import diag_mcmaster_oval as recipe

IN = 25.4


def test_spec_is_the_catalogue_screw() -> None:
    """Verified 91790A199: 8-32 x 1 inch from the bevel top, standard oval.

    Catalogue head height 0.152 and crown 0.052 are reference dimensions,
    not supplied head/length tolerance bands or actual receipt readings.
    """
    assert screw.SKU == "91790A199"
    assert entry.PART_NO == screw.SKU
    assert screw.THREAD == "#8-32"
    assert screw.THREAD_MAJOR == pytest.approx(0.164 * IN)
    assert screw.PITCH == pytest.approx(IN / 32.0)
    assert screw.STOCK_LENGTH == pytest.approx(IN)
    assert screw.HEAD_DIA == pytest.approx(0.312 * IN)
    assert screw.HEAD_H == pytest.approx(0.152 * IN)
    assert screw.CROWN_H == pytest.approx(0.052 * IN)
    assert screw.HEAD_ANGLE_DEG == 82.0
    # The shared recipe's row is the supplied screw, not the cut one.
    assert recipe.OVAL_SIZES[screw.SKU] == (
        screw.THREAD_MAJOR,
        screw.STOCK_LENGTH,
        screw.HEAD_DIA,
        screw.CROWN_H,
        screw.HEAD_ANGLE_DEG,
        screw.PITCH,
    )


def test_the_cut_is_flush_with_the_arm_front_face() -> None:
    """Bevel top flush with the plate's rear face, so the tip is flush with
    the arm's front face after the plate's over-arm section and the arm."""
    assert screw.CUT_LENGTH == pytest.approx(plate.THICKNESS_OVER_ARM + arm.THICKNESS)
    assert screw.LENGTH == screw.CUT_LENGTH
    assert screw.CUT_END_BREAK_MAX == pytest.approx(0.1016)  # .004
    assert joints.PLATE_SCREW_STOCK_LEAD_MARGIN_MM > 0.0


def _junction_y() -> float:
    """Where an 82 deg cone from the Ø HEAD_DIA rim at y = 0 meets the
    thread major (independent of the recipe's own arithmetic)."""
    half = math.radians(screw.HEAD_ANGLE_DEG / 2.0)
    return -(screw.HEAD_DIA - screw.THREAD_MAJOR) / 2.0 / math.tan(half)


@pytest.mark.parametrize(
    ("cut_length", "cut_end_break"),
    [
        (screw.CUT_LENGTH, None),  # half a cut
        (None, screw.CUT_END_BREAK_MAX),
        (screw.STOCK_LENGTH, screw.CUT_END_BREAK_MAX),  # leaves the factory tip
        (screw.CUT_LENGTH, 0.0),  # an unbroken cut end
        (-_junction_y(), screw.CUT_END_BREAK_MAX),  # no shank under the bevel
    ],
)
def test_recipe_refuses_a_cut_it_cannot_draw(cut_length, cut_end_break) -> None:
    with pytest.raises(ValueError):
        recipe.revolved_volume(screw.SKU, cut_length, cut_end_break)


def test_standalone_recipe_run_is_catalog_only(monkeypatch) -> None:
    """No vendor model: the standalone run builds, checks and saves the
    catalog recipe and never enters the McMaster replica path, which demands
    a vendor SLDPRT and its harvest."""
    assert not hasattr(entry, "replica_main")
    seen: list = []

    async def fake_catalog_run(adapter, part_no, builder):
        seen.append((part_no, builder))
        return {}

    monkeypatch.setattr(entry, "catalog_run", fake_catalog_run)
    asyncio.run(entry.build_catalog(None))
    assert seen == [(screw.SKU, entry.build_91790A199)]


def test_no_vendor_model_of_the_new_hardware_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{screw.SKU}*.SLDPRT"))


# A size on the sheet's registry-printed fields: a thread (#8-32), a fraction,
# a length with units, or an "x" between numbers.  The 18-8 grade is not one.
_SIZE = re.compile(r"#\d|\d+/\d+|\d\s*(?:mm|in\b|\")|\d\s*[xX]\s*\d|°")


def test_sheet_points_to_the_cut_step_and_no_size_in_the_registry_names() -> None:
    """The ordinary purchased reference sheet carries the actual stock identity;
    the cut is MHA-PD-00's step, which the general line cites by number."""
    import pd_paper_drive_assembly_steps as steps

    row = _config.parts(part.PART_NAME)
    for field in ("title", "stock_name", "supplier", "finish", "material"):
        assert not _SIZE.search(str(row[field])), (field, row[field])
    assert "installation_notes" not in row
    assert drawing.CUT_STEP == steps.step_number("arm-plate-screws-cut")
    assert f"MHA-PD-00 STEP {drawing.CUT_STEP}" in drawing.GENERAL_TEXT


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["pd_vn_transgear_arm_plate_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )


def test_sheet_prints_only_the_replacement_sizes(monkeypatch) -> None:
    from _supplier_screw_layout import supplier_screw_lane_plan, supplier_screw_margins

    rows = drawing._printed_rows()
    assert tuple(name for name, _, _ in rows) == drawing.PRINTED_REFERENCES
    assert all(orientation != "angle" for _, _, orientation in rows)
    # The part still authors these; ITEM and a standard oval head imply them.
    authored = {name for name, _, _ in screw.SUPPLIER_REFERENCE_DIMENSIONS}
    assert authored - set(drawing.PRINTED_REFERENCES) == {
        "SupplierHeadAngle",
        "SupplierCrownHeight",
        "SupplierStockLength",
        "SupplierNominalThreadMajor",
    }
    planes = drawing._printed(screw.SUPPLIER_REFERENCE_PLANES)
    sides = drawing._printed(screw.SUPPLIER_REFERENCE_SIDES)
    plan = supplier_screw_lane_plan(rows, planes=planes, sides=sides)
    assert set(plan) == set(drawing.PRINTED_REFERENCES)
    # Only TOP is reserved, so only TOP may carry imported dimensions; FRONT
    # and RIGHT stay centred in their cells, in projection with TOP.
    margins = supplier_screw_margins(rows, planes=planes, sides=sides)
    assert set(margins) == {"*Top"}
    left, _bottom, right, _top = margins["*Top"]
    assert left == right
    formats = drawing._printed(screw.SUPPLIER_REFERENCE_FORMATS)
    assert formats == {
        "SupplierHeadDiameter": screw.SUPPLIER_REFERENCE_FORMATS["SupplierHeadDiameter"]
    }
    assert "supplier_top" in drawing.build.__code__.co_consts
    monkeypatch.setattr(
        drawing, "PRINTED_REFERENCES", ("SupplierStockLength", "SupplierMissing")
    )
    with pytest.raises(ValueError, match="SupplierMissing"):
        drawing._printed_rows()
