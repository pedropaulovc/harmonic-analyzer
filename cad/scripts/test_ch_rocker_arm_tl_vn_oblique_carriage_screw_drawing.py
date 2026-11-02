"""Offline contracts for the MHA-CH-06-TL-VN-64 carriage screw (McMaster 91290A168)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import _mcmaster_91290a168 as dims
import build_ch_rocker_arm_tl_vn_oblique_carriage_screw as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_carriage_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _socket_head_dimensions import SocketHeadScrew
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91290A168 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-carriage-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91290A168",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-64"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    # Cut to fit at assembly (owner ruling 2026-11-01): the note names the
    # jig step that owns the fit-up, the general line says "cut at assembly".
    assert row["installation_notes"].strip() == (
        "CUT EACH TO ITS OWN COUNTERBORE FLOOR PER MHA-CH-06-TL-00 STEP 5."
    )
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    # The cut end is bare steel; the finish cell says how to protect it.
    assert row["finish"] == "black oxide as supplied; oil the cut end"
    metadata = recipe_declaration(spec.SKU, recipe.build_91290A168)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91290A168
    assert metadata.threaded is True


def test_quantity_thread_and_length_are_the_fastener_tables() -> None:
    row = fasteners.BLOCK_TO_CARRIAGE
    assert spec.ROW is row
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == row.count
    assert (dims.THREAD, dims.LENGTH_TEXT, fasteners.SHCS) == (
        row.thread,
        row.length,
        row.head,
    )
    assert dims.DIMS.length == pytest.approx(row.length_mm)
    assert dims.DIMS.major_dia == pytest.approx(row.major_mm, abs=1e-3)
    assert spec.CALLOUT == fasteners.callout(row) == "M4 X 20 SHCS"


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_91290A168
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91290A168*.SLDPRT"))


def test_recipe_is_the_catalogue_screw() -> None:
    d = dims.DIMS
    assert d.part_no == spec.SKU
    assert d.major_dia == pytest.approx(4.0)
    assert d.pitch == pytest.approx(0.7)
    assert d.length == pytest.approx(20.0)
    assert d.head_dia == pytest.approx(7.0)
    assert d.head_h == pytest.approx(4.0)
    assert d.socket_af == pytest.approx(3.0)
    assert d.socket_depth == pytest.approx(2.0)  # standard minimum key engagement
    assert d.fully_threaded


def test_dimension_record_is_the_91251a_familys() -> None:
    assert type(dims.DIMS) is SocketHeadScrew
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "build_socket_head(adapter, DIMS)" in source
    assert "build_socket_head_catalog(adapter, DIMS)" in source


def test_frame_puts_the_bearing_face_at_y0() -> None:
    d = dims.DIMS
    assert d.underside_y == 0.0
    assert d.top_y == pytest.approx(d.head_h)
    assert d.tip_y == pytest.approx(-spec.ROW.length_mm)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'screw_axis_planes=("Front Plane", "Right Plane")' in source


def test_modelled_as_cut_to_fit_from_the_bought_screw() -> None:
    """Owner ruling 2026-11-01 (option A): each screw is cut to its own
    counterbore floor, so the part is the installed cut screw at the nominal
    .570 floor, the sheet's length a reference and the 20 mm a stock witness."""
    import ch_rocker_arm_tl_oblique_pivot_block_spec as block

    assert (
        spec.CUT_LENGTH
        == spec.ROW.cut_length_mm
        == pytest.approx(block.CBORE_FLOOR + block.SCREW_REACH)
    )
    assert spec.CUT_LENGTH == pytest.approx((0.570 + 0.189) * IN)
    assert block.SCREW_CUT_LENGTH_MAX < dims.DIMS.length - block.SCREW_LENGTH_TOL
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'parameters={"cut_length": supplier.CUT_LENGTH}' in source
    recipe_source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert (
        "build_socket_head(adapter, replace(DIMS, length=cut_length))" in recipe_source
    )
    references = {name: value for name, value, _ in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert references["CutLength"] == -spec.CUT_LENGTH
    assert references["SupplierLength"] == -dims.DIMS.length
    assert spec.SUPPLIER_REFERENCE_FORMATS["CutLength"][3] == "CUT TO FIT"
    assert (
        spec.SUPPLIER_REFERENCE_FORMATS["SupplierLength"][3]
        == "AS-SUPPLIED STOCK LENGTH"
    )
    # The stock witness's lane stands left of the solid; its chord runs down
    # the shank's left edge into the phantom uncut tip (machinist review: a
    # carrier beside the head printed as a loose dashed line), and the thread
    # Ø's chord lies on the cut end rather than across the shank.
    assert spec.SUPPLIER_REFERENCE_SIDES["SupplierLength"] == "left"
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierLength"] == (-dims.DIMS.major_dia / 2.0, 0.0)
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierThreadDiameter"] == (
        -dims.DIMS.major_dia / 2.0,
        -spec.CUT_LENGTH,
    )
    draw_source = (
        Path(part.__file__).parent
        / "draw_ch_rocker_arm_tl_vn_oblique_carriage_screw.py"
    ).read_text(encoding="utf-8")
    assert "cut_to_suit=True" in draw_source


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_carriage_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_carriage_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES


def test_lengths_shelve_either_side_of_the_screw_and_head_height_clears_them() -> None:
    """Machinist review: the two qualifiers crossed the thread and collided,
    and the 20 mm's line struck the (4 mm) text on its extension line."""
    import draw_ch_rocker_arm_tl_vn_oblique_carriage_screw as drawing
    from _supplier_screw_layout import supplier_screw_lane_plan

    lanes = supplier_screw_lane_plan(
        spec.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=spec.SUPPLIER_REFERENCE_PLANES,
        sides=spec.SUPPLIER_REFERENCE_SIDES,
    )
    assert lanes["SupplierLength"][0] == drawing.SHELVES["SupplierLength"][1] == "left"
    assert lanes["CutLength"][0] == drawing.SHELVES["CutLength"][1] == "right"
    assert set(drawing.SHELVES) == {
        name for name, _value, _orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS
    }
    assert set(drawing.ARROWS_INSIDE) == {"SupplierLength", "CutLength"}
    assert drawing.LIFTED == "SupplierHeadHeight"
    # The stock-length lane plus its widest qualifier fits the left reserve.
    assert drawing.SUPPLIER_MARGINS["*Front"][0] > lanes["SupplierLength"][1] + 0.062
    sides = {name: (m[0], m[2]) for name, m in drawing.SUPPLIER_MARGINS.items()}
    assert sides["*Front"] == sides["*Top"]


def test_uncut_tip_phantom_closes_the_stock_witness() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_carriage_screw as drawing

    r = dims.DIMS.major_dia / 2000.0
    cut, stock = -spec.CUT_LENGTH / 1000.0, -dims.DIMS.length / 1000.0
    ends = drawing._uncut_tip_ends()
    assert ends == {
        "left": ((-r, cut, 0.0), (-r, stock, 0.0)),
        "end": ((-r, stock, 0.0), (r, stock, 0.0)),
        "right": ((r, stock, 0.0), (r, cut, 0.0)),
    }
    # The stock witness's chord ends where the phantom's end line starts.
    x, y = spec.SUPPLIER_REFERENCE_STARTS["SupplierLength"]
    assert (x / 1000.0, (y - dims.DIMS.length) / 1000.0, 0.0) == ends["end"][0]
    assert drawing._PHANTOM_LINE_STYLE == 2  # swLineStyles_e.swLinePHANTOM
