"""Offline contracts for the knife-hanger-stud drawing.

A 1/2-13 stud with an integral washer, hex, collar and tip on the shared
fastener recipe: no datums, frames, roughness symbols or basic dimensions
(cad/docs/drawing-simplicity-policy.md rules 3-5) and four lines of note that
carry only the stack sizes the views do not dimension (rule 6).
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
    # The end view carries the washer diameter (the stack's outermost circle),
    # the side view the four stack lengths; together they cover exactly the
    # marked set.
    assert set(drawing.END_KEEP) == set().union(*spec.END_VIEW_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == set().union(*spec.SIDE_VIEW_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert spec.END_VIEW_DIMENSIONS.keys() | spec.SIDE_VIEW_DIMENSIONS.keys() == (
        spec.DRAWING_DIMENSIONS.keys()
    )


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("knife-hanger-stud")
    assert spec.THREAD == catalog.thread == "1/2-13"
    assert spec.SHANK_DIA == catalog.model_diameter_mm == 12.7
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
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
    # steps, so the four lengths ship as extrude-DEPTH model dimensions:
    # the build names them, the drawing inserts them in the side view.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Thread", ["ThreadLg"])' in part_source
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert 'name_dimensions(adapter, "HexNut", ["NutHt"])' in part_source
    assert 'name_dimensions(adapter, "Tip", ["TipLg"])' in part_source
    assert spec.SIDE_VIEW_DIMENSIONS == {
        "Thread": {"ThreadLg"},
        "Shank": {"ShankLg"},
        "HexNut": {"NutHt"},
        "Tip": {"TipLg"},
    }
    assert "side_keep=SIDE_KEEP" in _source()


def test_notes_carry_only_the_undimensioned_stack_sizes() -> None:
    # The stack LENGTHS are dimensions; the stack diameters, washer
    # thickness, reduced thread neck and centre drill are not, so they ride
    # the four note lines -- never a tolerance, never the mating bore.
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert max(map(len, lines)) < 80
    assert lines[0] == (
        f"{spec.THREAD_DESIGNATION} ON LOWER END ONLY; PLAIN SHANK "
        f"{spec.SHANK_DIA:.2f} DIA ABOVE."
    )
    assert f"THREADED NECK DRAWN AT {spec.THREAD_DIA:.2f}, REFERENCE ONLY." in notes
    assert f"HEX {spec.NUT_AF:.2f} A/F" in notes
    assert f"WASHER {spec.WASHER_T:.2f} THICK" in notes
    assert f"COLLAR {spec.COLLAR_DIA:.2f} DIA X {spec.COLLAR_H:.2f}" in notes
    assert f"TIP {spec.TIP_DIA:.2f} DIA" in notes
    assert f"CENTER DRILL TIP END {spec.CDRILL_DIA:.2f} DIA X {spec.CDRILL_DEPTH:.2f} DEEP" in (
        notes
    )
    assert "TURN AND MILL" in notes
    # Dimensioned lengths never repeat in the note.
    assert f"{spec.THREAD_LEN:.2f}" not in notes
    assert f"X {spec.NUT_H:.2f}" not in notes
    for banned in (
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
    ):
        assert banned not in notes, banned


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
    assert drawing.RECIPE.decorate is None


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
