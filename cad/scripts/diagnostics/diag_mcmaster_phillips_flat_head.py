r"""Recipe for McMaster Phillips flat (82 deg countersunk) head machine screws.

``build_phillips_flat_head(adapter, d)`` authors one 91771A screw from a pure
:class:`_phillips_flat_head_dimensions.PhillipsFlatHeadScrew` (catalogue
first; the vendor model's reading only where the catalogue is silent).  It is
not replica-gated (user ruling 2026-10-17): the standalone run is
catalog-only (``build_phillips_flat_head_catalog``).
``diag_mcmaster_oval`` is hardwired to one slotted, crowned oval head and
cannot draw a flat top with a cross recess, so the family is drawn here, with
the socket head family's idioms (91255A148's socket cut, 91375A106's
single-body thread route):

1. ``Shank``: revolve of the half-section below the thread top.
2. ``ThreadHelix`` / ``ThreadGroove``: the tip-seeded helix and the family
   cutter swept as a cut on the part's only body (``thread_cut``, i.e.
   ``diag_mcmaster_lib.thread_sweep_cut_modern``).  Cutting the shank before
   the head exists ends the groove in a flat face at the thread top with no
   body scoping.
3. ``Head``: revolve boss of the rest (flat top, 82 deg cone, the major down
   to the thread top); it merges onto the groove's flat end.
4. ``RecessCut``: the cross-and-notch outline on the Top Plane, cut blind to
   the thread top with every wall drafted inward at the recess draft
   (FeatureCut4).
5. ``RecessRefill``: revolve boss putting back what that cut took outside
   the entry cylinder and the bottom cone.
6. ``RecessConeTip``: revolve cut of the bottom cone below the drafted cut.

Frame: axis +Y (Front ∩ Right), head up, the flat top (the face that sits
flush in the countersink) on the Top Plane, the tip at y = -length.
"""

from __future__ import annotations

import math

import _telemetry  # noqa: E402

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from _phillips_flat_head_dimensions import (  # noqa: E402
    Point,
    PhillipsFlatHeadScrew,
    revolved_volume,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    assert_profile_closed,
    bodies,
    draw_closed_profile,
    insert_helix,
    mass_properties,
    offset_plane,
    thread_sweep_cut_modern,
)
from diagnostics.sketch_profile import Line, Segment  # noqa: E402


def profile_segments(loop) -> tuple[Segment, ...]:
    """A record's ``(p0, p1)`` line loop as sketch segments."""
    return tuple(Line(*s) for s in loop)


def chain_segments(points: tuple[Point, ...]) -> tuple[Segment, ...]:
    """A closed polygon through ``points`` as sketch segments."""
    return tuple(Line(a, b) for a, b in zip(points, points[1:] + points[:1]))


async def sketch_revolve(
    adapter,
    label: str,
    segments: tuple[Segment, ...],
    *,
    profile_name: str,
    feature_name: str,
    is_cut: bool,
) -> None:
    """One closed (radius, y) profile on Front, with its axis as a
    centerline, revolved 360 deg about +Y."""
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    ys = [p[1] for s in segments for p in (s.start, s.end)]
    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCenterLine(
                0.0, max(ys) / 1000.0, 0.0, 0.0, min(ys) / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{label}: CreateCenterLine failed")
    await draw_closed_profile(adapter, segments, label=label, loops=1)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, profile_name)
    assert_profile_closed(adapter, label, loops=1, feature=profile_name)
    check(
        label,
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=is_cut)),
    )
    name_last_feature(adapter, feature_name)


async def thread_cut(adapter, d: PhillipsFlatHeadScrew) -> None:
    """The tip-seeded right-hand ``ThreadHelix`` (91255A148's flags for a +Y
    ``TipPlane``) and the family cutter swept round it as a cut on the
    part's only body, through ``thread_sweep_cut_modern``."""
    from _sketch import add_line_chain
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    part_no = d.part_no
    offset_plane(adapter, "TipPlane", d.tip_y)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, d.major_r / 1000.0
            )
            is None
        ):
            raise RuntimeError(f"{part_no} helix seed circle failed")
    insert_helix(
        adapter,
        d.pitch,
        d.helix_revs,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, list(d.thread_cutter()))
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    count = len(bodies(adapter))
    if count != 1:
        raise RuntimeError(
            f"{part_no}: {count} bodies before the thread cut, expected 1"
        )
    thread_sweep_cut_modern(adapter, "ThreadCutter", "ThreadHelix", "ThreadGroove")


def drafted_cut_down(
    adapter, sketch_name: str, depth_mm: float, draft_deg: float, feature_name: str
):
    """91255A148's socket cut idiom (FeatureCut4 single direction, default
    direction, blind) with the first direction drafted: Dchk1 = True,
    Ddir1 = False (inward: the section shrinks with depth; True flared the
    walls on farm run 20261017T051944296Z: 5.71 mm^3 removed, the recess at
    -5 deg, instead of 5.09), Dang1 in radians."""
    from _com import _early_bound, _read_member
    from _feature_tree import _feature_by_name

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    model.ClearSelection2(True)
    _feature_by_name(adapter, sketch_name).Select2(False, 0)
    feat = fm.FeatureCut4(
        True,
        False,
        False,  # single, no flip, default dir
        0,
        0,
        depth_mm / 1000.0,
        0.0,  # blind
        True,
        False,
        False,  # Dchk1, Dchk2, Ddir1 (False = inward)
        False,  # Ddir2
        math.radians(draft_deg),
        0.0,  # Dang1, Dang2
        False,
        False,
        False,
        False,
        False,
        False,
        True,
        False,
        False,
        False,
        0,
        0.0,
        False,
        False,
    )
    if feat is None:
        raise RuntimeError(f"{feature_name}: FeatureCut4 failed")
    name_last_feature(adapter, feature_name)


@_telemetry.traced("stock.phillips_flat_head")
async def build_phillips_flat_head(adapter, d: PhillipsFlatHeadScrew) -> None:
    """Author ``d`` in the open part (see the module docstring)."""
    from _sketch import add_line_chain
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    part_no = d.part_no
    shank = d.shank_profile()

    # --- 1. shank (below the thread top) ---------------------------------------
    await sketch_revolve(
        adapter,
        f"{part_no} shank",
        profile_segments(shank),
        profile_name="ShankProfile",
        feature_name="Shank",
        is_cut=False,
    )
    v = revolved_volume(shank)
    await volume_check(adapter, f"{part_no} revolved shank", v, 1e-4 * v)

    # --- 2. helix and single-body thread groove ------------------------------
    await thread_cut(adapter, d)

    # --- 3. head ---------------------------------------------------------------
    await sketch_revolve(
        adapter,
        f"{part_no} head",
        profile_segments(d.head_profile()),
        profile_name="HeadProfile",
        feature_name="Head",
        is_cut=False,
    )
    merged = len(bodies(adapter))
    if merged != 1:
        raise RuntimeError(f"{part_no}: {merged} bodies after the head, expected 1")
    before = mass_properties(adapter)["volume_mm3"]

    # --- 4. drafted cross-and-notch cut ---------------------------------------
    # The outline is symmetric under the square's rotations and reflections,
    # so the Top sketch's axis directions do not matter.
    check("create_sketch recess", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, list(d.recess_outline()))
    check("exit_sketch recess", await adapter.exit_sketch())
    name_last_feature(adapter, "RecessProfile")
    # Ddir1 False drafts the walls inward (farm-verified sense, see
    # drafted_cut_down); a wrong sense fails the recess volume check below by
    # far more than its 1 %.
    drafted_cut_down(
        adapter, "RecessProfile", d.thread_top_depth, d.recess_draft_deg, "RecessCut"
    )

    # --- 5. refill outside the entry cylinder and the cone, 6. cone tip ------
    await sketch_revolve(
        adapter,
        f"{part_no} recess refill",
        profile_segments(d.refill_profile()),
        profile_name="RecessRefillProfile",
        feature_name="RecessRefill",
        is_cut=False,
    )
    await sketch_revolve(
        adapter,
        f"{part_no} recess cone tip",
        chain_segments(d.cone_tip_profile()),
        profile_name="RecessConeTipProfile",
        feature_name="RecessConeTip",
        is_cut=True,
    )
    recess = d.recess_volume()
    await volume_check(
        adapter, f"{part_no} Phillips recess", before - recess, 0.01 * recess
    )
    merged = len(bodies(adapter))
    if merged != 1:
        raise RuntimeError(f"{part_no}: {merged} bodies after the recess, expected 1")


async def build_phillips_flat_head_catalog(
    adapter, d: PhillipsFlatHeadScrew
) -> dict[str, str]:
    """Catalog-only run (``diag_mcmaster_socket_head.build_socket_head_catalog``'s
    steps): build the recipe, check the solid is sane and save it with its
    views under cad/out/reference; no vendor truth."""
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
    )

    part_no = d.part_no
    with _telemetry.span("catalog.build", label=part_no):
        check(f"create_part {part_no}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, part_no)
        await build_phillips_flat_head(adapter, d)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{part_no} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{part_no}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{part_no}-catalog"))
        _telemetry.success(
            f"{part_no} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts
