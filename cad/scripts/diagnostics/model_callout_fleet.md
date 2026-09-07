# Source-owned dimension callouts: fleet candidate

This extends the alignment candidate to the remaining 34 active recipes. The
retained inventory has 35 parts and 72 literal rows; 22 empty-only recipes stay
unchanged. Every row resolves to one named feature in its existing
`DRAWING_DIMENSIONS` contract. No geometry, tolerance, BASIC, PMI, save or rebuild
policy changes are included.

Each builder authors its shared spec map after dimension marking and before its
existing final save. Drawings only verify the imported text against the explicit
intended view and source model, including exact native owner/dimension identity.
The cone-tip-adjuster body callout keeps its original above-text lane. The shared
fastener path verifies only cone-pivot-screw's nonempty side map; empty maps do not
acquire a part-author dependency. There is no retired-setter alias.

## Offline evidence and deliberate contract changes

The imported `_model_callout_migration_inventory.py` fixture pins all original
values, f-string expressions, feature owners and lanes. It is test data, not a
second production value source. Importing the fixture enrolls its bytes in the
recipe gate's dependency closure.

The author/verifier tests were renamed to `test_model_dimension_callouts_drawing.py`
and the fleet tests use the same `_drawing.py` suffix. An explicit test checks that
`check:recipe` enrolls both exactly once, including the inventory dependency.

Three previously deliberate source-location assertions were revised with the
reviewer's approval: the connecting-rod BORE literal and pinion-cam f-string now
belong to their specs; the unused magnifying-vertical-rod `ROD_DIA` drawing export
is removed. Tests retain the exact values/expressions and assert that builder,
drawing and spec share the same map object. Existing geometry, limit, GD&T and
legacy setter assertions remain intact. The alignment-only author dependency test
now asserts the exact approved 35 consumers, not an open-ended subset.

The read-only AST comparison covers all 102 migrated builder/drawing/spec files
against the pre-fleet baseline, stripping only explicitly named callout map,
import, capture, author/verifier and cone-pivot metadata changes. It passes; all
other executable AST remains identical. The shared fastener integration is
separately exercised with exact source-before-factory and intended-view tests.

```powershell
uv run --no-sync python cad/scripts/diagnostics/check_model_callout_migration.py
uv run --no-sync python -m doit check:recipe check:graph check:config check:partiso
```

The AST checker requires the recorded baseline Git object (or an explicitly
supplied `--baseline`); it is not a Git-dependent pytest gate. The ordinary tests
use the committed inventory. The first broad offline run reported 5510 passes,
one skip and the two old literal-location failures above. After their approved
updates, focused checks passed; the actual enrolled gate is rerun on the frozen
candidate before handoff.

Frozen candidate `232250a2` then passed the actual combined command above:
`check:recipe` 5186 tests in 91.80 s (`run-kg86af8x`), `check:graph` 83 tests in
10.34 s (`run-zp0gc9lg`), `check:config` exit 0, and `check:partiso` four tests in
7.65 s (`run-a56cajtb`). The parent process exited 0. Receipts are retained under
`C:/src/ha-perf-model-callout-fleet/cad/out/reports/pytest-telemetry/`; the actual
recipe command enrolled both renamed callout test files. These are offline gates,
not native fleet acceptance or performance measurements.

## Cache impact and native acceptance still required

The author helper has exactly 35 part consumers. This fleet-only change affects
37 part closures: 34 migrated parts plus three unchanged parts that already import
changed geometry specs: cone-swing-platform, harmonic-base and platen-clip. This
is conservative whole-module invalidation, not new authoring in those parts.
Existing part-to-assembly execution-token propagation is unchanged.

No native run was made for this fleet candidate. The alignment source-author pilot
`datum-policy-k15laxv1/pilot.json` passed built/cold import and printed-text checks
(SHA-256 `c75c5eb53ccb2bc9480a4492d520801f3002885ce64dac19acbe97afd88a6b48`).
It supports the native author/import mechanism, not blanket acceptance of the
other 34 recipes. Production rebuilds, saved/cold source values and tolerances,
imported identity, layout and printed/visual checks remain mandatory. Diagnostics
that observed the old setter require their explicit verifier ABI migration;
historical tooling is not silently adapted.

### First production builders

The root's actual alignment-pinion part and drawing passed at `fdf1e84d`;
the native source/save and visual evidence is recorded in
[`alignment-source-save-boundaries.md`](../../docs/pipeline/alignment-source-save-boundaries.md).
This is distinct from the earlier diagnostic authoring of an owned source copy.

The actual cone-tip-adjuster builder passed at `2d5d4d4d`, including the original
above-text BodyProfile callout and below-text Cup callout. Its saved execution
token is `8e2ce51d8e7ca47f9ca5a8e5c743d1d6a0f0cd749e10195a54e2140117bf12f4`.
The cup/slot part render was visually inspected. Its drawing stopped before the
recipe, at the prepared-template visible-pixel-box check; no drawing callout
verification was reached. A production retry at `5448afab` repeated the exact
one-pixel-per-dimension mismatch, retained in
`cad/out/prepared-drawing-templates/pending-09f01092e507-vao_atut/receipt.json`
(SHA-256 `436ceb10b7fa52f0ef809576ba08bb18dd91ad6f980e1ded523ec11d4e54814d`).

The actual cone-pivot-screw builder passed at `c61655db`, adapter `25bc99b1`,
licensed PID 31860, remote cache off. Source SHA-256 and execution token both
equal `515019088b41d329b45f0487b9241123751ecac7d6c116481930ae9c45e89c36`.
Trace `0x03b6ad66aeedd08030f5543c0e2da971` records 95.660778 seconds for the
part task, including 2.131209 seconds authoring the ThreadTail callout. Its
slotted-head/shoulder/tail render was visually inspected. The subsequent drawing
also stopped before its shared-fastener recipe at the same template check:
`pending-09f01092e507-dn6v_vzy/receipt.json`, SHA-256
`e5ae56a4ad0ea4071d2f7308e71c2c348e8ce60b658bdf67e7fd8f6ff765f28d`.
The drawing task took 26.395381 seconds, trace
`0x7e1768d6bbf3294c9cf279d69a1ca52e`.

Both failing template receipts preserve the original visible rectangle
`[2216, 141, 3824, 995]` and verification rectangle `[2216, 141, 3823, 994]`,
with no cleanup error. These are successful source builders but failed drawing
tasks, not native acceptance of the above-text or shared-fastener import paths.
