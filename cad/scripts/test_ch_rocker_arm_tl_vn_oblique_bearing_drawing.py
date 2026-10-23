"""Offline contracts for the MHA-CH-06-TL-VN-52 pivot bearing (McMaster 5972K41)."""

from __future__ import annotations

import math

import pytest

import _config
import _mcmaster_5972k41 as dims
import build_ch_rocker_arm_tl_vn_oblique_bearing as part
import ch_rocker_arm_tl_vn_oblique_bearing_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
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


def test_joints_are_presses_owned_by_the_pin_and_block() -> None:
    assert spec.PIN_SECTION_DIA > spec.BORE
    assert spec.SEAT_DIA < spec.OD
    assert spec.PIN_INTERFERENCE == pytest.approx((0.001, 0.015))
    assert spec.SEAT_INTERFERENCE == pytest.approx((0.002, 0.024))
