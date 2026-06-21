r"""Channel-spring geometry: the shared helical extension-spring builder.

One helper for both the installed channel spring (``build_channel_spring_installed``)
and the per-channel stretched variants the channel assembly mass-produces
(``build_channel_assembly``). Holds the wire/coil geometry scaled from the book
ch. 17 p. 41 inset and :func:`build_spring`, which sweeps a wire circle along a
helix of a caller-given body length and adds the bent-wire end hooks
(``_features.add_spring_end_hooks``).

The FREE (relaxed) body length and its provenance are the single dimension
callout in ch. 17 (the p. 41 inset). They live in the part registry
(``cad/config/parts/channel-spring-installed.yaml`` -> ``free_length_mm``): the
standalone free-spring part (was ``build_channel_spring.py`` / ``channel-spring``,
MHA-010) was display-only and is no longer built, so its relaxed length is kept
there as the source of truth and read back here.

Layout: coil axis along +Y from the origin (helix base circle on the Top plane);
the helix starts and ends on the +X side (whole number of coils). Hook eye
centres land at ``y = -bottom_lead`` and ``y = body + top_lead``.
"""

from __future__ import annotations

from typing import Iterable

import _config
from _common import (
    SPRING_BLACK,
    apply_color,
    apply_material,
    blank_sketch,
    check,
    define_circle,
    ensure_fully_defined,
    name_bore_axis,
    report_mass_properties,
    save_part_and_images,
)
from _features import (
    add_spring_end_hooks,
    insert_helix,
)

MATERIAL = "Alloy Steel"  # see _common.apply_material docstring

# Relaxed body length: registry is the source of truth (see module docstring).
COIL_BODY_LENGTH = float(_config.parts("channel-spring-installed")["free_length_mm"])
COIL_OD = 6.5  # DIMENSIONS.md ch17: scaled from p.41 inset (low)
WIRE_DIA = 1.0  # DIMENSIONS.md ch17: scaled from p.41 inset (low)
COIL_COUNT = 28  # close-wound: body length / ~1.14 mm pitch (derived, low)

MEAN_RADIUS = (COIL_OD - WIRE_DIA) / 2.0
HOOK_LEAD = 2.0 * WIRE_DIA  # _features.add_spring_end_hooks default
EYE_C2C = COIL_BODY_LENGTH + 2.0 * HOOK_LEAD  # hook eye centres, 36.0 free


async def build_spring(
    adapter,
    part_name: str,
    body_length: float,
    leads: tuple[float, float] | None = None,
    eye_axes: bool = False,
    views: Iterable[str] | None = None,
) -> dict[str, str]:
    """Build a channel spring with the given coil body length (mm).

    ``leads`` = (bottom, top) hook lead lengths; None = 2 x wire both ends.

    ``eye_axes`` adds two named reference axes so the spring can be MATED at
    both ends (vs. the legacy grounded-by-transform placement). They are
    plane-intersection axes (view-independent, the ``name_bore_axis`` pattern),
    derived from the same geometry the hooks are built from:

      * bottom lead axis -- the straight bottom lead is a wire cylinder at
        ``x = mean_radius`` running along the coil axis (+Y), ``z = 0``. It
        threads the summing-lever plate hole, so its axis = ``Right Plane`` +
        mean_radius (x = mean_radius) intersect ``Front Plane`` (z = 0).
      * top eye axis -- the top loop's centre is at ``x = 0`` (mean_radius -
        loop_r, and loop_r = mean_radius), ``y = body + top_lead``, with the
        loop drawn in the Front plane so its axis is along Z. It hooks the
        lever tab pin, so its axis = ``Right Plane`` (x = 0) intersect
        ``Top Plane`` + (body + top_lead).

    Off by default: the existing parts stay byte-identical until the summation
    reorg adopts mated springs.
    """
    from solidworks_mcp.adapters.base import SweepParameters

    pitch = body_length / COIL_COUNT  # whole coils: both ends land at +X

    check("create_part", await adapter.create_part())

    # Helix path from a base circle on the Top plane (consumed while open).
    check("create_sketch helix base", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, MEAN_RADIUS, "helix base")
    await ensure_fully_defined(adapter, "helix base sketch")
    helix_name = insert_helix(adapter, body_length, pitch)

    # Wire cross-section at the helix start point (+X side).
    check("create_sketch wire profile", await adapter.create_sketch("Front"))
    await define_circle(adapter, MEAN_RADIUS, 0.0, WIRE_DIA / 2.0, "wire profile")
    await ensure_fully_defined(adapter, "wire profile sketch")
    check("exit_sketch wire profile", await adapter.exit_sketch())

    check(
        "sweep wire along helix",
        await adapter.create_sweep(SweepParameters(path=helix_name)),
    )

    await add_spring_end_hooks(adapter, MEAN_RADIUS, WIRE_DIA, body_length, leads=leads)

    eye_axis_names: dict[str, str] = {}
    if eye_axes:
        top_lead = leads[1] if leads is not None else HOOK_LEAD
        eye_axis_names["bottom_lead_axis"] = await name_bore_axis(
            adapter, "Right Plane", MEAN_RADIUS, "Front Plane", 0.0,
            "bottom-lead axis (threads the plate hole)")
        eye_axis_names["top_eye_axis"] = await name_bore_axis(
            adapter, "Right Plane", 0.0, "Top Plane", body_length + top_lead,
            "top-eye axis (hooks the lever tab)")

    # The helix base sketch stays unabsorbed-and-shown after InsertHelix;
    # shown sketches render in every assembly instance (20 floating seed
    # circles above the top frame in the ch30 views).
    blank_sketch(adapter, "Sketch1")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, SPRING_BLACK)  # ch30 plates: see _common palette
    await report_mass_properties(adapter)
    # ``views=[]`` saves the part with no PNG exports -- used when build_channel_
    # assembly mass-produces the per-channel stretched variants (the slow
    # image step would dominate; the canonical part still renders its views).
    if views is None:
        result = await save_part_and_images(adapter, part_name)
    else:
        result = await save_part_and_images(adapter, part_name, views)
    # The two eye axes are baked into the .SLDPRT by the names captured above, so
    # the summation assembly can mate both ends without re-deriving them.
    return {**result, **eye_axis_names}
