r"""Reproduction script: gooseneck post (book ch. 19, pp. 44-45).

The tall chrome tube that "towers above the machine" and anchors the top
of the counter spring: a vertical O16 tube rising from the east column
line, a 180-degree bend (R 51) at the top, and a short down-pointing tip
carrying the spring pin. Tension is set by sliding the tube in its clamp
(build_gooseneck_clamp.py).

M6.4 geometry (ch. 19 full-machine photo at gooseneck scale 0.515 px/mm,
p3 90-degree page): vertical leg at machine x 197 (east column line),
y 1030..1390; bend top ~y 1441; tip leg at machine x 95 -- directly above
the summing-lever boss hook so the counter spring hangs plumb -- ending
at y 1378. The book's tip "slotted screw" is modeled as a lug + O4 X-pin
under the tip for the spring's top loop to encircle (simplification).

Layout: part origin at the vertical leg's MID-height (machine
(197, 1210, 0)): leg y +-180, bend arc centre (-51, +180), tip leg at
x -102 (y 168..180), lug x -109..-103.5 (y 159..168), pin along X at
(y 163, z 0). Dimensions: cad/DIMENSIONS.md ch. 19 (low/med).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_gooseneck.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "gooseneck"
MATERIAL = "Chrome Stainless Steel"  # polished chrome tube

TUBE_DIA = 16.0  # DIMENSIONS.md ch19: scaled vs frame anchors (med)
LEG_HALF = 180.0  # vertical leg y +-180 = machine 1030..1390 (med)
BEND_R = 51.0  # 180-degree bend; tip lands at x -102 = machine 95 (derived:
# the tip must sit plumb above the boss hook at machine x 95)
TIP_TOP = 180.0  # tip leg top (bend exit)
TIP_BOT = 168.0  # tip end face = machine 1378 (low)
LUG_X = (-109.0, -103.5)  # lug plate, machine x 88..93.5 (derived: clear
# of the spring loop's wire band x 94.1..95.9)
LUG_Y = (159.0, 168.0)
LUG_HALF_Z = 1.5
PIN_DIA = 4.0  # spring-loop pin (low)
PIN_Y = 163.0  # machine 1373: loop centre 1370.6 + (loop mean r 5.35
# - wire r 0.9 - pin r 2.0) hanging contact (derived)
PIN_X = (-109.0, -98.0)  # cantilevers past the loop band to machine x 99

TUBE_R = TUBE_DIA / 2.0
TIP_X = -2.0 * BEND_R


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateEquationCurveParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
        SweepParameters,
    )

    def fmt(value_mm: float) -> str:
        return f"{value_mm / IN:.12g}"  # document units are inches

    check("create_part", await adapter.create_part())

    # 1. Vertical leg (mid-plane extrude from the Top plane).
    check("create_sketch leg", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, TUBE_R, "leg")
    await ensure_fully_defined(adapter, "leg sketch")
    check("exit_sketch leg", await adapter.exit_sketch())
    check(
        "extrude leg",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * LEG_HALF, both_directions=True)
        ),
    )
    expected = math.pi * TUBE_R**2 * 2.0 * LEG_HALF
    vol = await _volume(adapter)
    print(f"  volume after leg: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"leg volume {vol:.1f} != {expected:.1f}")

    # 2. 180-degree bend: sweep along an explicit half-circle path (an
    # equation curve has no direction ambiguity and no free endpoints).
    path_name = check("create_sketch bend path", await adapter.create_sketch("Front"))
    arc = await check_curve(
        adapter,
        CreateEquationCurveParameters(
            x_expression=(
                f"{fmt(-BEND_R)} + {fmt(BEND_R)} * cos({math.pi:.12g} * t)"
            ),
            y_expression=(
                f"{fmt(LEG_HALF)} + {fmt(BEND_R)} * sin({math.pi:.12g} * t)"
            ),
            range_start="0",
            range_end="1",
        ),
        "bend arc",
    )
    await ensure_fully_defined(adapter, "bend path", fix_entities=[arc])
    check("exit_sketch bend path", await adapter.exit_sketch())

    profile_plane = check(
        "create_plane bend profile",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=LEG_HALF)
        ),
    )
    check(
        "create_sketch bend profile",
        await adapter.create_sketch(getattr(profile_plane, "name", profile_plane)),
    )
    await define_circle(adapter, 0.0, 0.0, TUBE_R, "bend profile")
    await ensure_fully_defined(adapter, "bend profile sketch")
    check("exit_sketch bend profile", await adapter.exit_sketch())
    res = await adapter.create_sweep(SweepParameters(path=path_name))
    if not res.is_success:
        print(f"  ..  bend sweep failed ({res.error}); flipping profile plane")
        profile_plane = check(
            "create_plane bend profile (flipped)",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Top Plane", offset=LEG_HALF, flip=True
                )
            ),
        )
        check(
            "create_sketch bend profile (flipped)",
            await adapter.create_sketch(getattr(profile_plane, "name", profile_plane)),
        )
        await define_circle(adapter, 0.0, 0.0, TUBE_R, "bend profile (flipped)")
        await ensure_fully_defined(adapter, "bend profile sketch (flipped)")
        check("exit_sketch bend profile (flipped)", await adapter.exit_sketch())
        res = await adapter.create_sweep(SweepParameters(path=path_name))
    check("sweep bend", res)
    v_bend = math.pi**2 * TUBE_R**2 * BEND_R  # half torus
    before, expected = expected, expected + v_bend
    vol = await _volume(adapter)
    print(f"  volume after bend: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"bend volume {vol:.1f} != {expected:.1f}")

    # 3. Tip leg (down tube), Top-plane sketch extruded at a start offset.
    check("create_sketch tip", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, TIP_X, 0.0, TUBE_R, "tip")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "tip sketch")
    check("exit_sketch tip", await adapter.exit_sketch())
    extrude_at_offset(adapter, TIP_TOP - TIP_BOT, TIP_BOT)
    expected += math.pi * TUBE_R**2 * (TIP_TOP - TIP_BOT)
    vol = await _volume(adapter)
    print(f"  volume after tip: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"tip volume {vol:.1f} != {expected:.1f}")

    # 4. Pin lug under the tip end face.
    check("create_sketch lug", await adapter.create_sketch("Top"))
    lug = await add_line_chain(
        adapter,
        [
            (LUG_X[0], -LUG_HALF_Z),
            (LUG_X[1], -LUG_HALF_Z),
            (LUG_X[1], LUG_HALF_Z),
            (LUG_X[0], LUG_HALF_Z),
        ],
    )
    await ensure_fully_defined(adapter, "lug sketch", fix_entities=lug)
    check("exit_sketch lug", await adapter.exit_sketch())
    extrude_at_offset(adapter, LUG_Y[1] - LUG_Y[0], LUG_Y[0])
    v_lug = (LUG_X[1] - LUG_X[0]) * 2.0 * LUG_HALF_Z * (LUG_Y[1] - LUG_Y[0])
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after lug: {vol:.1f} mm^3 (+{added:.1f}, solid {v_lug:.1f})")
    if not (0.95 * v_lug <= added <= 1.01 * v_lug):
        raise RuntimeError(f"lug: added {added:.1f}, expected ~{v_lug:.1f}")
    expected = vol

    # 5. Spring pin along X (revolved in the Front plane -- no Right-plane
    # axis-mapping ambiguity).
    check("create_sketch pin", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "pin centerline",
        await adapter.add_centerline(PIN_X[0], PIN_Y, PIN_X[1], PIN_Y),
    )
    profile = await add_line_chain(
        adapter,
        [
            (PIN_X[0], PIN_Y),
            (PIN_X[1], PIN_Y),
            (PIN_X[1], PIN_Y + PIN_DIA / 2.0),
            (PIN_X[0], PIN_Y + PIN_DIA / 2.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "pin sketch", fix_entities=[centerline, *profile]
    )
    check("exit_sketch pin", await adapter.exit_sketch())
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    pin_len = PIN_X[1] - PIN_X[0]
    v_pin = math.pi * (PIN_DIA / 2.0) ** 2 * pin_len
    # The pin passes through the lug: subtract the lens-clipped overlap.
    r, h = PIN_DIA / 2.0, LUG_HALF_Z
    a_clip = 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))
    v_overlap = a_clip * (LUG_X[1] - LUG_X[0])
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    v_net = v_pin - v_overlap
    print(f"  volume after pin: {vol:.1f} mm^3 (+{added:.1f}, net {v_net:.1f})")
    if not (0.9 * v_net <= added <= 1.1 * v_net):
        raise RuntimeError(f"pin: added {added:.1f}, expected ~{v_net:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


async def check_curve(adapter, params, label: str) -> str:
    res = await adapter.create_equation_driven_curve(params)
    return check(f"curve {label}", res)


if __name__ == "__main__":
    sys.exit(run_build(build))
