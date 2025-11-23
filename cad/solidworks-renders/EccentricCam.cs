using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates an eccentric cam part for harmonic motion generation.
    /// Translated from eccentric-cam.kcl
    ///
    /// The cam produces harmonic motion with displacement = eccentricity × sin(θ)
    /// Features a simple cylinder with off-center mounting hole and keyway.
    /// </summary>
    public class EccentricCam : IPartCreator
    {
        public string PartName => "Eccentric Cam";
        // Parameters from parameters.kcl (in inches, converted to meters for SolidWorks API)
        private const double CamDiameter = 2.0 * 0.0254;        // 2.0 inches
        private const double CamThickness = 0.4 * 0.0254;       // 0.4 inches
        private const double ShaftDiameter = 0.375 * 0.0254;    // 0.375 inches (3/8")
        private const double KeywayWidth = 0.125 * 0.0254;      // 0.125 inches (1/8")
        private const double KeywayDepth = 0.06 * 0.0254;       // 0.06 inches

        // Eccentric cam specific parameter
        private const double Eccentricity = 0.2 * 0.0254;       // 0.2 inches - offset distance from center

        private ISldWorks swApp;

        public EccentricCam(ISldWorks solidWorksApp)
        {
            swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));
        }

        /// <summary>
        /// Creates the eccentric cam part
        /// </summary>
        public IModelDoc2 CreatePart()
        {
            // Get part template from user preferences
            string partTemplate = swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplatePart);

            if (string.IsNullOrEmpty(partTemplate))
            {
                throw new InvalidOperationException("No part template found. Please set a default part template in SolidWorks options.");
            }

            // Create new part document
            IModelDoc2 swModel = (IModelDoc2)swApp.NewDocument(
                TemplateName: partTemplate,
                PaperSize: 0,
                Width: 0,
                Height: 0);

            if (swModel == null)
            {
                throw new InvalidOperationException("Failed to create new part document");
            }

            // Validate design parameters (assertions from KCL)
            ValidateParameters();

            // Create the cam geometry
            CreateCamBody(swModel);
            CreateShaftHoleWithKeyway(swModel);

            // Rebuild the model
            swModel.ForceRebuild3(true);

            return swModel;
        }

        /// <summary>
        /// Validates design parameters (translated from KCL assertions)
        /// </summary>
        private void ValidateParameters()
        {
            double camRadius = CamDiameter / 2;
            double minClearance = camRadius - Eccentricity - ShaftDiameter / 2;

            if (CamDiameter <= ShaftDiameter)
                throw new ArgumentException("Cam diameter must be larger than shaft");

            if (Eccentricity <= 0 || Eccentricity >= camRadius)
                throw new ArgumentException("Eccentricity must be greater than 0 and less than cam radius");

            if (minClearance <= 0)
                throw new ArgumentException("Shaft hole too close to cam edge");

            if (CamThickness <= 0)
                throw new ArgumentException("Cam thickness must be positive");

            if (KeywayWidth >= ShaftDiameter)
                throw new ArgumentException("Keyway too wide for shaft");
        }

        /// <summary>
        /// Creates the circular cam body centered at origin
        /// </summary>
        private void CreateCamBody(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane (XY plane equivalent)
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane");

            // Insert sketch on Front Plane
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Create circular cam body (centered at origin)
            double camRadius = CamDiameter / 2;
            ISketchSegment camCircle = swSketchMgr.CreateCircle(
                XC: 0, YC: 0, Zc: 0,
                Xp: camRadius, Yp: 0, Zp: 0);

            if (camCircle == null)
                throw new InvalidOperationException("Failed to create cam circle");

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
                throw new InvalidOperationException("Failed to select sketch for extrusion");

            // Extrude the cam body
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Don't flip extrusion direction
                T1: (int)swEndConditions_e.swEndCondBlind,        // Blind extrusion
                T2: (int)swEndConditions_e.swEndCondBlind,        // Not used for single direction
                D1: CamThickness,                                  // Extrusion depth
                D2: 0,                                             // Not used for single direction
                Dchk1: false,                                      // No draft
                Dchk2: false,                                      // No draft
                Ddir1: false,                                      // Draft direction (not used)
                Ddir2: false,                                      // Draft direction (not used)
                Dang1: 0,                                          // Draft angle (not used)
                Dang2: 0,                                          // Draft angle (not used)
                OffsetReverse1: false,                             // Offset direction (not used)
                OffsetReverse2: false,                             // Offset direction (not used)
                TranslateSurface1: false,                          // Translation (not used)
                TranslateSurface2: false,                          // Translation (not used)
                Merge: true,                                       // Merge result
                UseFeatScope: false,                               // Affect all bodies
                UseAutoSelect: true,                               // Auto-select bodies
                T0: (int)swStartConditions_e.swStartSketchPlane,  // Start from sketch plane
                StartOffset: 0,                                    // No start offset
                FlipStartOffset: false);                           // Don't flip start offset

            if (extrudeFeature == null)
                throw new InvalidOperationException("Failed to extrude cam body");
        }

        /// <summary>
        /// Creates shaft hole with keyway, positioned at eccentricity offset
        /// The hole is positioned at [eccentricity, 0] to create eccentric motion
        /// </summary>
        private void CreateShaftHoleWithKeyway(IModelDoc2 swModel)
        {
            // Create shaft hole as a simple circle
            CreateShaftHole(swModel);

            // Create keyway as a rectangular cut
            CreateKeyway(swModel);
        }

        /// <summary>
        /// Creates the circular shaft hole at eccentric position
        /// </summary>
        private void CreateShaftHole(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

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
                throw new InvalidOperationException("Failed to select Front Plane for shaft hole");

            // Insert sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Create circular shaft hole offset by eccentricity
            double shaftRadius = ShaftDiameter / 2;
            ISketchSegment shaftCircle = swSketchMgr.CreateCircle(
                XC: Eccentricity, YC: 0, Zc: 0,
                Xp: Eccentricity + shaftRadius, Yp: 0, Zp: 0);

            if (shaftCircle == null)
                throw new InvalidOperationException("Failed to create shaft hole circle");

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Select the sketch for cutting
            selected = swModelExt.SelectByID2(
                Name: "Sketch2",
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select shaft hole sketch");

            // Cut through all - using parameters from working VBA example
            IFeature holeFeature = swFeatMgr.FeatureCut4(
                Sd: true,                                          // Single-ended cut
                Flip: false,                                       // Don't flip side to cut
                Dir: true,                                         // Flip direction (VBA uses True)
                T1: (int)swEndConditions_e.swEndCondThroughAll,   // Through all
                T2: 0,                                             // Not used
                D1: 0,                                             // Not needed for through all
                D2: 0,                                             // Not used
                Dchk1: false,                                      // No draft
                Dchk2: false,                                      // No draft
                Ddir1: false,                                      // Draft direction (not used)
                Ddir2: false,                                      // Draft direction (not used)
                Dang1: 0,                                          // Draft angle (not used)
                Dang2: 0,                                          // Draft angle (not used)
                OffsetReverse1: false,                             // Offset direction (not used)
                OffsetReverse2: false,                             // Offset direction (not used)
                TranslateSurface1: false,                          // Translation (not used)
                TranslateSurface2: false,                          // Translation (not used)
                NormalCut: false,                                  // Not a sheet metal part
                UseFeatScope: true,                                // Feature affects selected bodies (VBA uses True)
                UseAutoSelect: true,                               // Auto-select bodies
                AssemblyFeatureScope: true,                        // Assembly feature scope (VBA uses True)
                AutoSelectComponents: true,                        // Auto-select components (VBA uses True)
                PropagateFeatureToParts: false,                    // Don't propagate to parts
                T0: (int)swStartConditions_e.swStartSketchPlane,  // Start from sketch plane
                StartOffset: 0,                                    // No start offset
                FlipStartOffset: false,                            // Don't flip start offset
                OptimizeGeometry: false);                          // Not a sheet metal part

            if (holeFeature == null)
                throw new InvalidOperationException("Failed to create shaft hole cut");
        }

        /// <summary>
        /// Creates the keyway as a rectangular cut
        /// </summary>
        private void CreateKeyway(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane for keyway sketch
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for keyway");

            // Insert sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Create keyway rectangle
            // Position: starts from the edge of the shaft hole and extends outward
            double shaftRadius = ShaftDiameter / 2;
            double keywayLeft = Eccentricity + shaftRadius;
            double keywayRight = keywayLeft + KeywayDepth;
            double keywayTop = KeywayWidth / 2;
            double keywayBottom = -KeywayWidth / 2;

            // Create corner rectangle - this creates a proper closed contour
            object rect = swSketchMgr.CreateCornerRectangle(
                X1: keywayLeft, Y1: keywayTop, Z1: 0,
                X2: keywayRight, Y2: keywayBottom, Z2: 0);

            if (rect == null)
                throw new InvalidOperationException("Failed to create keyway rectangle");

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rebuild to ensure sketch is recognized
            swModel.ForceRebuild3(false);

            // Get the last feature added (should be the keyway sketch)
            IFeature keywaySketch = swModelExt.GetLastFeatureAdded();
            if (keywaySketch == null)
                throw new InvalidOperationException("Failed to get keyway sketch - no feature was added");

            string sketchName = keywaySketch.Name;
            Console.WriteLine($"DEBUG: Keyway sketch name: {sketchName}");

            // Select the sketch for cutting
            selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select keyway sketch '{sketchName}'");

            // Cut through all - using parameters from working VBA example
            IFeature keywayFeature = swFeatMgr.FeatureCut4(
                Sd: true,
                Flip: false,
                Dir: true,                                         // Flip direction (VBA uses True)
                T1: (int)swEndConditions_e.swEndCondThroughAll,
                T2: 0,
                D1: 0,
                D2: 0,
                Dchk1: false,
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
                UseFeatScope: true,                                // Feature affects selected bodies (VBA uses True)
                UseAutoSelect: true,
                AssemblyFeatureScope: true,                        // Assembly feature scope (VBA uses True)
                AutoSelectComponents: true,                        // Auto-select components (VBA uses True)
                PropagateFeatureToParts: false,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false,
                OptimizeGeometry: false);

            if (keywayFeature == null)
            {
                // Get the last feature added (even if it failed) to check error code
                IFeature lastFeature = swModelExt.GetLastFeatureAdded();
                if (lastFeature != null)
                {
                    bool isWarning;
                    int errorCode = lastFeature.GetErrorCode2(out isWarning);
                    string errorMsg = $"Failed to create keyway cut. Error code: {errorCode} ({(swFeatureError_e)errorCode})";
                    if (errorCode != 0)
                    {
                        errorMsg += isWarning ? " (Warning)" : " (Error)";
                    }
                    throw new InvalidOperationException(errorMsg);
                }
                throw new InvalidOperationException("Failed to create keyway cut - no feature created");
            }
        }

        /// <summary>
        /// Prints eccentric cam-specific part details
        /// </summary>
        public void PrintPartDetails()
        {
            Console.WriteLine("\nPart Details:");
            Console.WriteLine("- Cam diameter: 2.0 inches");
            Console.WriteLine("- Cam thickness: 0.4 inches");
            Console.WriteLine("- Shaft diameter: 0.375 inches (3/8\")");
            Console.WriteLine("- Eccentricity: 0.2 inches");
            Console.WriteLine("- Keyway width: 0.125 inches (1/8\")");
            Console.WriteLine("- Keyway depth: 0.06 inches");
        }
    }
}
