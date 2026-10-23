"""ZYLtech Tr8x2 brass flange nut (MHA-CH-06-TL-VN-55) contracts, SolidWorks-free."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_vn_oblique_leadscrew_nut as part
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as spec
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed
import draw_ch_rocker_arm_tl_vn_oblique_leadscrew_nut as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

STEM = "ch-rocker-arm-tl-vn-oblique-leadscrew-nut"
NAME = "ch_rocker_arm_tl_vn_oblique_leadscrew_nut"
ROW = _config.parts(STEM)


def test_registry_row_is_the_purchased_zyltech_nut() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-55"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER
    assert ROW["supplier_skus"] == [spec.SKU] == ["HW-SC-T8x2-NUT"]
    assert ROW["material"] == spec.MATERIAL
    assert int(ROW["quantity"]) == spec.QUANTITY == 1
    # One line in the title block's MATERIAL cell; the provenance is the spec's.
    assert len(ROW["material_specification"]) <= 36
    assert spec.SKU in (spec.__doc__ or "")
    assert "Datasheet-built" in (spec.__doc__ or "")
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }
    assert spec.INVENTORY_ID == "fixtures.trammel-tr8-flange-nut"


def test_c4_values_are_imported_not_retyped() -> None:
    assert spec.FLANGE_DIA == feed.NUT_FLANGE_DIA
    assert spec.FLANGE_THICK == feed.NUT_FLANGE_THICK
    assert spec.HOLE_DIA == feed.NUT_HOLE_DIA
    assert spec.HOLE_PCD == feed.NUT_HOLE_PCD
    assert spec.HOLE_ANGLES_DEG == feed.NUT_HOLE_ANGLES_DEG
    assert spec.BODY_DIA == feed.NUT_BODY_DIA
    assert spec.LENGTH == feed.NUT_LENGTH
    assert spec.SPIGOT_LENGTH == feed.NUT_BODY_SHORT
    assert spec.BODY_LONG == feed.NUT_BODY_LONG
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name in ("FLANGE_DIA", "FLANGE_THICK", "HOLE_PCD", "BODY_DIA", "LENGTH"):
        assert re.search(rf"^{name} = feed\.", source, re.MULTILINE), name


def test_frame_puts_the_flange_bracket_face_at_zero() -> None:
    ys = [y for _, y in spec.PROFILE]
    assert min(ys) == -spec.SPIGOT_LENGTH
    assert max(ys) == spec.FLANGE_THICK + spec.BODY_LONG
    assert max(ys) - min(ys) == spec.LENGTH
    flange = [y for r, y in spec.PROFILE if r == spec.FLANGE_DIA / 2.0]
    assert flange == [0.0, spec.FLANGE_THICK]
    # C4 seats the flange's spigot face on TL-29 with the long body proud.
    assert feed.NUT_FLANGE_X[1] - feed.NUT_FLANGE_X[0] == pytest.approx(
        spec.FLANGE_THICK
    )


def test_bore_is_the_contract_thread_minor_not_the_ooznest_crest() -> None:
    assert min(r for r, _ in spec.PROFILE) == spec.BORE_DIA / 2.0 == 3.0
    assert spec.OOZNEST_CREST_DIA > spec.BORE_DIA
    assert spec.BORE_DIA < feed.SCREW_MAJOR_DIA


def test_holes_are_the_45_degree_square_on_the_pcd() -> None:
    a = spec.HOLE_PCD / 2.0 * math.sqrt(0.5)
    expected = sorted((sx * a, sz * a) for sx in (-1.0, 1.0) for sz in (-1.0, 1.0))
    for got, want in zip(sorted(spec.HOLE_CENTRES), expected, strict=True):
        assert got == pytest.approx(want, abs=1e-8)
    # Symmetric about both axes, so the Top sketch's z sign is moot.
    assert sorted(part.hole_sketch_points()) == sorted(spec.HOLE_CENTRES)


def test_volume_is_the_revolve_less_four_holes() -> None:
    r_b, r_d, r_f = spec.BORE_DIA / 2.0, spec.BODY_DIA / 2.0, spec.FLANGE_DIA / 2.0
    body = math.pi * (r_d**2 - r_b**2) * spec.LENGTH
    flange = math.pi * (r_f**2 - r_d**2) * spec.FLANGE_THICK
    holes = 4 * math.pi * (spec.HOLE_DIA / 2.0) ** 2 * spec.FLANGE_THICK
    assert spec.VOLUME_MM3 == pytest.approx(body + flange - holes, rel=1e-12)


def test_build_sketches_the_spec_profile() -> None:
    assert part.profile_points() == list(spec.PROFILE)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'volume_check(adapter, "flange nut", VOLUME_MM3' in source
    assert "publish_screw_axis(adapter)" in source


def test_spec_is_pure_data() -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE)
    assert set(imports) <= {
        "__future__",
        "math",
        "ch_rocker_arm_tl_vn_oblique_leadscrew_spec",
    }


def test_sheet_is_the_registered_purchased_part_reference() -> None:
    sheet = DRAWINGS_BY_NAME[NAME]
    assert (sheet.part, sheet.artifact_stem, sheet.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert sheet.layout is DrawingLayout.LANDSCAPE
    assert sheet.artifact_stem == part.PART_NAME
    assert "FLANGE NUT" in draw.ITEM


def test_note_is_one_short_line_without_numbers() -> None:
    note = spec.DRAWING_NOTES
    assert "\n" not in note and len(note) <= 80
    assert not re.search(r"\d", note)


def test_supplier_references_are_the_drop_in_interface() -> None:
    rows = {name: (value, orientation) for name, value, orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert rows == {
        "SupplierLength": (spec.LENGTH, "vertical"),
        "SupplierFlangeThickness": (spec.FLANGE_THICK, "vertical"),
        "SupplierBodyDiameter": (spec.BODY_DIA, "horizontal"),
        "SupplierFlangeDiameter": (spec.FLANGE_DIA, "horizontal"),
        "SupplierMountingHoleDiameter": (spec.HOLE_DIA, "vertical"),
        "SupplierHolePitchDiameter": (spec.HOLE_PCD, "vertical"),
    }
    assert set(spec.SUPPLIER_REFERENCE_STARTS) == set(rows) == set(spec.SUPPLIER_REFERENCE_FORMATS)
    # The end view carries the flange OD and the bolt pattern; the side view
    # the two lengths and the pilot.
    assert spec.SUPPLIER_REFERENCE_PLANES == {
        "SupplierFlangeDiameter": "Top",
        "SupplierMountingHoleDiameter": "Top",
        "SupplierHolePitchDiameter": "Top",
    }
    assert spec.SUPPLIER_REFERENCE_SIDES == {"SupplierBodyDiameter": "bottom"}

    def chord(name: str) -> tuple[tuple[float, float], tuple[float, float]]:
        (x, y), (value, orientation) = spec.SUPPLIER_REFERENCE_STARTS[name], rows[name]
        return (x, y), (x + value, y) if orientation == "horizontal" else (x, y + value)

    # Front sketch (x = radius, y = station). The printed construction chords
    # lie on the axis or on visible edges, never across a face: the overall
    # length on the axis, the flange thickness on the flange rim, the pilot on
    # the spigot's end face.
    assert chord("SupplierLength") == ((0.0, -spec.SPIGOT_LENGTH), (0.0, spec.FAR_END_Y))
    assert chord("SupplierFlangeThickness") == (
        (-spec.FLANGE_DIA / 2.0, 0.0),
        (-spec.FLANGE_DIA / 2.0, spec.FLANGE_THICK),
    )
    assert chord("SupplierBodyDiameter") == (
        (-spec.BODY_DIA / 2.0, -spec.SPIGOT_LENGTH),
        (spec.BODY_DIA / 2.0, -spec.SPIGOT_LENGTH),
    )
    # Top sketch reads model (x, -z): every chord crosses its circle's centre,
    # the flange OD and the pitch circle on the view's centrelines.
    assert chord("SupplierFlangeDiameter") == ((-spec.FLANGE_DIA / 2.0, 0.0), (spec.FLANGE_DIA / 2.0, 0.0))
    (hx, hy0), (_, hy1) = chord("SupplierMountingHoleDiameter")
    centre_x, centre_z = spec.HOLE_CENTRES[0]
    assert hx == centre_x
    assert (hy0 + hy1) / 2.0 == pytest.approx(-centre_z, abs=1e-12)
    assert chord("SupplierHolePitchDiameter") == ((0.0, -spec.HOLE_PCD / 2.0), (0.0, spec.HOLE_PCD / 2.0))


def test_every_chord_shelves_its_text_outward() -> None:
    from _supplier_screw_layout import supplier_screw_lane_plan

    lanes = supplier_screw_lane_plan(
        spec.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=spec.SUPPLIER_REFERENCE_PLANES,
        sides=spec.SUPPLIER_REFERENCE_SIDES,
    )
    rows = {name: orientation for name, _, orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    # At 1:1 each horizontal text is wider than its span or crosses its own
    # vertical dimension line, so every one moves clear of its own ink.
    assert set(draw.TEXT_SHELVES) == set(rows)
    for name, side in draw.TEXT_SHELVES.items():
        assert side in ("left", "right")
        if rows[name] == "vertical":
            # Away from the view, beyond the lane's own dimension line.
            assert side == lanes[name][0], name


def test_shelf_gap_measures_clearance_on_the_shelf_side() -> None:
    from types import SimpleNamespace

    text = SimpleNamespace(xmin=0.070, xmax=0.095)
    actual = {"left": 0.097, "right": 0.108, "text": text}
    assert draw._shelf_gap("SupplierHolePitchDiameter", actual) == pytest.approx(0.002)
    text = SimpleNamespace(xmin=0.135, xmax=0.160)
    actual = {"left": 0.118, "right": 0.133, "text": text}
    assert draw._shelf_gap("SupplierMountingHoleDiameter", actual) == pytest.approx(0.002)


def test_sheet_fits_its_title_cells_and_selects_the_tall_top_layout() -> None:
    import _purchased_title_fit as title_fit

    assert draw.TITLE_BLOCK_SETUP.func is title_fit.fit_purchased_title_block
    assert draw.TITLE_BLOCK_SETUP.keywords == {"spec": draw.SPEC}
    assert draw.VIEW_LAYOUT == "tall_top"
    assert not hasattr(draw, "SUPPLIER_DATA")


def test_hidden_line_guard_refuses_any_orthographic_view_not_hlr() -> None:
    from _drawing_view_display import _SW_HLR

    class View:
        def __init__(self, mode: int) -> None:
            self.mode = mode

        def GetDisplayMode2(self) -> int:
            return self.mode

    views = {name: View(_SW_HLR) for name in ("*Front", "*Top", "*Right")}
    draw._assert_hidden_lines_removed(views)
    views["*Front"].mode = 1  # swHIDDEN_GREYED
    with pytest.raises(RuntimeError, match="Front"):
        draw._assert_hidden_lines_removed(views)


# Native ``GetOutline`` at farm run 20261023T163903809Z (e04fd60ab): every
# orthographic view measured its model extent times the scale plus a constant
# 11.176 mm of sheet-space padding (Front/Right 22 x 15, Top 22 x 22 mm).
_NATIVE_PADDING_M = 0.011176
_MODEL_EXTENT_MM = {
    "*Front": (spec.FLANGE_DIA, spec.LENGTH),
    "*Top": (spec.FLANGE_DIA, spec.FLANGE_DIA),
    "*Right": (spec.FLANGE_DIA, spec.LENGTH),
}


class _PaddedView:
    def __init__(self, orientation: str, center: tuple[float, float]) -> None:
        self._orientation = orientation
        self._center = center
        self.UseSheetScale = 0
        self.ScaleRatio = (1.0, 1.0)

    @property
    def Position(self) -> tuple[float, float]:
        return self._center

    def GetOrientationName(self) -> str:
        return self._orientation

    def UpdateViewDisplayGeometry(self) -> None:
        return None

    def GetOutline(self) -> tuple[float, float, float, float]:
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        width, height = (
            extent / 1000.0 * ratio + _NATIVE_PADDING_M for extent in _MODEL_EXTENT_MM[self._orientation]
        )
        x, y = self._center
        return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)

    def SetViewPosition(self, position, _update) -> bool:
        self._center = tuple(position)
        return True


class _Drawing:
    @staticmethod
    def EditRebuild3() -> bool:
        return True


def _fit_orthographic(
    monkeypatch,
    dimensions=spec.SUPPLIER_REFERENCE_DIMENSIONS,
    planes=spec.SUPPLIER_REFERENCE_PLANES,
    *,
    sides=spec.SUPPLIER_REFERENCE_SIDES,
    layout=draw.VIEW_LAYOUT,
    supplier_data=(),
) -> tuple[int, int]:
    import _purchased_fastener_drawing as purchased
    from _supplier_screw_layout import supplier_screw_margins

    monkeypatch.setattr(purchased, "double_array", tuple)
    caption_y = purchased.view_band_bottom(
        spec.DRAWING_NOTES, label=STEM, supplier_data=supplier_data
    )
    cells = purchased.fastener_view_cells(caption_y, layout=layout)
    margins = supplier_screw_margins(dimensions, planes=planes, sides=sides)
    fitted = purchased.supplier_fit_cells(cells, margins, label=STEM)
    members = [
        (_PaddedView(name, center), (name, center, bounds))
        for name, center, bounds in fitted
        if name in _MODEL_EXTENT_MM
    ]
    return purchased._fit_group(_Drawing(), members)


def test_supplier_lanes_leave_one_to_one_for_the_padded_native_outlines(monkeypatch) -> None:
    assert _fit_orthographic(monkeypatch) == (1, 1)


def test_each_part_of_the_layout_is_needed_for_one_to_one(monkeypatch) -> None:
    # The standard 64 mm Top cell: a 46 mm reserve leaves 18 mm, so 1:4.
    assert _fit_orthographic(monkeypatch, layout="standard") == (1, 4)
    # supplier_top's 70 mm Top cell leaves 24 mm: 1:2.
    assert _fit_orthographic(monkeypatch, layout="supplier_top") == (1, 2)
    # Restoring the two-line supplier-data footer lowers the tall_top Front
    # row to 60.5 mm, a 14.5 mm window: 1:8.
    data = ("SOURCE NOMINALS; INTERNAL THREAD NOT MODELLED.",)
    assert _fit_orthographic(monkeypatch, supplier_data=data) == (1, 8)
    # A second horizontal Front size (the flange OD back in the side view)
    # takes a second bottom lane: 1:2.
    front_od = {
        name: plane for name, plane in spec.SUPPLIER_REFERENCE_PLANES.items()
        if name != "SupplierFlangeDiameter"
    }
    assert _fit_orthographic(monkeypatch, planes=front_od) == (1, 2)
