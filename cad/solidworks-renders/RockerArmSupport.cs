using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates a rocker arm support (A-frame bearing stand) for the harmonic analyzer.
    ///
    /// Features:
    /// - Base plate: rectangular with mounting holes at corners
    /// - A-frame sides: two tapered plates forming triangular shape
    /// - Center cutout: rectangular window for clearance
    /// - Top bearing housing: cylindrical boss for pivot shaft
    /// - Lifting eyelet: ring at top for chain attachment
    /// - Fillets: rounded edges for cast appearance
    /// </summary>
    public class RockerArmSupport : IPartCreator
    {
        public string PartName => "Rocker Arm Support";
        public string FileName => "rocker-arm-support.sldprt";

        // Dimensions (in inches, converted to meters for SolidWorks API)
        private const double InchToMeter = 0.0254;

        // Base plate parameters
        private const double BasePlateLength = 6.0 * InchToMeter;      // X direction
        private const double BasePlateWidth = 3.0 * InchToMeter;       // Y direction (depth)
        private const double BasePlateThickness = 0.5 * InchToMeter;   // Z direction

        // Mounting hole parameters
        private const double MountingHoleRadius = 0.25 * InchToMeter;
        private const double MountingHoleInset = 0.5 * InchToMeter;    // From edge

        // A-frame side plate parameters
        private const double AFrameHeight = 5.0 * InchToMeter;         // Z direction from base top
        private const double AFrameBaseWidth = 5.0 * InchToMeter;      // Width at base (X)
        private const double AFrameTopWidth = 2.0 * InchToMeter;       // Width at top (X)
        private const double AFrameThickness = 0.4 * InchToMeter;      // Y direction (plate thickness)

        // Center cutout parameters
        private const double CutoutBottomOffset = 0.75 * InchToMeter;  // From base plate top
        private const double CutoutHeight = 3.0 * InchToMeter;
        private const double CutoutBottomWidth = 3.5 * InchToMeter;
        private const double CutoutTopWidth = 1.2 * InchToMeter;

        // Top bearing housing parameters
        private const double BearingHousingRadius = 0.75 * InchToMeter;
        private const double BearingHousingLength = 2.0 * InchToMeter; // Y direction
        private const double BearingHoleRadius = 0.375 * InchToMeter;  // For shaft

        // Lifting eyelet parameters
        private const double EyeletOuterRadius = 0.4 * InchToMeter;
        private const double EyeletInnerRadius = 0.2 * InchToMeter;
        private const double EyeletHeight = 0.75 * InchToMeter;        // Above bearing housing
        private const double EyeletThickness = 0.3 * InchToMeter;

        // Fillet radius
        private const double FilletRadius = 0.15 * InchToMeter;
        private const double SmallFilletRadius = 0.05 * InchToMeter;

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

            Console.WriteLine("Creating mounting holes...");
            CreateMountingHoles(swModel);

            Console.WriteLine("Creating bearing housing...");
            CreateBearingHousing(swModel);

            Console.WriteLine("Creating bearing hole...");
            CreateBearingHole(swModel);

            Console.WriteLine("Creating lifting eyelet...");
            CreateLiftingEyelet(swModel);

            Console.WriteLine("Adding fillets...");
            AddFillets(swModel);

            // Rebuild the model
            swModel.ForceRebuild3(true);

            return swModel;
        }

        /// <summary>
        /// Creates the base plate: rectangular plate on XY plane
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
                X2: BasePlateLength / 2, Y2: BasePlateWidth / 2, Z2: 0);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature sketch = swModelExt.GetLastFeatureAdded();
            sketch.Name = "Base Plate Sketch";

            selected = swModelExt.SelectByID2(
                Name: sketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select base plate sketch");

            // Extrude downward (negative Z)
            IFeature feature = swFeatMgr.FeatureExtrusion3(
                Sd: true,
                Flip: false,
                Dir: true,  // Reverse direction (down)
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

            if (feature == null)
                throw new InvalidOperationException("Failed to extrude base plate");

            feature.Name = "Base Plate";
        }

        /// <summary>
        /// Creates the A-frame body: tapered triangular shape
        /// Sketch on Front Plane (XZ), extrude in Y direction
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
                throw new InvalidOperationException("Failed to select Front Plane for A-frame");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // A-frame profile (trapezoid)
            // Bottom left
            double bottomLeft = -AFrameBaseWidth / 2;
            double bottomRight = AFrameBaseWidth / 2;
            double topLeft = -AFrameTopWidth / 2;
            double topRight = AFrameTopWidth / 2;
            double bottomZ = 0;  // On base plate top surface
            double topZ = AFrameHeight;

            // Draw trapezoid: bottom -> right side -> top -> left side -> close
            swSketchMgr.CreateLine(bottomLeft, bottomZ, 0, bottomRight, bottomZ, 0);  // Bottom
            swSketchMgr.CreateLine(bottomRight, bottomZ, 0, topRight, topZ, 0);       // Right side
            swSketchMgr.CreateLine(topRight, topZ, 0, topLeft, topZ, 0);              // Top
            swSketchMgr.CreateLine(topLeft, topZ, 0, bottomLeft, bottomZ, 0);         // Left side

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature sketch = swModelExt.GetLastFeatureAdded();
            sketch.Name = "A-Frame Sketch";

            selected = swModelExt.SelectByID2(
                Name: sketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select A-frame sketch");

            // Extrude symmetric in Y direction
            IFeature feature = swFeatMgr.FeatureExtrusion3(
                Sd: false,  // Both directions
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: AFrameThickness / 2,
                D2: AFrameThickness / 2,
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

            if (feature == null)
                throw new InvalidOperationException("Failed to extrude A-frame");

            feature.Name = "A-Frame Body";
        }

        /// <summary>
        /// Creates the center cutout (window) in the A-frame
        /// </summary>
        private void CreateCenterCutout(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane
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

            // Cutout profile (trapezoid shape matching A-frame taper)
            double bottomZ = CutoutBottomOffset;
            double topZ = CutoutBottomOffset + CutoutHeight;
            double bottomHalfWidth = CutoutBottomWidth / 2;
            double topHalfWidth = CutoutTopWidth / 2;

            // Draw cutout trapezoid
            swSketchMgr.CreateLine(-bottomHalfWidth, bottomZ, 0, bottomHalfWidth, bottomZ, 0);  // Bottom
            swSketchMgr.CreateLine(bottomHalfWidth, bottomZ, 0, topHalfWidth, topZ, 0);         // Right
            swSketchMgr.CreateLine(topHalfWidth, topZ, 0, -topHalfWidth, topZ, 0);              // Top
            swSketchMgr.CreateLine(-topHalfWidth, topZ, 0, -bottomHalfWidth, bottomZ, 0);       // Left

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature sketch = swModelExt.GetLastFeatureAdded();
            sketch.Name = "Center Cutout Sketch";

            selected = swModelExt.SelectByID2(
                Name: sketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select cutout sketch");

            // Cut through all (both directions)
            IFeature feature = swFeatMgr.FeatureCut4(
                Sd: false,
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
                NormalCut: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                AssemblyFeatureScope: false,
                AutoSelectComponents: false,
                PropagateFeatureToParts: false,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false,
                OptimizeGeometry: false);

            if (feature == null)
                throw new InvalidOperationException("Failed to create center cutout");

            feature.Name = "Center Cutout";
        }

        /// <summary>
        /// Creates mounting holes in the base plate corners
        /// </summary>
        private void CreateMountingHoles(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Top Plane
            bool selected = swModelExt.SelectByID2(
                Name: "Top Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Top Plane for mounting holes");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Four corner holes
            double holeX = BasePlateLength / 2 - MountingHoleInset;
            double holeY = BasePlateWidth / 2 - MountingHoleInset;

            swSketchMgr.CreateCircleByRadius(holeX, holeY, 0, MountingHoleRadius);
            swSketchMgr.CreateCircleByRadius(-holeX, holeY, 0, MountingHoleRadius);
            swSketchMgr.CreateCircleByRadius(holeX, -holeY, 0, MountingHoleRadius);
            swSketchMgr.CreateCircleByRadius(-holeX, -holeY, 0, MountingHoleRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature sketch = swModelExt.GetLastFeatureAdded();
            sketch.Name = "Mounting Holes Sketch";

            selected = swModelExt.SelectByID2(
                Name: sketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select mounting holes sketch");

            // Cut through base plate
            IFeature feature = swFeatMgr.FeatureCut4(
                Sd: true,
                Flip: false,
                Dir: true,
                T1: (int)swEndConditions_e.swEndCondThroughAll,
                T2: (int)swEndConditions_e.swEndCondBlind,
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
                NormalCut: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                AssemblyFeatureScope: false,
                AutoSelectComponents: false,
                PropagateFeatureToParts: false,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false,
                OptimizeGeometry: false);

            if (feature == null)
                throw new InvalidOperationException("Failed to create mounting holes");

            feature.Name = "Mounting Holes";
        }

        /// <summary>
        /// Creates the cylindrical bearing housing at the top
        /// </summary>
        private void CreateBearingHousing(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane for circle sketch
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

            // Circle at top of A-frame
            double centerZ = AFrameHeight;
            swSketchMgr.CreateCircleByRadius(0, centerZ, 0, BearingHousingRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature sketch = swModelExt.GetLastFeatureAdded();
            sketch.Name = "Bearing Housing Sketch";

            selected = swModelExt.SelectByID2(
                Name: sketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select bearing housing sketch");

            // Extrude symmetric in Y direction
            IFeature feature = swFeatMgr.FeatureExtrusion3(
                Sd: false,
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: BearingHousingLength / 2,
                D2: BearingHousingLength / 2,
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

            if (feature == null)
                throw new InvalidOperationException("Failed to create bearing housing");

            feature.Name = "Bearing Housing";
        }

        /// <summary>
        /// Creates the center hole through the bearing housing
        /// </summary>
        private void CreateBearingHole(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for bearing hole");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            double centerZ = AFrameHeight;
            swSketchMgr.CreateCircleByRadius(0, centerZ, 0, BearingHoleRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature sketch = swModelExt.GetLastFeatureAdded();
            sketch.Name = "Bearing Hole Sketch";

            selected = swModelExt.SelectByID2(
                Name: sketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select bearing hole sketch");

            // Cut through all
            IFeature feature = swFeatMgr.FeatureCut4(
                Sd: false,
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
                NormalCut: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                AssemblyFeatureScope: false,
                AutoSelectComponents: false,
                PropagateFeatureToParts: false,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false,
                OptimizeGeometry: false);

            if (feature == null)
                throw new InvalidOperationException("Failed to create bearing hole");

            feature.Name = "Bearing Hole";
        }

        /// <summary>
        /// Creates the lifting eyelet at the top
        /// </summary>
        private void CreateLiftingEyelet(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for eyelet");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Eyelet profile: outer circle with inner circle (ring)
            double eyeletCenterZ = AFrameHeight + BearingHousingRadius + EyeletHeight;

            // Outer ring
            swSketchMgr.CreateCircleByRadius(0, eyeletCenterZ, 0, EyeletOuterRadius);
            // Inner hole
            swSketchMgr.CreateCircleByRadius(0, eyeletCenterZ, 0, EyeletInnerRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature sketch = swModelExt.GetLastFeatureAdded();
            sketch.Name = "Lifting Eyelet Sketch";

            selected = swModelExt.SelectByID2(
                Name: sketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select eyelet sketch");

            // Extrude symmetric
            IFeature feature = swFeatMgr.FeatureExtrusion3(
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

            if (feature == null)
                throw new InvalidOperationException("Failed to create lifting eyelet");

            feature.Name = "Lifting Eyelet";

            // Add connecting piece from bearing to eyelet
            CreateEyeletConnector(swModel, swSketchMgr, swFeatMgr, swModelExt);
        }

        /// <summary>
        /// Creates the connector piece between bearing housing and eyelet
        /// </summary>
        private void CreateEyeletConnector(IModelDoc2 swModel, ISketchManager swSketchMgr,
            IFeatureManager swFeatMgr, IModelDocExtension swModelExt)
        {
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for connector");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Rectangular connector from top of bearing housing to bottom of eyelet
            double bottomZ = AFrameHeight + BearingHousingRadius * 0.5;
            double topZ = AFrameHeight + BearingHousingRadius + EyeletHeight - EyeletOuterRadius;
            double halfWidth = EyeletOuterRadius * 0.8;

            swSketchMgr.CreateCenterRectangle(
                X1: 0, Y1: (bottomZ + topZ) / 2, Z1: 0,
                X2: halfWidth, Y2: topZ, Z2: 0);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature sketch = swModelExt.GetLastFeatureAdded();
            sketch.Name = "Eyelet Connector Sketch";

            selected = swModelExt.SelectByID2(
                Name: sketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select connector sketch");

            IFeature feature = swFeatMgr.FeatureExtrusion3(
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

            if (feature == null)
                throw new InvalidOperationException("Failed to create eyelet connector");

            feature.Name = "Eyelet Connector";
        }

        /// <summary>
        /// Adds fillets to edges for cast appearance
        /// Note: Fillets require manual edge selection which is complex to automate.
        /// This method is a placeholder - fillets can be added manually in SolidWorks.
        /// </summary>
        private void AddFillets(IModelDoc2 swModel)
        {
            // Fillets require selecting specific edges, which is complex to automate
            // without knowing the exact edge IDs. In production, you would:
            // 1. Select specific faces/edges programmatically
            // 2. Use FeatureFillet3 with the selection
            // For now, we note that fillets should be added manually for the cast look.
            Console.WriteLine("Note: Add fillets manually in SolidWorks for cast appearance");
            Console.WriteLine("  - Fillet the A-frame internal edges at cutout");
            Console.WriteLine("  - Fillet transition from base plate to A-frame");
            Console.WriteLine("  - Fillet bearing housing to A-frame connection");
        }

        public void PrintPartDetails()
        {
            Console.WriteLine("\nPart Details:");
            Console.WriteLine($"- Base plate: {BasePlateLength / InchToMeter}\" x {BasePlateWidth / InchToMeter}\" x {BasePlateThickness / InchToMeter}\"");
            Console.WriteLine($"- A-frame height: {AFrameHeight / InchToMeter}\"");
            Console.WriteLine($"- A-frame base width: {AFrameBaseWidth / InchToMeter}\"");
            Console.WriteLine($"- A-frame top width: {AFrameTopWidth / InchToMeter}\"");
            Console.WriteLine($"- A-frame thickness: {AFrameThickness / InchToMeter}\"");
            Console.WriteLine($"- Cutout: {CutoutBottomWidth / InchToMeter}\" x {CutoutHeight / InchToMeter}\" (tapered)");
            Console.WriteLine($"- Bearing housing: {BearingHousingRadius * 2 / InchToMeter}\" dia x {BearingHousingLength / InchToMeter}\" long");
            Console.WriteLine($"- Bearing hole: {BearingHoleRadius * 2 / InchToMeter}\" dia");
            Console.WriteLine($"- Mounting holes: 4x {MountingHoleRadius * 2 / InchToMeter}\" dia");
        }
    }
}
