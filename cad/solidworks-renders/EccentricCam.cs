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
    public class EccentricCam
    {
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
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select the top face of the extruded cam for the cut sketch
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select plane for hole sketch");

            // Insert sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Calculate shaft hole with keyway profile parameters
            double shaftRadius = ShaftDiameter / 2;
            double startAngle = Math.Asin(KeywayWidth / 2 / shaftRadius);

            // Calculate profile start point (on the shaft circle, offset by eccentricity)
            double startX = Eccentricity + shaftRadius * Math.Cos(startAngle);
            double startY = shaftRadius * Math.Sin(startAngle);

            // Enable AddToDB for performance
            swSketchMgr.AddToDB = true;
            swSketchMgr.DisplayWhenAdded = false;

            // Create keyway rectangle portion (extending outward from circle)
            // Line 1: Horizontal line going outward (keyway depth)
            ISketchSegment line1 = swSketchMgr.CreateLine(
                X1: startX, Y1: startY, Z1: 0,
                X2: startX + KeywayDepth, Y2: startY, Z2: 0);

            // Line 2: Vertical line going down (keyway width)
            ISketchSegment line2 = swSketchMgr.CreateLine(
                X1: startX + KeywayDepth, Y1: startY, Z1: 0,
                X2: startX + KeywayDepth, Y2: startY - KeywayWidth, Z2: 0);

            // Line 3: Horizontal line going back (closing keyway)
            ISketchSegment line3 = swSketchMgr.CreateLine(
                X1: startX + KeywayDepth, Y1: startY - KeywayWidth, Z1: 0,
                X2: startX, Y2: startY - KeywayWidth, Z2: 0);

            // Arc 1: From bottom of keyway to opposite side (clockwise, covering ~180°)
            // Start angle: -startAngle + 360° (bottom of keyway)
            // End angle: 180° (opposite side of circle)
            double arc1StartX = startX;
            double arc1StartY = startY - KeywayWidth;
            double arc1EndX = Eccentricity - shaftRadius;
            double arc1EndY = 0;

            ISketchSegment arc1 = swSketchMgr.CreateArc(
                XC: Eccentricity, YC: 0, Zc: 0,
                X1: arc1StartX, Y1: arc1StartY, Z1: 0,
                X2: arc1EndX, Y2: arc1EndY, Z2: 0,
                Direction: -1);  // Clockwise

            // Arc 2: From opposite side back to start of keyway (clockwise, covering remaining angle)
            // Start angle: 180°
            // End angle: startAngle
            double arc2StartX = arc1EndX;
            double arc2StartY = arc1EndY;
            double arc2EndX = startX;
            double arc2EndY = startY;

            ISketchSegment arc2 = swSketchMgr.CreateArc(
                XC: Eccentricity, YC: 0, Zc: 0,
                X1: arc2StartX, Y1: arc2StartY, Z1: 0,
                X2: arc2EndX, Y2: arc2EndY, Z2: 0,
                Direction: -1);  // Clockwise

            // Disable AddToDB and refresh display
            swSketchMgr.AddToDB = false;
            swSketchMgr.DisplayWhenAdded = true;
            swModel.GraphicsRedraw2();

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Select the sketch for cut extrusion
            selected = swModelExt.SelectByID2(
                Name: "Sketch2",
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select hole sketch for cut");

            // Cut through the entire cam thickness
            IFeature cutFeature = swFeatMgr.FeatureCut4(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Don't flip direction
                T1: (int)swEndConditions_e.swEndCondThroughAll,   // Cut through all
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
                UseFeatScope: false,                               // Affect all bodies
                UseAutoSelect: true,                               // Auto-select bodies
                AssemblyFeatureScope: false,                       // Not an assembly feature
                AutoSelectComponents: false,                       // Not an assembly feature
                PropagateFeatureToParts: false,                    // Not an assembly feature
                T0: (int)swStartConditions_e.swStartSketchPlane,  // Start from sketch plane
                StartOffset: 0,                                    // No start offset
                FlipStartOffset: false,                            // Don't flip start offset
                OptimizeGeometry: false);                          // Not a sheet metal part

            if (cutFeature == null)
                throw new InvalidOperationException("Failed to create shaft hole cut");
        }
    }
}
