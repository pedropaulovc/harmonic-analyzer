"""Offline contracts for the rocker-arm-support drawing."""

from __future__ import annotations

import contextlib
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import _config
import _drawing_common
import _part_pmi
import _section_axis
from _hole_spec import blind_cut_dia_mm

import draw_fr_rocker_arm_support as drawing
import build_fr_rocker_arm_support as support
import build_fr_frame_assembly as frame
import build_vn_lag_screw as stock_screw
import vn_lag_screw_spec as screw
import fr_rocker_arm_support_section_spec as section
import fr_rocker_arm_support_spec as placement
import fr_rocker_arm_support_drawing_spec as drawing_spec
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
        "RailDepth",
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
        **dict.fromkeys(expected - {"PocketRadius", "RimChamferSize", "RailDepth"}, 1),
        "PocketRadius": 2,
        "RimChamferSize": 2,
        "WebThickness": 2,
        "FootThickness": 2,
    }
    # The rail depth's places are the part's (Codex #936 PRRT_kwDOPHDy386mTMXw).
    assert drawing.MODEL_OWNED_PRECISION == {"RailDepth": seats.RAIL_DEPTH_PLACES}


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


def test_pockets_have_no_unapproved_machining_callout() -> None:
    # "Machine both pockets" dictates method (ASME Y14.5 1.4(e)); the section's
    # web dimension defines what the pockets leave, so no callout exists.
    assert not hasattr(support, "WEB_CALLOUT")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_property_linked_callout" not in source
    assert "Web Callout" not in source


def test_support_finish_masks_mounting_and_machined_table_pickup_faces() -> None:
    assert _config.parts(support.PART_NAME)["finish"] == (
        "GREEN ENAMEL; MASK MOUNTING AND TABLE PICKUP FACES; "
        "LIGHT OIL BARE MACHINED SURFACES"
    )
    assert support.HOLE_SPEC.kind == "drilled_fractional"
    assert support.HOLE_SPEC.size == "5/16"
    assert support.HOLE_DIA == pytest.approx(7.938)
    source = Path(support.__file__).read_text(encoding="utf-8")
    assert "ThreadClass" not in source
    assert "TITLE_BLOCK_THREAD_CLASS" not in source


def test_mounting_face_carries_the_seat_finish_symbol_not_a_note() -> None:
    # The existing mounting face is still the only numeric finish requirement.
    # The newly-required table pickups carry machining but no invented Ra.
    # The mounting face is -Y at y=-HALF_Y, with offset +HALF_Y along its normal.
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


def test_finished_pickup_faces_meet_the_unchanged_theoretical_table_corner():
    corner = (-section.BOSS_DEPTH / 2, -section.HALF_Y, -section.WIDE)
    assert corner == (-88.9, -88.9, -31.75)
    assert drawing.HOLE_TABLE_DATUM_XZ_MM == (corner[0], corner[2])
    assert set(drawing_spec.TABLE_PICKUP_FACES) == {
        "table_pickup_end", "table_pickup_taper"
    }
    for face in drawing_spec.TABLE_PICKUP_FACES.values():
        assert math.dist(face.normal, (0, 0, 0)) == pytest.approx(1)
        assert sum(n * p for n, p in zip(face.normal, corner)) == pytest.approx(
            face.offset_mm
        )
    taper = drawing_spec.TABLE_PICKUP_FACES["table_pickup_taper"]
    assert taper.normal[1] > 0
    assert taper.normal[2] < -0.99
    top_of_taper = (0, section.HALF_Y, -section.NARROW)
    assert sum(n * p for n, p in zip(taper.normal, top_of_taper)) == pytest.approx(
        taper.offset_mm
    )
    # Machining is newly required, but the existing mounting grade is the ONLY Ra.
    assert [control.roughness_um for control in drawing_spec.SURFACE_FINISHES] == [3.2]
    assert "Ra" not in drawing_spec.TABLE_PICKUP_PROCESS
    assert _config.parts(support.PART_NAME)["process"] == (
        "casting; machine mounting and hole-table pickup faces "
        "before hole location or inspection"
    )


class _PickupPlaneFace:
    def __init__(self, context, name, normal, point_mm, reference):
        self.context = context
        self.name = name
        self.normal = normal
        self.point_mm = point_mm
        self.surface = SimpleNamespace(
            Identity=4001,
            PlaneParams=(*normal, *(value / 1000 for value in point_mm)),
        )
        self.FaceInSurfaceSense = False
        self.reference = reference
        self.next_face = None

    def GetSurface(self):
        return self.surface

    def GetBox(self):
        low_x, high_x = -section.BOSS_DEPTH / 2, section.BOSS_DEPTH / 2
        low_y, high_y = -section.HALF_Y, section.HALF_Y
        low_z, high_z = -section.WIDE, section.WIDE
        if self.normal[0]:
            low_x = high_x = self.point_mm[0]
        elif self.normal == (0, -1, 0):
            low_y = high_y = self.point_mm[1]
        else:
            sign = 1 if self.normal[2] > 0 else -1
            low_z, high_z = sorted((sign * section.WIDE, sign * section.NARROW))
        return tuple(
            value / 1000 for value in (low_x, low_y, low_z, high_x, high_y, high_z)
        )

    def GetNextFace(self):
        return self.next_face

    def GetFeature(self):
        return SimpleNamespace(Name="Wall", GetTypeName2=lambda: "Boss")

    def Select4(self, _append, _callout):
        context = self.context
        if context["failure"] == "refused":
            return False
        if context["failure"] == "empty_selection":
            context["selected"] = []
        elif context["failure"] == "wrong_face":
            context["selected"] = [context["opposite_end"]]
        elif context["failure"] == "multiple":
            context["selected"] = [self, context["opposite_end"]]
        else:
            context["selected"] = [self]
        return True


def _native_pickup_part(monkeypatch, *, failure=None):
    """Drive the real resolver with independent trapezoid-plane native seams."""
    monkeypatch.setattr(_part_pmi, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(_part_pmi, "_bind", lambda obj, _name: obj)
    monkeypatch.setattr(_part_pmi, "null_callout", lambda: None)
    monkeypatch.setattr(support, "_early_bound", lambda obj, _name: obj)

    def invoke(obj, _interface, name, *args):
        member = getattr(obj, name)
        return member(*args) if callable(member) else member

    monkeypatch.setattr(_part_pmi, "_com_invoke", invoke)
    context = {"selected": [], "failure": failure}
    # Construct the slant normal from the actual section segment's direction,
    # not from TABLE_PICKUP_FACES or its already-computed normal/offset.
    dy = 2 * section.HALF_Y
    dz = section.WIDE - section.NARROW
    length = math.hypot(dy, dz)
    end = _PickupPlaneFace(
        context, "end", (-1, 0, 0), (-section.BOSS_DEPTH / 2, 0, 0), b"\x01"
    )
    opposite_end = _PickupPlaneFace(
        context, "opposite_end", (1, 0, 0), (section.BOSS_DEPTH / 2, 0, 0), b"\x02"
    )
    taper = _PickupPlaneFace(
        context,
        "taper",
        (0, dz / length, -dy / length),
        (0, -section.HALF_Y, -section.WIDE),
        b"\x03",
    )
    opposite_taper = _PickupPlaneFace(
        context,
        "opposite_taper",
        (0, dz / length, dy / length),
        (0, -section.HALF_Y, section.WIDE),
        b"\x04",
    )
    mounting = _PickupPlaneFace(
        context, "mounting", (0, -1, 0), (0, -section.HALF_Y, 0), b"\x06"
    )
    faces = [end, opposite_end, taper, opposite_taper, mounting]
    context["opposite_end"] = opposite_end
    if failure == "missing_taper":
        faces.remove(taper)
    elif failure == "ambiguous_end":
        faces.append(
            _PickupPlaneFace(
                context,
                "split_end",
                (-1, 0, 0),
                (-section.BOSS_DEPTH / 2, 0, 0),
                b"\x05",
            )
        )
    elif failure == "missing_reference":
        end.reference = b""
    for index, face in enumerate(faces):
        face.next_face = faces[index + 1] if index + 1 < len(faces) else None
    body = SimpleNamespace(GetFirstFace=lambda: faces[0])
    selection = SimpleNamespace(
        GetSelectedObjectCount2=lambda _mark: len(context["selected"]),
        GetSelectedObjectType3=lambda _index, _mark: 1 if failure == "edge_type" else 2,
        GetSelectedObject6=lambda index, _mark: context["selected"][index - 1],
    )

    def clear_selection(_all):
        context["selected"] = []

    model = SimpleNamespace(
        GetBodies2=lambda _kind, _hidden: (body,),
        SelectionManager=selection,
        Extension=SimpleNamespace(GetPersistReference3=lambda face: face.reference),
        ClearSelection2=clear_selection,
    )
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda left, right: int(left is right)),
    )
    return adapter, context


def test_pickup_witness_resolves_real_planes_and_records_exact_selected_faces(
    monkeypatch,
):
    adapter, context = _native_pickup_part(monkeypatch)
    events = []
    monkeypatch.setattr(
        support._telemetry, "event", lambda name, **fields: events.append((name, fields))
    )
    support._witness_table_pickup_faces(adapter)
    witnesses = {
        fields["key"]: fields
        for name, fields in events
        if name == "rocker_support.table_pickup_face"
    }
    assert set(witnesses) == {
        "table_pickup_end", "table_pickup_taper", "mounting_face"
    }
    assert witnesses["table_pickup_end"]["persistent_reference"] == "01"
    assert witnesses["table_pickup_taper"]["persistent_reference"] == "03"
    assert witnesses["mounting_face"]["persistent_reference"] == "06"
    for fields in witnesses.values():
        assert (fields["selected_count"], fields["selected_type"]) == (1, 2)
        assert fields["same_selected"] == 1
        assert fields["surface_identity"] == 4001
    assert json.loads(witnesses["table_pickup_taper"]["outward_normal"])[1] > 0
    assert context["selected"] == []


@pytest.mark.parametrize(
    "failure, message",
    (
        ("missing_taper", "matched 0 faces"),
        ("ambiguous_end", "matched 2 faces"),
        ("refused", "face selection failed"),
        ("empty_selection", "count=0"),
        ("multiple", "count=2"),
        ("edge_type", "type=1"),
        ("wrong_face", "same=0"),
        ("missing_reference", "no persistent reference"),
    ),
)
def test_pickup_witness_refuses_missing_ambiguous_or_wrong_native_faces(
    monkeypatch, failure, message
):
    adapter, context = _native_pickup_part(monkeypatch, failure=failure)
    with pytest.raises(RuntimeError, match=message):
        support._witness_table_pickup_faces(adapter)
    assert context["selected"] == []


@pytest.mark.parametrize("failure", (None, "link", "text", "alignment"))
def test_table_pickup_note_requires_native_link_and_current_resolved_process(
    monkeypatch, failure
):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    note = SimpleNamespace(
        PropertyLinkedText='$PRPSHEET:"Table Pickup Process"',
        GetText=lambda: drawing_spec.TABLE_PICKUP_PROCESS.replace("\n", "\r\n"),
        GetTextJustification=lambda: 1,
        GetTextVerticalJustification=lambda: 0,
        GetExtent=lambda: (0.025, 0.031, 0, 0.178, 0.049, 0),
    )
    if failure == "link":
        note.PropertyLinkedText = "MACHINE SOME FACES"
        message = "lost its native link"
    elif failure == "text":
        note.GetText = lambda: "CASTING; USE AS-CAST PICKUP FACES"
        message = "does not resolve this part"
    elif failure == "alignment":
        note.GetTextJustification = lambda: 2
        message = "lost its left/top alignment"
    if failure:
        with pytest.raises(RuntimeError, match=message):
            drawing._assert_table_pickup_note(note)
    else:
        drawing._assert_table_pickup_note(note)


@pytest.mark.parametrize("failure", (None, "wrong_face"))
def test_pickup_native_reads_have_one_batch_phase_and_propagate_error(monkeypatch, failure):
    adapter, _context = _native_pickup_part(monkeypatch, failure=failure)
    active, roots = [], []

    @contextlib.contextmanager
    def capture_span(name, **_fields):
        record = {"name": name, "failed": False}
        if not active:
            roots.append(record)
        active.append(record)
        try:
            yield None
        except BaseException:
            record["failed"] = True
            raise
        finally:
            active.pop()

    monkeypatch.setattr(support._telemetry, "span", capture_span)
    reference = adapter.currentModel.Extension.GetPersistReference3

    def read_reference(face):
        assert active, "native reference read outside a phase"
        return reference(face)

    adapter.currentModel.Extension.GetPersistReference3 = read_reference
    if failure:
        with pytest.raises(RuntimeError, match="same=0"):
            support._witness_table_pickup_faces(adapter)
    else:
        support._witness_table_pickup_faces(adapter)
    assert len(roots) == 1
    assert roots[0]["failed"] is bool(failure)
    assert active == []


class _FootRimEdge:
    def __init__(self, face, y_mm):
        self.face = face
        self.curve = SimpleNamespace(
            IsCircle=lambda: True,
            IsLine=lambda: False,
            CircleParams=(
                face.x_mm / 1000, y_mm / 1000, face.z_mm / 1000,
                0, 1, 0, support.HOLE_DIA / 2000,
            ),
        )

    def GetCurve(self):
        return self.curve

    def GetTwoAdjacentFaces2(self):
        return (self.face,)


class _FootCylinderFace:
    def __init__(self, x_mm, z_mm, reference):
        self.x_mm, self.z_mm = x_mm, z_mm
        self.reference = reference
        self.next_face = None
        self.surface = SimpleNamespace(
            Identity=4002,
            CylinderParams=(
                x_mm / 1000, -section.HALF_Y / 1000, z_mm / 1000,
                0, 1, 0, support.HOLE_DIA / 2000,
            ),
        )
        self.rims = (
            _FootRimEdge(self, -section.HALF_Y),
            _FootRimEdge(self, -section.BIG),
        )

    def GetSurface(self):
        return self.surface

    def GetBox(self):
        radius = support.HOLE_DIA / 2
        return tuple(
            value / 1000
            for value in (
                self.x_mm - radius, -section.HALF_Y, self.z_mm - radius,
                self.x_mm + radius, -section.BIG, self.z_mm + radius,
            )
        )

    def GetNextFace(self):
        return self.next_face

    def GetFeature(self):
        return SimpleNamespace(Name="FootClearanceHoles", GetTypeName2=lambda: "HoleWzd")

    def GetEdges(self):
        return self.rims


class _ReadOnlyDatumPoint:
    """Independent simulated native datum drift; no correction setter exists."""

    @property
    def X(self):
        return -0.0889

    @property
    def Y(self):
        return -0.03176

    @property
    def Z(self):
        return 0.0

    def GetSketch(self):
        identity = (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
        return SimpleNamespace(ModelToSketchTransform=SimpleNamespace(ArrayData=identity))


def _native_table_readback_fixture(monkeypatch, *, fail_cell=False):
    adapter, context = _native_pickup_part(monkeypatch)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(
        _drawing_common, "visible_component_entities",
        lambda view, component, kind: view.GetVisibleEntities2(component, kind),
    )
    body = adapter.currentModel.GetBodies2(0, False)[0]
    face = body.GetFirstFace()
    while face.next_face is not None:
        face = face.next_face
    holes = [
        _FootCylinderFace(x, z, bytes([20 + index]))
        for index, (x, z) in enumerate(support.HOLES)
    ]
    for hole in holes:
        face.next_face = hole
        face = hole
    transform = (
        1, 0, 0, 0, 0, 1, 0, -1, 0, 0.105, 0.075, 0, 0.5, 0, 0, 0
    )
    component = object()
    view = SimpleNamespace(
        ReferencedDocument=adapter.currentModel,
        ModelToViewTransform=SimpleNamespace(ArrayData=transform),
        GetVisibleComponents=lambda: (component,),
        GetVisibleEntities2=lambda selected_component, kind: (
            tuple(hole.rims[0] for hole in holes)
            if selected_component is component and kind == 1 else ()
        ),
    )
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "BottomNative")
    point = _ReadOnlyDatumPoint()
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: (point,),
        GetAttachedEntityTypes=lambda: (11,),
        GetAttachedEntityCount3=lambda: 1,
        IsDangling=lambda: False,
        GetPosition=lambda: (0.06055, 0.05912, 0),
    )
    origin = SimpleNamespace(
        GetAnnotation=lambda: annotation,
        GetAxisPoints2=lambda: (
            0.06055, 0.05912, 0.06555, 0.05912,
            0.06055, 0.05912, 0.06055, 0.06412,
        ),
        XLabel="X", YLabel="Y",
    )
    rows = [
        ["TAG", "X LOC", "Y LOC", "SIZE"],
        ["A1", "28.58", "14.30", "5/16"],
        ["A2", "28.58", "49.22", "5/16"],
        ["A3", "149.22", "14.30", "5/16"],
        ["A4", "149.22", "49.22", "5/16"],
    ]

    def cell_text(row, column, _hidden):
        if fail_cell:
            raise RuntimeError("native cell read failed")
        return rows[row][column]

    table = SimpleNamespace(
        RowCount=5, ColumnCount=4,
        Text2=cell_text,
        DisplayedText2=cell_text,
        HoleTable=SimpleNamespace(
            DatumOrigin=origin,
            GetHoleLocationPrecision=lambda: 2,
            GetHoleLocationUseDocPrecision=lambda: False,
            EnableUpdate=True,
        ),
    )
    axes = tuple(
        SimpleNamespace(
            GetCurve=lambda params=params: SimpleNamespace(
                IsCircle=lambda: False, IsLine=lambda: True, LineParams=params
            ),
            GetTwoAdjacentFaces2=lambda: (),
        )
        for params in (
            (0, -0.0889, -0.03048, 1, 0, 0),
            (-0.08763, -0.0889, 0, 0, 0, 1),
        )
    )
    return adapter, view, table, point, axes, context


def test_native_table_readback_preserves_raw_offset_and_printed_discrepancy(monkeypatch):
    """Hypothetical drift is captured, not evidence of the actual pilot's cause."""
    adapter, view, table, point, axes, context = _native_table_readback_fixture(monkeypatch)
    witness = drawing._witness_support_hole_table(adapter, view, table, point, axes)
    assert witness["created_point"]["xyz_si"] == (-0.0889, -0.03176, 0)
    assert point.Y != drawing.HOLE_TABLE_DATUM_XZ_MM[1] / 1000
    assert witness["origin_attachments"][0]["same_created_point"] == 1
    assert witness["cell_text2"] == witness["cell_displayed_text2"]
    assert [row[2] for row in witness["cell_displayed_text2"][1:]] == [
        "14.30", "49.22", "14.30", "49.22"
    ]
    assert set(witness["native_part_faces"]) == {
        "table_pickup_end", "table_pickup_taper", "mounting_face",
        "foot_0", "foot_1", "foot_2", "foot_3",
    }
    for index, (x, z) in enumerate(support.HOLES):
        rims = witness["native_part_faces"][f"foot_{index}"]["rim_edges"]
        assert len(rims) == 2
        assert rims[0]["circle_parameters_si"][:3] == pytest.approx(
            (x / 1000, -section.HALF_Y / 1000, z / 1000)
        )
    assert len(witness["current_view_foot_rims"]) == 4
    assert witness["view_model_to_view_transform"][9:13] == (
        0.105, 0.075, 0, 0.5
    )
    assert witness["initial_datum_axis_edges"][0]["line_parameters_si"][2] == -0.03048
    assert context["selected"] == []
    assert (point.X, point.Y, point.Z) == (-0.0889, -0.03176, 0)


def test_native_table_readback_error_propagates_in_the_batch_phase(monkeypatch):
    adapter, view, table, point, axes, _context = _native_table_readback_fixture(
        monkeypatch, fail_cell=True
    )
    active, roots = [], []

    @contextlib.contextmanager
    def capture_span(name, **_fields):
        record = {"name": name, "failed": False}
        if not active:
            roots.append(record)
        active.append(record)
        try:
            yield None
        except BaseException:
            record["failed"] = True
            raise
        finally:
            active.pop()

    monkeypatch.setattr(drawing._telemetry, "span", capture_span)
    with pytest.raises(RuntimeError, match="native cell read failed"):
        drawing._witness_support_hole_table(adapter, view, table, point, axes)
    assert len(roots) == 1
    assert roots[0]["failed"] is True
    assert active == []


def test_native_hole_table_covers_every_foot_hole() -> None:
    expected_holes = {
        (60.32, 17.46),
        (-60.32, 17.46),
        (60.32, -17.46),
        (-60.32, -17.46),
    }
    assert set(support.HOLES) == expected_holes
    assert drawing.HOLE_TABLE_DATUM_XZ_MM == (
        -section.BOSS_DEPTH / 2.0,
        -support.WIDE,
    )
    x_centres = {x for x, _ in expected_holes}
    y_centres = {y for _, y in expected_holes}
    assert round(max(x_centres) - min(x_centres), 2) == 120.64
    assert round(max(y_centres) - min(y_centres), 2) == 34.92
    expected_locations = {
        (
            round(x + section.BOSS_DEPTH / 2.0, 2),
            round(z + support.WIDE, 2),
        )
        for x, z in expected_holes
    }
    assert set(drawing.EXPECTED_HOLE_TABLE_LOCATIONS_MM) == expected_locations
    xs = {x for x, _ in expected_locations}
    ys = {y for _, y in expected_locations}
    assert round(min(xs) + max(xs), 2) == section.BOSS_DEPTH
    assert round(min(ys) + max(ys), 2) == 2.0 * support.WIDE
    points = {drawing._bottom_sheet_xy(hole) for hole in expected_holes}
    assert len(points) == 4
    half_w = section.BOSS_DEPTH / 2.0 * drawing.VIEW_SCALE / 1000.0
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
    import fr_harmonic_base_fasteners as base

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
    # section spec, so a window or rail edit in the COM builder re-keys none
    # of them; the foot clearances ride the placement spec with the hold-down
    # pattern they are drilled on.
    for name in ("WIDE", "NARROW", "HALF_Y", "BIG", "FOOT_THICKNESS"):
        assert getattr(support, name) is getattr(section, name)
    for name in ("HOLE_SPEC", "HOLE_DIA"):
        assert getattr(support, name) is getattr(placement, name)
    assert drawing_spec.HALF_Y is section.HALF_Y
    assert frame.LAG_FOOT_THICKNESS is section.FOOT_THICKNESS
    assert seats.FOOT_THICKNESS is section.FOOT_THICKNESS
    # The base seats key on the foot: it stays exactly the source's 6.35.
    assert section.FOOT_THICKNESS == pytest.approx(6.35)
    assert section.BIG == pytest.approx(82.55)


def test_deeper_rail_lowers_only_the_window_top() -> None:
    assert seats.RAIL_DEPTH == 22.7
    assert seats.WINDOW_TOP_Y == pytest.approx(66.2)
    assert seats.WINDOW_BOTTOM_Y == pytest.approx(-support.BIG)
    assert seats.WINDOW_HEIGHT == pytest.approx(148.75)
    # 165.1 wide by 148.75 tall: the print no longer calls it square.
    assert 2.0 * support.BIG - seats.WINDOW_HEIGHT > 10.0
    assert "SQ" not in drawing.DIMENSION_CALLOUTS["WinWidth"]
    # The cavity's chamfered top rim stays a web edge under the rail.
    assert seats.WINDOW_TOP_Y - support.CAV == pytest.approx(2.7)


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
    import ch_pivot_bracket_spec as bracket
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
    # MHA-VN-032 #8-32 x 3/4 through MHA-CH-008's 6.0 (.XX) foot.
    assert seats.SCREW_REACH_MIN == pytest.approx(19.05 - 0.76 - 6.508)
    assert seats.SCREW_REACH_MAX == pytest.approx(19.05 - 5.492)
    assert seats.ENGAGEMENT_MIN >= 1.5 * seats.SCREW_MAJOR_DIA
    assert seats.SEAT_THREAD_DEPTH - 0.8 >= seats.SCREW_REACH_MAX + 0.25
    assert seats.SEAT_DRILL_DEPTH - 0.8 >= seats.SEAT_THREAD_DEPTH + 0.8 + 2 * 25.4 / 32
    assert seats.SEAT_DRILL_BOTTOM_MAX + 0.25 <= seats.RAIL_DEPTH - 0.8
    assert seats.RAIL_WALL >= 2.0


def test_rail_depth_is_a_model_dimension_on_the_section_plane() -> None:
    """Codex #936 PRRT_kwDOPHDy386mTMXw: the rail depth the seat stack's
    worst case rests on is a marked WallProfile dimension (the Right-plane
    trapezoid Section A-A is parallel to), carried at the layout's .X places
    by the part and only asserted by the sheet."""
    assert "RailDepth" in support.DRAWING_DIMENSIONS["WallProfile"]
    assert drawing.RIGHT_KEEP["RailDepth"] == drawing.RAIL_TEXT_XY
    assert seats.RAIL_DEPTH_PLACES == 1
    assert round(seats.RAIL_DEPTH, seats.RAIL_DEPTH_PLACES) == seats.RAIL_DEPTH
    # The construction line it measures to spans the wall at the window top.
    assert 0.0 < support._wall_half_z_at(seats.WINDOW_TOP_Y) < support.WIDE
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SetPrecision3(DIMENSION_PRECISION[\"RailDepth\"]" not in source
    assert 'label="section rail depth"' not in source


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
    sheet-made ones (web, foot) set their own after the import. Every
    DIMENSION_PRECISION name goes through exactly one of the two; the
    part-owned rail depth goes through neither."""
    import ast

    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    bulk = drawing.imported_precision()
    assert set(bulk) == kept & set(drawing.DIMENSION_PRECISION)
    assert not set(bulk) & set(drawing.MODEL_OWNED_PRECISION)
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    own = {
        node.slice.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "DIMENSION_PRECISION"
        and isinstance(node.slice, ast.Constant)
    }
    assert own == {"WebThickness", "FootThickness"}
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


# Sheet-default note text as rendered by r743-rocker-fix3 (leaf
# 20260926T112244Z-1-a884759d): "TRANSFER FROM MHA-CH-008" spanned 57.6 mm for 21
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
    front_right = drawing.FRONT_CENTER[0] + section.BOSS_DEPTH / 2 * scale
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
    front_right = drawing.FRONT_CENTER[0] + section.BOSS_DEPTH / 2 * scale
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
    moves = []
    note = SimpleNamespace(GetText=lambda: text)

    def set_position(new_x, new_y, new_z):
        moves.append((new_x, new_y, new_z))
        state["position"] = (new_x, new_y, new_z)
        return True

    return SimpleNamespace(
        GetType=lambda: kind,
        GetName=lambda: text,
        GetSpecificAnnotation=lambda: note,
        GetPosition=lambda: state["position"],
        SetPosition2=set_position,
        moves=moves,
    )


def test_bottom_hole_tags_keep_right_mirrors_and_clear_lower_hidden_line(monkeypatch):
    """Keep the established right mirrors; only A1/A3 move down from the pilot."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    tags = {
        name: _fake_note_annotation(name, x, y)
        for name, x, y in (
            ("A1", 0.0790716, 0.0705061),
            ("A2", 0.0790716, 0.0879661),
            ("A3", 0.1393916, 0.0705061),
            ("A4", 0.1393916, 0.0879661),
        )
    }
    dimension = _fake_note_annotation("A4", 0.2, 0.1, kind=1)
    view = SimpleNamespace(GetAnnotations=lambda: (*tags.values(), dimension))
    moved = drawing._position_bottom_hole_tags(view)
    assert set(moved) == {"A1", "A3", "A4"}
    assert tags["A1"].GetPosition() == pytest.approx((0.0790716, 0.0675061, 0))
    assert tags["A2"].GetPosition() == pytest.approx((0.0790716, 0.0879661, 0))
    assert tags["A3"].GetPosition() == pytest.approx((0.1243916, 0.0675061, 0))
    assert tags["A4"].GetPosition() == pytest.approx((0.1243916, 0.0879661, 0))
    assert tags["A2"].moves == []
    assert dimension.moves == []

    # Native pilot 829e6f8e5: the unchanged hidden line is y70.0085 mm;
    # both lower tag extents topped at70.5976 mm relative to y70.5061.
    # Those old boxes cross it; translated boxes must leave >2 mm of air.
    hidden_line_y, old_box_top, old_anchor_y = 0.0700085, 0.0705976, 0.0705061
    assert 0.0663084 < hidden_line_y < old_box_top
    for name in ("A1", "A3"):
        new_top = old_box_top + tags[name].GetPosition()[1] - old_anchor_y
        assert hidden_line_y - new_top > 0.002

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


def test_bottom_hole_tag_positioner_fails_loud(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    only_a3 = SimpleNamespace(
        GetAnnotations=lambda: (_fake_note_annotation("A3", 0.1397, 0.0661),)
    )
    with pytest.raises(RuntimeError, match="A4"):
        drawing._position_bottom_hole_tags(only_a3)
    left_a4 = SimpleNamespace(
        GetAnnotations=lambda: (_fake_note_annotation("A4", 0.0796, 0.0878),)
    )
    with pytest.raises(RuntimeError, match="not at the right end"):
        drawing._position_bottom_hole_tags(left_a4)


@pytest.mark.parametrize("failure", ("duplicate", "wrong_row", "refused", "snapped"))
def test_bottom_hole_tags_reject_ambiguous_or_unsettled_positions(monkeypatch, failure):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    tags = [
        _fake_note_annotation(name, x, y)
        for name, x, y in (
            ("A1", 0.0790716, 0.0705061),
            ("A2", 0.0790716, 0.0879661),
            ("A3", 0.1393916, 0.0705061),
            ("A4", 0.1393916, 0.0879661),
        )
    ]
    if failure == "duplicate":
        tags.append(_fake_note_annotation("A1", 0.0790716, 0.0705061))
        message = "duplicate bottom-view hole tag"
    elif failure == "wrong_row":
        tags[0] = _fake_note_annotation("A1", 0.0790716, 0.0879661)
        message = "not in the lower row"
    elif failure == "refused":
        tags[0].SetPosition2 = lambda *_args: False
        message = "failed to move hole tag"
    else:
        tags[0].SetPosition2 = lambda *_args: True
        message = "landed at .* not"
    with pytest.raises(RuntimeError, match=message):
        drawing._position_bottom_hole_tags(
            SimpleNamespace(GetAnnotations=lambda: tags)
        )


class _NativeCalloutLength:
    """A native length token with an independently retained model value."""

    def __init__(self, name, value_mm, *, persists=True):
        self._oleobj_ = SimpleNamespace(VariableName=name)
        self.value_mm = value_mm
        self._precision = 2
        self.persists = persists

    @property
    def Precision(self):
        return self._precision

    @Precision.setter
    def Precision(self, value):
        if self.persists:
            self._precision = value


def _native_seat_callout(monkeypatch, *, depths_persist=True):
    # Bind only the native seams; exercise the existing precision helper itself.
    monkeypatch.setitem(
        sys.modules,
        "win32com.client.dynamic",
        SimpleNamespace(Dispatch=lambda raw: raw),
    )
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda obj, _name: obj)
    lengths = [
        _NativeCalloutLength("hw-tapdrldia", 3.454),
        _NativeCalloutLength("hw-tapdrldepth", 18.0, persists=depths_persist),
        _NativeCalloutLength("hw-threaddepth", 14.7, persists=depths_persist),
    ]
    thread = SimpleNamespace(
        _oleobj_=SimpleNamespace(VariableName="hw-threadsize"),
        native_text="native thread designation",
    )
    variables = [*lengths, thread]
    return SimpleNamespace(GetHoleCalloutVariables=lambda: variables), lengths, thread


def test_native_seat_depth_precision_preserves_diameter_thread_and_model_values(
    monkeypatch,
):
    display, lengths, thread = _native_seat_callout(monkeypatch)
    values_before = [length.value_mm for length in lengths]
    drawing.set_hole_callout_precision(
        display, drawing.SEAT_CALLOUT_PRECISION, label="rocker-bracket transfer seats"
    )
    assert [length.Precision for length in lengths] == [2, 1, 1]
    assert [length.value_mm for length in lengths] == values_before
    assert thread.native_text == "native thread designation"
    assert [
        f"{length.value_mm:.{length.Precision}f}" for length in lengths
    ] == ["3.45", "18.0", "14.7"]


@pytest.mark.parametrize("failure", ("missing_thread_depth", "ignored_precision"))
def test_native_seat_depth_precision_refuses_missing_or_ignored_variables(
    monkeypatch, failure
):
    display, lengths, thread = _native_seat_callout(
        monkeypatch, depths_persist=failure != "ignored_precision"
    )
    if failure == "missing_thread_depth":
        display.GetHoleCalloutVariables = lambda: (*lengths[:2], thread)
        message = "no native variables.*hw-threaddepth"
    else:
        message = "hw-tapdrldepth precision did not persist"
    with pytest.raises(RuntimeError, match=message):
        drawing.set_hole_callout_precision(
            display, drawing.SEAT_CALLOUT_PRECISION, label="rocker-bracket transfer seats"
        )


def _native_section_caption(monkeypatch):
    monkeypatch.setattr(_section_axis, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(_section_axis, "rebuild_drawing", lambda *_args, **_kwargs: None)
    annotation = _fake_note_annotation("SECTION A-A", 0.205, 0.128485)
    note = SimpleNamespace(
        PropertyLinkedText="SECTION <VLLABEL>",
        GetAnnotation=lambda: annotation,
        GetText=lambda: "SECTION A-A",
        font_sizes=(0.00635, 0.0035),
    )
    return SimpleNamespace(GetNotes=lambda: (note,)), note, annotation


def test_section_caption_moves_as_native_linked_text_without_font_change(monkeypatch):
    view, note, annotation = _native_section_caption(monkeypatch)
    drawing.position_section_caption(
        object(), view, drawing.SECTION_CAPTION_XY, label="rocker-arm support"
    )
    assert annotation.GetPosition() == pytest.approx((0.205, 0.1255, 0))
    assert note.PropertyLinkedText == "SECTION <VLLABEL>"
    assert note.font_sizes == (0.00635, 0.0035)

    # Translate the saved native extent, not the padded VIEW B GetOutline.
    # Neither assertion is a claim about the still-unrendered candidate.
    delta_y = annotation.GetPosition()[1] - 0.128485
    extent_bottom, extent_top = 0.1206373 + delta_y, 0.1287389 + delta_y
    foot_span_arrow_low = 0.1298
    crop_ink_top = (
        drawing.VIEW_B_CENTER[1]
        + drawing.VIEW_B_CROP_HALF_Z_MM * drawing.VIEW_SCALE / 1000
    )
    assert foot_span_arrow_low - extent_top > 0.002
    assert extent_bottom - crop_ink_top > 0.003


@pytest.mark.parametrize(
    "failure", ("unlinked", "ambiguous", "refused", "snapped", "lost_native_fields")
)
def test_section_caption_refuses_ambiguous_or_unsettled_native_label(
    monkeypatch, failure
):
    view, note, annotation = _native_section_caption(monkeypatch)
    if failure == "unlinked":
        note.PropertyLinkedText = "SECTION A-A"
        message = "expected one native linked"
    elif failure == "ambiguous":
        second_note = SimpleNamespace(PropertyLinkedText="SECTION <VLLABEL>")
        view.GetNotes = lambda: (note, second_note)
        message = "expected one native linked"
    elif failure == "refused":
        annotation.SetPosition2 = lambda *_args: False
        message = "failed to position"
    elif failure == "snapped":
        annotation.SetPosition2 = lambda *_args: True
        message = "position did not persist"
    else:
        def lose_native_fields(*_args, **_kwargs):
            note.PropertyLinkedText = "SECTION A-A"

        monkeypatch.setattr(_section_axis, "rebuild_drawing", lose_native_fields)
        message = "lost its native fields"
    with pytest.raises(RuntimeError, match=message):
        drawing.position_section_caption(
            object(), view, drawing.SECTION_CAPTION_XY, label="rocker-arm support"
        )


class _DocumentHoleMarkPreference:
    def __init__(self, *, persists=True):
        self.enabled = True
        self.persists = persists
        self.writes = []

    def GetUserPreferenceToggle(self, preference, option):
        assert (preference, option) == (101, 0)  # fixture ID, not a native constant
        return self.enabled

    def SetUserPreferenceToggle(self, preference, option, value):
        assert (preference, option) == (101, 0)
        self.writes.append(value)
        if self.persists:
            self.enabled = value
        return self.enabled  # OFF is false, not an operation failure.


@pytest.mark.parametrize("persists", (True, False))
def test_automatic_hole_marks_change_only_document_preference_with_readback(
    monkeypatch, persists
):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "_preference_id", lambda _adapter, _name: 101)
    extension = _DocumentHoleMarkPreference(persists=persists)
    model = SimpleNamespace(Extension=extension)
    # No application setter is available: a document-only operation must not need it.
    adapter = SimpleNamespace(swApp=object())
    if persists:
        drawing._disable_automatic_hole_center_marks(adapter, model)
        assert extension.enabled is False
    else:
        with pytest.raises(RuntimeError, match="remain enabled"):
            drawing._disable_automatic_hole_center_marks(adapter, model)
        assert extension.enabled is True
    assert extension.writes == [False]


def test_automatic_hole_marks_refuse_unresolved_native_preference(monkeypatch):
    monkeypatch.setattr(drawing, "_preference_id", lambda _adapter, _name: None)
    with pytest.raises(RuntimeError, match="cannot resolve native drawing preference"):
        drawing._disable_automatic_hole_center_marks(object(), object())


def test_center_mark_census_reads_annotations_and_retains_duplicate_locations(
    monkeypatch,
):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    marks = [
        _fake_note_annotation("CenterMark347", 0.0735367, 0.0647781, kind=13),
        _fake_note_annotation("CenterMark352", 0.0735367, 0.0647781, kind=13),
    ]
    note = _fake_note_annotation("A1", 0.0790716, 0.0705061)
    centerline = _fake_note_annotation("CenterLine", 0.08, 0.07, kind=15)
    view = SimpleNamespace(GetAnnotations=lambda: (*marks, note, centerline))
    census = drawing._center_mark_census(view)
    assert census == [
        {"name": "CenterMark347", "position": (0.0735367, 0.0647781, 0)},
        {"name": "CenterMark352", "position": (0.0735367, 0.0647781, 0)},
    ]
    # These are two actual annotation records, not a geometry-deduplicated count.
    assert len(census) == 2


def test_seats_print_as_one_native_callout_with_only_the_transfer_as_text() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRSOJ): the seat note retyped BracketSeats'
    thread and depths, so a model change would leave the print stale. The
    native callout reads count, thread and both depths from the Hole Wizard
    feature; the transfer instruction is the only text, ending in a line
    break so the native size starts its own row (13be2ca03)."""
    bracket = _config.parts("ch-pivot-bracket")["number"]
    assert drawing.SEAT_CALLOUT_PROCESS == f"TRANSFER FROM {bracket}\nAT ASSEMBLY;\n"
    assert not hasattr(drawing, "SEAT_NOTE")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for retyped in ("UNC-2B", " DEEP", "SEAT_THREAD_DEPTH", "SEAT_DRILL_DEPTH"):
        assert retyped not in source, retyped
    assert "process=SEAT_CALLOUT_PROCESS" in source
    assert drawing.SEAT_CALLOUT_X_MM == max(seats.SEAT_LOCAL_X)


# Use the saved pilot's native caption extent relative to its native anchor,
# translated to the recipe's current target. This is a layout prediction,
# not proof of the next rendered caption or the padded view outline.
SECTION_CAPTION_BOTTOM = drawing.SECTION_CAPTION_XY[1] + (0.1206373 - 0.128485)
# Other ink landmarks below were measured on the fix4 render
# (leaf20260926T141000Z-1-f32d205b), in sheet metres.
HOLE_TABLE_BOTTOM = 0.0967
TITLE_BLOCK_TOP, TITLE_BLOCK_LEFT = 0.0649, 0.2183
DEPTH_DIM_LINE_Y = 0.2549  # the 177.8 above the front view


def test_pickup_process_note_has_space_below_the_uncropped_bottom_view():
    """Left/top-aligned standard text has a lane; actual saved ink remains a gate."""
    x, y = drawing.TABLE_PICKUP_NOTE_XY
    lines = drawing_spec.TABLE_PICKUP_PROCESS.splitlines()
    assert 1 < len(lines) <= 4
    right = x + max(map(len, lines)) * NOTE_CHAR_WIDTH
    bottom = y - len(lines) * NOTE_LINE_PITCH
    bottom_view_low = (
        drawing.BOTTOM_CENTER[1] - section.WIDE * drawing.VIEW_SCALE / 1000
    )
    assert x > 0.010
    assert right < TITLE_BLOCK_LEFT - 0.003
    assert bottom > 0.010
    assert y < bottom_view_low - 0.003


def test_view_b_is_a_cropped_rail_strip_in_the_band_below_the_section() -> None:
    """Main's ruling on Codex PRRT_kwDOPHDy386mRSOJ: the seats get a visible
    circle to carry the callout, in a relocated partial top view (VIEW B) of
    the rail strip, below Section A-A and right of the bottom view."""
    scale = drawing.VIEW_SCALE / 1000
    bottom_right = drawing.BOTTOM_CENTER[0] + section.BOSS_DEPTH / 2 * scale
    x, y = drawing.VIEW_B_CENTER
    half_len = section.BOSS_DEPTH / 2 * scale
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
    assert x - width > drawing.BOTTOM_CENTER[0] + section.BOSS_DEPTH / 2 * scale
    assert x + width < 0.415  # the right border


def test_view_b_arrow_looks_down_on_the_rail_from_above_the_front_view() -> None:
    scale = drawing.VIEW_SCALE / 1000
    text_xy, tip_xy = drawing.VIEW_B_ARROW
    front_top = drawing.FRONT_CENTER[1] + support.HALF_Y * scale
    assert tip_xy[1] == pytest.approx(front_top)
    assert abs(tip_xy[0] - drawing.FRONT_CENTER[0]) < section.BOSS_DEPTH / 2 * scale
    # The letter stands square above its tip, under the 177.8 dimension line.
    assert text_xy[1] - drawing.VIEW_LETTER_HEIGHT > tip_xy[1] + 0.004
    assert text_xy[1] < DEPTH_DIM_LINE_Y - 0.002
    assert abs(text_xy[0] + drawing.VIEW_LETTER_HEIGHT * 0.36 - tip_xy[0]) < 0.001
    # Clear of the section's own A arrow on the centreline.
    assert abs(tip_xy[0] - drawing.FRONT_CENTER[0]) > 0.015


def _circle_edge(
    x_mm: float,
    y_mm: float,
    radius_mm: float,
    *,
    z_mm: float = 0.0,
    axis: tuple[float, float, float] = (0.0, 1.0, 0.0),
    feature_name: str = "BracketSeats",
    feature_type: str = "HoleWzd",
    native_identity=None,
):
    curve = SimpleNamespace(
        IsLine=lambda: False,
        IsCircle=lambda: True,
        CircleParams=(x_mm / 1000, y_mm / 1000, z_mm / 1000, *axis, radius_mm / 1000),
    )
    owners = tuple(
        SimpleNamespace(
            GetFeature=lambda name=name, kind=kind: SimpleNamespace(
                Name=name, GetTypeName2=lambda: kind
            )
        )
        for name, kind in ((feature_name, feature_type), ("Wall", "Extrusion"))
    )
    return SimpleNamespace(
        GetCurve=lambda: curve,
        GetTwoAdjacentFaces2=lambda: owners,
        native_identity=object() if native_identity is None else native_identity,
    )


def _patch_seat_rims(monkeypatch, part_entry, visible_edges):
    """Expose independent part topology and current cropped-view topology.

    Binding and the component bridge are offline seams; the real shared scan,
    full-circle filtering and native-identity uniqueness logic still run.
    """
    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    face = SimpleNamespace(
        GetEdges=lambda: (
            _circle_edge(
                drawing.SEAT_CALLOUT_X_MM,
                support.HALF_Y - seats.SEAT_DRILL_DEPTH,
                radius,
            ),
            part_entry,
            SimpleNamespace(GetCurve=lambda: SimpleNamespace(IsCircle=lambda: False)),
        )
    )
    requested = {}

    def resolve(model, requests):
        requested.update(requests)
        return {"seat": face}

    component = object()
    view = SimpleNamespace(
        ReferencedDocument=object(),
        GetVisibleComponents=lambda: (component,),
        GetVisibleEntities2=lambda selected_component, kind: (
            visible_edges if selected_component is component and kind == 1 else ()
        ),
    )
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(
            IsSame=lambda first, second: int(
                getattr(first, "native_identity", first)
                is getattr(second, "native_identity", second)
            )
        )
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "_resolve_faces", resolve)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "VIEW B")
    monkeypatch.setattr(
        _drawing_common,
        "visible_component_entities",
        lambda native_view, native_component, kind: native_view.GetVisibleEntities2(
            native_component, kind
        ),
    )
    events = []
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **fields: events.append((name, fields))
    )
    return adapter, view, requested, events


def test_seat_entry_edge_is_the_unique_visible_east_rim_after_the_crop(monkeypatch) -> None:
    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    east = drawing.SEAT_CALLOUT_X_MM
    entry = _circle_edge(east, support.HALF_Y, radius)
    other_station = sorted(set(seats.SEAT_LOCAL_X))[-2]
    others = (
        _circle_edge(other_station, support.HALF_Y, radius),
        _circle_edge(east, support.HALF_Y - seats.SEAT_DRILL_DEPTH, radius),
        _circle_edge(east, support.HALF_Y, radius, z_mm=0.5),
        _circle_edge(east, support.HALF_Y, radius, axis=(0.0, 0.0, 1.0)),
        _circle_edge(east, support.HALF_Y, radius + 0.1),
    )
    adapter, view, requested, events = _patch_seat_rims(
        monkeypatch, entry, (*others, entry)
    )
    assert drawing._seat_entry_edge(adapter, view) is entry
    (spec,) = requested.values()
    assert spec.diameter_mm == pytest.approx(2 * radius)
    assert spec.contains_x_mm == east
    name, witness = events[-1]
    assert name == "drawing.rocker_support_seat_rim"
    assert witness["part_visible_is_same"] == 1
    assert json.loads(witness["visible_circle_mm"]) == pytest.approx(
        [east, support.HALF_Y, 0.0, radius]
    )
    assert json.loads(witness["visible_circle_axis"]) == [0.0, 1.0, 0.0]


def test_seat_entry_edge_uses_current_view_identity_not_same_curve_part_identity(
    monkeypatch,
) -> None:
    """Model a part-only handle separately from the current view's native edge.

    This is a consumer visibility/identity regression, not a claimed native
    explanation of worker15's swap: that log did not describe the attached edge.
    """
    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    part_entry = _circle_edge(drawing.SEAT_CALLOUT_X_MM, support.HALF_Y, radius)
    visible_entry = _circle_edge(drawing.SEAT_CALLOUT_X_MM, support.HALF_Y, radius)
    adapter, view, _requested, events = _patch_seat_rims(
        monkeypatch, part_entry, (visible_entry,)
    )
    assert drawing._seat_entry_edge(adapter, view) is visible_entry
    _name, witness = events[-1]
    assert witness["part_visible_is_same"] == 0
    assert witness["part_circle_mm"] == witness["visible_circle_mm"]
    assert witness["part_adjacent_features"] == witness["visible_adjacent_features"]


@pytest.mark.parametrize("wrong", ("missing", "station", "depth", "z", "axis", "radius"))
def test_seat_entry_edge_refuses_part_only_rim_when_the_crop_has_no_exact_rim(
    monkeypatch, wrong
) -> None:
    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    east = drawing.SEAT_CALLOUT_X_MM
    part_entry = _circle_edge(east, support.HALF_Y, radius)
    candidates = {
        "missing": (),
        "station": (_circle_edge(sorted(set(seats.SEAT_LOCAL_X))[-2], support.HALF_Y, radius),),
        "depth": (_circle_edge(east, support.HALF_Y - seats.SEAT_DRILL_DEPTH, radius),),
        "z": (_circle_edge(east, support.HALF_Y, radius, z_mm=0.5),),
        "axis": (_circle_edge(east, support.HALF_Y, radius, axis=(0.0, 0.0, 1.0)),),
        "radius": (_circle_edge(east, support.HALF_Y, radius + 0.1),),
    }
    adapter, view, _requested, _events = _patch_seat_rims(
        monkeypatch, part_entry, candidates[wrong]
    )
    with pytest.raises(RuntimeError, match="no circular edge|no visible circle"):
        drawing._seat_entry_edge(adapter, view)


def test_seat_entry_edge_refuses_distinct_native_rims_on_the_same_curve(monkeypatch) -> None:
    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    entry = _circle_edge(drawing.SEAT_CALLOUT_X_MM, support.HALF_Y, radius)
    twin = _circle_edge(drawing.SEAT_CALLOUT_X_MM, support.HALF_Y, radius)
    adapter, view, _requested, _events = _patch_seat_rims(
        monkeypatch, entry, (entry, twin)
    )
    with pytest.raises(RuntimeError, match="ambiguous visible circle"):
        drawing._seat_entry_edge(adapter, view)


def test_seat_entry_edge_accepts_duplicate_wrappers_only_for_one_native_rim(
    monkeypatch,
) -> None:
    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    entry = _circle_edge(drawing.SEAT_CALLOUT_X_MM, support.HALF_Y, radius)
    wrapper = _circle_edge(
        drawing.SEAT_CALLOUT_X_MM,
        support.HALF_Y,
        radius,
        native_identity=entry.native_identity,
    )
    adapter, view, _requested, _events = _patch_seat_rims(
        monkeypatch, entry, (entry, wrapper)
    )
    assert drawing._seat_entry_edge(adapter, view) is entry


@pytest.mark.parametrize(
    ("feature_name", "feature_type"),
    (("BracketSeats", "Cut"), ("OtherSeats", "HoleWzd")),
)
def test_seat_entry_edge_refuses_same_curve_without_bracket_seat_ownership(
    monkeypatch, feature_name, feature_type
) -> None:
    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    part_entry = _circle_edge(drawing.SEAT_CALLOUT_X_MM, support.HALF_Y, radius)
    other = _circle_edge(
        drawing.SEAT_CALLOUT_X_MM,
        support.HALF_Y,
        radius,
        feature_name=feature_name,
        feature_type=feature_type,
    )
    adapter, view, _requested, _events = _patch_seat_rims(
        monkeypatch, part_entry, (other,)
    )
    with pytest.raises(RuntimeError, match="not owned by BracketSeats"):
        drawing._seat_entry_edge(adapter, view)


def test_current_visible_seat_target_still_refuses_one_live_wrong_edge(monkeypatch) -> None:
    """Preserve worker15's REAL failure family: one EDGE, no dangling flag.

    The attachment is independently supplied as the neighbouring seat; it is
    not an echo of the selector or a fabricated native success observation.
    """
    radius = blind_cut_dia_mm(seats.SEAT_SPEC) / 2
    entry = _circle_edge(drawing.SEAT_CALLOUT_X_MM, support.HALF_Y, radius)
    neighbour = _circle_edge(sorted(set(seats.SEAT_LOCAL_X))[-2], support.HALF_Y, radius)
    adapter, view, _requested, _events = _patch_seat_rims(
        monkeypatch, entry, (entry, neighbour)
    )
    target = drawing._seat_entry_edge(adapter, view)
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: (neighbour,),
        GetAttachedEntityCount3=lambda: 1,
        GetAttachedEntityTypes=lambda: (1,),
        GetLeaderCount=lambda: 0,
        IsDangling=lambda: False,
    )
    with pytest.raises(RuntimeError, match="same_entity=False"):
        _drawing_common._assert_attached_to(
            adapter,
            annotation,
            target,
            entity_type="EDGE",
            what="native hole callout",
            label="rocker-bracket transfer seats",
            expected_leaders=None,
        )


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
            section.BOSS_DEPTH / 2 * drawing.VIEW_SCALE / 1000
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
            self.origin[0] + xyz[0] / (section.BOSS_DEPTH / 2000) * self.end_run,
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
    assert min(x1, x2) < cx - section.BOSS_DEPTH / 2 * scale
    assert max(x1, x2) > cx + section.BOSS_DEPTH / 2 * scale
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
        (drawing.VIEW_B_CENTER, section.BOSS_DEPTH / 2 / 1000),
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
