//--------------------------------------------------------------
// SolidWorks C# Macro: Sinusoidal Cam (Eccentric Cam)
//
// Description:
// Creates an eccentric cam that produces harmonic motion for a follower.
// Simple cylinder with off-center mounting hole and keyway.
// Displacement = eccentricity × sin(θ)
//
// Translated from: cad/sinusoidal-cam.kcl
//
// Units: SolidWorks API uses meters internally
//--------------------------------------------------------------

using System;
using System.Diagnostics;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SinusoidalCamMacro
{
    partial class SolidWorksMacro
    {
        // ========================================
        // PARAMETERS (converted from inches to meters)
        // ========================================

        // Cam parameters (from parameters.kcl)
        private const double CAM_DIAMETER = 2.0 * 0.0254;      // 2.0 inches -> meters
        private const double CAM_THICKNESS = 0.4 * 0.0254;     // 0.4 inches -> meters

        // Shaft mounting parameters (from parameters.kcl)
        private const double SHAFT_DIAMETER = 0.375 * 0.0254;  // 3/8" -> meters
        private const double KEYWAY_WIDTH = 0.125 * 0.0254;    // 1/8" -> meters
        private const double KEYWAY_DEPTH = 0.06 * 0.0254;     // 0.06" -> meters

        // Eccentric cam geometry
        private const double ECCENTRICITY = 0.2 * 0.0254;      // 0.2 inches -> meters (amplitude of motion)

        // Calculated parameters
        private static double CAM_RADIUS => CAM_DIAMETER / 2.0;
        private static double SHAFT_RADIUS => SHAFT_DIAMETER / 2.0;

        public void Main()
        {
            // Validate parameters (assertions from KCL)
            if (CAM_DIAMETER <= SHAFT_DIAMETER)
                throw new InvalidOperationException("Cam diameter must be larger than shaft");

            if (ECCENTRICITY <= 0 || ECCENTRICITY >= CAM_RADIUS)
                throw new InvalidOperationException("Eccentricity must be greater than 0 and less than cam radius");

            double minClearance = CAM_RADIUS - ECCENTRICITY - SHAFT_RADIUS;
            if (minClearance <= 0)
                throw new InvalidOperationException("Shaft hole too close to cam edge");

            if (CAM_THICKNESS <= 0)
                throw new InvalidOperationException("Cam thickness must be positive");

            if (KEYWAY_WIDTH >= SHAFT_DIAMETER)
                throw new InvalidOperationException("Keyway too wide for shaft");

            Debug.Print("=== Creating Sinusoidal Cam (Eccentric Cam) ===");
            Debug.Print($"Cam Diameter: {CAM_DIAMETER * 1000:F3} mm");
            Debug.Print($"Cam Thickness: {CAM_THICKNESS * 1000:F3} mm");
            Debug.Print($"Eccentricity: {ECCENTRICITY * 1000:F3} mm");
            Debug.Print($"Shaft Diameter: {SHAFT_DIAMETER * 1000:F3} mm");
            Debug.Print($"Minimum Edge Clearance: {minClearance * 1000:F3} mm");

            // Create the cam part
            CreateEccentricCam();

            Debug.Print("=== Cam creation complete! ===");
        }

        private void CreateEccentricCam()
        {
            ModelDoc2 swModel = null;
            ModelDocExtension swModelExt = null;
            SketchManager swSketchMgr = null;
            FeatureManager swFeatureMgr = null;
            bool status = false;

            try
            {
                // Step 1: Create new part document
                Debug.Print("Creating new part document...");
                swModel = (ModelDoc2)swApp.NewDocument("C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2016\\templates\\Part.prtdot", 0, 0, 0);

                if (swModel == null)
                    throw new InvalidOperationException("Failed to create new part document");

                swModelExt = (ModelDocExtension)swModel.Extension;
                swSketchMgr = (SketchManager)swModel.SketchManager;
                swFeatureMgr = (FeatureManager)swModel.FeatureManager;

                // Step 2: Create cam body (circular disk)
                Debug.Print("Creating cam body sketch...");

                // Select Front plane (equivalent to XY plane in KCL)
                status = swModelExt.SelectByID2(
                    Name: "Front Plane",
                    Type: "PLANE",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: (int)swSelectOption_e.swSelectOptionDefault);

                if (!status)
                    throw new InvalidOperationException("Failed to select Front plane");

                // Insert sketch on Front plane
                swSketchMgr.InsertSketch(UpdateEditRebuild: true);

                // Enable AddToDB for better performance
                swSketchMgr.AddToDB = true;
                swSketchMgr.DisplayWhenAdded = false;

                // Create outer cam circle centered at origin (0, 0, 0)
                SketchSegment camCircle = swSketchMgr.CreateCircle(
                    XC: 0.0,
                    YC: 0.0,
                    Zc: 0.0,
                    Xp: CAM_RADIUS,  // Point on circle
                    Yp: 0.0,
                    Zp: 0.0);

                // Restore normal display mode
                swSketchMgr.AddToDB = false;
                swSketchMgr.DisplayWhenAdded = true;

                // Exit sketch
                swSketchMgr.InsertSketch(UpdateEditRebuild: true);

                // Step 3: Extrude cam body
                Debug.Print("Extruding cam body...");

                // Select the sketch we just created
                status = swModelExt.SelectByID2(
                    Name: "Sketch1",
                    Type: "SKETCH",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: (int)swSelectOption_e.swSelectOptionDefault);

                // Create boss extrusion
                Feature camBodyFeature = swFeatureMgr.FeatureExtrusion3(
                    Sd: true,                          // Single-ended extrusion
                    Flip: false,                       // Don't flip direction
                    Dir: false,                        // Use default direction (normal to sketch)
                    T1: (int)swEndConditions_e.swEndCondBlind,  // Blind extrusion
                    T2: (int)swEndConditions_e.swEndCondBlind,  // (not used for single-ended)
                    D1: CAM_THICKNESS,                 // Extrusion depth
                    D2: 0.0,                           // (not used for single-ended)
                    Dchk1: false,                      // No draft
                    Dchk2: false,                      // No draft
                    Ddir1: false,                      // (draft not enabled)
                    Ddir2: false,                      // (draft not enabled)
                    Dang1: 0.0,                        // (draft not enabled)
                    Dang2: 0.0,                        // (draft not enabled)
                    OffsetReverse1: false,             // (not using offset)
                    OffsetReverse2: false,             // (not using offset)
                    TranslateSurface1: false,          // (not using offset)
                    TranslateSurface2: false,          // (not using offset)
                    Merge: true,                       // Merge result
                    UseFeatScope: false,               // Affect all bodies
                    UseAutoSelect: true,               // Auto-select all bodies
                    T0: (int)swStartConditions_e.swStartSketchPlane,  // Start from sketch plane
                    StartOffset: 0.0,                  // (not using offset)
                    FlipStartOffset: false);           // (not using offset)

                if (camBodyFeature == null)
                    throw new InvalidOperationException("Failed to create cam body extrusion");

                swModel.ClearSelection2(true);

                // Step 4: Create eccentric shaft hole with keyway
                Debug.Print("Creating shaft hole with keyway...");

                // Select the front face of the cam body
                status = swModelExt.SelectByID2(
                    Name: "Front Plane",
                    Type: "PLANE",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: (int)swSelectOption_e.swSelectOptionDefault);

                // Insert sketch for hole
                swSketchMgr.InsertSketch(UpdateEditRebuild: true);

                // Enable AddToDB for better performance
                swSketchMgr.AddToDB = true;
                swSketchMgr.DisplayWhenAdded = false;

                // Create shaft hole circle, offset by ECCENTRICITY
                // The hole is positioned at [eccentricity, 0] to create eccentric motion
                SketchSegment holeCircle = swSketchMgr.CreateCircle(
                    XC: ECCENTRICITY,   // Offset in X direction
                    YC: 0.0,
                    Zc: 0.0,
                    Xp: ECCENTRICITY + SHAFT_RADIUS,  // Point on circle
                    Yp: 0.0,
                    Zp: 0.0);

                // Create keyway profile
                // The keyway is a rectangular notch that extends from the shaft hole
                // Calculate start angle for the keyway (where it meets the shaft circle)
                double startAngle = Math.Asin(KEYWAY_WIDTH / 2.0 / SHAFT_RADIUS);

                // Calculate keyway profile points
                double keywayStartX = ECCENTRICITY + SHAFT_RADIUS * Math.Cos(startAngle);
                double keywayStartY = SHAFT_RADIUS * Math.Sin(startAngle);

                // Draw keyway profile as connected lines
                // Top horizontal line extending outward
                SketchSegment line1 = swSketchMgr.CreateLine(
                    X1: keywayStartX,
                    Y1: keywayStartY,
                    Z1: 0.0,
                    X2: keywayStartX + KEYWAY_DEPTH,
                    Y2: keywayStartY,
                    Z2: 0.0);

                // Vertical line going down
                SketchSegment line2 = swSketchMgr.CreateLine(
                    X1: keywayStartX + KEYWAY_DEPTH,
                    Y1: keywayStartY,
                    Z1: 0.0,
                    X2: keywayStartX + KEYWAY_DEPTH,
                    Y2: -keywayStartY,
                    Z2: 0.0);

                // Bottom horizontal line going back
                SketchSegment line3 = swSketchMgr.CreateLine(
                    X1: keywayStartX + KEYWAY_DEPTH,
                    Y1: -keywayStartY,
                    Z1: 0.0,
                    X2: keywayStartX,
                    Y2: -keywayStartY,
                    Z2: 0.0);

                // Create arcs to connect the keyway back to the shaft hole
                // Arc 1: from bottom of keyway to left side of shaft
                double arc1StartX = keywayStartX;
                double arc1StartY = -keywayStartY;
                double arc1EndX = ECCENTRICITY - SHAFT_RADIUS;
                double arc1EndY = 0.0;

                SketchArc arc1 = (SketchArc)swSketchMgr.CreateArc(
                    XC: ECCENTRICITY,
                    YC: 0.0,
                    Zc: 0.0,
                    X1: arc1StartX,
                    Y1: arc1StartY,
                    Z1: 0.0,
                    X2: arc1EndX,
                    Y2: arc1EndY,
                    Z2: 0.0,
                    Direction: 1);  // Counter-clockwise

                // Arc 2: from left side of shaft to top of keyway
                SketchArc arc2 = (SketchArc)swSketchMgr.CreateArc(
                    XC: ECCENTRICITY,
                    YC: 0.0,
                    Zc: 0.0,
                    X1: arc1EndX,
                    Y1: arc1EndY,
                    Z1: 0.0,
                    X2: keywayStartX,
                    Y2: keywayStartY,
                    Z2: 0.0,
                    Direction: 1);  // Counter-clockwise

                // Restore normal display mode and redraw
                swSketchMgr.AddToDB = false;
                swSketchMgr.DisplayWhenAdded = true;

                // Exit sketch
                swSketchMgr.InsertSketch(UpdateEditRebuild: true);

                // Step 5: Cut extrude the hole through all
                Debug.Print("Cutting shaft hole through cam body...");

                // Select the hole sketch
                status = swModelExt.SelectByID2(
                    Name: "Sketch2",
                    Type: "SKETCH",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: (int)swSelectOption_e.swSelectOptionDefault);

                // Create cut extrusion through all
                Feature cutFeature = swFeatureMgr.FeatureCut4(
                    Sd: true,                          // Single-ended cut
                    Flip: false,                       // Don't flip
                    Dir: false,                        // Use default direction
                    T1: (int)swEndConditions_e.swEndCondThroughAll,  // Through all
                    T2: (int)swEndConditions_e.swEndCondBlind,       // (not used)
                    D1: 0.0,                           // (through all - depth not needed)
                    D2: 0.0,                           // (not used)
                    Dchk1: false,                      // No draft
                    Dchk2: false,                      // No draft
                    Ddir1: false,                      // (draft not enabled)
                    Ddir2: false,                      // (draft not enabled)
                    Dang1: 0.0,                        // (draft not enabled)
                    Dang2: 0.0,                        // (draft not enabled)
                    OffsetReverse1: false,             // (not using offset)
                    OffsetReverse2: false,             // (not using offset)
                    TranslateSurface1: false,          // (not using offset)
                    TranslateSurface2: false,          // (not using offset)
                    NormalCut: false,                  // Not sheet metal
                    UseFeatScope: false,               // Affect all bodies
                    UseAutoSelect: true,               // Auto-select all bodies
                    AssemblyFeatureScope: false,       // Not an assembly feature
                    AutoSelectComponents: false,       // Not an assembly feature
                    PropagateFeatureToParts: false,    // Not an assembly feature
                    T0: (int)swStartConditions_e.swStartSketchPlane,  // Start from sketch plane
                    StartOffset: 0.0,                  // (not using offset)
                    FlipStartOffset: false,            // (not using offset)
                    OptimizeGeometry: false);          // Not sheet metal

                if (cutFeature == null)
                    throw new InvalidOperationException("Failed to create cut feature for shaft hole");

                swModel.ClearSelection2(true);

                // Zoom to fit
                swModel.ViewZoomtofit2();

                Debug.Print("Cam body created successfully!");
                Debug.Print($"  - Outer diameter: {CAM_DIAMETER * 1000:F3} mm");
                Debug.Print($"  - Thickness: {CAM_THICKNESS * 1000:F3} mm");
                Debug.Print($"  - Shaft hole offset: {ECCENTRICITY * 1000:F3} mm");
                Debug.Print($"  - Shaft diameter: {SHAFT_DIAMETER * 1000:F3} mm");
                Debug.Print($"  - Keyway: {KEYWAY_WIDTH * 1000:F3} mm wide x {KEYWAY_DEPTH * 1000:F3} mm deep");
            }
            catch (Exception ex)
            {
                Debug.Print($"ERROR: {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// The SldWorks swApp variable is pre-assigned for you.
        /// </summary>
        public SldWorks swApp;
    }
}
