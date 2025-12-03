using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates a rocker arm support (A-frame bearing stand) for the harmonic analyzer.
    ///
    /// Features:
    /// - Base plate with mounting holes for securing to table
    /// - Tapered A-frame body (trapezoid profile)
    /// - Center cutout window (weight reduction)
    /// - Cylindrical bearing housing at top
    /// - Through-hole for pivot shaft
    /// - Lifting eyelet at top with chain attachment
    /// </summary>
    public class RockerArmSupport : IPartCreator
    {
        public string PartName => "Rocker Arm Support";
        public string FileName => "rocker-arm-support.sldprt";
        public string Description => "A-frame bearing stand with mounting holes";

        // Dimensions in meters (SI units for SolidWorks API)
        private const double InchToMeter = 0.0254;

        // Base plate dimensions
        private const double BasePlateWidth = 4.0 * InchToMeter;      // Width (X direction)
        private const double BasePlateDepth = 1.5 * InchToMeter;      // Depth (Y direction)
        private const double BasePlateThickness = 0.25 * InchToMeter; // Thickness (Z direction)

        // A-frame body dimensions
        private const double FrameHeight = 6.0 * InchToMeter;         // Total height from base
        private const double FrameBottomWidth = 3.5 * InchToMeter;    // Width at base (X direction)
        private const double FrameTopWidth = 1.5 * InchToMeter;       // Width at top (X direction)
        private const double FrameThickness = 0.375 * InchToMeter;    // Thickness (Y direction)

        // Center cutout dimensions
        private const double CutoutWidth = 2.0 * InchToMeter;         // Width of cutout
        private const double CutoutHeight = 3.5 * InchToMeter;        // Height of cutout
        private const double CutoutBottomOffset = 0.75 * InchToMeter; // Distance from base to cutout bottom

        // Bearing housing dimensions
        private const double BearingHousingRadius = 0.75 * InchToMeter;
        private const double BearingHousingDepth = 1.25 * InchToMeter; // Depth/length of cylinder
        private const double BearingHoleRadius = 0.375 * InchToMeter;  // Through-hole for shaft

        // Mounting holes
        private const double MountingHoleRadius = 0.1875 * InchToMeter; // 3/8" holes
        private const double MountingHoleInsetX = 0.5 * InchToMeter;    // Inset from edge
        private const double MountingHoleInsetY = 0.375 * InchToMeter;  // Inset from edge

        // Lifting eyelet dimensions
        private const double EyeletInnerRadius = 0.25 * InchToMeter;
        private const double EyeletOuterRadius = 0.5 * InchToMeter;
        private const double EyeletThickness = 0.25 * InchToMeter;
        private const double EyeletConnectorHeight = 0.5 * InchToMeter;
        private const double EyeletConnectorWidth = 0.5 * InchToMeter;

        private ISldWorks swApp;

        public RockerArmSupport(ISldWorks solidWorksApp)
        {
            swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));
        }

        public IModelDoc2 CreatePart()
        {
            string partTemplate = swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplatePart);

            if (string.IsNullOrEmpty(partTemplate))
            {
                throw new InvalidOperationException("No part template found. Please set a default part template in SolidWorks options.");
            }

            IModelDoc2 swModel = (IModelDoc2)swApp.NewDocument(
                TemplateName: partTemplate,
                PaperSize: 0,
                Width: 0,
                Height: 0);

            if (swModel == null)
            {
                throw new InvalidOperationException("Failed to create new part document");
            }

            // Create components in order
            Console.WriteLine("Creating base plate...");
            CreateBasePlate(swModel);

            Console.WriteLine("Creating A-frame body...");
            CreateAFrameBody(swModel);

            Console.WriteLine("Creating center cutout...");
            CreateCenterCutout(swModel);

            Console.WriteLine("Creating bearing housing...");
            CreateBearingHousing(swModel);

            Console.WriteLine("Creating bearing through-hole...");
            CreateBearingHole(swModel);

            Console.WriteLine("Creating mounting holes...");
            CreateMountingHoles(swModel);

            Console.WriteLine("Creating lifting eyelet...");
            CreateLiftingEyelet(swModel);

            // Rebuild the model
            swModel.ForceRebuild3(true);

            return swModel;
        }

        /// <summary>
        /// Creates the base plate on the XY plane
        /// </summary>
        private void CreateBasePlate(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Top Plane (XY)
            bool selected = swModelExt.SelectByID2(
                Name: "Top Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Top Plane for base plate");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Create rectangle centered at origin
            swSketchMgr.CreateCenterRectangle(
                X1: 0, Y1: 0, Z1: 0,
                X2: BasePlateWidth / 2, Y2: BasePlateDepth / 2, Z2: 0);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rename sketch
            swModel.ForceRebuild3(false);
            IFeature plateSketch = swModelExt.GetLastFeatureAdded();
            plateSketch.Name = "Base Plate Sketch";

            // Select sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: plateSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select base plate sketch for extrusion");

            // Extrude downward (negative Z)
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: true,                                          // Single direction
                Flip: false,
                Dir: true,                                         // Flip direction (down)
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: BasePlateThickness,
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
                Merge: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false);

            if (extrudeFeature == null)
                throw new InvalidOperationException("Failed to extrude base plate");

            extrudeFeature.Name = "Base Plate";
        }

        /// <summary>
        /// Creates the A-frame body (trapezoid profile) on Front Plane
        /// </summary>
        private void CreateAFrameBody(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane (XZ)
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for A-frame body");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Create trapezoid profile (A-frame cross section)
            // Bottom left, bottom right, top right, top left
            double bottomHalf = FrameBottomWidth / 2;
            double topHalf = FrameTopWidth / 2;

            // Start at bottom left, go clockwise
            // Bottom edge
            swSketchMgr.CreateLine(-bottomHalf, 0, 0, bottomHalf, 0, 0);
            // Right edge (tapered)
            swSketchMgr.CreateLine(bottomHalf, 0, 0, topHalf, FrameHeight, 0);
            // Top edge
            swSketchMgr.CreateLine(topHalf, FrameHeight, 0, -topHalf, FrameHeight, 0);
            // Left edge (tapered)
            swSketchMgr.CreateLine(-topHalf, FrameHeight, 0, -bottomHalf, 0, 0);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rename sketch
            swModel.ForceRebuild3(false);
            IFeature frameSketch = swModelExt.GetLastFeatureAdded();
            frameSketch.Name = "A-Frame Sketch";

            // Select sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: frameSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select A-frame sketch for extrusion");

            // Extrude symmetric (both directions in Y)
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,                                         // Both directions
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: FrameThickness / 2,
                D2: FrameThickness / 2,
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
                Merge: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false);

            if (extrudeFeature == null)
                throw new InvalidOperationException("Failed to extrude A-frame body");

            extrudeFeature.Name = "A-Frame Body";
        }

        /// <summary>
        /// Creates the center cutout window
        /// </summary>
        private void CreateCenterCutout(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane (XZ)
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for cutout");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Create rectangle for cutout (trapezoid shape to match A-frame taper)
            // Calculate width at bottom and top of cutout based on taper
            double taperRatio = (FrameBottomWidth - FrameTopWidth) / (2 * FrameHeight);

            double cutoutBottom = CutoutBottomOffset;
            double cutoutTop = CutoutBottomOffset + CutoutHeight;

            // Width at cutout bottom and top (following the taper)
            double widthAtBottom = FrameBottomWidth / 2 - taperRatio * cutoutBottom;
            double widthAtTop = FrameBottomWidth / 2 - taperRatio * cutoutTop;

            // Use a simpler centered rectangle cutout (not following taper exactly)
            double cutoutHalfWidth = CutoutWidth / 2;

            // Bottom left corner
            double blX = -cutoutHalfWidth;
            double blZ = cutoutBottom;
            // Bottom right
            double brX = cutoutHalfWidth;
            double brZ = cutoutBottom;
            // Top right
            double trX = cutoutHalfWidth;
            double trZ = cutoutTop;
            // Top left
            double tlX = -cutoutHalfWidth;
            double tlZ = cutoutTop;

            swSketchMgr.CreateLine(blX, blZ, 0, brX, brZ, 0);
            swSketchMgr.CreateLine(brX, brZ, 0, trX, trZ, 0);
            swSketchMgr.CreateLine(trX, trZ, 0, tlX, tlZ, 0);
            swSketchMgr.CreateLine(tlX, tlZ, 0, blX, blZ, 0);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rename sketch
            swModel.ForceRebuild3(false);
            IFeature cutoutSketch = swModelExt.GetLastFeatureAdded();
            cutoutSketch.Name = "Center Cutout Sketch";

            // Select sketch for cut
            selected = swModelExt.SelectByID2(
                Name: cutoutSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select cutout sketch");
                return;
            }

            // Cut through all
            IFeature cutFeature = swFeatMgr.FeatureCut4(
                Sd: false,                                         // Both directions
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondThroughAll,
                T2: (int)swEndConditions_e.swEndCondThroughAll,
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
                Console.WriteLine("WARNING: Failed to create center cutout - continuing without it");
            }
            else
            {
                cutFeature.Name = "Center Cutout";
            }
        }

        /// <summary>
        /// Creates the bearing housing cylinder at the top
        /// </summary>
        private void CreateBearingHousing(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane (XZ)
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for bearing housing");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Create circle at top center of frame
            swSketchMgr.CreateCircleByRadius(
                XC: 0,
                YC: FrameHeight,
                Zc: 0,
                Radius: BearingHousingRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rename sketch
            swModel.ForceRebuild3(false);
            IFeature housingSketch = swModelExt.GetLastFeatureAdded();
            housingSketch.Name = "Bearing Housing Sketch";

            // Select sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: housingSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select bearing housing sketch for extrusion");

            // Extrude symmetric (both directions in Y)
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,                                         // Both directions
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: BearingHousingDepth / 2,
                D2: BearingHousingDepth / 2,
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
                Merge: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false);

            if (extrudeFeature == null)
                throw new InvalidOperationException("Failed to extrude bearing housing");

            extrudeFeature.Name = "Bearing Housing";
        }

        /// <summary>
        /// Creates the through-hole in the bearing housing
        /// </summary>
        private void CreateBearingHole(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane (XZ)
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
                Console.WriteLine("WARNING: Failed to select Front Plane for bearing hole");
                return;
            }

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Create circle at bearing center
            swSketchMgr.CreateCircleByRadius(
                XC: 0,
                YC: FrameHeight,
                Zc: 0,
                Radius: BearingHoleRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rename sketch
            swModel.ForceRebuild3(false);
            IFeature holeSketch = swModelExt.GetLastFeatureAdded();
            holeSketch.Name = "Bearing Hole Sketch";

            // Select sketch for cut
            selected = swModelExt.SelectByID2(
                Name: holeSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select bearing hole sketch");
                return;
            }

            // Cut through all
            IFeature cutFeature = swFeatMgr.FeatureCut4(
                Sd: false,                                         // Both directions
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondThroughAll,
                T2: (int)swEndConditions_e.swEndCondThroughAll,
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
                Console.WriteLine("WARNING: Failed to create bearing hole - continuing without it");
            }
            else
            {
                cutFeature.Name = "Bearing Through-Hole";
            }
        }

        /// <summary>
        /// Creates mounting holes in the base plate (4 corners)
        /// </summary>
        private void CreateMountingHoles(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Top Plane (XY)
            bool selected = swModelExt.SelectByID2(
                Name: "Top Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select Top Plane for mounting holes");
                return;
            }

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Calculate hole positions (4 corners)
            double holeX = BasePlateWidth / 2 - MountingHoleInsetX;
            double holeY = BasePlateDepth / 2 - MountingHoleInsetY;

            // Create 4 holes at corners
            swSketchMgr.CreateCircleByRadius(-holeX, -holeY, 0, MountingHoleRadius);
            swSketchMgr.CreateCircleByRadius(holeX, -holeY, 0, MountingHoleRadius);
            swSketchMgr.CreateCircleByRadius(holeX, holeY, 0, MountingHoleRadius);
            swSketchMgr.CreateCircleByRadius(-holeX, holeY, 0, MountingHoleRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rename sketch
            swModel.ForceRebuild3(false);
            IFeature holesSketch = swModelExt.GetLastFeatureAdded();
            holesSketch.Name = "Mounting Holes Sketch";

            // Select sketch for cut
            selected = swModelExt.SelectByID2(
                Name: holesSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select mounting holes sketch");
                return;
            }

            // Cut through the base plate (both directions to ensure it passes through)
            IFeature cutFeature = swFeatMgr.FeatureCut4(
                Sd: false,                                         // Both directions
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondThroughAll,
                T2: (int)swEndConditions_e.swEndCondThroughAll,
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
                Console.WriteLine("WARNING: Failed to create mounting holes - continuing without them");
            }
            else
            {
                cutFeature.Name = "Mounting Holes";
            }
        }

        /// <summary>
        /// Creates the lifting eyelet at the top of the frame
        /// </summary>
        private void CreateLiftingEyelet(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // First create the connector piece between bearing housing and eyelet
            // Select Right Plane (YZ)
            bool selected = swModelExt.SelectByID2(
                Name: "Right Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select Right Plane for eyelet connector");
                return;
            }

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Create connector rectangle from top of bearing housing upward
            double connectorBottom = FrameHeight + BearingHousingRadius * 0.7; // Start above bearing housing
            double connectorTop = connectorBottom + EyeletConnectorHeight;
            double halfWidth = EyeletConnectorWidth / 2;

            swSketchMgr.CreateCenterRectangle(
                X1: 0, Y1: (connectorBottom + connectorTop) / 2, Z1: 0,
                X2: halfWidth, Y2: connectorTop, Z2: 0);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rename sketch
            swModel.ForceRebuild3(false);
            IFeature connectorSketch = swModelExt.GetLastFeatureAdded();
            connectorSketch.Name = "Eyelet Connector Sketch";

            // Select sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: connectorSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select eyelet connector sketch");
                return;
            }

            // Extrude symmetric (both directions in X)
            IFeature connectorFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: EyeletThickness / 2,
                D2: EyeletThickness / 2,
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
                Merge: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false);

            if (connectorFeature == null)
            {
                Console.WriteLine("WARNING: Failed to create eyelet connector");
            }
            else
            {
                connectorFeature.Name = "Eyelet Connector";
            }

            // Now create the eyelet ring
            selected = swModelExt.SelectByID2(
                Name: "Right Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select Right Plane for eyelet ring");
                return;
            }

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Create two concentric circles for the eyelet ring
            double eyeletCenterZ = connectorTop + EyeletOuterRadius;

            // Outer circle
            swSketchMgr.CreateCircleByRadius(
                XC: 0,
                YC: eyeletCenterZ,
                Zc: 0,
                Radius: EyeletOuterRadius);

            // Inner circle (hole)
            swSketchMgr.CreateCircleByRadius(
                XC: 0,
                YC: eyeletCenterZ,
                Zc: 0,
                Radius: EyeletInnerRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Rename sketch
            swModel.ForceRebuild3(false);
            IFeature eyeletSketch = swModelExt.GetLastFeatureAdded();
            eyeletSketch.Name = "Eyelet Ring Sketch";

            // Select sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: eyeletSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select eyelet ring sketch");
                return;
            }

            // Extrude symmetric
            IFeature eyeletFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: EyeletThickness / 2,
                D2: EyeletThickness / 2,
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
                Merge: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false);

            if (eyeletFeature == null)
            {
                Console.WriteLine("WARNING: Failed to create eyelet ring");
            }
            else
            {
                eyeletFeature.Name = "Lifting Eyelet";
            }
        }

        public void PrintPartDetails()
        {
            Console.WriteLine("\nPart Details:");
            Console.WriteLine($"- Base plate: {BasePlateWidth / InchToMeter}\" x {BasePlateDepth / InchToMeter}\" x {BasePlateThickness / InchToMeter}\"");
            Console.WriteLine($"- Frame height: {FrameHeight / InchToMeter}\"");
            Console.WriteLine($"- Frame width: {FrameBottomWidth / InchToMeter}\" (bottom) to {FrameTopWidth / InchToMeter}\" (top)");
            Console.WriteLine($"- Frame thickness: {FrameThickness / InchToMeter}\"");
            Console.WriteLine($"- Bearing housing radius: {BearingHousingRadius / InchToMeter}\"");
            Console.WriteLine($"- Bearing hole radius: {BearingHoleRadius / InchToMeter}\"");
            Console.WriteLine($"- Cutout window: {CutoutWidth / InchToMeter}\" x {CutoutHeight / InchToMeter}\"");
            Console.WriteLine($"- Mounting holes: 4 x {MountingHoleRadius * 2 / InchToMeter}\" diameter");
        }
    }
}
