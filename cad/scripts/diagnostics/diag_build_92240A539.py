r"""McMaster 92240A539 -- 18-8 stainless hex head screw, 1/4"-20 x 5/8".

This diagnostic is a clean geometric replay of the harvested vendor part; it
never imports a production fastener specification.  Catalog dimensions are in
millimetres and are exposed below.  The vendor frame puts the under-head plane
at axial coordinate 0, the tip at -L, and the head top at +HH.  SolidWorks'
Top plane is that under-head plane.  The diagnostic adapter builds the screw
axis along model +Y, so a Front-plane profile uses sketch X for radius and
sketch Y for the vendor axial coordinate.  At the end, ``_mcm_com_map`` cycles
model XYZ to vendor XYZ (model Y becomes vendor Z) for centre-of-mass gating.

Geometry laws recovered from the harvest:

* The shank is a D/2 cylinder from 0 to -L.  Its 45-degree tip chamfer has
  equal axial and radial setback ``P*.75`` (the vendor Chamfer1 equation).
* The head is a regular hexagon of width HW across flats, hence circumradius
  ``HW/sqrt(3)``, extruded from 0 to +HH.  A Through-All outside-circle cut at
  the top uses the inscribed radius HW/2 and a 60-degree draft from the axis;
  this is the vendor's six rounded/trimmed corner faces.
* The under-head washer face is a circular boss of radius
  ``HW/2 - D*.01`` and thickness ``HW*.025`` below the under-head plane.
  Only its annulus outside the shank adds volume.
* The shank is fully threaded.  The sharp 60-degree thread height is
  ``P*sqrt(3)/2``; the root is ``D/2 - 3/4`` of that height, the root flat is
  P/8, and the crest cutter overtravels by 1/16 of the sharp height.  The
  tip-seeded helix spans ``L+P`` (13.5 turns) and starts at 90 degrees.  The
  cutter is centred 7P/16 beyond the tip, with crest endpoints at +/-15P/32
  and root endpoints at +/-P/16.  Splitting prevents the sweep from touching
  the head; a union restores the vendor's single body.  A final face-owned
  washer-radius boss extruded up to the hex underside reproduces the vendor
  washer transition and its merged face topology.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_92240A539.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import check, name_last_feature, volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    combine_union,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

# Catalog dimensions, millimetres.  Keep the diameter as a public constant;
# the radius is derived so the catalog law has one source of truth.
MAJOR_DIAMETER_MM = 6.35
LENGTH_MM = 15.875
HEX_WIDTH_MM = 11.1125
HEX_HEIGHT_MM = 3.96875
PITCH_MM = 1.27
WASHER_DEPTH_MM = HEX_WIDTH_MM * 0.025

# Vendor axial placement, expressed in the adapter's model-Y build frame.
UNDERSIDE_MM = 0.0
TIP_MM = UNDERSIDE_MM - LENGTH_MM
HEAD_TOP_MM = UNDERSIDE_MM + HEX_HEIGHT_MM


async def build_92240A539(adapter, truth=None):
    """Build the harvested 92240A539 geometry in the vendor coordinate frame."""
    from _common import add_line_chain, _early_bound, _feature_by_name, _read_member
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    major_r = MAJOR_DIAMETER_MM / 2.0
    sharp_thread_h = PITCH_MM * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * sharp_thread_h
    flat_r = HEX_WIDTH_MM / 2.0
    hex_r = HEX_WIDTH_MM / math.sqrt(3.0)

    # Vendor equations: Chamfer1=P*.75 and washer depth=HW*.025.  Sketch7's
    # harvested radial inset is 0.0635 mm, exactly one percent of thread OD.
    tip_chamfer = PITCH_MM * 0.75
    tip_flat_r = major_r - tip_chamfer
    washer_r = flat_r - MAJOR_DIAMETER_MM * 0.01
    washer_depth = WASHER_DEPTH_MM

    # Shank profile: Front sketch X is radius; Y is vendor axial Z.  Folding
    # the separately-authored vendor chamfer into this revolve preserves its
    # exact final cylinder, cone, and tip-plane faces deterministically.
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sketch = adapter.currentSketchManager
    if (
        sketch.CreateCenterLine(
            0.0,
            UNDERSIDE_MM / 1000.0,
            0.0,
            0.0,
            TIP_MM / 1000.0,
            0.0,
        )
        is None
    ):
        raise RuntimeError("92240A539 shank: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (0.0, UNDERSIDE_MM),
                (major_r, UNDERSIDE_MM),
                (major_r, TIP_MM + tip_chamfer),
                (tip_flat_r, TIP_MM),
                (0.0, TIP_MM),
            ],
        )
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check(
        "revolve shank",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "Shank")
    shank_volume = math.pi * major_r**2 * (LENGTH_MM - tip_chamfer) + _rev_frustum(
        tip_chamfer, major_r, tip_flat_r
    )
    await volume_check(adapter, "shank revolve", shank_volume, 0.005 * shank_volume)

    # The Top plane is exactly vendor Z=0: head goes +Y, washer face goes -Y.
    check("create_sketch hex", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (0.0, hex_r),
                (-flat_r, hex_r / 2.0),
                (-flat_r, -hex_r / 2.0),
                (0.0, -hex_r),
                (flat_r, -hex_r / 2.0),
                (flat_r, hex_r / 2.0),
            ],
        )
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    check(
        "extrude hex",
        await adapter.create_extrusion(ExtrusionParameters(depth=HEX_HEIGHT_MM)),
    )
    name_last_feature(adapter, "HexHead")
    hex_volume = HEX_WIDTH_MM**2 * math.sqrt(3.0) / 2.0 * HEX_HEIGHT_MM
    await volume_check(
        adapter,
        "hex head",
        shank_volume + hex_volume,
        0.005 * hex_volume,
    )

    # Circular washer boss below the hex.  Its core overlaps the shank, so the
    # observable added volume is the annulus rather than the complete disk.
    check("create_sketch washer", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, washer_r / 1000.0
            )
            is None
        ):
            raise RuntimeError("washer circle failed")
    check("exit_sketch washer", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    check(
        "washer face",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=washer_depth, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "WasherFace")
    washer_volume = math.pi * (washer_r**2 - major_r**2) * washer_depth
    await volume_check(
        adapter,
        "washer face",
        shank_volume + hex_volume + washer_volume,
        0.05 * washer_volume,
    )

    # At +HH, retain the r=HW/2 circle and cut the six corner regions.  The
    # 60-degree draft is measured from the screw axis, matching Cut-Extrude1.
    offset_plane(adapter, "HeadTopPlane", HEAD_TOP_MM)
    check("create_sketch trim", await adapter.create_sketch("HeadTopPlane"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, flat_r / 1000.0
            )
            is None
        ):
            raise RuntimeError("head trim circle failed")
    check("exit_sketch trim", await adapter.exit_sketch())
    name_last_feature(adapter, "TrimProfile")

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "TrimProfile").Select2(False, 0)
    feature_manager = _early_bound(
        _read_member(model, "FeatureManager"), "IFeatureManager"
    )
    trim = feature_manager.FeatureCut4(
        True,
        True,
        False,  # single-ended, cut outside the circle, default direction
        1,
        0,
        0.0,
        0.0,  # direction 1 Through All
        True,
        False,
        False,
        False,  # direction-1 draft; empirical vendor sense
        math.radians(60.0),
        0.0,
        False,
        False,
        False,
        False,
        False,
        False,
        True,  # normal cut, feature scope off, auto-select on
        False,
        False,
        False,
        0,
        0.0,
        False,
        False,
    )
    if trim is None:
        raise RuntimeError("corner trim cut failed")
    name_last_feature(adapter, "CornerTrim")

    # The vendor split lies at the under-head plane.  Build-frame body boxes
    # are [xmin, ymin, zmin, xmax, ymax, zmax], so Y identifies the shank.
    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for body in body_boxes:
        box = body["box_mm"]
        if box and box[1] < UNDERSIDE_MM - 1.0:
            shank_name = body["name"]
            break
    if shank_name is None:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # A Top-parallel plane at -L gives an ascending tip-seeded helix.  The
    # helper plane's orientation represents the vendor's clockwise+reversed
    # read-back as the equivalent false+false pair while growing toward +Y.
    offset_plane(adapter, "TipPlane", TIP_MM)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if (
        adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0
        )
        is None
    ):
        raise RuntimeError("helix seed circle failed")
    insert_helix(
        adapter,
        PITCH_MM,
        LENGTH_MM / PITCH_MM + 1.0,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # The cutter is the harvested symmetric 60-degree thread profile.  Its
    # crest deliberately extends beyond the major cylinder and beyond both
    # axial ends; body scoping clips the sweep to the split shank.
    cutter_center = TIP_MM - 7.0 * PITCH_MM / 16.0
    cutter_outer_r = major_r + sharp_thread_h / 16.0
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (cutter_outer_r, cutter_center + 15.0 * PITCH_MM / 32.0),
                (root_r, cutter_center + PITCH_MM / 16.0),
                (root_r, cutter_center - PITCH_MM / 16.0),
                (cutter_outer_r, cutter_center - 15.0 * PITCH_MM / 32.0),
            ],
        )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(
        adapter,
        "ThreadCutter",
        "ThreadHelix",
        shank_name,
        "ThreadGroove",
        tangency=(0, 0),
    )

    # The sweep is intentionally authored while split so it cannot cut the
    # head. Vendor Combine1 is an additive union back to one watertight body.
    combine_union(adapter, "BodyUnion")

    # Vendor Sketch8 is owned by the washer boss's -Y face, not an offset
    # plane. Boss-Extrude3 reverses from that face to the hex underside face
    # (deprecated UpToSurface=4). The extrusion overlaps the washer boss, but
    # its native merge coalesces the annular planar/side faces exactly as the
    # vendor feature does; replay the references rather than substituting a
    # blind distance.
    from _holes import find_planar_face
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    washer_bottom = find_planar_face(
        model,
        (0.0, -1.0, 0.0),
        [[4.0, -washer_depth, 0.0]],
        tol_mm=0.02,
    )
    head_underside = find_planar_face(
        model,
        (0.0, -1.0, 0.0),
        [[0.0, 0.0, 6.0]],
        tol_mm=0.02,
    )
    if washer_bottom is None or head_underside is None:
        raise RuntimeError("vendor washer-transition reference faces not found")

    model.ClearSelection2(True)
    if not _early_bound(washer_bottom, "IEntity").Select4(False, null_callout()):
        raise RuntimeError("washer-bottom sketch face selection failed")
    sketch_manager = _early_bound(model.SketchManager, "ISketchManager")
    sketch_manager.InsertSketch(True)
    with no_sketch_inference(adapter):
        if (
            sketch_manager.CreateCircleByRadius(0.0, 0.0, 0.0, washer_r / 1000.0)
            is None
        ):
            raise RuntimeError("washer-transition circle failed")
    sketch_manager.InsertSketch(True)
    name_last_feature(adapter, "WasherMergeProfile")

    model.ClearSelection2(True)
    if not _feature_by_name(adapter, "WasherMergeProfile").Select2(False, 0):
        raise RuntimeError("washer-merge profile selection failed")
    selection_manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    end_select = selection_manager.CreateSelectData()
    end_select = _early_bound(end_select, "ISelectData")
    end_select.Mark = 1
    if not _early_bound(head_underside, "IEntity").Select4(True, end_select):
        raise RuntimeError("washer-merge end-face selection failed")
    washer_merge = feature_manager.FeatureExtrusion3(
        True,
        False,
        True,
        4,
        0,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        True,
        False,
        True,
        0,
        0.0,
        False,
    )
    if washer_merge is None:
        raise RuntimeError("under-head face-merging extrusion failed")
    name_last_feature(adapter, "WasherMerge")

    # Cyclic, right-handed frame map: (model X,Y,Z) -> (vendor Y,Z,X).
    adapter._mcm_com_map = lambda value: [value[1], value[2], value[0]]


if __name__ == "__main__":
    sys.exit(replica_main("92240A539", build_92240A539))
