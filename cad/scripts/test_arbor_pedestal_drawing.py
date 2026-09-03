"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

import re
from pathlib import Path

import _surface_finish
import arbor_pedestal_spec
import build_arbor_pedestal as part
import draw_arbor_pedestal as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/arbor-pedestal_drawing.png")
    assert (
        DRAWINGS_BY_NAME["arbor_pedestal"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "Width", "Depth", "FootHt", "BoreDia", "DomeDia"
    }


def test_arbor_bore_closes_the_configured_running_fit() -> None:
    import _config

    assert round(arbor_pedestal_spec.BORE_DIA, 3) == 9.525
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == "BORE THRU"
    assert "BoreHeight" not in drawing.DIMENSION_CALLOUTS
    assert "Depth" not in drawing.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_PRECISION["BoreDia"] == 3
    assert "ARBOR BORE LIMITS" not in arbor_pedestal_spec.DRAWING_NOTES
    shaft_limits = (9.505, 9.525)
    bore_limits = (9.550, 9.580)
    clearances = (
        bore_limits[0] - shaft_limits[1],
        bore_limits[1] - shaft_limits[0],
    )
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    assert tuple(round(value, 3) for value in clearances) == expected


def test_screw_clearance_tracks_the_hole_resolver() -> None:
    """The hand-pinned diameter must equal what the hole resolver would give.

    ``arbor_pedestal_spec`` keeps ``SCREW_CLEARANCE_DIA`` as a LITERAL on
    purpose -- it is a pure-data module, and importing ``_holes`` would pull
    ``_common``/``_telemetry`` into its dependency closure and re-key both the
    part and the drawing. The cost of that choice is a duplicated constant, and
    this duplicate has now drifted twice (3.2512 <-> 3.264), each time only
    surfacing when a real rebuild replaced a remote-cache restore.

    A test can import both without touching the part's closure, so the drift is
    pinned here instead: the literal, ``_holes.CLEARANCE_MM``, and the seat's
    own wizard table (``#4`` normal = 0.1285 in) must all agree.
    """
    import _holes

    assert arbor_pedestal_spec.SCREW_CLEARANCE_DIA == _holes.CLEARANCE_MM[("#4", "normal")]
    # 0.1285 in is the seat's Screw Clearances row, read via
    # diagnostics/diag_hole_wizard_tables.py -- the authority the build asserts
    # against. Rounded to the resolver's 3 dp.
    assert round(0.1285 * 25.4, 3) == arbor_pedestal_spec.SCREW_CLEARANCE_DIA


def test_no_dead_band_between_wizard_correction_and_the_builder_assert() -> None:
    """What the wizard will FORCE must cover what the builder will ACCEPT.

    These were two different literals -- `_holes` only corrected a drift over
    0.05 mm, while `build_arbor_pedestal` rejected anything over 0.005. A #4
    clearance initialized at 3.2512 instead of 3.264 drifts 0.0128 and lands in
    the gap: the wizard leaves it, the builder refuses it, and NO value of the
    spec pin can satisfy both. It read as the seat's table "moving" and cost
    three flip-flops of the pin before Codex spotted the real mechanism on #422.

    Both now read one constant. This test fails if they are ever separated
    again, including by someone tightening only the builder's side.
    """
    import _holes

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "DIAMETER_TOLERANCE_MM" in source, "builder must use the shared tolerance"
    # Any numeric literal compared against the cut diameter re-opens the band.
    # Regex rather than a fixed string so `>0.005`, `> 0.0050` and friends are
    # caught too -- a whitespace variant slipping through would defeat the gate.
    assert not re.search(r"[<>]=?\s*0\.0*5\b|[<>]=?\s*0\.005\d*", source), (
        "builder compares the cut diameter against a numeric literal; use "
        "_holes.DIAMETER_TOLERANCE_MM so the wizard's correction threshold and "
        "this acceptance threshold cannot separate into a dead band again"
    )

    holes_source = Path(_holes.__file__).read_text(encoding="utf-8")
    assert "abs(initialized_dia_mm - pinned_dia_mm) > DIAMETER_TOLERANCE_MM" in holes_source

    # The tolerance must sit strictly between the benign rounding gap (the
    # 0.0001 between CLEARANCE_MM's 3.264 and the live 3.2639 -- writing there
    # would corrupt swHoleThru 25 into 26) and the wrong-row drift it must
    # catch (3.264 vs ("#3","loose") 3.251 = 0.0128).
    rounding_gap = abs(3.2639 - _holes.CLEARANCE_MM[("#4", "normal")])
    wrong_row_drift = abs(
        _holes.CLEARANCE_MM[("#4", "normal")] - _holes.CLEARANCE_MM[("#3", "loose")]
    )
    assert rounding_gap < _holes.DIAMETER_TOLERANCE_MM < wrong_row_drift


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = arbor_pedestal_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "MACHINE FROM CONTINUOUS-CAST STOCK" in notes
    assert "DIA 9.525 CYLINDER ARBOR" in notes  # the mating arbor, by size
    assert "HOLD-DOWN HOLE ON THE BORE CENTRELINE" in notes
    assert "MASK THE BORE" in notes
    # Nothing the title block, a dimension or a deleted frame used to say.
    for banned in (
        "+/-", "DATUM", "BOXED", "PROFILE", "GD&T", "MATERIAL", "JAPANNED",
        "X.XX", "UOS", "25-50 um", "TWO COATS", "(REF)",
    ):
        assert banned not in notes, banned
    # Parked under the foot-width dimension, above the border.
    assert drawing.NOTES_XY == (0.020, 0.066)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)' in source


def test_hole_callout_states_size_and_process() -> None:
    import _holes

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_native_hole_callout(" in source
    # Harvey #13: the callout says DRILL; #4 normal clearance is the #30 drill.
    assert 'process="#30 DRILL"' in source
    assert round(0.1285 * 25.4, 3) == _holes.CLEARANCE_MM[("#4", "normal")]
    assert 'label="flange-hole location from near foot edge"' in source


def test_upright_taper_and_depth_are_defined() -> None:
    # The 24.00 foot width sits BELOW the seat (it used to cross the strap
    # flanks at mid-height); the head diameter's callout says the flanks run
    # up to it; the strap thickness is dimensioned in the plan against the
    # flush rear face; the overall is a reference beside the bore height.
    assert drawing.FRONT_KEEP["Width"][1] < drawing._front_y(0.0)
    assert drawing.BORE_OFFSET_TEXT_Y < drawing._front_y(0.0)
    assert drawing.BORE_OFFSET_TEXT_Y > drawing.FRONT_KEEP["Width"][1]
    assert drawing.DIMENSION_CALLOUTS["DomeDia"] == "STRAP SIDES RUN TO IT"
    assert arbor_pedestal_spec.STRAP_T == 10.0
    assert arbor_pedestal_spec.OVERALL_HEIGHT == 49.718
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'label="strap thickness"' in source
    assert 'label="overall height"' in source
    # Add*Dimension2 hands back the late-bound IDisplayDimension; the
    # reference helper wants its IAnnotation (draw_crank_arm precedent).
    assert (
        'set_reference_dimension(\n        adapter,\n'
        '        _early_bound(overall, "IDisplayDimension").GetAnnotation(),\n'
        '        label="overall height",\n    )'
    ) in source
    assert 'arc="max"' in source
    assert drawing.OVERALL_TEXT_X < drawing.BORE_HEIGHT_TEXT_X < drawing.FRONT_KEEP["FootHt"][0]


def test_print_carries_no_gdt_or_basic_dimensions_and_one_running_ra() -> None:
    # drawing-simplicity-policy.md rules 3-5: a bearing casting is not on the
    # GD&T allowlist; the arbor bore is the one surface a shaft turns in.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_add_circle_basic(",
    ):
        assert helper not in source, helper
    assert not hasattr(arbor_pedestal_spec, "GEOMETRIC_TOLERANCES_MM")
    assert source.count("add_surface_finish(") == 1
    assert drawing.SURFACE_FINISHES is arbor_pedestal_spec.SURFACE_FINISHES
    assert len(drawing.SURFACE_FINISHES) == 1
    assert drawing.SURFACE_FINISHES[0].roughness_ra == _surface_finish.MACHINED
    assert 'surface_finish_by_key(SURFACE_FINISHES, "arbor_bore")' in source
    assert "leader_attach_xy=(FRONT_CENTER[0], _front_y(BORE_HEIGHT) - _bore_r)" in source
    # Keep the native symbol body right of the elevation and at least 20 mm
    # below the Ø20/strap callout text.
    assert drawing.FINISH_SYMBOL_XY[0] > drawing.FRONT_CENTER[0] + drawing.TOP_RADIUS * drawing._S
    assert drawing.FINISH_SYMBOL_XY[1] <= drawing.FRONT_KEEP["DomeDia"][1] - 0.020
    # The bore, hold-down, strap and overall locations survive as ordinary
    # entity-selected dimensions (five calls plus the helper).
    assert source.count("_add_entity_dimension(") == 6
    assert 'orientation="horizontal"' in source
    assert 'orientation="vertical"' in source
    assert "set_arc_endpoints_to_center(" in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    # The isometric deliberately keeps hidden lines so the hold-down hole
    # behind the upright stays visible in the pictorial.
    assert "set_hidden_lines_visible(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.FRONT_CENTER == (0.100, 0.150)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(2, 1)") == 3  # elevation + plan + pictorial


def test_plan_and_its_outer_dimension_clear_the_top_border() -> None:
    # At 2:1 the 16 mm-deep foot is 32 mm tall on paper.  Keep another 12 mm
    # for the outer 3.00 location dimension and its arrows below the ~273 mm
    # printable top border.
    assert drawing.TOP_CENTER == (0.100, 0.233)
    plan_top = (
        drawing.TOP_CENTER[1]
        + drawing.FOOT_DEPTH / 2.0 * drawing._S
        + 0.012
    )
    assert plan_top <= 0.261


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("arbor-pedestal")
    assert "A48" in str(config["material_specification"])
    assert "A48" in str(config["material"])
    finish = str(config["finish"]).lower()
    assert "sspc-sp3" in finish
    assert "black japan varnish" in finish
    assert "2 coats" in finish
    assert "25-50um dft" in finish
    assert "mask" not in finish
    # Two identical castings: the south pedestal plus the north one rotated
    # 180 about Y (build_drive_train_assembly places both).
    assert int(config["quantity"]) == 2
