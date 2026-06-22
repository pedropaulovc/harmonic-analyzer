# /// script
# requires-python = ">=3.11"
# ///
"""Generate comparisons/index.html — all pairs for inspection.

Static page, relative image paths, no dependencies. Pairs are grouped by
model; each row shows a reveal slider (reference under, the pixel-registered
composite/<id>_cad.jpg on top — drag to sweep) next to the red-tint blend,
with id, camera pose, score, status and notes. A text box filters rows
(id/model/source/notes), and broken/missing renders are flagged.

Usage:
    uv run comparisons/tools/gallery.py
"""

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cad" / "scripts"))
import _telemetry  # noqa: E402

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
header .tiers button { background: #1b1b1f; color: #bbb; border: 1px solid #555;
                       border-radius: 4px; padding: .25em .7em; cursor: pointer; }
header .tiers button.active { background: #354; color: #cfc; border-color: #7a7; }
h2 { padding: .4em 1em 0; margin: .6em 0 0; color: #cdc; font-size: 1em; }
.pair { display: flex; gap: 6px; align-items: flex-start; padding: .5em 1em;
        border-bottom: 1px solid #2e2e35; }
.pair.hide { display: none; }
.imgs { display: flex; gap: 6px; flex: 1; min-width: 0; }
.imgs a { flex: 1; min-width: 0; text-align: center; }
.imgs img { max-height: 340px; max-width: 100%; object-fit: contain;
            background: #000; border-radius: 3px; }
.imgs .lbl { font-size: .7em; color: #888; }
.cmpwrap { flex: 1.3; min-width: 0; text-align: center; }
.cmp { position: relative; display: inline-block; cursor: ew-resize;
       user-select: none; touch-action: none; }
.cmp img { display: block; }
.cmp .over { position: absolute; inset: 0; width: 100%; height: 100%;
             clip-path: inset(0 50% 0 0); }
.cmp .divider { position: absolute; top: 0; bottom: 0; left: 50%; width: 2px;
                background: #7af; opacity: .6; pointer-events: none; }
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
const tierBtns = [...document.querySelectorAll('.tiers button')];
let tier = 'all';
function apply() {
  const t = q.value.toLowerCase();
  let n = 0;
  for (const r of rows) {
    const hit = (tier === 'all' || r.dataset.tier === tier)
      && (!t || r.dataset.text.includes(t));
    r.classList.toggle('hide', !hit);
    if (hit) n++;
  }
  for (const s of document.querySelectorAll('section')) {
    s.style.display = s.querySelector('.pair:not(.hide)') ? '' : 'none';
  }
  count.textContent = n + ' / ' + rows.length + ' pairs';
}
for (const b of tierBtns) {
  b.addEventListener('click', () => {
    tier = b.dataset.tier;
    tierBtns.forEach(x => x.classList.toggle('active', x === b));
    apply();
  });
}
q.addEventListener('input', apply);
apply();
for (const c of document.querySelectorAll('.cmp')) {
  const over = c.querySelector('.over');
  const div = c.querySelector('.divider');
  const set = (x) => {
    const r = c.getBoundingClientRect();
    const v = Math.max(0, Math.min(1, (x - r.left) / r.width));
    over.style.clipPath = `inset(0 ${(1 - v) * 100}% 0 0)`;
    div.style.left = (v * 100) + '%';
  };
  c.addEventListener('pointerdown', (e) => {
    c.setPointerCapture(e.pointerId);
    set(e.clientX);
    e.preventDefault();
  });
  c.addEventListener('pointermove', (e) => { if (e.buttons) set(e.clientX); });
}
"""


def img_cell(rel: str, label: str) -> str:
    p = COMP / rel
    if not p.is_file():
        return f'<div><span class="missing">missing {html.escape(label)}</span></div>'
    return (f'<a href="{rel}" target="_blank"><img loading="lazy" src="{rel}">'
            f'<div class="lbl">{html.escape(label)}</div></a>')


def slider_cell(pid: str) -> str:
    """Reference under, pixel-registered CAD on top; drag sweeps the reveal."""
    ref, cad = f"ref/{pid}.jpg", f"composite/{pid}_cad.jpg"
    if not (COMP / ref).is_file() or not (COMP / cad).is_file():
        return img_cell(ref, "reference") + img_cell(f"render/{pid}.jpg", "CAD render")
    return (
        f'<div class="cmpwrap"><div class="cmp">'
        f'<img class="under" loading="lazy" src="{ref}">'
        f'<img class="over" loading="lazy" src="{cad}">'
        f'<div class="divider"></div></div>'
        f'<div class="lbl"><a href="{ref}" target="_blank">ref</a> ⇆ '
        f'<a href="{cad}" target="_blank">cad</a> · '
        f'<a href="render/{pid}.jpg" target="_blank">raw render</a></div></div>'
    )


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
        f'<div class="pair" data-text="{html.escape(text)}" data-tier="{tier}">'
        f'<div class="meta">{"".join(meta)}</div>'
        f'<div class="imgs">'
        + slider_cell(pid)
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
        sections.append(f'<section><h2 id="{model}">{model} ({len(pairs)})</h2>{rows}</section>')

    from collections import Counter

    tiers = Counter(f"p{p.get('tier', 9)}" for p in manifest["pairs"])
    tier_btns = "<button class='active' data-tier='all'>all</button>" + "".join(
        f"<button data-tier='{t}'>{t} ({tiers[t]})</button>" for t in sorted(tiers)
    )
    nav = " · ".join(f'<a href="#{m}" style="color:#8ab">{m}</a>' for m in sorted(by_model))
    OUT.write_text(
        "<!doctype html><meta charset='utf-8'><title>harmonic-analyzer comparisons</title>"
        f"<style>{CSS}</style>"
        "<header><h1>photo vs CAD</h1>"
        f"<span class='tiers'>{tier_btns}</span>"
        "<input id='q' placeholder='filter: id, model, source, notes…'>"
        "<span class='count' id='count'></span></header>"
        f"<div style='padding:.5em 1em;font-size:.85em'>{nav}</div>"
        + "".join(sections)
        + f"<script>{JS}</script>",
        encoding="utf-8",
    )
    _telemetry.success(f"wrote {OUT} ({len(manifest['pairs'])} pairs, {len(by_model)} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
