# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Deterministic scorer + report for the pose-presentation benchmark.

No LLM judging: every metric is computed from results.jsonl against the known
per-case delta recorded on each row. Emits per-model markdown tables (T1 sign
accuracy macro-averaged over {-,0,+} per parameter class, magnitude buckets,
control false-positive rate, parameter confusion; T3 fraction-correct and 75%
threshold) plus a machine-readable summary.json and the per-model arm ranking
the decision rule consumes.

    uv run comparisons/bench/report.py                 # all models present
    uv run comparisons/bench/report.py --model codex
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parent
OUT = BENCH / "out"
RESULTS = OUT / "results.jsonl"
PARAMS = ["az", "el", "roll", "target_x", "target_y", "zoom"]
DKEY = {"az": "az_deg", "el": "el_deg", "roll": "roll_deg",
        "target_x": "tx_mm", "target_y": "ty_mm"}


def _sign(x: float) -> str:
    return "+" if x > 0 else "-" if x < 0 else "0"


def gt_dirs(delta: dict) -> dict:
    d = {p: _sign(delta.get(DKEY[p], 0)) for p in PARAMS if p != "zoom"}
    d["zoom"] = _sign(delta.get("zoom", 1.0) - 1.0)
    return d


def gt_bucket(param: str, delta: dict) -> str | None:
    if param == "zoom":
        return "large" if delta.get("zoom", 1.0) != 1.0 else None
    v = abs(delta.get(DKEY[param], 0))
    if v == 0:
        return None
    if param in ("az", "el", "roll"):
        return "small" if v <= 2 else "medium" if v <= 8 else "large"
    return "small" if v <= 8 else "medium" if v <= 25 else "large"


def load(task: str, model: str) -> list[dict]:
    if not RESULTS.exists():
        return []
    rows = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["task"] == task and r["model"] == model and r.get("response"):
            rows.append(r)
    return rows


def macro_sign_accuracy(rows: list[dict]) -> tuple[float, dict]:
    """Macro over {-,0,+} per parameter class, then mean over parameters.

    ~80% of labels are '0'; a plain mean lets an always-'0' arm score ~80%.
    The per-class macro forces the active signs to carry the score.
    """
    # per param -> per gt-class -> [correct bools]
    acc = {p: defaultdict(list) for p in PARAMS}
    for r in rows:
        gt = gt_dirs(r["delta"])
        for p in PARAMS:
            pred = r["response"].get(p, {}).get("direction")
            acc[p][gt[p]].append(1 if pred == gt[p] else 0)
    per_param = {}
    for p in PARAMS:
        classes = [sum(v) / len(v) for v in acc[p].values() if v]
        per_param[p] = sum(classes) / len(classes) if classes else float("nan")
    valid = [v for v in per_param.values() if v == v]
    return (sum(valid) / len(valid) if valid else float("nan")), per_param


def magnitude_accuracy(rows: list[dict]) -> float:
    hit = tot = 0
    for r in rows:
        for p in PARAMS:
            b = gt_bucket(p, r["delta"])
            if b is None:
                continue
            pred = r["response"].get(p, {}).get("magnitude")
            tot += 1
            hit += 1 if pred == b else 0
    return hit / tot if tot else float("nan")


def control_fp(rows: list[dict]) -> float:
    """Fraction of control cells where any parameter is read as non-zero."""
    ctrl = [r for r in rows if r["tier"] == "control"]
    if not ctrl:
        return float("nan")
    fp = sum(1 for r in ctrl
             if any(r["response"].get(p, {}).get("direction") != "0" for p in PARAMS))
    return fp / len(ctrl)


def confusion(rows: list[dict]) -> dict:
    """Single-parameter cells where the WRONG parameter was read non-zero."""
    conf = defaultdict(int)
    tot = defaultdict(int)
    for r in rows:
        if r["tier"] != "single":
            continue
        gt = gt_dirs(r["delta"])
        active = [p for p in PARAMS if gt[p] != "0"]
        if len(active) != 1:
            continue
        true_p = active[0]
        tot[true_p] += 1
        for p in PARAMS:
            if p != true_p and r["response"].get(p, {}).get("direction") != "0":
                conf[f"{true_p}->{p}"] += 1
    return {"leaks": dict(sorted(conf.items(), key=lambda x: -x[1])[:8]),
            "n_by_param": dict(tot)}


def bootstrap_ci(rows: list[dict], stat, n_boot: int = 400, seed: int = 0):
    """CI over PAIRS (temperature-0 repeats are near-duplicates — never resample them)."""
    by_pair = defaultdict(list)
    for r in rows:
        by_pair[r["pair_id"]].append(r)
    pairs = list(by_pair)
    if len(pairs) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        sample = []
        for _ in range(len(pairs)):
            sample.extend(by_pair[rng.choice(pairs)])
        v = stat(sample)
        if v == v:
            vals.append(v)
    if not vals:
        return (float("nan"), float("nan"))
    vals.sort()
    return (vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))])


def t1_report(model: str) -> dict:
    rows = load("t1", model)
    arms = sorted({r["arm"] for r in rows}, key=lambda a: int(a[1:]))
    table = {}
    for arm in arms:
        ar = [r for r in rows if r["arm"] == arm and not r.get("grid")]
        if not ar:
            continue
        macro, per_param = macro_sign_accuracy(ar)
        lo, hi = bootstrap_ci(ar, lambda rs: macro_sign_accuracy(rs)[0])
        toks = [r["tokens"] for r in ar if r["tokens"]]
        table[arm] = {
            "n": len(ar), "macro_sign": macro, "ci": [lo, hi],
            "per_param": per_param, "magnitude": magnitude_accuracy(ar),
            "control_fp": control_fp(ar), "confusion": confusion(ar),
            "median_tokens": sorted(toks)[len(toks) // 2] if toks else None,
            "mean_latency_s": round(sum(r["latency_s"] for r in ar) / len(ar), 1),
        }
    ranking = sorted(table, key=lambda a: (table[a]["macro_sign"] if table[a]["macro_sign"] == table[a]["macro_sign"] else -1), reverse=True)
    return {"table": table, "ranking": ranking}


def t3_report(model: str) -> dict:
    rows = load("t3", model)
    arms = sorted({r["arm"] for r in rows}, key=lambda a: int(a[1:]))
    table = {}
    for arm in arms:
        ar = [r for r in rows if r["arm"] == arm]
        by_class = defaultdict(list)
        for r in ar:
            correct = 1 if r["response"].get("choice") == r["correct"] else 0
            by_class[r["delta_class"]].append(correct)
        overall = [c for v in by_class.values() for c in v]
        table[arm] = {
            "n": len(ar),
            "frac_correct": sum(overall) / len(overall) if overall else float("nan"),
            "by_class": {k: round(sum(v) / len(v), 3) for k, v in sorted(by_class.items())},
        }
    ranking = sorted(table, key=lambda a: (table[a]["frac_correct"] if table[a]["frac_correct"] == table[a]["frac_correct"] else -1), reverse=True)
    return {"table": table, "ranking": ranking}


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    return s[len(s) // 2] if s else float("nan")


def t2_report(model: str) -> dict:
    """Closed-loop convergence per arm. Non-converged rounds censored at 7
    (max+1) so divergence can only lengthen a median, never shrink it."""
    rows = [r for r in load_raw("t2", model) if r.get("response") is not None]
    arms = sorted({r["arm"] for r in rows}, key=lambda a: int(a[1:]))
    table = {}
    for arm in arms:
        ar = [r for r in rows if r["arm"] == arm]
        conv = [r for r in ar if r["converged"]]
        rounds = [r["n_rounds"] if r["converged"] else 7 for r in ar]
        table[arm] = {
            "n": len(ar), "converged": len(conv),
            "conv_rate": len(conv) / len(ar) if ar else float("nan"),
            "median_rounds": _median(rounds),
            "median_final_rot": _median([max(r["final_err"]["az"], r["final_err"]["el"],
                                             r["final_err"]["roll"]) for r in ar]),
        }
    ranking = sorted(table, key=lambda a: (table[a]["conv_rate"], -table[a]["median_rounds"]),
                     reverse=True)
    return {"table": table, "ranking": ranking, "n_total": len(rows)}


def load_raw(task: str, model: str) -> list[dict]:
    if not RESULTS.exists():
        return []
    out = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["task"] == task and r["model"] == model:
            out.append(r)
    return out


def _fmt_pct(x) -> str:
    return f"{100*x:.1f}" if isinstance(x, float) and x == x else "-"


def markdown(model: str, t1: dict, t3: dict) -> str:
    L = [f"## Subject model: `{model}`\n", "### T1 - single-shot pose read\n",
         "| arm | n | macro sign % | 95% CI | magnitude % | control FP % | median tok | lat s |",
         "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for arm in t1["ranking"]:
        t = t1["table"][arm]
        ci = f"{_fmt_pct(t['ci'][0])} to {_fmt_pct(t['ci'][1])}"
        L.append(f"| {arm} | {t['n']} | **{_fmt_pct(t['macro_sign'])}** | {ci} | "
                 f"{_fmt_pct(t['magnitude'])} | {_fmt_pct(t['control_fp'])} | "
                 f"{t['median_tokens'] or '-'} | {t['mean_latency_s']} |")
    L.append("\n### T1 per-parameter macro sign %\n")
    L.append("| arm | " + " | ".join(PARAMS) + " |")
    L.append("|---|" + "|".join("--:" for _ in PARAMS) + "|")
    for arm in t1["ranking"]:
        pp = t1["table"][arm]["per_param"]
        L.append(f"| {arm} | " + " | ".join(_fmt_pct(pp[p]) for p in PARAMS) + " |")
    if t3["table"]:
        L.append("\n### T3 - 2AFC discrimination (fraction correct)\n")
        L.append("| arm | n | frac correct | by class |")
        L.append("|---|--:|--:|---|")
        for arm in t3["ranking"]:
            t = t3["table"][arm]
            bc = ", ".join(f"{k}:{v}" for k, v in t["by_class"].items())
            L.append(f"| {arm} | {t['n']} | {_fmt_pct(t['frac_correct'])} | {bc} |")
    L.append(f"\n**T1 arm ranking ({model}):** {' > '.join(t1['ranking'])}\n")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="codex|codex-sol|opus|opus-5|opus-5-tools (default: all present)")
    args = ap.parse_args()
    models = [args.model] if args.model else ["codex", "codex-sol", "opus", "opus-5", "opus-5-tools"]
    summary, md = {}, ["# Pose-presentation benchmark - results\n"]
    for model in models:
        t1 = t1_report(model)
        t3 = t3_report(model)
        t2 = t2_report(model)
        if not t1["table"] and not t3["table"] and not t2["table"]:
            continue
        summary[model] = {"t1": t1, "t3": t3, "t2": t2}
        md.append(markdown(model, t1, t3))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    report_md = OUT / "report.md"
    report_md.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\n-> {report_md}\n-> {OUT / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
