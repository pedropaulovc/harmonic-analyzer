r"""Reproduction script: rocker pivot bracket (book ch. 14 pp. 26-27; 2 used).

The black steel bracket that carries each end of the rocker pivot shaft on
the green rocker-arm support (ch14 page002_img01/img02, page002_img07
"pivot"). 2026-09-02 photo re-derive: it is an L, not a T -- the ear stands
at one END of the foot, the foot is only as wide as the support's apex, and
a bright BALL sits on the ear at the pivot (the chrome sphere of
page002_img01), cross-bored for the O6.35 shaft.

TODO(build_channel_assembly.py -- owned by the lead): the foot is now
ASYMMETRIC along Z (it runs from the ear toward local +Z), so one IDENTITY
pose no longer serves both shaft ends. The SOUTH bracket (mount_z -74.17,
whose inboard side is +Z) stays IDENTITY; the NORTH bracket (mount_z
+81.83, inboard = -Z) must be inserted with Ry(180) about its bore axis --
euler [0, 180, 0], rows ROT_Y_180 = [[-1,0,0],[0,1,0],[0,0,-1]] -- so its
foot also runs INBOARD under the outer arms. Ry180 about the part origin
keeps the bore at (x 72.9, y 253.8, z mount_z) exactly (the bore is on the
part's y axis), so PIVOT/SUPPORT_APEX_Y/PIVOT_BRACKET_Z are unchanged; the
_locate_to_datum "pivot bracket datum x/z" distance mates then see flipped
Right/Front normals on that instance (a "@<diag>" flip-seed suffix may be
needed in _assembly._FLIP_INVERT -- learn it from the first build's
"flip-seed MISS" warn).

Why INBOARD, when the plate shows the foot running outboard from the ear:
the modelled rocker-arm-support is 177.8 long (z -88.9..+88.9) and the ears
sit at +-78 from the stack mid (3.83), so only 4.1 (north) / 11.7 (south)
of apex remains outboard of an ear -- a 24 foot cannot run that way. Inboard
it lies under the 1-2 outermost arms: foot top y 234.6 vs the arm bottoms
at 245.8 (11.2 air) and the O10 pivot bushings at 248.8.

Layout (part frame): seat face at y = 0; origin under the bore, on the
seat plane. Foot FOOT_W along X (x +-FOOT_W/2, inside the support's 16.933
apex with 0.47 margin each side) by FOOT_H tall by FOOT_Z0..FOOT_Z1 along Z
(the ear end at -EAR_T/2, the free end at +21); ear stub EAR_W wide (X) by
EAR_T thick (Z), centred on the origin, rising from the foot top to
STUB_TOP_Y; ball O BALL_DIA centred on the bore axis at (0, BORE_H, 0),
merged into the stub top (it overlaps the stub by BALL_CY - BALL_R ..
STUB_TOP_Y = 2.8); O BORE_DIA cross-bore along Z through the ball; two
hold-down holes through the foot on x = 0 at z = HOLE_Z. Ball faces (and
the bore inside it) painted POLISHED_STEEL over the PANEL_BLACK part.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pivot_bracket.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    PANEL_BLACK,
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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

PART_NAME = "pivot-bracket"
MATERIAL = "Plain Carbon Steel"  # black-finished steel (ch14 p.27)

FOOT_W = 16.0  # X, across the support apex (16.933 wide; 0.47 margin each side)
FOOT_H = 6.0
EAR_W = 14.0  # X
EAR_T = 6.0  # Z; the ear's Z band is the bore's (z -3..+3)
FOOT_Z0 = -EAR_T / 2.0  # foot starts at the ear's outer face ...
FOOT_Z1 = 21.0  # ... and runs 24 along +Z (inboard once placed)
FOOT_LEN = FOOT_Z1 - FOOT_Z0  # 24
STUB_TOP_Y = 20.0  # the ear stub the ball is merged into
BORE_H = 25.2  # shaft axis above the seat (unchanged: the rocker pivot stays
# at machine y 253.8 on the 228.6 support apex)
BALL_DIA = 16.0  # bright pivot ball on the ear (ch14 page002_img01)
BORE_DIA = 6.5  # O6.35 shaft, 0.15 diametral clearance
HOLE_DIA = 4.2  # #19-drill hold-down clearance
HOLE_Z = (9.0, 17.0)  # hold-down holes on x = 0, inside the foot's free run

BALL_R = BALL_DIA / 2.0
BALL_CY = BORE_H
BALL_BOTTOM_Y = BALL_CY - BALL_R  # 17.2 < STUB_TOP_Y: the ball bites the stub

if not (FOOT_H < BALL_BOTTOM_Y < STUB_TOP_Y < BALL_CY):
    raise AssertionError("ball must overlap the ear stub top, not the foot")
if not all(FOOT_Z0 + HOLE_DIA / 2.0 < z < FOOT_Z1 - HOLE_DIA / 2.0 for z in HOLE_Z):
    raise AssertionError("hold-down holes must lie within the foot")
if HOLE_Z[0] - HOLE_DIA / 2.0 < EAR_T / 2.0 + 0.5:
    raise AssertionError("first hold-down hole runs under the ear stub")


def _ball_stub_overlap() -> float:
    """Volume of the ball inside the stub box (|x| <= EAR_W/2, y <= STUB_TOP_Y,
    |z| <= EAR_T/2): the cap below y = STUB_TOP_Y, clipped by the two z faces
    (the cap's widest section, r 6.08 at the stub top, exceeds the 3 half-
    thickness but never the 7 half-width). Simpson over y of the disc/strip
    intersection area -- closed form per slice, numerical only across y."""
    hz = EAR_T / 2.0

    def area(y: float) -> float:
        r2 = BALL_R**2 - (y - BALL_CY) ** 2
        if r2 <= 0.0:
            return 0.0
        r = math.sqrt(r2)
        if r <= hz:
            return math.pi * r2
        # int_{-hz}^{hz} 2 sqrt(r^2 - z^2) dz (== pi r^2 at r = hz)
        return 2.0 * (hz * math.sqrt(r2 - hz * hz) + r2 * math.asin(hz / r))

    n = 2000
    y0, y1 = BALL_BOTTOM_Y, STUB_TOP_Y
    h = (y1 - y0) / n
    total = area(y0) + area(y1)
    for k in range(1, n):
        total += (4.0 if k % 2 else 2.0) * area(y0 + k * h)
    return total * h / 3.0


V_FOOT = FOOT_W * FOOT_H * FOOT_LEN
V_STUB = EAR_W * (STUB_TOP_Y - FOOT_H) * EAR_T
V_BALL = 4.0 / 3.0 * math.pi * BALL_R**3
V_OVERLAP = _ball_stub_overlap()  # ~129
# Coaxial O6.5 bore through the O16 ball only (the bore band y 21.95..28.45
# clears the stub top at 20): V = 4pi/3 (R^3 - (R^2 - a^2)^1.5).
V_BORE = (4.0 * math.pi / 3.0) * (BALL_R**3 - (BALL_R**2 - (BORE_DIA / 2.0) ** 2) ** 1.5)
V_HOLES = len(HOLE_Z) * math.pi * (HOLE_DIA / 2.0) ** 2 * FOOT_H
V_TOTAL = V_FOOT + V_STUB + V_BALL - V_OVERLAP - V_BORE - V_HOLES


def _com_get(obj, name: str):
    """Zero-argument COM member that late-bound dispatch may expose as a
    method or a value (the ``'tuple' object is not callable`` trap)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


async def _paint_ball_bright(adapter) -> None:
    """Face-level bright finish on the pivot ball over the black bracket:
    every face whose bounding box lies inside the ball's box AND has a real
    y extent (the stub's top-face annulus at y = STUB_TOP_Y also sits inside
    that box; being planar it has none, so it stays black). The bore face
    inside the ball is bright too -- a shaft seat. Fails loud if nothing
    matches."""
    from solidworks_mcp.adapters.com_variant import double_array

    bright = double_array([*POLISHED_STEEL, 1.0, 1.0, 0.5, 0.31, 0.0, 0.0])
    part_h = _early_bound(adapter.currentModel, "IPartDoc")
    n = 0
    y_lo = (BALL_BOTTOM_Y - 0.05) / 1000.0
    y_hi = (BALL_CY + BALL_R + 0.05) / 1000.0
    for body in part_h.GetBodies2(0, True) or []:
        for face in _com_get(body, "GetFaces") or []:
            box = _com_get(face, "GetBox")
            if not box:
                continue
            ymin, ymax = float(box[1]), float(box[4])
            xs = (float(box[3]) - float(box[0])) * 1000.0
            zs = (float(box[5]) - float(box[2])) * 1000.0
            inside = ymin >= y_lo and ymax <= y_hi and xs <= BALL_DIA + 0.1 and zs <= BALL_DIA + 0.1
            if inside and (ymax - ymin) * 1000.0 > 1.0:
                face.MaterialPropertyValues = bright
                n += 1
    if n < 2:
        raise RuntimeError(f"pivot ball faces not found ({n} matched)")
    _telemetry.info(f"pivot-bracket: {n} ball faces bright")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "FootW", f"{FOOT_W}mm")
    await set_global(adapter, "FootH", f"{FOOT_H}mm")
    await set_global(adapter, "FootLen", f"{FOOT_LEN}mm")
    await set_global(adapter, "FootZ1", f"{FOOT_Z1}mm")
    await set_global(adapter, "EarW", f"{EAR_W}mm")
    await set_global(adapter, "EarT", f"{EAR_T}mm")
    await set_global(adapter, "StubTopY", f"{STUB_TOP_Y}mm")
    await set_global(adapter, "BoreH", f"{BORE_H}mm")
    await set_global(adapter, "BallDia", f"{BALL_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Foot: Top-plane rectangle (sketch y = model -Z) x +-W/2, z FOOT_Z0..
    # FOOT_Z1, extruded +Y by FOOT_H. Emission: seg0 width, seg1 length, then
    # the (-W/2, -FOOT_Z1) corner anchor (x then z; the anchor z lands at the
    # magnitude FOOT_Z1 -- the magnifying-bracket Top-sketch idiom).
    half_w = FOOT_W / 2.0
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Top"))
    rect = [
        (-half_w, -FOOT_Z1),
        (half_w, -FOOT_Z1),
        (half_w, -FOOT_Z0),
        (-half_w, -FOOT_Z0),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="foot", dims=foot,
        names=["FootW", "FootLen", "FootAnchorX", "FootAnchorZ"],
        drives=['"FootW"', '"FootLen"', '"FootW" / 2', '"FootZ1"'],
    )
    await ensure_fully_defined(adapter, "foot sketch")
    check("exit_sketch foot", await adapter.exit_sketch())
    name_last_feature(adapter, "FootProfile")
    drive_jobs += foot.apply(adapter, "FootProfile")
    check(
        "extrude foot",
        await adapter.create_extrusion(ExtrusionParameters(depth=FOOT_H)),
    )
    name_last_feature(adapter, "Foot")
    drive_jobs.append(("D1@Foot", '"FootH"'))
    expected = V_FOOT
    await volume_check(adapter, "foot", expected, 0.005 * V_FOOT)

    # Ear stub: Front-plane rectangle x +-EAR_W/2, y FOOT_H..STUB_TOP_Y,
    # extruded both ways (EAR_T total) -- its Z band is the bore's. Emission:
    # seg0 width, seg1 rise, then the (-EAR_W/2, FOOT_H) corner anchor (x, z).
    half_e = EAR_W / 2.0
    ear = SketchDims()
    check("create_sketch ear", await adapter.create_sketch("Front"))
    ear_rect = [
        (-half_e, FOOT_H),
        (half_e, FOOT_H),
        (half_e, STUB_TOP_Y),
        (-half_e, STUB_TOP_Y),
    ]
    ear_lines = await add_line_chain(adapter, ear_rect)
    await define_rectilinear_chain(
        adapter, ear_lines, ear_rect, label="ear", dims=ear,
        names=["EarW", "EarRise", "EarAnchorX", "EarAnchorZ"],
        drives=['"EarW"', '"StubTopY" - "FootH"', '"EarW" / 2', '"FootH"'],
    )
    await ensure_fully_defined(adapter, "ear sketch")
    check("exit_sketch ear", await adapter.exit_sketch())
    name_last_feature(adapter, "EarProfile")
    drive_jobs += ear.apply(adapter, "EarProfile")
    check(
        "extrude ear",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=EAR_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Ear")
    expected += V_STUB
    await volume_check(adapter, "ear stub", expected, 0.005 * V_STUB)

    # Ball: revolved O16 sphere centred on the bore axis, MERGED into the
    # stub top (it bites 2.8 into the stub, so the boolean is a proper
    # intersection, not the tangent-sliver case the fulcrum keeper avoids).
    # Proven half-disc revolve idiom (fulcrum keeper / dome cap): Front-plane
    # profile in direct DB, so the on-axis centerline, the axis closure line
    # and the arc merge their endpoints by exact coordinates with no inference
    # relations; CCW arc from the bottom pole through +X to the top pole. The
    # centre anchor on the Y axis + the diameter dim size the arc; one
    # vertical_points per arc end pins the flat edge onto the revolve axis.
    ball = SketchDims()
    check("create_sketch ball", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "add_centerline ball axis",
        await adapter.add_centerline(0.0, BALL_BOTTOM_Y, 0.0, BALL_CY + BALL_R),
    )
    check(
        "add_line ball axis closure",
        await adapter.add_line(0.0, BALL_BOTTOM_Y, 0.0, BALL_CY + BALL_R),
    )
    arc = check(
        "add_arc ball",
        await adapter.add_arc(0.0, BALL_CY, 0.0, BALL_BOTTOM_Y, 0.0, BALL_CY + BALL_R),
    )
    set_sketch_direct_db(adapter, False)
    for end in ("start", "end"):
        check(
            f"ball arc {end} on the axis",
            await adapter.add_sketch_constraint(
                f"{arc}.{end}", f"{arc}.center", "vertical_points"
            ),
        )
    await anchor_point_to_origin(adapter, f"{arc}.center", 0.0, BALL_CY, "ball centre")
    ball.record("BallRise", '"BoreH"')
    check(
        "ball diameter",
        await adapter.add_sketch_dimension(arc, None, "diameter", BALL_DIA),
    )
    ball.record("BallDia", '"BallDia"')
    await ensure_fully_defined(adapter, "ball sketch")
    check("exit_sketch ball", await adapter.exit_sketch())
    name_last_feature(adapter, "BallProfile")
    drive_jobs += ball.apply(adapter, "BallProfile")
    check("revolve ball", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Ball")
    expected += V_BALL - V_OVERLAP
    await volume_check(adapter, "ball merged into the stub", expected, 0.01 * V_BALL)

    # Shaft cross-bore through the ball along Z at (0, BORE_H): on-axis in X,
    # so define_circle records the rise + diameter.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_H, BORE_DIA / 2.0, "shaft bore",
        dims=bore, names=("BoreCx", "BoreCz", "ShaftBoreDia"),
        drives=(None, '"BoreH"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftBoreProfile")
    drive_jobs += bore.apply(adapter, "ShaftBoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BALL_DIA + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")
    expected -= V_BORE
    await volume_check(adapter, "shaft bore", expected, 0.02 * V_BORE)

    # Hold-down holes through the foot: Top-plane circles on x = 0 (sketch y
    # = -z), cut both ways past the foot height. On-axis in X, so each
    # records only its z rise + diameter.
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Top"))
    for tag, z in zip("AB", HOLE_Z, strict=True):
        await define_circle(
            adapter, 0.0, -z, HOLE_DIA / 2.0, f"hole z{z:g}",
            dims=holes, names=(f"Hole{tag}x", f"Hole{tag}z", f"Hole{tag}Dia"),
            drives=(None, None, '"HoleDia"'),
        )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += holes.apply(adapter, "HoleProfile")
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * FOOT_H + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "HoldDownHoles")
    expected -= V_HOLES
    await volume_check(adapter, "hold-down holes", expected, 0.02 * V_HOLES)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bracket (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await _paint_ball_bright(adapter)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
