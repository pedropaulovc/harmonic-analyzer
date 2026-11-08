"""NUIBBYED HGR15 rail kit (MHA-CH-06-TL-VN-83) contracts, SolidWorks-free.

One native model, ``Rail`` and ``Carriage`` configurations, one drawing
package: sheet 1 the configured reference, sheet 2 the rail's receipt check.
"""

from __future__ import annotations

import ast
import asyncio
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_ch_rocker_arm_tl_vn_oblique_rail_kit as part
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_rail_kit_carriage_spec as carriage
import ch_rocker_arm_tl_vn_oblique_rail_kit_rail_spec as rail
import draw_ch_rocker_arm_tl_vn_oblique_rail_kit as draw
import test_ch_rocker_arm_tl_oblique_adapter_contract as contract
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _layout_geometry import estimate_text_box
from _part_configuration_exports import member_configurations
from _purchased_fastener_drawing import check_item, footer_top, note_lines
from _purchased_part_variants import _member_properties

STEM = "ch-rocker-arm-tl-vn-oblique-rail-kit"
NAME = "ch_rocker_arm_tl_vn_oblique_rail_kit"
ROW = _config.parts(STEM)
STEEL_KG_PER_MM3 = 7.7e-6  # SOLIDWORKS "Alloy Steel"
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.2159, 0.0127, 0.4191, 0.0651)

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


def _overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# --- The kit: one registry row, two configured members ---------------------------


def test_registry_row_is_one_kit_with_two_configured_members() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-83"
    assert ROW["process"] == "purchased"
    assert ROW["drawing_unit"] == "mm"
    assert ROW["supplier"] == rail.SUPPLIER == carriage.SUPPLIER == "Amazon (sold by XIQI)"
    # The kit's ASIN: one kit supplies both rails and both carriages.
    assert ROW["supplier_skus"] == [rail.SKU] == [carriage.SKU] == ["B0C4DJNL33"]
    assert rail.SOURCE_URL.endswith(f"/dp/{rail.SKU}")
    assert ROW["default_configuration"] == rail.CONFIGURATION == "Rail"
    assert ROW["configuration_quantities"] == {"Rail": 2, "Carriage": 2}
    assert int(ROW["quantity"]) == sum(ROW["configuration_quantities"].values()) == 4
    assert member_configurations(NAME) == part.CONFIGURATIONS == ("Rail", "Carriage")
    assert carriage.CONFIGURATION == "Carriage"
    assert ROW["material"] == rail.MATERIAL == carriage.MATERIAL == "Alloy Steel"
    assert ROW["tolerance_class"] == "machined_block"
    assert "fit_class" not in ROW and "usage_scope" not in ROW
    # The style designations, never HIWIN order codes: the kit is not HIWIN's.
    assert rail.STYLE == "HGR15" and rail.STYLE in ROW["stock_name"]
    assert carriage.STYLE == "HGH15CA" and carriage.STYLE in ROW["stock_name"]
    assert "HGR15R" not in ROW["stock_name"] and "Z0" not in ROW["stock_name"]
    assert not hasattr(rail, "MAKER_PART") and not hasattr(carriage, "MAKER_PART")
    # The retired member identities have no row of their own.
    parts_dir = Path(_config.CONFIG_DIR) / "parts"
    for retired in ("ch-rocker-arm-tl-vn-oblique-rail", "ch-rocker-arm-tl-vn-oblique-carriage"):
        assert not (parts_dir / f"{retired}.yaml").exists(), retired


def test_member_quantities_are_one_rail_and_one_carriage_per_side() -> None:
    quantities = ROW["configuration_quantities"]
    assert quantities[rail.CONFIGURATION] == fasteners.RAILS == 2
    assert quantities[carriage.CONFIGURATION] == fasteners.RAILS
    # C4's rail-to-bar screws fill exactly the rails' holes.
    assert fasteners.RAIL_TO_BAR.count == rail.HOLE_COUNT * fasteners.RAILS
    screws = fasteners.BLOCK_TO_CARRIAGE
    assert screws.thread == trammel.CARRIAGE_BOLT == "M4"
    assert screws.count == len(carriage.BOLT_POINTS) * fasteners.RAILS
    assert screws.thread_depth_mm == carriage.BORE_DEPTH
    # The M4 x 20 stops short of the bores' floors.
    assert screws.engagement_mm <= carriage.BORE_DEPTH


def test_member_properties_carry_each_members_material_quantity_and_note() -> None:
    assert ROW["material_specification"] == rail.MATERIAL_SPECIFICATION
    assert carriage.MATERIAL_SPECIFICATION == "Bearing steel, plastic end caps"
    for spec in (rail, carriage):
        # One line in the title block's MATERIAL cell.
        assert len(spec.MATERIAL_SPECIFICATION) <= 36
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": rail.SUPPLIER,
        "Supplier SKUs": rail.SKU,
    }
    for configuration, spec in part.MEMBER_SPECS.items():
        properties = _member_properties(
            STEM,
            configuration,
            part.MEMBER_DESCRIPTIONS[configuration],
            part.MEMBER_PROPERTIES[configuration],
        )
        assert properties["Number"] == ROW["number"]
        assert properties["Quantity"] == str(ROW["configuration_quantities"][configuration])
        assert properties["Material Specification"] == spec.MATERIAL_SPECIFICATION
        assert properties["Manufacturing Notes"] == spec.DRAWING_NOTES
        assert properties["Description"] == spec.BOM_DESCRIPTION
    assert part.MEMBER_DESCRIPTIONS == {
        "Rail": "HGR15 RAIL, 439.928 MM, KIT, TRIMMED",
        "Carriage": "HGH15CA CARRIAGE, KIT",
    }
    assert part.MEMBER_NOTE_PROPERTIES == draw.NOTE_PROPERTIES
    assert set(part.MEMBER_NOTE_PROPERTIES) <= set(part.SAVED_DRAWING_PROPERTIES)


def test_member_features_are_disjoint_and_own_every_named_feature() -> None:
    owned = [name for names in part.MEMBER_FEATURES.values() for name in names]
    assert len(owned) == len(set(owned))
    assert tuple(part.MEMBER_FEATURES) == part.CONFIGURATIONS
    source = Path(part.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    named: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
            "_author_rail",
            "_author_carriage",
        }:
            names = named.setdefault(node.name, set())
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "name_last_feature"
                ):
                    argument = call.args[1]
                    if isinstance(argument, ast.Constant):
                        names.add(argument.value)
                    else:  # the end planes' loop: f"{feature}Profile" and name
                        names.add(ast.unparse(argument))
    rail_names = named["_author_rail"]
    carriage_names = {
        name for name in named["_author_carriage"] if not name.startswith(("f'", "name", "feature"))
    }
    assert rail_names == set(part.MEMBER_FEATURES["Rail"])
    loop_features = {"NippleEnd", "PlugEnd", "GreaseNipple", "PortPlug"}
    loop_profiles = {"GreaseNippleProfile", "PortPlugProfile"}
    assert carriage_names | loop_features | loop_profiles == set(part.MEMBER_FEATURES["Carriage"])
    # Each member's planes are its own and blanked in its configuration.
    for configuration, planes in part.MEMBER_PLANES.items():
        assert set(planes) <= set(part.MEMBER_FEATURES[configuration])
    # Parents before dependents: each profile precedes its feature.
    for names in part.MEMBER_FEATURES.values():
        for index, name in enumerate(names):
            if name.endswith(("Profile", "Section")):
                assert index + 1 < len(names), name


def test_builder_adapter_calls_bind_to_the_vendored_sdk() -> None:
    path = Path(part.__file__)
    calls = contract._bind_calls(path, contract.sdk._tree(path))
    assert {
        "create_part", "create_sketch", "exit_sketch", "create_extrusion",
        "create_cut_extrude", "create_plane", "get_mass_properties",
    } <= {call.func.attr for call in calls}


# --- Rail member --------------------------------------------------------------------


def test_rail_calculator_values_are_imported_not_retyped() -> None:
    assert rail.LENGTH == trammel.RAIL_LENGTH == 439.928
    assert rail.WIDTH == trammel.RAIL_WIDTH == 15.0
    assert rail.HEIGHT == trammel.RAIL_HEIGHT == 15.0
    assert rail.HOLE_PITCH == trammel.RAIL_HOLE_PITCH == 60.0
    assert rail.HOLE_COUNT == trammel.RAIL_HOLE_COUNT == 8
    assert rail.HOLE_END == trammel.RAIL_HOLE_END == 9.964
    source = Path(rail.__file__).read_text(encoding="utf-8")
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


def test_rail_agrees_with_the_catalogue_and_reference_rail() -> None:
    assert math.isclose(rail.CBORE_DEPTH, rail.CATALOGUE_CBORE_DEPTH)
    assert (rail.HOLE_DIA, rail.CBORE_DIA) == (4.5, 7.5)
    reference_span = (rail.REFERENCE_HOLE_COUNT - 1) * rail.HOLE_PITCH
    assert math.isclose(
        2 * rail.REFERENCE_HOLE_END + reference_span, rail.REFERENCE_LENGTH
    )
    assert rail.REFERENCE_HOLE_COUNT == rail.HOLE_COUNT
    assert math.isclose(rail.HOLE_X[0] + rail.HOLE_X[-1], rail.LENGTH)
    assert rail.HOLE_X == tuple(9.964 + 60.0 * k for k in range(8))
    # The rail's stations are the base bar's tapped stations.
    assert rail.HOLE_X == base_bar.RAIL_HOLE_X


def test_rail_section_is_the_reference_profile_in_the_part_frame() -> None:
    ys = [y for y, _ in rail.SECTION]
    zs = [z for _, z in rail.SECTION]
    assert (min(ys), max(ys)) == (-rail.WIDTH / 2.0, rail.WIDTH / 2.0)
    assert (min(zs), max(zs)) == (0.0, rail.HEIGHT)
    assert len(rail.SECTION) == 2 * len(rail.REFERENCE_HALF_PROFILE)
    assert sorted(rail.SECTION) == sorted((-y, z) for y, z in rail.SECTION)
    area = _shoelace(rail.SECTION)
    assert area > 0.0
    assert math.isclose(area, rail.SECTION_AREA, rel_tol=1e-12)
    assert _simple(rail.SECTION)
    # The 0.7 x 45 deg foot chamfer clears the catalogue's r1 0.5 max fillet
    # at the base bar's locating shoulder.
    seat_end, chamfer_top = rail.REFERENCE_HALF_PROFILE[:2]
    assert chamfer_top[0] - seat_end[0] > rail.SHOULDER_FILLET_MAX


def test_rail_volume_mass_and_centroid_match_the_reference() -> None:
    hole = math.pi * 2.25**2 * (rail.HEIGHT - rail.CBORE_DEPTH)
    cbore = math.pi * 3.75**2 * rail.CBORE_DEPTH
    expected = _shoelace(rail.SECTION) * rail.LENGTH - rail.HOLE_COUNT * (hole + cbore)
    assert math.isclose(rail.VOLUME_MM3, expected, rel_tol=1e-12)
    extra = rail.LENGTH - rail.REFERENCE_LENGTH
    assert math.isclose(extra, -0.072, abs_tol=1e-10)
    assert math.isclose(
        rail.REFERENCE_EQUIVALENT_VOLUME_MM3,
        rail.REFERENCE_VOLUME_MM3 + (rail.SECTION_AREA - rail.GROOVE_FILL_MM2) * extra,
        rel_tol=1e-12,
    )
    residual = (
        rail.VOLUME_MM3
        - rail.REFERENCE_EQUIVALENT_VOLUME_MM3
        - rail.GROOVE_FILL_MM2 * rail.LENGTH
    )
    assert abs(residual) < rail.REFERENCE_VOLUME_ALLOWANCE_MM3
    assert 0.0 < rail.GROOVE_FILL_MM2 < 0.01 * rail.SECTION_AREA
    kg_per_m = rail.VOLUME_MM3 * STEEL_KG_PER_MM3 / (rail.LENGTH / 1000.0)
    assert math.isclose(kg_per_m, rail.MASS_KG_PER_M, rel_tol=0.03)
    assert rail.CENTROID[:2] == (rail.LENGTH / 2.0, 0.0)
    assert 0.4 * rail.HEIGHT < rail.CENTROID[2] < rail.SECTION_CENTROID_Z


def test_rail_stations_are_unbanded_model_references() -> None:
    """Actual hardware transfers the pattern; nominal stations are REF only."""
    assert rail.STATION_DIMENSIONS == tuple(f"Station{k}" for k in range(1, 9))
    assert rail.DRAWING_DIMENSIONS == {
        "Rail": {"Length"},
        "BoltHoleProfile": set(rail.STATION_DIMENSIONS),
    }
    assert rail.REFERENCE_PLACES == base_bar.RAIL_HOLE_PLACES == 3
    assert rail.DRAWING_PRECISION == {
        "Rail": {"Length": 3},
        "BoltHoleProfile": dict.fromkeys(rail.STATION_DIMENSIONS, 3),
    }
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "set_dimension_symmetric_tolerance"
        for node in ast.walk(tree)
    )
    assert "BoltHoleProfile" in part.MEMBER_FEATURES["Rail"]


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


def test_hole_sketch_places_every_station_from_the_end_face(monkeypatch) -> None:
    adapter = _SketchAdapter()
    monkeypatch.setattr(
        part, "_sketch_mapper", lambda *_a, **_k: lambda point: (point[0], point[1])
    )

    async def fully_defined(*_args, **_kwargs):
        return None

    monkeypatch.setattr(part, "ensure_fully_defined", fully_defined)
    dims = asyncio.run(
        part._hole_circles(
            adapter, "Front", 0.0, rail.HOLE_DIA, "bolt hole",
            names=rail.STATION_DIMENSIONS,
        )
    )
    assert [x for x, _, _ in adapter.circles] == list(rail.HOLE_X)
    distances = [
        (ref1, ref2, value)
        for ref1, ref2, kind, value in adapter.dimensions
        if kind == "horizontal_distance"
    ]
    # Baseline: every hole from the origin (the -X end face), never chained.
    assert distances == [
        (f"circle{k}.center", "origin", x) for k, x in enumerate(rail.HOLE_X, start=1)
    ]
    assert adapter.relations == [
        (f"circle{k}.center", "origin", "horizontal_points")
        for k in range(1, rail.HOLE_COUNT + 1)
    ]
    assert [value for *_, kind, value in adapter.dimensions if kind == "diameter"] == [
        rail.HOLE_DIA
    ] * rail.HOLE_COUNT
    names = [name for name, _ in dims._rows]
    assert names[0::2] == list(rail.STATION_DIMENSIONS)
    assert names[1::2] == [None] * rail.HOLE_COUNT


def test_rail_receipt_note_points_at_the_stations() -> None:
    bar = _config.parts("ch-rocker-arm-tl-oblique-base-bar")
    lines = note_lines(rail.DRAWING_NOTES, label=NAME)
    assert len(lines) == 3
    assert all(len(line) <= 70 for line in lines), lines
    note = " ".join(lines)
    assert rail.WALL_ACCEPTANCE_MM == 2.0
    assert "[A] WALL FROM EACH END COUNTERBORE TO RAIL END: 2.0 MIN." in note
    assert "TAP WALL" not in note
    assert "TRANSFER TO" not in note
    assert "MHA-CH-06-TL-00 SHEET 1 LIMITS; SEALS ON RAIL, NO BIND" in rail.END_FIT_CALLOUT
    assert "KEEP EACH RAIL WITH ITS MATCHED BASE BAR" in note
    assert "ALL SCREWS MUST ENTER FREELY BY HAND" in note
    assert f"BASE BAR {bar['number']}" in rail.RECEIPT_FLAG
    assert "STATIONS REF" in rail.RECEIPT_FLAG
    assert rail.END_FIT_CALLOUT.splitlines()[0] == "RAIL ENDS FLUSH WITH BASE BAR ENDS"
    assert len(rail.END_FIT_CALLOUT.splitlines()) == 2
    assert rail.CBORE_END_WALL_WORST >= base_bar.WALL_TARGET_MM
    assert rail.CBORE_END_WALLS_WORST == pytest.approx((6.214, 5.96))
    assert {label for label, _, _ in draw.WALL_FLAGS} == {
        "near counterbore", "far counterbore",
    }
    assert len(draw.WALL_FLAGS) == 2
    assert draw.caption_text("RIGHT", (2, 1)) == "END VIEW  2:1"


def test_wall_flag_extent_includes_the_native_leader(monkeypatch) -> None:
    # 114c1622 near-end flag: GetExtent includes text AND leader to the end.
    reported = (
        0.023639363281249964, 0.16034543750000008,
        0.06191944531249996, 0.17927042187500009,
    )
    edge = (0.062036, 0.160)
    target = (0.024, 0.179)
    text_cell, envelope = draw.wall_flag_regions(edge, target)
    assert not _inside_box(reported, text_cell)
    assert _inside_box(reported, envelope)
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    annotation = SimpleNamespace(
        GetPosition=lambda: (*target, 0.0),
        GetLeaderCount=lambda: 1,
        GetLeaderPointsAtIndex=lambda _index: (*target, 0.0, *edge, 0.0),
    )
    note = SimpleNamespace(GetAnnotation=lambda: annotation)
    draw.assert_wall_flag_landing(note, edge, text_cell)
    # A leader-inclusive envelope is not a replacement for the text-lane guard.
    annotation.GetPosition = lambda: (*edge, 0.0)
    with pytest.raises(RuntimeError, match="text left its lane"):
        draw.assert_wall_flag_landing(note, edge, text_cell)
    annotation.GetPosition = lambda: (*target, 0.0)
    annotation.GetLeaderPointsAtIndex = lambda _index: (
        *target, 0.0, edge[0] + 0.003, edge[1], 0.0,
    )
    with pytest.raises(RuntimeError, match="intended feature"):
        draw.assert_wall_flag_landing(note, edge, text_cell)


def test_below_rail_wall_flags_clear_native_overall_ink(monkeypatch) -> None:
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    # Native 957501d1 extents, translated by the proven +20/+4 mm correction.
    length_text = (0.0706, 0.1744, 0.2073, 0.1870)
    length_lines = [((0.062, 0.1744), (0.282, 0.1744))]
    for _label, edge, target in draw.WALL_FLAGS:
        text_cell, envelope = draw.wall_flag_regions(edge, target)
        assert envelope[3] < length_lines[0][0][1] - draw.CLEAR_GAP_M
        annotation = SimpleNamespace(
            GetPosition=lambda: (*target, 0.0),
            GetLeaderCount=lambda: 1,
            GetLeaderPointsAtIndex=lambda _index: (*target, 0.0, *edge, 0.0),
        )
        note = SimpleNamespace(GetAnnotation=lambda: annotation)
        leaders = draw.assert_wall_flag_landing(note, edge, text_cell)
        draw.require_wall_leaders_clear(leaders, length_text, length_lines)
    # Crossing-path mutation against the measured overall-line segment.
    with pytest.raises(RuntimeError, match="overall Length line"):
        draw.require_wall_leaders_clear(
            (((0.250, 0.190), (0.277, 0.161875)),),
            length_text, length_lines,
        )
    with pytest.raises(RuntimeError, match="Length text"):
        draw.require_wall_leaders_clear(
            (((0.080, 0.200), (0.080, 0.160)),),
            length_text, length_lines,
        )
    source = Path(draw.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    settled = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "settled")
    assert any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "require_wall_leaders_clear"
        for n in ast.walk(settled)
    )


@pytest.mark.parametrize("bar_deviation", (-trammel.RAIL_LENGTH_BAND, trammel.RAIL_LENGTH_BAND))
@pytest.mark.parametrize("near_station", (8.0, 9.964, 12.0))
def test_actual_station_can_differ_from_reference_with_safe_walls(
    bar_deviation: float, near_station: float
) -> None:
    actual_bar = rail.LENGTH + bar_deviation
    # These deliberately do not fit the retired +/-0.080 station envelope.
    stations = tuple(near_station + 60.0 * k for k in range(8))
    base_bar.require_matched_rail_walls(
        counterbore_end_wall=min(stations[0], actual_bar - stations[-1]) - rail.CBORE_DIA / 2.0,
        tap_end_wall=min(stations[0], actual_bar - stations[-1]) - 2.1,
        tap_slot_wall=3.0, tap_bracket_wall=3.0,
    )


# --- Carriage member ----------------------------------------------------------------


def test_carriage_calculator_values_are_imported_not_retyped() -> None:
    assert carriage.MOUNTING_FACE_Z == trammel.CARRIAGE_HEIGHT == 28.0
    assert carriage.UNDERSIDE_Z == trammel.CARRIAGE_UNDER == 4.3
    assert carriage.WIDTH == trammel.CARRIAGE_WIDTH == 34.0
    assert carriage.LENGTH == trammel.CARRIAGE_LENGTH == 61.4
    assert trammel.CARRIAGE_BOLT_SPAN == (26.0, 26.0)
    assert carriage.BORE_DEPTH == pivot_block.CARRIAGE_THREAD_DEPTH == 5.0
    source = Path(carriage.__file__).read_text(encoding="utf-8")
    for name, value in (
        ("MOUNTING_FACE_Z", "CARRIAGE_HEIGHT"),
        ("UNDERSIDE_Z", "CARRIAGE_UNDER"),
        ("WIDTH", "CARRIAGE_WIDTH"),
        ("LENGTH", "CARRIAGE_LENGTH"),
    ):
        assert re.search(rf"^{name} = trammel\.{value}\b", source, re.M), name
    assert re.search(r"^BORE_DEPTH = CARRIAGE_THREAD_DEPTH\b", source, re.M)
    assert re.search(r"^SUPPLIER = rail\.SUPPLIER$", source, re.M)
    assert re.search(r"^SKU = rail\.SKU$", source, re.M)


def test_carriage_frame_puts_face_underside_and_bolts_where_the_jig_expects() -> None:
    assert set(carriage.BOLT_POINTS) == {
        (x, y) for x in (-13.0, 13.0) for y in (-13.0, 13.0)
    }
    assert set(carriage.BOLT_POINTS) == set(pivot_block.BOLT_POINTS)
    body_y = [y for y, _ in carriage.BODY_OUTLINE]
    body_z = [z for _, z in carriage.BODY_OUTLINE]
    assert (min(body_y), max(body_y)) == (-carriage.WIDTH / 2.0, carriage.WIDTH / 2.0)
    assert (min(body_z), max(body_z)) == (carriage.UNDERSIDE_Z, carriage.MOUNTING_FACE_Z)
    cap_z = [z for _, z in carriage.CAP_OUTLINE]
    assert (min(cap_z), max(cap_z)) == (carriage.UNDERSIDE_Z, carriage.END_CAP_TOP_Z)
    groove_edge = max(abs(y) for y, z in carriage.BODY_OUTLINE if z == 27.5) + 0.5
    for _, y in carriage.BOLT_POINTS:
        assert abs(y) - carriage.BORE_DIA / 2.0 > groove_edge
    assert math.isclose(carriage.NIPPLE_Z, 20.05)
    assert math.isclose(carriage.NIPPLE_Z - rail.HEIGHT, 5.05)
    assert carriage.NIPPLE_FACE_X == carriage.LENGTH / 2.0 == -carriage.PLUG_FACE_X
    lo, hi = carriage.REFERENCE_BBOX_MIN, carriage.REFERENCE_BBOX_MAX
    assert math.isclose(
        hi[0] - lo[0], carriage.LENGTH + carriage.NIPPLE_PROUD + carriage.PLUG_PROUD
    )
    assert math.isclose(lo[1] + rail.HEIGHT, carriage.UNDERSIDE_Z)
    assert math.isclose(hi[1] + rail.HEIGHT, carriage.MOUNTING_FACE_Z)
    assert (lo[2], hi[2]) == (-carriage.WIDTH / 2.0, carriage.WIDTH / 2.0)
    assert all(_inside(p, carriage.BODY_OUTLINE) for p in carriage.CAP_OUTLINE)
    assert carriage.BORE_DIA == 3.242


def test_carriage_sections_are_simple_and_clear_the_rail() -> None:
    for name in ("BODY_OUTLINE", "CAP_OUTLINE", "CHANNEL", "BODY_SECTION", "CAP_SECTION"):
        points = getattr(carriage, name)
        assert _simple(points), name
        assert _shoelace(points) > 0.0, name
    assert min(z for _, z in carriage.CHANNEL) == carriage.CHANNEL_FLOOR_Z < carriage.UNDERSIDE_Z
    for section in (carriage.BODY_SECTION, carriage.CAP_SECTION):
        gap = _gap(section, rail.SECTION)
        assert math.isclose(gap, carriage.CHANNEL_CLEARANCE, abs_tol=1e-6)
    for p in rail.SECTION:
        if p[1] > carriage.UNDERSIDE_Z:
            assert _inside(p, carriage.CHANNEL_IN_BLOCK), p


def test_carriage_volume_against_the_reference_step() -> None:
    v_caps = _shoelace(carriage.CAP_OUTLINE) * carriage.LENGTH
    v_body = (
        _shoelace(carriage.BODY_OUTLINE) - _shoelace(carriage.CAP_OUTLINE)
    ) * carriage.BODY_LENGTH
    v_channel = _shoelace(carriage.CHANNEL_IN_BLOCK) * carriage.LENGTH
    v_bores = 4 * math.pi * 1.621**2 * 5.0
    v_ends = (
        math.pi * 3.0**2 * carriage.NIPPLE_PROUD
        + math.pi * 3.76**2 * carriage.PLUG_PROUD
    )
    assert math.isclose(
        carriage.VOLUME_MM3, v_caps + v_body - v_channel - v_bores + v_ends, rel_tol=1e-12
    )
    explained = (
        -carriage.CHANNEL_EXCESS_MM2 * carriage.LENGTH
        + carriage.V_DRILL_POINTS
        + carriage.CAP_INTERNAL_MM3
        + carriage.V_NIPPLE
        - carriage.REFERENCE_NIPPLE_VOLUME_MM3
        + carriage.V_PLUG
        - carriage.REFERENCE_PLUG_VOLUME_MM3
    )
    difference = carriage.VOLUME_MM3 - carriage.REFERENCE_VOLUME_MM3
    assert abs(difference - explained) < carriage.REFERENCE_BODY_ALLOWANCE_MM3
    assert abs(difference) < 0.02 * carriage.REFERENCE_VOLUME_MM3
    residual = carriage.REFERENCE_BODY_MODEL_MM3 - carriage.REFERENCE_BODY_VOLUME_MM3
    assert abs(residual) < carriage.REFERENCE_BODY_ALLOWANCE_MM3
    vendor = 2.0 * (carriage.REFERENCE_CAP_VOLUME_MM3 + carriage.REFERENCE_SEAL_VOLUME_MM3)
    assert 0.0 < carriage.CAP_INTERNAL_MM3 < 0.08 * vendor
    assert 0.0 < carriage.CENTROID[0] < 0.5
    assert 0.0 < carriage.CENTROID[1] < 0.5
    assert carriage.UNDERSIDE_Z < carriage.CENTROID[2] < carriage.MOUNTING_FACE_Z


def test_carriage_note_is_the_owner_kit_description_and_play_acceptance() -> None:
    """The owner's description (#2177), the rail named by its item on the same
    sheet, the play check's home, how the carrier is rocked and where the
    indicator reads (20261104T194839817Z: 'AT PIVOT' named an undrawn feature)."""
    assert carriage.JIG_NUMBER == jig.DRAWING_NUMBER
    lines = note_lines(carriage.DRAWING_NOTES, label=NAME)
    assert len(lines) == 3
    assert all(len(line) <= 70 for line in lines), lines
    note = " ".join(lines)
    assert lines[0].startswith(f"{carriage.ITEM_TAG} ")
    for fact in (
        "GENERIC HIWIN-STYLE",
        "NUIBBYED-BRANDED",
        "NOT GENUINE HIWIN",
        f"MATCHED KIT WITH RAIL {rail.ITEM_TAG}",
        "Z0 PRELOAD, C ACCURACY NOT REQUIRED",
        f"IN {jig.DRAWING_NUMBER}: ROCK SIDEWAYS",
        f"{trammel.CARRIAGE_PLAY_TIR_MAX:.2f} MM TIR MAX AT SHOULDER SCREW",
    ):
        assert fact in note, fact
    assert "PIVOT" not in note
    assert trammel.CARRIAGE_PLAY_TIR_MAX == 0.02
    # The item tags are the sheet's own member labels.
    assert [label.split()[0] for _, label in draw.VARIANTS] == [
        rail.ITEM_TAG, carriage.ITEM_TAG,
    ]


def test_member_specs_are_pure_data() -> None:
    allowed = {
        rail: {
            "__future__", "math",
            "ch_rocker_arm_tl_oblique_trammel_spec",
            "ch_rocker_arm_tl_oblique_base_bar_spec",
        },
        carriage: {
            "__future__", "math",
            "ch_rocker_arm_tl_oblique_pivot_block_spec",
            "ch_rocker_arm_tl_vn_oblique_rail_kit_rail_spec",
            "ch_rocker_arm_tl_oblique_trammel_spec",
        },
    }
    for spec, modules in allowed.items():
        source = Path(spec.__file__).read_text(encoding="utf-8")
        imports = set(re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE))
        assert imports <= modules, spec.__name__
        doc = spec.__doc__ or ""
        for mark in (
            "KIT LISTING", "REFERENCE GEOMETRY", "REFERENCE STEP", "SOURCED",
            "FROM THE CALCULATOR", "UNVERIFIED",
        ):
            assert mark in doc, (spec.__name__, mark)
        assert spec.REFERENCE_STEP in doc
        assert "HIWIN is not the supplier" in doc
        assert re.fullmatch(r"[0-9a-f]{64}", spec.REFERENCE_STEP_SHA256)
        assert spec.REFERENCE_DOWNLOADED == "2026-10-17"
        assert ROW["number"] in doc


# --- The drawing package ------------------------------------------------------------


def test_package_is_the_registered_configured_reference_with_a_receipt_sheet(
    monkeypatch,
) -> None:
    sheet = DRAWINGS_BY_NAME[NAME]
    assert draw.SPEC is sheet
    assert (sheet.part, sheet.artifact_stem, sheet.script_name) == (
        NAME, STEM, f"draw_{NAME}.py",
    )
    assert sheet.layout is DrawingLayout.LANDSCAPE
    assert sheet.source_kind == "part"
    assert "ch_rocker_arm_tl_vn_oblique_rail" not in DRAWINGS_BY_NAME
    assert "ch_rocker_arm_tl_vn_oblique_carriage" not in DRAWINGS_BY_NAME
    assert tuple(configuration for configuration, _ in draw.VARIANTS) == part.CONFIGURATIONS
    assert draw.SHEET_NAMES == ("RAIL RECEIPT",)
    assert draw.SHEET_NAMES.index(draw.RECEIPT_SHEET_NAME) + 2 == rail.RECEIPT_SHEET
    assert f"{rail.ITEM_TAG} RECEIPT CHECK PER SHEET {rail.RECEIPT_SHEET}" in draw.GENERAL_TEXT
    assert check_item(draw.ITEM, label=NAME) == draw.ITEM
    assert rail.STYLE in draw.ITEM and carriage.STYLE in draw.ITEM
    assert "GENERIC" in draw.ITEM and "Z0" not in draw.ITEM
    assert f"{rail.LENGTH:.0f}" not in draw.ITEM
    assert draw.FOOTER_NOTES == carriage.DRAWING_NOTES
    calls = []

    async def fake(adapter, drawn, **kwargs):
        calls.append((adapter, drawn, kwargs))
        return {"pdf": "x"}

    monkeypatch.setattr(draw, "build_purchased_variant_drawing", fake)
    adapter = object()
    assert asyncio.run(draw.build(adapter)) == {"pdf": "x"}
    ((called, drawn, kwargs),) = calls
    assert (called, drawn) == (adapter, sheet)
    assert kwargs["variants"] == draw.VARIANTS
    assert kwargs["notes"] == carriage.DRAWING_NOTES
    assert kwargs["general_text"] == draw.GENERAL_TEXT
    assert kwargs["additional_sheet_scales"] == {"RAIL RECEIPT": draw.SHEET_SCALE}
    assert kwargs["append_sheets"] is draw.append_rail_receipt_sheet
    assert kwargs["title_fit"] is True
    assert kwargs["unit"] == "mm"
    # Sheet 1's rail is its isometric, its header citing the receipt sheet
    # (at 1:8 its orthographic views read as a bar and dots); the carriage
    # keeps its four views.
    assert kwargs["isometric_only"] == {"Rail": rail.RECEIPT_SHEET} == {"Rail": 2}
    import _purchased_variant_drawing as variant_drawing

    for index, (configuration, label) in enumerate(draw.VARIANTS):
        header = f"{label}  QTY {ROW['configuration_quantities'][configuration]} INSTALLED"
        if configuration in kwargs["isometric_only"]:
            header += f", SEE SHEET {kwargs['isometric_only'][configuration]}"
        cells = variant_drawing.configuration_view_cells(index, len(draw.VARIANTS))
        width = cells[2][2][2] - cells[0][2][0]
        assert len(header) * 0.0025 <= width, header


def test_receipt_dimensions_are_the_marked_model_dimensions() -> None:
    marked = set().union(*rail.DRAWING_DIMENSIONS.values())
    assert set(draw.RECEIPT_DIMENSIONS) == marked
    assert set(draw.FRONT_DIMENSION_PRECISION) == marked
    # The short first span uses outside arrows; all other stations stay inside.
    assert draw.STATION_ARROW_SIDES == {
        name: (1 if index == 0 else 0)
        for index, name in enumerate(rail.STATION_DIMENSIONS)
    }
    assert draw.RECEIPT_DIMENSIONS["Length"][:2] == (0.0, rail.LENGTH)
    offsets = []
    for name, x in zip(rail.STATION_DIMENSIONS, rail.HOLE_X, strict=True):
        start, end, offset = draw.RECEIPT_DIMENSIONS[name]
        assert (start, end) == (0.0, x)  # baseline from the -X end face
        offsets.append(offset)
    # Rows step outward with the station: shortest nearest the part, so no
    # extension line crosses a nearer row's dimension line.
    assert offsets == sorted(offsets, reverse=True)
    assert all(b - a == pytest.approx(-draw.STATION_ROW_PITCH) for a, b in zip(offsets, offsets[1:]))
    rail_edge = draw._FRONT_HALF[1]
    assert -offsets[0] - 0.003 > rail_edge
    assert draw.RECEIPT_DIMENSIONS["Length"][2] - 0.003 > rail_edge
    # The pitch leaves a row's text CLEAR_GAP_M under the nearer row's
    # extension-line overrun, which ends over the 75 and 135 values.
    text_top = draw.TEXT_OVER_LINE + draw.DIMENSION_TEXT_HEIGHT / 2.0
    assert draw.STATION_ROW_PITCH - text_top - _EXTENSION_GAP >= draw.CLEAR_GAP_M + 0.0005


_EXTENSION_GAP = 0.0016  # extension lines start off, and overrun, by this much


def _stack_ink(*, pitch=None, lift=None):
    """The receipt stack as SolidWorks printed run 20261104T222143958Z's:
    each text centred at its requested point, its dimension line
    ``TEXT_OVER_LINE`` under it, the extension lines from the part to just
    past the line. ``pitch`` re-spaces the station rows; ``lift`` raises
    named texts off their lines (sheet metres)."""
    per_mm = draw._sheet_mm(draw.SHEET_SCALE)
    center_y = draw.FRONT_CENTER[1]
    end_face_x = draw.FRONT_CENTER[0] - draw._FRONT_HALF[0]
    edge = draw._FRONT_HALF[1]

    def sheet(x_mm: float) -> tuple[float, float]:
        return end_face_x + x_mm * per_mm, center_y

    inks = {}
    for name, (start, end, offset) in draw.RECEIPT_DIMENSIONS.items():
        if pitch is not None and name != "Length":
            offset = -(draw.STATION_FIRST_DROP + rail.STATION_DIMENSIONS.index(name) * pitch)
        x, y = draw.receipt_text_point(name, sheet(start), sheet(end), offset)
        line_y = y - draw.TEXT_OVER_LINE
        y += (lift or {}).get(name, 0.0)
        if name == "Length":
            text = f"({rail.LENGTH:.3f})"
        else:
            text = f"({end:.{rail.REFERENCE_PLACES}f})"
        box = estimate_text_box(
            text, anchor=(x, y), height=draw.DIMENSION_TEXT_HEIGHT, reference=2
        )
        text_box = (box.xmin, box.ymin, box.xmax, box.ymax)
        if name == "Length":
            above = estimate_text_box(
                rail.END_FIT_CALLOUT, anchor=(x, y + 0.005),
                height=draw.DIMENSION_TEXT_HEIGHT, reference=2,
            )
            text_box = (
                min(text_box[0], above.xmin), text_box[1],
                max(text_box[2], above.xmax), above.ymax,
            )
        x0, x1 = sheet(start)[0], sheet(end)[0]
        segments = [((x0, line_y), (x1, line_y))]
        if name in draw.TEXT_OUTSIDE_START:  # the leg under the outside text
            segments.append(((text_box[0], line_y), (x0, line_y)))
        down = line_y < center_y
        part_side = center_y - edge - _EXTENSION_GAP if down else center_y + edge + _EXTENSION_GAP
        overrun = line_y - _EXTENSION_GAP if down else line_y + _EXTENSION_GAP
        segments += [((x0, part_side), (x0, overrun)), ((x1, part_side), (x1, overrun))]
        inks[name] = (text_box, segments)
    flag = estimate_text_box(
        rail.RECEIPT_FLAG,
        anchor=draw.RECEIPT_FLAG_XY,
        height=draw.DIMENSION_TEXT_HEIGHT,
        reference=5,
    )
    return end_face_x, per_mm, inks, (flag.xmin, flag.ymin, flag.xmax, flag.ymax)


def test_receipt_stack_keeps_each_value_on_its_own_line_clear_of_the_others() -> None:
    _, _, inks, flag = _stack_ink()
    assert draw.receipt_stack_findings(inks, flag) == []
    assert _inside_box(flag, draw.RECEIPT_FLAG_CELL)


def test_native_short_station_ink_uses_the_outside_witness_lane() -> None:
    """Pinned native text/line extents, 20261107T002231Z-1-4eb76c9d.

    Unlike the font estimator, these include the entire native tolerance
    block. Translate only the authored text targets and the FRONT origin;
    keep measured widths, heights, row lines and witness overruns unchanged.
    """
    native_x = (
        (0.0222, 0.0525), (0.0614, 0.0939), (0.0751, 0.1098),
        (0.0901, 0.1248), (0.1051, 0.1398), (0.1201, 0.1548),
        (0.1351, 0.1698), (0.1501, 0.1848),
    )
    _, _, inks, flag = _stack_ink()
    old_inks = {}
    view_shift = draw.FRONT_CENTER[0] - 0.170
    old_end = 0.170 - draw._FRONT_HALF[0]
    new_end = old_end + view_shift
    front_cell = draw.view_cell(draw.FRONT_CENTER, draw._FRONT_HALF)
    for index, (name, (left, right)) in enumerate(zip(rail.STATION_DIMENSIONS, native_x, strict=True)):
        line_y = 0.1492 - index * 0.0085
        witness_end = 0.065 + index * 0.030
        old_box = (left, line_y, right, line_y + 0.0035)
        old_segments = [
            ((0.060, 0.159), (0.060, line_y - 0.001)),
            ((witness_end, 0.159), (witness_end, line_y - 0.001)),
            ((0.060, line_y), (witness_end, line_y)),
        ]
        if index == 0:
            old_segments.append(((left, line_y), (0.060, line_y)))
        old_inks[name] = (old_box, old_segments)
        station = draw.STATION_NOMINALS[name]
        old_target = old_end - 0.023 if index == 0 else old_end + station * 0.00025
        new_target, _ = draw.receipt_text_point(
            name, (new_end, 0.160), (new_end + station * 0.0005, 0.160), 0.0
        )
        dx = new_target - old_target
        box = (left + dx, line_y, right + dx, line_y + 0.0035)
        segments = [
            ((a[0] + view_shift, a[1]), (b[0] + view_shift, b[1]))
            for a, b in old_segments[:3]
        ]
        if name in draw.TEXT_OUTSIDE_START:
            segments.append(((box[0], line_y), (0.060 + view_shift, line_y)))
            assert box[2] + draw.CLEAR_GAP_M <= front_cell[0], name
            assert box[0] >= BORDER[0] + 0.005, name
        inks[name] = (box, segments)
    old_findings = draw.receipt_stack_findings(old_inks, flag)
    for index in range(3, 9):
        assert f"Station{index} line runs within 2 mm of Station2 text" in old_findings
    assert draw.receipt_stack_findings(inks, flag) == []


def test_receipt_stack_rule_refuses_run_20261104T222143958Z() -> None:
    """The farm's FIX: the callout under 435.00 lifted that value 2.5 mm,
    onto 375.00's text and its line, off its own (5.5 mm rows)."""
    _, _, inks, flag = _stack_ink(pitch=0.0055, lift={"Station8": 0.0025})
    findings = draw.receipt_stack_findings(inks, flag)
    assert "Station8 text foot stands 3.35 mm off its own line" in findings
    assert "Station7 text and Station8 text overlap" in findings
    assert "Station7 line runs within 2 mm of Station8 text" in findings


def test_receipt_stack_rule_refuses_a_row_pitch_under_the_gap() -> None:
    # 5.5 mm rows leave each text 1.15 mm under the next row's line.
    _, _, inks, flag = _stack_ink(pitch=0.0055)
    findings = draw.receipt_stack_findings(inks, flag)
    assert "Station1 line runs within 2 mm of Station2 text" in findings
    assert len([f for f in findings if "line runs within" in f]) >= 7


def test_receipt_stack_rule_refuses_a_flag_on_the_stack() -> None:
    _, _, inks, flag = _stack_ink()
    last_line = inks["Station8"][1][0][0][1]
    raised = (flag[0], last_line - 0.001, flag[2], last_line + 0.0025)
    findings = draw.receipt_stack_findings(inks, raised)
    assert "the flag is not under the last station line" in findings
    assert "Station8 line runs into the flag" in findings


def _inside_box(inner, outer) -> bool:
    return (
        outer[0] <= inner[0] and outer[1] <= inner[1]
        and inner[2] <= outer[2] and inner[3] <= outer[3]
    )


def test_receipt_texts_fit_their_spans_rows_and_the_border() -> None:
    end_face_x, per_mm, inks, _ = _stack_ink()
    boxes = {name: text for name, (text, _) in inks.items()}
    front_cell = draw.view_cell(draw.FRONT_CENTER, draw._FRONT_HALF)
    for name in rail.STATION_DIMENSIONS:
        box = boxes[name]
        if name in draw.TEXT_OUTSIDE_START:
            assert box[2] + draw.CLEAR_GAP_M <= front_cell[0], name
            assert box[0] >= BORDER[0] + 0.005, name
            continue
        x = draw.STATION_NOMINALS[name]
        # Long stations fit between their own extension lines.
        assert end_face_x + 0.002 <= box[0] and box[2] + 0.002 <= end_face_x + x * per_mm, name


def test_receipt_sheet_views_captions_and_notes_fit() -> None:
    footer = footer_top(rail.DRAWING_NOTES, label=NAME)
    assert draw.RECEIPT_NOTE_TOP == footer
    cells = {name: draw.view_cell(center, half) for name, center, half, _ in draw.VIEWS}
    _, _, inks, _ = _stack_ink()
    texts = {name: text for name, (text, _) in inks.items()}
    flag = draw.RECEIPT_FLAG_CELL
    texts["flag"] = flag
    for name, cell in cells.items():
        assert BORDER[0] <= cell[0] and cell[2] <= BORDER[2], name
        assert footer < cell[1] and cell[3] <= BORDER[3], name
        assert not _overlaps(cell, TITLE_BLOCK), name
        for text_name, box in texts.items():
            assert not _overlaps(cell, box), (name, text_name)
    names = sorted(cells)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            assert not _overlaps(cells[first], cells[second]), (first, second)
    assert draw.TOP_CENTER[0] == draw.FRONT_CENTER[0]
    assert draw.RIGHT_CENTER[1] == draw.FRONT_CENTER[1]
    caption_boxes = {}
    for label, x, y, scale in draw.CAPTIONS:
        cell = cells[f"*{label.title()}"]
        assert y < cell[1] and cell[0] < x < cell[2], label
        assert y - 0.006 > footer, label
        expected_label = "END VIEW" if label == "RIGHT" else label
        assert draw.caption_text(label, scale).startswith(expected_label)
        box = (x - draw._CAPTION_HALF_WIDTH, y - 0.006, x + draw._CAPTION_HALF_WIDTH, y + 0.001)
        caption_boxes[label] = box
        for text_name, text in texts.items():
            assert not _overlaps(box, text), (label, text_name)
        for other, cell in cells.items():
            assert not _overlaps(box, cell), (label, other)
    # The full two-line fit callout, not just the nominal length value,
    # must clear TOP's caption. The a966 layout overlapped by 1.54 mm.
    assert caption_boxes["TOP"][1] >= texts["Length"][3] + draw.CLEAR_GAP_M

    # The flag stands between the stack and FRONT's caption, in the run of
    # the end face and last station's extension lines.
    end_face_x = draw.FRONT_CENTER[0] - draw._FRONT_HALF[0]
    assert end_face_x < flag[0] and flag[2] < end_face_x + rail.HOLE_X[-1] * 0.0005
    assert caption_boxes["FRONT"][3] < flag[1]
    label = draw.ITEM_LABEL_CELL
    assert all(not _overlaps(label, cell) for cell in cells.values())
    assert BORDER[1] < label[1] and label[3] <= BORDER[3]
    note = draw.RECEIPT_NOTE_CELL
    assert note[3] == pytest.approx(footer + 0.001)
    assert not _overlaps(note, TITLE_BLOCK)


def test_native_multiline_length_ink_clears_witnesses_and_top_caption() -> None:
    """Native 957501d1 geometry, not a centred-font approximation."""
    _, _, inks, flag = _stack_ink()
    old_text = (0.0506, 0.1704, 0.1873, 0.1830)
    old_lines = [
        ((0.062, 0.1644), (0.062, 0.1714)),
        ((0.282, 0.1644), (0.282, 0.1714)),
        ((0.062, 0.1704), (0.0557, 0.1704)),
        ((0.062, 0.1704), (0.282, 0.1704)),
        ((0.282, 0.1704), (0.2883, 0.1704)),
    ]
    assert "Length text sits on its own extension line" in draw.receipt_stack_findings(
        {"Length": (old_text, old_lines)}, flag
    )
    dx = draw.LENGTH_TEXT_SHIFT
    dy = draw.LENGTH_ROW_RISE - 0.016
    text = (old_text[0] + dx, old_text[1] + dy, old_text[2] + dx, old_text[3] + dy)
    lines = [
        ((a[0], a[1] if index < 2 else a[1] + dy), (b[0], b[1] + dy))
        for index, (a, b) in enumerate(old_lines)
    ]
    inks["Length"] = (text, lines)
    assert draw.receipt_stack_findings(inks, flag) == []
    assert text[0] >= 0.062 + draw.CLEAR_GAP_M
    assert text[2] <= 0.282 - draw.CLEAR_GAP_M
    assert text[1] >= draw.view_cell(draw.FRONT_CENTER, draw._FRONT_HALF)[3] + draw.CLEAR_GAP_M
    top_caption_y = next(y for label, _x, y, _scale in draw.CAPTIONS if label == "TOP")
    assert top_caption_y - 0.006 >= text[3] + draw.CLEAR_GAP_M


class _Tolerance:
    def __init__(self, kind: int, low: float, high: float) -> None:
        self.Type = kind
        self._low, self._high = low, high

    def GetMinValue(self) -> float:
        return self._low

    def GetMaxValue(self) -> float:
        return self._high


class _Display:
    def __init__(self, value_mm: float, texts: dict[int, str], tolerance, places=2) -> None:
        self.dimension = SimpleNamespace(SystemValue=value_mm / 1000.0, Tolerance=tolerance)
        self.texts = texts
        self.places = places
        self.ArrowSide = 0

    def GetDimension2(self, _index):
        return self.dimension

    def GetText(self, part_index: int) -> str:
        return self.texts.get(part_index, "")

    def GetPrimaryTolPrecision2(self) -> int:
        return self.places


class _Annotation:
    def __init__(self, name: str, display: _Display) -> None:
        self.name = name
        self.display = display

    def GetSpecificAnnotation(self):
        return self.display


def _receipt_annotations():
    annotations = [
        _Annotation(
            name,
            _Display(
                x,
                {1: "(", 2: ")"},
                _Tolerance(0, 0, 0),
                places=rail.REFERENCE_PLACES,
            ),
        )
        for name, x in zip(rail.STATION_DIMENSIONS, rail.HOLE_X, strict=True)
    ]
    for annotation in annotations:
        annotation.display.ArrowSide = draw.STATION_ARROW_SIDES[annotation.name]
    annotations.append(
        _Annotation("Length", _Display(
            rail.LENGTH, {1: "(", 2: ")", 3: rail.END_FIT_CALLOUT},
            _Tolerance(0, 0, 0), rail.DRAWING_PRECISION["Rail"]["Length"],
        ))
    )
    return annotations


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "widened",
        "bilateral",
        "bare",
        "callout",
        "length-bare",
        "length-fit-flag",
        "missing",
        "arrows",
        "short-arrows",
        "nominal",
    ],
)
def test_receipt_controls_readback_refuses_every_drift(monkeypatch, fault) -> None:
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "dimension_name", lambda _adapter, annotation: annotation.name)
    annotations = _receipt_annotations()
    by_name = {annotation.name: annotation.display for annotation in annotations}
    if fault == "widened":
        by_name["Station4"].dimension.Tolerance = _Tolerance(4, -1e-5, 1e-5)
    elif fault == "bilateral":
        by_name["Station2"].dimension.Tolerance = _Tolerance(2, -1e-5, 1e-5)
    elif fault == "bare":
        by_name["Station5"].texts = {}
    elif fault == "callout":
        by_name["Station8"].texts = {4: rail.RECEIPT_FLAG}
    elif fault == "length-bare":
        by_name["Length"].texts = {}
    elif fault == "length-fit-flag":
        by_name["Length"].texts[3] = ""
    elif fault == "missing":
        annotations = annotations[1:]
    elif fault == "arrows":
        by_name["Station5"].ArrowSide = 1
    elif fault == "short-arrows":
        by_name["Station1"].ArrowSide = 0
    elif fault == "nominal":
        by_name["Station6"].dimension.SystemValue += 0.0001
    if fault is None:
        draw.assert_receipt_controls(object(), annotations)
    else:
        with pytest.raises(RuntimeError):
            draw.assert_receipt_controls(object(), annotations)


def test_sheet_one_footer_and_purchase_note_fit_their_budgets() -> None:
    lines = note_lines(draw.FOOTER_NOTES, label=NAME)
    assert len(lines) == 3
    purchase_note = (
        f"QTY {ROW['quantity']} INSTALLED MEMBERS; PURCHASE UNIT: {draw.PURCHASE_UNIT}."
    )
    # At about 2.5 mm a character: the purchase note's reserved 0.015..0.415
    # band, the general line's _NOTE_X.._FOOTER_RIGHT footer width.
    from _purchased_fastener_drawing import _FOOTER_RIGHT, _NOTE_X

    assert len(purchase_note) * 0.0025 <= 0.415 - 0.018
    assert len(draw.GENERAL_TEXT) * 0.0025 <= _FOOTER_RIGHT - _NOTE_X
    assert all(len(line) * 0.0025 <= _FOOTER_RIGHT - _NOTE_X for line in lines)
    # The kit supplies the carriages the jig leaves spare: 4 bought, 2 installed.
    assert "2 RAILS AND 4 CARRIAGES" in draw.PURCHASE_UNIT
