"""Offline contracts for the pinion-pivot-block drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import dt_pinion_pivot_block_spec
import draw_dt_pinion_pivot_block as drawing
import build_dt_pinion_pivot_block as block
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_ream_slide import REAM_SLIDE
from _hole_spec import blind_cut_dia_mm
from _printed_tolerance import printed_band_mm


def test_raised_pivot_follows_bank_without_changing_the_upper_envelope() -> None:
    import cone_line
    import dt_pinion_pivot_block_geometry as geometry
    import _cone_axis_constants
    import pinion_rig_park_geometry as park

    raise_mm = _cone_axis_constants.AXIS_RAISE_MM
    assert geometry.BORE_UP == pytest.approx(12.0 + raise_mm)
    # #290: the raised envelope snaps to the nearest .XX the sheet prints.
    assert geometry.BLOCK_HEIGHT == pytest.approx(20.5 + raise_mm, abs=0.127)
    assert round(geometry.BLOCK_HEIGHT / 25.4, 9) == pytest.approx(0.99)
    assert geometry.BLOCK_TOP_Y == pytest.approx(8.414)
    assert park.PIVOT_Y == pytest.approx(cone_line.Y_BASE_TOP + geometry.BORE_UP)
    assert park.APINION_Y == cone_line.Y_DRIVE
    assert park.APINION_Y - park.PIVOT_Y == pytest.approx(27.718)
    assert park.STRAP_C2C == 28.0
    assert park.STRAP_LEAN_DEG == pytest.approx(8.138574451932667)


def test_engaged_pinion_centre_and_clocking_share_the_pivot_swing() -> None:
    import math

    import dt_alignment_pinion_spec as pinion
    import pinion_rig_park_geometry as park

    x, y = park.ENGAGED_APINION_XY
    assert math.hypot(x - park.PIVOT_X, y - park.PIVOT_Y) == pytest.approx(park.STRAP_C2C)
    assert math.hypot(x - park.X_DRUM, y - park.Y_DRIVE) == pytest.approx(
        pinion.ENGAGED_CENTER_DISTANCE_MM
    )
    parked = math.atan2(park.APINION_Y - park.PIVOT_Y, park.APINION_X - park.PIVOT_X)
    engaged = math.atan2(y - park.PIVOT_Y, x - park.PIVOT_X)
    assert engaged - parked == pytest.approx(park.ENGAGED_SWING_RAD)
    assert 0.01 < park.ENGAGED_SWING_RAD < math.radians(10.0)
    assert y != pytest.approx(park.APINION_Y)


def test_live_stock_block_screw_keeps_full_threads_at_the_longest_grip() -> None:
    import dt_pinion_pivot_block_geometry as geometry
    import dt_vn_slotted_screw_spec as screw
    from _mcmaster_90280a203 import FILLISTER_SIZE

    entry = _config.title_block("edge_break")
    entry_loss = max(float(entry["radius_mm"]), float(entry["chamfer_max_mm"]))
    full_threads = (
        screw.SHANK_LEN - geometry.BLOCK_HEIGHT - geometry.BLOCK_HEIGHT_BAND
        - screw.PITCH - entry_loss
    )
    assert full_threads >= 1.5 * screw.SHANK_DIA
    assert FILLISTER_SIZE == (
        screw.SHANK_DIA, screw.SHANK_LEN, screw.HEAD_H, screw.HEAD_DIA, screw.PITCH
    )


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    # Both bores run a shaft (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)): MHA-DT-19 in the pivot bore, MHA-DT-17
    # in the lift bore.
    pivot, lift = dt_pinion_pivot_block_spec.SURFACE_FINISHES
    assert (pivot.key, lift.key) == ("pivot_bore", "lift_bore")
    for control in (pivot, lift):
        assert control.roughness_um == 1.6
        assert control.face.diameter_mm == dt_pinion_pivot_block_spec.BORE_DIA
    assert pivot.face.contains_y_mm == -dt_pinion_pivot_block_spec.BORE_DIA / 2.0
    # The lift selector's station lies outside the pivot bore's x-span.
    lift_x = lift.face.contains_x_mm
    assert lift_x == -dt_pinion_pivot_block_spec.LIFT_BORE_SPACING
    assert abs(lift_x) > dt_pinion_pivot_block_spec.BORE_DIA / 2.0
    part_source = Path(block.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "pivot_bore")' in drawing_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "lift_bore")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-pivot-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-pivot-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-pivot-block_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_pinion_pivot_block"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert block.DRAWING_DIMENSIONS is dt_pinion_pivot_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_pinion_pivot_block_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.BLOCK_WIDTH, drawing.FRONT_BBOX_CY, drawing.FRONT_BBOX_CX) == (
        dt_pinion_pivot_block_spec.BLOCK_WIDTH,
        dt_pinion_pivot_block_spec.FRONT_BBOX_CY,
        dt_pinion_pivot_block_spec.FRONT_BBOX_CX,
    )


def test_sheet_runs_at_3_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source  # the isometric override
    assert dt_pinion_pivot_block_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_each_ream_callout_names_its_running_mate() -> None:
    # Machinist review r1 (#1014): the mate and fit ride each bore's own
    # callout (drawing-guidelines.md rule 4 (tighten only for function, and
    # name the mate)), named exactly as the mate's title block reads.
    callouts = drawing.DIMENSION_CALLOUTS
    for name, part in (
        ("PivotBoreDia", "dt-pinion-pivot-shaft"),
        ("LiftBoreDia", "dt-pinion-lift-rod"),
    ):
        row = _config.parts(part)
        lines = callouts[name].splitlines()
        assert lines[0] == "THRU - REAM"
        assert "RUNNING FIT ON" in lines
        assert str(row["number"]) in lines
        assert str(row["title"]).upper() in lines
    # R2 (converged-r7): REAM_SLIDE, one fit per shaft with MHA-DT-14; the
    # stock 1/4 in reamer wording went with the line-to-line band.
    assert dt_pinion_pivot_block_spec.BORE_DIA_BAND == REAM_SLIDE
    assert "1/4 IN" not in callouts["PivotBoreDia"]


def test_sheet_carries_no_general_notes() -> None:
    # Every bore's fit is at its callout and the hold-downs at their DRILL
    # callout, so nothing is left for a general note; general tolerances live
    # in the title block only.
    assert not hasattr(dt_pinion_pivot_block_spec, "DRAWING_NOTES")
    for script in (drawing, block):
        source = Path(script.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source


def test_front_view_locations_start_at_the_pivot_bore() -> None:
    # Machinist review r1 (#1014, rule 10 (dimension from a real feature)):
    # the front view's one datum is the pivot bore; every location in it
    # carries the origin circle there.
    assert set(drawing.PIVOT_ORIGIN_DIMENSIONS) == {
        "AnchorX",
        "LiftBoreX",
        "AnchorZ",
        "LiftBoreCz",
    }
    assert set(drawing.PIVOT_ORIGIN_DIMENSIONS) <= set(drawing.FRONT_KEEP)
    # The lift-bore rise stands outside the block's west end (rule 14).
    rise_x, _ = drawing.FRONT_KEEP["LiftBoreCz"]
    assert rise_x < drawing._front_x(-dt_pinion_pivot_block_spec.BLOCK_WEST)
    # Review r2: the sheet says why the spacing is held from the pivot bore,
    # on one line (a multi-line above-callout does not print).
    assert set(drawing.ABOVE_CALLOUTS) == {"LiftBoreX"}
    assert all("\n" not in text for text in drawing.ABOVE_CALLOUTS.values())


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["PivotBoreDia"].startswith("THRU")
    assert callouts["LiftBoreDia"].startswith("THRU")
    assert "+0.05/-0.00" not in "\n".join(callouts.values())
    assert model_toleranced_dimensions(block) == {
        ("BlockProfile", "PivotBoreDia"): "*deviations(BORE_DIA_BAND)",
        ("BlockProfile", "LiftBoreDia"): "*deviations(BORE_DIA_BAND)",
    }


def test_block_carries_no_gdt_only_its_running_bore_finish() -> None:
    # drawing-guidelines.md rule 5 (avoid excessive GD&T): blocks are not on the GD&T
    # allowlist, so no datum tags, no feature-control frames, no basic boxes.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "set_basic_dimension(" not in source
    assert not hasattr(dt_pinion_pivot_block_spec, "GEOMETRIC_TOLERANCES_MM")
    assert "set_dimension_origin" in source
    assert "add_surface_finish(" in source
    # The hold-downs are ordinary coordinates from the west end.
    assert '"west hold-down station"' in source
    assert '"east hold-down station"' in source


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    # The hold-down holes are a native Hole Wizard feature: their size comes
    # from the clearance standard, so no ScrewHoles dimension may be hand-marked.
    assert not any("Screw" in feature for feature in block.DRAWING_DIMENSIONS)


def test_screw_hole_contract_is_part_owned_and_resolved() -> None:
    spec = dt_pinion_pivot_block_spec.SCREW_HOLE_SPEC
    assert block.SCREW_HOLE_SPEC is spec
    assert spec.kind == "clearance"
    assert spec.size == "#8"
    assert spec.fit == "normal"
    assert dt_pinion_pivot_block_spec.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)
    assert drawing.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(block.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("dt-pinion-pivot-block")
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 2  # the book uses two blocks


def test_assembly_and_base_depend_on_geometry_not_drawing_notes() -> None:
    from _buildgraph import module_deps_of

    for script in ("build_dt_drive_train_assembly.py", "build_fr_harmonic_base.py"):
        deps = {
            Path(path).name for path in module_deps_of(Path(__file__).with_name(script))
        }
        assert "dt_pinion_pivot_block_geometry.py" in deps, script
        assert "dt_pinion_pivot_block_spec.py" not in deps, script
        assert "build_dt_pinion_pivot_block.py" not in deps, script


def test_views_carry_no_hidden_lines_and_the_drill_callout_names_its_process() -> None:
    # Fable review r4 (drawing-guidelines.md rule 9 (show internal shape in solid lines)): the holes are standard drills and reams fully
    # defined by their callouts, so every view is hidden-lines-removed.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hidden_lines_visible" not in source
    assert "for view in (front, top, right, iso):" in source
    assert 'process="DRILL"' in source
    assert "symbol_xy=PIVOT_FINISH_XY" in source
    assert "char_height=0.0025" in source
    # The Ra leader must leave the block through its top face, left of the
    # corner where BlockHeight's extension line starts.
    rim = (
        drawing._front_x(0.0) + drawing.BORE_R_SHEET * 0.866,
        drawing._front_y(0.0) + drawing.BORE_R_SHEET * 0.5,
    )
    top_y = drawing._front_y(
        dt_pinion_pivot_block_spec.BLOCK_HEIGHT - dt_pinion_pivot_block_spec.BORE_UP
    )
    finish_x, finish_y = drawing.PIVOT_FINISH_XY
    slope = (finish_y - rim[1]) / (finish_x - rim[0])
    exit_x = rim[0] + (top_y - rim[1]) / slope
    assert exit_x < drawing._front_x(dt_pinion_pivot_block_spec.BLOCK_EAST) - 0.003


def test_rig_layout_sets_the_front_block_by_feeler_off_the_back_stop() -> None:
    # User ruling (c): the blocks locate the swing cluster.  Codex #854/#858
    # P1 (Main): the pose IS the fit-up stack -- back strap hard on the back
    # block, the drum hard on it, the front strap one shim off the drum's front
    # end (the shaft's drilling set-up, ruling 3), and the front block one
    # feeler off the front strap.
    import dt_alignment_pinion_spec
    import pinion_rig_layout as rig
    from dt_pinion_bracket_geometry import THICKNESS

    assert rig.DRUM_LEN == dt_alignment_pinion_spec.FACE_WIDTH
    assert rig.STRAP_Z_OUTER[1] == pytest.approx(rig.BACK_BLOCK_Z0, abs=1e-9)
    front_inner = rig.FRONT_BLOCK_Z0 + dt_pinion_pivot_block_spec.BLOCK_DEPTH
    assert rig.STRAP_Z_OUTER[0] - front_inner == pytest.approx(0.25, abs=1e-9)
    assert (rig.DRUM_FRONT_Z - rig.DRUM_END_SHIM, rig.DRUM_BACK_Z) == pytest.approx(
        rig.STRAP_Z_INNER, abs=1e-9
    )
    # The drum shim is its own 0.45 blade (Main, #858: the 0.25 feeler left the
    # drum 0.05 over its end-play floor).
    assert rig.DRUM_END_SHIM == 0.45
    assert not hasattr(rig, "STRAP_AIR")
    assert rig.STRAP_Z_OUTER[1] - rig.STRAP_Z_INNER[1] == pytest.approx(THICKNESS)


def test_rig_layout_shaft_and_rod_are_set_back_flush() -> None:
    import pinion_rig_layout as rig
    from dt_pinion_lift_rod_spec import ROD_LEN
    from dt_pinion_pivot_shaft_spec import SHAFT_LEN

    assert SHAFT_LEN == rig.TORQUE_SHAFT_LEN
    assert ROD_LEN == rig.LIFT_ROD_LEN
    # Back ends flush with the back block; the shaft's front end flush with
    # the front block, the rod >= LEVER_SEAT_PROUD proud of it.
    assert rig.TORQUE_SHAFT_Z0 + SHAFT_LEN == pytest.approx(rig.BACK_BLOCK_OUTER_Z)
    assert rig.LIFT_ROD_Z0 + ROD_LEN == pytest.approx(rig.BACK_BLOCK_OUTER_Z)
    shaft_proud = rig.FRONT_BLOCK_Z0 - rig.TORQUE_SHAFT_Z0
    assert shaft_proud == pytest.approx(
        rig.TORQUE_SHAFT_LEN - 2.0 * rig.BLOCK_DEPTH - rig.INNER_SPAN
    )
    proud = rig.FRONT_BLOCK_Z0 - rig.LIFT_ROD_Z0
    assert rig.LEVER_SEAT_PROUD - 1e-9 <= proud <= rig.LEVER_SEAT_PROUD + 0.254
    # Both are budgeted on the worst fitted stack (their own tests); at
    # nominal each stands that allowance proud of the front block.
    assert (SHAFT_LEN, ROD_LEN) == pytest.approx((7.27 * 25.4, 7.70 * 25.4))


def test_lift_rod_length_budgets_the_whole_fitted_stack() -> None:
    # Codex #854 P1: MHA-DT-17 carries both MHA-DT-18 lift bores, the two MHA-DT-23
    # collars between them and the MHA-DT-16 lever hub past the front block --
    # nothing else rides it (ruling (c): no collar, no spacer; the MHA-DT-30
    # cross pin runs radially and takes no length).  The drive-train assembly
    # must place every one of them from pinion_rig_layout: before the
    # placement moved into this PR, the old hard-coded stations left the
    # 192.0 rod 0.25 into the back block, which no interference gate sees.
    import math

    import build_dt_drive_train_assembly as drive
    import pinion_rig_layout as rig
    from dt_pinion_cam_geometry import CAM_LEN
    from dt_pinion_lever_geometry import (
        BORE_DEPTH,
        HUB_LEN,
        PIN_HOLE_DIA,
        ROD_PIN_HOLE_FROM_END,
        WALL_T,
    )

    depth = dt_pinion_pivot_block_spec.BLOCK_DEPTH
    budget = 2.0 * depth + rig.INNER_SPAN + rig.LEVER_SEAT_PROUD
    assert rig.LIFT_ROD_LEN == pytest.approx(math.ceil(budget / 0.254 - 1e-6) * 0.254)
    # One source of truth: every rig station the assembly places is the
    # layout's.
    assert drive.LIFT_ROD_Z0 == rig.LIFT_ROD_Z0
    assert drive.PIVOT_SHAFT_Z0 == rig.TORQUE_SHAFT_Z0
    assert (drive.BLOCK_FRONT_Z0, drive.BLOCK_BACK_Z0) == rig.BLOCK_Z0
    rod = (drive.LIFT_ROD_Z0, drive.LIFT_ROD_Z0 + rig.LIFT_ROD_LEN)
    shaft = (drive.PIVOT_SHAFT_Z0, drive.PIVOT_SHAFT_Z0 + rig.TORQUE_SHAFT_LEN)
    # Full engagement of the rod in both lift bores, and both rod and shaft
    # reach the back block's outer face (the (c) back stop).
    for z0 in rig.BLOCK_Z0:
        assert rod[0] <= z0 and z0 + depth <= rod[1] + 1e-9
    assert rod[1] == pytest.approx(rig.BACK_BLOCK_OUTER_Z)
    assert shaft[1] == pytest.approx(rig.BACK_BLOCK_OUTER_Z)
    # Both collars sit on the rod between the blocks' inner faces.
    inner = (drive.BLOCK_FRONT_Z0 + depth, drive.BLOCK_BACK_Z0)
    for z0 in drive.CAM_Z0:
        assert inner[0] - 1e-9 <= z0 and z0 + CAM_LEN <= inner[1] + 1e-9
    # The lever hub takes BORE_DEPTH of the proud length (the rod bottoms on
    # its floor) and its mouth stays clear of the block.
    assert drive.LEVER_Z - HUB_LEN / 2.0 + WALL_T == pytest.approx(rod[0])
    hub_mouth = rod[0] + BORE_DEPTH
    assert rig.FRONT_BLOCK_Z0 - hub_mouth == pytest.approx(
        rig.LEVER_SEAT_PROUD - BORE_DEPTH, abs=0.1
    )
    # MHA-DT-30's hole stays inside the hub engagement at the title block's .XX.
    assert ROD_PIN_HOLE_FROM_END - PIN_HOLE_DIA / 2.0 - 0.254 >= 0.0
    assert ROD_PIN_HOLE_FROM_END + PIN_HOLE_DIA / 2.0 + 0.254 <= BORE_DEPTH


def test_worst_stack_bands_are_the_printed_places() -> None:
    # Codex #837 P1: the worst fitted stack reads each band from the geometry
    # module that owns it, at the title-block row for the places (and unit)
    # its sheet prints (#290: the strap at .XXX, the drum, shaft and rod
    # lengths at .XX).
    import dt_alignment_pinion_spec
    import dt_pinion_bracket_spec
    import dt_pinion_lift_rod_spec
    import dt_pinion_pivot_shaft_spec
    import pinion_rig_layout as rig

    assert dt_pinion_bracket_spec.DRAWING_PRECISION["Strap"]["Depth"] == 3
    assert dt_pinion_bracket_spec.THICKNESS_BAND == printed_band_mm(3, unit="in")
    assert dt_alignment_pinion_spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == 2
    assert dt_alignment_pinion_spec.UNIT == rig.DRUM_LEN_UNIT == "in"
    assert rig.DRUM_LEN_BAND == printed_band_mm(2, unit="in")
    assert dt_pinion_lift_rod_spec.DRAWING_PRECISION["RodProfile"]["RodBody"] == 2
    assert dt_pinion_pivot_shaft_spec.DRAWING_PRECISION["ShaftProfile"]["ShaftLength"] == 2
    assert rig.LENGTH_BAND == printed_band_mm(2, unit="in")
    assert not hasattr(rig, "STACK_BAND")  # the stacks name every term


def test_front_block_feeler_setting_is_the_ruled_band() -> None:
    # Codex #854 P1: the fit-up setting that makes INNER_SPAN (and
    # so the 185.1 shaft and 197.0 rod) true is ruling (c)'s 0.25 +/- 0.10
    # feeler between the front strap and the front block.  The band is a
    # named fit-up value so the MHA-DT-00 step and every worst-case gate read
    # one source; it never closes the gap or doubles it.  The layout owns it
    # (its worst stack sizes the shaft and rod, Codex #837) and pinion_rig_fitup
    # re-exports it for the print.
    import pinion_rig_fitup as fitup
    import pinion_rig_layout as rig

    assert fitup.FRONT_BLOCK_FEELER is rig.FRONT_BLOCK_FEELER
    assert fitup.FRONT_BLOCK_FEELER_BAND is rig.FRONT_BLOCK_FEELER_BAND
    assert (fitup.FRONT_BLOCK_FEELER, fitup.FRONT_BLOCK_FEELER_BAND) == (0.25, 0.10)
    # Main (#858): both feelers are stock leaves of one purchased set.
    assert fitup.DRUM_END_SHIM == 0.45
    assert fitup.FEELER_GAGE_LEAVES_MM[4] == 0.25
    assert fitup.FEELER_GAGE_LEAVES_MM[8] == 0.45
    assert len(fitup.FEELER_GAGE_LEAVES_MM) == 20
    assert "66MA" in fitup.FEELER_GAGE
    assert 0.0 < fitup.FRONT_BLOCK_FEELER - fitup.FRONT_BLOCK_FEELER_BAND
    assert fitup.FRONT_BLOCK_FEELER_BAND < fitup.FRONT_BLOCK_FEELER


def test_manufactured_block_span_is_the_solid_stack_plus_one_feeler() -> None:
    # Codex #854 P1: the span between the blocks is the solid stack (strap,
    # drum, strap) plus the one feeler end play.  Codex #854/#858 P1 (Main):
    # the saved pose carries exactly that span -- no extra pose air -- so the
    # base seats cut from it fit the single-feeler fit-up.  Ruling 3 adds the
    # drum shim the pinned straps were drilled on.
    import pinion_rig_layout as rig
    from dt_pinion_bracket_geometry import THICKNESS

    solid = 2.0 * THICKNESS + rig.DRUM_LEN
    assert rig.INNER_SPAN == pytest.approx(
        solid + rig.DRUM_END_SHIM + rig.FRONT_BLOCK_FEELER
    )
    model_span = rig.BACK_BLOCK_Z0 - (
        rig.FRONT_BLOCK_Z0 + dt_pinion_pivot_block_spec.BLOCK_DEPTH
    )
    assert model_span == pytest.approx(rig.INNER_SPAN, abs=1e-9)


def test_torque_shaft_bears_the_front_block_at_the_worst_fitted_stack() -> None:
    # Codex #854 P1: the shaft was sized at nominal only, and at the worst
    # fitted stack (back block, both straps, drum and feeler at their maxima,
    # the shaft at its printed minimum) it reached only ~6.49 into the front
    # block.  Each band is re-derived here from the grade its dimension prints at.
    import math

    import dt_pinion_bracket_spec
    import pinion_rig_layout as rig
    from dt_pinion_lever_geometry import HUB_OD
    from dt_pinion_pivot_block_geometry import LIFT_BORE_RISE, LIFT_BORE_SPACING
    from dt_pinion_pivot_shaft_spec import DRAWING_PRECISION, SHAFT_DIA

    xx_in, xxx_in = printed_band_mm(2, unit="in"), printed_band_mm(3, unit="in")
    assert dt_pinion_bracket_spec.DRAWING_PRECISION["Strap"]["Depth"] == 3
    assert DRAWING_PRECISION["ShaftProfile"]["ShaftLength"] == 2
    # MHA-DT-18 is not precision-migrated; its part authors Depth at .XX.
    assert "draw_dt_pinion_pivot_block.py" not in PRECISION_MIGRATED_DRAWINGS
    assert dt_pinion_pivot_block_spec.DRAWING_PRECISION["Block"]["Depth"] == 2
    assert dt_pinion_pivot_block_spec.BLOCK_DEPTH == pytest.approx(0.44 * 25.4)
    assert rig.DRUM_LEN_BAND == xx_in  # the inch drum's .XX
    assert rig.LENGTH_BAND == xx_in
    assert rig.BLOCK_DEPTH_BAND == xx_in
    # Main (Codex #854 P1): each band is the title block's row for the places
    # its dimension prints at, so a sheet that prints more places tightens its
    # term by itself.  The layout's places must be the sheets' places.
    from _printed_tolerance import printed_deviations
    from dt_alignment_pinion_spec import DRAWING_PRECISION as DRUM_PRECISION
    from dt_pinion_lift_rod_spec import DRAWING_PRECISION as ROD_PRECISION

    assert rig.BLOCK_DEPTH_PLACES == 2
    assert rig.STRAP_T_PLACES == dt_pinion_bracket_spec.DRAWING_PRECISION["Strap"]["Depth"]
    assert rig.DRUM_LEN_PLACES == DRUM_PRECISION["GearBlank"]["FaceWidth"]
    assert rig.LENGTH_PLACES == DRAWING_PRECISION["ShaftProfile"]["ShaftLength"]
    assert rig.LENGTH_PLACES == ROD_PRECISION["RodProfile"]["RodBody"]
    # A nominal that does not print exactly moves its term by the rounding.
    assert printed_deviations(10.254, 2) == pytest.approx((-0.514, 0.506))
    assert rig.FRONT_BLOCK_FEELER_BAND == 0.10

    depth = dt_pinion_pivot_block_spec.BLOCK_DEPTH
    shortest_shaft = rig.TORQUE_SHAFT_LEN - xx_in
    # Straps at .XXX, the drum at its own row, the feeler and the drum shim
    # each 0.10 wide, and the flush setting the shaft is drilled at 0.10 proud
    # (ruling 2).
    growth = 2.0 * xxx_in + rig.DRUM_LEN_BAND + 0.10 + 0.10
    longest_span = (depth + xx_in) + rig.INNER_SPAN + growth
    bearing = shortest_shaft - longest_span - 0.10
    assert bearing == pytest.approx(sum(rig.TORQUE_SHAFT_BEARING_STACK.values()))
    required = rig.FRONT_BLOCK_MIN_BEARING + rig.BLOCK_BEARING_MARGIN
    assert bearing >= required and rig.FRONT_BLOCK_MIN_BEARING == 9.5
    # The smallest .XX length that does it (Main, #858: with 0.5 over the 9.5
    # floor): .01 shorter falls under it.
    assert bearing - xx_in < required
    # Other extreme: the longest shaft in the shortest stack stands proud of
    # the front block, and nothing sits on its axis there -- the MHA-DT-16 lever
    # hub rides the lift rod, which the blocks carry off the shaft axis.
    longest_shaft = rig.TORQUE_SHAFT_LEN + xx_in
    shortest_outer = 2.0 * (depth - xx_in) + rig.INNER_SPAN - growth
    assert longest_shaft - shortest_outer == pytest.approx(1.837, abs=5e-3)
    hub_clear = (
        math.hypot(LIFT_BORE_SPACING, LIFT_BORE_RISE) - (HUB_OD + SHAFT_DIA) / 2.0
    )
    assert hub_clear == pytest.approx(8.974, abs=5e-3)


def test_spring_blade_stays_on_the_back_strap_flank_at_every_stack() -> None:
    # The pinned cluster's end play is the feeler setting P = 0.25 +/- 0.10
    # (option E-a); the back strap sits anywhere from hard on the back block
    # to P forward of it, at any thickness in its .X band.
    import pinion_rig_layout as rig
    from dt_pinion_bracket_geometry import THICKNESS
    from dt_pinion_bracket_spec import THICKNESS_BAND

    p_max = rig.FRONT_BLOCK_FEELER + rig.FRONT_BLOCK_FEELER_BAND
    blade = (rig.SPRING_Z - rig.SPRING_W / 2.0, rig.SPRING_Z + rig.SPRING_W / 2.0)
    for t in (THICKNESS - THICKNESS_BAND, THICKNESS + THICKNESS_BAND):
        for g in (0.0, p_max):
            outer = rig.BACK_BLOCK_Z0 - g
            inner = outer - t
            assert blade[0] >= inner + 0.1, (t, g)
            assert blade[1] <= outer - 0.1, (t, g)
