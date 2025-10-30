# Console Bracket CAD Model

Game console under-desk mounting bracket designed in KCL (KittyCAD Language).

## Design Specifications

- **Material:** 20 gauge sheet metal (0.0359" thick)
- **Dimensions:** 10" width × 18" total length (before bending)
- **Shape:** C-shaped bracket with three sections:
  - Top section: 5" (desk mounting with 4 screw holes)
  - Vertical section: 10" (with ventilation holes)
  - Bottom section: 3" (console support shelf)
- **Mounting:** 4 holes for #8 screws (0.177" clearance)
- **Ventilation:** 4 rectangular slots (2.5" × 1.0")
- **Bend radius:** 1/8" (0.125") for manufacturability

## Building

### Windows (using build.bat)

```batch
# Generate STL and renders
build.bat

# Generate only STL
build.bat stl

# Generate only renders
build.bat renders

# Clean generated files
build.bat clean

# Show help
build.bat help
```

### Linux/Mac (using Makefile)

```bash
# Generate STL and renders
make

# Generate only STL
make stl

# Generate only renders
make renders

# Clean generated files
make clean

# Show help
make help
```

## Requirements

- [Zoo CLI](https://zoo.dev/docs/cli) - For KCL to STL export
- [Blender 4.5+](https://www.blender.org/) - For rendering (optional)
  - Update `BLENDER` path in build.bat or Makefile if using different version

## Files

- `console-bracket.kcl` - Source KCL CAD model
- `console-bracket.stl` - Generated STL file (after build)
- `render_bracket.py` - Blender Python script for rendering
- `renders/` - Generated render images (6 views)
- `build.bat` - Windows build script
- `Makefile` - Unix/Make build script

## Output

The build process generates:
- `console-bracket.stl` - 3D model for manufacturing/3D printing
- `renders/bracket_isometric.png` - Isometric view showing all three sections
- `renders/bracket_front.png` - Front view showing ventilation holes
- `renders/bracket_side.png` - Side profile showing C-shape and bends
- `renders/bracket_top.png` - Top view showing screw hole locations
- `renders/bracket_bottom.png` - Bottom view
- `renders/bracket_back.png` - Back view
