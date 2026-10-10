"""Part materials and colours.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _check import check, log
from _com import _early_bound


@_telemetry.traced("appearance.material", label_param="material")
async def apply_material(adapter: Any, material: str) -> None:
    """Assign a SolidWorks-database material (saved with the part).

    Materials follow the book: brass for the polished gauge/lever/pen
    hardware, gray cast iron for the castings (base, levers, supports),
    plain carbon steel for shafts/pins/bars, alloy steel for spring wire,
    oak for the stained-wood crank handle (see DIMENSIONS.md per chapter).
    """
    from solidworks_mcp.adapters.base import ApplyMaterialParameters

    check(
        f"apply_material {material}",
        await adapter.apply_material(ApplyMaterialParameters(material=material)),
    )


CASTING_GREEN = (0.03, 0.45, 0.38)  # re-sampled from the ch30/ch17/ch18 plates


# (2026-07-08): R≈0.05·G, B≈0.85·G — the previous 0.13 red channel rendered teal
# M6.8 photo-tuning palette, all sampled from the ch30 plates:
POLISHED_STEEL = (0.65, 0.64, 0.63)  # frame columns (p006 column average)


PANEL_BLACK = (0.08, 0.08, 0.09)  # platen board / clips / knife hardware


SPRING_BLACK = (0.12, 0.12, 0.13)  # blued spring wire (counter + channel)


STAINED_OAK = (0.16, 0.10, 0.07)  # crank handle (dark-stained wood)


PAPER_WHITE = (0.92, 0.92, 0.88)  # platen paper sheet


BAR_STEEL = (0.42, 0.41, 0.39)  # amplitude-bar curtain (p004 edge-on 0.56,


# back views read darker from shadowing; mid value chosen)
@_telemetry.traced("appearance.color")
async def apply_color(adapter: Any, rgb: tuple[float, float, float]) -> None:
    """Explicit part display colour, overriding the material appearance.

    The real machine's frame castings are green-painted, but their database
    material ("Gray Cast Iron") renders dark gray — those parts call this
    after apply_material. The comparison render cache reads the same
    override (export_models doc_rgb cascade).

    Set at BOTH the doc and the solid-body level: apply_material attaches
    the database material's render appearance at part scope, and doc MPV
    only retints its primary colour — useless against TEXTURED appearances
    (Oak's wood image kept rendering over PAPER_WHITE). Body appearances
    sit above part appearances in the display hierarchy, so the body-level
    colour wins over the texture.
    """
    from solidworks_mcp.adapters.com_variant import double_array

    values = double_array([*rgb, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0])
    doc = adapter.currentModel
    # [R,G,B, ambient, diffuse, specular, shininess, transparency, emission]
    doc.MaterialPropertyValues = values
    back = tuple(float(v) for v in (doc.MaterialPropertyValues or ())[:3])
    # SolidWorks quantises to 8 bits per channel
    if len(back) != 3 or any(abs(b - w) > 1 / 255 for b, w in zip(back, rgb)):
        raise RuntimeError(f"colour readback mismatch: set {rgb}, got {back}")
    n_bodies = 0
    try:
        part_h = _early_bound(
            doc, "IPartDoc"
        )  # IPartDoc for GetBodies2; keep `doc` for MaterialPropertyValues
        bodies = part_h.GetBodies2(0, True) or []  # solid bodies
        for body in bodies:
            body.MaterialPropertyValues2 = values
            n_bodies += 1
    except Exception as exc:
        log(f"body colour skipped ({exc})")
    log(f"colour override {tuple(round(v, 3) for v in back)} ({n_bodies} bodies)")
