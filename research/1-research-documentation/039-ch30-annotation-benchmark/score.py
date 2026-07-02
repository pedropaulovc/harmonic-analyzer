"""Score benchmark runs against ground truth.

Usage: uv run python research/1-research-documentation/039-ch30-annotation-benchmark/score.py

Reference per image: ground_truth/<stem>.json if present (human, via groundtruth-app),
else ch30_annotated/final/<stem>.json (round-1 consensus, marked PROVISIONAL).
Writes results.json and results.md next to this script.
"""
import json
import math
import statistics
from pathlib import Path

BENCH = Path(__file__).parent
REPO = BENCH.parents[2]
GT = BENCH / "ground_truth"
CONSENSUS = REPO / "ch30_annotated" / "final"
RUNS = BENCH / "runs"

MODELS = ["fable", "opus", "sonnet", "haiku", "codex"]
STEMS = [f"page00{n}_img01" for n in range(2, 10)]
THRESHOLDS = (10, 25, 50)


def mirror_name(f):
    """Swap left<->right in an analyzer-corner name (the SPEC's ambiguous convention)."""
    if not f.startswith("analyzer_corner_"):
        return f
    if f.endswith("_left"):
        return f[:-5] + "_right"
    if f.endswith("_right"):
        return f[:-6] + "_left"
    return f


def maybe_mirror(ref_pts, run_pts):
    """Pick identity or a consistent left<->right relabel of the run's analyzer corners,
    whichever minimizes total distance on corners matched under both mappings."""
    mirrored = {mirror_name(f): xy for f, xy in run_pts.items()}
    def total(pts):
        ds = [math.dist(xy, pts[f]) for f, xy in ref_pts.items()
              if f.startswith("analyzer_corner_") and f in pts]
        return (sum(ds), -len(ds))
    if total(mirrored) < total(run_pts):
        return mirrored, True
    return run_pts, False


def load(path):
    return json.loads(path.read_text()) if path.exists() else None


def reference(stem):
    gt = load(GT / f"{stem}.json")
    if gt:
        return gt, "ground_truth"
    cons = load(CONSENSUS / f"{stem}.json")
    return cons, "consensus_provisional"


def score_model(model, normalize=False):
    rows, missing, mirrored_stems = [], [], []
    for stem in STEMS:
        ref, ref_kind = reference(stem)
        run = load(RUNS / model / f"{stem}.json")
        if ref is None:
            continue
        if run is None:
            missing.append(stem)
            continue
        ref_pts = {p["feature"]: (p["x"], p["y"]) for p in ref["points"]}
        ref_occ = {o["feature"] for o in ref.get("occluded", [])}
        run_pts = {p["feature"]: (p["x"], p["y"]) for p in run["points"]}
        run_occ = {o["feature"] for o in run.get("occluded", [])}
        if normalize:
            run_pts, swapped = maybe_mirror(ref_pts, run_pts)
            if swapped:
                run_occ = {mirror_name(f) for f in run_occ}
                mirrored_stems.append(stem)
        for f, (rx, ry) in ref_pts.items():
            if f in run_pts:
                d = math.dist((rx, ry), run_pts[f])
                rows.append({"stem": stem, "feature": f, "kind": "dist", "dist": d, "ref": ref_kind})
            else:
                rows.append({"stem": stem, "feature": f, "kind": "missed_visible",
                             "claimed_occluded": f in run_occ, "ref": ref_kind})
        for f in ref_occ:
            if f in run_pts:
                rows.append({"stem": stem, "feature": f, "kind": "false_visible", "ref": ref_kind})
            elif f in run_occ:
                rows.append({"stem": stem, "feature": f, "kind": "occluded_agree", "ref": ref_kind})
    dists = [r["dist"] for r in rows if r["kind"] == "dist"]
    n_vis = len([r for r in rows if r["kind"] in ("dist", "missed_visible")])
    summary = {
        "model": model,
        "images_missing": missing,
        "mirrored_corner_stems": mirrored_stems,
        "visible_features_in_ref": n_vis,
        "marked": len(dists),
        "missed_visible": len([r for r in rows if r["kind"] == "missed_visible"]),
        "false_visible": len([r for r in rows if r["kind"] == "false_visible"]),
        "occluded_agree": len([r for r in rows if r["kind"] == "occluded_agree"]),
        "mean_px": round(statistics.mean(dists), 1) if dists else None,
        "median_px": round(statistics.median(dists), 1) if dists else None,
        "p90_px": round(statistics.quantiles(dists, n=10)[8], 1) if len(dists) >= 10 else None,
        **{f"within_{t}px": len([d for d in dists if d <= t]) for t in THRESHOLDS},
    }
    return summary, rows


def table(results, key):
    lines = ["| model | marked/visible | missed | false-visible | occl-agree | mean px | median px | ≤10px | ≤25px | ≤50px |",
             "|-------|---------------|--------|---------------|-----------|---------|-----------|-------|-------|-------|"]
    order = sorted(MODELS, key=lambda m: results[key][m]["median_px"] or 9e9)
    for m in order:
        s = results[key][m]
        lines.append(f"| {m} | {s['marked']}/{s['visible_features_in_ref']} | {s['missed_visible']} | "
                     f"{s['false_visible']} | {s['occluded_agree']} | {s['mean_px']} | {s['median_px']} | "
                     f"{s['within_10px']} | {s['within_25px']} | {s['within_50px']} |")
    return lines


def main():
    ref_kinds = {stem: reference(stem)[1] for stem in STEMS}
    provisional = any(k != "ground_truth" for k in ref_kinds.values())
    results = {"reference": ref_kinds, "provisional": provisional,
               "models": {}, "models_normalized": {}, "detail": {}, "detail_normalized": {}}
    for m in MODELS:
        results["models"][m], results["detail"][m] = score_model(m)
        results["models_normalized"][m], results["detail_normalized"][m] = score_model(m, normalize=True)
    (BENCH / "results.json").write_text(json.dumps(results, indent=2))

    lines = ["# ch30 annotation benchmark — results", ""]
    if provisional:
        lines += ["> **PROVISIONAL** — some/all images scored against the round-1 consensus, not",
                  "> human ground truth. Run the groundtruth-app, drag the dots, save, re-run this.", ""]
    lines += ["## Convention-normalized (headline)",
              "",
              "Analyzer-corner names may apply ONE consistent left↔right relabel per image —",
              "SPEC's \"machine-relative\" left/right was ambiguous and models split between the",
              "machine's-own-left and viewer-facing-front conventions. This table scores dot",
              "PLACEMENT; the flips used are listed below the strict table.",
              ""]
    lines += table(results, "models_normalized")
    lines += ["", "## Strict labels", "",
              "Literal feature-name matching (a mirrored corner name scores as its ~800px",
              "distance to the opposite corner).", ""]
    lines += table(results, "models")
    flips = [f"- `{m}` corner names mirrored on: {', '.join(results['models_normalized'][m]['mirrored_corner_stems']) or '—'}"
             for m in MODELS]
    lines += ["", "### Left↔right flips applied in the normalized table", ""] + flips
    for m in MODELS:
        if results["models"][m]["images_missing"]:
            lines.append(f"\n- `{m}` missing runs: {', '.join(results['models'][m]['images_missing'])}")
    lines += ["",
              "> **pinion_center caveat:** every model marked SPEC v2's operational definition",
              "> (the small chain sprocket beside the large brass drive gear at platen level),",
              "> but the human ground truth places the pinion at a different part (the book's",
              "> ch25 pinion gear at the base), so all models carry a ~300–500px error on this",
              "> feature in most views. It reflects a SPEC/GT identity mismatch, not placement skill.",
              "",
              "Per-feature detail in `results.json`."]
    (BENCH / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
