r"""Reproduction script: crank handle (book ch. 11, pp. 12-15).

The pear-shaped wooden handle (stained black) that rotates on the crank-arm
pivot -- the book calls it "a smooth piece of wood ... well-suited for a firm
grip" (p.12). The brass collar at the crank end is modelled as an integral
cylindrical section of the revolve profile (it gets its own appearance at
M3 material assignment); the slotted pivot screw is a separate part
(grouped with the plain shafts/pins).

The silhouette is now genuinely SMOOTH (the earlier revision approximated it
with straight, axially-faceted segments). Two internally-tangent circular
arcs span the wood body: a long, gentle front arc swells from the neck to the
maximum diameter, and a tighter rear arc rounds off into the blunt domed butt
(truncated by a small flat where the end-cap/screw seats -- see the p.15
photo). The arcs share a horizontal tangent at the swell, so the wood reads as
one continuous curve; the only edges are the deliberate ones in the photo (the
brass-collar shoulder and the butt cap rim). Circumferentially smooth after
the revolve, as before.

Dimensions: cad/DIMENSIONS.md "Chapter 11" -- handle ~90 long x Ø22 max,
photo-scaled (low).

Layout: handle axis along +X from the origin (collar face at x=0), profile
revolved 360 deg about a centerline on the axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_handle.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    name_bore_axis,
    apply_color,
    STAINED_OAK,
    check,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "crank-handle"
MATERIAL = "Oak"  # see _common.apply_material docstring

HANDLE_LENGTH = 90.0  # DIMENSIONS.md ch11: handle length (low)
HANDLE_MAX_DIA = 22.0  # DIMENSIONS.md ch11: handle diameter (low)
COLLAR_LENGTH = 6.0  # DIMENSIONS.md ch11: brass collar, p.12 photo (low)
COLLAR_DIA = 11.0  # DIMENSIONS.md ch11: brass collar, p.12 photo (low)

COLLAR_R = COLLAR_DIA / 2.0
PEAK_R = HANDLE_MAX_DIA / 2.0
NECK_R = 4.8  # waist just below the collar (p.12 photo); < collar -> shoulder
PEAK_X = 62.0  # axial station of the maximum diameter (p.15 photo, ~0.69 L)
CAP_R = 3.5  # flat butt cap (metal disc + slot screw seat), p.15 photo

# Smooth pear silhouette = two circular arcs that meet at the swell (PEAK_X,
# PEAK_R) with a common horizontal tangent (both centres sit directly below
# the swell on x = PEAK_X), so the join is curvature-side-consistent and the
# wood is tangent-continuous from neck to butt.
#   front arc: through the neck (COLLAR_LENGTH, NECK_R) and the swell.
#   rear arc : through the swell and the butt cap rim (HANDLE_LENGTH, CAP_R).
# For a chord that rises dh over run dx to a horizontal-tangent apex, the
# radius is R = (dx^2 + dh^2) / (2 dh) and the centre is PEAK_R - R below.
_dx_f, _dh_f = PEAK_X - COLLAR_LENGTH, PEAK_R - NECK_R
FRONT_R = (_dx_f**2 + _dh_f**2) / (2.0 * _dh_f)
FRONT_CY = PEAK_R - FRONT_R
_dx_r, _dh_r = HANDLE_LENGTH - PEAK_X, PEAK_R - CAP_R
REAR_R = (_dx_r**2 + _dh_r**2) / (2.0 * _dh_r)
REAR_CY = PEAK_R - REAR_R
# Both circles pass through the swell apex (their common top point) and share
# x = PEAK_X centres -> they are internally tangent there (|ΔCY| == ΔR):
assert abs(abs(FRONT_CY - REAR_CY) - abs(FRONT_R - REAR_R)) < 1e-6


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the handle silhouette's design
    # constants as named globals driving the dimensions below. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads BARE
    # numbers in document units, so an unsuffixed 90 would be read as 90 inches
    # and blow the part up 25.4x. The two arc radii/centres are a non-trivial
    # closed form of these knobs (R = (dx^2 + dh^2) / 2dh); only the clean knobs
    # (length, collar, peak station) drive dims -- the derived arc-centre depths
    # stay auto-named/static (no single-global expression, see drives below).
    await set_global(adapter, "HandleLength", f"{HANDLE_LENGTH}mm")
    await set_global(adapter, "HandleMaxDia", f"{HANDLE_MAX_DIA}mm")
    await set_global(adapter, "CollarLength", f"{COLLAR_LENGTH}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "NeckR", f"{NECK_R}mm")
    await set_global(adapter, "PeakX", f"{PEAK_X}mm")
    await set_global(adapter, "CapR", f"{CAP_R}mm")

    # Per-sketch SketchDims records each dim in emission order; apply() renames
    # them and collects the drive jobs run in one deferred batch at the end (every
    # equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the shallow front arc / collar
    # shoulder to auto relations (see crank pin lesson).
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, HANDLE_LENGTH, 0.0),
    )
    # Brass collar as three lines: face -> outer cylinder -> shoulder step.
    collar = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (0.0, COLLAR_R),
            (COLLAR_LENGTH, COLLAR_R),
            (COLLAR_LENGTH, NECK_R),
        ],
        close=False,
    )
    collar_face, collar_top, collar_step = collar
    # add_arc draws CCW from start to end; order each so the CCW sweep is the
    # minor (silhouette) arc over the top of its big circle.
    front_arc = check(
        "front swell arc",
        await adapter.add_arc(
            PEAK_X, FRONT_CY, PEAK_X, PEAK_R, COLLAR_LENGTH, NECK_R
        ),
    )
    rear_arc = check(
        "rear butt arc",
        await adapter.add_arc(
            PEAK_X, REAR_CY, HANDLE_LENGTH, CAP_R, PEAK_X, PEAK_R
        ),
    )
    cap_face = check(
        "butt cap face",
        await adapter.add_line(HANDLE_LENGTH, CAP_R, HANDLE_LENGTH, 0.0),
    )
    check(
        "axis closure",
        await adapter.add_line(HANDLE_LENGTH, 0.0, 0.0, 0.0),
    )
    set_sketch_direct_db(adapter, False)

    # 16-DOF profile. The centerline merged into the (0, 0) / (HANDLE_LENGTH,
    # 0) chain ends, so horizontal + a length dim on it pin the axis (as in
    # crank-pin). The collar face/top/step get h/v + linear dims; each arc
    # centre is anchored (radius then derives from a pinned point -- the neck
    # for the front arc, the tangency for the rear), and a single tangent
    # relation locks the swell join and sizes the rear arc. Dimensioning a
    # radius on top of that would over-define, so neither arc carries one.
    check(
        "anchor collar face",
        await adapter.add_sketch_constraint(
            f"{collar_face}.start", "origin", "coincident"
        ),
    )
    check(
        "axis horizontal",
        await adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    # Record each manual dim into SketchDims as it is created (creation order).
    check(
        "handle length",
        await adapter.add_sketch_dimension(centerline, None, "linear", HANDLE_LENGTH),
    )
    profile.record("HandleLength", '"HandleLength"')
    # collar face -> CollarR (= CollarDia/2); collar top -> CollarLength;
    # collar step -> CollarR - NeckR (shoulder, derived); cap face has no dim.
    for label, ent, relation, value, name, drive in (
        ("collar face", collar_face, "vertical", COLLAR_R,
         "CollarR", '"CollarDia" / 2'),
        ("collar top", collar_top, "horizontal", COLLAR_LENGTH,
         "CollarLength", '"CollarLength"'),
        ("collar step", collar_step, "vertical", COLLAR_R - NECK_R,
         "CollarStep", '"CollarDia" / 2 - "NeckR"'),
        ("cap face", cap_face, "vertical", None, None, None),
    ):
        check(
            f"{label} {relation}",
            await adapter.add_sketch_constraint(ent, None, relation),
        )
        if value is not None:
            check(
                f"{label} dim",
                await adapter.add_sketch_dimension(ent, None, "linear", value),
            )
            profile.record(name, drive)
    # Each arc centre is off-axis (PEAK_X != 0, *_CY < 0): anchor_point_to_origin
    # emits a horizontal then a vertical distance dim. The horizontal span is
    # PEAK_X (clean knob -> "PeakX"); the vertical span is the arc-centre depth
    # |*_CY|, a non-trivial closed form of several knobs with no single-global
    # expression, so it stays auto-named/static (None). The depth is a NEGATIVE
    # coordinate displayed as its magnitude -- recorded with no drive, so the
    # unsigned-distance trap (a negative drive failing at equation-add) can't bite.
    await anchor_point_to_origin(
        adapter, f"{front_arc}.center", PEAK_X, FRONT_CY, "front arc centre"
    )
    profile.record("FrontArcCx", '"PeakX"')
    profile.record(None, None)
    await anchor_point_to_origin(
        adapter, f"{rear_arc}.center", PEAK_X, REAR_CY, "rear arc centre"
    )
    profile.record("RearArcCx", '"PeakX"')
    profile.record(None, None)
    check(
        "swell tangent",
        await adapter.add_sketch_constraint(front_arc, rear_arc, "tangent"),
    )
    await ensure_fully_defined(adapter, "handle profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "HandleProfile")
    drive_jobs += profile.apply(adapter, "HandleProfile")

    check(
        "revolve handle",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Handle")

    # Capture the as-built volume as the neutrality reference (the revolved
    # twin-arc silhouette has no tidy closed form), then apply the deferred drive
    # equations after the model + a rebuild exists so every target resolves. Each
    # equation evaluates to the value just built, so the geometry must not move.
    mass = await adapter.get_mass_properties()
    v_handle = float(mass.data.volume)
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven crank handle (equations neutral)", v_handle, 0.001 * v_handle
    )

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "handle axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, STAINED_OAK)  # ch30 plates: see _common palette
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
