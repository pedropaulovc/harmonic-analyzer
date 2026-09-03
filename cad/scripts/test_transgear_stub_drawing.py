"""Offline contracts for the transgear-stub drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a stepped stud turned
in one setting carries no datums or frames; its two fits are the bands on the
model diameters, plus one Ra on the seat the feed pinion and disc turn on. The
axial stations baseline from the base end with a conspicuous overall, and the
shoulder roots carry one leadered R MAX allowance (rule 7).
"""

from __future__ import annotations

from pathlib import Path

import _fit_limits
import build_transgear_stub as part
import draw_transgear_stub as drawing
import transgear_stub_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _part_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-stub.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-stub.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-stub_drawing.png")
    assert (
        DRAWINGS_BY_NAME["transgear_stub"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is transgear_stub_spec.DRAWING_DIMENSIONS
    marked = set().union(*transgear_stub_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked
    nominals = (
        transgear_stub_spec.BASE_DIA,
        transgear_stub_spec.BASE_LEN,
        transgear_stub_spec.SEAT_DIA,
        transgear_stub_spec.SEAT_LEN,
        transgear_stub_spec.COLLAR_DIA,
        transgear_stub_spec.COLLAR_LEN,
    )
    assert (
        part.BASE_DIA,
        part.BASE_LEN,
        part.SEAT_DIA,
        part.SEAT_LEN,
        part.COLLAR_DIA,
        part.COLLAR_LEN,
    ) == nominals
    # The drawing types BASE_DIA only to place the root-note pick on the
    # base shoulder's rim; the base reaches the sheet as a marked dimension.
    assert (
        drawing.BASE_DIA,
        drawing.BASE_LEN,
        drawing.SEAT_DIA,
        drawing.SEAT_LEN,
        drawing.COLLAR_DIA,
        drawing.COLLAR_LEN,
    ) == nominals
    # The base is machine-standard 3/8" stock carried in mm.
    assert transgear_stub_spec.BASE_DIA == 0.375 * transgear_stub_spec.MM_PER_IN


def test_lands_carry_true_diametric_dimensions() -> None:
    """The revolve profile dims the lathe-facing set: three doubled
    centerline (diameter) dims plus the three base-end axial stations --
    never the radius/step chain a rectilinear-chain recipe would emit."""
    source = _part_source()
    assert source.count("await add_diametric_linear_dimension(") == 1
    assert "swDiametricLinearDimension" in source
    imports = source.split("PART_NAME =", 1)[0]
    assert "define_rectilinear_chain" not in imports  # not even imported
    marked = transgear_stub_spec.DRAWING_DIMENSIONS["StubProfile"]
    assert {"BaseDia", "SeatDia", "CollarDia"} <= marked
    assert {"BaseLength", "SeatEnd", "Overall"} <= marked


def test_axial_stations_baseline_from_the_base_end() -> None:
    """Machinist review 2026-09-02: the per-land chain ran from three faces
    and left no conspicuous overall. Every axial station now measures from
    the base (faced) end -- 9.10, 22.90, 26.90 -- off one shared corner."""
    source = _part_source()
    assert "SeatLength" not in source
    assert "CollarLength" not in source
    assert 'base_corner = f"{profile_lines[0]}.end"' in source
    assert "\"SeatEnd\", '\"BaseLen\" + \"SeatLen\"'" in source
    assert "'\"BaseLen\" + \"SeatLen\" + \"CollarLen\"'" in source
    stations = (
        transgear_stub_spec.BASE_LEN,
        transgear_stub_spec.BASE_LEN + transgear_stub_spec.SEAT_LEN,
        drawing.TOTAL_LEN,
    )
    assert [round(s, 2) for s in stations] == [9.1, 22.9, 26.9]
    # One lane per station on the profile's right, longest outermost, and
    # the two lanes that span the Ra symbol's height sit clear of its arm
    # (measured to x=0.1764).
    lanes = [
        drawing.FRONT_KEEP[name][0] for name in ("BaseLength", "SeatEnd", "Overall")
    ]
    assert lanes == sorted(lanes)
    assert lanes[1] > 0.1764 and lanes[2] > 0.1764
    assert all(x > drawing._fx(transgear_stub_spec.COLLAR_DIA / 2.0) for x in lanes)
    # The diameters keep their left-hand stack.
    for name in ("BaseDia", "SeatDia", "CollarDia"):
        assert drawing.FRONT_KEEP[name][0] < drawing._fx(-transgear_stub_spec.COLLAR_DIA / 2.0)


def test_shoulder_roots_carry_a_leadered_allowance() -> None:
    # Review 2026-09-02 blocker: both concave shoulder roots were undefined.
    # One attached note on the base shoulder's rim sizes both (rule 7).
    assert transgear_stub_spec.ROOT_NOTE == "2X ROOT R0.25 MAX"
    source = _source()
    assert source.count("add_attached_note(") == 1
    assert "text=ROOT_NOTE" in source
    assert "find_edge_near(" in source
    # Picked on the base shoulder (y = BASE_LEN), 1 mm inboard of the rim, on
    # the left where the note sits between the BaseDia and SeatDia lines.
    assert drawing.ROOT_PICK_XY[1] == drawing._fy(transgear_stub_spec.BASE_LEN)
    assert drawing.ROOT_PICK_XY[0] < drawing.FRONT_CENTER[0]
    assert drawing.ROOT_NOTE_XY[0] < drawing.ROOT_PICK_XY[0]
    assert (
        drawing.FRONT_KEEP["BaseDia"][1]
        < drawing.ROOT_NOTE_XY[1]
        < drawing.FRONT_KEEP["SeatDia"][1]
    )


def test_diameter_bands_are_toleranced_on_the_model_not_the_sheet() -> None:
    """The fit bands must reach the print as NATIVE dimension tolerances.

    A band spelled as callout text (``SetText``) is frozen: SolidWorks prints it
    verbatim beside a live numeral and never re-renders it, so the mm->inch flip
    in issue #290 would leave "+0.00/-0.02" reading as inches. Tolerancing the
    model dimension instead is the only path that survives a unit change, so the
    sheet must carry NO override for either diameter.
    """
    assert drawing.DIMENSION_CALLOUTS == {}
    # The seat is the shared ground-shaft class, not a value peculiar to this
    # stud -- assert the IDENTITY so a local retype cannot silently fork it.
    assert transgear_stub_spec.SEAT_DIA_BAND is _fit_limits.SHAFT_H
    assert transgear_stub_spec.BASE_DIA_BAND == (0.000, -0.050)
    assert model_toleranced_dimensions(part) == {
        ("StubProfile", "BaseDia"): "*deviations(BASE_DIA_BAND)",
        ("StubProfile", "SeatDia"): "*deviations(SEAT_DIA_BAND)",
    }
    # Only the fitted 3/8" base prints three decimals.
    assert drawing.DIMENSION_PRECISION == {"BaseDia": 3}


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = transgear_stub_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "ONE SETUP" in notes
    # Deburr/edge-break is a title-block row; concentricity is a GD&T note;
    # the root radius rides its leadered note on the view.
    for banned in ("DEBURR", "CONCENTRIC", "ROOT", "WITHIN", "+/-", "UOS", "DATUM", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_and_one_running_finish() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert transgear_stub_spec.PART_DATUMS == ()
    assert transgear_stub_spec.GEOMETRIC_CONTROLS == ()
    assert not hasattr(transgear_stub_spec, "GEOMETRIC_TOLERANCES_MM")
    # The feed pinion and disc turn on the seat, so it alone carries a
    # roughness symbol.
    (control,) = transgear_stub_spec.SURFACE_FINISHES
    assert control.key == "gear_seat"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == transgear_stub_spec.SEAT_DIA
    assert source.count("add_surface_finish(") == 1
    sheet_source = "".join(source.split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"gear_seat")'
        in sheet_source
    )
    assert "roughness_ra=" not in source
    # The part build keeps its author_part_pmi call shape on the empty tuples.
    part_source = "".join(_part_source().split())
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=SURFACE_FINISHES" in part_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, end):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    # All three views read at the sheet's own 4:1 -- no blow-up note needed.
    assert _source().count("scale=(4, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = _part_source()
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("transgear-stub")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
