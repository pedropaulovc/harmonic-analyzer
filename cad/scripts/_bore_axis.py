"""Named bore-axis creation.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from typing import Any

from _check import check

# ---------------------------------------------------------------------------
# Mate family: semantic kinematic joints + driving dimensions.
#
# Generalised from build_fr_frame_assembly's plane-plane mate. Every component is
# inserted at its exact final (mirrored) transform, so a correctly solved mate
# must NOT move it. distance / angle / coincident (and alignment-sensitive
# concentric) mates can pick the far-side solution; pass ``verify=(comp_name,
# origin_mm)`` and the helper reads back ``Transform2`` and re-adds the mate
# flipped when the origin drifts past tolerance -- the same readback-and-flip
# recovery the frame used inline, now shared.
#
# A ``distance``/``angle`` mate IS a driving dimension: ``distance_driver`` /
# ``angle_driver`` are those mates used to pin a residual DOF to a coefficient
# value (the 21 machine inputs + computed-equilibrium snapshot dims).
# ---------------------------------------------------------------------------
_MATE_TOL_MM = 0.5


async def name_bore_axis(
    adapter: Any,
    plane_a: str,
    offset_a: float,
    plane_b: str,
    offset_b: float,
    label: str,
    drive_a: str | None = None,
    drive_b: str | None = None,
    drive_jobs: list[tuple[str, str]] | None = None,
) -> str:
    """Create a named reference axis through a bore, view-independently.

    The axis is the intersection of two planes, each either a principal plane
    (``offset`` 0, used by name) or a plane offset from one. Coordinate
    face/edge selection is view-dependent (``SelectByID2`` picks at the screen
    projection), so an internal/occluded bore wall never selects by point; a
    name-selected axis does. Assembly mates then pick the axis as
    ``named_ref("Axis<N>@<comp>", "AXIS")``.

    ``drive_a``/``drive_b`` optionally tie each offset plane's distance to an
    equation (e.g. ``'"BarDepth" / 2'``) so the axis -- and any assembly mate to
    it -- TRACKS a GUI edit of those globals instead of staying frozen at the
    as-built offset. When given, the created plane's distance dim (``D1@<plane>``)
    is appended to ``drive_jobs`` for the caller's deferred drive batch (same
    convention as ``_cut_tick``); each equation must evaluate to the as-built
    offset so the placement stays neutral. A drive on a principal-plane (offset
    0) side has no dim to drive and is ignored.

    Returns the new axis's resolved name (e.g. ``"Axis1"``).
    """
    from _visibility import blank_reference_geometry
    from solidworks_mcp.adapters.base import (
        CreateAxisParameters,
        CreatePlaneParameters,
    )

    planes: list[str] = []
    created: list[tuple[str, str]] = []
    for base, off, tag, drive in (
        (plane_a, offset_a, "A", drive_a),
        (plane_b, offset_b, "B", drive_b),
    ):
        if abs(off) < 1e-9:
            planes.append(base)
            continue
        plane_name = check(
            f"plane {label} {tag} ({base} + {off:g})",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane=base, offset=off)
            ),
        ).name
        planes.append(plane_name)
        created.append((plane_name, "PLANE"))
        if drive is not None and drive_jobs is not None:
            drive_jobs.append((f"D1@{plane_name}", drive))
    axis_name = check(
        f"axis {label} ({planes[0]} ∩ {planes[1]})",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=planes)
        ),
    ).name
    # Hidden at creation, selectable by name: a shown axis or plane prints in
    # every render of the part and of each assembly that places it.
    blank_reference_geometry(adapter, (*created, (axis_name, "AXIS")))
    return axis_name
