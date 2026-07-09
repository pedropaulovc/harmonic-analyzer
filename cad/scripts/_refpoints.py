"""Permanent named reference points on the moving parts (spring eyes, cam ring
centres, the wire rim point).

The full-machine couplings (``_assembly_top.py``: 20 cam ring<->lobe mates, 21
spring force elements, the WIRE-2 rim->pen yoke) each need a mateable POINT on a
part. These used to be created at RUNTIME by the motion study -- an
``ActivateDoc3`` round-trip per part doc, never saved -- so the shipped parts
could not carry the couplings. Each part build now authors its point(s) as a
permanent named REFERENCE POINT feature, anchored to real geometry (``arc_center``
of the eye hole's circular edge / ``along_curve`` on the rim edge), so the point
MOVES WITH the geometry instead of drifting silently like a raw coordinate would.

Imported ONLY by the part scripts that carry a coupling anchor -- deliberately
NOT ``_common.py``, whose helper closure is on every part's build recipe (adding
it there would rebuild the whole ~100-part fleet for a six-part feature).

Each ``edge_points`` is a CANDIDATE list (part-local mm): a union can consume
part of a circular edge (the gooseneck lug eats the pin end-face's top arc,
probed live), so several points on the same circle are tried in order and the
first that selects wins.
"""

from __future__ import annotations

from typing import Any, Sequence

from _common import log, name_last_feature


async def add_named_point(
    adapter: Any,
    name: str,
    edge_points: Sequence[Sequence[float]],
    mode: str = "arc_center",
) -> str:
    """Author a named reference-point feature on the ACTIVE part document.

    ``arc_center`` -> the centre of the circular edge under the candidate point
    (eye holes, the connecting-rod ring bore); ``along_curve`` (percentage 0) ->
    the curve point itself (the magnifying-wheel rim). Returns ``name``; raises
    if no candidate edge selects.
    """
    from solidworks_mcp.adapters.base import CreateReferencePointParameters

    last_err: Any = None
    for ep in edge_points:
        kwargs: dict[str, Any] = {"mode": mode, "edge_point": list(ep)}
        if mode == "along_curve":
            kwargs.update(along="percentage", percentage=0.0)
        res = await adapter.create_reference_point(
            CreateReferencePointParameters(**kwargs)
        )
        if res.is_success:
            log(f"  ref point {name}: edge {list(ep)} selected")
            return name_last_feature(adapter, name)
        last_err = res.error
        log(f"    ref point {name}: edge {list(ep)} rejected")
    raise RuntimeError(
        f"ref point {name}: no candidate edge selected ({[list(e) for e in edge_points]}); "
        f"last error: {last_err}"
    )
