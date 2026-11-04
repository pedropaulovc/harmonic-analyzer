"""Offline contracts for the cone gears' dividing-head index plate (MHA-DT-03-TL-01)."""

from __future__ import annotations

import ast
import inspect
import math

import _config
import build_dt_cone_gear_tl_index_plate as part
import dt_cone_gear_tl_index_plate_spec as spec
import draw_dt_cone_gear_tl_index_plate as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

INCH = 25.4


def test_each_circle_indexes_its_cone_gear_on_the_40_to_1_head() -> None:
    assert spec.WORM_RATIO == 40
    assert sorted(spec.RING_TEETH.values()) == sorted(spec.GEAR_TEETH) == [96, 102, 114]
    advances = {
        circle: spec.holes_per_tooth(teeth, circle)
        for circle, teeth in spec.RING_TEETH.items()
    }
    assert advances == {57: 20.0, 51: 20.0, 24: 10.0}
    assert spec.HOLE_COUNT == 132 == sum(spec.RING_COUNTS)


def test_no_stock_bs0_plate_indexes_these_gears() -> None:
    stock = (15, 16, 17, 18, 19, 20, 21, 23, 27, 29, 31, 33, 37, 39, 41, 43, 47, 49)
    # 40/96 = 5/12, 40/102 = 20/51 and 40/114 = 20/57 need circles divisible
    # by 12, 51 and 57; no stock circle is.
    for teeth in (96, 102, 114):
        assert not any(
            spec.holes_per_tooth(teeth, circle).is_integer() for circle in stock
        ), teeth


def test_the_model_globals_are_the_spec_sizes() -> None:
    g = spec.GLOBALS
    assert (g["PlateDia"], g["BoreDia"], g["PlateThick"]) == (
        spec.PLATE_DIA,
        spec.BORE_DIA,
        spec.THICKNESS,
    )
    assert {n: g[f"Ring{n}Pcd"] for n in spec.RING_COUNTS} == spec.RING_PCDS
    assert g["IndexHoleDia"] == spec.INDEX_HOLE_DIA
    assert (g["MountPcd"], g["MountHoleDia"], g["CskDia"]) == (
        spec.MOUNT_PCD,
        spec.MOUNT_HOLE_DIA,
        spec.CSK_DIA,
    )
    assert math.isclose(math.hypot(*spec.MOUNT_SEED), spec.MOUNT_PCD / 2.0)
    assert spec.MOUNT_SEED[0] < 0.0 < spec.MOUNT_SEED[1]


def test_every_guess_cites_the_tracking_issue() -> None:
    source = inspect.getsource(spec)
    assert "issues/2157" in spec.TRACKING_ISSUE
    for name in (
        "PLATE_DIA",
        "BORE_DIA",
        "THICKNESS",
        "INDEX_HOLE_DIA",
        "MOUNT_PCD",
        "MOUNT_SCREW",
        "CSK_DIA",
    ):
        line = next(row for row in source.splitlines() if row.startswith(f"{name} = "))
        assert "# GUESS (#2157)" in line, name
    for count in spec.RING_COUNTS:
        line = next(
            row for row in source.splitlines() if row.lstrip().startswith(f"{count}: ")
        )
        assert "# GUESS (#2157)" in line, count


def test_registry_row_is_tooling_in_inch() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == "MHA-DT-03-TL-01"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    entry = DRAWINGS_BY_NAME["dt_cone_gear_tl_index_plate"]
    assert entry.artifact_stem == spec.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"


def test_only_the_bore_carries_a_model_band() -> None:
    bands = model_toleranced_dimensions(part)
    assert set(bands) == {("PlateProfile", "BoreDia")}
    assert spec.BORE_DEVIATIONS == (0.0, 0.003 * INCH)


def test_machinist_review_is_off_while_the_sizes_are_guesses() -> None:
    tree = ast.parse(inspect.getsource(drawing))
    assigned = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "MACHINIST_REVIEW" not in assigned


def test_the_sheet_states_the_web_shortfall_it_carries() -> None:
    assert spec.SHORT_WEBS <= set(spec.WEBS_MM)
    shortest = min(spec.WEBS_MM[name] for name in spec.SHORT_WEBS)
    assert shortest == spec.WEB_MIN_MM
    assert spec.WEB_MIN_PRINTED * INCH <= spec.WEB_MIN_MM
    assert spec.WEB_CALLOUT == "WEB .03 MIN"
    assert spec.CALLOUTS_BELOW[spec.PRINTED_HOLE].endswith(spec.WEB_CALLOUT)


def test_callouts_name_counts_and_the_countersink() -> None:
    assert spec.CALLOUTS_ABOVE[spec.PRINTED_HOLE] == "132X"
    assert spec.CALLOUTS_ABOVE["Ring57Pcd"] == "57X EQ SP ON"
    assert spec.CALLOUTS_ABOVE["MountHoleDia"] == "3X"
    assert spec.CALLOUTS_BELOW["MountHoleDia"].split("\n")[:2] == [
        "DRILL THRU",
        "CSK<MOD-DIAM>.35 X 82°",
    ]
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.CALLOUTS_ABOVE) <= marked
    assert set(spec.CALLOUTS_BELOW) <= marked
    assert set(drawing.FACE_KEEP) | set(drawing.EDGE_KEEP) == marked


def test_the_flat_head_sinks_and_the_countersink_stays_in_the_plate() -> None:
    xx = 0.01 * INCH
    assert spec.CSK_DIA - xx >= spec.MOUNT_HEAD_DIA_MAX
    assert spec.CSK_DEPTH_MAX < spec.THICKNESS - xx
    assert spec.MOUNT_HOLE_DIA > spec.MOUNT_SCREW_BODY_DIA


def test_the_build_volume_budget_counts_every_hole() -> None:
    holes = sum(spec.RING_COUNTS) * part.V_INDEX_HOLE
    mounts = spec.MOUNT_COUNT * (part.V_MOUNT_HOLE + part.V_CSK)
    assert math.isclose(part.V_FINISHED, part.V_PLATE - holes - mounts)
    assert part.V_CSK > 0.0


def test_builder_declares_the_spec_part_name() -> None:
    assert part.PART_NAME == spec.PART_NAME


def test_the_indexing_kit_holds_the_plate_and_tables_each_gear() -> None:
    import _buildgraph as bg
    import draw_dt_cone_gear_tl_indexing_assembly as kit

    assert "dt_cone_gear_tl_index_plate" in bg.references_of("dt_cone_gear_tl_indexing")
    assert "dt_cone_gear_tl_indexing" not in bg.MACHINE_ASSEMBLIES
    assert kit.DRAWING_NUMBER == "MHA-DT-03-TL-00"
    assert kit.INDEXING_TABLE.splitlines()[1:] == [
        "96T: 10 HOLE SPACES ON THE 24-HOLE CIRCLE",
        "102T: 20 HOLE SPACES ON THE 51-HOLE CIRCLE",
        "114T: 20 HOLE SPACES ON THE 57-HOLE CIRCLE",
    ]
