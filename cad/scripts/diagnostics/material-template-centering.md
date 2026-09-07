# Material-only template centering candidate

Offline diagnostic candidate, **not native acceptance or a production fix**.
Base: `a89a27b0b4f6b77b666a6d0418a013c07bd56436`; runtime adapter:
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`.
No DRWDOT, production factory, part builder, drawing recipe, adapter, or prior
source manifest is changed. No native run was performed for this candidate.

## Reproduced production symptom and ownership

The fresh foundation `tube-frame_drawing.png` visibly places the second material
line across the title-block divider. Its SHA256 is
`e4fd7b11327893b060f64c233366e2c1b16ecde065e72384abfb9778adba3c8b` at
`C:/src/ha-foundations-integration/cad/out/png/tube-frame_drawing.png`.
That sheet and the current candidate base use the same tracked DRWDOT bytes:
`2b1bbe3dfff265e8bb35ea79f0f9690f808049f5cef764cab8959c1eaee5e849`.

The embedded note links to `$PRPSHEET:"Material"`. The source property is
authored by `_common.part_properties` from `cad/config/parts/tube-frame.yaml`:
`ASTM A513 Type 5 SAE 1020 DOM tube, 1.000 x 0.120 in`. The template owns its
layout; replacing it with a shorter material string is not authorized.

The preceding seven-note bake's raw readback is retained in
`C:/src/harmonic-analyzer/cad/out/reports/baked-template-d54wy3lp/template-layout.json`
(SHA256 `806cfe2fe54ea76db62aee24962cc0d9f419e3e97723ed9f378c3daf2cf74741`).
It records the material value as left/top justified, unlocked, with 9-point
height (`CharHeight = 0.0023812499999999997 m`). That experiment used the
rocker/lever material footprints; it did not prove this longer tube value fits.

## Exact change under test

`probe_baked_template_layout.py --layout material-center` is a separate opt-in
arm. It does not run the four-note planner or merge the populated-gap planner.
Its only target is the unique visible, sheet-format-owned material note:

- Require the inherited unlocked, left/top state.
- Preserve X, Z, font, text, property link, and horizontal alignment exactly.
- Measure the note's enclosing native rectangular cell. Set Y to its midpoint.
- Call `INote.SetTextVerticalJustification(1)`, read back exactly `1`, then call
  `IAnnotation.SetPosition2` and require both `True` and the exact target anchor.
- Stop before a subsequent write/redraw on rejection; do not retry with
  smaller fonts, edited text, shifted labels, or relaxed tolerances.

The bundled official `INote/SetTextVerticalJustification`,
`INote/GetTextVerticalJustification`, `swTextAlignmentVertical_e`,
`IAnnotation/SetPosition2`, and `INote/GetExtent` references were read.
`swTextAlignmentMiddle` is `1`; the setter is void, and position constraints
can clamp movement. The official `Anchor_a_Note_Example_VB` is a positive
control for note justification/position calls, **not** for this middle-aligned
multiline candidate. `GetExtent` requires visible documents.

The old generic transition validator is unchanged. The material arm adds only
the one top-to-middle change before reusing that exhaustive validator. Other
notes, fonts, text, geometry, surface finishes, units, and native defaults must
remain exact. Blank save/reinstantiation and PDF/PNG equality remain required.
Blank geometric acceptance covers only the unchanged static MATERIAL label:
unresolved formula ink does not prove resolved manufacturing text will fit.

## Separately observed local source inputs

The new `material-baseline` and `material-center` population modes use these
three explicit inputs under
`C:/src/ha-foundations-integration/cad/out/sldprt`. Each SHA was read directly
and matched its `.execution` sidecar on 2026-09-07. The module
`_material_template_sources.py` pins them separately; the historical pilot
registry and the default two-source mode are unchanged.

| Source | Exact native SHA256 and execution-token value |
| --- | --- |
| rocker-arm.SLDPRT | `eb78509e2ef6f765b40efac0d5d2f16fcea8e20a118e57f04ceaad1429b44cc5` |
| channel-lever.SLDPRT | `7c07b92c1855ef5774f35513c0da2a5b799c2562e8bac5838bd12c6ed39d401e` |
| tube-frame.SLDPRT | `5b3c9bb45e06965f262d5734612c065872ddf0decd2daaa10e4e887fc9061320` |

Producer checkout HEAD was verified as
`eb39accdfb18d4c81b45dbc76439111c4658c0fb`, adapter
`e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`. Its
`cad/out/reports/telemetry/traces.jsonl` contains these completed `OK`, cache-miss
production task spans, not diagnostic-built replacements:

| Task | UTC start → end, 2026-09-07 | Span ID |
| --- | --- | --- |
| part:tube_frame | 19:21:32.666273 → 19:21:56.742794 | `0x330768a6a3c99e2f` |
| part:rocker_arm | 19:22:32.181619 → 19:23:24.645160 | `0xc60e140a811c12c7` |
| part:channel_lever | 19:52:10.261293 → 19:53:19.061686 | `0x7cd4298b40e3e220` |

This is bounded source provenance, not a green full-build claim: foundation
run 78419 subsequently failed on other surface-finish attachments.

The existing owned title trial accepts an explicit manifest for these modes;
its default registry behavior is unchanged. The source hash is checked before
copying, and the source/token files remain protected inputs. Every source is
used only through a unique-basename bytecopy. The existing exact path/native
owner, parameter/handle, copy-hash, no-source-save, cold native, PDF, and PNG
guards remain. Tube parameter witnesses are the builder's two marked drawing
dimensions, `OuterDia@AnnulusProfile` and `CapApexY@CapProfile`; these are not a
full in-memory geometry/PMI immutability proof.

The tube's minimal Front view is explicitly 1:10. At the historical trial's
1:2 view scale, its 994 mm length would span 497 mm on a 279.4 mm sheet. Only
this diagnostic view scale changes; the normal 1:2 sheet setup and rocker/lever
view scales stay unchanged. This is not a proposed production drawing layout.

Both population modes read the complete Material custom property from the
exact referenced copied source and require the displayed linked value to match.
The baseline requires top alignment; the candidate requires middle alignment.
The unchanged field auditor retains every native/PDF bounding box, full glyph
text, measured-cell containment, and 1 mm neighboring-field clearance. Existing
footer, finish, or unrelated failures still fail the overall diagnostic.

## Native launch prerequisites and acceptance sequence

The parent agent owns the native seat. Do not launch until its active run has
drained and it explicitly grants this diagnostic. Use the normal owned runner,
not `--worker` directly, and a visible existing SolidWorks process whose PID
has been verified. Set `HARMONIC_SW_AUTOSTART=0`,
`HARMONIC_REMOTE_CACHE_MODE=off`, and `HARMONIC_DIAGNOSTIC_SW_PID` to that PID.
Do not change the watchdog, session ownership, or seat-lock rules.

Use this worktree's `uv sync --frozen` environment and these entry points:

1. Run `probe_populated_template.py` with `--population material-baseline`, the
   unchanged tracked DRWDOT path and SHA above, the verified source root above,
   and the actual installed `--symbol-library` path (`gtol.sym`). Retain all
   three native/cold/PDF/PNG reports, including failed fit evidence. An expected
   baseline fit failure is not a clean result or permission to skip ownership
   or source-integrity failures.
2. Run `uv run --frozen python cad/scripts/diagnostics/probe_baked_template_layout.py
   --layout material-center`. Require successful blank transition, save, fresh
   inheritance, and print equality. The report supplies the owned derived
   DRWDOT path and SHA; never replace the tracked template at this step.
3. Repeat the first entry point using `--population material-center` and that
   exact derived path/SHA. Require all three material values to fit natively
   and in PDF, exact cold/PNG equality, and all original input hashes unchanged.
   Compare baseline/candidate raw material font/link and other static-label/
   template geometry records; there is no automated cross-report acceptance
   claim beyond the per-run guards described above. Inspect all six printed
   first/cold sheets, not only cropped title blocks.
4. Stop and retain a rejected or non-fitting result. Native multiline fit is
   still an untested hypothesis. Any broader reflow/font/title-block change
   needs a separate reviewed experiment, not a fallback in this arm.

If source bytes or tokens differ at launch, fail rather than repin silently.
Newly observed producer receipts are required to enroll different inputs.
Production adoption additionally requires the ordinary full drawing recipes,
manufacturing/cold/print acceptance, and full build/review gates on the eventual
integrated head. This candidate neither changes the production template nor
claims those gates have passed.

## Offline verification

The new tests were run before implementation: the missing material modules
failed 26 and 12 tests respectively. Three new fixture mistakes were then
corrected: a tuple mutation, a rounded literal standing in for the exact
measured midpoint, and an incomplete symbol-library fixture. Existing test
assertions and all native/PDF tolerances were left unchanged.

Focused run `run-_b96jkfk` passed **319 tests in 10.76 seconds** through this
worktree's `uv run --frozen python -m pytest`. Retained evidence under
`cad/out/reports/pytest-telemetry/run-_b96jkfk`:

- `logs.jsonl`: `14894c88f24fbc686c6439c8e2ab87128f6c1b64bfae605191c26b0b9685e447`.
- `traces.jsonl`: `5d431c6f6c0ecd78291d0b76a617f108180ecbb0cfff2bd8c092776ef28d7393`.

`ruff check` on all nine changed/new Python files and `git diff --check` passed.
The suite includes the unchanged historical template, populated-title, fresh
title lifecycle, and source-policy tests alongside the new explicit-mode,
foreign-owner/token, manufacturing-text, no-further-write, native/PDF overrun,
and unrelated-field drift counterexamples. It contains no native calls.
