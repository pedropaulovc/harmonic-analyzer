"""Offline contracts for the pinion-swing-bracket drawing."""

from __future__ import annotations

import itertools
import math
from pathlib import Path

import pinion_bracket_spec
import pinion_bracket_geometry
import draw_pinion_bracket as drawing
import build_pinion_bracket as bracket
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import REAM_H7, REAM_SLIDE, deviations


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-bracket_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_bracket"].script == Path(drawing.__file__).resolve()


def _kept() -> dict[str, tuple[float, float]]:
    return {**drawing.FRONT_KEEP, **drawing.LEFT_KEEP}


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert bracket.DRAWING_DIMENSIONS is pinion_bracket_spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is pinion_bracket_spec.DRAWING_DIMENSIONS
    assert bracket.SURFACE_FINISHES is pinion_bracket_spec.SURFACE_FINISHES
    assert drawing.SURFACE_FINISHES is pinion_bracket_spec.SURFACE_FINISHES
    marked = set().union(*pinion_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = _kept()
    assert set(kept) == marked
    # Each name is shown exactly once: a dimension repeated across two views is a
    # double specification, and the second copy is what drifts.
    assert len(kept) == len(drawing.FRONT_KEEP) + len(drawing.LEFT_KEEP)
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= set(kept)
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.C2C, drawing.OVERALL_LENGTH, drawing.R_END) == (
        pinion_bracket_spec.C2C,
        pinion_bracket_spec.OVERALL_LENGTH,
        pinion_bracket_spec.R_END,
    )
    assert pinion_bracket_spec.C2C == pinion_bracket_geometry.C2C


def test_drive_train_recipe_depends_on_geometry_not_drawing_notes() -> None:
    drive_train = Path(__file__).with_name("build_drive_train_assembly.py")
    dependency_names = {Path(path).name for path in module_deps_of(drive_train)}
    assert "pinion_bracket_geometry.py" in dependency_names
    assert "build_pinion_bracket.py" not in dependency_names
    assert "pinion_bracket_spec.py" not in dependency_names


def test_every_band_traces_to_a_named_fit_class() -> None:
    # Policy rule 1: a per-feature band exists only where a fit demands it, and
    # its numbers come from the shared fit table rather than a local literal.
    # Three features qualify -- two running bores and the pressed follower seat.
    assert model_toleranced_dimensions(bracket) == {
        ("StrapProfile", "PivotBoreDia"): "*deviations(PIVOT_BORE_BAND)",
        ("StrapProfile", "ArborBoreDia"): "*deviations(ARBOR_BORE_BAND)",
        ("PinSeatProfile", "PinSeatDia"): "*deviations(PIN_SEAT_DIA_BAND)",
    }
    assert pinion_bracket_spec.PIVOT_BORE_BAND is REAM_SLIDE
    assert pinion_bracket_spec.ARBOR_BORE_BAND is REAM_SLIDE
    assert pinion_bracket_spec.PIN_SEAT_DIA_BAND is REAM_H7
    # A running bore must be able to end up LARGER than nominal and a pressed
    # seat must not: that sign difference is the whole reason the two classes
    # differ, and swapping them would be silent on the sheet.
    assert deviations(REAM_SLIDE)[0] > 0.0
    assert deviations(REAM_H7)[0] == 0.0


def test_print_carries_no_gdt_no_datums_and_no_note_block() -> None:
    # Policy rules 3 and 6: a bracket is not on the GD&T allowlist, and a note
    # block that repeats the geometry is the classic over-specification.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature" not in source
    assert "add_feature_control_frame" not in source
    assert "add_property_linked_note" not in source
    assert pinion_bracket_spec.GEOMETRIC_TOLERANCES_MM == {}
    assert pinion_bracket_spec.DRAWING_NOTES == ""
    # Nothing may re-appear through a title-block property either.
    part_source = Path(bracket.__file__).read_text(encoding="utf-8")
    for retired in ("Manufacturing Notes", "Isometric View Note"):
        assert retired not in source
        assert retired not in part_source
    assert not hasattr(pinion_bracket_spec, "ISOMETRIC_VIEW_NOTE")


def test_callouts_state_processes_and_never_restate_numbers() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    # The only thing a callout adds is what the dimension cannot say: how the
    # feature is made and whether it goes through.
    assert callouts["PivotBoreDia"] == "REAM THRU"
    assert callouts["ArborBoreDia"] == "REAM THRU"
    assert callouts["PinSeatDia"] == "REAM; FLAT-BOTTOM BLIND"
    # The blind seat's depth and the one finely-held location each say what
    # the number alone cannot: where the depth is measured from, and why the
    # station is held tighter than the title block's general grade.
    assert callouts["PinSeatDepth"] == "DEPTH FROM ENTRY FACE"
    assert callouts["PinSeatCy"] == "CAM CLEARANCE"
    joined = "\n".join(callouts.values())
    assert "+/-" not in joined
    assert not any(character.isdigit() for character in joined)
    assert "DATUM" not in joined


def test_decimal_places_are_authored_on_the_part_and_only_read_by_the_sheet() -> None:
    # Policy rule 2: the model owns display precision. The part applies the map
    # and the sheet proves the import kept it; a sheet-side setter would be a
    # second, divergent tolerance statement.
    part_source = Path(bracket.__file__).read_text(encoding="utf-8")
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in part_source
    assert "set_dimension_precision" not in sheet_source
    assert "assert_imported_precision" in sheet_source
    assert "draw_pinion_bracket.py" in PRECISION_MIGRATED_DRAWINGS
    by_name = pinion_bracket_spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set(_kept())
    # A banded dimension must print finely enough to resolve its own band,
    # otherwise the displayed limits round into each other.
    for name, band in (
        ("PivotBoreDia", pinion_bracket_spec.PIVOT_BORE_BAND),
        ("ArborBoreDia", pinion_bracket_spec.ARBOR_BORE_BAND),
        ("PinSeatDia", pinion_bracket_spec.PIN_SEAT_DIA_BAND),
    ):
        width = abs(deviations(band)[0] - deviations(band)[1])
        assert width >= 10.0 ** -by_name[name]
    # The follower-seat height rides the cam clearance budget, so it is the one
    # dimension held to the title block's finest general grade.
    assert by_name["PinSeatCy"] == 3
    assert max(by_name.values()) == 3
    # The single sheet-created dimension is a reference, so its places come
    # from the spec rather than a literal.
    assert pinion_bracket_spec.DRAWING_REFERENCE_PRECISION == 1
    assert "SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)" in sheet_source


def test_overall_length_is_a_reference_of_the_dimensioned_features() -> None:
    # It is (43) in parentheses because C2C and the two end radii already
    # drive it; a toleranced copy would be a redundant chain.
    assert pinion_bracket_spec.OVERALL_LENGTH == (
        pinion_bracket_spec.C2C + 2.0 * pinion_bracket_spec.R_END
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimension" in source
    assert "OverallLength" not in set().union(
        *pinion_bracket_spec.DRAWING_DIMENSIONS.values()
    )


def test_only_the_face_view_carries_hidden_lines() -> None:
    # The blind follower seat is the single feature no outline shows, and only
    # the face view looks along its depth -- so it is the only view that may
    # print a dashed edge. A flank or pictorial view with hidden lines turned
    # on would dash the two through bores and both scallops for nothing.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("set_hidden_lines_visible(adapter, front)") == 1
    assert source.count("set_hidden_lines_visible") == 2  # import + the call
    assert "PinSeatDepth" in drawing.FRONT_KEEP
    # Everything else on the strap goes clean through, so nothing else needs
    # the dashed outline the face view now shows.
    assert pinion_bracket_geometry.PIN_SEAT < pinion_bracket_geometry.WIDTH
    # The seat mouth is a solid circle on the flank, which is where its size
    # and its station through the bar are dimensioned.
    assert set(drawing.LEFT_KEEP) == {"PinSeatDia", "PinSeatCz", "Depth"}


def test_blind_seat_entry_face_is_solid_flank_where_the_reamer_lands() -> None:
    # The seat's mouth has to land on flat metal above the pivot bore. The
    # parked relief scallop reaches up past the bottom tangent of that mouth,
    # so the print shows the mouth slightly interrupted -- but the entry stays
    # startable: the axis and the whole upper half of the circle are on solid
    # flank, and the nick never eats more than a tenth of the seat depth.
    seat_y = -pinion_bracket_geometry.PIN_DROP
    assert seat_y > 0.0
    assert seat_y < pinion_bracket_geometry.C2C - pinion_bracket_geometry.R_END
    assert seat_y - pinion_bracket_geometry.PIVOT_BORE / 2.0 > 1.0
    half_width = pinion_bracket_geometry.WIDTH / 2.0
    radius = pinion_bracket_geometry.CAM_RELIEF_RADIUS
    seat_half = pinion_bracket_geometry.PIN_BORE / 2.0
    worst = 0.0
    interrupted = 0.0
    steps = 64
    for centre in (
        pinion_bracket_geometry.CAM_RELIEF_PARK_CENTER,
        pinion_bracket_geometry.CAM_RELIEF_ENGAGED_CENTER,
    ):
        for step in range(steps + 1):
            probe = seat_y - seat_half + 2.0 * seat_half * step / steps
            rise = abs(probe - centre[1])
            if rise >= radius:
                continue  # the scallop never reaches this height at all
            depth = centre[0] + math.sqrt(radius**2 - rise**2) + half_width
            if depth <= 0.0:
                continue  # it stops short of the flank at this height
            worst = max(worst, depth)
            interrupted = max(interrupted, probe - (seat_y - seat_half))
            # Nothing may reach the axis height or above it.
            assert probe < seat_y
    assert worst < 0.15 * pinion_bracket_geometry.PIN_SEAT
    assert interrupted < 0.2 * pinion_bracket_geometry.PIN_BORE


def test_cam_scallops_are_dimensioned_the_way_they_are_cut() -> None:
    # Two plunges of one cutter: each centre located from the pivot-bore axis,
    # each carrying a RADIUS, both radii driven by a single equation global so
    # they cannot drift apart.
    dims = pinion_bracket_spec.DRAWING_DIMENSIONS
    assert dims["CamReliefParkProfile"] == {
        "CamReliefParkX",
        "CamReliefParkY",
        "CamReliefParkR",
    }
    assert dims["CamReliefEngagedProfile"] == {
        "CamReliefEngagedX",
        "CamReliefEngagedY",
        "CamReliefEngagedR",
    }
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert 'relief.record(f"CamRelief{label}R", \'"CamReliefRadius"\')' in source
    assert '"CamReliefRadius", f"{CAM_RELIEF_RADIUS}mm"' in source
    # No diameter callout survives on an arc that never closes on the part.
    assert "CamReliefDia" not in source
    assert pinion_bracket_geometry.CAM_RELIEF_MIN_PIVOT_LIGAMENT >= 2.5


def test_strap_thickness_carries_the_cam_pin_seat_and_the_photo_band() -> None:
    # Re-derived from the ch25 photograph against the O22.433 drum: the strap
    # measures 7.6-9.4 mm thick, and the blind O4 follower seat needs real web
    # on both sides of it -- which the retired 5.0 could not give.
    thickness = pinion_bracket_geometry.THICKNESS
    assert 7.6 <= thickness <= 9.4
    web = (thickness - pinion_bracket_geometry.PIN_BORE) / 2.0
    assert web >= 1.5
    assert pinion_bracket_geometry.PIN_BORE < thickness


def test_label_positions_are_on_the_sheet_and_do_not_collide() -> None:
    # Every annotation the recipe places by hand, checked against the ASME B
    # sheet it is placed on. Two labels closer than a text height print as one
    # unreadable smear in the PDF.
    positions = {
        **{f"front:{k}": v for k, v in drawing.FRONT_KEEP.items()},
        **{f"left:{k}": v for k, v in drawing.LEFT_KEEP.items()},
        "front:pivot-finish": drawing.PIVOT_FINISH_XY,
        "front:arbor-finish": drawing.ARBOR_FINISH_XY,
    }
    for name, (x, y) in positions.items():
        assert 0.012 <= x <= 0.420, name
        assert 0.012 <= y <= 0.268, name
    for (left_name, left_xy), (right_name, right_xy) in itertools.combinations(
        positions.items(), 2
    ):
        gap = math.dist(left_xy, right_xy)
        assert gap >= 0.008, f"{left_name} and {right_name} overlap ({gap:.4f} m)"


def test_part_config_supplies_the_title_block_fields() -> None:
    import _config

    spec = _config.parts("pinion-bracket")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 2  # the book uses two swing brackets
