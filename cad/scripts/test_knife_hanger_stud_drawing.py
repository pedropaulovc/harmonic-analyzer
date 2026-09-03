"""Offline contracts for the knife-hanger-stud drawing.

A 1/2-13 stud with an integral washer, hex, collar and tip on the shared
fastener recipe after the 2026-09-02 blind machinist review: no datums,
frames, roughness symbols or basic dimensions
(cad/docs/drawing-simplicity-policy.md rules 3-5); every stack size is a
dimension or a leadered callout on a view (the thread designation on the
neck, the hex across-flats and the drilled centre on the end view), the
(REF) overall stands outside the chained lengths, and the profile carries
the axis centerline (rule 7); three lines of note that carry only what the
views cannot say (rule 6).
"""

from __future__ import annotations

import math
from pathlib import Path

import build_knife_hanger_stud as part
import draw_knife_hanger_stud as drawing
import knife_hanger_stud_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import DriveStyle, HeadStyle, fastener
from _holes import TAP_DRILL_MM

BANNED_NOTE_PHRASES = (
    "UOS",
    "DIMENSIONS IN",
    "+/-",
    "DATUM",
    "PERPENDICULAR",
    "RUNOUT",
    "WITHIN",
    "ASME",
    "SYSTEM 21",
    "TAP DRILL",
    "13.49",
    "COSMETIC",
    "DEBURR",
    "BREAK SHARP",
    "TITLE BLOCK",
    "COMMERCIAL",
    "THREAD NOT MODELED",
    "REFERENCE ONLY",
    "TURN AND MILL",
    "-2A",
    " A/F",
    " THICK",
    " DIA X ",
    " DIA ABOVE",
    "CENTER DRILL",
    "DRAWN AT",
)


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/knife-hanger-stud.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/knife-hanger-stud.pdf")
    assert drawing.PNG.as_posix().endswith("/png/knife-hanger-stud_drawing.png")
    assert DRAWINGS_BY_NAME["knife_hanger_stud"].script == (
        Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    # The end view carries the washer and collar diameters (the stack's two
    # larger circles), the side view every stack length plus the shank and
    # tip diameters; together they cover exactly the marked set.
    assert set(drawing.END_KEEP) == set().union(*spec.END_VIEW_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == set().union(*spec.SIDE_VIEW_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert spec.END_VIEW_DIMENSIONS.keys() | spec.SIDE_VIEW_DIMENSIONS.keys() == (
        spec.DRAWING_DIMENSIONS.keys()
    )
    assert set(drawing.END_KEEP) == {"WasherDia", "CollarDia"}
    assert set(drawing.SIDE_KEEP) == {
        "ThreadLg",
        "ShankLg",
        "NutHt",
        "TipLg",
        "WasherT",
        "CollarHt",
        "ShankDia",
        "TipDia",
    }


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("knife-hanger-stud")
    assert spec.THREAD == catalog.thread == "1/2-13"
    assert spec.SHANK_DIA == catalog.model_diameter_mm == 12.7
    assert spec.SHANK_LEN == catalog.length_mm
    # Blind review: "1/2-13 UNC" -- the 2A class is the title block's -- as
    # a leader to the threaded neck, never a note line.
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    source = _source()
    assert "add_thread_leader(" in source
    assert "designation=THREAD_DESIGNATION" in source
    assert '"1/2-13' not in source
    assert spec.THREAD_DESIGNATION not in spec.DRAWING_NOTES
    assert catalog.head is HeadStyle.HEX_STACK
    assert catalog.drive is DriveStyle.EXTERNAL_HEX
    assert drawing.DIMENSION_CALLOUTS == {}


def test_stack_arithmetic_matches_the_top_frame_rederive_contract() -> None:
    # Shank: 12 thread engagement + 0.25 mount gap + 36.5 crossbar = 48.75;
    # stack above the casting top face: washer 2.5 + hex 11 + collar 3 +
    # tip 4; ONE merged part, machine y 987.45 .. 1056.7.
    assert spec.THREAD_LEN == 12.0
    assert spec.THREAD_DIA == 10.6
    assert spec.MOUNT_GAP == 0.25
    assert spec.CROSSBAR_SPAN == 36.5
    assert spec.THREAD_LEN + spec.MOUNT_GAP + spec.CROSSBAR_SPAN == spec.SHANK_LEN
    assert spec.SHANK_LEN == 48.75
    assert (spec.WASHER_DIA, spec.WASHER_T) == (28.0, 2.5)
    assert (spec.NUT_AF, spec.NUT_H) == (19.0, 11.0)
    assert (spec.COLLAR_DIA, spec.COLLAR_H) == (11.0, 3.0)
    assert (spec.TIP_DIA, spec.TIP_LEN) == (6.0, 4.0)
    assert spec.TOTAL_LEN == 69.25
    assert 987.45 + spec.TOTAL_LEN == 1056.7
    # The plain shank rides the crossbar's 1/2-close clearance bore.
    assert spec.SHANK_DIA < 13.49
    # The threaded engagement is modeled at a reduced diameter just under
    # the knife-mount's 1/2-13 tap drill (repo convention: modeled thread
    # < tap drill), so the stud/mount overlap volume is exactly ZERO.
    assert spec.THREAD_DIA < TAP_DRILL_MM["1/2-13"] == 10.716
    overlap_area = math.pi / 4.0 * max(
        spec.THREAD_DIA**2 - TAP_DRILL_MM["1/2-13"] ** 2, 0.0
    )
    assert overlap_area * spec.THREAD_LEN == 0.0
    # The reduced neck must stay a neck: strictly under the plain shank.
    assert spec.THREAD_DIA < spec.SHANK_DIA


def test_lengths_are_marked_extrude_depth_model_dims() -> None:
    # The vertical (axis +Y) profile cannot point-select the edge-on stack
    # steps, so every stack length ships as an extrude-DEPTH model
    # dimension: the build names them, the drawing inserts them in the side
    # view (four in a right column, the two thin ones on the left).
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    for feature, dim in (
        ("Thread", "ThreadLg"),
        ("Shank", "ShankLg"),
        ("Washer", "WasherT"),
        ("HexNut", "NutHt"),
        ("Collar", "CollarHt"),
        ("Tip", "TipLg"),
    ):
        assert f'name_dimensions(adapter, "{feature}", ["{dim}"])' in part_source
        assert spec.SIDE_VIEW_DIMENSIONS[feature] == {dim}
    assert "side_keep=SIDE_KEEP" in _source()
    right_column = {"ThreadLg", "ShankLg", "NutHt", "TipLg"}
    assert all(drawing.SIDE_KEEP[d][0] > drawing.SIDE_CENTER[0] for d in right_column)
    assert all(
        drawing.SIDE_KEEP[d][0] < drawing.SIDE_CENTER[0]
        for d in ("WasherT", "CollarHt", "ShankDia", "TipDia")
    )


def test_overall_is_a_conspicuous_reference_outside_the_chain() -> None:
    # Blind review: "36.75 can read as the overall; add (69.25 REF)".  A
    # drawing-native vertical between the threaded end face and the tip face
    # (model points on the right half of each, the tip picked outside its
    # drilled centre), parenthesised, in a column outside the four lengths.
    source = _source()
    assert "add_overall_reference(" in source
    assert 'orientation="vertical"' in source
    assert 'entity_types=("EDGE", "EDGE")' in source
    assert drawing.OVERALL_END_POINTS_MM == (
        (0.7 * spec.THREAD_DIA / 2.0, 0.0, 0.0),
        (0.7 * spec.TIP_DIA / 2.0, spec.TOTAL_LEN, 0.0),
    )
    assert 0.7 * spec.TIP_DIA / 2.0 > spec.CDRILL_DIA / 2.0
    right_column_x = {drawing.SIDE_KEEP[d][0] for d in ("ThreadLg", "ShankLg", "NutHt", "TipLg")}
    assert drawing.OVERALL_DIM_X - max(right_column_x) >= 0.020
    assert drawing.OVERALL_TEXT_XY[0] + 0.010 < drawing.ISO_CENTER[0] - 0.025


def test_end_view_carries_the_flats_and_the_drilled_centre() -> None:
    # The hex is a polygon with no marked diameter, so its across-flats is a
    # drawing-native vertical between the two flats; the drilled centre is
    # hidden in the profile, so it is called out on the circle it shows as
    # ("DRILL", not an undefined center-drill form -- blind review blocker).
    source = _source()
    half = spec.NUT_AF / 2.0 * drawing._S
    assert drawing.END_FLAT_PICKS == (
        (drawing.END_CENTER[0] + 0.004, drawing.END_CENTER[1] + half),
        (drawing.END_CENTER[0] + 0.004, drawing.END_CENTER[1] - half),
    )
    assert drawing.END_FLATS_TEXT_XY[0] > drawing.END_CENTER[0] + half
    assert 'label="hex across-flats"' in source
    assert 'orientation="vertical"' in source
    assert source.count("add_edge_dimension(") == 1
    assert spec.CENTER_DRILL_CALLOUT == "<MOD-DIAM>2.00 DRILL X 1.50 DEEP"
    assert "text=CENTER_DRILL_CALLOUT" in source
    assert 'label="tip centre drill"' in source
    assert "end_diameter_leaders_at_rim(" in source
    assert drawing.END_DIAMETERS == ("WasherDia", "CollarDia")
    assert drawing.RECIPE.decorate is drawing._decorate
    assert drawing.RECIPE.side_centerline_face_xy == drawing.SIDE_AXIS_FACE_XY


def test_notes_carry_only_what_the_views_cannot_say() -> None:
    # Every size is a dimension or a leadered callout; the notes keep the
    # thread extent, the one-piece fact and the shoulder-root allowance
    # (blind review blocker: the turned roots had no permissible fillet).
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert lines == [
        "THREADED ON THE LOWER END ONLY; PLAIN SHANK ABOVE.",
        "ONE PIECE; NOT A LOOSE NUT AND WASHER.",
        f"TURNED SHOULDER ROOTS R{spec.SHOULDER_ROOT_R_MAX:.2f} MAX.",
    ]
    assert spec.SHOULDER_ROOT_R_MAX == 0.25
    assert max(map(len, lines)) < 80
    for value in (
        spec.THREAD_LEN,
        spec.THREAD_DIA,
        spec.SHANK_DIA,
        spec.SHANK_LEN,
        spec.WASHER_T,
        spec.NUT_AF,
        spec.NUT_H,
        spec.COLLAR_DIA,
        spec.COLLAR_H,
        spec.TIP_DIA,
        spec.CDRILL_DIA,
        spec.CDRILL_DEPTH,
    ):
        assert f"{value:.2f}" not in notes, value
    for banned in BANNED_NOTE_PHRASES:
        assert banned not in notes, banned
    assert spec.END_VIEW_NOTE == "HEX-STACK END VIEW"


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
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "SURFACE_FINISHES")
    assert "build_fastener_sheet(" in source
    assert drawing.RECIPE.scale == drawing.SHEET_SCALE == (2.0, 1.0)


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("knife-hanger-stud")
    assert config["number"] == "MHA-119"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 2
