"""Offline contracts for the magnifying-lever drawing."""

from __future__ import annotations

from pathlib import Path

import build_mg_magnifying_lever as part
import draw_mg_magnifying_lever as drawing
import mg_magnifying_lever_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-lever_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_lever"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is mg_magnifying_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*mg_magnifying_lever_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.PRESS_ZONE_KEEP)
    )
    assert kept == marked
    assert marked == {"RightDomeCentre", "DomeRadius", "PressZoneLen", "PressZoneDia"}
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= set(drawing.FRONT_KEEP)
    assert set(drawing.PRESS_ZONE_CALLOUTS) <= set(drawing.PRESS_ZONE_KEEP)
    assert drawing.ROD_LENGTH == mg_magnifying_lever_spec.ROD_LENGTH
    # The reference sketch's dims are the hidden-sketch path's, never the
    # entire-model import's (the part saves PressZone blanked).
    assert not set(drawing.PRESS_ZONE_KEEP) & set(drawing.FRONT_KEEP)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "curate_hidden_dimensions(" in source
    assert "dimensions_by_feature=DRAWING_DIMENSIONS" in source


def test_press_zone_is_a_native_band_from_the_drawing_free_geom() -> None:
    """The collar press (user ruling 2026-10-11): the rod's last 10 carry a
    0/-0.008 band natively on the blanked PressZone sketch; the bore nominal
    and band live beside them in the geom module so the bracket build, this
    build and the assembly's allowance read ONE source; the worst-case
    budget is computed there, not typed anywhere."""
    import pytest

    import mg_magnifying_lever_geom as geom

    assert geom.PRESS_ZONE_DIA == geom.ROD_DIA == 6.0
    assert geom.PRESS_ZONE_DIA_BAND == (0.0, -0.008)
    assert geom.COLLAR_BORE_DIA == 5.976
    assert geom.COLLAR_BORE_BAND == (0.008, 0.0)
    assert geom.PRESS_ZONE_X == (
        geom.COLLAR_LOCAL_X - geom.COLLAR_HALF_LEN,
        geom.COLLAR_LOCAL_X + geom.COLLAR_HALF_LEN,
    )
    assert geom.PRESS_ZONE_X == (155.0, 165.0)
    assert geom.PRESS_ZONE_LENGTH == 2.0 * geom.COLLAR_HALF_LEN == 10.0
    assert geom.PRESS_ZONE_X[1] == geom.ROD_LENGTH  # tip flush with the outer face
    # Straight rod inside the collar: from its inner face to where the dome starts.
    assert geom.COLLAR_ENGAGEMENT == pytest.approx(7.0)
    budget = geom.press_fit_budget()
    assert budget == geom.PRESS_FIT_BUDGET
    assert budget["interference_nominal"] == pytest.approx(0.024)
    assert budget["interference_min"] == pytest.approx(0.008)
    assert budget["interference_max"] == pytest.approx(0.024)
    assert budget["engagement"] == geom.COLLAR_ENGAGEMENT
    assert 0.0 < budget["interference_min"] <= budget["interference_max"]
    # ANSI B4.1 FN2 for 0.12..0.24 in: 1.0 thou at the tightest.
    assert geom.PRESS_INTERFERENCE_MAX_FN2 == pytest.approx(0.0254)
    assert budget["interference_max"] <= geom.PRESS_INTERFERENCE_MAX_FN2
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "PressZone")' in source
    assert '"PressZone", "PressZoneDia", *deviations(PRESS_ZONE_DIA_BAND)' in source
    assert 'blank_reference_sketches(adapter, ("PressZone",))' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "segment.ConstructionGeometry = True" in source
    assert 'zone.record("PressZoneDia", \'"RodDia"\')' in source
    assert 'zone.record("PressZoneEnd", \'"RodLength"\')' in source
    assert mg_magnifying_lever_spec.DRAWING_PRECISION["PressZone"] == {
        "PressZoneLen": 2,
        "PressZoneDia": 3,
    }
    assert "PressZoneEnd" not in set().union(*part.DRAWING_DIMENSIONS.values())


def test_final_forced_volume_guard_follows_annotations_before_publication() -> None:
    """Source ordering only: after the last dimension/annotation mutation the
    build rebuilds, re-proves the rod's volume, then saves."""
    import ast

    source = Path(part.__file__).read_text(encoding="utf-8")
    build = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    rebuild, guard, publish = build.body[-3:]
    assert isinstance(rebuild, ast.Expr) and isinstance(rebuild.value, ast.Await)
    assert rebuild.value.value.func.id == "force_rebuild"
    assert isinstance(guard, ast.Expr) and isinstance(guard.value, ast.Await)
    call = guard.value.value
    assert call.func.id == "volume_check"
    assert call.args[1].value == "final rod (annotations neutral)"
    assert call.args[2].id == "v_rod"
    assert isinstance(publish, ast.Return) and isinstance(publish.value, ast.Await)
    assert publish.value.value.func.id == "save_part_and_images"
    for mutation in (
        "set_dimension_bilateral_tolerance",
        "apply_drawing_precision",
        "clear_dimensions_for_drawing",
        "mark_dimensions_for_drawing",
        "apply_drawing_properties",
        "blank_reference_sketches",
    ):
        calls = [
            node for node in ast.walk(build)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == mutation
        ]
        assert calls, mutation
        assert all(node.lineno < rebuild.lineno for node in calls), mutation


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The knife-axis station the assembly imports lives in the drawing-FREE geom
    # module, so a print-note edit cannot enter the assembly's recipe closure.
    import mg_magnifying_lever_geom as geom

    assert (geom.ROD_DIA, geom.ROD_LENGTH) == (6.0, 165.0)
    assert hasattr(geom, "KNIFE_LOCAL_X") and hasattr(geom, "KNIFE_LOCAL_Y")
    assembly = (
        Path(part.__file__)
        .with_name("build_mg_magnifier_assembly.py")
        .read_text(encoding="utf-8")
    )
    assert "from mg_magnifying_lever_geom import (" in assembly
    assert "KNIFE_LOCAL_X," in assembly
    assert "KNIFE_LOCAL_Y," in assembly


def test_linked_notes_specify_round_brass_stock_and_domed_ends() -> None:
    notes = mg_magnifying_lever_spec.DRAWING_NOTES
    assert "Ø6 ROUND BAR" in notes
    assert "BRASS" not in notes and "C36000" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "HEMISPHERE" in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    assert "165" in notes  # overall length carried in the note
    # The press zone's size and band are native dims; the note says how to
    # hold them and what they mate. The press and Loctite are the bracket sheet's.
    assert "PRESS ZONE" in notes and "MHA-MG-001" in notes
    assert "LOCTITE" not in notes and "638" not in notes
    assert "0.008" not in notes and "5.976" not in notes and "6.000" not in notes
    assert len(notes.splitlines()) <= 4
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert drawing.DIMENSION_CALLOUTS["DomeRadius"] == "FULL R, BOTH ENDS - Ø6 ROD"


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the front side view
    assert "scale=(4, 1)" in source  # the end view
    assert drawing.ISO_SCALE == (1, 2)
    assert "scale=ISO_SCALE" in source
    assert mg_magnifying_lever_spec.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    assert mg_magnifying_lever_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source


def test_form_and_finish_are_note_based_on_the_unpickable_capsule() -> None:
    # A smooth hemispherical-ended capsule exposes no selectable edge, so there
    # are NO coordinate-pick annotations (datum/FCF/Ra/edge dims); the OD
    # straightness + Ra requirement is carried in the manufacturing note instead.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 0
    assert source.count("add_feature_control_frame(") == 0
    assert source.count("add_surface_finish(") == 0
    assert source.count("add_edge_dimension(") == 0
    assert "Ra 1.6" in mg_magnifying_lever_spec.DRAWING_NOTES


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-lever")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
    # The clamp block still slides along the rod; the tip end is pressed.
    assert config["fit_class"] == "shaft_in_bushing"
    assert "pressed into the MHA-MG-001 bracket collar" in config["process"]
