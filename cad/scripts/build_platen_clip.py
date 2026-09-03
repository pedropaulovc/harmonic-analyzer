r"""Reproduction script: one-piece platen paper holder (book ch. 22, pp. 54-55).

One of the two bright brass holders hugging the platen front's extreme
left/right edges, running from the TOP edge down about 84 mm.  The reference
photos show one slotted sheet: a flat screw rail and an
adjacent spring rail are separated by open-ended lengthwise notches.  The
notches stop before the middle, leaving one intact bridge between the rails.
Each free half of the spring rail bows shallowly away from the platen and
returns to the sheet plane at its rounded paper-contact end.

The model is one merged brass body with no added end flange or independent
motion.  The two existing #4 clearance holes lie only in the 4 mm flat rail.
The 0.8 mm sheet thickness and 1.5 mm arch rise retain the photo-proportioned
values from the earlier interpretation while correcting its topology.

Used twice in paper-drive.SLDASM.  Length is local +X, total width is local +Y,
and the flat rail's outward face is local z = 0.  The assembly turns the holder
-90 degrees about Z and places local z = SHEET_T against the platen.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen_clip.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    name_dimensions,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _holes import CLEARANCE_MM, HoleSpec, wizard_holes
from fillister_screw_spec import HEAD_DIA as CLIP_SCREW_HEAD_DIA

PART_NAME = "platen-clip"
MATERIAL = "Brass"  # see _common.apply_material docstring

CLIP_LENGTH = (
    83.5  # ch22 p.55 rear photo: 86.7 of the 140 mm plate (0.619) x PLATE_HEIGHT 134.82
)
CLIP_WIDTH = 8.988  # ch30-p002 Pose Studio: 10 * 0.8988
SHEET_T = 0.8  # photo-backed brass sheet thickness
CLIP_THICKNESS = SHEET_T  # assembly stand-off: one sheet, not a face stack

SCREW_RAIL_WIDTH = 4.0
CLIP_SCREW_HEAD_CLEARANCE = 0.05
NOTCH_WIDTH = (
    CLIP_SCREW_HEAD_DIA / 2.0
    - SCREW_RAIL_WIDTH / 2.0
    + CLIP_SCREW_HEAD_CLEARANCE
)
SPRING_RAIL_WIDTH = CLIP_WIDTH - SCREW_RAIL_WIDTH - NOTCH_WIDTH
SPRING_RAIL_Y0 = SCREW_RAIL_WIDTH + NOTCH_WIDTH
CENTER_BRIDGE_LENGTH = 5.0
NOTCH_LENGTH = (CLIP_LENGTH - CENTER_BRIDGE_LENGTH) / 2.0
SPRING_END_RADIUS = SPRING_RAIL_WIDTH / 2.0
ARCH_RISE = 1.5  # shallow outward bow; editable as ArchRise in Tools > Equations

# The brass fillister clip screws retain their existing lengthwise stations.
# Their transverse station is explicit because the holes belong to the flat
# rail; the adjacent notch clears each Ø5.5 head before the spring bows outward.
HOLE_INSET = 7.1904  # ch30-p002 Pose Studio: 8 * 0.8988 from each end
HOLE_Y = SCREW_RAIL_WIDTH / 2.0
HOLE_DIA = CLEARANCE_MM[("#4", "normal")]

# The rounded tips occupy one end-radius of flat tangent run before each arch.
# The four equal sloped runs form two symmetric shallow bows.  Between them,
# the spring rail lies in the sheet plane for the full 5 mm middle bridge,
# making that connection both photo-visible and robustly merged.  Physical
# coordinates are (local X, local Z) on the spring rail's outward face;
# negative Z is away from the platen.
_BRIDGE_X0 = (CLIP_LENGTH - CENTER_BRIDGE_LENGTH) / 2.0
_BRIDGE_X1 = _BRIDGE_X0 + CENTER_BRIDGE_LENGTH
_ARCH_RUN = (_BRIDGE_X0 - 2.0 * SPRING_END_RADIUS) / 2.0
ARCH_FRONT_XZ = (
    (SPRING_END_RADIUS, 0.0),
    (2.0 * SPRING_END_RADIUS, 0.0),
    (2.0 * SPRING_END_RADIUS + _ARCH_RUN, -ARCH_RISE),
    (_BRIDGE_X0, 0.0),
    (_BRIDGE_X1, 0.0),
    (CLIP_LENGTH - 2.0 * SPRING_END_RADIUS - _ARCH_RUN, -ARCH_RISE),
    (CLIP_LENGTH - 2.0 * SPRING_END_RADIUS, 0.0),
    (CLIP_LENGTH - SPRING_END_RADIUS, 0.0),
)

MODEL_FEATURES = (
    "FlatRail",
    "CenterBridge",
    "SpringArch",
    "RoundedSpringEnds",
    "ScrewHoles",
)
BOSS_DRIVES = {
    "FlatRail": ('"SheetT"',),
    "CenterBridge": ('"SheetT"',),
    "SpringArch": ('"SpringRailW"', '"SpringRailY0"'),
    "RoundedSpringEnds": ('"SheetT"',),
}


V_FLAT_RAIL = CLIP_LENGTH * SCREW_RAIL_WIDTH * SHEET_T
V_CENTER_BRIDGE = CENTER_BRIDGE_LENGTH * NOTCH_WIDTH * SHEET_T
V_SPRING_CORE = (
    (CLIP_LENGTH - 2.0 * SPRING_END_RADIUS) * SPRING_RAIL_WIDTH * SHEET_T
)
# Each full end circle overlaps one half-circle of the flat tangent run, leaving
# exactly two outer half-circles of additional material.
V_ROUNDED_ENDS = math.pi * SPRING_END_RADIUS**2 * SHEET_T
V_HOLES = 2.0 * math.pi * (HOLE_DIA / 2.0) ** 2 * SHEET_T
V_FINAL = V_FLAT_RAIL + V_CENTER_BRIDGE + V_SPRING_CORE + V_ROUNDED_ENDS - V_HOLES

if not math.isclose(
    SCREW_RAIL_WIDTH + NOTCH_WIDTH + SPRING_RAIL_WIDTH,
    CLIP_WIDTH,
    abs_tol=1e-9,
):
    raise AssertionError("platen clip lane widths must close to ClipWidth")
if not math.isclose(
    2.0 * NOTCH_LENGTH + CENTER_BRIDGE_LENGTH, CLIP_LENGTH, abs_tol=1e-9
):
    raise AssertionError("opposed platen clip notches must stop at one center bridge")
if HOLE_Y - HOLE_DIA / 2.0 <= 0.0 or HOLE_Y + HOLE_DIA / 2.0 >= SCREW_RAIL_WIDTH:
    raise AssertionError("platen clip screw holes must stay wholly inside the flat rail")
if not math.isclose(
    SPRING_RAIL_Y0 - (HOLE_Y + CLIP_SCREW_HEAD_DIA / 2.0),
    CLIP_SCREW_HEAD_CLEARANCE,
    abs_tol=1e-9,
):
    raise AssertionError("platen clip notch must clear the fillister screw heads")
if _ARCH_RUN <= 0.0 or ARCH_RISE <= 0.0:
    raise AssertionError("platen clip spring arches need positive run and rise")


async def _rect(
    adapter,
    label: str,
    name: str,
    rect: list[tuple[float, float]],
    dims: SketchDims,
    names,
    drives,
):
    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label=label, dims=dims, names=names, drives=drives
    )
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, name)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations).  The mm suffix is load-bearing because
    # the template is IPS and bare equation-manager numbers are document units.
    await set_global(adapter, "ClipLength", f"{CLIP_LENGTH}mm")
    await set_global(adapter, "ClipWidth", f"{CLIP_WIDTH}mm")
    await set_global(adapter, "SheetT", f"{SHEET_T}mm")
    await set_global(adapter, "ScrewRailW", f"{SCREW_RAIL_WIDTH}mm")
    await set_global(adapter, "NotchW", f"{NOTCH_WIDTH}mm")
    await set_global(
        adapter, "SpringRailW", '"ClipWidth" - "ScrewRailW" - "NotchW"'
    )
    await set_global(adapter, "SpringRailY0", '"ScrewRailW" + "NotchW"')
    await set_global(adapter, "CenterBridgeL", f"{CENTER_BRIDGE_LENGTH}mm")
    await set_global(adapter, "BridgeX0", '("ClipLength" - "CenterBridgeL") / 2')
    await set_global(adapter, "SpringEndR", '"SpringRailW" / 2')
    await set_global(adapter, "ArchRise", f"{ARCH_RISE}mm")
    await set_global(
        adapter,
        "ArchRun",
        '(("ClipLength" - "CenterBridgeL") / 2 - 2 * "SpringEndR") / 2',
    )
    await set_global(adapter, "HoleInset", f"{HOLE_INSET}mm")
    await set_global(adapter, "HoleY", '"ScrewRailW" / 2')
    await set_global(adapter, "HoleFarX", '"ClipLength" - "HoleInset"')

    drive_jobs: list[tuple[str, str]] = []

    # Flat rail: the only full-length planar lane and the only lane drilled for
    # the two retaining screws.
    flat = SketchDims()
    await _rect(
        adapter,
        "flat rail outline",
        "FlatRailProfile",
        [
            (0.0, 0.0),
            (CLIP_LENGTH, 0.0),
            (CLIP_LENGTH, SCREW_RAIL_WIDTH),
            (0.0, SCREW_RAIL_WIDTH),
        ],
        flat,
        ["Length", "Width"],
        ['"ClipLength"', '"ScrewRailW"'],
    )
    drive_jobs += flat.apply(adapter, "FlatRailProfile")
    check(
        "extrude flat rail",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHEET_T)),
    )
    name_last_feature(adapter, "FlatRail")
    flat_dims = name_dimensions(adapter, "FlatRail", ["SheetDepth"])
    drive_jobs += [(flat_dims[0], BOSS_DRIVES["FlatRail"][0])]
    await volume_check(adapter, "flat rail", V_FLAT_RAIL, 0.005 * V_FLAT_RAIL)

    # The two open-ended notches are the absence of material between lanes from
    # each outer end to this one intact 5 mm middle bridge.
    bridge_x0 = _BRIDGE_X0
    bridge = SketchDims()
    await _rect(
        adapter,
        "center bridge outline",
        "CenterBridgeProfile",
        [
            (bridge_x0, SCREW_RAIL_WIDTH),
            (bridge_x0 + CENTER_BRIDGE_LENGTH, SCREW_RAIL_WIDTH),
            (bridge_x0 + CENTER_BRIDGE_LENGTH, SPRING_RAIL_Y0),
            (bridge_x0, SPRING_RAIL_Y0),
        ],
        bridge,
        ["BridgeLength", "BridgeWidth", "BridgeX0", "BridgeY0"],
        ['"CenterBridgeL"', '"NotchW"', '"BridgeX0"', '"ScrewRailW"'],
    )
    drive_jobs += bridge.apply(adapter, "CenterBridgeProfile")
    check(
        "extrude center bridge",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHEET_T)),
    )
    name_last_feature(adapter, "CenterBridge")
    bridge_dims = name_dimensions(adapter, "CenterBridge", ["SheetDepth"])
    drive_jobs += [(bridge_dims[0], BOSS_DRIVES["CenterBridge"][0])]
    volume = V_FLAT_RAIL + V_CENTER_BRIDGE
    await volume_check(adapter, "flat rail and center bridge", volume, 0.005 * volume)

    # Spring rail longitudinal section on Top: sketch (x, y) maps to part
    # (X, -Z).  Its outward and platen-side boundaries use the same station
    # ordinates, separated vertically by SheetT.  This keeps the part one merged
    # body while the ArchRise equation drives both symmetric free halves.
    front_sketch = [(x, -z) for x, z in ARCH_FRONT_XZ]
    back_sketch = [(x, -z - SHEET_T) for x, z in reversed(ARCH_FRONT_XZ)]
    arch_points = front_sketch + back_sketch
    arch = SketchDims()
    check("create_sketch spring arch", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    arch_lines = await add_line_chain(adapter, arch_points)
    set_sketch_direct_db(adapter, False)
    run_expr = '"ArchRun"'
    rise_expr = '"ArchRise"'
    await define_polygon_chain(
        adapter,
        arch_lines,
        arch_points,
        label="spring arch section",
        dims=arch,
        names=[
            "SpringStartX",
            "TipRunL",
            "FrontRunL1",
            "FrontRiseL",
            "FrontRunL2",
            "FrontFallL",
            "CenterReturn",
            "FrontRunR1",
            "FrontRiseR",
            "FrontRunR2",
            "FrontFallR",
            "TipRunR",
            "SectionT",
            "BackTipRunR",
            "BackRunR1",
            "BackRiseR",
            "BackRunR2",
            "BackFallR",
            "BackCenterReturn",
            "BackRunL1",
            "BackRiseL",
            "BackRunL2",
            "BackFallL",
            "BackTipRunL",
        ],
        drives=[
            '"SpringEndR"',
            '"SpringEndR"',
            run_expr,
            rise_expr,
            run_expr,
            rise_expr,
            '"CenterBridgeL"',
            run_expr,
            rise_expr,
            run_expr,
            rise_expr,
            '"SpringEndR"',
            '"SheetT"',
            '"SpringEndR"',
            run_expr,
            rise_expr,
            run_expr,
            rise_expr,
            '"CenterBridgeL"',
            run_expr,
            rise_expr,
            run_expr,
            rise_expr,
            '"SpringEndR"',
        ],
    )
    await ensure_fully_defined(adapter, "spring arch section")
    check("exit_sketch spring arch", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringArchProfile")
    drive_jobs += arch.apply(adapter, "SpringArchProfile")
    extrude_at_offset(adapter, SPRING_RAIL_WIDTH, SPRING_RAIL_Y0)
    name_last_feature(adapter, "SpringArch")
    # Offset bosses expose depth first and start offset second.
    spring_dims = name_dimensions(
        adapter, "SpringArch", ["RailWidth", "RailStart"]
    )
    drive_jobs += list(zip(spring_dims, BOSS_DRIVES["SpringArch"], strict=True))
    volume += V_SPRING_CORE
    await volume_check(adapter, "spring arch", volume, 0.005 * volume)

    # Full circles overlap the flat tangent portion of the spring core by one
    # half each.  Their exposed halves give both free ends a rounded planform.
    ends = SketchDims()
    check("create_sketch rounded spring ends", await adapter.create_sketch("Front"))
    spring_y = SPRING_RAIL_Y0 + SPRING_RAIL_WIDTH / 2.0
    define_jobs = (
        (
            SPRING_END_RADIUS,
            ("LeftEndX", "EndY", "LeftEndDia"),
            ('"SpringEndR"', '"SpringRailY0" + "SpringEndR"', '2 * "SpringEndR"'),
        ),
        (
            CLIP_LENGTH - SPRING_END_RADIUS,
            ("RightEndX", "RightEndY", "RightEndDia"),
            ('"ClipLength" - "SpringEndR"', '"SpringRailY0" + "SpringEndR"', '2 * "SpringEndR"'),
        ),
    )
    for x, names, drives in define_jobs:
        await define_circle(
            adapter,
            x,
            spring_y,
            SPRING_END_RADIUS,
            "rounded spring end",
            dims=ends,
            names=names,
            drives=drives,
        )
    await ensure_fully_defined(adapter, "rounded spring ends")
    check("exit_sketch rounded spring ends", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringEndProfiles")
    drive_jobs += ends.apply(adapter, "SpringEndProfiles")
    check(
        "extrude rounded spring ends",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHEET_T)),
    )
    name_last_feature(adapter, "RoundedSpringEnds")
    end_dims = name_dimensions(adapter, "RoundedSpringEnds", ["SheetDepth"])
    drive_jobs += [(end_dims[0], BOSS_DRIVES["RoundedSpringEnds"][0])]
    volume += V_ROUNDED_ENDS
    await volume_check(adapter, "rounded spring ends", volume, 0.005 * volume)

    # One native Hole Wizard #4 clearance feature, two points, both wholly in
    # the flat rail.  No opening or hole crosses the spring lane.
    hole_cut = wizard_holes(
        adapter,
        HoleSpec("clearance", "#4"),
        [
            [HOLE_INSET, HOLE_Y, 0.0],
            [CLIP_LENGTH - HOLE_INSET, HOLE_Y, 0.0],
        ],
        (0.0, 0.0, -1.0),
        "flat-rail screw holes (#4 clearance)",
        name="ScrewHoles",
        placement_dims=[
            (("LeftX", '"HoleInset"'), ("LeftZ", '"HoleY"')),
            (("RightX", '"HoleFarX"'), ("RightZ", '"HoleY"')),
        ],
    )
    drive_jobs += hole_cut.placement_drive_jobs
    await volume_check(adapter, "one-piece clip", V_FINAL, 0.005 * V_FLAT_RAIL)

    # Apply deferred equations after every target exists.  Their initial values
    # are neutral, so the second volume check also catches a mis-bound arch knob.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven one-piece clip (equations neutral)", V_FINAL, 0.005 * V_FLAT_RAIL
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
