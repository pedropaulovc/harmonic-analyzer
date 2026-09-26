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
    points = [
        (0.0, y_mm / 1000.0, z0_mm / 1000.0),
        (0.0, y_mm / 1000.0, z1_mm / 1000.0),
    ]
    curve = SimpleNamespace(IsLine=lambda: True, LineParams=(*points[0], *direction))
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


# Sheet-default note text as rendered by r743-rocker-fix3 (leaf
# 20260926T112244Z-1-a884759d): "TRANSFER FROM MHA-123" spanned 57.6 mm for 21
# characters and five lines stepped 4.45 mm. add_note does not apply a height,
# so every note on this sheet renders at this size.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045


def _text_box(text: str, center: tuple[float, float]) -> tuple[float, ...]:
    """(left, bottom, right, top) of a note or dimension text centred on ``center``."""
    lines = text.splitlines()
    half_w = max(map(len, lines)) * NOTE_CHAR_WIDTH / 2.0
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


def test_rim_chamfer_callout_clears_the_rail_depth_text() -> None:
    """r743-rocker-fix3 ran "X 45 DEG" into the section's 21.0: both sat in the
    lane between the front view and the section at y ~0.224."""
    # Rendered as three lines: the value, then the callout's two.
    assert drawing.DIMENSION_CALLOUTS["RimChamferSize"] == " X 45 DEG\n2 FACES"
    chamfer = _text_box("1.27\nX 45 DEG\n2 FACES", drawing.RIGHT_KEEP["RimChamferSize"])
    rail = _text_box(f"{support.RAIL_DEPTH:.1f}", drawing.RAIL_TEXT_XY)
    assert _boxes_clear(chamfer, rail, 0.003)
    # ...and stays right of the front view.
    front_right = drawing.FRONT_CENTER[0] + support.HALF_Y * drawing.VIEW_SCALE / 1000
    assert chamfer[0] > front_right + 0.003


def test_web_thickness_text_clears_the_wall_and_the_height_dimension() -> None:
    """r743-rocker-fix3 printed the section's 6.35 across the slanted wall
    line; the text must sit between that wall and the 177.8 dimension line."""
    web = _text_box(f"{2 * support.WEB:.2f}", drawing.WEB_TEXT_XY)
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
    foot = _text_box(f"{support.HALF_Y - support.BIG:.2f}", drawing.FOOT_TEXT_XY)
    foot_top_y = drawing.RIGHT_CENTER[1] - support.BIG * scale
    assert foot[1] > foot_top_y + 0.002
    lowest_local_y = (foot[1] - drawing.RIGHT_CENTER[1]) / scale
    wall_x = drawing.RIGHT_CENTER[0] - support._wall_half_z_at(lowest_local_y) * scale
    assert foot[2] < wall_x - 0.002
    front_right = drawing.FRONT_CENTER[0] + support.BOSS_DEPTH / 2 * scale
    assert foot[0] > front_right + 0.003


def test_iso_tapped_hole_label_is_materialized_then_removed() -> None:
    """r743-rocker-fix3's isometric carried SolidWorks' own "#8-32 Tapped
    Hole" label past the right border. The seat note already states the thread,
    so the cosmetic threads are imported before finalize (the pen-hanger
    pattern) and finalize removes exactly that one label."""
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    (finalize,) = [c for c in calls if c.func.id == "finalize_drawing"]
    kwargs = {
        k.arg: ast.literal_eval(k.value)
        for k in finalize.keywords
        if k.arg in {"redundant_note_substrings", "expected_redundant_notes"}
    }
    assert kwargs == {
        "redundant_note_substrings": ("Tapped Hole",),
        "expected_redundant_notes": 1,
    }
    threads = [c for c in calls if c.func.id == "import_cosmetic_threads"]
    assert [[ast.unparse(a) for a in c.args] for c in threads] == [
        ["adapter", "iso"],
        ["adapter", "view_b"],
    ]
    assert all(c.lineno < finalize.lineno for c in threads)


def test_stacked_pocket_widths_keep_separate_bands() -> None:
    """Each stacked width prints its text just above its own dimension line.
    At WinWidth y 0.118 the 127.0 line ran through "165.1" (Main's fix3 eye
    pass), so the lower text clears the upper dimension by a full line pitch,
    and its own line still stays above the bottom view."""
    cavity = _text_box("127.0\nSQ CAVITY THRU", drawing.FRONT_KEEP["CavWidth"])
    pocket = _text_box("165.1\nPOCKET", drawing.FRONT_KEEP["WinWidth"])
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
    label = _text_box("R12.7\n4X", text_xy)
    front_right = drawing.FRONT_CENTER[0] + support.BOSS_DEPTH / 2 * scale
    assert label[0] > front_right + 0.003
    for other in (
        _text_box("16.9", drawing.RIGHT_KEEP["TopSpan"]),
        _text_box(f"{support.RAIL_DEPTH:.1f}", drawing.RAIL_TEXT_XY),
        _text_box("1.27\nX 45 DEG\n2 FACES", drawing.RIGHT_KEEP["RimChamferSize"]),
        _text_box("177.8", drawing.FRONT_KEEP["Depth"]),
    ):
        assert _boxes_clear(label, other, 0.003)


def _fake_note_annotation(text: str, x: float, y: float, *, kind: int = 6):
    state = {"position": (x, y, 0.0)}
    note = SimpleNamespace(GetText=lambda: text)

    def set_position(new_x, new_y, new_z):
        state["position"] = (new_x, new_y, new_z)
        return True

    return SimpleNamespace(
        GetType=lambda: kind,
        GetSpecificAnnotation=lambda: note,
        GetPosition=lambda: state["position"],
        SetPosition2=set_position,
    )


def test_right_end_hole_tags_move_left_of_their_holes(monkeypatch) -> None:
    """A3 and A4 printed across the pocket's hidden end lines (fix3 render).
    They take the mirror spot left of their holes; A1 and A2 stay put."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    tags = {
        name: _fake_note_annotation(name, x, y)
        for name, x, y in (
            ("A1", 0.0796, 0.0661),
            ("A2", 0.0796, 0.0878),
            ("A3", 0.1397, 0.0661),
            ("A4", 0.1397, 0.0878),
        )
    }
    dimension = _fake_note_annotation("A4", 0.2, 0.1, kind=1)
    view = SimpleNamespace(GetAnnotations=lambda: (*tags.values(), dimension))
    moved = drawing._mirror_right_end_hole_tags(view)
    assert set(moved) == {"A3", "A4"}
    for name in ("A3", "A4"):
        assert tags[name].GetPosition()[0] == pytest.approx(
            0.1397 + drawing.HOLE_TAG_MIRROR_SHIFT
        )
    assert tags["A1"].GetPosition()[0] == 0.0796
    assert dimension.GetPosition()[0] == 0.2

    # Measured on A4 in the fix3 render: the tag's left edge 4.6 mm right of
    # its hole centre, 5.8 mm wide. The shift mirrors it about the hole.
    scale = drawing.VIEW_SCALE / 1000
    hole_x = (
        drawing.BOTTOM_CENTER[0]
        + (
            drawing.HOLE_TABLE_DATUM_XZ_MM[0]
            + drawing.EXPECTED_HOLE_TABLE_LOCATIONS_MM[0][0]
        )
        * scale
    )
    moved_right = hole_x + 0.0046 + 0.0058 + drawing.HOLE_TAG_MIRROR_SHIFT
    assert hole_x - moved_right == pytest.approx(0.0046, abs=0.0005)


def test_right_end_hole_tag_mover_fails_loud(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    only_a3 = SimpleNamespace(
        GetAnnotations=lambda: (_fake_note_annotation("A3", 0.1397, 0.0661),)
    )
    with pytest.raises(RuntimeError, match="A4"):
        drawing._mirror_right_end_hole_tags(only_a3)
    left_a4 = SimpleNamespace(
        GetAnnotations=lambda: (_fake_note_annotation("A4", 0.0796, 0.0878),)
    )
    with pytest.raises(RuntimeError, match="not at the right end"):
        drawing._mirror_right_end_hole_tags(left_a4)


def test_seats_print_as_one_native_callout_with_only_the_transfer_as_text() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRSOJ): the seat note retyped BracketSeats'
    thread and depths, so a model change would leave the print stale. The
    native callout reads count, thread and both depths from the Hole Wizard
    feature; the transfer instruction is the only text, ending in a line
    break so the native size starts its own row (13be2ca03)."""
    bracket = _config.parts("pivot-bracket")["number"]
    assert drawing.SEAT_CALLOUT_PROCESS == f"TRANSFER FROM {bracket}\nAT ASSEMBLY;\n"
    assert not hasattr(drawing, "SEAT_NOTE")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for retyped in ("UNC-2B", " DEEP", "SEAT_THREAD_DEPTH", "SEAT_DRILL_DEPTH"):
        assert retyped not in source, retyped
    assert "process=SEAT_CALLOUT_PROCESS" in source
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
    # The crop keeps the whole rail top (its half-width) and stays inside the
    # foot, so only rail-strip ink survives.
    assert support.NARROW < drawing.VIEW_B_CROP_HALF_Z_MM < support.WIDE
    assert x - half_len > bottom_right + 0.010
    assert x + half_len < drawing.HOLE_TABLE_ANCHOR[0] - 0.010
    assert y + half_crop < SECTION_CAPTION_BOTTOM - 0.003
    caption_left, caption_top = drawing.VIEW_B_CAPTION_XY
    caption_lines = drawing.VIEW_B_CAPTION.splitlines()
    assert caption_lines == ["VIEW B", "SCALE 1:2"]
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


def _circle_edge(x_mm: float, y_mm: float, radius_mm: float):
    curve = SimpleNamespace(
        IsCircle=lambda: True,
        CircleParams=(x_mm / 1000, y_mm / 1000, 0.0, 0.0, 1.0, 0.0, radius_mm / 1000),
    )
    return SimpleNamespace(GetCurve=lambda: curve, name=(x_mm, y_mm, radius_mm))


def test_seat_entry_edge_is_the_east_seats_rim_on_the_rail_top(monkeypatch) -> None:
    """The edge comes from the part through the typed seat cylinder: the one
    drill-diameter circle of the east seat on the rail top, never the rim
    where the drill point starts."""
    from _hole_spec import blind_cut_dia_mm

    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    east = max(seats.SEAT_LOCAL_X)
    entry = _circle_edge(east, support.HALF_Y, radius)
    face = SimpleNamespace(
        GetEdges=lambda: (
            _circle_edge(east, support.HALF_Y - seats.SEAT_DRILL_DEPTH, radius),
            entry,
            SimpleNamespace(GetCurve=lambda: SimpleNamespace(IsCircle=lambda: False)),
        )
    )
    requested = {}

    def resolve(model, requests):
        requested.update(requests)
        return {"seat": face}

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "_resolve_faces", resolve)
    view = SimpleNamespace(ReferencedDocument=object())
    assert drawing._seat_entry_edge(view) is entry
    (spec,) = requested.values()
    assert spec.diameter_mm == pytest.approx(2 * radius)
    assert spec.contains_x_mm == east


# r743-p1s-A: VIEW B's GetOutline right after its crop, which had not
# narrowed it; the fake serves it as the uncropped outline.
UNCROPPED_VIEW_B_OUTLINE = (0.15183, 0.09033, 0.26817, 0.12565)
# The view border GetOutline adds around what a crop keeps (fake only).
BORDER = (0.012, 0.002)


class _CropSeat:
    """Just enough of IDrawingDoc/IView to run the VIEW B crop offline."""

    def __init__(
        self,
        crop_result: int = 1,
        cropped: bool = True,
        crop_lands: bool = True,
        origin: tuple[float, float] = drawing.VIEW_B_CENTER,
        end_run: float | None = None,
    ) -> None:
        self.rectangle = None
        self.crop_calls = []
        self.selected = []
        self.selected_at_crop = None
        self.rebuilds = []
        self.origin = origin
        self.end_run = (
            support.BOSS_DEPTH / 2 * drawing.VIEW_SCALE / 1000
            if end_run is None
            else end_run
        )
        self.crop_result = crop_result
        self.cropped = cropped
        self.crop_lands = crop_lands
        identity = SimpleNamespace()
        self.sketch = SimpleNamespace(ModelToSketchTransform=identity)
        self.model = SimpleNamespace(
            ActivateView=lambda _name: True,
            ClearSelection2=lambda _all: None,
            EditRebuild3=lambda: True,
            SketchManager=SimpleNamespace(CreateCornerRectangle=self._rectangle),
            SelectionManager=SimpleNamespace(
                GetSelectedObjectCount2=lambda _mark: len(self.selected)
            ),
        )
        math_utility = SimpleNamespace(
            CreatePoint=lambda data: SimpleNamespace(
                MultiplyTransform=lambda _t: SimpleNamespace(ArrayData=tuple(data))
            )
        )
        self.adapter = SimpleNamespace(
            currentModel=self.model,
            swApp=SimpleNamespace(GetMathUtility=lambda: math_utility),
        )
        self.view = SimpleNamespace(
            GetSketch=lambda: self.sketch,
            Crop2=self._crop,
            UpdateViewDisplayGeometry=lambda: None,
            IsCropped=lambda: self.cropped,
            GetOutline=self._outline,
            ScaleDecimal=0.5,
            Position=drawing.VIEW_B_CENTER,
        )

    def _rectangle(self, *coords):
        self.rectangle = coords
        return tuple(
            SimpleNamespace(
                Select4=lambda append, _data, i=i: self.selected.append(i) or True
            )
            for i in range(4)
        )

    def _crop(self, *args):
        self.crop_calls.append(args)
        self.selected_at_crop = sorted(self.selected)
        return self.crop_result

    def project(self, _adapter, _view, xyz, *, label):
        # *Top at 1:2: model +X runs along the sheet from the part origin.
        del label
        return (
            self.origin[0] + xyz[0] / (support.BOSS_DEPTH / 2000) * self.end_run,
            self.origin[1],
        )

    def _outline(self):
        if not (self.crop_calls and self.crop_lands):
            return UNCROPPED_VIEW_B_OUTLINE
        x1, y1, _z1, x2, y2, _z2 = self.rectangle
        bx, by = BORDER
        return (
            min(x1, x2) - bx,
            min(y1, y2) - by,
            max(x1, x2) + bx,
            max(y1, y2) + by,
        )


def _patch_crop_seat(monkeypatch, seat: _CropSeat) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "VIEW B")
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(drawing, "model_point_in_view", seat.project)
    monkeypatch.setattr(
        drawing,
        "rebuild_drawing",
        lambda _adapter, *, label: seat.rebuilds.append(label),
    )


def test_view_b_crop_fence_is_the_rail_strip_across_the_whole_rail(monkeypatch) -> None:
    seat = _CropSeat()
    _patch_crop_seat(monkeypatch, seat)
    drawing._crop_view_b_to_rail(seat.adapter, seat.view)
    # Rebuilt after placement, before the fence is located (positive control).
    assert seat.rebuilds == ["VIEW B placement"]
    # Crop2 is handed the whole closed fence.
    assert seat.selected_at_crop == [0, 1, 2, 3]
    scale = drawing.VIEW_SCALE / 1000
    x1, y1, _z1, x2, y2, _z2 = seat.rectangle
    cx, cy = drawing.VIEW_B_CENTER
    assert min(x1, x2) < cx - support.BOSS_DEPTH / 2 * scale
    assert max(x1, x2) > cx + support.BOSS_DEPTH / 2 * scale
    assert (min(y1, y2), max(y1, y2)) == pytest.approx(
        (
            cy - drawing.VIEW_B_CROP_HALF_Z_MM * scale,
            cy + drawing.VIEW_B_CROP_HALF_Z_MM * scale,
        )
    )
    # Straight-edged crop with no outline (swCropViewErrors_e NoError = 1).
    assert seat.crop_calls == [(False, True, 0)]


@pytest.mark.parametrize(
    ("crop_result", "cropped", "crop_lands", "message"),
    (
        (0, True, True, "failed to crop"),
        (1, False, True, "did not retain"),
        # Crop2 and IsCropped both report success, but the outline is the
        # uncropped view's.
        (1, True, False, "not the rail strip"),
    ),
)
def test_view_b_crop_fails_loud(
    monkeypatch, crop_result, cropped, crop_lands, message
) -> None:
    seat = _CropSeat(crop_result=crop_result, cropped=cropped, crop_lands=crop_lands)
    _patch_crop_seat(monkeypatch, seat)
    with pytest.raises(RuntimeError, match=message):
        drawing._crop_view_b_to_rail(seat.adapter, seat.view)


def test_view_b_fence_follows_the_part_origin_it_measured(monkeypatch) -> None:
    offset = (drawing.VIEW_B_CENTER[0] + 0.0006, drawing.VIEW_B_CENTER[1] - 0.0004)
    seat = _CropSeat(origin=offset)
    _patch_crop_seat(monkeypatch, seat)
    drawing._crop_view_b_to_rail(seat.adapter, seat.view)
    x1, y1, _z1, x2, y2, _z2 = seat.rectangle
    assert ((x1 + x2) / 2, (y1 + y2) / 2) == pytest.approx(offset)


@pytest.mark.parametrize(
    ("origin", "end_run"),
    (
        # The part landed off VIEW_B_CENTER.
        ((drawing.VIEW_B_CENTER[0] + 0.003, drawing.VIEW_B_CENTER[1]), None),
        # The view came out 1:1, not 1:2.
        (drawing.VIEW_B_CENTER, support.BOSS_DEPTH / 2 / 1000),
    ),
)
def test_view_b_refuses_a_misplaced_or_misscaled_view(
    monkeypatch, origin, end_run
) -> None:
    seat = _CropSeat(origin=origin, end_run=end_run)
    _patch_crop_seat(monkeypatch, seat)
    with pytest.raises(RuntimeError, match="not the rail at 1:2"):
        drawing._crop_view_b_to_rail(seat.adapter, seat.view)
    assert seat.crop_calls == []
