# Assembly granularity integration evidence

This run follows `second-vm-assembly-granularity-integration.md` at
`29c6ec1eea9456cc7403cab8e5e6c3fb4df02979`. Validation is in progress;
no historical #677 timing or native artifact is used as new acceptance.
VM1 owns integration and merging. Portfolio status belongs on the
[project board](https://github.com/users/pedropaulovc/projects/1).

## Inputs and extraction

- Main: `c6ab57dbdf73a733b32fb580bada81dab7fd758c`, re-fetched before baseline.
- Adapter: `2269009ed56712867826516f4406afc98a0c2814`, unchanged from main.
- Parser branch: `perf/assembly-source-dependencies-isolated`, PR #686.
- Child branch: `perf/assembly-granularity-isolated`.
- Native checkout: `C:/src/ha-assembly-granularity-integration`.
- Code-only checkout: `C:/src/ha-assembly-granularity-staging`.

Both checkouts have their own `uv sync --frozen` environment and initialized
submodules. The native checkout builds a same-main baseline while code extraction
runs in the other checkout; its Python, configuration and adapter inputs stay
frozen. No native outputs, freshness ledger, token, gate stamp or environment
were borrowed from another experiment.

Parser commits were extracted in order: `ac8d9035`, `592629bb`, `e2d3af8b`,
`d35c50ef`. The helper split follows `62cc4d79`, `840b0a42`, `aff115c4`.
The recipe-test conflict was resolved by importing only the helper fixture and
mutation cases, excluding the drawing parent's `_channel_pose` regression.
No `_channel_pose.py` or `_cwm.py` change is part of this stack.

The initial read-only comparison found 82 unchanged definition ASTs and 13
import-only callers. Fresh integrated source-contract and key-mutation checks
will be recorded below. Neither helper body changes nor the withdrawn #678
mass-read optimization are part of this extraction.

## Receipts so far

The reporter was copied locally from `aff115c4` before its introducing commit.
Its SHA-256 is
`9cbab71ad608397b57bdc2a5f47d389d9e0e5d33be67ab9be6050607bda8035a`.
Each report records production recipes/task keys for eight assemblies and 108
leaf parts without COM or cache transfers. Its untracked presence is disclosed.

| Report | SHA-256 |
|---|---|
| Native checkout `cad/out/reports/assembly-granularity-integration/main.json` | `77369ea71ba99d4edd436cc9f493715b36ce744967720a03d216925c7f9514aa` |
| Code checkout `cad/out/reports/assembly-granularity-integration/parser-only.json` | `77b3e6c0b531637455d36a163201d1f7a2514da878ab40b2316435034aff598b` |

The attach-only, seat-locked inventory found PID 18748, revision 34.3.0, and
only the two clean documents from our completed #685 run. Those exact documents
were closed without saving, with their accepted SHA-256 values checked before
and after. The original #682/#685 worktrees, outputs and receipts remain intact.
Inventory evidence is retained beside the native baseline report.

The cache-disabled same-main `uv run python -m doit -n 4 build_bare` run is in
progress. Candidate full-build, zero-COM repeat, native fingerprint/DOF comparison,
visual inspection and latest-code reviews are still required. This is not a
merge-ready result.
