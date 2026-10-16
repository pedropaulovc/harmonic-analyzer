"""Offline contracts for the magnifying-lever drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

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
    kept = set(drawing.FRONT_KEEP) | set(drawing.REFERENCE_KEEP)
    assert kept == marked
    assert marked == {
        "OverallLength",
        "DomeRadius",
        "RodDia",
        "PressZoneStart",
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
        "PressZoneStart",
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
    prefix the point-form diametric dims need (v41 sheet).  Retry09 review:
    it carries the cold-drawn bar's own h9 band, which contains the press
    zone's tighter band on the same unstepped cylinder."""
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
    assert mg_magnifying_lever_spec.ROD_DIA_BAND == (0.0, -0.03)
    assert part.ROD_DIA_BAND is mg_magnifying_lever_spec.ROD_DIA_BAND
    body_low, body_high = (
        press.ROD_DIA + mg_magnifying_lever_spec.ROD_DIA_BAND[1],
        press.ROD_DIA + mg_magnifying_lever_spec.ROD_DIA_BAND[0],
    )
    zone_low, zone_high = (
        press.PRESS_ZONE_DIA + press.PRESS_ZONE_DIA_BAND[1],
        press.PRESS_ZONE_DIA + press.PRESS_ZONE_DIA_BAND[0],
    )
    assert body_low <= zone_low <= zone_high <= body_high
    assert '"RodStock", "RodDia", *deviations(ROD_DIA_BAND)' in source
    assert "RodDiaStation" not in set().union(*part.DRAWING_DIMENSIONS.values())
    assert "RodStockAxis" not in set().union(*part.DRAWING_DIMENSIONS.values())
    assert drawing.REFERENCE_CALLOUTS["RodDia"] == "STOCK OD"
    # The dome radius is a reference now; its callout states the shape that
    # governs it, never the full radius or the rod diameter.
    assert drawing.DIMENSION_CALLOUTS["DomeRadius"] == "BOTH ENDS\nTANGENT HEMISPHERE"
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
    assert budget["engagement"] == press.COLLAR_ENGAGEMENT_MAX
    # Whole-contact envelope with independent, deliberately conservative corners:
    # the longest collar less the smallest dome radius (the straight cylinder at
    # its longest), plus the part of the largest dome still outside the smallest
    # bore. Not one physical part (the coupled tight corner is 7.204819).
    collar_max, dome_min = 10.0 + 0.0, (6.0 - 0.006) / 2.0
    dome_max, bore_min = (6.0 + 0.0) / 2.0, (5.986 + 0.0) / 2.0
    assert budget["engagement"] == pytest.approx(
        collar_max - dome_min + math.sqrt(dome_max**2 - bore_min**2)
    )
    assert budget["engagement"] == pytest.approx(7.2078194326718075, abs=1e-9)
    assert press.COLLAR_ENGAGEMENT < budget["engagement"] < press.COLLAR_LENGTH
    assert 0.0 < budget["interference_min"] <= budget["interference_max"]
    # ANSI B4.1 FN2 for 0.12..0.24 in: 1.0 thou at the tightest.
    assert press.PRESS_INTERFERENCE_MAX_FN2 == pytest.approx(0.0254)
    assert budget["interference_max"] <= press.PRESS_INTERFERENCE_MAX_FN2
    assert part.PRESS_ZONE_DIA_BAND is press.PRESS_ZONE_DIA_BAND
    # Main's batch10 ruling: the zone's start from the tip carries the
    # drawing-free geom's axial band natively, at .XX, never a spec alias.
    assert part.PRESS_ZONE_LENGTH_BAND is press.PRESS_ZONE_LENGTH_BAND
    assert not hasattr(mg_magnifying_lever_spec, "PRESS_ZONE_START_BAND")
    assert not hasattr(mg_magnifying_lever_spec, "PRESS_ZONE_LENGTH_BAND")
    assert part.PRESS_ZONE_X is geom.PRESS_ZONE_X
    # Retry09 review: the zone is located from the rod TIP -- PRESS_ZONE_LENGTH
    # back to its start -- and runs to the dome tangent, so its banded
    # cylinder is ONLY the straight engagement, never the R3 dome.
    assert geom.ROD_LENGTH - part.PRESS_ZONE_X[0] == press.PRESS_ZONE_LENGTH
    assert part.PRESS_ZONE_END == geom.ROD_LENGTH - press.ROD_DIA / 2.0 == 162.0
    assert part.PRESS_ZONE_END - part.PRESS_ZONE_X[0] == press.COLLAR_ENGAGEMENT
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "PressZone")' in source
    assert '"PressZone", "PressZoneDia", *deviations(PRESS_ZONE_DIA_BAND)' in source
    # Point-form diametric dims print no Ø of their own (v41 sheet).
    assert 'set_dimension_prefix(adapter, "PressZone", "PressZoneDia", "<MOD-DIAM>")' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "segment.ConstructionGeometry = True" in source
    # The axis runs from the zone start to the tip; the witness rides the
    # bottom outline from the zone start to the tangent.
    assert "add_centerline(PRESS_ZONE_X[0], 0.0, ROD_LENGTH, 0.0)" in source
    assert "add_line(PRESS_ZONE_X[0], -R, PRESS_ZONE_END, -R)" in source
    assert (
        'f"{zone_axis}.end",\n        "origin",\n        "horizontal_distance",\n'
        '        ROD_LENGTH,\n        "press zone PressZoneTip",'
    ) in source
    assert (
        'f"{zone_witness}.start",\n        f"{zone_axis}.end",\n'
        '        "horizontal_distance",\n        PRESS_ZONE_LENGTH,\n'
        '        "press zone PressZoneStart",'
    ) in source
    assert (
        '"horizontal_distance",\n        COLLAR_ENGAGEMENT,\n        "press zone PressZoneLen",'
        in source
    )
    assert 'zone.record("PressZoneTip", \'"RodLength"\')' in source
    assert 'zone.record("PressZoneStart", \'"CollarLen"\')' in source
    assert 'zone.record("PressZoneLen", \'"CollarLen" - "RodDia" / 2\')' in source
    assert 'zone.record("PressZoneDia", \'"RodDia"\')' in source
    assert "PressZoneEnd" not in source
    assert 'set_global(adapter, "CollarLen", f"{PRESS_ZONE_LENGTH}mm")' in source
    assert mg_magnifying_lever_spec.DRAWING_PRECISION["PressZone"] == {
        "PressZoneStart": 2,
        "PressZoneLen": 1,
        "PressZoneDia": 3,
    }
    assert (
        '"PressZone", "PressZoneStart", *deviations(PRESS_ZONE_LENGTH_BAND)' in source
    )
    assert "PressZoneTip" not in set().union(*part.DRAWING_DIMENSIONS.values())
    # The cylinder's length (start less the dome radius) prints as a LINEAR
    # reference; the start from the tip is the toleranced value.
    assert mg_magnifying_lever_spec.REFERENCE_DIMENSIONS == {"PressZoneLen"}
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimension(adapter, matches[0]" in sheet_source
    assert "set_reference_dimensions(" not in sheet_source
    assert "PressZoneLen" not in drawing.REFERENCE_CALLOUTS
    assert drawing.REFERENCE_CALLOUTS["PressZoneStart"] == "PRESS ZONE START"
    # The sheet's stations come from the same constants as the model's.
    assert drawing._PRESS_ZONE_START_X == pytest.approx(
        drawing._ROD_TIP_X - press.PRESS_ZONE_LENGTH / 1000.0
    )
    assert drawing._DOME_TANGENT_X == pytest.approx(
        drawing._ROD_TIP_X - press.ROD_DIA / 2000.0
    )
    assert drawing._DOME_TANGENT_X - drawing._PRESS_ZONE_START_X == pytest.approx(
        press.COLLAR_ENGAGEMENT / 1000.0
    )


def test_overall_length_runs_tip_to_tip_on_the_profile() -> None:
    """Retry09 review: the far dome centre (162.00) cannot be picked up; the
    profile dimensions the rod between its two dome tips -- the axis line's
    ends, merged with the apexes (build_ch_fulcrum_shaft's idiom) -- at .X,
    and the right dome's centre is only placed on the axis, R back from the
    tip by the radial dim."""
    import mg_lever_press_fit_geom as press

    assert mg_magnifying_lever_spec.DRAWING_DIMENSIONS["RodProfile"] == {
        "OverallLength",
        "DomeRadius",
    }
    assert mg_magnifying_lever_spec.DRAWING_PRECISION["RodProfile"] == {
        "OverallLength": 1,
        "DomeRadius": 1,
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        'f"{axis_line}.start",\n        f"{axis_line}.end",\n'
        '        "horizontal_distance",\n        ROD_LENGTH,\n'
        '        "rod OverallLength",'
    ) in source
    assert 'profile.record("OverallLength", \'"RodLength"\')' in source
    assert 'f"{cap_right}.center", "origin", "horizontal_points"' in source
    assert "RightDomeCentre" not in source
    assert part.R == press.ROD_DIA / 2.0
    assert "OverallLength" not in drawing.DIMENSION_CALLOUTS
    assert "TO FAR DOME CENTRE" not in drawing.DIMENSION_CALLOUTS.values()


def test_dome_radius_is_a_radial_reference_of_the_tangent_hemisphere() -> None:
    """Main's batch10 ruling: each dome is a full hemisphere tangent to the
    selected bar, so its radius follows the zone diameter (R2.997 at the
    smallest selected bar) and prints as a radial REFERENCE "(R3.0)": the
    display's own radius glyph is kept behind the "(" (the singular
    set_reference_dimension's bare "(" would replace it, the plural one would
    print a Ø)."""
    import mg_lever_press_fit_geom as press

    assert mg_magnifying_lever_spec.RADIAL_REFERENCE_DIMENSIONS == {"DomeRadius"}
    assert not (
        mg_magnifying_lever_spec.RADIAL_REFERENCE_DIMENSIONS
        & mg_magnifying_lever_spec.REFERENCE_DIMENSIONS
    )
    assert "DomeRadius" in drawing.FRONT_KEEP
    min_radius = (press.PRESS_ZONE_DIA + press.PRESS_ZONE_DIA_BAND[1]) / 2.0
    assert f"{min_radius:.1f}" == f"{part.R:.1f}" == "3.0"
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'profile.record("DomeRadius", \'"RodDia" / 2\')' in source
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_set_radial_reference(adapter, matches[0]" in sheet_source
    assert 'prefix = "(" + existing' in sheet_source
    assert "for name in sorted(RADIAL_REFERENCE_DIMENSIONS):" in sheet_source
    assert "<MOD-DIAM>" not in sheet_source


def test_press_zone_text_clears_its_lines_and_the_isometric() -> None:
    """Retry09 review: the zone diameter's rows sat on its own dimension
    line.  Its line now stands inside the zone and its rows hang above the
    rod, right of that line (layout doc: rows hang from a shoulder that starts
    at the line), above the dome radius; the zone's lengths print below the
    rod off the bottom witness, the reference innermost and left of its span,
    the start from the tip outside it and right of the tip, the overall length
    outermost."""
    rod_bottom_y = drawing.FRONT_CENTER[1] - drawing.ROD_DIA / 2000.0
    dia_x, dia_y = drawing.REFERENCE_KEEP["PressZoneDia"]
    assert drawing._PRESS_ZONE_START_X < dia_x < drawing._DOME_TANGENT_X
    assert dia_y > drawing.FRONT_KEEP["DomeRadius"][1] + 0.015
    assert drawing.FRONT_KEEP["DomeRadius"][0] > drawing._ROD_TIP_X
    assert drawing.FRONT_KEEP["DomeRadius"][1] > drawing._ROD_TOP_Y
    length_x, length_y = drawing.REFERENCE_KEEP["PressZoneLen"]
    start_x, start_y = drawing.REFERENCE_KEEP["PressZoneStart"]
    overall_y = drawing.FRONT_KEEP["OverallLength"][1]
    assert overall_y < start_y < length_y < rod_bottom_y
    assert length_x < drawing._PRESS_ZONE_START_X
    assert start_x > drawing._ROD_TIP_X
    # Two rows, so the mate callout stays short of the isometric.
    rows = mg_magnifying_lever_spec.PRESS_ZONE_DIA_CALLOUT.split("\n")
    assert len(rows) == 2
    assert max(len(row.replace("<MOD-DIAM>", "Ø")) for row in rows) <= 36
    assert drawing.ISO_CENTER == (0.350, 0.185)



def test_press_zone_callout_ties_the_zone_to_the_bracket_bore() -> None:
    """Review item 5 / code-review nit: the banded zone's callout names the
    mating MHA-MG-001 bore as the REFERENCE nominal that sheet prints and the
    matched-fit interference its callout states (rule 25: the sheets agree;
    the bore carries no absolute band), every number derived from
    mg_lever_press_fit_geom in the spec -- the sheet carries no
    manufacturing string of its own (_drawing_contract)."""
    import mg_lever_press_fit_geom as press
    import mg_magnifying_bracket_spec as bracket_spec
    from _drawing_contract import drawing_specification_violations

    callout = mg_magnifying_lever_spec.PRESS_ZONE_DIA_CALLOUT
    assert drawing.REFERENCE_CALLOUTS["PressZoneDia"] is callout
    assert callout == (
        "IN MHA-MG-001 (<MOD-DIAM>5.986) BORE:\n0.002-0.014 DIAMETRAL INTERFERENCE"
    )
    assert f"(<MOD-DIAM>{press.COLLAR_BORE_DIA:.3f})" in callout
    assert "/" not in callout and "+0.006" not in callout
    interference = (
        f"{press.PRESS_FIT_BUDGET['interference_min']:.3f}-"
        f"{press.PRESS_FIT_BUDGET['interference_max']:.3f}"
    )
    assert f"{interference} DIAMETRAL INTERFERENCE" in callout
    # The bracket sheet's bore callout states the same matched fit.
    assert interference in bracket_spec.COLLAR_BORE_CALLOUT
    assert "DIAMETRAL INTERFERENCE" in bracket_spec.COLLAR_BORE_CALLOUT
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
        "author_part_pmi",
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


def test_linked_notes_select_the_press_zone_and_say_how_to_press() -> None:
    """Retry09 review: the stock line, the overall length and the zone's
    start are native now, and the OD finish is the part's symbol; the notes
    keep only the zone's selection (lapping cannot enlarge an undersize bar)
    and the press."""
    import mg_lever_press_fit_geom as press

    notes = mg_magnifying_lever_spec.DRAWING_NOTES
    assert "ROUND BAR" not in notes and "REF" not in notes
    assert "STRAIGHT" not in notes and "Ra" not in notes
    assert "SELECT OR LAP" in notes
    assert "LAPPING CANNOT ENLARGE UNDERSIZE STOCK" in notes
    assert "LOWER LIMIT" in notes
    assert "BRASS" not in notes and "C36000" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    # Review item 6: the dome is the native R3 "BOTH ENDS"; no restatement.
    assert "HEMISPHERE" not in notes and "R3" not in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    assert f"{part.ROD_LENGTH:g}" not in notes
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
    assert f"{abs(mg_magnifying_lever_spec.ROD_DIA_BAND[1]):.2f}" not in notes
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
    assert drawing.ISO_SCALE == (1, 2)
    assert "scale=ISO_SCALE" in source
    assert mg_magnifying_lever_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    # Retry09 review: the featureless end view is gone, with its scale note.
    assert '"*Right"' not in source and "End View Note" not in source
    assert "auto_center_marks" not in source
    assert not hasattr(drawing, "RIGHT_KEEP") and not hasattr(drawing, "RIGHT_CENTER")
    assert not hasattr(mg_magnifying_lever_spec, "END_VIEW_NOTE")
    assert "End View Note" not in Path(part.__file__).read_text(encoding="utf-8")


def test_od_finish_is_the_parts_native_symbol_on_the_od_face() -> None:
    """Retry09 review: the Ra note becomes the part-owned finish control
    (the clamp block slides on the OD), projected with the audited helper;
    the capsule still carries no datum, frame or edge dimension.  Source-644
    native leaf: the silhouette pick's re-read type-46 attachment failed the
    owning-face IsSame proof, so the symbol attaches to the controlled model
    FACE, which IsSame proves directly, and lands its leader on the top
    outline."""
    from _gtol_cylinder import CylinderFace
    from _surface_finish import MACHINED_UM

    (control,) = mg_magnifying_lever_spec.SURFACE_FINISHES
    assert control.key == "rod_od" and control.roughness_um == MACHINED_UM == 1.6
    assert control.face == CylinderFace(mg_magnifying_lever_spec.ROD_DIA)
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in part_source
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    compact = "".join(sheet_source.split())
    assert 'control=surface_finish_by_key(SURFACE_FINISHES,"rod_od")' in compact
    assert 'entity_type="SILHOUETTE"' not in sheet_source
    assert "roughness_ra=" not in sheet_source
    assert sheet_source.count("add_surface_finish(") == 1
    assert sheet_source.count("add_datum_feature(") == 0
    assert sheet_source.count("add_feature_control_frame(") == 0
    assert sheet_source.count("add_edge_dimension(") == 0
    assert not hasattr(drawing, "FINISH_PICK")
    # The landing is on the top outline inside the clamp's travel: past the
    # west dome's tangent, short of the press zone, in part X.
    station_x, outline_y, plane_z = drawing.FINISH_LANDING_MODEL
    assert station_x == drawing.FINISH_STATION_MM / 1000.0
    assert outline_y == mg_magnifying_lever_spec.ROD_DIA / 2000.0
    assert plane_z == 0.0
    west_tangent = mg_magnifying_lever_spec.ROD_DIA / 2.0
    press_zone_start = drawing.ROD_LENGTH - drawing.PRESS_ZONE_LENGTH
    assert west_tangent < drawing.FINISH_STATION_MM < press_zone_start
    # On the 1:1 front view centred on the rod it projects under the symbol,
    # which stands above the rod.
    sheet_x = drawing.FRONT_CENTER[0] + (
        drawing.FINISH_STATION_MM - drawing.ROD_LENGTH / 2.0
    ) * drawing.SHEET_SCALE[0] / 1000.0
    assert sheet_x == pytest.approx(drawing.FINISH_SYMBOL[0])
    assert drawing.FINISH_SYMBOL[1] > drawing._ROD_TOP_Y


def test_od_finish_attaches_the_resolved_face_at_its_landing() -> None:
    """The build hands add_surface_finish the resolved face and its
    projected landing -- never a coordinate hit-test or a silhouette."""
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    calls = [
        node for node in ast.walk(build)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    (finish,) = [node for node in calls if node.func.id == "add_surface_finish"]
    (pick,) = [node for node in calls if node.func.id == "_rod_od_finish_pick"]
    assert [ast.unparse(arg) for arg in pick.args] == ["adapter", "front"]
    assert [ast.unparse(arg) for arg in finish.args] == ["adapter", "front"]
    assigned = next(
        node for node in ast.walk(build)
        if isinstance(node, ast.Assign) and node.value is pick
    )
    (target,) = assigned.targets
    assert [element.id for element in target.elts] == ["od_face", "od_landing"]
    keywords = {kw.arg: ast.unparse(kw.value) for kw in finish.keywords}
    assert keywords["entity"] == "od_face"
    assert keywords["leader_attach_xy"] == "od_landing"
    assert keywords["entity_type"] == "'FACE'"
    assert keywords["symbol_xy"] == "FINISH_SYMBOL"
    assert not {"edge_xy", "edge_entity", "roughness_ra"} & set(keywords)


class _View:
    def __init__(self, document: object) -> None:
        self.ReferencedDocument = document


def test_od_finish_pick_resolves_the_part_control_on_the_referenced_part(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The face is the part PMI's own ``rod_od`` spec, resolved (exactly one
    match) on the part the front view references; the landing is the model
    top-outline point projected through that view."""
    from _gtol_cylinder import CylinderFace

    part_document, od_face, landing = object(), object(), (0.065, 0.153)
    adapter, view = object(), _View(part_document)
    seen: dict[str, tuple[object, ...]] = {}

    def resolve(document: object, requests: dict[str, object]) -> dict[str, object]:
        seen["resolve"] = (document, requests)
        return {"rod_od": od_face}

    def project(
        adapter_: object, view_: object, xyz: tuple[float, ...], *, label: str
    ) -> tuple[float, float]:
        seen["project"] = (adapter_, view_, xyz, label)
        return landing

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "resolve_faces", resolve)
    monkeypatch.setattr(drawing, "model_point_in_view", project)

    assert drawing._rod_od_finish_pick(adapter, view) == (od_face, landing)
    document, requests = seen["resolve"]
    assert document is part_document
    assert requests == {"rod_od": CylinderFace(mg_magnifying_lever_spec.ROD_DIA)}
    adapter_, view_, xyz, label = seen["project"]
    assert adapter_ is adapter and view_ is view
    assert xyz == pytest.approx((0.0325, 0.003, 0.0))
    assert label == "lever rod OD finish landing"


def test_od_finish_pick_fails_closed_when_the_face_does_not_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spec matching zero or several faces (a split or missing OD) stops
    the sheet before anything is selected or projected."""

    def resolve(document: object, requests: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("rod_od: face spec matched 2 faces")

    def project(*_args: object, **_kwargs: object) -> tuple[float, float]:
        raise AssertionError("projected a landing for an unresolved face")

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "resolve_faces", resolve)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    with pytest.raises(RuntimeError, match="matched 2 faces"):
        drawing._rod_od_finish_pick(object(), _View(object()))


class _Annotation:
    """The ``IAnnotation`` readbacks the attachment proofs send."""

    def __init__(
        self,
        entities: tuple[object, ...],
        types: tuple[int, ...],
        *,
        leaders: int = 1,
        dangling: bool = False,
        tip: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        self.entities, self.types = entities, types
        self.leaders, self.dangling, self.tip = leaders, dangling, tip

    def GetAttachedEntities3(self) -> tuple[object, ...]:  # noqa: N802
        return self.entities

    def GetAttachedEntityCount3(self) -> int:  # noqa: N802
        return len(self.entities)

    def GetAttachedEntityTypes(self) -> tuple[int, ...]:  # noqa: N802
        return self.types

    def GetLeaderCount(self) -> int:  # noqa: N802
        return self.leaders

    def IsDangling(self) -> bool:  # noqa: N802
        return self.dangling

    def GetLeaderPointsAtIndex(self, index: int) -> tuple[float, ...]:  # noqa: N802
        assert index == 0
        return (drawing.FINISH_SYMBOL[0], drawing.FINISH_SYMBOL[1], 0.0, *self.tip, 0.0)


class _Silhouette:
    """An ``ISilhouetteEdge``: identified only through its owning face."""

    def __init__(self, face: object) -> None:
        self.face = face

    def GetFace(self) -> object:  # noqa: N802
        return self.face


class _App:
    def IsSame(self, left: object, right: object) -> int:  # noqa: N802
        return int(left is right)


class _Adapter:
    swApp = _App()


_LANDING = (0.065, 0.153)


def _prove(annotation: _Annotation, entity: object, entity_type: str) -> None:
    import _drawing_attachment

    label = "lever rod OD finish"
    _drawing_attachment._assert_attached_to(
        _Adapter(), annotation, entity, entity_type=entity_type,
        what="surface-finish symbol", label=label,
    )
    _drawing_attachment._assert_leader_lands(
        annotation, _LANDING, what="surface-finish symbol", label=label
    )


def test_od_finish_proof_reproduces_the_native_silhouette_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source-644: one live, non-dangling type-46 attachment whose owning
    face is not IsSame the picked silhouette's.  That is no proof of the
    land, and the guard must keep refusing it word for word."""
    import _drawing_attachment

    monkeypatch.setattr(_drawing_attachment, "_early_bound", lambda value, _kind: value)
    picked, reread = _Silhouette(object()), _Silhouette(object())
    with pytest.raises(RuntimeError) as info:
        _prove(_Annotation((reread,), (46,), tip=_LANDING), picked, "SILHOUETTE")
    assert str(info.value) == (
        "surface-finish symbol lost its silhouette attachment (lever rod OD "
        "finish): entities=1, count=1, types=(46,), same_entity=False, "
        "dangling=False, leaders=1"
    )


def test_od_finish_proof_accepts_only_the_resolved_face_at_its_landing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import _drawing_attachment

    monkeypatch.setattr(_drawing_attachment, "_early_bound", lambda value, _kind: value)
    od_face = object()
    _prove(_Annotation((od_face,), (2,), tip=_LANDING), od_face, "FACE")


@pytest.mark.parametrize(
    ("attached", "types", "options", "expected"),
    (
        # A silhouette is not the face, even one OF the face: no type-46
        # attachment passes the FACE proof.
        ("od-silhouette", (46,), {}, "types=(46,)"),
        # The neighbouring dome's sphere, or any other face.
        ("dome", (2,), {}, "same_entity=False"),
        ("od", (2,), {"dangling": True}, "dangling=True"),
        ("od", (2,), {"leaders": 0}, "leaders=0"),
        (None, (), {}, "entities=0"),
        # The right face, landed on the bottom flank (one Ø down).
        ("od", (2,), {"tip": (_LANDING[0], _LANDING[1] - 0.006)}, "attachment moved"),
        # The right face, landed at another station or in another view.
        ("od", (2,), {"tip": (_LANDING[0] + 0.090, _LANDING[1])}, "attachment moved"),
    ),
    ids=(
        "silhouette", "wrong-face", "dangling", "no-leader", "detached",
        "bottom-flank", "wrong-station",
    ),
)
def test_od_finish_proof_rejects_wrong_entity_geometry_or_landing(
    monkeypatch: pytest.MonkeyPatch,
    attached: str | None,
    types: tuple[int, ...],
    options: dict[str, object],
    expected: str,
) -> None:
    import _drawing_attachment

    monkeypatch.setattr(_drawing_attachment, "_early_bound", lambda value, _kind: value)
    od_face = object()
    entities = {
        "od": (od_face,),
        "od-silhouette": (_Silhouette(od_face),),
        "dome": (object(),),
        None: (),
    }[attached]
    annotation = _Annotation(entities, types, **{"tip": _LANDING, **options})
    with pytest.raises(RuntimeError, match=r"\(lever rod OD finish\)") as info:
        _prove(annotation, od_face, "FACE")
    assert expected in str(info.value)


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
    assert "MHA-MG-001" in config["process"]
