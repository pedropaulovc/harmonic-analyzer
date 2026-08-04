# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Multi-model runner for the pose-presentation benchmark (cad/docs/pose-presentation-benchmark.md).

Fans out one fresh-context call per cell x subject model. Two Codex variants
(gpt-5.5 and gpt-5.6-sol, both high reasoning) via `codex exec` with
`--output-schema` structured output in a sandbox cwd; Claude Opus via
`claude -p --model opus` (explicit override) in the same sandbox. Deterministic
side/order schedules, opaque stimulus ids (the id->delta map stays here, never
served), N repeats, resumable (answered cells skipped), results appended to
results.jsonl tagged by model. Ground truth is recorded on each row for the
scorer but NEVER shown to a subject.

    uv run cad/comparisons/bench/run.py --task t1 --model codex               # T1, Codex gpt-5.5
    uv run cad/comparisons/bench/run.py --task t1 --model codex-sol           # T1, Codex gpt-5.6-sol
    uv run cad/comparisons/bench/run.py --task t1 --model codex-sol --limit 10 --arms P1,P2  # smoke
    uv run cad/comparisons/bench/run.py --task t3 --model codex-sol
    uv run cad/comparisons/bench/run.py --task t1 --model opus                # after codex
    uv run cad/comparisons/bench/run.py --task t1 --model opus-5              # pinned claude-opus-5 (Read-only)
    uv run cad/comparisons/bench/run.py --task t1 --model opus-5-tools        # side-probe: unrestricted tools

Resume is automatic: rerun the same command; done cells are skipped.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
import presentations as P  # noqa: E402
import gen_cases as gc  # noqa: E402  (bpy-free camera math: _apply, camera_axes)

OUT = BENCH / "out"
CASES = BENCH / "cases.jsonl"
RESULTS = OUT / "results.jsonl"
# The sandbox is the subject's cwd, so it must NOT sit inside the repo: from
# out/sandbox/<cell> a relative walk reaches cases.jsonl (the per-case delta =
# the answer key) and results.jsonl (prior rows), and the benchmark contract is
# that ground truth is never shown to a subject. No cell has ever read one (0
# non-jpg reads across 168 transcripts), but the isolation should not rest on
# the subject's good manners. An opaque temp root also means a relative escape
# finds nothing worth reading. Override with HARMONIC_BENCH_SANDBOX.
# ...and it is namespaced per CHECKOUT: a machine-global root would let two
# worktrees running the same cells (say one pinned to the archived v0.19/
# c8efcf1e assets and one on current assets) land on the same <sandbox_id> leaf
# and overwrite each other's stimulus while a subject is mid-read. The per-
# process collision guard cannot see across processes; distinct roots make it
# structurally impossible. The hash keeps the parent as opaque as the leaf.
SANDBOX_ROOT = Path(os.environ.get("HARMONIC_BENCH_SANDBOX")
                    or Path(tempfile.gettempdir())
                    / f"pose-bench-{sha256(str(BENCH).encode()).hexdigest()[:8]}")
# Harness generation. Rows are stamped with it and `done_keys` counts ONLY the
# current one: cell keys did not change across the fixes, so a seat still
# holding a gitignored results.jsonl from the pre-fix run (cwd leaking the
# delta, ambient CLAUDE.md in context) would otherwise resume as if those cells
# were done and publish the mixture. Bump this on any change to what a subject
# sees or is told.
HARNESS = "h2-safemode-opaque-cwd"
SCHEMA_DIR = OUT / "schemas"
SALT = "pose-bench-v1"
ARMS = P.ARMS

# T1 sub-grid tags (27/pair): rotations +-3/+-15, targets +-15/+-40, both zooms,
# first 4 mixed, control. Generation renders the FULL 45; the sub-grid is a view.
SUBGRID_TAGS = (
    [f"{p}{s}{v}" for p in ("az", "el", "roll") for s in ("+", "-") for v in (3, 15)]
    + [f"{p}{s}{v}" for p in ("tx", "ty") for s in ("+", "-") for v in (15, 40)]
    + ["zoom085", "zoom118", "mix1", "mix2", "mix3", "mix4", "ctrl"]
)

# T3 delta-pairs (8), all positive-signed, one direction per class.
T3_PAIRS = [
    ("az", "az+1", "az+3"), ("az", "az+3", "az+7"), ("az", "az+7", "az+15"),
    ("el", "el+3", "el+7"), ("roll", "roll+3", "roll+7"),
    ("ty", "ty+5", "ty+15"), ("ty", "ty+15", "ty+40"), ("tx", "tx+15", "tx+40"),
]

FIRST_PASS_PAIRS = [
    "harmonic_analyzer--ch30-p002-img01", "harmonic_analyzer--ch30-p007-img01",
    "harmonic_analyzer--ch12-p002-img09", "harmonic_analyzer--ch12-p001-img02",
    "harmonic_analyzer--ch17-p002-img06", "harmonic_analyzer--ch23-p004-img02",
]

# --- arm encodings (shared prompt fragment; describes the encoding only) ------
ARM_ENCODING = {
    "P1": "a single overlay: the reference photo in grayscale with the CAD render tinted RED on top. Where red edges sit off the grayscale photo edges, the pose is misaligned there.",
    "P2": "two images side by side: one is the reference photo, the other the CAD render (their left/right order is randomised).",
    "P3": "two images side by side (reference photo and CAD render, order randomised) with a labelled coordinate grid (columns 0-9, rows A-J) drawn over both to help you name where things sit.",
    "P4": "a 5-tile strip that cross-fades reference->render (opacity 100/0, 75/25, 50/50, 25/75, 0/100); drift between the ends shows the pose error.",
    "P5": "a subtle overlay: the reference photo (full colour texture visible) with the CAD render faintly superimposed.",
    "P6": "an 8x8 checkerboard alternating tiles of the reference photo and the CAD render; a registered pose reads continuous across tile seams, a misaligned one shows breaks at the seams.",
    "P7": "a colour fusion: the reference photo drives the GREEN channel and the CAD render drives MAGENTA (red+blue). Registered structure reads gray; misregistration shows green/magenta colour fringes on the side it drifted toward.",
    "P8": "a difference heatmap (bright = large photo-vs-render mismatch) with small reference and render thumbnails below.",
    "P9": "the reference photo (full colour) with the CAD render's edges drawn as thin RED lines on top; red edges away from the matching photo edge show the pose error there.",
    "P10": "two full-frame images shown in sequence: one reference photo and one CAD render (order randomised); compare them like a blink comparator.",
    "P11": "a dashboard: a small reference|render pair on top, and below it a green/magenta colour fusion and a red-edge overlay of the same pair.",
}

T1_CONVENTIONS = """You are estimating the CAMERA POSE ERROR of a CAD render.
The REFERENCE shows the correct pose of a mechanical model. The CAD RENDER was
produced from a camera perturbed from that correct pose. Estimate the
perturbation APPLIED TO THE RENDER (not the correction) for each of six
independent parameters, using this convention:
- az (azimuth/yaw, deg): + = camera orbited toward the object's RIGHT (you see
  more of its right side than the reference); - = toward its left.
- el (elevation/pitch, deg): + = camera moved UP (looking down more); - = down.
- roll (deg): + = render rotated CLOCKWISE vs the reference; - = anticlockwise.
- target_x (mm, image-plane): + = camera aim shifted right, so the MODEL appears
  shifted LEFT in the render vs the reference; - = model shifted right.
- target_y (mm): + = aim shifted up, so the MODEL appears shifted DOWN; - = up.
- zoom (factor): + = render zoomed IN (model larger than reference); - = out.
Magnitude buckets: rotations small<=2deg / medium 3-8 / large>8; targets
small<=8mm / medium 9-25 / large>25; zoom is always large. Use direction "0"
and magnitude "small" for a parameter with no detectable error."""

T3_CONVENTIONS = """You will judge which of two stimuli shows the CAD render in
BETTER alignment with the reference pose (smaller pose error). Answer with the
label of the better-aligned stimulus."""

# --- JSON schemas (codex --output-schema; opus parses the same shape) ---------
_PARAM = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "direction": {"type": "string", "enum": ["-", "0", "+"]},
        "magnitude": {"type": "string", "enum": ["small", "medium", "large"]},
    }, "required": ["direction", "magnitude"],
}
T1_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {p: _PARAM for p in ("az", "el", "roll", "target_x", "target_y", "zoom")},
    "required": ["az", "el", "roll", "target_x", "target_y", "zoom"],
}
T3_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"choice": {"type": "string", "enum": ["1", "2"]}},
    "required": ["choice"],
}

# T2 pinned starts (6/pair, one per parameter class). "M1" = the pair's mix1 delta.
T2_STARTS = [
    ("az7", {"az_deg": 7.0}), ("elm7", {"el_deg": -7.0}), ("roll7", {"roll_deg": 7.0}),
    ("zoom085", {"zoom": 0.85}), ("txp25", {"tx_mm": 25.0}), ("mix1", "M1"),
]
_T2P = ("az_deg", "el_deg", "roll_deg", "target_x_mm", "target_y_mm", "zoom_factor")
T2_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {k: {"type": "number"} for k in _T2P}, "required": list(_T2P),
}
T2_CONVENTIONS = """You are closing a camera-pose loop. The REFERENCE shows the
correct pose; the CAD RENDER is from a perturbed camera. Propose the CORRECTION
to APPLY to the render's camera to make it match the reference (not the error -
the corrective move):
- az_deg/el_deg/roll_deg: additive degrees (if the render is rotated +5deg az
  vs the reference, propose az_deg = -5).
- target_x_mm/target_y_mm: additive mm along the image right/up. target_x_mm +
  shifts the camera aim right, moving the MODEL LEFT in the frame; so if the
  model sits too far RIGHT, propose a POSITIVE target_x_mm.
- zoom_factor: multiplicative (>1 zooms in / enlarges the model, <1 zooms out);
  1.0 = no zoom change.
Use 0 for a parameter that needs no change. Aim to converge in as few rounds as
possible (az/el/roll within 1deg, target within 5mm, zoom within 3%)."""

_LOCK = threading.Lock()


def load_cases() -> dict:
    rows = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["case_id"]: r for r in rows}


def crc(*parts) -> int:
    return zlib.crc32(":".join(str(p) for p in parts).encode())


def opaque(*parts) -> str:
    return sha256((SALT + ":" + ":".join(str(p) for p in parts)).encode()).hexdigest()[:16]


def sandbox_id(cell, model: str) -> str:
    """The cell's opaque sandbox id -- MUST be unique per cell.

    Two cells sharing a sandbox share filenames, so sibling cells running
    concurrently overwrite each other's stimulus while a subject is reading it,
    and an answer gets scored against a delta the subject never saw. T3 is the
    trap: three `az` and two `ty` entries in T3_PAIRS share a dclass, so keying
    on the class collapses five cells into two directories (the same collision
    that bit `cell_key` in #257 -- see memory/bench-opus-run-setup.md). Key on
    the delta-PAIR. The MODEL is in the key too: the scored `opus-5` run and the
    `opus-5-tools` side-probe cover the same cells, so without it two concurrent
    invocations in one checkout share a leaf (the old cell_key-derived path
    carried the model for free). Stimulus filenames take the same id, for the
    same reason. Hashing keeps all of it opaque, so nothing here lands back in
    the subject's cwd. `check_sandbox_ids` enforces uniqueness at run start.
    """
    task = cell[0]
    if task == "t1":
        _t, cid, arm, rep, grid = cell
        return opaque("t1", model, cid, arm, rep, grid)
    if task == "t3":
        _t, pid, dclass, (c1, c2), arm, rep = cell
        return opaque("t3", model, pid, dclass, c1, c2, arm, rep)
    _t, pid, start_key, _sd, arm = cell
    return opaque("t2", model, pid, start_key, arm)


def check_sandbox_ids(cells, model: str) -> None:
    ids = [sandbox_id(c, model) for c in cells]
    if len(set(ids)) != len(ids):
        dup = next(i for i in ids if ids.count(i) > 1)
        clash = [c for c in cells if sandbox_id(c, model) == dup]
        raise SystemExit(f"xx sandbox id collision ({len(ids) - len(set(ids))} cells): "
                         f"{clash[:2]} -- sibling cells would overwrite each other's "
                         "stimulus mid-read")


def _sandbox(oid: str) -> Path:
    """The cell's cwd, named by its OPAQUE id -- never by the cell key.

    A subject sees its working directory (Claude Code puts it in the prompt
    context; asked, a probe cell quoted back
    `/tmp/pose-bench-sandbox/t1_opus-5_..._+az+3_P7_0_0`, read "az+3" out of it
    AND recognised the directory as an eval harness). Since a T1 cell key
    embeds the ground-truth delta tag, that path WAS the answer key. The opaque
    id is the same one the stimulus files already carry, so the cwd now leaks
    nothing the subject is not meant to see.
    """
    sb = SANDBOX_ROOT / oid
    sb.mkdir(parents=True, exist_ok=True)
    return sb


def done_keys() -> set:
    if not RESULTS.exists():
        return set()
    keys, stale = set(), 0
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        # A row from an older harness is NOT done: it answered a differently
        # posed question (see HARNESS). Cell keys are stable across generations,
        # so without this a stale local results.jsonl silently resumes as if the
        # contaminated cells were finished.
        if r.get("harness") != HARNESS:
            stale += 1
            continue
        if r.get("response") is not None:   # only successful cells count as done;
            keys.add(r["cell_key"])         # errored cells retry on rerun
    if stale:
        print(f"!! ignoring {stale} row(s) from an older harness generation "
              f"(current: {HARNESS}) -- those cells will be re-run", flush=True)
    return keys


def append_result(row: dict) -> None:
    with _LOCK:
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    # first balanced object
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except ValueError:
                    return None
    return None


def write_schema(name: str, schema: dict) -> Path:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    p = SCHEMA_DIR / f"{name}.json"
    p.write_text(json.dumps(schema), encoding="utf-8")
    return p


def run_codex(prompt: str, images: list[Path], schema_path: Path, sandbox: Path,
              codex_model: str = "gpt-5.5",
              timeout: int = 240) -> tuple[dict | None, int, str]:
    out_file = sandbox / "codex_out.json"
    # Prompt goes via STDIN, never as a positional: `-i FILE...` is variadic and
    # would otherwise swallow a trailing prompt arg as another image path.
    cmd = ["codex", "exec", "--model", codex_model,
           "-c", "model_reasoning_effort=high",
           "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
           "-C", str(sandbox), "-s", "read-only",
           "--output-schema", str(schema_path), "-o", str(out_file)]
    for im in images:
        cmd += ["-i", str(im)]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, 0, "timeout"
    tokens = 0
    m = re.search(r"tokens used[:\s]+([\d,]+)", proc.stdout + "\n" + proc.stderr)
    if m:
        tokens = int(m.group(1).replace(",", ""))
    data = None
    if out_file.exists():
        data = _extract_json(out_file.read_text(encoding="utf-8"))
    if data is None:
        data = _extract_json(proc.stdout)
    err = "" if data is not None else (proc.stderr[-400:] or "no-json")
    return data, tokens, err


def run_opus(prompt: str, images: list[Path], sandbox: Path,
             claude_model: str = "opus", allowed_tools: str | None = None,
             timeout: int = 240,
             hermetic: bool = False) -> tuple[dict | None, int, str, str]:
    imgs = ", ".join(f"./{im.name}" for im in images)
    full = (prompt + f"\n\nThe stimulus image(s) are in this directory: {imgs}. "
            "Use the Read tool to view each, then respond with ONLY the JSON object.")
    cmd = ["claude", "-p", "--model", claude_model, "--effort", "high",
           "--output-format", "json",
           "--permission-mode", "bypassPermissions"]
    if allowed_tools:
        # --tools sets the AVAILABLE built-in set (verified: the subject reports
        # Read as its only tool). --allowed-tools does NOT work here: it is a
        # no-prompt allow-list, so under bypassPermissions Bash still runs.
        # --strict-mcp-config drops the user's MCP servers, which would
        # otherwise re-open a scripting path. Both in `=` form, never a separate
        # arg: the flags are variadic and would swallow the trailing prompt
        # (same trap as codex's `-i`).
        cmd += [f"--tools={allowed_tools}", "--strict-mcp-config"]
    if hermetic:
        # Without this the cell inherits the seat's ambient config -- VERIFIED:
        # asked what it saw, a default cell quoted back both ~/.claude/CLAUDE.md
        # and the repo's own CLAUDE.md/AGENTS.md, so every subject was reading
        # the project's instructions alongside the stimulus. --safe-mode drops
        # CLAUDE.md, skills, plugins, hooks, MCP servers and custom agents while
        # leaving auth/model/tools/permissions normal (re-asked under it: NONE).
        # NOT --bare: it also skips keychain reads, so the CLI lands on
        # "Not logged in - please run /login".
        cmd.append("--safe-mode")
    cmd.append(full)
    try:
        proc = subprocess.run(cmd, cwd=str(sandbox), capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, 0, "timeout", ""
    model_id, text, tokens = "", "", 0
    try:
        obj = json.loads(proc.stdout)
        events = obj if isinstance(obj, list) else [obj]
        for e in events:
            if e.get("type") == "system" and e.get("model"):
                model_id = e["model"]
            if e.get("type") == "result":
                text = e.get("result", "")
                u = e.get("usage", {})
                tokens = u.get("input_tokens", 0) + u.get("output_tokens", 0)
            if not model_id and e.get("message", {}).get("model"):
                model_id = e["message"]["model"]
            # Third source, last: the result event's modelUsage is keyed by the
            # model that actually served the turn, so it survives a system event
            # that never arrives. (Measured on CLI 2.1.219 the system event is
            # always present -- 29/29 rows carried a model_id -- but the pinned
            # -model guard turns a missing id into a rejected cell, so it is
            # worth a belt-and-braces read rather than a stalled rerun.)
            if not model_id and e.get("type") == "result" and e.get("modelUsage"):
                model_id = next(iter(e["modelUsage"]), "")
    except ValueError:
        text = proc.stdout
    data = _extract_json(text)
    err = "" if data is not None else "no-json"
    return data, tokens, err, model_id


# Subject models tagged onto every result row and cell_key. Opus is the
# production pose agent; the two Codex variants are crossed generalization
# checks, both at high reasoning. Keying each cell by its --model id keeps the
# three subjects independently resumable and lets a future run reproduce any one
# exactly from the recorded model_id -- add a variant here (+ argparse choices)
# and it is a fully-crossed subject with no other change.
CODEX_MODELS = {
    "codex": "gpt-5.5",          # incumbent second subject
    "codex-sol": "gpt-5.6-sol",  # added subject
}
# Subjects whose committed archives were collected under the pre-fix harness.
ARCHIVED_SUBJECTS = ("codex", "codex-sol", "opus")
# Claude subjects, all at --effort high. The alias "opus" floats with whatever
# `claude --model opus` resolves to on the day (it recorded claude-opus-4-8 for
# the archived column), so a NEW generation gets its own pinned id rather than
# silently reusing that key -- the recorded model_id on each row is what makes a
# column reproducible.
#
# `tools` is the --allowed-tools value, and it is load-bearing: this benchmark
# measures how well a PRESENTATION conveys pose error to a reader who LOOKS at
# it. Left unrestricted, claude-opus-5 answers ~6 cells in 7 by shelling out to
# numpy/PIL (venv + pip install included) to compute the misregistration
# numerically -- which scores a different question (every arm collapses to the
# same pixel math) and costs 10+ min/cell against ~30 s for a visual read. So
# the scored subject is pinned to Read; `opus-5-tools` keeps the unrestricted
# path as a side-probe that MEASURES that gap instead of assuming it.
CLAUDE_MODELS = {
    "opus": {"model": "opus", "tools": None, "timeout": 240, "hermetic": False},
    # 420 s, not the archived 240: a Read-only claude-opus-5 cell measured
    # 20-152 s at concurrency 8, so 240 would truncate the slow tail under
    # concurrency 16 and bias the column toward whatever answers fast.
    "opus-5": {"model": "claude-opus-5", "tools": "Read", "timeout": 420,
               "hermetic": True},
    "opus-5-tools": {"model": "claude-opus-5", "tools": None, "timeout": 900,
                     "hermetic": True},
}


def invoke(model: str, prompt: str, images: list[Path], schema: dict, sandbox: Path):
    if model in CODEX_MODELS:
        sp = write_schema("t_" + opaque(prompt)[:8], schema)
        data, tokens, err = run_codex(prompt, images, sp, sandbox, CODEX_MODELS[model])
        return data, tokens, err, CODEX_MODELS[model]
    spec = CLAUDE_MODELS[model]
    data, tokens, err, mid = run_opus(prompt, images, sandbox, spec["model"],
                                      spec["tools"], spec["timeout"],
                                      spec["hermetic"])
    # A pinned column must contain ONLY that model. `report.py` groups by the
    # subject key, not by model_id, so an automatic model switch or a configured
    # fallback would silently seat a different model in the opus-5 column under
    # a cell_key that then counts as done. Reject the row instead: response=None
    # makes done_keys() retry the cell on the next pass. Only checked for a
    # concrete id -- the archived "opus" spec is an alias by design.
    if data is not None and spec["model"].startswith("claude-") and mid != spec["model"]:
        return None, tokens, f"model-mismatch:{mid or 'unknown'}", mid
    return data, tokens, err, mid


# --- cell builders -----------------------------------------------------------
def t1_cells(cases, pairs, arms, n, grid):
    for pid in pairs:
        for tag in SUBGRID_TAGS:
            cid = f"{pid}+{tag}"
            if cid not in cases:
                continue
            for arm in arms:
                for rep in range(n):
                    yield ("t1", cid, arm, rep, grid)


def t3_cells(cases, pairs, arms, n):
    for pid in pairs:
        for dclass, t1, t2 in T3_PAIRS:
            c1, c2 = f"{pid}+{t1}", f"{pid}+{t2}"
            if c1 not in cases or c2 not in cases:
                continue
            for arm in arms:
                for rep in range(n):
                    yield ("t3", pid, dclass, (c1, c2), arm, rep)


def t3_key(model, cell) -> str:
    # cell = ("t3", pid, dclass, (c1, c2), arm, rep). The key discriminates on the
    # DELTA-PAIR tag (c1's "az+1"/"az+3"/... suffix), NOT dclass alone -- three az
    # and two ty pairs share a dclass, so keying on dclass would collide them and a
    # resumable --limit run would drop the graded-difficulty pairs (see report).
    _t, pid, _dclass, (c1, _c2), arm, rep = cell
    return f"t3:{model}:{pid}:{c1.split('+', 1)[1]}:{arm}:{rep}"


def exec_t1(cases, cell, model):
    _t, cid, arm, rep, grid = cell
    row = cases[cid]
    cell_key = f"t1:{model}:{cid}:{arm}:{rep}:{int(grid)}"
    side = crc(cid, arm) + rep
    oid = opaque("t1", model, cid, arm, rep, grid)
    sb = _sandbox(sandbox_id(cell, model))
    imgs = P.build_stimulus(row, arm, sb, oid, grid=grid, side=side % 2, order=side % 2)
    prompt = (T1_CONVENTIONS + f"\n\nThe stimulus is {ARM_ENCODING[arm]}\n\n"
              "Return a JSON object with keys az, el, roll, target_x, target_y, zoom, "
              "each an object {\"direction\": \"-\"|\"0\"|\"+\", \"magnitude\": "
              "\"small\"|\"medium\"|\"large\"}.")
    t0 = time.monotonic()
    data, tokens, err, mid = invoke(model, prompt, imgs, T1_SCHEMA, sb)
    return {
        "task": "t1", "cell_key": cell_key, "harness": HARNESS,
        "model": model, "model_id": mid,
        "case_id": cid, "pair_id": row["pair_id"], "arm": arm, "repeat": rep,
        "grid": grid, "side": side % 2, "tier": row["tier"], "delta": row["delta"],
        "response": data, "tokens": tokens, "error": err,
        "latency_s": round(time.monotonic() - t0, 1),
    }


def exec_t3(cases, cell, model):
    _t, pid, dclass, (c1, c2), arm, rep = cell
    cell_key = t3_key(model, cell)
    # opaque cwd -- a t3 cell key names the delta-pair tag (the answer)
    sb = _sandbox(sandbox_id(cell, model))
    order = (crc(pid, arm, "t3", dclass) + rep) % 2   # which delta is shown first
    side = crc(pid, arm) % 2                          # arm-internal layout (base-pair keyed)
    first_cid, second_cid = (c1, c2) if order == 0 else (c2, c1)
    imgs = []
    for slot, cid in (("1", first_cid), ("2", second_cid)):
        # c1/c2 in the id: sibling pairs share a dclass, so omitting them
        # collides the stimulus filenames as well as the sandbox.
        oid = opaque("t3", model, pid, dclass, c1, c2, arm, rep, slot)
        for im in P.build_stimulus(cases[cid], arm, sb, oid, grid=False, side=side, order=side):
            imgs.append(im)
    # correct answer: the smaller-delta case (c1) = better aligned
    correct = "1" if first_cid == c1 else "2"
    prompt = (T3_CONVENTIONS + f"\n\nEach stimulus is {ARM_ENCODING[arm]}\n\n"
              f"Stimulus 1 = {imgs[0].name if len(imgs)<=2 else 'the first image(s)'}, "
              f"Stimulus 2 = the remaining image(s). Which stimulus shows BETTER "
              "alignment (smaller pose error)? Return JSON {\"choice\": \"1\"|\"2\"}.")
    t0 = time.monotonic()
    data, tokens, err, mid = invoke(model, prompt, imgs, T3_SCHEMA, sb)
    return {
        "task": "t3", "cell_key": cell_key, "harness": HARNESS,
        "model": model, "model_id": mid,
        "pair_id": pid, "delta_class": dclass, "arm": arm, "repeat": rep,
        "order": order, "side": side, "correct": correct,
        "response": data, "tokens": tokens, "error": err,
        "latency_s": round(time.monotonic() - t0, 1),
    }


# --- T2 closed loop ----------------------------------------------------------
# A model-proposed correction is untrusted input: an extreme, NaN, or negative
# value (e.g. zoom_factor=0 or 1e9) can degenerate the camera (zero/huge
# ortho_scale, near-infinite target) and pathologically stall Blender's
# rasterizer -- which then wedges the ONE shared render server every other T2
# loop queues behind. Clamp every field to a generous-but-finite range instead
# of trusting the schema alone (a JSON Schema "number" has no magnitude bound).
_CORR_BOUNDS = {"az_deg": 90.0, "el_deg": 90.0, "roll_deg": 90.0,
               "target_x_mm": 500.0, "target_y_mm": 500.0}


def _safe_num(v, bound: float, default: float = 0.0) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(v):
        return default
    return max(-bound, min(bound, v))


def _apply_correction(cur: dict, corr: dict, r0, u0) -> dict:
    nc = json.loads(json.dumps(cur))
    nc["az_deg"] = cur["az_deg"] + _safe_num(corr.get("az_deg"), _CORR_BOUNDS["az_deg"])
    nc["el_deg"] = cur["el_deg"] + _safe_num(corr.get("el_deg"), _CORR_BOUNDS["el_deg"])
    nc["roll_deg"] = cur["roll_deg"] + _safe_num(corr.get("roll_deg"), _CORR_BOUNDS["roll_deg"])
    tx = _safe_num(corr.get("target_x_mm"), _CORR_BOUNDS["target_x_mm"])
    ty = _safe_num(corr.get("target_y_mm"), _CORR_BOUNDS["target_y_mm"])
    nc["target_mm"] = [cur["target_mm"][i] + tx * r0[i] + ty * u0[i] for i in range(3)]
    zf = _safe_num(corr.get("zoom_factor"), 8.0, default=1.0)
    zf = zf if 0.1 <= zf <= 8.0 else 1.0   # non-finite/absurd/degenerate -> no-op
    nc["zoom"] = max(0.05, min(50.0, cur["zoom"] * zf))
    return nc


def _pose_err(cur: dict, base: dict, target0, zoom0: float) -> dict:
    return {
        "az": abs(cur["az_deg"] - base["az_deg"]),
        "el": abs(cur["el_deg"] - base["el_deg"]),
        "roll": abs(cur["roll_deg"] - base["roll_deg"]),
        "target": math.dist(cur["target_mm"], target0),
        "zoom": abs(math.log(cur["zoom"] / zoom0)),
    }


def _converged(e: dict) -> bool:
    return (e["az"] <= 1 and e["el"] <= 1 and e["roll"] <= 1
            and e["target"] <= 5 and e["zoom"] <= math.log(1.03))


def t2_cells(cases, pairs, arms):
    for pid in pairs:
        if f"{pid}+ctrl" not in cases:
            continue
        for start_key, start_delta in T2_STARTS:
            for arm in arms:
                yield ("t2", pid, start_key, start_delta, arm)


def exec_t2(cases, cell, model, server):
    _t, pid, start_key, start_delta, arm = cell
    meta = cases[f"{pid}+ctrl"]
    base = meta["base_camera"]
    target0 = tuple(meta["target0"])
    zoom0 = float(meta.get("zoom0") or base.get("zoom") or 1.0)
    r0, u0 = tuple(meta["basis"]["r"]), tuple(meta["basis"]["u"])
    frozen = {"need_w": meta["frozen"]["need_w"]}
    w, h = meta["frozen"]["canvas"]
    bg, align = meta.get("background", "black"), meta.get("align") or {}
    cell_key = f"t2:{model}:{pid}:{start_key}:{arm}"
    # opaque cwd -- a t2 cell key names the starting perturbation
    sb = _sandbox(sandbox_id(cell, model))
    sd = cases[f"{pid}+mix1"]["delta"] if start_delta == "M1" else start_delta
    cur = gc._apply(base, target0, r0, u0, sd, zoom0)
    row_syn = {"pair_id": pid, "case_id": f"{pid}+ctrl", "align": align, "background": bg}
    side = crc(pid, arm) % 2
    rounds, history, converged, mid, err_break = [], [], False, "", ""
    for rnd in range(6):
        ren = server.render_jpg(cur, w, h, frozen, bg, sb / f"round{rnd}.jpg")
        oid = opaque("t2", model, pid, start_key, arm, rnd)
        imgs = P.build_stimulus(row_syn, arm, sb, oid, grid=False, side=side, order=side,
                                render_path=ren)
        hist = ("\n\nPrior rounds (text only, images not reshown):\n" + "\n".join(history)) \
            if history else ""
        prompt = (T2_CONVENTIONS + f"\n\nThe stimulus is {ARM_ENCODING[arm]}" + hist +
                  "\n\nReturn a JSON object with numeric keys az_deg, el_deg, roll_deg, "
                  "target_x_mm, target_y_mm, zoom_factor.")
        data, tokens, err, mid = invoke(model, prompt, imgs, T2_SCHEMA, sb)
        e_before = _pose_err(cur, base, target0, zoom0)
        if data is None:
            rounds.append({"round": rnd, "error": err, "err_before": e_before})
            err_break = err or "round-error"
            break
        rounds.append({"round": rnd, "correction": data, "err_before": e_before,
                       "tokens": tokens})
        history.append(f"Round {rnd + 1}: applied {json.dumps(data)}")
        cur = _apply_correction(cur, data, r0, u0)
        if _converged(_pose_err(cur, base, target0, zoom0)):
            converged = True
            break
    # response=None on an error-break so done_keys retries the cell (a genuine
    # non-converged loop that ran its rounds keeps response=rounds and counts done).
    return {
        "task": "t2", "cell_key": cell_key, "harness": HARNESS,
        "model": model, "model_id": mid,
        "pair_id": pid, "start": start_key, "arm": arm,
        "response": None if err_break else rounds, "error": err_break,
        "rounds": rounds, "n_rounds": len(rounds), "converged": converged,
        "final_err": _pose_err(cur, base, target0, zoom0),
        "tokens": sum(r.get("tokens", 0) or 0 for r in rounds),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=["t1", "t3", "t2"])
    ap.add_argument("--model", required=True,
                    choices=["codex", "codex-sol", "opus", "opus-5", "opus-5-tools"])
    ap.add_argument("--arms", help="comma list, default all 11")
    ap.add_argument("--pairs", help="comma list, default 6 first-pass")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--grid", action="store_true", help="grid-ON variant (T1)")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--limit", type=int, help="cap cells (smoke)")
    ap.add_argument("--budget-tokens", type=int, default=16_000_000)
    ap.add_argument("--allow-archived-subject", action="store_true",
                    help="run a FROZEN archived subject under the current harness")
    args = ap.parse_args()

    # The archived columns were collected under a harness that no longer exists
    # here: their cells ran with the seat's CLAUDE.md/AGENTS.md in context and
    # with a repo-local, cell-key-named cwd (i.e. the delta tag was visible in
    # the working directory). Both are now fixed, so resuming one of those
    # unfinished columns -- `opus` is only 770/1584 on T3 with T2 unstarted --
    # would silently append rows from a DIFFERENT harness under the same cell
    # keys and publish the mixture as one column. Refuse by default.
    if args.model in ARCHIVED_SUBJECTS and not args.allow_archived_subject:
        print(f"xx `{args.model}` is a FROZEN archived subject: its rows predate the "
              "--safe-mode + opaque-sandbox fixes, so resuming it here would mix two "
              "harnesses under one cell key. Start a new subject id instead (as "
              "`opus-5` did), or pass --allow-archived-subject if you accept the mix.",
              flush=True)
        return 2

    cases = load_cases()
    arms = args.arms.split(",") if args.arms else ARMS
    pairs = args.pairs.split(",") if args.pairs else FIRST_PASS_PAIRS
    SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    server = None
    if args.task == "t1":
        cells = list(t1_cells(cases, pairs, arms, args.n, args.grid))
        runner = exec_t1
    elif args.task == "t3":
        cells = list(t3_cells(cases, pairs, arms, args.n))
        runner = exec_t3
    else:  # t2 needs a persistent blender render server (one per run)
        cells = list(t2_cells(cases, pairs, arms))
        from render_server import RenderServer
        print("t2: starting persistent blender render server ...", flush=True)
        server = RenderServer()
        runner = lambda cs, c, m: exec_t2(cs, c, m, server)  # noqa: E731

    check_sandbox_ids(cells, args.model)
    done = done_keys()
    todo = []
    for c in cells:
        if args.task == "t1":
            key = f"t1:{args.model}:{c[1]}:{c[2]}:{c[3]}:{int(c[4])}"
        elif args.task == "t3":
            key = t3_key(args.model, c)
        else:
            key = f"t2:{args.model}:{c[1]}:{c[2]}:{c[4]}"
        if key not in done:
            todo.append(c)
    n_done = len(cells) - len(todo)
    if args.limit:
        todo = todo[:args.limit]
    print(f"{args.task}/{args.model}: {len(cells)} cells, {n_done} already done, "
          f"{len(todo)} to run now (concurrency {args.concurrency})", flush=True)

    spent = 0
    completed = 0
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(runner, cases, c, args.model): c for c in todo}
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  xx cell failed: {e}", flush=True)
                continue
            append_result(row)
            # codex suppresses its "tokens used" summary under --output-schema, so
            # fall back to a measured ~18k/cell estimate to keep the budget gate live.
            spent += (row.get("tokens") or 0) or 18000
            completed += 1
            ok = row.get("response") is not None
            if completed % 10 == 0 or not ok:
                rate = completed / max(1e-9, time.monotonic() - t0)
                print(f"  [{completed}/{len(todo)}] {row['cell_key']} "
                      f"{'OK' if ok else 'ERR:' + row.get('error','')} "
                      f"tok~{spent} {rate:.2f}/s", flush=True)
            if spent > args.budget_tokens:
                print(f"!! budget gate hit ({spent} > {args.budget_tokens}); stopping", flush=True)
                break
    if server is not None:
        server.close()
    print(f"done: {completed} cells, ~{spent} tokens, {time.monotonic()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
