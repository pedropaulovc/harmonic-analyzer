---
name: load-bearing-claims-need-repro
description: A written "X doesn't work" claim that gates architecture must have a re-runnable repro stapled to it, or it calcifies into unfalsifiable folklore — the early-binding tax cost dozens of hours this way
metadata:
  type: feedback
---

The SolidWorks COM adapter forced **late binding everywhere** on an explicit,
written, WRONG claim: a runbook section titled *"Late binding is forced, always"*
(`SolidworksMCP-python/CLAUDE.md`) with a confident rationale — "early-bound
wrappers reject the VARIANT pass-by-ref out-parameters used by `OpenDoc6`". False.
makepy invokes by DISPID through `InvokeTypes`, which describes each `[out]` param
from the typelib and returns it in the result tuple; `OpenDoc6` works early-bound
with `pythoncom.Missing` exactly as late-bound. The false premise made every COM
object pay `flag_methods`' per-name `GetIDsOfNames`/`_FlagAsMethod` round-trips
(~155 ms/object, ~90% of the drawing-audit overhead in issue #277, plus a steady
tax on every part build) — dozens of hours of wasted build/iteration time before
the wholesale early-bound migration (this branch) disproved it.

**Origin (git archaeology, 2026-07-12):** the flag-methods architecture landed in
upstream `andrewbartels1/SolidworksMCP-python` **PR #14** ("STA-thread COM executor
+ per-interface method flagging", merged 2026-05-14), commits `166b26b`/`58edfd7`
by author DPerrault. Reviewed by `copilot-pull-request-reviewer[bot]` (a comment)
and human-approved twice by andrewbartels1 — **NOT reviewed by Codex**. Neither
reviewer caught the false premise, because the CODE was correct (late binding does
work); reviewers check the correctness of what's written, not whether an unstated
architectural premise ("early binding CAN'T work here") is true. An automated
reviewer (Copilot) cannot flag "you assumed a thing that's false" when the
assumption compiles and runs.

**Why:** a load-bearing "X doesn't work" claim, once written into a runbook as
gospel with a plausible rationale, becomes UNFALSIFIABLE folklore — every future
reader inherits it as fact and designs around it, and the cost compounds silently
because nothing ever re-tests it. The rationale being *specific and technical*
made it MORE trusted, not less. The claim named a falsifiable mechanism (VARIANT
byref rejection) but never stapled a re-runnable repro proving that mechanism —
so the one thing that would have caught it (run `OpenDoc6` early-bound, see it
work) was never in the repo.

**How to apply:**
- When you WRITE a claim that gates architecture ("we must use X because Y fails"),
  staple a re-runnable repro to it — a script/test that demonstrates the failure,
  checked in next to the claim. A claim with a named mechanism but no repro is a
  hypothesis wearing a fact's clothes.
- When you INHERIT such a claim (runbook, comment, prior agent, upstream code),
  treat it as a hypothesis until you find its repro. If there's no repro, the claim
  is unverified regardless of how confident or detailed the prose is — spend the few
  minutes to falsify it before building on it, ESPECIALLY when it's expensive
  (forces a slow/ugly pattern across the whole codebase).
- Codebase conventions that look like settled fact can rest on a single untested
  assumption from one PR. Human + automated (Copilot) review does not catch a false
  premise that produces working code. Don't assume "it's been reviewed" means the
  premise was checked.
- This is the inherited-claim twin of [[no-untested-failure-assumptions]] (don't
  build fallbacks on unverified failure assumptions) and
  [[negative-result-positive-control]] (get a positive control before declaring an
  API dead). Same root: a "doesn't work" verdict without an empirical, re-runnable
  demonstration is not evidence. Here the verdict came from someone else and
  calcified — which is exactly why it survived so long.
