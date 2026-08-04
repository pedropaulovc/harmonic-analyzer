# Outline

Working title: **_Receipts: what actually happened when I built a
nineteenth-century computer with AI agents_**

Format undecided — companion book, main-book appendix, or blog series. The
material decides. Write the essays first; they stand alone either way.

## Arc

A software engineer with no machining experience sets out to reproduce a
machine that has never been documented, using LLM agents for essentially all of
the code. Three years of commits later, here is what that was actually like.

The reader is a working engineer who is tired of both the hype and the backlash
and wants to know what the artefacts look like.

## Essays

### 1. The premise problem

The single most expensive failure mode in this project: confident, well-written,
reviewed work built on a premise nobody checked. Not bad code — code that was
correct given an assumption that was wrong.

Material: the "load-bearing claims need a repro" rule
(`memory/load-bearing-claims-need-repro.md`,
`memory/no-untested-failure-assumptions.md`,
`memory/negative-result-positive-control.md`) and the incidents that produced
them. Also `AGENTS.md`: *"It was reviewed" ≠ "the premise was checked" — review
verifies written code, not unstated architectural premises.*

### 2. Feedback loops are the whole game

Where agents were superb: anywhere a gate could fail loudly. Interference
checks, degree-of-freedom assertions, mass-property fingerprints, renders you
can eyeball. Where they were dangerous: geometry that looked right and wasn't.

Material: the `verify:*` and `check:*` suites; the photo-vs-CAD comparison
gallery as the loop that made the model converge; the merge gate in `AGENTS.md`
that requires **visual inspection of renders** because "the CAD gates prove
volumes and mates, not that the geometry LOOKS like the machine".

### 3. Building the wrong machine twice

Mechanisms built, used, and then deleted — with the reasoning recorded.

Material:
- The **park drivers**: two-sided deferred mates, a `locked` build mode, and a
  release-time 0-DOF closure proof — killed because placement already made the
  build deterministic and the replay path was a recurring bug source
  (`memory/default-free-dof-park-drivers.md`).
- The **COM task_dep spine**: a topological linearization of every COM task,
  replaced by a file lock, because the fake edges made the dependency graph lie
  (`memory/com-seat-lock.md`).
- The `subsystems` verify suite: ~95 % duplicate COM work, folded away
  (`memory/checks-perf-value-audit.md`).

Each was a reasonable design that survived review and turned out to be wrong at
a level review doesn't reach.

### 4. Working against an API the model has barely seen

The SolidWorks COM API: ~9,000 methods, inconsistent naming, silent `null`
returns instead of exceptions, and thin training coverage. What it takes to make
an agent productive against that — offline docs as a bundled skill, a learnings
log, and a hard rule that a clean build proves nothing until you run it.

Material: the `developing-solidworks` skill, and the SolidWorks entries in
`memory/` (`sw-zombie-doc-lock`, `mate-flip-determinism`,
`solidworks-center-rectangle-determinism`, `hole-wizard-com-recipe`, …).

### 5. The memory problem

130+ files of findings, because agents don't remember and neither do I. What
makes a memory worth writing, what makes it rot, and what happens when a stale
memory sends you the wrong way.

Material: `memory/`, `memory/MEMORY.md`, `memory/never-final.md`.

### 6. Performance work nobody asked for

Agents will happily accept a 25-minute build. Where the wins actually came from
once someone looked: a 2-second-per-process stall because an OTLP exporter
resolved `localhost` to IPv6 first; a 274-second no-op assembly refresh doing
gates that re-proved a previous save; a cross-machine cache that missed
everywhere because the digest embedded absolute paths.

Material: `AGENTS.md` telemetry section, `memory/release-perf-incremental.md`,
`memory/v018-perf-review.md`, `cad/out/reports/telemetry/`.

### 7. Review at scale

Hundreds of PRs with automated review. What automated review caught that I
didn't, what it missed, and what it flagged that was noise. The
diminishing-returns finding (`memory/codex-review-diminishing-returns.md`) is
the interesting one — and worth a real count, not an impression.

### 8. What I'd do differently

The honest list. Written last.

## Themes running through

- **Verification is the product.** The code was cheap; being sure it was right
  was the whole cost.
- **Loud failure over graceful degradation.** Every place this project got
  burned, something had quietly succeeded when it should have screamed.
- **A shape can pass every check and still be visibly wrong.** The literal
  merge-gate rule, and a decent metaphor for the rest of it.
- **Cost.** Real numbers from `memory/usage.jsonl`, or it doesn't go in.

## Open questions

- **Format.** Appendix (reaches machinists who don't care) vs blog series
  (reaches engineers who do) vs companion book (most work). Lean: blog series
  first, collect later if it lands.
- **How much machining in it?** The machining is the interesting *contrast* —
  a domain where you cannot fake the feedback loop. Probably essay 9.
- **Timing.** Publishing during the campaign draws a different audience than the
  book's. Could help; could dilute.
