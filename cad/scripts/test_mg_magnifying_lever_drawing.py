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
        set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.REFERENCE_KEEP)
    )
    assert kept == marked
    assert marked == {
        "RightDomeCentre",
        "DomeRadius",
        "RodDia",
        "PressZoneLen",
        "PressZoneDia",
    }
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= set(drawing.FRONT_KEEP)
    assert set(drawing.REFERENCE_CALLOUTS) <= set(drawing.REFERENCE_KEEP)
    assert drawing.ROD_LENGTH == mg_magnifying_lever_spec.ROD_LENGTH
    # The reference sketches' dims are the hidden-sketch path's, never the
    # entire-model import's (the part saves PressZone and RodStock blanked).
    assert not set(drawing.REFERENCE_KEEP) & set(drawing.FRONT_KEEP)
    assert mg_magnifying_lever_spec.DRAWING_DIMENSIONS["RodStock"] == {"RodDia"}
    assert mg_magnifying_lever_spec.DRAWING_DIMENSIONS["PressZone"] == {
        "PressZoneLen",
        "PressZoneDia",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "curate_hidden_dimensions(" in source
    assert "dimensions_by_feature=DRAWING_DIMENSIONS" in source
    assert "keep=REFERENCE_KEEP" in source


def test_stock_diameter_is_a_native_dimension_on_the_side_view() -> None:
    """Machinist review item 5: the Ø6 rod was a note only.  It prints once
    from the blanked RodStock reference sketch (the revolve profile's top line
    is already the dome radius's height, so a second diameter there
    over-defines the capsule), doubled off a short centerline with the Ø
    prefix the point-form diametric dims need (v41 sheet)."""
    import mg_lever_press_fit_geom as press

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "RodStock")' in source
    assert 'stock.record("RodDia", \'"RodDia"\')' in source
    assert 'stock.record("RodDiaStation", \'"RodLength" / 2\')' in source
    assert 'set_dimension_prefix(adapter, "RodStock", "RodDia", "<MOD-DIAM>")' in source
    assert 'blank_reference_sketches(adapter, ("PressZone", "RodStock"))' in source
    assert part.ROD_DIA_STATION == part.ROD_LENGTH / 2.0
    assert part.R == press.ROD_DIA / 2.0
    assert mg_magnifying_lever_spec.DRAWING_PRECISION["RodStock"] == {"RodDia": 2}
    assert "RodDiaStation" not in set().union(*part.DRAWING_DIMENSIONS.values())
    assert "RodStockAxis" not in set().union(*part.DRAWING_DIMENSIONS.values())
    assert drawing.REFERENCE_CALLOUTS["RodDia"] == "STOCK OD"
    # The dome radius keeps its native R3; its callout no longer restates the
    # full radius or the rod diameter (both are dimensions now).
    assert drawing.DIMENSION_CALLOUTS["DomeRadius"] == "BOTH ENDS"
    assert "FULL R" not in drawing.DIMENSION_CALLOUTS["DomeRadius"]
    assert "Ø6" not in drawing.DIMENSION_CALLOUTS["DomeRadius"]


def test_press_zone_is_a_native_band_from_the_config_free_press_contract() -> None:
    """The collar press (user rulings 2026-10-11/12): the STRAIGHT rod the
    collar grips carries its stock band natively on the blanked PressZone
    sketch; the rod diameter, zone length, bore nominal and band live in
    mg_lever_press_fit_geom so the bracket build, this build and the assembly's
    allowance read ONE source that pulls NO machine config; the worst-case
    budget is computed there, not typed anywhere. The lever geom keeps the
    configured station and asserts it is that zone, tip flush."""
    import ast

    import pytest

    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as geom

    press_source = Path(press.__file__).read_text(encoding="utf-8")
    imported = [
        node for node in ast.parse(press_source).body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    modules = {
        name
        for node in imported
        for name in (
            [node.module]
            if isinstance(node, ast.ImportFrom)
            else [alias.name for alias in node.names]
        )
    }
    assert modules == {"__future__", "math"}, (
        "the press contract must stay config-free (no _config/output.yaml closure)"
    )
    assert press.PRESS_ZONE_DIA == press.ROD_DIA == 6.0
    assert press.PRESS_ZONE_LENGTH == 10.0
    # Max-material model nominals (Main's 2026-10-12 press ruling).
    assert press.PRESS_ZONE_DIA_BAND == (0.0, -0.006)
    assert press.COLLAR_BORE_DIA == 5.986
    assert press.COLLAR_BORE_BAND == (0.006, 0.0)
    # The configured collar window is the zone, and the rod ends flush with it.
    assert geom.PRESS_ZONE_X == (
        geom.COLLAR_LOCAL_X - geom.COLLAR_HALF_LEN,
        geom.COLLAR_LOCAL_X + geom.COLLAR_HALF_LEN,
    )
    assert geom.PRESS_ZONE_X == (155.0, 165.0)
    assert geom.PRESS_ZONE_X[1] - geom.PRESS_ZONE_X[0] == press.PRESS_ZONE_LENGTH
    assert geom.PRESS_ZONE_X[1] == geom.ROD_LENGTH  # tip flush with the outer face
    assert not hasattr(geom, "COLLAR_BORE_DIA") and not hasattr(geom, "ROD_DIA")
    # Straight rod inside the collar: from its inner face to where the dome starts.
    assert press.COLLAR_ENGAGEMENT == press.PRESS_ZONE_LENGTH - press.ROD_DIA / 2.0
    assert press.COLLAR_ENGAGEMENT == pytest.approx(7.0)
    budget = press.press_fit_budget()
    for key in ("interference_nominal", "interference_min", "interference_max", "engagement"):
        assert budget[key] == press.PRESS_FIT_BUDGET[key]
    assert budget["interference_nominal"] == pytest.approx(0.014)
    assert budget["interference_min"] == pytest.approx(0.002)
    assert budget["interference_max"] == pytest.approx(0.014)
    assert budget["engagement"] == press.COLLAR_ENGAGEMENT
    assert 0.0 < budget["interference_min"] <= budget["interference_max"]
    # ANSI B4.1 FN2 for 0.12..0.24 in: 1.0 thou at the tightest.
    assert press.PRESS_INTERFERENCE_MAX_FN2 == pytest.approx(0.0254)
    assert budget["interference_max"] <= press.PRESS_INTERFERENCE_MAX_FN2
    assert part.PRESS_ZONE_DIA_BAND is press.PRESS_ZONE_DIA_BAND
    assert part.PRESS_ZONE_X is geom.PRESS_ZONE_X
    # Review item 6: the banded witness is ONLY the straight engagement, from
    # the collar's inner face to the dome tangent -- never the R3 dome.
    assert part.PRESS_ZONE_END == geom.ROD_LENGTH - press.ROD_DIA / 2.0 == 162.0
    assert part.PRESS_ZONE_END - part.PRESS_ZONE_X[0] == press.COLLAR_ENGAGEMENT
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "PressZone")' in source
    assert '"PressZone", "PressZoneDia", *deviations(PRESS_ZONE_DIA_BAND)' in source
    # Point-form diametric dims print no Ø of their own (v41 sheet).
    assert 'set_dimension_prefix(adapter, "PressZone", "PressZoneDia", "<MOD-DIAM>")' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "segment.ConstructionGeometry = True" in source
    assert "add_line(PRESS_ZONE_X[0], R, PRESS_ZONE_END, R)" in source
    assert (
        '"horizontal_distance",\n        COLLAR_ENGAGEMENT,\n        "press zone PressZoneLen",'
        in source
    )
    assert 'zone.record("PressZoneLen", \'"CollarLen" - "RodDia" / 2\')' in source
    assert 'zone.record("PressZoneEnd", \'"RodLength" - "RodDia" / 2\')' in source
    assert 'zone.record("PressZoneDia", \'"RodDia"\')' in source
    assert 'set_global(adapter, "CollarLen", f"{PRESS_ZONE_LENGTH}mm")' in source
    assert mg_magnifying_lever_spec.DRAWING_PRECISION["PressZone"] == {
        "PressZoneLen": 2,
        "PressZoneDia": 3,
    }
    assert "PressZoneEnd" not in set().union(*part.DRAWING_DIMENSIONS.values())
    # The sheet places the zone's dims by the engagement, not the collar length.
    assert drawing._PRESS_ZONE_MID_X == pytest.approx(
        drawing._ROD_TIP_X - (press.ROD_DIA / 2.0 + press.COLLAR_ENGAGEMENT / 2.0) / 1000.0
    )
    assert drawing.REFERENCE_CALLOUTS["PressZoneLen"] == "PRESS ZONE"


def test_press_zone_callout_ties_the_zone_to_the_bracket_bore() -> None:
    """Review item 5 / code-review nit: the banded zone's callout names the
    mating MHA-MG-001 bore, its band and the interference, every number
    derived from mg_lever_press_fit_geom in the spec -- the sheet carries no
    manufacturing string of its own (_drawing_contract)."""
    import mg_lever_press_fit_geom as press
    from _drawing_contract import drawing_specification_violations

    callout = mg_magnifying_lever_spec.PRESS_ZONE_DIA_CALLOUT
    assert drawing.REFERENCE_CALLOUTS["PressZoneDia"] is callout
    assert callout == (
        "IN MHA-MG-001<MOD-DIAM>5.986 +0.006/0 BORE: 0.002-0.014 INTERFERENCE"
    )
    assert f"{press.COLLAR_BORE_DIA:.3f}" in callout
    assert f"{press.PRESS_FIT_BUDGET['interference_min']:.3f}-" in callout
    assert f"{press.PRESS_FIT_BUDGET['interference_max']:.3f} INTERFERENCE" in callout
    script = Path(drawing.__file__)
    assert not drawing_specification_violations(
        script.read_text(encoding="utf-8"), filename=script.name
    )


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
        "set_dimension_prefix",
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
    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as geom

    assert (press.ROD_DIA, geom.ROD_LENGTH) == (6.0, 165.0)
    assert mg_magnifying_lever_spec.ROD_LENGTH is geom.ROD_LENGTH
    assert mg_magnifying_lever_spec.PRESS_ZONE_LENGTH is press.PRESS_ZONE_LENGTH
    assert hasattr(geom, "KNIFE_LOCAL_X") and hasattr(geom, "KNIFE_LOCAL_Y")
    assembly = (
        Path(part.__file__)
        .with_name("build_mg_magnifier_assembly.py")
        .read_text(encoding="utf-8")
    )
    assert "from mg_magnifying_lever_geom import (" in assembly
    assert "KNIFE_LOCAL_X," in assembly
    assert "KNIFE_LOCAL_Y," in assembly


def test_linked_notes_specify_round_brass_stock_and_the_press() -> None:
    import mg_lever_press_fit_geom as press

    notes = mg_magnifying_lever_spec.DRAWING_NOTES
    assert "Ø6 ROUND BAR" in notes
    assert "BRASS" not in notes and "C36000" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    # Review item 6: the dome is the native R3 "BOTH ENDS"; no restatement.
    assert "HEMISPHERE" not in notes and "R3" not in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    assert f"({part.ROD_LENGTH:g}) REF" in notes
    assert f"PRESS ZONE START ({press.PRESS_ZONE_LENGTH:g}) FROM TIP REF" in notes
    # The press zone's size and band are native dims; the note says how to
    # hold it, how the collar is pressed on and the fit contract's worst-case
    # force (never typed). The Loctite retention is the bracket sheet's.
    assert "PRESS ZONE" in notes and "MHA-MG-001" in notes
    assert "LOCTITE" not in notes and "638" not in notes
    for banned in (
        press.COLLAR_BORE_DIA,
        press.PRESS_ZONE_DIA + press.PRESS_ZONE_DIA_BAND[1],
        abs(press.PRESS_ZONE_DIA_BAND[1]),
        press.COLLAR_BORE_BAND[0],
    ):
        assert f"{banned:.3f}" not in notes
    assert f"{press.PRESS_FORCE_MAX_KN:.1f} kN MAX" in notes
    assert "ROD HELD NEAR ITS END" in notes
    assert len(notes.splitlines()) <= 4
    assert max(len(line) for line in notes.splitlines()) <= 80
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


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
