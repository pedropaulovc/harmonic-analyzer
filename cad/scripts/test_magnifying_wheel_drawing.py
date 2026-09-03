"""Offline contracts for the magnifying-wheel drawing.

The print follows cad/docs/drawing-simplicity-policy.md: the wheel is not on
the GD&T allowlist (no datum, no runout frame, no basic dimension); the one
roughness symbol sits on the axle bore, which turns on the stud in service and
carries its ream band on the model dimension; the axial facts (rim width, hub
length, spoke thickness and their stations) are real cut edges in SECTION A-A,
never hidden lines.
"""

from __future__ import annotations

from pathlib import Path

import build_magnifying_wheel as part
import draw_magnifying_wheel as drawing
import magnifying_wheel_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import REAM_H7


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_surface_finish_is_the_running_bore_only() -> None:
    # Rule 5: the bore runs on the axle stud; the hub drum only carries the
    # wrapped wire and stays at the block Ra.
    (control,) = magnifying_wheel_spec.SURFACE_FINISHES
    assert control.key == "axle_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == magnifying_wheel_spec.BORE_DIA
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = _source()
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "axle_bore")' in drawing_source
    assert drawing_source.count("add_surface_finish(") == 1
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-wheel.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-wheel.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-wheel_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_wheel"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_wheel_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_wheel_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.SECTION_KEEP)
    assert kept == marked
    # The rim ID is controlling on the face (the 6 wall is derived), so both
    # rim diameters, the hub, the spoke width and the bore are the face set.
    assert marked == {
        "RimOuterDiaDim",
        "RimInnerDiaDim",
        "HubDiaDim",
        "SpokeWidthDim",
        "BoreDiaDim",
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert set(drawing.DIMENSION_PRECISION) <= kept
    assert set(drawing.FRONT_DIAMETERS) <= kept


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hub diameter + spoke axial the assembly imports live in the drawing-
    # FREE geom module, so a print-note edit cannot enter the assembly recipe.
    import magnifying_wheel_geom as geom

    assert (geom.RIM_OUTER_DIA, geom.HUB_DIA, geom.SPOKE_COUNT) == (100.0, 20.0, 6)
    assembly = Path(part.__file__).with_name("build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from magnifying_wheel_geom import HUB_DIA, SPOKE_AXIAL" in assembly
    assert "from build_magnifying_wheel import" not in assembly


def test_reamed_bore_band_rides_the_model_dimension() -> None:
    # Policy rule 2: the H7 ream band is a native tolerance on BoreDiaDim (the
    # sheet shows it to three places), never callout text or a note.
    assert magnifying_wheel_spec.BORE_DIA_BAND == REAM_H7 == (0.012, 0.000)
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDiaDim"): "*deviations(BORE_DIA_BAND)"
    }
    assert drawing.DIMENSION_PRECISION == {"BoreDiaDim": 3}
    assert drawing.DIMENSION_CALLOUTS["BoreDiaDim"] == "REAM THRU"
    assert drawing.DIMENSION_CALLOUTS["SpokeWidthDim"] == "6X SPOKES, EQUALLY SPACED"


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = magnifying_wheel_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 1
    # The one process fact no view carries: which casting faces are machined.
    assert notes == "CASTING. MACHINE THE RIM OD, BOTH RIM FACES AND THE HUB DRUM."
    # Nothing the title block, a dimension or a release ticket already says --
    # in particular no bare-integer spoke/wall sizes (they are on the views).
    for banned in (
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "DATUM",
        "MHA-",
        "DO NOT RELEASE",
        "5X",
        "6X",
        "REAM",
        "Ra ",
        "GRAY-IRON",
        "BLACK-PAINTED",
        "DEBURR",
        "BREAK SHARP",
        "X.XX",
        "WALL",
        "THICK",
        "CENTRED",
    ):
        assert banned not in notes, banned
    assert not any(character.isdigit() for character in notes)
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()
    # The section's native label replaces the old "SIDE VIEW" caption, and the
    # isometric caption no longer repeats the sheet scale.
    assert not hasattr(magnifying_wheel_spec, "SECTION_VIEW_NOTE")
    assert magnifying_wheel_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW"
    assert "Section View Note" not in _source()
    assert "Section View Note" not in Path(part.__file__).read_text(encoding="utf-8")


def test_print_carries_no_gdt_or_basic_dimensions() -> None:
    # Policy rules 3-4: a wheel is not on the allowlist.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(magnifying_wheel_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(magnifying_wheel_spec, "GEOMETRIC_CONTROLS")


def test_axial_facts_are_cut_edges_in_section_a_a() -> None:
    # Policy rule 7: the spoke thickness, hub length and their stations against
    # the rim faces are dimensioned on the section strip cut through the face
    # view's horizontal centreline, never on hidden lines.
    source = _source()
    assert source.count("create_section_view(") == 1
    assert 'section_label="A"' in source
    assert source.count("add_edge_dimension(") == 5
    for label in (
        'label="rim axial width"',
        'label="spoke thickness"',
        'label="spoke face to rim face"',
        'label="hub-drum axial length"',
        'label="hub face to rim face"',
    ):
        assert label in source, label
    # Picks are resolved through the section's projected frame, not guessed.
    assert "model_point_in_view(" in source
    # The cutting plane runs horizontally through the face centre (the
    # 90/270-degree spokes are on it, so the strip shows a spoke band).
    assert drawing.SECTION_LINE[0][1] == drawing.SECTION_LINE[1][1] == drawing.FRONT_CENTER[1]
    assert drawing.SECTION_LINE[0][0] < drawing.FRONT_CENTER[0] - drawing._RIM_R
    assert drawing.SECTION_LINE[1][0] > drawing.FRONT_CENTER[0] + drawing._RIM_R
    # The strip sits under the face, clear of the title block (x > ~0.218,
    # y < 0.070).  Its generated caption is moved through the complete view
    # annotation collection into a band above and to the right of the strip.
    assert drawing.SECTION_CENTER[1] < drawing.FRONT_CENTER[1] - drawing._RIM_R
    assert drawing.SECTION_CENTER[0] + drawing._RIM_R < 0.218
    assert drawing.SECTION_LABEL_XY[1] >= drawing.SECTION_CENTER[1] + 0.015
    assert drawing.SECTION_LABEL_XY[0] >= drawing.SECTION_CENTER[0] + 0.070
    assert "view.GetNotes()" in source
    assert "view.GetFirstNote2()" in source
    assert "view.GetAnnotations()" in source
    assert "view.GetFirstAnnotation3()" in source
    assert "label annotation not found" in source
    # The hub callout is outboard in the lower-right spoke gap rather than
    # sharing the narrow band above the section with the hub and bore leaders.
    hub_xy = drawing.FRONT_KEEP["HubDiaDim"]
    assert hub_xy[0] > drawing.FRONT_CENTER[0] + drawing._RIM_R
    assert hub_xy[1] - drawing.SECTION_CENTER[1] >= 0.045
    # The bore's three-line nominal/H7/process stack clears the cutting plane.
    assert (
        drawing.FRONT_CENTER[1] - drawing.FRONT_KEEP["BoreDiaDim"][1]
        >= 0.025
    )
    assert drawing.SECTION_KEEP == {}
    # Every face diameter leader ends on its circumference (arrows outside).
    assert "_leaders_to_circumference(" in source
    assert drawing.FRONT_DIAMETERS == (
        "RimOuterDiaDim",
        "RimInnerDiaDim",
        "HubDiaDim",
        "BoreDiaDim",
    )


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, section):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-wheel")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
