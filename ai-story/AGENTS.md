# AGENTS.md — ai-story/

Writing about how AI was used on this project. There is an obvious conflict of
interest here: an agent writing about how useful agents were.

**Handle it by never writing an unsourced claim.**

## Rules

1. **Every factual claim carries a citation** — a commit SHA, a PR number, a
   `memory/` filename, a file path, or a number from
   `cad/out/reports/telemetry/`. A claim you cannot cite is a claim you cut.
2. **Do not soften the failures.** If the record shows a mechanism was built,
   used for months, and then deleted because it was a recurring bug source
   (`memory/default-free-dof-park-drivers.md`), that is the story. Write it
   plainly.
3. **Do not editorialise about AI in general.** This is one project's
   experience. Generalisations are for the reader to make.
4. **No invented metrics.** Not "roughly 10,000 lines", not "about 80%". Count
   it or omit it. `git log`, `gh pr list`, `memory/usage.jsonl` and the
   telemetry captures are right there.
5. **Anonymise nothing that's already public**, and publish nothing that isn't.
   The repo is public; `agent-sessions-backup/` and any local transcripts are
   not, and may contain paths, keys or personal detail. Quote from them only
   after the user has reviewed the quote.
6. **The user's voice, not the agent's.** First person singular, and it's the
   user's first person. Draft; don't ventriloquise conclusions they haven't
   reached. Run drafts through `/humanizer`.

## A note on self-assessment

When an agent writes this section, it is grading its own homework. Prefer
evidence that is adversarial to the flattering conclusion: reverted commits,
review comments that caught real bugs, memory files that begin "this claim was
wrong". If a draft reads as favourable to AI, that is a signal to go looking
for the counter-evidence, not to publish.
