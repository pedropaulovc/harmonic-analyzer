"""Offline contracts for the gooseneck drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a bent tube with a
brazed lug carries no datums, frames or roughness symbols, and its notes are
four lines of forming and brazing fact.
"""

from __future__ import annotations

import re
from pathlib import Path

import build_gooseneck as part
import draw_gooseneck as drawing
import gooseneck_geom as geom
import gooseneck_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/gooseneck.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/gooseneck.pdf")
    assert drawing.PNG.as_posix().endswith("/png/gooseneck_drawing.png")
    assert DRAWINGS_BY_NAME["gooseneck"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is gooseneck_spec.DRAWING_DIMENSIONS
    marked = set().union(*gooseneck_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = gooseneck_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The block sits left of the tall elevation; keep the lines short.
    assert max(len(line) for line in lines) <= 68
    # The tube wall, the leg length (an extrude offset, not a sketch dim) and
    # the brazed plug/screw are the facts the views cannot carry.
    assert "2.0 WALL" in notes
    assert "BRAZED" in notes
    # Pass-3 geometry: end plug + axial spring screw, no lug or cross-pin.
    assert "END PLUG" in notes
    assert "#6-32" in notes
    assert "SLOTTED HEAD" in notes
    assert f"{part.LEG_TOP - part.LEG_BOTTOM:g} LEG" in notes
    assert f"{part.ARM_RUN:g} ARM" in notes
    assert not re.search(r"\bLUG\b", notes)
    assert not re.search(r"\bPIN\b", notes)
    for banned in ("UOS", "DIMENSIONS IN", "+/-", "WITHIN", "MAX", "CHROME", "AISI", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert '"Manufacturing Notes", 0.016, 0.114' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(gooseneck_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hidden_lines_stay_on_in_the_elevation() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_view_scale_is_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 3.0)
    source = _source()
    assert "scale=(1, 3)" in source
    assert "scale=(1, 4)" in source
    assert drawing.ISO_VIEW_NOTE_XY == (0.260, 0.095)
    # The rendered caption is about 70 mm wide; this 90 mm offset leaves its
    # right edge clear of the isometric's long stem at the view centre.
    assert drawing.ISO_CENTER[0] - drawing.ISO_VIEW_NOTE_XY[0] > 0.089
    assert (
        'add_property_linked_note(adapter, "Isometric View Note", *ISO_VIEW_NOTE_XY)'
        in source
    )
    # The arm-end detail view was intentionally dropped (see the "NO end-screw
    # detail view" rationale in draw_gooseneck.py): assert no detail-view CALL
    # exists, not the historical mention in the explanatory comment.
    assert "CreateDetailViewAt4(" not in source
    assert "NO end-screw detail view" in source
    assert gooseneck_spec.ELEVATION_VIEW_NOTE == "ELEVATION SCALE 1:3"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("gooseneck")
    assert config["material"] == "AISI 1010 seamless steel tube"
    assert config["material"] == config["material_specification"]
    assert "chrome" not in str(config["material_specification"]).lower()
    assert "ASTM B456 SC2" in str(config["finish"])
    assert int(config["quantity"]) == 1


def test_part_reimports_the_geometry_nominals_assemblies_read() -> None:
    # gooseneck_geom is the prose-free import surface for build_summing_assembly
    # (codex #361 pattern, like boss_hook_geom); the part build must use the
    # SAME objects so the hang proof and the geometry can never drift.
    for name in (
        "ARM_END_X", "ARM_Y", "PLUG_T", "SCREW_HEAD_DIA", "SCREW_HEAD_T",
        "SCREW_SHANK_DIA", "SCREW_SHANK_LEN", "TUBE_DIA", "WALL_T",
    ):
        assert getattr(part, name) == getattr(geom, name), name
    assert abs(part.LEG_TOP - (geom.ARM_Y - part.BEND_R)) < 1e-6
    # The eye must clear the head shoulder and the end face along the shank,
    # with room for the head to exist beyond the eye.
    assert 0.0 < geom.SCREW_SHANK_LEN
    assert geom.SCREW_SHANK_DIA < geom.SCREW_HEAD_DIA
    # The head must RETAIN a slack eye: wider than the eye's inner diameter.
    import counter_spring_spec as spring

    assert geom.SCREW_HEAD_DIA > spring.COIL_ID
    assert geom.SCREW_SHANK_DIA + 2 * 0.25 <= spring.COIL_ID  # 0.25 radial air
    assert geom.PLUG_T > 0.0
    assert part.PLUG_DIA < geom.TUBE_DIA  # never coincident with the tube OD
    assert part.PLUG_DIA > geom.TUBE_DIA - 2.0 * geom.WALL_T  # real wall overlap
