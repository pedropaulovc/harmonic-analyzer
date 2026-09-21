"""Offline contracts for the pinion-swing-bracket drawing."""

from __future__ import annotations

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
    return {
        **drawing.FRONT_KEEP,
        **drawing.DETAIL_KEEP,
        **drawing.LEFT_KEEP,
        **drawing.SECTION_KEEP,
    }


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
    assert len(kept) == sum(
        len(group)
        for group in (
            drawing.FRONT_KEEP,
            drawing.DETAIL_KEEP,
            drawing.LEFT_KEEP,
            drawing.SECTION_KEEP,
        )
    )
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= set(kept)
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.C2C, drawing.R_END) == (
        pinion_bracket_spec.C2C,
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


def test_print_contract_carries_no_gdt_datums_or_note_block() -> None:
    # Policy rules 3 and 6: a bracket is not on the GD&T allowlist, and a note
    # block that repeats the geometry is over-specification.
    assert pinion_bracket_spec.GEOMETRIC_TOLERANCES_MM == {}
    assert pinion_bracket_spec.DRAWING_NOTES == ""
    assert not hasattr(pinion_bracket_spec, "ISOMETRIC_VIEW_NOTE")


def test_decimal_places_cover_every_marked_dimension_and_resolve_fit_bands() -> None:
    by_name = pinion_bracket_spec.DRAWING_PRECISION_BY_NAME
    assert "draw_pinion_bracket.py" in PRECISION_MIGRATED_DRAWINGS
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


def test_overall_length_is_a_derived_reference_with_spec_owned_places() -> None:
    # 43 is C2C plus the two end radii, so the sheet must not carry a driving
    # copy of it: a second toleranced overall would be a redundant chain a
    # machinist could satisfy two ways.  It IS printed, parenthesised, so the
    # bar is not sawn short of the two end radii -- and the decimal places of
    # that derived reference come from the spec, never a sheet literal.
    assert pinion_bracket_spec.OVERALL_LENGTH == (
        pinion_bracket_spec.C2C + 2.0 * pinion_bracket_spec.R_END
    )
    assert "OverallLength" not in set(pinion_bracket_spec.DRAWING_PRECISION_BY_NAME)
    assert pinion_bracket_spec.DRAWING_REFERENCE_PRECISION == 1


def test_blind_seat_dimensions_are_assigned_to_readable_views() -> None:
    # The blind floor and its depth are solid geometry in the dedicated seat
    # section. The third-angle left view owns the visible mouth diameter, its
    # through-thickness station, and the critical axis-to-axis engagement
    # location without dimensioning hidden lines.
    assert set(drawing.SECTION_KEEP) == {"PinSeatDepth"}
    assert pinion_bracket_geometry.PIN_SEAT < pinion_bracket_geometry.WIDTH
    assert set(drawing.LEFT_KEEP) == {"PinSeatDia", "PinSeatCy", "PinSeatCz", "Depth"}


def test_scallop_detail_encloses_what_it_dimensions() -> None:
    # The detail carries every scallop dimension plus the size of the pivot
    # bore whose centre is their common, reachable physical origin. The fence
    # must therefore show the whole pivot bore (so its centre mark reads as a
    # bore axis), both relief centres, and both bites.
    relief_dimensions = (
        pinion_bracket_spec.DRAWING_DIMENSIONS["CamReliefParkProfile"]
        | pinion_bracket_spec.DRAWING_DIMENSIONS["CamReliefEngagedProfile"]
    )
    assert set(drawing.DETAIL_KEEP) == relief_dimensions | {"PivotBoreDia"}
    fence_center = drawing.DETAIL_FENCE_CENTER_MM
    radius = drawing.DETAIL_FENCE_RADIUS_MM
    assert (
        math.dist((0.0, 0.0), fence_center)
        + pinion_bracket_geometry.PIVOT_BORE / 2.0
        <= radius - 1.0
    )
    for point in (
        pinion_bracket_geometry.CAM_RELIEF_PARK_CENTER,
        pinion_bracket_geometry.CAM_RELIEF_ENGAGED_CENTER,
    ):
        assert math.dist(point, fence_center) <= radius - 1.0, point
    # The bites run down the strap's left edge; both ends of each bite sit
    # inside the fence.
    edge = -pinion_bracket_geometry.HALF_WIDTH
    for cx, cy in (
        pinion_bracket_geometry.CAM_RELIEF_PARK_CENTER,
        pinion_bracket_geometry.CAM_RELIEF_ENGAGED_CENTER,
    ):
        half_chord = math.sqrt(
            pinion_bracket_geometry.CAM_RELIEF_RADIUS**2 - (edge - cx) ** 2
        )
        for end in ((edge, cy - half_chord), (edge, cy + half_chord)):
            assert math.dist(end, fence_center) <= radius - 1.0, end
    # The detail enlarges: at the sheet's 2:1 the six dimensions overprinted.
    assert drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] > 2.0


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


def test_part_config_supplies_the_title_block_fields() -> None:
    import _config

    spec = _config.parts("pinion-bracket")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 2  # the book uses two swing brackets
