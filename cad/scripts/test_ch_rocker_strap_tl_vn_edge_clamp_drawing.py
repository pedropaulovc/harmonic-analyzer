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
    # Blind both ways past the full height (FeatureCut3 refuses ThroughAll
    # both ways): each side reaches past the body.
    assert slot.end_condition == "Blind" and slot.both_directions
    assert slot.depth > spec.TOP_Z
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
    # Front (plan, sketch = part X, Y): A and C on the side faces, F on the heel.
    (a0, a1) = _reference_line("SupplierA")
    assert a0 == (-half, 0.0) and a1 == pytest.approx((-half, spec.KNIFE_Y))
    (c0, c1) = _reference_line("SupplierC")
    assert c0 == (half, spec.HEEL_Y) and c1 == pytest.approx((half, spec.KNIFE_Y))
    (f0, f1) = _reference_line("SupplierF")
    assert f0 == (-half, spec.HEEL_Y) and f1 == pytest.approx((half, spec.HEEL_Y))
    # Top (sketch = part X, -Z): B up the right face from the heel line, D on
    # the left face from B's height to the top, each in a lane of its own.
    (b0, b1) = _reference_line("SupplierB")
    (d0, d1) = _reference_line("SupplierD")
    assert b0 == (half, 0.0) and d0 == (-half, pytest.approx(b1[1]))
    sides = {name: side for name, (side, _) in plan.items()}
    assert (sides["SupplierB"], sides["SupplierD"]) == ("right", "left")
    assert (
        len(
            {
                (spec.SUPPLIER_REFERENCE_PLANES.get(n, "Front"), s)
                for n, s in sides.items()
            }
        )
        == 6
    )
    assert -d1[1] == pytest.approx((spec.CATALOG_B_IN + spec.CATALOG_D_IN) * IN)
    assert -d1[1] - spec.TOP_Z < 0.06  # D's catalogue end stands .002 past the top
    # The 4-40 chord spans the shank's flat tip.
    (t0, t1) = _reference_line("SupplierThreadDiameter")
    assert -t0[1] == pytest.approx(spec.SCREW_TIP_Z)
    assert t1[0] - t0[0] == pytest.approx(spec.SCREW_MAJOR_DIA)
    assert t0[0] == pytest.approx(-spec.SCREW_MAJOR_DIA / 2.0)


def test_no_reference_line_is_welded_at_both_ends() -> None:
    """``_supplier_screw_reference._linear`` relies on each new line sharing
    at most one end with the lines authored before it in its sketch: a line
    joining two earlier lines closes a loop whose orientation relation is
    redundant, and SolidWorks reports the sketch over-defined (farm r2, run
    20261117T234918780Z: F on the knife edge closed A-F-C)."""
    earlier: dict[str, list[tuple[float, float]]] = {}
    for name, _, _ in spec.SUPPLIER_REFERENCE_DIMENSIONS:
        plane = spec.SUPPLIER_REFERENCE_PLANES.get(name, "Front")
        ends = _reference_line(name)
        points = earlier.setdefault(plane, [])
        shared = [
            end for end in ends if any(math.dist(end, point) < 1e-6 for point in points)
        ]
        assert len(shared) <= 1, name
        points.extend(ends)


# --- the sheet's layout, simulated with the shared builder's own cells --------
# GetOutline pads a view's model box by a fixed 5.59 mm a side (farm r3: the
# 1:1 FRONT 20.70 mm across the 9.525 mm plan, TOP 23.9 mm over 12.75 mm).
OUTLINE_PAD = 0.00559
# r3's 4:1 isometric outline, 74.2 x 78.6 mm, less its pads, per unit scale.
ISO_MODEL = ((0.0742 - 2 * OUTLINE_PAD) / 4.0, (0.0786 - 2 * OUTLINE_PAD) / 4.0)
# Native reference ink, sheet metres, from farm r3's layout audit (1:1, all
# shelved) and r7's failure (4:1). Value over letter, Century Gothic 3.5 mm:
# (.150) 12.5 mm wide, D MIN 13.6 mm, (Ø.112) ~16 mm.
TEXT_W = {"SupplierD": 0.0136, "SupplierThreadDiameter": 0.0165}
TEXT_W_DEFAULT = 0.0125
TEXT_H = 0.0095  # value's caps 3.5 mm over the letter's baseline 5.55 mm below
# A horizontal reference's position is its value's baseline: caps 3.8 mm
# above it, the letter's baseline 5.55 mm below, line and arrows inked to
# 6.55 mm below (r7: SupplierF at y .0976393 inked down to .091085).
VALUE_ABOVE = 0.0038
LETTER_BELOW = 0.00555
INK_BELOW = 0.006554
# A vertical reference's line stands on its position; witnesses overshoot it
# 1.0 mm; arrows outside a short span run the line 6.35 mm past each witness;
# a shelf starts 2.2 mm past the outermost line (r3: A, D, the 4-40 chord).
WITNESS_OVERSHOOT = 0.001
ARROW_RUN = 0.00635
SHELF_GAP = 0.0022
ARROW_HALF = 0.000381
TITLE_BLOCK = (0.216, 0.4191, 0.0127, 0.066)
SHEET = (0.0127, 0.4191, 0.0127, 0.2667)


Box = tuple[float, float, float, float]  # x0, x1, y0, y1 (sheet metres)


def _overlap(a: Box, b: Box) -> bool:
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def _model_extent() -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """Each view's model box in its own sketch frame, metres: (x range, y range)."""
    x = (-spec.WIDTH / 2000.0, spec.WIDTH / 2000.0)
    plan_y = (spec.HEEL_Y / 1000.0, spec.KNIFE_Y / 1000.0)
    top_y = (-spec.TOP_Z / 1000.0, -spec.SCREW_TIP_Z / 1000.0)
    return {
        "*Front": (x, plan_y),
        "*Top": (x, top_y),
        "*Right": ((spec.SCREW_TIP_Z / 1000.0, spec.TOP_Z / 1000.0), plan_y),
        "*Isometric": ((0.0, ISO_MODEL[0]), (0.0, ISO_MODEL[1])),
    }


def _size(name: str, scale: tuple[int, int]) -> tuple[float, float]:
    (x0, x1), (y0, y1) = _model_extent()[name]
    k = scale[0] / scale[1]
    return (x1 - x0) * k + 2 * OUTLINE_PAD, (y1 - y0) * k + 2 * OUTLINE_PAD


def _layout():
    """The builder's row split and per-group fit (``_top_lowering``,
    ``_fit_group``) over its own cells, with modelled native outlines."""
    from _purchased_fastener_drawing import (
        _ISOMETRIC,
        _SCALES,
        _project_from_front,
        fastener_view_cells,
        supplier_fit_cells,
        view_band_bottom,
    )

    notes = str(_config.parts(STEM).get("installation_notes", ""))
    caption_y = view_band_bottom(notes, label=STEM, supplier_data=spec.SUPPLIER_DATA)
    margins = drawing.supplier_margins()

    def cells(lower: float):
        outer = fastener_view_cells(caption_y, lower=lower)
        fit = _project_from_front(supplier_fit_cells(outer, margins, label=STEM))
        return {n: c for n, _, c in outer}, {n: c for n, _, c in fit}

    outer, fit = cells(0.0)
    lowering = 0.0
    for scale in _SCALES:
        spare = {}
        for name in ("*Front", "*Top", "*Right"):
            w, h = _size(name, scale)
            c = fit[name]
            spare[name] = ((c[2] - c[0]) - w, (c[3] - c[1]) - h)
        row = min(spare["*Front"][1], spare["*Right"][1])
        short = -spare["*Top"][1]
        if min(s[0] for s in spare.values()) < 0.0 or row < 0.0:
            continue
        if short <= 0.0:
            break
        if short <= row:
            lowering = (short + row) / 2
            break
    if lowering:
        outer, fit = cells(lowering)

    def fits(names, scale) -> bool:
        return all(
            _size(n, scale)[0] <= fit[n][2] - fit[n][0]
            and _size(n, scale)[1] <= fit[n][3] - fit[n][1]
            for n in names
        )

    orthographic = ("*Front", "*Top", "*Right")
    ortho = next(s for s in _SCALES if fits(orthographic, s))
    iso = next(s for s in _SCALES if fits((_ISOMETRIC,), s))
    scales = {**dict.fromkeys(orthographic, ortho), _ISOMETRIC: iso}
    views = {}
    for name, c in fit.items():
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        w, h = _size(name, scales[name])
        views[name] = (cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2)
    return outer, scales, views, caption_y


def _reference_ink(views, scales) -> dict[str, tuple[Box, Box, str]]:
    """Each reference's (text box, whole ink box, view) as the shared lane
    plan and the builder's shelving place it. A short span's arrows are taken
    as outside (its line run past both witnesses)."""
    from _drawing_annotation_extent import CLEAR_GAP_M

    plan = supplier_screw_lane_plan(
        spec.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=spec.SUPPLIER_REFERENCE_PLANES,
        sides=spec.SUPPLIER_REFERENCE_SIDES,
    )
    extents = _model_extent()
    ink = {}
    for name, (side, offset) in plan.items():
        view = f"*{spec.SUPPLIER_REFERENCE_PLANES.get(name, 'Front')}"
        box = views[view]
        (mx0, mx1), (my0, my1) = extents[view]
        k = scales[view][0] / scales[view][1] / 1000.0
        cx, cy = (box[0] + box[1]) / 2, (box[2] + box[3]) / 2
        (p0, p1) = _reference_line(name)
        ends = [
            (cx + (x - (mx0 + mx1) * 500.0) * k, cy + (y - (my0 + my1) * 500.0) * k)
            for x, y in (p0, p1)
        ]
        width = TEXT_W.get(name, TEXT_W_DEFAULT)
        if side in ("left", "right"):
            lane = box[0] - offset if side == "left" else box[1] + offset
            lo, hi = sorted(y for _, y in ends)
            mid = (lo + hi) / 2
            text_y = (mid - TEXT_H / 2, mid + TEXT_H / 2)
            line = (
                lane - ARROW_HALF,
                lane + ARROW_HALF,
                lo - ARROW_RUN,
                hi + ARROW_RUN,
            )
            if TEXT_H + 2 * CLEAR_GAP_M < hi - lo:
                text = (lane - width / 2, lane + width / 2)
            else:  # shelved outward past its witnesses' ends
                reach = WITNESS_OVERSHOOT + SHELF_GAP
                text = (
                    (lane - reach - width, lane - reach)
                    if side == "left"
                    else (lane + reach, lane + reach + width)
                )
        else:
            lane = box[2] - offset if side == "bottom" else box[3] + offset
            lo, hi = sorted(x for x, _ in ends)
            line = (lo - ARROW_RUN, hi + ARROW_RUN, lane - INK_BELOW, lane)
            if width + 2 * CLEAR_GAP_M < hi - lo:
                text = ((lo + hi - width) / 2, (lo + hi + width) / 2)
            else:  # a centred span shelves right of its line's end
                start = hi + ARROW_RUN + SHELF_GAP
                text = (start, start + width)
            text_y = (lane - LETTER_BELOW, lane + VALUE_ABOVE)
        text_box = (text[0], text[1], text_y[0], text_y[1])
        whole = (
            min(text_box[0], line[0]),
            max(text_box[1], line[1]),
            min(text_box[2], line[2]),
            max(text_box[3], line[3]),
        )
        ink[name] = (text_box, whole, view)
    return ink


def test_the_ink_model_reproduces_r7s_fall_out_of_front() -> None:
    """r7 (run 20261118T001932117Z) dropped F 8 mm: its annotation stood at
    y .0976393 and its ink reached .091085, 2.9 mm under FRONT's .094 cell.
    Undropped, F's whole ink stays a millimetre inside its cell."""
    assert 0.0976393 - INK_BELOW == pytest.approx(0.091085, abs=1e-6)
    outer, scales, views, _ = _layout()
    _, (_, _, bottom, _), _ = _reference_ink(views, scales)["SupplierF"]
    assert bottom >= outer["*Front"][1] + 0.001
    assert bottom - 0.008 < outer["*Front"][1]  # r7's drop would still fall out


def test_orthographic_views_fit_at_four_to_one_with_the_isometric_no_larger() -> None:
    """Owner review of r3 (run 20261117T235437892Z): FRONT, TOP and RIGHT at
    1:1 under a 4:1 isometric. The pre-fit margins now let them fit at 4:1."""
    _, scales, _, _ = _layout()
    assert scales["*Front"] == scales["*Top"] == scales["*Right"] == (4, 1)
    assert scales["*Isometric"][0] / scales["*Isometric"][1] <= 4


def test_margins_reserve_only_the_annotated_sides() -> None:
    margins = drawing.supplier_margins()
    assert set(margins) == {"*Front", "*Top"}
    side = 0.006 + drawing.TEXT_BESIDE_M
    left, bottom, right, top = margins["*Front"]
    assert left == right == pytest.approx(side)
    assert bottom == pytest.approx(0.006 + drawing.INK_BELOW_M)
    assert top == drawing.ARROW_OVERSHOOT_M
    left, bottom, right, top = margins["*Top"]
    assert left == right == pytest.approx(side)
    assert bottom == drawing.ARROW_OVERSHOOT_M
    assert top == pytest.approx(0.006 + drawing.TEXT_ABOVE_M)
    # The measured ink each allowance covers.
    assert INK_BELOW < drawing.INK_BELOW_M
    assert VALUE_ABOVE < drawing.TEXT_ABOVE_M
    shelf = WITNESS_OVERSHOOT + SHELF_GAP + max(TEXT_W.values())
    assert shelf < drawing.TEXT_BESIDE_M
    assert ARROW_RUN + 0.056 * 4 / 1000 - OUTLINE_PAD < drawing.ARROW_OVERSHOOT_M
    # F's value stands clear under FRONT's outline (r7 dropped it 8 mm more).
    assert 0.006 - VALUE_ABOVE >= 0.002


def test_no_two_blocks_or_views_overlap_and_all_stand_on_the_sheet() -> None:
    """r3 defects 2-4: (.075) D MIN on (.140) B and on TOP's outline; every
    view, reference text, caption, the notes block and the title block clear
    of one another after the 4:1 rescale. B landscape 0.4318 x 0.2794,
    border 0.0127; title block x >= 0.216 below y 0.066."""
    from _purchased_fastener_drawing import (
        _CAPTION_BELOW,
        _CAPTION_TO_CELL,
        _FOOTER_RIGHT,
        footer_top,
    )

    outer, scales, views, _ = _layout()
    ink = _reference_ink(views, scales)
    # Each view's geometry, its outline less the pad, grown by the audit's
    # 2 mm of air: no text on geometry or within 2 mm of it.
    air = OUTLINE_PAD - 0.002
    boxes: dict[str, Box] = {
        f"view {n}": (b[0] + air, b[1] - air, b[2] + air, b[3] - air)
        for n, b in views.items()
    }
    for name, (text, whole, view) in ink.items():
        boxes[name] = text
        cell = outer[view]
        # The builder's settled guard: reference ink inside its outer cell.
        assert cell[0] <= whole[0] and whole[1] <= cell[2], name
        assert cell[1] <= whole[2] and whole[3] <= cell[3], name
    sheet_scale = scales["*Front"]
    for name, cell in outer.items():
        caption = name[1:].upper()
        if scales[name] != sheet_scale:
            caption += f"  {scales[name][0]}:{scales[name][1]}"
        half = 0.00125 * len(caption)
        at = cell[1] - _CAPTION_TO_CELL
        centre = (cell[0] + cell[2]) / 2
        boxes[f"caption {caption}"] = (
            centre - half,
            centre + half,
            at - _CAPTION_BELOW,
            at + 0.001,
        )
    notes = str(_config.parts(STEM).get("installation_notes", ""))
    top = footer_top(notes, label=STEM, supplier_data=spec.SUPPLIER_DATA)
    boxes["notes"] = (0.015, _FOOTER_RIGHT, SHEET[2], top + 0.001)
    boxes["title block"] = TITLE_BLOCK
    names = sorted(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert not _overlap(boxes[a], boxes[b]), (a, b)
    for name, box in boxes.items():
        assert SHEET[0] <= box[0] and box[1] <= SHEET[1], name
        assert SHEET[2] <= box[2] and box[3] <= SHEET[3], name


def test_the_thread_callout_and_the_short_references_read_at_scale() -> None:
    """r3 defect 3: the (Ø.112) 4-40 line and D's span were ~3 mm on paper."""
    _, scales, views, _ = _layout()
    k = scales["*Top"][0] / scales["*Top"][1]
    assert spec.SCREW_MAJOR_DIA * k >= 11.0  # mm of dimension line
    assert spec.D_REFERENCE * k >= 7.5
    thread, _, _ = _reference_ink(views, scales)["SupplierThreadDiameter"]
    assert thread[2] >= views["*Top"][3]  # above TOP, clear of the shank


def test_footer_item_and_operating_data_fit() -> None:
    """r8 LEARN review (FIX): rule 7's four short lines with the PURCHASED
    PART line; the letters the note names are the letters printed; no
    assembly torque; the O-ring a member of this item; the material only in
    the title block."""
    assert check_item(spec.ITEM, label=STEM) == spec.ITEM
    lines = _supplier_data_lines(spec.SUPPLIER_DATA, label=STEM)
    assert lines[0] == "SUPPLIER OPERATING DATA (REFERENCE):"
    assert not str(_config.parts(STEM).get("installation_notes", "")).strip()
    assert 1 + len(spec.SUPPLIER_DATA) <= 4
    text = " ".join(spec.SUPPLIER_DATA)
    for fact in ("26000", "1.30 FT-LB MAX", f"(26008) OF {NUMBER}"):
        assert fact in text
    for gone in ("FIXTURE", "0.5 FT-LB", "650 LB", "THROW", "PACKAGE"):
        assert gone not in text
    assert spec.NUMBER == NUMBER == _config.parts(STEM)["number"]
    printed = sorted(
        callout[0]
        for *_, callout in spec.SUPPLIER_REFERENCE_FORMATS.values()
        if callout[0].isalpha()
    )
    assert printed == ["A", "B", "C", "D", "F"]
    assert "; A-D, F AS LETTERED." in spec.SUPPLIER_DATA[0]
    assert "STEEL" not in spec.ITEM


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
    assert 0.0 < parameters["clamp_torque_in_lb"] <= spec.MAX_TORQUE_FT_LB * 12.0
    # The fixture's 6 in-lb (0.5 ft-lb) prints on the assembly, under the
    # clamp's limit.
    assert parameters["clamp_torque_in_lb"] == 6
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
