r"""Reproduction script: gooseneck post (book ch. 19, pp. 44-45).

The tall chrome tube that "towers above the machine" and anchors the top
of the counter spring: a vertical O16 tube rising from the east column
line, a 90-DEGREE bend (R 51) at the top, and a horizontal arm reaching
west over the summing-lever boss, carrying the spring pin under its end.
(M6.8 ch30 8-view pass: 90 degrees, not the earlier 180 candy-cane --
user-confirmed against the ch. 19 photos; the ch30 plates crop below the
bend.) Tension is set by sliding the tube in its clamp
(build_gooseneck_clamp.py).

Geometry: vertical leg at machine x 197 (east column line), y 1041
(seats in the clamp bore just above the east rail top 1040.7) up to the
bend start 1335; quarter bend to the horizontal arm at centreline
y 1386, running west to its end face at machine x 85; the spring lug
hangs under the arm end so the pin stays at machine (95, 1373) --
directly above the summing-lever boss hook, counter spring hanging
plumb, loop top 1376.9 clearing the arm underside 1378. The book's tip
"slotted screw" is modeled as a lug + O4 X-pin for the spring's top
loop to encircle (simplification).

Layout: part origin at the vertical leg's MID-height of the OLD 180 lay
(machine (197, 1210, 0), placement preserved): leg y -169..+125, bend
arc centre (-51, +125), arm centreline y +176 from x -51 to -112, lug
x -109..-103.5 rising y 159..172 into the arm underside (min 168), pin
along X at (y 163, z 0). Dimensions: cad/DIMENSIONS.md ch. 19 (low/med).

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
LEG_TOP = 125.0  # bend start = machine 1335 (derived: arm y - bend R)
LEG_BOTTOM = -169.0  # leg bottom = machine 1041: stops 0.3 above the east
# rail top (1040.7) -- the tube seats in the clamp bore, not in the rail
BEND_R = 51.0  # 90-degree bend (med)
ARM_Y = LEG_TOP + BEND_R  # 176: arm centreline = machine 1386; underside
# 168 = machine 1378, 1.1 above the spring loop top 1376.9
ARM_END_X = -112.0  # arm end face = machine 85: covers the lug with margin
ARM_RUN = -ARM_END_X - BEND_R  # 61: straight run after the bend exit
LUG_X = (-109.0, -103.5)  # lug plate, machine x 88..93.5 (derived: clear
# of the spring loop's wire band x 94.1..95.9)
LUG_Y = (159.0, 172.0)  # rises 4 past the arm underside so the prism
# merges into the round tube (the old design met the down-tip's FLAT end
# face, where exact touch unions; a curved face needs real overlap)
LUG_HALF_Z = 1.5
PIN_DIA = 4.0  # spring-loop pin (low)
PIN_Y = 163.0  # machine 1373: loop centre 1370.6 + (loop mean r 5.35
# - wire r 0.9 - pin r 2.0) hanging contact (derived)
PIN_X = (-109.0, -98.0)  # cantilevers past the loop band to machine x 99

TUBE_R = TUBE_DIA / 2.0


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateEquationCurveParameters,
        CreatePlaneParameters,
        RevolveParameters,
        SweepParameters,
    )

    def fmt(value_mm: float) -> str:
        return f"{value_mm / IN:.12g}"  # document units are inches

    check("create_part", await adapter.create_part())

    # 1. Vertical leg (start-offset extrude from the Top plane: the leg is
    # asymmetric -- bottom at LEG_BOTTOM, top at +LEG_TOP into the bend).
    check("create_sketch leg", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, TUBE_R, "leg")
    await ensure_fully_defined(adapter, "leg sketch")
    check("exit_sketch leg", await adapter.exit_sketch())
    extrude_at_offset(adapter, LEG_TOP - LEG_BOTTOM, LEG_BOTTOM)
    expected = math.pi * TUBE_R**2 * (LEG_TOP - LEG_BOTTOM)
    vol = await _volume(adapter)
    print(f"  volume after leg: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"leg volume {vol:.1f} != {expected:.1f}")

    # 2. Quarter bend + horizontal arm: ONE sweep along two equation
    # curves (no direction ambiguity, no free endpoints).
    path_name = check("create_sketch bend path", await adapter.create_sketch("Front"))
    arc = await check_curve(
        adapter,
        CreateEquationCurveParameters(
            x_expression=(
                f"{fmt(-BEND_R)} + {fmt(BEND_R)} * cos({math.pi / 2.0:.12g} * t)"
            ),
            y_expression=(
                f"{fmt(LEG_TOP)} + {fmt(BEND_R)} * sin({math.pi / 2.0:.12g} * t)"
            ),
            range_start="0",
            range_end="1",
        ),
        "bend arc",
    )
    arm = await check_curve(
        adapter,
        CreateEquationCurveParameters(
            x_expression=f"{fmt(-BEND_R)} - {fmt(ARM_RUN)} * t",
            y_expression=f"{fmt(ARM_Y)} + 0 * t",
            range_start="0",
            range_end="1",
        ),
        "arm run",
    )
    await ensure_fully_defined(adapter, "bend path", fix_entities=[arc, arm])
    check("exit_sketch bend path", await adapter.exit_sketch())

    profile_plane = check(
        "create_plane bend profile",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=LEG_TOP)
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
                    mode="offset", base_plane="Top Plane", offset=LEG_TOP, flip=True
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
    check("sweep bend + arm", res)
    v_bend = math.pi**2 * TUBE_R**2 * BEND_R / 2.0  # quarter torus
    v_arm = math.pi * TUBE_R**2 * ARM_RUN
    expected = expected + v_bend + v_arm
    vol = await _volume(adapter)
    print(f"  volume after bend + arm: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"bend volume {vol:.1f} != {expected:.1f}")
    expected = vol  # rebase: keep the sweep's B-rep slack out of the lug delta

    # 3. Pin lug rising into the arm underside.
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
    # Added material = the prism OUTSIDE the tube: height to the tube
    # underside (~168 + z^2/16 over z +-1.5) ~ 9.05 mean, vs the 9-high
    # solid reference -> ratio 1.005, inside the (0.95, 1.01) window.
    v_lug = (LUG_X[1] - LUG_X[0]) * 2.0 * LUG_HALF_Z * 9.0
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after lug: {vol:.1f} mm^3 (+{added:.1f}, solid {v_lug:.1f})")
    if not (0.95 * v_lug <= added <= 1.01 * v_lug):
        raise RuntimeError(f"lug: added {added:.1f}, expected ~{v_lug:.1f}")
    expected = vol

    # 4. Spring pin along X (revolved in the Front plane -- no Right-plane
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
