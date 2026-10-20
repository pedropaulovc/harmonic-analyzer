"""Offline contracts for the MHA-CH-06-TL-VN-52 pivot bearing (McMaster 5972K41)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import _mcmaster_5972k41 as dims
import build_ch_rocker_arm_tl_vn_oblique_bearing as part
import ch_rocker_arm_tl_vn_oblique_bearing_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_5972K41 as recipe
from diagnostics.sketch_profile import Arc, Line, closed_loops, endpoint_merges

STEM = "ch-rocker-arm-tl-vn-oblique-bearing"

# The vendor STEP read by FreeCAD 1.1 on 2026-10-17 (dt-logs
# trammel-bought/vendor-cad/bd-freecad-harvest.json): volume per body, mm^3.
VENDOR_VOLUMES = {
    "outer ring": 1427.660359,
    "inner ring": 602.244065,
    "seal": 209.873107,
    "ball": 196.337672,
    "total": 3824.014343,
}
# The recipe's closed form reproduces the vendor STEP to 0.02 %.
VOLUME_REL = 2e-4


def _points(segments) -> set[tuple[float, float]]:
    return {point for segment in segments for point in (segment.start, segment.end)}


def test_catalogue_row_is_the_registered_mcmaster_bearing() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("5972K41",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-52"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert int(row["quantity"]) == spec.QUANTITY == 4  # two per pivot block
    assert jig.QUANTITIES[STEM] == spec.QUANTITY
    metadata = recipe_declaration(spec.SKU, recipe.build_5972K41)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_5972K41
    assert metadata.threaded is False


def test_standalone_recipe_run_is_catalog_only() -> None:
    """Not replica-gated (user ruling 2026-10-17): the standalone command must
    not enter the McMaster replica path, which demands a vendor SLDPRT and its
    harvest."""
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert recipe.PART_NO == spec.SKU
    assert REGISTRY[spec.SKU] is recipe.build_5972K41
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main(" not in source and "import replica_main" not in source
    assert "run_build(build_catalog)" in source
    assert "catalog-only" in (recipe.__doc__ or "")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/5972K41*.SLDPRT"))


def test_envelope_is_the_calculators_bearing() -> None:
    assert (spec.BORE, spec.OD, spec.WIDTH) == (10.0, 30.0, 9.0)
    assert (dims.BORE, dims.OD, dims.WIDTH) == (
        trammel.BEARING_BORE,
        trammel.BEARING_OD,
        trammel.BEARING_WIDTH,
    )
    assert spec.RADIAL_PLAY == trammel.BEARING_RADIAL_PLAY
    text = _config.parts(STEM)["material_specification"]
    assert re.search(r"\b10 x 30 x 9\b", text), text


def test_rings_carry_the_nominal_bore_od_and_width_exactly() -> None:
    outer, inner = recipe.outer_ring_section(), recipe.inner_ring_section()
    outer_points, inner_points = _points(outer), _points(inner)
    assert max(r for r, _ in outer_points) == spec.OD / 2.0
    assert min(r for r, _ in inner_points) == spec.BORE / 2.0
    for points in (outer_points, inner_points):
        assert min(y for _, y in points) == 0.0
        assert max(y for _, y in points) == spec.WIDTH
    # Full-width OD and bore faces between the 0.45 chamfers.
    c = dims.RING_CHAMFER
    assert Line((spec.OD / 2.0, c), (spec.OD / 2.0, spec.WIDTH - c)) in outer
    assert Line((spec.BORE / 2.0, spec.WIDTH - c), (spec.BORE / 2.0, c)) in inner


def test_every_body_section_is_one_closed_loop() -> None:
    sections = [
        recipe.outer_ring_section(),
        recipe.inner_ring_section(),
        recipe.seal_section(far=False),
        recipe.seal_section(far=True),
    ] + [recipe.ball_section(k) for k in range(dims.BALL_COUNT)]
    assert len(sections) == len(recipe.BODY_NAMES) == 11
    for segments in sections:
        endpoint_merges(segments)
        assert len(closed_loops(segments)) == 1


def test_balls_sit_in_both_grooves_and_touch_both_seals() -> None:
    groove_r = math.hypot(
        (dims.OUTER_LAND_DIA - dims.PITCH_DIA) / 2.0, dims.GROOVE_HALF_WIDTH
    )
    assert dims.BALL_DIA / 2.0 == pytest.approx(groove_r)
    assert dims.BALL_DIA / 2.0 == pytest.approx(math.sqrt(13.0))
    near = recipe.seal_section(far=False)
    inner_face = max(y for _, y in _points(near))
    assert inner_face == pytest.approx(spec.WIDTH / 2.0 - dims.BALL_DIA / 2.0)
    for k in range(dims.BALL_COUNT):
        arc, diameter = recipe.ball_section(k)
        assert isinstance(arc, Arc)
        assert math.hypot(*arc.center) == pytest.approx(dims.PITCH_DIA / 2.0)
        assert math.dist(diameter.start, diameter.end) == pytest.approx(dims.BALL_DIA)


def test_seals_mirror_about_mid_width() -> None:
    near = sorted(_points(recipe.seal_section(far=False)))
    far = sorted(
        (r, round(spec.WIDTH - y, 9)) for r, y in _points(recipe.seal_section(far=True))
    )
    assert far == [(r, round(y, 9)) for r, y in near]


@pytest.mark.parametrize(
    ("label", "volume"),
    [
        ("outer ring", dims.outer_ring_volume),
        ("inner ring", dims.inner_ring_volume),
        ("seal", dims.seal_volume),
        ("ball", dims.ball_volume),
        ("total", dims.total_volume),
    ],
)
def test_closed_form_volume_is_the_vendor_steps(label, volume) -> None:
    assert volume() == pytest.approx(VENDOR_VOLUMES[label], rel=VOLUME_REL)


def test_frame_and_bodies_are_declared() -> None:
    assert recipe.BODY_NAMES == (
        "OuterRing",
        "InnerRing",
        "NearSeal",
        "FarSeal",
        *(f"Ball{k}" for k in range(1, 8)),
    )
    # One side face of both rings at y = 0 (the Top Plane).
    for section in (recipe.outer_ring_section(), recipe.inner_ring_section()):
        assert any(s.start[1] == s.end[1] == 0.0 for s in section)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'screw_axis_planes=("Front Plane", "Right Plane")' in source


def test_joints_are_presses_owned_by_the_pin_and_block() -> None:
    assert spec.PIN_SECTION_DIA > spec.BORE
    assert spec.SEAT_DIA < spec.OD
    assert 0.0 < spec.PIN_INTERFERENCE[0] <= spec.PIN_INTERFERENCE[1]
    assert 0.0 < spec.SEAT_INTERFERENCE[0] <= spec.SEAT_INTERFERENCE[1]
    assert spec.CHAMFER_MODELLED < spec.CHAMFER_STANDARD_MIN == 0.6


def test_the_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
    flat = " ".join(lines)
    assert "OUTER RING" in flat and "INNER RING" in flat


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_bearing as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_bearing"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
