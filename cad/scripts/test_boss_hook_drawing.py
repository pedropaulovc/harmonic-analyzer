"""Offline contracts for the boss-hook drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a formed wire hook
carries no datums, frames or roughness symbols; the bend radius and crack
check are a leader callout on the elbow, and the note block is one line of
forming fact.
"""

from __future__ import annotations

from pathlib import Path

import boss_hook_geom
import boss_hook_spec
import build_boss_hook as part
import draw_boss_hook as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/boss-hook.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/boss-hook.pdf")
    assert drawing.PNG.as_posix().endswith("/png/boss-hook_drawing.png")
    assert DRAWINGS_BY_NAME["boss_hook"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is boss_hook_spec.DRAWING_DIMENSIONS
    marked = set().union(*boss_hook_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert (drawing.ELBOW_R, drawing.ROD_DIA, drawing.SHANK_RISE) == (
        boss_hook_geom.ELBOW_R,
        boss_hook_geom.ROD_DIA,
        boss_hook_geom.SHANK_RISE,
    )
    assert drawing.ARM_RUN is part.ARM_RUN


def test_bend_callout_carries_the_radius_to_one_decimal() -> None:
    # Machinist review 2026-09-02: "R3" had no tolerance under the title
    # block; R3.0 puts it under the .X band, and it sits on the bend with the
    # crack check instead of in a remote note.
    note = boss_hook_spec.BEND_NOTE
    assert f"R{boss_hook_geom.ELBOW_R:.1f}" in note
    assert "R3.0" in note
    assert "CENTRELINE" in note
    assert "NO CRACKS" in note
    source = _source()
    assert "text=BEND_NOTE" in source
    assert "entity_xy=elbow_xy" in source
    assert 'entity_type="SILHOUETTE"' in source
    assert "find_edge_near(" in source
    # The callout sits up-left of the elbow, clear of the 3.50 lane above the arm.
    assert drawing.BEND_NOTE_XY[0] < drawing.OUTER_ELBOW_XY[0]
    assert drawing.BEND_NOTE_XY[1] > drawing.OUTER_ELBOW_XY[1]


def test_wire_diameter_leader_lands_on_the_visible_half() -> None:
    # The right half of the wire circle in the top view is hidden under the
    # arm, so the Ø3.00 text sits LEFT of the section.
    assert drawing.TOP_KEEP["RodDia"][0] < drawing.TOP_CENTER[0]


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = boss_hook_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "TANGENT" in notes
    # The wire size is the Ø3.00 dimension; the radius and crack check ride
    # the bend callout -- neither is restated here.
    for banned in (
        "3.00 WIRE",
        "R3",
        "NO CRACKS",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "MAX",
        "<=",
        "AISI",
        "X.XX",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


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
    assert not hasattr(boss_hook_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = _source()
    assert "scale=(4, 1)" in source
    assert "scale=(2, 1)" in source
    assert boss_hook_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("boss-hook")
    assert config["material"] == "ASTM A108 Grade 1018 steel"
    assert config["material"] == config["material_specification"]
    assert "steel" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
