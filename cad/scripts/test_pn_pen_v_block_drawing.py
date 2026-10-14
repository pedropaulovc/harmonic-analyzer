"""Offline contracts for the pen v-block part and its drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import build_pn_pen_v_block as part
import draw_pn_pen_v_block as drawing
import pn_pen_v_block_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import TAP_DRILL_MM

_PART_SOURCE = Path(part.__file__).read_text(encoding="utf-8")
_DRAWING_SOURCE = Path(drawing.__file__).read_text(encoding="utf-8")
_VIEW_KEEPS = (
    drawing.FRONT_KEEP,
    drawing.RIGHT_KEEP,
    drawing.BOTTOM_KEEP,
    drawing.SECTION_KEEP,
)


def _string_constants(source: str) -> set[str]:
    return {
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-pen-v-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-pen-v-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-pen-v-block_drawing.png")
    assert DRAWINGS_BY_NAME["pn_pen_v_block"].script == Path(drawing.__file__).resolve()


def test_drawing_keeps_exactly_the_marked_dimensions() -> None:
    # The part marks the spec's map and the drawing keeps exactly its union,
    # each dimension in one view only.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = [name for keep in _VIEW_KEEPS for name in keep]
    assert len(kept) == len(set(kept))
    assert set(kept) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.DIMENSION_CALLOUTS is spec.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_CALLOUTS_ABOVE is spec.DIMENSION_CALLOUTS_ABOVE
    assert set(spec.DIMENSION_CALLOUTS) <= marked
    assert set(spec.DIMENSION_CALLOUTS_ABOVE) <= marked
    for feature, name in spec.DIMENSION_PREFIXES:
        assert name in spec.DRAWING_DIMENSIONS[feature]
    for feature, name in spec.DRAWING_BANDS:
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert name in spec.DIMENSION_CALLOUTS


def test_build_authors_every_marked_feature_and_dimension_name() -> None:
    strings = _string_constants(_PART_SOURCE)
    # f-string names (the chamfer legs) are spelled out by the loop's pattern.
    strings |= {f"Chamfer{corner}{leg}" for corner in (2, 4) for leg in ("dx", "dy")}
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        assert feature in strings, feature
        assert names <= strings, (feature, names - strings)
    tree_order = [
        "OutlineProfile",
        "Block",
        "VGrooveProfile",
        "VGroove",
        "ReliefProfile",
        "Relief",
        "PivotBoreProfile",
        "PivotBore",
        "PivotBoreChamfer",
        "SetScrewHole",
        "LighteningBore",
    ]
    positions = [_PART_SOURCE.index(f'"{name}"') for name in tree_order]
    # The reference sketches' helpers sit above build(); their calls come
    # last, the section's after its cutting plane.
    positions.append(_PART_SOURCE.index("await _section_plane(adapter)"))
    positions += [
        _PART_SOURCE.index(f"drive_jobs += await _{helper}_reference(adapter)")
        for helper in ("relief", "pivot", "lightening")
    ]
    # The tap is built after the bore, so its through_next stops at the bore.
    assert positions == sorted(positions)


def test_every_feature_is_located_from_the_front_face() -> None:
    # drawing-guidelines.md rule 10: no feature across the depth by symmetry.
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {"VMouthZ", "ReliefZ0", "PivotZ", "LighteningZ"} <= marked
    assert '"VApexZ"' not in _PART_SOURCE
    assert set(spec.REFERENCE_SKETCHES) <= set(spec.DRAWING_DIMENSIONS)
    for feature in spec.REFERENCE_SKETCHES:
        assert f'"{feature}"' in _PART_SOURCE
    # Hidden only once marked, before the save that the drawing opens.
    marks = _PART_SOURCE.index("mark_dimensions_for_drawing(adapter, feature_name")
    hide = _PART_SOURCE.index("blank_reference_sketches(adapter, REFERENCE_SKETCHES)")
    assert marks < hide < _PART_SOURCE.index("save_part_and_images(adapter")
    assert "segment.ConstructionGeometry = True" in _PART_SOURCE
    # PivotZ's extension line lands on the section's bore-axis centreline.
    # Farm 2229cc4db: InsertCenterLine2 on a picked bore face returned None in
    # this section, so the axis is sketched between projected model points
    # (dt_cone_pivot_post's section recipe), black, CENTER font, read back.
    assert "add_view_centerline" not in _DRAWING_SOURCE
    assert "_add_pivot_axis_centerline(adapter, section)" in _DRAWING_SOURCE
    body = _DRAWING_SOURCE[_DRAWING_SOURCE.index("def _add_pivot_axis_centerline(") :]
    body = body[: body.index("\ndef ")]
    for needle in (
        "model_point_in_view(",
        "PIVOT_BORE_X / 1000.0",
        "_CZ / 1000.0",
        "drawing.EditSheet()",
        "CreateCenterLine(",
        "segment.Style = _SW_LINE_CENTER",
        "GetOutline()",
    ):
        assert needle in body, needle
    # 3 mm past each end on paper.
    assert drawing._CENTERLINE_OVERSHOOT_MM * drawing._S == pytest.approx(0.003)
    # Drawn after the section is cut and curated.
    assert _DRAWING_SOURCE.index("keep=SECTION_KEEP") < _DRAWING_SOURCE.index(
        "_add_pivot_axis_centerline(adapter, section)"
    )


def test_hidden_reference_dimensions_reach_their_views() -> None:
    # Farm e7b8b6928: the plain targeted import delivered none of a hidden
    # sketch's dimensions (LighteningZ missing from the bottom view).  Every
    # view curates through _drawing_hidden_sketches, which shows a hidden
    # owner per view; the section, a derived view, is cut and curated while
    # the part shows its sketches, which lie in its cutting plane.
    assert (
        "from _drawing_hidden_sketches import curate_view_dimensions, "
        "part_sketches_shown" in _DRAWING_SOURCE
    )
    assert "from _drawing_dimension_import import curate_view_dimensions" not in (
        _DRAWING_SOURCE
    )
    assert set(spec.SECTION_REFERENCE_SKETCHES) <= set(spec.REFERENCE_SKETCHES)
    section_names = set().union(
        *(spec.DRAWING_DIMENSIONS[s] for s in spec.SECTION_REFERENCE_SKETCHES)
    )
    assert section_names <= set(drawing.SECTION_KEEP)
    for sketch in set(spec.REFERENCE_SKETCHES) - set(spec.SECTION_REFERENCE_SKETCHES):
        assert not spec.DRAWING_DIMENSIONS[sketch] & set(drawing.SECTION_KEEP)
    block = _DRAWING_SOURCE.index("with part_sketches_shown(")
    assert "SECTION_REFERENCE_SKETCHES" in _DRAWING_SOURCE[block : block + 200]
    assert "base_view=front" in _DRAWING_SOURCE[block : block + 250]
    cut = _DRAWING_SOURCE.index("section = create_section_view(")
    curate = _DRAWING_SOURCE.index("keep=SECTION_KEEP")
    iso = _DRAWING_SOURCE.index('"*Isometric"')
    assert block < cut < curate < iso
    # The cutting line and the sketches' plane are the same x.
    assert {point[0] for point in drawing.SECTION_LINE_MODEL_MM} == {spec.PIVOT_BORE_X}
    assert 'base_plane="Right Plane", offset=PIVOT_BORE_X' in _PART_SOURCE
    for helper in ("_relief_reference", "_pivot_reference"):
        body = _PART_SOURCE[_PART_SOURCE.index(f"async def {helper}(") :]
        body = body[: body.index("\nasync def ")]
        assert "create_sketch(SECTION_PLANE)" in body
    assert 'blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))' in (
        _PART_SOURCE
    )


def test_relief_corners_carry_the_largest_radius_the_grip_allows() -> None:
    assert spec.RELIEF_CORNER_R == 1.0
    assert spec._GRIP_GAP_AT_BOTTOM - spec.RELIEF_CORNER_R >= 0.25
    assert spec.DIMENSION_PREFIXES == {("ReliefProfile", "ReliefCornerR"): "2X R"}
    assert (
        "set_dimension_prefix(adapter, feature_name, dimension_name, prefix)"
        in _PART_SOURCE
    )
    assert '"tangent"' in _PART_SOURCE and '"radial"' in _PART_SOURCE


def test_pivot_chamfer_clears_the_rod_fillet_as_a_min_limit() -> None:
    import _config
    import pn_pen_rod_spec as rod

    fillet_reach = rod.SHOULDER_FILLET_R * (2.0 - math.sqrt(2.0))
    assert spec.PIVOT_BORE_TOP_CHAMFER - fillet_reach >= 0.1
    mouth_r = (spec.PIVOT_BORE_DIA + spec.PIVOT_BORE_BAND[0]) / 2.0
    largest = spec.PIVOT_BORE_TOP_CHAMFER + spec.PIVOT_CHAMFER_BAND[0]
    assert mouth_r + largest < (rod.ROD_SECTION + rod.SECTION_BAND[1]) / 2.0
    assert spec.PIVOT_CHAMFER_TOL_TYPE == 5  # swTolMIN
    assert "tolerance.Type = PIVOT_CHAMFER_TOL_TYPE" in _PART_SOURCE
    assert _PART_SOURCE.index("_pivot_chamfer_min_limit(adapter)\n") < (
        _PART_SOURCE.index("clear_dimensions_for_drawing(adapter)")
    )
    rod_number = _config.parts("pn-pen-rod")["number"]
    assert rod_number in spec.DIMENSION_CALLOUTS_ABOVE["PivotChamferSize"]
    for text in (
        spec.DIMENSION_CALLOUTS["PivotChamferSize"],
        spec.DIMENSION_CALLOUTS_ABOVE["PivotChamferSize"],
    ):
        assert not re.search(r"\d\.\d", text)


def test_holes_are_native_wizard_features_with_native_callouts() -> None:
    assert spec.SET_SCREW_TAP_SPEC.kind == "tapped"
    assert spec.SET_SCREW_TAP_SPEC.end == "through_next"
    assert spec.LIGHTENING_SPEC.end == "through_all"
    assert _PART_SOURCE.count("wizard_holes(") == 2
    assert "SET_SCREW_TAP_SPEC,\n" in _PART_SOURCE
    assert "LIGHTENING_SPEC,\n" in _PART_SOURCE
    # The reamed pivot bore is a sketched cut whose diameter carries the band.
    assert "define_circle(" in _PART_SOURCE
    assert spec.DRAWING_BANDS == {
        ("PivotBoreProfile", "PivotDia"): spec.PIVOT_BORE_BAND
    }
    assert _DRAWING_SOURCE.count("add_native_hole_callout(") == 2
    assert 'process="TAP"' in _DRAWING_SOURCE
    assert 'process="DRILL"' in _DRAWING_SOURCE
    # The title block owns the thread class (rule 2); the drill's and the
    # reamed bore's leaders stop on the near rim (rule 14).
    assert (
        'omit_title_block_thread_class(tap_callout, label="rod set-screw tap")'
        in _DRAWING_SOURCE
    )
    assert "lightening_callout.GetAnnotation()" in _DRAWING_SOURCE
    assert 'set_near_side_diameter(pivot_dia[0], "reamed pivot-bore diameter")' in (
        _DRAWING_SOURCE
    )


def test_pivot_callout_names_its_mate_and_says_ream() -> None:
    import _config

    rod_number = _config.parts("pn-pen-rod")["number"]
    callout = spec.DIMENSION_CALLOUTS["PivotDia"]
    assert callout.startswith("REAM THRU")
    assert rod_number in callout
    assert not re.search(r"\d\.\d", callout)


def test_analytic_volumes_match_the_carriage_mass_model() -> None:
    import pn_pen_carriage_geom as carriage

    assert part.V_BLOCK == pytest.approx(11016.0)
    assert part.V_GROOVE == pytest.approx(360.0)
    # The carriage mass model cuts the relief square-cornered and leaves the
    # bore's top chamfer: both under 0.05% of the block.
    assert part.V_RELIEF + part.V_RELIEF_CORNERS == pytest.approx(2197.0)
    corner_r, relief_h = spec.RELIEF_CORNER_R, spec.RELIEF_HEIGHT
    assert part.V_RELIEF_CORNERS == pytest.approx(
        2.0 * (1.0 - math.pi / 4.0) * corner_r**2 * relief_h
    )
    assert 0.0 < part.V_RELIEF_CORNERS < 0.0005 * part.V_TOTAL
    assert 0.0 < part.V_PIVOT_CHAMFER < 0.0005 * part.V_TOTAL
    bore_length = spec.BLOCK_HEIGHT - spec.RELIEF_HEIGHT
    assert part.V_PIVOT_BORE == pytest.approx(math.pi * 4.0 * bore_length)
    tap_r = TAP_DRILL_MM[spec.SET_SCREW_TAP_SPEC.size] / 2.0
    # The exact tap reaches past the bore wall's 7.0 on its axis, never past the bore axis.
    assert (
        math.pi * tap_r**2 * spec.SET_SCREW_TAP_LENGTH
        < part.V_SET_SCREW_TAP
        < math.pi * tap_r**2 * spec.BLOCK_DEPTH / 2.0
    )
    block_mass = sum(
        mass
        for name, mass, _x, _z in carriage.plan_mass_items()
        if name.startswith("v-block ")
    )
    sliver = part.V_SET_SCREW_TAP - math.pi * tap_r**2 * spec.SET_SCREW_TAP_LENGTH
    carriage_volume = block_mass / carriage.BRASS_G_PER_MM3 - sliver
    assert carriage_volume == pytest.approx(
        part.V_TOTAL - part.V_RELIEF_CORNERS + part.V_PIVOT_CHAMFER
    )


def test_sheet_runs_at_4_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert drawing.VIEW_SCALE == (4, 1)
    assert drawing.ISO_SCALE == (1, 1)
    assert _DRAWING_SOURCE.count("scale=VIEW_SCALE") == 4  # three projections + A-A
    assert _DRAWING_SOURCE.count("scale=ISO_SCALE") == 1
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in _DRAWING_SOURCE
    assert '"*Back"' in _DRAWING_SOURCE and '"*Left"' in _DRAWING_SOURCE
    assert "create_section_view(" in _DRAWING_SOURCE


def test_no_note_block_no_gdt_no_roughness() -> None:
    # Material and finish ride the title block; the sheet has nothing else to say.
    assert spec.DRAWING_NOTES == ""
    for source in (_PART_SOURCE, _DRAWING_SOURCE):
        assert "Manufacturing Notes" not in source
        for banned in (
            "author_part_pmi",
            "PART_DATUMS",
            "GEOMETRIC_CONTROLS",
            "_gtol",
            "add_datum_feature",
            "add_feature_control_frame",
            "set_basic_dimension",
            "SURFACE_FINISHES",
            "add_surface_finish",
            "apply_color",
        ):
            assert banned not in source, banned


def test_part_stamps_make_critical_drawing_properties() -> None:
    assert "apply_drawing_properties" in _PART_SOURCE
    assert "clear_dimensions_for_drawing" in _PART_SOURCE
    assert "require_saved_drawing_properties" in _PART_SOURCE
    import _config

    registry = _config.parts("pn-pen-v-block")
    assert "brass" in str(registry["material_specification"]).lower()
    assert "bright brass" in str(registry["finish"]).lower()
    assert int(registry["quantity"]) == 1
