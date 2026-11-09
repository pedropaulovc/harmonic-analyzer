r"""Reproduction script: cone gear shaft (book ch. 12, pp. 16-21) -- stepped.

Steel shaft carrying the 20-gear cone set (all gears fixed to and
rotating with the shaft), with its large-end bearing journal in the green
pivot post and its tip held through T006's pivot, the brass bushing and the
end screw in the tip block -- the post and tip block both stand on the swing
platform, so the whole set pivots out of engagement as one unit (ch. 25;
p. 18 "pivot").  The book never shows how the gears attach; here (owner
decision C1 keyed, 2026-11-09, PR #1992; cone_tip_cluster) the 64T and
T030..T120 slide on the keyed land 1 as a solid touching stack, T024 is
bonded on the round land 2, and T006's spigot (carrying T018 and T012) is
bonded in a reamed socket in the shaft's end.

The FRONT STUB end is local z = 0, JOURNAL_PROUD south of the post's front
face. The integral journal spans the post's derived CONE_BOSS_LENGTH and
that proud length. The 5/8 bar's as-supplied thrust collar bears on the
post's north boss face and fills the distance to the 64T's south face.
The spec derives every downstream station from cone_line, the post, the
configured cone face/seat pitch and the tip cluster (cone_tip_cluster):

* The journal fits the post at JOURNAL_CLEARANCE diametral clearance.
* The 3/8 in land carries the 64T and T120..T030 on the 1/16 key
  (cone_land_key), its keyseat the whole land.
* The 1/4 in land carries T024 and ends inside its bore; the reamed socket
  in that end takes T006's spigot.

The land step is SEAT_STEP_SETBACK south of T030's north face.

Dimensions: cad/DIMENSIONS.md "Chapter 12" -- the journal comes from the
manually rederived v2 post bore and its 42.011 axial body; the gear-seat
stations and diameters remain the legacy/derived stack (Appendix C #7).

Build: coaxial circles extruded along +Z to each section's end station with
``merge_result`` -- each smaller cylinder is contained in its larger
neighbour over the shared length, so the union is exactly the stepped shaft
(volume check is exact per section).  The keyseat is then cut back from
land 1's end plane over the land's length, the socket from land 2's end
plane, and the step root is filleted.

Layout: shaft axis along +Z, large (pivot) end at the origin -- along
the assembly depth like the gears (`build_dt_cone_gear.py` axis = Z), so
the drive-train assembly inclines the whole cone set by the configured
cone-line angle (DIMENSIONS.md ch. 13 drive-train layout).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_shaft.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
import cone_land_key
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties
from _part_save import save_part_and_images
from _paths import IN
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _sketch_circle import define_circle
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _document_units import apply_package_model_units
from _fit_deviations import deviations
from _gear import volume_check
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _visibility import blank_reference_geometry
from dt_cone_gear_shaft_spec import (
    COLLAR_DIA,
    COLLAR_END_STATION,
    COLLAR_START_STATION,
    COLLAR_THICKNESS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FILLET_RADIUS,
    FILLET_R_BAND,
    FILLET_R_TOL_TYPE,
    SECTION_DIA_BANDS,
    SECTION_DIAS,
    SECTION_ENDS,
    SECTION_KNOBS,
    SECTION_ORIGINS,
    SECTIONS,
    SOCKET_DEPTH,
    SOCKET_DIA,
    SOCKET_DIA_BAND,
    SURFACE_FINISHES,
    UNIT,
    validate_gear_loading_clearances,
)
from solidworks_mcp.adapters.com_variant import double_array

PART_NAME = "dt-cone-gear-shaft"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

# SECTIONS and SECTION_KNOBS live in the shared pure-data spec.  FRONT_STUB
# follows the current cone-line post station; the journal spans the post boss
# and proud length, and each downstream land follows its gear/tip owner.
# Diameters agree with the configured gear bores.

# Every length knob and the dimensions it is the ONE owner of (the seat-side
# gate proves it): SecEnd{i} owns land i's end plane and its depth, SecEnd0
# the journal and the CollarFace plane, CollarWidth the collar's plane and
# web (rule 11, round 6: the journal and web run from the collar's thrust
# face, the gear lands and the tip from its tip-side face, CollarEndPlane),
# SocketDepth the socket.  The keyseat's length is land 1's, so SecEnd1
# drives it without owning it.
STATION_OWNERS: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    (
        "SecEnd0",
        SECTION_KNOBS[0],
        ("Sec0End@Sec0", "CollarFaceStation@CollarFace"),
    ),
    *(
        (
            f"SecEnd{i}",
            SECTION_KNOBS[i],
            (f"Sec{i}Station@Sec{i}EndPlane", f"Sec{i}End@Sec{i}"),
        )
        for i in range(1, len(SECTIONS))
    ),
    (
        "CollarWidth",
        COLLAR_THICKNESS,
        ("CollarStation@CollarEndPlane", "CollarWidth@Collar"),
    ),
    ("SocketDepth", SOCKET_DEPTH, ("SocketDepth@Socket",)),
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    validate_gear_loading_clearances()
    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): one diameter + one end station per
    # section. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units. The section diameters
    # come from SECTIONS in inches (the first is the metric v2 journal converted
    # to inches by the pure-data spec). The end stations are extrude DEPTHS
    # (feature parameters); each is named Sec{i}End and driven by its SecEnd{i}
    # global below, so the knobs really reshape the shaft AND the stations are
    # markable manufacturing dimensions for the drawing. A land sketched on its
    # own offset plane has that plane's offset driven by the same SecEnd{i}, so
    # the knob moves the shoulder and the depth back to its origin together.
    # Rule 11 (round 6): two origins, one per chucking.  SecEnd0 is the
    # journal (front stub to the collar's thrust face) and CollarWidth the web;
    # SecEnd1 is the shoulder station and SecEnd2 the tip FROM the collar's
    # tip-side face.
    for i, (dia_in, _end_z) in enumerate(SECTIONS):
        await set_global(adapter, f"SecDia{i}", f"{dia_in * IN}mm")
        await set_global(adapter, f"SecEnd{i}", f"{SECTION_KNOBS[i]}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarWidth", f"{COLLAR_THICKNESS}mm")
    await set_global(adapter, "Sec1KeyseatW", f"{cone_land_key.KEYSEAT_WIDTH_MM}mm")
    await set_global(adapter, "Sec1KeyseatS", f"{cone_land_key.KEYSEAT_S_MM}mm")
    await set_global(adapter, "SocketDia", f"{SOCKET_DIA}mm")
    await set_global(adapter, "SocketDepth", f"{SOCKET_DEPTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # The collar's south face -- the thrust face the post bears on, the
    # journal-side origin -- as a named plane, placed from the front face by
    # the journal and owned like the journal by SecEnd0.  The drive train
    # seats on it by name: a point pick there is ambiguous (the post face lies
    # under it).
    check(
        "create_plane CollarFace",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=COLLAR_START_STATION
            )
        ),
    )
    name_last_feature(adapter, "CollarFace")
    face_dim = name_dimensions(adapter, "CollarFace", ["CollarFaceStation"])
    drive_jobs += [(face_dim[0], '"SecEnd0"')]
    # The collar's north face, the tip-side origin the gear lands and the tip
    # are measured from, one web on from the thrust face and owned by
    # CollarWidth.  The drive train seats the 64T on it by name.
    check(
        "create_plane CollarEndPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="CollarFace", offset=COLLAR_THICKNESS
            )
        ),
    )
    name_last_feature(adapter, "CollarEndPlane")
    plane_dim = name_dimensions(adapter, "CollarEndPlane", ["CollarStation"])
    drive_jobs += [(plane_dim[0], '"CollarWidth"')]

    volume = 0.0
    prev_end = 0.0
    for i, (dia_in, end_z) in enumerate(SECTIONS):
        label = f"section d{dia_in:g}in to z={end_z:g}"
        knob = SECTION_KNOBS[i]
        if i == 1:
            # The collar joins the journal before the gear lands start at its
            # tip-side face, so the body stays one solid.
            volume = await _add_collar(adapter, drive_jobs, volume)
            prev_end = COLLAR_END_STATION
        # Each land is a cylinder from its origin (the large-end face, or the
        # collar's tip-side face for the gear-seat lands) to its own end
        # station, so every smaller land is contained in its larger neighbour
        # and the running volume stays exact per section.
        #
        # WHERE the profile circle sits is a drawing decision: a diameter
        # dimension can only be dragged into the side view at the station its
        # sketch occupies.  Sketching every circle on the Front plane put
        # every diameter at the large-end face, which is why the sheet
        # used to pile them as leadered callouts beside an end view.  Land 0
        # is sketched on the Front plane (its circle IS the large-end face);
        # every other land is sketched on an offset plane AT ITS END STATION
        # and extruded BACK to its origin, which leaves each diameter on its
        # own shoulder while the extrude depth is still the station itself.
        if i == 0:
            plane_name = "Front"
        else:
            check(
                f"create_plane end of {label}",
                await adapter.create_plane(
                    CreatePlaneParameters(
                        mode="offset", base_plane=SECTION_ORIGINS[i], offset=knob
                    )
                ),
            )
            plane_name = f"Sec{i}EndPlane"
            name_last_feature(adapter, plane_name)
            plane_dim = name_dimensions(adapter, plane_name, [f"Sec{i}Station"])
            drive_jobs += [(plane_dim[0], f'"SecEnd{i}"')]
        # On-axis circle (centre at the origin): define_circle records ONLY the
        # diameter dim (the X/Z centre slots are relations, not display dims).
        sec = SketchDims()
        check(f"create_sketch {label}", await adapter.create_sketch(plane_name))
        await define_circle(
            adapter,
            0.0,
            0.0,
            dia_in * IN / 2.0,
            label,
            dims=sec,
            names=(f"Sec{i}Cx", f"Sec{i}Cz", f"Sec{i}Dia"),
            drives=(None, None, f'"SecDia{i}"'),
        )
        await ensure_fully_defined(adapter, f"{label} sketch")
        check(f"exit_sketch {label}", await adapter.exit_sketch())
        name_last_feature(adapter, f"Sec{i}Profile")
        drive_jobs += sec.apply(adapter, f"Sec{i}Profile")
        check(
            f"extrude {label}",
            await adapter.create_extrusion(
                ExtrusionParameters(depth=knob, reverse_direction=i > 0)
            ),
        )
        name_last_feature(adapter, f"Sec{i}")
        depth_dim = name_dimensions(adapter, f"Sec{i}", [f"Sec{i}End"])
        drive_jobs += [(depth_dim[0], f'"SecEnd{i}"')]
        volume += math.pi * (dia_in * IN / 2.0) ** 2 * (end_z - prev_end)
        # A land extruded the wrong way lands inside its larger neighbour or
        # off the end of the shaft, so the running volume is the direction
        # check as well as the size check.
        await volume_check(adapter, label, volume, 0.005 * volume)
        prev_end = end_z
    blank_reference_geometry(
        adapter, tuple((f"Sec{i}EndPlane", "PLANE") for i in range(1, len(SECTIONS)))
    )

    # The collar's two planes stay as named mate references (the drive train
    # seats the post's boss face on CollarFace and the 64T on CollarEndPlane,
    # both by name), so they are hidden, not removed: shown, they would render
    # in every assembly that places the shaft (#950's save gate).
    blank_reference_geometry(adapter, (("CollarFace", "PLANE"), ("CollarEndPlane", "PLANE")))

    # Land 1's keyseat (owner decision 2026-11-09, C1 keyed, PR #1992), cut
    # back from land 1's end plane over exactly the land, so it runs from the
    # collar's face to the land's end.  Before the step root, so the fillet
    # follows the cut.  The cut's own volume, not the shaft's, sets the gate:
    # run the wrong way off the end plane it meets only air, since land 2
    # lies inside the keyseat floor.
    removed = await _cut_keyseat(adapter, drive_jobs)
    volume -= removed
    await volume_check(adapter, "Sec1 keyseat", volume, 0.1 * removed)
    # The reamed socket for T006's spigot, back from land 2's end plane;
    # run the wrong way it too meets only air.
    removed = await _cut_socket(adapter, drive_jobs)
    volume -= removed
    await volume_check(adapter, "socket", volume, 0.1 * removed)

    # Step root.  The land-1 to land-2 step is a full circle on land 2 (land
    # 2 lies inside the keyseat floor), picked once at -X, opposite the
    # keyseat.  The collar's two roots stay sharp: the post boss and the 64T
    # bear flat against its faces, and a root radius would stand on the post
    # bore's and the 64T bore's edges -- the title block's edge break on those
    # parts is what clears the tool's nose radius.  (The old journal step
    # edge is buried under the collar.)
    check(
        "fillet step root",
        await adapter.add_fillet(
            FILLET_RADIUS,
            [[-SECTION_DIAS[2] / 2.0, 0.0, SECTION_ENDS[1]]],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "ShoulderFillets")
    name_dimensions(adapter, "ShoulderFillets", ["ShoulderR"])
    # An R0.10 root adds a fraction of a mm^3 to the shaft: this checks
    # that the fillet did not eat a land, not that it moved the number.
    await volume_check(adapter, "step fillets", volume, 0.005 * volume)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cone-gear shaft (equations neutral)", volume, 0.005 * volume
    )
    _assert_stations_single_owned(adapter)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The three turned diameters, the keyseat and the socket carry their fit
    # on the MODEL dimension, so SolidWorks renders the limits and
    # re-renders them on a unit change.  The bands are millimetres; UNIT
    # prints them in decimal inch at the nominal's places.
    for section, band in enumerate(SECTION_DIA_BANDS):
        set_dimension_bilateral_tolerance(
            adapter,
            f"Sec{section}Profile",
            f"Sec{section}Dia",
            *deviations(band),
            places=DRAWING_PRECISION[f"Sec{section}Profile"][f"Sec{section}Dia"],
            display_unit=UNIT,
        )
    for name, band in (
        ("Sec1KeyseatWidth", cone_land_key.KEYSEAT_WIDTH_BAND),
        ("Sec1KeyseatS", cone_land_key.KEYSEAT_S_BAND),
    ):
        set_dimension_bilateral_tolerance(
            adapter,
            "Sec1KeyseatProfile",
            name,
            *deviations(band),
            places=DRAWING_PRECISION["Sec1KeyseatProfile"][name],
            display_unit=UNIT,
        )
    set_dimension_bilateral_tolerance(
        adapter,
        "SocketProfile",
        "SocketDia",
        *deviations(SOCKET_DIA_BAND),
        places=DRAWING_PRECISION["SocketProfile"]["SocketDia"],
        display_unit=UNIT,
    )
    # The step roots' single limit R.004 MAX: the band (0/-R) stays on the
    # native tolerance as the model's record; swTolMAX prints the model value
    # then MAX, so the setback books the printed maximum
    # (build_dt_cylinder_gear._notch_width_max_limit's recipe).
    set_dimension_bilateral_tolerance(
        adapter,
        "ShoulderFillets",
        "ShoulderR",
        *deviations(FILLET_R_BAND),
        places=DRAWING_PRECISION["ShoulderFillets"]["ShoulderR"],
        display_unit=UNIT,
    )
    _shoulder_root_max_limit(adapter)
    # Display precision is model-owned too (drawing-simplicity-policy.md `How the repository implements the guidelines`).
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The land that RUNS carries a roughness symbol.  No datums and no
    # feature-control frames (drawing-guidelines.md rule 5 (avoid excessive GD&T)).
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


@_telemetry.traced("part.cone_gear_shaft.shoulder_root_max")
def _shoulder_root_max_limit(adapter: Any) -> None:
    """ShoulderR as the single limit "R.004 MAX" (dt_cone_gear_shaft_spec.
    FILLET_R_TOL_TYPE): swTolMAX prints the model value then MAX."""
    _, dimension = _named_dimension(adapter, "ShoulderFillets", "ShoulderR")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = FILLET_R_TOL_TYPE
    if int(tolerance.Type) != FILLET_R_TOL_TYPE:
        raise RuntimeError("ShoulderR@ShoulderFillets: swTolMAX did not persist")


async def _add_collar(
    adapter: Any, drive_jobs: list[tuple[str, str]], volume: float
) -> float:
    """The thrust collar (#914): the full Ø5/8 disc from CollarEndPlane back
    onto the collar face, joined to the journal; returns the running volume.

    Built before the gear lands, which start at its tip-side face, so nothing
    else lies inside it.  CollarWidth drives the plane (above) and the depth,
    so the knob moves the collar rather than only a depth.
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    label = f"collar d{COLLAR_DIA:g}mm to z={COLLAR_END_STATION:g}"
    collar = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("CollarEndPlane"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        COLLAR_DIA / 2.0,
        label,
        dims=collar,
        names=("CollarCx", "CollarCz", "CollarDia"),
        drives=(None, None, '"CollarDia"'),
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    check(
        f"extrude {label}",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=COLLAR_THICKNESS, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Collar")
    width_dim = name_dimensions(adapter, "Collar", ["CollarWidth"])
    drive_jobs += [(width_dim[0], '"CollarWidth"')]
    volume += math.pi / 4.0 * COLLAR_DIA**2 * COLLAR_THICKNESS
    await volume_check(adapter, label, volume, 0.005 * volume)
    return volume


def keyseat_area() -> float:
    """Cross-section (mm^2) land 1 loses to its keyseat: the part of the
    rectangle |y| <= W/2, x >= floor inside the land's circle.  Exact: the
    floor lies inside the circle's chord at y = W/2, so the area is the
    circle's strip between y = -W/2 and W/2 beyond x = floor."""
    radius = SECTION_DIAS[1] / 2.0
    half = cone_land_key.KEYSEAT_WIDTH_MM / 2.0
    floor = cone_land_key.KEYSEAT_FLOOR_OFFSET_MM
    if floor > math.sqrt(radius**2 - half**2):
        raise AssertionError("keyseat floor lies outside the land at its edges")
    strip = half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)
    return strip - 2.0 * half * floor


def keyseat_end_volume(steps: int = 4000) -> float:
    """Volume (mm^3) the end-mill plunge removes beyond the straight cut: the
    half disc of radius W/2 on the collar side of its centre, from the floor
    out to the land's round (midpoint rule over y; the integrand is smooth
    and the floor lies inside the land at the keyseat's edges)."""
    radius = SECTION_DIAS[1] / 2.0
    half = cone_land_key.KEYSEAT_WIDTH_MM / 2.0
    floor = cone_land_key.KEYSEAT_FLOOR_OFFSET_MM
    dy = 2.0 * half / steps
    total = 0.0
    for k in range(steps):
        y = -half + (k + 0.5) * dy
        total += math.sqrt(half**2 - y**2) * (math.sqrt(radius**2 - y**2) - floor) * dy
    return total


async def _cut_keyseat(adapter: Any, drive_jobs: list[tuple[str, str]]) -> float:
    """Cut land 1's keyseat and return the volume removed.

    Sketched on Sec1EndPlane, where its sizes lie in the plane a section view
    shows: a rectangle whose inner edge is the keyseat floor, ``Sec1KeyseatWidth`` long and centred on the
    sketch's x axis, and whose outer edge stands 1 mm clear of the land; a
    construction line along the x axis from the land's far side (anchored by
    ``SecDia1``/2 from the axis) to the floor's midpoint, whose length IS
    ``Sec1KeyseatS`` (ANSI B17.1 S, the across-flat's measurement form).  The
    cut runs back toward the collar (a blind cut's default, off a plane with
    material behind it) by the land's length, square at the collar's
    tip-side face.  Over that length there is no material outside the land
    for the rectangle's 1 mm margin to reach.
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    land = 1
    label = "Sec1 keyseat"
    radius = SECTION_DIAS[land] / 2.0
    floor_offset = cone_land_key.KEYSEAT_FLOOR_OFFSET_MM
    half = cone_land_key.KEYSEAT_WIDTH_MM / 2.0
    reach = radius + 1.0
    length = SECTION_ENDS[land] - COLLAR_END_STATION
    profile = "Sec1KeyseatProfile"
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("Sec1EndPlane"))
    sign = _sketch_x_per_model_x(adapter)
    bottom, outer, top, floor = await add_line_chain(
        adapter,
        [
            (sign * floor_offset, -half),
            (sign * reach, -half),
            (sign * reach, half),
            (sign * floor_offset, half),
        ],
    )
    for edge, direction in (
        (bottom, "horizontal"),
        (outer, "vertical"),
        (top, "horizontal"),
        (floor, "vertical"),
    ):
        check(
            f"{label} {direction} {edge}",
            await adapter.add_sketch_constraint(edge, None, direction),
        )
    await dimension_between(
        adapter,
        f"{bottom}.start",
        f"{bottom}.end",
        "horizontal_distance",
        reach - floor_offset,
        f"{label} reach",
    )
    dims.record("Sec1KeyseatReach")
    await dimension_between(
        adapter,
        f"{floor}.start",
        f"{floor}.end",
        "vertical_distance",
        2.0 * half,
        f"{label} width",
    )
    dims.record("Sec1KeyseatWidth", '"Sec1KeyseatW"')
    (across,) = await add_line_chain(
        adapter, [(-sign * radius, 0.0), (sign * floor_offset, 0.0)], close=False
    )
    _as_construction(adapter, across)
    check(
        f"{label} S line horizontal",
        await adapter.add_sketch_constraint(across, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter, f"{across}.start", -sign * radius, 0.0, f"{label} far side"
    )
    dims.record("Sec1FarSide", '"SecDia1" / 2')
    check(
        f"{label} S line meets the floor",
        await adapter.add_sketch_constraint(f"{across}.end", floor, "midpoint"),
    )
    await dimension_between(
        adapter,
        f"{across}.start",
        f"{across}.end",
        "horizontal_distance",
        cone_land_key.KEYSEAT_S_MM,
        f"{label} S",
    )
    dims.record("Sec1KeyseatS", '"Sec1KeyseatS"')
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    drive_jobs += dims.apply(adapter, profile)
    check(
        f"cut {label}",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=length)),
    )
    name_last_feature(adapter, "Sec1Keyseat")
    length_dim = name_dimensions(adapter, "Sec1Keyseat", ["Sec1KeyseatLength"])
    drive_jobs += [(length_dim[0], '"SecEnd1"')]
    return keyseat_area() * length


async def _cut_socket(adapter: Any, drive_jobs: list[tuple[str, str]]) -> float:
    """Cut the reamed socket for T006's spigot and return the volume removed.

    An on-axis ``SocketDia`` circle on Sec2EndPlane (the shaft's end), cut
    back into land 2 by ``SocketDepth`` -- the lands' own recipe, so its
    diameter reads on an end-on view and its depth along the shaft.
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    label = f"socket d{SOCKET_DIA:g}mm x {SOCKET_DEPTH:g}mm"
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("Sec2EndPlane"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SOCKET_DIA / 2.0,
        label,
        dims=dims,
        names=("SocketCx", "SocketCz", "SocketDia"),
        drives=(None, None, '"SocketDia"'),
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketProfile")
    drive_jobs += dims.apply(adapter, "SocketProfile")
    check(
        f"cut {label}",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=SOCKET_DEPTH)),
    )
    name_last_feature(adapter, "Socket")
    depth_dim = name_dimensions(adapter, "Socket", ["SocketDepth"])
    drive_jobs += [(depth_dim[0], '"SocketDepth"')]
    return math.pi / 4.0 * SOCKET_DIA**2 * SOCKET_DEPTH


def _as_construction(adapter: Any, entity_id: str) -> None:
    """Make a registered sketch line construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _sketch_x_per_model_x(adapter: Any) -> float:
    """+1 or -1: the active sketch's x per model +X.

    The keyseat's outward normal is the part's +X (the Right plane's normal,
    the direction the gears' keyways are clocked to); which way a land end plane's
    sketch x runs is the sketch's to state (ModelToSketchTransform), not ours
    to assume.
    """
    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    mapped = []
    for x in (0.0, 0.001):
        point = _early_bound(
            utility.CreatePoint(double_array([x, 0.0, 0.0])), "IMathPoint"
        )
        if abs(float(point.ArrayData[0]) - x) > 1e-12:
            raise RuntimeError(f"CreatePoint did not echo x={x}: {point.ArrayData}")
        moved = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        mapped.append(tuple(float(value) for value in moved.ArrayData))
    dx = mapped[1][0] - mapped[0][0]
    dy = mapped[1][1] - mapped[0][1]
    if abs(abs(dx) - 0.001) > 1e-9 or abs(dy) > 1e-9:
        raise RuntimeError(f"sketch x is not along model X: {mapped}")
    return math.copysign(1.0, dx)


def _equations_for(adapter: Any, lhs: str) -> list[str]:
    """Every equation whose left-hand side is exactly ``lhs``."""
    from solidworks_mcp.adapters.solidworks.parametrics import (
        _equation_manager,
        _read_member,
    )

    manager = _equation_manager(adapter)
    matches = []
    for index in range(int(_read_member(manager, "GetCount") or 0)):
        text = str(manager.Equation(index) or "")
        if text.partition("=")[0].strip() == lhs:
            matches.append(text)
    return matches


# A linear global keeps 8 document (inch) places: 5e-9 in, 1.3e-7 mm.
_STATION_TOLERANCE_MM = 1e-6


@_telemetry.traced("dim.station_ownership")
def _assert_stations_single_owned(adapter: Any) -> None:
    """After the deferred equations and the final rebuild.

    Each STATION_OWNERS knob must be the ONE owner of every dimension that
    carries it (Codex #839; #914 adds the collar face and the collar).  An
    equation-owned dimension reads DrivenState 1
    (driven), never 2, so the gate is single ownership: the knob is defined
    once; each dimension has exactly one equation, whose right-hand side is
    the knob; the knob's dimensions share one DrivenState; none is a
    reference dimension; and each still reads the as-built value (the drive
    is neutral) to the global's 8 inch places.  Each reading is logged, so
    the leaf log is the evidence.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    problems: list[str] = []
    for global_name, value, names in STATION_OWNERS:
        owner = f'"{global_name}"'
        definitions = _equations_for(adapter, owner)
        _telemetry.info(f"station ownership {global_name} definition {definitions}")
        if len(definitions) != 1:
            problems.append(
                f"{global_name}: expected one definition, found {definitions}"
            )
        states = {}
        for name in names:
            problems += _single_owner_problems(model, adapter, name, owner, value)
            dimension = model.Parameter(name)
            if dimension is not None:
                states[name] = int(_early_bound(dimension, "IDimension").DrivenState)
        if len(set(states.values())) > 1:
            problems.append(f"{global_name}: DrivenState differs {states}")
    if problems:
        raise RuntimeError("station ownership: " + "; ".join(problems))
    _telemetry.success(
        f"{len(STATION_OWNERS)} length knobs singly own their dimensions"
    )


def _single_owner_problems(
    model: Any, adapter: Any, name: str, owner: str, value: float
) -> list[str]:
    """Why ``name`` is not singly owned by ``owner`` at ``value`` (empty if it is)."""
    dimension = model.Parameter(name)
    if dimension is None:
        return [f"{name} not found"]
    dimension = _early_bound(dimension, "IDimension")
    equations = _equations_for(adapter, f'"{name}"')
    evidence = {
        "dimension": name,
        "equations": equations,
        "driven_state": int(dimension.DrivenState),
        "is_reference": bool(dimension.IsReference()),
        "value_mm": 1000.0 * float(dimension.SystemValue),
        "expected_mm": value,
    }
    _telemetry.info(f"station ownership {evidence}")
    problems = []
    if len(equations) != 1:
        problems.append(f"{name}: expected one equation, found {equations}")
    elif equations[0].partition("=")[2].strip() != owner:
        problems.append(f"{name}: owned by {equations[0]!r}, not {owner}")
    if evidence["is_reference"]:
        problems.append(f"{name}: became a reference dimension")
    if abs(evidence["value_mm"] - value) > _STATION_TOLERANCE_MM:
        problems.append(
            f"{name}: reads {evidence['value_mm']:.9f} mm, {owner} is {value}"
        )
    return problems


if __name__ == "__main__":
    sys.exit(run_build(build))
