"""Offline contracts for MHA-CH-13-TL-VN-50, the strap fixture's edge clamp.

The Mitee-Bite Pitbull 26000 and its supplied #4-40 x 3/8 SHCS: registry and
catalogue identity, the spec's vendor-model geometry and frame, the recipe's
recorded sketches (no SolidWorks), the specification-control sheet's
catalogue references, the plan's agreement and the adapter-call census.
"""

from __future__ import annotations

import ast
import contextlib
import math
import tomllib
from pathlib import Path

import pytest

import _config
import build_ch_rocker_strap_tl_vn_edge_clamp as part
import ch_rocker_strap_tl_vn_edge_clamp_spec as spec
import draw_ch_rocker_strap_tl_vn_edge_clamp as drawing
import hardware_schedule
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _machinist_review_mode import MachinistReviewMode, mode_for_drawing
from _purchased_fastener_drawing import _supplier_data_lines, check_item
from _supplier_screw_layout import supplier_screw_lane_plan
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_26000 as recipe

STEM = "ch-rocker-strap-tl-vn-edge-clamp"
NUMBER = "MHA-CH-13-TL-VN-50"
IN = 25.4
SCRIPTS = Path(__file__).resolve().parent
PLAN = SCRIPTS.parents[1] / "cad" / "process" / "ch_rocker_strap" / "plan.toml"


def test_registry_catalogue_and_recipe_name_the_mitee_bite_26000() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("26000",)
    assert stock.supplier == row["supplier"] == "Mitee-Bite Products"
    assert stock.stock_name == row["stock_name"]
    assert part.MATERIAL == stock.material == "Alloy Steel"
    assert (
        row["material"] == "Tool Steel"
    )  # PITBULL-INST-0426: "Tool Steel, Knife Edge"
    assert row["number"] == NUMBER
    assert row["process"] == "purchased"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 4
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_26000
    assert metadata.threaded is False
    for other, entry in FASTENERS.items():
        if other != STEM:
            assert spec.SKU not in entry.skus, other


def test_tier_two_row_and_its_own_specification_control_sheet() -> None:
    tier = hardware_schedule.TIERS[STEM]
    assert tier["tier"] == 2 and tier["why"]
    assert STEM not in hardware_schedule.SCHEDULE
    sheet = DRAWINGS_BY_NAME["ch_rocker_strap_tl_vn_edge_clamp"]
    assert sheet.part == "ch_rocker_strap_tl_vn_edge_clamp"
    assert sheet.source_kind == "part"
    assert drawing.SPEC is sheet
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.LEARN
    assert mode_for_drawing(Path(drawing.__file__)) is MachinistReviewMode.LEARN


def test_catalogue_facts() -> None:
    """Mitee-Bite PITBULL-INST-0426, row 26000, read 2026-11-17."""
    assert (
        spec.CATALOG_A_IN,
        spec.CATALOG_B_IN,
        spec.CATALOG_C_IN,
        spec.CATALOG_D_IN,
        spec.CATALOG_F_IN,
    ) == (0.150, 0.140, 0.375, 0.075, 0.375)
    assert spec.MAX_TORQUE_FT_LB == 1.30
    assert spec.HOLDING_FORCE_LB == 650
    assert spec.THROW_IN == 0.0075
    assert spec.PER_PACKAGE == 8
    assert spec.O_RING_SKU == "26008"
    assert spec.SCREW_THREAD == "#4-40 UNC x 3/8"


def test_frame_matches_the_fixture_contract() -> None:
    assert spec.KNIFE_Y == pytest.approx(3.810)
    assert spec.HEEL_Y == pytest.approx(-5.715)
    assert spec.WIDTH == pytest.approx(9.525)
    assert spec.HEEL_FACE_MID_Z == pytest.approx(1.524)
    assert spec.KNIFE_TIP[0] == pytest.approx(spec.KNIFE_Y)
    ys = [p[0] for seg in spec.PROFILE for p in seg[1:] if seg[0] == "line"]
    zs = [p[1] for seg in spec.PROFILE for p in seg[1:] if seg[0] == "line"]
    assert max(ys) == pytest.approx(spec.KNIFE_Y)
    assert min(zs) > 0.0  # the lowest point is the heel circle's bottom
    assert spec.HEEL_CENTER[1] - spec.HEEL_R == pytest.approx(0.0)
    assert spec.HEEL_CENTER[0] - spec.HEEL_R == pytest.approx(spec.HEEL_Y)
    assert spec.TOP_Z == pytest.approx(5.405147)
    # Seated in a .140 pocket (TL-01), the top and the knife stand above Z0:
    assert spec.TOP_Z - spec.B_REFERENCE == pytest.approx(1.849, abs=1e-3)
    assert spec.KNIFE_TIP[1] - spec.B_REFERENCE == pytest.approx(1.524, abs=1e-3)
    assert spec.SCREW_HEAD_TOP_Z < spec.TOP_Z
    assert spec.SCREW_TIP_DEPTH == pytest.approx(7.340573)
    assert spec.SCREW_HEAD_DIA == pytest.approx(4.6482)


def test_profile_is_closed_and_matches_the_vendor_section() -> None:
    segments = spec.PROFILE
    for here, after in zip(segments, (*segments[1:], segments[0]), strict=True):
        assert here[-1] == after[-2 if after[0] == "line" else 2]
    for kind, *points in segments:
        if kind == "arc":
            c, p, q = points
            assert math.dist(c, p) == pytest.approx(math.dist(c, q), abs=1e-9)
    # FreeCAD section of 260001 at STEP z = 3.5 (outside the counterbore).
    assert spec.PROFILE_AREA == pytest.approx(spec.STEP_PROFILE_AREA, abs=0.005)


def test_volumes_bound_the_vendor_solids() -> None:
    """The model leaves out the O-ring recess, edge breaks and the thread, so
    it may only exceed the vendor solids, by a bounded amount (FreeCAD
    Boolean: vendor body minus model 0.26 mm^3, model minus vendor 6.1)."""
    assert spec.V_BODY == pytest.approx(270.515, abs=0.01)
    assert 0.0 < spec.V_BODY - spec.STEP_BODY_VOLUME < 0.025 * spec.STEP_BODY_VOLUME
    assert 0.0 < spec.V_SCREW - spec.STEP_SCREW_VOLUME < 0.25 * spec.STEP_SCREW_VOLUME
    assert spec.V_TOTAL == pytest.approx(spec.V_BODY + spec.V_SCREW)
    assert spec.V_COUNTERBORE > 0.0 and spec.V_THROUGH_SLOT > 0.0
    assert spec.COUNTERBORE_SKETCH_Z > spec.TOP_Z
    assert (
        spec.COUNTERBORE_SKETCH_Z - spec.COUNTERBORE_CUT_DEPTH / 2.0
        == pytest.approx(spec.COUNTERBORE_FLOOR_Z)
    )
    assert spec.THROUGH_SLOT_DIA > spec.SCREW_MAJOR_DIA
    assert spec.COUNTERBORE_DIA > spec.SCREW_HEAD_DIA


# --- the recipe, recorded ----------------------------------------------------

_PLANE_Z = {
    spec.COUNTERBORE_PLANE: spec.COUNTERBORE_SKETCH_Z,
    spec.SOCKET_PLANE: spec.SCREW_HEAD_TOP_Z,
}


class _Recorder:
    """A fake SolidWorks recording sketch entities in sketch coordinates."""

    def __init__(self) -> None:
        self.plane: str | None = None
        self.sketches: list[dict] = []
        self.features: list[tuple] = []

    def create_sketch(self, plane):
        self.plane = plane
        self.sketches.append({"plane": plane, "lines": [], "arcs": [], "axes": []})
        return "ok"

    def exit_sketch(self):
        self.plane = None
        return "ok"

    def add_line(self, x1, y1, x2, y2):
        self.sketches[-1]["lines"].append(((x1, y1), (x2, y2)))
        return "ok"

    def add_arc(self, cx, cy, sx, sy, ex, ey):
        self.sketches[-1]["arcs"].append(((cx, cy), (sx, sy), (ex, ey)))
        return "ok"

    def add_centerline(self, x1, y1, x2, y2):
        self.sketches[-1]["axes"].append(((x1, y1), (x2, y2)))
        return "ok"

    def create_extrusion(self, params):
        self.features.append(("extrude", params))
        return "ok"

    def create_cut_extrude(self, params):
        self.features.append(("cut", params))
        return "ok"

    def create_revolve(self, params):
        self.features.append(("revolve", params))
        return "ok"


def _uv(adapter: _Recorder, point) -> tuple[float, float]:
    """SolidWorks' plane conventions: Right sketch (u, v) = (-Z, Y)."""
    x, y, z = point
    if adapter.plane == "Right":
        assert x == 0.0
        return -z, y
    expected_z = 0.0 if adapter.plane == "Front" else _PLANE_Z[adapter.plane]
    assert z == pytest.approx(expected_z)
    return x, y


@pytest.fixture
def recorded(monkeypatch) -> _Recorder:
    adapter = _Recorder()
    names: list[str] = []
    volumes: list[float] = []
    planes: list[tuple] = []

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe, "name_last_feature", lambda _a, name: names.append(name)
    )
    monkeypatch.setattr(
        recipe, "volume_check", lambda _a, _l, expected, _t: volumes.append(expected)
    )
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    monkeypatch.setattr(recipe, "set_sketch_direct_db", lambda *a: None)
    monkeypatch.setattr(
        recipe, "offset_plane", lambda _a, name, z, base: planes.append((name, z, base))
    )
    monkeypatch.setattr(recipe, "_sketch_uv", _uv)
    monkeypatch.setattr(
        recipe, "_assert_two_bodies", lambda _a: names.append("<2 bodies>")
    )
    recipe.build_26000(adapter)
    adapter.names, adapter.volumes, adapter.planes = names, volumes, planes
    return adapter


def _ccw_sweep(arc) -> float:
    c, s, e = arc
    a0 = math.atan2(s[1] - c[1], s[0] - c[0])
    a1 = math.atan2(e[1] - c[1], e[0] - c[0])
    return (a1 - a0) % (2.0 * math.pi)


def _closed(sketch) -> bool:
    ends: dict[tuple[float, float], int] = {}
    for p, q in sketch["lines"]:
        for point in (p, q):
            key = (round(point[0], 6), round(point[1], 6))
            ends[key] = ends.get(key, 0) + 1
    for _, p, q in sketch["arcs"]:
        for point in (p, q):
            key = (round(point[0], 6), round(point[1], 6))
            ends[key] = ends.get(key, 0) + 1
    return bool(ends) and all(count == 2 for count in ends.values())


def test_recipe_features_and_volumes(recorded) -> None:
    assert [s["plane"] for s in recorded.sketches] == [
        "Right",
        spec.COUNTERBORE_PLANE,
        "Front",
        "Right",
        spec.SOCKET_PLANE,
    ]
    assert recorded.planes == [
        (spec.COUNTERBORE_PLANE, spec.COUNTERBORE_SKETCH_Z, "Front Plane"),
        (spec.SOCKET_PLANE, spec.SCREW_HEAD_TOP_Z, "Front Plane"),
    ]
    assert recorded.names == [
        spec.BODY_SKETCH,
        spec.BODY_FEATURE,
        spec.COUNTERBORE_SKETCH,
        spec.COUNTERBORE_FEATURE,
        spec.THROUGH_SLOT_SKETCH,
        spec.THROUGH_SLOT_FEATURE,
        spec.SCREW_SKETCH,
        spec.SCREW_FEATURE,
        spec.SOCKET_SKETCH,
        spec.SOCKET_FEATURE,
        "<2 bodies>",
    ]
    kinds = [kind for kind, _ in recorded.features]
    assert kinds == ["extrude", "cut", "cut", "revolve", "cut"]
    body, counterbore, slot, screw, socket = (p for _, p in recorded.features)
    assert body.depth == pytest.approx(spec.WIDTH) and body.both_directions
    assert counterbore.depth == pytest.approx(spec.COUNTERBORE_CUT_DEPTH)
    assert counterbore.both_directions and counterbore.end_condition == "Blind"
    assert slot.end_condition == "ThroughAll" and slot.both_directions
    assert screw.angle == 360.0 and screw.merge_result is False and not screw.is_cut
    assert socket.depth == pytest.approx(spec.SCREW_SOCKET_CUT_DEPTH)
    assert socket.both_directions
    v = spec.V_EXTRUDED
    assert recorded.volumes == pytest.approx(
        [
            v,
            v - spec.V_COUNTERBORE,
            spec.V_BODY,
            spec.V_BODY + spec.screw_revolved_volume(),
            spec.V_TOTAL,
        ]
    )


def test_recorded_profile_is_closed_and_its_arcs_turn_the_short_way(recorded) -> None:
    profile = recorded.sketches[0]
    assert _closed(profile)
    assert len(profile["lines"]) == 5 and len(profile["arcs"]) == 4
    # Right sketch u = -Z, v = Y: a mirror of part (Y, Z), so every minor arc
    # must still sweep counter-clockwise less than half a turn.
    for arc in profile["arcs"]:
        assert 0.0 < _ccw_sweep(arc) < math.pi
    radii = sorted(math.dist(c, s) for c, s, _ in profile["arcs"])
    assert radii == pytest.approx(
        sorted([spec.TOP_FILLET_R, spec.HEEL_R, spec.KNEE_R, spec.KNIFE_ARC_R])
    )
    knife = (-spec.KNIFE_TIP[1], spec.KNIFE_TIP[0])
    assert any(
        math.dist(point, knife) < 1e-9 for line in profile["lines"] for point in line
    )


@pytest.mark.parametrize(
    ("index", "dia"),
    [(1, spec.COUNTERBORE_DIA), (2, spec.THROUGH_SLOT_DIA)],
)
def test_obrounds_run_toward_the_heel(recorded, index, dia) -> None:
    sketch = recorded.sketches[index]
    assert _closed(sketch)
    for arc in sketch["arcs"]:
        c, s, _ = arc
        assert math.dist(c, s) == pytest.approx(dia / 2.0)
        assert _ccw_sweep(arc) == pytest.approx(math.pi)
        # The cap's far point (CCW midpoint) lies away from the slot.
        a = math.atan2(s[1] - c[1], s[0] - c[0]) + math.pi / 2.0
        mid_y = c[1] + dia / 2.0 * math.sin(a)
        assert (mid_y > 0.0) if c[1] == 0.0 else (mid_y < -spec.SLOT_TRAVEL)
    centres = sorted(c[1] for c, _, _ in sketch["arcs"])
    assert centres == pytest.approx([-spec.SLOT_TRAVEL, 0.0])


def test_recorded_screw_profile_revolves_about_part_z(recorded) -> None:
    sketch = recorded.sketches[3]
    assert sketch["axes"] == [((-spec.SCREW_HEAD_TOP_Z, 0.0), (-spec.SCREW_TIP_Z, 0.0))]
    assert _closed(sketch)
    assert not sketch["arcs"]
    radii = {round(p[1], 6) for line in sketch["lines"] for p in line}
    assert max(radii) == pytest.approx(spec.SCREW_HEAD_DIA / 2.0)
    assert min(radii) == 0.0
    hexagon = recorded.sketches[4]
    assert _closed(hexagon) and len(hexagon["lines"]) == 6
    xs = [p[0] for line in hexagon["lines"] for p in line]
    assert max(xs) - min(xs) == pytest.approx(spec.SCREW_SOCKET_AF)


def test_stock_build_keeps_the_part_frame(monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(part, "build_stock_fastener", lambda _a, **kw: seen.update(kw))
    part.build(None)
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_26000
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert seen["material"] == part.MATERIAL
    assert seen["screw_axis_planes"] == ("Top Plane", "Right Plane")
    assert seen["save_unthreaded_part"] is part._save_supplier_part


def test_supplier_hook_authors_the_catalogue_references(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        part,
        "add_supplier_reference_sketch",
        lambda _a, dims, **kw: calls.append((dims, kw)),
    )
    monkeypatch.setattr(part, "save_part_and_images", lambda _a, name: {"part": name})
    assert part._save_supplier_part(None, STEM) == {"part": STEM}
    ((dims, kwargs),) = calls
    assert dims is spec.SUPPLIER_REFERENCE_DIMENSIONS
    assert kwargs == {
        "starts": spec.SUPPLIER_REFERENCE_STARTS,
        "planes": spec.SUPPLIER_REFERENCE_PLANES,
    }


# --- the specification-control sheet -----------------------------------------


def _reference_line(name: str):
    rows = {n: (v, o) for n, v, o in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    value, orientation = rows[name]
    x, y = spec.SUPPLIER_REFERENCE_STARTS[name]
    end = (x + value, y) if orientation == "horizontal" else (x, y + value)
    return (x, y), end


def test_sheet_prints_the_catalogue_letters_on_silhouette_lines() -> None:
    plan = supplier_screw_lane_plan(
        spec.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=spec.SUPPLIER_REFERENCE_PLANES,
        sides=spec.SUPPLIER_REFERENCE_SIDES,
    )
    assert set(plan) == set(spec.SUPPLIER_REFERENCE_FORMATS)
    letters = {name: fmt[3] for name, fmt in spec.SUPPLIER_REFERENCE_FORMATS.items()}
    assert letters == {
        "SupplierA": "A",
        "SupplierB": "B",
        "SupplierC": "C",
        "SupplierD": "D MIN",
        "SupplierF": "F",
        "SupplierThreadDiameter": "4-40",
    }
    half = spec.WIDTH / 2.0
    # Front (plan, sketch = part X, Y): A and C on the side faces, F on the knife.
    (a0, a1) = _reference_line("SupplierA")
    assert a0 == (-half, 0.0) and a1 == pytest.approx((-half, spec.KNIFE_Y))
    (c0, c1) = _reference_line("SupplierC")
    assert c0 == (half, spec.HEEL_Y) and c1 == pytest.approx((half, spec.KNIFE_Y))
    (f0, f1) = _reference_line("SupplierF")
    assert f0 == (-half, spec.KNIFE_Y) and f1 == pytest.approx((half, spec.KNIFE_Y))
    # Top (sketch = part X, -Z): B then D up a side face from the heel line.
    (b0, b1) = _reference_line("SupplierB")
    (d0, d1) = _reference_line("SupplierD")
    assert b0 == (half, 0.0) and b1 == pytest.approx(d0)
    assert -d1[1] == pytest.approx((spec.CATALOG_B_IN + spec.CATALOG_D_IN) * IN)
    assert -d1[1] - spec.TOP_Z < 0.06  # D's catalogue end stands .002 past the top
    # The 4-40 chord spans the shank's flat tip.
    (t0, t1) = _reference_line("SupplierThreadDiameter")
    assert -t0[1] == pytest.approx(spec.SCREW_TIP_Z)
    assert t1[0] - t0[0] == pytest.approx(spec.SCREW_MAJOR_DIA)
    assert t0[0] == pytest.approx(-spec.SCREW_MAJOR_DIA / 2.0)


def test_footer_item_and_operating_data_fit() -> None:
    assert check_item(spec.ITEM, label=STEM) == spec.ITEM
    lines = _supplier_data_lines(spec.SUPPLIER_DATA, label=STEM)
    assert lines[0] == "SUPPLIER OPERATING DATA (REFERENCE):"
    text = " ".join(spec.SUPPLIER_DATA)
    for fact in (
        "26000",
        "1.30 FT-LB",
        "650 LB",
        "THROW .0075",
        "8 PER PACKAGE",
        "26008",
    ):
        assert fact in text


def test_drawing_passes_the_spec_rows_to_the_shared_purchased_sheet() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "ch_rocker_strap_tl_vn_edge_clamp_spec"
        for alias in node.names
    }
    assert imported == {
        "ITEM",
        "SUPPLIER_DATA",
        "SUPPLIER_REFERENCE_DIMENSIONS",
        "SUPPLIER_REFERENCE_FORMATS",
        "SUPPLIER_REFERENCE_PLANES",
        "SUPPLIER_REFERENCE_SIDES",
        "SUPPLIER_REFERENCE_STARTS",
    }
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {"build_purchased_fastener_drawing", "annotate_supplier_screw"} <= called


def test_plan_agrees_with_the_clamp() -> None:
    """cad/process/ch_rocker_strap/plan.toml, read here and never by a leaf."""
    parameters = tomllib.loads(PLAN.read_text(encoding="utf-8"))["parameters"]
    assert 0.0 < parameters["clamp_torque_ft_lb"] <= spec.MAX_TORQUE_FT_LB
    assert "0.5 FT-LB" in spec.SUPPLIER_DATA[1]
    assert parameters["clamp_torque_ft_lb"] == 0.5
    assert parameters["clamp_height_mm"] == pytest.approx(spec.CATALOG_D_IN * IN)
    # Seated on a B-deep pocket floor the modelled clamp stays under the
    # plan's clamp-nose keep-out.
    assert spec.TOP_Z - spec.B_REFERENCE <= parameters["clamp_height_mm"]


def test_no_vendor_model_is_tracked() -> None:
    root = SCRIPTS.parents[1]
    assert not list(root.glob("cad/references/**/26000*.STEP"))
    assert not list(root.glob("cad/references/**/26000*.SLDPRT"))


@pytest.mark.parametrize(
    "module",
    [
        "diagnostics/diag_build_26000.py",
        "build_ch_rocker_strap_tl_vn_edge_clamp.py",
        "draw_ch_rocker_strap_tl_vn_edge_clamp.py",
    ],
)
def test_every_direct_adapter_call_exists_and_binds(module: str) -> None:
    from test_pd_transgear_adapter_contract import (
        _adapter_calls,
        _adapter_methods,
        _missing,
        _signature,
    )

    tree = ast.parse((SCRIPTS / module).read_text(encoding="utf-8"))
    assert not _missing(tree), sorted(_missing(tree))
    for call in _adapter_calls(tree):
        _, method = _adapter_methods()[call.func.attr]
        assert not any(isinstance(arg, ast.Starred) for arg in call.args), call.lineno
        _signature(method).bind(
            call.func.value,
            *call.args,
            **{keyword.arg: keyword.value for keyword in call.keywords},
        )
    if module.startswith("diagnostics"):
        assert {
            "create_sketch",
            "add_line",
            "add_arc",
            "add_centerline",
            "create_extrusion",
            "create_cut_extrude",
            "create_revolve",
            "create_part",
            "save_file",
        } <= {call.func.attr for call in _adapter_calls(tree)}
