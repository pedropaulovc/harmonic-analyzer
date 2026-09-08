# Rack source-hash change: native reproduction

The drawing's `THRU - REAM` callout writes through to the imported model
dimension. `IDisplayDimension.SetText(4, ...)` changes the source dimension's
below-text and makes the part dirty. The subsequent native drawing
`SaveAs3(...SLDDRW, 0, 0)` saves that referenced part. PDF export and closing
the documents cause no further byte changes in these controls.

This is a reproduced model-annotation change, not an unexplained metadata
exception. The original probe only bracketed the whole recipe/export, so its
exact write operation was not recorded. The controls below reproduce the same
recipe mechanism with a fresh source and isolate the responsible operation.

## Same-input controls

The normal, cache-disabled `doit -a part:rack_pinion` task built a new isolated
part from unchanged production code. Its byte-identical retained baseline is
[rack-fresh-source-baseline/rack-pinion.SLDPRT](probes/rack-fresh-source-baseline/rack-pinion.SLDPRT),
SHA-256 `aa70ef6a9907311ccc78cf3bd5de4252e887a78aeef10a99652037be1161ef90`.
Each of the first three controls copied those exact bytes into a separate report
directory. No trial changed the retained baseline or normal pipeline source.

| Preparation before datum insertion | First source dirtying | First saved-byte change | Duration |
| --- | --- | --- | --- |
| [Full callout + precision](probes/rack-source-save-full/receipt.json) | Callout `SetText` | Native drawing save | 41.593 s |
| [Precision, callout omitted](probes/rack-source-save-precision/receipt.json) | None | None | 41.028 s |
| [Callout, precision omitted](probes/rack-source-save-callout/receipt.json) | Callout `SetText` | Native drawing save | 41.904 s |
| [Full preparation on the saved callout source](probes/rack-source-save-repeat/receipt.json) | None | None | 42.031 s |

The full control ends at
`00a6bbd8a60f64ae4fae5feeadc843e9103026a5ac5642fd596dce5d3f68b1a1`;
the callout-only control ends at
`03543e8283c5ddfccc64d33ebed50ca16fe51df06732a5464329f46cfdc5baff`.
The precision-only control retains the fresh baseline hash. The repeat starts
and ends at the callout-only hash: reopening confirms the text persisted and
setting the same text does not cause another source write in this experiment.
Separate saves need not produce identical document bytes; these controls do not
assert equivalence between their final hashes.

Every source and imported drawing dimension readback retained:

- native nominal `0.004999999906 m`;
- tolerance type `2`;
- lower deviation `2.9999999999999997e-05 m` and upper deviation `5e-05 m`;
- drawing/source dimension identity `IsSame == 1`.

The probe brackets its own readbacks with `GetSaveFlag`; none changed the dirty
flag. Opening, placing views, importing/curating dimensions and rebuilding were
clean before callout mutation. Source precision remained `-2` while the drawing
precision was set separately. Raw receipts retain every checkpoint, source-byte
snapshot and separate native/PDF export hash.

## Identity and acceptance limits

The earlier rack source transition was
`1cce146435cf80cac5d9827bd76e0b6948764ed314f5304956e08acc1e46bd96`
to `612fda6a2db58670dce187b1e59016f721067a9f89c4a374b06bee035407bc15`.
The latter bytes are retained in
[rack-post-export-source](probes/rack-post-export-source/rack-pinion.SLDPRT).
The fresh baseline has newly built native identities; it is not a reconstruction
of the original pre-export bytes. The old identity guard failure remains a failure.

No execution token or ledger was restamped, no source part code was changed,
and no manufacturing content was removed to avoid this write. This report
explains a pre-existing drawing behavior; it does not authorize accepting
unrecorded source drift. Complete production drawing validation must record
before/after identities and then prove cold-reopen identity on the actual saved
source. The partial diagnostic drawings stop before datum/FCF/finish/notes and
are not manufacturing acceptance artifacts.

The final full-stack build still waits for VM1's explicit combined integration
SHA, followed by the closed snapshot and exact-head zero-COM repeat.
