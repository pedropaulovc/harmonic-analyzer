---
name: developing-kcl
description: Writes, modifies, and debugs KCL (KittyCAD Language) code for parametric 3D CAD modeling. Use when working with .kcl files, code-first CAD, parametric geometry, or when the user mentions KCL, KittyCAD, or zoo CLI tools.
---

# KCL Development Skill

Expert guidance for code-first CAD modeling with KCL (KittyCAD Language).

## CRITICAL WORKFLOW

Before writing ANY KCL code:
1. Read [kcl-guide-for-llm.md](./kcl-guide-for-llm.md) for current syntax and patterns
2. ABORT if you cannot access the documentation - your default knowledge may be outdated
3. Verify your approach aligns with documented best practices

## Core Patterns

### Standard File Structure

Every KCL file must follow this structure (see guide for details):
```kcl
// Part description

@settings(defaultLengthUnit = mm, kclVersion = 1.0)

// Input parameters
width = 20

// Calculated parameters
area = width * height

// Assertions
assert(width, isGreaterThan = 0, error = "Width must be positive")

// Geometry
part = startSketchOn(XY)
  |> rectangle(width = width, height = height, center = [0, 0])
  |> extrude(length = thickness)
```

### Creating Holes (Reliability Order)

See guide for complete patterns. Prefer in this order:

**BEST: Negative extrude**
```kcl
base = extrude(baseProfile, length = 10)
holes = startSketchOn(base, face = END)
  |> circle(radius = 5)
  |> extrude(length = -10.1)  // NEGATIVE CUTS
```

**GOOD: 2D subtract before extrude**
```kcl
profile = rectangle(...)
  |> subtract2d(tool = holeProfile)
  |> extrude(length = 10)
```

**AVOID: 3D booleans** (engine limitation - may fail)

### Tag Usage

- Declare with `$`: `line(end = [10, 0], tag = $edge1)`
- Reference without `$`: `fillet(tags = [edge1])`

## Development Workflow

Copy this checklist for complex parts:

```
KCL Development:
- [ ] Read relevant sections of kcl-guide-for-llm.md
- [ ] Write code following standard structure
- [ ] Export to STL: zoo kcl export --output-format=stl file.kcl .
- [ ] Validate output
```

### Feedback Loop Pattern

For quality-critical code:

1. **Write code** following documented patterns
2. **Lint immediately**: `zoo kcl lint file.kcl`
3. **Fix issues** if lint fails
4. **Lint again** until passing
5. **Export**: `zoo kcl export --output-format=stl file.kcl .`
6. **Verify output**

## Required Knowledge

Consult the guide for:
- **Syntax patterns**: 2D sketching, 3D operations, patterns, transforms
- **Query functions**: `profileStartX()`, `segEndY()`, etc.
- **Known limitations**: 3D booleans, arc syntax, transform constraints
- **Zoo CLI tools**: export, format, lint, snapshot, volume, mass, etc.

## Key Principles (See Guide for Details)

- **Immutable variables**: Never reassign
- **Pipeline operator**: Chain with `|>`
- **Unit-aware**: Include units (mm, deg) in all values
- **Negative extrude for holes**: Preferred over 3D subtract
- **Patterns not repetition**: Use `patternLinear2d`, `patternCircular2d`
- **Assertions for validation**: Check parameters early

## Code Quality Checklist

Before delivering:
- [ ] Consulted kcl-guide-for-llm.md
- [ ] File starts with `@settings` directive
- [ ] Variables never reassigned
- [ ] Pipeline operator `|>` used for chaining
- [ ] Tags declared with `$`, used without
- [ ] Units included in numeric values
- [ ] Assertions validate critical parameters
- [ ] Using recommended patterns (see guide)
- [ ] Will export to STL

## When to Ask User

- Geometry might hit known engine limitations (see guide)
- Multiple valid approaches exist
- Unit preferences needed (mm vs in)
- Manufacturing constraints required

## Example Workflows

### Creating a Parametric Part

**User**: "Create a mounting plate with 4 corner holes"

**Steps**:
1. Read [kcl-guide-for-llm.md](./kcl-guide-for-llm.md) hole creation section
2. Define parameters: plate dimensions, hole diameter, hole offset
3. Add assertions for dimensional validity
4. Create base using `rectangle` + `extrude`
5. Add holes using `patternCircular2d` + `subtract2d` (or negative extrude)
6. Export: `zoo kcl export --output-format=stl file.kcl .`

### Debugging KCL Code

**User**: "My code fails: [snippet]"

**Steps**:
1. Compare against kcl-guide-for-llm.md patterns
2. Check common issues:
   - Immutability violation
   - Missing units
   - Wrong arc syntax
   - 3D boolean usage
3. Provide corrected code
4. Explain root cause and prevention

### Best Practices Questions

**User**: "How should I create holes in KCL?"

**Steps**:
1. Reference guide's hole creation section
2. Explain reliability order: negative extrude > subtract2d > 3D subtract
3. Show code example
4. Mention engine limitation for 3D booleans
