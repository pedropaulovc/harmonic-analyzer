r"""Bought feed handwheel: MISUMI HOK40-HC8 (MHA-CH-06-TL-VN-57).

The Ø40 knurled handwheel with its revolving grip, on the far end of the
oblique trammel jig's Tr8 leadscrew. It is one solid, built from
``ch_rocker_arm_tl_vn_oblique_handwheel_spec``, and the spec records each value's
source. The build:

- revolves the hub and rim round the Ø8 through bore (``WheelProfile`` ->
  ``Wheel``) and rounds the hub's end edge and its corner with the rim
  (``HubEndFillet``, ``HubCornerFillet``);
- revolves the grip about its own axis on the Front plane, fused to the rim
  face (``GripProfile`` -> ``Grip``), and rounds its end (``GripEndRound``);
- revolve-cuts the two radial M5 set-screw taps at the thread's minor
  diameter, from the hub OD into the bore (``SetScrewTap`` along -X, opposite
  the grip, which takes the supplied screw; ``SetScrewTapQuarter`` along +Z).
  The set screw is not modelled.

Vendor-checked against MISUMI's STEP ``HOK40-HC8.step`` (sha256 a9c2c04c...,
downloaded 2026-10-17 UTC).

Frame: the axis is +Y and is published as ``ScrewAxis`` (Front ∩ Right).
y = 0 is the hub end face, where the bore opens. The grip's axis is at
x = GRIP_OFFSET, z = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_handwheel.py
"""

from __future__ import annotations

import sys

import _config
from _appearance import PANEL_BLACK, apply_color, apply_material
from _bought_revolve import (
    SAVED_PROPERTIES,
    fillet_edge,
    publish_screw_axis,
    revolve_profile,
    stock_properties,
)
from _check import check
from _custom_properties import apply_custom_properties
from _drawing_marks import apply_drawing_properties
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from ch_rocker_arm_tl_vn_oblique_handwheel_spec import (
    DRAWING_NOTES,
    GRIP_DIA,
    GRIP_END_ROUND,
    GRIP_END_ROUND_MM3,
    GRIP_OFFSET,
    GRIP_PROFILE,
    GRIP_VOLUME_MM3,
    HUB_CORNER_FILLET_MM3,
    HUB_DIA,
    HUB_END_FILLET_MM3,
    HUB_FILLET,
    HUB_LENGTH,
    LENGTH,
    MATERIAL,
    SET_SCREW_DIRECTIONS,
    TAP_PROFILE,
    TAP_VOLUME_MM3,
    VOLUME_MM3,
    WHEEL_FACE_Y,
    WHEEL_PROFILE,
    WHEEL_VOLUME_MM3,
)

PART_NAME = "ch-rocker-arm-tl-vn-oblique-handwheel"
STOCK_PROPERTIES = stock_properties(_config.parts(PART_NAME))
# One set-screw tap per SET_SCREW_DIRECTIONS entry: (feature name, sketch
# plane). TAP_PROFILE runs along the sketch's -u: on Front, u = model x, so
# the tap points -X; on Right, u = -model z, so it points +Z. A centroid
# guard after each cut proves the direction.
TAPS: tuple[tuple[str, str], ...] = (
    ("SetScrewTap", "Front"),
    ("SetScrewTapQuarter", "Right"),
)


def wheel_points() -> list[tuple[float, float]]:
    """``WHEEL_PROFILE`` as Front-plane sketch points: x = radius, y = station."""
    return list(WHEEL_PROFILE)


def grip_points() -> list[tuple[float, float]]:
    """``GRIP_PROFILE`` on the Front plane about the grip axis x = GRIP_OFFSET."""
    return [(GRIP_OFFSET + r, y) for r, y in GRIP_PROFILE]


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Hub and rim round the through bore; the bore's centerline is free.
    await revolve_profile(
        adapter,
        "Front",
        "hub and rim",
        wheel_points(),
        ("WheelProfile", "Wheel"),
        free_axis_length=WHEEL_FACE_Y,
    )
    expected = WHEEL_VOLUME_MM3
    await volume_check(adapter, "hub and rim", expected, 0.002 * expected)
    hub_r = HUB_DIA / 2.0
    await fillet_edge(
        adapter, "hub end edge", HUB_FILLET, (0.0, 0.0, -hub_r), "HubEndFillet"
    )
    expected -= HUB_END_FILLET_MM3
    await volume_check(adapter, "hub end fillet", expected, 0.1 * HUB_END_FILLET_MM3)
    await fillet_edge(
        adapter,
        "hub-to-rim corner",
        HUB_FILLET,
        (0.0, HUB_LENGTH, -hub_r),
        "HubCornerFillet",
    )
    expected += HUB_CORNER_FILLET_MM3
    await volume_check(
        adapter, "hub corner fillet", expected, 0.1 * HUB_CORNER_FILLET_MM3
    )

    # The grip, on its own axis, fused to the rim face.
    await revolve_profile(
        adapter, "Front", "grip", grip_points(), ("GripProfile", "Grip")
    )
    expected += GRIP_VOLUME_MM3
    await volume_check(
        adapter, "grip fused to the rim face", expected, 0.002 * expected
    )
    await fillet_edge(
        adapter,
        "grip end",
        GRIP_END_ROUND,
        (GRIP_OFFSET, LENGTH, -GRIP_DIA / 2.0),
        "GripEndRound",
    )
    expected -= GRIP_END_ROUND_MM3
    await volume_check(adapter, "grip end round", expected, 0.1 * GRIP_END_ROUND_MM3)

    # The two M5 set-screw taps at the minor diameter (M5 has no pinned tap
    # drill): each a rectangle revolved about its own axis, from the wheel
    # axis out past the hub OD, so it opens one wall into the empty bore.
    for (name, plane), (dx, dz) in zip(TAPS, SET_SCREW_DIRECTIONS, strict=True):
        before = check(f"mass before {name}", await adapter.get_mass_properties())
        await revolve_profile(
            adapter,
            plane,
            name,
            list(TAP_PROFILE),
            (f"{name}Profile", name),
            is_cut=True,
        )
        expected -= TAP_VOLUME_MM3
        await volume_check(adapter, name, expected, 0.03 * TAP_VOLUME_MM3)
        after = check(f"mass after {name}", await adapter.get_mass_properties())
        # Cutting toward (dx, dz) moves the centroid the other way.
        shift = [
            a - b
            for a, b in zip(after.center_of_mass, before.center_of_mass, strict=True)
        ]
        if not dx * shift[0] + dz * shift[2] < 0.0:
            raise RuntimeError(
                f"{name}: tap not cut toward (x, z) = {(dx, dz)}; centroid moved {shift}"
            )
    await volume_check(adapter, "handwheel", VOLUME_MM3, 0.002 * VOLUME_MM3)

    await publish_screw_axis(adapter)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)  # black anodise
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, SAVED_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
