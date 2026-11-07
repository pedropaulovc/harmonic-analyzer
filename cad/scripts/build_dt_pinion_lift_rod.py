r"""Reproduction script: pinion lift rod (book ch. 25).

The second Ø6.35 rod of the swing rig, running through the pivot
blocks' LOW west bores, parallel to (and 4.51 below) the strap torque
shaft. Turning it by the engage lever (build_dt_pinion_lever.py, clamped
on its front end) spins the two eccentric cam collars pinned to it
(build_dt_pinion_cam.py, PR8); their rising ODs lift the straps' follower
pins resting on them from above and swing the drum east into mesh
(page001_img01). PR5's integral radial cam pins are RETIRED -- the
photo shows plain rod + separate set-pinned collars, and the collar
mechanism replaced the crossed-pin lift.

Layout: rod axis Z, z 0..ROD_LEN, one revolved half-profile crowned at its
back end. U36: the MHA-DT-30 pin hole crosses it along local X, 4.0 in from
the flat front end (the lever hub's mid-engagement), match-drilled at assembly.
Two set-screw flats, one under each MHA-DT-23 cam's #2-56 screw, share one
plane through the axis whose outward normal is FLAT_NORMAL_LOCAL --
rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
#2248); a named view looks square at them for the drawing.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_pinion_lift_rod.py
"""

from __future__ import annotations

import math
import sys
from typing import Any, Callable

import _telemetry
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, set_global
from _feature_tree import _feature_by_name, name_last_feature
from _named_views import octant_rotation
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _visibility import blank_reference_geometry
from solidworks_mcp.adapters.com_variant import double_array
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _drawing_prefix import set_dimension_prefix
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _document_units import apply_package_model_units
from _part_properties import part_drawing_unit
from dt_pinion_lever_geometry import PIN_HOLE_DIA, ROD_PIN_HOLE_FROM_END
from dt_pinion_lift_rod_spec import (
    ACROSS_FLAT,
    BACK_FLAT_EDGE_FROM_RIM,
    BACK_FLAT_LEN,
    CAP_R,
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FLAT_DEPTH,
    FLAT_HEIGHT,
    FLAT_NORMAL_LOCAL,
    FLAT_PLANE,
    FLATS_VIEW,
    FRONT_FLAT_EDGE_FROM_RIM,
    FRONT_FLAT_LEN,
    ISOMETRIC_VIEW_NOTE,
    ROD_DIA,
    ROD_DIA_BAND,
    ROD_LEN,
    ROD_PHASE_DEG,
    SURFACE_FINISHES,
    UNIT,
)

PART_NAME = "dt-pinion-lift-rod"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)

# ROD_DIA rides the block bores, same stock as the torque shaft (derived).
# ROD_LEN (pinion_rig_layout): back end FLUSH with the back block's outer
# face (crowned below); the front end reaches just far enough south of the
# front block for the lever's clamp hub.
# CAP_SAG is the back-end crown sagitta (the p.69 dome; the front end hides
# under the lever hub's own domed cap). All three live in
# dt_pinion_lift_rod_spec.py, the dimensional contract the drawing shares.

ROD_R = ROD_DIA / 2.0
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 19.7

V_ROD = math.pi * ROD_R**2 * ROD_LEN
# Each set-screw flat removes a circular segment FLAT_DEPTH deep along its
# length of the straight O.D. (both lie on the body, clear of the crown and
# the pin hole: the spec pins their stations).
_SEGMENT_AREA = ROD_R**2 * math.acos(FLAT_HEIGHT / ROD_R) - FLAT_HEIGHT * math.sqrt(
    ROD_R**2 - FLAT_HEIGHT**2
)
V_FLATS = _SEGMENT_AREA * (FRONT_FLAT_LEN + BACK_FLAT_LEN)
# Flat rectangles: from the flat out past the O.D.; the cut runs mid-plane
# across the whole diameter (build_ch_fulcrum_shaft's flats).
_FLAT_RECT_TOP = ROD_R + 0.5
_FLAT_CUT_DEPTH = 2.0 * ROD_DIA


def _plane_normal(adapter: Any, name: str) -> tuple[float, float, float]:
    """A reference plane's unit normal in model coordinates, read back from
    ``IRefPlane::Transform`` (its third rotation row; build_dt_crankshaft)."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [
        float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")
    ]
    return (data[6], data[7], data[8])


def _delete_feature(adapter: Any, name: str, kind: str) -> None:
    """Select a feature by name and delete it (build_dt_crankshaft)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, kind, 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {name!r} for deletion")
    if not model.Extension.DeleteSelection2(0):
        raise RuntimeError(f"DeleteSelection2 refused {name!r}")
    model.ClearSelection2(True)


async def _angled_plane_containing(
    adapter: Any,
    name: str,
    *,
    base_plane: str,
    pivot_axis: str,
    angle_deg: float,
    direction: tuple[float, float, float],
) -> None:
    """Build the angled plane through ``pivot_axis`` that CONTAINS ``direction``
    (build_dt_crankshaft's recipe): ``InsertRefPlane`` has two solutions per
    magnitude and the adapter's sign picks one undocumented way, so the normal
    is read back and the wrong solution deleted for its mirror."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    for attempt, signed in enumerate((angle_deg, -angle_deg)):
        check(
            f"create_plane {name} ({signed:+.4f} deg about {pivot_axis})",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="angle",
                    base_plane=base_plane,
                    angle=signed,
                    pivot_axis=pivot_axis,
                )
            ),
        )
        name_last_feature(adapter, name)
        normal = _plane_normal(adapter, name)
        off_plane = abs(sum(n * d for n, d in zip(normal, direction, strict=True)))
        _telemetry.info(
            f"{name}: attempt {attempt + 1} normal {normal}, |n.d| = {off_plane:.3e}"
        )
        if off_plane < 1e-6:
            return
        _delete_feature(adapter, name, "PLANE")
    raise RuntimeError(f"{name}: neither angled-plane solution contains {direction}")


def _flat_sketch_frame(
    adapter: Any,
) -> tuple[Callable[[float, float], tuple[float, float]], bool]:
    """Map (axial z, height along FLAT_NORMAL_LOCAL) into the ACTIVE flats
    sketch, and say whether the rod axis runs along its u.

    SolidWorks picks an angled plane's sketch axes, so they are read off
    ``ModelToSketchTransform`` (the _oblique_pivot_block_model mapper): the
    rod axis must run along one sketch axis and the flat normal along the
    other, either sign, with the sketch origin on the part origin.
    """
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("flats sketch: no active sketch")
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
    if max(abs(c) for c in base) > 1e-6:
        raise RuntimeError(f"flats sketch: the part origin maps to {base}")
    axial = [m - b for m, b in zip(raw((0.0, 0.0, 1.0)), base, strict=True)]
    normal = [m - b for m, b in zip(raw(FLAT_NORMAL_LOCAL), base, strict=True)]

    def along(delta: list[float], index: int) -> bool:
        return abs(abs(delta[index]) - 1.0) < 1e-6 and all(
            abs(delta[other]) < 1e-6 for other in range(3) if other != index
        )

    axial_is_u = along(axial, 0) and along(normal, 1)
    if not axial_is_u and not (along(axial, 1) and along(normal, 0)):
        raise RuntimeError(
            f"flats sketch: rod axis maps to {axial}, flat normal to {normal}; "
            "neither along a sketch axis"
        )

    def to_sketch(axial_mm: float, height_mm: float) -> tuple[float, float]:
        u, v, w = raw(
            (
                height_mm * FLAT_NORMAL_LOCAL[0],
                height_mm * FLAT_NORMAL_LOCAL[1],
                axial_mm,
            )
        )
        if abs(w) > 1e-4:
            raise RuntimeError(f"flats sketch: ({axial_mm}, {height_mm}) is {w:g} mm off it")
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch, axial_is_u


def _as_construction(adapter: Any, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (the setter is
    on ISketchSegment; build_ch_fulcrum_shaft)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _flats(adapter: Any, rod_axis: str) -> list[tuple[str, str]]:
    """The two set-screw flats: one mid-plane cut from two rectangles on
    FLAT_PLANE, each from the flat (FLAT_HEIGHT along the normal) out past the
    O.D. -- build_ch_fulcrum_shaft's ``_flats`` on a plane turned
    ROD_PHASE_DEG about the rod axis from the Right Plane, so it holds the
    cams' screw axis (dt_pinion_lift_rod_spec.FLAT_NORMAL_LOCAL).

    Constraint accounting (16 rectangle + 4 rim witness + 4 across-flat
    witness unknowns = 24): eight rectangle along/across relations; each
    flat's length, rise and station from the rim (its rim-side corner off the
    rim witness's end); the rim witness along the axis from the origin,
    RodLen long; the flats on one line; the across-flat witness across the
    axis under the back flat's rim-side corner, its foot RodDia/2 off the
    origin and its top on the axis, whose AcrossFlat dim sets both flats'
    height.
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    await _angled_plane_containing(
        adapter,
        FLAT_PLANE,
        base_plane="Right Plane",
        pivot_axis=rod_axis,
        angle_deg=ROD_PHASE_DEG,
        direction=FLAT_NORMAL_LOCAL,
    )
    blank_reference_geometry(adapter, ((FLAT_PLANE, "PLANE"),))
    dims = SketchDims()
    check("create_sketch flats", await adapter.create_sketch(FLAT_PLANE))
    to_sketch, axial_is_u = _flat_sketch_frame(adapter)
    along, across = ("horizontal", "vertical") if axial_is_u else ("vertical", "horizontal")

    def rectangle(edge_from_rim: float, length: float) -> list[tuple[float, float]]:
        """Rim-side corner on the flat, far corner, then out past the O.D."""
        z_rim = ROD_LEN - edge_from_rim
        z_far = z_rim - length
        return [
            to_sketch(z_rim, FLAT_HEIGHT),
            to_sketch(z_far, FLAT_HEIGHT),
            to_sketch(z_far, _FLAT_RECT_TOP),
            to_sketch(z_rim, _FLAT_RECT_TOP),
        ]

    back_z = ROD_LEN - BACK_FLAT_EDGE_FROM_RIM
    set_sketch_direct_db(adapter, True)
    back = await add_line_chain(adapter, rectangle(BACK_FLAT_EDGE_FROM_RIM, BACK_FLAT_LEN))
    front = await add_line_chain(
        adapter, rectangle(FRONT_FLAT_EDGE_FROM_RIM, FRONT_FLAT_LEN)
    )
    (rim_witness,) = await add_line_chain(
        adapter, [to_sketch(0.0, 0.0), to_sketch(ROD_LEN, 0.0)], close=False
    )
    witness = check(
        "across-flat witness",
        await adapter.add_line(*to_sketch(back_z, -ROD_R), *to_sketch(back_z, 0.0)),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, rim_witness)
    _as_construction(adapter, witness)
    for lines in (back, front):
        for line, direction in zip(lines, (along, across, along, across), strict=True):
            check(
                f"flat {direction} {line}",
                await adapter.add_sketch_constraint(line, None, direction),
            )
    check(
        "rim witness along the axis",
        await adapter.add_sketch_constraint(rim_witness, None, along),
    )
    check(
        "rim witness starts at the origin",
        await adapter.add_sketch_constraint(
            f"{rim_witness}.start", "origin", "coincident"
        ),
    )
    check(
        "across-flat witness across the axis",
        await adapter.add_sketch_constraint(witness, None, across),
    )
    rim = f"{rim_witness}.end"
    await dimension_between(
        adapter, f"{rim_witness}.start", rim, f"{along}_distance", ROD_LEN, "rim witness"
    )
    dims.record("RimStation", '"RodLen"')
    for prefix, lines, length, edge in (
        ("Back", back, BACK_FLAT_LEN, BACK_FLAT_EDGE_FROM_RIM),
        ("Front", front, FRONT_FLAT_LEN, FRONT_FLAT_EDGE_FROM_RIM),
    ):
        flat, rise = lines[0], lines[1]
        corner = f"{flat}.start"  # the rim-side corner on the flat line
        await dimension_between(
            adapter, corner, f"{flat}.end", f"{along}_distance", length, f"{prefix}FlatLen"
        )
        dims.record(f"{prefix}FlatLen", f'"{prefix}FlatLen"')
        await dimension_between(
            adapter,
            f"{rise}.start",
            f"{rise}.end",
            f"{across}_distance",
            _FLAT_RECT_TOP - FLAT_HEIGHT,
            f"{prefix.lower()} flat rise",
        )
        dims.record(f"{prefix}FlatRise")
        await dimension_between(
            adapter, rim, corner, f"{along}_distance", edge, f"{prefix}FlatFromRim"
        )
        dims.record(f"{prefix}FlatFromRim", f'"{prefix}FlatFromRim"')
    back_corner = f"{back[0]}.start"
    check(
        "flats on one line",
        await adapter.add_sketch_constraint(
            f"{front[0]}.start", back_corner, f"{along}_points"
        ),
    )
    check(
        "across-flat witness under the back flat's corner",
        await adapter.add_sketch_constraint(
            f"{witness}.start", back_corner, f"{across}_points"
        ),
    )
    await dimension_between(
        adapter, back_corner, f"{witness}.start", f"{across}_distance", ACROSS_FLAT, "AcrossFlat"
    )
    dims.record("AcrossFlat", '"RodDia" - "FlatDepth"')
    await dimension_between(
        adapter,
        f"{witness}.start",
        "origin",
        f"{across}_distance",
        ROD_R,
        "across-flat witness foot",
    )
    dims.record("WitnessFoot", '"RodDia" / 2')
    check(
        "across-flat witness top on the axis",
        await adapter.add_sketch_constraint(
            f"{witness}.end", "origin", f"{along}_points"
        ),
    )
    await ensure_fully_defined(adapter, "flats sketch")
    check("exit_sketch flats", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatProfile")
    drive_jobs = dims.apply(adapter, "FlatProfile")
    check(
        "cut flats",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=_FLAT_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SetScrewFlats")
    return drive_jobs


def _transpose_rotation(rotation: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(rotation[column + 3 * row] for column in range(3) for row in range(3))


def _rotations_close(
    left: tuple[float, ...], right: tuple[float, ...], tolerance: float
) -> bool:
    return len(left) == len(right) and max(
        abs(a - b) for a, b in zip(left, right, strict=True)
    ) <= tolerance


def flats_view_rows() -> tuple[float, ...]:
    """The FLATS_VIEW rotation, each view axis a ROW in model coordinates:
    view x along -Z (the crown end screen-left, as on the *Right side view),
    view y the flats' outward normal (flats up), view z = x cross y, square to
    FLAT_PLANE."""
    x = (0.0, 0.0, -1.0)
    y = FLAT_NORMAL_LOCAL
    z = (
        x[1] * y[2] - x[2] * y[1],
        x[2] * y[0] - x[0] * y[2],
        x[0] * y[1] - x[1] * y[0],
    )
    return (*x, *y, *z)


def _name_flats_view(adapter: Any) -> None:
    """Persist the named view the drawing's flats view places (the
    build_dt_cone_pivot_post ``_name_cone_axis_view`` recipe: the storage
    convention is read off the built-in *Isometric, then the view is read
    back)."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    built_in = tuple(float(value) for value in model.GetStandardViewRotation(7))
    row_isometric = octant_rotation(1, 1, 1)
    if _rotations_close(built_in, row_isometric, 1e-3):
        store = lambda rotation: rotation  # noqa: E731
    elif _rotations_close(built_in, _transpose_rotation(row_isometric), 1e-3):
        store = _transpose_rotation
    else:
        raise RuntimeError(
            f"*Isometric rotation {built_in!r} establishes no known convention"
        )
    rotation = store(flats_view_rows())
    transform = utility.CreateTransform(
        double_array([*rotation, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
    )
    if transform is None:
        raise RuntimeError("failed to create the flats view transform")
    view = _early_bound(model.ActiveView, "IModelView")
    view.Orientation3 = transform
    model.NameView(FLATS_VIEW)
    readback = tuple(
        float(value) for value in (extension.GetNamedViewRotation(FLATS_VIEW) or ())
    )
    if not _rotations_close(readback, rotation, 1e-6):
        raise RuntimeError(
            f"flats named view read back {readback!r}, expected {rotation!r}"
        )
    model.ShowNamedView2("*Isometric", 7)
    _telemetry.info(f"flats named view {FLATS_VIEW!r}: rotation={readback!r}")


def _pin_hole_removed() -> float:
    """Volume a diametral X hole of PIN_HOLE_DIA takes out of the solid rod:
    the hole's chord width times the rod's full chord at each height
    (Simpson over the hole's y extent)."""
    r = PIN_HOLE_DIA / 2.0
    n = 2000
    h = 2.0 * r / n

    def slab(y: float) -> float:
        width = 2.0 * math.sqrt(max(r * r - y * y, 0.0))
        return width * 2.0 * math.sqrt(max(ROD_R**2 - y * y, 0.0))

    total = slab(-r) + slab(r)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * slab(-r + i * h)
    return total * h / 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): the rod diameter, body length and
    # crown sagitta -- RodDia/RodLen drive the marked drawing dims, CapSag the
    # crown and the overall. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 6.35 = 6.35 in).
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodLen", f"{ROD_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "PinHoleFromEnd", f"{ROD_PIN_HOLE_FROM_END}mm")
    await set_global(adapter, "FlatDepth", f"{FLAT_DEPTH}mm")
    await set_global(adapter, "FrontFlatLen", f"{FRONT_FLAT_LEN}mm")
    await set_global(adapter, "BackFlatLen", f"{BACK_FLAT_LEN}mm")
    await set_global(adapter, "FrontFlatFromRim", f"{FRONT_FLAT_EDGE_FROM_RIM}mm")
    await set_global(adapter, "BackFlatFromRim", f"{BACK_FLAT_EDGE_FROM_RIM}mm")

    # The rod is one half-profile revolved about its axis, as it sits in the
    # lathe (drawing-guidelines.md rule 11 (turned parts read like the lathe);
    # machinist review r1 of the ENFORCE gate, #1013): the diameter, the body
    # length, the crown's SR and the overall all import into the side view.
    # It is sketched on the Right Plane (sketch u = -z, v along y) -- the
    # plane the side view looks at: the flat front end face on the origin, the
    # OD to the crown rim at the body length, the rim -> apex crown arc (the
    # minor CCW lobe: rim at ~139 deg, apex at 180 deg about its on-axis
    # centre) and the axis back to the origin, over an axis centerline the
    # diameter doubles from.
    from solidworks_mcp.adapters.base import RevolveParameters

    u_rim, u_apex = -ROD_LEN, -(ROD_LEN + CAP_SAG)
    u_centre = -(ROD_LEN + CAP_SAG - CAP_R)
    rod = SketchDims()
    check("create_sketch rod", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "rod axis centerline", await adapter.add_centerline(0.0, 0.0, u_apex, 0.0)
    )
    front = check("rod front end", await adapter.add_line(0.0, 0.0, 0.0, ROD_R))
    outline = check("rod outline", await adapter.add_line(0.0, ROD_R, u_rim, ROD_R))
    arc = check(
        "rod crown arc",
        await adapter.add_arc(u_centre, 0.0, u_rim, ROD_R, u_apex, 0.0),
    )
    close = check("rod close on axis", await adapter.add_line(u_apex, 0.0, 0.0, 0.0))
    set_sketch_direct_db(adapter, False)
    check(
        "rod front end vertical",
        await adapter.add_sketch_constraint(front, None, "vertical"),
    )
    check(
        "rod outline horizontal",
        await adapter.add_sketch_constraint(outline, None, "horizontal"),
    )
    check(
        "rod close horizontal",
        await adapter.add_sketch_constraint(close, None, "horizontal"),
    )
    await anchor_point_to_origin(adapter, f"{front}.start", 0.0, 0.0, "rod front end")
    await add_diametric_linear_dimension(
        adapter, axis, outline, (u_rim / 2.0, ROD_R + 4.0), "RodDia"
    )
    rod.record("RodDia", '"RodDia"')
    await dimension_between(
        adapter,
        f"{outline}.start",
        f"{outline}.end",
        "horizontal_distance",
        ROD_LEN,
        "rod body length",
    )
    rod.record("RodBody", '"RodLen"')
    await dimension_between(
        adapter,
        f"{close}.start",
        "origin",
        "horizontal_distance",
        ROD_LEN + CAP_SAG,
        "rod overall length",
    )
    rod.record("RodOverall", '"RodLen" + "CapSag"')
    check(
        "rod crown radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    rod.record(
        "CapR",
        '("RodDia" / 2 * "RodDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs = rod.apply(adapter, "RodProfile")
    check("revolve rod", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Rod")
    expected = V_ROD + V_CAP
    await volume_check(adapter, "rod with crown", expected, 0.03 * V_CAP)

    # U36 pin hole: a diametral cross-hole along X at the lever's
    # mid-engagement, sketched on the Right Plane (normal X; sketch u = -z) --
    # the plane the side view looks at, with the crown -- and cut mid-plane
    # twice the rod diameter deep.  (ThroughAll + both_directions cut only ONE
    # side on the farm, r7: the adapter falls back to single-sided ThroughAll
    # when the install has no swEndCondThroughAllBoth.)  The origin sits on
    # the flat front end face, so the circle's axial anchor IS the front-end
    # station the print carries.  Its mirror station (z -4) lies outside the rod, so a wrong side
    # cuts nothing and the volume gate fails loud.
    v_hole = _pin_hole_removed()
    pin_hole = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        -ROD_PIN_HOLE_FROM_END,
        0.0,
        PIN_HOLE_DIA / 2.0,
        "pin hole",
        dims=pin_hole,
        names=("PinHoleZ", "PinHoleY", "PinHoleDia"),
        drives=('"PinHoleFromEnd"', None, '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_hole.apply(adapter, "PinHoleProfile")
    cut = await adapter.create_cut_extrude(
        ExtrusionParameters(
            depth=2.0 * ROD_DIA, both_directions=True
        )
    )
    if not cut.is_success:
        raise RuntimeError(f"pin hole cut failed: {cut.error}")
    name_last_feature(adapter, "PinHole")
    expected -= v_hole
    await volume_check(adapter, "pin hole", expected, 0.05 * v_hole)

    # Named centreline axis (Axis1): the assembly's revolute (coaxial to the
    # block's lift-bore axis) and the cam/lever clamps all key off it (PR8).
    rod_axis = await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", 0.0, "rod axis"
    )
    # Named pin-hole axis (along X at the pin station): the MHA-DT-30 pin's
    # coaxial reference in the assembly.
    await name_bore_axis(
        adapter, "Top Plane", 0.0, "Front Plane", ROD_PIN_HOLE_FROM_END, "lever pin"
    )

    # Set-screw flats (rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00
    # rubric sample, PR #2248)): one cut from a plane
    # turned about the rod axis (so after it), the cams' screw axis in it.
    drive_jobs += await _flats(adapter, rod_axis)
    expected -= V_FLATS
    await volume_check(adapter, "set-screw flats", expected, 0.05 * V_FLATS)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven lift rod (equations neutral)", expected, 0.03 * V_CAP
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RodProfile", "RodDia", *deviations(ROD_DIA_BAND), display_unit=UNIT
    )
    set_dimension_prefix(adapter, "RodProfile", "CapR", "SR")
    # One AcrossFlat sets both flats (they share one line in FlatProfile).
    set_dimension_prefix(adapter, "FlatProfile", "AcrossFlat", "2X ")
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    _name_flats_view(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
