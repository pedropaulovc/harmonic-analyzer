# KCL Constraint Solver Language Extension Proposal

> A language extension for KCL (KittyCAD Language) that adds a full geometric constraint solver, enabling declarative constraint-based sketching alongside KCL's existing procedural approach.

## Motivation

KCL currently uses **procedural construction**: calculate exact coordinates, then draw. Traditional CAD uses **declarative constraints**: draw approximate geometry, then solve for constraints. This extension bridges both paradigms.

### The Problem

In the `summing-lever.kcl` middle rib, tangent points between lines and arcs are calculated manually:

```kcl
// Current: Manual trigonometric calculations
arcOffsetX = arcRadius * sin(45deg)
arcOffsetZ = arcRadius * cos(45deg)

middleRib = startSketchOn(XZ)
  |> startProfile(at = [-coefficientsPlateWidth, cylinderCenterZ])
  |> line(endAbsolute = [cylinderCenterX - arcOffsetX, cylinderCenterZ + arcOffsetZ])
  |> arc(interiorAbsolute = [0, arcRadius], endAbsolute = [arcOffsetX, arcOffsetZ])
  // ... more manual geometry
```

**Issues:**
1. Tangent points are approximated using 45-degree assumption
2. If arc radius changes, tangent points need manual recalculation
3. Symmetry is manual (upper/lower geometry mirrored by negating coordinates)
4. No validation that geometry actually satisfies design intent

### The Solution

When translating to SolidWorks, these constraints are expressed directly:

```csharp
// SolidWorks: Declarative constraints
swModel.SketchAddConstraints("sgTANGENT");  // line1 tangent to arc1
swModel.SketchAddConstraints("sgCORADIAL"); // arc1 and arc2 same center & radius
swModel.SketchAddConstraints("sgSYMMETRIC"); // symmetric about centerline
```

The solver computes exact tangent points automatically. This proposal brings similar capabilities to KCL.

---

## Syntax Design

### Recommended Approach: Inline Constraint Operator

```kcl
sketch = startSketchOn(XZ)
  |> startProfile(at = [leftX, 0], tag = $leftVertex)
  |> line(end = [approx, approx], tag = $line1)
  |> arc(radius = r, sweep = 90deg, tag = $arc1)
  |> line(endAbsolute = [rightX, 0], tag = $line2)
  |> close(tag = $line3)
  |> constrain([
       tangent($line1, $arc1),
       coradial($arc1, $arc2),
       symmetric($line1, $line3, about = X),
       fix($leftVertex)
     ])
  |> solve()
  |> extrude(length = thickness)
```

**Rationale:**
- Fits KCL's pipe operator style
- Constraints grouped logically after geometry definition
- Explicit `solve()` makes constraint solving intent clear
- Approximate coordinates become initial guesses for the solver

---

## Entity Reference System

### Extended Tag System

KCL already has tags (`tag = $name`). The constraint system extends this with point accessors:

```kcl
// Tag an entity
line(end = [10, 0], tag = $bottomEdge)

// Reference points on tagged entities
pointAt($bottomEdge, START)   // Start point of line
pointAt($bottomEdge, END)     // End point of line
pointAt($bottomEdge, MID)     // Midpoint
centerOf($arc1)               // Center of arc/circle
```

### Entity Types and Properties

| Entity Type | Accessible Points |
|-------------|-------------------|
| `line` | `START`, `END`, `MID` |
| `arc` | `START`, `END`, `MID`, `CENTER` |
| `circle` | `CENTER` |
| `point` | (the point itself) |

---

## Constraint Types

### Geometric Relations

| Constraint | Syntax | Description | DOF Removed |
|------------|--------|-------------|-------------|
| **Tangent** | `tangent($line, $arc)` | Line tangent to arc at connection | 1 |
| **Coradial** | `coradial($arc1, $arc2)` | Same center AND radius | 3 |
| **Concentric** | `concentric($arc1, $arc2)` | Same center (radii may differ) | 2 |
| **Symmetric** | `symmetric($e1, $e2, about = $axis)` | Mirror about line/axis | varies |
| **Parallel** | `parallel($l1, $l2)` | Lines are parallel | 1 |
| **Perpendicular** | `perpendicular($l1, $l2)` | Lines are perpendicular | 1 |
| **Horizontal** | `horizontal($line)` | Line is horizontal | 1 |
| **Vertical** | `vertical($line)` | Line is vertical | 1 |
| **Collinear** | `collinear($l1, $l2)` | Lines on same infinite line | 2 |

### Dimensional Constraints

| Constraint | Syntax | Description | DOF Removed |
|------------|--------|-------------|-------------|
| **Distance** | `distance($p1, $p2, value = 10mm)` | Fixed distance between points | 1 |
| **Angle** | `angle($l1, $l2, value = 45deg)` | Angle between lines | 1 |
| **Length** | `length($line, value = 25mm)` | Segment length | 1 |
| **Radius** | `radius($arc, value = 10mm)` | Arc/circle radius | 1 |
| **Equal Length** | `equalLength($l1, $l2)` | Same length | 1 |
| **Equal Radius** | `equalRadius($a1, $a2)` | Same radius | 1 |

### Coincident/Connection Constraints

| Constraint | Syntax | Description | DOF Removed |
|------------|--------|-------------|-------------|
| **Coincident** | `coincident($p1, $p2)` | Points at same location | 2 |
| **Point on Line** | `pointOnLine($point, $line)` | Point lies on line | 1 |
| **Point on Arc** | `pointOnArc($point, $arc)` | Point lies on arc/circle | 1 |
| **Midpoint** | `midpoint($point, $line)` | Point at segment midpoint | 2 |
| **Fix** | `fix($point)` | Lock point position | 2 |

---

## Construction Geometry

Non-rendering geometry for constraint references:

```kcl
sketch = startSketchOn(XZ)
  // Construction geometry (not extruded)
  |> constructionLine(from = [0, 0], to = [100, 0], tag = $hCenterline)
  |> constructionCircle(center = [0, 0], radius = clearanceRadius, tag = $clearanceCircle)

  // Actual geometry
  |> startProfile(at = [leftX, 0], tag = $start)
  |> line(end = [10, 10], tag = $line1)
  |> arc(tag = $arc1)
  // ...

  |> constrain([
       // Arcs lie on clearance circle
       onCircle($arc1, $clearanceCircle),
       // Symmetry about centerline
       symmetric($line1, $line4, about = $hCenterline)
     ])
  |> solve()
```

---

## Error Handling

### Constraint Status

```kcl
// After solve(), query constraint status
status = sketchConstraintStatus(sketch)
// Returns: FULLY_CONSTRAINED | UNDER_CONSTRAINED | OVER_CONSTRAINED | CONFLICTING
```

### Under-Constrained Detection

```kcl
sketch = startSketchOn(XY)
  |> line(end = [10, 0], tag = $line1)
  |> line(end = [0, 10], tag = $line2)
  |> close()
  |> constrain([
       perpendicular($line1, $line2)
       // Missing: fixed point, length constraints
     ])
  |> solve()  // Warning: Under-constrained by 3 DOF

// Query what's missing
dof = degreesOfFreedom(sketch)  // Returns: 3
suggestions = suggestConstraints(sketch)
// Returns: ["fix(pointAt($line1, START))", "length($line1)", "length($line2)"]
```

### Over-Constrained Detection

```kcl
sketch = startSketchOn(XY)
  |> rectangle(width = 10, height = 5, tag = $rect)
  |> constrain([
       length(edge($rect, TOP), value = 10mm),
       length(edge($rect, BOTTOM), value = 12mm),  // Conflict!
     ])
  |> solve()  // Error: Over-constrained - conflicting lengths

errors = constraintErrors(sketch)
// Returns: [{ type: "CONFLICT", constraints: ["length(TOP)", "length(BOTTOM)"] }]
```

### Soft Constraints (Optional)

```kcl
// Soft constraints for best-fit solutions
|> constrain([
     length($line1, value = 10mm, priority = HARD),   // Must satisfy
     angle($line1, value = 0deg, priority = SOFT),    // Best effort
   ])
```

---

## Complete Example: Middle Rib

### Current Procedural KCL

```kcl
// From summing-lever.kcl - manual calculation approach
arcRadius = cylinderRadius + ribPadding
arcAngleOffset = 45deg
arcOffsetX = arcRadius * sin(arcAngleOffset)
arcOffsetZ = arcRadius * cos(arcAngleOffset)

middleRib = startSketchOn(XZ)
  |> startProfile(at = [-coefficientsPlateWidth, cylinderCenterZ], tag = $leftVertex)
  |> line(endAbsolute = [cylinderCenterX - arcOffsetX, cylinderCenterZ + arcOffsetZ])
  |> arc(
       interiorAbsolute = [cylinderCenterX, cylinderCenterZ + arcRadius],
       endAbsolute = [cylinderCenterX + arcOffsetX, cylinderCenterZ + arcOffsetZ]
     )
  |> line(endAbsolute = [summationPlateTipX, cylinderCenterZ])
  |> line(endAbsolute = [cylinderCenterX + arcOffsetX, cylinderCenterZ - arcOffsetZ])
  |> arc(
       interiorAbsolute = [cylinderCenterX, cylinderCenterZ - arcRadius],
       endAbsolute = [cylinderCenterX - arcOffsetX, cylinderCenterZ - arcOffsetZ]
     )
  |> line(endAbsolute = segEnd(leftVertex))
  |> close()
  |> extrude(length = ribThickness, symmetric = true)
```

### Proposed Constrained KCL

```kcl
// Constraint-based approach - solver computes tangent points
arcRadius = cylinderRadius + ribPadding
pivotCenter = [cylinderCenterX, cylinderCenterZ]

middleRib = startSketchOn(XZ)
  // Construction: horizontal centerline for symmetry
  |> constructionLine(
       from = [-coefficientsPlateWidth, 0],
       to = [summationPlateTipX, 0],
       tag = $hCenterline
     )

  // Profile with approximate geometry (solver will adjust)
  |> startProfile(at = [-coefficientsPlateWidth, 0], tag = $leftVertex)
  |> line(end = [20, 10], tag = $upperLeft)
  |> arc(center = pivotCenter, radius = arcRadius, tag = $upperArc)
  |> line(endAbsolute = [summationPlateTipX, 0], tag = $upperRight)
  |> line(end = [-20, -10], tag = $lowerRight)
  |> arc(center = pivotCenter, radius = arcRadius, tag = $lowerArc)
  |> close(tag = $lowerLeft)

  |> constrain([
       // Tangent line-arc transitions (smooth corners)
       tangent($upperLeft, $upperArc),
       tangent($upperArc, $upperRight),
       tangent($lowerRight, $lowerArc),
       tangent($lowerArc, $lowerLeft),

       // Both arcs share center and radius
       coradial($upperArc, $lowerArc),

       // Arcs centered on pivot cylinder
       coincident(centerOf($upperArc), pivotCenter),

       // Fixed radius
       radius($upperArc, value = arcRadius),

       // Symmetry about horizontal centerline
       symmetric($upperLeft, $lowerLeft, about = $hCenterline),
       symmetric($upperRight, $lowerRight, about = $hCenterline),
       symmetric($upperArc, $lowerArc, about = $hCenterline),

       // Ground the sketch (fix endpoint positions)
       fix($leftVertex),
       fix(pointAt($upperRight, END))
     ])
  |> solve()
  |> extrude(length = ribThickness, symmetric = true)
```

### Benefits of Constrained Approach

1. **No manual tangent calculation** - solver finds exact points
2. **Symmetry enforced** - not approximated by coordinate negation
3. **Self-documenting** - constraints express design intent
4. **Robust to changes** - modify `arcRadius` and tangent points auto-update
5. **Validated geometry** - solver ensures constraints are satisfied

---

## New Functions Summary

### Constraint Functions

| Function | Purpose |
|----------|---------|
| `constrain([...])` | Apply constraint list to sketch |
| `solve()` | Trigger constraint solver |

### Query Functions

| Function | Purpose |
|----------|---------|
| `sketchConstraintStatus(sketch)` | Get FULLY/UNDER/OVER_CONSTRAINED status |
| `degreesOfFreedom(sketch)` | Get remaining DOF count |
| `suggestConstraints(sketch)` | Get suggestions for under-constrained |
| `constraintErrors(sketch)` | Get detailed conflict information |

### Reference Functions

| Function | Purpose |
|----------|---------|
| `pointAt($tag, position)` | Get point on entity (START, END, MID) |
| `centerOf($arc)` | Get arc/circle center point |
| `edge($shape, side)` | Get edge of rectangle/polygon |

### Construction Geometry

| Function | Purpose |
|----------|---------|
| `constructionLine(from, to, tag)` | Non-rendering line for constraints |
| `constructionCircle(center, radius, tag)` | Non-rendering circle for constraints |
| `constructionPoint(at, tag)` | Non-rendering point for constraints |

---

## Backward Compatibility

- Existing procedural sketches work unchanged
- `constrain()` and `solve()` are optional additions
- Sketches without `solve()` use explicit geometry as before
- Mixed mode: some geometry procedural, some constrained

---

## Implementation Notes

### Constraint Solver Requirements

A geometric constraint solver (e.g., [Slvs](https://github.com/solvespace/solvespace/tree/master/include/slvs.h), Planern) would need to:

1. **Parse constraints into equation system** - Each constraint becomes equations
2. **Build Jacobian matrix** - For Newton-Raphson iteration
3. **Solve iteratively** - Find geometry satisfying all constraints
4. **Update sketch geometry** - Replace approximate values with solved values

### Degrees of Freedom Analysis

| Entity | Initial DOF |
|--------|-------------|
| Point | 2 |
| Line (2 points) | 4 |
| Arc (center + 2 endpoints) | 6 |
| Circle (center + radius) | 3 |

Constraints remove DOF until the sketch has 0 remaining (fully constrained).

### Engine Integration

This extension would require KittyCAD engine support for:
- Geometric constraint solver library integration
- DOF analysis and reporting
- Incremental re-solving when parameters change
- Error reporting for conflicting/redundant constraints

---

## Appendix: SolidWorks Constraint Reference

The SummingLever SolidWorks implementation uses these constraints:

| SolidWorks | Proposed KCL | Usage |
|------------|--------------|-------|
| `sgTANGENT` | `tangent($line, $arc)` | Line-arc smooth transition |
| `sgCORADIAL` | `coradial($arc1, $arc2)` | Arcs share center and radius |
| `sgSYMMETRIC` | `symmetric($e1, $e2, about = $axis)` | Mirror about centerline |
| `sgCONCENTRIC` | `concentric($a1, $a2)` | Share center only |
| `sgPARALLEL` | `parallel($l1, $l2)` | Parallel lines |
| `sgPERPENDICULAR` | `perpendicular($l1, $l2)` | Perpendicular lines |
| `sgHORIZONTAL` | `horizontal($line)` | Horizontal line |
| `sgVERTICAL` | `vertical($line)` | Vertical line |
| `sgCOINCIDENT` | `coincident($p1, $p2)` | Points at same location |
| `sgFIXED` | `fix($entity)` | Lock position |
