---
name: farm-debug-leaf
description: Dispatch one task to the farm instead of a build (`./build <target> --leaf-timeout N`), read the leaf's own published log rather than the submitter console, and drain the worker to hold it for inspection — the budget is part of the workflow id, so re-dispatching with a different timeout starts a new run instead of joining the live one
metadata:
  type: project
---

A debug run on the farm is just a narrower closure — any farm-dispatchable task is a valid
target, so nothing special is needed to exercise one leaf:

```
./build part:fulcrum_keeper --leaf-timeout 90
./build assembly:drive_train
```

`build.py` takes `--leaf-timeout MINUTES` and passes every other argument through to doit
(`parse_known_args`), so targets and doit flags compose normally.

## Watch and steer it from the pool checkout

```powershell
uv run --frozen python farm.py workers                 # pollers, idle/busy, queue depth
uv run --frozen python farm.py status  <workflow-id>
uv run --frozen python farm.py logs    <workflow-id>   # that leaf's PUBLISHED log
uv run --frozen python farm.py capture <worker-id>     # desktop frame + recent log lines
uv run --frozen python farm.py cancel  <workflow-id>
```

**Read the leaf's own log, not the submitter's console.** The worker ships its task log to
the results container; the submitter only sees the dispatch outcome. `capture` is the right
tool when the symptom might be visual — a modal dialog or a wedged seat is invisible in a log
and obvious in a frame.

## The budget is part of the workflow id

Concurrent submitters of the same cache key **and budget** attach to the same `BuildLeaf` run.
The budget is in the id because Temporal cannot widen a running execution's timeout — so
re-dispatching the same target with a different `--leaf-timeout` starts a *new* run rather
than joining the one already in flight. Decide the budget before dispatching.

## Hold a worker instead of racing for it

```powershell
uv run --frozen python farm.py drain   <worker-id> --reason 'debugging #NN'
uv run --frozen python farm.py undrain <worker-id>
```

A drain stops new leaves and lets the in-flight one finish (the poller is what stops; the
activity is not cancelled). `undrain` refuses unless that worker's own seat report is younger
than 120 s and reads `ready`, so dispatch cannot resume to a session nobody restored.

## Check the cache before blaming the farm

`doit cache_status` answers "why did this miss?" with no seat, no worker and no `.doit.db`
contention, and `cad/out/reports/cache.jsonl` is safe to read *while* a build runs. An
unexpected dispatch is almost always one dep digest that moved, not the farm misbehaving.

## What the farm will not run

`gallery` needs Blender and no worker has it; `cache_status` is a local diagnostic. Both are
refused by the pool's admission allowlist, not merely skipped by the recipe. The
SolidWorks-free `check:*` gates are *admissible* on a worker but are **never dispatched** —
they route through `_run_stamped`/`_run`, never `_cached_com_action` — so they always run on
the submitter. Do not confuse the pool's admission list with what this recipe dispatches;
they are different questions and a reviewer has already conflated them once.
