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
        ("CrossHoleProfile", "CrossHoleDia"): "*deviations(CROSS_HOLE_BAND)",
        # The one band that is not a fit: user ruling (a) tightened the seat's
        # printed station for its far-face web (PIN_SEAT_WEB_WORST).
        ("PinSeatProfile", "PinSeatCz"): "PIN_SEAT_STATION_TOL",
    }
    assert pinion_bracket_spec.PIN_SEAT_STATION_TOL == 0.10
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
        (
            "PinSeatCz",
            (
                pinion_bracket_spec.PIN_SEAT_STATION_TOL,
                -pinion_bracket_spec.PIN_SEAT_STATION_TOL,
            ),
        ),
    ):
        width = abs(deviations(band)[0] - deviations(band)[1])
        assert width >= 10.0 ** -by_name[name]
    # The follower-seat height sets engagement geometry, so it is the one
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
    assert set(drawing.LEFT_KEEP) == {
        "PinSeatDia",
        "PinSeatCy",
        "Depth",
        "CrossHoleDia",
        "CrossHoleCz",
        "PinSeatCz",
        "CrossHoleFromBoreWall",
    }


def test_follower_seat_station_is_printed_from_face_a_with_a_rule_12_web() -> None:
    # Rule 12 (audit W23) under user ruling (a), Codex #858 P2: the station
    # is the model's own PinSeatCz from broad face A, never "CENTRED" prose.
    # At the general .XX grade the far-face web was 1.18, so the user approved
    # +/-0.10 on the station alone: 1.54 worst case over the 1.5 floor.
    assert "CENTRED" not in drawing.DIMENSION_CALLOUTS["PinSeatDia"]
    assert "PinSeatCz" in pinion_bracket_spec.DRAWING_DIMENSIONS["PinSeatProfile"]
    assert pinion_bracket_spec.DRAWING_PRECISION_BY_NAME["PinSeatCz"] == 2
    assert pinion_bracket_spec.PIN_SEAT_WEB_WORST >= 1.5
    assert pinion_bracket_spec.PIN_SEAT_NEAR_WEB_WORST >= 2.0
    # pc-ra eye pass: a symmetric +/- band (ASME Y14.5), printed at the
    # dimension's own two places ("4.50 +/-0.10"), set on the model.
    import inspect

    build_source = inspect.getsource(bracket)
    assert (
        '_tolerance_at_dimension_places(adapter, "PinSeatProfile", "PinSeatCz")'
        in build_source
    )
    # Both through-thickness stations print left of face A with their arrows
    # inside the span: centred, the cross hole's threw its right arrow outside,
    # into the THRU callout's leader (pc-rc eye pass, nit D).
    face_a = drawing.LEFT_CENTER[0] - (
        pinion_bracket_geometry.THICKNESS * drawing.SHEET_SCALE[0] / 2000.0
    )
    for name in ("PinSeatCz", "CrossHoleCz"):
        assert drawing.LEFT_KEEP[name][0] < face_a, name


def _segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


# Callout geometry calibrated on the pc-ra render (7f7b58460): a 2.7 mm
# character pitch and a 5.3 mm row pitch put the leader's start -- the near
# end of the callout's underline -- within 3 mm of where SolidWorks drew it
# for both hole callouts.
_CHAR_PITCH = 0.0027
_ROW_PITCH = 0.0053


def _leader_start(name: str, hole: tuple[float, float]) -> tuple[float, float]:
    """The near end of a hole callout's underline: the leader's start."""
    lines = drawing.DIMENSION_CALLOUTS[name].splitlines()
    half_width = max(len(line) for line in lines) * _CHAR_PITCH / 2.0
    rows = len(lines) + 2  # the diameter and its stacked tolerance
    x, y = drawing.LEFT_KEEP[name]
    near = x - half_width if hole[0] < x else x + half_width
    return near, y - rows * _ROW_PITCH / 2.0


def test_hole_callout_leaders_keep_off_the_other_hole() -> None:
    # pc-ra eye pass (Main, nit C): the follower-seat leader grazed the cross
    # hole's rim, a few pixels from the cross hole's own leader, so a reader
    # could not tell which callout owned which hole.  The layout audit sees
    # leader crossings, not leader-to-feature clearance, so this models each
    # leader (underline end to hole centre) and holds it at least 1 mm (sheet)
    # clear of the OTHER hole's circle, arriving on a clearly different
    # bearing.  At the pc-ra layout the seat leader passed 2.2 mm from the
    # cross hole's centre against the 2.6 mm this requires.
    scale = drawing.SHEET_SCALE[0] / 1000.0
    x = drawing.LEFT_CENTER[0]
    seat = (x, drawing._flank_y(-pinion_bracket_geometry.PIN_DROP))
    cross = (x, drawing._flank_y(0.0))
    seat_r = pinion_bracket_geometry.PIN_BORE / 2.0 * scale
    cross_r = pinion_bracket_spec.CROSS_HOLE_DIA / 2.0 * scale
    seat_leader = (_leader_start("PinSeatDia", seat), seat)
    cross_leader = (_leader_start("CrossHoleDia", cross), cross)
    assert _segment_distance(cross, *seat_leader) >= cross_r + 0.001
    assert _segment_distance(seat, *cross_leader) >= seat_r + 0.001
    bearing = [
        math.degrees(math.atan2(start[1] - hole[1], start[0] - hole[0]))
        for start, hole in (seat_leader, cross_leader)
    ]
    assert abs(bearing[0] - bearing[1]) >= 45.0


def test_blind_seat_entry_face_is_complete_solid_flank() -> None:
    # The full follower-seat mouth lies on the straight flank between the two
    # rounded ends. Its complete diameter and blind depth therefore remain in
    # solid stock without opening into an adjacent cut.
    seat_y = -pinion_bracket_geometry.PIN_DROP
    seat_radius = pinion_bracket_geometry.PIN_BORE / 2.0
    straight_end = pinion_bracket_geometry.C2C
    assert seat_y - seat_radius >= 0.0
    assert seat_y + seat_radius <= straight_end
    assert (
        pinion_bracket_geometry.WIDTH - pinion_bracket_geometry.PIN_SEAT >= seat_radius
    )
    assert seat_y - pinion_bracket_geometry.PIVOT_BORE / 2.0 > 1.0


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


def test_set_pin_cross_hole_is_located_by_model_dimensions() -> None:
    # Codex #858 P2, user ruling (a): no location lives in prose.  Through the
    # thickness the model's own CrossHoleCz (half the thickness from broad
    # face A) prints at .XX; across the bar a hidden construction reference
    # sketch owns the hole's distance from the pivot-bore wall ("PivotBore" /
    # 2), which the side view shows and prints at .XX.  The callout keeps only
    # THRU and the pin it takes.  Main overrode the loose-SUPPLY wording once
    # MHA-145 became a modelled BOM line (2 used): supplying one per strap
    # would double the order, so the callout names the part, and its number
    # is the parts registry's.
    import inspect

    import _config

    callout = drawing.DIMENSION_CALLOUTS["CrossHoleDia"]
    assert callout is pinion_bracket_spec.CROSS_HOLE_CALLOUT
    assert "AXIS" not in callout and "CENTRED" not in callout
    assert "SUPPLY" not in callout and "LOOSE" not in callout
    number = _config.parts("pinion-strap-pin")["number"]
    assert callout.splitlines() == ["THRU", f"FOR {number} SPRING PIN"]
    dims = pinion_bracket_spec.DRAWING_DIMENSIONS
    assert dims["CrossHoleProfile"] == {"CrossHoleDia", "CrossHoleCz"}
    assert dims["CrossHoleAxisReference"] == {"CrossHoleFromBoreWall"}
    by_name = pinion_bracket_spec.DRAWING_PRECISION_BY_NAME
    assert by_name["CrossHoleDia"] == 2
    assert by_name["CrossHoleCz"] == 2
    assert by_name["CrossHoleFromBoreWall"] == 2
    # Both locations are the model's relations to its globals, not typed
    # numbers, and the reference sketch is saved hidden so it never renders
    # in an assembly.
    build_source = inspect.getsource(bracket)
    assert "'\"StrapThickness\" / 2'" in build_source
    assert "(wall_dims[0], '\"PivotBore\" / 2')" in build_source
    assert 'blank_sketch(adapter, "CrossHoleAxisReference")' in build_source
    # A part-hidden owner sketch delivers nothing to the plain import, so the
    # side view that keeps its dimension imports through the hidden-owner form.
    draw_source = inspect.getsource(drawing)
    assert "left_annotations = curate_hidden_owner_dimensions(" in draw_source
    assert pinion_bracket_spec.CROSS_HOLE_DIA == 25.4 / 16.0
    # The spring pin's own band, resolvable at two places.
    assert pinion_bracket_spec.CROSS_HOLE_BAND == (0.06, 0.0)


# Title-block general grades by printed decimal places (.X, .XX, .XXX).
_GENERAL_GRADE = {1: 0.8, 2: 0.51, 3: 0.13}
# The 0.05 drilled-hole allowance every web budget on this strap carries.
_DRILL_ALLOWANCE = 0.05
_WEB_FLOOR = 1.5


def _printed_band(name: str) -> float:
    """The half-width a location can wander on the print: its own model band
    when it carries one, else its decimal places' general grade."""
    own = {"PinSeatCz": pinion_bracket_spec.PIN_SEAT_STATION_TOL}
    if name in own:
        return own[name]
    return _GENERAL_GRADE[pinion_bracket_spec.DRAWING_PRECISION_BY_NAME[name]]


def test_every_web_and_ligament_clears_the_floor_at_the_printed_bands() -> None:
    # User ruling (a): each thin wall around the two pin holes is recomputed
    # here from the model constants and the bands the sheet PRINTS (decimal
    # places or a model band), so a later tolerance or precision change that
    # thins one under the 1.5 floor fails loud.
    import pinion_pivot_shaft_spec as shaft
    import pinion_strap_pin_spec as pin

    geometry = pinion_bracket_geometry
    thickness_min = geometry.THICKNESS - _printed_band("Depth")
    hole_r = (
        pinion_bracket_spec.CROSS_HOLE_DIA + pinion_bracket_spec.CROSS_HOLE_BAND[0]
    ) / 2.0
    seat_r = (geometry.PIN_BORE + pinion_bracket_spec.PIN_SEAT_DIA_BAND[0]) / 2.0
    bore_r = (geometry.PIVOT_BORE + pinion_bracket_spec.PIVOT_BORE_BAND[0]) / 2.0
    shaft_min = shaft.SHAFT_DIA + shaft.SHAFT_DIA_BAND[1]
    half = geometry.THICKNESS / 2.0
    # The bore-wall offset's nominal (3.175) does not print exactly at two
    # places, so the offset carries its rounding too (restricted review).
    places = pinion_bracket_spec.DRAWING_PRECISION_BY_NAME["CrossHoleFromBoreWall"]
    wall = geometry.PIVOT_BORE / 2.0
    hole_height = _printed_band("CrossHoleFromBoreWall") + abs(
        round(wall, places) - wall
    )
    seat_height = _printed_band("PinSeatCy")
    worst = {
        # Cross hole to the far and the near broad face.
        "cross hole far face": thickness_min
        - (half + _printed_band("CrossHoleCz"))
        - hole_r
        - _DRILL_ALLOWANCE,
        "cross hole near face": half
        - _printed_band("CrossHoleCz")
        - hole_r
        - _DRILL_ALLOWANCE,
        # Follower seat to the far and the near broad face.
        "seat far face": thickness_min
        - (half + _printed_band("PinSeatCz"))
        - seat_r
        - _DRILL_ALLOWANCE,
        "seat near face": half - _printed_band("PinSeatCz") - seat_r - _DRILL_ALLOWANCE,
        # The match-drilled hole off the shaft axis thins the shaft wall.
        "shaft wall": (shaft_min - 2.0 * hole_r) / 2.0 - hole_height,
        # Follower seat down to the pivot bore and to the cross hole.
        "seat to pivot bore": abs(geometry.PIN_DROP)
        - seat_height
        - seat_r
        - bore_r
        - _DRILL_ALLOWANCE,
        "seat to cross hole": abs(geometry.PIN_DROP)
        - seat_height
        - hole_height
        - seat_r
        - hole_r
        - _DRILL_ALLOWANCE,
    }
    thin = {name: round(web, 3) for name, web in worst.items() if web < _WEB_FLOOR}
    assert not thin, f"webs under the {_WEB_FLOOR} floor: {thin}"
    # The spec constants the build and review cite are these same worst cases.
    assert math.isclose(worst["cross hole far face"], pin.STRAP_FACE_WEB_WORST)
    assert math.isclose(worst["seat far face"], pinion_bracket_spec.PIN_SEAT_WEB_WORST)
    assert math.isclose(
        worst["seat near face"], pinion_bracket_spec.PIN_SEAT_NEAR_WEB_WORST
    )
    assert math.isclose(worst["shaft wall"], pin.SHAFT_LIGAMENT_WORST)
    # Restricted review (ruling 3): the places the web gates read are the
    # sheet's own, stated once in pinion_bracket_geometry.
    for name, places in (
        ("Depth", geometry.THICKNESS_PLACES),
        ("CrossHoleCz", geometry.CROSS_HOLE_CZ_PLACES),
        ("CrossHoleFromBoreWall", geometry.CROSS_HOLE_FROM_BORE_WALL_PLACES),
        ("BottomCapRadius", geometry.END_RADIUS_PLACES),
        ("TopCapRadius", geometry.END_RADIUS_PLACES),
    ):
        assert pinion_bracket_spec.DRAWING_PRECISION_BY_NAME[name] == places, name
    pin_source = Path(pin.__file__).read_text(encoding="utf-8")
    assert "DOT_X_BAND" not in pin_source and "DOT_XX_BAND" not in pin_source
    # The values the ruling approved.
    assert math.isclose(worst["cross hole far face"], 2.316, abs_tol=5e-4)
    assert math.isclose(worst["seat far face"], 1.544, abs_tol=5e-4)
    assert math.isclose(worst["shaft wall"], 1.826, abs_tol=5e-4)
