r"""Plain-shank McMaster fillister head screws for new purchased SKUs (#2886).

The head, slot and tip follow the same family laws as
``diag_mcmaster_fillister`` (the vendor's 5-dim equations): head cylinder
band = HeadHeight*0.8 under a spherical-cap dome through the apex and the
rim; slot width = HeadDia*0.135, depth = width*1.5 from the apex; tip
chamfer 45 deg x 0.7P.  The shank is a plain cylinder at the thread major:
no split, helix, ``ThreadGroove`` or runout, so a recipe built on this
helper declares ``threaded=False``.  It is a separate file so the threaded
family's recipes keep their cache keys (AGENTS.md, "File-granular recipe
helpers").

Frame: head UP, under-head junction at y = 0, axis on the Front plane's Y.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from _sketch import add_line_chain  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    _spherical_cap_volume,
    no_sketch_inference,
)


def plain_fillister_volume(size: tuple[float, ...]) -> float:
    """The revolved head and plain shank, mm^3, before the slot."""
    major_d, length, hh, hd, pitch = size
    major_r, head_r = major_d / 2.0, hd / 2.0
    band = hh * 0.8
    tip_ch = 0.7 * pitch
    return (
        _spherical_cap_volume(head_r, hh - band)
        + math.pi * head_r**2 * band
        + math.pi * major_r**2 * (length - tip_ch)
        + _rev_frustum(tip_ch, major_r, major_r - tip_ch)
    )


def build_plain_fillister(adapter, size: tuple[float, ...]) -> None:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    major_d, length, hh, hd, pitch = size
    major_r = major_d / 2.0
    head_r = hd / 2.0
    band = hh * 0.8
    dome_h = hh - band
    slot_w = hd * 0.135
    slot_d = slot_w * 1.5
    tip_ch = 0.7 * pitch
    apex_y = hh
    cap_r = (head_r**2 + dome_h**2) / (2.0 * dome_h)

    check("create_sketch profile", adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(0.0, hh / 1000.0, 0.0, 0.0, -length / 1000.0, 0.0)
            is None
        ):
            raise RuntimeError("plain fillister profile: CreateCenterLine failed")
    # The dome as a three-point arc under no_sketch_inference: the mid-point
    # pins the bulge side with no direction flag (diag_mcmaster_fillister).
    yc = apex_y - cap_r
    ang_mid = (math.pi / 2.0 + math.atan2(band - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0,
            apex_y / 1000.0,
            0.0,
            head_r / 1000.0,
            band / 1000.0,
            0.0,
            cap_r * math.cos(ang_mid) / 1000.0,
            (yc + cap_r * math.sin(ang_mid)) / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError("plain fillister profile: dome arc failed")
        add_line_chain(
            adapter,
            [
                (head_r, band),
                (head_r, 0.0),
                (major_r, 0.0),
                (major_r, -(length - tip_ch)),
                (major_r - tip_ch, -length),
                (0.0, -length),
                (0.0, apex_y),
            ],
            close=False,
        )
    check("exit_sketch profile", adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check(
        "revolve body",
        adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "Body")
    v = plain_fillister_volume(size)
    volume_check(adapter, "revolved body", v, 0.005 * v)

    check("create_sketch slot", adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        add_line_chain(
            adapter,
            [
                (-slot_w / 2.0, apex_y + 0.5),
                (slot_w / 2.0, apex_y + 0.5),
                (slot_w / 2.0, apex_y - slot_d),
                (-slot_w / 2.0, apex_y - slot_d),
            ],
        )
    check("exit_sketch slot", adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check(
        "cut slot",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * hd, both_directions=True)
        ),
    )
    name_last_feature(adapter, "DriverSlot")
