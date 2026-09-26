"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import rocker_arm_notes
import rocker_arm_spec
import draw_rocker_arm as drawing
import build_rocker_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME
from cone_pivot_post_installation import MECHANISM_X_SHIFT
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*rocker_arm_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept | drawing.NOTE_ONLY_DIMENSIONS == marked


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        rocker_arm_spec.ROD_HOLE_X,
        rocker_arm_spec.TOP_END_Y,
    )
    assert rocker_arm_spec.CURVE_RADIUS == arm.CURVE_RADIUS
    assert rocker_arm_spec.ARM_DEPTH == arm.ARM_DEPTH
    assert rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X
    assert arm.ROD_HOLE_SPEC is rocker_arm_spec.ROD_HOLE_SPEC
    assert drawing._ROD_HOLE_DIA == blind_cut_dia_mm(rocker_arm_spec.ROD_HOLE_SPEC)


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        rocker_arm_spec.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(rocker_arm_spec.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)
    assert rocker_arm_spec.ROD_HOLE_ABOVE_BOTTOM == arm.ROD_HOLE_ABOVE_BOTTOM
    assert rocker_arm_spec.ROD_HOLE_Y == arm.ROD_HOLE_Y


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_metric_and_not_title_block_duplicates() -> None:
    notes = rocker_arm_notes.DRAWING_NOTES
    assert "R800" in notes
    assert "R816" in notes
    # The rod hole rides its native Ø1.99 THRU ALL callout; the notes state
    # count and process only, never a second copy of a sheet dimension.
    assert "(1X)" in notes
    assert "#47" not in notes
    assert "REAM +0.03/0" in notes
    assert "16.00 REF" in notes
    assert "11.5 IN" not in notes
    assert "0.22 IN" not in notes
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert re.search(
        r'add_property_linked_note\(\s*adapter, "Manufacturing Notes"', source
    )


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = pivot bore axis, B = broad face (right end view), C = rod-side tip
    # face; the rod-pin position frame references all three.
    assert source.count("add_datum_feature(") == 3
    assert "pivot_datum_angle = math.radians(135.0)" in source
    assert 'label="pivot bore cylindrical datum feature"' in source
    assert source.count("shoulder=True") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'datums=("A", "B", "C")' in source
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "add_native_hole_callout(" in source
    # r743-p1s-B: both rod-pin annotations take the diameter-picked edge.
    assert "edge_xy=rod_rim" not in source
    assert source.count("edge=rod_hole_edge") == 1
    assert source.count("edge_entity=rod_hole_edge") == 1


def test_large_radius_values_are_note_only() -> None:
    assert drawing.NOTE_ONLY_DIMENSIONS == {"TopRadius", "BottomRadius"}
    assert "R800" in rocker_arm_notes.DRAWING_NOTES
    assert "R816" in rocker_arm_notes.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("rocker-arm")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = rocker_arm_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == rocker_arm_spec.PIVOT_HOLE_DIA
    assert arm.PIVOT_HOLE_DIA == rocker_arm_spec.PIVOT_HOLE_DIA
    part_source = "".join(Path(arm.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"pivot_bore")' in sheet_source
    )
    assert "roughness_ra=" not in sheet_source


def test_every_view_keep_map_is_curated_on_its_own_view() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRk__): RIGHT_KEEP promised HubLength but
    build() curated only the front view, so the hub length never printed. Each
    non-empty <VIEW>_KEEP must be curated on that view, and curation fails
    loud on a missing kept dimension, so the print carries every one."""
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    curated = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "curate_view_dimensions"
        ):
            continue
        keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
        curated[keywords["keep"]] = (ast.unparse(node.args[1]), keywords)
    for keep_name, view in (
        ("FRONT_KEEP", "front"),
        ("RIGHT_KEEP", "right"),
        ("TOP_KEEP", "top"),
    ):
        if not getattr(drawing, keep_name):
            continue
        assert keep_name in curated, keep_name
        assert curated[keep_name][0] == view
    # The end view imports by feature: only Hub's dimensions arrive there.
    assert curated["RIGHT_KEEP"][1]["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert drawing.DRAWING_DIMENSIONS is rocker_arm_notes.DRAWING_DIMENSIONS


def test_hub_length_prints_its_one_sided_band() -> None:
    """#743 PR2: the hubs are a solid stack whose north end is the rocker
    bank's datum, so each hub may only come out long and the print says so
    natively; rocker_bank_layout's L20 acceptance caps the sum."""
    from _drawing_contract import model_toleranced_dimensions

    assert rocker_arm_notes.DRAWING_DIMENSIONS["Hub"] == {"HubLength"}
    assert "HubLength" in drawing.RIGHT_KEEP
    assert model_toleranced_dimensions(arm)[("Hub", "HubLength")] == (
        "*deviations(HUB_LENGTH_BAND)"
    )
    assert rocker_arm_spec.HUB_LENGTH_BAND == (0.05, 0.0)
    assert f"{rocker_arm_spec.HUB_LENGTH:.2f}" not in rocker_arm_notes.DRAWING_NOTES


def test_both_bores_are_picked_by_diameter_not_by_a_rim_coordinate() -> None:
    """r743-p1s-B: a coordinate pick on the #47 rod-hole rim resolved to the
    strap's tapered end-face line, so AddHoleCallout2 returned None. Every
    annotation on the rod-pin hole takes the diameter-picked edge."""
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    picks = {}
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "visible_circle_edge"
            ):
                picks[node.targets[0].id] = ast.unparse(call.args[2])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
            if keywords.get("label", "").startswith("'rod-pin") or keywords.get(
                "label", ""
            ).startswith('"rod-pin'):
                if node.func.id != "set_basic_dimension":
                    uses.append((node.func.id, keywords))
    assert picks == {
        "rod_hole_edge": "_ROD_HOLE_DIA",
        "pivot_bore_edge": "PIVOT_HOLE_DIA",
    }
    kinds = {name for name, _ in uses}
    assert kinds == {
        "add_native_hole_callout",
        "add_edge_dimension",
        "add_feature_control_frame",
    }
    for name, keywords in uses:
        assert "edge_xy" not in keywords, name
        if name == "add_native_hole_callout":
            assert keywords["edge"] == "rod_hole_edge"
        elif name == "add_edge_dimension":
            assert keywords["entities"] == "(pivot_bore_edge, rod_hole_edge)"
        else:
            assert keywords["edge_entity"] == "rod_hole_edge"


# Measured on the r743-p1s-B2 render (5100x3300 px on 431.8x279.4 mm): the
# drawable region ends 12.7 mm above the sheet's bottom edge, the linked
# notes pitch ~4.14 mm a line, and the iso caption runs ~2.5 mm a character.
BORDER_BOTTOM = 0.0127
NOTE_LINE_PITCH = 0.0042
CAPTION_CHAR_WIDTH = 0.0026
RIGHT_BORDER = 0.415


def test_general_notes_are_seated_on_the_border_under_the_front_view() -> None:
    """r743-p1s-B2: anchored by its top at 0.082, the 18-line block ran two
    lines past the bottom border. The build now seats its MEASURED bottom on
    the drawable region and fails if it then reaches the front view's
    annotations; this pins that the block fits that band at all."""
    lines = rocker_arm_notes.DRAWING_NOTES.splitlines()
    bottom = BORDER_BOTTOM + drawing.NOTES_BORDER_CLEARANCE
    assert bottom + len(lines) * NOTE_LINE_PITCH < drawing.NOTES_CEILING - 0.010
    # The old top anchor: the same block reached below the border.
    assert 0.082 - len(lines) * NOTE_LINE_PITCH < BORDER_BOTTOM
    assert drawing.NOTES_CEILING < 0.117  # the front view's O6.50 text
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_seat_notes_on_border(adapter, notes, sheet)" in source
    assert "check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)" in source


def test_iso_caption_sits_under_the_iso_clear_of_the_frame_and_end_view() -> None:
    caption = rocker_arm_notes.ISOMETRIC_VIEW_NOTE
    left, top = drawing.ISO_CAPTION_XY
    right = left + len(caption) * CAPTION_CHAR_WIDTH
    fcf_bottom = drawing.FCF_XY[1] - 0.007
    assert top < fcf_bottom - 0.003
    assert left > drawing.RIGHT_CENTER[0] + 0.015  # the end view and its +0.05
    assert right < RIGHT_BORDER - 0.005
    # Under the iso: the caption's span overlaps the iso's.
    assert left < drawing.ISO_CENTER[0] < right


def test_pivot_finish_is_note_height_with_its_leader_running_down_left() -> None:
    """r743-p1s-B2: the default-height Ra 1.6 sat across the strap and the
    centre mark, its leader running up through the symbol. The body draws
    up-right of its leader end, so the symbol sits up-right of its rim point."""
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    (call,) = (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "add_surface_finish"
    )
    keywords = {k.arg: ast.unparse(k.value) for k in call.keywords}
    assert keywords["char_height"] == "0.0025"
    assert keywords["leader_attach_xy"] == "pivot_finish_rim"
    assert keywords["symbol_xy"] == (
        "(pivot_finish_rim[0] + 0.012, pivot_finish_rim[1] + 0.011)"
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "pivot_finish_angle = math.radians(45.0)" in source
