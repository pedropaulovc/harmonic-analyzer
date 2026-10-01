"""Offline contracts for the latch hook (MHA-127) and its drawing."""

from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path

import pytest

import _config
import build_latch_hook as part
import draw_latch_hook as drawing
import latch_hook_bracket_geometry as bracket
import latch_hook_geometry as geom
import latch_hook_spec as spec
import support_bar_spec as bar
import transgear_arm_geometry as arm
import transgear_latch_pin_spec as pin
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _band(places: int) -> float:
    return _config.title_block(f"linear_{places}pl")["value_in"] * 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/latch-hook.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/latch-hook.pdf")
    assert DRAWINGS_BY_NAME["latch_hook"].script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_placement_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_only_the_drilled_holes_carry_a_model_band() -> None:
    assert model_toleranced_dimensions(part) == {
        ("PinHoleProfile", "PinHoleDia"): "*deviations(HOLE_BAND)",
        ("RivetHoleProfile", "RivetHoleDia"): "*deviations(HOLE_BAND)",
    }
    assert min(spec.HOLE_BAND) == 0.0 < max(spec.HOLE_BAND)


def _on_centreline(y: float, z: float) -> float:
    """Distance of machine (y, z) from the centreline arc that governs y."""
    centre, radius = (geom.C1, geom.R1) if y >= geom.JUNCTION[0] else (geom.C2, geom.R2)
    return abs(math.hypot(y - centre[0], z - centre[1]) - radius)


def test_the_centreline_is_two_tangent_arcs_from_a_square_top() -> None:
    """R9-10: the tangent two-arc chain replaces the traced spline; the top
    cut is square to the strip.  R9-26: the pin hole is on the arm's pin axis
    and within the sheet's centring band of the centreline."""
    # Square top: arc 1's centre lies on the normal to the cut line (y const).
    assert geom.C1[0] == geom.TOP_Y
    # Tangent: both centres and the junction collinear.
    (y1, z1), (y2, z2), (yj, zj) = geom.C1, geom.C2, geom.JUNCTION
    cross = (y2 - y1) * (zj - z1) - (z2 - z1) * (yj - y1)
    assert abs(cross) / (geom.R1 * geom.R1) < 1e-5
    for station in (geom.JUNCTION, geom.END_YZ):
        assert _on_centreline(*station) < 2e-3
    arm_pin_z = arm.FRONT_FACE_MACHINE_Z + arm.THICKNESS / 2.0
    assert geom.PIN_HOLE_YZ[1] == pytest.approx(arm_pin_z, abs=1e-9)
    assert _on_centreline(*geom.PIN_HOLE_YZ) <= spec.CENTRING_BAND
    # The rivet pair straddles the centreline symmetrically.
    (ya, za), (yb, zb) = geom.RIVET_YZ
    assert ya == yb == geom.RIVET_Y
    assert zb - za == pytest.approx(geom.RIVET_PITCH)
    assert (za + zb) / 2.0 == pytest.approx(geom.centreline_z(geom.RIVET_Y))


def test_the_strip_fills_the_contract_envelope() -> None:
    """The model carries the printed 99.9 tip run, 0.05 short of the
    contract's 206.25 end; the envelope holds within that."""
    assert geom.END_YZ[0] == pytest.approx(geom.TOP_Y - round(geom.TIP_RUN, 1))
    assert geom.BBOX_Y == pytest.approx((201.25, 306.2), abs=0.06)
    assert geom.BBOX_Z[0] == pytest.approx(-128.5, abs=0.06)
    assert geom.PLANE_X[1] - geom.PLANE_X[0] == pytest.approx(geom.STRIP_T)


def test_walls_hold_the_target_at_the_worst_case_the_sheet_prints() -> None:
    drill = max(spec.HOLE_BAND)
    rivet_r = (geom.RIVET_HOLE_DIA + drill) / 2.0
    pin_r = (geom.PIN_HOLE_DIA + drill) / 2.0
    tol3 = _band(spec.RIVET_PLACES)
    edge_loss = spec.CENTRING_BAND + spec.STOCK_WIDTH_TOL / 2.0
    top = round(geom.RIVET_RUN, 3) - tol3 - rivet_r
    web = round(geom.RIVET_PITCH, 3) - tol3 - 2.0 * rivet_r
    edge = geom.HALF_W - (round(geom.RIVET_PITCH, 3) + tol3) / 2.0 - rivet_r - edge_loss
    pin = geom.HALF_W - pin_r - edge_loss
    for worst in (top, web, edge, pin):
        assert worst >= spec.WALL_TARGET - 0.01
    assert spec.WALLS_WORST == pytest.approx(
        {
            "rivet hole to top cut": top,
            "rivet hole to long edge": edge,
            "rivet web": web,
            "pin hole to long edge": pin,
        },
        abs=0.01,
    )


def test_the_latch_pin_enters_its_hole_at_the_fit_up_pose() -> None:
    """The pin's full diameter, swept obliquely through the strip, clears
    the 5.4 hole by the latch's minimum at the pose the hook is set in."""
    pivot = (bar.PIVOT_TAP_X, bracket.BAR_CENTRE_Y + bar.HANGER_TAP_Y)
    hole_y = geom.PIN_HOLE_YZ[0]
    mid_x = sum(geom.PLANE_X) / 2.0
    run = (mid_x - pivot[0], hole_y - pivot[1])
    length = math.hypot(*run)
    ux, uy = run[0] / length, run[1] / length  # the pin axis, in a z plane
    r = pin.DIA_MAX / 2.0
    reach = 0.0
    for step in range(3600):
        phi = 2.0 * math.pi * step / 3600
        # A point on the pin's surface: across the axis in the xy plane by
        # r cos(phi) (normal (-uy, ux)), along z by r sin(phi).
        across, off_z = r * math.cos(phi), r * math.sin(phi)
        off_x, off_y = -uy * across, ux * across
        for face_x in geom.PLANE_X:
            s = (face_x - mid_x - off_x) / ux
            y = hole_y + s * uy + off_y
            reach = max(reach, math.hypot(y - hole_y, off_z))
    clearance = geom.PIN_HOLE_DIA / 2.0 - reach
    assert clearance >= spec.PIN_CLEARANCE_MIN
    assert spec.PIN_CLEARANCE_ALONG == pytest.approx(clearance, abs=1e-3)


def _spec_with(monkeypatch, name: str, value):
    monkeypatch.setattr(geom, name, value)
    loaded = importlib.util.spec_from_file_location("_hook_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(fresh)
    return fresh


def test_the_wall_gate_refuses_the_contract_pitch(monkeypatch) -> None:
    """The contract's 3.2 rivet pitch leaves the web under target."""
    fresh = _spec_with(monkeypatch, "RIVET_PITCH", geom.RIVET_PITCH)
    assert fresh.WALLS_WORST == spec.WALLS_WORST
    with pytest.raises(AssertionError, match="rivet web"):
        _spec_with(monkeypatch, "RIVET_PITCH", 3.2)


def test_legacy_assembly_extents_stay_exported() -> None:
    assert part.STRIP_T == geom.STRIP_T == 0.6
    assert part.X_MAX == pytest.approx(0.0, abs=1e-9)
    assert part.X_MIN == pytest.approx(-(geom.TIP_RUN + geom.TIP_R), abs=0.01)
    assert part.Y_MIN == pytest.approx(-11.8605, abs=0.01)


def test_registry_row_is_the_dead_soft_strip_mha_127() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-127"
    assert int(row["quantity"]) == 1
    assert "dead soft" in row["material_specification"]
    assert "spring" not in row["finish"] + row["material_specification"]
    assert row["material"] == part.MATERIAL


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args] == [
        "adapter",
        "PART_NAME",
        "{'Manufacturing Notes': DRAWING_NOTES}",
    ]
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(
        None, part.PART_NAME, {"Manufacturing Notes": spec.DRAWING_NOTES}
    )
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
