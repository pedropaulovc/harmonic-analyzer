"""HIWIN-style HGR15 kit rail, 450 as supplied (MHA-CH-06-TL-VN-50) contracts, SolidWorks-free."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path

import _config
import build_ch_rocker_arm_tl_vn_oblique_rail as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_rail_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_vn_oblique_rail as draw
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout

STEM = "ch-rocker-arm-tl-vn-oblique-rail"
NAME = "ch_rocker_arm_tl_vn_oblique_rail"
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


def test_registry_row_is_the_purchased_kit_rail() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-50"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "Amazon (sold by XIQI)"
    # The kit's ASIN: one kit supplies both rails and both carriages.
    assert ROW["supplier_skus"] == [spec.SKU] == ["B0C4DJNL33"]
    assert spec.SOURCE_URL.endswith(f"/dp/{spec.SKU}")
    carriage_row = _config.parts("ch-rocker-arm-tl-vn-oblique-carriage")
    assert carriage_row["supplier_skus"] == ROW["supplier_skus"]
    assert carriage_row["supplier"] == ROW["supplier"]
    assert ROW["material"] == spec.MATERIAL == "Alloy Steel"
    assert ROW["tolerance_class"] == "machined_block"
    assert "fit_class" not in ROW
    # The style designation, never a HIWIN order code: the rail is not HIWIN's.
    assert spec.STYLE == "HGR15" and spec.STYLE in ROW["stock_name"]
    assert not hasattr(spec, "MAKER_PART")
    assert "HGR15R" not in ROW["stock_name"]
    # One line in the title block's MATERIAL cell; the provenance is the spec's.
    assert len(ROW["material_specification"]) <= 36
    assert spec.REFERENCE_STEP in (spec.__doc__ or "")
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
    assert spec.LENGTH == trammel.RAIL_LENGTH == 450.0
    assert spec.WIDTH == trammel.RAIL_WIDTH == 15.0
    assert spec.HEIGHT == trammel.RAIL_HEIGHT == 15.0
    assert spec.HOLE_PITCH == trammel.RAIL_HOLE_PITCH == 60.0
    assert spec.HOLE_COUNT == trammel.RAIL_HOLE_COUNT == 8
    assert spec.HOLE_END == trammel.RAIL_HOLE_END == 15.0
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


def test_calculator_agrees_with_the_catalogue_and_reference_rail() -> None:
    # The calculator's counterbore floor is the catalogue's h 5.3.
    assert math.isclose(spec.CBORE_DEPTH, spec.CATALOGUE_CBORE_DEPTH)
    assert (spec.HOLE_DIA, spec.CBORE_DIA) == (4.5, 7.5)
    # The reference model is HIWIN's standard 440, 8 holes at E 10; the kit
    # rail is 450 with 8 holes at E 15 on the same pitch. Both patterns are
    # symmetric on their lengths.
    reference_span = (spec.REFERENCE_HOLE_COUNT - 1) * spec.HOLE_PITCH
    assert math.isclose(
        2 * spec.REFERENCE_HOLE_END + reference_span, spec.REFERENCE_LENGTH
    )
    assert spec.REFERENCE_HOLE_COUNT == spec.HOLE_COUNT
    assert math.isclose(spec.HOLE_X[0] + spec.HOLE_X[-1], spec.LENGTH)
    assert spec.HOLE_X == (15.0, 75.0, 135.0, 195.0, 255.0, 315.0, 375.0, 435.0)


def test_section_is_the_reference_profile_in_the_part_frame() -> None:
    ys = [y for y, _ in spec.SECTION]
    zs = [z for _, z in spec.SECTION]
    assert (min(ys), max(ys)) == (-spec.WIDTH / 2.0, spec.WIDTH / 2.0)
    assert (min(zs), max(zs)) == (0.0, spec.HEIGHT)
    assert len(spec.SECTION) == 2 * len(spec.REFERENCE_HALF_PROFILE)
    # Mirror-symmetric about the centre plane, counter-clockwise from +X.
    assert sorted(spec.SECTION) == sorted((-y, z) for y, z in spec.SECTION)
    area = _shoelace(spec.SECTION)
    assert area > 0.0
    assert math.isclose(area, spec.SECTION_AREA, rel_tol=1e-12)
    # The 0.7 x 45 deg foot chamfer clears the catalogue's r1 0.5 max fillet
    # at the base bar's locating shoulder.
    seat_end, chamfer_top = spec.REFERENCE_HALF_PROFILE[:2]
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


def test_closed_form_volume_matches_the_reference_step() -> None:
    hole = math.pi * 2.25**2 * (spec.HEIGHT - spec.CBORE_DEPTH)
    cbore = math.pi * 3.75**2 * spec.CBORE_DEPTH
    expected = _shoelace(spec.SECTION) * spec.LENGTH - spec.HOLE_COUNT * (hole + cbore)
    assert math.isclose(spec.VOLUME_MM3, expected, rel_tol=1e-12)
    # The reference solid (440, 8 holes) lengthened to 450 in its true
    # section (the chord section less the groove fill), plus the closed-form
    # chord fill of the raceway grooves less the R1 blends over the whole
    # length; what is left is the reference's ten R0.4 blends, its 0.1 deep
    # logo and the dims' rounding.
    extra = spec.LENGTH - spec.REFERENCE_LENGTH
    assert extra == 10.0
    assert math.isclose(
        spec.REFERENCE_EQUIVALENT_VOLUME_MM3,
        spec.REFERENCE_VOLUME_MM3 + (spec.SECTION_AREA - spec.GROOVE_FILL_MM2) * extra,
        rel_tol=1e-12,
    )
    residual = (
        spec.VOLUME_MM3
        - spec.REFERENCE_EQUIVALENT_VOLUME_MM3
        - spec.GROOVE_FILL_MM2 * spec.LENGTH
    )
    assert abs(residual) < spec.REFERENCE_VOLUME_ALLOWANCE_MM3 == 45.0
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
    # The base bar spec (pure data) carries the receipt band the note prints.
    assert imports <= {
        "__future__",
        "math",
        "ch_rocker_arm_tl_oblique_trammel_spec",
        "ch_rocker_arm_tl_oblique_base_bar_spec",
    }


def test_docstring_marks_every_source() -> None:
    doc = spec.__doc__ or ""
    for mark in (
        "KIT LISTING",
        "REFERENCE GEOMETRY",
        "REFERENCE STEP",
        "SOURCED",
        "FROM THE CALCULATOR",
        "UNVERIFIED",
    ):
        assert mark in doc, mark
    assert spec.REFERENCE_STEP in doc
    assert spec.SOURCE_URL in doc or spec.SKU in doc
    assert "HIWIN is not the supplier" in doc
    assert re.fullmatch(r"[0-9a-f]{64}", spec.REFERENCE_STEP_SHA256)
    assert spec.REFERENCE_DOWNLOADED == "2026-10-17"


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


def test_build_names_and_marks_the_receipt_dimensions() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for needle in (
        'name_dimensions(adapter, "Rail", ["Length"])',
        'end_name="HoleEnd"',
        'pitch_name="HolePitch"',
        'hole_dims.apply(adapter, "BoltHoleProfile")',
        "apply_drawing_precision(adapter, DRAWING_PRECISION)",
        "mark_dimensions_for_drawing(adapter, feature_name, names)",
    ):
        assert needle in source, needle
    assert spec.DRAWING_DIMENSIONS == {
        "Rail": {"Length"},
        "BoltHoleProfile": {"HoleEnd", "HolePitch"},
    }
    assert spec.DRAWING_PRECISION == {
        "Rail": {"Length": 0},
        "BoltHoleProfile": {"HoleEnd": 0, "HolePitch": 0},
    }
    # The one printed pitch counts every gap between the eight holes.
    assert spec.HOLE_PITCH_CALLOUT == f"{spec.HOLE_COUNT - 1}X" == "7X"


class _Result:
    def __init__(self, data=None) -> None:
        self.is_success = True
        self.error = None
        self.data = data


class _SketchAdapter:
    """Records the hole sketch's circles, relations and dimensions."""

    def __init__(self) -> None:
        self.currentSketchManager = type("SketchManager", (), {"AddToDB": False})()
        self.circles: list[tuple[float, float, float]] = []
        self.relations: list[tuple[str, str, str]] = []
        self.dimensions: list[tuple[str, str | None, str, float]] = []

    async def create_sketch(self, plane):
        return _Result(plane)

    async def add_circle(self, x, y, radius):
        self.circles.append((x, y, radius))
        return _Result(f"circle{len(self.circles)}")

    async def add_sketch_constraint(self, ref1, ref2, kind):
        self.relations.append((ref1, ref2, kind))
        return _Result()

    async def add_sketch_dimension(self, ref1, ref2, kind, value):
        self.dimensions.append((ref1, ref2, kind, value))
        return _Result()

    async def exit_sketch(self):
        return _Result()


def test_hole_sketch_places_the_end_distance_then_one_pitch_per_gap(
    monkeypatch,
) -> None:
    adapter = _SketchAdapter()
    monkeypatch.setattr(
        part, "_sketch_mapper", lambda *_a, **_k: lambda point: (point[0], point[1])
    )

    async def fully_defined(*_args, **_kwargs):
        return None

    monkeypatch.setattr(part, "ensure_fully_defined", fully_defined)
    dims = asyncio.run(
        part._hole_circles(
            adapter,
            "Front",
            0.0,
            spec.HOLE_DIA,
            "bolt hole",
            end_name="HoleEnd",
            pitch_name="HolePitch",
        )
    )
    assert [x for x, _, _ in adapter.circles] == list(spec.HOLE_X)
    distances = [
        (ref1, ref2, value)
        for ref1, ref2, kind, value in adapter.dimensions
        if kind == "horizontal_distance"
    ]
    # The first hole from the origin (the -X end face), each next one from
    # the hole before it: the chain the drawing prints as 15 and 7X 60.
    assert distances[0] == ("circle1.center", "origin", spec.HOLE_END)
    assert distances[1:] == [
        (f"circle{k}.center", f"circle{k + 1}.center", spec.HOLE_PITCH)
        for k in range(1, spec.HOLE_COUNT)
    ]
    assert all(kind == "horizontal_points" for _, _, kind in adapter.relations)
    assert [value for *_, kind, value in adapter.dimensions if kind == "diameter"] == [
        spec.HOLE_DIA
    ] * spec.HOLE_COUNT
    names = [name for name, _ in dims._rows]
    assert len(names) == 2 * spec.HOLE_COUNT == len(adapter.dimensions)
    assert names[0] == "HoleEnd" and names[2] == "HolePitch"
    assert sum(name is not None for name in names) == 2


def test_sheet_is_the_registered_purchased_part_reference() -> None:
    sheet = DRAWINGS_BY_NAME[NAME]
    assert draw.SPEC is sheet
    assert (sheet.part, sheet.artifact_stem, sheet.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert sheet.layout is DrawingLayout.LANDSCAPE
    assert sheet.source_kind == "part"
    assert spec.STYLE in draw.ITEM and "HGR15R" not in draw.ITEM
    assert "GENERIC" in draw.ITEM
    # The length is the FRONT view's dimension, never the item's text.
    assert f"{spec.LENGTH:.0f}" not in draw.ITEM
    assert {name for name, *_ in draw.VIEWS} == {
        "*Front",
        "*Top",
        "*Right",
        "*Isometric",
    }
    source = Path(draw.__file__).read_text(encoding="utf-8")
    # Every view, the isometric included, is hidden-lines-removed.
    assert "for name, center, _, scale in VIEWS:" in source
    assert "set_hidden_lines_removed(adapter, view)" in source


def test_receipt_dimensions_are_the_marked_model_dimensions() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(draw.RECEIPT_DIMENSIONS) == marked
    assert set(draw.FRONT_DIMENSION_PRECISION) == marked
    assert set(draw.FRONT_DIMENSION_PRECISION.values()) == {0}
    assert draw.DIMENSION_PREFIXES == {"HolePitch": spec.HOLE_PITCH_CALLOUT}
    # The short hole-row spans keep their arrows off each other.
    assert draw.ARROWS_INSIDE == ("HoleEnd", "HolePitch")
    # Each spans its own stations from the -X end face (rule 10).
    assert draw.RECEIPT_DIMENSIONS["Length"][:2] == (0.0, spec.LENGTH)
    assert draw.RECEIPT_DIMENSIONS["HoleEnd"][:2] == (0.0, spec.HOLE_END)
    start, end, _ = draw.RECEIPT_DIMENSIONS["HolePitch"]
    assert end - start == spec.HOLE_PITCH
    # The hole row nearest the part, the length row under it, the caption
    # under both.
    assert 0.0 < draw.HOLE_ROW_DROP < draw.LENGTH_ROW_DROP
    assert draw.FRONT_CENTER[1] - draw.LENGTH_ROW_DROP - 0.003 > draw.CAPTIONS[0][2]
    rail_edge = draw.FRONT_CENTER[1] - draw._FRONT_HALF[1]
    assert draw.FRONT_CENTER[1] - draw.HOLE_ROW_DROP + 0.003 < rail_edge


def test_end_distance_text_stands_outside_its_short_span() -> None:
    """At 1:2 the 15 end distance spans 7.5 mm, under its "(15)" text: the
    text stands left of the -X end face, clear of it and inside the border;
    the pitch's text stays centred in its 30 mm span."""
    per_mm = draw._sheet_mm(draw.SHEET_SCALE)
    end_face_x = draw.FRONT_CENTER[0] - draw._FRONT_HALF[0]

    def sheet(x_mm: float) -> tuple[float, float]:
        return end_face_x + x_mm * per_mm, draw.FRONT_CENTER[1]

    text_half = 0.005  # "(15)" at the 3.5 mm dimension font, about 10 mm wide
    span = spec.HOLE_END * per_mm
    assert span < 2.0 * text_half
    start, end, drop = draw.RECEIPT_DIMENSIONS["HoleEnd"]
    x, y = draw.receipt_text_point("HoleEnd", sheet(start), sheet(end), drop)
    assert y == draw.FRONT_CENTER[1] - drop
    assert x + text_half + 0.002 <= end_face_x
    assert x - text_half >= 0.0127 + 0.005  # the border, with air
    start, end, drop = draw.RECEIPT_DIMENSIONS["HolePitch"]
    x, _ = draw.receipt_text_point("HolePitch", sheet(start), sheet(end), drop)
    assert x == (sheet(start)[0] + sheet(end)[0]) / 2.0
    assert set(draw.TEXT_OUTSIDE_START) == {"HoleEnd"}


def test_views_and_captions_fit_the_sheet() -> None:
    from _purchased_fastener_drawing import footer_top

    border = (0.0127, 0.0127, 0.4191, 0.2667)
    title_block = (0.2159, 0.0127, 0.4191, 0.0651)
    footer = footer_top(spec.DRAWING_NOTES, label=NAME)

    def overlaps(a, b) -> bool:
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    cells = {name: draw.view_cell(center, half) for name, center, half, _ in draw.VIEWS}
    for name, cell in cells.items():
        assert border[0] <= cell[0] and cell[2] <= border[2], name
        assert footer < cell[1] and cell[3] <= border[3], name
        assert not overlaps(cell, title_block), name
    names = sorted(cells)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            assert not overlaps(cells[first], cells[second]), (first, second)
    # TOP over FRONT and RIGHT beside it, in projection.
    assert draw.TOP_CENTER[0] == draw.FRONT_CENTER[0]
    assert draw.RIGHT_CENTER[1] == draw.FRONT_CENTER[1]
    for label, x, y, scale in draw.CAPTIONS:
        cell = cells[f"*{label.title()}"]
        assert y < cell[1] and cell[0] < x < cell[2], label
        assert y - 0.006 > footer, label
        assert draw.caption_text(label, scale).startswith(label)


def test_note_is_the_bounded_receipt_check() -> None:
    from _purchased_fastener_drawing import note_lines

    import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar

    bar = _config.parts("ch-rocker-arm-tl-oblique-base-bar")
    # Rule 7: the length and hole pattern are FRONT's dimensions; the note's
    # only numbers are the base bar's drawing number and the receipt band.
    assert spec.RECEIPT_BAND == base_bar.RAIL_RECEIPT_BAND
    assert bar["number"] in spec.DRAWING_NOTES
    assert spec.RECEIPT_TEXT == f"±{base_bar.RAIL_RECEIPT_BAND:.2f} MM" == "±0.08 MM"
    rest = spec.DRAWING_NOTES.replace(bar["number"], "").replace(spec.RECEIPT_TEXT, "")
    assert not re.search(r"\d", rest)
    lines = note_lines(spec.DRAWING_NOTES, label=NAME)
    assert len(lines) == 3
    assert all(len(line) <= 70 for line in lines), lines
    # The kit rail is used uncut; the bar is drilled to its print, so the rail
    # is accepted only inside the fit's allowance and stopped outside it
    # (Codjiflo P2; farm review 20261104T203420333Z).
    note = " ".join(lines)
    assert "USED UNCUT" in note and "SPECIAL ORDER" not in note
    assert f"EACH WITHIN {spec.RECEIPT_TEXT} OF THIS SHEET, OR STOP AND REPORT" in note
    assert "THE BAR IS DRILLED AS DRAWN" in note
    assert "TAP THE BAR TO THE RAIL" not in note
