# AGENTS.md — web/

TypeScript + Vite + three.js. No SolidWorks, no COM.
**The `/developing-solidworks` skill is not required here** — but if a task
sends you into `cad/scripts/export_models.py` to change what the GLB contains,
it is.

## Rules

1. **Never hand-edit anything under `public/models/`.** The GLB is a CAD build
   artefact. It arrives via `npm run fetch-model` and is gitignored. If the
   model is wrong, fix the CAD, not the asset.
2. **Kinematics stays free of three.js.** `src/kinematics.ts` imports nothing
   and is the only place the machine's ratios live. Motion derived from the
   1898 paper and `cad/config/machine/gear_train.yaml` — cite the source in a
   comment when you add a ratio. If you need a number, read it out of the
   config; do not eyeball it from the model.
3. **Joints bind by name.** Add a joint by adding a `Binding` in
   `src/bindings.ts`, never by indexing into the glTF node array. An unresolved
   binding must warn and degrade, never throw.
4. **The page must work with no model.** A fresh checkout has no GLB. The load
   failure path is a supported state with a useful message, not an error.
5. **`npm run build` runs `tsc --noEmit` first.** Keep it green — strict mode
   with `noUncheckedIndexedAccess` is on deliberately, because the code is full
   of `arrays[i]` over twenty channels.
6. **Narration copy comes from the transcripts.** `references/engineerguy-youtube/*.vtt`
   for pacing and beat order — paraphrase, never paste. The videos are
   copyrighted; the structure is not.

## What this is for

Two audiences: someone who watched the videos and wants to poke at the machine,
and someone deciding whether to back the Kickstarter. Both want to *understand
the mechanism*, so favour clarity over spectacle — a slow crank with a visible
cam and a visible trace beats a cinematic fly-through.

## Verify before claiming done

`npm run build` passing is necessary, not sufficient. If you changed anything
visual or kinematic, run `npm run dev` and look at it — a joint driven on the
wrong axis typecheck-passes perfectly.
