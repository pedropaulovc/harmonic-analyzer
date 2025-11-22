using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace HarmonicAnalyzer.Cad
{
    /// <summary>
    /// Eccentric Cam - produces harmonic motion for follower
    /// Simple cylinder with off-center mounting hole
    /// Displacement = eccentricity × sin(θ)
    /// </summary>
    public class EccentricCam
    {
        // Shared parameters - converted from inches to meters
        private const double CamDiameter = 2.0 * 0.0254;      // 2.0" -> 0.0508 m
        private const double CamThickness = 0.4 * 0.0254;     // 0.4" -> 0.01016 m
        private const double ShaftDiameter = 0.375 * 0.0254;  // 3/8" -> 0.009525 m
        private const double KeywayWidth = 0.125 * 0.0254;    // 1/8" -> 0.003175 m
        private const double KeywayDepth = 0.06 * 0.0254;     // 0.06" -> 0.001524 m

        // Input parameters - cam geometry
        private const double Eccentricity = 0.2 * 0.0254;     // 0.2" -> 0.00508 m (amplitude of motion)

        // Calculated parameters
        private static double CamRadius => CamDiameter / 2;
        private static double ShaftRadius => ShaftDiameter / 2;
        private static double MinClearance => CamRadius - Eccentricity - ShaftRadius;

        public static void CreatePart()
        {
            // Validate parameters (equivalent to KCL assertions)
            ValidateParameters();

            // Get SolidWorks application
            ISldWorks swApp = (ISldWorks)Marshal.GetActiveObject("SldWorks.Application");
            if (swApp == null)
            {
                throw new InvalidOperationException("SolidWorks application not found");
            }

            // Create new part document using default part template
            string partTemplate = swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplatePart);

            IModelDoc2 swModel = (IModelDoc2)swApp.NewDocument(
                defaultTemplate: partTemplate,
                paperSize: 0,
                width: 0,
                height: 0);

            if (swModel == null)
            {
                throw new InvalidOperationException("Failed to create new part document");
            }

            IModelDocExtension swModelExt = swModel.Extension;
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatureMgr = swModel.FeatureManager;

            // Step 1: Create cam body (circular sketch on Front Plane)
            CreateCamBody(swModelExt, swSketchMgr, swFeatureMgr);

            // Step 2: Create shaft hole with keyway (cut through cam body)
            CreateShaftHoleWithKeyway(swModelExt, swSketchMgr, swFeatureMgr);

            // Rebuild and zoom to fit
            swModel.ForceRebuild3(false);
            swModel.ViewZoomtofit2();
        }

        private static void ValidateParameters()
        {
            // Assert: Cam diameter must be larger than shaft
            if (CamDiameter <= ShaftDiameter)
            {
                throw new ArgumentException("Cam diameter must be larger than shaft");
            }

            // Assert: Eccentricity must be greater than 0 and less than cam radius
            if (Eccentricity <= 0 || Eccentricity >= CamRadius)
            {
                throw new ArgumentException("Eccentricity must be less than cam radius");
            }

            // Assert: Shaft hole too close to cam edge
            if (MinClearance <= 0)
            {
                throw new ArgumentException("Shaft hole too close to cam edge");
            }

            // Assert: Cam thickness must be positive
            if (CamThickness <= 0)
            {
                throw new ArgumentException("Cam thickness must be positive");
            }

            // Assert: Keyway too wide for shaft
            if (KeywayWidth >= ShaftDiameter)
            {
                throw new ArgumentException("Keyway too wide for shaft");
            }
        }

        private static void CreateCamBody(
            IModelDocExtension swModelExt,
            ISketchManager swSketchMgr,
            IFeatureManager swFeatureMgr)
        {
            // Select Front Plane (equivalent to XY plane in KCL)
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                throw new InvalidOperationException("Failed to select Front Plane");
            }

            // Insert sketch on Front Plane
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Create circle centered at origin with cam radius
            // CreateCircle(XC, YC, ZC, Xp, Yp, Zp) - center and point on circle
            ISketchSegment circle = swSketchMgr.CreateCircle(
                XC: 0, YC: 0, Zc: 0,
                Xp: CamRadius, Yp: 0, Zp: 0);

            if (circle == null)
            {
                throw new InvalidOperationException("Failed to create cam body circle");
            }

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Select the sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: "Sketch1",
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                throw new InvalidOperationException("Failed to select cam body sketch");
            }

            // Extrude cam body
            IFeature extrudeFeature = swFeatureMgr.FeatureExtrusion2(
                sd: true,                                           // Single direction
                flip: false,                                        // Don't flip direction
                dir: false,                                         // Default direction
                dir1: (int)swEndConditions_e.swEndCondBlind,       // Blind extrusion
                dir2: (int)swEndConditions_e.swEndCondBlind,
                d1: CamThickness,                                   // Extrusion depth
                d2: 0,
                dchk1: false,                                       // No draft
                dchk2: false,
                ddir1: false,
                ddir2: false,
                dang1: 0,
                dang2: 0,
                offstatus: false,
                offstatus1: false,
                offdirection1: false,
                offdirection2: false,
                merge: false,
                useFeatScope: false,
                useAutoSelect: true,
                t0: (int)swStartConditions_e.swStartSketchPlane,   // Start from sketch plane
                startOffset: 0,
                flipStartOffset: false);

            if (extrudeFeature == null)
            {
                throw new InvalidOperationException("Failed to extrude cam body");
            }
        }

        private static void CreateShaftHoleWithKeyway(
            IModelDocExtension swModelExt,
            ISketchManager swSketchMgr,
            IFeatureManager swFeatureMgr)
        {
            // Select Front Plane for shaft hole sketch
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                throw new InvalidOperationException("Failed to select Front Plane for shaft hole");
            }

            // Insert sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Calculate keyway geometry (matching KCL calculations)
            double startAngle = Math.Asin(KeywayWidth / 2 / ShaftRadius);

            // Calculate profile points - shaft hole positioned at [eccentricity, 0]
            // Profile starts at top of keyway
            double x0 = Eccentricity + ShaftRadius * Math.Cos(startAngle);
            double y0 = ShaftRadius * Math.Sin(startAngle);

            // Create keyway and shaft profile
            // Line 1: Horizontal line for top of keyway (going right)
            ISketchSegment line1 = swSketchMgr.CreateLine(
                X1: x0, Y1: y0, Z1: 0,
                X2: x0 + KeywayDepth, Y2: y0, Z2: 0);

            // Line 2: Vertical line down (right side of keyway)
            ISketchSegment line2 = swSketchMgr.CreateLine(
                X1: x0 + KeywayDepth, Y1: y0, Z1: 0,
                X2: x0 + KeywayDepth, Y2: -y0, Z2: 0);

            // Line 3: Horizontal line back to shaft (bottom of keyway)
            ISketchSegment line3 = swSketchMgr.CreateLine(
                X1: x0 + KeywayDepth, Y1: -y0, Z1: 0,
                X2: x0, Y2: -y0, Z2: 0);

            // Arc 1: Bottom half of shaft (from -startAngle to 180°)
            // Center is at [eccentricity, 0]
            // Start point is at [x0, -y0]
            // End point is at [eccentricity - shaftRadius, 0]
            ISketchSegment arc1 = swSketchMgr.CreateArc(
                XC: Eccentricity, YC: 0, Zc: 0,
                X1: x0, Y1: -y0, Z1: 0,
                X2: Eccentricity - ShaftRadius, Y2: 0, Z2: 0,
                Direction: 1);  // Counter-clockwise

            // Arc 2: Top half of shaft (from 180° to startAngle)
            // Start point is at [eccentricity - shaftRadius, 0]
            // End point is at [x0, y0]
            ISketchSegment arc2 = swSketchMgr.CreateArc(
                XC: Eccentricity, YC: 0, Zc: 0,
                X1: Eccentricity - ShaftRadius, Y1: 0, Z1: 0,
                X2: x0, Y2: y0, Z2: 0,
                Direction: 1);  // Counter-clockwise

            if (line1 == null || line2 == null || line3 == null || arc1 == null || arc2 == null)
            {
                throw new InvalidOperationException("Failed to create shaft hole profile");
            }

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Select the shaft hole sketch for cut extrusion
            selected = swModelExt.SelectByID2(
                Name: "Sketch2",
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                throw new InvalidOperationException("Failed to select shaft hole sketch");
            }

            // Cut extrude through all
            IFeature cutFeature = swFeatureMgr.FeatureCut4(
                Sd: true,                                           // Single direction
                Flip: false,                                        // Don't flip side to cut
                Dir: false,                                         // Default direction
                T1: (int)swEndConditions_e.swEndCondThroughAll,    // Through all
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: 0,                                              // Not used with Through All
                D2: 0,
                Dchk1: false,                                       // No draft
                Dchk2: false,
                Ddir1: false,
                Ddir2: false,
                Dang1: 0,
                Dang2: 0,
                OffsetReverse1: false,
                OffsetReverse2: false,
                TranslateSurface1: false,
                TranslateSurface2: false,
                NormalCut: false,
                UseFeatScope: false,
                UseAutoSelect: true,
                AssemblyFeatureScope: false,
                AutoSelectComponents: false,
                PropagateFeatureToParts: false,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false,
                OptimizeGeometry: false);

            if (cutFeature == null)
            {
                throw new InvalidOperationException("Failed to create shaft hole cut");
            }
        }
    }
}
