# Amplitude Bar - SolidWorks SDK Translation

This directory contains translations of `amplitude-bar.kcl` to SolidWorks API calls in both C# and Python.

## Files

- **amplitude-bar.kcl** - Original KCL source (KittyCAD Language)
- **amplitude-bar.cs** - C# translation using SolidWorks Interop API
- **amplitude-bar.py** - Python translation using win32com
- **amplitude-bar-solidworks-readme.md** - This file

## Part Description

The amplitude bar is a vertical rod (32" x 0.25" x 0.25") with two centered notches:

- **Bottom notch**: 0.125" wide x 3/32" (0.09375") high
- **Top notch**: 0.125" wide x 0.5" high

```
Visual representation:
   ##  ##  <- Top notch (0.5" high)
   ##  ##
   ##  ##
   ######
   ######
   ######  <- Bar body (32" total length)
   ######
   ######
   ######
   ######
   ######
   ######
   ##  ##  <- Bottom notch (3/32" high)
   ##  ##
```

## API Translation Details

### Coordinate System Mapping

| KCL | SolidWorks |
|-----|------------|
| `startSketchOn(XZ)` | Front Plane (XZ plane) |
| X-axis | X-axis (horizontal, right) |
| Z-axis | Z-axis (vertical, up) |
| Extrude depth | Y-axis direction |

### Unit Conversion

KCL uses inches (default), SolidWorks API requires meters:
- **Conversion factor**: 1 inch = 0.0254 meters
- All dimensions are multiplied by 0.0254 before passing to API

### Key API Methods Used

1. **Document Creation**
   ```csharp
   IModelDoc2 NewDocument(string template, int paperSize, double width, double height)
   ```

2. **Plane Selection**
   ```csharp
   bool SelectByID2(string name, string type, double x, double y, double z,
                    bool append, int mark, Callout callout, int selectOption)
   ```

3. **Sketch Insertion**
   ```csharp
   void InsertSketch(bool updateEditRebuild)
   ```

4. **Line Creation**
   ```csharp
   ISketchSegment CreateLine(double x1, double y1, double z1,
                             double x2, double y2, double z2)
   ```

5. **Extrusion**
   ```csharp
   IFeature FeatureExtrusion3(bool sd, bool flip, bool dir,
                              int t1, int t2, double d1, double d2,
                              bool dchk1, bool dchk2, bool ddir1, bool ddir2,
                              double dang1, double dang2,
                              bool offsetReverse1, bool offsetReverse2,
                              bool translateSurface1, bool translateSurface2,
                              bool merge, bool useFeatScope, bool useAutoSelect,
                              int t0, double startOffset, bool flipStartOffset)
   ```

## Usage

### C# Version

**Requirements:**
- Visual Studio 2019 or later
- SolidWorks 2025 (or compatible version)
- SolidWorks Interop assemblies:
  - `SolidWorks.Interop.sldworks.dll`
  - `SolidWorks.Interop.swconst.dll`

**Setup:**
1. Create a new C# Console Application or Class Library
2. Add references to SolidWorks Interop assemblies (typically in `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist`)
3. Add the `amplitude-bar.cs` file to your project
4. Call the method:

```csharp
using HarmonicAnalyzer;
using SolidWorks.Interop.sldworks;

// Get or create SolidWorks instance
ISldWorks swApp = (ISldWorks)System.Runtime.InteropServices.Marshal.GetActiveObject("SldWorks.Application");

// Create the amplitude bar
AmplitudeBar.CreateAmplitudeBar(swApp);
```

### Python Version

**Requirements:**
- Python 3.7 or later
- SolidWorks 2025 (or compatible version)
- Python packages:
  - `pywin32` (for win32com)

**Setup:**
1. Install required packages:
   ```bash
   pip install pywin32
   ```

2. Run the script:
   ```bash
   python amplitude-bar.py
   ```

The script will:
- Connect to SolidWorks (or launch it if not running)
- Create a new part document
- Draw the amplitude bar profile
- Extrude it to the final shape
- Display the completed part

## Sketch Profile Coordinates

The sketch is drawn as a closed profile with 12 line segments on the Front Plane (XZ):

| Segment | Start Point | End Point | Description |
|---------|-------------|-----------|-------------|
| 1 | (0, 0, 0) | (0.003175, 0, 0) | Bottom left edge to notch |
| 2 | (0.003175, 0, 0) | (0.003175, 0, 0.00238125) | Up to notch top |
| 3 | (0.003175, 0, 0.00238125) | (0.00635, 0, 0.00238125) | Across notch top |
| 4 | (0.00635, 0, 0.00238125) | (0.00635, 0, 0) | Down from notch |
| 5 | (0.00635, 0, 0) | (0.00635, 0, 0) | Bottom right edge to notch |
| 6 | (0.00635, 0, 0) | (0.00635, 0, 0.8128) | Up main bar height |
| 7 | (0.00635, 0, 0.8128) | (0.003175, 0, 0.8128) | Top right edge to notch |
| 8 | (0.003175, 0, 0.8128) | (0.003175, 0, 0.8001) | Down into notch |
| 9 | (0.003175, 0, 0.8001) | (0, 0, 0.8001) | Across notch bottom |
| 10 | (0, 0, 0.8001) | (0, 0, 0.8128) | Up from notch |
| 11 | (0, 0, 0.8128) | (0, 0, 0.8128) | Top left edge to notch |
| 12 | (0, 0, 0.8128) | (0, 0, 0) | Close - down to origin |

*All coordinates in meters (multiply by 39.3701 for inches)*

## Differences from KCL

### Similarities
- Both create the exact same geometry
- Both use a single closed profile sketch
- Both extrude in one direction

### Key Differences

1. **Coordinate specification**
   - KCL: Relative endpoints (`end = [dx, dy]`)
   - SolidWorks: Absolute coordinates for start and end of each line

2. **Units**
   - KCL: Supports unit annotations (`@settings(defaultLengthUnit = in)`)
   - SolidWorks API: Always uses meters, requires manual conversion

3. **Pipeline vs. Procedural**
   - KCL: Uses pipeline operator `|>` for chaining operations
   - SolidWorks: Sequential method calls on manager objects

4. **Sketch closure**
   - KCL: Explicit `|> close()` operator
   - SolidWorks: Final line drawn back to origin

5. **Error handling**
   - KCL: Declarative, errors caught at compile/execution
   - SolidWorks: Requires explicit null checks and return value validation

## Extending the Code

### Adding Parameters as Dimension Variables

To make dimensions editable in SolidWorks:

```csharp
// After creating each line, add dimensions
IDisplayDimension dim = swModel.AddDimension2(x, y, z);
IDimension dimension = dim.GetDimension();
dimension.Name = "BarLength";
dimension.SystemValue = barLength;
```

### Adding Configuration Support

```csharp
// Create configurations for different bar lengths
swModel.ConfigurationManager.AddConfiguration2(
    "32-inch", "32 inch bar", "", 0, false, false, false, false, ""
);
```

### Exporting to Other Formats

```csharp
// Export as STEP
swModel.Extension.SaveAs(
    @"C:\path\to\amplitude-bar.step",
    (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
    (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
    null,
    ref errors,
    ref warnings
);
```

## Troubleshooting

### Common Issues

1. **"Failed to connect to SolidWorks"**
   - Ensure SolidWorks is installed
   - Check that you have proper COM registration
   - Try running as Administrator

2. **"Failed to create new part document"**
   - Verify SolidWorks template path is correct
   - Check that default templates are installed

3. **"Failed to select Front Plane"**
   - SolidWorks uses localized plane names
   - For non-English versions, use: "Plan de face" (French), "Vorderansicht" (German), etc.
   - Or select by feature ID instead of name

4. **Dimensions appear incorrect**
   - Verify unit conversion (inches × 0.0254 = meters)
   - Check that document units are set correctly

## References

- [SolidWorks API Documentation](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS_API.htm)
- [KCL Language Documentation](https://zoo.dev/docs/kcl)
- Original KCL file: `amplitude-bar.kcl`

## Version History

- **v1.0** (2025-11-11) - Initial translation from KCL to C# and Python
