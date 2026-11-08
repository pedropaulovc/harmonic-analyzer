"""ReliaBot T8 kit (MHA-CH-06-TL-VN-84): LeadScrew and FeedNut members, SolidWorks-free."""

from __future__ import annotations

import ast
import asyncio
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _purchased_fastener_drawing as footer
import _purchased_part_variants as variants
import _supplier_screw_dimensions as supplier_dimensions
import _stock_trim_drawing as trim_drawing
import build_ch_rocker_arm_tl_vn_oblique_leadscrew_kit as part
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec as nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec as spec
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed
import draw_ch_rocker_arm_tl_vn_oblique_leadscrew_kit as draw
from _drawing_annotation_extent import CLEAR_GAP_M, CalloutInk, boxes_clear
from _drawing_contract import drawing_specification_violations, model_toleranced_dimensions
from _drawing_layout_check import DrawableRegion, LeaderSegment
from _drawing_notes import property_link
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _machinist_review_mode import MachinistReviewMode
from _mcmaster_91771a112 import DIMS as SCREW_DIMS
from _printed_tolerance import printed_band_mm

STEM = "ch-rocker-arm-tl-vn-oblique-leadscrew-kit"
NAME = "ch_rocker_arm_tl_vn_oblique_leadscrew_kit"
ROW = _config.parts(STEM)
SCRIPTS = Path(__file__).resolve().parent
RETIRED = (
    "ch-rocker-arm-tl-vn-oblique-leadscrew",  # MHA-CH-06-TL-VN-54
    "ch-rocker-arm-tl-vn-oblique-feed-nut",  # MHA-CH-06-TL-VN-82, never released
    "ch-rocker-arm-tl-oblique-feed-nut",  # MHA-CH-06-TL-27
    "ch-rocker-arm-tl-vn-oblique-nut-dowel",  # MHA-CH-06-TL-VN-81
    "ch-rocker-arm-tl-vn-oblique-nut-screw",  # MHA-CH-06-TL-VN-66
)


def test_kit_row_has_one_configuration_per_member() -> None:
    assert ROW["number"] == spec.NUMBER == nut.NUMBER == "MHA-CH-06-TL-VN-84"
    assert spec.PART_NAME == nut.PART_NAME == part.PART_NAME == STEM
    assert ROW["process"] == "purchased"
    assert ROW["drawing_unit"] == "mm"
    assert ROW["supplier"] == spec.SUPPLIER == nut.SUPPLIER == "Amazon (sold by ReliaBot)"
    assert ROW["supplier_skus"] == [spec.SKU] == [nut.SKU] == ["B085DDHJTW"]
    assert spec.SUPPLIER_PRODUCT_URL == f"https://www.amazon.com/dp/{spec.SKU}"
    # One member per configuration, LeadScrew the default, each its own
    # installed quantity; the kit's quantity is their sum.
    assert ROW["default_configuration"] == spec.CONFIGURATION == "LeadScrew"
    assert part.CONFIGURATIONS == (spec.CONFIGURATION, nut.CONFIGURATION)
    assert part.CONFIGURATIONS == ("LeadScrew", "FeedNut")
    assert variants.require_member_configurations(STEM, part.CONFIGURATIONS) == (
        part.CONFIGURATIONS
    )
    assert ROW["configuration_quantities"] == {
        spec.CONFIGURATION: spec.QUANTITY,
        nut.CONFIGURATION: nut.QUANTITY,
    } == {"LeadScrew": 1, "FeedNut": 1}
    assert int(ROW["quantity"]) == sum(ROW["configuration_quantities"].values()) == 2
    assert tuple(name for name, _label in draw.VARIANTS) == part.CONFIGURATIONS
    # Each member its own library material and its own BOM grouping key.
    assert part.MATERIALS == {"LeadScrew": spec.MATERIAL, "FeedNut": nut.MATERIAL}
    assert part.MATERIALS == {"LeadScrew": "AISI 304", "FeedNut": "Brass"}
    assert part.MEMBER_DESCRIPTIONS == {
        "LeadScrew": spec.BOM_DESCRIPTION,
        "FeedNut": nut.BOM_DESCRIPTION,
    }
    assert spec.BOM_DESCRIPTION == f"TR8X2 LEADSCREW, {spec.LENGTH:.{spec.LENGTH_PLACES}f} MM LONG"
    # One line in the title block's MATERIAL cell; the provenance is the specs'.
    assert len(ROW["material_specification"]) <= 36
    assert spec.SKU in (spec.__doc__ or "")
    assert "Datasheet-built" in (spec.__doc__ or "")
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }
    assert spec.INVENTORY_ID == "fixtures.trammel-tr8-leadscrew"


def test_retired_identities_left_no_registry_producer_or_sheet() -> None:
    root = SCRIPTS.parent
    for stem in RETIRED:
        name = stem.replace("-", "_")
        assert not (root / "config" / "parts" / f"{stem}.yaml").exists(), stem
        assert name not in DRAWINGS_BY_NAME, stem
        for script in (f"build_{name}.py", f"draw_{name}.py", f"test_{name}_drawing.py"):
            assert not (SCRIPTS / script).exists(), script
    for module in (
        "ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec",
        "ch_rocker_arm_tl_vn_oblique_feed_nut_spec",
    ):
        assert not (SCRIPTS / f"{module}.py").exists(), module
    # TL-VN-54 is never reissued and TL-VN-82 stays reserved.
    numbers = {str(row.get("number")) for row in _config.parts().values()}
    assert "MHA-CH-06-TL-VN-84" in numbers
    assert not numbers & {"MHA-CH-06-TL-VN-54", "MHA-CH-06-TL-VN-82"}


def test_member_features_partition_the_model() -> None:
    """Each feature belongs to one member, parents first; the shared
    ScrewAxis belongs to neither."""
    lead = part.MEMBER_FEATURES[spec.CONFIGURATION]
    fitted = part.MEMBER_FEATURES[nut.CONFIGURATION]
    assert set(part.MEMBER_FEATURES) == set(part.CONFIGURATIONS)
    assert len(set(lead)) == len(lead) and len(set(fitted)) == len(fitted)
    assert not set(lead) & set(fitted)
    assert "ScrewAxis" not in {*lead, *fitted}
    assert set(spec.DRAWING_DIMENSIONS) | set(part.CLOCK_PLANES) <= set(lead)
    assert set(nut.DRAWING_DIMENSIONS) <= set(fitted)
    assert {"SupplierReference", "SupplierTopReference"} <= set(fitted)
    assert lead[:4] == ("ScrewProfile", "Screw", "FlatProfile", "Flats")
    for name in spec.CLOCKED_FLATS:
        plane, profile, flat = (
            lead.index(f"{name}{suffix}")
            for suffix in ("ClockPlane", "ClockProfile", "ClockFlat")
        )
        assert plane < profile < flat
    assert fitted[:4] == ("NutProfile", "Nut", "FlangeHoleSketch", "FlangeHoles")
    for index in range(1, len(nut.COUNTERSINK_AXES) + 1):
        assert fitted.index(f"Countersink{index}Profile") + 1 == fitted.index(
            f"Countersink{index}"
        )
    # Each member's notes say where its work is drawn.
    assert part.MEMBER_NOTE_PROPERTIES == {
        "LeadScrew Manufacturing Notes": spec.DRAWING_NOTES,
        "FeedNut Manufacturing Notes": nut.DRAWING_NOTES,
    }
    for configuration, member in part.MEMBER_SPECS.items():
        assert part.MEMBER_PROPERTIES[configuration]["Manufacturing Notes"] == (
            member.DRAWING_NOTES
        )
    assert spec.DRAWING_NOTES.endswith(f"SHEET {spec.MODIFIED_STOCK_SHEET}.")
    assert nut.DRAWING_NOTES.endswith(f"SHEET {nut.REWORK_SHEET}.")


def test_save_takes_one_library_material_per_member() -> None:
    assert variants._member_materials(part.CONFIGURATIONS, part.MATERIALS) == (
        part.MATERIALS
    )
    assert variants._member_materials(("A", "B"), "Brass") == {"A": "Brass", "B": "Brass"}
    with pytest.raises(ValueError, match="differ from members"):
        variants._member_materials(part.CONFIGURATIONS, {"LeadScrew": "AISI 304"})
    with pytest.raises(ValueError, match="differ from members"):
        variants._member_materials(("LeadScrew",), part.MATERIALS)
    calls = []
    adapter = object()
    original = variants.require_material_in_every_configuration
    try:
        variants.require_material_in_every_configuration = (
            lambda _adapter, name, material, members: calls.append(
                (name, material, tuple(members))
            )
        )
        variants._require_member_materials(
            adapter, STEM, {"LeadScrew": "AISI 304", "FeedNut": "Brass", "X": "Brass"}
        )
    finally:
        variants.require_material_in_every_configuration = original
    assert calls == [
        (STEM, "AISI 304", ("LeadScrew",)),
        (STEM, "Brass", ("FeedNut", "X")),
    ]
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    [save] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "save_member_part"
    ]
    keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in save.keywords}
    assert keywords["material"] == "MATERIALS"


def test_c4_values_are_imported_not_retyped() -> None:
    assert spec.MAJOR_DIA == feed.SCREW_MAJOR_DIA
    assert spec.LEAD == feed.SCREW_LEAD
    assert spec.STOCK_LENGTH == feed.SCREW_STOCK_LENGTH
    assert spec.LENGTH == feed.SCREW_LENGTH
    assert spec.LENGTH == pytest.approx(feed.SCREW_FAR_END_S - feed.SCREW_NEAR_END_S)
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name in ("MAJOR_DIA", "LEAD", "STOCK_LENGTH", "LENGTH"):
        assert re.search(rf"^{name} = feed\.", source, re.MULTILINE), name


def test_profile_is_an_edge_broken_major_diameter_cylinder() -> None:
    assert spec.PROFILE[0] == (0.0, 0.0) and spec.PROFILE[-1] == (0.0, spec.LENGTH)
    r = spec.MAJOR_DIA / 2.0
    assert max(radius for radius, _ in spec.PROFILE) == r
    # Each end broken 45° at the title block's chamfer limit, so no callout.
    edge_break = _config.title_block("edge_break")
    assert spec.END_CHAMFER == float(edge_break["chamfer_max_mm"]) == 0.25
    assert spec.PROFILE[1] == (r - spec.END_CHAMFER, 0.0)
    assert spec.PROFILE[2] == (r, spec.END_CHAMFER)
    assert spec.PROFILE[-2] == (r - spec.END_CHAMFER, spec.LENGTH)
    assert spec.LENGTH + spec.LENGTH_TOLERANCE <= spec.STOCK_LENGTH


def test_volume_is_the_blank_less_five_flat_segments() -> None:
    r, c = spec.MAJOR_DIA / 2.0, spec.END_CHAMFER
    ring = 2.0 * math.pi * (r - c / 3.0) * c * c / 2.0  # Pappus on the 45° triangle
    assert spec.BLANK_VOLUME_MM3 == pytest.approx(
        math.pi * r * r * spec.LENGTH - 2.0 * ring, rel=1e-12
    )
    # A circular segment by its subtended angle: R^2 (theta - sin theta) / 2.
    offset = r - spec.FLAT_DEPTH

    def segment(radius: float) -> float:
        theta = 2.0 * math.acos(offset / radius)
        return radius * radius * (theta - math.sin(theta)) / 2.0

    theta = 2.0 * math.acos(offset / r)
    assert spec.FLAT_SEGMENT_AREA == pytest.approx(segment(r), rel=1e-12)
    assert spec.FLAT_VOLUME_MM3 == pytest.approx(segment(r) * 8.0, rel=1e-12)
    assert spec.FLAT_CHORD == pytest.approx(2.0 * r * math.sin(theta / 2.0))
    # The open flat starts half a flat length before the actual handwheel
    # grub, measured from the screw's relocated near end. Integrate through
    # the shrinking end break independently of the spec's Simpson rule.
    steps = 20000
    h = c / steps
    radii = [r - (k + 0.5) * h for k in range(steps)]
    handwheel_start = (
        feed.HUB_END_S + feed.HANDWHEEL_GRUB_FROM_HUB
        - feed.SCREW_NEAR_END_S - spec.FLAT_LENGTH / 2.0
    )
    full = spec.LENGTH - c - handwheel_start
    open_volume = segment(r) * full + h * sum(segment(radius) for radius in radii)
    open_area = spec.FLAT_CHORD * full + h * sum(
        2.0 * math.sqrt(radius**2 - offset**2) for radius in radii
    )
    assert spec.OPEN_FLAT_VOLUME_MM3 == pytest.approx(open_volume, rel=1e-6)
    assert spec.OPEN_FLAT_AREA_MM2 == pytest.approx(open_area, rel=1e-6)
    assert spec.FLAT_VOLUMES_MM3 == pytest.approx(
        {"NearKP08": spec.FLAT_VOLUME_MM3, "FarKP08": spec.FLAT_VOLUME_MM3,
         "Handwheel": open_volume}, rel=1e-6
    )
    assert spec.VOLUME_MM3 == pytest.approx(
        spec.BLANK_VOLUME_MM3 - 4 * spec.FLAT_VOLUME_MM3 - open_volume, rel=1e-9
    )
    # The groove allowance the plain cylinder overstates (Ooznest STEP: 10.9/mm).
    assert spec.THREAD_GROOVE_MM3_PER_MM == pytest.approx(10.9, rel=0.02)


def test_build_sketches_the_spec_profile() -> None:
    points = part.screw_profile_points()
    # The same outline, walked up the axis from the origin vertex first.
    assert sorted(points) == sorted(spec.PROFILE)
    assert points[:2] == [(0.0, 0.0), (0.0, spec.LENGTH)]
    assert spec.revolved_volume(tuple(points)) == pytest.approx(spec.BLANK_VOLUME_MM3)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'volume_check(adapter, "leadscrew", VOLUME_MM3' in source
    assert "publish_screw_axis(adapter)" in source
    assert 'name_last_feature(adapter, "ScrewProfile")' in source
    assert 'name_last_feature(adapter, "Screw")' in source
    assert 'name_last_feature(adapter, "FlatProfile")' in source
    assert 'name_last_feature(adapter, "Flats")' in source
    # Every cut is proved by its own faces as well as its volume step.
    assert re.search(r'_flat_faces_readback\(\s*adapter,\s*"Flats",', source)
    assert 'f"{name}ClockFlat"' in source


def test_flat_stations_are_c4s_set_screw_positions() -> None:
    """One flat under each set screw, stationed from the near end on C4's
    layout: each KP08's axial centre and the handwheel's set screw."""
    near = feed.SCREW_NEAR_END_S
    assert spec.FLAT_STATIONS == {
        "NearKP08": feed.KP08_S[0] - near,
        "FarKP08": feed.KP08_S[1] - near,
        "Handwheel": feed.HUB_END_S + feed.HANDWHEEL_GRUB_FROM_HUB - near,
    }
    assert spec.FLAT_STATIONS["NearKP08"] == pytest.approx(feed.KP08_WIDTH / 2.0 + feed.NEAR_STUB)
    assert spec.FLAT_STATIONS["FarKP08"] - spec.FLAT_STATIONS["NearKP08"] == pytest.approx(
        feed.KP08_S[1] - feed.KP08_S[0]
    )
    assert spec.FLAT_STATIONS["Handwheel"] - spec.FLAT_STATIONS["FarKP08"] == pytest.approx(
        feed.KP08_WIDTH / 2.0 + feed.HUB_GAP + feed.HANDWHEEL_GRUB_FROM_HUB
    )
    # Each KP08 locks with two set screws 120° apart; the handwheel with one of
    # its two (the other bears on the plain thread past the nut's travel).
    assert spec.CLOCKED_FLATS == ("NearKP08", "FarKP08")
    assert spec.KP08_SET_SCREW_SPACING_DEG == 120.0
    assert spec.FLAT_COUNT == 5
    assert spec.HANDWHEEL_SET_SCREW_MAJOR == 5.0
    # Review bought-r15 (rule 10): the print stations each flat's near edge.
    assert spec.FLAT_STARTS == pytest.approx({
        name: station - spec.FLAT_LENGTH / 2.0
        for name, station in spec.FLAT_STATIONS.items()
    })
    for name, start in spec.FLAT_STARTS.items():
        lo, hi = (s - near for s in spec.FLAT_HOUSINGS[name])
        assert lo <= start - spec.FLAT_TOLERANCE
        if name == spec.OPEN_FLAT:
            continue
        end_max = start + spec.FLAT_LENGTH + spec.FLAT_TOLERANCE
        assert end_max + spec.FLAT_LENGTH_TOLERANCE <= hi
    # The handwheel's set screw may stand off its station by the cover and
    # still sit wholly on the open flat: the flat's start at its band on the
    # hub side, the shortest cut's break on the other. The screw's far end
    # stays inside the handwheel's guaranteed bore at a long cut.
    station = spec.FLAT_STATIONS["Handwheel"]
    cover = min(
        spec.FLAT_LENGTH / 2.0 - spec.HANDWHEEL_SET_SCREW_MAJOR / 2.0 - spec.FLAT_TOLERANCE,
        spec.LENGTH - spec.LENGTH_TOLERANCE - spec.END_CHAMFER
        - (station + spec.HANDWHEEL_SET_SCREW_MAJOR / 2.0),
    )
    assert spec.HANDWHEEL_GRUB_COVER == pytest.approx(cover) == pytest.approx(0.7)
    assert (
        feed.SCREW_FAR_END_S + spec.LENGTH_TOLERANCE
        < feed.HUB_END_S + feed.HANDWHEEL_BORE_LENGTH
    )


def test_handwheel_flat_runs_out_through_the_cut_end_at_title_block_bands() -> None:
    """Owner ruling 2026-11-05 (Codjiflo 4483623004, rule 4): the handwheel
    flat runs from its station out through the cut end, so no land on it
    depends on the cut, and the cut, the stations and the flat length print at
    the title block's .X. A closed 8 flat there kept a land only at .XX."""
    assert spec.OPEN_FLAT == "Handwheel"
    bands = (spec.FLAT_TOLERANCE, spec.FLAT_LENGTH_TOLERANCE, spec.LENGTH_TOLERANCE)
    assert bands == (printed_band_mm(1),) * 3
    assert (spec.LENGTH_PLACES, spec.FLAT_PLACES, spec.FLAT_LENGTH_PLACES) == (1, 1, 1)
    # Its profile runs past even the longest cut, so the cut leaves no far wall.
    assert spec.FLAT_ENDS["Handwheel"] == spec.LENGTH + spec.FLAT_RUNOUT
    assert spec.FLAT_RUNOUT > spec.LENGTH_TOLERANCE
    assert spec.CLOSED_FLATS == ("NearKP08", "FarKP08")
    # Negative control: closing an 8 mm flat at the CURRENT handwheel
    # station would break through the shortest cut's far chamfer at .X bands.
    closed_far_edge = (
        spec.FLAT_STATIONS["Handwheel"] + spec.FLAT_LENGTH / 2.0
        + spec.FLAT_TOLERANCE + spec.FLAT_LENGTH_TOLERANCE
    )
    assert closed_far_edge > spec.LENGTH - spec.LENGTH_TOLERANCE - spec.END_CHAMFER
    # Every closed flat stays off both end breaks at its bands, the far one at
    # the shortest cut; the open one off the near end.
    for name, flat_start in spec.FLAT_STARTS.items():
        assert flat_start - spec.FLAT_TOLERANCE > spec.END_CHAMFER, name
        if name == spec.OPEN_FLAT:
            continue
        far_edge = flat_start + spec.FLAT_LENGTH + spec.FLAT_TOLERANCE
        assert (
            far_edge + spec.FLAT_LENGTH_TOLERANCE
            < spec.LENGTH - spec.LENGTH_TOLERANCE - spec.END_CHAMFER
        ), name
    # Retained hub gap; the chosen one-place cut changes engagement by its
    # rounding residual, not by the near support's entire relocation.
    assert feed.HUB_GAP == 11.0
    engagement = spec.LENGTH - (feed.KP08_S[1] - feed.KP08_S[0]) - feed.KP08_WIDTH - feed.NEAR_STUB - feed.HUB_GAP
    assert feed.HANDWHEEL_ENGAGEMENT == pytest.approx(engagement)
    assert engagement - spec.LENGTH_TOLERANCE >= feed.HANDWHEEL_ENGAGEMENT_MIN
    assert engagement + spec.LENGTH_TOLERANCE < feed.HANDWHEEL_BORE_LENGTH


def test_flats_hold_the_set_screws_at_the_band_limits() -> None:
    r = spec.MAJOR_DIA / 2.0
    assert (spec.FLAT_DEPTH, spec.FLAT_LENGTH) == (0.72, 8.0)
    assert spec.FLAT_AF == pytest.approx(7.28)
    assert spec.FLAT_AF_TOLERANCE == printed_band_mm(2) == pytest.approx(0.51)
    assert spec.FLAT_TOLERANCE == printed_band_mm(1) == pytest.approx(0.8)
    assert spec.FLAT_LENGTH_TOLERANCE == printed_band_mm(1) == pytest.approx(0.8)
    assert spec.CLOCK_TOLERANCE_DEG == 1.0
    # ISO 2904: the Tr8x2 external root d3 = d - 2 (P/2 + ac), ac = 0.25.
    assert spec.SCREW_ROOT_DIA == spec.MAJOR_DIA - 2.0 * (spec.PITCH / 2.0 + 0.25)
    assert spec.MINOR_DIA == 6.0  # the modelled nut bore, not the flats' limit

    def holds(af: float) -> bool:
        depth = spec.MAJOR_DIA - af
        deepest = depth + spec.FLAT_AF_TOLERANCE
        shallowest = depth - spec.FLAT_AF_TOLERANCE
        return (
            spec.flat_offset(deepest) > spec.SCREW_ROOT_DIA / 2.0
            and spec.flat_chord(shallowest) >= spec.SET_SCREW_POINT_DIA
        )

    # The ±0.51 band fits only AF 7.26..7.289; 7.28 is inside it.
    assert holds(spec.FLAT_AF) and holds(7.261) and holds(7.289)
    assert not holds(7.25) and not holds(7.29)
    deepest = spec.FLAT_DEPTH + spec.FLAT_AF_TOLERANCE
    shallowest = spec.FLAT_DEPTH - spec.FLAT_AF_TOLERANCE
    # In the crests, clear of the Ø5.5 root.
    assert r - deepest == pytest.approx(2.77)
    # Wider than an M5 cup point, and past the screw both sides off station.
    assert spec.flat_chord(shallowest) == pytest.approx(2.558, abs=1e-3)
    # The handwheel's M5 sits wholly on the open flat off station by the
    # cover; a closed 8 flat at .X would leave its far side on the thread.
    assert spec.HANDWHEEL_GRUB_COVER >= 0.0
    assert spec.FLAT_LENGTH / 2.0 - 2.0 * printed_band_mm(1) < 2.5
    # A KP08's two flats never meet.
    assert 2.0 * spec.flat_half_angle_deg(deepest) < 120.0 - 1.0


def test_flats_sketch_records_every_dimension_it_emits(monkeypatch) -> None:
    """One Front sketch, a rectangle and across-flat line per station: the
    printed FlatAF on the handwheel's, the printed FlatLength on the far
    KP08's, each station from the origin, every emitted dimension named in
    creation order."""
    emitted, chains, applied = [], [], {}
    ok = SimpleNamespace(is_success=True, data="D", error=None)

    class Adapter:
        async def create_sketch(self, plane):
            assert plane == "Front"
            return ok

        async def add_sketch_constraint(self, *_args):
            return ok

        async def add_sketch_dimension(self, ref1, ref2, kind, value):
            emitted.append((ref1, ref2, kind, value))
            return ok

        async def exit_sketch(self):
            return ok

        async def create_cut_extrude(self, params):
            assert params.both_directions and params.depth == spec.MAJOR_DIA + 2.0
            return ok

    async def chain(_adapter, points, close=True):
        chains.append(list(points))
        return [f"L{len(chains)}_{i}" for i in range(len(points) if close else 1)]

    async def defined(*_args, **_kwargs):
        return None

    def apply(self, _adapter, feature):
        applied[feature] = [name for name, _ in self._rows]
        return []

    monkeypatch.setattr(part, "add_line_chain", chain)
    monkeypatch.setattr(part, "_as_construction", lambda *_args: None)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(part.SketchDims, "apply", apply)
    asyncio.run(part._flats(Adapter()))
    names = applied["FlatProfile"]
    assert len(names) == len(emitted) == 15 == len(set(names))
    by_name = dict(zip(names, emitted, strict=True))
    assert spec.DRAWING_DIMENSIONS["FlatProfile"] <= set(names)
    assert by_name["FlatLength"][2:] == ("vertical_distance", 8.0)
    assert by_name["FlatAF"][2:] == ("horizontal_distance", pytest.approx(7.28))
    assert by_name["HandwheelFlatLength"][2:] == (
        "vertical_distance",
        pytest.approx(spec.LENGTH + spec.FLAT_RUNOUT - spec.FLAT_STARTS["Handwheel"]),
    )
    for name, start in spec.FLAT_STARTS.items():
        station = by_name[f"{name}FlatStation"]
        assert station[1:] == ("origin", "vertical_distance", start)
        # From the flat's near end: the rectangle's first vertex.
        assert station[0].endswith("_0.start")

    def chain_of(start: float) -> str:
        (found,) = [points for points in chains if points[0][1] == start]
        return f"L{chains.index(found) + 1}_"

    # The across-flat prints on the handwheel's rectangle, the length on the
    # far KP08's; the handwheel's runs 1 past the cut end, its length unprinted.
    assert by_name["FlatLength"][0].startswith(chain_of(spec.FLAT_STARTS["FarKP08"]))
    assert by_name["HandwheelFlatLength"][0].startswith(chain_of(spec.FLAT_STARTS["Handwheel"]))
    offset = spec.MAJOR_DIA / 2.0 - spec.FLAT_DEPTH
    reach = spec.MAJOR_DIA / 2.0 + 1.0
    for name in ("Handwheel", "FarKP08"):
        start = spec.FLAT_STARTS[name]
        end = spec.LENGTH + spec.FLAT_RUNOUT if name == "Handwheel" else start + spec.FLAT_LENGTH
        assert [(offset, start), (offset, end), (reach, end), (reach, start)] in chains
    # This is the actual rectangle sent to the native cut, not only a spec
    # flag: it must remove material through the longest permissible blank.
    handwheel_chain = next(points for points in chains if points[0] == (offset, spec.FLAT_STARTS["Handwheel"]))
    assert handwheel_chain[1][1] > spec.LENGTH + spec.LENGTH_TOLERANCE


def test_clock_flat_sketch_is_defined_by_its_angle(monkeypatch) -> None:
    """The clock flat's sketch: its station plane, the 120° flat at 3.28 from
    the axis, its across-flat and angle the printed pair, the angle last."""
    emitted, chains, applied, planes, angles = [], [], {}, [], []
    ok = SimpleNamespace(is_success=True, data="D", error=None)

    class Adapter:
        async def create_plane(self, params):
            planes.append((params.mode, params.base_plane, params.offset))
            return ok

        async def create_sketch(self, _plane):
            return ok

        async def add_sketch_constraint(self, *_args):
            return ok

        async def add_sketch_dimension(self, ref1, ref2, kind, value):
            emitted.append((ref1, ref2, kind, value))
            return ok

        async def exit_sketch(self):
            return ok

        async def create_cut_extrude(self, params):
            assert params.both_directions and params.depth == spec.FLAT_LENGTH
            return ok

    async def chain(_adapter, points, close=True):
        chains.append(list(points))
        count = len(points) if close else len(points) - 1
        return [f"L{len(chains)}_{i}" for i in range(count)]

    async def defined(*_args, **_kwargs):
        return None

    def apply(self, _adapter, feature):
        applied[feature] = [name for name, _ in self._rows]
        return []

    monkeypatch.setattr(part, "add_line_chain", chain)
    monkeypatch.setattr(part, "_as_construction", lambda *_args: None)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(part, "_sketch_z_per_model_z", lambda _adapter: -1.0)
    monkeypatch.setattr(part, "_clock_angle", lambda *args: angles.append(args[1:]))
    monkeypatch.setattr(part.SketchDims, "apply", apply)
    plane = asyncio.run(part._clock_flat(Adapter(), "FarKP08"))
    assert plane == "FarKP08ClockPlane"
    assert planes == [("offset", "Top Plane", feed.KP08_S[1] - feed.SCREW_NEAR_END_S)]
    names = applied["FarKP08ClockProfile"]
    # The angle is authored natively, outside the adapter's dimension call.
    assert names[-1] == "FarKP08ClockAngle" and len(emitted) == len(names) - 1
    assert len(set(names)) == len(names)
    assert spec.DRAWING_DIMENSIONS["FarKP08ClockProfile"] <= set(names)
    by_name = dict(zip(names, emitted, strict=False))
    assert by_name["FarKP08ClockAF"][2:] == ("distance", pytest.approx(7.28))
    assert angles == [("FarKP08", "L1_0", "L1_1", -1.0)]
    # Clock 0 along +X, the flat's midpoint 3.28 out at 120° toward +Z, which
    # this frame's sketch y reads as -Z.
    (reach, zero), origin, mid = chains[0]
    assert (reach, zero, origin) == (5.0, 0.0, (0.0, 0.0))
    offset = spec.MAJOR_DIA / 2.0 - spec.FLAT_DEPTH
    assert mid == pytest.approx(
        (
            offset * math.cos(math.radians(120.0)),
            -offset * math.sin(math.radians(120.0)),
        )
    )
    assert chains[1][1] == mid


def test_flat_face_readback_refuses_a_wrong_cut(monkeypatch) -> None:
    """The flats are proved by their own planar faces: one flat per station
    square to the clock's radial 3.28 from the axis, two end walls each, or
    one for the open flat run out through the cut end."""
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)

    def face(normal, root, area_mm2=0.0):
        surface = SimpleNamespace(
            IsPlane=lambda: True,
            PlaneParams=(*normal, *(v / 1000.0 for v in root)),
        )
        return SimpleNamespace(
            GetSurface=lambda: surface, GetArea=lambda: area_mm2 / 1e6
        )

    def adapter(faces):
        feature = SimpleNamespace(
            GetErrorCode2=lambda: (0, False), GetFaces=lambda: faces
        )
        doc = SimpleNamespace(FeatureByName=lambda _name: feature)
        return SimpleNamespace(currentModel=doc)

    area = spec.FLAT_CHORD * spec.FLAT_LENGTH
    offset = spec.MAJOR_DIA / 2.0 - spec.FLAT_DEPTH
    c, s = math.cos(math.radians(120.0)), math.sin(math.radians(120.0))
    start, end = spec.FLAT_STARTS["FarKP08"], spec.FLAT_ENDS["FarKP08"]
    station = feed.KP08_S[1] - feed.SCREW_NEAR_END_S
    closed = ((start, end, area),)
    good = [
        face((c, 0.0, s), (offset * c, station, offset * s), area),
        face((0.0, 1.0, 0.0), (0.0, start, 0.0)),
        face((0.0, -1.0, 0.0), (0.0, end, 0.0)),
    ]
    part._flat_faces_readback(adapter(good), "FarKP08ClockFlat", 120.0, closed)
    deep = offset + 0.1
    shallow = [face((c, 0.0, s), (deep * c, station, deep * s), area), *good[1:]]
    off_station = [good[0], good[1], face((0.0, -1.0, 0.0), (0.0, end + 1.0, 0.0))]
    for faces in (shallow, off_station, good[:2]):
        with pytest.raises(RuntimeError):
            part._flat_faces_readback(adapter(faces), "FarKP08ClockFlat", 120.0, closed)
    with pytest.raises(RuntimeError):  # a clock-0 flat where the 120° one belongs
        part._flat_faces_readback(adapter(good), "FarKP08ClockFlat", 0.0, closed)
    # The open flat: its start wall only, its face run through the far break.
    start = spec.FLAT_STARTS["Handwheel"]
    open_ = ((start, None, spec.OPEN_FLAT_AREA_MM2),)
    run_out = [
        face((1.0, 0.0, 0.0), (offset, (start + spec.LENGTH) / 2.0, 0.0), spec.OPEN_FLAT_AREA_MM2),
        face((0.0, 1.0, 0.0), (0.0, start, 0.0)),
    ]
    part._flat_faces_readback(adapter(run_out), "Flats", 0.0, open_)
    closed_at_end = [*run_out, face((0.0, -1.0, 0.0), (0.0, start + spec.FLAT_LENGTH, 0.0))]
    short = [face((1.0, 0.0, 0.0), (offset, start + spec.FLAT_LENGTH / 2.0, 0.0), area), run_out[1]]
    for faces in (closed_at_end, short):
        with pytest.raises(RuntimeError):
            part._flat_faces_readback(adapter(faces), "Flats", 0.0, open_)


def test_cut_length_is_the_axis_edge_driving_dimension() -> None:
    """The emitted dimensions match the recorded names one for one, and the
    cut length is a driving dimension of its own: the axis edge, emitted first."""
    emitted = []
    ok = SimpleNamespace(is_success=True, data="D", error=None)

    class Adapter:
        async def add_sketch_constraint(self, *_args):
            return ok

        async def add_sketch_dimension(self, ref1, ref2, kind, value):
            emitted.append((ref1, ref2, kind, value))
            return ok

    lines = [f"L{i}" for i in range(len(spec.PROFILE))]
    dims = asyncio.run(part.define_screw_profile(Adapter(), lines))
    names = [name for name, _drive in dims._rows]
    assert names == list(part.SCREW_PROFILE_DIMENSIONS)
    assert len(emitted) == len(names)
    by_name = dict(zip(names, emitted, strict=True))
    assert by_name["CutLength"] == (
        "L0.start",
        "L0.end",
        "vertical_distance",
        spec.LENGTH,
    )
    assert by_name["ShankLength"][3] == spec.LENGTH - 2.0 * spec.END_CHAMFER
    for end in ("Far", "Near"):
        assert by_name[f"{end}ChamferRadial"][3] == spec.END_CHAMFER
        assert by_name[f"{end}ChamferAxial"][3] == spec.END_CHAMFER
    # The near end face closes on the origin vertex: dimensioning it as well
    # would over-define the sketch.
    assert not any(ref1.startswith("L5.") for ref1, *_ in emitted)
    assert "CutLength" in spec.DRAWING_DIMENSIONS["ScrewProfile"]


def test_controls_print_at_the_title_block_rows() -> None:
    assert spec.LENGTH_TOLERANCE == printed_band_mm(1) == pytest.approx(0.8)
    stations = {f"{name}FlatStation" for name in spec.FLAT_STATIONS}
    assert spec.DRAWING_DIMENSIONS == {
        "ScrewProfile": {"CutLength"},
        "FlatProfile": {"FlatLength", "FlatAF", *stations},
        "NearKP08ClockProfile": {"NearKP08ClockAF", "NearKP08ClockAngle"},
        "FarKP08ClockProfile": {"FarKP08ClockAF", "FarKP08ClockAngle"},
    }
    places = {
        "CutLength": 1,
        "FlatLength": 1,
        "FlatAF": 2,
        **dict.fromkeys(stations, 1),
        "NearKP08ClockAF": 2,
        "FarKP08ClockAF": 2,
        "NearKP08ClockAngle": 0,
        "FarKP08ClockAngle": 0,
    }
    assert spec.DIMENSION_PRECISION == places
    assert spec.DRAWING_PRECISION == {
        feature: {name: places[name] for name in names}
        for feature, names in spec.DRAWING_DIMENSIONS.items()
    }
    # swTolGeneral: no band of its own, the title block's row in force.
    assert spec.DIMENSION_TOLERANCE_TYPES == dict.fromkeys(places, 11)
    for name, (_nominal, band, digits) in spec.DIMENSION_CONTROLS.items():
        if name in spec.ANGULAR_DIMENSIONS:
            assert band == 1.0 and spec.control_si(name)[1] == math.radians(1.0)
        else:
            assert band == printed_band_mm(digits)
            assert spec.control_si(name)[1] == band / 1000.0
    # Every KP08 flat is one size; the printed one says how many and names
    # the pillow blocks by their short number. The handwheel's flat station
    # prints bare.
    assert spec.FLAT_LENGTH_CALLOUT == "4X"
    assert set(draw.FLAT_CALLOUTS) == {"FlatLength", "FlatAF"}
    assert draw.FLAT_CALLOUTS["FlatLength"].startswith(f"{spec.FLAT_LENGTH_CALLOUT} ")
    assert draw.FLAT_CALLOUTS["FlatAF"].splitlines()[0] == ", ".join(
        detail.label for detail in draw.END_DETAILS
    )
    # The across-flat links note 1, which gives one flat at each detail and
    # their free angle, set at a numbered TL-00 step (owner ruling via Main).
    assert draw.FLAT_CALLOUTS["FlatAF"].endswith("SEE NOTE 1")
    assert draw.FLAT_CLOCK_NOTE.startswith("1. ")
    assert "ANGLE FREE" in draw.FLAT_CLOCK_NOTE
    assert f"SET AT {draw.FLAT_CLOCK_STEP}." in draw.FLAT_CLOCK_NOTE
    assert draw.FLAT_CLOCK_NOTE in draw.NOTES
    assert draw.FLAT_CLOCK_STEP.startswith("MHA-CH-06-TL-00 STEP ")
    # The cited step is the one that tightens the set screws on the flats.
    step = draw.FLAT_CLOCK_STEP.rsplit(" ", 1)[1]
    assert any(
        re.match(rf"{step}[A-Z]?\. ", text) and "SET SCREWS ON THE" in text
        and "FLATS" in text
        for text in jig.ASSEMBLY_STEPS
    )
    # The feed absorbs the band at either limit.
    short_margin = (feed.NEAR_STUB - feed.NEAR_STUB_MIN) + (
        feed.HANDWHEEL_ENGAGEMENT - feed.HANDWHEEL_ENGAGEMENT_MIN
    )
    assert short_margin >= spec.LENGTH_TOLERANCE
    assert (
        feed.SCREW_FAR_END_S + spec.LENGTH_TOLERANCE
        < feed.HUB_END_S + feed.HANDWHEEL_BORE_LENGTH
    )


def test_spec_is_pure_data() -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE)
    assert set(imports) <= {
        "__future__",
        "math",
        "_printed_tolerance",
        "ch_rocker_arm_tl_vn_oblique_leadscrew_spec",
    }


def test_package_is_the_registered_kit_drawing() -> None:
    sheet = DRAWINGS_BY_NAME[NAME]
    assert draw.SPEC is sheet
    assert (sheet.part, sheet.artifact_stem, sheet.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert sheet.layout is DrawingLayout.LANDSCAPE
    assert sheet.source_kind == "part"
    assert sheet.artifact_stem == part.PART_NAME
    assert draw.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    source = Path(draw.__file__).read_text(encoding="utf-8")
    assert drawing_specification_violations(source) == ()
    # One package: sheet 1 the members' references, then each member's sheet.
    tree = ast.parse(source)
    [call] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "build_purchased_variant_drawing"
    ]
    keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords}
    assert keywords["variants"] == "VARIANTS"
    assert keywords["append_sheets"] == "append_member_sheets"
    assert keywords["isometric_only"] == "ISOMETRIC_ONLY"
    assert keywords["title_fit"] == "True"
    assert draw.SHEET_NAMES == ("LEADSCREW", "FEED NUT REWORK")
    appended = source[source.index("def append_member_sheets") :]
    assert appended.index("_append_leadscrew_sheet(") < appended.index(
        "_append_feed_nut_rework_sheet("
    )
    # Sheet 1 shows the screw's isometric only; its sheet 2 draws its views.
    assert draw.ISOMETRIC_ONLY == {spec.CONFIGURATION: spec.MODIFIED_STOCK_SHEET}
    assert draw.SHEET_NAMES.index(draw.LEADSCREW_SHEET_NAME) + 2 == spec.MODIFIED_STOCK_SHEET


def test_one_axis_horizontal_view_at_the_largest_fitting_scale() -> None:
    usable = draw.BORDER[2] - draw.BORDER[0]
    assert usable == pytest.approx(0.4064)
    # 1:1 overruns the border; 1:2 is the next project scale down.
    assert spec.LENGTH / 1000 > usable
    assert draw.SHEET_SCALE == draw.ISO_SCALE == (1.0, 2.0)
    assert draw.SCREW_SHEET_LENGTH == pytest.approx(spec.LENGTH * draw.SHEET_SCALE[0] / draw.SHEET_SCALE[1] / 1000.0)
    # *Front looks at the profile sketch; -90 deg lays model +Y to sheet right.
    assert draw.MAIN_VIEW_ANGLE == -math.pi / 2.0
    half = draw.SCREW_SHEET_LENGTH / 2.0
    radius = draw.SCREW_SHEET_DIA / 2.0
    main = (
        draw.MAIN_CENTER[0] - half,
        draw.MAIN_CENTER[1] - radius,
        draw.MAIN_CENTER[0] + half,
        draw.MAIN_CENTER[1] + radius,
    )
    # The isometric stands the actual cut axis up, plus the end ellipses.
    iso_half_height = (
        (spec.LENGTH * math.sqrt(2.0 / 3.0) + spec.MAJOR_DIA)
        * draw._SHEET_PER_MODEL_MM
        / 2.0
    )
    iso = (
        draw.ISO_CENTER[0] - radius * 1.5,
        draw.ISO_CENTER[1] - iso_half_height,
        draw.ISO_CENTER[0] + radius * 1.5,
        draw.ISO_CENTER[1] + iso_half_height,
    )
    for box in (main, iso):
        assert draw._inside_sheet(box), box
    assert main[2] < iso[0]
    assert not draw._inside_sheet(draw.TITLE_BLOCK)
    # The cut length stands over the screw, inside its span; the far two
    # flats' stations under it, each in its own row. The near station, the
    # flats' length and across-flat are the details'.
    details = [set(detail.keep) for detail in draw.END_DETAILS]
    assert set(draw.MAIN_KEEP).union(*details) == (
        spec.DRAWING_DIMENSIONS["ScrewProfile"] | spec.DRAWING_DIMENSIONS["FlatProfile"]
    )
    assert sum(map(len, details)) + len(draw.MAIN_KEEP) == len(
        set(draw.MAIN_KEEP).union(*details)
    )
    text_x, text_y = draw.MAIN_KEEP["CutLength"]
    assert main[0] < text_x < main[2] and text_y > main[3]
    rows = [
        draw.MAIN_KEEP[f"{name}FlatStation"][1] for name in ("FarKP08", "Handwheel")
    ]
    assert len(set(rows)) == 2 and max(rows) < main[1] - 0.015
    end_to_grub = spec.LENGTH - spec.FLAT_STATIONS["Handwheel"]
    assert draw.sheet_x(spec.FLAT_STATIONS["Handwheel"]) == pytest.approx(
        main[2] - end_to_grub * draw._SHEET_PER_MODEL_MM
    )
    # The cut length's dimension line (its text about 2.7 mm over it) stands
    # over the sections' letters, 1.7 .. 7.9 mm past the cutting lines' reach.
    assert text_y - 0.0027 > draw.MAIN_CENTER[1] + draw.SECTION_REACH + 0.0079 + 0.004
    # Each section's face and texts within the border, over the main view: the
    # across-flat's text above the axis, the angle's below it (clock 0 points
    # to the sheet's bottom, the angle's bisector 60° off it).
    scale = draw.SECTION_SCALE[0] / draw.SECTION_SCALE[1] / 1000.0
    af_reach = draw.CLOCK_AF_TEXT_RADIUS_MM * scale + 0.006
    angle_reach = draw.CLOCK_ANGLE_TEXT_RADIUS_MM * scale + 0.006
    assert spec.MAJOR_DIA / 2.0 < draw.CLOCK_ANGLE_ARC_RADIUS_MM
    assert draw.CLOCK_ANGLE_ARC_RADIUS_MM < draw.CLOCK_ANGLE_TEXT_RADIUS_MM
    half_clock = math.radians(spec.KP08_SET_SCREW_SPACING_DEG / 2.0)
    drop = max(
        spec.MAJOR_DIA / 2.0 * scale,
        draw.CLOCK_ANGLE_TEXT_RADIUS_MM * scale * math.cos(half_clock)
        + draw.TEXT_HALF_HEIGHT,
        draw.CLOCK_ANGLE_ARC_RADIUS_MM * scale + draw.EXTENSION_OVERSHOOT,
    )
    for section in draw.CLOCK_SECTIONS:
        x, y = section.centre
        box = (x - angle_reach, y - angle_reach, x + angle_reach, y + af_reach)
        assert draw._inside_sheet(box), (section.label, box)
        # The two-row caption (about 13 mm) hangs between the section's
        # lowest ink and the cut length's text.
        caption_bottom = y - drop - draw.SECTION_CAPTION_GAP - 0.013
        assert caption_bottom > text_y + draw.TEXT_HALF_HEIGHT, section.label
        # The cutting line crosses its station's flat, 2.5 clear of both of
        # its ends and away from the far KP08 station's extension line
        # (machinist review: at 0.5 separation the two lines merged).
        start = spec.FLAT_STARTS[section.flat]
        assert start + 2.5 <= section.cut_mm <= start + spec.FLAT_LENGTH - 2.5
        assert section.cut_mm != spec.FLAT_STATIONS[section.flat]
    assert [s.flat for s in draw.CLOCK_SECTIONS] == list(spec.CLOCKED_FLATS)
    # The note block (three rows about 13 mm tall and 70 mm wide, top-left
    # anchored) stands under the main view's lowest text, right of the
    # details and over the title block, left of the isometric.
    notes = (
        draw.NOTES_XY[0],
        draw.NOTES_XY[1] - 0.013,
        draw.NOTES_XY[0] + 0.070,
        draw.NOTES_XY[1],
    )
    assert draw._inside_sheet(notes)
    assert notes[3] < min(rows) - draw.TEXT_HALF_HEIGHT - 0.005
    assert notes[2] < iso[0]
    detail_right = max(
        x for detail in draw.END_DETAILS for x, _y in detail.keep.values()
    )
    assert notes[0] > detail_right + 0.015


# --- FeedNut: the brass flange nut as fitted ---------------------------------------


def test_feed_nut_sourced_envelope_and_the_faced_length() -> None:
    # The listing's dimension image: spigot, flange and body make its 15
    # overall; the fitter faces the 1.5 spigot off, leaving 13.5.
    assert (nut.FLANGE_DIA, nut.FLANGE_THICK) == (22.0, 3.5)
    assert (nut.HOLE_DIA, nut.HOLE_PCD, len(nut.HOLE_ANGLES_DEG)) == (3.5, 16.0, 4)
    assert (nut.BODY_DIA, nut.BODY_LENGTH, nut.SPIGOT_LENGTH) == (10.2, 10.0, 1.5)
    assert nut.SPIGOT_LENGTH + nut.LENGTH == nut.SUPPLIED_LENGTH == 15.0
    assert nut.LENGTH == nut.FLANGE_THICK + nut.BODY_LENGTH == 13.5
    assert nut.LENGTH >= 5.0 * spec.LEAD
    # The thread is modelled as a plain bore at the Tr8x2 minor diameter.
    assert nut.BORE_DIA == spec.MINOR_DIA == 6.0
    assert nut.LEAD == spec.LEAD
    assert nut.SUPPLIER_PRODUCT_URL == f"https://www.amazon.com/dp/{nut.SKU}"


def test_feed_nut_receipt_limits_are_native_dimensions_on_sheet_3() -> None:
    """4475311251: F1A's receipt limits are the FeedNut's own native
    dimensions, each at its band's places in its native type, imported onto
    sheet 3's end view; the faced length's LIMIT joins the rework in F-F."""
    # UNVERIFIED nominals: F1A measures the nut against these before the lug's
    # taps are transferred, in the nut's own millimetres.
    assert nut.FLANGE_THICK_MIN < nut.FLANGE_THICK < nut.FLANGE_THICK_MAX
    assert nut.HOLE_DIA_MIN < nut.HOLE_DIA < nut.HOLE_DIA_MAX
    assert nut.BODY_DIA < nut.BODY_DIA_MAX
    assert nut.FLANGE_DIA_MIN < nut.FLANGE_DIA < nut.FLANGE_DIA_MAX
    assert (nut.FLANGE_DIA_MIN, nut.FLANGE_DIA_MAX) == (21.8, 22.2)
    assert nut.LENGTH_MIN < nut.LENGTH < nut.LENGTH_MAX < nut.SUPPLIED_LENGTH
    assert (nut.LENGTH_MIN, nut.LENGTH_MAX) == (13.2, 13.8)
    assert nut.HOLE_STATION_BAND == nut.HOLE_PCD_BAND / 2.0
    # (nominal, lower, upper, places): each band's limits are the spec's.
    limits = {
        name: (round(nominal + lower, 6), round(nominal + upper, 6), places)
        for name, (nominal, lower, upper, places) in nut.RECEIPT_CONTROLS.items()
    }
    assert limits == {
        "ReceiptFlangeDia": (nut.FLANGE_DIA_MIN, nut.FLANGE_DIA_MAX, 1),
        "ReceiptBodyDia": (nut.BODY_DIA_MIN, nut.BODY_DIA_MAX, 1),
        "ReceiptHoleDia": (nut.HOLE_DIA_MIN, nut.HOLE_DIA_MAX, 2),
        "ReceiptHolePcd": (
            nut.HOLE_PCD - nut.HOLE_PCD_BAND, nut.HOLE_PCD + nut.HOLE_PCD_BAND, 1,
        ),
    }
    nominal, lower, upper, places = nut.REWORK_CONTROLS["FacedLength"]
    assert (nominal, round(nominal + lower, 6), upper, places) == (
        nut.LENGTH_MAX, nut.LENGTH_MIN, 0.0, 1,
    )
    # swTolLIMIT 3, swTolSYMMETRIC 4: a LIMIT prints both limits.
    assert {
        name: nut.DIMENSION_TOLERANCE_TYPES[name]
        for name in (*nut.RECEIPT_CONTROLS, "FacedLength")
    } == {
        "ReceiptFlangeDia": 3,
        "ReceiptBodyDia": 3,
        "ReceiptHoleDia": 3,
        "ReceiptHolePcd": 4,
        "FacedLength": 3,
    }
    # 4476701302: the body's least bounds RV-02's thread wall; its nominal
    # is the listing's.
    assert nut.RECEIPT_CONTROLS["ReceiptBodyDia"][0] == nut.BODY_DIA
    assert nut.BODY_DIA_MIN == round(nut.BODY_DIA - nut.FLANGE_DIA_BAND, 6) == 10.0
    # Each receipt control is the driving diameter of its own construction
    # circle on the hidden Top-plane carrier, at the control's nominal; the
    # faced length is a Front-plane line LENGTH_MAX long from the seat face.
    assert {name: value for name, value, _centre in nut.RECEIPT_CIRCLES} == {
        name: control[0] for name, control in nut.RECEIPT_CONTROLS.items()
    }
    hole = {name: centre for name, _value, centre in nut.RECEIPT_CIRCLES}
    assert hole["ReceiptHoleDia"] == (0.0, -nut.HOLE_PCD / 2.0)  # +Z: sketch y is -z
    assert {centre for name, centre in hole.items() if name != "ReceiptHoleDia"} == {(0.0, 0.0)}
    assert nut.REFERENCE_SKETCHES == (nut.RECEIPT_SKETCH, nut.FACED_LENGTH_SKETCH)
    assert set(nut.REFERENCE_SKETCHES) <= set(part.MEMBER_FEATURES[nut.CONFIGURATION])
    # The #29 transfer spot enters the least hole; the largest hole at its
    # worst station still leaves brass between it and the largest body.
    assert feed_block.TRANSFER_SPOT_DIA < nut.HOLE_DIA_MIN
    assert nut.HOLE_PCD / 2.0 - nut.HOLE_STATION_BAND - nut.HOLE_DIA_MAX / 2.0 > (
        nut.BODY_DIA_MAX / 2.0
    )
    assert nut.REACH == nut.LENGTH_MAX
    assert feed_block.NUT_REACH_X == pytest.approx((
        feed_block.LUG_X0, feed_block.NUT_FACE_X + nut.LENGTH_MAX,
    ))
    assert feed_block.NUT_FACE_X == feed_block.LUG_X1


def test_feed_nut_rework_is_native_banded_controls_on_sheet_3() -> None:
    """Codjiflo P2 and 4475311242: the flange's thickness and the
    countersink's mouth are LIMITs, the mouth's at the two places its 4.76
    needs; the 82° held by the apex depth and printed in the callout; TL-00
    cites the sheet."""
    nominal, lower, upper, places = nut.REWORK_CONTROLS["FlangeThick"]
    assert nominal == nut.FLANGE_THICK
    assert (nominal + lower, nominal + upper) == pytest.approx(
        (nut.FLANGE_THICK_MIN, nut.FLANGE_THICK_MAX)
    )
    assert (nut.FLANGE_THICK_MIN, nut.FLANGE_THICK_MAX) == (3.3, 3.7)
    assert places == 1
    # The mouth's band runs to the 3/16 cutter F2 may open it with, rounded
    # down to the band's places so the printed maximum never exceeds it.
    assert nut.REWORK_CONTROLS["CskDia"] == (4.6, -0.1, 0.16, 2)
    assert (nut.CSK_DIA_MIN, nut.CSK_DIA_MAX) == (4.50, 4.76)
    assert nut.CSK_DIA_MIN < nut.CSK_DIA < nut.CSK_DIA_MAX <= nut.CSK_CUTTER_DIA_MAX
    assert nut.CSK_CUTTER_DIA_MAX - nut.CSK_DIA_MAX < 0.01
    # swTolLIMIT 3, swTolSYMMETRIC 4.
    assert nut.DIMENSION_TOLERANCE_TYPES == {
        "FlangeThick": 3,
        "CskDia": 3,
        "FacedLength": 3,
        "ReceiptFlangeDia": 3,
        "ReceiptBodyDia": 3,
        "ReceiptHoleDia": 3,
        "ReceiptHolePcd": 4,
    }
    assert nut.DRAWING_DIMENSIONS == {
        "NutProfile": {"FlangeThick"},
        "Countersink1Profile": {"CskDia"},
        "FacedLengthReference": {"FacedLength"},
        "ReceiptReference": {
            "ReceiptFlangeDia", "ReceiptBodyDia", "ReceiptHoleDia", "ReceiptHolePcd",
        },
    }
    assert nut.DRAWING_PRECISION == {
        "NutProfile": {"FlangeThick": 1},
        "Countersink1Profile": {"CskDia": 2},
        "FacedLengthReference": {"FacedLength": 1},
        "ReceiptReference": {
            "ReceiptFlangeDia": 1, "ReceiptBodyDia": 1, "ReceiptHoleDia": 2, "ReceiptHolePcd": 1,
        },
    }
    # A set prefix replaces a diameter's own Ø (run 20261105T023247678Z
    # printed "4X 3.60/3.46"), so the hole's count carries the token too; the
    # countersink's carries the Y14.5 countersink symbol as well.
    assert nut.DIMENSION_PREFIXES == {
        ("Countersink1Profile", "CskDia"): "4X <HOLE-SINK><MOD-DIAM>",
        ("ReceiptReference", "ReceiptHoleDia"): "4X <MOD-DIAM>",
    }
    # "4X ⌵ Ø4.76/4.50 X 82°": the count, the countersink symbol, then
    # SolidWorks' own diameter token, once; the angle is the sheet's suffix.
    # CskDia is the mouth's diameter (REWORK_CONTROLS' 4.6), printed in the
    # section as a linear size, which adds no Ø of its own (run 6 printed
    # "4X 4.6"); the callout lines below carry none either.
    assert nut.HOLE_PREFIX == f"{nut.SCREW_COUNT}X <MOD-DIAM>" == "4X <MOD-DIAM>"
    assert nut.CSK_PREFIX == f"{nut.SCREW_COUNT}X <HOLE-SINK><MOD-DIAM>"
    assert nut.REWORK_CONTROLS["CskDia"][0] == nut.CSK_DIA
    assert "Ø" not in draw.CSK_SCREW_CALLOUT and "MOD-DIAM" not in draw.CSK_SCREW_CALLOUT
    assert nut.CSK_ANGLE == 82.0
    assert nut.CSK_SUFFIX == " X 82°"
    assert "CSK" not in draw.CSK_SCREW_CALLOUT
    assert nut.CSK_APEX_DEPTH * math.tan(math.radians(41.0)) == pytest.approx(
        nut.CSK_DIA / 2.0
    )
    # The printed names are the flange's rim edge and countersink 1's.
    assert nut.NUT_PROFILE_DIMENSIONS[3] == "FlangeThick"
    assert nut.countersink_dimensions(1)[3:5] == ("CskDia", "CskApexDepth")
    names = [
        name
        for index in range(1, len(nut.COUNTERSINK_AXES) + 1)
        for name in nut.countersink_dimensions(index)
    ]
    assert len(names) == len(set(names)) == 6 * len(nut.COUNTERSINK_AXES)
    # Countersink 1 is the +X hole on Front, the plane section F-F cuts.
    assert nut.COUNTERSINK_AXES[0] == ("Front", nut.HOLE_PCD / 2.0)
    assert nut.REWORK_SHEET_REFERENCE == "MHA-CH-06-TL-VN-84 SHEET 3"
    assert nut.REWORK_SHEET_REFERENCE == f"{nut.NUMBER} SHEET {nut.REWORK_SHEET}"
    assert draw.SHEET_NAMES.index(draw.REWORK_SHEET_NAME) + 2 == nut.REWORK_SHEET
    assert draw.SHEET_NAMES.index(draw.LEADSCREW_SHEET_NAME) + 2 == (
        spec.MODIFIED_STOCK_SHEET
    )
    assert draw.REWORK_EXPECTED == {
        "FlangeThick": pytest.approx((0.0035, -0.0002, 0.0002)),
        "CskDia": pytest.approx((0.0046, -0.0001, 0.00016)),
        "FacedLength": pytest.approx((0.0138, -0.0006, 0.0)),
    }
    assert draw.REWORK_PRECISION == {"FlangeThick": 1, "CskDia": 2, "FacedLength": 1}
    assert set(draw.REWORK_CALLOUTS) == set(nut.REWORK_CONTROLS)
    assert draw.RECEIPT_EXPECTED == {
        "ReceiptFlangeDia": pytest.approx((0.022, -0.0002, 0.0002)),
        "ReceiptBodyDia": pytest.approx((0.0102, -0.0002, 0.0001)),
        "ReceiptHoleDia": pytest.approx((0.0035, -0.00004, 0.0001)),
        "ReceiptHolePcd": pytest.approx((0.016, -0.0001, 0.0001)),
    }
    assert draw.RECEIPT_PRECISION == {
        "ReceiptFlangeDia": 1, "ReceiptBodyDia": 1, "ReceiptHoleDia": 2, "ReceiptHolePcd": 1,
    }
    assert set(draw.RECEIPT_CALLOUTS) == set(draw.RECEIPT_TEXT_XY) == set(nut.RECEIPT_CONTROLS)


def test_rework_bands_name_their_mates_at_their_callouts() -> None:
    """Rule 4 (run 20261104T230444981Z, 4475311251): the flange's 3.3/3.7
    names the lug the faced seat bears on and the screws it grips; the
    countersink's band names the flat head that seats in it and its walls;
    the faced length names the KP08 it clears; each receipt limit names what
    it fits."""
    import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners

    lane, flange = draw.REWORK_CALLOUTS["FlangeThick"]
    # ABOVE: one line, since a line-broken above-callout reads back but never
    # prints (run 20261105T010614057Z printed the limits alone).
    assert lane == "above" and "\n" not in flange
    lane, countersink = draw.REWORK_CALLOUTS["CskDia"]
    assert lane == "below"
    # The lug is the feed block's, and the screws are the registry row that
    # buys the SKU whose head the spec sizes the countersink for.
    assert draw.FEED_BLOCK_NUMBER == feed_block.NUMBER
    assert flange.startswith(f"SEAT FACE ON {feed_block.NUMBER} LUG, ")
    screw_row = _config.parts("ch-rocker-arm-tl-vn-oblique-riser-screw")
    assert screw_row["supplier_skus"] == [nut.SCREW_SKU]
    assert draw.NUT_SCREW_NUMBER == screw_row["number"]
    assert flange.endswith(f", GRIP OF {nut.SCREW_COUNT}X {screw_row['number']}")
    # The fastener table's nut row is that flat head, through the flange
    # (the grip) into the feed block.
    row = fasteners.NUT_TO_FEED_BLOCK
    assert (row.thread, row.length, row.count) == (
        nut.SCREW_THREAD, nut.SCREW_LENGTH_TEXT, nut.SCREW_COUNT,
    )
    assert row.head == fasteners.FLAT_HEAD
    assert row.grip_mm == pytest.approx(nut.FLANGE_THICK + nut.HEAD_PROUD_NOMINAL)
    # The countersink's size line is the dimension's own (symbol prefix,
    # angle suffix); the callout is the screw by its same-parent short
    # number and SKU, then the spec's walls (RV-01).
    assert nut.SCREW_DIMS.head_angle_deg == nut.CSK_ANGLE
    screw_short = draw.short_number(screw_row["number"])
    assert screw_short == "TL-VN-67"
    rows = countersink.splitlines()
    assert rows == [f"FOR {screw_short} ({nut.SCREW_SKU})", nut.CSK_WALL_TEXT]
    # Nothing the spec does not establish: no seat depth, no flush; the only
    # numbers past the screw's are the spec's walls.
    assert "FLUSH" not in countersink and not re.search(r"\d\.\d", rows[0])
    # The faced face is named where it is: the seat face the lug bears on.
    assert draw.SPIGOT_NOTE.replace("\n", " ") == "SPIGOT FACED FLUSH WITH FLANGE SEAT FACE"
    assert nut.LENGTH == nut.FLANGE_THICK + nut.BODY_LENGTH  # no spigot left
    # The faced length's MAX is the near KP08's feed gap: it names that KP08.
    lane, faced = draw.REWORK_CALLOUTS["FacedLength"]
    kp08 = _config.parts("ch-rocker-arm-tl-vn-oblique-pillow-block")["number"]
    assert lane == "below" and draw.KP08_NUMBER == kp08
    assert faced.splitlines()[-1] == kp08
    # The receipt limits print once, natively; each size callout below them
    # names its mate, with no number of its own but the body's RV-02 wall
    # row, the spec's. The PCD, a location, carries its identifier only
    # (rule 7).
    assert draw.RECEIPT_CALLOUTS["ReceiptHolePcd"] == ("below", "PCD")
    mates = {}
    for name, (lane, text) in draw.RECEIPT_CALLOUTS.items():
        if name == "ReceiptHolePcd":
            continue
        rows = text.splitlines()
        if name == "ReceiptBodyDia":
            assert rows[-1] == nut.THREAD_WALL_TEXT
            rows = rows[:-1]
        assert lane == "below" and not re.search(r"\d\.\d", "\n".join(rows))
        mates[name] = rows[-1]
    assert mates == {
        "ReceiptFlangeDia": "LUG FACE",
        "ReceiptBodyDia": f"CLEARS HEADS OF {nut.SCREW_COUNT}X {screw_short}",
        "ReceiptHoleDia": f"{feed_block.NUMBER} LUG",
    }
    assert draw.RECEIPT_CALLOUTS["ReceiptFlangeDia"][1].startswith(f"WITHIN {feed_block.NUMBER}\n")
    assert draw.RECEIPT_CALLOUTS["ReceiptBodyDia"][1] == (
        "CLEARS HEADS OF 4X TL-VN-67\nMIN WALL 0.75 TO THREAD"
    )


def test_rework_tolerances_live_only_in_the_feed_nut_member() -> None:
    """The banded controls are authored on FeedNut-owned features, only
    while the FeedNut member is authored; the LeadScrew's controls stay
    under the title block's general rows."""
    fitted = set(part.MEMBER_FEATURES[nut.CONFIGURATION])
    lead = set(part.MEMBER_FEATURES[spec.CONFIGURATION])
    assert set(nut.DRAWING_DIMENSIONS) <= fitted
    assert not set(nut.DRAWING_DIMENSIONS) & lead
    # Each native control's tolerance is set in one loop over the spec's
    # NATIVE_CONTROLS, on the feature that owns it.
    assert model_toleranced_dimensions(part) == {("feature", "name"): "upper"}
    assert set(spec.DIMENSION_TOLERANCE_TYPES.values()) == {11}  # swTolGeneral
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    def calls(function: str) -> set[str]:
        return {
            getattr(node.func, "id", None) or getattr(node.func, "attr", "")
            for node in ast.walk(functions[function])
            if isinstance(node, ast.Call)
        }

    def callers(name: str) -> set[str]:
        return {function for function in functions if name in calls(function)}

    banded = {"set_dimension_symmetric_tolerance", "set_dimension_prefix", "_author_limits"}
    assert callers("set_dimension_symmetric_tolerance") == {"_feed_nut_rework"}
    # Every nut control is a LIMIT or a ±: no single-limit MAX is left.
    assert callers("set_single_limit") == set()
    assert callers("set_dimension_prefix") == {"_feed_nut_rework"}
    assert callers("_author_limits") == {"_feed_nut_rework"}
    assert callers("_feed_nut_rework") == {"_author_feed_nut"}
    assert not banded & calls("_author_lead_screw")
    rework = ast.unparse(functions["_feed_nut_rework"])
    assert "feed_nut.NATIVE_CONTROLS.items()" in rework
    assert "_control_feature(name)" in rework
    assert "feed_nut.DIMENSION_TOLERANCE_TYPES[name]" in rework
    # The reference sketches are drawn, then blanked, before the controls.
    author = ast.unparse(functions["_author_feed_nut"])
    order = [
        author.index(call)
        for call in (
            "_faced_length_reference(adapter)",
            "_receipt_reference(adapter)",
            "blank_reference_sketches(adapter, feed_nut.REFERENCE_SKETCHES)",
            "_feed_nut_rework(adapter)",
        )
    ]
    assert order == sorted(order)
    # build pairs each author with its own member, active and alone.
    source = ast.unparse(functions["build"])
    assert "(LEAD_SCREW_CONFIGURATION, _author_lead_screw)" in source
    assert "(FEED_NUT_CONFIGURATION, _author_feed_nut)" in source
    assert source.index("activate_member(adapter, configuration)") < source.index(
        "await author(adapter)"
    )


def test_feed_nut_countersinks_seat_the_flat_heads_proud_and_off_the_body() -> None:
    tan = math.tan(math.radians(nut.CSK_ANGLE / 2.0))
    assert nut.CSK_ANGLE == SCREW_DIMS.head_angle_deg == 82.0
    # The head's cone meets each mouth below its top Ø, so it stands proud at
    # every mouth in the band, for the largest and the least B18.6.3 head
    # (4475311242): the least head in the band's largest mouth governs.
    def proud(head: float, mouth: float) -> float:
        return (head - mouth) / (2.0 * tan)

    assert nut.HEAD_PROUD_MAX == pytest.approx(proud(nut.SCREW_HEAD_DIA_MAX, nut.CSK_DIA_MIN))
    assert nut.HEAD_PROUD_NOMINAL == pytest.approx(proud(SCREW_DIMS.head_dia, nut.CSK_DIA))
    assert nut.HEAD_PROUD_AT_MOUTH_MAX == pytest.approx(
        proud(nut.SCREW_HEAD_DIA_MAX, nut.CSK_DIA_MAX)
    )
    assert nut.HEAD_PROUD_MIN == pytest.approx(proud(nut.SCREW_HEAD_DIA_MIN, nut.CSK_DIA_MAX))
    least = min(
        proud(head, mouth)
        for head in (nut.SCREW_HEAD_DIA_MIN, nut.SCREW_HEAD_DIA_MAX)
        for mouth in (nut.CSK_DIA_MIN, nut.CSK_DIA_MAX)
    )
    assert nut.HEAD_PROUD_MIN == pytest.approx(least) and least > 0.0
    assert nut.HEAD_PROUD_MIN == pytest.approx(0.053, abs=5e-4)
    assert nut.HEAD_PROUD_MAX == pytest.approx(0.509, abs=5e-4)
    # F2 opens the countersinks only within the band, whose maximum is the
    # 3/16 cutter's diameter rounded down to the band's places.
    assert nut.CSK_DIA_MAX <= nut.CSK_CUTTER_DIA_MAX == pytest.approx(3.0 / 16.0 * 25.4)
    # F2's head limit is the catalogue head the body check uses; B18.6.3's
    # least head (.191) is the proud check's.
    assert nut.SCREW_HEAD_DIA_MAX == SCREW_DIMS.head_dia == pytest.approx(0.212 * 25.4)
    assert nut.SCREW_HEAD_DIA_MIN == pytest.approx(0.191 * 25.4)
    # The countersink never runs through the thinnest flange.
    assert nut.CSK_DEPTH == pytest.approx((nut.CSK_DIA - nut.HOLE_DIA) / (2.0 * tan))
    assert nut.CSK_DEPTH < nut.FLANGE_THICK_MIN

    # The Ø3/16 cutter's cone stays off the largest body at the worst hole
    # station; a Ø1/4 cutter would gouge it.
    def cutter_to_body(cutter: float) -> float:
        return (
            nut.HOLE_PCD / 2.0 - nut.HOLE_STATION_BAND - nut.CSK_ECCENTRICITY_MAX
            - cutter / 2.0 - nut.BODY_DIA_MAX / 2.0
        )

    assert nut.CSK_CUTTER_TO_BODY == pytest.approx(cutter_to_body(nut.CSK_CUTTER_DIA_MAX))
    assert nut.CSK_CUTTER_TO_BODY > 0.0
    assert cutter_to_body(0.25 * 25.4) < 0.0
    # The heads bear on each cone between the underhead fillet and the least
    # mouth.
    assert nut.CSK_BEARING_INNER_DIA == max(nut.HOLE_DIA_MAX, nut.SCREW_FILLET_DIA_MAX)
    assert nut.CSK_BEARING_AREA_MIN == pytest.approx(
        math.pi / 4.0 * (nut.CSK_DIA_MIN**2 - nut.CSK_BEARING_INNER_DIA**2)
    )
    assert nut.CSK_BEARING_AREA_MIN > 0.0


def test_feed_nut_flat_heads_engage_the_lug_at_rule_18_and_stop_inside_it() -> None:
    assert nut.SCREW_COUNT == len(nut.HOLE_ANGLES_DEG) == 4
    assert nut.SCREW_LENGTH == SCREW_DIMS.length == pytest.approx(0.625 * 25.4)
    assert nut.SCREW_GRIP == pytest.approx(nut.FLANGE_THICK + nut.HEAD_PROUD_NOMINAL)
    assert nut.SCREW_ENGAGEMENT == pytest.approx(nut.SCREW_LENGTH - nut.SCREW_GRIP)
    full = (
        nut.SCREW_LENGTH - 0.03 * 25.4
        - (nut.FLANGE_THICK_MAX + nut.HEAD_PROUD_MAX)
        - feed.TAP_MOUTH_BREAK
        - 2.0 * SCREW_DIMS.pitch
    )
    assert nut.SCREW_FULL_THREAD_MIN == pytest.approx(full)
    assert full >= feed.ENGAGEMENT_TARGET_D * nut.SCREW_MAJOR
    reach = nut.SCREW_LENGTH - nut.FLANGE_THICK_MIN - nut.HEAD_PROUD_MIN
    assert nut.SCREW_TIP_REACH_MAX == pytest.approx(reach)
    assert reach < feed_block.LUG_WIDTH
    # The heads stand short of the body's end, inside the nut's own reach.
    assert nut.FLANGE_THICK_MAX + nut.HEAD_PROUD_MAX < nut.LENGTH


def test_feed_nut_profile_holes_and_countersinks_follow_the_envelope() -> None:
    r_bore, r_body, r_flange = nut.BORE_DIA / 2.0, nut.BODY_DIA / 2.0, nut.FLANGE_DIA / 2.0
    assert part.nut_profile_points() == [
        (r_bore, 0.0), (r_flange, 0.0), (r_flange, nut.FLANGE_THICK),
        (r_body, nut.FLANGE_THICK), (r_body, nut.LENGTH), (r_bore, nut.LENGTH),
    ]
    for (x, z), angle in zip(nut.HOLE_CENTRES, nut.HOLE_ANGLES_DEG, strict=True):
        assert math.hypot(x, z) == pytest.approx(nut.HOLE_PCD / 2.0)
        assert math.degrees(math.atan2(z, x)) % 360.0 == pytest.approx(angle)
    assert part.hole_sketch_points() == [(x, -z) for x, z in nut.HOLE_CENTRES]
    # One countersink per hole: Front's u is model x, Right's is -z.
    axes = sorted(
        (u, 0.0) if plane == "Front" else (0.0, -u) for plane, u in nut.COUNTERSINK_AXES
    )
    assert axes == pytest.approx(sorted(nut.HOLE_CENTRES))
    tan = math.tan(math.radians(nut.CSK_ANGLE / 2.0))
    for _plane, u in nut.COUNTERSINK_AXES:
        apex, mouth, outer, top = nut.countersink_points(u)
        assert apex == (u, nut.CSK_APEX_Y) and top == (u, nut.CSK_TOP_Y)
        # The mouth lies on the head face at the countersink's diameter, on
        # the 82° cone from the apex; the wall rises square from it.
        assert mouth[1] == nut.FLANGE_THICK
        assert abs(mouth[0] - u) == pytest.approx(nut.CSK_DIA / 2.0)
        assert (nut.FLANGE_THICK - nut.CSK_APEX_Y) * tan == pytest.approx(
            nut.CSK_DIA / 2.0
        )
        assert outer == (mouth[0], nut.CSK_TOP_Y)
        # The mouth's side faces away from the nut's axis; the wall clears
        # the modelled body.
        assert abs(mouth[0]) > abs(u)
        assert abs(u) - nut.CSK_DIA / 2.0 > r_body


def test_feed_nut_volume_is_the_revolved_profile_less_holes_and_countersinks() -> None:
    tan = math.tan(math.radians(nut.CSK_ANGLE / 2.0))
    flange = math.pi / 4.0 * (nut.FLANGE_DIA**2 - nut.BORE_DIA**2) * nut.FLANGE_THICK
    body = math.pi / 4.0 * (nut.BODY_DIA**2 - nut.BORE_DIA**2) * nut.BODY_LENGTH
    assert nut.BODY_VOLUME_MM3 == pytest.approx(flange + body)
    hole = math.pi / 4.0 * nut.HOLE_DIA**2 * nut.FLANGE_THICK
    r_m, r_h = nut.CSK_DIA / 2.0, nut.HOLE_DIA / 2.0
    depth = (r_m - r_h) / tan
    frustum = math.pi * depth / 3.0 * (r_m**2 + r_m * r_h + r_h**2)
    countersink = frustum - math.pi * r_h**2 * depth
    assert nut.CSK_VOLUME_MM3 == pytest.approx(countersink)
    assert nut.VOLUME_MM3 == pytest.approx(flange + body - 4 * (hole + countersink))
    assert nut.VOLUME_MM3 == pytest.approx(1622.7, abs=0.1)


def test_feed_nut_supplier_references_are_the_dimension_image() -> None:
    values = {name: value for name, value, _orientation in nut.SUPPLIER_REFERENCE_DIMENSIONS}
    assert values == {
        "SupplierBodyLength": nut.BODY_LENGTH,
        "SupplierFlangeThickness": nut.FLANGE_THICK,
        "SupplierFlangeDiameter": nut.FLANGE_DIA,
        "SupplierBodyDiameter": nut.BODY_DIA,
        "SupplierMountingHoleDiameter": nut.HOLE_DIA,
        "SupplierHolePitchDiameter": nut.HOLE_PCD,
    }
    assert set(nut.SUPPLIER_REFERENCE_UNITS.values()) == {"mm"}
    assert set(nut.SUPPLIER_REFERENCE_STARTS) == set(values) == set(
        nut.SUPPLIER_REFERENCE_FORMATS
    )
    assert nut.SUPPLIER_REFERENCE_FORMATS["SupplierMountingHoleDiameter"][3] == "4X"
    assert nut.SUPPLIER_REFERENCE_FORMATS["SupplierHolePitchDiameter"][3] == "PCD"
    # The hole chord starts on the +X hole's edge, the PCD chord on the -Z hole.
    assert nut.SUPPLIER_REFERENCE_STARTS["SupplierMountingHoleDiameter"] == (
        nut.HOLE_CENTRES[0][0], -nut.HOLE_DIA / 2.0,
    )
    assert nut.SUPPLIER_REFERENCE_STARTS["SupplierHolePitchDiameter"] == (
        0.0, -nut.HOLE_PCD / 2.0,
    )
    # Sheet 1's FeedNut panel prints them, each text on its shelf; the
    # LeadScrew's panel carries none.
    assert set(draw.SHELVES) == set(values)
    assert draw.annotate_member(None, spec.CONFIGURATION, (), []) == ()


def test_member_specs_are_pure_data() -> None:
    allowed = {
        spec: {
            "__future__",
            "math",
            "_printed_tolerance",
            "ch_rocker_arm_tl_vn_oblique_leadscrew_spec",
        },
        nut: {
            "__future__",
            "math",
            "fractions",
            "ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec",
            "ch_rocker_arm_tl_vn_oblique_leadscrew_spec",
            "_hole_spec",
            "_mcmaster_91771a112",
        },
    }
    for module, names in allowed.items():
        source = Path(module.__file__).read_text(encoding="utf-8")
        imports = re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE)
        assert set(imports) <= names, module.__name__


# --- Builder sketches: every emitted dimension named ------------------------------


class _SketchAdapter:
    """Records sketch dimensions; every other native step succeeds."""

    def __init__(self) -> None:
        self.emitted: list[tuple] = []
        self.revolves: list = []
        self.planes: list[str] = []
        self._ok = SimpleNamespace(is_success=True, data="C0", error=None)

    async def create_sketch(self, plane):
        self.planes.append(plane)
        return self._ok

    async def add_centerline(self, *_points):
        return self._ok

    async def add_sketch_constraint(self, *_args):
        return self._ok

    async def add_sketch_dimension(self, ref1, ref2, kind, value):
        self.emitted.append((ref1, ref2, kind, value))
        return self._ok

    async def exit_sketch(self):
        return self._ok

    async def create_revolve(self, params):
        self.revolves.append(params)
        return self._ok


def _patch_sketching(monkeypatch, applied: dict, chains: list) -> None:
    async def chain(_adapter, points, close=True):
        chains.append(list(points))
        count = len(points) if close else len(points) - 1
        return [f"L{len(chains)}_{i}" for i in range(count)]

    async def defined(*_args, **_kwargs):
        return None

    def apply(self, _adapter, feature):
        applied[feature] = [name for name, _ in self._rows]
        return []

    monkeypatch.setattr(part, "add_line_chain", chain)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda *_args: None)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(part.SketchDims, "apply", apply)


def test_nut_profile_names_the_flange_thickness_it_emits(monkeypatch) -> None:
    applied, chains = {}, []
    _patch_sketching(monkeypatch, applied, chains)
    adapter = _SketchAdapter()
    asyncio.run(part._revolve_nut(adapter))
    names = applied["NutProfile"]
    assert names == list(nut.NUT_PROFILE_DIMENSIONS)
    assert len(adapter.emitted) == len(names)
    by_name = dict(zip(names, adapter.emitted, strict=True))
    assert by_name["NutAxisLength"] == ("C0", None, "linear", nut.LENGTH)
    # The flange's rim edge, seat face to head face: the printed LIMIT.
    assert by_name["FlangeThick"][2:] == ("vertical_distance", nut.FLANGE_THICK)
    assert by_name["FlangeThick"][:2] == ("L1_1.start", "L1_1.end")
    assert by_name["BodyLength"][3] == nut.BODY_LENGTH
    assert chains == [part.nut_profile_points()]
    assert adapter.planes == ["Front"] and not adapter.revolves[0].is_cut


@pytest.mark.parametrize("index", range(1, 5))
def test_countersink_profile_names_every_dimension_it_emits(monkeypatch, index) -> None:
    """Six drivers per countersink: the 82° held by the apex depth below the
    mouth, never an angular dimension; countersink 1 carries the printed
    names."""
    applied, chains, diameters = {}, [], []
    _patch_sketching(monkeypatch, applied, chains)

    async def diametric(adapter, centerline, line, text_xy, label):
        diameters.append((centerline, line, text_xy))
        adapter.emitted.append((centerline, line, "diametric", nut.CSK_DIA))

    monkeypatch.setattr(part, "add_diametric_linear_dimension", diametric)
    adapter = _SketchAdapter()
    plane, u = nut.COUNTERSINK_AXES[index - 1]
    asyncio.run(part._countersink(adapter, index, plane, u))
    names = applied[f"Countersink{index}Profile"]
    assert names == list(nut.countersink_dimensions(index))
    assert len(adapter.emitted) == len(names)
    by_kind = dict(zip(names, adapter.emitted, strict=True))
    assert by_kind[names[1]][2:] == ("horizontal_distance", abs(u))
    assert by_kind[names[2]][2:] == ("vertical_distance", nut.FLANGE_THICK)
    assert by_kind[names[3]][1:] == ("L1_1", "diametric", nut.CSK_DIA)
    assert by_kind[names[4]] == (
        "L1_0.start", "L1_1.start", "vertical_distance", nut.CSK_APEX_DEPTH,
    )
    assert by_kind[names[5]][2:] == ("vertical_distance", nut.CSK_OVERRUN)
    assert not any(kind == "angle" for *_refs, kind, _value in adapter.emitted)
    assert chains == [nut.countersink_points(u)]
    # The diameter's text stands outboard of the wall, away from the axis.
    assert abs(diameters[0][2][0]) > abs(chains[0][1][0])
    assert adapter.planes == [plane] and adapter.revolves[0].is_cut


class _ReferenceAdapter(_SketchAdapter):
    """Also records the construction entities a reference sketch draws."""

    def __init__(self) -> None:
        super().__init__()
        self.currentSketchManager = SimpleNamespace(AddToDB=False)
        self.entities: list[tuple] = []

    def _entity(self, prefix: str, *geometry) -> SimpleNamespace:
        self.entities.append((prefix, *geometry))
        return SimpleNamespace(is_success=True, data=f"{prefix}{len(self.entities)}", error=None)

    async def add_circle(self, x, y, radius):
        return self._entity("C", x, y, radius)

    async def add_line(self, x0, y0, x1, y1):
        return self._entity("L", x0, y0, x1, y1)


def _patch_reference(monkeypatch) -> tuple[dict, list, _ReferenceAdapter]:
    applied, construction = {}, []
    _patch_sketching(monkeypatch, applied, [])
    monkeypatch.setattr(part, "_as_construction", lambda _a, entity: construction.append(entity))
    return applied, construction, _ReferenceAdapter()


def test_receipt_reference_names_every_dimension_it_emits(monkeypatch) -> None:
    """4475311251: one Top-plane construction circle per receipt control,
    each driven by the control's diameter; the +Z hole's station is the only
    other driver."""
    applied, construction, adapter = _patch_reference(monkeypatch)
    asyncio.run(part._receipt_reference(adapter))
    names = applied[nut.RECEIPT_SKETCH]
    assert names == list(nut.RECEIPT_DIMENSIONS)
    assert len(adapter.emitted) == len(names)
    by_name = dict(zip(names, adapter.emitted, strict=True))
    for name, value, _centre in nut.RECEIPT_CIRCLES:
        assert by_name[name][2:] == ("diameter", pytest.approx(value)), name
    assert by_name[nut.RECEIPT_HOLE_STATION][1:] == (
        "origin", "vertical_distance", nut.HOLE_PCD / 2.0,
    )
    assert adapter.entities == [
        ("C", *centre, pytest.approx(value / 2.0)) for _name, value, centre in nut.RECEIPT_CIRCLES
    ]
    assert construction == ["C1", "C2", "C3", "C4"]
    assert adapter.planes == ["Top"]


def test_faced_length_reference_names_every_dimension_it_emits(monkeypatch) -> None:
    """The faced length's MAX is a Front-plane construction line from the
    seat face, LENGTH_MAX long, its start held on the body's -X silhouette."""
    applied, construction, adapter = _patch_reference(monkeypatch)
    asyncio.run(part._faced_length_reference(adapter))
    names = applied[nut.FACED_LENGTH_SKETCH]
    assert names == list(nut.FACED_LENGTH_DIMENSIONS)
    by_name = dict(zip(names, adapter.emitted, strict=True))
    assert by_name["FacedLength"] == ("L1.start", "L1.end", "vertical_distance", nut.LENGTH_MAX)
    x, y = nut.FACED_LENGTH_START
    assert (x, y) == (-nut.BODY_DIA / 2.0, 0.0)
    assert by_name["FacedLengthStart"] == (
        "L1.start", "origin", "horizontal_distance", nut.BODY_DIA / 2.0,
    )
    assert adapter.entities == [("L", x, y, x, y + nut.LENGTH_MAX)]
    assert construction == ["L1"] and adapter.planes == ["Front"]


# --- The package: text fit and the REWORK sheet's layout -------------------------


def test_footer_and_labels_fit_their_rows() -> None:
    assert footer.check_item(draw.ITEM, label=STEM) == draw.ITEM
    budget = math.floor((footer._FOOTER_RIGHT - footer._NOTE_X) / 0.00236)
    assert budget == 83
    assert len(draw.GENERAL_TEXT) <= budget
    assert f"SHEET {spec.MODIFIED_STOCK_SHEET}" in draw.GENERAL_TEXT
    assert f"SHEET {nut.REWORK_SHEET}" in draw.GENERAL_TEXT
    # The REWORK sheet's item label stays in its band at 2.36 mm a character.
    cell = draw.ITEM_LABEL_CELL
    assert draw.ITEM_LABEL_XY[0] + 0.00236 * len(draw.REWORK_ITEM) < cell[2]
    assert cell[0] < draw.ITEM_LABEL_XY[0] and cell[1] < draw.ITEM_LABEL_XY[1] - 0.004
    assert draw.ITEM_LABEL_XY[1] <= cell[3] and draw._inside_sheet(cell)
    # Each member sheet's item carries sheet 1's member number.
    for item, (_configuration, label) in zip(
        (draw.LEADSCREW_ITEM, draw.REWORK_ITEM), draw.VARIANTS, strict=True
    ):
        assert item.split()[0] == label.split()[0]
    for member in (spec, nut):
        assert len(member.DRAWING_NOTES) <= budget


def test_rework_sheet_lays_the_nut_out_axis_horizontal_and_clear() -> None:
    scale = draw._REWORK_PER_MODEL_MM
    assert draw.REWORK_SCALE == (4.0, 1.0)
    radius = nut.FLANGE_DIA / 2.0 * scale
    end = (
        draw.REWORK_END_CENTER[0] - radius,
        draw.REWORK_END_CENTER[1] - radius,
        draw.REWORK_END_CENTER[0] + radius,
        draw.REWORK_END_CENTER[1] + radius,
    )
    half_length = nut.LENGTH / 2.0 * scale
    section = (
        draw.REWORK_SECTION_CENTER[0] - half_length,
        draw.REWORK_SECTION_CENTER[1] - radius,
        draw.REWORK_SECTION_CENTER[0] + half_length,
        draw.REWORK_SECTION_CENTER[1] + radius,
    )
    reach = radius + draw.REWORK_SECTION_OVERRUN
    cut = (end[0], draw.REWORK_END_CENTER[1] - reach, end[2], draw.REWORK_END_CENTER[1] + reach)
    for box in (end, section, cut):
        assert draw._inside_sheet(box), box
    assert not draw._overlaps(cut, section)
    assert cut[3] < draw.ITEM_LABEL_CELL[1]
    # Text fit, notes. Calibration, run 20261105T002852195Z's native extents:
    # the 3 mm member caption "[2] FEED NUT  QTY 1 INSTALLED" read 57.2 mm
    # wide and 3.81 mm tall, 1.97 mm a character and 1.27 x its height a
    # line; the two-line spigot note read 8.9 mm from its anchor down, 4.45 mm
    # a line, so a 3.5 mm default note height (4.45 / 1.27) and 2.30 mm a
    # character. Each estimate covers these with margin.
    caption = "[2] FEED NUT  QTY 1 INSTALLED"
    caption_extent = (0.21971254849498326, 0.2583655719063545, 0.2769007759197324, 0.2621781204013378)
    measured_char = (caption_extent[2] - caption_extent[0]) / len(caption) * 3.5 / 3.0
    measured_line = (draw.SPIGOT_NOTE_XY[1] - 0.12111382608695656) / 2.0
    assert measured_char == pytest.approx(0.0023, abs=0.00005)
    assert measured_line == pytest.approx(0.00445, abs=0.00005)
    char, line = 0.0028, 0.0055
    assert char > 1.15 * measured_char and line > 1.15 * measured_line
    # Dimension text, from run 20261105T010614057Z's sheet-3 render (150 dpi):
    # the CskDia block, its value and four rows, read 0.3305..0.4227 by
    # 0.1941..0.2213 m, its shoulder from the text point rightward and its
    # rows centred on the point's height; its 30-character row
    # "91771A112 (MHA-CH-06-TL-VN-67)" read 0.3393..0.4142.
    run9_csk = (0.3305, 0.1941, 0.4227, 0.2213)
    dim_char_measured = (0.4142 - 0.3393) / 30
    dim_line_measured = (run9_csk[3] - run9_csk[1]) / 5
    dim_char, dim_line = 0.0029, 0.0065
    assert dim_char > 1.15 * dim_char_measured and dim_line > 1.15 * dim_line_measured

    def sheet_point(radius_mm, station_mm):
        return (
            draw.REWORK_SECTION_CENTER[0] + (station_mm - nut.LENGTH / 2.0) * scale,
            draw.REWORK_SECTION_CENTER[1] + radius_mm * scale,
        )

    def width(text, per_char=char):
        return per_char * max(len(row) for row in text.splitlines())

    def leadered_block(point, text, value_rows=1):
        # The shoulder's stroke starts a hair left of the point (run 9: 0.5 mm).
        # A LIMIT's value stacks its two limits in two rows.
        rows = value_rows + len(text.splitlines())
        return (
            point[0] - 0.001,
            point[1] - rows * dim_line / 2.0,
            point[0] + width(text, dim_char),
            point[1] + rows * dim_line / 2.0,
        )

    def centred_block(point, text, value_rows=1):
        # A near-side diameter's and an offset text's block is centred on its
        # point, both ways (run 20261105T023247678Z, below).
        rows = value_rows + len(text.splitlines())
        half = width(text, dim_char) / 2.0
        return (
            point[0] - half,
            point[1] - rows * dim_line / 2.0,
            point[0] + half,
            point[1] + rows * dim_line / 2.0,
        )

    # Run 20261105T023247678Z's sheet 3 (200 dpi): each measured block sits
    # inside the model's block for the point and text that printed it.
    run11 = {
        "body": (
            (0.1471, 0.2093, 0.1947, 0.2252), (0.171, 0.2175),
            f"CLEARS HEADS OF 4X\n{draw.NUT_SCREW_NUMBER}", 1,
        ),
        "hole": (
            (0.1467, 0.1499, 0.1954, 0.1699), (0.171, 0.1595),
            f"MATCHES TAPS IN\n{feed_block.NUMBER} LUG", 2,
        ),
        "faced": (
            (0.2803, 0.0980, 0.3448, 0.1135), (0.313, 0.106),
            draw.REWORK_CALLOUTS["FacedLength"][1], 1,
        ),
    }
    for name, (measured, point, text, value_rows) in run11.items():
        assert draw._inside(measured, centred_block(point, text, value_rows)), name

    # Run 9's text point and printed rows (that round's callout, the wall row
    # as it then read): the model holds the measured block and crosses the
    # border, as the render did.
    run9_text = "\n".join(
        (
            "82° CSK FOR #4-40 FLAT HEAD",
            f"{nut.SCREW_SKU} ({draw.NUT_SCREW_NUMBER})",
            "HEAD PROUD OF FACE",
            "WALL 0.39 MIN TO BODY, 0.54 MIN TO OD",
        )
    )
    run9_model = leadered_block(
        sheet_point(nut.FLANGE_DIA / 2.0 + 1.0, nut.LENGTH + 6.0), run9_text
    )
    assert draw._inside(run9_csk, run9_model)
    assert run9_csk[2] > draw.BORDER[2] and not draw._inside_sheet(run9_model)
    flange_x, flange_y = sheet_point(*draw.FLANGE_THICK_TEXT_MM)
    lane, callout = draw.REWORK_CALLOUTS["FlangeThick"]
    assert lane == "above" and "\n" not in callout
    # 3.7 over 3.3 (run 9: 0.2569..0.2628 by 0.2220..0.2296 m), the one
    # callout row above them.
    flange_limits = (
        flange_x - 1.5 * dim_char,
        flange_y - dim_line,
        flange_x + 1.5 * dim_char,
        flange_y + dim_line,
    )
    assert draw._inside((0.2569, 0.2220, 0.2628, 0.2296), flange_limits)
    half = width(callout, dim_char) / 2.0
    flange_text = (
        flange_x - half,
        flange_y + dim_line,
        flange_x + half,
        flange_y + 2.0 * dim_line,
    )
    csk_point = sheet_point(*draw.CSK_DIA_TEXT_MM)
    lane, callout = draw.REWORK_CALLOUTS["CskDia"]
    assert lane == "below"
    # A LIMIT now (4475311242): its value stacks 4.76 over 4.50.
    csk_text = leadered_block(csk_point, callout, value_rows=2)
    seat_x = sheet_point(0.0, 0.0)[0]
    flange_ink = (
        seat_x,
        draw.REWORK_SECTION_CENTER[1] - radius,
        seat_x + nut.FLANGE_THICK * scale,
        draw.REWORK_SECTION_CENTER[1] + radius,
    )
    body_ink = (
        flange_ink[2],
        draw.REWORK_SECTION_CENTER[1] - nut.BODY_DIA / 2.0 * scale,
        seat_x + nut.LENGTH * scale,
        draw.REWORK_SECTION_CENTER[1] + nut.BODY_DIA / 2.0 * scale,
    )
    note_x, note_y = draw.SPIGOT_NOTE_XY
    note = (
        note_x,
        note_y - line * len(draw.SPIGOT_NOTE.splitlines()),
        note_x + width(draw.SPIGOT_NOTE),
        note_y,
    )
    assert draw._inside(note, draw.SPIGOT_NOTE_CELL)
    # The spigot note's leader lands on the seat face, inside the annulus the
    # faced spigot stood on, just right of its cell.
    tip_r, tip_station = draw.SPIGOT_TIP_MM
    assert tip_station == 0.0
    assert nut.BORE_DIA / 2.0 < abs(tip_r) < nut.BODY_DIA / 2.0
    tip = sheet_point(tip_r, tip_station)
    assert tip[0] == pytest.approx(seat_x)
    assert draw.SPIGOT_NOTE_CELL[2] < tip[0] < draw.SPIGOT_NOTE_CELL[2] + 0.015
    assert draw.SPIGOT_NOTE_CELL[1] < tip[1] < draw.REWORK_SECTION_CENTER[1]
    # The note's native extent spans its leader: run 7 read this box, which
    # leaves the text cell, so the check bounds the cell widened to the tip.
    run7 = (0.17157912374581938, 0.12111382608695656, 0.25259577926421395, 0.14398911705685621)
    assert not draw._inside(run7, draw.SPIGOT_NOTE_CELL)
    bounds = draw.spigot_note_bounds(tip)
    assert draw._inside(run7, bounds)
    assert run7[0] < draw.SPIGOT_NOTE_CELL[2] and run7[2] >= tip[0] - draw._LEADER_TIP_MARGIN
    noted = (
        min(note[0], tip[0]),
        min(note[1], tip[1]),
        max(note[2], tip[0]),
        max(note[3], tip[1]),
    )
    assert draw._inside(noted, bounds)
    # The countersink's dimension line stands at its text point, its lower
    # arrow hanging past the body's top: clear of the body's end.
    assert csk_text[0] > body_ink[2] + 0.004
    # The faced length's LIMIT (13.8/13.2, stacked in one row as the body's
    # 10.3/10.0 prints) and its mate, offset right of the
    # far witness and under its line, over the title block and right of the
    # section's caption. The caption hangs its native box's top centre at
    # REWORK_CAPTION_TOP: run 20261105T054045952Z printed its two rows
    # (SECTION F-F, SCALE 4 : 1) 0.2586..0.3014 by 0.0833..0.0975 m and run 9
    # read its native extent 47 mm wide, so the model takes 50 by 16 mm.
    caption_x, caption_top = draw.REWORK_CAPTION_TOP
    assert caption_x == draw.REWORK_SECTION_CENTER[0]
    caption = (caption_x - 0.025, caption_top - 0.016, caption_x + 0.025, caption_top)
    assert draw._inside_sheet(caption)
    lane, faced_callout = draw.REWORK_CALLOUTS["FacedLength"]
    assert lane == "below"
    faced_text = centred_block(sheet_point(*draw.FACED_LENGTH_TEXT_MM), faced_callout)
    faced_line_y = sheet_point(*draw.FACED_LENGTH_LINE_MM)[1]
    faced_span = (seat_x, seat_x + nut.LENGTH_MAX * scale)
    assert caption[3] < faced_line_y < flange_ink[1]
    assert faced_text[0] > max(faced_span[1], caption[2])
    assert faced_text[1] > draw.TITLE_BLOCK[3]
    # Its own line and witnesses (each 1.5 mm past the line): run 11's block
    # was crossed by both, the placed one by neither.
    body_y = draw.REWORK_SECTION_CENTER[1] - nut.BODY_DIA / 2.0 * scale
    faced_own = {
        "line": (faced_span[0], faced_line_y, faced_span[1], faced_line_y),
        **{
            f"witness {x:.4f}": (x, body_y, x, faced_line_y - 0.0015)
            for x in faced_span
        },
    }
    touch = draw._OWN_LINE_TOUCH_M
    assert sorted(
        draw.text_crossings(run11["faced"][0], lines=faced_own, circles={}, touch=touch)
    ) == ["line", f"witness {faced_span[1]:.4f}"]
    assert draw.text_crossings(faced_text, lines=faced_own, circles={}, touch=touch) == []
    # callout_ink takes the longest horizontal stroke for the shoulder: the
    # mate's row, even at run 9's measured pitch, outruns the dimension line.
    assert width(faced_callout, dim_char_measured) > faced_span[1] - faced_span[0]
    # The receipt limits on the end view (4475311251), the +Z hole right of
    # its centre: each block centred on its text point, its leader radial
    # from its circle's centre to the block's shoulder (its lower-left corner).
    cx, cy = draw.REWORK_END_CENTER
    hole_centre = (cx + nut.HOLE_PCD / 2.0 * scale, cy)
    top_hole = (cx, cy + nut.HOLE_PCD / 2.0 * scale)
    csk_r = nut.CSK_DIA_MAX / 2.0 * scale
    circles = {
        "ReceiptFlangeDia": ((cx, cy), nut.FLANGE_DIA / 2.0),
        "ReceiptBodyDia": ((cx, cy), nut.BODY_DIA / 2.0),
        "ReceiptHolePcd": ((cx, cy), nut.HOLE_PCD / 2.0),
        "ReceiptHoleDia": (hole_centre, nut.HOLE_DIA / 2.0),
    }
    assert set(circles) == set(draw.RECEIPT_TEXT_XY)
    # The end view's outline as the readback projects it: model +X up the
    # sheet, +Z to the right. Run 11's hole block crossed the flange's Ø22
    # and the +Z hole's countersink; the placed blocks cross nothing.
    outline = {
        name: (cx + z * scale, cy + x * scale, radius * scale)
        for name, ((x, _y, z), radius) in draw.END_VIEW_CIRCLES_MM.items()
    }
    crossed = draw.text_crossings(run11["hole"][0], lines={}, circles=outline)
    assert "flange OD" in crossed and any(name.startswith("countersink") for name in crossed)
    receipt, leaders = {}, {}
    for name, point in draw.RECEIPT_TEXT_XY.items():
        lane, text = draw.RECEIPT_CALLOUTS[name]
        stacked = nut.DIMENSION_TOLERANCE_TYPES[name] == nut.TOL_LIMIT
        block = centred_block(point, text, value_rows=2 if stacked else 1)
        assert draw.text_crossings(block, lines={}, circles=outline) == [], name
        (ox, oy), r_mm = circles[name]
        # The shoulder's corner nearer the arrow: a block right of its
        # circle's centre hangs from its lower left, one left from its lower
        # right.
        right = (block[0] + block[2]) / 2.0 > ox
        shoulder = (block[0] if right else block[2], block[1])
        dx, dy = shoulder[0] - ox, shoulder[1] - oy
        length = math.hypot(dx, dy)
        arrow = (ox + r_mm * scale * dx / length, oy + r_mm * scale * dy / length)
        # The text stands wholly off its circle, beyond the arrow.
        assert (block[0] > arrow[0]) if right else (block[2] < arrow[0]), name
        receipt[name], leaders[name] = block, (arrow, shoulder)

    def along(segment, steps=400):
        (x0, y0), (x1, y1) = segment
        return [
            (x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps)
            for k in range(1, steps)
        ]

    def through(segment, box):
        return any(box[0] < x < box[2] and box[1] < y < box[3] for x, y in along(segment))

    def off(segment, centre, radius):
        return min(math.hypot(x - centre[0], y - centre[1]) for x, y in along(segment)) > radius

    # Two stack between the end view and the section, under the FlangeThick
    # row and over the spigot note's run-7 extent; the bolt circle's goes under
    # the end view right of the cutting line's lower letter, the flange OD's
    # under it left of the cutting line.
    letters_f = [(0.1257, y - 0.002, 0.1317, y + 0.004) for y in (0.2117, 0.1077)]
    for name in ("ReceiptBodyDia", "ReceiptHoleDia"):
        assert end[2] < receipt[name][0] and receipt[name][2] < section[0], name
        assert run7[3] + CLEAR_GAP_M <= receipt[name][1], name
        assert receipt[name][3] + CLEAR_GAP_M <= flange_text[1], name
    for name in ("ReceiptHolePcd", "ReceiptFlangeDia"):
        assert receipt[name][3] + CLEAR_GAP_M <= min(run7[1], cut[1]), name
    assert receipt["ReceiptHolePcd"][0] > letters_f[1][2]
    assert receipt["ReceiptFlangeDia"][2] < cx
    # Each block clears every other text by the readback's gap; each leader
    # runs through no text, its arrow off the countersinks it passes, and the
    # hole's under the end view's horizontal centreline.
    texts = {
        "flange limits": flange_limits,
        "flange callout": flange_text,
        "countersink": csk_text,
        "faced length": faced_text,
        "spigot note": noted,
        "spigot extent": run7,
        "caption": caption,
        **receipt,
    }
    for name, block in receipt.items():
        assert draw._inside_sheet(block), name
        assert not draw._overlaps(block, draw.ITEM_LABEL_CELL)
        assert not draw._overlaps(block, draw.TITLE_BLOCK)
        for other, box in texts.items():
            if other != name:
                assert boxes_clear(block, box), (name, other)
        for other, box in {**texts, "F1": letters_f[0], "F2": letters_f[1]}.items():
            if other != name:
                assert not through(leaders[name], box), (name, other)
        for other, segment in leaders.items():
            if other != name:
                assert not any(
                    math.hypot(x - u, y - v) < 0.001
                    for x, y in along(segment, 100)
                    for u, v in along(leaders[name], 100)
                ), (name, other)
    bottom_hole = (cx, cy - nut.HOLE_PCD / 2.0 * scale)
    for name in ("ReceiptBodyDia", "ReceiptHolePcd"):
        for hole in (hole_centre, top_hole, bottom_hole):
            assert off(leaders[name], hole, csk_r + 0.002), name
    assert max(y for _x, y in along(leaders["ReceiptHoleDia"])) < cy
    for name, block in {"faced length": faced_text}.items():
        for other, box in texts.items():
            if other != name:
                assert boxes_clear(block, box), (name, other)
    texts_old = (flange_limits, flange_text, csk_text, noted, faced_text)
    for index, text in enumerate(texts_old):
        assert draw._inside_sheet(text), text
        assert not draw._overlaps(text, draw.ITEM_LABEL_CELL)
        for ink in (flange_ink, body_ink, end, cut):
            assert not draw._overlaps(text, ink), (text, ink)
        for other in texts_old[index + 1 :]:
            assert not draw._overlaps(text, other), (text, other)
    assert draw.REWORK_END_ANGLE == math.pi / 2.0
    # One letter per cut in the package: sheet 2's A to E, sheet 3's F.
    letters = [
        *(section.label for section in draw.CLOCK_SECTIONS),
        *(detail.label for detail in draw.END_DETAILS),
        draw.REWORK_SECTION_LABEL,
    ]
    assert letters == ["A", "B", "C", "D", "E", "F"]
    source = Path(draw.__file__).read_text(encoding="utf-8")
    rework = source[source.index("def _append_feed_nut_rework_sheet") :]
    assert "configure_reference_views(adapter, feed_nut.CONFIGURATION, [end])" in rework
    assert "_require_axis_horizontal(adapter, section" in rework
    # F-F is cut and curated while the part shows the faced length's hidden
    # carrier; the receipt diameters follow on the end view.
    steps = [
        rework.index(call)
        for call in (
            "hidden_sketches.part_sketches_shown(",
            "create_section_view(",
            "hidden_sketches.curate_view_dimensions(",
            "offset_dimension_text(adapter, annotations",
            "verify_machining_controls(",
            "_set_callouts(adapter, annotations, REWORK_CALLOUTS)",
            "_receipt_dimensions(adapter, end)",
        )
    ]
    assert steps == sorted(steps)
    receipt_source = source[source.index("def _receipt_dimensions") :]
    steps = [
        receipt_source.index(call)
        for call in (
            "hidden_sketches.curate_view_dimensions(",
            "set_near_side_diameter(",
            "verify_machining_controls(",
            "_set_callouts(adapter, receipt, RECEIPT_CALLOUTS)",
        )
    ]
    assert steps == sorted(steps)


# Run 20261105T030845448Z's logged callout ink on sheet 3: (shoulder box,
# display lines), sheet metres. Its readback refused CskDia for "own line 1",
# the upper extension line, which runs 1.0 mm past the dimension line into
# the text that abuts it, as run 11 printed it, unflagged.
_RUN12_INK = {
    "CskDia": (
        (0.3150, 0.1924, 0.3971, 0.2236),
        [
            (0.2690, 0.1828, 0.3160, 0.1828),
            (0.2690, 0.2012, 0.3160, 0.2012),
            (0.3971, 0.1924, 0.3150, 0.1924),
            (0.3150, 0.1924, 0.3150, 0.2012),
            (0.3150, 0.1828, 0.3150, 0.1765),
        ],
    ),
    "FacedLength": (
        (0.3182, 0.0861, 0.3822, 0.1027),
        [
            (0.2530, 0.1386, 0.2530, 0.1050),
            (0.3082, 0.1386, 0.3082, 0.1050),
            (0.2530, 0.1060, 0.2467, 0.1060),
            (0.2530, 0.1060, 0.3082, 0.1060),
            (0.3082, 0.1060, 0.3146, 0.1060),
            (0.2806, 0.1060, 0.3182, 0.0861),
            (0.3182, 0.0861, 0.3822, 0.0861),
        ],
    ),
    "ReceiptBodyDia": (
        (0.1796, 0.2091, 0.2288, 0.2259),
        [(0.1268, 0.1719, 0.1796, 0.2091), (0.1796, 0.2091, 0.2288, 0.2091)],
    ),
    "ReceiptHolePcd": (
        (0.1775, 0.1866, 0.2309, 0.2034),
        [(0.1398, 0.1717, 0.1775, 0.1866), (0.1775, 0.1866, 0.2309, 0.1866)],
    ),
    "ReceiptHoleDia": (
        (0.1690, 0.1494, 0.2394, 0.1696),
        [(0.1485, 0.1574, 0.1690, 0.1494), (0.1690, 0.1494, 0.2394, 0.1494)],
    ),
}


def test_callout_text_crossings_pass_run_12_and_refuse_run_11() -> None:
    """The readback's crossing rule on measured ink: a callout's own line may
    end just inside its text (run 12's CskDia extension line, 1.0 mm), but a
    line or witness through it (run 11's faced length) and a part outline
    through it (run 11's hole callout) refuse."""
    scale = draw._REWORK_PER_MODEL_MM
    cx, cy = draw.REWORK_END_CENTER
    circles = {
        name: (cx + z * scale, cy + x * scale, radius * scale)
        for name, ((x, _y, z), radius) in draw.END_VIEW_CIRCLES_MM.items()
    }
    sx, sy = draw.REWORK_SECTION_CENTER

    def section_point(radius, station):
        return (sx + (station - nut.LENGTH / 2.0) * scale, sy + radius * scale)

    lines = {
        name: (*section_point(*start), *section_point(*end))
        for name, (start, end) in draw.SECTION_OUTLINE_MM.items()
    }
    touch = draw._OWN_LINE_TOUCH_M
    for name, (text, ink) in _RUN12_INK.items():
        # callout_ink's leader: every line but the shoulder under the text.
        own = {
            str(index): line
            for index, line in enumerate(
                line for line in ink if not (line[1] == line[3] == text[1])
            )
        }
        assert len(own) == len(ink) - 1, name
        assert draw.text_crossings(text, lines=own, circles={}, touch=touch) == [], name
        assert draw.text_crossings(text, lines=lines, circles=circles) == [], name
    # The pass is the touch allowance: the extension line does end inside.
    text, ink = _RUN12_INK["CskDia"]
    assert draw.text_crossings(text, lines={"extension": ink[1]}, circles={}) == ["extension"]
    # Run 11's faced length: its line and far witness through the text.
    faced = (0.2803, 0.0980, 0.3448, 0.1135)
    _text, ink = _RUN12_INK["FacedLength"]
    witnesses = {"line": ink[3], "far witness": ink[1], "near witness": ink[0]}
    assert draw.text_crossings(faced, lines=witnesses, circles={}, touch=touch) == [
        "line", "far witness",
    ]
    # Run 11's hole callout: the flange's Ø22 and the +Z countersink.
    crossed = draw.text_crossings((0.1467, 0.1499, 0.1954, 0.1699), lines=lines, circles=circles)
    assert "flange OD" in crossed and any(name.startswith("countersink") for name in crossed)


# Run 20261105T054045952Z's sheet 3 (150 dpi): section F-F's caption where
# SolidWorks hung it, its two rows' printed ink, and the faced length's ink
# where run 12 logged it (_RUN12_INK; the render's leader runs 0.2806, 0.1061
# to 0.3180, 0.0862), the leader across the caption's second F.
_RUN17_FF_CAPTION = (0.2586, 0.0833, 0.3014, 0.0975)
_RUN7_SPIGOT_EXTENT = (0.17157912374581938, 0.12111382608695656, 0.25259577926421395, 0.14398911705685621)


def _rework_readback(monkeypatch, caption):
    """Sheet 3 as ``_assert_rework_ink`` reads it, the faced length its one
    leadered callout: section F-F owns its native caption (the linked
    view-label field) and the spigot note (literal text); the end view owns
    no note. Returns the readback's arguments after the annotations and the
    faced length's ink."""

    def extent(box):
        return (box[0], box[1], 0.0, box[2], box[3], 0.0)

    spigot = SimpleNamespace(
        PropertyLinkedText=draw.SPIGOT_NOTE, GetExtent=lambda: extent(_RUN7_SPIGOT_EXTENT)
    )
    native_caption = SimpleNamespace(
        PropertyLinkedText="<VLNAME> <VLLABEL>\r\n<VLSCALE><VLSCALEV>",
        GetExtent=lambda: extent(caption),
    )
    section = SimpleNamespace(GetNotes=lambda: (native_caption, spigot))
    end = SimpleNamespace(GetNotes=lambda: ())
    text, lines = _RUN12_INK["FacedLength"]
    label = "FacedLength callout"
    ink = CalloutInk(
        label,
        text,
        tuple(
            LeaderSegment(label, "dim", *line)
            for line in lines
            if not (line[1] == line[3] == text[1])
        ),
    )
    monkeypatch.setattr(draw, "LEADERED", ("FacedLength",))
    monkeypatch.setattr(draw, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(draw, "sheet_region", lambda _adapter: DrawableRegion(*draw.BORDER))
    monkeypatch.setattr(draw, "_named", lambda _adapter, _annotations: {"FacedLength": "dim"})
    monkeypatch.setattr(draw, "_callout_block", lambda _adapter, _dim, _label: (ink, text))
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "_rework_outlines", lambda _adapter, _end, _section: ({}, {}))
    return (spigot, end, section), ink


def test_rework_readback_keeps_leaders_off_the_view_captions(monkeypatch) -> None:
    """Section F-F's caption counts as text a leader must clear by the
    readback's gap: where run 17 printed it the faced length's leader ran
    through it, 1 mm lower the leader grazes it, and at REWORK_CAPTION_TOP
    (the 50 x 16 mm model of its native box) it clears. The spigot note the
    section also owns is no caption, and the caption stays off the title
    block."""
    args, ink = _rework_readback(monkeypatch, _RUN17_FF_CAPTION)
    assert draw.view_captions({"end view": args[1], "section F-F": args[2]}) == {
        "section F-F caption": _RUN17_FF_CAPTION,
    }
    with pytest.raises(RuntimeError, match=r"leader runs through \['section F-F caption'\]"):
        draw._assert_rework_ink(None, [], *args)
    # The leader passes 1 mm over this box's top right corner: clear of the
    # printed letters, inside the gap.
    left, _bottom, right, top = _RUN17_FF_CAPTION
    corner_y = 0.1060 - (right - 0.2806) * (0.1060 - 0.0861) / (0.3182 - 0.2806)
    grazed = (left, corner_y - 0.001 - (top - _bottom), right, corner_y - 0.001)
    draw.require_leader_clear(ink, {"caption": grazed})
    args, _ink = _rework_readback(monkeypatch, grazed)
    with pytest.raises(RuntimeError, match="leader runs through"):
        draw._assert_rework_ink(None, [], *args)
    x, y = draw.REWORK_CAPTION_TOP
    args, _ink = _rework_readback(monkeypatch, (x - 0.025, y - 0.016, x + 0.025, y))
    draw._assert_rework_ink(None, [], *args)
    # Dropped onto the title block, the caption refuses.
    low = (x - 0.025, draw.TITLE_BLOCK[3] - 0.006, x + 0.025, draw.TITLE_BLOCK[3] + 0.010)
    args, _ink = _rework_readback(monkeypatch, low)
    with pytest.raises(RuntimeError, match="section F-F caption .* runs onto the title block"):
        draw._assert_rework_ink(None, [], *args)


def test_notes_name_the_item_not_its_length_or_material() -> None:
    # The cut length is the dimension's, the material the title block's, and
    # no line prescribes a method (rule 7).
    assert draw.LEADSCREW_ITEM == "[1] TR8X2 LEAD SCREW"
    assert "STAINLESS" not in draw.NOTES.upper()
    assert f"{spec.LENGTH:.0f}" not in draw.NOTES
    for name in ("Supplier", "Supplier SKUs"):
        assert property_link(name) in draw.NOTES
    # Identity only: no stock size row. The bought stock's sizes are the
    # thread designation's and the SKU's; a note typing spec numbers that no
    # native dimension owns breaks model ownership (rule 7, review), and the
    # 1:10 gauge sketch before it read as a confusing pseudo-view. Note 1
    # (the across-flat's free clock) follows the three identity rows.
    identity = "\n".join(draw.NOTES.splitlines()[:3])
    assert draw.NOTES == f"{identity}\n{draw.FLAT_CLOCK_NOTE}"
    assert not hasattr(draw, "STOCK_REFERENCE")
    assert re.findall(r"\d", identity.replace("TR8X2", "").replace("[1]", "")) == []
    assert not hasattr(spec, "SUPPLIER_REFERENCE_DIMENSIONS")
    assert "Manufacturing Notes" not in draw.NOTES
    assert set(part.MEMBER_NOTE_PROPERTIES) <= set(part.SAVED_DRAWING_PROPERTIES)


def test_sections_print_hidden_lines_removed_and_text_off_their_lines() -> None:
    """Precision display on every view (a section left at draft prints
    faceted), and the across-flat's and angles' texts offset off their lines."""
    source = Path(draw.__file__).read_text(encoding="utf-8")
    sections = source[source.index("def _add_clock_sections") :]
    assert "set_hidden_lines_removed(adapter, view)" in sections
    assert "for view in (main, iso):" in source
    assert "_offset_angle_text(adapter, view_annotations, angle, arc, angle_text)" in (
        sections
    )
    details = source[source.index("def _add_end_details") :]
    assert "set_hidden_lines_removed(adapter, view)" in details
    build = source[source.index("def _append_leadscrew_sheet") :]
    assert "FLAT_AF_TEXT_XY" not in source
    assert build.index("_add_end_details(adapter, main)") < build.index(
        "verify_machining_controls("
    )


def _fence_box(detail) -> tuple[float, float, float, float]:
    half = detail.radius_mm * draw._DETAIL_PER_MODEL_MM
    x, y = detail.centre
    return (x - half, y - half, x + half, y + half)


def test_details_show_every_flat_at_the_sections_scale() -> None:
    """The 1:2 view draws a flat 0.36 mm deep: each station's flats, and the
    screw's ends, stand whole in one 3:1 detail fence (review r9, rule 15)."""
    assert draw.DETAIL_SCALE == draw.SECTION_SCALE == (3, 1)
    labels = [detail.label for detail in draw.END_DETAILS]
    assert labels == ["C", "D", "E"]
    assert not set(labels) & {section.label for section in draw.CLOCK_SECTIONS}
    radius = spec.MAJOR_DIA / 2.0

    def fences(station: float, offset: float) -> list[str]:
        return [
            detail.label
            for detail in draw.END_DETAILS
            if math.hypot(station - detail.centre_mm, offset) < detail.radius_mm
        ]

    for name, station in spec.FLAT_STATIONS.items():
        corners = [
            fences(station + along * spec.FLAT_LENGTH / 2.0, across * radius)
            for along in (-1.0, 1.0)
            for across in (-1.0, 1.0)
        ]
        assert all(found == corners[0] and len(found) == 1 for found in corners), name
    for end in (0.0, spec.LENGTH):
        assert all(len(fences(end, across * radius)) == 1 for across in (-1.0, 1.0))
    assert [fences(station, 0.0)[0] for station in spec.FLAT_STATIONS.values()] == [
        "C",
        "D",
        "E",
    ]
    # The fences stand apart on the main view, and so do the details, in a
    # row under its lowest text, left of the title block and in the border.
    spans = sorted(
        (detail.centre_mm - detail.radius_mm, detail.centre_mm + detail.radius_mm)
        for detail in draw.END_DETAILS
    )
    assert all(left[1] < right[0] for left, right in zip(spans, spans[1:]))
    boxes = [_fence_box(detail) for detail in draw.END_DETAILS]
    lowest_main_text = min(y for _x, y in draw.MAIN_KEEP.values())
    for box in boxes:
        assert draw._inside_sheet(box), box
        assert box[3] < lowest_main_text - draw.TEXT_HALF_HEIGHT - 0.010
    assert all(left[2] + 0.004 < right[0] for left, right in zip(boxes, boxes[1:]))


def test_details_carry_the_near_station_and_the_printed_flat() -> None:
    """C prints the near station from the near end's centre; D the KP08
    flats' length (4X); E the open flat's across-flat (3X); every text off
    its fence and over the captions' row."""
    by_label = {detail.label: detail for detail in draw.END_DETAILS}
    assert set(by_label["C"].keep) == {"NearKP08FlatStation"}
    assert set(by_label["D"].keep) == {"FlatLength"}
    assert set(by_label["E"].keep) == {"FlatAF"}
    assert (spec.PRINTED_FLAT, spec.PRINTED_LENGTH_FLAT) == ("Handwheel", "FarKP08")
    assert set(draw.FLAT_CALLOUTS) == {"FlatLength", "FlatAF"}
    for detail in draw.END_DETAILS:
        fence = detail.radius_mm * draw._DETAIL_PER_MODEL_MM
        for name, (x, y) in detail.keep.items():
            assert math.dist((x, y), detail.centre) > fence + 0.004, name
            assert y - draw.TEXT_HALF_HEIGHT - 0.006 > draw.DETAIL_CAPTION_TOP
            assert draw.BORDER[0] < x < draw.TITLE_BLOCK[0]
    # The flat's length and the near station hang under their spans.
    near, far, wheel = by_label["C"], by_label["D"], by_label["E"]
    x, _y = near.keep["NearKP08FlatStation"]
    assert draw.detail_xy(near.centre_mm, near.centre, 0.0)[0] < x
    assert (
        x
        < draw.detail_xy(near.centre_mm, near.centre, spec.FLAT_STATIONS["NearKP08"])[0]
    )
    # The flat length's text stands right of the far KP08 flat's far-end
    # extension line (review jbf-r17, rule 14), its widest row clear of the
    # line and of E's fence.
    flat_end = draw.detail_xy(
        far.centre_mm,
        far.centre,
        spec.FLAT_STATIONS["FarKP08"] + spec.FLAT_LENGTH / 2.0,
    )[0]
    text_x, text_y = far.keep["FlatLength"]
    assert text_x - draw.FLAT_LENGTH_TEXT_HALF_WIDTH > flat_end
    assert text_x + draw.FLAT_LENGTH_TEXT_HALF_WIDTH < _fence_box(wheel)[0]
    flat_rows = draw.FLAT_CALLOUTS["FlatLength"].splitlines()
    assert draw.FLAT_LENGTH_TEXT_HALF_WIDTH * 2 > 0.0022 * max(map(len, flat_rows))
    # The across-flat's dimension line stands left of E's fence, short of the
    # flat's start (so its extension line leaves the fence over the flat, not
    # along the thread), its text (widest row "C, D, E", about 15 mm) clear of
    # both fences and between the far crest and the flat, and a row over the
    # flat length's rows (its value and its callout's).
    af_x, af_y = wheel.keep["FlatAF"]
    flat_start = spec.FLAT_STARTS["Handwheel"]
    assert wheel.centre_mm - wheel.radius_mm < flat_start
    assert af_x + 0.0075 < _fence_box(wheel)[0]
    assert af_x - 0.0075 > _fence_box(far)[2] + 0.004
    af_rows = 1 + len(draw.FLAT_CALLOUTS["FlatAF"].splitlines())
    assert af_y - af_rows * draw.TEXT_HALF_HEIGHT > (
        text_y + (1 + len(flat_rows)) * draw.TEXT_HALF_HEIGHT
    )
    radius = spec.MAJOR_DIA / 2.0
    crest = draw.detail_xy(wheel.centre_mm, wheel.centre, 0.0, -radius)[1]
    flat = draw.detail_xy(wheel.centre_mm, wheel.centre, 0.0, spec.FLAT_AF - radius)[1]
    assert flat < af_y < crest
    # The open flat runs out through the end inside E's fence.
    assert wheel.centre_mm + wheel.radius_mm > spec.LENGTH


def test_details_letters_stand_off_the_screw() -> None:
    letters = [detail.letter for detail in draw.END_DETAILS]
    for x, y in letters:
        assert abs(y - draw.MAIN_CENTER[1]) > draw.SCREW_SHEET_DIA / 2.0 or (
            x > draw.sheet_x(spec.LENGTH) + 0.004 or x < draw.NEAR_END_X - 0.004
        )
    assert all(math.dist(a, b) > 0.010 for a in letters for b in letters if a != b)


def test_settled_detail_frames_fit_after_translating_the_whole_bank() -> None:
    # Final native 0c3 frames, not the smaller nominal fences. C's box is
    # also the 84d failure: the earlier placement check was not a settled one.
    measured = (
        (.008517633303345734, .047647259642392935, .0772935907769218, .11642314838436299),
        (.0638121, .0548120, .1181879, .1091880),
        (.1307121, .0512121, .1922879, .1127879),
    )
    old_x = (.043, .091, .1615)
    translations = [detail.centre[0] - x for detail, x in zip(draw.END_DETAILS, old_x, strict=True)]
    # The bank moved +8 mm; E 4 mm more, widening the D-E text lane.
    assert translations == pytest.approx([.008, .008, .012])
    for detail, box, dx in zip(draw.END_DETAILS, measured, translations, strict=True):
        moved = (box[0] + dx, box[1], box[2] + dx, box[3])
        draw._require_detail_bounds(SimpleNamespace(GetOutline=lambda box=moved: box), detail)
        assert moved[0] - draw.BORDER[0] > .003
        assert draw.TITLE_BLOCK[0] - moved[2] > .011


def test_detail_containment_is_rechecked_when_the_native_outline_settles() -> None:
    detail = draw.END_DETAILS[0]._replace(centre=(.043, draw.DETAIL_ROW_Y))
    outline = _fence_box(detail)
    view = SimpleNamespace(GetOutline=lambda: outline)
    draw._require_detail_bounds(view, detail)
    # Same centre, expanded native frame: this must refuse even if the
    # geometric-fence check already passed, as it did in the old build.
    outline = (.008517633303345734, .047647259642392935, .0772935907769218, .11642314838436299)
    with pytest.raises(RuntimeError, match="leaves the drawable sheet"):
        draw._require_detail_bounds(view, detail)
    # A displaced frame still inside the border must not silently move the
    # detail away from the authored dimension and caption lanes.
    detail = draw.END_DETAILS[0]
    outline = tuple(v + (.001 if i in (0, 2) else 0)
                    for i, v in enumerate(_fence_box(detail)))
    with pytest.raises(RuntimeError, match="moved from its reserved centre"):
        draw._require_detail_bounds(view, detail)


def test_detail_bounds_are_read_after_projection_and_in_the_final_callback() -> None:
    tree = ast.parse((SCRIPTS / "draw_ch_rocker_arm_tl_vn_oblique_leadscrew_kit.py").read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    create = functions["_create_end_detail"]
    calls = [node.value.func.id for node in create.body
             if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
             and isinstance(node.value.func, ast.Name)]
    assert calls.index("_require_detail_bounds") > calls.index("settle_detail_projection")
    [settled] = [node for node in functions["_append_leadscrew_sheet"].body
                 if isinstance(node, ast.FunctionDef) and node.name == "settled"]
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "_require_detail_bounds" for node in ast.walk(settled))


def test_thread_is_called_out_on_the_main_view() -> None:
    """The bought thread is named by a leadered callout touching the screw,
    a designation and its extent, no size or method (rule 7)."""
    assert draw.THREAD_CALLOUT.splitlines()[0] == "TR8X2 THREAD FULL LENGTH"
    assert re.findall(r"\d", draw.THREAD_CALLOUT.replace("TR8X2", "")) == []
    tip_x, tip_y = draw.THREAD_LEADER_TIP
    assert draw.NEAR_END_X < tip_x < draw.sheet_x(spec.LENGTH)
    assert tip_y == pytest.approx(draw.MAIN_CENTER[1] + draw.SCREW_SHEET_DIA / 2.0)
    text_x, text_top = draw.THREAD_CALLOUT_XY
    # Under the cut length's dimension line, over the screw, clear of the
    # sections' letters 4.8 .. 6.3 mm in from the cutting lines' ends.
    assert text_top < draw.MAIN_KEEP["CutLength"][1] - 0.006
    assert text_top - 0.009 > tip_y + 0.005
    cuts = [draw.sheet_x(section.cut_mm) for section in draw.CLOCK_SECTIONS]
    assert min(cuts) + 0.025 < text_x and text_x + 0.060 < max(cuts) - 0.015
    source = Path(draw.__file__).read_text(encoding="utf-8")
    build = source[source.index("def _append_leadscrew_sheet") :]
    assert "add_leader_note(" in build and "view=main," in build


@pytest.mark.parametrize("target", sorted(spec.DIMENSION_CONTROLS))
@pytest.mark.parametrize(
    "fault",
    [None, "reference", "nominal", "tolerance_type", "widened", "precision", "missing"],
)
def test_drawing_requires_every_control(monkeypatch, fault, target) -> None:
    """A reference-only, moved, banded or re-placed control is a regression."""
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    assert draw.EXPECTED_CONTROLS["CutLength"] == (
        pytest.approx(spec.LENGTH / 1000.0),
        pytest.approx(-0.0008),
        pytest.approx(0.0008),
    )
    assert draw.EXPECTED_CONTROLS["FlatAF"] == (
        pytest.approx(0.00728),
        pytest.approx(-0.00051),
        pytest.approx(0.00051),
    )
    assert draw.EXPECTED_CONTROLS["NearKP08ClockAngle"] == (
        pytest.approx(math.radians(120.0)),
        pytest.approx(-math.radians(1.0)),
        pytest.approx(math.radians(1.0)),
    )
    annotations = []
    parts = {}
    for name, (nominal, lower, upper) in draw.EXPECTED_CONTROLS.items():
        tolerance = SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda value=lower: value,
            GetMaxValue=lambda value=upper: value,
        )
        dimension = SimpleNamespace(
            Name=name, DrivenState=2, SystemValue=nominal, Tolerance=tolerance
        )
        display = SimpleNamespace(
            GetDimension2=lambda _configuration, value=dimension: value,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda value=spec.DIMENSION_PRECISION[name]: value,
        )
        annotations.append(
            SimpleNamespace(
                name=name, GetSpecificAnnotation=lambda value=display: value
            )
        )
        parts[name] = (tolerance, dimension, display, upper)
    tolerance, dimension, display, upper = parts[target]
    if fault == "reference":
        dimension.DrivenState = 1
    elif fault == "nominal":
        dimension.SystemValue += 0.001
    elif fault == "tolerance_type":
        tolerance.Type = 4  # swTolSYMMETRIC prints a band the title block carries.
    elif fault == "widened":
        tolerance.GetMaxValue = lambda: upper + 0.001
    elif fault == "precision":
        display.GetPrimaryPrecision2 = lambda: (
            2 if spec.DIMENSION_PRECISION[target] != 2 else 3
        )
    elif fault == "missing":
        annotations = [a for a in annotations if a.name != target]

    def verify() -> None:
        trim_drawing.verify_machining_controls(
            annotations,
            expected=draw.EXPECTED_CONTROLS,
            tolerance_types=spec.DIMENSION_TOLERANCE_TYPES,
            precision=spec.DIMENSION_PRECISION,
        )

    if fault is None:
        verify()
    else:
        with pytest.raises(RuntimeError):
            verify()


@pytest.fixture
def supplier_attachment_state(monkeypatch):
    """Stateful native identities: equal coordinates never imply IsSame."""
    state = SimpleNamespace(
        reads=[], messages=[], captures=[], faults={}, log_fault=None,
        capture_fault=None, warning_fault=None, warnings=[], bound_points=[],
        id_read_objects=[], predicate_point_objects={},
    )
    frame = SimpleNamespace(ArrayData=(
        1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
        0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
    ))

    def read(token, member, value):
        state.reads.append((token, member))
        fault = state.faults.get((token, member))
        if isinstance(fault, Exception):
            raise fault
        return value if fault is None else fault

    class Sketch:
        def __init__(self, token):
            self.token = token
            self.ModelToSketchTransform = frame
            self.points = []
            self.segments = []
            self.inventory_reads = {11: 0, 10: 0}

        def inventory(self, kind, objects):
            self.inventory_reads[kind] += 1
            if self.inventory_reads[kind] > 1:
                raise AssertionError("diagnostics must not replace the refused inventory")
            return objects

        def GetSketchPoints2(self):
            return self.inventory(11, self.points)

        def GetSketchSegments(self):
            return self.inventory(10, self.segments)

    class Point:
        Type = 0

        def __init__(self, token, index, xyz, owner, generation=0):
            self.token, self.index, self.xyz, self.owner = token, index, xyz, owner
            self.generation = generation

        def GetID(self):
            # A newly rebound wrapper exposes a different context-local ID.
            state.id_read_objects.append(self)
            return read(self.token, "GetID", (self.index, self.generation))

        def GetSketch(self):
            return read(self.token, "GetSketch", self.owner)

        @property
        def X(self):
            return read(self.token, "X", self.xyz[0])

        @property
        def Y(self):
            return read(self.token, "Y", self.xyz[1])

        @property
        def Z(self):
            return read(self.token, "Z", self.xyz[2])

    class Segment:
        def __init__(self, token, index, endpoints, owner):
            self.token, self.index, self.endpoints, self.owner = token, index, endpoints, owner

        def GetType(self):
            return 0  # swSketchLINE

        def GetID(self):
            return read(self.token, "GetID", (self.index, 1))

        @property
        def ConstructionGeometry(self):
            return read(self.token, "ConstructionGeometry", True)

        def GetStartPoint2(self):
            return read(self.token, "GetStartPoint2", self.endpoints[0])

        def GetEndPoint2(self):
            return read(self.token, "GetEndPoint2", self.endpoints[1])

        def GetSketch(self):
            return read(self.token, "GetSketch", self.owner)

    def typed(value, interface):
        if interface == "ISketchPoint" and isinstance(value, Point):
            value = Point(value.token, value.index, value.xyz, value.owner, value.generation + 1)
            state.bound_points.append(value)
        return value

    monkeypatch.setattr(supplier_dimensions, "_early_bound", typed)

    source_sketch, view_sketch = Sketch("source-sketch"), Sketch("view-sketch")
    source_points = [
        Point(f"source-{index}", index, (index * 0.002, 0.004, 0.0), source_sketch)
        for index in range(6)
    ]
    mapped_points = [
        Point(f"mapped-{index}", index, point.xyz, view_sketch)
        for index, point in enumerate(source_points)
    ]
    attached = [
        Point(f"attached-{index}", index, mapped_points[index].xyz, view_sketch)
        for index in (0, 5)
    ]
    source_sketch.points = source_points
    source_segments = [
        Segment(f"source-line-{index}", index, source_points[2 * index:2 * index + 2], source_sketch)
        for index in range(3)
    ]
    mapped_segments = [
        Segment(f"mapped-line-{index}", index, mapped_points[2 * index:2 * index + 2], view_sketch)
        for index in range(3)
    ]
    source_sketch.segments = source_segments
    feature_reads = []

    def source_specific():
        feature_reads.append("source-sketch")
        if len(feature_reads) > 1:
            raise AssertionError("diagnostics must retain the actual source sketch")
        return source_sketch

    source_feature = SimpleNamespace(
        token="source-feature", Name="SupplierReference",
        GetTypeName2=lambda: "ProfileFeature", GetSpecificFeature2=source_specific,
    )
    source_model = SimpleNamespace(
        GetPathName=lambda: "supplier-source.SLDPRT",
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="SupplierStock"),
        ),
        SketchManager=SimpleNamespace(ActiveSketch=None),
    )
    def system_values(which_configurations, config_names):
        # gen_py declares (VT_I4, VT_VARIANT); the documented variant accepts
        # either one BSTR or a BSTR array, not arbitrary configuration objects.
        if type(which_configurations) is not int or which_configurations != 3:
            raise TypeError("GetSystemValue3 requires swSpecifyConfiguration here")
        if isinstance(config_names, str):
            names = (config_names,)
        elif isinstance(config_names, (tuple, list)) and all(type(name) is str for name in config_names):
            names = tuple(config_names)
        else:
            raise TypeError("Config_names must be a BSTR or BSTR array")
        if names != ("SupplierStock",):
            raise ValueError("dimension readback requested a different configuration")
        return (0.600,)

    native_dimension = SimpleNamespace(
        token="native-dimension", FullName="SupplierStockLength@SupplierReference@supplier-source.SLDPRT",
        DrivenState=2, GetSystemValue3=system_values,
        GetFeatureOwner=lambda: source_feature,
    )
    mapping_reads = {}

    def corresponding(point):
        mapping_reads[point.token] = mapping_reads.get(point.token, 0) + 1
        if mapping_reads[point.token] > 1:
            raise AssertionError("diagnostics must not replace the refused mapping")
        return state.mapping[point.token]

    view = SimpleNamespace(
        token="view", ReferencedDocument=source_model,
        ReferencedConfiguration="SupplierStock", ModelToViewTransform=frame,
        GetSketch=lambda: view_sketch, GetCorresponding=corresponding,
        GetReferencedModelName=lambda: "supplier-source.SLDPRT",
        GetOrientationName=lambda: "*Front",
        GetName2=lambda: "SupplierStock",
    )
    attachment_reads = []

    def entities():
        attachment_reads.append("entities")
        if attachment_reads.count("entities") > 1:
            raise AssertionError("diagnostics must retain the actual attachments")
        return state.attached

    def types():
        attachment_reads.append("types")
        if attachment_reads.count("types") > 1:
            raise AssertionError("diagnostics must retain the actual attachment types")
        return (state.kind,) * len(state.attached)

    annotation = SimpleNamespace(GetAttachedEntities3=entities, GetAttachedEntityTypes=types)

    def dimension(_index):
        state.reads.append(("display", "GetDimension2"))
        return native_dimension

    display = SimpleNamespace(GetAnnotation=lambda: annotation, GetDimension2=dimension)
    drawing = SimpleNamespace(
        GetPathName=lambda: "refused.SLDDRW", GetEditSheet=lambda: True,
        ActiveDrawingView=view, SketchManager=SimpleNamespace(ActiveSketch=None),
    )
    def native_same(left, right):
        if not state.reads:
            for obj in (left, right):
                if isinstance(obj, Point):
                    state.predicate_point_objects[id(obj)] = obj
        return int(left.token == right.token)


    adapter = SimpleNamespace(
        currentModel=drawing,
        swApp=SimpleNamespace(IsSame=native_same),
    )

    def log(message):
        if state.log_fault is not None:
            raise state.log_fault
        state.messages.append(message)

    def warn(message):
        state.warnings.append(message)
        if state.warning_fault is not None:
            raise state.warning_fault

    def capture(_adapter, _label, _message, **kwargs):
        state.captures.append(kwargs)
        if state.capture_fault is not None:
            raise state.capture_fault
        raise kwargs["exception"]

    actual_correspondence = supplier_dimensions._attachment_correspondence

    def observed_correspondence(*args, **kwargs):
        result = actual_correspondence(*args, **kwargs)
        state.returned_proof = result
        state.private_cache = result.get("_failure_native_objects")
        return result

    monkeypatch.setattr(supplier_dimensions, "_attachment_correspondence", observed_correspondence)
    monkeypatch.setattr(supplier_dimensions, "_assert_dimension_source", lambda *_args, **_kwargs: source_feature)
    monkeypatch.setattr(supplier_dimensions._telemetry, "info", log)
    monkeypatch.setattr(supplier_dimensions._telemetry, "warn", warn)
    monkeypatch.setattr(supplier_dimensions._seat_forensics, "capture_com_failure", capture)
    state.adapter, state.view, state.display = adapter, view, display
    state.source_sketch, state.view_sketch = source_sketch, view_sketch
    state.source_points, state.mapped_points, state.attached = source_points, mapped_points, attached
    state.kind = 11
    state.mapping = dict(zip(
        (point.token for point in source_points), mapped_points, strict=True,
    ))
    state.source_segments, state.mapped_segments = source_segments, mapped_segments
    state.segment_type = Segment
    state.native_dimension = native_dimension
    state.mapping_reads, state.attachment_reads = mapping_reads, attachment_reads

    def verify():
        supplier_dimensions._assert_source(
            adapter, view, display, name="SupplierStockLength", feature="SupplierReference",
        )

    state.verify = verify
    return state


def test_supplier_attachment_equal_xyz_different_identity_still_refuses(
    supplier_attachment_state,
) -> None:
    state = supplier_attachment_state
    assert state.attached[0].xyz == state.mapped_points[0].xyz
    assert state.attached[0].token != state.mapped_points[0].token
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    capture = state.captures[0]
    assert capture["exception"] is refused.value
    context = capture["attachment_context"]
    assert context["attachment_correspondence"]["proven"] is False
    assert "_failure_native_objects" not in context["attachment_correspondence"]
    batch = context["failure_native_readback"]
    assert "read_error" not in batch
    assert batch["context"]["drawing_edit_sheet"] is True
    assert batch["context"]["view_name"] == "SupplierStock"
    assert len(batch["predicate_inventory"]["source"]) == 6
    assert len(batch["predicate_inventory"]["mapped"]) == 6
    assert batch["predicate_inventory"]["uncaptured_kinds"]["10"]["status"] == "unavailable"
    assert {
        id(point) for point in state.id_read_objects
    } == set(state.predicate_point_objects)
    assert all(point.generation == 1 for point in state.id_read_objects)
    assert state.private_cache == {}
    point = batch["predicate_inventory"]["source"][0]
    assert point["id"] == [0, 1]
    assert point["xyz_native_m"] == {"X": 0.0, "Y": 0.004, "Z": 0.0}
    assert point["sketch_owner"]["is_same"]["source"] == {
        "left_to_right": 1, "right_to_left": 1,
    }
    comparison = next(
        row for row in batch["member_comparisons"]
        if row["left"] == "mapped:11:0" and row["right"] == "attached:0"
    )
    assert comparison["is_same"] == {"left_to_right": 0, "right_to_left": 0}
    assert comparison["sketch_owner_is_same"] == {"left_to_right": 1, "right_to_left": 1}
    assert batch["native_dimension"]["system_values"] == [0.600]
    assert batch["native_dimension"]["driven_state"] == 2
    assert state.source_sketch.inventory_reads == {11: 1, 10: 0}
    assert set(state.mapping_reads.values()) == {1}
    assert state.attachment_reads == ["entities", "types"]
    logged = json.loads(state.messages[0].split(": ", 1)[1])
    assert logged == json.loads(json.dumps(context, allow_nan=False))


@pytest.mark.parametrize("getter_fails", [False, True])
def test_supplier_attachment_failure_early_binds_actual_source_feature_type(
    supplier_attachment_state, monkeypatch, getter_fails,
) -> None:
    """Late dispatch can expose the no-argument method as an already-read string."""
    state = supplier_attachment_state
    raw_feature = supplier_dimensions._assert_dimension_source()
    raw_feature.GetTypeName2 = "ProfileFeature"
    original_early_bound = supplier_dimensions._early_bound

    def feature_type():
        if getter_fails:
            raise OSError("typed feature type getter failed")
        return "ProfileFeature"

    bound_feature = SimpleNamespace(
        token=raw_feature.token,
        Name=raw_feature.Name,
        GetSpecificFeature2=raw_feature.GetSpecificFeature2,
        GetTypeName2=feature_type,
    )

    def early_bound(value, interface):
        if value is raw_feature and interface == "IFeature":
            return bound_feature
        return original_early_bound(value, interface)

    monkeypatch.setattr(supplier_dimensions, "_early_bound", early_bound)
    with pytest.raises(
        RuntimeError, match="nominal supplier attachment changed source sketch",
    ) as refused:
        state.verify()
    capture = state.captures[0]
    assert capture["exception"] is refused.value
    batch = capture["attachment_context"]["failure_native_readback"]
    actual_type = batch["context"]["source_feature_type"]
    if getter_fails:
        assert actual_type == {
            "member": "IFeature.GetTypeName2",
            "error_type": "OSError",
            "message": "typed feature type getter failed",
        }
    else:
        assert actual_type == "ProfileFeature"
    assert batch["attachments"]["members"][0]["id"] == [0, 1]
    assert batch["native_dimension"]["system_values"] == [0.600]
    assert state.source_sketch.inventory_reads == {11: 1, 10: 0}
    assert set(state.mapping_reads.values()) == {1}
    assert state.attachment_reads == ["entities", "types"]
    assert state.private_cache == {}


@pytest.mark.parametrize(
    "member,fault,field",
    [
        ("GetID", RuntimeError("native ID read failed"), "id"),
        ("GetID", AttributeError("GetID is unavailable"), "id"),
        ("X", math.nan, "xyz_native_m"),
        ("GetSketch", RuntimeError("owner read failed"), "sketch_owner"),
    ],
)
def test_supplier_attachment_optional_getter_failure_keeps_refusal_and_other_fields(
    supplier_attachment_state, member, fault, field,
) -> None:
    state = supplier_attachment_state
    state.faults[("source-0", member)] = fault
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    assert state.captures[0]["exception"] is refused.value
    batch = state.captures[0]["attachment_context"]["failure_native_readback"]
    assert "read_error" not in batch
    first = batch["predicate_inventory"]["source"][0]
    failed_field = first[field]["X"] if member == "X" else first[field]
    assert failed_field["member"] == f"ISketchPoint.{member}"
    assert "error_type" in failed_field
    assert first["xyz_native_m"]["Y"] == 0.004
    assert batch["predicate_inventory"]["mapped"][0]["id"] == [0, 1]
    assert batch["attachments"]["members"][0]["id"] == [0, 1]
    assert batch["native_dimension"]["driven_state"] == 2
    json.dumps(batch, allow_nan=False)
    assert state.private_cache == {}


@pytest.mark.parametrize("fault", ["logging", "capture_and_warning"])
def test_supplier_attachment_diagnostic_delivery_failure_preserves_original_refusal(
    supplier_attachment_state, fault,
) -> None:
    state = supplier_attachment_state
    if fault == "logging":
        state.log_fault = OSError("diagnostic log sink failed")
    else:
        state.capture_fault = OSError("forensic capture failed")
        state.warning_fault = OSError("warning sink failed")
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    capture = state.captures[0]
    assert capture["exception"] is refused.value
    assert capture["attachment_context"]["failure_native_readback"]["native_dimension"]["driven_state"] == 2
    assert state.private_cache == {}
    if fault == "logging":
        assert capture["attachment_context"]["diagnostic_log_error"]["error_type"] == "OSError"
    else:
        assert len(state.warnings) == 1


def test_supplier_attachment_success_does_not_read_failure_diagnostics(
    supplier_attachment_state,
) -> None:
    state = supplier_attachment_state
    state.attached = (state.mapped_points[0], state.mapped_points[5])
    state.faults[("source-0", "GetID")] = AssertionError("failure-only getter was read on success")
    state.verify()
    assert state.reads == []
    assert state.captures == []
    assert len(state.messages) == 1
    assert state.messages[0].startswith("supplier_source_attachment_proof ")
    assert state.private_cache is None
    assert "_failure_native_objects" not in state.returned_proof


def test_supplier_attachment_cached_segments_keep_independent_endpoint_and_flag_fields(
    supplier_attachment_state,
) -> None:
    state = supplier_attachment_state
    state.kind = 10
    state.mapping = dict(zip(
        (segment.token for segment in state.source_segments), state.mapped_segments, strict=True,
    ))
    state.attached = [
        state.segment_type("attached-line", 0, state.mapped_segments[0].endpoints, state.view_sketch),
    ]
    state.faults[("source-line-0", "GetStartPoint2")] = OSError("start point getter failed")
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    assert state.captures[0]["exception"] is refused.value
    batch = state.captures[0]["attachment_context"]["failure_native_readback"]
    first = batch["predicate_inventory"]["source"][0]
    assert first["construction"] is True
    assert first["start"]["native"]["member"] == "ISketchLine.GetStartPoint2"
    assert first["start"]["native"]["error_type"] == "OSError"
    assert first["end"]["id"] == [1, 1]
    assert first["end"]["xyz_native_m"] == {"X": 0.002, "Y": 0.004, "Z": 0.0}
    assert batch["predicate_inventory"]["mapped"][0]["start"]["id"] == [0, 1]
    assert state.source_sketch.inventory_reads == {11: 0, 10: 1}
    assert set(state.mapping_reads.values()) == {1}
    assert batch["native_dimension"]["driven_state"] == 2


def test_supplier_attachment_readback_records_both_native_comparison_directions(
    supplier_attachment_state,
) -> None:
    state = supplier_attachment_state
    ordinary_same = state.adapter.swApp.IsSame

    def asymmetric_same(left, right):
        if left.token == "mapped-0" and right.token == "attached-0":
            return 2  # Unsupported only in this direction; never an acceptance shortcut.
        return ordinary_same(left, right)

    state.adapter.swApp.IsSame = asymmetric_same
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch"):
        state.verify()
    batch = state.captures[0]["attachment_context"]["failure_native_readback"]
    comparison = next(
        row for row in batch["member_comparisons"]
        if row["left"] == "mapped:11:0" and row["right"] == "attached:0"
    )
    assert comparison["is_same"] == {"left_to_right": 2, "right_to_left": 0}


@pytest.mark.parametrize("full_name", [None, object()])
def test_supplier_attachment_non_json_scalar_is_labelled_without_hiding_refusal(
    supplier_attachment_state, full_name,
) -> None:
    state = supplier_attachment_state
    state.native_dimension.FullName = full_name
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    capture = state.captures[0]
    assert capture["exception"] is refused.value
    batch = capture["attachment_context"]["failure_native_readback"]
    identity = batch["native_dimension"]["full_name"]
    assert identity["member"] == "IDimension.FullName"
    assert "error_type" in identity
    assert batch["native_dimension"]["system_values"] == [0.600]
    assert batch["attachments"]["members"][0]["id"] == [0, 1]
    assert state.private_cache == {}
    json.dumps(capture["attachment_context"], allow_nan=False)


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        (None, None),
        ("name", "invalid, duplicate or unexpected machining control name"),
        ("nominal", "native dimension nominal changed"),
    ],
)
def test_untyped_native_annotation_keeps_control_identity_and_value_guards(
    monkeypatch, fault, message
) -> None:
    """A dynamic property result is not the generated zero-argument method."""
    name = "CutLength"
    nominal, lower, upper = draw.EXPECTED_CONTROLS[name]
    dimension = SimpleNamespace(
        Name=name if fault != "name" else "UnrelatedControl",
        DrivenState=2,
        SystemValue=nominal + (0.001 if fault == "nominal" else 0.0),
        Tolerance=SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda: lower,
            GetMaxValue=lambda: upper,
        ),
    )
    display = SimpleNamespace(
        GetDimension2=lambda _configuration: dimension,
        GetText=lambda _index: "",
        GetPrimaryPrecision2=lambda: spec.DIMENSION_PRECISION[name],
    )

    class SpecificDispatch:
        def __init__(self, specific):
            self.specific = specific

        def __call__(self):
            raise RuntimeError("returned dispatch has no default member")

    class DynamicAnnotation:
        def __init__(self, specific):
            self.specific = specific

        @property
        def GetSpecificAnnotation(self):
            # Dynamic attribute lookup has already invoked the property.
            return SpecificDispatch(self.specific)

    class TypedAnnotation:
        def __init__(self, specific):
            self.specific = specific

        def GetSpecificAnnotation(self):
            return self.specific

    def early_bound(value, interface):
        if isinstance(value, DynamicAnnotation):
            if interface != "IAnnotation":
                raise TypeError("native annotation requires IAnnotation")
            return TypedAnnotation(value.specific)
        return value

    annotation = DynamicAnnotation(display)
    with pytest.raises(RuntimeError, match="no default member"):
        annotation.GetSpecificAnnotation()
    monkeypatch.setattr(trim_drawing, "_early_bound", early_bound)

    def verify():
        trim_drawing.verify_machining_controls(
            [annotation],
            expected={name: (nominal, lower, upper)},
            tolerance_types=spec.DIMENSION_TOLERANCE_TYPES,
            precision=spec.DIMENSION_PRECISION,
        )

    if fault is None:
        verify()
    else:
        with pytest.raises(RuntimeError, match=message):
            verify()


def _source_view(*, shown: str, active: str) -> SimpleNamespace:
    """A drawing view whose source part is active in ``active``."""
    document = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name=active)
        )
    )
    return SimpleNamespace(ReferencedConfiguration=shown, ReferencedDocument=document)


def test_supplier_references_are_proven_only_in_the_active_source_member(monkeypatch):
    # Farm run 20261104T222143958Z: the FeedNut supplier references were
    # imported into a FeedNut view while the part was active in its saved
    # LeadScrew default; every attachment failed IsSame against the source
    # sketch. The member that carries supplier references is the one the
    # source is activated in, and it is not the saved default.
    member = draw.SUPPLIER_REFERENCE_CONFIGURATION
    default = _config.parts(spec.PART_NAME)["default_configuration"]
    assert member == nut.CONFIGURATION != default
    assert member in dict(draw.VARIANTS)
    # The LeadScrew member carries none, so it needs no source transition.
    assert draw.annotate_member(None, default, (), []) == ()

    draw.require_source_configuration(None, _source_view(shown=member, active=member), member)
    with pytest.raises(RuntimeError, match=f"active in '{default}'"):
        draw.require_source_configuration(
            None, _source_view(shown=member, active=default), member
        )
    with pytest.raises(RuntimeError, match="another member"):
        draw.require_source_configuration(
            None, _source_view(shown=default, active=member), member
        )

    def imported(*_args, **_kwargs):
        raise AssertionError("supplier references imported against the wrong member")

    monkeypatch.setattr(draw, "annotate_supplier_screw", imported)
    cells = tuple(
        (name, (0.0, 0.0), (0.0, 0.0, 1.0, 1.0))
        for name in ("*Front", "*Top", "*Right", "*Isometric")
    )
    views = [_source_view(shown=member, active=default) for _ in cells]
    with pytest.raises(RuntimeError, match=f"active in '{default}'"):
        draw.annotate_member(None, member, cells, views)


def test_build_activates_the_nut_and_shows_the_leadscrew_as_its_isometric(
    monkeypatch,
):
    captured = {}

    async def capture(_adapter, _spec, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(draw, "build_purchased_variant_drawing", capture)
    asyncio.run(draw.build(None))
    # The shared builder activates this member in the read-only source before
    # the drawing exists and requires it in every source check.
    assert captured["source_configuration"] == draw.SUPPLIER_REFERENCE_CONFIGURATION
    # The screw (sheet 2 draws it) shows only its isometric; the nut, which
    # carries the supplier references on its four views, is not isometric-only.
    assert captured["isometric_only"] == {spec.CONFIGURATION: 2}
    assert draw.SUPPLIER_REFERENCE_CONFIGURATION not in captured["isometric_only"]
    assert set(captured["additional_sheet_scales"]) == set(draw.SHEET_NAMES)


def _floor2(value: float) -> str:
    return f"{math.floor(value * 100.0 + 1e-9) / 100.0:.2f}"


def test_countersink_walls_are_the_worst_case_the_package_allows() -> None:
    # Every allowance a MIN must cover (4475311242, 4475311247): the hole off
    # station (receipt band), the countersink off the hole, the mouth at its
    # band's Ø4.76 maximum (all F2 may open it to), the body at its receipt
    # maximum and the flange at its receipt minimum.
    shift = nut.HOLE_STATION_BAND + nut.CSK_ECCENTRICITY_MAX
    assert (nut.HOLE_STATION_BAND, nut.CSK_ECCENTRICITY_MAX) == (0.05, 0.02)
    mouth = nut.CSK_DIA_MAX
    assert mouth == 4.76 == round(nut.CSK_DIA + nut.REWORK_CONTROLS["CskDia"][2], 6)
    assert nut.BODY_DIA_MAX == 10.3 and nut.FLANGE_DIA_MIN == 21.8
    assert nut.CSK_WALL_TO_BODY == pytest.approx(
        nut.HOLE_PCD / 2.0 - shift - mouth / 2.0 - nut.BODY_DIA_MAX / 2.0
    ) == pytest.approx(0.40)
    assert nut.CSK_WALL_TO_OD == pytest.approx(
        nut.FLANGE_DIA_MIN / 2.0 - nut.HOLE_PCD / 2.0 - shift - mouth / 2.0
    ) == pytest.approx(0.45)
    # Thinner than at the modelled mouth with everything nominal.
    assert nut.CSK_WALL_TO_BODY < nut.HOLE_PCD / 2.0 - nut.CSK_DIA / 2.0 - nut.BODY_DIA / 2.0
    assert nut.CSK_WALL_TO_OD < nut.FLANGE_DIA / 2.0 - nut.HOLE_PCD / 2.0 - nut.CSK_DIA / 2.0
    assert 0.0 < nut.CSK_WALL_TO_BODY < nut.CSK_WALL_TO_OD < nut.WALL_FLOOR == 1.5
    # The supplied holes alone already miss the floor, nominal and at receipt.
    assert nut.HOLE_WALL_TO_BODY == pytest.approx(1.15)
    assert nut.HOLE_WALL_TO_OD == pytest.approx(1.25)
    assert nut.HOLE_WALL_TO_BODY_MIN == pytest.approx(
        nut.HOLE_PCD / 2.0 - nut.HOLE_STATION_BAND - nut.HOLE_DIA_MAX / 2.0 - nut.BODY_DIA_MAX / 2.0
    ) == pytest.approx(1.00)
    assert nut.HOLE_WALL_TO_OD_MIN == pytest.approx(
        nut.FLANGE_DIA_MIN / 2.0 - nut.HOLE_PCD / 2.0 - nut.HOLE_STATION_BAND
        - nut.HOLE_DIA_MAX / 2.0
    ) == pytest.approx(1.05)
    assert max(nut.HOLE_WALL_TO_BODY, nut.HOLE_WALL_TO_OD) < nut.WALL_FLOOR
    # Printed rounded down, so a MIN never overstates the wall.
    for printed, wall in zip(
        re.findall(r"\d+\.\d\d", nut.CSK_WALL_TEXT),
        (nut.CSK_WALL_TO_BODY, nut.CSK_WALL_TO_OD),
        strict=True,
    ):
        assert wall - 0.01 < float(printed) <= wall + 1e-9
    # The countersink's callout carries it as its last line.
    assert draw.CSK_SCREW_CALLOUT.splitlines()[-1] == nut.CSK_WALL_TEXT


def test_countersink_wall_shortfall_is_a_declared_owner_ruled_minor() -> None:
    """A printed shortfall with no declaration gates the machinist review."""
    import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
    from machinist_exceptions import load_exceptions

    wall, _thread, _faced = load_exceptions(_config.CONFIG_DIR, draw.PART_STEM, "part")
    assert (wall.id, wall.kind) == ("RV-01", "minor")
    # "where" quotes the printed callout: the prefix's countersink symbol and
    # Ø token as printed, the band, the angle suffix and the wall line,
    # exactly. LIMIT prints the maximum over the minimum at the band's two
    # places.
    symbols = nut.CSK_PREFIX.replace("<HOLE-SINK>", "⌵ ").replace("<MOD-DIAM>", "Ø")
    printed = f"{symbols}{nut.CSK_DIA_MAX:.2f}/{nut.CSK_DIA_MIN:.2f}{nut.CSK_SUFFIX}"
    assert printed == "4X ⌵ Ø4.76/4.50 X 82°"
    label = draw.REWORK_SECTION_LABEL
    assert wall.where == (
        f"sheet {nut.REWORK_SHEET}, Section {label}-{label}, the {printed} callout: "
        f"{nut.CSK_WALL_TEXT}"
    )
    worst = (
        f"each hole ±{nut.HOLE_STATION_BAND:.2f} off its station on the "
        f"Ø{nut.HOLE_PCD:.0f} PCD, the countersink {nut.CSK_ECCENTRICITY_MAX:.2f} off "
        f"its hole, the mouth at its Ø{nut.CSK_DIA_MAX:.2f} band maximum, the "
        f"body at its Ø{nut.BODY_DIA_MAX:.1f} receipt maximum, the flange at its "
        f"Ø{nut.FLANGE_DIA_MIN:.1f} receipt minimum"
    )
    assert f"({worst})" in wall.finding
    assert (
        f"leave {_floor2(nut.CSK_WALL_TO_BODY)} mm to the body and "
        f"{_floor2(nut.CSK_WALL_TO_OD)} mm to the flange OD, "
        f"below the {nut.WALL_FLOOR:.1f} mm metric wall floor"
    ) in wall.finding
    # The owner's ruling must cover the walls the package declares, no thinner.
    assert wall.reason.startswith("owner ruling 2026-11-04 (Pedro, PR #2187 comment ")
    assert (
        f"{_floor2(nut.CSK_WALL_TO_BODY)} mm (to body) / "
        f"{_floor2(nut.CSK_WALL_TO_OD)} mm (to flange OD) walls"
    ) in wall.reason
    assert (
        f"Ø{nut.HOLE_DIA:.1f} holes on the Ø{nut.HOLE_PCD:.0f} PCD already leave "
        f"{nut.HOLE_WALL_TO_BODY:.2f} mm to the body and {nut.HOLE_WALL_TO_OD:.2f} mm "
        f"to the OD nominal, {_floor2(nut.HOLE_WALL_TO_BODY_MIN)} mm and "
        f"{_floor2(nut.HOLE_WALL_TO_OD_MIN)} mm at the receipt limits"
    ) in wall.reason
    # The load facts are the jig spec's nut-stop numbers.
    assert (
        f"({nut.SCREW_SKU}) takes {jig.NUT_STOP_FORCE_N:.0f} N at the "
        f"{jig.NUT_TORQUE_NM:.2f} N·m reversing torque, ×{jig.NUT_STOP_MARGIN:.1f} in shear"
    ) in wall.reason


def test_thread_body_wall_is_the_real_thread_at_the_least_body() -> None:
    """4476701302: the Ø6 bore models the thread's minor; the real Tr8x2
    internal thread's major is D4 = d + 2 ac (ISO 2904, ac 0.25 at P2), and
    the body at its receipt minimum leaves the printed MIN under the floor."""
    assert spec.MAJOR_DIA == 8.0 and nut.LEAD == 2.0
    assert nut.THREAD_MAJOR_DIA == spec.MAJOR_DIA + 2.0 * 0.25 == 8.5
    assert nut.BORE_DIA == spec.MAJOR_DIA - nut.LEAD  # D1 = d - P, the model's bore
    assert nut.THREAD_BODY_WALL_MIN == pytest.approx(
        (nut.BODY_DIA_MIN - nut.THREAD_MAJOR_DIA) / 2.0
    ) == pytest.approx(0.75)
    assert nut.THREAD_BODY_WALL_MIN < (nut.BODY_DIA - nut.THREAD_MAJOR_DIA) / 2.0 < nut.WALL_FLOOR
    assert nut.THREAD_WALL_TEXT == f"MIN WALL {_floor2(nut.THREAD_BODY_WALL_MIN)} TO THREAD"
    assert nut.THREAD_WALL_TEXT == "MIN WALL 0.75 TO THREAD"
    # The body's callout carries it as its last line.
    assert draw.RECEIPT_CALLOUTS["ReceiptBodyDia"][1].splitlines()[-1] == nut.THREAD_WALL_TEXT


def test_thread_wall_shortfall_is_a_declared_owner_ruled_minor() -> None:
    """RV-02, on RV-01's pattern: where quotes the printed callout, finding
    the worst case, reason the owner's ruling and the load facts."""
    import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
    from machinist_exceptions import load_exceptions

    csk, wall, _faced = load_exceptions(_config.CONFIG_DIR, draw.PART_STEM, "part")
    assert (wall.id, wall.kind) == ("RV-02", "minor")
    _nominal, lower, upper, places = nut.RECEIPT_CONTROLS["ReceiptBodyDia"]
    assert nut.DIMENSION_TOLERANCE_TYPES["ReceiptBodyDia"] == nut.TOL_LIMIT
    printed = f"Ø{nut.BODY_DIA_MAX:.{places}f}/{nut.BODY_DIA_MIN:.{places}f}"
    assert printed == "Ø10.3/10.0"
    assert wall.where == (
        f"sheet {nut.REWORK_SHEET}, the end view, the {printed} body callout: "
        f"{nut.THREAD_WALL_TEXT}"
    )
    assert (
        f"Ø{nut.THREAD_MAJOR_DIA:.1f} major ({spec.MAJOR_DIA:.0f} + 2 × "
        f"{nut.TR_CREST_CLEARANCE:.2f} crest clearance, ISO 2904) inside the body at "
        f"its Ø{nut.BODY_DIA_MIN:.1f} receipt minimum, concentric, leaves "
        f"{_floor2(nut.THREAD_BODY_WALL_MIN)} mm"
    ) in wall.finding
    assert f"below the {nut.WALL_FLOOR:.1f} mm metric wall floor" in wall.finding
    # The same owner ruling as RV-01, covering exactly the declared wall.
    opening = csk.reason.split('"Accept as owner exception"')[0]
    assert opening.startswith("owner ruling 2026-11-04 (Pedro, PR #2187 comment ")
    assert wall.reason.startswith(opening + '"Accept as owner exception"')
    assert f"{_floor2(nut.THREAD_BODY_WALL_MIN)} mm thread-to-body wall" in wall.reason
    assert "a supplied, unmachined feature of the bought nut" in wall.reason
    assert f"Ø{nut.BODY_DIA:.1f} body leaves {_floor2((nut.BODY_DIA - nut.THREAD_MAJOR_DIA) / 2.0)} mm" in wall.reason
    # The load facts are the jig spec's nut-thrust numbers.
    assert (
        f"carries the {jig.NUT_THRUST_N:.0f} N largest nut thrust axially from the thread "
        f"into the flange"
    ) in wall.reason
    assert (
        f"{jig.NUT_BODY_WALL_MPA:.0f} MPa on the bare annulus, teeth not credited, "
        f"×{jig.NUT_BODY_WALL_MARGIN:.1f} under the brass's "
        f"{jig._BRASS_YIELD_MPA:.0f} MPa yield"
    ) in wall.reason


def test_feed_nut_full_thread_shortfall_is_the_owner_ruled_rv03() -> None:
    """Codjiflo 4483623010 (rule 18): the faced length is bounded both ways,
    and the shortest faced nut, less the body end's incomplete threads, holds
    five Tr8 turns: under 1.5 D, declared as RV-03 on the owner's ruling."""
    from machinist_exceptions import load_exceptions

    *_walls, faced = load_exceptions(_config.CONFIG_DIR, draw.PART_STEM, "part")
    assert (faced.id, faced.kind) == ("RV-03", "minor")
    assert nut.FULL_THREAD_MIN == pytest.approx(nut.LENGTH_MIN - 1.5 * nut.LEAD) == pytest.approx(10.2)
    assert 5.0 * nut.LEAD <= nut.FULL_THREAD_MIN < 1.5 * spec.MAJOR_DIA
    # Negative control: a nut faced 0.3 under the limit holds under five turns.
    assert (nut.LENGTH_MIN - 0.3) - 1.5 * nut.LEAD < 5.0 * nut.LEAD
    label = draw.REWORK_SECTION_LABEL
    printed = f"{nut.LENGTH_MAX:.1f}/{nut.LENGTH_MIN:.1f}"
    assert faced.where == (
        f"sheet {nut.REWORK_SHEET}, Section {label}-{label}, the faced length {printed}"
    )
    assert f"holds {nut.FULL_THREAD_MIN:.1f} mm of full Tr8x2 thread" in faced.finding
    assert f"1.5D ({1.5 * spec.MAJOR_DIA:.1f})" in faced.finding
    assert faced.reason.startswith(
        "owner ruling 2026-11-05 (Pedro, recorded in PR #2187 comment 6665347496"
    )
    assert "consistent with ruling A1 (a517a1cd3f)" in faced.reason
