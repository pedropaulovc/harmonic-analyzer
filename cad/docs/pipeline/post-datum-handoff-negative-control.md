# Post-datum footprint reuse: negative performance control

One ordered FRESH/REUSE pair on 2026-09-06 does **not** support adopting the
post-datum footprint handoff. Its complete changed phase was slower, despite
eight reused measurements. Keep this experiment in history, not as a production
default. This result does not invalidate the earlier, different
[callout-to-GTol handoff](drawing-layout-handoff-profile.md).

Both runs used frozen `0ee5978b885c46c494f5f5da4f264d78619ec1c5`, adapter
`e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`, and the owned rocker recipe pilot.
The only selected policy changed from `fresh` to `reuse_post_policy`. All 1,003
helper/config fingerprints, the actual imported adapter file bank, four original
source hashes and original recipe SHA matched exactly across runs. Unique owned
source/drawing names differed deliberately; neither run modified production
recipes or original CAD files.

## Non-overlapping timing comparison

| Observed phase | FRESH (s) | REUSE (s) |
| --- | ---: | ---: |
| Whole recipe | 62.566718 | 61.796635 |
| Whole layout, nested in recipe | 49.517531 | 48.916555 |
| Initial callout witness children, front + right | 3.324590 | 2.055412 |
| Complete changed phase: fresh initial witnesses / reuse handoff parent | 3.324590 | 5.469141 |
| Datum document policy, including both original full witnesses | 26.526332 | 26.775678 |
| Callout final witnesses | 3.314217 | 3.235576 |
| Whole packing phase | 10.721518 | 8.972241 |
| Packing measurement + final readback, nested in packing | 10.479937 | 8.739414 |

The REUSE parent includes registration, sealing, complete inventory/context
checks, the two initial-witness children and lifetime completion. **Do not add
its children again.** Children saved 1.269178 s, but handoff work outside them
cost 3.413729 s: the measured changed span envelope grew **2.144551 s**. FRESH
also makes a few unspanned view-kind queries; this is a span-envelope comparison,
not isolated CPU attribution. Neither policy skips native semantic/attachment/
value reads or any final witness. REUSE recorded/reused 8/8 footprints, made four
fresh initial measurements, and reached the required `exhausted` lifetime.

Whole recipe/layout decreased only 0.770083/0.600976 s. Unchanged packing alone
decreased 1.749277 s; project time outside its immediate child spans decreased
0.499245 s. These single-pair variations cannot be credited to footprint reuse.
There is no demonstrated net speedup, statistical estimate or conflict-rate
claim. The proposed optimization's additional COM guards outweighed its avoided
footprint work in the directly observed spans.

## Native outcome and limits

Both construction/layout/export paths passed. Across variants, complete captured
`built.annotations`, `built.layout`, `reopened.annotations` and `reopened.layout`
are exactly equal, without coordinate normalization. Their 5100-by-3300 RGB
production-preview PNGs are pixel-identical. Drawing semantic rows differ only
in three model paths and five qualified dimension names referring to the unique
owned source/drawing copies; numeric values, geometry signatures and other
captured semantic fields are equal. The separate before/after source inventories
differ across runs only in their three source-qualified dimension names.

Both complete pilots nevertheless **failed** the same cold-title acceptance:
three printed-title X observations moved **7.225209847092629 mm**. The rejected
paths are `Sheet1/DetailItem245` under `generic/texts/0/position/0`,
`measurement/text_runs/0/position/0` and `native/text_runs/0/position/0`. The complete
cold-comparison reports match, including all 187 accepted coordinate-roundoff
entries. No title exception was introduced. The later `source_reopened`
inventory gate was not reached after this rejection, so this is not a completed
source-reopen or whole-pilot success.

All four original source files remained byte-exact. Each owned source copy kept
SHA-256 `3bfb6da45b91e5a73b24c74baf81141899149e3c327aa943930baed3fba4d4a0`
at copy, after recipe, after close and final observation. Both ownership receipts
record initial/final native inventories `[]`, preservation and null cleanup
error. No handoff guard failed. The final fresh packing checks reported no forward
or reverse GTol collision in either run.

## Retained evidence

Paths below are relative to `C:/src/harmonic-analyzer/cad/out/reports/`.
These are local generated artifacts, not embedded copies of the native files.

| File | SHA-256 |
| --- | --- |
| `datum-policy-aciqu0sr/pilot.json` | `28384576050eed1956bd7ced4f3c87c55933e058530599c711315788cceb3618` |
| `datum-policy-aciqu0sr/ownership.json` | `2136401084e0f0a0cb6378fc840722938388e930ac5788b04242e82ab91fe84b` |
| `datum-policy-ndvkjmzp/pilot.json` | `1e3cb660fd98fe4c05d463753961fb7b5899293794f0638a57c96c8042bdae1d` |
| `datum-policy-ndvkjmzp/ownership.json` | `cec30f6767243468514e188d5dcef0f8d122c3d35d26347d887603edd5be5394` |

FRESH trace: `0x8077add95f819ab825b99725e8caeaa2`.
REUSE trace: `0x681c24c91640cf8b247b465195e2cca9`.
Both are in `telemetry/traces.jsonl`; reuse counters and final clearance receipts
are in the corresponding `telemetry/logs.jsonl` trace.

This PowerShell command is read-only and uses an existing project venv. It checks
shared input equality and extracts every immediate layout child, avoiding nested
double-counting; it also prints the two initial-witness child sums separately.

```powershell
@'
import hashlib, json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
root = Path('C:/src/harmonic-analyzer/cad/out/reports')
names = ('datum-policy-aciqu0sr', 'datum-policy-ndvkjmzp')
reports = [json.loads((root / n / 'pilot.json').read_text()) for n in names]
for key in ('candidate', 'helper_revision', 'helpers', 'imported_adapter',
            'sources_before', 'sources_after'):
    assert reports[0][key] == reports[1][key], key
ids = [p['trials'][0]['layout_calls'][0]['trace_id'] for p in reports]
banks = {tid: [] for tid in ids}
with (root / 'telemetry/traces.jsonl').open() as stream:
    for line in stream:
        if not any(tid in line for tid in ids):
            continue
        row = json.loads(line)
        banks[row['context']['trace_id']].append(row)
def seconds(row):
    return (datetime.fromisoformat(row['end_time']) -
            datetime.fromisoformat(row['start_time'])).total_seconds()
for name, report, tid in zip(names, reports, ids):
    trial, bank = report['trials'][0], banks[tid]
    parent = next(r for r in bank if r['name'] == 'drawing.project_native_layout')
    children = [r for r in bank if r['parent_id'] == parent['context']['span_id']]
    totals = defaultdict(float)
    for row in children:
        totals[row['name']] += seconds(row)
    totals['unspanned_project'] = seconds(parent) - sum(map(seconds, children))
    initial = sum(seconds(r) for r in bank
                  if r['name'] == 'drawing.callouts.initial_witness')
    print(name, report['status'], 'recipe', trial['recipe_seconds'],
          'layout', trial['layout_calls'][0]['seconds'], 'initial_children', initial)
    print(json.dumps(totals, indent=2))
    for file in ('pilot.json', 'ownership.json'):
        print(file, hashlib.sha256((root / name / file).read_bytes()).hexdigest())
'@ | uv run --no-project --python C:/src/harmonic-analyzer/.venv/Scripts/python.exe python -
```

## Re-running the historical native experiment

The selector and prototype are rejected for rollout and may be removed from
current HEAD. Reproduce **only from the frozen revision**, with its own checkout,
submodules and venv; do not revive the obsolete CLI on current production code:

```powershell
git worktree add --detach C:/src/ha-datum-handoff-repro 0ee5978b885c46c494f5f5da4f264d78619ec1c5
Set-Location C:/src/ha-datum-handoff-repro
git submodule update --init --recursive
uv sync --locked
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
```

Before either invocation, obtain the coordinated exclusive native seat and set
`HARMONIC_DIAGNOSTIC_SW_PID` to the confirmed already-running SolidWorks PID.
Do not launch/recover SolidWorks or reuse a remembered PID. The parent wrapper
takes the machine-global seat; never call `--worker` or set `HARMONIC_COM_SEAT`
yourself. The recorded source/guard directories below must still contain the
exact protected hashes; the historical pilot rejects replacements.

```powershell
uv run python cad/scripts/diagnostics/probe_datum_policy_recipes.py --candidate 0ee5978b885c46c494f5f5da4f264d78619ec1c5 --source-root C:/src/ha-perf-channel/cad/out/sldprt --guard-root C:/src/harmonic-analyzer/cad/out/sldprt --target rocker_arm --datum-initial-measurement fresh
uv run python cad/scripts/diagnostics/probe_datum_policy_recipes.py --candidate 0ee5978b885c46c494f5f5da4f264d78619ec1c5 --source-root C:/src/ha-perf-channel/cad/out/sldprt --guard-root C:/src/harmonic-analyzer/cad/out/sldprt --target rocker_arm --datum-initial-measurement reuse_post_policy
```

Each invocation owns new copies and keeps failure evidence. An exit code 1 is
expected for the recorded title defect, not permission to skip its assertion.
Check each receipt and cleanup outcome before granting the next native run.
