"""HIWIN HGR15R rail cut to 440 (MHA-CH-006-TL-30) contracts, SolidWorks-free."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path

import _config
import build_ch_rocker_arm_tl_oblique_rail as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_rail_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_rail as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

STEM = "ch-rocker-arm-tl-oblique-rail"
NAME = "ch_rocker_arm_tl_oblique_rail"
ROW = _config.parts(STEM)
STEEL_KG_PER_MM3 = 7.7e-6  # SOLIDWORKS "Alloy Steel"


def _shoelace(points):
    return (
        math.fsum(
            y0 * z1 - y1 * z0
            for (y0, z0), (y1, z1) in zip(points, points[1:] + points[:1])
        )
        / 2.0
    )


def test_registry_row_is_the_purchased_hiwin_rail() -> None:
    assert ROW["number"] == "MHA-CH-006-TL-30"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "Motion Constrained"
    assert ROW["supplier_skus"] == [spec.SKU] == ["172270559990"]
    assert ROW["material"] == spec.MATERIAL == "Alloy Steel"
    assert ROW["tolerance_class"] == "machined_block"
    assert "fit_class" not in ROW
    assert spec.MAKER_PART in ROW["stock_name"]
    # One line in the title block's MATERIAL cell; the provenance is the spec's.
    assert len(ROW["material_specification"]) <= 36
    assert spec.VENDOR_STEP in (spec.__doc__ or "")
    assert part.PART_NAME == STEM
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }


def test_quantity_is_one_rail_per_side() -> None:
    assert int(ROW["quantity"]) == fasteners.RAILS == 2
    # C4's rail-to-bar screws fill exactly this rail's holes.
    assert fasteners.RAIL_TO_BAR.count == spec.HOLE_COUNT * fasteners.RAILS


def test_calculator_values_are_imported_not_retyped() -> None:
    assert spec.LENGTH == trammel.RAIL_LENGTH == 440.0
    assert spec.WIDTH == trammel.RAIL_WIDTH == 15.0
    assert spec.HEIGHT == trammel.RAIL_HEIGHT == 15.0
    assert spec.HOLE_PITCH == trammel.RAIL_HOLE_PITCH == 60.0
    assert spec.HOLE_COUNT == trammel.RAIL_HOLE_COUNT == 7
    assert spec.HOLE_END == trammel.RAIL_HOLE_END == 40.0
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name, value in (
        ("LENGTH", "RAIL_LENGTH"),
        ("WIDTH", "RAIL_WIDTH"),
        ("HEIGHT", "RAIL_HEIGHT"),
        ("HOLE_PITCH", "RAIL_HOLE_PITCH"),
        ("HOLE_COUNT", "RAIL_HOLE_COUNT"),
        ("HOLE_END", "RAIL_HOLE_END"),
    ):
        assert re.search(rf"^{name} = trammel\.{value}\b", source, re.M), name
    assert re.search(
        r"^CBORE_DEPTH = HEIGHT - trammel\.RAIL_SCREW_SEAT_ABOVE_BASE", source, re.M
    )


def test_calculator_agrees_with_the_catalogue_and_vendor_rail() -> None:
    # The calculator's counterbore floor is the catalogue's h 5.3.
    assert math.isclose(spec.CBORE_DEPTH, spec.CATALOGUE_CBORE_DEPTH)
    assert (spec.HOLE_DIA, spec.CBORE_DIA) == (4.5, 7.5)
    # The special order: the vendor's standard 440 is 8 holes at E 10 on the
    # same pitch, ours 7 at E 40; both patterns are symmetric on the length.
    vendor_span = (spec.VENDOR_HOLE_COUNT - 1) * spec.HOLE_PITCH
    assert math.isclose(2 * spec.VENDOR_HOLE_END + vendor_span, spec.LENGTH)
    assert math.isclose(spec.HOLE_X[0] + spec.HOLE_X[-1], spec.LENGTH)
    assert spec.HOLE_X == (40.0, 100.0, 160.0, 220.0, 280.0, 340.0, 400.0)


def test_section_is_the_vendor_profile_in_the_part_frame() -> None:
    ys = [y for y, _ in spec.SECTION]
    zs = [z for _, z in spec.SECTION]
    assert (min(ys), max(ys)) == (-spec.WIDTH / 2.0, spec.WIDTH / 2.0)
    assert (min(zs), max(zs)) == (0.0, spec.HEIGHT)
    assert len(spec.SECTION) == 2 * len(spec.VENDOR_HALF_PROFILE)
    # Mirror-symmetric about the centre plane, counter-clockwise from +X.
    assert sorted(spec.SECTION) == sorted((-y, z) for y, z in spec.SECTION)
    area = _shoelace(spec.SECTION)
    assert area > 0.0
    assert math.isclose(area, spec.SECTION_AREA, rel_tol=1e-12)
    # The 0.7 x 45 deg foot chamfer clears the catalogue's r1 0.5 max fillet
    # at the base bar's locating shoulder.
    seat_end, chamfer_top = spec.VENDOR_HALF_PROFILE[:2]
    assert chamfer_top[0] - seat_end[0] > spec.SHOULDER_FILLET_MAX


def test_section_edges_never_cross() -> None:
    edges = list(zip(spec.SECTION, spec.SECTION[1:] + spec.SECTION[:1]))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if abs(i - j) <= 1 or {i, j} == {0, len(edges) - 1}:
                continue
            assert not (
                cross(a, b, c) * cross(a, b, d) < 0
                and cross(c, d, a) * cross(c, d, b) < 0
            ), (i, j)


def test_closed_form_volume_matches_the_vendor_step() -> None:
    hole = math.pi * 2.25**2 * (spec.HEIGHT - spec.CBORE_DEPTH)
    cbore = math.pi * 3.75**2 * spec.CBORE_DEPTH
    expected = _shoelace(spec.SECTION) * spec.LENGTH - spec.HOLE_COUNT * (hole + cbore)
    assert math.isclose(spec.VOLUME_MM3, expected, rel_tol=1e-12)
    # The vendor solid (8 holes) re-drilled to 7, plus the closed-form chord
    # fill of the raceway grooves less the R1 blends; what is left is the
    # vendor's ten R0.4 blends, its 0.1 deep logo and the dims' rounding.
    assert math.isclose(
        spec.VENDOR_EQUIVALENT_VOLUME_MM3,
        spec.VENDOR_VOLUME_MM3 + hole + cbore,
        rel_tol=1e-12,
    )
    residual = (
        spec.VOLUME_MM3
        - spec.VENDOR_EQUIVALENT_VOLUME_MM3
        - spec.GROOVE_FILL_MM2 * spec.LENGTH
    )
    assert abs(residual) < spec.VENDOR_VOLUME_ALLOWANCE_MM3 == 44.0
    # The groove fill is small against the section: the chords are faithful.
    assert 0.0 < spec.GROOVE_FILL_MM2 < 0.01 * spec.SECTION_AREA


def test_mass_matches_the_catalogue_rail_weight() -> None:
    kg_per_m = spec.VOLUME_MM3 * STEEL_KG_PER_MM3 / (spec.LENGTH / 1000.0)
    assert math.isclose(kg_per_m, spec.MASS_KG_PER_M, rel_tol=0.03)


def test_centroid_sits_on_the_centre_plane_at_mid_length() -> None:
    assert spec.CENTROID[:2] == (spec.LENGTH / 2.0, 0.0)
    assert 0.4 * spec.HEIGHT < spec.CENTROID[2] < spec.SECTION_CENTROID_Z


def test_spec_is_pure_data() -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    imports = set(re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE))
    assert imports <= {"__future__", "math", "ch_rocker_arm_tl_oblique_trammel_spec"}


def test_docstring_marks_every_source() -> None:
    doc = spec.__doc__ or ""
    for mark in ("VENDOR STEP", "SOURCED", "FROM THE CALCULATOR", "VENDOR-CHECKED"):
        assert mark in doc, mark
    assert spec.VENDOR_STEP in doc
    assert "datasheet-built: no vendor CAD obtained" in doc
    assert re.fullmatch(r"[0-9a-f]{64}", spec.VENDOR_STEP_SHA256)
    assert spec.VENDOR_DOWNLOADED == "2026-10-17"


def test_build_extrudes_the_section_then_drills_and_counterbores() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for needle in (
        'adapter.create_sketch("Right")',
        "u_axis=2, v_axis=1",
        'name_last_feature(adapter, "Rail")',
        'name_last_feature(adapter, "BoltHoles")',
        'name_last_feature(adapter, "Counterbores")',
        "both_directions=True",
        'volume_check(adapter, "rail", VOLUME_MM3, VOLUME_TOL_MM3)',
        'apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})',
    ):
        assert needle in source, needle


def test_sheet_is_the_registered_purchased_part_reference(monkeypatch) -> None:
    sheet = DRAWINGS_BY_NAME[NAME]
    assert draw.SPEC is sheet
    assert (sheet.part, sheet.artifact_stem, sheet.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert sheet.layout is DrawingLayout.LANDSCAPE
    calls = []

    async def fake(adapter, drawn, *, item, cut_to_suit=False):
        calls.append((adapter, drawn, item, cut_to_suit))
        return {"pdf": "x"}

    monkeypatch.setattr(draw, "build_purchased_part_drawing", fake)
    adapter = object()
    assert asyncio.run(draw.build(adapter)) == {"pdf": "x"}
    # Bought already cut to 440, so not cut to suit at assembly.
    assert calls == [(adapter, sheet, draw.ITEM, False)]
    assert "HGR15R" in draw.ITEM


def test_note_orders_the_base_bar_hole_pattern() -> None:
    assert spec.DRAWING_NOTES == (
        "SPECIAL ORDER: 7 HOLES AT 60 PITCH, 40 FROM EACH END, TO SUIT TL-20."
    )
    assert len(spec.DRAWING_NOTES) <= 80
