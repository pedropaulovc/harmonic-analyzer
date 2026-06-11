# /// script
# requires-python = ">=3.11"
# ///
"""Generate comparisons/index.html — all pairs side by side for inspection.

Static page, relative image paths, no dependencies. Pairs are grouped by
model; each row shows reference | render | blend with id, camera pose,
score, status and notes. A text box filters rows (id/model/source/notes),
and broken/missing renders are flagged.

Usage:
    uv run comparisons/tools/gallery.py
"""

import html
import json
from pathlib import Path

COMP = Path(__file__).resolve().parents[1]
OUT = COMP / "index.html"

CSS = """
body { font-family: system-ui, sans-serif; margin: 0; background: #1b1b1f; color: #ddd; }
header { position: sticky; top: 0; background: #26262c; padding: .6em 1em; z-index: 9;
         display: flex; gap: 1em; align-items: baseline; box-shadow: 0 2px 6px #0008; }
header h1 { font-size: 1.05em; margin: 0; }
header input { background: #1b1b1f; color: #ddd; border: 1px solid #555;
               border-radius: 4px; padding: .3em .6em; width: 22em; }
header .count { color: #9a9; }
h2 { padding: .4em 1em 0; margin: .6em 0 0; color: #cdc; font-size: 1em; }
.pair { display: flex; gap: 6px; align-items: flex-start; padding: .5em 1em;
        border-bottom: 1px solid #2e2e35; }
.pair.hide { display: none; }
.imgs { display: flex; gap: 6px; flex: 1; min-width: 0; }
.imgs a { flex: 1; min-width: 0; text-align: center; }
.imgs img { max-height: 300px; max-width: 100%; object-fit: contain;
            background: #000; border-radius: 3px; }
.imgs .lbl { font-size: .7em; color: #888; }
.meta { width: 21em; flex: none; font-size: .8em; line-height: 1.5; }
.meta .id { font-weight: 600; color: #fff; word-break: break-all; }
.meta .tier { background: #354; color: #cfc; border-radius: 3px; padding: 0 .4em; font-weight: 600; }
.meta .cam { color: #8ab; }
.meta .score { color: #c96; }
.meta .status-rough { color: #b85; } .meta .status-aligned { color: #8b5; }
.meta .notes { color: #999; }
.missing { color: #e66; font-weight: 600; }
"""

JS = """
const q = document.getElementById('q');
const rows = [...document.querySelectorAll('.pair')];
const count = document.getElementById('count');
function apply() {
  const t = q.value.toLowerCase();
  let n = 0;
  for (const r of rows) {
    const hit = !t || r.dataset.text.includes(t);
    r.classList.toggle('hide', !hit);
    if (hit) n++;
  }
  count.textContent = n + ' / ' + rows.length + ' pairs';
}
q.addEventListener('input', apply);
apply();
"""


def img_cell(rel: str, label: str) -> str:
    p = COMP / rel
    if not p.is_file():
        return f'<div><span class="missing">missing {html.escape(label)}</span></div>'
    return (f'<a href="{rel}" target="_blank"><img loading="lazy" src="{rel}">'
            f'<div class="lbl">{html.escape(label)}</div></a>')


def pair_row(pair: dict, score) -> str:
    pid = pair["id"]
    cam = pair["camera"]
    campart = [f"az {cam.get('az_deg', 0):g}° el {cam.get('el_deg', 0):g}°"]
    if cam.get("mode") == "named":
        campart = [f"view {cam.get('view')}"]
    if cam.get("zoom", 1.0) not in (1.0, None):
        campart.append(f"zoom {cam['zoom']:g}")
    if cam.get("frame_components"):
        campart.append("framed: " + ", ".join(cam["frame_components"][:4]))
    tier = f"p{pair.get('tier', 9)}"
    text = " ".join([pid, tier, pair["model"], pair["reference"].get("source", ""),
                     pair.get("notes", ""), pair.get("status", "")]).lower()
    meta = [
        f'<div class="id">{html.escape(pid)}</div>',
        f'<div><span class="tier">{tier}</span> · '
        f'{html.escape(pair["reference"].get("source", ""))}</div>',
        f'<div class="cam">{html.escape(" | ".join(campart))}</div>',
        f'<div><span class="score">score {score if score is not None else "—"}</span>'
        f' · <span class="status-{pair.get("status", "rough")}">{pair.get("status", "rough")}</span></div>',
    ]
    if pair.get("notes"):
        meta.append(f'<div class="notes">{html.escape(pair["notes"])}</div>')
    return (
        f'<div class="pair" data-text="{html.escape(text)}">'
        f'<div class="meta">{"".join(meta)}</div>'
        f'<div class="imgs">'
        + img_cell(f"ref/{pid}.jpg", "reference")
        + img_cell(f"render/{pid}.jpg", "CAD render")
        + img_cell(f"composite/{pid}_blend.jpg", "blend")
        + "</div></div>"
    )


def main() -> int:
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    scores_path = COMP / "scores.json"
    scores = json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.exists() else {}

    by_model: dict[str, list[dict]] = {}
    for p in manifest["pairs"]:
        by_model.setdefault(p["model"], []).append(p)

    sections = []
    for model in sorted(by_model):
        pairs = sorted(by_model[model], key=lambda p: (p.get("tier", 9), p["id"]))
        rows = "".join(pair_row(p, scores.get(p["id"])) for p in pairs)
        sections.append(f'<h2 id="{model}">{model} ({len(pairs)})</h2>{rows}')

    nav = " · ".join(f'<a href="#{m}" style="color:#8ab">{m}</a>' for m in sorted(by_model))
    OUT.write_text(
        "<!doctype html><meta charset='utf-8'><title>harmonic-analyzer comparisons</title>"
        f"<style>{CSS}</style>"
        "<header><h1>photo vs CAD</h1>"
        "<input id='q' placeholder='filter: id, model, source, notes…'>"
        "<span class='count' id='count'></span></header>"
        f"<div style='padding:.5em 1em;font-size:.85em'>{nav}</div>"
        + "".join(sections)
        + f"<script>{JS}</script>",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(manifest['pairs'])} pairs, {len(by_model)} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
