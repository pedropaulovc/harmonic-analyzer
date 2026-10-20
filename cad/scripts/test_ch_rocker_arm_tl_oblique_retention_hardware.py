"""Source-only purchased identity, frame, and receiving-envelope contracts."""
from __future__ import annotations

import ast
import importlib
import math
from pathlib import Path

import pytest
import yaml

import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import ch_rocker_arm_tl_oblique_retention_spec as cartridge
import ch_rocker_arm_tl_vn_oblique_pivot_cotter_spec as cotter
import ch_rocker_arm_tl_vn_oblique_pivot_lock_wire_spec as wire

SCRIPTS = Path(__file__).resolve().parent
PREFIX = "ch_rocker_arm_tl_vn_oblique_pivot_"
PARTS = (
    ("cap_screw", 73, 8, "NAS1352N4H12"),
    ("clevis_pin", 74, 2, "CLPS6-0187-1250D"),
    ("cotter", 75, 2, "CP-062-0500"),
    ("lock_wire", 76, 4, "05-02685"),
)


@pytest.mark.parametrize("suffix,number,quantity,sku", PARTS)
def test_purchased_identity_quantity_native_author_and_sheet(suffix, number, quantity, sku):
    module = PREFIX + suffix
    stem = module.replace("_", "-")
    row = yaml.safe_load((SCRIPTS.parent / "config" / "parts" / f"{stem}.yaml").read_text())[stem]
    spec = importlib.import_module(module + "_spec")
    assert row["number"] == f"MHA-CH-06-TL-VN-{number}"
    assert row["supplier_skus"] == [sku]
    assert row["quantity"] == spec.QUANTITY == quantity
    assert spec.SKU == sku
    assert row["process"] == "purchased"
    assert sku in row["material_specification"]
    recipe_name = "diagnostics.diag_build_" + sku.replace("-", "_")
    author = importlib.import_module(recipe_name)
    from _stock_recipe import recipe_declaration
    declaration = recipe_declaration(sku, getattr(author, "build_" + sku.replace("-", "_")))
    assert declaration.threaded == (suffix == "cap_screw")
    builder = ast.parse((SCRIPTS / f"build_{module}.py").read_text())
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "StockComponent" for node in ast.walk(builder))
    drawing = ast.parse((SCRIPTS / f"draw_{module}.py").read_text())
    assert any(isinstance(node, ast.ImportFrom) and node.module == "_purchased_part_drawing"
               for node in drawing.body)


def test_nas_drilled_head_thread_and_length_are_sourced_limits():
    assert hardware.SCREW_MAJOR_DIA_MIN == pytest.approx(0.2419 * 25.4)
    assert hardware.SCREW_MAJOR_DIA_MAX == pytest.approx(0.2500 * 25.4)
    assert hardware.SCREW_LENGTH_MIN == pytest.approx(0.720 * 25.4)
    assert hardware.SCREW_DIMS.fully_threaded
    assert hardware.SCREW_DIMS.length == pytest.approx(0.750 * 25.4)
    assert hardware.SCREW_WIRE_HOLE_ANGLES == (0, 60, 120, 180, 240, 300)
    assert hardware.WIRE_DIA < hardware.SCREW_WIRE_HOLE_DIA_MIN
    assert hardware.SCREW_HEAD_HEIGHT_MIN <= hardware.SCREW_HEAD_HEIGHT <= hardware.SCREW_HEAD_HEIGHT_MAX
    assert hardware.SCREW_HEAD_DIA_MIN <= hardware.SCREW_HEAD_DIA <= hardware.SCREW_HEAD_DIA_MAX


def test_clevis_actual_shank_and_split_cotter_fit_not_rounded_nominal():
    assert hardware.CLEVIS_DIA_MIN <= hardware.CLEVIS_DIA <= hardware.CLEVIS_DIA_MAX < 5.0
    assert hardware.CLEVIS_DIA_MAX < 3 / 16 * 25.4
    assert hardware.CLEVIS_HEAD_DIA_MIN > 5.0
    assert hardware.COTTER_DIA_MAX < hardware.CLEVIS_HOLE_DIA_MIN
    assert math.hypot(hardware.COTTER_DIA, hardware.COTTER_WIDTH) < hardware.CLEVIS_HOLE_DIA_MIN
    assert hardware.CLEVIS_HOLE_FROM_HEAD == pytest.approx((1.109 + 0.094 / 2) * 25.4)
    assert hardware.CLEVIS_HOLE_FROM_HEAD + hardware.CLEVIS_HOLE_DIA / 2 < hardware.CLEVIS_LENGTH
    # Assembly's -13 head seat puts the cotter eye outside the washer's R12.
    assert -13 + hardware.CLEVIS_HOLE_FROM_HEAD - cotter.EYE_OUTER_RADIUS > 12
    assert cotter.INSTALLED_Z_MAX > hardware.CLEVIS_DIA / 2
    assert cotter.INSTALLED_Z_MIN < -hardware.CLEVIS_DIA / 2
    assert cotter.SHORT_TAIL > 0
    assert cotter.LONG_TAIL - cotter.SHORT_TAIL == pytest.approx(hardware.COTTER_PRONG_DIFFERENCE_MIN)


def _point(segment, t):
    return tuple((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d
                 for a,b,c,d in zip(*segment))


def _split_cubic(segment):
    def midpoint(a, b):
        return tuple((x+y)/2 for x,y in zip(a,b))
    a,b,c,d = segment
    ab,bc,cd = midpoint(a,b),midpoint(b,c),midpoint(c,d)
    abc,bcd = midpoint(ab,bc),midpoint(bc,cd)
    middle = midpoint(abc,bcd)
    return (a,ab,abc,middle),(middle,bcd,cd,d)


def _certify_hull(segment, enclosed, depth=0):
    """Every accepted leaf encloses its entire cubic, not a set of samples.

    De Casteljau subdivision preserves the curve exactly. Failure to prove
    containment at the depth limit is a failure, never a sampled fallback.
    """
    if enclosed(segment):
        return True
    if depth == 16:
        return False
    return all(_certify_hull(half,enclosed,depth+1) for half in _split_cubic(segment))


def test_wire_is_continuous_with_twists_loops_and_bent_ends_below_cap():
    segments = wire.installed_wire_segments()
    assert len(segments) > 100
    for previous, following in zip(segments, segments[1:]):
        assert previous[-1] == pytest.approx(following[0])
    radius = hardware.WIRE_DIA / 2
    from _printed_tolerance import printed_band_mm
    counterbore_depth_band = printed_band_mm(cartridge.CAP_COUNTERBORE_DEPTH_PLACES)
    channel_band = printed_band_mm(cartridge.CAP_WIRE_CHANNEL_PLACES)
    floor_max = (cartridge.CAP_COUNTERBORE_DEPTH + counterbore_depth_band
                 - cartridge.CAP_WIRE_CHANNEL_DEPTH + channel_band)
    top_min = cartridge.CAP_COUNTERBORE_DEPTH - counterbore_depth_band
    nas_low = hardware.SCREW_HEAD_HEIGHT_MIN - hardware.SCREW_WIRE_FROM_TOP_MAX
    nas_high = hardware.SCREW_HEAD_HEIGHT_MAX - hardware.SCREW_WIRE_FROM_TOP_MIN
    for segment in segments:
        for control in segment:
            relative_z = control[2] - wire.WIRE_AXIS_Z
            assert floor_max < nas_low + relative_z - radius
            assert nas_high + relative_z + radius < top_min
            assert wire.WIRE_Z_MIN <= control[2] - radius
            assert control[2] + radius <= wire.WIRE_Z_MAX
    # A curve is inside its Bezier control hull. A sphere of wire radius
    # encloses every oriented wire section, including bends/twists. Eroding
    # each convex void by that radius therefore certifies the swept tube.
    cb_radius_min = (cartridge.CAP_COUNTERBORE_DIAMETER
                     - printed_band_mm(cartridge.CAP_COUNTERBORE_DIAMETER_PLACES))/2
    channel_half_min = (cartridge.CAP_WIRE_CHANNEL_WIDTH-channel_band)/2
    # The cap's overall X width retains its one-place title-block band.
    cap_half_min = (cartridge.CAP_WIDTH-printed_band_mm(1))/2

    def enclosed(controls):
        if all(abs(p[0])+radius < cap_half_min and abs(p[1])+radius < channel_half_min
               for p in controls):
            return True
        for center in wire.CAP_BOLT_X_OFFSETS:
            if all(math.hypot(p[0]-center,p[1])+radius < cb_radius_min
                   for p in controls):
                return True
            side = 1 if center > 0 else -1
            if all(side*p[0] >= abs(center)+radius and abs(p[0])+radius < cap_half_min
                   and abs(p[1])+radius < cb_radius_min for p in controls):
                return True
        return False

    for segment in segments:
        assert _certify_hull(segment,enclosed), segment
    # Nominal wrap torus, with the complete round section, fits the smallest
    # accepted counterbore. Chords/bends are separately certified above.
    assert wire.OUTER_BEND_RADIUS + radius < cb_radius_min
    assert wire.OUTER_BEND_RADIUS - radius > hardware.SCREW_HEAD_DIA_MAX/2
    assert nas_low-wire.TWIST_RADIUS-radius-floor_max == pytest.approx(0.4722)
    assert 2*(wire.TWIST_RADIUS+radius) < 2*channel_half_min


def test_wire_crosses_heads_only_through_the_real_diametral_drills():
    radius = hardware.WIRE_DIA / 2
    for center in wire.CAP_BOLT_X_OFFSETS:
        def enclosed(controls):
            # AABB lower distance bounds the complete convex control hull.
            # Merely finding each control outside a circle would NOT suffice.
            intervals = [(min(p[i] for p in controls),max(p[i] for p in controls))
                         for i in (0,1)]
            closest = [max(lo-value,0,value-hi)
                       for (lo,hi),value in zip(intervals,(center,0))]
            if math.hypot(*closest) > hardware.SCREW_HEAD_DIA_MAX/2 + radius:
                return True
            # Both diametral drill passages remain straight at every NAS W.
            # Relative Z is invariant when formed to the actual received head.
            return all(math.hypot(p[1],p[2]-hardware.SCREW_WIRE_HEIGHT)+radius
                       < hardware.SCREW_WIRE_HOLE_DIA_MIN/2 for p in controls)

        for segment in wire.installed_wire_segments():
            assert _certify_hull(segment,enclosed), (center,segment)


def test_wire_nonadjacent_strands_do_not_overlap():
    # Spatial bins avoid an O(n²) all-pairs census. Ignore adjacent lengths
    # along the same bent strand, not separate turns or the return strand.
    diameter = hardware.WIRE_DIA
    bins = {}
    length = 0.0
    previous = None
    for segment in wire.installed_wire_segments():
        for index in range(17):
            point = _point(segment, index/16)
            if previous is not None:
                length += math.dist(previous,point)
            previous = point
            cell = tuple(math.floor(value/diameter) for value in point)
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for dz in (-1,0,1):
                        key = (cell[0]+dx,cell[1]+dy,cell[2]+dz)
                        for old_length,old_point in bins.get(key, ()):
                            if length-old_length > 3*diameter:
                                assert math.dist(point,old_point) >= diameter, (point,old_point)
            bins.setdefault(cell, []).append((length,point))


def test_hardware_provider_does_not_import_its_cartridge_consumer():
    tree = ast.parse(Path(hardware.__file__).read_text())
    modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert "ch_rocker_arm_tl_oblique_retention_spec" not in modules
    assert all(not module.startswith("build_") for module in modules if module)
