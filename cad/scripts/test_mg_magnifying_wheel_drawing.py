"""Offline contracts for the magnifying-wheel drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import build_mg_magnifying_wheel as part
import draw_mg_magnifying_wheel as drawing
import sh_vn_music_wire_lever_geom
import mg_magnifying_wheel_geom as geom
import _mg_wheel_rim_geometry as rim
import mg_magnifying_wheel_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED_UM


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
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.SECTION_KEEP)
        | set(drawing.SECTION_DIAMETER_KEEP)
    )
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.SECTION_KEEP)
    # The rim's Ø print on A-A from the hidden reference sketch alone.
    assert set(drawing.SECTION_DIAMETER_KEEP) == set(
        mg_magnifying_wheel_spec.DRAWING_DIMENSIONS[
            mg_magnifying_wheel_spec.DIAMETER_REFERENCE
        ]
    )
    assert not set(drawing.SECTION_DIAMETER_KEEP) & (
        set(drawing.FRONT_KEEP) | set(drawing.SECTION_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS) | set(drawing.CALLOUTS_ABOVE) <= kept


def test_rim_diameters_ride_the_hidden_section_reference() -> None:
    build = Path(part.__file__).read_text(encoding="utf-8")
    blank = "blank_reference_sketches(adapter, REFERENCE_SKETCHES)"
    assert build.count(blank) == 1
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    # A diametric linear dimension prints no Ø unless the prefix carries it.
    assert (
        'set_dimension_prefix(adapter, DIAMETER_REFERENCE, name, "<MOD-DIAM>")' in build
    )
    # A-A is cut and curated while the part shows the diameter reference
    # alone (the spoke reference would print in the cut), through the face it
    # is cut from; the isometric is placed after the re-blank.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    block = source.index("with _drawing_hidden_sketches.part_sketches_shown(")
    header = source[block : source.index("):", block)]
    assert "(DIAMETER_REFERENCE,)" in header and "base_view=front" in header
    assert (
        block
        < source.index("section = create_section_view(")
        < source.index("_drawing_hidden_sketches.curate_view_dimensions(")
        < source.index('iso = place_view(adapter, str(SOURCE), "*Isometric"')
    )


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
    # The spigot and the bore are matched fits: a reference nominal, the
    # acceptance on the callout.  The web's plane, cast, prints .61 +/-.03.
    assert spec.REFERENCE_DIMENSIONS == {"SpigotDia", "BoreDiaDim"}
    print_shift = 0.03 * 25.4 + abs(-0.61 * 25.4 - geom.HUB_FRONT_Z)
    route_gaps = sh_vn_music_wire_lever_geom.run_gaps(
        sh_vn_music_wire_lever_geom.WIRE_START, sh_vn_music_wire_lever_geom.WIRE_END
    )
    expected_gap = min(route_gaps["rim"], route_gaps["spokes"]) - print_shift
    assert spec.LEVER_WIRE_WEB_GAP == pytest.approx(expected_gap, abs=1e-9)
    assert spec.LEVER_WIRE_WEB_GAP >= sh_vn_music_wire_lever_geom.CLEARANCE


def test_tight_bands_sit_on_the_model_dimensions() -> None:
    # The boss Ø and TIE 1's two coordinates ride the title block's .XX: the
    # boss is sized for TIE 1's wall, so none carries a band of its own.
    assert model_toleranced_dimensions(part) == {
        ("HubProfile", "HubLength"): "HUB_LEN_BAND[0]",
        ("HubProfile", "SpigotLength"): "*deviations(SPIGOT_LEN_BAND)",
        ("GrooveProfile", "GrooveR"): "GROOVE_R_BAND[0]",
        ("GrooveProfile", "GrooveBottomDia"): "GROOVE_BOTTOM_BAND[0]",
        ("feature_name", "dimension_name"): "CAST_TOL",
    }
    # The as-cast sizes carry the explicit +/-.03 casting band.
    assert geom.CAST_TOL == pytest.approx(0.03 * 25.4)
    precision = mg_magnifying_wheel_spec.DRAWING_PRECISION
    assert precision["HubProfile"]["HubDia"] == 2
    assert precision["Tie1Profile"]["Tie1X"] == precision["Tie1Profile"]["Tie1Y"] == 2


def test_walls_and_groove_hold_at_the_printed_bands() -> None:
    spec = mg_magnifying_wheel_spec
    inch = 25.4
    # Every wall holds rule 17's .080 in target at the printed limits.
    assert min(spec.WALLS.values()) >= spec.MIN_WALL - 1e-9
    assert spec.MIN_WALL == pytest.approx(0.080 * inch)
    # TIE 1's axis may stand off by both .XX coordinates' +/-.01, and tilt by
    # the title block's 1 deg plus 0.3 deg drill wander over the boss (the
    # hub's .775 max less the spigot's .354 min).
    offset = math.hypot(0.01 * inch, 0.01 * inch) + (0.775 - 0.354) * inch * math.tan(
        math.radians(1.3)
    )
    assert geom.TIE1_OFFSET_MAX == pytest.approx(offset)
    tie1_r = math.hypot(0.38, 0.22) * inch
    assert geom.TIE1_R == pytest.approx(tie1_r)
    # The #60 ties at the title block's drilled row, .040 +.004.
    tie_r_max = (0.040 + 0.004) * inch / 2.0
    assert spec.WALLS["tie1_to_hub_od"] == pytest.approx(
        (1.18 - 0.01) * inch / 2.0 - (tie1_r + offset) - tie_r_max
    )
    # The cast spokes, fillets and rim bore at their +/-.03 casting band.
    assert spec.WALLS["tie2_to_rim_fillet"] == pytest.approx(2.602, abs=1e-3)
    assert spec.WALLS["tie1_to_hub_fillet"] == pytest.approx(2.824, abs=1e-3)
    # TIE 1 stands outboard of the drum it sits behind: the smallest hole,
    # at its worst offset, still opens a wire diameter past the largest drum
    # (.74 + .01).
    assert geom.TIE1_DRUM_OPENING == pytest.approx(
        tie1_r - offset + 0.020 * inch - 0.75 * inch / 2.0
    )
    assert geom.TIE1_DRUM_OPENING >= geom.LEVER_WIRE_DIA
    # 8 o'clock seen from the front, midway between two spokes.
    assert geom.TIE1_CLOCK_DEG == pytest.approx(-150.0, abs=0.1)
    # TIE 2 breaks into the bore at mid-width: its ligament ends at the
    # rim-bore rounds, R.03 MAX (no model band), on a rim .31 wide at .XX.
    assert spec.WALLS["tie2_to_rim_faces"] == pytest.approx(2.462, abs=1e-3)
    assert geom.CAST_ROUND_R == pytest.approx(0.03 * inch)
    assert not hasattr(geom, "CAST_ROUND_BAND")
    assert spec.ROUND_TEXT_SUFFIX == " MAX"
    # The matched fits' worst pair: the smallest spigot (.4990 bore + .0002
    # press) over the largest bore (.1877 pin + .0017 running clearance).
    assert spec.WALLS["spigot_to_bore"] == pytest.approx((0.4992 - 0.1894) * inch / 2.0)
    assert "RimRounds" not in spec.DRAWING_DIMENSIONS
    assert geom.TIE2_CLOCK_DEG == -43.0
    # The 0.8 pen wire seats at every printed groove corner: R.024 -.004 wide,
    # and the 3.94 -.01 rim over the 3.843 +.004 groove bottom deep.
    assert spec.GROOVE_WIDTH_MIN == pytest.approx(2.0 * 0.020 * inch)
    assert spec.GROOVE_DEPTH_MIN == pytest.approx((3.93 - 3.847) * inch / 2.0)
    # The drum, minus-only against the plus-only spigot, is never proud.
    assert geom.DRUM_RECESS == pytest.approx((0.0, 0.008 * inch), abs=1e-9)


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hub stations the assembly imports live in the drawing-FREE geom
    # module, so a print-note edit cannot enter the assembly recipe.
    assert (rim.RIM_OUTER_DIA, geom.HUB_DIA, geom.SPOKE_COUNT) == (100.0, 30.0, 6)
    assembly = Path(part.__file__).with_name("build_mg_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from mg_magnifying_wheel_geom import" in assembly
    assert "from build_mg_magnifying_wheel import" not in assembly


def test_feature_volumes_are_consistent() -> None:
    # The fillet gates sum to the geom's own fillet volume; the groove matches
    # a direct section integral; TIE 2 is a #60 hole a little over the floor wall.
    assert part.V_HUB_FILLETS + part.V_RIM_FILLETS == pytest.approx(
        geom.fillets_volume()
    )
    floor = rim.GROOVE_BOTTOM_DIA / 2.0 - rim.RIM_INNER_DIA / 2.0
    hole = 3.141592653589793 / 4.0 * geom.TIE_HOLE_DIA**2
    assert hole * floor < part.V_TIE2 < hole * (floor + 2.0 * rim.GROOVE_R)
    assert part.V_GROOVE == pytest.approx(405.07, abs=0.05)
    assert part.V_SPOKE_FREE > part.V_SPOKE_WEB > 0.0


def test_tie2_profile_runs_radially_and_ends_in_air() -> None:
    p_in, p_out, q_out, q_in = part._tie2_profile()
    cross = p_in[0] * p_out[1] - p_in[1] * p_out[0]
    assert cross == pytest.approx(0.0, abs=1e-9)  # the axis passes the origin
    assert q_in[1] == pytest.approx(p_in[1])  # the inner end runs horizontal
    assert part._TIE2_ANGLE == pytest.approx(43.0)
    assert (p_out[0] ** 2 + p_out[1] ** 2) ** 0.5 > rim.GROOVE_BOTTOM_DIA / 2.0
    assert (q_out[0] ** 2 + q_out[1] ** 2) ** 0.5 < rim.RIM_OUTER_DIA / 2.0
    # The driven Tie2Angle reads the ACUTE angle: its text point lies between
    # the axis ray and the horizontal ray (same x side) from P_in.
    tx, ty = part._TIE2_ANGLE_TEXT
    bearing = math.degrees(math.atan2(ty - p_in[1], tx - p_in[0]))
    axis = math.degrees(math.atan2(p_out[1] - p_in[1], p_out[0] - p_in[0]))
    horizontal = 0.0 if p_out[0] > p_in[0] else 180.0
    low, high = sorted((axis % 360.0, horizontal % 360.0))
    assert high - low == pytest.approx(part._TIE2_ANGLE)
    assert low < bearing % 360.0 < high


@pytest.mark.parametrize(
    ("circle_r", "printed", "fillet_name"),
    [
        ("_HUB_R", "HUB_FILLET_PRINTED", "_HUB_FILLET"),
        ("_RIM_IN_R", "RIM_FILLET_PRINTED", "_RIM_FILLET"),
    ],
)
def test_each_fillet_r_prints_on_the_builders_first_pick(
    circle_r: str, printed: str, fillet_name: str
) -> None:
    # The imported R lands on the first pick's edge, so the drawing's landing
    # proof must target the fillet the builder picks first.
    picks = part._spoke_edge_picks(
        getattr(part, circle_r), getattr(mg_magnifying_wheel_spec, printed)
    )
    centre = getattr(drawing, fillet_name)[0]
    gaps = [math.dist(pick[:2], centre) for pick in picks]
    assert len(picks) == 12 and min(gaps) == gaps[0]


def test_linked_notes_specify_the_ties_and_the_angle_the_spokes() -> None:
    spec = mg_magnifying_wheel_spec
    notes = spec.DRAWING_NOTES
    lines = notes.splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 80 for line in lines)
    assert "SPOKES" not in notes and "CAST" not in notes
    # The spokes' count, pitch and clocking print on their own angle between
    # two spoke centrelines: two on the centerline TIE 2's angle is measured
    # from (the model's seed spoke on local +X).
    assert spec.SPOKE_PITCH_PREFIX == "6X " and spec.SPOKE_PITCH_DEG == 60.0
    assert spec.DRAWING_PRECISION[spec.SPOKE_REFERENCE] == {"SpokePitch": 0}
    assert "SpokePitch" in drawing.FRONT_KEEP
    assert drawing.CALLOUTS_ABOVE["SpokePitch"] == "TWO ON THE HORIZONTAL CENTERLINE"
    assert spec.SPOKE_REFERENCE in spec.REFERENCE_SKETCHES
    assert "TIE 1" in notes and "TIE 2" in notes
    # The bore's REAM THRU callout carries the process; the notes do not.
    assert "REAMED" not in notes
    # Each fit prints on its own diameter: the mate and the stated fit.
    assert "PRESS FIT" not in notes and "RUNS ON" not in notes
    # Each groove band names the wire it seats, at its own callout.
    assert (
        drawing.DIMENSION_CALLOUTS["GrooveBottomDia"] == "PEN-WIRE SEAT\nMHA-SH-VN-56"
    )
    assert drawing.CALLOUTS_ABOVE["GrooveR"] == "PEN-WIRE SEAT MHA-SH-VN-56"
    assert drawing.ROUND_CALLOUT.endswith("\nHOLDS TIE 2 WALL")
    assert drawing.CALLOUTS_ABOVE["HubLength"] == "MHA-MG-07 LOCKNUT STACK"
    # An above-callout prints one line only.
    assert not any("\n" in text for text in drawing.CALLOUTS_ABOVE.values())
    assert drawing.CALLOUTS_ABOVE["SpigotLength"] == "MG-WHEEL-DRUM MHA-MG-10 NOT PROUD"
    assert drawing.DIMENSION_CALLOUTS["Tie2HoleDia"].endswith("\nRADIAL")
    assert drawing.CALLOUTS_ABOVE["HubFrontZ"] == "GROOVE, WEB & RIM CENTER"
    assert drawing.DIMENSION_CALLOUTS["RimOuterDiaDim"].startswith("HOLDS PEN WIRE")
    # TIE 1 stands off the drum; the note says so without a number.
    assert "CLEAR OF MG-WHEEL-DRUM" in notes and "BAND" not in notes
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
    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the running bore takes the machined grade; the
    # spigot is pressed into the drum and takes none.
    finishes = {
        control.key: control.roughness_um
        for control in mg_magnifying_wheel_spec.SURFACE_FINISHES
    }
    assert finishes == {"mg_wheel_bore": MACHINED_UM}
    # Only the rim's axial width is added on the sheet.
    assert calls.count("add_edge_dimension") == 1
    assert not hasattr(mg_magnifying_wheel_spec, "GEOMETRIC_TOLERANCES_MM")


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-wheel")
    assert config["material"] == config["material_specification"]
    # Paint never reaches a fitted or wire-bearing surface (drawing-guidelines.md rule 2 (the title block is the general specification)).
    assert config["finish"] == (
        "BLACK ENAMEL; MASK BORE, SPIGOT, HUB ENDS, RIM AND GROOVE; OIL BARE SURFACES"
    )
    assert int(config["quantity"]) == 1
