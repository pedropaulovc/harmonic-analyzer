"""Offline contracts for the magnifying-wheel drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import build_mg_magnifying_wheel as part
import draw_mg_magnifying_wheel as drawing
import mg_magnifying_wheel_geom as geom
import mg_magnifying_wheel_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _called_names(path: str) -> list[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return [
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    ]


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-wheel.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-wheel.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-wheel_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_wheel"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is mg_magnifying_wheel_spec.DRAWING_DIMENSIONS
    marked = set().union(*mg_magnifying_wheel_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_every_marked_dimension_has_model_places() -> None:
    spec = mg_magnifying_wheel_spec
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        name: digits
        for names in spec.DRAWING_PRECISION.values()
        for name, digits in names.items()
    }
    # The press-fit spigot and the reamed bore print their microns.
    assert spec.DRAWING_PRECISION["HubProfile"]["SpigotDia"] == 3
    assert spec.DRAWING_PRECISION["BoreProfile"]["BoreDiaDim"] == 3


def test_tight_bands_sit_on_the_model_dimensions() -> None:
    assert model_toleranced_dimensions(part) == {
        ("HubProfile", "HubDia"): "*deviations(HUB_DIA_BAND)",
        ("HubProfile", "HubLength"): "*deviations(HUB_LEN_BAND)",
        ("HubProfile", "SpigotDia"): "*deviations(SPIGOT_BAND)",
        ("HubProfile", "SpigotLength"): "*deviations(SPIGOT_LEN_BAND)",
        ("GrooveProfile", "GrooveR"): "*deviations(GROOVE_R_BAND)",
        ("GrooveProfile", "GrooveBottomDia"): "*deviations(GROOVE_BOTTOM_BAND)",
        ("BoreProfile", "BoreDiaDim"): "*deviations(BORE_BAND)",
        ("Tie1Profile", "Tie1HoleDia"): "*deviations(TIE_HOLE_BAND)",
        ("Tie2Profile", "Tie2HoleDia"): "*deviations(TIE_HOLE_BAND)",
        ("RimRounds", "CastRoundR"): "*deviations(CAST_ROUND_BAND)",
        ("Tie1Profile", "Tie1Y"): "TIE_POSITION_TOL",
    }


def test_walls_and_groove_hold_at_the_printed_bands() -> None:
    spec = mg_magnifying_wheel_spec
    assert min(spec.WALLS.values()) >= spec.MIN_WALL == 2.0
    assert spec.WALLS["tie2_to_rim_fillet"] == pytest.approx(2.706, abs=1e-3)
    assert spec.WALLS["tie1_to_hub_fillet"] == pytest.approx(2.088, abs=1e-3)
    # TIE 2 breaks into the bore at mid-width: its ligament ends at the R1 MAX
    # rim-bore rounds, which the sheet now prints.
    assert spec.WALLS["tie2_to_rim_faces"] == pytest.approx(2.025, abs=1e-3)
    assert geom.CAST_ROUND_BAND == (0.0, -0.5)
    assert spec.DRAWING_DIMENSIONS["RimRounds"] == {"CastRoundR"}
    # At 4:30 (-45) the worst printed casting leaves TIE 2 about a 1.2 wall.
    assert geom.TIE2_CLOCK_DEG == -43.0
    # The 0.8 pen wire seats at every printed groove corner.
    assert spec.GROOVE_WIDTH_MIN == pytest.approx(1.0)
    assert spec.GROOVE_DEPTH_MIN == pytest.approx(0.895)
    # The drum, minus-only against the plus-only spigot, is never proud.
    assert geom.DRUM_RECESS == pytest.approx((0.0, 0.2))


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hub stations the assembly imports live in the drawing-FREE geom
    # module, so a print-note edit cannot enter the assembly recipe.
    assert (geom.RIM_OUTER_DIA, geom.HUB_DIA, geom.SPOKE_COUNT) == (100.0, 25.0, 6)
    assembly = Path(part.__file__).with_name("build_mg_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from mg_magnifying_wheel_geom import" in assembly
    assert "from build_mg_magnifying_wheel import" not in assembly


def test_feature_volumes_are_consistent() -> None:
    # The fillet gates sum to the geom's own fillet volume; the groove matches
    # a direct section integral; TIE 2 is a Ø1 hole a little over the floor wall.
    assert part.V_HUB_FILLETS + part.V_RIM_FILLETS == pytest.approx(
        geom.fillets_volume()
    )
    floor = geom.GROOVE_BOTTOM_DIA / 2.0 - geom.RIM_INNER_DIA / 2.0
    hole = 3.141592653589793 / 4.0 * geom.TIE_HOLE_DIA**2
    assert hole * floor < part.V_TIE2 < hole * (floor + 2.0 * geom.GROOVE_R)
    assert part.V_GROOVE == pytest.approx(399.45, abs=0.05)
    assert part.V_SPOKE_FREE > part.V_SPOKE_WEB > 0.0


def test_tie2_profile_runs_radially_and_ends_in_air() -> None:
    p_in, p_out, q_out, q_in = part._tie2_profile()
    cross = p_in[0] * p_out[1] - p_in[1] * p_out[0]
    assert cross == pytest.approx(0.0, abs=1e-9)  # the axis passes the origin
    assert q_in[1] == pytest.approx(p_in[1])  # the inner end runs horizontal
    assert part._TIE2_ANGLE == pytest.approx(43.0)
    assert (p_out[0] ** 2 + p_out[1] ** 2) ** 0.5 > geom.GROOVE_BOTTOM_DIA / 2.0
    assert (q_out[0] ** 2 + q_out[1] ** 2) ** 0.5 < geom.RIM_OUTER_DIA / 2.0


def test_linked_notes_specify_the_spokes_and_ties() -> None:
    notes = mg_magnifying_wheel_spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert "6 TAPERED CAST SPOKES" in notes
    assert "TIE 1" in notes and "TIE 2" in notes
    assert "REAMED" in notes
    assert "DO NOT" not in notes and "RELEASE" not in notes
    assert "GRAY-IRON" not in notes and "BLACK" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_no_gdt_frames_and_one_sheet_dimension() -> None:
    calls = _called_names(drawing.__file__)
    assert calls.count("add_datum_feature") == 0
    assert calls.count("add_feature_control_frame") == 0
    assert calls.count("add_surface_finish") == 0
    # Only the rim's axial width is added on the sheet.
    assert calls.count("add_edge_dimension") == 1
    assert "author_part_pmi" not in _called_names(part.__file__)
    assert not hasattr(mg_magnifying_wheel_spec, "SURFACE_FINISHES")
    assert not hasattr(mg_magnifying_wheel_spec, "GEOMETRIC_TOLERANCES_MM")


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-wheel")
    assert config["material"] == config["material_specification"]
    # Paint never reaches a fitted or wire-bearing surface (policy rule 1).
    assert config["finish"] == (
        "BLACK ENAMEL; MASK BORE, SPIGOT, FACED HUB ENDS AND TURNED RIM WITH "
        "ITS GROOVE; OIL BARE MACHINED SURFACES"
    )
    assert int(config["quantity"]) == 1
