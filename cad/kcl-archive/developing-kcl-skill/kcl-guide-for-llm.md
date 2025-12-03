# KCL (KittyCAD Language) Reference Guide for LLMs - Version 4

## Core Principles

1. **Code-first CAD**: Programming language for CAD modeling
2. **Immutable variables**: Cannot reassign once declared
3. **Pipeline-oriented**: Use `|>` operator to chain operations
4. **Unit-aware**: Numbers carry unit information (mm, in, deg, rad)
5. **Tagged geometry**: Use tags (`$tagName`) to reference geometry
6. **Negative extrude is king**: Use `extrude(length = -depth)` to cut geometry (preferred over 3D booleans)

## File Structure & Best Practices

**Every KCL file should follow this structure:**

```kcl
// 1. File header comment
// [Part Name] - [Description]

// 2. Settings (MANDATORY)
@settings(defaultLengthUnit = mm, kclVersion = 1.0)

// 3. Input parameters (user-modifiable)
width = 20
height = 10

// 4. Calculated parameters (derived)
area = width * height

// 5. Assertions (validate early)
assert(width, isGreaterThan = height, error = "Width must exceed height")

// 6. Geometry creation
// ... modeling code
```

**Key practices:**
- Use patterns (`patternLinear2d`, `patternCircular2d`), not repetitive code
- Add holes using `subtract2d` BEFORE extruding, OR use negative extrude from faces
- Tag geometry you'll reference: `tag = $myTag`, use without $: `tags = [myTag]`
- Use query functions (`profileStartX()`, `segEndY()`) for dynamic geometry
- Tag extrude faces: `extrude(length = 10, tagStart = $bottom, tagEnd = $top)`
- Axis can be vectors: `axis = [1, 1]` for diagonal, not just X/Y/Z constants

## Zoo CLI Tools

The `zoo` CLI provides essential tools for working with KCL files. All commands support stdin input using `-` as the file path.

### Format - Code Formatting

Format KCL files according to standard style guidelines:

```bash
# Output formatted code to stdout
zoo kcl format my-file.kcl

# Overwrite file in-place
zoo kcl format -w my-file.kcl

# From stdin
cat my-file.kcl | zoo kcl format -

# Custom tab size
zoo kcl format --tab-size 4 my-file.kcl

# Use tabs instead of spaces
zoo kcl format --use-tabs -w my-file.kcl
```

**Options:**
- `-w, --write`: Write output back to original file
- `--tab-size <N>`: Set tab size in spaces (default: 2)
- `--use-tabs`: Use tabs instead of spaces
- `--insert-final-newline`: Ensure/remove final newline

### Lint - Style & Quality Checks

Check KCL files for style issues and code quality problems:

```bash
# Basic lint check
zoo kcl lint my-file.kcl

# Show offending source code
zoo kcl lint -s my-file.kcl

# Show detailed descriptions and rationale
zoo kcl lint --descriptions my-file.kcl

# From stdin
cat my-file.kcl | zoo kcl lint -
```

**Options:**
- `-s, --show-code`: Display the problematic source code
- `--descriptions`: Show detailed explanations and rationale

**Best practice:** Always run `zoo kcl lint` before committing KCL files.

### Export - Convert to CAD Formats

Export KCL files to standard CAD and 3D model formats:

```bash
# Export to STL
zoo kcl export --output-format=stl my-file.kcl output_dir

# Export to STEP
zoo kcl export --output-format=step my-file.kcl .

# Export to OBJ
zoo kcl export --output-format=obj my-file.kcl output_dir

# From stdin
cat my-file.kcl | zoo kcl export --output-format=step - output_dir

# Deterministic output (no timestamps, useful for version control)
zoo kcl export --output-format=stl --deterministic my-file.kcl .
```

**Supported formats:**
- `stl`: STL (stereolithography) - widely supported for 3D printing
- `step`: STEP (ISO 10303-21) - industry standard for CAD interchange
- `obj`: Wavefront OBJ - common 3D model format
- `gltf`: glTF 2.0 (embedded, pretty printed) - modern 3D format
- `glb`: Binary glTF 2.0 - compact 3D format
- `fbx`: Autodesk Filmbox - animation and modeling format
- `ply`: PLY (Polygon File Format) - 3D scanning format

**Options:**
- `-t, --output-format`: Required - specify output format
- `--deterministic`: Remove timestamps for version control
- `--show-trace`: Print tracing data link for debugging

### Snapshot - Render Images

Generate rendered images of KCL models:

```bash
# Snapshot to PNG
zoo kcl snapshot my-file.kcl my-file.png

# Snapshot to JPEG
zoo kcl snapshot --output-format=jpeg my-file.kcl output.jpg

# From stdin
cat my-file.kcl | zoo kcl snapshot - output.png
```

**Supported formats:**
- `png`: PNG image (default, lossless)
- `jpeg`: JPEG image (lossy compression)

**Options:**
- `-t, --output-format`: Specify image format (png or jpeg)
- `--session <ID>`: Reuse existing modeling session
- `--replay`: Tell engine to store a replay
- `--show-trace`: Print tracing data link

**Use case:** Generate preview images for documentation, version control, or visual comparison.

### View - Terminal Preview

View a rendered preview of a KCL file directly in your terminal:

```bash
# View in terminal
zoo kcl view my-file.kcl

# From stdin
cat my-file.kcl | zoo kcl view -
```

**Use case:** Quick visual verification without opening external tools.

### Volume - Calculate Volume

Calculate the volume of objects in a KCL file:

```bash
# Volume in cubic millimeters
zoo kcl volume --output-unit=mm3 my-file.kcl

# Volume in cubic inches
zoo kcl volume --output-unit=in3 my-file.kcl

# Volume in liters
zoo kcl volume --output-unit=l my-file.kcl
```

**Supported units:**
- `mm3`: Cubic millimeters
- `cm3`: Cubic centimeters
- `m3`: Cubic meters
- `in3`: Cubic inches
- `ft3`: Cubic feet
- `yd3`: Cubic yards
- `l`: Liters
- `ml`: Milliliters
- `usfloz`: US Fluid Ounces
- `usgal`: US Gallons

**Options:**
- `-u, --output-unit`: Required - specify volume unit
- `-f, --format`: Output format (json, yaml, table)

### Mass - Calculate Mass

Calculate the mass of objects given material density:

```bash
# Mass of steel part (7850 kg/m³)
zoo kcl mass \
  --material-density=7850 \
  --material-density-unit=kg-m3 \
  --output-unit=kg \
  my-file.kcl

# Mass of aluminum part (2700 kg/m³) in grams
zoo kcl mass \
  --material-density=2700 \
  --material-density-unit=kg-m3 \
  --output-unit=g \
  my-file.kcl

# Mass in pounds with imperial density
zoo kcl mass \
  --material-density=490 \
  --material-density-unit=lb-ft3 \
  --output-unit=lb \
  my-file.kcl
```

**Density units:**
- `kg-m3`: Kilograms per cubic meter
- `lb-ft3`: Pounds per cubic foot

**Mass units:**
- `g`: Grams
- `kg`: Kilograms
- `lb`: Pounds

**Options:**
- `-m, --material-density`: Required - material density value
- `--material-density-unit`: Required - density unit
- `-u, --output-unit`: Required - output mass unit
- `-f, --format`: Output format (json, yaml, table)

**Common material densities (kg/m³):**
- Steel: 7850
- Aluminum: 2700
- Titanium: 4500
- Brass: 8400-8700
- Copper: 8960
- ABS plastic: 1040
- PLA plastic: 1250

### Surface Area - Calculate Surface Area

Calculate the surface area of objects:

```bash
# Surface area in square millimeters
zoo kcl surface-area --output-unit=mm2 my-file.kcl

# Surface area in square inches
zoo kcl surface-area --output-unit=in2 my-file.kcl
```

**Supported units:**
- `mm2`: Square millimeters
- `cm2`: Square centimeters
- `dm2`: Square decimeters
- `m2`: Square meters
- `km2`: Square kilometers
- `in2`: Square inches
- `ft2`: Square feet
- `yd2`: Square yards

**Options:**
- `-u, --output-unit`: Required - specify area unit
- `-f, --format`: Output format (json, yaml, table)

### Center of Mass - Calculate Center of Mass

Get the center of mass coordinates:

```bash
# Center of mass in millimeters
zoo kcl center-of-mass --output-unit=mm my-file.kcl

# Center of mass in inches
zoo kcl center-of-mass --output-unit=in my-file.kcl
```

**Supported units:**
- `mm`: Millimeters
- `cm`: Centimeters
- `m`: Meters
- `in`: Inches
- `ft`: Feet
- `yd`: Yards

**Options:**
- `-u, --output-unit`: Required - specify length unit
- `-f, --format`: Output format (json, yaml, table)

### Common Workflows

```bash
# Development workflow: format, lint, and view
zoo kcl format -w my-file.kcl
zoo kcl lint my-file.kcl
zoo kcl view my-file.kcl

# Export workflow: generate renders and CAD files
zoo kcl snapshot my-file.kcl preview.png
zoo kcl export --output-format=stl my-file.kcl .
zoo kcl export --output-format=step my-file.kcl .

# Analysis workflow: get physical properties
zoo kcl volume --output-unit=cm3 my-file.kcl
zoo kcl surface-area --output-unit=cm2 my-file.kcl
zoo kcl mass --material-density=7850 --material-density-unit=kg-m3 --output-unit=kg my-file.kcl
zoo kcl center-of-mass --output-unit=mm my-file.kcl

# Version control workflow: deterministic exports
zoo kcl format -w my-file.kcl
zoo kcl lint my-file.kcl
zoo kcl export --output-format=stl --deterministic my-file.kcl .
zoo kcl snapshot my-file.kcl preview.png
git add my-file.kcl my-file.stl preview.png
git commit -m "Update part design"
```

### Global Options

All `zoo kcl` commands support these global options:

- `-d, --debug`: Enable debug output
- `--host <HOST>`: Specify Zoo API host (default: api.zoo.dev)
- `-f, --format`: Output format for data (json, yaml, table)
- `--show-trace`: Print tracing link for API requests

### Working with Directories

Most commands accept either a file path or a directory containing `main.kcl`:

```bash
# These are equivalent if my-project/ contains main.kcl
zoo kcl format my-project/main.kcl
zoo kcl format my-project

# Same for export
zoo kcl export --output-format=stl my-project .
```

### Using with CI/CD

```bash
# Pre-commit hook example
#!/bin/bash
zoo kcl format -w "$1"
zoo kcl lint "$1" || exit 1

# GitHub Actions example
- name: Lint KCL files
  run: |
    for file in $(find . -name "*.kcl"); do
      zoo kcl lint "$file"
    done

- name: Export STL files
  run: |
    for file in $(find . -name "*.kcl"); do
      dir=$(dirname "$file")
      zoo kcl export --output-format=stl --deterministic "$file" "$dir"
    done
```

## Known Engine Limitations

**3D Boolean Operations:**
1. **Union of non-touching solids** may fail
   - Workaround: Keep separate or use `method = MERGE` when extruding
2. **Multiple subtract operations** may fail
   - Workaround: Use `subtract2d` on 2D profiles BEFORE extruding
3. **Subtract with transformed geometry** may fail
   - Workaround: Create geometry in final position, not transformed after

**Preferred workflow for holes (in order of reliability):**

```kcl
// BEST: Negative extrude from face
base = startSketchOn(XY)
  |> rectangle(width = 100, height = 50, center = [0, 0])
  |> extrude(length = 10)

holes = startSketchOn(base, face = END)
  |> circle(center = [20, 0], radius = 5)
  |> patternLinear2d(axis = [1, 0], instances = 3, distance = 30)
  |> extrude(length = -10.1)  // NEGATIVE LENGTH CUTS

// GOOD: 2D subtract before extrude
profile = startSketchOn(XY)
  |> rectangle(width = 100, height = 50, center = [0, 0])
  |> subtract2d(tool = holeProfile)
  |> extrude(length = 10)

// AVOID: 3D subtract (may fail)
plate = extrude(profile, length = 10)
holes = extrude(holeProfile, length = 10)
result = subtract([plate], tools = [holes])  // May fail
```

**Arc Limitations:**
- `tangentialArc` must use EITHER `(angle, radius)` OR `(end)` OR `(endAbsolute)` - not mixed

## Basic Syntax

### Variables & Functions
```kcl
// Immutable variables
width = 20
height = 10

// Functions - @ prefix makes first param unlabeled
fn makeCube(@size, color) {
  return startSketchOn(XY)
    |> rectangle(width = size, height = size, center = [0, 0])
    |> extrude(length = size)
    |> appearance(color = color)
}

cube = makeCube(10, color = "#ff0000")  // First param unlabeled due to @

// Type annotations
fn makeBox(@width: number(mm), height: number(mm)) { ... }
```

### Pipeline Operator
```kcl
sketch = startSketchOn(XY)
  |> startProfile(at = [0, 0])
  |> line(end = [10, 0])
  |> close()
  |> extrude(length = 5)

// % represents left side value (often implicit)
x = 10 |> sqrt(%) |> pow(%, exp = 2)
```

### Conditionals
```kcl
thickness = if partSize > 100 {
  5
} else if partSize > 50 {
  3
} else {
  2
}
```

## Units

### Types
- Length: `mm`, `cm`, `m`, `in`, `ft`, `yd`
- Angle: `deg`, `rad`

### Usage
```kcl
line(end = [10mm, 5in])  // Auto-convert
extrude(length = 2.5cm)

// Type ascription - asserts units (doesn't convert)
radius = (circumference / (2 * PI)): mm

// Actual conversion - use units:: functions
area = units::toMillimeters(width) * units::toMillimeters(height)

// Conversion functions
units::toMillimeters(value)
units::toInches(value)
units::toRadians(angleDeg)
units::toDegrees(angleRad)
```

## 2D Sketching

### Choose Plane
```kcl
startSketchOn(XY)   // Z up (default horizontal)
startSketchOn(XZ)   // Y down
startSketchOn(YZ)   // X out
startSketchOn(-XY)  // Flipped normal
startSketchOn(offsetPlane(XY, offset = 10))

// Get plane from face without sketching on it
planeOf(solid, face = END)  // Returns plane, doesn't modify solid

// Use planeOf to create separate solid (not merged)
tower = startSketchOn(planeOf(cube, face = END))
  |> circle(radius = 2)
  |> extrude(length = 5)  // Creates NEW solid, not merged with cube

// Custom plane
customPlane = {
  origin = [x, y, z],
  xAxis = [dx, dy, dz],
  yAxis = [dx, dy, dz],
  zAxis = [dx, dy, dz]  // Optional
}
startSketchOn(customPlane)
```

### Draw Paths
```kcl
// Lines
line(end = [10, 5])                    // Relative
line(endAbsolute = [20, 30])           // Absolute
xLine(length = 10)                     // Horizontal
yLine(length = 5)                      // Vertical
angledLine(angle = 45deg, length = 10)
angledLine(angle = 45deg, lengthX = 10)
angledLine(angle = -45deg, lengthY = 10)
angledLineThatIntersects(angle = 0, intersectTag = seg2, offset = 0)

// Arcs
arc(angleStart = 0, angleEnd = 90deg, radius = 5)
arc(endAbsolute = [x, y], radius = 5)
arc(interiorAbsolute = [x, y], endAbsolute = [x2, y2])
tangentialArc(end = [10, 0])
tangentialArc(angle = 90deg, radius = 5)
tangentialArc(interiorAbsolute = [x, y], endAbsolute = [x2, y2])
bezierCurve(control1 = [5, 10], control2 = [10, 10], end = [15, 0])

// Involute (for gears)
involuteCircular(
  startRadius = baseDiameter / 2,
  endRadius = tipDiameter / 2,
  angle = 0,
  reverse = false
)

// Shapes
circle(center = [0, 0], radius = 5)
rectangle(width = 10, height = 5, center = [0, 0])
polygon(numSides = 6, radius = 10, center = [0, 0])

// Polar coordinates
startProfile(at = polar(angle = 45deg, length = 10))
```

### Close Sketch
```kcl
close()

// Dynamic closing with query functions
profile = startProfile(at = [10, 20])
  |> line(end = [5, 0])
  |> line(endAbsolute = [profileStartX(%), profileStartY(%)])
  |> close()
```

## Query Functions

Enable dynamic, responsive geometry:

```kcl
// Profile queries
profileStart(%)      // [x, y] start point
profileStartX(%)     // X coordinate
profileStartY(%)     // Y coordinate

// Segment queries
segLen(tag)          // Length
segAng(tag)          // Angle
segStart(tag)        // [x, y] start
segStartX(tag)       // X start
segStartY(tag)       // Y start
segEnd(tag)          // [x, y] end
segEndX(tag)         // X end
segEndY(tag)         // Y end
tangentToEnd(tag)    // Tangent angle at arc end
lastSegX(%)          // Last segment X
lastSegY(%)          // Last segment Y

// Example: Dynamic geometry
profile = startProfile(at = [0, 0])
  |> line(end = [width, 0], tag = $bottom)
  |> line(end = [0, height], tag = $right)
  |> line(endAbsolute = [0, segEndY(bottom)])  // Use query not hardcode
  |> close()
```

## 3D Operations

### Extrude
```kcl
extrude(length = 10)
extrude(length = -10)  // NEGATIVE CUTS (preferred for holes)
extrude(length = 10, symmetric = true)
extrude(twistAngle = 90deg, length = 10)
extrude(length = 10, tagStart = $bottom, tagEnd = $top)  // Tag faces
extrude(length = 10, method = NEW)     // Separate solid
extrude(length = 10, method = MERGE)   // Extends existing (default)
```

### Revolve
```kcl
revolve(axis = Y, angle = 360deg)
revolve(axis = Y, angle = 180deg)
revolve(axis = Y, angle = -70deg)  // Negative reverses
revolve(axis = Y, angle = 65deg, symmetric = true)

// Custom axis
axisObj = {
  direction = [0, 1],
  origin = [radius, radius]
}
revolve(axis = axisObj, angle = 90deg)
```

### Sweep
```kcl
sweepPath = startSketchOn(XZ)
  |> startProfile(at = [0, 0])
  |> line(end = [0, 10])
  |> tangentialArc(angle = 90deg, radius = 5)

profile = startSketchOn(XY) |> circle(center = [0, 0], radius = 2)
sweptSolid = sweep(profile, path = sweepPath)
```

### Helix
```kcl
helixPath = helix(
  axis = Z,
  radius = 10,
  length = 50,
  revolutions = 5,
  angleStart = 0,
  ccw = false
)

coilProfile = startSketchOn(XY) |> circle(center = [10, 0], radius = 1)
spring = sweep(coilProfile, path = helixPath)
```

### Loft
```kcl
profile1 = startSketchOn(XY) |> circle(center = [0, 0], radius = 10)
profile2 = startSketchOn(offsetPlane(XY, offset = 20))
  |> rectangle(width = 20, height = 20, center = [0, 0])
profile3 = startSketchOn(offsetPlane(XY, offset = 40)) |> circle(radius = 5)

loft([profile1, profile2, profile3])
```

## Tags and References

### Declaring and Using
```kcl
sketch = startSketchOn(XY)
  |> startProfile(at = [0, 0])
  |> line(end = [10, 0], tag = $edge1)  // Declare with $
  |> line(end = [0, 10], tag = $edge2)
  |> close(tag = $edge3)

solid = extrude(sketch, length = 5)
  |> fillet(radius = 2, tags = [edge1, edge2])  // Use without $

// Special face tags
startSketchOn(solid, face = START)  // Bottom face
startSketchOn(solid, face = END)    // Top face
```

### Tag Relationships
```kcl
getOppositeEdge(edge1)
getNextAdjacentEdge(edge1)
getPreviousAdjacentEdge(edge1)
getCommonEdge(faces = [face1, face2])  // CRITICAL for precise fillets

// Example usage
solid = extrude(profile, length = 5, tagStart = $capStart, tagEnd = $capEnd)
  |> fillet(
       radius = 1,
       tags = [
         getCommonEdge(faces = [seg01, capEnd]),
         getCommonEdge(faces = [seg02, capStart])
       ]
     )
```

## Solid Operations

### Boolean Operations
```kcl
union([solid1, solid2, solid3])
subtract([baseSolid], tools = [toolSolid])
intersect([solid1, solid2])

// Prefer 2D operations or negative extrude instead
```

### Edge Operations
```kcl
fillet(radius = 2, tags = [edge1, edge2])
chamfer(length = 2, tags = [edge1])
chamfer(length = 2, angle = 45deg, tags = [edge1])
```

### Shell Operations
```kcl
shell(faces = [END], thickness = 2)
shell(faces = [START, END], thickness = 2)
hollow(thickness = 2)  // All faces closed
```

## Patterns

```kcl
// 2D Linear - axis can be ANY vector
patternLinear2d(axis = [1, 0], instances = 5, distance = 10)   // X
patternLinear2d(axis = [0, 1], instances = 5, distance = 10)   // Y
patternLinear2d(axis = [1, 1], instances = 5, distance = 10)   // Diagonal
patternLinear2d(axis = [-1, 0], instances = 5, distance = 10)  // Negative X

// 2D Circular
patternCircular2d(
  center = [0, 0],
  instances = 12,
  arcDegrees = 360,
  rotateDuplicates = true
)

// 3D Linear
patternLinear3d(axis = [1, 0, 0], instances = 5, distance = 10)
patternLinear3d(axis = [0, -1, 0], instances = 5, distance = 10)

// 3D Circular
patternCircular3d(
  axis = [0, 0, 1],  // Or constant Z
  center = [0, 0, 0],
  instances = 12,
  arcDegrees = 360,
  rotateDuplicates = true
)

// Chained for grids
grid = circle(center = [0, 0], radius = 2)
  |> patternLinear2d(instances = 5, distance = 10, axis = [1, 0])
  |> patternLinear2d(instances = 3, distance = 10, axis = [0, 1])  // 5×3 = 15

// Custom transform
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
rotate(roll = angleX, pitch = angleY, yaw = angleZ)
scale(x = 2, y = 1.5, z = 1)
scale(x = -1, y = 1, z = 1)  // Negative mirrors
mirror2d(axis = X)  // Sketches only

// Global transformations
translate(x = 10, y = 20, z = 30, global = true)
rotate(roll = 0, pitch = 45deg, yaw = 90deg, global = true)
```

## Cloning & Face Sketching

```kcl
// Clone for independent copy
clonedPart = clone(originalPart)
  |> translate(x = 20, y = 0, z = 0)

// Sketch on face → extrude MERGES with solid (default)
startSketchOn(cube, face = END)
  |> circle(radius = 2)
  |> extrude(length = 5)  // Merged into cube

// Use planeOf() to create separate solid
startSketchOn(planeOf(cube, face = END))
  |> circle(radius = 2)
  |> extrude(length = 5)  // NEW solid, not merged

// Or use method = NEW for separate solid
startSketchOn(cube, face = END)
  |> circle(radius = 2)
  |> extrude(method = NEW, length = 5)  // NEW solid
```

## Mathematical Functions

```kcl
// Trig
sin(angle), cos(angle), tan(angle)
asin(value), acos(value), atan(value)

// Circular positioning
x = radius * cos(angle)
y = radius * sin(angle)

// Other
abs(value), sqrt(value), pow(value, exp = 2)
floor(value), ceil(value), round(value)
min(a, b), max(a, b)

// Constants
PI, E, TAU
```

## Appearance

```kcl
|> appearance(color = "#FF0000")
|> appearance(color = "#1f9896", metalness = 40, roughness = 30)
// metalness: 0-100 (reflectivity)
// roughness: 0-100 (surface finish)
```

## Array Operations & Control Flow

```kcl
// Arrays (0-indexed)
arr = [1, 2, 3, 4, 5]
first = arr[0]
last = arr[count(arr) - 1]
newArr = push(arr, item = 6)
concatArr = concat(arr, items = [7, 8, 9])
arrLength = count(arr)

// Map - transform each element
offsets = [0, 25, 50]
cubes = map(offsets, f = fn(@offset) {
  return startSketchOn(XY)
    |> rectangle(width = 10, height = 10, center = [offset, 0])
    |> extrude(length = 10)
})

// Reduce - accumulate
sum = reduce([1, 2, 3, 4], initial = 0, f = fn(@item, accum) {
  return accum + item
})
```

## Assertions

```kcl
assert(value, isEqualTo = 10)
assert(value, isGreaterThan = 0, isLessThan = 100)
assert(value, isEqualTo = 5.0, tolerance = 0.001)
assert(width, isGreaterThan = thickness * 2, error = "Width too small")
assertIs(booleanValue)  // Assert true
```

## Module System

```kcl
// Export (utils.kcl)
export fn myFunction(x) { return x * 2 }
export myConstant = 42

// Import (main.kcl) - must be at file top
import myFunction, myConstant from "utils.kcl"
import "utils.kcl" as utils
```

## Important Constants

```kcl
// Planes: XY, XZ, YZ, -XY, -XZ, -YZ
// Axes: X, Y, Z (or vectors [1,0,0])
// Math: PI, E, TAU
// Faces: START, END
// Methods: NEW, MERGE
```

## Critical Gotchas

1. Variables are immutable - cannot reassign
2. Function parameters must be labeled (except first with `@`)
3. Tags declared with `$`, used without: `tag = $myTag` vs `tags = [myTag]`
4. Close sketches before extrusion
5. Arrays are 0-indexed
6. Imports must be at file top
7. Sketch on FACE merges (MERGE), sketch on PLANE creates new solid - use `planeOf()` or `method = NEW` for separate solids
8. Sketch on face uses global coordinates, not face-local
9. 3D booleans may fail - use 2D ops or negative extrude
10. Arc needs EITHER `(angle, radius)` OR `(end)` - not both
11. Type ascription (`: mm`) validates, doesn't convert - use `units::` for conversion
12. Axis can be vectors like `[1, 1]` not just X/Y/Z
13. Use `getCommonEdge` for precise fillet targeting

## Complete Example

```kcl
// Mounting Plate - demonstrates all best practices

@settings(defaultLengthUnit = mm, kclVersion = 1.0)

// Input parameters
baseWidth = 80
baseHeight = 80
baseThickness = 5
bossDiameter = 20
bossHeight = 15
mountHoleDia = 6
mountHoleOffset = 30
filletRadius = 2

// Calculated parameters
minBossClearance = mountHoleOffset - bossDiameter / 2

// Assertions
assert(baseWidth, isGreaterThan = mountHoleOffset * 2, error = "Plate too narrow")
assert(minBossClearance, isGreaterThan = mountHoleDia, error = "Boss interferes with holes")

// Base plate profile
basePlateProfile = startSketchOn(XY)
  |> startProfile(at = [-baseWidth/2, -baseHeight/2])
  |> line(end = [baseWidth, 0], tag = $frontEdge)
  |> line(end = [0, baseHeight], tag = $rightEdge)
  |> line(end = [-baseWidth, 0], tag = $backEdge)
  |> close(tag = $leftEdge)

// Mounting holes pattern (2D)
mountingHoles = startSketchOn(XY)
  |> circle(center = [mountHoleOffset/2, 0], radius = mountHoleDia/2)
  |> patternCircular2d(
       center = [0, 0],
       instances = 4,
       arcDegrees = 360,
       rotateDuplicates = true
     )

// Subtract holes in 2D, then extrude
basePlate = basePlateProfile
  |> subtract2d(tool = mountingHoles)
  |> extrude(length = baseThickness, tagEnd = $plateTop)
  |> fillet(radius = filletRadius, tags = [
       getNextAdjacentEdge(frontEdge),
       getNextAdjacentEdge(leftEdge)
     ])

// Boss on top (method=MERGE by default)
boss = startSketchOn(basePlate, face = END)
  |> circle(center = [0, 0], radius = bossDiameter/2, tag = $circleBottom)
  |> extrude(length = bossHeight)
  |> fillet(
       radius = filletRadius,
       tags = [getOppositeEdge(circleBottom)]
     )
```

This example demonstrates: @settings, organized parameters, assertions, pattern-based features, 2D subtract before extrude, tagged edges/faces, getCommonEdge for fillets, and descriptive naming.
