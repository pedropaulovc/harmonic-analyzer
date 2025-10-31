# KCL (KittyCAD Language) Reference Guide for LLMs

## Core Principles

1. **Code-first CAD**: KCL is a programming language specifically designed for CAD modeling
2. **Immutable variables**: Variables cannot be reassigned once declared
3. **Pipeline-oriented**: Use `|>` operator to chain operations cleanly
4. **Unit-aware**: Numbers carry unit information (mm, in, deg, rad, etc.)
5. **Tagged geometry**: Use tags (`$tagName`) to reference geometry for later operations

## Design Strategy for LLMs

When creating KCL parts, follow this workflow for best results:

1. **Plan 2D first**: Design your 2D profile completely including all holes/cutouts
2. **Use subtract2d**: Add holes using `subtract2d` on the 2D profile
3. **Then extrude**: Only extrude to 3D after the 2D profile is complete
4. **Avoid 3D boolean ops**: Minimize use of `union` and 3D `subtract` due to engine limitations
5. **Keep it simple**: For complex assemblies, keep parts as separate variables instead of unioning
6. **Test incrementally**: Build complex parts by adding features one at a time

**Good workflow:**
```
2D profile → add 2D holes → extrude → add features on faces → done
```

**Problematic workflow (avoid):**
```
extrude → create separate 3D holes → subtract (may fail!)
```

## Known Engine Limitations and Workarounds

**IMPORTANT**: The KCL engine has some limitations as of 2025. Understanding these will save significant time:

### 3D Boolean Operation Limitations

1. **Union of non-touching solids**: `union([solid1, solid2, solid3])` may fail if the solids don't share edges/faces
   - **Workaround**: Keep parts separate, or use `method = MERGE` when extruding from existing geometry

2. **Multiple subtract operations**: Complex `subtract(tools = [many_holes])` operations may fail
   - **Workaround**: Use 2D operations (`subtract2d`) on profiles BEFORE extruding to 3D

3. **Subtract with transformed geometry**: Subtracting geometry that has been translated/rotated may fail
   - **Workaround**: Create subtract tools in their final position, not transformed after creation

### Preferred Workflow for Parts with Holes

**ALWAYS prefer this approach:**

```kcl
// 1. Create 2D profile
basePlate = startSketchOn(XY)
  |> rectangle(width = 100, height = 50, center = [0, 0])

// 2. Create holes as 2D profile
holes = startSketchOn(XY)
  |> circle(center = [20, 0], radius = 5)
  |> patternLinear2d(axis = X, instances = 3, distance = 30)

// 3. Subtract in 2D (more reliable than 3D subtract)
plateWithHoles = basePlate
  |> subtract2d(tool = holes)
  |> extrude(length = 10)
```

**Avoid this approach when possible:**
```kcl
// This may fail due to engine limitations
plate = startSketchOn(XY)
  |> rectangle(width = 100, height = 50, center = [0, 0])
  |> extrude(length = 10)

holes = startSketchOn(XY)
  |> circle(center = [20, 0], radius = 5)
  |> extrude(length = 10)

plateWithHoles = subtract([plate], tools = [holes])  // May fail!
```

### Arc and Curve Limitations

1. **tangentialArc parameter combinations**: Must use EITHER:
   - `tangentialArc(angle = ..., radius = ...)` OR
   - `tangentialArc(end = [x, y])` (without radius)
   - NOT `tangentialArc(end = [...], radius = ...)` together

### Rendering Limitations

1. **zoo kcl snapshot**: Does not support view parameters
   - No `--view=front`, `--view=side`, etc.
   - Always produces isometric/default view
   - To get different views, rotate your model in the code

## Basic Syntax

### Variables
```kcl
width = 20      // Immutable - cannot reassign
height = 10
area = width * height
```

### Functions
```kcl
// All parameters must be labeled when calling (except first if marked with @)
// @ prefix makes the first parameter positional/unlabeled
fn makeCube(@size, color) {
  return startSketchOn(XY)
    |> startProfile(at = [0, 0])
    |> line(end = [size, 0])
    |> line(end = [0, size])
    |> line(end = [-size, 0])
    |> close()
    |> extrude(length = size)
    |> appearance(color = color)
}

// Call with labeled args (first unlabeled due to @)
cube = makeCube(10, color = "#ff0000")

// Functions can have type annotations
fn makeBox(@width: number(mm), height: number(mm), depth: number(mm)) {
  return startSketchOn(XY)
    |> rectangle(width = width, height = height, center = [0, 0])
    |> extrude(length = depth)
}
```

### Pipeline Operator
```kcl
// Clean chaining with |>
sketch = startSketchOn(XY)
  |> startProfile(at = [0, 0])
  |> line(end = [10, 0])
  |> line(end = [0, 10])
  |> close()
  |> extrude(length = 5)

// The % symbol represents the left side value (often implicit for first unlabeled param)
x = 10 |> sqrt(%) |> pow(%, exp = 2)
```

### Conditionals
```kcl
// if/else expressions (must have else branch)
thickness = if partSize > 100 {
  5
} else if partSize > 50 {
  3
} else {
  2
}

// Conditional geometry
profile = if needHoles {
  baseProfile |> subtract2d(tool = holes)
} else {
  baseProfile
}
```

## Units of Measurement

### Length Units
- `mm` - millimeters (often default)
- `cm` - centimeters
- `m` - meters
- `in` - inches
- `ft` - feet
- `yd` - yards

### Angle Units
- `deg` - degrees
- `rad` - radians

### Usage
```kcl
line(end = [10mm, 5in])  // Mixed units auto-convert
extrude(length = 2.5cm)
revolve(angle = 180deg)

// Type ascription for unit assertions
// Use `: type` syntax when KCL cannot infer units (e.g., with PI calculations)
radius = (circumference / (2 * PI)): mm  // Asserts result should be mm
angle = (degrees * PI / 180): rad        // Asserts result should be radians

// For area/volume calculations - convert to same unit first
area = units::toMillimeters(width) * units::toMillimeters(height)  // Result in mm²
```

**Important**: Type ascription (`: type`) only asserts/validates units, it doesn't convert them. For actual unit conversion, use `units::` functions like `units::toMillimeters()`. KCL doesn't have built-in area or volume units.

## 2D Sketching Workflow

### 1. Choose a plane
```kcl
startSketchOn(XY)   // Z points up (default for horizontal surfaces)
startSketchOn(XZ)   // Y points down (good for side views)
startSketchOn(YZ)   // X points out (good for front/back views)
startSketchOn(-XY)  // Z points down (flipped normal)
startSketchOn(-XZ)  // Y points up (flipped normal)
startSketchOn(-YZ)  // X points in (flipped normal)
startSketchOn(offsetPlane(XY, offset = 10))  // Parallel plane, offset along normal
```

### 2. Start a profile
```kcl
startProfile(at = [0, 0])  // Starting point
```

### 3. Draw paths
```kcl
// Basic lines
line(end = [10, 5])           // Relative: move 10 right, 5 up from current point
line(endAbsolute = [20, 30])  // Absolute: go to exact position [20, 30]
xLine(length = 10)            // Horizontal line (relative)
yLine(length = 5)             // Vertical line (relative)
angledLine(angle = 45deg, length = 10)  // Line at angle (relative)

// Arcs and curves
arc(angleStart = 0, angleEnd = 90deg, radius = 5)
tangentialArc(end = [10, 0], radius = 5)
bezierCurve(control1 = [5, 10], control2 = [10, 10], end = [15, 0])

// Shapes
circle(center = [0, 0], radius = 5)
rectangle(width = 10, height = 5, center = [0, 0])
polygon(numSides = 6, radius = 10, center = [0, 0])
```

### 4. Close the sketch
```kcl
close()  // Completes the profile loop
```

### 5. Add holes and cutouts (BEFORE extruding to 3D)

**CRITICAL**: Always add holes using 2D operations before extruding to 3D:

```kcl
// Create base profile
base = startSketchOn(XY)
  |> rectangle(width = 50, height = 30, center = [0, 0])

// Create hole pattern
mountingHoles = startSketchOn(XY)
  |> circle(center = [15, 10], radius = 2)
  |> patternLinear2d(axis = X, instances = 2, distance = 20)

// Subtract in 2D, then extrude
plate = base
  |> subtract2d(tool = mountingHoles)
  |> extrude(length = 5)
```

This approach is much more reliable than creating 3D holes after extrusion.

## 3D Operations

### Extrude
```kcl
extrude(length = 10)
extrude(length = 10, symmetric = true)  // Extrude both directions
extrude(twistAngle = 90deg, length = 10)  // Twisted extrude
```

### Revolve
```kcl
revolve(axis = Y, angle = 360deg)
revolve(axis = Y, angle = 180deg)  // Partial revolve
```

### Sweep
```kcl
// Define a path for the sweep
sweepPath = startSketchOn(XZ)
  |> startProfile(at = [0, 0])
  |> line(end = [0, 10])
  |> tangentialArc(angle = 90deg, radius = 5)
  |> line(end = [10, 0])

// Create a profile to sweep
profile = startSketchOn(XY)
  |> circle(center = [0, 0], radius = 2)

// Sweep the profile along the path
sweptSolid = sweep(profile, path = sweepPath)
```

### Loft
```kcl
// Create multiple profiles on different planes
profile1 = startSketchOn(XY)
  |> circle(center = [0, 0], radius = 10)

profile2 = startSketchOn(offsetPlane(XY, offset = 20))
  |> rectangle(width = 20, height = 20, center = [0, 0])

loft([profile1, profile2])
```

## Tags and References

### Declaring Tags
```kcl
sketch = startSketchOn(XY)
  |> startProfile(at = [0, 0])
  |> line(end = [10, 0], tag = $edge1)  // Declare with $
  |> line(end = [0, 10], tag = $edge2)
  |> line(end = [-10, 0], tag = $edge3)
  |> close(tag = $edge4)
```

### Using Tags
```kcl
// Reference without $ to use the tag
solid = extrude(sketch, length = 5)
  |> fillet(radius = 2, tags = [edge1, edge2])  // No $ when using

// Special face tags
solid = extrude(sketch, length = 5)
startSketchOn(solid, face = START)  // Bottom face
startSketchOn(solid, face = END)    // Top face
```

### Tag Relationships
```kcl
getOppositeEdge(edge1)         // Get edge on opposite face
getNextAdjacentEdge(edge1)     // Get next adjacent edge
getPreviousAdjacentEdge(edge1) // Get previous adjacent edge
```

### Query Tags
```kcl
segLen(edge1)           // Get length of segment
segAng(edge1)           // Get angle of segment
segStart(edge1)         // Get start point [x, y]
segEnd(edge1)           // Get end point [x, y]
profileStart()          // Get profile start point
profileStartX()         // Get profile start X coordinate
```

## Solid Operations

**⚠️ WARNING**: 3D boolean operations have engine limitations. Prefer 2D operations (`subtract2d`) on profiles before extruding when possible. See "Known Engine Limitations" section.

### Boolean Operations
```kcl
union([solid1, solid2, solid3])              // Combine solids (may fail if non-touching)
subtract([baseSolid], tools = [toolSolid])   // Cut away (may fail with multiple tools)
intersect([solid1, solid2])                  // Keep only overlap
```

**Recommended alternative for holes:**
```kcl
// Instead of 3D subtract, use 2D subtract before extrude:
plate = startSketchOn(XY)
  |> rectangle(width = 100, height = 50, center = [0, 0])
  |> subtract2d(tool = holeProfile)  // 2D operation
  |> extrude(length = 10)
```

### Edge Operations
```kcl
fillet(radius = 2, tags = [edge1, edge2])    // Round edges
chamfer(length = 2, tags = [edge1])          // Cut edges at angle
chamfer(length = 2, angle = 45deg, tags = [edge1])
```

### Shell Operations
```kcl
shell(faces = [END], thickness = 2)  // Hollow with open face
hollow(thickness = 2)                 // Hollow completely
```

### Patterns
```kcl
// Linear pattern
patternLinear3d(axis = X, instances = 5, distance = 10)

// Circular pattern
patternCircular3d(
  axis = Z,
  center = [0, 0, 0],
  instances = 12,
  arcDegrees = 360,
  rotateDuplicates = true
)

// Custom transform pattern
fn transform(@i) {
  return { translate = [i * 10, 0, 0], scale = [1, 1, 1 + i * 0.1] }
}
patternTransform(instances = 5, transform = transform)
```

## Transformations

```kcl
translate(x = 10, y = 5, z = 3)
rotate(pitch = 45deg, yaw = 30deg)
rotate(axis = Z, angle = 90deg)
scale(x = 2, y = 1.5, z = 1)
mirror2d(axis = X)  // For sketches only
```

## Cloning Geometry

```kcl
// Clone creates an independent copy that can be transformed separately
originalSketch = startSketchOn(XY)
  |> circle(center = [0, 0], radius = 5)
  |> extrude(length = 10)

// Create a clone and transform it
clonedPart = clone(originalSketch)
  |> translate(x = 20, y = 0, z = 0)
  |> scale(z = 2)

// Both original and clone exist independently
```

## Sketch on Face

```kcl
// Extrude creates faces from edges
solid = startSketchOn(XY)
  |> startProfile(at = [0, 0])
  |> line(end = [10, 0], tag = $bottom)
  |> line(end = [0, 10])
  |> line(end = [-10, 0])
  |> close()
  |> extrude(length = 10)

// Sketch on the face that grew from the tagged edge
startSketchOn(solid, face = bottom)
  |> circle(center = [5, 5], radius = 2)
  |> extrude(length = 5)
```

## Common Patterns

### Parametric Design
```kcl
// Define parameters at top
width = 20
height = 10
thickness = 2
filletRadius = 1

// Use throughout design
sketch = startSketchOn(XY)
  |> startProfile(at = [-width/2, -height/2])
  |> line(end = [width, 0], tag = $edge1)
  |> line(end = [0, height], tag = $edge2)
  |> line(end = [-width, 0], tag = $edge3)
  |> close(tag = $edge4)
  |> extrude(length = thickness)
  |> fillet(radius = filletRadius, tags = [
       getNextAdjacentEdge(edge1),
       getNextAdjacentEdge(edge2),
       getNextAdjacentEdge(edge3),
       getNextAdjacentEdge(edge4)
     ])
```

### Reusable Functions
```kcl
fn flange(numHoles, holeRadius, flangeRadius, thickness) {
  holes = startSketchOn(XY)
    |> circle(radius = holeRadius, center = [flangeRadius * 0.7, 0])
    |> patternCircular2d(
         center = [0, 0],
         instances = numHoles,
         arcDegrees = 360,
         rotateDuplicates = true
       )

  return startSketchOn(XY)
    |> circle(radius = flangeRadius, center = [0, 0])
    |> subtract2d(tool = holes)
    |> extrude(length = thickness)
}

myFlange = flange(numHoles = 8, holeRadius = 5, flangeRadius = 50, thickness = 10)
```

### Using Map and Reduce
```kcl
// Map: transform each element
offsets = [0, 25, 50, 75]
cubes = map(offsets, f = fn(@offset) {
  return startSketchOn(XY)
    |> rectangle(width = 10, height = 10, center = [offset, 0])
    |> extrude(length = 10)
})

// Reduce: accumulate a value
numbers = [1, 2, 3, 4, 5]
sum = reduce(numbers, initial = 0, f = fn(@item, accum) {
  return accum + item
})

// Array operations
arr = [1, 2, 3, 4, 5]
first = arr[0]           // Access by index (0-based)
last = arr[count(arr)-1] // Get last element
newArr = push(arr, item = 6)  // Add element
concatArr = concat(arr, items = [7, 8, 9])  // Combine arrays
```

## Important Constants

```kcl
// Standard planes: XY, XZ, YZ
sketch1 = startSketchOn(XY) |> circle(center = [0, 0], radius = 5)

// Negative planes (flipped normal): -XY, -XZ, -YZ
sketch2 = startSketchOn(-XY) |> circle(center = [0, 0], radius = 5)

// 3D axes: X, Y, Z
solid1 = extrude(sketch1, length = 10)
  |> patternLinear3d(instances = 3, distance = 15, axis = X)

// Math constants: PI, E, TAU
circumference = 20
radius = (circumference / (2 * PI)): mm
area = E * TAU

// Special face tags: START, END
solid2 = extrude(sketch2, length = 10)
sketch3 = startSketchOn(solid2, face = END)
  |> circle(center = [0, 0], radius = 2)

// Extrusion methods: NEW (separate solid), MERGE (default, extends existing)
cylinder1 = extrude(sketch3, length = 5, method = NEW)
```

## Assertions and Validation

```kcl
assert(value, isEqualTo = 10)
assert(value, isGreaterThan = 0, isLessThan = 100)
assert(value, isEqualTo = 5.0, tolerance = 0.001)
assertIs(booleanValue)  // Assert true
```

## Common Gotchas

1. **Variables are immutable** - Cannot reassign
2. **All function parameters must be labeled** (except first if marked with `@`)
3. **Tags declared with `$`, used without** - `tag = $myTag` vs `tags = [myTag]`
4. **Units in arithmetic** - `10in * 2` gives 20in, not 20cm
5. **Close your sketches** - Profiles must be closed before extrusion
6. **Pipeline first param** - If function's first param is marked `@`, it's automatically filled from pipeline
7. **Arrays are 0-indexed** - First element is `arr[0]`, not `arr[1]`
8. **Imports must be at top** - Import statements cannot be inside functions or conditionals
9. **Sketch on face coordinates** - When sketching on a face, coordinates use the global coordinate system, not the face's local system
10. **Method parameter** - `extrude(method = NEW)` creates a separate solid; `method = MERGE` (default) extends/modifies existing solid
11. **3D Boolean limitations** - `union` and `subtract` operations may fail; prefer 2D operations before extruding
12. **Arc parameter combinations** - `tangentialArc` needs EITHER `angle + radius` OR just `end` point, not both
13. **Snapshot views** - `zoo kcl snapshot` only produces default isometric view; rotate model in code for other views
14. **2D before 3D** - Always add holes/cutouts using `subtract2d` on 2D profiles before extruding to 3D

## Module System

```kcl
// Export from module
// utils.kcl
export fn myFunction(x) { return x * 2 }
export myConstant = 42

// Import in another file
import myFunction, myConstant from "utils.kcl"
import "utils.kcl" as utils  // Import entire module
```

**Important**: Import statements must be at the top level of a file, before any other code (comments are allowed).

## Experimental Features

Some features require enabling experimental features:

```kcl
@settings(experimentalFeatures = allow)

// Now you can use experimental features like:
// - hole::hole() and related hole functions
// - gdt::datum() and gdt::flatness()
```

## Best Practices

1. **Use descriptive variable names** - `flangeRadius` not `r`
2. **Define parameters at top** - Makes modification easier
3. **Tag geometry you'll reference** - Edges for fillets, faces for sketching
4. **Break complex models into functions** - Reusability and clarity
5. **Use units explicitly** - Especially when mixing systems
6. **Comment non-obvious calculations** - Help future readers
7. **Validate with assertions** - Catch errors early

## Example: Complete Part

```kcl
// Parameters
baseWidth = 50
baseHeight = 30
baseThickness = 5
bossDiameter = 20
bossHeight = 15
mountHoleDia = 6
mountHoleOffset = 35

// Create base plate profile
basePlateProfile = startSketchOn(XY)
  |> startProfile(at = [-baseWidth/2, -baseHeight/2])
  |> line(end = [baseWidth, 0], tag = $frontEdge)
  |> line(end = [0, baseHeight], tag = $rightEdge)
  |> line(end = [-baseWidth, 0], tag = $backEdge)
  |> close(tag = $leftEdge)

// Create mounting holes pattern IN 2D
mountingHoles = startSketchOn(XY)
  |> circle(center = [mountHoleOffset/2, 0], radius = mountHoleDia/2)
  |> patternCircular2d(
       center = [0, 0],
       instances = 4,
       arcDegrees = 360,
       rotateDuplicates = true
     )

// Subtract holes in 2D BEFORE extruding
basePlate = basePlateProfile
  |> subtract2d(tool = mountingHoles)
  |> extrude(length = baseThickness)
  |> fillet(radius = 2, tags = [
       getNextAdjacentEdge(frontEdge),
       getNextAdjacentEdge(rightEdge),
       getNextAdjacentEdge(backEdge),
       getNextAdjacentEdge(leftEdge)
     ])

// Boss on top (extrude from face of base)
boss = startSketchOn(basePlate, face = END)
  |> circle(center = [0, 0], radius = bossDiameter/2)
  |> extrude(length = bossHeight)

// Note: boss uses method=MERGE by default, so it joins with basePlate automatically
```

## CLI Usage

```bash
# Format code
zoo kcl format main.kcl -w

# Export to different formats
zoo kcl export --output-format=step main.kcl ./output
zoo kcl export --output-format=stl main.kcl ./output
zoo kcl export --output-format=obj main.kcl ./output

# Create snapshot
zoo kcl snapshot main.kcl output.png

# Get volume/mass/surface area
zoo kcl volume main.kcl
zoo kcl mass main.kcl --material-density=2700 --material-density-unit=kg-m3
zoo kcl surface-area main.kcl

# Lint code
zoo kcl lint main.kcl
```

## Debugging Tips

1. **Use assertions liberally** - Validate dimensions and relationships
2. **Break complex operations** - Split into smaller, testable functions
3. **Check units** - Ensure consistent units throughout calculations
4. **Validate tags** - Ensure tags are declared before use
5. **Use comments** - Document design intent and constraints

## Common Functions Reference

- **Sketch**: `startSketchOn`, `startProfile`, `line`, `arc`, `circle`, `close`
- **3D**: `extrude`, `revolve`, `sweep`, `loft`
- **Boolean**: `union`, `subtract`, `intersect`
- **Modify**: `fillet`, `chamfer`, `shell`, `hollow`
- **Pattern**: `patternLinear3d`, `patternCircular3d`, `patternTransform`
- **Transform**: `translate`, `rotate`, `scale`, `mirror2d`
- **Query**: `segLen`, `segAng`, `profileStart`, `getOppositeEdge`
- **Utility**: `clone`, `assert`, `assertIs`

This guide covers the essential KCL concepts and patterns needed for effective CAD modeling in KittyCAD's KCL language.
