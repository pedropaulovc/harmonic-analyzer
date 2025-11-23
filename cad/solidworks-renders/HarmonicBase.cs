using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates a harmonic analyzer base - two-plate welded construction.
    /// Translated from base.kcl
    ///
    /// Features a bottom plate (11" x 18" x 0.5") with a top plate
    /// (10.5" x 17.5" x 1.5") centered on top.
    /// NOTE: KCL version includes fillets; this version creates basic geometry without fillets.
    /// </summary>
    public class HarmonicBase : IPartCreator
    {
        public string PartName => "Harmonic Analyzer Base";
        public string FileName => "harmonic-base.sldprt";

        // Bottom plate parameters (in inches, converted to meters for SolidWorks API)
        private const double BottomWidth = 11.0 * 0.0254;      // 11 inches
        private const double BottomLength = 18.0 * 0.0254;     // 18 inches
        private const double BottomHeight = 0.5 * 0.0254;      // 0.5 inches

        // Top plate parameters (in inches, converted to meters for SolidWorks API)
        private const double TopWidth = 10.5 * 0.0254;         // 10.5 inches
        private const double TopLength = 17.5 * 0.0254;        // 17.5 inches
        private const double TopHeight = 1.5 * 0.0254;         // 1.5 inches

        // Fillet radii
        private const double FilletRadius = 0.125 * 0.0254;        // 0.125 inches - bottom plate edges
        private const double EdgeFilletRadius = 0.0625 * 0.0254;  // 0.0625 inches - top plate intersection

        // Calculated parameters
        private const double TotalHeight = (0.5 + 1.5) * 0.0254; // bottomHeight + topHeight

        private ISldWorks swApp;

        public HarmonicBase(ISldWorks solidWorksApp)
        {
            swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));
        }

        /// <summary>
        /// Creates the harmonic analyzer base part
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

            // Create the base geometry
            IFeature bottomFeature = CreateBottomPlate(swModel);
            IFeature topFeature = CreateTopPlate(swModel);

            // Add fillets
            ApplyBottomPlateFillets(swModel, bottomFeature);
            ApplyTopPlateFillets(swModel, topFeature);

            // Rebuild the model
            swModel.ForceRebuild3(true);

            return swModel;
        }

        /// <summary>
        /// Validates design parameters (translated from KCL assertions)
        /// </summary>
        private void ValidateParameters()
        {
            if (TopWidth >= BottomWidth)
                throw new ArgumentException("Top plate must be narrower than bottom");

            if (TopLength >= BottomLength)
                throw new ArgumentException("Top plate must be shorter than bottom");
        }

        /// <summary>
        /// Creates the bottom plate (centered at origin)
        /// </summary>
        private IFeature CreateBottomPlate(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select XY Plane (Front Plane)
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

            // Create bottom plate rectangle centered at origin
            // KCL centers at [-bottomLength/2, -bottomWidth/2]
            // SolidWorks CreateCenterRectangle takes center point and corner point
            object rect = swSketchMgr.CreateCenterRectangle(
                X1: 0, Y1: 0, Z1: 0,                                // Center point
                X2: BottomLength / 2, Y2: BottomWidth / 2, Z2: 0);  // Corner point

            if (rect == null)
                throw new InvalidOperationException("Failed to create bottom plate rectangle");

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
                throw new InvalidOperationException("Failed to select bottom plate sketch for extrusion");

            // Extrude the bottom plate
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Don't flip extrusion direction
                T1: (int)swEndConditions_e.swEndCondBlind,        // Blind extrusion
                T2: (int)swEndConditions_e.swEndCondBlind,        // Not used for single direction
                D1: BottomHeight,                                  // Extrusion depth
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
                throw new InvalidOperationException("Failed to extrude bottom plate");

            return extrudeFeature;
        }

        /// <summary>
        /// Creates the top plate (centered on top of bottom plate)
        /// </summary>
        private IFeature CreateTopPlate(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select the top face of the bottom plate to sketch on
            // The face is at Z = BottomHeight from the Front Plane
            bool selected = swModelExt.SelectByID2(
                Name: "Boss-Extrude1",
                Type: "BODYFEATURE",
                X: 0, Y: 0, Z: BottomHeight,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                // Alternative: Try selecting the face directly
                // SelectByID2 can be tricky with face selection, so let's select a plane offset
                // Instead, we'll sketch on a plane offset from Front Plane
                selected = swModelExt.SelectByID2(
                    Name: "Front Plane",
                    Type: "PLANE",
                    X: 0, Y: 0, Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: 0);

                if (!selected)
                    throw new InvalidOperationException("Failed to select plane for top plate");
            }

            // Insert sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Create top plate rectangle centered at origin
            object rect = swSketchMgr.CreateCenterRectangle(
                X1: 0, Y1: 0, Z1: 0,                          // Center point
                X2: TopLength / 2, Y2: TopWidth / 2, Z2: 0);  // Corner point

            if (rect == null)
                throw new InvalidOperationException("Failed to create top plate rectangle");

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Get the sketch name (should be Sketch2)
            swModel.ForceRebuild3(false);
            IFeature topSketch = swModelExt.GetLastFeatureAdded();
            if (topSketch == null)
                throw new InvalidOperationException("Failed to get top plate sketch");

            string sketchName = topSketch.Name;
            Console.WriteLine($"DEBUG: Top plate sketch name: {sketchName}");

            // Select the sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select top plate sketch '{sketchName}' for extrusion");

            // Extrude the top plate from the top of the bottom plate
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Don't flip extrusion direction
                T1: (int)swEndConditions_e.swEndCondBlind,        // Blind extrusion
                T2: (int)swEndConditions_e.swEndCondBlind,        // Not used for single direction
                D1: TopHeight,                                     // Extrusion depth
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
                Merge: true,                                       // Merge result with bottom plate
                UseFeatScope: false,                               // Affect all bodies
                UseAutoSelect: true,                               // Auto-select bodies
                T0: (int)swStartConditions_e.swStartOffset,       // Start with offset from sketch plane
                StartOffset: BottomHeight,                         // Offset by bottom plate height
                FlipStartOffset: false);                           // Don't flip start offset

            if (extrudeFeature == null)
                throw new InvalidOperationException("Failed to extrude top plate");

            return extrudeFeature;
        }

        /// <summary>
        /// Applies fillets to the bottom plate edges
        /// </summary>
        private void ApplyBottomPlateFillets(IModelDoc2 swModel, IFeature bottomFeature)
        {
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select the feature to fillet its edges
            bool selected = swModelExt.SelectByID2(
                Name: bottomFeature.Name,
                Type: "BODYFEATURE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 1,  // Mark = 1 for edges to fillet
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine($"WARNING: Could not select bottom plate feature '{bottomFeature.Name}' for filleting");
                return;
            }

            // Create fillet definition
            object filletData = swFeatMgr.CreateDefinition((int)swFeatureNameID_e.swFmFillet);
            if (filletData == null)
            {
                Console.WriteLine("WARNING: Failed to create fillet definition");
                swModel.ClearSelection2(true);
                return;
            }

            ISimpleFilletFeatureData2 filletFeatureData = (ISimpleFilletFeatureData2)filletData;

            // Initialize as constant radius fillet
            filletFeatureData.Initialize((int)swSimpleFilletType_e.swConstRadiusFillet);

            // Set fillet properties
            filletFeatureData.DefaultRadius = FilletRadius;  // 0.125 inches
            filletFeatureData.OverflowType = (int)swFilletOverFlowType_e.swFilletOverFlowType_Default;
            filletFeatureData.ConicTypeForCrossSectionProfile = (int)swFeatureFilletProfileType_e.swFeatureFilletCircular;

            // Create the fillet feature
            swModel.ClearSelection2(true);
            IFeature filletFeature = swFeatMgr.CreateFeature(filletFeatureData);

            if (filletFeature == null)
            {
                Console.WriteLine("WARNING: Failed to create bottom plate fillet feature");
            }
            else
            {
                Console.WriteLine($"SUCCESS: Created fillet on bottom plate with radius {FilletRadius * 1000 / 0.0254:F3} inches");
            }
        }

        /// <summary>
        /// Applies fillets to the top plate intersection edges
        /// </summary>
        private void ApplyTopPlateFillets(IModelDoc2 swModel, IFeature topFeature)
        {
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select the feature to fillet its edges
            bool selected = swModelExt.SelectByID2(
                Name: topFeature.Name,
                Type: "BODYFEATURE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 1,  // Mark = 1 for edges to fillet
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine($"WARNING: Could not select top plate feature '{topFeature.Name}' for filleting");
                return;
            }

            // Create fillet definition
            object filletData = swFeatMgr.CreateDefinition((int)swFeatureNameID_e.swFmFillet);
            if (filletData == null)
            {
                Console.WriteLine("WARNING: Failed to create fillet definition");
                swModel.ClearSelection2(true);
                return;
            }

            ISimpleFilletFeatureData2 filletFeatureData = (ISimpleFilletFeatureData2)filletData;

            // Initialize as constant radius fillet
            filletFeatureData.Initialize((int)swSimpleFilletType_e.swConstRadiusFillet);

            // Set fillet properties
            filletFeatureData.DefaultRadius = EdgeFilletRadius;  // 0.0625 inches
            filletFeatureData.OverflowType = (int)swFilletOverFlowType_e.swFilletOverFlowType_Default;
            filletFeatureData.ConicTypeForCrossSectionProfile = (int)swFeatureFilletProfileType_e.swFeatureFilletCircular;

            // Create the fillet feature
            swModel.ClearSelection2(true);
            IFeature filletFeature = swFeatMgr.CreateFeature(filletFeatureData);

            if (filletFeature == null)
            {
                Console.WriteLine("WARNING: Failed to create top plate fillet feature");
            }
            else
            {
                Console.WriteLine($"SUCCESS: Created fillet on top plate with radius {EdgeFilletRadius * 1000 / 0.0254:F3} inches");
            }
        }

        /// <summary>
        /// Prints harmonic base part details
        /// </summary>
        public void PrintPartDetails()
        {
            Console.WriteLine("\nPart Details:");
            Console.WriteLine("- Bottom plate: 18\" x 11\" x 0.5\"");
            Console.WriteLine("- Top plate: 17.5\" x 10.5\" x 1.5\"");
            Console.WriteLine("- Total height: 2.0\"");
            Console.WriteLine("- Bottom plate fillet radius: 0.125\"");
            Console.WriteLine("- Top plate intersection fillet radius: 0.0625\"");
        }
    }
}
