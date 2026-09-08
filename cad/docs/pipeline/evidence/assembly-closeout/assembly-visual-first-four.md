# Independent closeout: first four assembly renders

Inspected at frozen head `64c3dab4875354a7d44d709539e001db920a0377` in
`C:/src/ha-assembly-closeout-independent`. Codex opened and visually inspected
each actual PNG below using the image viewer. All four previews are readable;
no visible geometry defect was found in these views.

**This is a partial visual receipt for four assemblies. It does not complete
the whole visual gate or certify the running full build.** No COM, native
artifact changes, tracked edits, or changes to `verify_closeout.py` were made.

| Assembly | PNG modified UTC, 2026-09-08 | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| frame | 04:38:43.2042951 | 272438 | `3c091004ac87d2575b7edaea539d5011356ac46b38256ffd1ee56dab24b64afe` |
| magnifier | 04:39:27.9854644 | 264736 | `e954bdd2978b8ff8f985599fea6d1ba46d11d9db84d0551aa3f3122d563e8845` |
| summing | 04:40:00.9433482 | 280499 | `7a8600842f767431d2d79e6dba03675fd99864f862a48253a31472eccb0e0c81` |
| paper-drive | 04:43:02.0873493 | 302818 | `212ee1f6269ee97adc97c0e99d10a2f052fb0628b44e6cb8cee1e0d779b71d4f` |

The coordinator supplied successful native assembly completion times of
04:38:49, 04:39:31, 04:40:06, and 04:43:07 UTC respectively. The inspected file
timestamps precede those completions by a few seconds. This receipt records
the image bytes actually inspected; final native/source-identity verification
remains with the coordinating build.

## Visible geometry

- `cad/out/png/frame/frame_isometric.png`: Entire frame is inside the view.
  All four columns, the upper rectangular casting with two openings, base,
  lower angled support, and nameplate are visible. Columns meet the upper and
  lower structure; no obvious displaced member or clipped assembly is visible.
- `cad/out/png/magnifier/magnifier_isometric.png`: Entire mechanism is visible,
  including the wheel, horizontal lower bar and clamp, upper rods and block,
  and the thin connecting line. The line can be followed from the upper
  mechanism to the wheel. No obvious missing wheel sector, misplaced bar, or
  discontinuous visible transmission element is apparent.
- `cad/out/png/summing/summing_isometric.png`: The curved support, spring and
  hooks, green lower mechanism, two end supports, and their fasteners are
  readable. The spring visibly connects the upper hook to the lower eye.
  No obvious detached piece, broken silhouette, or clipping is visible.
- `cad/out/png/paper-drive/paper-drive_isometric.png`: The platen, clips,
  support bar and clamp, gear cluster, and complete hanging chain loop are
  visible. The chain follows both sprockets without an obvious broken section.
  A separate silver sprocket left of the chain initially merits checking; it
  is the intentionally loose spare T18, not a detached driven sprocket.

The spare interpretation was checked against the actual source, not assumed
from the image: `cad/scripts/build_paper_drive_assembly.py:409` defines the
spare at `(160.0, BASE_DECK_Y, -75.0)`, and line 1509 inserts
`transgear-removable` configuration `T18` with `ROT_X_NEG90`, labelled
`transgear-removable (spare T18)`. Its deck belongs to the separate frame
assembly, so the isolated paper-drive render shows the spare without the
supporting deck. Source comments and the insertion agree with the visible
flat spare. Its final placement on the deck still belongs to the top-assembly
image inspection.

These isometric views support an overall geometry eye pass for the four named
assemblies. They do not measure tolerances, prove hidden clearances or mates,
or cover the other assemblies and drawing sheets.
