"""Offline contracts for the rocker-arm-support drawing."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import _config
import _drawing_common

import draw_rocker_arm_support as drawing
import build_rocker_arm_support as support
import build_frame_assembly as frame
import build_lag_screw as screw
import rocker_arm_support_spec as placement
import rocker_arm_support_drawing_spec as drawing_spec
import rocker_bracket_seat_layout as seats


def test_drawing_keeps_only_make_critical_model_dimensions() -> None:
    expected = {
        "FootSpan",
        "TopSpan",
        "WallHeight",
        "Depth",
        "WinWidth",
        "CavWidth",
        "PocketRadius",
        "CavityRadius",
        "RimChamferSize",
    }
    marked = set().union(*support.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked == expected
    assert drawing.DIMENSION_CALLOUTS == {
        "WinWidth": " POCKET",
        "PocketRadius": "8X",
        "CavityRadius": "4X",
        "CavWidth": "SQ CAVITY THRU",
        "RimChamferSize": " X 45 DEG\n2 FACES",
    }
    assert drawing.DIMENSION_PRECISION == {
        **dict.fromkeys(expected - {"PocketRadius", "RimChamferSize"}, 1),
        "PocketRadius": 2,
        "RimChamferSize": 2,
        "WebThickness": 2,
        "FootThickness": 2,
        "RailDepth": 1,
    }


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
        seats.WINDOW_TOP_Y,
    }
    assert all(abs(edge[2]) > support.WEB for edge in support.POCKET_FILLET_EDGES)


def test_no_process_callout_on_the_sheet() -> None:
    # "Machine both pockets" dictates method (ASME Y14.5 1.4(e)); the section's
    # web dimension defines what the pockets leave, so no callout exists.
    assert not hasattr(support, "WEB_CALLOUT")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_property_linked_callout" not in source
    assert "Web Callout" not in source


def test_support_finish_masks_only_the_machined_mounting_face() -> None:
    assert _config.parts(support.PART_NAME)["finish"] == (
        "GREEN ENAMEL; MASK MOUNTING FACE; LIGHT OIL BARE MACHINED SURFACES"
    )
    assert support.HOLE_SPEC.kind == "drilled_fractional"
    assert support.HOLE_SPEC.size == "5/16"
    assert support.HOLE_DIA == pytest.approx(7.938)
    source = Path(support.__file__).read_text(encoding="utf-8")
    assert "ThreadClass" not in source
    assert "TITLE_BLOCK_THREAD_CLASS" not in source


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
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'surface_finish_by_key(SURFACE_FINISHES, "mounting_face")' in source
    assert source.count("add_surface_finish(") == 1
    assert "MOUNTING_FACE_CALLOUT" not in source
    assert "add_attached_note" not in source


def test_native_hole_table_covers_every_foot_hole() -> None:
    expected_holes = {
        (60.32, 17.46),
        (-60.32, 17.46),
        (60.32, -17.46),
        (-60.32, -17.46),
    }
    assert set(support.HOLES) == expected_holes
    assert drawing.HOLE_TABLE_DATUM_XZ_MM == (
        -support.BOSS_DEPTH / 2.0,
        -support.WIDE,
    )
    x_centres = {x for x, _ in expected_holes}
    y_centres = {y for _, y in expected_holes}
    assert round(max(x_centres) - min(x_centres), 2) == 120.64
    assert round(max(y_centres) - min(y_centres), 2) == 34.92
    expected_locations = {
        (
            round(x + support.BOSS_DEPTH / 2.0, 2),
            round(z + support.WIDE, 2),
        )
        for x, z in expected_holes
    }
    assert set(drawing.EXPECTED_HOLE_TABLE_LOCATIONS_MM) == expected_locations
    xs = {x for x, _ in expected_locations}
    ys = {y for _, y in expected_locations}
    assert round(min(xs) + max(xs), 2) == support.BOSS_DEPTH
    assert round(min(ys) + max(ys), 2) == 2.0 * support.WIDE
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


def test_stock_hold_down_clears_support_and_engages_blind_base_tap() -> None:
    import build_harmonic_base as base

    assert screw.SPEC.skus == ("92240A540",)
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
    # Sized at the printed .XX band's worst case (base.seat_thread_depth).
    assert base.HOLD_DOWN_THREAD_DEPTH == pytest.approx(
        base.seat_thread_depth(base.HOLD_DOWN_ENGAGEMENT)
    )
    assert (
        base.HOLD_DOWN_THREAD_DEPTH - base.SEAT_DEPTH_BAND - base.HOLD_DOWN_ENGAGEMENT
        >= base.HOLD_DOWN_TIP_CLEARANCE
    )
    assert base.HOLD_DOWN_DRILL_DEPTH - base.SEAT_DEPTH_BAND >= (
        base.HOLD_DOWN_THREAD_DEPTH + base.SEAT_DEPTH_BAND + 5.0 * screw.THREAD_PITCH
    )
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
    assert {z for _, z in placement.SUPPORT_HOLD_DOWN_XZ} == {
        -60.32,
        60.32,
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
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(_drawing_common, "view_name", lambda *_: "Front")
    monkeypatch.setattr(_drawing_common, "double_array", tuple)
    monkeypatch.setattr(
        _drawing_common._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
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
    result = _drawing_common.create_section_view(
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
        _drawing_common.create_section_view(
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
        _drawing_common.create_section_view(
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
    # spec, so a window or rail edit in the COM builder re-keys none of them.
    for name in ("WIDE", "NARROW", "HALF_Y", "FOOT_THICKNESS", "HOLE_SPEC", "HOLE_DIA"):
        assert getattr(support, name) is getattr(placement, name)
    assert drawing_spec.HALF_Y is placement.HALF_Y
    # The base seats key on the foot: it stays exactly the source's 6.35.
    assert placement.FOOT_THICKNESS == 6.35
    assert support.BIG == pytest.approx(82.55)


def test_deeper_rail_lowers_only_the_window_top() -> None:
    assert seats.RAIL_DEPTH == 21.0
    assert seats.WINDOW_TOP_Y == pytest.approx(67.9)
    assert seats.WINDOW_BOTTOM_Y == pytest.approx(-support.BIG)
    assert seats.WINDOW_HEIGHT == pytest.approx(150.45)
    # 165.1 wide by 150.45 tall: the print no longer calls it square.
    assert 2.0 * support.BIG - seats.WINDOW_HEIGHT > 10.0
    assert "SQ" not in drawing.DIMENSION_CALLOUTS["WinWidth"]
    # The cavity's chamfered top rim stays a web edge under the rail.
    assert seats.WINDOW_TOP_Y - support.CAV == pytest.approx(4.4)


def test_rail_volume_deltas_are_the_closed_forms() -> None:
    def wall(y: float) -> float:
        return support.WIDE + (support.NARROW - support.WIDE) * (
            (y + support.HALF_Y) / (2.0 * support.HALF_Y)
        )

    # The band WINDOW_TOP_Y..BIG, numerically integrated, per pocket side.
    steps = 2000
    dy = (support.BIG - seats.WINDOW_TOP_Y) / steps
    band = sum(
        2.0
        * support.BIG
        * (wall(seats.WINDOW_TOP_Y + (i + 0.5) * dy) - support.WEB)
        * dy
        for i in range(steps)
    )
    assert support.RAIL_BAND_VOLUME == pytest.approx(band, rel=1e-9)
    assert support.WINDOW_CUT1_VOLUME - support.SQUARE_WINDOW_CUT1_VOLUME == (
        pytest.approx(band)
    )
    assert support.WINDOW_CUT2_VOLUME - support.SQUARE_WINDOW_CUT2_VOLUME == (
        pytest.approx(2.0 * band)
    )
    # Moving four spandrels down to a thicker wall adds material, a little.
    assert 0.0 < support.TOP_FILLET_SHIFT_VOLUME < 100.0
    # The rim chamfer runs on four shorter window side edges.
    removal = support.FOOT_HOLED_VOLUME - support.RIM_CHAMFER_VOLUME
    assert removal == pytest.approx(
        support.SQUARE_RIM_CHAMFER_REMOVAL
        - 4.0 * (support.BIG - seats.WINDOW_TOP_Y) * support.CHAMFER**2 / 2.0
    )
    assert support.BRACKET_SEATS_VOLUME < support.RIM_CHAMFER_VOLUME


def test_bracket_seats_sit_under_the_bracket_holes_on_the_rail() -> None:
    import pivot_bracket_spec as bracket
    import rocker_bank_layout as bank

    assert seats.SEAT_SPEC.kind == "tapped_bottoming"
    assert seats.SEAT_SPEC.size == seats.SCREW_THREAD == "#8-32"
    assert seats.SEAT_SPEC.depth_mm == seats.SEAT_DRILL_DEPTH == 18.0
    assert seats.SEAT_SPEC.overrides_mm == {"ThreadDepth": seats.SEAT_THREAD_DEPTH}
    assert seats.SEAT_THREAD_DEPTH == 14.7
    assert len(seats.SEAT_MACHINE_XZ) == 2 * len(bank.PIVOT_BRACKET_Z)
    south, north = bank.PIVOT_BRACKET_Z
    assert [z for _, z in seats.SEAT_MACHINE_XZ] == pytest.approx(
        [south + h for h in bracket.HOLE_Z] + [north - h for h in bracket.HOLE_Z]
    )
    assert {x for x, _ in seats.SEAT_MACHINE_XZ} == {placement.SUPPORT_WORLD_X}
    assert [p[0] for p in support.SEAT_POINTS] == pytest.approx(
        [placement.SUPPORT_WORLD_Z - z for _, z in seats.SEAT_MACHINE_XZ]
    )
    assert all(p[1:] == [support.HALF_Y, 0.0] for p in support.SEAT_POINTS)


def test_bracket_screw_stack_holds_at_the_printed_worst_case() -> None:
    # MHA-143 #8-32 x 3/4 through MHA-123's 6.0 (.XX) foot.
    assert seats.SCREW_REACH_MIN == pytest.approx(19.05 - 0.76 - 6.508)
    assert seats.SCREW_REACH_MAX == pytest.approx(19.05 - 5.492)
    assert seats.ENGAGEMENT_MIN >= 1.5 * seats.SCREW_MAJOR_DIA
    assert seats.SEAT_THREAD_DEPTH - 0.8 >= seats.SCREW_REACH_MAX + 0.25
    assert seats.SEAT_DRILL_DEPTH - 0.8 >= seats.SEAT_THREAD_DEPTH + 0.8 + 2 * 25.4 / 32
    assert seats.SEAT_DRILL_BOTTOM_MAX + 0.25 <= seats.RAIL_DEPTH - 0.8
    assert seats.RAIL_WALL >= 2.0


def test_section_picks_land_on_the_rail_and_the_lower_web() -> None:
    def wall(y: float) -> float:
        return support.WIDE + (support.NARROW - support.WIDE) * (
            (y + support.HALF_Y) / (2.0 * support.HALF_Y)
        )

    # Top face: half-width NARROW less the rim chamfer. Pocket top face: from
    # the web face out to the chamfered wall.
    z = drawing.RAIL_PICK_Z
    assert z < support.NARROW - support.CHAMFER
    assert support.WEB < z < wall(seats.WINDOW_TOP_Y) - support.CHAMFER
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "RIGHT_CENTER[1] - (BIG + CAV) / 2.0" in source
    assert 'label="section rail depth"' in source


def test_seat_note_names_the_transfer_and_both_depths() -> None:
    assert drawing.SEAT_NOTE == (
        "4X #8-32 UNC-2B\n14.7 DEEP\n#29 DRILL 18.0 DEEP\n"
        "TRANSFER FROM MHA-123\nAT ASSEMBLY"
    )
    # The leader lands on the rail's top edge over the outermost seat.
    assert drawing.SEAT_NOTE_ATTACH == pytest.approx(
        (
            drawing.FRONT_CENTER[0]
            + min(seats.SEAT_LOCAL_X) * drawing.VIEW_SCALE / 1000,
            drawing.FRONT_CENTER[1] + support.HALF_Y * drawing.VIEW_SCALE / 1000,
        )
    )


def test_rim_chamfer_is_placed_on_the_section_by_a_targeted_import() -> None:
    """#743: the front view only ever got RimChamferSize from the entire-model
    import, and the rail took it away (r743-diag-a/b). A targeted RimChamfer
    import into the section delivers it (r743-diag-c), so the section owns it
    and its curate imports only the features that own its kept dimensions."""
    import ast

    assert "RimChamferSize" in drawing.RIGHT_KEEP
    assert "RimChamferSize" not in drawing.FRONT_KEEP
    owned = set().union(*support.DRAWING_DIMENSIONS.values())
    assert set(drawing.RIGHT_KEEP) <= owned

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    curates = {
        call.args[1].id: {kw.arg: kw.value for kw in call.keywords}
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "curate_view_dimensions"
    }
    section = curates["right"]
    assert isinstance(section["keep"], ast.Name) and section["keep"].id == "RIGHT_KEEP"
    by_feature = section.get("dimensions_by_feature")
    assert isinstance(by_feature, ast.Name) and by_feature.id == "DRAWING_DIMENSIONS"
    assert drawing.DRAWING_DIMENSIONS is support.DRAWING_DIMENSIONS


def test_precision_reaches_every_dimension_exactly_once() -> None:
    """r743-rocker-fix (53cb9ad5b) failed "dimension precision not applied:
    ['RailDepth']": the bulk call covers only imported dimensions, and the
    sheet-made ones (web, foot, rail depth) set their own after the import.
    Every DIMENSION_PRECISION name goes through exactly one of the two."""
    import ast

    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    bulk = drawing.imported_precision()
    assert set(bulk) == kept & set(drawing.DIMENSION_PRECISION)
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    own = {
        node.slice.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "DIMENSION_PRECISION"
        and isinstance(node.slice, ast.Constant)
    }
    assert own == {"WebThickness", "FootThickness", "RailDepth"}
    assert not own & set(bulk)
    assert own | set(bulk) == set(drawing.DIMENSION_PRECISION)


def _z_line(y_mm: float, z0_mm: float, z1_mm: float, *, direction=(0.0, 0.0, 1.0)):
    points = [(0.0, y_mm / 1000.0, z0_mm / 1000.0), (0.0, y_mm / 1000.0, z1_mm / 1000.0)]
    curve = SimpleNamespace(
        IsLine=lambda: True, LineParams=(*points[0], *direction)
    )
    return SimpleNamespace(
        GetCurve=lambda: curve,
        GetStartVertex=lambda: SimpleNamespace(GetPoint=lambda: points[0]),
        GetEndVertex=lambda: SimpleNamespace(GetPoint=lambda: points[1]),
        name=f"y{y_mm} z{z0_mm}..{z1_mm}",
    )


def test_rail_depth_is_dimensioned_between_exact_section_edges(monkeypatch) -> None:
    """r743-rocker-fix2 (2570b5251): the coordinate picks for the rail depth
    produced "section rail dimension measured 2225.982125 mm". The section now
    hands add_edge_dimension the longest visible model lines along Z on the top
    face and on the window's top face."""
    arc = SimpleNamespace(GetCurve=lambda: SimpleNamespace(IsLine=lambda: False))
    edges = [
        _z_line(support.HALF_Y, -7.2, 7.2),
        _z_line(support.HALF_Y, -1.0, 1.0),
        _z_line(seats.WINDOW_TOP_Y, -9.9, -3.175),
        _z_line(seats.WINDOW_TOP_Y, 3.175, 5.0),
        _z_line(seats.WINDOW_TOP_Y, -50.0, 50.0, direction=(1.0, 0.0, 0.0)),
        arc,
    ]
    view = SimpleNamespace(
        GetVisibleComponents=lambda: ("support",),
        GetVisibleEntities2=lambda component, kind: tuple(edges),
    )
    adapter = SimpleNamespace(_attempt=lambda call, default=None: call())
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    top, window = drawing._right_rail_edges(adapter, view)
    assert top.name == f"y{support.HALF_Y} z-7.2..7.2"
    assert window.name == f"y{seats.WINDOW_TOP_Y} z-9.9..-3.175"

    edges[:] = [_z_line(support.HALF_Y, -7.2, 7.2)]
    with pytest.raises(RuntimeError, match="window top-face"):
        drawing._right_rail_edges(adapter, view)

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "entities=_right_rail_edges(adapter, right)" in source


def test_seat_note_stays_left_of_the_depth_callout_and_above_the_view() -> None:
    """Offline extent check after r743-rocker-fix2: at ~0.75 x height per
    character (the drive-train package's measured 2.63 mm at 3.5 mm) and
    ~1.3 x height per line (its 4.525 mm pitch), the note ends left of the
    front view's left edge, where the Depth extension line runs, and above the
    view's top edge, under the top zone border."""
    height = drawing.SEAT_NOTE_HEIGHT
    lines = drawing.SEAT_NOTE.splitlines()
    right = drawing.SEAT_NOTE_XY[0] + max(map(len, lines)) * 0.75 * height
    bottom = drawing.SEAT_NOTE_XY[1] - len(lines) * 1.3 * height
    front_left = drawing.FRONT_CENTER[0] - support.HALF_Y * drawing.VIEW_SCALE / 1000
    front_top = drawing.FRONT_CENTER[1] + support.HALF_Y * drawing.VIEW_SCALE / 1000
    assert right < front_left - 0.002
    assert bottom > front_top + 0.002
    assert drawing.SEAT_NOTE_XY[1] <= 0.263
