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
    assert set(spec.DIMENSION_CALLOUTS) <= marked
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
        "SetScrewHole",
        "LighteningBore",
    ]
    positions = [_PART_SOURCE.index(f'"{name}"') for name in tree_order]
    # The tap is built after the bore, so its through_next stops at the bore.
    assert positions == sorted(positions)


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
    assert part.V_RELIEF == pytest.approx(2197.0)
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
    assert block_mass / carriage.BRASS_G_PER_MM3 - sliver == pytest.approx(part.V_TOTAL)


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
