# Drawing simplicity policy

The drawing standard itself is [`drawing-guidelines.md`](./drawing-guidelines.md):
one set of numbered rules for part and assembly packages, followed by authors
and sent verbatim to the blind machinist reviewer. This file holds what the
reviewer must not see: how the repository implements those rules, where
per-part adjustments live, and the review gate. Per-part and per-assembly
adjustments are declared as `machinist_exceptions` under the package's own key
in `cad/config/parts/<dashed-name>.yaml` or
`cad/config/assemblies/<dashed-stem>.yaml`, and only the reviewed package's
own declarations reach its reviewer. Cite rules by the guideline's number and
title, for example "rule 5 (avoid excessive GD&T)".

It supersedes the "full GD&T vocabulary, applied functionally" verdict of
[`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md) §1 wherever the
two disagree: that assessment listed what GD&T *could* express; the guidelines
fix what the prints *do* carry.

## Why

The fleet grew ~125 feature-control frames, 100+ datum tags, roughness symbols
on gear seats and hand-crank bores, boxed basic dimensions on non-critical
holes, and 5-12-line note blocks. Most of it came from adversarial "senior
machinist" reviews prompted to hunt for *missing* tolerances, datums and
finishes: a reviewer rewarded for gaps asks for a production-line inspection
package. Authors and reviewers now work from one standard, so a reviewer
cannot ask for what the authors were told to leave out.

## How the repository implements the guidelines

Packages convert to decimal inches in batches under issue #290. The temporary
`drawing_unit: in` declaration in a package's own part or assembly registry row
selects the model's TOL_* stamps and document units, and the draw script passes
it to `new_project_drawing(unit=...)`. Missing declarations mean `mm`; explicit
`mm` is retained for metric-only supplier packages. `finalize_drawing` refuses
a sheet whose linked model carries inch rows while the drawing is not in
inches. Remove the rollout switch when the last batch lands and make inches
the fabrication default, retaining the supplier-unit exception. On an inch
fabrication sheet, a metric-only vendor line's dimension (HGR15R, KP08, Tr8)
keeps its exact millimetres: the builder gives the model dimension its own
symmetric band (`set_dimension_symmetric_tolerance(display_unit="mm")`) and
`_metric_vendor_dimension.set_metric_vendor_units` prints it in mm labelled
`mm` in the model; the imported dimension takes the sheet's document units,
so the draw script prints it in mm again and reads it back with
`_drawing_metric_vendor.print_imported_metric_dimensions`.

A converted package's builder selects the model's document units with
`_document_units.apply_package_model_units` right after `create_part` or
`create_assembly`, before any global, sketch, feature or check
(`_stock_fastener` does it for purchased stock). They are IPS decimal inches at
**8** places: calculation precision, because the equation manager evaluates
every global at the document's places; never set the 3-place print grid there.
Printed places stay each dimension's `DRAWING_PRECISION`.

The inch grades are `.X ±.1` for non-functional features only, `.XX ±.01` and
`.XXX ±.005`; drilled holes use `+.004/0` with three-place inch diameters.
Printed-grid nominals, explicit fits, roughness and worst-case wall checks
convert together with each package. Unconverted packages keep their metric
conventions. Supplier fractions remain exact REF values through
`_supplier_dimensions` with `RoundToFraction=False`; no fractional tolerance
grade applies. Changes to these shared review documents invalidate every cached
machinist review once, even though only selected native packages change units.

- **The model owns tolerance and precision (rules 3 and 4).** A band goes on
  the dimension as a native model tolerance
  (`_drawing_tolerances.set_dimension_*_tolerance`). Decimal places are authored
  by the part build (`<part>_spec.DRAWING_PRECISION`, applied natively on the
  `.SLDPRT`); the drawing imports the dimension verbatim and reads the
  precision back to prove it. A drawing script never rewrites precision at
  render time (`SetPrecision3`, `set_dimension_precision`) or types a spec
  constant into note text (`f"{DEPTH:.1f} DEEP"`). A value the sheet prints
  but no feature dimension carries is modelled, if need be by a hidden
  reference sketch whose one driving dimension is the value. The one
  exception is a pure reference dimension with no band and no model dimension
  to import; its places come from a `*_spec` constant
  (`DRAWING_REFERENCE_PRECISION`), never a literal. Migrated packages are
  gated by `test_drawing_specification_purity.py`; the rest of the fleet
  migrates incrementally.
  The cylinder-bank assembly settings also author their native dimension
  callout text in the builder; the drawing reads it back instead of calling
  `SetText` on imported dimensions. That call can write through to the source
  model, as the [rack source-save controls](pipeline/evidence/vm2-datum-placement/source-hash-cause.md)
  demonstrated. Source-clean guards remain fail-closed before drawing export.
  Purchased supplier-reference sheets retain the supplier's explicit units,
  precision, exact fractions and source bands rather than project fabrication
  controls. `_supplier_dimensions` formats a visible native value without
  assigning `SystemValue` or replacing numeric text; sizes are parenthesized
  and unit-labelled. Model-owned hidden construction carriers are explicitly
  nominal supplier references, not claims of physical-edge or helical-thread
  attachment. Thread identification is below-text on the native nominal-major
  carrier. Source bands remain model-owned. Reference sketches are authored in
  the final transformed stock frame by `_supplier_screw_reference`; only
  threaded builders import the separate `_supplier_screw_save` saver.
  Connected linear witnesses reuse an existing anchor only after both native
  endpoints report `swFullyConstrained`; independent witnesses retain their
  origin anchors. Included angles select both existing rays and use native
  angular type, exact-value and driving-state readback, with text placement
  transformed through the owning sketch plane. Final-frame coordinate and
  fully-defined-sketch guards remain mandatory.
  Source ownership requires native `IDimension` identity both with the source
  parameter and with a dimension enumerated from the intended model feature;
  matching names or values alone cannot prove membership. `IFeature` wrapper
  equality is diagnostic only: drawing-context owners can compare unequal
  even when the original model dimension is identical.
  The purchased-sheet hook reserves annotation lanes before fitting and runs
  source/configuration, native attachment/value/inventory and cell/ink checks
  after the final rebuild. The rendered supplier comparison remains necessary;
  a pre-fit allowance is not evidence that native ink fits.
  The clamp screw selects the purchased sheet's `tall_top` layout: a 96 mm
  outer Top cell retains the existing 46 mm annotation reserve, leaving
  50 mm for the measured native outline. The bottom-row cells' tops and
  the Isometric's bottom lower 32 mm; other sheets keep `standard`.
  Scale selection still tries the existing standard scales against complete
  native outlines,
  without subtracting fixed sheet-space padding. Short clamp-reference text
  is shelved only when its measured extent cannot clear the native arrow
  span; the measured arrow/witness stations stay fixed and final native
  paths, text and cell containment remain checked. Missing, duplicate, foreign
  or wrong-view native references refuse with expected and observed inventories.
  This layout contract is not a substitute for the rendered comparison with
  the supplier drawing.
- **Roughness grades (rule 6)** on inch sheets are 63 µin Ra for running
  journals and bores, cam-follower contact, slides, knife edges and their seats;
  32 µin Ra for ground knife edges and pivot-screw shoulders; and 125 µin Ra
  for the one locating seat. Unconverted metric sheets retain `_surface_finish`
  grades `MACHINED_UM` (1.6), `GROUND_UM` (0.8) and `SEAT_UM` (3.2).
- **Notes (rule 7)** that live in `<part>_notes.py` stay there. A
  drawing-only note helper enters a part's rebuild closure only if its builder
  imports it. When a builder stamps notes into a saved model property, that
  helper is a part recipe input: a note edit rebuilds or restores the part
  under the changed key before a property-linked drawing can print it.
- **Views (rules 8–10).** A cut-surface-only section uses
  `IDrSection::SetDisplayOnlySurfaceCut` and never shows hidden lines. A Hole
  Wizard placement sketch cannot carry a datum point (every point in it is a
  hole), so a hole's model dimensions stay origin-based and the print
  dimensions it from the datum feature with a driven dimension picked on both
  features.
- **Layout (rules 13–15).** Each `DrawingSpec` records its sheet orientation.
  The layout audit (`_drawing_layout_check`) checks the template's border and
  title-block keep-out; the machinist review judges containment, balance and
  fit of every visible element. An eye pass never substitutes for it (merge
  gate 3 in the root `AGENTS.md`).
  Purchased drawings may opt into a recipe-local title-block setup after the
  source links resolve, returning final-rebuild checks through the existing
  `settled_checks` contract. The catalogued supplier screws opt into
  `_purchased_title_fit`: it fits their existing linked Name, Material
  and DWG. NO. notes inside their actual native ruled cells on one row.
  Readable native-height floors are 3 mm for Name/Number and 2 mm for Material;
  an unfit complete value refuses export, never truncates it.
  `SetTextFormat` can remove a leading native `<FONT size=15PTS>` tag. The
  identity guard permits only that supported size-tag syntax around the same
  exact `$PRPSHEET` expression and still requires the full resolved value.
  Font, anchor and whole-cell bounds remain independently checked after the
  final rebuild. No saved template, purchase identity, grade or reference-view
  scale changes. The fixture's Material `LineLength` write
  was observed to persist without widening its wrapped text, so that ineffective
  write is removed for Material only; actual native bounds still decide fit.
- **Fit-up at assembly (rule 19) is a last resort.** Slots, shims, cut-to-fit
  and match-drilling open space for sloppy work, so avoid them as much as
  possible: prefer geometry whose loose bands hold the stack at the worst
  case. A stated fit-up adjustment is the escape hatch when the stack cannot
  be held otherwise — never the design default.
- **Thread engagement (rule 18)** is owned by the CAD: the build's seat-fit
  and stack asserts enforce it. Through-tapped receivers use actual retained
  material and external full-form overlap, not blind drilling depths or raw
  screw insertion (for example `require_through_seat_fit` in the harmonic
  base's pure fastener contract). Receiver capacity does not by itself prove
  a purchased screw's installed engagement; existing inspected minima and
  owner-declared shortfalls remain explicit. The 1.5D engagement minimum and
  the rule-17 wall targets (.080 in target, .060 in floor after conversion;
  2.0 mm target, 1.5 mm floor on unconverted packages) allow for a first-time hobby machinist:
  they are design margins for the shop class the guidelines describe, not
  capability limits.
- **Retention (rule 23).** Mechanical locks are the default, in preference
  order: dowels, set screws, jam nuts, cross-pins, keys or flats with axial
  capture, pinch clamps — then a brazed joint — then peening. Threadlocker is
  an option, never the default; on its own it locks nothing (rule 23).
  `cad/scripts/joint_retention.py` lists every threaded joint and audits the
  rule (`check:joint_retention`).
- **Legacy assembly sheets.** Three-view sheets from
  `drawing_recipe_assembly.md` are orientation placeholders and are expected
  to fail review until they are built out to rule 22.
- **Model defects found in review (rule 21).** Check the finding against the
  source CAD and primary visual evidence. Fix a uniquely supported omission in
  the CAD and regenerate. When the evidence permits materially different
  geometries or processes, escalate the feature, the evidence and the viable
  options to the user, with a sketch comparing them. A reviewer can be wrong:
  validate the premise rather than implementing its proposed fix.

## GD&T allowlist (rule 5)

A feature-control frame and its datums appear only where rule 5's functional
classes demand one and the project owner has accepted the specific control.
Which features may carry frames is a per-part adjustment: it is declared as a
`machinist_exceptions` entry (kind `accept`) under the package's own key in
its config YAML, carrying the functional reason, and only the reviewed
package's own declarations reach its reviewer. Everything else carries no
frames and no datums. A new entry needs a user ruling.

## Named exceptions

A shortfall against rules 17–19 (or another numeric rule) is acceptable only
by the user's own ruling, declared as a `machinist_exceptions` entry (kind
`minor`) under the package's own key in its config YAML. No one else rules,
and the thresholds are never loosened to admit a shortfall. Each entry is
specific to the part it names; it is not precedent.

The sheet states the shortfall as a plain manufacturing fact (rule 20);
`test_printed_text_rulings` keeps rule numbers, ruling ids and governance
words off printed text. The blind reviewer reports a stated shortfall under
minor. Whoever runs the gate matches each one to the part's declared entry
(same parts, shortfall within the declared range). A stated shortfall with no
matching declaration gates the package like a blocker. An emitter of an
approved declaration carries a comment naming it.

The owner's **2026-10-20** ruling for **MHA-FR-01 `fr-harmonic-base` RV-02**
accepts one nonnumeric departure from rule 2: redundant default **2B** in that
package's generated native hole-table **SIZE cells only**. The package-local
declaration in [`fr-harmonic-base.yaml`](../config/parts/fr-harmonic-base.yaml)
is the reviewer-consumed register. Physical model threads remain class 2B,
and the five separate native tap callouts still omit the duplicate class.
The generated cells are not rewritten. This is not a general native-table
exemption and accepts no other specification, geometry or numeric shortfall.

## The gate

`uv run cad/scripts/machinist_review.py <name>... --before-pdf-dir <baseline>`
compares baseline PDFs with the current registered PDFs (`--pdf-dir <after>`
selects another output directory). For an explicit package, use `--name <stem>`
with `--before-pdf` and `--pdf`; repeat each PDF option in matching
sheet-document order. PNG CLI input is not supported. Both PDF versions are
required unless `--force` requests an
unconditional review of the after PDFs.

Before starting independent reviews, the findings judge inspects the repository
PDF diff tool's **overlaid** before/after pictures: shared ink is gray, removed
ink red, and added ink blue. It may skip a package only when the differences are
rendering noise, or an assembly drawing changes only one part's geometry without
affecting mating shown on the drawings. SolidWorks balloon placement is unstable:
movement of a balloon or leader is noise when both its number and referenced
part/region remain unchanged. That noise may coexist with a skippable single-part
geometry change. A different number or target requires review, as does uncertainty
about either. This allowance does not extend to dimension changes or other
annotation edits. Proximity of a changed feature to a joint alone does not prove
a mating effect; the judge compares the depicted connections and relative
placement. A hypothetical hidden effect of a small local feature is not a
depicted mating change. Uncertainty grounded in the visible assembly evidence
still requires a full review.
An unchanged overlay is inspected too; an image-generation or precheck failure
is not permission to skip. The report retains the before/after identities,
overlay evidence and decision. A skip returns `SHIP` with an explicit warning
that the machinist review was skipped due to minimal changes, not a claim that
a full review ran. The precheck does not establish that the baseline was
approved, and PDF overlays cannot reveal changes to review rules or owner
exceptions. Use `--force` when those require reassessment. It bypasses the
precheck; build gates and prompt benchmarks use it for unconditional reviews.

Packages selected for review run three independent blind senior-machinist
reviews (`--runs N` changes the count). The same judge session that inspected
the overlays later merges their findings; independent reviewers do not receive
the baseline or precheck context. Each run receives `drawing-guidelines.md`
followed by the reviewer
instructions for the package kind (`cad/scripts/prompts/machinist_review_part.md`
or `machinist_review_assembly.md`), with its classification slot expanded from
the matching `machinist_review_<kind>_severity.md` contract. The isolated
judge inspects the after sheets and receives that same kind-specific classification
and evidence contract, not the reviewer's detection or report instructions.
It vets every finding against the guidelines, text layer and owner exceptions,
and clusters duplicate claims. Categories follow the contract's defect-type
precedence rather than the original filing: the judge corrects misfiled claims,
confirms real findings, rejects misreads, and keeps contract-defined minor or
accepted-exception claims non-gating. Complete `--prompt-file` rubric overrides
remain opaque; repository templates must be composed before use as overrides.
Historical benchmark composition pins the reviewer rubric, resolving its
severity contract from the same Git ref rather than the working tree. The
benchmark judge and its kind-specific contract still come from the working
tree for both configurations, as before this change. A confirmed
finding gates only when at least two runs raised it independently (owner ruling
2026-10-18; `GATING_MIN_RUNS`, reduced to the number of valid runs when fewer
than two are valid). A confirmed finding from one run stays in the report as
non-gating evidence: across repeated rounds, lone confirmations moved from
round to round while the sheet itself converged.

The gate covers every sheet whose rendered output a PR changes, including a
sheet that changes only because CAD geometry, config or a helper it reads
changed. A sheet the PR's own drawing script or spec edits must pass as below.
A sheet changed only indirectly passes when its review adds no gating finding
beyond a review of `main`'s version of the same sheet run with the same
reviewer, model, effort and prompt (the report records each); the PR records
both verdicts and the finding diff.

- **Review with Claude Opus 5.5 by default** (`--reviewer claude`,
  `claude-opus-5-5` at medium effort). The machinist review does not follow
  the cross-family rule for code review: Opus may review every drawing,
  whichever model authored it. Another reviewer (`--reviewer codex`, or
  `--model claude-fable-5-1`) is allowed, for example when Opus is over
  quota; record the reviewer and model in the PR. An 80-case benchmark ranks
  Opus highest on expectations met at about a third of Fable's cost.
- Every review and judge must view every sheet through the private sheet server;
  full-resolution crops resolve fine detail. A contact sheet alone is not proof.
  The judge defaults independently to Claude Opus 5.5 at medium effort
  (`--judge-reviewer`, `--judge-model`, `--judge-effort` select alternatives).
  PDF text coordinates use PDFium's page-to-device mapping with `ctypes.c_int`
  outputs, matching its `int*` binding contract on Linux and Windows.
- Claude execution first selects an eligible API credential from the private
  codjiflo pool and uses the pinned Python Claude Agent SDK. Its bundled runtime
  runs in bare mode: OAuth/keychain auth and implicit hooks, memory, plugins and
  CLAUDE.md discovery are disabled, with skills additionally disabled explicitly.
  The bundled Claude 2.1.132 parser rejects the former `--restricted` and
  `--permission-prompts` flags. Isolation instead uses supported `--bare`,
  explicit skill disabling, `tools=[]`, `permission_mode="dontAsk"`, empty
  setting sources and strict sheets-only MCP configuration.
  SDK thinking uses adaptive mode with summarized display
  (`thinking={"type": "adaptive", "display": "summarized"}`), preserving the
  selected reasoning effort and retaining emitted summaries as evidence.
  The SDK receives only explicit environment overrides (including empty values
  to remove ambient authentication); its launcher owns parent-environment
  merging and entrypoint/tracing hygiene. OMP instead receives a sanitized full
  environment, with inherited PI/OMP/XDG state removed before private-HOME and
  broker overrides are applied. Do not send a copied full parent environment
  through the SDK override map.
  The shared pool is
  `CODJIFLO_ANTHROPIC_KEYS_FILE` (default
  `~/.config/codjiflo/anthropic-keys.json`), containing exactly three unique
  `{"id": "label", "apiKey": "secret", "quotaGroup": "optional-group"}` entries
  under `keys`. Files must be regular, non-symlink, current-user-owned and mode
  `0600` on POSIX. Windows creation sets the owner to the current token user
  and a private DACL; validation still requires that owner (SYSTEM and
  Administrators may also be allowed by the DACL). Ambient Anthropic/OAuth
  keys are not a second credential source. Routing state uses
  `CODJIFLO_CLAUDE_STATE_FILE`, default
  `~/.local/state/codjiflo/claude-routing.json`, with locked round-robin claims,
  fingerprint-aware rotation and quota-group cooldown/exhaustion. Invalid or
  insecure configuration fails closed. Invalid API keys are configuration errors,
  not quota exhaustion: they never authorize cooldown or transport switching.
  Only terminal typed API quota errors authorize rotation, not ordinary prose,
  schema errors, startup failures or SDK exceptions. The pinned SDK exposes
  `billing_error` as an assistant-error discriminator: it authorizes indefinite
  exhaustion independently of diagnostic wording (`reason=billing-error`).
  Authentication errors remain configuration failures, even when their prose
  mentions credits. Other typed rate-limit/invalid-request errors require the
  corresponding quota signal; normal assistant text never authorizes rotation.
  Transient SDK
  `system/api_retry` notices are retained as evidence while the in-flight turn
  continues, including a resumed judge; they do not trigger credential cooldown,
  rotation or transport switching. A terminal quota route records
  `quota_state_write` as pending, then persisted, stale_credential or failed.
  A concurrent credential replacement returns `stale_credential`, does not block
  the replacement key and is reported identically in route evidence and logs.
  Failure also records
  the safe exception type in `quota_state_write_error` and emits
  `machinist_review.quota_state_write` with outcome `failed`. State-write lock
  waits remain inside the original attempt deadline. A failed write does not
  erase the quota evidence or silently authorize fallback.
- Shared routing recovery is operator-controlled; there is no automatic lock
  reclamation or re-probe of indefinite exhaustion. From the sibling
  `codjiflo-reviewer` checkout, using the same `CODJIFLO_ANTHROPIC_KEYS_FILE` and
  `CODJIFLO_CLAUDE_STATE_FILE` overrides as the review, run
  `node scripts/claude-keys.mjs status` to inspect safe IDs, quota groups and
  blocks. After topping up an account, run
  `node scripts/claude-keys.mjs reset ID [ID ...]` for every blocked key ID in
  its quota group. `node scripts/claude-keys.mjs reset` clears all blocks and
  recovers corrupt routing state. These commands use the same shared lock.
  If `<state-file>.lock` is stale, first confirm its owner has stopped and no
  review or codjiflo process can still be updating that state; only then manually
  remove that lock file and retry. Never remove a live or unverified owner's
  lock, or replace the shared lock with a process-local advisory lock: both
  projects must retain mutual exclusion.
- When no configured API credential is eligible, execution uses **OMP**, never
  Claude CLI OAuth. OMP runs in RPC mode with cwd beneath a private HOME, an inert
  local `.omp` discovery boundary, and disabled ancestor context-file providers,
  built-in tools, extensions, rules, skills, LSP, memory and autolearn. Only the
  cwd-local sheets MCP server is discovered. The model is qualified as
  `anthropic/<model>` and its resolved provider must be Anthropic.
  A bounded `omp --version` preflight requires a recognized stable version at
  least **18.7.0**, before opening the broker or submitting any prompt. Unknown
  or older versions fail clearly; there is no 17.x compatibility path. A newer
  version does not bypass actual system-prompt, provider or sheets-only tool
  isolation validation. Successful probes record canonical `omp_version` in
  both current provenance and the route history.
  OMP's fixed workstation metadata and built-in critical directives remain;
  the startup guard accepts their rendered structure but rejects additional
  project instructions, rules, skills or appended context.
  Existing OMP credentials remain in the original
  vault, accessed through the supported auth broker: an explicitly configured
  `OMP_AUTH_BROKER_URL`/`OMP_AUTH_BROKER_TOKEN` pair is reused, otherwise a scoped
  loopback broker opens the existing store and is reaped after the invocation.
  No privileged Windows links or credential copies are required. Broker tokens
  are passed only in environment, with snapshot disk caching disabled.
  API-key proxy overrides are stripped from the OAuth environment, so a proxy
  configured for SDK API keys never receives the broker's OAuth bearer.
- Before submitting review content, SDK `get_mcp_status` must prove that the
  actual session has the sole connected sheets server and both tools; OMP waits
  for synchronous MCP startup and validates actual RPC `get_state.dumpTools`,
  system-prompt isolation and resolved provider. Startup is bounded to 120
  seconds within the total attempt deadline; timeout diagnostics retain the
  startup phase and its budget rather than reporting a full-attempt timeout.
  An exhausted overall deadline remains an attempt timeout even when it expires
  inside a startup phase; the startup budget must not relabel that failure.
  The timers share an absolute attempt deadline; equal startup/attempt
  boundaries always belong to the overall attempt, regardless of timer order.
  Credential-lock contention has its own phase and budget (at most 30 seconds,
  also bounded by the attempt deadline), distinct from MCP startup and full
  attempt timeouts. A contended or stale lock fails closed, without bypassing
  shared routing state through OMP; recovery follows the operator procedure above.
  Failed or incomplete startup submits no review. Native redacted records and
  normalized image/tool evidence are retained separately.
  Tool arguments retain OMP's harness intent metadata in those records. The sheet
  server and shared reviewer/judge evidence validator ignore only the `i` key
  when its value is a string, before checking the exact integer tool arguments.
  Unknown keys and non-string intent values remain invalid; successful image
  results and an in-range view of every sheet are still required for inspection.
  SDK dataclasses are converted once; native records are redacted before being
  streamed to disk. Normalized image/tool events still accumulate in memory for
  the existing stdout/evaluation interface; only native records are streamed.
  OMP streaming logs retain incremental deltas rather than repeated cumulative
  message snapshots. Terminal messages, including real tool images and usage,
  remain intact. Verdict extraction and successful inspection use only the final
  route; billed usage sums every route, including quota-rotated API attempts.
  Interrupted routes without a terminal SDK result retain partial events and
  observed input/output/cache-read/cache-creation integer token counters in a
  synthesized error result. Nonnumeric usage metadata (service tiers and nested
  cache/server-tool details) remains in raw evidence, not token arithmetic.
  Partial accounting neither certifies complete billing nor makes a failed
  attempt successful or cacheable; an existing SDK terminal result stays
  authoritative. Runtime and eval share the same OMP prompt/config validator.
  Routing-lock cleanup attempts each owned resource independently and closes
  temporary output before deleting it. Cleanup failure never masks a primary
  operation exception (including interruption); sanitized exception notes and
  structured `credential_cleanup_failed` error logs report the cleanup category,
  OS error codes and primary category, never raw exception or credential text.
  Without a primary error, cleanup failure remains fatal.
  No cleanup error authorizes a whole-operation retry, lock stealing or an
  ambiguous Windows access-denied acquisition retry.
  RPC stdout is a strict machine channel: every nonempty line, including the
  shutdown drain, must be a JSON object. Malformed lines are retained as native
  `rpc_parse_error` evidence and fail closed, never discarded as diagnostic noise.
  A prompt-correlated RPC `response` with `success:false` fails immediately,
  without waiting for a `prompt_result` that may never arrive.
  Legitimate trailing terminal events use the same native retention and
  normalization as active RPC events; unexpected postcompletion events and
  non-sheets tool calls fail closed. Success is emitted only after this drain
  and persisted-image validation complete. Drain failures retain sanitized
  `cleanup_error` evidence and logs without replacing an earlier primary
  failure. SDK disconnect and transcript-redaction failures follow the same
  primary-error rule; redaction failure alone is fatal, never permission to
  return a successful verdict with unsanitized native state.
  Valid findings are never retried. A successful precheck pins its actual transport and session for
  judging. SDK continuation prefers the original credential, but may select
  another eligible key **before** submitting its single resumed turn: the local
  conversation and cwd remain unchanged. Once submitted, a failed resumed turn
  is never retried or switched to another transport.
  Resume inputs are explicitly allowlisted: `transport`, `private_home`,
  `session_id`, `credential_id`, `credential_fingerprint`, `sdk_session_dir`,
  `sdk_redacted_files`, `sdk_redacted_fingerprint`, and `session_file`. Mutable
  allowlisted values are deep-copied. Completion evidence (resolved model,
  effective options, exact prompt/hash, image digests and shutdown outcome) must
  be newly observed for the resumed turn, never inherited from the precheck.
  Judge provenance is a separate object; judging must not mutate the retained
  precheck report.
  The same boundary applies when quota rotation starts a new SDK route or
  falls back to OMP: route entry rebuilds provenance from explicitly owned run
  metadata and conversation inputs, not a completion-field denylist. Unknown
  completion fields cannot leak into a successor; prior route outcomes remain.
  Resumed conversations retain their explicit session/redaction inputs, while
  fresh routes retain only their lifecycle-owned private HOME and run metadata.
  Private SDK transcripts and OMP agent/blob state survive the precheck so
  persisted images hydrate correctly in the judge's history. Independent runs,
  failed attempts and completed judges delete native state after retaining
  redacted event/image evidence. The aggregate also cleans an unused precheck
  when judging is skipped or an error returns early. Native session IDs remain
  historical provenance, not standalone CLI resume recipes after cleanup.
- Structured operation logs and span events record credential decisions (safe
  IDs/counts), SDK route starts, quota unavailability and OMP fallback reasons.
  Logs also record broker readiness and terminal outcome or original failure
  category; redacting a provider exception must not collapse its structured
  category to `RuntimeError`. Keys/tokens, environment maps and unredacted
  exceptions are never logged or retained. Eval identities record runtime versions and
  each attempt's actual transport provenance; SDK descriptors are not CLI argv.
  Descriptor config/schema paths must match the staged cwd-local inputs; a
  mismatched recorded path fails before submitting a provider request.
  Each retained `native-events.jsonl` is SHA-256/count-bound to its invocation.
  Eval parses every JSONL record as an object envelope with object `native_event`;
  indexes must belong to started routes, agree with normalized-event route
  boundaries and cover successful/provider-event routes. Failures before the
  first provider event need no native records. Validation remains offline:
  `CredentialPool.redact` checks explicitly known environment credential values
  without opening credential stores; arbitrary unknown-secret detection is not
  claimed. Digests catch later injection, truncation and substitution.
  SDK provenance records the effective isolation options in `sdk_isolation`
  (tools, permission mode, setting sources and strict MCP configuration).
  Both transports record `resolved_model` as a provider/id object; the SDK
  provider is `anthropic`.
  Successful OMP evidence records `omp_effective_options`: actual argv, parsed
  overlay JSON, actual `get_state` system-prompt parts and sorted tools, and
  actual cwd. Evaluation independently checks the isolation flags and overlay,
  runtime context/tools, private-HOME cwd and session containment, nonempty valid
  persisted image digests, and completed shutdown. `omp_prompt` and
  `omp_prompt_sha256` bind the exact submitted message, including its appended
  JSON schema, rather than just the rubric. These completion requirements apply
  to successful invocations; failed startup/attempt history remains usable
  without pretending completion evidence exists.
  OMP has no constrained decoding. When its final text fails the verdict
  extractor's own parser or the supplied JSON schema, the transport sends at
  most two correction prompts in the same session. Each quotes the error and
  asks for only the corrected JSON object: same content, no new findings, no
  tool calls. `omp_repair_turns` records each error and a
  `machinist_review.omp_repair_turn` span event marks it. Once a correction is
  requested, any tool call event fails the attempt, including trailing events
  read by later control requests or the shutdown drain, so corrections never
  add sheet evidence. The result event and verdict are the final text;
  validators are unchanged, so text still invalid after two corrections fails
  exactly as before.
  The pinned SDK package/version is mandatory. OMP is an optional fallback for
  SDK runs: a missing executable or failed, empty, timed-out or OS-error
  `omp --version` probe does not prevent SDK execution. Runtime identity records
  the explicit probe outcome (and exit code when available), not raw failed-probe
  output or exception text that could leak secrets. An executed fallback still
  fails normally if OMP is unavailable. This transport policy does not regroup
  project dependencies or change dependency-group installation semantics.
  The cache key identifies the SDK-first/OMP-fallback **routing policy**, not a
  quota-dependent route selected in advance. The canonical cached result records
  the route actually used and its per-attempt provenance, which adopters retain;
  it does not claim SDK and OMP are identical inference harnesses.
  Review-verdict inputs include repository-root `pyproject.toml` and `uv.lock`,
  so pinned SDK/runtime dependency changes invalidate cached verdicts.
  Whole-manifest hashing conservatively invalidates reviews for unrelated
  manifest edits too; dependency versions remain authoritative in manifests,
  not duplicated in cache code. These review-only inputs do not change CAD
  part/drawing geometry recipe keys.
  SDK-only run identity excludes optional OMP version probes; diagnostics remain
  in aggregate `runtime_probes`. An actual OMP route's recorded version must
  match a successful current probe before reuse. An unavailable cached OMP probe
  stops clearly without issuing paid reruns; a changed successful version
  invalidates the evidence.
- Claude multi-run reviews use **initial-request staggering, then concurrent
  continuation**: `r1` starts alone; the other isolated runs start after its
  first real positive-usage provider assistant response, while `r1` continues.
  Initialization, MCP readiness, diagnostics, synthetic/API errors and zero-usage
  events do not release the followers; the first assistant event's partial
  output count is not a completed review. If `r1` terminates before responding,
  including exhausted retries or timeout, followers still run under the existing
  partial-failure policy, without claiming a warmed cache. Each run keeps its
  own neutral cwd and fresh session UUID, the same frozen sheets, rubric, model
  and effort, and no shared history. Codex runs remain fully parallel. Single-run
  reviews, the precheck/judge lifecycle and the two-run support rule are unchanged.
- The authoritative result is `<name>.aggregate.json` and its companion
  `<name>.aggregate.md`, not an individual run's verdict. `FIX` means at least one
  **confirmed** blocker, over-specification or clarity finding raised by two or
  more runs. Confirmed minor findings, single-run confirmations and rejected
  clusters remain in the report but do not gate. `SHIP`
  means no confirmed gating findings and no aggregate error, or an explicitly
  warned minimal-change skip. If valid runs return zero findings, findings
  adjudication is skipped. The judge schema enumerates the submitted finding
  ids, so a cluster citing any other id is a schema violation (repaired in the
  same OMP session when possible). If all runs fail, or
  the judge fails after retries (including incomplete/duplicate finding
  coverage), the result is `ERROR` and exits nonzero. Partial run failures
  remain visible alongside valid evidence; run reports and isolated judge
  transcripts are retained separately.
- A review counts as a merge gate's visual check only on the exact drawing
  version being merged.

Use `uv run cad/scripts/machinist_review_bench.py run --workspace <outside-git-root>
--evals <id-or-name>... --reviewer claude --baseline-ref origin/main` to compare
release-package reviews with the working-tree skill (`with_skill`) and the
baseline skill (`old_skill`); `--ref <git-ref>` pins `with_skill` instead.
Review model and reasoning controls are `--model` and `--effort`.
Use `--baseline-ref none` to run only `with_skill`, without loading or reviewing
the baseline prompt.
Alternatively, `import --workspace <outside-git-root> --evals <id-or-name>...
--config with_skill=<review-directory> --config old_skill=<review-directory>`
enrolls existing reviews without running another reviewer.
A single `--config with_skill=<review-directory>` or
`--config old_skill=<review-directory>` is also allowed; only the supplied
configuration is graded and displayed, with no comparison or delta columns.
Both commands create
an `iteration-N` outside Git, with descriptive eval names and per-configuration
`run-K/outputs/review.json`. Run `grade <iteration-directory>` to grade it with
Codex (defaults: `gpt-6.1-sol`, medium); `--grader-model`, `--grader-effort`,
`--grader-timeout` and `--jobs` control grading. Aggregation writes
`benchmark.json`, `benchmark.md`, and `failures.json`; failed assertions retain
their rule, polarity, confidence and grader evidence, with unknown legacy rule
or confidence recorded as `null`. Then run
`view <iteration-directory> --static <output.html>` for the skill-creator
viewer; `--skill-creator-path <checkout>` selects its installation. The bench
viewer includes formatted findings with highlighted rule citations and the
release drawing sheets, with links to full-size sheet images. Omit
`--workspace` to use `$HARMONIC_AGENT_SCRATCHPAD/harmonic-analyzer/machinist-review-evals`,
or, when unset,
`%LOCALAPPDATA%/harmonic-analyzer-agent-scratchpad/harmonic-analyzer/machinist-review-evals`.
The benchmark measures release-package/LLM review regressions; the separate
`machinist_review_eval.py` remains the frozen-PNG/human calibration tool.
A case whose drawing was renamed after its release names the current registry
package and the release's PDF basename in `release_pdf`; run and import read
that PDF.

Regression tests defend observable manufacturing contracts and plausible
failures, not note wording, line counts or mocked API-call sequences. Native
drawing generation verifies persisted dimension values, tolerances, reference
state and required view modes. A finish attachment identifies the controlled
model face and keeps its physical leader landing, not merely a non-dangling
transient silhouette. A sheet-derived linear reference reads back a linear
native dimension type before its system value is read as a length.
