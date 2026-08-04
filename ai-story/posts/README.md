# Drafts

One file per essay: `NNN-<slug>.md`. Plan in [`../outline.md`](../outline.md).

## Frontmatter

```yaml
---
title: "…"
status: outline | drafted | sourced | published
essay: 1              # position in ../outline.md
sources_verified: false   # every claim cited AND checked, not just cited
---
```

`sourced` is the gate that matters: it means someone re-ran every citation and
the claim still holds. A draft may not be published at `drafted`.

## Process

1. Outline the argument.
2. **Pull the evidence first** ([`../evidence/README.md`](../evidence/README.md))
   and let it change the argument — that's the point of doing it in this order.
3. Draft.
4. Verify every citation by re-running it.
5. `/humanizer` pass.
6. Flip `sources_verified` to true, then publish.

_No drafts yet._
