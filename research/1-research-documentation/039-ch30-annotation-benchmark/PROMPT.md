# Benchmark task prompt (identical for every model)

You are one contestant in a multi-model annotation benchmark. Your task message
provides four values: ASSIGNED IMAGE, VIEW HINT, OUTPUT DIRECTORY, MODEL NAME, and a
SCRATCH DIRECTORY. Everything else is defined here and in `SPEC.md` (same folder).

Steps:

1. Read `SPEC.md` in this folder fully and follow it exactly.
2. View your assigned image in
   `C:\src\harmonic-analyzer\references\albert-michelsons-harmonic-analyzer\ch30_images`.
3. Study the cross-reference chapters listed in SPEC.md for any part you are not
   certain you can identify on sight (cone vs cylinder gears, pinion vs crank-axle
   sprocket, rocker arms). Look at other ch30 views if it helps determine what is
   visible from your angle.
4. Locate every SPEC feature by crop-and-look only (no CV edge detection). Decide
   honestly which features are occluded.
5. Draw the dots (small, per SPEC), verify EVERY dot with a ≥4× post-draw crop,
   adjust until each is within ~5 original pixels.
6. Write `<stem>_annotated.png` and `<stem>.json` (schema in SPEC, including your
   MODEL NAME in the "model" field) into your OUTPUT DIRECTORY.
7. Return the final JSON verbatim as your last message, plus one line per point
   stating how you verified it.

If the /developing-solidworks skill is unavailable in your session, skip it — it is
irrelevant to this task.
