"""HIWIN HGH15CA Z0 carriage (MHA-CH-06-TL-VN-51) contracts, SolidWorks-free."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path

import _config
import build_ch_rocker_arm_tl_vn_oblique_carriage as part
import ch_rocker_arm_tl_vn_oblique_carriage_spec as spec
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_vn_oblique_rail_spec as rail
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_vn_oblique_carriage as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

STEM = "ch-rocker-arm-tl-vn-oblique-carriage"
NAME = "ch_rocker_arm_tl_vn_oblique_carriage"
ROW = _config.parts(STEM)

Point = tuple[float, float]


def _shoelace(points):
    return (
        math.fsum(
            y0 * z1 - y1 * z0
            for (y0, z0), (y1, z1) in zip(points, points[1:] + points[:1])
        )
        / 2.0
    )


def _edges(points):
    return list(zip(points, points[1:] + points[:1]))


def _orient(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    """Proper or touching intersection of segments ab and cd."""
    d1, d2 = _orient(a, b, c), _orient(a, b, d)
    d3, d4 = _orient(c, d, a), _orient(c, d, b)
    return d1 * d2 <= 0 and d3 * d4 <= 0 and not (d1 == d2 == 0)


def _point_segment(p: Point, a: Point, b: Point) -> float:
    ab = (b[0] - a[0], b[1] - a[1])
    t = ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / (ab[0] ** 2 + ab[1] ** 2)
    t = min(1.0, max(0.0, t))
    return math.dist(p, (a[0] + t * ab[0], a[1] + t * ab[1]))


def _inside(p: Point, points) -> bool:
    inside = False
    for (y0, z0), (y1, z1) in _edges(points):
        if (z0 > p[1]) != (z1 > p[1]):
            if p[0] < y0 + (p[1] - z0) * (y1 - y0) / (z1 - z0):
                inside = not inside
    return inside


def _gap(first, second) -> float:
    """Least distance between two disjoint polygons; fails on any overlap."""
    for a, b in _edges(first):
        for c, d in _edges(second):
            assert not _segments_cross(a, b, c, d), (a, b, c, d)
    assert not any(_inside(p, second) for p in first)
    assert not any(_inside(p, first) for p in second)
    return min(
        min(_point_segment(p, a, b) for p in first for a, b in _edges(second)),
        min(_point_segment(p, a, b) for p in second for a, b in _edges(first)),
    )


def _simple(points) -> bool:
    edges = _edges(points)
    n = len(edges)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _segments_cross(*edges[i], *edges[j]):
                return False
    return True


def test_registry_row_is_the_purchased_hiwin_carriage() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-51"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER
    assert ROW["supplier_skus"] == [spec.SKU] == ["HGH-15-CA-Z0-C"]
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


def test_quantity_is_one_carriage_per_rail() -> None:
    assert int(ROW["quantity"]) == fasteners.RAILS == 2
    screws = fasteners.BLOCK_TO_CARRIAGE
    assert screws.thread == trammel.CARRIAGE_BOLT == "M4"
    assert screws.count == len(spec.BOLT_POINTS) * fasteners.RAILS
    assert screws.thread_depth_mm == spec.BORE_DEPTH
    # The M4 x 20 stops short of the bores' floors.
    assert screws.engagement_mm <= spec.BORE_DEPTH


def test_calculator_values_are_imported_not_retyped() -> None:
    assert spec.MOUNTING_FACE_Z == trammel.CARRIAGE_HEIGHT == 28.0
    assert spec.UNDERSIDE_Z == trammel.CARRIAGE_UNDER == 4.3
    assert spec.WIDTH == trammel.CARRIAGE_WIDTH == 34.0
    assert spec.LENGTH == trammel.CARRIAGE_LENGTH == 61.4
    assert trammel.CARRIAGE_BOLT_SPAN == (26.0, 26.0)
    assert spec.BORE_DEPTH == pivot_block.CARRIAGE_THREAD_DEPTH == 5.0
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name, value in (
        ("MOUNTING_FACE_Z", "CARRIAGE_HEIGHT"),
        ("UNDERSIDE_Z", "CARRIAGE_UNDER"),
        ("WIDTH", "CARRIAGE_WIDTH"),
        ("LENGTH", "CARRIAGE_LENGTH"),
    ):
        assert re.search(rf"^{name} = trammel\.{value}\b", source, re.M), name
    assert re.search(r"^BORE_DEPTH = CARRIAGE_THREAD_DEPTH\b", source, re.M)


def test_frame_puts_face_underside_and_bolts_where_the_jig_expects() -> None:
    assert spec.MOUNTING_FACE_Z == 28.0
    assert spec.UNDERSIDE_Z == 4.3
    assert set(spec.BOLT_POINTS) == {
        (x, y) for x in (-13.0, 13.0) for y in (-13.0, 13.0)
    }
    assert set(spec.BOLT_POINTS) == set(pivot_block.BOLT_POINTS)
    body_y = [y for y, _ in spec.BODY_OUTLINE]
    body_z = [z for _, z in spec.BODY_OUTLINE]
    assert (min(body_y), max(body_y)) == (-spec.WIDTH / 2.0, spec.WIDTH / 2.0)
    assert (min(body_z), max(body_z)) == (spec.UNDERSIDE_Z, spec.MOUNTING_FACE_Z)
    cap_z = [z for _, z in spec.CAP_OUTLINE]
    assert (min(cap_z), max(cap_z)) == (spec.UNDERSIDE_Z, spec.END_CAP_TOP_Z)
    # The M4 bores land on the mounting face, clear of its 0.5 deep, 45 deg
    # sided top grooves.
    groove_edge = max(abs(y) for y, z in spec.BODY_OUTLINE if z == 27.5) + 0.5
    for _, y in spec.BOLT_POINTS:
        assert abs(y) - spec.BORE_DIA / 2.0 > groove_edge
    # Nipple axis H - H2, the vendor's 5.05 above the rail top.
    assert math.isclose(spec.NIPPLE_Z, 20.05)
    assert math.isclose(spec.NIPPLE_Z - rail.HEIGHT, 5.05)
    assert spec.NIPPLE_FACE_X == spec.LENGTH / 2.0 == -spec.PLUG_FACE_X


def test_vendor_bounding_box_maps_onto_the_part_frame() -> None:
    lo, hi = spec.VENDOR_BBOX_MIN, spec.VENDOR_BBOX_MAX
    # Along: the seal faces at +-L/2 plus the nipple and the plug.
    assert math.isclose(
        hi[0] - lo[0], spec.LENGTH + spec.NIPPLE_PROUD + spec.PLUG_PROUD
    )
    assert math.isclose(-lo[0] - spec.LENGTH / 2.0, spec.NIPPLE_PROUD)
    assert math.isclose(hi[0] - spec.LENGTH / 2.0, spec.PLUG_PROUD)
    # Up: part z = vendor y + rail height.
    assert math.isclose(lo[1] + rail.HEIGHT, spec.UNDERSIDE_Z)
    assert math.isclose(hi[1] + rail.HEIGHT, spec.MOUNTING_FACE_Z)
    # Across.
    assert (lo[2], hi[2]) == (-spec.WIDTH / 2.0, spec.WIDTH / 2.0)
    # The cap and seal section lies inside the steel body's.
    assert all(_inside(p, spec.BODY_OUTLINE) for p in spec.CAP_OUTLINE)


def test_derived_bore_is_the_m4_minor_diameter() -> None:
    assert spec.BORE_DIA == 3.242
    assert math.isclose(spec.BORE_DIA, 4.0 - 1.082532 * 0.7, abs_tol=5e-4)


def test_sections_are_simple_and_counter_clockwise() -> None:
    for name in (
        "BODY_OUTLINE",
        "CAP_OUTLINE",
        "CHANNEL",
        "BODY_SECTION",
        "CAP_SECTION",
    ):
        points = getattr(spec, name)
        assert _simple(points), name
        assert _shoelace(points) > 0.0, name
    assert math.isclose(
        _shoelace(spec.BODY_SECTION),
        _shoelace(spec.BODY_OUTLINE) - spec.A_CHANNEL,
        rel_tol=1e-12,
    )
    assert math.isclose(
        _shoelace(spec.CAP_SECTION),
        _shoelace(spec.CAP_OUTLINE) - spec.A_CHANNEL,
        rel_tol=1e-12,
    )
    # The cut profile closes below the underside, in the air beside the rail.
    assert min(z for _, z in spec.CHANNEL) == spec.CHANNEL_FLOOR_Z < spec.UNDERSIDE_Z


def test_channel_clears_the_rail_section() -> None:
    for section in (spec.BODY_SECTION, spec.CAP_SECTION):
        gap = _gap(section, rail.SECTION)
        assert gap > 0.0
        assert math.isclose(gap, spec.CHANNEL_CLEARANCE, abs_tol=1e-6)
    # Every rail vertex above the underside lies inside the channel, every
    # channel vertex outside the rail.
    for p in rail.SECTION:
        if p[1] > spec.UNDERSIDE_Z:
            assert _inside(p, spec.CHANNEL_IN_BLOCK), p
    assert not any(_inside(p, rail.SECTION) for p in spec.CHANNEL)


def test_closed_form_volume_and_centroid() -> None:
    v_caps = _shoelace(spec.CAP_OUTLINE) * spec.LENGTH
    v_body = (
        _shoelace(spec.BODY_OUTLINE) - _shoelace(spec.CAP_OUTLINE)
    ) * spec.BODY_LENGTH
    v_channel = _shoelace(spec.CHANNEL_IN_BLOCK) * spec.LENGTH
    v_bores = 4 * math.pi * 1.621**2 * 5.0
    v_ends = math.pi * 3.0**2 * spec.NIPPLE_PROUD + math.pi * 3.76**2 * spec.PLUG_PROUD
    assert math.isclose(
        spec.VOLUME_MM3, v_caps + v_body - v_channel - v_bores + v_ends, rel_tol=1e-12
    )
    # The nipple outweighs the plug on +X; the 0.3 relief and the caps' 0.043
    # offset tip it to +Y.
    assert 0.0 < spec.CENTROID[0] < 0.5
    assert 0.0 < spec.CENTROID[1] < 0.5
    assert spec.UNDERSIDE_Z < spec.CENTROID[2] < spec.MOUNTING_FACE_Z


def test_steel_body_matches_the_vendor_solid() -> None:
    # HIWIN's body from this outline: its channel on the rail's true profile,
    # the bores with their 118 deg drill points.
    true_rail = _shoelace(rail.clip_above(rail.SECTION, spec.UNDERSIDE_Z))
    assert math.isclose(
        spec.VENDOR_CHANNEL_MM2, true_rail - rail.GROOVE_SEGMENTS_MM2, rel_tol=1e-12
    )
    cone = math.pi * 1.621**2 * (1.621 / math.tan(math.radians(59.0))) / 3.0
    assert math.isclose(spec.V_DRILL_POINTS, 4 * cone, rel_tol=1e-3)
    residual = spec.VENDOR_BODY_MODEL_MM3 - spec.VENDOR_BODY_VOLUME_MM3
    # Eight R0.4 blend chords (each under 0.01 mm^2 of section).
    assert abs(residual) < spec.VENDOR_BODY_ALLOWANCE_MM3


def test_caps_and_seals_bound_the_vendor_solids() -> None:
    vendor = 2.0 * (spec.VENDOR_CAP_VOLUME_MM3 + spec.VENDOR_SEAL_VOLUME_MM3)
    # Solid prisms: their lube passages, ports, turnarounds and seal lips
    # are the only volume they add, under 8 % of the vendor caps and seals.
    assert 0.0 < spec.CAP_INTERNAL_MM3 < 0.08 * vendor


def test_native_volume_against_the_vendor_step() -> None:
    explained = (
        -spec.CHANNEL_EXCESS_MM2 * spec.LENGTH
        + spec.V_DRILL_POINTS
        + spec.CAP_INTERNAL_MM3
        + spec.V_NIPPLE
        - spec.VENDOR_NIPPLE_VOLUME_MM3
        + spec.V_PLUG
        - spec.VENDOR_PLUG_VOLUME_MM3
    )
    difference = spec.VOLUME_MM3 - spec.VENDOR_VOLUME_MM3
    # Every departure is closed form or vendor-measured; the body's blend
    # chords are the residual.
    assert abs(difference - explained) < spec.VENDOR_BODY_ALLOWANCE_MM3
    assert abs(difference) < 0.02 * spec.VENDOR_VOLUME_MM3
    # The 0.1 running clearance is the channel's excess over HIWIN's.
    assert 0.0 < spec.CHANNEL_EXCESS_MM2 < 0.1 * spec.VENDOR_CHANNEL_MM2


def test_nipple_and_plug_envelope_the_vendor_parts() -> None:
    # Ball head Ø6 (hex AF5 across corners 5.77), domed plug Ø7.513.
    assert spec.NIPPLE_DIA >= 5.0 / math.cos(math.radians(30.0))
    assert spec.PLUG_DIA >= 2.0 * 3.7566
    assert spec.NIPPLE_PROUD > spec.CATALOGUE_NIPPLE_PROUD
    assert spec.V_NIPPLE > 0.0 and spec.V_PLUG > 0.0
    assert spec.NIPPLE_Z + spec.NIPPLE_DIA / 2.0 < spec.END_CAP_TOP_Z


def test_spec_is_pure_data() -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    imports = set(re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE))
    assert imports <= {
        "__future__",
        "_config",
        "math",
        "ch_rocker_arm_tl_oblique_pivot_block_spec",
        "ch_rocker_arm_tl_vn_oblique_rail_spec",
        "ch_rocker_arm_tl_oblique_trammel_spec",
    }


def test_docstring_marks_every_source() -> None:
    doc = spec.__doc__ or ""
    for mark in ("VENDOR STEP", "SOURCED", "FROM THE CALCULATOR", "VENDOR-CHECKED"):
        assert mark in doc, mark
    assert spec.VENDOR_STEP in doc
    assert "datasheet-built: no vendor CAD obtained" in doc
    assert re.fullmatch(r"[0-9a-f]{64}", spec.VENDOR_STEP_SHA256)
    assert spec.VENDOR_DOWNLOADED == "2026-10-17"


def test_build_unions_caps_and_body_then_cuts_channel_and_bores() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    order = [
        source.index(f'name_last_feature(adapter, "{name}")')
        for name in ("EndCaps", "SteelBody", "Channel", "M4Bores")
    ]
    assert order == sorted(order)
    for needle in (
        "u_axis=2, v_axis=1",
        "both_directions=True",
        '"GreaseNipple" if name == "NippleEnd" else "PortPlug"',
        'volume_check(adapter, "carriage", VOLUME_MM3, VOLUME_TOL_MM3)',
        '_require_one_solid_body(adapter, label="carriage")',
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
    assert calls == [(adapter, sheet, draw.ITEM, False)]
    assert spec.MAKER_PART in draw.ITEM


def test_note_names_the_rail_by_its_registry_drawing_number() -> None:
    """Machinist review: the mounting note named the rail only in words."""
    number = _config.parts("ch-rocker-arm-tl-vn-oblique-rail")["number"]
    assert spec.RAIL_NUMBER == number
    assert spec.DRAWING_NOTES == (
        f"MOUNT ON THE OBLIQUE TRAMMEL RAIL {number}; GREASE THROUGH THE END NIPPLE."
    )
    # The number is the only digits the note carries, read from the registry.
    assert not re.search(r"\d", spec.DRAWING_NOTES.replace(number, ""))
    source = Path(spec.__file__).read_text(encoding="utf-8")
    note_source = source[source.index("RAIL_NUMBER = ") :]
    assert '_config.parts("ch-rocker-arm-tl-vn-oblique-rail")["number"]' in note_source
    assert number not in note_source
