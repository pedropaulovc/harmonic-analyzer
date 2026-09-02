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

from _common import (
    POLISHED_STEEL,
    SketchDims,
    _feature_by_name,
    apply_color,
    apply_material,
    blank_sketch,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    save_part_and_images,
    set_global,
    volume_check,
)
from _features import (
    add_spring_end_hooks,
    insert_helix,
)
from channel_spring_installed_spec import (
    COIL_COUNT,
    COIL_OD,
    FREE_BODY_LENGTH as COIL_BODY_LENGTH,
    WIRE_DIA,
)

MATERIAL = "Alloy Steel"  # see _common.apply_material docstring

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

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    # CoilBodyLength + Pitch feed InsertHelix (FEATURE params, not sketch dims),
    # declared but never driven (like an extrude depth). MeanRadius is derived and
    # drives the helix base diameter and the wire-profile centre.
    await set_global(adapter, "CoilOD", f"{COIL_OD}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    await set_global(adapter, "MeanRadius", '("CoilOD" - "WireDia") / 2')
    await set_global(adapter, "CoilBodyLength", f"{body_length}mm")
    await set_global(adapter, "Pitch", f"{pitch}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Helix path from a base circle on the Top plane. The sketch is consumed by
    # InsertHelix (no exit_sketch), so rename it by-name before that consumes it.
    base_dims = SketchDims()
    check("create_sketch helix base", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, MEAN_RADIUS, "helix base", dims=base_dims,
        names=("BaseCx", "BaseCz", "MeanDia"),
        drives=(None, None, '2 * "MeanRadius"'),
    )
    await ensure_fully_defined(adapter, "helix base sketch")
    _feature_by_name(adapter, "Sketch1").Name = "HelixBaseProfile"
    drive_jobs += base_dims.apply(adapter, "HelixBaseProfile")
    helix_name = insert_helix(adapter, body_length, pitch)

    # Wire cross-section at the helix start point (+X side): centre-X (x != 0)
    # then diameter; centre-Z slot None (y == 0).
    wire_dims = SketchDims()
    check("create_sketch wire profile", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, MEAN_RADIUS, 0.0, WIRE_DIA / 2.0, "wire profile", dims=wire_dims,
        names=("WireCx", "WireCz", "WireDiaDim"),
        drives=('"MeanRadius"', None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire profile sketch")
    check("exit_sketch wire profile", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += wire_dims.apply(adapter, "WireProfile")

    check(
        "sweep wire along helix",
        await adapter.create_sweep(SweepParameters(path=helix_name)),
    )
    name_last_feature(adapter, "CoilBody")

    await add_spring_end_hooks(adapter, MEAN_RADIUS, WIRE_DIA, body_length, leads=leads)

    eye_axis_names: dict[str, str] = {}
    if eye_axes:
        top_lead = leads[1] if leads is not None else HOOK_LEAD
        # Two reference axes along LOCAL X (the spring's through-thickness), each
        # the Top-plane <-> Front-plane intersection at a different height. The
        # summation assembly inserts the spring ROT_Y(+90).Rz(theta), so local X
        # ALWAYS images to world Z -- the rotation's first row is [0,0,-1] for
        # EVERY tilt (theta), independent of the amplitude preset. So these axes
        # are world-Z-parallel no matter how the spring tilts, and the assembly
        # pins the (possibly tilted) spring's position + yaw by their in-plane
        # X/Y distances to the datum planes (the spin_driver idiom), instead of
        # forcing it vertical with plane-parallel mates (the neutral-only locate).
        # Axis1 = low (origin height), Axis2 = high (top-eye height): the long
        # lever arm between them gives a well-conditioned yaw pin.
        eye_axis_names["mate_axis_low"] = await name_bore_axis(
            adapter, "Top Plane", 0.0, "Front Plane", 0.0,
            "low mate axis (X-parallel, origin height)")
        eye_axis_names["mate_axis_high"] = await name_bore_axis(
            adapter, "Top Plane", body_length + top_lead, "Front Plane", 0.0,
            "high mate axis (X-parallel, top-eye height)")

    # The helix base sketch stays unabsorbed-and-shown after InsertHelix;
    # shown sketches render in every assembly instance (20 floating seed
    # circles above the top frame in the ch30 views). Renamed above, so blank
    # it by the new name.
    blank_sketch(adapter, "HelixBaseProfile")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    _m = await adapter.get_mass_properties()
    if not _m.is_success:
        raise RuntimeError(f"as-built mass props failed: {_m.error}")
    v_built = float(_m.data.volume)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven spring (equations neutral)", v_built, 5e-3 * v_built)

    await apply_material(adapter, MATERIAL)
    # ch17 pp.40-41 + p.41 inset: the channel springs are BRIGHT steel wire
    # (every coil reads silver against the black levers); only the counter
    # spring (build_counter_spring) is black.
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    # ``views=[]`` saves the part with no PNG exports -- used when build_channel_
    # assembly mass-produces the per-channel stretched variants (the slow
    # image step would dominate; the canonical part still renders its views).
    if views is None:
        result = await save_part_and_images(adapter, part_name)
    else:
        result = await save_part_and_images(adapter, part_name, views)
    # The two mate axes are baked into the .SLDPRT (Axis1 low, Axis2 high), so the
    # summation assembly pins each spring's tilt by their world-Z-parallel
    # in-plane distances without re-deriving any geometry.
    return {**result, **eye_axis_names}
