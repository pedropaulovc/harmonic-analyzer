"""Offline contracts for the MHA-CH-06-TL-VN-67 riser screw (McMaster 91771A112)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import _mcmaster_91771a112 as dims
import build_ch_rocker_arm_tl_vn_oblique_riser_screw as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_jig_assembly_spec as assembly
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_vn_oblique_riser_screw_spec as spec
import ch_rocker_arm_tl_oblique_riser_spec as riser
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91771A112 as recipe
from diagnostics.diag_mcmaster_phillips_flat_head import chain_segments
from diagnostics.sketch_profile import closed_loops, endpoint_merges
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

STEM = "ch-rocker-arm-tl-vn-oblique-riser-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91771A112",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-67"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_91771A112)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91771A112
    assert metadata.threaded is True


def test_quantity_thread_and_length_are_the_fastener_tables() -> None:
    row = fasteners.RISER_TO_CARRIER
    assert spec.ROW is row
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == row.count
    assert (dims.THREAD, dims.LENGTH_TEXT, fasteners.FLAT_HEAD) == (
        row.thread,
        row.length,
        row.head,
    )
    assert dims.DIMS.length == pytest.approx(row.length_mm)
    assert row.length_mm == pytest.approx(0.625 * IN)
    assert spec.CALLOUT == fasteners.callout(row) == "#4-40 X 5/8 B18.6.3 FLAT HEAD"
    # Installed as bought: the tip stops inside the carrier's tap.
    assert row.protrusion_mm < 0.0


def test_head_seats_nominally_below_the_riser_top() -> None:
    # Equal 82 deg cones: the Ø.212 flat top sits where the riser's countersink
    # narrows to it, not flush with the riser top.  Nominal seat only: no
    # head-angle tolerance is sourced or assumed.
    recess = (riser.CSK_DIA - 0.212 * IN) / (2.0 * math.tan(math.radians(41.0)))
    assert spec.HEAD_RECESS_NOMINAL == pytest.approx(recess)
    assert spec.HEAD_TOP_BELOW_RISER_TOP == spec.HEAD_RECESS_NOMINAL
    assert 0.0 < spec.HEAD_RECESS_NOMINAL < dims.DIMS.junction_depth
    assert spec.ROW.grip_mm == pytest.approx(riser.THICKNESS - spec.HEAD_RECESS_NOMINAL)
    with pytest.raises(ValueError):
        dims.DIMS.seated_recess(riser.CSK_DIA, 100.0)
    with pytest.raises(ValueError):
        dims.DIMS.seated_recess(dims.DIMS.head_dia - 0.01, riser.CSK_ANGLE)


def test_assembly_places_each_head_at_its_nominal_seat() -> None:
    z = trammel.CARRIER_TOP_Z + trammel.RISER_THICK - spec.HEAD_TOP_BELOW_RISER_TOP
    assert assembly.RISER_SCREW_PLACEMENTS == tuple(
        assembly._carried(point, z) for point in trammel.RISER_SCREWS
    )
    # The bought tip stops inside the nominal faced carrier.
    assert spec.TIP_BELOW_RISER_TOP_NOMINAL == pytest.approx(
        spec.HEAD_RECESS_NOMINAL + 0.625 * IN
    )
    assert spec.TIP_ABOVE_CARRIER_UNDERSIDE_NOMINAL == pytest.approx(
        riser.THICKNESS + carrier.THICKNESS - spec.TIP_BELOW_RISER_TOP_NOMINAL
    )
    assert spec.TIP_ABOVE_CARRIER_UNDERSIDE_NOMINAL > 0.0


def test_riser_screw_keeps_rule_18_full_thread() -> None:
    # Shortest catalogue screw, flush seat (no recess credit), thickest riser,
    # the carrier mouth break and the B18.6.3 2P maximum point.
    required = 1.5 * spec.ROW.major_mm
    assert spec.ENGAGEMENT_REQUIRED == pytest.approx(required)
    assert spec.LENGTH_MIN == pytest.approx((0.625 - 0.03) * IN)
    assert spec.POINT_CHAMFER_LENGTH_MAX == pytest.approx(2.0 * IN / 40.0)
    assert spec.SCREW_FULL_THREAD_REACH_MIN == pytest.approx(
        spec.LENGTH_MIN
        - (riser.THICKNESS + riser.THICKNESS_BAND)
        - carrier.TAP_MOUTH_BREAK
        - spec.POINT_CHAMFER_LENGTH_MAX
    )
    assert spec.RECEIVER_FULL_THREAD_MIN == carrier.ENGAGEMENT_MM[carrier.RISER_THREAD]
    assert spec.ENGAGEMENT_MIN == min(
        spec.SCREW_FULL_THREAD_REACH_MIN, spec.RECEIVER_FULL_THREAD_MIN
    )
    assert spec.ENGAGEMENT_MIN >= required


def test_factory_tip_stays_clear_below_the_carrier_at_the_plate_bands() -> None:
    # The longest screw at the nominal seat in the thinnest plates: whatever
    # it stands past the underside stays above the pivot-block tops and the
    # rails, and in plan no pivot block reaches a riser axis about any pin.
    stand_out = (
        dims.DIMS.length
        + spec.HEAD_RECESS_NOMINAL
        - (riser.THICKNESS - riser.THICKNESS_BAND)
        - (carrier.THICKNESS - carrier.THICKNESS_BAND)
    )
    assert spec.STAND_OUT_MAX_NOMINAL_SEAT == pytest.approx(stand_out)
    assert trammel.CARRIER_UNDERSIDE_Z - trammel.PIVOT_BLOCK_TOP_Z == pytest.approx(
        trammel.PIVOT_SUPPORT_HEIGHT
    )
    assert stand_out < trammel.PIVOT_SUPPORT_HEIGHT
    assert stand_out < trammel.CARRIER_TO_RAIL_GAP
    radius = max(
        math.dist((x, y), (pivot_block.BORE_X, 0.0))
        for x in (pivot_block.BLOCK_X0, pivot_block.BLOCK_X1)
        for y in (-pivot_block.BLOCK_WIDTH / 2.0, pivot_block.BLOCK_WIDTH / 2.0)
    )
    assert spec.PIVOT_BLOCK_PLAN_RADIUS == pytest.approx(radius)
    for axis in trammel.RISER_SCREWS:
        for pin in trammel.PIN_HOLES.values():
            assert math.dist(axis, pin) > radius + dims.DIMS.major_dia / 2.0
    assert spec.PIVOT_BLOCK_PLAN_CLEARANCE > 0.0


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_91771A112
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91771A11*.SLDPRT"))


def test_recipe_is_the_catalogue_screw() -> None:
    d = dims.DIMS
    assert d.part_no == spec.SKU
    assert d.major_dia == pytest.approx(0.112 * IN)
    assert d.pitch == pytest.approx(IN / 40.0)
    assert d.length == pytest.approx(0.625 * IN)
    assert d.head_dia == pytest.approx(0.212 * IN)
    assert d.head_dia <= trammel.RISER_SCREW_HEAD_DIA
    assert d.head_angle_deg == 82.0
    assert d.thread_top_depth == pytest.approx(0.067 * IN)  # catalogue head height
    assert d.junction_depth < d.thread_top_depth < spec.ROW.grip_mm


def test_recess_volume_matches_an_occ_boolean() -> None:
    # FreeCAD 1.1 boolean of the drafted cross-and-notch prism with the entry
    # cylinder and bottom cone, on the same-family 91771A110 recess form:
    # 5.086111 mm^3 (2026-10-17).
    assert dims.DIMS.recess_volume() == pytest.approx(5.086111, abs=1e-3)


def test_profiles_close() -> None:
    d = dims.DIMS
    for points, on_axis in (
        (tuple(seg[0] for seg in d.body_profile()), True),
        (tuple(seg[0] for seg in d.head_profile()), True),
        (tuple(seg[0] for seg in d.shank_profile()), True),
        (tuple(seg[0] for seg in d.refill_profile()), False),
        (d.cone_tip_profile(), True),
    ):
        segments = chain_segments(points)
        endpoint_merges(segments)
        assert len(closed_loops(segments)) == 1
        assert any(s.start[0] == 0.0 and s.end[0] == 0.0 for s in segments) is on_axis


def test_frame_puts_the_flat_top_at_y0() -> None:
    d = dims.DIMS
    ys = [p[1] for seg in d.body_profile() for p in seg]
    assert max(ys) == 0.0
    assert min(ys) == pytest.approx(-spec.ROW.length_mm)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'screw_axis_planes=("Front Plane", "Right Plane")' in source


def test_thread_chord_lies_on_the_head_cone_edge() -> None:
    # The thread Ø's line is the cone/major junction edge, not a chord drawn
    # across the threaded shank.
    d = dims.DIMS
    start = spec.SUPPLIER_REFERENCE_STARTS["SupplierThreadDiameter"]
    assert start == (-d.major_dia / 2.0, -d.junction_depth)
    assert ((d.head_dia / 2.0, 0.0), (-start[0], start[1])) in d.body_profile()


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_riser_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_riser_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES


def test_reserved_lanes_keep_the_views_in_projection() -> None:
    """Machinist review b344192: TOP and RIGHT sat .12 in off FRONT's axis/row."""
    import draw_ch_rocker_arm_tl_vn_oblique_riser_screw as drawing
    from _purchased_fastener_drawing import fastener_view_cells, supplier_fit_cells
    from _supplier_screw_layout import supplier_screw_margins

    raw = supplier_screw_margins(
        spec.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=spec.SUPPLIER_REFERENCE_PLANES,
        sides=spec.SUPPLIER_REFERENCE_SIDES,
    )
    aligned = drawing._aligned_margins(raw)
    # The same reserved views (the settled inventory guard), never a smaller lane.
    assert set(aligned) == set(raw) == {"*Front", "*Top"}
    for name, lanes in aligned.items():
        assert all(new >= old for new, old in zip(lanes, raw[name], strict=True))
    centres = {
        name: center
        for name, center, _cell in supplier_fit_cells(
            fastener_view_cells(0.07, layout="supplier_top"), aligned, label="riser"
        )
    }
    assert centres["*Top"][0] == pytest.approx(centres["*Front"][0], abs=1e-12)
    assert centres["*Right"][1] == pytest.approx(centres["*Front"][1], abs=1e-12)
    # The unbalanced reserve is what broke the projection.
    raw_centres = {
        name: center
        for name, center, _cell in supplier_fit_cells(
            fastener_view_cells(0.07, layout="supplier_top"), raw, label="riser"
        )
    }
    assert raw_centres["*Top"][0] != pytest.approx(raw_centres["*Front"][0], abs=1e-4)
