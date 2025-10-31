# Summing Lever Implementation Plan

## Project Overview
Creating a parametric KCL model of the summing lever component for the harmonic analyzer based on reference photo and hand-drawn sketches.

## Design Decisions Made
- **Units:** Imperial (inches) - consistent with other CAD files in project
- **Design approach:** Organic curves - attempting to match the flowing transitions in the reference photo
- **Dimensions source:** User-provided hand sketches
- **Fulcrum detail:** Simple hole/slot approach
- **Workflow:** Incremental phases with PNG + STL exports and git commits after each phase

## Key Dimensions (from sketches)
- Total lever length: 13" (vertical in sketch)
- Base thickness: 1/8"
- Paddle section width: 3"
- Paddle section length: ~5" (estimated)
- Lower section width: 4" (from sketch)
- Counter arm width: 2"
- Counter spring hole: 1" diameter
- Fulcrum position: 10" from left end
- Transition radii: 1/3" (tight curves), 2" (gradual transitions)
- Mounting holes: 20 total (5 across × 4 rows), 0.125" diameter, aligned on left short edge

## Current Status

### ✅ COMPLETED

#### Phase 1: Setup & Basic Outline
- Created `summing-lever.kcl` with:
  - `@settings(defaultLengthUnit = in, kclVersion = 1.0)`
  - Input parameters section
  - Calculated parameters section
  - Parameter assertions
  - Basic rectangular paddle outline (3" × 5" × 1/8")
- **Commit:** `085de85` - "Implement summing lever Phases 1-2: basic outline and mounting holes"

#### Phase 2: Paddle with Mounting Holes
- Added 4×5 grid of mounting holes (20 holes total)
- Used `subtract2d` before extrusion (best practice)
- Fixed hole positioning to align on short edge:
  - 5 holes across the 3" width
  - 4 rows going 0.5" deep into the paddle
  - Starting 0.25" from left edge
- **Files:** `summing-lever-phase2-aligned.png`, `output.stl`
- **Commit:** `7a23e74` - "Fix summing lever mounting hole alignment"

### 🔲 REMAINING PHASES

#### Phase 3: Add Organic Curves & Transitions
**Goal:** Replace straight edges with curves to match the flowing design in the reference photo

**Steps:**
1. Replace straight line segments with `tangentialArc` or `arc` calls
2. Key areas to add curves:
   - Paddle outer edges (use gentle curves for flowing design)
   - Round corners for smoother transitions
   - Any internal corners (use smaller radii for tight curves)
3. Important KCL constraint: Use EITHER:
   - `tangentialArc(angle = ..., radius = ...)` OR
   - `tangentialArc(end = [x, y])` alone
   - NOT both together
4. Build incrementally - add one curve, test, then continue
5. Export and review:
   ```bash
   zoo kcl snapshot summing-lever.kcl summing-lever-phase3.png
   zoo kcl export --output-format=stl summing-lever.kcl .
   ```
6. Commit using Task tool

**What to check:** Curves flow smoothly, profile is closed properly, proportions look good

---

#### Phase 4: Add Center Fulcrum Section
**Goal:** Extend lever geometry from paddle to center section with fulcrum mounting

**Steps:**
1. Read current `summing-lever.kcl` to see the paddle profile
2. Extend the lever profile to include:
   - Continue from paddle edge to fulcrum position
   - Add width transition (paddle is 3" wide, may need to taper/expand)
   - Add fulcrum slot/hole at center position
3. Create fulcrum geometry:
   - Simple rectangular slot (`fulcrumSlotWidth = 0.5"`, `fulcrumSlotLength = 1.0"`)
   - Position at `fulcrumPosition` along length
   - Use `subtract2d` for slot before final extrusion
4. Keep geometry simplified (rectangular sections, apply curves consistent with Phase 3)
5. Export and review:
   ```bash
   zoo kcl snapshot summing-lever.kcl summing-lever-phase4.png
   zoo kcl export --output-format=stl summing-lever.kcl .
   ```
6. Commit using Task tool with message about adding fulcrum section

**What to check:** Fulcrum position looks correct, slot is visible, overall proportions make sense

---

#### Phase 5: Add Counter-Weight Arm
**Goal:** Add the right-side counter-weight arm with spring hole

**Steps:**
1. Extend profile from fulcrum to right end (counter arm)
2. Add counter arm section:
   - Width: `counterWidth = 2.0"`
   - Length: calculated as `counterArmLength = leverLength - fulcrumPosition - 2.0`
   - Include organic shaping/tapering to match sketch
3. Add counter spring hole:
   - Diameter: `counterHoleDiam = 1.0"`
   - Position: near right end (`counterHolePosition`)
   - Use `subtract2d` before extrusion
4. Apply curves/transitions consistent with Phase 4 style
5. Export and review:
   ```bash
   zoo kcl snapshot summing-lever.kcl summing-lever-phase5.png
   zoo kcl export --output-format=stl summing-lever.kcl .
   ```
6. Commit using Task tool

**What to check:** Full lever profile from left paddle to right counter-weight, all holes visible, overall length ~13" (or as adjusted)

---

#### Phase 6: Apply Fillets & Finishing
**Goal:** Add edge fillets and final refinements for realistic appearance

**Steps:**
1. Identify edges to fillet (after extrusion):
   - Use tags on profile edges during sketch creation
   - Target: `edgeFillet = 0.0625"` (1/16") for main edges
2. Apply fillets:
   ```kcl
   |> fillet(radius = edgeFillet, tags = [edge1, edge2, ...])
   ```
3. Consider which edges should be sharp vs rounded based on reference photo
4. Final parameter validation:
   - Run all assertions
   - Check for any KCL lint warnings:
     ```bash
     zoo kcl lint summing-lever.kcl
     ```
5. Format code:
   ```bash
   zoo kcl format summing-lever.kcl -w
   ```
6. Final exports:
   ```bash
   zoo kcl snapshot summing-lever.kcl summing-lever-final.png
   zoo kcl export --output-format=stl summing-lever.kcl .
   zoo kcl export --output-format=step summing-lever.kcl .
   zoo kcl volume summing-lever.kcl
   zoo kcl surface-area summing-lever.kcl
   ```
7. Commit using Task tool with final message

**What to check:** Realistic edge treatments, no sharp corners where there should be fillets, clean geometry

---

## Commands Reference

### At Each Phase Checkpoint:
```bash
# 1. Create snapshot
zoo kcl snapshot summing-lever.kcl summing-lever-phaseN.png

# 2. Export STL
zoo kcl export --output-format=stl summing-lever.kcl .

# 3. View the PNG to review
# (use Read tool or open in image viewer)

# 4. Commit changes (use Task tool, never git directly)
# Task tool with subagent_type=general-purpose will handle git operations
```

### Useful Validation Commands:
```bash
# Check for syntax errors
zoo kcl format summing-lever.kcl -w

# Lint for best practices
zoo kcl lint summing-lever.kcl

# Get volume
zoo kcl volume summing-lever.kcl

# Get surface area
zoo kcl surface-area summing-lever.kcl

# Get mass (cast iron ~0.26 lb/in³ = 7200 kg/m³)
zoo kcl mass summing-lever.kcl --material-density=7200 --material-density-unit=kg-m3
```

## File Organization

**Note:** All summing-lever files are now organized in the `cad/summing-lever/` directory.

### Source Files (in summing-lever/):
- `summing-lever.kcl` - Main source file (work in progress)
- `summing-lever.jpg` - Reference photo
- `summing-lever-sketch.png` - Hand-drawn dimension sketches
- `SUMMING-LEVER-PLAN.md` - This planning document

### Generated Files (per phase, in summing-lever/):
- `summing-lever-phase1.png` - Phase 1 snapshot
- `summing-lever-phase2-18ga.png` - Phase 2 final snapshot (18ga holes, single line)
- `summing-lever-phase2.stl` - Phase 2 STL export
- `summing-lever-phase3.png` - Phase 3 snapshot (to be created)
- `summing-lever-phase4.png` - Phase 4 snapshot (to be created)
- `summing-lever-phase5.png` - Phase 5 snapshot (to be created)
- `summing-lever-final.png` - Phase 6 final snapshot (to be created)

### Working Directory:
When working on the summing lever, ensure you're in the `cad/summing-lever/` directory, or use full paths.

## Important KCL Constraints & Best Practices

### Engine Limitations to Remember:
1. **Always use `subtract2d` for holes BEFORE extruding** - 3D subtract operations are unreliable
2. **Arc parameters:** Use `tangentialArc(angle=..., radius=...)` OR `tangentialArc(end=[x,y])`, not both
3. **Patterns over repetition:** Use `patternLinear2d` instead of creating individual holes
4. **Close sketches:** Profiles must be closed before extrusion
5. **Union limitations:** `union()` may fail if solids don't touch - keep parts separate if needed

### File Structure Requirements:
1. Start with `@settings(defaultLengthUnit = in, kclVersion = 1.0)`
2. Organize as: Input params → Calculated params → Assertions → Geometry
3. Add descriptive comments explaining design intent
4. Use meaningful variable names

### Git Workflow:
- **ALWAYS use Task tool for git operations** - never run git commands directly
- Commit after EVERY phase completion
- Include Claude Code attribution footer in commits
- Push periodically (can do at end of session)

## Resume Instructions

When resuming this work:

1. **Check current status:**
   ```bash
   git log --oneline -5  # See recent commits
   ls -la summing-lever*.png  # See what phases have snapshots
   ```

2. **Read the current implementation:**
   ```
   Use Read tool on summing-lever.kcl to see current state
   ```

3. **Check todo list:**
   ```
   Review this SUMMING-LEVER-PLAN.md to see what phase is next
   ```

4. **Continue from next pending phase:**
   - Follow the steps for that phase
   - Export PNG + STL after changes
   - Review and get user approval
   - Commit using Task tool
   - Move to next phase

## Questions to Resolve (if needed)

- [ ] Should total length be 13" (from sketch) or 20" (currently in code)?
- [ ] What should width be at center section? (sketch shows 4")
- [ ] How much should counter arm taper? (sketch shows ~2" at end)
- [ ] Should there be any boss/reinforcement features?
- [ ] Material properties for mass calculations? (assuming cast iron)

## Reference Files
- Main photo: `summing-lever.jpg` - shows actual cast green lever with organic curves
- User sketches: Provided via images showing dimensions and side view

---

**Created:** 2025-10-31
**Last Updated:** 2025-10-31 (Phase 2 complete, phases 3-4 swapped)
**Next Phase:** Phase 3 - Add organic curves & transitions
