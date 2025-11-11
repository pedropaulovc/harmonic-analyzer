// Amplitude Bar - SolidWorks API Translation
// Translated from amplitude-bar.kcl
// Creates a vertical rod with notches at top and bottom

using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace HarmonicAnalyzer
{
    public class AmplitudeBar
    {
        // Input parameters (converted from inches to meters for SolidWorks API)
        private const double barLength = 32.0 * 0.0254;          // 32" = 0.8128 m
        private const double barWidth = 0.25 * 0.0254;            // 0.25" = 0.00635 m
        private const double barDepth = 0.25 * 0.0254;            // 0.25" = 0.00635 m

        // Bottom notch
        private const double bottomNotchWidth = 0.125 * 0.0254;   // 0.125" = 0.003175 m
        private const double bottomNotchHeight = 0.09375 * 0.0254; // 3/32" = 0.00238125 m

        // Top notch
        private const double topNotchWidth = 0.125 * 0.0254;      // 0.125" = 0.003175 m
        private const double topNotchHeight = 0.5 * 0.0254;       // 0.5" = 0.0127 m

        // Calculated parameters
        private static double leftNotchOffset = (barWidth - bottomNotchWidth) / 2;  // 0.003175 m
        private static double rightNotchOffset = (barWidth - topNotchWidth) / 2;    // 0.003175 m

        public static void CreateAmplitudeBar(ISldWorks swApp)
        {
            if (swApp == null)
            {
                throw new ArgumentNullException(nameof(swApp), "SolidWorks application is null");
            }

            // 1. Create new part document
            IModelDoc2 swModel = (IModelDoc2)swApp.NewDocument(
                "",        // Use default part template
                0,         // Paper size (not used for parts)
                0.0,       // Width (not used for parts)
                0.0        // Height (not used for parts)
            );

            if (swModel == null)
            {
                throw new Exception("Failed to create new part document");
            }

            // Get model extension for selection
            IModelDocExtension swModelExt = swModel.Extension;

            // Get sketch manager
            ISketchManager swSketchMgr = swModel.SketchManager;

            // Get feature manager
            IFeatureManager swFeatMgr = swModel.FeatureManager;

            // 2. Select the XZ plane (Front plane in SolidWorks)
            bool selectResult = swModelExt.SelectByID2(
                "Front Plane",              // Plane name
                "PLANE",                    // Selection type
                0, 0, 0,                    // X, Y, Z coordinates (not used for named selection)
                false,                      // Append = false (clear previous selection)
                0,                          // Mark
                null,                       // Callout
                (int)swSelectOption_e.swSelectOptionDefault
            );

            if (!selectResult)
            {
                throw new Exception("Failed to select Front Plane");
            }

            // 3. Insert sketch on selected plane
            swSketchMgr.InsertSketch(true);

            // 4. Draw the profile with notches
            // The profile traces around both centered notches
            //   ##  ##
            //   ##  ##
            //   ##  ##
            //   ######
            //   ######
            //   ######
            //   ######
            //   ######
            //   ######
            //   ######
            //   ######
            //   ######
            //   ##  ##
            //   ##  ##

            // Track current position
            double x = 0.0;
            double z = 0.0;

            // Start at origin [0, 0] and draw lines in sequence
            // Note: In XZ plane, Y is always 0

            // Line 1: Right to leftNotchOffset
            ISketchSegment seg1 = swSketchMgr.CreateLine(x, 0, z, x + leftNotchOffset, 0, z);
            x += leftNotchOffset;

            // Line 2: Up by bottomNotchHeight
            ISketchSegment seg2 = swSketchMgr.CreateLine(x, 0, z, x, 0, z + bottomNotchHeight);
            z += bottomNotchHeight;

            // Line 3: Right by bottomNotchWidth
            ISketchSegment seg3 = swSketchMgr.CreateLine(x, 0, z, x + bottomNotchWidth, 0, z);
            x += bottomNotchWidth;

            // Line 4: Down by bottomNotchHeight
            ISketchSegment seg4 = swSketchMgr.CreateLine(x, 0, z, x, 0, z - bottomNotchHeight);
            z -= bottomNotchHeight;

            // Line 5: Right to leftNotchOffset
            ISketchSegment seg5 = swSketchMgr.CreateLine(x, 0, z, x + leftNotchOffset, 0, z);
            x += leftNotchOffset;

            // Line 6: Up by barLength
            ISketchSegment seg6 = swSketchMgr.CreateLine(x, 0, z, x, 0, z + barLength);
            z += barLength;

            // Line 7: Left by rightNotchOffset
            ISketchSegment seg7 = swSketchMgr.CreateLine(x, 0, z, x - rightNotchOffset, 0, z);
            x -= rightNotchOffset;

            // Line 8: Down by topNotchHeight
            ISketchSegment seg8 = swSketchMgr.CreateLine(x, 0, z, x, 0, z - topNotchHeight);
            z -= topNotchHeight;

            // Line 9: Left by topNotchWidth
            ISketchSegment seg9 = swSketchMgr.CreateLine(x, 0, z, x - topNotchWidth, 0, z);
            x -= topNotchWidth;

            // Line 10: Up by topNotchHeight
            ISketchSegment seg10 = swSketchMgr.CreateLine(x, 0, z, x, 0, z + topNotchHeight);
            z += topNotchHeight;

            // Line 11: Left by rightNotchOffset
            ISketchSegment seg11 = swSketchMgr.CreateLine(x, 0, z, x - rightNotchOffset, 0, z);
            x -= rightNotchOffset;

            // Line 12: Close back to origin (down to z=0)
            ISketchSegment seg12 = swSketchMgr.CreateLine(x, 0, z, 0, 0, 0);

            // 5. Exit sketch
            swSketchMgr.InsertSketch(true);

            // 6. Select the sketch for extrusion
            selectResult = swModelExt.SelectByID2(
                "Sketch1",                  // Sketch name
                "SKETCH",                   // Selection type
                0, 0, 0,                    // X, Y, Z coordinates
                false,                      // Append = false
                0,                          // Mark
                null,                       // Callout
                (int)swSelectOption_e.swSelectOptionDefault
            );

            if (!selectResult)
            {
                throw new Exception("Failed to select sketch for extrusion");
            }

            // 7. Extrude the profile by barDepth
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                true,                       // Sd: Single direction
                false,                      // Flip: Don't flip cut side
                false,                      // Dir: Don't flip direction
                (int)swEndConditions_e.swEndCondBlind,  // T1: Blind end condition
                0,                          // T2: Not used for single direction
                barDepth,                   // D1: Extrusion depth in meters
                0.0,                        // D2: Not used
                false,                      // Dchk1: No draft
                false,                      // Dchk2: No draft
                false,                      // Ddir1: Not used
                false,                      // Ddir2: Not used
                0.0,                        // Dang1: Draft angle
                0.0,                        // Dang2: Draft angle
                false,                      // OffsetReverse1
                false,                      // OffsetReverse2
                false,                      // TranslateSurface1
                false,                      // TranslateSurface2
                true,                       // Merge: Merge results
                false,                      // UseFeatScope: Don't use feature scope
                false,                      // UseAutoSelect: Don't auto-select bodies
                (int)swStartConditions_e.swStartSketchPlane,  // T0: Start from sketch plane
                0.0,                        // StartOffset: No offset
                false                       // FlipStartOffset: Don't flip
            );

            if (extrudeFeature == null)
            {
                throw new Exception("Failed to create extrusion feature");
            }

            // 8. Rebuild and zoom to fit
            swModel.ForceRebuild3(false);
            swModel.ViewZoomtofit2();

            Console.WriteLine("Amplitude bar created successfully!");
            Console.WriteLine($"Bar dimensions: {barLength * 39.3701:F3}\" x {barWidth * 39.3701:F3}\" x {barDepth * 39.3701:F3}\"");
            Console.WriteLine($"Bottom notch: {bottomNotchWidth * 39.3701:F3}\" x {bottomNotchHeight * 39.3701:F3}\"");
            Console.WriteLine($"Top notch: {topNotchWidth * 39.3701:F3}\" x {topNotchHeight * 39.3701:F3}\"");
        }
    }
}
