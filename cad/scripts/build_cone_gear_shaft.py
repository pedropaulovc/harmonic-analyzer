r"""Reproduction script: cone gear shaft (book ch. 12, pp. 16-21) -- stepped.

Steel shaft carrying the 20-gear cone set (all gears fixed to and
rotating with the shaft), with its large-end bearing journal in the green
pivot post and its thin end located by the external spacer and cup-ended
adjuster -- the post and adjuster carrier both stand on the swing platform,
so the whole set pivots out of engagement as one
unit (ch. 25; p. 18 "pivot"). At the finer module DP 49.82 (ch13 OD 62.2) the
tip gears are tiny -- T006 OD is 4.08 mm -- so the shaft steps down far
more at the thin end to match the configured gear bores AND stay inside
each gear's root circle (`build_cone_gear.py` ``BoreDia``, DIMENSIONS.md
Appendix C #7). Gears attach by means the book never shows (p.21 macro
shows solder blobs at the small gears) -- no keyseat, the shaft steps are
plain; the four yellow tip gears (T006..T024) are a harder high-zinc
yellow metal soldered on.

Sections, FRONT STUB end at z = 0.  The v2 post puts that end at cone
station -61.9068609979, 1.0 mm proud of the post front face.  An integral
Ø12.2308 journal runs to z = 43.011 in the post's Ø12.2808 bore, where an
integral Ø15.0 thrust collar (#914) fills the 1.681 to the 64T and bears on
the post's north boss face, then steps to the existing 3/8 in gear-seat shaft. M6.7
(true-cone mesh, see the assembly docstring): gear seats at the
exact-tracking stack pitch 6.8889 mm (= drum z-pitch 7.0565 x
cos 12.52 deg), seat centres at FRONT_STUB + 28.25 + 6.8889 j, gear
faces 6.5 -- each step lands in the ~0.39 mm air gap between adjacent
gear faces (stations below quoted from the legacy pivot end):

* 12.2308 mm x 43.011 -- v2 pivot-post bearing journal, 0.05 diametral
  running clearance
* 3/8 in x 135.0 -- 64T at stations 14.9..24.9 + seats T120..T030
* 1/4 in x 141.9 -- T024 seat
* 1/8 in x 148.8 -- T018 seat
* 1/16 in x 138.9788 -- T012 and T006 seats and tip journal; contacts the
  exact McMaster 94025A164 conical cup apex at 9.5 mm thread engagement
  (rule-12 E11).  Its 23.294 mm terminal land also carries the 4 mm tip bushing.  U40
  (2026-09-23) moved every small land one station toward the big end at
  unchanged overall length, so this land now also carries T012 and runs at
  L/D 14.7; it is turned with tailstock support (a drawing note).  1/16 in
  is the largest step the T006 rim tolerates (0.543 mm under the as-cut
  base-chord root) -- see cone_gear_shaft_spec.SECTIONS.

Dimensions: cad/DIMENSIONS.md "Chapter 12" -- the journal comes from the
manually rederived v2 post bore and its 42.011 axial body; the gear-seat
stations and diameters remain the legacy/derived stack (Appendix C #7).

Build: five coaxial Front-plane circles extruded +Z to each section's end
station with ``merge_result`` -- each smaller cylinder is contained in
its larger neighbour over the shared length, so the union is exactly the
stepped shaft (volume check is exact per section, no offset planes
needed).

Layout: shaft axis along +Z, large (pivot) end at the origin -- along
the assembly depth like the gears (`build_cone_gear.py` axis = Z), so
the drive-train assembly inclines the whole cone set with one Ry(-19.8)
rotation (DIMENSIONS.md ch. 13 drive-train layout).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_gear_shaft.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
from _common import (
    IN,
    SketchDims,
    _early_bound,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _gear import volume_check
from _part_pmi import author_part_pmi
from cone_gear_shaft_spec import (
    COLLAR_DIA,
    COLLAR_END_STATION,
    COLLAR_START_STATION,
    COLLAR_THICKNESS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FILLET_RADIUS,
    SECTION_DIA_BANDS,
    SECTIONS,
    SURFACE_FINISHES,
)

PART_NAME = "cone-gear-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# FRONT_STUB = 61.9068609979: with the final coupled-layout post centred at
# cone station -39.90136099793 and spanning 42.011 along that axis, the shaft begins 1.0 mm
# proud of the front face.  The Ø12.2308 integral journal occupies local
# 0..43.011 in the post's Ø12.2808 bore; downstream 3/8-in and smaller gear
# seats retain their world stations because every old local end receives the
# 49.6068609979 stub delta.

# SECTIONS (diameter in inches, section end station in mm from the FRONT STUB
# end) now lives in cone_gear_shaft_spec.py -- the pure-data contract the
# drawing shares -- and is imported above; the derivation stays here. M6.7
# exact-tracking seat pitch 6.8889 (= 7.0565 drum z-pitch x cos 12.5188 deg,
# the shallower incline at DP 49.82): seat j spans 28.25 + 6.8889 j +- 3.25
# from the pivot end; each step station sits in the ~0.39 air gap between
# faces (T030 north 134.83 | 135.0 | T024 south 135.22, and so on; U40).
# Diameters agree with build_cone_gear.bore_dia_in (snug perpendicular seats),
# stepping much finer than the old DP 30 shaft because the tip gears shrank:
# T006 OD is now 4.08 mm.  The terminal land stops at 1/16": below that the
# T006 rim gains little and the journal becomes unturnable (L/D 31 at 1/32").


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): one diameter + one end station per
    # section. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units. The section diameters
    # come from SECTIONS in inches (the first is the metric v2 journal converted
    # to inches by the pure-data spec). The end stations are extrude DEPTHS
    # (feature parameters); each is named Sec{i}End and driven by its SecEnd{i}
    # global below, so the knobs really reshape the shaft AND the stations are
    # markable manufacturing dimensions for the drawing. A land sketched on its
    # own offset plane has that plane's offset driven by the same SecEnd{i}, so
    # the knob moves the shoulder and the depth back to the large end together.
    for i, (dia_in, end_z) in enumerate(SECTIONS):
        await set_global(adapter, f"SecDia{i}", f"{dia_in * IN}mm")
        await set_global(adapter, f"SecEnd{i}", f"{end_z}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarEnd", f"{COLLAR_END_STATION}mm")
    await set_global(adapter, "CollarWidth", f"{COLLAR_THICKNESS}mm")

    drive_jobs: list[tuple[str, str]] = []

    volume = 0.0
    prev_end = 0.0
    for i, (dia_in, end_z) in enumerate(SECTIONS):
        label = f"section d{dia_in:g}in to z={end_z:g}"
        # Each land is a cylinder from the large-end face to its own end
        # station, so every smaller land is contained in its larger neighbour
        # and the running volume stays exact per section.
        #
        # WHERE the profile circle sits is a drawing decision: a diameter
        # dimension can only be dragged into the side view at the station its
        # sketch occupies.  Sketching all five circles on the Front plane put
        # all five diameters at the large-end face, which is why the sheet
        # used to pile them as leadered callouts beside an end view.  Land 0
        # is sketched on the Front plane (its circle IS the large-end face);
        # every other land is sketched on an offset plane AT ITS END STATION
        # and extruded BACK to that face, which leaves each diameter on its
        # own shoulder while the extrude depth is still the station itself.
        if i == 0:
            plane_name = "Front"
        else:
            check(
                f"create_plane end of {label}",
                await adapter.create_plane(
                    CreatePlaneParameters(
                        mode="offset", base_plane="Front Plane", offset=end_z
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
                ExtrusionParameters(depth=end_z, reverse_direction=i > 0)
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

    # Thrust collar (#914): the ring from the journal end to the 64T, the one
    # land that is not contained in its neighbour, so it is sketched on a
    # plane at its north face and extruded back one web onto the 3/8 in land.
    # CollarEnd drives the plane and CollarWidth the web, so the knobs move
    # the collar rather than only a depth.
    label = f"collar d{COLLAR_DIA:g}mm to z={COLLAR_END_STATION:g}"
    check(
        f"create_plane end of {label}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=COLLAR_END_STATION
            )
        ),
    )
    name_last_feature(adapter, "CollarEndPlane")
    plane_dim = name_dimensions(adapter, "CollarEndPlane", ["CollarStation"])
    drive_jobs += [(plane_dim[0], '"CollarEnd"')]
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
    land_dia = SECTIONS[1][0] * IN
    volume += math.pi / 4.0 * (COLLAR_DIA**2 - land_dia**2) * COLLAR_THICKNESS
    await volume_check(adapter, label, volume, 0.005 * volume)
    # The collar's south face is the thrust face the drive train seats on the
    # post boss.  A point pick there is ambiguous (the post face lies under
    # it), so it gets a named plane, owned like the journal by SecEnd0.
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

    # Shoulder roots.  ONE constant-radius fillet over the three gear-seat
    # step edges, each picked by a point on the SMALLER land's circle at that
    # station; the nearest other edge is 0.79 mm away radially and 6.9 mm
    # axially.  Tangent propagation is off: every seed is already a complete
    # closed circle.  The collar's two roots stay sharp: the post boss and the
    # 64T bear flat against its faces, and a root radius would stand on the
    # post bore's and the 64T bore's edges -- the title block's edge break on
    # those parts is what clears the tool's nose radius.  (The old journal
    # step edge is buried under the collar.)
    fillet_edges = [
        [SECTIONS[i + 1][0] * IN / 2.0, 0.0, end_z]
        for i, (_dia_in, end_z) in enumerate(SECTIONS[1:-1], start=1)
    ]
    check(
        "fillet shoulder roots",
        await adapter.add_fillet(FILLET_RADIUS, fillet_edges, propagate=False),
    )
    name_last_feature(adapter, "ShoulderFillets")
    name_dimensions(adapter, "ShoulderFillets", ["ShoulderR"])
    # Three R0.10 rounds add ~0.1 mm^3 to a ~13000 mm^3 shaft: this checks
    # that the fillet did not eat a land, not that it moved the number.
    await volume_check(adapter, "shoulder fillets", volume, 0.005 * volume)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cone-gear shaft (equations neutral)", volume, 0.005 * volume
    )
    _assert_shoulder_planes_single_owned(adapter)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The five turned diameters carry their fit on the MODEL dimension, so
    # SolidWorks renders the limits and re-renders them on a unit change. The
    # sheet used to append "+0.00/-0.02" as frozen callout text instead.
    for section, band in enumerate(SECTION_DIA_BANDS):
        set_dimension_bilateral_tolerance(
            adapter,
            f"Sec{section}Profile",
            f"Sec{section}Dia",
            *deviations(band),
        )
    # Display precision is model-owned too (drawing-simplicity policy rule 2).
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The two lands that RUN carry a roughness symbol.  No datums and no
    # feature-control frames (drawing-simplicity policy rule 3).
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


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


@_telemetry.traced("dim.shoulder_plane_ownership")
def _assert_shoulder_planes_single_owned(adapter: Any) -> None:
    """After the deferred equations and the final rebuild.

    SecEnd{i} must be the ONE owner of both the offset plane land i is
    sketched on and that land's depth back to the large end (Codex #839).  An
    equation-owned dimension reads DrivenState 1 (driven), never 2, so the gate
    is single ownership, checked on the plane AND the depth alike: SecEnd{i}
    is defined once; each dimension has exactly one equation, whose
    right-hand side is SecEnd{i}; both read the same DrivenState; neither is a
    reference dimension; and both still read the as-built station (the drive
    is neutral) to the global's 8 inch places.  Each reading is logged, so the
    leaf log is the evidence.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    problems: list[str] = []
    for i, (_dia_in, end_z) in enumerate(SECTIONS):
        if i == 0:
            continue
        owner = f'"SecEnd{i}"'
        globals_ = _equations_for(adapter, owner)
        _telemetry.info(f"shoulder plane ownership SecEnd{i} definition {globals_}")
        if len(globals_) != 1:
            problems.append(f"SecEnd{i}: expected one definition, found {globals_}")
        states = {}
        for name in (f"Sec{i}Station@Sec{i}EndPlane", f"Sec{i}End@Sec{i}"):
            problems += _single_owner_problems(model, adapter, name, owner, end_z)
            dimension = model.Parameter(name)
            if dimension is not None:
                states[name] = int(_early_bound(dimension, "IDimension").DrivenState)
        if len(set(states.values())) > 1:
            problems.append(f"SecEnd{i}: plane and depth DrivenState differ {states}")
    if problems:
        raise RuntimeError("SecEnd ownership: " + "; ".join(problems))
    _telemetry.success(f"SecEnd owns {len(SECTIONS) - 1} shoulder planes and depths")


def _single_owner_problems(
    model: Any, adapter: Any, name: str, owner: str, end_z: float
) -> list[str]:
    """Why ``name`` is not singly owned by ``owner`` at ``end_z`` (empty if it is)."""
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
        "station_mm": end_z,
    }
    _telemetry.info(f"shoulder plane ownership {evidence}")
    problems = []
    if len(equations) != 1:
        problems.append(f"{name}: expected one equation, found {equations}")
    elif equations[0].partition("=")[2].strip() != owner:
        problems.append(f"{name}: owned by {equations[0]!r}, not {owner}")
    if evidence["is_reference"]:
        problems.append(f"{name}: became a reference dimension")
    if abs(evidence["value_mm"] - end_z) > _STATION_TOLERANCE_MM:
        problems.append(
            f"{name}: reads {evidence['value_mm']:.9f} mm, {owner} is {end_z}"
        )
    return problems


if __name__ == "__main__":
    sys.exit(run_build(build))
