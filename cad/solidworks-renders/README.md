# SinusoidalCamGenerator - SolidWorks C# Implementation

This program replicates the sinusoidal-cam.kcl design in SolidWorks using the SolidWorks API.

## Design Overview

The sinusoidal cam is an **eccentric cam** that produces harmonic motion for a follower mechanism. It consists of:

- **Circular disk** (2.0" diameter × 0.4" thick)
- **Eccentric shaft hole** (0.375" diameter, offset 0.2" from center)
- **Integrated keyway** (0.125" wide × 0.06" deep)

The displacement follows the formula: **Displacement = eccentricity × sin(θ)**

## Dimensions

All dimensions are in inches:

| Parameter | Value | Description |
|-----------|-------|-------------|
| Cam Diameter | 2.0" | Outer diameter of cam disk |
| Cam Thickness | 0.4" | Thickness of cam disk |
| Shaft Diameter | 0.375" | Mounting hole diameter (3/8") |
| Eccentricity | 0.2" | Offset from center (amplitude) |
| Keyway Width | 0.125" | Keyway slot width (1/8") |
| Keyway Depth | 0.06" | Keyway depth from shaft surface |

## Geometry Details

### Cam Body
- Circular disk centered at origin [0, 0]
- Extruded to 0.4" thickness

### Eccentric Shaft Hole with Keyway
The shaft hole is offset by the eccentricity (0.2") to create the harmonic motion effect. The hole profile consists of:

1. **Keyway slot**: Rectangular extension from the circular hole
2. **Circular portion**: Arc segments forming the shaft hole

The keyway profile construction:
- Starts at angle: `asin(keywayWidth / 2 / shaftRadius)` ≈ 19.5°
- Three straight line segments form the rectangular keyway slot
- Two arc segments complete the circular shaft hole
- Profile is closed to form a single region

## Prerequisites

1. **SolidWorks** must be installed (tested with SolidWorks 2020+)
2. **.NET Framework 4.8** or later
3. **SolidWorks API DLLs** (included with SolidWorks installation)

## Building the Program

### Option 1: Using Visual Studio

1. Open `SinusoidalCamGenerator.csproj` in Visual Studio
2. Verify the SolidWorks API DLL paths in the .csproj file match your installation:
   - Default: `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist\`
   - Update paths if your SolidWorks is installed elsewhere
3. Build the solution (Ctrl+Shift+B)
4. Run the program (F5)

### Option 2: Using Command Line (dotnet CLI)

```cmd
# Verify .NET SDK is installed
dotnet --version

# Build the project
dotnet build SinusoidalCamGenerator.csproj

# Run the program
dotnet run --project SinusoidalCamGenerator.csproj
```

### Option 3: Using MSBuild (without Visual Studio)

```cmd
# Restore NuGet packages (if any)
msbuild /t:Restore SinusoidalCamGenerator.csproj

# Build the project
msbuild SinusoidalCamGenerator.csproj /p:Configuration=Release

# Run the executable
.\bin\Release\net48\SinusoidalCamGenerator.exe
```

## Troubleshooting

### SolidWorks API DLLs Not Found

If you get errors about missing SolidWorks DLLs, update the `HintPath` elements in `SinusoidalCamGenerator.csproj`:

```xml
<Reference Include="SolidWorks.Interop.sldworks">
  <HintPath>YOUR_SOLIDWORKS_PATH\api\redist\SolidWorks.Interop.sldworks.dll</HintPath>
  <EmbedInteropTypes>false</EmbedInteropTypes>
</Reference>
```

Common SolidWorks installation paths:
- `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\`
- `C:\Program Files\SolidWorks Corp\SolidWorks\`
- `C:\Program Files (x86)\SOLIDWORKS Corp\SOLIDWORKS\`

### COM Interop Errors

If you encounter COM registration errors:
1. Run Visual Studio as Administrator
2. Ensure SolidWorks is properly installed and licensed
3. Try running SolidWorks once manually before running the program

### Platform Target Mismatch

SolidWorks typically runs as 64-bit, so ensure the project targets x64:
- Check `<PlatformTarget>x64</PlatformTarget>` in the .csproj file
- In Visual Studio: Project Properties → Build → Platform target → x64

## Program Output

When executed successfully, the program will:

1. Connect to SolidWorks (or start a new instance)
2. Validate all design parameters
3. Create a new part document
4. Generate the cam body sketch with eccentric hole and keyway
5. Extrude the sketch to create the 3D solid
6. Save the part as `sinusoidal-cam.SLDPRT` in the current directory

Console output example:
```
Connecting to SolidWorks...
Connected to SolidWorks 28.0.0

Validating design parameters...
  Cam diameter: 2.000"
  Cam thickness: 0.400"
  Shaft diameter: 0.375"
  Eccentricity: 0.200"
  Keyway: 0.125" × 0.060"
  Minimum edge clearance: 0.613"
  Parameters validated successfully.

Creating cam part...
  Creating cam body sketch...
    Created cam circle: radius = 1.000"
    Creating eccentric shaft hole with keyway...
    Shaft hole center offset: [0.200", 0]
    Keyway start angle: 19.47°
    Profile start point: [0.3767", 0.0625"]
    Eccentric shaft hole with keyway created.
    Sketch created with cam body and eccentric hole.
  Extruding cam body...
    Extruded to thickness: 0.400"
  Cam part created successfully.

Saving part to: C:\src\harmonic-analyzer\cad\solidworks-renders\sinusoidal-cam.SLDPRT
  Part saved successfully.

Sinusoidal cam created successfully!

Press any key to exit...
```

## Code Structure

The program follows SolidWorks API best practices:

### Key Methods

- **`ConnectToSolidWorks()`**: Establishes connection to SolidWorks application
- **`ValidateParameters()`**: Checks design parameters for validity
- **`CreateCamPart()`**: Orchestrates the part creation process
- **`CreateCamBodySketch()`**: Creates the 2D sketch with cam circle and hole
- **`CreateCamCircle()`**: Draws the outer circular boundary
- **`CreateShaftHoleWithKeyway()`**: Constructs the complex eccentric hole profile
- **`ExtrudeCamBody()`**: Extrudes the sketch to 3D solid
- **`SavePart()`**: Saves the completed part file

### Design Patterns Used

1. **Named parameters**: All SolidWorks API calls use named parameters for clarity
2. **Proper error handling**: Null checks and meaningful error messages
3. **COM object cleanup**: Proper handling of COM interop references
4. **Validation early**: Parameters validated before geometry creation
5. **Calculated properties**: Derived values computed from base parameters

## Reference Files

- **KCL source**: `/c/src/harmonic-analyzer/cad/sinusoidal-cam.kcl`
- **Parameters**: `/c/src/harmonic-analyzer/cad/parameters.kcl`
- **STL reference**: `/c/src/harmonic-analyzer/cad/stl-renders/sinusoidal-cam.stl`
- **PNG renders**: `/c/src/harmonic-analyzer/cad/png-renders/sinusoidal-cam/`

## Further Modifications

To modify the design, change the constants at the top of `SinusoidalCamGenerator.cs`:

```csharp
private const double CAM_DIAMETER = 2.0;      // Change cam size
private const double ECCENTRICITY = 0.2;      // Change motion amplitude
private const double KEYWAY_WIDTH = 0.125;    // Change keyway dimensions
```

The program will automatically validate that your changes produce valid geometry.

## License

This code is part of the harmonic-analyzer project.
