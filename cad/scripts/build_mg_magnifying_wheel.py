r"""Reproduction script: magnifying wheel (book ch. 21, pp. 50-53).

A gray cast-iron spider: a turned Ø100 rim on six tapered cast spokes and a
turned Ø30 hub boss. The boss carries an integral Ø.499 spigot on its front
(pen) side, on which the MHA-MG-10 brass drum is pressed. The lever wire wraps
the drum, the pen wire runs in the rim's U-groove: the wire-centre radii
49.2 / 9.85 give the wheel's 5x magnification. TIE 1 (lever wire) is an axial
#60 through the boss just outboard of the drum's O.D., counter-drilled #50
from the drum side; TIE 2 (pen wire) is a radial hole from the groove bottom
to the rim bore.

Layout: wheel axis = local Z through the origin, the origin on the spokes' and
rim's mid-plane (``mg_magnifying_wheel_geom``). The hub profile and the groove
are revolved on the Top plane, the plane through the seed spoke on +X and the
180 deg spoke that section A-A cuts (``_profile_mapper``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifying_wheel.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable

from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import _feature_by_name, name_last_feature
from _part_checks import measure_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    _record_origin_anchor,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle

import _telemetry
from _drawing_dimension_insert import (
    add_angular_reference_dimension,
    add_diametric_linear_dimension,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from _mg_wheel_rim_geometry import (
    GROOVE_BOTTOM_DIA,
    GROOVE_R,
    RIM_AXIAL,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    RIM_RING_RADIAL,
)
from mg_magnifying_wheel_geom import (
    BORE_DIA,
    CAST_ROUND_R,
    CAST_TOL,
    DRILL_POINT_DEG,
    HUB_BACK_Z,
    HUB_DIA,
    HUB_FILLET_R,
    HUB_FRONT_Z,
    HUB_LEN,
    HUB_STEP_Z,
    RIM_FILLET_R,
    SPIGOT_DIA,
    SPIGOT_LEN,
    SPOKE_AXIAL,
    SPOKE_COUNT,
    SPOKE_OVERLAP,
    SPOKE_ROOT_WIDTH,
    SPOKE_TIP_WIDTH,
    SPOKE_X0,
    SPOKE_X1,
    TIE1_CDRILL_DEPTH,
    TIE1_CDRILL_DIA,
    TIE1_X,
    TIE1_Y,
    TIE2_CLOCK_DEG,
    TIE_HOLE_DIA,
    clock_to_local_deg,
    fillet_area,
    fillets_volume,
    side_meets_circle,
    spoke_half_width,
    UNIT,
)
from mg_magnifying_wheel_spec import (
    CAST_DIMENSIONS,
    DIAMETER_REFERENCE,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HUB_FILLET_PRINTED,
    REFERENCE_DIAMETERS,
    REFERENCE_SKETCHES,
    REFERENCE_WITNESS_LEN,
    RIM_FILLET_PRINTED,
    SECTION_PLANE,
    SPOKE_PITCH_DEG,
    SPOKE_PITCH_PREFIX,
    SPOKE_PITCH_SPOKES,
    SPOKE_REFERENCE,
    SPOKE_FACE_OFFSET,
    SPOKE_STUB_R,
    SURFACE_FINISHES,
    TIE2_CLOCK_SPOKE,
    TIE2_FROM_SPOKE_DEG,
)
from mg_wheel_bar_geom import WHEEL_BAR_Y as _YOKE_WHEEL_Y

PART_NAME = "mg-magnifying-wheel"
MATERIAL = "Gray Cast Iron"  # see _appearance.apply_material docstring

# Wheel nominals live in mg_magnifying_wheel_geom (imported above).

# --- WIRE-1 yoke point (the coupling mate's wheel-side geometry) --------------
# ``WireYokePoint``: a reference point on the hub PITCH circle (groove radius +
# wire radius) at the lever-wire's tangency azimuth, in the wheel mid-plane. The
# magnifier assembly holds it COINCIDENT to the lever-wire's Top plane, tying the
# wheel's spin to the lever group's travel along the wire (the linearized
# inextensible-wire constraint -- see sh_vn_music_wire_lever_geom's docstring). The azimuth
# is layout-derived, so it is imported from sh_vn_music_wire_lever_geom: a layout move
# re-tangents the wire AND re-stamps this point in one rebuild.
from sh_vn_music_wire_lever_geom import (  # noqa: E402
    WHEEL_X as _YOKE_WHEEL_X,
    YOKE_POINT as _YOKE_POINT,
)

# The wheel is placed at IDENTITY, so the yoke point's local offset IS the
# machine offset from the wheel centre. (Pre-#151 this was authored x-NEGATED
# to survive the chirality mirror's double flip -- the imported tangency
# azimuth was itself in the mirrored frame, so the two negations cancelled to
# the same +10.1225 the machine-handed layout gives directly.)
YOKE_LOCAL_X = _YOKE_POINT[0] - _YOKE_WHEEL_X
YOKE_LOCAL_Y = _YOKE_POINT[1] - _YOKE_WHEEL_Y

# --- Feature volumes (mm^3), one gate per feature ---------------------------------
_RIM_R = RIM_OUTER_DIA / 2.0
_RIM_IN_R = RIM_INNER_DIA / 2.0
_HUB_R = HUB_DIA / 2.0
_SPIGOT_R = SPIGOT_DIA / 2.0
_BORE_R = BORE_DIA / 2.0
_TIE_R = TIE_HOLE_DIA / 2.0
_GROOVE_CENTRE_R = GROOVE_BOTTOM_DIA / 2.0 + GROOVE_R  # 49.708
# The groove walls run past the rim OD so the cut opens cleanly.
_GROOVE_TOP_R = _RIM_R + 0.5
_BOSS_LEN = HUB_LEN - SPIGOT_LEN  # 10.6, back face to the step


def _spoke_area(r_in: float, r_out: float, steps: int = 20000) -> float:
    """Seed-spoke trapezoid area between the circles ``r_in`` and ``r_out``."""
    dx = (SPOKE_X1 - SPOKE_X0) / steps
    area = 0.0
    for i in range(steps):
        x = SPOKE_X0 + (i + 0.5) * dx
        half = spoke_half_width(x)
        y_out = math.sqrt(max(0.0, r_out * r_out - x * x))
        y_in = math.sqrt(max(0.0, r_in * r_in - x * x))
        area += 2.0 * max(0.0, min(half, y_out) - y_in) * dx
    return area


def _tie2_volume(steps: int = 400) -> float:
    """Rim material the radial TIE 2 hole removes: groove floor to rim bore,
    over the hole's disc (tangential u, axial v)."""
    d = TIE_HOLE_DIA / steps
    total = 0.0
    for i in range(steps):
        u = -_TIE_R + (i + 0.5) * d
        for j in range(steps):
            v = -_TIE_R + (j + 0.5) * d
            if u * u + v * v > _TIE_R * _TIE_R:
                continue
            floor = _GROOVE_CENTRE_R - math.sqrt(GROOVE_R * GROOVE_R - v * v)
            outer = math.sqrt(floor * floor - u * u)
            inner = math.sqrt(_RIM_IN_R * _RIM_IN_R - u * u)
            total += max(0.0, outer - inner) * d * d
    return total


V_RIM = math.pi * (_RIM_R**2 - _RIM_IN_R**2) * RIM_AXIAL
V_SPOKE_FREE = SPOKE_AXIAL * _spoke_area(0.0, _RIM_IN_R)  # before the hub exists
V_SPOKE_WEB = SPOKE_AXIAL * _spoke_area(_HUB_R, _RIM_IN_R)  # outside the hub
V_HUB = math.pi * (_HUB_R**2 * _BOSS_LEN + _SPIGOT_R**2 * SPIGOT_LEN)
V_BORE = math.pi * _BORE_R**2 * HUB_LEN
V_HUB_FILLETS = 2 * SPOKE_COUNT * SPOKE_AXIAL * fillet_area(_HUB_R, HUB_FILLET_R, True)
V_RIM_FILLETS = (
    2 * SPOKE_COUNT * SPOKE_AXIAL * fillet_area(_RIM_IN_R, RIM_FILLET_R, False)
)
if abs(V_HUB_FILLETS + V_RIM_FILLETS - fillets_volume()) > 1e-6:
    raise AssertionError("fillet gates do not sum to the geom's fillets_volume()")
# Each R1 round removes a spandrel (1 - pi/4) R^2 swept about the axis at its
# centroid, 0.2234 R in from the rim-bore corner (Pappus).
_SPANDREL_OFFSET = (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi) * CAST_ROUND_R
V_ROUNDS = (
    2
    * (1.0 - math.pi / 4.0)
    * CAST_ROUND_R**2
    * 2.0
    * math.pi
    * (_RIM_IN_R + _SPANDREL_OFFSET)
)
# The U-groove: the band from its centre circle to the OD plus the round
# bottom's half disc, each swept about the axis at its centroid (Pappus).
_GROOVE_BAND = 2.0 * GROOVE_R * (_RIM_R - _GROOVE_CENTRE_R)
_GROOVE_HALF_DISC = math.pi * GROOVE_R**2 / 2.0
V_GROOVE = (
    2.0
    * math.pi
    * (
        _GROOVE_BAND * (_RIM_R + _GROOVE_CENTRE_R) / 2.0
        + _GROOVE_HALF_DISC * (_GROOVE_CENTRE_R - 4.0 * GROOVE_R / (3.0 * math.pi))
    )
)
V_TIE1 = math.pi * _TIE_R**2 * _BOSS_LEN
# TIE 1's #50 counter-drill beyond the #60 already through: the annulus
# between the two Ø down to the shoulder, then its 118 deg point's frustum
# from the #50 down to the #60's Ø (the point's tip lies in the #60's air).
_TIE1_CDRILL_R = TIE1_CDRILL_DIA / 2.0
_POINT_PER_R = 1.0 / math.tan(math.radians(DRILL_POINT_DEG / 2.0))
_POINT_LEN = (_TIE1_CDRILL_R - _TIE_R) * _POINT_PER_R
V_TIE1_POINT = (
    math.pi
    * _POINT_LEN
    / 3.0
    * (_TIE1_CDRILL_R**2 + _TIE1_CDRILL_R * _TIE_R + _TIE_R**2)
    - math.pi * _TIE_R**2 * _POINT_LEN
)
V_TIE1_CDRILL = (
    math.pi * (_TIE1_CDRILL_R**2 - _TIE_R**2) * TIE1_CDRILL_DEPTH + V_TIE1_POINT
)
V_TIE2 = _tie2_volume()

# --- TIE 2 profile: a half rectangle beside its radial axis, revolve-cut -------
# The axis runs radially at TIE2_CLOCK_DEG from inside the rim bore out past the
# groove floor. Its inner end runs HORIZONTAL, in the air inside the rim bore.
_TIE2_LOCAL = math.radians(clock_to_local_deg(TIE2_CLOCK_DEG))
_TIE2_U = (math.cos(_TIE2_LOCAL), math.sin(_TIE2_LOCAL))
_TIE2_W = (-_TIE2_U[1], _TIE2_U[0])
_TIE2_IN_R = _RIM_IN_R - 1.5  # the full bore starts inside the rim bore
_TIE2_OUT_R = _GROOVE_CENTRE_R + 0.1  # ends in the groove's air
if abs(_TIE2_U[1]) < 1e-6 or abs(_TIE2_U[0]) < 1e-6:
    raise AssertionError("TIE 2 must run oblique to the sketch axes")


def _tie2_profile() -> list[tuple[float, float]]:
    """[P_in, P_out, Q_out, Q_in]: the axis, the outer end square to it, the
    hole's wall, and the horizontal inner end back to the axis."""
    p_in = (_TIE2_IN_R * _TIE2_U[0], _TIE2_IN_R * _TIE2_U[1])
    p_out = (_TIE2_OUT_R * _TIE2_U[0], _TIE2_OUT_R * _TIE2_U[1])
    q_out = (p_out[0] + _TIE_R * _TIE2_W[0], p_out[1] + _TIE_R * _TIE2_W[1])
    # The wall line meets the horizontal through P_in at t along U.
    t = -_TIE_R * _TIE2_W[1] / _TIE2_U[1]
    q_in = (
        p_in[0] + _TIE_R * _TIE2_W[0] + t * _TIE2_U[0],
        p_in[1] + _TIE_R * _TIE2_W[1] + t * _TIE2_U[1],
    )
    if math.hypot(*q_in) > _RIM_IN_R - 0.5:
        raise AssertionError("TIE 2's inner end must stay inside the rim bore")
    return [p_in, p_out, q_out, q_in]


def _relate(adapter, rows) -> None:
    """Apply ``(label, first, second, relation)`` sketch relations."""
    for label, first, second, relation in rows:
        check(label, adapter.add_sketch_constraint(first, second, relation))


def _fillet(adapter, radius: float, picks, name: str, dim: str) -> None:
    check(f"fillet {name}", adapter.add_fillet(radius, picks, propagate=False))
    name_last_feature(adapter, name)
    name_dimensions(adapter, name, [dim])


def _spoke_edge_picks(circle_r: float, printed: tuple[int, int]) -> list[list[float]]:
    """Mid-height points on each spoke side's junction edge with the circle,
    the ``printed`` (spoke, side) edge first: the drawing's imported radius
    lands on the first pick's edge (mg_magnifying_wheel_spec.HUB_FILLET_PRINTED)."""
    x, y = side_meets_circle(circle_r)
    picks = []
    for k in range(SPOKE_COUNT):
        a = math.radians(k * 360.0 / SPOKE_COUNT)
        for py in (y, -y):
            picks.append(
                [
                    x * math.cos(a) - py * math.sin(a),
                    x * math.sin(a) + py * math.cos(a),
                    0.0,
                ]
            )
    spoke, side = printed
    first = 2 * spoke + (0 if side > 0 else 1)
    return [picks[first], *picks[:first], *picks[first + 1 :]]


def _section_plane(adapter) -> None:
    """Section A-A's cutting plane, named and hidden: coincident with the Top
    plane (model Y = 0, through the wheel axis and the 0 and 180 deg spokes),
    the plane A-A cuts.  A hidden sketch on a bare standard plane imports
    nothing into a section, and an offset plane cannot sit at zero offset, so
    it is InsertRefPlane's Coincident constraint on the selected Top plane
    (build_ch_rocker_arm_tl_oblique_carrier's section plane)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "Top Plane", "PLANE", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"plane {SECTION_PLANE}: cannot select the Top plane")
    feature_manager = _early_bound(model.FeatureManager, "IFeatureManager")
    # swRefPlaneReferenceConstraint_Coincident = 4
    if feature_manager.InsertRefPlane(4, 0.0, 0, 0.0, 0, 0.0) is None:
        raise RuntimeError(f"plane {SECTION_PLANE}: InsertRefPlane failed")
    model.ClearSelection2(True)
    name_last_feature(adapter, SECTION_PLANE)
    blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))


def _require_on_section_plane(adapter, sketch: str) -> None:
    """create_sketch falls back to a standard plane when a named one fails to
    select; the sketch's parents must name SECTION_PLANE."""
    feature = _early_bound(_feature_by_name(adapter, sketch), "IFeature")
    parents = [
        str(_early_bound(parent, "IFeature").Name)
        for parent in (feature.GetParents() or ())
    ]
    if SECTION_PLANE not in parents:
        raise RuntimeError(f"{sketch} is not on {SECTION_PLANE}: parents {parents}")


def _sketch_mapper(
    adapter, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign)
    (build_ch_rocker_arm_tl_oblique_carrier's mapper): a plane coincident with
    the Top plane need not keep its sketch axes' senses."""
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"{label}: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    base = raw((0.0, 0.0, 0.0))
    for axis, want in ((u_axis, 0), (v_axis, 1)):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        delta = [m - b for m, b in zip(raw(tuple(unit)), base, strict=True)]
        if abs(abs(delta[want]) - 1.0) > 1e-6:
            raise RuntimeError(
                f"{label}: model axis {axis} maps to sketch {delta!r}, not along "
                f"sketch {'uv'[want]}"
            )

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        u, v, w = raw(model_mm)
        if abs(w) > 1e-4:
            raise RuntimeError(f"{label}: {model_mm} is {w:g} mm off the sketch")
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


# The turned profiles lie in A-A's plane (the Top plane): the axis runs along
# the sketch's v (model Z) and every radius along its u (model X), so an
# axial line is vertical in the sketch and a radial one horizontal.
_AXIAL = "vertical"
_RADIAL = "horizontal"
_AXIAL_DISTANCE = "vertical_distance"
_RADIAL_DISTANCE = "horizontal_distance"
# Two points at one axial station / on one radius.
_SAME_STATION = "horizontal_points"
_SAME_RADIUS = "vertical_points"


def _profile_mapper(
    adapter, *, label: str
) -> tuple[Callable[[float, float], tuple[float, float]], bool]:
    """Map a turned profile point (a, r) into the ACTIVE Top-plane sketch:
    ``a`` the axial coordinate -z (the half-profile's own frame, front face
    to the right), ``r`` the radius out along model +X, the seed spoke's
    side, which A-A stands upward.  Returns the map and whether it mirrors
    the (a, r) frame: SketchManager.CreateArc always runs counter-clockwise,
    so a mirrored frame draws each arc from its far end."""
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=2, label=label)

    def to_profile(a: float, r: float) -> tuple[float, float]:
        return to_sketch((r, 0.0, -a))

    origin = to_profile(0.0, 0.0)
    along_a = [p - o for p, o in zip(to_profile(1.0, 0.0), origin, strict=True)]
    along_r = [p - o for p, o in zip(to_profile(0.0, 1.0), origin, strict=True)]
    mirrored = along_a[0] * along_r[1] - along_a[1] * along_r[0] < 0.0
    return to_profile, mirrored


# The reference sketch's axis is the bore's centreline in A-A: it runs the
# hub's length and this far past each end face, clear of the Ø30's text.
_CENTRELINE_OVERRUN = 2.0


def _diameter_reference(adapter) -> list[tuple[str, str]]:
    """Section A-A's rim diameters and the spokes' back face
    (mg_magnifying_wheel_spec.DIAMETER_REFERENCE).

    A hidden sketch on SECTION_PLANE: the wheel axis as a centreline, and on
    each rim surface a construction witness REFERENCE_WITNESS_LEN long, the
    OD's from the rim's back face, the rim bore's from the back rim-bore
    round's tangent.  Each Ø is a diametric dimension from the axis to its
    witness's start, driven from the global its Front-plane circle is driven
    from, so the sketch restates the geometry and moves with it.  A third
    witness starts where the spokes' back face meets the rim bore, and
    SpokeFaceOffset locates it from the OD witness's start along the axis
    (SPOKE_FACE_OFFSET): the part owns that size and its casting band, so A-A
    imports it like the spokes' thickness.  It adds no volume.
    """
    feature = DIAMETER_REFERENCE
    _section_plane(adapter)
    check(f"create_sketch {feature}", adapter.create_sketch(SECTION_PLANE))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=2, label=feature)
    axis_start = to_sketch((0.0, 0.0, HUB_BACK_Z + _CENTRELINE_OVERRUN))
    axis_end = to_sketch((0.0, 0.0, HUB_FRONT_Z - _CENTRELINE_OVERRUN))
    back = RIM_AXIAL / 2.0
    witnesses = (
        # (dimension, global, radius, model z of the witness start)
        ("RimOuterDiaDim", '"RimOuterDia"', _RIM_R, back),
        ("RimInnerDiaDim", '"RimInnerDia"', _RIM_IN_R, back - CAST_ROUND_R),
    )
    set_sketch_direct_db(adapter, True)
    axis = check(
        f"{feature} axis", adapter.add_centerline(*axis_start, *axis_end)
    )
    lines = []
    for name, _drive, radius, z in witnesses:
        start = to_sketch((radius, 0.0, z))
        end = to_sketch((radius, 0.0, z - REFERENCE_WITNESS_LEN))
        lines.append(
            check(f"{feature} {name} witness", adapter.add_line(*start, *end))
        )
    face_z = SPOKE_AXIAL / 2.0
    face_start = to_sketch((_RIM_IN_R, 0.0, face_z))
    face_end = to_sketch((_RIM_IN_R, 0.0, face_z - REFERENCE_WITNESS_LEN))
    face = check(
        f"{feature} SpokeFaceOffset witness",
        adapter.add_line(*face_start, *face_end),
    )
    set_sketch_direct_db(adapter, False)
    for line in (*lines, face):
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{feature} {line}: construction flag rejected")
    for line in (axis, *lines, face):
        check(
            f"{feature} {line} axial",
            adapter.add_sketch_constraint(line, None, _AXIAL),
        )
    dims = SketchDims()
    anchor_point_to_origin(
        adapter, f"{axis}.start", *axis_start, f"{feature} axis start"
    )
    dims.record(None)
    check(
        f"{feature} axis length",
        adapter.add_sketch_dimension(
            axis, None, "linear", HUB_LEN + 2.0 * _CENTRELINE_OVERRUN
        ),
    )
    dims.record(None)
    for line, (name, _drive, _radius, z) in zip(lines, witnesses, strict=True):
        dimension_between(
            adapter,
            f"{line}.start",
            "origin",
            _AXIAL_DISTANCE,
            abs(z),
            f"{feature} {name} witness station",
        )
        dims.record(None)
        check(
            f"{feature} {name} witness length",
            adapter.add_sketch_dimension(
                line, None, "linear", REFERENCE_WITNESS_LEN
            ),
        )
        dims.record(None)
    for line, (name, drive, radius, _z) in zip(lines, witnesses, strict=True):
        add_diametric_linear_dimension(
            adapter,
            axis,
            f"{line}.start",
            to_sketch((radius + 4.0, 0.0, back)),
            name,
        )
        dims.record(name, drive)
    # The spokes' back-face witness: on the rim bore's radius, its length,
    # and located from the OD witness's start (the rim's back face).
    dimension_between(
        adapter,
        f"{face}.start",
        "origin",
        _RADIAL_DISTANCE,
        _RIM_IN_R,
        f"{feature} SpokeFaceOffset witness radius",
    )
    dims.record(None)
    check(
        f"{feature} SpokeFaceOffset witness length",
        adapter.add_sketch_dimension(
            face, None, "linear", REFERENCE_WITNESS_LEN
        ),
    )
    dims.record(None)
    dimension_between(
        adapter,
        f"{lines[0]}.start",
        f"{face}.start",
        _AXIAL_DISTANCE,
        SPOKE_FACE_OFFSET,
        "SpokeFaceOffset",
    )
    dims.record("SpokeFaceOffset")
    ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", adapter.exit_sketch())
    name_last_feature(adapter, feature)
    _require_on_section_plane(adapter, feature)
    return dims.apply(adapter, feature)


def _spoke_reference(adapter) -> list[tuple[str, str]]:
    """The spoke pattern's pitch and TIE 2's clock
    (mg_magnifying_wheel_spec.SPOKE_REFERENCE).

    A hidden Front-plane sketch of construction stubs through the rim, each
    end anchored on its radial, in pairs: the centrelines of
    SPOKE_PITCH_SPOKES, and the TIE2_CLOCK_SPOKE spoke's with TIE 2's axis.
    Each pair's DRIVEN angle (vertex on the bore axis) restates the pattern
    and the hole's clock without driving either.  It adds no volume.
    """
    feature = SPOKE_REFERENCE
    check(f"create_sketch {feature}", adapter.create_sketch("Front"))
    clock_spoke = TIE2_CLOCK_SPOKE * SPOKE_PITCH_DEG
    pairs = (
        (
            "SpokePitch",
            "spoke pitch",
            [k * SPOKE_PITCH_DEG for k in SPOKE_PITCH_SPOKES],
            SPOKE_PITCH_DEG,
        ),
        (
            "Tie2Clock",
            "tie 2 clock",
            [clock_spoke, clock_spoke + TIE2_FROM_SPOKE_DEG],
            TIE2_FROM_SPOKE_DEG,
        ),
    )
    stubs = []
    set_sketch_direct_db(adapter, True)
    for _name, label, bearings, _degrees in pairs:
        for bearing in bearings:
            a = math.radians(bearing)
            ends = [(r * math.cos(a), r * math.sin(a)) for r in SPOKE_STUB_R]
            line = check(
                f"{feature} {label} {bearing:g} deg centreline",
                adapter.add_centerline(*ends[0], *ends[1]),
            )
            stubs.append((line, ends))
    set_sketch_direct_db(adapter, False)
    dims = SketchDims()
    for line, ends in stubs:
        for end_ref, point in zip((f"{line}.start", f"{line}.end"), ends, strict=True):
            anchor_point_to_origin(
                adapter, end_ref, *point, f"{feature} {end_ref}"
            )
            _record_origin_anchor(dims, *point, None, None, None, None)
    for index, (name, label, bearings, degrees) in enumerate(pairs):
        between = math.radians(sum(bearings) / 2.0)
        add_angular_reference_dimension(
            adapter,
            stubs[2 * index][0],
            stubs[2 * index + 1][0],
            (SPOKE_STUB_R[0] * math.cos(between), SPOKE_STUB_R[0] * math.sin(between)),
            label,
            expected_degrees=degrees,
        )
        dims.record(name)
    ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return dims.apply(adapter, feature)


# TIE 1's counter-drill is drawn on a plane through TIE 1's axis parallel to
# the Top plane (A-A's), the plane section B-B cuts, so its Ø and depth
# print there.
_TIE1_PLANE = "Tie1Plane"


def _tie1_counter_drill(adapter) -> list[tuple[str, str]]:
    """TIE 1's #50 counter-drill from the boss front (drum) face (owner ruling
    2026-11-20 on #2406: "A"), revolve-cut on _TIE1_PLANE: a half profile
    beside TIE 1's axis -- the mouth on the front face, the #50's wall to
    its shoulder, the 118 deg point back to the axis.  The plane stands off
    the Top plane by "Tie1Y"; the mouth runs from the origin by "Tie1X" and
    by the front face's station ("HubFrontZ" - "SpigotLength"), so the
    counter-drill moves with the #60 and the boss.  Its Ø and depth are
    named and driven for B-B (drawing-guidelines.md rule 12); the point's
    length is the #50's 118 deg point, as drawn.  The key pin's chord hole
    on a station plane is the recipe (build_pd_transgear_disc_hub
    ._key_pin_hole).  Returns the deferred drive jobs."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create_plane {_TIE1_PLANE}",
        adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=TIE1_Y)
        ),
    )
    name_last_feature(adapter, _TIE1_PLANE)
    jobs = [(name_dimensions(adapter, _TIE1_PLANE, ["Tie1PlaneY"])[0], '"Tie1Y"')]
    blank_reference_geometry(adapter, ((_TIE1_PLANE, "PLANE"),))

    sd = SketchDims()
    check("create_sketch tie 1 counter-drill", adapter.create_sketch(_TIE1_PLANE))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=2, label="tie 1 counter-drill")
    origin = to_sketch((0.0, TIE1_Y, 0.0))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"tie 1 counter-drill: sketch origin maps to {origin}")
    shoulder_z = HUB_STEP_Z + TIE1_CDRILL_DEPTH
    point_len = _TIE1_CDRILL_R * _POINT_PER_R
    wall_x = TIE1_X + _TIE1_CDRILL_R
    mouth, rim, shoulder, tip = (
        to_sketch((x, TIE1_Y, z))
        for x, z in (
            (TIE1_X, HUB_STEP_Z),
            (wall_x, HUB_STEP_Z),
            (wall_x, shoulder_z),
            (TIE1_X, shoulder_z + point_len),
        )
    )
    set_sketch_direct_db(adapter, True)
    axis = check("tie 1 counter-drill axis", adapter.add_centerline(*mouth, *tip))
    set_sketch_direct_db(adapter, False)
    mouth_line, wall, cone, on_axis = add_line_chain(
        adapter, [mouth, rim, shoulder, tip]
    )
    _relate(
        adapter,
        (
            ("tie 1 counter-drill axis along TIE 1", axis, None, _AXIAL),
            (
                "tie 1 counter-drill profile on the axis, mouth",
                f"{axis}.start",
                f"{on_axis}.end",
                "coincident",
            ),
            (
                "tie 1 counter-drill profile on the axis, tip",
                f"{axis}.end",
                f"{on_axis}.start",
                "coincident",
            ),
            ("tie 1 counter-drill mouth on the face", mouth_line, None, _RADIAL),
            ("tie 1 counter-drill wall along the axis", wall, None, _AXIAL),
        ),
    )
    anchor_point_to_origin(
        adapter, f"{axis}.start", *mouth, "tie 1 counter-drill mouth"
    )
    _record_origin_anchor(
        sd,
        *mouth,
        "Tie1CdrillX",
        "Tie1CdrillZ",
        '"Tie1X"',
        '"HubFrontZ" - "SpigotLength"',
    )
    dimension_between(
        adapter,
        f"{wall}.start",
        f"{wall}.end",
        _AXIAL_DISTANCE,
        TIE1_CDRILL_DEPTH,
        "Tie1CdrillDepth",
    )
    sd.record("Tie1CdrillDepth", '"Tie1CdrillDepth"')
    dimension_between(
        adapter,
        f"{cone}.start",
        f"{cone}.end",
        _AXIAL_DISTANCE,
        point_len,
        "tie 1 counter-drill point",
    )
    sd.record("Tie1CdrillPoint")
    add_diametric_linear_dimension(
        adapter,
        axis,
        wall,
        to_sketch((wall_x + 3.0, TIE1_Y, HUB_STEP_Z - 3.0)),
        "Tie1CdrillDia",
    )
    sd.record("Tie1CdrillDia", '"Tie1CdrillDia"')
    ensure_fully_defined(adapter, "tie 1 counter-drill sketch")
    check("exit_sketch tie 1 counter-drill", adapter.exit_sketch())
    name_last_feature(adapter, "Tie1CdrillProfile")
    return jobs + sd.apply(adapter, "Tie1CdrillProfile")


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 100 = 100 in). SPOKE_COUNT is a pattern
    # instance count, not a sketch length, so it stays a Python constant.
    set_global(adapter, "RimOuterDia", f"{RIM_OUTER_DIA}mm")
    set_global(adapter, "RimRingRadial", f"{RIM_RING_RADIAL}mm")
    set_global(adapter, "RimInnerDia", '"RimOuterDia" - 2 * "RimRingRadial"')
    set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    set_global(adapter, "HubLength", f"{HUB_LEN}mm")
    set_global(adapter, "HubFrontZ", f"{-HUB_FRONT_Z}mm")
    set_global(adapter, "SpigotDia", f"{SPIGOT_DIA}mm")
    set_global(adapter, "SpigotLength", f"{SPIGOT_LEN}mm")
    set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    set_global(adapter, "SpokeAxial", f"{SPOKE_AXIAL}mm")
    set_global(adapter, "SpokeOverlap", f"{SPOKE_OVERLAP}mm")
    set_global(adapter, "SpokeRootWidth", f"{SPOKE_ROOT_WIDTH}mm")
    set_global(adapter, "SpokeTipWidth", f"{SPOKE_TIP_WIDTH}mm")
    set_global(adapter, "SpokeX0", '"HubDia" / 2 - "SpokeOverlap"')
    set_global(adapter, "SpokeX1", '"RimInnerDia" / 2 + "SpokeOverlap"')
    set_global(adapter, "GrooveR", f"{GROOVE_R}mm")
    set_global(adapter, "GrooveBottomDia", f"{GROOVE_BOTTOM_DIA}mm")
    set_global(adapter, "TieHoleDia", f"{TIE_HOLE_DIA}mm")
    set_global(adapter, "Tie1X", f"{TIE1_X}mm")
    set_global(adapter, "Tie1Y", f"{-TIE1_Y}mm")
    set_global(adapter, "Tie1CdrillDia", f"{TIE1_CDRILL_DIA}mm")
    set_global(adapter, "Tie1CdrillDepth", f"{TIE1_CDRILL_DEPTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rim ring (annulus, mid-plane symmetric). Two on-axis circles: each emits
    # only its diameter dim.
    rim_sd = SketchDims()
    check("create_sketch rim", adapter.create_sketch("Front"))
    define_circle(
        adapter,
        0.0,
        0.0,
        _RIM_R,
        "rim OD",
        dims=rim_sd,
        names=("RimOdCx", "RimOdCz", "RimOdCircleDia"),
        drives=(None, None, '"RimOuterDia"'),
    )
    define_circle(
        adapter,
        0.0,
        0.0,
        _RIM_IN_R,
        "rim ID",
        dims=rim_sd,
        names=("RimIdCx", "RimIdCz", "RimIdCircleDia"),
        drives=(None, None, '"RimInnerDia"'),
    )
    ensure_fully_defined(adapter, "rim sketch")
    check("exit_sketch rim", adapter.exit_sketch())
    name_last_feature(adapter, "RimProfile")
    drive_jobs += rim_sd.apply(adapter, "RimProfile")
    check(
        "extrude rim",
        adapter.create_extrusion(
            ExtrusionParameters(depth=RIM_AXIAL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Rim")
    volume = volume_check(adapter, "rim", V_RIM, 0.002 * V_RIM)

    # Named wheel axis (local Z = Top x Right): the spoke pattern rotates about
    # it, and the M6 assembly mates the wheel on the axle by it. Created before
    # the pattern so the pattern selects it by name.
    wheel_axis = name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "wheel axis"
    )

    # Seed spoke along +X, tapering from the root (inside the hub's circle) to
    # the tip (inside the rim). Record each display dim in CREATION order: the
    # two end widths, then the root and tip corner anchors (x, then y).
    spoke_sd = SketchDims()
    check("create_sketch spoke", adapter.create_sketch("Front"))
    h0 = SPOKE_ROOT_WIDTH / 2.0
    h1 = SPOKE_TIP_WIDTH / 2.0
    bottom, tip, _top, root = add_line_chain(
        adapter, [(SPOKE_X0, -h0), (SPOKE_X1, -h1), (SPOKE_X1, h1), (SPOKE_X0, h0)]
    )
    _relate(
        adapter,
        (
            ("spoke root vertical", root, None, "vertical"),
            ("spoke tip vertical", tip, None, "vertical"),
        ),
    )
    check(
        "spoke root width",
        adapter.add_sketch_dimension(root, None, "linear", SPOKE_ROOT_WIDTH),
    )
    spoke_sd.record("SpokeRootWidth", '"SpokeRootWidth"')
    check(
        "spoke tip width",
        adapter.add_sketch_dimension(tip, None, "linear", SPOKE_TIP_WIDTH),
    )
    spoke_sd.record("SpokeTipWidth", '"SpokeTipWidth"')
    anchor_point_to_origin(
        adapter, f"{bottom}.start", SPOKE_X0, -h0, "spoke root"
    )
    spoke_sd.record("SpokeX0", '"SpokeX0"')
    spoke_sd.record("SpokeRootY", '"SpokeRootWidth" / 2')  # unsigned half-width
    anchor_point_to_origin(adapter, f"{tip}.start", SPOKE_X1, -h1, "spoke tip")
    spoke_sd.record("SpokeX1", '"SpokeX1"')
    spoke_sd.record("SpokeTipY", '"SpokeTipWidth" / 2')
    ensure_fully_defined(adapter, "spoke sketch")
    check("exit_sketch spoke", adapter.exit_sketch())
    name_last_feature(adapter, "SpokeProfile")
    drive_jobs += spoke_sd.apply(adapter, "SpokeProfile")
    check(
        "extrude spoke",
        adapter.create_extrusion(
            ExtrusionParameters(depth=SPOKE_AXIAL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Spoke")
    spoke_depth = name_dimensions(adapter, "Spoke", ["SpokeAxial"])
    drive_jobs.append((spoke_depth[0], '"SpokeAxial"'))

    # Pattern the spoke BEFORE the stepped hub revolve: circular patterns on
    # stepped revolved bodies fail to create (_features reeding probe), while
    # this body is still extrusions only. The spokes already join through the
    # rim, so the pattern is one body.
    check(
        f"circular pattern {SPOKE_COUNT} spokes",
        adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name=wheel_axis,
                features=["Spoke"],
                count=SPOKE_COUNT,
            )
        ),
    )
    name_last_feature(adapter, "SpokePattern")
    volume = volume_check(
        adapter,
        "rim + spokes",
        volume + SPOKE_COUNT * V_SPOKE_FREE,
        0.002 * (volume + SPOKE_COUNT * V_SPOKE_FREE),
    )

    # Hub: ONE stepped half-profile in A-A's plane (_profile_mapper: axial
    # a = -z, radius on +X): the Ø30 boss from its back face to the step, then
    # the Ø.499 spigot to its front face, revolved about the axis line.
    hub_sd = SketchDims()
    back_x, step_x, front_x = -HUB_BACK_Z, -HUB_STEP_Z, -HUB_FRONT_Z
    check("create_sketch hub", adapter.create_sketch("Top"))
    hub_point, _ = _profile_mapper(adapter, label="hub sketch")
    set_sketch_direct_db(adapter, True)
    hub_axis = check(
        "hub axis centerline",
        adapter.add_centerline(*hub_point(back_x, 0.0), *hub_point(front_x, 0.0)),
    )
    back, boss, step, spigot, front, axis_line = add_line_chain(
        adapter,
        [
            hub_point(back_x, 0.0),
            hub_point(back_x, _HUB_R),
            hub_point(step_x, _HUB_R),
            hub_point(step_x, _SPIGOT_R),
            hub_point(front_x, _SPIGOT_R),
            hub_point(front_x, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    for line, direction in (
        (back, _RADIAL),
        (boss, _AXIAL),
        (step, _RADIAL),
        (spigot, _AXIAL),
        (front, _RADIAL),
        (axis_line, _AXIAL),
    ):
        check(
            f"hub {direction} {line}",
            adapter.add_sketch_constraint(line, None, direction),
        )
    # The spigot's front face sits HUB_FRONT_Z below the spokes' mid-plane
    # (the origin): every axial size reads from that one faced end
    # (drawing-guidelines.md rule 11 (turned parts read like the lathe)), the spigot length the drum's recess needs among them.
    anchor_point_to_origin(
        adapter, f"{front}.end", *hub_point(front_x, 0.0), "hub spigot front face"
    )
    hub_sd.record("HubFrontZ", '"HubFrontZ"')
    dimension_between(
        adapter,
        f"{back}.start",
        f"{front}.end",
        _AXIAL_DISTANCE,
        HUB_LEN,
        "HubLength",
    )
    hub_sd.record("HubLength", '"HubLength"')
    dimension_between(
        adapter,
        f"{step}.start",
        f"{front}.end",
        _AXIAL_DISTANCE,
        SPIGOT_LEN,
        "SpigotLength",
    )
    hub_sd.record("SpigotLength", '"SpigotLength"')
    add_diametric_linear_dimension(
        adapter, hub_axis, boss, hub_point(back_x + 3.0, _HUB_R + 4.0), "HubDia"
    )
    hub_sd.record("HubDia", '"HubDia"')
    add_diametric_linear_dimension(
        adapter,
        hub_axis,
        spigot,
        hub_point(front_x - 3.0, _SPIGOT_R + 4.0),
        "SpigotDia",
    )
    hub_sd.record("SpigotDia", '"SpigotDia"')
    ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub_sd.apply(adapter, "HubProfile")
    check("revolve hub", adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "HubBody")
    v_spoke_in_hub = SPOKE_COUNT * (V_SPOKE_FREE - V_SPOKE_WEB)
    volume = volume_check(
        adapter, "hub", volume + V_HUB - v_spoke_in_hub, 0.002 * V_HUB
    )

    # Axle bore through the boss and spigot. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", adapter.create_sketch("Front"))
    define_circle(
        adapter,
        0.0,
        0.0,
        _BORE_R,
        "bore",
        dims=bore_sd,
        names=("BoreCx", "BoreCz", "BoreDiaDim"),
        drives=(None, None, '"BoreDia"'),
    )
    ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore_sd.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * -HUB_FRONT_Z + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    volume = volume_check(adapter, "bore", volume - V_BORE, 0.02 * V_BORE)

    # Section A-A's rim diameters, restated on a hidden sketch in its cut, and
    # the spoke pattern's pitch on a hidden Front-plane sketch.
    drive_jobs += _diameter_reference(adapter)
    drive_jobs += _spoke_reference(adapter)

    # Cast fillets where each spoke side meets the boss (R.12) and the rim
    # (R.16), picked mid-height on every junction edge, the edge the face view
    # prints first; then the R.03 rounds on the rim bore's two edges, picked between
    # the 0 and 60 deg spokes.
    _fillet(
        adapter,
        HUB_FILLET_R,
        _spoke_edge_picks(_HUB_R, HUB_FILLET_PRINTED),
        "HubFillets",
        "HubFilletR",
    )
    volume = volume_check(
        adapter, "hub fillets", volume + V_HUB_FILLETS, 0.02 * V_HUB_FILLETS
    )
    _fillet(
        adapter,
        RIM_FILLET_R,
        _spoke_edge_picks(_RIM_IN_R, RIM_FILLET_PRINTED),
        "RimFillets",
        "RimFilletR",
    )
    volume = volume_check(
        adapter, "rim fillets", volume + V_RIM_FILLETS, 0.02 * V_RIM_FILLETS
    )
    between = math.radians(180.0 / SPOKE_COUNT)
    round_xy = [_RIM_IN_R * math.cos(between), _RIM_IN_R * math.sin(between)]
    _fillet(
        adapter,
        CAST_ROUND_R,
        [[*round_xy, RIM_AXIAL / 2.0], [*round_xy, -RIM_AXIAL / 2.0]],
        "RimRounds",
        "CastRoundR",
    )
    volume = volume_check(
        adapter, "rim rounds", volume - V_ROUNDS, 0.02 * V_ROUNDS
    )

    # Pen-wire U-groove, revolve-cut in A-A's plane (_profile_mapper): two
    # quarter arcs meet at the groove bottom (a vertex the bottom diameter
    # dimensions to), then straight walls run out past the OD. The revolve axis
    # is a short unit centerline from the origin.  Each arc is named by its
    # ends: a mirrored sketch frame draws it from its far end, so "start" and
    # "end" swap.
    groove_sd = SketchDims()
    check("create_sketch groove", adapter.create_sketch("Top"))
    groove_point, mirrored = _profile_mapper(adapter, label="groove sketch")
    set_sketch_direct_db(adapter, True)
    groove_axis = check(
        "groove axis",
        adapter.add_centerline(*groove_point(0.0, 0.0), *groove_point(1.0, 0.0)),
    )
    bottom_r = GROOVE_BOTTOM_DIA / 2.0
    centre = groove_point(0.0, _GROOVE_CENTRE_R)
    bottom = groove_point(0.0, bottom_r)
    left_foot = groove_point(-GROOVE_R, _GROOVE_CENTRE_R)
    right_foot = groove_point(GROOVE_R, _GROOVE_CENTRE_R)
    first, last = ("end", "start") if mirrored else ("start", "end")
    left_ends = (bottom, left_foot) if mirrored else (left_foot, bottom)
    right_ends = (right_foot, bottom) if mirrored else (bottom, right_foot)
    left_arc = check(
        "groove left arc",
        adapter.add_arc(*centre, *left_ends[0], *left_ends[1]),
    )
    right_arc = check(
        "groove right arc",
        adapter.add_arc(*centre, *right_ends[0], *right_ends[1]),
    )
    groove_bottom = f"{right_arc}.{first}"
    set_sketch_direct_db(adapter, False)
    _right_wall, groove_top, _left_wall = add_line_chain(
        adapter,
        [
            right_foot,
            groove_point(GROOVE_R, _GROOVE_TOP_R),
            groove_point(-GROOVE_R, _GROOVE_TOP_R),
            left_foot,
        ],
        close=False,
    )
    check(
        "groove axis along the wheel axis",
        adapter.add_sketch_constraint(groove_axis, None, _AXIAL),
    )
    anchor_point_to_origin(
        adapter, f"{groove_axis}.start", 0.0, 0.0, "groove axis"
    )
    check(
        "groove axis length",
        adapter.add_sketch_dimension(groove_axis, None, "linear", 1.0),
    )
    groove_sd.record(None)
    _relate(
        adapter,
        (
            (
                "groove arcs concentric",
                f"{left_arc}.center",
                f"{right_arc}.center",
                "coincident",
            ),
            (
                "groove centre on the mid-plane",
                f"{right_arc}.center",
                "origin",
                _SAME_STATION,
            ),
            (
                "groove bottom under the centre",
                groove_bottom,
                f"{right_arc}.center",
                _SAME_STATION,
            ),
            (
                "groove right wall foot",
                f"{right_arc}.{last}",
                f"{right_arc}.center",
                _SAME_RADIUS,
            ),
            (
                "groove left wall foot",
                f"{left_arc}.{first}",
                f"{right_arc}.center",
                _SAME_RADIUS,
            ),
            ("groove right wall radial", _right_wall, None, _RADIAL),
            ("groove left wall radial", _left_wall, None, _RADIAL),
            ("groove top axial", groove_top, None, _AXIAL),
        ),
    )
    check(
        "groove radius",
        adapter.add_sketch_dimension(right_arc, None, "radial", GROOVE_R),
    )
    groove_sd.record("GrooveR", '"GrooveR"')
    add_diametric_linear_dimension(
        adapter,
        groove_axis,
        groove_bottom,
        groove_point(4.0, bottom_r - 4.0),
        "GrooveBottomDia",
    )
    groove_sd.record("GrooveBottomDia", '"GrooveBottomDia"')
    dimension_between(
        adapter,
        f"{groove_top}.start",
        "origin",
        _RADIAL_DISTANCE,
        _GROOVE_TOP_R,
        "groove overrun",
    )
    groove_sd.record(None)
    ensure_fully_defined(adapter, "groove sketch")
    check("exit_sketch groove", adapter.exit_sketch())
    name_last_feature(adapter, "GrooveProfile")
    drive_jobs += groove_sd.apply(adapter, "GrooveProfile")
    check(
        "revolve-cut groove",
        adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Groove")
    volume = volume_check(adapter, "groove", volume - V_GROOVE, 0.02 * V_GROOVE)

    # TIE 1: the lever-wire tie hole, axial through the boss just outboard of
    # the drum's O.D., located from the bore centre by two coordinates.
    tie1_sd = SketchDims()
    check("create_sketch tie 1", adapter.create_sketch("Front"))
    define_circle(
        adapter,
        TIE1_X,
        TIE1_Y,
        _TIE_R,
        "tie 1",
        dims=tie1_sd,
        names=("Tie1X", "Tie1Y", "Tie1HoleDia"),
        drives=('"Tie1X"', '"Tie1Y"', '"TieHoleDia"'),
    )
    ensure_fully_defined(adapter, "tie 1 sketch")
    check("exit_sketch tie 1", adapter.exit_sketch())
    name_last_feature(adapter, "Tie1Profile")
    drive_jobs += tie1_sd.apply(adapter, "Tie1Profile")
    # Mid-plane cut on the spokes' plane: it must reach past both boss faces
    # (back HUB_BACK_Z, front HUB_STEP_Z), which sit off-centre on it.
    check(
        "cut tie 1",
        adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * (max(HUB_BACK_Z, -HUB_STEP_Z) + 1.0),
                both_directions=True,
            )
        ),
    )
    name_last_feature(adapter, "Tie1")
    volume = volume_check(adapter, "tie 1", volume - V_TIE1, 0.02 * V_TIE1)
    drive_jobs += _tie1_counter_drill(adapter)
    check(
        "revolve-cut tie 1 counter-drill",
        adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Tie1Cdrill")
    # Planes, cylinders and a cone: the measured removal should match
    # V_TIE1_CDRILL to well under the band (expected residual ~1e-3 mm^3 or
    # less on analytic faces), and the band is half what the 118 deg point
    # adds over a flat-bottomed #50 (0.087 of 0.174 mm^3), so a flat bottom
    # fails the gate.
    volume = volume_check(
        adapter, "tie 1 counter-drill", volume - V_TIE1_CDRILL, V_TIE1_POINT / 2.0
    )

    # TIE 2: the pen-wire tie hole, radial from the groove bottom to the rim
    # bore at TIE2_CLOCK_DEG -- a half rectangle beside its radial axis,
    # revolve-cut. build_pd_latch_hook's pin-hole recipe, relation for
    # relation: both axis ends anchored by x/y distances, the profile's axis
    # edge coincident with the axis ENDS, the far side square/parallel to it.
    # The farm's first native run (1b6b007ff) left this sketch under-defined
    # with the axis pinned instead by an origin-on-line coincidence, an
    # outer-reach distance and an adapter "angular" dimension; none of those has
    # a native precedent in the repo. The anchors are computed on the radial,
    # so the axis passes the origin; its clock prints from the spoke
    # reference (_spoke_reference's Tie2Clock), vertex on the bore axis.
    # DOF: axis 4 + profile 4 lines 8 = 12 = 4 anchor dims + 2x2 end
    # coincidences + square + parallel + inner end horizontal + diameter.
    tie2_sd = SketchDims()
    profile = _tie2_profile()
    check("create_sketch tie 2", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    tie2_axis = check(
        "tie 2 axis", adapter.add_centerline(*profile[0], *profile[1])
    )
    set_sketch_direct_db(adapter, False)
    on_axis, outer_end, wall, inner_end = add_line_chain(adapter, profile)
    _relate(
        adapter,
        (
            (
                "tie 2 profile on the axis, start",
                f"{tie2_axis}.start",
                f"{on_axis}.start",
                "coincident",
            ),
            (
                "tie 2 profile on the axis, end",
                f"{tie2_axis}.end",
                f"{on_axis}.end",
                "coincident",
            ),
            ("tie 2 outer end square to the axis", outer_end, on_axis, "perpendicular"),
            ("tie 2 wall parallel to the axis", wall, on_axis, "parallel"),
            ("tie 2 inner end horizontal", inner_end, None, "horizontal"),
        ),
    )
    for end_ref, point, label in (
        (f"{tie2_axis}.start", profile[0], "tie 2 axis inner end"),
        (f"{tie2_axis}.end", profile[1], "tie 2 axis outer end"),
    ):
        anchor_point_to_origin(adapter, end_ref, *point, label)
        tie2_sd.record(None)
        tie2_sd.record(None)
    text = (
        profile[2][0] + 3.0 * _TIE2_W[0] + 3.0 * _TIE2_U[0],
        profile[2][1] + 3.0 * _TIE2_W[1] + 3.0 * _TIE2_U[1],
    )
    add_diametric_linear_dimension(adapter, tie2_axis, wall, text, "Tie2HoleDia")
    tie2_sd.record("Tie2HoleDia", '"TieHoleDia"')
    ensure_fully_defined(adapter, "tie 2 sketch")
    check("exit_sketch tie 2", adapter.exit_sketch())
    name_last_feature(adapter, "Tie2Profile")
    drive_jobs += tie2_sd.apply(adapter, "Tie2Profile")
    check(
        "revolve-cut tie 2",
        adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Tie2")
    volume = volume_check(adapter, "tie 2", volume - V_TIE2, 0.05 * V_TIE2)

    apply_material(adapter, MATERIAL)
    # Black-painted casting (p.51 photo); the brass drum is its own part.
    apply_color(adapter, PANEL_BLACK)

    # The rim OD (book-annotated Ø100) and the boss Ø at its back face.
    measure_check(
        adapter,
        "rim OD (annotated 100)",
        [{"entity_type": "EDGE", "point": [_RIM_R, 0.0, RIM_AXIAL / 2.0]}],
        "diameter",
        RIM_OUTER_DIA,
    )
    measure_check(
        adapter,
        "boss dia",
        [{"entity_type": "EDGE", "point": [_HUB_R, 0.0, HUB_BACK_Z]}],
        "diameter",
        HUB_DIA,
    )

    # WIRE-1 yoke point (see the module-level YOKE_LOCAL_* block): one raw
    # sketch point on the Front plane (mid-plane, exact coords, inference OFF)
    # promoted to a named REFERENCE POINT feature the assembly's coupling mate
    # selects. The carrier sketch is blanked (unabsorbed sketches render SHOWN
    # in every assembly instance); the point's coords are re-read and asserted
    # after the final rebuild -- it is undimensioned, so drift must fail loud.
    check("create_sketch yoke", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    model = adapter.currentModel
    sk_point = model.SketchManager.CreatePoint(
        YOKE_LOCAL_X / 1000.0, YOKE_LOCAL_Y / 1000.0, 0.0)
    if sk_point is None:
        raise RuntimeError("yoke sketch point creation failed")
    set_sketch_direct_db(adapter, False)
    check("exit_sketch yoke", adapter.exit_sketch())
    name_last_feature(adapter, "WireYokeSketch")
    blank_sketch(adapter, "WireYokeSketch")
    _make_yoke_ref_point(adapter)

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # so every target resolves. Each equation evaluates to the as-built value:
    # the geometry must not move.
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven magnifying wheel (equations neutral)", volume, 0.001 * volume
    )

    _assert_yoke_point(adapter)
    report_mass_properties(adapter)

    # drawing-simplicity-policy.md `How the repository implements the guidelines`: the tight bands sit on the model dimensions,
    # the places on every marked one.  The spigot and the bore are matched
    # fits (mg_magnifying_wheel_spec.REFERENCE_DIMENSIONS): no band.  The
    # boss Ø rides the title block (mg_magnifying_wheel_geom.HUB_DIA), and so
    # do the hub's overall (fit audit MHA-MG-05.hub_length), the spigot
    # length and the groove's R and bottom Ø at .XXX.  The bands are
    # millimetres; UNIT prints them in inches.
    # The as-cast sizes carry the casting band (mg_magnifying_wheel_spec).
    for feature_name, dimension_names in CAST_DIMENSIONS.items():
        for dimension_name in sorted(dimension_names):
            set_dimension_symmetric_tolerance(
                adapter, feature_name, dimension_name, CAST_TOL, display_unit=UNIT
            )
    # The tie holes are drilled: the title block's DRILLED HOLES row governs
    # their size, and TIE 1's radius rides the title block's .XX.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # A diametric linear dimension prints no Ø of its own: the native symbol
    # token supplies it (build_dt_pinion_arbor's journal references).
    for name in REFERENCE_DIAMETERS:
        set_dimension_prefix(adapter, DIAMETER_REFERENCE, name, "<MOD-DIAM>")
    set_dimension_prefix(adapter, SPOKE_REFERENCE, "SpokePitch", SPOKE_PITCH_PREFIX)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    # The reference sketches stay in the part for the drawing's views to
    # import, hidden so they print in no assembly (_drawing_hidden_sketches
    # shows the diameter reference in A-A, the spoke reference on the face).
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    return save_part_and_images(adapter, PART_NAME)


def _yoke_sketch_points(adapter):
    """The ISketchPoint list of WireYokeSketch (exactly one expected).

    COM members read via ``_read_member`` -- pywin32 late binding exposes
    FirstFeature/Name/GetNextFeature as methods on some builds and properties
    on others (the fix_shown_sketches walk idiom)."""
    model = adapter.currentModel
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        if str(_read_member(feat, "Name")) == "WireYokeSketch":
            sketch = _read_member(feat, "GetSpecificFeature2")
            return list(_read_member(sketch, "GetSketchPoints2") or [])
        feat = _read_member(feat, "GetNextFeature")
    raise RuntimeError("WireYokeSketch not found")


def _make_yoke_ref_point(adapter) -> None:
    """Promote the yoke sketch point to a named reference-point FEATURE
    (``WireYokePoint``) via raw COM -- the adapter's reference-point modes are
    edge/face-based only; ``InsertReferencePoint(swRefPointSketchPoint=7)``
    works from a selected sketch point (the adapter has no writer, same
    raw-COM precedent as the Part D custom properties)."""
    model = adapter.currentModel
    pts = _yoke_sketch_points(adapter)
    if len(pts) != 1:
        raise RuntimeError(f"WireYokeSketch: expected 1 point, found {len(pts)}")
    model.ClearSelection2(True)
    # Select2(Append, Mark): the late-binding-safe select -- Select4's
    # ISelectData arg raises "Type mismatch" under the adapter's forced late
    # binding (the _assembly batch-fix comment documents the same trap).
    if not pts[0].Select2(False, 0):
        raise RuntimeError("cannot select the yoke sketch point")
    feat = model.FeatureManager.InsertReferencePoint(7, 0, 0.0, 1)  # 7 = sketch point
    model.ClearSelection2(True)
    if isinstance(feat, tuple):  # late binding marshals the object return boxed
        feat = next((f for f in feat if f is not None), None)
    if feat is None:
        raise RuntimeError("InsertReferencePoint(sketch point) returned null")
    feat.Name = "WireYokePoint"
    if str(_read_member(feat, "Name")) != "WireYokePoint":
        raise RuntimeError("reference point rename failed")
    # Hidden but still selectable by name for the WIRE-1 yoke mate.
    blank_reference_geometry(adapter, (("WireYokePoint", "DATUMPOINT"),))
    _telemetry.success("WireYokePoint reference point created")


def _assert_yoke_point(adapter) -> None:
    """Fail loud if the (undimensioned, hidden) yoke sketch point drifted from
    its authored coords across the rebuilds -- the coupling mate's geometry
    must stay exact."""
    pts = _yoke_sketch_points(adapter)
    x_mm = float(_read_member(pts[0], "X")) * 1000.0
    y_mm = float(_read_member(pts[0], "Y")) * 1000.0
    if abs(x_mm - YOKE_LOCAL_X) > 1e-3 or abs(y_mm - YOKE_LOCAL_Y) > 1e-3:
        raise RuntimeError(
            f"yoke point drifted: ({x_mm:.4f}, {y_mm:.4f}) != "
            f"({YOKE_LOCAL_X:.4f}, {YOKE_LOCAL_Y:.4f})"
        )
    _telemetry.success(f"yoke point holds at ({x_mm:.4f}, {y_mm:.4f})")


if __name__ == "__main__":
    sys.exit(run_build(build))
