r"""Reproduction script: pinion swing bracket (book ch. 25; 2 used).

The polished-steel strap that carries one end of the alignment-pinion
drum (p. 68 close-ups, shot from the BACK side): a short rounded-end
flat bar with a O6.35 pivot bore below (the torque shaft,
build_pinion_pivot_shaft.py) and a O8 arbor bore above (the steel
arbor, build_pinion_arbor.py) -- plus a BLIND O4 bore in the WEST EDGE
just above the pivot (PR8, page001_img01): it seats the cam-follower
pin (build_pinion_cam_pin.py) that rests ON the lift rod's eccentric
cam collar (build_pinion_cam.py) from above, so turning the lever
raises the collar under the pin and swings the drum east into mesh.
(PR5's O3 tail CROSS-bore at drop 6.25 is retired: the photo puts the
fatter pin near pivot height, and only a blind edge seat clears the
pivot bore there -- a through bore at drop 2 would cut into it.)

Layout: pivot bore at the origin, arbor bore at (0, C2C), strap up +Y,
thickness z 0..THICKNESS; the blind follower seat runs along X into the
-X edge at (y -PIN_DROP, z mid), PIN_SEAT deep from the flat flank face
at x -R_END.  PIN_DROP is negative, so the seat sits ABOVE the pivot on the
STRAIGHT flank -- clear of both cap arcs.  The solid flank preserves the
complete follower-seat mouth around its axis.
The assembly composes a Ry(180) into the strap's lean pose, so local -x (the
seat edge) reads machine WEST and the origin lands at the strap's NORTH
face.

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_bracket.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pinion_bracket_geometry import (
    ARBOR_BORE,
    C2C,
    PIN_BORE,
    PIN_DROP,
    PIN_SEAT,
    PIVOT_BORE,
    R_END,
    THICKNESS,
    WIDTH,
)
from pinion_bracket_spec import (
    ARBOR_BORE_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_SEAT_DIA_BAND,
    PIVOT_BORE_BAND,
    SURFACE_FINISHES,
)

import _telemetry


def _flank_face(model: Any, point_mm: tuple[float, float, float]) -> Any:
    """Return the planar -X flank face whose bounds contain ``point_mm``."""
    body = (_early_bound(model, "IPartDoc").GetBodies2(0, False) or [None])[0]
    body = _early_bound(body, "IBody2")
    for face in body.GetFaces() or []:
        face = _early_bound(face, "IFace2")
        normal = tuple(face.Normal)
        if normal[0] > -0.99:
            continue
        box = [v * 1000.0 for v in face.GetBox()]
        if abs(box[0] - point_mm[0]) > 1e-3:
            continue
        if box[1] <= point_mm[1] <= box[4] and box[2] <= point_mm[2] <= box[5]:
            return face
    raise RuntimeError(f"no planar -X flank face contains {point_mm}")


def _open_flank_sketch(
    adapter: Any, point_mm: tuple[float, float, float]
) -> tuple[float, float, bool]:
    """Open a sketch ON the flank face; map ``point_mm`` into it.

    Returns the sketch ``(u, v)`` of the point and whether the sketch normal
    points OUT of the flank (-X). A cut runs opposite the sketch normal by
    default (IFeatureManager.FeatureCut4 remarks), so the caller reverses the
    cut only when the normal points into the strap.

    The seat depth must dimension from the face the drill enters. A sketch on a
    reference plane coincident with that face displays its blind depth from
    the (blanked) plane, and Section B-B drew it outward into air; a face
    sketch anchors the imported depth on the real flank edge. The face's
    sketch axes are SolidWorks' choice, so the caller maps through
    ``ModelToSketchTransform`` instead of assuming an orientation.
    """
    import pythoncom
    from win32com.client import VARIANT

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    face = _flank_face(model, point_mm)
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError("pin seat: flank face Select2 failed")
    adapter.currentSketchManager = model.SketchManager
    adapter._reset_sketch_entity_registry()
    model.SketchManager.InsertSketch(True)
    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("pin seat: no active sketch on the flank face")
    # Mirror the adapter's create_sketch bookkeeping so exit_sketch and the
    # cut resolve this sketch as the profile.
    adapter.currentSketch = active
    adapter._sketch_count += 1
    adapter._last_sketch_name = str(active.Name)
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    u, v, w = to_sketch(point_mm)
    if abs(w) > 1e-4:
        raise RuntimeError(f"pin seat centre is {w:g} mm off the flank sketch")
    w_out = to_sketch((point_mm[0] - 1.0, point_mm[1], point_mm[2]))[2]
    if abs(abs(w_out) - 1.0) > 1e-4:
        raise RuntimeError(f"flank sketch normal is not along X (w {w_out:g})")
    return u, v, w_out > 0.0


PART_NAME = "pinion-bracket"
MATERIAL = "Plain Carbon Steel"  # p.68: bright steel strap
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
)


def _pin_bore_removed() -> float:
    """Material removed by the blind edge bore: for each (dy, dz) point of
    the bore disc the removed length runs from the cap arc surface
    x = -sqrt(R_END^2 - y^2) east to the bore bottom x = -(R_END - PIN_SEAT).
    z drops out (the disc's z-chord scales it); Simpson over dy."""
    r = PIN_BORE / 2.0
    bottom = -(R_END - PIN_SEAT)  # -5
    n = 2000
    h = 2.0 * r / n

    def f(dy: float) -> float:
        y = -PIN_DROP + dy
        chord = 2.0 * math.sqrt(max(r * r - dy * dy, 0.0))
        surface = _edge_x(y)
        return chord * max(bottom - surface, 0.0)

    total = f(-r) + f(r)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * f(-r + i * h)
    return total * h / 3.0




def _edge_x(y: float) -> float:
    """The strap's -X edge at *y*: the straight flank between the two bores,
    else the end-cap arc about the nearer bore centre."""
    if 0.0 <= y <= C2C:
        return -R_END
    off = min(abs(y), abs(y - C2C))
    return -math.sqrt(max(R_END**2 - off * off, 0.0))




async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the strap width (= cap radius x 2), the
    # bore-to-bore centre distance and the bore diameters. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads BARE
    # numbers in document units (an unsuffixed 22 = 22 in). Thickness is the
    # extrude feature parameter (built with the literal); StrapThickness is
    # declared so a GUI edit sees the knob.
    await set_global(adapter, "StrapWidth", f"{WIDTH}mm")
    await set_global(adapter, "C2C", f"{C2C}mm")
    await set_global(adapter, "StrapThickness", f"{THICKNESS}mm")
    await set_global(adapter, "PivotBore", f"{PIVOT_BORE}mm")
    await set_global(adapter, "ArborBore", f"{ARBOR_BORE}mm")
    await set_global(adapter, "PinBore", f"{PIN_BORE}mm")
    await set_global(adapter, "PinDrop", f"{PIN_DROP}mm")
    await set_global(adapter, "PinSeatDepth", f"{PIN_SEAT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Outer rounded-bar loop + both bores in ONE sketch -> single extrude.
    # Inference OFF: the bottom cap arc endpoints sit near the origin.
    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bottom_cap = check(
        "add bottom cap arc",
        await adapter.add_arc(0.0, 0.0, -R_END, 0.0, R_END, 0.0),
    )
    check("add right edge", await adapter.add_line(R_END, 0.0, R_END, C2C))
    top_cap = check(
        "add top cap arc",
        await adapter.add_arc(0.0, C2C, R_END, C2C, -R_END, C2C),
    )
    check("add left edge", await adapter.add_line(-R_END, C2C, -R_END, 0.0))
    # Pivot bore on the origin (only its diameter recorded); arbor bore on the +Y
    # axis (x 0): one centre dim (the rise, driven by the positive C2C) + diameter.
    await define_circle(
        adapter,
        0.0,
        0.0,
        PIVOT_BORE / 2.0,
        "pivot bore",
        dims=strap,
        names=("PivotBoreCx", "PivotBoreCz", "PivotBoreDia"),
        drives=(None, None, '"PivotBore"'),
    )
    arbor_bore = await define_circle(
        adapter,
        0.0,
        C2C,
        ARBOR_BORE / 2.0,
        "arbor bore",
        dims=strap,
        names=("ArborBoreCx", "ArborBoreCz", "ArborBoreDia"),
        drives=(None, '"C2C"', '"ArborBore"'),
    )
    set_sketch_direct_db(adapter, False)
    # Cap arcs: centre + radius + endpoint alignment (one angle constraint
    # per endpoint -- centre + radius + both endpoints fully located would
    # over-define an arc's 5 DOF). The side edges carry no relations of
    # their own: their endpoints merged with the cap endpoints at creation,
    # so the four h-aligned cap ends pin them too.
    check(
        "anchor bottom cap centre",
        await adapter.add_sketch_constraint(
            f"{bottom_cap}.center", "origin", "coincident"
        ),
    )
    check(
        "bottom cap radius",
        await adapter.add_sketch_dimension(bottom_cap, None, "radial", R_END),
    )
    strap.record("BottomCapRadius", '"StrapWidth" / 2')
    # The top cap is CONCENTRIC with the arbor bore -- that is the design intent,
    # so say it as a constraint instead of re-dimensioning the rise. (The obvious
    # alternative, anchor_point_to_origin + an ArborCentreRise = "C2C" equation,
    # fails live: SolidWorks rejects ANY equation binding on that point-to-origin
    # distance dim -- even a literal 43mm -- erroring the Equations folder on
    # rebuild, while the identical dim on the bore circle takes "C2C" fine.
    # Probed 2026-07-02; same bug class as the magnifying-lever dome radius.)
    check(
        "top cap centre concentric with arbor bore",
        await adapter.add_sketch_constraint(
            f"{top_cap}.center", f"{arbor_bore}.center", "coincident"
        ),
    )
    check(
        "top cap radius",
        await adapter.add_sketch_dimension(top_cap, None, "radial", R_END),
    )
    strap.record("TopCapRadius", '"StrapWidth" / 2')
    for cap, end in (
        (bottom_cap, "start"),
        (bottom_cap, "end"),
        (top_cap, "start"),
        (top_cap, "end"),
    ):
        check(
            f"cap {end} level",
            await adapter.add_sketch_constraint(
                f"{cap}.{end}", f"{cap}.center", "horizontal_points"
            ),
        )
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    check(
        "extrude strap",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Strap")
    depth_dim = name_dimensions(adapter, "Strap", ["Depth"])
    drive_jobs += [(depth_dim[0], '"StrapThickness"')]
    area = (
        WIDTH * C2C
        + math.pi * R_END**2
        - math.pi * (PIVOT_BORE / 2.0) ** 2
        - math.pi * (ARBOR_BORE / 2.0) ** 2
    )
    expected = area * THICKNESS
    await volume_check(adapter, "strap", expected, 0.005 * expected)


    # Blind cam-pin seat (PR8): O4 along X into the -X edge at (y -PIN_DROP,
    # z mid), PIN_SEAT deep from the flat flank face at x -R_END. The sketch
    # sits ON that face, so the cut's depth dimension anchors on the entry
    # edge a drawing section shows. Its sketch axes are mapped, never assumed
    # (_open_flank_sketch), and the centre offsets are UNSIGNED distances from
    # the projected origin, so their drives stay positive whichever way the
    # face sketch is oriented. Two assertions keep a mislocated circle LOUD:
    # the removed volume vs analytic (the strap is x-symmetric BEFORE this cut,
    # so a volumetric pass alone cannot tell the -x seat from its +x mirror)
    # and the centre-of-mass x sign (material removed at -x pushes the COM to +x).
    v_bore = _pin_bore_removed()
    res = await adapter.get_mass_properties()
    vol_before = res.data.volume
    com_before = res.data.center_of_mass
    com_before_x = com_before[0] * 1000.0 if com_before is not None else None
    seat = SketchDims()
    u, v, normal_out = _open_flank_sketch(
        adapter, (-R_END, -PIN_DROP, THICKNESS / 2.0)
    )
    # The face's sketch axes may carry model z or model y; name and drive each
    # unsigned centre offset by the model axis it measures.
    if abs(abs(u) - THICKNESS / 2.0) < 1e-4 and abs(abs(v) - abs(PIN_DROP)) < 1e-4:
        names = ("PinSeatCz", "PinSeatCy", "PinSeatDia")
        drives = ('"StrapThickness" / 2', 'abs("PinDrop")', '"PinBore"')
    elif abs(abs(v) - THICKNESS / 2.0) < 1e-4 and abs(abs(u) - abs(PIN_DROP)) < 1e-4:
        names = ("PinSeatCy", "PinSeatCz", "PinSeatDia")
        drives = ('abs("PinDrop")', '"StrapThickness" / 2', '"PinBore"')
    else:
        raise RuntimeError(
            f"pin seat centre mapped to unexpected sketch ({u:g}, {v:g})"
        )
    _telemetry.debug(f"pin seat flank sketch centre ({u:+g}, {v:+g})")
    await define_circle(
        adapter,
        u,
        v,
        PIN_BORE / 2.0,
        "pin seat",
        dims=seat,
        names=names,
        # PinSeatCy is an UNSIGNED distance; PinDrop is signed (negative = the
        # seat above the pivot), so drive the magnitude.
        drives=drives,
    )
    await ensure_fully_defined(adapter, "pin seat sketch")
    check("exit_sketch pin seat", await adapter.exit_sketch())
    name_last_feature(adapter, "PinSeatProfile")
    drive_jobs += seat.apply(adapter, "PinSeatProfile")
    cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=PIN_SEAT, reverse_direction=not normal_out)
    )
    if not cut.is_success:
        raise RuntimeError(f"pin seat cut failed: {cut.error}")
    res = await adapter.get_mass_properties()
    removed = vol_before - res.data.volume
    if abs(removed - v_bore) > 0.02 * v_bore + 0.5:
        raise RuntimeError(
            f"pin seat cut removed {removed:.1f} mm^3, expected {v_bore:.1f} "
            "-- circle misplaced/resized or wrong side"
        )
    com = res.data.center_of_mass
    com_x = com[0] * 1000.0 if com is not None else None
    if com_x is None or com_before_x is None or com_x <= com_before_x + 0.005:
        raise RuntimeError(
            f"pin seat landed on the wrong edge (COM x {com_before_x} -> {com_x}) -- "
            "the -x seat must move the COM farther +x"
        )
    _telemetry.success(
        f"pin seat (flank face, sketch {u:+g}, {v:+g}) removed "
        f"{removed:.1f} mm^3 (analytic {v_bore:.1f}), COM x {com_x:+.3f}"
    )
    name_last_feature(adapter, "PinSeat")
    seat_depth_dim = name_dimensions(adapter, "PinSeat", ["PinSeatDepth"])
    drive_jobs += [(seat_depth_dim[0], '"PinSeatDepth"')]
    expected -= v_bore
    await volume_check(adapter, "strap with pin seat", expected, 0.005 * expected)

    # Named bore axes for the assembly: the pivot bore (Axis1) rides the torque
    # shaft, the arbor bore (Axis2) journals the pinion. The p2 swing group keys
    # off these (concentric to the shaft + lock the pinion in -- build_drive_train).
    pivot_axis = await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pivot bore"
    )
    arbor_axis = await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", C2C, "arbor bore"
    )
    # Pin seat axis (along X): Front @ mid-thickness x Top @ -PIN_DROP. The
    # follower pin mates coaxial to this in the assembly, riding the swing.
    pin_seat_axis = await name_bore_axis(
        adapter, "Front Plane", THICKNESS / 2.0, "Top Plane", -PIN_DROP, "pin seat"
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven strap (equations neutral)", expected, 0.005 * expected
    )

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # author their decimal places ON THE MODEL, and stamp the make-critical
    # title-block properties.  Only the three fitted bores carry a band, and
    # each one comes from a named fit class; every other feature is governed
    # by its decimal places against the title block's general grades.
    set_dimension_bilateral_tolerance(
        adapter, "StrapProfile", "PivotBoreDia", *deviations(PIVOT_BORE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "StrapProfile", "ArborBoreDia", *deviations(ARBOR_BORE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinSeatProfile", "PinSeatDia", *deviations(PIN_SEAT_DIA_BAND)
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Decimal places are the tolerance statement, so the part authors them and
    # the drawing only reads them back (policy rule 2).
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(adapter, PART_NAME)
    blank_reference_geometry(
        adapter,
        (
            # name_bore_axis's offset planes: the arbor's Top + C2C, then the
            # pin seat's Front + mid-thickness and Top + seat height.
            ("Plane1", "PLANE"),
            ("Plane2", "PLANE"),
            ("Plane3", "PLANE"),
            (pivot_axis, "AXIS"),
            (arbor_axis, "AXIS"),
            (pin_seat_axis, "AXIS"),
        ),
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
