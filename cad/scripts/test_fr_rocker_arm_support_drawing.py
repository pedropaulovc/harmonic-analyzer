"""Offline contracts for the rocker-arm-support drawing."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import solidworks_mcp.adapters

import _config
import _drawing_sections
import build_fr_frame_assembly as frame
import build_fr_rocker_arm_support as support
import build_fr_vn_lag_screw as stock_screw
import draw_fr_rocker_arm_support as drawing
import fr_rocker_arm_support_drawing_spec as drawing_spec
import fr_rocker_arm_support_section_spec as section
import fr_rocker_arm_support_spec as placement
import rocker_bracket_seat_layout as seats
import fr_vn_lag_screw_spec as screw


def test_drawing_keeps_only_make_critical_model_dimensions() -> None:
    locations = {
        "CavityEndStation",
        "CavityTopStation",
        "PocketEndStation",
        "PocketBottomStation",
        "WebFaceStation",
        "TopFlatPlusZStation",
    }
    expected = {
        "FootSpan",
        "WallHeight",
        "Depth",
        "WinWidth",
        "CavWidth",
        "PocketRadius",
        "CavityRadius",
        "RimChamferSize",
        "SeatEastStation",
        "SeatWestStation",
        *locations,
    }
    marked = set().union(*support.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.VIEW_B_KEEP)
    assert kept == marked == expected
    assert set(drawing.DIMENSION_CALLOUTS) == {
        "WinWidth",
        "PocketRadius",
        "CavityRadius",
        "CavWidth",
        "RimChamferSize",
        "PocketEndStation",
        "PocketBottomStation",
        "TopFlatPlusZStation",
    }
    part_owned = {
        "RimChamferSize",
        "SeatEastStation",
        "SeatWestStation",
        *locations,
    }
    assert set(drawing.PART_PRECISION) == part_owned
    assert drawing.DIMENSION_PRECISION == {
        **dict.fromkeys(expected - part_owned, 2),
        "WebThickness": 2,
        "FootThickness": 2,
    }
    # The chamfer leg is .06 exactly on its .XX grid (fleet ruling: .06/.03).
    assert support.CHAMFER == pytest.approx(0.06 * 25.4)
    places = drawing.PART_PRECISION["RimChamferSize"]
    assert places == 2
    assert support.CHAMFER == pytest.approx(
        round(support.CHAMFER / 25.4, places) * 25.4
    )


def test_pocket_and_cavity_reliefs_are_distinct() -> None:
    assert support.FILLET_R == 12.7
    assert {tuple(edge) for edge in support.FILLET_EDGES} == {
        (x_sign * support.CAV, y_sign * support.CAV, 0.0)
        for x_sign in (-1, 1)
        for y_sign in (-1, 1)
    }
    assert support.POCKET_FILLET_R == 6.35
    assert len(support.POCKET_FILLET_EDGES) == 8
    assert {abs(edge[0]) for edge in support.POCKET_FILLET_EDGES} == {support.BIG}
    assert {edge[1] for edge in support.POCKET_FILLET_EDGES} == {
        -support.BIG,
        support.BIG,
    }
    assert all(abs(edge[2]) > support.WEB for edge in support.POCKET_FILLET_EDGES)


def test_no_process_callout_on_the_sheet() -> None:
    # "Machine both pockets" dictates method (ASME Y14.5 1.4(e)); the section's
    # web dimension defines what the pockets leave, so no callout exists.
    assert not hasattr(support, "WEB_CALLOUT")


def test_support_finish_masks_both_mating_faces() -> None:
    # #2108 review: the base underside seats on the harmonic base and the
    # top face under the MHA-CH-08 feet; the finish names both.
    assert _config.parts(support.PART_NAME)["finish"] == (
        "GREEN ENAMEL; MASK FOOT UNDERSIDE AND TOP FACE; OIL BARE FACES"
    )
    assert support.HOLE_SPEC.kind == "drilled_fractional"
    assert support.HOLE_SPEC.size == "5/16"
    assert support.HOLE_DIA == pytest.approx(7.938)


def test_mounting_face_carries_the_seat_finish_symbol_not_a_note() -> None:
    # The foot seats on harmonic-base: the one face that MUST be cut on a part
    # the title block otherwise leaves CAST/MACHINED. It is the -Y face at
    # y = -HALF_Y (PlanarFace offsets run along the outward normal, so +HALF_Y),
    # and the drawing places the symbol, not a text callout.
    (control,) = drawing_spec.SURFACE_FINISHES
    assert control.key == "mounting_face"
    assert control.roughness_um == 3.2
    assert control.face.normal == (0, -1, 0)
    assert control.face.offset_mm == support.HALF_Y == drawing_spec.HALF_Y


def test_native_hole_table_covers_every_foot_hole() -> None:
    # 2.375 x .687 off the support's centre, on the .001 in grid.
    expected_holes = {
        (sx * 2.375 * 25.4, sz * 0.687 * 25.4) for sx in (-1, 1) for sz in (-1, 1)
    }
    assert {(round(x, 9), round(z, 9)) for x, z in support.HOLES} == {
        (round(x, 9), round(z, 9)) for x, z in expected_holes
    }
    assert drawing.HOLE_TABLE_DATUM_XZ_MM == (
        -support.BOSS_DEPTH / 2.0,
        -support.WIDE,
    )
    # The table prints inch LOC cells from the -X end face and the -Z foot
    # edge: 3.78 -/+ 2.375 and 1.250 +/- .687.
    printed_in = {
        (round(x / 25.4, 9), round(z / 25.4, 9))
        for x, z in drawing.EXPECTED_HOLE_TABLE_LOCATIONS_MM
    }
    assert printed_in == {
        (6.155, 1.937),
        (1.405, 1.937),
        (6.155, 0.563),
        (1.405, 0.563),
    }
    points = {drawing._bottom_sheet_xy(hole) for hole in expected_holes}
    assert len(points) == 4
    half_w = support.BOSS_DEPTH / 2.0 * drawing.VIEW_SCALE / 1000.0
    half_h = support.WIDE * drawing.VIEW_SCALE / 1000.0
    for x, y in points:
        assert abs(x - drawing.BOTTOM_CENTER[0]) <= half_w
        assert abs(y - drawing.BOTTOM_CENTER[1]) <= half_h


def test_projected_views_remain_aligned() -> None:
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    assert drawing.BOTTOM_CENTER[0] == drawing.FRONT_CENTER[0]


def test_support_has_no_unapproved_gdt_contract() -> None:
    assert not hasattr(placement, "GEOMETRIC_TOLERANCES_MM")


def test_stock_hold_down_clears_support_and_engages_finite_through_base_tap() -> None:
    import fr_harmonic_base_fasteners as base
    import fr_harmonic_base_spec as base_spec

    assert stock_screw.SPEC.skus == ("92240A540",)
    assert screw.THREAD_SIZE == base.HOLD_DOWN_THREAD == "1/4-20"
    assert (screw.THREAD_CLASS, base.HOLD_DOWN_THREAD_CLASS) == ("2A", "2B")
    assert screw.THREAD_LEN == screw.SHANK_LEN
    assert screw.SHANK_DIA < support.HOLE_DIA < screw.HEAD_AF
    assert frame.LAG_SUPPORT_CLEARANCE_DIA == support.HOLE_DIA
    assert frame.LAG_SCREW_UNDER_HEAD_Y - screw.BEARING_OFFSET == pytest.approx(
        frame.BASE_TOP_Y + support.FOOT_THICKNESS
    )
    assert frame.LAG_BASE_ENGAGEMENT == pytest.approx(base.HOLD_DOWN_ENGAGEMENT)
    assert base.HOLD_DOWN_ENGAGEMENT == pytest.approx(
        screw.SHANK_LEN - support.FOOT_THICKNESS - screw.BEARING_OFFSET
    )
    assert base.HOLD_DOWN_ENGAGEMENT / screw.SHANK_DIA >= 1.5
    assert base.HOLD_DOWN_SEAT_SPEC.end == "through_all"
    assert len(frame.LAG_BASE_THREAD_FITS) == len(frame.LAG_SCREW_XZ) == 4
    for xz, fit in zip(frame.LAG_SCREW_XZ, frame.LAG_BASE_THREAD_FITS, strict=True):
        material = base.through_seat_material(base.HOLD_DOWN_SEAT_SPEC, xz)
        assert material.nominal_segments_mm == ((0.0, base_spec.POCKET_SKIN),)
        # The base's .51 skin at its .XX band (FrBase, MHA-FR-01).
        assert material.exit_depth_min_mm == pytest.approx(0.48 * 25.4)
        assert material.exit_depth_max_mm == pytest.approx(0.54 * 25.4)
        assert fit.full_thread_engagement_min_mm == pytest.approx(10.1996875)
        assert fit.full_thread_engagement_min_mm >= 1.5 * screw.SHANK_DIA
        assert fit.protrusion_max_mm == pytest.approx(
            base.HOLD_DOWN_INSERTION_MAX_MM - material.exit_depth_min_mm,
        )
        assert fit.protrusion_max_mm > 0.0
        assert fit.clearance_min_mm > 0.0
    assert frame.LAG_SCREW_TIP_Y == pytest.approx(
        frame.BASE_TOP_Y - base.HOLD_DOWN_ENGAGEMENT
    )


def test_bottom_view_picks_actual_clearance_rim_at_each_station() -> None:
    for x_mm, z_mm in support.HOLES:
        sheet_x, sheet_y = drawing._bottom_sheet_xy((x_mm, z_mm))
        picked_x = (sheet_x - drawing.BOTTOM_CENTER[0]) * 1000 / drawing.VIEW_SCALE
        picked_z = (sheet_y - drawing.BOTTOM_CENTER[1]) * 1000 / drawing.VIEW_SCALE
        assert math.hypot(picked_x - x_mm, picked_z - z_mm) == pytest.approx(
            support.HOLE_DIA / 2.0
        )


def test_support_keeps_original_world_placement_and_hold_down_pattern() -> None:
    assert placement.SUPPORT_WORLD_Z == 0.0
    # 2.375 either side of the support's centre plane.
    assert {round(z / 25.4, 9) for _, z in placement.SUPPORT_HOLD_DOWN_XZ} == {
        -2.375,
        2.375,
    }


class _FakeSketchManager:
    """Records the ``CreateLine`` call and can snap the segment like inference.

    ``add_to_db`` is the mode the seat is already in when the helper runs: a
    seat left in direct-to-DB mode by an earlier leaf must get THAT value back,
    which a fake hard-wired to ``False`` cannot tell apart from a restore that
    always writes ``False``. ``snap_at`` picks which endpoint inference moves,
    and ``raises`` makes ``CreateLine`` fail so the restore can be proved on
    the exception path -- a leaked ``AddToDB = True`` poisons every later
    sketch on the shared seat, which is the whole reason for the guard.
    """

    def __init__(
        self,
        snap: tuple[float, float, float] = (0.0, 0.0, 0.0),
        *,
        add_to_db: bool = False,
        snap_at: str = "end",
        raises: Exception | None = None,
    ) -> None:
        self.AddToDB = add_to_db
        self.add_to_db_when_created: bool | None = None
        self.calls: list[tuple[float, ...]] = []
        self._snap = snap
        self._snap_at = snap_at
        self._raises = raises

    def CreateLine(self, *args: float) -> SimpleNamespace:
        self.add_to_db_when_created = self.AddToDB
        self.calls.append(args)
        if self._raises is not None:
            raise self._raises
        shifted = tuple(
            value + shift
            for value, shift in zip(
                args[0:3] if self._snap_at == "start" else args[3:6], self._snap
            )
        )
        start = shifted if self._snap_at == "start" else tuple(args[0:3])
        end = tuple(args[3:6]) if self._snap_at == "start" else shifted
        return SimpleNamespace(
            GetStartPoint2=lambda: SimpleNamespace(X=start[0], Y=start[1], Z=start[2]),
            GetEndPoint2=lambda: SimpleNamespace(X=end[0], Y=end[1], Z=end[2]),
            Select4=lambda append, data: True,
        )


def _member(obj, name):
    """Stand in for the adapter's method-or-property COM read."""
    value = getattr(obj, name)
    return value() if callable(value) else value


def _section_doubles(
    monkeypatch,
    scale: float,
    snap: tuple[float, float, float] = (0.0, 0.0, 0.0),
    *,
    add_to_db: bool = False,
    snap_at: str = "end",
    raises: Exception | None = None,
) -> SimpleNamespace:
    origin = drawing.FRONT_CENTER
    transform = object()
    points: list[tuple[float, ...]] = []

    def make_point(values):
        points.append(tuple(values))

        def multiply(actual_transform):
            assert actual_transform is transform
            return SimpleNamespace(
                ArrayData=(
                    (values[0] - origin[0]) / scale,
                    (values[1] - origin[1]) / scale,
                    0.0,
                )
            )

        return SimpleNamespace(MultiplyTransform=multiply)

    math_utility = SimpleNamespace(CreatePoint=make_point)
    sketch = SimpleNamespace(ModelToSketchTransform=transform)
    parent = SimpleNamespace(GetSketch=lambda: sketch)
    section_definition = Mock()
    section_definition.SetLabel2.return_value = 0
    section = Mock()
    section.GetSection.return_value = section_definition
    section.SetViewPosition.return_value = True
    sketch_manager = _FakeSketchManager(
        snap, add_to_db=add_to_db, snap_at=snap_at, raises=raises
    )
    model = Mock()
    model.ActivateView.return_value = True
    model.SketchManager = sketch_manager
    model.SelectionManager = SimpleNamespace(
        CreateSelectData=lambda: SimpleNamespace(View=None),
        GetSelectedObjectCount2=lambda mark: 1,
    )
    model.CreateSectionViewAt5.return_value = section
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(GetMathUtility=lambda: math_utility),
        _get_attr_or_call=lambda obj, name: _member(obj, name),
    )
    monkeypatch.setattr(_drawing_sections, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(_drawing_sections, "view_name", lambda *_: "Front")
    monkeypatch.setattr(_drawing_sections, "double_array", tuple)
    monkeypatch.setattr(
        solidworks_mcp.adapters.sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
    )
    return SimpleNamespace(
        adapter=adapter,
        parent=parent,
        model=model,
        section=section,
        section_definition=section_definition,
        sketch_manager=sketch_manager,
        points=points,
        start=(origin[0], origin[1] - 0.050),
        end=(origin[0], origin[1] + 0.050),
    )


@pytest.mark.parametrize("scale", [0.5, 1.0])
@pytest.mark.parametrize("seat_add_to_db", [False, True])
def test_section_cut_uses_parent_sketch_coordinates(
    monkeypatch, scale, seat_add_to_db
) -> None:
    """A centre cut must stay centred on a translated, scaled parent view.

    Native CreateLine interprets sheet coordinates a second time: the old
    helper cut x=42.5 mm off centre at 1:2 and left an unsectioned taper.

    ``seat_add_to_db`` is the mode the seat arrives in. Restoring the value we
    found is not the same as writing ``False``, and only the ``True`` case can
    tell them apart -- a seat an earlier leaf left in direct-to-DB mode must
    not be silently reset by a drawing recipe.
    """
    doubles = _section_doubles(monkeypatch, scale, add_to_db=seat_add_to_db)
    result = _drawing_sections.create_section_view(
        doubles.adapter,
        doubles.parent,
        line_start=doubles.start,
        line_end=doubles.end,
        view_xy=drawing.RIGHT_CENTER,
        section_label="A",
        scale=(1, 2),
        label="centre cut regression",
    )
    assert result is doubles.section
    assert doubles.points == [(*doubles.start, 0.0), (*doubles.end, 0.0)]
    assert doubles.sketch_manager.calls[0] == pytest.approx(
        (0.0, -0.050 / scale, 0.0, 0.0, 0.050 / scale, 0.0)
    )
    # The cutting line is authored direct-to-DB, out of sketch inference's
    # reach, and the seat's own mode is left as it was found.
    assert doubles.sketch_manager.add_to_db_when_created is True
    assert doubles.sketch_manager.AddToDB is seat_add_to_db
    doubles.section_definition.SetAutoHatch.assert_called_once_with(True)
    doubles.section_definition.SetLabel2.assert_called_once_with("A")


@pytest.mark.parametrize("seat_add_to_db", [False, True])
def test_section_cut_restores_the_seat_when_the_line_fails(
    monkeypatch, seat_add_to_db
) -> None:
    """A CreateLine that raises must still hand the seat back as it was found.

    This is the failure the guard exists for: ``AddToDB`` is a session-global
    sketch mode, so a helper that sets it and dies leaves every later sketch on
    that seat -- in this leaf and the next one -- authoring direct to the
    database with no inference at all. The restore therefore belongs in a
    ``finally``; dropping it back to the success path passes every other test
    in this file.
    """
    boom = RuntimeError("CreateLine exploded")
    doubles = _section_doubles(monkeypatch, 1.0, add_to_db=seat_add_to_db, raises=boom)
    with pytest.raises(RuntimeError, match="CreateLine exploded"):
        _drawing_sections.create_section_view(
            doubles.adapter,
            doubles.parent,
            line_start=doubles.start,
            line_end=doubles.end,
            view_xy=drawing.RIGHT_CENTER,
            section_label="A",
            scale=(1, 2),
            label="exception regression",
        )
    assert doubles.sketch_manager.add_to_db_when_created is True
    assert doubles.sketch_manager.AddToDB is seat_add_to_db
    doubles.model.CreateSectionViewAt5.assert_not_called()


@pytest.mark.parametrize("moved", ["start", "end"])
def test_section_cut_refuses_a_cutting_line_inference_moved(monkeypatch, moved) -> None:
    """A snapped endpoint tilts the cut plane; no section may be created.

    top_frame's D-D was cut 4.29 degrees oblique this way (0.674 mm off
    station at the rail face), and the tilt only surfaced much later, as a
    missing cut-face line in a different recipe's dimension pick. Inference
    snaps whichever end lands near a witness entity, so both endpoints are
    read back -- checking only the end point is a tilt of the same magnitude
    about the other pivot.
    """
    doubles = _section_doubles(
        monkeypatch, 1.0, snap=(0.0, 0.000674, 0.0), snap_at=moved
    )
    with pytest.raises(RuntimeError, match=rf"{moved} point sits 0\.674 mm"):
        _drawing_sections.create_section_view(
            doubles.adapter,
            doubles.parent,
            line_start=doubles.start,
            line_end=doubles.end,
            view_xy=drawing.RIGHT_CENTER,
            section_label="A",
            scale=(1, 2),
            label="snap regression",
        )
    doubles.model.CreateSectionViewAt5.assert_not_called()


def test_section_constants_live_in_the_pure_data_spec() -> None:
    # The base, frame and drive train read the casting's section from the
    # section spec, so a window or rail edit in the COM builder re-keys none
    # of them; the foot clearances ride the placement spec with the hold-down
    # pattern they are drilled on.
    for name in ("WIDE", "NARROW", "HALF_Y", "BIG", "FOOT_THICKNESS"):
        assert getattr(support, name) is getattr(section, name)
    for name in ("HOLE_SPEC", "HOLE_DIA"):
        assert getattr(support, name) is getattr(placement, name)
    assert drawing_spec.HALF_Y is section.HALF_Y
    assert frame.LAG_FOOT_THICKNESS is section.FOOT_THICKNESS
    # The base seats key on the foot: it stays exactly the source's 6.35.
    assert section.FOOT_THICKNESS == pytest.approx(6.35)
    assert section.BIG == pytest.approx(82.55)


def test_window_is_the_source_square_with_rails_as_deep_as_the_foot() -> None:
    """The 2026-10-09 sketch reverted #743's deeper rail: the window is the
    source's 165.1 square again, so the top rail, side posts and foot are all
    one 6.35 frame member, and the print calls the pocket square."""
    assert support.HALF_Y - support.BIG == pytest.approx(section.FOOT_THICKNESS)
    assert drawing.DIMENSION_CALLOUTS["WinWidth"] == "SQ POCKET BOTH SIDES"
    assert {abs(edge[1]) for edge in support.POCKET_FILLET_EDGES} == {support.BIG}


def test_web_volume_deltas_are_the_closed_forms() -> None:
    """The source casting's native targets plus the .50 web's deltas, the
    longer wall's (7.56 for the source's 7.000) and the .330 top's: the
    window and cavity cut inside the side posts, so every stage gains the
    trapezoid's area times the added length; the narrower top changes the
    thickness every through cut removes."""
    growth = support.WEB - support.SOURCE_WEB
    assert growth == pytest.approx(3.175)
    assert support.BOSS_DEPTH == pytest.approx(2.0 * placement.SUPPORT_HALF_MACHINE_Z)
    assert support.SOURCE_BOSS_DEPTH == 177.8
    wall = (
        (support.WIDE + support.NARROW)
        * 2.0
        * support.HALF_Y
        * (support.BOSS_DEPTH - support.SOURCE_BOSS_DEPTH)
    )
    assert support.WALL_GROWTH_VOLUME == pytest.approx(wall)
    # The top half-width moved from the source's 8.4665 to .330; each slant
    # face moves in proportion to height, so a through cut over a region
    # symmetric in Y removes the delta times its area from the two halves.
    delta = support.NARROW - 8.4665
    taper_wall = delta * 2.0 * support.HALF_Y * support.SOURCE_BOSS_DEPTH
    cavity_area = (2.0 * support.CAV) ** 2
    net_area = (2.0 * support.BIG) ** 2 - cavity_area
    taper_cut1 = taper_wall - delta * cavity_area - delta * net_area / 2.0
    taper_cut2 = taper_wall - delta * cavity_area - delta * net_area
    assert support.WALL_VOLUME - support.SOURCE_WALL_VOLUME == pytest.approx(
        wall + taper_wall
    )
    assert support.CAVITY_CUT_VOLUME - support.SOURCE_CAVITY_CUT_VOLUME == (
        pytest.approx(wall + taper_wall - delta * cavity_area)
    )
    band = net_area * growth
    assert support.WINDOW_CUT1_VOLUME - support.SQUARE_WINDOW_CUT1_VOLUME == (
        pytest.approx(band + wall + taper_cut1)
    )
    assert support.WINDOW_CUT2_VOLUME - support.SQUARE_WINDOW_CUT2_VOLUME == (
        pytest.approx(2.0 * band + wall + taper_cut2)
    )
    spandrel = 1.0 - math.pi / 4.0
    corner = 4.0 * spandrel * support.FILLET_R**2 * 2.0 * growth
    pocket = 8.0 * spandrel * support.POCKET_FILLET_R**2 * growth
    # The eight pocket-corner edges shorten by the delta per high/low pair.
    pocket_taper = -4.0 * spandrel * support.POCKET_FILLET_R**2 * delta
    assert (
        support.CORNER_FILLET_VOLUME - support.SQUARE_CORNER_FILLET_VOLUME
    ) == pytest.approx(2.0 * band + corner + wall + taper_cut2)
    assert (
        support.POCKET_FILLET_VOLUME - support.SQUARE_POCKET_FILLET_VOLUME
    ) == pytest.approx(2.0 * band + corner - pocket + wall + taper_cut2 + pocket_taper)
    removal = support.FOOT_HOLED_VOLUME - support.RIM_CHAMFER_VOLUME
    # The source's measured 1.27-leg removal, scaled by the leg squared, less
    # the two end faces' top edges the feature skips (#1038): each a
    # leg-squared-over-two prism the top flat's width long.
    top_edges = 2 * (2.0 * section.NARROW) * support.CHAMFER**2 / 2.0
    assert removal == pytest.approx(
        support.SQUARE_RIM_CHAMFER_REMOVAL * (support.CHAMFER / 1.27) ** 2 - top_edges
    )
    assert support.BRACKET_SEATS_VOLUME < support.RIM_CHAMFER_VOLUME


def _floor_spandrel_quarter_turn_volume(r: float, wall_radius: float) -> float:
    """The R ``r`` floor spandrel swept a quarter turn round a corner whose
    wall has radius ``wall_radius``, by midpoint integration (u from the
    wall toward the corner's axis, v up from the floor)."""
    steps = 400
    cell = r / steps
    total = 0.0
    for i in range(steps):
        u = (i + 0.5) * cell
        for j in range(steps):
            v = (j + 0.5) * cell
            if (u - r) ** 2 + (v - r) ** 2 >= r**2:
                total += math.pi / 2.0 * (wall_radius - u) * cell * cell
    return total


def test_pocket_floor_fillet_sits_under_the_title_block_and_its_volume_closed_form() -> (
    None
):
    """The r7 review's unstated pocket floor corner is the title block's
    INSIDE CORNERS R.040 MAX; a local R0.8 MAX named no mate or function
    (ENFORCE review 2026-10-23), so the sheet prints none and the model's
    R0.8 lies within the ceiling."""
    from _printed_tolerance import inside_corner_radius_mm

    assert support.POCKET_FLOOR_R == 0.8
    assert support.POCKET_FLOOR_R <= inside_corner_radius_mm(unit=placement.UNIT)
    assert "PocketFloorFillet" not in support.DRAWING_DIMENSIONS
    assert "PocketFloorFillet" not in support.DRAWING_PRECISION
    # One edge per pocket, on the top rail's floor corner, +Z first.
    assert support.POCKET_FLOOR_FILLET_EDGES == [
        [0.0, support.BIG, support.WEB],
        [0.0, support.BIG, -support.WEB],
    ]
    r = support.POCKET_FLOOR_R
    straight = 4.0 * (2.0 * support.BIG - 2.0 * support.POCKET_FILLET_R)
    per_pocket = (1.0 - math.pi / 4.0) * r**2 * straight + 4.0 * (
        _floor_spandrel_quarter_turn_volume(r, support.POCKET_FILLET_R)
    )
    assert support.POCKET_FLOOR_FILLET_GROWTH == pytest.approx(
        2.0 * per_pocket, rel=1e-4
    )
    assert (
        support.POCKET_FLOOR_FILLET_VOLUME - support.POCKET_FILLET_VOLUME
        == pytest.approx(support.POCKET_FLOOR_FILLET_GROWTH)
    )
    holes = (
        len(support.HOLES)
        * math.pi
        / 4.0
        * support.HOLE_DIA**2
        * (support.FOOT_THICKNESS)
    )
    assert support.FOOT_HOLED_VOLUME == pytest.approx(
        support.POCKET_FLOOR_FILLET_VOLUME - holes
    )
    # The fillet stands outside the web, clear of the seats' threads inside
    # it and of the clearance holes in the foot.
    floor_reach = support.WEB + r
    assert seats.SCREW_MAJOR_DIA / 2.0 < support.WEB
    assert min(abs(z) for _, z in support.HOLES) - support.HOLE_DIA / 2.0 > (
        floor_reach + 5.0
    )


def test_bracket_seats_sit_under_the_bracket_holes() -> None:
    import ch_pivot_bracket_sides as sides

    assert seats.SEAT_SPEC.kind == "tapped_bottoming"
    assert seats.SEAT_SPEC.size == seats.SCREW_THREAD == "#8-32"
    assert (
        seats.SEAT_SPEC.depth_mm == seats.SEAT_DRILL_DEPTH == pytest.approx(0.59 * 25.4)
    )
    assert seats.SEAT_SPEC.overrides_mm == {"ThreadDepth": seats.SEAT_THREAD_DEPTH}
    assert seats.SEAT_THREAD_DEPTH == pytest.approx(0.46 * 25.4)
    assert len(seats.SEAT_MACHINE_XZ) == len(sides.SIDES) == 2
    assert [z for _, z in seats.SEAT_MACHINE_XZ] == pytest.approx(
        [
            sides.MOUNT_Z[name] + sides.OUTBOARD_SIGN[name] * sides.HOLE_Z
            for name in sides.SIDES
        ]
    )
    assert {x for x, _ in seats.SEAT_MACHINE_XZ} == {placement.SUPPORT_WORLD_X}
    assert [p[0] for p in support.SEAT_POINTS] == pytest.approx(
        [placement.SUPPORT_WORLD_Z - z for _, z in seats.SEAT_MACHINE_XZ]
    )
    assert all(p[1:] == [support.HALF_Y, 0.0] for p in support.SEAT_POINTS)


def test_bracket_screw_stack_holds_at_the_printed_worst_case() -> None:
    from _inch_wall_limits import WALL_TARGET_MM
    from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm

    # MHA-CH-VN-57 #8-32 x 5/8 through MHA-CH-08's foot at its band.
    assert seats.SCREW_REACH_MIN == pytest.approx(15.875 - 0.76 - seats.FOOT_H_RANGE[1])
    assert seats.SCREW_REACH_MAX == pytest.approx(15.875 - seats.FOOT_H_RANGE[0])
    assert seats.ENGAGEMENT_MIN >= 1.5 * seats.SCREW_MAJOR_DIA
    # The seat depths print .XX on the inch sheet.
    assert drawing.SEAT_CALLOUT_PRECISION["hw-tapdrldepth"] == 2
    assert drawing.SEAT_CALLOUT_PRECISION["hw-threaddepth"] == 2
    depth = printed_band_mm(2, unit=placement.UNIT)
    edge = edge_break_chamfer_mm(unit=placement.UNIT)
    assert seats.SEAT_THREAD_DEPTH - depth >= seats.SCREW_REACH_MAX + edge
    assert (
        seats.SEAT_DRILL_DEPTH - depth
        >= seats.SEAT_THREAD_DEPTH + depth + 2 * 25.4 / 32
    )
    assert seats.WEB_WALL_MIN >= WALL_TARGET_MM
    assert min(seats.END_WALL_MIN) >= WALL_TARGET_MM


def _point_to_segment(point, start, end) -> float:
    (px, py), (ax, ay), (bx, by) = point, start, end
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _end_wall_past_top_edge_break(end_wall: float, leg: float) -> float:
    """The bracket seat's thread to the end face, with that face's top edge
    broken at a 45° leg. In the end-face section (x in from the end face, y
    down from the top) the thread's crest runs down x = end_wall from its
    mouth break; the iron's boundary is the bounded break face (leg, 0) to
    (0, leg), then the end face below it. Both are convex and apart, so the
    nearest pair includes the crest's top point or a face endpoint."""
    mouth = seats.EDGE_BREAK
    crest = (end_wall, mouth)
    break_face = ((leg, 0.0), (0.0, leg))
    to_corner_below = end_wall if leg >= mouth else math.hypot(end_wall, mouth - leg)
    return min(
        end_wall,  # the end face below the break
        _point_to_segment(crest, *break_face),
        math.hypot(end_wall - leg, mouth),  # the break's top edge
        to_corner_below,
    )


def test_the_end_faces_top_edges_skip_the_rim_chamfer_to_keep_the_seat_end_wall() -> (
    None
):
    """#1038 review: the .06 leg on an end face's top edge left the bracket
    seat's thread about 1.50 mm from the break's top edge at the worst case
    (under the .060 floor). Neither top edge is chamfered, so the edge keeps
    the title block's break and the seats keep 2.51 (S) and 3.92 (N) since
    the .50 hold-down station (#2563) moved each seat .010 outboard."""
    from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
    from _printed_tolerance import edge_break_chamfer_mm

    half = support.BOSS_DEPTH / 2.0
    for sign in (1.0, -1.0):
        assert [sign * half, support.HALF_Y, 0.0] not in support.CHAMFER_EDGES
        assert [sign * half, 0.0, 0.0] not in support.CHAMFER_FACES
    title_break = edge_break_chamfer_mm(unit=placement.UNIT)
    walls = [_end_wall_past_top_edge_break(w, title_break) for w in seats.END_WALL_MIN]
    assert walls == pytest.approx([2.506, 3.916], abs=0.001)
    assert min(walls) >= WALL_TARGET_MM
    south = min(seats.END_WALL_MIN)
    chamfered = _end_wall_past_top_edge_break(south, support.CHAMFER)
    assert chamfered == pytest.approx(1.249, abs=0.001)
    assert chamfered < WALL_FLOOR_MM


def test_rim_chamfer_size_lands_on_an_outside_corner_of_the_front_view() -> None:
    """r7 machinist review (clarity): the size sat on a cavity rim inside the
    section. A chamfer's size lands on its first selected edge and prints
    only where that edge is seen end-on, so the +X end face's foot edge goes
    first and the front view, which sees it end-on at its bottom-right
    corner, carries the size. The section keeps its targeted import."""

    first, second = support.CHAMFER_EDGES[:2]
    assert first == [support.BOSS_DEPTH / 2.0, -support.HALF_Y, 0.0]
    assert second == [-support.BOSS_DEPTH / 2.0, -support.HALF_Y, 0.0]
    assert "RimChamferSize" in drawing.FRONT_KEEP
    assert "RimChamferSize" not in drawing.RIGHT_KEEP
    scale = drawing.VIEW_SCALE / 1000
    corner = (
        drawing.FRONT_CENTER[0] + support.BOSS_DEPTH / 2.0 * scale,
        drawing.FRONT_CENTER[1] - support.HALF_Y * scale,
    )
    line_x, line_y = drawing.FRONT_KEEP["RimChamferSize"]
    assert 0.0 < line_x - corner[0] <= 0.003
    assert 0.0 < corner[1] - line_y <= 0.003
    # The text's leader stays short: the text is in the lane just up-right.
    text_x, text_y = drawing.RIM_CHAMFER_TEXT_XY
    assert math.dist((text_x, text_y), (line_x, line_y)) < 0.060

    assert drawing.DRAWING_DIMENSIONS is support.DRAWING_DIMENSIONS


def test_precision_reaches_every_dimension_exactly_once() -> None:
    """r743-rocker-fix (53cb9ad5b) failed "dimension precision not applied:
    ['RailDepth']": each bulk call covers only the dimensions its curate pass
    kept, and the sheet-made ones (web, foot) set their own after the import.
    Every DIMENSION_PRECISION name goes through exactly one of them, and every
    part-owned name is read back by exactly one curate pass."""

    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    bulk = drawing.imported_precision(kept)
    assert set(bulk) == kept & set(drawing.DIMENSION_PRECISION)
    # VIEW B shows only part-owned places: the sheet sets none there.
    assert drawing.imported_precision(drawing.VIEW_B_KEEP) == {}
    part = set(drawing.PART_PRECISION)
    assert not part & set(drawing.DIMENSION_PRECISION)
    read_main, read_view_b = part & kept, part & set(drawing.VIEW_B_KEEP)
    assert not read_main & read_view_b
    assert read_main | read_view_b == part


def test_seat_stations_print_as_ref_from_the_real_end_faces() -> None:
    """r7 machinist review (blocker): the seats printed with no location and
    read as crowding the end wall. Main's r8 ruling: REF stations from the
    end faces in VIEW B, the transfer staying the method."""
    lines = {
        row.dimension: (row.end_x, row.seat_x) for row in support.SEAT_STATION_LINES
    }
    assert lines == {
        "SeatEastStation": (support.BOSS_DEPTH / 2.0, max(seats.SEAT_LOCAL_X)),
        "SeatWestStation": (-support.BOSS_DEPTH / 2.0, min(seats.SEAT_LOCAL_X)),
    }
    printed = {
        name: f"{abs(end - seat):.{drawing.PART_PRECISION[name]}f}"
        for name, (end, seat) in lines.items()
    }
    places = drawing.PART_PRECISION["SeatEastStation"]
    assert printed == {
        "SeatEastStation": f"{placement.SUPPORT_HALF_MACHINE_Z - max(seats.SEAT_LOCAL_X):.{places}f}",
        "SeatWestStation": f"{placement.SUPPORT_HALF_MACHINE_Z + min(seats.SEAT_LOCAL_X):.{places}f}",
    }
    assert support.REFERENCE_SKETCHES[0] == "SeatStationReference"
    assert support.DRAWING_DIMENSIONS["SeatStationReference"] == set(lines)
    assert set(drawing.VIEW_B_KEEP) == set(lines)
    # The transfer instruction stays on the seat callout.
    assert "AT ASSEMBLY;" in drawing.SEAT_CALLOUT_PROCESS


def _evaluate_equation(expression: str, values: dict[str, float]) -> float:
    """An equation-manager expression of quoted names and arithmetic, in mm."""
    numeric = re.sub(r'"(\w+)"', lambda match: repr(values[match[1]]), expression)
    return float(eval(numeric, {"__builtins__": {}}))


def _record_location_sketch(monkeypatch: pytest.MonkeyPatch, sketch_builder) -> tuple:
    """Run one location-reference sketch offline. Returns its chords (name ->
    (start, end) in sketch coordinates), its dimensions as created (name ->
    (ref1, ref2, kind, value); an origin anchor is two, ("origin", ref, axis,
    value)) and its drive jobs."""
    import _sketch

    emitted: list[tuple] = []
    names: list[str] = []
    lines: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    monkeypatch.setattr(_sketch, "_feature_by_name", lambda _adapter, name: name)
    monkeypatch.setattr(
        _sketch, "_display_dimensions", lambda *_: [None] * len(emitted)
    )
    monkeypatch.setattr(
        _sketch, "_rename_dimensions", lambda _dims, _feature, new: names.extend(new)
    )
    monkeypatch.setattr(support, "_early_bound", lambda obj, _interface: obj)
    for name in ("set_sketch_direct_db", "name_last_feature"):
        monkeypatch.setattr(support, name, lambda *_: None)

    def dimension(_adapter, ref1, ref2, kind, value, _label) -> None:
        emitted.append((ref1, ref2, kind, value))

    def anchor(_adapter, ref, x, y, _label) -> None:
        assert y != 0.0
        if x == 0.0:  # on the vertical axis: a relation and one dimension
            emitted.append(("origin", ref, "y", y))
            return
        emitted.extend([("origin", ref, "x", x), ("origin", ref, "y", y)])

    def nothing(*_args: object) -> None:
        return None

    monkeypatch.setattr(support, "dimension_between", dimension)
    monkeypatch.setattr(support, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(support, "ensure_fully_defined", nothing)
    ok = SimpleNamespace(is_success=True, data=None)
    relations: dict[str, str] = {}
    point_relations: list[tuple[str, str]] = []

    class Adapter:
        _sketch_entities = defaultdict(
            lambda: SimpleNamespace(ConstructionGeometry=False)
        )

        def create_sketch(self, _plane: str) -> SimpleNamespace:
            return ok

        def add_line(self, x0, y0, x1, y1) -> SimpleNamespace:
            line = f"L{len(lines)}"
            lines[line] = ((x0, y0), (x1, y1))
            return SimpleNamespace(is_success=True, data=line)

        def add_sketch_constraint(self, line, other, relation) -> SimpleNamespace:
            if other is not None:
                assert relation == "horizontal_points"
                point_relations.append((line, other))
                return ok
            relations[line] = relation
            return ok

        def exit_sketch(self) -> SimpleNamespace:
            return ok

    adapter = Adapter()
    jobs = dict(sketch_builder(adapter))
    assert all(adapter._sketch_entities[line].ConstructionGeometry for line in lines)
    dims = dict(zip(names, emitted, strict=True))
    chords = {}
    for name, (ref1, ref2, kind, value) in dims.items():
        line = ref1.split(".")[0]
        if (ref1, ref2) == (f"{line}.start", f"{line}.end"):
            assert kind == f"{relations[line]}_distance"
            chords[name] = lines[line]

    def point(ref: str) -> tuple[float, float]:
        line, end = ref.split(".")
        return lines[line][0 if end == "start" else 1]

    # Every dimension holds the geometry as drawn.
    for ref1, ref2, kind, value in dims.values():
        if ref1 == "origin":
            assert point(ref2)[kind == "y"] == pytest.approx(value)
            continue
        a = point(ref1)
        b = (0.0, 0.0) if ref2 == "origin" else point(ref2)
        axis = 0 if kind == "horizontal_distance" else 1
        assert abs(a[axis] - b[axis]) == pytest.approx(value)
    for ref1, ref2 in point_relations:
        assert point(ref1)[1] == pytest.approx(point(ref2)[1])
    return chords, dims, jobs


def _evaluate_drive(expression: str, values: dict[str, float]) -> float:
    return _evaluate_equation(re.sub(r"(?<=\d)mm\b", "", expression), values)


def test_cavity_pocket_and_web_locations_run_from_real_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR #1469 r4 machinist review (blockers): the 127.0 SQ cavity and the
    165.1 SQ pockets printed with no location, and section A-A placed neither
    the 9.53 web nor the top face across the 63.5 base. Owner ruling
    (rule 10): dimension from a real feature. Each location spans two
    construction chords lying on edges their view draws, prints its value at
    the part's places, and its drive keeps it on its features for any edit."""
    front_chords, front_dims, front_jobs = _record_location_sketch(
        monkeypatch, support._cavity_location_reference
    )
    right_chords, right_dims, right_jobs = _record_location_sketch(
        monkeypatch, support._web_location_reference
    )
    end_x, top_y = -support.BOSS_DEPTH / 2.0, support.HALF_Y
    corner = support.CHAMFER
    cavity_run = support.CAV - support.FILLET_R
    pocket_run = support.BIG - support.POCKET_FILLET_R
    # Front plane (X, Y): on the end face, the top and bottom faces and the
    # walls' straight runs, clear of every chamfer and corner radius.
    on_line = {
        "EndChord": (0, end_x, top_y - corner),
        "TopChord": (1, top_y, support.BOSS_DEPTH / 2.0 - corner),
        "BottomChord": (1, -top_y, support.BOSS_DEPTH / 2.0 - corner),
        "CavitySideChord": (0, -support.CAV, cavity_run),
        "PocketSideChord": (0, -support.BIG, pocket_run),
        "CavityTopChord": (1, support.CAV, cavity_run),
        "PocketBottomChord": (1, -support.BIG, pocket_run),
    }
    assert set(front_chords) == set(on_line)
    for name, (axis, at, run) in on_line.items():
        for chord_point in front_chords[name]:
            assert chord_point[axis] == pytest.approx(at)
            assert abs(chord_point[1 - axis]) <= run
    # Right plane (-Z, Y): along the base from its -Z edge, and up the web's
    # -Z face between the pocket floor's fillet and the cavity's rim chamfer,
    # clear of where the drawing picks the web for its 12.70.
    assert set(right_chords) == {
        "BaseChord",
        "WebChord",
        "TopFlatMinusZStationFaceChord",
        "TopFlatMinusZStationChord",
        "TopFlatPlusZStationFaceChord",
        "TopFlatPlusZStationChord",
    }
    base, web = right_chords["BaseChord"], right_chords["WebChord"]
    assert base[0] == (support.WIDE, -support.HALF_Y)
    assert base[1][1] == -support.HALF_Y and base[1][0] < support.WIDE
    web_pick_y = -(support.BIG + support.CAV) / 2.0
    for z, y in web:
        assert z == support.WEB
        assert -(support.BIG - support.POCKET_FLOOR_R) < y
        assert y < -(support.CAV + support.CHAMFER)
        assert abs(y - web_pick_y) > 2.0
    # Owner Q13d: each flat edge off its nearer web face, a real surface. The
    # face chord runs down its side's web face from under the upper pocket
    # floor's fillet, above the cavity's rim chamfer; the flat chord in along
    # the top face from its edge, short of the web face's line.
    for name, row in support.TOP_FLAT_STATIONS.items():
        assert abs(row.face_u) == support.WEB and abs(row.edge_u) == support.NARROW
        assert row.face_u * row.edge_u > 0.0
        for z, y in right_chords[f"{name}FaceChord"]:
            assert z == row.face_u
            assert support.CAV + support.CHAMFER < y
            assert y < support.BIG - support.POCKET_FLOOR_R
        start, end = right_chords[f"{name}Chord"]
        assert start == (row.edge_u, support.HALF_Y) and end[1] == support.HALF_Y
        assert support.WEB < abs(end[0]) < abs(start[0])
    # Each location runs from the face chord's start to its feature chord's.
    spans = {
        "CavityEndStation": (front_dims, "EndChord", "CavitySideChord"),
        "PocketEndStation": (front_dims, "EndChord", "PocketSideChord"),
        "CavityTopStation": (front_dims, "TopChord", "CavityTopChord"),
        # r6 review: the pockets' vertical location, off the mounting face.
        "PocketBottomStation": (front_dims, "BottomChord", "PocketBottomChord"),
        "WebFaceStation": (right_dims, "BaseChord", "WebChord"),
        "TopFlatMinusZStation": (
            right_dims,
            "TopFlatMinusZStationFaceChord",
            "TopFlatMinusZStationChord",
        ),
        "TopFlatPlusZStation": (
            right_dims,
            "TopFlatPlusZStationFaceChord",
            "TopFlatPlusZStationChord",
        ),
    }
    for name, (dims, face, feature) in spans.items():
        ref1, ref2, _kind, _value = dims[name]
        # A chord's length dimension runs from its start.
        assert (ref1, ref2) == (dims[face][0], dims[feature][0])
    # Every location lands on its printed inch grid, so no value sits near a
    # rounding tie. One flat edge prints (its BOTH SIDES covers the other, r6
    # review); the -Z one stays unprinted.
    assert "TopFlatMinusZStation" not in drawing.PART_PRECISION
    printed = {
        name: str(
            (Decimal(dims[name][3]) / Decimal("25.4")).quantize(
                Decimal(1).scaleb(-drawing.PART_PRECISION[name])
            )
        )
        for name, (dims, _face, _feature) in spans.items()
        if name in drawing.PART_PRECISION
    }
    assert printed == {
        "CavityEndStation": "1.28",
        "PocketEndStation": "0.53",
        "CavityTopStation": "1.00",
        "PocketBottomStation": "0.25",
        "WebFaceStation": "1.00",
        "TopFlatPlusZStation": "0.08",
    }
    for name in printed:
        value_in = abs(spans[name][0][name][3]) / 25.4
        places = drawing.PART_PRECISION[name]
        assert value_in == pytest.approx(round(value_in, places), abs=1e-9)

    nominal = {
        "WallWidth": support.BOSS_DEPTH,
        "HalfHeight": support.HALF_Y,
        "CavHalf": support.CAV,
        "WindowOuter": support.BIG,
        "FootHalf": support.WIDE,
        "TopHalf": support.NARROW,
    }
    jobs = {
        **{name.split("@")[0]: drive for name, drive in front_jobs.items()},
        **{name.split("@")[0]: drive for name, drive in right_jobs.items()},
    }
    assert set(front_jobs) == {
        f"{name}@CavityLocationReference"
        for name in ("EndChordX", "TopChordY", "BottomChordY", *list(spans)[:4])
    }
    assert set(right_jobs) == {
        f"{name}@WebLocationReference"
        for name in (
            "BaseChordZ",
            "BaseChordY",
            "WebFaceStation",
            "TopFlatMinusZStationChordY",
            "TopFlatMinusZStation",
            "TopFlatPlusZStationChordY",
            "TopFlatPlusZStation",
        )
    }
    for edit in (
        {},
        {"WallWidth": 180.8},
        {"HalfHeight": 90.0, "CavHalf": 60.0},
        {"WindowOuter": 80.0},
        {"FootHalf": 33.0},
        {"TopHalf": 9.0},
    ):
        values = {**nominal, **edit}
        expected = {
            "EndChordX": values["WallWidth"] / 2.0,
            "TopChordY": values["HalfHeight"],
            "CavityEndStation": values["WallWidth"] / 2.0 - values["CavHalf"],
            "PocketEndStation": values["WallWidth"] / 2.0 - values["WindowOuter"],
            "CavityTopStation": values["HalfHeight"] - values["CavHalf"],
            "BottomChordY": values["HalfHeight"],
            "PocketBottomStation": values["HalfHeight"] - values["WindowOuter"],
            "BaseChordZ": values["FootHalf"],
            "BaseChordY": values["HalfHeight"],
            # The window cuts start WEB off the centre plane: no global.
            "WebFaceStation": values["FootHalf"] - support.WEB,
            "TopFlatMinusZStationChordY": values["HalfHeight"],
            "TopFlatPlusZStationChordY": values["HalfHeight"],
            # Each flat edge off its web face, WEB off the centre plane.
            "TopFlatMinusZStation": values["TopHalf"] - support.WEB,
            "TopFlatPlusZStation": values["TopHalf"] - support.WEB,
        }
        assert {
            name: _evaluate_drive(drive, values) for name, drive in jobs.items()
        } == pytest.approx(expected)
        if not edit:
            # Unedited, every drive holds the value the sketch was drawn at.
            for name, value in expected.items():
                dims = front_dims if name in front_dims else right_dims
                assert abs(dims[name][3]) == pytest.approx(value)


def test_seat_station_texts_stand_above_view_b_outboard_of_its_ends() -> None:
    scale = drawing.VIEW_SCALE / 1000
    centre_x, centre_y = drawing.VIEW_B_CENTER
    fence_top = centre_y + drawing.VIEW_B_CROP_HALF_Z_MM * scale
    end_run = support.BOSS_DEPTH / 2.0 * scale
    east = _text_box(
        _inch_ref((support.BOSS_DEPTH / 2.0 - max(seats.SEAT_LOCAL_X)) / 25.4),
        drawing.VIEW_B_REF_TEXT_XY["SeatEastStation"],
    )
    west = _text_box(
        _inch_ref((support.BOSS_DEPTH / 2.0 + min(seats.SEAT_LOCAL_X)) / 25.4),
        drawing.VIEW_B_REF_TEXT_XY["SeatWestStation"],
    )
    # Each text rides a leader, above the tops of its extension lines.
    assert set(drawing.VIEW_B_REF_TEXT_XY) == set(drawing.VIEW_B_KEEP)
    line_y = fence_top + drawing.VIEW_B_REF_RISE
    for box in (east, west):
        assert box[1] > line_y + 0.002
    assert drawing.VIEW_B_KEEP["SeatEastStation"][0] > centre_x + end_run
    assert drawing.VIEW_B_KEEP["SeatWestStation"][0] < centre_x - end_run
    # East: left of the hole table. West: right of the front view's pocket
    # width extension line and clear of the stacked width texts.
    assert east[2] < drawing.HOLE_TABLE_ANCHOR[0] - 0.002
    pocket_x = drawing.FRONT_CENTER[0] + support.BIG * scale
    assert west[0] > pocket_x + 0.003
    pocket = _text_box("6.50\nSQ POCKET BOTH SIDES", drawing.FRONT_KEEP["WinWidth"])
    assert _boxes_clear(west, pocket, 0.003)


def _inch_ref(value_in: float) -> str:
    """A .XXX inch REF as the sheet prints it: no leading zero."""
    return f"({value_in:.3f})".replace("(0.", "(.")


FLAT_PLUS_TEXT = ".08\n" + drawing.DIMENSION_CALLOUTS["TopFlatPlusZStation"]
# The sheet's left inner border (r7 layout audit: the 6.35's block at 11.1 mm
# crossed it by 1.58 mm).
SHEET_LEFT_INNER_BORDER_X = 0.0127


def test_section_locations_stand_off_the_section_and_its_texts() -> None:
    """One top-flat edge prints above the section, its text outboard of the
    +Z edge and its BOTH SIDES covering the other (owner Q13d, r6 review);
    WebFaceStation's row stands between the base and the 63.5, whose text
    sits right of the web face's extension line; the front view's locations
    clear its other texts."""
    scale = drawing.VIEW_SCALE / 1000
    centre_x, centre_y = drawing.RIGHT_CENTER
    top_right = centre_x + support.NARROW * scale
    base_left = centre_x - support.WIDE * scale
    web_left = centre_x - support.WEB * scale
    section_top = centre_y + support.HALF_Y * scale
    top_span = _text_box(FLAT_PLUS_TEXT, drawing.RIGHT_KEEP["TopFlatPlusZStation"])
    assert "TopFlatMinusZStation" not in drawing.RIGHT_KEEP
    assert top_span[0] > top_right + 0.002
    assert top_span[1] > section_top + 0.002
    web_face = _text_box("1.00", drawing.RIGHT_KEEP["WebFaceStation"])
    foot = _text_box("2.50", drawing.RIGHT_KEEP["FootSpan"])
    assert web_face[3] < centre_y - support.HALF_Y * scale
    assert foot[0] > web_left + 0.003
    assert base_left < drawing.RIGHT_KEEP["WebFaceStation"][0] < web_left
    assert _boxes_clear(web_face, foot, 0.003)
    # r10 review: one mm lower than r8's row, the 63.5's left extension line
    # overshot its line into the SECTION A-A label's E.
    assert drawing.RIGHT_KEEP["FootSpan"][1] >= 0.133
    front_bottom = drawing.FRONT_CENTER[1] - support.HALF_Y * scale
    front_left = drawing.FRONT_CENTER[0] - support.BOSS_DEPTH / 2.0 * scale
    front_top = drawing.FRONT_CENTER[1] + support.HALF_Y * scale
    pocket = _text_box(".53\nBOTH SIDES", drawing.FRONT_KEEP["PocketEndStation"])
    cavity = _text_box("1.28", drawing.FRONT_KEEP["CavityEndStation"])
    cavity_top = _text_box("1.00", drawing.FRONT_KEEP["CavityTopStation"])
    assert pocket[2] < front_left and cavity_top[2] < front_left
    # r6 review: the pockets' 6.35 up from the mounting face, left of the
    # view under the face's extension line, clear of the R6.35's text and
    # of the 165.1's left extension line (the pocket's -X wall). Its text
    # stands outside the span, so SolidWorks sets the block LEFT of the
    # dimension line, its right edge on it (r7 render: at x 0.036 BOTH
    # SIDES ran 11.1..35.7 mm, over the left inner border at 12.7 mm).
    line_x, text_y = drawing.FRONT_KEEP["PocketBottomStation"]
    centred = _text_box(".25\nBOTH SIDES", (line_x, text_y))
    half_w = (centred[2] - centred[0]) / 2.0
    pocket_bottom = _text_box(".25\nBOTH SIDES", (line_x - half_w, text_y))
    assert pocket_bottom[2] < drawing.FRONT_CENTER[0] - support.BIG * scale - 0.003
    assert line_x < front_left - 0.003
    assert pocket_bottom[3] < front_bottom - 0.003
    assert pocket_bottom[0] > SHEET_LEFT_INNER_BORDER_X + 0.003
    # Clear of the 25.4's dimension line and of its outside arrow tail above
    # the top face (r9 review: the tail struck BOTH SIDES): on r9's render
    # the tail reached 5.7 mm above the face.
    assert pocket[2] < drawing.FRONT_KEEP["CavityTopStation"][0] - 0.001
    assert pocket[1] > front_top + 0.008
    assert front_top < cavity[1] and cavity[3] < DEPTH_DIM_LINE_Y - 0.002
    # The 26.7 stands inside its span, the end face to the cavity wall.
    assert front_left < cavity[0] and cavity[2] < drawing.FRONT_CENTER[0] - (
        support.CAV * scale
    )
    for a, b in ((pocket, cavity), (pocket, cavity_top), (cavity, cavity_top)):
        assert _boxes_clear(a, b, 0.002)
    for other in (
        _text_box("7.56", drawing.FRONT_KEEP["Depth"]),
        _text_box("R.25\n8X", drawing.FRONT_KEEP["PocketRadius"]),
        _text_box("6.50\nSQ POCKET BOTH SIDES", drawing.FRONT_KEEP["WinWidth"]),
    ):
        for box in (pocket, cavity, cavity_top, pocket_bottom):
            assert _boxes_clear(box, other, 0.002)


# Sheet-default note text as rendered by r743-rocker-fix3 (leaf
# 20260926T112244Z-1-a884759d): "TRANSFER FROM MHA-CH-008" spanned 57.6 mm for 21
# characters and five lines stepped 4.45 mm. add_note does not apply a height,
# so every note on this sheet renders at this size.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045


def _text_box(text: str, center: tuple[float, float]) -> tuple[float, ...]:
    """(left, bottom, right, top) of a note or dimension text centred on ``center``.

    A decimal point renders about half a digit wide (inch values lead with it)."""
    lines = text.splitlines()
    half_w = (
        max(sum(0.5 if char == "." else 1.0 for char in line) for line in lines)
        * NOTE_CHAR_WIDTH
        / 2.0
    )
    half_h = len(lines) * NOTE_LINE_PITCH / 2.0
    return (
        center[0] - half_w,
        center[1] - half_h,
        center[0] + half_w,
        center[1] + half_h,
    )


def _boxes_clear(a: tuple[float, ...], b: tuple[float, ...], gap: float) -> bool:
    return (
        a[2] + gap <= b[0]
        or b[2] + gap <= a[0]
        or a[3] + gap <= b[1]
        or b[3] + gap <= a[1]
    )


RIM_CHAMFER_TEXT = ".06\n" + drawing.DIMENSION_CALLOUTS["RimChamferSize"].strip().replace(
    "<MOD-DEG>", "°"
)


def _rim_chamfer_box() -> tuple[float, ...]:
    """The chamfer's text box: on its OffsetText leader the text centres on
    RIM_CHAMFER_TEXT_XY."""
    return _text_box(RIM_CHAMFER_TEXT, drawing.RIM_CHAMFER_TEXT_XY)


def test_rim_chamfer_feature_breaks_every_edge_its_note_names() -> None:
    # The callout links the numbered note that names the edges.
    assert drawing.DIMENSION_CALLOUTS["RimChamferSize"].endswith(
        f"SEE NOTE {drawing.CHAMFER_NOTE_NUMBER}"
    )
    assert drawing.CHAMFER_NOTE.startswith(f"{drawing.CHAMFER_NOTE_NUMBER}. ")
    # The faces whose every edge the feature breaks: both slant faces (the
    # pocket rims and the outside edges they share) and one cavity fillet
    # face. Each end face is selected as its foot edge, the one edge the
    # slant faces do not own that the feature breaks (the +X one first, for
    # the size); the top edges stay off it, as the note's exception says.
    assert len(support.CHAMFER_FACES) == 3
    assert all(
        abs(face[0]) != support.BOSS_DEPTH / 2.0 for face in support.CHAMFER_FACES
    )
    end_edges, rim_edges = support.CHAMFER_EDGES[:2], support.CHAMFER_EDGES[2:]
    assert {(edge[0], edge[1]) for edge in end_edges} == {
        (support.BOSS_DEPTH / 2.0, -support.HALF_Y),
        (-support.BOSS_DEPTH / 2.0, -support.HALF_Y),
    }
    assert "EXCEPT THE TOP EDGES OF BOTH END FACES" in drawing.CHAMFER_NOTE
    assert len(rim_edges) == 12
    assert {abs(edge[2]) for edge in rim_edges} == {support.WEB}


def test_rim_chamfer_callout_sits_between_the_front_view_and_the_section() -> None:
    scale = drawing.VIEW_SCALE / 1000
    chamfer = _rim_chamfer_box()
    front_right = drawing.FRONT_CENTER[0] + support.BOSS_DEPTH / 2 * scale
    assert chamfer[0] > front_right + 0.003
    # The caption's rows stay clear of the section's slant wall...
    for y in (chamfer[1], chamfer[3]):
        local_y = (y - drawing.RIGHT_CENTER[1]) / scale
        wall_x = drawing.RIGHT_CENTER[0] - support._wall_half_z_at(local_y) * scale
        assert chamfer[2] < wall_x - 0.002
    # ...and of the foot's 6.35 text, which hangs left of its anchor.
    foot = _text_box(".25", drawing.FOOT_TEXT_XY)
    foot = (
        foot[0] - (foot[2] - foot[0]) / 2.0,
        foot[1],
        drawing.FOOT_TEXT_XY[0],
        foot[3],
    )
    assert _boxes_clear(chamfer, foot, 0.003)


def test_web_thickness_text_clears_the_wall_and_the_height_dimension() -> None:
    """r743-rocker-fix3 printed the section's 6.35 across the slanted wall
    line; the text must sit between that wall and the 177.8 dimension line."""
    web = _text_box(".50", drawing.WEB_TEXT_XY)
    scale = drawing.VIEW_SCALE / 1000
    lowest_local_y = (web[1] - drawing.RIGHT_CENTER[1]) / scale
    wall_x = drawing.RIGHT_CENTER[0] + support._wall_half_z_at(lowest_local_y) * scale
    assert web[0] > wall_x + 0.002
    assert web[2] < drawing.RIGHT_KEEP["WallHeight"][0] - 0.002


def test_foot_thickness_text_sits_above_its_extension_lines() -> None:
    """The foot's 6.35 spans 3.2 mm of sheet. At y 0.142 its text sat between
    the extension lines with the dimension line through it (fix4 render), so
    it prints above the top extension line, left of the slanted wall and
    right of the front view."""
    scale = drawing.VIEW_SCALE / 1000
    foot = _text_box(".25", drawing.FOOT_TEXT_XY)
    foot_top_y = drawing.RIGHT_CENTER[1] - support.BIG * scale
    assert foot[1] > foot_top_y + 0.002
    lowest_local_y = (foot[1] - drawing.RIGHT_CENTER[1]) / scale
    wall_x = drawing.RIGHT_CENTER[0] - support._wall_half_z_at(lowest_local_y) * scale
    assert foot[2] < wall_x - 0.002
    front_right = drawing.FRONT_CENTER[0] + support.BOSS_DEPTH / 2 * scale
    assert foot[0] > front_right + 0.003


def test_stacked_pocket_widths_keep_separate_bands() -> None:
    """Each stacked width prints its text just above its own dimension line.
    At WinWidth y 0.118 the 127.0 line ran through "165.1" (Main's fix3 eye
    pass), so the lower text clears the upper dimension by a full line pitch,
    and its own line still stays above the bottom view."""
    cavity = _text_box("5.00\nSQ CAVITY THRU", drawing.FRONT_KEEP["CavWidth"])
    pocket = _text_box("6.50\nSQ POCKET BOTH SIDES", drawing.FRONT_KEEP["WinWidth"])
    assert pocket[3] + NOTE_LINE_PITCH <= cavity[1]
    bottom_top = drawing.BOTTOM_CENTER[1] + support.WIDE * drawing.VIEW_SCALE / 1000
    assert pocket[1] - NOTE_LINE_PITCH > bottom_top + 0.005


def test_cavity_radius_callout_sits_on_its_corner_bisector_outside_the_view() -> None:
    """CornerFillet's R12.7 is bound to one cavity corner. From the left
    column its leader crossed the whole cavity and landed on the far side of
    the fillet's circle (fix3 render). On the arc's bisector the arrow lands on
    the arc itself; the text stays outside the view and clear of the section's
    callouts."""
    scale = drawing.VIEW_SCALE / 1000
    sign_x, sign_y = drawing.CAVITY_RADIUS_CORNER
    inset = (support.CAV - support.FILLET_R) * scale
    centre = (
        drawing.FRONT_CENTER[0] + sign_x * inset,
        drawing.FRONT_CENTER[1] + sign_y * inset,
    )
    text_xy = drawing.FRONT_KEEP["CavityRadius"]
    angle = math.degrees(
        math.atan2(sign_y * (text_xy[1] - centre[1]), sign_x * (text_xy[0] - centre[0]))
    )
    assert 25.0 < angle < 65.0
    label = _text_box("R.50\n4X", text_xy)
    front_right = drawing.FRONT_CENTER[0] + support.BOSS_DEPTH / 2 * scale
    assert label[0] > front_right + 0.003
    for other in (
        _rim_chamfer_box(),
        _text_box("7.56", drawing.FRONT_KEEP["Depth"]),
    ):
        assert _boxes_clear(label, other, 0.003)


def test_seats_print_as_one_native_callout_with_only_the_transfer_as_text() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRSOJ): the seat note retyped BracketSeats'
    thread and depths, so a model change would leave the print stale. The
    native callout reads count, thread and both depths from the Hole Wizard
    feature; the transfer instruction is the only text, ending in a line
    break so the native size starts its own row (13be2ca03)."""
    bracket = _config.parts("ch-pivot-bracket")["number"]
    assert drawing.SEAT_CALLOUT_PROCESS == f"TRANSFER FROM {bracket}\nAT ASSEMBLY;\n"
    assert not hasattr(drawing, "SEAT_NOTE")
    assert drawing.SEAT_CALLOUT_X_MM == max(seats.SEAT_LOCAL_X)


# Measured on the fix4 render (leaf 20260926T141000Z-1-f32d205b), sheet metres.
SECTION_CAPTION_BOTTOM = 0.1211  # "SECTION A-A" under the section
HOLE_TABLE_BOTTOM = 0.0967
TITLE_BLOCK_TOP, TITLE_BLOCK_LEFT = 0.0649, 0.2183
DEPTH_DIM_LINE_Y = 0.2549  # the 177.8 above the front view


def test_view_b_is_a_cropped_rail_strip_in_the_band_below_the_section() -> None:
    """Main's ruling on Codex PRRT_kwDOPHDy386mRSOJ: the seats get a visible
    circle to carry the callout, in a relocated partial top view (VIEW B) of
    the rail strip, below Section A-A and right of the bottom view."""
    scale = drawing.VIEW_SCALE / 1000
    bottom_right = drawing.BOTTOM_CENTER[0] + support.BOSS_DEPTH / 2 * scale
    x, y = drawing.VIEW_B_CENTER
    half_len = support.BOSS_DEPTH / 2 * scale
    half_crop = drawing.VIEW_B_CROP_HALF_Z_MM * scale
    # The crop keeps the whole rail top (its half-width) and stays clear of
    # the foot holes seen through the cavity: a fence through them left half
    # hole symbols on its edges (r743-p1s-B2 render, Main's eye-pass ruling).
    foot_hole_inner_z = min(abs(z) for _, z in support.HOLES) - support.HOLE_DIA / 2
    assert support.NARROW < drawing.VIEW_B_CROP_HALF_Z_MM < foot_hole_inner_z
    assert x - half_len > bottom_right + 0.010
    assert x + half_len < drawing.HOLE_TABLE_ANCHOR[0] - 0.010
    assert y + half_crop < SECTION_CAPTION_BOTTOM - 0.003
    caption_left, caption_top = drawing.VIEW_B_CAPTION_XY
    caption_lines = drawing.VIEW_B_CAPTION.splitlines()
    assert caption_top < y - half_crop - 0.002
    assert caption_left >= x - half_len
    caption_right = caption_left + max(map(len, caption_lines)) * NOTE_CHAR_WIDTH
    assert caption_right < TITLE_BLOCK_LEFT - 0.003


def test_seat_callout_text_sits_between_the_hole_table_and_the_title_block() -> None:
    """The callout's rows centre on its y; whichever side of its x the text
    falls, five rows of up to 24 characters clear view B, the hole table and
    the title block."""
    scale = drawing.VIEW_SCALE / 1000
    x, y = drawing.SEAT_CALLOUT_XY
    width, half_h = 24 * NOTE_CHAR_WIDTH, 5 * NOTE_LINE_PITCH / 2
    assert y + half_h < HOLE_TABLE_BOTTOM - 0.001
    assert y - half_h > TITLE_BLOCK_TOP + 0.002
    view_b_bottom = drawing.VIEW_B_CENTER[1] - drawing.VIEW_B_CROP_HALF_Z_MM * scale
    assert y + half_h < view_b_bottom - 0.003
    assert x - width > drawing.BOTTOM_CENTER[0] + support.BOSS_DEPTH / 2 * scale
    assert x + width < 0.415  # the right border


def test_hole_table_with_its_mate_column_stays_inside_the_border() -> None:
    """The fifth (MATE) column fits only because the native columns narrow."""
    widths = drawing.HOLE_TABLE_COLUMN_WIDTHS
    assert set(widths) == {0, 1, 2, drawing.HOLE_TABLE_SIZE_COLUMN, drawing.HOLE_TABLE_MATE_COLUMN}
    assert drawing.HOLE_TABLE_ANCHOR[0] + sum(widths.values()) < 0.415
    assert drawing.HOLE_TABLE_MATE == "MHA-FR-01"


def test_chamfer_note_sits_in_the_open_band_under_the_bottom_view() -> None:
    left, top = drawing.CHAMFER_NOTE_XY
    lines = drawing.CHAMFER_NOTE.split("\n")
    right = left + max(len(line) for line in lines) * NOTE_CHAR_WIDTH
    assert left > SHEET_LEFT_INNER_BORDER_X + 0.003
    assert right < TITLE_BLOCK_LEFT - 0.003
    # The note's last line stays over the bottom inner border.
    assert top - len(lines) * NOTE_LINE_PITCH > 0.0127 + 0.002
    scale = drawing.VIEW_SCALE / 1000
    bottom_view_bottom = drawing.BOTTOM_CENTER[1] - support.WIDE * scale
    assert top < bottom_view_bottom - 0.012  # under the origin arrows


def test_view_b_arrow_looks_down_on_the_rail_from_above_the_front_view() -> None:
    scale = drawing.VIEW_SCALE / 1000
    text_xy, tip_xy = drawing.VIEW_B_ARROW
    front_top = drawing.FRONT_CENTER[1] + support.HALF_Y * scale
    assert tip_xy[1] == pytest.approx(front_top)
    assert abs(tip_xy[0] - drawing.FRONT_CENTER[0]) < support.BOSS_DEPTH / 2 * scale
    # The letter stands square above its tip, under the 177.8 dimension line.
    assert text_xy[1] - drawing.VIEW_LETTER_HEIGHT > tip_xy[1] + 0.004
    assert text_xy[1] < DEPTH_DIM_LINE_Y - 0.002
    assert abs(text_xy[0] + drawing.VIEW_LETTER_HEIGHT * 0.36 - tip_xy[0]) < 0.001
    # Clear of the section's own A arrow on the centreline.
    assert abs(tip_xy[0] - drawing.FRONT_CENTER[0]) > 0.015
