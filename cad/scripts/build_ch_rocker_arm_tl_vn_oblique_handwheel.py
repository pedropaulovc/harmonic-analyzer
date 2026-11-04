r"""Bought feed handwheel: HARFINGTON 50 mm, Amazon B0DJ3DZT86 (MHA-CH-06-TL-VN-57).

The Ø50 knurled handwheel with its rotating handle, on the far end of the
oblique trammel jig's Tr8 leadscrew. It is one solid, built from
``ch_rocker_arm_tl_vn_oblique_handwheel_spec``, and the spec records each value's
source (several are UNVERIFIED envelope values). The build:

- revolves the hub and rim round the blind Ø8 bore, about the axis edge
  behind the bore's bottom (``WheelProfile`` -> ``Wheel``); no edge breaks
  are modelled (none is published);
- revolves the handle's envelope cylinder about its own axis on the Front
  plane, fused to the rim face (``GripProfile`` -> ``Grip``);
- revolve-cuts the two radial M5 set-screw taps at the thread's minor
  diameter, from the hub OD into the bore (``SetScrewTap`` along -X, opposite
  the handle, the one on the leadscrew's flat; ``SetScrewTapQuarter`` along
  +Z). The set screws are not modelled.

Datasheet-built: no vendor CAD obtained.

Frame: the axis is +Y and is published as ``ScrewAxis`` (Front ∩ Right).
y = 0 is the hub end face, where the bore opens. The handle's axis is at
x = GRIP_OFFSET, z = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_handwheel.py
"""

from __future__ import annotations

import sys

import _config
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bought_revolve import (
    SAVED_PROPERTIES,
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
    GRIP_OFFSET,
    GRIP_PROFILE,
    GRIP_VOLUME_MM3,
    MATERIAL,
    SET_SCREW_DIRECTIONS,
    TAP_PROFILE,
    TAP_VOLUME_MM3,
    VOLUME_MM3,
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
    """``GRIP_PROFILE`` on the Front plane about the handle axis x = GRIP_OFFSET."""
    return [(GRIP_OFFSET + r, y) for r, y in GRIP_PROFILE]


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Hub and rim round the blind bore; the closing edge on the axis is the
    # revolve's centerline.
    await revolve_profile(
        adapter, "Front", "hub and rim", wheel_points(), ("WheelProfile", "Wheel")
    )
    expected = WHEEL_VOLUME_MM3
    await volume_check(adapter, "hub and rim", expected, 0.002 * expected)

    # The handle's envelope, on its own axis, fused to the rim face.
    await revolve_profile(
        adapter, "Front", "handle", grip_points(), ("GripProfile", "Grip")
    )
    expected += GRIP_VOLUME_MM3
    await volume_check(
        adapter, "handle fused to the rim face", expected, 0.002 * expected
    )

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
    await apply_color(adapter, POLISHED_STEEL)  # the listing photos' silver anodize
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, SAVED_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
