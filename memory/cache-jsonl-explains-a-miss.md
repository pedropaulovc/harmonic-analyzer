---
name: cache-jsonl-explains-a-miss
description: "Diff two restore_miss events in cache.jsonl to pin exactly which dep shifted a cache key — works mid-build, unlike doit cache_status"
metadata:
  node_type: memory
  type: project
---

To answer "why did this task miss the cache?", **diff the `inputs` of two
`restore_miss` events in `cad/out/reports/cache.jsonl`** — each event carries the
task's FULL per-dep digest list (138 entries for an assembly), so comparing the
event under the old key with the one under the new key names the changed dep
exactly.

```python
evs = [e for e in map(json.loads, open("cad/out/reports/cache.jsonl"))
       if e.get("label") == "assembly:paper_drive" and "inputs" in e]
last = evs[-1]
prev = next(e for e in reversed(evs[:-1]) if e["key"] != last["key"])
a = {i["path"]: i["digest"] for i in prev["inputs"]}
b = {i["path"]: i["digest"] for i in last["inputs"]}
# report paths where a[p] != b[p]
```

**Why:** two traps make the obvious approaches worse.
1. **`store` events carry NO `inputs` key** — only `restore_miss`/`restore_hit` do.
   Diffing the two `store`s (the intuitive pick, since a store marks a completed
   build) raises `KeyError: 'inputs'`. Always filter on `"inputs" in e`.
2. **`doit cache_status` opens `.doit.db`**, which a running build is actively
   writing. `cache.jsonl` is an append-only log, so reading it is safe **while the
   build is still running** — no waiting, no ledger risk. Reach for it FIRST;
   `cache_status` is for when no build is in flight.

**How to apply:** when a task rebuilds unexpectedly, do NOT reason from "which
parts does this assembly insert?" — that answers a different question. A cache
key folds in the **transitive source closure** of the build script, so an
assembly legitimately rebuilds on edits to scripts whose parts it never inserts.
Observed 2026-07-26: `assembly:paper_drive` missed on six changed inputs, all of
them *source scripts* (`build_harmonic_base.py`, `harmonic_base_spec.py`, …) and
**not one an execution token** — reached via
`build_paper_drive_assembly.py:434 → from build_drive_train_assembly import
X_CRANK, Y_CRANK`. Guessing "child execution tokens" was wrong; the log said
otherwise in one query. See [[exact-cad-identity-cache]], [[com-seat-lock]].
