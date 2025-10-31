# KCL (KittyCAD Language) Reference Guide for LLMs

## Core Principles

1. **Code-first CAD**: KCL is a programming language specifically designed for CAD modeling
2. **Immutable variables**: Variables cannot be reassigned once declared
3. **Pipeline-oriented**: Use `|>` operator to chain operations cleanly
4. **Unit-aware**: Numbers carry unit information (mm, in, deg, rad, etc.)
5. **Tagged geometry**: Use tags (`$tagName`) to reference geometry for later operations

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

// Type ascription for complex expressions
area = (width * height): mm  // Assert result is in mm
```

## 2D Sketching Workflow

### 1. Choose a plane
```kcl
startSketchOn(XY)   // Or XZ, YZ, -XY, -XZ, -YZ
startSketchOn(offsetPlane(XY, offset = 10))  // Offset plane
```

### 2. Start a profile
```kcl
startProfile(at = [0, 0])  // Starting point
```

### 3. Draw paths
```kcl
// Basic lines
line(end = [10, 5])           // Relative distance
line(endAbsolute = [20, 30])  // Absolute position
xLine(length = 10)            // Horizontal line
yLine(length = 5)             // Vertical line
angledLine(angle = 45deg, length = 10)

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
// Define a path
sweepPath = startSketchOn(XZ)
  |> startProfile(at = [0, 0])
  |> line(end = [0, 10])
  |> tangentialArc(angle = 90deg, radius = 5)
  |> line(end = [10, 0])

// Sweep a profile along path
profile = startSketchOn(XY)
  |> circle(center = [0, 0], radius = 2)
  |> sweep(path = sweepPath)
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

### Boolean Operations
```kcl
union([solid1, solid2, solid3])              // Combine solids
subtract([baseSolid], tools = [toolSolid])   // Cut away
intersect([solid1, solid2])                  // Keep only overlap
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
  |> rectangle(width = width, height = height, center = [0, 0])
  |> extrude(length = thickness)
  |> fillet(radius = filletRadius, tags = getAllEdges())
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
```

## Important Constants

```kcl
// Planes
XY, XZ, YZ          // Standard planes
-XY, -XZ, -YZ       // Negative planes (flipped normal)

// Axes
X, Y, Z             // 3D axes

// Special tags
START               // Starting face of extrusion
END                 // Ending face of extrusion

// Math constants
PI                  // 3.14159...
E                   // 2.71828...
TAU                 // 6.28318... (2π)

// Extrusion methods
NEW                 // Create separate solid
MERGE               // Merge with existing (default)
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

// Base plate
basePlate = startSketchOn(XY)
  |> startProfile(at = [-baseWidth/2, -baseHeight/2])
  |> line(end = [baseWidth, 0], tag = $frontEdge)
  |> line(end = [0, baseHeight], tag = $rightEdge)
  |> line(end = [-baseWidth, 0], tag = $backEdge)
  |> line(end = [0, -baseHeight], tag = $leftEdge)
  |> close()
  |> extrude(length = baseThickness)
  |> fillet(radius = 2, tags = [
       getNextAdjacentEdge(frontEdge),
       getNextAdjacentEdge(rightEdge),
       getNextAdjacentEdge(backEdge),
       getNextAdjacentEdge(leftEdge)
     ])

// Boss on top
boss = startSketchOn(basePlate, face = END)
  |> circle(center = [0, 0], radius = bossDiameter/2)
  |> extrude(length = bossHeight)

// Mounting holes
holes = startSketchOn(basePlate, face = START)
  |> circle(center = [mountHoleOffset/2, 0], radius = mountHoleDia/2)
  |> patternCircular2d(
       center = [0, 0],
       instances = 4,
       arcDegrees = 360,
       rotateDuplicates = true
     )
  |> extrude(length = -baseThickness)

// Combine
finalPart = subtract([union([basePlate, boss])], tools = [holes])
```

## CLI Usage

```bash
# Format code
zoo kcl format main.kcl -w

# Export to different formats
zoo kcl export --output-format=step main.kcl ./output
zoo kcl export --output-format=stl main.kcl ./output

# Create snapshot
zoo kcl snapshot main.kcl output.png

# Get volume/mass/surface area
zoo kcl volume main.kcl
zoo kcl mass main.kcl --material-density=2700 --material-density-unit=kg-m3
zoo kcl surface-area main.kcl

# Lint code
zoo kcl lint main.kcl
```

This guide covers the essential KCL concepts and patterns needed for effective CAD modeling.
