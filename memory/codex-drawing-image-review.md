---
name: codex-drawing-image-review
description: "No-context machinist review of drawing PNGs via codex exec gpt-5.6-sol high — command recipe (stdin prompt, NOT inline), what it catches, when to stop"
metadata:
  type: feedback
---

Pedro's flow for validating manufacturing drawings (2026-07-11): render the sheet PNG, then have codex review the IMAGE with zero repo context, role-played as a machinist handed one sheet.

**Why:** it catches what the pipeline's gates cannot — a geometrically impossible note (90° spot drill × 0.5 deep cannot open Ø8), features hidden in every view, missing taper direction, dims that read as contradictions (a window height outside the view reads as an overall height). Two rounds took the crank-arm print from "cannot manufacture" to "machinable as a pre-assembly blank" (the intended state).

**Command recipe** (run from an EMPTY dir so it has no context):

```
codex exec --skip-git-repo-check --ignore-user-config --ignore-rules \
  -C <empty-dir> -m gpt-5.6-sol -c model_reasoning_effort=high \
  -i <sheet.png> - < prompt.txt
```

- **NEVER pass `--sandbox danger-full-access` here.** An earlier version of this
  note did, copied from [[codex-windows-sandbox]] — but that flag is for a codex
  task that must READ/WRITE, and it is exactly backwards for this gate, whose
  whole value is that the reviewer has seen nothing but the image. With it, codex
  reaches the filesystem, the SessionStart hook's memory lookup lands, and it
  follows the image path back into the repo — so the "blind machinist" is reading
  AGENTS.md. That open-sandbox run is where the retracted claim "these reviews are
  not blind, only advisory" came from ([[drawing-fanout-orchestration]]).
- **`--ignore-user-config --ignore-rules` are what make the isolation real**: they
  skip `$CODEX_HOME/config.toml` and user/project rules, so the seat's hooks, MCP
  servers and standing instructions cannot bias the verdict. `comparisons/bench/run.py`
  pins the same two flags so a benchmark subject cannot vary per seat. The broken
  Windows sandbox blocks exploration too, but that is an accident of this machine —
  do not let it be the only thing standing between the reviewer and the repo.
- **Pass the prompt via stdin (`- < prompt.txt`), never inline** — the command-chain-separator hook mangles a long quoted prompt argument after `&&`/`cd`, and codex then dies with "No prompt provided via stdin".
- Prompt shape: "experienced machinist, NO other context, could you manufacture this part from this sheet alone? Report (1) blockers (2) ambiguities/contradictions (3) standards/readability (4) items to confirm."

**How to apply:** triage findings into (a) cheap note-text fixes — do them; (b) view/layout changes (hidden-lines-visible view, dim repositioning) — do if one rebuild; (c) foundation-level (GD&T frames, title-block rows, watermark, decimal display) — file on the foundations PR instead. Stop after ~2 rounds ([[codex-review-diminishing-returns]]); the reviewer will always want a full production drawing package.
