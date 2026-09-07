# Verification-blank display synchronization candidate

This is a bounded display synchronization change, not a frame-resize fix. The
first actual production MISS passed below; a universal cause/fix is not proved.
Three actual spec-4:1 preparation failures retained the same one-pixel smaller
verification viewport; the attach-only accessor controls at `cd1766e1` passed
without a warmup drawing, extra CREATE-exit restoration, or Frame getters. Those
controls therefore do not establish the cause of the production failure. See
[the frame-control evidence](prepared_frame_control.md).

The candidate adds exactly one `IModelDoc2.GraphicsRedraw2()` after the existing
verification `ViewZoomtofit2`, CREATE scope exit, baseline inventory and exact
current/active ownership checks. It precedes the existing viewport restore and
its first capture. It adds no native observation, moved guard, frame setter,
scale/pan setter, retry, or fallback. The existing restore still refuses a
different pixel box before writing scale/pan, then requires exact final viewport
and raw defaults equality. The blank initializer and inherited factory are
unchanged. A `drawing.template.verification_redraw` span measures the extra call.

The bundled official `types/IModelDoc2/GraphicsRedraw2.md` documents a void call
that forces an immediate display update; `examples/Redraw_Graphics_Example_VB.md`
shows that call on the native document. The method is obsolete in favor of
IModelView.GraphicsRedraw; this bounded experiment uses the same documented
document-level method already used by the restore. Neither reference promises
that it fixes this viewport mismatch.

Before the production edit, new ordering/exception tests both failed because
the call was absent (`pytest-telemetry/run-_jeelm6i`). Existing call-order tests
were deliberately revised, after reporting their contradiction: they now require
one earlier redraw and the unchanged later restore sequence. Pixel refusal still
allows zero Frame, Scale2, or Translation3 writes; ownership refusal still allows
zero redraws. New tests cover void return, redraw exceptions, active/current
switches and baseline-state drift before the call. Exact comparison tests remain.
The seven-file adjacent gate passed 412 tests in 14.35 s
(`pytest-telemetry/run-rzj0xdif`); the unchanged shared-restore pixel/ownership
refusal tests are included. Ruff checks passed for the four changed Python files.

Changing the preparation helper changes its content-derived cache key and the
drawing helper input closure. No part/assembly source, adapter, global preference,
or tracked DRWDOT changes. The candidate's offline test evidence is separate from
the subsequent native run below.

## First actual production result, 2026-09-07

At root `4c3c1e11`, adapter `25bc99b1`, SW revision `34.3.0`, the normal
`drawing:cone_tip_adjuster` task passed. Trace
`e94eb6fb64ce06cb1cd7232978a8a173` records 62.501315 s for the task,
40.490950 s for `drawing.template.prepare`, and 0.026469 s for the new redraw.
The receipt's broader preparation timer is 40.530845 s; these are distinct
boundaries, not competing measurements.

Published cache entry:
`cad/out/prepared-drawing-templates/541ab0717c2abd5f9739543b88a72ceb63064ad896dfdccd3f0f026195f82bbf`.
Its receipt SHA-256 is
`5a2445340d4d15069c2769b1885f09e0f24022a8e6c6aac6f91a748284478447`;
derived DRWDOT SHA-256 is
`6a18b373803a0b813ef66cab1995af1bd1bed201a56d0f99b96286b3c3028098`.
The manifest is validated and binds both hashes. Inputs before/after are exact,
including original template
`2b1bbe3dfff265e8bb35ea79f0f9690f808049f5cef764cab8959c1eaee5e849`,
scale 4:1 and precision 2. The empty baseline was preserved; no cleanup error
was recorded.

Compared with the last failed `pending-09f01092e507-dn6v_vzy` receipt, the only
changed input digest is `_drawing_prepared_template.py`. The target viewport is
identical. After the new redraw, the pre-restore visible pixel box is
`[2216,141,3824,995]`, not the former `[2216,141,3823,994]`; the transform also
changes while scale, translation and orientation retain the prior pre-restore
values. The unchanged restore then reaches exact six-field target equality.
All enforced defaults for 43 notes and two surface-finish symbols agree; the
actual comparator was rerun offline successfully. Only the existing separately
retained ten proven zero-ink extent observations differ. No equality or resize
policy was relaxed. This is one positive actual-production synchronization
control against three retained failures, not proof of reproducibility on every
session or of the precise underlying UI mechanism.

The fresh cone-tip PNG was visually inspected: drawing number `MHA-097` and
revision `v32` occupy separate fields, and the elevation shows the source-authored
`5/16-18 UNC-2A` above-lane text and `DEEP` lower-lane text. Native callout
verification passed for both source features. PNG SHA-256 is
`ba4a2c43a0c4b48621d8e44720d758b211a61e736d12a86747b1091ab1ca873d`
(written 11:21:13 UTC); native drawing and PDF were also freshly saved. This
eye pass is not a cold-reopen or measured full-title-field fit proof.

The subsequent screw trace `4339a41c960ce33fcd059a38e0c03ab2` reused that exact
entry (`drawing.template.cache_hit`: 0.002180 s; factory: 1.518177 s) and passed
the `ThreadTail` callout verifier. It then failed the unchanged final
annotation-stroke/GTol-body crossing gate before save/export. Its old PNG,
SHA-256 `30775821e820c47f151b9de3fa91e307c28985e5b5e90e149fb2eb05e9d70714`,
was written 2026-09-06 18:50:52 UTC and still shows the old crowded title block.
It is not an output or acceptance witness for this failed run. No new title-block
fix is inferred from comparing that stale image with the fresh cone-tip image.
Remaining screw layout and both cold-replay gates stay in force.
