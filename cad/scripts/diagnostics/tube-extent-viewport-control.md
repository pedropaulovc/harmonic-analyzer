# Retained tube viewport positive control

This is an observation protocol, not production-template acceptance. It follows
the rejected [material/finish candidate](material-finish-clearance.md). No fit
threshold, 1 mm clearance, drawing scale, text, font, note anchor, or frame changes.

The preserved candidate moved MATERIAL by -95.823970 micrometres in its native
display-text positions and approximately the same distance in PDF ink, while all
six `INote.GetExtent` values stayed identical. FINISH moved +452.652418 micrometres
in its anchor/display text, but its extent moved only +333.709602 micrometres.
The tube still failed native containment by 16.713446 micrometres at built/cold.
That is evidence against the rigid-extent-translation prediction, not evidence
that the required text failed to move. Screen quantization remains a hypothesis.

## Immutable historical inputs

- Runtime that produced the evidence: `2ce7e15e8855ff2aee982a6b51303895aea0a222`.
- Blank report: `baked-template-o6sv1ubh/template-layout.json`, SHA256
  `98546ce1c61cdcec36ed2c81f690817fa8c8f1bffc49af8a344c2da807c17e34`.
- Derived DRWDOT: `baked-template-o6sv1ubh/baked-template-o6sv1ubh.DRWDOT`, SHA256
  `97a59b4f1d39994d522b7220fb89e0cb026b47d253031d5c54a2107872ff5c92`.
- Populated report: `populated-template-ear8a03p/populated-template.json`, SHA256
  `9fbdd1f43856980c5ab4ef53522a68017e15a8fe68e68225cafc7d7febb63dcd`.
- Its ownership report SHA256:
  `3b2dabe0ca5f7c7a7d7f577bea38d7b6c4d7eeca0bd4b3270d99cdf03fb17b6c`.

These paths are relative to the retained material-finish checkout's
`cad/out/reports`. The only part consumed is the unique tube copy explicitly
named in the populated receipt, SHA256
`5b3c9bb45e06965f262d5734612c065872ddf0decd2daaa10e4e887fc9061320`.
The validator checks its full source/copy/cold record and ownership preservation.
It does not read the original foundation producer paths or execution tokens.
Those originals can rebuild independently; this copy remains historical evidence.

## One drawing, two states

Use the existing owned populated-template entry and normal factory. Create one
fresh tube fixture from that retained source copy and exact derived template;
this does not reopen the prior SLDDRW or claim byte-identical fresh drawing output.
The view remains 1:10 and sheet remains 1:2, as in the rejected tube fixture.

Before inserting the model view, run blank A/B/A on that document. After the
normal finalizer/PDF export, run populated A/B/A on the same document. Compare
retained and current blank/loaded non-extent state before testing the hypothesis.
Each A/B/A captures all raw native note fields, display-text positions, frame
geometry, exact live handles, and the initial seven-field viewport state:

1. A: capture original viewport and note extents; export PDF.
2. B: set `IModelView.Scale2` to exactly twice its initial value, immediately
   verify native scale/orientation, and hold the captured `Translation3` fixed.
   Redraw, capture extents plus the native model-to-screen basis, export PDF.
3. A: restore the exact initial viewport; require exact native A/A equality and
   unchanged PDF glyphs, supported path/object inventory and uncropped pixels.

An additional exact restoration runs in `finally`, including on interruption,
measurement failure or checkpoint failure. A failed restoration is retained with
the original exception, never substituted for it. Native source/cold/no-save
guards from `one_trial` remain; no drawing-content writes occur within A/B/A.
The initial normal factory/finalizer still performs its existing setup and saves.

The existing material field audit runs unchanged and keeps every issue. Only
native-fit issues are observations in this explicit mode; wrong text/properties,
fonts, geometry, defaults, identity, PDF or cold state fail the diagnostic.
Even a successful control ends `observed`, never `fit accepted`. Extent changes
may support or refute the screen-grid hypothesis. They cannot change production
layout or justify a relaxed tolerance. A/B raw extents are observations; A/A is
an exact guard. There is no rounded or font-estimated replacement bounding box.

## Documented API boundary

The local official reference explicitly documents `IModelView.Scale2 *= 2` for
2x zoom. `IModelView.Transform` is **get-only** despite its generated property
signature: its setter is unimplemented; its output maps model points to screen
pixels. `IMathUtility.CreatePoint` / `IMathPoint.MultiplyTransform` capture that
basis without guessing matrix storage. `Translation3` restores only the original
native pan vector. `GetVisibleBox` records pixel bounds; no window resizing,
orientation setters, zoom-to-fit, sheet scale or `IView.ScaleDecimal` writes.
`GetExtent` documents sheet-space bounds and is invalid for invisible documents.
`IDisplayData.GetTextPositionAtIndex` is retained as its documented raw offset,
not relabelled as an independently calibrated glyph bounding box.

## Native launch

Use a reviewed frozen candidate with its own uv environment and adapter `25bc99b1`.
The parent sets the observed existing SW PID, disables autostart and remote cache,
and launches the normal entry under the global seat lock; never invoke `--worker`
directly. No source root argument is accepted in this mode:

```powershell
uv run --frozen python cad/scripts/diagnostics/probe_populated_template.py --population tube-extent-viewport --template C:/src/ha-template-material-finish/cad/out/reports/baked-template-o6sv1ubh/baked-template-o6sv1ubh.DRWDOT --template-sha256 97a59b4f1d39994d522b7220fb89e0cb026b47d253031d5c54a2107872ff5c92 --retained-population C:/src/ha-template-material-finish/cad/out/reports/populated-template-ear8a03p/populated-template.json --retained-population-sha256 9fbdd1f43856980c5ab4ef53522a68017e15a8fe68e68225cafc7d7febb63dcd --retained-ownership-sha256 3b2dabe0ca5f7c7a7d7f577bea38d7b6c4d7eeca0bd4b3270d99cdf03fb17b6c --retained-blank-sha256 98546ce1c61cdcec36ed2c81f690817fa8c8f1bffc49af8a344c2da807c17e34 --symbol-library "C:/ProgramData/SOLIDWORKS/SOLIDWORKS 2026/lang/english/gtol.sym"
```

Native execution is pending. Offline fixtures test refusal and restoration, not
actual SOLIDWORKS extent quantization or production drawing acceptance.
