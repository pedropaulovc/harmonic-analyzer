"""Part saving, STL/image export and view housekeeping.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

# Recipe-inert (in no cache key; see its docstring and check:inert). Imported as a
# module and used by attribute: it reads these helpers the same way, so neither
# side needs the other fully initialised at import time.
import _seat_forensics
import _telemetry
from _check import check, log
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _part_properties import apply_block_tolerances, apply_summary_info, part_properties
from _paths import DEFAULT_VIEWS, OUT_PNG, OUT_SLDPRT, OUT_STL
from _preferences import STL_EXPORT_PREFERENCES, enforce_preferences
from _rebuild import rebuild_stale_configurations

_ROUTINE_PART_VIEWS = frozenset(
    (
        "front",
        "back",
        "left",
        "right",
        "top",
        "bottom",
        "isometric",
        "trimetric",
        "dimetric",
    )
)


@_telemetry.traced("export.stl")
async def export_part_stl(adapter: Any, out_path: Path) -> None:
    """Write the active part's fine binary STL (mm, model origin) to ``out_path``.

    The assembly build reads these via ``stl_bbox_mm`` to place each
    bbox-mirrored part, so a part build must emit its STL alongside the SLDPRT --
    ``export_models.py`` only refreshes the render cache and can't bootstrap a
    from-empty assembly (its part list is manifest-driven and otherwise needs an
    already-built assembly to scan).

    The export preferences are ENFORCED, not saved-and-restored (see
    :func:`enforce_preferences`). The previous version captured the seat's
    OBSERVED values and restored them in a ``finally``: any death inside the
    block -- including our own watchdog ``os._exit`` paths, which skip ``finally``
    by construction -- stranded the mutated values on the seat, and the next run
    then captured the stranded value as "the original" and restored it forever.
    Nothing in this repo wants any other STL configuration, so the declared state
    is asserted and deliberately left in place, which makes stranding impossible
    rather than unlikely.
    """
    enforce_preferences(adapter, STL_EXPORT_PREFERENCES)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Delete any prior STL first so a failed SaveAs3 (locked target, export
    # error) cannot leave a stale file that the existence check below would
    # accept as a fresh export (codex review #10). SaveAs3's return is not a
    # reliable success flag here (it yields 0 on a successful write), so the
    # post-delete "file exists" check is the real gate.
    if out_path.exists():
        out_path.unlink()
    rc = adapter._attempt(lambda: adapter.currentModel.SaveAs3(str(out_path), 0, 0))
    if not out_path.exists():
        raise RuntimeError(
            f"STL export produced no file (SaveAs3 rc={rc!r}): {out_path}"
        )
    _telemetry.success(
        f"export STL -> {out_path.name} ({out_path.stat().st_size / 1e6:.1f} MB)"
    )


@_telemetry.traced("export.part_images", label_param="part_name")
async def save_part_and_images(
    adapter: Any,
    part_name: str,
    views: Iterable[str] = DEFAULT_VIEWS,
    *,
    allowed_shown: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Save the part to ``cad/out/sldprt``, its STL to ``cad/out/stl`` (the
    assembly build reads it for mirror placement), and PNG views to
    ``cad/out/png``.

    The creating helpers hide the planes, axes, points and curves they make;
    the save fails if anything still shows, including any sketch not listed in
    ``allowed_shown`` (``reference_visibility_allowances``)."""
    from _visibility import assert_reference_geometry_hidden

    # Recorded BEFORE anything touches the camera: this runs at the end of
    # authoring, and set_isometric_view below (like export_image further down) is
    # the first thing in the whole build path that moves the view, so this is the
    # last moment at which the screen-space state the sketches were authored
    # under can still be read. A SUCCESS has to record it too -- otherwise a good
    # run and a bad one cannot be compared (see _seat_forensics.record_authoring_context).
    _seat_forensics.record_authoring_context(adapter, part_name)
    assert_reference_geometry_hidden(adapter, part_name, allowed_shown)
    OUT_SLDPRT.mkdir(parents=True, exist_ok=True)
    part_path = (OUT_SLDPRT / f"{part_name}.SLDPRT").resolve()
    set_isometric_view(adapter)  # save on isometric so the .SLDPRT opens isometric
    check(f"save_file -> {part_path}", await adapter.save_file(str(part_path)))

    png_dir = OUT_PNG / part_name
    png_dir.mkdir(parents=True, exist_ok=True)
    views = list(views)
    _prune_stale_part_views(png_dir, part_name, views)
    apply_block_tolerances(adapter)
    properties = part_properties(part_name)
    apply_custom_properties(adapter, properties)
    # The drawing template's PART cell resolves the linked model's document
    # summary Title, not its same-named custom property. Keep both identities
    # sourced from part_properties (the slug) so the two cannot split.
    apply_summary_info(adapter, title=properties["Title"])
    rebuild_stale_configurations(adapter, part_name)
    check(
        f"re-save with properties -> {part_path}",
        await adapter.save_file(str(part_path)),
    )

    stl_path = (OUT_STL / f"{part_name}.STL").resolve()
    await export_part_stl(adapter, stl_path)

    artefacts = {"part": str(part_path), "stl": str(stl_path)}
    for view in views:
        img_path = (png_dir / f"{part_name}_{view}.png").resolve()
        check(
            f"export_image {view}",
            await adapter.export_image(
                {
                    "file_path": str(img_path),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": view,
                }
            ),
        )
        artefacts[view] = str(img_path)
    return artefacts


def _prune_stale_part_views(
    png_dir: Path, part_name: str, views: Iterable[str]
) -> None:
    """Remove obsolete routine views without deleting configuration renders."""
    requested = {f"{part_name}_{view}.png" for view in views}
    for view in _ROUTINE_PART_VIEWS:
        stale = png_dir / f"{part_name}_{view}.png"
        if stale.name not in requested:
            stale.unlink(missing_ok=True)


def set_isometric_view(adapter: Any) -> None:
    """Orient the active document to the standard Isometric view (+ zoom to fit).

    Every part/assembly build calls this at the START (right after
    ``create_part``/``create_assembly``) and the shared save helpers call it again
    just before writing the document, so every ``.SLDPRT``/``.SLDASM`` OPENS on
    isometric -- the convention the user asked for. ``ShowNamedView2`` with an
    empty ``VName`` and ``swIsometricView`` (7) is the documented orient call (see
    the SolidWorks "Change to Isometric and Zoom to Fit" example); the same
    ``ShowNamedView2``/``_zoom_to_fit`` pair as :func:`remap_front_to_machine_front`.

    Independent of :func:`remap_front_to_machine_front`'s standard-view re-basing:
    on the top assembly that runs AFTER the remap, so the file still opens
    isometric while the gallery's re-based Front/Back/etc. stay correct. Tolerant
    of an empty just-created document -- the orient + zoom-to-fit are best-effort.
    """
    SW_ISOMETRIC = 7  # swStandardViews_e.swIsometricView
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if model is None:
        return
    adapter._attempt(lambda: model.ShowNamedView2("", SW_ISOMETRIC), default=None)
    adapter._zoom_to_fit(model)
    log("view set to isometric")
