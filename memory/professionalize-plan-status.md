---
name: professionalize-plan-status
description: "Progress on the professionalize-cad plan (Parts A–F); what's done, what remains in Part F"
metadata: 
  node_type: memory
  type: project
  originSessionId: 045bacc1-f12e-48b0-b137-916b2b43a02d
---

Executing `C:\Users\pedro\.claude\plans\i-want-to-professionalize-stateful-star.md` on branch `professionalize-cad`. Each commit fast-forward-pushed to `origin/main` (user wants main to track the work; `git push origin professionalize-cad:main` + `git branch -f main professionalize-cad`).

**DONE (pushed to main):**
- A (prune comparisons to ch30 8-views), B1 (retire C#/KCL), B2 (README + docs/), C (YAML config layer + `_config.py` + generated DIMENSIONS.md from dimensions.yaml), E (gitignore binaries).
- B3/B4: `verify.py` + `truth_model.py`.
- **D**: tolerance metadata + custom properties — see [[part-d-custom-properties]].
- **F2**: output-proof gates in `truth` suite (single-channel-term, superposition, sawtooth-band-limited). truth suite 8/8.
- **F1**: `verify.py --suite isolation` — per-subsystem soundness gates, fresh session per assembly (CloseAllDocuments between; the 5th open's InterferenceDetectionManager came back null otherwise). Validated LIVE 27/27 across frame/drive-train/channel/output/harmonic-analyzer. Channel-independence gate = 20 independent instances of each moving stem (not pattern slaves); drive-train gear-ratios = crank 1:4 + 20 meshes. Component bands pinned (channel 144, drive-train 61, frame 13, output 123, harmonic-analyzer 4 SUBassemblies — top-level count not flattened). Skip `~$*.SLDASM` SW lock files in the glob.

`verify.py` suites: static / truth / config / isolation / **motion** / all. truth+config run with NO SolidWorks; static+isolation+motion need SW. Isolation suite ≈20 min (interference detection dominates). `all` = static+truth+config+motion.

**DONE — Part F (cont.):**
- **F3**: amplitude bars driven from `channels.yaml amplitude_mm` (square preset = 80/harmonic_n on odds, 0 on evens). inc1 = config/truth/verify (config suite asserts the square law, 14/14); inc2 = the 4-bar geometry drive in `build_channel_assembly.py` (`solve_state(amplitude)` bisects the bar tilt closing the lever-reach loop; bars fan visibly by harmonic at the 80mm scale, per-channel attached springs avoid the patterned-spring interference). Validated 6/6 channel gates @80mm. See [[parametric-springs]] for why the top-level plate fit needs LENGTH-parametric springs (task #10).
- **F4**: both engage/disengage config enums on drive-train.SLDASM are now config-scoped mate-suppress states (NOT re-pose+gear-mate): `cone_disengaged` (build_engagement_configs, 21 meshes cut) + `pinion_engaged` (build_pinion_engagement_configs, the lone alignment-pinion swing park driver `Distance42` suppressed → exactly the 3-member swing group free). Closes the tracked `pinion_engaged` config (dof-refactor (dropped memory)). REMAINING F4 polish: top-level `pinion_engaged` wiring (mirror `operating` in build_top_engagement_configs — flexible drive-train referencing the child config) so the swing shows through the full device.

- **F5 DONE + LIVE-VALIDATED (2026-06-16)**: kinematic pen driver — `pen_driver.py` (shared) equation-links the pen-rod travel mate to a STANDALONE `CrankDeg` global in output.SLDASM through a chained Fourier sum (S1..S20, PenY=Magnify·S20, PenScale, PenRest), reproducing `truth_model.pen_y` with NO force solver; computed-not-simulated. `verify.py --suite motion` sweeps CrankDeg + samples the pen-marker tip → PASSES 3/3 (tip traces truth_model worst **5.25e-05 mm**, interference-free at stroke extremes, 123 comps fully-defined). Top harmonic-analyzer re-validated 6/6 with the new output (rest pose CrankDeg=90 holds geometry bit-identical → no top rebuild needed). docs/motion-policy.md rewritten authoritative. Mechanics + the PenRest double-operator/exponent gotcha in [[pen-equation-driver]]. Plan verification step 9 (F5 half) MET.

- **F4 per-config DOF tests DONE + LIVE-VALIDATED (2026-06-16)**: `verify.py --suite engagement` promotes each build script's OWN per-config verifier into the standalone acceptance pass (lazy-imports build_engagement_configs/build_operating_config/build_pinion_engagement_configs/build_top_engagement_configs; `Report.agate` = async sibling of `gate` since the verifiers are async; `_open_isolated` = CloseAllDocuments+open per assembly). Opens drive-train + harmonic-analyzer, asserts each config frees EXACTLY the expected DOF set + the top references the matching child. PASSES **8/8** at validation 2026-06-16 (drive-train Default 0-DOF / cone_disengaged 42 decoupled / operating rotating-train / pinion_engaged 3-member swing; top 4 child-references rigid/flexible). **Now 6/6** — `pinion_engaged` retired 2026-06-18 (alignment-pinion removed, commit d32c110; see [[od-62mm-reanchor]]), so drive-train Default/cone_disengaged/operating × top references = 6 gates. 560s (engagement NOT in `all`, like isolation — too heavy). top-level pinion_engaged config was ALREADY built in build_top_engagement_configs. Plan verification step 9 (F4 half) MET.

**PART F COMPLETE** — F1 (isolation 27/27) + F2 (truth output proofs) + F3 (amplitude bars from config) + F4 (engagement — suite + the assembly configs themselves REMOVED 2026-06-19, see [[assembly-single-config]]; was 8/8 at validation, 6/6 after pinion_engaged retired) + F5 (motion 3/3) all DONE + live-validated. Plan verification step 9 fully met. Remaining plan tail = the from-scratch reproduction checks (step 1 `build_all.py --clean`, step 6 fresh-clone) — not run this session; the model + all suites validate against the on-disk build.

LESSON (cost a 20-min hang): NEVER run two `verify.py`/build scripts against SolidWorks at once — single STA COM server, they deadlock. And pipe long runs through `tee` to a log unbuffered (`PYTHONUNBUFFERED=1`), never `| grep | head` (block-buffers, looks frozen) — per updated global CLAUDE.md long-running-command rules.
