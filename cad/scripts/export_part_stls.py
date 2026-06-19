r"""Bootstrap a base-part STL (mm, fine, untranslated) for every part document
in cad/out/sldprt that lacks a fresh one.

``mirror_placement`` mirrors each component about the machine YZ plane and reads
the part's STL bbox (``stl_bbox_mm``) to find the mirror centre. ``export_models``
only exports the parts/assemblies named in comparisons/manifest.json, so the
drive-train support parts (pedestals, posts, shafts) -- which are not in the
manifest -- have no STL. On a fresh checkout, or after the gitignored
cad/out/stl cache is wiped, the first assembly build then dies with
``FileNotFoundError`` on the first such part. This fills that gap: one STL per
present part document, enough for every assembly to compute its mirror centres.
The richer per-configuration STLs + STEP + scene boxes still come from
``export_models.py`` (driven by the comparison manifest).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\export_part_stls.py [--force]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import OUT_STL, check, log, run_build  # noqa: E402
from export_models import (  # noqa: E402
    OUT_SLDPRT,
    doc_rgb,
    load_colors,
    restore_export_prefs,
    save_colors,
    set_export_prefs,
)


def _stale(stem: str) -> bool:
    stl = OUT_STL / f"{stem}.STL"
    src = OUT_SLDPRT / f"{stem}.SLDPRT"
    return not stl.exists() or stl.stat().st_mtime < src.stat().st_mtime


async def build(adapter):
    OUT_STL.mkdir(parents=True, exist_ok=True)
    colors = load_colors()
    force = "--force" in sys.argv[1:]
    todo = [p.stem for p in sorted(OUT_SLDPRT.glob("*.SLDPRT")) if force or _stale(p.stem)]
    if not todo:
        print("all part STLs fresh")
        return {}
    print(f"exporting {len(todo)} part STLs: {todo}")
    old = set_export_prefs(adapter)
    done: dict[str, str] = {}
    try:
        for stem in todo:
            src = OUT_SLDPRT / f"{stem}.SLDPRT"
            check(f"open {src.name}", await adapter.open_model(str(src)))
            doc = adapter.currentModel
            out = OUT_STL / f"{stem}.STL"
            doc.SaveAs3(str(out), 0, 0)
            if not out.exists():
                raise RuntimeError(f"SaveAs3 produced no file: {out}")
            colors[stem] = doc_rgb(doc)
            log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB) rgb={colors[stem]}")
            adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
            done[stem] = str(out)
    finally:
        restore_export_prefs(adapter, old)
        save_colors(colors)
    return done


if __name__ == "__main__":
    raise SystemExit(run_build(build))
