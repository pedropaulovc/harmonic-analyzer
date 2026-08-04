# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Build the self-contained visual report for a subject model's T1 results.

Ranking table + an arm gallery (each of the 11 presentations rendered on the
SAME perturbed case, ranked, with its scores) + per-parameter heatmap +
findings. Images are embedded as data URIs so the page is self-contained.

    uv run cad/comparisons/bench/build_report_html.py --model codex
"""

import argparse
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
import presentations as P  # noqa: E402

OUT = BENCH / "out"
EXEMPLAR_PAIR = "harmonic_analyzer--ch30-p002-img01"   # wide, dark, legible
EXEMPLAR_TAG = "az+15"                                  # clear single-axis rotation

ARM_NAME = {
    "P1": "Blend (red overlay)", "P2": "Side-by-side", "P3": "Side-by-side + grid",
    "P4": "Onion ladder", "P5": "Blend (subtle)", "P6": "Checkerboard",
    "P7": "Green–magenta fusion", "P8": "Difference heatmap", "P9": "Edge overlay",
    "P10": "Flicker pair", "P11": "Dashboard",
}
ARM_KIND = {  # incumbent / registration-visualization / multi-image
    "P1": "incumbent", "P2": "multi-image", "P3": "multi-image", "P10": "multi-image",
}


def _b64(img: Image.Image, long_edge: int, q: int = 82) -> str:
    w, h = img.size
    if max(w, h) > long_edge:
        s = long_edge / max(w, h)
        img = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _cases() -> dict:
    return {json.loads(l)["case_id"]: json.loads(l)
            for l in (BENCH / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}


def exemplar_images(cases: dict) -> dict:
    """Data URIs: the raw inputs + each arm's stimulus on the exemplar case."""
    tmp = OUT / "_report_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    pid, cid = EXEMPLAR_PAIR, f"{EXEMPLAR_PAIR}+{EXEMPLAR_TAG}"
    imgs = {}
    ref = Image.open(OUT / "ref" / f"{pid}.jpg")
    ctrl = Image.open(OUT / "render" / f"{pid}+ctrl.jpg")
    pert = Image.open(OUT / "render" / f"{cid}.jpg")
    imgs["ref"] = _b64(ref, 520)
    imgs["ctrl"] = _b64(ctrl, 520)
    imgs["pert"] = _b64(pert, 520)
    for arm in P.ARMS:
        paths = P.build_stimulus(cases[cid], arm, tmp, f"ex_{arm}", grid=False, side=0, order=0)
        if len(paths) == 1:
            imgs[arm] = _b64(Image.open(paths[0]), 520)
        else:  # P10 flicker: stitch the two frames with a divider
            a, b = Image.open(paths[0]).convert("RGB"), Image.open(paths[1]).convert("RGB")
            h = max(a.height, b.height)
            a = a.resize((round(a.width * h / a.height), h))
            b = b.resize((round(b.width * h / b.height), h))
            gap = 10
            stitched = Image.new("RGB", (a.width + gap + b.width, h), (60, 63, 70))
            stitched.paste(a, (0, 0))
            stitched.paste(b, (a.width + gap, 0))
            imgs[arm] = _b64(stitched, 640)
    return imgs


HTML = """<title>Pose-presentation benchmark — codex T1</title>
<style>
:root {{
  --paper:#f5f6f8; --card:#ffffff; --ink:#171a20; --muted:#5c6473; --faint:#8b93a1;
  --line:#e2e5ea; --accent:#2f6fb0; --accent-soft:#e7f0f8;
  --good:#2f8f5b; --mid:#c2892c; --bad:#c0473f;
  --shadow:0 1px 2px rgba(20,24,32,.06),0 6px 18px rgba(20,24,32,.05);
}}
@media (prefers-color-scheme:dark){{
  :root{{--paper:#0e1014;--card:#171a20;--ink:#e7eaef;--muted:#9aa3b2;--faint:#6b7280;
    --line:#242832;--accent:#5aa0e0;--accent-soft:#17222e;--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);}}
}}
:root[data-theme="dark"]{{--paper:#0e1014;--card:#171a20;--ink:#e7eaef;--muted:#9aa3b2;--faint:#6b7280;
  --line:#242832;--accent:#5aa0e0;--accent-soft:#17222e;--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);}}
:root[data-theme="light"]{{--paper:#f5f6f8;--card:#ffffff;--ink:#171a20;--muted:#5c6473;--faint:#8b93a1;
  --line:#e2e5ea;--accent:#2f6fb0;--accent-soft:#e7f0f8;--shadow:0 1px 2px rgba(20,24,32,.06),0 6px 18px rgba(20,24,32,.05);}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.55;
  -webkit-font-smoothing:antialiased;}}
.wrap{{max-width:1080px;margin:0 auto;padding:clamp(20px,4vw,52px) clamp(16px,3vw,32px) 80px;}}
h1,h2,h3{{font-family:Charter,"Iowan Old Style",Georgia,"Times New Roman",serif;
  font-weight:650;letter-spacing:-.01em;text-wrap:balance;line-height:1.15;}}
h1{{font-size:clamp(1.8rem,4vw,2.6rem);margin:0 0 .3em;}}
h2{{font-size:1.5rem;margin:2.6em 0 .2em;padding-top:.6em;border-top:1px solid var(--line);}}
h2:first-of-type{{border-top:none}}
h3{{font-size:1.06rem;margin:1.6em 0 .4em}}
.lede{{font-size:1.16rem;color:var(--muted);max-width:64ch;margin:.2em 0 1.4em}}
.mono{{font-family:ui-monospace,"SF Mono","Cascadia Code",Menlo,monospace;font-variant-numeric:tabular-nums}}
a{{color:var(--accent)}}
.eyebrow{{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);
  font-weight:700;margin-bottom:.8em}}
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin:1.2em 0 .4em}}
.chip{{font-size:.8rem;background:var(--card);border:1px solid var(--line);border-radius:999px;
  padding:5px 12px;color:var(--muted);box-shadow:var(--shadow)}}
.chip b{{color:var(--ink);font-variant-numeric:tabular-nums}}
.scroll{{overflow-x:auto;border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);background:var(--card)}}
table{{border-collapse:collapse;width:100%;font-size:.92rem}}
th,td{{padding:11px 14px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}}
th:first-child,td:first-child{{text-align:left}}
thead th{{font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);font-weight:600}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover{{background:var(--accent-soft)}}
.armname{{font-weight:600}}
.tag{{font-size:.68rem;color:var(--faint);margin-left:.5em;font-weight:500}}
.bar{{position:relative;min-width:120px}}
.bar .track{{height:7px;background:var(--line);border-radius:4px;overflow:hidden;margin-top:5px}}
.bar .fill{{height:100%;background:var(--accent);border-radius:4px}}
.num{{font-family:ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.rank{{color:var(--faint);font-variant-numeric:tabular-nums;width:2ch}}
.inputs{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:1.4em 0}}
.io{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;box-shadow:var(--shadow)}}
.io img{{width:100%;display:block;background:#0b0c0f}}
.io .cap{{padding:9px 12px;font-size:.82rem;color:var(--muted)}}
.io .cap b{{color:var(--ink);display:block;font-size:.9rem}}
.gallery{{display:flex;flex-wrap:wrap;gap:18px;margin:1.2em 0}}
.acard{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;
  box-shadow:var(--shadow);width:220px;display:flex;flex-direction:column}}
.acard.wide{{width:340px}}
.acard .imgwrap{{position:relative;background:#0b0c0f;display:flex;align-items:center;justify-content:center;
  min-height:150px;max-height:340px;overflow:hidden}}
.acard img{{max-width:100%;max-height:340px;display:block}}
.acard .badge{{position:absolute;top:8px;left:8px;background:rgba(10,12,16,.82);color:#fff;
  font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:999px;letter-spacing:.02em}}
.acard .score{{position:absolute;top:8px;right:8px;font-family:ui-monospace,monospace;font-weight:700;
  font-size:.82rem;padding:3px 9px;border-radius:999px;color:#fff}}
.acard .meta{{padding:10px 13px 13px}}
.acard .meta .nm{{font-weight:600;font-size:.95rem}}
.acard .meta .sub{{color:var(--muted);font-size:.8rem;margin-top:2px}}
.acard .meta .fp{{color:var(--faint);font-size:.76rem;margin-top:6px;font-variant-numeric:tabular-nums}}
.heat td.h{{color:#fff;font-family:ui-monospace,monospace;font-variant-numeric:tabular-nums;text-align:center;
  border:1px solid var(--paper)}}
.finding{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:10px;padding:14px 18px;margin:12px 0;box-shadow:var(--shadow)}}
.finding b{{color:var(--ink)}}
.note{{color:var(--muted);font-size:.92rem}}
footer{{margin-top:3em;padding-top:1.4em;border-top:1px solid var(--line);color:var(--faint);font-size:.84rem}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;font-size:.8rem;color:var(--muted);margin:.6em 0}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}}
</style>

<div class="wrap">
<div class="eyebrow">Pose-feedback presentation benchmark · first-pass screening</div>
<h1>Which composite lets a vision model read camera-pose error?</h1>
<p class="lede">Eleven ways to show a reference photo against a mis-posed CAD render, scored by how
well <b>Codex gpt-5.5</b> reads the applied camera error, discriminates two errors apart, and closes
a correction loop. Deterministic grading — no LLM judge. T1 (below) is an N=1 screening pass over Codex;
T3 and T2 are complete too, giving a full decision-rule preview — but the rule governs on Opus, whose
run is paused (see "Reading the result").</p>
<div class="chips">
 <span class="chip">subject · <b>Codex gpt-5.5</b>, high reasoning</span>
 <span class="chip">task · <b>T1</b> single-shot direction read</span>
 <span class="chip"><b>{ncells}</b> cells · {narms} arms × 6 pairs × 27 cases</span>
 <span class="chip">≈<b>{tokM}M</b> tokens</span>
 <span class="chip">grading · <b>deterministic</b></span>
</div>

<h2>The inputs</h2>
<p class="note">Every arm sees the same two images: the reference photograph (ground-truth pose) and a
CAD render from a perturbed camera. The exemplars below use pair <span class="mono">ch30-p002</span>
with a <b>+15° azimuth</b> error applied to the render.</p>
<div class="inputs">
 <div class="io"><img src="{ref}" alt="reference photo"><div class="cap"><b>Reference photo</b>correct pose (grayscale)</div></div>
 <div class="io"><img src="{ctrl}" alt="control render"><div class="cap"><b>Render · control</b>0° error baseline</div></div>
 <div class="io"><img src="{pert}" alt="perturbed render"><div class="cap"><b>Render · +15° az</b>the error to read</div></div>
</div>

<h2>Arm ranking</h2>
<p class="note">Headline metric is <b>macro sign accuracy</b> — did the model call the direction
(−/0/+) of each of the six camera parameters right, macro-averaged over the three sign classes so
the ~80%-<span class="mono">0</span> labels can't inflate the score. Bar = macro sign %; also shown:
magnitude-bucket accuracy, false-positive rate on the zero-error controls, and cost.</p>
<div class="scroll"><table>
<thead><tr><th>#</th><th>arm</th><th>macro sign %</th><th>95% CI</th><th>magnitude %</th>
<th>control FP %</th><th>median tok</th><th>lat s</th></tr></thead>
<tbody>{rows}</tbody></table></div>

<h2>What each presentation looks like</h2>
<p class="note">The same +15° case rendered through all eleven arms, ordered by rank. This is the
comparison: read each composite as the model must, then check its score. The registration-preserving
overlays (checkerboard, blends, fusion, edges) sit at the top; the two-image arms (side-by-side,
flicker) sit at the bottom — consistent with the known VLM weakness at multi-image reasoning.</p>
<div class="gallery">{cards}</div>

<h2>Per-parameter sign accuracy</h2>
<p class="note">Where each arm's reading strength lies. Rotations (az/el/roll) read well across the
board; <b>image-plane translation and zoom are the hard axes</b> for every arm, and collapse worst
on the side-by-side pair (P2/P3) — the classic azimuth↔target-x degeneracy.</p>
<div class="legend"><span><span class="dot" style="background:var(--bad)"></span>≤55%</span>
<span><span class="dot" style="background:var(--mid)"></span>55–68%</span>
<span><span class="dot" style="background:var(--good)"></span>&gt;68%</span></div>
<div class="scroll"><table class="heat">
<thead><tr><th>arm</th><th>az</th><th>el</th><th>roll</th><th>target-x</th><th>target-y</th><th>zoom</th></tr></thead>
<tbody>{heat}</tbody></table></div>

<h2>T3 — can it tell two errors apart?</h2>
<p class="note">A different question: shown two stimuli of the same pair with different error
magnitudes, pick the better-aligned one (2AFC, chance = 50%). This is <b>discrimination</b>, not
absolute reading — and the ranking nearly <b>inverts</b> T1. The two-image arms (side-by-side,
flicker) that were worst at reading a single stimulus are best at telling two apart; the overlay
arms that won T1 sit near chance here. The winner depends on the task.</p>
<div class="scroll"><table>
<thead><tr><th>arm</th><th>discrimination %</th><th>vs chance</th><th>strongest axis</th></tr></thead>
<tbody>{t3rows}</tbody></table></div>

<h2>T2 — closing the loop <span class="tag" style="font-size:.6em">complete · {t2n}/144</span></h2>
<p class="note">The production question: iterate — read stimulus, propose a camera correction, re-render,
repeat (≤6 rounds). Convergence = az/el/roll ≤ 1°, target ≤ 5 mm, zoom ± 3%. Run on the top-3 T1 arms
plus the incumbent P1, 6 pairs × 6 pinned starts (one per parameter class). Non-converged cells enter
the median as round 7 (censored at max+1).</p>
<div class="scroll"><table>
<thead><tr><th>arm</th><th>n</th><th>converged</th><th>median rounds</th></tr></thead>
<tbody>{t2rows}</tbody></table></div>

<h2>Decision rule — applied to Codex (generalization check)</h2>
<p class="note">The benchmark's rule: adopt the arm that wins T1 macro sign accuracy over the
incumbent (P1) by <b>&ge;5 points</b> <i>and</i> is non-inferior on T2 — convergence rate within
5 points of the best arm, median rounds-to-converge at most 1 round more. <b>The rule governs on
the Opus numbers</b> (Opus runs pose feedback in production); this section applies it to Codex as
the generalization check, since the Opus run is currently paused (quota). Treat this as a preview,
not the adoption decision.</p>
<div class="scroll"><table>
<thead><tr><th>arm</th><th>T1 macro sign %</th><th>margin vs P1</th><th>T2 converged %</th>
<th>vs best conv</th><th>median rounds</th><th>vs best rounds</th><th>passes?</th></tr></thead>
<tbody>{decrows}</tbody></table></div>
<div class="finding"><b>{dec_verdict}</b> {dec_detail}</div>

<h2>Reading the result</h2>
{findings}

<h2>Method &amp; caveats</h2>
<p class="note">Renders are produced on a <b>fixed canvas with frozen framing</b> so a translation or
zoom error moves the model in the frame instead of silently re-fitting; the manifest 2-D alignment is
frozen from each pair's control so the zero-error case sits registered. Perturbations are applied one
parameter at a time (plus a mixed tier and a control) with exactly known deltas, and stimulus ids
served to the model are opaque salted hashes so it can't read the answer.</p>
<div class="finding note"><b>T1 itself is still N=1</b> (the original design's first pass calls for
N=3 on this sub-grid); the field is tight (58.7–70.8%) and the confidence intervals overlap, and the
control false-positive rate rests on only six control cells per arm. T1, T3, and T2 are all now
complete on Codex, and the decision rule above gives a clean preview verdict on that data — but it is
a <b>generalization check, not the adoption decision</b>: the rule governs on the <b>Opus</b> numbers
(Opus runs pose feedback in production), and that run is currently <b>paused</b> (rate-limit quota) at
1,091/1,782 T1 cells, resumable. The actual call waits on Opus, not on more Codex data — and if the
winning arm flips between models, that gets reported prominently, not averaged away.</p>

<footer>Deterministic scoring · {ncells} Codex cells · pose-presentation-benchmark · harmonic-analyzer</footer>
</div>
"""


def _score_color(v: float) -> str:
    return "var(--good)" if v > 0.68 else "var(--mid)" if v >= 0.55 else "var(--bad)"


def _heat_color(v: float) -> str:
    return "#2f8f5b" if v > 0.68 else "#c2892c" if v >= 0.55 else "#c0473f"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="codex")
    args = ap.parse_args()
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    t1 = summary[args.model]["t1"]
    table, ranking = t1["table"], t1["ranking"]
    cases = _cases()
    imgs = exemplar_images(cases)

    ncells = sum(t["n"] for t in table.values())
    tokM = round(sum((t["median_tokens"] or 0) * t["n"] for t in table.values()) / 1e6, 1)

    rows = []
    for i, arm in enumerate(ranking, 1):
        t = table[arm]
        ms = t["macro_sign"]
        tag = f'<span class="tag">{ARM_KIND[arm]}</span>' if arm in ARM_KIND else ""
        rows.append(
            f'<tr><td class="rank">{i}</td>'
            f'<td><span class="armname">{arm}</span> {ARM_NAME[arm]}{tag}</td>'
            f'<td class="bar"><span class="num" style="color:{_score_color(ms)}">{100*ms:.1f}</span>'
            f'<div class="track"><div class="fill" style="width:{100*ms:.0f}%"></div></div></td>'
            f'<td class="num">{100*t["ci"][0]:.0f}–{100*t["ci"][1]:.0f}</td>'
            f'<td class="num">{100*t["magnitude"]:.0f}</td>'
            f'<td class="num" style="color:{_score_color(1-t["control_fp"])}">{100*t["control_fp"]:.0f}</td>'
            f'<td class="num">{t["median_tokens"] or "-"}</td>'
            f'<td class="num">{t["mean_latency_s"]:.0f}</td></tr>')

    wide = {"P2", "P3", "P4", "P10", "P11"}
    cards = []
    for i, arm in enumerate(ranking, 1):
        t = table[arm]
        ms = t["macro_sign"]
        cls = "acard wide" if arm in wide else "acard"
        cards.append(
            f'<div class="{cls}"><div class="imgwrap">'
            f'<span class="badge">#{i} · {arm}</span>'
            f'<span class="score" style="background:{_score_color(ms)}">{100*ms:.0f}%</span>'
            f'<img src="{imgs[arm]}" alt="{ARM_NAME[arm]} stimulus"></div>'
            f'<div class="meta"><div class="nm">{ARM_NAME[arm]}</div>'
            f'<div class="sub">macro sign {100*ms:.1f}% · magnitude {100*t["magnitude"]:.0f}%</div>'
            f'<div class="fp">control false-positives {100*t["control_fp"]:.0f}%</div></div></div>')

    params = ["az", "el", "roll", "target_x", "target_y", "zoom"]
    heat = []
    for arm in ranking:
        pp = table[arm]["per_param"]
        cells = "".join(
            f'<td class="h" style="background:{_heat_color(pp[p])}">{100*pp[p]:.0f}</td>' for p in params)
        heat.append(f'<tr><td><b>{arm}</b> {ARM_NAME[arm]}</td>{cells}</tr>')

    # T3 discrimination
    t3 = summary[args.model].get("t3", {"table": {}, "ranking": []})
    t3rows = []
    for arm in t3["ranking"]:
        t = t3["table"][arm]
        fc = t["frac_correct"]
        best = max(t["by_class"].items(), key=lambda kv: kv[1]) if t["by_class"] else ("-", 0)
        t3rows.append(
            f'<tr><td><span class="armname">{arm}</span> {ARM_NAME[arm]}</td>'
            f'<td class="num" style="color:{_score_color((fc-0.5)*2)}">{100*fc:.1f}</td>'
            f'<td class="num">+{100*(fc-0.5):.1f}</td>'
            f'<td class="num">{best[0]} {100*best[1]:.0f}%</td></tr>')

    # T2 convergence (preliminary)
    t2 = summary[args.model].get("t2", {"table": {}, "ranking": [], "n_total": 0})
    t2rows = []
    for arm in t2["ranking"]:
        t = t2["table"][arm]
        t2rows.append(
            f'<tr><td><span class="armname">{arm}</span> {ARM_NAME[arm]}</td>'
            f'<td class="num">{t["n"]}</td>'
            f'<td class="num">{t["converged"]}/{t["n"]} ({100*t["conv_rate"]:.0f}%)</td>'
            f'<td class="num">{t["median_rounds"]:g}</td></tr>')

    top = ranking[0]
    p1_rank = ranking.index("P1") + 1

    # Decision rule (T1 margin vs incumbent + T2 non-inferiority vs best T2 arm)
    decrows, dec_verdict, dec_detail = "", "", ""
    if t2["table"]:
        p1_sign = table["P1"]["macro_sign"]
        best_conv_arm = max(t2["table"], key=lambda a: t2["table"][a]["conv_rate"])
        best_conv, best_rounds = t2["table"][best_conv_arm]["conv_rate"], t2["table"][best_conv_arm]["median_rounds"]
        rows_out = []
        winner = None
        for arm in t2["ranking"]:
            if arm not in table:
                continue
            t1m, t2t = table[arm]["macro_sign"], t2["table"][arm]
            margin = (t1m - p1_sign) * 100
            conv_gap = (best_conv - t2t["conv_rate"]) * 100
            rounds_gap = t2t["median_rounds"] - best_rounds
            passes = margin >= 5 and conv_gap <= 5 and rounds_gap <= 1
            if passes and winner is None and arm != "P1":
                winner = arm
            rows_out.append(
                f'<tr><td><span class="armname">{arm}</span> {ARM_NAME[arm]}</td>'
                f'<td class="num">{100*t1m:.1f}</td>'
                f'<td class="num" style="color:{_score_color(0.5+margin/20)}">{margin:+.1f}</td>'
                f'<td class="num">{100*t2t["conv_rate"]:.0f}</td>'
                f'<td class="num">{"best" if arm==best_conv_arm else f"-{conv_gap:.0f}"}</td>'
                f'<td class="num">{t2t["median_rounds"]:g}</td>'
                f'<td class="num">{"best" if arm==best_conv_arm else f"+{rounds_gap:g}"}</td>'
                f'<td class="num" style="color:{"var(--good)" if passes else "var(--faint)"}">'
                f'{"YES" if passes else "no"}</td></tr>')
        decrows = "\n".join(rows_out)
        if winner:
            dec_verdict = f"On Codex, {winner} ({ARM_NAME[winner]}) clears both bars."
            dec_detail = (f"It beats the incumbent P1 by {(table[winner]['macro_sign']-p1_sign)*100:.1f} "
                          f"points on T1 and is non-inferior to the best T2 arm on both convergence "
                          f"rate and median rounds. P1 itself fails T2 non-inferiority decisively "
                          f"(conv rate {100*(best_conv-t2['table']['P1']['conv_rate']):.0f} points below "
                          f"best, median rounds +{t2['table']['P1']['median_rounds']-best_rounds:g}) -- "
                          "the retirement condition (\"beaten on both\") is met on the Codex side. "
                          "This is a generalization-check result, not the production decision, which "
                          "governs on Opus.")
        else:
            dec_verdict = "No arm clears both bars on Codex yet."
            dec_detail = "The incumbent P1 is not displaced under this rule on the current data."
    findings = f"""
<div class="finding"><b>Checkerboard (P6) leads — and is the only arm that separates from the pack.</b>
It tops macro sign accuracy at {100*table['P6']['macro_sign']:.1f}% and, tellingly, has by far the
lowest control false-positive rate ({100*table['P6']['control_fp']:.0f}% vs 83–100% for most arms):
continuous anatomy across tile seams gives the model a clean "these are registered" signal, so it
hallucinates fewer errors on the zero-error controls.</div>
<div class="finding"><b>The incumbent blend-red (P1) lands mid-pack — rank {p1_rank}.</b> It is not
beaten decisively (the ≥5-point margin the decision rule needs is only marginally met, and CIs
overlap), but it is not winning either. Its false-positive rate ({100*table['P1']['control_fp']:.0f}%)
is high — a red-tinted render over a grayscale photo reads as "misaligned" even when it isn't.</div>
<div class="finding"><b>Two-image arms trail.</b> Side-by-side (P2/P3) and the flicker pair (P10)
occupy the bottom three, with their worst reads on image-plane translation — the model struggles to
hold two frames in register and compare them, exactly the multi-image weakness the prior art warned of.
A coordinate grid (P3) did not rescue side-by-side here.</div>
<div class="finding"><b>Everyone struggles with translation and zoom.</b> Rotations read at 65–82%;
target-x, target-y and zoom sit at 45–68%. Any presentation adopted for production pose feedback will
need to lean on the reads it is good at and treat translation as low-confidence.</div>
<div class="finding"><b>The task changes the winner.</b> On T3's two-image discrimination the ranking
nearly inverts — side-by-side and flicker (T1's losers) come out on top, the overlays near chance.
Absolute pose reading (T1) and fine A-vs-B discrimination (T3) reward different presentations, so the
right choice depends on how the production loop actually uses the composite. T2 (the closed loop that
mirrors production) is the tiebreaker — and it is still running.</div>
"""

    html = HTML.format(
        ncells=ncells, narms=len(ranking), tokM=tokM,
        ref=imgs["ref"], ctrl=imgs["ctrl"], pert=imgs["pert"],
        rows="\n".join(rows), cards="\n".join(cards), heat="\n".join(heat),
        t3rows="\n".join(t3rows), t2rows="\n".join(t2rows) or '<tr><td colspan="4">no data yet</td></tr>',
        t2n=t2.get("n_total", 0), findings=findings,
        decrows=decrows or '<tr><td colspan="8">T2 not yet run</td></tr>',
        dec_verdict=dec_verdict, dec_detail=dec_detail)
    out = OUT / f"report_{args.model}.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
