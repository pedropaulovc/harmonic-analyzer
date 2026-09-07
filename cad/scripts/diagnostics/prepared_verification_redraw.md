# Verification-blank display synchronization candidate

This is an unproved production synchronization candidate, not a frame-resize fix.
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
or tracked DRWDOT changes. Actual production cone-drawing acceptance is pending;
no native execution is included in this candidate's offline test evidence.
