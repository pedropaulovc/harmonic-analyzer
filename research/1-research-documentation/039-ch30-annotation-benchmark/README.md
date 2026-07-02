# 039 — ch30 annotation benchmark (multi-model vision)

Benchmark of 5 models pinpointing mechanical features on the 8 ch. 30 "Eight Views"
photos: dead centers (rotation-axis points) of the pinion, cylinder and cone gears;
the 4 corners of the most visible rocker arm; all visible machine corners.

Round 2 of the experiment — v1 lived in `ch30_annotated/` (Claude Fable vs Codex,
adjudicated per feature). v2 changes: dead center = ROTATION-AXIS point (not
lengthwise midpoint), smaller dots (r ≈ 4–6 px), models are told to cross-reference
the book's part-detail chapters (ch11 crank, ch12 cone gear, ch13 cylinder gears,
ch14 rocker arms, ch25 pinion), and every model gets the IDENTICAL prompt.

## Layout

| path | what |
|------|------|
| `SPEC.md` | feature definitions, method constraints, output schema |
| `PROMPT.md` | the one prompt all models received (per-image values substituted) |
| `runs/{fable,opus,sonnet,haiku,codex}/` | each model's 8 annotated PNGs + JSONs |
| `ground_truth/` | human ground truth (made with the app below) |
| `groundtruth-app/` | drag-drop ground-truth editor |
| `score.py` | scores runs vs ground truth → `results.md` / `results.json` |
| `results.md` | headline table (provisional until ground truth is saved) |

Models: `fable` = Claude Fable 5, `opus` = Claude Opus, `sonnet` = Claude Sonnet,
`haiku` = Claude Haiku 4.5 (Claude Code subagents, one per image), `codex` = Codex
CLI / GPT-5.x (`codex exec --sandbox danger-full-access`, one run per image — the
plugin's workspace-write sandbox is broken on Windows, see
`memory/codex-windows-sandbox.md`).

## Providing ground truth

```
uv run python research/1-research-documentation/039-ch30-annotation-benchmark/groundtruth-app/server.py
# open http://localhost:8039
```

Each image loads prefilled from the round-1 consensus — drag each crosshair onto the
true point (wheel-zoom for precision, arrow keys nudge 1 px), toggle `occl` for
features not visible, then **Save**. Repeat for the 8 images.

## Scoring

```
uv run python research/1-research-documentation/039-ch30-annotation-benchmark/score.py
```

Reports per model: marked/missed/false-visible counts, occlusion agreement, mean /
median / p90 pixel error, and hit counts within 10/25/50 px. Uses `ground_truth/`
where present, falling back to the round-1 consensus (flagged PROVISIONAL).
