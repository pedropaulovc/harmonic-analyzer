# Evidence

Where the receipts are, and how to pull them. **Nothing goes in a draft that
can't be sourced from one of these.**

## In-repo sources

| source | what it proves | how to read it |
|---|---|---|
| `git log` | what changed, when, and why — commit messages here carry context first, then the change, then verification | `git log --format='%h %ad %s' --date=short` |
| `memory/` | 130+ findings, mostly bugs that cost real time | `memory/MEMORY.md` is the index |
| `AGENTS.md` | design decisions **with their history**: several sections end in a "(History: this replaced X — see memory/Y)" note | read the parenthetical asides; that's where the reversals are |
| `docs/` | the engineering assessments: assumptions, known limitations, DFM, tolerances | `docs/known-limitations.md` is the most honest file in the repo |
| `cad/out/reports/telemetry/` | real span durations and log records per build | `traces.jsonl` / `logs.jsonl`, one OTel record per line |
| `cad/out/reports/cache.jsonl` | every cache hit/miss/store, with keys | append-only event log |
| `memory/usage.jsonl` | token/cost accounting | the only defensible source for cost claims |
| `comparisons/` | how close the model got to the photographs, over time | `scores.json` is a regression trend, comparable within one render engine |

## GitHub sources

```bash
# every merged PR, oldest first
gh pr list --state merged --limit 1000 --json number,title,mergedAt,additions,deletions \
  --jq 'sort_by(.mergedAt)[] | "\(.number)\t\(.mergedAt[:10])\t+\(.additions)/-\(.deletions)\t\(.title)"'

# review comments on one PR (what automated review actually caught)
gh pr view <N> --json reviews,comments

# releases: what shipped, and when
gh release list --limit 100
```

## Useful queries

```bash
# reversals: mechanisms that were built and then removed
git log --format='%h %s' | rg -i 'revert|remove|retire|replace|kill|drop'

# memory files that record a wrong claim
rg -l -i 'was wrong|turned out|actually|does not|myth|folklore' memory/

# the slowest operations on record (calibrates every perf claim)
rg '"name"' cad/out/reports/telemetry/traces.jsonl | head

# how many parts, assemblies, gates
ls cad/scripts/build_*.py | wc -l
```

## Not evidence

- **`agent-sessions-backup/` and any local transcripts.** They may contain
  paths, keys and personal detail, and they are not public. Quote only after
  the user has reviewed the specific quote.
- **Anything remembered rather than looked up.** Including by me.
- **Impressions of how much AI "did".** There is no defensible measure of that
  and reaching for one is where this genre loses its credibility.

## The counter-evidence habit

Before publishing an essay that concludes something flattering, spend a pass
looking for the record that contradicts it. Reverted commits, review comments
that caught a real bug, and memory files that begin by correcting an earlier
belief are the highest-yield places to look.
