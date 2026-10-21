"""Source-only purchased identity, frame, and receiving-envelope contracts."""
from __future__ import annotations

import ast
from dataclasses import replace
import importlib
import math
from pathlib import Path

import pytest
import yaml

import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import ch_rocker_arm_tl_oblique_retention_spec as cartridge
import ch_rocker_arm_tl_vn_oblique_pivot_cotter_spec as cotter
import ch_rocker_arm_tl_vn_oblique_pivot_cap_screw_spec as screw
import ch_rocker_arm_tl_vn_oblique_pivot_lock_wire_spec as wire
import ch_rocker_arm_tl_oblique_cap_wire_clearance as wire_capture

SCRIPTS = Path(__file__).resolve().parent
PREFIX = "ch_rocker_arm_tl_vn_oblique_pivot_"
PARTS = (
    ("cap_screw", 73, 8, "NAS1352N5H12"),
    ("clevis_pin", 74, 2, "CLPS6-0187-1250D"),
    ("cotter", 75, 2, "CP-062-0500"),
    ("lock_wire", 76, 4, "05-02685"),
)


@pytest.mark.parametrize("suffix,number,quantity,sku", PARTS)
def test_purchased_identity_quantity_and_native_recipe(suffix, number, quantity, sku):
    module = PREFIX + suffix
    stem = module.replace("_", "-")
    row = yaml.safe_load((SCRIPTS.parent / "config" / "parts" / f"{stem}.yaml").read_text(encoding="utf-8"))[stem]
    spec = importlib.import_module(module + "_spec")
    assert row["number"] == f"MHA-CH-06-TL-VN-{number}"
    assert row["supplier_skus"] == [sku]
    assert row["quantity"] == spec.QUANTITY == quantity
    assert spec.SKU == sku
    assert row["process"] == "purchased"
    recipe_name = "diagnostics.diag_build_" + sku.replace("-", "_")
    author = importlib.import_module(recipe_name)
    from _stock_recipe import recipe_declaration
    declaration = recipe_declaration(sku, getattr(author, "build_" + sku.replace("-", "_")))
    assert declaration.threaded == (suffix == "cap_screw")


def test_nas_drilled_head_thread_and_length_are_sourced_limits():
    assert hardware.SCREW_MAJOR_DIA_MIN == pytest.approx(0.3038 * 25.4)
    assert hardware.SCREW_MAJOR_DIA_MAX == pytest.approx(0.3125 * 25.4)
    assert hardware.SCREW_DIMS.pitch == pytest.approx(25.4 / 18)
    assert hardware.SCREW_LENGTH_MIN == pytest.approx(0.720 * 25.4)
    assert hardware.SCREW_DIMS.length == pytest.approx(0.750 * 25.4)
    assert hardware.SCREW_DIMS.socket_af == pytest.approx(0.250 * 25.4)
    assert hardware.SCREW_DIMS.socket_depth == pytest.approx(0.151 * 25.4)
    assert hardware.SCREW_WIRE_HOLE_ANGLES == (0, 60, 120, 180, 240, 300)
    assert hardware.WIRE_DIA < hardware.SCREW_WIRE_HOLE_DIA_MIN
    assert hardware.SCREW_HEAD_HEIGHT_MIN <= hardware.SCREW_HEAD_HEIGHT <= hardware.SCREW_HEAD_HEIGHT_MAX
    assert hardware.SCREW_HEAD_DIA_MIN <= hardware.SCREW_HEAD_DIA <= hardware.SCREW_HEAD_DIA_MAX
    assert (hardware.SCREW_HEAD_DIA_MIN, hardware.SCREW_HEAD_DIA_MAX) == pytest.approx(
        (0.457 * 25.4, 0.469 * 25.4))
    assert (hardware.SCREW_HEAD_HEIGHT_MIN, hardware.SCREW_HEAD_HEIGHT_MAX) == pytest.approx(
        (0.306 * 25.4, 0.312 * 25.4))
    assert (hardware.SCREW_WIRE_FROM_TOP_MIN, hardware.SCREW_WIRE_FROM_TOP_MAX) == pytest.approx(
        (0.084 * 25.4, 0.104 * 25.4))
    assert (hardware.SCREW_WIRE_HOLE_DIA_MIN, hardware.SCREW_WIRE_HOLE_DIA_MAX) == pytest.approx(
        (0.044 * 25.4, 0.050 * 25.4))
    assert hardware.SCREW_WIRE_HEIGHT == pytest.approx(5.4610)
    assert (hardware.SCREW_WIRE_HEIGHT_MIN, hardware.SCREW_WIRE_HEIGHT_MAX) == pytest.approx(
        (5.1308, 5.7912))


def test_head_bearing_uses_nas_edge_break_and_asme_runout_not_whole_head_od():
    assert hardware.SCREW_HEAD_EDGE_BREAK_MAX == pytest.approx(0.008 * 25.4)
    assert hardware.SCREW_HEAD_BEARING_DIA_MIN == pytest.approx(11.2014)
    assert hardware.SCREW_HEAD_BEARING_DIA_MIN == pytest.approx(
        hardware.SCREW_HEAD_DIA_MIN - 2 * hardware.SCREW_HEAD_EDGE_BREAK_MAX)
    assert hardware.SCREW_HEAD_RUNOUT_FIM_MAX == pytest.approx(0.00625 * 25.4)
    assert hardware.SCREW_HEAD_ECCENTRICITY_MAX == pytest.approx(0.079375)
    assert hardware.SCREW_HEAD_ECCENTRICITY_MAX == pytest.approx(
        hardware.SCREW_HEAD_RUNOUT_FIM_MAX / 2)
    assert hardware.SCREW_BEARING_ANGLE_MAX_DEGREES == 1
    assert hardware.SCREW_FILLET_JUNCTION_DIA_MIN == pytest.approx(0.329 * 25.4)
    assert hardware.SCREW_FILLET_JUNCTION_DIA_MAX == pytest.approx(0.347 * 25.4)
    assert hardware.SCREW_FILLET_LENGTH_MAX == pytest.approx(0.029 * 25.4)


def test_cap_screw_purchasing_matches_live_cbs_identity_not_material_surrogate():
    from _fastener_catalog import fastener
    stem = (PREFIX + "cap_screw").replace("_", "-")
    row = yaml.safe_load((SCRIPTS.parent / "config" / "parts" / f"{stem}.yaml").read_text(encoding="utf-8"))[stem]
    assert hardware.SCREW_SUPPLIER_SKU == screw.SKU == "NAS1352N5H12"
    assert row["supplier"] == fastener(stem).supplier == hardware.SCREW_SUPPLIER == "CBS Fasteners"
    assert hardware.SCREW_SOURCE_URL == "https://cbsfasteners.com/nas-fastener-inventory/"
    assert "A286" in row["material_specification"]
    assert row["finish"] == "PASSIVATED"
    assert row["material"] == fastener(stem).material == "AISI 304"


@pytest.mark.parametrize(
    "suffix,required_physical_terms,supplier",
    (
        ("cap_screw", ("A286", "PASSIVATED"), "CBS Fasteners"),
        ("clevis_pin", ("316", "STAINLESS"), "Huyett"),
        ("cotter", ("CARBON STEEL", "ZINC CLEAR", "ASME B18.8.1"), "Huyett"),
        ("lock_wire", ("302/304", "STAINLESS", "SOFT", "MS20995"), "Aircraft Spruce"),
    ),
)
def test_required_purchase_materials_finishes_and_standards(
    suffix, required_physical_terms, supplier,
):
    from _fastener_catalog import fastener
    stem = (PREFIX + suffix).replace("_", "-")
    row = yaml.safe_load((SCRIPTS.parent / "config" / "parts" / f"{stem}.yaml").read_text(encoding="utf-8"))[stem]
    spec = importlib.import_module(PREFIX + suffix + "_spec")
    registered = fastener(stem)
    # Physical requirements must remain in the printed general specification.
    # Do not pin its prose or which of Material/Finish carries a given term.
    physical_specification = f"{row['material_specification']} {row['finish']}".upper()
    assert all(term in physical_specification for term in required_physical_terms)
    assert row["supplier"] == registered.supplier == supplier
    assert tuple(row["supplier_skus"]) == registered.skus == (spec.SKU,)


def test_stock_drills_publish_six_radial_openings_at_actual_hole_height():
    angles = []
    for segment in screw.drilled_head_segments():
        a, b = segment[0], segment[-1]
        assert a[0] == pytest.approx(-b[0])
        assert a[2] == pytest.approx(-b[2])
        for index, point in enumerate(segment):
            assert point == pytest.approx(tuple(
                (1-index/3)*u + index/3*v for u,v in zip(a,b)))
            assert point[1] == pytest.approx(hardware.SCREW_WIRE_HEIGHT)
        for x, y, z in (a,b):
            # The production wrapper rotates stock +Y to installed +Z.
            assert math.hypot(x,-z) > hardware.SCREW_HEAD_DIA_MAX / 2
            angles.append(round(math.degrees(math.atan2(-z,x))) % 360)
    assert sorted(angles) == list(hardware.SCREW_WIRE_HOLE_ANGLES)
    socket_floor = hardware.SCREW_HEAD_HEIGHT - hardware.SCREW_SOCKET_DEPTH_MIN
    assert socket_floor < hardware.SCREW_WIRE_HEIGHT - hardware.SCREW_WIRE_HOLE_DIA/2


def test_native_stock_authors_consume_certified_drill_and_wire_paths():
    recipe = ast.parse((SCRIPTS / "diagnostics" / "diag_build_NAS1352N5H12.py").read_text(encoding="utf-8"))
    build = next(node for node in recipe.body
                 if isinstance(node, ast.AsyncFunctionDef) and node.name == "build_NAS1352N5H12")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    socket = next(node for node in calls if isinstance(node.func, ast.Name)
                  and node.func.id == "build_socket_head")
    assert isinstance(socket.args[1], ast.Name) and socket.args[1].id == "SCREW_DIMS"
    loop = next(node for node in ast.walk(build) if isinstance(node, ast.For))
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "drilled_head_segments" for node in ast.walk(loop.iter))
    cut = next(node for node in calls if isinstance(node.func, ast.Name)
               and node.func.id == "circular_sweep")
    assert isinstance(cut.args[1], ast.Tuple)
    assert [node.id for node in cut.args[1].elts] == ["segment"]
    assert isinstance(cut.args[2], ast.Name) and cut.args[2].id == "SCREW_WIRE_HOLE_DIA"
    assert any(item.arg == "cut" and isinstance(item.value, ast.Constant)
               and item.value.value is True for item in cut.keywords)
    author = ast.parse((SCRIPTS / "diagnostics" / "diag_build_05_02685.py").read_text(encoding="utf-8"))
    sweep = next(node for node in ast.walk(author) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "circular_sweep")
    assert isinstance(sweep.args[1], ast.Call)
    assert isinstance(sweep.args[1].func, ast.Name)
    assert sweep.args[1].func.id == "installed_wire_segments"
    assert isinstance(sweep.args[2], ast.Name) and sweep.args[2].id == "WIRE_DIA"


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


def _curvature_clears_round_section(controls):
    """Bound curvature over a whole cubic, not just its endpoints.

    Derivative control hulls bound velocity/acceleration. Projection onto
    the chord lower-bounds speed; all velocity/acceleration cross products
    upper-bound the numerator of curvature. Subdivision tightens both.
    """
    velocity = [tuple(3*(v-u) for u,v in zip(a,b))
                for a,b in zip(controls,controls[1:])]
    acceleration = [tuple(2*(v-u) for u,v in zip(a,b))
                    for a,b in zip(velocity,velocity[1:])]
    chord = tuple(v-u for u,v in zip(controls[0],controls[-1]))
    chord_length = math.hypot(*chord)
    if chord_length == 0:
        return False
    speed_min = min(sum(v*u for v,u in zip(vector,chord))/chord_length
                    for vector in velocity)
    if speed_min <= 0:
        return False
    cross_max = max(math.hypot(
        v[1]*a[2]-v[2]*a[1],
        v[2]*a[0]-v[0]*a[2],
        v[0]*a[1]-v[1]*a[0],
    ) for v in velocity for a in acceleration)
    return cross_max * hardware.WIRE_DIA/2 < speed_min**3


def test_modeled_bends_have_room_for_the_round_wire_section():
    segments = wire.installed_wire_segments()
    assert all(_certify_hull(segment,_curvature_clears_round_section)
               for segment in segments)
    # Shrinking the actual route without shrinking its wire must fail the
    # same certificate rather than hiding a locally self-folding sweep.
    tightened = tuple(tuple(tuple(0.1*v for v in point) for point in segment)
                      for segment in segments)
    assert not all(_certify_hull(segment,_curvature_clears_round_section)
                   for segment in tightened)


def test_representative_normal_wire_is_continuous_and_fits_fitted_depth_window():
    segments = wire.installed_wire_segments()
    assert segments
    for previous, following in zip(segments, segments[1:]):
        assert previous[-1] == pytest.approx(following[0])
    radius = hardware.WIRE_DIA / 2
    from _printed_tolerance import printed_band_mm
    fitted = cartridge.fitted_counterbore_bounds()
    channel_band = printed_band_mm(cartridge.CAP_WIRE_CHANNEL_PLACES)
    # This certifies the representative normal route, not arbitrary installed
    # head angles or cap motion. Actual fitted depth bounds replace the REF
    # model depth; there is no manufactured counterbore-depth tolerance band.
    floor_max = fitted.depth_at_head_max - cartridge.CAP_WIRE_CHANNEL_DEPTH + channel_band
    top_min = fitted.depth_at_head_min - cartridge.CAP_HEAD_SEATING_GAP_MAX
    nas_low = hardware.SCREW_HEAD_HEIGHT_MIN - hardware.SCREW_WIRE_FROM_TOP_MAX
    nas_high = hardware.SCREW_HEAD_HEIGHT_MAX - hardware.SCREW_WIRE_FROM_TOP_MIN
    assert wire.swept_wire_z_bounds(segments) == pytest.approx(
        (wire.WIRE_Z_MIN, wire.WIRE_Z_MAX))
    assert wire.swept_wire_z_bounds(segments, hardware_limits=True) == pytest.approx(
        (wire.WIRE_Z_WORST_MIN, wire.WIRE_Z_WORST_MAX))
    assert wire.WIRE_Z_WORST_MIN < wire.WIRE_Z_MIN
    assert wire.WIRE_Z_WORST_MAX > wire.WIRE_Z_MAX
    assert floor_max < wire.WIRE_Z_WORST_MIN
    assert wire.WIRE_Z_WORST_MAX < top_min
    # A changed modeled tail/control must change the consumer's roof bound.
    raised = tuple(tuple((x,y,z+2) for x,y,z in segment) for segment in segments)
    assert wire.swept_wire_z_bounds(raised, hardware_limits=True)[1] > top_min
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

    def enclosed(controls, *, cb_radius=cb_radius_min, channel_half=channel_half_min):
        if all(abs(p[0])+radius < cap_half_min and abs(p[1])+radius < channel_half
               for p in controls):
            return True
        for center in wire.CAP_BOLT_X_OFFSETS:
            if all(math.hypot(p[0]-center,p[1])+radius < cb_radius
                   for p in controls):
                return True
            side = 1 if center > 0 else -1
            if all(side*p[0] >= abs(center)+radius and abs(p[0])+radius < cap_half_min
                   and abs(p[1])+radius < cb_radius for p in controls):
                return True
        return False

    for segment in segments:
        assert _certify_hull(segment,enclosed), segment
    # Both receiving features are real consumers: losing either void must
    # reject the same modeled path, not silently accept sampled endpoints.
    assert not all(_certify_hull(segment, lambda controls: enclosed(
        controls, channel_half=radius)) for segment in segments)
    assert not all(_certify_hull(segment, lambda controls: enclosed(
        controls, cb_radius=hardware.SCREW_HEAD_DIA_MAX/2)) for segment in segments)
    # Nominal wrap torus, with the complete round section, fits the smallest
    # accepted counterbore. Chords/bends are separately certified above.
    assert wire.OUTER_BEND_RADIUS + radius < cb_radius_min
    assert wire.OUTER_BEND_RADIUS - radius > hardware.SCREW_HEAD_DIA_MAX/2 + hardware.SCREW_HEAD_ECCENTRICITY_MAX
    assert nas_low-wire.TWIST_RADIUS-radius > floor_max
    assert 2*(wire.TWIST_RADIUS+radius) < 2*channel_half_min


def _wire_clears_drilled_heads(segments, hole_diameter=hardware.SCREW_WIRE_HOLE_DIA_MIN):
    radius = hardware.WIRE_DIA / 2
    for center in wire.CAP_BOLT_X_OFFSETS:
        def enclosed(controls):
            # AABB lower distance bounds the complete convex control hull.
            # Merely finding each control outside a circle would NOT suffice.
            intervals = [(min(p[i] for p in controls),max(p[i] for p in controls))
                         for i in (0,1)]
            closest = [max(lo-value,0,value-hi)
                       for (lo,hi),value in zip(intervals,(center,0))]
            if math.hypot(*closest) > hardware.SCREW_HEAD_DIA_MAX/2 + hardware.SCREW_HEAD_ECCENTRICITY_MAX + radius:
                return True
            # Both diametral drill passages remain straight at every NAS W.
            # Relative Z is invariant when formed to the actual received head.
            return all(math.hypot(p[1],p[2]-hardware.SCREW_WIRE_HEIGHT)+radius
                       < hole_diameter/2 for p in controls)

        if not all(_certify_hull(segment,enclosed) for segment in segments):
            return False
    return True


def _nonadjacent_strands_clear(segments):
    # Spatial bins avoid an O(n²) all-pairs census. Ignore adjacent lengths
    # along the same bent strand, not separate turns or the return strand.
    diameter = hardware.WIRE_DIA
    bins = {}
    length = 0.0
    previous = None
    for segment in segments:
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
                                if math.dist(point,old_point) < diameter:
                                    return False
            bins.setdefault(cell, []).append((length,point))
    return True


def test_wire_drilled_legs_and_bridge_follow_the_shared_cap_pair():
    assert wire.CAP_BOLT_X_OFFSETS == cartridge.CAP_BOLT_X_OFFSETS
    segments = wire.installed_wire_segments()
    # Inspect the actual native sweep controls, not a separately moved mask
    # or envelope. Each new head axis must have a straight diametral leg.
    head_radius = hardware.SCREW_HEAD_DIA_MAX / 2
    for center in cartridge.CAP_BOLT_X_OFFSETS:
        assert any(
            all(abs(p[1]) < 1e-12 and abs(p[2] - wire.WIRE_AXIS_Z) < 1e-12
                for p in segment)
            and min(p[0] for p in segment) < center - head_radius
            and max(p[0] for p in segment) > center + head_radius
            for segment in segments
        )
    # The twisted bridge must leave the same physical approach length at
    # both heads when their shared X span changes.
    for center in cartridge.CAP_BOLT_X_OFFSETS:
        bridge_end = math.copysign(wire.BRIDGE_HALF_LENGTH, center)
        assert abs(center - bridge_end) == pytest.approx(wire.OUTER_BEND_RADIUS + 1.0)
        for side in (-1, 1):
            assert any(
                endpoint == pytest.approx((bridge_end, side * wire.TWIST_RADIUS, wire.WIRE_AXIS_Z))
                for segment in segments for endpoint in (segment[0], segment[-1])
            )


def test_wire_crosses_heads_only_through_the_real_diametral_drills():
    segments = wire.installed_wire_segments()
    assert _wire_clears_drilled_heads(segments)
    # Closing the real drill onto the wire, or moving a head passage sideways,
    # must fail instead of treating all wire/head contact as an exception.
    assert not _wire_clears_drilled_heads(segments, hole_diameter=hardware.WIRE_DIA)
    shifted = tuple(tuple((x,y+hardware.WIRE_DIA,z) for x,y,z in segment)
                    for segment in segments)
    assert not _wire_clears_drilled_heads(shifted)


def test_wire_nonadjacent_strands_do_not_overlap():
    assert _nonadjacent_strands_clear(wire.installed_wire_segments())


@pytest.mark.parametrize("name,value", (
    ("BRIDGE_HALF_LENGTH", 8.0),
    ("TWIST_RADIUS", hardware.WIRE_DIA / 4),
))
def test_strand_clearance_rejects_old_bridge_and_collapsed_twist(monkeypatch, name, value):
    monkeypatch.setattr(wire, name, value)
    assert not _nonadjacent_strands_clear(wire.installed_wire_segments())


def test_hardware_provider_does_not_import_its_cartridge_consumer():
    tree = ast.parse(Path(hardware.__file__).read_text(encoding="utf-8"))
    modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert "ch_rocker_arm_tl_oblique_retention_spec" not in modules
    assert all(not module.startswith("build_") for module in modules if module)


def test_capture_wire_uses_maximum_head_radius_and_complete_native_route():
    assert wire.OUTER_BEND_RADIUS == pytest.approx(
        hardware.SCREW_HEAD_DIA_MAX / 2
        + hardware.SCREW_HEAD_ECCENTRICITY_MAX
        + hardware.WIRE_DIA / 2 + 0.35
    )
    assert wire.ENTRY_SHOULDER_OFFSET == pytest.approx(0.20)
    assert wire.ENTRY_SHOULDER_RISE == pytest.approx(1.00)
    result = wire_capture.require_wire_capture_geometry()
    assert all(value > 0 for value in vars(result).values())
    assert result.surface_clearance == min(
        result.lateral_clearance, result.channel_floor_clearance, result.top_clearance
    )
    # This is the real head-bearing support, not a nonexistent closed X wall
    # at the enlarged counterbore's full-width outward mouth.
    assert result.head_support_x_clearance == pytest.approx(
        cartridge.capture_bounds().cap_head_floor_x_margin
    )


def test_capture_wire_consumes_the_shared_register_pose_bound(monkeypatch):
    captured = cartridge.capture_bounds()
    monkeypatch.setattr(
        cartridge, "capture_bounds",
        lambda: replace(
            captured,
            cap_register_endpoint_offset=2 * captured.cap_register_endpoint_offset,
        ),
    )
    with pytest.raises(ValueError, match="wire"):
        wire_capture.require_wire_capture_geometry()


def test_capture_wire_detects_changed_interior_height_not_only_endpoints():
    segments = wire.installed_wire_segments()
    # Alter a central bridge control while preserving every cubic endpoint.
    index = min(range(len(segments)), key=lambda i: max(abs(p[0]) for p in segments[i]))
    changed = [list(segment) for segment in segments]
    x, y, z = changed[index][1]
    changed[index][1] = (x, y, z + 6.0)
    changed = tuple(tuple(segment) for segment in changed)
    assert all(a[0] == b[0] and a[-1] == b[-1] for a, b in zip(segments, changed))
    with pytest.raises(ValueError, match="wire"):
        wire_capture.require_wire_capture_geometry(segments=changed)


def test_deep_groove_cannot_remove_the_guaranteed_head_bearing_floor():
    with pytest.raises(ValueError, match="head_bearing_floor_clearance"):
        wire_capture.require_wire_capture_geometry(channel_depth=9.0)


def test_whole_wire_certificate_cannot_pass_an_empty_route():
    with pytest.raises(ValueError, match="nonempty"):
        wire_capture.require_wire_capture_geometry(segments=())
